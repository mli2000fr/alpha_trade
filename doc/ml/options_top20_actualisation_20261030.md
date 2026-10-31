# Filtre options du batch US : audit TOP20 actualisé au 30 octobre 2026

Conclusion : **branchement du batch vérifié ; indice descriptif surtout à H5,
plus faible à H10, insuffisant à H15/H20 pour conclure à un avantage stable.**
L'échantillon évalué reste une reconstruction rétrospective de septembre.
Aucune nouvelle sélection prospective n'a encore cinq séances complètes.

## Branchement effectivement utilisé

Dans `config.yaml`, `options_directional_filter.enabled: true`, `oracle_top_n: 20`,
`min_combined_score: 0.5`, `min_covered: 4`, couverture Oracle minimale 90 %.
Le filtre LLM est désactivé. Le nombre 20 désigne vingt titres, pas 20 %.

Le dernier plan planifié est
`artifacts/operations/us_pipeline/us_pipeline-20261029220502-3c3098ad/plan.json`.
Sa commande d'étape 10 appelle `service.options_directional.pipeline --phase predict`.
Les étapes 11 et 12 reprennent le même identifiant exact
`opt-6399bec5c0a647448aaa01c7880e08a4`. Le rapport de sélection est terminé,
séance du 29 octobre, cutoff du 30 octobre à 00:10:55 UTC : **13/20 couverts,
4 retenus LONG : BAND, COHU, UCTT, SIMO**. Cette preuve concerne l'exécution
du filtre ; elle ne signifie pas que tous ces titres ont été achetés.

La relecture du 29 octobre reproduit les vingt lignes du rapport : aucune
différence de sélection, motif, score combiné ou features volume/OI.

## Protocole figé

- Données SQL existantes uniquement, transaction US en lecture seule,
  horodatages SQL en UTC, aucun téléchargement, appel LLM, entraînement,
  nouvelle inférence Oracle, ordre ou écriture SQL.
- Cutoff : **30 octobre 2026, 18:43 UTC** ; dernière séance entièrement close :
  29 octobre. Les cours intraday du 30 octobre ne terminent aucun horizon.
- Univers courant `config/univers_batch/univers_filtred_tradable.txt`, 1 790 titres.
- Oracle parcours H20 : septembre
  `model-factory-20261014113232-bc35a7`, octobre
  `model-factory-20261016180250-3b0515`. Politique mensuelle reprise de l'audit
  antérieur, sans compétition entre modèles. Hashes, folds, disponibilité des
  labels d'entraînement/validation et lineage contrôlés.
- TOP20 initial fixé par score Oracle décroissant, symbole pour départager.
  Aucun remplacement par le rang 21 lorsqu'une option ou une issue manque.
- Features et sélection : réutilisation directe de
  `service/options_directional/features.py`, sans copie approximative du filtre.
  Volume **30Min**, snapshots Alpaca `indicative`, mêmes reçus, exclusions de
  conflits, appariements CALL/PUT, DTE 15–25 jours calendaires, préférence 20 jours,
  strike OI à moins de 5 % du cours. Volume et OI peuvent avoir des expirations
  différentes ; c'est la définition actuelle, pas une comparaison de contrats
  strictement identiques entre les deux composants.
- Écart `log(1+CALL) - log(1+PUT)` pour chaque composant ; rang relatif dans les
  TOP20 doublement couverts, moyenne 50/50. Minimum quatre couverts ; LONG
  seulement si score > 0,5 et dans la moitié supérieure. Aucun SHORT automatique.
- Décision cinq minutes avant l'ouverture officielle J+1, bornée au cutoff réel.
  Reçus options postérieurs exclus, pas de report d'OI ancien sur un nouveau jour.
- Prix actuels ajustés des splits, priorité de source configurée
  `eodhd_eod`, puis `alpaca_sip` seulement si la première manque. Sélection de la
  ligne complète ; aucune moyenne entre fournisseurs. Identité constante,
  séances complètes, OHLC et volume positifs ; pas de remplissage de trou.
- Entrée théorique à l'ouverture J+1 ; **parcours entier** de 5, 10, 15 ou 20
  séances, entrée incluse. Le classement Oracle reste H20 dans les quatre cas.

La cible principale reprend les audits précédents : comparer la plus forte
excursion favorable LONG avant son SL10 à la plus forte excursion favorable
SHORT avant son propre SL10. Les deux scénarios sont simulés séparément. Lors
de la séance où le stop est touché, les OHLC journaliers ne disent pas si le
sommet ou le creux est arrivé d'abord : calcul par bornes, issue ambiguë exclue
des taux/AUC lorsque ces bornes ne départagent pas les deux sens.

**« LONG dominant » n'est ni un trade gagnant ni une vente réalisable au sommet.**
Le SL10 est une définition d'issue de recherche, pas une modification du SL Winner
actuel. Cet audit ne simule ni portefeuille, frais, capital ni levier.

## Couverture et maturité

19 séances avec classement Oracle qualifié du 14 septembre au 29 octobre :
**380 couples séance/titre**, dont **99 doublement couverts (26,05 %)**.
89 ont effectivement un score après le minimum de quatre couverts ; 36 retenus,
15 sociétés distinctes sur l'ensemble de ces sélections.

Il manque des scores Oracle existants pour quinze séances d'octobre dans cette
fenêtre ; aucune inférence ou interpolation n'a été ajoutée pour les combler.
Les 19 classements contiennent 13 séances de septembre et six d'octobre.

Les résultats du filtre arrivés à maturité viennent de **sept séances de signal,
22–30 septembre** : 51 couples couverts scorés, dont un parcours ambigu ;
**50 issues départagées sur 21 sociétés**. Parmi les 22 retenus mûrs, **21 issues
départagées sur 10 sociétés**, et un parcours ambigu. Ce sont des signaux répétés,
pas 21 sociétés indépendantes ni 21 achats nécessairement exécutables ensemble.

Les 14 retenus des 27–29 octobre restent non mûrs à tous les horizons étudiés.
Les séances des 16 et 23 octobre, et du 26 octobre, n'ont pas le minimum de quatre
doublement couverts dans ce rejeu. Le résultat H5 ne reçoit donc pas encore de
confirmation prospective supplémentaire depuis le précédent audit.

## Résultats principaux : parcours protégé SL10

Les colonnes avant/après filtrage comparent les mêmes cohortes couvertes.
L'AUC est la moyenne des AUC quotidiennes ; seules les dates ayant les deux
directions réalisées peuvent y contribuer. Les rangs sont fixés avant les issues.

| Horizon | LONG dominant avant filtre | LONG dominant parmi les retenus | AUC volume | AUC OI | AUC mélange | Dates AUC |
|---|---:|---:|---:|---:|---:|---:|
| H5 | 34/50 = 68,00 % | **18/21 = 85,71 %** | 0,778 | 0,792 | **0,894** | 6 |
| H10 | 34/50 = 68,00 % | **17/21 = 80,95 %** | **0,781** | 0,633 | 0,734 | 7 |
| H15 | 31/50 = 62,00 % | 14/21 = 66,67 % | **0,663** | 0,525 | 0,610 | 7 |
| H20 | 31/50 = 62,00 % | 14/21 = 66,67 % | **0,663** | 0,525 | 0,610 | 7 |

Parmi les 29 non retenus évaluables mais scorés, proportions LONG dominant :
55,17 % à H5, 58,62 % à H10/H15/H20. Il y a donc aussi des occasions haussières
écartées. Les titres sans score ne sont pas classés artificiellement baissiers.

L'égalité H15/H20 ne signifie pas que les prix ne bougent plus : sous cette
cible, le SL10 a déjà borné suffisamment de parcours pour laisser les mêmes
directions dominantes. Les amplitudes des excursions peuvent encore changer.

## Sensibilité à la définition du mouvement

Sans stop, en comparant simplement les deux excursions maximales sur la fenêtre,
le résultat est moins favorable à l'interprétation d'une tendance durable :

| Horizon | AUC quotidienne du mélange, sans stop | LONG dominant parmi les retenus mûrs, sans stop |
|---|---:|---:|
| H5 | 0,817 | 17/22 = 77,27 % |
| H10 | 0,738 | 16/22 = 72,73 % |
| H15 | 0,527 | 7/22 = 31,82 % |
| H20 | 0,545 | 6/22 = 27,27 % |

Ici le parcours ambigu avec stops redevient mesurable : les deux maxima
journaliers sont connus même si leur ordre intrajournalier ne l'est pas. Les
dénominateurs 21 et 22 ont donc des définitions différentes, explicitement
séparées. Cela ne prouve pas qu'il faudrait vendre à un horizon particulier.

## Limites et décision

L'AUC élevée H5 demeure **un indice sur un très petit échantillon**, pas une
probabilité de réussite de 89,4 %. Les fenêtres se chevauchent et les titres se
répètent. En espaçant les dates couvertes d'au moins H séances, il ne reste que
deux dates informatives à H5, une à H10/H15/H20. Les intervalles bootstrap par
date fournis dans le JSON restent descriptifs : ils ne corrigent pas cette
dépendance temporelle et sectorielle.

Les scores de septembre ont été physiquement calculés en octobre. Les folds
sont causaux selon leur contrat, mais ce n'est pas une preuve de disponibilité
des scores avant les ouvertures de septembre. Dans le sous-ensemble dont les
scores étaient réellement créés avant la décision, **zéro issue mûre du filtre**
est disponible aujourd'hui. Les prix sont par ailleurs des versions actuelles,
pas un historique certifié de leurs révisions ; l'univers courant introduit
un biais de survivance. L'OI indicative n'est pas une donnée OPRA certifiée,
et les volumes CALL/PUT ne révèlent pas le sens des transactions.

**Pas de modification du filtre ou de l'horizon de détention sur ces résultats.**
Conserver les résultats comme référence et évaluer ensuite les cohortes
prospectives déjà archivées, lorsqu'elles mûriront. Aucun suivi automatique
supplémentaire n'a été créé.

## Livrables et vérification

- Script : `scripts/research/us_options_top20_refresh_20261030.py`.
- Dossier final : `artifacts/research/us_options_top20_refresh/20261030-v2/`.
  Protocole, sources et données figées, scellements SHA256, couverture journalière,
  décisions et parcours individuels CSV/Parquet, `report.json`.
- Relecture : `artifacts/research/us_options_top20_refresh/20261030-v2-review.json` ;
  cohérence des comptes, hashes et parité des vingt lignes du dernier batch.
  Relecture par le même assistant, pas une validation humaine indépendante.
- **21 tests réussis** : tests de l'audit et du filtre courant. Ils couvrent
  notamment les parcours ambigus, les séances manquantes, les changements
  d'identité, le classement avant les options et la distinction entre causalité
  des folds et disponibilité physique des scores.
- `20261030-v1` est une extraction de travail conservée : une correction du
  champ de liste diagnostique et du choix des dates sans chevauchement a conduit
  au dossier final v2, sans changement des résultats principaux.
