# 06 — Audit OHLCV / `data_adjustment` / corporate actions / lineage

## 1. Convention canonique en vigueur

| Attribut | Valeur canonique | Source vérité |
|---|---|---|
| `data_adjustment` | `split` (split-only) | `dataIntegrityEngine/import_alpaca_bar.py:36` (`DATA_ADJUSTMENT = "split"`) + `service/eodhd/adapters.py:DATA_ADJUSTMENT_SPLIT` (référencé par `corporate_actions/engine.py:39`) |
| Contraintes SQL | `chk_bars_adj`, `chk_daily_adj` | `database/sql/` + `doc/database.md §9` |
| Dividendes | Non injectés dans les prix ; comptabilisés via `portfolio_cash_ledger` | `corporate_actions/engine.py:43-50` |
| Total return | `MTM(positions, stock_bars_daily.close) + cumulative(portfolio_cash_ledger)` | `README.md §0`, `corporate_actions/engine.py:47-50` |

## 2. Provider OHLCV primaire actuel — verdict

| Élément | État réel (code) |
|---|---|
| `config.yaml › market_data.bars_provider` | `eodhd` (l. 182) |
| `fallback_on_failure` | `true` (l. 183) |
| Commande nominale étape 1 | `python -m dataIntegrityEngine.import_eodhd_bar` |
| Commande Alpaca (mode rétrocompat) | `python -m dataIntegrityEngine.import_alpaca_bar` (no-op contrôlé en mode eodhd) |
| Bandeau doc | `doc/dataIntegrityEngine.md:5-9`, `doc/data_lineage_matrix.md:5,12-14` |

**Verdict : EODHD est bien le provider primaire actuel.** Cohérence
intégrale `config ↔ code ↔ doc` confirmée.

## 3. Modules à vérifier explicitement

| Sujet | Cohérence | Commentaire |
|---|---|---|
| `dataIntegrityEngine/import_alpaca_bar.py` | ✅ | `DATA_ADJUSTMENT = "split"` ; no-op si bars_provider != alpaca (test `test_import_alpaca_bar_noop.py`). |
| `dataIntegrityEngine/import_eodhd_bar.py` | ✅ | Shim mince → `dataIntegrityEngine.eodhd.orchestrator.run_eodhd_ingestion`. Re-exports patchables pour tests préservés. |
| `service/eodhd/adapters.py` | ✅ | `eodhd_to_split_only`, `to_stock_bars_*` adaptateurs split-only. |
| `corporate_actions/engine.py` | ✅ | Docstring formelle de la convention ; engine ne touche jamais aux barres. |
| `backtesting/data_loader.py` | À confirmer | Charge `stock_bars_daily.close` split-adjusted → cohérent. |
| `selector/`, `screener/`, `risk_management/` | ✅ | Consommateurs des barres canoniques. |

## 4. Lineage

Voir `doc/data_lineage_matrix.md` (généré). **Synthèse audit** :
- 1 ligne par table métier, producteur unique annoncé.
- `stock_bars_daily` apparaît **deux fois** (provider eodhd primaire + provider alpaca rétrocompat) — risque visuel d'ambiguïté mais cohérent vu la `PRIMARY KEY(symbol,date)` qui empêche cohabitation. La note 2026-05-22 le précise.
- `stock_bars` intraday reste **toujours Alpaca**, ce qui est correct (EODHD intraday non utilisé).

## 5. Convention `data_adjustment` valeurs autorisées

| Valeur | Statut | Commentaire |
|---|---|---|
| `split` | ✅ canonique | seule valeur produite |
| `all` | ❌ rejetée par `chk_bars_adj` | empêche double ajustement dividende |
| `raw` | ❌ rejetée par `chk_bars_adj` | n/a |

Contrainte SQL bloquante : excellente garde-fou.

## 6. Risques résiduels

| ID | Risque | Sévérité |
|---|---|---|
| A-004 | quotes IEX biaisées indépendamment du provider barres | P1 |
| A-013 | bascule silencieuse EODHD → Alpaca/IEX sans alert | P1 |
| A-022 | impossibilité native cohabitation Alpaca + EODHD same-day | P2 |
| A-019 | partage du quota EODHD entre OHLCV + news + macro | P2 |
| A-030 | oracle "total return MTM+ledger vs reference" à renforcer | P2 |

## 7. Recommandations OHLCV

1. **Court terme** : alerter explicitement sur `provider_fallback_triggered`
   (A-013).
2. **Court terme** : exporter `data_source_distribution_by_day` dans le
   run_summary global pipeline pour repérer une bascule silencieuse.
3. **Moyen terme** : migration optionnelle `PRIMARY KEY(symbol,date,data_source)`
   pour comparer EODHD vs Alpaca en shadow (A-022).
4. **Moyen terme** : plug Alpaca SIP (payant ~$99/mo) ou Polygon NBBO
   pour résoudre A-004 sur les quotes.
5. **Long terme** : reproductibilité totale "tu fournis `(symbol,
   trade_date)`, je te rejoue le book cible" — nécessite figer
   provider+version+adj dans run_summary.

## 8. Verdict OHLCV

Le bloc OHLCV est **le plus solide de l'application** : conventions
explicites, contrainte SQL, audit dédié, run_summary instrumenté, switch
provider testé, fallback documenté. Notes : **8.0 / 10** (data integrity)
et **8.0 / 10** (corporate actions).

