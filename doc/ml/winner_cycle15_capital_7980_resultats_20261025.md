# Résultat DD15/pause3mois contre B4 seul — capital7980,17USD

Run terminé et audité :`COMPLETED_AUDITED_EXPLORATORY`. Sources et fichiers
de résultat vérifiés après exécution. Protocole initial inchangé :
[compte à capital égal](winner_cycle15_capital_7980_20261025.md).

2 janvier2020–31 décembre2024, TOP20, positions complètes sans renfort,
cap gross1x, SL5/sansTP/sansTR/H20-open21, frais8pb/jambe. Dépôt exact
7980,1667511581745USD, compte neuf sans positions/plans hérités.
Comparateur sans liquidation/pause déjà audité, réutilisé et non rejoué.

| Mesure | B4 seul, sans liquidation/pause | DD15 de cycle + pause3mois |
|---|---:|---:|
| Capital final valorisé USD |39598,15|27196,44|
| Rendement cumulé |+396,21%|+240,80%|
| DD historique maximal5m |−35,82%|−39,61%|
| Trades clôturés |1027|370|
| Gagnants/perdants |227/800|96/274|
| Taux gagnant |22,10%|25,95%|
| PnL gagnants USD |112246,78|69657,08|
| PnL perdants USD |−81032,24|−50867,17|
| Gain moyen gagnant USD |494,48|725,59|
| Perte moyenne perdante USD |−101,29|−185,65|
| Capital brut moyen investi USD |13256,25|7738,91|
| Exposition moyenne/capital courant |49,04%|35,36%|
| Frais USD |3099,22|1981,48|
| Positions finales valorisées |9|7|

La variante avec pauses termine12401,70USD plus bas, avec un DD historique
plus élevé de3,79points. Son taux gagnant supérieur ne suffit pas à améliorer
le résultat économique. PnL gagnants/perdants inclut les frais ; capital final
comprend les positions non clôturées. Ne pas soustraire les frais deux fois.

## Variante avec pauses : par année

Pas de remise à zéro annuelle, le capital passe d'une année à la suivante.

| Année | Capital final USD | Rendement annuel |
|---|---:|---:|
|2020|14442,65|+80,98%|
|2021|24918,57|+72,53%|
|2022|19716,45|−20,88%|
|2023|29232,31|+48,26%|
|2024|27196,44|−6,96%|

11 liquidations totales et11 reprises ;531 séances avec exposition,
727 sans exposition sur1258. Réarmement sur capital réel, aucun dépôt.
Audits :377 achats,327 sorties ordinaires,43 sorties globales, total370 ;
cash/frais/PnL/positions/DD, pauses à plat, dates officielles de reprise,
absence de plafond global et reset natif vérifiés.25 tests de qualification
passés avant lancement. Aucun SQL/API/LLM, entraînement, ordre ou changement
production. Les anciens comptes et leurs règles sont conservés.

## Conclusion bornée

À7980,17USD, contrairement au résultat à4000USD, les pauses n'améliorent
ni le capital final ni le DD historique. L'impact dépend de la trajectoire,
du capital, des seuils et des dates de réadmission : pas une règle protectrice
uniformément supérieure. Les pauses limitent localement un cycle mais leur
reset ne remet jamais les pertes économiques à zéro ; plusieurs pertes de
cycle se cumulent et les gaps peuvent dépasser15%.

Une exposition plus faible et les périodes sans positions sont observées,
mais ne constituent pas à elles seules une attribution causale détaillée des
12401,70USD d'écart. Ne pas en déduire automatiquement qu'il faut augmenter
l'exposition ou supprimer les garde-fous en production.

Les limites des deux protocoles demeurent : périodes déjà observées, univers
survivant/secteurs actuels, sélection de couverture future, OHLC5m et coûts
supposés, pas de holdout indépendant ni de parité live complète.

Rapport :`artifacts/research/us_winner_cycle15_matched_capital/20261025-v1/report.json`.
