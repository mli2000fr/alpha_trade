# 01 — Scorecard global

| # | Module / domaine | Note /10 | Verdict synthétique |
|---|---|---:|---|
| 1 | Documentation (`doc/`) | 7.5 | Très étoffée mais hétérogène en fraîcheur ; index OK. |
| 2 | Configuration (`config.yaml`, presets, pyproject, pytest, mypy) | 7.5 | Conventions claires ; presets micro-compte agressifs. |
| 3 | `dataIntegrityEngine/` | 8.0 | Provider switch propre, bandeau IEX, run_summary homogènes. |
| 4 | `database/` (schémas, repos, migrations Alembic) | 8.0 | Contraintes `chk_bars_adj` strictes, repositories propres. |
| 5 | `service/` (providers : alpaca, eodhd, finnhub, ibkr, stooq, yahoo) | 7.5 | Multi-providers, failover, cache, telemetry, retry HTTP. |
| 6 | `screener/` | 7.5 | Profil strict aligné capital_presets, persistence-guard. |
| 7 | `selector/` | 7.0 | Multi-facteurs solide ; filtres spread biaisés IEX. |
| 8 | `event_sentiment/` | 6.5 | Pipeline 5 étapes implicitement ordonnée, garde-fou absent. |
| 9 | `modelFactory/` (LSTM/LightGBM/CatBoost) | 7.0 | Gouvernance modèle, drift, champion ; coût/valeur à challenger. |
| 10 | `risk_management/` | 7.5 | Sizing + conviction + corrélation + regime ; Kelly désactivé. |
| 11 | `execution_engine/` | 7.5 | OMS/EMS structuré, préflight, kill-switch ; double entrée à clarifier. |
| 12 | `corporate_actions/` | 8.0 | Sync/apply idempotent, ledger cash, audit séparé du prix. |
| 13 | `backtesting/` | 7.5 | Parité, fidélité, walk-forward, fuzz, diagnostics screener. |
| 14 | `ihm/` (Streamlit) | 7.5 | Pages riches, tests E2E ; tooltips/help YAML, multi-compte. |
| 15 | Observabilité / `run_summary` / logs | 7.0 | Schémas versionnés, lineage, runbooks ; alerting à muscler. |
| 16 | Sécurité / readiness production | 7.5 | Scanner secrets, recette pré-live ; encore Kelly off, IEX biais. |
| 17 | Qualité logicielle globale (tests, typage, lint, dette) | 8.0 | ~280 tests, ruff, mypy, conftest mature, refactors propres. |

**Note globale agrégée pondérée : 7.4 / 10** — verdict **quasi-pro /
pro-grade partiel** pour usage swing US discipliné par un opérateur
indépendant à partir de ~10 k$.

| Comparatif | Position d'Alpha Trade |
|---|---|
| Amateur sérieux (4–5/10) | Largement au-dessus. |
| Indé avancé (5–7/10) | **Au-dessus** : structure, tests, OPS, conventions. |
| Buy-side / prop swing (7–8.5/10) | **Au pied** du niveau : il manque réconciliation J+1, parité backtest/live garantie, observabilité alerting, IEX → SIP. |
| Institutionnel mature (9–10/10) | Encore loin (formal verif, DR, capacity planning, redondance multi-broker production). |

Niveau de confiance de la note globale : **moyen-élevé** — le code est très
volumineux ; certains modules (modelFactory en profondeur, backtesting
internals) n'ont pas été lus ligne par ligne. Marge d'erreur estimée
±0.4 point.

