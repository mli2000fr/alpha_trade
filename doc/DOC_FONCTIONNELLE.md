# Alpha Trade — Documentation Fonctionnelle

> *Version : 0.3.0 — Dernière mise à jour : avril 2026*

---

## 1. Présentation Générale du Projet

### 1.1 Objectif de l'application

**Alpha Trade** est un système de trading algorithmique **Swing Trade** sur actions US, de bout en bout. Il couvre la totalité de la chaîne : ingestion de données de marché, screening quantitatif, analyse de sentiment (NLP/FinBERT), prédiction par modèle LSTM, gestion du risque, construction de portefeuille, exécution automatisée des ordres via le broker **Alpaca**, et gestion des corporate actions (dividendes, splits). Une **IHM opérateur Streamlit** permet la supervision du pipeline.

### 1.2 Contexte métier

Le système cible le **marché actions US (NYSE/NASDAQ)**, en stratégie **swing trading** (horizon de détention de quelques jours à quelques semaines). Il est conçu pour fonctionner en **paper trading** (compte fictif Alpaca) ou en **live trading** (argent réel), avec un mode simulation (dry-run) sans aucun envoi d'ordre.

### 1.3 Cas d'usage principal

Un opérateur lance quotidiennement le pipeline dans l'ordre suivant :

1. **Ingestion** des données de marché depuis Alpaca (barres OHLCV journalières)
2. **Nettoyage** des données (sanitizer, détection d'anomalies)
3. **Screening** multi-facteurs pour identifier les meilleurs candidats
4. **Alpha Scanner** — scoring avancé Minervini/VCP + neutralisation sectorielle
5. **Analyse de sentiment** des news via FinBERT + fusion avec les scores quantitatifs
6. **Signal Aggregator** — fusion quant + sentiment → `final_score_sentiment`
7. **ML Train** — entraînement des modèles LSTM+Attention par symbole candidat (périodique)
8. **ML Predict** — inférence LSTM → `predicted_proba` par symbole candidat (quotidien)
9. **Gestion du risque** : sizing de position (ATR, Kelly), contraintes de portefeuille, score de conviction (40% quant + 60% ML)
10. **Exécution** automatisée des ordres sur Alpaca avec bracket orders (take-profit + trailing stop)
11. **Corporate actions sync** — récupère dividendes/splits depuis Alpaca uniquement pour les symboles détenus en portefeuille (après exécution du jour)
12. **Corporate actions apply** — application des dividendes/splits sur les positions existantes

L'opérateur supervise l'ensemble via l'**IHM Streamlit** (`ihm/app.py`).

---

## 2. Fonctionnalités Principales

### 2.1 Connexion à Alpaca Trade API

- **Market Data API** (`data.alpaca.markets/v2`) : récupération des barres OHLCV historiques et des news
- **Trading API** (`paper-api.alpaca.markets/v2` ou `api.alpaca.markets/v2`) : soumission d'ordres, consultation de positions, horloge de marché
- Modes **paper** et **live** supportés nativement
- Gestion automatique du rate limiting, des timeouts et des retries avec backoff exponentiel

### 2.2 Gestion des ordres (achat / vente)

| Fonctionnalité | Description |
|---|---|
| **Ordres d'entrée** | Market ou limit (buffer configurable en bps) |
| **Take-profit** | Ordre limit sell à +X% du prix de fill (défaut : +8%) |
| **Trailing stop** | Ordre trailing_stop sell à -X% (défaut : -5%) |
| **Synthetic bracket** | TP + TS soumis séparément après fill, car Alpaca ne supporte pas le trailing stop natif en bracket |
| **OCO logique** | Si le TP ou le TS est exécuté, l'autre est automatiquement annulé |
| **Ordres de rééquilibrage** | Vente d'excédent ou achat complémentaire lors de la réconciliation |
| **Idempotence** | Clé SHA-256 basée sur risk_run_id + symbole + rôle pour éviter les doublons |

### 2.3 Stratégies de trading utilisées

Le système est conçu principalement pour du **swing trading**. Le backtesting permet désormais de simuler explicitement des contraintes réalistes de petit capital Alpaca / compte US :

- **`account_type = margin`** : compte margin simulé ;
- **`pdt_rule = auto`** : maximum **3 day trades sur 5 jours ouvrés** quand le capital simulé est inférieur à **25 000 $** ;
- **`account_type = cash`** : pas de règle PDT, mais uniquement du **cash settled** réutilisable après settlement simplifié **T+1** ;
- **`swing_only = True`** : achat aujourd'hui, revente demain ou plus tard.

Cette API composable permet d'évaluer une stratégie avec **2 000 $** ou un autre petit capital sans surévaluer artificiellement la fréquence de rotation intraday, tout en distinguant proprement :

- le **type de compte**,
- la **règle réglementaire PDT**,
- le **style de trading swing**.

Cette logique n'est plus limitée au backtest : le module `execution_engine` applique aussi ces contraintes au moment de la soumission des ordres et de l'armement des sorties.

#### Scanner multi-facteurs (AlphaScanner)
- **Trend Score** (critères Minervini) : 7 critères techniques (close > MA150, MA150 > MA200, MA200 en hausse, close > MA50, close ≥ 1.25 × low 52w, close ≥ 0.75 × high 52w)
- **VCP Score** (Volatility Contraction Pattern) : ratio volatilité 10j/60j vs seuil
- **Score composite** : `50% × (trend+vcp)/2 + 30% × score_screener + 20% × RSI_relatif`
- **Neutralisation sectorielle** : z-score intra-secteur pour éliminer les biais sectoriels
- **Winsorisation** : protection contre les outliers (percentiles 1%-99%)

#### Screener de liquidité
- Pipeline en 3 passes : liquidité (volume × close sur 30j), force relative vs SPY (6 mois), position dans le range 10 ans
- Exécuté par chunks de 500 symboles en parallèle (ProcessPoolExecutor)

#### Analyse de sentiment (FinBERT)
- Ingestion des news Alpaca, scoring via le modèle pré-entraîné `ProsusAI/finbert`
- Fusion : `75% quant + 15% sentiment ticker + 10% macro sectoriel` (poids configurables)
- Fenêtre glissante de 5 jours, pondérée par le nombre d'articles

#### Prédiction LSTM
- Modèle LSTM + Temporal Attention par symbole
- Classification binaire : hausse/baisse à horizon 5 jours
- Métriques : accuracy, precision, recall, AUC

### 2.4 Gestion du portefeuille

- **Construction du portefeuille cible** par le module `risk_management` à partir des candidats scorés
- **Sizing ATR** : budget de risque par trade (1% du capital) / (ATR(20) × multiplicateur stop)
- **Sizing Kelly** (optionnel) : fraction Kelly pondérée par probabilité prédite et win rate historique
- **Score de conviction** : combinaison score quantitatif (40%) + probabilité prédiction ML (60%)
- Tri des candidats par conviction décroissante

### 2.5 Gestion du risque

| Paramètre | Défaut | Description |
|---|---|---|
| `max_positions` | 20 | Nombre maximum de positions |
| `max_position_weight` | 10% | Poids max d'une position dans le portefeuille |
| `max_sector_weight` | 30% | Poids max d'un secteur |
| `max_gross_exposure` | 100% | Exposition brute maximale |
| `min_position_notional` | 500 $ | Montant minimum par position |
| `max_portfolio_drawdown_pct` | 15% | Seuil circuit breaker drawdown |
| `max_daily_loss_pct` | 5% | Seuil circuit breaker perte journalière |
| `correlation_threshold` | 0.80 | Corrélation max entre deux positions retenues |
| `risk_per_trade_pct` | 1% | Budget de risque par trade |

**Circuit breaker** : coupe automatiquement toute allocation si le drawdown dépasse 15% ou si la perte journalière dépasse 5%.

**Filtre de corrélation** : rejette les candidats trop corrélés (> 0.80 sur 60 jours) pour diversifier.

### 2.6 Alertes / notifications

- **Alerte slippage** : déclenchée si l'écart prix fill vs prix de décision > seuil (défaut 30 bps)
- **Kill switch** : arrêt automatique après N échecs consécutifs (défaut : 3)
- **Circuit breaker actif** : événement loggé, run avorté
- **Logs critiques** : si le scanner produit 0 candidats (LOGGER.critical)
- Tous les événements sont persistés dans la table `execution_events`

### 2.7 Historique / reporting

- **Table `execution_runs`** : chaque run d'exécution est tracé (statut, timestamps, métriques)
- **Table `execution_fills`** : chaque fill reçu du broker avec slippage et implementation shortfall
- **Table `execution_events`** : journal complet de chaque événement (type, message, payload JSON)
- **Table `risk_decisions`** : chaque décision d'acceptation/rejet d'un candidat
- **Table `portfolio_targets`** : portefeuille cible issu du risk management
- **Table `broker_positions_snapshots`** : photo des positions broker après chaque run
- **TCA (Transaction Cost Analysis)** : slippage moyen, max, implementation shortfall agrégé
- **Rapport de backtest** : exporte aussi des diagnostics métier sur les contraintes de compte (`day trades exécutés`, `sorties same-day bloquées`, `entrées bloquées faute de cash settled`)

### 2.8 Logs métier

- Logs structurés avec niveaux INFO/DEBUG/WARNING/ERROR/CRITICAL
- **RotatingFileHandler** : logs fichier rotatifs (`alpha_trade.log`, 5 Mo, 3 backups) en plus de stdout
- Couverture de code ≥ 60% (seuil pytest configuré)
- Rapport HTML de couverture généré dans `htmlcov/`

### 2.9 Gestion des Corporate Actions (dividendes et splits)

Le module `corporate_actions` assure le suivi automatique des opérations sur titres :

| Fonctionnalité | Description |
|---|---|
| **Dividendes cash** | Détection via provider (Alpaca), calcul montant = qty × dividende/action, crédit cash dans un ledger dédié |
| **Splits** | Ajustement automatique : qty × ratio, cost basis / ratio, conservation de la valeur totale |
| **Reverse splits** | Idem avec gestion des fractions (cash-in-lieu) |
| **Idempotence** | Clé SHA-256 déterministe (provider + symbol + type + ex_date + montant/ratio), unicité DB |
| **Audit trail** | Tables `corporate_actions_events`, `corporate_actions_applications`, `portfolio_cash_ledger` |
| **Réconciliation** | Comparaison positions internes post-CA vs positions broker |

**Stratégie données de marché** : les barres OHLCV sont ingérées avec `adjustment="all"` (déjà ajustées par Alpaca). Le module corporate actions ne touche pas aux prix historiques — il gère uniquement la comptabilité portefeuille (qty, cost basis, cash).

**Intégration pipeline** : s'exécute en fin de pipeline, juste avant l'apply, après que les positions du jour sont connues :
```
python -m corporate_actions sync --portfolio-only    # Sync uniquement les symboles détenus en portefeuille
python -m corporate_actions apply                    # Appliquer sur les positions
python -m corporate_actions status                   # Résumé des événements
python -m corporate_actions sync --all-symbols       # Backfill complet (usage exceptionnel)
```

### 2.10 Multi-comptes Alpaca

Le système supporte **plusieurs comptes broker Alpaca en parallèle** (paper et/ou live).

| Fonctionnalité | Description |
|---|---|
| **Registre centralisé** | `AccountRegistry` charge les comptes depuis `config.yaml`, env vars préfixées, ou fallback classique |
| **Isolation par compte** | Chaque exécution, chaque run de risk et chaque apply CA peut cibler un compte spécifique via `--account <ID>` |
| **Traçabilité DB** | Colonne `account_id` sur 6 tables : `execution_runs`, `broker_positions_snapshots`, `risk_decisions`, `portfolio_targets`, `corporate_actions_applications`, `portfolio_cash_ledger` |
| **IHM** | Sélecteur de compte dans la sidebar Streamlit — filtre automatiquement les données affichées |
| **Rétrocompatibilité** | Les données existantes (sans `account_id`) sont considérées comme `default` |
| **Données de marché** | Les barres OHLCV, news et assets sont partagés (non liés à un compte) |

**Configuration** (dans `config.yaml`) :
```yaml
alpaca:
  accounts:
    - id: default
      label: "Paper principal"
      api_key: "${ALPACA_API_KEY}"
      secret_key: "${ALPACA_SECRET_KEY}"
      mode: paper
    - id: live1
      label: "Compte live"
      api_key: "${ALPACA_LIVE1_API_KEY}"
      secret_key: "${ALPACA_LIVE1_SECRET_KEY}"
      mode: live
```

**Usage CLI** :
```
python run_execution.py paper --account default      # exécuter sur le compte paper
python run_execution.py live --account live1          # exécuter sur le compte live
python -m risk_management.run_risk --account live1    # risk pour le compte live
python -m corporate_actions apply --account live1     # appliquer CA sur le compte live
```

---

## 3. Flux de Fonctionnement Global

### 3.1 Étapes du démarrage à l'exécution

```
                     INITIALISATION (une fois)
                     ┌───────────────────────┐
                     │ import_alpaca_assets   │ → stock_metadata
                     │ update_sector          │ → stock_metadata.sector (Finnhub)
                     └───────────────────────┘

                     PIPELINE QUOTIDIEN
     ┌─────────────────────────────────────────────────────────────────────────────┐
     │ 1.  import_alpaca_bar        │ → stock_bars                                 │
     │ 2.  data_sanitizer_daily     │ → stock_bars_daily                           │
     │ 3.  stock_screener           │ → stock_scores                               │
     │ 4.  alpha_scanner            │ → stock_scores (update)                      │
     │ 5.  sentiment_pipeline       │ → ticker/sector feats                        │
     │ 6.  signal_aggregator        │ → final_score_sentiment                      │
     │ 7.  ml_train (périodique)    │ → model_registry, model_training_run         │
     │ 8.  ml_predict (quotidien)   │ → model_predictions                          │
     │ 9.  run_risk                 │ → portfolio_targets                          │
     │ 10. run_execution            │ → ordres Alpaca + broker_positions_snapshots  │
     │ 11. corporate_actions sync   │ → corporate_actions_events (portfolio only)  │
     │ 12. corporate_actions apply  │ → position adjustments                       │
     └─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Cycle d'un trade

1. **Sélection** : le symbole est identifié comme candidat (`is_candidate=1` dans `stock_scores`)
2. **Risk check** : sizing ATR/Kelly, vérification contraintes (poids, secteur, corrélation, circuit breaker)
3. **Portfolio target** : si accepté, le symbole est ajouté à `portfolio_targets` avec nombre de parts et prix d'entrée
4. **Soumission** : l'executor lit les targets et soumet un ordre market/limit d'achat
5. **Fill** : polling du broker jusqu'au fill ou timeout (120s défaut)
6. **Bracket synthétique** : après fill, soumission d'un take-profit (limit sell +8%) et d'un trailing stop (-5%)
7. **OCO** : si l'un des enfants est exécuté, l'autre est annulé
8. **Réconciliation** : comparaison positions broker vs cibles, rééquilibrage automatique optionnel
9. **TCA** : calcul du slippage et de l'implementation shortfall

### 3.3 Détection des signaux

Les signaux sont le résultat de la fusion multi-sources :

- **Quantitatif** (75%) : trend Minervini + VCP + screener (liquidité, RSI relatif, range historique)
- **Sentiment** (15%) : score FinBERT agrégé sur fenêtre glissante 5j
- **Macro sectoriel** (10%) : impact macro par secteur (événements macro-économiques)

Le `final_score_sentiment` résultant détermine le classement final des candidats.

---

## 4. Paramètres Métier Configurables

### 4.1 Seuils de sélection (AlphaScanner)

| Paramètre | Défaut | Description |
|---|---|---|
| `selection_size` | 100 | Nombre max de candidats retenus |
| `min_history_days` | 252 | Historique minimum requis (1 an) |
| `liquidity_threshold` | 20 M$ | Dollar volume moyen 20j minimum |
| `min_close` | 5.00 $ | Prix de clôture minimum |
| `max_anomaly_count` | 20 | Anomalies max acceptées par titre |
| `sector_cap_ratio` | 30% | Plafond par secteur dans la sélection |

### 4.2 Paramètres d'exécution

| Paramètre | Simulate | Paper | Live |
|---|---|---|---|
| `profit_taker_pct` | 8% | 8% | 8% |
| `trailing_stop_pct` | 5% | 5% | 5% |
| `max_slippage_bps` | 30 | 30 | 20 |
| `inter_order_delay_ms` | 0 | 350 | 350 |
| `fill_timeout_seconds` | 120 | 120 | 180 |
| `allow_outside_rth` | Oui | Non | Non |

### 4.3 Paramètres de sentiment

| Paramètre | Défaut | Description |
|---|---|---|
| `sentiment_weight` | 15% | Poids du sentiment ticker |
| `macro_sector_weight` | 10% | Poids du signal macro sectoriel |
| `lookback_days` | 5 | Fenêtre de sentiment |
| `min_news_count` | 2 | Articles minimum pour activer le boost |

### 4.4 Horaires

- Le système vérifie l'horloge NYSE avant exécution (sauf dry-run ou `allow_outside_rth`)
- Calendrier : `pandas_market_calendars` (NYSE) avec couverture complète des jours fériés US

---

## 5. Règles de Gestion Identifiées

1. **Seules les actions US equity** actives, tradables, avec données disponibles sont éligibles (exclusion ETF, crypto, fonds)
2. **Les ETF sont filtrés** par nom de société (patterns : "etf", "ishares", "spdr", "vanguard", etc.)
3. **Un candidat doit avoir ≥ 252 jours d'historique** (1 an)
4. **Les scores quantitatifs sont neutralisés par secteur** (z-score intra-secteur) pour éviter le biais sectoriel
5. **Le circuit breaker suspend le trading** si drawdown ≥ 15% ou perte daily ≥ 5%
6. **La corrélation > 0.80 entre deux positions** entraîne le rejet du candidat le moins bien classé
7. **L'idempotence est garantie** par une clé SHA-256, un même portefeuille cible ne génère pas de doublons
8. **Les ordres 4xx du broker ne sont PAS retentés** (erreurs permanentes) ; seuls les 5xx/timeout/réseau sont retentés
9. **Les positions broker hors cible** (action "investigate") ne sont pas soldées automatiquement pour éviter les erreurs
10. **Le score de conviction combine** score quantitatif (40%) et probabilité prédite par le modèle ML (60%)
11. **En backtest, un compte margin peut être soumis à la règle PDT** si `pdt_rule=auto` et `equity < 25k`, avec blocage du 4e day trade sur 5 séances glissantes
12. **En backtest, l'option `swing_only` peut interdire toute revente le jour même**
13. **En backtest, un cash account n'utilise que le cash settled** et retarde la réutilisation des fonds après vente jusqu'au settlement `T+1`
14. **En exécution, un compte cash ne peut pas soumettre d'achats au-delà du cash settled disponible**
15. **En exécution, `swing_only` et la contrainte PDT peuvent différer l'armement des ordres de sortie le jour même**

---

## 6. Risques / Limitations Fonctionnelles

| Risque | Impact | Probabilité |
|---|---|---|
| **Marché fermé** (week-end, fériés) | Aucun ordre soumis, run avorté | Élevée si exécution non planifiée |
| **Pas de news pour un symbole** | Boost sentiment neutre (0.5), signal quant seul | Moyenne |
| **Modèle LSTM non entraîné** | Pas de prediction_proba, conviction dégradée | Moyenne |
| **Latence Alpaca API** | Fill timeout, ordres children non soumis | Faible |
| **Circuit breaker déclenché** | Aucune allocation possible | Faible (sauf crash marché) |
| **Corrélation élevée entre candidats** | Portefeuille réduit (moins de positions) | Moyenne |
| **Pas de gestion multi-devises** | Uniquement USD / actions US | Limitation de design |
| **Pas de short selling** | Uniquement des positions long | Limitation de design |
| **Pas de streaming temps réel** | Polling périodique (2s) pour les fills | Limitation de design |
| **Pas de notification externe** | Pas d'email/SMS/Slack, logs fichier uniquement | Limitation |

Concernant les contraintes petit capital simulées en backtest :

- la règle `PDT` est modélisée sur la base d'une fenêtre glissante de **5 séances de backtest** ;
- le paramètre `pdt_rule=auto` n'a d'effet que sur un **compte margin** ; sur un **compte cash**, la règle est neutralisée ;
- l'option `swing_only` peut être combinée aussi bien avec un compte `margin` qu'avec un compte `cash` ;
- le mode `cash` repose sur un settlement simplifié **T+1** pour rester testable et lisible ;
- ces modes s'appliquent au moteur de backtest et n'altèrent pas l'exécution live/paper réelle du broker.

Concernant l'exécution réelle/paper :

- le moteur tient compte du snapshot broker (`buying_power`, `cash`, `non_marginable_buying_power`, `daytrade_count`) ;
- un compte `margin` et un compte `cash` peuvent donc produire des résultats d'exécution très différents à capital nominal identique ;
- cet écart est attendu, car la mécanique de capital disponible n'est pas la même.

---

## 7. Suggestions d'Amélioration Métier

1. **Alertes externes** : intégrer Slack/email/SMS pour circuit breaker, slippage, et fin de run
2. ~~**Dashboard temps réel**~~ → ✅ **Implémenté** : IHM Streamlit opérateur (`ihm/app.py`)
3. ~~**Backtesting intégré**~~ → ✅ **Implémenté** : module `backtesting/` basé sur vectorbt — replay signaux conviction + bracket TP/TS, métriques Sharpe/Sortino/CAGR/drawdown, equity curve PNG
4. **Support short selling** : étendre la stratégie aux positions short
5. **Streaming WebSocket** : remplacer le polling des fills par un stream Alpaca pour réduire la latence
6. **Scheduler automatisé** : cron/Airflow/Prefect pour automatiser l'exécution quotidienne du pipeline
7. ~~**Multi-comptes** : supporter plusieurs comptes broker en parallèle~~ → ✅ **Implémenté** : registre multi-comptes (`service/alpaca/accounts.py`), colonne `account_id` sur 6 tables, `--account` CLI sur tous les modules
8. ~~**Gestion des dividendes et splits**~~ → ✅ **Implémenté** : module `corporate_actions`
9. **Optimisation des poids** : calibration automatique IC-weighted des facteurs via backtest glissant
10. **Audit trail enrichi** : export PDF/CSV des rapports TCA et des décisions de risque

