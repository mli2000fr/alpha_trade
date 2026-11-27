# Suivi Pipeline des workflows lancés par un batch — 27 novembre 2026

Le batch `us_pipeline-20261127220502-5383c238` exécute le workflow
`20261127_230504_516dac04` dans un processus distinct de Streamlit.
À 23:38 Europe/Paris, il est actif à l'étape 2, `Data Sanitizer Daily` :
sous-run `20261127_232849_7feb9a57`, 6 952/12 329 symboles traités au constat.

Le registre de l'IHM ne connaissait que ses propres processus en mémoire.
Sa normalisation pouvait donc présenter un workflow externe vivant comme
« Arrêté », bien que le runner continuât d'écrire ses reçus et ses logs.

Le suivi lit désormais le verrou exact `pipeline_workflow`, vérifie son PID
et son identité de création via le contrôle existant de réutilisation des PID,
puis consulte les reçus canoniques du workflow et de son sous-run courant.
Les liens parent/enfant et les identifiants sont vérifiés. Ces instantanés
alimentent les runs actifs, l'historique affiché et la lecture d'un run précis.
Un ancien index « stopped » ne remplace plus un reçu actif qualifié.

Cette observation ne réécrit pas les reçus du runner, n'adopte pas ses processus
et ne modifie aucun verrou. Le bouton Arrêter est désactivé pour ces lignes :
le registre local ne peut pas arrêter un workflow qu'il ne possède pas.
Un processus mort, un verrou d'un autre propriétaire, un reçu manquant ou
un workflow terminé ne sont pas déclarés actifs par cette lecture.

Validation : tests du suivi externe, du registre et de la page Pipeline réussis
avec un répertoire temporaire court sous Windows. Les tests de contrôle de
processus sont isolés et n'utilisent ni SQL réel, ni fournisseur, ni broker.
Le contrôle réel s'est limité à lire le verrou et les deux reçus ; le batch
n'a pas été arrêté, relancé ou reconfiguré.
