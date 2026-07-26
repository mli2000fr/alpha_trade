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

### Niveau 2 — Features pondérées par horizon (à faire)

Créer des versions "dédiées" des features clés, taguées par horizon. Le ratio de boost/atténuation vient de l'analyse de corrélation feature→target par horizon.

```
rsi_3_h3_weight   = rsi_3 × 1.5   (boost pour H3)
rsi_3_h10_weight  = rsi_3 × 0.2   (atténué pour H10)
momentum_250_h3   = momentum_250 × 0.1  (presque ignoré en H3)
momentum_250_h10  = momentum_250 × 1.5  (boost pour H10)
```

**Mécanisme** :
1. Après le premier batch avec Niveau 1, extraire l'IC Rank par feature × horizon
2. Pour chaque feature, calculer : `weight_h = IC(feature, target_h) / max(IC(any_feature, target_h))`
3. Générer `feature_h3_weighted`, `feature_h5_weighted`, `feature_h10_weighted`
4. Ajouter ces features pondérées au pipeline

- **Coût** : ~2h
- **Fichiers** : `modelFactory/global_ranking.py`, `modelFactory/features.py`
- **Gain attendu** : H3 IC ~0.012-0.018, H5 IC ~0.005-0.010, H10 IC ~0.010-0.015

### Niveau 3 — Features croisées horizon (à faire)

Créer des features qui capturent la **dynamique temporelle** entre horizons. Ces features décrivent comment le signal évolue dans le temps, pas juste sa valeur instantanée.

```
accel_3_5        = momentum_5 / momentum_3 − 1    (accélération du momentum)
decay_5_10       = momentum_10 / momentum_5 − 1   (essoufflement)
rsi_slope        = rsi_3 − rsi_14                 (vitesse de changement du RSI)
vol_expansion    = vol_5 / vol_20 − 1             (explosion de volatilité court-terme)
meanrev_signal   = dist_to_sma_5d − dist_to_sma_20d  (intensité de la réversion)
gap_fade         = overnight_gap × (1 − abs(rsi_3 − 50) / 50)  (gap + condition de survente/surachat)
```

- **Coût** : ~3h
- **Fichiers** : `modelFactory/features.py` → `INTERACTION_FEATURES` + `compute_features()`
- **Gain attendu** : H3 IC ~0.015-0.025, H5 IC ~0.008-0.015, H10 IC ~0.012-0.020

---

## 🎯 Gain attendu — Résumé

| Horizon | Sans interaction | Niveau 1 (top-K) | Niveau 2 (pondéré) | Niveau 3 (croisé) |
|---------|:---:|:---:|:---:|:---:|
| H3 | IC ~0.008 | ~0.010-0.013 | ~0.012-0.018 | ~0.015-0.025 |
| H5 | IC ~−0.002 | ~0.002-0.005 | ~0.005-0.010 | ~0.008-0.015 |
| H10 | IC ~0.007 | ~0.008-0.012 | ~0.010-0.015 | ~0.012-0.020 |

---

## 🔧 Plan d'implémentation

### Étape 1 : Mesurer (batch à lancer)
- Lancer un batch avec `ranking_top_k_features=30`
- Extraire les IC par feature × horizon depuis les logs
- Identifier quelles features sont utiles pour quel horizon

### Étape 2 : Niveau 2 (si IC H3 < 0.02 après Niveau 1)
- Générer les poids à partir des IC mesurés
- Ajouter les features pondérées
- Relancer un batch

### Étape 3 : Niveau 3 (si IC H3 < 0.03 après Niveau 2)
- Ajouter les 6-8 features croisées horizon
- Relancer un batch

---

## 📝 Notes

- Le Niveau 1 est déjà en production. Le Niveau 2 nécessite d'abord un batch complet pour mesurer les IC par feature.
- Le Niveau 3 est le plus prometteur mais aussi le plus risqué : les features croisées peuvent introduire du bruit si mal conçues.
- Priorité absolue : améliorer H3 (seul horizon structurellement positif). Si H3 décolle, H5 et H10 suivront par propagation du stacking.
