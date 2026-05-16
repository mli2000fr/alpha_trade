# 00 — Audit Executive Summary — Alpha Trade

> **Date** : mai 2026 | **Version** : 0.3.0 | **Auditeur** : GitHub Copilot

---

## Synthèse dirigeant

**Alpha Trade** est une plateforme Python de swing trading US de bout en bout. Elle couvre l'ingestion OHLCV, le screening quantitatif, l'analyse de sentiment NLP (FinBERT), la gouvernance ML multi-modèles, la gestion du risque (sizing ATR/Kelly, circuit breaker), l'exécution automatisée Alpaca, les corporate actions (dividendes/splits), le backtesting, et une IHM opérateur Streamlit.

L'application est **clairement plus avancée qu'un projet hobby** : elle dispose d'une architecture modulaire cohérente, d'un audit trail DB complet, d'idempotence par SHA-256, d'une couverture de tests remarquable (250+ fichiers de tests), et d'une documentation bien maintenue. Elle présente cependant des lacunes qui la distinguent encore d'une application professionnelle buy-side.

---

## Note globale : **7,2 / 10 — Niveau "Indépendant avancé / quasi-pro"**

| Dimension | Note |
|---|---|
| Architecture générale | 8/10 |
| Intégrité des données / OHLCV | 7.5/10 |
| Screening / sélection | 7/10 |
| Sentiment / ML | 6.5/10 |
| Risk management | 7.5/10 |
| Exécution | 7.5/10 |
| Corporate actions | 7/10 |
| Backtesting | 7/10 |
| DB / lineage / auditabilité | 7/10 |
| IHM / supervision | 7.5/10 |
| Qualité logicielle | 8/10 |
| Sécurité / readiness prod | 7/10 |

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

1. **`capital_0_2000_eur` : `risk_max_positions: 10` incompatible avec la description "3 lignes"** et le capital de 2 000 €. Avec 10 positions à 150 $ minimum = 1 500 $, le budget est mathématiquement tenu mais chaque position est de 150 $ — non viable en pratique. **(P1)**
2. **`data_lineage_matrix.md` ligne CA : mentionne EODHD comme provider primaire des CA**, mais `CorporateActionEngine` a pour provider par défaut `AlpacaCorporateActionProvider`. La factory `build_corporate_action_provider` est absente du code visible — cohérence à confirmer. **(P1)**
3. **`data_lineage_matrix.md` nomme `execution_orders`** (ancienne table) alors que le schéma réel utilise `execution_order_requests` + `execution_broker_orders`. Écart doc ↔ code P1 sur un fichier généré.
4. **`DOC_TECHNIQUE.md` §9 mentionne "vectorbt"** comme framework backtest alors que le module est 100% custom (aucun import vectorbt). **(P2 doc)**
5. **`model_predictions` ne persiste pas `selected_model` / `decision_threshold`** : la gouvernance ML en DB est incomplète. Le champion servi n'est pas traçable en SQL, seulement dans les artefacts disque. **(P1)**
6. **Tous les presets ≥ 25 001 $ ont `execution_pdt_rule: "off"`** alors qu'ils passent à `margin`. Un compte margin < 25 000 $ avec PDT off peut subir des conséquences réglementaires (trade restriction). Incohérence potentielle si l'equity fluctue. **(P2)**
7. **`market_regimes.macro_provider: eodhd`** dans config.yaml, mais `yields.enabled: false` — la logique yield est donc toujours désactivée malgré une configuration potentiellement coûteuse en quota. **(P3)**
8. **`config.yaml` mentionne un compte `test1` et `test2`** en paper mais sans doc sur leur cycle de vie et sans tests dédiés au comportement avec 3 comptes actifs simultanément. **(P3)**

---

## Recommandations prioritaires (Top 5)

1. **Corriger `capital_0_2000_eur.risk_max_positions`** à 3 et ajuster les seuils en conséquence.
2. **Enrichir `model_predictions` DB** avec `selected_model`, `decision_threshold`, `calibration_method`.
3. **Corriger `data_lineage_matrix.md`** : noms de tables, provider CA (Alpaca vs EODHD), régénération canonique.
4. **Supprimer la mention "vectorbt"** dans `DOC_TECHNIQUE.md §9`.
5. **Documenter et tester le comportement du switch PDT** quand equity passe autour de 25 000 $ avec `pdt_rule: "off"` sur un compte margin.

---

## Positionnement estimé

| Niveau | Atteint ? |
|---|---|
| Application amateur sérieuse | ✅ Largement dépassé |
| Indépendant avancé | ✅ Atteint |
| Quasi-pro (pre-institutional) | 🟡 Partiel — 70-75% du chemin |
| Professionnel buy-side / prop desk | ❌ Non — manque : ordre par ordre audit trail complet, gouvernance ML en DB, notifications externes, orchestrateur pipeline, DR formalisé |
| Institutionnel très mature | ❌ Non — nécessite containerisation, monitoring live, tests de charge, SLA formels |

**Verdict** : `quasi-pro en cours de finalisation` — exploitable en production swing discipliné avec les corrections P0/P1 appliquées.

