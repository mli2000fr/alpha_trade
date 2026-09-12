# Données manquantes et priorités fournisseurs pour la recherche ML

## 1. Objet du document

Ce document recense les expériences ML qui sont bloquées, suspendues ou restées non concluantes principalement à cause d'un manque de données. Il sert de cahier des charges pour rechercher et comparer des fournisseurs.

Il distingue trois situations qui ne doivent pas être confondues :

1. **Hypothèse encore ouverte et réellement bloquée par les données** : l'achat ou la collecte d'une nouvelle donnée peut débloquer une expérience pertinente.
2. **Donnée disponible mais contrat PIT, profondeur historique ou couverture insuffisants** : la famille de signal n'est pas nécessairement rejetée, mais les résultats actuels ne sont pas fiables.
3. **Hypothèse déjà testée avec une couverture suffisante et rejetée** : racheter la même donnée sous un autre nom ne doit pas être prioritaire.

L'objectif principal reste la direction conditionnelle à l'Oracle Extreme : parmi les titres dont l'amplitude future semble extrême, distinguer les futurs D1 des futurs D10, ou savoir s'abstenir. Une donnée intéressante doit donc apporter une information directionnelle nouvelle, disponible avant la décision, et pas seulement reformuler le prix ou le volume déjà connus.

## 2. Synthèse des priorités

| Priorité | Groupe | Donnée | Statut actuel | Valeur attendue |
|---|---|---|---|---|
| P0 | Fondation scientifique | Référentiel titres PIT, radiations et corporate actions | Manque structurel | Supprimer le biais de survivants et fiabiliser tous les OOS |
| P0 | Exploitation | OHLCV quotidien frais et corporate actions | Collecte arrêtée/incomplète après 2026-06/07 | Continuer les validations prospectives, prédictions et le live |
| P0 | Fondamentaux | Historique SEC PIT avec lignage complet | Source gratuite disponible, contrat/refresh à finaliser | Débloquer l'expérience fondamentale sans fuite temporelle |
| P1 | Direction SHORT/squeeze | Prêt de titres : borrow fee, utilisation, disponibilité | `BLOCKED_NO_PIT_HISTORY` | Pression vendeuse, crowding, squeeze et faisabilité réelle du short |
| P1 | Direction microstructure | Déséquilibres d'enchères d'ouverture/clôture | `BLOCKED_NO_DATA_SOURCE` | Flux acheteur/vendeur signé, distinct des quotes ordinaires |
| P1 | Direction fondamentale | Révisions d'estimations analystes PIT | Non testable avec les données actuelles | Changement d'anticipations, dispersion et révisions coordonnées |
| P2 | Options | Surface options historique dense et PIT | `BLOCKED_NO_DENSE_PIT_HISTORY` | Skew, demande puts/calls, IV relative et flux options |
| P3 | Entrée/exécution | Prémarché et plage d'ouverture | Absent localement | Confirmation au plus près de l'entrée next-open |
| P3 | Événementiel | 8-K/6-K complets, horodatés et structurés | Couverture partielle, expérience inconclusive | Direction propre à un événement d'entreprise |
| P4 | Positionnement lent | 13F/13D/13G PIT | Proposé, non prioritaire | Crowding institutionnel et changements de détention |
| P4 | Parité régime | Macro 2026 complète | Lacune connue | Reproduire le contexte de risque, faible promesse directionnelle |

L'ordre d'achat conseillé n'est pas exactement l'ordre technique. Il faut d'abord rendre la recherche fiable avec P0, puis demander des échantillons P1. Les options P2 peuvent coûter très cher : elles ne doivent être achetées qu'après un pilote contractuel et une estimation de couverture.

## 3. Contrat commun exigé de tout fournisseur

Une donnée n'est exploitable dans Alpha-Trade que si le fournisseur peut documenter les points suivants.

### 3.1 Point-in-time réel

Chaque observation doit comporter, directement ou de façon reconstructible :

- l'identifiant permanent du titre ;
- le ticker utilisé à la date concernée ;
- la date/heure de l'événement économique ;
- la date/heure de publication ou de première disponibilité ;
- la date/heure de réception, si elle diffère ;
- le fuseau horaire ;
- les versions, corrections, annulations ou restatements ;
- une règle claire indiquant la première séance où l'observation est légalement utilisable.

Un fichier qui reconstruit le passé avec la valeur connue aujourd'hui n'est pas PIT. Un champ `date` sans heure ni sémantique de disponibilité est insuffisant pour les signaux proches de l'ouverture ou de la clôture.

### 3.2 Couverture minimale à mesurer avant achat

Le fournisseur doit fournir un échantillon permettant de calculer :

- pourcentage des symboles de `univers_filtred_equities.txt` couverts ;
- pourcentage des événements Oracle TOP20 couverts ;
- couverture par année, semestre, secteur, capitalisation et côté réel D1/D10 ;
- profondeur historique, idéalement 2016-2025, ou au minimum plusieurs régimes ;
- fréquence des trous et délai de publication ;
- taux de correspondance sur identifiant permanent, pas seulement ticker courant ;
- politique sur les titres radiés, fusions, changements de ticker et faillites.

Pour une expérience Walk-Forward, une couverture moyenne élevée ne suffit pas : aucune année ne doit être presque vide. Comme règle de pré-audit, viser au moins 60 % des événements Oracle au total et 40 % dans chaque année évaluée. Ces seuils sont des gates de faisabilité, pas une preuve d'alpha.

### 3.3 Conditions commerciales à demander

- historique inclus dans le forfait ou facturé séparément ;
- API, fichiers bulk, SFTP ou cloud ;
- limites de débit et coût d'un backfill complet ;
- droit de stockage local permanent ;
- droit d'entraîner des modèles et de conserver les artefacts après résiliation ;
- droit d'utilisation en backtest, production et redistribution interne ;
- corrections historiques et délai de disponibilité ;
- échantillon gratuit portant sur des dates anciennes, pas uniquement le jour courant.

## 4. P0 — Fondations indispensables

### 4.1 Référentiel titres PIT, radiations et rendements de radiation

#### Problème constaté

Plusieurs expériences utilisent un univers et des métadonnées construits à partir de titres encore visibles aujourd'hui. Cela peut exclure les sociétés disparues et utiliser rétrospectivement leur classification actuelle. Les résultats OOS peuvent alors bénéficier d'un biais de survivants, particulièrement dangereux dans les petites et moyennes capitalisations et dans la queue D1.

#### Données nécessaires

- identifiant permanent : CIK, FIGI, CUSIP, ISIN ou identifiant propre stable ;
- historique des tickers avec dates d'effet ;
- dates de première cotation, suspension, radiation et reprise ;
- marché principal et venue de cotation par période ;
- type d'instrument par période : action ordinaire, ADR, preferred, ETF, ETN, fonds, trust, warrant, etc. ;
- classe d'action et lien entre émissions d'une même société ;
- raison de radiation et **rendement de radiation** quand disponible ;
- secteur et industrie avec historique de classification ;
- actions en circulation, flottant et capitalisation PIT ;
- splits, reverse splits, dividendes, spin-offs, fusions, acquisitions et distributions ;
- prix brut et prix ajusté avec convention d'ajustement explicite.

#### Pourquoi Alpha-Trade en a besoin

- reconstruire l'univers réellement tradable à chaque date ;
- calculer l'Oracle TOP20 sur le bon dénominateur quotidien ;
- conserver les perdants disparus dans les labels ;
- éviter qu'un changement de ticker casse la jointure entre barres, fondamentaux, options et modèles ;
- mesurer correctement les rendements autour des corporate actions ;
- rendre fiables les comparaisons par secteur et capitalisation.

#### Fournisseurs à examiner

- CRSP pour la recherche actions US, notamment l'historique de radiation et les rendements associés ;
- FactSet, LSEG, S&P Capital IQ ou autres security masters institutionnels ;
- combinaison SEC + données d'exchanges + fournisseur de corporate actions si le coût institutionnel est prohibitif.

Cette donnée est une priorité scientifique, même si elle n'apporte pas directement une nouvelle feature directionnelle.

### 4.2 OHLCV quotidien frais et corporate actions

#### Problème constaté

Les barres locales s'arrêtent autour de fin juin/début juillet 2026 depuis l'arrêt du flux EODHD. L'expérience prospective E17-B/E17-C sur le momentum résiduel H120 ne peut pas maturer ses cohortes futures sans nouvelles barres. La prédiction et le live finiront également par travailler sur un univers périmé.

#### Données nécessaires

- OHLCV quotidien régulier et, si possible, prémarché/postmarché séparés ;
- cours bruts et ajustés ;
- splits, dividendes et spin-offs avec dates ex/pay/record ;
- corrections historiques ;
- SPY, benchmarks sectoriels et facteurs de marché utilisés par les features ;
- couverture des titres actifs, suspendus puis radiés.

#### Pourquoi Alpha-Trade en a besoin

- poursuivre les validations prospectives sans réutiliser la période déjà explorée ;
- calculer les rendements H3/H5/H10/H20/H60/H120 ;
- rafraîchir les features de prix, de volatilité, de volume et de régime ;
- exécuter le live et le canary Oracle sur des données fraîches.

Alpaca expose des barres historiques multi-symboles et des corporate actions ; EODHD ou un autre fournisseur peut également rester la source principale. Le choix doit être fait sur la couverture, les ajustements et le droit de conservation, pas seulement sur le prix.

### 4.3 Fondamentaux SEC PIT avec lignage

#### Problème constaté

E19-A a montré un volume SEC local important, mais E19-A2 a aussi identifié un contrat PIT insuffisant pour distinguer correctement publication, période fiscale, amendement et restatement. Le code et la migration prévus doivent être appliqués, puis l'historique rafraîchi. Il s'agit davantage d'un problème de lignage et de normalisation que d'une absence de source brute.

#### Données nécessaires

- CIK et identifiant titre ;
- accession number ;
- formulaire : 10-K, 10-Q, 8-K, 20-F, 40-F, 6-K et amendements ;
- date/heure d'acceptation EDGAR ;
- date de disponibilité pour le modèle ;
- période fiscale couverte et date de fin de période ;
- contexte XBRL, tag, unité, valeur et durée/instant ;
- version originale, amendée ou retraitée ;
- mappings contrôlés des tags custom vers les concepts canoniques ;
- distinction dette financière/passifs totaux ;
- dividende par action distinct du rendement du dividende.

#### Pourquoi Alpha-Trade en a besoin

- tester proprement qualité, valeur, croissance, accruals, levier et détérioration fondamentale ;
- construire une famille d'alpha moins dépendante du bêta de marché ;
- empêcher une valeur retraitée ultérieurement d'être visible avant sa publication ;
- diagnostiquer les erreurs de labels causées par un mauvais rattachement de période.

La SEC fournit gratuitement les historiques de soumissions et les faits XBRL via API et archives bulk. Avant de payer un autre fournisseur, il faut terminer ce flux gratuit. Un fournisseur payant ne devient utile que s'il offre une normalisation PIT auditée, un bon mapping des concepts et une maintenance des corporate actions.

## 5. P1 — Nouvelles données directionnelles prioritaires

### 5.1 Prêt de titres et coût d'emprunt

#### Expérience concernée

Audit de faisabilité borrow/lending : statut `BLOCKED_NO_PIT_HISTORY`.

Les données locales ou accessibles au courtier décrivent surtout l'état courant (`shortable`, easy/hard to borrow). Elles ne permettent pas de rejouer 2016-2025. Le short interest publié périodiquement et le short volume quotidien ne sont pas des substituts à la disponibilité réelle du stock-loan.

#### Données nécessaires par titre et par jour

- borrow fee, stock-loan fee ou rebate rate ;
- bid, ask et last borrow rate si disponibles ;
- utilisation : quantité empruntée / quantité prêtable ;
- lendable supply et quantité réellement disponible ;
- shares on loan et évolution quotidienne ;
- statut easy-to-borrow, hard-to-borrow, non-shortable ;
- locate quote, locate size et coût effectif, si disponible ;
- short interest quotidien estimé et days-to-cover ;
- scores de crowding/squeeze, à condition de disposer aussi des variables brutes ;
- horodatage et heure limite de disponibilité avant la décision.

#### Transformations envisagées

- niveau et variation 1/5/20 jours du borrow fee ;
- percentile cross-sectionnel quotidien du coût ;
- variation d'utilisation et contraction de la disponibilité ;
- interaction fee élevé × utilisation élevée × momentum prix ;
- veto SHORT en cas de coût ou disponibilité incompatible ;
- détection d'un risque de squeeze pour une branche LONG ;
- différenciation entre pression vendeuse croissante et débouclement de shorts.

#### Pourquoi cette donnée est prioritaire

Elle décrit une contrainte économique et un déséquilibre d'offre/demande absent de l'OHLCV. Elle peut expliquer simultanément le sens futur et la possibilité réelle d'exécuter le short. S3 annonce un historique PIT depuis 2015 ainsi que rates, disponibilité et utilisation ; S&P Global annonce une longue profondeur quotidienne de supply, demand et fee. Il faut demander un extrait avant toute souscription et mesurer la couverture exacte des événements Oracle.

#### Ce qu'il ne faut pas acheter à la place

- uniquement le short interest bimensuel ;
- uniquement le short volume FINRA quotidien ;
- un champ courant `shortable` sans historique ;
- un score propriétaire impossible à reproduire et sans variables sources.

Ces substituts ont déjà été testés ou ne permettent pas un backtest PIT.

### 5.2 Déséquilibres d'enchères d'ouverture et de clôture

#### Expérience concernée

Piste auction/MOC-LOC : statut `BLOCKED_NO_DATA_SOURCE`.

Les quotes IEX/NBBO, le microprice et les barres cinq minutes déjà testés n'observent pas le carnet spécifique de l'enchère. Leur échec ne rejette donc pas l'hypothèse d'un déséquilibre MOC/LOC ou NOII.

#### Données nécessaires

- timestamp de chaque diffusion ;
- symbole, marché de cotation et venue ;
- paired shares / matched quantity ;
- imbalance quantity ;
- imbalance side buy/sell ;
- reference price ;
- indicative match price ;
- near/far clearing price lorsque disponible ;
- volume indicatif du cross ;
- quantités MOC, LOC, MOO et LOO lorsque le flux les distingue ;
- séquence complète des mises à jour, corrections et annulations ;
- prix et volume officiels de l'enchère ;
- calendrier précis des phases de diffusion.

#### Pourquoi Alpha-Trade en a besoin

- observer une pression acheteuse/vendeuse signée avant l'enchère ;
- tester si l'imbalance confirme ou contredit la direction proposée après Oracle ;
- expliquer les gaps entre close J et open J+1 ;
- séparer signal directionnel et risque d'exécution ;
- construire une règle d'abstention lorsque le flux d'enchère est opposé.

NYSE fournit des historiques TAQ contenant les order imbalances ; le produit NYSE TAQ Integrated inclut profondeur, trades et déséquilibres. Nasdaq diffuse le NOII avant ses crosses d'ouverture et de clôture. Il faut vérifier qu'un vendeur couvre toutes les venues de cotation de l'univers, car un flux NYSE seul laisse les titres Nasdaq sans information comparable.

#### Attention au timing

Si le modèle décide au close officiel, seules les publications arrivées avant le cutoff sont utilisables. Une confirmation à 15:59:xx peut changer le contrat de décision et doit être simulée avec latence. Les données d'enchère publiées après le cross ne peuvent servir qu'à l'exécution ou à la séance suivante.

### 5.3 Révisions d'analystes et consensus point-in-time

#### Expériences concernées

- révisions Yahoo : proxies insuffisants et résultats `NO_GO` ;
- Eroya earnings estimates : périodes inversées ou ambiguës, historique inexploitable ;
- variables forward locales : pas d'historique SEC car la SEC ne produit pas le consensus sell-side ;
- hypothèse DDR-1 : `NON_TESTABLE` avec les données présentes.

L'earnings surprise brute a été testée sur une couverture dense et rejetée. La nouvelle hypothèse ne consiste pas à racheter les mêmes actual/estimate, mais à observer la **trajectoire des anticipations avant la publication**.

#### Données nécessaires au niveau observation

- identifiant société/titre ;
- métrique : EPS, chiffre d'affaires, EBITDA, marge, FCF ou KPI sectoriel ;
- horizon fiscal précis : trimestre/année, date de fin de période ;
- valeur estimée, devise, unité et base ajustée/non ajustée ;
- analyste ou broker source, éventuellement anonymisé mais stable ;
- timestamp de création/révision/retrait ;
- ancienne et nouvelle valeur ;
- timestamp de première disponibilité ;
- nombre d'analystes inclus dans le consensus ;
- mean, median, high, low et dispersion du consensus ;
- recommandations, upgrades/downgrades et prix cibles avec historique ;
- date/heure réelle de publication de l'actual et période correspondante ;
- politiques de split, restatement et exclusion d'estimates.

#### Features envisagées

- breadth des révisions positives/négatives sur 5/20/60 jours ;
- amplitude médiane des révisions ;
- accélération des révisions ;
- dispersion et contraction/élargissement du consensus ;
- fraîcheur de la dernière révision ;
- révision pondérée par l'historique de précision de l'analyste ;
- désaccord entre prix, Oracle amplitude et consensus ;
- événement coordonné : plusieurs brokers révisent dans le même sens.

#### Pourquoi Alpha-Trade en a besoin

Une surprise publiée est trop tardive ou déjà intégrée. Une modification progressive des anticipations peut en revanche indiquer le sens avant l'événement. LSEG I/B/E/S propose des historiques point-in-time et décrit des clusters de révisions ; FactSet propose également un consensus PIT. Ce sont des sources institutionnelles probablement coûteuses : demander d'abord un échantillon quotidien multi-années pour 30 à 50 symboles incluant des radiés.

## 6. P2 — Options historiques : potentiel réel, coût élevé

### 6.1 Ce qui a déjà été testé

Les collectes Eroya ont produit environ 625 événements, 155 symboles et seulement huit dates distinctes ; environ la moitié seulement possédaient une surface considérée complète. Ce volume ne permet pas une validation Walk-Forward robuste.

Les variantes long-straddle 45 DTE, y compris DTE adapté à l'horizon, ont été `NO_GO` sur ce petit historique. E7 a trouvé un signal H3 ponctuel, mais sur une seule fraction de l'historique et sans rendement LONG brut convaincant. Il ne faut donc pas acheter un historique coûteux uniquement pour répéter le même straddle fixe.

### 6.2 Hypothèses encore ouvertes

- évolution temporelle du skew put/call avant l'événement ;
- pente et courbure de smile ;
- demande relative puts/calls par volume et open interest ;
- variation d'IV, pas seulement niveau instantané ;
- realized volatility attendue par l'Oracle versus implied volatility ;
- flux optionnel signé et pression sur certains strikes/expirations ;
- term structure et déplacement relatif des maturités ;
- proxies de dealer gamma/vanna, avec hypothèses explicites.

### 6.3 Contrat de données minimal

Par contrat et timestamp :

- underlying et identifiant permanent ;
- OCC symbol/root ;
- expiration, strike et type call/put ;
- bid/ask NBBO et tailles ;
- last/trade price, taille et condition de trade si possible ;
- volume et open interest ;
- implied volatility et Greeks, ou entrées nécessaires pour les recalculer ;
- spot du sous-jacent au même timestamp ;
- taux sans risque, dividendes attendus et convention de calcul ;
- multiplicateur et historique des ajustements de contrat ;
- timestamp précis et session ;
- corrections et annulations.

Pour évaluer économiquement une stratégie, il faut conserver le **même contrat** entre l'entrée et la sortie et disposer de ses quotes à open J+1 puis H3/H5/H10/H20. Une simple chaîne EOD actuelle ou un snapshot ATM ne suffit pas.

### 6.4 Profondeur minimale

- au moins 504 dates de marché, idéalement 2022-2025 ou davantage ;
- plusieurs régimes de volatilité ;
- couverture suffisante de l'univers Oracle, mesurée par événement ;
- appels/puts et plusieurs deltas/maturités ;
- minute bars ou snapshots à heures fixes ;
- idéalement trades et quotes OPRA si le test porte sur le flux signé.

Cboe DataShop indique que ses Option Quote Intervals peuvent fournir des résumés une minute avec NBBO, tailles, OHLC et volume, avec IV/Greeks en option. C'est un bon format de demande de devis/pilote. ThetaData reste techniquement possible mais avait été suspendu pour raison commerciale ; la présence d'une bibliothèque Python ne remplace pas l'abonnement historique.

## 7. P3 — Données utiles sous conditions

### 7.1 Prémarché, ouverture et opening range

#### Données nécessaires

- trades et quotes du prémarché, idéalement tick ou minute ;
- volume, spread, profondeur et nombre d'impressions ;
- opening auction imbalance/NOII ;
- prix indicatif puis prix officiel d'ouverture ;
- gap overnight brut et ajusté du marché ;
- barres 1/5 minutes sur les 30 à 60 premières minutes ;
- trade conditions pour écarter les impressions non régulières.

#### Pourquoi les tester

L'entrée canonique se fait au prochain open. Ces données peuvent détecter qu'un signal construit à J est invalidé pendant la nuit, améliorer le fill attendu ou imposer une abstention. Elles sont plus proches du moment d'exécution que la microstructure de clôture ordinaire déjà rejetée.

#### Limite conceptuelle

Les utiliser change le contrat : une décision après observation de l'open n'est plus une entrée stricte au next-open. Il faut pré-enregistrer un délai d'entrée réaliste, par exemple après l'enchère ou après une opening range, puis appliquer slippage et coûts correspondants.

### 7.2 8-K, 6-K et événements d'entreprise structurés

#### État actuel

La collecte 8-K avait une couverture appréciable mais une forte concentration, des répétitions et aucun gate stable. Le résultat est `INCONCLUSIVE`, pas un signal prêt à servir.

#### Données complémentaires utiles

- accession number et timestamp d'acceptation ;
- item codes complets et amendements ;
- texte intégral, pièces jointes et exhibit 99.1 ;
- 6-K pour les émetteurs étrangers ;
- typologie normalisée : guidance, contrat, dette, acquisition, management, litige, financement, impairment ;
- extraction des montants, dates, contreparties et changement par rapport à la guidance précédente ;
- lien permanent entre société, titre et événement ;
- déduplication des republications et reprises média.

#### Pourquoi

Un événement précis peut donner le sens que l'Oracle amplitude ne connaît pas. Toutefois, comme les catégories simples ont été instables, privilégier la SEC gratuite et un meilleur parsing avant d'acheter un flux événementiel coûteux.

## 8. P4 — Faible priorité ou horizon mal aligné

### 8.1 13F, 13D et 13G

#### Données nécessaires

- manager/filer, CIK et accession ;
- date de période et timestamp de dépôt ;
- identifiants issuer/security ;
- quantité, valeur, put/call, discretion et voting authority ;
- amendements et versions ;
- changement depuis le dépôt précédent ;
- agrégation par manager actif/passif/hedge fund ;
- 13D/13G et amendements pour les changements de détention significatifs.

#### Pourquoi la priorité est basse

Le 13F est trimestriel et publié avec retard. Il est plus adapté au crowding et aux horizons longs qu'à D1/D10 sur H3-H20. La SEC permet une collecte gratuite ; cette piste doit venir après borrow, auctions et revisions analystes.

### 8.2 Macro 2026

#### Lacune

Une partie des séries macro/volatilité utilisées par l'application n'est plus alimentée en 2026 : VIX/VXN/VIX3M/MOVE et autres variables de régime selon les pipelines.

#### Pourquoi la récupérer

- parité entre backtest et live ;
- contrôle de risque et classification de régime ;
- analyse de dérive 2026 ;
- suppression du fallback neutre dans les diagnostics.

#### Pourquoi ne pas la classer comme achat alpha prioritaire

Les ablations et tests de macro déjà réalisés n'ont pas expliqué l'échec directionnel principal. La simulation de macro absente sur 2024-2025 a réduit la performance de façon limitée, sans reproduire le décrochage 2026. Remplir la lacune est utile pour la qualité opérationnelle, mais ne promet pas de résoudre D1/D10.

### 8.3 News/sentiment enrichi

Le sentiment interne et les collectes Eroya ont été testés sans résultat robuste. Une nouvelle source n'est justifiée que si elle fournit quelque chose de réellement différent : corpus historique complet, timestamps immuables, rattachement ticker fiable, événements structurés, nouveauté de l'information et changements de narrative. Un simple score positif/négatif de headline ne mérite pas un nouvel abonnement.

## 9. Données déjà testées : ne pas les racheter sous la même forme

| Famille | Verdict observé | Ce qui pourrait justifier une réouverture |
|---|---|---|
| Short volume quotidien | `NO_GO` | Borrow fee/utilisation/lendable supply, pas plus de short volume identique |
| Short interest sparse | `NO_GO` | Historique quotidien de prêt de titres ou changements réellement PIT |
| News sentiment générique/FinBERT/Eroya | `NO_GO` | Événements structurés ou révisions d'anticipations réellement nouvelles |
| Earnings surprise et distance aux résultats | `NO_GO` avec données denses | Trajectoires PIT des estimates avant annonce |
| Form 4 agrégé | `NO_GO` | Signal transactionnel beaucoup plus ciblé et échantillon indépendant |
| Barres 5 minutes session complète | `NO_GO` directionnel | Prémarché/opening range avec contrat d'entrée différent |
| Quote IEX/NBBO de clôture, spread, microprice, depth | `NO_GO` | Véritable carnet/imbalance d'enchère |
| Trades signés et accélération de flux | `NO_GO` | Flux d'enchère ou options, économiquement distinct |
| Contexte intraday SPY/QQQ/IWM/VXX | `NO_GO` | Nouveau régime indépendant et pré-enregistré |
| Long-straddle 45 DTE fixe/adapté | `NO_GO` sur l'échantillon disponible | Surface temporelle/flow ou realized-minus-implied sur historique dense |
| Screener | Couverture réparée puis `NO_GO` | Nouvelle variable fondamentale réelle, pas nouveau remplissage du même score |
| Historique des scores internes | Couverture réparée puis `NO_GO` directionnel | Nouvelle cible ou nouvelle donnée exogène |
| Features macro historiques | Gain non démontré | Usage risk/regime plutôt que promesse directionnelle |

## 10. Ordre concret de recherche des fournisseurs

### Lot A — À lancer immédiatement

1. **Prêt de titres historique** : demander un échantillon 2019-2025 avec fee, utilization, lendable supply et availability.
2. **Order imbalance historique** : demander NYSE + Nasdaq, ouverture et clôture, avec séquence intraday et timestamp.
3. **Consensus/révisions PIT** : demander un extrait observation-level, pas un consensus actuel backfillé.

Pour chaque lot, commencer par 30 à 50 symboles couvrant grandes/moyennes/petites caps, D1/D10, radiés et changements de ticker. L'échantillon doit inclure plusieurs dates anciennes imposées par nous.

### Lot B — Demande de devis et pilote contrôlé

4. **Options historiques** : prix d'un sous-ensemble de 20 à 50 symboles, 2022-2025, minute NBBO + volume/OI + IV/Greeks, plusieurs deltas et DTE.
5. **Security master/delistings** : comparer une solution institutionnelle à un assemblage SEC/exchanges/corporate actions.

### Lot C — À collecter gratuitement ou à faible coût avant achat

6. Terminer le refresh fondamental SEC avec lignage PIT.
7. Maintenir les barres quotidiennes et corporate actions.
8. Enrichir 8-K/6-K depuis EDGAR.
9. Collecter 13F/13D/13G uniquement pour une expérience long-horizon pré-enregistrée.

## 11. Questionnaire fournisseur prêt à l'emploi

Pour éviter un achat inutilisable, envoyer les questions suivantes à chaque vendeur :

1. S'agit-il d'un historique point-in-time conservant les valeurs originales, corrections et suppressions ?
2. Quel champ représente la première disponibilité de l'information ? Avec quelle précision horaire et quel fuseau ?
3. Quelle est la profondeur historique pour les actions US, y compris titres radiés ?
4. Les changements de ticker, fusions, spin-offs et ajustements sont-ils fournis avec identifiants permanents ?
5. Pouvez-vous livrer un échantillon sur nos propres symboles et dates anciennes ?
6. Quel est le taux de couverture attendu sur 2016-2025, par année ?
7. Les fichiers historiques sont-ils réécrits avec les valeurs courantes ou versionnés ?
8. L'usage autorise-t-il backtests, entraînement ML, stockage local et serving interne ?
9. Que peut-on conserver après résiliation ? Les modèles entraînés restent-ils utilisables ?
10. Quel est le coût total d'un backfill, puis du rafraîchissement mensuel/quotidien ?
11. Existe-t-il un export bulk évitant des millions d'appels API ?
12. Comment sont traités les jours sans observation : zéro économique, donnée inconnue ou absence de couverture ?

## 12. Gates avant intégration définitive

Aucune nouvelle source ne doit entrer directement dans le batch final. Le protocole conseillé est :

1. audit de schéma et de sémantique PIT ;
2. rapport de couverture par date/symbole/événement Oracle ;
3. contrôle manuel d'un petit échantillon contre la source primaire ;
4. gel de la population, des features, des horizons et métriques ;
5. baseline sans nouvelle donnée ;
6. ablation avec une seule famille nouvelle ;
7. Walk-Forward avec mêmes folds ;
8. résultats séparés LONG, SHORT, D1/D10, semestre et régime ;
9. correction du multiple testing ;
10. mesure économique après coûts et taux d'abstention ;
11. période OOS finale non utilisée pour choisir la source ou les paramètres ;
12. décision `GO`, `NO_GO`, `INCONCLUSIVE` ou `BLOCKED_DATA`, documentée dans `experiences_done.md`.

Une source est utile seulement si elle améliore plusieurs folds et périodes, pas si elle produit une belle moyenne sur quelques dates. Pour la mission Oracle, les métriques principales doivent être conditionnelles au pool Oracle et inclure précision LONG/SHORT, séparation D1/D10, calibration, rendement futur et stabilité.

## 13. Recommandation finale

Pour chercher des fournisseurs aujourd'hui, l'ordre rationnel est :

1. **borrow/lending PIT** ;
2. **auction imbalance NYSE + Nasdaq** ;
3. **analyst estimates/revisions PIT** ;
4. **options historiques denses**, uniquement via pilote ;
5. **security master/delistings**, indispensable à la robustesse générale ;
6. **barres et corporate actions fraîches**, indispensable à la continuité ;
7. autres familles seulement si elles sont gratuites ou très peu coûteuses.

En parallèle, il ne faut pas attendre un fournisseur pour terminer le contrat fondamental SEC : la matière première est déjà disponible gratuitement. Enfin, le manque de nouvelles observations prospectives ne peut pas être acheté ; il faut continuer à accumuler des cohortes futures intactes.

## 14. Sources externes de référence

- SEC EDGAR APIs : historique de soumissions et faits XBRL, sans clé API, avec archives bulk.
- NYSE Historical TAQ Integrated Feed : profondeur, trades, auction imbalances et security status.
- Nasdaq NOII : paired shares, imbalance shares/side et prix indicatifs des crosses.
- Cboe DataShop Option Quote Intervals : snapshots une minute, NBBO, tailles, OHLC, volume, IV/Greeks en option.
- LSEG I/B/E/S : historique d'estimations et offre Point-in-Time ; analytics de clusters de révisions.
- FactSet Estimates Point-in-Time Consensus : consensus historique quotidien.
- S3 Partners et S&P Global Securities Finance : short positioning, rates, availability/utilization et historiques PIT.
- CRSP US Stock Databases : événements/rendements de radiation, prix et capitalisation historiques.

