# Ablation propre ML vs régime

Ce document décrit le protocole standardisé ajouté dans `scripts/run_ml_regime_ablation.py` pour décider **objectivement** quoi garder entre la composante **ML** et la couche **market regime**.

## 1. Ce que le script compare

Le script construit une matrice factorielle **2 × 2** sur plusieurs fenêtres temporelles :

| Variante | ML | Régime |
|---|---|---|
| `control` | ON (`rebuild-missing`) | ON |
| `ml_off` | OFF | ON |
| `regime_off` | ON (`rebuild-missing`) | OFF |
| `ml_off_regime_off` | OFF | OFF |

Cela évite les conclusions trompeuses du type « j’ai coupé deux choses à la fois donc je ne sais pas laquelle a aidé ».

## 2. Garanties de comparabilité

Le protocole fige explicitement :

- `engine_mode=pipeline`
- `phase2_mode=risk_execution`
- `phase3_mode=execution_replay`
- `phase4_mode=protection_replay`
- `phase5_mode=watcher_replay`
- `phase7_mode=exit_lifecycle_replay`
- `capital_preset_key=capital_0_2000`
- coûts d’exécution (`commission_bps`, `slippage_bps`)
- overlays de risque importants (`max_entry_gap_pct`, `max_sector_exposure_pct`, `max_portfolio_dd_pct`, `target_annual_vol`, etc.)

Le script **fige aussi la configuration runtime** dans `output_root/configs/` :

- `baseline.runtime.yaml`
- `regime_off.runtime.yaml`

Ainsi, même si `config.yaml` change plus tard, l’ablation reste reproductible.

## 3. Fenêtres par défaut

Preset par défaut : `core_2020`

- `2020_q1_crash`
- `2020_q2_rebound`
- `2020_q3_momentum`
- `2020_q4_rotation`
- `2020_full_year`

Preset alternatif : `cross_cycle`

- `2020_q1_crash`
- `2020_q2_rebound`
- `2022_h1_bear`
- `2022_h2_bottom`
- `2023_h1_recovery`

Vous pouvez aussi fournir vos propres fenêtres via `--windows-file`.

## 4. Commandes

### Préparer le plan uniquement

```powershell
python -m scripts.run_ml_regime_ablation --output-root artifacts/ablation/ml_regime_objective
```

### Exécuter réellement les runs

```powershell
python -m scripts.run_ml_regime_ablation --execute --skip-existing --output-root artifacts/ablation/ml_regime_objective
```

### Utiliser un preset plus diversifié

```powershell
python -m scripts.run_ml_regime_ablation --execute --skip-existing --window-preset cross_cycle --output-root artifacts/ablation/ml_regime_cross_cycle
```

## 5. Fichiers produits

Dans `output_root/` vous obtiendrez notamment :

- `ablation_plan.json` : manifest complet des runs
- `run_all.ps1` : script PowerShell prêt à relancer manuellement
- `ablation_runs.csv` : vue tabulaire de tous les runs trouvés
- `ablation_summary.json` : synthèse machine-readable
- `ablation_decision.md` : lecture décisionnelle
- `run_overview.json` : résumé rapide de l’état global

Chaque run écrit dans :

- `output_root/runs/<window_id>/<variant_id>/report.json`
- `output_root/runs/<window_id>/<variant_id>/fidelity_manifest.json`
- `output_root/runs/<window_id>/<variant_id>/phase2_risk_summary.json`

## 6. Comment lire la décision

Le rapport calcule trois familles d’effets :

### Effet `ml_mode=off`

- **positif** : couper le ML actuel aide la métrique
- **négatif** : garder le ML aide la métrique

### Effet régime ON

- **positif** : garder le régime aide la métrique
- **négatif** : couper le régime aide la métrique

### Synergie du combo

- **positive** : le combo se comporte mieux que la somme naïve des effets isolés
- **négative** : interaction défavorable, donc prudence avant de couper les deux en même temps

## 7. Interprétation recommandée

- Si `ml_off` améliore **majoritairement** `return` et `Sharpe`, et que les runs ML ON sont souvent `degraded`, alors la bonne décision opérationnelle est de **désactiver le ML actuel** dans la baseline tant qu’une nouvelle version n’est pas prête.
- Si le régime améliore surtout le drawdown mais pas le rendement, il faut plutôt **recalibrer** que supprimer.
- Si le régime dégrade à la fois rendement et Sharpe sur plusieurs fenêtres, il est probablement **sur-filtrant**.

## 8. Prochaine étape conseillée

1. lancer le preset `core_2020` pour obtenir vite une première décision propre ;
2. si le verdict semble stable, relancer avec `cross_cycle` ;
3. seulement ensuite décider de :
   - garder `ml_mode=off` en baseline,
   - recalibrer ou retirer `market_regimes`,
   - ou réintroduire le ML après amélioration de couverture / qualité.

