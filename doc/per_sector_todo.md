# Per-Sector — Dossier de décision pour GPT

> **Date** : 2026-08-15 (mis à jour 2026-08-16 — benchmark gate B41 en production-parity)
> **Objet** : dossier complet (contexte, méthodologie, tests exécutés, résultats chiffrés) pour qu'une IA externe **tranche la suite à donner** à la piste per-sector d'α-Trade.
> **Document complémentaire** : `doc/per_sector.md` (architecture, historique, règles de ré-entrée).

---

## Résumé exécutif

Le per-sector (11 modèles GICS × 5 horizons, target sector-neutre, LightGBM+CatBoost) est en `research-only` depuis 2026-08-05 : **F1 WF ≈ 0.33 (hasard), DirAcc ≈ 50 %**. Un programme de recherche en 3 étapes a été exécuté le 2026-08-15 pour répondre à : **« existe-t-il un ranking intra-sectoriel OOS qui produit un spread long–short net de coûts ? »**

| Phase | Question testée | Verdict |
|---|---|---|
| **0** | Baselines techniques simples (momentum relatif, reversal, mom/vol, blends) | ❌ IC ≈ 0 à négatif partout, aucun spread net positif |
| **0bis** | Données PIT existantes (sentiment, scores screener, fondamentaux en percentiles sectoriels) | ❌ Instables ; seul `short_score` positif en 2025H1 (spread net +211 bps H20) mais négatif en 2019 |
| **5** | Interactions conditionnelles (régime bull/bear/bull_strict × signal, valuation × momentum) | ❌ WF tout ≈ 0 ; holdout bull_strict `short_score` IC +0.05 H20 mais spread net −5 bps |

**Verdict consolidé : aucun alpha intra-sectoriel exploitable net de coûts dans les données actuellement disponibles.**

**Question posée à GPT** (voir « Décision GPT et nouvelle roadmap » en fin de document).

> ✅ **Réponse GPT (2026-08-15)** : **ne pas clôturer le per-sector**, mais sortir de la logique « 11 modèles indépendants + tuning de features ». Tester d'abord les **hypothèses structurelles** : D0 (dispersion/oracle), D2 (Global + résiduel sectoriel), D1 (ablation symbol), D3 (earnings PIT), + 1 expérience hors périmètre (short_score → jambe short du Global Ranking). Détail en fin de document.

---

## Méthodologie du harness (commune aux 3 phases)

- **Univers** : `config/ticket_mid_cap_400.txt` (400 mid-caps), mapping 11 secteurs GICS via `stock_metadata.provider_sector`.
- **Target** : `relative_return_h = future_return_h − médiane_sectorielle(future_return_h, date)`, avec `future_return = close[t+h]/close[t] − 1` (prix ajustés adj_close/close).
- **Métriques** :
  - **IC relatif** = Spearman par date, score vs relative_return → `ic_mean`, `ic_pos_pct` (% dates > 0) ; `ic_abs_mean` = IC vs rendement brut (contrôle d'exposition beta).
  - **Spread** = moyenne relative_return du top quintile − bottom quintile, brut puis **net de coûts** (aller-retour 51 bps/jambe → −102 bps pour le long-short), winsorisation 1 %/99 % intra-date sur le spread uniquement (l'IC reste sur valeurs brutes, rank-based donc robuste).
- **Zones** : WF 2019-01-01 → 2024-06-30 (exclu) ; **holdout gelé** 2024-07-01 → 2025-12-31 (jamais consulté pendant le design des phases).
- **Calibration** : score aléatoire `B0` → IC ≈ 0 dans toutes les périodes et zones → harness valide.
- **Caveats** : forward returns chevauchants entre dates adjacentes (l'IR est optimiste, ne pas conclure dessus — métriques fiables : ic_mean, ic_pos_pct, spread net) ; `short_score`/`trend_score`/sentiment ne couvrent pas toutes les dates (snapshots ~mensuels ou jours à news uniquement → n_dates < n_jours) ; fondamentaux forward-fillés (~48 snapshots/symbole).
- **Scripts** : `scripts/per_sector_baselines.py`, `scripts/per_sector_baselines_signals.py`, `scripts/per_sector_interactions.py`. Rapports complets dans `logs/per_sector_*_2019-01-01_2025-12-31.txt`.

---

## 0. Changement de cadre (préalable à tout)

- [x] **Abandonner la question « quel modèle donne le meilleur F1 ? »** au profit de :
  > **« Peut-on construire un ranking intra-sectoriel OOS qui produit un spread Long–Short net de coûts ? »**
- [x] **F1/DirAcc/MSE deviennent des métriques secondaires** (diagnostic), la métrique primaire devient **IC Spearman relatif par date** + **spread long-short net de coûts**.
- [x] **Décision utilisateur requise** → prise le 2026-08-15 : réouverture de la recherche sous protocole strict (conforme à la règle de ré-entrée de `doc/per_sector.md` §1.2) puis exécution des phases 0/0bis/5.
- [x] **Coûts de référence** (pour tous les calculs de spread net) : commission 1 bps, slippage 2 bps, spread réel médian ~44 bps → aller-retour ≈ **51 bps** ; marge 7.5 %/an, levier 2×.

---

## Phase 0 — Construire le vrai benchmark (P0, avant toute modification de modèle)

Pour chaque **secteur × date × horizon H3/H5/H10/H15/H20**, calculer :
`future_return` (déjà en base) et **`relative_return = future_return − médiane_sectorielle(future_return, date)`** (colonne **à créer** — Action 2.1 de `ml_todo_1.md` jamais réalisée).

Puis tester des baselines simples, en IC relatif par date ET spread long-short net :

| ID | Baseline | Formule |
|---|---|---|
| B0 | Hasard | score aléatoire |
| B1 | Momentum | `mom20`, `mom60`, `mom120` (3 scores) |
| B2 | Reversal | `−ret_5`, `−ret_10` |
| B3 | Momentum × volatilité | `mom20 / vol20` |
| B4 | Momentum relatif | `ret20 − median_sector(ret20)` |
| B5 | Blend multi-horizon relatif | `0.5·rel_mom20 + 0.3·rel_mom60 + 0.2·rel_mom120` |

- [x] Implémenter le calcul de `relative_return` par secteur/date (ajout au dataset per-sector). **Fait : `scripts/per_sector_baselines.py`**
- [x] Implémenter l'évaluation baselines : IC relatif moyen/IR, spread top−bottom quintile avant/après coûts, % folds positifs. **Fait (harness calibré par B0_random ≈ 0)**
- [x] Exécuter B0-B5 sur les folds WF (2019-2024) + holdout gelé. **Fait le 2026-08-15**
- **Question tranchée** : existe-t-il déjà un alpha intra-sectoriel trivial ? → **NON.** Voir verdict ci-dessous.

### Verdict Phase 0 (2026-08-15)

Rapport : `logs/per_sector_baselines_2019-01-01_2025-12-31.txt` — univers 400 mid-caps, zones WF 2019-01 → 2024-06 + holdout gelé 2024-07 → 2025-12, coût aller-retour 51 bps/jambe.

| Signal testé | Verdict (IC relatif par date, tous horizons) |
|---|---|
| B0 hasard | IC ≈ 0 partout → **harness valide** |
| B1 mom20 / B4 rel_mom20 | IC ≈ 0 à **légèrement négatif** sur toutes les périodes (2019, COVID 2020, holdout 2025) → pas d'alpha relatif |
| B2 reversal (rev5/rev10) | IC ≈ 0, pointe marginale +0.04 pendant COVID 2020H1, jamais net de coûts |
| B3 mom20/vol20 | IC ≈ 0 à négatif |
| B5 blend rel (20/60/120) | IC ≈ 0 à −0.05 |
| B1 mom60/120 (2024H2-2025H2) | Seul indice : IC +0.04 à +0.06 en H20, ~70 % dates positives — **trop faible et trop récent pour être exploitable** |

**Conséquence directe :** le F1 ≈ 0.33 du ML per-sector reflète bien **l'absence de signal dans les familles simples** — ce n'est PAS un échec d'apprentissage d'un signal trivial. L'hypothèse « le ML a raté un momentum relatif » est **invalidée** par les données.

**Réorientation :** selon la règle du plan (`si aucun baseline ne bat le hasard → aller directement aux informations nouvelles`), la priorité bascule sur :
1. **Phase 6 — événements PIT** (earnings surprises, révisions analystes, réaction de prix) — levier le plus plausible.
2. **Phase 4 — fondamentaux réellement relatifs** (percentiles sectoriels).
3. **Phase 5 — interactions conditionnelles** (surprise × momentum, valuation × momentum).
4. En parallèle, ajouter le **IC relatif + spread net dans `trainer_sector.py`/`report.py`** pour que tout futur batch soit jugé sur ces métriques.

Les phases 1-3 (refonte target, LambdaRank, features relatives) restent utiles mais **secondaires** : sans source de signal, changer la target ou le modèle ne créera pas d'alpha.

### Verdict Phase 0bis (2026-08-15) — signaux PIT existants

Rapport : `logs/per_sector_baselines_signals_2019-01-01_2025-12-31.txt` — 14 scores (sentiment 1d/5d ± relatif, short_score, normalized_total_score, trend_score ± relatif, percentiles sectoriels PE/ROE/eps_growth/revenue_growth).

| Famille | Résultat chiffré |
|---|---|
| Sentiment net 1d/5d (± relatif) | IC ≈ 0 partout (WF 2019-2024 et holdout) — aucun alpha |
| `short_score` | 2019H1 : IC −0.04/−0.07 · 2024H2 : ≈ 0 · **2025H1 : IC +0.075 (H10) / +0.099 (H15) / +0.097 (H20), spread net +32/+123/+211 bps** · 2025H2 : +0.035/+0.053, net +24/+34 bps (H20) — signe instable |
| `normalized_total_score` | +0.05 en 2024H2 (H15) → **−0.06/−0.08 en 2025H1 (H10-H20)** — instable |
| `trend_score` | +0.04/+0.08 en 2019H1 → **−0.04/−0.10 en 2025H1** — instable |
| Fondamentaux percentiles | PE ≈ 0 puis **négatif 2025H2 (−0.03/−0.04)** ; ROE négatif ; eps_growth +0.02/+0.03 en 2025H1 (66-68 % pos) puis négatif ; revenue_growth +0.07 en 2019H1 sinon ≈ 0 |

**Conclusion :** aucune information PIT existante ne produit un IC relatif **stable** et net de coûts. Le pattern le plus intéressant est `short_score` (négatif en 2019, fortement positif au rebond 2025H1) — cohérent avec la dépendance au régime déjà documentée sur le Global Ranking (oversold high-beta puni en correction Q1 2026).

**Options restantes soumises à GPT :** voir « Options à trancher par GPT » en fin de document.

**Ancrage code** : `modelFactory/model_benchmark.py` (classe `SimpleBaselines` existante à étendre), `modelFactory/dataset.py` (création de `relative_return_h`), évaluation via un nouveau helper réutilisable par les phases suivantes.

### Verdict Phase 5 (2026-08-15) — interactions × régime

Rapport : `logs/per_sector_interactions_2019-01-01_2025-12-31.txt` — segmentation bull/bear/neutre/bull_strict + interactions `X_val_mom`, `X_epsg_mom`, `X_short_mom`.

| Zone | Résultat |
|---|---|
| WF 2019-2024 (tous régimes) | Tout ≈ 0 ou légèrement négatif — aucun signal, aucune interaction |
| Holdout bull_strict (rebond 2025, 255 j) | `short_score` IC +0.03/+0.05 H15/H20 (61-65 % pos) mais **spread net ≈ −5 à −23 bps** — pas rentable |
| Holdout bull_strict | `X_val_mom` IC +0.02/+0.025 (62-67 % pos) mais spread net −46 bps ; le percentile PE est **négatif** (−0.025 : les chers surperforment en 2025) |

**Conclusion : aucun alpha intra-sectoriel exploitable dans les données existantes, même conditionné par régime.** Le signe de `short_score` dérive (≈0 en WF → +0.05 en holdout) sans stabilité entre zones ni profit net. Les leviers « données existantes » sont épuisés : il ne reste que le backfill earnings (données nouvelles) ou la clôture définitive de la piste per-sector comme signal.

**Ancrage code** : `modelFactory/model_benchmark.py` (classe `SimpleBaselines` existante à étendre), `modelFactory/dataset.py` (création de `relative_return_h`), évaluation via un nouveau helper réutilisable par les phases suivantes.

---

## Phases 1 à 7 — pistes NON exécutées (suspendues)

> ⚠️ Ces phases (refonte target, LambdaRank, features relatives, fondamentaux relatifs, interactions, événements, architectures hiérarchiques) proviennent de l'avis GPT initial. **Aucune n'a été exécutée** en tant que telle — seules les baselines correspondantes (phases 0/4/5) ont été testées dans le harness. Règle appliquée : sans source de signal démontrée, changer la target ou le modèle ne crée pas d'alpha ; ces pistes restent conditionnées à l'apparition d'une information nouvelle.

---

## Phase 1 — Refaire la target (5 familles à tester séparément)

La target actuelle = `future_return → vol scaling → winsorize → − médiane sectorielle`. À remplacer/confronter par :

| Famille | Target | Note |
|---|---|---|
| A | `y = future_return_i − median_sector(future_return)` | Relative « brute », sans vol scaling |
| B | `y = percentile_rank(future_return)` intra-secteur/date ∈ [0,1] | L'objectif devient le classement |
| C | `y = (return_i − sector_mean) / sector_std` | Z-score cross-sectionnel |
| D | `y = 2·percentile_rank − 1` ∈ [−1,1] | Rang centré |
| E | **Pairwise ranking** : « A fera-t-il mieux que B ? » (paires intra-secteur/date) → modèle de ranking | Le plus proche de l'objectif économique |

- [ ] Ajouter les flags/targets B, C, D, E au pipeline per-sector (A ≈ T1 déjà testé ; T2/T3 existent mais mal métrisés — re-tester avec les nouvelles métriques, pas F1).
- [ ] Toutes les transformations (z-score, percentile) doivent être **fit train-only par fold** (sauf médiane sectorielle de date, contemporaine et licite).
- [ ] Évaluer chaque famille avec la métrique du §0 (IC relatif + spread net), jamais avec F1 seul.

**Ancrage code** : `modelFactory/dataset.py` (`build_multi_horizon_targets`), `modelFactory/labeling.py`, flags existants `--target-skip-vol-scaling`, `--target-intra-sector-rank`, `--target-ternary-intra-sector` à compléter.

---

## Phase 2 — Passer aux modèles de ranking (pas de classification)

- [ ] **LightGBM LambdaRank** (ou équivalent) avec **`group = secteur × date`** — le modèle apprend l'ordre des titres dans le secteur à chaque date. Métrique **NDCG**.
- [ ] **Pas de classification ternaire** LONG/FLAT/SHORT pour le per-sector (mauvaise abstraction : T3 a déjà montré 72 % flat et surapprentissage).
- [ ] Comparer LambdaRank vs régression continue sur target B/D, **uniquement via IC relatif + spread net**.
- [ ] Attention : les expériences PairLogit globales (B23/B24/B28/B29) ont échoué pour coût O(n²) — limiter le pairwise aux paires intra-secteur/date et borner le nombre de paires.

**Ancrage code** : `modelFactory/global_ranking.py` (LambdaRank déjà branché côté Global), `modelFactory/tabular_baseline.py` / `lightgbm_baseline.py` (étendre au ranking groupé pour le per-sector).

---

## Phase 3 — Features cross-sectionnelles relatives (prix, vol, volume, momentum)

Chaque feature doit répondre à « comment ce titre se comporte **par rapport aux autres titres du secteur aujourd'hui** ? » :

| Famille | Features |
|---|---|
| A. Prix relatifs | `ret5/10/20/60/120 − sector_median(...)`, `sector_percentile(ret20)`, `sector_zscore(ret20)` |
| B. Volatilité relative | `vol20 / sector_median(vol20)`, `ATR20 / sector_median(ATR20)`, `ATR20/price` relatif |
| C. Volume relatif | `volume / avg_volume20`, percentile sectoriel du volume relatif |
| D. Momentum relatif | `mom20/60/120` + leurs rangs sectoriels (`mom20_sector_rank`, ...) |

- [ ] Inventorier ce qui existe déjà dans `modelFactory/cross_sectional.py` (helpers `_sector_neutral_column_name`, `_sector_zscore_column_name`, rangs percentile) — **beaucoup de briques sont déjà là mais étaient neutres/0.5 dans les batchs per-sector historiques** (bug XS corrigé 2026-08-04, jamais re-testé proprement avec les bonnes métriques).
- [ ] Étendre aux relatifs vol/volume, puis **rejouer l'ablation XS ON/OFF avec les nouvelles métriques** (les batchs B13/B33 « XS toxiques » ont été jugés sur IC Global, pas sur spread intra-sectoriel net).

---

## Phase 4 — Fondamentaux **réellement relatifs**

Les fondamentaux absolus ont été testés (B9/B31 : toxiques pour le Global). GPT considère que l'hypothèse intra-sectorielle n'a **pas** été testée :

- [ ] Construire les percentiles sectoriels par date : `PE_sector_percentile`, `ROE_...`, `revenue_growth_...`, `EPS_growth_...`, `debt_...`, marges, FCF.
- [ ] Faire attention au forward-fill trimestriel des fondamentales (staleness) et à la PIT : un percentile sectoriel doit utiliser uniquement les valeurs publiées à la date.
- [ ] Test = 1 expérience : « fondamentaux relatifs ON » vs baseline de la Phase 0, même protocole.

**Ancrage code** : `modelFactory/fundamental_features.py`, `modelFactory/cross_sectional.py`.

---

## Phase 5 — Interactions conditionnelles

- [ ] `momentum relatif × volatilité relative`
- [ ] `earnings growth relatif × momentum relatif`
- [ ] `earnings surprise × momentum`
- [ ] `valuation relative × momentum relatif` (sous-évalué ET momentum positif)

- [ ] Une hypothèse = une expérience ; ne pas empiler les interactions dans un seul batch.

---

## Phase 6 — Événements PIT (le plus gros levier potentiel selon GPT)

- [ ] **Earnings** : `earnings_surprise`, `revenue_surprise`, `EPS_surprise`, `guidance_surprise`, et **`surprise_relative_sector`**.
- [ ] **Révisions analystes** (si les données existent en base) : `EPS_revision_7d/30d/90d`.
- [ ] **Réaction de prix post-earnings** : combiner surprise + retour post-annonce (« excellents résultats mais action −5 % » ≠ « excellents résultats + action +8 % »).
- [ ] **Vérifier d'abord la disponibilité PIT des données** (tables earnings/révisions, dates d'annonce) — c'est une condition bloquante de ré-entrée. Sans données PIT, cette phase est à reporter.

---

## Phase 7 — Architectures hiérarchiques

| Architecture | Principe | Détail |
|---|---|---|
| **Modèle A** | GLOBAL + `sector` catégoriel + features sector-relatives | Partage l'information entre les 400 titres |
| **Modèle B** | Global → prédiction + modèle résiduel sectoriel léger | `final = global + α·sector_residual`, `α ∈ {0.10, 0.25, 0.50, 0.75, 1.0}` |
| **MoE** | `final = w_sector·sector_model + (1−w_sector)·global_model` | `w_sector` **appris/choisi sur validation uniquement, jamais optimisé sur test** |

- [ ] Modèle A vs Modèle B sur protocole identique.
- [ ] MoE en variante, avec la contrainte de non-optimisation de `w_sector` sur le test.

**Ancrage code** : `modelFactory/trainer_sector.py` (`_train_sector_models`), `modelFactory/global_model.py`, orchestrateur.

---

## Ablation de la feature `symbol` (à faire immédiatement)

- [ ] `A0` = sans `symbol`
- [ ] `A1` = `symbol` catégoriel (actuel)
- [ ] `A2` = features sector-relatives, sans `symbol`
- [ ] `A3` = `symbol` + features relatives

Le `symbol` permet potentiellement de mémoriser « XOM est généralement meilleur » — pas du signal généralisable. Décision sur folds WF, jamais sur le holdout.

---

## Nouvelle métrique de champion (remplace `selection_score` ≈ F1)

- [ ] Critère primaire : **IC Spearman relatif par date** (vs `relative_return`).
- [ ] Critère secondaire : **spread long-short net de coûts** (top vs bottom quintile intra-secteur).
- [ ] Robustesse : **% folds positifs** (+ IR de l'IC relatif).
- [ ] Version pondérée si besoin : `score = 50% IC_relatif + 30% spread_net + 20% stabilité`, pénalités turnover/drawdown.
- [ ] Le champion LightGBM vs CatBoost (et LambdaRank) est choisi **sur validation/WF uniquement**.

**Ancrage code** : `modelFactory/trainer_sector.py` (`_persist_sector_metrics`, logique de champion).

---

## Protocole expérimental strict

- [ ] **Train → Validation → Walk-Forward → Frozen Holdout** (jamais de choix sur le holdout).
- [ ] **Frozen holdout à définir une fois** (ex. train jusqu'à 2024-12-31 comme B44, holdout 2025 gelé ; ou 2026 réservé). Une seule consultation par hypothèse confirmée.
- [ ] **Une hypothèse = une expérience** : `S1` relative momentum, `S2` fondamentaux relatifs, `S3` LambdaRank, `S4` target pairwise, `S5` modèle hiérarchique, `S6` earnings surprise. Interdit : `S7 = 38 features + ranking + fondamentaux + macro`.
- [ ] **Pré-registration** de chaque expérience (hypothèse, métrique, seuil de décision) avant de lancer.
- [ ] **Stop/go** : une idée sans IC relatif positivement stable OU sans spread net significatif après coûts est abandonnée — même si un secteur isolé s'améliore.
- [ ] **Levier en dernier** : ne toucher au sizing/levier qu'après un spread relatif OOS démontré. Le levier est la conséquence de l'alpha, pas un moyen de fabriquer de la performance.

---

## Ordre de priorité d'exécution

> ⚠️ **Post-phases 0/0bis/5 (2026-08-15)** : les rangs 1, 2, 5, 6-partiel (fondamentaux) et 10-partiel (macro×régime via les flags ML) ont été testés — tous négatifs. Il ne reste, dans ce tableau, que **6 (earnings PIT, bloqué par les données)** et les pistes de modèle (3, 7, 8, 9) qui sont **suspendues** faute de source de signal. Le tableau est conservé pour l'historique.

| Priorité | Expérience | Potentiel |
|---|---|---|
| 🥇 | Baseline momentum relatif (Phase 0) | ⭐⭐⭐⭐⭐ |
| 🥈 | IC + spread relatif correctement mesurés (§0/Champion) | ⭐⭐⭐⭐⭐ |
| 🥉 | LambdaRank / ranking par secteur×date (Phase 2) | ⭐⭐⭐⭐⭐ |
| 4 | Features prix/volume relatives (Phase 3) | ⭐⭐⭐⭐ |
| 5 | Fondamentaux relatifs (Phase 4) | ⭐⭐⭐⭐ |
| 6 | Earnings / révisions PIT (Phase 6) | ⭐⭐⭐⭐⭐ (si données dispo) |
| 7 | Global + résiduel sectoriel (Phase 7 B) | ⭐⭐⭐⭐⭐ |
| 8 | Mixture Global/Sector (Phase 7 MoE) | ⭐⭐⭐⭐ |
| 9 | Pairwise learning (Phase 1 E) | ⭐⭐⭐⭐ |
| 10 | Macro × secteur × régime | ⭐⭐⭐ |
| 11 | Tuning hyperparamètres | ⭐ |
| 12 | Ajouter encore des features absolues | ⭐ |

---

## Hypothèse directrice

~~Le problème n'est probablement pas « le secteur n'est pas prédictible » mais « on demande au modèle de prédire une magnitude alors que l'objectif est le classement ».~~

**État final (2026-08-15, après phases 0/0bis/5)** : les baselines techniques (IC ≈ 0 à négatif), les données PIT existantes (instables, jamais net de coûts) et les interactions × régime (≈ 0 partout) ne produisent **aucun alpha intra-sectoriel exploitable**. L'hypothèse résiduelle est que l'alpha sectoriel, s'il existe, exige une **information PIT réellement nouvelle** (earnings surprises/révisions) — non testable sans backfill de données. La décision est soumise à GPT dans la section « Options à trancher par GPT ».

---

## Dépendances à vérifier avant de lancer

- [x] `relative_return_h` : colonne absente aujourd'hui (seuls `future_return_h` brut et `target_h` neutralisée existent) — **calculée dans le script Phase 0** ; à intégrer dans `dataset.py` si elle devient une métrique persistée.
- [x] Disponibilité PIT des données earnings/révisions (Phase 6) — inventaire fait le 2026-08-15 : **`stock_earnings_calendar` quasi vide (19 lignes, juin 2026 uniquement)** ; Finnhub ne fournit que le calendrier futur ; **aucune révision analyste** (`eps_estimate_current` 100 % null). Voir « Données disponibles » plus bas.
- [ ] Le cache XS actuel (`cross_sectional.py`) couvre déjà rangs/z-scores sectoriels — inventorier l'existant pour éviter de réécrire.
- [ ] Les métriques IC relatif/spread net par secteur×date ne sont rapportées nulle part (`report.py`, `trainer_sector.py`) — à ajouter avant toute expérience, sinon les résultats ne seront pas mesurables.
- [ ] Rappel historique : `7e4cf8` (F1 0.51, DirAcc 0.70) est antérieur aux correctifs — ne pas l'utiliser comme preuve qu'un signal a déjà existé.
- [x] **Piège rencontré le 2026-08-15** : un `rolling(h)` sur une série `shift(-1)` calcule des rendements PASSÉS, pas futurs (première version du harness donnait des IC fantômes de 0.9 sur le momentum). Toujours valider le harness avec B0_random ≈ 0 **et** un test de cohérence cible/score.

---

## Données disponibles (inventaire 2026-08-15, univers 400)

| Source | Couverture | Contenu | Statut pour la recherche |
|---|---|---|---|
| `stock_bars_daily` | 400 symboles, ≥2016 (718 681 lignes sur 2018-04→2025-12) | OHLCV + adj_close | ✅ base du harness |
| `stock_scores_history` | 399 symboles, 2010→2026-06 | short_score, normalized_total_score, trend_score, final_score... (100 % non-null) | ✅ testé Phase 0bis/5 — instable |
| `ticker_daily_sentiment_features` | 400 symboles, 2015→2026-07 | sentiment net 1d/3d/5d/10d/20d, confiance, news counts | ✅ testé Phase 0bis — nul |
| `stock_fundamentals_daily` | 400 symboles, 2009→2026 (~48 snapshots/symbole, forward-fill) | PE/ROE/croissances... (73-88 % non-null) | ✅ testé Phase 0bis/5 — nul/négatif |
| `stock_earnings_calendar` | **19 lignes, 2026-06 uniquement** | eps/revenue estimate vs actual | ❌ **inutilisable sans backfill** |
| Révisions analystes | **Absentes** (`eps_estimate_current` 100 % null) | — | ❌ |
| `stock_macro_indicators_daily` | VIX/VXN/VIX3M/MOVE | idem pour tous les symboles | ℹ️ déjà testé via ML (0 gain) |

---

## Décision GPT et nouvelle roadmap (2026-08-15)

### Verdict GPT

**Ne pas clôturer le per-sector.** Les phases 0/0bis/5 ont démontré que les données actuelles (prix + indicateurs + fondamentaux) ne contiennent pas de signal intra-sectoriel robuste — mais **pas** qu'aucune information intra-sectorielle exploitable n'existe. Deux hypothèses structurelles restent non testées :
1. **Existe-t-il suffisamment de dispersion économique intra-sectorielle** pour que le ranking soit rentable après 102 bps de coûts ?
2. **Le partage d'information** (architecture Global + résiduel sectoriel) peut-il extraire un alpha marginal que 11 modèles indépendants ne peuvent pas apprendre (~85 titres/secteur = trop peu de cross-sections) ?

### Roadmap D0 → D3

> ✅ **D0 FAIT le 2026-08-15 — verdict : GO.** Voir résultats ci-dessous.

| Phase | Nom | Effort | Question | Go / Stop |
|---|---|---|---|---|
| 🔴 **D0** | Dispersion / Economic Ceiling (oracle) | ~½ j | Combien pouvait-on gagner avec une prédiction PARFAITE ? | Stop si l'oracle lui-même ne produit pas de spread net suffisant |
| 🟠 **D1** | Ablation `symbol` (A0-A5) | ~½ j | Le catégoriel mémorise-t-il des effets individuels non généralisables ? | — |
| 🟡 **D2** | Architecture hiérarchique Global + résiduel sectoriel | ~1 j | « Peux-tu améliorer marginalement le Global Ranking dans ton secteur ? » — `pred = global + α·sector_residual`, α fixé par validation (commencer α = 0.25) | — |
| 🟢 **D3** | Earnings PIT (backfill Finnhub) | 1-2 j | Surprise + réaction de prix + version sector-relative ; event state (surprise brute, surprise z-secteur, percentile, ret post-earnings 1d/3d/5d, reaction_vs_sector, **surprise × réaction**) | Signaux simples d'abord (IC +0.04, spread > 0) avant tout ML |
| ⚪ **S-SHORT-01** (hors périmètre) | short_score → jambe SHORT du Global Ranking | ~½ j | `short = rank < P10 AND short_score < médiane_sectorielle(short_score)` × régimes (all/bull/neutre/bear/bull_strict), 1 règle pré-enregistrée, critères Δspread/Δdrawdown/Δturnover sur WF puis holdout | — |

> ⚠️ Roadmap remplacée par le plan D1→D4 ci-dessous (retour GPT post-D0).

**Ordre de priorité GPT** : D0 ⭐⭐⭐⭐⭐ → D2 ⭐⭐⭐⭐⭐ → D1 ⭐⭐⭐⭐ → D3 ⭐⭐⭐⭐ → S-SHORT-01 ⭐⭐⭐⭐ → pair trading ⭐⭐ (seulement si D0 montre beaucoup de dispersion) → rotation sectorielle ⭐⭐ (projet séparé — le Global Ranking est déjà sector-neutre).

### Verdict D0 (2026-08-15) — GO

Rapport : `logs/per_sector_dispersion_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_dispersion.py`).

**Economic ceiling (oracle = top/bottom quintile PAR le rendement futur, net de 102 bps) :**

| Zone | H3 | H5 | H10 | H15 | H20 |
|---|---|---|---|---|---|
| WF 2019-2024 (pooled) | **+1 570 bps** | +2 303 | +3 855 | +5 356 | **+6 852** |
| Holdout gelé (pooled) | **+735** | +1 000 | +1 505 | +1 900 | **+2 232** |

- **Dispersion** P90−P10 du relative_return : 740→2 034 bps (WF), 666→1 940 bps (holdout) — dans tous les secteurs (Utilities le plus faible : +300→+1 290 bps net d'oracle). Energy est un outlier (oracle net jusqu'à +52 260 bps H20 en WF — outliers non winsorisés) mais la conclusion tient hors Energy.
- **Predictability ceiling inutilisé** : B4 (momentum relatif) = −1 000 à −2 700 bps WF (destructeur), −83 à −109 bps holdout ; B0 ≈ −100 bps (coûts purs) ; short_score −86 à −174 bps WF, −74 à +69 bps holdout. `ceiling_used_pct` = **−40 % à −67 % (WF)** et −4 % à −15 % (holdout) → **0 % du plafond capturé par les signaux existants**.
- **Conclusion : le secteur vaut largement la peine d'être ranké ; le problème est « comment prédire cette dispersion », pas « pas assez de dispersion ». → GO vers D1/D2/D3.**

### Retour GPT post-D3 (2026-08-15) — roadmap D4 → D11

> ⚠️ Remplace le plan D1→D4 (retour GPT post-D0). D0 = GO confirmé (plafond énorme), D3 = STOP (momentum/reversal/event-shock tués). GPT ne ferme PAS le per-sector : la question devient **« quelles caractéristiques observables à t expliquent la dispersion future intra-sectorielle, et peut-on séparer amplitude et direction ? »**

**Expérience prioritaire (avant tout) : oracle direction vs oracle magnitude.** Mesurer si la dispersion est prédictible indépendamment de la direction (|relative_return|) → si oui, architecture 2 étages amplitude → direction. → Implémentée dans `scripts/per_sector_d4_dispersion.py` (volet 1 : `O_mag`, p_extreme).

| Rang | Phase | Contenu | Statut |
|---|---|---|---|
| 🔥🔥🔥🔥🔥 | **D4 — Volatilité / dispersion** | vol20/60/120, ATR relatif secteur, beta individuel/secteur, **idio-vol (résidu régression titre~secteur)**, R² titre/secteur, distance beta, volume relatif, volume shock, amplitude intraday relative, gap frequency, downside/upside vol, dispersion historique — **~16 variables UNE PAR UNE** | **en cours** |
| 🔥🔥🔥🔥 | **D5 — Volume / liquidité relatif** | volume vs avg20/60, volume zscore, dollar volume, turnover, volume relatif au secteur | après D4 |
| 🔥🔥🔥🔥 | **D6 — Fundamentals composites relatifs** | dimensions Quality / Growth / Valuation / Balance sheet + versions relatives + quality×valuation, growth×valuation, quality×momentum — une hypothèse économique par expérience | après |
| 🔥🔥🔥🔥🔥 | **D7 — Earnings PIT** | triplet surprise + réaction + réaction secteur-relative ; `eps_surprise − median_sector` ; surprise × réaction/valuation/quality ; ret post-earnings 1/3/5j | GO si backfill raisonnable |
| 🔥🔥🔥🔥 | **D8 — Global + résiduel sectoriel** | `final = global + α·résiduel`, **α ∈ {0, 0.1, 0.25, 0.5, 0.75, 1} choisi en validation uniquement** (D1-global-relatif prêt = précurseur, commande disponible) | après |
| 🔥🔥🔥🔥 | **D9 — Deux étages amplitude → direction** | Modèle A : P(|rel| élevé) ; Modèle B : direction ; `final = P(extrême) × score directionnel` | après |
| 🔥🔥🔥 | **D10 — LambdaRank** | group = secteur×date, target = future relative return, NDCG ; comparaison stricte Ridge / LGBM reg / LGBM LambdaRank / CatBoost reg | seulement après D4-D9 |
| 🔥🔥 | **D11 — MoE Global/Sector** | w_sector appris en validation uniquement | ensuite |

**Méthode D4** : une variable = un test (jamais d'empilement), H20 uniquement, métriques = IC relatif + spread net 102 bps + **IC magnitude** (Spearman vs |rel|) + **% extrêmes directionnels capturés** (base hasard = 40 %), décision sur WF puis holdout gelé. Seules les familles avec signal passent à la suite.

### Ajustements de méthode (toujours en vigueur)

1. **Métriques de capture corrigées** : `signal_capture = max(signal_spread_net, 0) / oracle_spread_net` et `signal_minus_random = signal_spread_net − B0_spread_net` (remplace `ceiling_used_pct` négatif).
2. **IC par secteur × fold** pendant les phases ML : décomposer l'IC global.
3. **H20 uniquement en premier** (oracle net holdout +2 232 bps, coûts moins destructeurs, moins de bruit) → H10/H15 si positif → H3/H5 en dernier. Réduit le multiple testing.

### Verdict D3 (2026-08-15) — STOP, pas de signal post-événement

Rapport : `logs/per_sector_eventshock_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_eventshock.py`). Événement = |abr1| ≥ 2×MAD intra-date (~23 % des lignes) ; scores continuation (S_abr1/3/5, E_cont) vs reversal (R_abr1/3/5, E_rev).

| Score | WF 2019-2024 | Holdout 2024-2025 | Verdict |
|---|---|---|---|
| Continuation S_abr*/E_cont | IC −0.010 à −0.024 (46-48 % pos) | IC −0.008 à −0.023 | ❌ aucun drift |
| Reversal R_abr*/E_rev | IC +0.010 à +0.022 (52-54 % pos) | IC +0.008 à +0.023 (max 59.8 % pos R_abr5 H20) | ⚠️ effet faible |
| **Spread net reversal** | **−43 à −91 bps** (tous horizons) | **−54 à −91 bps** | ❌ **jamais net de coûts** |
| B0_random | IC ≈ 0, spread ≈ −100 bps | idem | harness valide |

**Conclusion : le reversal post-choc existe statistiquement (IC ~+0.02) mais est ~5× trop faible pour couvrir 102 bps de coûts.** La famille momentum/reversal est définitivement épuisée. → GO vers D1 (Global relatif) / D2 (résiduel sectoriel) / D4 (earnings).

### Verdict D1 (2026-08-15) — POSITIF : le Global relatif marche

Rapport : `logs/per_sector_d1_global_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d1_global.py`). 1 CatBoost global (400 titres, 53 features = Global prod + sector-neutral/zscore + `sector` cat), target = relative_return H20, 11 folds WF + holdout gelé.

| Zone | IC relatif | % dates pos | spread net | signal_minus_random | capture/oracle |
|---|---|---|---|---|---|
| WF 2019-2024 | **+0.030** (IR 0.26) | 57.4 % | **+41 bps** | **+142 bps** | 0.6 % |
| Holdout gelé | **+0.060** (IR 0.57) | **71.0 %** | **+121 bps** | **+229 bps** | **5.4 %** |

- **10 folds sur 11 positifs** (seul fold 5 : −0.026) ; IC par secteur positif dans la plupart des secteurs (Materials/Staples/CommSvcs/Tech dominants, Utilities souvent négatif, HealthCare mixte).
- **Premier résultat positif de toute la recherche per-sector** : le partage des 400 titres (facteur ~10× de cross-sections) était bien le levier structurel. L'hypothèse de GPT est validée.
- Limite : l'IC reste modeste (0.03-0.06) et la capture de l'oracle n'est que 0.6-5.4 % — c'est une base, pas une fin. → alimente D8 (Global + résiduel sectoriel) et D9.

### Verdict D4 (2026-08-15) — magnitude prédictible, direction instable

Rapport : `logs/per_sector_d4_dispersion_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d4_dispersion.py`). 16 variables dispersion/vol/volume une par une, H20, 4 métriques.

**Volet 1 — oracle direction vs magnitude (réponse à la question prioritaire GPT) :** `O_mag = |rel_h20|` capture **100 %** des extrêmes directionnels (p_extreme = 100 % vs 40 % hasard) → l'architecture 2 étages amplitude→direction (D9) est information-théoriquement viable.

**Volet 2 — la magnitude EST prédictible (premier signal stable de toute la recherche) :**

| Signal | mag_ic WF | mag_ic holdout | p_extreme WF/holdout (base 40 %) |
|---|---|---|---|
| **S_idio60** (vol idio 60j, résidu régression titre~secteur) | **0.322** | **0.278** | 60.6 / 55.7 % |
| S_idio20 | 0.282 | 0.228 | 58.5 / 53.3 % |
| S_vol120_rel / S_vol60_rel | 0.230 / 0.223 | 0.195 / 0.179 | 59.3 / 54.6 % |
| S_range20_rel / S_atr_rel / S_disp_rel | 0.23 / 0.22 / 0.20 | 0.19 / 0.18 / 0.15 | ~54-60 % |
| S_r2_60 | **−0.145** | **−0.141** | 30 % (inversé : faible R² → gros moves) |

- **100 % des dates positives** sur WF et holdout pour idio-vol/vol/ATR/range/dispersion → signal **stable entre zones** (le premier de toute la recherche).
- **Direction** : IC ≈ 0 en WF pour toutes les variables ; holdout +0.04/+0.06 (vol60_rel +0.059, 68 % pos, net +77 bps) → **dépendant du régime** (même pattern que short_score 2025), à ne pas traiter comme un alpha stable.
- **Conclusion : la brique magnitude existe (D9 est GO) ; la brique direction reste le D1_pred (IC +0.03/+0.06) ou D5-D7 à trouver.**

### Retour GPT post-D1/D4 (2026-08-15) — GO fort vers D9-A / D8

- **D4 = résultat le plus important** (mag_ic 0.32/0.28, 100 % dates pos, stable) ; **D1 = preuve que l'architecture comptait** ; **D0 = le gâteau est énorme**. La faiblesse actuelle est clairement **la direction, pas l'amplitude**.
- **Nouveau cadre conceptuel : OPPORTUNITY × ALPHA = Trading Score.** `OPPORTUNITY = combien ce titre va diverger du secteur ?` (`E[|relative_return|]`, brique D4) ; `ALPHA = dans quelle direction ?` (brique D1). Ne plus faire « un seul modèle prédit le rendement ».
- **Ordre révisé** : D0 ✅ → D3 ❌ → D4 ✅ → **D9-A 🔥** → **D8 🔥** → D5 (volume → magnitude et direction|extreme) → D6 (quality→magnitude, valuation→direction conditionnelle) → D7 (earnings = la « raison du mouvement ») → D9-B (architecture finale) → D10 LambdaRank (en pause).
- **3 expériences immédiates** :
  1. **D9-A1** : combiner les 2 briques — A0 global seul ; A1 `P_extreme × D1` ; A2 gating `P_extreme > 60/70/80 %` (seuils pré-enregistrés, choix en validation) ; A3 sizing `direction × confidence` (ne change jamais le signe). + analyse par **quintile d'idio_vol60** (Q1-Q5 : mean rel, mean |rel|, P(top), P(bottom)) — test « pur détecteur d'opportunité ». Script : `scripts/per_sector_d9a.py`.
  2. **D8** : `final = global + α·résiduel`, avec **résiduel = rel − global_prediction** (le secteur corrige le Global, il ne réapprend pas les rendements) ; α ∈ {0, 0.1, 0.25, 0.5, 0.75, 1} **choisi sur WF uniquement**, holdout gelé. Script : `scripts/per_sector_d8_residual.py`.
  3. **D9-A2** (après) : `P(|Rrel| élevé)` → sélection **100 % OOS** → direction conditionnelle `P(up|extreme) − P(down|extreme)`.
- **Critères GO (plus exigeants)** : magnitude IC_mag WF **et** holdout > +0.10 + majorité folds (D4 OK) ; direction IC WF > +0.015 & holdout > +0.020 & spread net > 0 & majorité folds ; score final spread net > 0 WF **ET** holdout + ≥4/5 folds + meilleur que Global Ranking seul.
- **Pièges** : magnitude ≠ tradabilité (ne jamais transformer idio-vol en LONG/SHORT direct) ; toute sélection D9-A2 doit être OOS ; α en validation uniquement.
- **Pause** : LambdaRank, tuning, ternary, features absolues, levier.

### Verdict D9-A1 (2026-08-15) — GATING GAGNANT : magnitude x direction marche

Rapport : `logs/per_sector_d9a_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d9a.py`). A0 = D1 seul (reproduit exactement D1 ✓) ; A1 = `P_extreme × D1` ; A2 = gating `P_extreme > 60/70/80 %` (NaN = flat) ; A3 = sizing sans changement de signe.

| Variant | WF IC / net | Holdout IC / net | % pos holdout |
|---|---|---|---|
| A0_global (D1) | +0.030 / **+41 bps** | +0.060 / +121 bps | 71 % |
| A1_mul | +0.026 / +27 | +0.062 / +136 | 74 % |
| **A2_g60** | +0.025 / +45 | **+0.081** / +212 | 80 % |
| **A2_g70** | +0.024 / **+50** | **+0.097** / **+274** | **82 %** |
| **A2_g80** | +0.025 / **+63** | +0.093 / **+292** | 80 % |
| A3_w | +0.028 / +35 | +0.061 / +132 | 72 % |

- **Le gating bat A0 sur WF ET holdout** (critère pré-enregistré ✓) : A2_g70 spread net +50 vs +41 WF et +274 vs +121 holdout — la combinaison des 2 briques fonctionne.
- **Quintiles idio_vol60** : mean rel Q1 −9 → Q5 +102 bps (WF) et −15 → +152 (holdout) ; P(top) Q1 10 % → Q5 30 % → **idio_vol60 n'est PAS un pur détecteur d'opportunité** : il a aussi un tilt directionnel positif (les titres très idiosynchratiques surperforment le secteur, surtout 2025).
- Caveats : gain WF modeste (IC 0.024-0.025 vs 0.030), amplifcation holdout possiblement liée au régime 2025 ; à confirmer par folds et D9-A2.

### Verdict D8 (2026-08-15) — STOP : le résiduel sectoriel n'apporte rien

Rapport : `logs/per_sector_d8_residual_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d8_residual.py`). Résiduel = `rel − global_prediction` (OOF sub-val), α ∈ {0, .1, .25, .5, .75, 1}.

| α | WF net | Holdout net |
|---|---|---|
| **0.00 (global seul)** | **+34 bps** (choisi sur WF) | +113 bps |
| 0.10 | +27 | +124 |
| 0.25 | +16 | +119 |
| 0.50 | −12 | +117 |
| 0.75 | −36 | +102 |
| 1.00 | −51 | +80 |

- **α > 0 dégrade le spread net sur WF de façon monotone** ; le choix WF donne α = 0. Le gain holdout à α = 0.1 (+11 bps) est non significatif.
- **Conclusion : le Global (avec `sector` catégoriel) capture déjà l'information sectorielle — le résiduel n'ajoute rien.** L'hypothèse « le secteur corrige les erreurs du Global » est rejetée. L'architecture finale ne comprendra PAS d'étage résiduel sectoriel.
- Note : le base D8_a000 est légèrement plus faible que D1 (train sur 80 % du fold) — normal, sans conséquence pour le verdict.

### Retour GPT post-D9-A1/D8 (2026-08-15) — D9-A2 priorité absolue

- **D8 : STOP définitif** (α > 0 dégrade WF de façon monotone — ne pas chercher « α = 0.07 »). **D9-A1 : GO conditionnel.** Le risque = transformer un effet réel de sélection en sur-ajustement au régime 2025 — **D9-A2 ne doit PAS devenir une recherche de seuil optimal**.
- **D9-A2 sépare 2 hypothèses** : A = idio_vol détecteur d'amplitude (→ architecture amplitude×direction) ; B = idio_vol tilt directionnel (high-idio-vol montent plus, favorable 2025). Protocole **figé avant de voir les résultats** : extrêmes = top/bottom 20 % intra-date, high = p_ext ≥ 70 %, low = p_ext ≤ 30 %, H20, mêmes coûts, WF puis holdout, aucune ré-optimisation après holdout.
- **Matrice 2×2** (Down extreme / Up extreme × Low idio / High idio) + 3 tests :
  1. **Magnitude pure** : `P(extreme|high) − P(extreme|low)` — stable WF+holdout → idio_vol est vraiment une feature d'amplitude ;
  2. **Direction conditionnelle** : `P(up|extreme,high) − 50 %` (vs low) — positif seulement en 2025 → tilt de régime ;
  3. **Interaction** : IC du D1_pred restreint aux rows high vs low — « quand idio_vol est élevé, D1 distingue-t-il mieux gagnants/perdants ? »
- **Contrôle random-gate obligatoire** : comparer D1+gate 60/70/80 vs D1+**gate aléatoire au même taux de sélection** (vérifier qu'un filtre quelconque gardant 30 % n'améliore pas mécaniquement le spread).
- **Puis M1/M2/M3 OOS** : M1 = `P(extrême) × D1` ; M2 = gating ; M3 = `D1 × (a + b·P(extrême))` avec a,b **choisis en validation uniquement** (la magnitude modifie la confiance, jamais le signe).
- **Ordre** : D9-A2 → M1/M2/M3 → D5 (volume/turnover → **|rel futur|**, autres détecteurs de magnitude) → D6 (dimensions Quality/Growth/Value/Balance, interactions uniquement avec D1) → D7 (earnings, dernier gros levier informationnel). **Pas de LambdaRank maintenant.**
- **Benchmark final** : Global actuel vs D1-global-relatif vs D1+gate vs D1+magnitude+nouvelles features vs earnings-enhanced — mêmes dates/coûts/univers, holdout totalement gelé.
- **Mise en garde GPT** : ne pas appeler +274/+292 bps « alpha robuste » tant que le mécanisme « magnitude élevée → D1 plus fiable » n'est pas démontré **indépendamment du régime 2025**.

### Verdict D9-A2 (2026-08-15) — amplitude réelle, interaction régime-dépendante, gate NON mécanique

Rapport : `logs/per_sector_d9a2_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d9a2.py`). Protocole figé avant résultats (extrêmes top/bottom 20 %, high p≥70 %, low p≤30 %, H20).

**Tests 2×2 :**

| Test | WF | Holdout | Conclusion |
|---|---|---|---|
| T1 magnitude pure : P(extreme|high) − P(extreme|low) | **+32.6 pp** | **+28.0 pp** | ✅ **stable** → idio_vol60 = vraie feature d'amplitude (56.9/53.5 % vs 24.4/25.5 %) |
| T2a dir cond : P(up|extreme,high) − 50 % | −0.4 pp | +3.1 pp | ≈ coin flip sur WF → **pas de vrai tilt directionnel** |
| T3 interaction : IC(D1|high) − IC(D1|low) | **−0.017** (0.024 vs 0.041) | **+0.070** (0.097 vs 0.027) | « D1 plus fiable à haute idio-vol » **vrai seulement en holdout** → mécanisme régime-dépendant |

**Contrôle random-gate (même taux de sélection, seed fixe) :**

| Variant | WF net | Holdout net |
|---|---|---|
| A0 global seul | +41 | +121 |
| A2_g70 (gate idio) | **+50** | **+274** |
| RG_g70 (gate aléatoire) | +35 | +145 |
| A2_g80 / RG_g80 | **+63** / +26 | **+292** / +149 |
| M3_blend (a,b fit WF : 0.75/−0.27) | +42 | +113 |

- **Le gate bat son contrôle aléatoire sur les 2 zones** (+15/+37 bps WF, +129/+143 holdout) → **l'effet n'est PAS mécanique** (une partie du gain holdout est mécanique : RG +145 > A0 +121, mais l'essentiel vient du tri idio-vol).
- **M3 (blending monotone) n'apporte rien** (b<0, ≈ A0) → **M2 (gating) reste la combinaison gagnante**.
- **Conclusion** : amplitude = robuste partout (T1) ; direction conditionnelle = coin flip sur WF (+3 pp holdout) ; interaction D1×idio = positive seulement 2024-2025 → **l'amplification holdout du gating est partiellement liée au régime**, le tri d'amplitude, lui, est structurel. → GO vers D5/D6/D7 et benchmark final vs Global seul.

### Retour GPT post-D9-A2 (2026-08-15) — D5 maintenant, architecture opportunity + ranking

- **D9-A2 = GO pour la brique amplitude uniquement** : T1 (+32.6/+28.0 pp) est le résultat clé — le mécanisme « high idio-vol → plus d'extrêmes » **survit au changement de régime**, plus convaincant que les +274 bps de spread holdout. **Ne plus optimiser idio_vol60** → c'est un « amplitude gate candidate ».
- **D5 = maintenant**, deux volets :
  - **D5-A** : volume/avg20, volume/avg60, volume z-score, dollar volume (+z-score), turnover (proxy dollar-volume), volume relatif au secteur, volume shock → mesurer **uniquement l'amplitude** : `mag_ic vs |rel_H20|` + `P(extreme|high) − P(extreme|low)` (même protocole que D9-A2). **Pas de direction pour commencer.**
  - **D5-B (test le plus important)** : indépendance vs idio_vol60 → `IC(volume, |rel| | idio_vol)` : mag_ic partiel par tercile d'idio-vol (et quintiles de volume à l'intérieur des terciles d'idio). Si le volume apporte une séparation supplémentaire **conditionnellement à idio-vol** → deuxième dimension de magnitude.
- **D6 ensuite** : Quality/Growth/Value/Balance **relatifs → |rel_return|** (les fondamentaux disent peut-être **où les erreurs de pricing seront grandes**, pas qui gagne).
- **D7 = grand test final de DIRECTION** : triplet `surprise + réaction du titre + réaction relative au secteur` (EPS +20 % mais action −8 % ≠ EPS +20 % seul). Earnings = ce qui peut améliorer la direction, le problème que D4 n'a pas résolu.
- **Matrice d'orthogonalité après D5/D6/D7** : Signal × {Magnitude, Direction, Gain vs D1} — **chaque nouvelle famille évaluée conditionnellement à D1 + idio_vol60** (éviter le monstre à 50 features redondantes).
- **Benchmark final à 4+ références** : B0 random · B1 Global actuel · B2 D1-global-relative · B3 D1+gate idio-vol · B4 = B3+D5 · B5 = B3+D6 · B6 = B3+D7 · B7 = meilleur ensemble. Question : **« combien d'alpha marginal chaque brique ajoute-t-elle au Global ? »**
- **Nouvelle qualification** : le per-sector n'est plus « un signal unique » mais une architecture **opportunity detection (amplitude) + directional ranking** — nettement plus solide que « 11 secteurs × 5 modèles ».
- **Statut global** : D0 ✅ · D3 ❌ · D4 ✅ · D1 ✅ · D8 ❌ · D9-A1 🟢 · D9-A2 🟢 (amplitude validée, interaction non validée) · D5 ▶️ · D6 ▶️ · D7 ▶️ · LambdaRank/MoE ⏸️.

### Verdict D5 (2026-08-15) — STOP : le volume ne prédit PAS la magnitude

Rapport : `logs/per_sector_d5_volume_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d5_volume.py`). 8 variables volume (ratios 20/60j, z-scores, dollar volume, versions relatives au secteur), amplitude uniquement (H20).

| Variable | mag_ic WF / holdout | P_ext_diff WF / holdout |
|---|---|---|
| **S_idio60 (référence)** | **0.322 / 0.278** | **+39.1 / +33.9 pp** |
| Toutes les 8 variables volume | **−0.014 à +0.018** (max S_vrz20_rel +0.018) | **−1.8 à +2.8 pp** |

- **Critères pré-enregistrés (mag_ic > +0.10, p_ext_diff > +10 pp) : toutes les variables volume échouent de ~20×.** Le volume/liquidité n'est PAS un détecteur de magnitude.
- **D5-B (indépendance conditionnelle)** : mag_ic partiel par tercile d'idio-vol 0.01-0.04 (max 0.039 holdout) — largement sous le seuil +0.05 → **aucune information additive à idio_vol60**.
- **Conclusion : STOP volume. idio_vol60 reste le SEUL détecteur de magnitude.** → D6 (fondamentaux → amplitude) puis D7 (earnings → direction).

### Verdict D6 (2026-08-15) — STOP : les fondamentaux ne prédisent pas la magnitude

Rapport : `logs/per_sector_d6_fundamentals_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d6_fundamentals.py`). 17 variables (composants + composites Quality/Growth/Valuation/Balance, percentiles sectoriels PIT), amplitude uniquement (H20).

| Variable | mag_ic WF / holdout | P_ext_diff WF / holdout |
|---|---|---|
| **S_idio60 (référence)** | **0.322 / 0.278** | **+39.2 / +33.9 pp** |
| Meilleures fondamentales | F_gross_margin +0.025 / −0.022 · F_revg +0.024 / +0.041 · F_cur_ratio +0.022 / +0.046 | max **+5.0 pp** (current ratio holdout) |
| Quality / Valuation composites | **négatifs** (ROA −0.083/−0.097, net_margin −0.095/−0.110, quality_comp −0.078/−0.109, val_comp −0.042/−0.019) | négatifs (−3 à −13 pp) |

- **Critères (mag_ic > +0.10, p_ext_diff > +10 pp) : tout échoue de 3-10×.** Note économique : quality/valuation ont un mag_ic **négatif** — les titres de qualité/cheap bougent MOINS (cohérent avec le R² inversé de D4), mais l'effet est trop faible pour être un 2e axe.
- **D6-B (décisif)** : mag_ic partiel par tercile d'idio-vol tous < +0.05 (max +0.039) et souvent négatifs → **aucune information additive à idio_vol60**.
- **Conclusion : STOP fondamentaux. idio_vol60 reste l'unique brique magnitude.** → D7 (earnings = dernier levier informationnel, priorité direction).

### Retour GPT post-D5/D6 (2026-08-15) — D7 dernier test de découverte, puis benchmark final

- **Ne pas fermer le per-sector.** Architecture propre émergente : **Global relatif = direction · idio_vol60 = amplitude · Earnings = catalyseur directionnel potentiel**. D5/D6 prouvent que le signal n'est PAS caché dans davantage de features classiques → **arrêter la course aux 50 features**.
- **D7 = dernier gros test de découverte, protocole strict** (earnings comme information directionnelle, PAS une soupe de features) :
  - **D7-A surprise seule** : eps_surprise, revenue_surprise, surprise relative au secteur → `IC(direction) + spread net + P(up|extreme)` post-event **H20** (puis H5/H10).
  - **D7-B surprise + réaction immédiate** : `post_earnings_ret_1d/3d/5d` et versions relatives au secteur, combinaisons **une par une** — « EPS +20 % mais action −7 % » ≠ « EPS +20 % et action +8 % ».
  - **D7-C earnings × idio_vol** : la surprise directionnelle est-elle différente selon le tercile d'idio-vol (forte idio-vol = marché en train de réévaluer) ?
  - **D7-D surprise × Global direction** : la surprise modifie-t-elle la fiabilité du D1_pred ?
  - Ne pas chercher « earnings positif = LONG » mais « **dans quelles conditions la surprise change-t-elle P(mouvement extrême UP vs DOWN) ?** » → `score = P(extrême) × [2·P(up|extrême) − 1]`.
- **Puis D9-B** (pas un gros modèle) : M0 Global seul · M1 Global×gate idio · M2 Global+earnings · M3 Global+idio+earnings · M4 deux étages P(extrême)×[2·P(up|extrême)−1] → répondre « le per-sector a-t-il un alpha économique DISTINCT du Global Ranking, ou est-ce un meilleur filtre du Global ? »
- **Comparaison finale** : Global vs Global+idio gate vs Global+earnings vs Global+idio+earnings — une seule décision à la fin.
- **Pause explicite** : nouvelles features volume/fondamentales/momentum, tuning massif, LambdaRank, MoE, 11 modèles sectoriels, levier, interactions arbitraires.
- **Même si D7 échoue** : D1+idio gate (+50/+63 bps WF, +274/+292 holdout, contrôle random nettement inférieur) devra être vérifié **dans le portefeuille Global réel** (turnover, drawdown, coûts exacts de production).
- ✅ **Backfill earnings implémenté (2026-08-16)** : `stock_earnings_calendar` = 19 lignes avant backfill. **Solution déployée : provider SEC EDGAR** (gratuit, sans clé API) dans l'IHM page Pipeline → bloc « 🗓️ Récupérer le calendrier earnings sur la période » → liste déroulante « Source des données » (**Finnhub par défaut**, switch « SEC EDGAR — réalisés historiques PIT »). Le backfill 2019-2025 des 400 mid-caps se lance depuis l'IHM (mêmes dates/univers que D7). Sémantique SEC : `earnings_date` = date de dépôt 10-Q/10-K/20-F (PIT conservateur), `eps_estimate`/`revenue_estimate` = même trimestre de l'exercice précédent (baseline YoY, pas de consensus analyste), trimestres désagrégés du cumul YTD, entrées comparatives exclues (règle `end`-latest + durée-min, conventions frame Apple/Alcoa opposées). Tags étendus : FPI (20-F, annuel FY uniquement), MLPs (per-unit net of tax), TMHC (override CIK). Script D7 prêt : `scripts/per_sector_d7_earnings.py`. NB : seuls les dépôts US sont couverts ; les symboles sans CIK sont comptés en échec (résumé du run).
- ✅ **Backfill vérifié final (2026-08-16)** : **13 949 lignes SEC, 2015-01 → 2026-08, 397/400 symboles couverts** (médiane 44 lignes/symbole ≈ 4 trimestres/an sur 11 ans ; p10=13). Absents définitifs : YOU/PLNT/RYAN (aucun tag EPS us-gaap dans leurs XBRL — limite de source, 3/400). Caveats de couverture : FPI (LKNCY, BZ, VIPS, XPEV, JOYY, QFIN, MNDY...) = **annuel 20-F uniquement** (pas de 10-Q) ; MLPs (PAA, WES, PAGP) = tags per-unit net of tax ; entrées récentes (SN, WAY, KVYO, SOLV, KGS...) = historique court par nature (IPO/spin-off). Correction YTD validée : AA 2025Q3 = 0.88 EPS / 2.995B rev (trimestriel ✓).

### Verdict D7 (2026-08-16) — STOP définitif : les earnings SEC n'apportent rien au-delà de Global+idio

Rapport : `logs/per_sector_d7_earnings_2019-01-01_2025-12-31.txt` (script `scripts/per_sector_d7_earnings.py`, protocole révisé post-retour GPT : E1 entrée lendemain du dépôt / E2 attente 1/3/5 j ; variables `eps_yoy`/`rev_yoy` = croissance YoY, PAS un consensus ; dépôts SEC ≠ annonces).

| Bloc | WF 2019-2024 | Holdout 2024-2025 | Verdict |
|---|---|---|---|
| D7-A eps_yoy / rev_yoy | +0.001 / −0.034 | −0.004 / −0.016 | ❌ ≈ 0 |
| D7-B yoy relatif secteur | +0.014 / +0.023 | +0.002 / −0.054 | ❌ instable |
| D7-C réactions 1/3/5j | +0.019/+0.013/−0.006 | −0.030/−0.009/0.000 | ❌ flip |
| D7-D 2×2 signe(yoy)×signe(r1rel) | meilleure : yoy−×r+ (+74 bps) | meilleures : ++ (+108), −− (+69) | ❌ aucune cellule stable |
| D7-E × idio terciles | idio t1→t3 : −6→+87 bps ; signe yoy n'ajoute rien (+87 vs +104) | t1→t3 : +15→+177 ; idem (+177 vs +141) | ❌ tout vient d'idio |
| D7-F incremental vs D1 | D1 zone 0.030 → D1 sur événements **0.005** (pire) ; yoy± : −0.014/−0.017 | D1 zone 0.060 → D1 sur événements **0.100** (mieux) ; yoy± : +0.133/+0.074 | ❌ **gain 2025 seulement** |

- **Aucun GO selon les critères pré-enregistrés** ; le test décisif D7-E montre que l'effet disparaît derrière idio_vol60, et D7-F que « D1 plus fiable post-dépôt » est un artefact du régime 2025 (s'inverse en WF).
- **Interprétation honnête** : la croissance YoY des dépôts SEC ne prédit pas la direction — cohérent avec « info pricée entre annonce et dépôt ». La surprise **vs consensus** reste non testée (données payantes).
- **Architecture candidate finale — en attente de validation production-parity** : Global (direction) × idio_vol60 (amplitude/gate) — **sans étage earnings**. Pas de LambdaRank. Le gain harness (+50/+63 bps WF, +274/+292 holdout) n'est PAS encore du P&L : il doit survivre au moteur de production réel (voir protocole FINAL ci-dessous).

### Protocole FINAL — validation production-parity (post-D7, retour GPT 2026-08-16)

**Changement de philosophie : fin de la phase Discovery, début de la phase Validation économique.** Plus AUCUNE nouvelle feature/modèle (ni LambdaRank, ni MoE, ni consensus payant) avant ce benchmark. Le risque n'est plus de rater un alpha, c'est de détruire la découverte en la sur-optimisant.

**3 variantes, pas davantage, dans le moteur de production exact** (mêmes dates/coûts/filtres univers/exclusions/règles de sélection/TP-SL/turnover/sizing/levier/réentrée/contraintes sectorielles/portefeuille simultané) :

| Variante | Définition |
|---|---|
| **F0** | Production Global Ranking (référence) |
| **F1** | Global + **hard gate** : `Global score` si `idio_vol60 percentile > seuil` (seuil figé AVANT holdout, celui choisi sur WF) |
| **F2** | Global + **soft sizing** : `position_size ∝ f(idio_vol60)`, sans changement de signe (contrôle : le gate dur est-il vraiment supérieur ?) |

**Contrôle obligatoire : Random Gate** (même taux de sélection, seed fixe) dans le même backtest final → répond à 3 questions : (A) trader moins de positions aide-t-il mécaniquement ? (Global vs Random) ; (B) le choix par idio-vol apporte-t-il quelque chose ? (Idio vs Random) ; (C) le système améliore-t-il le portefeuille ? (Idio vs Global).

**Règles** : seuil choisi UNIQUEMENT sur WF/validation puis une seule exécution holdout (ne pas choisir 80 % parce qu'il fait +292) ; petite analyse de robustesse autour du seuil sans consulter le holdout pour sélectionner le champion.

**3 scénarios de décision** :
- 🟢 **A — le gain survit** (`Global+X` ; `Global+idio = X+Δ` ; `Random ≈ X`) → **GO production** : amélioration structurelle démontrée.
- 🟠 **B — le gain disparaît** (`idio ≈ Global ± bruit`, `Random ≈ Global`) → **STOP per-sector comme alpha de portefeuille** ; découverte scientifique conservée (idio_vol60 prédit l'amplitude intra-sectorielle mais ne se transforme pas en alpha après contraintes).
- 🔴 **C — le gate dégrade** → **fermeture définitive de la branche per-sector comme composant de trading** ; conserver `idio_vol60` comme feature potentielle du Global (rôle d'amplitude démontré).

**Point d'injection** : moteur de replay production `backtesting/cli/_impl.py` (pipeline screener/selector → `final_score*` → sélection → risk → execution → broker-like → protection → exits → compare-to-live, artifacts `ab_prodparity_*`). Le gate s'applique au niveau sélection (filtre `idio_vol60 percentile > seuil`), sans toucher au modèle Global lui-même.

### Verdict FINAL gate (2026-08-16) — GO conditionnel fort : train 2016-2024, WF 2019-2024, verif 2025-2026

Rapport : `logs/per_sector_final_gate_2019-01-01_2026-08-14.txt` (script `scripts/per_sector_final_gate.py`). **Train 2016-2024** (1 CatBoost D1 sur les 400 titres, target rel_h20), **WF = 2019-2024** (analyse 60/70/80 + random control **d'abord**), **vérification = 2025-2026** (une seule lecture). Multi-horizon H3→H20. Table par symbole : `artifacts/per_sector_cache/final_gate_per_symbol.csv`.

| Variant (H20) | IC WF | spread net WF | IC verif | spread net verif |
|---|---|---|---|---|
| A0_global | 0.031 | +45 bps | 0.060 | +100 bps |
| **A2_g60** | 0.027 | +57 | 0.074 | +157 |
| **A2_g70** | 0.028 | +67 | **0.081** | +189 |
| **A2_g80** | 0.030 | **+86** | 0.071 | **+198** |
| RG_g70 (random, contrôle) | 0.031 | +46 | 0.057 | +103 |
| F2_soft (sizing doux) | 0.030 | +40 | 0.060 | +101 |

- **WF : monotone 60 < 70 < 80 en spread net** (+57/+67/+86) → le gain n'est pas un cherry-pick de seuil ; chaque seuil bat A0 **et** son contrôle aléatoire (+11/+21/+40 bps vs RG).
- **Vérification 2025-2026** : gate > A0 (+57 à +98 bps) et gate > random (+54 à +95 bps) — reproductible.
- **Multi-horizon** : le gate améliore le spread net à **tous les horizons** H3→H20 sur les 2 zones (le plus fort H10-H20 ; WF H10 +7.7 vs −25.0 A0 · H15 +47.8 vs +11.7 ; verif H10 +28.0 vs −1.0 · H15 +94.2 vs +47.7).
- **Seuil gelé : g70** (milieu de bande robuste, ~30 % de l'univers sélectionné, +21 WF / +86 verif vs random, meilleur IC verif 0.081). g80 légèrement meilleur en spread mais IC verif plus bas et sélection plus étroite.
- **Verdict : GO conditionnel fort** — spread net > 0 partout + gain vs random reproductible WF+verif ; seule réserve : IC WF du gate ~0.028 (sous +0.03 strict), l'effet est de sélection (IC ≈ constant, spread net ↑).
- **Table par symbole** : attention aux petits échantillons individuels (tops WF type KGS 26 j, MWA 17 j à 100 % win = non significatif) ; lecture fiable = classement agrégé.
- **Étape suivante** : brancher le gate au moteur de production (F0/F1/F2 + random) — `backtesting/cli/_impl.py`, flag au niveau sélection, modèle Global intact.

### Verdict GPT final (2026-08-16, post-FINAL-gate) — STOP recherche per-sector · GO FINAL-GATE-PROD-PARITY

- **GO intégration `idio_vol60 > P70` comme filtre de sélection du Global Ranking, en production-parity.** P70 gelé (meilleur compromis robustesse/couverture ~30 %/IC verif) ; **P80 conservé comme challenger, pas comme paramètre de production**. Ne pas toucher au levier.
- **Présentation honnête du résultat** : idio_vol60 ne prédit PAS les rendements ; il prédit la **probabilité/amplitude d'un mouvement relatif suffisant pour que le ranking Global soit exploitable** — Global = direction, idio = opportunité/amplitude, position seulement si les deux sont réunies.
- **Branches fermées définitivement** : momentum/reversal, event shock, volume, fondamentaux, earnings SEC, résiduel sectoriel, 11 modèles sectoriels indépendants, LambdaRank, MoE, features « au hasard ».
- **FINAL-GATE-PROD-PARITY** (même moteur de production exact) : **F0** Global actuel · **F1** Global + idio gate P70 · **F2** Global + idio gate P80 (challenger) · **FR** Global + random gate P70. Métriques : CAGR, Sharpe, MaxDD, Calmar, turnover, coûts, nb trades, hit rate, profit factor, exposition moyenne, spread net. Question clé : « les +67/+189 bps du harness survivent-ils au moteur de portefeuille réel ? »
- **Décomposition par terciles d'idio-vol** (low < 30 % / mid 30-70 % / high > 70 %) : rendement relatif moyen, dispersion, taux de bons classements du Global, turnover, coût par trade → « le Global devient-il meilleur en forte dispersion » vs « distribution plus favorable des titres très idio-volatils » ?
- **Conclusion GPT** : « D4 a trouvé la brique structurelle, D9-A2 a montré qu'elle n'est pas un artefact de sélection, D5/D6/D7 ont éliminé les alternatives, le final gate a reproduit le gain 2025-2026 » → le per-sector indépendant n'était pas la bonne architecture ; l'information sectorielle utile apparaît en partageant les 400 titres dans un modèle Global + gate de dispersion idiosyncratique.

### Verdict GPT architecture per-symbol (2026-08-16) — choix (b) + variante F3, F0 immutable

**Question posée à GPT** : « revenir à l'architecture originale hybride — le Global continue de donner le TOP/BOTTOM 10 %, mais les probas viennent des modèles per-symbol réels — est-ce une bonne idée ? »

**Réponse GPT — choix (b), avec variante prudente (c)** :
- **Séparation des trois fonctions** : **Global rank = qui trader ?** (sélection TOP/BOTTOM 10 % + direction + ordre primaire) · **idio_vol60 P70 = quand trader ?** (gate d'opportunité) · **per-symbol = combien engager ?** (sizing/conviction borné, uniquement si information marginale démontrée).
- **Interdiction initiale** : ne pas laisser le per-symbol réordonner les candidats — réordonner détruit ce qui est démontré fonctionnel.
- **F0 = synth rank-derived = champion immutable** : « Aucune nouvelle source de probabilité n'est autorisée à remplacer le Global tant qu'elle n'a pas démontré un gain marginal OOS en production-parity. »
- **Dataset expérimental** : pas les 400 titres — uniquement les **queues TOP/BOTTOM 10 % du Global**. Question : « une fois le Global a identifié les candidats, le per-symbol apporte-t-il de l'information supplémentaire ? »

**Protocole de validation (4 tests, dans chaque queue séparément, H3/H5/H10/H15/H20)** :
- **T1 compétence absolue** : `Spearman(per_symbol_score, rel_return)` dans TOP ; signe inversé dans BOTTOM ; + spread quintile intra-queue.
- **T2 compétence conditionnelle** : IC Global dans la queue vs IC per-symbol dans la queue vs IC résiduel après contrôle du Global ; spread net, hit rate, turnover.
- **T3 alpha résiduel** (test décisif) : `residual = rel_return − f(global_rank)` puis `IC(per_symbol, residual)` par queue → information **orthogonale** au Global (leçon D8 : un IC positif corrélé au Global ne vaut rien).
- **T4 permutation control** : scores per-symbol permutés intra-date/intra-queue ; exiger `F1 réel > F1 permuté` (contrôle l'effet « n'importe quelle modulation intra-queue améliore mécaniquement »).

**A/B moteur si PASS** (F0 = champion de référence, pas une baseline historique) :
- **F0** Global rank-derived (synth) · **F1** Global sélection + probas per-symbol · **F2** blend pré-enregistré (0.75/0.25, 0.90/0.10, 0.50/0.50 — α choisi sur validation seulement, PAS d'α optimisé) · **F3** Global sélection/direction + sizing borné per-symbol (`rank_conviction × bounded(per_symbol_confidence)`, multiplicateur 0.75–1.25, pas de proba absolue) · **FR** score aléatoire (contrôle).
- Si `F3 = Global + per-symbol sizing` fonctionne mais `F1 = probas per-symbol` non → **on garde F3** (information non démontrée ne doit jamais écraser information démontrée — asymétrie Global démontré / per-symbol non démontré).

**Critères GO pré-enregistrés AVANT entraînement** :
1. **Signal** : IC intra-queue > 0, idéalement ≥ +0.03, majorité de folds positifs, présent TOP et/ou BOTTOM.
2. **Incrémental** : `IC(per_symbol, residual_global) > 0` + spread net supplémentaire.
3. **Stabilité** : gain présent WF 2019-2024 **et** verif 2025-2026 **et** H10/H20 minimum. Un +0.10 IC uniquement en 2025 = **STOP** (leçons short_score/D7/gating).
4. **Production-parity** : F0 vs F3 — mêmes dates, coûts, univers, TP/SL, cascade, risque, couverture, turnover ; comparer PnL net, Sharpe, DD, turnover, coûts, nb positions, exposition, stabilité.

**Ordre d'exécution GPT** : STEP 0 smoke test idio P70 prod-parity → STEP 1 train per-symbol proprement → STEP 2 score OOS → STEP 3 queues Global 10 % → STEP 4 IC+spread intra-queue → STEP 5 IC(per-symbol, residual_global) → STEP 6 permutation control → FAIL = abandon per-symbol / PASS = F0-F1-F2-F3 → production-parity → **une seule décision**.
- Ne PAS entraîner de nouveau gros modèle ni toucher au Global avant d'avoir répondu à la question : « après que le Global a fait le gros du travail, le per-symbol sait-il encore distinguer les meilleurs des moins bons candidats dans les queues ? »

### Verdict GPT plan ajusté (2026-08-16, v2) — per-symbol mis de côté · clôture sectorielle d'abord

GPT révise son plan précédent : **ne pas ouvrir la branche per-symbol maintenant**. Clôturer d'abord la question « le Global + composante sectorielle fonctionne-t-il réellement ? » avant « le per-symbol améliore-t-il ? ».

**Plan court (A→E)** :
- **A. Smoke test gate production** : F0 Global actuel · F1 Global + idio P70 · F2 Global + idio P80 · FR Global + random P70 — même moteur `_impl.py`, mêmes coûts, TP/SL, univers. Objectif : le gain du harness survit-il au moteur réel ?
- **B. Ablation `sector` dans le Global** (dernière ablation avant clôture sectorielle) :
  - **G0** = Global actuel (avec sector categorical) vs **G1** = Global identique **sans** sector categorical
  - **G2** = G0 + idio_vol60 P70 vs **G3** = G1 + idio_vol60 P70
  - Pourquoi : D1 montre Global + sector categorical → IC 0.03 WF / 0.06 verif, mais D8 montre résiduel sectoriel = 0 → le secteur sert de **contexte**, pas de second modèle. On doit savoir si l'information sectorielle vient du `sector` catégoriel ou du simple partage des 400 titres.
- **C. Benchmark final F0 / P70 / P80 / random** dans `_impl.py`.
- **D. Décision définitive** sur l'architecture sectorielle.
- **E. Seulement ensuite**, retour éventuel au per-symbol (protocole de validation conservé dans ce document, section précédente).

**Clôtures explicites** :
- **D8 clôturé définitivement** : Global + α résiduel sectoriel → α = 0 → STOP, aucune raison d'y revenir.
- **Plus de nouveaux signaux sectoriels** : pas de 50 nouvelles features, pas de nouvelles combinaisons momentum, pas de tuning massif, pas de LambdaRank, MoE, 11 modèles sectoriels, pairwise ranking.

**Architecture cible** (si l'ablation confirme que sector apporte quelque chose) : Global model (+ sector context) → Global ranking → TOP/BOTTOM → idio_vol60 P70 → gate OK ? NO=flat / YES=production. **Aucun modèle per-sector.** Le secteur devient une feature/context du Global + une composante du calcul `idio_vol60`.

**Per-symbol** : laissé tel quel, branche future, sans poids dans la décision actuelle.

### Benchmark FINAL gate en production-parity — batch B41 (2026-08-16, soir)

**Contexte** : décision utilisateur de pivoter la validation du gate sur **B41** (`model-factory-20260813231851-bb2e76`, features volume P3-5, best_h 15, ic_rank 0.0260) au lieu de B25. B41 = 6 splits WF, train jusqu'à 2023-12-15, val jusqu'à 2024-06-18 → **2025+ est strictement OOS**.

**Correctifs d'infrastructure appliqués (indispensables à la parité)** :
- **Univers pipeline = univers du batch** : `_load_batch_training_universe_scope` lit `model_training_batch.symbols` (400) au lieu de l'univers tradable PIT (~1200) → couverture mesurée contre l'univers réel du modèle.
- **Bug cascade batch** : la cascade lisait `batch_diagnostics.backtest_batch_id` (config = B25) même avec `--ml-batch-id B41` → sélection faite avec les rangs B25/H10 sur des prédictions B41. Fix : flag `--cascade-batch-id` (défaut = config, zéro impact prod).
- **`--batch-diagnostics-batch-id`** : même logique pour les filtres §7 (exclude/prefer, 11 `s7_flat_pathological` propres à chaque batch) → « 100 % B41 ».
- **Seuil couverture 95→90 temporaire** via le flag existant `--min-ml-coverage-ratio 0.90` (2022 : 93.11 % — 42 IPO 2021-22 sans 500 séances d'historique en début de fenêtre). Le preset prod reste à 0.95.
- **Rangs B41 régénérés** 2022-2026 (400 symboles/jour) + synth per-symbol (`model_predictions`, run_id `..._globalrank_synth`, 456 640 lignes). Fix lundis manquants : lookback 500 j (momentum_250 NaN sur sa 250ᵉ barre).
- **IHM** : `BacktestRunOptions` + builder + page backtesting + générateur ml_diagnostics propagent les 3 flags batch (un seul selecteur pilote les 3).

**Protocole 12 runs** (pile pipeline production : phases 2-7, `use-persisted`, coûts canoniques, ATR stop 2.5, TP 3.0 ATR / 7 %, loose 2.0, **max-positions 8**) × 3 fenêtres × 4 bras :

| Fenêtre | Statut |
|---|---|
| 2025 (2025-01-02 → 2025-12-31) | OOS strict |
| oos (2024-07-01 → 2026-05-31) | OOS strict |
| 2022 (2022-01-03 → 2022-12-30) | indicatif (partiellement in-sample) |

| Bras | Sélection | Taux gardé |
|---|---|---|
| F0 off | aucune | 100 % |
| F1 p70 | top 30 % idio_vol60 intra-date | ~30 % |
| F2 p80 | top 20 % idio_vol60 intra-date | ~20 % |
| FR random70 | aléatoire (seed 42) | ~30 % (contrôle placebo, même taille que F1) |

**Résultats (12/12 rc=0)** :

*2025 (OOS strict)* :
| Bras | Retour | Sharpe | DD | Trades | PF |
|---|---|---|---|---|---|
| F0 off | −13.11 % | −0.87 | 16.7 % | 85 | 0.71 |
| F1 p70 | −15.43 % | −1.84 | 17.0 % | 65 | 0.41 |
| F2 p80 | −16.77 % | −1.95 | 18.2 % | 61 | 0.39 |
| FR random | **−7.04 %** | −0.80 | **15.4 %** | 82 | 0.68 |

*OOS 2024-07 → 2026-05* :
| Bras | Retour | Sharpe | DD | Trades | PF |
|---|---|---|---|---|---|
| F0 off | −12.20 % | −0.43 | 20.3 % | 167 | 0.84 |
| **F1 p70** | **−8.85 %** | −0.49 | **17.4 %** | 113 | 0.82 |
| F2 p80 | −9.88 % | −0.56 | 17.9 % | 95 | 0.71 |
| FR random | −11.81 % | −0.46 | 27.2 % | 134 | 0.76 |

*2022 (indicatif)* :
| Bras | Retour | Sharpe | DD | Trades | PF |
|---|---|---|---|---|---|
| F0 off | −14.50 % | −1.71 | 15.5 % | 21 | 0.21 |
| **F1 p70** | **−2.00 %** | −0.61 | **5.4 %** | 6 | 0.68 |
| **F2 p80** | **−1.73 %** | −0.71 | **4.6 %** | 4 | 0.59 |
| FR random | −6.42 % | −1.17 | 8.2 % | 8 | 0.12 |

**Lecture** :
- Critère GPT (F1 > F0 **et** F1 > FR sur la majorité des fenêtres) : **2/3 OK** (oos ✅, 2022 ✅ directionnel mais n=4-21), **2025 ❌** — sur la fenêtre OOS la plus riche en trades (61-85/bras), le gate dégrade de façon monotone avec le seuil et **le random bat F0 ET F1**. Verdict : **MIXTE, pas de GO propre**.
- **Constat plus large et plus important : B41 perd de l'argent sur les 12 bras, toutes fenêtres confondues** — même sans gate (F0 B41 2025 = −13.1 %). Le batch volume-features ne tient pas en conditions production, alors que **B25 en prod reste la référence** (+5.13 % sur 2026 Q1, 4 trades, run validé 15/08). Le problème n°1 n'est plus le gate : c'est B41 lui-même.
- **Réserve méthodologique** : `--max-positions 8` dans la série vs défaut 20 du run prodparity validé → comparabilité limitée (user : « laisse tel quel pour l'instant »). Le résultat 2025 (monotone + random gagnant) est robuste à ce paramètre, pas les niveaux absolus.

**Questions ouvertes pour GPT** :
1. Le gate idio_vol60 a un effet **non stable** (améliore en oos, dégrade en 2025, battu par random) → faut-il un NO-GO définitif du gate, ou un test de robustesse (fenêtres supplémentaires, seeds multiples pour FR) avant clôture ?
2. B41 négatif partout en pile production → quel protocole de promotion de batch (B41 ne doit pas remplacer B25 ; faut-il un gate « batch candidat doit battre le batch prod sur les mêmes fenêtres » ?).

### Protocole de promotion de batch Global Ranking (2026-08-16)

**Leçon fondatrice** : B41 était le **meilleur batch sur papier** (IC 0.0260 vs 0.0241, IR 1.55 vs 1.07, decile spread +50 %, 6/6 splits positifs) et a **échoué en production-parity** (−8.61 % vs +1.93 % sur 2026, négatif partout en 2025). **La promotion n'est PAS un screening** : les métriques WF (2019-2024) ne prédisent pas le P&L OOS. Tout test de production de N batchs à la fois = sélection sur le test = verdict invalide.

**Étape 0 — Screening papier (automatique, tous les batchs)** :
- Métriques lues dans `model_training_batch.metadata_json` (global_ranking) : `ic_rank`, `ic_rank_std`, decile spreads H3-H20, IC par split, `best_horizon`.
- Aucun batch n'est promu sur ces métriques — elles servent uniquement à **désigner UN candidat**.

**Étape 1 — Éligibilité minimale du candidat (pré-enregistrée)** :
- `ic_rank` ≥ champion en place + 0.002 **ET** IR ≥ 1.2 **ET** tous les splits positifs **ET** decile spread du best_horizon ≥ champion × 1.2.
- Un batch qui ne remplit pas ces conditions est **rejeté sans production-parity** (cela élimine mécaniquement ~tous les B1-B40 face à B25).
- Résultat B41 : éligible sur papier → testé → **échoué**.

**Étape 2 — UN seul candidat à la fois** :
- Désigné sur validation uniquement, avant toute lecture OOS. Interdit de tester « le suivant » immédiatement après un échec pour contourner la règle (quarantaine : nouvelle information requise).

**Étape 3 — Production-parity unique (protocole figé)** :
- Fenêtres : **2025 complet** (2025-01-02 → 2025-12-31) et **2026 Q1** (2026-01-02 → 2026-05-31) — les deux OOS strict.
- Flags identiques champion vs candidat (le défaut prod, sans `--max-positions` explicite) :
  - pile pipeline (phases 2-7, `use-persisted`), `--capital-preset-key capital_2001_5000`, `--use-canonical-costs`, ATR stop 2.5, TP 3.0 ATR / 7 %, loose 2.0
  - `--ml-batch-id --cascade-batch-id --batch-diagnostics-batch-id` = batch testé (100 % batch)
  - `--min-ml-coverage-ratio 0.90` (seuil documenté, preset prod intact à 0.95)
- Prérequis données AVANT lancement : rangs `global_rank_history` complets (400 symboles/jour) + synth `model_predictions` du batch — vérifier par SQL, ne jamais lancer un run dont la couverture est < 90 % (ex. B25 2025 = 205/261 jours → gap-fill obligatoire).

**Étape 4 — Critères de promotion** :
- **PROMU** si le candidat bat le champion sur **les deux fenêtres** (retour ET Sharpe ET DD) ; un simple match nul n'est pas une promotion.
- **REJET** si défaite sur au moins une fenêtre → le champion en place est conservé, le candidat est archivé avec son verdict.

**État actuel** : B25 = champion en prod · B41 = candidat testé → **verdict inconclusif** (voir section suivante). Aucun autre batch B1-B42 n'est éligible (tous papier-inférieurs à B41). Infra de test prête et réutilisable en ~30 min par fenêtre.

### Verdict final B25 vs B41 (2026-08-16, nuit) — comparaison production-parity directe

Protocole : F0 (gate off), **sans `--max-positions`** (défaut prod = 20), seuil couverture 0.90, 100 % batch (cascade + §7), pile pipeline complète. Deux fenêtres OOS strict : 2025 complet et 2026-01→05.

| Run | Retour | Sharpe | DD | PnL | Trades | PF |
|---|---|---|---|---|---|---|
| B25 2025 | −11.40 % | −1.02 | 15.5 % | −11 806 $ | 59 | 0.70 |
| **B41 2025** | **−0.70 %** | 0.00 | 11.4 % | −3 263 $ | 49 | 0.89 |
| **B25 2026** | **+1.93 %** | +0.81 | 4.9 % | +1 470 $ | 7 | 1.37 |
| B41 2026 | −8.61 % | −1.37 | 13.0 % | −10 556 $ | 21 | 0.44 |

**Lecture — match nul, pas de victoire B25** :
- **2025 : B41 gagne** (−0.70 % vs −11.40 %, +10.7 pts) ; **2026 : B25 gagne** (+1.93 % vs −8.61 %, +10.5 pts).
- **Total cumulé 2025+2026** : B25 ≈ −10 336 $ · B41 ≈ −13 819 $ → **les deux perdent de l'argent**.
- Échantillons fragiles : B25 2026 = 7 trades (non significatif), B41 2025 = 49 trades (plus crédible).
- **Conclusion corrigée** : aucun batch ne domine ; la promotion est **refusée faute de supériorité démontrée** — et le vrai signal est que **la stratégie Global Ranking ne tient pas en OOS strict 2025+2026, quel que soit le batch**. B25 reste en prod par statu quo (aucun challenger ne le bat sur 2 fenêtres), pas par supériorité démontrée.
- **Sensibilité découverte** : `--max-positions` change tout (B41 2025 : −13.11 % à 8 positions → −0.70 % à 20) → toute comparaison doit figer ce paramètre au défaut prod.

### Critères de fermeture définitive (révisés par GPT)

Ne plus dire « F1 ≈ 0.33 → on ferme ». Fermer seulement si **les trois conditions** sont réunies :
1. **Economic ceiling faible** : l'oracle top/bottom quintile n'offre pas assez de spread net après coûts. **OU**
2. **Ceiling élevé mais aucun signal** (existant ou nouveau : dispersion, hiérarchique, earnings PIT) ne produit un IC stable. **ET**
3. **Aucun gain marginal vs Global Ranking** : même un petit alpha per-sector ne justifie pas sa complexité s'il n'améliore pas le système global.

### Phrase de conclusion corrigée (remplace « il ne reste que le backfill ou la clôture »)

> **« Les données actuellement disponibles ne démontrent aucun alpha intra-sectoriel exploitable. Avant une clôture définitive, deux hypothèses structurelles restent à trancher : (1) existe-t-il suffisamment de dispersion économique intra-sectorielle pour rendre le ranking rentable après coûts ? (2) le partage d'information via une architecture Global + résiduel sectoriel peut-il extraire un alpha marginal que les 11 modèles indépendants ne peuvent pas apprendre ? Le backfill earnings constitue ensuite la dernière source d'information PIT qualitativement nouvelle. »**

---

## Réponses de GPT aux questions ouvertes

1. **Option 1 vs 2** : option 1 (earnings) mais comme **dernier test de découverte** avec go/no-go strict — 60-70 % de probabilité de signal statistiquement détectable, **20-30 % seulement** de spread net OOS exploitable.
2. **short_score 2025H1** : pas un signal démontré, mais assez gros pour **une** expérience ciblée hors per-sector (S-SHORT-01). Question causale : le régime identifié *avant* le trade permet-il de savoir quand short_score est utile ? Sinon = regime fitting.
3. **Angle non testé** : la **dispersion intra-sectorielle** (« le secteur vaut-il la peine d'être ranké ? ») — d'où D0, incluant le **predictability ceiling** : oracle spread vs naive baseline vs meilleur signal existant vs ML.
4. **Pair trading** : après earnings et dispersion ; nécessite une hypothèse de mean-reversion des écarts entre pairs économiquement similaires (secteur + industry + beta + taille proches). **Rotation sectorielle** : projet séparé.

---

## Références

| Document | Chemin |
|---|---|
| Contexte per-sector complet | `doc/per_sector.md` |
| Plan d'action ML 1 (phases/actions d'origine) | `prompt/ml/ml_todo_1.md` |
| Journal de recherche | `doc/ml_todo.md` |
| Architecture du module | `doc/ml/module_model_factory.md` (§5) |
| Flags & features | `doc/ml/features_ml.md` |
| Analyse OOS Global (contexte 2026) | `doc/ml/analyse_oos.txt` |
