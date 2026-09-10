# E4-B — Contrôle binaire de première touche

## Objectif

E4-B vérifie si l’échec d’E4 provient de sa formulation à quatre classes. Dans
E4, `NO_TOUCH` et surtout `AMBIGUOUS` étaient extrêmement rares mais recevaient
un poids automatique très élevé. Le modèle prédisait alors ces deux classes
beaucoup trop souvent et sa politique s’abstenait presque partout.

E4-B conserve strictement le même univers, les mêmes features PIT, les mêmes
barrières et les mêmes folds. Une seule variable change : l’apprentissage
devient binaire, sans pondération des classes.

Ce module est une expérience de recherche : `research_only=true` et
`serving_ready=false`. Il n’est relié ni au serving, ni à la table des
prédictions, ni à la cascade du backtest.

## Différence exacte avec E4

| Élément | E4 | E4-B |
|---|---|---|
| Classes vues pendant le fit | 4 | `DOWN_FIRST`, `UP_FIRST` |
| `NO_TOUCH` / `AMBIGUOUS` dans le fit | Oui | Non |
| Pondération | `Balanced` | Aucune |
| Sortie du modèle | 4 probabilités | `P(UP)` et `1-P(UP)` |
| Classes rares dans les tests OOS | Oui | Oui |
| Contrat de barrière | Symétrique | Identique |
| Folds Walk-Forward | Causaux | Identiques |

Les classes rares sont supprimées uniquement du train et de la validation. Les
partitions de test les conservent. Ainsi, une décision LONG ou SHORT émise sur
un vrai `NO_TOUCH` ou `AMBIGUOUS` pénalise la précision de la politique.

## Cible

Pour chaque événement Oracle TOP20 OOF :

```text
DOWN_FIRST -> 0
UP_FIRST   -> 1
NO_TOUCH   -> absent du fit
AMBIGUOUS  -> absent du fit
```

Le label sous-jacent est construit comme dans E4 :

- information arrêtée au close du signal J ;
- ATR de Wilder 14 connu à J ;
- entrée à l’open J+1 ;
- rejet si le gap absolu dépasse 3 % ;
- aucune touche autorisée pendant la séance d’entrée ;
- barrières symétriques `min(3×ATR, 7 %)` ;
- horizon de 20 séances ;
- double touche sur la même barre quotidienne classée `AMBIGUOUS` ;
- horizon incomplet en fin de données laissé sans label.

## Modèle

CatBoost binaire avec :

- `Logloss` ;
- métrique de validation `AUC` ;
- aucune pondération automatique ou manuelle ;
- maximum 600 itérations ;
- profondeur 6 ;
- learning rate 0,03 ;
- early stopping après 60 itérations ;
- seed 42 ;
- aucun contexte symbole/secteur par défaut.

Le profil par défaut reste
`config/features/shared_direction/shared.json`. Le score Oracle sert uniquement
à constituer le TOP20 OOF et n’est jamais fourni au modèle.

## Politique préfixée

```text
marge = |P(UP_FIRST) - P(DOWN_FIRST)|

si P(UP) >= 0,5 et marge >= 0,10 : LONG
si P(UP) <  0,5 et marge >= 0,10 : SHORT
sinon                            : ABSTAIN
```

Les marges `0`, `0,05`, `0,10` et `0,15` sont publiées pour diagnostic. La
marge primaire reste `0,10`. Il est interdit de promouvoir après coup la marge
qui affiche le meilleur rendement sur ces mêmes données.

## Évaluation

Les sorties sont converties dans le même schéma que celui d’E4 afin de comparer
les deux expériences sans ambiguïté :

- AUC UP contre DOWN sur les vrais événements directionnels ;
- précision en conservant les classes rares dans le dénominateur OOS ;
- couverture et répartition LONG/SHORT ;
- rendement du replay E3 du côté choisi ;
- lift contre un choix 50/50 et contre le meilleur côté statique ;
- stabilité par fold et semestre ;
- perte catastrophique, CVaR et concentration par symbole.

Les gates sont identiques à E4. E4-B n’est concluant que si l’amélioration est à
la fois statistique, économique et stable. Une meilleure couverture seule ne
suffit pas.

## Interprétation

- Si E4-B obtient une AUC nettement supérieure à E4 et passe les gates, la
  surpondération des classes rares était la cause principale de l’échec E4.
- Si la couverture augmente mais que l’AUC reste proche de 0,50, le modèle est
  simplement plus souvent forcé à choisir une direction sans mieux la connaître.
- Si l’AUC s’améliore mais pas le rendement, l’ordre de première touche n’est pas
  aligné avec l’utilité économique du replay.
- Si E4-B échoue également, la piste « première barrière touchée » doit être
  fermée pour ce profil de features, sans sweep de seuils.

## Résultat de la campagne canonique du 6 septembre 2026

Artefact : `shared-first-touch-binary-20260906085319-0802c8`.

Le run produit 78 538 prédictions OOS sur 9 folds, du 5 janvier 2021 au
11 juillet 2025. Après exclusion de `NO_TOUCH` et `AMBIGUOUS`, 111 703 lignes
binaires environ sont utilisables pour le fit.

- AUC globale : 0,4831 ; moyenne des folds : 0,5011 ; 5 folds sur 9 > 0,50 ;
- marge primaire 0,10 : couverture 4,10 %, précision 41,09 % ;
- rendement net moyen -2,36 % ; lift contre 50/50 : -2,07 points ;
- un seul fold à lift positif et un seul fold battant le meilleur côté statique ;
- 1 gate sur 11 validé.

Le mapping CatBoost a été contrôlé : `[0, 1]`, avec `1=UP_FIRST`. L’échec
n’est donc pas une inversion technique. E4-B échoue davantage qu’E4 : la
formulation multiclasses expliquait la surabstention, mais pas l’absence de
signal directionnel. La piste « première barrière touchée » est rejetée pour le
profil courant, sans sweep de marge ni branchement production.

## Artefacts

Le run est écrit sous
`artifacts/models/shared_directional/shared-first-touch-binary-*` :

- `contract.json` ;
- `metrics.json` ;
- `oof_predictions.parquet` ;
- `first_touch_binary_model.cbm` ;
- `feature_profile.json`.

## Commande de référence

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.first_touch_binary --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --barrier-atr-mult 3.0 --barrier-max-pct 0.07 --max-sessions 20 --max-entry-gap-pct 0.03 --primary-margin 0.10 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --log-level INFO
```
