# Grille Winner 2016–2026 : contrôle préalable, choix de période nécessaire

> **Amendement du 23 octobre : période confirmée par l'utilisateur :
> 02/06/2017–30/09/2026.** Le choix demandé ci-dessous est donc résolu.
> [Bilan de la qualification des scores et suite](winner_grille_2017_2026_perimetre_valide_20261023.md).
> Le contrôle des scores est terminé ; la grille économique n'est pas encore lancée.

23 octobre2026. Demande utilisateur : exploiter le backfill5m depuis2016,
rejouer une grille et remettre trois combinaisons intéressantes.
**La grille économique n'est pas lancée ; aucun TOP3 n'est calculé.**
L'étape préalable a trouvé une borne Oracle incompatible avec la période
exacte demandée. Ne pas attribuer aux prix téléchargés une capacité de
prédiction qu'aucun modèle causal archivé ne couvre.

## Ce qui est confirmé

Inventaire local des quatre modèles actifs OracleparcoursH20, de leurs folds
etOOF ;44requêtes SQL de données indexées, limitées à une ligne, dans une
transaction READONLY. Aucun scanCOUNTglobal de l'intraday, aucun fournisseur,
écritureSQL, téléchargement, réentraînement, ordre ou changement de production.

Artefacts :
`artifacts/research/us_winner_grid_history_readiness/20261023-v1/report.json`
et `fold-inventory.csv`. Deux tests de causalité/agrégation passent.
Les reçus des fichiers de progression sont des snapshots horodatés : ils
peuvent évoluer, un étatRUNNING n'est pas une preuve de processus vivant.

## Oracle : 2016 ne peut pas être un backtest hors échantillon actuel

| Modèle | Première dateOOF | Dernière dateOOF |
| --- | --- | --- |
| `model-factory-20261014113215-437ed1` | **02/06/2017** | 05/06/2024 |
| `model-factory-20261014113226-102eca` | 04/06/2018 | 09/06/2025 |
| `model-factory-20261014113232-bc35a7` | 06/06/2019 | 13/07/2026 |
| `model-factory-20261016180250-3b0515` | 02/07/2021 | 07/08/2026 |

Le premier fold disponible du premier modèle a ses derniers labels train au
29/11/2016, val au01/06/2017 et commence à scorer le02/06/2017. Les bornes de
disponibilité train/validation vérifiées sont antérieures à chaque test.
Les poids/lineages et profils devront encore être figés pour le dataset final.

Le fichierOOF du premier modèle contient2 981 241scores, notamment147dates
en2017,251en2018,252en2019,253en2020,252en2021,251en2022,250en2023 et108en2024.
Ce n'est pas encore une certification de complétude quotidienne de TOP10.
Les anciennes archives de recherche comparatives commencent plus tard,
le05/07/2018 ; elles ne sont donc pas la meilleure borne disponible.

La table`oracle_path_prediction_lineage` ne contient pas de ligne2016–2023 dans
les requêtes annuelles ; les scores plus anciens existent dans les archives
OOF locales, pas dans cette table. Les premières lignes stockées2024–2026
correspondent aux modèles annuels déjà utilisés. Il ne faut pas confondre
absence enSQL et absence de tout score historique.

**2016–01/06/2017 sert à l'amorçage des modèles existants.** Pour tester réellement
une stratégie Oracle dèsjanvier2016, il faudrait d'abord qualifier des données
antérieures et produire un Oracle entraîné/validé avant chaque date testée.
Ne pas appliquer le modèle2024/2025/2026 à2016 et appeler cela horséchantillon.
Nouvel entraînement ou rescoring historique à proposer explicitement, pas un
fallback caché du backtest.

## Intraday : présent depuis2016, mais complétude non encore certifiée

Univers des plans :1790titres de
`config/univers_batch/univers_filtred_tradable.txt`, empreinte d'origine
`7f5bf0ac2212be129d2ba11fe7a9ab832c0f91cd05b2d345b34270d8173b76c8`.
Requêtes de présence annuelles surAA/ANF/HOV, fluxAlpacaSIP/régulier/raw/5m,
marchéUS_EQ/nonrempli. Une ligne présente ne signifie pas séance ou année complète.
AAPL/SPY ne font pas partie de ce fichier : leur absence intraday n'est pas
qualifiée de trou ; le benchmarkdaily reste un besoin séparé.

Snapshots de progression :

- 2016–2017, `intraday-8d1e1a8598a44500affb` :COMPLETED,44750/44750tâches,
  dont11298vides,0échec. Les50 740 252lignes persistées sont un compteur de
  soumissions, pas un nombre garanti de lignes uniques/séances régulières.
- 2018, `intraday-5dfcdc71cfaf4819ed1b` :BLOCKED après429,18679/23270tâches,
  1échec, dernierHOV28/10→27/11. Le plan2018–2019
  `intraday-75d9f29edb1bb670e48c` afficheRUNNING192/44750au snapshot ; ne pas
  le relancer ou l'arrêter automatiquement, ni supposer qu'il a terminé.
- 2019, `intraday-62fb58d72bff570d2bb4` :COMPLETED23270/23270,0échec.
- 2020–2024, `intraday-3c3998fbeeddd84f0034` :COMPLETED109190/109190,
  0échec,10836tâches vides.
- 2025–2026, planSIP`intraday-fbc507f68cbaf2824fe7` :RUNNING23914/39380au
  snapshot ; le plan2026`intraday-54e358aaf00a49fba091` estCOMPLETED17900/17900.
  Des snapshots ciblés2025/2026 ont déjà permis nos tests récents, mais ne
  certifient pas tout ce nouveau périmètre. L'ancien planIEX est exclu.

Il reste à mesurer la couverture titre×séance réellement nécessaire aux TOP10
et aux fenêtres d'attente/détention, avec séances écourtées, provenance,
identités/OST et trous. Tâches vides ne veut pas automatiquement dire erreur :
IPO, absence de cotation et disponibilité fournisseur doivent être distinguées.

## Choix demandé avant le calcul lourd

Proposition : **2016–début2017 comme amorçage**, puis grille du02/06/2017 au
30/09/2026, 2017et2026 signalées partielles. Confirmer ce changement de période
plutôt que présenter une fausse grille2016–2026. Autre voie : étudier un nouvel
Oracle antérieur pour inclure réellement2016 ; coût et données à qualifier d'abord.

Une fois la période confirmée : définir et sceller la grilleLONG autour du
contratWinner actuel (inclure les variantes récentesSL3/TP7ou15/TR3/open11),
les règles de risque/frais/capital et le critère de choix des trois profils.
Ne pas réutiliser aveuglément l'ancienne grille rapide144LONG+144SHORT : son
échéanceJ+H et ses213campagnes diffèrent du runtime depuis le fill.
Une grilleSHORT demanderait un contrat d'emprunt/exécution séparé, non fourni
par le runtimeWinnerLONG actuel ; ne pas l'ajouter silencieusement.

Les trois profils devront être comparés parannée, rendement net/DD, capital
utilisé, taux gagnant, coûts et voisins de paramètres, avec sélection temporelle
et réserves de survivants/PIT. Aucun réglage « optimal » garanti, ni période
déjà vue présentée comme holdout indépendant.
