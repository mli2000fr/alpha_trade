# 08 — Plan d'Action par Sprints — Alpha Trade

> **Date** : mai 2026 | Objectif : amener l'application vers un niveau quasi-pro 8.5+/10

---

## Vue d'ensemble

| Sprint | Objectif principal | Priorité | Durée estimée | Modules |
|---|---|---|---|---|
| S1 | Corrections docs + config P1 (quick wins) | ✅ Immédiat | 1–2 jours | doc, config, tests |
| S2 | Corrections techniques P1/P2 | ✅ Critique | 3–5 jours | DB, modelFactory, execution, config |
| S3 | Améliorations opérationnelles P2 | 🔵 Important | 5–7 jours | backtesting, observabilité, sécurité |
| S4 | Qualité avancée + analytics P3 | 🟢 Perfectionnement | 5–7 jours | backtesting, IHM, ML, walk-forward |
| S5 | Pro-grade : monitoring + orchestration | 🟡 Long terme | 10–15 jours | infra, ops, ML governance |

---

## Sprint S1 — Quick Wins : Corrections docs et config P1

**Objectif** : Éliminer les incohérences P1 documentaires et de configuration sans toucher au code algorithme.  
**Durée estimée** : 1–2 jours  
**Modules impactés** : `doc/`, `config/`  
**Anomalies traitées** : A-001, A-002, A-004, A-005, A-016, A-018, A-023, A-026

### Tâches détaillées

**T1.1** — Corriger `config/capital_presets.yaml` preset `capital_0_2000_eur`
```yaml
# Avant :
risk_max_positions: 10
risk_min_position_notional: 150.0
# Après :
risk_max_positions: 3
risk_min_position_notional: 500.0
```
**Fichiers** : `config/capital_presets.yaml:15-19`

**T1.2** — Régénérer `doc/data_lineage_matrix.md` via `scripts/generate_data_lineage.py`
- Vérifier que `execution_orders` → `execution_order_requests` + `execution_broker_orders`
- Vérifier que `execution_audit_events` → `execution_events`
- Activer vérification en CI : `python scripts/generate_data_lineage.py --check`

**T1.3** — Corriger `doc/DOC_TECHNIQUE.md §9 point 14`
```markdown
# Avant :
→ ✅ Implémenté : module `backtesting/` (vectorbt)
# Après :
→ ✅ Implémenté : module `backtesting/` (simulateur custom PIT — aucune dépendance vectorbt)
```

**T1.4** — Corriger `doc/DOC_FONCTIONNELLE.md §1.3` étape 1
```markdown
# Avant :
1. **Ingestion** des données de marché depuis Alpaca (barres OHLCV journalières)
# Après :
1. **Ingestion** des barres OHLCV journalières depuis EODHD (provider primaire, `bars_provider=eodhd`) 
   ou Alpaca IEX (mode rétrocompatibilité, `bars_provider=alpaca`)
```

**T1.5** — Corriger `doc/DOC_FONCTIONNELLE.md §2.3` seuils AlphaScanner
- `beta_126 >= 1.0` → `beta_126 >= 0.8` (valeur dans le profil strict canonique)
- `max_spread_bps <= 25 bps` → `max_spread_bps <= 40 bps` (valeur dans le profil strict canonique)

**T1.6** — Documenter le switch provider CA dans `doc/DOC_FONCTIONNELLE.md §2.9`
```markdown
**Provider corporate actions** : EODHD si `market_data.bars_provider = eodhd` 
(factory `build_corporate_action_provider` sélectionne `EodhdCorporateActionProvider`), 
Alpaca sinon. Cette cohérence garantit que les CA et les barres OHLCV sont issues 
du même fournisseur.
```

**T1.7** — Ajouter commentaire YAML pour PDT rule sur comptes cash
```yaml
execution_pdt_rule: "off"  # PDT rule N/A sur compte cash (règle margin uniquement)
```

**T1.8** — Documenter `test_import_alpaca_bar_noop.py` dans `doc/dataIntegrityEngine.md`

### Tests à ajouter/exécuter

| Test | Type | Priorité |
|---|---|---|
| `test_capital_preset_risk_overrides.py` — ajout assertion `max_positions × notional ≤ 0.95 × equity` | Unitaire config | P1 |
| `test_data_lineage_autogen.py` — activer en CI | Non-régression doc | P1 |
| `test_doc_provider_alignment.py` — ajout patterns "vectorbt", "beta_126 >= 1.0", "spread_bps <= 25" | Non-régression doc | P1 |
| `test_strict_filter_profiles.py` — vérifier cohérence STRICT_SWING_CASH_FILTERS vs doc | Unitaire | P2 |

### Critères d'acceptation

- ✅ `test_capital_preset_risk_overrides.py` passe sur `capital_0_2000_eur` avec max_positions=3
- ✅ `test_data_lineage_autogen.py` vert en CI sans erreur de noms de tables
- ✅ `test_doc_provider_alignment.py` vert (aucun pattern obsolète détecté)
- ✅ Aucune mention "vectorbt" dans `DOC_TECHNIQUE.md`

### Gain attendu sur les notes

| Module | Avant | Après |
|---|---|---|
| Documentation | 8.0 | 8.5 |
| Configuration | 7.0 | 7.5 |
| corporate_actions | 7.0 | 7.5 |

---

## Sprint S2 — Corrections techniques P1/P2

**Objectif** : Résoudre les problèmes techniques maineurs qui impactent la fiabilité en production.  
**Durée estimée** : 3–5 jours  
**Modules impactés** : `database/`, `modelFactory/`, `execution_engine/`, `config/`  
**Anomalies traitées** : A-003, A-006, A-007, A-009, A-012, A-017

### Tâches détaillées

**T2.1** — Migration Alembic `0029_model_predictions_governance`
```sql
ALTER TABLE model_predictions 
  ADD COLUMN selected_model VARCHAR(32) NULL COMMENT 'Backend ML servi : lstm_attention | lightgbm | catboost | global_model',
  ADD COLUMN decision_threshold FLOAT NULL COMMENT 'Seuil de décision optimisé',
  ADD COLUMN calibration_method VARCHAR(16) NULL COMMENT 'Méthode de calibration : none | platt',
  ADD COLUMN signal_label VARCHAR(16) NULL COMMENT 'Label textuel du signal ML';
```
**Fichiers** : `alembic/versions/0029_model_predictions_governance.py` (nouveau)

**T2.2** — Persister `selected_model` dans `predictor.py`
```python
# modelFactory/predictor.py — après calcul de predicted_proba
if persist:
    repo.insert_prediction(
        symbol=symbol,
        prediction_date=prediction_date,
        predicted_proba=predicted_proba,
        predicted_class=predicted_class,
        run_id=run_id,
        selected_model=artifact_routes.selected_model,  # NEW
        decision_threshold=decision_threshold,           # NEW
        calibration_method=calibration_method,           # NEW
    )
```
**Fichiers** : `modelFactory/predictor.py`, `database/ml_io.py`

**T2.3** — Corriger presets capital PDT rule (margin)
```yaml
# capital_25001_50000, capital_50001_100000, capital_100001_plus
execution_pdt_rule: "auto"  # Corrigé : comptes margin avec suivi PDT auto si equity < 25k$
```
**Fichiers** : `config/capital_presets.yaml:230`, `:280`, `:330`

**T2.4** — Corriger `selector_min_close` preset `capital_0_5000`
```yaml
selector_min_close: 10.0  # Corrigé : aligné profil strict canonique (was 5.0)
```
**Fichiers** : `config/capital_presets.yaml:97`

**T2.5** — Vérifier et ajouter contrainte unicité `model_predictions`
```sql
-- Vérifier si la contrainte existe déjà
SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS 
WHERE TABLE_NAME='model_predictions' AND CONSTRAINT_TYPE='UNIQUE';
-- Si absente :
ALTER TABLE model_predictions ADD UNIQUE INDEX uq_prediction_symbol_date (symbol, prediction_date);
```

**T2.6** — Activer SSL MySQL (optionnel via env var)
```python
# database/connection.py
ssl_args = {}
if os.getenv("DB_SSL_CA"):
    ssl_args = {"ssl_ca": os.getenv("DB_SSL_CA")}
engine = create_engine(url, connect_args=ssl_args, ...)
```
**Fichiers** : `database/connection.py`, `doc/DOC_TECHNIQUE.md §4.1`

**T2.7** — Augmenter fill_timeout et documenter le comportement gap
```python
# execution_engine/config.py
fill_timeout_seconds: int = 180  # paper (was 120)
# live : 300 secondes — configurable via preset
```
**Fichiers** : `execution_engine/config.py:85`

### Tests à ajouter

| Test | Type | Priorité |
|---|---|---|
| `test_model_factory_db_registry.py` — assertion `selected_model IS NOT NULL` | Intégration | P1 |
| `test_model_factory_predictor.py` — passage des champs governance à insert | Unitaire | P1 |
| `test_execution_config.py` — PDT auto sur margin quand equity < 25k$ | Unitaire | P2 |
| `test_capital_preset_risk_overrides.py` — regression min_close ≥ 10.0 | Unitaire | P2 |
| `test_connection.py` — SSL activé si DB_SSL_CA définie | Unitaire | P2 |
| `test_execution_engine_executor.py` — fill_timeout gap scenario | Unitaire | P2 |

### Critères d'acceptation

- ✅ `model_predictions.selected_model` non-NULL après un run de predict
- ✅ `test_capital_preset_risk_overrides.py` vert avec PDT auto sur presets margin
- ✅ `selector_min_close ≥ 10.0` pour tous les presets (ou exception documentée)
- ✅ Migration 0029 appliquée sans erreur sur base de test SQLite

### Gain attendu sur les notes

| Module | Avant | Après |
|---|---|---|
| modelFactory | 6.5 | 7.5 |
| database | 7.0 | 7.5 |
| Configuration | 7.5 | 8.0 |
| Sécurité | 7.0 | 7.5 |

---

## Sprint S3 — Améliorations opérationnelles P2

**Objectif** : Renforcer la supervision, l'alerting, les performances backtesting et la robustesse.  
**Durée estimée** : 5–7 jours  
**Modules impactés** : `backtesting/`, `ihm/`, `common/`, `execution_engine/`  
**Anomalies traitées** : A-008, A-010, A-011, A-013, A-014, A-015, A-025, A-027

### Tâches détaillées

**T3.1** — Brancher `ParquetCache` dans la CLI backtesting
```bash
python -m backtesting run --start ... --end ... --use-cache   # Nouveau flag
```
- Invalidation automatique si `dataset_hash` change
- Cache stocké dans `artifacts/backtest_cache/`

**T3.2** — Exposer `bootstrap_trades()` et `parameter_sensitivity()` en CLI
```bash
python -m backtesting run --bootstrap-samples 1000 --sensitivity-analysis
```

**T3.3** — Alerting automatique email sur circuit_breaker + kill_switch
```python
# risk_management/circuit_breaker.py — après déclenchement
from ihm.services.email_notifier import send_notification
send_notification(event="circuit_breaker_fired", payload={...})
```
**Fichiers** : `risk_management/circuit_breaker.py`, `execution_engine/executor.py` (kill switch)

**T3.4** — Alerting IHM quand réconciliation contient des diffs depuis > 24h
```python
# ihm/pages/execution.py — section reconciliation
if unresolved_diffs and max_diff_age > timedelta(hours=24):
    st.warning("⚠️ Diffs de réconciliation non résolus depuis plus de 24h")
```

**T3.5** — Alerte TTL market_cap dans l'IHM
```python
# ihm/pages/screening.py
stale_pct = compute_stale_market_cap_pct(cutoff_days=45)
if stale_pct > 0.20:
    st.warning(f"⚠️ {stale_pct:.0%} des symboles ont un market_cap > 45j")
```

**T3.6** — TimedRotatingFileHandler + compression gzip
```python
# common/utils.py
from logging.handlers import TimedRotatingFileHandler
handler = TimedRotatingFileHandler(
    "alpha_trade.log", when="midnight", backupCount=14, encoding="utf-8"
)
handler.suffix = "%Y%m%d.gz"
```

**T3.7** — Ajouter bornes business sur les poids calibrés walk-forward
```python
# backtesting/walk_forward.py — après calibration
assert 0.05 <= calibrated_sentiment_weight <= 0.40, f"Poids sentiment hors bornes: {calibrated_sentiment_weight}"
```

### Tests à ajouter

| Test | Type | Priorité |
|---|---|---|
| `test_backtesting.py` — pipeline avec ParquetCache activé | Intégration | P2 |
| `test_backtesting.py` — bootstrap_samples=100, assert len(metrics) == 100 | Unitaire | P2 |
| `test_ihm_notifications.py` — email déclenché sur circuit_breaker | Intégration | P2 |
| `test_execution_engine_reconciliation.py` — alerte si diff > 24h | Unitaire | P2 |
| `test_alpha_scanner.py` — filtre market_cap TTL expiré | Unitaire | P2 |
| `test_common_utils.py` — TimedRotatingFileHandler avec compress | Unitaire | P3 |
| `test_weights_calibration.py` — bornes business poids [0.05, 0.40] | Unitaire | P3 |

### Critères d'acceptation

- ✅ `python -m backtesting run --use-cache` fonctionne et accélère les reruns
- ✅ Email envoyé (mock SMTP) quand circuit breaker déclenché
- ✅ Page Execution IHM affiche warning si diffs > 24h
- ✅ Walk-forward ne produit pas de poids hors bornes sans lever d'exception

### Gain attendu sur les notes

| Module | Avant | Après |
|---|---|---|
| backtesting | 7.0 | 7.5 |
| observabilité | 7.0 | 7.5 |
| IHM | 7.5 | 8.0 |

---

## Sprint S4 — Qualité avancée + analytics

**Objectif** : Enrichir les capacités analytiques, le PnL IHM et étendre le walk-forward.  
**Durée estimée** : 5–7 jours  
**Modules impactés** : `backtesting/`, `ihm/`, `modelFactory/`, `doc/`  
**Anomalies traitées** : A-019, A-020, A-021, A-022, A-024

### Tâches détaillées

**T4.1** — Widget PnL quotidien dans la page Overview
```python
# ihm/pages/overview.py
pnl_today = compute_daily_pnl(positions_df, close_prices_df, cash_ledger_df)
st.metric("PnL aujourd'hui", f"${pnl_today:,.0f}", delta=f"{pnl_pct:.1%}")
```

**T4.2** — Étendre walk-forward aux paramètres risk
```python
# backtesting/walk_forward.py — nouvelle fonction
def walk_forward_risk_params(
    start: date, end: date,
    param_grid: dict,  # ex. {"atr_period": [14, 20], "correlation_threshold": [0.75, 0.80, 0.85]}
    ...
) -> dict:
```

**T4.3** — Documenter utilisation Stooq sans clé API
```yaml
# config.yaml
# market_regimes.macro_provider: stooq
# Stooq est gratuit sans clé. STOOQ_API_KEY n'est PAS requis pour l'usage standard.
# Uniquement si Stooq modifie son API vers authentification.
```

**T4.4** — Documenter quota EODHD consommé par composant
```markdown
# doc/dataIntegrityEngine.md §3.2
| Appel | Calls/jour | Notes |
|---|---|---|
| EodhdMacroProvider VIX | 2–3 | Par run pipeline |
| Bulk EOD | 1 | ~5k symboles US |
| Per-symbol fallback | N(failures) | Si bulk fail |
| Corporate actions EODHD | ≤ 10 | Si bars_provider=eodhd |
```

**T4.5** — Archiver les prompts de sprints précédents
```
prompt/archive/         # créer, déplacer prompt/tod/, prompt/iex/, prompt/execution/ etc.
prompt/tod1/            # conserver les livrables d'audit courant
```

### Tests à ajouter

| Test | Type | Priorité |
|---|---|---|
| `test_pages_overview.py` — widget PnL présent et non-None | E2E IHM | P3 |
| `test_weights_calibration.py` — walk_forward_risk_params grid | Intégration | P3 |
| `test_macro_providers.py` — Stooq sans clé | Unitaire | P3 |

### Critères d'acceptation

- ✅ Page Overview affiche PnL quotidien (même si 0 € en paper)
- ✅ `walk_forward_risk_params` fonctionne sans erreur sur dataset test
- ✅ Aucune référence à STOOQ_API_KEY comme "requise" dans la doc

---

## Sprint S5 — Pro-grade : monitoring + orchestration + gouvernance ML

**Objectif** : Atteindre un niveau quasi-institutionnel avec monitoring live, orchestration pipeline, gouvernance ML complète.  
**Durée estimée** : 10–15 jours  
**Modules impactés** : infra, `modelFactory/`, `database/`, `ihm/`

### Tâches détaillées

**T5.1** — Intégrer Prometheus metrics pour le pipeline
```python
# common/metrics.py
from prometheus_client import Counter, Histogram, Gauge
pipeline_steps_total = Counter('alpha_pipeline_steps', 'Pipeline steps', ['step', 'status'])
candidates_gauge = Gauge('alpha_candidates_count', 'Candidats sélectionnés après AlphaScanner')
```

**T5.2** — Orchestrateur pipeline (Prefect ou équivalent léger)
```python
# flows/daily_pipeline.py
@flow(name="alpha_trade_daily")
def daily_pipeline(date: date, account_id: str):
    run_import_bars(date)
    run_sanitizer(date)
    run_screener(date)
    ...
```

**T5.3** — Backup automatique des artefacts ML
```bash
# scripts/backup_ml_artifacts.sh
rsync -avz artifacts/models/ backup:/alpha_trade/models/
```

**T5.4** — Sauvegarde DB automatique quotidienne
```bash
mysqldump alpha_trade | gzip > backups/alpha_trade_$(date +%Y%m%d).sql.gz
```

### Tests à ajouter

| Test | Type | Priorité |
|---|---|---|
| `test_pipeline_flow.py` — pipeline Prefect end-to-end sur dataset mock | E2E | P2 |
| `test_ml_artifacts_backup.py` — backup déclenché après train | Intégration | P2 |
| `test_prometheus_metrics.py` — métriques exposées et non-None | Unitaire | P3 |

---

## Fin du plan — Sections requises

### Ce qu'il restera éventuellement à faire pour atteindre un vrai 10/10 pro-grade

1. **Containerisation** : Docker + docker-compose pour MySQL + Python + Streamlit
2. **Tests de charge** : simulation 1 000 symboles, 5 ans de données, latence acceptable
3. **SLA et disaster recovery** : RTO/RPO formalisés, procédure de restauration testée
4. **Mutation testing** : ≥ 70% mutation score sur les modules critiques (actuellement non mesuré)
5. **Multi-broker** : abstraction BrokerPort complète pour supporter IBKR en plus d'Alpaca
6. **Short selling** : extension stratégie pour comptes avec accès au short
7. **Notifications WebSocket** : alerting temps réel (Slack, Teams, SMS) sans polling IHM
8. **Certification formelle** : TLAPS proofs sur les invariants critiques (circuit breaker, idempotence) — fichiers déjà présents dans `formal/` et `doc/formal_verification.md`

---

### À partir de quel sprint l'application est suffisamment robuste pour swing trading réel discipliné

**À partir de la fin du Sprint S2** (corrections techniques P1/P2 appliquées) :
- Gouvernance ML en DB opérationnelle
- PDT rule correcte sur les comptes margin
- `min_close ≥ 10$` sur tous les presets
- SSL DB activé

**Condition additionnelle** : que l'opérateur ait :
1. Complété le backfill PIT sur ≥ 1 an de données
2. Exécuté au moins 3 mois de paper trading pour valider le pipeline
3. Activé le trailing stop ATR en paper et validé son comportement
4. Configuré les notifications email sur circuit_breaker

**Niveau de maturité fin S2** : ~7.5/10 — suffisant pour un swing trading réel discipliné avec supervision quotidienne active.

**Niveau de maturité fin S3** : ~8.0/10 — confortable pour swing trading régulier avec alerting automatique.

