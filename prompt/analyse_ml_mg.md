# 🔬 Analyse Approfondie — Batch `model-factory-20260724094042-7662f8`

> **Date** : 2026-07-24
> **Commande** : `--target-mode ternary --feature-set expert --enable-global-stacking --enable-global-challenge --include-short-score --include-macro-move`
> **200 symboles** — 0 échec — ~1h13 d'entraînement — 3 challengers (LSTM, LightGBM, CatBoost)
> **Focus actuel** : LightGBM & CatBoost (LSTM non optimisé, analyse volontairement limitée)

---

## Table des matières

1. [Résumé exécutif](#résumé-exécutif)
2. [Comparaison LightGBM vs CatBoost](#1-comparaison-lightgbm-vs-catboost)
3. [Qualité de prédiction : distribution des F1](#2-qualité-de-prédiction--distribution-des-f1)
4. [Analyse par classe (Short / Flat / Long)](#3-analyse-par-classe-short--flat--long)
5. [Calibration : true vs pred](#4-calibration--true-vs-pred)
6. [Top & Flop performers](#5-top--flop-performers)
7. [Impact des nouvelles features : short-score & macro-move](#6-impact-des-nouvelles-features--short-score--macro-move)
8. [LightGBM vs CatBoost : lequel choisir ?](#7-lightgbm-vs-catboost--lequel-choisir-)
9. [Pistes d'amélioration priorisées](#8-pistes-damélioration-priorisées)
10. [Plan d'action](#9-plan-daction)

---

## Résumé exécutif

| Indicateur | Valeur | Verdict |
|:---|:---|:---|
| Symboles entraînés | 200/200 (0 échec) | ✅ Parfait |
| Durée | 1h13min | ✅ Rapide (vs ~10h sur le batch 0722) |
| F1 macro moyen WF | **0.293–0.296** (GBM) | 🟡 Acceptable, marge de progression |
| Meilleur modèle | **LightGBM** (97 champions) | 🟡 Léger avantage sur CatBoost |
| LSTM | 9 champions, F1=0.221 | 🔴 Non compétitif (attendu) |
| Symboles F1>0.40 | 5/200 (2.5%) | 🟡 Faible, univers difficile |
| Symboles F1<0.20 | 2/200 (1%) | ✅ Très peu de catastrophes |

**Verdict global** : Le batch est **sain et reproductible**. LightGBM et CatBoost sont au coude-à-coude, avec un très léger avantage pour LightGBM. La qualité de prédiction est modeste (F1~0.30) mais honnête pour du ternary classification sur 200 symboles avec walk-forward. Le LSTM reste non compétitif et confirme qu'il nécessite un chantier d'optimisation dédié (hors scope actuel). Les pistes d'amélioration sont claires et actionnables.

---

## 1. Comparaison LightGBM vs CatBoost

### 1.1 Champions sélectionnés

| Modèle | Nb champions | % du total |
|:---|---:|---:|
| **LightGBM** | **97** | 48.5% |
| CatBoost | 94 | 47.0% |
| LSTM | 9 | 4.5% |

LightGBM et CatBoost se partagent l'univers à quasi-égalité (97 vs 94). Cela signifie qu'**aucun des deux ne domine clairement l'autre** — le choix du champion dépend du symbole. C'est une situation saine : avoir deux algorithmes compétitifs permet de sélectionner le meilleur par symbole.

### 1.2 F1 macro par split

| Split | LightGBM | CatBoost | Δ (LGBM - CB) |
|:---|---:|---:|---:|
| **val** | 0.322 | 0.315 | +0.007 |
| **test** | 0.317 | 0.313 | +0.004 |
| **wf** (walk-forward) | **0.296** | **0.293** | +0.003 |

**Analyse** :
- LightGBM domine très légèrement sur tous les splits (+0.003 à +0.007).
- L'écart est **statistiquement non significatif** à l'échelle de 200 symboles — les deux modèles sont interchangeables en performance brute.
- La dégradation val→test→wf est **maîtrisée** : ~0.02 de perte, signe d'un bon contrôle de l'overfitting.
- Le walk-forward (validation temporelle réaliste) reste le juge de paix : F1 ~0.295 pour les deux GBM.

### 1.3 F1 par classe (WF)

| Classe | LightGBM | CatBoost | Δ |
|:---|---:|---:|---:|
| **F1 Short** | **0.281** | 0.260 | **+0.021** ✨ |
| F1 Flat | 0.294 | **0.307** | -0.013 |
| F1 Long | 0.313 | 0.313 | 0.000 |

**Analyse** :
- **LightGBM est nettement meilleur sur le Short** (+0.021), ce qui explique son avantage global. La détection des signaux baissiers est notoirement plus difficile — c'est un vrai différenciateur.
- CatBoost est légèrement meilleur sur le Flat (+0.013), mais c'est la classe la moins intéressante financièrement.
- Sur le Long, égalité parfaite (0.313).
- **Recommandation** : LightGBM est préférable si l'objectif métier est d'avoir un signal short de qualité.

### 1.4 Stabilité des hyperparamètres actuels

```
LightGBM : depth=4, n_estimators=200, lr=0.05
CatBoost  : depth=6, iterations=300, lr=0.03
```

Ces hyperparamètres sont **conservateurs mais robustes**. La faible profondeur (4-6) limite l'overfitting, ce qui est cohérent avec la bonne stabilité val→wf. On peut probablement monter en performance avec un tuning plus agressif (cf. section 8).

---

## 2. Qualité de prédiction : distribution des F1

### 2.1 Distribution F1 macro (Walk-Forward)

| Bucket F1 | Nb symboles | % | Cumul |
|:---|---:|---:|---:|
| **0.40+** | 5 | 2.5% | 2.5% |
| 0.35–0.39 | 52 | 26.0% | 28.5% |
| 0.30–0.34 | 60 | 30.0% | 58.5% |
| 0.25–0.29 | 55 | 27.5% | 86.0% |
| 0.20–0.24 | 26 | 13.0% | 99.0% |
| 0.10–0.19 | 2 | 1.0% | 100% |

### 2.2 Interprétation

```
┌─────────────────────────────────────────────────────────────┐
│  ████████████████████████████████████████ 58.5% ≥ 0.30      │
│  ██████████████████████████████ 86.0% ≥ 0.25                │
│  ██████████████████ 28.5% ≥ 0.35 (zone exploitable)         │
│  ██ 2.5% ≥ 0.40 (zone très bonne)                           │
└─────────────────────────────────────────────────────────────┘
```

- **58.5% des symboles** ont un F1 ≥ 0.30 — le modèle apporte une information exploitable sur la majorité de l'univers.
- **28.5% des symboles** ont un F1 ≥ 0.35 — ce sont les candidats prioritaires pour un déploiement.
- **Seulement 2.5%** atteignent 0.40+ — le ternary classification sur données financières reste un problème difficile.
- **1% de catastrophes** (F1 < 0.20) — très bien maîtrisé.

### 2.3 Comparaison avec le batch précédent (0722)

| Métrique | Batch 0722 | Batch 0724 (ce batch) | Évolution |
|:---|---:|---:|:---|
| F1 WF moyen GBM | ~0.28 | 0.293–0.296 | ✅ +0.01/+0.02 |
| Symboles F1>0.40 | 3 | 5 | ✅ +2 |
| Symboles F1<0.20 | 4 | 2 | ✅ -2 |
| Temps d'entraînement | ~10h | 1h13 | ✅✅ x8 plus rapide |

**Progrès notable** : les nouvelles features (short-score, macro-move) et le global stacking apportent un gain modeste mais réel, et le temps d'entraînement a été drastiquement réduit (probablement grâce à l'optimisation du pipeline ou une réduction du walk-forward).

---

## 3. Analyse par classe (Short / Flat / Long)

### 3.1 Performance par classe — GBM uniquement (WF)

| Modèle | F1 Short | F1 Flat | F1 Long | Δ Long-Short |
|:---|---:|---:|---:|---:|
| LightGBM | 0.281 | 0.294 | 0.313 | +0.032 |
| CatBoost | 0.260 | 0.307 | 0.313 | +0.053 |

**Constat** :
- **Le Long est mieux prédit que le Short** pour les deux modèles. C'est un biais classique en finance : les marchés montent plus souvent qu'ils ne baissent, et les features techniques capturent mieux les tendances haussières.
- L'asymétrie Long/Short est plus marquée chez CatBoost (+0.053) que chez LightGBM (+0.032).
- Le Flat reste la classe la plus difficile à prédire correctement (sauf pour CatBoost où c'est la meilleure).

### 3.2 Symboles avec F1 Short = 0

| Symbole | F1 Macro | F1 Long | F1 Flat | Diagnostic |
|:---|---:|---:|---:|:---|
| ESE | 0.303 | 0.361 | 0.547 | Bon sur Flat/Long, zero short |
| HIW | 0.313 | 0.351 | 0.588 | Idem |
| WWD | 0.291 | 0.360 | 0.514 | Idem |

**Analyse** : Ces 3 symboles ont un F1 macro acceptable (0.29–0.31) mais **ne prédisent jamais la classe Short**. Le modèle est « aveugle au downside » sur ces tickers. Le F1 macro masque ce problème car compensé par de bonnes performances Flat/Long.

**Risque métier** : Si ces symboles sont tradés avec le signal, on prendra des longs et des flats mais jamais de shorts → exposition directionnelle systématique.

### 3.3 Symboles avec F1 Flat = 0

| Symbole | F1 Macro | F1 Long | F1 Short | Note |
|:---|---:|---:|---:|:---|
| LQDA | 0.200 | 0.139 | 0.460 | Modèle tout short, jamais flat |

Un seul symbole avec F1 Flat = 0 — c'est acceptable. Le vrai problème serait des F1 Flat = 0 généralisés, ce qui n'est pas le cas.

---

## 4. Calibration : true vs pred

### 4.1 Distribution true vs predicted (WF)

| Modèle | Classe | True % | Pred % | Écart | Biais |
|:---|---:|---:|---:|---:|:---|
| **CatBoost** | Short | 29.2% | 32.7% | +3.5% | Léger sur-pred short |
| | Flat | 34.3% | 34.5% | +0.2% | ✅ Parfait |
| | Long | 36.6% | 32.8% | **-3.8%** | Sous-pred long |
| **LightGBM** | Short | 29.2% | 36.9% | **+7.7%** | 🔴 Sur-pred short |
| | Flat | 34.3% | 30.5% | **-3.8%** | Sous-pred flat |
| | Long | 36.6% | 32.5% | **-4.1%** | Sous-pred long |

### 4.2 Interprétation

```
CatBoost  : [===Short===][====Flat====][====Long====]  ← Bon équilibre
True      : [===Short===][====Flat====][====Long====]
LightGBM  : [=====Short=====][===Flat===][====Long====] ← Biais short
```

**CatBoost est nettement mieux calibré que LightGBM.** C'est un point important :

- **LightGBM** sur-prédit le Short de +7.7 points et sous-prédit Flat et Long. Cela signifie qu'il voit des shorts partout → beaucoup de faux signaux short. C'est cohérent avec son meilleur F1 Short (il prend plus de risques sur cette classe) mais au prix d'une calibration dégradée.
- **CatBoost** est quasi-parfait sur le Flat et ne sous-prédit le Long que de 3.8 points. Sa calibration est plus équilibrée.

**Implication** : Si on utilise LightGBM, il faut **recalibrer les probabilités** (Platt scaling déjà activé, mais peut-être insuffisant) ou ajuster les decision thresholds par classe.

---

## 5. Top & Flop performers

### 5.1 Top 5 — À répliquer

| Symbole | F1 Macro | F1 Long | F1 Short | F1 Flat | Profil |
|:---|---:|---:|---:|---:|:---|
| **MAS** | 0.427 | 0.259 | 0.417 | 0.606 | Excellent Flat, bon Short |
| **INDV** | 0.424 | 0.549 | 0.477 | 0.246 | Excellent Long/Short |
| **EXTR** | 0.413 | 0.589 | 0.483 | 0.166 | Excellent Long/Short |
| **TD** | 0.402 | 0.355 | 0.302 | 0.549 | Excellent Flat |
| **WERN** | 0.402 | 0.353 | 0.223 | 0.630 | Excellent Flat |

**Pattern** : Les top performers ont un point fort très marqué (Flat > 0.55 pour MAS/TD/WERN, Long > 0.50 pour INDV/EXTR) qui compense un point faible. Aucun n'est bon partout. Le F1 macro récompense la spécialisation.

### 5.2 Flop 5 — À investiguer

| Symbole | F1 Macro | F1 Long | F1 Short | F1 Flat | Diagnostic probable |
|:---|---:|---:|---:|---:|:---|
| **TH** | 0.199 | 0.124 | 0.451 | 0.021 | Bon short, incapable flat/long |
| **LQDA** | 0.200 | 0.139 | 0.460 | 0.000 | Tout short, zero flat |
| **BAP** | 0.203 | 0.000 | 0.261 | 0.347 | Zero long |
| **HLIO** | 0.205 | 0.064 | 0.330 | 0.220 | Faible partout |
| **CTOS** | 0.210 | 0.119 | 0.238 | 0.272 | Faible partout |

**Pattern des flops** : La plupart ont un F1 très déséquilibré (bon sur une classe, nul sur les autres) ou mauvais partout. Leur point commun probable : faible capitalisation, faible liquidité → données bruitées → signal ML inefficace. À croiser avec les données de marché (volume, market cap, spread).

---

## 6. Impact des nouvelles features : short-score & macro-move

Ce batch introduit deux nouvelles features via `--include-short-score --include-macro-move` :

### 6.1 Ce qu'on observe

| Indicateur | Sans (batch 0722) | Avec (batch 0724) | Δ |
|:---|---:|---:|:---|
| F1 WF LightGBM | ~0.280 | 0.296 | **+0.016** ✅ |
| F1 WF CatBoost | ~0.278 | 0.293 | **+0.015** ✅ |
| F1 Short LightGBM | ~0.26 | 0.281 | **+0.02** ✅ |
| F1 Short CatBoost | ~0.24 | 0.260 | **+0.02** ✅ |

### 6.2 Interprétation

- Le **gain est modeste mais réel** : +0.015 de F1 macro, principalement porté par l'amélioration du Short.
- Le **short-score** semble bien remplir son rôle : améliorer la détection des signaux baissiers.
- Le **macro-move** apporte probablement un complément d'information sur le régime de marché.
- Le coût en calcul est négligeable — ces features sont rentables.

**Verdict** : ✅ À conserver. Le short-score est un bon ajout. On pourrait explorer un **macro-move plus granulaire** (sectoriel plutôt que global SPY).

---

## 7. LightGBM vs CatBoost : lequel choisir ?

### 7.1 Matrice de décision

| Critère | LightGBM | CatBoost | Gagnant |
|:---|:---|:---|:---|
| F1 macro WF | 0.296 | 0.293 | LightGBM (léger) |
| F1 Short | 0.281 | 0.260 | **LightGBM** ✅ |
| F1 Long | 0.313 | 0.313 | Égalité |
| Calibration | Biais short +7.7% | Bonne (±3.8%) | **CatBoost** ✅ |
| Vitesse entraînement | Rapide | Plus lent | LightGBM |
| Gestion des catégorielles | Manuelle | Automatique | CatBoost |
| Robustesse hyperparamètres | Bonne | Excellente | CatBoost |
| Interprétabilité (SHAP) | Excellente | Bonne | LightGBM |

### 7.2 Recommandation

```
🏆 POUR LE DÉPLOIEMENT ACTUEL : LightGBM
   → Meilleur F1 global, meilleur F1 Short, plus rapide
   → Mais nécessite une recalibration des probabilités

🥈 POUR LA ROBUSTESSE LONG TERME : CatBoost
   → Meilleure calibration naturelle, moins de biais
   → Meilleur choix si on automatise sans recalibration
```

**Stratégie hybride recommandée** : Continuer à entraîner les deux et sélectionner le champion par symbole (comme actuellement). C'est la meilleure approche : on prend le meilleur des deux mondes.

---

## 8. 🔍 Analyse du code source — Ce que le code explique des résultats

> Les sections ci-dessous croisent les métriques du batch avec le code source
> de `modelFactory/`. Chaque constat est tracé jusqu'au fichier et à la ligne
> responsables.

### 8.1 Chaîne de décision ternaire : pourquoi LightGBM sur-pred le Short

Le pipeline de décision suit ce chemin :

```
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Modèle GBM   │───▶│ TemperatureScaler │───▶│ TernaryDecisionPolicy │───▶ side
│  (3 probas)   │    │ (calibration)     │    │ (threshold + margin)  │
└──────────────┘    └──────────────────┘    └─────────────────────┘
```

**Fichiers clés** :
- `modelFactory/lightgbm_baseline.py` : `run_lightgbm_baseline()` → `LGBMClassifier(objective="multiclass")`
- `modelFactory/catboost_baseline.py` : `run_catboost_baseline()` → `CatBoostClassifier(loss_function="MultiClass")`
- `modelFactory/tabular_baseline.py` : `run_tabular_baseline()` — cœur commun
- `modelFactory/calibration.py` : `TemperatureScaler` pour calibration ternaire
- `core/ternary_decision_policy.py` : `TernaryDecisionPolicy` + `decide_ternary_side()`

**Diagnostic du biais LightGBM** :

1. **Poids de classe égaux** (ligne de commande : `--ternary-weight-short 1.0 --ternary-weight-flat 1.0 --ternary-weight-long 1.0`)
   → Dans `model.py:LSTMAttentionModule.__init__()`, les poids sont `[1.0, 1.0, 1.0]`.
   → Les GBM (`lightgbm_baseline.py`, `catboost_baseline.py`) **n'utilisent pas** ces poids
   (pas de `class_weight` dans `LGBMClassifier` ou `CatBoostClassifier`).
   → **Donc les GBM sont entraînés sans régularisation de classe.**

2. **Sample weighting par récence** (`tabular_baseline.py:260-275`) :
   ```python
   _sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)
   ```
   Demi-vie de 365 jours. Les données récentes pèsent plus. Si le régime récent
   a été baissier (2022, début 2025), le modèle apprend à sur-prédire le Short.

3. **TemperatureScaler** (`tabular_baseline.py:230-250`) :
   La calibration ternaire utilise `TemperatureScaler` sur les logits inversés.
   Contrairement à Platt (binaire), le TemperatureScaler ne corrige que la « netteté »
   des probas, pas leur distribution. Il ne peut pas corriger un biais systématique
   vers une classe.

4. **TernaryDecisionPolicy** (`core/ternary_decision_policy.py:147-220`) :
   ```python
   threshold_long=0.45, threshold_short=0.45, top2_margin=0.05
   ```
   Les seuils sont **symétriques** (0.45 pour long et short). Avec des probas
   brutes déjà biaisées short, la policy ne compense rien.

**Conclusion code** : Le biais Short de LightGBM (+7.7%) a **3 causes racines** :
- (A) ~~Pas de `class_weight` dans les GBM~~ → ✅ Résolu (2026-07-24) : `class_weight="balanced"` + `auto_class_weights="Balanced"`
- (B) ~~`TemperatureScaler` ne corrige pas le biais de distribution~~ → ✅ Résolu (2026-07-24) : remplacé par `VectorScaler` (T + biais par classe)
- (C) `TernaryDecisionPolicy` a des seuils symétriques → ⏳ À faire (cf. §9.4)

### 8.2 Feature set réel utilisé par les GBM

D'après `features.py:get_feature_columns()`, avec `--feature-set expert --enable-cross-sectional --include-short-score --include-macro-move` :

| Groupe | Nombre | Colonnes |
|:---|---:|:---|
| **V1 (OHLCV)** | 13 | `daily_return`, `log_return`, `intraday_range`, `overnight_gap`, `close_to_vwap`, `volume_ratio_20`, `rolling_volatility_20/60`, `rolling_mean_return_5/20`, `rsi_14`, `atr_14_norm`, `is_filled` |
| **Expert** | 18 | `sma20/50/100/200_distance`, `ema20/50_distance`, `momentum_10/20/60`, `vol_ratio_20_60`, `range_position_20`, `market_return_20`, `market_volatility_20`, `market_trend_strength_50`, `relative_strength_20/60`, `regime_bull_market`, `regime_risk_off` |
| **Cross-sectional** | 16 | 8 rangs percentiles + 8 sectorielles (momentum, vol, alpha intra-secteur) |
| **Macro** | 1 | `move_close` (MOVE index) |
| **Short-score** | 1 | `selector_short_score` |
| **Régime × technique** | 18 | Interactions `momentum_20_x_bull`, `rsi_14_x_risk_off`, etc. |
| **Global stacking** | 3 | `global_pred_short`, `global_pred_flat`, `global_pred_long` |
| **Total** | **~70** | |

**Analyse** :
- Les GBM reçoivent **~70 features** dont 18 interactions régime×technique → c'est
  beaucoup pour `depth=4` (LightGBM) ou `depth=6` (CatBoost). Ces arbres peu profonds
  ne peuvent capturer que des interactions d'ordre 4 à 6.
- Les interactions `_x_bull` et `_x_risk_off` doublent le nombre de features techniques.
  C'est théoriquement utile mais la faible profondeur limite l'exploitation.
- **Recommandation** : Si on augmente la profondeur (tuning), ces interactions
  deviendront exploitables. Sinon, elles ajoutent du bruit.

### 8.3 Global Stacking : mécanisme réel

**Fichier** : `modelFactory/global_model.py`

Le Global Model (`--enable-global-model --global-model-name lightgbm`) :
1. Agrège TOUS les symboles dans un seul DataFrame
2. Utilise **uniquement** les features cross-symboles (ranks, secteurs, macro, régime)
   → Les features locales (OHLCV, expert) sont **exclues** (`_get_global_feature_columns()`)
3. Entraîne un seul LightGBM multi-symbole
4. Produit `global_pred_long(symbol, date)`, `global_pred_short`, `global_pred_flat`

Le Global Stacking (`--enable-global-stacking`) :
1. Injecte les 3 probas globales comme **features supplémentaires** dans les modèles
   per-symbol (`get_feature_columns()` avec `include_global_stacking=True`)
2. Le modèle per-symbol peut ainsi exploiter le « contexte de marché » appris par le global

**Limite actuelle** : Le global et le per-symbol utilisent le **même algorithme**
(LightGBM). Pour un vrai stacking, il faudrait diversifier (ex: CatBoost global +
LightGBM per-symbol, ou l'inverse).

### 8.4 Walk-Forward : configuration et impact

**Fichier** : `modelFactory/config.py:WalkForwardConfig` — partagé par **tous** les modèles
(LSTM via `trainer.py`, GBM via `tabular_baseline.py`, Global via `global_model.py`).

```python
min_train_size=504  # ~2 ans de training
val_size=126        # ~6 mois de validation
test_size=126       # ~6 mois de test
step_size=126       # avance de 6 mois par split
max_splits=3        # ⚠️ 3 splits — volontairement réduit (phase recherche)
```

**Statut** : `max_splits=3` est un **choix délibéré de phase recherche**. On allège
les paramètres pour itérer vite sur les combinaisons (features, hyperparams, stacking).
Ce n'est PAS un bug — c'est un trade-off vitesse vs couverture temporelle.

**Quand passer à `max_splits=8+`** : Une fois la « best combinaison » trouvée,
augmenter `max_splits` pour une validation WF complète sur tous les régimes
(2020-2024) avant le go-live.

### 8.5 Sélection du champion : mécanique et biais

**Fichier** : `modelFactory/champion_selection.py`

```python
def selection_score_from_result(result, metric="selection_score"):
    # Utilise val et walk_forward, PAS test/final_holdout
```

Le champion est sélectionné sur `selection_score` qui est :
1. `threshold_business_score` (si disponible)
2. Sinon `auc` (AUC binaire)
3. Sinon 0

**Problème** : Le `selection_score` est basé sur la partition **val uniquement**
(pas de look-ahead dans le test). Mais comme le WF n'a que 3 splits, la sélection
est faite sur une vision partielle des régimes de marché.

**À noter** : La règle stricte « pas de test dans la sélection » dans
`champion_selection.py` est une **bonne pratique** — elle prévient le data leakage.

---

## 9. Pistes d'amélioration priorisées (enrichies code)

### 🔴 Priorité Haute — Impact fort, effort modéré

#### 9.1 Hyperparameter tuning LightGBM

**Fichier à modifier** : `modelFactory/lightgbm_baseline.py:38-46`

```python
# Actuel (lightgbm_baseline.py):
model_builder=lambda resolved_seed: lgb.LGBMClassifier(
    objective="multiclass",
    num_class=3,
    max_depth=cfg.baseline.max_depth,        # 4
    n_estimators=cfg.baseline.n_estimators,   # 200
    learning_rate=cfg.baseline.learning_rate,  # 0.05
    random_state=resolved_seed,
    verbosity=-1,
)
```

**Paramètres déjà appliqués (2026-07-24)** :
```python
    class_weight="balanced", # ✅ FAIT — corrige le biais Short (+7.7%)
```

**Paramètres restant à tuner** :
```python
    reg_alpha=0.1,          # L1 régularisation → réduit overfitting
    reg_lambda=0.1,         # L2 régularisation
    min_child_samples=50,   # Évite les feuilles trop petites
    subsample=0.8,          # Bagging → robustesse
    colsample_bytree=0.8,   # Feature sampling
```

**Gain attendu** : +0.02 à +0.04 de F1 WF (tuning).

#### 9.2 Hyperparameter tuning CatBoost

**Fichier à modifier** : `modelFactory/catboost_baseline.py:49-60`

```python
# Actuel (catboost_baseline.py):
CatBoostClassifier(
    depth=cfg.baseline.catboost_depth,            # 6
    iterations=cfg.baseline.catboost_iterations,   # 300
    learning_rate=cfg.baseline.catboost_learning_rate,  # 0.03
    random_seed=resolved_seed,
    loss_function="MultiClass",
    verbose=False,
    train_dir=str(...),
    allow_writing_files=True,
)
```

**Paramètres déjà appliqués (2026-07-24)** :
```python
    auto_class_weights="Balanced",  # ✅ FAIT — corrige le biais Short
```

**Paramètres restant à tuner** :
```python
    l2_leaf_reg=3,             # L2 régularisation
    border_count=128,          # Précision des splits
    random_strength=1,         # Randomized scoring → robustesse
    bagging_temperature=1,     # Bayesian bagging
    od_type="IncToDec",        # Overfitting detector
    od_wait=20,                # Patience overfitting
```

**Gain attendu** : +0.02 à +0.03 de F1 WF (tuning).

#### 9.3 Poids de classe GBM — Correction du biais Short ✅ FAIT (2026-07-24)

**Cause racine** : Ni `LGBMClassifier` ni `CatBoostClassifier` ne recevaient de
`class_weight`. Les poids `--ternary-weight-*` étaient utilisés **que** par le LSTM
(`model.py:117`).

**Correctif appliqué** (3 fichiers) :
- `lightgbm_baseline.py` → `class_weight="balanced"`
- `catboost_baseline.py` → `auto_class_weights="Balanced"`
- `global_model.py` → idem pour le Global Model (single-split + WF)

**Alternative plus fine** (si `"balanced"` insuffisant) :
```python
train_class_counts = train_targets.value_counts().sort_index()
total = len(train_targets)
class_weights = {cls: total / (3 * count) for cls, count in train_class_counts.items()}
```

**Gain attendu** : Correction du biais de calibration +0.01–0.02 F1.

#### 9.3b Calibration VectorScaler (remplace TemperatureScaler) ✅ FAIT (2026-07-24)

**Cause racine** : `TemperatureScaler` (1 paramètre T) ne peut pas corriger un biais
de distribution vers une classe. Le `VectorScaler` (1 + C paramètres : T + biais par
classe) permet de compenser la sur/sous-prédiction systématique par classe.

$$P_{\text{calibré}}(y=i | z) = \frac{\exp(z_i / T + b_i)}{\sum_j \exp(z_j / T + b_j)}$$

**Correctif appliqué** (3 fichiers) :
- `calibration.py` → nouvelle classe `VectorScaler`
- `tabular_baseline.py` → `_fit_ternary_calibrator()` utilise `VectorScaler`
- `global_model.py` → calibration ternaire sur single-split et WF

#### 9.4 Seuils asymétriques dans TernaryDecisionPolicy

**Fichier à modifier** : `core/ternary_decision_policy.py:93-97`

```python
# Actuel :
threshold_long: float = 0.45
threshold_short: float = 0.45
top2_margin: float = 0.05

# Proposé (compense le biais short de LightGBM) :
threshold_long: float = 0.40   # Plus facile de dire long
threshold_short: float = 0.50  # Plus exigeant pour dire short
top2_margin: float = 0.05
```

Ajouter ces paramètres dans la CLI (`config.py`) pour permettre l'A/B testing :
```python
# DataConfig:
ternary_decision_threshold_long: float = 0.45
ternary_decision_threshold_short: float = 0.45
ternary_decision_top2_margin: float = 0.05
```

**Gain attendu** : Meilleure calibration, réduction du biais Short.

#### 9.5 Filtrage de l'univers par liquidité

**Fichier à créer/modifier** : `modelFactory/orchestrator.py` (dans la boucle de
sélection des symboles) ou `database/selector_reference.py`.

Ajouter un filtre dans `filter_symbols_from_start()` ou en amont dans l'orchestrateur :
```python
MIN_AVG_VOLUME_20D = 500_000   # 500k shares/jour
MIN_MARKET_CAP = 500_000_000    # 500M$
MAX_AVG_SPREAD_PCT = 0.5        # 0.5%
```

**Gain attendu** : Élimination des 10-15% de small caps illiquides → F1 moyen +0.01.

### 🟡 Priorité Moyenne — Impact modéré, effort modéré

#### 9.6 Augmenter max_splits WF (post-recherche)

**Fichier** : `modelFactory/config.py:WalkForwardConfig` — partagé par LSTM, GBM, Global.

```python
# Actuel : max_splits: int = 3   ← volontaire (phase recherche, itérations rapides)
# Cible  : max_splits: int = 8   ← pré-go-live (couvre 2020-2024 avec step=126)
```

⚠️ Ce n'est **PAS** à faire maintenant. On garde `max_splits=3` tant qu'on
cherche la meilleure combinaison (features + hyperparams + stacking). On passera
à 8+ une fois la config finale trouvée, pour une validation complète avant
déploiement. Le temps d'entraînement augmentera de ~2-3x.

#### 9.7 Calibration Isotonic

**Fichier** : `modelFactory/calibration.py` — Ajouter `IsotonicCalibrator`.

```python
from sklearn.isotonic import IsotonicRegression

@dataclass(slots=True)
class IsotonicCalibrator:
    """Calibrateur isotonique non-paramétrique."""
    # ...
```

Puis dans `tabular_baseline.py:fit_tabular_calibrator()`, brancher sur
`cfg.calibration.method == "isotonic"`.

**Avantage** : Contrairement à Platt (logistique) ou TemperatureScaler (scaling),
l'isotonique peut corriger des biais non-monotones.

#### 9.8 Global stacking cross-modèle

**Fichier** : `modelFactory/global_model.py:176`

Actuellement `_build_global_estimator()` ne supporte que lightgbm ou catboost selon
`cfg.global_model.model_name`.

**Proposé** : Toujours entraîner les deux (LightGBM + CatBoost) et injecter
6 probas (3 par modèle) comme features de stacking dans les per-symbol.

### 🟢 Priorité Basse

#### 9.9 Interaction régime×technique : réévaluation

**Fichier** : `modelFactory/features.py:REGIME_INTERACTION_FEATURES`

Les 18 features d'interaction sont calculées mais avec `depth=4`, un arbre
ne peut pas les exploiter pleinement. Deux options :
- (A) Augmenter la profondeur à 6–8 (en même temps que le tuning)
- (B) Remplacer les interactions par des features plus simples :
  `momentum_20_capped_by_regime` au lieu de `momentum_20_x_bull` + `momentum_20_x_risk_off`

#### 9.10 LSTM — pourquoi le biais flat (diagnostic code)

**Rappel** : Le LSTM prédit flat 62% du temps vs 34% en vrai.

**Causes racines dans le code** :

1. **Poids par défaut** (`model.py:109`) :
   ```python
   ternary_weight_flat: float = 1.5  # ← Le flat est SUR-pondéré !
   ternary_weight_short: float = 1.0
   ternary_weight_long: float = 1.0
   ```
   Le paramètre par défaut `ternary_weight_flat=1.5` explique le biais. Le CLI
   passe `--ternary-weight-flat 1.0` mais uniquement si le paramètre est exposé —
   vérifier qu'il est bien passé au `LSTMAttentionModule`.

2. **Sequence length = 10** (`--sequence-length 10`) : 10 jours, c'est très court
   pour du LSTM. Avec `forecast_horizon=10`, le modèle voit 10 jours pour prédire
   J+10 → ratio signal/bruit très faible.

3. **Normalisation globale** : Si les features sont normalisées sur tout l'univers
   plutôt que par symbole, le LSTM voit des patterns non stationnaires.

> Le chantier LSTM est hors scope actuel mais ces 3 points seront les premiers
> à corriger quand on s'y attaquera.

---

## 10. Plan d'action (mis à jour avec code)

### Semaine 1 : Quick wins code

| Action | Fichier(s) | Effort | Statut |
|:---|:---|:---|:---|
| **class_weight="balanced" LightGBM** | `lightgbm_baseline.py` | 30min | ✅ Fait |
| **auto_class_weights="Balanced" CatBoost** | `catboost_baseline.py` | 30min | ✅ Fait |
| **VectorScaler (remplace TemperatureScaler)** | `calibration.py` + `tabular_baseline.py` + `global_model.py` | 2h | ✅ Fait |
| **Seuils asymétriques** | `ternary_decision_policy.py` + `config.py` | 2h | ⏳ À faire |
| Filtrage liquidité | `orchestrator.py` + `selector_reference.py` | 3h | ⏳ À faire |

### Semaine 2 : Tuning

| Action | Fichier(s) | Effort | Gain |
|:---|:---|:---|:---|
| Hyperparameter tuning LightGBM | `lightgbm_baseline.py` + `config.py` | 4h | +0.02–0.04 |
| Hyperparameter tuning CatBoost | `catboost_baseline.py` + `config.py` | 4h | +0.02–0.03 |
| Isotonic calibrator | `calibration.py` + `tabular_baseline.py` | 3h | calibration |

### Pré-Go-Live (après recherche)

| Action | Fichier(s) | Effort | Gain |
|:---|:---|:---|:---|
| Augmenter max_splits WF (3→8+) | `config.py:WalkForwardConfig` | 1h | couverture régimes |
| Global stacking cross-modèle | `global_model.py` | 4h | +0.005–0.01 |
| Simplifier interactions régime | `features.py` | 2h | robustesse |
| Macro-move sectoriel | `features.py` + loader | 5h | +0.005–0.01 |

---

## Annexe A — Rappel de la configuration

```powershell
python -m modelFactory --mode train --accelerator auto \
  --target-mode ternary --num-classes 3 \
  --ternary-weight-short 1.0 --ternary-weight-flat 1.0 --ternary-weight-long 1.0 \
  --ternary-threshold-short 0.35 --ternary-threshold-long 0.35 --ternary-top2-margin 0.02 \
  --forecast-horizon 10 --target-up-threshold 0.03 --target-down-threshold -0.03 \
  --decision-threshold 0.55 --calibration-method platt \
  --feature-set expert --benchmark-symbol SPY --sequence-length 10 --batch-size 32 --hidden-size 128 \
  --ml-mode rebuild-all --training-start-date 2018-01-01 \
  --symbol-source ticket-recherche --artifacts-dir artifacts/models \
  --max-workers 6 --max-epochs 20 --patience 3 --cross-sectional-min-universe 20 \
  --lgbm-max-depth 4 --lgbm-n-estimators 200 --lgbm-learning-rate 0.05 \
  --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 \
  --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO \
  --training-end-date 2025-12-31 --compare-lightgbm --enable-catboost \
  --enable-global-model --global-model-name lightgbm \
  --enable-global-stacking --enable-global-challenge --enable-cross-sectional \
  --select-champion --walkforward \
  --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 3 \
  --include-short-score --include-macro-move \
  --comment "baseline + global staking gbm + challenger+ short score + move"
```

## Annexe B — Glossaire

| Terme | Définition |
|:---|:---|
| **F1 macro** | Moyenne des F1 par classe (Short, Flat, Long). Mesure globale non biaisée par la distribution des classes. |
| **WF (Walk-Forward)** | Validation temporelle réaliste : entraînement sur passé, test sur futur, avec fenêtre glissante. |
| **Platt scaling** | Calibration des probabilités par régression logistique sur les scores bruts du modèle. |
| **Global stacking** | Un méta-modèle entraîné sur tous les symboles qui combine les features avec les prédictions du modèle local. |
| **Short-score** | Feature indiquant la probabilité qu'un titre baisse, dérivée d'indicateurs techniques baissiers. |
| **Macro-move** | Feature indiquant le mouvement global du marché (basé sur SPY), pour conditionner les prédictions au régime. |
