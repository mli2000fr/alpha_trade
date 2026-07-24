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

## 8. Pistes d'amélioration priorisées

### 🔴 Priorité Haute — Impact fort, effort modéré

#### 8.1 Hyperparameter tuning LightGBM

```yaml
Actuel:
  depth: 4, n_estimators: 200, lr: 0.05

Proposé (recherche par plages):
  depth: [3, 4, 5, 6, 7]
  n_estimators: [100, 200, 300, 500]
  lr: [0.01, 0.03, 0.05, 0.1]
  min_child_samples: [20, 50, 100]
  subsample: [0.7, 0.8, 0.9, 1.0]
  colsample_bytree: [0.7, 0.8, 0.9, 1.0]
  reg_alpha: [0, 0.1, 0.5, 1.0]
  reg_lambda: [0, 0.1, 0.5, 1.0]
```

**Gain attendu** : +0.02 à +0.04 de F1 WF. Avec 200 symboles, on peut faire un tuning par sous-ensemble puis généraliser.

#### 8.2 Hyperparameter tuning CatBoost

```yaml
Actuel:
  depth: 6, iterations: 300, lr: 0.03

Proposé:
  depth: [4, 5, 6, 7, 8]
  iterations: [200, 300, 500, 1000]
  lr: [0.01, 0.03, 0.05, 0.1]
  l2_leaf_reg: [1, 3, 5, 10]
  border_count: [32, 64, 128]
  random_strength: [0, 1, 2]
```

**Gain attendu** : +0.02 à +0.03 de F1 WF.

#### 8.3 Ajustement des thresholds de décision

Actuellement : `--decision-threshold 0.55` uniforme pour toutes les classes.

**Problème** : Le biais de prédiction (LightGBM sur-pred short de +7.7%) suggère que le threshold optimal n'est pas le même par classe.

**Proposition** : Thresholds asymétriques :
```yaml
decision-threshold-short: 0.60  # Plus exigeant car sur-prédit
decision-threshold-flat: 0.50   # Standard
decision-threshold-long: 0.50   # Standard
```

Ou utiliser un **threshold optimizer** qui maximise le F1 macro par symbole sur la période de validation.

**Gain attendu** : +0.01 à +0.02 de F1 WF, meilleure calibration.

#### 8.4 Filtrage de l'univers

Les 5 flops (TH, LQDA, BAP, HLIO, CTOS) ont probablement des caractéristiques communes (faible cap, faible liquidité).

**Proposition** : Ajouter un filtre de liquidité pré-entraînement :
- Volume moyen 20j > 500k shares
- Market cap > 500M$
- Spread moyen < 0.5%

**Gain attendu** : Élimination des 10-15% de symboles les plus bruités → F1 moyen mécaniquement amélioré.

### 🟡 Priorité Moyenne — Impact modéré, effort modéré

#### 8.5 Global stacking amélioré

Actuellement : `--enable-global-stacking --global-model-name lightgbm`

Le global stacking est activé mais on pourrait :
- **Stacker les deux GBM** : utiliser LightGBM + CatBoost comme base learners, et un méta-modèle (LogisticRegression ou un LightGBM shallow) par-dessus.
- **Feature de stacking cross-modèle** : ajouter les prédictions de CatBoost comme feature pour LightGBM et vice-versa.

#### 8.6 Macro-move sectoriel

Remplacer le macro-move SPY unique par des moves sectoriels (XLF, XLK, XLE, XLV, XLI, etc.). Un titre technologique devrait être conditionné au move du secteur tech, pas au SPY global.

#### 8.7 Poids de classe dynamiques

Actuellement : `--ternary-weight-short 1.0 --ternary-weight-flat 1.0 --ternary-weight-long 1.0`

Des poids asymétriques pourraient compenser le biais Long :
```yaml
ternary-weight-short: 1.3   # Pénaliser plus les erreurs short
ternary-weight-flat: 0.8    # Réduire l'importance du flat
ternary-weight-long: 1.0
```

#### 8.8 Calibration Isotonic en complément de Platt

La calibration Platt est une régression logistique — elle suppose une relation monotone. La calibration isotonique est non-paramétrique et peut mieux corriger les biais non-linéaires.

```yaml
--calibration-method isotonic  # Au lieu de platt
```

### 🟢 Priorité Basse — Gain incertain, à explorer plus tard

#### 8.9 Feature engineering

- **Features de momentum multi-timeframe** : 5j, 10j, 20j, 60j
- **Features de volatilité conditionnelle** : vol régimes haut/bas
- **Features cross-sectionnelles avancées** : rang sectoriel, z-score vs secteur
- **Features de saisonnalité** : jour du mois, semaine de l'année

#### 8.10 Pseudo-labelling

Utiliser les prédictions à haute confiance (>0.70) sur des données non labellisées pour augmenter le training set.

#### 8.11 LSTM — chantier dédié (hors scope actuel)

Le LSTM nécessite un travail spécifique :
- Réduire le biais flat massif (pred flat 62% vs true 34%)
- Ajuster l'architecture (dropout, attention, num_layers)
- Augmenter la sequence length (10 → 20 ou 30)
- Essayer un loss weighted ou focal loss
- Normalisation par symbole (et non globale)

Ce chantier est documenté dans `prompt/analyse_ml.md` et n'est pas la priorité actuelle.

---

## 9. Plan d'action

### Semaine 1 : Quick wins

| Action | Effort | Gain estimé | Priorité |
|:---|:---|:---|:---|
| Threshold asymétrique Short/Long/Flat | 2h | +0.01 F1 | 🔴 |
| Filtrage liquidité pré-entraînement | 3h | +0.01 F1 (avg) | 🔴 |
| Poids de classe asymétriques (1.3/0.8/1.0) | 1h | calibration | 🔴 |
| Rapport de calibration post-batch | 2h | visibilité | 🟡 |

### Semaine 2 : Tuning

| Action | Effort | Gain estimé | Priorité |
|:---|:---|:---|:---|
| Hyperparameter tuning LightGBM (Optuna) | 4h | +0.02–0.04 F1 | 🔴 |
| Hyperparameter tuning CatBoost (Optuna) | 4h | +0.02–0.03 F1 | 🔴 |
| Calibration isotonique vs Platt (A/B test) | 2h | calibration | 🟡 |

### Semaine 3-4 : Améliorations structurelles

| Action | Effort | Gain estimé | Priorité |
|:---|:---|:---|:---|
| Macro-move sectoriel (11 secteurs GICS) | 5h | +0.005–0.01 F1 | 🟡 |
| Global stacking bi-modèle (LGBM+CB) | 4h | +0.005–0.01 F1 | 🟡 |
| Feature momentum multi-timeframe | 3h | incertain | 🟢 |

### Indicateurs de succès

| Métrique | Actuel | Cible S+2 | Cible S+4 |
|:---|---:|---:|:---|
| F1 macro WF moyen (GBM) | 0.295 | 0.31 | 0.33 |
| Symboles F1 > 0.40 | 5 (2.5%) | 15 (7.5%) | 30 (15%) |
| Symbole F1 < 0.20 | 2 (1%) | 0 (0%) | 0 (0%) |
| Écart Long/Short F1 | 0.04 | 0.02 | 0.01 |

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
