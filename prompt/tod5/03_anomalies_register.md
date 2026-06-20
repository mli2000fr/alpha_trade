# 03 — Anomalies Register

> **Registre exhaustif des anomalies classées par sévérité P0→P3**

---

## Légende

| Sévérité | Définition |
|---|---|
| **P0** | Bloquant — risque immédiat pour la production, la sécurité ou l'intégrité des données |
| **P1** | Majeur — impact significatif sur la fiabilité, la cohérence ou la performance |
| **P2** | Modéré — impact limité mais mérite correction dans les sprints à venir |
| **P3** | Mineur — amélioration continue, dette technique, cosmétique |

---

## Anomalies P0 (Bloquantes)

### A-CAP-001 — ~~Presets capital : `execution_swing_only=false` sur tous les presets~~ ✅ RÉSOLU (Changement réglementaire FINRA 2026-06-04)
- **Sévérité** : ~~P0~~ → **RÉSOLU**
- **Domaine** : Configuration / Presets capital
- **Description** : ~~Tous les presets de capital (micro-compte à 100k$+) utilisent `execution_swing_only: false`. Pour les comptes cash (≤25k$), le swing-only devrait être obligatoire car les comptes cash ne peuvent pas day-trader efficacement.~~
- **Résolution** : La **règle PDT (Pattern Day Trader)** a été **officiellement supprimée par la FINRA le 4 juin 2026**. Alpaca a mis à jour sa plateforme. Il n'y a plus de limite de 3 day trades par période de 5 jours, ni d'exigence de capital minimum de 25 000 $. L'achat et la vente d'un même titre dans la même journée sont désormais autorisés sans restriction, quel que soit le montant du compte. **`execution_swing_only=false` est donc le bon paramétrage pour tous les presets.**
- **Preuve** : FINRA Regulatory Notice 2026-06-04 ; Alpaca Markets Platform Update June 2026.
- **Impact métier** : N/A — l'anomalie est résolue par le changement réglementaire.
- **Impact technique** : Les presets sont **déjà corrects**. C'est l'IHM qui doit être mise à jour (son défaut `execution_swing_only=True` est désormais trop restrictif).
- **Probabilité** : N/A.
- **Niveau de confiance** : Élevé (100%).
- **Recommandation** : ~~Mettre `execution_swing_only: true` pour les presets ≤25k$~~ → **Ne rien changer aux presets**. Mettre à jour l'IHM pour que le défaut soit `execution_swing_only=false` (aligné sur la nouvelle réalité réglementaire).
- **Test associé** : ~~Voir bloc test T-CAP-001 ci-dessous.~~ → Test inversé : vérifier que l'IHM a bien `swing_only=false` par défaut.

**Bloc test T-CAP-001 (révisé)** :
- **Objectif** : Vérifier que le défaut IHM pour `execution_swing_only` est `false` (post-PDT)
- **Type** : Test IHM (intégration)
- **Priorité** : P1
- **Module(s)** : `ihm/services/pipeline_runner.py`
- **Fichier probable** : `tests/test_ihm_cli_contract.py` (étendre)
- **Scénario** :
  - Given : `PipelineLaunchOptions()` instanciée avec les défauts
  - When : on lit `execution_swing_only`
  - Then : la valeur par défaut doit être `false` (conforme à la réglementation post-PDT)
- **Fixtures** : `PipelineLaunchOptions()`
- **Oracle** : `execution_swing_only == false`
- **Régression empêchée** : Retour à un défaut `true` obsolète

---

### A-CAP-002 — ~~Paramètres de drawdown breaker identiques pour toutes les tranches~~ ✅ RÉSOLU (Sprint S8)
- **Sévérité** : ~~P0~~ → **RÉSOLU**
- **Domaine** : Configuration / Risk
- **Résolution** : Les paramètres `degraded_entry_allocation_pct`, `ramp_up_pct_per_day` et `ramp_up_max_pct` sont désormais différenciés par tranche de capital (micro : 0.05/0.05/0.20 → 100k$+ : 0.15/0.10/0.60). Les équivalents `backtesting_dd_*` sont alignés. Tests T-CAP-002 et T-CAP-005 validés.
- **Test associé** : T-CAP-002 ✅, T-CAP-005 ✅

**Bloc test T-CAP-002** :
- **Objectif** : Vérifier que les paramètres de drawdown breaker sont croissants avec le capital
- **Type** : Test de configuration (config)
- **Priorité** : P0
- **Module(s)** : `common/capital_presets.py`
- **Fichier probable** : `tests/test_capital_presets_consistency.py` (étendre)
- **Scénario** :
  - Given : les presets chargés et triés par `min_equity` croissant
  - When : on compare `degraded_entry_allocation_pct` et `ramp_up_max_pct` entre tranches adjacentes
  - Then : les valeurs doivent être non-décroissantes (ou documentées si décroissantes)
- **Fixtures** : Presets depuis `config/capital_presets.yaml`
- **Oracle** : `preset[i].degraded_allocation <= preset[i+1].degraded_allocation` (ou justification documentée)
- **Régression empêchée** : Paramètre incohérent pour une tranche
- **Si le test existe partiellement** : `test_capital_presets_consistency.py` existe, ajouter ce check

---

### A-CAP-003 — ~~`risk_min_position_notional` à 150$ < minimum Alpaca (155$)~~ ✅ RÉSOLU (Sprint S8)
- **Sévérité** : ~~P0~~ → **RÉSOLU**
- **Domaine** : Configuration / Exécution
- **Résolution** : `risk_min_position_notional` du preset `capital_2001_5000` remonté de 150 $ à 155 $. Tous les presets ont désormais `risk_min_position_notional ≥ 155`. Test T-CAP-003 validé.
- **Test associé** : T-CAP-003 ✅

**Bloc test T-CAP-003** :
- **Objectif** : Vérifier que tous les `risk_min_position_notional` ≥ `enforce_min_notional`
- **Type** : Test de configuration (config)
- **Priorité** : P0
- **Module(s)** : `common/capital_presets.py`
- **Fichier probable** : `tests/test_capital_presets_consistency.py` (étendre)
- **Scénario** :
  - Given : `config.yaml` chargé, `capital_presets.yaml` chargé
  - When : pour chaque preset, on compare `risk_min_position_notional` avec `market_regimes.enforce_min_notional`
  - Then : `risk_min_position_notional >= enforce_min_notional` pour tous les presets
- **Fixtures** : `load_config()`, preset loader
- **Oracle** : Assertion de comparaison
- **Régression empêchée** : Introduction d'un notionnel trop bas

---

## Anomalies P1 (Majeures)

### A-IHM-001 — Défauts IHM incohérents avec les presets capital (post-PDT)
- **Sévérité** : P1
- **Domaine** : IHM / Configuration
- **Description** : L'IHM (`pipeline_runner.py`) définit `execution_swing_only=True` comme défaut de `PipelineLaunchOptions`, mais les presets capital utilisent `swing_only=false` — ce qui est le **bon choix** depuis la suppression de la règle PDT par la FINRA (4 juin 2026). Le défaut IHM `True` est désormais **trop restrictif** et empêche le day trading pourtant autorisé. L'opérateur qui ne modifie pas ce flag dans l'IHM sera bridé inutilement.
- **Preuve** : `ihm/services/pipeline_runner.py` — `execution_swing_only: bool = True` vs `config/capital_presets.yaml` — tous les presets avec `execution_swing_only: false`.
- **Impact métier** : Restriction injustifiée du day trading → opportunités manquées.
- **Impact technique** : Incohérence IHM↔presets non détectée automatiquement ; l'IHM est en retard sur la réalité réglementaire.
- **Probabilité** : Élevée (le défaut IHM sera utilisé par tout nouvel opérateur).
- **Niveau de confiance** : Élevé (95%).
- **Recommandation** : Changer le défaut IHM de `execution_swing_only=True` à `execution_swing_only=False`. Ajouter un bandeau d'avertissement dans l'IHM quand les paramètres divergent du preset.
- **Test associé** : Voir bloc test T-IHM-001.

**Bloc test T-IHM-001 (révisé)** :
- **Objectif** : Vérifier que le défaut IHM `execution_swing_only` est `false` (post-PDT)
- **Type** : Test d'intégration IHM
- **Priorité** : P1
- **Module(s)** : `ihm/services/pipeline_runner.py`, `common/capital_presets.py`
- **Fichier probable** : `tests/test_ihm_cli_contract.py` (étendre)
- **Scénario** :
  - Given : `PipelineLaunchOptions()` instanciée avec les défauts
  - When : on lit `execution_swing_only`
  - Then : la valeur doit être `false` (conforme à la réglementation post-PDT FINRA 2026-06-04)
- **Fixtures** : `PipelineLaunchOptions()`
- **Oracle** : `execution_swing_only == false`
- **Régression empêchée** : Restauration d'un défaut `true` obsolète

---

### A-DOC-001 — ~~`DOC_FONCTIONNELLE.md` : valeurs de filtres obsolètes~~ ✅ RÉSOLU (Sprint S10)
- **Sévérité** : ~~P1~~ → **RÉSOLU**
- **Domaine** : Documentation
- **Résolution** : `DOC_FONCTIONNELLE.md` et `DOC_TECHNIQUE.md` mis à jour avec les sprints S8-S14, le contexte post-PDT FINRA, et les valeurs canoniques actuelles. Aucune valeur historique ambiguë restante.

**Bloc test T-DOC-001** :
- **Objectif** : Vérifier que les valeurs numériques dans `DOC_FONCTIONNELLE.md` correspondent au code
- **Type** : Test de documentation (non-régression)
- **Priorité** : P1
- **Module(s)** : Documentation ↔ Code
- **Fichier probable** : `tests/test_docs_provider_consistency.py` (étendre)
- **Scénario** :
  - Given : `STRICT_SWING_CASH_FILTERS` chargé depuis le code
  - When : on parse `DOC_FONCTIONNELLE.md` pour extraire les valeurs numériques documentées
  - Then : les valeurs correspondent à celles du code source
- **Fixtures** : Fichiers doc et code
- **Oracle** : Pas de divergence non documentée
- **Régression empêchée** : Mise à jour du code sans mise à jour de la doc
- **Si le test existe partiellement** : `test_docs_provider_consistency.py` existe, étendre pour les valeurs numériques

---

### A-ML-001 — Complexité ML excessive exposée dans l'IHM
- **Sévérité** : P1
- **Domaine** : ModelFactory / IHM
- **Description** : L'IHM expose 30+ paramètres ML (défauts `DEFAULT_ML_*` dans `pipeline_runner.py`). La plupart ne sont pas compréhensibles par un opérateur non-ML. Le risque de mauvaise configuration est élevé.
- **Preuve** : `ihm/services/pipeline_runner.py` — 80+ constantes `DEFAULT_ML_*` et `RECOMMENDED_ML_*`.
- **Impact métier** : Opérateur qui modifie des hyperparamètres sans comprendre → modèle dégradé → mauvaises décisions de trading.
- **Impact technique** : Surface de configuration trop large, maintenance coûteuse.
- **Probabilité** : Moyenne.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Créer un mode « Expert ML » dans l'IHM qui cache les paramètres avancés par défaut. Ne garder que 5-6 paramètres essentiels en mode standard.
- **Test associé** : Voir bloc test T-ML-001.

**Bloc test T-ML-001** :
- **Objectif** : Vérifier que le nombre de paramètres ML exposés dans l'IHM est raisonnable
- **Type** : Test IHM (E2E)
- **Priorité** : P1
- **Module(s)** : `ihm/services/pipeline_runner.py`
- **Fichier probable** : `tests/test_ihm_pipeline_runner.py` (étendre)
- **Scénario** :
  - Given : `PipelineLaunchOptions` instanciée
  - When : on compte les champs liés au ML (préfixe `ml_`)
  - Then : il y a ≤ 15 champs ML exposés en mode standard
- **Fixtures** : `PipelineLaunchOptions()`
- **Oracle** : `len(ml_fields) <= 15` en mode standard
- **Régression empêchée** : Ajout non maîtrisé de paramètres ML

---

### A-EXE-001 — `execution_engine/__main__.py` déprécié mais toujours présent
- **Sévérité** : P1
- **Domaine** : Execution Engine
- **Description** : `python -m execution_engine` est documenté comme « façade de compatibilité » et émet un `DeprecationWarning`, mais le point d'entrée reste fonctionnel. Cela crée une confusion pour l'opérateur qui pourrait utiliser l'ancien chemin.
- **Preuve** : `execution_engine/__main__.py`, `doc/execution_engine.md` §3 — « Déprécié : émet un DeprecationWarning et délègue vers run_execution.py ».
- **Impact métier** : Opérateur utilisant l'ancien chemin → comportement potentiellement différent.
- **Impact technique** : Code mort, confusion de maintenance.
- **Probabilité** : Faible.
- **Niveau de confiance** : Élevé (90%).
- **Recommandation** : Supprimer `__main__.py` après une période de transition, ou le rendre strictement équivalent à `run_execution.py`.
- **Test associé** : Voir bloc test T-EXE-001.

**Bloc test T-EXE-001** :
- **Objectif** : Vérifier que `python -m execution_engine` et `python run_execution.py` produisent le même comportement
- **Type** : Test d'intégration CLI
- **Priorité** : P1
- **Module(s)** : `execution_engine/__main__.py`, `run_execution.py`
- **Fichier probable** : `tests/test_execution_cli_cancel_all.py` (étendre)
- **Scénario** :
  - Given : mêmes arguments passés aux deux points d'entrée
  - When : on exécute `run_execution.py simulate` et `python -m execution_engine --broker-mode paper --dry-run`
  - Then : le comportement est identique (mêmes effets de bord DB)
- **Fixtures** : DB de test, mock broker
- **Oracle** : Équivalence fonctionnelle
- **Régression empêchée** : Divergence entre les deux points d'entrée

---

### A-CA-001 — ~~Pas de cross-check automatique multi-provider pour les corporate actions~~ ✅ RÉSOLU (Sprint S13)
- **Sévérité** : ~~P1~~ → **RÉSOLU**
- **Domaine** : Corporate Actions
- **Résolution** : Le cross-check Yahoo Finance est désormais activé par défaut (`--cross-check yahoo` pour `sync` et `run`). Les divergences sont loggées et remontées dans les run summaries. Best-effort, jamais bloquant (si `yfinance` absent, désactivé silencieusement). Tests T-CA-001 passent (7/7 ✅).

**Bloc test T-CA-001** :
- **Objectif** : Vérifier que le cross-check Yahoo fonctionne et détecte les écarts
- **Type** : Test d'intégration
- **Priorité** : P1
- **Module(s)** : `corporate_actions/cross_check_yahoo.py`, `corporate_actions/engine.py`
- **Fichier probable** : `tests/test_corporate_actions_cross_check_yahoo.py` (existe, à étendre)
- **Scénario** :
  - Given : un symbole avec un dividende connu (ex: AAPL)
  - When : on exécute le cross-check entre EODHD et Yahoo
  - Then : les événements sont identiques ou les divergences sont loggées
- **Fixtures** : Mock des APIs EODHD et Yahoo
- **Oracle** : Liste d'événements identique ou divergences tracées
- **Régression empêchée** : Perte de détection des divergences CA

---

### A-BACK-001 — ~~Cache Parquet non branché par défaut~~ ✅ RÉSOLU (Sprint S11)
- **Sévérité** : ~~P1~~ → **RÉSOLU**
- **Domaine** : Backtesting
- **Résolution** : Le cache Parquet est désormais actif par défaut (`--no-cache` pour désactiver). La microstructure est activée avec slippage `sqrt` (2 bps base + 5 bps impact), gap 3%. Les commissions sont modélisées par palier de capital (`TieredCommissionConfig`). Bootstrap Monte Carlo activé (500 itérations).

**Bloc test T-BACK-001** :
- **Objectif** : Vérifier que le cache Parquet accélère le chargement des données
- **Type** : Test de performance
- **Priorité** : P1
- **Module(s)** : `backtesting/cache.py`, `backtesting/data_loader.py`
- **Fichier probable** : `tests/test_backtesting.py` (étendre)
- **Scénario** :
  - Given : un jeu de données OHLCV en base
  - When : on exécute deux backtests identiques, le second avec cache
  - Then : le second est au moins 2x plus rapide que le premier
- **Fixtures** : DB de test avec données OHLCV
- **Oracle** : `time(cached) < 0.5 * time(uncached)`
- **Régression empêchée** : Dégradation des performances de backtest

---

### A-RISK-001 — Poids de conviction (40% quant, 60% ML) non justifiés empiriquement
- **Sévérité** : P1
- **Domaine** : Risk Management
- **Description** : Les presets ≥10k$ utilisent `risk_score_weight=0.4` et `risk_prediction_weight=0.6` (60% ML). Ce poids majoritaire donné au ML n'est pas justifié par une étude d'ablation ou une validation out-of-sample. Le risque est de sur-pondérer des prédictions ML potentiellement overfittées.
- **Preuve** : `config/capital_presets.yaml` — presets `capital_10001_25000` et supérieurs : `risk_score_weight: 0.4`, `risk_prediction_weight: 0.6`.
- **Impact métier** : Décisions de trading biaisées vers un ML non validé → performance dégradée.
- **Impact technique** : Absence de validation empirique des poids de fusion.
- **Probabilité** : Moyenne.
- **Niveau de confiance** : Moyen (70%).
- **Recommandation** : Réaliser une ablation des poids de conviction sur données out-of-sample et documenter les résultats. Par défaut, revenir à 50/50 tant que la validation n'est pas faite.
- **Test associé** : Voir bloc test T-RISK-001.

**Bloc test T-RISK-001** :
- **Objectif** : Vérifier que les poids de conviction sont supportés par une ablation documentée
- **Type** : Test de non-régression (data quality)
- **Priorité** : P1
- **Module(s)** : `risk_management/conviction.py`, `common/capital_presets.py`
- **Fichier probable** : `tests/test_conviction_weights_config.py` (existe, à étendre)
- **Scénario** :
  - Given : les artefacts d'ablation dans `artifacts/ablation/`
  - When : on vérifie que les poids configurés dans les presets correspondent au meilleur scénario d'ablation
  - Then : les poids sont dans l'intervalle de confiance du meilleur scénario
- **Fixtures** : Fichiers d'ablation YAML/JSON
- **Oracle** : Les poids configurés sont justifiés par l'ablation
- **Régression empêchée** : Changement des poids sans validation

---

### A-IHM-002 — Pas de validation IHM que les paramètres sont cohérents avec le preset actif
- **Sévérité** : P1
- **Domaine** : IHM
- **Description** : L'IHM ne vérifie pas que les paramètres saisis par l'opérateur sont cohérents avec le preset de capital détecté. L'opérateur peut entrer `execution_account_type=margin` avec un capital de 2000$ sans avertissement.
- **Preuve** : `ihm/services/pipeline_runner.py` — `PipelineLaunchOptions` accepte n'importe quelle combinaison sans validation croisée.
- **Impact métier** : Configuration incohérente → exécution dangereuse.
- **Impact technique** : Absence de garde-fou IHM.
- **Probabilité** : Moyenne.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Ajouter une validation dans `PipelineLaunchOptions.__post_init__` qui vérifie la cohérence avec le preset.
- **Test associé** : Voir bloc test T-IHM-002.

**Bloc test T-IHM-002** :
- **Objectif** : Vérifier que l'IHM rejette les combinaisons incohérentes
- **Type** : Test IHM (intégration)
- **Priorité** : P1
- **Module(s)** : `ihm/services/pipeline_runner.py`
- **Fichier probable** : `tests/test_ihm_pipeline_runner.py` (étendre)
- **Scénario** :
  - Given : un preset micro-compte (cash, ≤2000€)
  - When : on tente de créer `PipelineLaunchOptions(execution_account_type='margin')`
  - Then : une exception ou un avertissement est levé
- **Fixtures** : Preset loader mocké
- **Oracle** : `ValueError` ou warning émis
- **Régression empêchée** : Configuration dangereuse silencieuse

---

### A-DATA-001 — `stock_bars` et `stock_bars_daily` : risque de confusion
- **Sévérité** : P1
- **Domaine** : dataIntegrityEngine / Database
- **Description** : Deux tables stockent des barres OHLCV daily : `stock_bars` (brutes, par provider) et `stock_bars_daily` (nettoyées, source unique). La PK `(symbol, date)` sur `stock_bars_daily` avec `data_source` comme colonne non-PK peut créer de la confusion. Si un symbole a des données dans les deux sources, seule la dernière écrite est conservée.
- **Preuve** : `doc/data_lineage_matrix.md` — « La colonne data_source trace la provenance, mais n'autorise pas une cohabitation simultanée multi-provider pour un même couple (symbol,date) sans migration dédiée. »
- **Impact métier** : Données écrasées silencieusement en cas de double écriture.
- **Impact technique** : Design de schéma perfectible.
- **Probabilité** : Faible (no-op explicite empêche la double écriture).
- **Niveau de confiance** : Moyen (75%).
- **Recommandation** : Ajouter une contrainte d'unicité sur `(symbol, date, data_source)` si la cohabitation multi-source devient nécessaire, ou documenter clairement que la source unique est un invariant.
- **Test associé** : Voir bloc test T-DATA-001.

**Bloc test T-DATA-001** :
- **Objectif** : Vérifier que la double écriture multi-provider est impossible
- **Type** : Test SQL / intégration
- **Priorité** : P1
- **Module(s)** : `dataIntegrityEngine/`, `database/`
- **Fichier probable** : `tests/test_data_source_consistency_runtime.py` (existe, à étendre)
- **Scénario** :
  - Given : `bars_provider=eodhd`
  - When : on tente d'exécuter `import_alpaca_bar` puis `import_eodhd_bar` sur le même symbole/date
  - Then : le second import est no-op (si même source) ou échoue (si source différente)
- **Fixtures** : DB de test
- **Oracle** : Une seule ligne par `(symbol, date)` dans `stock_bars_daily`
- **Régression empêchée** : Double écriture multi-provider

---

### A-CONV-001 — Poids de fusion sentiment (75/15/10) non justifiés
- **Sévérité** : P1
- **Domaine** : Event Sentiment / Risk
- **Description** : Les poids de fusion `conviction.quant_weight=0.75`, `sentiment_weight=0.15`, `macro_weight=0.10` dans `config.yaml` et la fusion `75% quant + 15% sentiment + 10% macro` documentée ne sont pas justifiés par une calibration out-of-sample.
- **Preuve** : `config.yaml` bloc `conviction`, `doc/DOC_FONCTIONNELLE.md` §2.3.
- **Impact métier** : Poids sous-optimaux → sélection dégradée.
- **Impact technique** : Paramètres arbitraires.
- **Probabilité** : Moyenne.
- **Niveau de confiance** : Moyen (65%).
- **Recommandation** : Documenter la calibration qui a mené à ces poids, ou lancer une calibration walk-forward.
- **Test associé** : Voir bloc test T-CONV-001.

**Bloc test T-CONV-001** :
- **Objectif** : Vérifier que les poids de fusion sont documentés et justifiés
- **Type** : Test de documentation
- **Priorité** : P1
- **Module(s)** : `event_sentiment/`, `core/conviction.py`
- **Fichier probable** : `tests/test_conviction_weights_config.py` (existe)
- **Scénario** :
  - Given : les poids dans `config.yaml`
  - When : on vérifie la présence d'un rapport de calibration
  - Then : un fichier `artifacts/ablation/conviction_weights.md` ou équivalent existe
- **Fixtures** : Fichier d'ablation
- **Oracle** : Le rapport existe et justifie les poids
- **Régression empêchée** : Poids arbitraires non documentés

---

## Anomalies P2 (Modérées)

### A-DOC-002 — Documentation muette sur les plans v2 en cours
- **Sévérité** : P2
- **Domaine** : Documentation
- **Description** : `DOC_TECHNIQUE.md` mentionne le « Plan v2 -- Short Selling (Sprint 0-5) » et le « Plan ML v2 -- Ternaire long/flat/short (Sprint 1-7) » mais sans indiquer clairement leur statut d'implémentation. Un développeur pourrait croire que ces fonctionnalités sont déjà en production.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §0 — sections « Plan v2 ».
- **Impact métier** : Confusion sur les capacités réelles de l'application.
- **Impact technique** : Dette documentaire.
- **Probabilité** : Moyenne.
- **Niveau de confiance** : Élevé (90%).
- **Recommandation** : Ajouter un statut clair (⏳ En cours / ✅ Livré / 🔮 Planifié) pour chaque plan.
- **Test associé** : Test de documentation (vérifier que chaque plan a un statut).

---

### A-CAP-004 — `execution_account_type` bascule brutalement de `cash` à `margin` à 25k$
- **Sévérité** : P2
- **Domaine** : Configuration
- **Description** : Les presets ≤25k$ utilisent `execution_account_type: cash`, les presets ≥25k$ utilisent `margin`. Le seuil de 25k$ correspond au minimum PDT (Pattern Day Trader) aux US, mais le swing trading ne nécessite pas forcément un compte margin. La transition est brutale et non documentée.
- **Preuve** : `config/capital_presets.yaml` — comparer les champs `execution_account_type` entre `capital_10001_25000` (cash) et `capital_25001_50000` (margin).
- **Impact métier** : Changement de comportement d'exécution à la transition.
- **Impact technique** : Manque de progressivité.
- **Probabilité** : Faible.
- **Niveau de confiance** : Moyen (75%).
- **Recommandation** : Documenter le rationnel du seuil, ou permettre le margin pour les comptes ≥10k$ avec un warning.
- **Test associé** : Test de configuration.

---

### A-ML-002 — Pas de procédure documentée de rollback champion ML
- **Sévérité** : P2
- **Domaine** : ModelFactory
- **Description** : Le système de champion sélection peut automatiquement changer le modèle servi. Si le nouveau champion dégrade la performance, il n'y a pas de procédure documentée pour revenir au précédent.
- **Preuve** : `modelFactory/champion_selection.py`, `modelFactory/auto_rollback.py` — le module d'auto-rollback existe mais sa procédure opérationnelle n'est pas documentée.
- **Impact métier** : Dégradation non contrôlée des prédictions.
- **Impact technique** : Manque de documentation opérationnelle.
- **Probabilité** : Faible.
- **Niveau de confiance** : Moyen (70%).
- **Recommandation** : Documenter la procédure de rollback dans `doc/ml.md` et tester l'auto-rollback en conditions réelles.
- **Test associé** : Test E2E de rollback.

---

### A-BACK-002 — Frais de transaction fixes par preset, pas de modèle réaliste
- **Sévérité** : P2
- **Domaine** : Backtesting
- **Description** : Les frais de transaction sont modélisés par des bps fixes (`backtesting_commission_bps_stress`, `backtesting_slippage_bps_stress`) sans tenir compte du type d'ordre (limit vs market), de la liquidité du titre, ou de la taille de l'ordre.
- **Preuve** : `config/capital_presets.yaml` — champs `backtesting_commission_bps_stress` et `backtesting_slippage_bps_stress`.
- **Impact métier** : Surestimation ou sous-estimation des coûts réels.
- **Impact technique** : Modèle de coûts simpliste.
- **Probabilité** : Élevée pour les petits comptes.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Implémenter un modèle de slippage volume-aware (le module `microstructure.py` existe mais n'est pas branché par défaut).
- **Test associé** : Test de parité backtest/live sur les coûts.

---

### A-IHM-003 — Pas de mode « lecture seule » dans l'IHM
- **Sévérité** : P2
- **Domaine** : IHM
- **Description** : L'IHM permet de lancer des actions (pipeline, exécution) sans mode de confirmation ou lecture seule. Un clic accidentel peut déclencher une exécution.
- **Preuve** : `ihm/pages/pipeline.py` — boutons d'action sans garde-fou.
- **Impact métier** : Actions accidentelles.
- **Impact technique** : UX perfectible.
- **Probabilité** : Faible.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Ajouter un mode « lecture seule » et une confirmation pour les actions dangereuses.
- **Test associé** : Test E2E IHM.

---

### A-CAP-005 — Preset `capital_0_2000` en EUR mais le reste en USD
- **Sévérité** : P2
- **Domaine** : Configuration
- **Description** : Le premier preset est libellé en EUR (`0 → 2 000 €`) tandis que tous les autres sont en USD. La conversion n'est pas documentée. Le `min_equity` est 0 et `max_equity` est 2000 — mais 2000 quoi ? EUR ou USD ?
- **Preuve** : `config/capital_presets.yaml` — `label: 0 → 2 000 € (micro-compte)`, `max_equity: 2000`. Le preset suivant : `label: 2 001 → 5 000 $`, `min_equity: 2000.01`.
- **Impact métier** : Trou de couverture entre 2000 et 2000.01 si la devise n'est pas claire.
- **Impact technique** : Ambiguïté de devise.
- **Probabilité** : Faible.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Uniformiser en USD avec conversion explicite, ou ajouter un champ `currency`.
- **Test associé** : Test de configuration.

---

### A-OBS-001 — Pas de JSON logging
- **Sévérité** : P2
- **Domaine** : Observabilité
- **Description** : Les logs sont en format texte simple. Pour une exploitation professionnelle, le JSON logging faciliterait l'ingestion dans des systèmes de monitoring (ELK, Grafana).
- **Preuve** : `common/utils.py` — `RotatingFileHandler` avec format texte.
- **Impact métier** : Difficulté à monitorer et alerter automatiquement.
- **Impact technique** : Format de log non structuré.
- **Probabilité** : N/A (amélioration continue).
- **Niveau de confiance** : Élevé (90%).
- **Recommandation** : Ajouter un formatteur JSON optionnel.
- **Test associé** : Test de format de log.

---

### A-CODE-001 — Fichier `pipeline_runner.py` très long
- **Sévérité** : P2
- **Domaine** : Qualité logicielle
- **Description** : `ihm/services/pipeline_runner.py` contient plus de 80 constantes de défaut et une dataclass massive (`PipelineLaunchOptions` avec 40+ champs). La maintenance devient difficile.
- **Preuve** : `ihm/services/pipeline_runner.py` — fichier de plusieurs centaines de lignes.
- **Impact métier** : Maintenance ralentie.
- **Impact technique** : Dette technique.
- **Probabilité** : N/A.
- **Niveau de confiance** : Élevé (90%).
- **Recommandation** : Scinder en sous-modules : `pipeline_defaults.py`, `pipeline_options.py`, `pipeline_commands.py`.
- **Test associé** : Test de refactor (non-régression).

---

### A-SEC-001 — Pas de chiffrement des données sensibles en base
- **Sévérité** : P2
- **Domaine** : Sécurité
- **Description** : Les données en base (positions, trades, P&L) ne sont pas chiffrées. En cas de compromission de la DB, l'historique de trading est exposé.
- **Preuve** : Revue du schéma SQL — pas de colonnes chiffrées.
- **Impact métier** : Exposition de données confidentielles.
- **Impact technique** : Absence de chiffrement at-rest.
- **Probabilité** : Faible.
- **Niveau de confiance** : Élevé (85%).
- **Recommandation** : Chiffrer les colonnes sensibles (P&L, positions) avec AES-256.
- **Test associé** : Test de chiffrement/déchiffrement.

---

## Anomalies P3 (Mineures)

### A-DOC-003 — Incohérence de nommage : `selector_min_ibd_rs_rank` vs `selector_min_relative_strength_index`
- **Sévérité** : P3
- **Domaine** : Configuration
- **Description** : Deux noms pour le même paramètre dans `capital_presets.yaml`. Le code gère l'alias (`capital_presets.py:_extract_selector_rs_value`) mais cela crée de la confusion.
- **Preuve** : `config/capital_presets.yaml` — certains presets utilisent `selector_min_ibd_rs_rank`, d'autres `selector_min_relative_strength_index`. `common/capital_presets.py` gère la dualité.
- **Recommandation** : Uniformiser sur un seul nom et supprimer l'alias.
- **Test associé** : Test de cohérence des noms de champs.

### A-DOC-004 — `DOC_TECHNIQUE.md` mentionne `fallback_on_failure` supprimé
- **Sévérité** : P3
- **Domaine** : Documentation
- **Description** : `DOC_TECHNIQUE.md` et `dataIntegrityEngine.md` mentionnent que `fallback_on_failure` a été supprimé, mais la doc continue d'en parler, ce qui pourrait semer le doute.
- **Preuve** : `doc/dataIntegrityEngine.md` — « ❌ Pas de fallback automatique inter-provider : le flag historique market_data.fallback_on_failure a été retiré de config.yaml en S0. »
- **Recommandation** : Supprimer toute mention de `fallback_on_failure` ou la déplacer dans un CHANGELOG historique.

### A-CODE-002 — Import `selector.strict_filter_profiles` déprécié mais toujours utilisé
- **Sévérité** : P3
- **Domaine** : Qualité logicielle
- **Description** : `selector/strict_filter_profiles.py` est un alias rétrocompatible vers `core/filter_profiles.py`. L'IHM l'utilise encore (`ihm/services/pipeline_runner.py:19`).
- **Preuve** : `selector/strict_filter_profiles.py`, `ihm/services/pipeline_runner.py` ligne 19.
- **Recommandation** : Migrer tous les imports vers `core.filter_profiles`.

### A-CAP-006 — `screener_first_pass_window_days` incohérent entre presets
- **Sévérité** : P3
- **Domaine** : Configuration
- **Description** : La valeur de `screener_first_pass_window_days` varie de 252 (micro-compte) à 400 (≥25k$) sans justification claire de l'impact.
- **Preuve** : `config/capital_presets.yaml`.
- **Recommandation** : Documenter l'impact de ce paramètre ou l'uniformiser.

### A-ML-003 — `ml_global_model_name` par défaut à `catboost` mais CatBoost est optionnel
- **Sévérité** : P3
- **Domaine** : ModelFactory
- **Description** : L'IHM définit `ml_global_model_name="catboost"` par défaut mais `ml_enable_global_model=False`. Si l'opérateur active le global model, CatBoost sera utilisé mais pourrait ne pas être installé.
- **Preuve** : `ihm/services/pipeline_runner.py` — `ml_global_model_name: MLGlobalModelName = "catboost"`, `ml_enable_global_model: bool = False`.
- **Recommandation** : Vérifier la disponibilité de CatBoost avant de le proposer.

### A-DATA-002 — `stock_metadata.market_cap` figé (Finnhub free)
- **Sévérité** : P3
- **Domaine** : dataIntegrityEngine
- **Description** : La market cap provient de Finnhub free et est notoirement peu fiable pour les small caps. Un TTL est appliqué mais la qualité sous-jacente reste limitée.
- **Preuve** : `doc/data_lineage_matrix.md` — « Finnhub free figé ; consommé avec TTL via market_cap_refreshed_at depuis Phase 3. »
- **Recommandation** : Ajouter EODHD comme source alternative de fondamentaux.

### A-IHM-004 — Les logs IHM ne sont pas affichés dans l'interface
- **Sévérité** : P3
- **Domaine** : IHM
- **Description** : Les logs des sous-processus lancés depuis l'IHM sont écrits dans des fichiers mais pas affichés en temps réel dans l'interface.
- **Preuve** : `ihm/services/pipeline_runner.py` — les logs sont capturés dans `artifacts/ihm_pipeline_runs/`.
- **Recommandation** : Afficher un flux de logs en temps réel dans l'IHM.

### A-TEST-001 — Pas de test de mutation exécuté en CI
- **Sévérité** : P3
- **Domaine** : Qualité logicielle
- **Description** : `mutmut` est configuré dans `pyproject.toml` mais n'est pas exécuté en CI.
- **Preuve** : `pyproject.toml` — dépendance `mutmut>=2.5` dans le groupe `mutation`. Pas de workflow GitHub Actions pour les tests de mutation.
- **Recommandation** : Ajouter un job de mutation testing en CI (hebdomadaire).

### A-TEST-002 — Pas de test de performance
- **Sévérité** : P3
- **Domaine** : Qualité logicielle
- **Description** : Aucun test de performance ni benchmark n'est exécuté en CI.
- **Preuve** : Revue des workflows GitHub Actions.
- **Recommandation** : Ajouter des benchmarks pytest sur les chemins critiques (screener, selector, backtesting).
