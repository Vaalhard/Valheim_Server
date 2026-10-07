#!/usr/bin/env python3
"""
Génère fiche_valheim.html : une fiche de personnage Valheim.

Utilisation :
    python3 generer_fiche.py
puis ouvrir fiche_valheim.html dans le navigateur.

Le script fait trois choses :
  1. il décrit les 24 compétences et leurs bonus au niveau 100 (partie DONNÉES) ;
  2. il les convertit en JSON (partie CONVERSION) ;
  3. il les glisse dans un modèle de page HTML et écrit le fichier (partie ÉCRITURE).

Pour corriger un bonus, il suffit de modifier un chiffre dans la partie DONNÉES
puis de relancer le script.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. DONNÉES
# ---------------------------------------------------------------------------
# Un effet = ce que la compétence apporte AU NIVEAU 100.
#   libelle : le texte affiché
#   maxi    : la valeur au niveau 100 (négatif = réduction)
#   unite   : "%" par défaut, ou "m" pour des mètres
# À un autre niveau, la valeur est : maxi × niveau / 100 (augmentation linéaire).


def effet(libelle, maxi, unite="%"):
    return {"libelle": libelle, "max": maxi, "unite": unite}


# Les armes de mêlée partagent les mêmes bonus : on les écrit une seule fois.
def bonus_arme():
    return [
        effet("de dégâts et de recul", 141),
        effet("d'endurance", -33),
    ]


CATEGORIES = [
    ("Armes et outils", [
        ("Haches", [
            effet("de dégâts et de recul (hors arbres)", 141),
            effet("d'endurance", -33),
        ]),
        ("Épées", bonus_arme()),
        ("Lances", bonus_arme()),
        ("Couteaux", bonus_arme()),
        ("Gourdins", bonus_arme()),
        ("Armes longues", bonus_arme()),
        ("Mains nues", bonus_arme()),
        ("Arcs", bonus_arme() + [effet("de temps de tirage", -80)]),
        ("Arbalètes", [
            effet("de dégâts et de recul", 141),
            effet("de temps de recharge", -50),
        ]),
        ("Pioches", bonus_arme()),
    ]),
    ("Défense et magie", [
        ("Blocage", [effet("d'armure de blocage", 50)]),
        ("Esquive", [effet("de coût en endurance", -50)]),
        ("Magie du sang", [
            effet("de dégâts et de recul", 200),
            effet("de protection", 250),
            effet("d'Eitr", -33),
            effet("de santé", -33),
        ]),
        ("Magie élémentaire", [
            effet("de dégâts et de recul", 141),
            effet("d'Eitr", -33),
        ]),
    ]),
    ("Déplacement", [
        ("Courir", [
            effet("de vitesse", 25),
            effet("d'endurance", -50),
        ]),
        ("Nager", [effet("d'endurance", -50)]),
        ("Sauter", [
            effet("de force de saut", 40),
            effet("de hauteur de saut", 100),
        ]),
        ("Discrétion", [
            effet("de visibilité initiale", -60),
            effet("de visibilité liée à la lumière", -20),
            effet("d'endurance", -75),
        ]),
        ("Monture", [
            effet("de vitesse de sprint", 25),
            effet("d'endurance", -50),
        ]),
    ]),
    ("Production et récolte", [
        ("Agriculture", [
            effet("de récolte bonus", 25),
            effet("de portée de la faucille", 1, unite="m"),
            effet("d'endurance de la faucille", -33),
            effet("d'endurance et de durabilité du cultivateur", -50),
        ]),
        ("Coupe du bois", [effet("de dégâts contre les arbres", 141)]),
        ("Pêche", [
            effet("de vitesse de rembobinage", 200),
            effet("d'endurance", -80),
        ]),
        ("Cuisine", [
            effet("de temps de préparation", -60),
            effet("de chance de plat bonus", 25),
            effet("d'endurance du plateau", -50),
        ]),
        ("Fabrication", [
            effet("de temps de fabrication", -60),
            effet("d'endurance et de durabilité du marteau", -50),
            effet("de chance d'objet bonus", 25),
        ]),
    ]),
]

# ---------------------------------------------------------------------------
# 2. CONVERSION en JSON (le navigateur lira ces données)
# ---------------------------------------------------------------------------


def construire_donnees():
    resultat = []
    numero = 0
    for nom_categorie, competences in CATEGORIES:
        liste = []
        for nom, effets in competences:
            numero += 1
            liste.append({"id": f"c{numero}", "nom": nom, "effets": effets})
        resultat.append({"categorie": nom_categorie, "competences": liste})
    return resultat


# ---------------------------------------------------------------------------
# 3. MODÈLE DE PAGE (HTML + CSS + JavaScript)
# ---------------------------------------------------------------------------
# Le texte __DONNEES__ sera remplacé par le JSON des compétences.

MODELE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fiche de personnage Valheim</title>
<style>
  :root {
    --fond: #182027;
    --panneau: #212c35;
    --ligne: #34434f;
    --texte: #e6dfcf;
    --discret: #9aa7ae;
    --bronze: #c2934f;
    --givre: #86b3c4;
    --gain: #9cc98a;
    --perte: #e0a070;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--fond);
    color: var(--texte);
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.55;
  }
  main { max-width: 860px; margin: 0 auto; padding: 2rem 1.2rem 4rem; }
  h1 { font-size: 2rem; margin: 0 0 .3rem; letter-spacing: .01em; }
  .intro { color: var(--discret); margin: 0 0 2.2rem; }
  section { margin-bottom: 2.6rem; }
  h2 {
    font-size: 1.35rem;
    margin: 0 0 1rem;
    padding-bottom: .5rem;
    border-bottom: 2px solid var(--bronze);
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 1rem; flex-wrap: wrap;
  }
  h2 .compte { font-size: .95rem; font-weight: normal; color: var(--discret); }
  .outils { display: flex; gap: .6rem; margin-bottom: 1.2rem; flex-wrap: wrap; }
  button {
    font: inherit; font-size: .92rem;
    background: transparent; color: var(--texte);
    border: 1px solid var(--ligne); border-radius: 4px;
    padding: .35rem .8rem; cursor: pointer;
  }
  button:hover { border-color: var(--bronze); }
  :focus-visible { outline: 2px solid var(--givre); outline-offset: 2px; }

  fieldset { border: 0; padding: 0; margin: 0 0 1.4rem; }
  legend { color: var(--bronze); font-weight: bold; margin-bottom: .4rem; padding: 0; }
  .grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: .25rem .8rem; }
  .grille label {
    display: flex; align-items: center; gap: .5rem;
    padding: .3rem .4rem; border-radius: 4px; cursor: pointer;
  }
  .grille label:hover { background: var(--panneau); }
  input[type=checkbox] { width: 1.05rem; height: 1.05rem; accent-color: var(--bronze); }

  .ligne-niveau {
    display: flex; align-items: center; justify-content: space-between;
    gap: 1rem; padding: .55rem .2rem; border-bottom: 1px solid var(--ligne);
  }
  .ligne-niveau input[type=number] {
    width: 5.2rem; font: inherit; text-align: right;
    background: var(--panneau); color: var(--texte);
    border: 1px solid var(--ligne); border-radius: 4px; padding: .3rem .5rem;
  }
  .ligne-niveau .sur { color: var(--discret); margin-left: .4rem; }

  .bloc-bonus { padding: .8rem 0; border-bottom: 1px solid var(--ligne); }
  .bloc-bonus h3 { margin: 0 0 .3rem; font-size: 1.05rem; }
  .bloc-bonus h3 span { color: var(--discret); font-weight: normal; font-size: .92rem; margin-left: .5rem; }
  .bloc-bonus ul { list-style: none; margin: 0; padding: 0; }
  .bloc-bonus li { padding: .1rem 0; }
  .valeur { font-weight: bold; display: inline-block; min-width: 5.5rem; }
  .gain { color: var(--gain); }
  .perte { color: var(--perte); }
  .vide { color: var(--discret); font-style: italic; margin: 0; }
</style>
</head>
<body>
<main>
  <h1>Fiche de personnage</h1>
  <p class="intro">Cochez vos compétences, saisissez leur niveau, et lisez les bonus obtenus. Vos choix sont gardés dans ce navigateur.</p>

  <section>
    <h2>Choisir les compétences <span class="compte" id="compte"></span></h2>
    <div class="outils">
      <button type="button" id="tout-cocher">Tout cocher</button>
      <button type="button" id="tout-decocher">Tout décocher</button>
    </div>
    <div id="choix"></div>
  </section>

  <section>
    <h2>Niveaux</h2>
    <div id="niveaux"></div>
  </section>

  <section>
    <h2>Bonus obtenus</h2>
    <div id="bonus"></div>
  </section>
</main>

<script>
// Les données viennent du script Python.
const DONNEES = __DONNEES__;

const CLE = "valheim_fiche_personnage_v1";   // nom de la sauvegarde dans le navigateur
const toutes = DONNEES.flatMap(c => c.competences);
const format = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

// Un niveau valide est un entier entre 0 et 100.
function limiter(valeur) {
  const n = parseInt(valeur, 10);
  if (isNaN(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

// --- État : { c1: {coche: true, niveau: 42}, ... } ---
let etat = {};
try { etat = JSON.parse(localStorage.getItem(CLE)) || {}; } catch (e) { etat = {}; }
for (const c of toutes) {
  const ancien = etat[c.id] || {};
  etat[c.id] = { coche: !!ancien.coche, niveau: limiter(ancien.niveau) };
}
function sauver() {
  try { localStorage.setItem(CLE, JSON.stringify(etat)); } catch (e) { /* sauvegarde indisponible */ }
}

const $ = id => document.getElementById(id);

// --- Partie 1 : cases à cocher ---
function afficherChoix() {
  $("choix").innerHTML = DONNEES.map(cat => `
    <fieldset>
      <legend>${cat.categorie}</legend>
      <div class="grille">
        ${cat.competences.map(c => `
          <label><input type="checkbox" data-id="${c.id}" ${etat[c.id].coche ? "checked" : ""}> ${c.nom}</label>
        `).join("")}
      </div>
    </fieldset>`).join("");
}

function afficherCompte() {
  const n = toutes.filter(c => etat[c.id].coche).length;
  $("compte").textContent = `${n} sur ${toutes.length} sélectionnées`;
}

// --- Partie 2 : niveaux des compétences cochées ---
function afficherNiveaux() {
  const choisies = toutes.filter(c => etat[c.id].coche);
  if (choisies.length === 0) {
    $("niveaux").innerHTML = '<p class="vide">Aucune compétence sélectionnée. Cochez-en plus haut.</p>';
    return;
  }
  $("niveaux").innerHTML = choisies.map(c => `
    <div class="ligne-niveau">
      <label for="n-${c.id}">${c.nom}</label>
      <span><input type="number" id="n-${c.id}" data-id="${c.id}" min="0" max="100" step="1" value="${etat[c.id].niveau}"><span class="sur">/ 100</span></span>
    </div>`).join("");
}

// --- Partie 3 : bonus calculés (valeur = max × niveau / 100) ---
function afficherBonus() {
  const choisies = toutes.filter(c => etat[c.id].coche);
  if (choisies.length === 0) {
    $("bonus").innerHTML = '<p class="vide">Les bonus apparaîtront ici dès qu\'une compétence sera sélectionnée.</p>';
    return;
  }
  $("bonus").innerHTML = choisies.map(c => {
    const niveau = etat[c.id].niveau;
    const lignes = c.effets.map(e => {
      const v = e.max * niveau / 100;
      const signe = v < 0 ? "\u2212" : "+";
      const classe = e.max < 0 ? "perte" : "gain";
      const espace = e.unite === "%" ? "\u00a0%" : "\u00a0" + e.unite;
      return `<li><span class="valeur ${classe}">${signe}${format.format(Math.abs(v))}${espace}</span> ${e.libelle}</li>`;
    }).join("");
    return `<div class="bloc-bonus"><h3>${c.nom}<span>niveau ${niveau}</span></h3><ul>${lignes}</ul></div>`;
  }).join("");
}

function toutAfficher() {
  afficherCompte();
  afficherNiveaux();
  afficherBonus();
}

// --- Réactions aux actions de l'utilisateur ---
$("choix").addEventListener("change", ev => {
  const id = ev.target.dataset.id;
  if (!id) return;
  etat[id].coche = ev.target.checked;
  sauver();
  toutAfficher();
});

$("niveaux").addEventListener("input", ev => {
  const id = ev.target.dataset.id;
  if (!id || ev.target.value === "") return;
  const n = limiter(ev.target.value);
  if (String(n) !== ev.target.value) ev.target.value = n;  // corrige une valeur hors limites
  etat[id].niveau = n;
  sauver();
  afficherBonus();
});

$("niveaux").addEventListener("change", ev => {
  const id = ev.target.dataset.id;
  if (!id) return;
  etat[id].niveau = limiter(ev.target.value);
  ev.target.value = etat[id].niveau;   // un champ vide revient à 0
  sauver();
  afficherBonus();
});

function toutDefinir(valeur) {
  for (const c of toutes) etat[c.id].coche = valeur;
  sauver();
  afficherChoix();
  toutAfficher();
}
$("tout-cocher").addEventListener("click", () => toutDefinir(true));
$("tout-decocher").addEventListener("click", () => toutDefinir(false));

afficherChoix();
toutAfficher();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# 4. ÉCRITURE du fichier HTML (à côté du script)
# ---------------------------------------------------------------------------


def main():
    donnees_json = json.dumps(construire_donnees(), ensure_ascii=False)
    page = MODELE.replace("__DONNEES__", donnees_json)
    sortie = Path(__file__).with_name("fiche_valheim.html")
    sortie.write_text(page, encoding="utf-8")
    print(f"Page créée : {sortie}")


if __name__ == "__main__":
    main()
