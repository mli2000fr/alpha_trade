# Sauvegarde, reprise après incident et rétention

## Périmètre

Une reprise complète peut nécessiter base, configuration, artefacts ML,
manifests, historiques de runs et secrets recréés. Les secrets ne doivent pas
être inclus en clair dans les archives documentaires.

## Backups disponibles

La page Infra & Backups permet archives ML et dumps DB. Une archive valide doit
être horodatée, inventoriée, lisible et testée par une restauration contrôlée.

## Ordre de reprise

1. stabiliser services et interdire les nouvelles mutations ;
2. identifier dernier état cohérent et portée de l’incident ;
3. sauvegarder l’état dégradé pour analyse ;
4. restaurer schéma/données puis artefacts compatibles ;
5. recréer secrets/configuration sécurisée ;
6. vérifier serving, positions et comptes avant reprise ;
7. rejouer uniquement les traitements idempotents nécessaires ;
8. effectuer parité/réconciliation et documenter.

## Rétention

Conserver plus longtemps les artefacts servis, champions précédents, manifests,
runs de validation/promotion et preuves réglementaires. Les logs volumineux et
runs exploratoires peuvent avoir une durée plus courte après synthèse. Toute
purge doit respecter dépendances et capacité de rollback.

Voir [guide administration](../guide_utilisateur/11_parametres_administration.md).

