# Evolution 12 — Persistance DB challengers/champion pour `modelFactory`

## Objectif
Cette évolution poursuit le point 2 listé dans `prompt/ml/11.evo_ihm.md` :

> persister aussi en DB des informations challengers/champion plus détaillées

Jusqu’ici, la gouvernance multi-modèles était surtout lisible dans les artefacts disque `config.json` / `metrics.json` par symbole.
La page `ML` savait déjà exploiter ces artefacts, mais la base SQL ne gardait pas une vue structurée du ranking challengers/champion par run.

Le but de cette évolution est donc de rendre cette gouvernance **audit-able en base**, sans casser le fonctionnement existant fondé sur les artefacts.

---

# 1. Ce qui a été implémenté

## 1.1 Nouvelle table SQL `model_governance`
Une nouvelle table a été ajoutée :

- `database/sql/ml/model_governance.sql`

Elle persiste, pour chaque `run_id` / `symbol` / `model_name`, une ligne de gouvernance contenant notamment :

- `rank`
- `is_selected_model`
- `selection_mode`
- `selection_metric`
- `selection_score`
- `model_status`
- `selection_eligible`
- `eligibility_reason`
- `reason`
- `inference_backend`
- `backend_model_name`
- `calibration_method`
- `decision_threshold`
- `artifact_symbol`
- chemins artefacts (`checkpoint_path`, `scaler_path`, `model_path`, `config_path`, `calibrator_path`)
- métriques utiles à l’audit (`val_auc`, `test_auc`, `wf_auc`, `val_threshold_business_score`, `test_threshold_business_score`, `wf_threshold_business_score`)

### Intérêt métier
Cette table permet maintenant de répondre beaucoup plus facilement à des questions comme :

- quel challenger était classé premier sur ce run ?
- quel modèle a été réellement retenu comme champion ?
- un challenger a-t-il été écarté parce qu’il n’était pas éligible au serving ?
- quel backend d’inférence était prévu pour ce modèle ?
- quel seuil et quelle calibration étaient associés au modèle servi ?

---

## 1.2 Migration Alembic ajoutée
Une migration a été créée :

- `alembic/versions/0006_add_model_governance_table.py`

### Effet
Elle crée proprement la table `model_governance` avec :

- une contrainte d’unicité sur `(run_id, symbol, model_name)` ;
- des index utiles pour l’IHM et les audits :
  - `idx_model_governance_symbol`
  - `idx_model_governance_run`
  - `idx_model_governance_selected`
  - `idx_model_governance_rank`

Cela aligne :

- le schéma Alembic ;
- le DDL manuel dans `database/sql/ml/model_governance.sql` ;
- le code Python de persistance.

---

## 1.3 `modelFactory/db_registry.py` sait construire et persister la gouvernance
Le module `modelFactory/db_registry.py` a été enrichi avec deux briques :

### `build_governance_rows(...)`
Cette fonction transforme les structures Python déjà présentes dans `trainer` / `orchestrator` en lignes normalisées prêtes pour la DB.

Elle fusionne :

- les challengers annotés ;
- le ranking ;
- les routes d’artefacts ;
- le champion final ;
- les métriques utiles au tri et à l’audit.

### `replace_model_governance(...)`
Cette fonction remplace le snapshot de gouvernance pour un couple `(run_id, symbol)` :

1. suppression des lignes existantes pour ce run/symbole ;
2. réinsertion du snapshot courant.

### Robustesse
Comme pour l’évolution 11 sur `model_predictions`, la persistance ne casse pas brutalement le runtime si le schéma n’est pas encore migré.

Si la table n’existe pas encore ou qu’une insertion échoue côté schéma, le code :

- loggue un warning ;
- n’interrompt pas le flux d’entraînement.

Cela évite qu’un entraînement soit marqué en échec uniquement parce que la migration n’a pas encore été appliquée.

---

## 1.4 `trainer.py` persiste la gouvernance finale par symbole
Dans `modelFactory/trainer.py`, une fois le run terminé et le champion sélectionné, le code persiste maintenant le snapshot DB correspondant.

### Ce qui est enregistré
Pour chaque symbole entraîné, la DB reçoit la photographie finale de gouvernance du run :

- le champion retenu ;
- les challengers présents ;
- leur rang ;
- leur éligibilité ;
- leurs scores ;
- leur backend prévu ;
- leurs métriques d’évaluation utiles.

### Résultat
La base n’est plus limitée à :

- `model_training_run`
- `model_metrics`
- `model_predictions`

Elle garde aussi la gouvernance multi-modèles qui justifie le choix du champion.

---

## 1.5 `orchestrator.py` republie la gouvernance après injection du `global_model`
Un point important : la gouvernance finale peut changer après l’ajout du `global_model` dans `modelFactory/orchestrator.py`.

Sans traitement complémentaire, la DB aurait pu rester cohérente pour le run local initial, mais devenir incomplète sur la décision finale si le `global_model` est injecté ensuite.

### Nouveau comportement
Après `_inject_global_model_into_symbol_artifacts(...)` :

- les artefacts symbole sont mis à jour comme avant ;
- la table `model_governance` est aussi resynchronisée pour refléter la gouvernance finale.

### Conséquence
Si le `global_model` devient champion, la DB reflète bien cet état final.

---

## 1.6 `ihm/services/queries.py` expose la nouvelle vue DB
Une nouvelle requête IHM a été ajoutée :

- `get_model_governance(limit=..., symbol=...)`

Elle permet de lire directement la gouvernance challengers/champion depuis la base.

### Colonnes exposées
La requête remonte notamment :

- `run_id`
- `symbol`
- `model_name`
- `rank`
- `is_selected_model`
- `selection_mode`
- `selection_metric`
- `selection_score`
- `model_status`
- `selection_eligible`
- `eligibility_reason`
- `inference_backend`
- `backend_model_name`
- `calibration_method`
- `decision_threshold`
- les métriques `auc` / `threshold_business_score`

---

## 1.7 La page `ML` montre maintenant aussi la gouvernance DB
La page :

- `ihm/pages/ml.py`

propose désormais une section dédiée :

- **Gouvernance challengers / champion**

### Rôle de cette section
Elle affiche la table `model_governance` filtrée sur le symbole sélectionné quand c’est possible.

### Répartition des rôles après cette évolution
- **Artefacts** : restent la source la plus riche pour les manifestes complets et le détail brut.
- **DB** : devient une vraie source d’audit quotidien pour le ranking challengers/champion.

La page `ML` combine donc mieux :

- artefacts détaillés ;
- audit SQL exploitable immédiatement.

---

## 1.8 Métadonnées IHM / admin mises à jour
Les métadonnées de tables ont été complétées pour inclure `model_governance` dans le périmètre ML :

- `ihm/services/db_admin.py`
- `ihm/services/pipeline_runner.py`

### Effet
La table apparaît comme une table métier ML légitime et l’étape `ML Train` annonce explicitement qu’elle l’alimente.

---

# 2. Fichiers modifiés

## Code
- `modelFactory/db_registry.py`
- `modelFactory/trainer.py`
- `modelFactory/orchestrator.py`
- `ihm/services/queries.py`
- `ihm/pages/ml.py`
- `ihm/services/db_admin.py`
- `ihm/services/pipeline_runner.py`

## Nouveaux fichiers
- `database/sql/ml/model_governance.sql`
- `alembic/versions/0006_add_model_governance_table.py`
- `prompt/ml/12.evo_6.m`

## Tests
- `tests/test_model_factory_db_registry.py`
- `tests/test_model_factory_trainer.py`
- `tests/test_model_factory_orchestrator.py`
- `tests/test_services_queries.py`

---

# 3. Contrat DB final de `model_governance`

## Clé logique
Une ligne par :

- `run_id`
- `symbol`
- `model_name`

## Informations de sélection
- `rank`
- `is_selected_model`
- `selection_mode`
- `selection_metric`
- `selection_score`
- `selection_eligible`
- `eligibility_reason`
- `model_status`
- `reason`

## Informations de serving
- `inference_backend`
- `backend_model_name`
- `calibration_method`
- `decision_threshold`
- `artifact_symbol`

## Traçabilité artefacts
- `checkpoint_path`
- `scaler_path`
- `model_path`
- `config_path`
- `calibrator_path`

## Métriques d’audit
- `val_auc`
- `test_auc`
- `wf_auc`
- `val_threshold_business_score`
- `test_threshold_business_score`
- `wf_threshold_business_score`

---

# 4. Impact sur l’exploitation quotidienne

## Avant
Pour comprendre pourquoi un champion avait été servi, il fallait souvent :

1. ouvrir les artefacts du symbole ;
2. retrouver le ranking challengers ;
3. reconstituer les raisons d’éligibilité ;
4. recroiser cela avec les routes d’inférence.

## Maintenant
Une partie significative de cette lecture est directement disponible en base.

### Exemples de questions désormais plus simples
- quel champion a été retenu pour `AAPL` sur le dernier run ?
- `lightgbm` était-il classé premier mais non éligible ?
- le `global_model` a-t-il remplacé le champion local ?
- quel backend d’inférence était prévu pour chaque challenger ?
- quel score de sélection et quelle métrique ont conduit à la décision ?

---

# 5. Validation exécutée

## Suite ciblée
```powershell
Set-Location "C:\Users\MLI\PycharmProjects\alpha_trade"
python -m pytest tests/test_model_factory_db_registry.py tests/test_model_factory_trainer.py tests/test_model_factory_orchestrator.py tests/test_services_queries.py tests/test_pages_ml.py --no-cov -q
```

## Suite élargie
```powershell
Set-Location "C:\Users\MLI\PycharmProjects\alpha_trade"
python -m pytest tests/test_model_factory_predictor.py tests/test_model_factory_db_registry.py tests/test_model_factory_trainer.py tests/test_model_factory_orchestrator.py tests/test_services_queries.py tests/test_services_ml_artifacts.py tests/test_pages_ml.py tests/test_pages_pipeline.py tests/test_ihm_pipeline_runner.py tests/test_ihm_process_registry.py --no-cov -q
```

## Résultat
- **suites passées**

---

# 6. Verdict technique

Cette évolution comble un vrai manque de traçabilité SQL autour de `modelFactory`.

## Gains principaux
1. **Audit DB enrichi** de la gouvernance challengers/champion.
2. **Vision par run et par symbole** directement en SQL.
3. **Cohérence avec le serving final**, y compris après injection du `global_model`.
4. **IHM ML plus exploitable** grâce à la nouvelle vue DB.
5. **Déploiement robuste** grâce au fallback si la migration n’est pas encore appliquée.

## Limite volontaire conservée
Les artefacts restent la source la plus complète pour les manifestes bruts et certaines informations très détaillées.

Mais la DB devient désormais suffisamment riche pour la majorité des audits opérateurs quotidiens autour du choix du champion.

---

# 7. Suite logique possible
Les évolutions cohérentes après ce point seraient par exemple :

1. ajouter dans la page `ML` une vue historique dédiée par `run_id` et par symbole ;
2. créer des filtres IHM plus fins sur `selection_mode`, `selected_model` et `selection_eligible` ;
3. relier explicitement `model_governance` et `model_predictions` pour naviguer d’une prédiction servie vers le snapshot de gouvernance qui l’a produite.

