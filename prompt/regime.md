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

## 11. Mise à jour après exécution (générée automatiquement)

- Généré le : `2026-06-10T20:19:00+00:00`
- Matrice : `F:\projets\artifacts\ablation\regime_recalibration_matrix`
- Baseline de comparaison : `F:\projets\artifacts\ablation\ml_regime_objective_structural_fix_full`

### Tableau comparatif R1→R5 vs baseline actuelle

| Variante | Return moyen effet régime | Sharpe moyen effet régime | DD moyen effet régime | Fenêtres return + | Fenêtres DD + | Q1 DD | FY return | Cash-only total | Entrées bloquées Q2/Q4/FY |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline actuelle | -1.560 | -0.370 | -0.563 | 0 | 0 | -0.008 | -4.284 | 78 | 1104/1590/3594 |
| R1 | -1.905 | -0.486 | -0.398 | 0 | 0 | -0.008 | -3.666 | 62 | 904/1190/2794 |
| R2 | -2.489 | -0.574 | -0.461 | 0 | 0 | -0.000 | -6.209 | 62 | 904/1190/2794 |
| R3 | -2.489 | -0.574 | -0.461 | 0 | 0 | -0.000 | -6.209 | 62 | 904/1190/2794 |
| R4 | -1.497 | -0.428 | -0.368 | 0 | 0 | -0.008 | -2.219 | 0 | 0/0/0 |
| R5 | -1.371 | -0.291 | -0.591 | 1 | 0 | -0.000 | -3.499 | 0 | 0/0/0 |

### Effets par fenêtre + distribution des modes (`control`)

| Variante | Fenêtre | Effet return | Effet Sharpe | Effet DD | Normal | Capital preservation | Cash only | Entrées bloquées |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| R1 | Q1 crash | -0.121 | -0.074 | -0.008 | 31 | 22 | 0 | 0 |
| R1 | Q2 rebound | -0.812 | -0.871 | -0.510 | 0 | 52 | 12 | 904 |
| R1 | Q3 momentum | -1.990 | -0.485 | -0.639 | 20 | 39 | 7 | 700 |
| R1 | Q4 rotation | -2.936 | -0.630 | -0.537 | 33 | 20 | 12 | 1190 |
| R1 | Full year | -3.666 | -0.372 | -0.294 | 84 | 133 | 31 | 2794 |
| R2 | Q1 crash | +0.000 | +0.000 | -0.000 | 31 | 22 | 0 | 0 |
| R2 | Q2 rebound | -0.812 | -0.871 | -0.510 | 0 | 52 | 12 | 904 |
| R2 | Q3 momentum | -1.990 | -0.485 | -0.639 | 20 | 39 | 7 | 700 |
| R2 | Q4 rotation | -3.433 | -0.760 | -0.632 | 33 | 20 | 12 | 1190 |
| R2 | Full year | -6.209 | -0.753 | -0.526 | 84 | 133 | 31 | 2794 |
| R3 | Q1 crash | +0.000 | +0.000 | -0.000 | 31 | 22 | 0 | 0 |
| R3 | Q2 rebound | -0.812 | -0.871 | -0.510 | 0 | 52 | 12 | 904 |
| R3 | Q3 momentum | -1.990 | -0.485 | -0.639 | 20 | 39 | 7 | 700 |
| R3 | Q4 rotation | -3.433 | -0.760 | -0.632 | 33 | 20 | 12 | 1190 |
| R3 | Full year | -6.209 | -0.753 | -0.526 | 84 | 133 | 31 | 2794 |
| R4 | Q1 crash | -0.121 | -0.074 | -0.008 | 30 | 23 | 0 | 0 |
| R4 | Q2 rebound | -0.812 | -0.871 | -0.510 | 0 | 64 | 0 | 0 |
| R4 | Q3 momentum | -1.757 | -0.434 | -0.648 | 20 | 46 | 0 | 0 |
| R4 | Q4 rotation | -2.576 | -0.511 | -0.479 | 32 | 33 | 0 | 0 |
| R4 | Full year | -2.219 | -0.251 | -0.194 | 82 | 166 | 0 | 0 |
| R5 | Q1 crash | +0.000 | +0.000 | -0.000 | 31 | 22 | 0 | 0 |
| R5 | Q2 rebound | +0.204 | -0.207 | -0.510 | 14 | 50 | 0 | 0 |
| R5 | Q3 momentum | -1.765 | -0.436 | -0.649 | 51 | 15 | 0 | 0 |
| R5 | Q4 rotation | -1.793 | -0.319 | -0.817 | 45 | 20 | 0 | 0 |
| R5 | Full year | -3.499 | -0.494 | -0.979 | 141 | 107 | 0 | 0 |

### Distribution agrégée des modes

| Variante | Normal total | Capital preservation total | Cash only total | Entrées bloquées total |
| --- | ---: | ---: | ---: | ---: |
| Baseline actuelle | 164 | 254 | 78 | 7188 |
| R1 | 168 | 266 | 62 | 5588 |
| R2 | 168 | 266 | 62 | 5588 |
| R3 | 168 | 266 | 62 | 5588 |
| R4 | 164 | 332 | 0 | 0 |
| R5 | 282 | 214 | 0 | 0 |

### Recommandation finale

- Variante en tête selon les critères A→D : **R5** — Suppression cash_only + triggers désensibilisés.
- Effet moyen du régime sur cette variante : return `-1.371`, Sharpe `-0.291`, amélioration DD `-0.591`.
- Réduction des blocages sur les fenêtres sensibles : Q2 `-1104`, Q4 `-1590`, full year `-3594` vs baseline actuelle (valeur négative = moins de blocages).
- Distribution agrégée des modes pour R5 : normal `282`, capital_preservation `214`, cash_only `0`.
- Classement synthétique observé : `R5, R4, R1, R2, R3`.

### Artefacts de référence

- `ablation_summary.json` et `ablation_decision.md` de chaque variante dans `artifacts/ablation/regime_recalibration_matrix/variants/R{1..5}/`
- `phase2_risk_summary.json` de chaque run `control` pour la lecture des modes
