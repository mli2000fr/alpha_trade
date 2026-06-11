# Plan d’implémentation R9.0 — Hystérésis de régime

_Date_: 2026-06-11

## Objectif

Faire évoluer la logique de régime d’un calcul **stateless** (photo du jour) vers une logique **stateful** (transition d’état) afin de réduire le sur-filtrage observé après les matrices `R1→R8`, sans retoucher d’abord les seuils de `R5`.

## Cible R9.0

- base fonctionnelle = réglages `R5`
- ajout d’une **hystérésis** sur les transitions `normal` ↔ `capital_preservation`
- persistance simple de l’état côté live
- propagation de l’état côté backtest pour garantir la parité

## Règles retenues pour R9.0

- entrée défensive immédiate sur **hard trigger**
- entrée défensive sur **soft triggers confirmés**
- maintien minimal du mode défensif
- sortie défensive uniquement après plusieurs jours calmes

### Paramètres par défaut R9.0

```yaml
market_regimes:
  hysteresis:
    enabled: false
    enter_soft_signals_required: 2
    enter_confirm_days: 2
    exit_soft_signals_max: 0
    exit_confirm_days: 3
    min_hold_days_defensive: 5
    hard_trigger_immediate: true
    hard_exit_confirm_days: 2
```

## Modifications fichier par fichier

### 1. `service/market/config.py`
Ajouter :
- `RegimeHysteresisConfig`
- champ `hysteresis` dans `MarketRegimesConfig`
- parsing YAML dans `parse_market_regimes()`

### 2. `service/market/models.py`
Ajouter :
- `MarketRegimeState`
- sérialisation `to_dict()` / `from_dict()` de l’état
- enrichissement de `MarketRegimeSnapshot` avec :
  - `raw_mode`
  - `previous_mode`
  - `transition_action`
  - `soft_signal_count`
  - `hard_triggered`
  - `state_age_days`
  - `next_state`

### 3. `service/market/regime_manager.py`
Refactor partiel :
- conserver la détection brute existante
- calculer `raw_mode`, `soft_signal_count`, `hard_triggered`
- appliquer une fonction `_apply_hysteresis(...)`
- retourner un snapshot enrichi contenant le `next_state`
- intégrer l’état dans la clé de cache

### 4. `service/market/state_store.py`
Créer un stockage JSON simple pour l’état live :
- `load_regime_state()`
- `save_regime_state()`
- chemin par défaut : `artifacts/market_regime/state/latest.json`

### 5. `service/market/__init__.py`
Exporter :
- `MarketRegimeState`
- `RegimeHysteresisConfig`
- `load_regime_state`
- `save_regime_state`

### 6. `risk_management/cli.py`
- charger l’état avant `build_snapshot()`
- passer `previous_state`
- sauvegarder `snapshot.next_state`

### 7. `run_execution.py`
Même intégration que `risk_management/cli.py` pour le preflight live.

### 8. `backtesting/risk_bridge.py`
- maintenir `previous_state` dans la boucle des `snapshot_dates`
- transmettre l’état au `build_snapshot()` suivant
- récupérer `snapshot.next_state`

### 9. `backtesting/weights_calibration.py`
Propager l’état lors de la résolution du segment régime pour garder une cohérence analytique avec la logique backtest principale.

### 10. `tests/test_market_regime.py`
Ajouter des tests de state machine :
- entrée soft confirmée
- hard trigger immédiat
- maintien minimal
- sortie confirmée
- parsing YAML de `hysteresis`

## Ce que R9.0 ne traite pas encore

- hysteresis différenciée par source (`vix` vs `yields` vs `sentiment`)
- persistance multi-comptes / multi-contextes
- compteur dédié de transitions dans les artefacts backtest
- gating complet de toutes les contraintes soft avant confirmation d’entrée

## Critères de validation R9.0

### Technique
- tests unitaires de transition verts
- pas de régression sur les tests de `service.market`
- `build_snapshot` backward-compatible quand `hysteresis.enabled = false`

### Métier / backtest
Comparer `R9.0` à `R5` :
- `cash_only = 0`
- `entries_blocked_by_regime = 0`
- `Q1 DD` pas pire de plus de `0.25 pt`
- `Q4 return effect` meilleur que `R5`
- `FY return effect` meilleur que `R5`

## Séquencement proposé

1. implémenter config + modèles + moteur d’hystérésis
2. propager l’état côté backtest
3. propager l’état côté live
4. sécuriser par tests
5. lancer une ablation dédiée `R9.0`

