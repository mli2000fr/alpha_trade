# 📐 Interactions × Horizon — Conception & Roadmap

> **Date** : 2026-07-26
> **Objectif** : Documenter la stratégie d'interactions features × horizon pour le Global Ranking Model.
> **Statut** : Niveau 1 fait (feature selection). Niveaux 2 et 3 à implémenter.

---

## 🧠 Le problème

Aujourd'hui, les **mêmes 164 features** sont utilisées pour prédire H3, H5 et H10. Or le marché fonctionne à des échelles de temps différentes :

```
H3 (3 jours)  →  réversion court-terme, microstructure, gaps
H5 (5 jours)  →  momentum hebdo, flux de volume
H10 (10 jours) → momentum moyen-terme, tendance sectorielle, fondamentaux
```

Une feature comme `rsi_3` est **excellente pour H3** (survente → rebond dans 3j) mais **bruit pur pour H10** (le RSI d'aujourd'hui ne dit rien sur le rendement dans 2 semaines). Forcer le modèle H10 à digérer `rsi_3`, c'est lui injecter du bruit.

---

## 📊 Les 3 niveaux d'interaction

### Niveau 1 — Feature Selection par horizon ✅ (déjà fait)

Chaque horizon a sa propre liste de features importantes. H3 sélectionne ses top-30, H5 les siennes, H10 les siennes.

- **Implémentation** : `ranking_top_k_features` dans `config.py` + `_compute_mean_importance()` dans `global_ranking.py`
- **Fichiers** : `modelFactory/config.py`, `modelFactory/global_ranking.py`
- **Coût** : déjà fait
- **Gain** : modeste (+0.002-0.005 IC)

### Niveau 2 — Features pondérées par horizon ❌ SKIP (inutile pour GBDT)

Créer des versions pondérées par un scalaire :

```
rsi_3_h3_weight  = rsi_3 × 1.5   (boost pour H3)
rsi_3_h10_weight = rsi_3 × 0.2   (atténué pour H10)
```

**Pourquoi c'est inutile :** Les arbres de décision (LightGBM, XGBoost, CatBoost) sont **invariants aux transformations monotones** ($f(x) = a \cdot x + b$ avec $a > 0$). Multiplier une feature par 1.5 ne change pas les splits optimaux — l'arbre trouvera exactement la même structure. Le Niveau 1 (top-K par horizon via importance) remplit déjà ce rôle de filtrage, sans ajouter de colonnes inutiles.

> ⚠️ Cette technique fonctionnerait pour un modèle linéaire (Ridge/Lasso), mais pas pour des GBDTs.

- **Statut** : ❌ Abandonné
- **Raison** : Invariance mathématique des arbres de décision
- **Coût évité** : ~2h

### Niveau 3 — Features croisées horizon 🚀 PRIORITAIRE

Créer des features qui capturent la **dynamique temporelle** (vitesse, accélération, convexité). En finance quantitative, la valeur instantanée d'un indicateur ($RSI=70$) contient moins de signal que sa **dynamique** ($RSI$ en train de chuter vs en train de monter).

```
accel_3_5        = momentum_5 / momentum_3 − 1    (accélération du momentum)
decay_5_10       = momentum_10 / momentum_5 − 1   (essoufflement)
rsi_slope        = rsi_3 − rsi_14                 (vitesse de changement du RSI)
vol_expansion    = vol_5 / vol_20 − 1             (explosion de volatilité court-terme)
meanrev_signal   = dist_to_sma_5d − dist_to_sma_20d  (tension de réversion vs tendance de fond)
gap_fade         = overnight_gap × (1 − abs(rsi_3 − 50) / 50)  (gap × condition de survente/surachat)
```

**Pourquoi ça marche :** Ces features sont **non-linéaires et non-monotones** par rapport aux features sources. Un arbre ne peut pas les recréer par simple split. Elles apportent une information réellement nouvelle.

- **Coût** : ~1h30
- **Fichiers** : `modelFactory/features.py` → `TEMPORAL_DYNAMICS_FEATURES` + `compute_features()`
- **Gain attendu** : H3 IC ~0.015-0.025, H5 IC ~0.008-0.015, H10 IC ~0.012-0.020

---

## 🎯 Gain attendu — Résumé

| Horizon | Sans interaction | Niveau 1 (top-K/horizon) | Niveau 3 (croisé) |
|---------|:---:|:---:|:---:|
| H3 | IC ~0.008 | ~0.009-0.013 | ~0.015-0.025 |
| H5 | IC ~−0.002 | ~0.002-0.005 | ~0.008-0.015 |
| H10 | IC ~0.007 | ~0.004-0.008 | ~0.012-0.020 |

---

## 🔧 Plan d'implémentation

### Étape 1 : Niveau 1 ✅ Fait
- [x] `ranking_top_k_features` dans `config.py`
- [x] Per-horizon feature selection (chaque horizon choisit ses propres top-K)
- [x] IHM input dans Pipeline → Paramètres d'exécution

### Étape 2 : ❌ SKIP — Niveau 2 (inutile pour GBDT)
- Les arbres sont invariants aux multiplications par un scalaire

### Étape 3 : 🚀 Niveau 3 — Features de dynamique temporelle (prochaine priorité)
- [ ] Ajouter `TEMPORAL_DYNAMICS_FEATURES` dans `modelFactory/features.py`
- [ ] Implémenter `compute_features()` pour les 6 features croisées
- [ ] Ajouter au `_XS_RANK_SOURCE_FEATURES` dans `global_ranking.py`
- [ ] Lancer un batch avec les nouvelles features

---

## 📝 Notes

- Le Niveau 1 est en production avec per-horizon top-K.
- Le Niveau 2 est définitivement abandonné (invariance mathématique des GBDT — Gemini a raison).
- **Le Niveau 3 est la prochaine étape à fort potentiel.** Les features de pente/convexité capturent la dynamique que les arbres ne peuvent pas inférer de features statiques.
- Priorité absolue : améliorer H3. Si H3 décolle, H5 et H10 suivront.
