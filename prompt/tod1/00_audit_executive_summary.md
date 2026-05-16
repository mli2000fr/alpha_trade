# 00 — Audit Executive Summary — Alpha Trade

> **Date** : mai 2026 | **Version** : 0.3.0 | **Auditeur** : GitHub Copilot

---

## Synthèse dirigeant

**Alpha Trade** est une plateforme Python de swing trading US de bout en bout. Elle couvre l'ingestion OHLCV, le screening quantitatif, l'analyse de sentiment NLP (FinBERT), la gouvernance ML multi-modèles, la gestion du risque (sizing ATR/Kelly, circuit breaker), l'exécution automatisée Alpaca, les corporate actions (dividendes/splits), le backtesting, et une IHM opérateur Streamlit.

L'application est **clairement plus avancée qu'un projet hobby** : elle dispose d'une architecture modulaire cohérente, d'un audit trail DB complet, d'idempotence par SHA-256, d'une couverture de tests remarquable (250+ fichiers de tests), et d'une documentation bien maintenue. Elle présente cependant des lacunes qui la distinguent encore d'une application professionnelle buy-side.

---

## Note globale : **7,5 / 10 — Niveau "Quasi-pro"** *(post Sprint S1 livré)*

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
| Configuration | 7.5/10 |
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

> ✅ = Confirmées RÉSOLUES après vérification code ou livraison Sprint S1

1. ✅ ~~**`capital_0_2000_eur` : `risk_max_positions: 10`**~~ — **RÉSOLU Sprint S1** : `risk_max_positions: 3`, `risk_min_position_notional: 500.0`, commentaires PDT cash ajoutés sur 4 presets. Tests ajoutés. **(A-001 ✅, A-016 ✅)**
2. ✅ ~~**`data_lineage_matrix.md` : provider CA ambigu**~~ — **RÉSOLU** avant Sprint S1 : règle conditionnelle documentée dans `DOC_FONCTIONNELLE.md:246` et `data_lineage_matrix.md §7`. **(A-005 ✅)**
3. ✅ ~~**`data_lineage_matrix.md` nomme `execution_orders`**~~ — **RÉSOLU Sprint S1** : LINEAGE_SPEC corrigé → `execution_order_requests` + `execution_broker_orders` + `execution_events`, MD régénéré, CI check vert. **(A-002 ✅)**
4. ✅ ~~**`DOC_TECHNIQUE.md §9` mentionne "vectorbt"**~~ — **RÉSOLU** (résidu argparse `backtesting/cli/_impl.py:67` corrigé Sprint S1). **(A-004 ✅)**
5. ✅ ~~**`model_predictions` ne persiste pas `selected_model`**~~ — **RÉSOLU** avant Sprint S1 : colonnes présentes en DB et persistées par `db_registry.py`. **(A-003 ✅)**
6. **Presets ≥ 25 001 $ ont `execution_pdt_rule: "off"` sur compte margin** — risque PDT si equity < 25 000 $. **(P2 actif — A-006 → Sprint S2)**
7. **`market_regimes.yields.enabled: false`** malgré `macro_provider: eodhd`. **(P3 — A-020)**
8. ✅ ~~**SSL MySQL absent**~~ — **RÉSOLU** avant Sprint S1 : TLS activable via `DB_SSL_CA_PATH`. **(A-012 ✅)**

---

## Recommandations prioritaires (Top 5)

> ~~1. Corriger `capital_0_2000_eur.risk_max_positions`~~ → **FAIT Sprint S1 ✅**  
> ~~2. Corriger `data_lineage_matrix.md §4`~~ → **FAIT Sprint S1 ✅**

1. **Passer `execution_pdt_rule: "auto"`** sur les 3 presets margin (capital_25001_50000, capital_50001_100000, capital_100001_plus). → **Sprint S2**
2. **Corriger `selector_min_close: 10.0`** sur `capital_0_5000` (actuellement 5.0). → **Sprint S2**
3. **Augmenter `fill_timeout_seconds: 180`** dans `execution_engine/config.py` (actuellement 120). → **Sprint S2**
4. **Brancher `ParquetCache`** via `--use-cache` dans la CLI backtesting. → **Sprint S3**
5. **Intégrer alerting email automatique** sur circuit_breaker + kill_switch. → **Sprint S3**

---

## Positionnement estimé

| Niveau | Atteint ? |
|---|---|
| Application amateur sérieuse | ✅ Largement dépassé |
| Indépendant avancé | ✅ Atteint |
| Quasi-pro (pre-institutional) | 🟡 En cours — 80% du chemin (score 7.5 post-S1, vise 8.0 post-S2) |
| Professionnel buy-side / prop desk | ❌ Non — manque : alerting push, orchestrateur pipeline, monitoring live, DR formalisé |
| Institutionnel très mature | ❌ Non — nécessite containerisation, tests de charge, SLA formels |

**Verdict** : `quasi-pro en cours de finalisation` — exploitable en swing trading réel discipliné à partir de la fin du Sprint S2 avec les corrections P1 appliquées.
