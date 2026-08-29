# Features et construction des datasets ML

Cette référence complète [features et labels](features_et_labels.md) en mettant
l’accent sur le contrat de dataset.

## Contrat d’une ligne

Une ligne doit définir symbole, date d’observation, date de disponibilité,
univers/groupe, features, cible/horizon et provenance. La clé d’apprentissage ne
doit pas permettre un mélange accidentel de deux snapshots ou versions.

## Temporalité

Toutes les features fondamentales, sentiment, macro, marché et prix doivent être
jointes avec leur disponibilité réelle. Une date économique ou une ex-date
n’est pas nécessairement la date où l’information était consommable. Les
rolling windows doivent être calculées avec le passé seulement.

## Valeurs manquantes

Documenter imputation, indicateur de manque, exclusion et impact de couverture.
Une imputation calculée sur l’ensemble du dataset fuit la validation. Les
transformations apprises sont ajustées sur train puis appliquées aux fenêtres
suivantes.

## Alignement des échelles

Rang, probabilité, rendement et score composite ne partagent pas une échelle.
Toute combinaison requiert une transformation/calibration explicite. Les ranks
cross-sectionnels dépendent de l’univers du jour.

## Reproductibilité

Persister liste et ordre des features, types, version de code/configuration,
fenêtre, univers, seed et statistiques de qualité. Le loader de serving doit
refuser ou signaler un schéma incompatible.

Pour Oracle, voir [dataset Oracle](oracle/03_dataset_features_et_leakage.md).

