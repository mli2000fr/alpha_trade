# Sprint 14 France — Bilan de validation du parcours opérateur recherche

Date : 5 octobre 2026. Décision : **terminé pour le périmètre de recherche
livré**, consultation des campagnes et reproduction d'une cellule économique
figée. Aucun GO économique, paper, live ou serving.

## Validation des deux lancements opérateur

Le propriétaire indique avoir lancé le replay depuis les deux pages proposées,
Pipeline et Backtesting. Le registre ne conserve pas la page d'origine :
ce point repose sur son retour, pas sur une attribution technique inventée.
Les deux derniers runs FR ont été examinés directement dans l'index, leurs
commandes, rapports, ledgers et journaux.

| Run | État | Code retour | stderr | Empreintes protocole/ledger | Métriques vs archive |
|---|---|---:|---|---|---|
| `20261005_182837_7d29eaad` | completed | 0 | vide | conformes | reproduction exacte |
| `20261005_182917_3a8093df` | completed | 0 | vide | conformes | reproduction exacte |

Les deux commandes sont identiques hors répertoire/ID : FR_EQ, fr_primary,
fold 6, Oracle TOP20 LONG, baseline, fiscalité inconnue taxée, coûts nominaux.
Les logs contiennent les quatre jalons preflight, loading, replaying,
report_written. Le calcul observé dure environ deux secondes après le
démarrage Python ; l'état du registre inclut aussi le démarrage/finalisation.

Les deux résultats donnent −27,8169310875 %, avec les mêmes coûts EUR :
commission 336 ; spread 36,00939450 ; slippage 72,0187890 ; taxes 217,12506.
Ce ne sont pas deux nouvelles expériences ni deux confirmations statistiques :
la même cellule a été reproduite deux fois, pour valider le parcours opérateur.
Le résultat négatif n'est pas une anomalie d'installation. Le −23,89 % cité
ailleurs correspond à un autre scénario fiscal, où les inconnus ne sont pas
taxés par hypothèse.

## Gates opérateur vérifiées

- Sélecteur France dans Pipeline, Diagnostic ML et Backtesting ; périmètre
  France séparé dans Batch. Défaut US conservé dans les trois pages historiques.
- Retour anticipé de la vue FR avant les formulaires et accès DB US.
- Consultation des campagnes explicitement référencées, y compris les
  modèles après réparation du fold 7 ; absence de source = erreur visible.
- Commande dédiée au service FR, options bornées au protocole et répertoire
  individuel dans les runs FR ; aucun module backtest US substitué.
- Historique FR partagé entre Pipeline et Backtesting, filtré par type ;
  runs FR/CN exclus du centre runtime US.
- Journaux, état du processus, durée, jalons, arrêt du run sélectionné et
  export FR_EQ/EUR. Pas de pourcentage temporel ou ETA inventé.
- Empreintes et reproduction exacte vérifiées avant présentation du résultat.
- Flags des deux rapports : `serving_enabled=false`, `canonical_writes=false`.
  Le service de replay lit les archives locales et n'effectue ni SQL, réseau,
  entraînement ou ordre.

Les 253 tests ciblés FR/US/CN/Batch et pages Pipeline/Backtesting du 14-B
passent. Les trois vues ont aussi été rendues avec le moteur de test Streamlit
sans exception. Cela ne constitue pas une exécution de toute la suite de tests
ou une mesure de sa couverture globale.

## Ce qui est terminé, ce qui ne l'est pas

Le parcours livré est décrit dans le [14-A](sprint_14a_ihm_recherche_isolee.md)
et le [14-B](sprint_14b_lancement_replay_et_suivi.md). Sa validation finale
opérateur est désormais consignée ici.

Cette clôture **ne signifie pas** que toutes les étapes quotidiennes US ont
été dupliquées en France. Le formulaire FR lance uniquement une reproduction
exploratoire figée ; il n'est pas un backtest libre, un lanceur général de
réentraînement, une ingestion ou une prédiction future. Aucun journal de
nouveau training/ingestion n'est donc présenté comme disponible.

Les réserves strictes prix/statuts/PIT/actions sur titres/fiscalité des Sprints
12/13 restent ouvertes. L'économie 13-D reste NO-GO exploratoire et la
confirmation 2026 reste réservée. Les messages de l'IHM ne doivent pas être
interprétés comme une qualification indépendante des données fournisseur.

Le GO du **Sprint 15, batchs prospectifs France, surveillance et sauvegardes**
a été reçu le 5 octobre 2026. La première tranche est décrite dans le
[Sprint 15-A](sprint_15a_catalogue_et_orchestration.md). Le catalogue et le
snapshot local du calendrier sont implémentés ; la collecte fournisseur
quotidienne, la restauration et les notifications réelles restent à qualifier.
Aucune tâche FR Windows n'a été installée automatiquement.
La prédiction future/shadow appartient au Sprint 16 ; aucun live n'est autorisé.
