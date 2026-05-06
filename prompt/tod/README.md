# Audit Alpha Trade — Livrables (`prompt/tod/`)

> Audit réalisé le **2026-05-06**, pivot du dépôt (`HEAD` au moment de l'audit).
> Source de vérité : **code courant**. Toute contradiction entre `doc/` et code
> est tranchée en faveur du code, et signalée explicitement.

## Ordre de lecture recommandé

1. **`00_audit_executive_summary.md`** — Synthèse dirigeant (10 minutes).
2. **`01_global_scorecard.md`** — Tableau global des notes /10 par module et
   note globale.
3. **`09_final_verdict.md`** — Verdict, niveau pro estimé, conditions de
   passage en swing trading réel.
4. **`02_module_scorecards.md`** — Détail module par module (notes, points
   forts, faiblesses, gap pour 10/10).
5. **`03_anomalies_register.md`** — Registre exhaustif des anomalies
   (P0–P3) avec preuves `fichier:ligne` et tests associés.
6. **`04_parametrage_review.md`** — Revue détaillée de `config.yaml` et des
   6 tranches de `config/capital_presets.yaml`.
7. **`05_doc_code_gap_matrix.md`** — Matrice écarts doc ↔ code ↔ config et
   doc à mettre à jour.
8. **`06_ohlcv_data_conventions_audit.md`** — Audit ciblé OHLCV / provider
   primaire / `data_adjustment` / corporate actions / lineage.
9. **`07_swing_trade_fitness_assessment.md`** — Adéquation métier swing
   trade, par tranche de capital et par axe.
10. **`08_sprint_plan.md`** — Plan d'exécution priorisé par sprints, avec
    volet tests obligatoire pour chaque sprint.
11. **`10_anomaly_test_matrix.md`** — Matrice traçable anomalie → correctif
    → test(s) → sprint.

## Mises à jour documentaires (`doc/`)

L'audit identifie plusieurs documents dans `doc/` désalignés avec le code
réel (notamment autour du provider OHLCV primaire et de la convention
`data_adjustment`). La liste exhaustive et les patches recommandés sont
listés dans `05_doc_code_gap_matrix.md` § « Doc à mettre à jour ».

Conformément à la consigne, ces mises à jour doivent être appliquées **sans
modification du code applicatif** ; seules les docstrings obsolètes
(notamment `corporate_actions/engine.py` ligne 36) sont identifiées comme
candidates à un correctif documentaire ultérieur via le sprint dédié.

## Verdict express

- **Note globale : 6.4 / 10** — _solide / quasi-pro partiel_
- **Prêt swing trading réel discipliné** : pas avant la fin du **Sprint S3**
  (correctifs P0/P1 + alignement provider/CA + cohérence IHM↔backend).
- **3 anomalies P0** détectées (voir `03_anomalies_register.md`).


