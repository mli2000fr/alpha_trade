# 03 — Registre des Anomalies — Alpha Trade

> **Date** : mai 2026 | P0 = critique bloquant | P1 = majeur | P2 = modéré | P3 = mineur/dette tech

---

## Résumé du registre

| Total | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| 27 | 0 | 5 | 12 | 10 |

---

## Anomalies P1 (majeures)

### A-001 — `capital_0_2000_eur` : `risk_max_positions: 10` incohérent
- **Sévérité** : P1
- **Domaine** : Configuration / capital_presets
- **Description** : Le preset `capital_0_2000_eur` déclare `risk_max_positions: 10` alors que la description dit "3 lignes ≈ 600-700 € chacune" et que le capital est de ~2 000 €. Avec 10 positions à `risk_min_position_notional: 150 USD`, on obtient 1 500 USD de capital alloué minimum — mathématiquement tenu mais chaque position est sous-dimensionnée (150 USD), rendant le coût des frais relatifs prohibitifs.
- **Preuve** : `config/capital_presets.yaml:15-20` — `risk_max_positions: 10` + description "3 lignes"
- **Impact métier** : Positions de 150 USD sur compte de 2 000 € → frais de transaction Alpaca (~1 USD/trade) représentent ~0.67% = ≥ 67 bps par aller-retour → destructeur d'alpha
- **Impact technique** : Incohérence entre la description et la valeur → confusion opérateur, test `test_capital_preset_risk_overrides.py` peut ne pas détecter cette incohérence sémantique
- **Probabilité** : Certaine (valeur incorrecte dans le fichier)
- **Niveau de confiance** : Très élevé
- **Recommandation** : Corriger `risk_max_positions: 3` pour ce preset et reconfigurer `risk_min_position_notional: 500 USD` minimum
- **Test à ajouter** : `test_capital_preset_risk_overrides.py` — valider que `max_positions × min_notional ≤ 0.95 × preset.max_equity`

---

### A-002 — `data_lineage_matrix.md` : noms de tables obsolètes (execution)
- **Sévérité** : P1
- **Domaine** : Documentation / database
- **Description** : `data_lineage_matrix.md §4` utilise les noms `execution_orders` et `execution_audit_events` qui correspondent à l'ancienne architecture. Le schéma réel utilise `execution_order_requests`, `execution_broker_orders`, `execution_events`. Ce fichier est décrit comme "généré par scripts/generate_data_lineage.py" — soit le script est désynchro, soit la regénération n'a pas été faite.
- **Preuve** : `doc/data_lineage_matrix.md:68-71` vs `doc/DOC_TECHNIQUE.md §4.4` (noms canoniques) et `database/sql/execution/`
- **Impact métier** : Un opérateur qui cherche une table en incident trouvera un nom obsolète → perte de temps en production
- **Impact technique** : La CI check `python scripts/generate_data_lineage.py --check` devrait échouer si les noms sont incohérents — soit le check n'est pas actif, soit le script n'est pas à jour
- **Probabilité** : Certaine (divergence confirmée par lecture directe)
- **Niveau de confiance** : Très élevé
- **Recommandation** : Régénérer `data_lineage_matrix.md` via `scripts/generate_data_lineage.py` et activer la vérification en CI
- **Test à ajouter** : `test_data_lineage_autogen.py` — vérifier que les noms de tables dans la matrix correspondent aux tables réelles

---

### A-003 — `model_predictions` DB : gouvernance ML incomplète
- **Sévérité** : P1
- **Domaine** : modelFactory / database
- **Description** : La table `model_predictions` ne contient pas `selected_model`, `decision_threshold`, `calibration_method`, `signal_label`. Ces informations sont présentes dans les artefacts disque (`artifacts/models/<symbol>/config.json`) mais absentes de la DB. Si les artefacts disque sont perdus (rotation, crash disque), il est impossible de savoir quel modèle a produit quelle prédiction.
- **Preuve** : `doc/DOC_TECHNIQUE.md §5.5 : "Le détail de serving (selected_model, decision_threshold, signal_label, calibration_method) est présent dans les résultats en mémoire et les artefacts, mais pas encore dans le schéma SQL."`
- **Impact métier** : Perte de traçabilité des décisions d'exécution ML → audit impossible en cas d'incident de trading
- **Impact technique** : Violation du principe d'auditabilité complète. Les `risk_decisions` ne peuvent pas référencer quel modèle a produit la proba utilisée
- **Probabilité** : Certaine (lacune documentée)
- **Niveau de confiance** : Très élevé
- **Recommandation** : Migration Alembic `0029_model_predictions_governance` ajoutant `selected_model VARCHAR(32)`, `decision_threshold FLOAT`, `calibration_method VARCHAR(16)`, `signal_label VARCHAR(16)`
- **Test à ajouter** : `test_model_factory_db_registry.py` — vérifier que `model_predictions.selected_model` est non-NULL après un run de prédiction

---

### A-004 — `DOC_TECHNIQUE.md §9` : mention "vectorbt" obsolète
- **Sévérité** : P1 (documentation)
- **Domaine** : documentation
- **Description** : `DOC_TECHNIQUE.md §9 point 14` mentionne "~~Framework de backtest intégré~~ → ✅ Implémenté : module `backtesting/` (vectorbt)". Or le module `backtesting/` est 100% custom — aucun import `vectorbt` n'existe dans le code. La mention est fausse et peut amener un opérateur à installer vectorbt inutilement ou à chercher une dépendance inexistante.
- **Preuve** : `doc/DOC_TECHNIQUE.md:496` ; `backtesting/simulator.py` — aucun `import vectorbt`
- **Impact métier** : Confusion opérateur sur les dépendances réelles → perte de temps à l'onboarding
- **Impact technique** : Un `requirements.txt` généré depuis la doc inclurait une dépendance fantôme
- **Probabilité** : Certaine
- **Niveau de confiance** : Très élevé
- **Recommandation** : Corriger `DOC_TECHNIQUE.md §9 point 14` → "→ ✅ Implémenté : module `backtesting/` (simulateur custom PIT)"
- **Test à ajouter** : `test_doc_provider_alignment.py` — étendre pour vérifier l'absence de balises "vectorbt" dans la documentation

---

### A-005 — `corporate_actions` provider CA ambigu dans la lineage matrix
- **Sévérité** : P1
- **Domaine** : corporate_actions / documentation
- **Description** : `data_lineage_matrix.md §5` indique "EODHD div/split, Alpaca CA, Yahoo (cross-check)" comme source upstream de `corporate_actions_events`, avec "EODHD (primaire)" en colonne provider. Or, le `CorporateActionEngine` reçoit son provider par injection. La factory `build_corporate_action_provider` sélectionne `EodhdCorporateActionProvider` si `bars_provider=eodhd`, mais cela n'est pas évident à la lecture du moteur principal. Si `bars_provider=alpaca`, le provider CA redevient Alpaca.
- **Preuve** : `doc/data_lineage_matrix.md:81` ; `corporate_actions/engine.py` (injection de provider) ; `DOC_FONCTIONNELLE.md §2.9 : "Dividendes cash — Détection via provider (Alpaca)"`
- **Impact métier** : Confusion sur quel provider CA est réellement actif selon la configuration `bars_provider`
- **Impact technique** : Inconsistance entre DOC_FONCTIONNELLE (dit "Alpaca") et data_lineage_matrix (dit "EODHD primaire")
- **Probabilité** : Certaine (contradiction documentée)
- **Niveau de confiance** : Élevé
- **Recommandation** : Documenter la règle de sélection provider CA dans DOC_FONCTIONNELLE §2.9 : "provider CA = EODHD si `bars_provider=eodhd`, Alpaca sinon". Mettre à jour la lineage matrix.
- **Test à ajouter** : `test_corporate_actions.py` — vérifier que le provider CA change selon `bars_provider` dans la factory

---

## Anomalies P2 (modérées)

### A-006 — PDT rule off sur comptes margin ≥ 25k$
- **Sévérité** : P2
- **Domaine** : Configuration / capital_presets / execution_engine
- **Description** : Les presets `capital_25001_50000`, `capital_50001_100000`, `capital_100001_plus` ont tous `execution_pdt_rule: "off"`. Ces presets sont sur des comptes `margin`. Si l'equity chute temporairement sous 25 000 $ (drawdown), la règle PDT non activée ne bloquera pas le 4e day trade. Alpaca côté broker peut alors imposer des restrictions (minimum equity call, trading restriction 90 jours).
- **Preuve** : `config/capital_presets.yaml:230-236`, `config/capital_presets.yaml:280-286`, `config/capital_presets.yaml:330-336`
- **Impact métier** : PDT violation potentielle lors d'un drawdown → restriction de compte broker pendant 90 jours → arrêt forcé du trading
- **Recommandation** : Passer `execution_pdt_rule: "auto"` pour les presets margin et documenter le comportement en cas de fluctuation autour de 25 000 $
- **Test à ajouter** : `test_execution_config.py` — test que PDT rule auto est appliqué quand equity fluctue sous 25k$ sur compte margin

---

### A-007 — `capital_0_5000.selector_min_close: 5.0` sous le profil strict canonique
- **Sévérité** : P2
- **Domaine** : Configuration / selector
- **Description** : Le preset `capital_0_5000` a `selector_min_close: 5.0` alors que `STRICT_SWING_CASH_FILTERS.min_close = 10.0`. Les actions à 5–9 USD ont des frais relatifs disproportionnés sur Alpaca et des biais IEX plus forts.
- **Preuve** : `config/capital_presets.yaml:96` vs `core/filter_profiles.py:241`
- **Recommandation** : Uniformiser `selector_min_close: 10.0` sur tous les presets ou documenter explicitement la justification du relâchement
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

### A-009 — `model_predictions` table : absence de `run_id` unique par symbole/date
- **Sévérité** : P2
- **Domaine** : modelFactory / database
- **Description** : `model_predictions` contient `run_id` mais il n'est pas clair si une contrainte `UNIQUE (symbol, prediction_date, run_id)` existe. Des runs de prédiction répétés pour le même symbole et la même date peuvent créer des doublons.
- **Preuve** : `doc/DOC_TECHNIQUE.md §5.5` — absence de documentation sur la contrainte d'unicité
- **Recommandation** : Vérifier et ajouter une contrainte `UNIQUE (symbol, prediction_date)` ou `UNIQUE (symbol, prediction_date, run_id)` selon la sémantique souhaitée
- **Test à ajouter** : `test_model_factory_db_registry.py` — tester l'idempotence des insertions par symbole/date

---

### A-010 — ParquetCache non branché par défaut (backtesting lent sur grands datasets)
- **Sévérité** : P2
- **Domaine** : backtesting
- **Description** : `backtesting/cache.py` (`ParquetCache`) est présent mais non utilisé par défaut dans la commande `run`. Chaque backtest full recharge toutes les données depuis MySQL. Sur 2 ans, 500 symboles, cela prend plusieurs dizaines de minutes et charge significativement la DB.
- **Preuve** : `doc/DOC_TECHNIQUE.md §2.1 : "ParquetCache... Présent dans le code et les tests, mais pas encore branché par défaut à la commande run"`
- **Recommandation** : Activer `ParquetCache` comme option `--use-cache` dans la CLI, avec invalidation sur changement de dates ou de dataset_hash
- **Test à ajouter** : `test_backtesting.py` — ajouter test de performance avec cache activé vs désactivé

---

### A-011 — `analytics.py` et `statistical_validation.py` non branchés à la CLI standard
- **Sévérité** : P2
- **Domaine** : backtesting
- **Description** : Bootstrap Monte Carlo (`bootstrap_trades()`), attribution sectorielle, exports HTML interactifs et `parameter_sensitivity()` sont implémentés dans `backtesting/analytics.py` et `backtesting/statistical_validation.py` mais ne sont pas accessibles via la CLI standard `python -m backtesting run`.
- **Preuve** : `doc/DOC_TECHNIQUE.md §2.1 : "briques disponibles côté code mais non encore automatiquement branchées à la CLI standard"`
- **Recommandation** : Ajouter options `--bootstrap-samples 1000` et `--sensitivity-analysis` à la CLI
- **Test à ajouter** : `test_backtesting.py` — tester le pipeline complet avec bootstrap activé

---

### A-012 — SSL MySQL absent par défaut
- **Sévérité** : P2
- **Domaine** : Sécurité / database
- **Description** : La connexion MySQL n'utilise pas SSL par défaut. Les credentials et données de position transitent en clair sur le réseau local.
- **Preuve** : `doc/DOC_TECHNIQUE.md §6 : "Risques : pas de SSL DB par défaut"`
- **Recommandation** : Activer SSL avec certificat auto-signé minimum dans `database/connection.py`
- **Test à ajouter** : `test_connection.py` — vérifier la présence de SSL si variable `DB_SSL_CA` est définie

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
- **Description** : Le rééquilibrage automatique est désactivé. Si des positions dérivent de leurs cibles (ordres partiels, fills manqués), la dérive s'accumule sans correction automatique.
- **Preuve** : `execution_engine/config.py:101 : auto_rebalance_on_reconcile: bool = False`
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

### A-016 — `execution_pdt_rule: "off"` sur presets 10–25k$ cash
- **Sévérité** : P2
- **Domaine** : Configuration / execution_engine
- **Description** : Les presets `capital_10001_25000` ont `execution_account_type: cash` et `execution_pdt_rule: "off"`. La règle PDT s'applique uniquement aux comptes margin — sur un compte cash, PDT est effectivement N/A. Cette configuration est donc correcte mais mérite une note explicite pour éviter la confusion.
- **Preuve** : `config/capital_presets.yaml:180-185`
- **Recommandation** : Ajouter commentaire dans le YAML : "pdt_rule: off car account_type=cash (PDT ne s'applique qu'aux comptes margin)"
- **Test à ajouter** : Aucun test supplémentaire — comportement correct mais décision à documenter

---

### A-017 — `fill_timeout_seconds` insuffisant lors de gap down/up
- **Sévérité** : P2
- **Domaine** : execution_engine
- **Description** : `fill_timeout_seconds: 120` (paper) et 180 (live) peut créer des ordres non fillés en état orphelin lors d'ouvertures volatiles avec gap important. Les positions orphelines nécessitent une intervention manuelle.
- **Preuve** : `execution_engine/config.py:85` ; documentation watcher orphan adoption
- **Recommandation** : Augmenter à 180/300 secondes et documenter la procédure de "cancel non-filled orders" à l'issue du timeout
- **Test à ajouter** : `test_execution_engine_executor.py` — tester le comportement timeout avec mock broker delayed fill

---

## Anomalies P3 (mineures / dette technique)

### A-018 — `DOC_FONCTIONNELLE.md §1.3` : script d'import OHLCV nommé `import_alpaca_bar` alors que provider primaire est EODHD
- **Sévérité** : P3
- **Domaine** : Documentation
- **Description** : L'étape 1 du pipeline quotidien est encore intitulée "import_alpaca_bar" dans le texte principal §1.3 de `DOC_FONCTIONNELLE.md`, alors que le provider primaire est EODHD (`import_eodhd_bar`).
- **Preuve** : `doc/DOC_FONCTIONNELLE.md:37` vs encart provider line 8
- **Recommandation** : Mettre à jour le texte §1.3 : "import_eodhd_bar (bars OHLCV daily — provider primaire EODHD)" + note rétrocompat Alpaca

---

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
- **Description** : `doc/DOC_TECHNIQUE.md §8` note : "prompt/execution/ : historique audit → plan → sprints → cutover désormais structuré ; homogénéisation du reste de prompt/ encore perfectible". Plusieurs sous-dossiers dans `prompt/` contiennent du contexte de sprint informel non exploitable par un opérateur tiers.
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

