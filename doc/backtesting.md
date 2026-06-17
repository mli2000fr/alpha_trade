# Backtesting & Backfill — guide d’usage

> Mise à jour : mai 2026
> Références principales : `backtesting/`, `ihm/pages/backtesting.py`, `ihm/services/backtesting_runner.py`

## 1. Objectif

Le module `backtesting/` couvre aujourd’hui quatre usages distincts :

- **backtest portefeuille** en mode `research` ou `pipeline` ;
- **backfill PIT** de `stock_scores_history` ;
- **diagnostic et recommandation screener** ;
- **calibration sentiment / walk-forward** via la CLI.

Le présent document décrit l’état **réellement implémenté dans le code**. Il distingue explicitement :

- ce qui est branché dans `python -m backtesting run` ;
- ce qui est disponible comme utilitaire dans `backtesting/` mais pas encore automatiquement exécuté par défaut ;
- ce qui est exposé dans l’IHM Streamlit.

---

## 2. Résumé rapide

### 2.1 Deux modes de backtest

| Mode | But | Comportement |
|---|---|---|
| `research` | recherche rapide | fallback possible vers `stock_scores`, tolérance aux trous de couverture |
| `pipeline` | replay PIT plus strict | exige `stock_scores_history`, produit un manifeste de fidélité, journalise les dégradations |

### 2.2 Sous-commandes disponibles

| Commande | Usage | Sorties / effet |
|---|---|---|
| `python -m backtesting run` | backtest complet | `report.json`, `fidelity_manifest.json`, `equity_curve.csv/png`, `trades.csv` |
| `python -m backtesting backfill-scores-history` | reconstruction PIT | écrit des snapshots dans `stock_scores_history` |
| `python -m backtesting diagnose-screener` | diagnostic PIT du screener | `summary_metrics.csv`, `daily_metrics.csv`, recommandations |
| `python -m backtesting recommend-screener` | recalcul de la recommandation | `scenario_recommendations*.csv`, résumés JSON |
| `python -m backtesting calibrate-sentiment-weights` | calibration des poids sentiment/macro | classement CSV, meilleur scénario JSON |
| `python -m backtesting walk-forward-sentiment` | calibration + backtest OOS | folds CSV, poids sélectionnés, `report.json` |

---

## 3. Architecture du module

| Fichier | Rôle |
|---|---|
| `backtesting/cli/_impl.py` | point central CLI |
| `backtesting/data_loader.py` | chargement OHLCV, scores PIT, prédictions ML |
| `backtesting/fidelity.py` | diagnostics PIT + `fidelity_manifest.json` |
| `backtesting/resilience.py` | politiques `ml_mode`, `sentiment_mode`, stratégie PIT ML |
| `backtesting/signal_replay.py` | reconstruction des signaux et fusion conviction |
| `backtesting/simulator.py` | simulateur journalier stateful (`signal J -> entrée J+1 open`) |
| `backtesting/microstructure.py` | slippage volume-aware, gap filter, initial stop, intrabar priority |
| `backtesting/risk_overlay.py` | sizing avancé, filtre régime, cap sectoriel, drawdown breaker, vol target |
| `backtesting/risk_bridge.py` | bridge Phase 2 vers `risk_management` |
| `backtesting/execution_bridge.py` | bridge Phase 2 vers `execution_engine` |
| `backtesting/execution_replay.py` | Phase 3 : replay explicite des entrées |
| `backtesting/execution_lifecycle_replay.py` | Phase 4 : protections issues des child intents |
| `backtesting/protection_watcher_replay.py` | Phase 5 : replay du watcher |
| `backtesting/exit_lifecycle_replay.py` | Phase 7 : exit terminal explicite + OCO logique |
| `backtesting/report.py` | métriques, exports CSV/PNG/JSON |
| `backtesting/run_metadata.py` | reproductibilité (`git`, `python`, `dataset_hash`, `seed`) |
| `backtesting/backfill_scores_history.py` | backfill PIT piloté par preset capital |
| `backtesting/analytics.py` | utilitaires benchmark/tail analytics/HTML interactif non branchés par défaut au `run` |
| `backtesting/cache.py` | cache Parquet utilitaire non branché par défaut au `run` |
| `backtesting/statistical_validation.py` | bootstrap et sensibilité paramétrique, surtout utilisés en code/tests |

### 3.1 Drawdown breaker C.5 — ramp-up régimed

Le `DrawdownCircuitBreaker` (`backtesting/risk_overlay.py`) protège le portefeuille
en réduisant les allocations quand le drawdown dépasse `max_dd_pct`. Depuis le
sprint short (juin 2026), il intègre un mécanisme de **ramp-up progressif**
conditionné au régime de marché et à la progression de l'equity :

| État | Condition | Allocation |
|------|-----------|-----------|
| Non trippé | DD < seuil | 100% (normale) |
| Trippé, régime ≠ normal | — | `degraded_entry_allocation_pct` (base, ex. 10%) |
| Trippé, régime normal, equity ↓ ou = | Streak gelé | allocation inchangée |
| Trippé, régime normal, equity ↑ vs veille | Streak++ | base + streak × `ramp_up_pct_per_day` (cap `ramp_up_max_pct`) |

**Paramètres CLI** (préfixe `--dd-regime-ramp-up-*`) :

| Argument | Défaut | Description |
|----------|--------|-------------|
| `--dd-regime-ramp-up-enabled` | `False` | Active le ramp-up |
| `--dd-regime-ramp-up-pct-per-day` | `0.025` | Bonus par jour de recovery |
| `--dd-regime-ramp-up-max-pct` | `0.40` | Plafond d'allocation |

**Artefact de diagnostic** : `drawdown_breaker_daily.csv` enrichi des colonnes
`normal_streak` (compteur de jours de recovery) et `entry_mode` (régime courant).

---

## 4. Contrat de données

### 4.1 Barres OHLCV

Le backtesting lit `stock_bars_daily` avec une contrainte explicite :

- la colonne `data_source` doit exister ;
- la source retenue doit être **`eodhd_eod`**.

Colonnes attendues :

- `symbol`
- `trade_date` ou `date`
- `open`, `high`, `low`, `close` ou `adj_close`, `volume`

### 4.2 Scores PIT

Source prioritaire : `stock_scores_history`.

Colonnes exploitées quand elles existent :

- `final_score`
- `final_score_sentiment`
- `final_score_walk_forward`
- `sector`
- `is_candidate`
- `capital_preset_key`
- `config_fingerprint`

En mode `research`, fallback possible vers `stock_scores`.

En mode `pipeline`, ce fallback est refusé : absence d’historique PIT = échec du run.

### 4.3 ML et sentiment

Tables optionnelles :

- `model_predictions`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

Politiques disponibles :

- `auto`
- `off`
- `rebuild-missing`

### 4.4 Presets capital

Le backtest et le backfill partagent :

- `capital_preset_key`
- `capital_preset_source`
- `capital_preset_fingerprint`

Ces champs alignent les snapshots PIT, les contraintes portefeuille et l’IHM.

---

## 5. Commande `run`

### 5.1 Convention d’exécution

Convention du simulateur :

- signal daté en `J` ;
- entrée exécutée au **`open` de `J+1`** ;
- sorties évaluées après l’entrée sur barres daily ;
- `swing_only` interdit une sortie le jour même.

### 5.2 Exemple minimal

```powershell
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 100000
```

### 5.3 Paramètres principaux

#### Portefeuille

- `--equity`
- `--tp`
- `--ts`
- `--max-positions`
- `--profile strict_swing_cash|swing_cash_aggressive|custom`

#### Fidélité et scoring

- `--engine-mode research|pipeline`
- `--score-column auto|final_score_walk_forward|final_score_sentiment|final_score`
- `--ml-pit-strategy auto|use-persisted|rebuild-missing|walk-forward-train-then-predict`
- `--walk-forward-artifacts-dir ...`

#### Coûts

- `--commission-bps`
- `--slippage-bps`
- `--fees` (déprécié mais encore accepté)

Le `fees_pct` effectif vaut `(commission_bps + slippage_bps) / 10_000`.

#### Contraintes de compte

- `--account-type margin|cash`
- `--swing-only`

Effets principaux :

- `margin + auto` : blocage du 4e day trade sur 5 séances si `equity < 25 000` ;
- `cash` : utilisation du settled cash uniquement, avec settlement simplifié `T+1` ;
- `swing_only` : pas de revente le jour d’entrée.

#### Résilience données

- `--ml-mode auto|off|rebuild-missing`
- `--sentiment-mode auto|off|rebuild-missing`
- `--artifacts-dir artifacts/models`

#### Reproductibilité

- `--risk-free-rate`
- `--seed`

### 5.4 Profils et presets

Deux notions distinctes :

| Notion | Rôle |
|---|---|
| `capital_preset_key` | sélectionne / aligne le cadre PIT et les contraintes |
| `profile` | préremplit certains paramètres CLI sans écraser les flags explicites |

Profils disponibles :

| Profil | TP | TS | Max positions | Commission | Slippage | Compte | Swing |
|---|---:|---:|---:|---:|---:|---|---|
| `strict_swing_cash` | 0.08 | 0.05 | 20 | 5 bps | 5 bps | `cash` | oui |
| `swing_cash_aggressive` | 0.12 | 0.06 | 25 | 5 bps | 8 bps | `cash` | oui |
| `custom` | défauts CLI | défauts CLI | défauts CLI | défauts CLI | défauts CLI | libre | libre |

### 5.5 Phases de fidélité opt-in

| Phase | Flag | Effet | Dépendance |
|---|---|---|---|
| 2 | `--phase2-mode risk|risk_execution` | réutilise `PortfolioBuilder`, puis éventuellement intents/fills simulés | aucune |
| 3 | `--phase3-mode execution_replay` | réinjecte les quantités remplies simulées à `J+1 open` | `phase2_mode = risk_execution` |
| 4 | `--phase4-mode protection_replay` | rejoue TP / initial stop / trailing issus des child intents | `phase3_mode = execution_replay` |
| 5 | `--phase5-mode watcher_replay` | rejoue la logique du watcher de protection | `phase4_mode = protection_replay` |
| 7 | `--phase7-mode exit_lifecycle_replay` | rejoue l’exit terminal explicite + annulation OCO logique | `phase5_mode = watcher_replay` |

Exemple de configuration “la plus proche du pipeline live aujourd’hui” :

```powershell
python -m backtesting run \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --engine-mode pipeline \
  --ml-pit-strategy use-persisted \
  --phase2-mode risk_execution \
  --phase3-mode execution_replay \
  --phase4-mode protection_replay \
  --phase5-mode watcher_replay \
  --phase7-mode exit_lifecycle_replay
```

### 5.6 Microstructure

Flags disponibles :

- `--slippage-model fixed|linear|sqrt`
- `--slippage-base-bps`
- `--slippage-impact-coef`
- `--initial-stop-pct`
- `--max-entry-gap-pct`
- `--intrabar-priority conservative|tp_first|ts_first|random`

### 5.7 Risk overlays

Flags disponibles :

- `--sizing-mode equal_weight|conviction_weighted`
- `--sizing-min-weight-pct`
- `--sizing-max-weight-pct`
- `--regime-filter`
- `--regime-sma-window`
- `--regime-bear-threshold`
- `--max-sector-exposure-pct`
- `--max-portfolio-dd-pct`
- `--dd-recovery-pct`
- `--target-annual-vol`

---

## 6. Artefacts produits par `run`

### 6.1 Artefacts standard

Quand `output_dir` est fourni :

- `report.json`
- `fidelity_manifest.json`
- `equity_curve.csv`
- `equity_curve.png` si `--no-save` est absent
- `trades.csv` si `--no-save` est absent

### 6.2 Artefacts de phases

#### Phase 2

- `phase2_execution_targets.csv`
- `phase2_execution_entry_intents.csv`
- `phase2_execution_child_intents.csv`
- `phase2_execution_fills.csv`
- `phase2_execution_tca_summary.json`
- `phase2_execution_summary.json`

#### Phase 3

- `phase3_execution_replay_signals.csv`
- `phase3_execution_replay_summary.json`

#### Phase 4

- `phase4_protection_replay.csv`
- `phase4_protection_replay_signals.csv`
- `phase4_protection_replay_summary.json`

#### Phase 5

- `phase5_watcher_replay_lifecycle.csv`
- `phase5_watcher_replay_events.csv`
- `phase5_watcher_replay_signals.csv`
- `phase5_watcher_replay_summary.json`

#### Phase 7

- `phase7_exit_lifecycle_replay.csv`
- `phase7_exit_lifecycle_replay_events.csv`
- `phase7_exit_lifecycle_replay_signals.csv`
- `phase7_exit_lifecycle_replay_summary.json`

### 6.3 Structure de `report.json`

Le manifeste contient les blocs :

- `summary`
- `artifacts`
- `params`
- `diagnostics`
- `run_metadata`
- `fidelity`

Métriques calculées :

- `total_return_pct`
- `total_return_with_dividends_pct`
- `dividends_received`
- `cagr_pct`
- `sharpe_ratio`
- `sortino_ratio`
- `calmar_ratio`
- `ulcer_index`
- `max_drawdown_pct`
- `total_trades`
- `win_rate_pct`
- `avg_trade_duration_days`
- `profit_factor`

Points importants :

- `profit_factor` peut être sérialisé en `"inf"` s’il n’y a pas de pertes ;
- `run_metadata` ajoute `git_commit_sha`, `git_branch`, `python_version`, `platform`, `dataset_hash`, `seed`, etc. ;
- `fidelity` documente la provenance PIT et les dégradations éventuelles.

---

## 7. Pourquoi un backtest peut afficher `0 trade`

Causes les plus fréquentes :

1. `stock_scores_history` ne contient pas encore d’historique quotidien utile ;
2. un snapshot unique tombe sur une séance non exécutable ;
3. le dernier snapshot PIT est postérieur aux dernières barres ;
4. les candidats existent mais aucune entrée `J+1 open` n’est possible.

En pratique, il faut d’abord vérifier la couverture réelle de `stock_scores_history` sur la plage demandée.

---

## 8. Backfill PIT de `stock_scores_history`

### 8.1 Ce que fait le backfill

Pour chaque séance manquante, le service :

1. rejoue le screener ;
2. rejoue `AlphaScanner` ;
3. applique la fusion sentiment ;
4. écrit un snapshot PIT dans `stock_scores_history`.

Le backfill :

- n’écrit pas dans `stock_scores` courant ;
- saute les jours déjà historisés, sauf `--overwrite-existing` ;
- est piloté par `capital_preset_key` et `config_fingerprint`.

### 8.2 Commandes utiles

Test rapide :

```powershell
python -m backtesting backfill-scores-history --start 2026-04-17 --limit-days 1 --screener-workers 1
```

Backfill automatique :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 2
```

Avec borne explicite :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --end 2026-04-16 --screener-workers 2
```

Recalcul forcé :

```powershell
python -m backtesting backfill-scores-history --start 2026-04-17 --end 2026-04-17 --overwrite-existing --screener-workers 1
```

---

## 9. Diagnostic et recommandation screener

### 9.1 `diagnose-screener`

Artefacts produits :

- `daily_metrics.csv`
- `summary_metrics.csv`
- `scenarios.csv`
- `metadata.json`
- `scenario_recommendations.csv`
- `recommendation_summary.json`

Si les régimes sont disponibles :

- `market_regimes.csv`
- `summary_metrics_by_regime.csv`
- `scenario_recommendations_by_regime.csv`
- `cross_regime_recommendations.csv`
- `cross_regime_recommendation_summary.json`

Si la recommandation par objectif est calculée :

- `scenario_recommendations_by_objective.csv`
- `recommendation_summary_by_objective.json`

Exemple :

```powershell
python -m backtesting diagnose-screener --start 2024-01-01 --end 2024-12-31 --mode oat --limit-days 60
```

### 9.2 `recommend-screener`

Relit un `summary_metrics.csv` existant, et enrichit l’analyse si `daily_metrics.csv` est présent.

```powershell
python -m backtesting recommend-screener --input-dir artifacts/screener_diagnostics
```

### 9.3 Validation hold-out

Les deux commandes supportent :

- `--holdout-train-end`
- `--holdout-test-end`

pour générer :

- `holdout_validation_recommendations.csv`
- `holdout_summary.json`

---

## 10. Calibration sentiment et walk-forward

### 10.1 Calibration simple

```powershell
python -m backtesting calibrate-sentiment-weights \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --top-n 20 \
  --horizons 5,10,20
```

Artefacts :

- `sentiment_weight_calibration.csv`
- `sentiment_weight_calibration_best.json`

### 10.2 Walk-forward strict

```powershell
python -m backtesting walk-forward-sentiment \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --min-train-days 252 \
  --test-days 63 \
  --max-positions 20
```

Artefacts principaux :

- `walk_forward_folds.csv`
- `fold_metrics.csv`
- `walk_forward_out_of_sample_scores.csv`
- `walk_forward_selected_signals.csv`
- `selected_weights.csv`
- `latest_best_weights.json`
- `champion_weights.json`
- `report.json`

Ces poids peuvent ensuite être relus par `--walk-forward-artifacts-dir` ou via `backtesting/walk_forward.py`.

---

## 11. IHM Streamlit

La page `ihm/pages/backtesting.py` expose directement quatre familles d’actions :

- `run`
- `backfill-scores-history`
- `diagnose-screener`
- `recommend-screener`

L’IHM permet aussi :

- de lancer les commandes en arrière-plan ;
- de suivre l’historique des runs ;
- de lire / télécharger les logs ;
- d’afficher les KPIs issus de `report.json` ;
- de relire les artefacts screener.

Important :

- l’IHM expose bien `engine_mode`, `ml_pit_strategy`, `phase2/3/4/5/7`, `risk_free_rate`, `seed`, microstructure et risk overlays ;
- l’IHM **n’expose pas encore** les sous-commandes `calibrate-sentiment-weights` et `walk-forward-sentiment` ;
- l’IHM continue de construire la commande `run` avec `--fees` plutôt qu’avec `--commission-bps` / `--slippage-bps` séparés.

---

## 12. Écart actuel avec le pipeline live

Le backtest est désormais :

- **PIT-aware** ;
- **risk-aware** ;
- **execution-aware** ;
- **watcher-aware** ;
- **exit-lifecycle-aware**.

En revanche, il ne remplace pas le live :

- pas d’ordres broker réels ;
- pas de fills observés réels ;
- pas de runtime intraday complet ;
- pas de réconciliation broker native dans la boucle PnL ;
- pas de reconstruction complète des étapes live 1→10 à chaque séance de backtest.

Le bon message à retenir est donc :

> le backtest est aujourd’hui crédible pour la recherche avancée et l’audit de fidélité, mais le pipeline live reste la source de vérité opérationnelle.

---

## 13. Vérifications et validations utiles

### 13.1 Vérifier la couverture de `stock_scores_history`

```powershell
python - <<'PY'
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT COUNT(*) AS n,
               MIN(snapshot_date) AS dmin,
               MAX(snapshot_date) AS dmax
        FROM stock_scores_history
    """)).mappings().one()
    print(dict(row))
PY
```

### 13.2 Vérifier un snapshot précis

```powershell
python - <<'PY'
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT snapshot_date,
               COUNT(*) AS n,
               SUM(CASE WHEN is_candidate = 1 THEN 1 ELSE 0 END) AS candidates
        FROM stock_scores_history
        WHERE snapshot_date = :d
        GROUP BY snapshot_date
    """), {"d": "2026-04-17"}).mappings().one()
    print(dict(row))
PY
```

### 13.3 Tests ciblés

```powershell
python -m pytest tests/test_backtesting.py tests/test_backfill_scores_history.py -q -o addopts=""
python -m pytest tests/test_backtesting_refactor.py -q --no-cov
```

Validations ciblées mentionnées dans les notes d’évolution :

```powershell
pytest tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_phase2_bridges.py tests/test_backtesting.py -q --no-cov
```

---

## 14. Séquence recommandée

Ordre conseillé :

1. tester un backfill sur 1 jour ;
2. étendre à 5 jours ;
3. lancer le backfill complet ;
4. lancer ensuite le backtest ;
5. activer les phases 2/3/4/5/7 seulement si l’objectif est un audit de fidélité.

Exemple :

```powershell
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 1 --screener-workers 2
python -m backtesting backfill-scores-history --start 2025-01-01 --limit-days 5 --screener-workers 2
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 2
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode auto --sentiment-mode auto
```

