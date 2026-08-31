# Oracle Extreme — dataset, features, ablations et anti-fuite

Retour : [dossier Oracle](README.md)

## Assemblage

`build_dataset()` joint les features calculées à D, le `global_rank_20` historique si requis, puis les targets `global_oracle_labels`. Les barres commencent environ 1 100 jours avant la fenêtre pour alimenter momentum 250 et z-scores. SPY est chargé comme benchmark.

Les features sont calculées par symbole avec `compute_features(feature_set="expert")`, puis les rangs cross-sectionnels sont calculés par date pour les sources utilisées par Global Ranking.

## Features Oracle

Deux extras existent :

- `drawdown_20 = close/rolling_max_20-1` ;
- `high_low_position_20 = (close-min_20)/(max_20-min_20)`.

Sans `adj_close`, le code remplit 0 et 0,5. Ce fallback évite un crash mais doit être compté comme défaut de couverture.

## Ablations

| Ablation | Contrat |
|---|---|
| O0 | features expert + rangs XS, sans Global Rank ni extras |
| O1 | O0 + `global_rank_20` + extras Oracle |
| O2 | sous-ensemble momentum, volume, volatilité et régime |

O0 est le contrat indépendant retenu par l’Oracle Extreme. O1 teste la valeur d’un second niveau au-dessus du Global Model. O2 teste si un ensemble réduit suffit. Les colonnes demandées sont intersectées avec le DataFrame : le rapport doit montrer les colonnes manquantes pour éviter une ablation silencieusement incomplète.

## Join train versus inference

Avec `need_targets=True`, les targets sont jointes en inner et seules les rows avec `oracle_available_date > date` sont gardées. Avec false, le join est left : les dates forward sans label restent prédictibles et la garde s’applique aux labels présents.

Avec `require_global_rank=True`, le join ranks est inner. Pour O0 standalone, false évite de rendre vide un batch sans `global_rank_history`.

## Split

`split_dataset()` prend pour train les labels dont `available_date <= train_cutoff` et pour validation les rows dont `date >= valid_start`. Le walk-forward ajoute les frontières de folds et assertions de cutoff ; des bornes mal choisies peuvent sinon se chevaucher.

## Garde-fous T1–T5

| Test | Vérification |
|---|---|
| T1 | available > prediction ; exit ≥ prediction |
| T2 | max available du train ≤ cutoff |
| T3 | noms sans patterns future/oracle |
| T4 | targets et colonnes Oracle absentes des features |
| T5 | aucun label lu avant sa disponibilité |

T3 est structurel : un nom correct ne prouve pas la disponibilité réelle. Les loaders PIT et timestamps restent nécessaires.

T4 interdit rang/décile/label/dates Oracle, future return/price/volume/volatility et anciens aliases top10. La relation T1 prouve qu’un label est futur par rapport à sa row ; T2 prouve qu’il était déjà connu au cutoff d’entraînement. Les deux sont nécessaires.

## Audit du dataset

Publier couverture par feature/date/symbole, fallbacks, NaN/infinis, tailles de coupes, rangs XS, liste/ordre/fingerprint, ablation, warm-up disponible et différence entre population demandée et jointe.

## Ajouter une feature

Définir sa disponibilité, coder sans futur, l’ajouter à une ablation nommée, tester les bords de fenêtre, publier fingerprint/couverture et réentraîner tous les folds. Ne pas charger un champion ancien avec un contrat nouveau.

