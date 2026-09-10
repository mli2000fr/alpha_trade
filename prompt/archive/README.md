# Alpha Trade — Audit Complet (TOD4)

Livrables de l'audit exhaustif réalisé le 2026-05-23, conformément au prompt
`prompt/demande_audit.md`.

## Ordre de lecture recommandé

| Ordre | Fichier | Contenu |
|---|---|---|
| 1 | `00_audit_executive_summary.md` | Synthèse dirigeant, conclusions clés |
| 2 | `01_global_scorecard.md` | Tableau global des notes /10 |
| 3 | `02_module_scorecards.md` | Détail module par module |
| 4 | `03_anomalies_register.md` | Registre exhaustif des anomalies (P0 → P3) |
| 5 | `04_parametrage_review.md` | Revue des configs et presets de capital |
| 6 | `05_doc_code_gap_matrix.md` | Écarts doc ↔ code ↔ config |
| 7 | `06_ohlcv_data_conventions_audit.md` | Audit OHLCV / provider / data_adjustment |
| 8 | `07_swing_trade_fitness_assessment.md` | Adéquation métier pure swing trade |
| 9 | `08_sprint_plan.md` | Plan d'exécution par sprints |
| 10 | `09_final_verdict.md` | Note globale, verdict, niveau pro estimé |
| 11 | `10_anomaly_test_matrix.md` | Matrice anomalie → correctif → test(s) → sprint |

## Production

- Date : 2026-05-23
- Périmètre audité : ensemble du dépôt Alpha Trade
- Méthode : lecture exhaustive de `doc/`, `config/`, `core/`, `service/`, `dataIntegrityEngine/`, `screener/`, `selector/`, `event_sentiment/`, `modelFactory/`, `risk_management/`, `execution_engine/`, `corporate_actions/`, `backtesting/`, `ihm/`, `tests/`
- Référence : `prompt/demande_audit.md`