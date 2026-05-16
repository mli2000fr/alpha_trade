# 10 — Matrice Anomalie → Correctif → Test(s) → Sprint — Alpha Trade

> **Date** : mai 2026 | ✅ = Confirmé RÉSOLU par vérification directe du code source

---

## Matrice complète

| ID | Titre | Sévérité | Statut | Correctif | Tests | Sprint |
|---|---|---|---|---|---|---|
| A-001 | max_positions 10 vs "3 lignes" | P1 | 🔴 Actif | Corriger `risk_max_positions: 3` | `test_capital_preset_risk_overrides.py` | S1 |
| A-002 | Noms tables obsolètes lineage matrix | P1 | 🔴 Actif | Régénérer `data_lineage_matrix.md` | `test_data_lineage_autogen.py` | S1 |
| A-003 | model_predictions absence governance ML | P1 | ✅ **RÉSOLU** | `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` présents dans `model_predictions.sql:8-11` + persistés par `db_registry.py:336-363` | `test_model_factory_db_registry.py` | — |
| A-004 | vectorbt mention obsolète DOC_TECHNIQUE | P1 | ✅ **RÉSOLU** (sauf résidu argparse) | `DOC_TECHNIQUE.md:497` corrigé. Résidu : `backtesting/cli/_impl.py:67` à corriger (cosmétique) | `test_doc_provider_alignment.py` | S1 (résidu) |
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
| A-016 | PDT rule commentaire absent (cash comptes) | P2 | 🔴 Actif | Ajouter commentaire YAML | Aucun test | S1 |
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

### A-001 — `test_capital_preset_risk_overrides.py`

**Objectif** : Valider la cohérence interne des presets capital  
**Type** : Unitaire / configuration  
**Priorité** : P1  
**Scénario** :
```
Given : fichier config/capital_presets.yaml chargé
When : on vérifie chaque preset
Then : max_positions × min_notional <= 0.95 × max_equity (solvabilité notionnelle)
Then : description mentionne le bon nombre de lignes
Then : si account_type=cash → pdt_rule doit être "off"
```
**Fixtures** : `config/capital_presets.yaml` chargé directement  
**Ce que le test empêche** : Regression de presets incohérents (positions × notional > equity)

---

### A-002 — `test_data_lineage_autogen.py`

**Objectif** : Valider que la lineage matrix référence les bons noms de tables  
**Type** : Non-régression documentation  
**Priorité** : P1  
**Scénario** :
```
Given : data_lineage_matrix.md et liste des tables réelles depuis database/sql/
When : vérification croisée des noms de tables
Then : aucun nom obsolète (execution_orders, execution_audit_events, etc.)
Then : pas de table référencée dans lineage absente du schéma réel
```
**Ce que le test empêche** : Divergence silencieuse doc ↔ schéma DB

---

## Détail des tests P1 RÉSOLUS ✅

### A-003 ✅ — `test_model_factory_db_registry.py` — RÉSOLU

**Résolution confirmée** : `model_predictions.sql:8-11` contient les 4 colonnes de gouvernance ML. `db_registry.py:336-363` les persiste. Aucune action requise — le test doit simplement vérifier que ces colonnes sont non-NULL après un run.

---

### A-004 ✅ — `test_doc_provider_alignment.py` — RÉSOLU (sauf résidu argparse)

**Résolution confirmée** : `DOC_TECHNIQUE.md:497` ne contient plus "vectorbt". Résidu cosmétique dans `backtesting/cli/_impl.py:67` — à corriger dans S1.

---

### A-005 ✅ — `test_corporate_actions.py` — RÉSOLU

**Résolution confirmée** : Factory `build_corporate_action_provider()` correctement implémentée (`corporate_actions/provider.py:402-432`). Le test du switch provider est un test de non-régression à conserver dans la CI.
```
Given : config avec bars_provider='eodhd'
When : build_corporate_action_provider(config)
Then : provider est EodhdCorporateActionProvider

Given : config avec bars_provider='alpaca'
When : build_corporate_action_provider(config)
Then : provider est AlpacaCorporateActionProvider
```

