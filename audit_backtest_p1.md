# Audit backtest — Priorité 1 (implémentation)

## Statut

Les 4 points **Priorité 1 — indispensable** sont maintenant couverts dans le workspace :

1. **Drawdown breaker portefeuille activable par défaut en mode pipeline**
2. **Vol targeting activable par défaut en mode pipeline**
3. **Gating dur sur la couverture ML**
4. **Régime 2021-2022 “rates shock” durci**

---

## 1) Drawdown breaker portefeuille

### Ce qui est en place

- Le CLI backtest applique désormais des **défauts défensifs pipeline** depuis le preset capital.
- Les presets capital portent déjà des valeurs de type :
  - `backtesting_max_portfolio_dd_pct`
  - `backtesting_target_annual_vol`
  - `backtesting_min_ml_coverage_ratio`
- En IHM, ces valeurs sont maintenant **visibles et préremplies** dans l’écran de lancement du backtest quand le run est en mode `pipeline`.

### Où modifier la valeur dans l’IHM

Dans l’onglet backtesting, expander :

- `🧪 Reproductibilité & surcouches research-grade (Phase B/C)`
- section **Phase C — Risk overlays**

Modifier le champ :

- **`Max DD portefeuille`**

Champ associé :

- **`DD recovery`**

### Valeurs actuellement recommandées

- `Max DD portefeuille` : **0.12** sur micro-compte
- `DD recovery` : **0.98** côté IHM pipeline

---

## 2) Vol targeting

### Ce qui est en place

- Le CLI supporte déjà `--target-annual-vol`.
- Les presets capital fournissent maintenant une cible de vol backtest.
- L’IHM affiche et préremplit explicitement cette valeur en mode `pipeline`.

### Où modifier la valeur dans l’IHM

Même zone :

- `🧪 Reproductibilité & surcouches research-grade (Phase B/C)`
- section **Phase C — Risk overlays**

Modifier le champ :

- **`Target annual vol (optionnel)`**

### Valeurs actuellement recommandées

- micro-compte : **0.12**
- petits/moyens comptes : valeurs pilotées par `config/capital_presets.yaml`

---

## 3) Gating dur sur la couverture ML

### Ce qui est en place

- Le helper `evaluate_ml_coverage_gate(...)` est disponible dans `backtesting/fidelity.py`.
- Le CLI backtest :
  - accepte `--min-ml-coverage-ratio`
  - évalue le gate après préparation des prédictions
  - **bloque le run** si la couverture ML est insuffisante en mode `pipeline`
- Le payload du gate est aussi remonté dans les paramètres/artefacts du run.
- L’IHM expose maintenant le champ correspondant et l’injecte dans la commande.

### Où modifier la valeur dans l’IHM

Toujours dans :

- `🧪 Reproductibilité & surcouches research-grade (Phase B/C)`
- section **Phase C — Risk overlays**

Modifier le champ :

- **`Min ML coverage ratio (pipeline)`**

### Valeur actuellement recommandée

- **0.80**

### Effet

En mode `pipeline`, si la couverture ML observée est sous ce seuil :

- le run échoue immédiatement,
- avec un message explicite indiquant la couverture observée et le seuil requis.

---

## 4) Régime 2021-2022 “rates shock” durci

### Ce qui est en place

Le régime de taux est déjà durci dans le code/config actuel :

- `config.yaml`
- `service/market/config.py`
- `service/market/regime_manager.py`
- `risk_management/regime_apply.py`

### Renforcements observés

- extension des secteurs bloqués en choc de taux :
  - `Technology`
  - `Tech`
  - `Growth`
  - `Real Estate`
  - `Consumer Cyclical`
  - `Financial Services`
- réduction plus forte du risque :
  - `risk_mult`
  - `soft_max_positions`
  - `soft_max_position_weight`
  - `soft_max_sector_weight`
  - `soft_max_gross_exposure`
- mode dur possible en backtest :
  - **`cash_only`**
- caps d’exposition plus stricts lors d’un choc dur :
  - `hard_max_positions`
  - `hard_max_position_weight`
  - `hard_max_sector_weight`
  - `hard_max_gross_exposure`
- application effective des caps côté `RiskConfig` via `risk_management/regime_apply.py`

---

## Fichiers touchés pour finaliser cette phase

- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting/__init__.py`
- `tests/test_ihm_backtesting_runner.py`
- `audit_backtest_p1.md`

## Fichiers déjà impliqués par l’implémentation P1

- `backtesting/fidelity.py`
- `backtesting/cli/_impl.py`
- `config/capital_presets.yaml`
- `config.yaml`
- `service/market/config.py`
- `service/market/regime_manager.py`
- `risk_management/regime_apply.py`

---

## Validation effectuée

Tests exécutés avec succès :

```powershell
python -m pytest tests/test_ihm_backtesting_runner.py tests/test_risk_regime_apply.py tests/test_market_regime.py -q --no-cov
python -m pytest tests/test_backtesting.py -q --no-cov -k "apply_pipeline_defensive_defaults_from_preset or enforce_ml_coverage_gate_fails_fast_for_pipeline"
```

---

## Résumé opérationnel

Pour lancer un backtest pipeline plus défensif depuis l’IHM :

1. choisir un preset de configuration `pipeline_live_like` ou `production_parity`
2. vérifier le preset capital
3. dans **Phase C — Risk overlays**, ajuster si besoin :
   - `Max DD portefeuille`
   - `DD recovery`
   - `Target annual vol (optionnel)`
   - `Min ML coverage ratio (pipeline)`
4. lancer le run

En pratique, les protections P1 sont maintenant :

- **visibles** dans l’IHM,
- **émises** dans la commande,
- **testées**,
- et **cohérentes** avec les presets capital et le régime rates-shock.

