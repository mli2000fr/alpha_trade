# Couverture de la documentation par rapport au code

La complétude est contrôlée en partant du code actuel. Chaque package possède un guide, une référence spécialisée lorsque le contrat est complexe et un inventaire de signatures dans `api/`.

| Package | Guide/références |
|---|---|
| `core`, `common` | architecture, configuration, contrats PIT, inventaires API |
| `database`, `alembic` | base, schéma métier, migrations/transactions |
| `dataIntegrityEngine` | EODHD, sanitizer, univers, quotes/earnings |
| `screener`, `selector`, `event_sentiment` | trois références signaux |
| `modelFactory` | orchestration, features, ranking, Oracle, gouvernance |
| `risk_management` | ML-first, sizing, contraintes, contrôles |
| `execution_engine` | lifecycle, protections, réconciliation/TCA |
| `backtesting` | replay, microstructure, parité, statistiques |
| `corporate_actions` | dividendes/splits/réconciliation |
| `service` | providers et adaptateurs |
| `ihm` | architecture, supervision et sécurité |
| `flows`, `lineage`, `reporting`, `formal`, `tax` | architecture et opérations spécialisées |

À chaque nouveau fichier ou point d'entrée, ajouter son rôle. À chaque nouveau contrat complexe, créer une référence autonome et la lier depuis le guide global. Les anciens documents ne sont jamais utilisés pour conclure qu'une fonctionnalité actuelle est couverte.
