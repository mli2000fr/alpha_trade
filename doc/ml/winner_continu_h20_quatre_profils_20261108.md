# Quatre profils continus Oracle H20 — 2021–2026

Demande utilisateur du8 novembre2026 : reprendre le portefeuille continu avec
les six nouveaux bundles Oracle parcours H20 + LONG/SHORT per-symbol, et
quatre profils Q088/Q051. LONG uniquement pour les achats.

## Modèles annuels figés

| Année d'entrée J+1 | Batch H20 | Début / fin d'entraînement |
| --- | --- | --- |
| 2021 | model-factory-20261108113730-607284 | 2014-01-01 / 2020-12-31 |
| 2022 | model-factory-20261108113738-f4ed09 | 2015-01-01 / 2021-12-31 |
| 2023 | model-factory-20261108113750-fc2601 | 2016-01-01 / 2022-12-31 |
| 2024 | model-factory-20261108130316-b54c49 | 2017-01-01 / 2023-12-31 |
| 2025 | model-factory-20261108130325-addb06 | 2018-01-01 / 2024-12-31 |
| 2026 | model-factory-20261108130333-7a5385 | 2019-01-01 / 2025-12-31 |

Les six modèles sont terminés, univers1 790 titres, contrats Oracle/directionnel
H20 et SL5. Le batch correspondant à l'année de l'entrée est utilisé ; le signal
précédant la première entrée annuelle peut être dans l'année précédente.
Les poids et AUC internes restent soumis à leur disponibilité causale.

## Quatre tests demandés

| Profil | Oracle | LONG per-symbol | Score strict > | AUC calibration ≥ | Plafond d'entrée | B4/DD15 / liquidation |
| --- | --- | --- | ---: | ---: | ---: | --- |
| H20_Q088_060 | TOP20 %,358 | TOP10 | 0,60 | 0,60 | 2× | Actifs, liquidation50 % |
| H20_Q088_050 | TOP20 %,358 | TOP10 | 0,50 | 0,50 | 2× | Actifs, liquidation50 % |
| H20_Q051_060 | TOP10 %,179 | TOP5 | 0,60 | 0,60 | 1× | Désactivés |
| H20_Q051_050 | TOP10 %,179 | TOP5 | 0,50 | 0,50 | 1× | Désactivés |

Même période que les tests continus précédents :01/01/2021–01/10/2026.
4 000 USD initiaux, aucun reset annuel du cash, des positions ou des exclusions.
Position complète, entrée à l'ouverture J+1 sans confirmation5m, SL5 %, sans TP
ni trailing. **Vingt séances de détention, puis sortie à l'ouverture de la21e**.
Compte margin de capacité2× pour tous ; Q051 conserve son plafond1× sur les
nouveaux achats. Risque par entrée1,25 %, poids maximal20 %, maximum20 positions,
minimum50 USD, quantités entières. Frais8bps par opération, financement6,5 % annuel.
Facteurs, corrélation, limites sectorielles, options et GPT désactivés.
Autres règles de répétition/cooldown identiques aux profils précédents.

## Prédictions à préparer

À la qualification initiale :2021–2023 ont leurs scores Oracle et LONG/SHORT,
2024 est en cours (processus existant préservé),2025/2026 n'ont pas encore de scores.
Deux calculs ML Predict H20 sont donc lancés pour2025/2026, sans doublon du2024.
Ce sont des prédictions de modèles existants, pas des entraînements.
Les scores et leur traçabilité sont écrits dans les tables de prédictions.
Aucun ordre, changement de compte ou appel fournisseur de cours n'est demandé.

Dates de signal requises, dérivées des séances officielles :

- 2021 :31/12/2020–30/12/2021,252 dates.
- 2022 :31/12/2021–29/12/2022,251 dates.
- 2023 :30/12/2022–28/12/2023,250 dates.
- 2024 :29/12/2023–30/12/2024,252 dates.
- 2025 :31/12/2024–30/12/2025,250 dates.
- 2026 :31/12/2025–30/09/2026,188 dates.

Le coordinateur attend la couverture des deux tables et la fin des processus.
Une couverture partielle ne déclenche pas le replay. Un arrêt de prédiction
incomplète reste un échec explicite, sans boucle de relance automatique.
Les lignées, horizons, folds, empreintes, scores et AUC sont ensuite revalidés.

## Cours et contrôle de référence

Les prix figés des campagnes précédentes sont réutilisés sans les remplacer.
Les cours SQL complémentaires concernent uniquement les couples symbole/séance
nécessaires au nouvel horizon qui n'avaient pas été interrogés. Une absence déjà
archivée n'est pas remplie rétroactivement. Les données5m sont inventoriées
de J+1 jusqu'à open21, sans filtre d'entrée fondé sur leur disponibilité future.
Les protections daily du replay et les réserves de couverture restent explicites.

Les cours daily, secteurs et opérations sur titres des nouveaux symboles sont
également figés. Aucun téléchargement fournisseur. Ces lectures sont READ ONLY.
Les étapes de prédiction seules écrivent leurs scores ; les replays sont isolés.
Registre des marchés validé/archivé une fois puis conservé pendant le replay.

Avant les quatre replays, Q088 H20 0,60/0,60 doit reproduire le backtest IHM2021
`20261108_163907_bc5802de` (−0,84803 %, DD−16,10831 %,78 trades), avec mêmes
sélections et conditions. Ses exports sont archivés dans la campagne pour qu'une
suppression ultérieure d'historique IHM ne détruise pas ce témoin.

## Exécution et consultation

Programme : `scripts/research/us_winner_continuous_h20_20261108.py`.
Suivi : `artifacts/research/us_winner_continuous_h20/20261108-v1/progress.json`.
Journal actif : `artifacts/research/us_winner_continuous_h20/launch-resume-20261108-v1.log`.
Demande figée : `request.json`. Puis protocole et manifeste des entrées, résultats
par profil dans `cases/<profil>/result`, comparaison globale et bilans annuels.
Quatre simulations peuvent tourner en parallèle après préparation et validation.

Import IHM automatique à chaque réussite, sans nouvelle simulation :

- `20261108_continu_H20_Q088_060_v1`
- `20261108_continu_H20_Q088_050_v1`
- `20261108_continu_H20_Q051_060_v1`
- `20261108_continu_H20_Q051_050_v1`

Libellés « Continu H20 2021–2026 — Q088/Q051 — seuils — open21 ».
Capital, rendement, DD, taux gagnant, capital engagé, trades, courbes et bilans
annuels conservés. Les résultats H10 précédents restent distincts et intacts.

10 tests passent sur les profils H20, l'échéance open21 officielle, la couverture
Oracle/directionnelle, les prix, les dates et l'import IHM ; le témoin annuel
reste utilisable après suppression simulée de l'export IHM initial.
État : attente des prédictions2024–2026. Aucun résultat H20 continu publié.
Étude rétrospective exploratoire : secteurs actuels et versions historiques non
certifiées PIT, parcours OHLC de couverture variable, absence de parité live
complète. Pas de choix de paramètres après observation des rendements H20.
