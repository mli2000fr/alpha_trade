# Refactor ML-First — Suppression du chemin critique `candidate -> ML`

**Statut :** Plan détaillé audité sur le code  
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

Clé minimale :

```text
(snapshot_date, capital_preset_key, symbol)
```

Champs minimaux :

1. `is_tradable` et `tradability_reason_code`,
2. état de données (`history_days`, `bars_available`, `data_source`),
3. critères objectifs (`close_price`, `adv_usd`, `spread_bps`, `market_cap`, `atr_pct_20`, `earnings_blackout`, anomalies),
4. provenance (`config_fingerprint`, `created_at`).

Le selector conserve `final_score` / `short_score` comme contexte et veto. Il ne décide plus si un symbole existe dans l'univers de sélection.

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

### Tâches

1. Figer une nomenclature cible :
  - `tradable_universe` = univers filtrable,
  - `selection_input` = entrée du ranking,
  - `selected_signals` = sorties long/short retenues.
2. Définir le contrat unique partagé par train, predict, live et backtest : univers PIT complet, prédiction ML obligatoire pour toute ligne sélectionnable, ranking long/short séparé, puis vetos score/événement/risque.
3. Préparer la validation pré-déploiement : migrations Alembic, backfill requis, tests unitaires/intégration/IHM et backtests de référence.
4. Le déploiement remplace l'ancien flux. Aucune option `ml_first_enabled`, `selection_source`, `score_legacy` ou `candidates` ne subsiste dans les commandes nominales.

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

### Tâches structurantes

1. Ajouter une migration Alembic et le DDL d'une table dédiée, recommandée sous le nom `tradable_universe_history`.
  - clé : `(snapshot_date, capital_preset_key, symbol)`;
  - conserver `config_fingerprint` et la date de création;
  - stocker `is_tradable`, un ou plusieurs motifs de rejet, et les métriques utilisées pour la décision.

2. Modifier le chemin screener qui part de `iter_symbol_chunks()`.
  - il doit produire une ligne PIT pour chaque symbole évalué, y compris les titres rejetés avant `final_scores`;
  - le selector continue à enrichir les survivants avec les scores techniques, sans faire disparaître les lignes non retenues du nouvel univers;
  - ne pas dériver l'univers depuis `stock_scores`, car `upsert_scores_snapshot()` y purge les symboles absents.

3. Créer un module ou repository unique de résolution d'univers.
  - live : dernier snapshot complet publié;
  - backtest : dernier snapshot `<= trade_date`;
  - train/predict historique : snapshots dans la fenêtre demandée;
  - les règles de data source, historique minimum et asset class y sont centralisées.

4. Ajouter les loaders explicites nécessaires.
  - `risk_management/db_io.py` : `load_tradable_universe_asof(...)`;
  - `backtesting/data_loader.py` : loader PIT DataFrame;
  - `modelFactory/db_registry.py` : source `tradable-universe` / `tradable_universe` validée, au lieu de détourner `stock-bars-daily`.

5. Écrire les tests PIT.
  - un titre non-candidat doit apparaître dans le snapshot;
  - un titre non tradable doit rester observable avec son motif;
  - aucun snapshot futur ne doit être utilisé pour une date de backtest.

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

1. `backtesting/resilience.py`
  - remplacer `_expected_symbol_dates(scores_df)` par `resolve_expected_prediction_scope(...)` fondé sur le snapshot `tradable_universe_history`;
  - le rebuild ML manquant reçoit ce scope, pas la liste de scores.

2. `backtesting/signal_replay.py`
  - ajouter un chemin predictions-first;
  - `predictions_df` devient la table primaire;
  - merger le snapshot d'univers puis les scores disponibles comme contexte/veto;
  - classer séparément longs et shorts avec `top_n_long` et `top_n_short`.

3. `backtesting/cli/_impl.py`
  - charger l'univers PIT puis les prédictions;
  - supprimer l'hypothèse de message et de contrôle "aucun score candidat";
  - remplacer le sens de `filter_candidates_without_ml` par une politique explicite de couverture ML de l'univers tradable.

4. `risk_management/cli.py` et `risk_management/db_io.py`
  - remplacer le point d'entrée live `repo.load_candidates_asof(trade_date)` par l'univers tradable;
  - joindre les prédictions puis construire le ranking ML avant `portfolio_builder`;
  - supprimer les filtres `is_candidate = 1` des requêtes auxiliaires utilisées par le chemin live, notamment `load_factor_columns_asof()`.

5. `backtesting/risk_bridge.py` et `risk_management/models.py`
  - faire accepter au bridge les résultats de sélection ML;
  - remplacer `CandidateScore` / `EnrichedCandidate` / `candidate_rank` par une représentation métier neutre (`SelectionInput`, `EnrichedSelection`, `selection_rank` ou équivalent).

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

---

## Sprint 3 — Migrer train/predict ML hors de `symbol_source=candidates`

**Objectif :** éviter de garder un gate implicite côté ML après avoir corrigé le backtest.

### Tâches structurantes

1. `ihm/services/pipeline_runner.py`
  - changer les defaults :
    - `ml_train_symbol_source`
    - `ml_predict_symbol_source`
  - la seule source nominale est `tradable-universe`.
  - `stock-bars-daily` reste une source d'administration / diagnostic, pas l'univers nominal, car elle ne porte pas les règles PIT de tradabilité.

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

### Tâches structurantes

1. `core/conviction.py`
  - introduire explicitement un mode `ml_primary` ou équivalent,
  - distinguer :
    - fusion pondérée normale,
    - veto score,
    - fallback score-only si ML manquant.

2. `config/capital_presets.yaml`
  - remplacer la sémantique "min score pour être candidat" par :
    - seuil veto long,
    - seuil veto short,
    - seuil minimum ML si nécessaire.

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

---

## Sprint 5 — Adapter l'IHM et les contrats d'options

**Objectif :** supprimer le mensonge fonctionnel dans l'IHM.

Aujourd'hui, l'IHM expose encore un modèle mental "selector universe -> ML". Tant que cela reste visible, l'utilisateur pilotera le nouveau backend avec de mauvaises attentes.

### Tâches structurantes

1. `ihm/services/pipeline_runner.py`
  - renommer les options internes :
    - `ml_include_selector_context` devient `ml_include_score_context`,
    - supprimer `ml_selector_universe_*`,
    - remplacer `filter_candidates_without_ml` par la politique de couverture ML de l'univers tradable.

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

5. documentation et glossaires
  - supprimer le concept opérationnel `candidate`.

### Fichiers concernés

- `database/stock_scores.py`
- `database/repositories/scores.py`
- `event_sentiment/db_io.py`
- `backtesting/fidelity.py`
- `doc/**/*.md`

---

## Sprint 7 — Nettoyage final du schéma candidate

**Objectif :** retirer les colonnes et index candidate devenus sans lecteur ni writer.

### Tâches

1. Supprimer les colonnes `is_candidate` et `candidate_rank` de `stock_scores` et `stock_scores_history` après migration des données nécessaire à l'audit.
2. Supprimer les index SQL `idx_history_candidate` et `idx_history_preset_candidate`.
3. Supprimer ou réécrire les migrations, DDL downgrade et scripts de backfill spécifiques aux candidats.
4. Ne pas ajouter `ml_rank` / `predicted_rank` tant qu'un besoin concret d'audit matérialisé n'existe pas.

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
3. Le ranking long/short est bien séparé.
4. Le score technique peut exclure un signal, mais ne définit plus seul l'univers.
5. Un run live `risk_management` utilise le même contrat d'univers que le backtest.

### Validation data / audit

1. La couverture ML sur l'univers servi augmente fortement.
2. Les diagnostics de missing ML sont exprimés relativement à l'univers tradable.
3. Le scope cross-sectionnel est cohérent entre train, predict et backtest.
4. Chaque sélection peut être reliée au snapshot d'univers, à la prédiction utilisée et au motif de rejet éventuel.

### Validation performance

1. `validate_score_predictiveness.py --source ml` sur 2024-2025 doit montrer une structure de buckets meilleure que le score technique brut.
2. Les backtests 2021+ doivent être rejoués avant toute suppression SQL de `is_candidate`.

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
