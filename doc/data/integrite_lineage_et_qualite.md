# Intégrité, lineage et qualité des données

## Dimensions

Complétude, fraîcheur, unicité, validité, cohérence inter-tables, temporalité PIT
et provenance. Une donnée peut être syntaxiquement valide mais temporellement
inadmissible.

## Lineage

Chaque sortie matérielle doit être rattachable à sources, date de disponibilité,
transformation, version/configuration et run. Pour ML, ajouter batch/artefact ;
pour trading, décision/request/ordre/fill.

## Contrôles

- clés et contraintes DB ;
- sanitizer et règles de validation ;
- compteurs/alertes pipeline ;
- cross-check fournisseurs ;
- couverture PIT ;
- parité replay/live ;
- propriétés/tests différentiels lorsque présents.

## Correction

Qualifier portée et consommateurs, conserver preuve avant mutation, réparer au
niveau source puis reconstruire les dérivés dans l’ordre. Éviter une correction
manuelle isolée qui casse le lineage.

Voir [données](README.md), [sanitizer](sanitizer_daily.md),
[univers PIT](univers_pit.md) et [base](../15_base_de_donnees.md).
