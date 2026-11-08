# Winner continu 2021–2026 avec six modèles annuels

Demande : un portefeuille unique du1er janvier2021 au1er octobre2026,4 000 USD
au départ, avec les modèles correspondant aux six backtests IHM transmis.

## Mapping des modèles

| Année des entrées | Run source | Batch | Début / fin du training |
| --- | --- | --- | --- |
| 2021 | 20261108_090441_57f9e2b2 | model-factory-20261107222539-837309 | 2014-01-01 / 2020-12-31 |
| 2022 | 20261108_091552_f146212e | model-factory-20261107222557-280d86 | 2015-01-01 / 2021-12-31 |
| 2023 | 20261108_093814_765b1b66 | model-factory-20261107222607-f44095 | 2016-01-01 / 2022-12-31 |
| 2024 | 20261108_094643_52aa43f9 | model-factory-20261107222618-89a4d2 | 2017-01-01 / 2023-12-31 |
| 2025 | 20261107_225127_babce5b8 | model-factory-20261106203103-91b063 | 2018-01-01 / 2024-12-31 |
| 2026, jusqu'au01/10 | 20261108_101309_93f8fb1b | model-factory-20261107222627-db80b0 | 2019-01-01 / 2025-12-31 |

Tous sont des bundles Oracle parcours H10, univers1 790, LONG/SHORT par titre.
La sélection et le replay restent LONG uniquement. Les empreintes des modèles,
des scores Oracle et des branches annuelles sont contrôlées ; aucun entraînement
ou calcul de nouvelles prédictions n'est lancé.

Le mapping concerne **l'année d'entrée J+1** : le premier signal du run2022
est le31/12/2021, pour une entrée le03/01/2022. Ce signal utilise le batch
du run2022, tout en conservant les exigences de disponibilité causale des poids
du fold Oracle et du modèle per-symbol annuel. Il ne faut pas concaténer les
scores en choisissant simplement le batch selon l'année du signal J.

## Conditions communes vérifiées

- Capital initial4 000 USD ; compte margin, exposition brute maximale2×.
- TOP10 LONG per-symbol ; score strictement >0,60 et AUC calibration ≥0,60.
- Risque1,25 % par entrée, poids maximal20 %,20 positions, minimum50 USD,
  quantités entières, position complète, aucun renforcement.
- Entrée au daily open J+1, sans confirmation5m ; SL5 %, sans TP ni trailing,
  dix séances de détention puis open11.
- B4/DD15 et perte quotidienne3 % actifs, liquidation50 % ; DD15 est un
  seuil de réaction et non un plafond garanti.
- Frais8 points de base par opération et financement6,5 % annuel.
- Mêmes limites de répétition et paramètres de risque que les six protocoles,
  aucun filtre options/GPT, aucun contrôle factoriel.

**Périmètre confirmé par l'utilisateur** : TOP20 % Oracle sur toutes les années,
soit 358 candidats sur l'univers de 1 790 titres, puis TOP10 LONG per-symbol.
Les runs sources 2021–2025 appliquaient déjà cette règle ; celui de 2026
prenait seulement TOP20 titres. Sa sélection est donc recalculée depuis les
scores archivés, sans nouvelle prédiction ni entraînement.
`replay-request.json` a été passé à `uniform20pct` le 08/11/2026 à
10:32:39 UTC, avant le démarrage du replay. La demande précédente est conservée
dans `replay-request.before-user-uniform20pct.json`. Le gel des prix inclut déjà
les deux périmètres et n'a pas besoin de recommencer.
La sélection uniforme comprend 5 606 candidatures, dont 1 078 en 2026,
avant les contrôles de risque et de capital : ce ne sont pas des trades exécutés.
Aucun rendement n'est déduit du produit des performances annuelles.

## Portefeuille et données

Un seul appel au moteur natif sur toute la période : capital, cash, positions,
âge réel de détention, financement, liquidations, état B4, DD et exclusions
temporaires par titre traversent les changements d'année. Aucun retour à4 000 $
au1er janvier, aucune liquidation annuelle artificielle. Les positions déjà
ouvertes conservent leurs protections et leur horizon d'origine.

Lecture SQL seulement pour figer les prix et opérations sur titres déjà stockés.
Préférence daily EODHD puis SIP, mêmes règles de qualification que les runs IHM.
Archives5m SIP régulières, sans téléchargement. Les lacunes restent des lacunes :
protections daily prudentes lorsqu'une séance5m est incomplète, sans exclusion
fondée sur la disponibilité future des bougies. Secteurs actuels, non PIT.

Programme : `scripts/research/us_winner_continuous_annual_models_20261108.py`.
Dossier : `artifacts/research/us_winner_continuous_annual_models/20261108-v2`.
Trois tests couvrent les tailles de pool, les frontières annuelles signal/entrée
et le refus de fusionner des conditions de portefeuille différentes.

Première tentative v1 arrêtée avant toute lecture SQL : les AUC du modèle2025
sont dans son diagnostic complémentaire vérifié, pas dans son ancien manifeste.
v2 utilise le même lecteur AUC que l'IHM et vérifie les diagnostics correspondants ;
le contrôle n'est pas désactivé. La sélection enregistrée de chaque run doit
être reproduite avant toute simulation continue.

## Suivi et sorties

`progress.json` indique la vérification des modèles, le gel des prix puis les
séances simulées. `protocol.json` et `inputs/manifest.json` scellent sources,
mapping et prix. Le replay demandé sera dans `continuous-uniform20pct`.
Sorties : bilan global,
bilan annuel du même portefeuille, trades, événements, capital quotidien/5m et
état du risque. Les rendements annuels utilisent le capital effectivement
hérité de l'année précédente ; les trades sont attribués à leur année de sortie.

Statut initial : préparation des entrées en cours. Étude exploratoire, sans
certification PIT complète ni parité live. Aucun ordre ou paramètre de
production modifié.

Le coordinateur local `scripts/research/us_winner_continuous_annual_models_followup.py`
attend le manifeste complet des entrées puis lance le replay choisi. Il ne
réessaie pas automatiquement une erreur de préparation ou de simulation et ne
fait aucun appel fournisseur/broker. Journaux dans `coordinator/`, suivi du
replay dans le `progress.json` global. Il s'agit du traitement de cette
simulation précise, sans automatisation récurrente.
