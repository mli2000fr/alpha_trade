# P04 — Dual Thrust : test terminé, effectif insuffisant

22octobre2026. **TERMINÉ / INSUFFICIENT_P04_SAMPLE / AUCUNE PROMOTION.**
Canonique : `artifacts/research/us_oracle_dual_thrust_p04/20261022-v1`.
[Protocole figé avant calcul](oracle_dual_thrust_p04_20261022.md).

## Conclusion

P04 n'est **pas validée**. Le résultat est négatif en2025 et positif en2026,
mais ne repose que sur **quatre trades par année**. Après espacement conservateur
des occasions par symbole, seuls3/4signaux P04 sur3/4titres subsistent, contre
les30signaux/10titres requis par année. Il est impossible d'en déduire un
avantage directionnel robuste. Cela ne prouve pas non plus une inefficacité
universelle de Dual Thrust : ce pilote manque d'effectif.

Ne pas optimiser N, k ou la fenêtre après ces résultats, ni promouvoir le
rendement2026 isolé. Une éventuelle reprise nécessiterait un périmètre plus
large avec raw historiques et scores Oracle OOS qualifiés, un nouveau protocole
et un nouveau GO, pas une relance automatique ou un assouplissement des seuils.

## Règle réellement testée

À J connu après clôture, calculer sur les **quatre séances raw régulières
complètes jusqu'à J** : `R=max(max(H)-min(C),max(C)-min(L))`. Les daily sont
agrégés depuis les5m SIP ; C est le dernier close régulier5m, pas une certification
du prix d'enchère officiel de clôture. À l'ouverture de **J+1 seulement**, figer
les seuils `open±0,5R`, arrondis scalaires à8décimales. Ne pas utiliser les
H/L/close finaux de J+1 pour déplacer les seuils.

Première clôture5m strictement au-delà de l'un des deux seuils :

- UP en premier : acheter LONG à l'open contigu suivant, même séance.
- DOWN en premier : P04 s'abstient définitivement pour cette occasion.
- Pas de franchissement : cash. Dernière bougie franchissante sans open
  suivant dans la séance : pas de fill fictif le lendemain.

Une seule tentative, pas d'inversion, retest, compression, EMA/ADX, partiel
ou renforcement. Ce pilote LONG ne fournit pas un backtest SHORT dont
l'emprunt serait qualifié ; le seuil bas sert au contrôle de timing.

Sources FMZ : [document258 Dual Thrust OKCoin](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Dual-Thrust-OKCoin-%E6%9C%9F%E8%B4%A7.md)
et [document260 version OKEX pédagogique](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Dual-Thrust-OKEX%E6%9C%9F%E8%B4%A7-%E6%95%99%E5%AD%A6.md).
Adaptation propre, pas exécution des bots crypto publiés.

## Cohorte et abstentions

213campagnes originales de recherche CatBoost PATH_H20, pas tout le TOP10
quotidien ni le LightGBM de production. Les quatre séances antérieures et J1
sont disponibles pour112occasions. Après qualification commune des chemins :
**108occasions/37titres**, contre105réservées pour tous les bras comparables :
101lookbacks4incomplets,1chemin futur incomplet,3horizons immatures.

Toutes les réserves sont déterminées avant les sorties, même si le futur stop
serait survenu plus tôt. Pas d'interpolation ou mélange daily ajusté/raw.
Cette sélection future conditionnelle et la survivance héritée limitent la portée.

Par année d'exécution :54/54Winner communs ; par année Oracle :57/51occasions.
Trois signaux de fin2025 entrent en2026 dans le Winner à fenêtre20séances.
P04 et les contrôles J1 utilisent seulement J+1. L'unitaire est regroupé par
année Oracle, le portefeuille par année d'exécution. Pas de simulation2024.

| Décision sur les108occasions | Nombre |
| --- | ---: |
| Aucun seuil Dual Thrust franchi |86|
| Premier seuil UP, avec fill possible : P04 |8|
| Premier seuil DOWN, avec fill possible : abstention P04 |13|
| Premier seuil DOWN à la dernière bougie, aucun fill |1|

TIME_LONG a donc21signaux contre8pourP04. HIGH_J en a43 et J1_WINNER26,
contre108pourleWinner commun à fenêtre20séances. Les abstentions restent
des occasions à rendement zéro ; aucun remplacement par un titre hors classement.

## Témoins et résultats nets

Capital réinitialisé4 000USD par année, plafond d'admission brut1×, demi-cible,
composants natifs de sizing/contraintes/cash et B4DD15, **SL7/TR15/sansTP**,
vingt séances entrée incluse puis vente à l'open21, aucun renforcement.
Frais usuels8bps parjambe ;2026 jusqu'au30septembre. Pas de levier2×.
Mêmes formules de risque, mais cash/quantités/admissions peuvent diverger.

| Année | Bras sur le périmètre commun | Rendement net | DD max | Capital final USD | Fermés |
| --- | --- | ---: | ---: | ---: | ---: |
|2025|Winner, fenêtre20séances|+1,01 %|15,65 %|4 040,47|46|
|2025|Winner limité à J1, deux clôtures|−17,04 %|22,38 %|3 318,48|12|
|2025|HIGH_J, première clôture >haut de J|−16,17 %|21,57 %|3 353,14|18|
|2025|TIME_LONG, premier seuil UP ou DOWN|−11,92 %|19,35 %|3 523,06|12|
|2025|P04, premier seuil UP seulement|−9,70 %|11,68 %|3 612,04|4|
|2026|Winner, fenêtre20séances|−9,00 %|19,31 %|3 639,98|38|
|2026|Winner limité à J1, deux clôtures|+10,67 %|11,66 %|4 426,72|12|
|2026|HIGH_J, première clôture >haut de J|+18,86 %|16,55 %|4 754,53|21|
|2026|TIME_LONG, premier seuil UP ou DOWN|+8,70 %|6,27 %|4 348,18|9|
|2026|P04, premier seuil UP seulement|+20,60 %|6,12 %|4 823,93|4|

Ancienne ancre Winner200campagnes, distincte de cette cohorte réduite :
**+20,09/+1,94 %**, DD18,79/18,60 %. Les quatre cas de cette ancre sont reproduits
à l'octet près. Ne pas comparer directement le nouveau P04 conditionnel au
Winner complet comme si le périmètre n'avait pas changé.

Avec25bps parjambe, P04 **−10,00/+20,21 %**, DD11,94/6,25 %. Winner commun
**+2,19/−10,05 %**, J1_WINNER **−10,53/+9,68 %**, HIGH_J **−16,26/+17,74 %**,
TIME_LONG **−12,62/+7,88 %**. Les frais modifient aussi le cash/B4 et les admissions :
un portefeuille peut paradoxalement mieux terminer avec plus de frais sans
qu'un trade identique devienne plus profitable.

P04 n'a aucune position encore ouverte à la fin des deux périodes ; d'autres
bras ont du mark-to-market ouvert fin2025, conservé dans le capital final,
sans liquidation fictive. B4DD15 n'est pas une garantie de DD plafond15 %.

## Pourquoi2026 ne suffit pas

| P04 à8bps |2025|2026|
| --- | ---: | ---: |
| Trades gagnants/perdants |0/4|3/1|
| Taux gagnant |0 %|75 %|
| Gain moyen USD |sans gagnant|301,76|
| Perte moyenne USD |−96,99|−81,36|
| Capital brut moyen engagé USD |77,26|362,26|
| Capital engagé moyen/equity |2,03 %|8,13 %|

Ces taux sur quatre trades ne sont pas des probabilités fiables. Le DD réduit
est à lire avec la très faible exposition, pas comme une meilleure protection
de positions comparables à volume constant.

| Année | Titre | PnL net USD | Rendement net du trade |
| --- | --- | ---: | ---: |
|2025|PLTR|−102,47|−10,45 %|
|2025|W|−153,85|−16,32 %|
|2025|TROX|−66,89|−7,16 %|
|2025|SRPT|−64,75|−7,18 %|
|2026|CIEN|+61,59|+7,08 %|
|2026|TTMI|+560,10|+57,87 %|
|2026|QDEL|+283,60|+24,65 %|
|2026|INTC|−81,36|−7,16 %|

TTMI apporte environ **68 % du gain net2026** (560,10/823,93USD). C'est une
contribution comptable, pas un rejeu du portefeuille après suppression du titre.
Les gaps PLTR/W expliquent des pertes dépassant le SL7 % : ce stop déclenche
une sortie, il ne garantit pas le prix au travers d'un gap.

Le champ brut `holding_sessions` du ledger compte inclusivement le jour d'open
de sortie ; une sortie à l'open21 peut y porter21. Le contrat reste vingt
séances avant cet open, sans nouvelle journée de détention prolongée.

## Effet unitaire et effectif

Les unités incluent toutes les occasions communes, zéro en cas d'abstention,
pas seulement les trades exécutés. Elles n'appliquent pas les contraintes de
capital/risque : c'est le portefeuille natif qui les applique. Aucun signal
du périmètre n'a ici un gap signal/fill >3 %.

Espacement conservateur par symbole jusqu'à OracleJ40, même pour une occasion
sans signal P04 :37occasions2025 et34en2026, mais **3/4signaux P04** seulement,
sur3/4titres. Ce n'est pas une correction arbitraire du taux gagnant observé.

| Année Oracle | P04−Winner commun | P04−J1_WINNER | P04−HIGH_J | P04−TIME_LONG |
| --- | ---: | ---: | ---: | ---: |
|2025|−1,19point|+0,22point|+0,75point|+0,32point|
|2026|−0,38point|+0,62point|−0,85point|+0,77point|

Ce sont des gains moyens par **occasion**, pas rendements composés du capital.
Bootstrap de mois Oracle2 000tirages,graine731. Contre Winner : IC95 %
2025 **[−6,53 ; +2,80]**,2026 **[−5,96 ; +3,95]**. Les autres bornes basses ne
sont pas strictement positives non plus (TIME_LONG2026 atteint0, pas >0).
Onze/huit mois représentés, mais l'effectif réel de signaux manque largement.
Le surplus contre Winner reste négatif aux coûts25bps. Aucun critère de
confirmation n'est assoupli après le beau résultat2026.

## Vérification et portée

**242tests passés**, dont29P04. Précontrôle indépendant des213sélections/seuils
avant PnL ; revue finale108bandes,206signaux,412rendements unitaires après coûts.
24audits cash/sorties/B4 et quatre ancres exactes. Statut technique :
`PASS_P04_RANGE_FIRST_HIT_UNIT_CASH_B4_REVIEW`. Même assistant, **pas revue humaine
indépendante**. L'audit valide le calcul, pas la rentabilité future.

Sources/données/résultats empreintés ; aucune mutation des sources figées des
autres expériences. Aucun SQL, appel fournisseur/LLM, entraînement, ordre,
modèle, batch ou paramètre de production modifié. Téléchargements non touchés.
P04 quitte la liste des non-testées, mais n'est pas déclarée invalidée
statistiquement ; seuleP07reste non lancée.

Limites : cohorte survivante/conditionnelle, couverture future, faible effectif,
années déjà explorées, raw historique restitué et disponibilité PIT non entièrement
certifiés, table d'opérations sur titres héritée vide/incomplète, identités/NBBO/
files d'attente/latence non entièrement qualifiés. Risque et sizing réemploient
les mêmes archives daily ATR/ADV ajustées que les contrôles. **Pas de parité live
complète**, pas de nouvelle démonstration D1/D10.

## Pièces

Dans le dossier canonique : `protocol.json`, `report.json`, `final-audit.json`,
`annual-summary.csv`, `signals.parquet`, `signal-decisions.parquet`,
`opening-bands.parquet`, `reservations.parquet`, `unit-results.parquet`,
`nonoverlap.parquet`, `session-quality.parquet` et les24sous-dossiers de cas.

SHA256 rapport : `6e6e3058377262bcfb00f0ea5deab33ba609bf87b4847818c1a093f282456a0c`.
