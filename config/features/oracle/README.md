# Campagne d'ablation Oracle Extreme — 2026-09-04

Le témoin est `oracle.json` : O0 canonique, 168 features, sans `global_rank_20`. Tous les profils `ablation_*.json` sont des sous-ensembles ordonnés de ce témoin. Ils conservent la même cible, le même horizon et les mêmes options de génération hors nécessité technique explicite.

## Règle expérimentale

Lancer chaque profil avec exactement le même univers, les mêmes dates, les mêmes folds Walk-Forward, la même seed et les mêmes hyperparamètres. Dans la page Pipeline, désactiver le bundle directionnel, activer Oracle Extreme, puis choisir le profil dans « Features du modèle Oracle Extreme ».

Ne pas modifier simultanément la calibration, les seuils, la liquidité, l'univers ou les fenêtres. `calibration: none` reste le témoin : cette campagne mesure les features, pas la calibration des probabilités.

## Profils

| Profil | Question testée |
|---|---|
| `oracle.json` | Baseline O0 complète |
| `ablation_01_no_xs_ranks.json` | Les rangs cross-sectionnels apportent-ils un gain ? |
| `ablation_02_xs_ranks_only.json` | Les rangs suffisent-ils presque seuls ? |
| `ablation_03_raw_simple.json` | Un socle brut plus simple généralise-t-il mieux ? |
| `ablation_04_no_momentum_returns.json` | Quelle dépendance aux rendements/momentum ? |
| `ablation_05_no_trend_position.json` | Quelle valeur pour tendance et position du prix ? |
| `ablation_06_no_volatility_range.json` | Quelle valeur pour volatilité et ranges ? |
| `ablation_07_no_volume_flow.json` | Quelle valeur pour volume et flux ? |
| `ablation_08_no_rsi_mean_reversion.json` | Quelle valeur pour RSI et mean-reversion ? |
| `ablation_09_no_market_relative_regime.json` | Quelle valeur pour marché, force relative et régime ? |
| `ablation_10_no_engineered_transforms.json` | Les transformations complexes généralisent-elles ? |
| `ablation_11_no_temporal_zscores.json` | Les z-scores temporels améliorent-ils la stabilité ? |

## Vague 2 — combinaisons issues des résultats

La synthèse chiffrée est conservée dans `RESULTATS_CAMPAGNE_20260904.md`. Les trois profils suivants combinent uniquement les retraits favorables de la première vague :

| Profil | Question testée |
|---|---|
| `combined_12_no_market_regime_no_engineered.json` | Le gain A09 se cumule-t-il avec le retrait des transformations complexes A10 ? |
| `combined_13_no_market_regime_no_momentum.json` | Le gain A09 se cumule-t-il avec le retrait momentum/rendements A04 ? |
| `combined_14_no_market_regime_no_engineered_no_momentum.json` | Une version compacte réunissant A09+A10+A04 conserve-t-elle la précision du TOP20 ? |

## Résultats à conserver par batch

Comparer prioritairement : `precision@10%`, lift contre la prévalence, recall@10%, AUC, monotonie des déciles, moyenne et minimum par fold, dispersion entre folds, nombre de folds valides et nombre de features effectif. Une ablation n'est favorable que si son gain est stable sur plusieurs folds ; une moyenne supérieure due à un seul fold ne suffit pas.

Après cette première vague, ne combiner que les familles dont le retrait améliore ou ne dégrade pas les résultats. Le profil compact final devra ensuite être réentraîné une seule fois sur un holdout non utilisé pour choisir les ablations.

Les fichiers sont régénérables avec `scripts/generate_oracle_ablation_profiles.py`.
