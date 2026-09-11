# E7 — Surveillance quotidienne des positions : KEEP / EXIT

## Statut et objectif

E7 cherche à répondre à une question différente de la direction initiale :

> Une fois une position LONG ouverte, les informations connues aujourd'hui
> permettent-elles d'estimer si la conserver possède encore une espérance
> supérieure à une sortie au prochain open ?

Le premier étage `E7-A_DATASET_AUDIT` est implémenté dans
`modelFactory/position_keep_exit_dataset.py`. Il est strictement
`research_only` : aucune table, aucun modèle de serving, aucun backtest et
aucun flux live ne sont modifiés. L'entraînement reste explicitement interdit
dans le manifeste tant que la qualité du dataset réel n'a pas été auditée.

## Population figée

E7 réutilise les trades `fixed_h20` de la variante 2 :

```text
Oracle H20 TOP20 à J
prix J→J+5 positif
consensus H5/H10/H15 encore confirmé à J+5
entrée LONG au premier open suivant J+5
lifecycle PROD, échéance maximale H20
```

Ce choix maintient les mêmes entrées que l'expérience précédente. E7 ne crée
pas a posteriori une nouvelle cohorte plus favorable. Les événements peuvent
se chevaucher : il s'agit d'un dataset de recherche trade-level, pas encore
d'un portefeuille avec contraintes de capacité.

## Une ligne = une décision causalement exécutable

Une ligne est créée uniquement si la position est encore ouverte à la clôture
de `state_date` :

```text
close state_date : toutes les features deviennent observables
open execution_date : sortie immédiate possible
terminal_date : résultat futur du lifecycle H20 témoin
```

Les états du jour où un stop ou TP a déjà clôturé la position sont exclus. Les
assertions imposent `state_date < execution_date <= label_end_date`.

La clôture de la 20e séance d'une position `fixed_h20` est également exclue :
la liquidation au prochain open est obligatoire et ne constitue donc pas une
décision à apprendre.

`label_end_date` couvre le plus tardif entre la sortie terminale et les labels
diagnostiques H3/H5. `trade_id = YYYYMMDD:SYMBOL` regroupe toutes les journées issues d'une même
position. Toutes ces journées devront rester dans la même partition lors des
expériences ML.

## Features PIT

### État et trajectoire de la position

- âge et séances restantes jusqu'à H20 ;
- PnL brut et net marqué à la clôture ;
- MFE et MAE observés depuis l'entrée ;
- drawdown depuis le plus haut atteint ;
- distance au TP et au stop/trailing actif ;
- ATR d'entrée, figé avant l'open d'entrée ;
- rendements 1/3/5 jours et volatilités réalisées 5/10 jours, calculés sur
  l'historique PIT antérieur même lorsque la position vient d'être ouverte ;
- ratio du volume courant à sa moyenne disponible sur 20 observations.

### Oracle multi-horizon

- percentiles OOF H5/H10/H15/H20 à `state_date` ;
- moyenne, dispersion et rang du consensus ;
- variation H5 sur une et trois observations ;
- indicateur H5 TOP20.

Les scores sont joints exactement sur `(state_date, symbol)`. Une absence reste
`NaN` ; elle n'est jamais convertie en rejet ou confirmation.

### Marché

- rendements SPY 1/5 jours ;
- volatilité SPY sur cinq jours ;
- rendements du symbole relatifs à SPY sur 1/5 jours.

Le symbole, la raison de sortie terminale et toutes les cibles futures sont
explicitement exclus du contrat de features.

## Labels conservés

| Colonne | Définition |
|---|---|
| `immediate_exit_net` | rendement total si sortie au prochain open |
| `keep_terminal_net` | rendement terminal du lifecycle H20 |
| `target_keep_advantage` | terminal H20 moins sortie immédiate |
| `target_future_residual` | rendement futur terminal depuis le prochain open |
| `label_keep` | 1 si ce rendement résiduel est positif |
| `label_tp_before_stop` | le lifecycle termine au TP |
| `label_stop_before_tp` | le lifecycle termine au stop initial ou trailing |
| `future_return_h3/h5` | rendement brut futur depuis l'open exécutable |
| `future_mfe_h5/future_mae_h5` | excursions futures sur cinq séances |

`label_keep` est une cible de recherche, pas encore une politique. Un modèle
ne sera autorisé que si l'audit montre une séparation temporellement stable.

## Artefacts E7-A

Chaque run écrit sous `artifacts/research/position_keep_exit/` :

| Fichier | Rôle |
|---|---|
| `position_states.parquet` | dataset quotidien complet |
| `univariate_deciles.csv` | déciles descriptifs de chaque feature |
| `feature_contract.csv` | liste fermée des features autorisées |
| `report.json` | filiation, empreintes, couverture et contrat anti-fuite |

Le rapport publie le nombre de trades et d'états, la période, la fréquence du
label KEEP, la couverture de chaque feature et la stabilité par semestre.

## Gate avant E7-B

L'audit doit vérifier avant tout entraînement : couverture des features,
horloge, duplications, plusieurs semestres, stabilité du signe, monotonie et
distribution non dégénérée des labels et durées. Un signal univarié intéressant
n'autorise pas la production. Il ouvre E7-B : régression logistique témoin,
puis LightGBM/CatBoost, avec Walk-Forward groupé par `trade_id` et purge telle
que `label_end_date` de l'entraînement précède le bloc évalué.

## Commande E7-A

```powershell
python -u -m modelFactory.position_keep_exit_dataset --lifecycle-artifact artifacts/research/oracle_rolling_lifecycle/oracle-rolling-lifecycle-20260910154636 --min-states-per-bin 100 --log-level INFO
```

Le run est terminé lorsque `report.json` existe dans le nouveau dossier
`position-keep-exit-dataset-*` affiché en fin de traitement.

## Audit préliminaire du premier run — artefact remplacé requis

Le premier artefact `position-keep-exit-dataset-20260910165656` a produit
201 050 états sur 29 449 trades, avec un label KEEP équilibré à 50,79 %. Il a
confirmé une dérive importante selon les semestres et un signal principalement
porté par l'état de la position. Les percentiles Oracle ont une relation faible
et changent fréquemment de signe selon les semestres.

Deux défauts de contrat ont été identifiés avant tout entraînement : 1 373 états
correspondaient à la clôture H20 précédant une liquidation obligatoire et ne
constituaient pas une décision ; les rendements et volatilités techniques
étaient calculés seulement depuis l'entrée, donnant une fausse couverture
partielle aux positions jeunes. Le constructeur a été corrigé et testé. Cet
artefact initial ne doit pas être utilisé pour E7-B ; la commande E7-A doit être
relancée afin de produire l'artefact canonique corrigé.

## Résultat E7-A corrigé — `GO_E7_B_RESEARCH`

L'artefact canonique `position-keep-exit-dataset-20260910172844` contient
199 677 états et 29 449 trades, du 13 juillet 2018 au 8 mai 2024. Le label KEEP
est équilibré à 51,14 %, aucune décision H20 forcée ne subsiste et toutes les
features ont une couverture de 100 %, sauf la distance au stop à 99,98 %.

La relation temporelle reste fortement dépendante du régime : l'avantage moyen
de KEEP varie de `-2,41 %` en 2022H1 à `+1,52 %` en 2022H2. Les percentiles
Oracle et leurs variations ont une association faible et changent de signe
selon les semestres. À l'inverse, PnL courant, drawdown, distance au stop/TP,
MFE/MAE et volatilité montrent suffisamment de structure pour justifier un test
ML purgé, sans autoriser de conclusion de production.

## E7-B — Walk-Forward et replay économique

`modelFactory/position_keep_exit_walk_forward.py` évalue trois challengers :

1. régression logistique sur `label_keep`, calibrée par Platt sur validation ;
2. LightGBM classifier sur `label_keep`, également calibré sur validation ;
3. LightGBM Huber sur `target_keep_advantage`.

Les lignes d'un trade reçoivent ensemble le même poids total. Le train impose
`label_end_date < val_start`, la validation impose
`label_end_date < test_start`, et les cohortes de validation/test commencent
après leur frontière afin d'éviter une politique tronquée. Aucun `trade_id` ne
peut traverser deux partitions.

Chaque fold choisit son seuil uniquement sur sa validation. La grille contient
une politique sentinelle « ne jamais sortir » : un modèle incapable de battre
H20 en validation n'est pas forcé à générer des exits. Sur le test OOS, la
première décision EXIT par trade est exécutée au prochain open ; sinon le trade
conserve son résultat H20.

Le gate primaire porte sur le delta net apparié contre H20, agrégé par date de
signal et bootstrapé en blocs. `GO_RESEARCH` exige au moins cinq folds, un delta
moyen positif, une borne IC95 basse positive et au moins 60 % de folds positifs.
Même un GO reste `research_only` et n'autorise ni serving ni backtest principal.

### Commande E7-B

```powershell
python -u -m modelFactory.position_keep_exit_walk_forward --dataset-artifact artifacts/research/position_keep_exit/position-keep-exit-dataset-20260910172844 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 8 --bootstrap-samples 2000 --log-level INFO
```

Le run écrit `fold_metrics.csv`, `oos_policy_trades.parquet` et `report.json`
dans un dossier `position-keep-exit-wf-*`.

## Résultat E7-B — `FAIT_NO_GO`

Artefact canonique : `position-keep-exit-wf-20260910175119`. Six folds OOS
couvrent janvier 2021 à janvier 2024 et 16 609 trades par challenger.

| Modèle | AUC état | Delta net/trade | Delta quotidien | Folds positifs | Sorties |
|---|---:|---:|---:|---:|---:|
| Logistique KEEP | 0,637 | +0,013 % | -0,044 % | 2/6 | 31,8 % |
| LightGBM KEEP | 0,638 | +0,047 % | -0,019 % | 1/6 | 32,7 % |
| LightGBM avantage | n/a | +0,080 % | +0,013 % | 2/6 | 42,9 % |

Le challenger avantage est le meilleur en moyenne par trade, mais son IC95
quotidien `[-0,484 % ; +0,516 %]` englobe largement zéro. Sa corrélation OOS
moyenne avec l'avantage futur est même négative (`-0,016`). Aucun modèle ne
passe le gate de stabilité.

L'attribution par fold révèle une bascule de régime : en 2022H1, sortir presque
tous les trades améliore le rendement d'environ `+1,40 %` par trade parce que le
témoin est très mauvais. Au fold suivant, 2022H2, la même politique sort encore
environ 99,5 % des trades et détruit environ `-0,98 %` par trade alors que le
témoin est gagnant. Les seuils validation→test apprennent donc surtout la
persistance du régime précédent et échouent lors de son retournement.

L'AUC de 0,64 ne doit pas être interprétée comme une stratégie : la
classification du signe terminal ne classe pas correctement la magnitude de
l'avantage économique, et le replay n'améliore ni les dates ni les folds de
façon robuste. E7 est fermé pour cette cohorte et ce contrat. Aucun modèle,
seuil, backtest ou flux live n'est promu.
