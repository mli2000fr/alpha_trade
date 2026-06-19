# Audit Alpha Trade — Livrables TOD5

> **Date** : 2026-06-19 — **Mis à jour le 2026-06-20** (changement réglementaire FINRA)  
> **Auditeur** : GitHub Copilot (DeepSeek V4 Pro)  
> **Périmètre** : Audit exhaustif selon `prompt/demande_audit.md`  
> **Méthode** : Analyse doc → cartographie modules → flux de données → conventions critiques → paramétrages → cohérence IHM/backend/modules → contradictions → notation → plan de sprints

---

## 🔴 Mise à jour majeure — 2026-06-20

**La règle PDT (Pattern Day Trader) a été supprimée par la FINRA le 4 juin 2026.** Alpaca a mis à jour sa plateforme. Conséquences :
- ✅ Plus de limite de 3 day trades par période de 5 jours
- ✅ Plus d'exigence de capital minimum de 25 000 $
- ✅ Achat/vente intraday autorisé sans restriction pour tous les comptes
- ✅ `execution_swing_only=false` sur tous les presets est désormais **correct**
- ⚠️ L'anomalie A-CAP-001 est **résolue** (plus besoin d'activer swing_only)
- ⚠️ L'IHM doit être mise à jour (son défaut `swing_only=True` est obsolète)

Les documents suivants ont été mis à jour pour refléter ce changement : `00`, `02`, `03`, `04`, `05`, `07`, `08`, `09`, `10`.

---

## Ordre de lecture recommandé

1. **`00_audit_executive_summary.md`** — Synthèse dirigeant, vue d'ensemble
2. **`01_global_scorecard.md`** — Tableau global des notes par module
3. **`02_module_scorecards.md`** — Détail module par module avec justifications
4. **`03_anomalies_register.md`** — Registre exhaustif des anomalies classées P0→P3
5. **`04_parametrage_review.md`** — Revue détaillée des configs et presets de capital
6. **`05_doc_code_gap_matrix.md`** — Écarts doc ↔ code ↔ config
7. **`06_ohlcv_data_conventions_audit.md`** — Audit spécifique OHLCV / provider / data_adjustment / corporate actions / lineage
8. **`07_swing_trade_fitness_assessment.md`** — Adéquation métier pure swing trade
9. **`08_sprint_plan.md`** — Plan d'exécution détaillé par sprint
10. **`09_final_verdict.md`** — Conclusion ferme, note globale, niveau pro estimé
11. **`10_anomaly_test_matrix.md`** — Matrice traçable anomalie → correctif → test(s) → sprint

---

## Synthèse rapide

| Indicateur | Valeur |
|---|---|
| **Note globale** | 6.4/10 (révisée post-PDT) |
| **Verdict** | **Solide** — avancé pour un projet indépendant, perfectible pour du pro-grade |
| **Anomalies P0** | 2 (A-CAP-001 résolue par FINRA 2026-06-04) |
| **Anomalies P1** | 12 |
| **Anomalies P2** | 18 |
| **Anomalies P3** | 14 |
| **Sprints recommandés** | 10 sprints sur ~6 mois (incluant S8-bis IHM post-PDT) |
| **Niveau cible après plan** | 8.5/10 (quasi-pro) |
