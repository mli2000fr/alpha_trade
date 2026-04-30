# Plan Phase 4 — ML & signaux

> Source : `prompt/refactor/plan.md` §Phase 4 (lignes 167-188), `prompt/refactor/audit_event_sentiment.md`, `prompt/refactor/audit_modelFactory.md`.
> Périmètre : `event_sentiment/` (4.1) puis `modelFactory/` (4.2).
> Conventions (rappel `plan.md` §Conventions) : 1 PR/commit par sous-phase, `pytest -q --no-cov` vert avant push, doc `doc/<module>.md` mise à jour dans la même sous-phase, audit coché en fin de sous-phase.

---

## 1. Inventaire des fichiers concernés

### 1.1 `event_sentiment/`

| Fichier | Rôle |
|---|---|
| `__init__.py`, `__main__.py` | Bootstrap module + entrée `python -m event_sentiment`. |
| `cli.py` | CLI principal (sous-commandes ingestion/scoring/aggregation). |
| `config.py` | `EventSentimentConfig` figée : `source_name="alpaca_news"`, FinBERT params (`finbert_model_name="ProsusAI/finbert"`, `finbert_model_version="finbert_v1"`, `finbert_batch_size=16`, `finbert_max_length=256`), fenêtres, backfill. |
| `models.py` | Dataclasses : `NormalizedNewsArticle`, `SentimentRecord` (déjà `model_name` + `model_version` + `text_hash`), `MacroImpactRecord`. |
| `mapping.py` | Normalisation tickers/secteurs. |
| `trading_calendar.py` | `TradingCalendarAligner` (alignement `published_at` → `effective_trade_date`). |
| `ingestion.py` | `NewsIngestionService` (pagination Alpaca News, dédup, upsert). |
| `scoring.py` | `FinBERTSentimentService` : `from_pretrained(model_name)` **sans `revision=`**, batch tokenisation, fallback CUDA→CPU. **Pas de fingerprint persisté**. |
| `macro_rules.py` | `MacroRuleEngine` (règles macro hard-codées). |
| `aggregation.py` | `build_ticker_daily_features` / `build_sector_daily_features`. |
| `db_io.py` | `EventSentimentRepository` (tous les upserts). |
| `pipeline.py` | `EventSentimentPipeline.run` orchestration ingestion→FinBERT→macro→aggregation. |
| `event_sentiment_pipeline.py` | Wrapper top-level (entrée IHM). |
| `sentiment_pipeline.py` | Variante de wrapper. |
| `history_backfill.py` | Backfill par tranches. |
| `importe_news.py` | Script ad-hoc IHM. |
| `signal_aggregator.py` (1341 LOC) | `SentimentBoostConfig` (poids 0.75/0.15/0.10, `time_decay_half_life_days=2.0`, horizons multi 1/3/5/10/20j) + `SentimentSignalAggregator.merge` + `save_to_db` (UPDATE `stock_scores`) + CLI. **Ne consomme PAS `core/conviction.py`** : implémente sa propre fusion ternaire `quant + sentiment_ticker + macro_sector`. |

### 1.2 `modelFactory/`

| Fichier | Rôle |
|---|---|
| `__init__.py`, `__main__.py` | Bootstrap. |
| `cli.py` | `build_arg_parser` + dispatch `--mode train|predict`. **`--walkforward` opt-in (default False)**. Pas de `--champion-min-runs`, pas de `--ml-mode`. |
| `config.py` | Dataclasses : `DataConfig`, `ModelConfig`, `CalibrationConfig`, `WalkForwardConfig` (default `enabled=False`), `BaselineConfig`, `GlobalModelConfig`, `TargetOptimizationConfig`, `ThresholdOptimizationConfig`, `ChampionSelectionConfig` (default `enabled=False`, **pas de min_runs/min_days**), `TrainingConfig`. |
| `run_train.py`, `run_predict.py` | Lanceurs wrappers. |
| `orchestrator.py` | `run_training_batch` ProcessPool, post-process global. |
| `trainer.py` (851 LOC) | `train_symbol` monolithique : ~17 étapes. **Persiste `scaler.pkl` + `calibrator.pkl` via `pickle`**. Écrit `config.json` + `metrics.json`. |
| `model.py` | `LSTMAttentionModule` Lightning. |
| `dataset.py`, `data_loader.py` | `SymbolDataModule`, `FeatureScaler` (state_dict pickled). |
| `features.py`, `cross_sectional.py` | `get_feature_columns(...)`. **Aucun fingerprint SHA256**. |
| `tabular_baseline.py` | `run_tabular_baseline` : **`pickle.dump(model)` ligne 209** + `pickle.dump(calibrator.state_dict())` ligne 214. Sortie `{model_name}_model.pkl`. |
| `lightgbm_baseline.py`, `catboost_baseline.py` | Wrappers fins sur `tabular_baseline.run_tabular_baseline`. |
| `global_model.py` | Modèle global multi-symboles, **utilise aussi `pickle`**. |
| `champion_selection.py` | `select_champion`, `build_challenger_ranking`, `evaluate_selection_eligibility`. **Pas de notion de quarantaine.** |
| `calibration.py` | `PlattCalibrator`. |
| `evaluation.py` | `compute_threshold_metrics`, `optimize_decision_threshold`. |
| `target_optimization.py` | Recherche `(horizon, up, down)`. |
| `predictor.py` | `predict_symbol` + `predict_batch` : **recharge artefacts à chaque appel** via `pickle.load` + `LSTMAttentionModule.load_from_checkpoint`. **Pas de cache**. |
| `db_registry.py` | `model_training_run`, `model_metrics`, `model_governance`, `model_predictions`. **`insert_metrics` ne stocke que loss/DA/precision/recall/auc** (pas de BLOB `metrics.json` complet). |

---

## 2. Consommateurs externes (impact rétrocompat)

### 2.1 `event_sentiment/`
- **`event_sentiment.signal_aggregator`** :
  - `tests/test_event_sentiment_run_summaries.py` (monkey-patch `SentimentSignalAggregator`, `RUN_SUMMARY_PREFIX`, `main`).
  - `tests/test_ihm_pipeline_runner.py` (build_pipeline_command "signal_aggregator" → CLI `python -m event_sentiment.signal_aggregator`).
  - **IHM** : build via `ihm.pipeline_runner.build_pipeline_command`.
  - **Aucun import direct** ailleurs : isolation correcte ; **préserver la signature CLI exacte**.
- **`event_sentiment.scoring.FinBERTSentimentService`** : `event_sentiment/pipeline.py` + tests `test_finbert_preprocessor.py`, `test_event_pipeline_defaults.py`, `test_event_pipeline_rerun.py`.
- **`event_sentiment.config.EventSentimentConfig`** : 6+ tests + `pipeline.py` + `history_backfill.py`.
- **`event_sentiment.db_io.EventSentimentRepository`** : `pipeline.py`, `cli.py`, `event_sentiment_pipeline.py`, `history_backfill.py`, `importe_news.py`, `tests/test_event_repository_db_io.py`.

### 2.2 `modelFactory/`
- **`modelFactory.predictor.predict_symbol` / `predict_batch`** : `cli.py` + `tests/test_model_factory_predictor.py` + consommateurs `risk_management/` & `selector/` (à confirmer).
- **`modelFactory.trainer.train_symbol`** : `orchestrator._train_worker` + `tests/test_model_factory_trainer.py`.
- **`modelFactory.cli.main`** : `run_train.py`, `run_predict.py`, IHM (`tests/test_ihm_pipeline_runner.py`).
- **`modelFactory.config.*Config`** : 5+ tests instancient directement.
- **`modelFactory.tabular_baseline.run_tabular_baseline`** : `lightgbm_baseline.py`, `catboost_baseline.py`, `tests/test_model_factory_lightgbm_baseline.py`.
- **`modelFactory.db_registry.*`** : `trainer.py`, `orchestrator.py`, `predictor.py`, `tests/test_model_factory_db_registry.py`.
- **Artefacts disque** existants `artifacts/models/<symbol>/{best.ckpt, scaler.pkl, calibrator.pkl, lightgbm_model.pkl, catboost_model.pkl, config.json, metrics.json}` : toute migration **doit conserver une lecture rétrocompat** des `.pkl` existants.

---

## 3. Sous-phases atomiques

> Numérotation `4.1.a … 4.1.c` (event_sentiment), `4.2.a … 4.2.h` (modelFactory). Ordre = ordre d'exécution recommandé.

### 4.1.a — Étendre `core/conviction.py` à la fusion ternaire (quant + sentiment + macro)
- **Objectif** : préparer l'API centralisée que `signal_aggregator` consommera, sans modifier `signal_aggregator` (zéro effet runtime).
- **Fichiers** : `core/conviction.py` — ajouter `SentimentFusionWeights` + `fuse_sentiment(*, quant_score, sentiment_signal_norm, macro_signal_norm, weights, signal_active)` (formule lignes 926-944 de `signal_aggregator.py` ; composante neutre 0.5 si `signal_active=False` ; clip [0,1]).
- **Tests** : `tests/test_core_conviction.py` — `test_fuse_sentiment_matches_legacy_formula` (5 cas), `test_sentiment_fusion_weights_validates_sum`, `test_sentiment_fusion_weights_rejects_negatives`.
- **Doc** : `doc/core_common.md` — section "fusion sentiment ternaire".
- **Done** : `pytest tests/test_core_conviction.py` vert ; aucun autre fichier touché.
- **Dépendances** : aucune. Bloque 4.1.b.

### 4.1.b — Migrer `signal_aggregator` vers `core/conviction.fuse_sentiment`
- **Objectif** : éliminer la duplication de la formule de fusion.
- **Fichiers** : `event_sentiment/signal_aggregator.py` — importer `core.conviction` ; `SentimentSignalAggregator.merge` (lignes 926-944) délègue ; `SentimentBoostConfig` gagne `to_fusion_weights() -> SentimentFusionWeights` ; **conserver les colonnes intermédiaires** `quant_component`, `company_idio_component`, `macro_regime_component`, `final_score_sentiment` (consommées par IHM/`save_to_db`).
- **Tests** : `tests/test_signal_aggregator.py` — `test_merge_uses_core_conviction_fusion` (monkey-patch `core.conviction.fuse_sentiment`). `tests/test_event_sentiment_run_summaries.py` doit rester vert.
- **Doc** : `doc/event_sentiment.md` — section "fusion sentiment" pointe vers `core/conviction.py`.
- **Done** : tests verts ; valeurs `final_score_sentiment` strictement inchangées (gold fixture).
- **Dépendances** : 4.1.a.

### 4.1.c — Versionner FinBERT (`model_fingerprint` + `revision=` épinglé)
- **Objectif** : tracer le SHA exact du checkpoint FinBERT consommé, le persister en DB, l'inclure dans `run_summary`.
- **Fichiers** :
  - `event_sentiment/config.py` : `finbert_model_revision: str | None = None`.
  - `event_sentiment/scoring.py` : ctor accepte `model_revision` ; `_load_model_for_device` passe `revision=` aux `from_pretrained` ; nouvelle propriété `model_fingerprint` = `sha256(model_name + ":" + (revision or "HEAD") + ":" + str(sorted(config.to_dict().items())))[:16]` mise en cache.
  - `event_sentiment/models.py` : `SentimentRecord.model_fingerprint: str = ""`.
  - `alembic/versions/00XX_finbert_fingerprint.py` : `model_fingerprint VARCHAR(32) NULL` sur `news_sentiment`.
  - `event_sentiment/pipeline.py` : `stats["finbert_model_fingerprint"] = self.finbert.model_fingerprint`.
  - `event_sentiment/cli.py` : argument `--finbert-revision`.
  - `event_sentiment/signal_aggregator.py` : enrichir `_build_cli_run_summary` avec le fingerprint actif (nouveau helper `EventSentimentRepository.get_active_finbert_fingerprints(trade_date)`).
- **Tests** : `tests/test_finbert_preprocessor.py` (`test_fingerprint_stable_across_calls`, `test_fingerprint_changes_with_revision`), `tests/test_event_repository_db_io.py` (persist fingerprint), `tests/test_event_pipeline_defaults.py` (stats), `tests/test_event_sentiment_run_summaries.py` (champ payload).
- **Doc** : `doc/event_sentiment.md` — sections "Versionnement FinBERT" + "Source unique Alpaca News" (limites + backlog SEC EDGAR).
- **Done** : `news_sentiment.model_fingerprint` peuplé sur tout nouveau scoring ; `run_summary` contient `finbert_model_fingerprint`.
- **Dépendances** : indépendant de 4.1.a/4.1.b mais à faire **après 4.1.b** pour éviter conflit sur `signal_aggregator._build_cli_run_summary`.

### 4.2.a — Découper `trainer.train_symbol` en sous-fonctions
- **Objectif** : préparer 4.2.b/c/d/e/f (extraction de fingerprint, format natif, quarantaine, BLOB DB plus sûres dans des fonctions courtes).
- **Fichiers** : `modelFactory/trainer.py` — extraire de `train_symbol` (lignes 499-842) :
  - `_resolve_effective_config(symbol, bars_df, cfg)`
  - `_setup_datamodule(...)`
  - `_train_lstm(...)`
  - `_train_local_challengers(...)`
  - `_persist_artifacts(...)`
  - `_persist_db(...)`
  - `train_symbol` devient compositor (~50 lignes). **Aucune modification de signature publique**.
- **Tests** : tests existants restent verts ; nouveaux tests unitaires sur 1-2 sous-fonctions extraites.
- **Doc** : `doc/modelFactory.md` — diagramme "17 étapes" pointe vers les sous-fonctions.
- **Done** : `train_symbol` < 80 lignes ; couverture ≥ baseline.
- **Dépendances** : aucune. Recommandé en premier dans 4.2.

### 4.2.b — Fingerprint features SHA256 dans `config.json`
- **Objectif** : tracer le contrat de features ; bloquer en CI tout changement silencieux.
- **Fichiers** :
  - `modelFactory/features.py` : `def fingerprint(*, include_sentiment, feature_set, include_cross_sectional) -> str` = `sha256(json.dumps({...}, sort_keys=True))[:16]`.
  - `modelFactory/trainer.py` (`_persist_artifacts`) : `config_data["feature_fingerprint"] = features.fingerprint(...)`.
  - `modelFactory/predictor.py` : recalcule à l'inférence ; **WARNING (pas raise)** si différent.
  - `modelFactory/global_model.py` : idem.
- **Tests** : `tests/test_model_factory_features_fingerprint.py` — `test_fingerprint_v1_no_sentiment_no_cross_is_stable` (gold value), `test_fingerprint_changes_with_*`.
- **Doc** : `doc/modelFactory.md` — section "Feature fingerprint" + procédure de régénération de la gold value.
- **Done** : tout `config.json` produit contient `feature_fingerprint` ; gold value bloque les modifs accidentelles.
- **Dépendances** : 4.2.a.

### 4.2.c — Migration LightGBM/CatBoost vers format natif
- **Objectif** : éliminer pickle pour les modèles tabulaires.
- **Fichiers** :
  - `modelFactory/tabular_baseline.py` : remplacer `pickle.dump(model)` par save callback. LightGBM → `model.booster_.save_model(path.txt)` ; CatBoost → `model.save_model(path.cbm)`.
  - `modelFactory/lightgbm_baseline.py` / `catboost_baseline.py` : injectent `save_callback`, `load_callback`, `model_extension`.
  - `modelFactory/predictor.py` : router selon extension (`.txt` → `lgb.Booster(model_file=)` ; `.cbm` → `CatBoostClassifier().load_model()` ; `.pkl` → **rétrocompat** + WARNING deprecated).
  - `modelFactory/global_model.py` : adapter sauvegarde + chargement.
- **Tests** : `tests/test_model_factory_lightgbm_baseline.py` (format natif), nouveau `tests/test_model_factory_catboost_baseline.py`, `tests/test_model_factory_predictor.py` (3 cas : native lgb, native cbm, pickle fallback).
- **Doc** : `doc/modelFactory.md` — "Format des artefacts ML" + "Migration pickle → natif".
- **Done** : aucun nouveau `.pkl` produit pour les challengers tabulaires ; rétrocompat lecture testée.
- **Dépendances** : 4.2.a.

### 4.2.d — Cache LRU des modèles dans `predictor.py`
- **Objectif** : éviter `pickle.load` + `load_from_checkpoint` à chaque appel `predict_symbol`.
- **Fichiers** : `modelFactory/predictor.py` — `_ModelCache` (`functools.lru_cache(maxsize=128)`) clé `(model_path, mtime, device)` stockant `(model_object, scaler_object, calibrator_object)` ; refactoriser `predict_symbol` pour passer par le cache ; API `clear_model_cache()`.
- **Tests** : `tests/test_model_factory_predictor.py` — `test_predict_batch_loads_each_model_once`, `test_cache_invalidates_on_mtime_change`.
- **Doc** : `doc/modelFactory.md` — "Performance prédiction batch".
- **Done** : `predict_batch` sur 200 symboles ne recharge pas les modèles communs.
- **Dépendances** : 4.2.c (pour avoir une API loader stable).

### 4.2.e — Quarantaine champion (`--champion-min-runs`, `--champion-min-days`)
- **Objectif** : empêcher un nouveau champion d'être servi avant N runs walk-forward OU N jours d'observation.
- **Fichiers** :
  - `modelFactory/config.py` : `ChampionSelectionConfig.min_runs: int = 0`, `min_days: int = 0`, validations ≥ 0.
  - `modelFactory/champion_selection.py` : `is_under_quarantine(model_name, symbol, *, min_runs, min_days, registry)` ; `select_champion` exclut + annote `quarantine_reason`.
  - `modelFactory/db_registry.py` : `count_completed_runs(engine, symbol, model_name) -> tuple[int, datetime|None]`.
  - `modelFactory/cli.py` : `--champion-min-runs`, `--champion-min-days`.
- **Tests** : `tests/test_model_factory_champion_selection.py` — quarantine blocks/releases ; `tests/test_model_factory_main.py` — parsing CLI.
- **Doc** : `doc/modelFactory.md` — "Quarantaine champion".
- **Done** : nouveau champion candidat reste non servi tant que seuils non franchis ; champion sortant fallback.
- **Dépendances** : aucune dure ; après 4.2.b pour éviter conflits sur `champion_selection.py`.

### 4.2.f — Persistance `metrics.json` BLOB en DB
- **Objectif** : ne plus dépendre uniquement de `artifacts/models/<symbol>/metrics.json`.
- **Fichiers** :
  - Migration Alembic `00XX_model_metrics_full_blob.py` : table `model_metrics_full(run_id PK, symbol, metrics_json LONGBLOB, created_at)`.
  - `modelFactory/db_registry.py` : `upsert_metrics_full(engine, *, run_id, symbol, metrics)`.
  - `modelFactory/trainer.py` (`_persist_db`) : si champion → `upsert_metrics_full`.
- **Tests** : `tests/test_model_factory_db_registry.py` — round-trip ; `tests/test_model_factory_trainer.py` — persist pour champion.
- **Doc** : `doc/modelFactory.md` — "Que faire si on perd `artifacts/models/`".
- **Done** : ligne en DB par run champion ; round-trip JSON identique.
- **Dépendances** : 4.2.a.

### 4.2.g — `--walkforward` par défaut + `--ml-mode rebuild-missing`
- **Objectif** : éliminer le risque de validation optimiste ; offrir un mode incrémental.
- **Fichiers** :
  - `modelFactory/cli.py` : `--walkforward` en `BooleanOptionalAction` default `True`. `--ml-mode {rebuild-all, rebuild-missing, refresh-stale}` (default `rebuild-all`).
  - `modelFactory/orchestrator.py` : `run_training_batch(mode=...)` ; `_filter_symbols_by_mode(engine, symbols, mode, current_fingerprint)`.
- **Tests** : `tests/test_model_factory_main.py` — defaults + `--no-walkforward` + `--ml-mode rebuild-missing` skip.
- **Doc** : `doc/modelFactory.md` — "Walk-forward par défaut" + "Modes ML".
- **Done** : training par défaut active walk-forward ; `rebuild-missing` skippe symboles déjà entraînés au même fingerprint.
- **Dépendances** : 4.2.b (consomme `feature_fingerprint`).

### 4.2.h — `run_summary` ML : `model_fingerprint`, `feature_fingerprint`, `champion_quarantine`
- **Objectif** : refléter les nouveautés dans le payload `run_summary` ; passer par `core.run_summary.attach_schema_version`.
- **Fichiers** : `modelFactory/cli.py` (ou `modelFactory/run_summary.py` analogue à `signal_aggregator._build_cli_run_summary`) — émettre `::alpha_trade_run_summary::{...}` en fin de `--mode train|predict`. Champs : `schema_version`, `mode`, `walkforward_enabled`, `ml_mode`, `feature_fingerprint`, `champion_min_runs`, `champion_min_days`, `symbols_total/completed/skipped/failed/quarantined`.
- **Tests** : `tests/test_model_factory_run_summary.py` — schema_version + parsing.
- **Doc** : `doc/modelFactory.md` — "Run summary ML".
- **Done** : ligne `::alpha_trade_run_summary::{...}` parsée sans erreur ; `schema_version` présent.
- **Dépendances** : 4.2.b, 4.2.e, 4.2.g.

---

## 4. Risques de régression et mitigations

| Sous-phase | Risque | Mitigation |
|---|---|---|
| 4.1.a | Drift numérique sur `final_score_sentiment` (somme float). | Test gold sur fixture (5 cas, tol `1e-9`). |
| 4.1.b | IHM `signal_aggregator` casse si CLI change. | **Geler la signature CLI** ; `test_ihm_pipeline_runner.test_build_pipeline_command_signal_aggregator_*` reste vert. |
| 4.1.c | Migration Alembic ; `revision=` invalide HF. | Migration NULL-able + backfill séparé ; `revision=None` = HEAD historique. |
| 4.2.a | Régression silencieuse dans `train_symbol`. | **Pas de changement de logique** ; tests `tests/test_model_factory_trainer.py` restent verts. |
| 4.2.b | Test gold bloque évolutions. | **Objectif** ; documenter "comment régénérer". |
| 4.2.c | Artefacts `.pkl` legacy illisibles. | **Double chemin** dans `predictor.py` ; test rétrocompat. |
| 4.2.d | Cache mémoire grossit. | `lru_cache(maxsize=128)` ; invalidation par `mtime`. |
| 4.2.e | Quarantaine bloque tout (cold start). | Defaults `min_runs=0, min_days=0` → désactivée ; fallback `default_champion`. |
| 4.2.f | LONGBLOB volumineux. | Stocker uniquement champion ; `gzip` optionnel si > 100 KB. |
| 4.2.g | `--walkforward` allonge runs. | Doc + `--no-walkforward` documenté pour CI ; `rebuild-missing` compense. |
| 4.2.h | `run_summary` mal parsé par IHM. | Test contractuel + `schema_version=1`. |

---

## 5. Ordre d'exécution

```
4.1.a → 4.1.b → 4.1.c
                    (commit indépendant)
4.2.a → 4.2.b → 4.2.c → 4.2.d
              ↓
              4.2.e → 4.2.f
                        ↓
                        4.2.g → 4.2.h
```

**Justifications** :
1. **4.1.a avant 4.1.b** : créer l'API avant de la consommer permet une revue isolée de la formule (gold + diff = 0).
2. **4.1.b avant 4.1.c** : les deux touchent `signal_aggregator.py` (lignes 920-960 vs 78-116) ; faire 4.1.b d'abord évite conflit de merge.
3. **4.1 avant 4.2** : zéro dépendance ; libère le sujet event_sentiment puis concentre la complexité ML dans 4.2.
4. **4.2.a en premier** : découper `train_symbol` rend toutes les sous-phases suivantes drastiquement plus simples.
5. **4.2.b avant 4.2.g** : `rebuild-missing` consomme `feature_fingerprint`.
6. **4.2.c avant 4.2.d** : le cache LRU doit savoir quel loader appeler.
7. **4.2.e/f en parallèle** : indépendantes.
8. **4.2.g avant 4.2.h** : `run_summary` (4.2.h) référence `walkforward_enabled` et `ml_mode`.
9. **4.2.h en dernier** : agrège tous les nouveaux signaux.

---

## 6. Critère de sortie de Phase 4

- Aucun artefact `.pkl` produit en sortie pour LightGBM/CatBoost (4.2.c).
- Champions gouvernés par quarantaine (4.2.e).
- `final_score_sentiment` produit par `core/conviction.py` (4.1.b).
- FinBERT versionné (`model_fingerprint` en DB + `run_summary`) (4.1.c).
- `feature_fingerprint` dans `config.json` + test gold CI-bloquant (4.2.b).
- `metrics.json` champion en DB BLOB (4.2.f).
- `--walkforward` actif par défaut + `--ml-mode rebuild-missing` (4.2.g).
- `run_summary` ML standardisé via `core.run_summary` (4.2.h).
- Audits `audit_event_sentiment.md` et `audit_modelFactory.md` cochés `✅ Phase 4`.

