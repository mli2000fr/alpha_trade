# Étape 12 — watcher obsolète, 28 octobre 2026

## Incident vérifié

Filtre exact : `opt-917380c30aab40cbb99362b3ead15e7c`.
Risque : `404615885b1041ac`. Exécution : `7246184a87924be8`.

Le moteur a échoué avant la création des campagnes Winner :
`Restart watcher: process predates the campaign implementation`.
Le watcher PAPER principal avait démarré le 28 octobre à 00:09 UTC,
avant la mise à jour du code Winner. Le contrôle d'ancienneté est conservé.

Le chargement ADV fonctionne désormais. Les refus 403 des cotations SIP
restent un problème distinct ; aucun repli IEX ni contournement du spread
n'est introduit.

## Correctifs

- Le démarrage du batch et l'admission Winner partagent désormais le contrôle
  d'ancienneté du processus. Un heartbeat récent ne suffit pas à qualifier
  un ancien interpréteur.
- L'étape 12 vérifie le watcher avant le marqueur durable d'effets possibles,
  les transitions et la création de plans. La seconde vérification juste
  avant la création des campagnes est conservée.
- Le moteur transmet `error_message` et `error_type` au bilan. Le CLI sort
  avec un code non nul pour un bilan `FAILED`, même si zéro ordre a échoué.
  Le wrapper ne publie donc plus `CHILD_COMPLETED` pour ce cas.
- La console affiche la cause d'échec réelle. Les hypothèses automatiques
  « marché fermé », « lundi 09:30 » et le conseil de forcer hors RTH sont
  supprimés en l'absence de preuve.
- Pour cette erreur précise, si les lectures OMS ont toutes réussi et
  attestent zéro intention/soumission/fill, les propositions non exécutées
  ne sont plus assimilées à des positions manquantes. Elles restent dans
  `unexecuted_targets`. Les positions broker inattendues et les autres
  contrôles de réconciliation restent vérifiés. Une lecture OMS échouée
  n'autorise pas cet ajustement.
- Le watcher utilise la session TLS vérifiée du projet, avec Certifi et les
  racines Windows. La vérification des certificats reste activée.

## Intervention et état

Le premier remplacement a révélé un échec TLS sur les GET broker. Après
correction, le watcher a été redémarré en conservant ses paramètres :
compte `default`, mode PAPER, intervalle 30 s, attente inactive 120 s,
heartbeat 300 s, TP standard 8 %, trailing standard 5 %, protection manuelle
5 %, activation à 1R. Les paramètres Winner figés ont leur propre contrat.

Le service est `READY` et les contrôles de démarrage et d'admission Winner
passent. Journaux :
`artifacts/operations/watcher_restart_20261028_tls/watcher-2dbba3d8/`.
Le PID lanceur est 6812 ; le heartbeat identifie son worker Python 16800.
Ce sont les deux processus d'un même lancement Windows, pas deux services.

Le dossier de preuve en lecture seule est :
`artifacts/operations/options_execution_watcher_incident_20261028/evidence.json`.
Il confirme les empreintes des liaisons, l'exécution SQL `FAILED`, zéro
demande d'ordre, zéro campagne, zéro position broker, zéro ordre ouvert,
zéro ordre et zéro fill depuis la tentative. Aucun achat n'a été relancé.

## Verrou initialement conservé

La tentative moderne contient déjà un marqueur `execution.effects_possible`.
L'examen automatique a refusé d'élargir l'outil de récupération pour archiver
ce type de tentative, en jugeant les preuves intégrées insuffisantes pour
exclure un doublon. Cette modification n'a pas été appliquée. La claim,
le résultat et le marqueur restent intacts. L'outil existant demeure limité
au crash historique `RiskDbIo` ; ne pas l'utiliser pour ce nouvel incident.

Une relance de l'étape 12 sur ce run reste donc bloquée. La reprise du verrou
précis nécessite une autorisation et une procédure ciblée vérifiant à nouveau
les effets avant toute modification ; il ne faut ni supprimer le marqueur,
ni choisir un nouveau run pour contourner ce blocage.

## Reprise ciblée autorisée et effectuée

Après cet état initial, l'utilisateur a explicitement demandé :
« tu peux retirer le verrour juste pour que je puisse relancer cette fois ci ? ».
Le 28 octobre, une procédure distincte, limitée aux identifiants exacts de
cette tentative, a revérifié l'exécution SQL `FAILED` avec la cause watcher
connue, zéro demande d'ordre, zéro campagne pour le compte, zéro exécuteur
et verrou de compte actif, ainsi que zéro position, ordre ouvert, ordre et
fill Alpaca depuis minuit UTC. Les empreintes de la tentative, du filtre et
du risque ont toutes été vérifiées sous le verrou système du wrapper.

La procédure `scripts.operations.recover_options_watcher_attempt_20261028`
a ensuite archivé les trois reçus locaux de cette tentative, sans modifier
l'historique SQL et sans lancer l'étape 12. L'outil de reprise automatique
et l'ancien outil `RiskDbIo` ne sont pas élargis.

Archive et preuve :
`artifacts/options_directional/opt-917380c30aab40cbb99362b3ead15e7c/execution_attempts/operator-watcher-recovery-2a98552321d54edf8d38b3a7b5c27d9c/`.
Le verrou de cette tentative est désormais libéré pour une relance manuelle.
Les contrôles normaux seront exécutés à nouveau ; ce n'est pas une garantie
de soumission ou de fill. Les 37 tests ciblés de preuve et de reprise passent.

Lors du contrôle final, le heartbeat demandé toutes les 300 secondes était
incompatible avec l'âge maximal de 180 secondes de l'admission Winner.
Les valeurs par défaut du CLI, du service et de l'IHM sont désormais de
60 secondes. En mode inactif, le cycle de 120 secondes envoie ainsi le
heartbeat avant son expiration, sans élargir le seuil de sécurité.
Le watcher a été rechargé et vérifié `READY` ; journaux :
`artifacts/operations/watcher_heartbeat_repair_20261028/watcher-59dd7011/`.
Aucun ordre n'a été envoyé par cette intervention. Les tests ciblés du
watcher, de configuration, de reprise et d'orchestration passent également.

## Validation

Tests ciblés : démarrage watcher, CLI d'exécution, reprise des tentatives
options, orchestration options, exécuteur, entrées ADV et pilotage watcher.
Les nouveaux cas couvrent un heartbeat sain avec code obsolète, le statut
`FAILED` du moteur qui doit échouer au niveau CLI sans autoriser de reprise
après effets possibles, et l'injection de la session TLS vérifiée.

La validation de production a seulement interrogé l'état du watcher et les
preuves d'exécution. Elle ne constitue pas un test d'achat : les permissions
SIP avant entrée restent à satisfaire.
