# 05 — Matrice écarts documentation ↔ code ↔ configuration

| ID | Document / config | Écart | Code source de vérité | Sévérité | Correction documentaire |
|---|---|---|---|---|---|
| GAP-001 | `doc/dataIntegrityEngine.md:136-149` | Runbook quotidien lance `import_alpaca_bar` alors que provider primaire est EODHD. | `config.yaml:181-183`; `ihm/services/pipeline_runner.py:1494-1506`; `import_alpaca_bar.py:597-629`. | P0 | Remplacer par `import_eodhd_bar --write` si `bars_provider=eodhd`, et préciser no-op Alpaca. |
| GAP-002 | `doc/dataIntegrityEngine.md:519-623` | Section détaillée focalisée Alpaca comme import bars principal. | `dataIntegrityEngine/import_eodhd_bar.py`; `dataIntegrityEngine/eodhd/orchestrator.py`. | P1 | Ajouter section EODHD comme chemin nominal ; déplacer Alpaca en rétrocompat. |
| GAP-003 | `doc/dataIntegrityEngine.md:662-663` | SPY absent déclenche import ciblé Alpaca selon doc. | `data_sanitizer_daily.py:142-152` dit no-op calendrier découplé ; EODHD primaire. | P1 | Corriger : calendrier NYSE via `common.market_calendar`; SPY n’est plus source calendrier. |
| GAP-004 | `doc/data_lineage_matrix.md:114-115` | Dit cohabitation `alpaca_iex` + `eodhd_eod` même `(symbol,date)` dans daily. | `database/sql/stock/stock_bars_daily.sql:24` PK `(symbol,date)`. | P1 | Dire “écrasement/upsert de la source active” ou migrer le schéma. |
| GAP-005 | `config.yaml:183` | `fallback_on_failure` suggère fallback mais non implémenté. | grep Python : tests uniquement. | P0 | Documenter “réservé/non supporté” ou implémenter. |
| GAP-006 | `doc/DOC_TECHNIQUE.md:102` | Source stricte mentionne `selector/strict_filter_profiles.py`. | `selector/strict_filter_profiles.py:1-12` alias ; source réelle `core/filter_profiles.py:1-13`. | P3 | Remplacer par `core/filter_profiles.py`, mentionner alias. |
| GAP-007 | `doc/DOC_FONCTIONNELLE.md:375` | Diagramme affiche `import_alpaca_bar` sans indiquer routage EODHD. | `pipeline_runner.py:536-542`, `1494-1506`. | P2 | Renommer “Import Bars provider-aware”. |
| GAP-008 | `database/connection.py:25-27` vs `:73-75` | Commentaire dit `user/pass` autorisés, message dit les remplacer. | Même fichier. | P3 | Aligner politique et message. |
| GAP-009 | `data_sanitizer_daily.py:169-175` | Commentaire explique `adj_close=close` par Alpaca. | EODHD primaire + adapter `service/eodhd/adapters.py:231-260`. | P3 | Reformuler par convention split-only provider-agnostique. |
| GAP-010 | `doc/backtesting.md:76-79` | Backtest exige EODHD mais ne mentionne pas le risque d’écrasement daily par PK. | `stock_bars_daily.sql:24`; `import_eodhd_bar.py:218-247`. | P1 | Ajouter preflight source `data_source=eodhd_eod`. |
| GAP-011 | `doc/ihm.md:199` | Liste step 1 `import_alpaca_bar`. | `pipeline_runner.py:536-542` dit provider-aware. | P2 | Renommer step doc. |
| GAP-012 | `doc/corporate_actions.md` | Généralement aligné, mais doit insister EODHD si `bars_provider=eodhd`. | `corporate_actions/provider.py:402-432`. | P3 | Ajouter table provider mapping. |

## Conclusion

La documentation principale a déjà commencé la migration vers EODHD, mais conserve trop de formulations historiques. La correction prioritaire n’est pas seulement cosmétique : elle conditionne le bon lancement opérateur et la traçabilité des données.

## Contrôle automatique recommandé

Créer `scripts/check_doc_provider_consistency.py` :

- recherche `python -m dataIntegrityEngine.import_alpaca_bar` non précédé/annoté par “rétrocompat” ou “bars_provider=alpaca” ;
- vérifie que `config.yaml market_data.bars_provider` et `doc/data_lineage_matrix.md` concordent ;
- vérifie que `stock_bars_daily` n’est pas documentée comme multi-source simultanée sans PK correspondante.

Test probable : `tests/test_docs_provider_consistency.py`.

