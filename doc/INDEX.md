# Index de la documentation Alpha Trade

> Généré automatiquement par `scripts/generate_doc_index.py` le 2026-10-10.
> 685 documents indexés.

## Sommaire

* [Architecture](#architecture) (4)
* [Archives et expériences historiques](#archives-et-expériences-historiques) (158)
* [Backtests et validation](#backtests-et-validation) (6)
* [Bases et migrations](#bases-et-migrations) (4)
* [Conformité & Audit](#conformité--audit) (3)
* [Divers](#divers) (8)
* [Documentation centrale actuelle](#documentation-centrale-actuelle) (24)
* [Données et ingestion](#données-et-ingestion) (6)
* [Exploitation et batchs](#exploitation-et-batchs) (20)
* [Exécution et protections](#exécution-et-protections) (5)
* [Guide utilisateur IHM](#guide-utilisateur-ihm) (21)
* [ML — contrats et recherche US](#ml--contrats-et-recherche-us) (192)
* [Marché chinois — CN](#marché-chinois--cn) (82)
* [Marché français — FR](#marché-français--fr) (101)
* [Recherche transverse](#recherche-transverse) (6)
* [Registre documentaire et audit](#registre-documentaire-et-audit) (1)
* [Risque et portefeuille](#risque-et-portefeuille) (6)
* [Références du code et configuration](#références-du-code-et-configuration) (32)
* [Signaux et sentiment](#signaux-et-sentiment) (5)
* [Tests & Vérification](#tests--vérification) (1)

## Architecture

| Document | Titre | Description |
|---|---|---|
| [`architecture/adr_0001_market_context.md`](architecture/adr_0001_market_context.md) | ADR-0001 — `MarketContext` explicite | Le runtime actuel suppose principalement NYSE, USD, SPY et `America/New_York`. Ces hypothèses sont présentes dans le calendrier, les cutoffs |
| [`architecture/adr_0002_instrument_identity.md`](architecture/adr_0002_instrument_identity.md) | ADR-0002 — Identité canonique des instruments | Dans la base US auditée, 58 tables contiennent `symbol` et 39 l’utilisent dans une clé primaire ou unique sans `market_code` ni `instrument_ |
| [`architecture/adr_0003_market_data_partitioning.md`](architecture/adr_0003_market_data_partitioning.md) | ADR-0003 — Isolation physique des données US et Chine | Utiliser deux bases physiques avec un contrat logique commun : |
| [`architecture/adr_0004_cn_execution_rules.md`](architecture/adr_0004_cn_execution_rules.md) | ADR-0004 — Règles d’exécution chinoises versionnées | Les règles CN varient selon la place, le board, le statut du titre et la date. Un backtest réutilisant implicitement les règles US produirai |

## Archives et expériences historiques

| Document | Titre | Description |
|---|---|---|
| [`experiences/README.md`](experiences/README.md) | Synthèses des expériences historiques | Archives intégrales : campagnes Global Ranking et archives ML complémentaires. |
| [`experiences/archives_ml/README.md`](experiences/archives_ml/README.md) | Archives ML complémentaires | Analyses OOS, backlog et synthèses datées retirés de `doc/ml`. Ils sont non normatifs. Les verdicts durables sont condensés dans le dossier |
| [`experiences/archives_ml/ml_todo.md`](experiences/archives_ml/ml_todo.md) | Global Ranking — Synthèse des tests A/B (2026-08-02) | Tous les tests utilisent la config P1 (target sector/factor-neutral, smoothing, 8 splits, 756j). |
| [`experiences/archives_ml/synthese_long_short.md`](experiences/archives_ml/synthese_long_short.md) | Comprendre le trading Long/Short ML-first de bout en bout | Guide fonctionnel et opérationnel du pipeline PIT, du ML ternaire, du risque, de l'exécution et du backtest. Révision du 2026-07-11. |
| [`experiences/archives_ml/synthese_per_symbol_v2_2026-08-19.md`](experiences/archives_ml/synthese_per_symbol_v2_2026-08-19.md) | Campagne Per-Symbol Directional v2 — F0/F1/F2/F3a/F3b : VERDICT NO-GO (2026-08-19) | La campagne **Per-Symbol Directional v2** (features directionnelles per-symbol dédiées au swing, opposées au ranking global B25) a été condu |
| [`experiences/archives_ml/synthese_s7_feature_whitelist_2026-08-18.md`](experiences/archives_ml/synthese_s7_feature_whitelist_2026-08-18.md) | S7 — Feature whitelist per-symbol : mécanisme implémenté, expérience NO-GO | Permettre, dans le pipeline d'entraînement **per-symbol** de modelFactory, un mécanisme de |
| [`experiences/archives_ml/synthese_tp_risk_execution_2026-08-18.md`](experiences/archives_ml/synthese_tp_risk_execution_2026-08-18.md) | Synthèse — Balayage TP / risque-exécution (Point 8) — verdict NO-GO (2026-08-18) | Branche d'investigation fermée : améliorer le moteur risk/exécution **sans toucher B25**. |
| [`experiences/archives_recherche/README.md`](experiences/archives_recherche/README.md) | Archives de recherche complémentaires | Ces fichiers sont des audits de runs, protocoles, verdicts et dossiers de décision datés. Ils sont conservés pour la reproductibilité et pou |
| [`experiences/archives_recherche/Tiebreaker.md`](experiences/archives_recherche/Tiebreaker.md) | Tiebreaker dip_quality — Document de synthèse | Le modèle **`dip_quality_score`** estime la qualité d'un candidat DIP (probabilité que le DIP soit « bon », c.-à-d. `future_return_H20 > 0`) |
| [`experiences/archives_recherche/b4_force_close_side_attribution.md`](experiences/archives_recherche/b4_force_close_side_attribution.md) | E44 — Test catastrophe B4 : KEEP vs CLOSE_ALL vs CLOSE_LONGS | **Méthode** : le hook `--research-force-close-at-dd-pct 0.08 --research-force-close-side {all\|longs}` liquide UNE fois par épisode de drawdo |
| [`experiences/archives_recherche/backtest_audit.md`](experiences/archives_recherche/backtest_audit.md) | Audit du backtest `20260817_165433_2785da86` (+63.9% sur 1 an 5 mois) | **Date de l'audit** : 2026-08-17 |
| [`experiences/archives_recherche/c2_b4_breaker_go_paper_2026-08-21.md`](experiences/archives_recherche/c2_b4_breaker_go_paper_2026-08-21.md) | 🟢 C2+B4 — Contrôleur de drawdown robuste : GO LIVE PROD (2026-08-21) | Le breaker historique PROD (`b0` : recovery 92% + cap 25%) est jugé trop lent à réarmer en conditions de marché normales, mais les variantes |
| [`experiences/archives_recherche/calibration_oracle_exterme.md`](experiences/archives_recherche/calibration_oracle_exterme.md) | Calibration Oracle Extreme — `proba_extreme` | Statut : implémenté en option (`oracle.calibration` + `--oracle-calibration`). |
| [`experiences/archives_recherche/check_performance_model_global ask.md`](experiences/archives_recherche/check_performance_model_global%20ask.md) | check_performance_model_global ask | — |
| [`experiences/archives_recherche/check_performance_model_global.md`](experiences/archives_recherche/check_performance_model_global.md) | Check Performance — Modèle Global (LONG Alpha Attribution) | **GO FAIBLE** |
| [`experiences/archives_recherche/directional_data_research.md`](experiences/archives_recherche/directional_data_research.md) | DirectionalDataResearch — Recherche de données directionnelles | Suite à la clôture de `GlobalDirection` (**NO-GO** : direction non observable avec |
| [`experiences/archives_recherche/e17_synthese_gpt.md`](experiences/archives_recherche/e17_synthese_gpt.md) | Synthèse des tests — Gate Extreme vs B25 & ablation du rôle per-symbol (E16→E17) | période **2025-01-02 → 2026-05-29**, moteur CLI production complet (preset + risk + sizing + coûts canoniques). |
| [`experiences/archives_recherche/e45_force_close_airbag_verdict.md`](experiences/archives_recherche/e45_force_close_airbag_verdict.md) | E45 — Crash-test catastrophe au VRAI seuil −15 % : KEEP vs WORST_50 vs ALL | **Protocole** : produire de VRAIS trips du breaker B4 (DD ≤ −15 %) **sans baisser le seuil**, via des |
| [`experiences/archives_recherche/e46_exposure_verdict.md`](experiences/archives_recherche/e46_exposure_verdict.md) | E46 — Verdict exposition (Phase B) — 2026-08-22 — DÉCISION : 1.46 retenu | Sharpe / Sortino / PF restent **constants** à travers 1.00→1.46→1.69 dans CHAQUE scénario (NORMAL 2025 : Sharpe 2.03/2.06/2.05 ; S3 2025 : 1 |
| [`experiences/archives_recherche/global_direction_h20.md`](experiences/archives_recherche/global_direction_h20.md) | GlobalDirection H20 — Recherche anti-D1 | Module de recherche (2026-08-26) : séparer les futurs **D10** (bon long) des |
| [`experiences/archives_recherche/global_direction_temporal.md`](experiences/archives_recherche/global_direction_temporal.md) | GlobalDirectionTemporal — Hypothèse temporelle (J-5/J-10) — 2026-08-26 | Les features statiques à J portent presque pas de direction ; leur **trajectoire |
| [`experiences/archives_recherche/go_live_b25_p14_m8_2026-08-17.md`](experiences/archives_recherche/go_live_b25_p14_m8_2026-08-17.md) | 🚀 Dossier de mise en réel — AlphaTrade (B25 + P14 + m8) | **MISE À JOUR 2026-08-19 (importante)** : le benchmark OOS 2026 original (+27.09%) utilisait un **TP fallback buggé** (max(12%, 2R) au lieu |
| [`experiences/archives_recherche/per_sector_todo.md`](experiences/archives_recherche/per_sector_todo.md) | Per-Sector — Dossier de décision pour GPT | **Date** : 2026-08-15 (mis à jour 2026-08-16 — benchmark gate B41 en production-parity) |
| [`experiences/archives_recherche/persistent_tail_price.md`](experiences/archives_recherche/persistent_tail_price.md) | persistent_tail_price_confirmation — 2026-08-27 | Expérience **diagnostique** (aucun réentraînement, aucun changement risk/PROD). |
| [`experiences/archives_recherche/persistent_top10_dip.md`](experiences/archives_recherche/persistent_top10_dip.md) | persistent_top10_dip_validation — 2026-08-27 | Validation du signal « GlobalRank TOP10 persistant + baisse récente » (DIP). |
| [`experiences/archives_recherche/rebench_canonique_postfix_tp_2026-08-19.md`](experiences/archives_recherche/rebench_canonique_postfix_tp_2026-08-19.md) | 📊 Étape A — Re-benchmark canonique post-fix TP (B25 P14 m8) | Seule différence vs original : **HEAD vs cceb808f** (fix TP inclus). Aucun autre paramètre modifié. |
| [`experiences/archives_recherche/smart_sector_cap_verdict_2026-08-27.md`](experiences/archives_recherche/smart_sector_cap_verdict_2026-08-27.md) | Chantier `smart_sector_cap` — Verdict C0/C1/C2 (2026-08-27) | Famille homogène 2022-01-01 → 2024-12-31, commande PROD identique pour les 3 runs |
| [`experiences/archives_recherche/stepB_C_timestop_parity_2026-08-19.md`](experiences/archives_recherche/stepB_C_timestop_parity_2026-08-19.md) | 🟡 Étapes B + C — Time-stop parity test sur baseline post-fix TP + décision | → Pas de bénéfice net robuste. **Le time_stop est redondant quand un trailing actif existe.** |
| [`experiences/archives_recherche/synthese_e6_e13_2026-08-20.md`](experiences/archives_recherche/synthese_e6_e13_2026-08-20.md) | Synthèse de clôture — E6 → E13 (2026-08-20) | Ce document raconte la **chaîne causale** E6→E13 (pas une succession de backtests), conserve |
| [`experiences/archives_recherche/synthese_gestion_drawdown_reprise_2026-08-21.md`](experiences/archives_recherche/synthese_gestion_drawdown_reprise_2026-08-21.md) | Synthèse — Gestion du Drawdown et reprise d'activité (2026-08-21) | Document autonome : décrit le système de gestion du risque de drawdown en place |
| [`experiences/campagnes_global_ranking/README.md`](experiences/campagnes_global_ranking/README.md) | Archives des campagnes Global Ranking | `test/` et `global_per_symbol_test/` conservent les rapports B0–B44 et essais per-symbol originaux. Ce sont des résultats historiques dépend |
| [`experiences/campagnes_global_ranking/test/B0 Baseline.md`](experiences/campagnes_global_ranking/test/B0%20Baseline.md) | Diagnostic ML — Batch `model-factory-20260809091632-a574c7` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B1 sentiement.md`](experiences/campagnes_global_ranking/test/B1%20sentiement.md) | Diagnostic ML — Batch `model-factory-20260809104004-44d3a8` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B10 Short + SPY + CAPM.md`](experiences/campagnes_global_ranking/test/B10%20Short%20%2B%20SPY%20%2B%20CAPM.md) | Diagnostic ML — Batch `model-factory-20260810160939-927f00` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B11 Short + SPY + Macro.md`](experiences/campagnes_global_ranking/test/B11%20Short%20%2B%20SPY%20%2B%20Macro.md) | Diagnostic ML — Batch `model-factory-20260810175924-7bd4ac` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B12 Short + SPY + Score histo.md`](experiences/campagnes_global_ranking/test/B12%20Short%20%2B%20SPY%20%2B%20Score%20histo.md) | Diagnostic ML — Batch `model-factory-20260810200031-9755c6` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B13 Short + SPY + sectoriel.md`](experiences/campagnes_global_ranking/test/B13%20Short%20%2B%20SPY%20%2B%20sectoriel.md) | Diagnostic ML — Batch `model-factory-20260810213112-95c7d0` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B14 Short + SPY + stacking.md`](experiences/campagnes_global_ranking/test/B14%20Short%20%2B%20SPY%20%2B%20stacking.md) | Diagnostic ML — Batch `model-factory-20260811073138-0a0b4f` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B15 Short + SPY + T1.md`](experiences/campagnes_global_ranking/test/B15%20Short%20%2B%20SPY%20%2B%20T1.md) | Diagnostic ML — Batch `model-factory-20260811095231-7b4179` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B16 Short + SPY + T2.md`](experiences/campagnes_global_ranking/test/B16%20Short%20%2B%20SPY%20%2B%20T2.md) | Diagnostic ML — Batch `model-factory-20260811110707-5029e9` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B17 Short + SPY + T3.md`](experiences/campagnes_global_ranking/test/B17%20Short%20%2B%20SPY%20%2B%20T3.md) | Diagnostic ML — Batch `model-factory-20260811144842-bd6976` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B18 Short + SPY + from 2011 + max 8 slits.md`](experiences/campagnes_global_ranking/test/B18%20Short%20%2B%20SPY%20%2B%20from%202011%20%2B%20max%208%20slits.md) | Diagnostic ML — Batch `model-factory-20260811165544-d4d6af` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B19 Short + SPY + from 2011 + max 16 slits.md`](experiences/campagnes_global_ranking/test/B19%20Short%20%2B%20SPY%20%2B%20from%202011%20%2B%20max%2016%20slits.md) | Diagnostic ML — Batch `model-factory-20260811184205-100f0a` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B2 scores screnner.md`](experiences/campagnes_global_ranking/test/B2%20scores%20screnner.md) | Diagnostic ML — Batch `model-factory-20260809115339-404c90` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B20 Short + SPY + YetiRank.md`](experiences/campagnes_global_ranking/test/B20%20Short%20%2B%20SPY%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260811213821-1bce18` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B21 Short + SPY + QueryRMSE.md`](experiences/campagnes_global_ranking/test/B21%20Short%20%2B%20SPY%20%2B%20QueryRMSE.md) | Diagnostic ML — Batch `model-factory-20260812001008-1ce659` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=lightgbm, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B22 Short + SPY + QuerySoftMax.md`](experiences/campagnes_global_ranking/test/B22%20Short%20%2B%20SPY%20%2B%20QuerySoftMax.md) | Diagnostic ML — Batch `model-factory-20260812001051-e2f0db` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=lightgbm, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B25 Short + SPY + CAPM + YetiRank.md`](experiences/campagnes_global_ranking/test/B25%20Short%20%2B%20SPY%20%2B%20CAPM%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260811223551-ef2cd0` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B26 Short + SPY + CAPM + QueryRMSE.md`](experiences/campagnes_global_ranking/test/B26%20Short%20%2B%20SPY%20%2B%20CAPM%20%2B%20QueryRMSE.md) | Diagnostic ML — Batch `model-factory-20260812064302-8843cf` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B27 Short + SPY + CAPM + QuerySoftMax.md`](experiences/campagnes_global_ranking/test/B27%20Short%20%2B%20SPY%20%2B%20CAPM%20%2B%20QuerySoftMax.md) | Diagnostic ML — Batch `model-factory-20260812064355-7faa02` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B3 scores short.md`](experiences/campagnes_global_ranking/test/B3%20scores%20short.md) | Diagnostic ML — Batch `model-factory-20260809132408-4d40c5` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B30 Short + SPY + YetiRank +  P1-3.md`](experiences/campagnes_global_ranking/test/B30%20Short%20%2B%20SPY%20%2B%20YetiRank%20%2B%20%20P1-3.md) | Diagnostic ML — Batch `model-factory-20260812151652-9aaddb` | Modèle 🏆 Champion: lightgbm (détail: H3=catboost, H5=catboost, H10=lightgbm, H15=lightgbm, H20=lightgbm) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B31 Short + SPY + Fondamentaux + YetiRank.md`](experiences/campagnes_global_ranking/test/B31%20Short%20%2B%20SPY%20%2B%20Fondamentaux%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260812185524-904666` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B32 Short + SPY + Score histo + YetiRank.md`](experiences/campagnes_global_ranking/test/B32%20Short%20%2B%20SPY%20%2B%20Score%20histo%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260812185649-98d980` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B33 Short + SPY + sectoriel + YetiRank.md`](experiences/campagnes_global_ranking/test/B33%20Short%20%2B%20SPY%20%2B%20sectoriel%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260812185814-da184f` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B34 scores screnner + YetiRank.md`](experiences/campagnes_global_ranking/test/B34%20scores%20screnner%20%2B%20YetiRank.md) | Diagnostic ML — Batch `model-factory-20260812190010-748dd9` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B35 B25 + symbols 196.md`](experiences/campagnes_global_ranking/test/B35%20B25%20%2B%20symbols%20196.md) | Diagnostic ML — Batch `model-factory-20260812232931-792070` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=lightgbm, H15=catboost, H20=lightgbm) — sélection par IC IR — 196 symbole |
| [`experiences/campagnes_global_ranking/test/B36 B20 + symbols 196.md`](experiences/campagnes_global_ranking/test/B36%20B20%20%2B%20symbols%20196.md) | Diagnostic ML — Batch `model-factory-20260812235655-c993b3` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=lightgbm) — sélection par IC IR — 196 symbole |
| [`experiences/campagnes_global_ranking/test/B37 B25 + symbols 393.md`](experiences/campagnes_global_ranking/test/B37%20B25%20%2B%20symbols%20393.md) | Diagnostic ML — Batch `model-factory-20260813092928-9f906f` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 393 symbole |
| [`experiences/campagnes_global_ranking/test/B38 B25 avec 300 symblos (parmi les 400).md`](experiences/campagnes_global_ranking/test/B38%20B25%20avec%20300%20symblos%20%28parmi%20les%20400%29.md) | Diagnostic ML — Batch `model-factory-20260813132105-a8aadc` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 300 symbole |
| [`experiences/campagnes_global_ranking/test/B39-B25-XGBoost-rank-ndcg-P3-3.md`](experiences/campagnes_global_ranking/test/B39-B25-XGBoost-rank-ndcg-P3-3.md) | Diagnostic ML — Batch `model-factory-20260813222929-c15ad8` | Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction |
| [`experiences/campagnes_global_ranking/test/B4 Short + SPY.md`](experiences/campagnes_global_ranking/test/B4%20Short%20%2B%20SPY.md) | Diagnostic ML — Batch `model-factory-20260809153352-2b4647` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B40-B4-volume-features-P3-5.md`](experiences/campagnes_global_ranking/test/B40-B4-volume-features-P3-5.md) | Diagnostic ML — Batch `model-factory-20260813230529-ca6dd8` | Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259235 lignes de prédiction |
| [`experiences/campagnes_global_ranking/test/B41-B25-volume-features-P3-5.md`](experiences/campagnes_global_ranking/test/B41-B25-volume-features-P3-5.md) | Diagnostic ML — Batch `model-factory-20260813231851-bb2e76` | Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259235 lignes de prédiction |
| [`experiences/campagnes_global_ranking/test/B42-B20-volume-features-P3-5.md`](experiences/campagnes_global_ranking/test/B42-B20-volume-features-P3-5.md) | Diagnostic ML — Batch `model-factory-20260814003436-7d8e60` | Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259235 lignes de prédiction |
| [`experiences/campagnes_global_ranking/test/B44-B41-config-global-only-train-end-2024-12-31.md`](experiences/campagnes_global_ranking/test/B44-B41-config-global-only-train-end-2024-12-31.md) | Diagnostic ML — Batch `model-factory-20260814204243-9535a3` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B5 Short + SPY + Vix.md`](experiences/campagnes_global_ranking/test/B5%20Short%20%2B%20SPY%20%2B%20Vix.md) | Diagnostic ML — Batch `model-factory-20260809173405-730267` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B6 Short + SPY + Vxn.md`](experiences/campagnes_global_ranking/test/B6%20Short%20%2B%20SPY%20%2B%20Vxn.md) | Diagnostic ML — Batch `model-factory-20260809191125-23cc62` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B7 Short + SPY + Vix3m.md`](experiences/campagnes_global_ranking/test/B7%20Short%20%2B%20SPY%20%2B%20Vix3m.md) | Diagnostic ML — Batch `model-factory-20260809211556-6f94d8` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B8 Short + SPY + Move.md`](experiences/campagnes_global_ranking/test/B8%20Short%20%2B%20SPY%20%2B%20Move.md) | Diagnostic ML — Batch `model-factory-20260809234022-4de46f` | Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/B9 Short + SPY + Fondamentaux.md`](experiences/campagnes_global_ranking/test/B9%20Short%20%2B%20SPY%20%2B%20Fondamentaux.md) | Diagnostic ML — Batch `model-factory-20260810052226-5de365` | Modèle 🏆 Champion: catboost (détail: H3=lightgbm, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symbole |
| [`experiences/campagnes_global_ranking/test/test_global_per_sector.md`](experiences/campagnes_global_ranking/test/test_global_per_sector.md) | 🧪 Comparaison des Tests — Global & Per-Sector | Fichier de suivi et comparaison des batches (B0, B1, B2, …). |
| [`experiences/filtres_et_direction.md`](experiences/filtres_et_direction.md) | Expériences filtres DIP, direction et nouvelles données | Retour : recherche quantitative |
| [`experiences/global_ranking_et_per_sector.md`](experiences/global_ranking_et_per_sector.md) | Expériences Global Ranking et per-sector — synthèse | Retour : dossier technique Global Ranking |
| [`experiences/oracle_extreme.md`](experiences/oracle_extreme.md) | Expériences Oracle — synthèse durable | Retour : dossier technique Oracle |
| [`experiences/risque_execution_lifecycle.md`](experiences/risque_execution_lifecycle.md) | Expériences risque, exécution et lifecycle — synthèse | Retour : exécution · backtesting |
| [`experiences/validation_et_recalibration.md`](experiences/validation_et_recalibration.md) | Expériences de validation, calibration et recalibration | Retour : gouvernance ML |
| [`sources_historiques/README.md`](sources_historiques/README.md) | Sources historiques conservées | Les fichiers de ce dossier préservent intégralement les informations retirées des anciens emplacements. Ils constituent des preuves historiq |
| [`sources_historiques/backup/backtesting/backtesting.md`](sources_historiques/backup/backtesting/backtesting.md) | Backtesting & Backfill — guide d’usage | Mise à jour : mai 2026 |
| [`sources_historiques/backup/data/EODHD_vs_Alpaca.md`](sources_historiques/backup/data/EODHD_vs_Alpaca.md) | EODHD vs Alpaca (IEX) — usage réel du volume dans l'application | Date d'analyse : 2026-05-10 |
| [`sources_historiques/backup/data/dataIntegrityEngine.md`](sources_historiques/backup/data/dataIntegrityEngine.md) | Data Integrity Engine — documentation détaillée de reprise | ✅ **Provider OHLCV primaire actuel : `EODHD` (bulk EOD consolidé).** |
| [`sources_historiques/backup/data/data_lineage_matrix.md`](sources_historiques/backup/data/data_lineage_matrix.md) | Matrice Data Lineage — table ↔ producteur ↔ consommateurs (Phase 7.6) | **Audience** : développeurs et opérateurs. |
| [`sources_historiques/backup/data/database.md`](sources_historiques/backup/data/database.md) | Database — Guide d'usage | Ce document résume le rôle du module `database/` et les usages utiles pour : |
| [`sources_historiques/backup/data/sector_normalization_full_production_sql.md`](sources_historiques/backup/data/sector_normalization_full_production_sql.md) | 🧠 ISecteurs métier principaux | sector_code sector_name |
| [`sources_historiques/backup/execution/calcul_tp_tl.md`](sources_historiques/backup/execution/calcul_tp_tl.md) | Calcul TP / SL / trailing : live vs backtest | Clarifier comment sont déterminés les trois niveaux de protection/sortie : |
| [`sources_historiques/backup/execution/execution_engine.md`](sources_historiques/backup/execution/execution_engine.md) | Execution Engine — Guide d'usage | Ce document résume le fonctionnement du module `execution_engine/` et les commandes utiles pour : |
| [`sources_historiques/backup/execution/watcher.md`](sources_historiques/backup/execution/watcher.md) | Watcher de protections — guide dédié | Ce document décrit le rôle, le positionnement et l'exploitation du watcher de protections post-exécution. |
| [`sources_historiques/backup/general/CONVENTIONS.md`](sources_historiques/backup/general/CONVENTIONS.md) | Conventions canoniques Alpha Trade | Source de vérité documentaire transversale pour les conventions encore en vigueur. |
| [`sources_historiques/backup/general/core_common.md`](sources_historiques/backup/general/core_common.md) | `core/` + `common/` — Modules de socle | Documentation Phase 2.1 du refactor (`prompt/refactor/plan.md`). |
| [`sources_historiques/backup/general/service.md`](sources_historiques/backup/general/service.md) | Service — Guide d'usage | Ce document résume le rôle du dossier `service/` et les usages utiles pour : |
| [`sources_historiques/backup/ihm/ihm.md`](sources_historiques/backup/ihm/ihm.md) | IHM — Guide d'usage | Ce document résume le fonctionnement du module `ihm/` et les commandes utiles pour : |
| [`sources_historiques/backup/ihm/question_1.md`](sources_historiques/backup/ihm/question_1.md) | Réponses détaillées à `doc/question.txt` | Document rédigé à partir du code, de la documentation et des tests présents dans le workspace. |
| [`sources_historiques/backup/ml/AlignementEchelles.md`](sources_historiques/backup/ml/AlignementEchelles.md) | Alignement des Échelles — Diagnostic Normalisation avant Fusion ML/Quant | **Date** : 2026-06-22 |
| [`sources_historiques/backup/ml/features_ml.md`](sources_historiques/backup/ml/features_ml.md) | 📊 Features ML — Documentation des paramètres | Fichier de référence listant chaque flag `--include-*` / `--target-*`, son rôle, les features concernées, et le statut de propagation dans l |
| [`sources_historiques/backup/ml/ml.md`](sources_historiques/backup/ml/ml.md) | Documentation des paramètres ML — IHM Pipeline (Model Factory) | Page IHM : `Pipeline` → bloc **Paramètres Model Factory** |
| [`sources_historiques/backup/ml/modelFactory.md`](sources_historiques/backup/ml/modelFactory.md) | Model Factory — Référence complète | `modelFactory/` est le module ML opérationnel du projet. Il ne se limite plus à un simple entraînement LSTM par symbole. |
| [`sources_historiques/backup/ml/module_model_factory.md`](sources_historiques/backup/ml/module_model_factory.md) | Module ModelFactory — Documentation Complète | **Version** : Sprint 2026-08-04 (batch f82ab5, per-sector + global ranking) — mise à jour 2026-08-14 (pivot per-symbol) |
| [`sources_historiques/backup/ml/ordre_execution_ml.md`](sources_historiques/backup/ml/ordre_execution_ml.md) | Ordre d'exécution ML — Calibration & Validation | **Date** : 2026-08-13 |
| [`sources_historiques/backup/ml/poid.md`](sources_historiques/backup/ml/poid.md) | Répartition des Poids dans la Chaîne de Décision | Synthèse générée le 2026-06-20 — source : codebase Alpha Trade |
| [`sources_historiques/backup/operations/corporate_actions.md`](sources_historiques/backup/operations/corporate_actions.md) | Corporate Actions — Guide d'usage | Ce document résume le fonctionnement du module `corporate_actions/` et les commandes utiles pour : |
| [`sources_historiques/backup/operations/observability.md`](sources_historiques/backup/operations/observability.md) | Observabilité — Endpoint `/metrics` Prometheus (Phase 7.5) | **Audience** : opérateurs Alpha Trade. |
| [`sources_historiques/backup/operations/runbook_24_7.md`](sources_historiques/backup/operations/runbook_24_7.md) | Runbook 24/7 — Alpha Trade | Phase C / S18.1. Procédures opérationnelles pour l'astreinte. |
| [`sources_historiques/backup/operations/runbook_provider_incident.md`](sources_historiques/backup/operations/runbook_provider_incident.md) | Runbook — Incident provider data (Phase 7.6) | **Audience** : opérateur on-call Alpha Trade. |
| [`sources_historiques/backup/operations/runbook_reconciliation.md`](sources_historiques/backup/operations/runbook_reconciliation.md) | Runbook — Réconciliation `MANUAL_REVIEW` / `BLOCKED` (Phase 7.6) | **Audience** : opérateur on-call. |
| [`sources_historiques/backup/risk/macro_regime.md`](sources_historiques/backup/risk/macro_regime.md) | Macro regime — impact concret sur le backtest et le live | Ce document centralise les explications fonctionnelles et techniques sur la couche **macro / market regime** du projet : |
| [`sources_historiques/backup/risk/mode_regime.md`](sources_historiques/backup/risk/mode_regime.md) | FAQ opérateur — Mode régime Market-Aware | ⚠️ **POC non activé** : note d'accompagnement opérateur. La référence |
| [`sources_historiques/backup/risk/risk_management.md`](sources_historiques/backup/risk/risk_management.md) | Risk Management — Guide d'usage | Dernière mise à jour : 2026-06-22 — Contrainte de liquidité dynamique (P1/P3/P4) livrée |
| [`sources_historiques/backup/signals/event_sentiment.md`](sources_historiques/backup/signals/event_sentiment.md) | Event Sentiment — Guide d'usage | Ce document résume le fonctionnement du module `event_sentiment/` et les commandes utiles pour : |
| [`sources_historiques/backup/signals/pipelin_sentiment.md`](sources_historiques/backup/signals/pipelin_sentiment.md) | Pipeline sentiment — notes de synthèse | Cette note résume les explications utiles sur le pipeline sentiment du projet, en particulier : |
| [`sources_historiques/backup/signals/screener.md`](sources_historiques/backup/signals/screener.md) | Screener — Guide d'usage | Ce document résume le fonctionnement du module `screener/` et les commandes utiles pour : |
| [`sources_historiques/backup/signals/selector-driven.md`](sources_historiques/backup/signals/selector-driven.md) | Contrat selector-driven | Ce document fige le contrat **selector-driven** aujourd’hui exposé côté opérateur et consommé par les briques avales `modelFactory`, IHM et |
| [`sources_historiques/backup/signals/selector.md`](sources_historiques/backup/signals/selector.md) | Selector — Guide d'usage | Ce document résume le fonctionnement du module `selector/` et les commandes utiles pour : |
| [`sources_historiques/backup/signals/selector_pipeline_compatibility.md`](sources_historiques/backup/signals/selector_pipeline_compatibility.md) | Compatibilité pipeline `screener` → `selector` → `modelFactory` | Cette note synthétise l’état de compatibilité autour des enrichissements récents du `selector` : |
| [`sources_historiques/backup/signals/sentiment_issue.md`](sources_historiques/backup/signals/sentiment_issue.md) | Diagnostic et reprise — pipeline `event_sentiment` | Ce document trace le diagnostic, les corrections apportées et la reprise opératoire effectuée pour le pipeline sentiment, avec priorité sur |
| [`sources_historiques/backup/signals/sentiments_migration.md`](sources_historiques/backup/signals/sentiments_migration.md) | Migration des résultats du pipeline « Import + score + history_backfill + relevance_backfill auto » | Date d'analyse : 2026-05-10 |
| [`sources_historiques/external_audit/ia1.md`](sources_historiques/external_audit/ia1.md) | Audit externe IA — Alpha Trade | _Date : 2026-05-13_ |
| [`sources_historiques/manuel/00_README.md`](sources_historiques/manuel/00_README.md) | 📖 Manuels utilisateur — Alpha Trade IHM | **Public visé** : utilisateur débutant, n'ayant **jamais** utilisé |
| [`sources_historiques/manuel/01_demarrage_rapide.md`](sources_historiques/manuel/01_demarrage_rapide.md) | 1. Démarrage rapide — installer et lancer l'IHM | Objectif : à la fin de ce manuel vous voyez la page d'accueil de l'IHM |
| [`sources_historiques/manuel/02_premiers_pas_ihm.md`](sources_historiques/manuel/02_premiers_pas_ihm.md) | 2. Premiers pas dans l'IHM — visite guidée | Objectif : comprendre la structure de l'interface. **Aucun lancement** ici, |
| [`sources_historiques/manuel/03_workflow_quotidien.md`](sources_historiques/manuel/03_workflow_quotidien.md) | 3. Workflow quotidien — comprendre le cycle complet | Objectif : comprendre **dans quel ordre** les choses doivent être lancées |
| [`sources_historiques/manuel/04_page_pipeline.md`](sources_historiques/manuel/04_page_pipeline.md) | 4. Page 🔄 Pipeline — orchestrer le cycle quotidien | C'est la page la plus utilisée. Elle permet de : |
| [`sources_historiques/manuel/05_page_screening.md`](sources_historiques/manuel/05_page_screening.md) | 5. Page 📊 Screening — l'univers des candidats | Consulter la table `stock_scores` produite par les étapes Screener + |
| [`sources_historiques/manuel/06_page_ml_predictions.md`](sources_historiques/manuel/06_page_ml_predictions.md) | 6. Page 🤖 ML / Prédictions — comprendre le modèle d'IA | Voir et gérer les **modèles de Machine Learning** qui prédisent la |
| [`sources_historiques/manuel/07_page_risk.md`](sources_historiques/manuel/07_page_risk.md) | 7. Page ⚖️ Risk — gestion du risque | Voir les **décisions de risque** : combien acheter de chaque ligne, où |
| [`sources_historiques/manuel/08_page_execution.md`](sources_historiques/manuel/08_page_execution.md) | 8. Page 🚀 Execution — envoyer les ordres au broker | Voir et superviser les **runs d'exécution** : quels ordres ont été envoyés |
| [`sources_historiques/manuel/09_page_corporate_actions.md`](sources_historiques/manuel/09_page_corporate_actions.md) | 9. Page 📑 Corporate Actions — dividendes, splits, etc. | Voir les **événements corporate** (dividendes, splits, fusions, spin-offs) |
| [`sources_historiques/manuel/10_page_backtesting.md`](sources_historiques/manuel/10_page_backtesting.md) | 10. Page 🧪 Backtesting — préparer et tester une stratégie sur l'historique | **But de ce chapitre** : produire un backtest reproductible, sans fuite |
| [`sources_historiques/manuel/11_page_parity.md`](sources_historiques/manuel/11_page_parity.md) | 11. Page 🔀 Parité Backtest ↔ Live | Comparer les décisions **simulées** (backtest) aux décisions **réelles** |
| [`sources_historiques/manuel/12_page_supervision_ops.md`](sources_historiques/manuel/12_page_supervision_ops.md) | 12. Page 🛟 Supervision Ops | Surveiller les **processus en arrière-plan** : pipeline qui tournent encore, |
| [`sources_historiques/manuel/17_page_settings.md`](sources_historiques/manuel/17_page_settings.md) | 17. Page ⚙️ Paramètres / Santé | ML, Sentiment, Execution). |
| [`sources_historiques/manuel/20_gestion_petit_capital_2000eur.md`](sources_historiques/manuel/20_gestion_petit_capital_2000eur.md) | 20. Guide micro-compte ~2 000 € — paramétrage et bonnes pratiques | Ce manuel est **incontournable** si vous démarrez avec ~2 000 € (~2 150 USD). |
| [`sources_historiques/manuel/30_glossaire_financier.md`](sources_historiques/manuel/30_glossaire_financier.md) | 30. Glossaire financier | Définitions volontairement simples, en français, illustrées. |
| [`sources_historiques/manuel/31_glossaire_application.md`](sources_historiques/manuel/31_glossaire_application.md) | 31. Glossaire technique de l'application | Termes spécifiques au code, à la base de données et aux artefacts. |
| [`sources_historiques/manuel/40_workflow_type_swing_2000eur.md`](sources_historiques/manuel/40_workflow_type_swing_2000eur.md) | 40. Workflow type swing trader débutant ~2 000 € | Journée type, heure par heure, pour une routine **swing trade discipline |
| [`sources_historiques/manuel/50_faq.md`](sources_historiques/manuel/50_faq.md) | 50. FAQ — questions fréquentes des débutants | Comptez **6 mois minimum** : 2 mois en simulate + 3 mois en paper + |
| [`sources_historiques/manuel/51_depannage.md`](sources_historiques/manuel/51_depannage.md) | 51. Dépannage | Mauvais `ALPACA_API_KEY` / `_SECRET`. Régénérez-les sur |
| [`sources_historiques/manuel/52_securite_et_argent_reel.md`](sources_historiques/manuel/52_securite_et_argent_reel.md) | 52. Sécurité & passage en argent réel — checklist obligatoire | ⚠️ **Lisez ce document en entier avant tout passage en mode `live`.** |
| [`sources_historiques/manuel/99_pour_aller_plus_loin.md`](sources_historiques/manuel/99_pour_aller_plus_loin.md) | 99. Pour aller plus loin | Vous maîtrisez l'IHM. Voici la documentation **avancée** pour comprendre |
| [`sources_historiques/manuel/README.md`](sources_historiques/manuel/README.md) | Ancien manuel utilisateur | Ces 22 fichiers sont conservés intégralement pour la traçabilité. Ils ne doivent plus être utilisés comme procédure opérationnelle : navigat |
| [`sources_historiques/ml_old/filtre_ml.md`](sources_historiques/ml_old/filtre_ml.md) | 🔍 Filtre ML — Diagnostics batch pour live & backtest | **Créé le** : 2026-07-23 |
| [`sources_historiques/ml_old/ml_hybride.md`](sources_historiques/ml_old/ml_hybride.md) | ML Hybride — Features Cross-Sectionnelles & Sectorielles | L'application `modelFactory` est une architecture **per-symbol** : un modèle indépendant (LSTM / LightGBM / CatBoost) est entraîné par titre |
| [`sources_historiques/ml_old/ml_refactor_1.md`](sources_historiques/ml_old/ml_refactor_1.md) | ML Refactor 1 - Plan concret d'amelioration de l'entrainement | La campagne du 2026-07-12 a entraine 2067 symboles. Les moyennes par symbole sont : |
| [`sources_historiques/onboarding_assets/README.md`](sources_historiques/onboarding_assets/README.md) | Assets vidéo onboarding | Sprint S25.3 — Phase G. |
| [`sources_historiques/racine_doc/CHANGELOG.md`](sources_historiques/racine_doc/CHANGELOG.md) | Changelog documentaire Alpha Trade | Journal synthétique des changements de conventions, docs structurantes et clarifications opératoires. |
| [`sources_historiques/racine_doc/DOC_FONCTIONNELLE.md`](sources_historiques/racine_doc/DOC_FONCTIONNELLE.md) | Alpha Trade — Documentation Fonctionnelle | *Version : 0.5.0 — Dernière mise à jour : 2026-07-11 (cutover ML-first long/short)* |
| [`sources_historiques/racine_doc/DOC_TECHNIQUE.md`](sources_historiques/racine_doc/DOC_TECHNIQUE.md) | Alpha Trade — Documentation Technique | *Version : 0.5.0 — Python ≥ 3.12 — Dernière mise à jour : 2026-07-11 (cutover ML-first long/short)* |
| [`sources_historiques/racine_doc/alpha_trade_anti_overfitting_oos_protocol_2026-08-22.md`](sources_historiques/racine_doc/alpha_trade_anti_overfitting_oos_protocol_2026-08-22.md) | α-Trade — Synthèse anti-overfitting et protocole de validation OOS | Les travaux réalisés sur α-Trade ont apporté beaucoup d'informations utiles : correction de bugs, amélioration de la parité backtest ↔ produ |
| [`sources_historiques/racine_doc/alpha_trade_recalibration_guide.md`](sources_historiques/racine_doc/alpha_trade_recalibration_guide.md) | α-Trade — Guide complet de recalibration après changement majeur de modèle ou d’univers | Ce document sert de guide de maintenance et de passation pour une personne qui reprend l’application sans connaître tout l’historique des re |
| [`sources_historiques/racine_doc/controle_couverture.md`](sources_historiques/racine_doc/controle_couverture.md) | Contrôle de couverture ML — documentation complète | Dernière mise à jour : 2026-08-27. |
| [`sources_historiques/racine_doc/ml_calivraiton_important.md`](sources_historiques/racine_doc/ml_calivraiton_important.md) | ml_calivraiton_important | — |
| [`sources_historiques/racine_doc/ml_oracle.md`](sources_historiques/racine_doc/ml_oracle.md) | Spécification — Oracle Layer au-dessus du Global Model | **Statut** : 📐 Spécification (2026-08-18) — révisée suite au retour opérateur (même jour) |
| [`sources_historiques/racine_doc/ml_oracle_sprint.md`](sources_historiques/racine_doc/ml_oracle_sprint.md) | Plan de sprint — Oracle Layer (TOP / BOTTOM) | **⚠️ REFACTOR 2026-08-19** : le modèle **Oracle TOP est renommé Oracle Extreme** |
| [`sources_historiques/racine_doc/mode_cascade.md`](sources_historiques/racine_doc/mode_cascade.md) | Modes de cascade — combinaison Global Rank × Oracle Extreme | Statut : implémenté (CLI `--cascade-rank-mode` + sélecteur dans la page backtesting IHM). |
| [`sources_historiques/racine_doc/model_extreme_mode.md`](sources_historiques/racine_doc/model_extreme_mode.md) | Modèle Oracle Extreme — Modes d'entraînement & dépendance à `global_rank_history` | échoue (`empty dataset → skipped → compté failed`) en mode **after-sequence**, et comment |
| [`sources_historiques/racine_doc/mutation_history.md`](sources_historiques/racine_doc/mutation_history.md) | Mutation history (auto) | — |
| [`sources_historiques/racine_doc/oracle_extreme.md`](sources_historiques/racine_doc/oracle_extreme.md) | Oracle Extreme — Gate d'univers LONG (composant officiel E6→E13) | (TP 12 %/SL 7 % au lieu de config prod) — **valeurs corrigées en §13** (EXT A = +113,1 %, B25 long-only = +175,7 %). |
| [`sources_historiques/racine_doc/per_sector.md`](sources_historiques/racine_doc/per_sector.md) | Synthèse Per-Sector — α-Trade (contexte pour recherche de leviers) | **Date** : 2026-08-15 |
| [`sources_historiques/racine_doc/recherche_vs_pipeline.md`](sources_historiques/racine_doc/recherche_vs_pipeline.md) | Recherche vs Pipeline — TP / SL / Trailing : pourquoi +175 % vs +9 % ? | chiffres vérifiés sur les 208 trades partagés (prix d'entrée identiques à 100 %). |

## Backtests et validation

| Document | Titre | Description |
|---|---|---|
| [`backtesting/README.md`](backtesting/README.md) | Références Backtesting | 1. Replay broker-like |
| [`backtesting/microstructure_et_couts.md`](backtesting/microstructure_et_couts.md) | Microstructure, coûts et résolution intrabar | Retour : références Backtesting |
| [`backtesting/parite_live_backtest.md`](backtesting/parite_live_backtest.md) | Parité live/backtest | Retour : références Backtesting |
| [`backtesting/replay_broker_like.md`](backtesting/replay_broker_like.md) | Architecture de replay broker-like | Retour : références Backtesting |
| [`backtesting/report_json_et_artefacts.md`](backtesting/report_json_et_artefacts.md) | `report.json` et artefacts de backtesting | `report.json` est le contrat machine entre moteur, IHM, tests et analyses. Le producteur principal est `backtesting/report.py`. Le contrat m |
| [`backtesting/validation_statistique.md`](backtesting/validation_statistique.md) | Validation statistique et promotion | Retour : références Backtesting |

## Bases et migrations

| Document | Titre | Description |
|---|---|---|
| [`database/ajouter_une_table.md`](database/ajouter_une_table.md) | Ajouter ou faire évoluer une table | Une table n’est pas terminée quand son DDL existe. Il faut aligner migration Alembic, repository, transactions/idempotence, producteurs, con |
| [`database/async_db_poc.md`](database/async_db_poc.md) | Accès base asynchrone — POC opt-in | L’async n’est pas le chemin de production par défaut. `database/async_engine.py` ne l’active que lorsque `ALPHA_TRADE_ASYNC_DB` vaut `1`, `t |
| [`database/migrations_et_transactions.md`](database/migrations_et_transactions.md) | Migrations, transactions et idempotence | Retour : base de données |
| [`database/schema_metier.md`](database/schema_metier.md) | Schéma métier et ownership des tables | Retour : base de données |

## Conformité & Audit

| Document | Titre | Description |
|---|---|---|
| [`AUDIT_COMPLET_DOCUMENTATION_20261010.md`](AUDIT_COMPLET_DOCUMENTATION_20261010.md) | Révision du corpus documentaire — 10 octobre 2026 | La révision couvre l'ensemble de `doc` : 665 Markdown au départ, plus les |
| [`AUDIT_MISE_A_JOUR_20261010.md`](AUDIT_MISE_A_JOUR_20261010.md) | Audit documentaire ciblé — 10 octobre 2026 | Rapprocher les guides d'entrée/exploitation des sources actuelles, après les |
| [`AUDIT_REMPLACEMENT.md`](AUDIT_REMPLACEMENT.md) | Audit de remplacement de l’ancienne documentation | Le référentiel `doc/refactor/` est autonome pour l'onboarding, l'exploitation, |

## Divers

| Document | Titre | Description |
|---|---|---|
| [`COUVERTURE_DOCUMENTS_HISTORIQUES.md`](COUVERTURE_DOCUMENTS_HISTORIQUES.md) | Couverture des documents historiques | Cet inventaire couvre les **178 fichiers Markdown** présents hors |
| [`COVERAGE_CODE.md`](COVERAGE_CODE.md) | Couverture de la documentation par rapport au code | La couverture statique est contrôlée en partant du code actuel. Les packages |
| [`MAINTENANCE_DOCUMENTAIRE.md`](MAINTENANCE_DOCUMENTAIRE.md) | Maintenir la documentation à partir des sources | Le point d'entrée est README. Les guides 01–22 et |
| [`MIGRATION_BACKUP.md`](MIGRATION_BACKUP.md) | Migration exhaustive de `doc/backup` | Cette matrice suit les 64 fichiers trouvés le 29 août 2026. La destination est autonome sous `doc/refactor`; le code courant prime. Audits, |
| [`MIGRATION_RESTE_DOC.md`](MIGRATION_RESTE_DOC.md) | Migration du reste de l’ancien répertoire `doc` | Ce registre couvre tous les fichiers qui restaient hors `doc/refactor`. Les références globales sont conservées comme sources historiques ; |
| [`SOURCES.md`](SOURCES.md) | Traçabilité de la refonte documentaire | La première refonte ci-dessous est une trace historique. Elle est complétée |
| [`batchs_perimetres_marches.md`](batchs_perimetres_marches.md) | Page Batch — périmètres US, CN et FR séparés | Actualisé le **10 octobre 2026** : catalogue courant |
| [`mode_cascade.md`](mode_cascade.md) | Cascade de sélection et modes de ranking | Mise à jour du 4 octobre 2026 : les modes Extreme Gate disposent du |

## Documentation centrale actuelle

| Document | Titre | Description |
|---|---|---|
| [`01_vue_fonctionnelle.md`](01_vue_fonctionnelle.md) | Vue fonctionnelle | Alpha Trade regroupe recherche, ML, backtests et exploitation de stratégies actions. |
| [`02_architecture_globale.md`](02_architecture_globale.md) | Architecture globale | État multi-marchés au 10/10/2026 : synthèse actuelle. |
| [`03_installation_et_demarrage.md`](03_installation_et_demarrage.md) | Installation et démarrage | Le bootstrap ci-dessous concerne le parcours **US**. Pour CN/FR, créer/résoudre |
| [`04_pipeline_quotidien.md`](04_pipeline_quotidien.md) | Pipeline quotidien US et déclinaisons par marché | Le workflow US exposé par `ihm/services/pipeline_runner.py` offre 14 étapes. |
| [`05_donnees_et_univers_pit.md`](05_donnees_et_univers_pit.md) | Données, qualité et univers PIT | Ce document donne la vue transversale. Les contrats algorithmiques, paramètres, erreurs et procédures de reprise vivent dans les références |
| [`06_ml_vue_ensemble.md`](06_ml_vue_ensemble.md) | Module ML — vue d'ensemble | Ce document positionne les familles. Les documents spécialisés détaillent les algorithmes et les contrats reproductibles. |
| [`07_ml_global_ranking.md`](07_ml_global_ranking.md) | ML — Global Ranking | Point d'entrée détaillé : |
| [`08_ml_oracle_extreme.md`](08_ml_oracle_extreme.md) | ML — Oracle Extreme O0 | Documentation approfondie : dossier Oracle Extreme complet. |
| [`09_risque_et_portefeuille.md`](09_risque_et_portefeuille.md) | Gestion du risque et construction du portefeuille | Le régime de marché dispose également de sa référence autonome. |
| [`10_regime_marche.md`](10_regime_marche.md) | Régime de marché | Le moteur `service/market/` produit un `MarketRegimeSnapshot` injecté au risque et au backtest. Il est conçu avec providers injectables pour |
| [`11_execution_et_protections.md`](11_execution_et_protections.md) | Exécution, ordres et protections | `python run_execution.py simulate\|paper\|live\|check` est le launcher du flux normal. `python -m execution_engine` reste une façade de compati |
| [`12_backtesting_validation.md`](12_backtesting_validation.md) | Backtesting, parité et validation | `backtesting/` rejoue signaux, risque et exécution avec données PIT et coûts réalistes. Sa fonction n'est pas seulement de calculer un PnL : |
| [`13_screener_selector_sentiment.md`](13_screener_selector_sentiment.md) | Screener, Selector et Event Sentiment | `screener/` traite l'univers large par chunks et deux passes. Il calcule liquidité moyenne, force relative vs benchmark et position dans le |
| [`14_services_externes.md`](14_services_externes.md) | Services externes et adaptateurs | Le package `service/` isole les communications externes et les politiques de retry/cache/télémétrie. |
| [`15_base_de_donnees.md`](15_base_de_donnees.md) | Base de données et persistance | Le chemin legacy US `database/connection.py` construit l'engine SQLAlchemy depuis |
| [`16_ihm_et_operations.md`](16_ihm_et_operations.md) | IHM, supervision et opérations | `ihm/app.py` est le point d'entrée Streamlit. `ihm/pages/` contient les pages métier ; `ihm/components/` les composants de rendu ; `ihm/serv |
| [`17_corporate_actions.md`](17_corporate_actions.md) | Corporate actions | Référence spécialisée : dividendes, splits et réconciliation. |
| [`18_reference_configuration.md`](18_reference_configuration.md) | Référence de configuration | `config.yaml` porte le profil US et les options communes, complétés par les |
| [`19_tests_et_contribution.md`](19_tests_et_contribution.md) | Tests, qualité et contribution | Référence spécialisée : fuzzing, mutation et vérification formelle. |
| [`20_glossaire.md`](20_glossaire.md) | Glossaire | — |
| [`21_catalogue_modules.md`](21_catalogue_modules.md) | Catalogue des modules et fichiers clés | Ce catalogue aide à localiser rapidement le propriétaire d'un comportement. Les fonctions privées ne sont pas une API stable ; partir du poi |
| [`22_runbook_exploitation.md`](22_runbook_exploitation.md) | Runbook d'exploitation | Références : failover broker, pré-live, sandbox health et sauvegarde/reprise. |
| [`ETAT_ACTUEL_IMPLEMENTATION.md`](ETAT_ACTUEL_IMPLEMENTATION.md) | État actuel de l'implémentation — 10 octobre 2026 | Ce document rapproche les guides du **code et des fichiers de configuration |
| [`README.md`](README.md) | Documentation Alpha Trade — référentiel fonctionnel et opérationnel | l'état actuel de l'implémentation et |

## Données et ingestion

| Document | Titre | Description |
|---|---|---|
| [`data/README.md`](data/README.md) | Références Data | Cette section documente les contrats d'acquisition et de qualité au niveau nécessaire pour maintenir ou auditer le pipeline. |
| [`data/ingestion_eodhd.md`](data/ingestion_eodhd.md) | Ingestion EODHD et backfill historique | Retour : références Data · vue globale |
| [`data/integrite_lineage_et_qualite.md`](data/integrite_lineage_et_qualite.md) | Intégrité, lineage et qualité des données | Complétude, fraîcheur, unicité, validité, cohérence inter-tables, temporalité PIT |
| [`data/quotes_et_earnings.md`](data/quotes_et_earnings.md) | Quotes, spreads et calendrier earnings | Retour : références Data |
| [`data/sanitizer_daily.md`](data/sanitizer_daily.md) | Sanitizer daily et audits qualité | Retour : références Data |
| [`data/univers_pit.md`](data/univers_pit.md) | Univers tradable PIT et gate d'entrée | Retour : références Data |

## Exploitation et batchs

| Document | Titre | Description |
|---|---|---|
| [`operations/alerting_et_metriques.md`](operations/alerting_et_metriques.md) | Alerting multicanal, notifications IHM et métriques | Retour : IHM et opérations |
| [`operations/broker_failover.md`](operations/broker_failover.md) | Failover broker Alpaca vers IBKR | `service/broker_failover.py` fournit `FailoverBrokerClient`. Le primaire reçoit toutes les opérations tant que son circuit est fermé. Après |
| [`operations/catalogue_batchs_actuel.md`](operations/catalogue_batchs_actuel.md) | Catalogue opérationnel des batchs — 10 octobre 2026 | Inventaire rapproché de `ihm/services/batch_management.py`, des trois YAML, |
| [`operations/compliance_et_audit.md`](operations/compliance_et_audit.md) | Compliance et auditabilité | Pouvoir expliquer une décision depuis les données disponibles jusqu’au broker, |
| [`operations/corporate_actions_reference.md`](operations/corporate_actions_reference.md) | Corporate actions — dividendes, splits et réconciliation | Retour : corporate actions |
| [`operations/evolution_et_compatibilite.md`](operations/evolution_et_compatibilite.md) | Évolution, compatibilité et dépréciation | Schéma DB/migrations, configuration, manifests d’artefacts, CLI, pages IHM et |
| [`operations/fiscalite_wash_sale.md`](operations/fiscalite_wash_sale.md) | Fiscalité — détecteur de wash sale | Retour : reporting, lineage et formal |
| [`operations/forward_pit_batches.md`](operations/forward_pit_batches.md) | Batchs de collecte Forward PIT | Rapprochement du 10/10/2026 : le |
| [`operations/horaires_fr_cn_presence_pc.md`](operations/horaires_fr_cn_presence_pc.md) | Horaires FR/CN — présence du PC, 10 octobre 2026 | Le PC est disponible avant 07:30 et à partir de **20:00 Europe/Paris**. |
| [`operations/ihm_reference.md`](operations/ihm_reference.md) | IHM Streamlit — architecture, orchestration et extension | Retour : IHM et opérations |
| [`operations/monitoring/README.md`](operations/monitoring/README.md) | Actifs Prometheus et Grafana | Le registre est local au processus et repart à zéro au redémarrage. Après changement des métriques, revalider chaque expression dans ces deu |
| [`operations/performance_et_capacite.md`](operations/performance_et_capacite.md) | Performance, capacité et quotas | CPU et mémoire pour features/ML, connexions et écritures DB, latence broker, |
| [`operations/pre_live_et_progression.md`](operations/pre_live_et_progression.md) | Pré-live et montée progressive du capital | `execution_engine/preflight.py`, appelé par `scripts/run_pre_live_checklist.py`, vérifie l’environnement courant. `risk_management/pre_live_ |
| [`operations/qualite_avancee_fuzz_mutation_formel.md`](operations/qualite_avancee_fuzz_mutation_formel.md) | Qualité avancée : fuzzing, mutation et vérification formelle | Ces outils complètent les tests classiques. Ils ne prouvent pas seuls le système en production : chacun vérifie un modèle, un espace d’entré |
| [`operations/reporting_lineage_formal.md`](operations/reporting_lineage_formal.md) | Reporting mensuel, lineage, fiscalité et vérification formelle | Retour : IHM et opérations |
| [`operations/sandbox_health.md`](operations/sandbox_health.md) | Sandbox health nocturne | `ihm/services/sandbox_health_loader.py` lit `artifacts/sandbox_runs/_rollup.json` et `<date>/health.json`. Absence ou JSON invalide retourne |
| [`operations/sauvegarde_reprise_et_retention.md`](operations/sauvegarde_reprise_et_retention.md) | Sauvegarde, reprise après incident et rétention | État des jobs au 10/10/2026 : |
| [`operations/securite_live.md`](operations/securite_live.md) | Sécurité live et protection de l’argent réel | Le passage live est un changement d’autorité, pas un simple paramètre. Chaque |
| [`operations/supervision_et_securite.md`](operations/supervision_et_securite.md) | Supervision, notifications et sécurité | Voir aussi failover broker, pré-live et sandbox health. |
| [`operations/us_pipeline.md`](operations/us_pipeline.md) | Batch US — Pipeline quotidien configurable 1 à 14 | `us_pipeline`, déclaré dans `batch.yaml`, enchaîne les étapes sélectionnées dans |

## Exécution et protections

| Document | Titre | Description |
|---|---|---|
| [`execution/README.md`](execution/README.md) | Références Execution | 1. Lifecycle des ordres |
| [`execution/ibkr.md`](execution/ibkr.md) | Adaptateur Interactive Brokers (IBKR) | `service/ibkr/client.py` utilise `ib_insync`. L’instanciation lève `IBKRUnavailableError` si package ou TWS/Gateway manque. Le défaut `reado |
| [`execution/lifecycle_ordres.md`](execution/lifecycle_ordres.md) | Lifecycle des ordres et machine d'état | Retour : références Execution |
| [`execution/protections_et_watcher.md`](execution/protections_et_watcher.md) | Protections OCO, break-even, trailing et watcher | Retour : références Execution |
| [`execution/reconciliation_et_tca.md`](execution/reconciliation_et_tca.md) | Réconciliation, reprise et Transaction Cost Analysis | Retour : références Execution |

## Guide utilisateur IHM

| Document | Titre | Description |
|---|---|---|
| [`guide_utilisateur/01_demarrage_navigation_securite.md`](guide_utilisateur/01_demarrage_navigation_securite.md) | Démarrage, navigation et sécurité opérateur | L’application repose sur plusieurs états externes : base de données, fichiers |
| [`guide_utilisateur/02_workflow_quotidien.md`](guide_utilisateur/02_workflow_quotidien.md) | Workflow quotidien de bout en bout | Ce chapitre décrit le parcours d'exploitation **US**. CN/FR ont des parcours |
| [`guide_utilisateur/03_pipeline.md`](guide_utilisateur/03_pipeline.md) | Page Pipeline — guide opérateur détaillé | Au 10/10/2026, choisir le parcours marché avant de configurer les blocs. CN/FR |
| [`guide_utilisateur/04_screening.md`](guide_utilisateur/04_screening.md) | Page Screening — scores, recommandations et explicabilité | La page consulte les sorties de screening persistées et les artefacts associés. |
| [`guide_utilisateur/05_ml_predictions.md`](guide_utilisateur/05_ml_predictions.md) | Page ML / Prédictions — gouvernance, serving et audit | Les listes de batches/diagnostics Oracle doivent être lues avec l'horizon de |
| [`guide_utilisateur/06_risque.md`](guide_utilisateur/06_risque.md) | Page Risk — décisions, contraintes et portefeuille cible | Le moteur de risque transforme les intentions issues du ranking/screener en |
| [`guide_utilisateur/07_execution.md`](guide_utilisateur/07_execution.md) | Page Execution — du portefeuille cible au broker | Le contrat ci-dessous est le parcours US Alpaca. Le shadow FR et les lectures |
| [`guide_utilisateur/08_backtesting.md`](guide_utilisateur/08_backtesting.md) | Page Backtesting — fidélité, diagnostics et campagnes | La page est un centre opérateur autour de plusieurs commandes du package |
| [`guide_utilisateur/09_supervision_parite.md`](guide_utilisateur/09_supervision_parite.md) | Supervision, parité et diagnostic | Cette page agrège des sources différentes : services, runs IHM, workflow, |
| [`guide_utilisateur/10_conformite_corporate_actions.md`](guide_utilisateur/10_conformite_corporate_actions.md) | Conformité, fiscalité et corporate actions | Une opération correcte techniquement peut être fausse économiquement si un |
| [`guide_utilisateur/11_parametres_administration.md`](guide_utilisateur/11_parametres_administration.md) | Paramètres, infrastructure et administration | Le fournisseur de barres influence disponibilité, ajustements et quotas. Un |
| [`guide_utilisateur/12_depannage_faq.md`](guide_utilisateur/12_depannage_faq.md) | Dépannage et questions fréquentes | Dans oracle_atr_market_regime_daily, missing_returns_policy est le mode choisi, |
| [`guide_utilisateur/13_regime_et_comptes.md`](guide_utilisateur/13_regime_et_comptes.md) | Régime marché et comptes broker | La page affiche le mode effectif, un badge, un résumé et la trace de décision. La trace est plus importante que le seul libellé : elle indiq |
| [`guide_utilisateur/14_infra_backups_et_db.md`](guide_utilisateur/14_infra_backups_et_db.md) | Infra, sauvegardes et administration DB | La page regroupe métriques, archives ML, dumps DB et reset ML. Les compteurs peuvent être actifs, no-op ou indisponibles selon dépendances ; |
| [`guide_utilisateur/15_calibrations_et_diagnostic_ml.md`](guide_utilisateur/15_calibrations_et_diagnostic_ml.md) | Calibrations de poids et Diagnostic ML | La page filtre les runs par scope, régime, horizon, fenêtre et statut de promotion live. Le détail expose meilleurs poids, candidats, histor |
| [`guide_utilisateur/16_fondamentaux.md`](guide_utilisateur/16_fondamentaux.md) | Fondamentaux | La page historique concerne principalement les fondamentaux US. Le batch |
| [`guide_utilisateur/17_conformite_fiscalite_sandbox.md`](guide_utilisateur/17_conformite_fiscalite_sandbox.md) | Compliance, fiscalité et sandbox health | La page agrège chaîne HMAC, drill DR, vulnérabilités, couverture, mutation, TLAPS, fuzzing et sandbox. Elle peut relancer certains jobs, exp |
| [`guide_utilisateur/18_glossaire_et_aide.md`](guide_utilisateur/18_glossaire_et_aide.md) | Glossaire et système d’aide | La page Glossaire charge les entrées d’aide enregistrées, permet une recherche tolérante et affiche chaque définition dans un expander. Elle |
| [`guide_utilisateur/19_batchs_et_marches.md`](guide_utilisateur/19_batchs_et_marches.md) | Batchs et marchés — guide opérateur | État du 10 octobre 2026, rapproché de `ihm/pages/batches.py`, |
| [`guide_utilisateur/COUVERTURE_PAGES_IHM.md`](guide_utilisateur/COUVERTURE_PAGES_IHM.md) | Couverture des pages IHM | Cette matrice est dérivée de `ihm/services/navigation.py`. Une page officielle doit avoir une source et au moins un chapitre opérateur. Les |
| [`guide_utilisateur/README.md`](guide_utilisateur/README.md) | Guide utilisateur de l’application | Mise à jour ciblée du **10 octobre 2026** : |

## ML — contrats et recherche US

| Document | Titre | Description |
|---|---|---|
| [`ml/README.md`](ml/README.md) | Références ML | Les références de recherche ci-dessous conservent leurs verdicts et réserves. |
| [`ml/alpha_trade_d10_d1_ratio_analysis.md`](ml/alpha_trade_d10_d1_ratio_analysis.md) | Analyse du ratio `d10_d1_ratio` — Alpha Trade | Cette analyse porte sur le fichier extrait de l'application **Alpha Trade** et vise à étudier le comportement du ratio : |
| [`ml/alpha_trade_quant_professional_methods_roadmap.md`](ml/alpha_trade_quant_professional_methods_roadmap.md) | Roadmap des méthodes quant professionnelles applicables à α-Trade | Ce document rassemble, dans une seule roadmap, les principales méthodes quantitatives professionnelles pertinentes pour l’architecture actue |
| [`ml/audit_autorisations_collectes_us_20261006.md`](ml/audit_autorisations_collectes_us_20261006.md) | US — Audit des autorisations de collecte des batchs | Date de vérification : 6 octobre 2026. Périmètre : catalogue `US_EQ` effectivement présenté par la page Batch, fournisseurs réellement appel |
| [`ml/borrow_lending_data_feasibility.md`](ml/borrow_lending_data_feasibility.md) | Faisabilité des données de prêt de titres | Audit réalisé le 7 septembre 2026. |
| [`ml/borrow_pilot_feasibility_20261001.md`](ml/borrow_pilot_feasibility_20261001.md) | Pilote de faisabilité des données de prêt de titres après Oracle | Le pilote est désormais **prêt à recevoir un extrait**, sans achat ni entraînement prématuré : liste de 50 titres et harnais `work/borrow_pi |
| [`ml/borrow_sample_request_20261001.md`](ml/borrow_sample_request_20261001.md) | Draft request — historical securities-lending sample | Hello, |
| [`ml/cascade_et_fallbacks.md`](ml/cascade_et_fallbacks.md) | Cascade de modèles et politiques de fallback | Une cascade essaie des sources/modèles selon une priorité et conserve la |
| [`ml/closing_quote_microstructure.md`](ml/closing_quote_microstructure.md) | Microstructure de clôture après Oracle TOP20 | Expérience terminée le 7 septembre 2026 sur H3, H5, H10 et H20. |
| [`ml/conditional_oracle_ranker.md`](ml/conditional_oracle_ranker.md) | Ranker conditionnel au TOP20 Oracle Extreme | Ce module est une expérience de recherche. Il n'est relié ni au serving, ni à |
| [`ml/correctif_pipeline_historique_filtre_gpt.md`](ml/correctif_pipeline_historique_filtre_gpt.md) | Correctif Pipeline — filtre GPT et boutons de prédiction historique | Le filtre GPT/recherche Web peut être coché par défaut pour le parcours |
| [`ml/d10_corporate_action_anomaly_audit.md`](ml/d10_corporate_action_anomaly_audit.md) | Audit de l'anomalie D10 — ruptures de continuité WFRD et CHRD | Audit terminé le 7 septembre 2026. Le défaut a ensuite été corrigé dans le |
| [`ml/daily_position_keep_exit.md`](ml/daily_position_keep_exit.md) | E7 — Surveillance quotidienne des positions : KEEP / EXIT | E7 cherche à répondre à une question différente de la direction initiale : |
| [`ml/data_gaps_and_provider_priorities.md`](ml/data_gaps_and_provider_priorities.md) | Données manquantes et priorités fournisseurs pour la recherche ML | Ce document recense les expériences ML qui sont bloquées, suspendues ou restées non concluantes principalement à cause d'un manque de donnée |
| [`ml/data_gaps_and_provider_priorities_source_free.md`](ml/data_gaps_and_provider_priorities_source_free.md) | Forward PIT Collector — sources gratuites vérifiées pour P0 à P4 | Ce document est destiné à être donné directement à une IA / un développeur pour implémentation. |
| [`ml/directional_alpha_attribution_e18a.md`](ml/directional_alpha_attribution_e18a.md) | E18-A — Attribution bêta, secteurs et régimes du momentum résiduel H120 | E18-A conclut **`MARKET_OR_SECTOR_EXPOSURE`**. L’analyse détaillée précise que |
| [`ml/directional_alpha_book_confirmation_e17b.md`](ml/directional_alpha_book_confirmation_e17b.md) | E17-B — Confirmation prospective du momentum résiduel H120 | E17-B ne réanalyse pas 2018–2025. Cette période a servi à découvrir le signal |
| [`ml/directional_alpha_book_e17.md`](ml/directional_alpha_book_e17.md) | E17 — Bibliothèque d’alphas directionnels price-only à H60/H120 | E17 est terminé avec le verdict **`NO_GO` pour une stratégie directionnelle |
| [`ml/directional_alpha_book_robustness_e17c.md`](ml/directional_alpha_book_robustness_e17c.md) | E17-C — Robustesse historique verrouillée du momentum résiduel H120 | E17-C conclut **`NOT_ROBUST`** selon les gates pré-enregistrés. |
| [`ml/directional_complementarity_audit.md`](ml/directional_complementarity_audit.md) | Audit de complementarite des signaux directionnels faibles | Peut-on combiner des scores faibles qui ne sont pas exploitables seuls ? Cet |
| [`ml/entrainement_serving_et_gouvernance.md`](ml/entrainement_serving_et_gouvernance.md) | Entraînement, serving et gouvernance ML | Un artefact exploitable associe modèle, schéma de features, configuration, |
| [`ml/eroya_directional_poc.md`](ml/eroya_directional_poc.md) | POC Eroya — nouvelles informations directionnelles | Ce POC cherche de l'information signée pour départager LONG et SHORT au sein |
| [`ml/experiences_done.md`](ml/experiences_done.md) | Registre des expériences ML réalisées | Repère de lecture du **10 octobre 2026** : ce registre conserve les résultats |
| [`ml/features_et_dataset.md`](ml/features_et_dataset.md) | Features et construction des datasets ML | Cette référence complète features et labels en mettant |
| [`ml/features_et_labels.md`](ml/features_et_labels.md) | Features, contrats et labels ML | Retour : références ML |
| [`ml/first_touch_binary.md`](ml/first_touch_binary.md) | E4-B — Contrôle binaire de première touche | E4-B vérifie si l’échec d’E4 provient de sa formulation à quatre classes. Dans |
| [`ml/first_touch_directional.md`](ml/first_touch_directional.md) | E4 — Direction par première barrière symétrique touchée | E4 est une expérience de recherche autonome. Elle ne modifie ni les modèles |
| [`ml/forward_pit_batch_plan.md`](ml/forward_pit_batch_plan.md) | Plan des batchs Forward PIT — P0 à P4 | État d’implémentation : le socle décrit ici est réalisé par la migration |
| [`ml/forward_pit_batch_plan_manquant.md`](ml/forward_pit_batch_plan_manquant.md) | Sources de données complémentaires pour améliorer la classification D1/D10 | L’objectif de ces différents batchs est d’enrichir le pipeline de données afin d’améliorer la capacité du modèle à distinguer les mouvements |
| [`ml/fundamental_alpha_book_e19b.md`](ml/fundamental_alpha_book_e19b.md) | E19-B — Bibliothèque d’alphas fondamentaux PIT | Ce protocole est figé avant le premier calcul de performance E19-B. Toute |
| [`ml/fundamental_pit_availability_e19a.md`](ml/fundamental_pit_availability_e19a.md) | E19-A — Audit de disponibilité PIT des fondamentaux | E19-A conclut **`PARTIAL_CONTRACT_BLOCKED`**. |
| [`ml/fundamental_pit_contract_e19a2.md`](ml/fundamental_pit_contract_e19a2.md) | E19-A2 — Contrat PIT fondamental | E19-A2 corrige le contrat applicatif identifié par E19-A. Le code, le schéma et |
| [`ml/fundamental_value_confirmation_e19c.md`](ml/fundamental_value_confirmation_e19c.md) | E19-C — Confirmation verrouillée du facteur valeur PIT | Statut final : `COMPLETE_NO_GO`. |
| [`ml/global_ranking/01_concept_et_architecture.md`](ml/global_ranking/01_concept_et_architecture.md) | 1 — Concept et architecture | Le modèle ne cherche pas d’abord à répondre « quel sera le rendement absolu de |
| [`ml/global_ranking/02_univers_donnees_et_features.md`](ml/global_ranking/02_univers_donnees_et_features.md) | 2 — Univers, données et features | `train_global_ranking_wf` reçoit une liste de symboles, résout la dernière date |
| [`ml/global_ranking/03_targets_labels_et_pit.md`](ml/global_ranking/03_targets_labels_et_pit.md) | 3 — Targets, labels et étanchéité temporelle | La fonction `_compute_ranking_targets` est appelée séparément sur le DataFrame |
| [`ml/global_ranking/04_train_walk_forward_et_championnat.md`](ml/global_ranking/04_train_walk_forward_et_championnat.md) | 4 — Entraînement walk-forward et championnat | `generate_walk_forward_splits_by_dates` construit les fenêtres temporelles |
| [`ml/global_ranking/05_artefacts_inference_et_persistance.md`](ml/global_ranking/05_artefacts_inference_et_persistance.md) | 5 — Artefacts, inférence et persistance | L’entraînement écrit un modèle par horizon : |
| [`ml/global_ranking/06_consommation_stacking_cascade.md`](ml/global_ranking/06_consommation_stacking_cascade.md) | 6 — Consommation, stacking, cascade et filtre DIP | Les rangs peuvent : |
| [`ml/global_ranking/07_metriques_diagnostics_et_historique.md`](ml/global_ranking/07_metriques_diagnostics_et_historique.md) | 7 — Métriques, diagnostics et historique | `compute_ic_rank` calcule la corrélation de Spearman entre scores prédits et |
| [`ml/global_ranking/08_configuration_et_runbook.md`](ml/global_ranking/08_configuration_et_runbook.md) | 8 — Configuration et runbook | LightGBM et plusieurs régularisations utilisent encore `BaselineConfig`. |
| [`ml/global_ranking/README.md`](ml/global_ranking/README.md) | Global Ranking — dossier technique complet | Le Global Ranking est le modèle cross-sectionnel multi-symboles de l’application. |
| [`ml/global_ranking_reference.md`](ml/global_ranking_reference.md) | Global Ranking — référence technique | Version exhaustive : dossier Global Ranking. |
| [`ml/guidance_feasibility_audit_20260930.md`](ml/guidance_feasibility_audit_20260930.md) | Guidance : audit de faisabilité du 30 septembre 2026 | Travail autorisé : relire les échecs E21, examiner les données conservées, constituer un petit corpus distinct et décider de la faisabilité |
| [`ml/guidance_historical_smoke_e21.md`](ml/guidance_historical_smoke_e21.md) | E21 — Backfill historique et validation manuelle de guidance | Le correctif des URL du collecteur est appliqué. Le smoke historique a récupéré |
| [`ml/guidance_oracle_overlap_and_calendar_20260930.md`](ml/guidance_oracle_overlap_and_calendar_20260930.md) | Guidance après Oracle Extreme — recouvrement et dates officielles (30 septembre 2026) | Statut : **INCONCLUSIVE / ZERO_PIT_ELIGIBLE**. Recherche descriptive sur le batch OOF historique `model-factory-20260909051302-323684`. Aucu |
| [`ml/guidance_pit_availability_e21a.md`](ml/guidance_pit_availability_e21a.md) | E21-A — Disponibilite PIT des revisions chiffrees de guidance | **Archive d'une piste fermée.** E21 a été clôturée le 15 septembre 2026 au |
| [`ml/guidance_pit_followup_20260930.md`](ml/guidance_pit_followup_20260930.md) | Guidance — vérification SEC et instant de décision, 30 septembre 2026 | Statut : **BLOCKED_FOR_ML_EVIDENCE_IMPROVED**. Suite bornée aux cinq candidats du pilote, sans nouvelles sociétés, sans rendements et sans e |
| [`ml/guidance_reference_pilot_20260930.md`](ml/guidance_reference_pilot_20260930.md) | Pilote de référence guidance — 30 septembre 2026 | Statut : **REVIEW_READY_PARTIAL_EVIDENCE_NOT_ML_READY**. Propositions d'annotation par l'assistant, non vérité terrain indépendante. Aucun m |
| [`ml/guidance_role_validation_e21b.md`](ml/guidance_role_validation_e21b.md) | E21-B2 — Rôles des fourchettes : protocole de validation | `statement_role` classe chaque fourchette dollar en NEW_FORECAST, |
| [`ml/guidance_structured_e21b.md`](ml/guidance_structured_e21b.md) | E21-B — Extraction structurée et comparabilité de la guidance | **Statut final — CLOSED / SUSPENDED_DATA_NOT_READY (15 septembre 2026).** |
| [`ml/guidance_table_extraction_e21b.md`](ml/guidance_table_extraction_e21b.md) | E21-B3 — Lecture des tableaux et de leurs en-têtes | `service/forward_pit/guidance_tables.py` lit les tableaux HTML et conserve la |
| [`ml/guidance_table_validation_protocol_e21b4.md`](ml/guidance_table_validation_protocol_e21b4.md) | E21-B4 — Validation indépendante du lecteur de tableaux | **Piste fermée — CLOSED / SUSPENDED_DATA_NOT_READY, 15 septembre 2026.** |
| [`ml/intraday_market_context_pilot.md`](ml/intraday_market_context_pilot.md) | Contexte intraday de marché après Oracle TOP20 | Cette piste teste si la trajectoire intraday commune du marché explique le sens |
| [`ml/intraday_session_path_pilot.md`](ml/intraday_session_path_pilot.md) | Trajectoire intraday 5 minutes de la séance complète | Cette expérience teste une information distincte des snapshots et des cinq |
| [`ml/market_cap_sec_edgar.md`](ml/market_cap_sec_edgar.md) | Capitalisation PIT — SEC prioritaire, Yahoo/Finnhub en fallback | Cette architecture empêche une capitalisation actuelle d'être recopiée dans le |
| [`ml/meta_oracle.md`](ml/meta_oracle.md) | Meta-Oracle — filtre des faux positifs Oracle | Cette campagne est research-only. Batch recommandé : `model-factory-20260909051302-323684`. Le shadow 2025-07-14 → 2026-06-30 reste un holdo |
| [`ml/meta_oracle_execution.md`](ml/meta_oracle_execution.md) | Meta Oracle : implementation et execution | Le module `modelFactory.meta_oracle` implemente le noyau experimental A/B du |
| [`ml/modeles_per_symbol_et_per_sector.md`](ml/modeles_per_symbol_et_per_sector.md) | Modèles per-symbol, per-sector et modèle global | Documentation exhaustive : |
| [`ml/multi_horizon_oracle_rolling_confirmation.md`](ml/multi_horizon_oracle_rolling_confirmation.md) | Multi-Horizon Oracle et confirmation rolling | `RUN TERMINÉ — WEAK_SIGNAL, PHASE 2 NON OUVERTE` |
| [`ml/new_entry_data_guard.md`](ml/new_entry_data_guard.md) | Contrôle strict des données des nouvelles entrées US | Le mode partiel de l'étude Oracle/ATR n'autorise jamais une entrée sur données |
| [`ml/nyse_auction_history_poc.md`](ml/nyse_auction_history_poc.md) | POC NYSE Auction History — déséquilibres post-auction | Le batch de production `auction_imbalance_sync` reste désactivé avec le statut `BLOCKED_NO_FREE_OFFICIAL_FEED`. |
| [`ml/oof_consensus_audit.md`](ml/oof_consensus_audit.md) | Audit du consensus des modèles directionnels OOF | Cette expérience vérifie si plusieurs modèles directionnels déjà entraînés |
| [`ml/options_acquisition_cost_audit.md`](ml/options_acquisition_cost_audit.md) | E8-A2 — Source et coût d’acquisition de l’historique options | E8-A2 est terminé en `GO_ACQUISITION_PILOT`, mais E8-B reste bloqué tant que |
| [`ml/options_delayed_alpaca_occ.md`](ml/options_delayed_alpaca_occ.md) | Options retardées Alpaca et ajustements OCC | Deux collectes prospectives sont actives pour la recherche : |
| [`ml/options_directional_poc.md`](ml/options_directional_poc.md) | E7 — Options directionnelles après Oracle | Campagne terminée le 6 septembre 2026 : `NO_GO` pour la surface 45 DTE testée. |
| [`ml/options_pit_history_audit.md`](ml/options_pit_history_audit.md) | E8-A — Audit de l'historique options PIT | E8-A est terminé en `BLOCKED_NO_DENSE_PIT_HISTORY`. L'artefact canonique est : |
| [`ml/oracle/01_concept_et_architecture.md`](ml/oracle/01_concept_et_architecture.md) | Oracle Extreme — concept, sémantique et architecture | Retour : dossier Oracle |
| [`ml/oracle/02_labels_univers_et_tables.md`](ml/oracle/02_labels_univers_et_tables.md) | Oracle Extreme — labels, univers, calendrier et tables | Retour : dossier Oracle |
| [`ml/oracle/03_dataset_features_et_leakage.md`](ml/oracle/03_dataset_features_et_leakage.md) | Oracle Extreme — dataset, features, ablations et anti-fuite | Retour : dossier Oracle |
| [`ml/oracle/04_train_walk_forward_et_calibration.md`](ml/oracle/04_train_walk_forward_et_calibration.md) | Oracle Extreme — entraînement, walk-forward, calibration et métriques | Retour : dossier Oracle |
| [`ml/oracle/05_inference_persistance_et_gate.md`](ml/oracle/05_inference_persistance_et_gate.md) | Oracle Extreme — inférence, persistance et gate quotidien | Retour : dossier Oracle |
| [`ml/oracle/06_diagnostics_et_historique.md`](ml/oracle/06_diagnostics_et_historique.md) | Oracle Extreme — diagnostics, expériences et statut actuel | Retour : dossier Oracle |
| [`ml/oracle/README.md`](ml/oracle/README.md) | Oracle Extreme — dossier technique complet | Ce dossier décrit la couche Oracle telle qu’elle existe dans le code actuel. Il remplace la fonction documentaire de l’ancien `doc/ml_oracle |
| [`ml/oracle_ablation_corrected_comparison.md`](ml/oracle_ablation_corrected_comparison.md) | Comparaison corrigée des ablations Oracle Extreme | Cette étude réévalue rétrospectivement les 14 ablations Oracle entraînées le |
| [`ml/oracle_amplitude_audit.md`](ml/oracle_amplitude_audit.md) | E6 — Audit direction-neutral de l’amplitude Oracle | Les expériences E2 à E5 n’ont pas trouvé de signal directionnel OOF suffisamment |
| [`ml/oracle_atr_amplitude_gate.md`](ml/oracle_atr_amplitude_gate.md) | Filtre d’amplitude Oracle Extreme × ATR — backtest et live | Étude associée : table quotidienne macro/régime et D1/D10, |
| [`ml/oracle_atr_market_regime_daily.md`](ml/oracle_atr_market_regime_daily.md) | Étude quotidienne Oracle × ATR et régime de marché | `alpha_trade.oracle_atr_market_regime_daily` rapproche les indicateurs macro du |
| [`ml/oracle_d10_trajectory_e23.md`](ml/oracle_d10_trajectory_e23.md) | E23 — D10 one-vs-rest après Oracle avec trajectoires J−10 à J | et toutes les trajectoires testées. Ce harnais reste exclusivement destiné à la |
| [`ml/oracle_daily_regime_direction.md`](ml/oracle_daily_regime_direction.md) | E5 — Direction quotidienne du régime Oracle | E5 est une expérience de recherche, non branchée au serving ou au backtest. Elle |
| [`ml/oracle_extreme_reference.md`](ml/oracle_extreme_reference.md) | Oracle Extreme O0 — référence technique | Contrats détaillés : dossier Oracle Extreme complet. |
| [`ml/oracle_global_ranking_cross_e11.md`](ml/oracle_global_ranking_cross_e11.md) | E11 — Croisement Oracle H20 × Global Ranking H20 | `FAIT_NO_GO` |
| [`ml/oracle_h20_corrected_top10_audit.md`](ml/oracle_h20_corrected_top10_audit.md) | Oracle H20 corrigé — audit des dix premiers titres | Audit terminé le 7 octobre 2026, sans nouvel entraînement ni écriture SQL. |
| [`ml/oracle_h20_numeric_effect.md`](ml/oracle_h20_numeric_effect.md) | Oracle H20 — mesure appariée de l'effet des corrections numériques | GO utilisateur du 7 octobre 2026. Audit numérique complet, **24 entraînements |
| [`ml/oracle_lifecycle_structural_audit_e15.md`](ml/oracle_lifecycle_structural_audit_e15.md) | E15 — Audit structurel du lifecycle Oracle H20 | `FAIT_NO_GO_OR_BLOCKED` — aucun contrat n'est promu. L'audit isole clairement |
| [`ml/oracle_llm_directional_filter.md`](ml/oracle_llm_directional_filter.md) | Filtre directionnel Oracle → GPT + Web → risque → PAPER | Implémentation du 8 octobre 2026. Marché US exclusivement. **Expérience prospective, |
| [`ml/oracle_monetization_bridge_e12.md`](ml/oracle_monetization_bridge_e12.md) | E12 — Pont de monétisation Oracle H20 | `FAIT_NO_GO_OR_BLOCKED` — expérience de recherche uniquement. Aucun artefact de |
| [`ml/oracle_numeric_feature_corrections.md`](ml/oracle_numeric_feature_corrections.md) | Correction des facteurs et ratios EXPERT — 7 octobre 2026 | À la suite de l'audit H20, l'utilisateur |
| [`ml/oracle_opening_price_confirmation_e20b.md`](ml/oracle_opening_price_confirmation_e20b.md) | E20-B — Confirmation Oracle strictement price-only | E20-B cherche à savoir si la trajectoire des prix juste après l'ouverture peut |
| [`ml/oracle_opening_price_economic_replay_e20d.md`](ml/oracle_opening_price_economic_replay_e20d.md) | E20-D — Replay économique de la confirmation price-only | E20-D vérifie si le signal directionnel statistique d’E20-B reste exploitable |
| [`ml/oracle_opening_volume_ablation_e20c.md`](ml/oracle_opening_volume_ablation_e20c.md) | E20-C — Ablation incrémentale du volume d’ouverture | E20-C est terminé avec le verdict pré-enregistré `NO_GO_INCREMENTAL_VOLUME`. |
| [`ml/oracle_opening_window_alpaca.md`](ml/oracle_opening_window_alpaca.md) | Oracle Opening Window — collecte Alpaca SIP PIT | `oracle_opening_window_sync` construit prospectivement un historique minute du |
| [`ml/oracle_opening_window_availability_e20a.md`](ml/oracle_opening_window_availability_e20a.md) | E20-A — Disponibilité PIT de la fenêtre d’ouverture après Oracle | E20-A est terminé en `BLOCKED_NO_OPENING_WINDOW_DATA`. Ce verdict ne rejette |
| [`ml/oracle_options_feasibility.md`](ml/oracle_options_feasibility.md) | E6-B0 — Faisabilité des options après Oracle | E6-A a démontré une forte concentration OOF de l’amplitude dans le TOP20 Oracle. |
| [`ml/oracle_post_signal_confirmation.md`](ml/oracle_post_signal_confirmation.md) | E9 — Confirmation directionnelle après le signal Oracle | E9-A est `NO_GO`. E9-B (lifecycle canonique) n'est pas ouvert. Le serving, le backtest applicatif et le live restent inchangés. |
| [`ml/oracle_pre_entry_utility_e14.md`](ml/oracle_pre_entry_utility_e14.md) | E14 — Cible économique pré-entrée après Oracle | `FAIT_NO_GO_OR_BLOCKED` — les modèles détectent une faible information |
| [`ml/oracle_pre_entry_veto_e13.md`](ml/oracle_pre_entry_veto_e13.md) | E13 — Veto pré-entrée après Oracle | `FAIT_NO_GO_OR_BLOCKED` — le score de risque est prédictif du type de sortie, |
| [`ml/oracle_pullback_long.md`](ml/oracle_pullback_long.md) | E10 — Pullback LONG après Oracle H20 | E10 est terminé en `NO_GO`. Le filtre « Oracle TOP20, baisse à J+1, achat |
| [`ml/oracle_relative_portfolio.md`](ml/oracle_relative_portfolio.md) | Portefeuille relatif dans le pool Oracle TOP20 | Cette expérience est isolée du serving, de la cascade ML et du backtest de |
| [`ml/oracle_revelation_jn_vs_cost_of_waiting.md`](ml/oracle_revelation_jn_vs_cost_of_waiting.md) | Oracle TOP20 H20 — révélation D1/D10 à J+N et coût économique de l'attente | Date : 17 septembre 2026. Statut : **diagnostic descriptif terminé, aucune politique promue**. |
| [`ml/oracle_split_corrected_oracle14_p0g_replay_20261001.md`](ml/oracle_split_corrected_oracle14_p0g_replay_20261001.md) | Oracle O0 réentraîné après correction des splits — 14 folds OOF, puis P0g | Le réentraînement hors base de l'Oracle d'amplitude O0 est terminé sur les **14 folds OOF gelés** du batch `model-factory-20260909051302-323 |
| [`ml/oracle_split_corrected_p0g_replay_20260930.md`](ml/oracle_split_corrected_p0g_replay_20260930.md) | Splits Oracle : prix et labels reconstruits, replay P0g — 30 septembre 2026 | Statut : **replay P0g à gate Oracle OOF figé terminé ; NO_GO_DIRECTION inchangé**. |
| [`ml/oracle_split_label_audit_20260930.md`](ml/oracle_split_label_audit_20260930.md) | Audit des splits et des cibles D1/D10 Oracle — 30 septembre 2026 | Statut initial : **quarantaine de recherche produite**. Un |
| [`ml/oracle_top10_annual_2020_2026.md`](ml/oracle_top10_annual_2020_2026.md) | Oracle H20 corrigé — backtests annuels TOP10, 2020–2026 | Expérience lancée le 7 octobre 2026 à la demande de l'utilisateur : mesurer le |
| [`ml/oracle_tradable_pit_reconstruction_e16.md`](ml/oracle_tradable_pit_reconstruction_e16.md) | E16 — Reconstruction PIT de l’univers tradable et réplication E12/E15 | 582 698/582 700 événements (99,9997 %) sans données futures. Malgré cette |
| [`ml/oracle_tradable_top20_backtest_live.md`](ml/oracle_tradable_top20_backtest_live.md) | Oracle TOP20 sur univers tradable — backtest et live | Ce document décrit le contrat d’exécution de la cascade directionnelle dans laquelle : |
| [`ml/oracle_trajectory_e22.md`](ml/oracle_trajectory_e22.md) | E22 — Trajectoire pré-signal J−5 à J pour Oracle Extreme | isolé. Il ne modifie ni les modèles Oracle servis, ni les prédictions SQL, ni |
| [`ml/oracle_universe_p0_audit.md`](ml/oracle_universe_p0_audit.md) | P0 — Audit de l’univers Oracle de 400 symboles | Cet audit vérifie si les labels D1/D10 et `oracle_extreme10` du batch |
| [`ml/oracle_universe_p0b_dynamic.md`](ml/oracle_universe_p0b_dynamic.md) | P0b — Reconstruction dynamique bar-only de l'univers Oracle | P0b mesure l'effet d'un univers quotidien construit sans rétropager les |
| [`ml/oracle_universe_p0c_targets.md`](ml/oracle_universe_p0c_targets.md) | P0c — Audit des cibles Oracle corrigées de la volatilité | P0b a construit 3 926 243 observations H20 avec un univers quotidien bar-only |
| [`ml/oracle_universe_p0d_balanced400.md`](ml/oracle_universe_p0d_balanced400.md) | P0d — Univers Oracle équilibré de 400 symboles | P0d produit un nouvel échantillon de recherche de 400 symboles à partir de |
| [`ml/oracle_universe_p0e_comparison.md`](ml/oracle_universe_p0e_comparison.md) | P0e — Comparaison OOF ancien Oracle 400 vs Balanced 400 | Le batch `model-factory-20260908183941-7826b4`, entraîné sur le nouvel univers |
| [`ml/oracle_universe_p0f_dynamic_training.md`](ml/oracle_universe_p0f_dynamic_training.md) | P0f — Entraînement Oracle sur univers quotidien PIT dynamique | P0f intègre le contrat P0b dans le vrai pipeline d'entraînement Oracle. Le but |
| [`ml/oracle_universe_p0g_directional_impact.md`](ml/oracle_universe_p0g_directional_impact.md) | P0g — Impact directionnel du nouvel univers Oracle dynamique | P0f a montré que l'univers quotidien PIT dynamique améliore nettement la |
| [`ml/oracle_universe_p0h_shadow_serving.md`](ml/oracle_universe_p0h_shadow_serving.md) | P0h — Serving shadow de l'Oracle à univers PIT dynamique | P0h est implémenté en `SHADOW_ONLY`. Il permet de produire des scores avec un |
| [`ml/oracle_universe_p0i_shadow_evaluation.md`](ml/oracle_universe_p0i_shadow_evaluation.md) | P0i — Évaluation holdout de l'Oracle dynamique shadow | P0i est **GO pour la détection d'amplitude en shadow**, y compris sur 2026H1. |
| [`ml/oracle_universe_p0j_daily_canary.md`](ml/oracle_universe_p0j_daily_canary.md) | P0j — Canary quotidien de l'Oracle dynamique | P0j est implémenté comme **canary shadow uniquement** pour le batch |
| [`ml/oracle_universe_p0k_directional_revalidation.md`](ml/oracle_universe_p0k_directional_revalidation.md) | P0k — Revalidation directionnelle ciblée sur l'univers Oracle dynamique | Les expériences directionnelles historiques ont majoritairement utilisé un |
| [`ml/oracle_universe_selection_playbook.md`](ml/oracle_universe_selection_playbook.md) | Guide de renouvellement des univers ML et Oracle | Ce document est le contrat à donner à l'IA lors du renouvellement trimestriel ou |
| [`ml/orchestration_train_predict.md`](ml/orchestration_train_predict.md) | Orchestration ML : train, predict et artefacts | Retour : références ML |
| [`ml/ordre_execution_et_dependances.md`](ml/ordre_execution_et_dependances.md) | Ordre d’exécution ML et dépendances | Le pipeline quotidien peut regrouper ou optionnaliser certaines étapes, mais ne |
| [`ml/panel_screener_dense.md`](ml/panel_screener_dense.md) | Panel screener PIT dense sur la population Oracle | Le screener de production persiste principalement les symboles qui ont déjà |
| [`ml/path_aware_economic_utility.md`](ml/path_aware_economic_utility.md) | E3-A2 — Utilité économique path-aware après Oracle Extreme | E3-A2 est une expérience strictement `research_only`. Elle ne modifie ni le |
| [`ml/path_risk_direction.md`](ml/path_risk_direction.md) | E3-D — Direction par asymétrie du tail-risk | E3-D teste si les deux détecteurs de pertes extrêmes E3-A2 permettent de |
| [`ml/path_risk_veto.md`](ml/path_risk_veto.md) | E3-R — Veto de risque path-aware après Oracle Extreme | E3-R évalue si les classifieurs de pertes extrêmes issus d'E3-A2 peuvent être |
| [`ml/per_sector/01_architecture_univers_pooling.md`](ml/per_sector/01_architecture_univers_pooling.md) | 1 — Architecture, univers et pooling | `run_per_sector_batch` associe les symboles aux secteurs depuis les données |
| [`ml/per_sector/02_features_et_targets.md`](ml/per_sector/02_features_et_targets.md) | 2 — Features et targets sectorielles | Le modèle reprend les familles activées dans `DataConfig` : techniques, |
| [`ml/per_sector/03_train_walk_forward_champion.md`](ml/per_sector/03_train_walk_forward_champion.md) | 3 — Entraînement, walk-forward et champion sectoriel | LightGBM choisit régresseur ou classifieur binaire/multiclasse. CatBoost choisit |
| [`ml/per_sector/04_artefacts_serving_fallback.md`](ml/per_sector/04_artefacts_serving_fallback.md) | 4 — Artefacts, serving et fallback secteur | Le slug met le secteur en minuscules et remplace espaces et `/` par `_`. Le |
| [`ml/per_sector/05_configuration_diagnostics_runbook.md`](ml/per_sector/05_configuration_diagnostics_runbook.md) | 5 — Configuration, diagnostics et runbook per-sector | `training_mode=per_sector`, `sector_use_symbol_feature`, flags de features, |
| [`ml/per_sector/README.md`](ml/per_sector/README.md) | Modèle per-sector — dossier technique complet | Le modèle per-sector mutualise les observations des symboles d’un même secteur. |
| [`ml/per_symbol/01_architecture.md`](ml/per_symbol/01_architecture.md) | 1 — Architecture et responsabilités per-symbol | `train_symbol` crée un `run_id` unique, enregistre le run si la base est |
| [`ml/per_symbol/02_dataset_features_targets.md`](ml/per_symbol/02_dataset_features_targets.md) | 2 — Dataset, features et targets per-symbol | Barres du symbole, benchmark, sentiment, univers, selector/screener, features |
| [`ml/per_symbol/03_train_walk_forward_champions.md`](ml/per_symbol/03_train_walk_forward_champions.md) | 3 — Entraînement, walk-forward et champions | Le réseau utilise hidden size, couches, dropout, learning rate et weight decay |
| [`ml/per_symbol/04_artefacts_serving_fallbacks.md`](ml/per_symbol/04_artefacts_serving_fallbacks.md) | 4 — Artefacts, serving et fallbacks | Le dossier du symbole contient checkpoint LSTM, scaler, calibrateur éventuel, |
| [`ml/per_symbol/05_configuration_diagnostics_runbook.md`](ml/per_symbol/05_configuration_diagnostics_runbook.md) | 5 — Configuration, diagnostics et runbook per-symbol | `sequence_length`, horizons, historique minimal, feature set/whitelist, modes et |
| [`ml/per_symbol/06_selection_candidats_directionnels.md`](ml/per_symbol/06_selection_candidats_directionnels.md) | 6 — Sélection des bons candidats per-symbol par direction | La page **Diagnostic ML** permet de construire, pour un batch ternaire contenant |
| [`ml/per_symbol/07_bundle_oracle_long_short.md`](ml/per_symbol/07_bundle_oracle_long_short.md) | Bundle Oracle Extreme + Per-Symbol LONG/SHORT | Ce mode sépare explicitement amplitude et direction dans une seule campagne ML. Chacune des trois branches possède un profil de features ind |
| [`ml/per_symbol/README.md`](ml/per_symbol/README.md) | Modèle per-symbol — dossier technique complet | Le modèle per-symbol entraîne une famille de challengers pour chaque ticker à |
| [`ml/pistes_mathematiques_D1_D10.md`](ml/pistes_mathematiques_D1_D10.md) | 2. La piste que je trouve la plus prometteuse : les relations lead-lag entre actions | C’est probablement la plus grosse famille mathématique que je ne vois pas réellement testée dans ton registre. |
| [`ml/pmath0_nonparametric_separability.md`](ml/pmath0_nonparametric_separability.md) | P-MATH-0 — Audit non paramétrique de séparabilité D1/D10 | aucun modèle de serving et aucune cascade n'ont été modifiés. |
| [`ml/pmath1_cross_asset_lead_lag.md`](ml/pmath1_cross_asset_lead_lag.md) | P-MATH-1 — relations cross-asset lead-lag sur résidus | P-MATH-0 a montré que les 84 variables d'état connues ne séparent pas de façon |
| [`ml/pmath2_low_depth_path_signatures.md`](ml/pmath2_low_depth_path_signatures.md) | P-MATH-2 — signatures de trajectoire de faible profondeur | P-MATH-0 n'a pas trouvé de séparation stable dans l'état ponctuel J et |
| [`ml/pmath3_conditional_quantiles.md`](ml/pmath3_conditional_quantiles.md) | P‑MATH‑3 — distribution conditionnelle du rendement H20 | P‑MATH‑0, 1 et 2 n'ont pas trouvé de séparation D1/D10 stable avec les |
| [`ml/qualite_couverture_et_fallbacks.md`](ml/qualite_couverture_et_fallbacks.md) | Qualité, couverture et fallbacks ML | La couverture mesure la part de la population/date pour laquelle le système peut |
| [`ml/recalibration_et_promotion.md`](ml/recalibration_et_promotion.md) | Recalibration, sélection et promotion des modèles | 1. réentraîner produit de nouveaux artefacts ; |
| [`ml/screener_post_oracle.md`](ml/screener_post_oracle.md) | Filtre screener PIT après Oracle Extreme | Cette fonctionnalité est un **harnais de recherche uniquement**. Elle ne modifie |
| [`ml/shared_directional_oracle_events.md`](ml/shared_directional_oracle_events.md) | Modèle directionnel mutualisé sur les événements Oracle | Ce module est une **expérience Walk-Forward non servable**. Il ne remplace pas |
| [`ml/signed_trade_flow_pilot.md`](ml/signed_trade_flow_pilot.md) | Flux signé trades/NBBO après Oracle TOP20 | Cette expérience vérifie une famille d'information réellement nouvelle par |
| [`ml/tail_direction_classifier_V2.md`](ml/tail_direction_classifier_V2.md) | EXPÉRIENCE V2 — Temporal D1/D10 Tail Direction Classifier | Cette campagne remplace complètement l’ancienne approche centrée principalement sur les features observées au seul jour `J`. |
| [`ml/temporal_d1d10_v2.md`](ml/temporal_d1d10_v2.md) | Temporal D1/D10 V2 | Campagne Dataset A terminée le 7 septembre 2026 : **`NO_GO_DATASET_A`**. |
| [`ml/thetadata_options_smoke.md`](ml/thetadata_options_smoke.md) | E8-A3 — Connecteur ThetaData et smoke d’éligibilité | Le connecteur et le smoke sont implémentés. La piste est désormais classée |
| [`ml/tick_price_liquidity_audit.md`](ml/tick_price_liquidity_audit.md) | Trajectoire tick de prix, spread et liquidité après Oracle | Cette expérience réutilise les ticks du run |
| [`ml/us_2019_2025_combinaison_regimes.md`](ml/us_2019_2025_combinaison_regimes.md) | US 2019–2025 — Confirmation descriptive M+V et audit des mois défavorables | Demande : tester la combinaison momentum120 + volatilité60/ATR20 entre |
| [`ml/us_2019_2026_audit_regimes_combinaison.md`](ml/us_2019_2026_audit_regimes_combinaison.md) | US — Audit des régimes de la combinaison D10, 2019–2026 T1 | 2026 sont désormais complets sur les dates testées. Voir le |
| [`ml/us_2025_atr_oracle_news_sentiment.md`](ml/us_2025_atr_oracle_news_sentiment.md) | US 2025 — Croisement ATR / Oracle H20 et news à sentiment fort | Ces expériences sont **terminées comme analyses descriptives**, sans GO |
| [`ml/us_2025_combinaison_features_d10.md`](ml/us_2025_combinaison_features_d10.md) | US 2025 — Combinaison de features candidates D10 | Expérience exploratoire uniquement : les familles ont été choisies à partir |
| [`ml/us_2025_features_separation_d1_d10.md`](ml/us_2025_features_separation_d1_d10.md) | US 2025 — Audit univarié des features entre vrais D1 et D10 | forte et fiable n'est démontrée.** Deux familles méritent une confirmation |
| [`ml/us_2026_regime_macro_actualise.md`](ml/us_2026_regime_macro_actualise.md) | US — Actualisation du régime après alimentation macro 2026 | 4 octobre 2026. Statut : terminé, lecture SQL seule. Cette actualisation |
| [`ml/us_bundle_probabilites_constantes_diagnostic.md`](ml/us_bundle_probabilites_constantes_diagnostic.md) | PENN, ROKU et GH — Diagnostic des probabilités LONG presque constantes | Le comportement est confirmé dans trois branches LONG CatBoost avec calibration |
| [`ml/us_bundle_repetition_fiabilite_long_audit.md`](ml/us_bundle_repetition_fiabilite_long_audit.md) | US — Répétition des signaux et fiabilité opérationnelle de P(LONG) | Les deux audits sont terminés en diagnostic. Aucun entraînement, accès SQL, |
| [`ml/us_concentrated_contract_qualification.md`](ml/us_concentrated_contract_qualification.md) | Sélections concentrées US — MP/BAND et contrat du moteur | Audit et correction du 6 octobre 2026. Suite du protocole de préparation. |
| [`ml/us_concentrated_exit_variants.md`](ml/us_concentrated_exit_variants.md) | Expérience LONG — sans TP, sortie vingt séances après l'entrée | Convention demandée par l'utilisateur : entrée à J+1, puis sortie à la clôture |
| [`ml/us_concentrated_historical_tapes.md`](ml/us_concentrated_historical_tapes.md) | Tapes historiques des sélections Oracle concentrées | L'assembleur est implémenté ; le pilote du 2 janvier 2025 est terminé. |
| [`ml/us_concentrated_live_parity_audit.md`](ml/us_concentrated_live_parity_audit.md) | Backtest concentré US — audit préalable de parité avec le portefeuille live | Date : 7 octobre 2026. Demande : un véritable backtest avec la logique du |
| [`ml/us_concentrated_portfolio_replay.md`](ml/us_concentrated_portfolio_replay.md) | Portefeuille stateful des variantes de sorties US | Qualification du 7 octobre 2026. **Adaptateur de recherche, pas activation live |
| [`ml/us_concentrated_replay_protocol.md`](ml/us_concentrated_replay_protocol.md) | Sélections Oracle concentrées — protocole exploratoire et préparation | Pré-enregistrement du 6 octobre 2026. **Cette étape prépare les candidats |
| [`ml/us_confirmation_secteur_breadth_protocole.md`](ml/us_confirmation_secteur_breadth_protocole.md) | US — Confirmation figée force relative / breadth et régime LONG | Protocole enregistré le 4 octobre 2026 avant calcul des résultats de ces |
| [`ml/us_confirmation_secteur_breadth_resultats.md`](ml/us_confirmation_secteur_breadth_resultats.md) | US — Résultats régime LONG, force relative et breadth | Le constat initial d'absence macro ci-dessous décrit l'état du premier run. |
| [`ml/us_d10_d1_ratio_audit_pit_lineage.md`](ml/us_d10_d1_ratio_audit_pit_lineage.md) | US — Audit PIT et lineage de l'expérience ratio D10/D1 | Date : 4 octobre 2026. Audit des trois étapes autorisées : scores Oracle, |
| [`ml/us_d10_d1_ratio_validation_chronologique.md`](ml/us_d10_d1_ratio_validation_chronologique.md) | US — Validation chronologique du contexte D10/D1 Oracle × ATR | Suite autorisée exécutée : audit PIT et lineage. |
| [`ml/us_degradation_commune_2026q1_audit.md`](ml/us_degradation_commune_2026q1_audit.md) | US — Audit de la dégradation du bundle ancien, janvier–mars 2026 | Le diagnostic directionnel et la comparaison de six contextes figés sont calculés. |
| [`ml/us_extreme50_capture.md`](ml/us_extreme50_capture.md) | US — Audit figé de capture des mouvements H20 ≥50 % | Objectif : vérifier si les grandes variations déjà visibles dans les listes |
| [`ml/us_extreme50_price_qualification.md`](ml/us_extreme50_price_qualification.md) | Qualification des très grands mouvements US avant rejeu économique | Date de revue : 6 octobre 2026. **Qualification partielle terminée ; aucun |
| [`ml/us_h20_atr_vs_oracle.md`](ml/us_h20_atr_vs_oracle.md) | Pilote US H20 — ATR seul contre Oracle Extreme | But : mesurer la valeur ajoutée de l'Oracle sur une règle simple de volatilité. Ce n'est ni un test directionnel D1/D10, ni un backtest écon |
| [`ml/us_oracle_atr_desaccord_protocole.md`](ml/us_oracle_atr_desaccord_protocole.md) | US — Audit figé du désaccord Oracle × ATR | 4 octobre 2026, protocole avant résultats. Aucun entraînement, SQL write, |
| [`ml/us_oracle_atr_desaccord_resultats.md`](ml/us_oracle_atr_desaccord_resultats.md) | US — Désaccord Oracle × ATR : résultats | 4 octobre 2026. Protocole figé. |
| [`ml/us_oracle_feature_outliers_audit.md`](ml/us_oracle_feature_outliers_audit.md) | Oracle US — localisation des features extrêmes et audit des prix | Audit du 7 octobre 2026, suite de l'audit de reproductibilité. |
| [`ml/us_oracle_h20_dataset_quality_audit.md`](ml/us_oracle_h20_dataset_quality_audit.md) | US — Audit qualité du contrat Oracle H20 après exclusions | Audit lancé et **terminé le 7 octobre 2026**. Il ne s'agit ni d'un nouvel |
| [`ml/us_oracle_post_exclusion_price_audit.md`](ml/us_oracle_post_exclusion_price_audit.md) | Oracle US — contrôle après retrait de KNTK et AMTB | Le retrait de KNTK et AMTB élimine les trois maxima initialement observés, |
| [`ml/us_oracle_remaining_discontinuities_audit.md`](ml/us_oracle_remaining_discontinuities_audit.md) | US — Audit des discontinuités restantes après cinq exclusions | Date : 7 octobre 2026. Statut : contrôle terminé, réserves historiques ouvertes. |
| [`ml/us_oracle_reproducibility_audit.md`](ml/us_oracle_reproducibility_audit.md) | Oracle US — audit de reproductibilité et chronologie du batch e98332 | Batch : `model-factory-20261003082853-e98332`, Oracle amplitude H20. |
| [`ml/us_oracle_top10_fixed_sl7.md`](ml/us_oracle_top10_fixed_sl7.md) | TOP10 Oracle sans filtre directionnel — stop initial fixe à 7 % | Demande : refaire le replay des dix premiers titres prédits chaque jour par |
| [`ml/us_oracle_top10_perfect_direction.md`](ml/us_oracle_top10_perfect_direction.md) | Oracle TOP10 — Simulation avec direction positive connue a posteriori | Expérience demandée le 7 octobre 2026 : mesurer ce que donnerait le portefeuille |
| [`ml/us_realized_top10_fixed_sl7.md`](ml/us_realized_top10_fixed_sl7.md) | Dix plus grands mouvements H20 réellement observés — SL initial 7 % | Simulation contrefactuelle : dix titres par date classés par valeur absolue du |
| [`ml/us_realized_top10_positive_fixed_sl7.md`](ml/us_realized_top10_positive_fixed_sl7.md) | TOP10 réel H20 : ne conserver que les futurs positifs, SL initial 7 % | Suite du TOP10 réel des deux signes. |
| [`ml/us_top10_2024_context_audit.md`](ml/us_top10_2024_context_audit.md) | Pourquoi le TOP10 Oracle LONG se dégrade en 2024 | Audit réalisé le 7 octobre 2026, sans entraînement, accès SQL, veto supplémentaire |
| [`ml/us_top10_early_weakness_2023_2024.md`](ml/us_top10_early_weakness_2023_2024.md) | Audit de faiblesse précoce — TOP10 Oracle prédit, 2023–2024 | Expérience autorisée le 7 octobre 2026, lancée dans |
| [`ml/us_top10_equal_sizing_2023_2024.md`](ml/us_top10_equal_sizing_2023_2024.md) | TOP10 prédit — allocation égalisée, 2023–2024 | Suite autorisée le 7 octobre 2026. Garder la sélection et les sorties, modifier |
| [`ml/us_top10_relative_sector_audit.md`](ml/us_top10_relative_sector_audit.md) | TOP10 Oracle — provenance et faiblesse relative pré-entrée | Suite de l'audit de contexte 2024. |
| [`ml/validation_et_gouvernance.md`](ml/validation_et_gouvernance.md) | Walk-forward, calibration et gouvernance ML | Retour : références ML |
| [`ml/yahoo_analyst_pit.md`](ml/yahoo_analyst_pit.md) | Snapshots analystes Yahoo Finance — contrat PIT de recherche | Le batch `analyst_snapshot_collection` construit à partir de sa date d'activation |

## Marché chinois — CN

| Document | Titre | Description |
|---|---|---|
| [`cn/README.md`](cn/README.md) | Documentation — Intégration du marché chinois | Lire d'abord l'état actuel multi-marchés |
| [`cn/TODO_reprise_oracle_dragon_tiger_D7_D11.md`](cn/TODO_reprise_oracle_dragon_tiger_D7_D11.md) | TODO de reprise — Oracle CN × Dragon/Tiger, sprints 15-D7 à 15-D11 | La vérification opérationnelle avant le premier passage est détaillée dans le préflight du 8 octobre, notamment l'heure **02:30 Paris** du s |
| [`cn/TODO_sprint_18c_post_cloture_2026_10_08.md`](cn/TODO_sprint_18c_post_cloture_2026_10_08.md) | TODO — Sprint 18-C après la clôture CN du 8 octobre 2026 | 1. Vérifier que le 8 octobre est une séance ouverte effective dans `market_sessions`, que l'heure de clôture canonique est passée et que la |
| [`cn/actualisation_fournisseurs_chine.md`](cn/actualisation_fournisseurs_chine.md) | Actualisation des fournisseurs Chine | Le fournisseur opérationnel initial est **BaoStock**. Il ne nécessite ni token ni abonnement. **AKShare** est un complément expérimental non |
| [`cn/architecture_bases_batchs_configuration_cn.md`](cn/architecture_bases_batchs_configuration_cn.md) | Architecture Chine — Bases, batchs et configurations `_cn` | Complément obligatoire à la roadmap et au sprint planning d’intégration du marché chinois. |
| [`cn/audit_autorisations_collectes_20261006.md`](cn/audit_autorisations_collectes_20261006.md) | CN — Audit des autorisations des collectes planifiées | Date de vérification : 6 octobre 2026. Périmètre : configuration et chemins de code actuels, conditions publiques des fournisseurs. Audit do |
| [`cn/comparaison_data_fournisseur.md`](cn/comparaison_data_fournisseur.md) | Comparaison des fournisseurs de données Chine pour Alpha-Trade | Le premier socle est désormais **gratuit** : BaoStock fournit le référentiel, le calendrier, les barres, les statuts ST/suspension, les fact |
| [`cn/contrat_univers_tradable_pit.md`](cn/contrat_univers_tradable_pit.md) | CN_A — Convention de radiation et contrat de négociabilité PIT | Statut au 25 septembre 2026 : **contrat figé, testé et utilisé par les 1 942 snapshots du Sprint 8 ; audit global `PASS`**. Ce document comp |
| [`cn/doc_fonctionnel.md`](cn/doc_fonctionnel.md) | α-Trade — Guide fonctionnel du marché chinois (CN_A) | 10 octobre 2026.** Ce guide s'adresse à une personne qui reprend l'application. |
| [`cn/preflight_premier_cycle_2026_10_08.md`](cn/preflight_premier_cycle_2026_10_08.md) | Premier cycle CN du 8 octobre 2026 — contrôle avant ouverture | État au 1er octobre : **préparation terminée, cycle réel non encore observé**. Ce contrôle ne remplace ni les rapports D6/D9/D10, ni le gate |
| [`cn/qualification_previsions_resultats_cninfo_20261006.md`](cn/qualification_previsions_resultats_cninfo_20261006.md) | Prévisions de résultats CN — qualification avant nouveau POC | Date : 6 octobre 2026. Décision : conserver `cn_akshare_enrichment` |
| [`cn/roadmap_integration_marche_chinois_audit_code.md`](cn/roadmap_integration_marche_chinois_audit_code.md) | Audit du code et roadmap d’intégration du marché chinois | La première implémentation opérationnelle utilise BaoStock gratuitement. AKShare reste un enrichissement optionnel ; RQData et Tushare sont |
| [`cn/sprint_0_baseline_us_et_adr.md`](cn/sprint_0_baseline_us_et_adr.md) | Sprint 0 — Baseline US, ADR et remédiation | Date : 19 septembre 2026 |
| [`cn/sprint_10a_labels_oracle_cn.md`](cn/sprint_10a_labels_oracle_cn.md) | Sprint 10-A — Labels Oracle CN_A H5/H10/H15/H20 | Le Sprint 10-A construit des **cibles futures de recherche**, sans entraîner |
| [`cn/sprint_10a_validation_2018_2025.md`](cn/sprint_10a_validation_2018_2025.md) | Sprint 10-A — Validation des labels Oracle CN_A 2018–2025 | `PASS_LABELS_PRICE_ONLY` sur les huit années et les quatre horizons H5, H10, |
| [`cn/sprint_10b_oracle_walk_forward.md`](cn/sprint_10b_oracle_walk_forward.md) | Sprint 10-B — Oracle amplitude CN_A, évaluation Walk-Forward | Le Sprint 10-B demande si les features **price-only** disponibles avant |
| [`cn/sprint_10c_global_ranking.md`](cn/sprint_10c_global_ranking.md) | Sprint 10-C — Global ranking signé CN_A et test conditionnel Oracle | Le Sprint 10-B a confirmé un signal d'**amplitude** CN face à une baseline |
| [`cn/sprint_11a_diagnostic_directionnel.md`](cn/sprint_11a_diagnostic_directionnel.md) | Sprint 11-A — Diagnostic directionnel après Oracle CN_A | franchi son gate face au momentum, mais la comparaison *post-hoc* avec une |
| [`cn/sprint_11b_veto_economic.md`](cn/sprint_11b_veto_economic.md) | Sprint 11-B — Stress économique indicatif du veto D1 CN_A | vérifier si le gain directionnel modeste du veto LightGBM du Sprint 11-A |
| [`cn/sprint_12a_contrat_execution.md`](cn/sprint_12a_contrat_execution.md) | Sprint 12-A — Contrat d'exécution daté CN_A | Le socle d'exécution du marché CN_A est **installé dans `alpha_trade_cn` |
| [`cn/sprint_12b_replay_portefeuille_cn.md`](cn/sprint_12b_replay_portefeuille_cn.md) | Sprint 12-B — Replay de portefeuille CN_A | Le moteur de replay CN et son adaptateur de lecture **sont implémentés**. |
| [`cn/sprint_13a2_normalisation_actions.md`](cn/sprint_13a2_normalisation_actions.md) | Sprint 13-A2 — Normalisation ciblée des actions d'entreprise CN | attendues sont en cache, les quatre journaux d'erreur sont vides, et |
| [`cn/sprint_13a_preflight_economique.md`](cn/sprint_13a_preflight_economique.md) | Sprint 13-A — Préflight économique CN_A (sans lecture des rendements) | actions non classifiées.** Le protocole a été figé avant l'audit, |
| [`cn/sprint_13b2_remediation_positions.md`](cn/sprint_13b2_remediation_positions.md) | Sprint 13-B2 — Remédiation des positions détenues | Le diagnostic 13-B initial a produit 40/40 sous-runs, dont 8 invalides : |
| [`cn/sprint_13b3_audit_huit_blocages.md`](cn/sprint_13b3_audit_huit_blocages.md) | Sprint 13-B3 — Audit des blocages révélés par cinq seeds | Le replay de robustesse |
| [`cn/sprint_13b4_dilution_actions_rachetees.md`](cn/sprint_13b4_dilution_actions_rachetees.md) | Sprint 13-B4 — Dividendes et transferts avec actions rachetées | La preuve A2 compare par défaut le ratio du facteur de prix avec les |
| [`cn/sprint_13b5_materialite_et_preuve_economique.md`](cn/sprint_13b5_materialite_et_preuve_economique.md) | Sprint 13-B5 — Matérialité des censures et droits économiques vérifiés | B5 ne cherche ni un meilleur seuil ni un nouveau modèle. La campagne |
| [`cn/sprint_13b_validation_economique.md`](cn/sprint_13b_validation_economique.md) | Sprint 13-B — Replay économique OOS CN_A (recherche) | Le lanceur est implémenté et testé. Un **premier passage diagnostique** |
| [`cn/sprint_13c_decision_economique.md`](cn/sprint_13c_decision_economique.md) | Sprint 13-C — Décision économique sur les replays CN_A figés | Audit descriptif en lecture seule terminé le 27/09/2026. Le |
| [`cn/sprint_14a_ihm_recherche_isolee.md`](cn/sprint_14a_ihm_recherche_isolee.md) | Sprint 14-A — Sélection de marché et vue CN_A de recherche isolée | Les pages **Pipeline**, **Diagnostic ML** et **Backtesting** affichent |
| [`cn/sprint_14b_diagnostic_campagnes_cn.md`](cn/sprint_14b_diagnostic_campagnes_cn.md) | Sprint 14-B — Registre et diagnostic des campagnes CN_A | Dans **Diagnostic ML → Marché : CN_A**, l'IHM présente les campagnes de |
| [`cn/sprint_14c_replay_recherche_ihm.md`](cn/sprint_14c_replay_recherche_ihm.md) | Sprint 14-C — Lancement d'un replay CN_A de recherche depuis Backtesting | Dans **Backtesting → Marché : CN_A**, le panneau Sprint 14-C permet de |
| [`cn/sprint_14d_pipeline_recherche_cn.md`](cn/sprint_14d_pipeline_recherche_cn.md) | Sprint 14-D — Pipeline CN_A de recherche | État au 27 septembre 2026 : l'écran Pipeline permet de lancer **un fold Oracle ou Global Ranking CN_A à la fois**. Il entraîne le modèle sél |
| [`cn/sprint_15a0_audit_money_flow_pit.md`](cn/sprint_15a0_audit_money_flow_pit.md) | Sprint 15-A0 — Audit des flux de capitaux CN point-in-time | Le besoin 15A est une série quotidienne **par titre** de flux acheteur/vendeur, idéalement ventilée par taille d'ordre et connue à la date d |
| [`cn/sprint_15b0_audit_margin_lending_pit.md`](cn/sprint_15b0_audit_margin_lending_pit.md) | Sprint 15-B0 — Audit financement sur marge et prêt de titres CN | Les relevés `融资融券` viennent des déclarations des courtiers aux bourses de Shanghai et Shenzhen. Ils contiennent des montants de financement, |
| [`cn/sprint_15b1_backfill_pilote_margin_lending.md`](cn/sprint_15b1_backfill_pilote_margin_lending.md) | Sprint 15-B1 — Backfill pilote `融资融券` SSE/SZSE, 2018–2025 | Suite exécutée : 15-B2 — rapprochement des listes et contrat PIT. Les constats ci-dessous décrivent l'état du pilote B1 ; B2 a depuis rappro |
| [`cn/sprint_15b2_eligibilite_et_contrat_pit.md`](cn/sprint_15b2_eligibilite_et_contrat_pit.md) | Sprint 15-B2 — Éligibilité historique et contrat PIT de financement/prêt | Suite exécutée : 15-B3 — qualification des blocages, avec extension aux listes Shenzhen des 40 séances et réconciliation des mêmes mesures d |
| [`cn/sprint_15b3_qualification_blocages.md`](cn/sprint_15b3_qualification_blocages.md) | Sprint 15-B3 — Qualification des blocages financement/prêt de titres | Suite préparée : 15-B4 — dataset quotidien et pré-enregistrement. Collecteur et smoke validés ; collecte complète encore à lancer. |
| [`cn/sprint_15b4_dataset_szse_et_preregistration.md`](cn/sprint_15b4_dataset_szse_et_preregistration.md) | Sprint 15-B4 — Dataset quotidien Shenzhen et pré-enregistrement | 28 septembre 2026. Suite de 15-B3. |
| [`cn/sprint_15b5_features_et_jointures_temporelles.md`](cn/sprint_15b5_features_et_jointures_temporelles.md) | Sprint 15-B5 — Fenêtres de marge et jointures temporelles Oracle | 29 septembre 2026. Suite du dataset B4. |
| [`cn/sprint_15b6_calendrier_et_extension_oracle_oof.md`](cn/sprint_15b6_calendrier_et_extension_oracle_oof.md) | Sprint 15-B6 — Calendrier réalisable et extension Oracle OOF | 29 septembre 2026. Suite de 15-B5. |
| [`cn/sprint_15b7_jointures_2021_preflight_directionnel.md`](cn/sprint_15b7_jointures_2021_preflight_directionnel.md) | Sprint 15-B7 — Jointures Oracle 2021 et préflight directionnel réel | 29 septembre 2026. Suite de 15-B6. Rapport canonique : report.json. |
| [`cn/sprint_15b8_ablation_directionnelle_marge.md`](cn/sprint_15b8_ablation_directionnelle_marge.md) | Sprint 15-B8 — Ablation directionnelle des données de marge SZSE | 29 septembre 2026. Suite du préflight B7, suivant le protocole B6 pré-enregistré. |
| [`cn/sprint_15c0_audit_analystes_pit.md`](cn/sprint_15c0_audit_analystes_pit.md) | Sprint 15-C0 — Audit des analystes et prévisions PIT (CN_A) | Audit du 29 septembre 2026. **Verdict : NO-GO pour entraîner sur un historique PIT 2018–2025 avec les données actuellement disponibles.** Au |
| [`cn/sprint_15d0_audit_evenements_pit.md`](cn/sprint_15d0_audit_evenements_pit.md) | Sprint 15-D0 — Audit PIT des événements CN_A | Audit réalisé le 29 septembre 2026, en lecture seule. Objet : déterminer si les **prévisions de résultats publiées par l'émetteur** et les l |
| [`cn/sprint_15d10_appariement_d7_quotidien.md`](cn/sprint_15d10_appariement_d7_quotidien.md) | Sprint 15-D10 — Journal quotidien de l'appariement D7 | Le batch `cn_dragon_tiger_daily_match` de batch.yaml automatise **uniquement l'appariement de recherche sans issues futures** défini par D7. |
| [`cn/sprint_15d11_cumul_d7_outcome_blind.md`](cn/sprint_15d11_cumul_d7_outcome_blind.md) | Sprint 15-D11 — Cumul prospectif D7, sans connaissance des issues | Le journal D10 produit un appariement indépendant par séance de décision. D11 additionne ces seules séances pour savoir **si le protocole D7 |
| [`cn/sprint_15d1_pilote_guidance_pit.md`](cn/sprint_15d1_pilote_guidance_pit.md) | Sprint 15-D1 — Pilote des prévisions de résultats CN sous proxy PIT | Réalisé le 29 septembre 2026. **Verdict : faisabilité documentaire confirmée, mais pas de GO pour un entraînement historique ni pour le serv |
| [`cn/sprint_15d2_audit_dragon_tiger_pit.md`](cn/sprint_15d2_audit_dragon_tiger_pit.md) | Sprint 15-D2 — Audit Dragon/Tiger historique SSE/SZSE | Audit réalisé le 29 septembre 2026. **Verdict : source et identité des événements validées sur quatre séances échantillons ; contrat PIT his |
| [`cn/sprint_15d3_robustesse_historique_dragon_tiger.md`](cn/sprint_15d3_robustesse_historique_dragon_tiger.md) | Sprint 15-D3 — Robustesse historique Dragon/Tiger 2018–2025 | Audit achevé le 30 septembre 2026. **Verdict : réconciliation des identités confirmée sur l'échantillon historique, intégrité structurelle d |
| [`cn/sprint_15d4_contrat_temporel_couverture_dragon_tiger.md`](cn/sprint_15d4_contrat_temporel_couverture_dragon_tiger.md) | Sprint 15-D4 — Contrat temporel et couverture Dragon/Tiger × Oracle | Audit du 30 septembre 2026. **Verdict : couverture suffisante pour un examen exploratoire, mais archive non certifiée PIT et aucun GO ML.** |
| [`cn/sprint_15d5_preflight_dragon_tiger_et_observations.md`](cn/sprint_15d5_preflight_dragon_tiger_et_observations.md) | Sprint 15-D5 — Préflight directionnel Dragon/Tiger et observation prospective | Audit exécuté le 30 septembre 2026. **Verdict : NO_GO pour entraînement/backtest/serving historique ; GO pour constituer un journal prospect |
| [`cn/sprint_15d6_collecte_prospective_dragon_tiger.md`](cn/sprint_15d6_collecte_prospective_dragon_tiger.md) | Sprint 15-D6 — Observations Dragon/Tiger prospectives, deux passages CN | Mise en place le 30 septembre 2026. **Deux tâches Windows de recherche sont installées ; aucun modèle, label, table CN/US, backtest ou servi |
| [`cn/sprint_15d7_protocole_appariement_dragon_tiger.md`](cn/sprint_15d7_protocole_appariement_dragon_tiger.md) | Sprint 15-D7 — Protocole apparié Dragon/Tiger, sans lecture des issues | État au 30 septembre 2026 : **pré-enregistrement et moteur d'appariement outcome-blind livrés**. Aucun entraînement, backtest ou changement |
| [`cn/sprint_15d7a_rattrapage_canonique_2026.md`](cn/sprint_15d7a_rattrapage_canonique_2026.md) | Sprint 15-D7a — rattrapage canonique CN 2026 | Le protocole Dragon/Tiger 15-D7 requiert des candidats Oracle réellement prédits sur des séances 2026. La base `alpha_trade_cn` s'arrêtait a |
| [`cn/sprint_15d8_export_oracle_prospectif.md`](cn/sprint_15d8_export_oracle_prospectif.md) | Sprint 15-D8 — export Oracle CN H20 prospectif, recherche uniquement | Le code d'export avant ouverture est livré, sans promotion au serving et sans ordre de bourse. Le rattrapage initial du Sprint 15-D7a s'arrê |
| [`cn/sprint_15d9_journal_oracle_prospectif_quotidien.md`](cn/sprint_15d9_journal_oracle_prospectif_quotidien.md) | Sprint 15-D9 — journal quotidien Oracle CN prospectif | Le batch `cn_oracle_prospective_daily` de batch.yaml constitue une chaîne **de recherche uniquement** : séance CN close J → collecte BaoStoc |
| [`cn/sprint_16a_gates_et_protocole_directionnel.md`](cn/sprint_16a_gates_et_protocole_directionnel.md) | Sprint 16-A — Éligibilité des familles et protocole directionnel CN | État au 1er octobre 2026 : **16-A réalisé (audit et cadre de pré-enregistrement), campagne 16-B non ouverte**. Les seuils propres à une nouv |
| [`cn/sprint_17a_audit_exploitation_cn.md`](cn/sprint_17a_audit_exploitation_cn.md) | Sprint 17-A — Audit opérationnel CN avant industrialisation | Mise à jour du 01/10/2026 : la sauvegarde CN a été traitée dans le Sprint 17-B. Le contrôle quotidien et le propriétaire unique D9 ont été i |
| [`cn/sprint_17b_sauvegarde_restauration_cn.md`](cn/sprint_17b_sauvegarde_restauration_cn.md) | Sprint 17-B — Sauvegarde et restauration isolées de la base CN | Ce sprint traite le finding critique du 17-A : `alpha_trade_cn` n'avait pas de sauvegarde planifiée. Le périmètre est **CN_A / `cn_primary` |
| [`cn/sprint_17c_qualite_quotidienne_proprietaire_collecte.md`](cn/sprint_17c_qualite_quotidienne_proprietaire_collecte.md) | Sprint 17-C — Propriétaire unique de la collecte CN et qualité quotidienne | État du 1er octobre 2026. Le code, la configuration et la tâche de contrôle sont installés ; **la preuve de sept séances réelles consécutive |
| [`cn/sprint_17d_preparation_bascule_catalogues.md`](cn/sprint_17d_preparation_bascule_catalogues.md) | Sprint 17-D — Préparation de la bascule des catalogues CN (sans activation) | État au 1er octobre 2026 : **préparation seulement**. Les quatre tâches prospectives D6/D9/D10 restent installées et lisent `batch.yaml`. Au |
| [`cn/sprint_18a_routage_broker_fail_closed.md`](cn/sprint_18a_routage_broker_fail_closed.md) | Sprint 18-A — Contrat broker et verrou de marché | Le moteur d'ordres existant reste **US_EQ / Alpaca**. Un contrat d'exécution minimal et un routeur de marché explicite sont introduits dans |
| [`cn/sprint_18b_shadow_execution_cn.md`](cn/sprint_18b_shadow_execution_cn.md) | Sprint 18-B — Shadow d'exécution CN_A, sans broker | Le module `service/market/cn_shadow_execution_18b.py` permet de produire une **preuve prospective, en trois temps**, pour une intention CN_A |
| [`cn/sprint_18c_pilote_shadow_prospectif.md`](cn/sprint_18c_pilote_shadow_prospectif.md) | Sprint 18-C — Pilote shadow prospectif Oracle CN | Le pilote relie l'export Oracle H20 prospectif du Sprint 15-D8 au moteur d'exécution **hypothétique** du Sprint 18-B. Il ne constitue ni une |
| [`cn/sprint_18d_port_oms_et_doubles.md`](cn/sprint_18d_port_oms_et_doubles.md) | Sprint 18-D — Port OMS complet et doubles mock/replay | Le contrat `ExecutionBrokerPort` de `execution_engine/broker_router.py` reflète désormais **toutes les opérations réellement appelées** par |
| [`cn/sprint_1_market_context.md`](cn/sprint_1_market_context.md) | Sprint 1 — MarketContext et registre de marchés | Date de clôture : 19 septembre 2026 |
| [`cn/sprint_2_referentiel_instruments.md`](cn/sprint_2_referentiel_instruments.md) | Sprint 2 — Référentiel instruments et mappings fournisseurs | Date de clôture : 19 septembre 2026 |
| [`cn/sprint_3_contexte_marche_runs.md`](cn/sprint_3_contexte_marche_runs.md) | Sprint 3 — Contexte marché sur les runs, batches et univers | Sprint terminé le 20 septembre 2026. Gate : **GO**. |
| [`cn/sprint_4_calendrier_pit_multi_marches.md`](cn/sprint_4_calendrier_pit_multi_marches.md) | Sprint 4 — Calendrier et PIT multi-marchés | Statut : **GO** — 20 septembre 2026 |
| [`cn/sprint_5_migration_canonique_us.md`](cn/sprint_5_migration_canonique_us.md) | Sprint 5 — Migration canonique US vers `instrument_id` | Le Sprint 5 retire `symbol` de son rôle d’identité technique. Un ticker reste |
| [`cn/sprint_6_connecteur_tushare_staging.md`](cn/sprint_6_connecteur_tushare_staging.md) | Sprint 6 — Connecteur Tushare et staging brut CN | Le Sprint 6 est **implémenté et validé structurellement**, mais son gate final reste : |
| [`cn/sprint_6_sources_gratuites_baostock.md`](cn/sprint_6_sources_gratuites_baostock.md) | Sprint 6 — Socle de données CN gratuit avec BaoStock | Le premier chemin opérationnel Chine d’Alpha-Trade repose désormais sur des sources gratuites : |
| [`cn/sprint_7a_canonicalisation_pilote.md`](cn/sprint_7a_canonicalisation_pilote.md) | Sprint 7-A — Canonicalisation pilote du marché chinois | Le Sprint 7-A transforme un sous-ensemble contrôlé du staging BaoStock en données canoniques consommables par les futurs moteurs de features |
| [`cn/sprint_7b_audit_final_2026_09_24.md`](cn/sprint_7b_audit_final_2026_09_24.md) | Sprint 7-B — Audit après backfill du 24 septembre 2026 | Le backfill historique 2018–2025 est terminé : **217/217 lots `COMPLETED`, aucun lot en échec**. Les contrôles intégrés renvoient `PASS` : * |
| [`cn/sprint_7b_canonicalisation_complete.md`](cn/sprint_7b_canonicalisation_complete.md) | Sprint 7-B — Canonicalisation complète et couverture historique CN | Le Sprint 7-B généralise le pipeline validé au Sprint 7-A à toutes les actions A ayant chevauché la période du 1er janvier 2018 au 31 décemb |
| [`cn/sprint_8_univers_pit.md`](cn/sprint_8_univers_pit.md) | Sprint 8 — Univers chinois quotidien Point-in-Time | Statut au 25 septembre 2026 : **backfill 2018–2025 et gate PIT terminés, `PASS` technique**. Voir la validation finale. Ce travail ne branch |
| [`cn/sprint_8_validation_finale_2026_09_25.md`](cn/sprint_8_validation_finale_2026_09_25.md) | Sprint 8 CN — Validation finale du backfill PIT | Date : 25 septembre 2026. Périmètre : actions A CN_A, séances ouvertes du 1er janvier 2018 au 31 décembre 2025, politique V1 du guide Sprint |
| [`cn/sprint_9_features_cn_price_v1.md`](cn/sprint_9_features_cn_price_v1.md) | Sprint 9 — Panel de features CN_A `cn_price_v1` | Le Sprint 9 construit un **panel de recherche price-only, point-in-time**, à partir de |
| [`cn/sprint_9_validation_2018_2025.md`](cn/sprint_9_validation_2018_2025.md) | Sprint 9 — Validation du panel CN 2018–2025 | Date : 25 septembre 2026. Profil : `cn_price_v1`. Source des décisions : |
| [`cn/sprint_planning_integration_marche_chinois.md`](cn/sprint_planning_integration_marche_chinois.md) | Sprint planning détaillé — Intégration du marché chinois dans α-Trade | Document d’exécution associé à `roadmap_integration_marche_chinois_audit_code.md`. |
| [`cn/Étude d’opportunité — Extension d’α-Trade au marché actions chinois.md`](cn/%C3%89tude%20d%E2%80%99opportunit%C3%A9%20%E2%80%94%20Extension%20d%E2%80%99%CE%B1-Trade%20au%20march%C3%A9%20actions%20chinois.md) | Étude d’opportunité — Extension d’α-Trade au marché actions chinois | **Mise à jour d’architecture — 19 septembre 2026.** Les conclusions fournisseurs et marché de cette étude restent utiles. La cible technique |

## Marché français — FR

| Document | Titre | Description |
|---|---|---|
| [`fr/README.md`](fr/README.md) | France — état actuel et parcours documentaire | État rapproché des sources le **10 octobre 2026**. Marché FR_EQ, base |
| [`fr/TODO_reprise_exploitation_sprints_16_18.md`](fr/TODO_reprise_exploitation_sprints_16_18.md) | TODO — Reprise France après préparation des Sprints 16–18 | État au 9 octobre 2026 : infrastructure livrée, clôtures avec réserves ; pas de |
| [`fr/TODO_sprint_12_reste_a_faire.md`](fr/TODO_sprint_12_reste_a_faire.md) | TODO — Reprise et clôture du Sprint 12 France | Date de référence : 4 octobre 2026. |
| [`fr/adr_0001_contrat_marche_et_isolation.md`](fr/adr_0001_contrat_marche_et_isolation.md) | ADR FR-0001 — Marché France et isolation physique | Mise à jour au Sprint 6-C (3 octobre 2026) : le calendrier XPAR a été validé au Sprint 4. Le benchmark de recherche devient `FR_RESEARCH_EW_ |
| [`fr/audit_autorisations_collectes_20261006.md`](fr/audit_autorisations_collectes_20261006.md) | Audit des droits de collecte des batchs FR — 6 octobre 2026 | La collecte Yahoo automatisée n'a pas d'autorisation explicite démontrée. |
| [`fr/audit_fiabilite_eodhd_euronext.md`](fr/audit_fiabilite_eodhd_euronext.md) | Fiabilité EODHD France — comparaison élargie avec Euronext | Objectif : mesurer une **concordance de données** sur plusieurs titres et |
| [`fr/catalogue_sources_gratuites_validation_historique.md`](fr/catalogue_sources_gratuites_validation_historique.md) | Catalogue des sources gratuites — validation historique du marché FR | Sources, limites et procédure de seconde revue. |
| [`fr/consensus_borrow_options_collectes.md`](fr/consensus_borrow_options_collectes.md) | Collectes FR séparées : consensus, borrow et options | après l'audit des droits. Leur état actif mentionné ci-dessous est historique. |
| [`fr/consensus_collecte_quotidienne.md`](fr/consensus_collecte_quotidienne.md) | Consensus FR — collecte prospective en quarantaine et promotion future | `BLOCKED_YAHOO_AUTOMATED_ACCESS`. L'autorisation utilisateur du pilote ne prouve |
| [`fr/couverture_univers_et_exclusions.md`](fr/couverture_univers_et_exclusions.md) | Couverture de l'univers France et motifs d'exclusion | État mesuré le 3 octobre 2026, depuis les archives EODHD téléchargées au 1er octobre 2026. Les chiffres décrivent la couverture de notre app |
| [`fr/demande_preuves_historiques_manquantes.md`](fr/demande_preuves_historiques_manquantes.md) | FR — Bilan public gratuit et demande ciblée de preuves historiques | État au 4 octobre 2026. Référence : comparaison économique des folds 6/7, |
| [`fr/etude_integration_marche_francais.md`](fr/etude_integration_marche_francais.md) | Étude d'intégration du marché actions français | État au 17 septembre 2026. Étude de faisabilité et POC de recherche uniquement : aucune table, stratégie, tâche planifiée ou exécution live |
| [`fr/execution_sprints_2_5_2026-10-02.md`](fr/execution_sprints_2_5_2026-10-02.md) | France — exécution des Sprints 2 à 5 (2 octobre 2026) | Ce document est un **état vérifié**, à lire avec le planning. Il ne constitue pas un GO pour l'entraînement français. Aucun batch US/CN ni e |
| [`fr/inpi_univers_collecte_securisee.md`](fr/inpi_univers_collecte_securisee.md) | INPI — Extension à l'univers FR et collecte en quarantaine | `BLOCKED_INPI_RETENTION`. L'accès API aux comptes publics est autorisé ; le |
| [`fr/options_mifir_collecte_quotidienne.md`](fr/options_mifir_collecte_quotidienne.md) | Options FR — collecte quotidienne partielle MiFIR + FIRDS | Le batch `fr_options_mifir_trade_sync` est implémenté, mais livré avec |
| [`fr/options_mifir_firds_poc.md`](fr/options_mifir_firds_poc.md) | Options FR : POC transactions MiFIR + référentiel FIRDS | Suite au GO, un batch quotidien partiel pour tout l'univers FR est maintenant |
| [`fr/options_mifir_qualification.md`](fr/options_mifir_qualification.md) | Qualification options FR — premier passage univers et unités | Le GO portait sur l'audit de la collecte partielle et la qualification des quantités, |
| [`fr/poc_guidance_120_emetteurs.md`](fr/poc_guidance_120_emetteurs.md) | POC France — faisabilité des révisions de guidance (120 émetteurs) | 13 UP/10 DOWN non encore validés indépendamment ; 26 observations recoupées |
| [`fr/publication_quotidienne_staging_sql.md`](fr/publication_quotidienne_staging_sql.md) | Publication quotidienne des barres FR en staging SQL | Le batch existant `fr_daily_bars_sync` collecte toujours EODHD en fichiers |
| [`fr/remediation_collectes_couverture_20261009.md`](fr/remediation_collectes_couverture_20261009.md) | Remédiation des collectes FR et audit SQL — 9 octobre 2026 | publication quotidienne des barres en staging SQL |
| [`fr/runbook_exploitation_fr.md`](fr/runbook_exploitation_fr.md) | Runbook France — préparation et reprise sûre | Document de passation du 9 octobre 2026. Marché `FR_EQ`, base `alpha_trade_fr` |
| [`fr/simulation_shadow_locale_xpar_164.md`](fr/simulation_shadow_locale_xpar_164.md) | Simulation shadow locale — 164 titres XPAR | Le flux de recherche local fonctionne : **164 titres scorés, zéro exclusion, |
| [`fr/sous_ensemble_reellement_utilisable_20261009.md`](fr/sous_ensemble_reellement_utilisable_20261009.md) | Sous-ensemble FR réellement utilisable — qualification bornée du 9 octobre 2026 | Il existe un sous-ensemble **utilisable pour une étude exploratoire des entrées |
| [`fr/sprint_0_1_baseline_et_routage.md`](fr/sprint_0_1_baseline_et_routage.md) | Sprints 0–1 France — audit de référence et route isolée | État : 2 octobre 2026. Voir l'ADR de décision et le planning complet. Ce rapport décrit ce qui a été **vérifié**, non les sprints futurs. |
| [`fr/sprint_10a_diagnostic_directionnel_h5.md`](fr/sprint_10a_diagnostic_directionnel_h5.md) | Sprint 10-A — Références directionnelles dans le TOP20 Oracle H5 | Premier diagnostic du Sprint 10, pas un entraînement de modèle directionnel ni la clôture du sprint. H5 prix-only, folds 4/5/6 du Sprint 9-A |
| [`fr/sprint_10b_modele_directionnel_mutualise_h5.md`](fr/sprint_10b_modele_directionnel_mutualise_h5.md) | Sprint 10-B — Pilote directionnel mutualisé H5, train conditionnel Oracle OOF | H5 prix-only, 14 features figées FR. Les périodes de développement ont déjà été examinées en 9-A et 10-A : **aucun résultat de ce lot n'est |
| [`fr/sprint_10c1_reparation_fold3.md`](fr/sprint_10c1_reparation_fold3.md) | Sprint 10-C1 — Tentative de réparation des lacunes du fold 3 | L'audit a été exécuté le 3 octobre 2026. Aucune admission n'a été forcée, |
| [`fr/sprint_10c2_audit_prix_independants.md`](fr/sprint_10c2_audit_prix_independants.md) | Sprint 10-C2 — Audit des prix indépendants du fold 3 | Une source **officielle, gratuite et effectivement téléchargée** permet de |
| [`fr/sprint_10c3_reparation_fold7.md`](fr/sprint_10c3_reparation_fold7.md) | Sprint 10-C3 — priorité à la réparation documentaire du fold 7 | Le Sprint 10 doit être traité avant le Sprint 11. L'audit général de fiabilité |
| [`fr/sprint_10c_qualification_historique_oracle_oof.md`](fr/sprint_10c_qualification_historique_oracle_oof.md) | Sprint 10-C — Qualification de davantage d'historique Oracle OOF FR | trace les lacunes jusqu'aux preuves source. Six publications ESMA non retrouvées |
| [`fr/sprint_11a_references_economiques.md`](fr/sprint_11a_references_economiques.md) | Sprint 11-A économique — références simples et aptitude au rejeu | Mise à jour4 octobre2026 : qualification partielle et scénario de coûts. |
| [`fr/sprint_11b_qualification_sources_evenementielles.md`](fr/sprint_11b_qualification_sources_evenementielles.md) | Sprint 11-B — qualification des sources événementielles gratuites FR | État exécuté le 4 octobre 2026. **Sprint 11 en cours, pas clôturé.** |
| [`fr/sprint_11c_evenements_guidance_ablation.md`](fr/sprint_11c_evenements_guidance_ablation.md) | Sprint 11-C — disponibilité, revue de guidance et ablation événementielle | Les résultats AMF/DILA ci-dessous restent figés, aucun modèle refait. La suite |
| [`fr/sprint_11d_corpus_guidance_elargi.md`](fr/sprint_11d_corpus_guidance_elargi.md) | Sprint 11-D — Élargissement et validation du corpus de guidance FR | Les chiffres ci-dessous décrivent la vague11-D figée. La suite collecte126 PDF |
| [`fr/sprint_11e_completion_gratuite_guidance.md`](fr/sprint_11e_completion_gratuite_guidance.md) | Sprint 11-E — Complément gratuit et dossier de seconde revue guidance | Date : 4 octobre 2026. Marché FR. Recherche uniquement. |
| [`fr/sprint_11f_sources_gratuites_et_seconde_revue.md`](fr/sprint_11f_sources_gratuites_et_seconde_revue.md) | Sprint 11-F — Sources gratuites, comparabilité et seconde revue | État vérifié le 4 octobre 2026. Recherche FR uniquement. |
| [`fr/sprint_11g_seconde_passe_documentaire.md`](fr/sprint_11g_seconde_passe_documentaire.md) | Sprint 11-G - Seconde passe documentaire, non indépendante | Date : 4 octobre 2026. Dossier source : `second-review-20261004-v4`. |
| [`fr/sprint_11h_arbitrage_et_disponibilite_pit.md`](fr/sprint_11h_arbitrage_et_disponibilite_pit.md) | Sprint 11-H — Arbitrage préparatoire et qualification PIT | État du 4 octobre 2026. Suite de la seconde passe technique 11-G. |
| [`fr/sprint_12a_couts_taxes_operations_sur_titres.md`](fr/sprint_12a_couts_taxes_operations_sur_titres.md) | FR — qualification des coûts, taxes et opérations sur titres (12-A) | Le GO de qualification est exécuté sur les **21 379 chemins candidats H5 de |
| [`fr/sprint_12b_moteur_rejeu_economique.md`](fr/sprint_12b_moteur_rejeu_economique.md) | Sprint 12-B — Moteur de rejeu économique FR | État au 4 octobre 2026 : **moteur de recherche implémenté et testé ; rejeu des |
| [`fr/sprint_12c_qualification_preuves_execution.md`](fr/sprint_12c_qualification_preuves_execution.md) | 12-C — Qualification des preuves d'exécution FR | La demande est de qualifier les preuves avant le comparatif économique réel. |
| [`fr/sprint_12d_levee_blocages_gratuits.md`](fr/sprint_12d_levee_blocages_gratuits.md) | Sprint 12-D — Levée gratuite des réserves économiques FR | État vérifié le 4 octobre 2026. **Avancement partiel, pas de GO économique.** |
| [`fr/sprint_12e_perimetre_exploitable.md`](fr/sprint_12e_perimetre_exploitable.md) | Sprint 12-E — Périmètre exploitable et biais de couverture | État du 4 octobre 2026. **Audit exécuté ; aucun rejeu économique réel autorisé.** |
| [`fr/sprint_12f_priorites_fiscales_operations_titres.md`](fr/sprint_12f_priorites_fiscales_operations_titres.md) | Sprint 12-F — Priorités fiscales Oracle et opérations sur titres | La passe classe les **40 titres** dont une fiscalité non qualifiée affecte |
| [`fr/sprint_13_bilan_et_conditions_reprise.md`](fr/sprint_13_bilan_et_conditions_reprise.md) | Sprint 13 France — Bilan, limites et conditions de reprise | Date : 4 octobre 2026. Ce document est le point d'entrée pour reprendre le |
| [`fr/sprint_13a_protocole_validation_economique.md`](fr/sprint_13a_protocole_validation_economique.md) | Sprint 13-A — Gel du protocole économique France et contrôle des gates | Suite technique préparée : 13-B — tapes et reporting. |
| [`fr/sprint_13b_assemblage_tapes_reporting.md`](fr/sprint_13b_assemblage_tapes_reporting.md) | Sprint 13-B — Préparation des tapes et du reporting économique France | Date : 4 octobre 2026. Statut **PREPARED_REPLAY_BLOCKED**. |
| [`fr/sprint_13b_exploratoire_fournisseur.md`](fr/sprint_13b_exploratoire_fournisseur.md) | 13-B exploratoire fournisseur — comparaison économique distincte | aboutit à 24/24 cellules exploratoires (sortie v8), avec analyse de concentration |
| [`fr/sprint_13c_reparations_decision_economique.md`](fr/sprint_13c_reparations_decision_economique.md) | Sprint 13-C — Réparations et décision économique France | Date : 4 octobre 2026. **Branche exploratoire complète ; validation stricte bloquée.** |
| [`fr/sprint_13d_robustesse_economique.md`](fr/sprint_13d_robustesse_economique.md) | Sprint 13-D — Robustesse économique exploratoire figée | Expérience terminée le 4 octobre 2026 : **96/96 cellules exécutées, zéro blocage**. |
| [`fr/sprint_14_bilan_validation_operateur.md`](fr/sprint_14_bilan_validation_operateur.md) | Sprint 14 France — Bilan de validation du parcours opérateur recherche | Date : 5 octobre 2026. Décision : **terminé pour le périmètre de recherche |
| [`fr/sprint_14a_ihm_recherche_isolee.md`](fr/sprint_14a_ihm_recherche_isolee.md) | Sprint 14-A — Consultation France isolée dans l'IHM et la CLI | 5 octobre 2026. GO du propriétaire pour commencer le Sprint 14. |
| [`fr/sprint_14b_lancement_replay_et_suivi.md`](fr/sprint_14b_lancement_replay_et_suivi.md) | Sprint 14-B — Lancement, historique et suivi des replays France | 5 octobre 2026. Tranche implémentée après le GO Sprint 14 ; aucune promotion |
| [`fr/sprint_15a_catalogue_et_orchestration.md`](fr/sprint_15a_catalogue_et_orchestration.md) | Sprint 15-A — Catalogue et orchestration opérationnelle France | 5 octobre 2026. GO Sprint 15 reçu. Première tranche implémentée ; **le Sprint |
| [`fr/sprint_15b_eodhd_quotidien.md`](fr/sprint_15b_eodhd_quotidien.md) | Sprint 15-B — Collecte EODHD quotidienne France, J−7/J | 5 octobre 2026. Collecteur implémenté, tests et deux passages réels réussis |
| [`fr/sprint_15c_deblocage_collectes.md`](fr/sprint_15c_deblocage_collectes.md) | Sprint 15-C — Déblocage des collectes possibles | État courant et preuves de sauvegarde/exploitation : [bilan 15-G du 6 octobre |
| [`fr/sprint_15d_sauvegardes_et_blocages.md`](fr/sprint_15d_sauvegardes_et_blocages.md) | Sprint 15-D — Sauvegardes vérifiées et référentiels encore bloqués | `backups/fr/qualification/20261005T193256-a4610757/report.json` porte |
| [`fr/sprint_15e_referentiel_quotidien.md`](fr/sprint_15e_referentiel_quotidien.md) | Sprint 15-E — Référentiel ESMA quotidien et prérequis INPI | 5 octobre 2026. Collecte gratuite publique ESMA, fichiers de recherche FR |
| [`fr/sprint_15f_inpi_comptes_annuels.md`](fr/sprint_15f_inpi_comptes_annuels.md) | Sprint 15-F — Pilote INPI comptes annuels | `BLOCKED_INPI_RETENTION`. Les paragraphes d'activation ci-dessous décrivent |
| [`fr/sprint_15g_bilan_cloture_operationnelle.md`](fr/sprint_15g_bilan_cloture_operationnelle.md) | Sprint 15-G — Bilan de clôture opérationnelle FR | État vérifié le **6 octobre 2026**, fuseau Europe/Paris. |
| [`fr/sprint_16_cloture_bornee.md`](fr/sprint_16_cloture_bornee.md) | Sprint 16 — Clôture bornée du 8 octobre 2026 | À la demande de l'utilisateur, la qualification est arrêtée au sous-ensemble |
| [`fr/sprint_16a_contrat_prediction_et_preflight.md`](fr/sprint_16a_contrat_prediction_et_preflight.md) | Sprint 16-A — Contrat de préparation de la prédiction France | Ce sous-sprint ne transforme pas un résultat de recherche en modèle de production. |
| [`fr/sprint_16b_assemblage_quotidien_pit.md`](fr/sprint_16b_assemblage_quotidien_pit.md) | Sprint 16-B — Assemblage quotidien FR à partir des observations archivées | L'assemblage est hors ligne, en fichiers de recherche. Aucune connexion SQL, |
| [`fr/sprint_16c_rattrapage_et_reserves.md`](fr/sprint_16c_rattrapage_et_reserves.md) | Sprint 16-C — Rattrapage de démarrage et qualification des réserves | Le 16-B a identifié l'absence de warmup |
| [`fr/sprint_16d_identites_evenements_reference_observee.md`](fr/sprint_16d_identites_evenements_reference_observee.md) | Sprint 16-D — Identités, événements réservés et référence connue à la décision | État : qualification technique et revue documentaire du 6 octobre 2026. |
| [`fr/sprint_16e_preuves_et_decision_reelle.md`](fr/sprint_16e_preuves_et_decision_reelle.md) | Sprint 16-E — Preuves locales et contrôle à une ouverture réelle | État au 6 octobre 2026, après 21 h Paris : outils livrés, preuves partielles |
| [`fr/sprint_16f_confirmation_ouverture.md`](fr/sprint_16f_confirmation_ouverture.md) | Sprint 16-F — Confirmation verrouillée sur une ouverture réelle | État au 7 octobre 2026 : **confirmation exécutée à 14 h 57, coupure maintenue |
| [`fr/sprint_16f_remediation.md`](fr/sprint_16f_remediation.md) | Sprint 16-F — Remédiation prospective | inchangée à 09:00 ; master frais couvrant le 7 octobre, 244 features calculables, |
| [`fr/sprint_16g2_rejeu_ancre_et_contrat_prospectif.md`](fr/sprint_16g2_rejeu_ancre_et_contrat_prospectif.md) | Sprint 16-G2 — Rejeu ancré et contrat prospectif distinct | zéro anomalie ; contrat prospectif en brouillon, aucun GO serving.** |
| [`fr/sprint_16g3_revue_liberation_actions_devises.md`](fr/sprint_16g3_revue_liberation_actions_devises.md) | Sprint 16-G3 — Revue de libération, actions et devises | Voir la clôture bornée du Sprint 16. |
| [`fr/sprint_16g_bilan_et_plan_de_liberation.md`](fr/sprint_16g_bilan_et_plan_de_liberation.md) | Sprint 16-G — Bilan du 8 octobre et plan de libération | Clôture administrative avec réserves, décidée après la dernière qualification |
| [`fr/sprint_16g_nouvelle_fenetre_prospective.md`](fr/sprint_16g_nouvelle_fenetre_prospective.md) | Sprint 16-G — nouvelle fenêtre prospective distincte | Le Sprint 16 est clos administrativement avec validation shadow bloquée : |
| [`fr/sprint_16g_parite_features_et_fenetre.md`](fr/sprint_16g_parite_features_et_fenetre.md) | Suite Sprint 16-G — Parité arithmétique et fenêtre d'identité | Cette étape poursuit la contre-revue technique demandée à l'assistant. Aucun |
| [`fr/sprint_16g_pilote_devises_actions.md`](fr/sprint_16g_pilote_devises_actions.md) | Sprint 16-G — pilote identité, devise et opérations sur titres | Pilote de qualification sur **AIR.PA, OR.PA et SAN.PA**, trois candidats du |
| [`fr/sprint_16g_preuve_devise_mifir.md`](fr/sprint_16g_preuve_devise_mifir.md) | Sprint 16-G — Preuve ponctuelle de devise MiFIR | Le fichier officiel Euronext Paris contient des publications de transactions |
| [`fr/sprint_16g_reparation_preancrage.md`](fr/sprint_16g_reparation_preancrage.md) | Sprint 16-G — reconstruction partielle avant l'ancrage | Le dossier figé utilise 21 séances de features du 9 septembre au 7 octobre. |
| [`fr/sprint_16g_revue_sources_pilote_20261008.md`](fr/sprint_16g_revue_sources_pilote_20261008.md) | Sprint 16-G — revue ciblée des preuves du pilote, 8 octobre 2026 | La recherche documentaire sur AIR.PA, OR.PA et SAN.PA apporte des |
| [`fr/sprint_17_cloture_avec_reserves.md`](fr/sprint_17_cloture_avec_reserves.md) | Sprint 17 — Clôture administrative avec réserves | L'utilisateur a choisi l'option 2 : suspendre le raccordement d'ordres et |
| [`fr/sprint_17a_preparation_execution.md`](fr/sprint_17a_preparation_execution.md) | Sprint 17-A — Préparation de l'exécution France | Le Sprint 17 complet reste conditionnel : `BLOCKED_BROKER` et |
| [`fr/sprint_17b_trading212_demo_lecture_seule.md`](fr/sprint_17b_trading212_demo_lecture_seule.md) | Sprint 17-B — Trading212 Invest DEMO, qualification en lecture seule | HTTP 200, historique inclus. La nouvelle preuve est |
| [`fr/sprint_17c_mapping_et_contrat_trading212.md`](fr/sprint_17c_mapping_et_contrat_trading212.md) | Sprint 17-C — Correspondances et préparation du contrat Trading212 | Une seconde lecture DEMO a confirmé EUR et cinq endpoints accessibles ; |
| [`fr/sprint_17d_reconciliation_simulee.md`](fr/sprint_17d_reconciliation_simulee.md) | Sprint 17-D — Réconciliation synthétique et clôture des accès en lecture | La nouvelle lecture Trading212 Invest **DEMO EUR** réussit sur les six endpoints, |
| [`fr/sprint_17e_journal_persistant_et_reprise.md`](fr/sprint_17e_journal_persistant_et_reprise.md) | Sprint 17-E — Journal persistant et reprise, transport factice exclusivement | `service/fr/trading212_durable_17e.py` ajoute un journal de recherche sur fichiers |
| [`fr/sprint_17f_qualification_protections.md`](fr/sprint_17f_qualification_protections.md) | Sprint 17-F — Qualification des protections et des courses d'exécution | courtier bloquée.** Aucun ordre DEMO/réel envoyé, aucune lecture de clé, aucun |
| [`fr/sprint_17g_decision_capacites_trading212.md`](fr/sprint_17g_decision_capacites_trading212.md) | Sprint 17-G — Décision bornée sur les capacités Trading212 Invest | clôture administrative avec réserves. |
| [`fr/sprint_18_preparation_exploitation.md`](fr/sprint_18_preparation_exploitation.md) | Sprint 18 — Préparation de l'exploitation, clôture avec réserves | La tranche réalisable sans ordre, activation LIVE ni écriture SQL est terminée. |
| [`fr/sprint_5_cloture_2026-10-02.md`](fr/sprint_5_cloture_2026-10-02.md) | Sprint 5 France — clôture technique et décision de gate | Date : 2 octobre 2026. Ce document clôt **l'exécution technique de collecte et de staging** du Sprint 5, mais **pas son gate d'admission au |
| [`fr/sprint_5_exceptions_identite_2026-10-02.md`](fr/sprint_5_exceptions_identite_2026-10-02.md) | Sprint 5 FR — exceptions d'identité prioritaires | État au 2 octobre 2026 : **preuves partielles ; aucun GO canonique global**. Ce document traite les exceptions d'identité et de cycle de vie |
| [`fr/sprint_5_finalisation_go_limite_2018_2026.md`](fr/sprint_5_finalisation_go_limite_2018_2026.md) | Sprint 5 France — finalisation du GO limité 2018–2026 | Date de décision : 3 octobre 2026. |
| [`fr/sprint_5_intervalles_esma_prix_radies_actions_2026-10-02.md`](fr/sprint_5_intervalles_esma_prix_radies_actions_2026-10-02.md) | Sprint 5 FR — intervalles ESMA, prix historiques, radiés, actions sur titres | État au 2 octobre 2026 : **audit en cours ; aucun `GO` canonique**. Ce document complète le sous-ensemble vérifié et la clôture du Sprint 5. |
| [`fr/sprint_5_sous_ensemble_verifie.md`](fr/sprint_5_sous_ensemble_verifie.md) | Sprint 5 France — qualification d'un sous-ensemble limité | Date : 2 octobre 2026. Cette procédure met en œuvre la décision de rechercher un **GO limité à un sous-ensemble vérifié**. Elle n'accorde pa |
| [`fr/sprint_6a_contrat_univers_pit.md`](fr/sprint_6a_contrat_univers_pit.md) | Sprint 6-A France — contrat d’univers PIT | Date de clôture : 3 octobre 2026. Verdict : **`GO_6A_CONTRACT_ONLY`**. |
| [`fr/sprint_6b_historique_liquidite.md`](fr/sprint_6b_historique_liquidite.md) | Sprint 6-B France — historique et liquidité PIT J+1 | Date de clôture : 3 octobre 2026. Verdict : **`GO_6B_TRAINING_UNIVERSE`**. |
| [`fr/sprint_6c_identite_benchmark_secteurs.md`](fr/sprint_6c_identite_benchmark_secteurs.md) | Sprint 6-C France — identités, benchmark de recherche et secteurs | État au 3 octobre 2026 : `GO_6C_RESEARCH_PRICE_ONLY`. L'identité de recherche et le benchmark prix sont construits, versionnés et persistés |
| [`fr/sprint_7a2_profil_prix_fige_par_periode.md`](fr/sprint_7a2_profil_prix_fige_par_periode.md) | Sprint 7-A2 — Profil prix figé et qualification par période | Gel réalisé le 3 octobre 2026, avant toute feature benchmark et avant tout entraînement France. Ce document complète le panel 7-A, sans modi |
| [`fr/sprint_7a_panel_features_price_only.md`](fr/sprint_7a_panel_features_price_only.md) | Sprint 7-A — Dictionnaire et panel France price-only | État au 3 octobre 2026 : **`GO_7A_RESEARCH_PANEL`**. Le panel de recherche a été construit et reconstruit avec le même hash. Aucune cible, a |
| [`fr/sprint_7b_features_relatives_benchmark.md`](fr/sprint_7b_features_relatives_benchmark.md) | Sprint 7-B — Features relatives au benchmark France | Réalisé le 3 octobre 2026. Ce lot enrichit le profil prix figé 7-A2 sans le modifier : **14 features prix + 12 features benchmark = 26 featu |
| [`fr/sprint_8a_labels_et_contrat_evaluation.md`](fr/sprint_8a_labels_et_contrat_evaluation.md) | Sprint 8-A — Labels France et contrat d'évaluation | Réalisé le 3 octobre 2026. **GO limité aux labels bruts de recherche**, pas aux rendements économiques ni à l'entraînement. Ce lot complète |
| [`fr/sprint_8b_revue_chemins_et_support_folds.md`](fr/sprint_8b_revue_chemins_et_support_folds.md) | Sprint 8-B — Revue des chemins extrêmes et support réel des folds | Réalisé le 3 octobre 2026, à la suite des labels Sprint 8-A. **Aucun entraînement, aucune modification de cible, aucun assouplissement des g |
| [`fr/sprint_9a_oracle_h5_pilote.md`](fr/sprint_9a_oracle_h5_pilote.md) | Sprint 9-A — Oracle H5 prix-only : protocole du pilote | Protocole figé avant les premiers fits/test de ce lot, le 3 octobre 2026. Les données et critères de couverture ont déjà été examinés aux Sp |
| [`fr/sprint_planning_integration_marche_francais.md`](fr/sprint_planning_integration_marche_francais.md) | Sprint planning détaillé — intégration du marché français dans α-Trade | État de référence : 1er octobre 2026. Ce document est un **plan de mise en œuvre**, pas le constat que les sprints sont réalisés. Pour l'éta |

## Recherche transverse

| Document | Titre | Description |
|---|---|---|
| [`research/README.md`](research/README.md) | Branches de recherche quantitative | Ces modules produisent des expériences et artefacts. Leur présence dans le dépôt ne signifie pas qu'ils pilotent le live. Toute promotion pa |
| [`research/cascade_selection.md`](research/cascade_selection.md) | Cascade de sélection et modes de ranking | La documentation canonique et détaillée a été regroupée dans |
| [`research/directional_data.md`](research/directional_data.md) | Recherche de données directionnelles | Retour : recherche |
| [`research/global_direction.md`](research/global_direction.md) | Global Direction H20 | Retour : recherche |
| [`research/persistent_dip.md`](research/persistent_dip.md) | Persistent Top10 DIP et filtre live/backtest | Retour : recherche |
| [`research/recherche_vs_production.md`](research/recherche_vs_production.md) | Recherche, backtest et production | Un script de recherche cohérent peut utiliser un lifecycle, un univers ou des |

## Registre documentaire et audit

| Document | Titre | Description |
|---|---|---|
| [`audit/registre_documentaire.md`](audit/registre_documentaire.md) | Registre exhaustif des fichiers documentaires | Classement de tous les fichiers sous doc au 2026-10-10. |

## Risque et portefeuille

| Document | Titre | Description |
|---|---|---|
| [`risk/README.md`](risk/README.md) | Références Risk Management | 1. Contrat ML-first |
| [`risk/capital_sizing_et_fractionnement.md`](risk/capital_sizing_et_fractionnement.md) | Capital, sizing, levier et fractionnement | Le sizing combine capital/equity, risque accepté, distance au stop, volatilité, |
| [`risk/contraintes_portefeuille.md`](risk/contraintes_portefeuille.md) | Contraintes et optimisation du portefeuille | Retour : références Risk |
| [`risk/contrat_ml_first.md`](risk/contrat_ml_first.md) | Contrat ML-first entre prédiction, sélection et risque | Retour : références Risk |
| [`risk/controles_et_audit.md`](risk/controles_et_audit.md) | Contrôles opérationnels, circuit breaker et audit | Retour : références Risk |
| [`risk/sizing_et_levier.md`](risk/sizing_et_levier.md) | Sizing, ATR, Kelly, liquidité et levier | Retour : références Risk |

## Références du code et configuration

| Document | Titre | Description |
|---|---|---|
| [`api/README.md`](api/README.md) | Inventaires API par package | Ces inventaires complètent les guides explicatifs. Ils sont régénérés depuis |
| [`api/alembic.md`](api/alembic.md) | Inventaire API — alembic | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/alembic_cn.md`](api/alembic_cn.md) | Inventaire API — alembic_cn | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/alembic_fr.md`](api/alembic_fr.md) | Inventaire API — alembic_fr | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/analyst_research.md`](api/analyst_research.md) | Inventaire API — analyst_research | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/backtesting.md`](api/backtesting.md) | Inventaire API — backtesting | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/common.md`](api/common.md) | Inventaire API — common | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/core.md`](api/core.md) | Inventaire API — core | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/corporate_actions.md`](api/corporate_actions.md) | Inventaire API — corporate_actions | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/dataIntegrityEngine.md`](api/dataIntegrityEngine.md) | Inventaire API — dataIntegrityEngine | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/database.md`](api/database.md) | Inventaire API — database | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/entrypoints.md`](api/entrypoints.md) | Inventaire API — entrypoints | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/event_sentiment.md`](api/event_sentiment.md) | Inventaire API — event_sentiment | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/execution_engine.md`](api/execution_engine.md) | Inventaire API — execution_engine | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/flows.md`](api/flows.md) | Inventaire API — flows | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/formal.md`](api/formal.md) | Inventaire API — formal | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/ihm.md`](api/ihm.md) | Inventaire API — ihm | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/lineage.md`](api/lineage.md) | Inventaire API — lineage | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/modelFactory.md`](api/modelFactory.md) | Inventaire API — modelFactory | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/reporting.md`](api/reporting.md) | Inventaire API — reporting | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/risk_management.md`](api/risk_management.md) | Inventaire API — risk_management | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/screener.md`](api/screener.md) | Inventaire API — screener | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/scripts.md`](api/scripts.md) | Inventaire API — scripts | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/selector.md`](api/selector.md) | Inventaire API — selector | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/service.md`](api/service.md) | Inventaire API — service | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`api/stabilite_v1_et_deprecation.md`](api/stabilite_v1_et_deprecation.md) | Stabilité de l’API v1 et dépréciation | Cette référence décrit le contrat de compatibilité des façades Python du projet. Les noms explicitement exportés par les `__init__.py` sont |
| [`api/tax.md`](api/tax.md) | Inventaire API — tax | Extraction AST du 2026-10-10 ; aucune importation ni exécution métier. |
| [`reference/batchs_generes.md`](reference/batchs_generes.md) | Catalogues de batchs déclarés — référence générée | Extraction YAML au 2026-10-10, sans importer le service ni interroger Windows/SQL. |
| [`reference/configuration_generee.md`](reference/configuration_generee.md) | Inventaire des clés de configuration | Généré depuis les fichiers du dépôt au 2026-10-10. Valeurs et secrets volontairement omis. |
| [`reference/modules_generes.md`](reference/modules_generes.md) | Couverture statique du code Python | Inventaire au 2026-10-10. Chaque module est localisable dans son inventaire API. |
| [`reference/navigation_generee.md`](reference/navigation_generee.md) | Pages IHM déclarées | Extraction statique au 2026-10-10, depuis `ihm/services/navigation.py`. |
| [`reference/schema_et_migrations_generes.md`](reference/schema_et_migrations_generes.md) | DDL et graphe des migrations présents dans le dépôt | Inventaire statique au 2026-10-10, **pas un schéma déployé**. Aucun SQL exécuté. |

## Signaux et sentiment

| Document | Titre | Description |
|---|---|---|
| [`signals/event_sentiment_reference.md`](signals/event_sentiment_reference.md) | Event Sentiment — référence | Retour : vue signaux |
| [`signals/filtres_persistants.md`](signals/filtres_persistants.md) | Filtres persistants de rang et de prix | Les filtres persistants exigent qu’un état survive plusieurs observations avant |
| [`signals/screener_reference.md`](signals/screener_reference.md) | Stock Screener — référence | Retour : vue signaux |
| [`signals/selection_et_scoring.md`](signals/selection_et_scoring.md) | Sélection, screening et scoring | Le selector définit l’univers/candidats admissibles. Le screener calcule des |
| [`signals/selector_reference.md`](signals/selector_reference.md) | Selector / AlphaScanner — référence | Retour : vue signaux |

## Tests & Vérification

| Document | Titre | Description |
|---|---|---|
| [`mutation_history.md`](mutation_history.md) | Mutation history (auto) | — |

