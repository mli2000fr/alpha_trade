# Contrat selector-driven

## Objet

Ce document fige le contrat **selector-driven** aujourd’hui exposé côté opérateur et consommé par les briques avales `modelFactory`, IHM et `risk_management`.

Il complète :

- `F:\projets\doc\selector.md`
- `F:\projets\doc\selector_pipeline_compatibility.md`
- `F:\projets\doc\modelFactory.md`

L’idée centrale :

1. le `selector` publie un **snapshot courant** dans `stock_scores` ;
2. ce snapshot est **archivé PIT-safe** dans `stock_scores_history` ;
3. l’aval peut soit **filtrer un univers courant**, soit **réutiliser un contexte historique PIT-safe**, soit **tracer la décision finale**.

---

## 1. Données selector persistées

### Snapshot courant — `stock_scores`

Le `selector` enrichit le snapshot courant avec notamment :

- `is_candidate`
- `candidate_rank`
- `trend_score`
- `vcp_score`
- `final_score`
- `raw_final_score`
- `normalized_total_score`
- `normalized_rsi`
- `total_score_neutralized`
- `relative_strength_index_neutralized`
- `trend_vcp_component`
- `total_score_component`
- `rsi_component`
- `atr_pct_20`
- `weekly_trend_score`
- `high_52w_proximity`
- `volatility_ratio`
- `earnings_date`
- `days_to_earnings`
- `earnings_blackout`
- `selector_signal_mode`
- `selection_explanation`

### Historique PIT-safe — `stock_scores_history`

Le snapshot courant est archivé dans `stock_scores_history` avec la clé PIT :

- `snapshot_date`
- `capital_preset_key`
- `symbol`

Le même sous-ensemble selector enrichi est propagé dans cet historique, ce qui permet :

- des features ML PIT-safe ;
- de la relecture as-of côté `risk_management` ;
- de l’audit / IHM.

---

## 2. Trois usages distincts du contrat selector-driven

## 2.1 Filtrage d’univers courant

But : **réduire la liste de symboles traités par le run ML courant** à partir du snapshot `stock_scores` le plus récent.

Paramètres opérateur exposés :

- `selector_universe_signal_modes`
- `selector_universe_max_candidate_rank`
- `selector_universe_exclude_earnings_blackout`

Sémantique :

- `signal_modes` garde uniquement certains `selector_signal_mode` ;
- `max_candidate_rank` garde uniquement `candidate_rank <= N` ;
- `exclude_earnings_blackout` supprime les lignes marquées blackout.

Point important : ce mécanisme agit sur la **liste des symboles**, pas sur les features historiques.

### Politique fail-open

Si le contexte selector courant est indisponible, vide ou partiellement manquant, le run ML :

- **continue** avec l’univers initial ;
- journalise la raison dans le résumé de filtrage.

---

## 2.2 Features selector PIT-safe

But : **injecter l’historique selector dans le dataset ML** sans fuite temporelle.

Source : `stock_scores_history`.

Colonnes actuellement exploitées côté `modelFactory` :

- `trend_score`
- `vcp_score`
- `final_score`
- `raw_final_score`
- `candidate_rank`
- `atr_pct_20`
- `weekly_trend_score`
- `high_52w_proximity`
- `volatility_ratio`
- `earnings_blackout`
- `selector_signal_mode`

Projection features :

- `selector_trend_score`
- `selector_vcp_score`
- `selector_final_score`
- `selector_raw_final_score`
- `selector_candidate_rank`
- `selector_atr_pct_20`
- `selector_weekly_trend_score`
- `selector_high_52w_proximity`
- `selector_volatility_ratio`
- `selector_earnings_blackout`
- `selector_mode_sector_neutralized`

---

## 2.3 Explicabilité opérateur

Le `selector` produit aussi un payload d’explicabilité canonique dérivé de :

- l’identité du candidat ;
- les entrées de score ;
- les composantes du score final ;
- le contexte technique / risque / earnings ;
- le contexte de sélection (`selector_signal_mode`, `selection_explanation`).

Ce payload est réutilisé par :

- le run summary `selector` ;
- l’IHM de résumé ;
- les vues SQL/IHM alimentées depuis `stock_scores`.

---

## 3. Contrat opérateur exposé dans l’IHM

## 3.1 Zone ML Train / ML Predict

Dans `F:\projets\ihm\pages\_execution_center\__init__.py`, l’opérateur dispose de deux familles distinctes de réglages selector-driven.

### A. Features selector PIT-safe

Widget :

- `Inclure les features contexte selector`

Effet CLI :

- `--include-selector-context`

Effet backend :

- charge `stock_scores_history` ;
- fusionne le contexte selector par `(symbol, date)` ;
- enrichit le contrat de features ML.

### B. Filtrage d’univers ML courant

Widgets :

- `selector_signal_mode autorisés`
- `candidate_rank max`
- `Exclure earnings_blackout`

Effet CLI :

- `--selector-universe-signal-modes ...`
- `--selector-universe-max-candidate-rank N`
- `--selector-universe-exclude-earnings-blackout`

Effet backend :

- filtre l’univers courant à partir du snapshot `stock_scores` avant `ml_train` et avant `ml_predict`.

---

## 3.2 Lecture opérateur des artefacts ML

L’IHM ML réaffiche un résumé du contrat selector-driven persistant dans les artefacts :

- `include_selector_context_features`
- `selector_universe_signal_modes`
- `selector_universe_max_candidate_rank`
- `selector_universe_exclude_earnings_blackout`

But : rendre explicite, pour un modèle donné, si le run a été entraîné sur un univers selector-borné et/ou avec des features selector PIT-safe.

---

## 4. Consommation par `modelFactory`

## 4.1 Train

Le train :

1. résout l’univers candidat ;
2. applique si demandé le filtre selector-driven courant depuis `stock_scores` ;
3. charge si demandé le contexte selector PIT-safe depuis `stock_scores_history` ;
4. persiste dans le `run_summary` et dans les artefacts le contrat selector utilisé.

## 4.2 Predict

Le predict :

1. résout la liste de symboles ;
2. applique le même filtre selector-driven courant ;
3. charge les artefacts et exécute l’inférence ;
4. expose le résumé selector-driven dans le `run_summary` ML.

---

## 5. Compatibilité avec `risk_management`

## 5.1 Source consommée

`risk_management` lit les candidats **PIT-safe** depuis `stock_scores_history` via `load_candidates_asof(trade_date)`.

Le module consomme désormais, quand le schéma les expose :

- `candidate_rank`
- `selector_signal_mode`
- `selection_explanation`
- `earnings_blackout`

## 5.2 Sémantique conservée

- le score de sizing / conviction continue d’être calculé à partir de `score_used` et éventuellement `predicted_proba` ;
- le `selector` ne remplace pas le moteur de risque ;
- les champs selector servent de **contexte de décision**, de **tie-breaker stable** et de **traçabilité**.

## 5.3 Effets avals ajoutés

Le stage de décision :

- conserve le `candidate_rank` selector au lieu de l’écraser par un pseudo-rang local ;
- utilise ce rang comme tie-breaker déterministe quand deux convictions sont équivalentes ;
- propage `selector_signal_mode`, `selection_explanation` et `selector_earnings_blackout` jusque dans :
  - `risk_decisions`
  - `portfolio_targets`
  - l’IHM Risk.

## 5.4 Compatibilité schéma

Les écritures risk sont volontairement **tolérantes** :

- si les colonnes selector ont déjà été migrées dans `risk_decisions` / `portfolio_targets`, elles sont remplies ;
- sinon, l’écriture reste compatible et ignore simplement ces colonnes.

Un script de migration dédié est fourni :

- `F:\projets\database\sql\risk\risk_selector_context_upgrade.sql`

---

## 5.5 Impact aval `execution` / post-risk live

Le pipeline live `execution` relit `portfolio_targets` via `execution_engine.db_io.load_portfolio_targets(...)`.

Le contrat aval conserve désormais, quand le schéma les expose :

- `candidate_rank`
- `selector_signal_mode`
- `selection_explanation`
- `selector_earnings_blackout`

Effets concrets :

- ces champs sont propagés dans `ExecutionTarget` ;
- le snapshot figé `execution_targets_snapshot` les persiste pour audit run-scopé ;
- l’IHM Execution peut les réafficher sans retomber sur `portfolio_targets` ;
- le résumé de run `execution` expose aussi une télémétrie de couverture selector (`selector_signal_mode_counts`, `selector_rank_available`, `selector_rank_coverage_pct`, `selector_earnings_blackout_targets`).

Compatibilité :

- les lectures/écritures execution restent tolérantes au schéma courant ;
- si `execution_targets_snapshot` n’a pas encore été migrée, le run live reste compatible et ignore ces colonnes ;
- un script de migration dédié est fourni :
  - `F:\projets\database\sql\execution\execution_selector_context_upgrade.sql`

---

## 5.6 Impact aval `backtesting` / replay

Les bridges backtesting conservent aussi désormais ce contexte selector :

- `backtesting.risk_bridge` le transporte depuis les scores d’entrée vers `CandidateScore` puis vers `PortfolioEntry` ;
- `phase2_risk_signals` réexpose `candidate_rank`, `selector_signal_mode`, `selection_explanation`, `selector_earnings_blackout` ;
- `backtesting.execution_bridge` et `backtesting.execution_replay` propagent ces champs jusque dans `ExecutionTarget` et dans les signaux/replays exportés ;
- `backtesting.simulator.BacktestEngine` les réinjecte dans le `signal_context` des événements/trades quand ils sont présents.

Conclusion :

- hors backtest, le pipeline live `risk_management -> execution` est compatible avec le contrat selector enrichi ;
- côté backtesting/replay, ces champs ne pilotent pas encore le sizing ou l’OMS simulé, mais ils sont désormais préservés et auditables en aval.

---

## 6. Contrat à retenir côté opérateur

### Ce que fait le filtre selector-driven ML

> Il borne l’univers courant traité par `ml_train` / `ml_predict` à partir du snapshot `stock_scores`.

### Ce que font les features selector

> Elles enrichissent le dataset ML avec un contexte historique PIT-safe provenant de `stock_scores_history`.

### Ce que fait `risk_management`

> Il relit le snapshot PIT selector archivé, conserve le rang et le contexte de sélection, puis les propage dans les décisions et le portefeuille cible pour audit opérateur.

---

## 7. État courant

À date du dépôt :

- le contrat selector-driven est câblé de bout en bout côté `selector` → `modelFactory` → IHM ;
- l’étape `risk_management` est compatible avec les nouveaux persistants selector ;
- la compatibilité reste rétroactive grâce aux lectures/écritures tolérantes au schéma courant.

