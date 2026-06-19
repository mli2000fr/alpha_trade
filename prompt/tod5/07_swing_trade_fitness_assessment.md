# 07 — Swing Trade Fitness Assessment

> **Adéquation métier pure de l'application au swing trading actions US**

---

## 1. Définition du swing trade cible

L'application se définit comme une plateforme de **swing trading actions US** avec :
- Horizon de détention : quelques jours à quelques semaines
- Marchés : NYSE / NASDAQ
- Style : directionnel long (et short en cours d'ajout)
- Exécution : ordres limit/market avec take-profit et trailing stop

---

## 2. Adéquation par dimension

### 2.1 Horizon de détention

| Critère | Statut | Note |
|---|---|---|
| Le pipeline produit des signaux pour un horizon swing (pas intraday) | ✅ | 8/10 |
| Les stops et take-profits sont calibrés pour le swing (TP ~8%, TS ~5%) | ✅ | 8/10 |
| Le backtesting simule `signal J → entrée J+1 open` | ✅ | 9/10 |
| Les contraintes de compte (cash settled T+1) sont modélisées | ✅ | 8/10 |
| Le ML utilise un horizon de prédiction de 5 jours (`forecast_horizon=5`) | ✅ | 8/10 |

**Note horizon** : **8.2/10** — Bien adapté

### 2.2 Qualité de l'univers d'investissement

| Critère | Statut | Note |
|---|---|---|
| Filtre de liquidité (volume × close ≥ 30M$) | ✅ | 8/10 |
| Filtre de prix minimum (close ≥ 10$) | ✅ | 8/10 |
| Filtre de capitalisation (≥ 2 Md$) | ✅ | 8/10 |
| Filtre de spread (≤ 40 bps) | ✅ | 8/10 |
| Blackout earnings pour éviter les événements binaires | ✅ | 9/10 |
| Filtre de volatilité (ATR 1.5%-6%) | ✅ | 8/10 |
| Filtre bêta pour la directionnalité | ✅ | 7/10 |
| Risque d'univers vide sur petits comptes | ⚠️ | 5/10 |

**Note univers** : **7.6/10** — Bon filtrage, mais risque d'univers vide sur micro-comptes

### 2.3 Gestion du risque

| Critère | Statut | Note |
|---|---|---|
| Sizing ATR avec budget de risque par trade (1%) | ✅ | 8/10 |
| Circuit breaker drawdown (15-20%) | ✅ | 8/10 |
| Circuit breaker perte quotidienne (2.5-5%) | ✅ | 8/10 |
| Filtre de corrélation pour diversification | ✅ | 7/10 |
| Contraintes sectorielles | ✅ | 8/10 |
| Kelly conditionnel (≥25k$) | ✅ | 8/10 |
| Ramp-up régimed progressif après drawdown | ✅ | 7/10 |
| Trailing stop dynamique | ✅ | 8/10 |
| Protection break-even | ✅ | 7/10 |

**Note risk** : **7.7/10** — Complet et bien pensé

### 2.4 Exécution

| Critère | Statut | Note |
|---|---|---|
| Ordres limit avec buffer configurable | ✅ | 8/10 |
| Take-profit et trailing stop broker-side | ✅ | 8/10 |
| OCO logique (TP/TS mutuellement exclusifs) | ✅ | 8/10 |
| Idempotence des ordres (SHA-256) | ✅ | 9/10 |
| Réconciliation post-exécution | ✅ | 9/10 |
| Gestion des contraintes de compte (margin/cash) | ✅ | 8/10 |
| Swing-only désactivable : `false` par défaut (correct post-PDT) | ✅ | 8/10 |
| Watcher post-exécution pour promotion trailing stop | ✅ | 7/10 |

**Note exécution** : **8.0/10** — Très bon ; `swing_only=false` est correct depuis la suppression de la PDT (FINRA 2026-06-04)

### 2.5 Backtesting et validation

| Critère | Statut | Note |
|---|---|---|
| Simulation PIT (signal J → entrée J+1) | ✅ | 8/10 |
| Contraintes de compte réalistes (margin/cash/swing) | ✅ | 8/10 |
| Microstructure (slippage, gap) | ⚠️ Optionnel | 5/10 |
| Frais de transaction | ⚠️ Fixes par preset | 5/10 |
| Drawdown breaker cohérent avec le live | ✅ | 8/10 |
| Backfill PIT des scores historiques | ✅ | 8/10 |
| Parité backtest/live | ⚠️ Tests existent mais pas en continu | 6/10 |
| Walk-forward validation | ✅ | 7/10 |

**Note backtesting** : **6.9/10** — Bonne base, microstructure et frais à améliorer

### 2.6 Adéquation au small account (≤25k$)

| Critère | Statut | Note |
|---|---|---|
| Presets dédiés par tranche de capital | ✅ | 8/10 |
| Filtres relâchés pour éviter l'univers vide | ⚠️ Trop relâchés ? | 5/10 |
| Tailles fractionnaires supportées | ✅ | 8/10 |
| Contraintes cash settled modélisées | ✅ | 8/10 |
| Swing-only non activé par défaut | ✅ Correct — post-PDT FINRA, day trading libre | 8/10 |
| Min notionnel cohérent avec Alpaca | ❌ Preset 2k-5k$ à 150$ | 4/10 |

**Note small account** : **6.5/10** — Perfectible, le min_notional et les drawdown breakers restent à corriger

---

## 3. Ce qui manque pour un swing trading de niveau professionnel

### 3.1 Court terme (sprints 1-3)
- [x] ~~Activer `swing_only=true`~~ → Résolu : `swing_only=false` est correct depuis la suppression de la PDT par la FINRA (4 juin 2026)
- [ ] Mettre à jour l'IHM pour que `execution_swing_only=False` soit le défaut
- [ ] Corriger le `min_position_notional` du preset 2k-5k$
- [ ] Activer le module microstructure dans le backtesting par défaut
- [ ] Ajouter un modèle de frais de transaction réaliste (tiered par volume)

### 3.2 Moyen terme (sprints 4-6)
- [ ] Backtester la stratégie sur 10+ ans de données out-of-sample
- [ ] Valider la parité backtest/live sur 6 mois de paper trading
- [ ] Ajouter un régime de marché « risk-off » avec réduction automatique de l'exposition
- [ ] Implémenter un suivi de slippage réel vs backtest

### 3.3 Long terme (sprints 7+)
- [ ] Short selling validé et backtesté
- [ ] ML ternaire (long/flat/short) validé out-of-sample
- [ ] Exécution multi-brokers (IBKR en secours)
- [ ] Rapport de performance conforme aux standards GIPS

---

## 4. Verdict Swing Trade Fitness

**Note globale adéquation swing trade : 7.0/10**

L'application est **bien conçue pour le swing trading** dans son architecture et ses paramètres de base. Les points forts sont :
- La convention de prix split-only avec dividendes séparés
- Le circuit breaker et le sizing ATR
- L'exécution avec take-profit/trailing stop
- La modélisation des contraintes de compte

Les points faibles sont :
- La microstructure et les frais de transaction trop simplistes en backtest
- Les presets petits comptes qui pourraient être mieux calibrés (min_notional, drawdown breaker)
- L'IHM qui utilise encore `swing_only=True` comme défaut (obsolète depuis la suppression de la PDT)

**Note** : `swing_only=false` sur tous les presets est désormais **correct** depuis la suppression de la règle PDT par la FINRA (4 juin 2026). Le day trading intraday est autorisé sans restriction.

**L'application est apte au swing trading paper. Pour le live, les corrections restantes (A-CAP-002, A-CAP-003) doivent être résolues au préalable.**
