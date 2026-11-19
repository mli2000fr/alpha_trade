# Pipeline US — finalisation, comptes et Telegram — 19 novembre 2026

## Incident constaté

Le lancement du 17 novembre à 23:05 a terminé les onze étapes demandées du
compte `default` le 18 novembre à 01:21:54, workflow
`20261117_230508_16cfe43d`. Les étapes 11 et 12 avaient leurs notifications
Telegram marquées envoyées dans leurs journaux. Le batch multi-compte était
cependant `FAILED` : le lancement de `test1` rencontrait encore un workflow
considéré actif. `test2` n'avait pas démarré. Les compteurs conservés étaient
15 demandés, 11 reçus/persistés et un échec.

Le lanceur PowerShell 30944 restait actif après la sortie du runner Python.
`Start-Process -Wait` attend également les descendants persistants, notamment
le watcher. Le lanceur ne pouvait donc pas recopier les journaux temporaires,
écrire son bilan final ni appeler la notification de fin de batch. Son mutex
`Local\AlphaTradeForwardPITuspipeline` bloquait le passage suivant : le
18 novembre à 23:05, le lancement était ignoré avec `already-running`.

## Corrections

- Le lanceur utilise désormais `Start-Process -PassThru`, matérialise le handle
  puis attend uniquement le processus runner avec `WaitForExit`. Il exige un
  code de sortie renseigné et garde les watchers actifs après sa propre fin.
  La notification finale conserve le vrai statut et les journaux capturés.
- Le registre écarte les snapshots terminaux réellement libérés de sa liste
  des traitements actifs. Un workflow dont le thread termine encore son
  nettoyage est signalé `workflow_finalizing` et continue de bloquer une
  exécution concurrente.
- Le batch attend cette libération avant le compte suivant. Au-delà de
  120 secondes de finalisation, il échoue explicitement sans démarrer un autre
  compte. Les compteurs déjà acquis sont conservés.
- L'étape 12 ajoute le détail des nouvelles entrées/plans et leur capital
  alloué indicatif. Voir [le contenu Telegram](pipeline_telegram_10_11_12.md).

## Remise en service

Les journaux originaux, le record du workflow et leurs empreintes ont été
conservés sous
`artifacts/operations/us_pipeline_launcher_repair/20261119-v1/inspection.json`.
Après vérification des identités des processus et de l'absence de runner actif,
seul le lanceur obsolète 30944 a été arrêté. Le mutex est désormais libre ;
les watchers 36484 et 36664 sont restés actifs avec leurs identités d'origine.
Le reçu est `recovery.json` dans le même dossier.

Une ligne `RECOVERED_FIN` du journal batch documente l'échec historique ; elle
ne le transforme pas en succès. Aucun ordre, étape 11/12 ou message historique
n'a été rejoué. Le prochain lancement lira le script corrigé à son emplacement
habituel ; aucune réinstallation de la tâche n'est nécessaire pour ce correctif.

## Validation

**248 tests ciblés réussis**. Le rapport est conservé dans `tests.xml` sous
le dossier d'audit indiqué plus haut. Les tests d'arrêt de processus exigent
la visibilité Windows des processus qu'ils créent ; leur exécution restreinte
ne permettait pas de confirmer ces arrêts. La suite complète a ensuite réussi
avec cette visibilité, sans modifier les assertions.

Les tests utilisent des transports Telegram factices, des bases SQLite locales
et des processus Windows factices. Ils vérifient la fin du lanceur en succès
et en erreur alors qu'un enfant persistant reste vivant, la notification finale,
l'absence de chevauchement entre comptes et la conservation des protections
de verrouillage. Les notifications détaillées vérifient prix réels/références,
quantités initiales, calcul des montants, refus, remplissages partiels,
isolation run/compte/séance et anti-doublon.

Aucun pipeline de trading n'a été exécuté pour valider cette réparation. Le
premier prochain passage planifié reste la vérification en exploitation.
