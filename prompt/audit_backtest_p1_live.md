# Portage live pipeline — Priorité 1 backtest

## Résumé exécutif

Les correctifs P1 du backtest sont désormais portés côté live pipeline sur les axes demandés :

1. **Drawdown breaker portefeuille activable et visible dans l’IHM**
2. **Vol targeting live activable et visible dans l’IHM**
3. **Gate dur de couverture ML** avant publication des cibles live
4. **Régime `rates shock` déjà durci et confirmé côté live**

## Ce qui est en place

### 1) Drawdown breaker portefeuille en live

- Le step `risk_management` accepte et propage désormais explicitement :
  - `--max-portfolio-drawdown-pct`
  - `--max-daily-loss-pct`
- Le backend live applique ces seuils via `RiskConfig` + `CircuitBreaker`.
- Les presets capital live portent déjà les valeurs `risk_max_drawdown_pct` / `risk_max_daily_loss_pct` dans `F:\projets\config\capital_presets.yaml`.

**Fichiers concernés**
- `F:\projets\ihm\services\pipeline_runner.py`
- `F:\projets\risk_management\cli.py`
- `F:\projets\risk_management\config.py`
- `F:\projets\risk_management\circuit_breaker.py`

### 2) Vol targeting live

- Le step `risk_management` propage :
  - `--target-annual-vol`
  - `--vol-target-lookback-days`
- Le backend live évalue la vol réalisée benchmark (`SPY`) puis réduit :
  - `risk_multiplier`
  - `max_gross_exposure`
- La télémétrie est exposée dans le `run_summary` sous `vol_targeting`.

**Fichiers concernés**
- `F:\projets\risk_management\live_pipeline_guards.py`
- `F:\projets\risk_management\cli.py`
- `F:\projets\risk_management\config.py`
- `F:\projets\ihm\services\pipeline_runner.py`

### 3) Gate dur sur la couverture ML

- Avant publication des cibles live, le step `risk_management` mesure la couverture ML du jour.
- Si `prediction_count / candidate_count < min_ml_coverage_ratio`, le run échoue avec `SystemExit`.
- Le comportement est journalisé et exposé dans le `run_summary` sous `ml_coverage_gate`.

**Fichiers concernés**
- `F:\projets\risk_management\live_pipeline_guards.py`
- `F:\projets\risk_management\cli.py`
- `F:\projets\ihm\services\pipeline_runner.py`
- `F:\projets\config\capital_presets.yaml`

### 4) Régime 2021–2022 style `rates shock`

Le durcissement était déjà présent côté live et a été confirmé :

- secteurs bloqués élargis : `Technology`, `Tech`, `Growth`, `Real Estate`, `Consumer Cyclical`, `Financial Services`
- `risk_mult` renforcé
- caps live resserrés sur positions / poids / exposition
- escalade `hard_mode_live: close_only`
- mode backtest séparé `hard_mode_backtest: cash_only`

**Fichiers concernés**
- `F:\projets\config.yaml`
- `F:\projets\service\market\config.py`
- `F:\projets\service\market\regime_manager.py`
- `F:\projets\risk_management\regime_apply.py`

## Où modifier les valeurs dans l’IHM (page Pipeline)

Dans la page **Pipeline** :

1. ouvrir **`Paramètres Risk Management (`python -m risk_management`)`**
2. ouvrir l’expander **`Risk — Kelly sizing & options avancées`**
3. aller à la sous-section **`Garde-fous live P1`**

Vous pouvez y modifier directement :

- **`Risk — DD max portefeuille`**
- **`Risk — perte journalière max`**
- **`Risk — target annual vol (0 = off)`**
- **`Risk — lookback vol target (jours)`**
- **`Risk — min ML coverage ratio (0 = off)`**

En plus, la page Pipeline affiche maintenant une bannière récapitulative :

- **`GARDE-FOUS RISK LIVE`**

avec rappel explicite du chemin de modification dans l’IHM.

## Presets capital

Les presets capital live préremplissent déjà les nouveaux garde-fous via :

- `risk_target_annual_vol`
- `risk_vol_target_lookback_days`
- `risk_min_ml_coverage_ratio`
- `risk_max_drawdown_pct`
- `risk_max_daily_loss_pct`

Valeur recommandée actuellement pour la couverture ML live : **`0.80`**.

## Tests ajoutés / validés

Tests ciblés passés sur :

- `F:\projets\tests\test_ihm_pipeline_runner.py`
- `F:\projets\tests\test_pages_pipeline.py`
- `F:\projets\tests\test_risk_management_cli.py`
- `F:\projets\tests\test_live_pipeline_guards.py`
- `F:\projets\tests\test_risk_regime_sizing_constraints.py`
- `F:\projets\tests\test_risk_ml_weight_gate.py`

Commande de validation exécutée :

```powershell
python -m pytest tests/test_ihm_pipeline_runner.py tests/test_pages_pipeline.py tests/test_risk_management_cli.py tests/test_live_pipeline_guards.py tests/test_risk_regime_sizing_constraints.py tests/test_risk_ml_weight_gate.py --cov-fail-under=0 -q
```

## Ajustements IHM finalisés dans cette passe

- correction d’une **erreur d’indentation** dans `F:\projets\ihm\pages\_execution_center\__init__.py`
- exposition claire des garde-fous live P1 dans la page Pipeline
- ajout d’une bannière opérateur dédiée pour rappeler les seuils actifs et leur emplacement de modification


## Points importants
- Le hard gate ML est bien bloquant côté live.
- Le vol targeting live est bien testé.
- Le régime rates shock était déjà durci côté live/shared config et a été confirmé dans le résumé.
- L’IHM Pipeline indique maintenant explicitement où régler ces paramètres.