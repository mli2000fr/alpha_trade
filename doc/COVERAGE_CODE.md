# Couverture de la documentation par rapport au code

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

La couverture statique est contrôlée en partant du code actuel. Les packages
inventoriés possèdent un inventaire de signatures dans `api/`, régénéré le
10 octobre 2026. Les guides expliquent les contrats ; une signature inventoriée
ne vaut pas validation sémantique de l'algorithme ni couverture de tests.

[Décompte et périmètre exacts](reference/modules_generes.md) ·
[Empreintes des sources](audit/inventaire_sources.json) ·
[Bilan de révision](AUDIT_COMPLET_DOCUMENTATION_20261010.md).

| Package | Guide/références |
|---|---|
| `core`, `common` | architecture, configuration, contrats PIT, inventaires API |
| `database`, `alembic`, `alembic_cn`, `alembic_fr` | bases séparées, DDL, graphes de migrations/transactions |
| `dataIntegrityEngine` | EODHD, sanitizer, univers, quotes/earnings |
| `screener`, `selector`, `event_sentiment` | trois références signaux |
| `modelFactory` | orchestration, features, ranking, Oracle, gouvernance |
| `risk_management` | ML-first, sizing, contraintes, contrôles |
| `execution_engine` | lifecycle, protections, réconciliation/TCA |
| `backtesting` | replay, microstructure, parité, statistiques |
| `corporate_actions` | dividendes/splits/réconciliation |
| `service` | providers et adaptateurs |
| `ihm` | architecture, supervision et sécurité |
| `flows` | pipeline : distinction explicite entre orchestrateur auxiliaire 5 étapes et canonique IHM |
| `lineage`, `reporting`, `formal` | reporting signé, capture lineage, portée des preuves |
| `tax` | référence wash-sale, algorithme et limites |
| `scripts`, points d'entrée racine | outils CLI, maintenance, recherche et sauvegardes ; disponibilité ≠ autorisation de lancement |

À chaque nouveau fichier ou point d'entrée, ajouter son rôle. À chaque nouveau contrat complexe, créer une référence autonome et la lier depuis le guide global. Les anciens documents ne sont jamais utilisés pour conclure qu'une fonctionnalité actuelle est couverte.
