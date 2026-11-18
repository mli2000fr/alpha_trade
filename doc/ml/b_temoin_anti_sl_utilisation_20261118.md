# B témoin et B + anti-SL témoin — entraînement, backtest et exploitation

Vérification du18novembre2026, complétée par le raccordement natif anti-SL décrit ci-dessous. Aucun entraînement de production, changement de compte ou ordre lancé. Voir le guide `doc/ml/oracle_path_anti_sl_pipeline_20261118.md` pour les commandes et contrôles.

## Ce que désignent les deux stratégies

| Élément | B témoin | B + anti-SL témoin |
| --- | --- | --- |
| Oracle | Parcours H10 ; profil de référence173variables | Même Oracle |
| Direction | Modèles annuels par titre LONG/SHORT, groupe B29variables ; LONG utilisé | Mêmes modèles B29 |
| Sélection | TOP10%Oracle → TOP10LONG, score>0,50/AUC calibration≥0,50 | Même sélection, puis veto anti-SL sans remplacement |
| Modèle supplémentaire | Aucun | Classifieur mutualisé du SL5 pendant la première séance,44variables |
| Protections | Position complète, entréeJ+1, SL5%, sansTP/trailing/renforcement, open11 | Identiques |

Le nom «anti-SL dix séances» décrit les dix séances passées utilisées par quinze descripteurs supplémentaires ; le label est le stop de la **première séance suivante**, pas les stops de toute la détention.

Architecture disponible : un bundle Oracle+B commun, avec une tête anti-SL optionnelle. Réentraîner indépendamment deux Oracle/B différents confondrait l’effet du veto avec celui du changement de modèles. L’import automatique des anciens poids de recherche n’est pas proposé.

## B : entraînement déjà accessible dans l’IHM

Page Pipeline, **T1. ML Train (hors pipeline quotidien)** :

1. Univers : `config/univers_batch/univers_filtred_tradable.txt` ;1790symboles lors de cette vérification.
2. Cocher **Oracle Extreme parcours**, choisir **H10**.
3. Cocher **Bundle Oracle + deux modèles Per-Symbol LONG/SHORT**.
4. Cocher **Volatilité inhabituelle — per-symbol (B)**.
5. Laisser Global Ranking désactivé ; décocher l’exclusion per-symbol/per-sector si le formulaire la propose.
6. Choisir dates d’apprentissage et algorithme Oracle. La référence utilisait **comparaison automatique LightGBM/CatBoost** pour l’Oracle ; les branches B sont des LightGBM. Les dates et le profil de features doivent être vérifiés au contrat après entraînement.

Le groupe B contient les24variables compactes plus volatilité60/120 et z-scores de volatilité20/60/120 :29variables. Le flag natif est `--oracle-path-directional-features compact_volatility`. Il ne transforme pas les modèles24 ou173variables déjà entraînés.

Pour approcher le profil Oracle de recherche : `feature_set=expert`, `include_short_score=true`, `include_factors=true`, rangs transversaux activés ; sentiment, screener, fondamentaux, score_components, macroVIX/VXN/VIX3M/MOVE/régime et volume_features désactivés. Vérifier `oracle_path/feature_profile.json` :173colonnes dans la référence. Les29variables B restent distinctes des173de l’Oracle.

Après entraînement, vérifier :

- `oracle_path/protocol.json` : horizon10, bundle directionnel actif, `directional_contract.feature_mode=compact_volatility`.
- `oracle_path/directional/manifest.json` : `status=COMPLETED`, exactement29colonnes B, modèles LONG/SHORT, dates de fit/calibration/disponibilité et titres sans modèle explicités.
- Puis **ML Predict**, avec le même batch, sur les dates nécessaires au backtest ; inclure la séance précédant la première entrée.

Inventaire actuel : aucun batch natif `artifacts/models/model-factory-*/oracle_path/protocol.json` en mode `compact_volatility` n’a été trouvé. Les poids B utilisés par les expériences sont dans les archives de recherche. Les IDs Oracle historiques de ces études ne sont donc pas à supposer être des bundles natifs B29.

## B : backtest déjà accessible

Activer Winner et choisir le nouveau batch B, puis le profil **Q051 — B seul, volatilité inhabituelle per-symbol, TOP10**. Cliquer **Réappliquer le profil choisi**.

Le profil applique TOP10%Oracle, TOP10LONG, score>0,50/AUC≥0,50, LONG seul ; entrée journalièreJ+1 sans confirmation, position complète, SL5%, sansTP/trailing/renforcement, sortieopen11. Risque1,25%, poids20%,20positions, minimum50$, plafond achats1×/capacité margin2×, frais8pb/côté, financement6,5%. Sans budget vol20, régimeSPY, B4/DD, facteurs, corrélation, limites sectorielles ou pause100. Le filtre options/GPT ne fait pas partie de ces témoins.

L’univers vient du contrat du modèle. Le profil refuse un modèle dont le manifeste n’a pas les29variables B attendues. Il configure la stratégie ; il ne réentraîne pas le modèle et ne garantit pas le rendement historique+297,35%.

## B + anti-SL : entraînement et veto natifs disponibles

Le protocole de `scripts/research/us_q051_b_early_sl_20261116.py` est désormais porté dans ModelFactory. Dans T1, après H10, le bundle et B, **Ajouter le filtre anti-SL — trajectoire dix séances** est coché par défaut et peut être décoché. Un nouveau batch est nécessaire ; les anciens modèles ne sont pas modifiés.

La tête additionnelle utilise29variables B àJ et15descripteurs de trajectoireJ−9..J : delta, pente et écart-type des cinq indicateurs return5d, RSI14, ratio vol20/60, position dans range20, z-scorevol20. Modèle commun, entraîné sur les candidats Oracle OOF historiques causaux ; calendrier de fit/calibration et disponibilité figés. Seuil du veto =90epercentile des risques prédits en calibration, pas une suppression de10% des titres chaque jour.

L’entraînement produit un manifeste et des têtes annuelles scellées. ML Predict persiste les risques et leur traçabilité dans `oracle_path_anti_sl_predictions`. Le veto s’applique automatiquement après le TOP LONG natif ou personnalisé, sans remplacement. Une année sans tête qualifiée conserve les candidats avec abstention explicite ; un artefact déclaré manquant/corrompu ou des scores non enregistrés bloquent la lecture. Les tableaux montrent risque, seuil et exclusions. Les routes options/GPT seules refusent les batchs anti-SL plutôt que d’ignorer le filtre.

## Exploitation : ne pas confondre le profil actuel avec les témoins

Configuration vérifiée : `us_pipeline.q051_vol20_regime.enabled=true`, batch `model-factory-20261114122842-c59bed`. Ce batch est H10/per-symbol compact24, pas B29.

Le service `service/q051_paper` prend sa sélection dans `config/strategies/q051_vol20_regime_reference.json` : TOP10%Oracle→TOP5LONG, puis budget vol20 et régimeSPY. Son risque applique réellement ces deux protections. Il est explicitement réservé au **PAPER**, pas à un compte réel. Changer seulement `model_batch_id` ne change ni TOP5 enTOP10 ni les protections ; en revanche, si le nouveau batch déclare une tête anti-SL complète, son veto est désormais automatique après ce TOP5.

La prédiction native sait lire un bundleB29 et sa tête anti-SL. Pour reproduire exactement B témoin ou B+anti-SL dans le pipeline PAPER quotidien, il reste à créer des profils opérationnels explicites et versionnés : TOP10, mêmes tailles/protections que le témoin, sans vol20/régime. Il faudra vérifier les étapes10/11/12 et le watcher sur ces profils. Ne pas modifier manuellement le JSON de référence pour contourner ses empreintes.

## Reproduction historique

La comparaison2021–2026 utilisait six contextes annuels et des poids B de recherche figés. Un seul batch entraîné récemment n’est pas une reproduction automatique de ces six configurations.

| Année de test | Début d’apprentissage Oracle de référence | Fin |
| --- | --- | --- |
| 2021 | 2014-01-01 | 2020-12-31 |
| 2022 | 2015-01-01 | 2021-12-31 |
| 2023 | 2016-01-01 | 2022-12-31 |
| 2024 | 2017-01-01 | 2023-12-31 |
| 2025 | 2018-01-01 | 2024-12-31 |
| 2026 | 2019-01-01 | 2025-12-31 |

Pour un nouveau modèle destiné aux prochaines séances : utiliser seulement les données connues et les labels arrivés à maturité, puis vérifier la disponibilité des branches/folds à la date de prédiction. Aucun entraînement, lancement de prédiction ou ordre n’a été effectué lors de cette vérification.
