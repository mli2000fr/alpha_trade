# Campagne Per-Symbol Directional v2 — F0/F1/F2/F3a/F3b : VERDICT NO-GO (2026-08-19)

## Résumé exécutif

La campagne **Per-Symbol Directional v2** (features directionnelles per-symbol dédiées au swing, opposées au ranking global B25) a été conduite de bout en bout : F0 (baseline legacy) → F1 (Trend/Volatility) → F2 (Momentum/Structure) → F3a (Relative Strength) → F3b (Volume).

**Verdict : 🔴 NO-GO global.** Aucune famille n'apporte d'information directionnelle per-symbol **persistante** au-delà de F0, sur aucune architecture (LSTM / LightGBM / CatBoost), sur aucune sous-période (2025H1 / 2025H2 / 2026H1). Les améliorations observées sont isolées, instables en signe, ou disparaissent dès qu'on consolide. **F3b (Volume) est systématiquement la pire famille** (ΔIC négatif sur les 4 architectures).

Ce résultat est cohérent avec l'antécédent S7 (whitelist sans gain OOS), Oracle S8 et TP C : **le per-symbol directionnel ne généralise pas hors échantillon** ; aucune optimisation post-NO-GO n'est autorisée (règle de gouvernance, §10).

---

## 1. Fingerprint F0 (référence absolue)

F0 = **legacy exact** du per-symbol actuel, whitelist OFF, intouchable.

- **Run de référence** : `model-factory-20260818161922-d7d984` (S7 bl), artifacts `artifacts/models_s7_bl/`
- **Manifest** : `artifacts/per_symbol_v2/f0_manifest.json`
  - `f0_fingerprint = 2135c54c60c71d53`
  - `feature_fingerprint = b091824b9932a002`
  - `feature_set = "v1"`, `feature_count = 18`, whitelist OFF
- **39 symboles communs** = 40 prod − CRBG (exclu de la campagne)
- **Target** : regression, horizon 20, seuils ±3 %, excess vs SPY, vol-scaled (inchangée pendant toute la campagne)
- **Modèles** : LSTM attention + LightGBM + CatBoost (`--select-champion`, `--enable-catboost`, `--compare-lightgbm`), walk-forward 8 splits, train ≤ 2024-12-31 (2025+2026 = OOS)

> ⚠️ Le fingerprint F0 est la pierre de touche : **tout run campagne qui ne diffère QUE par sa whitelist** (même target, archis, hyperparams, seeds, split temporel, contract) est comparable proprement à F0.

---

## 2. Définition exacte F1 / F2 / F3a / F3b

Toutes les familles sont des **whitelists** appliquées via le mécanisme S7 (X = exactement les features listées, feature_set=expert, aucune autre feature dans l'input modèle). Implémentation : `modelFactory/features.py` (constantes `DIRECTIONAL_FEATURE_COLUMNS`, `DIRECTIONAL_F2_FEATURE_COLUMNS`, `DIRECTIONAL_F3A_FEATURE_COLUMNS`, `DIRECTIONAL_F3B_FEATURE_COLUMNS` ; calcul PIT sur prix ajustés) et `modelFactory/cross_sectional.py` (variantes 5j sectorielles).

| Famille | Features (whitelist exacte) | n | Fingerprint | Flag requis |
|---|---|---|---|---|
| **F1** Trend/Volatility | `adx_14, atr_ratio_5_20, atr20_pct, ema20_slope_10, ema50_slope_20, distance_ema20, distance_ema50` | 7 | `02e7e251039ed1ea` (feature `225cc2579c5c1da2`) | — |
| **F2** Momentum/Structure | F1 + `range_position_20, return_2d, return_5d, return_10d, return_20d, range_position_50, distance_high_20, distance_low_20, body_range, close_location_value` | 17 | `97e816074410e6ee` | — |
| **F3a** Relative Strength | `relative_strength_5, relative_strength_20, relative_strength_60, stock_vs_sector_ret_5, stock_vs_sector_ret_20, stock_vs_sector_ret_60` | 6 | `3c917686d57a7cd5` | `--enable-cross-sectional` |
| **F3b** Volume | `volume_ratio_20, volume_zscore_20, obv_slope_20, cmf_20` | 4 | `45abcca59c9ac5f4` | `--include-volume-features` |

Définitions économiques (PIT, normalisées, indépendantes du niveau de prix) :

- **F1** — force de tendance (ADX 14), compression/expansion de volatilité (ATR5/ATR20), volatilité normalisée (ATR20/close), pentes EMA (20/10j, 50/20j), distances close→EMA20/50.
- **F2** — momentum simple (retours 2/5/10/20j), position dans le range 50j, distance au high/low 20j **précédents** (shiftés, PIT strict), géométrie de bougie (body/range, close location).
- **F3a** — force relative au marché SPY (5/20/60j) et au secteur (5/20/60j) : « le titre est-il réellement fort/faible relativement à son environnement ? »
- **F3b** — volume/SMA20, z-score volume 20j, pente OBV 20j, Chaikin Money Flow 20j.

Runs : `artifacts/psv2_f1` (`…193414-b43139`), `psv2_f2` (`…200840-c1f256`), `psv2_f3a` (`…200855-db8b99`), `psv2_f3b` (`…200911-541e15`) — 39/39 symboles, Completed 39 / Skipped 0 / Failed 0.

---

## 3. Matrice complète des résultats

Métrique principale : **ΔIC vs F0** (différence d'IC moyen par symbole, Spearman score vs future_return, OOS 2025/2026, 39 symboles). Une cellule > 0 = la famille améliore F0 sur cette (architecture × période).

### ΔIC vs F0 — consolidé (ALL, n=12 948)

| Famille | LSTM | LightGBM | CatBoost | Champion |
|---|---|---|---|---|
| **F1** Trend/Vol | **−0.0094** | +0.0026 | +0.0071 | −0.0093 |
| **F2** Momentum/Structure | −0.0468 | +0.0042 | +0.0137 | −0.0276 |
| **F3a** Rel. Strength | −0.0137 | −0.0195 | −0.0010 | +0.0026 |
| **F3b** Volume | **−0.0399** | **−0.0519** | **−0.0547** | **−0.0476** |

→ Aucun ΔIC consolidé n'est robustement positif. **F3b est négatif sur les 4 architectures.**

### Rappel des niveaux absolus (IC mean / dacc / F1macro, ALL)

| run | LSTM IC | LSTM dacc | LGBM IC | LGBM dacc | CB IC | CB dacc | Champ IC | Champ dacc |
|---|---|---|---|---|---|---|---|---|
| f0 | 0.0241 | 0.488 | 0.0589 | 0.477 | 0.0478 | 0.496 | 0.0287 | 0.490 |
| f1 | 0.0147 | 0.491 | 0.0615 | 0.482 | 0.0549 | 0.494 | 0.0194 | 0.491 |
| f2 | −0.0227 | 0.499 | 0.0631 | 0.501 | 0.0615 | 0.508 | 0.0011 | 0.490 |
| f3a | 0.0104 | 0.491 | 0.0394 | 0.516 | 0.0468 | 0.519 | 0.0313 | 0.517 |
| f3b | −0.0158 | 0.498 | 0.0070 | 0.493 | −0.0069 | 0.487 | −0.0188 | 0.475 |

→ **dacc ≈ 0.47–0.52 partout** (proche du hasard), précision LONG/SHORT ≈ 0.43–0.58 sans cohérence directionnelle. Rank IC cross-sectionnel ≈ 0 (souvent négatif). **Aucune information directionnelle démontrée.**

---

## 4. Résultats par architecture (architecture contrôlée)

### LSTM — ΔIC vs F0
| Période | F1 | F2 | F3a | F3b |
|---|---|---|---|---|
| 2025H1 | −0.0333 | +0.0028 | −0.0030 | −0.0186 |
| 2025H2 | +0.1193 | +0.0694 | +0.0340 | −0.0760 |
| 2026H1 | +0.0359 | +0.0149 | **+0.1171** (isolé) | −0.0188 |
| **ALL** | **−0.0094** | −0.0468 | −0.0137 | −0.0399 |

### LightGBM — ΔIC vs F0 (backfill, §7)
| Période | F1 | F2 | F3a | F3b |
|---|---|---|---|---|
| 2025H1 | −0.0921 | −0.0814 | −0.0689 | −0.1362 |
| 2025H2 | +0.0214 | +0.0387 | +0.0286 | −0.0142 |
| 2026H1 | +0.0387 | +0.0116 | +0.0554 | −0.0357 |
| **ALL** | +0.0026 | +0.0042 | −0.0195 | **−0.0519** |

### CatBoost — ΔIC vs F0
| Période | F1 | F2 | F3a | F3b |
|---|---|---|---|---|
| 2025H1 | −0.0720 | −0.0622 | +0.0155 | −0.1088 |
| 2025H2 | +0.0390 | +0.0587 | +0.0445 | +0.0147 |
| 2026H1 | +0.0774 | +0.0633 | +0.0283 | −0.0349 |
| **ALL** | +0.0071 | +0.0137 | −0.0010 | −0.0547 |

### Lecture par famille (architecture-contrôlée)
- **F1** : ≈ 0 en consolidé sur les 3 architectures ; signe instable (H1'25 négatif, H2'25/H1'26 positif). **Pas de signal persistant.**
- **F2** : léger positif sur LightGBM/CatBoost (+0.004/+0.014) mais **négatif LSTM (−0.047)** et 2025H1 négatif. **Pas cohérent entre architectures → non retenu.**
- **F3a** : plat ou négatif (CatBoost −0.001, LightGBM −0.020). Le spike LSTM 2026H1 (+0.117) est **isolé** → même artefact que le LSTM DC 2026H1 de S7. **Non retenu.**
- **F3b** : **négatif sur les 4 architectures et quasi toutes les périodes.** Confirme S7 : le volume n'apporte pas d'alpha directionnel.

---

## 5. Résultats champion

Sélection par `--select-champion` (selection_score = directional accuracy de validation). Mix par run :

| Run | Champion LSTM | Champion CatBoost | Champion LightGBM |
|---|---|---|---|
| F0 | 7 | 13 | **20** |
| F1 | 11 | 28 | — |
| F2 | 8 | 31 | — |
| F3a | 12 | 27 | — |
| F3b | 9 | 30 | — |

### ΔIC vs F0 (champion)
| Période | F1 | F2 | F3a | F3b |
|---|---|---|---|---|
| 2025H1 | −0.1642 | −0.1327 | −0.0572 | −0.1563 |
| 2025H2 | +0.0626 | +0.0404 | +0.0100 | +0.0368 |
| 2026H1 | +0.0489 | +0.0217 | +0.0645 | −0.0293 |
| **ALL** | −0.0093 | −0.0276 | +0.0026 | −0.0476 |

### ⚠️ Facteur de confusion champion
F0 champion = **LightGBM pour 20/40 symboles (50 %)** ; les runs campagne n'ont JAMAIS LightGBM comme champion (jamais entraîné pendant la sélection). → La comparaison « champion » est **biaisée** (deltas très négatifs en 2025H1). La lecture propre est **architecture par architecture** (§4). Le backfill (§7) fournit les scores LightGBM pour l'analyse par architecture mais **ne modifie pas la sélection champion** des runs campagne.

---

## 6. Résultats temporels (stabilité)

Test central de la campagne : une famille n'est retenue que si son ΔIC est positif sur **plusieurs périodes indépendantes** (2025H1, 2025H2, 2026H1).

- **F1** : signe instable sur les 3 architectures (H1'25 négatif). ❌
- **F2** : H1'25 négatif sur 3/4 architectures. ❌
- **F3a** : positif uniquement à partir de H2'25, consolidé plat/négatif ; spike isolé LSTM H1'26. ❌
- **F3b** : négatif sur la majorité des (architecture × période). ❌

**Aucune famille ne satisfait la persistance temporelle.** C'est exactement le filtre qui a tué Oracle S8 et TP C (§9).

---

## 7. Backfill LightGBM (correction d'anomalie)

**Anomalie** : les 4 runs campagne ont été lancés **sans `--compare-lightgbm`** → `baseline.enabled=False` → aucun modèle LightGBM persisté (seuls LSTM + CatBoost). Cause : `baseline.enabled = opts.compare_lightgbm` dans `cli.py`.

**Correction** : `scripts/psv2_lightgbm_backfill.py` — ré-entraîne **uniquement** `h20/lightgbm/lightgbm_model.txt` pour chaque symbole, en réutilisant exactement le pipeline :
1. reconstruction du `TrainingConfig` depuis le `config.json` persisté (DataConfig, Model, Calibration, WalkForward, Baseline, Reproducibility seed=42) ;
2. chargement des données comme l'orchestrateur (`_train_worker`) : bars, benchmark SPY, selector, cross-sectional (F3a) jusqu'au `training_end_date` 2024-12-31 ;
3. `SymbolDataModule(...).setup()` → `prepared_df` (features + target, mêmes winsorize/standardize/splits) ;
4. `run_tabular_baseline(model_name="lightgbm", forecast_horizon_override=20, symbol_tag="{sym}_h20")` → même seed dérivé `tabular_baseline/lightgbm/{sym}_h20`, mêmes sample weights.

**Résultat** : 39/39 symboles par run (F1/F2/F3a/F3b). Idempotent (skip si présent). Les scores OOS LightGBM sont désormais dans `artifacts/per_symbol_v2/predictions_oos.parquet` (5 runs × 4 archs × 13 728 = 274 560 lignes) et dans l'analyse (§4).

⚠️ Le backfill **ne modifie pas `architecture_selected`** des runs campagne → le champion reste LSTM/CatBoost (§5).

---

## 8. Antécédents : S7 + S7-C

**S7 — Feature whitelist per-symbol** (2026-08-18) : mécanisme de whitelist additive/rétrocompatible (X = exactement les features listées ; whitelist OFF = legacy strict ; volume gaté sur whitelist ON ; LSTM force v1 quand whitelist OFF). 3 expériences : bl (18 feats WL off), dc (9, WL on), dv (12, WL on). **Verdict NO-GO** : les gains IS (CatBoost dacc 0.494→0.540) disparaissent OOS ; champion ALL IC dc−bl = −0.009 (plat) ; stabilité faible (dc−bl : −0.087 H1'25 → −0.020 H2'25 → +0.056 H1'26). Document : `doc/ml/synthese_s7_feature_whitelist_2026-08-18.md`.

**S7-C — OOS 2025/2026** : IC par symbole (Spearman), dacc, F1 par run × arch × sous-période. C'est le pattern réutilisé pour la campagne v2 (`s7_oos_predict.py`, `s7_analyse_s7c.py` → `psv2_oos_predict.py`, `psv2_analyse.py`).

**Enseignement clé pour la campagne v2** : « une simple whitelist de features ne suffit pas » — la campagne v2 a étendu le test à 4 familles économiques explicites, sans succès non plus.

---

## 9. Faux positifs temporels : Oracle S8 et TP C

Rappel des deux exemples qui ont fondé la règle de validation temporelle :

- **TP C** : très bon résultat dans la fenêtre de recherche, avantage insuffisant sur la période récente → NO-GO.
- **Oracle S8** : `oracle_edge` → qualité du trade : rho ≈ +0.18 sur 2025 (p=0.02), mais **disparaît sur les périodes historiques** (2022 ≈ 0, 2024 ≈ 0, consolidé 583 trades rho = +0.02, p = 0.64) → NO-GO.

**Même signature dans la campagne v2** : les seules cellules « positives » (LSTM F1 H2'25 +0.119, LSTM F3a H1'26 +0.117, CatBoost F1/F2 H1'26 +0.077/+0.063) sont **isolées** et ne survivent pas à la consolidation → non promues.

---

## 10. Règle de gouvernance : aucune optimisation post-NO-GO

Conformément à la règle formelle du projet (établie après TP C et Oracle S8) :

> **Une amélioration doit démontrer une persistance temporelle multi-périodes avant toute promotion. Après un verdict NO-GO, AUCUNE optimisation (tuning de features, de seuils, de target, de seeds, de périmètre) n'est autorisée sur la famille rejetée.**

Application campagne v2 :
- ❌ **Pas de tuning des 7 features F1** après le résultat moyen.
- ❌ **Pas d'ajustement de F3a** pour « sauver » le spike LSTM 2026H1.
- ❌ **Pas d'itération F3 = F2 + F3a + F3b** tant que les familles ne montrent pas de signal stable.
- ✅ F0 reste la référence intouchable ; B25/global ranking gelé ; production intacte.
- ✅ L'infrastructure (whitelist, features F1/F2/F3a/F3b, backfill LightGBM, scripts OOS) reste disponible pour de futures campagnes, sans modification de la production.

**Conclusion finale** : la campagne répond clairement à sa question — *« existe-t-il une information directionnelle per-symbol stable dans les données PIT, indépendante du global ranking ? »* → **NON, pas avec ces familles.** Résultat valide et documenté.

---

## Annexes

- `artifacts/per_symbol_v2/f0_manifest.json` — fingerprint F0
- `artifacts/per_symbol_v2/predictions_oos.parquet` — prédictions OOS (5 runs × 4 archs × 39 symboles)
- `artifacts/per_symbol_v2/rapport_campagne_oos.md` — matrice détaillée (IC, Rank IC, dacc, prec L/S, F1 par arch × période)
- `scripts/psv2_oos_predict.py`, `scripts/psv2_analyse.py`, `scripts/psv2_lightgbm_backfill.py` — scripts de la campagne
- `tests/test_model_factory_directional_v2.py` — tests features F1/F2/F3a/F3b (22 pass + S7)
- Runs : `artifacts/psv2_f1`, `psv2_f2`, `psv2_f3a`, `psv2_f3b` ; référence F0 : `artifacts/models_s7_bl`
