# 02 — Scorecards détaillées module par module

Pour chaque module : note /10, résumé, points forts, faiblesses, risques,
gap vers 10/10. Sauf mention contraire, les chemins sont relatifs au
dépôt.

---

## 1. Documentation `doc/` — **7.5 / 10**

**Résumé** : ~60 fichiers (`DOC_FONCTIONNELLE`, `DOC_TECHNIQUE`,
`dataIntegrityEngine`, `corporate_actions`, `risk_management`,
`execution_engine`, `backtesting`, `ihm`, runbooks, etc.) + `INDEX.md`
généré automatiquement (`scripts/generate_doc_index.py`). Le bandeau
"primary_provider: eodhd" est cohérent avec `config.yaml`.

**Points forts** :
- Index `doc/INDEX.md` cherchable.
- Bandeaux et notes d'audit datées (`doc/audit_alignment_tod2.md`).
- Runbooks opérationnels (`runbook_provider_incident.md`,
  `runbook_reconciliation.md`, `runbook_24_7.md`, `sandbox_health_runbook.md`).
- `EODHD_vs_Alpaca.md` documente le choix de provider.

**Faiblesses** :
- Hétérogénéité de fraîcheur : plusieurs docs renvoient à des sprints
  passés (S25/S26/S27/S30) sans note unique des "conventions en vigueur".
- Pas d'arbre décisionnel unifié "quel preset choisir, dans quel cas".
- Certaines docs spéculatives (`async_db_poc.md`, `formal_verification.md`)
  peuvent semer le doute sur ce qui est *réellement* en production.

**Risques** : opérateur reprenant le projet lit des docs encore non
purgées et applique une convention obsolète.

**Pour 10/10** : index "conventions canoniques en vigueur" (1 page),
purger les POCs, ajouter un changelog `doc/CHANGELOG.md`.

---

## 2. Configuration — **7.5 / 10**

`config.yaml`, `config/capital_presets.yaml`, `pyproject.toml`,
`pytest.ini`, `mypy.ini`.

**Points forts** :
- Aucun secret littéral toléré (`alpaca.accounts[*].api_key: "${VAR}"`,
  scanner `core.secrets.scan_yaml_for_literal_secrets`, test
  `tests/test_config_no_literal_secrets.py`).
- Schémas validés (`tests/test_config_yaml_schema.py`,
  `tests/test_capital_presets.py`).
- Conventions explicites en commentaires (Sprint S5/A-013 sur secrets,
  Sprint S26 sur micro-compte, Sprint S30 sur market-aware).

**Faiblesses** :
- `risk_per_trade_pct` agressif sur micro-compte (cf. A-001).
- `risk_enable_kelly: false` partout (cf. A-006).
- `macro_provider: eodhd` impose le quota EODHD pour VIX/yields (A-007).
- Pas de validation cross-preset garantissant la monotonie (concentration
  décroissante quand equity ↑) ; un test existe partiellement.

**Pour 10/10** : ajouter tests propriété de monotonie sur toutes les clés
risk/selector ; ajouter `config_schema_version` ; valider la cohérence
`execution_account_type` ↔ `execution_pdt_rule`.

---

## 3. `dataIntegrityEngine/` — **8.0 / 10**

**Résumé** : ingestion barres (Alpaca/EODHD), nettoyage daily, sync
quotes/earnings, métadonnées, cross-check Stooq.

**Points forts** :
- Switch provider piloté par `config.yaml › market_data.bars_provider`
  (cf. `import_alpaca_bar.py:36 DATA_ADJUSTMENT='split'`,
  `import_eodhd_bar.py` shim + `dataIntegrityEngine/eodhd/orchestrator.py`).
- No-op contrôlé du provider inactif (test
  `tests/test_import_alpaca_bar_noop.py`).
- Audit run_summary : helpers `_emit_run_summary`, `attach_schema_version`,
  contrôle staleness (`_assess_staleness` lignes 78-99).
- Détection symbols zero volume 30d, stale quote, stale market cap.
- Cross-check Stooq optionnel pour OHLC.

**Faiblesses** :
- Encore beaucoup de `# noqa: F401` dans le shim EODHD (technique mais
  acceptable car maintenu pour patch tests).
- Pas encore d'observabilité unifiée "qualité d'ingestion" par provider.

**Risques** : incident provider EODHD non géré peut basculer
silencieusement sur Alpaca (`fallback_on_failure: true`) sans alerter.

**Pour 10/10** : alerting actif sur fallback provider, métriques d'écart
EODHD vs Alpaca/Stooq centralisées (déjà partiellement présent).

---

## 4. `database/` — **8.0 / 10**

`assets.py`, `audit_chain.py`, `connection.py`, `async_engine.py`,
`async_loaders.py`, `bar_metadata.py`, `cleaning_audits.py`,
`repositories/`, `sql/`, `stock_scores.py`, etc.

**Points forts** :
- Contraintes SQL bloquantes `chk_bars_adj` / `chk_daily_adj` (cf. README
  §0, `doc/database.md` §9).
- `account_id` propagé sur les périmètres critiques (cf. README §12.6).
- Migrations Alembic + test `tests/test_alembic_rollback.py`.
- Async engine pour les lectures lourdes.

**Faiblesses** : connexion uniquement MySQL (pas de profil Postgres) ;
pas de réplica lecture pour soulager l'IHM en prod.

**Pour 10/10** : tests de schéma drift, profil Postgres en CI, recipe
`pt_table_checksum` style.

---

## 5. `service/` — **7.5 / 10**

Providers : `alpaca/`, `eodhd/`, `finnhub/`, `ibkr/`, `stooq/`, `yahoo/`,
`market/`, `cache/`, `mock_broker.py`, `broker_failover.py`,
`_http_retry.py`, `_telemetry.py`, `alerting.py`.

**Points forts** :
- Failover broker (`broker_failover.py`, test `test_failover_alpaca_to_ibkr.py`).
- Cache disque EODHD + quota tracker, circuit breaker EODHD.
- Telemetry HTTP centralisée.
- IBKR adapter paper réel (`test_ibkr_adapter_paper.py`).

**Faiblesses** :
- IBKR adapter n'est pas (encore) le primaire ; doctrine de fallback
  Alpaca→IBKR à documenter plus clairement côté IHM.
- Pas d'abstraction unifiée "BrokerInterface contract" exposée à risk_management.

**Pour 10/10** : contrat broker formel testé par tests de contrat
(`test_broker_interface_contract.py` existe — étendre).

---

## 6. `screener/` — **7.5 / 10**

**Points forts** :
- Aligné `STRICT_SWING_CASH_FILTERS` (profil canonique).
- `run_summary` structuré : `persistence_status`, `chunk_failure_ratio`,
  `chunk_error_samples` (README §8.2).
- Diagnostics et recommandations (`backtesting/screener_diagnostics/`).

**Faiblesses** : encore couplé à liquidité IEX (A-004) → faux signaux
liquidité sur small caps.

**Pour 10/10** : volume "consolidé proxy" via EODHD bulk (en place côté
barres mais à propager au scoring liquidité).

---

## 7. `selector/` — **7.0 / 10**

**Points forts** : `alpha_scanner.py`, factors, ranking, regime filters,
explainability, ablation, profil strict.

**Faiblesses** :
- Filtres spread bps mesurés sur NBBO IEX biaisé.
- `selector_min_close=10$` sur micro-compte : trop restrictif (A-008).
- Sector neutrality test propriété existe (bien) mais pas de garde-fou
  "fail closed" si l'univers tombe sous N tickers.

**Pour 10/10** : seuil dynamique `min_universe_size` qui fait échouer le
sprint plutôt que produire 0 sélection silencieuse.

---

## 8. `event_sentiment/` — **6.5 / 10**

**Points forts** : pipeline 5 étapes (importe_news → relevance →
scoring std → contextuel → aggregation), provider switch EODHD/Alpaca/Finnhub,
trading calendar dédié, macro_rules.

**Faiblesses** :
- Ordre des étapes implicite et fragile (A-003).
- Coût/valeur du FinBERT contextuel à challenger empiriquement (calibration
  partielle via `backtesting/sentiment_calibration.py`).
- Pas de "fail closed" si relevance_score absent → fusion donne du poids à
  des news non pertinentes.

**Pour 10/10** : wrapper d'orchestration unique avec verrou d'ordre +
validation ex-post sentiment_attribution.

---

## 9. `modelFactory/` — **7.0 / 10**

**Points forts** : multi-baselines (LightGBM, CatBoost, LSTM, global,
tabular, cross-sectional), drift_monitor + drift_policy, champion
selection, auto rollback, reproducibility, calibration, dataset isolé.

**Faiblesses** :
- Surcomplexité possible ; trace de "ML uniquement si gate" (`ml_gate.py`
  côté risk) bien — mais pas de KPI public "edge ML net de frais".
- Pas de monitoring de **drift live** continu (drift_runs daily P2 seulement).

**Pour 10/10** : Sharpe attribution ML vs quant publié en IHM, drift
intra-day en mode paper.

---

## 10. `risk_management/` — **7.5 / 10**

**Points forts** : `position_sizer`, `kelly`, `correlation_filter`,
`circuit_breaker`, `ml_gate`, `regime_apply`, `portfolio_builder`,
`shadow_compare`, `audit.py`.

**Faiblesses** :
- `risk_enable_kelly: false` partout (A-006).
- Conviction weights fixes par défaut (0.4/0.6) — calibration empirique
  prévue Phase 7 mais pas encore tournée en boucle live.

**Pour 10/10** : calibration trimestrielle des poids conviction
(`test_quarterly_calibration_job.py` existe — formaliser le job en prod).

---

## 11. `execution_engine/` — **7.5 / 10**

**Points forts** : OMS/EMS modulaire (`executor`, `executor_phases`,
`state_machine`, `oco_manager`, `protection_*`, `tca`, `reconciliation`,
`preflight`, `orphan_adoption`, `broker_state_sync`,
`market_regime_preflight`), kill-switch (`cancel-all`), recette pré-live.

**Faiblesses** :
- Double point d'entrée (A-002).
- Pas de réconciliation J+1 vs statement broker exposée (A-005).
- TCA présent (`tca.py`, `test_tca.py`) mais pas de tableau de bord IHM
  consolidé "slippage moyen par compte / par tranche".

**Pour 10/10** : page IHM "TCA + réconciliation J+1" + alert sur
divergence > seuil.

---

## 12. `corporate_actions/` — **8.0 / 10**

**Points forts** : engine séparé sync/apply, processors dividend/split,
provider Alpaca + cross-check Yahoo, ledger cash idempotent, audit_runs,
docstring du `CorporateActionEngine` qui formalise la convention
split-only + dividendes-ledger (`engine.py:34-55`).

**Faiblesses** : provider EODHD CA disponible mais Alpaca reste primaire
— acceptable, mais à documenter si EODHD devient primaire CA.

**Pour 10/10** : test de propriété "MTM + cumulative ledger = total
return Bloomberg" sur N tickers de référence.

---

## 13. `backtesting/` — **7.5 / 10**

**Points forts** : parity, fidelity, walk-forward, fuzz, microstructure,
brinson-fachler, risk_overlay, execution replay, screener diagnostics
dédiés, statistical_validation.

**Faiblesses** :
- Parité backtest↔live testée par `test_parity_backtest_live.py` mais pas
  d'oracle quand sentiment + ML + macro activés simultanément (A-009).
- Coverage de fidélité sur les frais réels Alpaca (PFOF, regulatory) à
  valider explicitement.

**Pour 10/10** : oracle global "replay 10 jours live → backtest reproduit
à ε près" en CI nightly.

---

## 14. `ihm/` (Streamlit) — **7.5 / 10**

**Points forts** : pages spécialisées (pipeline, screening, portfolio,
exécution scopée run, ML, CA, reporting, paramètres, supervision,
backtesting), multi-compte sidebar, tooltips help YAML, tests E2E
(`test_ihm_pipeline_e2e.py`, `test_ihm_execution_e2e.py`,
`test_ihm_navigation.py`, `test_pages_*`).

**Faiblesses** :
- Pas de "guard" empêchant de lancer l'étape N+1 du pipeline si N a
  échoué (process_registry suit mais ne bloque pas).
- Pas de gel UI quand un job critique tourne ailleurs.
- Pas de page consolidée "santé broker + DB + provider + queue".

**Pour 10/10** : dashboard santé unique + "advance pipeline" intelligent.

---

## 15. Observabilité / run_summary / logs — **7.0 / 10**

**Points forts** : run_summary versionnés (`attach_schema_version`),
helper `merge_iex_bias_counters`, run_business_summaries persistés,
notifications email (Sprint S27), audit chain (`database/audit_chain.py`).

**Faiblesses** :
- Pas de Prometheus exporter "first-class" branché par défaut
  (`test_prometheus_metrics.py` existe pourtant — clarifier statut).
- Logs Python encore en texte simple (pas de structlog JSON natif).

**Pour 10/10** : log JSON, exporter Prometheus actif en prod, alerting
Grafana documenté.

---

## 16. Sécurité / readiness production — **7.5 / 10**

**Points forts** : scanner secrets bloquant, env vars exclusives,
ressaisie label compte live, RuntimeError si equity manquante,
`pre_live_checklist`, vault optionnel (`config_vault.py`).

**Faiblesses** :
- Audit de privilèges DB minimal (recommandé : utilisateur RO pour IHM).
- Pas de signature des artefacts (`models/`, `eodhd_cache/`).
- Pas de rotation automatique de secrets documentée.

**Pour 10/10** : profil utilisateur DB RO pour IHM, KMS-backed vault,
rotation programmée.

---

## 17. Qualité logicielle globale — **8.0 / 10**

**Points forts** : ~280 fichiers de tests, ruff, mypy (`mypy.ini`),
import-linter (`test_import_linter_contracts.py`), property-based tests,
benchmarks (`tests/benchmarks/`), formal (`tests/formal/`), integration
(`tests/integration/`), pas de TODO en prod (`test_no_todo_in_app_code.py`).

**Faiblesses** :
- Pas de couverture mesurée < N % bloquante en CI publique.
- Pas vu de mutation testing actif en CI (`mutation_testing.md` est doc).

**Pour 10/10** : seuil coverage CI ≥ 85 %, mutation testing nightly,
golden tests sur 1 an de données de référence.

