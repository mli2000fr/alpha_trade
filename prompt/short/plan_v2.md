# Plan d'intégration du **short** (hors ML) — v2.1 mise à jour

_Date : 2026-06-18 — Révision post-Quick Wins long-only_

## 0. Préambule : ce qui a changé depuis la v1 du plan (2026-06-13)

Les optimisations long-only suivantes ont été implémentées et **impactent directement**
le plan short. Elles sont à considérer comme des **prérequis déjà remplis** :

### 0.1 Régime de marché durci
- `hard_mode_backtest/live` : `capital_preservation` → `close_only` (bloque les entrées)
- `critical_mode_backtest/live` : `capital_preservation` → `close_only`
- `inverted_curve_mode` : `capital_preservation` → `close_only`
- `hard_requires_sentiment_warning` : `true` → `false`
- ➜ Le `MarketRegimeSnapshot` détecte désormais les bear markets et bloque les entrées. La matrice d'autorisation directionnelle (Sprint 0) devra s'appuyer sur cette base.

### 0.2 Scoring regime-aware
- `selector/regime_scoring.py` : `apply_regime_weights()`, `CAPITAL_PRESERVATION_WEIGHTS`, `NORMAL_WEIGHTS`
- `MomentumRotationState` : rotation automatique si momentum sous-performe -3% sur 4 semaines
- Intégré dans le backtest (`risk_bridge.py`) et le live (`portfolio_builder.py`)
- ➜ Le scoring directionnel du Sprint 4 (plan_with_ml.md) pourra réutiliser cette infrastructure.

### 0.3 TP/SL/Time stop recalibrés
- TP : 12% | TS (trailing) : 10% | Trailing activation : 2.0R | Time stop : 20 jours
- ➜ Les valeurs de TP/SL pour le short (Sprint 2) devront être distinctes et non symétriques.

### 0.4 Concentration / diversification
- `SymbolTradeTracker` : max 5 trades/symbole/180 jours
- `ConsecutiveLossTracker` : blacklist après 3 pertes consécutives (90 jours)
- `BreakoutConfirmationTracker` : confirmation de breakout sur N jours (défaut 1)
- Max positions : 3 pour le preset micro-capital
- ➜ Ces trackers devront être rendus side-aware (tracker séparé long/short ou champ `side`).

### 0.5 Force-close sur circuit breaker
- `force_close_on_breaker: true` dans `config.yaml`
- `force_close_pct: 1.0` (liquidation totale)
- `DrawdownCircuitBreaker.just_tripped()` détecte la transition
- Backtest : liquidation des positions au close du jour
- Live : `CircuitBreaker.just_tripped()` → `executor.py` soumet des market sell
- ➜ Le breaker est déjà partiellement side-aware (force-close). Le rendre complètement directionnel (allocation séparée long/short) est prévu au Sprint 2.

### 0.6 Pullback entry + score threshold
- `entry_limit_offset_pct: 0.01` (limit -1% sous le signal)
- `min_score_threshold: 0.7` (filtre les scores faibles)
- `entry_order_type: limit` + `limit_price_buffer_bps: -100` (live)
- ➜ Ces filtres devront être directionnels (ex: le pullback entry pour un short = +1% au-dessus du signal).

---

## 1. Objet et périmètre (inchangé)

Objectif : faire évoluer l'application d'un mode **long-only** vers un mode **long + short**.

Périmètre :
- le **backtest** ;
- le **pipeline live** (risk → targets → execution → protections → réconciliation → reporting) ;
- **sans traiter le ML** pour l'instant.

---

## 2. Conclusion rapide (mise à jour)

L'application reste **structurellement long-only** malgré les optimisations récentes.
Cependant, des fondations solides sont en place :

| Brique | Statut | Impact Short |
|---|---|---|
| Régime `close_only` | ✅ Opérationnel | Base pour `allowed_long_entries` / `allowed_short_entries` |
| Scoring regime-aware | ✅ Opérationnel | Base pour scoring directionnel long/short |
| Force-close breaker | ✅ Opérationnel | Déjà side-aware (liquidation) ; manque l'allocation directionnelle |
| Concentration trackers | ✅ Opérationnel | À rendre side-aware (trackers séparés long/short) |
| `ExecutionTarget.side` | ✅ Existe déjà | Prêt à consommer |
| `ExecutionPosition.net_qty` | ✅ Signé | Compatible positions courtes |

---

## 3. Recommandation d'architecture (inchangée)

La représentation canonique recommandée reste :
- `side: "buy" | "sell"` explicite partout en métier
- `qty` absolue sur targets/intents
- `net_qty` signé uniquement pour positions broker/interne

---

## 4. Impacts des évolutions récentes sur chaque sprint

### Sprint 0 — Cadrage technique (IMPACT : FAIBLE)

**Ajouts à prendre en compte :**
- Le `DrawdownCircuitBreaker` a déjà `force_close_on_breaker`, `force_close_pct`, `just_tripped()`. Le contrat de breaker side-aware (Sprint 2) doit s'appuyer sur cette base plutôt que de la refaire.
- La matrice régime → directions doit intégrer `close_only` (déjà actif) comme mode « ni long ni short, closes uniquement ».
- `core/direction.py` doit inclure un helper `compute_pullback_limit_price(entry_side, signal_price, offset_pct)` pour le pullback entry directionnel.

### Sprint 1 — Propagation du `side` (IMPACT : MODÉRÉ)

**Ajouts à prendre en compte :**
- Les trackers de concentration (`SymbolTradeTracker`, `ConsecutiveLossTracker`, `BreakoutConfirmationTracker`) dans `PortfolioBuilder` et `simulator.py` doivent accepter un `side` ou être dupliqués en version long/short.
- Le `min_score_threshold` de 0.7 est appliqué uniformément ; pour le short, il faudra un seuil distinct (`min_score_threshold_short`).
- Le `entry_limit_offset_pct` de 0.01 (pullback -1%) doit être inversé pour le short (limit +1% au-dessus du signal).

### Sprint 2 — Backtest bidirectionnel (IMPACT : ÉLEVÉ)

**Ce qui est déjà fait et réutilisable :**
- Le `DrawdownCircuitBreaker` a déjà `force_close_on_breaker` et `just_tripped()`. L'ajout de `allocation_scale(side)` pour le rendre side-aware peut se faire par extension plutôt que par refonte.
- Le `BacktestDiagnostics` a déjà `blocked_by_drawdown_breaker`, `blocked_by_concentration`, `blocked_by_breakout`. Ajouter `blocked_by_short_*` est mécanique.
- Les formules de PnL et mark-to-market sont encore long-only (cf. constats originaux §4.2.G).

**Nouveaux points critiques :**
- Le **time stop** (20 jours) doit être directionnel : pour un short, vérifier `close_price <= entry_price` (progrès short) au lieu de `close_price >= entry_price`.
- Le **pullback entry** doit être inversé pour les shorts : `limit_price = signal_price * (1 + offset_pct)`.
- Le **force-close** existant liquide tout sans distinction long/short. Après le Sprint 2, il devra respecter `force_close_pct` par side.

### Sprint 3 — Exécution live (IMPACT : MODÉRÉ)

**Ce qui est déjà fait et réutilisable :**
- L'`executor.py` a déjà la logique de force-close avec `just_tripped()` et soumission de market sell. L'extension au short (buy-to-cover) suit le même pattern.
- Le `CircuitBreaker` a déjà `just_tripped()` et `_was_tripped`.

**Nouveaux points :**
- La liquidation partielle (`force_close_pct`) doit être side-aware : liquider d'abord les shorts les plus perdants (rachat au plus haut), puis les longs.
- Le `entry_order_type: limit` + `limit_price_buffer_bps: -100` pour les longs doit devenir `limit_price_buffer_bps: +100` pour les shorts.

### Sprint 4 — Reporting (IMPACT : FAIBLE)

**Ajouts :**
- Les rapports doivent afficher `force_close_exits` (déjà dans les diagnostics backtest).
- Les métriques de PnL long/short doivent inclure l'impact du force-close.

### Sprint 5 — Tests (IMPACT : FAIBLE)

**Ajouts :**
- Tests de non-régression : vérifier que le force-close, le scoring regime-aware, et les trackers de concentration fonctionnent toujours après l'ajout du `side`.
- Tests spécifiques : force-close sur portefeuille mixte long/short.

---

## 5. Stratégie de sélection des candidats short

Le plan original `plan.md` ne précise pas **comment** générer les candidats short
en l'absence de ML. Cette section comble ce vide.

### 5.1 Recommandation : Option C — Short via `MomentumRotationState`

Le `MomentumRotationState` est **déjà câblé** backtest + live. Il détecte quand
le momentum sous-performe (-3% sur 4 semaines) et active les poids défensifs.
L'extension au short est conceptuellement simple :

```python
# Aujourd'hui : rotation → poids défensifs → moins de longs
if rotation_state.should_rotate():
    weights = CAPITAL_PRESERVATION_WEIGHTS

# Demain (Sprint 1) : rotation → activation short
if rotation_state.should_rotate():
    # Les pires scores deviennent des candidats short
    short_candidates = sorted(candidates, key=lambda c: c.score_used)[:max_short_positions]
    for c in short_candidates:
        c.side = "sell"
    # Les meilleurs scores restent des longs
    long_candidates = sorted(candidates, key=lambda c: -c.score_used)[:max_long_positions]
    for c in long_candidates:
        c.side = "buy"
```

**Pourquoi cette approche :**
- Ne shorter que quand le momentum sous-performe (pas en bull market)
- Réutilise l'infrastructure `MomentumRotationState` existante
- Le `final_score` est un proxy acceptable en première approximation : un score
  faible signifie que les facteurs momentum/trend/qualité sont défavorables
- Permet de valider toute la plomberie (side, backtest, exécution) rapidement

**Paramètres à ajouter dans `config.yaml` :**
```yaml
short_selling:
  enabled: false                    # feature flag global
  max_short_positions: 2            # nombre max de shorts simultanés
  min_score_for_short: 0.30         # score maximum pour être éligible short
  rotation_required: true           # exiger rotation_state.should_rotate()
  short_risk_per_trade_pct: 0.005   # risque par trade short (moitié du long)
  short_tp_pct: 0.08               # TP short (8% de baisse)
  short_trailing_pct: 0.10          # trailing stop short (10% de hausse)
  short_time_stop_days: 20          # time stop directionnel
```

### 5.2 Roadmap d'évolution du signal short

```
Phase 1 (Sprint 1-2) : Option C — MomentumRotationState
    → Shorts activés uniquement en période de sous-performance momentum
    → Signal = inversion du final_score (bottom-N)
    → Permet de valider la plomberie et d'obtenir un premier backtest 2022

Phase 2 (Sprint 3-4) : Option B — short_score dédié
    → Facteurs baissiers : trend_score < 0.3, RSI < 40, prix < SMA50/200
    → Remplacer l'inversion du final_score par un vrai score short
    → Calibration sur backtest 2020-2022

Phase 3 (plan_with_ml.md) : Option D — ML ternaire long/flat/short
    → Une fois le backtest bidirectionnel validé
    → Modèle 3 classes entraîné sur target directionnelle
```

### 5.3 Pourquoi pas l'Option A (inversion pure) ?

L'inversion naïve (`short = bottom-N(final_score)`) sans garde-fou shorterait
**tout le temps**, y compris en bull market. Le `MomentumRotationState` apporte
un déclencheur contextuel : on ne short que quand le momentum underperforme.

### 5.4 Pourquoi pas l'Option D (ML) tout de suite ?

L'Option D nécessite les Sprints 0-4 de `plan_with_ml.md` (target ternaire,
modèle 3 classes, calibration, persistance, ranking bilatéral) avant de produire
un seul trade short. L'Option C permet d'avoir un résultat tangible en 2 semaines
et de valider la plomberie avant d'investir dans le ML.

---

## 6. Plan de sprint révisé

L'ordre de priorité reste inchangé :
1. **Sprint 0** — Cadrage + `core/direction.py`
2. **Sprint 1** — Propagation du `side` dans le pipeline risk
3. **Sprint 2** — Moteur de backtest bidirectionnel
4. **Sprint 3** — Exécution live / OMS / protections
5. **Sprint 4** — Reporting et IHM
6. **Sprint 5** — Tests et validation

**Nouveau :** chaque sprint doit inclure une tâche « compatibilité long-only » pour vérifier que les optimisations récentes (force-close, regime-aware scoring, concentration, pullback entry) ne sont pas cassées par l'ajout du `side`.

---

## 7. Checklist pré-démarrage Sprint 0

- [ ] Vérifier que `force_close_on_breaker` et `force_close_pct` sont lus correctement dans le backtest ET le live
- [ ] Vérifier que `DrawdownCircuitBreaker.just_tripped()` est appelé dans le simulator
- [ ] Vérifier que `CircuitBreaker.just_tripped()` est appelé dans l'executor
- [ ] Vérifier que les trackers de concentration sont instanciés dans le live (CLI)
- [ ] Vérifier que le scoring regime-aware est actif dans le backtest ET le live
- [ ] Documenter les valeurs actuelles de TP/SL/time-stop pour référence future short
