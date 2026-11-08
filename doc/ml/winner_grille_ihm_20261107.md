# Grille Winner — référence 20261107_095041_0b38b8de

Étude autorisée le 7 novembre 2026 : même batch
`model-factory-20261106203103-91b063`, même année 2025, dépôt initial 4 000 $,
compte margin, plafond de levier 2×, frais natifs et financement annuel 6,5 %.
Les prédictions et les modèles sont réutilisés ; aucun nouvel entraînement,
aucun téléchargement fournisseur ni ordre. Aucune configuration de production
n'est modifiée.

## Référence et question

Le run de référence termine à 4 275,9536665 $, rendement +6,89884 %, DD maximal
−10,85603 %, 59 trades et 1 334,04 $ engagés en moyenne (33,10 % du capital
courant ; environ 16,55 % de la capacité théorique à 2×). Les seuils score LONG
strictement >0,70 et AUC de calibration ≥0,60 laissent 204 signaux sur 250
séances. Le levier est une capacité, pas une obligation d'investir.

L'original demeure inchangé. La grille doit d'abord le reproduire avec le moteur
natif et une bande de données figée. Un écart financier interrompt la grille.
Les lacunes intraday restent des lacunes : mode journalier, protection sur 5m
complètes sinon OHLC quotidien avec collision défavorable prioritaire, sans
exclure une entrée en fonction de sa disponibilité future. Les résultats sont
donc exploratoires et conservent la qualification de couverture du moteur.

## Plan figé avant les résultats

128 croisements complets des axes suivants :

| Paramètre | Valeurs |
|---|---|
| Score LONG minimum strict | 0,60 / 0,70 |
| AUC de calibration minimum | désactivée / 0,60 |
| Risque budgété par entrée | 1,25 % / 2,50 % |
| Poids maximal par titre | 20 % / 40 % |
| SL | 3 % / 5 % |
| Durée de détention | 10 / 20 séances, sortie à l'ouverture suivante |
| Contrôleur de risque | désactivé / B4 DD15 avec liquidation 50 % |

Le pool reste TOP10 % (179 titres sur l'univers figé de 1 790), puis TOP10 LONG.
32 variantes complémentaires prédéfinies examinent pools 5/20 %, TOP5/20 LONG,
score 0,55/0,65 et AUC 0,55 ; SL1/7, TP10/20, trailing3/7/15, H5/15 ; demi-position
et renforcement gagnant, budgets 0,5/5 %, poids 10 %, minimums 25/100 $, 30
positions ; corrélation, secteurs et répétition des entrées ; confirmation 0/2
avec SIP retardé de 930 s. Deux combinaisons supplémentaires : SL3/TP15 et
trailing15/H20. Ces variantes partent d'une ancre fixée score >0,60, AUC≥0,60,
budget 2,5 %, poids 40 %, SL5/H10.

Amendement utilisateur avant tout replay financier : **108 croisements complets**
supplémentaires des trois filtres de sélection et du nombre de LONG :
TOP Oracle 5/10/20 % (90/179/358), score strict >0,55/0,60/0,65/0,70,
AUC désactivée/≥0,55/≥0,60, TOP5/10/20 LONG. Les autres paramètres sont ceux de
l'ancre ci-dessus. Total amendé : **269 replays avec la référence**.
Le premier gel partiel `20261107-v1` est conservé comme plan dépassé, sans
résultat financier. Le gel `v2`, également sans replay financier, est remplacé
par `v3` : EXPLAIN MySQL confirmait qu'à 254 symboles le moteur utilisait PRIMARY
au lieu de l'index date/intervalle. Les requêtes sont partitionnées par groupes
d'au plus 100 titres, puis réunies, avec les mêmes critères et contrôles.

Les délais de fraîcheur, réserves techniques et frais ne sont pas minimisés
pour améliorer artificiellement la performance. Le modèle reste un Oracle H10
même si une variante conserve sa position pendant 20 séances. Les paramètres
factoriels désactivés n'apportent aucune information nouvelle dans cette étude.

## Lecture et limites

Chaque cas conserve configuration, progression, courbes, trades, événements,
frais, financement, rendement, DD maximal, taux gagnant, exposition moyenne et
maximale, utilisation de la capacité de levier, nombre de signaux et motifs de
refus. `comparison.csv` compare tous les cas ; `pareto.csv` conserve ceux pour
lesquels aucun autre cas n'améliore à la fois rendement et DD. Les échecs de
données, notamment des variantes intraday strictes, restent visibles et exclus
du classement des rendements. DD15 déclenche une réaction ; il ne garantit pas
un maximum de perte de 15 %.

La recherche examine 2025 déjà observé : aucun résultat ne constitue une
validation indépendante, et aucun meilleur réglage n'est déployé automatiquement.
La stabilité trimestrielle et les variantes proches doivent accompagner les
trois propositions finales, puis une autre période doit les confirmer.

Critères de restitution fixés avant les replays : rendement positif et au moins
30 trades clôturés ; frontière de Pareto rendement/DD. Le compromis descriptif
classe le rendement divisé par `max(5, |DD en %|)`, puis distingue le rendement
maximal et une alternative de DD inférieur avec rendement au moins égal à la
référence. Ce rapport n'est ni une probabilité prédictive ni une garantie de
robustesse. Les courbes trimestrielles et les réglages voisins restent à examiner.

## Exécution et suivi

Script : `scripts/research/us_winner_ui_grid_20261107.py` ; phases `prepare`,
`reference`, `run`, `summarize`. Dossier
`artifacts/research/us_winner_ui_grid/20261107-v3/` : `protocol.json` immuable,
`inputs/manifest.json` et ses empreintes, `progress.json`, `comparison.csv`,
`pareto.csv`, `cases/<nom>/progress.json` et rapports. Les entrées SQL sont lues
une fois sous transaction en lecture seule, puis les replays utilisent uniquement
les fichiers figés. Trois processus de simulation au maximum, indépendants des
processus de batch et des comptes Alpaca.

La restitution peut être enchaînée pendant que la grille tourne :
`python -m scripts.research.us_winner_ui_grid_review_20261107 --wait`.
Elle publie `live-status.json` avec les séances des trois cas actifs, puis
`review/summary.md`, les trois compromis admissibles et leurs réglages complets,
les contrôles de voisinage/concentration et `review/capital-drawdown.png`.
Une grille en échec n'est pas relancée par cette phase.

### Augmentation du parallélisme — 7 novembre, 15 h 25 Paris

Sur demande utilisateur, passage de trois à **huit simulations simultanées**.
Les 85 rapports alors terminés sont conservés et contrôlés par empreinte ; les
trois cas actifs ont été interrompus puis repris depuis le début. Les cinq
processus de l'ancien arbre ont été vérifiés arrêtés avant la reprise : aucun
second coordinateur ne travaille sur les mêmes dossiers.

Le lanceur `scripts/research/us_winner_ui_grid_parallel_resume_20261107.py`
réutilise le moteur et le protocole financier figés ; il modifie seulement le
nombre de processus passé au coordinateur. Le protocole initial reste inchangé
avec son réglage historique à trois ; `runtime-amendments/` enregistre la demande,
le nouveau parallélisme et les empreintes des rapports déjà terminés.
Le journal de reprise est `run-workers8.log`. Aucun paramètre de sélection,
risque, coût, levier ou protection n'a changé.
