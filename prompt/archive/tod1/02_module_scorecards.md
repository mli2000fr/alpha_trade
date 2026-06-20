# 02 — Module Scorecards — Alpha Trade

> **Date** : mai 2026 | Code = source de vérité

---

## 1. Documentation

**Note : 9.5/10** *(révisée +0.5 Sprint S4 — beta_126/spread_bps corrigés, doc EODHD quota, spread IEX, lineage autogen CI confirmé)*

### Résumé
La documentation est remarquablement complète pour un projet indépendant : `DOC_FONCTIONNELLE.md` (588 lignes), `DOC_TECHNIQUE.md` (824 lignes), une doc dédiée par module. Les conventions OHLCV provider et `data_adjustment='split'` sont documentées et cohérentes avec le code. La règle de sélection du provider CA est explicitement documentée. La lineage matrix est synchronisée avec les tables réelles depuis Sprint S1. Les valeurs `beta_126` et `max_spread_bps` sont désormais cohérentes entre doc et code (Sprint S4 ✅).

### Points forts
- Bandeaux de convention en tête de `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md` signalant le provider primaire EODHD
- `data_lineage_matrix.md` avec producteur/consommateur par table — régénérée Sprint S1 ✅
- Runbooks opérateurs (`runbook_24_7.md`, `runbook_reconciliation.md`, etc.)
- Det tech "cochée" maintenue dans `DOC_TECHNIQUE.md §8`
- ✅ `DOC_TECHNIQUE.md:497` : "simulateur custom PIT — aucune dépendance vectorbt" (A-004 ✅)
- ✅ `DOC_FONCTIONNELLE.md:37` : ingestion EODHD nommée explicitement provider primaire (A-018 ✅)
- ✅ Rule de sélection provider CA documentée dans `DOC_FONCTIONNELLE.md:246` et `data_lineage_matrix.md §7` (A-005 ✅)
- ✅ Noms tables canoniques dans lineage matrix : `execution_order_requests`, `execution_broker_orders`, `execution_events` (A-002 ✅ Sprint S1)
- ✅ `DOC_FONCTIONNELLE.md §2.3` : `beta_126 >= 0.8` (corrigé depuis 1.0) et `spread_bps <= 40` (corrigé depuis 25 bps) — Sprint S4
- ✅ `doc/dataIntegrityEngine.md §3.3` : tableau quota EODHD par composant (A-020 ✅ Sprint S4)
- ✅ `doc/dataIntegrityEngine.md §3.4` : biais spreads IEX documenté avec mitigation (A-008 ✅ Sprint S4)
- ✅ `doc/dataIntegrityEngine.md §11` : `test_import_alpaca_bar_noop.py` et `test_data_lineage_autogen.py` référencés (A-023/A-026 ✅ Sprint S4)

### Faiblesses
- ~~`DOC_FONCTIONNELLE.md §2.3` cite `beta_126 >= 1.0` mais le code utilise 0.8~~ → ✅ corrigé Sprint S4
- ~~Nouvelles tables à intégrer dans la lineage matrix~~ → tables `execution_reconciliation_results`, `execution_targets_snapshot` présentes via `generate_data_lineage.py`

### Risques
- Aucun risque critique documentation actif → P3 uniquement

### Pour atteindre 10/10
- Documenter la procédure de déploiement SSL complète (certificat, test de connexion)
- Compléter le guide "disaster recovery" avec les procédures Alembic downgrade

---

## 2. Configuration (`config.yaml` + `config/capital_presets.yaml`)

**Note : 8.0/10** *(révisée — A-001 ✅ S1, A-006 ✅ S2, A-007 ✅ S2, A-016 ✅ S1)*

### Résumé
La configuration est centralisée dans `config.yaml` (224 lignes) et `config/capital_presets.yaml` (360 lignes). La structure est claire. Les credentials sont exclusivement via env vars / placeholders. La couche Market-Aware est bien configurée. Toutes les anomalies P1/P2 de configuration sont résolues.

### Points forts
- Aucune credential en clair (`scan_yaml_for_literal_secrets` enforced)
- `market_data.bars_provider: eodhd` comme défaut documenté et commenté
- Structure multi-comptes propre avec placeholders
- `market_regimes.enabled: true` avec fallback neutre documenté
- Capital presets couvrent 7 tranches bien graduées

### Faiblesses
- **P3** : `market_regimes.macro_provider: eodhd` mais `yields.enabled: false` — voir `doc/dataIntegrityEngine.md §3.3` pour le détail du quota consommé (A-020 ✅ Sprint S4 — documenté)
- **P3** : `risk_management.trailing_stop.enabled: false` par défaut mais configuration `dynamic_atr` complète présente — recommandé d'activer en paper

### Anomalies résolues dans cette section
- ✅ `capital_0_2000.risk_max_positions: 3`, `risk_min_position_notional: 500.0` (A-001 ✅ Sprint S1)
- ✅ `selector_min_close: 10.0` sur tous les presets (A-007 ✅ Sprint S2)
- ✅ Contraintes margin clarifiées sur les 3 presets ≥ 25k$ (A-006 ✅ Sprint S2)
- ✅ Reliquats cash clarifiés sur 4 presets (A-016 ✅ Sprint S1)

### Risques
- `yields.enabled: false` → quota EODHD consommé sans valeur ajoutée (P3 mineur)

### Pour atteindre 10/10
- Documenter le quota EODHD consommé par macro_provider même quand yields désactivés (Sprint S4)
- Activer Kelly sur presets ≥ 50k$ avec guard `max_kelly_fraction: 0.25`
- Validation schéma YAML automatique en CI (déjà partiellement testé dans `test_config_yaml_schema.py`)

---

## 3. dataIntegrityEngine

**Note : 8.0/10** *(révisée +0.5 Sprint S4 — A-008 documenté, A-023/A-026 couverts, §3.3/§3.4 ajoutés)*

### Résumé
Module d'ingestion et de nettoyage bien structuré. La migration vers EODHD comme provider primaire est proprement implémentée avec un shim de rétrocompatibilité (`import_eodhd_bar.py`), une logique circuit breaker EODHD, un cache disque Parquet, et un tracker de quota. Le sanitizer daily produit un audit trail dans `cleaning_audit_runs`. Le cross-check Stooq est best-effort et documenté comme tel. Sprint S4 : quota EODHD documenté par composant (§3.3), biais spreads IEX documenté avec mitigation (§3.4), tests CI confirmés (A-023, A-026).

### Points forts
- Shim architecture (`import_eodhd_bar.py` → sous-package `eodhd/`) permet patchabilité des tests sans casser la surface publique
- Circuit breaker EODHD (`consecutive_failures: 5, cooldown_minutes: 30`) bien configuré
- `fetch_eod_bulk` + fallback `fetch_eod` par symbole : résilience provider
- Quota tracker avec seuil soft (80k) et hard (100k) sur plan 100k/jour
- `data_adjustment='split'` enforced par CHECK SQL sur `stock_bars` et `stock_bars_daily`
- ✅ **`doc/dataIntegrityEngine.md §3.3`** : tableau quota EODHD par composant (bulk EOD, VIX macro, corporate actions) — yields via Stooq gratuit (A-020 ✅ Sprint S4)
- ✅ **`doc/dataIntegrityEngine.md §3.4`** : biais spreads IEX ~50 bps documenté + mitigation `max_spread_bps_iex = 65` / `min_quote_size = 100` (A-008 ✅ Sprint S4)
- ✅ **`test_import_alpaca_bar_noop.py`** + **`test_data_lineage_autogen.py`** référencés dans doc §11, confirmés dans CI (A-023 ✅, A-026 ✅ Sprint S4)

### Faiblesses
- **P2** : Stock quotes (`stock_quote_snapshots`) restent sur Alpaca IEX — spreads peuvent être ~50 bps vs NBBO réel, biais possible sur filtre `spread_bps` du selector (mitigé par `max_spread_bps_iex = 65`)
- **P3** : `data_source_health.py` présent mais son intégration dans le pipeline quotidien et son exposition IHM mériteraient d'être vérifiées

### Risques
- Quotes IEX biaisées → universs de titres rejetés par spread_bps trop conservateur → univers réduit artificiellement
- Market cap stale (Finnhub) → filtre market_cap peut rejeter ou accepter des symboles incorrectement

### Pour atteindre 10/10
- Intégrer NBBO quotes (Polygon/EODHD) pour réduire le biais IEX sur les spreads
- Alerting automatique quand cross-check Stooq détecte N anomalies > seuil
- Exposer les métriques de santé `data_source_health` dans l'IHM (page supervision)
- Documenter clairement le quota EODHD consommé par type d'appel (bulk EOD vs per-symbol fallback)

---

## 4. database / migrations

**Note : 7.5/10** *(révisée — A-009 ✅ résolu, A-012 ✅ résolu)*

### Résumé
Persistance MySQL 8.x avec SQLAlchemy Core (pas d'ORM complet), Alembic pour les migrations, pool configuré (`pool_size=2, max_overflow=3`). Les migrations `0027` et `0028` (news relevance/sentiment) sont bien documentées. La DDL est dans `database/sql/` par sous-domaine. La contrainte d'unicité `model_predictions` est confirmée en place.

### Points forts
- Alembic avec révisions numérotées (`0027_news_ticker_map_relevance`, `0028_news_ticker_sentiment`)
- `CHECK` constraints SQL sur `data_adjustment` (convention projet enforced en DB)
- `account_id` propagé sur 12+ tables pour multi-comptes
- DDL organisé par domaine (stock/, news/, ml/, risk/, execution/, corporate_actions/)
- ✅ `model_predictions.sql:14` — `UNIQUE KEY uq_symbol_date_run` présent + `ON DUPLICATE KEY UPDATE` (A-009 ✅)
- ✅ SSL MySQL activable via `DB_SSL_CA_PATH` env var (`database/connection.py:97-111`) (A-012 ✅)

### Faiblesses
- **P1** : `data_lineage_matrix.md` utilise `execution_orders` et `execution_audit_events` — noms obsolètes (A-002 actif)
- **P2** : `alembic.ini` contient une URL factice — la procédure d'injection d'URL est manuelle
- **P3** : `database/sql/all_tables.py` n'est pas mentionné dans le pipeline de bootstrap IHM

### Risques
- Incohérence noms tables dans la lineage matrix → confusion lors d'un incident, requêtes SQL incorrectes

### Pour atteindre 10/10
- Régénérer `data_lineage_matrix.md` pour corriger les noms de tables (A-002)
- Documenter la procédure d'upgrade Alembic dans le runbook opérateur
- Activer SSL MySQL avec certificats et le documenter dans le `DOC_TECHNIQUE.md §4`

---

## 5. service / providers

**Note : 8.0/10** *(révisée +0.5 Sprint S4 — A-019 ✅, A-020 ✅)*

### Résumé
Les providers sont bien encapsulés : `service/alpaca/` (market data, trading, news), `service/eodhd/` (bars, splits, macro), `service/finnhub/` (profil, earnings), `service/stooq/` (macro VIX/10Y), `service/market/` (market regime orchestration). Pattern de retry/backoff cohérent. `AccountRegistry` singleton pour multi-comptes. Depuis Sprint S4 : Stooq correctement documenté (sans clé API, usage gratuit) + test ajouté.

### Points forts
- Retry borné + backoff exponentiel partout (5 tentatives, 2^attempt secondes)
- `BrokerApiError` sur 4xx (pas de retry) bien distinct des 5xx/timeout
- EODHD quota tracker (soft + hard) avec circuit breaker
- AccountRegistry avec résolution prioritaire (config.yaml > env vars > fallback)
- Rate limiting : 200ms entre bars, 350ms entre ordres
- ✅ **Stooq sans clé API documenté** : `service/stooq/clientStooq.py` docstring Sprint S4 — `STOOQ_API_KEY` optionnelle, service gratuit sans inscription (A-019 ✅)
- ✅ **Test `test_stooq_provider_works_without_api_key`** : confirme que l'URL ne contient pas `apikey` si la variable est absente (A-019 ✅ Sprint S4)

### Faiblesses
- **P2** : `service/alpaca/trading_client.py` — pas de vérification que le mode `live` vs `paper` correspond au compte réellement ciblé
- **P2** : Stooq client utilise des symboles `^vix`, `^vix9d`, `^tnx` qui peuvent changer de format selon l'endpoint Stooq — fragilité potentielle

### Risques
- Mode broker mal détecté → ordre live sur compte paper ou vice versa
- Stooq instabilité → régime macro fallback neutre → sous-optimisation du market regime

### Pour atteindre 10/10
- Valider mode vs URL broker à l'initialisation (`BrokerAdapter.__init__`)
- Tester le client Stooq avec et sans clé STOOQ_API_KEY
- Ajouter un provider de fallback robuste pour le macro VIX (cache local 24h si aucun provider disponible)

---

## 6. screener

**Note : 7/10**

### Résumé
Screener de liquidité en 3 passes (volume, force relative, range historique), exécuté par chunks de 500 symboles avec `ProcessPoolExecutor`. Produit `stock_scores` avec run_summaries. Bien testé. Risque d'univers vide identifié.

### Points forts
- ProcessPoolExecutor : parallélisme efficace sans contention mémoire
- Run summaries exportés (`::alpha_trade_run_summary::` pattern)
- Filtres SQL pré-sélection + filet pandas pour la sécurité
- Seuil minimum configurable `screener_liquidity_threshold_usd`

### Faiblesses
- **P2** : Risque d'univers vide si le seuil `screener_liquidity_threshold_usd` est trop élevé pour un petit compte actif lors d'un marché baissier
- **P2** : Le screener ne produit pas de `stock_scores_history` directement — c'est le backfill qui le fait. Sur la chaîne live, il n'y a donc pas d'historique automatique de scores sans backfill explicite
- **P3** : Les erreurs de chunk sont isolées mais leur agrégation dans les run_summaries n'est pas standardisée (peut varier selon le mode d'exécution)

### Risques
- Univers vide → `LOGGER.critical` mais le pipeline continue → exécution sur 0 candidats → portefeuille vide sans signal clair pour l'opérateur
- Absence de `stock_scores_history` live → backfill PIT impossible sans backfill explicite préalable

### Pour atteindre 10/10
- Ajouter un circuit breaker spécifique `screener_universe_too_small` (< N symboles après filtrage → abort pipeline)
- Brancher l'écriture automatique dans `stock_scores_history` à chaque run live (PIT immédiat)
- Normaliser les error counters dans les run_summaries

---

## 7. selector (AlphaScanner)

**Note : 7.5/10**

### Résumé
AlphaScanner multi-facteurs mature : Trend Score (Minervini), VCP, beta_126 local, spread filter, earnings blackout, neutralisation sectorielle, winsorisation. Profils stricts partagés dans `core/filter_profiles.py`. PIT-safe via `reference_date`. ThreadPoolExecutor.

### Points forts
- `STRICT_SWING_CASH_FILTERS` centralisé dans `core/filter_profiles.py` (plus de duplication)
- `fetch_quote_snapshots(reference_date=...)` et `fetch_next_earnings(reference_date=...)` pour PIT correct
- `beta_126` calculé localement contre SPY : pas de dépendance provider externe
- `max_spread_bps_iex` + `min_quote_size` pour relâchement contrôlé quotes IEX
- `market_cap_max_age_days: 45` TTL market cap appliqué

### Faiblesses
- **P2** : La neutralisation sectorielle intra-secteur peut perturber le ranking si un secteur entier est en tendance forte (surpondération d'un secteur fort jugé "normal")
- **P3** : Le score composite `50% × (trend+vcp)/2 + 30% × score_screener + 20% × RSI_relatif` a des pondérations non calibrées explicitement

### Anomalies résolues dans cette section
- ✅ `selector_min_close: 10.0` sur tous les presets (A-007 ✅ Sprint S2)

### Risques
- Neutralisation sectorielle peut créer des biais inverses dans certains régimes

### Pour atteindre 10/10
- Aligner tous les presets sur `min_close ≥ 10.0` ou documenter explicitement la déviation justifiée
- Calibrer les pondérations du score composite via backtest walk-forward
- Rendre configurable la normalisation sectorielle (opt-in par régime)

---

## 8. event_sentiment

**Note : 6.5/10**

### Résumé
Pipeline NLP FinBERT complet : ingestion news (Alpaca), scoring par ticker, fusion `75% quant + 15% sentiment + 10% macro`. Migrations `0027`/`0028` pour relevance et scoring contextuel. Modes `provider_default`, `strict`, `scored`. Rétrocompatibilité garantie par COALESCE.

### Points forts
- Séparation claire ingestion / scoring / fusion
- Pondération par `COALESCE(relevance_score, 1.0)` rétrocompatible
- Mode scoring contextuel en opt-in (`enable_contextual_scoring: false`) — ne casse pas l'historique
- Calibration sentiment et walk-forward disponibles en backtesting

### Faiblesses
- **P1** : Le provider news (Alpaca) peut avoir des lacunes historiques — pas de fallback news provider documenté en production. Si Alpaca News change d'API, le sentiment pipeline s'arrête sans fallback
- **P2** : Le backfill de `relevance_score` sur l'historique n'est pas automatique (`NULL` accepté) — cohérence entre articles anciens (sans relevance) et nouveaux (avec relevance) non garantie dans les signaux produits
- **P2** : Le scoring contextuel (`enable_contextual_scoring: false` par défaut) représente la feature la plus précise mais n'est pas utilisée en production — la fusion reste donc sur `news_sentiment` standard, moins précis
- **P3** : `min_news_count: 2` — avec seulement 2 articles, le score peut être très bruité pour des small/mid caps

### Risques
- Provider news unique → single point of failure du pipeline sentiment
- Score FinBERT peut être optimiste (biais positif connu du modèle ProsusAI/finbert sur certains types de news)
- Absence de backfill relevance → résultats de calibration sentiment potentiellement biaisés sur historique mixte

### Pour atteindre 10/10
- Ajouter fallback news provider (EODHD news ou Finnhub news)
- Automatiser le backfill `relevance_score` sur historique lors d'une migration scheduled
- Activer `enable_contextual_scoring` progressivement avec tests A/B sur backtest
- Augmenter `min_news_count: 3` pour réduire le bruit

---

## 9. modelFactory

**Note : 7.0/10** *(révisée — A-003 ✅ résolu)*

### Résumé
Gouvernance multi-modèles mature : LSTM+Attention, challengers LightGBM/CatBoost locaux, modèle global optionnel, champion selection, calibration Platt, optimisation seuil. Serving route vers backend sélectionné. GPU-aware. La gouvernance ML en DB est désormais complète avec `selected_model`, `decision_threshold`, `calibration_method` et `signal_label` persistés.

### Points forts
- Champion selection uniquement si backend réellement inférable (artefacts présents)
- Router `predictor.py` vers 4 backends
- ✅ `model_predictions` : `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` persistés (`database/sql/ml/model_predictions.sql:8-11` + `modelFactory/db_registry.py:336-363`) (A-003 ✅)
- Manifeste d'artefacts + rapport de gouvernance (`config.json`, `metrics.json`)
- ML drift monitor + gate (`ml_kill_switch_active` dans run_summary)
- GPU force sequential sur machine single-GPU (protection correcte)

### Faiblesses
- **P2** : Entraînement par symbole individuel (LSTM) peut être lent sur un univers de 50–100 symboles — pas de parallélisation GPU multi-symboles documentée
- **P2** : Le champion par défaut (`fallback_default_champion`) n'est pas clairement documenté — si aucun backend n'est éligible, comportement à préciser
- **P3** : L'overfitting risk sur des séries temporelles courtes (< 2 ans) n'est pas quantifié ni documenté

### Risques
- LSTM sur séries courtes → overfitting probable → faux sentiment de robustesse ML
- Sauvegarde artefacts disque uniquement → pas de backup externe automatisé

### Pour atteindre 10/10
- Ajouter sauvegarde automatique des artefacts dans un stockage externe (S3 / backup réseau)
- Documenter et tester le comportement quand 0 champions sont éligibles
- Ajouter une métrique de robustesse out-of-sample (Sharpe hors échantillon, walk-forward) dans le rapport de gouvernance

---

## 10. risk_management

**Note : 7.5/10**

### Résumé
Module risk solide : sizing ATR+Kelly, filtre corrélation (0.80), circuit breaker drawdown/perte daily, constraint checks (poids secteur/position), conviction fusion quant/ML. Couche Market-Aware intégrée via `regime_apply.py`. Shadow compare disponible.

### Points forts
- `PortfolioBuilder` avec pipeline ACCEPTED/REDUCED/REJECTED traçable
- `risk_decisions` table : toutes les décisions d'acceptation/rejet persistées
- Circuit breaker + conviction_score articulés
- `regime_apply.py` : `risk_multiplier`, `allowed_slots`, market regime intégré
- Kelly fraction pondérée par probabilité ML (cohérent avec conviction 40/60)

### Faiblesses
- **P2** : Kelly désactivé (`risk_enable_kelly: false`) dans **tous** les presets — la conviction scoring utilise un poids ML de 60% mais le sizing reste purement ATR. L'utilité du Kelly est donc nulle en production
- **P2** : Le `max_gross_exposure: 100%` couplé à `risk_per_trade_pct: 1%` et `max_positions: 20` peut générer un portefeuille théoriquement pleinement chargé (20 × 5% = 100%) sans marge de sécurité d'exécution
- **P3** : `correlation_threshold: 0.80` sur 60 jours peut être insuffisant dans des marchés très corrélés (crise) — risque de concentration camouflée

### Risques
- Kelly désactivé = sizing non adaptatif = sursizing en période de faible win rate
- Corrélation 60j peut ne pas capturer les corrélations de crise (corrélations bondissent en crises)

### Pour atteindre 10/10
- Activer Kelly par défaut sur presets ≥ 50k$ avec guard `max_kelly_fraction: 0.25`
- Tester `correlation_threshold` dynamique (réduction à 0.60 en régime VIX > 25)
- Exposer le `shadow_compare` automatiquement en backtesting pour quantifier le coût de chaque contrainte

---

## 11. execution_engine

**Note : 7.5/10**

### Résumé
Chaîne canonique complète et bien auditée : targets_snapshot → order_requests → broker_orders → fills → positions → lots → réconciliation → TCA. Idempotence SHA-256. OCO logique. Protections broker-side post-fill. Watcher post-exécution. Market regime preflight. `ExecutionConfig` frozen dataclass avec validation.

### Points forts
- `ExecutionConfig` frozen + `__post_init__` validation exhaustive
- Idempotence SHA-256 sur `risk_run_id + symbole + rôle`
- Kill switch (3 échecs consécutifs)
- Séparation ordre d'entrée / enfants (protections) / OCO
- TCA : slippage + implementation shortfall persistés
- Contraintes cash/margin/swing appliquées côté execution (cohérent avec backtesting)

### Faiblesses
- **P2** : `auto_rebalance_on_reconcile: false` par défaut — si une position est hors cible, l'opérateur doit manuellement déclencher le rééquilibrage depuis l'IHM. Risque de dérive silencieuse
- **P2** : `fill_timeout_seconds: 120` pour paper et 180 pour live — un marché volatile peut voir des fills en dehors de ces fenêtres (gap down), les ordres non fillés créant des états orphelins
- **P3** : La protection stop initial est fixe (par défaut `trailing_stop_pct: 0.05`) sans ATR par défaut pour les positions normales — le trailing stop ATR est `enabled: false`

### Risques
- Orphans (positions ouvertes sans protections) si fill timeout dépasse la fenêtre
- Dérive de portefeuille silencieuse si réconciliation non déclenchée régulièrement

### Pour atteindre 10/10
- Activer `trailing_stop` ATR par défaut (au moins en paper)
- Ajouter alerting automatique quand `execution_reconciliation_results` contient des diffs non résolus depuis > 24h
- Documenter le comportement gap-down sur fill_timeout

---

## 12. corporate_actions

**Note : 7.5/10** *(révisée — A-005 ✅ résolu)*

### Résumé
Module complet pour dividendes/splits/reverse-splits. Idempotence SHA-256, audit trail complet (`corporate_actions_events`, `corporate_actions_applications`, `portfolio_cash_ledger`). Convention `data_adjustment='split'` respectée. Provider abstrait extensible. La règle de sélection du provider est maintenant explicitement documentée.

### Points forts
- Idempotence robuste (clé SHA-256 déterministe provider+symbol+type+ex_date+montant)
- `CorporateActionEngine` docstring explicite sur la stratégie : "ne touche pas stock_bars"
- Reconciliation après CA (`corporate_actions/reconciliation.py`)
- Rétrocompatibilité multi-provider (`AlpacaCorporateActionProvider` + `EodhdCorporateActionProvider`)
- ✅ Règle de sélection provider CA documentée : `EodhdCorporateActionProvider` si `bars_provider=eodhd`, `AlpacaCorporateActionProvider` sinon. `DOC_FONCTIONNELLE.md:246` + `data_lineage_matrix.md §7:109-111` + `corporate_actions/provider.py:402-432` (A-005 ✅)

### Faiblesses
- **P2** : `sync --portfolio-only` ne synchronise que les symboles détenus — split annoncé hors fenêtre de détention peut être manqué
- **P3** : Le reverse split avec cash-in-lieu sur les fractions < 0.001 part non testé spécifiquement

### Risques
- Split manqué si sync non exécuté le jour J du détachement

### Pour atteindre 10/10
- Ajouter alerting si `corporate_actions_events.status != applied` après 24h
- Tester les fractions très petites (< 0.001) sur reverse split

---

## 13. backtesting

**Note : 8.0/10** *(révisée +0.5 Sprint S4 — A-022 ✅ `walk_forward_risk_params`)*

### Résumé
Module backtesting mature avec modes research/pipeline, convention `signal J → entrée open J+1`, simulation cash/swing_only, phases de fidélité 2/3/4/5/7. Walk-forward, calibration sentiment, diagnostic screener. `BacktestReport` structuré avec `report.json`. PIT via `stock_scores_history`. Depuis Sprint S3 : ParquetCache branché (`--use-cache`), Bootstrap Monte Carlo exposé (`--bootstrap-samples`), bornes walk-forward enforced [0.05, 0.40]. Depuis Sprint S4 : `walk_forward_risk_params()` pour ATR/Kelly/correlation.

### Points forts
- Convention fidèle `signal J → entrée J+1 open` (pas de look-ahead)
- Phases de fidélité opt-in (risk_bridge, execution_replay, protection, watcher, exit)
- `TradingConstraintConfig` : axes `account_type` et `swing_only` pour les contraintes actives
- `BackfillScoresHistoryService` : reconstruction PIT historique
- `run_metadata` avec git_commit_sha, dataset_hash (reproductibilité)
- ✅ **`--use-cache`** : `ParquetCache` branché dans CLI `backtesting run` — 3x–10x vitesse (A-010 ✅ Sprint S3)
- ✅ **`--bootstrap-samples N`** + **`--sensitivity-analysis`** exposés en CLI (A-011 ✅ Sprint S3)
- ✅ **Bornes walk-forward `[0.05, 0.40]`** enforced via `validate_walk_forward_weights()` (A-027 ✅ Sprint S3)
- ✅ **`walk_forward_risk_params(returns, param_grid)`** : grid-search ATR period / Kelly fraction / correlation threshold avec métriques Sharpe/Sortino/hit-rate (A-022 ✅ Sprint S4)

### Faiblesses
- **P3** : `walk_forward_risk_params` est une grid-search légère sur une série de rendements — ne simule pas un backtest complet par combinaison. Pour une validation complète, exécuter le simulateur complet par combinaison manuelle

### Risques
- Grid-search légère vs backtest complet → peut sélectionner des paramètres sub-optimaux sur des séries courtes

### Pour atteindre 10/10
- Ajouter un rapport automatique Bootstrap MC dans les artifacts de chaque run
- Intégrer `walk_forward_risk_params` dans la page IHM Backtesting (visualisation de la grid)

---

## 14. IHM / supervision

**Note : 8.5/10** *(révisée +0.5 Sprint S4 — A-021 ✅ Widget PnL quotidien)*

### Résumé
IHM Streamlit opérateur complète : pipeline 1→14, Backtesting, Risk, Exécution, Market Regime, Supervision Ops, Paramètres. Workflow quotidien one-click. Process registry. Résumés métier structurés. Supervision Windows watcher read-only. Depuis Sprint S3 : alerte IHM sur diffs réconciliation non résolus > 24h et sur market_cap TTL expiré. Depuis Sprint S4 : widget PnL latent des positions ouvertes (section 0 de la page Overview).

### Points forts
- Workflow pipeline GUI complet avec résumés métier extraits (`::alpha_trade_run_summary::`)
- Sélecteur compte multi-comptes dans sidebar
- Supervision watcher Windows read-only (Task Scheduler / NSSM) sans admin
- Page Market Regime avec snapshot à la volée + historique
- `test_ihm_pipeline_e2e.py`, `test_ihm_execution_e2e.py`, `test_ihm_market_regime_banner.py` : tests E2E
- ✅ **Alerte réconciliation** : bandeau warn si diffs non résolus depuis > 24h (A-014 ✅ Sprint S3)
- ✅ **Alerte market_cap TTL** : warning si > 30% des symboles ont market_cap > 45j (A-015 ✅ Sprint S3)
- ✅ **Widget PnL latent** : `_render_pnl_widget()` section 0 — `compute_daily_pnl()` via `broker_positions_snapshots.unrealized_pnl`, gracieux si 0 position (paper trading) (A-021 ✅ Sprint S4)

### Faiblesses
- **P3** : Notifications email configurables depuis l'IHM mais le pipeline SMTP mériterait un test d'intégration avec serveur mock
- **P3** : `walk_forward_risk_params` pas encore exposé dans la page Backtesting IHM

### Risques
- ~~Absence de PnL live~~ → ✅ résolu Sprint S4

### Pour atteindre 10/10
- Tester le pipeline SMTP de notifications en intégration (avec serveur mock)
- Ajouter un indicateur "dernière exécution : il y a N heures" dans la bannière
- Exposer la grid-search `walk_forward_risk_params` dans la page IHM Backtesting

---

## 15. Observabilité / run summaries / logs

**Note : 7.5/10** *(révisée +0.5 — A-013 ✅, A-025 ✅ Sprint S3)*

### Résumé
`TimedRotatingFileHandler` + gzip depuis Sprint S3, logs structurés par module, `run_summaries` DB + `::alpha_trade_run_summary::` pattern IHM. Tables `execution_events`, `risk_decisions`, `cleaning_audit_runs` fournissent un audit trail multi-couches. Alerting email automatique sur circuit_breaker opérationnel depuis Sprint S3.

### Points forts
- `run_business_summaries` table partagée entre watcher, execution, screener
- Pattern `::alpha_trade_run_summary::` parsé et affiché dans l'IHM
- `execution_events` : journal complet événement par événement
- Artifacts JSON `artifacts/market_regime/snapshot_*.json` exploitables par des outils tiers
- ✅ **`TimedRotatingFileHandler`** quotidien avec compression gzip automatique + max 30 fichiers (A-025 ✅ Sprint S3)
- ✅ **Alerting email automatique** : `NotificationService` déclenché sur `circuit_breaker_fired` + `kill_switch_activated` via SMTP (A-013 ✅ Sprint S3)

### Faiblesses
- **P2** : Pas de monitoring externe (Prometheus/Grafana/Alertmanager) — observabilité limitée à la consultation active de l'IHM
- **P2** : Les logs sont en fichiers rotatifs locaux — pas de centralisation (ELK/Loki) pour audit historique long ou multi-machines
- **P3** : Les `run_summaries` IHM sont capturés par pattern regex sur stdout — fragile si un print non anticipé précède le pattern

### Risques
- Logs rotatifs locaux : historique limité à 30 fichiers gzip — suffisant pour usage quotidien mais pas pour audit annuel
- Pas de Prometheus → métriques pipeline (latence, count candidats, nb ordres) non visualisables en temps réel

### Pour atteindre 10/10
- Intégrer Prometheus ou équivalent pour métriques pipeline (latence steps, count candidats, nb ordres) → Sprint S5
- Centraliser les logs (syslog, Loki ou équivalent Windows) → Sprint S5
- Renforcer le pattern de capture run_summary (JSON strict plutôt que regex stdout)

---

## 16. Sécurité / readiness production

**Note : 7.5/10** *(révisée — A-012 ✅ résolu)*

### Résumé
Bonne base : credentials via env vars uniquement, scan literals YAML automatisé (`test_config_no_literal_secrets.py`), confirmation interactive live, vault optionnel (`${vault:...}`), secrets masqués à l'affichage. SSL MySQL désormais activable via env var.

### Points forts
- `scan_yaml_for_literal_secrets` enforced en test (P0 automatiquement bloquant)
- Vault support (`ALPHA_TRADE_VAULT_ADDR`) pour SMTP password
- Confirmation `oui` requise en mode live
- Allowlist stricte PowerShell bridge (watcher read-only uniquement)
- `__all__` audité pour éviter exposition API privée (`test_audit_private_api_exposure.py`)
- ✅ SSL MySQL activable via `DB_SSL_CA_PATH` env var (`database/connection.py:97-111`) — ne casse pas le LAN dev sans certificat (A-012 ✅)

### Faiblesses
- **P2** : La confirmation live est interactive (saisie `oui`) mais pas renforcé par une double confirmation ou un token out-of-band. Un script mal écrit peut passer outre
- **P3** : Rotation automatique des secrets non implémentée — si une clé Alpaca est compromise, la procédure de rotation est manuelle
- **P3** : SSL non activé par défaut — l'opérateur doit définir `DB_SSL_CA_PATH` explicitement

### Risques
- Script automatisé bypasse la confirmation live → ordres réels non désirés
- Rotation secrets manuelle → délai de réaction si compromission

### Pour atteindre 10/10
- Documenter la procédure de déploiement SSL (certificat, variable, test de connexion)
- Implémenter rotation secrets Alpaca (script de validation post-rotation)
- Ajouter confirm live via fichier `live_session_token` généré à chaque session (pas juste stdin)

