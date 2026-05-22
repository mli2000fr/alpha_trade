# Addendum documentaire — Audit `prompt/tod2` (2026-05-22)

Cet addendum réaligne les conventions documentaires avec le code courant audité. Il complète `DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`, `dataIntegrityEngine.md`, `data_lineage_matrix.md`, `corporate_actions.md`, `backtesting.md` et `ihm.md`.

## Conventions canoniques constatées

1. **Provider OHLCV daily primaire** : `EODHD`.
   - Config : `config.yaml › market_data.bars_provider: eodhd`.
   - IHM : la step historique `import_alpaca_bar` route vers `dataIntegrityEngine.import_eodhd_bar --write` quand `bars_provider=eodhd`.
   - Alpaca daily est conservé en rétrocompatibilité ; en mode EODHD, `import_alpaca_bar` doit être compris comme un no-op contrôlé.

2. **Convention de prix** : `data_adjustment = 'split'`.
   - Les schémas SQL `stock_bars` et `stock_bars_daily` imposent cette valeur via CHECK.
   - Les dividendes ne sont pas injectés dans les prix : ils passent par `portfolio_cash_ledger`.

3. **Corporate actions** :
   - `build_corporate_action_provider()` sélectionne `EodhdCorporateActionProvider` quand `bars_provider=eodhd`, sinon Alpaca.
   - Le module `corporate_actions` n’ajuste pas `stock_bars` / `stock_bars_daily`.
   - L’apply nécessite des snapshots de positions broker récents pour créditer correctement dividendes/splits sur portefeuille.

4. **Lineage `stock_bars_daily`** :
   - Le schéma actuel a `PRIMARY KEY(symbol,date)`.
   - Il ne permet donc pas une cohabitation simultanée de plusieurs `data_source` pour le même symbole/date. Toute documentation indiquant cette cohabitation doit être lue comme obsolète tant qu’une migration multi-source n’a pas été réalisée.

5. **Fallback provider** :
   - `market_data.fallback_on_failure` est présent dans `config.yaml`, mais l’audit n’a pas trouvé de consommation runtime Python hors tests/schema.
   - Ne pas le documenter comme un fallback opérationnel avant implémentation explicite.

## Runbook quotidien corrigé — mode EODHD nominal

```powershell
Set-Location -Path 'F:\projets'
python -m dataIntegrityEngine.import_eodhd_bar --write
python -m dataIntegrityEngine.data_sanitizer_daily
python -m screener.stock_screener
python -m dataIntegrityEngine.sync_latest_quotes
python -m dataIntegrityEngine.sync_earnings_calendar
python -m selector.alpha_scanner
python -m event_sentiment.signal_aggregator
python -m modelFactory --mode train
python -m modelFactory --mode predict
python -m risk_management
python .\run_execution.py simulate
python -m corporate_actions sync --portfolio-only
python -m corporate_actions apply
```

En pratique, l’utilisateur lance principalement le workflow depuis l’IHM. La commande ci-dessus sert de référence technique ; l’IHM reste la voie opérateur prioritaire.

## Runbook rétrocompatibilité Alpaca daily

À utiliser seulement si `config.yaml › market_data.bars_provider: alpaca` :

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
```

Si `bars_provider=eodhd`, ce module doit produire un `run_summary` `mode=noop`, `skipped_reason=wrong_provider`.

## Corrections documentaires à propager

- Remplacer les formulations “step 1 = `import_alpaca_bar`” par “step 1 = Import Bars provider-aware”.
- Corriger les sections qui décrivent SPY comme calendrier runtime obligatoire ; le sanitizer utilise désormais `common.market_calendar.nyse_session_dates` avec fallback historique.
- Corriger la matrice lineage concernant la cohabitation de sources dans `stock_bars_daily`.
- Ajouter un warning explicite sur `fallback_on_failure` tant que non implémenté.
- Préciser que `vwap` EODHD est un proxy typical price, pas un VWAP intraday réel.

## Tests documentaires recommandés

- `tests/test_docs_provider_consistency.py` : aucune commande `import_alpaca_bar` non qualifiée dans un runbook nominal EODHD.
- `tests/test_docs_lineage_schema_consistency.py` : la documentation ne promet pas une cohabitation multi-source daily si la PK ne l’autorise pas.
- `tests/test_config_keys_are_consumed.py` : toute clé critique de `config.yaml` est consommée ou explicitement déclarée réservée.

