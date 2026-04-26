# Audit — `backtesting`

> Périmètre : `backtesting/` (`cli.py`, `data_loader.py`, `signal_replay.py`,
> `simulator.py`, `trading_constraints.py`, `report.py`,
> `backfill_scores_history.py`, `walk_forward.py`, `screener_diagnostics.py`,
> `sentiment_calibration.py`, `resilience.py`).
> Sources : `doc/backetesting.md` (716 lignes), code listé,
> tests `tests/test_backtesting.py`, `tests/test_backfill_scores_history.py`.

---

## 1. Résumé exécutif

`backtesting/` est le moteur **point-in-time** du projet : reconstruit l'historique
`stock_scores_history`, rejoue les signaux jour par jour, simule l'exécution au prochain
`open` avec contraintes de compte (`margin|cash`, `pdt_rule`, `swing_only`,
settlement `T+1` cash), TP + trailing stop, calcule les métriques (Sharpe, Sortino,
CAGR, drawdown, win rate, profit factor). Inclut un diagnostic screener
(`diagnose-screener`, `recommend-screener`) avec analyse cross-régime de marché et
recommandations adaptatives par objectif (robuste / offensif / bear / exécutable).

État global : **module ambitieux, riche fonctionnellement**, avec des choix corrects
(exécution au `open` du J+1, séparation `account_type` / `pdt_rule` / `swing_only`,
modes ML / sentiment `auto|off|rebuild-missing`). Documentation très dense.

Principaux risques :

1. **Dépendance massive à `vectorbt`** (>=0.26) : librairie maintenue par un seul
   auteur, breaking changes possibles, alternatives (`backtesting.py`, `bt`) moins
   intégrées. Risque maintenabilité long terme.
2. **`stock_scores_history` rebuilt = source de vérité** mais coûteuse à reconstruire :
   le backfill doit rejouer screener + selector + sentiment pour chaque date → temps
   significatif (`screener-workers 2-4` recommandé).
3. **Absence de "training/test split" clair entre data ML utilisée pour predict
   et data utilisée pour backtest** : `--ml-mode rebuild-missing` reconstruit les
   prédictions PIT, mais si un modèle a été entraîné avec une plage qui chevauche le
   backtest, il y a leak. Pas de garde-fou explicite.
4. **TP fixe + trailing stop fixe** : pas de simulation de scenarios de gap (open
   gap > stop). Réalisme partiel sur les gaps.
5. **Costs / slippage / commissions** : pas mentionné explicitement dans la doc → si
   absent, les rendements simulés sont sur-estimés.
6. **`sentiment_calibration.py`** : présent mais non documenté en détail dans la doc
   backtesting. Rôle ?
7. **Phase 5-7 recommandation** : moteur sophistiqué (robuste / offensif / bear /
   exécutable), mais pas de validation empirique que les leaders recommandés battent
   réellement le `STRICT_SWING_CASH_FILTERS` actuel sur out-of-sample.

Priorités immédiates :
- Auditer la présence / absence de costs & slippage dans le simulator.
- Garde-fou explicite training-test split pour `--ml-mode rebuild-missing`.
- Documenter le rôle de `sentiment_calibration.py`.

---

## 2. Constat détaillé

### 2.1 `cli.py` — sous-commandes

| Item | Détail |
|---|---|
| Constat | `run`, `backfill-scores-history`, `diagnose-screener`, `recommend-screener`. UX riche. |
| Force | Découpage clair. Modes `--ml-mode`, `--sentiment-mode`, contraintes de compte exposés. |
| Risque | **Maintenabilité** : nombreux paramètres (`--tp`, `--ts`, `--max-positions`, `--equity`, `--account-type`, `--pdt-rule`, etc.) → CLI surchargée. |
| Recommandation | Profil `--profile strict_swing_cash` qui présète tout. |

### 2.2 `data_loader.py`

| Constat | Charge OHLCV, scores history, sentiment features, model predictions. PIT. |
| Risque | **Cohérence PIT** : à confirmer que le chargement de `model_predictions` exclut bien les prédictions postérieures à la date du signal. |
| Recommandation | Test PIT explicite "predictions doivent être strictement < trade_date". |

### 2.3 `signal_replay.py`

| Constat | Reconstruction conviction = quant + sentiment + ML jour par jour. |
| Risque | **Cohérence** : la formule de fusion doit être strictement identique à celle de `event_sentiment.signal_aggregator` + `risk_management.conviction`. Risque de divergence silencieuse entre live et backtest. |
| Recommandation | Centraliser la formule de fusion dans `core/conviction.py` consommé par les 3 lieux. |

### 2.4 `simulator.py` — moteur backtest

| Item | Détail |
|---|---|
| Constat | Exécution au `open` J+1, TP + trailing stop, contraintes via `trading_constraints.py`. |
| Risque | **Réalisme** : pas de mention costs/slippage dans la doc. |
| Risque 2 | **Réalisme** : sur gap > stop, le fill est-il à `open` ou au `stop_price` ? Convention non documentée. |
| Risque 3 | **Cohérence avec live** : trailing stop simulé peut différer du trailing broker-side (Alpaca trailing stop a sa propre logique de réévaluation). |
| Recommandation | (a) Ajouter `--commission-bps`, `--slippage-bps`, défauts >= 5 bps ; (b) documenter "fill on gap" ; (c) test "même setup en simulate vs paper" pour mesurer la dérive. |

### 2.5 `trading_constraints.py` — contraintes de compte

| Constat | `account_type=margin|cash`, `pdt_rule=auto|off`, `swing_only`. Cash settlement T+1. PDT simulé `< 25 000 $`. |
| Force | Belle séparation conceptuelle, expose des artefacts diagnostics
(`blocked_pdt_day_trades`, `blocked_same_day_exits`, `blocked_cash_entries`). |
| Recommandation | Étendre à `T+2` pour les vrais cash accounts US (T+1 depuis SEC May 2024 — OK pour 2026) ; documenter explicitement. |

### 2.6 `report.py`

| Constat | Sharpe, Sortino, CAGR, drawdown, win rate, profit factor. Artefacts CSV + PNG. |
| Recommandation | Ajouter Calmar ratio, Ulcer index, % positive months. |

### 2.7 `backfill_scores_history.py`

| Constat | Pour chaque séance manquante : screener + selector + sentiment + insert snapshot. |
| Risque | **Performance** : coût élevé (rejouer 2 modules par jour × N jours). |
| Risque 2 | **Cohérence** : la doc précise "n'écrit pas dans `stock_scores` courant" ✔️ ; idempotent (skip dates déjà historisées). |
| Recommandation | Parallélisation par jour (déjà partiellement via `--screener-workers`) ; profiling documenté pour 1 an = X heures cible. |

### 2.8 `screener_diagnostics.py` + recommandations phase 5-7

| Constat | Génère `summary_metrics.csv`, `daily_metrics.csv`, `scenarios.csv`,
`market_regimes.csv`, `scenario_recommendations*.csv`. 4 profils objectifs
(robuste/offensif/bear/exécutable). |
| Force | Module sophistiqué, à valeur ajoutée pour la décision de tuning. |
| Risque | **Modèle / overfit** : 4 profils avec scoring composite → risque que le scénario "champion" soit surfit sur l'historique de diagnostic. Pas de validation forward documentée. |
| Recommandation | Validation hold-out : recommander un scénario sur 2024, valider sur 2025, mesurer l'IC. |

### 2.9 `sentiment_calibration.py`

| Constat | Présent mais non documenté en détail. |
| Recommandation | Documenter dans `doc/backetesting.md`. |

### 2.10 `walk_forward.py`

| Constat | Walk-forward (probablement pour backtest pur, ou interaction avec
`modelFactory.walk_forward`). |
| Recommandation | Clarifier la responsabilité (backtesting WF vs ML WF — sont-ils unifiés ?). |

### 2.11 `resilience.py`

| Constat | Probablement gestion des erreurs / retry pendant un long backtest. |
| Recommandation | Documenter. |

---

## 3. Risques prioritaires

### Critique
- **Pas de costs/slippage explicites** = backtest optimiste de plusieurs % par an.

### Élevé
- Pas de garde-fou anti-leak ML pendant `--ml-mode rebuild-missing`.
- Formule de fusion conviction dupliquée (backtest vs live) → risque de divergence.
- Diagnostic screener phase 5-7 sans validation hold-out forward.

### Modéré
- Dépendance vectorbt mono-mainteneur.
- TP/TS sur gap : convention non documentée.
- `sentiment_calibration.py`, `resilience.py`, `walk_forward.py` non documentés.

### Faible
- CLI surchargée → profils consolidés à introduire.
- `report.py` peut s'enrichir (Calmar, Ulcer).

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Le backtest hérite de **toutes** les limitations IEX :
- `volume`, `liquidity`, `spread_bps` IEX → filtres et sizing biaisés ;
- `historical_range_score` impacté si `is_filled` non filtré ;
- `daily_return` OK.

**Recommandation** : ajouter un **mode "consolidated proxy"** dans `data_loader.py` :
si une seconde source (Stooq) est disponible pour le volume / OHLC, l'utiliser comme
proxy "consolidated" pour le backtest. Sinon fallback IEX.

Cela permettrait d'avoir **deux backtests** :
- "live-equivalent" : 100 % IEX → ce qu'on aura en production live ;
- "ideal" : Stooq consolidé → ce qu'on aurait avec un compte payant.

L'écart entre les deux mesure le coût opérationnel de l'offre gratuite.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Conserver `split_adjusted` :
- les TP/TS sont en pourcentage du prix → invariants au split ✔️ ;
- les dividendes sont cumulés via `portfolio_cash_ledger` (déjà géré) ✔️ ;
- la performance totale = position MTM + cash ledger ✔️.

**Recommandation backtest** : exposer **deux KPI** dans `report.py` :
- `total_return_price_only` (sans dividendes)
- `total_return_with_dividends` (avec ledger CA)

C'est cohérent avec le choix global et propre.

---

## 6. Quick wins

1. **Ajouter `--commission-bps` et `--slippage-bps`** (défauts 0 + 5 bps).
2. **Documenter "fill on gap"**.
3. **Test PIT predictions** "strictement < trade_date".
4. **Documenter `sentiment_calibration.py`, `resilience.py`, `walk_forward.py`**.
5. **Calmar ratio + Ulcer index** dans `report.py`.
6. **Ajouter `total_return_with_dividends`** au rapport.
7. **Profil `--profile strict_swing_cash`** pour CLI consolidé.
8. **Validation hold-out** sur le diagnostic screener (un fold validation auto).

## 7. Recommandations structurelles

1. **Centraliser la formule de fusion conviction** dans `core/conviction.py`
   consommé par `event_sentiment`, `risk_management`, `backtesting`.
2. **`MarketDataPort`** (cf. audit service) : permettrait de brancher Stooq comme
   proxy consolidé.
3. **Refactor `simulator.py`** en `Strategy` pattern composables (entry / exit / TP /
   trailing).
4. **Migrer hors vectorbt** progressivement vers une implémentation maison plus simple
   pour réduire la dette dépendance (vectorbt n'est plus maintenu activement, à
   valider).
5. **Test runtime "live-equivalent vs ideal"** : utiliser deux sources data et reporter
   l'écart de performance attribuable à la couverture IEX.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5, 6, 7.
- Documentation des 3 fichiers non documentés.

### Moyen terme
- Centralisation formule fusion.
- Validation hold-out diagnostic.
- Profile CLI.

### Long terme
- `MarketDataPort` Stooq.
- Évaluation alternative à vectorbt.
- Refactor simulator en Strategy.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bons (`tests/test_backtesting.py`, `tests/test_backfill_scores_history.py`). **Manque** :
  - test "PIT prediction non-leak".
  - test "gap > stop" → fill convention.
  - test "costs/slippage présents" (snapshot à chaque release).
  - test "sentiment_calibration".

### Monitoring
- Artefacts CSV/PNG riches. **Manque** :
  - dashboard IHM "comparaison N runs récents".
  - comparaison automatique simulate vs live.

### Documentation
- Excellente (716 lignes). **Manque** :
  - section "costs et slippage" explicites.
  - `sentiment_calibration.py`, `resilience.py`, `walk_forward.py`.
  - section "validation hold-out du diagnostic".

