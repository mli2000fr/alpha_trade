# Options → étape 12 : reprise après échec avant tout ordre

## Incident et reprise vérifiée

Analyse options : `opt-917380c30aab40cbb99362b3ead15e7c`.
Run risque exact : `404615885b1041ac`, séance du **27 octobre 2026**.

Le premier enfant `run_execution.py` a échoué sur l'ancien import `RiskDbIo`
dans le chargement ADV/volatilité. Le wrapper avait déjà créé
`execution.claim.json` ; le second lancement s'est donc arrêté avec
`FileExistsError`. Ce verrou évite un doublon, mais ne distinguait pas cet
échec précoce d'une tentative ayant pu passer des ordres.

Le 28 octobre, avant intervention, vérifications refaites sous verrou local :

- aucune ligne `execution_runs` ou `execution_order_requests` pour ce run risque ;
- aucun plan Winner pour ce run (table de campagnes absente) ;
- aucun verrou d'exécution actif du compte ;
- aucun processus `run_execution.py` ou module du pipeline options encore actif ;
- compte principal explicitement **PAPER** : zéro position, zéro ordre ouvert,
  zéro ordre et zéro fill depuis le début de la tentative ;
- empreintes du rapport scellé, de la liaison risque et du résumé vérifiées ;
- journal exact attestant l'échec `RiskDbIo` avant moteur/transition.

Le verrou a été **déplacé**, pas supprimé, dans :

`artifacts/options_directional/opt-917380c30aab40cbb99362b3ead15e7c/execution_attempts/legacy-65fc21a8710f48ceb9bd49dafd190b73/`

Ce dossier conserve `execution.claim.json` et `recovery_proof.json`. Les
rapports options/risque et leurs empreintes restent inchangés. Aucune écriture
SQL, aucun ordre, aucune relance d'exécution par cette intervention.

## Contrat des nouvelles tentatives

`service.options_directional.execution_attempts` sérialise les tentatives avec
un verrou noyau `execution.lock`. La claim persistante contient un identifiant
de tentative, le run options, le run risque et les empreintes rapport/liaison.
L'enfant reçoit explicitement ces identifiants, dans le seul mode PAPER/default.

Avant la première phase pouvant créer un ordre de transition, une exécution
ou un plan Winner, `run_execution.py` écrit un marqueur durable
`execution.effects_possible.<attempt_id>.json`.

- Exception **avant** ce marqueur : l'enfant peut enregistrer un reçu
  `execution.pre_effect_failure.<attempt_id>.json` lié aux empreintes exactes.
  Une relance manuelle archive alors la claim précédente avant une nouvelle
  tentative, sans réécrire l'historique.
- Exception **après** le marqueur, enfant tué ou panne sans reçu : aucune
  reprise automatique ; l'état peut avoir produit des effets financiers.
- Enfant terminé : `execution.result.json` interdit un deuxième passage.
  « CHILD_COMPLETED » n'affirme pas qu'un achat a été rempli ou rentable.
- Reçu altéré, routage différent, exécution parallèle ou ancienne claim sans
  preuve : refus. Aucune remise à zéro globale des verrous.

Les commandes directes hors filtre options gardent leur contrat existant.
Les validations de fenêtre J/J+1, du compte, des cibles et du filtre sont
refaites au lancement ; la reprise n'autorise pas un snapshot périmé.

Validation : 79 tests de reprise/orchestration/CLI et non-régression passent,
puis un second passage de 47 tests incluant deux nouveaux scénarios du CLI
enfant (échec avant/après le marqueur). Le rapport scellé et la liaison risque
ont été revérifiés en UTF-8 après archivage : empreintes intactes et aucune
claim d'exécution active laissée par cette intervention.

## Ancienne claim

L'outil `scripts.operations.recover_options_execution_claim` est volontairement
limité au crash historique `RiskDbIo` prouvé par le journal exact. Il contrôle
la base en READ ONLY et le broker par GET avant archivage. La présence de toute
exécution, demande, campagne, ordre, fill, position ou processus actif bloque
l'opération ; il n'existe pas d'option « forcer » ou « ignorer les preuves ».

## Cotations SIP

Ce correctif concerne uniquement le verrou et la reprise. Le refus **403 SIP**
reste indépendant : les contrôles avant achat ne sont pas désactivés. Le
paramètre `risk_management.quote_spread_check_enabled=false` porte sur l'étape
11, pas sur la permission d'achat du watcher/exécuteur.
