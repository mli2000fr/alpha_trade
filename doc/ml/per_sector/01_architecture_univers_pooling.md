# 1 — Architecture, univers et pooling

## Regroupement

`run_per_sector_batch` associe les symboles aux secteurs depuis les données
disponibles, filtre les groupes exploitables et entraîne un modèle par secteur.
Il charge une fois benchmark, sentiment, univers, selector, fondamentaux et
cache cross-sectionnel pour éviter de refaire les mêmes requêtes à chaque
groupe.

## Préparation indépendante puis concaténation

`_prepare_sector_data` prépare chaque symbole séparément avec les mêmes
transformations per-symbol, puis concatène les lignes. Cela protège les rolling
features et targets contre un mélange de séries entre tickers. Le split final du
pool est fait par dates afin que les mêmes périodes appartiennent aux mêmes
partitions pour tous les symboles.

## Feature d’identité du symbole

Si `sector_use_symbol_feature=True`, `symbol` est ajouté comme feature
catégorielle. CatBoost reçoit nativement `cat_features=['symbol']`; LightGBM
travaille avec la colonne convertie en catégorie dans le DataFrame. L’ablation
`False` teste un modèle totalement mutualisé qui ne connaît pas l’identité du
ticker.

## Cache cross-sectionnel

Le batch construit le cache pour tout l’univers avant les secteurs, puis fusionne
les colonnes utiles. Le code mesure les features réellement non constantes après
fusion. Une colonne demandée mais sans variance n’apporte pas de séparation et
doit apparaître dans le diagnostic.

## Limite LSTM

Le docstring parle de trois challengers, mais le résultat courant fixe
`lstm_attention` à `skipped` avec `lstm_not_implemented_for_sectors`. Il n’existe
donc pas aujourd’hui de champion LSTM sectoriel servi par ce chemin.

