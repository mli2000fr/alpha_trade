# 00 — Audit Executive Summary — Alpha Trade

> **Date** : mai 2026 | **Version** : 0.3.0 | **Auditeur** : GitHub Copilot

---

## Synthèse dirigeant

**Alpha Trade** est une plateforme Python de swing trading US de bout en bout. Elle couvre l'ingestion OHLCV, le screening quantitatif, l'analyse de sentiment NLP (FinBERT), la gouvernance ML multi-modèles, la gestion du risque (sizing ATR/Kelly, circuit breaker), l'exécution automatisée Alpaca, les corporate actions (dividendes/splits), le backtesting, et une IHM opérateur Streamlit.

L'application est **clairement plus avancée qu'un projet hobby** : elle dispose d'une architecture modulaire cohérente, d'un audit trail DB complet, d'idempotence par SHA-256, d'une couverture de tests remarquable (250+ fichiers de tests), et d'une documentation bien maintenue. Elle présente cependant des lacunes qui la distinguent encore d'une application professionnelle buy-side.

---

## Note globale : **7,4 / 10 — Niveau "Indépendant avancé / quasi-pro"** *(révisée après vérification code)*

| Dimension | Note |
|---|---|
| Architecture générale | 8/10 |
| Intégrité des données / OHLCV | 7.5/10 |
| Screening / sélection | 7/10 |
| Sentiment / ML | 7/10 |
| Risk management | 7.5/10 |
| Exécution | 7.5/10 |
| Corporate actions | 7.5/10 |
| Backtesting | 7/10 |
| DB / lineage / auditabilité | 7.5/10 |
| IHM / supervision | 7.5/10 |
| Qualité logicielle | 8.5/10 |
| Sécurité / readiness prod | 7.5/10 |

---

## Points forts majeurs

1. **Architecture modulaire mature** : séparation des responsabilités bien respectée, interfaces Protocol (`core/interfaces.py`), injection de dépendances.
2. **Couverture de tests exceptionnelle** : 250+ fichiers de tests, couvrant unitaire, intégration, E2E IHM, parité backtest/live, IHM, contract tests. Seuil 60% configuré.
3. **Idempotence partout** : SHA-256 sur les ordres, les CA, le signal aggregator. Très solide.
4. **Provider OHLCV switch propre** : le basculement EODHD / Alpaca piloté par `config.yaml › market_data.bars_provider` est cohérent dans tout le code, la doc et les migrations.
5. **Backtesting rigoureux** : pipeline/research modes, point-in-time, contraintes PDT/cash/swing, phases de fidélité 2/3/4/5/7.
6. **Sécurité secrets** : aucune credential en dur, scan `core.secrets.scan_yaml_for_literal_secrets`, vault support.
7. **Couche Market-Aware complète** : market regime, circuit breaker sentiment, patterns calendaires, trailing stop ATR.
8. **Support multi-comptes** Alpaca avec colonne `account_id` propagée.
9. **Documentation très complète** (bien que quelques écarts codés dans ce rapport).

---

## Vulnérabilités critiques identifiées

> ✅ = Confirmées RÉSOLUES après vérification directe du code source

1. **`capital_0_2000_eur` : `risk_max_positions: 10` incompatible** avec la description "3 lignes" et le capital de 2 000 €. **(P1 actif — A-001)**
2. ✅ ~~**`data_lineage_matrix.md` : provider CA ambigu**~~ — **RÉSOLU** : règle conditionnelle documentée (`EodhdCorporateActionProvider` si `bars_provider=eodhd`) dans `DOC_FONCTIONNELLE.md:246` et `data_lineage_matrix.md §7`. Factory `build_corporate_action_provider()` correctement implémentée. **(A-005 ✅)**
3. **`data_lineage_matrix.md` nomme `execution_orders`** (ancienne table) alors que le schéma réel utilise `execution_order_requests` + `execution_broker_orders` + `execution_events`. **(P1 actif — A-002)**
4. ✅ ~~**`DOC_TECHNIQUE.md §9` mentionne "vectorbt"**~~ — **RÉSOLU** : `DOC_TECHNIQUE.md:497` confirme "simulateur custom PIT — aucune dépendance vectorbt". Résidu cosmétique dans argparse (`backtesting/cli/_impl.py:67`). **(A-004 ✅)**
5. ✅ ~~**`model_predictions` ne persiste pas `selected_model`**~~ — **RÉSOLU** : colonnes `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` présentes (`database/sql/ml/model_predictions.sql:8-11`) et persistées par `modelFactory/db_registry.py`. **(A-003 ✅)**
6. **Tous les presets ≥ 25 001 $ ont `execution_pdt_rule: "off"`** sur compte `margin`. Risque de violation PDT si l'equity chute sous 25 000 $. **(P2 actif — A-006)**
7. **`market_regimes.macro_provider: eodhd`** dans config.yaml, mais `yields.enabled: false`. **(P3 — A-020)**
8. ✅ ~~**SSL MySQL absent**~~ — **RÉSOLU** : `database/connection.py:97-111` active TLS si la variable `DB_SSL_CA_PATH` est définie. **(A-012 ✅)**

---

## Recommandations prioritaires (Top 5)

1. **Corriger `capital_0_2000_eur.risk_max_positions`** à 3 et ajuster `risk_min_position_notional: 500`.
2. **Corriger `data_lineage_matrix.md §4`** : remplacer `execution_orders` → `execution_order_requests` + `execution_broker_orders`, `execution_audit_events` → `execution_events`.
3. **Passer `execution_pdt_rule: "auto"`** sur les 3 presets margin (capital_25001_50000, capital_50001_100000, capital_100001_plus).
4. **Brancher `ParquetCache`** via `--use-cache` dans la CLI backtesting et exposer les analytics (bootstrap Monte Carlo).
5. **Intégrer alerting email automatique** sur circuit_breaker + kill_switch (notifications partiellement implémentées dans `artifacts/ihm_notifications/`).

---

## Positionnement estimé

| Niveau | Atteint ? |
|---|---|
| Application amateur sérieuse | ✅ Largement dépassé |
| Indépendant avancé | ✅ Atteint |
| Quasi-pro (pre-institutional) | 🟡 Partiel — 75-80% du chemin (score 7.4, vise 8.0) |
| Professionnel buy-side / prop desk | ❌ Non — manque : alerting push, orchestrateur pipeline, monitoring live, DR formalisé |
| Institutionnel très mature | ❌ Non — nécessite containerisation, tests de charge, SLA formels |

**Verdict** : `quasi-pro en cours de finalisation` — exploitable en swing trading réel discipliné à partir de la fin du Sprint S2 avec les corrections P1 appliquées.
