# Alignement des Échelles — Diagnostic Normalisation avant Fusion ML/Quant

> **Date** : 2026-06-22
> **Statut** : ✅ RAS — La normalisation est correctement appliquée
> **Verdict** : Pas de bug d'échelle. Les deux composantes sont en [0, 1] avant fusion.

---

## 1. La question posée

> *Si votre modèle ML renvoie une probabilité entre 0 et 1, mais que votre scanner quantitatif renvoie un z-score ou un score brut (ex: entre −3 et +3 ou 0 et 100), la brique la plus grande va mathématiquement écraser l'autre, rendant vos coefficients de pondération (60/40) totalement obsolètes.*

C'est une question légitime. Voici le traçage complet de bout en bout.

---

## 2. Traçage complet des échelles

### 2.1 Chemin du score quantitatif (`score_used`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 1 — Screener (screener/pipeline.py)                           │
│                                                                     │
│   liquidity_score       = percentile_rank * 100  → [0, 100]        │
│   relative_strength_sc  = percentile_rank * 100  → [0, 100]        │
│   historical_range_pct  = percentile_rank * 100  → [0, 100]        │
│                                                                     │
│   total_score = (Σ weight_i * score_i) / Σ weight_i  → [0, 100]   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 2 — merge_scores() (selector/ranking.py:220-230)             │
│                                                                     │
│   normalized_total_score = winsorize_and_normalize(total_score)    │
│     → winsorisation [1%, 99%] + min-max → [0, 1]  ✅              │
│                                                                     │
│   normalized_rsi = winsorize_and_normalize(relative_strength_index)│
│     → winsorisation [1%, 99%] + min-max → [0, 1]  ✅              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 3 — _apply_selection_explainability (selector/ranking.py)    │
│                                                                     │
│   trend_vcp = 0.50 * 0.5 * (trend_score + vcp_score)  → [0, 0.50]│
│   total     = 0.30 * normalized_total_score              → [0, 0.30]│
│   rsi       = 0.20 * normalized_rsi                     → [0, 0.20]│
│                                                                     │
│   final_score = Σ composantes                           → [0, 1.00] │
│                                                                     │
│   ✅ Garanti par les poids (0.50+0.30+0.20 = 1.00)                │
│   ✅ Chaque composante est bornée dans [0, 1] avant pondération   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 4 — Signal Aggregator (event_sentiment/signal_aggregator.py) │
│                                                                     │
│   quant_scores = final_score.clip(0.0, 1.0)  → [0, 1] ✅          │
│                                                                     │
│   sentiment_signal_norm = normalize_signed_signal(sentiment_net)   │
│     = ((clip(sentiment_net, -1, 1) + 1) / 2)  → [0, 1] ✅        │
│                                                                     │
│   macro_signal_norm = idem  → [0, 1] ✅                            │
│                                                                     │
│   final_score_sentiment = fuse_sentiment(quant, sentiment, macro)  │
│     = clip(0.75*q + 0.15*s + 0.10*m, 0.0, 1.0)  → [0, 1] ✅      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
            score_used ∈ [0, 1]  ✅
```

### 2.2 Chemin de la prédiction ML (`predicted_proba`)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 1 — Modèle LSTM/Attention (modelFactory/trainer.py)          │
│                                                                     │
│   logits = model(input)           → ℝ (non borné)                  │
│   raw_proba = softmax(logits)[:,1] → [0, 1]                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Étape 2 — Calibration Platt (modelFactory/calibration.py)          │
│                                                                     │
│   margin = logit_pos - logit_neg                                   │
│   calibrated = sigmoid(slope * margin + intercept)  → [0, 1] ✅   │
│                                                                     │
│   Si pas de calibrateur : raw_proba  → [0, 1] ✅                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
            predicted_proba ∈ [0, 1]  ✅
```

### 2.3 Point de fusion

```python
# core/conviction.py — compute_conviction()
conviction = clip(0.4 * score_used + 0.6 * predicted_proba, 0.0, 1.0)
```

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   score_used       ∈ [0, 1]   (quant, normalisé)               │
│   predicted_proba  ∈ [0, 1]   (ML, probabilité calibrée)       │
│                                                                  │
│   → MÊME ÉCHELLE → les poids 40/60 sont mathématiquement       │
│     cohérents. Pas d'écrasement d'échelle.                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Les normalisations en place (preuves par le code)

### 3.1 `winsorize_and_normalize()` — la normalisation centrale

**Fichier** : `selector/factors.py:58-88`

```python
def winsorize_and_normalize(
    series: pd.Series | None,
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> pd.Series:
    lo = float(non_null.quantile(lower_pct))
    hi = float(non_null.quantile(upper_pct))
    winsorized = numeric.clip(lo, hi)
    return ((winsorized - lo) / (hi - lo)).clip(0.0, 1.0)
```

Appliquée à :
- `total_score` (brut [0, 100]) → `normalized_total_score` [0, 1]
- `relative_strength_index` (brut) → `normalized_rsi` [0, 1]
- `total_score_neutralized` (z-score) → [0, 1]
- `relative_strength_index_neutralized` (z-score) → [0, 1]

### 3.2 `_normalize_signed_signal()` — normalisation sentiment

**Fichier** : `event_sentiment/signal_aggregator.py:786-792`

```python
@staticmethod
def _normalize_signed_signal(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    clipped = numeric.clip(-1.0, 1.0).fillna(0.0)
    return ((clipped + 1.0) / 2.0).astype(float)  # [-1,1] → [0,1]
```

### 3.3 `fuse_sentiment()` — clip de sécurité

**Fichier** : `core/conviction.py:147-173`

```python
def fuse_sentiment(*, quant_score, sentiment_signal_norm, macro_signal_norm, ...):
    fused = np.clip(
        quant_component + sent_component + macro_component,
        0.0, 1.0,  # ← clip explicite
    )
```

### 3.4 `_percentile_score()` — normalisation cross-sectionnelle

**Fichier** : `screener/pipeline.py:42-48`

```python
def _percentile_score(series: pd.Series) -> pd.Series:
    return numeric.rank(method="average", pct=True) * 100.0  # → [0, 100]
```

---

## 4. Points d'attention (nuances)

Bien que la normalisation d'échelle soit correcte, deux subtilités méritent d'être notées :

### 4.1 Distribution ≠ Échelle

Les deux composantes sont dans [0, 1], mais leurs **distributions** diffèrent :

| Composante | Distribution typique |
|---|---|
| `score_used` (quant) | Après winsorisation [1%, 99%] + min-max → distribution relativement **uniforme** étalée sur [0, 1] |
| `predicted_proba` (ML) | Après Platt scaling → tend à être **concentrée** autour de 0.5 (haute incertitude) ou vers les extrêmes (sur-confiance) |

**Conséquence** : la pondération 40/60 ne reflète pas directement la contribution *informationnelle*. Un `predicted_proba` qui varie de 0.48 à 0.52 apporte moins d'information discriminante qu'un `score_used` qui varie de 0.2 à 0.9 — même si les deux sont dans [0, 1].

**Recommandation** : lors de la calibration empirique (Phase 7), mesurer la **variance conditionnelle** de chaque composante plutôt que de se fier uniquement au ratio 60/40 théorique.

### 4.2 Walk-forward calibration — repondération possible

**Fichier** : `backtesting/weights_calibration.py`

Le module de calibration walk-forward peut ajuster les poids de fusion `score_weight` / `prediction_weight` (et aussi les poids `quant_weight` / `sentiment_weight` / `macro_weight`). C'est la bonne approche pour corriger le point 4.1.

### 4.3 Cas particulier : `aux_mask = False`

Quand aucun score auxiliaire (screener) n'est disponible, le `final_score` se réduit à :
```python
final_score = 0.5 * (trend_score + vcp_score)  # ∈ [0, 1]
```
Pas de normalisation additionnelle nécessaire car `trend_score` et `vcp_score` sont déjà dans [0, 1].

---

## 5. Vérification de tous les points d'entrée

| Source | Colonne | Échelle brute | Normalisation | Échelle finale |
|---|---|---|---|---|
| Screener | `total_score` | [0, 100] | `winsorize_and_normalize` | [0, 1] |
| Screener | `relative_strength_index` | Variable | `winsorize_and_normalize` | [0, 1] |
| Factors | `trend_score` | [0, 1] | Aucune (déjà borné) | [0, 1] |
| Factors | `vcp_score` | [0, 1] | Aucune (déjà borné) | [0, 1] |
| Sentiment | `sentiment_net_agg` | [-1, 1] | `_normalize_signed_signal` | [0, 1] |
| Sentiment | `sector_impact_agg` | [-1, 1] | `_normalize_signed_signal` | [0, 1] |
| ML | `predicted_proba` | [0, 1] | Aucune (probabilité native) | [0, 1] |
| ML | `proba_long` | [0, 1] | Aucune (probabilité native) | [0, 1] |
| ML | `proba_short` | [0, 1] | Aucune (probabilité native) | [0, 1] |

**Toutes les composantes qui entrent dans la fusion sont en [0, 1].** ✅

---

## 6. Tests existants qui valident ce comportement

- `tests/test_alpha_scanner.py` : vérifie les valeurs de `final_score`, `total_score_neutralized`, `relative_strength_index_neutralized` après fusion — toutes entre 0 et 1
- `tests/test_regime_scoring.py` : vérifie les composantes défensives
- `tests/test_alpha_scanner_sector_neutrality_property.py` : property-based tests sur la cohérence post-neutralisation
- `tests/test_backtesting_refactor.py` : `score_used=0.9` utilisé comme valeur de test (dans [0, 1])

---

## 7. Verdict

| Point vérifié | Statut |
|---|---|
| `score_used` (quant) normalisé avant fusion ? | ✅ Oui — `winsorize_and_normalize` + `clip [0,1]` |
| `predicted_proba` (ML) borné dans [0, 1] ? | ✅ Oui — softmax ou Platt sigmoid |
| Même échelle [0, 1] pour les deux ? | ✅ Oui |
| Les poids 40/60 sont-ils mathématiquement cohérents ? | ✅ Oui |
| Risque d'écrasement d'échelle ? | ❌ **Aucun** |
| Distribution différente (variance inégale) ? | ⚠️ Oui — à calibrer empiriquement (Phase 7) |

**Conclusion : la couche de normalisation est présente et correcte. Il n'y a PAS de bug d'échelle. Le piège numéro un est évité.** 🎉

---

## 8. Fichiers clés

| Fichier | Fonction | Rôle |
|---|---|---|
| `selector/ranking.py` | `merge_scores()` | Normalise `total_score`, `rsi` via winsorize |
| `selector/ranking.py` | `apply_factor_neutralization()` | Neutralise + re-normalise |
| `selector/ranking.py` | `_apply_selection_explainability()` | Compose `final_score` ∈ [0, 1] |
| `selector/factors.py` | `winsorize_and_normalize()` | Normalisation winsorized min-max |
| `event_sentiment/signal_aggregator.py` | `_normalize_signed_signal()` | [-1, 1] → [0, 1] |
| `event_sentiment/signal_aggregator.py` | `merge()` | Fusion ternaire quant+sentiment+macro |
| `core/conviction.py` | `fuse_sentiment()` | Fusion avec clip [0, 1] |
| `core/conviction.py` | `compute_conviction()` | Fusion conviction (ML + quant) [0, 1] |
| `modelFactory/calibration.py` | `PlattCalibrator.predict_proba()` | Calibration Platt → [0, 1] |
| `screener/pipeline.py` | `_percentile_score()` | Percentile rank → [0, 100] |
