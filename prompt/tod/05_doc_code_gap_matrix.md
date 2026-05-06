# 05 — Matrice écarts doc ↔ code ↔ config

> Le code est la **source de vérité**. Chaque ligne ci-dessous indique la
> doc à corriger pour réaligner avec le code réel.

## Matrice principale

| # | Sujet | Doc actuelle (constat) | Code réel (preuve) | Écart | Anomalie |
|---|---|---|---|---|---|
| 1 | Provider OHLCV primaire | `doc/dataIntegrityEngine.md:3-22` (bandeau IEX), `doc/data_lineage_matrix.md:27-31` (Alpaca IEX) | `config.yaml:51` `bars_provider: eodhd` ; `import_eodhd_bar.py:151` | Doc parle d'Alpaca primaire, code utilise EODHD primaire | A-003, A-004, A-005 |
| 2 | Convention `data_adjustment` | `corporate_actions/engine.py:36` (docstring) dit `Alpaca adjustment="all"` | `import_alpaca_bar.py:36` `DATA_ADJUSTMENT="split"` ; `service/eodhd/adapters.py:262` `DATA_ADJUSTMENT_SPLIT` | Docstring ment | A-001 |
| 3 | Pipeline quotidien étape 1 | `README.md:142` `python -m dataIntegrityEngine.import_alpaca_bar` | Quand `bars_provider=eodhd`, l'étape réelle est `import_eodhd_bar` | Runbook obsolète | A-003 |
| 4 | `eodhd.enabled` | `config.yaml:55` `eodhd.enabled: false` ; `service/eodhd/__init__.py:21` (docstring) y fait référence | Aucune lecture en code applicatif | Clé fantôme | A-002 |
| 5 | Performance totale backtest | `README.md:15-16` formule canonique avec `portfolio_cash_ledger` | À confirmer dans `backtesting/analytics.py` | Possible non-application | A-006 |
| 6 | Doublon doc backtesting | `doc/backetesting.md` + `doc/backtesting.md` cohabitent | un seul doit subsister | Doublon | A-012 |
| 7 | Multi-comptes env check | `README.md:474-481` documente `ALPACA_<ID>_*` | `run_execution.py:60-62` ne contrôle que `ALPACA_API_KEY/SECRET_KEY` | Doc ne signale pas la limite | A-008 |
| 8 | Watcher post-run | `README.md:177-179` (optionnel) | Pas de hook automatique | Acceptable mais à clarifier | A-018 |
| 9 | Auto-gen lineage | `doc/data_lineage_matrix.md:8-10` (TODO `scripts/generate_data_lineage.py`) | Script absent | TODO non implémenté | A-019 |
| 10 | Structure simplifiée README | `README.md:427-447` omet `alembic/`, `service/`, `corporate_actions/` | Existent | Inexact | A-030 |
| 11 | `risk.max_drawdown` / `max_daily_loss` | `config.yaml:39-40` global ; doc ne mentionne pas l'absence de surcharge par préset | Override absent code | À documenter ou implémenter | A-011 |
| 12 | `weekly_trend_score=1.0` | Pas de mention du risque univers vide | Borné [0,1] dans `core/filter_profiles.py:67-68` | Risque non documenté | A-009 |
| 13 | Sentiment double application | `README.md:316` warning verbal | Pas de garde-fou code | À implémenter | A-022 |
| 14 | `signal_aggregator` poids 75/15/10 | `README.md:199` | À confirmer en code | À auditer | — |
| 15 | Doc IHM `_execution_center` | Doc sommaire ; fichier 2 550 lignes | TODO interne reconnu | Dette technique | A-016 |

## Doc à mettre à jour (livrable hors `prompt/tod/`)

> Ces mises à jour relèvent d'un sprint dédié (S1) à exécuter par un agent
> implémentation ou par l'utilisateur, suite à validation de l'audit. Le
> présent audit étant lecture seule sur le code, les patches précis sont
> listés ici comme spécification.

### `README.md`

- §6 « Pipeline quotidien recommandé » : remplacer l'étape 1 par un bloc
  conditionnel : si `bars_provider=alpaca` → `import_alpaca_bar`, si
  `eodhd` → `import_eodhd_bar`.
- §11 « Structure racine simplifiée » : ajouter `alembic/`, `service/`,
  `corporate_actions/`, `backtesting/`, `common/`, `core/`, `database/`.
- §1 « Conventions clés » : préciser que **EODHD est le provider primaire
  par défaut** (tout en gardant la convention `data_adjustment='split'`).

### `doc/dataIntegrityEngine.md`

- Réécrire le bandeau initial : « Provider primaire actuel : EODHD bulk EOD ».
- Conserver le tableau IEX en sous-section « rétrocompat ».
- Ajouter une section « comment basculer le provider » qui pointe vers
  `ihm/services/market_data_provider.py`.

### `doc/data_lineage_matrix.md`

- Marquer EODHD comme producteur principal de `stock_bars_daily` /
  `stock_bars` quand `bars_provider=eodhd`.
- Ajouter une colonne « Provider actif (selon `config.yaml`) ».
- Implémenter `scripts/generate_data_lineage.py` (sprint S6).

### `doc/corporate_actions.md`

- Aligner avec la convention `'split'` + ledger dividendes.
- Documenter la factory `corporate_actions/provider.py:399-405` qui choisit
  le provider CA selon `bars_provider`.

### `doc/backtesting.md`

- Documenter explicitement la formule de performance totale, et exiger
  l'inclusion du `portfolio_cash_ledger`.
- Supprimer ou rediriger `doc/backetesting.md`.

### `doc/DOC_FONCTIONNELLE.md`

- Mettre à jour la chaîne fonctionnelle pour mentionner EODHD primaire et
  l'étape conditionnelle d'ingestion.
- Mettre à jour le diagramme de flux (s'il existe) pour la nouvelle ordering.

### `doc/DOC_TECHNIQUE.md`

- Idem : provider primaire, factory CA, chemin de données réel.
- Ajouter un encart « dette technique reconnue » avec `_execution_center.py`,
  `alpha_scanner.py`, `import_eodhd_bar.py`.

### `doc/ihm.md`

- Documenter le sélecteur de provider OHLCV exposé dans `Settings`
  (`ihm/pages/settings.py:87`).
- Mettre à jour la liste des pages avec `backtesting`, `supervision_ops`,
  `db_admin`, `alpaca_accounts`, `risk` (incomplet dans README).

### Docstring code (un seul changement de docstring, sans toucher à la logique)

- `corporate_actions/engine.py:34-39` : réécrire la docstring (la convention
  réelle est `'split'` + ledger). C'est une mise à jour documentaire interne
  au code source, à exécuter dans le sprint S1.

## Synthèse

15 écarts doc ↔ code identifiés, dont 3 majeurs (P0) liés au provider OHLCV
primaire et à la convention `data_adjustment`. La dette documentaire est
**modérée mais persistante** : signe d'un refactor en cours (Phase 6 EODHD)
non terminé côté doc.

