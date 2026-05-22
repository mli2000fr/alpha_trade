# 06 — Audit OHLCV / provider / conventions de données

## Provider OHLCV daily primaire réel

Le provider primaire réel des barres daily est **EODHD**.

Preuves :

- `config.yaml:181-183` : `market_data.bars_provider: eodhd`.
- `ihm/services/pipeline_runner.py:1494-1506` : si provider `eodhd`, la step IHM `import_alpaca_bar` route vers `python -m dataIntegrityEngine.import_eodhd_bar --write`.
- `dataIntegrityEngine/import_eodhd_bar.py:113-117` : résolution `market_data.bars_provider`.
- `dataIntegrityEngine/eodhd/cli.py:68-102` : no-op si provider différent ; run EODHD si `eodhd`.
- `dataIntegrityEngine/import_alpaca_bar.py:597-629` : no-op explicite si `bars_provider=eodhd`.

Conclusion : **le code réel confirme EODHD comme provider daily primaire**. Alpaca/IEX reste rétrocompatibilité pour daily et provider toujours actif pour assets/quotes/exécution.

## Switch provider

| Côté | Implémentation | Évaluation |
|---|---|---|
| Config | `market_data.bars_provider` dans `config.yaml` | Clair. |
| IHM | `_resolve_bars_provider_for_ihm()` + routage commande | Correct. |
| EODHD import | no-op si provider ≠ EODHD | Correct. |
| Alpaca import | no-op si provider = EODHD | Correct. |
| Fallback | `fallback_on_failure` non consommé | **Incohérent**. |

## Convention `data_adjustment`

La convention canonique est **`split`**.

Preuves :

- `database/sql/stock/stock_bars.sql:15-20` : `data_adjustment` default `split`, CHECK `data_adjustment='split'`.
- `database/sql/stock/stock_bars_daily.sql:20-27` : idem.
- `service/eodhd/adapters.py:38-40` : `DATA_SOURCE_EODHD='eodhd_eod'`, `DATA_ADJUSTMENT_SPLIT='split'`.
- `corporate_actions/engine.py:34-55` : barres split-only ; dividendes séparés dans `portfolio_cash_ledger`.

Évaluation : convention robuste et saine pour éviter le double comptage dividendes. Mais elle exige que tout backtest total return ajoute explicitement le ledger cash.

## `data_source`

| Table | Schéma | Comportement |
|---|---|---|
| `stock_bars` | Unique `(symbol,timeframe,timestamp)` | Une source par symbole/timeframe/timestamp ; EODHD et Alpaca peuvent se remplacer si même timestamp. |
| `stock_bars_daily` | PK `(symbol,date)` | Une source par symbole/date ; pas de cohabitation simultanée. |

Contradiction détectée : `doc/data_lineage_matrix.md:114-115` indique cohabitation simultanée daily `alpaca_iex` et `eodhd_eod`. Cette affirmation est fausse selon le schéma actuel.

## EODHD split-only reconstruction

`service/eodhd/adapters.py` explique que EODHD fournit OHLC brut + adjusted close total return. Le projet reconstruit split-only avec les splits :

- `cumulative_split_factor()` (`adapters.py:82-104`) ;
- `eodhd_to_split_only()` (`adapters.py:153-194`) ;
- `to_stock_bars_daily_row()` (`adapters.py:231-260`) met `adj_close=close` et `vwap` proxy typical price.

Évaluation : approche correcte mais à auditer continuellement sur splits récents, reverse splits et gros dividendes exceptionnels.

## Corporate actions

`CorporateActionEngine` ne modifie pas les bars. Il applique :

- splits aux positions/cost basis ;
- dividendes au `portfolio_cash_ledger`.

Preuves : `corporate_actions/engine.py:43-55`, schémas `portfolio_cash_ledger.sql:6-23`.

Risque : si les bars sont déjà split-adjusted et que l’apply split ajuste les positions, c’est cohérent en portefeuille live ; mais le backtesting doit éviter un double ajustement prix/position historique.

## Backtesting

La documentation indique source EODHD obligatoire (`doc/backtesting.md:76-79`). Cette décision est cohérente avec le provider primaire. En revanche, il faut un preflight DB :

```sql
SELECT data_source, COUNT(*)
FROM stock_bars_daily
WHERE date BETWEEN :start AND :end
GROUP BY data_source;
```

Le run doit échouer si la source requise n’est pas majoritairement/totalement `eodhd_eod` selon le mode choisi.

## Verdict OHLCV

- **Provider primaire réel** : EODHD.
- **Convention prix réelle** : split-only.
- **Dividendes** : ledger cash, pas dans prix.
- **Point faible majeur** : versioning source daily insuffisant et doc contradictoire.
- **Note spécifique OHLCV** : 7,0 / 10.

## Tests indispensables

| Test | Type | Scénario | Oracle |
|---|---|---|---|
| `test_eodhd_import_routes_from_ihm_when_provider_eodhd` | E2E/IHM | config EODHD, step import bars | commande contient `import_eodhd_bar --write`. |
| `test_alpaca_import_noop_when_provider_eodhd` | non-régression | lancer `import_alpaca_bar.main` | summary `mode=noop`, `skipped_reason=wrong_provider`. |
| `test_stock_bars_daily_cannot_claim_multi_source_same_date` | SQL/doc | schéma PK daily | doc checker refuse cohabitation. |
| `test_eodhd_split_only_roundtrip` | unit data | split 10:1 historique | prix anciens divisés, volume multiplié, adj_close=close persisté. |
| `test_backtest_refuses_non_eodhd_source_in_pipeline_mode` | backtest-live parity | daily source alpaca sur fenêtre | run pipeline échoue. |
| `test_corporate_actions_dividend_ledger_not_price_adjustment` | intégration CA | dividende cash | bars inchangées, ledger crédité une fois. |

