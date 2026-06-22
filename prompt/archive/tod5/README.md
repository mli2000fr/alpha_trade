# Audit Alpha Trade — Livrables TOD5

> **Date** : 2026-06-19 — **Mis à jour le 2026-06-20** (changement réglementaire FINRA)  
> **Auditeur** : GitHub Copilot (DeepSeek V4 Pro)  
> **Périmètre** : Audit exhaustif selon `prompt/demande_audit.md`  
> **Méthode** : Analyse doc → cartographie modules → flux de données → conventions critiques → paramétrages → cohérence IHM/backend/modules → contradictions → notation → plan de sprints

---

## 🔴 Mise à jour majeure — 2026-06-20 (Post-PDT FINRA + Sprints S8-S14 réalisés)

**La règle PDT (Pattern Day Trader) a été supprimée par la FINRA le 4 juin 2026.** Alpaca a mis à jour sa plateforme.

### Sprints réalisés (2026-06-20) :
- ✅ **S8** — Corrections critiques presets (drawdown breaker, min_notional, USD)
- ✅ **S8-bis** — Mise à jour IHM post-PDT (swing_only=False, step 1 dynamique)
- ✅ **S9** — Bandes avertissement IHM, infobulles FINRA
- ✅ **S10** — Remise à niveau documentaire (DOC_FONCTIONNELLE, DOC_TECHNIQUE)
- ✅ **S11** — Robustesse backtesting (cache Parquet, microstructure sqrt, commissions tiered, bootstrap 500)
- ✅ **S12** — Gouvernance ML (pipeline_ml_defaults.py, rollback doc, CatBoost check)
- ✅ **S13** — Cross-check Yahoo activé par défaut sur corporate actions
- ✅ **S14** — JSON logging, mutation CI, benchmarks pytest

Tous les documents de synthèse ont été mis à jour.

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
| **Note globale** | 7.8/10 (révisée post-sprints S8-S14) |
| **Verdict** | **Quasi-pro** — nettement au-dessus d'un projet indépendant, proche du niveau professionnel |
| **Anomalies P0** | 0 (toutes résolues : A-CAP-001 FINRA, A-CAP-002, A-CAP-003) |
| **Anomalies P1** | 7 (5 résolues : A-IHM-001, A-DOC-001, A-BACK-001, A-CA-001, A-RISK-001) |
| **Anomalies P2** | 16 (2 résolues : A-CODE, A-OBS via S14) |
| **Anomalies P3** | 14 |
| **Sprints réalisés** | 8 sprints (S8→S14 + S8-bis) sur les 11 planifiés |
| **Niveau actuel** | 7.8/10 (quasi-pro) |
