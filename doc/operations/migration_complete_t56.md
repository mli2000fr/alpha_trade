# T5.6 — Sauvegarde complète et restauration sur un autre PC

Implémentation du 31 octobre 2026. Accès : **Infra & Backups → T5.6**.
La sauvegarde sert aussi à constituer une copie de résilience : **le PC source
continue à fonctionner**. Aucune tâche, aucun batch, aucun watcher du PC source
n'est arrêté, désactivé ou reconfiguré par cet outil.

## Contenu des packages

| Répertoire | Contenu |
|---|---|
| `donnees/alpha_trade` | Dump complet US, dont `news_raw`, pas le backup hebdomadaire partiel |
| `donnees/alpha_trade_fr` | Dump complet FR |
| `donnees/alpha_trade_cn` | Dump complet CN |
| `modeles` | Tous les arbres `artifacts/models*`, poids et contrats |
| `configuration` | Configurations, univers, presets, prompts classés par leur chemin ; métadonnées privées d'exécution |
| `application` | Source présent sur disque, y compris les modifications non commitées, tests et documents |
| `etats-et-archives` | `artifacts`, sorties, journaux et archives de recherche hors exclusions |
| `environnement` | Variables utilisées par l'application, valeurs et origine, chiffrées |
| `outils` et `restaurer.ps1` | Restaurateur autonome, utilisable avant d'installer l'IHM |

Les catégories conservent les chemins relatifs d'origine : ce ne sont pas des
répertoires à recopier manuellement dans l'application. Le restaurateur les
reconstitue. Chaque flux compressé et chiffré est fractionné à 2 Gio ; copier
**tout le répertoire**, dont `manifest.json`, `progress.json` et tous les fragments.

Exclusions : `.venv`, `.git`, caches Python/IDE, fichiers PID/verrous temporaires,
backups antérieurs et répertoires temporaires identifiés par `inventory.py`.
Le code courant est sauvegardé ; l'historique Git n'est pas transféré. Les
références de modèles, archives et verrous **métier** restent conservées : un
`execution.claim.json` scellé n'est pas un simple verrou de processus.

Les variables sont recherchées dans les sources/configurations et les familles
de fournisseurs connues, y compris les comptes Alpaca dynamiques. Les valeurs
effectives du processus ont priorité sur celles de l'utilisateur, puis celles
de la machine. `PATH`, les chemins système Windows et l'environnement du PC
ne sont pas transférés en bloc. Les variables absentes apparaissent comme telles.
Les secrets stockés dans des fichiers du projet sont également protégés puisque
**tous les packages**, pas seulement celui d'environnement, sont chiffrés.
Les variables pointant vers un chemin absolu externe au projet portent le
signalement `external_path` ; leurs fichiers ne sont pas copiés implicitement.

## Sauvegarde à chaud et limites de cohérence

Le mode IHM est `online`. Il utilise `mysqldump --single-transaction
--skip-lock-tables --routines --triggers --skip-events`, avec GTID/tablespaces
hors dump. Le mot de passe MySQL est transmis dans l'environnement du client,
jamais dans ses arguments. Aucun verrou global applicatif n'est ajouté.

Chaque base InnoDB bénéficie de sa propre transaction de lecture. Les trois
transactions et les fichiers ne sont **pas** un instantané global au même
instant. Le manifeste indique `source_mode: online`,
`cross_database_atomic: false`, `row_counts_authoritative: false` et
`source_services_unchanged: true`. Les modifications de données sur le PC source
sont autorisées ; les changements de schéma détectés invalident la sauvegarde.
Les tables non InnoDB sont refusées.
Chaque package SQL conserve son intervalle de début/fin d'export ; il ne
prétend pas connaître l'heure exacte d'ouverture de la transaction du client.

Les fichiers sont lus dans leur version disponible au moment de leur ouverture.
Pour les journaux append-only sous `log`/`logs`, la portion présente à l'ouverture
est archivée. Une modification en place pendant la lecture d'un autre fichier
fait échouer la sauvegarde. Ce refus n'interrompt pas le travail du PC source.
La présence de fichiers nouvellement créés après l'inventaire n'est pas garantie.
Si un entraînement/une collecte est actif, une sauvegarde ultérieure peut donc
être utile pour conserver sa version terminée.

`COMPLETE` signifie : export terminé, manifeste authentifié, fragments et
contenus relus avec succès. Cela ne prouve ni cohérence transactionnelle entre
les trois bases, ni réconciliation avec le broker, ni reprise d'exploitation
qualifiée. Un export interrompu/échoué ne possède pas de manifeste utilisable.

Un mode technique `quiescent` existe dans l'API pour un arrêt déjà organisé par
l'opérateur ; il n'est pas sélectionné par l'IHM et ne ferme jamais de service.
Ses comptages ne détectent pas toutes les mises à jour concurrentes à nombre
de lignes identique. Aucun mode ne suspend automatiquement la source.

## Créer et vérifier

1. Ouvrir T5.6, choisir un **nouveau** dossier, par défaut
   `backups/migrations/alpha-trade-<UTC>` ; utiliser ensuite un disque/autre PC
   pour conserver la copie de résilience.
2. Saisir deux fois un mot de passe d'au moins douze caractères. Le conserver
   séparément : aucune récupération du mot de passe n'est fournie.
3. Indiquer les chemins de `mysqldump.exe` et `mysql.exe`.
4. L'inventaire affiche tailles/nombres de fichiers et noms des variables,
   sans valeur. Lancer **Créer les packages chiffrés**.
5. Dans **Suivi et packages**, actualiser jusqu'à `COMPLETE`, puis copier le
   dossier entier et le vérifier depuis la copie.

AES-256-GCM authentifie les blocs et la fin de chaque flux ; Scrypt dérive les
clés du mot de passe. Le manifeste est authentifié par HMAC et contient les
empreintes SHA-256 des fragments et outils portables. Les fichiers ne sont pas
décompressibles directement avec un gestionnaire ZIP.

Les secrets passent de l'IHM au worker par un pipe stdin anonyme, sans fichier
de requête, argument de commande ou sortie brute persistante. Le bouton de
lancement efface ensuite les champs sensibles de la session IHM.

### Suivi en direct

Dans **Suivi et packages**, choisir l'opération. Le bloc se rafraîchit
automatiquement toutes les **deux secondes**, sans recharger les formulaires.
Il affiche :

- une barre globale **estimée par étapes**, la phase et le temps écoulé ;
- la base/package et le fichier ou la table en cours ;
- les octets transférés, avec une seconde barre de volume lorsque le total
  est connu, ainsi que les nombres de fichiers/tables ;
- un journal défilant de 280 pixels, les 150 derniers événements et un bouton
  pour télécharger ces dernières lignes ;
- les erreurs et le retour arrière éventuel, sans afficher de secret.

Le journal intégral est `events.jsonl` et l'état courant `tracking.json`, dans
le dossier du worker ; ils sont également écrits dans le répertoire de sauvegarde
ou le rapport de restauration dès que ce répertoire existe. Les horaires de
l'écran sont ceux de Paris ; les événements sur disque portent une date UTC.
Les événements de phase sont conservés, les compteurs sont limités à une écriture
par seconde et les traces de volume à une toutes les quinze secondes, plus les
fins de package. Le suivi n'enregistre aucun SQL, contenu de fichier, requête
complète ou valeur d'environnement.

Le pourcentage global est un repère d'étapes, **pas une estimation du temps
restant**. Un export SQL de taille inconnue affiche ses octets compressés ;
l'import affiche les octets SQL lus. Le pourcentage peut rester stable pendant
une longue requête ou une installation Python. Le processus arrêté sans résultat
final est signalé ; une erreur/annulation ne fait pas passer la barre à 100 %.
En restauration, 100 % n'est atteint qu'après la finalisation du worker et la
tentative de préparation Python ; un échec de cette dernière reste un avertissement.
Le restaurateur portable affiche également ses étapes dans PowerShell.

## Préparer le PC cible

Installer la même famille **Python majeure.mineure** et **MySQL majeure.mineure**
que celle du manifeste, ainsi que les clients `mysql` et `mysqldump`. Les trois
bases physiques sont `alpha_trade`, `alpha_trade_fr`, `alpha_trade_cn`.
Le restaurateur refuse un serveur non local et **le même UUID MySQL que la
source**, pour éviter d'écraser le serveur du PC encore actif.

Les comptes SQL `DEFINER` des procédures/triggers/événements doivent exister
sur le serveur cible. L'outil ne copie pas `mysql.user` et ne crée pas ces
comptes à votre place. Les chemins de certificats externes, services de coffre
distants, comptes Windows et logiciels système ne sont pas embarqués ; ils
doivent être disponibles sur le nouveau PC si la configuration les utilise.

Fermer **sur le PC cible** les processus du projet, y compris son IHM, et
désactiver ses tâches Windows visant ce projet. Le contrôle lit leurs états,
sans les modifier. S'il existe déjà un `.venv`, le renommer manuellement :
l'outil ne le supprime, ne le réutilise et ne le remplace pas.

Le dossier de packages et les journaux de restauration doivent être **hors du
projet cible**. Un disque externe convient ; la préparation et les anciens
fichiers sont conservés dans des dossiers privés à côté du projet pour assurer
les déplacements sur le même volume.

## Restaurer

Sur un PC sans installation Alpha Trade : lancer `restaurer.ps1` depuis
PowerShell. Il crée uniquement son propre environnement d'outils dans la copie
de sauvegarde et installe leurs versions figées. Un accès aux paquets Python
est requis. Il demande ensuite les chemins et mots de passe de façon interactive.

T5.6 affiche un bloc **Restaurer depuis PowerShell, sans l’IHM** sous le dossier
de sauvegarde, dans l'onglet de restauration et dans le suivi d'une sauvegarde
terminée. Le bloc de code possède le bouton Copier habituel. Exemple :

```powershell
& 'E:\Sauvegardes\alpha-trade-20261031\restaurer.ps1' -Action restore
```

Le script utilise son propre répertoire comme sauvegarde ; après copie sur
l'autre PC, adapter seulement son chemin dans la commande. Aucun mot de passe
n'est intégré dans la ligne de commande. Pour préremplir aussi le projet cible :

```powershell
& 'E:\Sauvegardes\alpha-trade-20261031\restaurer.ps1' -Action restore -TargetDir 'F:\projets'
```

Les nouveaux scripts acceptent également `-BackupDir` pour un autre répertoire
de packages et `-Python` pour l'exécutable Python installé sur le PC cible.
Pour `-Action recover`, le dossier de préimage reste demandé s'il n'est pas
explicitement fourni. Les sauvegardes créées avant cette évolution conservent
leur ancien script interactif ; la commande simple reste utilisable.

Depuis une IHM déjà installée : renseigner **Vérifier / restaurer**, lancer la
prévisualisation, examiner les bases/racines remplacées, puis confirmer le
remplacement. Les champs de mots de passe sont effacés après chaque opération :
les ressaisir pour la restauration. Le worker détaché attend au maximum quinze
minutes la fermeture des services du PC cible. Il ne ferme rien lui-même.

L'opération :

1. authentifie le manifeste, relit les fragments et archives, refuse traversées
   de chemins, doublons de casse, liens/jonctions et noms Windows ambigus ;
2. lie la confirmation au plan et à l'état des bases de destination ;
3. extrait les fichiers en préparation, contrôle les contrats/poids Oracle sans
   charger de pickle, et sauvegarde **l'existant chiffré avant le premier DROP** ;
4. recrée puis importe les trois schémas, sans fusion et sans `alembic upgrade` ;
5. vérifie schémas/objets et compte les lignes après import ; en mode online,
   les comptes ne peuvent pas être comparés à un compte source atomique ;
6. remplace les racines gérées et l'arbre d'artefacts, empêchant le mélange de
   vieux modèles avec les nouveaux ; les répertoires hors périmètre restent ;
7. restaure les variables dans **HKCU Environment**, adapte leur préfixe de
   projet et conserve les identifiants MySQL locaux choisis pour la cible ;
8. remet à zéro uniquement `execution_locks` et les statuts PID de l'IHM ;
   conserve les journaux/idempotences métier et les fichiers source des anciens
   statuts ; restaure les événements SQL en **DISABLED** ;
9. tente de créer un nouveau `.venv` avec les versions `pip freeze` figées.

Les dépendances locales/VCS non installables par un simple `nom==version` sont
signalées par `dependency_review_count` ; leurs URL éventuellement sensibles
ne sont pas inscrites dans les rapports. Les wheels CUDA/indices privés peuvent
demander une installation manuelle. Un échec de construction Python produit
`BUILD_FAILED_RETRY_REQUIRED` ; les données restaurées restent en place.

Les fichiers de configuration sont conservés tels quels ; les chemins absolus
qu'ils contiennent doivent être revus si le répertoire du projet change. Les
archives et contrats historiques scellés ne sont pas réécrits arbitrairement.
Les variables de processus déjà ouvertes ne changent pas : rouvrir une session
Windows/terminal avec l'environnement mis à jour avant d'utiliser l'application.

Le résultat `RESTORED_PAUSED` et le marqueur
`.alpha_trade_restore_pending.json` sont **informatifs**, sans modification
globale des moteurs. Rien ne démarre automatiquement. Avant une reprise réelle,
réconcilier comptes/positions/ordres du broker et les évolutions intervenues
depuis le backup. Une copie de résilience ne doit pas lancer un second watcher
sur les mêmes comptes pendant que le PC source les gère encore.

## Échec et récupération

Une erreur pendant le remplacement tente automatiquement de restaurer les
trois anciennes bases, les anciens fichiers et les variables modifiées.
Statuts : `FAILED_ROLLED_BACK` ou `FAILED_ROLLBACK_INCOMPLETE`. Aucun de ces
statuts ne déclenche de reprise des services.

Les rapports sont sous le dossier choisi dans `journaux`. Ils contiennent le
chemin `existant-chiffre/recovery.json`, les archives chiffrées, ainsi que
`local-directories.json`, qui indique les fichiers de préparation et les anciens
fichiers conservés à côté du projet. Ces répertoires locaux peuvent contenir
la configuration en clair : les traiter comme le projet lui-même. Aucune purge
automatique n'est effectuée avant validation de la restauration.

Après coupure du processus/du PC, utiliser **le même mot de passe** et
`restaurer.ps1 -Action recover` ; indiquer le répertoire `existant-chiffre` du
rapport concerné, puis la destination d'origine. La récupération vérifie les
archives avant de remplacer les bases ; les fichiers partiels sont conservés
à part. Elle nécessite également l'arrêt des seuls services du PC cible.
Un verrou de migration laissé par une coupure doit être vérifié (PID éteint)
puis peut être archivé automatiquement à la prochaine tentative : le PID et
son heure de création sont vérifiés, afin de distinguer un processus actif
d'un PID réutilisé. Un verrou illisible ou un propriétaire inaccessible reste
bloquant. Un garde système tenu uniquement par les opérations de migration
empêche deux reprises concurrentes et est libéré par Windows à la mort du
worker. Ce garde n'est consulté ni par SQL, ni par les batchs métier, ni par le
watcher. Le suivi utilise le PID réel du worker Python, prioritaire sur celui
du lanceur `.venv`, et un même échec n'est plus journalisé deux fois.

### Nettoyage explicite des anciennes tentatives

Dans **Suivi et packages → Nettoyer les anciennes sauvegardes T5.6 et libérer
le verrou**, inventorier les dossiers, confirmer la suppression définitive,
puis cliquer **Nettoyer les anciennes sauvegardes et déverrouiller**.
Le périmètre est limité à `backups/migrations` et `backups/migration_jobs` ;
les sauvegardes planifiées DB/ML/FR/CN sont hors de cette action. Les exports
dans d'autres répertoires ne sont pas supprimés implicitement.

Les opérations actives et les propriétaires incertains bloquent le nettoyage.
Les dossiers inconnus ou liens/jonctions sont conservés/refusés. Le plan est
lié aux empreintes de l'inventaire et revérifié avant suppression ; un contenu
modifié impose un nouvel inventaire. Le reçu d'un verrou orphelin est conservé
dans l'audit de nettoyage avant son retrait. Le bilan est écrit sous
`backups/operations_history/migration-cleanup-*.json`. Aucun processus n'est
arrêté ; aucune donnée de production ni aucun modèle actif n'est supprimé.

Incident du 31/10/2026 à 16:24 Paris : `FileExistsError` causé par le reçu du
worker terminé 15176, démarré à 15:14 Paris. Son suivi avait atteint
24 200 162 353 octets compressés avant interruption. Sur demande explicite,
les deux tentatives échouées et les trois historiques de migration restants
ont été supprimés, le propriétaire a été revérifié mort et le verrou libéré.
Le gros dossier de la première tentative était déjà absent de l'inventaire.
Audit : `backups/operations_history/migration-cleanup-20261031T153714Z-07db44a6.json`.
Aucun nouveau dump n'a été lancé par ce nettoyage.

## Qualification effectuée

Tests automatisés avec bases simulées et secrets fictifs : export/vérification,
restauration des trois bases, absence de mélange de modèles, conservation des
claims, retour arrière SQL/fichiers/environnement, récupération de préimage,
mot de passe incorrect, fragments manquants/altérés, archives non finalisées,
outils altérés, traversées de chemins, cible active, changements de plan,
protection du serveur source, chiffrement des variables, lancement par stdin,
et interface Streamlit.

**Aucun dump, export de secrets réels, import MySQL de production ou arrêt de
service n'a été exécuté pendant le développement.** Un essai sur un serveur
MySQL cible distinct reste nécessaire pour qualifier le volume et les droits
de cette installation ; les tests simulés ne prouvent pas son RTO réel.

Sources : `service/migration/`, `ihm/services/migration_runner.py`,
`ihm/components/migration_panel.py`, tests `test_migration_complete.py` et
`test_migration_ui_worker.py`.
