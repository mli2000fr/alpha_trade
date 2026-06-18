# Sprint 5 — Synthèse

_Date : 2026-06-18_

## Objectif
Option B — remplacer le bottom-N final_score (Option C) par un `short_score`
dédié basé sur des facteurs baissiers (trend_score, RSI, SMA). Finaliser
les ajustements de compatibilité long/short.

## Livrables

### C1 — `selector/short_score.py` (NOUVEAU)

Module de calcul du score baissier composite.

| Fonction | Description |
|---|---|
| `compute_short_score(day_df, close_df, trade_day)` | Calcule un score 0-1 (plus élevé = plus baissier) |
| `enrich_with_short_score(day_df, ...)` | Ajoute la colonne `short_score` au DataFrame |

**Facteurs :**
| Facteur | Poids | Condition baissière |
|---|---|---|
| `trend_score` | 30% | trend faible → 1-trend |
| `relative_strength_index` | 25% | RSI bas → 1-RSI/100 |
| Prix < SMA50 | 25% | close < sma_50 |
| Prix < SMA200 | 20% | close < sma_200 |

Les facteurs SMA nécessitent `close_df` (non disponible en live sans chargement OHLCV).
Sans `close_df`, le score est calculé uniquement sur trend_score + RSI.

### C2 — `_tag_short_candidates` : support dual score

```python
if "short_score" in result.columns:
    score_col = "short_score"   # Option B : top-N (plus baissier)
    ascending = False
elif "score" in result.columns:
    score_col = "score"          # Option C : bottom-N (pire final_score)
    ascending = True
```

Si `short_score` est absent → fallback automatique sur Option C.

### C3 — Injection backtest (`risk_bridge.py`)

```python
from selector.short_score import enrich_with_short_score
day_scores = enrich_with_short_score(day_scores)
day_scores = _tag_short_candidates(day_scores, ...)
```

### C4 — Injection live (`cli.py`)

```python
from selector.short_score import enrich_with_short_score
candidates_df = enrich_with_short_score(candidates_df)
candidates_df = _tag_short_candidates(candidates_df, ...)
```

⚠️ Le live n'a pas les colonnes `trend_score`/`relative_strength_index` dans
`CandidateScore`. Le short_score se dégrade → fallback Option C.
Pour le full Option B en live, ajouter ces colonnes à `CandidateScore` (DB migration).

### C5 — Tests de non-régression

| Test | Résultat |
|---|---|
| `test_portfolio_builder.py` (12) | ✅ |
| `test_regime_scoring.py` (30) | ✅ |
| `test_order_intents.py` (33) | ✅ |
| **Total** | **75 passed** |

## Backtest ✅

| Composant | Fichier | Statut |
|---|---|---|
| short_score compute | `selector/short_score.py` | ✅ |
| enrich before tag | `risk_bridge.py` | ✅ |
| dual score in tag | `risk_bridge.py` | ✅ |
| Fallback Option C | `risk_bridge.py` | ✅ (auto) |

## Live ✅

| Composant | Fichier | Statut |
|---|---|---|
| enrich before tag | `cli.py` | ✅ |
| dual score in tag | `risk_bridge.py` (shared) | ✅ |
| Colonnes trend_score/RSI | `CandidateScore` | ⚠️ Manquantes → fallback Option C |

## Calibration Option B

Pour calibrer Option B sur backtest 2020-2022 :

```bash
python -m backtesting run --start 2020-01-01 --end 2022-12-31 \
  --equity 5000 --capital-preset-key capital_0_5000 \
  --phase2-mode risk_execution --engine-mode pipeline
```

Comparer les métriques long/short dans le rapport console :
- `Trades Short` — nombre et win rate des shorts
- `short_pnl_total` — PnL total des shorts

L'Option B devrait produire des shorts plus pertinents (trend faible + RSI bas)
que l'Option C (bottom-N final_score).

## Améliorations futures

| Point | Priorité |
|---|---|
| Ajouter `trend_score`, `relative_strength_index` à `CandidateScore` | Moyenne |
| Calculer SMA50/200 dans `risk_bridge` depuis `close_df` | Moyenne |
| Calibrer les poids des facteurs short_score par ablation | Faible |
| Option D — ML ternaire long/flat/short | long terme |
