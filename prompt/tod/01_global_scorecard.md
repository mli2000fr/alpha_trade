# 01 — Scorecard global

## Tableau récapitulatif des notes /10

| # | Module / Domaine | Note | Tendance | Commentaire express |
|---|---|---|---|---|
| 1 | Documentation (`doc/`, README) | **5.5** | ↘ | Riche mais désalignée du code (provider OHLCV, CA, doublon `backetesting.md`). |
| 2 | Configuration (`config.yaml`, presets, `pyproject`, `mypy`) | **6.0** | → | Presets bien structurés ; clé fantôme `eodhd.enabled`, `config.yaml` à durcir. |
| 3 | `dataIntegrityEngine/` | **7.0** | ↗ | Switch alpaca/eodhd implémenté proprement, sanitizer solide ; doc bandeau IEX obsolète. |
| 4 | `database/` (schéma + repos + alembic) | **7.5** | ↗ | Schéma propre, contrainte `chk_bars_adj`, multi-comptes propagé. Migrations à auditer. |
| 5 | `service/` (providers Alpaca/EODHD/Finnhub/Stooq/Tiingo/Yahoo) | **7.5** | ↗ | Adapters EODHD avec quota tracker, circuit breaker, cache disque. Bon design. |
| 6 | `screener/` | **6.5** | → | Scores liquidité/RS/range corrects ; couplage à la qualité des barres EODHD. |
| 7 | `selector/` (`alpha_scanner` + factors + filters + ranking) | **7.5** | ↗ | Multi-facteurs propre, neutralisation sectorielle, profils stricts unifiés. |
| 8 | `event_sentiment/` | **6.0** | → | FinBERT + agrégats ; risque sur-complexité vs bénéfice à mesurer empiriquement. |
| 9 | `modelFactory/` | **6.0** | → | Pipeline LSTM/governance/drift présent ; gouvernance des artefacts à muscler. |
| 10 | `risk_management/` | **6.5** | → | Sizing ATR strict bon ; circuit breaker non branché par défaut sur PnL réel. |
| 11 | `execution_engine/` | **7.5** | ↗ | Synthetic bracket bien pensé, audit trail complet ; tests sérieux. |
| 12 | `corporate_actions/` | **6.5** | ↗ | Sync/apply idempotents ; **docstring engine fausse**, à corriger. |
| 13 | `backtesting/` | **6.5** | → | Surface fonctionnelle large ; **vérifier intégration `portfolio_cash_ledger`** dans analytics. |
| 14 | `ihm/` (Streamlit pages + services) | **6.5** | → | Découpage Phase 6.2 bien fait ; `_execution_center.py` ~2 550 lignes à découper davantage. |
| 15 | Observabilité / `run_summaries` / logs | **7.0** | ↗ | Run summaries enrichis (IEX bias counters), schema versioning ; bon socle. |
| 16 | Sécurité / readiness production | **6.0** | → | Sentinelles secrets DB rejetées, ressaisie label live ; multi-comptes env non checké. |
| 17 | Qualité logicielle globale (lint/types/tests) | **7.0** | ↗ | ~190 tests, mypy + ruff ; quelques modules massifs (>2 000 lignes). |

## Note globale

| | Valeur |
|---|---|
| **Note globale Alpha Trade** | **6.4 / 10** |
| Niveau de confiance | **Élevé** (preuves `fichier:ligne` collectées sur la majorité des constats) |
| Verdict | **solide / quasi-pro partiel** |

## Positionnement comparatif

| Niveau de référence | Note typique | Alpha Trade aujourd'hui ? |
|---|---|---|
| Application amateur sérieuse | 4-5 | ❌ dépassé |
| Application indépendante avancée | 6-7 | ✅ **positionnement actuel** |
| Application pro buy-side / prop / desk swing | 8-9 | ⚠️ pas encore (gap : doc, sécurité ops, gouvernance ML, parité backtest/live formelle) |
| Application institutionnelle très mature | 9.5+ | ❌ hors cible immédiate |

## Trajectoire post-sprints

| Étape | Note projetée | Conditions |
|---|---|---|
| Après Sprint S1 (doc/config) | 6.7 | Anomalies P0/P1 doc traitées |
| Après Sprint S2 (IHM/pipeline) | 7.0 | Cohérence opérationnelle restaurée |
| Après Sprint S3 (risk/CA/backtest) | 7.4 | Live trading discipliné devient envisageable |
| Après Sprint S6 | 8.0 | Quasi pro-grade |
| Après Sprint S9 (gouvernance ML, parité backtest, refactor IHM) | 8.5+ | Pro-grade partiel revendiqué |

Détail des notes module par module dans `02_module_scorecards.md`.

