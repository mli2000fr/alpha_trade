# TOP20 : minimum 70 USD contre 155 USD, capital initial 4 000 USD

Protocole figé du 25 octobre 2026. Un seul nouveau compte, comparaison au
`FIXED_REFERENCE` terminé à 5 178,779578340831 USD (+29,47 %).

## Une seule différence

`risk_config.min_position_notional` : 155 devient 70 USD. Comparaison exhaustive
des configurations sérialisées ; minimum effectif vérifié dans les décisions
du module risque à l'exécution. Les presets actuels ne sont pas rechargés.
L'utilisateur a modifié son minimum à 70 ; aucun changement de production ici.
Les montants de cette étude US sont en USD, sans conversion EUR/USD.

## Conditions conservées

2 janvier 2020 au 31 décembre 2024 ; compte neuf de 4 000 USD, sans héritage
de 2019 ni remise à zéro annuelle. TOP20 Oracle original figé, critères de
couverture identiques. Positions complètes, sans renforcement, exposition
brute plafonnée à 1x à l'entrée ; risque par entrée 1,25 %, maximum 20 positions,
25 % par titre / 50 % par secteur, 10 entrées par titre sur 180 jours.
SL 5 %, ni TP ni trailing ; vingt séances entrée incluse, sortie open21.
Confirmation native de deux bougies 5m terminées après cassure du plus haut
précédent, exécution à l'ouverture suivante. Admission externe historique
SL3 puis redimensionnement SL5 conservés. Frais 8 points de base par jambe.
Risque B4 et seuil DD15 originaux conservés : PAS de nouvelle liquidation
globale, pause trois mois, remise à zéro du DD ou sélection mensuelle.

## Réalisation et vérifications

Chargement en processus isolé des deux moteurs archivés du témoin, jamais
remplacement des fichiers de production. Archives locales et reçus vérifiés
avant/après ; HTTP interdit, aucun SQL, fournisseur, LLM, entraînement ou ordre.
Audit indépendant cash/frais/positions/DD/sorties scalaires/confirmation/coverage.
Trace des décisions risque, courbes 5m et quotidiennes, opérations, métriques
et bilan annuel continu conservés. Une anomalie d'arrondi doit arrêter le run,
pas entraîner un relâchement silencieux des contrôles.

Commande : `.venv\Scripts\python.exe -u -m scripts.research.us_winner_min70_4000_20261025`.

Résultats : `artifacts/research/us_winner_min70_4000/20261025-v1`.
Suivi : `progress.json` ; bilan final `report.json`, années `annual-summary.csv`.

## Limites

Recherche exploratoire sur historique déjà examiné, secteurs actuels non PIT,
biais de sélection par couverture future préservé. Pas de parité live complète,
pas de preuve hors échantillon ni garantie de reproduire les gains du compte
à 7 980 USD. Comparer rendement, DD, frais, nombre de trades et exposition.
