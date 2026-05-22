# Audit Alpha Trade — Livrables tod3 (2026-05-22)

> Audit complet conforme au prompt `prompt/demande_audit.md`. Auditeur :
> Copilot agent (lecture code + doc + config + tests). Périmètre : tout le
> dépôt (`backtesting/`, `common/`, `core/`, `corporate_actions/`,
> `database/`, `dataIntegrityEngine/`, `event_sentiment/`,
> `execution_engine/`, `ihm/`, `modelFactory/`, `risk_management/`,
> `screener/`, `selector/`, `service/`, `tax/`, `tests/`,
> `run*.py`, `config*.yaml`, `doc/`).

## Ordre de lecture recommandé

| # | Fichier | Pour qui ? |
|---|---|---|
| 1 | [`00_audit_executive_summary.md`](00_audit_executive_summary.md) | Direction / décideur |
| 2 | [`09_final_verdict.md`](09_final_verdict.md) | Direction / décideur |
| 3 | [`01_global_scorecard.md`](01_global_scorecard.md) | Tech lead |
| 4 | [`02_module_scorecards.md`](02_module_scorecards.md) | Tech lead / responsables modules |
| 5 | [`07_swing_trade_fitness_assessment.md`](07_swing_trade_fitness_assessment.md) | Quant / trader |
| 6 | [`04_parametrage_review.md`](04_parametrage_review.md) | Quant / risk officer |
| 7 | [`06_ohlcv_data_conventions_audit.md`](06_ohlcv_data_conventions_audit.md) | Data engineer |
| 8 | [`05_doc_code_gap_matrix.md`](05_doc_code_gap_matrix.md) | Tech writer / mainteneur |
| 9 | [`03_anomalies_register.md`](03_anomalies_register.md) | Toute l'équipe (backlog) |
| 10 | [`10_anomaly_test_matrix.md`](10_anomaly_test_matrix.md) | QA / dev |
| 11 | [`08_sprint_plan.md`](08_sprint_plan.md) | PO / tech lead |

## Méthodologie

- Lecture de `README.md` (645 l.), `config.yaml` (229 l.),
  `config/capital_presets.yaml` (360 l., 7 tranches),
  `doc/data_lineage_matrix.md`, `doc/dataIntegrityEngine.md`,
  `dataIntegrityEngine/import_alpaca_bar.py`,
  `dataIntegrityEngine/import_eodhd_bar.py`, `corporate_actions/engine.py`,
  `core/conviction.py`, `run_execution.py`.
- Cartographie complète des packages racines (`backtesting/`, `common/`,
  `core/`, `corporate_actions/`, `database/`, `dataIntegrityEngine/`,
  `event_sentiment/`, `execution_engine/`, `ihm/`, `modelFactory/`,
  `risk_management/`, `screener/`, `selector/`, `service/`) et de
  `tests/` (~280 fichiers).
- Pour les modules non lus ligne par ligne (volume), constats étayés par
  les README/docs internes et les noms de fichiers/tests, et marqués
  explicitement « *à confirmer en lecture approfondie ciblée* » dans le
  registre d'anomalies.

## Convention de notation

`/10` ; verdict global comparé à : amateur sérieux / indé avancé / buy-side
professionnel / institutionnel mature.

## Mise à jour documentaire

Voir [`../../doc/AUDIT_2026_05_22_doc_updates.md`](../../doc/AUDIT_2026_05_22_doc_updates.md)
pour la note de réalignement `doc/` ↔ code consolidée.

