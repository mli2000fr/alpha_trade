# Audit backtest — Priorité 3

## Contexte
Cette note synthétise l’implémentation **réelle dans le code source** de la Priorité 3 backtest :
- coûts d’exécution plus réalistes,
- unification corporate actions / ajustements prix,
- réconciliation des exports pipeline de trades,
- adaptation IHM.

> Source de vérité : **le code**. La documentation du dossier `/doc` peut être en retard.

---

## 1) Coûts d’exécution réalistes

### Implémenté
Le backtest accepte désormais des coûts explicites séparés :
- `commission_bps`
- `slippage_bps`

L’IHM backtesting expose ces deux champs explicitement et ne retombe sur `fees` qu’en compatibilité legacy.

### Fichiers
- `ihm/services/backtesting_runner.py`
  - `BacktestRunOptions` contient `commission_bps` et `slippage_bps`
  - `build_backtesting_command()` émet `--commission-bps` / `--slippage-bps`
  - `--fees` n’est utilisé qu’en fallback legacy si les deux champs explicites sont absents
- `ihm/pages/backtesting/__init__.py`
  - widgets IHM `Commission (bps)` et `Slippage explicite (bps)`
  - défauts conditionnés au mode moteur (`research` vs `pipeline`)
  - correction du bug fonctionnel : le défaut lit `current_engine_mode` depuis la session **avant** la construction du widget
  - table de référence IHM mise à jour pour documenter `commission_bps`, `slippage_bps` et `fees` legacy

### Détail important
En mode `pipeline`, l’IHM préremplit :
- `commission_bps = 15.0`
- `slippage_bps = 15.0`

En mode `research`, l’IHM préremplit :
- `commission_bps = 5.0`
- `slippage_bps = 5.0`

---

## 2) Corporate actions / ajustements prix unifiés

### Convention implémentée
La convention projet est explicitée et surfacée dans le code :
- les prix de marché sont consommés comme **split-adjusted**,
- les dividendes **ne sont pas injectés dans les prix**,
- les flux cash corporate actions sont séparés dans `portfolio_cash_ledger`.

### Fichiers
- `corporate_actions/engine.py`
  - docstring d’orchestration qui formalise la convention canonique
  - `apply()` revalide les événements au moment de l’application
  - un événement invalide persisté est marqué `failed` via `repo.mark_failed(...)`
- `backtesting/report.py`
  - `load_corporate_actions_summary()` agrège `portfolio_cash_ledger`
  - expose notamment :
    - `price_adjustment_convention`
    - `split_adjusted_prices`
    - `dividends_reflected_in_prices`
    - `cash_ledger_entry_types`
    - `dividend_cash_total`
    - `cash_in_lieu_total`
    - `total_cash_impact`
  - `load_dividends_received()` s’aligne sur ce résumé
- `ihm/pages/backtesting/__init__.py`
  - affiche un bloc **Corporate actions / convention prix** lors de la lecture d’un `report.json`
- `backtesting/report_schema.py`
  - accepte maintenant explicitement le bloc racine `corporate_actions`

---

## 3) Réconciliation des exports pipeline de trades

### Implémenté
Le fichier `trades.csv` n’est plus limité au seul export legacy `closed_trades_df` quand la vérité pipeline est disponible.

Le code reconstruit un export réconcilié à partir des données pipeline Phase 3→7 si présentes, avec rapprochement best-effort contre le legacy.

### Fichiers
- `backtesting/report.py`
  - `_build_legacy_trade_export_frame()`
  - `_build_pipeline_trade_export_frame()`
  - `build_trade_export_bundle()`
  - `save_trades_csv()`
  - `save_report_json()` ajoute un bloc racine `trade_export`

### Informations exposées dans `trade_export`
- `source`
- `row_count`
- `legacy_source`
- `legacy_closed_rows`
- `pipeline_signal_rows`
- `pipeline_closed_rows`
- `pipeline_open_rows`
- `legacy_matches`
- `legacy_unmatched_rows`
- `export_closed_rows`
- `export_open_rows`
- `price_adjustment_convention`

### Colonnes enrichies côté export
Selon les données disponibles, l’export peut contenir notamment :
- `trade_status`
- `pipeline_reconciled`
- `legacy_trade_match`
- `exit_reason`
- `exit_intent_role`
- `oco_sibling_canceled`
- `watcher_transition_state`
- `estimated_pnl_price_only`
- `estimated_return_pct_price_only`

### IHM
- `ihm/pages/backtesting/__init__.py` affiche un bloc **Export trades réconcilié** lors de la lecture d’un `report.json`
- `backtesting/report_schema.py` accepte maintenant explicitement le bloc racine `trade_export`

---

## 4) Adaptation IHM backtesting

### Implémenté
L’IHM backtesting a été adaptée sur les points utiles à la Priorité 3 :
- coûts explicites commission/slippage,
- correction du défaut dépendant de `engine_mode`,
- lecture des blocs `corporate_actions` et `trade_export` dans `report.json`,
- documentation opérateur mise à jour dans la table de référence.

### Fichiers
- `ihm/pages/backtesting/__init__.py`
- `ihm/services/backtesting_runner.py`

---

## 5) Validation / tests

Tests ciblés exécutés après mise à jour :

- `tests/test_backtesting_refactor.py`
- `tests/test_executor.py`
- `tests/test_pages_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`

Résultat : **116 tests passés**.

Commande utilisée :

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_backtesting_refactor.py tests/test_executor.py tests/test_pages_backtesting.py tests/test_ihm_backtesting_runner.py -q -o addopts=
```

---

## 6) Verdict

### Priorité 3 backtest — état
- **Coûts d’exécution réalistes** : oui
- **Corporate actions / ajustements prix unifiés** : oui
- **Exports pipeline de trades réconciliés** : oui
- **IHM adaptée** : oui
- **Synthèse P3 présente dans `/prompt`** : oui

### Note
Il subsiste des warnings d’analyse statique sur certains gros fichiers IHM, mais ils ne remettent pas en cause l’implémentation fonctionnelle de la Priorité 3 backtest.

