# 08 — Plan de sprints

> Plan séquencé pour amener Alpha Trade vers un niveau quasi-pro. Chaque
> sprint inclut un volet tests **obligatoire**.
>
> Hypothèse de cadence : 1 développeur senior, 1 sprint = 1 semaine sauf
> mention contraire.

---

## Sprint S1 — Quick wins doc & config (1 semaine)

- **Objectif** : éliminer les contradictions critiques doc/config qui
  trompent activement l'opérateur.
- **Priorité** : **P0**.
- **Modules impactés** : `doc/`, `config.yaml`, `corporate_actions/engine.py`
  (docstring), `README.md`.
- **Anomalies traitées** : A-001, A-002, A-003, A-004, A-005, A-012, A-022,
  A-030.
- **Tâches** :
  1. Réécrire docstring `corporate_actions/engine.py:34-39` (convention
     `'split'` + ledger).
  2. Supprimer `eodhd.enabled` de `config.yaml` (ou implémenter
     consommation explicite).
  3. Réécrire `README.md` §6 (étape 1 conditionnelle).
  4. Réécrire bandeau `doc/dataIntegrityEngine.md:3-22`.
  5. Réécrire `doc/data_lineage_matrix.md` lignes 27-31.
  6. Mettre à jour `doc/corporate_actions.md` (convention split).
  7. Supprimer/rediriger `doc/backetesting.md` (doublon).
  8. README §11 : ajouter dossiers manquants.
  9. Ajouter à `doc/DOC_FONCTIONNELLE.md` / `DOC_TECHNIQUE.md` la mention
     EODHD primaire.
  10. Garde-fou idempotent dans `signal_aggregator` (verrou ou flag
      `--already-applied`).
- **Critères d'acceptation** : aucune contradiction provider primaire
  doc↔code↔config ; `grep eodhd.enabled` retourne 0 résultat dans
  `config.yaml` ; tests doc verts.
- **Tests à ajouter** :
  - `tests/test_data_adjustment_convention.py` (A-001) — *test unitaire,
    fixture: aucune.* Vérifie constantes module + parsing docstring.
  - `tests/test_config_yaml_schema.py` (A-002) — *test config Pydantic,
    fixture: copie temporaire `config.yaml`.* Échec si clé orpheline.
  - `tests/test_doc_provider_alignment.py` (A-004, A-005) — *test
    documentation*, parse markdown, vérifie marqueur cohérent avec
    `bars_provider`.
  - `tests/test_signal_aggregator_idempotency.py` (A-022) — *intégration*,
    second lancement → idempotent.
- **Tests existants à étendre** : `tests/test_eodhd_split_only.py` pour
  ajouter assert constante module + docstring CA.
- **Non-régression à exécuter** : suite complète `pytest`.
- **Gain notes attendu** : Documentation 5.5 → 7.0 ; Configuration 6.0 →
  7.0 ; Corporate actions 6.5 → 7.0.
- **Risques/Dépendances** : aucun risque majeur ; documentation pure.

---

## Sprint S2 — Cohérence pipeline & IHM (1 semaine)

- **Objectif** : verrouiller la cohérence runbook ↔ IHM ↔ backend, supprimer
  les pièges no-op silencieux.
- **Priorité** : **P0/P1**.
- **Modules impactés** : `dataIntegrityEngine/`, `ihm/services/`,
  `run_execution.py`.
- **Anomalies traitées** : A-003 (test), A-006 (test backtest), A-008,
  A-014, A-017, A-018, A-023.
- **Tâches** :
  1. Émettre un **WARNING** explicite + champ `skipped_reason` dans
     `import_alpaca_bar` quand `bars_provider != 'alpaca'`.
  2. Ajouter check env contextuel dans `run_execution.py` selon `--account`.
  3. Ajouter télémétrie `data_source` à la lecture des barres dans le
     screener et le selector (compteurs mixés).
  4. Garde-fou IHM : verrou pipeline pour empêcher backtesting concurrent.
  5. Option `--auto-watcher` dans `run_execution` (lance le watcher
     post-run automatiquement).
  6. Check au démarrage du pipeline : `% rows par data_source` >= seuil.
- **Critères d'acceptation** : run no-op silencieux supprimé ; lancement
  live sans creds → erreur claire ; télémétrie `data_source_mix` présente
  dans `run_summary`.
- **Tests à ajouter** :
  - `tests/test_import_alpaca_bar_noop.py` (A-003).
  - `tests/test_run_execution_check_env_per_account.py` (A-008).
  - `tests/test_data_source_consistency_runtime.py` (A-017, A-023).
  - `tests/test_ihm_pipeline_concurrency_lock.py` (A-014).
  - `tests/test_run_execution_auto_watcher.py` (A-018).
- **Non-régression** : `tests/test_ihm_eodhd_provider_switch.py`,
  `tests/test_executor*.py`.
- **Gain notes** : `dataIntegrityEngine` 7.0→7.5 ; IHM 6.5→7.0 ; Sécurité
  6.0→6.8.
- **Risques** : impact UX IHM (verrou) à valider.

---

## Sprint S3 — Risk / CA / Backtest robustesse live (2 semaines)

- **Objectif** : rendre le pipeline réellement protecteur en live.
- **Priorité** : **P1**.
- **Modules impactés** : `risk_management/`, `backtesting/`,
  `corporate_actions/`.
- **Anomalies traitées** : A-006, A-007, A-009, A-010, A-011.
- **Tâches** :
  1. Brancher `PnLSnapshot` réel dans `run_risk` (lecture
     `broker_positions_snapshots` + `execution_runs`).
  2. Vérifier et tester l'inclusion `portfolio_cash_ledger` dans
     `backtesting/analytics.py`.
  3. Émettre `rejected_for_notional`, `rejected_for_atr_missing` dans
     `run_summary` du risk.
  4. Ajouter overrides `risk_max_drawdown_pct` / `risk_max_daily_loss_pct`
     aux 6 presets.
  5. Assouplissement conditionnel `weekly_trend_score` si univers vide.
- **Critères d'acceptation** : circuit breaker testable en intégration ;
  parité backtest↔live ledger dividendes prouvée par test.
- **Tests à ajouter** :
  - `tests/test_run_risk_circuit_breaker_wired.py` (A-007).
  - `tests/test_backtest_total_return_with_dividends.py` (A-006).
  - `tests/test_position_sizer_telemetry.py` (A-010).
  - `tests/test_capital_preset_risk_overrides.py` (A-011).
  - `tests/test_capital_preset_universe_yield.py` (A-009).
- **Tests à étendre** : `tests/test_circuit_breaker.py`,
  `tests/test_risk_checker.py`.
- **Non-régression** : `tests/test_position_sizer.py`, suite backtesting
  complète.
- **Gain notes** : Risk 6.5→7.5 ; Backtesting 6.5→7.5.
- **Risques** : implémentation `PnLSnapshot` peut imposer des migrations DB
  mineures.

---

## Sprint S4 — Hardening providers & data quality (1 semaine)

- **Objectif** : garantir que les barres lues sont homogènes en provider et
  qualité.
- **Modules impactés** : `service/`, `database/`, `screener/`.
- **Anomalies traitées** : A-017 (renforcement), A-019, A-021, A-023.
- **Tâches** :
  1. Implémenter `scripts/generate_data_lineage.py`.
  2. Drift ML → policy gate (kill switch ML automatique).
  3. Matrice provider→table dans `doc/service.md`.
  4. Politique de rétention `artifacts/` documentée.
- **Tests** :
  - `tests/test_data_lineage_autogen.py`.
  - `tests/test_ml_drift_policy_gate.py`.
- **Gain** : Service 7.5→8.0 ; modelFactory 6.0→6.7.

---

## Sprint S5 — Sécurité readiness production (1 semaine)

- **Objectif** : durcissement live.
- **Anomalies traitées** : A-013, suivis A-008.
- **Tâches** :
  1. Supprimer `api_key: "PK..."` / `secret_key: "..."` du `config.yaml`.
  2. Pre-flight checks live (kill switch global, dry run obligatoire avant
     bascule live).
  3. Recette pré-live formalisée (doc + script).
- **Tests** : `tests/test_config_no_literal_secrets.py`,
  `tests/test_pre_live_checklist.py`.
- **Gain** : Sécurité 6.0→7.5.

---

## Sprint S6 — Refactor IHM `_execution_center` (2 semaines)

- **Objectif** : tarir la dette technique IHM massive.
- **Anomalies traitées** : A-016.
- **Tâches** :
  1. Extraction de `_build_launch_options` en sous-blocs thématiques
     (execution, risk, ML, screener, selector, signal_aggregator, CA, data
     integrity).
  2. Tests E2E IHM via `streamlit.testing` (au moins page Pipeline et
     Execution).
- **Tests** : `tests/test_ihm_pipeline_e2e.py`,
  `tests/test_ihm_execution_e2e.py`.
- **Gain** : IHM 7.0→7.8 ; qualité logicielle 7.0→7.5.

---

## Sprint S7 — Refactor `selector/alpha_scanner` & autres modules massifs (2 semaines)

- **Objectif** : finir l'extraction de `AlphaScanner`, découper
  `executor.py` (1318 l.) et `import_eodhd_bar.py` (871 l.) en
  sous-modules pertinents.
- **Anomalies traitées** : A-015.
- **Tests** : property-based sur invariance neutralisation sectorielle ;
  régression `tests/test_alpha_scanner.py`.
- **Gain** : Selector 7.5→8.0 ; Execution 7.5→8.0 ; qualité globale
  7.5→7.8.

---

## Sprint S8 — Gouvernance ML & sentiment empirique (2 semaines)

- **Objectif** : prouver/refuter le bénéfice métier du ML et du sentiment.
- **Anomalies traitées** : A-021, étude FinBERT.
- **Tâches** :
  1. Étude attribution alpha sentiment vs quant pur sur backtest historique.
  2. Calibration formelle des poids 75/15/10.
  3. Mode `--disable-sentiment` + `--disable-ml` testables.
  4. Drift gate auto.
- **Tests** : `tests/test_sentiment_attribution.py`,
  `tests/test_ml_disable_modes.py`.
- **Gain** : event_sentiment 6.0→7.0 ; modelFactory 6.7→7.5.

---

## Sprint S9 — Parité backtest ↔ live formalisée + supervision (2 semaines)

- **Objectif** : tableau de bord de parité backtest/live, alerting externe.
- **Tâches** :
  1. Job quotidien comparant les décisions backtest replay J vs live J.
  2. Alerting Slack/mail si divergence > seuil.
  3. Tableau de bord IHM dédié.
- **Tests** : `tests/test_parity_backtest_live.py`.
- **Gain** : observabilité 7.0→8.0 ; backtesting 7.5→8.0.

---

## Reste à faire pour atteindre un vrai 10/10 pro-grade

- Tests E2E sandbox Alpaca (paper) tournant en CI nightly.
- Multi-broker (au moins un mock + un broker secondaire réel).
- Auto-rollback ML champion si dégradation.
- DR (disaster recovery) DB documenté et testé.
- SOX-like audit trail (signature digitale runs critiques).
- Conformité reporting (statements broker reconciliation automatisée).
- Couverture tests > 85 % branches, mutation testing sur risk + execution.
- Formal verification des invariants critiques (idempotence CA, OCO logique).

## À partir de quel sprint l'application devient suffisamment robuste pour un swing trading réel discipliné ?

**À l'issue du Sprint S3 inclus**, sous condition que tous les tests
P0/P1 listés soient verts en CI. À ce stade :

- Convention provider OHLCV alignée doc↔code↔config ✅
- Pipeline opérateur sans no-op silencieux ✅
- Circuit breaker effectivement branché ✅
- Backtest avec ledger dividendes vérifié ✅
- Multi-comptes sécurisé ✅
- Tranches de capital cohérentes et investissables ✅

Avant S3, le live trading est **déconseillé** ; les modes paper et simulate
restent évidemment exploitables pour expérimenter.

**Niveau pro-grade (note > 8)** atteint après S6 ; **pro-grade revendiquable
(note > 8.5)** après S9.

---

## Matrice anomalies → sprints (synthèse)

| Anomalie | Sprint | Priorité |
|---|---|---|
| A-001, A-002, A-003 (P0) | S1 | bloquant |
| A-004, A-005, A-012, A-022, A-030 (P1/P2/P3) | S1 | quick win |
| A-006, A-007, A-009, A-010, A-011 (P1) | S3 | live readiness |
| A-008 (P1) | S2 | sécurité |
| A-014, A-017, A-018, A-023 (P2) | S2 | cohérence |
| A-013 (P2) | S5 | sécurité |
| A-015 (P2) | S7 | dette |
| A-016 (P2) | S6 | dette |
| A-019, A-021 (P2) | S4 | data/ML |
| A-024 → A-032 (P3) | S5/S6/S9 | mineurs |

