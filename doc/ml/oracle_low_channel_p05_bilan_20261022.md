# P05 — canal des dix derniers creux : non confirmé

22 octobre 2026. **TERMINÉ / NO_GO_P05_NOT_CONFIRMED / AUCUNE PROMOTION.**
Canonique : `artifacts/research/us_oracle_low_channel_p05/20261022-v2`.
[Protocole figé](oracle_low_channel_p05_20261022.md).

## Conclusion

Remplacer le trailing15 % par le canal des dix creux quotidiens ne fait pas mieux
que le témoin **sur les mêmes occasions admissibles**. Rendement dégradé dans
les deux années, drawdown aggravé, et pas de confirmation du gain unitaire.
Ne pas activer en production ni optimiser N après observation de ces pertes.
Cette non-confirmation porte sur le protocole et la cohorte ci-dessous, pas sur
tous les canaux possibles ni une impossibilité universelle de gérer les sorties.

## Règle réellement testée

Même entrée Winner : franchissement frais du haut brut de la séance précédente,
deux clôtures5m régulières au-dessus, achat à l'open contigu suivant. Pas simple
attente de cinq minutes ni filtre P01. LONG, demi-cible, aucun renforcement.

SL initial7 % immédiat ; première mise à jour après la clôture du jour d'entrée.
Le stop est ensuite le maximum de son niveau précédent, du SL initial et du
plus bas des dix séances complètes, effectif à l'open suivant. Il ne descend
jamais. Pas de TR15 restant, TP, vente partielle, buffer ATR, MA ou réentrée.
Échéance conservée : vingt séances entrée incluse, vente à l'open21.
Gaps à l'ouverture réellement disponible, pas au niveau garanti du stop.

Inspirations, adaptation propre : [document413, stop extrema](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Highest-high-lowest-low-stop.md)
et [document492, Turtle](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/M-Language-Turtle-Trading-strategy-implementationsV-10.md).

## Couverture : ne pas confondre effet du canal et effet de sélection

Ancre200 campagnes/69titres du Winner P01. L'archive ne permet de reconstruire
tous les canaux des vingt jours potentiels que pour **109 campagnes/36titres**.
Les91 autres sont réservées **dans les deux bras communs**, avant les sorties,
même si elles auraient été stoppées avant la date manquante. Motifs/dates dans
`coverage-reserves.json`. Aucune interpolation ou import de daily ajustés.
Le nombre de titres doit être lu dans `report.json` ; ne pas additionner les
effectifs annuels, certains symboles reviennent dans les deux années.

Par année d'exécution :54 signaux en2025 et55 en2026. Par année Oracle :57/52 ;
trois signaux de fin2025 entrent en2026. L'unitaire est regroupé par année Oracle,
le portefeuille par année d'exécution. Les refus risque/positions déjà détenues
restent conservés ; pas de remplacement par un candidat hors classement.

L'ancre complète est publiée pour contrôle, mais **P05 doit être comparée au
Winner commun**, pas au Winner complet : enlever91 occasions change déjà la
performance. Population de recherche CatBoost PATH_H20 conditionnelle aux
chemins futurs complets/survivants, pas tout le TOP10 quotidien ni le LightGBM
de production. Ce filtre de couverture future supplémentaire limite la portée.

## Portefeuilles nets

Capital remis à4 000USD chaque année, plafond d'admission1×, composants natifs
de sizing/frais/contraintes et B4DD15 identiques. Coûts usuels8bps par jambe.
2025 jusqu'au31décembre ;2026 jusqu'au30septembre. Pas de simulation2024.
Capital final comprend le mark-to-market restant, sans liquidation fictive.

| Année | Bras | Rendement net | DD max | Capital final USD | Fermés | Gagnants |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
|2025|Winner complet, ancre|+20,09 %|18,79 %|4 803,41|90|33,33 %|
|2025|Winner commun|+2,08 %|15,42 %|4 083,14|46|32,61 %|
|2025|P05 canal10|−10,54 %|18,98 %|3 578,33|45|22,22 %|
|2026|Winner complet, ancre|+1,94 %|18,60 %|4 077,42|61|36,07 %|
|2026|Winner commun|−8,60 %|18,96 %|3 655,87|38|31,58 %|
|2026|P05 canal10|−10,18 %|20,64 %|3 592,94|33|18,18 %|

P05 contre témoin commun : **−12,62points en2025, −1,57point en2026**.
DD aggravé de3,56/1,68points. Une position reste ouverte fin2025 dans les deux
bras communs ; aucune finseptembre2026. B4DD15 n'est pas un stop garanti du
portefeuille à15 % : ses états/admissions et gaps peuvent produire davantage.

Stress25bps par jambe : Winner commun **+3,01/−9,42 %**, P05 **−12,90/−11,01 %**.
DD P05 **20,88/21,18 %**. Les coûts changent cash, B4 et admissions : une hausse
de frais peut donc améliorer un portefeuille donné par un chemin différent,
pas parce que les frais créent un gain sur une transaction identique.

| Mesure P05 à8bps |2025|2026|
| --- | ---: | ---: |
| Gains/pertes fermés, nombre |10/35|6/27|
| Gain moyen USD |63,43|78,79|
| Perte moyenne USD |−30,52|−32,59|
| Gain/perte moyens sur prix, nets |+18,76/−7,19 %|+13,05/−5,93 %|
| Détention gagnants/perdants, séances |18,70/5,69|18,67/6,96|
| Capital brut moyen engagé USD |571,77|917,66|
| Capital engagé moyen / equity |15,26 %|22,85 %|

Le capital moyen et les quantités diffèrent entre variantes à cause des sorties
et du risque, pas d'une modification du sizing initial configuré. L'unitaire
apparié ci-dessous permet de distinguer ces effets de portefeuille.

## Effet par occasion, sans chevauchement

Conserver une seule occasion par symbole jusqu'à disponibilité OracleJ40,
pour les deux bras. Pas des trades exécutés indépendants ni des rendements
capitalisés. Bootstrap de mois Oracle,2 000tirages,graine731.

| Année Oracle | Occasions | Stop remonté | Gain moyen P05−Winner | IC95 % mensuel | Gain à25bps |
| --- | ---: | ---: | ---: | ---: | ---: |
|2025|37|24|−1,61point|[−6,09 ; +1,43]|−1,61point|
|2026|33|18|+0,82point|[−2,29 ; +3,67]|+0,82point|

Onze/huit mois représentés. Les minimums30occasions/10remontées sont atteints,
mais les conditions préfixées de confirmation échouent. L'effet unitaire2026
positif reste incertain et ne se traduit pas par un meilleur portefeuille.

## Vérifications et réserves

**184 tests passés**, dont24P05. Douze replays avec contrôles cash/sorties/B4 ;
quatre ancres reproduites à l'octet près. Revue finale distincte :5 668canaux,
436rendements unitaires après coûts et1 245mises à jour du canal vérifiés.
Statut `PASS_P05_CHANNEL_CAUSALITY_BASELINE_EXIT_CASH_B4_REVIEW`.
Même assistant, **pas revue humaine indépendante**.

V1 conservée non validée après divergence d'arrondi du vérificateur, pas du
canal exécuté. V2 corrige l'arrondi scalaire des demi-cents puis rejoue tout.
Les68fichiers d'exécution/canaux/units/nonoverlap comparés v1/v2 sont identiques
à l'octet près (`rounding-replay-comparison.json`) : aucun seuil optimisé après
résultats. Anciennes empreintes v1 historiques, canoniquev2 seule validée.

Les données raw et les sessions sont qualifiées selon les règles de l'archive,
mais la table d'opérations sur titres héritée est vide : cela ne certifie pas
l'absence d'événement ni une résolution complète des identités. Couverture
sectorielle/PIT, NBBO, files d'attente et latence des remplacements non qualifiés.
Années2025/2026déjà étudiées, pas holdout neuf ; pas parité live complète.

Aucun nouvel appel marché/LLM, entraînement, SQL, ordre, modèle, batch ou
paramètre de production modifié. Téléchargements en cours non touchés.
Registre actualisé ; P05 quitte la liste à tenter. P03/P04/P07 non lancées.

## Pièces à consulter

Dans le dossier canonique : `protocol.json`, `report.json`, `final-audit.json`,
`annual-summary.csv`, `entry-signals.parquet`, `coverage-reserves.json`,
`complete-session-lows.parquet`, `channels.parquet`, `unit-results.parquet`,
`nonoverlap.parquet` ; douze sous-dossiers de cas avec trades, valorisations,
décisions, événements B4 et, pour P05, `channel-updates.json`.
Empreinte du rapport : `704928e831d271d262a093c92db30eb0e586fbb9b0cbec4e1eb5102e3eb5e7f5`.
