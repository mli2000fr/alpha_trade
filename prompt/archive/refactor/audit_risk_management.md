# Audit — `risk_management`

> Périmètre : `risk_management/` (`portfolio_builder.py`, `position_sizer.py`, `kelly.py`,
> `constraints.py`, `risk_checker.py`, `circuit_breaker.py`, `conviction.py`,
> `correlation_filter.py`, `db_io.py`, `audit.py`, `config.py`, `cli.py`, `run_risk.py`).
> Sources : `doc/risk_management.md`, code listé, tests `tests/test_risk_management_*`,
> `tests/test_position_sizer.py`, `tests/test_constraints.py`,
> `tests/test_circuit_breaker.py`, `tests/test_risk_checker.py`,
> `tests/test_portfolio_builder.py`.

---

## 1. Résumé exécutif

`risk_management/` construit le **portefeuille cible** à partir des candidats scorés :
sizing ATR / Kelly, contraintes (max positions, max poids, secteur, gross exposure,
notionnel min, drawdown circuit breaker, perte daily, corrélation > 0.80), conviction
score (40 % quant + 60 % ML), et persistance dans `risk_decisions` et `portfolio_targets`.

État global : **module bien structuré, séparation des responsabilités exemplaire**
(une classe par concern). Bonne couverture de tests unitaires sur chaque composant.
Intégration multi-comptes propre.

Principaux risques :

1. **Source d'equity hétérogène** : le CLI tente d'ajouter `corporate_actions` dividend
   ledger au capital, mais c'est best-effort. Si la fonction échoue silencieusement,
   l'equity est sous-estimée → sizing sous-dimensionné.
2. **`correlation_threshold = 0.80` fixe** : pas adaptatif. Sur un univers très corrélé
   (bull market tech), peut rejeter trop de candidats ; sur un univers décorrélé, trop
   peu.
3. **Conviction `40/60`** : poids quant/ML arbitraire, jamais validé en backtest formel
   documenté. Si le ML est faible (peu de prédictions disponibles, voir `modelFactory`),
   `predicted_proba` peut tirer le score vers une moyenne neutre 0.5 → biais mécanique.
4. **Circuit breaker basé sur snapshot PnL** : `PortfolioBuilder` a accès à
   `pnl: PnLSnapshot` mais la doc ne précise pas comment `portfolio_high_watermark` est
   alimenté. Risque que le high watermark soit "réinitialisé" silencieusement.
5. **Sizing ATR uniquement** par défaut (`enable_kelly_sizing` opt-in) : Kelly demande
   `historical_win_rate` non triviaux à calculer, source potentielle de skip.
6. **Pas de gestion explicite de la "phase de transition"** entre une position
   existante et une nouvelle cible (rebalancing) — délégué au `execution_engine`.
7. **Filtre de corrélation post-sizing** : si après filtre il reste 5 positions au lieu
   de 20, le portefeuille est sous-diversifié sans alerte.

Priorités immédiates :
- Logger explicitement la source et le détail de `account_equity` (cash + positions
  + dividends ledger).
- Documenter et exposer la calibration des poids `40/60`.
- Ajouter une métrique de "surconcentration" si le filtre de corrélation rejette
  beaucoup.

---

## 2. Constat détaillé

### 2.1 `portfolio_builder.py` — orchestrateur

| Item | Détail |
|---|---|
| Constat | Pipeline : enrich (proba, win rate) → conviction → tri → corrélation → sizing → contraintes → entries (`ACCEPTED`/`REDUCED`/`REJECTED`). |
| Force | Statuts explicites `REDUCED` permettent d'expliquer le sizing ajusté. |
| Risque | **Modèle / cohérence** : ordre des étapes critique — un changement (ex : appliquer corrélation après sizing) modifierait le résultat. Pas de test "ordre invariance" à confirmer. |
| Recommandation | Test paramétrique qui fixe l'ordre attendu et le valide. |

### 2.2 `position_sizer.py` — ATR

| Constat | `shares = (risk_budget / (atr_20 * stop_multiplier))`. `risk_per_trade_pct = 1 %`. |
| Force | Convention swing classique. Lisible. |
| Risque | **Cohérence** : `atr_20` doit être strictement positif. Si pour une raison data un ATR vaut 0 ou NaN, division par zéro → catch ? |
| Recommandation | Logger explicitement et `REJECT` plutôt que crash silencieux. |

### 2.3 `kelly.py` — Kelly fractionnel

| Constat | Sizing optionnel (`--enable-kelly-sizing`). Demande `historical_win_rate` et `predicted_proba`. |
| Risque | **Modèle** : Kelly sensible aux estimations. Si `historical_win_rate` est calculé sur peu de trades, la fraction peut être trompeuse. |
| Recommandation | (a) Imposer un `min_historical_trades = 30` avant d'activer Kelly pour un symbole ; (b) clamper la fraction Kelly à `[0, max_position_weight]` (sécurité). |

### 2.4 `constraints.py` — contraintes portefeuille

| Constat | `max_positions=20`, `max_position_weight=10%`, `max_sector_weight=30%`, `max_gross_exposure=100%`, `min_position_notional=500$`. |
| Force | Limites usuelles, raisonnables. |
| Risque | **Cohérence** : `max_gross_exposure=100%` = pas de levier. Cohérent avec `cash account` et `swing trading`. |
| Risque 2 | Absence de `min_position_count` → si toutes les contraintes éliminent N candidats, on peut finir avec 1 seule position sans alerte. |
| Recommandation | Ajouter une métrique "diversification atteinte" + warning si < 5 positions. |

### 2.5 `risk_checker.py`

| Constat | Vérifications portefeuille global. |
| Risque | Détail non disponible sans lire le code. À compléter en lecture ciblée. |

### 2.6 `circuit_breaker.py`

| Item | Détail |
|---|---|
| Constat | Coupe si drawdown ≥ 15 % ou perte daily ≥ 5 %. Déclenché AVANT toute construction de portefeuille. Bien testé. |
| Force | Logique simple et lisible. |
| Risque | **Cohérence** : `portfolio_high_watermark` source ? Si reset chaque run, le drawdown est mal calculé. |
| Risque 2 | Pas de "période de réactivation" : une fois le circuit cassé, comment se débloque-t-il ? |
| Recommandation | (a) Documenter explicitement la persistance du `high_watermark` (table ou snapshot broker) ; (b) prévoir un mécanisme `--force-reactivate` opérateur. |

### 2.7 `conviction.py`

| Constat | `conviction_score = 0.4 * quant + 0.6 * ml_proba` (par défaut). |
| Risque | **Modèle** : pondération arbitraire, jamais documentée comme validée empiriquement. Si `ml_proba` absente pour un symbole (modelFactory n'a pas pu prédire), fallback à 0.5 → tire mécaniquement la conviction vers le bas. |
| Recommandation | (a) Documenter le fallback ; (b) exposer `--conviction-fallback-strategy keep|drop|neutral` ; (c) calibration empirique annuelle. |

### 2.8 `correlation_filter.py`

| Constat | Rejette les candidats trop corrélés (> 0.80 sur 60 jours, min overlap 40 jours). |
| Risque | **Cohérence** : seuil fixe. Sur secteur tech bull, beaucoup de paires > 0.80 → rejet potentiellement majeur de l'univers candidat. |
| Recommandation | Adaptatif : `correlation_threshold = max(0.70, p90_correlation_of_universe)` calculé sur la matrice. |

### 2.9 `audit.py` + `db_io.py`

| Constat | Persistance dans `risk_decisions` et `portfolio_targets`. Multi-comptes via `account_id`. |
| Force | Bonne traçabilité. |
| Risque | Pas de mention d'un `risk_run_id` immuable persisté sur les deux tables (à vérifier dans le DDL). |
| Recommandation | Garantir `risk_run_id` UNIQUE sur les deux tables pour permettre les jointures execution. |

---

## 3. Risques prioritaires

### Critique
- Aucun direct.

### Élevé
- Equity = cash + positions + ledger CA, mais composé "best-effort" → erreur silencieuse
  possible.
- Conviction `40/60` non calibrée empiriquement.
- `circuit_breaker.high_watermark` : source non clarifiée.
- ATR=0 ou NaN : comportement non défini explicite.

### Modéré
- Filtre de corrélation à seuil fixe (non adaptatif).
- Pas de `min_position_count` → portefeuille sur-concentré silencieux.
- Kelly sans `min_historical_trades`.

### Faible
- Pas de pessimisme sur les `ml_proba` absentes (fallback 0.5 mécanique).

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Impact indirect via `stock_bars_daily` :
- `atr_20` calculé sur OHLC IEX → légèrement pessimiste pour les small caps (high
  artificiellement plus bas, low plus haut, ATR sous-estimé) → **sizing trop large**
  pour les small caps illiquides.
- `correlation_filter` calculé sur `daily_return` IEX → returns OK (close-to-close pas
  trop affecté), filtre robuste.

**Recommandation** :
- documenter dans `doc/risk_management.md` que `atr_20` est calculé sur IEX et peut
  sous-estimer la vol réelle pour les small caps ;
- éventuellement appliquer un floor `atr_pct_min = 1.0 %` (déjà en partie via le filtre
  selector `atr_pct_20 >= 1.5%`).

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct (ATR sur close split-adjusted, OK).

Note : si on passe à `all` un jour, il faudra re-vérifier la formule de sizing
(rendement total inclus dans les prix peut amplifier l'ATR).

---

## 6. Quick wins

1. **Logger `account_equity_breakdown`** (cash, positions, dividends) dans le run_summary.
2. **Garde-fou `atr_20 > 0`** : `REJECT` explicite avec message.
3. **Documenter persistence `high_watermark`**.
4. **Versionner les poids `40/60`** dans `risk_run.config_snapshot`.
5. **`min_position_count` warning** si < 5 positions retenues.
6. **`min_historical_trades` pour Kelly** (défaut 30).
7. **Test "ordre invariance" du `PortfolioBuilder.build()`**.
8. **Documenter le fallback `ml_proba` absente**.

## 7. Recommandations structurelles

1. **Calibration empirique des poids `40/60`** via backtest 6 mois glissant, écriture
   `conviction_weights_history`.
2. **Filtre de corrélation adaptatif** (threshold = max(0.70, p90)).
3. **Refactor `portfolio_builder.build()` en pipeline composable** : chaque étape
   testable indépendamment.
4. **Service `EquityResolver`** : centralise le calcul d'equity (cash + positions live
   + dividends ledger) avec gestion d'erreur explicite et fallback documenté.
5. **`high_watermark` persistant** dans une table dédiée
   (`risk_high_watermark(account_id, value, observed_at)`).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5, 6, 8.
- Documentation : ajout d'une section "calibration des poids".

### Moyen terme
- `EquityResolver` extrait.
- Filtre de corrélation adaptatif.
- `high_watermark` persistant en table dédiée.

### Long terme
- Calibration empirique automatisée.
- Stress tests : "que se passe-t-il si tous les symboles sont rejetés ?"

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Très bonne couverture composant. **Manque** :
  - test invariance d'ordre `build()`.
  - test ATR=0 → REJECT explicite.
  - test conviction fallback ml_proba absente.
  - test fil rouge "petit univers candidat" (1 seul candidat → comportement attendu).

### Monitoring
- `risk_decisions` riche. **Manque** :
  - table `risk_run_summary(run_id, candidates_n, accepted_n, rejected_n,
    rejection_reasons)`.
  - distribution sectorielle visualisée IHM.

### Documentation
- Bonne (`doc/risk_management.md`). **Manque** :
  - calibration des poids justifiée.
  - persistence `high_watermark`.
  - troubleshooting "je n'ai aucune position retenue".

