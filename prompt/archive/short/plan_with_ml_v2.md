# Plan de transformation **long + short avec ML** — v2.1 mise à jour

_Date : 2026-06-18 — Révision post-Quick Wins long-only_

## 0. Préambule : ce qui a changé depuis la v1 du plan (2026-06-13)

Les optimisations long-only suivantes impactent directement le ML directionnel :

### 0.1 Scoring regime-aware (`selector/regime_scoring.py`)
- `apply_regime_weights()` avec `CAPITAL_PRESERVATION_WEIGHTS` (0.25/0.15/0.10 + 0.22/0.13/0.15) et `NORMAL_WEIGHTS`
- `MomentumRotationState` : rotation automatique si momentum cumulé < -3% sur 4 semaines
- `evaluate_momentum_rotation()` : combine régime + rotation factor
- Intégré backtest (`risk_bridge.py`) et live (`portfolio_builder.py`)
- ➜ **Impact ML Sprint 4** : le scoring directionnel long+short pourra s'appuyer sur cette architecture de poids factoriels par régime. Chaque side (long/short) pourra avoir ses propres poids par régime.

### 0.2 Régime de marché durci (`config.yaml`)
- `hard_mode_*` : `close_only` (bloque les entrées, pas juste `capital_preservation`)
- `critical_mode_*` : `close_only`
- `inverted_curve_mode` : `close_only`
- `hard_requires_sentiment_warning` : `false` (le spike 10Y seul suffit)
- ➜ **Impact ML Sprint 4/7** : la matrice d'autorisation directionnelle (`allowed_long_entries`/`allowed_short_entries`) devra composer avec `close_only` comme mode « ni long ni short ». Le ML gate devra être side-aware.

### 0.3 Force-close sur circuit breaker
- `force_close_on_breaker: true`, `force_close_pct: 1.0`
- `DrawdownCircuitBreaker.just_tripped()` + `CircuitBreaker.just_tripped()`
- Backtest et live : liquidation des positions au déclenchement
- ➜ **Impact ML Sprint 5** : le backtest ML devra intégrer le force-close directionnel. Les métriques de contribution short aux drawdowns devront isoler l'effet du force-close.

### 0.4 Concentration / diversification
- `SymbolTradeTracker`, `ConsecutiveLossTracker`, `BreakoutConfirmationTracker`
- Max positions : 3 (micro-capital)
- ➜ **Impact ML Sprint 4** : les trackers devront être side-aware. Un symbole pourrait être éligible en long mais blacklisté en short (ou inversement).

### 0.5 TP/SL/Time stop recalibrés
- TP : 12% | TS (trailing) : 10% | Trailing activation : 2.0R | Time stop : 20j
- Pullback entry : limit -1% sous le signal
- Score threshold : 0.7 minimum
- ➜ **Impact ML Sprint 5** : les valeurs de TP/SL pour le short devront être distinctes et non symétriques. Le pullback entry doit être inversé pour les shorts.

---

## 1. Objet du document (inchangé)

Ce document traite la **transformation complète de l'application en long + short avec Machine Learning**.

L'objectif : faire évoluer l'application d'une logique **bullish / long-only / top-N descendant** vers une logique **directionnelle / long-short / allocation bilatérale / ML aware**.

---

## 2. Résumé exécutif (mise à jour)

### 2.1 Conclusion principale (inchangée)

Le système reste **doublement long-only** (métier/exécution + ML/sélection). Les optimisations récentes ont renforcé le long-only mais n'ont pas changé sa nature directionnelle.

### 2.2 Ce qui est déjà réutilisable (mis à jour)

| Brique | Statut | Impact ML |
|---|---|---|
| Scoring regime-aware | ✅ Prêt | Architecture de poids factoriels par régime → base pour scoring directionnel |
| `MomentumRotationState` | ✅ Prêt | Rotation factor → pourra être étendu avec `short_momentum_state` |
| Force-close breaker | ✅ Prêt | Déjà side-aware (liquidation) → base pour métriques de DD par side |
| Concentration trackers | ✅ Prêt | À rendre side-aware pour le ML directionnel |
| `LSTMAttentionClassifier(num_classes)` | ✅ Prêt | Backbone extensible à 3 classes |
| `PlattCalibrator` | ✅ Prêt | À étendre pour calibration multi-classe |
| Pullback entry | ✅ Prêt | À inverser pour les shorts |
| Score threshold 0.7 | ✅ Prêt | À dupliquer en `min_score_threshold_short` |

### 2.3 Ce qui bloque aujourd'hui (inchangé, sauf ajouts)

**Côté ML :**
- `build_target()` ne produit que des labels binaires (`binary`, `swing_cash`)
- Les métriques sont `Binary*` (Accuracy, AUROC, etc.)
- `core/conviction.py` fusionne un score quant et une probabilité de hausse → **pas de conviction short**
- `selector/ranking.py` trie descendant sur `final_score` → **pas de shortlist short**
- La persistance ML ne stocke pas `predicted_side`

**Côté trading :**
- Risk, backtest, exécution restent long-only (cf. `plan_v2.md`)
- Le force-close existe mais n'est pas side-aware pour l'allocation

---

## 3. Impacts des évolutions récentes sur les sprints ML

### Sprint 1 — Target ML et dataset (IMPACT : FAIBLE)

Le `target_mode='ternary'` devra produire `{-1, 0, +1}`. Les seuils long/short devront être calibrés en tenant compte des valeurs actuelles de TP (12%) — un short réussi doit avoir un rendement négatif suffisant pour justifier le risque.

### Sprint 2 — Modèle, métriques, calibration (IMPACT : FAIBLE)

Rien de spécifique aux évolutions récentes. Le passage à 3 classes reste le même.

### Sprint 3 — Persistance et registre ML (IMPACT : FAIBLE)

Le schéma de `model_predictions` doit stocker `predicted_side`, `proba_long`, `proba_flat`, `proba_short`. Les consommateurs aval (`risk_management`, `backtesting`) devront lire ce nouveau schéma.

### Sprint 4 — Ranking, conviction et risk management bilatéraux (IMPACT : ÉLEVÉ)

**Ce qui change :**
- Le `selector/ranking.py` devra produire **deux shortlists** (long et short) en utilisant l'infrastructure de scoring regime-aware existante.
- `CAPITAL_PRESERVATION_WEIGHTS` pourra être décliné en version long et version short.
- Les trackers de concentration devront être side-aware : un symbole blacklisté en long peut être éligible en short.
- Le `min_score_threshold` de 0.7 devra avoir un équivalent short (`min_score_threshold_short`).
- Le `MomentumRotationState` pourra être étendu avec un `ShortMomentumState` pour tracker la performance relative long vs short.

### Sprint 5 — Backtest directionnel complet (IMPACT : ÉLEVÉ)

**Ce qui change :**
- Le `DrawdownCircuitBreaker` a déjà `force_close_on_breaker`, `force_close_pct`, `just_tripped()`. Il faut le rendre side-aware pour l'allocation : `allocation_scale(side)` et `degraded_short_allocation_pct`.
- Le force-close doit pouvoir liquider séparément les longs et les shorts.
- Le time stop (20j) doit être directionnel.
- Le pullback entry doit être inversé pour les shorts.
- Les diagnostics backtest doivent inclure `force_close_exits_long` et `force_close_exits_short`.

### Sprint 6 — Exécution live (IMPACT : MODÉRÉ)

Mêmes impacts que `plan_v2.md` Sprint 3.

### Sprint 7 — Gouvernance ML et monitoring (IMPACT : FAIBLE)

Les métriques de production doivent inclure l'impact du force-close par side, et la performance du rotation factor directionnel.

---

## 4. Plan de sprint révisé (ordre inchangé)

1. **Sprint 0** — ADR, contrats de données, feature flags
2. **Sprint 1** — Target ML ternaire + dataset
3. **Sprint 2** — Modèle 3 classes + calibration
4. **Sprint 3** — Persistance et registre ML
5. **Sprint 4** — Ranking, conviction et risk bilatéraux ← **le plus impacté**
6. **Sprint 5** — Backtest directionnel ← **le plus impacté**
7. **Sprint 6** — Exécution live / paper
8. **Sprint 7** — Gouvernance et monitoring

---

## 5. Checklist pré-démarrage Sprint 0 ML

- [ ] Vérifier que le scoring regime-aware est actif backtest + live
- [ ] Vérifier que `MomentumRotationState` est instancié backtest + live
- [ ] Vérifier que les trackers de concentration fonctionnent backtest + live
- [ ] Vérifier que le force-close est actif et testé
- [ ] Documenter les valeurs de TP/SL/time-stop pour référence calibration target ML
- [ ] Valider que `LSTMAttentionClassifier(num_classes=3)` est compatible avec l'infrastructure actuelle
