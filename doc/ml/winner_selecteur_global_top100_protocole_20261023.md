# Sélecteur global Winner TOP100 — protocole avant entraînement

GO utilisateur du23octobre2026 après contrôle des deuxgrilles en cours.
Recherche séparée, sans modifier cesgrilles, Oracle, batchs, YAML, SQL oubroker.
Sortie : `artifacts/research/us_winner_global_selector/20261023-v1/`.
Script : `scripts/research/us_winner_global_selector_20261023.py`.

## Population, dates et causalité

TOP100 OracleparcoursH20 avant exclusions de prix, score décroissant/symbole
croissant. Reprise des mêmes modèles/folds causaux que la préparation des
grilles :437ed1 pour2017–2024,102eca pour2025,bc35a7 pour2026. OOF préférés ;
SQLavec lineage vérifiée seulement pour les dates entièrement absentes desOOF.
Ne pas lire les excursions/labels Oracle pour classer les candidats.

Apprentissage :02/06/2017–2024, TOP100. Validation2025 et test2026au30/09 :
**TOP10 primaire**, cible de l'utilisateur, pas résultat TOP100 présenté comme
résultat TOP10. Disponibilité commune des labels àJ+41séances, même si unprofil
sort avant ou ne déclenche pas d'entrée. Exclure du fit tout label pas mûr avant
le31/12/2024 ; purge identique fin2025 et30/09/2026. Pas de réentraînement2026.

Ancres parsymbole : première occasion chronologique puis blocage jusqu'àJ+41,
avant couverture/prix futurs. Si uneancre est malcouverte, pas de remplacement
immédiat par une occasion voisine mieuxcouverte. Conserver tous les motifs.
Les fenêtres d'unmême titre ne chevauchent pas, mais des titres au même moment
ne sont pas indépendants : pondération des dates et bootstrap mensuel.

2016 sert au warm-up des prix/modèles, pas à un rendement inventé. Avant de figer
lesprix, attendre la fin complète du rattrapage2018 ; ne pas lancer de nouvelle
collecte. SQL READONLY, une tranche/snapshot parsymbole, transactions libérées
entre symboles, archives/reçus et reprise sans recommencer les parties validées.

## Première version : six configurations figées

| Profil | SL | Trailing | TP | Détention |
| --- | ---: | ---: | ---: | ---: |
| REFERENCE |7 %|15 %|aucun|20séances|
| COURT |3 %|3 %|7 %|10séances|
| COURT_TP15 |3 %|3 %|15 %|10séances|
| EQUILIBRE |5 %|10 %|10 %|10séances|
| PATIENT |7 %|20 %|aucun|20séances|
| H15 |5 %|15 %|15 %|15séances|

Profils fixés sans attendre les gagnants des300combinaisons en cours. Les
anciens résultats connus restent déclarés : ne pas prétendre un protocole
entièrement vierge. Premier modèle limité aux protections/horizon ; taille,
confirmation et renforcement ne sont **pas** appris dans cetteversion.
HALF, sansajout, deuxclôtures5m complétées après cassure fraîche, attente20.
Première entrée commune aux sixprofils. Horizon depuislefill, ouverture de
la séance suivante, pas depuisledépart Oracle. Stopdur jamais desserré.

Labels unitaires nets à8bps/jambe, SL prioritaire dans une même bougie,
gapsSL au prixouvert, TPgap plafonné, trailing basé surhighs déjà terminés.
Arrondis Python au centime identiques au résolveurscalaire. Vérifications
vectoriel/scalaires survraiesbandes SIP et échantillon déterministe en cours
de construction. Séances exactement couvertes surJ..J+41, ycompris écourtées,
OHLCV positifs et provenance. Réserver toutes les configurations si trou ou
événement connu dans la fenêtre. Pas de remplissage artificiel, pas deTOP101.

Une absence d'entrée donne zéro aux sixprofils et reste dansleslabels.
Récompense : rendement net unitaire du profil moins celui deREFERENCE.
**Ce n'est pas un PnL de portefeuille** : pas de simulation fictive de quantités,
cash, levier, réinvestissement ou admissionrisque pour transformer les labels
en rendement annuel. Une comparaison économique nativedu sélecteur resterait
unétage séparé. Il ne peut contournerB4, les capssecteur/corrélation/marge, les
donnéesfraîches ou le budget derisque, ni décider de desserrer unstop live.

## Modèle global et données autorisées

Un LightGBM global CPU, conditionné par le contexte et le profil candidat,
pas un modèle parsymbole ou parannée. Vingt-sixvariables observablesàJ :
retours5/10/20/60/120, vol5/20/60, expansionvol, ATR/prix, ranges/gaps,
volume relatif, liquidité, distances de tendance/drawdown, contexte SPY
retours/vol/SMA50/200 et forcerelative, rangOracle normalisé. Aucun symbole,
année, rendementfutur ou horizonréalisé parmi les features. Contrôle préfixe
des features : leur valeur àJ ne change pas en ajoutant les cours aprèsJ.

**Macro premièreversion : proxys de prix SPY uniquement.** Les vintages
macroéconomiques révisables nonqualifiés ne sont pas injectés. **Secteurs
actuels nonPIT exclus des prédicteurs** ; leur présence en base ne suffit pas
à prouver un secteur historiquement connu. Ces familles pourront être ajoutées
aprèsqualification et comparaison dédiée, pas qualifiées par un meilleur PnL.

Hyperparamètres uniques avantfit : profondeur3,7feuilles,150arbres,
learningrate0,03, minimum150lignes/feuille, L1=0,1,L2=10,seed731,unthread.
Pas de recherche, d'earlystopping ou defit sur2025/2026. Chaque date a le même
poidstotal ; les sixprofils d'une mêmeoccasion ne créent pas sixcampagnes
indépendantes. Minimum avantfit :500ancres train,50validation,30test. Sinon
statut insuffisant explicite, pas de modèle forcé pour livrer un fichier.

ÀJ : REFERENCE par défaut. Autreprofil seulement si avantage netprédit>16bps,
marge figée avantfit ; égalité préférenceREFERENCE puisordre du tableau.
Ces prédictions sont des écarts de rendementattendu, pas une probabilité de
réussite et pas une prédictionLONG/SHORT. Fichier modèle et liste des features
conservés localement, aucune activationautomatique live/PAPER.

## Validation et test

2025 sert à choisir le meilleur profil **constant** de comparaison. Le modèle
global reste entraîné uniquement sur2017–2024 ; comparer aussi touslesconstants.
Figer le modèle et le comparateur dans `model/fit.json` **avant** calcul des
résultats2026. Évaluer TOP10 avec les mêmes ancres et mêmes exclusions dans
touslesbras. Publier tailles, entrées/noentry, rendements unitaires moyens et
médians, positifs/négatifs, répartition desprofils et comparaison parsplit.

Simple signal exploratoire nécessitant encore un testportefeuille si gain
unitaire2026>0,25point, au moinsdeuxprofils choisis, au moins6mois de test et
bornebasse bootstrapmensuel95 % du gain>0 (2000tirages,seed731). Sinon NO_GO.
Ce critère ne prouve ni rentabilité ni robustesse live. Un modèle entraîné
peut être livré avec verdictnégatif ; ne pas retoucher les seuils sur2026.

Réserves : univers actuel survivant, prix révisés, OOFstockéaujourd'hui,
couverturefuture conditionnant les exemples, OSTnonexhaustives, données OHLC
sans bid/ask/fills, échantillons liés parmarché, annéesdéjàbeaucoupétudiées.
L'élargissementTOP100 augmente les données possibles, pas la garantie de
signal ni le nombre d'observations indépendantes.

Commandes : `--phase smoke` valide le résolveur surarchiveslocales ;
`--phase all` construit/reprend le dataset puis entraîne et évalue si les
conditionssont remplies. `progress.json` distingue collecteREADONLY, attente,
fit, insuffisance et échec. Aucun nouveau téléchargement fournisseur/GPT.
