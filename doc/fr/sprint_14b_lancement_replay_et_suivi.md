# Sprint 14-B — Lancement, historique et suivi des replays France

5 octobre 2026. Tranche implémentée après le GO Sprint 14 ; aucune promotion
économique, aucun paper/live. Complète le [14-A](sprint_14a_ihm_recherche_isolee.md).

## Utilisation

Redémarrer l'IHM pour charger les nouveaux services. Dans Pipeline ou
Backtesting, choisir **France — recherche uniquement**, puis descendre au bloc
« Lancer un replay FR — une cellule figée ».

Choisir un fold 6/7, une politique, une variante, un scénario fiscal et un
scénario de coûts ; cliquer sur « Lancer le replay France ». La commande
affichée avant lancement est une prévisualisation : la sortie `preview` est
remplacée par une sortie portant un ID unique. Les deux pages partagent le
même historique FR mais ont leurs propres clés de widgets.

| Paramètre | Choix autorisés / sens |
|---|---|
| Marché/base/devise | FR_EQ / fr_primary (alpha_trade_fr) / EUR ; pas de connexion SQL dans ce rejeu |
| Fold | 6 ou 7, développement déjà inspecté ; pas de confirmation 2026 |
| Politique | Oracle TOP20 LONG, ATR TOP20 LONG, contrôle uniforme LONG |
| Variante | baseline, retard d'une séance, plafond d'entrée 10 %, retard + plafond |
| Fiscalité inconnue | taxée ou non taxée **par hypothèse**, jamais qualifiée d'exonération |
| Coûts | nominal ou stress spread/slippage ×2 du protocole archivé |

Capital, candidats, rangs, calendrier, coûts et horizon restent figés. Le
retard conserve la date de sortie H5 originale : il ne crée pas une nouvelle
détention de cinq séances à partir du prix d'entrée retardé. Le plafond est
un budget à l'entrée frais inclus, pas un rééquilibrage quotidien.

Ce n'est pas un nouveau modèle, une optimisation de stratégie ou un backtest
de production librement paramétrable. Les entraînements et prédictions FR
futurs ne sont pas activés par ce bloc.

## Ce que fait le processus

1. Vérifie options, rapport 13-D, hash de son protocole, source 13-C,
   sorties archivées et empreintes des entrées/implémentations figées.
2. Charge les intentions et scores du protocole gelé ; revalide leur
   reconstruction. Ne consulte aucune donnée SQL ou API.
3. Reconstitue la tape d'une seule cellule à partir des archives partagées,
   sans nouveau filtre, reclassement ou suppression de candidat.
4. Écrit le protocole du nouveau run **avant** le calcul économique.
5. Rejoue le portefeuille avec le moteur exploratoire 13-D inchangé.
6. Compare toutes les métriques à la cellule correspondante du 13-D.
   Toute différence est une erreur de reproduction, pas un nouveau résultat
   sélectionnable comme amélioration.
7. Écrit ledger et rapport, avec empreintes, limites et indicateur de
   reproduction exacte. L'IHM vérifie les empreintes avant présentation.

Implémentation : `service/fr/research_replay_14b.py` ; construction de commande
dans `ihm/services/fr_replay_launch.py`. Le registre de processus existant est
étendu par un type distinct `fr-research-replay`, pas par une commande US
avec un simple changement de libellé.

## Suivi et incidents

Les sorties sont dans :

```text
artifacts/ihm_backtesting_runs/fr-research-replay/<run_id>/
  stdout.log / stderr.log / combined.log
  artifacts/
    protocol.json
    ledger.json
    report.json
```

L'état est conservé dans l'index partagé
`artifacts/ihm_backtesting_runs/history_index.json`, filtré sur le type FR
par la vue France ; les logs et résultats restent sous cet ID.
Le résultat final est récupérable après
redémarrage de l'IHM via son historique persistant.

Jalons observés dans stdout : `preflight`, `loading`, `replaying`,
`report_written`. L'état du processus passe ensuite à `completed` seulement
si son code retour est zéro. La barre suit ces étapes, pas une estimation de
temps restant ; actualisation toutes les cinq secondes. Logs et durée sont
visibles même si le calcul échoue.

« Arrêter ce run FR » arrête uniquement le run sélectionné. Il ne lance pas
de reprise automatique. Sur une exception contrôlée, `failure.json` conserve
l'erreur ; un blocage de tape peut aussi laisser `partial_ledger.json`,
diagnostic incomplet à ne pas utiliser comme performance. Un arrêt brutal
peut ne pas permettre ces écritures : l'état du registre et les logs font foi.

Un second lancement ne remplace pas une sortie existante ; il reçoit un
nouvel ID. Un replay FR actif empêche un autre replay FR de démarrer. Le
verrou partagé pipeline/backtesting existant reste respecté : cette tranche
ne change pas les règles de concurrence de l'application.

Les historiques FR et CN sont exclus du centre runtime US. La vue France
ne présente que `fr-research-replay`, pas les entraînements/replays US ou CN.
L'export JSON est identifié `FR_EQ_EUR_<run_id>` et conserve les hypothèses.

## Démonstration réalisée

Run `20261005_182035_4a93bd20`, du 5 octobre 2026 : fold 6, Oracle TOP20 LONG,
baseline, inconnus fiscaux taxés, coûts nominaux. Terminé en environ 3,5 s,
code retour 0, aucune ligne stderr. Rendement net reproduit : −27,8169310875 %.
Ce chiffre n'est pas comparable directement au −23,89 % du scénario nominal
où les inconnus ne sont pas taxés.

Quatre jalons apparaissent dans le journal, `exact_archive_reproduction=true`
dans le rapport. Scripts de vérification reproductibles :

```powershell
python scripts/research/fr_sprint14_smoke.py
python scripts/research/fr_sprint14_ui_smoke.py
```

Le premier crée un nouveau run, le suit et arrête **son propre run** au-delà
de 120 secondes ; le second consulte les trois vues avec le moteur de test
Streamlit, sans cliquer sur un lancement ni écrire en base. La consultation
Pipeline, Diagnostic et Backtesting a réussi sans exception.

253 tests ciblés FR/US/CN/Batch et pages Pipeline/Backtesting passent avec
`--no-cov`. Ce n'est pas une exécution de toute la suite ni une mesure de
couverture globale. `git diff --check` ne relève pas d'erreur de whitespace.

## Portée et suite

La tranche 14-B est opérationnelle pour ce replay figé. La validation stricte
des Sprints 12/13 reste bloquée ; le 13-D reste NO-GO exploratoire. Le
catalogue des batchs prospectifs FR et ses sauvegardes reste au Sprint 15.
Le [bilan final opérateur](sprint_14_bilan_validation_operateur.md) consigne
les deux replays lancés par le propriétaire et la clôture du périmètre
consultation/replay figé de recherche. Aucun nouveau
modèle ni aucune donnée de marché n'ont été modifiés par cette tranche.
