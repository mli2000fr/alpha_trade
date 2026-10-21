# Acquisitions en cash — audit de faisabilité, 20 octobre 2026

> **Suite exécutée le 20 octobre :** les treize dépôts initiaux sont désormais
> traités, cinq opérations et leur clôture juridique documentées, 94 séances
> pré-clôture qualifiées. Voir le [bilan courant de cohorte et chronologie](arbitrage_acquisitions_cash_cohorte_20261020.md).
> Le présent document conserve le premier audit de huit dossiers, pas l'état
> final de la continuation. Un [pilote économique séparé a ensuite été calculé](arbitrage_acquisitions_cash_pilote_economique_20261020.md)
> : +31,49 USD de trading net simulé, sans promotion de stratégie.

## Bilan borné

**Audit de faisabilité terminé ; piste techniquement accessible, aucun résultat
de rentabilité et pas encore de GO backtest.** Les documents publics permettent
de reconstituer des modalités initiales. Deux cibles à prix fixe en cash sont
identifiées ; leurs historiques sont absents de notre base mais cinq séances
initiales sont disponibles chez Alpaca SIP. Aucun prix n'a été analysé, aucun
rendement ou gain calculé.

| Étape | Résultat |
|---|---:|
| Lignes de l'index SEC trimestriel parcourues | 370 321 |
| Lignes initiales `SC TO-T`, co-déposants compris | 26 |
| Dépôts initiaux distincts après déduplication accession | 13 |
| Échantillon figé : huit premiers dépôts par date/accession | 8 |
| Dépôts et pièces annexes obtenus intégralement | 8 |
| Offres exclues du pilote simple, sans sélection par issue | 6 |
| Candidats de modalités « toutes actions, cash fixe » | 2 |
| Cas avec parcours complet, issue et paiement qualifiés | **0** |

Ces deux candidats **ne sont pas deux opérations gagnantes**. Leurs issues
n'ont pas été recherchées dans cet audit. La population des opérations
abandonnées n'est donc pas encore qualifiée. Les cinq autres dépôts initiaux
du trimestre n'ont pas été substitués aux six dossiers exclus.

## Question et méthode

L'[arbitrage de fusion décrit par AQR](https://www.aqr.com/Insights/Research/Journal-Article/Characteristics-of-Risk-and-Return-in-Risk-Arbitrage)
cherche notamment à capter un écart entre prix de marché et montant d'une
acquisition annoncée. Ce n'est pas un rendement garanti : une rupture ou un
retard peut provoquer une perte et immobiliser le capital. Le pilote potentiel
reste distinct du TOP10 Oracle, du sentiment et des signaux techniques.

Avant de télécharger les pièces ou examiner une issue, protocole figé :

1. Lire l'index officiel complet **2024Q1**.
2. Retenir seulement les dépôts **initiaux `SC TO-T`**, pas les amendements
   `SC TO-T/A` ni les rachats par l'émetteur `SC TO-I`.
3. Dédupliquer par accession : un même dépôt peut être indexé au titre de
   plusieurs parties. Trier par date de dépôt puis accession ; prendre les
   **huit premiers**, sans filtre d'univers courant, prix ou issue future.
4. Lire ces huit pièces initiales ; distinguer cible/acquéreur, offre partielle,
   société non cotée, contrepartie variable/CVR, offre cash fixe de contrôle.
5. Pour les seuls candidats aux modalités simples, vérifier la présence des
   **dates**, pas le niveau ou l'évolution des prix, sur cinq séances initiales.

**Ce n'est pas un recensement de toutes les acquisitions en cash.** Les fusions
passant par un vote des actionnaires et d'autres formulaires peuvent ne jamais
déposer de `SC TO-T`. Le trimestre contient aussi 70 lignes `DEFM14A`, non
analysées ici ; ce n'est pas 70 acquisitions cash supplémentaires présumées.
L'échantillonnage chronologique évite de choisir les gagnants mais ne rend pas
ces huit dossiers représentatifs de toutes les acquisitions.

## Revue des huit dossiers

| Cible réelle | Décision de périmètre | Motif vérifié dans les pièces initiales |
|---|---|---|
| CNL Healthcare Properties | Exclue | REIT sans marché public établi ; offre partielle, sans prise de contrôle |
| Moody National REIT II | Exclue | REIT sans marché public établi ; offre partielle, sans prise de contrôle |
| NorthStar Healthcare Income | Exclue | REIT sans marché public établi ; offre partielle, sans prise de contrôle |
| Sinovac, SVA | Exclue | Offre partielle d'investissement passif, pas acquisition de contrôle |
| Theseus Pharmaceuticals, THRX | Exclue du pilote simple | Cash variable de 3,90 à 4,05 USD et droit contingent CVR ; ne pas valoriser ce droit à zéro par facilité |
| Manchester United, MANU | Exclue du pilote simple | Offre partielle sur les actions de classe A ; plafond et proratisation, pas 33 USD garantis pour toutes les actions achetées |
| **RayzeBio, RYZB** | **Modalités candidates** | Toutes les actions à **62,50 USD en cash** ; acquéreur Bristol-Myers Squibb via Rudolph Merger Sub |
| **Science 37, SNCE** | **Modalités candidates** | Toutes les actions à **5,75 USD en cash** ; acquéreur eMed via Marlin Merger Sub |

Les exclusions portent sur des propriétés connues dans le dépôt initial,
**pas sur le succès futur** ni sur la disponibilité de cours favorables.
Les sommes des offres exclues ne sont pas des rendements simulables.

### RayzeBio

- Cible : **CIK 0001825367**, action ordinaire, symbole historique **RYZB**
  explicitement donné dans l'offre. Contrepartie initiale **62,50 USD**.
- [Dépôt initial du 25 janvier 2024](https://www.sec.gov/Archives/edgar/data/14272/0001140361-24-003759.txt),
  accession `0001140361-24-003759`, pièce d'offre `ny20019237x1_ex-a1i.htm`.
- Le dépôt est aussi indexé sous **Bristol-Myers Squibb**, CIK 14272. C'est
  l'acquéreur : utiliser naïvement le nom/CIK de la ligne d'index conduirait
  à étudier **BMY au lieu de RYZB**. L'identité cible est prise dans l'en-tête
  `SUBJECT COMPANY` et la pièce d'offre, pas dans le ticker courant.
- Conditions initiales notamment : majorité apportée, exigences HSR/accords
  publics et autres conditions ; absence de condition de financement.
- Expiration initialement affichée à la minute suivant 23 h 59, heure Est,
  le 22 février 2024, sauf extension ou résiliation. **Ce n'est ni une date
  de clôture observée, ni une date de crédit de cash qualifiée.**

### Science 37

- Cible : **CIK 0001819113**, action ordinaire, symbole historique **SNCE**
  explicitement donné dans l'offre. Contrepartie initiale **5,75 USD**.
- [Dépôt initial du 12 février 2024](https://www.sec.gov/Archives/edgar/data/1819113/0001104659-24-013752.txt),
  accession `0001104659-24-013752`, offre `tm244930d1_ex99-a1a.htm`.
- Conditions notamment : majorité des droits de vote apportée et autres
  conditions usuelles ; absence de condition de financement.
- Expiration initialement affichée à minuit, fin du 11 mars 2024 à New York,
  sauf extension ou résiliation. Là encore, **pas une sortie backtest ni un
  paiement effectif présumé**.

La qualification ici est celle des **modalités initiales et identités citées**,
pas celle de leur stabilité jusqu'au dénouement ou de leur rendement net.

## Horodatages : ne pas inventer une disponibilité de trading

Les sources ont été récupérées le **20 octobre 2026**, pas en janvier/février
2024. L'acceptation du dépôt SEC n'est pas un reçu historique Alpha Trade,
et l'annonce de l'acquisition peut précéder ce dépôt.

L'extraction conserve l'acceptation SEC, interprétée en heure de New York,
et l'ouverture suivante comme **proxy non qualifié**. La sonde de couverture
utilise une borne plus prudente : première ouverture après le maximum entre
l'acceptation et **la fin du jour de dépôt de l'index**. Cela n'est pas une
certification de première publication mondiale ni un choix d'entrée optimisé.

- RYZB : cinq séances attendues **26/01, 29/01, 30/01, 31/01 et 01/02/2024**.
- SNCE : **13/02, 14/02, 15/02, 16/02 et 20/02/2024**.

Ces dates ne sont pas encore des trades : il faudrait d'abord qualifier la
diffusion publique et le contrat d'exécution du pilote.

## Couverture : ce que nous avons réellement vérifié

| Cible | Base `alpha_trade.stock_bars_daily`, 2023–2024 | Alpaca SIP, cinq séances demandées | Conclusion |
|---|---:|---:|---|
| RYZB | **0 ligne** | **5/5**, HTTP 200 | Accès historique possible malgré l'absence locale |
| SNCE | **0 ligne** | **5/5**, HTTP 200 | Même constat |

Le SQL était strictement en lecture seule, avec sélection des symboles,
dates, provenance et marqueur de remplissage — **pas des prix**. Les deux
réponses fournisseur brutes sont archivées, mais seuls horodatages et nombres
de barres ont été examinés. Aucun niveau de prix, spread d'acquisition,
rendement, win-rate, gain/perte ou PnL n'a été calculé.

Paramètres : `feed=sip`, `adjustment=raw`, `asof=-`, fenêtres fixes de cinq
séances, compte principal, aucune requête d'ordre, aucun repli IEX.
Ces dix barres ne certifient **ni l'ensemble du parcours jusqu'à la fin de
l'opération, ni la qualité OHLCV, ni l'identité économique de toutes les
versions historiques**. Les versions courantes des fournisseurs ne sont pas
des archives PIT d'époque.

## Accès aux sources et archivage

La [SEC décrit l'accès public gratuit, les index et les règles de fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
Nous avons fait **neuf requêtes SEC** : un index compressé et huit dépôts
complets. Agent identifié, TLS vérifié, au plus deux requêtes par seconde,
aucun retry ni contournement de refus/challenge. Pas d'accès Yahoo ni source
commerciale nouvelle. Deux requêtes historiques Alpaca, aucun achat ou
changement d'abonnement.

Les limites de taille et de durée étaient fixées avant acquisition. Aucune
troncature silencieuse : les huit soumissions complètes contiennent leur
marqueur de fin. Les clauses de la revue sont vérifiées dans les pièces
nommées et reliées par SHA256. Les co-déposants sont dédupliqués avant la
sélection. La revue a été faite par **le même assistant**, pas par un lecteur
humain indépendant.

Artefacts : `F:/projets/artifacts/research/us_cash_merger_feasibility/20261020-v1`.

| Fichier ou dossier | Usage |
|---|---|
| `protocol.json` | Périmètre et limites figés avant téléchargement |
| `index.json` | Compteurs du trimestre, huit accessions sélectionnées |
| `http` | Neuf reçus SEC, index et dépôts intégraux, hashes et UTC réels |
| `review` | En-têtes et textes des pièces initiales des huit dossiers |
| `coverage-v1/protocol.json` | Revue tracée et protocole de sonde dates seules |
| `coverage-v1/local.json` | Lecture seule des dates locales : aucune pour ces deux tickers |
| `coverage-v1/*-alpaca.json` | Deux réponses historiques brutes, sans évaluation des prix |
| `coverage-v1/report.json` | Revue, exclusions et couverture ; statut NOT_READY_FOR_BACKTEST |
| `audit-v1/report.json` | Contrôle technique final ; pas validation de stratégie |

Revue structurée :
[cash_merger_review_20261020.json](F:/projets/doc/ml/sources/cash_merger_review_20261020.json).
Modules séparés : `scripts.research.us_cash_merger_feasibility`,
`scripts.research.us_cash_merger_review`, `scripts.research.us_cash_merger_audit`.
Ils refusent l'écrasement des dossiers scellés.

## Ce qui manque avant un backtest — borné et concret

1. **Population** : traiter les cinq autres dépôts initiaux du trimestre dans
   une phase figée séparée, toujours sans choisir par issue, ou assumer
   explicitement que le pilote ne porte que sur les huit premiers. Ne pas
   présenter ce sous-ensemble comme toutes les acquisitions US.
2. **Chronologie de chaque opération admissible** : première annonce vérifiable,
   modifications de prix, prorogations, résiliation ou succès, date d'effet,
   traitement de l'action et paiement effectif. Chercher également les preuves
   d'échec, sans supposer une réussite lorsqu'un ticker disparaît. Si un
   recensement complet ne contient aucun échec, l'indiquer ; ne pas en ajouter
   artificiellement pour équilibrer les résultats.
3. **Prix et identité** : historique brut jusqu'à l'issue pertinente et jusqu'à
   une liquidation possible en cas d'échec ; splits et changement de ticker,
   titres radiés, absence de cours après radiation traitée comme événement,
   pas comme prix zéro ou forward-fill.
4. **Exécution et économie** : entrée non rétrospective, frais, cash immobilisé,
   intérêts comparables à une référence cash, date où le produit redevient
   dépensable ; ne pas vendre fictivement au prix proposé à l'expiration prévue.

**Cette étape a depuis été exécutée :** cohorte initiale SC TO-T complète,
cinq dénouements et prix pré-clôture documentés ; les dates de paiement
fournisseur restent distinguées d'un crédit courtier réel. Voir le
[bilan courant](arbitrage_acquisitions_cash_cohorte_20261020.md) pour les
résultats et la prochaine simulation exploratoire proposée, non lancée.

## Statut opérationnel

Neuf tests ciblés et audit technique du dossier. Aucune écriture SQL, ordre,
entraînement, appel LLM, modification de modèle, configuration/batch ou page
de production. Seuls des scripts, tests, documents et artefacts de recherche
séparés sont ajoutés. Aucun téléchargement ou job laissé actif après le bilan.
