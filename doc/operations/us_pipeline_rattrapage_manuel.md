# Rattrapage manuel US avant ouverture

Évolution du 19 novembre 2026, page **Batchs planifiés**, fiche `us_pipeline`.

## Bouton et séance traitée

Le bouton **Rattraper le JJ/MM/AAAA** apparaît à côté de **Lancer maintenant**
uniquement avant l'ouverture de la séance US du jour, lorsque la dernière
séance de bourse clôturée n'a pas de batch entièrement finalisé. Le calendrier
US qualifié détermine les jours fériés, demi-séances et changements d'heure.
Le lundi, la séance à rattraper est normalement celle du vendredi. Les jours
sans séance US, ce bouton n'est pas proposé.

Le 19 novembre au matin, ce bouton vise explicitement le **18 novembre**.
Il ne désactive pas `SESSION_NOT_CLOSED` pour le 19 novembre. Le lancement
standard et la planification habituelle conservent leur contrat de date.
Les étapes, fenêtres de collecte, Oracle, filtres et risque partagent tous
la date de la séance rattrapée ; l'horloge réelle n'est jamais falsifiée.

## Qualification et reprise

La qualification lit `alpha_trade.pit_collection_runs` pour cette période,
sans téléchargement fournisseur ni appel au courtier. Un succès doit être
terminal avec une date de fin, des compteurs entièrement persistés, un nombre
d'étapes demandé positif et aucun échec. Une tentative `SKIPPED` visant
aujourd'hui ne cache pas le rattrapage de la veille ; un succès plus ancien
de la séance reste prioritaire sur une tentative ultérieure ignorée/échouée.
Un ancien état SQL `RUNNING` d'une autre période n'est pas assimilé au verrou
Windows actuel et n'est pas réécrit par ce contrôle.

S'il n'y a eu aucun traitement, le rattrapage construit le parcours complet
avec la configuration actuelle. Un échec limité aux collectes, avant risque
ou exécution, peut également repartir avec un nouveau plan tracé.

Si le compte principal a entièrement terminé mais qu'un compte suivant n'a
pas commencé, ses reçus locaux sont vérifiés. Le compte terminé est conservé ;
les autres réutilisent les options et l'identifiant exact de sélection initial,
sans refaire Oracle ni les achats du compte terminé. Une incohérence de
compte, une sélection absente ou des reçus manquants interdit cette reprise.

Si risque, exécution ou opérations sur compte ont déjà été tentés dans un
workflow non terminé, le bouton apparaît désactivé avec un motif de
réconciliation. Il n'efface aucun verrou ni tentative ambiguë. Les protections
et gardes métier des étapes 11/12 restent applicables.

## Concurrence et traçabilité

La date et l'éligibilité sont revérifiées au clic puis par le runner sous le
mutex du lanceur. Un clic après l'ouverture, une séance déjà finalisée ou une
date autre que la dernière clôturée sont refusés avant tout workflow. Les
verrous Windows, le registre Pipeline et les verrous des comptes restent actifs.
Deux clics ne peuvent pas lancer deux parcours concurrents.

Le run figure dans l'historique IHM avec la mention `rattrapage AAAA-MM-JJ`.
Le plan, les compteurs SQL et les notifications du batch gardent la date
traitée, le contexte de reprise et les comptes préservés. Les watchers sont
vérifiés avant l'étape 12 comme dans le parcours standard.

La commande du lanceur ajoute `-RecoverySessionDate AAAA-MM-JJ`, transmise au
runner via `--us-pipeline-recovery-date`. Cet argument est réservé à
`us_pipeline` ; la section persistante de `batch.yaml` n'est pas modifiée.

## Validation du 19 novembre

**262 tests ciblés réussis** : fenêtres et changement de date Paris/New York,
lundi et jours fermés, ouverture et décalage saisonnier, compteurs partiels,
tentatives ignorées, garde de concurrence, reçus, exclusion des comptes déjà
terminés, conservation du filtre exact, commande PowerShell et bouton IHM.
Les processus et transports des tests sont factices.

Le plan réel a été construit à blanc : séance **2026-11-18**, **15 étapes**
au total (11 pour `default`, puis 11/12 pour `test1` et `test2`), profil
`q051_b_anti_sl_witness_v1`, modèle `model-factory-20261118172104-2f6a31`,
mode PAPER. Aucun workflow, téléchargement ou ordre n'a été lancé lors de
cette vérification. Reçu :
`artifacts/operations/us_pipeline_launcher_repair/20261119-v1/recovery-button-preflight.json`.
Le rapport des tests est `recovery-button-tests.xml` dans ce même dossier.
