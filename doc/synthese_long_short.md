# Synthèse : Calcul des scores Long/Short, Sentiment, ML et Risk

> **Document généré le 2026-06-24** — à mettre à jour au fur et à mesure de la discussion.
> Projet Alpha Trade — `f:\projets`

---

## 1. CALCUL DES SCORES LONG ET SHORT

### 1.1 Architecture en 3 couches

Le calcul des scores est un pipeline à **3 étages** :

```
Screener → Selector (factors + ranking) → Signal Aggregator (sentiment boost)
```

### 1.2 Screener (`screener/pipeline.py`) — Score de base `total_score`

Le screener est le **premier filtre large**. Il produit pour chaque symbole un `total_score` ∈ [0,1] composé de :

$$\text{total\_score} = 0.15 \times \text{liquidity\_val} + 0.55 \times \text{RSI\_norm} + 0.30 \times \text{historical\_range\_score}$$

- **`liquidity_val`** : dollar volume moyen sur 20 jours, normalisé via winsorisation [1%, 99%] + min-max [0,1]
- **`RSI_norm`** : force relative vs SPY (relative strength index), normalisé
- **`historical_range_score`** : position du prix dans le range 2 ans (0 = au plus bas, 1 = au plus haut)

### 1.3 Selector (`selector/`) — Score technique `final_score`

Le **Selector** (`alpha_scanner.py`) calcule les facteurs techniques puis les fusionne.

#### a) Facteurs techniques (`selector/factors.py`)

La fonction `compute_factor_frame()` calcule ces facteurs **purs** (sans I/O) :

| Facteur | Description |
|---------|-------------|
| `trend_score` | Score Minervini (0-1) : position du prix vs MA50/150/200 + pente du MA200 |
| `vcp_score` | Volatility Contraction Pattern (0-1) : contraction de volatilité |
| `ma50/150/200` | Moyennes mobiles simples |
| `atr_20`, `atr_pct_20` | Average True Range (20j) |
| `beta_126` | Bêta vs SPY sur 126 jours |
| `high_52w_proximity` | Proximité du plus haut 52 semaines |
| `volatility_ratio` | Ratio vol 10j / vol 60j |
| `weekly_trend_score` | Tendance hebdomadaire (close vs MA10/MA30 weekly) |

#### b) Fusion des scores (`selector/ranking.py`) — `merge_scores()`

C'est le cœur du calcul. La formule produit un `final_score` ∈ [0,1] :

$$\text{final\_score} = w_{trend\_vcp} \times \frac{trend\_score + vcp\_score}{2} + w_{total\_score} \times total\_score_{norm} + w_{rsi} \times RSI_{norm}$$

Les poids **par défaut** (en régime `normal`) :
- `weight_trend_vcp` = **0.50** (momentum technique)
- `weight_total_score` = **0.30** (score screener)
- `weight_rsi` = **0.20** (force relative)

Chaque composante est **winsorisée** [1%, 99%] puis **normalisée** [0,1] via `winsorize_and_normalize()`.

#### c) Neutralisation sectorielle (`apply_factor_neutralization()`)

Applique un **z-score intra-secteur** sur `total_score` et `relative_strength_index` :

$$\text{z\_score}_{secteur} = \frac{x - \mu_{secteur}}{\sigma_{secteur}}$$

Puis re-normalise en [0,1]. Cela évite qu'un secteur entier soit sur/sous-représenté à cause d'un biais sectoriel.

#### d) Sélection finale (`rank_and_select()`)

1. Trie par `final_score` décroissant
2. Applique `apply_sector_neutrality()` : **round-robin** avec un plafond par secteur (`sector_cap_ratio`)
3. Sélectionne le **top N** (typiquement 20-30 positions)

---

### 1.4 Score Short dédié (`selector/short_score.py`)

Les shorts ne sont PAS les bottom-N du `final_score`. Ils utilisent un **score baissier composite** indépendant (0-1, plus c'est haut = plus baissier) :

$$\text{short\_score} = 0.30 \times (1 - trend\_score) + 0.25 \times (1 - \frac{RSI}{100}) + 0.25 \times \mathbb{1}[prix < SMA50] + 0.20 \times \mathbb{1}[prix < SMA200]$$

Les 4 facteurs :
1. **Trend faible** (30%) : `1 - trend_score` — un trend_score bas (ex: 0.1) donne 0.9 de contribution bearish
2. **RSI bas** (25%) : RSI < 40 → bearish (transformé linéairement)
3. **Prix sous SMA50** (25%) : booléen, +0.25 si sous la MM 50 jours
4. **Prix sous SMA200** (20%) : booléen, +0.20 si sous la MM 200 jours

La sélection short est faite par `rank_and_select_short()` qui trie par `short_score` décroissant, en excluant les symboles déjà sélectionnés en long.

#### Fichiers clés :
- `selector/short_score.py` — `compute_short_score()`, `enrich_with_short_score()`
- `selector/ranking.py` — `rank_and_select_short()`

---

## 2. UTILISATION DU SENTIMENT POUR LONG ET SHORT

### 2.1 Pipeline Sentiment (`event_sentiment/`)

```
News API → ingestion.py → scoring.py (FinBERT) → aggregation.py → signal_aggregator.py → stock_scores
```

#### Niveau 1 — Scoring article par article (`scoring.py`)
- **FinBERT** (ProsusAI/finbert) classifie chaque article : `positive`, `neutral`, `negative`
- Produit un `sentiment_net` ∈ [-1, 1] et une `confidence` ∈ [0, 1]

#### Niveau 2 — Agrégation journalière (`aggregation.py`)
- `build_ticker_daily_features()` : par (symbole, date) → `sentiment_net_mean_1d`, `news_count_1d`, `major_event_flag`, etc.
- `build_sector_daily_features()` : par (secteur, date) → `sector_impact_score`, `macro_event_intensity`

#### Niveau 3 — Règles macro (`macro_rules.py`)
- Détection d'événements macro : FOMC, CPI, emploi, géopolitique, fiscal
- Propagation d'impact par secteur (ex: hausse des taux → négatif pour Tech, positif pour Financials)

### 2.2 Fusion Sentiment → Score (`signal_aggregator.py`)

Le `SentimentSignalAggregator.merge()` fusionne le score quantitatif avec le sentiment.

#### Étape 1 — Calcul du signal sentiment agrégé

Pour chaque symbole, on agrège les N derniers jours de sentiment avec **décroissance temporelle exponentielle** :

$$w_{jour} = 0.5^{\frac{age\_jours}{demi\_vie}}$$

Avec `demi_vie = 2` jours par défaut. Chaque jour est aussi pondéré par son `news_count`.

Condition d'activation : il faut au moins `min_news_count` articles (défaut = 2) pour que le signal soit actif.

#### Étape 2 — Normalisation

Le signal agrégé `sentiment_net_agg` ∈ [-1, 1] est transformé en [0, 1] :

$$\text{sentiment\_signal\_norm} = \frac{\text{clamp}(sentiment\_net\_agg, -1, 1) + 1}{2}$$

0.5 = neutre, 0 = très négatif, 1 = très positif.

#### Étape 3 — Fusion ternaire (`fuse_sentiment()` dans `core/conviction.py`)

$$\text{final\_score\_sentiment} = w_{quant} \times final\_score + w_{sentiment} \times sentiment\_norm + w_{macro} \times macro\_norm$$

Le tout clippé dans [0, 1].

Si le signal sentiment n'est **pas actif** (pas assez de news), on utilise **0.5** (neutre) au lieu de `sentiment_norm`.

### 2.3 Poids et impact réel

**IMPORTANT** — Les poids par défaut sont :
- `quant_weight` = **1.00** (100% quantitatif)
- `sentiment_weight` = **0.00** (désactivé par défaut !)
- `macro_weight` = **0.00** (désactivé par défaut !)

**Pourquoi ?** Le diagnostic empirique (IC = Information Coefficient) sur 2020-2025 a montré :
- **Sentiment** : IC ≈ 0.01, t-stat ≈ 1.1 → **non significatif statistiquement**
- **Macro** : IC ≈ 0, t-stat ≈ 0 → **aucun pouvoir prédictif**
- **Quant** : IC ≈ 0.03, t-stat ≈ 2.5 → **seul signal significatif**

Donc **en production, le sentiment n'a pas d'impact par défaut**. Les poids sont laissés configurables pour exploration/calibration.

#### Fichiers clés :
- `event_sentiment/signal_aggregator.py` — `SentimentSignalAggregator`, `SentimentBoostConfig`
- `core/conviction.py` — `fuse_sentiment()`, `SentimentFusionWeights`

---

## 3. WALK-FORWARD SENTIMENT — Calibration des poids

### 3.1 Qu'est-ce que c'est ?

Le **Walk-Forward Sentiment** (`backtesting/sentiment_calibration.py` + `backtesting/walk_forward.py`) est un processus de **calibration hors-échantillon** qui détermine les meilleurs poids `(w_sentiment, w_macro, w_quant)` à utiliser pour la fusion.

### 3.2 Fonctionnement

1. **Chargement du dataset** : `stock_scores_history` + forward returns (rendements futurs à J+5, J+10, J+20)
2. **Grille de scénarios** (11 scénarios par défaut) :
   - `sentiment_weight` ∈ {0.00, 0.02, 0.05, 0.08, 0.10}
   - `macro_weight` ∈ {0.00, 0.02}
   - `quant_weight = 1.0 - sentiment - macro`
3. **Walk-forward par folds glissants** :
   - Pour chaque fold (ex: train 2020-2022 → test 2023) :
     - Sur la période **train** : teste tous les scénarios, garde le meilleur
     - Sur la période **test** (OOS) : évalue le scénario gagnant
   - On obtient un score OOS moyen pour chaque scénario
4. **Sélection** : le scénario avec le meilleur score OOS global (Sharpe, rendement total, max drawdown)

### 3.3 Fichiers produits

- `latest_best_weights.json` (ou `walk_forward_best_weights_latest.json`)
- Contient : `sentiment_weight`, `macro_weight`, `quant_weight`, `calibration_run_id`, `best_scenario_name`

### 3.4 Application des poids calibrés (`backtesting/walk_forward.py`)

La fonction `resolve_latest_walk_forward_weights()` cherche ces fichiers dans :
- `artifacts/sentiment_walk_forward/`
- `artifacts/sentiment_calibration/`
- `artifacts/`

Les poids sont **clippés** dans [0.05, 0.40] (bornes business de sécurité) via `validate_walk_forward_weights()`.

### 3.5 Impact sur long et short

Quand les poids walk-forward sont appliqués (via `SentimentBoostConfig`), le `final_score_sentiment` remplace ou complète le `final_score` quantitatif pur. Les colonnes impactées dans `stock_scores` :

| Colonne | Signification |
|---------|---------------|
| `final_score_sentiment` | Score final avec boost sentiment (utilisé si calibré) |
| `final_score_walk_forward` | Score final avec poids walk-forward appliqués |
| `walk_forward_sentiment_weight` | Poids sentiment calibré |
| `walk_forward_macro_weight` | Poids macro calibré |
| `walk_forward_quant_weight` | Poids quant calibré |

⚠️ **En pratique actuelle** : vu que les poids calibrés optimaux tendent vers `sentiment=0, macro=0, quant=1`, le walk-forward confirme que le signal quantitatif seul est le plus robuste.

#### Fichiers clés :
- `backtesting/sentiment_calibration.py` — `SentimentWeightCalibrator`
- `backtesting/walk_forward.py` — `resolve_latest_walk_forward_weights()`, `WalkForwardWeights`

---

## 4. ML — ENTRAÎNEMENT LONG ET SHORT

### 4.1 Architecture du modèle (`modelFactory/model.py`)

Le modèle est un **LSTM + Attention Temporelle** :

```
Input [batch, seq_len, n_features]
  → LSTM multi-couche (2 couches, hidden=128, dropout=0.3)
  → Temporal Soft-Attention (pondère les pas de temps)
  → Dropout
  → Linear(hidden, num_classes)
  → Softmax → probabilités
```

#### Modes de classification

| Mode | Classes | Description |
|------|---------|-------------|
| `binary` | 2 classes | 0 = baisse/flat, 1 = hausse |
| `ternary` | 3 classes | 0 = short (baisse), 1 = flat (neutre), 2 = long (hausse) |

En mode ternaire, les poids de classe sont asymétriques pour contrer le déséquilibre : `[1.5, 1.0, 1.5]` (short, flat, long).

### 4.2 Features utilisées (`modelFactory/features.py`)

#### Features V1 (13 colonnes) — dérivées OHLCV
`daily_return, log_return, intraday_range, overnight_gap, close_to_vwap, volume_ratio_20, rolling_volatility_20, rolling_volatility_60, rolling_mean_return_5, rolling_mean_return_20, rsi_14, atr_14_norm, is_filled`

#### Features Expert (18 colonnes supplémentaires)
Distances aux SMA/EMA, momentum, force relative vs marché, régimes bull/risk-off

#### Features Sentiment (4 colonnes) — si `include_sentiment=True`
`sentiment_net_mean_1d, sentiment_confidence_mean_1d, news_count_log, major_event_flag`

#### Features Contexte Selector (23 colonnes) — si `include_selector_context=True`
`trend_score, vcp_score, final_score, short_score, market_cap, beta_126, spread_bps, days_to_earnings`, etc.

#### Features Cross-Sectionnelles — si `enable_cross_sectional=True`
Rangs cross-sectionnels dans l'univers (ret_20_rank, relative_strength_rank, volatility_rank, dollar_volume_rank)

### 4.3 Target (étiquette à prédire)

La target est construite par `build_target()` :

- **Binary** : `1` si le rendement forward (J+horizon) > `target_threshold_up` (ex: +2%), sinon `0`
- **Swing Cash** : `1` si rendement > seuil UP, `0` si rendement < seuil DOWN, `NaN` (ignoré) si entre les deux

$$\text{target\_binary} = \mathbb{1}[r_{t, t+horizon} > threshold\_up]$$

### 4.4 Pipeline d'entraînement (`modelFactory/trainer.py`)

```python
# 1. Chargement des données
bars_df = load_symbol_bars(symbol, start, end)
sentiment_df = load_symbol_sentiment(symbol)    # optionnel
selector_df = load_symbol_selector_context(symbol)  # optionnel
benchmark_df = load_benchmark_bars()

# 2. Feature engineering
features_df = compute_features(bars_df, sentiment_df, benchmark_df, selector_df)

# 3. Split chronologique (pas de shuffle !)
train, val, test = chrono_split(features_df, train_ratio=0.70, val_ratio=0.15)

# 4. Scaling (StandardScaler)
scaler = FeatureScaler().fit(train)
train_scaled = scaler.transform(train)

# 5. Dataset de séquences (seq_len=20 jours)
train_dataset = SequenceDataset(train_scaled, seq_len=20, target_col="target")

# 6. Training PyTorch Lightning
model = LSTMAttentionModule(input_size=n_features, hidden_size=128, num_layers=2, dropout=0.3)
trainer = L.Trainer(max_epochs=50, callbacks=[EarlyStopping, ModelCheckpoint])
trainer.fit(model, train_loader, val_loader)

# 7. Calibration Platt (optionnelle)
calibrator = PlattCalibrator()
calibrator.fit(val_margins, val_labels)

# 8. Challengers optionnels (CatBoost, LightGBM)
catboost_metrics = run_catboost_baseline(train, val, test)
lightgbm_metrics = run_lightgbm_baseline(train, val, test)

# 9. Sélection du champion
champion = select_champion(lstm_metrics, catboost_metrics, lightgbm_metrics)
```

### 4.5 Walk-forward ML (`generate_walk_forward_splits()`)

Le trainer supporte aussi le **walk-forward ML** : on entraîne sur des fenêtres glissantes (expanding window) pour valider la robustesse temporelle.

#### Fichiers clés :
- `modelFactory/model.py` — `LSTMAttentionModule`, `LSTMAttentionClassifier`, `TemporalAttention`
- `modelFactory/trainer.py` — `train_symbol()`
- `modelFactory/features.py` — `compute_features()`, `get_feature_columns()`
- `modelFactory/dataset.py` — `SequenceDataset`, `chrono_split()`, `FeatureScaler`

---

## 5. ML — PRÉDICTION LONG ET SHORT

### 5.1 Service d'inférence (`modelFactory/predictor.py`)

```python
# Pour chaque symbole candidat :
# 1. Charger les artefacts du champion
checkpoint = torch.load(f"artifacts/models/{symbol}/champion.ckpt")
scaler = pickle.load(open(f"artifacts/models/{symbol}/scaler.pkl", "rb"))
calibrator = pickle.load(open(f"artifacts/models/{symbol}/calibrator.pkl", "rb"))

# 2. Charger les dernières barres + features
bars = load_symbol_bars(symbol, lookback=252)
features = compute_features(bars, include_sentiment=True, include_selector_context=True)

# 3. Construire la séquence d'entrée (derniers seq_len jours)
sequence = features.tail(seq_len)  # 20 jours
sequence_scaled = scaler.transform(sequence)

# 4. Inférence
model.eval()
with torch.no_grad():
    logits, attn_weights = model(sequence_scaled)  # [1, num_classes]
    probs = softmax(logits)

# 5. Calibration Platt (si disponible)
if calibrator and calibrator.fitted:
    margin = logits[:, 1] - logits[:, 0]  # binaire
    calibrated_proba = calibrator.predict_proba(margin)

# 6. Insertion dans model_predictions (DB)
insert_predictions(symbol, predicted_proba, prediction_date)
```

### 5.2 Pour les shorts

En mode **ternaire** (num_classes=3), le modèle produit 3 probabilités :

| Classe | Index | Interprétation |
|--------|-------|----------------|
| Short  | 0     | Probabilité de baisse significative |
| Flat   | 1     | Probabilité de stagnation |
| Long   | 2     | Probabilité de hausse significative |

En mode **binaire** (num_classes=2), on a :
- `proba_long = probs[:, 1]` — probabilité de hausse
- Pour le short, on peut utiliser `1 - proba_long` comme approximation

### 5.3 Drift Monitoring (`modelFactory/drift_monitor.py`)

Avant d'utiliser les prédictions, le système vérifie la **dérive du modèle** :
- **KS test** : compare la distribution des prédictions actuelles vs baseline 30 jours
- **PSI** (Population Stability Index)
- Statuts : `OK` / `WARN` / `ALERT`
- Si `ALERT` → le **ML kill-switch** (`risk_management/ml_gate.py`) désactive la consommation des prédictions ML

#### Fichiers clés :
- `modelFactory/predictor.py` — `predict_symbol()`
- `modelFactory/drift_monitor.py` — drift detection
- `modelFactory/drift_policy.py` — décisions de drift
- `risk_management/ml_gate.py` — ML kill-switch

---

## 6. MODULE RISQUE — SÉLECTION LONG ET SHORT

### 6.1 Pipeline complet (`risk_management/portfolio_builder.py`)

Le `PortfolioBuilder.build()` prend les candidats du selector et les transforme en portefeuille final :

```
Candidats (CandidateScore)
  │
  ├─ 0. Scoring directionnel (regime-aware + rotation momentum)
  │     → Ajuste les poids selon le régime marché (normal / capital_preservation)
  │
  ├─ 0bis. Filtre anti-faux-départs (Breakout Confirmation)
  │     → Exige min N jours de présence dans les candidats (shorts exemptés)
  │
  ├─ 0ter. Seuil de score minimum
  │     → Long : score_used >= min_score_threshold
  │     → Short : score_used >= min_score_threshold_short
  │
  ├─ 0quat. Filtres de concentration
  │     → Max trades par symbole (fenêtre glissante)
  │     → Blacklist après N pertes consécutives
  │
  ├─ 1. Enrichissement → conviction score
  │     → Fusion quant + ML (via core.conviction)
  │
  ├─ 2. Filtre de corrélation
  │     → Pearson ou Factoriel (si enable_factor_model=True)
  │     → Garde les plus hautes convictions, rejette les corrélés
  │
  ├─ 2bis. Contraintes factorielles (si enable_factor_model=True)
  │     → Max beta portefeuille, max concentration par facteur
  │
  ├─ 3. Sizing (Kelly ou ATR)
  │     → Calcule le nombre d'actions
  │
  ├─ 4. Risk Checker
  │     → Vérifie contraintes (poids max, secteur max, ADV, circuit breaker)
  │
  └─ 5. Décision finale (ACCEPTED / REDUCED / REJECTED)
```

### 6.2 Conviction Score — Fusion Quant + ML

C'est le **score clé** qui détermine tout. Défini dans `core/conviction.py` :

#### Pour les LONGS :

$$\text{conviction\_long} = 0.40 \times score\_quant + 0.60 \times proba\_ml\_long$$

Clampé dans [0, 1].

- `score_quant` = `final_score` du selector (ou `final_score_sentiment` si boost activé)
- `proba_ml_long` = prédiction ML (probabilité que le rendement futur > seuil)
- Poids par défaut : **40% quant, 60% ML**

#### Pour les SHORTS (`compute_conviction_short()`) :

$$\text{conviction\_short} = 0.40 \times (1 - score\_quant) + 0.60 \times proba\_ml\_short$$

- Le score quant est **inversé** (un bon long a un score élevé → mauvais short)
- `proba_ml_short` = probabilité de baisse prédite par le ML (en mode ternaire)

### 6.3 Kelly Sizing (`risk_management/kelly.py`)

Le Kelly Sizer V2 combine :

$$p_{eff} = \alpha \times proba\_ml + (1 - \alpha) \times win\_rate\_historique$$

$$f_{kelly} = p_{eff} - \frac{1 - p_{eff}}{payoff\_ratio}$$

$$f_{fraction} = f_{kelly} \times kelly\_multiplier$$

$$shares = \frac{equity \times risk\_per\_trade \times f_{fraction}}{ATR \times stop\_multiple}$$

Borné par la limite ATR.

### 6.4 Filtre de Corrélation (`risk_management/correlation_filter.py`)

**Algorithme glouton** :
1. Trie les candidats par conviction décroissante
2. Pour chaque candidat, vérifie la corrélation Pearson avec les déjà-sélectionnés
3. Si `|corr| > correlation_threshold` (défaut 0.70) → **REJETÉ**
4. Sinon → **ACCEPTÉ**

Alternative : **filtre factoriel** (`factor_model.py`) qui utilise un modèle à 4 facteurs (market, size, momentum, value) avec covariance EWMA.

### 6.5 Circuit Breaker (`risk_management/circuit_breaker.py`)

Bloque les entrées si :
- **Drawdown** > seuil (ex: -10%)
- **Perte journalière** > seuil (ex: -3%)
- Supporte un mode **dégradé** (allocation réduite)

### 6.6 Flux de décision complet

```mermaid
graph TD
    A[Candidats Selector] --> B[Regime Scoring]
    B --> C[Breakout Filter]
    C --> D[Score Threshold]
    D --> E[Concentration Filters]
    E --> F["Conviction Fusion: 40% quant + 60% ML"]
    F --> G[Correlation Filter]
    G --> H[Factor Constraints]
    H --> I[Kelly Sizing]
    I --> J[Risk Checker]
    J --> K{Décision}
    K -->|OK| L[ACCEPTED]
    K -->|Corrélation| M[REJECTED: CORRELATION]
    K -->|Sizing| N[REJECTED: SIZING]
    K -->|Contrainte| O[REJECTED: CONSTRAINT]
    K -->|Circuit Breaker| P[REJECTED: CIRCUIT_BREAKER]
```

#### Fichiers clés :
- `risk_management/portfolio_builder.py` — `PortfolioBuilder.build()`
- `core/conviction.py` — `fuse()`, `fuse_short()`, `compute_conviction()`, `compute_conviction_short()`
- `risk_management/kelly.py` — `KellySizer.compute()`
- `risk_management/correlation_filter.py` — `filter_correlated()`
- `risk_management/circuit_breaker.py` — `CircuitBreaker`
- `risk_management/concentration.py` — `SymbolTradeTracker`, `ConsecutiveLossTracker`
- `risk_management/factor_model.py` — CWMS 4-factor model

---

## 7. RÉSUMÉ SYNTHÉTIQUE

| Question | Réponse |
|----------|---------|
| **Comment on calcule les scores long ?** | `final_score = 0.50×(trend+vcp)/2 + 0.30×total_score + 0.20×RSI`, winsorisé puis normalisé [0,1], avec neutralisation sectorielle |
| **Comment on calcule les scores short ?** | Score baissier composite indépendant : 30% trend faible + 25% RSI bas + 25% prix<SMA50 + 20% prix<SMA200 |
| **Comment le sentiment impacte long/short ?** | Fusion ternaire : `w_quant×score + w_sentiment×sentiment_norm + w_macro×macro_norm`. Mais par défaut `w_sentiment=0`, `w_macro=0` car IC non significatif |
| **Qu'est-ce que le forward sentiment ?** | Walk-forward calibration : backtest OOS par folds glissants pour trouver les meilleurs poids (sentiment, macro, quant). Produit `latest_best_weights.json` |
| **Son impact ?** | Quand calibré et appliqué, ajuste le `final_score` en ajoutant une composante sentiment/macro. Mais la calibration confirme que le quant seul est optimal |
| **Comment ML entraîne long/short ?** | LSTM 2 couches + Attention temporelle sur séquences de 20 jours. Features OHLCV + sentiment + contexte selector. Target = rendement forward binaire ou ternaire. Split chronologique avec purge |
| **Comment ML prédit ?** | Charge champion model → compute features → inférence → softmax → calibration Platt → `predicted_proba` inséré en DB |
| **Comment le risque sélectionne ?** | 1) Regime scoring 2) Breakout filter 3) Score threshold 4) Concentration 5) Conviction = 40%×quant + 60%×ML 6) Corrélation filter 7) Factor constraints 8) Kelly/ATR sizing 9) Circuit breaker → Décision finale |

---

## 8. GLOSSAIRE DES FICHIERS CLÉS

| Fichier | Rôle |
|---------|------|
| `selector/ranking.py` | Fusion scores, neutralisation sectorielle, rank_and_select |
| `selector/short_score.py` | Score baissier dédié pour shorts |
| `selector/factors.py` | Calcul facteurs techniques (trend, VCP, MA, ATR, beta) |
| `selector/regime_scoring.py` | Ajustement des poids selon régime de marché |
| `core/conviction.py` | Formule de fusion conviction (quant+ML+sentiment) |
| `event_sentiment/signal_aggregator.py` | Fusion scores quant + sentiment → final_score_sentiment |
| `event_sentiment/scoring.py` | FinBERT sentiment scoring |
| `event_sentiment/aggregation.py` | Agrégation journalière ticker/secteur |
| `event_sentiment/macro_rules.py` | Détection événements macro |
| `backtesting/sentiment_calibration.py` | Calibration walk-forward des poids sentiment |
| `backtesting/walk_forward.py` | Résolution des poids walk-forward calibrés |
| `modelFactory/model.py` | LSTM + Temporal Attention (PyTorch Lightning) |
| `modelFactory/trainer.py` | Service d'entraînement mono-symbole |
| `modelFactory/predictor.py` | Service d'inférence |
| `modelFactory/features.py` | Feature engineering (OHLCV + sentiment + selector) |
| `modelFactory/dataset.py` | SequenceDataset, splits chronologiques |
| `modelFactory/drift_monitor.py` | Détection de dérive ML (KS test + PSI) |
| `risk_management/portfolio_builder.py` | Construction du portefeuille final |
| `risk_management/kelly.py` | Kelly fractional sizing V2 |
| `risk_management/correlation_filter.py` | Filtre de corrélation glouton |
| `risk_management/circuit_breaker.py` | Circuit breaker (drawdown, perte journalière) |
| `risk_management/concentration.py` | Filtres anti-répétition et blacklist |
| `risk_management/factor_model.py` | Modèle factoriel CWMS 4 facteurs |
| `risk_management/ml_gate.py` | Kill-switch ML (drift policy) |

---

> **Dernière mise à jour** : 2026-06-24
> **Prochaine mise à jour** : après discussion continue
