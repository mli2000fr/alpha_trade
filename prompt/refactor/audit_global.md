# Audit global — Alpha Trade

> Audit synthétique transverse du projet **Alpha Trade**, plateforme de
> swing trading batch quotidienne, données principales Alpaca free (IEX),
> backend MySQL, IHM Streamlit.
>
> Ce document est la **synthèse haut niveau** des audits modulaires :
>
> - [`audit_dataIntegrityEngine.md`](audit_dataIntegrityEngine.md)
> - [`audit_database.md`](audit_database.md)
> - [`audit_service.md`](audit_service.md)
> - [`audit_screener.md`](audit_screener.md)
> - [`audit_selector.md`](audit_selector.md)
> - [`audit_event_sentiment.md`](audit_event_sentiment.md)
> - [`audit_modelFactory.md`](audit_modelFactory.md)
> - [`audit_risk_management.md`](audit_risk_management.md)
> - [`audit_execution.md`](audit_execution.md)
> - [`audit_corporate_actions.md`](audit_corporate_actions.md)
> - [`audit_backtesting.md`](audit_backtesting.md)
> - [`audit_ihm.md`](audit_ihm.md)
> - [`audit_watcher.md`](audit_watcher.md)
> - [`audit_core_common.md`](audit_core_common.md)

---

## 1. Résumé exécutif

### État général

Alpha Trade est une **plateforme batch de swing trading actions US**, mature et
déjà très structurée :

- **13 modules métier** clairement délimités (`dataIntegrityEngine`, `database`,
  `service`, `screener`, `selector`, `event_sentiment`, `modelFactory`,
  `risk_management`, `execution_engine`, `corporate_actions`, `backtesting`,
  `ihm`, `watcher`).
- **Pipeline quotidien 1→14** orchestré depuis l'IHM, avec un workflow PIT
  reproductible (`backtesting.backfill-scores-history`).
- **Audit canonique exécution** post-cutover (snapshot → request → broker order
  → fill → position/lot → réconciliation → TCA).
- **Gouvernance ML multi-modèles** (LSTM+Attention + LightGBM + CatBoost +
  modèle global), sélection champion automatique, calibration, optimisation
  cible/seuil.
- **Documentation très complète** (`doc/*.md` totalisant > 5 000 lignes,
  `DOC_TECHNIQUE.md`, `DOC_FONCTIONNELLE.md`, `README.md`, doc dédiée par module).
- **Tests nombreux** (> 200 fichiers `tests/test_*`).

### Niveau de maturité

| Domaine | Maturité |
|---|---|
| Architecture modulaire | **Élevée** |
| Documentation | **Très élevée** (parfois trop dense pour onboarding) |
| Tests unitaires | **Élevée** par module |
| Tests d'intégration | **Faible** (peu de testcontainers MySQL en CI) |
| Observabilité (`run_summary` stdout) | **Élevée** |
| Observabilité (DB, dashboards) | **Modérée** |
| Sécurité opérationnelle (live trading) | **Modérée** (équity fallback, confirmations contournables) |
| Versioning de schéma SQL | **Faible** (Alembic présent mais sous-utilisé) |
| Gestion des limites Alpaca free / IEX | **Faible** (impacts non instrumentés) |
| Découplage interfaces (Protocols) | **Faible** (`core/interfaces.py` sous-utilisé) |

### Principaux risques transverses

1. **CRITIQUE — Limites Alpaca IEX non instrumentées** : la couverture ~2-3 %
   du volume consolidé impacte directement `liquidity_val`, `spread_bps`,
   `avg_dollar_volume_20d`, `atr_20`, `vwap`, et la TCA. Aucun pipeline ne
   mesure la dégradation, aucun cross-check externe n'existe.
2. **CRITIQUE — Schéma SQL non versionné Alembic** : 95 % des tables vivent dans
   `database/sql/*.sql` hors Alembic → divergences silencieuses possibles entre
   environnements.
3. **CRITIQUE — Equity fallback live silencieux** : `run_execution.py` retombe à
   `100 000 $` si `broker.get_account_equity()` lève → sizing massivement faux.
4. **ÉLEVÉ — Pas de Protocols centralisés** dans `core/interfaces.py` →
   couplage fort entre couches métier et infrastructures.
5. **ÉLEVÉ — `market_cap` Finnhub figé** sans TTL → filtre `market_cap >= 2 Md$`
   peut être faux pendant des mois.
6. **ÉLEVÉ — Pas de leader election watcher** → race conditions possibles sur
   les transitions de protections.
7. **ÉLEVÉ — Persistance ML challengers en `pickle`** → fragilité version +
   vecteur sécurité.
8. **ÉLEVÉ — Pas de costs/slippage explicites** dans le backtest → résultats
   optimistes de plusieurs % par an.
9. **MODÉRÉ — Convention `split_adjusted` non matérialisée par contrainte SQL**
   → un changement par accident (test, branche) pollue silencieusement la base.
10. **MODÉRÉ — `pages/pipeline.py` IHM monolithique** → maintenabilité.

### Priorités immédiates (≤ 2 semaines)

1. Profiter de la **réinitialisation prévue de la base** pour :
   - migrer le schéma sous Alembic (baseline `0001_initial_schema`) ;
   - ajouter `CHECK (data_adjustment='split')` partout ;
   - ajouter `data_source`, `market_cap_refreshed_at`, `metadata_synced_at` ;
   - ajouter audit dédié pour `quotes` et `earnings`.
2. **Sécuriser l'exécution live** :
   - exit immédiat sur erreur `get_account_equity()` ;
   - confirmation cryptographique forte (nom de compte saisi).
3. **Instrumenter les limites IEX** : compteurs `symbols_zero_volume_30d`,
   `symbols_stale_quote`, `symbols_stale_market_cap` dans tous les `run_summary`.
4. **Sortir les secrets DB de `config.yaml`** : placeholders `${VAR}` partout.
5. **Installer un lock SQL pour le watcher** via `execution_locks`.

---

## 2. Constat détaillé par module / pipeline

### Pipeline quotidien 1→14 — vision transverse

Étape par étape, points de fragilité :

| Étape | Risque transverse | Renvoi |
|---|---|---|
| 1. `import_alpaca_bar` | Pas d'exit ≠ 0 si ratio succès trop faible | `audit_dataIntegrityEngine.md` |
| 2. `data_sanitizer_daily` | Calendrier = SPY (couplage), jours `is_filled` consommés downstream | `audit_dataIntegrityEngine.md` |
| 3. `stock_screener` | `liquidity_val` IEX biais ; `historical_range_score` consomme `is_filled` | `audit_screener.md` |
| 4. `sync_latest_quotes` | Quotes IEX, pas de filtre fraîcheur ni audit | `audit_dataIntegrityEngine.md` |
| 5. `sync_earnings_calendar` | Source unique Finnhub free | `audit_dataIntegrityEngine.md` |
| 6. `alpha_scanner` | Filtre `spread_bps` biaisé IEX, `market_cap` Finnhub figé | `audit_selector.md` |
| 7. `sentiment_pipeline` | FinBERT non versionné, source unique Alpaca News | `audit_event_sentiment.md` |
| 8. `signal_aggregator` | Pondérations 75/15/10 non calibrées | `audit_event_sentiment.md` |
| 9. `ml_train` | Format pickle, pas de fingerprint features, walk-forward optionnel | `audit_modelFactory.md` |
| 10. `ml_predict` | Champion sans quarantaine, recharge complète à chaque appel | `audit_modelFactory.md` |
| 11. `risk_management` | Equity composé "best-effort", conviction 40/60 non calibrée | `audit_risk_management.md` |
| 12. `execution` | Equity fallback 100k$, confirmations live contournables | `audit_execution.md` |
| 12.bis `watcher` | Pas de leader election | `audit_watcher.md` |
| 13. `corporate_actions sync` | Source unique Alpaca CA, spin-offs non couverts | `audit_corporate_actions.md` |
| 14. `corporate_actions apply` | `idempotency_key` non documenté | `audit_corporate_actions.md` |

### Couplages problématiques transverses

1. **SPY = calendrier + benchmark + univers de prédiction** : trop de responsabilités
   sur un seul ticker. Si SPY a un incident provider, **toutes** les étapes 2 → 11
   sont dégradées.
2. **`history_status` pilote l'éligibilité** sur `dataIntegrityEngine`, `screener`,
   `selector`, `risk_management` simultanément → modification = effet cross-modules.
3. **`stock_quote_snapshots` (1 ligne / symbole / jour)** consommée par `selector`
   sans validation de fraîcheur → dépendance fragile.
4. **`stock_metadata.market_cap`** (Finnhub free, figé) consommé par filtre strict
   sans TTL.
5. **Formule de fusion conviction** dupliquée entre `event_sentiment.signal_aggregator`,
   `risk_management.conviction`, `backtesting.signal_replay` → divergence latente.

### Couches techniques faibles

- **`database`** : pas d'Alembic effectif, secrets en clair, pool minuscule.
- **`core/interfaces.py`** : sous-utilisé, couplage fort.
- **`common/utils.py`** : fourre-tout.
- **`service`** : politique de retry dispersée, pas de circuit breaker, `feed=iex`
  implicite.

---

## 3. Risques prioritaires (synthèse)

### Critique
- IEX non instrumenté + spreads pollués `stock_quote_snapshots`.
- Schéma SQL non versionné Alembic.
- Equity fallback live silencieux à 100k$.
- Persistance ML en pickle (fragilité + sécurité).

### Élevé
- `market_cap` figé sans TTL.
- Pas de Protocols (`core/interfaces.py` sous-utilisé).
- Pas de leader election watcher.
- Pas de costs/slippage explicites en backtest.
- Pondérations conviction / signal_aggregator non calibrées empiriquement.
- Source unique pour news, earnings, corporate actions, market cap.
- `train_symbol`, `execute_run`, `pages/pipeline.py` monolithiques.
- Fingerprint features ML absent.
- Pas de garde-fou anti-leak ML en `--ml-mode rebuild-missing`.

### Modéré
- Pas de contrainte `CHECK` SQL sur les énums métier.
- Pas de heartbeat persistant watcher.
- Documentation `MANUAL_REVIEW` / `BLOCKED` réconciliation manquante.
- `is_filled` non filtré dans `historical_range_score` / `high_52w_proximity`.
- Pas de TLS DB par défaut.
- Pas de rotation `artifacts/ihm_*_runs/`.
- Calendrier dépend de SPY (couplage).
- Pas de confirmation forte live trading.
- Pas de cache modèles dans le predictor.
- IHM sans authentification (acceptable localhost, à documenter).

### Faible
- Doublons (`update_sector` + naming, `corporate_action_run.py`, `importe_news.py`).
- Format `run_summary` non versionné (`schema_version`).
- Aliases legacy CLI à dépreciation propre.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

### Constat consolidé

Le projet repose **majoritairement** sur l'offre Alpaca gratuite, qui utilise le feed
**IEX** pour le market data. IEX représente ~2-3 % du volume US consolidé. Conséquences
mesurables :

| Donnée | Impact IEX | Modules impactés |
|---|---|---|
| `volume` | sous-évalué x30-50 | `screener` (liquidité), `selector` (avg_dollar_volume), `risk_management` (sizing indirect) |
| `vwap` | peu fiable | `execution_engine.tca` (slippage) |
| `bid/ask` quotes | spreads larges | **`selector` (spread_bps), critique** |
| OHLC | OK pour large caps, ±1-3 % small caps | `screener`, `modelFactory` (features), `backtesting` |
| `daily_return` | OK | tous |
| `historical_range_score` | OK si `is_filled` filtré | `screener`, `selector` |

**Le plus problématique** : `spread_bps` IEX consommé tel quel par le selector pour le
filtre `<= 25 bps`. Conduit à des **faux négatifs** (titres pourtant exécutables exclus)
de manière non quantifiée.

### Biais sur les filtres et la sélection

- **`liquidity_threshold_usd = 30 M$`** (selector) : équivalent IEX = ~1 Md$
  consolidated. **Cohérent avec l'objectif large/mid cap** swing.
- **`spread_bps <= 25`** : équivalent NBBO ~50 bps, donc trop strict en IEX.
- **`market_cap`** : pas affecté par IEX (Finnhub), mais affecté par le manque de TTL.
- **Score `total_score` percentile** : robuste relativement (tous les symboles mesurés
  sur la même base IEX).

### Biais sur la TCA (`execution_engine.tca`)

- `decision_price` souvent issu d'IEX, `fill_price` consolidé broker → slippage **biaisé
  systématiquement à la hausse** (pas une vraie mesure d'exécution).

### Alternatives gratuites pertinentes

| Source | Données | Qualité free | Pertinence pour Alpha Trade |
|---|---|---|---|
| **Stooq** | Daily OHLCV consolidé | Très bonne, pas de clé | **Élevée** — cross-check volume / OHLC daily, intégration `pandas-datareader` |
| **Yahoo Finance** (`yfinance`) | Daily, fundamentals, dividendes, splits, earnings | Bonne mais non officielle | **Élevée** — cross-check earnings + dividends + market_cap |
| **SEC EDGAR** | Filings 8-K, 10-K, 10-Q | Source officielle | **Élevée** pour event-driven (compléter Alpaca News) |
| **Polygon.io** free | NBBO, trades, snapshots | Quota strict 5 req/min | Modérée — utile pour test/dev cross-check NBBO |
| **Tiingo** free | EOD consolidé, fundamentals limités | Quota strict | Modérée |
| **FMP** free | Earnings, fundamentals | Quota free serré | Modérée |
| **Nasdaq Data Link** | Datasets gratuits limités | Variable | Faible |

### Recommandation cible

**Plan en 3 étapes** :

1. **Court terme** : instrumenter et documenter le biais IEX dans les `run_summary` et
   dans `doc/dataIntegrityEngine.md`. Compteurs `symbols_zero_volume_30d`,
   `stale_quote_pct`, `stale_market_cap_pct`.
2. **Moyen terme** : intégrer **Stooq** comme source de cross-check daily volume /
   OHLC dans `data_sanitizer_daily` (en best-effort, marquage divergences dans
   `cleaning_audit_runs`).
3. **Long terme** : intégrer **SEC EDGAR 8-K** comme second canal news événementiel
   (event-driven supplément à Alpaca News). Évaluer **Yahoo dividends** comme
   cross-check `corporate_actions`.

L'objectif n'est **pas** de remplacer Alpaca, mais d'avoir un **filet de sécurité
gratuit fiable** sur les données les plus exposées au biais IEX.

---

## 5. Choix recommandé pour la politique de prix

### Comparaison

| Critère | `split_adjusted` (choix actuel) | `all` |
|---|---|---|
| Simplicité | ✅ une série canonique | ❌ réécrit l'historique à chaque dividende |
| Auditabilité | ✅ prix = ce que voit le broker | ❌ prix synthétique |
| Cohérence comptable | ✅ dividendes = ledger séparé | ❌ double comptage potentiel |
| Performance backtest | ✅ + cash ledger CA pour total | ✅ direct mais opaque |
| Cohérence avec exécution live | ✅ broker affiche split-adjusted | ✅ |
| Maintenance | ✅ stable | ❌ recalculs continus |
| Comparabilité long terme dividendes inclus | ❌ besoin d'agréger ledger | ✅ direct |

### Recommandation

**Conserver `split_adjusted`** comme convention canonique. Implications pratiques :

1. **Matérialiser le choix dans le schéma SQL** :
   ```sql
   ALTER TABLE stock_bars ADD COLUMN data_adjustment VARCHAR(16) NOT NULL DEFAULT 'split';
   ALTER TABLE stock_bars ADD CONSTRAINT chk_bars_adj CHECK (data_adjustment = 'split');
   ALTER TABLE stock_bars_daily ADD CONSTRAINT chk_daily_adj CHECK (data_adjustment = 'split');
   ```
2. **Documenter explicitement** dans `README.md` :
   > Performance totale (dividendes inclus) =
   > `MTM(positions, stock_bars_daily.close) + cumulative(portfolio_cash_ledger)`
3. **Exposer dans `service/alpaca/clientAlpaca.py`** un paramètre `adjustment`
   typé `Literal["split","all","raw"]` validé.
4. **Ajouter dans `report.py`** deux KPI distincts :
   - `total_return_price_only` (sans dividendes) ;
   - `total_return_with_dividends` (avec ledger CA).
5. **Affirmer la convention** dans `doc/dataIntegrityEngine.md`,
   `doc/corporate_actions.md`, `doc/backetesting.md`.

Ce choix est **simple, traçable, cohérent** avec le reste de l'architecture
(comptabilité dividendes via ledger), et **adapté au swing trading actions cash**
(pas besoin de simuler la complexité d'une série dividendes incluse).

---

## 6. Quick wins (synthèse cross-modules)

### Données et schéma
1. Ajouter `CHECK (data_adjustment='split')` sur `stock_bars` et `stock_bars_daily`.
2. Ajouter `data_source VARCHAR(16)` sur tables marché (préparation cross-source).
3. Ajouter `market_cap_refreshed_at`, `metadata_synced_at` sur `stock_metadata`.
4. Filtrer `WHERE is_filled = 0` dans `historical_range_score` / `high_52w_proximity`.

### Sécurité opérationnelle
5. **Equity fallback fatal** en mode live (`raise RuntimeError`).
6. **Confirmation live renforcée** (saisie nom de compte).
7. **Lock SQL watcher** via `execution_locks`.
8. **Heartbeat watcher SQL persistant**.
9. **Sortir secrets DB de `config.yaml`** → placeholders `${VAR}`.

### Observabilité
10. Compteurs `symbols_zero_volume_30d`, `stale_quote_pct`, `stale_market_cap_pct`
    dans `run_summary`.
11. `chunk_failures` dans `run_summary` du screener.
12. `rejected_by_filter` (par filtre) dans `run_summary` du selector.
13. `account_equity_breakdown` dans `run_summary` du risk.
14. `schema_version` dans tous les `run_summary`.

### ML
15. Migrer `lightgbm` / `catboost` vers format natif (`save_model`).
16. Fingerprint features SHA256 dans `config.json` modèle.
17. Activer `--walkforward` par défaut en production.

### Backtest
18. Ajouter `--commission-bps`, `--slippage-bps` (défauts > 0).
19. Ajouter `total_return_with_dividends` au rapport.

### Configuration & service
20. Faire de `feed` un paramètre validé dans `clientAlpaca.fetch_bars`.
21. Helper unique de retry `service/_http_retry.py`.
22. Cache TTL 7j pour profils Finnhub.

### Documentation
23. Section "Limites IEX et impact concret" dans `doc/dataIntegrityEngine.md`.
24. Runbook `MANUAL_REVIEW` / `BLOCKED` dans `doc/execution_engine.md`.
25. Documenter construction `idempotency_key` corporate_actions.

---

## 7. Recommandations structurelles

### Architecture
1. **Centraliser les Protocols** dans `core/interfaces.py` :
   - `BrokerPort`, `MarketDataPort`, `BarsRepository`, `ScoresRepository`,
     `RiskRepository`, `ExecutionRepository`, `NewsProvider`,
     `CorporateActionProvider`.
   - Discipline d'usage forcée par `import-linter` (interdit aux modules métier
     d'importer directement les implémentations).
2. **Façade `database/repositories/`** : chaque module métier consomme un
   repository typé, plus de SQL inline éparpillé.
3. **Centraliser la formule de fusion conviction** dans `core/conviction.py`,
   consommée par `event_sentiment`, `risk_management`, `backtesting`.
4. **Centraliser les filtres / profils** dans `core/filter_profiles.py`,
   consommés par `screener`, `selector`, `backtesting`.
5. **Découper les monolithes** :
   - `execution_engine/executor.py` (`execute_run` en sous-méthodes + state machine).
   - `selector/alpha_scanner.py` (`factors.py` + `filters.py` + `ranking.py`).
   - `modelFactory/trainer.py` (`train_symbol` en sous-fonctions).
   - `ihm/pages/pipeline.py` en sous-modules.

### Données
6. **Faire d'Alembic la source de vérité du schéma SQL** : baseline
   `0001_initial_schema` + CI obligatoire `alembic upgrade head`.
7. **Découpler le calendrier de SPY** via `pandas_market_calendars`.
8. **Introduire une seconde source** (Stooq) en cross-check volume / OHLC daily.
9. **Audit dédié** pour quotes (`cleaning_audit_quotes_runs`), earnings
   (`cleaning_audit_earnings_runs`), CA (`corporate_actions_audit_runs`).

### Sécurité opérationnelle
10. **Vault / secret store** pour les credentials live (DPAPI Windows déjà
    partiellement en place pour le watcher).
11. **Kill switch global** : `python -m execution_engine cancel-all --account live1`.
12. **TLS DB** activable via env (`DB_SSL_CA_PATH`).
13. **Auth basique IHM** optionnelle (token query string ou Streamlit native).

### ML & qualité
14. **Quarantaine champion** : `--champion-min-runs N`, `--champion-min-days N`.
15. **Backup automatique `artifacts/models/`** + persistance `metrics.json`
    en BLOB DB pour les champions.
16. **Calibration empirique** des poids (conviction, signal_aggregator) sur
    backtest glissant 6 mois → tables historiques de versioning.

### Backtest & validation
17. **Validation hold-out** systématique pour le diagnostic screener phase 5-7.
18. **Costs / slippage** par défaut > 0 dans le simulator.
19. **Mode "shadow"** simulate parallèle d'un live pour mesurer la dérive.

---

## 8. Plan d'action priorisé

### Court terme (≤ 2 semaines)

> Bénéficier de la **réinitialisation prévue de la base** pour faire propre :

- **Schéma** : Alembic baseline `0001`, `CHECK (data_adjustment='split')`,
  `data_source`, `market_cap_refreshed_at`, `metadata_synced_at`, audit dédié
  quotes/earnings/CA, suppression des `.sql` obsolètes (execution legacy).
- **Sécurité live** : equity fallback fatal, confirmation live renforcée, secrets
  DB hors `config.yaml`.
- **Watcher** : lock SQL via `execution_locks`, heartbeat SQL.
- **Observabilité** : enrichir tous les `run_summary` (compteurs IEX,
  `chunk_failures`, `rejected_by_filter`, `account_equity_breakdown`,
  `schema_version`).
- **Quick wins** screener / selector listés (filtres `is_filled`, alias defaults).
- **Service** : `feed=iex` explicite, helper retry centralisé, cache Finnhub.
- **Documentation** : section "Limites IEX" dans `doc/dataIntegrityEngine.md` et
  `README.md`, runbook `MANUAL_REVIEW`, construction `idempotency_key` CA.

### Moyen terme (≤ 2 mois)

- **Architecture** :
  - Protocols `core/interfaces.py` (BrokerPort, MarketDataPort, repositories).
  - Façade `database/repositories/`.
  - `core/filter_profiles.py` partagé screener / selector / backtest.
  - `core/conviction.py` partagé event_sentiment / risk / backtest.
  - Découpage `executor.py`, `alpha_scanner.py`, `trainer.py`, `pages/pipeline.py`.
- **Données** :
  - Calendrier `pandas_market_calendars`.
  - Stooq cross-check volume / OHLC.
  - Yahoo cross-check earnings + dividends.
- **ML** :
  - Migration LightGBM/CatBoost format natif.
  - Fingerprint features.
  - Walk-forward par défaut.
  - Quarantaine champion.
  - Persistance `metrics.json` BLOB DB pour les champions.
- **Backtest** : costs/slippage > 0, validation hold-out diagnostic, profiles CLI
  consolidés.
- **Sécurité** : TLS DB, auth IHM optionnelle, kill switch.
- **Tests** : `testcontainers[mysql]` activés, tests contractuels IHM ↔ CLI,
  tests Protocols.

### Long terme (≤ 6 mois)

- **Architecture** :
  - Inversion de dépendance complète (modules métier ↔ Protocols).
  - `import-linter` enforced.
  - `ProcessRegistry` IHM DB-backed.
- **Données** :
  - SEC EDGAR 8-K comme second canal news.
  - Évaluer Polygon free / Tiingo pour NBBO.
- **ML** :
  - Calibration empirique automatisée poids (conviction, signal_aggregator).
  - Évaluer XGBoost comme 3e challenger.
  - Évaluer fine-tune LoRA FinBERT.
- **Backtest** :
  - Mode shadow live vs simulate.
  - Migration progressive hors vectorbt si maintenance défaillante.
- **Sécurité** :
  - Vault / DPAPI complet pour secrets live.
  - Audit `watcher_transitions`.
- **Observabilité** :
  - Dashboard Prometheus / Grafana minimal.
  - Drift ML monitoring auto.

---

## 9. Lacunes de tests, monitoring et documentation

### Tests

**Forces** : excellente couverture unitaire par module (>200 fichiers `test_*`),
tests CLI, tests des pages IHM, tests des résumés `run_summary`, tests de gouvernance ML.

**Manques transverses** :
- Peu / pas de tests d'intégration MySQL réel via `testcontainers[mysql]`
  (dépendance présente, à activer).
- Pas de test contractuel **IHM ↔ CLI backend** (introspection argparse).
- Pas de tests **PIT non-leak** explicites pour `--ml-mode rebuild-missing`.
- Pas de tests **costs/slippage présents** en backtest.
- Pas de tests **leader election watcher**.
- Pas de tests **Protocols contracts**.
- Pas de tests **fingerprint features stable** ML.
- Pas de tests **import-linter** (couplage architecture).
- Pas de tests **non-régression visuelle** IHM (Streamlit testing / Playwright).
- Pas de tests de **drift FinBERT** (changement de modèle silencieux).
- Pas de tests **équivalence simulate vs paper réel**.
- Pas de tests **plans d'exécution SQL** (EXPLAIN sur requêtes critiques).

### Monitoring

**Forces** : `run_summary` standardisés sur la plupart des CLI, IHM riche, audit
DB exhaustif côté exécution.

**Manques transverses** :
- Pas d'export Prometheus / metrics.
- Pas de dashboard "santé data" (fraîcheur tables).
- Pas d'alarme automatique sur seuils (`MANUAL_REVIEW > N`, `watcher heartbeat
  absent > X min`, `% symbols volume zero > 5 %`).
- Pas de métrique de **drift ML** (distribution `predicted_proba` jour-à-jour).
- Pas de métrique **drift sentiment** (IC vs forward returns).
- Pas de **dashboard Supervision Ops Linux** (Windows-only).
- Pas de **comparaison automatique simulate vs live** (mode shadow).

### Documentation

**Forces** : `doc/*.md` très complète (>5000 lignes au total), `README.md` riche,
`DOC_TECHNIQUE.md` et `DOC_FONCTIONNELLE.md` présents, runbooks par module.

**Manques transverses** :
- Pas de section globale "Limitations Alpaca free / IEX et leur impact concret".
- Pas de **runbook réconciliation** `MANUAL_REVIEW` / `BLOCKED`.
- Pas de **runbook incident provider** (Alpaca / Finnhub down 30 min).
- Pas de **kill switch d'urgence** documenté.
- Pas de section **"comment migrer un format pickle vers natif"** ML.
- Pas de section **sécurité IHM** (auth, exposition réseau).
- Pas de **guide "ajouter une nouvelle table"** (template Alembic).
- Pas de **policy de prix** explicite (`split_adjusted` choisi et pourquoi —
  proposé à matérialiser dans `README.md`).
- Pas de **mapping table ↔ producteur ↔ consommateurs** (matrice impact analysis).
- Pas de **doc `core/` et `common/`** (modules transverses non documentés).

---

## 10. Vision cible

À horizon 6-12 mois, Alpha Trade pourrait converger vers :

- **Schéma SQL versionné Alembic**, contraintes `CHECK` strictes, rollback testé.
- **Couches découplées via Protocols** ; tests d'intégration MySQL en CI ;
  `import-linter` enforced.
- **Cross-check systématique** Alpaca ↔ Stooq / Yahoo / EDGAR avec audit dédié.
- **Sécurité opérationnelle live** durcie : confirmations cryptographiques,
  vault secrets, kill switch, leader election watcher.
- **ML auditable** : artefacts en formats natifs, fingerprint features,
  quarantaine champion, backup automatisé, persistance `metrics.json` DB.
- **Backtest réaliste** : costs/slippage par défaut, validation hold-out,
  comparaison simulate vs live (shadow mode).
- **Observabilité** : dashboard fraîcheur data, alertes automatiques, métriques
  de drift ML / sentiment, heartbeat services persistants.
- **Documentation cible** : runbooks complets, guides "ajouter table / backend /
  filtre / nouvelle source", policy de prix explicite.

L'infrastructure actuelle est **solide et déjà très structurée**. Les
recommandations de cet audit visent moins à corriger des erreurs critiques qu'à
**durcir la robustesse**, **réduire la dette d'architecture**, **instrumenter
les zones d'ombre** (notamment le biais IEX) et **préparer la résilience
opérationnelle** d'une exploitation swing cash quotidienne.

La réinitialisation prévue de la base est une **opportunité unique** d'introduire
plusieurs des recommandations structurelles (schéma SQL durci, audit dédié,
nouvelles colonnes de provenance) sans coût de migration de données.

---

## 11. Clôture refactor (Phases 1 → 7)

> Synthèse de l'état après exécution complète de `prompt/refactor/plan.md`.

### Items traités (✅ corrigés)

- **Phase 1** : Alembic baseline + migrations 0002 → 0019, equity fallback fatal,
  confirmation live renforcée, secrets DB hors `config.yaml`, lock SQL watcher,
  heartbeat persistant, `schema_version` partout, compteurs IEX, `feed=iex`
  validé, helper `service/_http_retry.py`, cache Finnhub 7j, doc transverse.
- **Phase 2** : Protocols `core/interfaces.py`, `core/conviction.py`,
  `core/filter_profiles.py`, découpage `common/utils.py`, doc `core_common.md`,
  façade `database/repositories/`, pool DB élargi, TLS optionnel,
  testcontainers MySQL, migration clients service vers `_http_retry`.
- **Phase 3** : exit ≠ 0 sur ratio import, `pandas_market_calendars`, audits
  dédiés quotes/earnings, `market_cap_refreshed_at` consommé,
  `chunk_failures`, `rejected_by_filter`, `core/filter_profiles.py` partagé,
  `spread_bps` adapté IEX, ranking selector découpé.
- **Phase 4** : FinBERT fingerprinté, `signal_aggregator` migré
  `core.conviction`, formats natifs LightGBM/CatBoost, fingerprint features
  SHA256, walk-forward par défaut, quarantaine champion, `metrics.json` BLOB
  DB, cache modèles predictor, garde-fou anti-leak, découpage `trainer.py`,
  `run_summary` ML standardisé.
- **Phase 5** : `account_equity_breakdown`, fusion conviction unifiée,
  pondérations 40/60 documentées, découpage `executor.py`, runbook
  `MANUAL_REVIEW`/`BLOCKED`, kill switch global (`execution_kill_switch_runs`),
  `idempotency_key` documenté + scopé account, audit
  `corporate_actions_audit_runs`, cross-check Yahoo dividendes.
- **Phase 6** : `--commission-bps`/`--slippage-bps`, `total_return_with_dividends`,
  validation hold-out, profils CLI consolidés, `signal_replay` migré
  `core.conviction`, atexit IHM, rotation artefacts, audit shell quoting,
  cache `@st.cache_data`, test contractuel IHM↔CLI, auth IHM optionnelle,
  doc sécurité IHM, leader election watcher, allowlist PowerShell durcie.
- **Phase 7** : `import-linter` (warn-only), calibration empirique poids
  (table `weights_calibration_runs`), Stooq cross-check
  (`dataIntegrityEngine.cross_check_stooq` + `service/stooq/`), drift ML
  monitoring (`modelFactory.drift_monitor` + table `ml_drift_runs`), endpoint
  `/metrics` Prometheus minimal (`core/metrics.py`), 4 docs cibles
  (runbook provider, runbook réconciliation, guide ajout table, matrice
  data lineage, observability), shadow compare offline
  (`risk_management.shadow_compare` + table `shadow_drift_runs`),
  documentation `doc/observability.md`.

### Items reportés au backlog Long terme

Voir [`backlog_long_terme.md`](backlog_long_terme.md) — entrées L1 → L11 :

| ID | Item | Justification report |
|---|---|---|
| L1 | SEC EDGAR 8-K | Volumétrie + IC à mesurer |
| L2 | Shadow live continu | Daemon + double broker |
| L3 | Grafana / Alertmanager complet | Déploiement infra |
| L4 | Fine-tune LoRA FinBERT | Dataset + GPU |
| L5 | XGBoost 3e challenger | ROI marginal |
| L6 | `ProcessRegistry` IHM DB-backed | Single-user actuel |
| L7 | Hors `vectorbt` | Pas de besoin immédiat |
| L8 | Vault complet | Single-host Windows |
| L9 | Polygon / Tiingo NBBO | Quotas free trop stricts |
| L10 | Découpage `pages/pipeline.py` | Risque IHM prod |
| L11 | `import-linter` strict (vs warn) | Triage requis |

### Métrique de clôture

- Audits modulaires (14) : **100 % traités** ou item explicitement reporté.
- Migrations Alembic : `0001` → `0022` (Phase 7 inclus).
- Nouvelles tables transverses : `weights_calibration_runs` *(7.2)*,
  `ml_drift_runs` *(7.4)*, `shadow_drift_runs` *(7.7)*.
- Nouveaux modules transverses : `core/metrics.py` *(7.5)*,
  `service/stooq/` *(7.3)*, `dataIntegrityEngine/cross_check_stooq.py`
  *(7.3)*, `backtesting/weights_calibration.py` *(7.2)*,
  `modelFactory/drift_monitor.py` *(7.4)*,
  `risk_management/shadow_compare.py` *(7.7)*.
- Nouveaux docs : `doc/observability.md`, `doc/runbook_provider_incident.md`,
  `doc/runbook_reconciliation.md`, `doc/guide_add_new_table.md`,
  `doc/data_lineage_matrix.md`.

> Le refactor "Audit-driven" est **clos**. La poursuite passe par
> `backlog_long_terme.md` (promotion item-par-item selon trigger métier).

