# Audit & Plan d'action — Module `backtesting/`

> Date : 2026-04-30
> Périmètre : `backtesting/` + doc `doc/backetesting.md` + tests `tests/test_backtesting*.py`
> Auteur : audit automatisé GitHub Copilot

---

## 1. Résumé — ce qui est bien fait ✅

### 1.1 Architecture claire et modulaire
| Couche | Fichier | Responsabilité |
|---|---|---|
| Entrée | `cli.py` / `__main__.py` | Argparse multi-commandes (`run`, `backfill-scores-history`, `diagnose-screener`, `recommend-screener`, `calibrate-sentiment-weights`, `walk-forward-sentiment`) |
| Données | `data_loader.py` | Chargement OHLCV / scores / sentiment / preds avec introspection des colonnes |
| Signaux | `signal_replay.py` | Reconstruction conviction PIT |
| Moteur | `simulator.py` | Simulation jour par jour, TP/TS, contraintes |
| Contraintes | `trading_constraints.py` | cash account T+1, swing-only |
| Profils | `profiles.py` | Presets `strict_swing_cash`, `swing_cash_aggressive` |
| Reporting | `report.py` | Sharpe/Sortino/CAGR/DD/PF + JSON manifeste |
| Backfill | `backfill_scores_history.py` | Reconstruction historique snapshots |
| Diagnostic | `screener_diagnostics.py` | Phases 4→7 scoring scénarios |
| Calibration | `sentiment_calibration.py`, `weights_calibration.py`, `walk_forward.py` | Pondération sentiment/macro |
| Résilience | `resilience.py` | Modes `auto / off / rebuild-missing` ML & sentiment |

### 1.2 Réalisme financier sérieux
- Convention d'exécution correcte : **signal J → entrée open J+1** (anti look-ahead).
- Frais en bps explicites (commission + slippage) — Phase 6.1.b.
- Dividendes lus depuis `portfolio_cash_ledger` (Phase 6.1.c).
- Cash settlement T+1 simulé (`settled_cash` vs `unsettled_cash`).
- Sizing equal-weight borné par cash settlé / candidats restants.
- Frais inclus côté entrée ET sortie.

### 1.3 Cohérence pipeline live
- `signal_replay` consomme `core.conviction.fuse(...)` → mêmes poids que prod.
- Profils CLI alignés `risk/execution`.
- Source bars forcée à EODHD (`get_required_bars_source_filter`).

### 1.4 Robustesse opérationnelle
- Fallbacks gracieux : `final_score_walk_forward → final_score_sentiment → final_score`.
- Tolérance à l'absence des tables `model_predictions`, `ticker_daily_sentiment_features`.
- Modes `--ml-mode rebuild-missing` / `--sentiment-mode rebuild-missing`.
- Diagnostics blocage exposés dans `report.json`.

### 1.5 Recherche scénarios avancée (phases 4 → 9)
Balayage OAT/grid, recommandation pondérée robustesse/survie/forward, classement par régime (`bull/bear/range/vol`), cross-régimes, par objectif (robuste/offensif/bear/exécutable), validation hold-out, lancement IHM.

### 1.6 Tests
31 tests passent — couverture swing-only, cash settled, holdout, profils, backfill.

---

## 2. Points à améliorer ⚠️

### 2.1 Réalisme micro-structure (impact moyen→fort)
1. Slippage modélisé en **bps fixes** uniquement (pas de fonction de la liquidité / ADV / size / spread).
2. Pas de modélisation des **gaps d'ouverture** (open[J+1] pris brut).
3. **TP / TS conflict** intra-bar : trailing stop privilégié arbitrairement.
4. Pas de **stop-loss dur** initial (uniquement trailing).
5. Pas de gestion explicite des **splits/dividends en intra-trade**.

### 2.2 Pas de benchmark / attribution
- Pas de comparaison vs SPY (alpha, beta, IR, capture ratios).
- Pas d'attribution sectorielle (alors que `sector` est chargé !).
- Pas de rolling Sharpe / DD / monthly returns.

### 2.3 Risk management du moteur trop simple
- Sizing **equal-weight** uniquement (pas Kelly, pas conviction-weighted).
- Pas de stop-loss volatility-adjusted (ATR).
- Pas de filtre de régime à l'entrée.
- Pas de circuit breaker portefeuille (DD max → flat, sectoral cap).
- `max_positions` fixe.

### 2.4 `signal_replay.py` — performance
- `df.apply(fuse, axis=1)` ligne par ligne → lent sur grands univers × longues périodes.
- Cascade fallback `final_score_walk_forward → ...` répétée 4 fois (~40 lignes dupliquées).

### 2.5 `simulator.py` — qualité code
- Paramètre **`open` ombre la builtin Python**.
- `_run_with_constraints` monolithe ~200 lignes.
- Recalcul `market_value` deux fois par jour.
- `BacktestConfig` n'override pas `fees_pct` depuis `exec_config`.

### 2.6 `report.py`
- Sharpe sans `risk_free_rate` paramétré.
- Annualisation fixée à 252.
- Pas de Calmar / tail ratio / VaR / CVaR / Ulcer Index.
- `profit_factor = inf` mappé à 0 → trompeur.
- Pas de HTML interactif sauvegardé.

### 2.7 `data_loader.py`
- `pivot_ohlcv` charge tout en mémoire (ne scalera pas à 10 ans × 5000 symboles).
- `load_predictions` charge tout sans filtrer sur candidats.
- Aucun cache local (parquet) entre runs.

### 2.8 Reproductibilité / observabilité
- Pas de `git_commit_sha` / `dataset_hash` / `python_version` / `seed` dans `report.json`.
- Pas de schéma Pydantic → consommateurs IHM fragiles.

### 2.9 Tests
- Pas de tests Hypothesis sur invariants.
- Pas de golden test PnL sur dataset synthétique.
- Pas de benchmark perf.

### 2.10 Documentation
- Faute de frappe : `backetesting.md` au lieu de `backtesting.md`.
- Sections "11" dupliquées.
- Manque schéma d'architecture + glossaire `report.json`.

---

## 3. Plan d'action — Phases A à G

### Phase A — Quick wins (1-2 j)
- A1. Renommer paramètre `open` → `open_df` dans `simulator.py`.
- A2. Vectoriser `fuse()` dans `signal_replay.py`.
- A3. Factoriser cascade fallback scores → helper `_pick_score_column`.
- A4. Ajouter au `report.json` : `git_commit_sha`, `dataset_hash`, `python_version`, `seed`.
- A5. Ajouter Calmar ratio + Ulcer Index dans `BacktestReport`.
- A6. Paramétrer `rf_rate` dans `generate_report`.
- A7. Conserver `profit_factor = inf` (sentinel explicite) au lieu de mapper à 0.

### Phase B — Réalisme micro-structure (3-5 j)
- B1. Slippage volume-aware : `slippage_bps = base + k * (size / ADV20)`.
- B2. Stop-loss initial dur (`--initial-stop-pct`).
- B3. Gestion gap ouverture (`--max-entry-gap-pct`).
- B4. TP/TS conflict resolution configurable (`--intrabar-priority`).

### Phase C — Risk & sizing (3-5 j)
- C1. Sizing pondéré par conviction.
- C2. Volatility targeting portefeuille.
- C3. Filtre régime à l'entrée (réutilise phase 6 diagnostic).
- C4. Sectoral cap (`--max-sector-exposure-pct`).
- C5. Portfolio drawdown circuit breaker.

### Phase D — Reporting & analytics (2-3 j)
- D1. Benchmark vs SPY : alpha, beta, IR, tracking error, capture ratios.
- D2. Attribution sectorielle + monthly returns.
- D3. HTML interactif Plotly (en plus PNG).
- D4. VaR / CVaR 1d-95%, tail ratio, omega ratio.
- D5. Schéma Pydantic `BacktestReportSchema` + tests compat.

### Phase E — Performance & scalabilité (2-4 j)
- E1. Cache Parquet OHLCV/scores/preds.
- E2. Filtrer `load_predictions` sur candidats.
- E3. Refactor `_run_with_constraints` en sous-méthodes.
- E4. Single-pass `market_value` par jour.

### Phase F — Tests & qualité (2 j)
- F1. Tests Hypothesis sur invariants (cash + positions = equity).
- F2. Golden test PnL dataset synthétique.
- F3. Benchmark perf (`pytest-benchmark`).

### Phase G — Validation statistique (5-10 j)
- G1. Monte Carlo bootstrap (IC sur Sharpe / CAGR).
- G2. Analyse de sensibilité ±10% sur paramètres principaux.
- G3. Documentation glossaire `report.json` + diagramme architecture.

---

## 4. Verdict

Note qualitative : **8/10**. Architecture professionnelle, fidélité live/backtest, recherche scénarios avancée. Faiblesses principales : micro-structure, absence de benchmark, sizing simple, scalabilité I/O.

Priorités : **Phase A → D → B → C → E → F → G**.

