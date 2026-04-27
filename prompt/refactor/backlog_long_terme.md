# Backlog Long terme — Alpha Trade

> Items reportés explicitement après la Phase 7 du refactor (cf.
> `prompt/refactor/plan.md`). Tous ont été instruits dans les audits ; leur
> implémentation a été jugée **hors scope 6-8 semaines** au vu du coût et/ou
> du faible ROI immédiat.
>
> Chaque entrée porte : **justification du report**, **esquisse cible**,
> **dépendances**, **estimation grossière**.

---

## L1 — SEC EDGAR 8-K comme second canal news *(Phase 7.8)*

- **Source** : `audit_event_sentiment.md` §sources, `audit_global.md` §4.
- **Justification report** : volumétrie 8-K élevée (~500/jour), parsing
  XBRL/HTML hétérogène, dédup vs Alpaca News non triviale, IC vs forward
  returns à mesurer **avant** intégration → coût > 5 jours, hors scope.
- **Esquisse cible** :
  - Module : `event_sentiment/edgar_provider.py` implémentant
    `core.interfaces.NewsProvider`.
  - Polling RSS `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom`.
  - Cache local `artifacts/edgar_cache/<symbol>/<accession>.json`.
  - Scoring FinBERT identique à Alpaca News (`SentimentSignalAggregator`).
  - Dédup via `(symbol, filing_date_utc, item_codes)`.
- **Dépendances** : pas de nouvelle dépendance Python (`requests` + `xml.etree`).
- **Estimation** : 5-8 jours dev + 1 semaine validation IC vs forward returns.

---

## L2 — Mode shadow live continu *(Phase 7.7 — partiellement livré offline)*

- **Source** : `audit_backtesting.md` §recommandations, `audit_global.md` §7.
- **Statut** : la **comparaison offline** (`risk_management.shadow_compare`
  + table `shadow_drift_runs`) est livrée Phase 7. Le **daemon shadow
  continu** reste backlog.
- **Justification report** : nécessite double broker session, double risk run
  journalier, monitoring dédié, résolution conflits idempotency.
- **Esquisse cible** :
  - Daemon `risk_management/shadow_daemon.py` qui réplique chaque run live
    sur un compte paper auto-pairé.
  - Persistance auto dans `shadow_drift_runs` après chaque cycle.
  - Alerting si `avg_qty_drift_pct > 5%` ou `symbols_only_in_*` non vides.
- **Estimation** : 8-10 jours.

---

## L3 — Dashboard Grafana + Alertmanager *(Phase 7.5 — endpoint livré)*

- **Statut** : l'endpoint `/metrics` (`core.metrics`) et la doc
  `doc/observability.md` sont livrés. Dashboards / alerting restent backlog.
- **Justification report** : nécessite déploiement Grafana + Alertmanager,
  versioning des dashboards JSON, formation ops.
- **Esquisse cible** :
  - Dossier `ops/grafana/` versionné (dashboards JSON).
  - Provisioning Docker Compose (Prometheus + Grafana + Alertmanager).
  - Alertes listées dans `doc/observability.md` §5.
- **Estimation** : 3-5 jours.

---

## L4 — Fine-tune LoRA FinBERT

- **Source** : `audit_event_sentiment.md` §améliorations.
- **Justification report** : nécessite dataset labellisé US-financial actuel
  (>= 5k exemples), GPU disponible, validation IC. Coût formation données.
- **Esquisse cible** :
  - Dataset `event_sentiment/datasets/finetune/`.
  - Script `event_sentiment/finetune_lora.py` (PEFT + LoRA r=8).
  - Adapter persisté `artifacts/models/finbert_lora/`.
- **Estimation** : 10-15 jours.

---

## L5 — XGBoost comme 3e challenger ML

- **Source** : `audit_modelFactory.md` §challengers.
- **Justification report** : champion sélection déjà en place avec LightGBM
  et CatBoost ; XGBoost peu de ROI marginal vs effort intégration (gestion
  GPU optionnel, sérialisation native, fingerprint).
- **Estimation** : 3-5 jours.

---

## L6 — `ProcessRegistry` IHM DB-backed

- **Source** : `audit_ihm.md` §process registry.
- **Statut** : registry actuel en mémoire + atexit cleanup (Phase 6.2).
- **Justification report** : utile uniquement si plusieurs instances IHM
  concurrentes (multi-utilisateur). Single-user actuel → faible priorité.
- **Esquisse cible** : table `ihm_process_registry(pid, started_at,
  step, status, owner_session)`.
- **Estimation** : 2-3 jours.

---

## L7 — Migration progressive hors `vectorbt`

- **Source** : `audit_backtesting.md` §dépendances.
- **Justification report** : `vectorbt` couvre les besoins actuels ;
  migration uniquement justifiée si maintenance défaillante upstream.
- **Esquisse cible** : moteur custom pandas/numpy + tests d'équivalence
  numérique sur 5 ans d'historique.
- **Estimation** : 15-20 jours.

---

## L8 — Vault complet pour secrets live

- **Source** : `audit_global.md` §sécurité.
- **Statut** : DPAPI partiel pour watcher (Phase 6.3) + secrets DB hors
  `config.yaml` (Phase 1.2).
- **Justification report** : déploiement Vault (Hashicorp ou Azure Key Vault)
  trop lourd pour single-host Windows actuel.
- **Esquisse cible** : abstraction `core/secrets.py` déjà présente, ajouter
  un backend `VaultSecretBackend`.
- **Estimation** : 5-7 jours.

---

## L9 — Évaluer Polygon free / Tiingo NBBO

- **Source** : `audit_global.md` §4.
- **Justification report** : quotas free très stricts (5 req/min Polygon, 50
  req/h Tiingo) → utile uniquement pour cross-check ponctuel, pas pour
  production daily.
- **Esquisse cible** : POC `service/polygon/` avec rate limiter strict.
- **Estimation** : 3-5 jours POC.

---

## L10 — Découpage `ihm/pages/pipeline.py` en sous-modules *(✅ livré post-Phase 7)*

- **Source** : `audit_ihm.md`, `prompt/refactor/plan.md` Phase 6.2.
- **Statut** : **livré.** `ihm/pages/pipeline.py` passe de 3049 lignes à
  **271 lignes** via `scripts/split_pipeline.py` (idempotent, ré-exécutable).
- **Sous-modules créés** dans `ihm/pages/` :
  - `_shared.py` (279 l.) — constantes `*_KEY`, `TAIL_LINES`, helpers
    transverses (`_tail_text`, `_render_run_summary`, `_render_log_block`,
    `_render_step_result`, `_status_badge`, `_workflow_progress`,
    `_launch_pipeline_step`, `_sanitize_compare_ids`, …).
  - `_workflow.py` (319 l.) — `_render_workflow_launcher`,
    `_render_runtime_center` (`@st.fragment`), `_merge_runs`,
    `_build_history_rows`.
  - `_data_integrity.py` (129 l.) — panneau `_render_import_news_panel`.
  - `_execution_center.py` (1953 l.) — `_apply_execution_prefills`,
    `_build_execution_prefill_caption`, `_build_launch_options` (~1760 l.,
    découpage plus fin par sous-bloc laissé en TODO 2e passe).
  - `_alpha_scanner_diagnostics.py` (321 l.) — éditeur de seuils, badges,
    `_render_alpha_scanner_dependency_diagnostic`.
  - `_watcher_block.py` (69 l.) — handoff watcher post-exécution.
- **Rétro-compatibilité** : `pipeline.py` ré-exporte tous les symboles
  publics et privés via `from ihm.pages._<sub> import …` ; les imports
  historiques `from ihm.pages.pipeline import X` continuent de fonctionner.
- **Validation** : 94 tests IHM verts (`pytest tests/test_ihm*.py`),
  imports vérifiés pour les 7 modules en standalone.
- **Note 2e passe** : `_build_launch_options` reste massif (~1760 lignes,
  agrège tous les panneaux de paramètres : execution, risk, ML, screener,
  selector, signal_aggregator, corporate_actions). Un futur découpage par
  sous-bloc d'options pourrait réduire ce module à <500 lignes ;
  non bloquant pour la livraison L10.

---

## L11 — `import-linter` strict (vs warn-only) *(Phase 7.1)*

- **Statut** : config `.importlinter` livrée Phase 7.1, test contractuel en
  `xfail`.
- **Justification report** : passage strict après triage des violations
  résiduelles (whitelist explicite ou refactor par module).
- **Estimation** : 1-2 jours triage + 0-3 jours refactor selon résultat.

---

## Critères de promotion (backlog → plan)

Un item du backlog est éligible à promotion en sprint quand :
1. Un **trigger métier** est observé (ex : 3 incidents Alpaca news en 1 mois
   → promotion L1 EDGAR).
2. Une **mesure quantitative** justifie l'effort (ex : drift ML répétés →
   promotion L4 fine-tune FinBERT).
3. Un **changement réglementaire** l'impose (ex : audit externe → L8 Vault).

---

**Réf.** : `prompt/refactor/plan.md` Phase 7 ; `prompt/refactor/audit_global.md`.

