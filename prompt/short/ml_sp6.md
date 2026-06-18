# ML Sprint 6 — Synthèse

_Date : 2026-06-18_

## Objectif
Intégrer les prédictions ML ternaires (`predicted_side`) dans le pipeline
d'exécution live et backtest. Le côté exécution (OMS, force-close, protections)
était déjà directionnel depuis le Sprint 3 trading.

## Ce qui était déjà fait (Sprint 3 trading)

| Fonctionnalité | Statut |
|---|---|
| `executor.py` force-close side-aware | ✅ |
| `order_intents.py` entry/TP/stop/trailing directionnel | ✅ |
| `cli.py` Option C injection live | ✅ |
| `limit_price_buffer_bps` directionnel | ✅ |

## Livrables Sprint 6 ML

### C1 — `_tag_short_candidates` : priorité ML

Si le DataFrame contient une colonne `predicted_side` (issue des prédictions ML) :
- Les lignes avec `predicted_side == "short"` reçoivent `side="sell"`
- Limité à `max_short_positions`
- Sans ML → fallback sur Option B/C (inchangé)

### C2 — Backtest : injection `predicted_side` dans `day_scores`

Avant l'appel à `_tag_short_candidates`, le `predicted_side` est extrait
de `predictions_df` et mergé dans `day_scores` :

```python
side_map = dict(zip(pred_day["symbol"], pred_day["predicted_side"]))
day_scores["predicted_side"] = day_scores["symbol"].map(side_map)
```

### C3 — Live : `predicted_side` dans le DataFrame candidats

Dans `cli.py`, le DataFrame temporaire inclut désormais `predicted_side`
depuis les prédictions ML chargées :

```python
"predicted_side": predictions.get(c.symbol).predicted_side
```

## Backtest ✅

| Composant | Fichier | Statut |
|---|---|---|
| ML priority dans tagging | `risk_bridge.py:_tag_short_candidates` | ✅ |
| Injection predicted_side | `risk_bridge.py` | ✅ |

## Live ✅

| Composant | Fichier | Statut |
|---|---|---|
| ML priority dans tagging | `risk_bridge.py` (shared) | ✅ |
| predicted_side dans DF | `cli.py` | ✅ |
| Exécution directionnelle | `executor.py` + `order_intents.py` | ✅ (Sprint 3) |

## Priorité de sélection short

```
1. ML predicted_side == "short"  →  side = "sell"  (si dispo)
2. Option B short_score          →  top-N          (si dispo)
3. Option C final_score           →  bottom-N       (fallback)
```

## Tests

```
115 passed, 2 warnings
```

## Prochain sprint

**ML Sprint 7** — Gouvernance et monitoring.
