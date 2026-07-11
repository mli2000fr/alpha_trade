# Refactor ML-First — Suppression du chemin critique `candidate -> ML`

**Statut :** Plan détaillé audité sur le code — Sprints 0 et 1 terminés; Sprints 2 et 3 en cours
**Date :** 2026-07-11  
**Auteur :** Session Copilot  
**Fichier :** `prompt/refactor_ml.md`

---

## 1. Objectif réel du refactor

Le but n'est pas seulement de "supprimer `is_candidate`" dans la base.

Le vrai objectif est plus précis :

1. Le **point d'entrée de la sélection** doit devenir la prédiction ML.
2. Le **score technique** doit cesser d'être le mécanisme qui définit l'univers servi au ML.
3. Les filtres screener/selector doivent devenir des **contraintes de tradabilité / garde-fous**, pas le moteur principal du ranking.
4. La suppression physique de `is_candidate` dans la DB ne doit intervenir **qu'après** migration des consommateurs runtime, batch, IHM, diagnostics et tests.

Autrement dit :

```text
Aujourd'hui : score-driven avec ML attaché au score
Demain     : ML-driven avec score utilisé en veto / contexte / diagnostic
```

---

## 2. État actuel vérifié dans le code

Le code source confirme que l'architecture est encore **candidate-first** à plusieurs niveaux.

### 2.1 Backtest / risk runtime

- `risk_management/db_io.py`
  - `load_candidates_asof()` lit `stock_scores_history` avec `AND s.is_candidate = 1`.
  - Le moteur risk reçoit donc déjà un univers tronqué avant toute logique ML.

- `backtesting/resilience.py`
  - `_expected_symbol_dates(scores_df)` déduit les paires attendues `(symbol, trade_date)` depuis `scores_df`.
  - Donc même si `model_predictions` contient plus de symboles, le runtime ML ne considère comme "attendus" que les symboles présents dans les scores.

- `backtesting/signal_replay.py`
  - `replay_signals(scores_df, predictions_df, ...)` construit d'abord le DataFrame depuis `scores_df`, puis merge `predictions_df` dessus.
  - La prédiction ML n'est pas la source primaire des signaux.

- `backtesting/cli/_impl.py`
  - Le backtest charge bien les prédictions ML, mais le chemin downstream reste score-first.
  - Le flag `filter_candidates_without_ml` lui-même exprime encore le monde comme "candidats filtrés par présence ML".

### 2.2 Training / predict ML

- `ihm/services/pipeline_runner.py`
  - Les defaults IHM sont encore `ml_train_symbol_source = "candidates"` et `ml_predict_symbol_source = "candidates"`.
  - L'IHM continue donc à piloter le ML comme un sous-système branché sur l'univers selector.

- `modelFactory/cli.py`
  - Le train/predict charge les symboles via `load_symbols_for_source(..., "candidates")` par défaut.
  - Les filtres `--selector-universe-signal-modes`, `--selector-universe-max-candidate-rank` et `--selector-universe-exclude-earnings-blackout` restent actifs.

- `modelFactory/db_registry.py`
  - `filter_symbols_by_selector_context()` applique encore `selector_signal_mode`, `candidate_rank`, `earnings_blackout` sur l'univers ML.
  - `load_candidate_symbols()` et `load_candidate_selector_context()` sont encore des primitives centrales.

- `modelFactory/predictor.py`
  - Pour les features cross-sectionnelles, `load_candidate_symbols(engine)` reste utilisé comme univers de référence.
  - Donc même un modèle global peut rester branché à un univers réduit si rien n'est changé.

### 2.3 DB et snapshots

- `database/sql/stock/stock_scores_history.sql`
  - Le snapshot PIT stocke `is_candidate`, `candidate_rank`, `selector_signal_mode`, `final_score`, `final_score_sentiment`, `short_score`, `spread_bps`, `market_cap`, `earnings_blackout`, `atr_pct_20`, etc.
  - Mais `screener/stock_screener.py` persiste seulement `final_scores`, puis `screener/db_io.py` purge de `stock_scores` les symboles absents. Ce n'est donc **pas** un snapshot de tout l'univers actif : les titres rejetés pendant les filtres précoces n'y figurent pas.
  - Conclusion : ces colonnes restent utiles comme contexte/veto pour les lignes présentes, mais elles ne suffisent pas à définir l'univers ML-first historique.

- `database/sql/ml/model_predictions.sql`
  - La table stocke déjà `predicted_proba`, `predicted_side`, `proba_long`, `proba_flat`, `proba_short`, `selected_model`, `run_id`.
  - Elle ne stocke pas de rang, mais le ranking peut être calculé en mémoire au runtime. Ce n'est pas un besoin de schéma bloquant.

- `modelFactory/db_registry.py`
  - `load_stock_bars_daily_symbols()` retourne actuellement tous les symboles présents dans les barres, sans appliquer `stock_metadata.status`, `stock_metadata.tradable`, `asset_class`, l'historique minimum, ni une sémantique PIT.
  - `symbol_source="stock-bars-daily"` ne peut donc pas devenir à lui seul l'univers nominal ML-first.

### 2.4 Screener / selector / services annexes

- `screener/pipeline.py`
  - Le screener ne marque pas lui-même les candidats finaux, mais il reste conçu autour d'une sortie intermédiaire destinée au selector.

- `database/stock_scores.py`, `database/repositories/scores.py`, `event_sentiment/db_io.py`
  - Plusieurs composants lisent encore explicitement les "candidate symbols" via `is_candidate = 1`.

- `risk_management/models.py`
  - Les structures métier s'appellent encore `CandidateScore`, `EnrichedCandidate`, etc.
  - Ce renommage est souhaitable à terme, mais ce n'est **pas** le premier levier fonctionnel.

### Conclusion d'audit

La dépendance à `candidate` n'est pas seulement une colonne SQL. Elle existe dans :

1. le chargement PIT des scores,
2. la définition de l'univers attendu côté ML,
3. le signal replay,
4. le training/predict ML,
5. les features cross-sectionnelles,
6. l'IHM pipeline,
7. les services satellites sentiment / diagnostics / fidelity.

Le plan de refactor doit donc faire deux choses dans cet ordre :

1. définir et persister un univers de sélection PIT complet,
2. découpler ensuite le flux runtime et ML de `scores_df` et de `symbol_source=candidates`.

La suppression physique de `is_candidate` reste une étape finale.

---

## 3. Ce qui doit changer fonctionnellement

### 3.1 Nouveau flux cible

```text
Univers tradable PIT
   ↓
Prédictions ML sur cet univers
   ↓
Filtre de tradabilité / veto objectif
   ↓
Classement séparé LONG / SHORT
   ↓
Veto score technique / veto événements / veto exécution
   ↓
Sizing / overlays / exécution
```

### 3.2 Ce qui ne doit plus être vrai

Les phrases suivantes doivent devenir fausses dans le code final :

1. "Le ML reçoit l'univers des candidats selector."
2. "Les prédictions attendues sont celles des symboles présents dans `scores_df`."
3. "Le backtest reconstruit les signaux depuis les scores puis enrichit avec le ML."
4. "L'IHM train/predict ML part par défaut de `candidates`."

### 3.3 Définition pratique de l'univers tradable

Le plan initial disait d'ajouter tout de suite `is_tradable` en DB. Ce n'est pas la meilleure première étape.

Les tables actuelles ne fournissent pas encore un univers PIT complet :

1. `stock_metadata` est un état courant et ne suffit pas à rejouer un univers historique.
2. `stock_bars_daily` couvre les symboles, mais `load_stock_bars_daily_symbols()` n'applique aujourd'hui ni statut actif/tradable, ni asset class, ni historique minimum.
3. `stock_scores_history` ne contient que les survivants du screener, pas les titres rejetés en amont.

Le refactor doit donc créer un **contrat d'univers PIT persistant**. Recommandation : une table dédiée `tradable_universe_history` plutôt que de surcharger `stock_scores_history`.

Clé logique du snapshot :

```text
(universe_run_id, symbol)
```

`universe_run_id` référence un run qui porte `snapshot_date` et `capital_preset_key`; cela conserve les reruns, tout en désignant un seul run canonique pour chaque couple date/preset.

Champs minimaux :

1. `is_tradable` et `tradability_reason_code`,
2. état de données (`history_days`, `bars_available`, `data_source`),
3. critères objectifs (`close_price`, `adv_usd`, `spread_bps`, `market_cap`, `atr_pct_20`, `earnings_blackout`, anomalies),
4. provenance (`config_fingerprint`, `created_at`).

Le selector conserve `final_score` / `short_score` comme contexte et veto. Il ne décide plus si un symbole existe dans l'univers de sélection.

### 3.4 Séparer tradabilité et signal technique

Le code actuel mélange des contraintes objectives et des signaux de stratégie dans le screener. Cette séparation doit devenir explicite :

**Tradabilité objective** : statut actif, asset class US equity, barres disponibles, historique minimum, prix, ADV, spread, market cap, blackout earnings, anomalies et qualité des données.

**Signal technique** : force relative, position dans le range historique, trend, VCP, RSI, proximité du plus haut 52 semaines, `final_score` et `short_score`.

Un mauvais signal technique ne rend pas un titre non tradable. Le nouveau pipeline doit donc :

1. construire l'univers PIT avec les contraintes objectives uniquement;
2. calculer les scores techniques pour **tous les symboles tradables**, pas seulement un Top-N;
3. utiliser ces scores comme features ML, vetos ou diagnostics après la prédiction.

### 3.5 Contrat directionnel ML

Le cutover cible le modèle ternaire déjà supporté par `model_predictions` :

1. `predicted_side` détermine `long`, `short` ou `flat`;
2. `proba_long` classe les longs;
3. `proba_short` classe les shorts;
4. `flat` n'est jamais sélectionnable;
5. `short_score` ne détermine plus le côté, il peut seulement agir comme veto technique short;
6. une prédiction binaire ou incomplète n'est pas transformée silencieusement en signal : les artefacts doivent être réentraînés en ternaire avant le cutover.

Il n'existe plus de fallback `score-only` lorsqu'une prédiction manque. La ligne est non sélectionnable et contribue au diagnostic de couverture ML.

### 3.6 Contrat de capacité portefeuille

Le code actuel combine `max_positions` total et `short_max_positions`. Le refactor doit conserver une limite totale unique et ajouter des plafonds par côté :

1. `max_positions` reste le plafond dur total long + short;
2. `max_long_positions` borne les positions longues;
3. `max_short_positions` borne les positions short;
4. le ranking ML est séparé par côté, mais le `PortfolioBuilder` arrête les ouvertures dès que `max_positions` est atteint;
5. les overlays régime peuvent réduire dynamiquement chacun de ces plafonds, jamais augmenter le plafond total.

Pour `capital_2001_5000`, le preset doit donc définir explicitement la répartition compatible avec quatre positions totales; il ne faut pas interpréter `max_positions=4` comme 4 longs + 4 shorts.

---

## 4. Corrections au plan initial

### 4.1 Ce qui est conservé

Les points du plan initial qui restent bons :

1. ML doit devenir le moteur principal.
2. Ranking séparé long / short.
3. Le score technique devient un garde-fou et non le maître du classement.
4. L'impact DB et IHM est réel.
5. `is_candidate` doit être retiré du flux, des APIs et du schéma actif dans le cutover ML-first.

### 4.2 Ce qui doit être corrigé

#### A. Les migrations SQL proposées en Sprint 1 sont prématurées

À ce stade, **`ml_rank`** et **`predicted_rank`** n'ont aucun consommateur réel existant dans le code.

En revanche, `is_tradable` (avec les raisons de rejet) devient nécessaire dans un contrat d'univers PIT, car `stock_scores_history` ne contient pas les titres exclus avant le selector.

Les ajouter avant d'avoir migré le flux critique ferait :

1. plus de schéma à maintenir,
2. plus de backfill à lancer,
3. plus de risques de divergence entre colonnes calculées et logique runtime,
4. sans résoudre le vrai verrou : l'univers PIT complet n'existe pas encore et `scores_df` reste la source primaire.

#### B. Le premier sprint doit définir le contrat d'univers PIT, pas ajouter des rangs

Le vrai premier sprint doit porter sur :

1. le schéma de l'univers PIT,
2. sa production depuis le screener / les données de marché,
3. son loader partagé live et backtest,
4. son utilisation comme scope attendu ML.

#### C. Le plan initial sous-estime l'impact sur `modelFactory`

Le problème n'est pas limité à `backtesting/`.

Il faut aussi migrer :

1. `modelFactory/cli.py`
2. `modelFactory/db_registry.py`
3. `modelFactory/predictor.py`
4. `ihm/services/pipeline_runner.py`
5. les options IHM liées au selector universe

#### D. Le plan initial sous-estime les consommateurs annexes de `is_candidate`

Ils doivent tous être migrés dans le même cutover fonctionnel :

1. `event_sentiment/db_io.py`
2. `database/stock_scores.py`
3. `database/repositories/scores.py`
4. diagnostics fidelity / candidate parity
5. tests et documentation

---

## 5. Plan détaillé corrigé

## Sprint 0 — Figer le contrat et préparer le cutover

**Objectif :** valider le nouveau flux ML-first hors production, puis remplacer l'ancien flux sans option de retour runtime.

### État d'implémentation au 2026-07-11

Implémenté :

1. `core/ml_selection_contract.py` définit le contrat immutable partagé :
  - univers nominal `tradable-universe`;
  - cible ML ternaire obligatoire;
  - score limité au rôle `feature_veto`;
  - feature engineering sur tout l'univers tradable avant l'inférence, sans gate;
  - vetos uniquement après le ranking ML;
  - workflow training séparé du live quotidien;
  - séquence live canonique figée à 12 étapes;
  - prédiction obligatoire;
  - rankings long/short séparés;
  - capacité totale et plafonds par côté via `SelectionCapacity`.
2. `RiskConfig` expose désormais `max_positions`, `max_long_positions`, `max_short_positions` et une propriété `selection_capacity` résolue après overlays.
3. L'ancien nom actif `short_max_positions` a été remplacé par `max_short_positions` dans le runtime, `config.yaml`, les tests et la documentation courante.
4. `PipelineLaunchOptions` et `BacktestRunOptions` exposent `ml_first_selection_contract`; cette intégration fige le contrat cible sans activer encore le cutover runtime.
5. Les tests de contrat interdisent explicitement les variantes legacy : univers `candidates`, cible binaire, score utilisé comme ranking, feature scope tronqué, veto pré-prédiction, training dans le live quotidien, prédiction optionnelle, ranking non directionnel ou workflow live différent des 12 étapes canoniques.
6. Une incohérence locale découverte pendant la validation a été corrigée dans `selector/short_score.py` : le régime `capital_preservation` abaisse bien le seuil short avec `min(..., 0.20)`.

Validé :

1. `tests/test_ml_selection_contract.py` : 18 tests passés;
2. `tests/test_short_score.py` : 3 tests passés;
3. `tests/test_phase2_bridges.py` et `tests/test_ihm_backtesting_runner.py` : tests passés dans la validation ciblée;
4. chargement YAML validé par `test_config_yaml_loads`;
5. aucun diagnostic éditeur sur les fichiers Python modifiés.

Sprint 0 est clos au niveau contrat et préparation. Le contrat n'est volontairement pas activé dans le runtime avant les fondations PIT du Sprint 1.

Écart de test externe observé : `tests/test_config_yaml_schema.py::test_market_data_section_has_only_known_keys` échoue sur `quotes_provider_live` et `quotes_provider_live_second`, clés sans lien avec ce sprint.

### Tâches

1. Figer une nomenclature cible :
  - `tradable_universe` = univers filtrable,
  - `selection_input` = entrée du ranking,
  - `selected_signals` = sorties long/short retenues.
2. Définir le contrat unique partagé par train, predict, live et backtest : univers PIT complet, prédiction ML obligatoire pour toute ligne sélectionnable, ranking long/short séparé, puis vetos score/événement/risque.
3. Préparer la validation pré-déploiement : migrations Alembic, backfill requis, tests unitaires/intégration/IHM et backtests de référence.
4. Le déploiement remplace l'ancien flux. Aucune option `ml_first_enabled`, `selection_source`, `score_legacy` ou `candidates` ne subsiste dans les commandes nominales.

### Workflow canonique figé

Le workflow live quotidien cible comporte 12 étapes visibles dans l'IHM :

1. `Import Market Data`;
2. `Data Integrity`;
3. `Universe Metrics`;
4. `Sync Latest Quotes`;
5. `Sync Earnings`;
6. `Publish Tradable Universe`;
7. `Feature Engineering PIT` sur tous les tradables, sans filtrage par score;
8. `ML Predict` ternaire sur tout l'univers publié;
9. `ML Ranking` long/short;
10. `Post-Prediction Vetos` techniques, événements et exécution;
11. `Risk Management`;
12. `Execution`.

`Feature Engineering PIT` regroupe les calculs technique, sentiment, macro et leur agrégation. Ces données sont calculées avant l'inférence lorsqu'elles sont des features, mais elles ne peuvent supprimer aucun symbole du scope ML. Les mêmes valeurs peuvent ensuite être réutilisées à l'étape 10 comme vetos, sans recalcul ni changement de date PIT.

`ML Train` ne fait pas partie du workflow live quotidien. Il devient un workflow séparé : univers historique PIT, construction du dataset, entraînement ternaire, validation, sélection du champion et publication du modèle servi. `ML Predict` refuse de démarrer sans champion ternaire compatible publié.

### Matrice go/no-go du cutover

| Contrôle | Seuil GO | Artefact attendu |
|---|---:|---|
| Tests du contrat partagé | 100% passés | rapport pytest `test_ml_selection_contract.py` |
| Snapshot d'univers publié | `status=completed` et `rows_written=rows_expected` | `universe_run_id` + audit DB |
| Fuite PIT | 0 date source postérieure à la date servie | rapport tests PIT |
| Couverture ternaire du scope live | 100% des tradables avant ouverture du risk | rapport de couverture par `universe_run_id` / `model_run_id` |
| Colonnes ternaires | `predicted_side`, `proba_long`, `proba_flat`, `proba_short` complètes et cohérentes | audit `model_predictions` |
| Parité de sélection live/backtest | 100% sur fixtures déterministes | rapport fidelity ML-first |
| Capacité portefeuille | 0 dépassement total, long ou short | tests risk + backtest |
| Options candidate nominales | 0 option acceptée ou affichée | tests CLI/IHM |
| Predictivité ML | verdict PASS de `validate_score_predictiveness.py --source ml` et meilleure structure que le score brut | artefact de validation 2024-2025 |
| Backtests de référence | aucun écart inexpliqué; décision GO documentée pour 2021+ | rapports backtest versionnés |

Un contrôle non satisfait bloque le cutover. Il ne réactive jamais l'ancien chemin candidate-first.

### Inventaire des commandes à verrouiller au cutover

1. `modelFactory/cli.py` : train/predict refusent `symbol_source=candidates` et les filtres `selector_universe_*`;
2. `ihm/services/pipeline_runner.py` : suppression des defaults candidats et de `include_ml_train` dans le workflow live;
3. `ihm/services/backtesting_runner.py` et `backtesting/cli/_impl.py` : suppression de `filter_no_ml` / `filter_candidates_without_ml` et des formulations candidate;
4. `risk_management/cli.py` : aucune entrée `load_candidates_asof()`;
5. pages IHM execution/backtesting : aucune option ou aide candidate-first.

### Fichiers concernés

- `backtesting/cli/_impl.py`
- `ihm/services/backtesting_runner.py`
- `ihm/services/pipeline_runner.py`
- `risk_management/config.py`

### Pourquoi ce sprint existe

La sécurité vient de la validation pré-déploiement; le runtime ne maintient pas deux logiques de sélection.

---

## Sprint 1 — Créer le contrat d'univers tradable PIT

**Objectif :** produire et lire le même univers historique complet pour le train, le predict, le backtest et le live.

### État d'implémentation au 2026-07-11

**Sprint 1 terminé au niveau fondation PIT.** Le runtime de sélection reste volontairement candidate-first jusqu'au Sprint 2; le nouvel univers ne sert donc pas encore à ouvrir des positions live ou backtest.

Implémenté :

1. Migration Alembic `0046_add_tradable_universe_history` :
  - `tradable_universe_runs` porte le statut, le preset, la date PIT, le fingerprint, les compteurs, la qualité et le caractère canonique;
  - `tradable_universe_history` porte une ligne par `(universe_run_id, symbol)` avec décision, motifs, métriques objectives et qualité;
  - index as-of sur les runs et index scope/tradabilité sur les lignes.
2. `common/tradable_universe.py` centralise le contrat :
  - `UniverseMember` et `UniverseResolution`;
  - création d'un run `running`;
  - publication transactionnelle seulement quand `rows_written == rows_expected`;
  - bascule atomique du run canonique sans mutation des reruns précédents;
  - échec explicite d'un run incomplet ou d'un chunk screener défaillant;
  - résolution `resolve_universe_asof(...)` qui ne sert que le dernier run `completed`, canonique, complet et antérieur ou égal à la date demandée.
3. Loaders partagés ajoutés :
  - `RiskRepository.load_tradable_universe_asof(...)`;
  - `backtesting.data_loader.load_tradable_universe_asof(...)`;
  - `modelFactory.db_registry.load_tradable_universe_symbols(...)` et source `tradable-universe`, avec date explicite obligatoire.
4. `screener/stock_screener.py` publie un membre PIT pour chaque symbole évalué, y compris les titres rejetés avant les scores finaux.
  - Les motifs objectifs actuels couvrent disponibilité des barres, historique, prix et ADV;
  - force relative et range ne déterminent plus `is_tradable` dans ce nouveau snapshot;
  - aucune publication canonique n'a lieu sur run partiel ou lorsque le schéma n'est pas migré.
5. La qualité des snapshots produits par le screener courant est explicitement `degraded`.
  - quotes/spread, earnings blackout et market-cap ne sont pas encore intégrés à cette publication;
  - le grade est restitué par `UniverseResolution` pour que les Sprints 2-3 puissent refuser tout snapshot non `full` avant un usage runtime;
  - il ne s'agit pas d'un contournement du contrat live final.

Validé :

1. `tests/test_tradable_universe.py` couvre scope tradable, rejet observable, run partiel/failed, rerun canonique, absence de look-ahead, presets indépendants et parité des trois loaders;
2. `tests/test_stock_screener.py` couvre la publication du scope complet, y compris un symbole rejeté;
3. `tests/test_model_factory_db_registry.py` couvre la source `tradable-universe` et l'obligation de date;
4. `tests/test_alembic_rollback.py` valide la révision `0046`;
5. la suite ciblée PIT/screener/registry/Alembic est passée sans échec et les diagnostics éditeur sont nuls.

Reste hors Sprint 1 :

1. enrichir le snapshot avec quotes, earnings et market-cap afin d'autoriser le grade `full`;
2. basculer réellement live/backtest sur ces loaders au Sprint 2;
3. relier l'univers au workflow IHM quotidien et au predict ML au Sprint 3;
4. exécuter le backfill historique complet avant le cutover.

### Tâches structurantes

1. Ajouter une migration Alembic et le DDL d'une table dédiée, recommandée sous le nom `tradable_universe_history`.
  - clé primaire des lignes : `(universe_run_id, symbol)`;
  - `tradable_universe_runs` porte `universe_run_id`, `snapshot_date`, `capital_preset_key`, `config_fingerprint`, statut `running|completed|failed`, nombres attendus/écrits et dates de début/fin;
  - `tradable_universe_history` porte `is_tradable`, un motif principal, les motifs détaillés de rejet, `created_at` et les métriques utilisées pour la décision;
  - indexer les résolutions nominales sur `(capital_preset_key, snapshot_date, status)` côté runs et `(universe_run_id, is_tradable, symbol)` côté lignes;
  - conserver les reruns comme runs distincts; un seul run `completed` est désigné comme publication canonique d'un couple `(snapshot_date, capital_preset_key)`;
  - un loader ne peut servir que les lignes d'un run `completed`; un snapshot partiel ne doit jamais devenir le "dernier snapshot" live.

2. Modifier le chemin screener qui part de `iter_symbol_chunks()`.
  - il doit produire une ligne PIT pour chaque symbole évalué, y compris les titres rejetés avant `final_scores`;
  - les critères force relative / range historique sont retirés de la décision `is_tradable`;
  - le selector calcule les scores techniques pour tous les tradables, sans sélection Top-N et sans écrire `is_candidate` / `candidate_rank`;
  - ne pas dériver l'univers depuis `stock_scores`, car `upsert_scores_snapshot()` y purge les symboles absents.

3. Créer un module ou repository unique de résolution d'univers.
  - live : dernier snapshot complet publié;
  - backtest : dernier snapshot `<= trade_date`;
  - train/predict historique : snapshots dans la fenêtre demandée;
  - les règles de data source, historique minimum et asset class y sont centralisées.

   Contrat recommandé :

   ```python
   resolve_universe_asof(
       engine,
       trade_date,
       capital_preset_key,
       *,
       tradable_only=True,
   ) -> UniverseResolution
   ```

   `UniverseResolution` contient le DataFrame, `universe_run_id`, la date réellement servie, la complétude et les diagnostics de dégradation.

4. Ajouter les loaders explicites nécessaires.
  - `risk_management/db_io.py` : `load_tradable_universe_asof(...)`;
  - `backtesting/data_loader.py` : loader PIT DataFrame;
  - `modelFactory/db_registry.py` : source `tradable-universe` / `tradable_universe` validée, au lieu de détourner `stock-bars-daily`.

5. Écrire les tests PIT.
  - un titre non-candidat doit apparaître dans le snapshot;
  - un titre non tradable doit rester observable avec son motif;
  - aucun snapshot futur ne doit être utilisé pour une date de backtest.
  - un run partiel ou `failed` ne doit jamais être servi;
  - la promotion d'un run vers `completed` et canonique doit être transactionnelle et refuser `rows_written != rows_expected`;
  - un rerun ne doit jamais modifier les lignes d'un run précédemment publié;
  - deux presets capital doivent produire des scopes indépendants.

6. Décider la stratégie de reprise historique avant de lancer le développement.
  - les anciens `stock_scores_history` ne contiennent pas les titres rejetés et ne permettent donc pas de reconstruire seuls l'univers complet;
  - un backfill ML-first doit rejouer le nouveau calcul depuis les données historiques disponibles (barres, métadonnées, fondamentaux, quotes, earnings);
  - lorsqu'une métrique historique est indisponible, le run doit marquer explicitement le snapshot comme dégradé ou exclure la période, jamais la remplacer silencieusement par une valeur courante.

### Fichiers concernés

- `alembic/versions/`
- `database/sql/stock/`
- `screener/stock_screener.py`
- `screener/db_io.py`
- `risk_management/db_io.py`
- `backtesting/data_loader.py`
- `modelFactory/db_registry.py`
- tests de persistence et PIT

### Critère de sortie

Pour une date donnée, le système peut lister de façon rejouable tous les symboles évalués, savoir lesquels sont tradables et expliquer les exclusions, sans dépendre de `is_candidate`.

---

## Sprint 2 — Basculer la sélection backtest et live sur l'univers ML-first

**Objectif :** faire de la prédiction ML la source primaire du ranking dans les deux chemins d'exécution.

### Tâches structurantes

0. Imposer le même ordre de chargement dans les deux runtimes :
  1. univers tradable PIT complet;
  2. features techniques, sentiment et macro PIT calculées ou chargées pour tout le scope, sans gate;
  3. prédictions ternaires correspondant exactement au scope;
  4. ranking long/short piloté uniquement par le ML;
  5. vetos post-prédiction fondés sur le contexte déjà chargé;
  6. risk, sizing et exécution.

  Lorsque les prédictions sont déjà persistées, elles restent la table primaire de `signal_replay`. Lorsque `rebuild-missing` doit lancer une inférence, les features de l'étape 2 sont construites avant cette inférence, toujours sur l'univers complet. Cette différence technique ne change pas l'autorité métier : ni les scores ni le sentiment ne définissent le scope ou le ranking.

1. `backtesting/resilience.py`
  - remplacer `_expected_symbol_dates(scores_df)` par `resolve_expected_prediction_scope(...)` fondé sur le snapshot `tradable_universe_history`;
  - le rebuild ML manquant reçoit ce scope, pas la liste de scores.

2. `backtesting/signal_replay.py`
  - ajouter un chemin predictions-first;
  - `predictions_df` devient la table primaire;
  - merger le snapshot d'univers puis les scores disponibles comme contexte/veto;
  - utiliser exclusivement `predicted_side`, `proba_long` et `proba_short`;
  - exclure `flat`, les prédictions non ternaires et les lignes sans prédiction;
  - classer séparément longs et shorts avec les plafonds par côté;
  - appliquer ensuite les vetos score/événement sans reclasser par score, puis respecter `max_positions` total.

3. `backtesting/cli/_impl.py`
  - charger l'univers PIT puis les prédictions;
  - supprimer l'hypothèse de message et de contrôle "aucun score candidat";
  - remplacer le sens de `filter_candidates_without_ml` par une politique explicite de couverture ML de l'univers tradable.

4. `risk_management/cli.py` et `risk_management/db_io.py`
  - remplacer le point d'entrée live `repo.load_candidates_asof(trade_date)` par l'univers tradable;
  - charger les prédictions pour l'univers complet avant tout tagging long/short;
  - supprimer l'actuel tagging short préalable au chargement des prédictions;
  - construire le ranking ML ternaire avant `portfolio_builder`;
  - supprimer les filtres `is_candidate = 1` des requêtes auxiliaires utilisées par le chemin live, notamment `load_factor_columns_asof()`.

5. `backtesting/risk_bridge.py` et `risk_management/models.py`
  - faire accepter au bridge les résultats de sélection ML;
  - remplacer `CandidateScore` / `EnrichedCandidate` / `candidate_rank` par une représentation métier neutre (`SelectionInput`, `EnrichedSelection`, `selection_rank` ou équivalent).

6. `risk_management/portfolio_builder.py`
  - supprimer `filter_candidates_without_ml`: une sélection sans ML n'existe plus;
  - remplacer le tri score/conviction actuel par l'ordre ML directionnel déjà calculé;
  - supprimer le fallback de probabilité et le tie-break sur `candidate_rank`;
  - appliquer `max_positions`, `max_long_positions` et `max_short_positions` de manière déterministe.

### Fichiers concernés

- `risk_management/db_io.py`
- `risk_management/cli.py`
- `risk_management/models.py`
- `backtesting/risk_bridge.py`
- `backtesting/resilience.py`
- `backtesting/signal_replay.py`
- `backtesting/cli/_impl.py`
- `risk_management/config.py`

### Critère de sortie

Backtest et live peuvent sélectionner des positions à partir de prédictions couvrant l'univers tradable, même si un titre n'a jamais été `is_candidate=1`.

### État d'implémentation (2026-07-11, en cours)

Les fondations backtest du Sprint 2 sont implémentées et validées :

- `backtesting/signal_replay.py` est désormais predictions-first. Les colonnes ternaires `predicted_side`, `proba_long`, `proba_flat` et `proba_short` sont obligatoires; `flat` et les probabilités directionnelles incomplètes sont exclus. Les rangs et plafonds long/short sont calculés séparément, puis les scores ne sont joints qu'en contexte.
- `backtesting/data_loader.py` expose `load_tradable_universe_scope()`, qui résout le snapshot PIT canonique pour chaque séance effectivement rejouée.
- `backtesting/resilience.py` déduit la couverture ML attendue depuis ce scope d'univers, et non plus depuis les lignes de score.
- `backtesting/cli/_impl.py` fournit ce scope à `prepare_predictions_for_ml_mode()` et bloque explicitement si l'univers PIT est absent ou vide.
- `risk_management/db_io.py` charge maintenant uniquement les prédictions live ternaires complètes. Une ligne binaire ou incomplète ne peut pas être traitée comme une prédiction de sélection ML-first.

Validation exécutée :

```text
16 passed: tests/test_tradable_universe.py,
tests/test_backtesting.py::TestSignalReplay,
tests/test_phase2_bridges.py::test_signal_replay_and_risk_bridge_keep_same_score_cascade,
tests/test_db_io_v2.py::{test_load_predictions_returns_latest,test_load_predictions_empty_symbols}
```

Le Sprint 2 n'est pas encore terminé. Restent le basculement de `risk_management/cli.py` vers l'univers PIT `full`, la représentation neutre de sélection et le remplacement du ranking/fusion score-first dans `PortfolioBuilder` et `backtesting/risk_bridge.py`. Le snapshot d'univers actuellement publié avec le grade `degraded` ne doit pas être activé pour la sélection live.

---

## Sprint 3 — Migrer train/predict ML hors de `symbol_source=candidates`

**Objectif :** éviter de garder un gate implicite côté ML après avoir corrigé le backtest.

### État d'implémentation (2026-07-11, en cours)

La migration du chemin nominal `modelFactory` est implémentée :

- `modelFactory/cli.py` n'accepte plus que `--symbol-source tradable-universe`, désormais la valeur par défaut. Les options `--selector-universe-*` sont supprimées; `--universe-date` porte la date PIT explicite, avec repli déterministe sur `training-end-date`, puis la date du jour.
- `modelFactory/db_registry.py` ne résout plus les anciennes sources de train/predict. Une source hors `tradable-universe` échoue explicitement, et la résolution exige une date PIT.
- `modelFactory/orchestrator.py` entraîne sur cet univers et exige `universe_date` lorsque les symboles ne sont pas fournis explicitement. Il n'applique plus de filtre selector après chargement.
- Le backfill `predict` résout le scope `tradable-universe` pour chaque date de prédiction; il ne réutilise plus `stock-scores-history` pour construire les scopes historiques.
- `modelFactory/predictor.py` utilise l'univers tradable PIT à la date de cutoff pour les features cross-sectionnelles, au lieu de `load_candidate_symbols()`.
- `DataConfig` ne porte plus les paramètres `selector_universe_*`.

Validation exécutée :

```text
63 passed: tests/test_model_factory_cli.py,
tests/test_model_factory_config.py,
tests/test_model_factory_db_registry.py,
tests/test_model_factory_orchestrator.py
```

Le Sprint 3 reste en cours : l'IHM `pipeline_runner`, les options et libellés IHM, ainsi que la publication d'un univers de grade `full` ne sont pas encore basculés. La suite large `tests/test_model_factory_predictor.py` contient en outre des fixtures existantes dont le stub `get_feature_columns` ne supporte pas l'argument actuel `include_short_score`; elle n'a pas été utilisée comme validation de ce changement ciblé.

### Tâches structurantes

0. Réordonner les étapes de `ihm/services/pipeline_runner.py`.
  - `stock_screener` collecte/calcul les métriques larges sans sélectionner un Top-N;
  - `sync_latest_quotes` et `sync_earnings_calendar` alimentent les contraintes objectives;
  - une étape explicite `publish_tradable_universe` publie atomiquement le snapshot complet;
  - `alpha_scanner`, sentiment et signal aggregator deviennent les sous-étapes de `Feature Engineering PIT` sur tous les tradables, sans sélection;
  - `ml_predict` consomme ce `universe_run_id`, les features PIT et un champion ternaire déjà publié;
  - le ranking ML et les vetos post-prédiction deviennent deux étapes métier distinctes;
  - `ml_train` est retiré du workflow live quotidien et exposé dans un workflow training séparé;
  - `risk_management` refuse de démarrer si l'univers ou la couverture ML du run courant est incomplet.

1. `ihm/services/pipeline_runner.py`
  - changer les defaults :
    - `ml_train_symbol_source`
    - `ml_predict_symbol_source`
  - la seule source nominale est `tradable-universe`.
  - `stock-bars-daily` reste une source d'administration / diagnostic, pas l'univers nominal, car elle ne porte pas les règles PIT de tradabilité.
  - le workflow live par défaut contient les 12 étapes figées au Sprint 0 et n'expose plus `include_ml_train`;
  - le workflow training conserve une commande explicite train + validation + publication du champion.

2. `modelFactory/cli.py`
  - revoir la valeur par défaut de `symbol_source`,
  - supprimer `candidates` des sources acceptées par le train et le predict,
  - supprimer les filtres d'univers `selector_signal_mode` et `candidate_rank`,
  - déplacer `earnings_blackout` dans les règles de tradabilité PIT.

3. `modelFactory/db_registry.py`
  - créer une primitive d'univers fondée sur `tradable_universe_history`,
  - supprimer `load_candidate_symbols()` et `filter_symbols_by_selector_context()` des chemins train/predict,
  - faire consommer aux features cross-sectionnelles le même scope que l'inférence.

4. `modelFactory/predictor.py`
  - pour les features cross-sectionnelles, ne plus prendre `load_candidate_symbols(engine)` comme univers de référence par défaut,
  - utiliser l'univers effectivement servi au predict.

5. `modelFactory/config.py`
  - supprimer `selector_universe_*`,
  - renommer `include_selector_context_features` en `include_score_context_features` si les scores restent des features ML.

6. Définir la sélection déterministe des prédictions en DB.
  - pour chaque `(symbol, prediction_date)`, choisir le run ML publié/servi, jamais une ligne arbitraire parmi plusieurs `run_id`;
  - rattacher les diagnostics et la sélection au `model_run_id` et au `universe_run_id` effectivement utilisés;
  - vérifier que les dates de training et de prédiction respectent le PIT avant de servir le run.

### Fichiers concernés

- `ihm/services/pipeline_runner.py`
- `modelFactory/cli.py`
- `modelFactory/db_registry.py`
- `modelFactory/predictor.py`
- `modelFactory/config.py`

### Critère de sortie

Une exécution train/predict depuis l'IHM ne peut utiliser que l'univers tradable PIT.

---

## Sprint 4 — Requalifier score, selector et conviction

**Objectif :** faire du score technique un garde-fou et non un driver principal.

### Statut d'implémentation (terminé)

Implémenté et validé sur le noyau de conviction et le replay backtest :

- `core/conviction.py` et le wrapper déprécié `risk_management/conviction.py`
  retournent désormais exclusivement la probabilité ML directionnelle ; une
  probabilité absente ou non finie échoue explicitement et ne peut plus produire
  de conviction score-only ;
- `backtesting/signal_replay.py` classe toujours séparément les longs par
  `proba_long` et les shorts par `proba_short`, puis applique des vetos
  post-ranking : `min_proba_long`, `min_proba_short`, `min_score_long` et
  `max_score_short` ;
- les vetos ne changent ni le périmètre de prédiction ni les rangs ML et exposent
  `veto_reason` pour le diagnostic ;
- `RiskConfig` et tous les presets capital exposent désormais les vetos
  directionnels `min_score_veto_long` / `max_score_veto_short` et les seuils
  `min_proba_long` / `min_proba_short`; les seuils de probabilité restent à
  `0.0` tant qu'une calibration ne justifie pas un niveau plus strict ;
- `PortfolioBuilder` refuse toute ligne sans prédiction ternaire directionnelle,
  dérive le côté depuis `predicted_side`, utilise la probabilité directionnelle
  comme conviction et ne départage plus par `candidate_rank`;
- le chemin live commence désormais par `load_tradable_universe_asof(...)` et
  refuse un snapshot dont `data_quality_grade != full`; le score PIT est chargé
  comme contexte facultatif pour ce scope, jamais via `is_candidate`.
- tests ciblés validés : `12 passed` pour la conviction et `4 passed` pour le
  replay de signaux.

Reste à migrer : les doubles et tests d'intégration de la CLI live vers le
nouveau repository d'univers, l'élimination de `is_candidate` /
`candidate_rank` dans les chemins selector/screener, et le retrait physique du
tagging `short_score` hérité dans la CLI avant chargement des prédictions.

### Tâches structurantes

1. `core/conviction.py`
  - remplacer la fusion binaire score + `predicted_proba` par une conviction directionnelle fondée sur `proba_long` ou `proba_short`;
  - appliquer ensuite le score comme veto ou modulateur calibré;
  - supprimer tout fallback score-only si ML ou les probabilités ternaires manquent.

2. `config/capital_presets.yaml`
  - remplacer la sémantique "min score pour être candidat" par :
    - seuil veto long,
    - seuil veto short,
    - seuil minimum `proba_long`,
    - seuil minimum `proba_short`,
    - `max_positions`, `max_long_positions`, `max_short_positions` cohérents.

3. `selector/` et `screener/`
  - laisser le calcul des scores en place,
  - supprimer l'écriture de `is_candidate` et de `candidate_rank`,
  - le score technique sert uniquement de feature et de veto post-prédiction.

4. `backtesting/signal_replay.py`
  - implémenter la logique métier claire :
    - ranking ML,
    - veto score,
    - modulation sentiment optionnelle,
    - sélection finale.

5. `selector/short_score.py` et les appels live/backtest
  - retirer `tag_short_candidates()` du chemin de décision;
  - conserver uniquement les calculs nécessaires au `short_score` si celui-ci reste une feature ou un veto;
  - le côté short vient exclusivement de `predicted_side=short`.

### Remarque importante

Passer brutalement de `0.4/0.6` à `0.2/0.8` partout sans recalibration serait arbitraire.

La bonne séquence est :

1. d'abord changer la structure du flux,
2. ensuite recalibrer les poids sur le nouveau flux,
3. puis fixer de nouveaux defaults.

### Fichiers concernés

- `core/conviction.py`
- `config/capital_presets.yaml`
- `selector/**/*.py`
- `screener/**/*.py`
- `backtesting/signal_replay.py`
- `selector/short_score.py`

---

## Sprint 5 — Adapter l'IHM et les contrats d'options

**Objectif :** supprimer le mensonge fonctionnel dans l'IHM.

### Statut d'implémentation (terminé)

Implémenté et validé sur les contrats de lancement ML et backtesting :

- `PipelineLaunchOptions` utilise `tradable-universe` comme unique source
  nominale pour `ml_train` et `ml_predict`, y compris lorsqu'un ancien payload
  IHM fournit une source selector/score historique ;
- l'execution center ne propose plus de filtres `selector_universe_*`; les
  commandes IHM n'émettent plus `--selector-universe-signal-modes`,
  `--selector-universe-max-candidate-rank` ni
  `--selector-universe-exclude-earnings-blackout` ;
- le libellé et le flag de feature sont requalifiés de contexte selector vers
  contexte score (`--include-score-context`), accepté par le CLI Model Factory
  tout en conservant l'ancien flag comme alias de compatibilité ; l'option IHM
  interne est désormais `ml_include_score_context` ;
- le workflow live par défaut ne comprend pas `ml_train`; le training reste un
  lancement explicite séparé, n'inclut plus `alpha_scanner`, et son formulaire
  n'expose plus les paramètres Selector ;
- le runner backtesting, le lancement live `risk_management` et leurs écrans ne
  proposent plus `filter_no_ml` / `--filter-no-ml`, car la couverture ML se
  mesure sur l'univers tradable ;
- les diagnostics de replay utilisent `scoring_rows` / `scoring_symbols` et
  affichent des lignes score plutôt que des candidats ;
- le préflight de couverture ML du backtesting compare les prédictions au
  `tradable_universe_history` associé aux runs canoniques complets, et expose
  `expected_universe_symbol_dates` au lieu d'un scope `is_candidate` ;
- la page Pipeline historique force elle aussi `ml_train` et `ml_predict` vers
  `tradable-universe`, sans sélecteur de sources scores/candidates ni filtre
  Selector ;
- le pipeline sentiment utilise l'univers tradable pour ses sous-étapes, et
  l'Alpha Scanner persiste seulement le contexte score sans écrire
  `is_candidate` ;
- l'Execution Center affiche le dernier `universe_run_id` PIT canonique, son
  grade, la couverture de prédictions et le champion de gouvernance servi.
- validations ciblées : `24 passed` pour `test_ihm_backtesting_runner.py` et
  `6 passed` pour les contrats ML du pipeline runner, `16 passed` pour le CLI
  Model Factory.

Le nettoyage des colonnes et noms de schéma historiques (`is_candidate`,
`candidate_rank`) reste le Sprint 6 : ils ne définissent plus le scope ni la
sélection nominale des parcours IHM/live.

Aujourd'hui, l'IHM expose encore un modèle mental "selector universe -> ML". Tant que cela reste visible, l'utilisateur pilotera le nouveau backend avec de mauvaises attentes.

### Tâches structurantes

1. `ihm/services/pipeline_runner.py`
  - renommer les options internes :
    - `ml_include_selector_context` devient `ml_include_score_context`,
    - supprimer `ml_selector_universe_*`,
    - remplacer `filter_candidates_without_ml` par la politique de couverture ML de l'univers tradable.
  - afficher séparément `Workflow Live ML-First` et `Workflow ML Training`;
  - montrer `universe_run_id`, couverture ML et champion servi dans les diagnostics du workflow live.

2. `ihm/services/backtesting_runner.py`
  - retirer toute option candidate-first,
  - exposer uniquement les paramètres ML-first: seuils ML, vetos score, top-N long/short et règles de tradabilité.

3. `ihm/pages/_execution_center/__init__.py`
  - modifier les labels et aides utilisateur :
    - supprimer toute option et tout libellé `candidate`,
    - expliciter le nouvel univers servi au train/predict.

4. `ihm/pages/backtesting/__init__.py`
  - adapter les diagnostics affichés :
    - beaucoup de widgets parlent encore de `candidate_rows`, `expected_candidate_symbol_dates`, `candidate_target_parity_summary`.
  - en mode ML-first, il faudra parler plutôt de :
    - `selection_input_rows`,
    - `expected_prediction_scope`,
    - `selection_to_target_parity`.

5. `ihm/services/run_summary.py` et services associés
  - revoir les libellés hérités : `selected_candidates`, `eligible_candidates`, `blocked_candidates`, etc.

### Fichiers concernés

- `ihm/services/pipeline_runner.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/_execution_center/__init__.py`
- `ihm/pages/backtesting/__init__.py`
- `ihm/services/run_summary.py`
- `ihm/services/queries.py`

### Critère de sortie

Un utilisateur IHM ne doit plus voir ni devoir comprendre le concept `candidate` pour piloter un run.

---

## Sprint 6 — Migrer les services satellites et supprimer les APIs candidate

**Objectif :** retirer les dépendances applicatives restantes à `is_candidate` et au vocabulaire candidat.

### Tâches structurantes

1. `database/stock_scores.py`
  - supprimer `list_candidate_symbols()` et le remplacer par les loaders d'univers ou de score explicitement nommés.

2. `database/repositories/scores.py`
  - supprimer `list_candidates()` et exposer les APIs nécessaires au contexte score ou à l'univers tradable.

3. `event_sentiment/db_io.py`
  - remplacer la dépendance directe aux candidats si le flux nominal doit couvrir l'univers tradable.

4. services / diagnostics / fidélité
  - remplacer les payloads nommés `candidate_*` par `selection_*` ou `universe_*`.

5. risk et execution
  - remplacer `candidate_rank` par `selection_rank` dans `risk_decisions`, `portfolio_targets` et `execution_targets_snapshot`;
  - mettre à jour `execution_engine/models.py`, `execution_engine/db_io.py`, `execution_engine/order_intents.py`, `backtesting/execution_bridge.py`, `backtesting/execution_replay.py` et les exports fidelity;
  - préserver `decision_rank` s'il représente toujours le rang après contraintes risk, en documentant clairement la différence avec `selection_rank`.

6. documentation et glossaires
  - supprimer le concept opérationnel `candidate`.

### Fichiers concernés

- `database/stock_scores.py`
- `database/repositories/scores.py`
- `event_sentiment/db_io.py`
- `backtesting/fidelity.py`
- `risk_management/models.py`
- `execution_engine/models.py`
- `execution_engine/db_io.py`
- `execution_engine/order_intents.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `doc/**/*.md`

---

## Sprint 7 — Nettoyage final du schéma candidate

**Objectif :** retirer les colonnes et index candidate devenus sans lecteur ni writer.

### Tâches

1. Supprimer les colonnes `is_candidate` et `candidate_rank` de `stock_scores` et `stock_scores_history` après migration des données nécessaire à l'audit.
2. Supprimer les index SQL `idx_history_candidate` et `idx_history_preset_candidate`.
3. Remplacer les colonnes `candidate_rank` downstream par `selection_rank` dans les tables risk/execution et leurs migrations Alembic.
4. Supprimer ou réécrire les DDL, scripts de backfill et diagnostics spécifiques aux candidats.
5. Ne pas ajouter `ml_rank` / `predicted_rank` tant qu'un besoin concret d'audit matérialisé n'existe pas.

---

## 6. Impacts détaillés par zone

## 6.1 Base de données

### Ce qui change sûrement

1. Les colonnes `is_candidate` et `candidate_rank` sont supprimées des schémas actifs.
2. `tradable_universe_history` devient la source PIT de portée et de tradabilité.
3. `stock_scores_history` reste la source PIT de score / contexte lorsque la ligne existe.
4. `model_predictions` devient beaucoup plus importante comme table d'entrée métier.

### Ce qui n'est pas encore justifié

1. `ml_rank`
2. `predicted_rank`
3. persister le top-N final si les artefacts de run fournissent déjà l'audit voulu

### Ce qui pourrait devenir utile plus tard

1. snapshot explicite du veto score
2. matérialisation du top-N long/short pour audit live/backtest
3. rangs ML matérialisés si les diagnostics ne peuvent pas être reconstruits depuis `model_predictions`

## 6.2 Backend métier

### Zones critiques

1. `backtesting/resilience.py`
2. `backtesting/signal_replay.py`
3. `risk_management/db_io.py`
4. `modelFactory/cli.py`
5. `modelFactory/db_registry.py`
6. `modelFactory/predictor.py`

### Risques principaux

1. doubles définitions de l'univers selon le module,
2. drift entre train et predict,
3. drift entre backtest et live,
4. cross-sectional features calculées sur un univers incohérent,
5. diagnostics fidelity toujours branchés sur le vocabulaire candidate.

## 6.3 IHM

### Impacts certains

1. defaults ML train/predict à changer,
2. widgets `selector universe` à requalifier,
3. wording backtest à corriger,
4. payloads de diagnostic à renommer progressivement,
5. aides utilisateurs et docs IHM à réaligner.

### Principe de migration IHM

1. d'abord changer le comportement backend,
2. ensuite refléter proprement ce comportement dans les labels,
3. supprimer les options candidate dans le même cutover.

---

## 7. Ordre recommandé d'implémentation

L'ordre recommandé n'est pas un refactor de colonnes de score ou de rangs DB-first. Il commence néanmoins par le **contrat de données PIT indispensable** :

1. Créer et alimenter l'univers tradable PIT complet.
2. Découpler les sélections backtest et live du score-first.
3. Migrer train/predict ML vers `tradable-universe` comme unique source admise.
4. Requalifier score et conviction.
5. Adapter l'IHM.
6. Migrer les services satellites et supprimer les APIs candidate.
7. Retirer les colonnes et index candidate une fois la validation pré-déploiement terminée.

Cet ordre minimise le risque parce qu'il attaque d'abord le **comportement réel** qui crée le biais actuel.

---

## 8. Validation attendue après refactor

Le refactor ne sera considéré réussi que si les validations suivantes passent.

### Validation fonctionnelle

1. Un backtest ML-first tourne sans dépendre d'un univers `is_candidate=1`.
2. Un train/predict depuis l'IHM n'expose ni n'accepte la source `candidates`.
3. Le ranking long/short est séparé et fondé sur les probabilités ternaires; `flat` ne génère aucun ordre.
4. Une ligne sans prédiction ternaire reste non sélectionnable, sans fallback score-only.
5. `max_long_positions` et `max_short_positions` sont respectés sans jamais dépasser `max_positions` total.
6. Le score technique peut exclure un signal, mais ne définit plus seul l'univers ou le côté.
7. Un run live `risk_management` utilise le même contrat d'univers que le backtest.

### Validation data / audit

1. La couverture ML sur l'univers servi augmente fortement.
2. Les diagnostics de missing ML sont exprimés relativement à l'univers tradable.
3. Le scope cross-sectionnel est cohérent entre train, predict et backtest.
4. Chaque sélection peut être reliée au snapshot d'univers, à la prédiction utilisée et au motif de rejet éventuel.
5. Un snapshot `running`, `failed` ou incomplet n'est jamais servi; un rerun publié ne modifie aucun run antérieur.
6. `selection_rank` traverse risk et execution, tandis que `candidate_rank` n'existe plus dans les schémas actifs.

### Validation performance

1. `validate_score_predictiveness.py --source ml` sur 2024-2025 doit montrer une structure de buckets meilleure que le score technique brut.
2. Les backtests 2021+ doivent être rejoués avant toute suppression SQL de `is_candidate`.
3. Les résultats live/backtest doivent identifier `universe_run_id` et `model_run_id` pour permettre une comparaison reproductible.

---

## 9. Décision sur `is_candidate`

Le nouveau système ne contient plus de notion opérationnelle de candidat.

1. `tradable_universe_history` remplace le rôle d'univers PIT.
2. Les scores restent des features et des vetos, pas un mécanisme de création de candidats.
3. Tous les readers, writers, options CLI/IHM, payloads et tests sont migrés avant le déploiement.
4. La migration de nettoyage supprime ensuite `is_candidate`, `candidate_rank` et leurs index du schéma actif.

---

## 10. Recommandation finale

Le plan final remplace entièrement le flux selector-first par un flux ML-first unique.

Le refactor doit être conduit comme suit :

1. Créer l'univers tradable PIT complet.
2. Brancher exclusivement live, backtest, train et predict sur ce contrat.
3. Construire les sélections depuis les prédictions ML, avec scores en feature/veto.
4. Supprimer les options et dépendances candidate dans l'IHM et les services.
5. Supprimer le schéma candidate après validation pré-déploiement.
