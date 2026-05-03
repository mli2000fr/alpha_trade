# Phase 1 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 1

La Phase 1 visait à rendre le backtest **beaucoup plus strict et explicite sur la fidélité PIT amont**, sans introduire de régression sur les pipelines live.

Principe retenu :
- **aucun changement destructif** sur les pipelines live 1→12 ;
- **aucun changement de comportement par défaut** pour le backtest standard ;
- tous les comportements stricts sont **opt-in** via de nouveaux paramètres dédiés au backtesting.

---

## Résumé des livrables réalisés

### 1. Séparation explicite des modes de backtest
Un nouveau mode a été introduit dans la CLI du backtest :
- `--engine-mode research`
- `--engine-mode pipeline`

#### Effet
- `research` = comportement historique, tolérant, rapide, compatible avec les usages existants ;
- `pipeline` = mode plus strict, exigeant des snapshots PIT corrects et exposant des diagnostics enrichis.

#### Sécurité anti-régression
Le mode par défaut reste `research`.
Cela garantit que les lancements existants, scripts déjà en place et usages IHM historiques ne changent pas tant que l’utilisateur ne demande pas explicitement le mode pipeline.

---

### 2. Contrat PIT strict pour le chargement des scores
Le chargement des scores dans `backtesting/data_loader.py` a été étendu pour introduire :
- `strict_pit=True|False`
- `return_diagnostics=True|False`

#### Nouveau comportement
En mode pipeline :
- si `stock_scores_history` n’existe pas → erreur explicite ;
- si `stock_scores_history` existe mais ne contient aucune ligne sur la période → erreur explicite ;
- le fallback silencieux vers `stock_scores` courant est interdit.

En mode research :
- le fallback vers `stock_scores` est conservé pour compatibilité.

#### Diagnostics ajoutés
Le chargement des scores expose maintenant des diagnostics structurés :
- table source utilisée ;
- mode strict demandé ou non ;
- présence ou non de `stock_scores_history` ;
- nombre de lignes PIT trouvées ;
- preset capital utilisé ;
- présence de `config_fingerprint` ;
- fallback éventuel ;
- raisons de dégradation.

---

### 3. Nouveau module de fidélité backtesting
Un nouveau module a été introduit :
- `backtesting/fidelity.py`

Il centralise les primitives Phase 1 :
- erreurs dédiées (`PitHistoryRequiredError`, `PitMlStrategyUnsupportedError`) ;
- objets de diagnostics scores / sentiment / ML ;
- manifeste de fidélité ;
- résolution explicite de stratégie ML PIT.

Ce module sert de socle pour les Phases 2 et 3.

---

### 4. Diagnostics PIT étendus côté sentiment
La fonction `prepare_scores_for_sentiment_mode(...)` a été étendue.

#### Nouvelles capacités
Elle peut maintenant :
- retourner les diagnostics (`return_diagnostics=True`) ;
- connaître le `engine_mode` (`research` ou `pipeline`) ;
- indiquer si des lignes ont été fallbackées sur `final_score` ;
- indiquer combien de dates ont été reconstruites ;
- indiquer si une écriture en base a été autorisée ou non ;
- tracer l’application éventuelle du walk-forward overlay.

#### Comportement important en mode pipeline
En `engine_mode="pipeline"` :
- `sentiment_mode=rebuild-missing` peut reconstruire des snapshots **en mémoire**,
- mais **n’écrit pas implicitement** dans `stock_scores_history`.

C’est un point de sûreté majeur pour éviter qu’un backtest pipeline modifie la base utilisée par les pipelines live.

---

### 5. Stratégie ML PIT explicite
Le backtest supporte maintenant un paramètre dédié :
- `--ml-pit-strategy`

Valeurs exposées :
- `auto`
- `use-persisted`
- `rebuild-missing`
- `walk-forward-train-then-predict`

#### Comportement actuel
- `auto` : comportement conservateur, rétrocompatible ;
- `use-persisted` : utilise uniquement ce qui existe déjà dans `model_predictions` ;
- `rebuild-missing` : reconstruit les prédictions manquantes via `predict_symbol(...)` ;
- `walk-forward-train-then-predict` : **fail-fast explicite** en Phase 1, car non encore supporté proprement.

#### Sécurité anti-régression
En mode pipeline :
- `rebuild-missing` reconstruit sans persister implicitement en base ;
- la stratégie non encore supportée échoue explicitement au lieu d’introduire un comportement ambigu.

---

### 6. Diagnostics PIT étendus côté ML
`prepare_predictions_for_ml_mode(...)` a été enrichie pour exposer :
- mode demandé ;
- stratégie ML PIT demandée ;
- stratégie effectivement utilisée ;
- nombre de prédictions d’entrée ;
- nombre de clés attendues ;
- nombre de prédictions manquantes ;
- nombre de prédictions reconstruites ;
- si un persist était autorisé ou non ;
- raisons de dégradation.

Cela permet maintenant de distinguer clairement :
- un run où le ML a été entièrement servi depuis l’historique existant,
- un run où le ML a été reconstruit partiellement,
- un run où des trous restent présents.

---

### 7. Manifeste de fidélité enrichi
Quand un `output_dir` est fourni, le backtest sauvegarde maintenant :
- `fidelity_manifest.json`

Le manifeste regroupe :
- `engine_mode` ;
- strict PIT demandé/satisfait ;
- fenêtre demandée ;
- preset capital ;
- diagnostics scores ;
- diagnostics sentiment ;
- diagnostics ML ;
- modes utilisés ;
- raisons globales de dégradation.

Le même bloc est aussi injecté dans `report.json` via la clé :
- `fidelity`

---

### 8. Schémas de rapport étendus
Les schémas de validation ont été étendus pour reconnaître le bloc `fidelity` :
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`

Cela permet aux futurs consommateurs IHM / API / dashboards de charger les rapports enrichis sans considérer ces champs comme étrangers.

---

### 9. Propagation safe dans l’IHM backtesting
L’IHM backtesting a été étendue côté **commande backtest uniquement** avec deux nouveaux champs :
- `engine_mode`
- `ml_pit_strategy`

#### Important
Cette propagation a été limitée à :
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`

Les pipelines live quotidiens 1→12 n’ont pas été modifiés.

Le mode par défaut exposé dans l’IHM reste :
- `engine_mode = research`
- `ml_pit_strategy = auto`

Donc l’IHM continue de produire par défaut un comportement compatible avec l’existant.

---

## Fichiers créés / modifiés dans la Phase 1

### Créés
- `backtesting/fidelity.py`
- `prompt/backtest/phase1.md`

### Modifiés
- `backtesting/cli/_impl.py`
- `backtesting/data_loader.py`
- `backtesting/resilience.py`
- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`
- `tests/test_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`
- `tests/test_pages_backtesting.py`

---

## Ce qui a été explicitement évité pour ne pas casser le live

### Non modifié dans cette phase
- `risk_management/*`
- `execution_engine/*`
- `ihm/services/pipeline_runner.py`
- les étapes live 1→12
- les flux live broker / risk / execution

### Règle de sûreté appliquée
Tout comportement plus strict ou plus fidèle a été introduit :
- soit derrière un flag (`engine_mode`, `ml_pit_strategy`),
- soit en mode non destructif (reconstruction en mémoire),
- soit avec fail-fast explicite quand la fonctionnalité n’est pas encore prête.

---

## Validation effectuée

Des tests ciblés ont été exécutés et validés sur :
- le backtesting principal ;
- le backfill PIT ;
- le runner IHM backtesting ;
- les références de paramètres de la page backtesting.

Les ajouts couvrent notamment :
- le mode `pipeline` strict sur `load_scores()` ;
- l’ajout du bloc `fidelity` dans `report.json` ;
- l’absence d’écriture implicite en mode pipeline pour sentiment / ML ;
- la propagation des nouveaux paramètres CLI / IHM.

---

## Limites connues à la fin de la Phase 1

La Phase 1 n’implémente pas encore :
- un vrai entraînement walk-forward ML à la date J ;
- le branchement sur le vrai `risk_management` ;
- la simulation d’exécution fidèle au `ProductionExecutor` ;
- la comparaison automatisée au live.

C’est normal : ces sujets relèvent des Phases 2 et 3.

---

## Résultat métier de la Phase 1

À la fin de la Phase 1, on peut dire :

- le backtest sait désormais distinguer clairement un run `research` d’un run `pipeline` ;
- il refuse en mode pipeline de se prétendre PIT si les snapshots PIT ne sont pas disponibles ;
- il rend visibles les dégradations sentiment / ML ;
- il évite les écritures implicites sur la base en mode pipeline ;
- il produit un manifeste de fidélité exploitable par les phases suivantes.

En revanche, on ne peut pas encore dire :
- que le backtest rejoue tout le pipeline live ;
- ni qu’il est équivalent au live côté risk / exécution.

---

## Prochaine étape logique

La suite naturelle est la **Phase 2** :
- brancher le backtest pipeline-fidèle sur le vrai chemin `risk_management`,
- rapprocher fortement la simulation d’exécution du moteur `execution_engine`.

