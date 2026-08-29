# Sélection, screening et scoring

## Responsabilités

Le selector définit l’univers/candidats admissibles. Le screener calcule des
composantes et un score. La sélection finale applique seuils, objectifs et
éventuels filtres. Le risque intervient ensuite ; il ne fait pas partie du score.

## Contrat cross-sectionnel

Un rang/percentile dépend de la population à la date. Conserver univers,
effectif, méthode de tie-break et valeurs manquantes. Les comparaisons entre
dates exigent des échelles/calibrations compatibles.

## Composantes

Les signaux de prix, fondamentaux, sentiment, short, macro/régime et ML doivent
être disponibles PIT. Le score composite doit rendre explicites poids,
normalisation, plafonds et fallback. Une composante absente ne doit pas recevoir
silencieusement la même signification qu’une valeur neutre.

## Sorties

Les tables de score, historiques PIT, artefacts CSV et recommandations répondent
à des usages différents. L’IHM expose la qualité amont, les filtres et
l’explicabilité. Voir [screener](screener_reference.md),
[selector](selector_reference.md) et [guide Screening](../guide_utilisateur/04_screening.md).

