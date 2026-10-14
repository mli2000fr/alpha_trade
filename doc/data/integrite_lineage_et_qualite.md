# Intégrité, lineage et qualité des données

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Dimensions

Complétude, fraîcheur, unicité, validité, cohérence inter-tables, temporalité PIT
et provenance. Une donnée peut être syntaxiquement valide mais temporellement
inadmissible.

## Lineage

Chaque sortie matérielle doit être rattachable à sources, date de disponibilité,
transformation, version/configuration et run. Pour ML, ajouter batch/artefact ;
pour trading, décision/request/ordre/fill.

Pour les news US, l'[archive prospective](../signals/news_version_archive.md)
conserve texte/payload, date fournisseur et précision, associations et politique,
empreintes et observations de disponibilité après commit. Cela ne qualifie pas
automatiquement l'identité de l'émetteur, la complétude du corps ou du flux, ni
les anciennes versions des scores FinBERT. Ne pas antidater un backfill.

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
