# Audit et plan de recalibration du régime

_Date_: 2026-06-10

## 1. Contexte

L'ablation corrigée du régime a été exécutée dans :

- `F:\projets\artifacts\ablation\ml_regime_objective_structural_fix_full`

La correction architecturale préalable a découplé :

- les garde-fous structurels petit compte (`enforce_min_notional`, slots max)
- la logique macro/régime (`normal`, `capital_preservation`, `cash_only`)

Cela permet enfin d'évaluer le **vrai** coût/bénéfice du régime sans biais de sizing.

---

## 2. Verdict de l'ablation corrigée

Fichiers de référence :

- `F:\projets\artifacts\ablation\ml_regime_objective_structural_fix_full\ablation_summary.json`
- `F:\projets\artifacts\ablation\ml_regime_objective_structural_fix_full\ablation_decision.md`
- `F:\projets\artifacts\ablation\ml_regime_objective_structural_fix_full\ablation_runs.csv`

### Effet global du régime ON

- return moyen : `-1.56014380114`
- sharpe moyen : `-0.3695093813`
- amélioration drawdown : `-0.5625102147800001`
- fenêtres positives en return : `0/5`
- fenêtres positives en DD : `0/5`

### Interprétation

Le régime actuel paraît **sur-filtrant** : une fois le biais structurel retiré, il dégrade la performance sur les 5 fenêtres au lieu d'apporter une protection rentable.

---

## 3. Diagnostic ciblé par mode

### Source d'information

- `phase2_risk_summary.json` pour la distribution des modes et les entrées bloquées
- `stdout.log` des runs `control` pour les raisons et caps appliqués

### Répartition des modes par fenêtre (`control`)

| Fenêtre | Normal | Capital preservation | Cash only | Entrées bloquées régime |
|---|---:|---:|---:|---:|
| `2020_q1_crash` | 30 | 22 | 1 | 100 |
| `2020_q2_rebound` | 0 | 50 | 14 | 1104 |
| `2020_q3_momentum` | 20 | 38 | 8 | 800 |
| `2020_q4_rotation` | 32 | 17 | 16 | 1590 |
| `2020_full_year` | 82 | 127 | 39 | 3594 |

### Diagnostic principal

1. **`cash_only` est la principale source de blocage dur**
   - il explique l'essentiel de `entries_blocked_by_regime`
   - les volumes bloqués sont très élevés en Q2, Q3, Q4 et full year

2. **`capital_preservation` est la principale source de frein permanent**
   - il est actif très souvent, surtout en Q2 et full year
   - il n'arrête pas toutes les entrées, mais comprime fortement l'exposition

3. **Les caps appliqués sont probablement trop sévères**
   - `capital_preservation_max_gross_exposure = 0.50`
   - `hard_max_gross_exposure = 0.35`
   - `hard_max_positions = 1`

### Conclusion diagnostic

Le régime protège probablement **trop tôt**, **trop souvent** et **trop fort**.

Ordre de priorité des suspects :

1. `cash_only` trop fréquent / trop facile à déclencher
2. `capital_preservation` trop fréquent ou trop durable
3. caps trop serrés, surtout `max_gross_exposure`

---

## 4. Réglages actuels du régime (base)

Source : `F:\projets\config.yaml`

- `market_regimes.vix.high_threshold: 25.0`
- `market_regimes.capital_preservation_max_gross_exposure: 0.50`
- `market_regimes.yields.relative_spike_threshold: 0.05`
- `market_regimes.yields.hard_relative_spike_threshold: 0.08`
- `market_regimes.yields.hard_mode_backtest: cash_only`
- `market_regimes.yields.soft_max_positions: 2`
- `market_regimes.yields.soft_max_position_weight: 0.20`
- `market_regimes.yields.soft_max_sector_weight: 0.25`
- `market_regimes.yields.soft_max_gross_exposure: 0.50`
- `market_regimes.yields.hard_max_positions: 1`
- `market_regimes.yields.hard_max_position_weight: 0.15`
- `market_regimes.yields.hard_max_sector_weight: 0.20`
- `market_regimes.yields.hard_max_gross_exposure: 0.35`
- `market_regimes.sentiment_circuit_breaker.warning_threshold: -0.15`
- `market_regimes.sentiment_circuit_breaker.critical_threshold: -0.30`
- `market_regimes.sentiment_circuit_breaker.critical_mode_backtest: cash_only`

---

## 5. Objectif de recalibration

Préserver le bénéfice protecteur en baisse continue de marché **sans** :

- bloquer trop d'entrées sur les rebonds,
- rester trop longtemps en mode défensif,
- écraser l'exposition via des caps trop stricts.

La baseline de comparaison pour toutes les recalibrations reste :

- **`ml_off` + `regime_off`**
- garde-fous structurels petit compte **conservés**

---

## 6. Matrice de recalibration R1 → R5

La matrice est préparée par le script :

- `F:\projets\scripts\prepare_regime_recalibration_matrix.py`

Ce script génère :

- des configs YAML dédiées dans `artifacts/ablation/regime_recalibration_matrix/configs/`
- un manifest : `regime_recalibration_manifest.json`
- un lanceur PowerShell : `run_all.ps1`
- et, si `--execute` est fourni, exécute les 5 variantes via `scripts.run_ml_regime_ablation`

## R1 — Cash-only réservé aux chocs rates extrêmes

### Hypothèse
Réduire les blocages d'entrées en retirant le `cash_only` du sentiment critique ; ne garder le `cash_only` que pour les cas de choc de taux dur.

### Overrides
- `sentiment_circuit_breaker.critical_mode_backtest = capital_preservation`
- `yields.hard_relative_spike_threshold = 0.10`

---

## R2 — Cash-only réduit + capital_preservation modéré

### Hypothèse
Tester si le vrai frein vient surtout des caps de `capital_preservation`.

### Overrides
- `capital_preservation_max_gross_exposure = 0.65`
- `sentiment_circuit_breaker.critical_mode_backtest = capital_preservation`
- `sentiment_circuit_breaker.warning_max_positions = 3`
- `yields.hard_relative_spike_threshold = 0.10`
- `yields.soft_max_positions = 3`
- `yields.soft_max_position_weight = 0.25`
- `yields.soft_max_sector_weight = 0.30`
- `yields.soft_max_gross_exposure = 0.65`

---

## R3 — Cash-only réduit + capital_preservation souple

### Hypothèse
Vérifier si une posture défensive plus légère restaure la participation aux rebonds sans perdre toute protection.

### Overrides
- `capital_preservation_max_gross_exposure = 0.75`
- `sentiment_circuit_breaker.critical_mode_backtest = capital_preservation`
- `sentiment_circuit_breaker.warning_max_positions = 4`
- `yields.hard_relative_spike_threshold = 0.10`
- `yields.soft_max_positions = 4`
- `yields.soft_max_position_weight = 0.30`
- `yields.soft_max_sector_weight = 0.35`
- `yields.soft_max_gross_exposure = 0.75`

---

## R4 — Suppression totale de cash_only

### Hypothèse
Isoler le rôle de `cash_only` en forçant tous les déclencheurs durs à se rabattre sur `capital_preservation`.

### Overrides
- `sentiment_circuit_breaker.critical_mode_backtest = capital_preservation`
- `yields.hard_mode_backtest = capital_preservation`

---

## R5 — Suppression cash_only + triggers désensibilisés

### Hypothèse
Approximer une sortie plus rapide du défensif en rendant les triggers plus rares et `capital_preservation` plus modéré.

### Overrides
- `capital_preservation_max_gross_exposure = 0.65`
- `vix.high_threshold = 30.0`
- `sentiment_circuit_breaker.warning_threshold = -0.20`
- `sentiment_circuit_breaker.critical_threshold = -0.40`
- `sentiment_circuit_breaker.critical_mode_backtest = capital_preservation`
- `sentiment_circuit_breaker.warning_max_positions = 3`
- `yields.relative_spike_threshold = 0.07`
- `yields.hard_relative_spike_threshold = 0.10`
- `yields.hard_mode_backtest = capital_preservation`
- `yields.soft_max_positions = 3`
- `yields.soft_max_position_weight = 0.25`
- `yields.soft_max_sector_weight = 0.30`
- `yields.soft_max_gross_exposure = 0.65`

---

## 7. Protocole de runs

### Préparation seule

```powershell
Set-Location "F:\projets"
python -m scripts.prepare_regime_recalibration_matrix
```

### Préparation + exécution directe de la matrice

```powershell
Set-Location "F:\projets"
python -m scripts.prepare_regime_recalibration_matrix --execute --skip-existing
```

### Sorties attendues

Racine :

- `F:\projets\artifacts\ablation\regime_recalibration_matrix`

Sous-dossiers :

- `configs\R1.yaml` … `configs\R5.yaml`
- `variants\R1\...` … `variants\R5\...`
- `regime_recalibration_manifest.json`
- `run_all.ps1`
- `matrix_overview.json`

Chaque variante réutilise `scripts.run_ml_regime_ablation` et produit donc ses propres artefacts d'ablation complets.

---

## 8. Critères d'acceptation

### Critère A — protection Q1 crash
Le drawdown ne doit pas se dégrader de plus de `0.5 pt` vs baseline propre.

### Critère B — non-destruction des rebonds
Sur Q2 et Q4 :
- baisse nette de `entries_blocked_by_regime`
- return au moins proche de la baseline propre (tolérance `0.5 pt`)

### Critère C — robustesse annuelle
Sur `2020_full_year` :
- effet régime ON / variante recalibrée sur return **>= 0**
- ou au minimum très proche de 0 avec protection supérieure clairement démontrée

### Critère D — lisibilité métier
Le mode `cash_only` doit devenir rare et explicable ; `capital_preservation` doit rester un mode défensif mais ne plus écraser systématiquement l'exposition.

---

## 9. Ordre recommandé d'exécution / lecture

### Étape 1 — tester d'abord
- `R1`
- `R4`

Ces deux variantes isolent rapidement le rôle de `cash_only`.

### Étape 2 — puis tester
- `R2`
- `R3`

Ces variantes testent le rôle des caps de `capital_preservation`.

### Étape 3 — enfin
- `R5`

Cette variante combine suppression de `cash_only` et désensibilisation des triggers.

---

## 10. Règle de lecture finale

### Si `R1` ou `R4` améliorent fortement la perf
Alors le principal problème vient de `cash_only`.

### Si `R2` / `R3` améliorent beaucoup plus que `R1`
Alors le principal problème vient des caps de `capital_preservation`.

### Si `R5` domine tout
Alors le problème vient à la fois :
- de triggers trop sensibles,
- et d'une posture défensive trop sévère.

---

## 11. Mise à jour à faire après exécution

À la fin des runs R1→R5, compléter ce document avec :

- un tableau comparatif des 5 variantes vs baseline propre,
- les effets par fenêtre,
- la distribution des modes (`normal`, `capital_preservation`, `cash_only`),
- et une recommandation finale :
  - garder une variante,
  - ou poursuivre la recalibration.

