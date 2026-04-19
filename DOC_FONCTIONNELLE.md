# Alpha Trade — Documentation Fonctionnelle

> *Version : 0.2.0 — Dernière mise à jour : avril 2026*

---

## 1. Présentation Générale du Projet

### 1.1 Objectif de l'application

**Alpha Trade** est un système de trading algorithmique **Swing Trade** sur actions US, de bout en bout. Il couvre la totalité de la chaîne : ingestion de données de marché, screening quantitatif, analyse de sentiment (NLP/FinBERT), prédiction par modèle LSTM, gestion du risque, construction de portefeuille, exécution automatisée des ordres via le broker **Alpaca**, et gestion des corporate actions (dividendes, splits). Une **IHM opérateur Streamlit** permet la supervision du pipeline.

### 1.2 Contexte métier

Le système cible le **marché actions US (NYSE/NASDAQ)**, en stratégie **swing trading** (horizon de détention de quelques jours à quelques semaines). Il est conçu pour fonctionner en **paper trading** (compte fictif Alpaca) ou en **live trading** (argent réel), avec un mode simulation (dry-run) sans aucun envoi d'ordre.

### 1.3 Cas d'usage principal

Un opérateur lance quotidiennement le pipeline dans l'ordre suivant :

1. **Ingestion** des données de marché depuis Alpaca (barres OHLCV journalières)
1a. **Corporate actions sync** — ingestion des dividendes/splits depuis Alpaca (référentiel)
2. **Nettoyage** des données (sanitizer, détection d'anomalies)
3. **Screening** multi-facteurs pour identifier les meilleurs candidats
4. **Alpha Scanner** — scoring avancé Minervini/VCP + neutralisation sectorielle
5. **Analyse de sentiment** des news via FinBERT + fusion avec les scores quantitatifs
6. **Signal Aggregator** — fusion quant + sentiment → `final_score_sentiment`
7. **Gestion du risque** : sizing de position (ATR, Kelly), contraintes de portefeuille
8. **Exécution** automatisée des ordres sur Alpaca avec bracket orders (take-profit + trailing stop)
8a. **Corporate actions apply** — application des dividendes/splits sur les positions existantes

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

**Intégration pipeline** : s'exécute entre l'étape 1 (import_alpaca_bar) et l'étape 2 (data_sanitizer_daily) :
```
python -m corporate_actions sync    # Ingérer les événements depuis Alpaca
python -m corporate_actions apply   # Appliquer sur les positions
python -m corporate_actions status  # Résumé des événements
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
     ┌───────────────────────────────────────────────────────┐
     │ 1.  import_alpaca_bar        │ → stock_bars           │
     │ 1a. corporate_actions sync   │ → corporate_actions_events│
     │ 2.  data_sanitizer_daily     │ → stock_bars_daily     │
     │ 3.  stock_screener           │ → stock_scores         │
     │ 4.  alpha_scanner            │ → stock_scores (update)│
     │ 5.  sentiment_pipeline       │ → ticker/sector feats  │
     │ 6.  signal_aggregator        │ → final_score_sentiment│
     │ 7.  run_risk                 │ → portfolio_targets    │
     │ 8.  run_execution            │ → ordres Alpaca        │
     │ 8a. corporate_actions apply  │ → position adjustments │
     └───────────────────────────────────────────────────────┘
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

---

## 7. Suggestions d'Amélioration Métier

1. **Alertes externes** : intégrer Slack/email/SMS pour circuit breaker, slippage, et fin de run
2. ~~**Dashboard temps réel**~~ → ✅ **Implémenté** : IHM Streamlit opérateur (`ihm/app.py`)
3. **Backtesting intégré** : cadre de backtest (vectorbt/zipline) pour valider les paramètres avant production
4. **Support short selling** : étendre la stratégie aux positions short
5. **Streaming WebSocket** : remplacer le polling des fills par un stream Alpaca pour réduire la latence
6. **Scheduler automatisé** : cron/Airflow/Prefect pour automatiser l'exécution quotidienne du pipeline
7. **Multi-comptes** : supporter plusieurs comptes broker en parallèle
8. ~~**Gestion des dividendes et splits**~~ → ✅ **Implémenté** : module `corporate_actions`
9. **Optimisation des poids** : calibration automatique IC-weighted des facteurs via backtest glissant
10. **Audit trail enrichi** : export PDF/CSV des rapports TCA et des décisions de risque

