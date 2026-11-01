# Reprise sécurisée depuis Pipeline

Évolution du 1er novembre 2026.

Le panneau **🔓 Déverrouiller une reprise — étapes 11/12 et watchers**, placé
après le centre d'exécution, apparaît uniquement lorsqu'un verrou concerné
est présent. Aucun bouton de déverrouillage n'est affiché sans verrou.

1. Choisir le compte et le verrou exact.
2. Cliquer sur **Vérifier avant déverrouillage**. Cette vérification ne modifie
   ni SQL ni les fichiers ; elle peut lire les positions et ordres PAPER.
3. Relire le compte, l'identifiant de sélection et le message de reprise.
4. Cocher la confirmation puis **Confirmer le déverrouillage**.

L'état est revérifié à la confirmation. Un changement de tentative ou de
verrou exige une nouvelle vérification. Le bouton ne lance aucun ordre,
n'annule aucune protection et ne démarre pas de watcher.

## Étapes 11/12 — filtre options

Le contexte est l'identifiant options explicitement choisi, sinon celui du
dernier lancement de l'étape 10, comme dans le tableau de sélection. Il ne
s'agit pas d'un nettoyage global de toutes les anciennes analyses.

Le compte doit être PAPER. Le service exige les empreintes cohérentes de la
sélection et du risque, aucun processus correspondant actif, aucun ordre
journalisé ni exécution SQL en cours. Il vérifie aussi le broker : aucune
cible déjà détenue, aucun achat ouvert, aucun achat exécuté depuis la
tentative. Une réponse historique tronquée ou une API indisponible interdit
la reprise. Une tentative risque non publiée doit posséder sa preuve native
d'échec avant publication ; une issue inconnue reste bloquée.

Les campagnes liées ne peuvent être conservées que si elles sont toujours
en attente, sans opération réservée/soumise et sans lot exécuté. Leurs lignes
SQL et leur clé unique compte/titre restent intactes. L'application prend
les verrous locaux risque/exécution et le verrou d'exécution du compte
pendant la confirmation.

Les fichiers de tentative sont déplacés sans suppression dans
`artifacts/options_directional/<run>/[accounts/<compte>/]manual_rearms/ihm-<id>/`.
`authorization.json` conserve l'action confirmée et les empreintes.
L'étape 11 réarmée exige ensuite 11 puis 12 ; une reprise d'exécution seule
conserve le risque lié et permet de relancer 12.

Les choix sont libellés **Réinitialiser 11 (relancer 11 puis 12)** et
**Reprendre 12 (conserver le risque)**. Si une tentative d'exécution existe
sur le compte choisi, elle est proposée en priorité à la première ouverture.
Réinitialiser 11 affiche un avertissement supplémentaire. L'étape 12 est
désactivée dans l'IHM tant que la publication risque courante manque ; la
commande directe explique également qu'il faut refaire 11 puis 12, au lieu
d'exposer une erreur de fichier absent. Aucune archive n'est réactivée
automatiquement après une réinitialisation confirmée du risque.

Les claims SQL du filtre LLM et les verrous globaux pipeline/backtesting
ne sont pas réinitialisés par ce panneau.

## Watcher arrêté et verrou de chef abandonné

Après un arrêt forcé, un heartbeat peut encore indiquer RUNNING et son verrou
`watcher:<compte>` rester présent jusqu'à expiration. Le nouveau démarrage
refuse alors le leadership, même si l'ancien PID a disparu.

Le nettoyage vérifie un heartbeat local, un PID réellement absent, l'absence
de tout autre watcher du compte et un verrou acquis avant ce heartbeat.
Les comparaisons exactes du propriétaire, des dates et du PID protègent un
redémarrage concurrent. Un PID réutilisé, un watcher distant ou non vérifiable
n'autorise aucun nettoyage. Seul l'ancien heartbeat libéré passe à STOPPED.

Ce contrôle est également appliqué avant un démarrage IHM et avant le
démarrage automatique du batch US. Une admission Winner reçoit désormais un
message explicite si le heartbeat pointe vers un processus absent ; elle
reste interdite tant qu'un watcher réel et récent n'est pas vérifié.

Après libération : démarrer les services locaux, attendre leurs heartbeats,
puis relancer 12. Aucun ordre ni nouvelle simulation n'est lancé par le bouton.
