# E5 — Direction quotidienne du régime Oracle

## Statut et objectif

E5 est une expérience de recherche, non branchée au serving ou au backtest. Elle
teste si la direction est plus prévisible comme facteur commun quotidien que
comme propriété individuelle de chaque symbole.

Une ligne E5 représente une date. Le modèle reçoit des agrégats PIT du marché et
des candidats Oracle TOP20 présents à cette date, puis prédit la proportion
future de candidats dont la barrière haussière sera touchée avant la barrière
baissière.

```text
Oracle OOF TOP20 par symbole
          │
          ├── agrégation des features connues au signal J
          ├── labels E4 UP_FIRST / DOWN_FIRST
          └── replays économiques E3 LONG / SHORT
                         │
                         ▼
               une observation par date
                         │
                 Ridge + CatBoost compact
                         │
            LONG_DAY / SHORT_DAY / ABSTAIN
```

Tous les artefacts déclarent `research_only=true` et `serving_ready=false`.

## Motivation empirique

Sur les 1 134 dates OOS d’E4, environ 68 événements directionnels sont présents
par date. Le côté réalisé majoritaire représente en moyenne 68,9 % du pool ; sa
médiane est 68,0 %. Sur 71,3 % des dates, au moins 60 % des événements vont dans
le même sens. Cette cohérence commune justifie un test au niveau quotidien,
malgré l’échec de la prédiction per-symbol.

Ces chiffres sont un plafond réalisé et non une stratégie : E5 doit encore
prouver que la majorité future est prédictible avec des données disponibles à J.

## Population et causalité

- source : cache Oracle strictement OOF du batch indiqué ;
- gate : percentile Oracle supérieur ou égal à 80 % ;
- score Oracle individuel interdit comme feature ;
- agrégats quotidiens de la distribution du score autorisés ;
- minimum 20 événements directionnels par date ;
- ATR et features connus au close J ;
- entrée économique à l’open J+1 ;
- purge Walk-Forward de 20 séances ;
- validation utilisée pour l’early stopping ; test exclusivement OOS.

Les dates sans horizon futur complet ne reçoivent pas de label. `NO_TOUCH` et
`AMBIGUOUS` ne participent pas au dénominateur directionnel mais restent comptés
dans les diagnostics de couverture amont.

## Cible

Pour une date `d` :

```text
up_rate(d) = UP_FIRST / (UP_FIRST + DOWN_FIRST)
target(d)  = 2 × up_rate(d) − 1
```

La cible continue appartient à `[-1,+1]` :

- `+1` : toutes les premières touches sont haussières ;
- `0` : équilibre 50/50 ;
- `−1` : toutes sont baissières.

Cette régression conserve l’intensité de la majorité. Une classification binaire
perdrait la différence entre 51/49 et 90/10.

## Features quotidiennes

Le contrat contient 23 features, sans sélection automatique :

### Marché commun

- moyenne du rendement SPY sur 20 jours ;
- distance du SPY à sa moyenne 50 jours ;
- indicateur bull market ;
- indicateur risk-off.

### Médianes du pool Oracle

- rendement journalier ;
- momentum 5, 20 et 60 jours ;
- force relative 20 jours ;
- distance SMA20 ;
- RSI14 ;
- position dans le range 20 jours.

### Breadth du pool

Proportion de valeurs positives pour : rendement journalier, momentum 5/20/60,
force relative 20 et distance SMA20.

### Dispersion

Écart-type cross-sectionnel du rendement journalier, du momentum 20 et de la
force relative 20.

### Oracle

Moyenne et dispersion quotidiennes du percentile Oracle. Ces deux variables
décrivent l’intensité/concentration du gate ; aucune probabilité individuelle
n’est transmise au modèle.

Les targets, rendements futurs, classes E4, identifiants de symbole et dates de
disponibilité sont explicitement exclus des features.

## Modèles préfixés

### Ridge

- imputation par médiane du train ;
- standardisation du train ;
- régression Ridge avec `alpha=10` ;
- aucun réglage d’hyperparamètre.

### CatBoost

- régression RMSE ;
- profondeur 4 ;
- 400 itérations maximum ;
- learning rate 0,03 ;
- `l2_leaf_reg=10` ;
- early stopping 60 ;
- seed 42 ;
- aucun tuning.

Les deux modèles publient leurs OOS séparément. Il n’existe pas de sélection de
champion fondée sur les folds de test.

## Politique directionnelle

Politique primaire fixée avant le run :

```text
prediction >= +0,20 : LONG_DAY
prediction <= −0,20 : SHORT_DAY
sinon                : ABSTAIN
```

Une valeur de `±0,20` correspond à une majorité attendue de 60/40. Les seuils
0,00, 0,10, 0,20 et 0,30 sont publiés comme diagnostics ; ils ne constituent pas
un sweep permettant de retenir après coup le meilleur résultat.

## Évaluation économique

Pour chaque date sélectionnée, E5 applique le même côté à tout le panier Oracle :

- LONG_DAY : moyenne équipondérée des replays LONG E3 ;
- SHORT_DAY : moyenne équipondérée des replays SHORT E3.

Le replay E3 emploie stop 2,5 ATR, TP `min(3 ATR,7 %)`, horizon H20 et coûts. Il
n’est pas le lifecycle production et sert uniquement à mesurer l’utilité du
signal commun.

Comparaisons appariées sur les mêmes dates :

- toujours LONG ;
- toujours SHORT ;
- espérance random 50/50 ;
- meilleur côté statique ;
- règles de signe SPY tendance 50 et rendement 20.

## Métriques et gates

Mesures : Pearson, Spearman, RMSE, MAE, couverture, précision du côté majoritaire,
répartition LONG/SHORT, rendement moyen du panier, lift, taux de journée positive,
perte catastrophique du panier, CVaR 5 %, résultats par fold et semestre.

Gates simultanés :

- Spearman global et moyen des folds ≥ 0,10 ;
- au moins 7 folds avec IC positif ;
- couverture ≥ 30 % ;
- précision ≥ 58 % ;
- lift de précision contre la majorité statique ≥ 5 points ;
- chaque côté représente au moins 15 % des décisions ;
- rendement moyen positif ;
- lift contre random ≥ 0,25 point ;
- au moins 7 folds à lift positif et 7 à rendement positif ;
- au moins 7 folds battent le meilleur côté statique.

## Artefacts

Répertoire `artifacts/models/shared_directional/shared-daily-regime-*` :

- `contract.json` ;
- `metrics.json` ;
- `daily_feature_contract.json` ;
- `daily_panel.parquet` ;
- `oof_predictions.parquet` ;
- `ridge_model.joblib` ;
- `catboost_model.cbm`.

## Commande canonique

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_daily_regime --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --min-daily-candidates 20 --primary-threshold 0.20 --ridge-alpha 10.0 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 400 --depth 4 --learning-rate 0.03 --log-level INFO
```

## Résultat de la campagne canonique du 6 septembre 2026

Artefact : `shared-daily-regime-20260906092533-0802c8`.

Le panel contient 1 720 dates et 114 275 événements. Les prédictions OOS
couvrent 1 008 dates sur 8 folds, du 23 février 2021 au 5 mars 2025.

Ridge : Spearman global 0,0000 et moyenne des folds 0,0045. Au seuil primaire,
la couverture vaut 8,93 %, la précision 47,78 % et le rendement +0,63 %, mais
ce rendement reste inférieur au meilleur côté statique des mêmes dates
(+1,29 %). Ridge valide 3 gates sur 12.

CatBoost : Spearman global -0,0078 et moyenne des folds -0,0048. Il ne produit
aucune sélection au seuil primaire et ne valide aucun gate sur 12.

Les baselines SPY obtiennent moins de 46 % de précision. La persistance J-20
donne un Spearman de 0,025 et une précision de signe de 47,65 %. La cohérence
quotidienne existe a posteriori, mais son sens n’est pas prévisible avec les
features PIT courantes. E5 est rejeté sans sweep ni branchement production.

## Règle de décision après campagne

- Si CatBoost ou Ridge passe tous les gates : confirmer sur une période encore
  invisible avant toute intégration.
- Si l’IC est positif mais la politique n’est pas rentable : le régime commun
  est partiellement prévisible mais mal aligné avec le replay économique.
- Si le seuil primaire ne sélectionne rien mais que l’IC est bon : problème de
  calibration ; ne pas choisir un seuil sur les mêmes tests.
- Si l’IC moyen est proche de zéro : la cohérence quotidienne n’est observable
  qu’a posteriori et la piste est rejetée avec les données PIT courantes.
