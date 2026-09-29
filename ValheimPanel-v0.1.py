#!/usr/bin/env python3
"""Panneau de configuration Valheim (Docker, image lloesche/valheim-server).

Aucune dépendance : Python 3.9+ et Docker Compose v2.
Usage :  python3 valheim_panel.py            (accessible depuis cette machine)
         python3 valheim_panel.py --lan      (accessible depuis le réseau local)
Le mot de passe du panneau est généré au premier lancement (panel_password.txt).
"""
import argparse, base64, hmac, json, os, re, secrets, shutil, subprocess, sys, zipfile
from urllib.parse import quote, unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG, ENV, COMPOSE, PWFILE = (ROOT / n for n in
                             ("config.json", ".env", "docker-compose.yml", "panel_password.txt"))

PRESETS = ["normal", "casual", "easy", "hard", "hardcore", "immersive", "hammer", "custom"]
MODS = {
    "combat": ["default", "veryeasy", "easy", "hard", "veryhard"],
    "deathpenalty": ["default", "casual", "veryeasy", "easy", "hard", "hardcore"],
    "resources": ["default", "muchless", "less", "more", "muchmore", "most"],
    "raids": ["default", "none", "muchless", "less", "more", "muchmore"],
    "portals": ["default", "casual", "hard", "veryhard"],
}
KEYS = ["nodeathpenalty", "nomap", "noportals", "playerevents", "passivemobs", "nobuildcost"]

DEFAULTS = {
    "name": "Mon serveur Valheim", "world": "Monde1", "password": "", "public": False,
    "crossplay": False, "port": 2456, "preset": "normal",
    "modifiers": {k: "default" for k in MODS}, "keys": [], "admins": [], "mods": False,
}

COMPOSE_TPL = """services:
  valheim:
    image: ghcr.io/lloesche/valheim-server
    container_name: valheim
    cap_add: [SYS_NICE]
    env_file: .env
    ports:
      - "{a}-{b}:{a}-{b}/udp"
    volumes:
      - ./data/config:/config
      - ./data/server:/opt/valheim
      - ./mods:/config/bepinex/plugins
    restart: unless-stopped
    stop_grace_period: 2m
"""


MODS_DIR = ROOT / "mods"
MAX_MOD = 200 * 1024 * 1024


def _landscape():
    trees = "".join(f"M{x-15} 360L{x} {305-(i*37)%45}L{x+15} 360z" for i, x in enumerate(range(25, 1600, 62)))
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 360'>"
            "<path fill='#0b1a2b' fill-opacity='.30' d='M0 360V180l170-70 130 70 190-130 180 110 140-60 210 130 150-90 190 100 240-100V360z'/>"
            "<path fill='#0b1a2b' fill-opacity='.55' d='M0 360V250l150-60 130 50 190-90 170 90 160-50 200 70 180-60 170 60 250-50V360z'/>"
            f"<path fill='#0b1a2b' d='{trees}'/><rect y='342' width='1600' height='18' fill='#0b1a2b'/></svg>")


# Un profil par jeu : titre, ciel (clair, sombre) et paysage de fond.
GAMES = {"valheim": {"title": "Mon serveur Valheim", "sky": ("#dbe6ee,#b9cddc", "#0c1a2c,#1d3653"),
                     "svg": _landscape()}}


def render(game):
    g = GAMES[game]
    art = 'url("data:image/svg+xml,' + quote(g["svg"]) + '")'
    return (PAGE.replace("%%TITLE%%", g["title"]).replace("%%SKYL%%", g["sky"][0])
            .replace("%%SKYD%%", g["sky"][1]).replace("%%ART%%", art))


def mod_list():
    MODS_DIR.mkdir(exist_ok=True)
    out = []
    for p in sorted(MODS_DIR.iterdir()):
        size = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        out.append({"name": p.name, "size": f"{size / 1e6:.1f} Mo"})
    return {"mods": out}


def save_mod(name, rfile, n):
    name = Path(name).name
    if not re.fullmatch(r"[\w .+()-]{1,100}\.(dll|zip)", name, re.I):
        return {"ok": False, "errors": ["Fichier .dll ou .zip attendu (nom simple)."]}
    if not 0 < n <= MAX_MOD:
        return {"ok": False, "errors": ["Fichier vide ou supérieur à 200 Mo."]}
    MODS_DIR.mkdir(exist_ok=True)
    tmp, left = MODS_DIR / (name + ".part"), n
    with open(tmp, "wb") as f:
        while left:
            chunk = rfile.read(min(65536, left))
            if not chunk:
                break
            f.write(chunk)
            left -= len(chunk)
    try:
        if left:
            raise ValueError("envoi interrompu")
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(tmp) as z:
                z.extractall(MODS_DIR / name[:-4])
            tmp.unlink()
        else:
            tmp.replace(MODS_DIR / name)
    except (zipfile.BadZipFile, ValueError, OSError) as ex:
        tmp.unlink(missing_ok=True)
        return {"ok": False, "errors": [f"Mod refusé : {ex}"]}
    return {"ok": True}


def delete_mod(name):
    p = MODS_DIR / Path(name).name
    if not name or not p.exists() or p.parent != MODS_DIR:
        return {"ok": False, "errors": ["Mod introuvable."]}
    shutil.rmtree(p) if p.is_dir() else p.unlink()
    return {"ok": True}


def install_service(lan, port, game):
    import pwd
    if os.geteuid() != 0:
        sys.exit("Lance cette commande avec sudo.")
    user = os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    args = f"--port {port} --game {game}" + (" --lan" if lan else "")
    Path("/etc/systemd/system/valheim-panel.service").write_text(f"""[Unit]
Description=Panneau de configuration serveur de jeu
After=network-online.target docker.service
Wants=network-online.target

[Service]
User={user}
WorkingDirectory={ROOT}
ExecStart={sys.executable} {Path(__file__).resolve()} {args}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
""")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "valheim-panel"], check=True)
    print(f"Service installé (utilisateur {user}). Mot de passe : {ROOT / 'panel_password.txt'}")


def load():
    try:
        return {**DEFAULTS, **json.loads(CFG.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def validate(d):
    """Retourne (config propre, liste d'erreurs en français)."""
    e, c = [], {}
    c["name"] = str(d.get("name", "")).strip()
    if not re.fullmatch(r"[\w .-]{1,40}", c["name"]):
        e.append("Nom du serveur : 1 à 40 caractères (lettres, chiffres, espaces, - . _).")
    c["world"] = str(d.get("world", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", c["world"]):
        e.append("Nom du monde : lettres sans accent, chiffres, - et _ (30 max).")
    c["password"] = str(d.get("password", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{5,40}", c["password"]):
        e.append("Mot de passe : 5 à 40 caractères (lettres, chiffres, - . _).")
    elif c["password"].lower() in c["name"].lower():
        e.append("Le mot de passe ne doit pas être contenu dans le nom du serveur.")
    c["public"], c["crossplay"] = bool(d.get("public")), bool(d.get("crossplay"))
    c["mods"] = bool(d.get("mods"))
    try:
        c["port"] = int(d.get("port", 2456))
        if not 1024 <= c["port"] <= 65530:
            raise ValueError
    except (TypeError, ValueError):
        e.append("Port : un nombre entre 1024 et 65530.")
    c["preset"] = d.get("preset")
    if c["preset"] not in PRESETS:
        e.append("Difficulté inconnue.")
    mods = d.get("modifiers") or {}
    c["modifiers"] = {k: mods.get(k, "default") for k in MODS}
    if any(c["modifiers"][k] not in v for k, v in MODS.items()):
        e.append("Réglage de difficulté personnalisé invalide.")
    c["keys"] = [k for k in d.get("keys", []) if k in KEYS]
    c["admins"] = [str(a).strip() for a in d.get("admins", []) if str(a).strip()]
    if not all(re.fullmatch(r"\d{5,20}", a) for a in c["admins"]):
        e.append("Administrateurs : un identifiant numérique par ligne (ID Steam64).")
    return c, e


def write_files(c):
    env = [f"SERVER_NAME={c['name']}", f"WORLD_NAME={c['world']}", f"SERVER_PASS={c['password']}",
           f"SERVER_PUBLIC={int(c['public'])}", f"SERVER_PORT={c['port']}",
           f"CROSSPLAY={'true' if c['crossplay'] else 'false'}", "BACKUPS=true"]
    if c["preset"] != "custom":
        env.append(f"PRESET={c['preset']}")
    else:
        env += [f"MODIFIER_{k.upper()}={v}" for k, v in c["modifiers"].items() if v != "default"]
    if c["mods"]:
        env.append("BEPINEX=true")
    if c["keys"]:
        env.append("SERVER_ARGS=" + " ".join(f"-setkey {k}" for k in c["keys"]))
    if c["admins"]:
        env.append("ADMINLIST_IDS=" + " ".join(c["admins"]))
    MODS_DIR.mkdir(exist_ok=True)
    ENV.write_text("\n".join(env) + "\n")
    COMPOSE.write_text(COMPOSE_TPL.format(a=c["port"], b=c["port"] + 2))
    CFG.write_text(json.dumps(c, indent=2))


def compose(*args, timeout=300):
    try:
        r = subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, str(ex)


def status():
    ok, out = compose("ps", "--format", "{{.State}}", timeout=20)
    if not ok:
        return "inconnu"
    return "en marche" if "running" in out else "arrêté"


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%%TITLE%%</title>
<style>
:root{color-scheme:light;--ink:#1b2430;--mute:#5b6675;--line:#d5dbe2;--acc:#2f5d8c;--ok:#2e7d4f;--bad:#b3382c;--card:#fff;--field:#fff;--onacc:#fff;--okbg:#e6f3ea;--badbg:#f8e6e3;--sky:linear-gradient(180deg,%%SKYL%%);--art:%%ART%%}[data-theme=dark]{color-scheme:dark;--ink:#e6ebf1;--mute:#a3afbf;--line:#33414f;--acc:#7db0e3;--ok:#6fcf9a;--bad:#f09a90;--card:#16202c;--field:#0f1822;--onacc:#0b1a2b;--okbg:#17352a;--badbg:#3b1f1c;--sky:linear-gradient(180deg,%%SKYD%%)}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--art) bottom center/100% auto no-repeat fixed,var(--sky) fixed;color:var(--ink);font:16px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.05rem;margin:0 0 12px}
.sub{color:var(--mute);margin:0 0 20px}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px;margin-bottom:16px}
label{display:block;font-weight:600;margin:12px 0 4px}label:first-of-type{margin-top:0}
small{display:block;color:var(--mute);font-weight:400}
input[type=text],input[type=password],input[type=number],select,textarea{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:6px;font:inherit;background:var(--field);color:var(--ink)}
.chk{display:flex;gap:10px;align-items:flex-start;font-weight:400;margin:10px 0}.chk input{margin-top:5px}
.row{display:flex;gap:8px}.row input{flex:1}
button{font:inherit;border:1px solid var(--acc);background:var(--acc);color:var(--onacc);padding:10px 18px;border-radius:6px;cursor:pointer}
button.alt{background:var(--card);color:var(--acc)}
:focus-visible{outline:3px solid #8fb4dd;outline-offset:2px}
#bar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
#state{font-weight:600}#msg{margin-top:14px;padding:10px 12px;border-radius:6px;display:none;white-space:pre-wrap}
#msg.ok{display:block;background:var(--okbg);color:var(--ok)}#msg.err{display:block;background:var(--badbg);color:var(--bad)}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:4px}
.sw{display:flex;align-items:center;gap:8px;font-weight:400;margin:0;cursor:pointer;color:var(--mute);position:relative}
.sw input{position:absolute;opacity:0}.sw i{width:42px;height:24px;border-radius:12px;background:var(--line);position:relative;transition:.2s}
.sw i::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:var(--card);transition:.2s}
.sw input:checked+i{background:var(--acc)}.sw input:checked+i::after{left:21px}.sw input:focus-visible+i{outline:3px solid #8fb4dd;outline-offset:2px}
#modbox{display:none}#modlist{list-style:none;padding:0;margin:12px 0 0}#modlist li{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-top:1px solid var(--line)}
#custom{display:none}details summary{cursor:pointer;color:var(--acc);margin-top:14px}
</style></head><body><main>
<header><h1>%%TITLE%%</h1><label class="sw"><span>Mode sombre</span><input type="checkbox" id="theme"><i></i></label></header>
<p class="sub">Modifiez les réglages ci-dessous, puis cliquez sur « Enregistrer et redémarrer ».</p>
<section><div id="bar"><div>État du serveur : <span id="state">…</span></div>
<button class="alt" type="button" id="refresh">Actualiser</button></div></section>

<section><h2>Le serveur</h2>
<label for="name">Nom du serveur</label><input type="text" id="name" maxlength="40">
<label for="world">Nom du monde<small>Un nouveau nom crée un nouveau monde. Sans accents ni espaces.</small></label>
<input type="text" id="world" maxlength="30">
<label for="password">Mot de passe pour rejoindre<small>5 caractères minimum, différent du nom du serveur.</small></label>
<div class="row"><input type="password" id="password"><button class="alt" type="button" id="show">Afficher</button></div>
<label class="chk"><input type="checkbox" id="public"><span>Serveur visible dans la liste publique<small>Sinon, on le rejoint par son adresse IP.</small></span></label>
<label class="chk"><input type="checkbox" id="crossplay"><span>Autoriser le crossplay (Xbox / Microsoft Store)</span></label>
<details><summary>Réglages avancés</summary>
<label for="port">Port du serveur<small>Change-le seulement si le port est déjà utilisé. Ouvre alors ports, port+1 et port+2 en UDP sur la box.</small></label>
<input type="number" id="port" min="1024" max="65530"></details></section>

<section><h2>Difficulté</h2>
<label for="preset">Niveau</label><select id="preset"></select>
<div id="custom"></div></section>

<section><h2>Règles spéciales</h2><div id="keys"></div></section>

<section><h2>Mods</h2>
<label class="chk"><input type="checkbox" id="mods"><span>Activer les mods (BepInEx)<small>Chaque joueur doit installer les mêmes mods. Les joueurs Xbox / Microsoft Store ne peuvent pas en installer.</small></span></label>
<div id="modbox"><label for="modfile">Ajouter un mod (.dll ou .zip)</label><input type="file" id="modfile" accept=".dll,.zip">
<small>Le mod est actif après « Enregistrer et redémarrer ».</small><ul id="modlist"></ul></div></section>

<section><h2>Administrateurs</h2>
<label for="admins">Identifiants Steam64, un par ligne<small>Les administrateurs peuvent ouvrir la console en jeu (F5).</small></label>
<textarea id="admins" rows="3"></textarea></section>

<button type="button" id="apply">Enregistrer et redémarrer</button>
<div id="msg" role="status" aria-live="polite"></div>
</main><script>
const $=id=>document.getElementById(id);
const PRESETS={normal:"Normal",casual:"Décontracté",easy:"Facile",hard:"Difficile",hardcore:"Hardcore",immersive:"Immersion",hammer:"Marteau",custom:"Personnalisé"};
const MODS={combat:["Combat",{default:"Par défaut",veryeasy:"Très facile",easy:"Facile",hard:"Difficile",veryhard:"Très difficile"}],
deathpenalty:["Pénalité de mort",{default:"Par défaut",casual:"Décontractée",veryeasy:"Très facile",easy:"Facile",hard:"Difficile",hardcore:"Hardcore"}],
resources:["Ressources",{default:"Par défaut",muchless:"Bien moins",less:"Moins",more:"Plus",muchmore:"Bien plus",most:"Maximum"}],
raids:["Raids",{default:"Par défaut",none:"Aucun",muchless:"Bien moins",less:"Moins",more:"Plus",muchmore:"Bien plus"}],
portals:["Portails",{default:"Par défaut",casual:"Libres",hard:"Sans minerai",veryhard:"Interdits"}]};
const KEYS={nodeathpenalty:"Aucune pénalité de mort",nomap:"Carte désactivée",noportals:"Portails désactivés",playerevents:"Événements selon les joueurs",passivemobs:"Créatures passives",nobuildcost:"Construction gratuite"};
const opt=(o,sel)=>Object.entries(o).map(([v,t])=>`<option value="${v}"${v===sel?" selected":""}>${t}</option>`).join("");
$("preset").innerHTML=opt(PRESETS);
$("custom").innerHTML=Object.entries(MODS).map(([k,[t,o]])=>`<label for="m_${k}">${t}</label><select id="m_${k}">${opt(o)}</select>`).join("");
$("keys").innerHTML=Object.entries(KEYS).map(([k,t])=>`<label class="chk"><input type="checkbox" data-key="${k}"><span>${t}</span></label>`).join("");
const toggle=()=>$("custom").style.display=$("preset").value==="custom"?"block":"none";
$("preset").onchange=toggle;
$("show").onclick=()=>{const p=$("password"),h=p.type==="password";p.type=h?"text":"password";$("show").textContent=h?"Masquer":"Afficher"};
function fill(c){["name","world","password","port","preset"].forEach(k=>$(k).value=c[k]);
$("public").checked=c.public;$("crossplay").checked=c.crossplay;$("mods").checked=c.mods;modtog();$("admins").value=c.admins.join("\\n");
Object.keys(MODS).forEach(k=>$("m_"+k).value=c.modifiers[k]||"default");
document.querySelectorAll("[data-key]").forEach(i=>i.checked=c.keys.includes(i.dataset.key));toggle()}
function collect(){const m={};Object.keys(MODS).forEach(k=>m[k]=$("m_"+k).value);
return{name:$("name").value,world:$("world").value,password:$("password").value,port:$("port").value,preset:$("preset").value,
public:$("public").checked,crossplay:$("crossplay").checked,mods:$("mods").checked,modifiers:m,
keys:[...document.querySelectorAll("[data-key]:checked")].map(i=>i.dataset.key),
admins:$("admins").value.split("\\n")}}
const say=(t,ok)=>{const m=$("msg");m.className=ok?"ok":"err";m.textContent=t};
async function state(){try{$("state").textContent=(await (await fetch("/api/status")).json()).state}catch(e){$("state").textContent="inconnu"}}
$("refresh").onclick=state;
$("apply").onclick=async()=>{$("apply").disabled=true;say("Redémarrage en cours, patiente quelques instants…",true);
try{const r=await fetch("/api/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(collect())});
const j=await r.json();say(j.ok?"Réglages enregistrés. Le serveur redémarre : compte 1 à 2 minutes avant de te reconnecter.":j.errors.join("\\n"),j.ok);state()}
catch(e){say("Le panneau ne répond pas. Vérifie qu'il est toujours lancé.",false)}$("apply").disabled=false};
const esc=s=>s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const setT=d=>{document.documentElement.dataset.theme=d?"dark":"light";$("theme").checked=d};
let saved=null;try{saved=localStorage.getItem("theme")}catch(e){}
setT(saved?saved==="dark":matchMedia("(prefers-color-scheme:dark)").matches);
$("theme").onchange=()=>{setT($("theme").checked);try{localStorage.setItem("theme",$("theme").checked?"dark":"light")}catch(e){}};
const modtog=()=>$("modbox").style.display=$("mods").checked?"block":"none";$("mods").onchange=modtog;
async function mods(){const r=await (await fetch("/api/mods")).json();
$("modlist").innerHTML=r.mods.map(m=>`<li><span>${esc(m.name)} <small>${m.size}</small></span><button class="alt" type="button" data-del="${esc(m.name)}">Supprimer</button></li>`).join("")||"<li><small>Aucun mod installé.</small></li>"}
$("modfile").onchange=async e=>{const f=e.target.files[0];if(!f)return;
const r=await fetch("/api/mods",{method:"POST",headers:{"X-Filename":encodeURIComponent(f.name)},body:f});const j=await r.json();
say(j.ok?"Mod ajouté : "+f.name+". Enregistre et redémarre pour l'activer.":j.errors.join("\\n"),j.ok);e.target.value="";mods()};
$("modlist").onclick=async e=>{const n=e.target.dataset.del;if(!n||!confirm("Supprimer "+n+" ?"))return;
await fetch("/api/mods/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:n})});mods()};
fetch("/api/config").then(r=>r.json()).then(fill);state();mods();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def authed(self):
        h = self.headers.get("Authorization", "")
        try:
            user, _, pw = base64.b64decode(h.split(" ", 1)[1]).decode().partition(":")
        except (IndexError, ValueError, UnicodeDecodeError):
            user, pw = "", ""
        ok = hmac.compare_digest(pw, self.server.panel_pw) and user == "admin"
        if not ok:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Valheim"')
            self.end_headers()
        return ok

    def send(self, body, ctype="application/json", code=200):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.authed():
            return
        if self.path == "/":
            self.send(render(self.server.game), "text/html")
        elif self.path == "/api/config":
            self.send(json.dumps(load()))
        elif self.path == "/api/mods":
            self.send(json.dumps(mod_list()))
        elif self.path == "/api/status":
            self.send(json.dumps({"state": status()}))
        else:
            self.send("{}", code=404)

    def do_POST(self):
        if not self.authed():
            return
        n = int(self.headers.get("Content-Length", 0))
        if self.path == "/api/mods":
            return self.send(json.dumps(save_mod(unquote(self.headers.get("X-Filename", "")), self.rfile, n)))
        if self.path == "/api/mods/delete":
            try:
                name = json.loads(self.rfile.read(n)).get("name", "")
            except ValueError:
                name = ""
            return self.send(json.dumps(delete_mod(name)))
        if self.path != "/api/apply":
            return self.send("{}", code=404)
        try:
            raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            return self.send(json.dumps({"ok": False, "errors": ["Requête invalide."]}), code=400)
        clean, errors = validate(raw)
        if errors:
            return self.send(json.dumps({"ok": False, "errors": errors}))
        write_files(clean)
        ok, out = compose("up", "-d", "--force-recreate")
        self.send(json.dumps({"ok": ok, "errors": [out or "Échec de Docker Compose."]}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", action="store_true", help="écouter sur le réseau local")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--game", default="valheim", choices=list(GAMES))
    ap.add_argument("--install-service", action="store_true", help="installer le service systemd (sudo)")
    a = ap.parse_args()
    if a.install_service:
        return install_service(a.lan, a.port, a.game)
    if not PWFILE.exists():
        PWFILE.write_text(secrets.token_urlsafe(9))
    srv = ThreadingHTTPServer(("0.0.0.0" if a.lan else "127.0.0.1", a.port), Handler)
    srv.panel_pw = PWFILE.read_text().strip()
    srv.game = a.game
    print(f"Panneau : http://localhost:{a.port}  (utilisateur : admin, mot de passe : {srv.panel_pw})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
