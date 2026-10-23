# P03 — premier retest confirmé : non confirmé

22octobre2026. **TERMINÉ / NO_GO_P03_NOT_CONFIRMED / AUCUNE PROMOTION.**
Dossier canonique : `artifacts/research/us_oracle_retest_p03/20261022-v1`.
[Protocole préenregistré](oracle_retest_p03_20261022.md).

## Conclusion

Attendre le premier retest confirmé ne bat pas l'entrée Winner sur les deux
années. P03 dépasse la simple attente en2025, mais est inférieure aux deux
témoins en2026. Le drawdown est aussi aggravé face aux deux contrôles à8bps.
Les gains unitaires appariés ne confirment pas d'avantage. Les minimums de
taille sont atteints ; les critères de confirmation échouent. **Ne pas activer
P03 et ne pas rechercher après coup une autre tolérance ou attente gagnante.**

Cela écarte ce protocole sur cette archive conditionnelle, pas tous les retests
possibles ni toute stratégie de timing. Pas de nouvelle preuve de direction.

## Règle effectivement exécutée

Premier breakout Winner seulement dans les vingt séances après le signal
Oracle : deux clôtures5m au-dessus du haut raw de la séance précédente après
franchissement frais, open contigu suivant. Niveau figé pour toute la tentative.

P03 attend le premier low proche du niveau dans une bande de1×ATR20 Wilder5m
de la **séance précédente achevée**, puis deux clôtures au-dessus, sur deux
bougies strictement après celle du retest. Au plus12bougies/une heure, même
séance ; pas de confirmation finale exécutée fictivement le lendemain.
Low sous la borne basse : annulation prioritaire, même si la bougie récupère.
Pas de nouvelle cassure, nouveau jour ou tentative après refus du risque.
L'open suivant fournit le prix réel ; pas de fill de limite au niveau touché.

DELAY_CONTROL attend six bougies/trente minutes fixes, avec la même borne
d'invalidation et deux dernières clôtures au-dessus. Pas de retest exigé,
pas de délai ajusté au futur délai P03. L'annulation après son entrée ne doit
pas effacer rétrospectivement une décision déjà prise.

SL7/TR15/sansTP, vingt séances entrée incluse puis open21, demi-cible,
aucun renforcement. Capital annuel4 000USD, plafond d'admission brut1×,
frais8/25bps parjambe, composants natifs sizing/contraintes/cash et B4DD15.
Même formules, mais timing/cash/risque peuvent changer quantités et admissions.
Pas de modification du watcher, des modèles ou de la configuration de production.

## Cohorte et exclusions

213campagnes originales de recherche CatBoost PATH_H20, pas tout le TOP10
quotidien de production ni LightGBM. **204occasions/70titres communs**,9réservées
pour les trois bras :5chemins futurs incomplets et4horizons immatures. Données
SIP raw régulières non remplies issues des seules archives locales existantes.

La couverture nouvelle diffère du test P01, qui pouvait attendre une cassure
beaucoup plus tardive. P03, son témoin retardé et son Winner sont toujours le
même jour ; une occasion peut donc être qualifiée ici sans l'être pour P01.
C'est pourquoi l'ancienne ancre200campagnes reste séparée et les trois nouveaux
bras doivent être comparés **sur leurs204occasions communes**.

Par année d'exécution :113/91occasions Winner en2025/2026 ; par année Oracle,
116/88. Trois signaux de fin2025 entrent en2026. Unitaire regroupé par année
Oracle, portefeuille par année d'exécution. Les abstentions restent en cash,
avec rendement d'occasion zéro ; elles ne disparaissent pas du bilan.

| Signal/cause, population commune | Nombre |
| --- | ---: |
| Winner |204|
| Simple attente valide |117|
| Retest P03 confirmé |102|
| P03 invalidée avant confirmation |66|
| P03 sans retest dans la fenêtre |33|
| P03 retest non confirmé à temps |3|

P03 :56signaux en2025 et46en2026. Témoin retardé66/51. Ces signaux ne sont
pas tous des trades : positions déjà détenues, risque ou sizing peuvent refuser
l'entrée. Une seule tentative, aucun remplacement par le candidat suivant.

## Portefeuilles nets

Frais usuels8bps parjambe, pas de levier2×.2025 jusqu'au31décembre ;2026 au
30septembre. Capital réinitialisé chaque année. Le capital final inclut les
positions encore ouvertes, sans liquidation fictive annuelle.2024 non simulée.

| Année | Bras comparable | Net | DD max | Capital final USD | Fermés | Gagnants |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
|2025|Winner commun|+24,61 %|21,51 %|4 984,54|92|33,70 %|
|2025|Simple attente|+0,68 %|20,16 %|4 027,19|57|31,58 %|
|2025|P03 retest|+5,72 %|22,50 %|4 228,65|51|31,37 %|
|2026|Winner commun|+1,94 %|18,60 %|4 077,42|61|36,07 %|
|2026|Simple attente|+6,76 %|17,85 %|4 270,51|46|36,96 %|
|2026|P03 retest|−10,42 %|19,48 %|3 583,16|37|32,43 %|

L'ancienne ancre Winner200campagnes est reproduite : **+20,09/+1,94 %**, DD
18,79/18,60 %, pas le témoin commun élargi2025 ci-dessus. Ne pas confondre
un changement de cohorte avec une amélioration de la règle.

À25bps parjambe : Winner commun **+30,33/−0,24 %**, attente **−0,55/+7,65 %**,
P03 **+5,52/−11,48 %** ; DD P03 **22,16/20,28 %**. Les frais changent le chemin
du cash/B4 et les admissions : un portefeuille peut gagner davantage avec
des frais plus élevés sans qu'un trade identique soit rendu plus profitable.

| P03,8bps |2025|2026|
| --- | ---: | ---: |
| Trades gagnants/perdants |16/35|12/25|
| Gain/perte moyens USD |+115,96/−47,91|+60,33/−45,63|
| Détention gagnants/perdants, séances |16,81/5,69|13,42/5,96|
| Capital brut moyen engagé USD |991,93|1 138,63|
| Positions encore ouvertes à la fin |1|0|

Le B4DD15 conservé n'est pas une garantie de DD maximum15 %. Les états de
réduction et décisions de risque, gaps et positions déjà détenues comptent.

## L'entrée est-elle vraiment meilleure ?

Sur les102signaux P03, délai médian **15minutes après l'entrée Winner**,
contre30minutes préfixées pour le témoin retardé. Le protocole permet jusqu'à
60minutes ; ne pas confondre délai médian observé et paramètre optimisé.

Prix d'entrée P03 par rapport au Winner de la même occasion : médiane
**+0,16 %**, calculée par `100*(prix_P03/prix_Winner−1)`. Le retest n'assure
donc pas une entrée moins chère : la reprise confirmée peut déjà la renchérir.
Statistique descriptive conditionnelle à un signal, pas effet causal isolé
ni prix d'exécution pour les occasions finalement refusées par le risque.

Les unités appariées incluent les abstentions à zéro ; une unité n'est pas un
portefeuille avec capital et refus de risque. Les sorties et frais sont identiques
aux règles de parcours. La garde de gap3 % et le sizing restent appliqués par
le portefeuille natif ; aucun des102signaux P03 n'a ici un gap signal/fill >3 %.

Après espacement conservateur OracleJ40 par symbole, sans chevauchement :

| Année Oracle | Occasions | Signaux P03/titres | P03−Winner, gain unitaire moyen | P03−attente |
| --- | ---: | ---: | ---: | ---: |
|2025|82|39/30|−2,77points|−0,51point|
|2026|59|30/23|−3,64points|−2,14points|

À25bps, surplus contre Winner **−2,59/−3,47points**, contre attente
**−0,47/−2,11points**. Bootstrap mensuel2 000tirages,graine731 :

- Contre Winner : IC95 %2025 **[−7,76 ; +1,23]**,2026 **[−11,04 ; +1,93]**.
- Contre attente : IC95 %2025 **[−3,17 ; +2,34]**,2026 **[−5,19 ; +0,18]**.

Douze/huit mois représentés ; minimum30signaux/10titres atteint chaque année.
Aucune borne basse positive. Pas de confirmation transversale ; ne pas sélectionner
après coup seulement2025 ou les cas où le retest donnait un meilleur prix.

## Vérification et portée

**213tests passés**, dont29P03 ; précontrôle distinct des213sélections/ATR
avant PnL, puis revue finale des204occasions,423signaux et846rendements après
coûts. Seize audits cash/sorties/B4, quatre ancres reproduites à l'octet près.
Statut final `PASS_P03_INDEPENDENT_SIGNALS_ATR_UNITS_CASH_B4_REVIEW`.
Même assistant, **pas revue humaine indépendante**.

Les sources, archives et résultats sont empreintés. Les seuils n'ont pas été
modifiés après observation des rendements. Pas de nouvelle collecte ou de SQL,
LLM, entraînement, ordre, modèle, batch ou paramètre de production modifié.
Téléchargements en cours non touchés. P03 quitte la liste à tenter ; P04/P07
restent non lancées.

Réserves : cohorte initiale déjà conditionnelle aux anciens signaux/chemins
futurs/survivants, nouveau gate de couverture future, années déjà étudiées,
PIT/identités/événements historiques non entièrement qualifiés. La table
d'opérations sur titres héritée est vide : pas une preuve d'absence d'événement.
Tolérance sur raw5m cohérente, mais risque/sizing réemploient les archives daily
ATR/ADV ajustées comme les contrôles. Pas de NBBO, file d'attente ni latence
historique qualifiés : **recherche exploratoire, pas parité live complète**.

## Pièces

Dans le dossier canonique : `protocol.json`, `report.json`, `final-audit.json`,
`annual-summary.csv`, `signals.parquet`, `signal-decisions.parquet`,
`reservations.parquet`, `unit-results.parquet`, `nonoverlap.parquet`,
`session-quality.parquet` ; seize sous-dossiers de cas avec trades, marks,
décisions, maintenance et événements B4.

SHA256 rapport : `d0b74c795923894d678fa837b0d557ab20ac558c6356ecd6ccbd8e6413d607fd`.
