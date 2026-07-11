# Glossaire `report.json` — module `backtesting`

> Référence des champs publiés dans `<output_dir>/report.json` après chaque
> backtest. Cohérent avec le refactor Phases A → G (voir
> [`refactor/backtesting/audit_plan.md`](../../refactor/backtesting/audit_plan.md)
> et [`refactor/backtesting/audit_plan_resume.md`](../../refactor/backtesting/audit_plan_resume.md)).

## Structure top-level

```jsonc
{
  "summary":        { ... },   // métriques principales (BacktestReport)
  "artifacts":      { ... },   // chemins relatifs vers les CSV/PNG/HTML
  "params":         { ... },   // paramètres CLI / config effective
  "diagnostics":    { ... },   // compteurs métier (swing/cash, gap, sectoral...)
  "run_metadata":   { ... },   // Phase A.4 — reproductibilité
  "benchmark":      { ... },   // Phase D.1 (optionnel)
  "tail":           { ... },   // Phase D.4 (optionnel)
  "sector_attribution": [...], // Phase D.2 (optionnel)
  "monthly_returns":    [...], // Phase D.2 (optionnel)
  "bootstrap":      { ... }    // Phase G.1 (optionnel)
}
```

## `summary` — `BacktestReport.to_serializable_dict()`

| Clé | Type | Description |
|---|---|---|
| `initial_equity` | float | Capital initial. |
| `final_value` | float | Equity finale (mark-to-market). |
| `total_return_pct` | float | Rendement total prix-only. |
| `total_return_with_dividends_pct` | float | Inclut les dividendes encaissés. |
| `dividends_received` | float | Total cash reçu. |
| `cagr_pct` | float | CAGR annualisé. |
| `sharpe_ratio` | float | Sharpe annualisé (excess returns vs `risk_free_rate`). |
| `sortino_ratio` | float | Sortino annualisé. |
| `max_drawdown_pct` | float | Max DD en %. |
| `calmar_ratio` | float \| `"inf"` | Phase A.5 — CAGR / |MDD|. `"inf"` si MDD ≈ 0. |
| `ulcer_index` | float | Phase A.5 — sqrt(mean(DD²)). |
| `risk_free_rate` | float | Phase A.6 — rf annualisé utilisé. |
| `total_trades` | int | Nombre de trades clôturés. |
| `win_rate_pct` | float | % trades gagnants. |
| `avg_trade_duration_days` | float | Durée moyenne. |
| `profit_factor` | float \| `"inf"` | Phase A.7 — sentinel `"inf"` si pertes = 0. |

## `diagnostics`

| Clé | Phase | Description |
|---|---|---|
| `blocked_same_day_exits` | base | Sorties bloquées par swing-only. |
| `blocked_cash_entries` | base | Entrées rejetées (cash settled insuffisant). |
| `executed_day_trades` | base | Day-trades exécutés. |
| `blocked_entry_gap` | B.3 | Entrées sautées (gap > seuil). |
| `initial_stop_exits` | B.2 | Sorties sur stop-loss initial dur. |
| `take_profit_exits` | B.4 | Sorties sur take-profit. |
| `trailing_stop_exits` | B.4 | Sorties sur trailing stop. |
| `blocked_by_regime` | C.3 | Entrées bloquées par filtre régime bear. |
| `blocked_by_sectoral_cap` | C.4 | Entrées bloquées par cap sectoriel. |
| `blocked_by_drawdown_breaker` | C.5 | Entrées bloquées par circuit breaker DD. |

## `run_metadata` (Phase A.4)

| Clé | Description |
|---|---|
| `git_commit_sha` | SHA HEAD du repo (ou `null`). |
| `git_branch` | Branche courante. |
| `git_dirty` | True si working tree modifié. |
| `python_version` | `sys.version`. |
| `platform` | OS + version. |
| `packages` | Versions de pandas / numpy / vectorbt / sqlalchemy. |
| `dataset_hash` | MD5 court d'OHLCV/scores/predictions. |
| `seed` | Graine reproductibilité (CLI `--seed`). |
| `generated_at_utc` | Timestamp UTC ISO (suffixe `Z`). |

## `benchmark` (Phase D.1, optionnel)

`alpha_annualized_pct`, `beta`, `information_ratio`, `tracking_error_pct`,
`up_capture`, `down_capture`, `benchmark_return_pct`.

## `tail` (Phase D.4, optionnel)

`var_95_pct`, `cvar_95_pct`, `tail_ratio`, `omega_ratio` — tous calculés sur
les returns journaliers.

## `sector_attribution` (Phase D.2, optionnel)

Liste de `{sector, n_trades, total_pnl, avg_return_pct, win_rate_pct}`.

## `monthly_returns` (Phase D.2, optionnel)

Pivot année × mois (`Jan` … `Dec`, `YTD`) en %.

## `bootstrap` (Phase G.1, optionnel)

`BootstrapResult.to_dict()` — IC sur Sharpe, total return, max DD à partir
d'un resampling avec remise des trades clôturés.

---

## Diagramme dataflow (Phase G.3)

```
                         ┌────────────────────────┐
                         │  CLI (backtesting.cli) │
                         └──────────┬─────────────┘
                                    │
                                    ▼
        ┌──────────────────────────────────────────────────────┐
        │          data_loader  (+ Phase E.1 cache.py)         │
        │  load_ohlcv / load_scores / load_predictions(symb=…) │
        └──────────────────┬───────────────────────────────────┘
                           │
                           ▼
              ┌──────────────────────┐
              │  resilience policies │ ml_mode + sentiment_mode
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │  signal_replay       │ (Phase A.2 vectorisé)
              │  conviction = fuse() │
              └──────────┬───────────┘
                         ▼
   ┌─────────────────────────────────────────────────────────┐
   │  simulator.BacktestEngine                               │
   │  – Phase B  microstructure  (slippage / gap / stop)     │
   │  – Phase C  risk_overlay    (sizing / regime / sector)  │
   │  – Phase E  single mark-to-market                       │
   └──────────┬──────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  report + analytics + statistical_validation         │
   │  → BacktestReport (Calmar/Ulcer)                     │
   │  → BenchmarkAnalytics, TailAnalytics, sector_attr    │
   │  → BootstrapResult                                   │
   │  → run_metadata                                      │
   └──────────┬───────────────────────────────────────────┘
              ▼
       ┌──────────────┐
       │ report.json  │  + equity_curve.csv / .png / .html
       └──────────────┘
```

