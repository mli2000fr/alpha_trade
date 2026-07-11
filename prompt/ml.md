# Plan d'action ML professionnel pour le swing trading

**Date de référence :** 2026-07-11  
**Statut :** plan prospectif, aucun sprint n'est considéré terminé sans ses critères de sortie  
**Périmètre :** `modelFactory/`, données PIT, entraînement, calibration, sélection du champion, prédiction, backtest, gouvernance et exploitation  
**Cible :** système ML ternaire long / flat / short adapté au swing trading US, validé hors échantillon et exploitable en paper puis en réel sous garde-fous

---

## 1. Objectif et principe directeur

L'objectif n'est pas de rendre le modèle « parfait » au sens d'une performance garantie, ce qui est impossible sur les marchés. L'objectif professionnel est de rendre le système :

1. temporellement correct et sans fuite de données ;
2. cohérent entre train, validation, backtest, paper et live ;
3. optimisé sur une stratégie tradable nette de coûts, pas seulement sur une classification ;
4. robuste aux changements de régime, d'univers et de liquidité ;
5. reproductible, observable, explicable et révocable ;
6. incapable de promouvoir automatiquement un modèle aux métriques invalides ou instables.

Le chemin critique est le suivant :

```text
Contrats et métriques fiables
    -> décision ternaire unique
    -> données et labels tradables PIT
    -> baselines et modèles robustes
    -> validation OOS financière
    -> parité backtest/paper/live
    -> shadow et paper trading
    -> déploiement progressif sous surveillance
```

Un gain d'AUC, de F1 ou de loss n'est jamais une preuve suffisante. La promotion doit être fondée sur le PnL net hors échantillon, sa stabilité, son drawdown, son turnover et sa capacité.

---

## 2. État initial et anomalies à traiter

| ID | Sévérité | Anomalie | Impact swing trading |
|---|---|---|---|
| ML-P0-01 | P0 | Métriques globales par symbole calculées avec des labels ternaires passés à un calcul binaire | AUC hors `[0,1]`, champion potentiellement sélectionné sur un score invalide |
| ML-P0-02 | P0 | Politique ternaire différente entre évaluation et inférence | Les métriques ne représentent pas les ordres réellement servis |
| ML-P0-03 | P0 | Calibration tabulaire appliquée à `p_long` mais ignorée par l'`argmax` ternaire | Décisions short/flat/long non calibrées |
| ML-P0-04 | P0 | Optimiseur de target ternaire compare long à flat et ignore short | Horizon et seuils sélectionnés sur une sémantique erronée |
| ML-P0-05 | P0 | Sélection du champion utilisant le test final | Contamination du holdout et surestimation de la généralisation |
| ML-P0-06 | P0 | Artefacts anciens potentiellement servis sans blocage dur | Modèle entraîné sur un régime obsolète utilisé en réel |
| ML-P1-01 | P1 | Collapse fréquent vers une classe, notamment long, et absence de prédiction flat | Turnover/exposition incontrôlés et faux sentiment de performance |
| ML-P1-02 | P1 | Target à horizon fixe fondée sur close-to-close brut | Décalage avec entrée J+1, stops, gaps, coûts et trajectoire intrahorizon |
| ML-P1-03 | P1 | Score métier non homogène et non net de coûts | Mauvais modèle ou mauvais seuil promu |
| ML-P1-04 | P1 | Contrat de disponibilité PIT incomplet pour sentiment, selector et macro | Risque de look-ahead lors de l'activation de ces features |
| ML-P1-05 | P1 | Ranks cross-sectionnels dépendants de l'univers disponible | Drift de features si univers train et predict diffèrent |
| ML-P1-06 | P1 | Validation insuffisante par régime, secteur, liquidité et direction | Alpha concentré et fragile |
| ML-P1-07 | P1 | Tests du prédicteur en échec et défauts code/tests désalignés | Régressions d'inférence non détectées avec confiance |
| ML-P2-01 | P2 | Poids ternaires codés en dur | Classes mal équilibrées selon symbole et régime |
| ML-P2-02 | P2 | LSTM par symbole sur peu d'observations et forte capacité | Risque élevé de surapprentissage |
| ML-P2-03 | P2 | Incertitude et abstention non modélisées | Trades pris lorsque le modèle ne sait pas |
| ML-P2-04 | P2 | Drift générique non relié au PnL et aux régimes | Alertes peu actionnables et retraining mal déclenché |

---

## 3. Règles globales de réalisation

### 3.1 Definition of Done commune

Un sprint n'est clos que si :

- tous ses critères d'acceptation sont satisfaits ;
- ses tests nouveaux et existants passent avec `--no-cov`, puis dans la suite globale avec le seuil de couverture ;
- aucun fichier de production modifié ne présente d'erreur de type ou de lint pertinente ;
- les artefacts produits portent version, fingerprint de données/features/config/code et bornes temporelles ;
- la documentation décrit le comportement réellement exécuté ;
- aucun seuil GO n'est contourné par un fallback silencieux.

### 3.2 Jeux de référence figés

Créer trois niveaux de données immuables :

1. **fixture synthétique** : quelques symboles, régimes et événements connus, pour les tests unitaires ;
2. **golden dataset PIT** : 20 à 50 symboles incluant survivants, delistings, splits, dividendes, earnings et trous de données ;
3. **benchmark institutionnel** : univers PIT complet, périodes 2018-2026, coûts et contraintes réalistes.

Les périodes de recherche, validation et test final doivent être figées avant les expériences. Le holdout final ne doit jamais servir à choisir modèle, features, target ou seuils.

### 3.3 Commandes de validation standard

```powershell
# Test ciblé sans faire échouer le run sur la couverture globale
python -m pytest tests/test_model_factory_target_optimization.py --no-cov -q

# Suite ML complète
$tests = Get-ChildItem tests/test_model_factory*.py | ForEach-Object { $_.FullName }
python -m pytest $tests tests/test_model_walk_forward.py tests/test_modelfactory_drift_monitor.py --no-cov -q

# Suite globale et couverture
python -m pytest

# Qualité statique ciblée
python -m ruff check modelFactory tests
python -m mypy modelFactory
```

---

## 4. Roadmap par sprints

## Sprint 0 — Figer la baseline et les contrats de décision

**Priorité :** P0, préalable à tous les autres sprints  
**Objectif :** rendre impossible toute comparaison mouvante et définir une seule sémantique long/flat/short.

### Tâches

1. Définir un `TernaryDecisionPolicy` partagé :
   - `long` si `p_long >= threshold_long` et marge de conviction suffisante ;
   - `short` si `p_short >= threshold_short` et marge suffisante ;
   - `flat` sinon ;
   - gestion explicite des égalités et probabilités non finies.
2. Définir le timing canonique : features à la clôture J, décision après disponibilité complète, entrée simulée à l'open J+1.
3. Figer un benchmark avant correction : métriques AAPL, SPY, secteurs, modèle global et 30 symboles représentatifs.
4. Versionner le contrat de prédiction, la convention des classes, les seuils et la convention de coûts.
5. Ajouter un mode `research_only` qui bloque toute promotion ou exécution pendant les sprints 0 à 7.

### Fichiers probables

- `modelFactory/evaluation.py`
- `modelFactory/predictor.py`
- `modelFactory/config.py`
- `core/ml_selection_contract.py`
- `backtesting/signal_replay.py`
- `doc/` et `README.md`

### Tests

- **Nouveau** `tests/test_ml_ternary_decision_policy.py::test_same_policy_is_used_by_evaluation_and_prediction`.
  - Given : trois matrices de probabilités couvrant long, short, flat et égalité.
  - When : évaluation et prédiction appliquent la policy.
  - Then : côtés et abstentions sont strictement identiques.
- **Nouveau** `tests/test_ml_timing_contract.py::test_eod_features_generate_next_session_entry`.
  - Oracle : aucune entrée n'utilise un prix antérieur à la disponibilité des features.
- **Non-régression** : tests predictor, evaluation, model walk-forward et sélection ML-first.

### Critères de sortie

- une seule fonction décide du side dans tous les chemins ;
- parité décisionnelle de 100 % sur la fixture déterministe ;
- baseline JSON immuable produite avec code/data/config fingerprints ;
- exécution réelle explicitement bloquée pour les modèles `research_only`.

### Gain attendu

Fiabilité du contrat ML : **4/10 -> 6/10**. Aucun gain de performance revendiqué à ce stade.

---

## Sprint 1 — Corriger métriques, calibration et sélection du champion

**Priorité :** P0  
**Dépendance :** Sprint 0  
**Objectif :** garantir que chaque score est mathématiquement valide et représente exactement la policy servie.

### Tâches

1. Corriger `_compute_by_symbol_metrics()` :
   - métriques one-vs-rest avec `label_long = target == 1` ;
   - métriques multiclasses avec targets shiftées ;
   - métriques financières par symbole avec la policy ternaire.
2. Corriger l'optimiseur de target pour traiter séparément `-1`, `0`, `1`.
3. Appliquer une calibration multiclasses aux modèles tabulaires et utiliser les probabilités calibrées pour décider.
4. Interdire la sélection du champion sur le test : sélection sur validation/walk-forward, test final en lecture seule.
5. Ajouter des invariants bloquants :
   - AUC dans `[0,1]` ;
   - probabilités finies, dans `[0,1]`, somme proche de 1 ;
   - aucun label inconnu ;
   - aucune métrique avec base rate négatif ;
   - aucune promotion avec `action_rate=0` ou collapse non justifié.
6. Invalider et reconstruire tous les artefacts dont la gouvernance a utilisé les anciennes métriques.

### Fichiers probables

- `modelFactory/global_model.py`
- `modelFactory/tabular_baseline.py`
- `modelFactory/target_optimization.py`
- `modelFactory/predictor.py`
- `modelFactory/champion_selection.py`
- `modelFactory/trainer.py`
- `modelFactory/db_registry.py`

### Tests

- `tests/test_model_factory_global_model.py::test_ternary_by_symbol_metrics_are_bounded_and_use_binary_long_labels`.
- `tests/test_model_factory_target_optimization.py::test_ternary_optimizer_compares_long_flat_and_short`.
- `tests/test_model_factory_predictor.py::test_tabular_ternary_prediction_uses_calibrated_probabilities`.
- `tests/test_model_factory_champion_selection.py::test_holdout_test_metrics_cannot_select_champion`.
- `tests/test_model_factory_champion_selection.py::test_invalid_auc_blocks_promotion`.
- `tests/test_model_factory_evaluation.py::test_runtime_and_backtest_policy_metrics_are_identical`.

### Matrice anomalies -> tests

| Anomalie | Tests obligatoires |
|---|---|
| ML-P0-01 | métriques bornées + labels long binarisés |
| ML-P0-02 | parité policy évaluation/prédiction |
| ML-P0-03 | calibration multiclasses utilisée à l'inférence |
| ML-P0-04 | optimisation ternaire avec trois classes |
| ML-P0-05 | holdout interdit à la sélection |

### Critères de sortie

- zéro AUC hors `[0,1]` sur tous les artefacts reconstruits ;
- somme des probabilités dans `1 +/- 1e-6` ;
- 100 % de parité side entre métriques, backtest et inférence ;
- aucune lecture de `test_metrics` dans le score de sélection ;
- tous les tests predictor actuellement en échec sont corrigés ou requalifiés avec justification documentée.

### Gain attendu

Gouvernance et métriques : **3/10 -> 8/10**.

---

## Sprint 2 — Garantir les données point-in-time et l'univers historique

**Priorité :** P0/P1  
**Dépendance :** Sprint 1  
**Objectif :** éliminer look-ahead, survivorship bias et dérive silencieuse des features.

### Tâches

1. Créer un registre de disponibilité par source : `event_time`, `available_at`, timezone, source, révision et date d'ingestion.
2. Imposer `available_at <= decision_cutoff` pour sentiment, selector, macro, earnings et corporate actions.
3. Utiliser exclusivement l'univers tradable PIT historique par date, avec delistings et changements de ticker.
4. Garantir la convention OHLCV ajustée : prix ajustés pour features/targets, prix exécutables non ajustés pour fills et coûts.
5. Rendre les ranks cross-sectionnels reproductibles à partir du même snapshot d'univers ; persister universe fingerprint et taille par date.
6. Remplacer les défauts macro `0.0` par état `missing` explicite, indicateur de fraîcheur et policy fail-closed configurable.
7. Produire un rapport quotidien de qualité : couverture, fraîcheur, trous, duplicates, corporate actions, univers et features non finies.

### Fichiers probables

- `modelFactory/data_loader.py`
- `modelFactory/features.py`
- `modelFactory/cross_sectional.py`
- `common/tradable_universe.py`
- `database/`
- `dataIntegrityEngine/`
- migration Alembic si `available_at` n'existe pas

### Tests

- **PIT** `tests/test_model_factory_feature_availability.py::test_feature_available_after_cutoff_is_excluded`.
- **Survivorship** `tests/test_model_factory_historical_universe.py::test_delisted_symbol_remains_in_historical_training_universe`.
- **Corporate actions** `tests/test_model_factory_features.py::test_split_adjustment_does_not_change_executable_fill_price`.
- **Cross-sectionnel** `tests/test_model_factory_cross_sectional.py::test_rank_uses_persisted_universe_snapshot`.
- **Data quality** `tests/test_model_factory_data_quality.py::test_stale_macro_blocks_or_marks_prediction`.
- **SQL** : contraintes d'unicité et résolution as-of sans ligne future.

### Critères de sortie

- zéro feature avec `available_at > decision_cutoff` sur le golden dataset ;
- univers historique comprenant survivants et non-survivants ;
- parité des ranks reconstruits à `1e-12` sur snapshot identique ;
- 100 % des prédictions portent data cutoff, universe fingerprint et freshness status ;
- aucune valeur macro artificielle `0.0` indistinguable d'une vraie observation.

### Gain attendu

Qualité/PIT : **6/10 -> 9/10**.

---

## Sprint 3 — Construire une target réellement tradable

**Priorité :** P1  
**Dépendance :** Sprint 2  
**Objectif :** aligner le label sur le trade exécuté et son risque intrahorizon.

### Tâches

1. Implémenter un label triple-barrier :
   - entrée au prochain open tradable ;
   - stop et take-profit exprimés en ATR/volatilité ;
   - horizon maximum en sessions ;
   - ordre du premier barrier touché déterminé avec convention intraday explicite.
2. Déduire spread, commissions, slippage et impact estimé à l'entrée/sortie.
3. Gérer les gaps : fill au premier prix exécutable, jamais au niveau théorique du stop.
4. Produire labels long, flat, short et retour net, durée, MAE, MFE, raison de sortie.
5. Optimiser les paramètres de target uniquement dans les folds train ; jamais globalement avant split.
6. Comparer target fixe actuelle, triple-barrier et target de ranking cross-sectionnel.
7. Utiliser block bootstrap pour tenir compte du chevauchement des labels et estimer les intervalles de confiance.

### Fichiers probables

- nouveau `modelFactory/labeling.py`
- `modelFactory/features.py`
- `modelFactory/target_optimization.py`
- `backtesting/microstructure.py`
- `backtesting/simulator.py`
- `backtesting/trading_constraints.py`

### Tests

- `tests/test_model_factory_labeling.py::test_first_barrier_determines_label`.
- `tests/test_model_factory_labeling.py::test_gap_through_stop_uses_executable_open`.
- `tests/test_model_factory_labeling.py::test_costs_can_turn_gross_win_into_flat_or_loss`.
- `tests/test_model_factory_target_optimization.py::test_target_parameters_fit_on_train_fold_only`.
- `tests/test_model_factory_labeling.py::test_no_label_reads_beyond_fold_boundary`.
- Property test : aucune sortie antérieure à l'entrée, aucun rendement non fini, invariant long/short symétrique sur série inversée.

### Critères de sortie

- parité label/backtest de 100 % sur les scénarios déterministes ;
- coûts identiques à ceux du moteur de backtest ;
- aucune target traversant une frontière de fold ;
- paramètres choisis uniquement sur train et journalisés ;
- rapport d'ablation montrant la distribution, le turnover et le PnL net de chaque target.

### Gain attendu

Adéquation swing : **5/10 -> 8/10**.

---

## Sprint 4 — Refaire le benchmark modèles et maîtriser le collapse

**Priorité :** P1  
**Dépendance :** Sprint 3  
**Objectif :** sélectionner l'architecture la plus simple qui généralise, plutôt que privilégier le LSTM.

### Tâches

1. Ajouter des baselines obligatoires :
   - always-flat, always-long/short ;
   - momentum et mean-reversion simples ;
   - régression logistique réguliarisée ;
   - LightGBM et CatBoost globaux.
2. Comparer global, sectoriel et par symbole avec le même protocole et le même budget de tuning.
3. Calculer les poids de classes sur le train uniquement ; tester balanced CE, focal loss et sampling pondéré.
4. Réduire et régulariser le LSTM ; tester si la séquence apporte un gain au-delà des features tabulaires laggées.
5. Ajouter monotonic constraints ou règles de plausibilité lorsqu'elles sont justifiées.
6. Rejeter automatiquement tout modèle :
   - inférieur aux baselines ;
   - présentant une classe prédite < 1 % alors qu'elle est matériellement présente ;
   - instable entre seeds ;
   - trop coûteux pour son gain marginal.
7. Journaliser temps, mémoire, latence et empreinte artefact.

### Fichiers probables

- `modelFactory/model.py`
- `modelFactory/global_model.py`
- `modelFactory/lightgbm_baseline.py`
- `modelFactory/catboost_baseline.py`
- `modelFactory/tabular_baseline.py`
- nouveau `modelFactory/model_benchmark.py`

### Tests

- `tests/test_model_factory_model.py::test_class_weights_are_fitted_from_train_only`.
- `tests/test_model_factory_champion_selection.py::test_collapsed_model_is_ineligible`.
- `tests/test_model_factory_model_benchmark.py::test_challengers_share_identical_folds_and_costs`.
- `tests/test_model_factory_reproducibility.py::test_same_seed_reproduces_predictions_and_metrics`.
- `tests/test_model_factory_reproducibility.py::test_seed_stability_is_reported_before_promotion`.

### Critères de sortie

- chaque candidat comparé sur folds, target, coûts et policy identiques ;
- aucun champion en collapse sur un fold critique ;
- amélioration statistiquement crédible face à CatBoost/LightGBM ou retrait du LSTM ;
- variation de score entre seeds sous un seuil documenté ;
- latence compatible avec la fenêtre EOD.

### Gain attendu

Modélisation : **5/10 -> 8/10**, avec réduction probable de complexité.

---

## Sprint 5 — Validation walk-forward financière et par régimes

**Priorité :** P1  
**Dépendance :** Sprint 4  
**Objectif :** remplacer le verdict classification par un verdict portefeuille OOS net de coûts.

### Tâches

1. Utiliser un nested walk-forward : tuning interne, sélection sur validation, test externe intact.
2. Ajouter purge par horizon et embargo adapté aux labels chevauchants.
3. Évaluer chaque fold dans `BacktestEngine` avec sizing, contraintes, stops, slippage et capacité réels.
4. Rapporter long, short et combiné :
   - CAGR, Sharpe, Sortino, Calmar ;
   - max drawdown et recovery ;
   - hit rate, payoff, profit factor ;
   - turnover, exposition, capacité et coûts ;
   - MAE/MFE et durée de détention ;
   - IC/rank IC et calibration.
5. Segmenter par bull/bear, volatilité, taux, secteur, market cap, ADV et earnings.
6. Ajouter intervalles de confiance block-bootstrap, Deflated Sharpe Ratio et correction du multiple testing.
7. Produire un score de promotion stable et dimensionnellement cohérent.

### Fichiers probables

- `modelFactory/evaluation.py`
- `modelFactory/trainer.py`
- `backtesting/walk_forward.py`
- `backtesting/statistical_validation.py`
- `backtesting/report.py`
- `validate_score_predictiveness.py`

### Tests

- `tests/test_model_walk_forward.py::test_nested_walk_forward_never_uses_outer_test_for_tuning`.
- `tests/test_model_walk_forward.py::test_purge_and_embargo_remove_overlapping_labels`.
- `tests/test_model_factory_evaluation.py::test_financial_metrics_are_net_of_costs`.
- `tests/test_model_factory_evaluation.py::test_long_short_and_combined_metrics_reconcile`.
- `tests/test_model_factory_statistical_validation.py::test_block_bootstrap_is_deterministic_with_seed`.
- Parité : mêmes signaux et PnL entre replay ML et `BacktestEngine` sur fixture.

### Seuils de recherche minimaux

Ces seuils sont des gates initiaux à recalibrer selon la capacité et le mandat :

| Indicateur OOS agrégé | Seuil candidat |
|---|---:|
| Folds OOS positifs nets de coûts | >= 70 % |
| Sharpe OOS médian | >= 1,0 |
| Sharpe OOS au 25e percentile | > 0 |
| Max drawdown | <= budget de risque stratégie |
| Profit factor | >= 1,20 |
| Nombre de trades indépendants | >= 200 globalement et >= 30 par régime critique |
| Coûts / alpha brut | <= 35 % |
| Performance sans les 10 meilleurs trades | encore positive |
| Performance long et short | aucune jambe structurellement non validée si elle est activée |

### Critères de sortie

- holdout externe jamais utilisé pour tuning ou sélection ;
- rapport par fold et régime complet ;
- comparaison à buy-and-hold, règles simples et modèle précédent ;
- décision GO/NO-GO automatique, explicable et impossible à contourner silencieusement.

### Gain attendu

Validation quantitative : **4/10 -> 9/10**.

---

## Sprint 6 — Incertitude, abstention, sizing et portefeuille

**Priorité :** P1/P2  
**Dépendance :** Sprint 5  
**Objectif :** convertir la prédiction en décision risquée disciplinée, avec droit explicite de ne pas trader.

### Tâches

1. Calibrer les trois classes et mesurer ECE/NLL/Brier multiclasses par régime.
2. Ajouter abstention fondée sur confiance, entropie, marge top-2, qualité de données et distance au domaine train.
3. Convertir probabilité et rendement conditionnel en expected edge net :

   `edge_net = expected_return - spread - slippage - commission - impact - borrow_cost`.

4. Interdire un trade si `edge_net <= safety_margin`.
5. Calibrer sizing avec volatilité, liquidité, corrélation, concentration et Kelly fractionné plafonné.
6. Gérer séparément short availability, borrow fee et squeeze risk.
7. Optimiser les seuils au niveau portefeuille, pas symbole par symbole sans contrainte commune.

### Fichiers probables

- `modelFactory/calibration.py`
- `modelFactory/evaluation.py`
- `risk_management/ml_gate.py`
- `risk_management/conviction.py`
- `risk_management/position_sizer.py`
- `risk_management/portfolio_builder.py`
- `execution_engine/`

### Tests

- `tests/test_model_factory_calibration.py::test_multiclass_calibration_improves_or_preserves_holdout_nll`.
- `tests/test_risk_ml_weight_gate.py::test_uncertain_prediction_abstains`.
- `tests/test_risk_ml_weight_gate.py::test_negative_net_edge_is_rejected`.
- `tests/test_position_sizer.py::test_size_decreases_with_volatility_and_cost`.
- `tests/test_short_execution_constraints.py::test_unavailable_or_expensive_borrow_blocks_short`.
- Property test : augmentation des coûts ne peut augmenter le sizing.

### Critères de sortie

- calibration testée hors de son fold de fit ;
- courbes performance/couverture produites ;
- aucun trade sous marge de sécurité nette ;
- limites portefeuille respectées sur 100 % des scénarios stressés ;
- politique short validée séparément.

### Gain attendu

Décision et risk-adjusted performance : **6/10 -> 9/10**.

---

## Sprint 7 — Parité backtest, paper et live

**Priorité :** P0 avant paper/live  
**Dépendance :** Sprint 6  
**Objectif :** garantir que ce qui a été validé est exactement ce qui sera exécuté.

### Tâches

1. Utiliser le même package de features, policy, modèle, seuils et coûts dans replay, paper et live.
2. Persister pour chaque décision : inputs, timestamps, universe/model/config fingerprints, probabilités, policy version, vetos, sizing et prix attendu.
3. Rejouer une journée live à l'identique depuis l'audit log.
4. Ajouter idempotence et exactly-once logique pour les prédictions persistées.
5. Bloquer l'inférence si artefact, scaler, calibrateur, features ou schéma sont incompatibles.
6. Comparer quotidiennement expected fills et realized fills.
7. Éliminer les fallbacks neutres silencieux : chaque fallback doit produire état dégradé et alerte.

### Fichiers probables

- `modelFactory/predictor.py`
- `modelFactory/db_registry.py`
- `backtesting/fidelity.py`
- `backtesting/signal_replay.py`
- `ihm/services/pipeline_runner.py`
- `execution_engine/`
- `lineage/`

### Tests

- `tests/test_ml_backtest_live_parity.py::test_identical_snapshot_produces_identical_features_probabilities_and_side`.
- `tests/test_model_factory_predictor.py::test_prediction_is_idempotent_for_model_symbol_date`.
- `tests/test_model_predictions_schema.py::test_prediction_lineage_is_complete`.
- `tests/test_execution_ml_parity.py::test_expected_and_paper_order_share_side_and_size`.
- `tests/test_ml_artifacts_backup.py` et tests de corruption/fallback.

### Critères de sortie

- 100 % de parité features/probabilités/side sur golden replay ;
- écarts numériques bornés et documentés selon backend ;
- audit lineage complet pour 100 % des ordres ;
- aucune exécution après échec d'intégrité ou staleness ;
- suite predictor entièrement verte.

### Gain attendu

Parité opérationnelle : **5/10 -> 9/10**.

---

## Sprint 8 — MLOps, drift, fraîcheur et rollback automatique

**Priorité :** P1 avant production  
**Dépendance :** Sprint 7  
**Objectif :** exploiter le modèle comme un système de production révocable, pas comme un fichier statique.

### Tâches

1. Créer un registry avec états `candidate`, `shadow`, `paper`, `champion`, `degraded`, `retired`.
2. Définir fraîcheur maximale des données, features, modèle et calibration ; bloquer au-delà.
3. Surveiller :
   - PSI/KS et missingness des features ;
   - drift des probabilités, sides, couverture et calibration ;
   - performance réalisée par cohorte et régime ;
   - slippage, rejets, latence, coût et exposition ;
   - écart attendu/réalisé.
4. Déclencher rollback/circuit breaker sur intégrité, staleness, drawdown, calibration ou dérive sévère.
5. Définir retraining périodique et événementiel, avec comparaison champion/challenger complète.
6. Canary release sur une fraction de l'univers/capital.
7. Tester sauvegarde, restauration, disaster recovery et reproductibilité d'un run.

### Fichiers probables

- `modelFactory/drift_monitor.py`
- `modelFactory/drift_policy.py`
- `modelFactory/auto_rollback.py`
- `modelFactory/runtime_status.py`
- `modelFactory/db_registry.py`
- `service/alerting.py`
- `ihm/pages/` ML

### Tests

- `tests/test_ml_drift_policy_gate.py::test_severe_drift_disables_new_entries`.
- `tests/test_ml_auto_rollback_champion.py::test_degraded_champion_rolls_back_atomically`.
- `tests/test_model_governance_drift_gate.py::test_stale_model_cannot_be_served`.
- `tests/test_ml_artifacts_backup.py::test_restore_reproduces_prediction`.
- E2E IHM : état, cause, modèle précédent et action opérateur visibles.

### Critères de sortie

- modèle obsolète ou incompatible impossible à servir ;
- rollback testé en moins de 5 minutes, sans nouvel ordre pendant la transition ;
- alertes actionnables avec cause, scope, sévérité et run IDs ;
- dashboard temps réel et rapport quotidien ;
- restauration vérifiée sur environnement propre.

### Gain attendu

MLOps et résilience : **6/10 -> 9/10**.

---

## Sprint 9 — Shadow mode et paper trading professionnel

**Priorité :** P0 avant capital réel  
**Dépendance :** Sprints 0 à 8  
**Objectif :** valider la chaîne sur données réellement arrivées, sans risque financier initial.

### Phase A — Shadow, minimum 4 semaines

1. Produire les décisions sans ordre.
2. Vérifier disponibilité réelle des features au cutoff.
3. Mesurer latence, couverture, staleness et différences replay/live.
4. Simuler fills à partir des quotes réellement observées.
5. Comparer chaque soir prediction snapshot, replay et backtest attendu.

### Phase B — Paper, minimum 8 à 12 semaines

1. Envoyer les ordres au broker paper avec contraintes réelles.
2. Mesurer fills, partial fills, slippage, rejets, borrow et latence.
3. Vérifier PnL par cohorte de prédiction et calibration réalisée.
4. Exécuter incidents simulés : données absentes, DB indisponible, artefact corrompu, modèle stale, broker timeout.
5. Geler toute modification de modèle pendant une fenêtre d'évaluation minimale, sauf rollback de sécurité.

### Tests et contrôles

- E2E pipeline quotidien complet sur environnement paper.
- Replay nocturne égal à la décision intraday/EOD auditée.
- Chaos tests des dépendances critiques.
- Rapport hebdomadaire automatique shadow/paper.
- Revue humaine des 20 plus grands gains, pertes et abstentions.

### Gates GO vers capital réel

| Contrôle | Seuil GO initial |
|---|---:|
| Erreur de parité side backtest/paper | 0 |
| Décisions avec lineage incomplet | 0 |
| Ordres après gate critique | 0 |
| Données futures détectées | 0 |
| Slippage réalisé / hypothèse | <= 1,25x en médiane |
| Performance paper nette | positive avec intervalle et taille d'échantillon suffisants |
| Drawdown paper | sous budget |
| Incidents non expliqués | 0 critique, 0 majeur ouvert |
| Rollback drill | réussi |

### Critères de sortie

- comité GO/NO-GO documenté ;
- au moins un cycle de retraining/challenger observé sans incident ;
- hypothèses de coûts recalibrées avec paper fills ;
- aucune divergence non expliquée entre research, replay et paper.

### Gain attendu

Confiance opérationnelle : **5/10 -> 9/10**.

---

## Sprint 10 — Go-live progressif et amélioration continue

**Priorité :** P0 production  
**Dépendance :** validation formelle du Sprint 9  
**Objectif :** engager du capital de manière graduelle, réversible et mesurable.

### Tâches

1. Démarrer à 5 % du budget de risque stratégie, univers liquide uniquement.
2. Monter par paliers `5 % -> 10 % -> 25 % -> 50 % -> 100 %`, jamais automatiquement.
3. Exiger une fenêtre minimale et une revue à chaque palier.
4. Définir stop opérationnel, stop drawdown, limite de pertes journalières et kill switch manuel testé.
5. Conserver champion précédent et retour arrière atomique.
6. Exécuter une revue mensuelle : attribution, régimes, coûts, drift, capacité et erreurs.
7. Réaliser une revue indépendante trimestrielle des hypothèses et du multiple testing.
8. Maintenir un journal des changements de modèle, données, features et policy.

### Gates de montée en charge

- aucun incident critique depuis le palier précédent ;
- performance réalisée compatible avec l'intervalle attendu ;
- drawdown et slippage sous limites ;
- calibration et couverture stables ;
- aucune concentration imprévue par secteur, facteur ou régime ;
- capacité et impact de marché compatibles avec le palier suivant.

### Tests permanents

- smoke test avant chaque session ;
- test quotidien de fraîcheur et intégrité ;
- reconciliation ordres/fills/positions/PnL ;
- rollback drill mensuel ;
- backtest-live parity quotidien ;
- restauration complète trimestrielle.

### Critères de sortie

Ce sprint ne se « termine » pas définitivement. Il devient le processus d'exploitation permanent. Le passage à 100 % du budget n'est autorisé qu'après plusieurs périodes et régimes observés, sans dégradation des gates.

### Gain attendu

Niveau professionnel exploitable : **9/10**, sous réserve de discipline opérationnelle continue.

---

## 5. Matrice de dépendances

| Sprint | Dépend de | Peut avancer en parallèle avec |
|---|---|---|
| 0 | aucun | préparation fixtures |
| 1 | 0 | aucun, chemin critique |
| 2 | 1 | préparation labeling |
| 3 | 2 | étude coûts/microstructure |
| 4 | 3 | optimisation infrastructure |
| 5 | 4 | reporting IHM |
| 6 | 5 | tests risk |
| 7 | 6 | lineage/observabilité |
| 8 | 7 | documentation opérateur |
| 9 | 0 à 8 | aucun changement majeur non contrôlé |
| 10 | 9 | recherche challenger isolée |

---

## 6. Matrice de promotion d'un modèle

Un modèle n'est éligible que si tous les gates obligatoires passent.

| Domaine | Gate bloquant |
|---|---|
| Intégrité | artefacts, scaler, calibrateur, schéma et fingerprints valides |
| Fraîcheur | données et modèle sous âge maximal autorisé |
| PIT | aucune observation disponible après cutoff |
| Métriques | valeurs finies, bornées et cohérentes |
| Policy | parité évaluation/backtest/predict/paper à 100 % |
| Baseline | gain net et robuste face aux stratégies simples |
| Stabilité | plusieurs seeds, folds et régimes sans collapse |
| Risque | drawdown, exposition, concentration et turnover sous limites |
| Coûts | alpha net positif après coûts stressés |
| Statistique | intervalle de confiance, multiple testing et taille d'échantillon acceptables |
| Opérations | shadow/paper, rollback et incident drills validés |
| Gouvernance | approbation et audit trail complets |

Un seul gate bloquant en échec donne `NO-GO`. Un fallback technique ne transforme jamais un `NO-GO` en `GO`.

---

## 7. Ordre d'impact recommandé

### Quick wins

1. corriger labels binaires des métriques globales par symbole ;
2. utiliser une policy ternaire partagée ;
3. retirer le test final de la sélection ;
4. bloquer AUC invalides, collapse et artefacts stale ;
5. réaligner les tests sur `forecast_horizon=10` ou restaurer le contrat attendu.

### Refactors structurants

1. labeling triple-barrier net de coûts ;
2. nested walk-forward financier ;
3. modèle global et benchmark multi-architectures ;
4. registre de disponibilité PIT ;
5. policy et lineage uniques de bout en bout.

### Travaux de validation longs mais indispensables

1. benchmarks multi-régimes ;
2. shadow mode ;
3. paper trading 8 à 12 semaines ;
4. montée progressive du capital.

---

## 8. À partir de quel sprint le système devient utilisable

- **Après Sprint 1 :** métriques fiables, mais recherche uniquement.
- **Après Sprint 3 :** labels adaptés au swing, mais performance encore non démontrée.
- **Après Sprint 5 :** candidat quantitativement crédible si tous les gates passent, toujours sans capital réel.
- **Après Sprint 7 :** chaîne techniquement cohérente pour shadow/paper.
- **Après Sprint 9 :** suffisamment robuste pour envisager un swing trading réel discipliné à capital très réduit, uniquement avec GO formel.
- **Sprint 10 :** exploitation professionnelle progressive.

Le système ne doit donc pas engager de capital réel avant la clôture du Sprint 9.

---

## 9. Ce qu'il restera pour un vrai 10/10 pro-grade

Même après ce plan, un « 10/10 » absolu n'existe pas. Le niveau institutionnel exige un processus continu :

1. données alternatives réellement point-in-time avec licences et audits fournisseurs ;
2. estimations de capacité et impact calibrées sur fills réels ;
3. revue indépendante du modèle et séparation recherche/validation/production ;
4. red-team des fuites temporelles et des hypothèses de backtest ;
5. stress tests de crises inédites et dépendances corrélées ;
6. surveillance permanente de l'alpha decay ;
7. gouvernance des changements, droits d'accès, approbations et journal immuable ;
8. plan de continuité broker, données, DB, calcul et opérateur ;
9. conformité, fiscalité, borrow et règles de marché adaptées au compte réel ;
10. capacité à retirer définitivement un modèle dont l'avantage disparaît.

La réussite se mesure moins par la complexité du modèle que par l'absence de fuite, la fidélité de l'exécution, la stabilité nette de coûts et la vitesse de retrait lorsqu'une hypothèse cesse d'être vraie.

---

## 10. Checklist de pilotage

Pour chaque sprint :

- [ ] owner nommé ;
- [ ] dates et dépendances confirmées ;
- [ ] anomalies reliées aux tâches ;
- [ ] tests écrits avant clôture ;
- [ ] artefacts de validation archivés ;
- [ ] documentation mise à jour ;
- [ ] risques résiduels acceptés explicitement ;
- [ ] décision GO/NO-GO signée ;
- [ ] rollback défini et testé ;
- [ ] aucun résultat du holdout utilisé pour améliorer le candidat évalué.
