# Plan de sprint — Oracle Layer (TOP / BOTTOM)

> **⚠️ REFACTOR 2026-08-19** : le modèle **Oracle TOP est renommé Oracle Extreme**
> (cible `oracle_extreme10 = oracle_top10 ∪ oracle_bottom10` = détection de gros
> mouvement H20, PAS la direction — cf. E0/D0/D1/D1d). Le modèle **Oracle BOTTOM est
> retiré** (redondant avec TOP, cf. E0b). Renommages : label `oracle_top10` →
> `oracle_extreme10` (migration DB 0065), `proba_top` → `proba_extreme`, `--target
> top|bottom` supprimé. `oracle_pct_rank`/`oracle_decile` conservés (dérivation
> top/bottom locale dans l'audit). Les sections ci-dessous sont le plan HISTORIQUE.
>
> **Référence** : `doc/ml_oracle.md` (spécification, 2026-08-18)
> **Contexte d'analyse** : `doc/backtest_audit.md` §19 — run `20260817_205031_2a2836d1`
> **Règle cardinale** : l'Oracle est un **TARGET**, jamais une **FEATURE**. **B25 reste intact** pendant toute la 1ʳᵉ expérimentation.
> **Unité d'estimation** : jours-homme (jh) — développeur solo, calendrier ≈ jh.

---

## 0. Synthèse de ma compréhension (points d'ancrage code)

Avant le découpage, voici comment la spec se branche sur le code existant :

| Concept de la spec | Ancrage dans le code | Fichier(s) |
|---|---|---|
| Ranking Global B25 | `global_rank_history` (une ligne par `symbol × date × batch_id`, colonnes `global_rank_3..20`) | `modelFactory/predictor.py::upsert_global_ranks` / `predict_global_rank_history` |
| Cascade top/bottom 10 % | `cascade_select()` : filtre `rank > 1-top_pct` / `rank < top_pct`, score `rank × prob`, **`rank_mode` = "ml" \| "random"` (hook d'ablation déjà présent)** | `modelFactory/predictor.py::cascade_select` / `apply_cascade_to_predictions` |
| CLI backtest cascade | `--cascade-rank-mode`, `--cascade-rank-seed`, `--cascade-batch-id`, `--best-horizon`, `--ml-batch-id`, `--batch-diagnostics-batch-id` | `backtesting/cli/_impl.py` |
| Features PIT Global Model | `compute_features()` + `get_feature_columns()` + rangs cross-sectionnels + sector-neutral | `modelFactory/features.py`, `modelFactory/global_ranking.py` |
| Targets ranking (future return, vol-scaled, winsorizé, sector/factor-neutral) | `_compute_ranking_targets()` | `modelFactory/global_ranking.py` |
| Univers ML par jour | `model_predictions` (run `…_globalrank_synth`) — ~399 sym/jour | audit `scripts/oracle_selection_audit.py` |
| Prix ajustés pour rendements futurs | `stock_bars_daily` (`adj_close`, sinon `close`) | `scripts/oracle_selection_audit.py` |
| Estimators dispo | LightGBM / XGBoost / CatBoost (ranking ET classification) | `modelFactory/global_ranking.py::_build_ranking_estimator`, `tabular_baseline.py`, `lightgbm_baseline.py` |
| Migrations DB | séquence alembic jusqu'à `0063_…` ; pattern de table `global_rank_history` en `0058` | `alembic/versions/` |
| WF backtest (financier) | `run_walk_forward()` / `WalkForwardPlan` (purge/embargo) | `backtesting/walk_forward_engine.py` |
| WF ML (Global Ranking) | `train_global_ranking_wf()` (folds internes) | `modelFactory/global_ranking.py` |

---

## 1. Décisions actées (retour opérateur, 2026-08-18)

1. **Target = brut d'abord, cross-sectionnel.** TOP 10 % = les **~40 meilleurs titres parmi l'univers du jour** (~399), par rendement futur brut `adj_close[D+H]/adj_close[D] − 1`. **Jamais** un seuil de rendement absolu (« > +5 % »). Le target neutralisé (vol-scaled/sector/factor-neutral) sera testé en ablation **après** la 1ʳᵉ expérience.
2. **H20 = horizon canonique, uniquement.** Pas de H10 dans la 1ʳᵉ expérience (simplification). H10 viendra ensuite si H20 valide.
3. **Univers = `global_rank_history`**, avec **vérification bit-for-bit** contre le pool réellement consommé par la cascade (`model_predictions`, run `…_globalrank_synth`). Toute divergence doit être arbitrée avant S1.
4. **Métrique principale = Oracle Top-10 Capture + monotonicité par déciles.** La « forme en U » n'est **pas** la cible : on veut `score élevé → probabilité plus élevée d'être dans le vrai TOP 10 %`.
5. **Oracle TOP = second signal spécialisé, pas un remplaçant de B25.** `adjusted_score = f(global_rank_20, P_top)`, puis TOP 10 % sur `adjusted_score`. B25 reste intouchable.
6. **Anti-leakage non négociable.** Pour chaque observation `feature_date = D`, le modèle n'utilise que l'information connue à D. Le label `oracle_top10(D)` (rendement H20) n'est utilisable pour entraîner/ajuster qu'à partir de `oracle_available_date`.
7. **Discipline OOS.** Aucune calibration de `α`, aucun seuil, aucun hyperparamètre Oracle choisi en regardant l'OOS final 2025-2026. Tout est choisi en WF historique, puis **gelé** avant l'OOS final.
8. **Baselines « sans oracle » de comparaison** (déjà disponibles) :
   - `20260817_211221_da7eb061` — backtest complet **2026** ;
   - `20260817_205031_2a2836d1` — backtest complet **2025-2026**.

---

## 2. Vue d'ensemble des sprints

| # | Sprint | Objectif (lié à la spec) | Estimation |
|---|---|---|---|
| S0 | Fondations & contrat anti-leakage | Migration table + squelette module + tests §27 | 1,0 j |
| S1 | Oracle dataset (`global_oracle_labels`) | Étape 1 — labels H20 2016→2025, univers bit-for-bit | 2,0 j |
| S2 | Audit Oracle reproductible | Étape 2 — reproduire 16.7 % / 8.2 % / déciles | 1,0 j |
| S3 | Oracle TOP Model (second signal) + ablations | Étape 3 — O0/O1/O2, target `oracle_top10` | 3,5 j |
| S4 | Walk-forward causal strict (anti-leakage) | Étape 4 — `oracle_available_date ≤ cutoff` | 2,0 j |
| S5 | Combinaison + calibration | Étape 5 — `adjusted_score = f(rank, P_top)`, α gelé WF | 1,5 j |
| S6 | Backtest complet B25 vs B25+Oracle TOP | Étape 6 — hiérarchie 3 niveaux (ML → ranking → trading) | 2,5 j |
| S7 | Oracle BOTTOM (conditionnel) | Étape 7 — si S6 GO ; asymétrie possible (backtest décide) | 3,0 j |
| S8 | Résiduel / distillation (optionnel) | §25–26 — hors 1ʳᵉ expérimentation | 3,0+ j |

**Total phase 1 (S0→S6)** : **≈ 13,5 jh** (~3 semaines calendaires solo).
**Total avec Oracle BOTTOM (S0→S7)** : **≈ 16,5 jh**.
**Gate principal** : S6 (backtest complet, niveau 3 = trading). S7 ne démarre **que** si le niveau 3 est GO côté LONG.

Dépendances : `S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7` (chaîne linéaire ; S4 peut se préparer en parallèle de S3 côté feature engineering).

---

## 3. Détail des sprints

### S0 — Fondations & contrat anti-leakage *(1,0 j)*

**Objectif** : poser la table, le module et les garde-fous avant tout calcul.

**Livrables**
- Migration `alembic/versions/0064_add_global_oracle_labels.py` :
  - Table `alpha_trade.global_oracle_labels` :
    `prediction_date (Date)`, `symbol (String)`, `batch_id (String 64)`, `horizon (Int)`,
    `future_return (Double)`, `oracle_pct_rank (Double)`, `oracle_decile (Int)`,
    `oracle_top10 (TinyInt)`, `oracle_bottom10 (TinyInt)`,
    `oracle_exit_date (Date)`, `oracle_available_date (Date)`, `created_at`.
  - PK `(prediction_date, symbol, batch_id, horizon)` ; index `(batch_id, prediction_date)`, `(oracle_available_date)`.
- Module `modelFactory/oracle/__init__.py` + `modelFactory/oracle/config.py` (config Oracle dédiée, sans toucher `TrainingConfig`).
- Tests anti-leakage **écrits d'abord** (TDD), inspirés du §27 :
  - T1 `oracle_available_date > prediction_date` ∀ lignes ;
  - T3 aucune feature issue de `D+1` ;
  - T4 `oracle_rank/decile/future_return` jamais dans les features ;
  - T2/T5 stubés (remplis en S4).
- Convention de batch : `batch_id` = `batch_diagnostics.backtest_batch_id` (B25).

**DoD** : migration `alembic upgrade head` OK ; module importable ; 4 tests anti-leakage verts (stubs acceptés pour T2/T5).

---

### S1 — Oracle dataset `global_oracle_labels` *(2,0 j)*

**Objectif** : Étape 1 — pré-calculer les labels Oracle **H20** 2016→2025, univers = univers Global Model **vérifié bit-for-bit**.

**Livrables**
- `modelFactory/oracle/build_labels.py` :
  1. Univers par jour = `global_rank_history` filtré sur `batch_id` ; **contrôle bit-for-bit** contre `model_predictions` (run `…_globalrank_synth`) → test d'égalité des couples `(date, symbol)`.
  2. Prix : `stock_bars_daily` (`adj_close` sinon `close`), pivot + `ffill` (même logique que `scripts/oracle_selection_audit.py`).
  3. `future_return_20 = px[D+20] / px[D] − 1`.
  4. Par date : `oracle_pct_rank` (rank pct intra-date), `oracle_decile`, **`oracle_top10 = 1` si le titre est dans le TOP 10 % cross-sectionnel de l'univers du jour (~40/~399)**, `oracle_bottom10 = 1` si BOTTOM 10 %. **Jamais de seuil de rendement absolu.**
  5. `oracle_exit_date = D + 20` ; `oracle_available_date = exit + 1 jour ouvrés` (calendrier bourse depuis `stock_bars_daily`).
  6. Upsert **idempotent + chunké** (pattern `ON DUPLICATE KEY UPDATE` de `upsert_global_ranks`).
- Backfill 2016→2025 (**H20 uniquement**), rejouable, journalisation du nombre de lignes/dates/symboles.

**DoD** : table remplie ; **test d'univers bit-for-bit vert** ; test T1 vert sur données réelles ; taille dataset ≈ 400 sym × ~250 j × ~9 ans ≈ 900 k lignes.

---

### S2 — Audit Oracle reproductible *(1,0 j)*

**Objectif** : Étape 2 — prouver que la nouvelle infrastructure reproduit les chiffres de l'audit.

**Livrables**
- `modelFactory/oracle/audit.py` : TOP capture, BOTTOM capture, répartition des déciles des trades, courbe rendement/décile, monotonicité (Spearman déciles ↔ rendement), capture ratio.
- Repro exacte sur le run `20260817_205031_2a2836d1` (baseline « sans oracle » 2025-2026) :
  - **H20 longs dans top-10 % = 16.7 %** ; **shorts dans bottom-10 % = 8.2 %** ;
  - déciles H20 identiques au tableau 19.2 (tolérance de flottants).
- Comparaison `global_oracle_labels` vs sortie de `scripts/oracle_selection_audit.py` (golden).
- Vérification croisée sur la baseline « sans oracle » 2026 : `20260817_211221_da7eb061`.

**DoD** : écart < 0.5 pt sur les 4 chiffres du tableau 19.1 ; déciles 19.2 reproduits ; rapport lisible en sortie.

---

### S3 — Oracle TOP Model (second signal) + ablations *(3,5 j)*

**Objectif** : Étape 3 — apprendre `P(vrai TOP 10 % | info à D)` comme **second signal** au-dessus du ranking B25. Il **ne remplace pas** B25.

**Architecture**
```
B25 Global Model → global_rank_20 → ranking initial
        ↓
Oracle TOP Model → P(top10)
        ↓
adjusted_score = f(global_rank_20, P_top)   (voir S5)
        ↓
TOP 10 % sur adjusted_score → cascade H20
```

**Livrables**
- `modelFactory/oracle/dataset.py` : pour chaque `(date, symbol)` :
  - features PIT (réutiliser `compute_features` / `_prepare_global_ranking_frame` + rangs cross-sectionnels + sector-neutral) ;
  - `global_rank_20` historique relu depuis `global_rank_history` (**jamais recalculé** — §28) ;
  - target `oracle_top10` jointe sur `prediction_date` **avec `oracle_available_date` en colonne de garde**.
- `modelFactory/oracle/train.py` : classifier binaire LightGBM (baseline) + XGBoost/CatBoost en challengers (gabarit `_build_ranking_estimator`/`tabular_baseline`).
- **Ablations — question scientifique : « B25 rate-t-il des gagnants parce que son *objectif* est mauvais, ou parce que ses *features* n'ont pas l'information ? »** :
  - **O0** — features **exactes** de B25, **sans** `global_rank_20` → isole l'effet de l'**objectif** (target oracle vs target B25) ;
  - **O1** — O0 + `global_rank_20` + features Oracle spécialisées §7C (accélération momentum, dispersion cross-sectionnelle, distance highs/lows, drawdown récent, interactions momentum×volume) ;
  - **O2** — **seulement** certaines familles : momentum / volume / volatility / market regime (sans le set complet B25) → teste si un set allégé suffit.
- Métriques ML : **Oracle Top-10 Capture** (16.7 % → 20 %+ visé, non garanti), AUC/PR-AUC, **monotonicité par déciles**, importance des features.

**DoD** : O0/O1/O2 entraînés et comparés ; le rapport d'importance répond à la question « objectif vs features » ; capture + monotonicité guident la sélection.

---

### S4 — Walk-forward causal strict (anti-leakage non négociable) *(2,0 j)*

**Objectif** : Étape 4 — pour chaque observation `feature_date = D`, le modèle ne peut utiliser **que** l'information connue à D. Le label `oracle_top10(D)` (rendement H20) n'est utilisable qu'à partir de `oracle_available_date`.

**Livrables**
- `modelFactory/oracle/walk_forward.py` : splitter causal où chaque fold d'entraînement vérifie
  `max(oracle_available_date) ≤ training_cutoff` ; purge + embargo (réutiliser les constantes WF existantes).
- Retrain par fold + prédictions OOS par fold (sur des dates où l'Oracle n'était **pas** encore disponible).
- Persistance des prédictions WF (parquet sous `artifacts/models/oracle/<run_id>/`).
- Tests T2 (cutoff ≥ max available) et T5 (la prod ne lit jamais `oracle_available_date > today`) finalisés.

**DoD** : T2/T5 verts sur données réelles ; aucun fold ne « voit » une ligne Oracle future ; **toute violation de leakage est bloquante**.

---

### S5 — Combinaison + calibration *(1,5 j)*

**Objectif** : Étape 5 — `adjusted_score = f(global_rank_20, P_top)`.

**Livrables**
- `modelFactory/oracle/combine.py` :
  - Baseline : `long_score = global_rank_20` ;
  - V1 : `global_rank_20 × P_top` ;
  - V2 : `α · global_rank_20 + (1−α) · P_top`.
- Calibration : isotonic + Platt + percentile-rank de `P_top` ; version sans calibration en baseline.
- **Choix de `α` et de la calibration uniquement sur folds WF**, puis **gelés** avant l'OOS final ; rapport de sensibilité.

**DoD** : une combinaison retenue sur « capture + monotonicité + stabilité WF » ; justification écrite ; **aucun réglage effectué sur l'OOS final**.

---

### S6 — Backtest complet B25 vs B25 + Oracle TOP *(2,5 j)*

**Objectif** : Étape 6 — la seule preuve qui compte (§19.4, §21), avec une **hiérarchie claire**.

**Livrables**
- Extension `cascade_select` / `apply_cascade_to_predictions` : `rank_mode="oracle"` (ou flag `--cascade-rank-override`) remplaçant le rang par `adjusted_rank` issu de S5, **sans toucher** min_prob, per-symbol, short momentum, coûts.
- Flag CLI `--cascade-rank-mode {ml,random,oracle}` + `--oracle-run-id` dans `backtesting/cli/_impl.py`.
- Backtest **même configuration que le candidat production** : H20 cascade · H20 risk · stop 3.5×ATR · TP min(4×ATR, 13 %) · market entry · P14 · m8 · coûts réels · overlays production · mêmes contraintes de portefeuille.
- Comparaison **mêmes dates** : baselines « sans oracle » `20260817_205031_2a2836d1` (2025-2026) et `20260817_211221_da7eb061` (2026), `random` en placebo.

**Hiérarchie du test (le niveau 3 décide)**
1. **Niveau 1 — capacité ML** : TOP capture Oracle > 16.7 % ?
2. **Niveau 2 — qualité du ranking** : déciles plus monotones (`D1 < D2 < … < D10`) ?
3. **Niveau 3 — trading** : B25 vs B25 + Oracle TOP sur PF / Sharpe / P&L / DD, à **dates, coûts, P14, m8, H20 cascade/risk, TP/stop, contraintes identiques**.

**DoD** : les 3 niveaux évalués explicitement ; **le niveau 3 décide** ; verdict « GO / NO-GO » pour l'Oracle BOTTOM ; aucune amélioration ne dépend d'un réglage fait sur l'OOS final.

---

### S7 — Oracle BOTTOM (conditionnel — démarrer seulement si S6 GO) *(3,0 j)*

**Objectif** : Étape 7 — `P(vrai BOTTOM 10 % | info à D)`, **sans symétrie forcée** avec le TOP.

**Livrables**
- Réplique de S3→S5 pour `oracle_bottom10` (modèle indépendant — §6).
- Combinaison short : `(1 − global_rank_20) × P_bottom` (+ variantes).
- Backtest complet **B25 vs B25 + Oracle TOP + Oracle BOTTOM** (mêmes garde-fous que S6).
- **L'asymétrie est autorisée** : la meilleure architecture finale peut être
  `B25 → Oracle TOP (LONG) + B25 original (SHORT)`, pas forcément `TOP + BOTTOM`.
  **Le backtest décide.** Si le short n'apporte rien (cohérent avec les 8.2 % actuels) : **documenter et ne pas promouvoir le short** — c'est un résultat valide.

**DoD** : verdict short (GO/NO-GO) documenté ; B25 toujours intact.

---

### S8 — Résiduel / distillation (optionnel, hors 1ʳᵉ expérimentation) *(3,0+ j)*

- Residual Model (§25) : `residual = oracle_pct_rank − global_rank_20`.
- Distillation / ranking (§26) : LambdaRank, NDCG.
- **Ne démarrer qu'après validation OOS robuste de S6/S7.**

---

## 4. Critères de réussite (§31) — hiérarchie 3 niveaux

| Niveau | Critère | Exigence |
|---|---|---|
| 1 — ML | Oracle Top-10 Capture | ↑ (16.7 % → 20 %+ visé, non garanti) |
| 2 — Ranking | Monotonicité déciles (`D1 < … < D10`) | ↑ |
| 3 — Trading | PF / Sharpe / P&L / max DD | PF↑ · Sharpe↑ · P&L↑ · DD stable/↓ — **décide** |
| Robustesse | OOS 2025/2026, stress coûts, bootstrap | validés |
| Intégrité | B25 inchangé ; α/seuils/hyperparams gelés avant OOS | aucun réglage sur l'OOS final |

---

## 5. Risques principaux

1. **Sur-ajustement OOS** — mitigation : WF causal strict (S4), α/calibration gelés avant l'OOS, placebo `random` permanent.
2. **Coût du pré-calcul** — ~900 k lignes (H20) ; mitigation : chunking + upsert idempotent, batch_id unique.
3. **Divergence d'univers** `global_rank_history` vs `model_predictions` — mitigation : contrôle **bit-for-bit** en S1, arbitrage documenté en S2.
4. **Définition du target Oracle** — mitigation : **cross-sectionnel sur l'univers du jour** (jamais de seuil de rendement absolu), brut d'abord, neutralisé en ablation.
5. **Gain ML sans gain trading** (capture ↑ mais PF ↓) — mitigation : S6 niveau 3 décide, le §21 prime sur la capture.
6. **Discipline OOS violée** (réglage d'α/seuil/hyperparam sur 2025-2026) — mitigation : tout choix Oracle est WF-only, avec un audit de gel explicite avant l'OOS final.

---

*Fichier : `doc/ml_oracle_sprint.md` — plan opérationnel de `doc/ml_oracle.md`.*
