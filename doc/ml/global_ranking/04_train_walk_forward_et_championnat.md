# 4 — Entraînement walk-forward et championnat

## Splits temporels

`generate_walk_forward_splits_by_dates` construit les fenêtres temporelles
communes aux horizons. Pour chaque horizon, le code dérive une seed spécifique,
puis une seed par split. Train et validation reçoivent leurs targets isolément.

Le rapport conserve pour chaque split : index, nombre total, bornes train/val,
nombre de lignes, IC du champion et, en mode championnat, IC de chaque candidat.
Ces éléments sont nécessaires pour distinguer une moyenne élevée d’un modèle
stable dans plusieurs régimes.

## Groupes de ranking

Pour LightGBM, les données sont triées/groupées par date et le ranker reçoit la
taille des groupes. XGBoost/CatBoost ranking utilisent un identifiant de groupe
par ligne lié à la date. Le modèle apprend donc l’ordre à l’intérieur de chaque
section quotidienne, pas un ordre arbitraire entre toutes les lignes.

## Mode mono-backend

Si `champion_enabled` est faux, seul `global_model.model_name` est construit :
`catboost`, `lightgbm` ou `xgboost`. Les métriques par horizon servent ensuite à
la sélection du meilleur horizon, mais aucun championnat de backend n’a lieu.

## Mode championnat par horizon

Si le flag est actif, trois candidats sont entraînés sur les mêmes folds :
LightGBM, CatBoost et XGBoost. Le choix est effectué une fois pour l’horizon sur
les métriques agrégées des folds, et non en choisissant le meilleur modèle
différent à chaque split pour fabriquer artificiellement l’OOS.

### Gates d’éligibilité

Un candidat doit satisfaire :

1. IC moyen strictement positif ;
2. IC IR au moins égal à `0.30` ;
3. si au moins trois splits existent, au plus deux splits négatifs, soit une
   proportion positive minimale de `(N-2)/N`.

Si aucun candidat n’est éligible, le code réouvre le choix à tous et sélectionne
le meilleur score composite. Il journalise explicitement si tous les IC sont
négatifs ou si le rejet vient de l’instabilité. Ce fallback permet de produire
un artefact, mais ne transforme pas l’horizon en signal fiable.

### Score composite

Pour les candidats éligibles :

```text
score = 55 % IC_normalisé
      + 30 % IC_IR_normalisé
      + 15 % proportion_de_splits_IC_positif
```

IC et IR sont divisés par leur maximum parmi les candidats éligibles. Les
ineligibles reçoivent `-∞`. Le backend au score maximal devient champion de
l’horizon et ses seules prédictions OOS alimentent le rang final.

## Feature importance

Les importances sont extraites par split, moyennées pour le backend retenu et
journalisées (top, bottom et liste complète). Elles indiquent l’usage du modèle,
pas une causalité. Leur stabilité par split/horizon et la présence de doublons
comptent davantage qu’un classement unique.

## Sélection du meilleur horizon

Après le championnat intra-horizon, les champions H3/H5/H10/H15/H20 sont
comparés avec le même composite 55/30/15. Sans proportion positive disponible,
les poids deviennent 55 % IC et 45 % IR.

Les scores à ±`0.020` sont considérés ex æquo. Le tie-break hiérarchique utilise :

1. IC, différence significative > `0.005` ;
2. IR, différence > `0.10` ;
3. proportion de splits positifs, différence > `0.05` ;
4. pire IC de split, différence > `0.01` ;
5. horizon le plus court en dernier recours.

Le résultat est persisté sous `best_horizon` et accompagné de tous les scores
par horizon. Un consommateur ne doit pas recalculer son propre gagnant sans
déclarer un contrat différent.

## Sorties OOS

Les scores continus du champion sont convertis en percentiles par date. Les
cinq DataFrames sont fusionnés sur `(symbol,date)`. Toute colonne d’horizon
absente ou valeur manquante est créée/remplie à `0.5`.

