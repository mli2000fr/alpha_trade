# 23 — Plan d'exécution Phase A (Sprints S10 + S11)

> Document de travail dérivé de `prompt/tod/22_plan_10_10.md` §2 (Phase A).
> Objectif : feuille de route stricte pour passer 7.8 → 8.5.

---

## 0. Vue d'ensemble

| ID | Tâche | Sprint | Complexité | Dépend de |
|----|---|---|---|---|
| S10.1 | Encodage YAML `config/capital_presets.yaml` | S10 | **S** | — |
| S10.2 | Bug `progress_callback` `event_sentiment/pipeline.py` | S10 | **S** | — |
| S10.3 | `tests/test_import_linter_contracts.py` | S10 | **S** | — |
| S10.4 | `tests/test_model_factory_global_model.py` engine mock | S10 | **S** | — |
| S10.5 | `tests/test_pages_pipeline.py` | S10 | **S** | S10.1 |
| S10.6 | Éclatement `ihm/pages/_execution_center.py` (2866 → < 200) | S10 | **L** | — |
| S10.7 | Découpage `execution_engine/executor.py` (977 → < 600) | S10 | **M** | — |
| S11.1 | `scripts/run_quarterly_weights_calibration.py` | S11 | **M** | — |
| S11.2 | CI nightly parité (workflow GH) | S11 | **S** | — |
| S11.3 | Auto-rollback champion ML 3 j consécutifs | S11 | **L** | (table `champion_history`) |
| S11.4 | Brancher `run_preflight` dans `run_execution.py --mode live` | S11 | **S** | — |
| S11.5 | Tableau de bord parité IHM (rolling 30 j) | S11 | **M** | S11.2 |

### Ordre d'exécution

1. Quick wins isolés — S10.1 → S10.2 → S10.4 → S10.5.
2. Hygiène CI — S10.3, S11.4.
3. Refactor — S10.7 → S10.6.
4. Industrialisation — S11.1 → S11.2 → S11.5.
5. Auto-rollback ML (S11.3) en dernier.

(Plan détaillé conservé dans l'historique de génération — exécution en cours.)

