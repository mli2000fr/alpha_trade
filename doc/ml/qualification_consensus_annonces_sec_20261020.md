# Consensus revenus et annonces SEC — qualification publique du 20 octobre 2026

## Bilan

Deux travaux séparés ont été poursuivis, sans modifier les cohortes ni les
scripts scellés du 19 octobre. **Qualification documentaire, pas test de
rentabilité ni démonstration D1/D10.**

1. Les **62 variations de consensus encore réservées** ont chacune un dossier.
   Devise de présentation identifiée pour 58 : 56 USD, BILI CNY, STNE BRL.
   Quatre restent sans devise de présentation suffisamment prouvée dans les
   pièces récupérées : ATEYY, ASX, IFNNY, STLA.
   **Quatre nouvelles correspondances devise/trimestre de revenus** sont
   appuyées : TWLO, FIVN, ENTG, AKAM. Les 58 autres restent réservées.
2. Les anciens **93 cas SEC étaient déjà reconstitués** : les 24 accords
   initiaux étaient devenus sept après recalage, avec un biais de sélection
   future restant à corriger. Nous n'avons pas relancé leur backtest.
   Une **nouvelle population bornée au premier trimestre 2024** a été construite
   sans cette condition : 51 dépôts candidats, 24 présents dans le TOP10 au
   jour de réaction reconstruit, cinq à montants trimestriels documentés après
   lecture complémentaire. **Aucun accord admissible comptes/réaction** sur ce
   petit périmètre. Cela n'est ni un taux de réussite nul ni une preuve que la
   stratégie serait perdante : aucun parcours après entrée n'a été examiné.

Les deux groupes de 24 sont **différents** : anciens accords comptabilité/prix
sur la présélection des trois années, contre nouveaux dépôts candidats de Q1
2024 avant les filtres financiers.

## Périmètre, méthode et chronologie

La phase préparatoire a figé les deux périmètres avant leur acquisition :
les 62 réserves de la cohorte revenus seuls du 19 octobre, et toutes les
publications candidates du premier trimestre 2024 des titres présents dans le
TOP10 quotidien archivé. Les téléchargements ont été réalisés sur les
interfaces publiques officielles SEC, avec identification du client, TLS
vérifié, appels séquentiels espacés et arrêt sur refus d'accès. Aucune
interface privée, restriction d'accès ou protection n'a été contournée.

La SEC documente les [interfaces de soumissions et de faits financiers](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
et les [règles d'accès automatisé](https://www.sec.gov/about/developer-resources).
Les sources sont publiques, mais leurs limites techniques et documentaires
restent explicites ; accès public ne signifie pas couverture exhaustive.

Les documents étaient publiés avant les décisions historiques concernées ;
leur **récupération Alpha Trade a lieu maintenant**, le 20 octobre. Aucun reçu
local de 2024 ou antérieur au 19 octobre 2026 n'est inventé. Les qualifications
ajoutées ne sont pas présentées comme déjà opérationnelles à ces anciennes
dates. La même assistance technique a effectué les lectures : **pas de revue
humaine indépendante**.

## 1. Consensus revenus seuls : ce qui est réellement qualifié

### Devise

Pour 56 émetteurs, la preuve est l'unité monétaire des faits de revenus
consolidés dans les documents inline XBRL originaux. Les contextes segmentés
ne servent pas à déterminer une devise consolidée. Un dollar de cotation
américaine ou le simple signe `$` ne suffisent pas.

Pour BILI, le rapport déclare une présentation en renminbi ; pour STNE, en
reais. Les traductions de confort en USD ne changent pas cette présentation.
Cela **ne certifie pas la devise d'un enregistrement Trends particulier** :
pour ces deux émetteurs non USD, la dénomination fournisseur reste réservée.
Les pièces partielles ou absentes des quatre autres émetteurs ne sont pas
remplacées par une devise supposée.

Le support EODHD précise des valeurs monétaires en unités complètes, mais
aucun champ devise par ligne Trends. On distingue donc systématiquement
**devise des comptes de l'émetteur** et **certification de la ligne du
fournisseur**, cette dernière n'étant pas acquise par la seule lecture SEC.

### Trimestre de revenus

| Titre | Rang Oracle | Fin réelle appuyée | Ancrage Trends | Motif technique de variation |
|---|---:|---|---|---|
| TWLO | 39 | 30/09/2026 | 30/09/2026 | LONG |
| FIVN | 48 | 30/09/2026 | 30/09/2026 | SHORT |
| ENTG | 93 | 26/09/2026 | 30/09/2026 | LONG |
| AKAM | 157 | 30/09/2026 | 30/09/2026 | SHORT |

- **TWLO** : prévision de revenus directement rattachée au trimestre finissant
  le 30 septembre, accession `0001447669-26-000088`.
- **FIVN** : prévision de revenus du troisième trimestre, rapprochée du tableau
  de guidance daté du 30 septembre dans le même communiqué,
  `0001288847-26-000121`. La fenêtre de conversion de dette du 10-Q est rejetée.
- **ENTG** : ventes attendues du trimestre finissant le 26 septembre,
  `0001101302-26-000146`. L'ancrage au 30 septembre suit la normalisation
  mensuelle décrite par le fournisseur ; le jour réel reste conservé.
- **AKAM** : tableau de guidance distinguant revenus trimestriels et annuels,
  `0001086222-26-000083`. Les mentions de conversion de dette sont rejetées.

Ces quatre appuis s'ajoutent aux contextes DOCN/FUN déjà documentés, soit
**six contextes appuyés sur les 64 variations**, sans écraser l'ancienne cohorte.
Ce ne sont pas six trades, probabilités ou preuves de rentabilité.

Les mentions de période CCOI, BRBR et ROAD concernent notamment dette,
paiements ou financement. Pour SDGR, une prévision trimestrielle d'**ACV**
n'est pas une prévision trimestrielle de revenus. Pour HP, les résultats
opérationnels préliminaires d'une période achevée ne sont pas transformés en
prévision de revenus d'un trimestre encore à annoncer. Les autres calendriers
fiscaux et champs DEI constituent des indices de cohérence, pas une preuve
explicite suffisante du trimestre de revenus ciblé.

La variation relative reste celle des vrais snapshots `0q`, à nombre
d'analystes inchangé. Les quatre nouveaux motifs sont 2 hausses et 2 baisses.
Leurs ordres de grandeur sont très petits : TWLO environ **+0,000041 %**,
FIVN **−0,000364 %**, ENTG **+0,0731 %**, AKAM **−0,000089 %**. Une variation
numérique aussi faible peut être peu informative ; la qualification des
sources ne démontre pas sa valeur directionnelle. Aucun seuil n'a été choisi
après observation d'un résultat futur pour les rendre plus favorables.

Le nombre inchangé d'analystes ne prouve toujours pas l'identité des mêmes
contributeurs. EPS exclu, pas de reconstruction J−7/J−30 à partir de `+1q`.
La maturation TP10/SL5 sur dix séances de la cohorte du 19 octobre reste le
**30 octobre après clôture NYSE**, sous réserve de prix qualifiés.

## 2. Annonces : nouvelle cohorte sans sélection par un futur dépôt

### Admission et décisions

- Fenêtre de réaction : **1er janvier–31 mars 2024**, 61 séances,
  **610 couples titre/date**, 32 titres distincts.
- TOP10 H20 historique de recherche déjà figé : CatBoost annuel walk-forward
  de `us_h10_h20_frozen_comparison/20261019-v1`, **pas** les identifiants
  annuels de production ni un nouvel entraînement.
- Acquisition des 8-K item 2.02 et des 6-K du périmètre. Les 6-K constituent
  une population large : chacun n'est pas nécessairement une annonce de
  résultats. Les dépôts de fin décembre sont conservés pour les premières
  réactions de janvier et les répétitions.
- Première séance complète dont l'ouverture suit strictement l'acceptation
  SEC horodatée ; décision après sa clôture, entrée éventuelle à l'ouverture
  de la séance suivante. Fuseau manquant : réserve, jamais heure inventée.
- Admission par appartenance au **TOP10 de cette séance de réaction**, avant
  examen des comptes. Aucune condition d'appartenance au TOP10 d'un futur 10-Q.
  Le regroupement des 32 titres sert uniquement à limiter l'acquisition.

Les correspondances historiques de titres ne sont pas certifiées par le
référentiel actuel. EXPI, KALV et SATS n'ont pas d'identité CIK suffisamment
résolue dans les métadonnées utilisées ; ils ne sont pas assimilés à une
absence d'événement. La population n'est donc **pas exhaustive de tout le
TOP10**. La première accession dont la période est parsée n'est pas une preuve
de première annonce mondiale : un communiqué IR antérieur peut manquer.

### Montants et réaction

Quatre montants doivent provenir d'un tableau trimestriel cohérent du
communiqué : revenu courant/précédent et résultat opérationnel
courant/précédent. Pas de montant annuel assimilé au trimestre, pas de
substitution par des chiffres publiés plus tard. Comparaison au même trimestre
de l'année précédente, pas surprise par rapport au consensus.

La lecture complémentaire récupère **HLF** (libellé `Worldwide Net sales`) et
**TAL** (colonnes 2022 puis 2023, inverses de l'ordre courant/précédent attendu).
Les échelles millions/milliers et les signes négatifs sont vérifiés.
Les autres tableaux ambigus ne sont pas forcés pour augmenter le nombre.

| Cas à quatre montants | Motif comptes | Réaction relative à SPY | Conclusion |
|---|---|---:|---|
| ASAN, 12 mars | LONG | −13,80 points de % | Désaccord |
| BILL, 9 février | LONG | −14,16 points de % | Désaccord |
| HLF, 15 février | Mixte / abstention | −32,35 points de % | Condition comptable non satisfaite |
| TAL, proxy SEC 29 janvier | LONG | Non utilisée | Communiqué daté du 25 janvier, avant acceptation SEC du 26 |
| W, 23 février | LONG | −2,81 points de % | Désaccord |

La réaction est le rendement ajusté clôture précédente → clôture de réaction,
**moins celui de SPY**, pas la performance d'un trade. Les 16 lignes de prix
archivées sont exclusivement les couples J/J−1 nécessaires à quatre cas,
avec contrôles OHLC, volume, remplissage, identité, source et ajustement.
TAL n'est pas recalé arbitrairement à partir d'une date sans heure vérifiée.

Sur les 24 dépôts admis : **19 restent sans quatre montants trimestriels**,
10 sans période trimestrielle explicite suffisamment résolue, un répète une
période déjà parsée, deux ont une population documentaire incomplète, un a une
annonce connue antérieure à l'acceptation SEC. Ces motifs **se chevauchent**.
Zéro accord provisoire admissible et zéro cas pleinement qualifié ; aucune
courbe, taux de gains ou performance H10/H20 n'a été calculé.

## Archives, limites et vérifications

Racine : `artifacts/research/us_public_information_followup/`.

- `20261020-v1/` : protocole commun, 92 dossiers d'identité au total, plan de
  171 accessions uniques, acquisition originale SGML et premières extractions.
  **INCOMPLETE / BOUNDED_ACQUISITION_LIMIT**, 149 accessions traitées, 121 corps
  complets récupérés. Certains documents dépassent 20 Mio ; un 503 est conservé.
  Environ 500 Mio de corps complets archivés. Ce n'est **pas** un plafond
  démontré de trafic réseau total : les octets des transferts interrompus ne
  sont pas tous comptabilisés par cet ancien lecteur.
- `compact-20261020-v1/` : pièces HTML ciblées pour les 50 accessions sans
  corps complet. 155 requêtes, **74 753 705 octets réellement lus**, y compris
  transferts interrompus. Plan traité, mais certaines pièces restent absentes
  ou trop grosses : `COMPLETE` ne signifie pas couverture documentaire complète.
  Les enveloppes SGML dérivées servent seulement au parsing ; les originaux
  HTML, URL, horodatages et empreintes restent disponibles séparément.
- `review-20261020-v1/` : 62 dossiers sémantiques, 51 dossiers de dépôts,
  première extraction automatique et cohorte Q1. Les trois tableaux reconnus
  automatiquement deviennent cinq après revue séparée, sans écraser ce dossier.
- `final-20261020-v1/` : `consensus-context-review.csv` et `.parquet` (62 lignes),
  `context-proofs.json`, `manual-table-proofs.json`, `q1-reviewed-events.parquet`,
  `reaction-price-inputs.parquet`, `protocol.json`, `report.json`, `audit.json`.
- Notes de revue versionnées :
  `doc/ml/sources/qualification_publique_20261020.json`.

**244 reçus de documents réussis vérifiés par empreinte** dans le bilan final.
Les sources des anciens dossiers ont changé de fins de ligne lors du commit
Git Windows : la préparation journalise uniquement les équivalences exactes
CRLF→LF, avec anciennes/nouvelles empreintes. Aucune différence de contenu
n'est acceptée et aucun ancien sceau n'est réécrit.

**164 tests ciblés passent**, dont 26 nouveaux sur les quatre modules de
collecte/revue ; pas l'intégralité de la suite applicative. L'audit séparé
revalide les 62 devises/contextes, citations, dates, les 24 appartenances
TOP10, montants et paires de prix nécessaires ; résultat **PASS**. Le premier
lancement pytest a buté sur le répertoire temporaire par défaut ; relance
isolée sous `artifacts/tmp/`, sans couverture globale : tests réussis.

Les scripts sont exclusivement sous `scripts/research/us_public_information_*`.
Les anciens dossiers restent immuables. Pas d'API LLM ou payante, SQL écrit,
entraînement, changement de modèle/configuration/batch, ordre ou processus de
collecte restant actif.

## Suite utile, sans transformer les réserves en signaux

**Suite déjà préparée le 20 octobre** :
[évaluateur consensus TP10/SL5 sur dix séances](evaluateur_consensus_revenus_h10_20261020.md).
349 membres figés, six contextes séparés, aucun prix lu avant maturité ;
pas de backtest économique ni de modèle supplémentaire.

1. Conserver de nouvelles observations prospectives de revenus et les
   classements contemporains ; évaluer la cohorte après maturité, en séparant
   les contextes documentés plus tard des données opérationnelles de l'époque.
2. Pour les 58 réserves, chercher des pièces plus ciblées de calendrier
   fiscal/revenus ; pour les émetteurs non USD, demander la dénomination exacte
   du champ fournisseur. Ni devise de cotation ni calendrier standard supposé.
3. Pour les annonces, améliorer les tableaux et retrouver l'annonce IR initiale
   horodatée, notamment TAL ; résoudre les trois identités et les pièces
   manquantes. Pas de PnL sur une poignée de cas choisis rétrospectivement.
4. Une extension annuelle ou au TOP20 % serait une **autre cohorte explicite**,
   pas un remplacement silencieux du strict TOP10 demandé. Le bilan Q1 ne
   justifie ni entraînement ni promotion en production.

Aucune nécessité d'achat de données n'est démontrée à ce stade : les réserves
restantes sont identifiées, pas déclarées gratuitement impossibles à résoudre.
