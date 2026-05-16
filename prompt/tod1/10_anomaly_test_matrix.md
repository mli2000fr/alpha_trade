# 10 — Matrice Anomalie → Correctif → Test(s) → Sprint — Alpha Trade

> **Date** : mai 2026

---

## Matrice complète

| ID | Titre | Sévérité | Correctif | Tests | Sprint |
|---|---|---|---|---|---|
| A-001 | max_positions 10 vs "3 lignes" | P1 | Corriger `risk_max_positions: 3` | `test_capital_preset_risk_overrides.py` | S1 |
| A-002 | Noms tables obsolètes lineage matrix | P1 | Régénérer `data_lineage_matrix.md` | `test_data_lineage_autogen.py` | S1 |
| A-003 | model_predictions absence governance ML | P1 | Migration `0029_model_predictions_governance` | `test_model_factory_db_registry.py` | S2 |
| A-004 | vectorbt mention obsolète DOC_TECHNIQUE | P1 | Corriger DOC_TECHNIQUE §9 | `test_doc_provider_alignment.py` | S1 |
| A-005 | CA provider ambigu (Alpaca vs EODHD) | P1 | Documenter règle factory CA dans les deux docs | `test_corporate_actions.py` | S1 |
| A-006 | PDT rule off sur comptes margin ≥ 25k$ | P2 | Passer `pdt_rule: auto` sur presets margin | `test_execution_config.py` | S2 |
| A-007 | min_close 5.0$ sous profil strict | P2 | Uniformiser `min_close: 10.0` preset 0_5000 | `test_strict_filter_profiles.py` | S2 |
| A-008 | Spreads IEX biaisés | P2 | Documenter + `max_spread_bps_iex` comme mitigation | `test_eodhd_phase4_volume_audit.py` | S3 |
| A-009 | model_predictions pas d'unicité symbol/date | P2 | Vérifier/ajouter contrainte UNIQUE | `test_model_factory_db_registry.py` | S2 |
| A-010 | ParquetCache non branché | P2 | Ajouter option `--use-cache` CLI | `test_backtesting.py` | S3 |
| A-011 | analytics/statistical_validation non branchés | P2 | Ajouter flags CLI opt-in | `test_backtesting.py` | S3 |
| A-012 | SSL MySQL absent | P2 | Activer SSL via env var `DB_SSL_CA` | `test_connection.py` | S2 |
| A-013 | Pas d'alerting externe automatique | P2 | Déclencher email sur circuit_breaker + kill_switch | `test_ihm_notifications.py` | S3 |
| A-014 | auto_rebalance off → dérive silencieuse | P2 | Alerting si diff réconciliation > seuil depuis > 24h | `test_execution_engine_reconciliation.py` | S3 |
| A-015 | Market cap stale TTL non alerté | P2 | Alerte IHM si TTL expiré sur N% symboles | `test_alpha_scanner.py` | S3 |
| A-016 | PDT rule commentaire absent (cash comptes) | P2 | Ajouter commentaire YAML | Aucun test | S1 |
| A-017 | fill_timeout insuffisant lors de gap | P2 | Augmenter à 180/300s + runbook | `test_execution_engine_executor.py` | S2 |
| A-018 | §1.3 DOC_FONCTIONNELLE step 1 = alpaca | P3 | Corriger §1.3 pour nommer eodhd/alpaca conditionnellement | `test_doc_provider_alignment.py` | S1 |
| A-019 | Stooq apikey conditionnelle non testée | P3 | Documenter utilisation sans clé | `test_macro_providers.py` | S3 |
| A-020 | yields désactivés avec provider eodhd | P3 | Documenter quota consommé | Aucun test | S4 |
| A-021 | Pas de PnL quotidien IHM | P3 | Ajouter widget PnL Overview | `test_pages_overview.py` | S4 |
| A-022 | Walk-forward limité poids sentiment | P3 | Étendre à paramètres risk | `test_weights_calibration.py` | S4 |
| A-023 | test_data_lineage_autogen non activé CI | P3 | Vérifier activation CI | `test_data_lineage_autogen.py` | S1 |
| A-024 | prompt/ structuration partielle | P3 | Archiver sprints précédents | Aucun test | S4 |
| A-025 | Compression logs insuffisante | P3 | TimedRotatingFileHandler + gzip | `test_common_utils.py` | S3 |
| A-026 | test_import_alpaca_bar_noop non documenté | P3 | Documenter dans dataIntegrityEngine.md | Aucun test | S1 |
| A-027 | Walk-forward : pas de bornes business poids | P3 | Ajouter assertions plages admissibles | `test_weights_calibration.py` | S3 |

---

## Détail des tests prioritaires P1

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

### A-003 — `test_model_factory_db_registry.py`

**Objectif** : Valider la persistance de la gouvernance ML en DB  
**Type** : Intégration  
**Priorité** : P1  
**Scénario** :
```
Given : modelFactory/predictor.py exécuté sur un symbole avec un champion sélectionné
When : insertion dans model_predictions
Then : selected_model IS NOT NULL
Then : decision_threshold IS NOT NULL
Then : calibration_method IS NOT NULL
```
**Fixtures** : Mock `champion_selection.py` retournant `selected_model='lightgbm'`, DB SQLite en mémoire  
**Ce que le test empêche** : Perte de traçabilité ML en production

---

### A-004 — `test_doc_provider_alignment.py`

**Objectif** : Détecter les mentions obsolètes dans les docs  
**Type** : Non-régression documentation  
**Priorité** : P1  
**Scénario** :
```
Given : fichiers doc/*.md
When : recherche de patterns obsolètes
Then : "vectorbt" n'apparaît pas dans DOC_TECHNIQUE.md
Then : "import_alpaca_bar" ne désigne pas l'étape 1 principale sans qualifier le provider
Then : beta_126 >= 1.0 n'apparaît pas comme seuil (corrigé en 0.8)
Then : max_spread_bps = 25 bps n'apparaît pas (corrigé en 40 bps)
```
**Ce que le test empêche** : Documentation induisant en erreur les opérateurs

---

### A-005 — `test_corporate_actions.py`

**Objectif** : Valider le switch provider CA selon `bars_provider`  
**Type** : Intégration  
**Priorité** : P1  
**Scénario** :
```
Given : config avec bars_provider='eodhd'
When : build_corporate_action_provider(config)
Then : provider est EodhdCorporateActionProvider

Given : config avec bars_provider='alpaca'
When : build_corporate_action_provider(config)
Then : provider est AlpacaCorporateActionProvider
```
**Fixtures** : Mock config avec les deux modes  
**Ce que le test empêche** : Provider CA incohérent avec les barres OHLCV

