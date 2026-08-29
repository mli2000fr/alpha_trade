# Page Pipeline — guide opérateur détaillé

## Rôle de la page

La page Pipeline configure, lance et observe les traitements métier. Elle n’est
pas seulement un bouton « tout exécuter » : elle sert aussi au bootstrap, aux
reprises ciblées, à la publication d’historiques PIT et à la préparation des
campagnes ML.

## Paramétrer l’univers

La source de symboles détermine la population chargée. La prévisualisation doit
être utilisée pour vérifier nombre, exemples et éventuelles exclusions avant
une collecte. Le symbole de départ permet une reprise/segmentation ; il ne
redéfinit pas la qualité de l’univers. Pour le ML, une source d’univers et un
commentaire de campagne peuvent être distincts de la source de collecte.

La publication historique de l’univers alimente
`tradable_universe_history`. Cette table permet au backtest de résoudre
l’univers disponible à chaque date. Publier l’univers courant rétroactivement
sur toutes les dates créerait un biais de survivance ; l’outil attend des
snapshots PIT cohérents.

## Dates, cotations et quota

La plage historique conditionne volume, durée et couverture. La page fournit
une estimation de coût de cotations et demande une confirmation pour les gros
runs. L’âge des quotes et l’option d’ignorer certaines quotes sont des choix
opérationnels : ils doivent être consignés quand ils modifient le périmètre.

Avant lancement, comparer : plage demandée, calendrier de marché, données déjà
présentes, quota disponible et profondeur réellement utile au traitement aval.

## Étapes et dépendances

Le pipeline de production est une séquence de quatorze étapes. L’interface
regroupe le cœur quotidien et les traitements optionnels, contrôle les
dépendances et expose des actions par étape. Pour la définition exacte et les
entrées/sorties de chacune, consulter [Pipeline quotidien](../04_pipeline_quotidien.md).

Principes :

- un bootstrap construit un socle historique ;
- une maintenance répare ou complète un sous-ensemble ;
- une exécution quotidienne prolonge un état déjà cohérent ;
- une étape verte ne garantit pas que sa donnée est assez récente pour le run
  actuel si elle provient d’une exécution antérieure ;
- les étapes ML nécessitent de contrôler batch, source de symboles et capacité
  de calcul, pas seulement leur statut final.

## Batch, parallélisme et workers

Les contrôles de taille de batch et de workers influencent débit, mémoire,
pression DB et capacité fournisseur. Une valeur supérieure n’est pas toujours
plus rapide. En cas d’échec intermittent, réduire la concurrence et examiner le
premier défaut causal plutôt que les erreurs en cascade.

La prédiction historique pour backtest possède son propre nombre de workers et
peut cibler un batch configuré. Vérifier le batch sélectionné : rejouer un batch
ancien est utile en recherche, mais il ne représente pas automatiquement le
serving courant.

## Centre d’exécution

Chaque lancement crée un enregistrement et des flux de logs. Le centre permet de
sélectionner un run, suivre statut/étape, télécharger ou consulter les traces et
arrêter un travail. Un arrêt est une mutation : attendre la confirmation puis
vérifier processus et verrou.

États à distinguer :

| État | Lecture |
|---|---|
| queued/pending | accepté mais pas encore en travail effectif |
| running | processus vivant ou récupéré et suivi |
| completed | commande terminée ; contrôler encore les sorties métier |
| failed | commande en erreur ; partir de la première cause utile |
| stopped/cancelled | interruption demandée ou constatée |
| orphan/recovered | registre reconstruit autour d’un processus/artefact existant |

## Machine d’état et protections live

Les contrôles empêchent notamment des dépendances invalides, des lancements
concurrents et certains enchaînements live dangereux. Le verrou partagé avec le
backtesting explique qu’un backtest puisse bloquer le pipeline et inversement.
Ne jamais contourner ce verrou par suppression manuelle avant d’avoir démontré
que son propriétaire est mort.

## Diagnostic d’un échec

1. relever run, étape et dernière activité ;
2. vérifier la santé DB/fournisseur et le quota ;
3. lire la première exception, pas seulement la dernière étape marquée rouge ;
4. contrôler le périmètre exact et les dépendances produites ;
5. déterminer si les écritures sont idempotentes ou partielles ;
6. choisir reprise ciblée ou relance complète selon le contrat de l’étape ;
7. vérifier les sorties aval avant de reprendre le workflow.

Une relance réussie ne suffit pas si elle mélange deux as-of dates, deux batchs
ou deux univers. L’audit doit conserver cette cohérence de chaîne.
