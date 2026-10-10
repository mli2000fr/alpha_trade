# Oracle Extreme — dataset, features, ablations et anti-fuite

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Retour : [dossier Oracle](README.md)

## Assemblage

`build_dataset()` joint les features calculées à D, le `global_rank_20` historique si requis, puis les targets `global_oracle_labels`. Les barres commencent environ 1 100 jours avant la fenêtre pour alimenter momentum 250 et z-scores. SPY est chargé comme benchmark.

Les features sont calculées par symbole avec `compute_features` et les options
du générateur. Les chemins sont segmentés aux discontinuités d'identité connues :
les fenêtres ne traversent pas ces ruptures. Si une population date/symbole est
fournie, elle est filtrée **avant** les rangs cross-sectionnels, afin de ne pas
classer dans une autre population que celle du protocole.

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

O0 est le contrat indépendant retenu par l’Oracle Extreme. O1 teste la valeur
d'un second niveau au-dessus du Global Model. O2 teste si un ensemble réduit suffit.
La résolution des colonnes de base filtre celles présentes, puis supprime six
aliases redondants (`distance_ema20/50`, `return_5d/10d/20d`, `log_return_xs_rank`).
En revanche, un `feature_whitelist` explicite est un contrat strict : une feature
absente ou une liste vide déclenche une erreur ; l'ordre demandé est conservé.
Publier les colonnes effectivement utilisées, pas seulement le nom O0/O1/O2.
Le champ `global_rank_20` reste nommé H20 : un horizon Oracle court ne transforme
pas implicitement cette feature en Global Rank H5/H10/H15.

## Join train versus inference

Le loader de targets ne lit que `target_quality_valid=1` pour le batch/horizon.
Avec `need_targets=True`, la jointure est inner et exige target non NULL,
disponibilité non NULL et `oracle_available_date > date`. La qualité des prix
ne suffit donc pas si le rang quotidien n'a pas pu être défini. Avec false, la
jointure est left : les dates forward sans label restent prédictibles et la
garde s'applique aux labels présents. La prédiction n'exige pas un rendement futur.

`restrict_features_to_targets=True` charge les membres historiques complets,
y compris les lignes de target invalides, avant les rangs XS. Cette option exige
`need_targets=True` et ne se combine pas avec `feature_membership` explicite.

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
