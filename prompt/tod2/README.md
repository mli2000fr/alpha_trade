# Audit Alpha Trade — livrables `tod2`

Audit statique professionnel réalisé à partir des fichiers de documentation, configuration, code critique et tests disponibles dans le dépôt.

## Ordre de lecture recommandé

1. `00_audit_executive_summary.md` — synthèse dirigeant.
2. `01_global_scorecard.md` — notes globales et positionnement.
3. `02_module_scorecards.md` — notes par module.
4. `03_anomalies_register.md` — registre des anomalies avec tests associés.
5. `04_parametrage_review.md` — cohérence des presets de capital et paramètres.
6. `05_doc_code_gap_matrix.md` — écarts doc/code/config.
7. `06_ohlcv_data_conventions_audit.md` — provider OHLCV, `data_source`, `data_adjustment`, corporate actions.
8. `07_swing_trade_fitness_assessment.md` — aptitude au swing trading réel.
9. `08_sprint_plan.md` — plan d’action priorisé par sprints avec tests.
10. `10_anomaly_test_matrix.md` — matrice anomalie → correctif → test → sprint.
11. `09_final_verdict.md` — verdict final.

## Addendum documentaire créé

Un addendum de réalignement documentaire a été ajouté dans `doc/audit_alignment_tod2.md` et référencé depuis les documents principaux. Il résume les conventions canoniques constatées dans le code courant et les points à corriger dans les docs existantes.

## Limite méthodologique

L’audit est volontairement sévère. Il s’appuie sur des preuves concrètes lues dans le dépôt : `config.yaml`, `config/capital_presets.yaml`, `dataIntegrityEngine`, `corporate_actions`, `ihm/services/pipeline_runner.py`, `execution_engine`, `risk_management`, schémas SQL et échantillon de tests. Les tests complets n’ont pas été relancés intégralement car le dépôt contient des tests DB/réseau lourds ; le statut de couverture `coverage.json` présent est considéré non probant car issu d’un run partiel récent.

