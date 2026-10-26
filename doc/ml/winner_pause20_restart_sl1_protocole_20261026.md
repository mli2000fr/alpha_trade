# DD15/pause20 : reprise SL1 pendant vingt séances puis retour SL5

26octobre2026. Une variante supplémentaire, sans remplacer celle en cours.
TOP20,4kUSD,minimum70USD,FULL sans renfort,cap1x,SL5/sansTP/TR/open21,
janvier2020–décembre2024 continu, mêmes frais8pb/jambe et règles natives.

## Cycle exact

1. Avant le premier coupe-circuit : nouvelles entrées SL5.
2. DD15 depuis le sommet du cycle : liquidation100% causale, annulation des plans.
3. Pause de vingt séances NYSE complètes APRÈS le jour de liquidation. Reprise
   à l'ouverture de la21e séance suivante, sans apport/reset du DDhistorique.
4. Dès cette reprise, nouvelles entrées SL1 pendant vingt séances officielles,
   séance de reprise INCLUSE. Aucun TP/trailing, horizon de détention inchangé.
5. À l'ouverture de la21e séance active : nouvelles entrées de nouveau SL5.

Une position effectivement entrée sous SL1 le CONSERVE jusqu'à sa sortie :
jamais élargissement rétroactif àSL5. Les plans non tentés sont requalifiés au
changement de phase sans prolonger leur échéance ; choix selon l'entrée réelle,
pas seulement le jour du signal. Le plafond historique d'admissionSL3 reste
identique aux témoins ; pas de grossissement au-delà de ce plafond pour SL1.

Si un nouveau DD15 arrive, même pendant la phase SL1 : nouvelle liquidation,
pause20, puis nouvelle phase complète SL1 de20séances. Pas de compteur en
nombre de trades, pas de jours calendaires ou de pause3mois cachée. Fériés,
week-ends, séances abrégées et DST respectés. Aucun plafond historiqueDD25.

## Recherche isolée et audits

Contrôleur/adaptateurs limités au processus, aucune source scellée de production
ou de témoins modifiée. Calendrier de phase calculé seulement depuis les reprises
effectives déjà survenues ; aucune lecture de leurs résultats futurs. Préparation
des mêmes archives et paramètres que la pause20 simple ; pas besoin d'attendre
ses résultats pour simuler le nouveau compte.

Audits cash/frais/quantités/sorties scalaires, ventes globales, pauses plates,
reset sur capital restant, vingtséances, phase de CHAQUE achat effectif et stop
gelé des lots. Tests d'une position SL1 encore ouverte après retour au modeSL5
et d'un plan non exécuté changeant de phase. Contrôles de restauration des
adaptateurs et de non-lecture des reprises futures.

Comparaison finale : sans pause, pause3mois, pause20/SL5, pause20/repriseSL1.
Si le témoin pause20 n'est pas terminé, marquer la comparaison en attente,
pas de nouveau calcul du témoin. Rapports globaux et annuels, DD total et de
cycle, exposition, taux gagnant, gains/pertes et achats par phase.

Commande : `python -u -m scripts.research.us_winner_pause20_restart_sl1_20261026`.
Sorties : `artifacts/research/us_winner_pause20_restart_sl1/20261026-v1`.
`progress.json`, `report.json`, `comparison.json`/`.csv`, `annual-comparison.csv`.
Archives locales uniquement, aucun SQL/API/LLM/entraînement/ordre/modification
production. Exploratoire, historique déjà vu et biais hérités OOF/survivants/
secteurs actuels/coverage future. SL1 ne garantit pas1% de perte en gaps ;
DD15 par cycle n'est pas un plafond des pertes historiques cumulées.
