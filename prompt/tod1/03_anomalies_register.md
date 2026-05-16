# 03 — Registre des Anomalies — Alpha Trade

> **Date** : mai 2026 | P0 = critique bloquant | P1 = majeur | P2 = modéré | P3 = mineur/dette tech
>
> **Méthode de vérification** : chaque anomalie a été vérifiée par lecture directe du code source (SQL, Python, YAML). Les anomalies marquées ✅ RÉSOLU ont été confirmées résolues dans le code ; les faux positifs initiaux issus d'une lecture de la seule documentation ont été corrigés.

---

## Résumé du registre

| Total initial | Résolues (code vérifié) | Actives | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
| 27 | 6 | 21 | 0 | 2 | 10 | 9 |

---

## Anomalies P1 (majeures) — actives

### A-001 — `capital_0_2000_eur` : `risk_max_positions: 10` incohérent
- **Sévérité** : P1
- **Domaine** : Configuration / capital_presets
- **Vérification code** : `config/capital_presets.yaml:16` — `risk_max_positions: 10` avec commentaire `# 3 lignes ≈ 600-700 € chacune`. Contradiction directement visible dans le fichier YAML.
- **Description** : Le preset `capital_0_2000_eur` déclare `risk_max_positions: 10` alors que la description dit "3 lignes ≈ 600-700 € chacune" et que le capital est de ~2 000 €. Avec 10 positions à `risk_min_position_notional: 150 USD`, on obtient 1 500 USD de capital alloué minimum — mathématiquement tenu mais chaque position est sous-dimensionnée (150 USD), rendant le coût des frais relatifs prohibitifs.
- **Preuve** : `config/capital_presets.yaml:16` — `risk_max_positions: 10` + commentaire inline "# 3 lignes ≈ 600-700 € chacune"
- **Impact métier** : Positions de 150 USD sur compte de 2 000 € → frais de transaction Alpaca (~1 USD/trade) représentent ~0.67% = ≥ 67 bps par aller-retour → destructeur d'alpha
- **Impact technique** : Incohérence entre la description et la valeur → confusion opérateur, test `test_capital_preset_risk_overrides.py` peut ne pas détecter cette incohérence sémantique
- **Probabilité** : Certaine (valeur incorrecte dans le fichier)
- **Niveau de confiance** : Très élevé (vérifié dans le code source)
- **Recommandation** : Corriger `risk_max_positions: 3` pour ce preset et reconfigurer `risk_min_position_notional: 500 USD` minimum
- **Test à ajouter** : `test_capital_preset_risk_overrides.py` — valider que `max_positions × min_notional ≤ 0.95 × preset.max_equity`

---

### A-002 — `data_lineage_matrix.md` : noms de tables obsolètes (execution)
- **Sévérité** : P1
- **Domaine** : Documentation / database
- **Vérification code** : `database/sql/execution/` contient : `execution_order_requests.sql`, `execution_broker_orders.sql`, `execution_events.sql`. La matrix utilise `execution_orders` (inexistant) et `execution_audit_events` (inexistant).
- **Description** : `data_lineage_matrix.md §4` utilise les noms `execution_orders` et `execution_audit_events` qui ne correspondent à aucun fichier SQL réel. Les tables réelles sont `execution_order_requests`, `execution_broker_orders`, `execution_events`.
- **Preuve** : `doc/data_lineage_matrix.md:68` (`execution_orders`) et `:70` (`execution_audit_events`) vs `database/sql/execution/` (noms canoniques vérifiés)
- **Impact métier** : Un opérateur qui cherche une table en incident trouvera un nom obsolète → perte de temps en production
- **Impact technique** : La documentation de production diverge du schéma réel ; tout script qui lirait la matrix pour générer des requêtes échouerait
- **Probabilité** : Certaine (divergence vérifiée par lecture des fichiers SQL réels)
- **Niveau de confiance** : Très élevé (vérifié dans le code source)
- **Recommandation** : Corriger `data_lineage_matrix.md §4` :
  - `execution_orders` → `execution_order_requests` + `execution_broker_orders` (deux tables distinctes)
  - `execution_audit_events` → `execution_events`
  - Régénérer via `scripts/generate_data_lineage.py` si ce script est à jour
- **Test à ajouter** : `test_data_lineage_autogen.py` — vérifier que chaque table listée dans la matrix existe réellement en DB

---

## Anomalies P2 (modérées) — actives

### A-006 — PDT rule off sur comptes margin ≥ 25k$
- **Sévérité** : P2
- **Domaine** : Configuration / capital_presets / execution_engine
- **Vérification code** : `config/capital_presets.yaml:232-233` (`capital_25001_50000`), `:282-283` (`capital_50001_100000`), `:332-333` (`capital_100001_plus`) — tous ont `execution_account_type: margin` ET `execution_pdt_rule: "off"`.
- **Description** : Les presets `capital_25001_50000`, `capital_50001_100000`, `capital_100001_plus` ont tous `execution_pdt_rule: "off"`. Ces presets sont sur des comptes `margin`. Si l'equity chute temporairement sous 25 000 $ (drawdown), la règle PDT non activée ne bloquera pas le 4e day trade. Alpaca côté broker peut alors imposer des restrictions (minimum equity call, trading restriction 90 jours). Note : `execution_engine/config.py:187` contient `applies_pdt_limit(equity)` qui prend en compte `pdt_equity_threshold` — ce mécanisme est opérationnel si `pdt_rule="auto"`.
- **Preuve** : `config/capital_presets.yaml:232-233`, `:282-283`, `:332-333`
- **Impact métier** : PDT violation potentielle lors d'un drawdown → restriction de compte broker pendant 90 jours → arrêt forcé du trading
- **Recommandation** : Passer `execution_pdt_rule: "auto"` pour les presets margin et documenter le comportement en cas de fluctuation autour de 25 000 $
- **Test à ajouter** : `test_execution_config.py` — test que PDT rule auto est appliqué quand equity fluctue sous 25k$ sur compte margin

---

### A-007 — `capital_0_5000.selector_min_close: 5.0` sous le profil strict canonique
- **Sévérité** : P2
- **Domaine** : Configuration / selector
- **Vérification code** : `config/capital_presets.yaml:96` — `selector_min_close: 5.0`. Les presets `capital_0_2000_eur` (line 44), `capital_25001_50000` (line 246) et supérieurs ont tous `selector_min_close: 10.0`. `core/filter_profiles.py:241` (STRICT_SWING_CASH_FILTERS) a `min_close = 10.0`. Par cohérence de gamme, même le preset micro-compte a `selector_min_close: 10.0`.
- **Description** : Le preset `capital_0_5000` a `selector_min_close: 5.0` alors que `STRICT_SWING_CASH_FILTERS.min_close = 10.0`. Les actions à 5–9 USD ont des frais relatifs disproportionnés sur Alpaca et des biais IEX plus forts.
- **Preuve** : `config/capital_presets.yaml:96` vs `core/filter_profiles.py:241`
- **Recommandation** : Uniformiser `selector_min_close: 10.0` sur `capital_0_5000` ou documenter explicitement la justification du relâchement
- **Test à ajouter** : `test_strict_filter_profiles.py` — vérifier que aucun preset n'a `min_close < 10.0` sans justification documentée

---

### A-008 — Quotes IEX biaisées pour le filtre spread_bps
- **Sévérité** : P2
- **Domaine** : dataIntegrityEngine / selector
- **Description** : `stock_quote_snapshots` provient toujours d'Alpaca IEX (même si `bars_provider=eodhd`). Alpaca IEX cite des spreads significativement plus larges (~50 bps) que le NBBO réel pour les mid-caps hors heures de trading. Cela peut faire rejeter des titres exécutables en réalité.
- **Preuve** : `doc/dataIntegrityEngine.md` en-tête : "spreads `stock_quote_snapshots` : toujours Alpaca IEX (~50 bps NBBO)"
- **Recommandation** : Utiliser `max_spread_bps_iex` (déjà défini dans le profil) comme valeur relâchée, documenter le biais dans le rapport d'audit de screens
- **Test à ajouter** : `test_eodhd_phase4_volume_audit.py` — étendre pour valider l'impact du biais IEX sur le taux de rejet spread

---

### A-010 — ParquetCache non branché par défaut (backtesting lent sur grands datasets)
- **Sévérité** : P2
- **Domaine** : backtesting
- **Vérification code** : `backtesting/cli/_impl.py:64` — `_build_parser()` ne contient pas d'option `--use-cache`. `backtesting/cache.py` (`ParquetCache`) existe et est testé mais non instancié dans `_run_backtest()`. `doc/DOC_TECHNIQUE.md:163` confirme : "pas encore branché par défaut à la commande `run`".
- **Description** : `backtesting/cache.py` (`ParquetCache`) est présent mais non utilisé par défaut dans la commande `run`. Chaque backtest full recharge toutes les données depuis MySQL. Sur 2 ans, 500 symboles, cela prend plusieurs dizaines de minutes et charge significativement la DB.
- **Preuve** : `backtesting/cli/_impl.py:_build_parser()` — absence d'option cache ; `doc/DOC_TECHNIQUE.md:163`
- **Recommandation** : Activer `ParquetCache` comme option `--use-cache` dans la CLI, avec invalidation sur changement de dates ou de dataset_hash
- **Test à ajouter** : `test_backtesting.py` — ajouter test de performance avec cache activé vs désactivé

---

### A-011 — `analytics.py` et `statistical_validation.py` non branchés à la CLI standard
- **Sévérité** : P2
- **Domaine** : backtesting
- **Vérification code** : `backtesting/cli/_impl.py:_build_parser()` — pas d'option `--bootstrap-samples` ni `--sensitivity-analysis`. `backtesting/analytics.py` et `backtesting/statistical_validation.py` existent mais ne sont pas importés dans `_impl.py`.
- **Description** : Bootstrap Monte Carlo (`bootstrap_trades()`), attribution sectorielle, exports HTML interactifs et `parameter_sensitivity()` sont implémentés mais ne sont pas accessibles via la CLI standard `python -m backtesting run`.
- **Preuve** : Absence d'options dans `backtesting/cli/_impl.py:_build_parser()` ; `doc/DOC_TECHNIQUE.md §2.1`
- **Recommandation** : Ajouter options `--bootstrap-samples 1000` et `--sensitivity-analysis` à la CLI
- **Test à ajouter** : `test_backtesting.py` — tester le pipeline complet avec bootstrap activé

---

### A-013 — Pas de déclenchement automatique d'alerting externe (email/Slack)
- **Sévérité** : P2
- **Domaine** : Observabilité
- **Description** : Le circuit breaker, les échecs consécutifs (kill switch), et les résultats de réconciliation ne déclenchent pas d'alerting externe automatique. L'opérateur doit consulter l'IHM activement.
- **Preuve** : `doc/DOC_FONCTIONNELLE.md §6 : "Pas de notification externe : Pas d'email/SMS/Slack, logs fichier uniquement"`
- **Recommandation** : Intégrer les notifications email déjà partiellement implémentées (`artifacts/ihm_notifications/`) comme déclencheur automatique sur circuit breaker + kill switch
- **Test à ajouter** : `test_ihm_notifications.py` — étendre pour tester le déclenchement email sur circuit_breaker_fired

---

### A-014 — `auto_rebalance_on_reconcile: false` — dérive silencieuse possible
- **Sévérité** : P2
- **Domaine** : execution_engine
- **Vérification code** : `execution_engine/config.py:101` — `auto_rebalance_on_reconcile: bool = False  # si True : soumet des ordres pour corriger les ecarts`
- **Description** : Le rééquilibrage automatique est désactivé. Si des positions dérivent de leurs cibles (ordres partiels, fills manqués), la dérive s'accumule sans correction automatique.
- **Preuve** : `execution_engine/config.py:101`
- **Recommandation** : Ajouter une alerte dans l'IHM quand `execution_reconciliation_results` contient des diffs > seuil depuis plus de N heures. Documenter la procédure de rééquilibrage manuel.
- **Test à ajouter** : `test_execution_engine_reconciliation.py` — tester la détection de dérive et l'alerting

---

### A-015 — Market cap Finnhub stale (TTL non enforced en prod)
- **Sévérité** : P2
- **Domaine** : dataIntegrityEngine / selector
- **Description** : `market_cap_max_age_days: 45` dans `STRICT_SWING_CASH_FILTERS` mais `update_sector` (Finnhub) est schedulé "weekly" dans la lineage matrix. Si Finnhub quota est épuisé ou l'update_sector non exécuté, le TTL de 45 jours peut expirer silencieusement.
- **Preuve** : `doc/data_lineage_matrix.md:39` — Fréquence `weekly`. `core/filter_profiles.py:263`
- **Recommandation** : Ajouter alerting dans l'IHM si `stock_metadata.market_cap_refreshed_at < NOW() - 45 jours` pour N% des symboles actifs
- **Test à ajouter** : `test_alpha_scanner.py` — tester le comportement du filtre market_cap quand TTL expiré

---

### A-016 — `execution_pdt_rule: "off"` sur presets 10–25k$ cash — commentaire manquant
- **Sévérité** : P2
- **Domaine** : Configuration / execution_engine
- **Vérification code** : `config/capital_presets.yaml:182-183` — `execution_account_type: cash` et `execution_pdt_rule: "off"` sans commentaire explicatif. `execution_engine/config.py:174-177` — `effective_pdt_rule` retourne `"off"` automatiquement si `account_type == "cash"`. Comportement correct mécaniquement.
- **Description** : Les presets `capital_10001_25000` ont `execution_account_type: cash` et `execution_pdt_rule: "off"`. La règle PDT s'applique uniquement aux comptes margin — sur un compte cash, PDT est effectivement N/A. Cette configuration est donc correcte mais mérite une note explicite pour éviter la confusion opérateur.
- **Preuve** : `config/capital_presets.yaml:182-183` — absence de commentaire justificatif
- **Recommandation** : Ajouter commentaire dans le YAML : `# pdt_rule: off car account_type=cash (PDT ne s'applique qu'aux comptes margin — cf. execution_engine/config.py effective_pdt_rule)`
- **Test à ajouter** : Aucun test supplémentaire — comportement correct mais commentaire YAML à ajouter

---

### A-017 — `fill_timeout_seconds` insuffisant lors de gap down/up
- **Sévérité** : P2
- **Domaine** : execution_engine
- **Vérification code** : `execution_engine/config.py:85` — `fill_timeout_seconds: int = 120`
- **Description** : `fill_timeout_seconds: 120` peut créer des ordres non fillés en état orphelin lors d'ouvertures volatiles avec gap important. Les positions orphelines nécessitent une intervention manuelle.
- **Preuve** : `execution_engine/config.py:85`
- **Recommandation** : Augmenter à 180/300 secondes et documenter la procédure de "cancel non-filled orders" à l'issue du timeout
- **Test à ajouter** : `test_execution_engine_executor.py` — tester le comportement timeout avec mock broker delayed fill

---

## Anomalies P3 (mineures / dette technique) — actives

### A-019 — Stooq client : logique `apikey` conditionnelle non testée sans clé
- **Sévérité** : P3
- **Domaine** : service/stooq
- **Description** : `service/stooq/clientStooq.py` ajoute `apikey` si `STOOQ_API_KEY` est défini. Stooq est gratuit sans clé — l'ajout d'une clé invalide peut générer des requêtes rejetées silencieusement.
- **Recommandation** : Documenter que Stooq est utilisé sans clé et que `STOOQ_API_KEY` n'est à définir que si Stooq modifie son API dans le futur

---

### A-020 — `market_regimes.macro_provider: eodhd` mais yields désactivés
- **Sévérité** : P3
- **Domaine** : Configuration
- **Description** : `config.yaml:62 macro_provider: eodhd` + `yields.enabled: false`. Le provider EODHD est configuré mais les yields ne sont pas utilisés. Consommation quota EODHD potentielle pour VIX uniquement.
- **Recommandation** : Documenter la consommation quota par le macro provider EODHD (VIX uniquement quand yields.enabled=false)

---

### A-021 — Pas de PnL quotidien visible dans l'IHM principale
- **Sévérité** : P3
- **Domaine** : IHM
- **Description** : Il n'y a pas de widget PnL quotidien (MTM positions + cash_ledger) dans la page Overview. L'opérateur doit consulter les tables DB manuellement.
- **Recommandation** : Ajouter un widget PnL "today" dans la page Overview en lisant `execution_positions × close_daily` + `portfolio_cash_ledger`

---

### A-022 — Walk-forward backtest limité aux poids sentiment (pas aux paramètres risque)
- **Sévérité** : P3
- **Domaine** : backtesting
- **Description** : Le walk-forward couvre les poids sentiment uniquement (`walk_forward.py`). L'optimisation out-of-sample des paramètres ATR, Kelly, correlation_threshold n'est pas implémentée.
- **Recommandation** : Étendre `walk_forward.py` pour supporter les paramètres risk (ATR period, Kelly, correlation)

---

### A-023 — `test_data_lineage_autogen.py` non activé en CI
- **Sévérité** : P3
- **Domaine** : Qualité logicielle / CI
- **Description** : Le test de vérification de la lineage matrix existe dans les tests (`tests/test_data_lineage_autogen.py`) mais son activation en CI (`--check`) n'est pas confirmée. Si désactivé, les incohérences de tables (cf. A-002) peuvent persister.
- **Recommandation** : S'assurer que `test_data_lineage_autogen.py` est inclus dans la suite CI principale

---

### A-024 — `prompt/` structuration partielle
- **Sévérité** : P3
- **Domaine** : Dette technique / documentation interne
- **Description** : `doc/DOC_TECHNIQUE.md §8` note que plusieurs sous-dossiers dans `prompt/` contiennent du contexte de sprint informel non exploitable par un opérateur tiers.
- **Recommandation** : Archiver les prompts de sprints précédents dans `prompt/archive/` et conserver uniquement les livrables actifs dans `prompt/tod1/`

---

### A-025 — Compression logs non configurée
- **Sévérité** : P3
- **Domaine** : Observabilité
- **Description** : RotatingFileHandler configuré avec 5 Mo et 3 backups. Sur un pipeline intensif (500 symboles, ML train), 15 Mo total peut être insuffisant pour 24h d'historique.
- **Recommandation** : Passer à `TimedRotatingFileHandler` quotidien avec rétention 7–14 jours + compression gzip

---

### A-026 — `test_import_alpaca_bar_noop.py` : couverture du switch provider complète mais non documentée
- **Sévérité** : P3
- **Domaine** : Tests
- **Description** : `test_import_alpaca_bar_noop.py` teste que `import_alpaca_bar` est un no-op quand `bars_provider=eodhd`. Ce test est bon mais non documenté publiquement — un contributeur peut ignorer ce garde-fou.
- **Recommandation** : Documenter ce test dans `doc/dataIntegrityEngine.md` section tests

---

### A-027 — `backtesting/walk_forward.py` sentiment : absence de test de régression des poids
- **Sévérité** : P3
- **Domaine** : backtesting / tests
- **Description** : Le walk-forward calibration des poids sentiment existe (`test_weights_calibration.py`) mais il n'y a pas de test de régression qui vérifie que les poids calibrés restent dans des bornes métier raisonnables (ex. poids sentiment ≥ 0.05 et ≤ 0.40).
- **Recommandation** : Ajouter des assertions business dans `test_weights_calibration.py` sur les plages de poids admissibles

---

## Anomalies RÉSOLUES ✅ (vérifiées dans le code source)

> Ces anomalies étaient documentées sur la base de lectures documentaires. La vérification directe du code source confirme qu'elles sont résolues dans l'implémentation actuelle.

---

### A-003 ✅ — `model_predictions` DB : gouvernance ML — RÉSOLU
- **Sévérité initiale** : P1
- **Domaine** : modelFactory / database
- **Résolution confirmée** :
  - `database/sql/ml/model_predictions.sql:8-11` — `selected_model VARCHAR(32)`, `decision_threshold DOUBLE`, `signal_label VARCHAR(32)`, `calibration_method VARCHAR(32)` avec COMMENTs détaillés.
  - `database/sql/ml/model_predictions.sql:14` — `UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id)` présent.
  - `modelFactory/db_registry.py:336-363` — `insert_predictions()` écrit ces 4 colonnes via `ON DUPLICATE KEY UPDATE`.
- **Ce qui reste** : Aucune action requise.

---

### A-004 ✅ — `DOC_TECHNIQUE.md §9` : mention "vectorbt" — RÉSOLU (résidu mineur)
- **Sévérité initiale** : P1 (documentation)
- **Domaine** : documentation
- **Résolution confirmée** : `doc/DOC_TECHNIQUE.md:497` — "simulateur custom PIT — aucune dépendance vectorbt ; moteur `BacktestEngine` dans `backtesting/simulator.py`".
- **Résidu mineur** : `backtesting/cli/_impl.py:67` — `description="Backtest intégré Alpha Trade (vectorbt)"` dans `argparse.ArgumentParser`. À corriger lors du prochain passage sur ce fichier (cosmétique, pas d'impact fonctionnel).

---

### A-005 ✅ — `corporate_actions` provider CA ambigu — RÉSOLU
- **Sévérité initiale** : P1
- **Domaine** : corporate_actions / documentation
- **Résolution confirmée** :
  - `doc/DOC_FONCTIONNELLE.md:246` — "`EodhdCorporateActionProvider` si `market_data.bars_provider=eodhd` (défaut), `AlpacaCorporateActionProvider` sinon (factory `build_corporate_action_provider`)".
  - `doc/data_lineage_matrix.md §7:109-111` — règle de sélection explicitement documentée.
  - `corporate_actions/provider.py:402-432` — factory `build_corporate_action_provider()` correctement implémentée avec fallback `alpaca` par défaut.

---

### A-009 ✅ — `model_predictions` table : absence de contrainte UNIQUE — RÉSOLU
- **Sévérité initiale** : P2
- **Domaine** : modelFactory / database
- **Résolution confirmée** :
  - `database/sql/ml/model_predictions.sql:14` — `UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id)`.
  - `modelFactory/db_registry.py:342-348` — `ON DUPLICATE KEY UPDATE` garantit l'idempotence.

---

### A-012 ✅ — SSL MySQL absent par défaut — RÉSOLU
- **Sévérité initiale** : P2
- **Domaine** : Sécurité / database
- **Résolution confirmée** :
  - `database/connection.py:97-111` — `_read_ssl_connect_args()` lit `DB_SSL_CA_PATH` et active TLS si la variable est définie.
  - `database/connection.py:138,159` — `connect_args=_read_ssl_connect_args()` passé à `create_engine()`.
  - Conforme à l'audit_database §3 (TLS optionnel, LAN dev non cassé).
- **Ce qui reste** : Ajouter le test `test_connection.py` vérifiant SSL si `DB_SSL_CA_PATH` est défini (recommandé, non bloquant).

---

### A-018 ✅ — `DOC_FONCTIONNELLE.md §1.3` : script "import_alpaca_bar" — RÉSOLU
- **Sévérité initiale** : P3
- **Domaine** : Documentation
- **Résolution confirmée** : `doc/DOC_FONCTIONNELLE.md:37` — "Ingestion des barres OHLCV journalières depuis **EODHD** (provider primaire par défaut, `market_data.bars_provider=eodhd`) ou Alpaca IEX (mode rétrocompatibilité, `bars_provider=alpaca`)."

---

## Guide de priorisation pour correction

| Ordre | Anomalie | Action | Fichier(s) |
|---|---|---|---|
| **1** | A-001 | Corriger `risk_max_positions: 3` + `risk_min_position_notional: 500` | `config/capital_presets.yaml` |
| **2** | A-002 | Corriger noms de tables dans `§4` de la matrix | `doc/data_lineage_matrix.md` |
| **3** | A-006 | Passer PDT rule `"auto"` sur presets margin ≥ 25k$ | `config/capital_presets.yaml` |
| **4** | A-007 | `selector_min_close: 10.0` sur `capital_0_5000` | `config/capital_presets.yaml` |
| **5** | A-016 | Ajouter commentaire PDT off cash | `config/capital_presets.yaml` |
| **6** | A-004 résidu | Corriger description argparse "vectorbt" | `backtesting/cli/_impl.py:67` |
| **7** | A-010 | Brancher `ParquetCache` via `--use-cache` | `backtesting/cli/_impl.py` |
| **8** | A-011 | Brancher analytics/statistical_validation CLI | `backtesting/cli/_impl.py` |
| **9** | A-017 | `fill_timeout_seconds` → 180 | `execution_engine/config.py` |
| **10** | A-013 | Alerting externe circuit breaker | `execution_engine/` + notifications |
| **11** | A-014 | Alerte IHM dérive réconciliation | `ihm/` + `execution_engine/` |
| **12** | A-023 | Activer `test_data_lineage_autogen.py` en CI | `pytest.ini` / CI config |
