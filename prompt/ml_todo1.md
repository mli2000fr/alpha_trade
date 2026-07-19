# Analyse du batch `model-factory-20260718005650-ce3035`

## 1. Vue d'ensemble

Le batch a entraîné **199 symboles** (1 échec) sur 2018-2025 en walk-forward avec 3 modèles : **LSTM_attention** (baseline), **LightGBM** et **CatBoost**. La tâche est une classification **ternaire** (short / flat / long) avec un horizon de 10 jours.

## 2. 🏆 Classement des modèles (Walk-Forward, le split qui compte)

| Modèle | F1 Macro | F1 Short | F1 Flat | F1 Long |
|--------|----------|----------|---------|---------|
| **LightGBM** | **0.308** | **0.343** | 0.167 | 0.413 |
| CatBoost | 0.301 | 0.329 | 0.148 | **0.426** |
| LSTM_attention | 0.250 | 0.246 | **0.200** | 0.304 |

**LightGBM est le meilleur modèle global**, talonné par CatBoost. Le LSTM_attention est nettement en retrait (-19% vs LightGBM en F1 macro). Les modèles tree-based (GBM) dominent clairement le deep learning sur ce problème.

## 3. 🚨 Problème majeur : la classe `flat` est catastrophique

C'est **LE** problème central de ce batch :

- **F1_flat** plafonne à **0.20** (LSTM) et descend à **0.148** (CatBoost WF). C'est très faible.
- La classe `flat` représente pourtant **~23% des vrais labels** — ce n'est pas une classe rare.
- Les modèles GBM **sous-prédisent massivement** le flat (13-18% de prédictions flat vs 23% réel), ils sont trop « directionnels ».
- Le LSTM fait l'inverse : il **sur-prédit** le flat (33% vs 23% réel), il est trop « prudent ».

## 4. 📊 Distribution des performances par symbole

La distribution des F1 macro en WF est concentrée dans le bas :

| Bucket F1 | Nb symboles | % |
|-----------|-------------|---|
| 0.10–0.19 | 16 | 5% |
| 0.20–0.29 | **185** | **55%** |
| 0.30–0.39 | 133 | 40% |

- **55% des symboles ont un F1 macro entre 0.20 et 0.29** — c'est médiocre. Un F1 de 0.25 sur une classification à 3 classes, c'est à peine mieux que le hasard (0.33).
- **Aucun symbole n'atteint 0.40** de F1 macro. Le meilleur est AIN à 0.381.
- Seulement 40% des symboles dépassent 0.30, ce qui reste un seuil modeste.

## 5. 🔴 Points d'alerte

- **APH** a un **F1_short = 0** : le modèle n'a jamais réussi à identifier un seul short correct pour ce symbole en walk-forward. C'est un échec complet sur la direction baissière pour ce ticker.
- **COLD** est le pire symbole avec F1_macro = 0.14. Le F1_short est de 0.031 — le modèle est aveugle aux shorts sur ce titre.
- **AVT et AIN apparaissent à la fois dans le top 10 et le bottom 10** → le rapport ne précise pas de quel modèle il s'agit dans ces classements, ce qui est une **lacune du reporting**. C'est probablement le meilleur vs le pire modèle pour chaque symbole, mais ce n'est pas explicite.

## 6. ✅ Points positifs

- **Walk-forward bien configuré** : 504 jours de train minimum (~2 ans), validation 126j, test 126j, 11 splits max. Le protocole est rigoureux.
- **Calibration Platt** activée, ce qui est indispensable pour une décision ternaire propre.
- **LightGBM et CatBoost sont stables** entre val/test/WF : pas de signe d'overfitting majeur (F1 macro val 0.33 → WF 0.308 pour LightGBM, baisse normale de ~7%).
- **F1_long** est correct (0.41-0.43 pour les GBM) : les modèles sont meilleurs pour identifier les hausses que les baisses ou les flats.

## 7. 🎯 Recommandations

### 7.1 Améliorer le F1 `flat`

Les seuils étaient déjà à 0.35/0.35/0.02 dans la commande (le rapport affiche 0.45/0.05 par erreur).

**🥇 Piste A : Remonter le poids de la classe `flat` dans la loss**

Actuellement : `--ternary-weight-flat 0.75` contre `1.0` pour short et long. Le modèle est moins pénalisé quand il se trompe sur le flat → il n'a aucun intérêt à apprendre cette classe.

➡️ **Proposition** : passer `--ternary-weight-flat` à **1.0** (voire 1.25). Le flat est la classe la plus difficile, il faut au minimum lui donner le même poids qu'aux autres.

**🥈 Piste B : Élargir la bande `flat` du target**

Actuellement `--target-up-threshold 0.02 --target-down-threshold -0.02` : sur 10 jours, un rendement entre -2% et +2% est considéré comme flat. C'est une bande très étroite. Beaucoup de jours classés `short` ou `long` sont en réalité proches de 0 et rendent la frontière floue.

➡️ **Proposition** : tester `--target-up-threshold 0.03 --target-down-threshold -0.03` (bande de ±3%), quitte à rétrécir ensuite si c'est trop large.

**🥉 Piste C : Vérifier l'effet de la calibration Platt**

La calibration Platt peut « écraser » les probas vers les extrêmes (0 ou 1), rendant difficile d'atteindre la zone `flat` (proba max < 0.35 sur les 3 classes). À investiguer : désactiver la calibration (`--calibration-method none`) sur un petit échantillon pour voir si le F1_flat remonte.

### 7.2 LSTM par défaut + `--select-champion`

Avec `--select-champion`, le système évalue chaque modèle sur la validation walk-forward et sélectionne automatiquement le meilleur par symbole. Même si LSTM est `--default-champion`, LightGBM sera servi en prédiction pour les symboles où il est meilleur. Le fallback LSTM ne s'applique que si LightGBM/CatBoost échouent les gates de qualité ou sont sous quarantaine. ✅ OK, pas de changement nécessaire.

### 7.3 `--ternary-weight-short`

**Garder 1.0 pour l'instant.**

Raisonnement :

| | Pred % WF | True % WF | F1 WF |
|---|---|---|---|
| Short | 38.5% | 36.2% | **0.343** |
| Long | 46.3% | 40.6% | **0.413** |

Le modèle prédit déjà assez de shorts (voire un poil trop). Le F1_short plus faible n'est pas un problème de quantité de prédictions mais de qualité (precision/recall). Augmenter le poids short dans la loss amplifierait la sur-prédiction sans nécessairement améliorer la précision.

Le différentiel short vs long (0.34 vs 0.41) est un phénomène bien connu : les baisses ont des dynamiques différentes (plus rapides, plus brutales, souvent liées à des chocs), ce qui les rend structurellement plus difficiles à anticiper avec un horizon de 10 jours. C'est plus un problème de features que de pondération.

👉 Si test : max **1.15** (hausse modeste de 15%).

### 7.4 Ajouter `model_name` dans les tableaux top/bottom

⚠️ **BUG** : Les requêtes SQL `TOP5_BEST_F1_QUERY`, `TOP5_WORST_F1_QUERY` et `ZERO_F1_SHORT_QUERY` dans `modelFactory/report.py` ne sélectionnent pas `mm.model_name`. Résultat : un même symbole peut apparaître plusieurs fois (une par modèle), ce qui explique AVT et AIN en double dans le rapport.

✅ **FIX** : Ajouter `mm.model_name` dans le SELECT des 3 requêtes dans `modelFactory/report.py`.

⚠️ **À faire aussi** : Mettre à jour l'IHM dans `ihm/pages/ml_diagnostics.py` qui utilise les mêmes requêtes pour l'affichage interactif (les dataframes affichés dans les colonnes best/worst/zero).

### 7.5 Investiguer APH et COLD

**Niveau 1 — Requêtes SQL de diagnostic rapide :**

```sql
-- a) Métriques détaillées par split et par modèle
SELECT mm.model_name, mm.split_name,
       mm.f1_macro, mm.f1_short, mm.f1_flat, mm.f1_long,
       mm.true_short_pct, mm.true_flat_pct, mm.true_long_pct,
       mm.pred_short_pct, mm.pred_flat_pct, mm.pred_long_pct
FROM alpha_trade.model_metrics mm
JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mm.run_id
WHERE mtr.batch_id = 'model-factory-20260718005650-ce3035'
  AND mm.symbol IN ('APH', 'COLD')
ORDER BY mm.symbol, mm.model_name, FIELD(mm.split_name, 'train','val','test','wf');

-- b) Champion sélectionné et raison
SELECT mg.symbol, mg.model_name, mg.selection_mode, mg.selection_score, mg.ineligibility_reason
FROM alpha_trade.model_governance mg
JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mg.run_id
WHERE mtr.batch_id = 'model-factory-20260718005650-ce3035'
  AND mg.symbol IN ('APH', 'COLD')
  AND mg.is_selected_model = 1;

-- c) Matrice de confusion ternaire
SELECT mm.symbol, mm.model_name, mm.split_name,
       mm.confusion_short_short, mm.confusion_short_flat, mm.confusion_short_long,
       mm.confusion_flat_short, mm.confusion_flat_flat, mm.confusion_flat_long,
       mm.confusion_long_short, mm.confusion_long_flat, mm.confusion_long_long
FROM alpha_trade.model_metrics mm
JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mm.run_id
WHERE mtr.batch_id = 'model-factory-20260718005650-ce3035'
  AND mm.symbol IN ('APH', 'COLD')
  AND mm.split_name = 'wf';
```

**Niveau 2 — Qualité des données :**

```sql
SELECT symbol, COUNT(*) AS nb_bars, MIN(bar_date), MAX(bar_date)
FROM alpha_trade.stock_bars_daily
WHERE symbol IN ('APH', 'COLD')
  AND bar_date BETWEEN '2018-01-01' AND '2025-12-31'
GROUP BY symbol;
```

**Niveau 3 — Inspection qualitative :**

- **COLD** (Americold Realty Trust) : une REIT (immobilier logistique froid). Les REITs ont des dynamiques très corrélées aux taux d'intérêt, ce qui peut rendre la prédiction technique à 10j très difficile.
- **APH** (Amphenol) : un industriel avec F1_short = 0. Soit le modèle ne prédit jamais short (pred_short_pct ≈ 0), soit il en prédit mais se trompe systématiquement.

## 📋 Résumé des actions

| # | Action | Détail |
|---|--------|--------|
| 1 | **Monter `--ternary-weight-flat` à 1.0** | Priorité n°1 — le flat est sous-pondéré dans la loss |
| 2 | **Garder LSTM + select-champion** ✅ | OK, pas de changement |
| 3 | **Garder `--ternary-weight-short` à 1.0** | Pas le problème principal ; si test : max 1.15 |
| 4 | **`model_name` ajouté aux requêtes top/bottom** | Fait dans `report.py` + à faire dans `ml_diagnostics.py` |
| 5 | **Investiguer APH/COLD** | Commencer par les requêtes SQL Niveau 1 |
