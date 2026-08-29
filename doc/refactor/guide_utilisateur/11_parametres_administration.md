# Paramètres, infrastructure et administration

## Paramètres / Santé

### Source primaire OHLCV

Le fournisseur de barres influence disponibilité, ajustements et quotas. Un
changement de source ne doit pas être traité comme cosmétique : valider schéma,
calendrier, symboles, conventions d’ajustement et parité sur un échantillon.

### Seuils Alpha Scanner

La page gère des presets, édition et reset des seuils de diagnostic. Un seuil de
diagnostic n’est pas forcément une règle de sélection. Exporter l’état avant
modification et associer tout changement à une validation.

### Variables d’environnement

L’export/import CSV est limité par une allowlist. Ne jamais supposer qu’un export
contient les secrets. Vérifier l’aperçu des clés et la destination ; ne pas
versionner un fichier contenant une valeur sensible.

### Notifications

Les préférences email portent notamment sur la fin du workflow pipeline et un
test peut vérifier la chaîne. Un test réussi valide la livraison au moment du
test, pas toutes les alertes métier. Les systèmes d’alerting du projet sont
distincts ; voir [alerting et métriques](../operations/alerting_et_metriques.md).

### Connexion DB et pipeline

Le formulaire DB configure/teste le contexte utilisé par l’IHM. Les paramètres
pipeline exposés ici sont durables, tandis que la page Pipeline peut fournir des
options de run. Toujours distinguer défaut persistant et override de session.

### Maintenance et sécurité

Le nettoyage d’artefacts et la rotation de secrets sont des opérations
sensibles. Inventorier cible, dépendances de serving et rollback avant action.
Le diagnostic Python révèle interpréteur et dépendances utiles pour expliquer
une différence entre terminal, service et IHM.

## Infra & Backups

La page expose métriques Prometheus, backup d’artefacts ML, backup DB et reset
ML. Un backup n’est validé qu’après test de lecture/restauration, pas après la
seule création d’une archive.

Le reset ML efface tables et répertoires de modèles/backtests, arrête les runs
actifs et réinitialise des index. Il est irréversible depuis l’IHM sauf sauvegarde
externe valide. Utiliser une purge ciblée chaque fois que possible.

## Administration DB

La page construit un plan de vidage par groupes de tables et distingue les
tables purgeables. Relire le plan avant validation : dépendances, ordre, volumes
et sauvegarde. La restauration depuis backup doit viser une archive identifiée
et compatible avec le schéma.

Ne pas utiliser une purge pour corriger un unique enregistrement incohérent sans
diagnostic causal. Les migrations, contraintes et services d’écriture restent
les sources de structure.

## Fondamentaux et régime marché

La page Fondamentaux peut peupler/rafraîchir les données, explorer détail,
distribution sectorielle et recherche. Contrôler date de publication et
disponibilité PIT avant usage ML/backtest.

La page Régime Marché montre mode, trace de décision, configuration active,
import macro, recalcul et snapshots persistés. Le calcul à la volée et les
scénarios de démo ne remplacent pas le snapshot réellement consommé par un run.

## Sauvegarde minimale avant mutation importante

1. export de configuration non secrète ;
2. dump DB horodaté et vérifié ;
3. archive des artefacts ML et manifests ;
4. inventaire des runs/batchs servis ;
5. procédure de restauration testée ;
6. journal de changement avec responsable et motif.

