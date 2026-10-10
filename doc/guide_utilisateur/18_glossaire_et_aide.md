# Glossaire et système d’aide

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

La page Glossaire charge les entrées d’aide enregistrées, permet une recherche tolérante et affiche chaque définition dans un expander. Elle explique les termes de l’application ; elle ne remplace pas le contrat technique du module.

Si un terme est absent ou ambigu, rechercher d’abord le guide du domaine puis le code producteur. Ajouter une entrée d’aide lorsque le terme apparaît dans l’IHM, et mettre à jour le glossaire global [20_glossaire.md](../20_glossaire.md) lorsqu’il s’agit d’un concept transversal.

Les aides contextuelles sont liées à des clés de page. Renommer un widget ou une page exige de vérifier les fichiers sous `ihm/help` et les appels `help_key`, sinon l’interface peut rester fonctionnelle avec une aide silencieusement absente.

