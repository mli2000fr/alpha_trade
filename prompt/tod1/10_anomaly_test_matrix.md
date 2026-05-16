# 10 — Matrice Anomalie → Correctif → Test(s) → Sprint — Alpha Trade

> **Date** : mai 2026 | ✅ = Confirmé RÉSOLU par vérification directe du code source

---

## Matrice complète

| ID | Titre | Sévérité | Statut | Correctif | Tests | Sprint |
|---|---|---|---|---|---|---|
| A-001 | max_positions 10 vs "3 lignes" | P1 | ✅ **RÉSOLU Sprint S1** | `risk_max_positions: 3`, `min_notional: 500.0` dans `capital_0_2000_eur` | `test_capital_preset_risk_overrides.py` (5 nouveaux tests) | — |
| A-002 | Noms tables obsolètes lineage matrix | P1 | ✅ **RÉSOLU Sprint S1** | LINEAGE_SPEC corrigé, MD régénéré, CI `--check` vert | `test_data_lineage_autogen.py` (7/7 pass) | — |
| A-003 | model_predictions absence governance ML | P1 | ✅ **RÉSOLU** | `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` présents dans `model_predictions.sql:8-11` + persistés par `db_registry.py:336-363` | `test_model_factory_db_registry.py` | — |
| A-004 | vectorbt mention obsolète DOC_TECHNIQUE | P1 | ✅ **RÉSOLU Sprint S1** (résidu argparse corrigé) | `backtesting/cli/_impl.py:67` description mise à jour | `test_doc_provider_alignment.py` | — |
| A-005 | CA provider ambigu (Alpaca vs EODHD) | P1 | ✅ **RÉSOLU** | Règle documentée : `DOC_FONCTIONNELLE.md:246` + `data_lineage_matrix.md §7:109-111` + factory `corporate_actions/provider.py:402-432` | `test_corporate_actions.py` | — |
| A-006 | PDT rule off sur comptes margin ≥ 25k$ | P2 | 🔴 Actif | Passer `pdt_rule: auto` sur presets margin | `test_execution_config.py` | S2 |
| A-007 | min_close 5.0$ sous profil strict | P2 | 🔴 Actif | Uniformiser `min_close: 10.0` preset 0_5000 | `test_strict_filter_profiles.py` | S2 |
| A-008 | Spreads IEX biaisés | P2 | 🟡 Atténué | Documenter + `max_spread_bps_iex` comme mitigation | `test_eodhd_phase4_volume_audit.py` | S3 |
| A-009 | model_predictions pas d'unicité symbol/date | P2 | ✅ **RÉSOLU** | `UNIQUE KEY uq_symbol_date_run` présent (`model_predictions.sql:14`) + `ON DUPLICATE KEY UPDATE` | `test_model_factory_db_registry.py` | — |
| A-010 | ParquetCache non branché | P2 | 🔴 Actif | Ajouter option `--use-cache` CLI | `test_backtesting.py` | S3 |
| A-011 | analytics/statistical_validation non branchés | P2 | 🔴 Actif | Ajouter flags CLI opt-in | `test_backtesting.py` | S3 |
| A-012 | SSL MySQL absent | P2 | ✅ **RÉSOLU** | `_read_ssl_connect_args()` dans `database/connection.py:97-111` — TLS activé si `DB_SSL_CA_PATH` défini | `test_connection.py` | — |
| A-013 | Pas d'alerting externe automatique | P2 | 🔴 Actif | Déclencher email sur circuit_breaker + kill_switch | `test_ihm_notifications.py` | S3 |
| A-014 | auto_rebalance off → dérive silencieuse | P2 | 🔴 Actif | Alerting si diff réconciliation > seuil depuis > 24h | `test_execution_engine_reconciliation.py` | S3 |
| A-015 | Market cap stale TTL non alerté | P2 | 🔴 Actif | Alerte IHM si TTL expiré sur N% symboles | `test_alpha_scanner.py` | S3 |
| A-016 | PDT rule commentaire absent (cash comptes) | P2 | ✅ **RÉSOLU Sprint S1** | Commentaire ajouté sur 4 presets cash dans `config/capital_presets.yaml` | `test_cash_presets_have_pdt_off` (nouveau) | — |
| A-017 | fill_timeout insuffisant lors de gap | P2 | 🔴 Actif | Augmenter à 180/300s + runbook | `test_execution_engine_executor.py` | S2 |
| A-018 | §1.3 DOC_FONCTIONNELLE step 1 = alpaca | P3 | ✅ **RÉSOLU** | `DOC_FONCTIONNELLE.md:37` nomme EODHD comme provider primaire | `test_doc_provider_alignment.py` | — |
| A-019 | Stooq apikey conditionnelle non testée | P3 | 🔴 Actif | Documenter utilisation sans clé | `test_macro_providers.py` | S3 |
| A-020 | yields désactivés avec provider eodhd | P3 | 🔴 Actif | Documenter quota consommé | Aucun test | S4 |
| A-021 | Pas de PnL quotidien IHM | P3 | 🔴 Actif | Ajouter widget PnL Overview | `test_pages_overview.py` | S4 |
| A-022 | Walk-forward limité poids sentiment | P3 | 🔴 Actif | Étendre à paramètres risk | `test_weights_calibration.py` | S4 |
| A-023 | test_data_lineage_autogen non activé CI | P3 | 🔴 Actif | Vérifier activation CI | `test_data_lineage_autogen.py` | S1 |
| A-024 | prompt/ structuration partielle | P3 | 🔴 Actif | Archiver sprints précédents | Aucun test | S4 |
| A-025 | Compression logs insuffisante | P3 | 🔴 Actif | TimedRotatingFileHandler + gzip | `test_common_utils.py` | S3 |
| A-026 | test_import_alpaca_bar_noop non documenté | P3 | 🔴 Actif | Documenter dans dataIntegrityEngine.md | Aucun test | S1 |
| A-027 | Walk-forward : pas de bornes business poids | P3 | 🔴 Actif | Ajouter assertions plages admissibles | `test_weights_calibration.py` | S3 |

---

## Détail des tests prioritaires P1 actifs

> ⚠️ **Toutes les anomalies P1 sont maintenant résolues** (A-001 ✅, A-002 ✅, A-003 ✅, A-004 ✅, A-005 ✅ après Sprint S1). Aucune P1 active restante.

---

## Détail des tests P1/P2 RÉSOLUS ✅

### A-001 ✅ — `test_capital_preset_risk_overrides.py` — RÉSOLU Sprint S1

**Résolution** : 5 nouveaux tests ajoutés et passent tous. `risk_max_positions: 3`, `min_notional: 500.0` confirmés.

Tests ajoutés :
```python
test_positions_notional_solvency()          # max_pos × min_notional ≤ 0.95 × max_equity
test_micro_account_max_positions_coherent() # capital_0_2000_eur.max_positions ≤ 5
test_micro_account_min_notional_viable()    # capital_0_2000_eur.min_notional ≥ 400 USD
test_positions_increase_with_account_size() # monotonie des positions entre tranches
test_cash_presets_have_pdt_off()            # pdt_rule='off' sur tous les presets cash
```

---

### A-002 ✅ — `test_data_lineage_autogen.py` — RÉSOLU Sprint S1

**Résolution** : `scripts/generate_data_lineage.py` LINEAGE_SPEC corrigé :
- `execution_orders` → `execution_order_requests` + `execution_broker_orders`
- `execution_audit_events` → `execution_events`

`doc/data_lineage_matrix.md` régénéré. `test_repo_lineage_matrix_is_in_sync` passe. 7/7 tests verts.

---

### A-003 ✅ — `test_model_factory_db_registry.py` — RÉSOLU (avant Sprint S1)

**Résolution confirmée** : `model_predictions.sql:8-11` contient les 4 colonnes. `db_registry.py:336-363` les persiste. Tests verts.

---

### A-004 ✅ — `test_doc_provider_alignment.py` — RÉSOLU Sprint S1

**Résolution** : `backtesting/cli/_impl.py:67` : `description="Backtest intégré Alpha Trade (simulateur custom PIT)"`. Plus aucun résidu "vectorbt".

---

### A-005 ✅ — `test_corporate_actions.py` — RÉSOLU (avant Sprint S1)

**Résolution confirmée** : Factory `build_corporate_action_provider()` correctement implémentée. Tests de non-régression à conserver en CI.

---

### A-016 ✅ — `test_cash_presets_have_pdt_off` — RÉSOLU Sprint S1

**Résolution** : 4 presets cash annotés avec commentaire explicatif. Test de régression ajouté dans `test_capital_preset_risk_overrides.py`.

