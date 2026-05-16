# 08 — Plan d'Action par Sprints — Alpha Trade

> **Date** : mai 2026 | Objectif : amener l'application vers un niveau quasi-pro 8.5+/10

---

## Vue d'ensemble

| Sprint | Objectif principal | Priorité | Durée estimée | Modules | Statut |
|---|---|---|---|---|---|
| S1 | Corrections docs + config P1 (quick wins) | ✅ Immédiat | 1–2 jours | doc, config, tests | ✅ **LIVRÉ** |
| S2 | Corrections techniques P2 | ✅ Critique | 2–3 jours | execution, config | ✅ **LIVRÉ** |
| S3 | Améliorations opérationnelles P2 | 🔵 Important | 5–7 jours | backtesting, observabilité, sécurité | 🔴 À faire |
| S4 | Qualité avancée + analytics P3 | 🟢 Perfectionnement | 5–7 jours | backtesting, IHM, ML, walk-forward | 🔴 À faire |
| S5 | Pro-grade : monitoring + orchestration | 🟡 Long terme | 10–15 jours | infra, ops, ML governance | 🔴 À faire |

---

## Sprint S1 — Quick Wins : Corrections docs et config P1 ✅ **LIVRÉ**

**Objectif** : Éliminer les incohérences P1 documentaires et de configuration sans toucher au code algorithme.  
**Durée estimée** : 1–2 jours | **Durée réelle** : ~1 jour  
**Modules impactés** : `doc/`, `config/`, `backtesting/cli/`, `tests/`  
**Anomalies clôturées** : A-001 ✅, A-002 ✅, A-004-résidu ✅, A-016 ✅

> ✅ **Toutes les anomalies S1 résolues** :
> - A-001 ✅ (risk_max_positions: 3, min_notional: 500 USD sur capital_0_2000_eur)
> - A-002 ✅ (LINEAGE_SPEC corrigé, data_lineage_matrix.md régénéré, CI check vert)
> - A-004-résidu ✅ (argparse description backtesting/cli/_impl.py:67 corrigée)
> - A-004 ✅ (DOC_TECHNIQUE §9 — déjà corrigé avant S1, entièrement clos)
> - A-005 ✅ (provider CA — déjà corrigé avant S1)
> - A-016 ✅ (commentaire PDT rule ajouté sur 4 presets cash)
> - A-018 ✅ (DOC_FONCTIONNELLE §1.3 — déjà corrigé avant S1)

### Tâches livrées

**T1.1** ✅ — `config/capital_presets.yaml` preset `capital_0_2000_eur` corrigé
```yaml
risk_max_positions: 3                     # 3 lignes ≈ 600-700 € chacune — A-001 fix
risk_min_position_notional: 500.0        # ticket mini USD — A-001 fix
```

**T1.2** ✅ — `scripts/generate_data_lineage.py` LINEAGE_SPEC + PROVIDER_SPEC corrigés, MD régénéré
- `execution_orders` → `execution_order_requests` + `execution_broker_orders`
- `execution_audit_events` → `execution_events`
- `python scripts/generate_data_lineage.py --check` → exit 0 ✅

**T1.3** ✅ — `backtesting/cli/_impl.py:67` description argparse corrigée
```python
description="Backtest intégré Alpha Trade (simulateur custom PIT)"
```

**T1.4** ✅ — Commentaire PDT rule ajouté sur 4 presets cash dans `config/capital_presets.yaml`

### Tests ajoutés et résultats

| Test | Type | Résultat |
|---|---|---|
| `test_positions_notional_solvency` (nouveau) | Unitaire config | ✅ Pass |
| `test_micro_account_max_positions_coherent` (nouveau) | Unitaire config | ✅ Pass |
| `test_micro_account_min_notional_viable` (nouveau) | Unitaire config | ✅ Pass |
| `test_positions_increase_with_account_size` (nouveau) | Unitaire config | ✅ Pass |
| `test_cash_presets_have_pdt_off` (nouveau) | Unitaire config | ✅ Pass |
| `test_capital_preset_risk_overrides.py` (13 tests) | Régression | ✅ 13/13 Pass |
| `test_data_lineage_autogen.py` (7 tests) | Non-régression doc | ✅ 7/7 Pass |
| Ensemble filtré "lineage or preset or capital" (80 tests) | Régression globale | ✅ 80 Pass, 0 Fail |

### Gain réalisé sur les notes

| Module | Avant S1 | Après S1 |
|---|---|---|
| Configuration | 7.0 | **7.5** |
| Documentation (lineage matrix) | 8.5 | **9.0** |
| Backtesting CLI | — | résidu vectorbt éliminé ✅ |

---

## Sprint S2 — Corrections techniques P1/P2 ✅ **LIVRÉ**

**Objectif** : Résoudre les problèmes techniques mineurs qui impactent la fiabilité en production.  
**Durée estimée** : 2–3 jours *(réduit — plusieurs tâches déjà résolues)* | **Durée réelle** : ~1 jour  
**Modules impactés** : `config/`, `execution_engine/`  
**Anomalies clôturées** : A-006 ✅, A-007 ✅, A-017 ✅

> ✅ **Toutes les anomalies S2 résolues** :
> - A-006 ✅ (`execution_pdt_rule: "auto"` sur 3 presets margin — capital_25001_50000, capital_50001_100000, capital_100001_plus)
> - A-007 ✅ (`selector_min_close: 10.0` sur capital_0_5000, capital_5001_10000, capital_10001_25000)
> - A-017 ✅ (`fill_timeout_seconds: 180` dans execution_engine/config.py)

### Tâches livrées

**T2.1** ✅ — PDT rule `"auto"` sur presets margin (`config/capital_presets.yaml`)
```yaml
# capital_25001_50000, capital_50001_100000, capital_100001_plus
execution_pdt_rule: "auto"  # A-006 fix : PDT auto sur compte margin — bloque le 4e day-trade si equity < 25k$
```

**T2.2** ✅ — `selector_min_close: 10.0` uniformisé sur tous les presets (`config/capital_presets.yaml`)
```yaml
# capital_0_5000 (was 5.0), capital_5001_10000 (was 7.0), capital_10001_25000 (was 8.0)
selector_min_close: 10.0  # A-007 fix : aligné STRICT_SWING_CASH_FILTERS.min_close=10.0
```

**T2.3** ✅ — `fill_timeout_seconds: 180` (`execution_engine/config.py:85`)
```python
fill_timeout_seconds: int = 180  # A-017 fix : paper (was 120) — live recommandé 300s
```

### Tests ajoutés et résultats

| Test | Type | Résultat |
|---|---|---|
| `test_margin_presets_have_pdt_auto` (nouveau) | Unitaire config | ✅ Pass |
| `test_all_presets_selector_min_close_gte_10` (nouveau) | Unitaire config | ✅ Pass |
| `test_pdt_auto_margin_equity_above_threshold_no_block` (nouveau) | Unitaire execution | ✅ Pass |
| `test_pdt_auto_margin_equity_below_threshold_blocks` (nouveau) | Unitaire execution | ✅ Pass |
| `test_pdt_auto_margin_equity_at_threshold_no_block` (nouveau) | Unitaire execution | ✅ Pass |
| `test_pdt_off_margin_never_blocks` (nouveau) | Unitaire execution | ✅ Pass |
| `test_pdt_cash_account_never_blocks` (nouveau) | Unitaire execution | ✅ Pass |
| `test_fill_timeout_default_is_180_seconds` (nouveau) | Unitaire execution | ✅ Pass |
| `test_fill_timeout_configurable_for_live` (nouveau) | Unitaire execution | ✅ Pass |
| `test_fill_timeout_must_be_positive` (nouveau) | Unitaire execution | ✅ Pass |
| Suite élargie S2 (86 tests) | Régression globale | ✅ 86 Pass, 0 Fail |

### Gain réalisé sur les notes

| Module | Avant S2 | Après S2 |
|---|---|---|
| Configuration | 7.5 | **8.0** |
| execution_engine | 7.5 | **8.0** |
| **Note globale** | 7.5 | **8.0** |

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

