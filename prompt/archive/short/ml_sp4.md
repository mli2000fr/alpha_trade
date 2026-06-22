# ML Sprint 4 — Synthèse

_Date : 2026-06-18_

## Objectif
Rendre le ranking, la conviction et le risk management bilatéraux : les shorts
ont leur propre seuil de score, leur propre formule de conviction, et les
trackers de concentration sont side-aware.

## Livrables

### C1 — `core/conviction.py` : conviction directionnelle

| Fonction | Description |
|---|---|
| `compute_conviction_short(score_used, predicted_proba_short, ...)` | Fusionne score quant inversé + proba short ML |

**Formule long** : `score_weight × score_used + prediction_weight × predicted_proba`

**Formule short** : `score_weight × (1 - score_used) + prediction_weight × proba_short`

### C2 — `risk_management/config.py` : `min_score_threshold_short`

```python
min_score_threshold_short: float = 0.0  # ML Sprint 4
```

Seuil distinct pour les shorts. `0.0` = pas de filtre (comportement actuel).

### C3 — `risk_management/portfolio_builder.py` : seuil + conviction directionnels

| Changement | Détail |
|---|---|
| Score threshold | Applique `min_score_threshold_short` pour `side="sell"`, `min_score_threshold` pour `side="buy"` |
| Conviction | Utilise `compute_conviction_short` si `side="sell"` avec `proba_short` du ML, sinon `compute_conviction` standard |

### C4 — Trackers de concentration (déjà faits — Sprint 5 trading)

- `SymbolTradeTracker.allow_entry/record(side=...)` ✅
- `ConsecutiveLossTracker.is_blacklisted/record(side=...)` ✅
- `BreakoutConfirmationTracker` : ignore shorts ✅

### C5 — Ranking bilatéral (existant, réutilisé)

- `selector/ranking.py` : `rank_and_select()` trie par `final_score` descendant → top-N longs
- `backtesting/risk_bridge.py` : `_tag_short_candidates()` trie par `short_score`/`score` → top-N shorts
- Les deux shortlists sont déjà produites séparément

## Backtest ✅

| Composant | Fichier | Statut |
|---|---|---|
| Seuil short distinct | `portfolio_builder.py` | ✅ |
| Conviction short | `core/conviction.py` → `portfolio_builder.py` | ✅ |
| Trackers side-aware | `concentration.py` | ✅ (Sprint 5) |
| Double shortlist | `ranking.py` + `risk_bridge.py` | ✅ (existant) |

## Live ✅

| Composant | Statut |
|---|---|
| `PortfolioBuilder` (commun) | ✅ |
| `core/conviction.py` (commun) | ✅ |
| Trackers (communs) | ✅ |

## Tests

```
115 passed, 2 warnings
```

## Prochain sprint

**ML Sprint 5** — Backtest directionnel complet :
- `DrawdownCircuitBreaker.allocation_scale(side)` déjà fait
- Force-close déjà side-aware (backtest + live)
- Time stop déjà directionnel
- Pullback entry déjà inversé pour shorts
