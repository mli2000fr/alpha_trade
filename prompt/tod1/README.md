# Audit Alpha Trade — Livrables `prompt/tod1/`

> **Date de l'audit** : mai 2026  
> **Auditeur** : GitHub Copilot — rôle auditeur principal software + quant trading + architecture data/ops  
> **Version auditée** : 0.3.0 (Python ≥ 3.12, MySQL 8.x)  
> **Périmètre** : application complète Alpha Trade (swing trading US, production)

---

## Ordre de lecture recommandé

| # | Fichier | Contenu |
|---|---|---|
| 1 | `00_audit_executive_summary.md` | Synthèse dirigeant — vue d'ensemble, score global, verdict |
| 2 | `01_global_scorecard.md` | Tableau de bord global toutes notes sur 10 |
| 3 | `02_module_scorecards.md` | Détail module par module (points forts, faiblesses, risques) |
| 4 | `03_anomalies_register.md` | Registre exhaustif des anomalies P0 → P3 |
| 5 | `06_ohlcv_data_conventions_audit.md` | Audit spécifique OHLCV / provider / data_adjustment / CA |
| 6 | `04_parametrage_review.md` | Revue config.yaml + capital_presets par tranche |
| 7 | `05_doc_code_gap_matrix.md` | Écarts doc ↔ code ↔ config |
| 8 | `07_swing_trade_fitness_assessment.md` | Adéquation métier swing trade réel |
| 9 | `10_anomaly_test_matrix.md` | Matrice anomalie → correctif → test(s) → sprint |
| 10 | `08_sprint_plan.md` | Plan d'action par sprints (priorisé, détaillé) |
| 11 | `09_final_verdict.md` | Conclusion ferme, note globale, niveau professionnel estimé |

---

## Méthode appliquée

1. Lecture doc/ (`DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`, `data_lineage_matrix.md`, `dataIntegrityEngine.md`, toutes docs modules)
2. Cartographie du code source réel : `dataIntegrityEngine/`, `screener/`, `selector/`, `risk_management/`, `execution_engine/`, `corporate_actions/`, `backtesting/`, `ihm/`, `core/`, `service/`
3. Lecture des configurations : `config.yaml`, `config/capital_presets.yaml`, `pyproject.toml`, `mypy.ini`, `pytest.ini`
4. Lecture d'un échantillon large de `tests/` (250+ fichiers)
5. Vérification conventions critiques : OHLCV provider, `data_adjustment`, CA, lineage
6. Contrôle cohérence IHM ↔ backend ↔ paramètres
7. Détection contradictions doc ↔ code ↔ config
8. Notation et plan d'action

---

## Avertissement

Le **code courant est la source de vérité prioritaire**. Toute divergence documentée dans ces livrables a été tranchée en faveur du code, sauf preuve contraire explicite. Les livrables dans `doc/` ont été mis à jour en conséquence.

