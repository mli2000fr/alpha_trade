# US : options dans les TOP10/20/50 Oracle, indice H5 mais effectifs insuffisants

26 octobre 2026. **AUDIT CONDITIONNEL TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.**

## Réponse au périmètre demandé

Oui, la conclusion sur tout l'univers n'était pas une conclusion sur le TOP10,
TOP20 ouTOP50. L'audit est maintenant effectué séparément sur chacun des trois,
en sélectionnant les N premiers scores Oracle AVANT disponibilité des options,
qualité/maturité du futur et direction réalisée. Aucun titre de rangN+1 ne remplace
un titre non couvert. N est un nombre de titres, pas un pourcentage.

Il existe un signal descriptif plus favorable dans certaines petites cohortes,
notamment TOP20 àH5. Mais la couverture et le nombre de dates sont insuffisants
pour promouvoir ce filtre ou affirmer une direction prédite de façon fiable.

[Protocole](options_oracle_topn_protocole_20261026.md).

## 1. Oracle H20 et issues H5/H10/H20 : distinction importante

Inventaire des protocoles locaux et lineage SQL :seuls des modèles
`oracle_path_extreme20` sont disponibles. **Aucun Oracle parcoursH5/H10 trouvé.**
Aucun nouveau modèle n'a été entraîné et aucun modèle terminalH5 n'a été substitué.

Le classement est donc celui de l'Oracle PARCOURS H20. Les issues sont ensuite
mesurées sur le parcours complet de5/10/20séances, avec un SL10 propre à chaque
sens et comparaison des excursions bornées. Pas du cours de clôture àH5/H10/H20,
pas du véritableTOP futur, pas d'une vente réalisable au sommet.

Modèles figés sans compétition :

- Septembre2026 :`model-factory-20261014113232-bc35a7`, CatBoost,
  fold2025-12-10, train disponible au10juin2025, validation au9décembre2025.
- Octobre2026 :`model-factory-20261016180250-3b0515`, champion CatBoost,
  fold2026-01-08, train disponible au9juillet2025, validation au7janvier2026.

Hashes de poids/profils et causalité des dates des folds contrôlés. Ils ont été
physiquement entraînés en octobre :les scores de septembre ont été recalculés
en octobre. Leur causalité de données du fold n'est pas une preuve d'exécution
réelle avant les ouvertures historiques, ni une certification de tous les vintages.

## 2. Couverture : principal frein concret

29 629scores existants lus, sans nouvelle inférence/fit ; fichier courant1790titres.
Au moins95% de cet univers doivent être scorés à chaque date. Quinze dates de
septembre et le16octobre passent, soit16classements qualifiés.
Le23octobre :1647/1790=92,01%, donc date réservée, pas un TOP tronqué accepté.
Les autres dates d'octobre sans scores restent absentes, sans forward-fill.

Double feature volume ET OI avant décision, sur prixEODHD :

| Sélection | Candidats Oracle sur16dates | Avec les deux features | Couverture | Titres couverts distincts |
|---|---:|---:|---:|---:|
| TOP10 |160|24|15,00%|9|
| TOP20 |320|56|17,50%|22|
| TOP50 |800|178|22,25%|49|

Cette sélection de disponibilité n'est pas représentative des dix/vingt/cinquante
complets. Les titres peu couverts peuvent justement différer des titres couverts.
Ne pas extrapoler les AUC à tout leTOP ni déclarer les absentsSHORT/perdants.

## 3. H5 : résultat conditionnel descriptif

Mêmes observations pour volume seul, OI seul, moyenne50/50 de leurs rangs dans le
TOPN effectivement couvert, avant filtre futur. Trois références à effectif égal.
PrixEODHD uniquement. AUC moyenne des dates comportant LONG ET SHORT.

| Sélection | Issues valides totales | Dont observations contribuant à l'AUC quotidienne | Dates AUC | Volume | OI | Mélange |
|---|---:|---:|---:|---:|---:|---:|
| TOP10 |23|**7**|**2**|0,625|**0,875**|0,750|
| TOP20 |54|**44**|**6**|0,778|0,792|**0,894**|
| TOP50 |172|**151**|**8**|0,577|0,651|**0,658**|

Les jours ne contenant qu'une direction n'ont pas d'AUC définie :ils sont
conservés dans les comptes d'issues mais pas transformés en0,5. En revanche un
SCORE constant sur une date à deux classes donne bien0,5.

H5 :TOP10 neuf sociétés/7dates,20LONG-dominants et3SHORT-dominants ;TOP20
22sociétés/10dates,38/16 ;TOP50 48sociétés/13dates,108/64. Ce ne sont pas des
gagnants/perdants d'un portefeuille ni un taux de réussite à une barrièreTP.
Entrées effectivement validesTOP10 23septembre–1octobre ;TOP20/TOP50
15septembre–1octobre, dates chevauchantes.

L'AUC0,894 ne signifie pas89,4% de trades gagnants. Sur TOP10, l'AUC quotidienne
repose seulement sur quatre puis trois observations ; elle est très fragile.
Les AUC GROUPÉES, autre estimateur :TOP10 volume0,508/OI0,725/mix0,700 ;
TOP20 0,708/0,736/0,800 ;TOP50 0,589/0,619/0,642. Ne pas choisir a posteriori
l'estimateur le plus flatteur.

## 4. H10 secondaire

| Sélection | Issues valides | Observations des dates à deux classes | Dates AUC | Volume | OI | Mélange |
|---|---:|---:|---:|---:|---:|---:|
| TOP10 |23|8|2|**0,833**|0,500|0,750|
| TOP20 |54|52|8|0,683|0,679|**0,705**|
| TOP50 |172|160|10|0,504|**0,638**|0,602|

Pas d'amélioration systématique des deux composants :le mélange dépasse les
deux sur TOP20 mais pasTOP10/TOP50. Il ne s'agit toujours pas d'OracleH10.

## 5. H20 primaire : pas de conclusion défendable

| Sélection | Issues valides | Titres | Répartition LONG/SHORT | Évaluation |
|---|---:|---:|---|---|
| TOP10 |0|0|—|Non mesurable|
| TOP20 |4|2|4/0|AUC non définie, une seule classe|
| TOP50 |21|11|19/2|Une seule date à deux classes, quatre observations|

TOP50 :AUC quotidienne OI/mélange1,0 sur CES QUATRE OBSERVATIONS seulement,
pas21observations contribuant et pas une preuve de perfection. Ne pas publier
ce1,0 comme un avantage validé. AUC groupée0,500/0,763/0,816, aussi extrêmement
fragile avec deux observationsSHORT et des sociétés répétées.

Les manques de prix/maturités/ambiguïtés ne sont pas remplacés par des H20
partiels. Les sorties bornées du parent sont conservées exactement, aucune
redéfinition du label pour améliorer les résultats conditionnels.

## 6. Contrôles, preuve effectivement disponible et prix SIP

Dates d'entrée H-espacées choisies sur les décisions Oracle avant les issues :
H5TOP10 quatre issues, toutes une seule classe, pas d'AUC ;TOP20 neuf issues,
UNEdate informative,volume0,500/OI0,800/mix0,800 ;TOP50 vingt-sept issues,
UNEdate informative,0,683/0,692/0,729. Les chiffres ne constituent donc pas une
confirmation à dates indépendantes multiples. H20 :zéro issue de ces cohortes
espacées. Première observation par titre conservée dans le rapport machine.

EODHD :aucune issue àH5/H10/H20 dont les timestamps SQL score ET lineage étaient
effectivement antérieurs à la décision. La lecture principale est rétrospective,
pas un résultat live ou un backtest strict historiquement enregistré.

SIP séparé :aucun casTOP10 couvert ;un casTOP20 ;cinq casTOP50, tous H5 à
l'entrée19octobre, créés avant décision (signal16octobre). TOP50 :unLONG/quatreSHORT,
AUC0,75 pour chacun des trois scores. Aucun gain du mélange ni effectif suffisant.
Pas d'H10/H20. created_at est nécessaire mais pas un journal immuable de versions :
même ces cinq cas ne certifient pas à eux seuls un PIT exhaustif.

## 7. Verdict et suite bornée

**INDICE CONDITIONNEL H5 TOP20 À CONFIRMER, PAS DE GO ÉCONOMIQUE OU LIVE.**
Le résultat sur tout l'univers ne devait pas être transposé au TOP10 ; cette
nouvelle mesure confirme l'importance du périmètre, pas une facilité générale de
prédiction des extrêmes. Une sélection sur amplitude n'impose pas le sens.

Pour avancer :compléter les scores Oracle et la couverture options réellement
collectée sur les TOP ciblés, conserver les mêmes poids, observer de nouvelles
dates et des horizons mûrs. Un Oracle parcoursH5/H10 est une construction distincte,
avec nouvelle cible/entraînement/validation, non lancé dans cet audit.
Pas de choix duTOP20 ou d'un horizon parce qu'il paraît meilleur sur ces jours.

24tests passent. Revue hors ligne :264scores conditionnels (sélections imbriquées,
pas autant de cas indépendants),792lignes horizon,114AUC reproduites ; rangs Oracle
reconstitués sur le plein univers, labels parent inchangés, hashes vérifiés.
Même assistant, pas une seconde personne indépendante.
Aucun entraînement, nouvelle inférence, API/LLM, SQLécrit, ordre ou changement live.

Archives :`artifacts/research/us_options_oracle_topn/20261026-v1/` ; revue
`20261026-v1-review/report.json`. Scripts :`scripts.research.us_options_oracle_topn_20261026`
et`us_options_oracle_topn_review_20261026`. Ancien audit large conservé sans écrasement.
