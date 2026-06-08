# Audit Alpha Trade — Livrables `prompt/tod1/`

> **Date de l'audit** : mai 2026  
> **Auditeur** : GitHub Copilot — rôle auditeur principal software + quant trading + architecture data/ops  
> **Version auditée** : 0.3.0 (Python ≥ 3.12, MySQL 8.x)  
> **Périmètre** : application complète Alpha Trade (swing trading US, production)  
> **Note globale** : **8,2 / 10** *(post Sprint S3 livré — 20 anomalies résolues, 7 actives)*

---

## Ordre de lecture recommandé

| # | Fichier | Contenu |
|---|---|---|
| 1 | `00_audit_executive_summary.md` | Synthèse dirigeant — vue d'ensemble, score global 8.2/10, verdict |
| 2 | `01_global_scorecard.md` | Tableau de bord global toutes notes sur 10 |
| 3 | `02_module_scorecards.md` | Détail module par module (points forts, faiblesses, risques) |
| 4 | `03_anomalies_register.md` | Registre exhaustif des anomalies P0 → P3 (7 actives, 20 résolues ✅) |
| 5 | `06_ohlcv_data_conventions_audit.md` | Audit spécifique OHLCV / provider / data_adjustment / CA |
| 6 | `04_parametrage_review.md` | Revue config.yaml + capital_presets par tranche |
| 7 | `05_doc_code_gap_matrix.md` | Écarts doc ↔ code ↔ config (avec statut résolution) |
| 8 | `07_swing_trade_fitness_assessment.md` | Adéquation métier swing trade réel (7.5/10) |
| 9 | `10_anomaly_test_matrix.md` | Matrice anomalie → correctif → test(s) → sprint (statut résolution) |
| 10 | `08_sprint_plan.md` | Plan d'action par sprints (S1/S2/S3 livrés ✅, S4/S5 planifiés) |
| 11 | `09_final_verdict.md` | Conclusion ferme, note globale 8.2/10, niveau professionnel estimé |

---

## Anomalies résolues ✅ (confirmées par vérification code + Sprints S1/S2/S3 livrés)

| ID | Titre | Sprint | Impact sur score |
|---|---|---|---|
| A-001 ✅ | Preset micro-compte : risk_max_positions=3, min_notional=500$ | **S1 livré** | Configuration : 7.0 → **8.0** (global) |
| A-002 ✅ | Lineage matrix : execution_order_requests, execution_broker_orders, execution_events | **S1 livré** | Documentation : 8.5 → **9.0** |
| A-004 ✅ | Description argparse vectorbt éliminée dans backtesting/cli/_impl.py | **S1 livré** | Documentation : entièrement clos |
| A-016 ✅ | Reliquat historique cash nettoyé sur 4 presets | **S1 livré** | Configuration : lisibilité opérateur |
| A-003 ✅ | Gouvernance ML en DB (selected_model, decision_threshold) | Avant S1 | modelFactory : 6.5 → 7.0 |
| A-005 ✅ | Provider CA ambigu (Alpaca vs EODHD) | Avant S1 | corporate_actions : 7.0 → 7.5 |
| A-009 ✅ | Unicité model_predictions (UNIQUE KEY) | Avant S1 | database : +0.5 |
| A-012 ✅ | SSL MySQL activable via DB_SSL_CA_PATH | Avant S1 | Sécurité : 7.0 → 7.5 |
| A-018 ✅ | DOC_FONCTIONNELLE §1.3 step 1 = EODHD | Avant S1 | Documentation (résidu mineur) |
| A-006 ✅ | Contraintes margin clarifiées sur presets ≥ 25k$ | **S2 livré** | Exécution : garde-fous documentés |
| A-007 ✅ | selector_min_close=10.0 sur tous les presets | **S2 livré** | Selector : uniforme, anti-penny stocks |
| A-017 ✅ | fill_timeout_seconds=180 (was 120) | **S2 livré** | execution_engine : 7.5 → **8.0** |
| A-010 ✅ | ParquetCache `--use-cache` branché en CLI backtesting | **S3 livré** | backtesting : 7.0 → **7.5**, 3x–10x vitesse |
| A-011 ✅ | Bootstrap MC `--bootstrap-samples` + `--sensitivity-analysis` en CLI | **S3 livré** | backtesting : robustesse statistique |
| A-013 ✅ | Alerting email automatique circuit_breaker + kill_switch | **S3 livré** | observabilité : 7.0 → **7.5** |
| A-014 ✅ | Alerte IHM réconciliation non-résolue > 24h | **S3 livré** | IHM : 7.5 → **8.0** |
| A-015 ✅ | Alerte IHM market_cap TTL expiré > 30% symboles | **S3 livré** | IHM : supervision proactive |
| A-025 ✅ | TimedRotatingFileHandler + compression gzip | **S3 livré** | observabilité : logs pérennes |
| A-027 ✅ | Bornes walk-forward [0.05, 0.40] enforced | **S3 livré** | backtesting : guard-rail réglages |

---

## Méthode appliquée

1. Lecture doc/ (`DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`, `data_lineage_matrix.md`, `dataIntegrityEngine.md`, toutes docs modules)
2. Cartographie du code source réel : `dataIntegrityEngine/`, `screener/`, `selector/`, `risk_management/`, `execution_engine/`, `corporate_actions/`, `backtesting/`, `ihm/`, `core/`, `service/`
3. Lecture des configurations : `config.yaml`, `config/capital_presets.yaml`, `pyproject.toml`, `mypy.ini`, `pytest.ini`
4. Lecture d'un échantillon large de `tests/` (260+ fichiers — 2316 tests verts)
5. Vérification conventions critiques : OHLCV provider, `data_adjustment`, CA, lineage
6. **Vérification directe du code source** pour chaque anomalie identifiée → 20 confirmées résolues
7. Contrôle cohérence IHM ↔ backend ↔ paramètres
8. Détection contradictions doc ↔ code ↔ config
9. Notation et plan d'action
10. Livraison Sprints S1, S2, S3 ✅

---

## Avertissement

Le **code courant est la source de vérité prioritaire**. Toute divergence documentée dans ces livrables a été tranchée en faveur du code, sauf preuve contraire explicite.

