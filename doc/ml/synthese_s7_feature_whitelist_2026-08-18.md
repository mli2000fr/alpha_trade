# S7 — Feature whitelist per-symbol : mécanisme implémenté, expérience NO-GO

**Date** : 2026-08-18
**Statut** : ❌ NO-GO (piste fermée proprement — l'infrastructure reste disponible, désactivée par défaut)
**Modèles de référence** : B25 (Global Ranking) gelé ; BL (comportement legacy per-symbol) reste la référence.

---

## 1. Objectif et hypothèse

Permettre, dans le pipeline d'entraînement **per-symbol** de modelFactory, un mécanisme de
**feature whitelist** : lancer des expériences avec un **sous-ensemble explicite de features**,
pour tester si un set « features directionnelles » généralise mieux que le set complet actuel.

Hypothèse testée : *les 9/12 features directionnelles améliorent-elles la prédiction de la
direction hors échantillon, par rapport au set actuel (18 features) ?*

**Contrainte majeure (règle d'or)** : whitelist OFF ou vide = comportement legacy **strictement inchangé**.
whitelist ON = seules les features listées sont utilisées comme X.

---

## 2. Mécanisme implémenté (validé, conservé comme capacité expérimentale)

### 2.1 Ce qui a été ajouté
- **`DataConfig`** : `feature_whitelist_enabled: bool = False`, `feature_whitelist: tuple[str, ...] = ()`
  (+ `force_v1_lstm: bool = True` — voir 2.3).
- **`features.apply_feature_whitelist(full_columns, whitelist)`** : filtrage final de X, dédup + ordre
  whitelist, **validation stricte** (feature inconnue → `ValueError`, fail-fast).
- **`get_feature_columns` / `fingerprint` / `build_feature_contract` / `validate_feature_contract`** :
  paramètres whitelist ; `enabled + vide` → `ValueError("Feature whitelist enabled but empty.")`.
- **Contrat de features** : ajoute `feature_whitelist: {enabled, features}` ; le fingerprint inclut la whitelist.
- **CLI** : `--feature-whitelist-enabled`, `--feature-whitelist a,b,c`, `--no-force-v1-lstm`.
- **Training per-symbol** : X final = whitelist ; log `Feature whitelist: ENABLED/DISABLED — feature_count=N`.
- **Prédiction** : `_load_data_cfg_from_payload`, `_check_feature_contract`, `_prepare_prediction_frame`,
  tabular/LSTM → la whitelist est reconstruite et appliquée (contrat strict, fail-fast sur mismatch).

### 2.2 Règle d'or respectée (vérifiée)
- Whitelist OFF → **exactement** le legacy (vérifié : 18 features, contract valide, prédiction sans mismatch).
- Whitelist ON → uniquement les features listées.

### 2.3 Points architecturaux découverts/corrigés
1. **Le LSTM per-symbol force `feature_set="v1"`** (Cause 2 — input dim) quand whitelist OFF
   → c'est pourquoi la prod persistait v1 (18 feats) malgré `--feature-set expert`.
   Whitelist ON → bypass → expert respecté. Flag opt-in `--no-force-v1-lstm` (défaut = prod).
2. **Gating volume** : `include_volume_features` ne prend effet QUE si whitelist ON.
   Whitelist OFF → volume ignoré per-symbol (legacy 18 exact) ; whitelist ON → volume dans le pool.
   Sans ce gate, whitelist OFF passait 18 → 28 (violation règle d'or).
   Appliqué aux 16 sites per-symbol/predictor (dataset, orchestrator, trainer, predictor, tabular_baseline).
   PAS centralisé dans `get_feature_columns` (les chemins global/per-sector passent volume sans whitelist).
3. **Challengers LSTM/LightGBM/CatBoost** : la whitelist s'applique uniformément aux 3 architectures.

### 2.4 Tests
- `tests/test_model_factory_feature_whitelist.py` → **17 tests passent** (règle d'or, fail-fast, contract,
  fingerprint, dataset, backward-compat, gating volume, forçage v1).
- Zéro régression : échecs préexistants features/orchestrator/trainer prouvés hors S7 (git stash).

---

## 3. Expériences (méthodologie)

| Run | Expérience | Features | Whitelist | Symboles | Entraînement | Résultat |
|-----|-----------|----------|-----------|----------|--------------|----------|
| Run 1 (bl) | Baseline | **18** (v1+short+factors) | OFF | 40 → 39 (CRBG exclu) | ≤ 2024-12-31 | 40/40 |
| Run 2 (dc) | Directional Core | **9** (momentum/RS/sector/short) | ON | 39 | ≤ 2024-12-31 | 39/40 |
| Run 3 (dv) | Directional + Volume | **12** (+3 volume) | ON | 39 | ≤ 2024-12-31 | 39/40 |

- **39 symboles communs** = univers prod du batch `model-factory-20260815143700-11a25e` (40) moins **CRBG**
  (skippé dc/dv : insuffisance de données avec features cross/whitelist).
- **2025 et 2026 préservés comme OOS** (entraînement ≤ 2024-12-31) — deux périodes indépendantes.
- Flags parité production (H20, target-excess-vs-spy, seeds, walk-forward, challengers, select-champion).
- Liste A (9) : momentum_5/10/20/60, relative_strength_20/60, stock_vs_sector_ret_20/60, selector_short_score.
- Liste B (12) = A + up_volume_ratio_20, volume_price_corr_20, obv_slope_20.

---

## 4. Résultats in-sample (S7-A architecture contrôlée, S7-B pipeline)

### S7-A — Effet features à architecture contrôlée (IS, 39 symboles)
| Architecture | Métrique | BL | DC | DV | DC−BL | DV−BL |
|---|---|---|---|---|---|---|
| LSTM | selection_score | 0.516 | 0.501 | 0.470 | −0.015 | −0.046 |
| LSTM | **IC in-sample** | **+0.052** | **−0.014** | **+0.010** | −0.092 | −0.068 |
| LightGBM | dacc | 0.490 | 0.512 | 0.512 | +0.022 | +0.022 |
| LightGBM | test_f1 | 0.297 | 0.328 | 0.321 | +0.031 | +0.024 |
| CatBoost | dacc | 0.494 | 0.517 | **0.540** | +0.023 | **+0.046** |
| CatBoost | test_f1 | 0.301 | 0.335 | **0.347** | +0.034 | **+0.046** |

**Lecture IS** : la whitelist **aide les modèles tabulaires** (surtout CatBoost : DV > DC → le volume
contribue), mais **dégrade le LSTM** (selection_score + IC). Le champion diffère entre runs pour
**29/39 symboles** → l'architecture n'est PAS constante entre runs (confondant à contrôler).

### S7-B — Pipeline réel (champion sélectionné par selection_score)
| Métrique champion | BL | DC | DV | BL→DC | BL→DV |
|---|---|---|---|---|---|
| selection_score | 0.513 | 0.504 | 0.485 | −0.008 | −0.028 |
| test_f1 | 0.297 | **0.322** | 0.312 | +0.025 | +0.015 |
| dacc | 0.499 | **0.521** | 0.509 | +0.022 | +0.011 |

- **DC (9) est le meilleur champion en accuracy IS** ; **DV ≤ DC** (le volume n'ajoute pas au pipeline).
- **Divergence `selection_score` vs f1/dacc** : `selection_score` classe BL en tête alors que DC fait
  mieux en f1/dacc → `selection_score` est **mal aligné** avec l'objectif directionnel
  (diagnostic oracle S7-B-B). **On ne le modifie pas** (ce serait une nouvelle optimisation).

---

## 5. Résultats OOS 2025/2026 (S7-C) — le test décisif

### S7-C-B — Champion (IC = moyenne per-symbol du Spearman, 39 symboles)
| Période | BL IC | DC IC | DV IC | DC−BL | DV−BL |
|---|---|---|---|---|---|
| 2025H1 | **0.139** | 0.052 | 0.031 | **−0.087** | −0.108 |
| 2025H2 | 0.006 | −0.014 | 0.052 | −0.020 | +0.046 |
| 2026H1 | 0.052 | **0.107** | 0.077 | **+0.056** | +0.026 |
| **ALL** | **0.029** | 0.019 | 0.034 | **−0.009** | +0.006 |

### S7-C-A — Par architecture (IC moyen)
- **LSTM** : 2025H2 DC−BL +0.062 ; 2026H1 DC−BL +0.128 (DC=0.218) ; 2025H1 −0.006. DV < DC.
- **LightGBM** : 2025H2 DV−BL +0.066 ; 2026H1 +0.030 ; 2025H1 DC−BL −0.048. DV ≈ DC.
- **CatBoost** : ALL DC−BL −0.027, DV−BL −0.033 (BL 0.048 > DC 0.021 > DV 0.015) —
  **l'amélioration CatBoost IS s'effondre OOS**.

### DC vs DV (diagnostic clé)
- ALL champion : DV−DC IC = +0.015, dacc +0.024 → **le volume n'apporte rien de décisif OOS**.
- LSTM 2026H1 : DC (0.218) > DV (0.127) → le volume dégrade même le meilleur cas.

---

## 6. Verdict — ❌ NO-GO

Selon les 4 critères de décision :
1. **Amélioration à architecture contrôlée** : **incohérente** (LSTM DC bon en 2025H2/2026H1,
   CatBoost mauvais partout, signes qui s'inversent).
2. **Amélioration pipeline complet** : **non** — champion ALL IC DC−BL **−0.009** ; le +0.022 dacc IS
   **disparaît OOS**.
3. **Persistance temporelle** : **faible** — champion DC−BL = −0.087 (H1'25) → −0.020 (H2'25) →
   +0.056 (H1'26) : signe instable, pas « plusieurs sous-périodes ».
4. **Dégradation catastrophique** : pas de dégradation massive, mais **aucun gain fiable**.

**Règle appliquée** : « Si l'amélioration n'existe qu'en IS et disparaît OOS → NO-GO, sans chercher à
sauver le modèle. » Aucun tuning supplémentaire (pas de nouvelle whitelist, pas de nouveau seuil,
pas de modification de `selection_score`, pas de tuning CatBoost/LSTM).

**BL / comportement legacy reste la référence.**

### Points démontrés par S7 (résultat négatif utile)
- Une simple whitelist de features « supposées pertinentes » **ne suffit pas** à créer un signal
  directionnel robuste.
- L'amélioration IS (surtout CatBoost dacc 0.494 → 0.540) **ne survit pas à l'OOS**.
- Le volume (3 features) : **aucune preuve** d'alpha directionnel stable.
- LSTM DC 2026H1 (IC 0.218) : cas intéressant mais **isolé et contradictoire avec IS** → ne pas
  investiguer (risque de boucle d'overfitting).

---

## 7. Infrastructure conservée (capacité expérimentale, désactivée par défaut)

Le mécanisme de **whitelist conditionnelle reste techniquement valide** et est conservé :
- whitelist **OFF** (défaut) → comportement legacy strictement inchangé ;
- whitelist **ON** → feature-set directionnel explicite.

Cela permet de tester proprement une **future hypothèse** sans risque de modifier la production
par accident. La production (B25 gelé, BL legacy) n'est PAS affectée.

---

## 8. Décision et prochaine étape

**Décision** : S7 fermé (NO-GO). BL = référence. Infrastructure S7 conservée (opt-in, désactivée).

**Prochaine étape** : construire un **vrai signal directionnel per-symbol** avec une méthodologie
plus stricte dès le premier run :
- **B25 global ranking** = sélection du contexte/titre ;
- **per-symbol directionnel** = prédiction du mouvement futur, avec un **feature set spécifiquement
  construit pour la direction** ;
- **validation temporelle stricte dès le départ** (mêmes règles que S7 : OOS indépendant, BL en
  contrôle obligatoire dans chaque expérience) ;
- pas de départ « 50 nouvelles features » : approche structurée (compression/expansion de volatilité,
  ADX/trend strength, distance aux moyennes, price action, relative strength, anomalies de volume —
  mais S7 montre qu'une simple whitelist ne suffit pas : il faut construire + valider temporellement).

---

## 9. Références

- Scripts : `scripts/s7_analyse_in_sample.py`, `scripts/s7_analyse_s7a.py`, `scripts/s7_analyse_s7b.py`,
  `scripts/s7_oos_predict.py`, `scripts/s7_analyse_s7c.py`.
- Artifacts : `artifacts/models_s7_{bl,dc,dv}/`, `artifacts/s7_in_sample/`, `artifacts/s7_oos/`.
- Tests : `tests/test_model_factory_feature_whitelist.py` (17 pass).
- Modifications : `modelFactory/config.py`, `features.py`, `dataset.py`, `orchestrator.py`, `cli.py`,
  `predictor.py`, `trainer.py`, `tabular_baseline.py`.
- Mémoire : `/memories/repo/s7_feature_whitelist_2026-08-18.md`, `/memories/session/s7_feature_whitelist.md`.
