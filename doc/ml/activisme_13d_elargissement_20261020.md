# Activisme 13D — élargissement à toute l’année 2024

**Mise à jour du 20 octobre :** la confirmation 2025–2026 a ensuite été menée.
Elle ne confirme pas d’avantage stable ; les résultats 2024 ci-dessous restent
inchangés. Voir le [bilan 2025–2026](activisme_13d_confirmation_2025_2026_20261020.md).

## Bilan

**Extension effectuée, calculée et auditée. Sept sociétés principales au lieu
de trois ; résultats exploratoires, pas de signal directionnel validé.**

Le nouveau périmètre porte sur les quatre trimestres 2024, pas seulement Q1.
Les quatre sociétés supplémentaires sont **MTCH, ATEX, LUV et BTU**. TPL reste
un cas de gouvernance secondaire, jamais ajouté au groupe principal pour en
améliorer le résultat. Le second BJRI reste bloqué par la règle des 60 séances.

| Périmètre principal | Sociétés | Net moyen à 20 séances | SPY mêmes dates, net | Net moyen à 60 séances | SPY mêmes dates, net |
|---|---:|---:|---:|---:|---:|
| Premier pilote Q1, déjà connu | 3 | +7,73 % | +3,75 % | +9,83 % | +5,99 % |
| **Quatre nouvelles sociétés** | **4** | **+1,49 %** | **+0,60 %** | **+8,32 %** | **+6,43 %** |
| Ensemble 2024 | 7 | +4,16 % | +1,95 % | +8,97 % | +6,24 % |

À 20 séances, **une seule des quatre nouvelles occasions est positive**, et
la médiane est **−2,90 %**. À 60 séances, trois sont positives et une négative.
Les sept cas réunis donnent 4 positifs/3 négatifs à 20 séances et 6/1 à 60.
Ces fractions ne constituent pas une estimation fiable du taux de réussite.

Ce sont des rendements par occasion sur un notionnel indépendant de 1 000 USD,
**pas** des rendements annuels, une somme de gains sur un compte partagé ou un
backtest avec parité live. Le rendement relatif à SPY est une comparaison
appariée, pas une preuve d’effet causal de l’activisme ni une couverture bêta.

## Sociétés et résultats, coûts inclus

Entrée à l’ouverture de la première séance NYSE complète strictement après
la date de dépôt SEC ; acceptation SEC également vérifiée avant cette ouverture.

| Société | Entrée | Net 20 séances | Net 60 séances | Rang Oracle avant entrée |
|---|---|---:|---:|---:|
| Gildan, GIL | 2024-01-09 | +6,77 % | +14,48 % | 805 / 1 790 |
| BJ’s Restaurants, BJRI | 2024-01-19 | +10,47 % | +2,16 % | 226 / 1 790 |
| Criteo, CRTO | 2024-02-28 | +5,96 % | +12,84 % | 435 / 1 790 |
| **Match Group, MTCH** | **2024-07-16** | **−1,71 %** | **+9,82 %** | 596 / 1 790 |
| **Anterix, ATEX** | **2024-07-30** | **−10,67 %** | **−22,26 %** | 508 / 1 790 |
| **Southwest Airlines, LUV** | **2024-08-06** | **+22,42 %** | **+28,43 %** | 478 / 1 790 |
| **Peabody Energy, BTU** | **2024-08-21** | **−4,08 %** | **+17,31 %** | 405 / 1 790 |

Le recul maximal de clôture le plus important parmi les cas principaux atteint
**22,95 %**, pour ATEX sur 60 séances. Pas de SL dans ce protocole ; ne pas
confondre ce recul avec une perte bornée par les protections du système live.

LUV contribue fortement à la moyenne. **Sensibilité descriptive, pas nouvelle
règle de sélection** : sans LUV, les trois autres nouvelles occasions donnent
en moyenne **−5,49 % à 20 séances**, puis **+1,62 % à 60 séances** contre SPY
environ **+4,69 %** à 60 séances. Le premier résultat « tous gagnants » ne se
généralise donc pas à l’extension. Nous ne retenons ni n’écartons un titre selon
ce résultat et ne choisissons pas ensuite le meilleur horizon.

Stress de coûts à 25 bps par jambe : ensemble 2024 **+3,86 % / +8,65 %**,
extension seule **+1,19 % / +8,01 %**, aux horizons 20/60. Les frais ne sont pas
la seule incertitude : il reste une sélection documentaire rare, un effet de
marché possible et un biais de survivants.

## Comment le périmètre a été élargi

1. Capturer/vérifier les index SEC complets 2024Q1…Q4 : respectivement
   **313, 266, 241 et 280 accessions initiales distinctes**, soit **1 100**.
   Une accession représente un dépôt, pas une société indépendante. Les
   codéclarants sont regroupés avant toute sélection.
2. Garder toutes les accessions avec au moins un CIK indexé dans le mapping
   de l’univers tradable **actuel** de 1 790 titres : **100 dossiers**,
   contre 23 sur le seul premier trimestre. Ce n’est pas un univers PIT 2024.
3. Ajouter **40 dossiers hors de cette route d’indexation** : dix par trimestre,
   sélectionnés par les plus petites empreintes SHA256 de l’accession, sans
   lire les prix, les résultats ou la réputation future de l’investisseur.
4. Lire les originaux et identifier **SUBJECT COMPANY**. Ne jamais attribuer
   un signal au ticker du déclarant/investisseur quand il vise une autre société.
5. Figer les décisions, les citations exactes et l’ordre d’admission avant
   tout rendement de l’extension. Le premier pilote Q1 était déjà connu :
   il n’est pas présenté comme une nouvelle confirmation hors échantillon.
6. Vérifier les tickers/classes historiques, puis seulement calculer les parcours.

Les **140 originaux** sont finalement disponibles. LUV dépassait la première
borne technique de 12 Mio ; une lecture complémentaire séparée, plafonnée à
40 Mio et décidée avant la revue/prix, a récupéré ses 32 471 881 octets.
L’ancien reçu de dépassement est conservé ; aucun refus d’accès n’a été contourné.

Parmi les 100 dossiers repérés via le mapping courant, **39 visent une autre
société hors univers**. Ils restent archivés mais hors cohorte principale ;
ils ne sont pas assimilés à des campagnes sur les tickers des déclarants.
Les 61 autres et les 40 dossiers du sondage donnent **101 dossiers cibles**.
Huit dépôts répondent au critère principal ; le blocage du second BJRI laisse
**sept émetteurs/entrées**. Un dépôt TPL reste secondaire. Deux dossiers sont
réservés ; les autres sont documentés comme participations ordinaires,
acquisitions, financements, transferts ou intentions génériques.

### Limite sur les radiés et sociétés absentes

Le sondage hors univers contient notamment des dossiers Clever Leaves, ARC
Document Solutions, Vertex Energy, Universal Stainless, Arena ou Capitalworks.
Il ne sélectionne pas leurs succès/échecs futurs : certaines acquisitions ou
financements sont déjà annoncés dans les originaux. Aucun ne fournit ici une
nouvelle entrée principale qualifiée ; Neuraxis demeure ambigu.

**Quarante dossiers hors route courante ne constituent ni un recensement des
radiés ni une correction complète du biais de survivants.** On ne peut pas
affirmer avoir mesuré les pertes d’activismes radiés ou la performance de tout
le marché. Les 39 cibles d’autres déclarants ne sont pas ajoutées opportunément
au sondage après lecture. L’absence de rendement hors univers n’est pas comptée
comme zéro ou une perte. Aucun prix manquant n’est remplacé par une société gagnante.

## Même définition d’intervention, pas « tous les 13D »

Le critère principal reste : nomination actuelle identifiable ou demande
concrète déjà formulée sur la stratégie, les opérations ou le capital. Une
formule « may discuss », « reserves the right » ou une valorisation jugée faible
ne suffit pas. Les droits au conseil issus d’une acquisition ou d’un financement
ne sont pas automatiquement une campagne indépendante.

- **MTCH / Starboard** : lettre jointe du 15 juillet, objectif de marge,
  rachats renforcés et comparaison avec une cession. Preuve dans l’annexe,
  pas simple présence du nom d’un gérant connu.
- **ATEX / Heard** : candidat au conseil déjà nommé dans le proxy de l’émetteur,
  passage de 13G à 13D. Nomination consensuelle, **pas nécessairement campagne
  hostile** ; conservée selon le critère fixé, nature différente explicitée.
- **LUV / Elliott** : demandes précises de renouvellement du conseil/CEO,
  lettres du 10 juin et du 8 juillet antérieures au dépôt du 5 août.
- **BTU** : suggestions déjà faites sur les rachats, Powder River Basin et
  la monétisation d’une participation dans Centurion, pas seulement une option future.

Les dossiers VAC, SNN, HLIT, NCNO et HR ne sont pas promus sur la seule base
d’un dialogue général avec la direction. Les montages FUN, CRC, SBS, INVX,
PRMB, VCTR, REZI, NTNX et PENG sont distingués des campagnes indépendantes.
Le 13D INVA est étiqueté ainsi dans l’index/type SGML mais son document réel
est un **13G** : aucune section d’activisme n’est inventée.

### Deux réserves conservées

- **SMP**, accession `0000807249-24-000095` : original complet, mais section
  de finalité non récupérée de façon fiable ; statut documentaire réservé,
  pas un classement automatique « absence d’événement ».
- **Neuraxis**, `0001622627-24-000064` : nomination de Gil Aharon avec
  détention de preferred convertibles et bloqueurs. Le document ne permet pas
  de séparer nettement une intervention indépendante de droits de financement.
  Ni entrée principale forcée ni hypothèse de rendement nul.

La performance des **dossiers effectivement qualifiés** est calculée ; la
complétude de toutes les campagnes de 2024 n’est pas certifiée.

## Temps, identité, prix et contrat économique

- Acceptation SEC interprétée en heure New York, convertie en UTC ; entrée à
  la première ouverture complète suivant la **date du dépôt**, jamais à la
  date d’achat de l’investisseur ou à une lettre antérieure.
- Lettres GIL, CRTO, ATEX et LUV antérieures au dépôt explicitement conservées.
  **Pas de revendication d’alpha de première annonce mondiale.** Les sources
  ont été téléchargées en 2026, sans réception locale historique inventée.
- Annuels originaux strictement antérieurs : MTCH déposé le 23 février 2024,
  ATEX le 26 juin, LUV le 6 février et BTU le 23 février. Couvertures CIK/ticker
  confirmées. Même contrôle BJRI/CRTO ; GIL et TPL étayés par les originaux 13D.
- Blocage commun par **CIK émetteur** pendant 60 séances : un changement de
  symbole ou une classe supplémentaire ne contourne pas la règle. Un premier
  résultat futur inconnu bloquerait quand même une deuxième entrée.
- LONG seulement ; 1 000 USD de notionnel par occasion, fractions de marques
  ajustées. Sortie à la clôture des 20e/60e séances, entrée comprise. Aucun
  TP, SL, trailing, levier ou réinvestissement de capital commun.
- Commission de 1 USD par ordre, spread 5 bps et slippage 5 bps par jambe,
  stress 25 bps total par jambe. Même traitement pour SPY.
- Uniquement les barres de recherche normalisées déjà archivées : facteur
  `adj_close/close` identique pour tous les OHLC d’une date, calendrier complet,
  barres non artificielles, prix/volume positifs, fournisseur/base/identité stables.
  Les réserves de prix antérieures restent appliquées. Aucun nouvel appel prix.
- Proxy de rendement ajusté fournisseur, **pas certification indépendante des
  dividendes, lifecycle broker ou prix réellement exécutables**.

Formule nette, r étant le rendement ajusté :

```text
net = r − 2 / 1000 − 0,001 × (2 + r)
```

Les 16 couples entrée/horizon, TPL inclus, ont des parcours utilisables après
admission et contrôle des identités. Ce zéro manquant parmi les admis ne résout
ni les deux réserves documentaires ni le biais de sélection du périmètre.

## Oracle et portée du résultat

Rangs PATH_H20 de recherche CatBoost déjà figés, à la clôture strictement
antérieure à l’entrée ; aucun rang futur/cible future pour choisir les dossiers.
**Zéro occasion TOP10**, un seul cas TOP20 % : BJRI. Les quatre nouvelles
sociétés sont toutes hors TOP20 % au moment de la décision.

Cette expérience est donc une piste événementielle autonome. **Elle ne démontre
toujours pas une méthode pour prédire LONG/SHORT sur le TOP10 Oracle.**

## Archives, reproductibilité et suite

Racine :
`artifacts/research/us_activist_13d/extension-2024-20261020-v1/`.

- `protocol.json`, `selection.json` : critères et sélection sans prix ; index
  2024 et également index 2025 pour évaluer la faisabilité de la suite.
- `documents.json`, `http/`, `extraction.json`, `review/` : originaux, en-têtes,
  URL, dates réelles et empreintes, tous les dossiers conservés.
- `oversize-v1/` : acquisition complémentaire LUV bornée, protocole et reçu propres.
- `review-sections.json` : 130 sections legacy standard, deux variantes legacy,
  six champs XML `transactionPurpose`, deux non résolues avant revue manuelle.
- `doc/ml/sources/activist_13d_extension_review_20261020.json` : décisions et
  citations exactes pour les 140 dossiers ; même assistant, pas revue humaine indépendante.
- `review-frozen-v1/` : décisions figées avant rendements, identités originales.
- `replay-extension-v1/` : protocole avant calcul, barres/rangs sources, entrées
  auditées, `event-results.csv`, `report.json`, `audit.json`.

**33 tests ciblés passent.** Audit :
`PASS_EXPLORATORY_2024_ONLY_WITH_DOCUMENTARY_RESERVES`.
Les 140 originaux sont reparsés, la sélection par index et hash reconstruite,
les admissions/horaires/citations/identités vérifiés, les 16 rendements et
comparaisons SPY recalculés, les résultats Q1 d’origine reproduits exactement.

**137 nouvelles requêtes SEC**, **121 483 504 octets lus**, toutes HTTP 200,
dont la lecture initiale interrompue au plafond de taille. Les archives déjà
acquises sont réutilisées séparément. TLS vérifié, contact SEC réel déclaré,
requêtes sérielles espacées de 0,6 seconde, aucun contournement ni appel LLM.
Aucune modification de modèle, univers, batch ou configuration ; aucune
écriture SQL, aucun entraînement ni ordre. Aucun calcul laissé en cours.

Les index complets **2025** sont disponibles : 269/273/278/295 accessions
initiales distinctes, dont **23/12/34/21**, soit **90 dossiers**, repérés par la
route du mapping actuel. **Ce ne sont pas 90 sociétés activistes qualifiées ;
leurs originaux, interventions et rendements n’ont pas été testés ici.**
À la clôture de cette extension, leur étude restait la prochaine confirmation
utile. Elle est désormais effectuée séparément, avec critères inchangés et
couverture hors survivants explicitement délimitée :
[confirmation 2025–2026](activisme_13d_confirmation_2025_2026_20261020.md).
Aucun avantage n’est promu sur les seuls sept cas de 2024.

Sources originales des quatre nouveaux cas :

- [MTCH, 15 juillet 2024](https://www.sec.gov/Archives/edgar/data/891103/0000902664-24-004719.txt).
- [ATEX, 29 juillet 2024](https://www.sec.gov/Archives/edgar/data/1304492/0001013762-24-002223.txt).
- [LUV, 5 août 2024](https://www.sec.gov/Archives/edgar/data/92380/0000902664-24-004970.txt).
- [BTU, 20 août 2024](https://www.sec.gov/Archives/edgar/data/1064728/0001193125-24-203869.txt).

Scripts : `scripts/research/us_activist_13d_extension.py`,
`us_activist_13d_extension_review.py`, `us_activist_13d_extension_audit.py`.
