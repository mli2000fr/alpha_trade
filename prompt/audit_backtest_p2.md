# Audit backtest — Priorité 2 (suivi IHM / overlays)

## Statut de cette passe

Cette passe finalise surtout la **surface opérateur IHM** autour des protections P2 déjà exposées côté backtest, avec validation ciblée sur :

1. **cap sectoriel overlay visible dans la page backtesting**
2. **gap filter d’entrée visible dans la page backtesting**
3. **cohérence des commandes émises par l’IHM**
4. **couverture de tests ciblés**

> Cette note documente uniquement ce qui a été vérifié dans cette passe. Elle ne prétend pas re-certifier l’ensemble de la logique portefeuille/régime hors du périmètre IHM + commandes.

---

## 1) Backtesting — surfaces P2 exposées dans l’IHM

Dans `ihm/pages/backtesting/__init__.py`, la section :

- `🧪 Reproductibilité & surcouches research-grade (Phase B/C)`

expose bien les champs P2 utiles pour le prochain run défensif :

### Phase B — Micro-structure

- `Max gap d'ouverture (fraction)`

### Phase C — Risk overlays

- `Max exposure secteur`
- `Max DD portefeuille`
- `DD recovery`
- `Target annual vol (optionnel)`
- `Min ML coverage ratio (pipeline)`

Les défauts sont désormais résolus à partir du preset capital pipeline via :

- `backtesting_max_sector_exposure_pct`
- `backtesting_max_entry_gap_pct`
- `backtesting_max_portfolio_dd_pct`
- `backtesting_target_annual_vol`
- `backtesting_min_ml_coverage_ratio`

---

## 2) Référence de paramètres backtesting

La table de référence de la page backtesting documente explicitement les flags P2/P1 pertinents du CLI `python -m backtesting run`, notamment :

- `max_entry_gap_pct`
- `max_sector_exposure_pct`
- `max_portfolio_dd_pct`
- `target_annual_vol`

Cela réduit le risque d’écart entre ce qui est affiché dans l’IHM et ce qui est réellement supporté par la CLI.

---

## 3) Ce qui a été vérifié dans les tests

Validations exécutées dans cette passe :

```powershell
python -m py_compile "F:\projets\ihm\pages\backtesting\__init__.py"
python -m pytest "F:\projets\tests\test_pages_backtesting.py" -q --no-cov -k "parameter_reference_rows_include_walk_forward_run_options or build_pipeline_pit_status_message_warns_when_history_is_missing or build_ml_coverage_status_message_warns_when_coverage_is_partial"
```

Résultat : **OK**.

---

## 4) Fichiers concernés dans cette passe

- `F:\projets\ihm\pages\backtesting\__init__.py`
- `F:\projets\tests\test_pages_backtesting.py`

---

## Résumé opérationnel

Pour le prochain backtest pipeline défensif, les paramètres P2 les plus utiles sont maintenant clairement pilotables dans l’IHM :

- **cap sectoriel overlay**
- **gap filter d’entrée**
- **drawdown breaker portefeuille**
- **vol targeting**
- **gate ML**

En pratique, le backtest operator peut donc régler ces garde-fous sans repasser par la CLI brute.
