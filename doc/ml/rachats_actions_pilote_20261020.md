# Rachats nets d’actions — pilote documentaire borné du 20 octobre 2026

## Conclusion

**Pilote de données terminé et audité ; aucun avantage directionnel mesuré.**
Les données publiques SEC permettent de retrouver les rachats effectivement
comptabilisés. Les **43 montants comparables** de sept rapports originaux
concordent exactement avec le cache Companyfacts, après unités et échelles.
Cela ne suffit pas à assimiler les rachats en dollars à la réduction nette du
nombre d’actions : émissions, rémunérations en actions, classes et changements
de périmètre interviennent aussi.

**Aucun test de rendement H20/H60 ni backtest portefeuille n’a été lancé.**
Le protocole conditionnait ce test à la qualification du signal et des témoins
secteur/capitalisation disponibles à la date de décision. Ce premier audit ne
remplit pas ces conditions ; son effectif de vingt émetteurs est également
inférieur au seuil exploratoire de trente observations d’émetteurs qualifiées
fixé avant extraction. Ce seuil n’est pas une garantie statistique et ne rend
pas une petite étude descriptive impossible : il interdit ici de présenter
une poignée de cas comme le test comparatif annoncé.

Ce n’est donc **ni un résultat négatif de trading, ni une preuve de rentabilité**,
et aucune nécessité de fournisseur payant n’est démontrée. La suite éventuelle
est une standardisation du panel historique, pas un entraînement supplémentaire.

## Hypothèse économique et sources

Une entreprise réduisant effectivement son nombre d’actions, avec une capacité
de financement positive, pourrait avoir un profil plus favorable qu’une
entreprise diluant ses actionnaires. C’est une hypothèse, pas une relation
automatique entre rachat et hausse. Le rapprochement entre rachats et émissions
est discuté dans la [méthodologie AQR de rendement de distribution net](https://www.aqr.com/-/media/AQR/Documents/Insights/Alternative-Thinking/AQR-Alternative-Thinking_Capital-Market-Assumptions_Appendix2017.pdf).
Ce document porte notamment sur les rendements de long terme ; il ne démontre
pas une efficacité H20 ou sur notre TOP10.

Les [API SEC](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
agrègent les faits normalisés d’une entité. Les [tableaux de rachats Item 703](https://www.sec.gov/files/corpfin/pre-amendment-item-703.pdf)
séparent notamment les achats effectués dans des programmes annoncés des autres
achats. Une autorisation non exécutée n’est jamais traitée comme un rachat réel.

## Échantillon figé avant les montants et les prix futurs

- Univers courant : `config/univers_batch/univers_filtred_tradable.txt`,
  **1 790 symboles** ; biais de survivants explicitement conservé.
- Vingt premiers selon SHA256 de `BUYBACK-PILOT-20261020|symbole`, indépendamment
  du score Oracle, des rachats et des rendements. Aucun remplacement.
- Par société : premier **10-K original déposé en 2024**, pas premier rapport
  présentant un rachat favorable. Formulaires amendés et étrangers non substitués.
- Montants annuels uniquement, durée 350–378 jours, accession originale,
  date de dépôt, intervalle exact et unité USD. Pas de YTD pris pour un trimestre,
  ni d’état révisé d’un dépôt ultérieur injecté dans l’état initial.
- Les huit premiers dossiers ayant ce 10-K, dans l’ordre figé, constituent la
  revue des originaux. Aucun filtre par montant, signe ou résultat futur.

Sélection : **DBX, STN, RPRX, WRB, JEF, WTTR, CL, GSBD, HCSG, SR, URBN, TM,
NNN, XEL, LEA, NHC, PAGS, GSHD, SMFG, DGII**.

STN/TM/PAGS/SMFG n’ont pas ce 10-K dans le cache ; ils ne sont pas classés
« sans rachat ». Un premier formulaire étranger ou des taxonomies IFRS seraient
un périmètre de traitement distinct. Les années financières ne sont pas
forcément calendaires : DGII/SR ont notamment un exercice clos en septembre2024.

## Couverture constatée

| Mesure | Résultat |
|---|---:|
| Émetteurs sélectionnés | 20 |
| Avec le 10-K annuel attendu | 16 |
| Avec montant de rachat standard présent, zéro explicite compris | 11/16 |
| Avec cash opérationnel standard | 16/16 |
| Avec capex sous le seul tag initial | 9/16 |
| Avec actions ordinaires non dimensionnées et comparatif annuel | 10/16 |
| Avec produit d’émission sous le tag « common stock » initial | 6/16 |
| Rapports originaux présélectionnés | 8 |
| Rapports originaux complets obtenus | 7 |
| Rapport trop volumineux, conservé exclu | 1, GSBD |
| Montants cache/original rapprochés | **43/43 identiques** |
| Événements intégralement admis au test comparatif | **0** |

Ces taux décrivent **notre mapping initial**, pas le taux d’existence économique
des informations dans les rapports. Un champ absent n’est ni un montant nul,
ni la preuve d’une mauvaise qualité du fournisseur.

## Ce que la lecture des originaux change

| Société | Observation vérifiée | Conséquence |
|---|---|---|
| DBX | Rachats539,9M USD ; produit d’émission2,5M **net de taxes** ; classesA/B et rémunérations en actions | Ne pas appeler cette différence « réduction nette des actions ». Les classes doivent être rapprochées ; dépenses SBC338M ne se soustraient pas comme des émissions en dollars. |
| RPRX | Rachats304,759M USD ; actionsA en hausse, actionsB en baisse | La seule classe cotée ne mesure pas toute la dilution ; échanges de classes et structure économique à traiter. |
| WRB | Rachats537,163M USD ; activité d’assurance | Les ventes de titres détenus en portefeuille ne sont pas des émissions de l’assureur. CFO-capex industriel non directement comparable. |
| JEF | Rachats169,402M USD ; conversion d’actions ordinaires en préférentielles ; activité financière | Baisse du nombre d’actions et cash opérationnel négatif ne suffisent pas à produire un signal LONG/SHORT. |
| WTTR | Rachats61,770M USD ; plusieurs classes et intérêts minoritaires ; émissions non monétaires d’acquisition | Réconcilier le périmètre économique et séparer retenues salariales/programme ; ne pas supposer émissions nulles. |
| CL | Rachats1128M USD ; exercice d’options380M ; capex705M sous `PaymentsToAcquireProductiveAssets` | Les capex ne manquent pas : le mapping initial était trop étroit. CFO3745M−capex705M=3040M est un proxy, pas une qualification complète du financement. |
| HCSG | Rachats11,283M USD ; actions73,341M contre74,088M ; cash opérationnel43,498M et capex5,406M | Candidat numérique lisible : actions **−1,0083%**, proxy de cash libre38,092M. Une seule société-année, pas une preuve d’efficacité. |
| GSBD | Rapport au-delà de8Mio | Pas de traitement d’un fichier tronqué ni remplacement par un autre titre. |

HCSG illustre aussi la différence entre **zéro explicite** et champ manquant :
produit d’exercice d’options et réinvestissement des dividendes sont à zéro dans
le tableau2023. Les retenues salariales871k sont une ligne distincte des rachats.
Un emprunt court terme net nul ne signifie pas absence de dette au bilan.

Les sept montants de rachat présents dans les rapports relus concordent avec
leurs faits normalisés. Cela ne garantit pas une définition uniforme de tous
les programmes ni une valeur prédictive de ces montants.

## Disponibilité et limites statistiques

Les originaux ont été capturés **maintenant**, pas en2024. Nous ne fabriquons
aucune réception locale historique. Le dépôt SEC permet une borne documentaire
conservatrice : décision à la première ouverture complète strictement après la
date de dépôt, sans heure inventée. Le rachat pouvait être annoncé bien avant
le10-K ; ce protocole n’en fait pas une annonce nouvelle.

Le cache factuel et les tickers courants ne certifient pas toute l’histoire des
classes/identités et ajustements. Aucun contrôle apparié à capitalisation et
secteur **as-of** n’a été certifié ici. La validation ne remplace pas les classes
complexes par des valeurs plus commodes et n’utilise aucun rendement pour choisir
les dossiers.

Le TOP10 Oracle n’a pas été retesté. Un effet dans un univers diversifié de
rachats, même établi plus tard, ne prouverait pas son existence dans dix titres
extrêmes ; l’intersection devra être mesurée séparément avec les scores du jour.

## Archives, bornes et audit

- `artifacts/research/us_buyback_pilot/20261020-v1/` : extraction initiale et
  huit échecs de connexion locale, **zéro réponse fournisseur**. Dossier conservé.
- `artifacts/research/us_buyback_pilot/20261020-v2/` : même sélection/scénario ;
  accès réseau autorisé,16requêtes SEC, **33871673octets lus**, y compris le
  transfert interrompu au plafond8Mio de GSBD. Sept rapports complets, aucun
  nouvel appel après cette acquisition. Pas de contournement403/429, pas de
  reprise automatique d’un refus, TLS vérifié et contact SEC identifié.
- Reçus avec URL/date réelle/hash, protocole et caches d’entrée scellés,
  `extraction.json`, `documents.json`, `review-*.json`, `report.json`.
- Notes sémantiques versionnées :
  `doc/ml/sources/buyback_review_20261020.json`.
- Audit final séparé : `final-review-v1/report.json`,
  **PASS_BOUNDED_FEASIBILITY_NOT_EFFICACY** ; reproduction de la sélection,
  des16extractions, des43montants et des citations des sept rapports.
- **19 tests ciblés passent**. Pas toute la suite de l’application.
- Même assistant : pas une seconde revue humaine indépendante.

Scripts de recherche uniquement : `us_buyback_pilot.py` et
`us_buyback_review_audit.py`. Aucun entraînement, LLM, ordre, SQL écrit,
modification de modèle/configuration/batch ou processus laissé actif.

## Suite bornée utile

1. Étendre le mapping **sur les sources**, pas sur les rendements : capex,
   classes, actions de trésorerie, émissions salariales/non monétaires,
   acquisitions, splits et variations de dette. Garder les secteurs financiers
   séparés ; ne jamais sommer des tags d’émission qui se recouvrent.
2. Construire un panel annuel plus large, sélectionné avant les prix futurs,
   comprenant aussi les émetteurs qui ne rachètent pas ou dont les actions
   augmentent. Conserver les exclus et les motifs, sans biais de survivants
   présenté comme résolu.
3. Qualifier les témoins secteur/capitalisation contemporains ; sinon nommer
   explicitement un test descriptif avec métadonnées courantes non PIT.
4. Seulement ensuite, comparaison H20/H60 avec coûts fixés et dénominateurs
   complets ; TOP10 Oracle comme sous-groupe séparé. Pas d’ajustement de seuils
   ou de changement de TP/SL pour améliorer ce premier résultat.

Le pilote borné est **clos**, pas un suivi quotidien en attente. Il démontre
l’accès et plusieurs pièges de définition ; il ne justifie ni activation live,
ni abonnement supplémentaire, ni promesse de rendement.
