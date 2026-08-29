# Évolution, compatibilité et dépréciation

## Sources d’évolution

Schéma DB/migrations, configuration, manifests d’artefacts, CLI, pages IHM et
contrats métier. Un changelog historique décrit une intention ; le code et les
migrations déterminent l’état exécutable.

## Compatibilité

Les lecteurs doivent tolérer seulement les versions explicitement supportées.
Les nouveaux champs ont besoin de défauts sûrs ; les anciens champs ne doivent
pas rester documentés comme actifs si aucun call site ne les consomme.

## Dépréciation

Identifier propriétaire, remplaçant, période de coexistence, télémétrie d’usage
et date de suppression. Tester données/artefacts anciens nécessaires au rollback.

## Documentation

Chaque évolution matérielle met à jour la référence spécialisée, le guide
opérateur si le workflow change, et la matrice de configuration. Les journaux
d’expérience restent synthétiques et ne redéfinissent pas la production.

