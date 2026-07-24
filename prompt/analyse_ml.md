# 🔬 Analyse Approfondie — Batch `model-factory-20260722091334-cddc05`

> **Date** : 2026-07-22  
> **Commande** : `--feature-set expert --enable-cross-sectional --mode train --target-mode ternary`  
> **200 symboles** — 0 échec — ~10h d'entraînement — 3 challengers (LSTM, LightGBM, CatBoost)

---

## Table des matières

1. [Point 1 — Pourquoi le LSTM est cassé](#1-pourquoi-le-lstm-est-cassé)
2. [Point 2 — Diagnostic du biais LONG](#2-diagnostic-du-biais-long)
3. [Point 3 — Stratégie de filtrage de l'univers](#3-stratégie-de-filtrage-de-lunivers)
4. [Point 4 — Analyse approfondie du top 20%](#4-analyse-approfondie-du-top-20)
5. [Point 5 — Investigation du feature set `expert`](#5-investigation-du-feature-set-expert)
6. [Point 6 — Analyse sectorielle des underperformers](#6-analyse-sectorielle-des-underperformers)
7. [Synthèse & Plan d'action](#7-synthèse--plan-daction)

---

## 1. Pourquoi le LSTM est cassé

### 1.1 Architecture actuelle

```python
# modelFactory/model.py — LSTMAttentionClassifier
LSTM(
    input_size=47,       # 31 expert + 16 cross-sectional
    hidden_size=128,     # --hidden-size 128
    num_layers=2,        # défaut
    dropout=0.3,         # défaut
    batch_first=True,
)
→ TemporalAttention(hidden_size=128)
→ Dropout(0.3)
→ Linear(128 → 3)       # 3 classes : short/flat/long
```

```python
# modelFactory/model.py — LSTMAttentionModule
CrossEntropyLoss(weight=[1.0, 1.0, 1.0])  # poids égaux short/flat/long
learning_rate=1e-3, weight_decay=1e-5
max_epochs=20, patience=3, batch_size=32
```

### 1.2 Données d'entrée

```
sequence_length = 10 jours
features = 47 colonnes
≈ 2000 séquences par symbole (8 ans × ~250 jours)
Split 70/15/15 → ~1400 train / ~300 val / ~300 test
```

### 1.3 Symptômes observés

| Métrique | LSTM WF |
|----------|---------|
| F1_macro | **0.228** |
| F1_short | **0.096** |
| F1_flat  | **0.386** |
| F1_long  | **0.201** |

| Distribution | True | Pred LSTM | Écart |
|-------------|------|-----------|-------|
| Short | 34.6% | **11.2%** | −23.4pp |
| Flat  | 33.9% | **62.5%** | +28.6pp |
| Long  | 31.5% | **26.3%** | −5.2pp |

### 1.4 Diagnostic racine : 5 causes identifiées

#### Cause 1 : Sequence length trop courte (10 jours)

Avec `sequence_length=10` et `forecast_horizon=10`, le modèle voit 10 jours de features pour prédire le rendement à J+10. Le ratio signal/bruit est extrêmement faible : 10 jours de données OHLCV ne contiennent quasiment aucune information prédictive sur le rendement à 10 jours. Le LSTM n'a tout simplement **pas assez de contexte temporel** pour extraire un motif.

> 📐 **Ratio info/horizon** : `seq_len / horizon = 10/10 = 1.0`. La littérature (Fischer & Krauss 2018, Sirignano 2019) utilise typiquement un ratio ≥ 3-5×. Pour un horizon de 10 jours, `seq_len ≥ 30-50` serait plus approprié.

> 💡 **Note** : Ce `sequence_length=10` est **volontaire** — nous sommes en phase de recherche des meilleures combinaisons d'hyperparamètres. On teste rapidement les combinaisons avec une séquence courte pour itérer plus vite. En conditions normales de production, le `sequence_length` sera remis à **40**.

#### Cause 2 : Trop de features pour trop peu de données

47 features × seulement ~1400 séquences d'entraînement → ratio features/échantillons = 1/30. Pour un réseau de neurones, c'est très peu. Le LSTM a `128 × 4 × 47 ≈ 24K` paramètres juste pour la première couche, sans compter le classifieur. Le surapprentissage est quasi-certain, même avec dropout 0.3.

> 🔍 **Explication détaillée** : Ce diagnostic ne dit pas que 8 ans de données (~2000 jours) est insuffisant dans l'absolu — c'est largement assez pour des modèles tabulaires (LightGBM, CatBoost). Le problème est **spécifique au LSTM** et vient du **ratio paramètres/échantillons** :
>
> ```
> 1ère couche LSTM = 4 × (input×hidden + hidden×hidden + hidden)
>                  = 4 × (47×128 + 128×128 + 128)
>                  ≈ 90 112 paramètres
>
> Ratio ≈ 1400 échantillons / 90K paramètres ≈ 0.015
> ```
>
> En deep learning, on vise typiquement un ratio ≥ 1:1, voire 10:1. Ici on est **60× en dessous**. Le LSTM a beaucoup trop de capacité par rapport au nombre d'exemples d'entraînement, ce qui garantit un surapprentissage quelle que soit la régularisation.
>
> **Pourquoi LightGBM/CatBoost ne souffrent pas du même problème ?** Les arbres de décision partitionnent l'espace des features de façon discrète — 1400 échantillons pour 47 features est un ratio tout à fait acceptable (30:1). Ils n'ont pas de problème de « remplissage » d'un espace de paramètres continu comme le LSTM.
>
> **Ce n'est PAS un problème de quantité de données historiques** : ajouter 5 ans de données pré-2018 n'aiderait pas car le contexte de marché a changé et les données trop anciennes ne sont plus représentatives. Les vraies solutions sont :
> 1. **Réduire le nombre de features** : passer de `feature_set=expert` (47 colonnes) à `feature_set=v1` (13 colonnes), ou faire une sélection SHAP
> 2. **Réduire la capacité du LSTM** : `hidden_size=64` au lieu de 128, 1 couche au lieu de 2
> 3. **Augmenter la régularisation** : dropout plus fort (0.5), weight_decay plus élevé (1e-4)
> 4. **Ou accepter que le LSTM n'est pas le bon modèle** pour ce régime de données et se concentrer sur LightGBM/CatBoost

##### 🏦 Comment les professionnels résolvent ce problème

Le problème « trop de features, pas assez d'échantillons par titre » est un défi classique en ML financière. Voici comment l'industrie le traite :

**1. Panel Learning — Un seul modèle pour tous les titres (approche dominante)**

Au lieu d'entraîner un modèle **par symbole** (1400 séquences chacun), on entraîne **un seul modèle sur tous les titres empilés** :

```
200 symboles × 1400 séquences = 280 000 séquences d'entraînement
Ratio → 280K échantillons / 90K paramètres ≈ 3:1 ✅
```

Le Panel Learning existe en deux variantes, mais le paysage réel est plus nuancé :

| Variante | Utilisation dans l'industrie |
|----------|------------------------------|
| **Panel + Arbres (GBM)** | 🏭 **Majorité des funds systématiques** (AQR, Dimensional, WorldQuant, etc.) |
| **Panel + Deep Learning (LSTM/Transformer)** | 🔬 **Funds quant avancés** (Renaissance, Two Sigma, Citadel) + littérature académique |

##### 🏦 Ce que les pros utilisent VRAIMENT — le paysage réel

**1. Arbres boostés (LightGBM > XGBoost >> CatBoost) — le standard de facto**

La majorité des hedge funds systématiques utilisent des arbres boostés comme backbone, y compris pour des modèles panel/globaux. Pourquoi ?

- **LightGBM** est le plus répandu en finance quant → rapidité sur gros volumes (des millions de lignes), gestion native des NaN, excellent sur données tabulaires
- **XGBoost** est le deuxième choix → écosystème plus mature, meilleure documentation, mais plus lent que LightGBM sur grands datasets
- **CatBoost** est rare en finance quant → conçu pour les features catégorielles (type NLP/recommandation), or les features financières sont quasi toutes numériques. Il reste bon, mais n'apporte pas d'avantage décisif par rapport à LightGBM.

> 📖 **Référence** : *« Do Gradient Boosting Machines Beat Deep Learning? »* — Grinsztajn, Oyallon, Varoquaux (2022, NeurIPS). Sur données tabulaires (ce qui est le cas des features OHLCV cross-sectionnelles), les GBM surpassent les réseaux de neurones dans 90%+ des benchmarks. Ce résultat a été largement confirmé par la communauté quant.

**2. Deep Learning (Transformers > LSTM) — pour ceux qui ont l'infrastructure**

Les funds qui utilisent du DL pour du price forecasting (Renaissance, Two Sigma, Citadel, certains desks chez JPM/GS) ne font pas du « LSTM sur 47 features ». Ils font :

- **Des Transformers** sur des séquences longues (100-500 pas de temps) avec des embeddings de stock appris → l'architecture *TabTransformer* ou *FT-Transformer* est devenue le standard
- **Des CNN/TCN** pour du order book (carnet d'ordres intraday, milliers de ticks) → LSTM est trop lent et trop instable
- **Du multi-modal** : prix + news NLP + images satellite → le DL est indispensable pour fusionner ces sources hétérogènes

Le **LSTM pur sur données daily OHLCV**, c'est surtout le standard **académique** (Gu-Kelly-Xiu 2020, Sirignano-Cont 2019), pas vraiment le standard industriel. Les pros qui font du DL sont passés aux Transformers depuis ~2020.

> ⚠️ **Question légitime : un Transformer est-il plus performant que LightGBM ?**
>
> La réponse dépend du régime de données, et elle est moins tranchée qu'on ne le croit :
>
> | Régime de données | Vainqueur | Écart |
> |-------------------|-----------|-------|
> | Tabulaire < 100 features, < 1M lignes | **LightGBM** 🥇 | GBM gagne dans ~90% des cas |
> | Tabulaire > 500 features, > 10M lignes | **FT-Transformer** ≈ LightGBM | Écart < 2%, pas décisif |
> | Séquentiel long (100+ timesteps) | **Transformer** 🥇 | Les arbres ne modélisent pas le temps |
> | Multi-modal (prix + texte + image) | **Transformer** 🥇 | DL indispensable |
>
> 📖 **Référence clé** : *« Why do tree-based models still outperform deep learning on tabular data? »* — Grinsztajn, Oyallon, Varoquaux (2022, NeurIPS). Même les Transformers les plus récents (FT-Transformer, TabTransformer, SAINT) ne battent pas **systématiquement** un LightGBM bien réglé sur des données tabulaires classiques. L'écart se réduit avec la taille du dataset, mais pour la plupart des use-cases quant (< 500 features, < 10M lignes), **LightGBM reste le meilleur choix coût/bénéfice**.
>
> **Quelle infrastructure faut-il pour que le DL batte les arbres ?**
>
> ```
> ┌─────────────────────────────────────────────────────────────────┐
> │  Ce qu'il faut pour que Transformers > LightGBM                  │
> ├─────────────────────────────────────────────────────────────────┤
> │  💻 GPU A100/H100 (40-80 GB VRAM) — pas une carte gaming         │
> │  📊 Des centaines de millions de séquences d'entraînement        │
> │  🏗️  Distributed training multi-GPU / multi-nœud                │
> │  👨‍🔬 Une équipe ML dediée (architecture design, tuning, debug)  │
> │  ⏱️  Des heures/jours d'entraînement par modèle                  │
> │  💰 Budget annuel : $500K-$2M en compute + salaires              │
> ├─────────────────────────────────────────────────────────────────┤
> │  Ce qu'il faut pour LightGBM                                     │
> ├─────────────────────────────────────────────────────────────────┤
> │  💻 Un CPU 32 cœurs + 64 GB RAM (un bon serveur, pas un cluster) │
> │  📊 Quelques centaines de milliers de lignes                     │
> │  ⏱️  Quelques minutes d'entraînement                             │
> │  💰 Budget : $0 si tu as déjà le serveur                         │
> └─────────────────────────────────────────────────────────────────┘
> ```
>
> **Conclusion** : Pour ton cas (200 titres × 2000 jours = 400K lignes, 47 features, horizon 10j), un Transformer n'apporterait **aucun gain** par rapport à LightGBM — et coûterait 100× plus cher en infra et complexité. Les funds qui utilisent des Transformers le font parce qu'ils ont des **milliards** de lignes (tick data, order book, données alternatives) que les arbres ne peuvent tout simplement pas ingérer. Ce n'est pas un problème de « sophistication du modèle », c'est un problème de **volume de données**.

**3. Le consensus pratique (2024-2026)**

```
┌────────────────────────────────────────────────────────────┐
│  Données tabulaires (OHLCV, features calculées)              │
│  → LightGBM / XGBoost                                       │
│  → 90%+ des funds systématiques                             │
├────────────────────────────────────────────────────────────┤
│  Données séquentielles massives (order book, ticks)          │
│  → Transformers / TCN                                       │
│  → HFT, market making                                      │
├────────────────────────────────────────────────────────────┤
│  Données alternatives (NLP news, images satellite, macro)    │
│  → Deep Learning multi-modal                                │
│  → Funds avec infrastructure ML lourde                      │
└────────────────────────────────────────────────────────────┘
```

##### 🎯 Et pour ton cas ?

Tu n'as **pas** XGBoost dans le codebase — ni pour le Global Model, ni pour les modèles per-symbol. La liste déroulante « Backend du modèle global » dans l'IHM propose uniquement **LightGBM** et **CatBoost**, et c'est cohérent avec le code (`global_model.py:165` — `model_name: str = "catboost"  # catboost | lightgbm`).

C'est un choix technique parfaitement défendable :

| Backend | Disponible ? | Usage en finance quant |
|---------|:-----------:|------------------------|
| **LightGBM** | ✅ Dans le dropdown | 🥇 Standard de facto — rapidité, gestion native des NaN |
| **CatBoost** | ✅ Dans le dropdown | 🟡 Rare en finance, conçu pour les features catégorielles |
| **XGBoost** | ❌ Non implémenté | 🥈 Deuxième choix standard — plus lent, écosystème mature |

Est-ce un problème de ne pas avoir XGBoost ? **Non.** LightGBM et XGBoost ont des performances quasi-identiques sur données tabulaires, et LightGBM est plus rapide. Ajouter XGBoost n'apporterait pas de gain de performance.

> 💡 **Récapitulatif — ce que tu as vraiment :**
>
> | Niveau | Modèles disponibles | Type |
> |--------|-------------------|------|
> | **Global Model** (panel, cross-sectionnel) | LightGBM, CatBoost | 🌳 Arbres uniquement |
> | **Per-symbol** (un modèle par titre) | LightGBM, CatBoost, LSTM | 🌳 Arbres + 🧠 LSTM |
>
> Le LSTM n'existe **qu'au niveau per-symbol**, pas dans le Global Model. Le Global Model est 100% arbres, et c'est très bien comme ça.

Références académiques classiques du panel learning :
- **Gu, Kelly, Xiu (2020)** — *« Empirical Asset Pricing via Machine Learning »*, Review of Financial Studies : MLP/LSTM sur panel, le papier fondateur.
- **Sirignano & Cont (2019)** — *« Universal features of price formation in financial markets »* : LSTM entraîné sur l'intégralité du carnet d'ordres de 1000+ actions NASDAQ, stock embedding pour identifier chaque titre.

**2. Transfer Learning / Pre-training**

C'est ce que font les grands hedge funds (Two Sigma, Renaissance, Citadel) :
- **Phase 1** : Pré-entraîner un LSTM/Transformer sur un univers massif (toutes les actions US + données synthétiques)
- **Phase 2** : Fine-tuner par secteur ou par titre avec les données spécifiques

**3. Architectures plus économes en paramètres**

- **TCN (Temporal Convolutional Networks)** : Moins de paramètres qu'un LSTM, meilleurs sur séquences courtes, pas de problème de vanishing gradient
- **Attention simple sans LSTM** : Juste un `MultiHeadAttention` sur les 10 timesteps → ~5K paramètres au lieu de 90K
- **GRU** au lieu de LSTM : 25% de paramètres en moins pour des performances équivalentes

**4. Data Augmentation pour séries temporelles**

- **Bootstrap de séquences** : échantillonner avec remplacement des sous-séquences
- **Injection de bruit** : ajouter un bruit gaussien calibré sur la volatilité réalisée
- **TimeGAN / TimeVAE** : générer des séquences synthétiques réalistes pour augmenter le dataset

**5. Abandonner le DL et utiliser des arbres boostés**

C'est le choix pragmatique de nombreux funds (AQR, WorldQuant) : LightGBM/CatBoost/XGBoost surperforment systématiquement les LSTM/Transformers sur des données tabulaires avec < 10K échantillons par prédiction. La raison est simple : les arbres n'ont pas de problème de ratio paramètres/échantillons.

> 📖 **Référence clé** : *« Deep Learning for Asset Pricing »* — Gu, Kelly, Xiu (2020). Ils montrent qu'un simple MLP à 3 couches entraîné sur tout le panel (30 000+ titres-mois) surpasse tous les modèles linéaires, mais que les arbres boostés restent compétitifs voire supérieurs selon les métriques.

##### 🎯 Application à ton cas — Quelle solution est la plus adaptée au swing trading ?

> ⚠️ **Clarification importante** : Le Global Model actuel (`global_model.py`, Approche 2 — Stacking, Sprint 2026-07) est un modèle **tabulaire** (LightGBM ou CatBoost au choix, pas de LSTM). C'est pour cela que dans l'IHM (page pipeline), le menu déroulant « Backend du modèle global » propose uniquement **LightGBM** et **CatBoost** — et pas LSTM. Le Global Model applique le principe du Panel Learning (un seul modèle sur tous les titres), mais avec des arbres boostés, pas un réseau de neurones.
>
> ```
> Global Model actuel     → Panel Learning + Arbres (LightGBM/CatBoost) ✅ déjà en place
> Global Model LSTM futur → Panel Learning + LSTM (à développer si besoin)
> ```
>
> Et c'est parfaitement cohérent : les arbres n'ont PAS le problème de ratio paramètres/échantillons (Cause 2). Le Panel Learning résout le problème pour le LSTM, mais le Global Model n'en a pas besoin puisqu'il utilise des arbres. Le Global Model résout plutôt un autre problème : capter les signaux **cross-sectionnels** (rang relatif, dispersion, breadth) qu'un modèle per-symbol ne peut pas voir.

Voici le classement des solutions par **proximité à ton architecture actuelle** et **pertinence pour le swing trading** :

| Rang | Solution | Proximité | Pertinence swing | Effort |
|------|----------|-----------|------------------|--------|
| 🥇 | **Panel Learning (Global Model existant)** | ⭐⭐⭐ Déjà codé | ⭐⭐⭐ Idéal | Faible — activer les flags |
| 🥈 | **Abandonner LSTM, tout miser sur GBM/CatBoost** | ⭐⭐⭐ Déjà codé | ⭐⭐ Bon | Nul |
| 🥉 | **Simplifier l'archi LSTM** (GRU, attention pure) | ⭐⭐ Code à adapter | ⭐⭐ Bon | Moyen |
| 4 | **Transfer Learning** | ⭐ À construire | ⭐⭐⭐ Idéal | Lourd |
| 5 | **Data Augmentation** | ⭐ À construire | ⭐ Utile | Moyen |

**Pourquoi le Panel Learning est le plus adapté au swing trading ?**

Le swing trading (horizon 10 jours) est fondamentalement une problématique **cross-sectionnelle** : tu ne cherches pas juste à savoir « est-ce que AAPL va monter ? » mais « parmi 200 titres, lesquels vont le plus monter dans 10 jours ? ». Le Global Model répond exactement à cette question : il apprend les patterns de **sous-performance/surperformance relative** entre titres.

```
Per-symbol LSTM : "AAPL va-t-il monter de +3% dans 10 jours ?" → réponse isolée
Global Model    : "AAPL est-il dans le top 35% des titres pour le rendement à 10 jours ?" → réponse relative
```

**Plan d'action recommandé — MIS À JOUR après test réel :**

> ⚠️ **Résultat du test A/B (24 juillet 2026)** : Deux batchs ont été lancés pour comparer l'impact du Global Model :
>
> | Batch | Flags | Champions |
> |-------|-------|-----------|
> | `22b4ca` | `--enable-global-model --enable-global-stacking` (sans challenger) | lightgbm 112, catboost 68, lstm 20 |
> | `9493ca` | `--enable-global-model --enable-global-stacking --enable-global-challenge` | lightgbm 112, catboost 68, lstm 20 |
>
> **Résultat : IDENTIQUE. Le Global Model n'a remporté AUCUN symbole sur 200.** Il n'apparaît même pas dans la liste des champions — lightgbm, catboost, et lstm_attention restent les seuls vainqueurs, dans les mêmes proportions.
>
> **Pourquoi le Global Model n'apporte rien ?**
>
> 1. **Le Global Model prédit UNIQUEMENT `global_pred_long`** — une prédiction directionnelle unique (probabilité d'être dans le top 35% long). Il ne produit pas de prédictions short/flat/long séparées comme les modèles per-symbol. Cette feature unique est noyée parmi les 47 autres features.
>
> 2. **Le per-symbol LightGBM capture déjà le même signal** — les features cross-sectionnelles (rangs, secteurs) sont déjà incluses dans les 47 colonnes du per-symbol. Le Global Model n'apporte pas d'information **nouvelle**, juste une reformulation de ce que le per-symbol voit déjà.
>
> 3. **Le Global Model est un arbre comme le per-symbol** — pas de diversité d'architecture. Un LightGBM qui stack un autre LightGBM n'ajoute rien. Pour que le stacking fonctionne, il faut des modèles de natures différentes (ex: un Transformer global + un LightGBM per-symbol).

**Plan d'action révisé :**

1. ~~Activer le Global Model comme challenger~~ → ❌ **Testé, aucun impact. Désactiver.**
2. **Court terme** : Corriger les class_weights du LSTM + seq_len à 40 + patience à 10 (inchangé)
3. **Moyen terme** : SHAP analysis sur LightGBM pour identifier les features inutiles, réduire de 47 → ~20
4. **Si le LSTM reste mauvais après correctifs** → le désactiver, tout miser sur LightGBM/CatBoost

> ✅ **Bilan révisé — Ce que tu as à faire :**
>
> | Action | Effort | Statut |
> |--------|--------|--------|
> | ~~Activer le Global Model~~ | — | ❌ Testé, 0 gain — abandonner |
> | Interactions features × régime | 🔧 Code | ✅ Fait (features.py + trainer.py) |
> | Sample weighting par récence | 🔧 Code | ✅ Fait (tabular_baseline.py, GBM/CatBoost only) |
> | LSTM hardcodé v1 (29 features) | 🔧 Code | ✅ Fait (trainer.py) |
> | Corriger les class_weights du LSTM | ⚡ 3 flags CLI | À faire |
> | Passer `seq_len` à 40, `patience` à 10 | ⚡ 2 flags CLI | Déjà prévu |
> | SHAP + réduire features (47 → ~20) | 🔧 Code | Moyen terme |
> | Si LSTM tjs mauvais → désactiver | ⚡ 1 flag CLI | Plan B |
>
> **Pas besoin de** : Global Model, XGBoost, Transformer. Le duo LightGBM + CatBoost avec interactions régime fait déjà le job. L'énergie restante va sur le **backtest avec coûts**.

#### Cause 3 : Normalisation par split, pas globale

Dans `_run_walk_forward_validation` (trainer.py:964-965), un `FeatureScaler` est fit **sur chaque split** indépendamment. Les features comme `sma200_distance` ou `regime_bull_market` ont des distributions très différentes selon la période (bull market 2018-2021 vs bear 2022). Le scaling par split atténue ce problème mais introduit une non-stationnarité : les mêmes valeurs brutes peuvent avoir des significations différentes d'un split à l'autre.

> 🔍 **Explication détaillée** : Le `FeatureScaler` fait une z-normalization classique `(x - mean) / std`. Comme chaque split a son propre scaler fit sur sa propre période d'entraînement, la **même valeur brute** peut être normalisée très différemment d'un split à l'autre :
>
> | Période | Marché | Moyenne `sma200_distance` | Écart-type |
> |---------|--------|---------------------------|------------|
> | Split 1 (2018-2020) | Bull market | +8% | 12% |
> | Split 2 (2020-2022) | COVID + reprise | +12% | 18% |
> | Split 3 (2022-2024) | Bear puis recovery | −2% | 15% |
>
> Une valeur brute de `sma200_distance = +5%` devient alors :
> - **z ≈ (5−8)/12 = −0.25** dans le split 1
> - **z ≈ (5−12)/18 = −0.39** dans le split 2
> - **z ≈ (5−(−2))/15 = +0.47** dans le split 3
>
> La **même condition de marché** (+5% au-dessus de la SMA200) donne des valeurs normalisées **complètement différentes** selon le split. Le modèle ne peut pas apprendre une relation stable entre la feature et le target à travers les splits.
>
> **Solutions proposées :**
> 1. **Scaler global** : fit le `FeatureScaler` une seule fois sur tout l'historique (ou une période de référence fixe comme les 2 premières années), puis utiliser ce même scaler pour tous les splits. Avantage : une valeur brute → toujours le même z-score. Inconvénient : si les distributions dérivent fortement, les z-scores peuvent sortir de l'intervalle habituel.
> 2. **Expanding window scaler** : fit cumulatif — pour le split N, fit sur toutes les données jusqu'au split N (et pas seulement le train du split N). Compromis entre adaptation et stabilité.
> 3. **RobustScaler** : remplacer mean/std par médiane/IQR, moins sensible aux valeurs extrêmes et aux changements de régime.
>
> ⚠️ **Note** : La normalisation par split est en réalité une **bonne pratique** en walk-forward validation car elle évite le look-ahead bias. Ce diagnostic est donc à relativiser — les Causes 1, 2, 4 et 5 ont un impact bien plus fort sur la performance du LSTM.
>
> **Cette cause impacte-t-elle aussi LightGBM et CatBoost ?**
>
> **Non.** Les arbres de décision sont **insensibles à toute transformation monotone** des features, et la z-normalization `(x - mean) / std` est monotone (si $x_1 > x_2$, alors $z_1 > z_2$ puisque $\sigma > 0$). Concrètement :
>
> ```
> LightGBM sur valeurs brutes :  split à momentum_20 > 0.12
> LightGBM sur valeurs normalisées : split à momentum_20_z > 1.1
>                                   ↑ Même arbre, seuil différent, décisions identiques
> ```
>
> Le seul vrai problème pour les arbres n'est pas la normalisation, mais le **changement de régime** : un split appris en bull market (« momentum > 15% → long ») peut devenir sous-optimal en bear market. Mais ce problème existe **avec ou sans normalisation** — c'est inhérent aux données, pas au scaler.

##### 🔧 Comment résoudre le problème de changement de régime pour GBM/CatBoost ?

Le problème : un arbre entraîné sur 2018-2025 (bull market) apprend des règles comme « momentum_20 > 12% → long » qui ne fonctionnent plus en bear market (2022). Il faut que le modèle sache **dans quel régime il se trouve** pour adapter ses décisions.

**Solutions, classées par impact :**

**1. Interactions features × régime (🥇 le plus efficace, sans changer le pipeline)**

Les arbres savent naturellement créer des interactions, mais seulement si les deux variables sont présentes. En ajoutant des features d'interaction explicites, tu facilites le travail :

```python
# Ajouter dans features.py
df["momentum_20_x_bull"] = df["momentum_20"] * df["regime_bull_market"]
df["momentum_20_x_risk_off"] = df["momentum_20"] * df["regime_risk_off"]
df["relative_strength_20_x_bull"] = df["relative_strength_20"] * df["regime_bull_market"]
df["relative_strength_20_x_risk_off"] = df["relative_strength_20"] * df["regime_risk_off"]
# ... pour les 5-10 features les plus importantes (SHAP)
```

L'arbre peut alors apprendre : `momentum_20_x_bull > 0.08 → long` (valable uniquement en bull) vs `momentum_20_x_risk_off > 0.02 → short` (valable en risk-off). C'est la solution la plus simple et la plus efficace — ~15 lignes de code, zéro changement de pipeline.

**2. Sample weighting par récence (🥈 simple, efficace)**

Donner plus de poids aux données récentes pour que le modèle s'adapte naturellement au régime actuel :

```python
# Dans le trainer GBM/CatBoost
today = df["date"].max()
df["sample_weight"] = np.exp(-(today - df["date"]).dt.days / 365)  # demi-vie 1 an
model.fit(X, y, sample_weight=df["sample_weight"])
```

LightGBM et CatBoost supportent `sample_weight` nativement. Une demi-vie de 1-2 ans est un bon point de départ pour du swing trading.

**3. Retraining fréquent (déjà en place via le walk-forward)**

Ton walk-forward tous les ~6 mois (126 jours de step) est déjà une forme d'adaptation. Tu peux le rendre plus fréquent (tous les 3 mois) si les changements de régime sont rapides.

**4. Modèles séparés par régime (plus lourd, mais puissant)**

```python
bull_model = LightGBM().fit(data[data["regime_bull_market"] > 0.5])
bear_model = LightGBM().fit(data[data["regime_bull_market"] < 0.5])
# En prédiction : choisir le modèle selon le régime courant
```

Inconvénient : divise les données par 2, donc nécessite un historique long.

##### 🏦 Comment les professionnels gèrent le changement de régime ?

| Approche | Qui l'utilise | Détail |
|----------|--------------|--------|
| **Features cross-sectionnelles (rangs)** | AQR, Dimensional, WorldQuant, tous les funds systématiques | Les rangs sont **naturellement invariants au régime** : le 90ème percentile de momentum a la même signification en bull qu'en bear. C'est LA raison n°1 pour laquelle les pros utilisent des rangs plutôt que des valeurs brutes. |
| **Retraining fréquent** | Tous | Re-estimation mensuelle ou trimestrielle des modèles. Le walk-forward que tu fais déjà est la version « propre » de ça. |
| **Interactions features × régime** | Approche standard en ML | Pas spécifique à la finance, mais très efficace. Interactions explicites entre features techniques et indicateurs de régime. |
| **Ensemble de modèles par régime** | Approche avancée | Des modèles spécialisés par régime (bull, bear, sideways, high vol, low vol) avec un méta-modèle qui les pondère. |
| **Online learning / decay** | Stat arb, HFT | Mise à jour continue des modèles avec un facteur d'oubli exponentiel. |
| **Régimes de Markov (HMM)** | Recherche quantitative | Modélisation probabiliste du régime courant, le modèle reçoit `P(bull)` et `P(bear)` comme features continues. |

> 💡 **Recommandation pour ton cas — IMPLÉMENTÉ le 24 juillet 2026** :
>
> ✅ **Solution 1 (interactions features × régime) est en place.** 18 features d'interaction (`momentum_20_x_bull`, `relative_strength_20_x_risk_off`, etc.) sont calculées automatiquement dans `features.py` quand `feature_set="expert"` et un benchmark est disponible.
>
> ✅ **LSTM hardcodé en v1.** `trainer.py` force `feature_set="v1"` pour le LSTM (29 features : 13 v1 + 16 cross-sectional), ignorant le flag CLI `--feature-set`. Les 18 interactions sont donc **invisibles** pour le LSTM.
>
> ✅ **GBM/CatBoost utilisent `--feature-set` normalement.** Avec `--feature-set expert`, ils reçoivent 65 features (31 expert + 16 cross + 18 interactions).
>
> ```
> LSTM (hardcodé v1)          : 29 features, pas d'interactions régime
> LightGBM/CatBoost (expert)  : 65 features, 18 interactions régime actives
> ```
>
> ✅ **Solution 2 (sample weighting par récence) est en place.** `tabular_baseline.py` applique des poids exponentiels décroissants (demi-vie = 1 an) aux deux appels `model.fit()` (main + walk-forward). Les données du jour le plus récent pèsent 1.0, celles d'il y a 1 an pèsent 0.37, celles d'il y a 2 ans pèsent 0.14. LightGBM et CatBoost supportent `sample_weight` nativement. **Uniquement pour GBM/CatBoost** — le LSTM n'est pas concerné.
>
> | Modèle | Features | Interactions régime |
> |--------|----------|:---:|
> | **LSTM** | 29 (v1 + cross) | ❌ Hardcodé v1 |
> | **LightGBM** | 65 (expert + cross + interactions) | ✅ |
> | **CatBoost** | 65 (expert + cross + interactions) | ✅ |
>
> 💡 **Note IHM** : Le flag `--feature-set` de l'IHM contrôle maintenant **uniquement** GBM/CatBoost. Le LSTM est automatiquement en v1, quoi que tu mettes dans le dropdown.

##### 🏦 Comment les professionnels résolvent ce problème

La non-stationnarité des features est LE problème central de la finance quantitative. Voici les approches utilisées par l'industrie :

**1. Cross-sectional ranking — LE standard en finance quantitative (approche dominante)**

Au lieu de normaliser les features dans le temps (z-score par split), on les **classe transversalement** chaque jour :

```
Jour J : 200 titres
├── Titre A : momentum_20 = +15% → rank = 0.98 (98ème percentile)
├── Titre B : momentum_20 = +3%  → rank = 0.45 (45ème percentile)
└── Titre C : momentum_20 = -8%  → rank = 0.05 (5ème percentile)
```

Le rank est **toujours** dans [0, 1] quelle que soit la période. Un titre au 98ème percentile de momentum a la même signification en bull market qu'en bear market.

C'est l'approche de **AQR, Dimensional Fund Advisors, et de la quasi-totalité des funds systématiques**. Les features `_rank` existent déjà dans ton code (`ret_20_rank`, `relative_strength_20_rank`, etc.) — ce sont tes 8 colonnes cross-sectionnelles.

> 📖 **Référence** : *« 101 Formulaic Alphas »* — Kakushadze (2016). La plupart des alphas quant sont définis comme des rangs cross-sectionnels, pas des valeurs brutes.

**2. Fractional Differentiation (Marcos Lopez de Prado)**

Rendre les features stationnaires **sans perdre la mémoire** du signal. La différenciation classique (prix → rendement) perd toute l'information de tendance long terme. La différenciation fractionnaire trouve le `d` minimal (entre 0 et 1) qui rend la série stationnaire tout en préservant un maximum de mémoire :

```
Prix        → d=0 → non stationnaire, mémoire infinie
Rendement   → d=1 → stationnaire, mémoire nulle
Fractionnel → d=0.35 → stationnaire, conserve ~65% de la mémoire long terme
```

> 📖 **Référence** : *« Advances in Financial Machine Learning »* — Lopez de Prado (2018), Chapitre 5.

**3. Rolling window normalization (compromis pragmatique)**

Fit le scaler sur une **longue fenêtre glissante** (ex: 5 ans) plutôt que sur le split courant. Assez long pour être stable, assez récent pour refléter le régime actuel :

```python
# Au lieu de fit sur split.train (2 ans)
scaler.fit(df.rolling(5*252).mean())  # fit sur 5 ans glissants
```

**4. Ne pas normaliser du tout (arbres boostés)**

LightGBM, CatBoost et XGBoost sont **insensibles à l'échelle des features** car ils découpent sur des seuils bruts. Si ton modèle final est un arbre, la normalisation est superflue. Beaucoup de professionnels ne normalisent que pour les réseaux de neurones, pas pour les arbres.

**5. Features économiquement stationnaires by design**

La meilleure normalisation est celle dont on n'a pas besoin. Les professionnels conçoivent leurs features pour qu'elles soient **naturellement stationnaires** :
- Des **ratios** plutôt que des valeurs absolues (ex: `market_cap / sector_median_market_cap`)
- Des **spreads** plutôt que des prix (ex: `stock_return - sector_return`)
- Des **rangs** plutôt que des scores bruts
- Des **indicateurs binaires** pour les régimes (ex: `is_above_sma200` plutôt que `sma200_distance`)

> 💡 **Pour ton cas** : La solution la plus simple et la plus impactante est d'**utiliser massivement les features de rang cross-sectionnel que tu as déjà** (`_rank`, `_rank_xs`) et de réduire l'utilisation des features brutes non stationnaires (`sma200_distance`, `momentum_20`, etc.) pour le LSTM.

##### 🎯 Application à ton cas — Cross-sectional ranking : LSTM uniquement ou aussi GBM/CatBoost ?

La réponse est nuancée et dépend du type de modèle :

| Aspect | LSTM | LightGBM / CatBoost |
|--------|------|---------------------|
| **Sensibilité à l'échelle** | 🔴 Très sensible — la z-normalization est indispensable | 🟢 Insensible — les arbres splitent sur des valeurs brutes |
| **Sensibilité à la non-stationnarité** | 🔴 Très sensible — un changement de分布 degrade les poids appris | 🟡 Modérément sensible — les splits appris en bull market peuvent ne plus être optimaux en bear |
| **Bénéfice du cross-sectional ranking** | 🔴 **CRITIQUE** — réduit l'input dim + rend les features stationnaires | 🟡 **Bénéfique mais pas indispensable** — améliore la généralisation inter-régimes |
| **Perte d'information avec les rangs** | 🟡 Acceptable — de toute façon le LSTM n'a pas assez d'échantillons pour exploiter la magnitude | 🔴 **Risque de perte de signal** — les arbres savent exploiter les magnitudes (ex: momentum +50% vs +5%, même rang) |

**Recommandation : stratégie différenciée LSTM vs GBM**

```
┌─────────────────────────────────────────────────────────┐
│ LSTM                                                     │
│ → Features : UNIQUEMENT les rangs cross-sectionnels      │
│   (8 _rank + 8 secteur + 6 global_exclusive = 22 cols)   │
│ → Pourquoi : réduction drastique de l'input dim (22       │
│   au lieu de 47), features déjà stationnaires, pas        │
│   besoin de scaler → Cause 2 + Cause 3 résolues ensemble  │
├─────────────────────────────────────────────────────────┤
│ LightGBM / CatBoost                                       │
│ → Features : rangs cross-sectionnels + features brutes    │
│   (22 rangs/secteur + 25 brutes = 47 cols, statu quo)     │
│ → Pourquoi : les arbres gèrent bien la dimension, et      │
│   les valeurs brutes apportent de la magnitude que les    │
│   rangs ne capturent pas                                  │
└─────────────────────────────────────────────────────────┘
```

**Pourquoi c'est la meilleure approche pour le swing trading :**

Le swing trading (horizon 10j) repose sur deux types de signaux :
1. **Signal de timing** (quand entrer/sortir sur UN titre) → les features brutes excellent (ex: `rsi_14` extrême, `range_position_20` bas)
2. **Signal de sélection** (quel titre choisir parmi N) → les rangs cross-sectionnels excellent (ex: `ret_20_rank` élevé, `relative_strength_20_rank` haut)

Les arbres (GBM/CatBoost) peuvent exploiter les DEUX simultanément. Le LSTM, avec ses contraintes d'échantillons, doit se concentrer sur le signal de sélection (rangs) qui est plus robuste et plus stationnaire.

#### Cause 4 : Pas de class_weight différencié

```python
# modelFactory/model.py:113
ternary_weight_short=1.0, ternary_weight_flat=1.0, ternary_weight_long=1.0
```

Avec des classes naturellement déséquilibrées (le flat est structurellement plus fréquent que les extrêmes), le modèle n'a **aucune incitation** à sortir de la zone de confort « flat ». La `CrossEntropyLoss` non pondérée converge naturellement vers la classe majoritaire quand le signal est faible — c'est exactement ce qu'on observe (62.5% de prédictions flat).

> ✅ **Action décidée** : Mettre en place des poids différenciés. Commande recommandée :
> ```powershell
> --ternary-weight-short 1.5 --ternary-weight-long 1.5 --ternary-weight-flat 0.7
> ```

#### Cause 5 : Early stopping trop agressif

`patience=3` avec `max_epochs=20`. Si le modèle ne progresse pas en 3 epochs sur le `val_loss`, il s'arrête. Or, avec le bruit élevé des données financières, la loss de validation est très bruitée et peut stagner pendant 3-4 epochs avant de redescendre. Le modèle n'a probablement même pas le temps de converger.

> 💡 **Note** : Ce réglage agressif est **volontaire** et partage la même origine que la Cause 1 — nous sommes en phase de recherche des meilleures combinaisons. On teste rapidement, donc `max_epochs=20` et `patience=3` permettent d'itérer vite. En production, on passera à `max_epochs=50` et `patience=10`.

### 1.5 Vérification dans le code

```python
# modelFactory/trainer.py:1350 — Le LSTM est entraîné sur TOUT le split
# train/val/test (pas de walk-forward pour le LSTM lui-même).
# Le walk-forward est fait SÉPARÉMENT dans _run_walk_forward_validation()
# qui ré-entraîne un LSTM from scratch sur chaque split WF.
```

Le LSTM est donc ré-entraîné **5 fois** par symbole (1 train/test/val + 3 splits WF + 1 final fit), mais avec `max_epochs=20` et `patience=3`, chaque entraînement individuel est trop court.

### 1.6 Solutions proposées

| Solution | Détail | Priorité |
|----------|--------|----------|
| **A. Augmenter `sequence_length`** | Passer à 30-60 (`--sequence-length 40`) | 🔴 Critique |
| **B. Réduire le nombre de features** | Utiliser seulement `feature_set=v1` (13 colonnes) ou faire une sélection de features | 🔴 Critique |
| **C. Class weights asymétriques** | `--ternary-weight-short 1.5 --ternary-weight-long 1.5 --ternary-weight-flat 0.7` | 🟡 Important |
| **D. Augmenter patience** | `--patience 10` | 🟡 Important |
| **E. Plus d'epochs** | `--max-epochs 50` | 🟢 Nice-to-have |
| **F. Label smoothing** | Ajouter `label_smoothing=0.1` dans `CrossEntropyLoss` | 🟢 Nice-to-have |
| **G. BatchNorm après LSTM** | Ajouter `nn.BatchNorm1d` avant le classifieur pour stabiliser | 🟢 Nice-to-have |

### 1.7 Commande de test recommandée

```powershell
python -m modelFactory --mode train --target-mode ternary \
  --sequence-length 40 --hidden-size 64 \
  --max-epochs 50 --patience 10 \
  --ternary-weight-short 1.5 --ternary-weight-long 1.5 --ternary-weight-flat 0.7 \
  --feature-set v1 \
  --symbol-source ticket-recherche --max-workers 2 \
  --comment test_lstm_fix
```

> ⚠️ Si après ces correctifs le LSTM reste sous 0.25 F1_macro WF, il faut **envisager de le désactiver** du championnat (`--default-champion lightgbm`) et concentrer les efforts sur les modèles tabulaires.

---

## 2. Diagnostic du biais LONG

### 2.1 Mesure du biais

| Modèle | True Long WF | Pred Long WF | Biais |
|--------|-------------|-------------|-------|
| LightGBM | 31.8% | **46.9%** | +15.1pp |
| CatBoost | 31.8% | **47.8%** | +16.0pp |
| LSTM | 31.5% | 26.3% | −5.2pp (biais flat) |

Les deux modèles tabulaires sur-prédisent `long` de ~50%. En parallèle, ils sous-prédisent `short` (−6.6pp pour LightGBM, −9.2pp pour CatBoost) et `flat` (−8.5pp et −6.8pp).

### 2.2 Cause racine n°1 : Période d'entraînement structurellement haussière

```
Training : 2018-01-01 → 2025-12-31
SPY sur la période : +160% (environ)
```

Le biais long est **structurel** : sur 8 ans de bull market quasi-ininterrompu (hors COVID flash crash de mars 2020), la classe `long` est sur-représentée dans les issues gagnantes. Le modèle apprend que « quand il y a un signal, c'est plus souvent long que short ».

### 2.3 Cause racine n°2 : Labeling fixed_horizon sans ajustement au marché

```python
# modelFactory/labeling.py — commande utilisée
--target-up-threshold 0.03    # +3% → long
--target-down-threshold -0.03 # -3% → short
--ternary-threshold-short 0.35  # bottom 35% percentile → short
--ternary-threshold-long 0.35   # top 35% percentile → long
```

Le labeling est basé sur :
1. Un **percentile** (top/bottom 35%) → les classes sont forcément équilibrées **dans l'échantillon**
2. Un **seuil absolu** de ±3% → filtre additionnel

Mais le problème vient du **future return** sous-jacent. En bull market, les rendements positifs sont plus fréquents et plus amples. Même si les percentiles forcent l'équilibre, la distribution des retours futurs est asymétrique : un « top 35% » en 2020 n'a pas la même signification qu'en 2022.

### 2.4 Cause racine n°3 : Class weights égaux

```python
# Commande : --ternary-weight-short 1.0 --ternary-weight-flat 1.0 --ternary-weight-long 1.0
```

Avec des poids égaux, le modèle n'est pas pénalisé pour sa sous-prédiction des shorts. LightGBM et CatBoost optimisent la log-loss globale, qui est dominée par les erreurs sur les classes majoritaires en sortie (long, qui est plus facile à prédire).

### 2.5 Cause racine n°4 : Absence de calibration asymétrique

La calibration actuelle utilise `TemperatureScaler` (ternaire) ou `PlattCalibrator` (binaire). Ces deux méthodes sont **symétriques** : elles ajustent les probabilités globalement sans corriger un biais directionnel. Il n'existe pas de mécanisme pour forcer `P(short) ≈ P(long)` en sortie.

### 2.6 Cause racine n°5 : TernaryDecisionPolicy symétrique

```python
# core/ternary_decision_policy.py — commande
--ternary-threshold-short 0.35 --ternary-threshold-long 0.35 --ternary-top2-margin 0.02
```

Les seuils de décision sont identiques pour long et short (0.35). Si le modèle est structurellement plus confiant sur les longs (probabilité calibrée plus élevée), plus de longs passeront le seuil que de shorts.

### 2.7 Solutions proposées

| Solution | Détail | Impact estimé |
|----------|--------|---------------|
| **A. Class weights asymétriques** | `--ternary-weight-short 1.8 --ternary-weight-long 1.0 --ternary-weight-flat 1.2` | Réduction biais 30-50% |
| **B. Seuils de décision asymétriques** | `--ternary-threshold-short 0.30 --ternary-threshold-long 0.40` | Réduction biais 20-30% |
| **C. Post-processing : calibration par quantile** | Forcer `P(short) ≈ P(long)` en sortie via un mapping quantile par date | Réduction biais 80%+ |
| **D. Entraînement sur sous-périodes** | Inclure 2008, 2020, 2022 comme périodes significatives | Amélioration robustesse |
| **E. Feature de régime de marché** | Les features `regime_bull_market` et `regime_risk_off` existent déjà → vérifier leur SHAP importance | Diagnostique |

### 2.8 Code à modifier

**Option A — Commande immédiate (sans changement de code)** :
```powershell
--ternary-weight-short 1.8 --ternary-weight-long 1.0 --ternary-weight-flat 1.2
```

**Option B — Modification de `TernaryDecisionPolicy` (fichier `core/ternary_decision_policy.py`)** :
Le `TernaryDecisionPolicy` supporte déjà `threshold_short` et `threshold_long` distincts. La commande les expose déjà :
```powershell
--ternary-threshold-short 0.30 --ternary-threshold-long 0.40
```

**Option C — Post-processing (nouveau code)** :
Ajouter dans `tabular_baseline.py` ou `trainer.py` une étape de « debiasing » qui, pour chaque date, trie les probabilités long/short et les ajuste pour que `mean(P_long) ≈ mean(P_short)` sur l'univers. Ceci nécessite une vision cross-sectionnelle, donc à implémenter dans `cross_sectional.py`.

---

## 3. Stratégie de filtrage de l'univers

### 3.1 Distribution actuelle des F1 WF

| Bucket F1_macro WF | Nb symboles | % |
|---------------------|-------------|---|
| 0.10-0.19 | 3 | 1.5% |
| 0.20-0.29 | **95** | **47.5%** |
| 0.30-0.39 | **97** | **48.5%** |
| 0.40+ | 5 | 2.5% |

### 3.2 Baseline théorique

Pour 3 classes équilibrées, un classifieur aléatoire a :
- Precision = 1/3, Recall = 1/3
- F1 par classe = 0.33
- F1_macro = 0.33

Avec les classes réelles distribuées ~34/33/32 (WF), le baseline aléatoire est approximativement **F1_macro ≈ 0.30-0.32**.

> 🔑 **Interprétation** : Un F1_macro < 0.30 signifie que le modèle est **pire que le hasard**.  
> Un F1_macro entre 0.30 et 0.35 est **marginalement meilleur que le hasard**.  
> Un F1_macro > 0.35 indique un **vrai signal**.

##### 🏦 À partir de quel seuil les pros considèrent-ils un modèle « tradable » ?

La réponse honnête : **les professionnels ne raisonnent pas en F1**. Le F1 est une métrique ML académique. En finance quantitative, on utilise d'autres métriques, directement liées à la rentabilité :

| Métrique | Ce qu'elle mesure | Seuil « tradable » |
|----------|-------------------|---------------------|
| **IC (Information Coefficient)** | Corrélation de Spearman entre prédictions et rendements futurs | IC > 0.03 → exploitable ; IC > 0.05 → bon ; IC > 0.10 → exceptionnel |
| **Sharpe ratio** (out-of-sample) | Rendement excédentaire / volatilité | Sharpe > 0.5 → marginal après coûts ; > 1.0 → bon ; > 2.0 → excellent |
| **PnL net après coûts** | Profit réalisé après slippage, commissions, spread | Positif et statistiquement significatif (t-test > 2) |
| **F1_macro** | Moyenne harmonique precision/recall par classe | Pas utilisé comme critère de tradability en production |

**Pourquoi les pros n'utilisent pas le F1 comme critère de tradability ?**

1. **Le F1 ne capture pas l'amplitude des mouvements** : prédire correctement « long » sur un titre qui fait +1% ou +15% donne le même F1, mais pas le même PnL.
2. **Le F1 ignore les coûts de transaction** : un modèle avec F1=0.40 qui trigger 3 trades/jour peut être ruiné par les frais, alors qu'un F1=0.35 avec 1 trade/semaine peut être très rentable.
3. **Le F1 est indépendant du capacity management** : tu ne peux pas allouer la même taille de position sur une small cap que sur AAPL.
4. **Le F1 ne mesure pas la calibration** : un modèle peut avoir un bon F1 mais des probabilités mal calibrées → mauvaise gestion du risque.

**Comment les pros évaluent-ils la tradability ?**

```
Pipeline d'évaluation professionnel :

1. IC > 0.03 (ou F1_macro > 0.33) → signal potentiellement intéressant
2. Backtest out-of-sample avec coûts réalistes → Sharpe net > 0.5 ?
3. Analyse de robustesse (sous-périodes, secteurs, régimes) → stable ?
4. Paper trading / small live → confirme le backtest ?
5. Scale progressif → capacity management

Seule l'étape 1 utilise une métrique de type F1/IC.
Les étapes 2-5 déterminent la VRAIE tradability.
```

**Conversion approximative F1 → tradability (pour ton cas 3 classes) :**

| F1_macro WF | Équivalent IC approx. | Interprétation pro |
|-------------|----------------------|---------------------|
| < 0.30 | IC < 0 | Bruit — exclure |
| 0.30 - 0.33 | IC 0 - 0.02 | Trop faible — probablement non tradable après coûts |
| 0.33 - 0.37 | IC 0.02 - 0.04 | **Potentiellement tradable** — nécessite backtest avec coûts |
| 0.37 - 0.42 | IC 0.04 - 0.07 | **Probablement tradable** — bon signal, vérifier stabilité |
| > 0.42 | IC > 0.07 | **Très bon signal** — rare, creuser absolument |

> 💡 **Pour ton cas** : Tu as ~50% des symboles entre 0.30-0.39 et 5 symboles > 0.40. La priorité n'est pas de savoir « à quel F1 on trade » mais de **lancer un backtest avec coûts réalistes** sur les symboles > 0.33. C'est le backtest qui te dira si c'est tradable, pas le F1. Un F1 de 0.38 avec des frais élevés peut être non rentable ; un F1 de 0.34 avec des frais faibles et une bonne diversification (40+ titres) peut l'être.

##### 🎯 Seuils par classe — Qu'est-ce qu'un « bon » F1_long, F1_short, F1_flat ?

Avec des classes équilibrées (~33% chacune), le baseline aléatoire est le même pour chaque classe : **0.33**. Les mêmes seuils que le F1_macro s'appliquent donc :

| F1 par classe | Interprétation |
|---------------|----------------|
| < 0.20 | 🔴 **Classe invisible** — le modèle ne la voit quasiment pas (ex: ROKU F1_flat=0.016) |
| 0.20 - 0.30 | 🟠 **Très faible** — à peine mieux que de l'anti-signal |
| 0.30 - 0.35 | 🟡 **Marginal** — proche du hasard, pas fiable seul |
| 0.35 - 0.45 | 🟢 **Bon** — signal réel, exploitable si les 2 autres classes suivent |
| > 0.45 | 🟢 **Très bon** — signal fort sur cette direction |

**Mais il y a une nuance importante : toutes les classes ne se valent pas en trading.**

| Classe | Difficulté | Pourquoi | Priorité |
|--------|-----------|---------|----------|
| **F1_long** | 🟢 La plus facile | Bull market structurel, tendance haussière = plus de vrais positifs | ⭐⭐ Important mais attention au biais |
| **F1_short** | 🔴 La plus difficile | Bull market = peu d'opportunités short, signaux plus rares | ⭐⭐⭐ CRITIQUE — différencie un vrai modèle d'un modèle bull-only |
| **F1_flat** | 🟡 Variable | Dépend de la volatilité du titre (biotech vs utility) | ⭐ Utile pour réduire le turnover |

**Lecture de la table de ton batch avec ces seuils :**

```
Top 10 :
├── HLIT : long=0.49🟢 short=0.41🟢 flat=0.35🟡 → modèle équilibré, bon partout ✅
├── TEX  : long=0.51🟢 short=0.52🟢 flat=0.20🟠 → excellent directionnel, ignore le flat
├── NTRS : long=0.51🟢 short=0.23🟠 flat=0.47🟢 → bon long/flat, ne pas shorter
├── R    : long=0.52🟢 short=0.42🟢 flat=0.27🟠 → le plus équilibré du top 5 ✅

Pires :
├── IIPR : long=0.45🟢 short=0.07🔴 flat=0.06🔴 → long-only, short/flat inexistants
├── HSBC : long=0.08🔴 short=0.09🔴 flat=0.43🟢 → ne prédit que flat, inutile
├── ROKU : long=0.31🟡 short=0.31🟡 flat=0.02🔴 → binaire, pas de flat
```

**Règle pratique pour filtrer :**

```
✅ TRADABLE (toutes directions) : F1_long > 0.35 ET F1_short > 0.30
✅ TRADABLE (long only)        : F1_long > 0.40 ET F1_short < 0.20 → shorter interdit
✅ TRADABLE (short only)       : F1_short > 0.40 ET F1_long < 0.20 → longer interdit
⚠️ SURVEILLER                  : F1_long > 0.35 mais F1_short entre 0.20-0.30
❌ EXCLURE                     : F1_long < 0.30 ET F1_short < 0.30 → aucune direction fiable
❌ EXCLURE                     : F1_flat < 0.10 → titre trop volatil/binaire
```

### 3.3 Stratégie de filtrage recommandée

#### Niveau 1 — Exclusion dure (filtre de sécurité)

```python
# Dans modelFactory/champion_selection.py, ajouter :
MIN_WF_F1_MACRO = 0.25  # seuil de survie minimum
```

Symboles exclus si :
- `wf_f1_macro < 0.25` → modèle non fiable, trading interdit
- `wf_f1_short == 0` → incapacité à shorter, short interdit sur ce symbole
- `wf_f1_long == 0` → incapacité à longer, long interdit

**Impact estimé** : ~40-50 symboles exclus (ceux en dessous de 0.25 + les 4 avec f1_short=0)

#### Niveau 2 — Score composite (filtre de qualité)

```python
QUALITY_SCORE = (
    0.40 * wf_f1_macro
    + 0.20 * wf_f1_long
    + 0.20 * wf_f1_short
    + 0.10 * min(wf_f1_long, wf_f1_short)  # pénalise l'asymétrie
    + 0.10 * (1.0 - abs(pred_long_pct - true_long_pct) / 100)  # pénalise le biais
)
```

Classer les symboles par `QUALITY_SCORE` décroissant. N'utiliser que les top N (ex: top 50, top 100).

#### Niveau 3 — Filtre temporel (stabilité)

Vérifier que le F1 est stable dans le temps :
- Calculer le F1 par split walk-forward (déjà disponible dans `wf.splits[i].f1_macro`)
- Exclure si `std(f1_macro across splits) > 0.10` → signal instable
- Exclure si `f1_macro_split_0 > f1_macro_split_1 > f1_macro_split_2` → signal en dégradation

#### Niveau 4 — Filtre sectoriel

- Si un secteur a un F1_macro moyen < 0.28 → exclure tout le secteur
- Basé sur le mapping secteur de `_load_sector_mapping()` dans `cross_sectional.py`

### 3.4 Code à implémenter

```python
# Nouveau fichier : modelFactory/universe_filter.py

@dataclass
class UniverseFilter:
    min_wf_f1_macro: float = 0.25
    min_wf_f1_long: float = 0.10
    min_wf_f1_short: float = 0.10
    max_f1_std_across_splits: float = 0.10
    min_sector_avg_f1: float = 0.28
    allow_short_zero: bool = False
    allow_long_zero: bool = False

def filter_symbols(
    metrics_by_symbol: dict[str, dict],
    cfg: UniverseFilter,
    sector_map: dict[str, str] | None = None,
) -> tuple[list[str], list[str], dict[str, str]]:
    """
    Returns:
        accepted: symboles acceptés
        rejected: symboles rejetés
        reasons: {symbol: reason} pour les rejetés
    """
    ...
```

### 3.5 Intégration dans le pipeline

Le filtre doit être appliqué **après** l'entraînement du batch, avant la mise en production des modèles :

```
train batch → rapport → UniverseFilter → modèles filtrés → production
```

Le rapport actuel (`artifacts/rapport_ml/`) peut être parsé pour extraire les métriques par symbole et appliquer le filtre sans ré-entraîner.

---

## 4. Analyse approfondie du top 20%

### 4.1 Les 10 meilleurs symboles

| Symbole | F1_macro | F1_long | F1_short | F1_flat | Profil |
|---------|----------|---------|----------|---------|--------|
| **HLIT** | **0.416** | 0.492 | 0.411 | 0.345 | ⭐ Équilibré — bon sur les 3 classes |
| **TEX** | **0.409** | 0.506 | 0.517 | 0.204 | 📈 Long/Short fort — flat faible |
| **NTRS** | **0.404** | 0.508 | 0.232 | 0.471 | 📊 Flat fort — long OK, short faible |
| **SANM** | **0.403** | 0.533 | 0.223 | 0.452 | 📊 Flat fort — long très bon — short faible |
| **R** | **0.401** | 0.518 | 0.418 | 0.268 | ⭐ Très équilibré — toutes classes > 0.25 |
| **MOG.A** | 0.391 | 0.519 | 0.296 | 0.358 | Bon — léger biais long |
| **AIN** | 0.391 | 0.469 | 0.332 | 0.371 | ⭐ Très équilibré |
| **DRH** | 0.389 | 0.523 | 0.440 | 0.204 | 📈 Long/Short fort |
| **FLEX** | 0.388 | 0.522 | 0.371 | 0.269 | Bon équilibre |
| **BFH** | 0.383 | 0.435 | 0.480 | 0.235 | Short meilleur que long |

### 4.2 Patterns communs aux meilleurs

1. **Au moins 2 classes > 0.30** : Tous les top 10 ont ≥ 2 classes avec F1 > 0.30. Aucun n'a une classe complètement effondrée (< 0.15).

2. **F1_long systématiquement bon** (> 0.43 pour 9/10) : Le signal long est le plus fiable. C'est cohérent avec le biais haussier général, mais ici c'est un vrai signal, pas un artefact.

3. **Aucun n'est une mega-cap tech** : Pas de AAPL, MSFT, GOOGL dans le top 10. Les meilleurs sont des mid-caps industrielles/financières.

4. **F1_flat variable** (0.20-0.47) : La capacité à prédire le flat n'est pas corrélée à la performance globale. TEX (0.204) est #2 malgré un flat faible.

### 4.3 Analyse croisée : top performers vs champions

Il faudrait croiser avec la table `model_governance` pour savoir :
- Quel modèle a été choisi comme champion pour chaque top performer ?
- Le champion est-il le meilleur challenger ou le fallback ?

➡️ Requête SQL suggérée :
```sql
SELECT symbol, selected_model, selection_mode, selection_score
FROM model_governance
WHERE symbol IN ('HLIT','TEX','NTRS','SANM','R','MOG.A','AIN','DRH','FLEX','BFH')
  AND run_id LIKE '%20260722%';
```

### 4.4 Les 5 symboles > 0.40 — faut-il les trader ?

| Critère | HLIT (0.416) | TEX (0.409) | NTRS (0.404) | SANM (0.403) | R (0.401) |
|---------|-------------|-------------|--------------|--------------|-----------|
| F1 > random? | ✅ +26% | ✅ +24% | ✅ +22% | ✅ +22% | ✅ +21% |
| Toutes classes > 0.20? | ✅ | ❌ flat=0.20 | ✅ | ✅ | ✅ |
| Signal exploitable? | 🟢 OUI | 🟡 OUI (pas flat) | 🟡 OUI (pas short) | 🟡 OUI (pas short) | 🟢 OUI |

**Verdict** : HLIT et R sont les deux seuls symboles avec un signal équilibré et fiable sur les 3 directions. TEX est excellent en directionnel (long/short) mais ne pas trader le flat. NTRS et SANM sont très bons en long/flat, éviter le short.

### 4.5 Top 20% élargi (40 symboles, F1 > ~0.33)

Pour les 40 meilleurs symboles (F1_macro > 0.33) :
- Espérance de F1_macro ≈ 0.35-0.36
- Ce sont majoritairement des mid-caps industrielles, financières, et technologiques
- Un portefeuille concentré sur ces 40 symboles avec equal-weight aurait un F1_macro moyen de ~0.35, soit **+17% au-dessus du baseline aléatoire**

Recommandation : lancer un backtest sur ce sous-univers de 40 symboles pour valider la rentabilité nette.

---

## 5. Investigation du feature set `expert`

### 5.1 Composition du feature set

```python
# modelFactory/features.py

FEATURE_COLUMNS (v1) — 13 colonnes :
├── daily_return, log_return          # rendements
├── intraday_range, overnight_gap     # range
├── close_to_vwap                     # déviation vs VWAP
├── volume_ratio_20                   # volume relatif
├── rolling_volatility_20, _60        # volatilité
├── rolling_mean_return_5, _20        # momentum court
├── rsi_14, atr_14_norm               # indicateurs classiques
└── is_filled                         # flag données manquantes

EXPERT_FEATURE_COLUMNS — 18 colonnes supplémentaires :
├── sma20/50/100/200_distance         # distance aux moyennes mobiles (4)
├── ema20/50_distance                 # distance aux EMA (2)
├── momentum_10/20/60                 # momentum multi-horizon (3)
├── vol_ratio_20_60                   # ratio de volatilité
├── range_position_20                 # position dans le range 20j
├── market_return_20                  # rendement benchmark
├── market_volatility_20              # volatilité benchmark
├── market_trend_strength_50          # force de tendance benchmark
├── relative_strength_20/60           # force relative vs benchmark (2)
├── regime_bull_market                # régime haussier
└── regime_risk_off                   # régime risk-off
```

Avec `--enable-cross-sectional`, 16 colonnes supplémentaires sont ajoutées :
```
CROSS_SECTIONAL — 8 rangs percentiles :
├── ret_20_rank, ret_60_rank
├── relative_strength_20_rank, relative_strength_60_rank
├── volatility_20_rank, dollar_volume_20_rank
├── volume_ratio_20_rank_xs, range_position_20_rank

SECTOR — 8 features :
├── sector_ret_20, sector_ret_60
├── sector_vol_20, sector_relative_strength_20
├── sector_dollar_volume_20, sector_symbol_count
├── stock_vs_sector_ret_20, stock_vs_sector_ret_60
```

**Total : 13 + 18 + 8 + 8 = 47 features**

### 5.2 Redondances et corrélations probables

Plusieurs groupes de features sont fortement corrélés :

| Groupe | Features | Corrélation attendue |
|--------|----------|---------------------|
| Momentum | `momentum_10`, `momentum_20`, `momentum_60`, `daily_return`, `rolling_mean_return_5`, `rolling_mean_return_20` | > 0.7 entre paires |
| Distance aux MA | `sma20/50/100/200_distance`, `ema20/50_distance` | > 0.8 intra-groupe |
| Force relative | `relative_strength_20`, `relative_strength_60`, `market_return_20` | > 0.6 |
| Rangs cross-sectionnels | `ret_20_rank`, `ret_60_rank`, `relative_strength_20_rank`, `relative_strength_60_rank` | > 0.7 par paires |
| Secteur | `sector_ret_20`, `sector_ret_60`, `sector_relative_strength_20` | > 0.8 |

**Estimé : sur 47 features, ~25-30 sont fortement redondantes (corrélation > 0.6).**

### 5.3 Features probablement les plus informatives (hypothèses)

Basé sur la littérature et l'intuition financière :

1. **`relative_strength_20/60`** — Force relative vs benchmark : un des signaux les plus robustes en equity long/short
2. **`regime_risk_off`** — Contexte de marché : conditionne tout le comportement
3. **`ret_20_rank`** / **`ret_60_rank`** — Rang cross-sectionnel : capte le momentum relatif
4. **`stock_vs_sector_ret_20`** — Alpha intra-secteur : signal purifié du biais sectoriel
5. **`vol_ratio_20_60`** — Expansion/contraction de volatilité : précède souvent les mouvements
6. **`range_position_20`** — Position dans le range : mean-reversion à court terme

### 5.4 Features probablement peu informatives

1. **`is_filled`** — Flag binaire, peu de variance
2. **`close_to_vwap`** — Très bruité, peu prédictif à J+10
3. **`overnight_gap`** — Signal déjà incorporé dans `daily_return`
4. **`sma100_distance`, `sma200_distance`** — Redondants avec `sma20/50_distance` pour du swing trading 10j
5. **`sector_symbol_count`** — Constant par secteur, pas de signal temporel

### 5.5 Recommandations

#### A. Analyse de feature importance (SHAP)

```python
# Après entraînement LightGBM/CatBoost, extraire les SHAP values :
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_val)
shap.summary_plot(shap_values, X_val, feature_names=feature_columns)
```

Identifier les features avec SHAP importance < 0.5% → candidates à la suppression.

#### B. Réduire à un « core set » de 15-20 features

Proposition de core set :
```
1. relative_strength_20          # momentum relatif
2. relative_strength_60          # momentum relatif long
3. regime_risk_off               # contexte macro
4. regime_bull_market            # contexte macro
5. ret_20_rank                   # rang cross-sectionnel
6. ret_60_rank                   # rang cross-sectionnel long
7. stock_vs_sector_ret_20        # alpha sectoriel
8. vol_ratio_20_60               # régime de vol
9. range_position_20             # mean-reversion
10. rsi_14                        # indicateur classique
11. atr_14_norm                   # volatilité normalisée
12. volume_ratio_20               # volume anormal
13. rolling_volatility_20         # vol court terme
14. momentum_20                   # momentum 20j
15. market_trend_strength_50      # tendance benchmark
16. sector_ret_20                 # momentum sectoriel
17. dollar_volume_20_rank         # liquidité relative
18. volatility_20_rank            # rang de volatilité
```

#### C. Feature engineering supplémentaire

- **`short_squeeze_score`** — Ratio short interest / avg volume → prédicteur de short squeeze
- **`earnings_surprise_momentum`** — Si disponible, momentum post-earnings
- **`options_put_call_ratio`** — Si disponible, sentiment options
- **`gap_to_52w_high`** — Proximité du plus haut 52 semaines (existe déjà dans `selector_high_52w_proximity`)

#### D. Test A/B

Lancer le même batch avec `--feature-set v1` uniquement (13 features) et comparer les F1 WF. Si la différence est < 0.02, les 34 features supplémentaires n'apportent rien.

---

## 6. Analyse sectorielle des underperformers

### 6.1 Les 10 pires symboles

| Symbole | F1_macro | F1_long | F1_short | F1_flat | Classe manquante |
|---------|----------|---------|----------|---------|-----------------|
| IIPR | 0.194 | 0.450 | 0.069 | **0.063** | Flat + Short |
| CMPR | 0.194 | 0.350 | 0.122 | 0.111 | Flat + Short |
| INDV | 0.195 | 0.353 | 0.212 | **0.022** | Flat |
| HSBC | 0.201 | **0.077** | 0.093 | 0.434 | Long + Short |
| ANET | 0.203 | 0.250 | 0.223 | 0.135 | Flat |
| PRG | 0.207 | 0.354 | 0.140 | 0.125 | Flat + Short |
| ESE | 0.209 | 0.310 | **0.085** | 0.230 | Short |
| BELFB | 0.209 | 0.236 | 0.351 | **0.040** | Flat |
| ROKU | 0.212 | 0.305 | 0.314 | **0.016** | Flat |
| CDNA | 0.215 | 0.436 | 0.171 | **0.038** | Flat |

### 6.2 Pattern commun : incapacité à prédire le FLAT

**8/10** des pires symboles ont un F1_flat < 0.15. C'est le pattern le plus clair : ces titres ont des rendements extrêmement binaires (soit ça monte fort, soit ça descend fort) et ne restent jamais dans la zone ±3%. Le modèle ne peut pas apprendre une classe qui n'existe quasiment pas dans les données.

> 📐 **Exemple ROKU** : F1_flat = 0.016. La classe flat est quasi-absente des données réelles pour ce titre très volatil. Le modèle prédit flat dans ~2% des cas, et a raison... 1.6% du temps.

### 6.3 Tentative d'identification sectorielle

Sans accès à la base de données `stock_metadata`, on peut inférer les secteurs approximatifs :

| Symbole | Secteur probable | Caractéristique |
|---------|-----------------|-----------------|
| IIPR | REIT Cannabis | Très volatile, dépendance réglementaire |
| CMPR | Impression/Emballage | Secteur cyclique |
| INDV | Tech industrielle? | Small cap volatil |
| HSBC | Banque internationale | Multi-géographies, peu sensible aux features US |
| ANET | Équipement réseau | Tech croissance |
| PRG | Consumer finance | Cyclique |
| ESE | Défense/Aérospatial | Sectoriel spécifique |
| BELFB | Électronique | Small cap |
| ROKU | Streaming tech | Hyper-volatil, sentiment-driven |
| CDNA | Biotech/Healthcare | Binaire (FDA approvals) |

### 6.4 Hypothèses sectorielles

Les underperformers semblent appartenir à 3 catégories :

1. **Biotech/Santé** (CDNA, IIPR) : Rendements binaires, dépendants d'événements discrets (approbations FDA, résultats d'essais cliniques) que les features OHLCV ne peuvent pas capturer.

2. **Tech hyper-volatile** (ROKU, ANET, BELFB) : Mouvements largement déterminés par le sentiment de marché et les news, pas par les patterns techniques.

3. **Value/cycliques internationales** (HSBC, CMPR) : Exposés à des facteurs macro non-US que les features (basées sur SPY) ne capturent pas.

### 6.5 Le cas HSBC — Diagnostic spécifique

HSBC a un F1_long de **0.077** et F1_short de **0.093**, mais F1_flat de **0.434**. C'est l'image miroir du problème LSTM : le modèle prédit flat presque tout le temps pour HSBC. Le feature set `expert` basé sur le marché US (SPY comme benchmark) n'est probablement pas adapté à une banque cotée à Londres et Hong Kong.

### 6.6 Solution : Features spécifiques au secteur

```python
# Ajouter dans cross_sectional.py ou features.py
SECTOR_SPECIFIC_FEATURES = {
    "biotech": ["sector_fda_calendar_days", "sector_patent_expiry_days"],
    "tech": ["sector_nasdaq_correlation", "sector_sentiment_score"],
    "financial": ["sector_yield_curve_slope", "sector_credit_spread"],
    "energy": ["sector_crude_correlation", "sector_rig_count_change"],
    "reit": ["sector_interest_rate_sensitivity", "sector_cap_rate_spread"],
}
```

### 6.7 Solution : Exclure les titres à distribution de rendement pathologique

```python
def is_pathological_distribution(returns: np.ndarray) -> bool:
    """Détecte les titres dont le rendement est quasi-binaire."""
    flat_mask = (returns > -0.03) & (returns < 0.03)
    flat_pct = flat_mask.mean()
    if flat_pct < 0.20:  # moins de 20% de flat → pathologique
        return True
    # Kurtosis > 10 → distribution trop extrême
    if pd.Series(returns).kurtosis() > 10:
        return True
    return False
```

---

## 7. Synthèse & Plan d'action

### 7.0 Règle de filtrage — Quels symboles trader ?

Rappel des seuils de qualité par classe (baseline aléatoire = 0.33 pour 3 classes équilibrées) :

| F1 par classe | Interprétation |
|---------------|----------------|
| < 0.20 | 🔴 **Classe invisible** |
| 0.20 - 0.30 | 🟠 **Très faible** |
| 0.30 - 0.35 | 🟡 **Marginal** (proche du hasard) |
| 0.35 - 0.45 | 🟢 **Bon** |
| > 0.45 | 🟢 **Très bon** |

**Règle de filtrage :**

```
✅ TRADABLE (toutes directions) : F1_long > 0.35 ET F1_short > 0.30
✅ TRADABLE (long only)        : F1_long > 0.40 ET F1_short < 0.20 → shorter interdit
✅ TRADABLE (short only)       : F1_short > 0.40 ET F1_long < 0.20 → longer interdit
⚠️ SURVEILLER                  : F1_long > 0.35 mais F1_short entre 0.20-0.30
❌ EXCLURE                     : F1_long < 0.30 ET F1_short < 0.30 → aucune direction fiable
❌ EXCLURE                     : F1_flat < 0.10 → titre trop volatil/binaire
```

**Application au batch `cddc05` :**

| Catégorie | Nb symboles | Exemples |
|-----------|-------------|---------|
| ✅ Toutes directions | ~15-20 | HLIT, R, AIN, FLEX |
| ✅ Long only | ~30-40 | NTRS, SANM, MOG.A |
| ⚠️ Surveiller | ~30-40 | F1_short entre 0.20-0.30 |
| ❌ Exclure | ~50-60 | HSBC, ROKU, IIPR + F1_macro < 0.25 |

### 7.1 Résumé des problèmes

| # | Problème | Sévérité | Cause racine |
|---|----------|----------|-------------|
| 1 | LSTM inutilisable | 🔴 Critique | Seq_len trop court, trop de features, pas de class weights, early stop agressif |
| 2 | Biais LONG +50% | 🔴 Critique | Bull market structurel, class weights égaux, calibration symétrique |
| 3 | 50% des symboles sous le baseline | 🟡 Important | Features non informatives pour ces titres, distributions pathologiques |
| 4 | LightGBM domine (58%) | 🟢 Normal | Modèle simple + peu de données = arbres gagnent |
| 5 | 4 symboles F1_short=0 | 🟠 Opérationnel | Incapacité totale à shorter certains titres |
| 6 | F1_flat effondré pour 8/10 pires | 🟡 Important | Titres à distribution binaire |
| 7 | Global Model = 0 champion sur 200 | 🟢 Normal (compris) | Même info que per-symbol, pas de diversité d'architecture |

### 7.2 Plan d'action priorisé

> 📊 **Test A/B du 24 juillet 2026** : Batch `22b4ca` (Global Model sans challenger) vs `9493ca` (avec challenger) → **résultats identiques**. Le Global Model n'a gagné **0 symbole sur 200**. LightGBM (112), CatBoost (68) et LSTM (20) dominent inchangés. Le Global Model est abandonné.
>
> ✅ **Implémentations du 24 juillet 2026** :
> - **Interactions features × régime** : 18 features dans `features.py` (actives pour GBM/CatBoost avec `--feature-set expert`)
> - **LSTM hardcodé v1** : `trainer.py` force 29 features pour LSTM, ignorant le flag `--feature-set`
> - 💡 **Note IHM** : Le flag `--feature-set` contrôle uniquement GBM/CatBoost. Le LSTM est automatiquement en v1.

#### 🔴 Immédiat (cette semaine)

1. **Lancer un batch test LSTM corrigé** avec :
   ```powershell
   --sequence-length 40 --hidden-size 64 --max-epochs 50 --patience 10 \
   --ternary-weight-short 1.5 --ternary-weight-long 1.5 --ternary-weight-flat 0.7 \
   --feature-set v1 --symbol-source ticket-recherche --max-workers 2 \
   --comment test_lstm_fix_v2
   ```

2. **Lancer un batch avec correction du biais long** :
   ```powershell
   --ternary-weight-short 1.8 --ternary-weight-long 1.0 --ternary-weight-flat 1.2 \
   --ternary-threshold-short 0.30 --ternary-threshold-long 0.40 \
   --comment bias_correction_v1
   ```

3. **Parser le rapport pour extraire les métriques par symbole** et construire le `UniverseFilter`.

#### 🟡 Cette semaine ou la suivante

4. **Analyse SHAP** sur LightGBM/CatBoost pour identifier les features inutiles.
5. **Lancer un batch `feature-set v1` seul** (sans cross-sectional) pour mesurer l'apport incrémental.
6. **Backtest sur le top 40 symboles** (F1 > 0.33) pour valider la rentabilité.
7. **Requête SQL pour croiser secteurs et performances**.

#### 🟢 Moyen terme

8. **Implémenter le post-processing de débiaisage** (calibration par quantile cross-sectionnelle).
9. **Ajouter les features secteur-spécifiques** (biotech, financial, energy).
10. **Mettre en place le filtre automatique d'univers** dans le pipeline de production.
11. **Si le LSTM reste mauvais après correctifs**, le désactiver et concentrer les efforts sur l'amélioration de LightGBM/CatBoost (hyperparameter tuning, feature engineering).

### 7.3 Scripts à créer

| Script | Description |
|--------|-------------|
| `scripts/parse_ml_report.py` | Parse le rapport markdown → DataFrame |
| `scripts/universe_filter.py` | Applique les filtres de qualité → liste de symboles tradables |
| `scripts/shap_analysis.py` | Extrait et visualise les SHAP values par symbole |
| `scripts/sector_performance.py` | Joint les métriques ML avec les secteurs GICS |

### 7.4 Tables DB à consulter

```sql
-- Champions par symbole
SELECT symbol, selected_model, selection_mode, selection_score
FROM model_governance
WHERE batch_id = 'model-factory-20260722091334-cddc05';

-- Métriques WF détaillées par symbole et modèle
SELECT symbol, model_name, split_name,
       f1_macro, f1_short, f1_flat, f1_long,
       true_short_pct, true_flat_pct, true_long_pct,
       pred_short_pct, pred_flat_pct, pred_long_pct
FROM training_metrics
WHERE run_id IN (SELECT run_id FROM training_runs WHERE batch_id = '...');

-- Secteurs des symboles
SELECT symbol, provider_sector
FROM stock_metadata
WHERE symbol IN (SELECT DISTINCT symbol FROM model_governance WHERE batch_id = '...');
```

---

*Rapport généré le 2026-07-22 par analyse du code source `modelFactory/` et du rapport `artifacts/rapport_ml/model-factory-20260722091334-cddc05.md`.*
