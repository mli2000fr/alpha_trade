# 00 — Audit Executive Summary — Alpha Trade

> **Date** : mai 2026 | **Version** : 0.3.0 | **Auditeur** : GitHub Copilot

---

## Synthèse dirigeant

**Alpha Trade** est une plateforme Python de swing trading US de bout en bout. Elle couvre l'ingestion OHLCV, le screening quantitatif, l'analyse de sentiment NLP (FinBERT), la gouvernance ML multi-modèles, la gestion du risque (sizing ATR/Kelly, circuit breaker), l'exécution automatisée Alpaca, les corporate actions (dividendes/splits), le backtesting, et une IHM opérateur Streamlit.

L'application est **clairement plus avancée qu'un projet hobby** : elle dispose d'une architecture modulaire cohérente, d'un audit trail DB complet, d'idempotence par SHA-256, d'une couverture de tests remarquable (2316 tests verts), et d'une documentation bien maintenue. Elle présente cependant des lacunes qui la distinguent encore d'une application professionnelle buy-side.

---

## Note globale : **8,2 / 10 — Niveau "Quasi-pro+"** *(post Sprint S3 livré — 20 anomalies résolues au total)*

| Dimension | Note |
|---|---|
| Architecture générale | 8/10 |
| Intégrité des données / OHLCV | 7.5/10 |
| Screening / sélection | 7/10 |
| Sentiment / ML | 7/10 |
| Risk management | 7.5/10 |
| Exécution | 8.0/10 |
| Corporate actions | 7.5/10 |
| Backtesting | 7.5/10 *(+0.5 post-S3 : --use-cache, --bootstrap-samples)* |
| DB / lineage / auditabilité | 7.5/10 |
| IHM / supervision | 8.0/10 *(+0.5 post-S3 : alertes réconciliation + market_cap TTL)* |
| Qualité logicielle | 8.5/10 |
| Configuration | 8.0/10 |
| Sécurité / readiness prod | 7.5/10 |
| Observabilité / logs | 7.5/10 *(+0.5 post-S3 : TimedRotatingFileHandler + gzip, alerting email CB)* |

---

## Points forts majeurs

1. **Architecture modulaire mature** : séparation des responsabilités bien respectée, interfaces Protocol (`core/interfaces.py`), injection de dépendances.
2. **Couverture de tests exceptionnelle** : 2316 tests verts (260+ fichiers), couvrant unitaire, intégration, E2E IHM, parité backtest/live, contract tests.
3. **Idempotence partout** : SHA-256 sur les ordres, les CA, le signal aggregator. Très solide.
4. **Provider OHLCV switch propre** : le basculement EODHD / Alpaca piloté par `config.yaml › market_data.bars_provider` est cohérent dans tout le code, la doc et les migrations.
5. **Backtesting rigoureux** : pipeline/research modes, point-in-time, contraintes PDT/cash/swing, phases de fidélité 2/3/4/5/7, `--use-cache` ParquetCache, `--bootstrap-samples` Bootstrap Monte Carlo.
6. **Sécurité secrets** : aucune credential en dur, scan `core.secrets.scan_yaml_for_literal_secrets`, vault support.
7. **Couche Market-Aware complète** : market regime, circuit breaker sentiment, patterns calendaires, trailing stop ATR.
8. **Alerting automatique opérationnel** : email sur circuit_breaker, avertissements IHM sur réconciliation > 24h et market_cap TTL expiré (A-013 ✅, A-014 ✅, A-015 ✅ Sprint S3).
9. **Support multi-comptes** Alpaca avec colonne `account_id` propagée.

---

## Vulnérabilités critiques identifiées

> ✅ = Confirmées RÉSOLUES après vérification code ou livraison Sprint S1/S2/S3

1. ✅ ~~**`capital_0_2000_eur` : `risk_max_positions: 10`**~~ — **RÉSOLU Sprint S1** : `risk_max_positions: 3`, `risk_min_position_notional: 500.0`, commentaires PDT cash ajoutés sur 4 presets. Tests ajoutés. **(A-001 ✅, A-016 ✅)**
2. ✅ ~~**`data_lineage_matrix.md` : provider CA ambigu**~~ — **RÉSOLU** avant Sprint S1 : règle conditionnelle documentée dans `DOC_FONCTIONNELLE.md:246` et `data_lineage_matrix.md §7`. **(A-005 ✅)**
3. ✅ ~~**`data_lineage_matrix.md` nomme `execution_orders`**~~ — **RÉSOLU Sprint S1** : LINEAGE_SPEC corrigé → `execution_order_requests` + `execution_broker_orders` + `execution_events`, MD régénéré, CI check vert. **(A-002 ✅)**
4. ✅ ~~**`DOC_TECHNIQUE.md §9` mentionne "vectorbt"**~~ — **RÉSOLU** (résidu argparse `backtesting/cli/_impl.py:67` corrigé Sprint S1). **(A-004 ✅)**
5. ✅ ~~**`model_predictions` ne persiste pas `selected_model`**~~ — **RÉSOLU** avant Sprint S1 : colonnes présentes en DB et persistées par `db_registry.py`. **(A-003 ✅)**
6. ✅ ~~**Presets ≥ 25 001 $ ont `execution_pdt_rule: "off"` sur compte margin**~~ — **RÉSOLU Sprint S2** : `pdt_rule: "auto"` sur 3 presets margin. **(A-006 ✅)**
7. ✅ ~~**`ParquetCache` non branché, analytics CLI absents**~~ — **RÉSOLU Sprint S3** : `--use-cache`, `--bootstrap-samples`, `--sensitivity-analysis` implémentés. **(A-010 ✅, A-011 ✅)**
8. ✅ ~~**Pas d'alerting externe automatique**~~ — **RÉSOLU Sprint S3** : email sur circuit_breaker + kill_switch. **(A-013 ✅)**
9. **`market_regimes.yields.enabled: false`** malgré `macro_provider: eodhd`. **(P3 — A-020)**
10. ✅ ~~**SSL MySQL absent**~~ — **RÉSOLU** avant Sprint S1 : TLS activable via `DB_SSL_CA_PATH`. **(A-012 ✅)**

---

## Recommandations prioritaires (Top 5)

> ~~1–7. Sprints S1, S2, S3 appliqués~~ → **FAITS ✅**

1. **Widget PnL quotidien** dans la page Overview (MTM positions + cash ledger). → **Sprint S4** (A-021)
2. **Walk-forward paramètres risque** (ATR period, Kelly, correlation threshold) en plus des poids sentiment. → **Sprint S4** (A-022)
3. **Documenter biais IEX spread_bps** et utiliser `max_spread_bps_iex` comme mitigation documentée. → **Sprint S4** (A-008)
4. **Orchestrateur pipeline** : scheduler léger ou Prefect pour automatisation sans surveillance. → **Sprint S5**
5. **Monitoring live** : Prometheus/Grafana ou équivalent pour métriques pipeline. → **Sprint S5**

---

## Positionnement estimé

| Niveau | Atteint ? |
|---|---|
| Application amateur sérieuse | ✅ Largement dépassé |
| Indépendant avancé | ✅ Atteint |
| Quasi-pro (pre-institutional) | 🟢 **Ici (8.2 post-S3) — alerting opérationnel, cache backtesting, 2316 tests verts** |
| Professionnel buy-side / prop desk | ❌ Non — manque : orchestrateur pipeline, monitoring live Prometheus, DR formalisé |
| Institutionnel très mature | ❌ Non — nécessite containerisation, tests de charge, SLA formels |

**Verdict** : `quasi-pro opérationnel` — exploitable en swing trading réel discipliné. Alerting automatique email activé depuis Sprint S3.
