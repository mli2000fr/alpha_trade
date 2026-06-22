# 02 — Module Scorecards

> **Détail module par module — note, points forts, faiblesses, risques, chemin vers 10/10**

---

## 1. Documentation — 5.0/10

**Résumé** : La documentation est abondante (~60 fichiers dans `doc/`) mais partiellement désynchronisée du code. Les documents principaux (`DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`) sont bien structurés mais accumulent des couches de sprints sans révision d'ensemble. Les docs de module (risk, execution, backtesting, corporate_actions) sont généralement de bonne qualité.

**Points forts** :
- Documentation fonctionnelle et technique détaillées
- Docs de module clairs et actionnables (commandes, prérequis, flux)
- Matrice de data lineage (`data_lineage_matrix.md`) excellente
- Conventions centralisées dans `CONVENTIONS.md`
- CHANGELOG pour tracer les évolutions documentaires

**Faiblesses** :
- `DOC_FONCTIONNELLE.md` mentionne les sprints S1-S7 mais pas les plans v2 en cours
- Certaines valeurs numériques dans la doc fonctionnelle ne sont plus à jour (ex: `max_spread_bps` documenté à 25 bps vs 40 bps dans le code)
- Références croisées partiellement obsolètes entre documents
- Pas de documentation sur le plan v2 short selling
- Le statut « en cours d'implémentation » des plans v2 n'est pas clairement indiqué

**Risques principaux** :
- Un nouvel opérateur peut être induit en erreur par des valeurs obsolètes
- La maintenance devient coûteuse si la doc n'est pas mise à jour en continu

**Pour atteindre 10/10** : Revue complète post-sprint, synchronisation doc↔code automatisée en CI, versioning documentaire aligné sur les releases.

---

## 2. Configuration — 6.5/10

**Résumé** : `config.yaml` est bien structuré et commenté. Les secrets sont gérés proprement via placeholders `${VAR}`. Le système de presets de capital (`config/capital_presets.yaml`) est une bonne idée mais souffre de quelques incohérences entre tranches.

**Points forts** :
- Secrets par variables d'environnement, placeholders `${VAR}`
- Multi-comptes Alpaca bien configuré
- Bloc `market_regimes` riche et paramétrable
- Bloc `leverage` avec garde-fous explicites
- Presets de capital avec justifications documentées
- `execution_swing_only=false` sur tous les presets est **correct** depuis la suppression de la règle PDT par la FINRA (4 juin 2026) : achat/vente intraday autorisé sans restriction

**Faiblesses** :
- Paramètres de drawdown breaker identiques pour toutes les tranches (`degraded_entry_allocation_pct=0.025`, `ramp_up_max_pct=0.8`)
- `execution_account_type` : `cash` pour ≤25k$, `margin` pour ≥25k$ — la transition cash→margin à 25k$ était historiquement liée à la PDT, ce seuil pourrait être révisé
- `risk_min_position_notional` à 150$ pour le preset 2k-5k$ — en dessous du min_notional Alpaca (155$ configuré dans `market_regimes.enforce_min_notional`)
- L'IHM utilise encore `execution_swing_only=True` comme défaut, en contradiction avec les presets (post-PDT, `false` est le bon choix)

**Risques principaux** :
- Mauvais paramétrage d'exécution si l'opérateur se fie aux défauts IHM (`swing_only=True`) sans vérifier les presets
- Micro-comptes potentiellement inopérants avec les contraintes combinées

**Pour atteindre 10/10** : Harmonisation complète des presets par tranche, validation automatisée de la cohérence inter-presets, golden config testée en backtest.

---

## 3. dataIntegrityEngine — 7.5/10

**Résumé** : Module d'ingestion et de nettoyage des données bien conçu. Le switch EODHD/Alpaca est proprement implémenté. La sanitation daily est robuste. Le backfill EODHD et le cross-check Stooq sont des plus appréciables.

**Points forts** :
- Provider switch explicite et propre : no-op avec `skipped_reason=wrong_provider` quand le mauvais provider est appelé (`import_alpaca_bar.py:613`)
- `bar_importer_common.py` factorise bien les helpers communs
- Sanitizer daily avec audit trail (`cleaning_audit_runs`)
- Cross-check Stooq best-effort
- `sync_latest_quotes` avec proxy `quote_iex_vs_consolidated_bps`
- Refactor S7-bis : `import_eodhd_bar.py` devenu shim mince, logique dans `dataIntegrityEngine/eodhd/`

**Faiblesses** :
- La colonne `data_source` dans `stock_bars_daily` est utilisée pour le lineage mais la PK `(symbol, date)` empêche la cohabitation multi-source — ce qui est documenté mais pourrait surprendre
- Pas de test automatisé de bout en bout EODHD → sanitizer → stock_bars_daily avec données réelles
- Le cache EODHD (`artifacts/eodhd_cache`) n'a pas de politique de nettoyage automatique documentée

**Risques principaux** :
- Dépendance à un seul provider daily (EODHD) : si EODHD est down, pas de fallback automatique (assumé)

**Pour atteindre 10/10** : E2E test avec données réelles, politique de rétention du cache, monitoring proactif de la fraîcheur des données.

---

## 4. Database — 6.5/10

**Résumé** : Schéma SQL riche et bien organisé en sous-dossiers (`stock/`, `news/`, `ml/`, `risk/`, `execution/`, `corporate_actions/`). La gestion des migrations Alembic est présente. La traçabilité multi-comptes est bien propagée.

**Points forts** :
- Organisation claire des DDL par domaine
- Contraintes SQL CHECK sur `data_adjustment` (cf. `doc/database.md` §9)
- Colonne `account_id` propagée sur les tables critiques
- Colonne `data_source` pour le lineage
- `run_business_summaries` pour les résumés structurés

**Faiblesses** :
- Certaines tables ont des colonnes JSON sans schéma validé côté DB (ex: `cleaning_audit_runs.cross_check_anomalies`)
- Pas de migration Alembic documentée pour les plans v2 (short selling, ML ternaire)
- `stock_bars` vs `stock_bars_daily` : deux tables avec des conventions partiellement redondantes
- Pas de foreign key constraints documentées entre certaines tables critiques

**Risques principaux** :
- Migration v2 non testée pourrait casser l'existant
- JSON non validé peut causer des erreurs silencieuses en aval

**Pour atteindre 10/10** : FK constraints explicites, validation JSON côté DB (MySQL 8.0+ CHECK sur JSON), migrations testées en CI.

---

## 5. Service / Providers — 7.0/10

**Résumé** : Clients HTTP bien implémentés avec retry, backoff, circuit breaker. Le `AccountRegistry` multi-comptes est une excellente abstraction. EODHD est bien intégré.

**Points forts** :
- Retry avec backoff exponentiel sur les clients Alpaca et EODHD
- Circuit breaker EODHD (`consecutive_failures: 5`, `cooldown_minutes: 30`)
- `AccountRegistry` : singleton, résolution propre, fallback classique
- Quota tracker EODHD (`soft_quota_warn: 80000`)
- Cache disque EODHD avec TTL

**Faiblesses** :
- Pas de mock cohérent pour les tests qui pourrait éviter les appels réels
- Le client Finnhub n'a pas de circuit breaker documenté
- Pas de healthcheck proactif des providers avant utilisation dans le pipeline

**Risques principaux** :
- Quota EODHD épuisé silencieusement si le soft warn n'est pas surveillé

**Pour atteindre 10/10** : Healthcheck proactif, mock cohérent pour tous les providers, alerting sur quota.

---

## 6. Screener — 7.0/10

**Résumé** : Pipeline de screening en 3 passes (liquidité, force relative, range historique) avec exécution parallèle. Les seuils sont paramétrables et les diagnostics sont bien outillés.

**Points forts** :
- Parallélisation par chunks (ProcessPoolExecutor)
- Seuils paramétrables et cohérents avec les presets capital
- Diagnostics screener intégrés au backtesting
- `ScreenerConfig.strict_swing_cash()` pour la cohérence

**Faiblesses** :
- Le screener dépend de `stock_bars_daily` qui peut avoir des trous
- Pas de test de performance sur univers complet (5000+ symboles)
- Les diagnostics pourraient être plus actionnables (seuils suggérés automatiquement)

**Risques principaux** :
- Univers vide si les seuils sont trop stricts combinés à des données manquantes

**Pour atteindre 10/10** : Tests de performance, recommandations automatiques de seuils, détection proactive d'univers vide.

---

## 7. Selector (AlphaScanner) — 7.5/10

**Résumé** : Scanner multi-facteurs mature avec scoring Minervini/VCP, neutralisation sectorielle, filtres PIT quotes/earnings. Le profil strict partagé (`core/filter_profiles.py`) est une excellente pratique.

**Points forts** :
- Profil strict canonique (`STRICT_SWING_CASH_FILTERS`) source de vérité unique
- Neutralisation sectorielle cross-sectorielle
- Filtres PIT : quotes, earnings, market cap avec TTL
- Winsorisation pour la robustesse aux outliers
- Alias rétrocompatible (`selector/strict_filter_profiles.py` → `core/filter_profiles.py`)
- Extensions IEX (`max_spread_bps_iex`, `min_quote_size`)

**Faiblesses** :
- Le `volatility_ratio` n'est pas filtrable en SQL (dépend de `compute_factors()`)
- Complexité du scoring composite : 50%×(trend+vcp)/2 + 30%×score_screener + 20%×RSI_relatif — les poids sont-ils validés empiriquement ?
- Le `beta_126` est calculé localement vs SPY — mais la qualité dépend de la disponibilité des données SPY

**Risques principaux** :
- Poids de scoring non calibrés formellement → risque de sélection sous-optimale
- Dépendance à SPY pour le calcul du beta

**Pour atteindre 10/10** : Calibration formelle des poids de scoring, suppression de la dépendance SPY pour le beta (utiliser un benchmark configurable), test de stabilité du ranking.

---

## 8. Event Sentiment — 7.0/10

**Résumé** : Pipeline NLP complet avec FinBERT, scoring article/ticker, features ticker/secteur. La migration vers le scoring contextuel (Niveau 4) est bien gérée avec rétrocompatibilité.

**Points forts** :
- Rétrocompatibilité du scoring contextuel via `COALESCE(news_ticker_sentiment.*, news_sentiment.*)`
- Mapping article→ticker en 3 modes (provider_default, strict, scored)
- Agrégation ticker pondérée par `relevance_score`
- Fusion 75% quant + 15% sentiment ticker + 10% macro sectoriel
- Provider news switch (Alpaca, Finnhub, EODHD)

**Faiblesses** :
- Le scoring contextuel (Niveau 4) est optionnel et pas activé par défaut
- La qualité du sentiment dépend fortement de FinBERT qui n'est pas ré-entraîné sur des données financières récentes
- Pas de validation formelle de la valeur ajoutée du sentiment vs quant seul

**Risques principaux** :
- Bruit excessif du sentiment si les articles sont de mauvaise qualité
- Faux positifs sur des tickers mal mappés

**Pour atteindre 10/10** : Validation out-of-sample de la valeur ajoutée, ré-entraînement périodique de FinBERT, filtrage par source de news.

---

## 9. ModelFactory — 6.0/10

**Résumé** : Gouvernance ML ambitieuse avec multiples backends (LSTM+Attention, LightGBM, CatBoost, global model, cross-sectional). Le système de champion sélection et de serving est bien conçu. Mais la complexité accumulée (plan ML v2 ternaire en cours) fait peser un risque de fragilité.

**Points forts** :
- Gouvernance multi-modèles avec sélection automatique du champion
- Garde-fou de persistance : validation des colonnes de gouvernance avant insertion (`db_registry.py`)
- Inférence routée vers le backend sélectionné
- Traçabilité dans `model_predictions` (selected_model, decision_threshold, etc.)
- Drift monitor et auto-rollback
- Walk-forward validation

**Faiblesses** :
- Complexité très élevée : 25+ fichiers dans `modelFactory/`
- Plan ML v2 ternaire (long/flat/short) ajoute encore de la complexité
- Le global model et le cross-sectional sont optionnels — périmètre mal défini
- Pas de test A/B permettant de comparer les backends en conditions réelles
- Les hyperparamètres par défaut dans l'IHM (`DEFAULT_ML_*`) sont nombreux et leur justification n'est pas documentée
- Pas de procédure documentée de rollback si un champion ML dégrade la performance

**Risques principaux** :
- Overfitting non détecté si le drift monitor n'est pas assez sensible
- Fragilité opérationnelle : trop de paramètres ML exposés dans l'IHM
- Coût cognitif élevé pour l'opérateur

**Pour atteindre 10/10** : Simplifier les options ML exposées, A/B testing automatisé, procédure de rollback documentée et testée, validation out-of-sample systématique.

---

## 10. Risk Management — 7.5/10

**Résumé** : Module risk mature avec sizing ATR/Kelly, circuit breaker, filtre de corrélation, contraintes de portefeuille, et intégration du régime de marché. Le support short selling (plan v2) est en cours d'ajout.

**Points forts** :
- Circuit breaker avec mode blocage et mode dégradé
- Ramp-up régimed progressif conditionné au régime et à l'equity
- Politique Kelly conditionnelle par tranche de capital (≥25k$)
- Filtre de corrélation paramétrable
- Tracking de concentration (SymbolTradeTracker, ConsecutiveLossTracker)
- Intégration du régime de marché via `regime_apply.py`

**Faiblesses** :
- Paramètres de conviction (40% quant, 60% ML) uniformes dans les presets ≥10k$ — non justifiés empiriquement
- Le ramp-up `ramp_up_max_pct=0.8` est identique pour toutes les tranches
- Les trackers de concentration (plan v2) ne sont pas encore testés en production
- Pas de test de résistance du circuit breaker avec des scénarios de crise historiques

**Risques principaux** :
- Sur-confiance dans les prédictions ML (60% du score de conviction)
- Ramp-up trop agressif (max 80%) après un drawdown

**Pour atteindre 10/10** : Backtest de résistance du circuit breaker sur crises historiques, validation empirique des poids de conviction, paramétrage différencié du ramp-up par tranche.

---

## 11. Execution Engine — 8.0/10

**Résumé** : Module d'exécution le plus mature du projet. Chaîne canonique bien définie : targets → intents → ordres → fills → positions → réconciliation → TCA. Le watcher post-exécution est un plus.

**Points forts** :
- Chaîne d'exécution en 10 phases bien définies
- Idempotence par SHA-256 (`idempotency_key`)
- Support multi-comptes natif
- Gestion des contraintes de compte (margin/cash) — le mode swing_only est désactivable mais post-PDT le day trading est libre
- Politique de levier explicite avec garde-fous
- Réconciliation structurée avec `ReconcileDiff`
- TCA (slippage, implementation shortfall)
- Watcher post-exécution pour la promotion trailing stop
- Kill switch natif (`cancel-all`)

**Faiblesses** :
- Le mode `live` exige une ressaisie du label de compte — sécurité appréciable mais pas infaillible
- Pas de simulation de latence réseau dans les tests
- La transition stop→trailing est complexe et pourrait échouer silencieusement
- `python -m execution_engine` est déprécié mais toujours présent → confusion possible

**Risques principaux** :
- Échec silencieux du watcher → stops non promus → risque de perte non contrôlée
- Course critique entre le watcher et une exécution manuelle

**Pour atteindre 10/10** : Tests de résilience réseau, heartbeat du watcher avec alerting, sandbox de pré-production.

---

## 12. Corporate Actions — 7.5/10

**Résumé** : Module propre avec séparation claire sync/apply, idempotence, et audit trail. La stratégie `data_adjustment='split'` + cash ledger pour les dividendes est cohérente.

**Points forts** :
- Factory `build_corporate_action_provider()` pour le switch EODHD/Alpaca
- Idempotence par SHA-256
- Audit trail complet (events, applications, cash ledger)
- Réconciliation post-apply
- Gestion des splits, reverse splits, cash-in-lieu

**Faiblesses** :
- La sync `--portfolio-only` peut ne rien ramener si aucune position n'existe — comportement documenté mais potentiellement déroutant
- Pas de cross-check automatique avec un second provider (Yahoo est mentionné mais optionnel)
- Le cash ledger n'est pas réconcilié avec le broker automatiquement

**Risques principaux** :
- Double-ajustement si un split est appliqué à la fois dans les prix (upstream) et dans les quantités (module CA) — le code dit que non, mais le risque existe si la convention `adjustment='split'` est violée
- Dividendes manqués si le provider CA ne les remonte pas

**Pour atteindre 10/10** : Cross-check automatique multi-provider, réconciliation broker automatique, alerte sur dividendes manqués.

---

## 13. Backtesting — 7.0/10

**Résumé** : Module backtesting riche avec modes research/pipeline, contraintes de compte réalistes, phases de fidélité PIT, et outillage de diagnostic. Le support short selling est en cours d'ajout.

**Points forts** :
- Deux modes : research (tolérant) et pipeline (strict PIT)
- Simulation des contraintes de compte (margin, cash settled, swing_only)
- Phases de fidélité opt-in (2→7)
- Backfill PIT de `stock_scores_history`
- Diagnostics screener et calibration des poids
- Drawdown breaker avec ramp-up régimed
- Manifeste de fidélité PIT
- Métadonnées de reproductibilité (git, seed, dataset_hash)

**Faiblesses** :
- Les phases de fidélité sont opt-in et non validées automatiquement
- Le cache Parquet n'est pas branché par défaut
- Pas de test de parité backtest/live automatisé en continu
- Les frais de transaction sont fixes par preset (pas de modèle réaliste par type d'ordre)

**Risques principaux** :
- Illusion de performance si la fidélité PIT est insuffisante
- Sur-optimisation si les paramètres sont calibrés sur le backtest sans validation out-of-sample

**Pour atteindre 10/10** : Validation out-of-sample systématique, parité backtest/live en paper, frais de transaction réalistes par type d'ordre.

---

## 14. IHM — 6.0/10

**Résumé** : Interface Streamlit fonctionnelle avec supervision complète du pipeline. La page Pipeline est bien organisée en 3 zones. Cependant, des incohérences avec les presets de capital et le backend sont préoccupantes.

**Points forts** :
- Organisation claire : Vue d'ensemble, Pipeline, Backtesting, Screening, Risk, Execution, CA, ML, Paramètres
- Pilotage du workflow 1→14 avec paramètres exposés
- Sélecteur multi-comptes dans la sidebar
- Préférences persistées côté serveur (fractional shares)
- Notifications email fin de workflow
- Historicalisation des runs IHM

**Faiblesses** :
- **Incohérence IHM/presets** : l'IHM utilise `execution_swing_only=True` comme défaut, mais les presets utilisent `swing_only=false` — ce qui est le bon choix depuis la suppression de la PDT (4 juin 2026). L'IHM doit être alignée sur les presets (défaut `false`). Cf. anomalie A-IHM-001.
- Pas de validation dans l'IHM que les paramètres sont cohérents avec le preset de capital actif
- Trop d'options ML exposées (30+ paramètres)
- Pas de mode « lecture seule » pour éviter les actions dangereuses
- Les pages Risk et Execution pourraient être plus synthétiques

**Risques principaux** :
- Opérateur qui change des paramètres dans l'IHM sans comprendre l'impact
- Défauts IHM non alignés avec les presets → mauvaises décisions d'exécution (`swing_only=True` restrictif au lieu du `false` post-PDT)

**Pour atteindre 10/10** : Validation IHM des paramètres vs preset, simplification des options exposées, mode lecture seule, alignement des défauts IHM avec les presets.

---

## 15. Observabilité / Run Summaries / Logs — 6.5/10

**Résumé** : Les run summaries structurés (JSON) sont une bonne pratique. Les logs sont correctement configurés avec rotation. Le monitoring Prometheus est présent mais opt-in.

**Points forts** :
- Run summaries structurés avec préfixe `::alpha_trade_run_summary::`
- RotatingFileHandler (5 Mo, 3 backups)
- Endpoint `/metrics` Prometheus opt-in
- Persistance des résumés dans `run_business_summaries`
- Compteurs IEX propagés dans les run summaries

**Faiblesses** :
- Pas de dashboard de monitoring (Grafana non configuré)
- Les logs ne sont pas structurés (pas de JSON logging)
- Pas d'alerting automatique sur les erreurs critiques (l'email IHM est best-effort)
- Le watcher a des heartbeats mais pas d'alerting si le heartbeat s'arrête

**Risques principaux** :
- Incident non détecté si personne ne regarde les logs
- Perte d'information dans les logs non structurés

**Pour atteindre 10/10** : JSON logging, dashboard Grafana, alerting automatique (Slack/email), healthcheck endpoint.

---

## 16. Sécurité / Readiness Production — 6.0/10

**Résumé** : Bonnes pratiques de sécurité sur les secrets (variables d'env, placeholders, vault). Le mode live a des garde-fous. Mais il manque une sandbox de pré-production.

**Points forts** :
- Secrets par variables d'environnement, jamais en clair dans `config.yaml`
- Scanner de secrets (`core/secrets/scan_yaml_for_literal_secrets`)
- Validation des credentials au démarrage
- Mode live avec confirmation explicite
- Kill switch natif
- Circuit breaker
- Packaging Windows avec DPAPI pour le secret store

**Faiblesses** :
- Pas de sandbox de pré-production (paper strict simulant exactement le live)
- Pas de test de pénétration ni d'audit de sécurité externe
- Les variables d'environnement sont la seule méthode de gestion des secrets (pas de vault externe type HashiCorp)
- Pas de chiffrement des données sensibles en base
- Pas de rate limiting sur l'IHM

**Risques principaux** :
- Fuite de secrets si les variables d'environnement sont exposées
- Action live accidentelle si mauvaise configuration

**Pour atteindre 10/10** : Vault externe (HashiCorp), sandbox de pré-production, chiffrement des données sensibles, audit de sécurité externe.

---

## 17. Qualité logicielle globale — 6.5/10

**Résumé** : La base de code est de bonne qualité avec typage, lint, et une suite de tests extensive (~230 fichiers). Cependant, la complexité accumulée et le rythme rapide d'ajout de fonctionnalités créent de la dette technique.

**Points forts** :
- Suite de tests extensive (~230 fichiers)
- Typage mypy configuré
- Lint ruff configuré
- Import-linter configuré
- pytest avec coverage ≥60%
- Property-based testing (hypothesis)
- Tests de parité backtest/live

**Faiblesses** :
- Duplication entre `stock_bars` et `stock_bars_daily`
- Code mort possible : `execution_engine/__main__.py` déprécié mais conservé
- Modules en cours de refactor (short selling, ML ternaire) qui complexifient le code existant
- Pas de test de mutation (mutmut configuré mais pas exécuté en CI)
- Pas de test de performance
- Certains fichiers sont très longs (ex: `ihm/services/pipeline_runner.py`)

**Risques principaux** :
- Dette technique croissante avec les plans v2
- Régression non détectée dans les zones sans tests

**Pour atteindre 10/10** : Tests de mutation en CI, tests de performance, réduction de la duplication, gel des features avant stabilisation.
