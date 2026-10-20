# Registre des expériences ML réalisées

## 2026-10-20 — Retour à la moyenne intraday SIP : règle figée non rentable

**TERMINÉ / NO_GO DE CETTE RÈGLE / AUCUNE PROMOTION.** Nouvelle expérience à
entrée et sortie dans la même séance, pas features intraday pour prédire H20.
66 900 couples sélectionnés avant résultats, 100 candidats liquides par jour
parmi l'univers tradable actuel, 234 titres distincts. 3 238 954 barres existantes
SIP 5m extraites en transaction READ ONLY ; aucune donnée 2024 sur ce panier,
donc aucune performance 2024 calculée. Pas de SPY/ETF sectoriel intraday local :
médiane du panier sur préfixes valides, minimum 80 %/50 titres, sans élimination
d'un pair à cause d'un trou futur. Excès relatif 2 %, début de retournement,
entrée à la barre suivante, stop 1 %, objectif VWAP proxy figé, expiration à
l'ouverture de la dernière barre. Coûts 10 bps/jambe +1 USD/ordre sur 1 000 USD,
stress 25 bps. Pas de portefeuille partagé, levier ou rendement annuel composé.

11 753 signaux, 11 687 chemins initialement évaluables ; 13 réserves de prix
supplémentaires laissent **5 338 occasions 2025 / 6 336 en 2026**. Quatre lignes
appariées corrigées conservativement pour plafonner un gap final au TP ; sources
et premier rejeu conservés, supplément qualifié scellé distinct. 30 chemins
incomplets, 33 abstentions après gap au-delà de l'objectif, trois réserves de
base de prix, jamais remplacés par pertes ou autres titres.

**LONG principal : 2 719 / 3 158 occasions, net moyen −0,418 % / −0,350 %**,
gagnants 37,07 % / 40,22 %. Sans commission fixe, mêmes frictions :
−0,218 % / −0,150 %. Panier liquide ∩ TOP20 % Oracle veille LONG :
−0,448 % / −0,343 % ; ∩ TOP10 LONG : **−0,616 % / −0,086 %**, 70/182cas,
sept/douze titres seulement. Oracle PATH_H20 CatBoost de recherche OOS archivé,
pas le champion LightGBM live ; jamais le rang calculé à la clôture du même jour.
SHORT diagnostique également négatif, locates non qualifiés. Contrôles inverse
et toujours LONG/SHORT publiés, aucune inversion/optimisation après résultat.
Gates LONG stress/avantage apparié échouent en 2025 et 2026. « Toujours LONG »
identique sur le sous-groupe LONG, pas preuve indépendante de valeur du signal.

22 tests, 46 748 sorties/coûts initiales et tous les 66 900 candidats/signaux
revérifiés par autre implémentation du même assistant, pas revue humaine
indépendante. Biais de survivants, liquidité daily retraitée, pas NBBO/fills
historiques certifiés ; pas de nouveau téléchargement, SQL écrit, LLM,
entraînement, ordre, changement batch/modèle/config de trading. Clôture de
cette règle, pas réfutation de tous les arbitrages statistiques institutionnels.
[Protocole, bilans qualifiés, coûts, contrôles et 13 réserves](retour_moyenne_intraday_20261020.md).

## 2026-10-20 — Rachats à prix fixe SC TO-I : faisabilité sans trade qualifié

**RECENSEMENT/REVUE TERMINÉS / AUCUN BACKTEST / PAS DE PROMOTION.** Onze index
SEC complets réutilisés, 2024–septembre2026 : 1616lignes initiales,1612accessions
distinctes(579/577/456),2017lignes d’amendements non traitées comme offres nouvelles.
39dépôts route tradable courant1790(27émetteurs),plus12horsroute par hash avantprix,
51dossiers relus :9dettes,4échanges,7enchères,24fondsNAV/noncotés,3préférentielles,
2warrants,1rémunération salariés,1réserve Infosys. Tous39courants inclus, pas
revue contractuelle exhaustive des1561autresdépôts. CNNE/GPRK/MNST/COKE/WEX/WIX/
SCHL prix en fourchette, bornehaute jamais réputée garantie. Infosys fixe1800INR
suractionsindiennes, pasADSUS ; recorddate14novembre avant dépôt18novembre2025,
retraitADS préalable/éligibilité/canal/frais réservés. Aucun trade admis.
Alpaca publie actuellement100USD/élection volontaire :5% sur2000USDactions,
2,5% sur4000USD, horsautrescoûts ; PAS tarifhistorique/compte prouvé ni PnL.
Élection/règlementpas un ordrePAPER normal, aucun lifecyclecourtierqualifié.
50originauxcomplets+complémentHTMLprincipalKIM(après plafond20Mio),sources/citations
conservées ;53requêtesSEC/123173186octets/HTTP200 ;6tests,audit documentaire.
PasSQLécrit,prixAPI,LLM,entraînement,ordre/élection,batch/modèle/univers modifiés.
[Résultats, exclusions, frais, réserve Infosys et archives](rachats_prix_fixe_faisabilite_20261020.md).

## 2026-10-20 — Sorties d’indices / rebond : faisabilité bloquée par la source

**AUDIT DES SOURCES TERMINÉ / PAS DE BACKTEST / PAS UN NO_GO ÉCONOMIQUE.**
Listes Russell publiques repérées, mais conditions LSEG sections9–10 ne
qualifient pas notre automatisation : aucun script de téléchargement LSEG,
aucun miroir, liste extraite ou import SQL. Alternative distincte SEC : trois
premières recherches interprétaient AND/parenthèses littéralement ; zéros
conservés mais invalides comme nombres d’événements. Contrôle positif 3529
documents2025 ; requêtes simples Russell+removed :950/969/890documents
2024/25/26, seulement100parpage, explicitement tronquées, pas autant d’exclusions.
Cinq originaux SU/PSO/MTX/RGR/PIPR relus, sélection date/accession avantprix,
tous2024 : mentions non qualifiées ; PIPR annexe rémunération/pairs, pas sa
suppression. Pas de cohorte complète, ni conclusion zéro événement historique.
12requêtesSEC/5535118octets/HTTP200 ; quatretests, audit de sources séparé.
Piste en attente d’autorisation LSEG ou fournisseur adapté, sans achat ;
EODHD historique S&P ne prouve ni Russell ni première annonce ni abonnement
actuel compatible. Contrat proposé LONGaprès effet, principalH5/secondairesH10H20,
témoins taille/liquidité as-of etSPY ; AUC/PnL non calculés. Aucun modèle,
prixAPI, LLM, SQLécrit, ordre, batch/config métier modifiés.
[Bilan de faisabilité, droits, archives et prérequis](reconstitutions_indices_faisabilite_20261020.md).

## 2026-10-20 — Activisme 13D : confirmation 2025–2026 défavorable

**TERMINÉ / PAS D’AVANTAGE STABLE / AUCUNE PROMOTION.** Index complets 2025
et 2026Q1–Q3 ; 222 originaux sélectionnés avant prix, dont 70 hors route du
mapping courant par sondage hash. 26 fausses attributions déclarant/cible
évitées ; 19 interventions admises, identités historiques confirmées, quatre
dossiers documentaires réservés. PBT unités de trust explicitement séparées
dans les métadonnées ; complément EMPD après changement de ticker, avant prix.
Même LONG1000USD indépendant, entrée après date SEC, 20/60 séances entrée
comprise, 1USD/ordre +10bps/jambe, aucun TP/SL/trailing/levier.
**2025 : 9/10 évaluables, nets moyens −0,94 % / −6,67 %**, SPY −1,24 % / +2,22 %,
positifs/négatifs 4/5 puis1/8. **2026 : 5/9 puis3/9 évaluables, −13,50 % / +2,97 %**,
SPY −2,96 % / +6,80 %, 1/4 puis1/2 ; H60 médiane−14,35 %, dépendance CODI.
ANTX/EMPD/SEER/LODE sans prix dans la bande existante, conservés UNKNOWN ;
MTN H20/H60 et UMH/HGV H60 non échus à la borne figée 30septembre2026.
Pas rendement annuel/portefeuille ni couverture exhaustive des radiés ;
échantillon survivant courant et sondage limités. Aucun TOP10 évaluable,
4TOP20%2025 et3TOP20%2026 : pas solution directionnelle TOP10.
43tests ; audit sources/admissions/identités/maturités/coûts/rangs et inconnus.
Audit PASS avec réserves de couverture : 222originaux,19identités,38issues
dont26évaluables/8inconnues/4nonéchues ; 265requêtesSEC,136155856octets,HTTP200.
Même assistant, pas seconde revue humaine indépendante. Pas d’API prix/LLM,
SQLécrit, entraînement, ordre, modèle/batch/config métier modifiés.
[Résultats individuels, couverture, protocole et archives](activisme_13d_confirmation_2025_2026_20261020.md).

## 2026-10-20 — Activisme 13D : extension à toute l’année 2024

**TERMINÉ ET AUDITÉ / SEPT SOCIÉTÉS / PAS DE SIGNAL VALIDÉ.** Index complets
2024 : 1 100 accessions initiales distinctes ; 100 dossiers par route du mapping
tradable courant1790, plus40 hors route sélectionnés par hash avant prix.
140originaux obtenus/reparsés ; LUV32,47Mo récupéré séparément sous plafond40Mio
après plafond initial12Mio. SUBJECT COMPANY évite39fausses attributions au
déclarant.61ciblescourantes+40sondage ; 8interventionsprincipales, secondBJRI
bloqué60séances avantprix : **GIL/BJRI/CRTO/MTCH/ATEX/LUV/BTU**, TPLsecondaire.
SMPsection nonrécupérée/Neuraxisnomination-financement restent réservés ;
sondagehorsunivers PAS couverturecomplète desradiés ni universPIT.
Mêmecontrat LONG1000USDindépendant, nextfullopen aprèsdateSEC, close20/60séances,
1USDordre+10bpsjambe, sansTP/SL/trailing/levier. **Quatre nouveaux cas** :
H20 MTCH−1,71/ATEX−10,67/LUV+22,42/BTU−4,08%, moyenne **+1,49%**, médiane−2,90%,
SPY+0,60%, **1positif/3négatifs**. H60+9,82/−22,26/+28,43/+17,31%, moyenne
**+8,32%**, SPY+6,43%, 3positifs/1négatif. Ensemble7cas+4,16/+8,97%, SPY+1,95/
6,24%. Forte dépendanceàLUV ; sansLUV nouveauxcas−5,49/+1,62%, PAS nouveaurègle.
ZéroTOP10, seulBJRI TOP20%; **aucune solution directionnelle TOP10 démontrée**.
Lettres parfoisantérieures, ATEXnominationconsensuelle explicitée, prixajustés
proxy paslifecycle/fills/portefeuille ; Q1déjàobservé pasconfirmationinédite.
33tests ; audit140originaux/16coupleshorizons, admissions, prix/rangs et coûts,
Q1reproduitexactement.137nouvellesrequêtesSEC/121483504octets ; aucuneAPIprix/LLM,
SQLécrit/entraînement/ordre/batchmodifié. Index2025disponibles,90dossiersroute
courante repérés **non qualifiés et non testés**. Aucunrunlaisséencours.
[Résultats détaillés, réserves et reproductibilité](activisme_13d_elargissement_20261020.md).

## 2026-10-20 — Activisme13D : pilote historique après dépôt, 2024Q1

**TERMINÉ ET AUDITÉ / POSITIF SUR TROIS CAS / PAS DE SIGNAL VALIDÉ.** Index SEC
complet2024Q1 :618lignes initiales13D/313accessions,23accessions rattachées au
CIKcourant tradable1790 avant toute lecture de prix.23originaux obtenus :
13faussesattributions déclarant/cible écartées(JPM/BEN/BNTX/FHI),10Item4/annexes
nécessaires relus. Quatre interventions explicites, mais seconde entréeBJRI
bloquée60séances avant qualitéfuture :3émetteurs principaux GIL/BJRI/CRTO ;
TPL gouvernance séparé,5autresdossiers exclus(donation/acquisitions/générique/
financementpréliminaire). Couvertures annuelles préfilingBJRI/CRTO confirment
les symboles/classeADS ; GILticker dans lettre originale.27requêtesSEC,
12891411octets, archives/citations/hash conservés, aucun prixAPI/LLM.
LONGnotionnel1000USD indépendant, entréeopen aprèsdate13D, close20/60séances,
sansTP/SL/trailing/levier,1USDordre+10bpsjambe, stress25bps. Nets H20
**GIL+6,77/BJRI+10,47/CRTO+5,96%**, H60 **+14,48/+2,16/+12,84%** ; moyennes
**+7,73/+9,83%**, SPY mêmesdates **+3,75/+5,99%**, écarts **+3,99/+3,84points**.
Troispositifs sur3 mais PAS winrategénéralisable, horizons imbriqués,
universcourantsurvivant etuntrimestre ; prixajustésproxy, pasportefeuille/fills/
lifecyclebroker certifiés. Lettres GILdécembre/CRTO22février antérieuresaux13D :
aucune revendication d’alpha de premièreannonce ou réceptionlocale historique.
**ZéroTOP10**, seulBJRIrang226/1790dansTOP20%(autres805/435, TPL520).
TPLsecondaire+0,45/+18,28% nonpoolé.23testsciblés ; audit23originaux et8cas/
horizonsPASS, mêmeassistant pasrevuehumaineindépendante. Aucun entraînement,
SQLécrit, ordre, modèle/config/univers/batchmodifié ou jobderechercheactif.
[Cohorte, exclusions, sources, coûts, résultats et limites](activisme_13d_pilote_20261020.md).

## 2026-10-20 — Décomposition nuit/séance, Oracle parcours H20 TOP10 et TOP20%

**TERMINÉ ET AUDITÉ / `NO_ROBUST_OVERNIGHT_INTRADAY_IMPROVEMENT` / PAS DE PROMOTION.**
Trois règles figées avant résultats : signes des20rendements log en séance,
de nuit, ou accord sinon abstention ; CLOSE20 et toujoursLONG en références.
TOP20% ajouté explicitement par utilisateur avant calcul. OracleH20 CatBoost
annuel de recherche déjà audité, pas H10 ni modèle live courant ;1195076scores,
6690TOP10 et239074TOP20%,669séances2024–1septembre2026. OHLC ajustés sur
facteur du même jour, réserves DD/TOELY conservées, sans remplissage ni remplacement.
EntréeJ+1open, sortieclose après5/10/20séances, sansTP/SL/trailing ;10bps/jambe,
stress25bps, prêtSHORT0,3%hypothétique. Aucun rendement de capital ou paritélive.
Admission principale sans chevauchement20séances par symbole AVANT qualité/sens
futurs,673TOP10 et14662TOP20% qualifiés àH20. Séance : nets moyens par occasion
TOP10 **−3,274/−2,577/+4,571%** ; TOP20% **−0,483/+0,462/+0,953%** (2024/25/26).
Précision TOP1043,92/44,35/60,00%, bascule2026 non confirmée. Nuit/accord
échouent aussi ; aucune des six règles/périmètres ne passe les gates annuels
et IC par blocs corrigés. SensibilitésH5/H10 non transversales. LONG séance
TOP20% descriptif+0,641/+2,561/+2,986%, inférieur au LONG non filtré2024,
pas filtre ni combinaison validés. Queues D1/D10 secondaires du plein univers
scoré qualifié≥95%, conditionnelles, différentes des labelsSQL/parcoursdominant.
**21tests** ; audit245764admissions,250historiques,750issues et3484710lignes
de calcul avec variantes, pas autant de trades indépendants. AuditPASS,
même assistant, pas revue humaine indépendante. Aucun entraînement, API/LLM,
SQLécrit, ordre, production/batch/config modifié ou job de recherche actif.
[Protocole, résultats annuels, coûts, couverture et limites](decomposition_nuit_seance_oracle_20261020.md).

## 2026-10-20 — Rachats nets d’actions : pilote documentaire borné

**PILOTE DE DONNÉES TERMINÉ ET AUDITÉ / EFFICACITÉ NON TESTÉE.** Vingt symboles
du tradable courant choisis par SHA256 avant montants/prix, sans remplacement ;
premier10-K original2024,16rapports annuels en cache. Huit originaux figés pour
revue, sept obtenus, GSBD réservé au plafond8Mio ;16requêtes publiques SEC,
33871673octets lus, reçus/hash/citations conservés. **43/43montants** normalisés
rapprochés exactement des originaux. Le premier essai réseau local échoué est
conservé séparément, aucune réponse fournisseur refusée contournée.
Cash rachat≠baisse nette des actions : classes et SBC DBX/RPRX/WTTR,
financières WRB/JEF, capex CL705M sous un autre tag. HCSG candidat numérique
lisible :11,283Mrachats, actions−1,0083%, CFO−capex38,092M ; pas un trade
gagnant ni une annonce nouvelle. Zéro événement entièrement admis au comparatif
secteur/cap as-of ; aucun H20/H60, PnL, entraînement ou testTOP10 calculé.
Panel courant survivant, qualification historique reconstruite maintenant,
échantillon trop petit pour le test comparatif figé ; pas preuve de nécessité
de données payantes. Audit finalPASS, **19tests ciblés** ; même assistant,
pas revue humaine indépendante. Aucun SQLécrit, LLM, ordre, modèle/config/batch
modifié ou job laissé actif. Pilote clos, standardisation du panel requise
avant le test d’efficacité, pas rejet directionnel de la piste.
[Sélection, couverture, cas, sources et suite bornée](rachats_actions_pilote_20261020.md).

## 2026-10-20 — Acquisitions cash : pilote économique cinq opérations

**TERMINÉ ET AUDITÉ / PETIT RÉSULTAT POSITIF / PAS DE PROMOTION.**
Cinq cas figés RYZB/SNCE/CBAY/NGMpublicnon-rollover/SCTL, entrée prochaine
ouverture après jour du dépôt initial,800USD par cas sur4000USD, fractions,
LONGsanslevier,1USDparachat+10bpsfriction, pasTP/SL. Créance à clôtureSEC,
cash selonpayable_datefournisseur, pas créditbroker qualifié.01jan–30juin2024.
Tradingnet **+31,49USD**, cinqgagnants/zéroperdant, mais cinqacquisitionsachevées
etaucunerupture dans cettepetitecohorte : paswinrategénéralisable.
Sans intérêtcash :4031,49USD/+0,79%/DD−1,03%. Avec cash4%annuelHYPOTHÉTIQUE :
4097,83USD/+2,45%/DD−0,97%, dont66,34USDintérêts ; témointoutcash4079,00USD,
doncseulement **+18,83USD** d'excédent. Coûts25bps :4gagnants/1perdant ;
retardcrédit2/5séances :excédent17,52/15,68USD. Septscénariosfigés,27tests
et septrejeuxquotidiensPASS. Issuesconnuesavantconceptionéconomique, pasholdout.
Pasd'annualisation ni certifcourtier, fraisfusion0hypothèse. Aucun nouvelappel
fournisseur/LLM, entraînement, SQLécrit, ordre ou changementproduction/batch.
[Règles, cinq gains, référence cash, sensibilités et archives](arbitrage_acquisitions_cash_pilote_economique_20261020.md).

## 2026-10-20 — Acquisitions cash : treize initiales, cinq clôtures et tapes pré-clôture

**ÉTAPE DOCUMENTAIRE TERMINÉE / TEST EXPLORATOIRE PRÉPARABLE / PAS DE PNL.**
Treize dépôts initiaux SC TO-T2024Q1 revus, huit exclusions par modalités
initiales, cinq candidats figés avant dénouements : RYZB62,50/SNCE5,75/
CBAY32,50/NGM1,55/SCTL1,10USD. NGMpublicnon-rollover seulement ; EURNajustable
aux distributions et KNTEcashvariable+CVR restent exclus du pilote simple.
23dépôts ultérieurs complets,15amendements numérotés sans trou observé+8rapports8K.
Cinq acquisitions juridiquement achevées, zéro résiliée/nonrésolue dans cette
population admissible, **pas cinq trades gagnants** ni estimation du risque rare.
Clôtures26février/12mars/22mars/5avril/8avril2024 ; droits contractuels rapprochés.
AlpacaSIPraw/split :94/94séances pré-clôture valides, deux marques de clôture
CBAY/NGMvolume0transactions0 conservées en quarantaine, aucun titre retiré.
CUSIPcouverturesSEC/actionsAlpaca concordants ; six lignes cashmerger→cinqdroits,
pas doublepaiementCBAY. Cinqpayable_datefournisseur déclarées, zéro crédit
courtier réel qualifié : hypothèse de simulation future à afficher, pas T+2inventé.
18tests et auditcompletPASS,31requêtesSECnouvelles+3Alpaca ; pas d'achat.
Aucun rendement/spread/PnL, entraînement/LLM/SQLécrit/ordre ou changementproduction.
[Cohorte, cinq chronologies, sources, tapes et limites](arbitrage_acquisitions_cash_cohorte_20261020.md).

## 2026-10-20 — Arbitrage acquisitions cash : faisabilité documentaire bornée

**AUDIT TERMINÉ / DONNÉES INITIALES ACCESSIBLES / PAS PRÊT POUR BACKTEST.**
Index SEC2024Q1 complet :370321lignes,26SC TO-T initiaux,13accessions distinctes
après co-déposants. Huit premiers dépôts figés date/accession avant documents
ou issues, pas de filtre de survivants ni remplacement. Huit obtenus intégralement.
Six exclus par modalités initiales : trois REITnoncotés/offres partielles,
SVApassivepartielle, THRXcashvariable+CVR, MANUpartielle/proratisation.
Deux candidats de modalités fixes toutesactions : **RYZB62,50USD / SNCE5,75USD**,
pas deux gagnants. Cible identifiée viaSUBJECT COMPANY, pas CIKacquéreur indexé.
Zérobarre locale2023–2024pourlesdeux ; deux sondes AlpacaSIPrawasof=- rendent
5/5séances initiales chacune, dates seules examinées, pas niveaux/prix/rendements.
Issues/échecs, amendements, parcours complets, paiement effectif et identité-prix
restent non qualifiés. Ce n'est ni touteslesfusionscash ni un historiquePIT
de réception locale. Neuf requêtesSECofficielles+deuxAlpaca, aucun achat.
Neuf tests et audittechniquePASS, même assistant, pas revue humaine indépendante.
Aucun PnL, entraînement/LLM/ordre/SQLécrit ou changementproduction/batch.
[Périmètre, huit revues, archives, réserves et suite bornée](arbitrage_acquisitions_cash_faisabilite_20261020.md).

## 2026-10-20 — Tendance multi-actifs SPY/TLT/GLD/DBC, séparée de l'Oracle

**CALCULÉ ET AUDITÉ / RISQUE RÉDUIT, PAS DE SURPERFORMANCE DÉMONTRÉE.**
Règle figée 2 rendements positifs sur 63/126/252 séances, 25 % par ETF actif,
cash sinon, mensuel prochaine ouverture avec quantités de la clôture précédente.
LONG/cash sans levier, 4 000 USD, 2016–30sept2026. Friction principale 10bps par
sens, références même capital/données/frais : conservation initiale et mensuel
équipondérés. Tendance : **7 790,34 USD / +94,76 % / CAGR6,40 % / DD−11,26 %** ;
conservation 11 359,06 USD / CAGR10,20 % / DD−16,69 % ; mensuel 10 969,92 USD /
CAGR9,84 % / DD−18,55 %. Sharpe0,90 contre1,04 ; exposition moyenne65,62 %.
2024/2025/2026partiel tendance +8,77/+12,00/+8,39 %, références meilleures.
Sensibilités0/25bps ne changent pas la conclusion de rendement.

AlpacaSIP2016+, amorçage EODHD274séances, distributions avec droits au
détachement et cash au paiement, aucun double comptage. Doublon DBC2018
dans actions ET cours ajustés Alpaca écarté dans la recherche, appui SEC.
Quatre distributions in-test absentes d'Alpaca reprises d'EODHD, trois sans
corroboration de l'ajustement Alpaca : réserve explicite, pas certification
exhaustive indépendante/PIT. 16tests et neuf rejeux comptables passent.
Pas réplication AQR, ni résultat D1/D10, ni parité live, ni promotion production.
Aucun entraînement/LLM/ordre/SQL écrit/batch modifié ou job laissé actif.
[Protocole, résultats annuels, sources et réserves](multi_actifs_tendance_pilote_20261020.md).

## 2026-10-20 — TOP10 : information nouvelle contre mouvement sans cause identifiable

**FAISABILITÉ AUDITÉE / COMPARAISON CAUSALE BLOQUÉE / PAS DE RÉSULTAT FINANCIER.**
Panneau historique janvier2026 : 200 sélections TOP10, 28 titres, 110 avec
textes/90UNKNOWN ; 418 couples/409 articles, 280 extraits tronqués et zéro
version courante gardée avant décision historique. Revue bornée par SHA256 de
20 présélections et10 témoins, sans prix : 12 candidats factuels, dont six
concernant un autre émetteur. Six candidats propres à CLS/CODI/MLTX/SRPT/WDC,
pas six événements nouveaux indépendants ; disponibilité/novelty non qualifiées.
Panneau récent distinct : TOP10 Oracle16oct disponible17 avant ouverture19,
news jusqu'à clôture19, pas un Oracle19 inventé. SELECT-only des archives
versionnées : cinq couples récents,75 de contexte, cinq reçus temporels valides.
Deux reprises FMC rapprochées d'une annonce déjà archivée le15 ; agrégat
d'analystes FMC et récapitulatif FUN réservés ; association TXG vers article
Terex/TEX, sujet incorrect. Aucun nouveau fait propre au titre pleinement qualifié.
Sept titres sans article récent restentUNKNOWN, pas sans annonce. Donc pas de
groupes « information / pas d'information » comparables aujourd'hui ; pas
preuve d'inefficacité de la piste. AuditPASS, 97tests ciblés dont13nouveaux,
35couples lus au total ; même assistant, pas revue humaine indépendante.
Zéro prix, résultatH10, performance, entraînement, fournisseur/LLM, SQL écrit,
ordre ou changement de production. Aucun job ou suivi automatique laissé actif.
[Sources, comptes, réserves de sujet et suite](news_information_ou_bruit_faisabilite_20261020.md).

## 2026-10-20 — Évaluateur consensus revenus TP10/SL5 préparé

**OUTIL LIVRÉ / CONTRÔLE DE MATURITÉ TESTÉ / AUCUN RÉSULTAT D'EFFICACITÉ.**
349 membres Oracle du 19 octobre conservés, six contextes (deux initiaux,
quatre qualifiés ensuite) séparés ; strict TOP10 = deux cas. Hausse revenus
LONG/baisse SHORT, TP10/SL5 sur dix séances depuis l'ouverture d'entrée,
gaps défavorables à l'ouverture, gap TP plafonné, ambiguïté intrajournalière
SL prioritaire, expiration dixième clôture. Pas de trailing ou optimisation.
Références LONG/SHORT systématiques sur les mêmes cas et sur l'Oracle sans
filtre, avec dénominateurs stricts ; pas de taux agrégé sur un bras incomplet.
Prix/identité/devise/ajustement/actions sur titres/finalité à qualifier : aucun
manifeste automatiquement déclaré valide. SHORT purement contrefactuel,
coûts/prêt/capital non modélisés, pas de PnL portefeuille ou rendement net.
3 490 clés de prix préparées ; audit PASS. Tentative réelle le 20 octobre :
WAITING_H10_MATURITY, zéro prix lu ; maturité le 30 octobre à 20 h UTC,
21 h Paris, puis prix finaux requis. 208 tests ciblés passent, dont 44 nouveaux.
Aucun entraînement, accès fournisseur/LLM, écriture SQL, ordre ou changement
de production. Aucun calcul ni suivi automatique laissé actif.
[Règles, exigences des prix, commandes et réserves](evaluateur_consensus_revenus_h10_20261020.md).

## 2026-10-20 — Qualification publique consensus et nouvelle population annonces SEC

**REVUE BORNÉE TERMINÉE / PREUVES PARTIELLES / PAS DE TEST D'EFFICACITÉ.**
62 réserves de revenus seules examinées : 56 devises de présentation USD,
BILI CNY et STNE BRL, quatre non résolues. Quatre appuis trimestre/revenus
supplémentaires TWLO/FIVN/ENTG/AKAM (2 hausses/2 baisses numériques), soit six
contextes avec DOCN/FUN ; 58 restent réservés. Qualification réalisée maintenant,
pas disponibilité locale historique inventée ni devise Trends certifiée par ligne.
Variations nouvelles très faibles, aucune valeur directionnelle démontrée.

Les 93 cas SEC étaient déjà recalés à sept accords, avec biais de sélection.
Nouvelle cohorte Q1 2024, indépendamment de cette admission future : 610 couples
TOP10/61 séances/32 titres, 51 dépôts candidats, 24 dans le TOP10 de la séance
de réaction, cinq tableaux trimestriels appuyés. Zéro accord admissible ; TAL
a un communiqué daté avant l'acceptation SEC, HLF des comptes mixtes, ASAN/BILL/W
un désaccord entre amélioration comptable et réaction relative négative.
Ce n'est pas un résultat de backtest ni un taux de réussite nul. Trois identités
non résolues, sources et première annonce mondiale non exhaustivement certifiées.

Acquisition publique SEC bornée : SGML initial incomplet aux limites de taille,
complément HTML ciblé avec réserves maintenues. 244 reçus réussis vérifiés,
audit final PASS, 164 tests ciblés dont 26 nouveaux. Aucun ancien dossier
scellé écrasé ; même assistant, pas seconde revue humaine indépendante.
Pas de parcours après entrée, PnL, entraînement, appel LLM/payant, SQL écrit,
ordre ou changement de production. Aucun run de ce travail encore actif.
[Bilan détaillé, archives et suite](qualification_consensus_annonces_sec_20261020.md).

## 2026-10-19 — Revenus seuls : extension séparée au TOP20 % Oracle

**EXTENSION CALCULÉE ET AUDITÉE / UNE COHORTE / H10 IMMATURE.**
Même hypothèse revenus seuls, `0q` et cutoffs avant ouvertures successives,
EPS exclu, TP10/SL5 sur dix séances inchangé. Classement contemporain du
16 octobre : 1 743 scores → **349 titres**, dont TOP10 séparé des 339 suivants.
346 paires présentes, 338 techniquement cohérentes ; **64 variations à nombre
d'analystes inchangé** (36 hausses / 28 baisses), pas 64 trades qualifiés.
233 stables à nombre inchangé, 26 variations avec nombre changé séparées.
Trois paires absentes (TKOMY/HUBG/AA), huit revenus non positifs/manquants
réservés, sans remplacement par les rangs suivants.
692 lignes raccordées à 518 enveloppes déjà archivées, 346/346 paires,
aucune enveloppe invalide. Devise/période appuyées seulement pour DOCN/FUN :
les deux mêmes motifs TOP10, pas d'autres signaux promus. Maturité cohorte
le 30 octobre après clôture ; aucun prix futur, win-rate, AUC ou PnL lu/calculé.
234 tests ciblés passent, dont 23 nouveaux ; audit des 349 rangs/dates : PASS.
Extension exploratoire après examen du TOP10, pas confirmation indépendante.
Aucun appel fournisseur/LLM, entraînement, SQL écrit, changement de production
ou ordre. Ancien pilote scellé conservé.
[Protocole, groupes, réserves et suite](consensus_revenus_top20pct_20261019.md).

## 2026-10-19 — Consensus revenus seuls entre vrais snapshots `0q`

**PILOTE EXÉCUTÉ ET AUDITÉ / H10 IMMATURE / PAS DE RÉSULTAT D'EFFICACITÉ.**
Hypothèse distincte, EPS complètement exclu. Derniers états reçus avant deux
ouvertures NYSE consécutives, même fournisseur/symbole/ancrage/0q, ≥3 analystes
revenus ; nombre inchangé primaire, changé séparé. Dossier figé11–18octobre :
8 570 comparaisons, 1 724 titres et cinq dates d'entrée. 967 variations techniques
à nombre inchangé (479hausses/488baisses), pas 967 signaux qualifiés. 40paires/
80lignes vérifiées contre58enveloppes déjà archivées,80/80retrouvées. Une seule
cohorteTOP10 à classement contemporain : entrée19octobre, Oracle16octobre,
batch H20 `model-factory-20261016180250-3b0515`. Les autres dates ne récupèrent
pas ce classement futur/ancien. Motifs documentés DOCN +0,0217 % (15analystes)
et FUN −0,1736 % (13), pas probabilités de direction. CCOI réservé devise/période,
FMC hors primaire car10→5analystes, six autres stables. Aucun H10 mature :
26octobre au plus tôt dans l'univers,30octobre pour ces deux casTOP10.
211 tests ciblés passent, dont22nouveaux ; audit des8 570comparaisons.
Protocole après les entrées déjà examinées : exploratoire, pas validation
indépendante/ex-ante ni admission live. Aucun prix futur, AUC, win-rate, PnL,
entraînement, appel fournisseur/LLM, SQL écrit, modèle/config/batch modifié ou ordre.
[Protocole, compteurs, maturité et suite](consensus_revenus_observes_20261019.md).

## 2026-10-19 — Retour support EODHD : conventions Trends précisées

**DOCUMENTATION ACTUALISÉE / AUCUN NOUVEAU SIGNAL OU TEST.** Réponse du support
transmise par l'utilisateur, sans en-têtes ni heure de courriel certifiée.
Valeurs en unités complètes, USD confirmé pour DOCN/FUN seulement. Dates
normalisées : FUN 30 juin = clôture du 28 juin ; septembre = Q3 2026, sans jour
fiscal exact inventé. `0q` représente l'état courant de la période, `+1q` un
ancien état conservé quand elle était « prochaine », sans date d'origine.
Ne pas transformer `+1q` en J−7/J−30 ou en vintage historique daté. EPS le plus
souvent non-GAAP mais convention non identifiée par item : réserve maintenue.
Pas d'identité des contributeurs : variation d'agrégat, pas révision prouvée
des mêmes analystes. Une variante revenus seuls entre vrais snapshots serait
une hypothèse distincte, non lancée. Huit dates ne suffisent toujours pas à
une confirmation. Aucun accès base/API, abonnement, modèle, configuration ou
batch modifié ; anciens artefacts scellés inchangés.
[Source transmise, conséquences et réserves](consensus_eodhd_precisions_support_20261019.md).

## 2026-10-19 — Reconstitution SEC des 93 cas « publication + réaction »

**RECHERCHE BORNÉE TERMINÉE / PREUVES PARTIELLES / PAS DE TEST D'EFFICACITÉ.**
68 historiques officiels et 154 soumissions originales : 222 requêtes publiques
SEC réussies, débit limité, collecteur identifié, TLS vérifié, pas de contournement.
93 cas conservés, 70 annexes mentionnant explicitement le trimestre attendu ;
36 séances de réaction avancées, 34 identiques. 65 encore TOP10 au jour recalé.
28 rapprochements des quatre montants d'origine ; 27 dans un même tableau
cohérent, 23 avec prix utilisables et TOP10 recalé. Accord features seulement :
quatre LONG et trois SHORT, aucun trade exécuté ou rendement futur lu.
Les valeurs du 10-Q ne sont jamais supposées connues dans un communiqué plus
ancien sans preuve chiffrée. Source actuelle ≠ réception historique Alpha-Trade.
Audit arithmétique des 27 cas et des nouvelles dates ; 189 tests ciblés passent,
dont 35 nouveaux. Trois des sept accords
présentent un biais de sélection future par la présélection au TOP10 de la date
du 10-Q. Un vrai backtest exigerait une nouvelle cohorte complète choisie au
jour de la réaction, pas la suppression des trois cas. Aucun PnL, entraînement,
LLM, API payante, SQL écrit, modèle/configuration/batch modifié ou ordre.
[Dossier, compteurs, réserves et cohorte causale nécessaire](reconstitution_annonces_financieres_sec_20261019.md).

## 2026-10-19 — Publication financière + réaction prix : faisabilité TOP10

**AUDIT TERMINÉ / 24 ACCORDS POTENTIELS / EFFICACITÉ NON TESTÉE.**
Référence H20 de recherche CatBoost déjà figée, pas les anciens batchs annuels
de production : 6 690 couples TOP10, 669 séances 2024–2026 au 1er septembre,
160 titres. 156 caches SEC raccordés ; faits trimestriels directs par accession,
début/fin/tag/unité, comparatifs du même dépôt, pas fy/fp seuls ni YTD/annuel
assimilé à un trimestre. 1 510 observations, 1 161 numériquement comparables.
93 dépôts coïncident avec le TOP10 à la clôture de la première séance complète
après dépôt, 68 chiffres comparables. Accord revenus/marge et réaction relative
SPY : 10/9/5 cas en 2024/2025/2026, soit 14 LONG et 10 SHORT, 22 dates.
Pas des trades gagnants ni des signaux validés : zéro accession RAW locale
retrouvée pour ces 93 événements historiques, nouveauté et première annonce
non qualifiées. OXM illustre le risque : résultats dans le 8-K du 3 septembre,
10-Q le 4 ; tous deux reçus localement le 14, pas de réception antidatée.
Quatre documents existants contrôlés, pas une revue exhaustive indépendante.
Audit scalaire : 1 161 comparaisons et 93 réactions reproduites ; 154 tests
ciblés passent, dont 29 nouveaux. Les 24 accords
restent sous le seuil de faisabilité de confirmation ; pas d'élargissement
silencieux au TOP20 %. Aucun rendement futur, PnL, entraînement, appel
fournisseur/LLM, SQL écrit, modèle/config/batch modifié ou ordre.
[Protocole, comptes, réserves et reconstitution historique nécessaire](publication_financiere_reaction_prix_20261019.md).

## 2026-10-19 — Qualification bornée DOCN / FUN : collecte fidèle, sens du consensus réservé

**REVUE TERMINÉE / CONTEXTE PARTIEL / AUCUN SIGNAL DIRECTIONNEL PROMU.**
Huit observations 11–18 octobre : 112 lignes normalisées contrôlées contre
16 enveloppes EODHD déjà archivées, 112/112 retrouvées, zéro anomalie technique
sur ce périmètre. 66 observations de master relues ; CIK DOCN/FUN concordants
avec le contexte SEC. Quatre documents publics capturés et scellés, une
expiration Business Wire conservée sans contournement. DOCN : fin de trimestre
confirmée ; FUN : ancrage fournisseur au 30 juin contre trimestre réel au
28 juin, mapping exact de septembre non certifié. L'EPS réalisé non-GAAP du
glossaire ne certifie pas la définition du consensus. Deux horizons différents
coexistent pour une même fin fiscale : ne pas les fusionner ou choisir celui
qui arrange le signal. Devise/échelle, définition EPS et référence des horizons
restaient à préciser par EODHD au terme de cette revue initiale. L'utilisateur
a ensuite envoyé les questions et transmis la réponse ; voir l'actualisation
en tête du registre, sans changement de ce rapport scellé.
Qualification actuelle non antidatée à l'ouverture du 19 ; FMC toujours réservé.
125 tests ciblés passent, dont 12 nouveaux. Aucun rendement, entraînement,
backtest, appel LLM/API de données payante, écriture SQL, modification de
production ou ordre. Recherche publique bornée close, pas un rejet de
l'efficacité des révisions ni une justification d'abonnement supplémentaire.
[Bilan, preuves, limites et questions fournisseur](qualification_consensus_docn_fun_20261019.md).

## 2026-10-19 — Axe information : révisions EODHD réellement observées

**PILOTE DE DONNÉES TERMINÉ / QUALIFICATION ET HISTORIQUE INSUFFISANTS / PAS DE TEST D'EFFICACITÉ.**
GO premier axe professionnel : information économique nouvelle, priorité
aux changements entre collectes, pas une répétition DDR-5/Yahoo/E21.
Lecture seule : 1 778/1 790 titres, huit snapshots 11–18 octobre, 1 170 331 lignes
dans l'univers ; export proche-période de 98 600 lignes. 86 222 paires de période
et d'observation, 86 134 techniquement cohérentes ; zéro pleinement qualifiée
(fiscal/unités non validés, devise absente, statut recherche). Ces marqueurs
par défaut ne prouvent pas que tous les nombres soient faux.
Échantillon sans prix futurs : 102 paires / 204 lignes, 50 enveloppes archivées ;
204/204 items retrouvés et hashes corrects. Pas une certification de tout le corpus.
TOP10 actuel du 16 octobre : CCOI/ICHR/BAND/FUN/UCTT/FMC/MXL/COHR/TXG/DOCN,
batch parcours H20 `model-factory-20261016180250-3b0515`, une seule cohorte récente.
Dernière comparaison de week-end sans changement conjoint. Diagnostic distinct
sur toute la semaine : DOCN EPS/revenus en hausse, FUN/FMC en baisse, BAND annuel
en baisse ; tous restent non qualifiés. FMC : changement important de contributeurs,
pas assimilation automatique à une baisse de guidance. Aucun rendement futur lu,
aucun score directionnel validé, PnL, fit, API fournisseur/LLM, SQL écrit ou ordre.
113 tests passent, dont 29 nouveaux. Pièces publiques de contexte examinées,
sans lever arbitrairement les réserves. H10 éventuel de la cohorte du 19 arrive
au 30 octobre après clôture ; cela ne remplace pas les dates indépendantes requises.
[Périmètre, protocole, chiffres, réserves et suite bornée](axe_information_revisions_observees_20261019.md).

## 2026-10-19 — PCA de trois facteurs ETF contre SPY et secteur

**TERMINÉ ET AUDITÉ / `NO_ROBUST_PCA_ETF_IMPROVEMENT` / PAS DE PROMOTION.**
PCA glissante de trois composantes des onze ETF sectoriels, sur 252 rendements,
puis OLS/OU sur 60 rendements projetés dans la même base à J. Pas une PCA de
toutes les actions. Même périmètre de 1 593 titres et TOP10 Oracle H10, mêmes
seuils, sortie dix séances, perte quotidienne observée au close puis next-open,
coûts de toutes les jambes et stress. Support commun depuis le 4 janvier 2024,
épisodes sélectionnés avant qualité future, pas de données SQL/API nouvelles.
Sur l'univers retenu : **−0,160 / −0,095 / −0,077 %** nets moyens en 2024/2025/2026
(signaux jusqu'au 1er septembre), 12 655 / 12 619 / 8 202 épisodes.
TOP10 : **+0,226 / +0,196 / −0,277 %**, 75 / 35 / 8 épisodes ; coûts stressés
**−0,015 / −0,044 / −0,518 %**, aucun critère de confirmation franchi.
2026 TOP10 : 1 422 des 1 547 couples titre/date à données utilisables demandent
une couverture supérieure au plafond L1=3 ; médiane L1=5,13. Limite de cette
couverture ETF et de son plafond, pas une réfutation générale de la PCA.
170 tests passent, dont 27 nouveaux. Audit `PASS_EXPLORATORY_ETF_PCA_ONLY` :
208 134 lignes de sorties, 542 285 candidats, 3 186 estimations scalaires,
50 préfixes et 162 287 chemins titre/date. Références reproduites sur
140 946 lignes, écart net maximal 1,11e−16. Même assistant, pas une revue humaine
indépendante. Aucun Oracle,
modèle de production, batch, configuration, table SQL ou ordre modifié.
[Protocole, résultats et limites](pca_etf_retour_moyenne_20261019.md).

## 2026-10-19 — Facteur ETF sectoriel contre SPY : même OU, mêmes coûts

**TERMINÉ ET AUDITÉ / `NO_ROBUST_SECTOR_IMPROVEMENT` / PAS DE PROMOTION.** GO pour
la priorité sectorielle, pas de PCA dans ce run. Extraction SELECT-only des onze
ETF déjà en base :10 329 lignes,939 séances chacun2023–septembre2026, aucun
trou/alerte20 % sur ces séries. Mapping courant d'industrie non PIT ;1 593 des
1 790 symboles retenus,195 libellés ambigus exclus, BAR non raccordable et PHYS
sans classification. Aucun changement du mapping/univers de production.
Même prix actions et scores H10 àJ, OLS/OU60, seuils±1,25/±0,5, couverture bêta
fixe, perte observée au close5 % puis sortie next-open, dix séances,8bps/leg
et stress20bps. Support passé/futur titre+SPY+secteur identique ; signaux et
épisodes propres aux bras, pas de prétention causale à trades identiques.
Sur l'univers retenu sans chevauchement, nets moyens secteur
**−0,068/−0,126/−0,042 %** contreSPY **−0,046/+0,001/−0,148 %**.
TOP10 : secteur **+0,222/+0,784/+0,333 %**,129/99/87 occasions, contreSPY
**+0,655/+0,865/−0,105 %**,130/76/40 (2024/2025/2026 au1er septembre).
Point exploratoire positifTOP10, mais tous ses IC95 incluent zéro ; supplément
non confirmé, concentration et coûts fragiles, pas de signal D1/D10 validé.
143 tests passent, dont 28 nouveaux ; référence SPY reproduite sur 352 196 lignes à
écart net zéro, adhésions et sorties identiques. Audit final
`PASS_EXPLORATORY_SECTOR_PROXY_ONLY` : 737 874 lignes de sorties,
369 313 candidats, 6 372 estimations scalaires et 100 préfixes contrôlés.
Seconde implémentation par le même assistant, pas une revue humaine indépendante.
376 candidats inconnus sur369 313 conservés sans remplacement, aucune correction
SQL, API fournisseur/LLM, nouvel entraînement ML, ordre ou modification de production.
[Protocole, facteurs disponibles, bilans, limites et certificats](facteurs_sectoriels_retour_moyenne_20261019.md).

## 2026-10-19 — Méthodes professionnelles : retour à la moyenne résiduel couvert SPY

**TERMINÉ / `NO_ROBUST_RESIDUAL_REVERSION` / PAS DE PROMOTION.** GO pour rechercher
des méthodes professionnelles puis tester avec l'application. Revue Man AHL,
Robeco, Avellaneda–Lee et AQR ; essai distinct d'E17 momentum H120 et d'E10
pullback : résidus OLS contreSPY, OU glissant60, entrée s hors±1,25 au prochain
open, paire couverte par bêta fixé, sortie normalisation±0,5/invalidité du modèle/
perte quotidienne5 %, exécutée au prochain open, au plus dix séances. Adaptation
mono-facteur, **pas réplication** sectorielle/PCA ou des rendements d'un fonds.
Univers tradable1 790 et TOP10 H10 àJ, 2024–2026 jusqu'au1er septembre ; archives
de prix normalisées, réserves DD/TOELY conservées, coût8bps par montant exécuté
sur les deux jambes et stress20bps, emprunt hypothétique0,3 %.
199 242 signaux,199 051 chemins qualifiés ; épisodes sans chevauchement choisis
avant qualité future, sans remplacement : univers complet14 913/14 734/8 668,
nets moyens **−0,037/−0,005/−0,177 %** ; TOP10 **153/87/47**, nets moyens
**+0,598/+0,683/−0,169 %**. Tous les intervalles95 % primaires incluent zéro.
Frais absorbent la faible moyenne brute2024/2025 de l'univers ;2026 brute déjà
négative. Diagnostic LONG TOP10 **+0,527/+1,600/+0,341 %**, mais106/49/23 cas,
IC2026 incluant zéro : pas de candidat LONG validé ou de nouveau filtre promu.
Risques en gap conservés, quatre grandes pertes2026 recoupées avec les opens
SIP déjà archivés, aucune suppression de titre. Pas de rendement annuel de
capital, de marge/locate/dividendes historiques reconstitués ou de parité broker.
**115 tests passent**,19 nouveaux ;796 204 lignes,5 370 estimations scalaires et
58 préfixes vérifiés, audit `PASS_EXPLORATORY_ADAPTATION_ONLY`. Aucun SQL,
API fournisseur/LLM, nouvel entraînement ML, ordre ou changement de production.
[Sources, adaptation, résultats, coûts et limites](methodes_professionnelles_et_test_residuel_20261019.md).

## 2026-10-19 — TOP10 H10, première cassure intraday des bornes de J

**TERMINÉ / NÉGATIF SUR LE PÉRIMÈTRE QUALIFIÉ / PAS DE PROMOTION.** Nouveau GO
sur les barres 5m SIP déjà en base : TOP10 H10 figé à J, première clôture J+1
hors des bornes de J, entrée à la barre suivante, TP10/SL5, dix séances maximum,
sans trailing ou retournement. Pas la précédente confirmation quatre clôtures.
Snapshot SQL READ ONLY de650 036 barres ; aucune collecte ni écriture SQL.
2024 non testable faute d'intraday ; 1 504/2 500 fenêtres2025 et1 022/1 670
fenêtres2026 qualifiées (signaux jusqu'au1er septembre), sans remplacer les exclus.
2 022 cassures : **−0,906 % / −0,761 % nets moyens par trade**, gagnants
**32,12 % /31,94 %** en2025/2026. LONG **−0,199/−0,630 %**, SHORT
**−1,592/−0,901 %**. Sans chevauchement,248/186 occasions : **−0,493/−1,820 %**.
Contrôle toujours LONG aux mêmes heures **+0,422/+0,050 %**, sans preuve de
rentabilité robuste ; inversion de la cassure non validée non plus.
Gaps adverses conservés : stop5 % n'est pas une perte garantie à5 %, notamment
MP/SRPT, ouvertures recoupées avec les archives daily. Couverture partielle,
coûts hypothétiques, années déjà explorées, pas de rendement annuel de capital.
**96 tests passent**, dont22 nouveaux ; second calcul de13 140 lignes,
audit `PASS_EXPLORATORY_PARTIAL_COVERAGE`. V2 : même snapshot, corrections
techniques de contacts décimaux et d'horodatage intrabar, aucun rendement de
la politique cassure changé. Aucun modèle, batch, ordre ou configuration modifié.
[Règles, couverture, contrôles et résultats](oracle_top10_cassure_intraday_tp10_sl5_20261019.md).

## 2026-10-19 — Sortie première clôture pour départ raté, TOP10 LONG

**TERMINÉ / RÈGLE NON RETENUE / PAS DE PROMOTION.** Nouveau GO après audit des
états : MFE de séance d'entrée strictement<+2,202691127 % (borne2024 exacte),
sortie au prochain open seulement ; pas de nouvelle décision les soirs suivants.
Même TOP10 H10 confirmé quatre clôtures, entréeJ+3, TP10/SL5, dix séances sans
trailing. Les protections intraday et au prochain open restent prioritaires.
708 occasions identiques ; contrôle sortir tous les survivants après première
clôture, capital non réinvesti et adhésion indépendante figée sur le lifecycle
natif. Moyennes référence **+0,915/−0,756/−0,415 %** contre règle
**+0,747/−0,982/−0,470 %** (2024/2025/2026 jusqu'au1er septembre).
141 pertes atténuées mais81 gains amputés, dont40 gagnants devenus non positifs ;
les gains abandonnés compensent plus que les pertes évitées. Sans chevauchement,
écarts **+0,588/−0,176/+0,013 point** : pas d'amélioration transversale.
Contrôle de durée +0,033/−0,496/−0,710 %, également non robuste. La feature avait
déjà été choisie après observation des trois années : pas de holdout vierge,
ni de seuil réajusté sur ces résultats. Pas un rendement annuel de capital.
**157 tests passent**, 708 références reproduites et2 124 lignes vérifiées,
audit `PASS_EXPLORATORY_REPLAY_ONLY`. Aucun SQL/API/LLM, entraînement, ordre
ou changement de production ; essai clos sans nouvelle optimisation automatique.
[Règle, pertes évitées, gains sacrifiés et contrôles](oracle_top10_sortie_depart_rate_20261019.md).

## 2026-10-19 — Audit des états quotidiens TOP10 LONG avant nouveau KEEP/EXIT

**AUDIT TERMINÉ / PAS D'ENTRAÎNEMENT / PAS DE NOUVELLE POLITIQUE.** Même cohorte
Oracle H10 TOP10 confirmé jusqu'àJ+2, entréeJ+3, TP10/SL5, dix séances sans
trailing. 708 positions,536 avec1 835 clôtures observables ; les172 sorties de
séance d'entrée ne sont pas récupérables par une décision au close. Vingt
features prix/volume/SPY et état de position, deux cibles avantage de sortir au
prochain open contre conserver jusqu'à sortie native ou au plus trois séances,
sans annuler les protections. Poids1/position, contrôles sans chevauchement,
tertiledécouverte2024 purgée (777 états/190 positions), années2025/2026 déjà vues.
Un seul couple passe le screen descriptif initial : MFE observée<+2,203 %,
cible trois séances. AUC sans chevauchement0,730/0,679/0,548 ; avantages d'états
+1,540/+1,084/+0,625 points mais intervalles2025/2026 incluant zéro,21 positions
seulement en2026. Après première clôture, avantage −1,028/−2,428 points en2025/2026
sur15/4 positions ; contrôle d'âge exact négatif2025. Hypothèse faible de départ
raté, pas détection stable d'inversion. Volume, reculATR et trajectoires relatives
ne passent pas les contrôles transversaux. Pas de critère qualifié pour entraîner
un nouveau modèle maintenant, ni de PnL d'une politique de sortie calculé.
**145 tests passent**, 708 issues natives et1 835 labels vérifiés,93 contrôles
de préfixe, audit `PASS_EXPLORATORY_AUDIT_ONLY`. Aucun SQL/API/LLM, entraînement,
ordre ou changement de production. Suite uniquement après nouveau GO borné.
[États, critères, causalité et réserves du candidat](oracle_top10_suivi_quotidien_audit_20261019.md).

## 2026-10-19 — TOP10 confirmé, grille TP/SL fixes et trois variantes ATR20

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** Même TOP10 H10 et confirmation
quatre clôtures J−1..J+2, entrée J+3, dix séances entrée comprise, pas de trailing.
16 profils fixes TP5/10/15/20 × SL3/5/7/10 et trois ATR20 (stop1/1,5/2×ATR,
SL borné3–10 %, TP=2×SL), ATR connu au closeJ+2 puis seuils fixés au fillJ+3.
Choix sur2024 uniquement, vérification2025/2026 sans réoptimisation ; ces années
restent historiquement déjà examinées, pas un holdout vierge.
Choix LONG2024 TP10/SL10 : **+1,699/−0,764/+0,161 %** par occasion
(2024/2025/2026 jusqu'au1er septembre), sans chevauchement
**+1,518/−0,390/−0,627 %**. ATR LONG1× **+1,070/−0,320/+0,089 %**,
1,5× **+0,524/−0,155/+0,441 %**, 2× **+0,717/−0,198/+0,693 %** ; sans
chevauchement tous négatifs2026. TP15/SL7 apparent **+0,840/+0,063/+0,013 %**
découvert rétrospectivement dans la grille, mais contrôle2026 −0,783 % : pas
de réglage robuste à promouvoir. Tous les profils SHORT et communs combinés
négatifs chaque année ; stops ATR plus larges aggravent les SHORT2026.
Choix commun2024 TP5/SL7 : −0,146/−0,882/−1,044 % ; choix par sens2024 combinés
+0,420/−1,017/−0,414 %. Taux gagnant accru ne suffit pas à la rentabilité.
6 690 couples identiques, aucun exclu par l'ATR, référenceTP10/SL5 reproduite
sur13 380 lignes ; **254 220 sorties vérifiées en scalaire**, **133 tests passent**,
audit `PASS_EXPLORATORY_ONLY`. Moyennes par occasion, pas rendements annuels
de capital. Aucun SQL, entraînement, API/LLM, ordre ou changement de production.
[Grille fixe/ATR, sélection2024, réserves et contrôles](oracle_top10_confirmation_audit_tp_sl_atr_20261019.md).

## 2026-10-19 — TOP10 H10, quatre clôtures jusqu'à J+2, entrée J+3, TP10/SL5

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** Même TOP10 figé à J et mêmes
modèles H10 annuels que le test trois clôtures. LONG si C(J−1)<C(J)<C(J+1)<C(J+2),
SHORT si strictement décroissant, sinon abstention. Entrée openJ+3 après la
confirmation, dix séances entrée comprise, expiration closeJ+12, TP10/SL5,
sans trailing, mêmes frictions et gaps non plafonnés. Aucun réentraînement.
LONG **+0,915/−0,756/−0,415 %** par occasion en 2024/2025/2026 (signaux jusqu'au
1er septembre), gagnants **43,10/32,16/32,13 %** ; SHORT
**−1,296/−1,301/−2,034 %**, gagnants **31,07/28,29/23,40 %**.
Combiné **−0,396/−1,052/−1,159 %**, sans chevauchement
**−0,061/−0,690/−1,165 %**. Confirmation limitée à 22–24 % des occasions,
contre 48–52 % précédemment. Référence tous LONG avec même entréeJ+3
**+0,259/+0,358/+0,094 %**. Contrôle descriptif trois clôtures mais même entréeJ+3 :
combiné −0,404/−0,752/−0,537 %, pas de gain transversal de la quatrième clôture.
6 690 couples d'origine tous qualifiés ; **118 tests passent**, 6 690 confirmations
et 13 380 sorties vérifiées en scalaire, audit `PASS_EXPLORATORY_ONLY`.
Pas rendement annuel de capital ; prix/OST et PIT hérités restent réservés.
Aucun API/LLM, SQL, entraînement, ordre ou changement de production.
[Règle quatre clôtures, résultats et contrôles](oracle_top10_confirmation_quatre_seances_tp10_sl5_20261019.md).

## 2026-10-19 — TOP10 H10, confirmation trois clôtures J−1/J/J+1, TP10/SL5

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** Périmètre précisé par
l'utilisateur : dix premiers scores du nouvel Oracle amplitude H10 à J, pas
TOP20 %. LONG si clôtures ajustées J−1<J<J+1, SHORT si strictement décroissantes,
sinon abstention. Entrée openJ+2 après confirmation ; dix séances entrée comprise,
expiration closeJ+11, TP10/SL5 sans trailing. Référence mêmes titres/entrée/risque,
sans confirmation ; mêmes frais et gaps non plafonnés. 2024/2025 et signaux2026
jusqu'au1er septembre, sans reclassement/remplacement par le futur.
LONG confirmés **+0,046/−0,679/−0,097 %** par occasion,
**37,31/32,22/34,90 %** gagnants ; SHORT **−1,208/−1,107/−0,936 %**,
**30,82/30,10/30,51 %** gagnants. Sens combinés **−0,669/−0,904/−0,500 %**.
Référence tous LONG sans filtre **+0,110/+0,232/+0,127 %** ; confirmation de sens
moins bonne que tous LONG sur les mêmes couples confirmés. Sans chevauchement,
combiné −0,381/−0,630/+0,072 % : pas de résultat transversal.
6 690 couples, tous qualifiés, 48–52 % confirmés ; stop5 dépassable par gap.
**105 tests passent**, 13 380 issues vérifiées par calcul scalaire ; audit
`PASS_EXPLORATORY_ONLY`. Pas rendement annuel de capital, pas nouveau modèle
directionnel. Aucun entraînement, API/LLM, SQL ou changement de production.
[Règles, résultats LONG/SHORT, contrôles et risques](oracle_top10_confirmation_trois_seances_tp10_sl5_20261019.md).

## 2026-10-19 — Prix suspects puis véritables modèles parcours H10 contre H20

**TERMINÉ / SIX MODÈLES DE RECHERCHE / PAS DE PROMOTION.** Qualification bornée
des ruptures KLAC/DD/MLI/SBS : 22 lectures SIP archivées, 3 420 lignes normalisées
dans une copie seulement ; base DD/Qnity et TOELY réservées, features après
rupture exclues sans supprimer globalement les symboles. Sensibilité des anciens
LONG TOP20 % filtrés inchangée ; pas de correction SQL ni de preuve absolue
indépendante pour les 711 anciennes lignes DD remises à l'échelle uniforme.
Deux modèles d'amplitude dédiés H10/H20 par année 2024/2025/2026, CatBoost figé,
mêmes 172 features, mêmes lignes, 504 dates train/126 validation et embargo21.
TOP20 % prédit avant qualité future ; TP10/SL10, LONG et SHORT séparés,
durées10 et20 pour séparer effet modèle et effet durée. Ce n'est pas un nouveau
classifieur de direction ou une reproduction des anciens scores annuels.
LONG durée10 H10 : **+0,054/+0,425/+0,112 %**, H20
**+0,078/+0,400/+0,083 %** par occasion (2024/2025/2026 au 1er septembre).
Durée20 H10 : +0,196/+0,551/+0,112 %, H20 +0,222/+0,510/+0,062 %.
SHORT moyens tous négatifs. TOP20 % communs à 95,1–95,6 % ; précision vrai TOP20 %
d'amplitude environ46–50 % pour les deux modèles, sans gain directionnel robuste.
Supplément LONG face à tous les titres observables non confirmé dans les trois
années ; faibles différences H10/H20 changent de signe après2024. Couverture
exécution ≥98,9 %, mais précision amplitude2026 seulement87,7 % des sélections
qualifiées pour le vrai H20 (vingt dates sous le seuil de couverture95 %),
sans remplacement des manquants. Moyennes après frictions hypothétiques,
pas des rendements annuels de capital ou une décision live.
**91 tests passent**, audit `PASS_EXPLORATORY_ONLY` ; modèles `serving_ready:false`.
Aucun SQL/ordre/LLM, changement de modèle, batch ou configuration de production.
[Prix, protocole, résultats, couvertures et contrôles](oracle_h10_h20_prix_et_comparaison_20261019.md).

## 2026-10-19 — Même Oracle H20, sorties H5/H10/H20 sans réentraînement

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION / RÉSERVE PRIX.** GO pour comparer
la durée avant un éventuel nouveau modèle. Deux périmètres : TOP20 % Oracle et
univers tradable complet (1 790 titres) ; mêmes couples 2025–2026 et adhésions
H20 historiques par titre/sens figées, TP10/SL10 et TP10 sans SL. Entrée open J+1,
sortie close-N si aucun seuil, N=5/10/20 ; mêmes frais et gaps/collisions. Contrôle
sans chevauchement conserve les mêmes épisodes espacés sur vingt séances.
LONG TOP20 % SL10 : H5 +0,34/−0,19 %, H10 +0,92/−0,41 %, H20 +1,25/−0,26 %
(2025/2026). Sans SL : H5 +0,75/+0,13 %, H10 +1,66/+0,52 %, H20 +3,11/+1,10 %.
Univers complet LONG SL10 : H5 −0,03/−0,04 %, H10 +0,18/+0,03 %, H20 +0,30/+0,28 %.
SHORT filtrés restent négatifs aux trois durées ; pas de choix LONG/SHORT stable.
Sans chevauchement TOP20 % LONG sans SL, H10 +2,41/+0,81 % contre H20
+3,69/+0,36 % : pas d'horizon dominant transversal. Direction terminale LONG du
filtre sans SL en 2026 : 49,50 % à H5, 49,35 % à H10, 50,77 % à H20 ; distincte du
taux gagnant avec TP. Durée courte limite certaines pertes mais coupe des profits.
Moyennes par occasion après frictions supposées, pas des rendements annuels de
capital ; capital recyclé et réentrées H5 supplémentaires non simulés.
83 tests passent ; parité exacte H20 sur 2 964 136 lignes et audit des douze
combinaisons. Aucun SQL/API/LLM, entraînement, changement modèle/production ou
ordre. Aucun Oracle H10 dédié testé ; ne pas confondre cette comparaison de sortie
avec l'apprentissage d'une nouvelle cible ou une preuve d'impossibilité à H10.
[Résultats, conventions, risques et contrôles](oracle_comparaison_detention_h5_h10_h20_20261019.md).

## 2026-10-19 — TOP20 % Oracle contre univers complet : TP10/SL10 et TP10 sans SL

**DEUX PÉRIMÈTRES TERMINÉS / EXPLORATOIRE / RÉSERVE PRIX / PAS DE PROMOTION.**
TOP20 % des scores Oracle prédits, et non vingt titres ou TOP10 ; score DESC,
symbole ASC, `ceil(0,20 × N scorés)`, classement avant qualité future, sans
remplacement. 350–358 titres par séance, univers complet 1 790 titres. Modèles
annuels parcours CatBoost 437ed1/102eca/bc35a7 ; scores SQL existants et lineage
lus en transaction SELECT-only, rangs archivés reproduits sur les 689 séances.
2024 historique ; évaluations 2025–2026 matures jusqu'au 1er septembre 2026.
Filtre titre/sens causal inchangé, appris dans chaque périmètre et séparément
pour chaque protection ; références tous LONG/SHORT et contrôle filtre appris
sur l'univers complet puis intersecté TOP20 % fournis.
LONG TOP20 % filtrés SL10 : +1,25/−0,26 % par occasion, 58,58/50,30 % gagnantes.
Sans SL : +3,11/+1,10 %, 71,76/65,20 %, mais contrôle sans chevauchement
+3,69/+0,36 %, contre tous TOP20 % LONG +1,32/+1,29 % : supplément non confirmé
en 2026. Sens choisi combiné : SL10 −0,37/−0,83 %, sans SL −0,13/+0,06 % ;
sans chevauchement ce dernier devient −0,29/−1,42 %. Pas de signal stable.
Les résultats univers complet TP10 v2 sont réutilisés à l'identique et vérifiés.
Sans SL, baisses contraires >10 % avant barre de sortie dans au moins
34,53/47,11 % des LONG retenus ; pertes et prix/OST suspects restent réservés.
57 tests passent. Aucun nouvel entraînement, changement modèle/production,
appel fournisseur/LLM, écriture SQL ou ordre. Ce sont des moyennes nettes après
frictions hypothétiques, pas des rendements annuels de capital.
[Périmètres, résultats détaillés, risques et contrôles](oracle_top20pct_et_univers_complet_tp10_20261019.md).

## 2026-10-19 — Univers complet : TP10/SL10 et TP10 sans SL

**DEUX TESTS TERMINÉS / EXPLORATOIRES / RÉSERVE PRIX / PAS DE PROMOTION.**
Même 1 790 titres et mêmes fenêtres qualifiées que TP20/SL7. 2024 historique,
sélections mensuelles causales en 2025–2026, règles de confiance inchangées ;
labels et adhésions propres à chaque protection. « Juste TP10 » = sans SL,
expiration close20 incluant l'entrée J+1, sans trailing ni moteur de marge réel.
LONG TP10/SL10 : 52,56/53,01 % d'occasions gagnantes, moyennes nettes
+0,30/+0,28 %. LONG sans SL : 58,89/61,18 %, +0,87/+0,92 %. SHORT restent
négatifs ; sens choisi combiné : −0,69/−0,54 % avec SL10, −0,60/−0,28 % sans SL.
Moyennes par occasion après frictions hypothétiques, pas rendements annuels
de portefeuille. Contrôles sans chevauchement et ancienne sélection figée inclus.
Supplément LONG face à tous LONG incertain dans les deux années ; pertes et
mouvements contraires plus grands sans SL. Second semestre 2026 LONG négatif.
Croisement secondaire TOP10, sans SL, LONG : 454/661 occasions, 73,57/80,94 %
gagnantes, +3,42/+4,50 % ; sans chevauchement +2,34/+2,41 %, pas de supplément
robuste du filtre face à tous TOP10 LONG (+3,18/+2,57 % sans chevauchement).
À conserver comme résultat exploratoire de sortie, pas preuve directionnelle
ou autorisation live sans SL. Prix/OST suspects hérités non corrigés.
50 tests passent ; v2 corrige les touches exactes à ±10 % (tolérance numérique
relative 1e−12), v1 conservé mais supplanté. Aucune modification de modèle,
donnée SQL, univers/batch de production, aucun API/LLM, entraînement ou ordre.
[Protocoles, chiffres LONG/SHORT, risques et contrôles](univers_tradable_tp10_sl10_et_sans_sl_20261019.md).

## 2026-10-19 — Univers tradable complet : confiance historique par titre/sens

**TERMINÉ SUR LES 1 790 TITRES / EXPLORATOIRE / RÉSERVE PRIX / PAS DE PROMOTION.**
Fichier `config/univers_batch/univers_filtred_tradable.txt`, aucun filtre Oracle
dans le test principal. 1 233 310 couples séance/titre examinés, 1 192 036
fenêtres qualifiées ; chaque titre couvert chaque année. Historique initial
2024 ; sélection mensuelle 2025–2026 avec les mêmes règles que le test TOP10 :
minimum huit fenêtres sans chevauchement, maturité avant sélection, Wilson90,
net positif/supérieur au global et stabilité des deux moitiés. TP20/SL7, mêmes
coûts hypothétiques, sans apprentissage d'un nouveau prédicteur.
525 titres distincts effectivement retenus, 77–226 qualifiés par mois.
LONG qualifiés : TP-first 17,14/16,75 % mais seulement 41,07/34,98 % d'occasions
positives, moyennes nettes +1,01/−0,04 % en 2025/2026. SHORT : −1,99/−1,53 %.
Sens choisi combiné : moyennes **−0,33/−0,58 % par occasion**, contrôles sans
chevauchement **−0,35/−0,44 %**. Pas des rendements annuels de portefeuille.
Croisement secondaire avec TOP10 original : 986/775 occasions, moyennes
−0,33/−1,45 %, pas d'avantage stable par rapport au TOP10 tous LONG.
96 lignes de pertes extrêmes sur douze symboles signalées, dont KLAC à échelles
apparemment incohérentes : prix/OST non indépendamment qualifiés, aucune
correction ou suppression SQL. Omission ex post des deux lignes extrêmes
sélectionnées en 2025 : moyenne combinée reste négative ; aucune en 2026.
Univers courant survivant, sélections multiples non corrigées, années déjà
explorées : pas d'univers définitif « titres faciles » démontré par cette règle.
31 tests passent ; parité sur 13 356 parcours TOP10 et 8 316 lignes avec coûts ;
empreintes et 1 790 parties vérifiées. Aucun SQL/API/LLM, entraînement, ordre,
changement d'univers, modèle, batch ou production.
[Périmètre complet, résultats, couverture et réserve prix](univers_tradable_complet_confiance_directionnelle_20261019.md).

## 2026-10-19 — TOP10 : univers de confiance causal par titre/sens

**TERMINÉ / EXPLORATOIRE / PAS D'UNIVERS PROMU.** 2024 historique initial,
sélection mensuelle 2025–2026 sur 504 séances antérieures ; maturité complète
strictement avant sélection, minimum huit fenêtres sans chevauchement par
titre/sens, borne Wilson90 TP supérieure au global passé, moyenne nette
positive/supérieure au global et stabilité des deux moitiés historiques.
TP20/SL7 inchangés, frictions hypothétiques et emprunt SHORT ; pas de nouveau
prédicteur directionnel ni GPT. Aucun remplacement hors des dix rangs Oracle.
2025 : 158 occasions retenues (LONG MXL/APP, SHORT TXG/GPRE), TP-first 36,08 %,
moyenne nette par occasion +2,59 % ; mais seulement quinze fenêtres sans
chevauchement, TP 3/15 et moyenne −2,82 %. Second semestre : dix-sept occasions,
zéro TP, moyenne −7,14 %. 2026 : 56 occasions MXL LONG seules, TP 35,71 %, moyenne
+2,40 % ; seulement cinq fenêtres, trois TP. Pas de généralisation diversifiée ;
2026 équivaut à toujours LONG sur MXL. Couverture 6,32/3,38 % des occasions,
majorité des autres titres insuffisamment documentés, pas jugés « mauvais ».
Différences appariées 2025 incertaines ; années déjà explorées, pas de holdout
nouveau. Moyennes par occasion, **pas rendements de portefeuille**.
23 tests passent ; deux calculs mêmes adhésions/sélections ; aucune connexion
SQL/API/LLM, aucun entraînement, ordre, modification d'univers/modèle/batch.
[Protocole, contrôles de chevauchement et résultats](top10_univers_confiance_par_titre_20261019.md).

## 2026-10-19 — TOP10 Oracle : liquidité, gaps et parcours TP20/SL7

**TERMINÉ / EXPLORATOIRE / PAS DE FILTRE PROMU.** Trois modèles annuels parcours
du 14 octobre, dix rangs originaux ; 6 678 occasions matures, LONG et SHORT
séparément, sans modèle directionnel ni GPT. Entrée J+1 open, vingt séances
incluant l'entrée, TP20/SL7 fixes, collisions OHLC stop-first et gaps au prix
d'ouverture. Pas un portefeuille ni une mesure de rendement économique.
Filtre figé ADV20 ≥20 M$ + max gap absolu20 <7 % : taux TP-first LONG par date
21,39→21,12 % / 29,84→29,86 % / 27,03→26,71 % en 2024/2025/2026 ; ne conserve
que 35,00 / 32,32 / 38,72 % des occasions. SHORT : 11,67→12,30 % /
14,32→14,48 % / 18,06→18,59 %, mais intervalles appariés du combiné incluant
zéro, effets individuels instables. Parmi les LONG finalement haussiers,
37,52 / 41,15 / 52,07 % avaient été stoppés avant TP. Observation future,
pas signal causal d'entrée ni justification d'élargir le stop.
Capitalisation small/mid/large non testable proprement : aucun snapshot
admissible avant les occasions matures ; pas de substitution par les valeurs
actuelles. 2026 mature jusqu'au 1er septembre, observation jusqu'au 30 septembre.
22 tests passent ; SQL lecture seule pour l'export borné, aucun API/LLM,
entraînement, ordre, changement de modèle/batch ou écriture SQL.
[Protocole, couverture et résultats](top10_liquidite_gaps_parcours_tp20_sl7_20261019.md).

## 2026-10-19 — TOP10 Oracle parcours tous SHORT, TP20/SL7

**CALCULS TERMINÉS / EXPLORATOIRE / RÉSERVE RÉGIME 2025 — aucune promotion.**
Trois modèles annuels parcours CatBoost du 14 octobre, univers courant 1 790 ;
dix rangs d'amplitude originaux, pas de tête SHORT ni GPT, aucun entraînement.
Capital 4 000 USD par cohorte, levier d'entrée ≤2, TP20/SL7 au fill, trailing OFF,
expiration à l'open après vingt séances détenues, quantités entières et contrôles
portefeuille natifs. Emprunt hypothétique 0,3 %/an ; indemnisation des dividendes
non exhaustive, shortabilité historique non certifiée.
2024 : **−29,29 %, 2 828,29 $, DD −38,33 %, 31 gagnants/78 perdants** (queue
d'expiration jusqu'au 03/02/2025 ; au 31/12 : −27,47 %). 2025 : **+8,20 %,
4 328,16 $, DD −19,28 %, 9/16**, mais seulement 25 entrées jusqu'à mars :
177 séances NORMAL avec quota SHORT nul, transition défensive incapable de
sortir avec compteurs de calme/sortie transmis à zéro. **Pas un résultat continu
2025 validé** ; aucune correction du moteur appliquée. 2026 au 30/09 :
**−35,57 %, 2 577,06 $, DD −42,57 %, 25/67**, quatre positions ouvertes valorisées.
Expositions moyennes 0,82× / 0,19× / 0,44×. 504 empreintes revérifiées, deux
replays reproduisent les mêmes equity/trades/DD ; 18 tests préalables passent.
Pas d'API/LLM, SQL, broker, changement de modèle ou de batch de production.
[Protocole, chiffres et anomalie de régime](oracle_top10_short_tp20_sl7_20261019.md).

## 2026-10-19 — premier bilan TOP10 Oracle et consensus collecté le 11 octobre

**DESCRIPTIF / H20 NON MATURE — aucune promotion.** Classement du vendredi
9 octobre repris du run archivé (le 11 était dimanche), ancien modèle
`model-factory-20261003082853-e98332`, dix rangs originaux sans sélection GPT.
Consensus du 11 reçu avant l'ouverture du 12, prix observés jusqu'au 16 : cinq
séances. EPS J−7 amélioré : une hausse sur cinq ; dégradé : une baisse sur trois.
Concordance signe/cours 2/8 ; solde des révisions 30 j : 2/9. Neutres exclus,
aucun seuil optimisé. Pas un verdict définitif sur le consensus, ni une mesure
de l'exactitude de l'EPS réalisé, ni une validation D1/D10. Réserves fiscales/
unités maintenues ; compteur baisses 7 j absent des dix payloads, non imputé.
Hauts/bas du parcours conservés, H20 au 6 novembre ; archive et prix de référence
contrôlés. Source prix unique, SPY/opérations sur titres connus examinés.
Aucun API/LLM, SQL, modèle, batch ou ordre modifié ; 11 tests ciblés passent.
[Bilan et prix par titre](oracle_top10_consensus_11oct2026_premier_bilan.md).

## 2026-10-19 — contexte LLM frais : calendrier, SEC, prix/volume et fondamentaux

**Livraison technique, pas une validation D1/D10.** Protocole v7 pour les futures
analyses GPT/DeepSeek, local/Web : limites de réception/publication propres à
chaque famille, dernier cours de séance clôturée obligatoire, extraits bornés,
preuves provisoires distinguées des sources directionnelles recevables. SEC :
CIK/URL/hash/fin de collecte, retrait des en-têtes SGML et extraction EX-99 utile.
Pas de tables brutes, pas de promotion SQL des consensus/news non qualifiés.
DeepSeek exclut les pages périmées/non datées avant analyse ; GPT Web impose
le filtre dans le prompt puis au contrôle de réponse. Archives v4/v5/v6 préservées.
Aperçu en base, lecture seule, sélection archivée de dix titres du 16 octobre :
10 calendriers/prix, consensus provisoire, 48 news sur neuf titres, un dépôt SEC
recevable (FMC), zéro fondamental passant tous les critères sur ce périmètre.
Aucun appel LLM/fournisseur payant, entraînement, ordre ou écriture SQL.
**802 tests passent**, dont 53 contrôles v7 dédiés ; aucune performance
économique ou amélioration directionnelle revendiquée.
[Contrat, réglages et bilan](llm_preuves_fraiches_20261019.md).

## 2026-10-19 — DeepSeek Web natif, sans relais GPT

**Livraison technique, pas une validation directionnelle.** Pour les nouvelles
analyses `provider: deepseek` / `analysis_mode: web_search`, Search/Fetch DeepSeek
remplace la recherche OpenAI ; analyse par le modèle DeepSeek configuré, même
consensus local et même objectif de tendance LONG/SHORT/ABSTAIN. Clé DeepSeek seule,
appels Web bornés, aucun fallback GPT ni retry payant automatique. Requêtes,
réponses, dates et consommation archivées dans les tables LLM existantes ; URL
inventées et dates modifiées rejetées. Anciens runs hybrides v4/v5 revalidables,
pas réécrits ni renvoyés aux API. GPT Web et les deux modes locaux conservés.
Configuration actuelle GPT/local non changée. **749 tests de régression passent**,
dont les contrôles de relecture v5/v6 et du préflight sans OpenAI.
Tests simulés uniquement : aucun
appel fournisseur payant, ordre, modèle ou donnée SQL de production modifié.
[Fonctionnement et réglages](llm_modes_consensus.md#recherche-native-deepseek--19-octobre-2026).

## 2026-10-18 — anciens avantages et complémentarité sur le TOP10 Oracle parcours

**TERMINÉ / `NO_STABLE_TOP10_COMPLEMENTARITY` — aucune promotion.**
Réévaluation locale des anciens scores/règles : dix bras plus douze scores E23
descriptifs, six combinaisons figées, trois retenus parmi les dix originaux.
1 049 dates 2022–2026, dont 1 027 complètes / 3 081 sélections comparables.
D10 parcours seul : D10 **30,57 %**, D1 **23,79 %** ; combinaison équipondérée
avec anti-D1 CatBoost : **31,61 % / 22,07 %**, contre **29,11 % / 25,61 %**
pour les trois premiers Oracle. Petit gain moyen, dégradation des deux critères
en 2024 ; zéro recette passe les gates. Confirmation 2023–2026 : +0,51 point
D10, −1,67 point D1 ; p Holm 1,000 / 0,936. Momentum/ATR n'ajoute pas de gain
stable. E17 seulement 85 dates complètes, inconclusif sur toute la période.
E23 : 42 dates complètes seulement, population filtrée sur labels futurs,
descriptif interdit comme entrée de recette ; 18 archives OOF absentes non
recréées. Aucune conclusion globale contre tous les anciens modèles.
Références à effectif égal, couverture/PIT distingués ; sources bloquées non
restaurées. Aucun entraînement, SQL, fournisseur/LLM, ordre, PnL ou modèle servi
modifié ; 87 tests ciblés passent et empreintes revérifiées. Dossier v2 de
référence, v1 conservé (sélections identiques, correction Holm renforcée).
Pas de nouveau holdout indépendant, pas de performance économique démontrée.
[Protocole et bilan](complementarite_anciens_signaux_top10_20261018.md).

## 2026-10-18 — TOP10, CatBoost trois classes et score P(D10)−P(D1)

**TERMINÉ / `NO_STABLE_CATBOOST_TOP10_DIRECTION` — aucune promotion.** Un seul réglage CatBoost MultiClass figé
(profondeur 3, 200 itérations, L2 10), 24 features J/variations 5–10 séances,
train/test sur les dix candidats Oracle causaux uniquement. D1, D2–D9 et D10
présents ; score de classement P(D10)−P(D1). Témoin logistique aux mêmes trois
classes pour isoler le non-linéaire, ancienne logistique D10/rest reproduite,
ordre Oracle conservé. Shortlist trois parmi dix, cinq/dix en sensibilités.
Périodes historiques déjà vues, couverture future contrôlée sur dates communes,
pas de SQL, fournisseur/LLM, ordre, PnL ou modèle servi modifié.
Même cohorte de 1 027 dates complètes / 3 081 sélections : CatBoost D10 **29,60 %**,
logistique trois classes **29,63 %**, ancien filtre D10 **30,57 %**, Oracle
**29,11 %**. D1 respectifs **23,47 / 23,56 / 23,79 / 25,61 %**. Amélioration
Brier3 contre logistique en confirmation (p Holm 0,036), pas de gain de
concentration D10 significatif/robuste ; validation 2022 échouée et zéro période
de confirmation passe tous les gates. Anciens scores reproduits à écart zéro,
cinq modèles sauvés/rechargés et probabilités reproduites ; 80 tests passent.
Pas de balayage de paramètres, nouveau backtest ou promotion après échec.
[Protocole et bilan](direction_top10_catboost_trois_classes_20261018.md).

## 2026-10-18 — apprentissage directionnel exclusivement TOP10 Oracle

**TERMINÉ / `NO_STABLE_TOP10_DIRECTION` — aucune promotion.** Nouveau GO et périmètre explicite : les dix
premiers scores Oracle seulement, au train comme au test ; la campagne
précédente apprenait sur TOP20 %. Six bras commun/secteur/hiérarchique × J ou
trajectoires 5/10 séances. D10/rest et D1/rest sont les tâches pratiques sur les
dix, déciles intermédiaires conservés ; D1/D10 seul reste secondaire théorique.
Shortlist de recherche figée à trois parmi dix, sensibilités cinq/dix ; comparaison
aux trois premiers Oracle originaux. Archives locales, zéro SQL/fournisseur/LLM,
aucun modèle servi, ordre ou batch modifié. Même période déjà observée,
secteurs actuels non PIT : pas un nouveau holdout indépendant.
19 300 couples TOP10, dont 10 490 en évaluation 2022–2026. Zéro des douze gates
pratiques passe. Global PATH D10/rest AUC 0,5072 ; secteur PATH 0,5125 ;
hiérarchie PATH 0,5102. Global PATH choisissant trois des dix : D10 moyens
30,52 % contre 29,12 % pour les trois premiers Oracle, D1 23,84 % contre
25,59 %. Effet surtout en 2025 ; 2022 se dégrade, 2026 augmente aussi D1.
Pas de choix de fenêtre/bras après résultat. Support titre limité ; aucun
modèle servi changé, 51 tests ciblés passent, quinze fichiers de prédictions
et toutes les dates d'apprentissage contrôlés, sources revérifiées.
[Protocole et bilan TOP10](direction_top10_seulement_20261018.md).

## 2026-10-18 — diagnostic hiérarchique D1/D10 secteur/titre et trajectoires

**TERMINÉ / `NO_STABLE_GROUP_STRUCTURE` — aucune promotion.** Protocole figé avant résultats : référence
commune contre corrections sectorielles régularisées et résidus par titre ;
photographie à J contre variations sur cinq/dix séances consécutives. Trois
tâches distinctes : D1/D10 théorique, D10/rest et D1/rest dans Oracle TOP20 %.
Déciles terminaux globaux H20, pas redéfinis par secteur ni confondus avec
le signe de l'excursion. Validation 2022, confirmations historiques 2023–2026.
Archives locales, anciens scores Oracle reproduits ; secteurs actuels non PIT
et années récentes déjà observées. Aucun modèle servi, batch, ordre ou table
modifié ; petites régressions uniquement diagnostiques. Aucun appel payant.
670 602 candidats historiques TOP20 %, dont 375 754 en évaluation 2022–2026.
D1/D10 : AUC quotidienne globale J 0,4908, globale trajectoires 0,4899,
secteur trajectoires 0,4859, hiérarchie trajectoires 0,4782. Petit effet D1/reste
hiérarchique (AUC 0,5263), mais Brier dégradé dans les cinq périodes ; aucun
des douze gates ne passe. 2023 partiel ; 2026 vingt dates inconnues pour
couverture des chemins <95 %, pas assimilées à des baisses. Scores Oracle
originaux reproduits à écart zéro ; empreintes revérifiées, 32 tests ciblés
passent. Aucun entraînement spécialisé supplémentaire justifié par ce test.
[Protocole, réserves et suivi](direction_hierarchique_secteur_titre_20261018.md).

## 2026-10-16 — janvier 2026, TOP10 Oracle et avis GPT archivés, parcours TP20/SL10

**Terminé et audité**, modèle parcours `model-factory-20261014113232-bc35a7`,
fold causal `2025-12-10` : 20 séances, 200 sélections, 28 titres, pas TOP10 %.
110 lots avec textes (409 articles distincts), dont 26 BULLISH, huit BEARISH,
71 ABSTAIN et cinq réponses invalides ; 90 autres sans texte admissible.
Snapshots SQL/cache exacts contrôlés et reparsés, zéro nouvel appel payant.

Entrée J+1, 20 séances, TP20/SL10, sans trailing. Tous les 200 chemins
journaliers qualifiés, fin jusqu'au 2 mars ; aucune ambiguïté journalière.
LONG : TOP10 complet 81/200 TP avant SL (**40,50 %**), avis haussiers 9/26
(**34,62 %**) ; stops 48,50 % contre 57,69 %. Terminal J20 moyen +7,33 %
contre −4,97 %, métrique distincte d'une sortie aux barrières ou d'un PnL.
SHORT secondaire sur les huit BEARISH : 1/8 TP (12,50 %), 6/8 stops, 1/8 timeout.

Comparaison par date avec avis haussiers : −7,78 points de taux TP. Forte
concentration COHR/LMND, douze des 26 avis ; aucune exclusion postérieure.
Pas d'amélioration démontrée sur ce mois, pas de règle contrariante promue.
Histoire news/LLM non PIT strict, univers courant, chemins chevauchants :
ni holdout indépendant ni portefeuille avec coûts/capital. 11 tests dédiés
passent, 400 chemins LONG/SHORT revérifiés offline. Aucun modèle, batch,
univers actif, ordre ou table modifié. Coût API supplémentaire nul.
[Bilan historique détaillé](news_oracle_top10_janvier_2026.md).

## 2026-10-16 — test descriptif news/prix 5m réellement calculé, pas de signal validé

Périmètre distinct du financement : 27 couples avec sujet rapproché, labels
qualitatifs figés avant extraction (12 favorables, trois défavorables, 12
mixtes/neutres). Aucun score FinBERT disponible sur ces couples au contrôle ;
pas d'inférence/API ni de score de confiance inventé. Prix Alpaca SIP déjà
présents, 5m raw, calendrier réel ; zéro collecte ou écriture SQL.

10 fenêtres complètes sur deux dates : cinq favorables, deux défavorables,
trois mixtes/neutres. Après 30 minutes : moyenne −0,5494 % pour les favorables
(3/5 hausses), +0,0503 % pour les défavorables (1/2 baisse), −0,5168 % pour les
mixtes/neutres. Cas affichés intégralement, avant/gap/après distingués ; variations
de cours, pas rendements de portefeuille. Quatre des cinq favorables montaient
déjà dans la fenêtre avant ; aucune causalité démontrée.

Lecture horaire postérieure explicitement marquée : trois favorables en séance
+0,2484 % après, deux hors séance −1,7461 %, sans validation d'un filtre horaire.
Panneau après réception réelle : zéro fenêtre complète ; les dix fenêtres de
publication finissaient avant réception. Tonalité rétrospective non disponible
alors. Ni gain prédictif/PnL, ni résultat généralisable à Oracle/H20/FinBERT.
Modèles, batchs, univers actifs et ordres inchangés.
[Résultats, cas et protocole](news_prix_descriptif_20261016.md).

## 2026-10-16 — clôture du corpus de financement présélectionné éligible

Quatre dernières lectures terminées ; **40/40 textes éligibles**, 73/73
associations présélectionnées examinées, plus les 20 témoins antérieurs :
60 textes distincts / 93 couples. Trois familles de reprises (IonQ, Iambic,
Bending Spoons) regroupent sept articles et 14 associations, pas 14 émissions
des tickers associés. Leurs émetteurs ne sont pas dans le fichier figé.

Registre final des 40 articles avec citations et disponibilités réelles.
BN préférentielles, GSK shelf de plans salariés, CWT dette, AEP/SNPS anciennes
levées : aucune promotion en nouveau financement primaire ordinaire qualifié.
BN reste un candidat préférentiel distinct, pas un événement déclaré neutre.
Nouveauté/histoire antérieure non certifiées ; liste d'événements entièrement
qualifiés pour l'expérience vide. Ni absence globale d'événements dans les
6 720 articles, ni backtest négatif, ni revue humaine indépendante.

Diagnostic figé clôturé, sans nouvel élargissement. Aucune collecte, API LLM,
lecture/écriture SQL, modèle, batch, univers actif ou ordre modifié pendant
cette étape. 69 tests ciblés passent. Les collectes quotidiennes existantes
restent inchangées ; pas d'entraînement ou de test financier lancé.
[Bilan final et référentiel](news_financement_cloture_corpus_20261016.md).

## 2026-10-16 — seconde revue bornée des news de financement, sans rendement

20 textes présélectionnés et 10 témoins nouveaux, sélection figée par empreinte,
un couple par texte, exclusion des textes du premier lot. Tous les corps lus :
zéro nouveau financement primaire entièrement qualifié pour le titre associé.
GSK : shelf ADS de plans salariés, pas cash levé prouvé ; CWT : dette, pas actions ;
offres IonQ/Iambic/Bending Spoons : autres émetteurs, hors fichier courant figé.
NICE : collision TSXV Ni-Co Energy, pas émission du titre US. Mapping contextuel
non assimilé à une erreur fournisseur ; aucune suppression de news.

Un financement de Bending Spoons dans un témoin non présélectionné expose une
limite de rappel des mots-clés, sans changement après coup des règles figées.
Réserve de réutilisation signalée pour deux notices MSCI, sans avis juridique
ni modification des batchs. Total des deux lots : 56 textes distincts, dont
36/40 présélectionnés éligibles ; quatre textes nouveaux restent non lus.

Lecture SQL uniquement : une fenêtre intraday complète (TSM, sans financement
qualifié), 23 manquantes/invalides, deux trop proches d'une limite de séance,
quatre futures au cutoff inchangé. Aucun rendement, API fournisseur/LLM,
écriture SQL, entraînement ou backtest. 64 tests ciblés passent.
[Bilan, preuves et limites](news_financement_seconde_revue_20261016.md).

## 2026-10-16 — rattrapage intraday ciblé réussi, pas encore de signal qualifié

Sur autorisation explicite, 15 titres du sous-univers de recherche téléchargés
en Alpaca SIP 5m, compte `default`, du 13 au 15 octobre inclus. Lot
`intraday-8e54e4efc373af722a2c` COMPLETED à 16h18:39 Paris ; 15/15 tranches,
zéro échec/vide/rejet. Contrôle SQL READ ONLY : 4 776 lignes réellement en
`stock_bars_intraday`, bon flux/marché/dates, zéro barre synthétique.

Les 30 couples d'origine comptent maintenant 10 fenêtres complètes (contre zéro),
14 encore incomplètes, une réserve d'ouverture et cinq futures à la borne
originale. Réception des barres non rétrodatée. Zéro événement nouveau entièrement
qualifié, donc pas de mesure directionnelle, entraînement ou backtest économique.
News, modèles, prix quotidiens, univers tradable et batchs inchangés ; seul le
sous-univers de recherche est créé. Le 16 reste hors de ce téléchargement.
[Bilan, SQL de contrôle et couverture](news_financement_identites_intraday_20261016.md).

## 2026-10-16 — suite identités et cause des trous intraday, sans expérience financière

Sur les 30 symboles déjà revus : dernières barres locales au 9 octobre pour 29,
aucune pour EADSY. Les trois plans intraday existants s'arrêtent au 10 octobre :
les annonces des 14–16 sont hors téléchargement, sans preuve d'une panne fournisseur.
Garde-fou de recherche : deux collisions explicites SUN/RGLD réservées, 25
ancrages à relire, trois sans ancre ; aucune approbation d'émetteur, même avec
une mention explicite US. Pas d'intégration aux collecteurs ni aux modèles.

Demande de rattrapage technique préparée pour 15 sujets rapprochés, Alpaca SIP
5m, 13–15 octobre, pas exécutée. Le 16 reste différé par la règle de fin avant
la date NY courante. Disponibilité réelle des news non rétrodatée ; ce lot ne
constitue pas un test économique exécutable. 80 tests de recherche passent.
Zéro téléchargement, API LLM, écriture SQL, modification de batch, entraînement
ou calcul de performance.
[Bilan et demande détaillée](news_financement_identites_intraday_20261016.md).

## 2026-10-16 — collecte news complète validée, revue financement et couverture intraday

Run final `eodhd_news_ingestion_sync-20261016121131-5ed4d540` COMPLETED :
1 790 checkpoints du cycle réussis, zéro anomalie d'intégrité dans les 6 558
mappings de ce passage ; compteurs SQL/fichier concordants. Dernier passage :
1 005 titres terminés + 785 SKIP, 3 568 versions brutes nouvelles, zéro échec.

Corpus figé sans troncature : 6 720 articles / 11 399 couples, export en quatre
partitions vérifiées. Revue stable sans sélection par prix : 20 cas et 10 témoins,
26 corps lus, citations exactes, aucun nouveau financement primaire entièrement
qualifié dans cet échantillon. Collisions SUN/RGLD entre marchés, rappels anciens,
liens annexes et autres émetteurs distingués. BN : émission préférentielle
identifiée, à qualifier séparément, pas assimilation à une émission ordinaire.
Pas de conclusion d'absence dans le corpus restant ni de revue humaine indépendante.

Intraday : zéro fenêtre complète ; 24 sans barres, une trop proche de l'ouverture,
cinq non achevées à la borne. L'ingestion quotidienne séparée est correctement
prise en compte ; le scoring hebdomadaire n'est pas réputé quotidien.
Disponibilité réelle conservée : rattrapage initial, pas historique de signal.
74 tests de recherche passent ; zéro appel fournisseur/LLM, entraînement,
rendement, backtest économique, écriture SQL ou ordre pendant cette validation.
[Bilan, preuves, limites et suite bornée](news_financement_validation_revue_20261016.md).

## 2026-10-16 — corrections opérationnelles Fed et reprises news, sans nouveau test financier

H15 : date annotée `2026 Oct 12*` désormais lue strictement, note conservée,
25 observations réelles vérifiées sans SQL ; valeurs absentes non imputées.
News EODHD : retries bornés configurables 3 × 30 s/page, titre lent isolé,
pause persistante 30 min après trois titres incomplets consécutifs, pas de
faux échecs pour les titres bloqués avant appel. Compteurs structurés préservés
en SQL/notifications. 406 tests ciblés passent. Les deux sondes réelles G/GABC
restent en timeout ; pas de collecte complète, entraînement, backtest ou ordre.
[Guide opérationnel et limites](../operations/eodhd_news_ingestion_sync.md).

## 2026-10-16 — premier run news finalisé FAILED, archives partielles conservées

Run `eodhd_news_ingestion_sync-20261015223851-cf9bbe96` terminé à 01h01 Paris,
22 min 48 s : 1 790 demandés, 668 terminés + 1 SKIP, 3 échecs et 1 118 non
parcourus. 3 496 occurrences reçues, 2 738 versions brutes nouvelles, 144 titres
sans article, 676 tentatives. Timeout HTTP G.US, puis circuit ouvert pour GABC
et GAIN ; pas un dépassement du plafond run/jour ou une nouvelle panne TLS.

Validation finale READ ONLY : compteurs SQL/fichier concordants ; 3 318 mappings
du run sans reçu non scellé/référence brute manquante/autre fournisseur. Données
partielles conservées en quarantaine, 671 checkpoints réussis dans le cycle
avec les trois smokes. **`FAILED_OR_INCOMPLETE_VALIDATION`**, pas un corpus global
ni une preuve de signal D1/D10. Lectures intermédiaires non promues.

Email accepté par SMTP/Telegram ERROR consignés par le launcher. Aucun nouveau
fetch, SQL write, modèle, scoring, backtest ou ordre pendant l'audit final ;
aucune relance ni modification de batch. Suivi arrêté après bilan, tâche
quotidienne inchangée. [Bilan final et reprise proposée](news_financement_premier_passage_20261016.md).

## 2026-10-16 — premier run news complet lancé, contrôle/revue intermédiaires

Continuation : passage manuel de `eodhd_news_ingestion_sync` sur 1 790 titres,
run `eodhd_news_ingestion_sync-20261015223851-cf9bbe96`, début 00h38 Paris.
**Encore en cours à la remise**, pas un succès final annoncé. Contrôle READ ONLY
à 00h43 : 125 terminés, 1 665 restants, 600 occurrences, 530 nouvelles versions,
20 titres sans article et zéro échec ; intégrité de 563 mappings du run sans
reçu non scellé/référence brute manquante. Compteurs SQL finalisés seulement à la fin.

Revue précoce bornée : cinq couples présélectionnés/deux textes sur une seule
IPO Iambic (IAM), associés à ABBV/NVDA/TAK. Émetteur différent, cinq réservés,
zéro signal qualifié pour ces titres ; IAM hors univers, pas ajouté. Pas une
revue indépendante ni une absence d'événement prouvée. Autres articles non revus.
Validateur final préparé, 64 tests recherche passent. Aucun modèle, scoring,
LLM ou ordre ; seuls les appels/écritures news du collecteur lancé continuent.
[Suivi, lectures et contrôle final](news_financement_premier_passage_20261016.md).

## 2026-10-16 — remédiation ingestion news quotidienne livrée, pas un signal

Transport EODHD corrigé via `common.verified_http` (Certifi + racines Windows,
certificat/hostname vérifiés), sans `verify=False` ni override global.
Page UTC filtrée vide avec suite conservée ; JSON d'erreur plus assimilé à zéro news.

Nouveau `eodhd_news_ingestion_sync` activé et tâche Windows installée, 20h30
Paris sept jours/semaine sur 1 790 titres du fichier tradable ; J−7/J, namespace
quotidien séparé, plafonds tentatives/durée, reprises et compteurs préservés.
Listes/horaires du pipeline US et scoring du vendredi inchangés.

Smoke réel CSCO/IRTC/WHD : 3 appels, 48 occurrences reçues, 46 articles soumis,
18 nouvelles versions brutes, 46 mappings versionnés et 64 reçus ajoutés ;
0 erreur. Reprise du même cycle : 3 SKIP, 0 appel/écriture news supplémentaire.
Contrôle : 73 raw versions, 101 map versions, 174 observations, aucune non scellée.
350 tests ciblés passent. Aucun FinBERT, GPT, modèle, rendement ou ordre.
Pas une qualification de toutes les news/identités ni de la première collecte
planifiée complète. [Contrat et preuves](../operations/eodhd_news_ingestion_sync.md).

## 2026-10-16 — émissions primaires + réaction intraday : faisabilité bloquée

GO qualification/collecte/couverture, sans entraînement ni comparaison financière.
Archives inchangées : 55 articles, 110 reçus confirmés, 112 couples dans l'univers
tradable courant. Requalification des mêmes neuf textes/13 couples : trois
présélections = un rappel SNPS 2025, **zéro nouvelle annonce primaire qualifiée**,
pas une preuve d'absence dans le marché. Revue du même assistant, non indépendante.

Barres 5m brutes, calendrier NYSE, fenêtres avant/après 30 min sans mélange
SIP/IEX : quatre couples complets (témoins, pas des événements qualifiés), 95
manquants/invalides, 13 trop proches des bornes de séance ; zéro fenêtre complète
parmi les présélections. Aucun rendement, label D1/D10 ou PnL calculé.

Cause opérationnelle constatée : étape 8 absente du lundi–jeudi dans config et
plans US récents, présente seulement vendredi. Checkpoints `news_ingested_at`
tous NULL, statuts success anciens non probants pour l'archive. Une seule sonde
HTTPS du transport ordinaire reproduit l'erreur de certificat ; le transport
système du pilote n'avait pas corrigé la production.

**`BLOCKED_DATA_FEASIBILITY`**, pas NO_GO directionnel. Rapport V2 après correction
de sérialisation d'un compteur MySQL ; V1 partielle conservée. Zéro SQL write,
GPT, modèle, ordre ou batch/config modifié. 81 tests ciblés passent.
[Preuves, limites et prochaine borne](news_financement_faisabilite_20261016.md).

## 2026-10-15 — news prospectives : pilote réel et lecture technique terminés

Famille conservée du protocole antérieur : annonces nouvelles de financement
primaire par émission d'actions. Nouveau dossier de recherche sur les seules
archives versionnées, univers tradable courant de 1 790 titres ; aucune sélection
par résultat futur. Dépistage vers revue, réserves d'identité/date/nouveauté,
citations exactes et montants littéraux ; pas de signal LONG/SHORT automatique.

Premières lectures : archives vides, rapports initiaux conservés. Continuation
bornée : problème TLS diagnostiqué, contexte système vérifié limité au pilote,
12 titres/12 tentatives EODHD maximum dans la reprise, une page par titre.
55 versions de texte, 55 mappings versionnés et 110 observations confirmées ;
checkpoints de production inchangés. Aucune disponibilité passée reconstruite.

Qualification V3 : 112 couples article/titre ; revue technique du même assistant
sur 13 couples/neuf textes. Seul texte présélectionné : rappel d'un financement
SNPS de 2025, également associé à ses concurrents. Confusions KEYS UK/US et
SO/SCCO dans les témoins. **Zéro nouvelle annonce qualifiée**, pas une absence
prouvée dans l'univers ni une seconde revue humaine indépendante.

73 tests ciblés passent. Appels EODHD et écritures news/archives limités au pilote,
zéro GPT payant, entraînement, ordre ou batch modifié. TLS des collectes ordinaires
reste à vérifier : le pilote ne modifie pas leur configuration.
Ce n'est pas un résultat financier : sentiment versionné, réaction prix et
comparaison TP20/SL10 restent hors de cette livraison.
[Fonctionnement, résultat et reprise](news_events_prospectifs_qualification_20261015.md).

## 2026-10-15 — projection hypothétique 70 % gagnants TP20/SL10

À la demande de l'utilisateur : projeter l'effet de70 % de trades LONG gagnants.
Simulation **synthétique, sans modèle ni historique**, séparée des expériences
échouées. Scénario principal suppose70 % de TP+20 % et30 % de SL−10 % sans gap,
4 000 USD au départ,25 % du capital courant par entrée, une position à la fois,
sans levier, coûts8bps/sens et réinvestissement.20/50/100 trades donnent
6 745/14 771/54 545 USD, **sans annualisation ni promesse de rendement**.
Sensibilité aux gains moyens plus faibles et aux pertes groupées :70 % de
réussite n'interdit pas un drawdown de53,73 % dans un stress de30 pertes
consécutives. Pas de parité native/live ou de preuve que70 % soit atteignable.
Six tests passent ; zéro SQL/API/apprentissage/ordre ou changement de production.
[Hypothèses, résultats et limites](projection_hypothetique_70pct_tp20_sl10_20261015.md).

## 2026-10-15 — point 2 terminé : filtre net TP15/SL7, NO_GO

Continuation autorisée : construire les cibles, vérifier la parité native et
entraîner un seul petit filtre si les gates de données passent. Oracle parcours
CatBoost inchangé, **20 premiers titres**, LONG TP15/SL7 sans trailing, expiration
open J+21, labels disponibles J+22. Pas de recherche de nouveaux paramètres.

25 200 candidats historiques conservés avant labels, 24 852 admissibles à J,
**20 875 labels connus** dans la v2. Cibles comptabilisées par les primitives
natives sur états isolés, coûts des deux notionnels et financement de référence
50 % à 6,5 % ACT/360. 24 sondes de ledger complet et préfixes sur 293 titres
vérifiés. Les cibles ne sont pas des PnL de portefeuille.

Incident technique documenté : v1 arrêtée par couverture validation **79,98008 %**
au lieu des 80 % fixés. Un rejet flottant de gap exact CUK 6,00 → 6,18 différait
du moteur natif. V2 séparée appelle la fonction native sur **tout** l'historique,
sans epsilon ni seuil modifié : cinq cas changent (trois gains, deux pertes),
25 195 lignes strictement identiques. Couverture validation corrigée à 80 % exacts.
V1/code/manifeste/verdict conservés ; aucune retouche à partir des signes futurs.

Fit 2018–2021 : **14 201** exemples, validation 2022 : **3 642**, contrôle 2023
partiel : **2 278**, après purge J+22. LightGBM profondeur3/sept feuilles,
maximum150/early stopping15, 24 features J, poids égaux par date ; itération
retenue **1**, aucun refit. Seuil 0,50 et autres gates inchangés.

| Mesure | Validation 2022 | Contrôle 2023 partiel |
| --- | ---: | ---: |
| AUC quotidienne moyenne | **0,4656** | **0,4772** |
| Brier filtre | 0,210225 | 0,257302 |
| Brier constant témoin | 0,210094 | 0,257355 |
| Candidats acceptés à 0,50 | **0 / 3 642** | **0 / 2 278** |

**`NO_GO_CONDITIONAL_NET_PROFIT_FILTER`.** AUC sous le gate 0,53, Brier non
amélioré en validation et aucune activité. Lift inconnu, pas « gain en cash ».
Ne pas abaisser le seuil ou inverser les scores après lecture de ces résultats.
Les 24 features varient dans le fit ; scores/cash/dates recontrôlés, pas un
diagnostic fondé seulement sur une erreur technique ou des inputs constants.

55 tests ciblés passent. Audit final du fit : 268 entrées/fichiers source et
quatre sorties vérifiées, scores reproduits et métriques recalculées. Un fit,
**zéro inférence récente ou backtest 2024–2026**, aucun SQL/API/GPT/ordre ou
changement de production. Modèle de recherche archivé, piste non promue.
[Bilan, parité, incident et résultats complets](oracle_path_profit_filter_tp15_sl7_resultats_20261015.md).

## 2026-10-15 — amendement du point 2 : TP15/SL7 avant tout apprentissage

Choix explicite de l'utilisateur : **TP +15 %, SL −7 %**, à la place de TP10/SL10.
Pas d'autre changement de TOP20, durée vingt séances, absence de trailing,
features, périodes, modèle auxiliaire ou seuil 0,50. Formule du budget risque
`0,4 × SL` conservée, donc 2,8 % avant gardes natives.
Témoin sans filtre et variante filtrée devront tous deux utiliser TP15/SL7 :
nouvelle baseline exigée, aucun capital/PnL TP10/SL10 recyclé comme ce témoin.

Version initiale et scores/prix conservés, nouveau protocole de recherche et
dossier `us_oracle_path_profit_filter/20261015-tp15-sl7-protocol-v1` séparés.
Zéro nouvelle cible, entraînement, replay, accès SQL/API/courtier ou changement
de production. La population est réutilisable, pas les anciens outcomes.
Préparation exécutée, statut `PREPARED_NOT_TRAINED` ; 22 tests ciblés passent,
empreintes recontrôlées et paramètres parent TP10/SL10 conservés.
[Protocole actif TP15/SL7](oracle_path_profit_filter_tp15_sl7_20261015.md).

## 2026-10-15 — point 2 : filtre net après Oracle parcours, préparation sans entraînement

Version initiale TP10/SL10, remplacée pour la suite par l'amendement TP15/SL7
ci-dessus ; aucun des anciens résultats n'est réécrit.

**Audit/protocole terminés, pas un nouveau résultat ML.** Le principe de prédire
la rentabilité nette d'un trade après Oracle existait déjà dans E3-A et le
challenger d'entrée du 13 octobre, expirations positives incluses. Verdict
`PARTIAL_DUPLICATE_BOUNDED_REPLICATION_ONLY` : pas une nouvelle famille de signal.
Différence bornée proposée : Oracle parcours CatBoost actuel, **20 premiers
titres**, filtre LONG TP10/SL10, un seul petit LightGBM, seuil fixé 0,50.

Dix caches OOF observables contrôlés, 2 152 562 scores, reproduction des anciens
scores CatBoost avec écart maximal zéro. Population reconstruite **avant futurs
labels** : 25 200 candidats, 1 260 séances, 293 titres, juillet 2018–juillet 2023.
72 tranches de prix / 3 409 276 lignes vérifiées par empreintes. Modèles annuels
`437ed1` / `102eca` / `bc35a7` et 13 780 candidats récents contrôlés ; pas de
réentraînement ni de sélection des candidats sur leur rendement futur.

Protocole : entrée prochain open, TP10/SL10, sans trailing, expiration open J+21,
labels disponibles J+22, 24 features à J, fit 2018–2021, validation 2022 et contrôle
2023 purgés. 2024–2026 déjà explorés, jamais présentés comme holdout vierge.
Cible standardisée nette de coûts natifs et financement de référence, **pas**
le PnL exact du futur portefeuille. Parité du labeler et couverture à qualifier
avant fit ; anciens résultats TOP5/60 séances non recyclés comme nouvelles cibles.
Gates préparés et arrêt si échec, sans seuil retouché sur les pertes récentes.

Dossier `us_oracle_path_profit_filter/20261015-protocol-v1`, statut
`PREPARED_NOT_TRAINED` : zéro entraînement, label calculé, replay économique,
appel API/SQL/courtier ou changement de production. Prochaine étape sur nouveau
GO : cibles/parité native, features J, couverture et purge, puis éventuel fit.
31 tests ciblés passent ; contrôle final séparé des 235 entrées et cinq sorties,
population sans label futur, bornes/ordre vérifiés. Pas de parité de nouvelles
cibles revendiquée : elles ne sont pas encore implémentées.
[Audit des doublons, inventaire et protocole](oracle_path_profit_filter_tp10_sl10_20261015.md).

## 2026-10-15 — contrôles LONG TP10/SL10 appariés : avantage de l'inversion non stable

GO point 1 : comparer achats des avis BEARISH, achats des avis BULLISH et TOP20
entier sans filtre, **tous LONG TP10/SL10**, mêmes modèles annuels
`437ed1` / `102eca` / `bc35a7`, mêmes prix, risque, coûts et financement.
Aucun seuil de confiance ajouté. 4 000 USD par an, levier maximal x2, sans
trailing, entrée prochain open, expiration vingt séances, pas de renforcement.
734/913 avis valides bruts, 732/911 admissibles à J ; le témoin entier conserve
aussi avis inconnus/invalides/ABSTAIN. Neuf cas : trois BEARISH repris après
vérification, **six nouveaux témoins**, aucun nouvel appel GPT.

| Année | BEARISH LONG | BULLISH LONG | TOP20 entier LONG |
| --- | ---: | ---: | ---: |
| 2024 | +55,88 % | −26,04 % | −17,24 % |
| 2025 | +20,80 % | −2,35 % | +14,66 % |
| 2026 au 30/09 | −18,82 % | −14,04 % | −19,67 % |

Bornes civiles avec positions ouvertes valorisées. DD, dans le même ordre :
2024 −16,48/−30,08/−40,16 % ; 2025 −28,24/−29,40/−34,37 % ;
2026 −31,98/−28,77/−34,93 %. Après fermeture des cohortes anciennes :
2024 +62,04/−26,04/−7,40 % ; 2025 +20,89/+2,95/+26,04 %.
L'avantage civil 2025 de l'inversion contre le témoin entier disparaît après
la queue : **−5,15 points** ; 2026, avantage de seulement +0,84 point contre
TOP20 entier, mais −4,78 points contre BULLISH et perte absolue importante.

Achats 294/289/560 ; clôturées 292/287/552 ; gagnantes/perdantes
161/131,155/132,299/253, taux gagnants 55,14/54,01/54,17 %.
Deux/deux/huit positions encore ouvertes en 2026. Exposition non appariée :
2026 brut moyen/equity 0,385/0,569/0,883 ; pas de preuve d'alpha à risque égal.
**Conclusion : intérêt rétrospectif surtout en 2024, pas d'inversion GPT robuste
à promouvoir.** Les années et l'hypothèse ont déjà été examinées, news/LLM et
macro non certifiés PIT, secteurs actuels, dividendes/marge incomplets.

Neuf cas terminés sans échec économique, audités quotidiennement ; 16 tests
ciblés passent. Premier lancement bloqué avant simulation par des conversions
LF/CRLF Python : équivalence SHA256 prouvée et archivée, sans modification des
anciens manifestes ni tolérance pour un changement de contenu/configuration.
Zéro entraînement, écriture SQL, ordre courtier ou modification de production.
[Protocole, capitaux, queues, exposition et bilan](news_gpt_comparaison_long_tp10_sl10.md).

## 2026-10-15 — inversion des 734 avis BEARISH en achats LONG TP10/SL10

Demande explicite : acheter en LONG les avis GPT baissiers valides, sans seuil
de confiance ajouté. Modèles annuels `437ed1` / `102eca` / `bc35a7`, même TOP20
figé et mêmes réponses archivées. **734 avis**, 732 admissibles à J avant risque ;
pas de remplacement hors TOP20, priorité au score Oracle original.

Trois portefeuilles : 4 000 USD réinitialisés annuellement, levier d'entrée <=2,
cap de position 40 % avant gardes, budget risque `0,4 x SL`, entrée à l'open
suivant, **TP10/SL10**, sans trailing, expiration à l'open après vingt séances.
Régimes, risque, coûts et financement natifs conservés ; LONG fractionnaire
possible, aucun frais d'emprunt SHORT.

| Année | Capital à fin d'année / 30 septembre 2026 | Rendement civil | DD civil | Achats | Gagnantes / perdantes de cohorte clôturée |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 6 235,36 USD | +55,88 % | −16,48 % | 82 | 48 / 34 |
| 2025 | 4 832,07 USD | +20,80 % | −28,24 % | 130 | 75 / 55 |
| 2026 au 30/09 | 3 247,12 USD | −18,82 % | −31,98 % | 82 | 38 / 42 |

Taux gagnants des cohortes : **58,54 % / 57,69 % / 47,50 %**. Les cohortes
2024/2025 incluent leurs sorties de début d'année suivante, sans nouvelle décision :
capitaux après fermeture **6 481,76 / 4 835,69 USD**, soit +62,04 / +20,89 %.
En 2026, deux positions APP/FICO restent ouvertes, latent −63,87 USD inclus.
Total : 294 achats, 292 clôturées, **161 gagnantes / 131 perdantes**,
soit **55,14 % / 44,86 %** ; aucune addition trompeuse des rendements annuels.

**Conclusion : positif en 2024/2025, perdant en 2026 ; avantage stable non démontré.**
Hypothèse postérieure aux pertes déjà observées. Pas de témoin LONG aux mêmes
TP10/SL10 dans ce périmètre initial ; les témoins ont depuis été évalués dans
la comparaison appariée du 15 octobre ci-dessus. L'écart avec les anciens SHORT
TP20/SL5 n'isole pas l'effet de l'inversion. News/LLM non certifiés PIT, secteurs actuels, dividendes et marge
non entièrement qualifiés : recherche uniquement, pas de promotion live.

Trois cas terminés sans échec, audit journalier des comptes/protections/entrées
passé, 27 tests ciblés réussis. Zéro nouvel appel GPT, entraînement, écriture SQL,
ordre courtier ou modification du moteur partagé et de la configuration.
[Protocole, résultats et réserves](news_gpt_baissiers_achat_long_tp10_sl10.md).

## 2026-10-15 — confiance GPT et LONG >=0,90 TP20/SL10 : clôturée, non concluante

**Statut : expérience terminée et archivée ; variante non retenue pour le live.**
Aucun avantage suffisamment stable démontré. Ce bilan porte sur ce filtre et
ces protections, pas sur l'inutilité de toutes les informations des news.

Comparaison par tranche à **TP20/SL5 inchangé** : 335 positions LONG et 167 SHORT
clôturées (SHORT autorisé aussi en régime normal uniquement dans la recherche).
Jambes regroupées, positions ouvertes exclues, cinq tranches figées et aucun
balayage de seuils. Au seuil >=0,90 :

- LONG : 16/65 gagnantes, **24,62 %**, PnL −262,57 USD ; sous 0,90 : 74/270,
  **27,41 %**, +3 061,67 USD ;
- SHORT : 13/67 gagnantes, **19,40 %**, PnL −692,55 USD ; sous 0,90 : 25/100,
  **25,00 %**, +476,95 USD.

PnL net de frais de transaction/emprunt, financement non attribué aux positions.
La confiance haute améliore le taux gagnant en 2026, pas en 2024/2025 : aucune
progression stable ni calibration. Groupe >=0,95 : seulement 11 LONG / 25 SHORT.
Attribution descriptive des exécutés, pas portefeuilles de tranches à capital égal.

Test distinct demandé : **LONG uniquement, avis BULLISH/VALID et confiance
>=0,90, TP +20 % / SL −10 %**, modèles annuels `437ed1` / `102eca` / `bc35a7`.
163 avis retenus (25/53/85), puis 74 achats après risque/exécution. Départ de
4 000 USD indépendant chaque année, levier d'entrée maximal x2, sans trailing,
expiration à l'open après vingt séances ; coûts, financement et régimes natifs.

| Année | Capital final civil | Rendement | DD maximal civil | Gagnantes / perdantes clôturées | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 3 226,05 USD | −19,35 % | −25,06 % | 2 / 10 | 16,67 % |
| 2025 | 4 019,75 USD | +0,49 % | −18,55 % | 15 / 17 | 46,88 % |
| 2026 au 30/09 | 3 454,23 USD | −13,64 % | −20,61 % | 11 / 18 | 37,93 % |

Au total : **28 gagnantes / 45 perdantes**, soit **38,36 % / 61,64 %** sur les
73 positions clôturées. Une VICR encore ouverte au 30/09/2026 : latent inclus
dans le capital, exclue du taux gagnant. Effet conjoint du seuil et du SL :
aucun effet causal isolé de la confiance n'est revendiqué.

**Conclusion : pas exploitable en production en l'état.** Deux années perdantes
et une année presque à l'équilibre, avec DD de 18,55 % à 25,06 %. Ne pas chercher
le « bon seuil » après coup sur les mêmes années. Une éventuelle reprise devra
utiliser un protocole figé, des données prospectives réellement disponibles avant
décision et une période encore non examinée, contre une baseline comparable.
L'historique non certifié PIT, la mémoire future du LLM, les secteurs actuels
et les hypothèses d'emprunt SHORT restent des réserves, pas des détails résolus.

Trois nouveaux cas terminés et audités quotidiennement ; 30 tests ciblés passent.
Zéro nouvel appel GPT, entraînement, écriture SQL, ordre ou changement de production.
[Tranches, résultats annuels, comptes et réserves](news_gpt_confiance_tranches_2024_2026.md).

## 2026-10-15 — 734 avis GPT baissiers : douze backtests SHORT audités, pas de rentabilité stable

Mêmes trois modèles annuels Oracle parcours `437ed1`/`102eca`/`bc35a7`, TOP20
et réponses SQL de la campagne terminée. **734 couples BEARISH/VALID**, 150 titres,
732 admissibles à J ; pas de nouveau seuil de confiance. Direction issue du
filtre GPT, pas d'une tête SHORT entraînée. Classement par score Oracle original.

4 000 USD réinitialisés chaque année, levier d'entrée <=2, TP20/SL5, sans trailing,
expiration à l'open après vingt séances ; quantités entières, cash/risque natifs.
Deux profils séparés : permissions natives inchangées, et permission locale de
SHORT en normal, **sans changement de production**. Témoin TOP20 entier SHORT
dans chacun. 12 cas terminés, aucun échec ; 37 tests ciblés passent.

Avec SHORT autorisé en normal : capitaux à fin 2024/2025 et au 30/09/2026
**3 101,34 / 4 909,75 / 3 831,99 USD**, rendements **−22,47 / +22,74 / −4,20 %**,
DD **−27,16 / −13,39 / −23,58 %**. Entrées55/37/77 ; gagnantes/perdantes
fermées11/44,10/27,17/58 ; deux positions2026 encore ouvertes, latent inclus.
Témoin sans filtre :−35,89/−26,74/−32,26 %, DD−44,96/−31,84/−40,95 %.
Avantage relatif sur ces trois années, mais deux années perdantes, exposition
non appariée et pas de confirmation indépendante. Avec régime natif :0/5/0
entrées, capital4 000/3 799,94/4 000USD ; cinq perdantes en2025, témoin+2,07 %.

Emprunt supposé disponible à0,3 %/an, pas de recalls/dividendes compensatoires
historiquement qualifiés ; marge hypothétique. NonPIT news/LLM et secteurs actuels.
Pas une preuve de SHORT historiquement exécutable, ni promotion live.
Audit journalier cash/dette/MTM/emprunt/protections/expiration et empreintes passé.
Zéro nouvel appelGPT, entraînement, écritureSQL, ordre ou changement du moteur.
[Protocole, résultats par profil et réserves](news_gpt_baissiers_short_backtest_2024_2026.md).

## 2026-10-15 — achat des seuls avis GPT haussiers : six backtests audités, avantage non uniforme

Trois modèles annuels explicitement demandés, mêmes sélections TOP20 que la
campagne SQL. 913 couples BULLISH/VALID (126 titres), aucun seuil de confiance
ajouté ; deux entrées KLAC non qualifiées à J écartées, sans regarder le futur.
Portefeuille LONG 4 000 USD réinitialisé chaque année, levier d'entrée <=2,
TP20/SL5, sans trailing, expiration à l'open après20séances ; coûts, financement,
risque et régimes natifs. Témoin TOP20 entier avec règles identiques.

Capitaux **à fin d'année / 30 septembre2026** pour GPT :
**2 947,62 / 6 991,65 / 4 607,48 USD**, rendements−26,31%/+74,79%/+15,19%,
DD−32,61%/−15,89%/−25,16%. Témoin :2 874,82/8 086,91/4 038,88USD,
−28,13%/+102,17%/+0,97%, DD−38,14%/−26,25%/−36,60%.
Après fermeture des cohortes anciennes :GPT2 947,62/7 138,62USD contre
témoin3 001,25/8 787,65USD ; l'avantage civil2024 ne tient pas après la queue.

Achats filtrés78/115/146 ; fermées gagnantes/perdantes15/63,40/75,35/107 ;
quatre positions2026 encore ouvertes, latent inclus au30/09 sans vente fictive.
Moins d'exposition et DD plus bas, mais pas de domination régulière du rendement
ni d'appariement d'exposition. Recherche nonPIT, pas de promotion.

Six cas terminés et audités,14tests ciblés passent. Expirations contrôlées à20
séances, TP/SL et capital réconciliés. Zéro nouvel appelGPT, entraînement,
écritureSQL, ordre courtier ou modification du moteur partagé.
[Protocole, résultats détaillés et réserves](news_gpt_haussiers_backtest_2024_2026.md).

## 2026-10-15 — TOP20 Oracle + GPT 2024–2026 : campagne lancée, pas de résultat économique

Demande explicite : les trois modèles annuels `437ed1` (2024), `102eca` (2025),
`bc35a7` (2026), du 1er janvier 2024 au 30 septembre 2026, TOP20 par séance.
Préparation complète de 689 séances / 13 780 couples ; 5 827 lots avec articles,
7 953 sans texte qualifié, deux requêtes trop volumineuses. 213 anciennes analyses
du T1 sont réutilisables gratuitement. Les scores proviennent du SQL courant,
avec filiation et folds annuels pré-année vérifiés, sans réentraînement.

Campagne GPT `gpt-6-luna` lancée le 15 octobre à 00:49 Paris, **8 USD maximum de
nouveaux appels**, réservations concurrentes persistantes, pas de retry payant.
Quatre tables `llm_news_analysis_*` : réponses immédiates et snapshots mensuels
complets, y compris inconnus. 37 tests ciblés passent. Ni PnL, ordres, modèle,
batch ni configuration de production modifiés. News importées/révisables et
métadonnées actuelles : recherche exploratoire, pas certification PIT historique.
**En cours au lancement de cette entrée** : seul le bilan du run atteste la fin.
Mise à jour : collecte terminée,33mois/689séances,5 612nouveaux appels et
213réutilisations,2,502154USD sur8USD. Avis913BULLISH/734BEARISH/3 823ABSTAIN ;
355réponses invalides,7 953sans news qualifiée et2lots trop volumineux gardés
inconnus. Les33snapshots mensuels terminés et réponses sont confirmés enSQL.
[Protocole, sauvegarde, limites et suivi](news_gpt_top20_historique_2024_2026.md).

## 2026-10-15 — cache SQL des avis GPT : 221 réponses conservées, aucun nouvel appel

Demande explicite distincte après les deux pilotes. Quatre nouvelles tables
`llm_news_analysis_*` dans `alpha_trade`, schéma canonique/migration0105 et
installation ciblée sans upgrade global. 221 réponses importées,203valides et
18invalides ;912associations article/lot et2snapshots complets de recherche.
Seconde importation :221réutilisations,0doublon et0appelAPI.

Relecture autonome SQL, cléOpenAI absente du processus et HTTP bloqué :les600avis
duT1 et25dupilote septembre reproduisent décisions,veto etrangs des originaux.
Les réponses restent des lots titre/date,pas des avis unitaires inventés.
Service unitaire séparé avec clé versionnée(article/texte/symbole/modèle/prompt),
réservation atomique,RAW avant validation,absence de retry sur issue inconnue.
Ancien article présent dans un lot :pas de paiement unitaire implicite.

Ni nouvel entraînement/PnL,ordre ou collecte,batch/config/pipelineWeb modifié.
Disponibilité SQL à l'import réel,pas antidatée ;pas de promotion ou gain
directionnel démontré par le cache. Les constats financiers ci-dessous restent
inchangés.92tests isolés passent,dont27du cache.
[Tables,preuves et réutilisation](../signals/news_analysis_cache.md).

## 2026-10-14 — TOP10 + GPT T1 2025 terminé : moins de pertes, signal partiel non PIT

GO payant obtenu après la préparation ci-dessous. Plafond initial 0,50 USD porté
à 1 USD par l'utilisateur ; processus maintenu à sa limite plus stricte de 0,50.
**213 réponses payées uniques, 0 retry/Web, 0,0887963 USD**, écritures de cache
incluses. Oracle parcours CatBoost annuel2025 `model-factory-20261014113226-102eca`,
fold causal2024-12-05 inchangé. TOP10 sur60séances :600couples,35titres.

26BULLISH/26BEARISH/143ABSTAIN ;18réponses invalides (15citations,3JSON) gardées
UNKNOWN sans veto ni nouvel appel,387sans texte qualifié sans appel. Premier
arrêtPLTR après12réponses, puis continuation stricte avant toute lecture du PnL.
Réponses scellées avant les résultats futurs. Correction du budget conservateur
pour inclure la majoration de cache omise dans l'estimation initiale.

Deux portefeuilles natifs continus, LONG,4 000USD,levier<=2,TP20/SL5,sans trailing,
entrée prochainopen,expiration après20séances,risque/frais/financement identiques,
aucun renforcement ni remplacementTOP11. **Oracle seul3 509,82USD,−12,25%,DD−24,34%,
41positions7gagnantes/34perdantes ; vetoGPT valide3 751,81USD,−6,20%,DD−16,99%,
42positions8gagnantes/34perdantes.** Écart+242,00USD avantAPI,+241,91USD après.
Avantage en février(−23,02%→−16,39%),pas en janvier/mars. Dernières entrées20février,
sorties7mars ; queue prévue jusqu'au30avril sans position restante.

26veto mais seulement3achats directement présents dans la baseline :TSLA21janvier,
AOSL6février,GPRE7février, tous perdants(−162,49USD au total). Ce total ne remplace
pas l'écart final :sizing/capital/réentrées changent. Trois cas ne prouvent pas
un signal stable. Diagnostic individuel BULLISH :3TPavantSL/21trajectoires
qualifiées,contre4/20BEARISH ; pas de validation d'un classifieur directionnel.

**COMPLETED_PARTIAL_SIGNAL_EXPLORATORY_NOT_PIT**,pas de promotion. Textes importés
enmai2026,LLM susceptible de connaître la suite,références actuelles,vintage macro
réservé,univers statique,aucun holdout indépendant.65tests isolés et audit horsligne
réussis ;réconciliation exacte,TP/SL vérifiés,aucune API pendant l'évaluation.
Aucun SQL écrit,entraînement,ordre ou changement de modèle/batch/config.

Run : `artifacts/research/us_news_gpt_q1_2025/20261014-v2` ;résultat final
`q1-results.json`,audit`paid-completion-audit.json`. Le`report.json` de préparation
reste inchangé. [Protocole, mois, coûts, erreurs et attribution](news_gpt_top10_t1_2025_resultats_20261014.md).

## 2026-10-14 — TOP10 + GPT T1 2025 : état de préparation avant le GO payant

**`PREPARED_AWAITING_PAID_ANALYSIS_GO` à cette étape historique**, avant le run
payant et financier terminé dans l'entrée ci-dessus.
GO borné à préparer et chiffrer avant consommation de crédit. CatBoost annuel
2025 `model-factory-20261014113226-102eca`, fold causal `2024-12-05`, poids inchangés.
107 399 couples observables scorés à nouveau sans entraînement : TOP10 de 60 séances,
600 couples titre/date, 35 titres. Les 300 TOP5 de référence sont reproduits
exactement, scores et admission à J compris. Aucun choix sur les résultats futurs.

News existantes, fenêtre figée 24 h avant clôture, même protocole que le pilote :
213/600 cas avec news qualifiées pour le paquet ; 387 UNKNOWN ; 885 associations,
880 articles distincts, 573 extraits tronqués. Zéro texte du jour historiquement
admissible à la garde conservatrice : insertions en mai 2026. Risque de mémoire
du LLM sur 2025 explicite. Pas de certification PIT ni d'avantage prédictif établi.

**213 appels GPT préparés, 0 effectué, 0 USD consommé.** Projection empirique
environ 0,07 USD ; borne conservatrice de tokens 0,4992202 USD ; plafond futur
proposé 0,50 USD, soumis à GO distinct. Aucun prix/rendement futur dans les
paquets, ni calcul financier. Présence des seules clés futures date/symbole
vérifiée pour les 600 fenêtres, jusqu'à l'expiration maximale du 30 avril 2025 ;
ce n'est pas une qualification des OHLCV ou des actions sur titres.

41 tests isolés et audit de préparation hors ligne réussis. Arrêt technique v1
avant news sur l'emplacement de `oracle_rank`, corrigé sans changer de protocole ;
**v2 est le run de référence**. Aucun batch/config/modèle de production ou SQL
modifié, aucun téléchargement fournisseur, appel GPT/Web ou ordre courtier.

Run : `artifacts/research/us_news_gpt_q1_2025/20261014-v2`.
[Couverture, budget, réserves et prochaine décision](news_gpt_top10_t1_2025_preparation_20261014.md).

## 2026-10-14 — GPT sur news stockées de septembre : pilote terminé, aucun veto

GO explicite, crédit API réduit. TOP5 CatBoost parcours annuel2026, cinq premières
séances :1/2/3/4/8septembre. 25couples titre/date, huit titres distincts, 27articles
dans les24h avant clôture. Publication seule : import des textes2–3octobre,
zéro texte du jour qualifié PIT local. Étude exploratoire distincte de la famille
dilution-only, jamais une réparation du précédent gate historique.

GPT configuré `gpt-6-luna`, uniquement textes stockés, sans Web/outil/prix futur.
Huit appels réussis, aucune relance ;17cas sans news gardés UNKNOWN. Sept
ABSTAIN, un BULLISH (MRVL4septembre), zéro BEARISH. Citations exactes vérifiées ;
19/27extraits tronqués. Règle primaire figée : veto LONG si fait matériel baissier,
identité correspondante, citations valides et confiance>=0,75. **Aucun veto.**
19 750tokens d'entrée/796sortie, coût estimé brut **0,002373USD**, plafond avant
appel0,0176142USD<0,05USD. Ni solde interrogé ni seuils relâchés après les résultats.

Deux portefeuilles natifs appariés, capital4000USD, levier<=2, SL5/TP20 sans
trailing, expiration après20séances, frais/spread/slippage/financement identiques :
**4881,17USD, +22,03%, DD clôtures−5,27%, 9positions closes,4gagnantes/5perdantes**
dans les deux cas, courbes/trades strictement égaux. **Gain additionnel GPT nul**,
avant sa petite dépense API. Le seul avis BULLISH MRVL touche SL5 dans le diagnostic
individuel ; il n'est pas acheté dans le portefeuille sous contraintes. Les25
diagnostics ne sont pas25ordres ni un test BULLISH-only. Aucun alpha établi.

Arrêt technique initial sur la macro manquante des5–7octobre, avant PnL. Script
initial conservé ; continuation hors ligne déléguant au garde natif existant,
sans interpolation/neutralisation : toutes les positions étaient sorties
le23septembre ; ces dates sont cash-only et ne nécessitent plus de macro.
Aucun nouvel appel GPT et aucun garde de risque désactivé. 28tests isolés et
audit final hors ligne réussis. Ni SQL écrit, batch/config/modèle changé ni ordre.
Textes/mappings historiques non immuables, mémoire LLM non maîtrisée, métadonnées
actuelles et petit échantillon répétitif interdisent une conclusion prédictive.

Run : `artifacts/research/us_news_gpt_september/20261014-v1`.
[Protocole, huit avis, résultats financiers et réserves](news_gpt_septembre_pilote_20261014.md).

## 2026-10-14 — Infrastructure news : archive prospective livrée, pas de nouveau test financier

GO distinct obtenu après le blocage de faisabilité ci-dessous. Collecte existante
raccordée à `news_raw_versions`, `news_ticker_map_versions` et
`news_archive_observations` dans `alpha_trade`. Textes/payloads distincts et
associations/politique conservés, empreintes et ordre des changements A/B/A,
disponibilité UTC confirmée après commit. Doublons inchangés sans nouvelle
version, reprises non antidatées et reçus en attente exclus. Les mises à jour
partielles et relectures de lignes anciennes sont distinguées des collectes.

Trois tables créées vides par DDL ciblé, aucun backfill ni modification des
anciennes news. Marqueur local0088 conservé ; pas d'upgrade global intermédiaire.
Migration canonique0104 et guide d'exploitation livrés. Aucun appel fournisseur
supplémentaire, modèle réentraîné, planning/activation/étapes de batch modifiés
ou ordre courtier. Seule la liste des tables touchées de `us_pipeline` est complétée.
Les anciens scores de sentiment ne deviennent pas immuables. L'identité de
l'émetteur, la complétude des textes/flux et l'alpha restent à qualifier.

91 tests ciblés et smoke natif MySQL sur copies temporaires de session réussis.
Aucune fausse news persistée dans les tables réelles ; archive vide au déploiement.

[Contrat, statut, reprise, rétention et limites](../signals/news_version_archive.md).

## 2026-10-14 — News factuelles nouvelles : faisabilité terminée, historique non qualifié

**Clôturé au gate de données : `BLOCKED_HISTORICAL_TEXT_PIT`.** Une seule famille
figée avant tout rendement : annonce nouvelle de financement primaire en actions,
comme éventuel veto d'un achat Oracle. Cible envisagée TP20 avant SL5 sous vingt
séances, mais **aucune cible/prix futur/PnL chargé ni calculé** dans cette étude.
Ce n'est pas une nouvelle preuve négative du sentiment ni une optimisation du stop.

TOP5 d'origine des CatBoost annuels, janvier/juillet 2025 et janvier/juillet2026 :
420 décisions titre/séance. Lecture SQL strictement SELECT, sources autorisées
de l'étude EODHD/Alpaca, trente jours de contexte. Résultat observé EODHD seul,
10 168 associations et 8 958 articles, zéro troncature ou requête manquante en v5.
Les archives de scores de sentiment ne conservent pas les corps ; `news_raw`
les conserve mais ses upserts et ceux des mappings ne versionnent pas tout l'historique.

2025 : aucun ancien texte passant la garde stricte avant clôture. 2026 :92/210
décisions ont un ancien texte admissible au diagnostic, toutes en juillet ;
**zéro article des dernières24h qualifié sur les deux années étudiées**.
Les publications2025 ont été insérées en2026. Absence de version admissible
ne devient ni absence d'événement ni sentiment neutre.

Deux annonces présélectionnées dans le contexte, mais aucune dans la fenêtre
des TOP5 effectifs à J : Marvel Biosciences canadien associé au MRVL US, identité
à exclure ; DigitalOcean avec émission et rachat de convertibles, dilution nette
non qualifiée, pas d'étiquette baissière automatique. Échantillon de14 pièces
contrôlé techniquement ; deux aperçus payants/incomplets repérés malgré>200caractères.
Pas de revue humaine indépendante et pas d'annotation exhaustive de tous les corps.

L'extracteur d'audit a été corrigé pour les payloads stockés en chaînesJSON :
10 004 publications précises/cohérentes,164 réservées à minuit. **Ne pas utiliser
le rapport préliminairev4**, remplacé parv5. Aucun payload SQL n'a été modifié.
Les arrêts SQL bornésv1/v2/v3 sont conservés comme essais techniques, pas comme
variantes de trading. Aucun seuil ou famille ajusté après lecture de rendements.

10 tests ciblés réussis ; empreintes, panneau recalculé, extraits et clôture
NYSE anticipée vérifiés hors ligne. Aucune écriture SQL, API fournisseur/LLM,
nouvelle collecte, modification de modèle/batch/configlive ou ordre courtier.
Les données ne sont pas à jeter ; l'alpha de nouveauté n'est ni démontré ni réfuté.
Une suite demanderait d'abord versions prospectives, identités et contenu qualifiés,
avec un nouveau GO avant toute modification de collecte.

Artefacts finaux : `artifacts/research/us_news_materiality_feasibility/20261014-v5`.
[Protocole, résultats de disponibilité et réserves](news_materiality_feasibility_20261014.md).

## 2026-10-14 — TOP5 Oracle parcours : une entrée exécutée par épisode, NO_GO

**Terminé, clôturé sans intégration.** Six cas complets, zéro échec technique,
verdict`NO_GO_STABLE_EPISODE_ENTRY_ADVANTAGE`. Mêmes CatBoost annuels
437ed1/102eca/bc35a7 que les comparaisons précédentes. LONG TOP5 en ordre de
score, SL5/TP20/trailing15, budget2 % equity, capital4000USD annuel, plafond
entrée levier2, coûts/financement/risque natifs conservés. Aucun entraînement,
SQL, ordre courtier ou changementLIVE/batch.

Règle figée : une présence continue au TOP5 original = un épisode. Une absence
observée puis retour réarme. Qualité/risk refusé ne crée pas un épisode ; seul
un achat effectivement committé le consomme. Pas de remplacement par le rang6,
pas de cooldown optimisé, aucune vente imposée aux positions existantes.
Épisodes et capital réinitialisés par année, première présence censurée à gauche.

Gate opérationnel de10 réentrées par an passé27/43/44, sans sélectionner selon
leur PnL : ces réentrées contribuaient−322,89/−47,77/+507,83USD réalisés au
témoin. Leur suppression ne simule pas un gain par simple soustraction.

| Période | Rendement témoin | Une entrée/épisode | DD témoin | DD règle |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −16,74 % | −47,93 % | −32,83 % | −50,75 % |
| 2025 | +33,12 % | +32,40 % | −21,79 % | −28,15 % |
| 2026 au30septembre | +36,14 % | −12,23 % | −26,19 % | −23,99 % |

Taux gagnants clos règle13,39/28,33/20,62 %, contre20,53/29,29/26,71 %.
Achats exécutés128/122/99, zéro réentrée même épisode dans le challenger ;
maximum1 fill/épisode vérifié. Trois témoins aux trades/courbes exactement
identiques aux archives FIXED_REFERENCE. Le filtre modifie aussi capital,
quantités et opportunités suivantes : l'attribution rétrospective initiale ne
prédisait pas cet effet économique complet.

50 tests ciblés réussis, dont neuf nouveaux. Épisodes/préfixes, rejets non
consommants, callbacks idempotents, causalité des compteurs de fills, stops et
réconciliation financière vérifiés. Seconde revue technique du même assistant,
pas humain indépendant. Périodes déjà inspectées et réserves de données natives
maintenues. Pas de variante sur ces pertes ni promotion du veto.

Artefacts : `artifacts/research/us_oracle_path_signal_episodes/20261014-v1`.
[Protocole](oracle_path_signal_episodes_20261014.md) ;
[résultats financiers et contrôles](oracle_path_signal_episodes_resultats_20261014.md).

## 2026-10-14 — TOP5 Oracle parcours : stop ATR contre SL5, avantage non stable

**Terminé et clôturé sans intégration.** Verdict
`NO_GO_STABLE_ATR_STOP_ADVANTAGE`. Six portefeuilles complets, zéro échec,
parité exacte des trois témoins avec les anciens FIXED_REFERENCE.

Nouveaux Oracles CatBoost annuels :2024
`model-factory-20261014113215-437ed1` ;2025
`model-factory-20261014113226-102eca` ;2026
`model-factory-20261014113232-bc35a7`. Mêmes TOP5/admissions connues à J,
LONG explicite, score d'amplitude non directionnel, pas de remplacement futur.

Règle unique figée avant calcul : SL=`clip(ATR20_J/close_J,5 %,10 %)` contre
SL5 fixe, TP20/trailing15 identiques, aucun balayage de coefficient.
Budget nominal2 % equity inchangé avant contraintes natives ; quantité adaptée
au stop, jamais hausse du budget `.4*SL` pour le brasATR. Fraction choisieJ,
ancrée au fillJ+1, jamais desserrée ensuite ; risque effectif du gap contrôlé.
Capital4000USD réinitialisé par année/bras, plafond entrée levier2, frais et
financement6,5 % ACT/360, garde-fous natifs conservés, aucune vente forcéeH20
ou terminale ; capital final avec latent des positions ouvertes.

| Période | Rendement SL5 | Rendement ATR | DD SL5 | DD ATR | Gagnants clos SL5 / ATR |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | −16,74 % | −28,91 % | −32,83 % | −32,03 % | 20,53 % / 19,29 % |
| 2025 | +33,12 % | +42,02 % | −21,79 % | −18,66 % | 29,29 % / 34,06 % |
| 2026 au30septembre | +36,14 % | −26,41 % | −26,19 % | −35,44 % | 26,71 % / 21,57 % |

SL ATR exécuté médian5,87/7,30/7,85 %. Levier brut moyen
SL5→ATR :1,03→0,90 /0,83→0,85 /0,48→0,41. Le budget de risque constant
n'impose pas des capitalisations/expositions identiques à chaque date : sorties,
réinvestissements et état des garde-fous divergent. L'amélioration2025 ne
justifie pas l'ATR uniquement sur cette année connue a posteriori.

41 tests ciblés réussis ; préfixes ATR des2361 décisions de risque vérifiés,
stops/risque des fills, lots clos, cash/latent/financement/DD et témoins audités.
Seconde vérification technique du même assistant, pas revue humaine indépendante.
Les six casv2 ont exactement les mêmes trades/courbes quev1 ;v2 corrige
uniquement un libellé hérité indiquant sizing inchangé dans le brasATR.
Copie du runner originalv1 et empreinte conservées. Aucune hypothèse retunée.

Artefacts finaux : `artifacts/research/us_oracle_path_atr_stop/20261014-v2`.
[Protocole](oracle_path_atr_stop_20261014.md) ;
[résultats financiers, risques et réserves](oracle_path_atr_stop_resultats_20261014.md).
Pas d'entraînement, SQL, ordre courtier, batch ou YAMLlive modifié. Les périodes
déjà observées, prix ajustés actuels, survivants/secteurs nonPIT, dividendes
incomplets et marge/fills hypothétiques restent réservés. Le SL5 reste témoin
de recherche, pas stratégie garantie gagnante ; aucun autre multiplicateurATR
ni profil lancé automatiquement après ce NO_GO.

## 2026-10-14 — TOP5 Oracle parcours : diagnostic des stops SL5 et récupérations

**Terminé, pas de nouveau portefeuille ni d'entraînement.** Référence réelle
des portefeuilles simulés SL5/trailing15/TP20, nouveaux modèles CatBoost
annuels437ed1/102eca/bc35a7. LONG TOP5 en ordre de score ;437 lots clos,
281 sorties au stop initial (gaps compris), trailing stops séparés.

Fenêtre20 séances depuis l'entrée incluse, suivi strictement après la séance
du stop, aucun remplissage avec des prix non qualifiés ou un autre titre.

| Période | Stops qualifiés | HIGH atteint ensuite +20 % | +20 % avant SL10 depuis l'entrée, sans trailing |
| --- | ---: | ---: | ---: |
| 2024 | 101 | 14,85 % | 12,87 % |
| 2025 | 82 | 26,83 % | 15,85 % |
| 2026 partiel | 96 | 33,33 % | 18,75 % |

ATR20/prix médian des lots clos5,94/7,44/8,27 % ; stop5 % médian
0,84/0,67/0,60 ATR.81,46/99,29/99,32 % des entrées ont un stop <1 ATR.
Pas une preuve de séparation : la quasi-totalité2025/2026 appartient à cette
tranche. Recul médian post-stop dans la fenêtre20, tous stops qualifiés :
−11,57/−15,03/−13,92 % ; récupérer ultérieurement n'est pas sans risque.

À60séances : récupération45,10/51,81/61,45 %, mais seulement
21,57/24,10/20,48 % atteignent +20 % avant un SL10 depuis l'entrée, sans
trailing. Treize fenêtres2026 immatures réservées ; deux stops hors suivi20.
Coûts/sizing/réinvestissements NON recalculés : ces taux ne sont pas du PnL.
Sensibilité sans fenêtres chevauchantes, bornes intraday et motifs conservés.

31 tests ciblés réussis (huit nouveaux et23 du diagnostic réutilisé) ; seconde vérification technique du même assistant
sur547 fenêtres qualifiées, empreintes/437 ATR à J/prix/denominateurs vérifiés.
Ni SQL ni modèle/batch/live modifiés. Verdict`HINDSIGHT_RECOVERY_NOT_STRATEGY_PROFIT`.
Suite ATR à risque financier constant uniquement après nouveauGO, pas de
paramètre optimal choisi ici ni d'intégration automatique.

Artefacts : `artifacts/research/us_oracle_path_stop_recovery/20261014-v1`.
[Protocole](oracle_path_stop_recovery_20261014.md) ;
[résultats et réserves](oracle_path_stop_recovery_resultats_20261014.md).

## 2026-10-14 — Sélecteur de protections entraîné : NO_GO, équivalent au profil LARGE fixe

**Statut : expérience terminée et clôturée sans intégration.** Verdict
`NO_GO_STABLE_PERSONALIZATION`. Douze portefeuilles complets, zéro échec.
Ce résultat porte sur ce sélecteur et ces variables, pas sur l'impossibilité
universelle de personnaliser des protections.

Trois profils figés, choisis à l'entrée et conservés pendant la position :

| Profil | SL dur | Trailing | TP |
| --- | ---: | ---: | ---: |
| COURT | 5 % | 10 % | 10 % |
| REFERENCE | 5 % | 15 % | 20 % |
| LARGE | 5 % | 20 % | 30 % |

Deux petites régressions LightGBM CPU prédisent les avantages unitaires nets
COURT−REFERENCE et LARGE−REFERENCE, en points de rendement, pas des probabilités.
Profondeur 2, quatre feuilles, minimum 150 lignes/feuille, learning rate 0,03,
L1=0,1/L2=10, maximum 150 itérations, early stopping 15 sur 2022 seulement.
24 features à J, pondération égale par date, labels à 60 séances purgés.
Développement 2018–2021, validation 2022, contrôle 2023 sans refit.

Oracles annuels utilisés, sans réentraînement ni changement de champion :

| Test | Modèle | Fold causal |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026 | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

Scores recalculés sur le pool observable avant qualification future. Le fit
retient cinq itérations pour COURT et une pour LARGE. Avantages prédits COURT
tous négatifs (−1,053…−0,728 points), LARGE tous positifs (+0,290…+0,412),
REFERENCE=0 : le sélecteur choisit **toujours LARGE**, sur validation 2022,
contrôle 2023 et les 1 260/1 250/933 décisions annuelles qualifiées.
Les sorties numériques varient légèrement, mais pas le profil choisi ;
aucune personnalisation utile ni bug de choix démontré.
Le constant sélectionné uniquement sur validation 2022 est COURT.
Aucun réglage n'a été ajusté aux résultats des tests.

Portefeuilles : capital initial 4 000 USD réinitialisé par année, TOP5 LONG,
plafond de levier ×2, frais/financement/risque natifs, sans renforcement ni
expiration H20/liquidation finale. Capital final avec positions ouvertes MTM.
**2026 est partielle, jusqu'au 30 septembre.**

| Période | COURT fixe | REFERENCE fixe | LARGE fixe | Sélecteur appris |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −23,10 % | −16,74 % | −33,96 % | −33,96 % |
| 2025 | +7,01 % | +33,12 % | +20,71 % | +20,71 % |
| 2026 partielle | −9,37 % | +36,14 % | −10,73 % | −10,73 % |

DD maximal du sélecteur : −40,90/−24,11/−39,84 %, contre
−32,83/−21,79/−26,19 % pour REFERENCE. Moins bon en rendement et DD que
REFERENCE dans chaque période ; ne bat COURT qu'en 2025. REFERENCE reste
perdante en 2024 : sa supériorité relative ne prouve pas une stratégie rentable.

**56 tests ciblés réussis.** Trades et courbes LEARNED exactement identiques
à FIXED_LARGE sur les trois années ; lots/protections/equity/cash/décisions
revérifiés dans `completion-audit.json`. Modifier les labels de contrôle 2023
dans une fixture ne change pas les poids appris. Aucun SQL/courtier/batch/live
touché. Périodes déjà examinées, univers actuel, historiques ajustés, dividendes
incomplets, secteur et vintages macro non PIT certifiés : réserves conservées.

**Décision : ne pas intégrer ce sélecteur, ni ajouter des profils plus fins
ou optimiser un seuil à partir de ces pertes dans cette expérience.** La marge
théorique du diagnostic précédent n'a pas été transformée en avantage appris.
Toute nouvelle hypothèse nécessitera un protocole distinct et un nouveau GO.
Run : `artifacts/research/us_oracle_path_protection_selector/20261014-v1`.
[Protocole et douze résultats financiers](oracle_path_selecteur_protections_20261014.md).

## 2026-10-14 — Protections personnalisées : dataset OOF qualifié, sélecteur pas entraîné

Suite GO à la préparation des variables à J et des exemples antérieurs.
Trois profils SL5 figés : trailing10/TP10, trailing15/TP20, trailing20/TP30.
Les dix folds de recherche CatBoost2018–2023, toujours présents, scorent le
pool observable complet avant qualité future :2 152 562 lignes,6300 TOP5.
Tous les anciens OOF reproduits avec écart zéro sur leurs2 146 823 clés.
24 variables de prix/volume/benchmark/rang recalculées causalement, archives
float32 comparées,404 canaris de préfixe exacts sur148 titres. Pas de macro
à lineage de publication inconnue, news, consensus, secteurs ou score selector
comme nouvelle feature. Le périmètre/rang de l'Oracle hérite cependant du
selector_short_score amont réservé ; pas de certification PIT fournisseur.

Fenêtre60 séances J+1 incluse, ouverte MTM, labels disponibles communément
à J+60.5115 outcomes qualifiés ;1185 exclusions conservées (1109 gaps>3 %,67
J non qualifiés,9 prix futurs inconnus),464 labels purgés aux frontières.
Splits prêts :3342 développement2018–2021,752 validation2022,557 contrôle2023.
209/65/39 exemples non chevauchants seulement : prudence sur taille effective.
35 tests ciblés réussis et revue séparée de comptes/features/targets/purges.
Verdict `READY_FOR_EXPLORATORY_PILOT_NOT_TRAINED`, aucune fit/SQL/courtier/live.

Modèles annuels fournis désormais :2024 `model-factory-20261014113215-437ed1`,
2025 `model-factory-20261014113226-102eca`,2026 `model-factory-20261014113232-bc35a7`.
CatBoost explicite, mêmes173 features et1790 titres ; poids/folds causaux
2023-12-05/2024-12-05/2025-12-10 vérifiés. Pas de nouveaux scores annuels,
backtests ou remplacement des résultats de leurs prédécesseurs dans cette étape.
Cette entrée décrit l'étape de préparation, alors sans entraînement. Le GO
suivant a depuis été exécuté : voir l'entrée du sélecteur ci-dessus, clôturée
`NO_GO_STABLE_PERSONALIZATION`. Le dataset qualifié reste conservé.
Run `us_oracle_path_protection_dataset/20261014-v1`.
[Dataset, modèles, qualification et limites](oracle_path_protections_dataset_oof_20261014.md).

## 2026-10-14 — Oracle parcours TOP5 : espace de personnalisation matériel, apprentissage non démontré

GO borné à l'audit, aucune fit/écriture SQL/ordre/évolution live. Sélections
CatBoost TOP5 archivées des trois folds annuels ; profils figés SL5 partout,
COURT trailing10/TP10, REFERENCE trailing15/TP20, LARGE trailing20/TP30.
Fenêtre principale60 séances, entrée incluse, ouverte valorisée sans vente
fictive ; contrôle20 séances. Coûts unitaires plats, pas de capital/sizing/
réinvestissement ni de PnL portefeuille. Scores avant exclusion future,
échantillon commun sans remplacer les candidats ; métadonnées de folds causales.

Six cohortes v2 terminées/vérifiées. À60 : 1 155/1 109/504 candidats qualifiés
2024/2025/2026 (2026 décisions jusqu'au16juillet). Surplus moyen du meilleur
profil connu après coup face au meilleur constant : +3,68/+3,91/+3,25 points
de rendement unitaire, **pas de rendement annuel réalisable**. Après espacement
des candidats d'un même titre : +2,36/+4,41/+2,14 points, seulement105/79/56
observations. Critère matériel préfigé atteint, pas de signal appris démontré.
Environ50 % de résultats identiques entre profils ; 63,20/62,76/62,10 %
perdent avec les trois. Le sélecteur parfait ne sauve donc pas la majorité
des perdants de cet échantillon. Peu de blocs, borne basse nulle pour le
non-chevauchant2026 ; cinq titres expliquent37–45 % du gain théorique.

51 tests ciblés passent. 437 sorties de protection CatBoost de référence
reproduites exactement en date/prix/motif, sans prétendre à la parité complète
du portefeuille. Revue séparée des six cohortes, comptes/coûts/chronologie
et empreintes présents vérifiés. Précontrôle v1 arrêté : anciens modèles
remplacés dans artifacts/models ; 18 fichiers originaux absents documentés,
aucun rescore/substitution avec les nouveaux modèles ni réécriture des anciens
hashes. Les scores archivés restent vérifiés ; poids non revérifiables aujourd'hui.
Périodes déjà vues, pas de holdout indépendant, pas de promotion.
Verdict `MATERIAL_HINDSIGHT_SPACE_NOT_LEARNABILITY` ; prochain GO nécessaire
pour qualification des features à J et données d'apprentissage OOF antérieures.
Run `us_oracle_path_protection_headroom/20261014-v2`.
[Protocole, résultats, exclusions et réserves](oracle_path_protections_apprentissage_faisabilite_20261014.md).

## 2026-10-14 — Oracle parcours : choix explicite du backend livré

IHM « Algorithme — Oracle Extreme parcours H20 » : LightGBM seul, CatBoost seul,
comparaison automatique sur validation. Défaut IHM `oracle_path.training_backend:
auto` dans config.yaml ; option dédiée `--oracle-path-backend` prioritaire sur
les flags challengers génériques. Choix gelé dans protocol/profile/report et folds,
repris par Predict/backtest/live ; aucun changement aux anciens batchs ou poids.
Compatibilité CLI legacy conservée, reprises avec changement de choix refusées,
pas de fallback silencieux à l'inférence. Petits entraînements CPU de fixtures,
widget/CLI, reprise et corruption testés ; aucun entraînement de production,
ordre, SQL ni nouveau backtest économique lancé pour cette évolution.
267 tests ciblés réussis ; trois anciens modèles annuels chargeables avec
leurs 14 folds et poids inchangés. Les empreintes des anciennes recherches
ne sont pas réécrites pour masquer cette évolution du code.
[Utilisation et contrat](oracle_path_training.md#choisir-lightgbm-catboost-ou-comparaison-automatique).

## 2026-10-14 — Oracle parcours TOP5 : avantage économique apparié CatBoost observé

Deux poids archivés de chaque fold annuel, sans réentraînement ni sélection sur
profits : six portefeuilles sur 2024, 2025, 2026 jusqu'au 30 septembre.
Même population, features, train/validation, prix, macro et risque. TOP5 LONG,
SL5/trailing15/TP20, capital 4 000 USD, plafond ×2, frais et financement inchangés.
Pas de renforcement ni expiration H20/liquidation terminale. 37 tests réussis.
Scores/membership/qualité des champions précédents reproduits exactement ;
six portefeuilles complets sans échec, sources/fichiers revérifiés et trois témoins
identiques trade/curve aux références. LightGBM / CatBoost :
2024 −34,83 /−16,74 %, 2025 +9,93 /+33,12 %, 2026 +11,11 /+36,14 %.
DD respectifs −39,44 /−32,83 %, −20,91 /−21,79 %, −25,74 /−26,19 %.
CatBoost supérieur en rendement et PnL réalisé sur trois périodes, pas en DD
partout. 2024 perdante pour les deux ; pas de solution par simple backend.
Recouvrement TOP5 : 70,48 /76,96 /73,69 % selon année. Périodes/protections déjà
inspectées, pas un nouveau holdout ; aucune promotion live ni modification SQL/batch.
Run `us_oracle_path_backend_economic/20261014-v1`.
[Protocole, modèles et contrôles](oracle_path_comparaison_economique_backends_20261014.md).

## 2026-10-14 — Oracle parcours TOP5 : protections dynamiques figées NO_GO

Une seule règle exploratoire, six portefeuilles FIXED/DYNAMIC sur 2024–2026.
Même source, modèles/folds, TOP5 LONG, frais, sizing et plafond ×2 que la grille.
SL dur 5 % partout. Profil choisi à J, ancré au fill J+1 et retenu pour la position :
DEFENSIVE trailing10/TP10 si régime/market weakness ; TREND trailing20/TP30
si tendance/breadth/force relative positives et VIX≤20 ; référence trailing15/TP20
sinon ou si données insuffisantes. Pas de mise à jour quotidienne des pourcentages.
Pas d'entraînement, SQL ni courtier ; pas de nouveau holdout car périodes déjà vues.
40 tests réussis et protocole figé avant PnL. Six cas complets sans échec ;
sources/fichiers revérifiés, trois témoins identiques trade/curve aux références.
FIXED → DYNAMIC : 2024 −16,74 →−25,96 % ; 2025 +9,93 →−1,75 % ;
2026 janvier–septembre +36,14 →−21,31 %. DD −32,83/−20,91/−26,19 %
→−35,26/−28,40/−39,68 %. Moins bon sur les trois périodes, aucun avantage
transversal. NO_GO pour cette règle, pas de promotion ni d'ajustement après pertes.
Artefact `us_oracle_path_dynamic_protections/20261014-v2`.
[Règles, temporalité, contrôles et réserves](oracle_path_protections_dynamiques_20261014.md).

## 2026-10-14 — Oracle parcours TOP5 : grille levier ×2 terminée, aucun profil positif trois ans

GO reçu pour les trois modèles `a4bd20` (2024), `155d09` (2025), `4df571`
(2026 jusqu'au 30 septembre). Folds causaux vérifiés : validation disponible avant
chaque année ; champions CatBoost / LightGBM / CatBoost archivés, sans sélection
sur les profits. Univers commun 1 790 titres, mêmes 173 features.
TOP5 LONG, pas de renforcement du titre détenu, pas de sortie forcée H20/fin annuelle.
48 profils par année : SL5/7/10, trailing OFF/10/15/20, TP OFF/10/20/30.
Capital 4 000 USD, plafond d'entrée ×2, intérêts simulés 6,5 % ACT/360, coûts natifs,
garde-fous conservés ; equity terminale inclut les positions ouvertes.
144/144 cas terminés sans échec à 09:47 Paris dans
`us_oracle_path_top5_leverage/20261014-v3`, sources/fichiers revérifiés.
Meilleurs observés par année : 2024 SL10/trailing20/TP20 +4,83 % (DD −39,29 %) ;
2025 SL5/trailing20/TP30 +184,83 % (DD −19,26 %) ; 2026 SL10/sans trailing/sans TP
+77,62 % (DD −38,39 %), essentiellement latent : huit positions ouvertes,
PnL réalisé −1 247,82 USD contre latent +4 548,28 USD.
Meilleure moyenne SL5/trailing20/TP30 : −33,96 / +184,83 / −10,73 %.
Aucun profil positif sur les trois périodes ; 1/48, 34/48 et 13/48 positifs
respectivement. Meilleure pire année observée SL5/trailing15/TP20 :
−16,74 / +9,93 / +36,14 %, DD pire −32,83 %. Pas de trailing stable démontré,
pas de promotion du meilleur profil sélectionné sur les mêmes résultats.
Dividendes et marginabilité historique réservés :
ce n'est pas une parité courtier ni un rendement total certifiés.
[Protocole détaillé, sources et suivi](oracle_path_top5_levier_grid_20261014.md).

## 2026-10-14 — News après entrée : confirmation et sortie négative

GO et douze cas hors ligne terminés. Dernière baseline Oracle parcours LightGBM,
mêmes trades/quantités/fills, capital libéré non réinvesti, TP20/SL10 sans trailing.
TOP10 primaire, TOP20/50 secondaires, 2025 et 2026 décisions jusqu'au 2 septembre.
Toutes les nouvelles news scorées doivent être négatives >0,9 pour une sortie
au prochain open ; positives → conserver, sans annuler stop/TP. Publications
après clôture/week-end consommées à la clôture suivante ; pas d'heure inventée.
Stops/TP/expiration/régime prioritaires ; aucune position ressuscitée.
Courbes sans changement et coûts de sortie reproduits exactement sur six cas.
2025 rendement TOP10/20/50 −5,54/−4,49/−2,98 % → −6,69/−6,30/−8,80 %.
2026 +9,23/+10,44/+9,01 % → +8,99/+11,83/+10,43 %. Pas de gain stable.
Premières positives TOP10 : conserver mieux 41,67 % (12 cas) / 53,33 % (15 cas),
écart apparié PnL/âge/mois change de signe. Petit corpus dépendant, non validé.
Diagnostic updated_at : zéro signal fort historiquement admissible sur positions,
courbes identiques à la baseline ; pas de certification PIT des scores.
Pas un rerun des risques après modification d'equity. Aucun SQL/API/fit/ordre
ou batch modifié ; sources vérifiées. Artefact `us_news_post_entry_exit/20261014-v1`.
[Protocole, PnL, drawdowns et limites](news_post_entree_sortie_20261014.md).

## 2026-10-14 — News positives : excursions H0…H20 et retards J−1/J−2

367 851 observations article/titre archivées, univers actuel 1 790 titres.
Règle figée : tous les articles scorés >0,9, au moins un par journée exigée.
J, J−1 seul, J−2 seul, fenêtres J−1/J et J−2/J ; dates NY, séances NYSE.
Maximum HIGH depuis l'open J jusqu'à J20, avec seconde vue open J+1…J20.
2025 complet ; 2026 mature jusqu'au 11 septembre, prix jusqu'au 9 octobre.
Petite hausse pendant le parcours ~99 % aussi sans filtre. H1/J seul : +20 %
atteint dans 7,50 % / 10,01 % des cas 2025/2026, univers 7,29 % / 10,15 %.
Pas d'avantage stable des retards/répétitions ; règle trois jours 41/45 cas.
Témoins par date/volatilité/momentum pré-J, bootstrap descriptif de blocs 21.
Zéro observation admissible avec le diagnostic des dernières mises à jour
avant l'entrée ; pas de certification PIT historique. Maximum ≠ PnL ni TP
avant SL. Aucun SQL/API/fit/ordre/batch modifié ; calcul hors ligne terminé.
V2 canonique : `us_news_positive_path/20261014-v2`.
[Résultats et limites](news_positives_parcours_h20_20261014.md).

## 2026-10-14 — Réutilisation des anciens signaux directionnels faibles

Audit de E2/E3, volatilité/momentum, surprise EPS, révisions EPS, options et prix
d'ouverture. Les confirmations sont négatives, insuffisantes ou sur une autre
cible/horaire. Combinaison OOF et complémentarité déjà NO_GO ; 17 anciens chemins
OOF absents après remise à zéro, pas de restauration. DDR-5 : la jointure sur
earnings_date ne démontre pas disponibilité/vintage PIT, réserve documentée.
Consensus EODHD : 959 094 lignes mais trois snapshots 11–13 octobre, qualifications
fiscales/unités/PIT encore fausses, pas d'issue H20 mature. Pas de stacking lancé.
[Inventaire et qualification](signaux_directionnels_faibles_audit_20261014.md).

## 2026-10-14 — Oracle parcours : filtre d'entrée univarié NO_GO

GO après audit des pertes. 173 features figées + score de référence + neuf
macro, TOP10 primaire et TOP20/50 robustesse. TP20 avant SL10, entrée J+1,
vingt séances, disponibilité J22 ; expiration positive reste « autre issue ».
Dix folds LightGBM originaux rescored sur toute la population observable,
sélection TOP avant labels, pas sur les anciens OOF filtrés par qualité future.
Orientation 2018–2021, validation purgée 2022, confirmation 2023–2026 ; gates
0,55/0,53/0,52, couverture 90 %, maxT en blocs 63 séances, 999 tirages figés.
Macro/lineage dérivé réservés, pas de veto promu ni de training/backtest/SQL écrit.
v1 arrêté sur le type nullable d'identifiants du tape récent, scores historiques
reproduits ; adaptation locale de lecture corrigée, données/modèles intacts.
v2 lancé à 00:16 Paris, PID 38888 ; 27 tests ciblés passent.
**Terminé à 00:18 Paris**, sources finales vérifiées. 96 500 candidats TOP50,
1 930 dates ; dix anciens OOF reproduits exactement sur leurs 2 146 823 lignes,
scores recalculés sur 2 152 562 lignes observables avant labels. 183 colonnes,
549 fiches feature/TOP : zéro piste sélectionnée avant confirmation. Meilleure
AUC quotidienne orientée découverte TOP10 0,5321, validation 2022 0,4986 ;
p maxT minimale 0,817. Verdict `NO_STABLE_UNIVARIATE_ENTRY_SEPARATION`.
Macro descriptive non certifiée PIT, RVX absent. Pas d'entraînement ni nouveau
replay ; piste univariée clôturée, aucune conclusion globale sur le multivarié.
[Protocole, source et suivi](oracle_path_filtre_entree_separabilite_20261014.md).

## 2026-10-13 — Oracle parcours : audit des pertes terminé

Neuf portefeuilles d'amplitude LightGBM archivés, aucun nouveau replay ou fit.
1 388 positions/cas avec chemins internes qualifiés ; portefeuilles recouvrants,
pas observations indépendantes. TOP10 2025 : 81 pertes, 62 baisses dominantes
sans TP20, six TP20 ultérieurs mais après SL. PnL brut −174,99 USD, coûts 46,74,
net −221,73 ; onze gaps sous SL, excès 159,72 USD. Les remises en entrée et
SLIDE perdants en 2025 sont positifs en 2026 : pas de veto uniforme justifié.
TOP20/TOP50 2024 : trades/décisions/courbes identiques, rang max exécuté 12.
26 tests ciblés passent. État `COMPLETED_RETROSPECTIVE_AUDIT` à 23:54 Paris,
sources vérifiées avant/après calcul ; aucun SQL/API/ordre/règle modifié.
Résultats dans `us_oracle_path_loss_audit/20261014-v1` (identifiant de dossier),
[interprétation et limites](oracle_path_audit_pertes_20261013.md).

## 2026-10-13 — Oracle parcours LightGBM : replay économique lancé

GO utilisateur après comparaison d'amplitude et challenger LSTM. LightGBM
original figé, dernier fold 2023-01-05 ; CatBoost reste le champion de validation
de ce fold, LightGBM est ici un choix opérationnel explicite. TOP10/20/50 titres
par score, LONG-only non appris, TP20/SL10, sans trailing, vingt séances depuis
l'entrée J+1. Neuf portefeuilles annuels de 4 000 USD, moteur partagé et coûts.
Univers figé de 1 790 titres, aucune intersection ATR ; sizing ATR natif conservé.
2024/2025 avec leurs queues de liquidation ; 2026 limité aux décisions jusqu'au
2 septembre, sorties jusqu'au 2 octobre, faute de macro du 5 au 9 octobre.
Pas de filtrage sur labels futurs ni remplacement des candidats non qualifiés.
66 tests passent ; lancement vérifié à 23:24 Paris, PID lanceur 34616.
**Terminé à 23:34 Paris, neuf cas vérifiés** : rendements TOP10/20/50 2024
−1,07/−1,84/−1,84 %, 2025 −5,54/−4,49/−2,98 %, 2026 partiel
+9,23/+10,44/+9,01 %. Pas d'avantage LONG annuel constant ni de promotion.
Pas de SQL écrit,
d'entraînement, d'ordre ou de promotion ; suivi et réserves dans le
[protocole économique](oracle_path_backtest_economique_20261013.md).

## 2026-10-13 — Oracle parcours : challenger LSTM terminé, pas d'avantage stable

GO après confirmation LightGBM/CatBoost 2024–2026. LSTM global avec attention,
40 séances/173 features + masques, hidden 64, une couche, seed 42, max 10 époques,
patience 3, meilleure AUC validation. Dix folds identiques, cibles/rangs inchangés.
Copies LightGBM/CatBoost réentraînées sur les mêmes endpoints de séquences,
originaux intacts. Puis modèles du dernier fold figés pour 2024–2026.
Données des archives existantes uniquement, pas de SQL/ordre/promotions.
Population commune et couverture explicites ; pas une comparaison d'architecture
pure ni un PnL. 121 tests ciblés passent, dont un entraînement GPU réel.
Lancement vérifié à 21:28 Paris, PID 17772 ; cache construit, dix folds reconstitués,
premier fold apparié engagé. Aucun résultat LSTM historique encore conclu.
v1 interrompu après sauvegarde de l'époque 1 par une erreur du callback
de progression (`epoch` transmis deux fois). Correction de suivi seulement,
test ajouté ; reprise **v2 à 21:34**, cache/checkpoints contrôlés, protocole
scientifique inchangé. Le statut actif est dans `oracle_path_lstm/20261013-v2`.
PID actif 6284, premier fold/époque 3 vérifié RUNNING ; 122 tests passent après correctif.
État final v2 **COMPLETED à 22:54 Paris** : dix folds, 2 136 465 lignes OOF et
1 237 285 scores de confirmation. Hashes/source/causalité valides, scores finis,
zéro doublon. TOP10 précision (copies appariées) LightGBM / CatBoost / LSTM :
2024 **70,67 / 71,23 / 71,19 %** ; 2025 **78,32 / 78,08 / 79,96 %** ;
2026 partiel **76,54 / 76,54 / 72,16 %**, sur 153/173 dates matures communes.
Amplitude TOP10 LSTM : **21,00 / 28,16 / 27,11 %** pour ces trois années.
Bénéfice limité au TOP10 de 2025, pas TOP20/50 ; recul sur toutes les tailles
en 2026. Époque 1 retenue dans chaque fold, arrêt après 4 : compatible avec
surapprentissage/optimisation inadéquate, pas bug démontré. Une seule seed et
architecture testées ; pas de généralisation à tous les LSTM, aucun PnL.
**Pas de promotion du LSTM**, aucune nouvelle expérience lancée après audit.
[Protocole, budget, checkpoints et suivi](oracle_path_lstm_comparaison_20261013.md).

## 2026-10-13 — Oracle parcours : confirmation 2024–2026 lancée, résultats en attente

GO reçu après comparaison 2018–2023. Modèles fixes du fold 2023-01-05 : LightGBM,
CatBoost et champion de validation CatBoost. Dernières disponibilités des labels
train 2022-07-06 et validation 2023-01-04 : pas de fit sur toute l'année 2023.
Univers/profil figés 1 790 titres/173 features. Lectures SQL uniquement, aucun
training, recalibration, ordre, promotion ni nouvelle sélection sur le test.
Décisions 2024-01-01 → 2026-10-09 ; as-of 2026-10-09, maturité J+21 théorique
jusqu'au 2026-09-10. TOP10/20/50 d'origine conservés avant exclusions de
résultats manquants ; couverture et métriques conditionnelles séparées.
Calcul lancé à 20:50 Paris, PID 1752, progression dataset vérifiée (18/72).
280 tests ciblés passent. Aucun résultat empirique encore conclu.
[Protocole détaillé et suivi](oracle_path_confirmation_2024_2026.md).

## 2026-10-13 — Oracle parcours : comparatif tabulaire terminé, avantage CatBoost non stable

LightGBM/CatBoost sur mêmes features, labels et folds ; champion par AUC de
validation uniquement, égalité exacte LightGBM. Les deux poids et diagnostics
OOF sont conservés, tailles 10/20/50 titres distinguées des TOP10/20 %.
Calcul terminé à 20:32:52 Paris : 10 folds, 173 features, 2 146 823 lignes et
1 260 séances OOF (2018-07-05 → 2023-07-07), zéro doublon, hashes vérifiés.
Sur les 10 premiers titres : précision LightGBM **85,51 %**, CatBoost **86,89 %** ;
amplitude moyenne **35,29 % / 36,08 %**. Ce sont des vrais TOP20 % d'amplitude
capturés, pas trades gagnants ou direction. AUC agrégées **0,7991 / 0,8088**.
CatBoost gagne seulement 5/10 folds sur précision/amplitude TOP10 ; avantage
moyen principalement porté par le second semestre 2020. Sur les neuf autres
folds, delta précision −0,106 point et amplitude −0,351 point. Diagnostic
rétrospectif, pas une règle d'exclusion. Champions de validation : 6 CatBoost,
4 LightGBM, précision TOP10 agrégée 85,33 % ; pas d'amélioration de cette politique.
SQL en lecture seule, sans promotion de modèle ni ordre. Aucun test 2024–2026
ni PnL encore réalisé avec ces modèles. Pas de LSTM initial.
[Protocole et suivi](oracle_path_comparaison_20261013.md).

## 2026-10-13 — Oracle parcours H20 : raccordement technique, pas une nouvelle performance

Case parcours cochée par défaut, TP avant SL décochée. CLI predict, sélecteurs
IHM, table des scores + lineage compagnon, adaptateur `oracle_path_policy`,
gate risque exact date/batch/tradable et backtest `extreme_gate` raccordés.
Validation finale : 631 tests ciblés passants, dont vingt tests serving dédiés
avec LightGBM local. Deux tests de configuration obsolètes corrigés sans
changer l'horaire du batch ni restaurer un modèle supprimé.
Un modèle d'amplitude unique, aucune direction LONG/SHORT apprise. Politique
`long_only` explicite ou `abstain`, LLM séparé/PAPER uniquement. Kelly interdit
pour la force de rang. Aucun nouveau training réel, PnL, ordre broker ni
promotion de batch lancé pendant l'intégration.
[Contrat, utilisation et tables](oracle_path_training.md).
Ancien test de reset dangereux corrigé et garde de production ajoutée ;
[incident, attribution et limites](securisation_tests_reset_20261013.md).

## 2026-10-13 — Nouveaux modèles annuels TP20/SL10 : neuf cas vérifiés

Après la remise à zéro, modèles `f62825` (2024), `f1b59f` (2025), `9be3d2`
(2026) fournis par l'utilisateur. Contrats TP20/SL10 vérifiés : 1 790 titres,
173 features identiques. Folds retenus respectivement 2023-12-05, 2024-12-05
et 2025-12-10, fit et validation disponibles avant toute décision testée.
LONG uniquement, TOP10/20/50, capital annuel 4 000 USD, sans trailing,
2026 partiel jusqu'au 3 septembre. Aucun entraînement, SQL ou ordre broker.
Quatorze tests passent ; neuf cas terminés, zéro échec. Audit final
`NINE_CAUSAL_ANNUAL_CASES_VERIFIED`, cash réconcilié, aucune position résiduelle.
Contrats enregistrés : fins 2024-11-30 et 2025-11-30 pour les deux premiers,
contrairement aux 31 décembre annoncés ; troisième fin 2026-09-30 conforme.

| Année | TOP10 | TOP20 | TOP50 |
| --- | ---: | ---: | ---: |
| 2024 | +1,29 % | −7,06 % | −7,06 % |
| 2025 | +2,68 % | −4,53 % | +10,44 % |
| 2026 partiel | +9,73 % | +11,40 % | +11,40 % |

Amélioration 2025 face à l'ancien `6d6569`, mais forte dégradation TOP20/50
en 2024 et perte de rendement sur toutes les tailles en 2026. Pas de domination
stable ni promotion ; pas de nouveau challenger entraîné. Rapport détaillé
par année : gains/pertes, taux gagnants/perdants, capital final et DD maximal.
[Protocole, suivi et réserves](oracle_modeles_annuels_20261013.md).

## 2026-10-13 — Remise à zéro des modèles US

Suppression autorisée de tous les modèles US et des données ML associées :
seize tables ciblées vidées, 33 campagnes SQL, 19 dossiers de modèles US,
champions Oracle et poids de recherche identifiés. Suppression directe,
aucune nouvelle archive de modèles. Sources, CN/FR, ordres/fills/positions
et rapports historiques conservés. Les essais ci-dessous conservent leurs
conclusions mais ne disposent plus des poids supprimés pour une reprise.
Configuration d'entraînement TP20/SL10 ; ancien serving/configuration figée
retiré. Aucun nouveau training ou test économique lancé.
[Périmètre, contrôles et réserves de récupération](remise_a_zero_us_20261013.md).

## 2026-10-13 — Trois challengers TP20/SL10 terminés : aucun avantage robuste à promouvoir

GO explicite pour `model-factory-20261012183840-6d6569`, dans l'ordre :
filtre d'entrée avec TP20/SL10 inchangés ; sortie quotidienne avec stop dur ;
choix TP/SL prédéfini et sizing adapté. **Pas de réduction progressive
d'exposition**, pas de cumul des challengers ni modification live.
Fit OOF 2018–2021, validation 2022, trois années exploratoires 2024–2026
partiel ; TOP10 primaire, TOP20/TOP50 secondaires. 36 nouveaux replays
terminés, zéro échec en version finale :27 cas des trois expériences et9
contrôles de sizing. 59 tests ciblés, audit `THREE_CHALLENGERS_VERIFIED`.

| Année | Baseline TOP10 | Sortie quotidienne | TP/SL personnalisés |
| --- | ---: | ---: | ---: |
| 2024 | −2,26 % | −2,01 % | +14,22 % |
| 2025 | −12,01 % | +4,96 % | −12,23 % |
| 2026 partiel | +28,71 % | +1,83 % | +5,67 % |

Le filtre au seuil figé0,50 n'ouvre aucun trade ; AUC de validation0,50021,
scores de test0,4121–0,4286. Aucun gain démontré par cette abstention totale.
Sortie quotidienne avec SL10/TP20 durs : DD TOP10 réduit sur les trois années,
mais fort sacrifice de gains en2026 et pertes nouvelles sur TOP20/50 en2024.
TP/SL personnalisés : avantage2024 TOP10,2025 non corrigée, gains2026 sacrifiés.
Les profils choisis sont presque toujours TP10/SL7 ; pas de preuve que la
personnalisation apporte plus qu'un tel profil fixe. Aucun test supplémentaire
de profils/seuils lancé après lecture des résultats.

Le contrôle TP20/SL10 avec sizing adapté reproduit exactement les neuf
baselines, trades compris. Inférences des cinq heads, profils exécutés,
chronologie, candidats, disponibilité des labels, cash et sourcehashes vérifiés.
V1 bloquée par une queue de features vide ; V2 corrige seulement l'alignement
d'index du benchmark. Poids d'entrée/sortie et labels OOF inchangés, canaris
et causalité par préfixe vérifiés. Versions échouées conservées.
Pas d'entraînement de l'Oracle original, SQL, broker, batch ou configuration
live modifiés. Aucun challenger promu ou empilé ; tests déjà observés,
réserves survivants/secteurs/prix/vintages inchangées.
[Protocole et résultats détaillés](oracle_challengers_20261013.md).
Artefacts : `artifacts/research/us_oracle_challengers/20261013-v2`.

## 2026-10-13 — Garde progressive Oracle TOP50 : NO-GO intégration

GO utilisateur « fait ton choix » : une seule règle figée, pas de modèle
supplémentaire. TP20/SL10 `6d6569`, TOP50 LONG, mêmes scores/prix/coûts/lifecycle
que la baseline. À J, rendement cinq séances d'un panier composé des TOP50
connus chaque veille ; baisse absolue et relative SPY confirmée deux/quatre
séances → risque de nouvelles entrées plafonné à 50/25 %, reprise confirmée.
Régime macro/B4, stops, TP et échéance vingt séances inchangés. Cinq séances
initiales de warmup à 25 %, historique continu, capital annuel 4 000 USD.

| Année | Rendement baseline → garde | DD baseline → garde |
| --- | ---: | ---: |
| 2024 | +16,44 % → +5,02 % | −8,46 % → −9,16 % |
| 2025 | −6,05 % → −3,00 % | −16,26 % → −18,25 % |
| 2026 partiel | +21,43 % → +7,38 % | −9,10 % → −7,92 % |

La baisse de perte annuelle 2025 ne valide pas la protection : signaux de
février −482,42 USD contre −424,27 USD, DD aggravé, réduction B4 retardée du
3 au 27 mars par la trajectoire différente du portefeuille. L'exposition
effectivement atteinte peut augmenter malgré des tailles plafonnées, car
les entrées/slots et protections de portefeuille sont dépendants du chemin.
Forte perte de rendement en 2024/2026 : règle non intégrée ni réoptimisée.

Trois nouveaux replays terminés, 46 tests ciblés passent. Audit des trois
années, des candidats, de la causalité par préfixe, protections, cash et
empreintes : `THREE_YEARS_AND_CAUSAL_TAPE_VERIFIED`. Années déjà observées,
réserves survivants/secteurs actuels/prix et vintages non certifiés inchangées.
Aucun training, SQL, broker, configuration live ou batch modifié ; aucun
challenger ML suspendu lancé. [Protocole et résultats](oracle_exposure_guard_20261013.md).
Artefacts : `artifacts/research/us_oracle_exposure_guard/20261013-v1`.

## 2026-10-12 — Trois nouveaux modèles Oracle, TOP50 : neuf cas comparables

Identifiants utilisateur : `834576` **parcours H20**, pas Oracle terminal ;
`a769bb` TP20/SL7 ; `6d6569` TP20/SL10. Même univers de 1 790 titres, mêmes
173 features et fold 2023-01-05, poids figés. Aucun nouveau training, SQL,
batch, ordre broker ou challenger d'entrée/sortie/sizing lancé.

Comparaison des classements, **LONG uniquement, TP20/SL10 commun aux trois**,
trailing OFF, vingt séances, 4 000 USD réinitialisés par cas, contraintes et
coûts natifs, mêmes inputs réparés et lifecycle. Les noms SL7/SL10 décrivent
les labels d'entraînement, pas des protections différentes dans cette expérience.
2026 : décisions jusqu'au 3 septembre puis dénouements ; pas une année complète.

| Année | Parcours H20 | Training TP20/SL7 | Training TP20/SL10 |
| ---: | ---: | ---: | ---: |
| 2024 | +6,00 % | +2,03 % | +16,44 % |
| 2025 | −7,84 % | −13,98 % | −6,05 % |
| 2026 partiel | +8,64 % | +17,36 % | +21,43 % |

TP20/SL10 meilleur rendement des trois cohortes, mais 2025 reste perdante.
TP20/SL7 a le DD minimal 2026 (−5,79 % contre −9,10 % pour TP20/SL10), pas
sur les deux années précédentes. Neuf cas achevés et audités : mêmes candidats
avant inférence/prix/macro/lifecycle, protections et cash contrôlés ; les trois
références TP20/SL10 reproduisent exactement la baseline précédente.
Réserves communes survivants/secteurs actuels, vintages macro non certifiées,
prix ajustés fournisseur et corporate actions simulées ; aucune promotion LIVE.

Artefacts : `artifacts/research/us_three_oracle_comparison/20261012-top50-v1`,
rapports par année et global avec gains/pertes, compteurs, DD, tapes par cas,
`completion-audit.json`. [Protocole et résultats complets](comparaison_trois_oracles_top50_20261012.md).

## 2026-10-12 — Nouveau batch TP20/SL10 : baseline 2024–2026, neuf cas vérifiés

Modèle utilisateur `model-factory-20261012183840-6d6569`, deux têtes entraînées
TP20/SL10 ; dernier fold archivé utilisable 2023-01-05, pas un refit implicite
de tout 2023. Baseline **LONG uniquement**, TOP10/20/50, 4 000 USD par année,
TP20/SL10 au fill J+1, trailing OFF, sortie à l'ouverture de la 21e séance.
Décisions 2026 arrêtées au 3 septembre ; cohortes dénouées ensuite.

V1–V5 conservent les échecs AVB/TOELY. Features AVB et volumes BAND/GPRE/ATEX
raccordés aux prix locaux, rangs recalculés sans fit : scores 2024/2025 inchangés.
V6 qualifie TOELY → TELWY via les corporate actions Alpaca et les prix EODHD
archivés du successeur ; aucun titre retiré, aucune imputation de prix manquant.
Neuf cas terminés, contrats SL/TP/expiry et cash vérifiés, portfolios clos,
six références 2024/2025 reproduites exactement sur trades et compteurs.

Rendements TOP10 / TOP20 / TOP50 :

- 2024 : **−2,26 % / +16,44 % / +16,44 %**.
- 2025 : **−12,01 % / −7,03 % / −6,05 %**.
- 2026 partiel : **+28,71 % / +21,43 % / +21,43 %**.

TOP10 2026 : capital final 5 148,37 USD, net +1 148,37 USD, 140 positions,
51,43 % gagnantes, DD maximal −8,66 %. TOP20/50 identiques en 2024 et 2026
sur les trades exécutés, pas seulement les chiffres arrondis.
Recherche réservée : survivants/secteurs actuels, données ajustées actuelles,
macro/selector vintage non certifiée, migration de protections simulée et
exécutabilité historique Alpaca des ADR OTC non démontrée. La perte 2025
empêche de déclarer un avantage stable ou une promotion LIVE.

**Arrêt demandé par l'utilisateur après baseline : aucun challenger lancé.**
Les pistes filtre d'entrée, sortie quotidienne et TP/SL personnalisés restent
des protocoles préparatoires, nécessitant nouveau GO et qualification lifecycle.
Résultats : `artifacts/research/us_oracle_tp20_sl10_new/20261012-v6`, rapports
annuels, `baseline-report.md/json`, `completion-audit.json` et tapes par cas.
[Protocole, chiffres et limites](oracle_tp20_sl10_new_baseline_and_challengers_20261012.md).

## 2026-10-12 — Oracle SHORT forcé TP20/SL10 : six cas, NO-GO promotion

Demande utilisateur : forcer SHORT uniquement sur la tête SHORT figée, TOP10,
TOP20, TOP50, mêmes inputs réparés 2025 et décisions 2026 jusqu'au 3 septembre.
TP20/SL10 depuis le fill J+1, sans trailing, rachat à l'ouverture de la 21e
séance détenue ; 4 000 USD réinitialisés par cas. Aucun entraînement, SQL,
appel fournisseur, ordre broker ou changement de réglage PAPER/LIVE.
Contrôle natif TOP10 2026 : zéro trade, SHORT autorisé seulement sur deux dates
CP. Scénario forcé distinct : permission SHORT en NORMAL ajoutée explicitement
pour cette recherche, sans bypass des autres contraintes/cash-only/close-only.
Cap natif cinq SHORT, actions entières, emprunt supposé disponible et 0,3 %/an ;
locates/rappels/taux historiques/dividendes compensateurs non modélisés.
RARE exposait un défaut de partial fills synthétiques : 9 → 8,999999999 → 8
au commit. Contrôles V1/V2 conservés FAILED ; remplissages SHORT entiers corrigés,
pas de modification du chemin LONG par défaut. 240 tests ciblés passent.
Grille finale `short-forced-grid-20261012-v1` : **6/6 terminés exploratoires**, 347
positions auditées, empreintes vérifiées, cash max 2,73e-12 USD. TOP10 2026
reproduit exactement le contrôle V3 sur trades économiques.
Rendements 2025 / 2026 : TOP10 **+1,54 % / −14,50 %**, TOP20 **+1,21 % /
−14,10 %**, TOP50 **+1,21 % / −10,64 %**. DD 2026 −16,09 / −16,11 / −15,91 %.
Le profit LONG antérieur ne s'inverse pas simplement pour produire un SHORT.
NO_GO_FORCED_SHORT_PROMOTION_TP20_SL10 ; ni avantage stable, ni emprunt historique
qualifié, ni serving promu. Pas d'optimisation sur les pertes 2026.
[Protocole, résultats, comptes et limites](oracle_short_tp20_sl10_20261012.md).

## 2026-10-12 — Trailing Oracle TP20/SL10 : 35 cas vérifiés, NO-GO promotion

Précision utilisateur avant lancement : TP20/SL10 fixe. Trailing10 primaire,
sensibilités 5 et 15 %, deux modèles déjà figés, TOP10/20/50, 2025 et décisions
2026 jusqu'au 3 septembre. 36 nouveaux cas face aux références OFF déjà auditées.
Activation uniquement lorsque le stop suiveur ne relâche plus le SL initial ;
plus haut observé en J applicable à partir de J+1, gaps et collisions conservateurs,
vingt séances détenues puis sortie à l'ouverture de la 21e séance.
Recherche LONG seule : aucune production, SQL, entraînement ou ordre courtier.
24 tests nouveaux passent ; quatre cas de contrôle V2 terminés, deux OFF reproduits
exactement, 296 sorties trailing contrôlées avec les plus hauts antérieurs.
Campagne terminée dans `trailing-grid-20261012-v1` : 35 cas stricts vérifiés,
un cas ancien TOP50/trailing5 2026 bloqué par LBRDK/20 juillet à volume nul.
Statut global conservé FAILED/PARTIAL_FAILED ; aucun PnL du cas arrêté n'est publié.
8 565 transactions et 6 227 sorties trailing auditées contre high antérieur,
activation sans relâcher le SL et gap au prix d'ouverture ; cash max 5,00e-12 USD.
Tous les 18 cas du nouveau modèle terminent : trailing moins rentable dans 17/18,
DD amélioré dans seulement 2/18. TOP10 nouveau sans trailing +12,39 % / +18,93 %,
trailing10 −0,09 % / +7,90 % ; trailing15 +0,84 % / +15,97 %.
Ancien trailing5 meilleur en 2025, non confirmé sur les cas 2026 terminés.
Piste SIP LBRDK archivée mais OHLC différents aussi : pas de volume opportuniste
ajouté ; identité/chemin, inputs et scores communs à qualifier avant reprise.
Régression ciblée complète : 192 tests passent.
NO_GO_TRAILING_PROMOTION_TP20_SL10 ; ni optimum, entraînement, SQL ou live.
Rapport indépendant partiel : `partial-summary.json` / `partial-summary.md`.
[Protocole et suivi](oracle_trailing_grid_20261012.md).

## 2026-10-12 — Grille TP/SL 2025–2026 terminée, 2026 débloqué

Warm-up AVB/SPY archivé en SELECT uniquement. Contrôle de 380 dates × 129 features
antérieures à l'anomalie sans écart ; 405 lignes AVB régénérées et rangs quotidiens
communs recalculés, mêmes modèles entraînés. Scores 2025 strictement inchangés ;
AVB ne figure plus dans TOP10/20/50 du nouveau modèle, sans exclusion de l'univers.
Deux contrôles stricts TOP10 2026 terminés, cash réconcilié, aucune fraction
inconnue : TP20/SL7 ancien +9,03 %, nouveau +21,20 % après les dernières sorties.
Trois corrections de volume fournisseur déjà archivées, BAND/GPRE/ATEX le 18/06,
intégrées également aux features et rangs communs : 365 dates × 129 features
par titre avant correction sans écart. Scores 2025 inchangés ; 172 anciens scores
2026 changent, aucune nouvelle tête ne change. Ces preuves restent non PIT.
Campagne de cinq couples TP/SL + référence commune, deux années, deux modèles
et TOP10/20/50 : **72 cas terminés strictement, aucun échec**, V2 finale. Les
36 cas 2025 sont réutilisés après preuve exacte des inputs jusqu'à la queue
du 30/01 ; tous les cas 2026 repartent de zéro. V1 conservée : six échecs BAND.
14 119 transactions et cash vérifiés, erreur maximale 6,37 × 10⁻¹² USD ;
168 tests ciblés passent. Nouveau LONG supérieur dans 35/36 comparaisons,
exception TOP50 2026 TP10/SL7. TOP10 nouveau TP20/SL5 : +17,11 % en 2025,
+11,21 % en 2026 ; TP20/SL10 : +12,39 % / +18,93 % ; référence +7,33 % / +21,20 %.
Pas de couple dominant tous les nombres/périodes, ni GO LONG/SHORT ou live.
Aucun entraînement,
SQL écrit, modèle modifié, changement de production ou ordre courtier.
[Protocole, résultats complets et réserves](oracle_tp_sl_grid_20261012.md).

## 2026-10-12 — Rejeu AVB 2026 : lifecycle livré, validation prédictive réservée

État historique du premier scénario ; remédiation et grille finales ci-dessus.

Six scénarios LONG terminés, mêmes scores figés et TOP10/20/50 ; trois contrôles
stricts restent bloqués par la valeur/date inconnues des fractions. AVB converti
une fois en 2,793 actions du successeur, protections et expiry conservés ; aucun
prix post-radiation AVB fabriqué ni titre retiré. 657 dates rapprochées en SIP :
632 prix d'origine inchangés, seulement 25 dates de base mixte restaurées.
**Une contamination des features est confirmée** : fausse baisse AVB −63,69 %
le 13/07 contre +1,40 % en prix d'origine. Les sélections du nouveau modèle sont
donc réservées malgré le raccordement d'exécution. Son scénario cash + actions
entières, créance non valorisée exclue, donne +18,60 % / +17,47 % / +17,47 % après
sorties ; ce n'est ni une validation prédictive ni un rendement complet du
patrimoine. Aucun entraînement, score modifié, SQL écrit ou ordre courtier.
15 nouveaux tests spécifiques réussis ; erreurs de réconciliation cash <10⁻¹¹ USD.
[Rapport qualifié, réserves et traitement d'une exclusion AVB](oracle_merger_replay_2026_20261012.md).

## 2026-10-12 — Comparaison figée ancien/nouveau Oracle : TOP10/20/50

État historique, avant correction des features AVB/volumes ; la grille finale
ci-dessus remplace les résultats 2026, sans effacer les premières archives.

Nombres de titres, pas pourcentages. Deux branches figées, même univers de
1 790 titres et même archive de features, période externe 2025 → 03/09/2026.
Ancien Oracle H20 corrigé contre tête LONG TP-avant-SL du batch `867a1e`.
Même SL 7 %, TP 20 %, entrée J+1, expiry 21e séance à l'ouverture, sans trailing.
Mesures par candidat terminées : aucune des six comparaisons annuelles/count
ne démontre un taux TP supérieur pour le nouveau modèle. Direction automatique
0,55 : uniquement quelques SHORT 2025 sans TP, abstention complète en 2026.
**Six portefeuilles 2025 terminés** : cohorte close ancien/nouveau LONG,
TOP10 −5,42 % / +7,33 %, TOP20 −3,61 % / +12,05 %, TOP50 −4,91 % / +17,37 % ;
drawdowns plus faibles pour le nouveau. La queue ajoute janvier 2026 ; les
rendements au 31/12 sont distingués dans le rapport. **2026 non confirmé** :
remédiation cash-only terminée ; neuf portefeuilles complets / trois bloqués.
Ancien 2026, cohorte close : TOP10 +6,11 %, TOP20 −1,01 %, TOP50 +4,53 %.
Nouveaux replays bloqués par
la conversion réelle AVB → VMRK au 17/08. Pas de titre retiré après observation,
de liquidation fictive, de prix remplis, de promotion ni changement en production.
Une révision de `selector_short_score`
en SQL est documentée ; les inputs communs archivés ne sont pas écrasés.
130 tests ciblés réussis (64 modèle/audit, 66 comparaison/replay).
Bootstrap descriptif par blocs de vingt séances, inconnus conservés avec bornes.
Aucun entraînement, SQL écrit ou ordre courtier. Diagnostic borné AVB via
Alpaca SIP en GET uniquement et preuves publiques émetteur de la fusion.
[Protocole et résultats](oracle_barrier_comparison_top10_20_50_20261012.md).

## 2026-10-12 — Oracle TP avant SL : première campagne réelle et audit TOP10

Batch utilisateur `model-factory-20261011221400-867a1e` terminé : 1 790 titres,
173 features, 12 folds, OOF 2018-07-05 → 2024-07-09 (2025/2026 non testées).
Audit sur les dix premiers titres par séance, pas TOP10 % ; TP 20 % avant SL 7 %,
vingt séances, entrée J+1, seuil et modèles inchangés, inconnus non remplacés.
TOP10 LONG : TP 24,41 %, SHORT : 16,42 %. Maximum des deux scores puis argmax
sans seuil (diagnostic séparé) : 22,05 % contre 24,18 % toujours LONG sur les
mêmes observations qualifiées. Politique figée seuil 0,55 : 403 choix / 15 120,
24,63 % de TP contre 25,87 % toujours LONG sur les mêmes 402 choix qualifiés.
Argmax dégradé en 2023 et 2024 partielle ; en 2024, 1 241 SHORT / 59 LONG,
TP 8,15 % contre 20,38 % toujours LONG sur les mêmes candidats. Scores SHORT
surestimant globalement la fréquence TP 2024, sans preuve que la calibration
résoudrait le problème. Aucun calibrateur appris sur le test, aucun bug déclaré.
Contrôles de checksums, chronologie et comptages ; 64 tests ciblés passent.
Aucun réentraînement, modèle modifié, SQL écrit, ordre ou PnL portefeuille.
Verdict : classement par sens informatif, choix LONG/SHORT **non promu**.
[Protocole, résultats annuels/folds et suite](oracle_barrier_top10_audit_20261012.md).

## 2026-10-11 — Collecteur consensus EODHD prospectif

Souscription Calendar & News signalée par l'utilisateur ; compte et Trends HTTP 200.
194 lignes reçues sur deux titres en un appel par le nouveau collecteur, sans
écriture SQL pendant ce smoke. Nouvelle table dédiée et migration 0099 ;
aucune table Yahoo utilisée. Batch `eodhd_consensus_snapshot` initialement livré
désactivé, puis activé à la demande utilisateur ; 22h15 Paris / secours
conditionnel 4h15, notifications. Collecte élargie aux symboles de stock_bars_daily.
Dates fiscales conservées sans leur attribuer une disponibilité historique PIT.
Révisions baisse 7 jours absentes : NULL, non zéro. Aucun nouveau résultat ML.
Remédiation du même jour : le seuil de consensus 95 % est limité au fichier
tradable (1 778/1 790 déjà couverts, 99,33 %), les réponses vides et symboles
invalides sont distingués des pannes techniques. Un symbole 404 ne coupe plus
les sous-lots suivants ; smoke sans SQL sur ACHR.WS + ALLO : un identifiant
invalide, ALLO reçu avec 84 lignes, zéro panne technique. Compteurs d'échec
partagés entre module importé et CLI `python -m` ; anciens runs non réécrits.
[Mise en service et contrat](../operations/eodhd_consensus_snapshot.md).

## 2026-10-11 — Audit de remplacement des barres US EODHD par Alpaca SIP

Deux études de recherche, sans SQL écrit ni changement de production :
[échantillon de 24 titres et sensibilité du champion Oracle au volume](us_daily_alpaca_eodhd_oracle_audit.md), puis
[univers entier, janvier–septembre 2026](us_sip_daily_universe_2026_audit.md).
1 790 titres interrogés, 1 692 avec historique SIP, 313 408 barres comparées aux lignes locales toutes marquées EODHD.
99,501 % des couples titre/date ont leurs quatre prix à moins de 1 % ; 98 absences, dont 96 OTC identifiés actuellement.
1 563 couples sur 148 titres divergent de plus de 1 % ; contrôle raw/split des vingt principaux cas effectué.
Volumes quasi figés locaux repérés ; aucun prix ni volume corrigé.
436 correspondances supplémentaires par remapping sont archivées séparément, non intégrées automatiquement.
Verdict : candidat sérieux à la substitution sur un périmètre qualifié, pas remplacement intégral validé ni résiliation EODHD.
L'effet économique et les classements Oracle complets ne sont pas testés dans l'audit étendu.

## 2026-10-10 — Nouvelle désactivation de la collecte analystes Yahoo US

L'utilisateur a de nouveau désactivé `analyst_snapshot_collection`.
État vérifié dans `batch.yaml` : `enabled: false`,
`BLOCKED_YAHOO_AUTOMATED_ACCESS`. La réactivation temporaire et le retrait
de l'expiration décrits plus bas sont historiques, plus l'état courant.
Les données restaurées et les analyses sont conservées ; aucun effacement,
appel fournisseur ou changement de tâche Windows effectué pour cette mise à jour.
EODHD Calendar & News envisagé pour la collecte prospective, sans activation
ou achat confirmé. [État actuel](yahoo_analyst_pit.md).

## 2026-10-10 — Restauration consensus Yahoo et premier test directionnel

Sauvegarde du 4 octobre : 1 080 167 lignes réinjectées dans les six tables
analystes, sans écrasement ; contrôle ultérieur, zéro ligne archivée manquante.
Analyse sur les 1 790 titres tradables actuels, disponibilité PIT validée,
entrée prochaine ouverture, H3/H5/H10/H20 sans entraînement.
Révisions EPS nettes 30 jours : H10 AUC 0,679 sur dix dates ; TOP20 des scores,
D10 16,53 % contre 10,47 %, D1 6,59 % contre 10,23 %. Pas encore de révisions
matures à H20. Objectifs H20 instables et augmentant aussi D1 ; recommandations
sans gain de sélection TOP20. Échantillon court et chevauchant, aucune promotion
ni preuve économique. Quatre tests ciblés passent.
[Protocole, restauration et résultats](analyst_archive_restore_directional_20261010.md).

Suite du même jour : contrôle de momentum20 et des secteurs actuels non PIT,
sans entraînement. Sur la même couverture H10, AUC révisions30 brutes 0,695,
neutralisées 0,595 ; le TOP20 neutralisé donne D10 7,16 % contre baseline
11,26 %, malgré une AUC supérieure à 0,5. Les dix dates H10 ne fournissent
qu'une date sans chevauchement. Aucun GO économique : continuer la collecte
et confirmer sur de nouvelles périodes. Objectifs/recommandations testés sans
avantage de sélection convaincant ; niveaux EPS/revenus, nombre d'analystes et
références EPS J−7/30/60/90 non testés isolément. Un mois de snapshots ne crée
pas quatre mois de décisions PIT. Un test de contrôle supplémentaire passe.

## 2026-10-10 — Historique : réactivation temporaire Yahoo US, arrêt manuel

Sur GO explicite de l'utilisateur, `analyst_snapshot_collection` avait été réactivé
depuis le 10 octobre : statut
`ACTIVE_RESEARCH_RIGHTS_UNCONFIRMED`, permission Yahoo toujours non confirmée.
Tâche `AlphaTrade-AnalystSnapshot`, 22h Paris / secours conditionnel 4h, univers
`config/univers_batch/univers_filtred_tradable.txt`, notifications existantes.
Sur demande ultérieure de l'utilisateur, la borne du 10 novembre est retirée :
arrêt manuel via `enabled: false`, sans réinstallation de la tâche.
Pas de modèle ni de décision de trading raccordés.
133 tests ciblés passent ; tâche Windows vérifiée Ready, actions masquées,
timezone machine Romance Standard Time. Aucun téléchargement immédiat lancé
dans cette réactivation, aucun nouveau résultat directionnel. Bilan à faire après
un mois (couverture, vraies révisions, rollover, rendements à maturité), puis
arrêt ou nouvelle décision explicite. Les autres blocages US/FR/CN restent inchangés.
[Détails et suivi](yahoo_analyst_pit.md).

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Repère de lecture du **10 octobre 2026** : ce registre conserve les résultats
et lancements **datés**. Une section « en cours » décrit son état au moment
de l'inscription, pas nécessairement un processus encore actif aujourd'hui.
Pour les paramètres/branches actuellement raccordés, voir
[l'état de l'implémentation](../ETAT_ACTUEL_IMPLEMENTATION.md). La présente
mise à jour documentaire ne requalifie aucun résultat ni ne promeut un modèle.

## US — Collectes prospectives : audit de couverture et direction courte

10 octobre 2026 : audit terminé sur les **1 790 titres** du fichier tradable.
Options indicatives : 231 519 lignes / 1 651 titres ; barres options retardées :
188 444 / 1 569 ; disponibilité short : 36 554 / 1 751 ; news/sentiment du mois :
11 581 / 1 268. Consensus analyste et short volume FINRA vides/suspendus.
Contrôle figé sans entraînement : AUC D1/D10 H5 volume call/put 0,547,
H3 OI call/put 0,547 ; associations faibles, chevauchement, recul trop court,
aucune promotion ni PnL. Aucune option encore mature H20 au 9 octobre.
Deux réserves SEC identifiées : extraction 8-K/6-K très insuffisante et
`issuer_symbol` 13F alimenté avec le symbole du déclarant ; non corrigées ici.
Aucune écriture SQL, configuration modifiée, collecte externe ou ordre.
Cinq tests de recherche passent. Voir
[audit détaillé et suites bornées](us_collectes_prospectives_direction_audit_20261010.md).

## US — TOP10 Oracle H20 corrigé : backtests annuels 2020–2026 en cours

7 octobre 2026 : lancement de sept années × quatre variantes de sortie,
LONG-only, SL initial fixe 7 %, portefeuille partagé, coûts/risques/régimes.
Capital remis à 4 000 USD chaque année ; 2026 limitée au 3 septembre.
Classement par score prédit exclusivement, sans filtre positif/futur ni ATR.
1 677 séances couvertes, dix candidats chaque jour ; second semestre 2024
complété avec les features archivées et le dernier modèle déjà figé, sans
réentraînement. Contrôle court réussi sur les sept années ; ces contrôles de
trois séances ne sont pas des rendements annuels. 53 tests ciblés passent
(`--no-cov`, pas une validation de toute la suite). Résultats économiques
complets à lire uniquement après statut terminé de chaque variante ; toute
anomalie de prix/volume reste bloquante et explicite. Secteurs actuels NON-PIT
acceptés, univers reconstruit et macro non certifiée par vintage restent des
limites. Pas d'écriture SQL ni de changement de serving/batch existant.
Voir [protocole, suivi et limites](oracle_top10_annual_2020_2026.md).

## US — TOP10 Oracle H20 corrigé : audit terminé, pas de gain stable

7 octobre 2026 : vérification offline des **dix premiers titres**, classés par
score, pas des 10 % ni des dix meilleures amplitudes futures. Archives appariées
OOF 2018-07-05–2024-07-09 (1 512 séances), externe figée 2025–2026-09-03
(419 sélections quotidiennes, 418 évaluables). Capture Oracle TOP10 avant →
corrigée : 61,17 → 59,85 % en OOF, 55,74 → 55,26 % en externe. Amplitude
moyenne absolue corrigée 20,91 % / 17,51 %, pas un gain de portefeuille.
Les dix premiers corrigés sont déjà tous dans Oracle TOP20 ∩ ATR TOP20 :
les deux politiques choisissent exactement les mêmes titres sur chaque date.
En externe, 53,44 % de hausses, 46,41 % de baisses ; aucune direction démontrée.
La capture recule historiquement (intervalle descriptif de différence excluant
zéro) ; avantage externe des correctifs non démontré. Concentration, ex æquo,
prix extrêmes et dix labels absents du 3 septembre explicités. 27 tests ciblés
passent, sans certification de la suite complète. Aucun entraînement, SQL,
changement de serving ni PnL. Conserver les calculs justes.
Voir [audit détaillé, rangs, résultats annuels et limites](oracle_h20_corrected_top10_audit.md).

## US — Oracle H20 : effet des correctifs mesuré, pas de gain net démontré

7 octobre 2026, GO : deux bras réentraînés sur les mêmes 1 790 titres et caches
2016–2024, anciennes features archivées contre features corrigées. 173 colonnes,
12 folds de référence, 24 entraînements, mêmes paramètres Oracle et purge H20.
24 entraînements terminés, 1 512 dates OOF du 2018-07-05 au 2024-07-09 :
capture Oracle TOP20 40,379 % → 40,435 % (+0,056 point) ; intersection ATR
42,186 % → 42,115 % (−0,071 point). Intervalles descriptifs par blocs incluant
zéro ; aucun gain net de capture démontré. ATR témoin inchangé à 38,601 %.
AUC moyenne des folds 0,708763 → 0,711081, 9/12 améliorés, sans avantage net
du TOP20. Aucune écriture SQL, aucun remplacement du serving ni PnL.
239 tests ciblés passent (dont 40 sur les protocoles/audit/corrections).
Confirmation figée 2025-01-01–2026-09-03 terminée (419 séances), chaque modèle
recevant son propre calcul numérique ; commit legacy et empreintes archivés.
Capture externe Oracle 39,825 % → 39,748 % (−0,077 point), intersection
41,132 % → 41,240 % (+0,108 point). Intervalles descriptifs incluant zéro,
amplitude moyenne non améliorée. Conserver les calculs justes, sans promotion
automatique ni promesse d'alpha. 2026 déjà examinée, pas de holdout vierge.
Voir [protocole, limites et suivi](oracle_h20_numeric_effect.md).

## US — Correction facteurs CAPM et ratios EXPERT : code et audit comparatif VALIDÉS

7 octobre 2026, GO utilisateur : rendements benchmark dérivés des prix ajustés,
alignement exact sans rendement imputé ni variation multi-séance présentée comme
quotidienne, OLS sur paires finies et momentum relatif corrigé. Six ratios
EXPERT neutralisés si dénominateur ≤ 1e−8/non fini, sans plafond de sortie choisi
sur les performances. Version numérique du fingerprint EXPERT/facteurs mise à
jour ; colonnes inchangées, anciens modèles à réentraîner avant usage corrigé.
224 tests ciblés passent, incluant FR/CN. Aucun titre supplémentaire retiré ni
SQL écrit. Audit corrigé v2 lancé ; v1 partiel arrêté volontairement et conservé.
Comparaison des 72 lots de features terminée : mêmes 3 787 770 clés date/titre,
aucune ligne supplémentaire perdue ; RSI/volatilité >1 million de 870 à 0 et
log-return/range >1 million de 50 058 à 0, sans plafond imposé aux ratios valides.
La consolidation annuelle est terminée (9/9) : aucune nouvelle violation des
contrôles de labels ni feature émise non finie. SPY contre lui-même retrouve
R²=1 et momentum relatif=0. Une amélioration prédictive reste à mesurer.
Voir [détails, limites et suivi](oracle_numeric_feature_corrections.md).

## US — Audit complet du contrat Oracle H20 : TERMINÉ, corrections recommandées

7 octobre 2026 : audit de recherche terminé sur 1 790 titres, features 2016–2024,
profil du batch `model-factory-20261003082853-e98332`. 173 features, dont 44 rangs
cross-sectionnels reconstruits sur l'univers complet après assemblage des lots.
Labels H20 existants contrôlés séparément sur leur univers original, sans les
réécrire. 3 787 770 lignes de features émises ; 72 579 barres sans ligne (1,88 %),
aucun titre totalement absent. Zéro incohérence détectée dans les contrôles
réalisés sur 3 873 149 labels valides du batch original. Défaut confirmé : les
3 023 rendements SPY persistés sont NULL, transformés en zéro par le module
factoriel ; beta/alpha/R² restent aux défauts et le momentum relatif est affecté.
Ratios EXPERT dégénérés : 870 RSI/volatilité et 50 058 log-return/range dépassent
un million en amplitude, tous avec dénominateur ≤ 1e−8. Short score zéro sur
99,249 % des lignes (valeur par défaut possible). 28 tests ciblés passent. Aucun
entraînement, correction applicative, modification de modèle ni écriture SQL.
Voir [protocole, contrôles, limites et surveillance](us_oracle_h20_dataset_quality_audit.md).

## US — Recontrôle après huit exclusions : 1 790 titres

7 octobre 2026 : scan terminé sur 4 950 873 barres ; 14 grandes variations
sur 11 titres subsistent, contre 18 sur 14 avant le dernier retrait. Maxima :
rendement MFA +216,67 %, gap REPX +178,21 %, volatilité20 MFA 0,564659.
Les contextes événementiels documentés ne prouvent pas les cours exacts, mais
interdisent de classer tous les grands mouvements comme erreurs. Trois dates
supplémentaires EVVTY/REPX/KALV relues : sauts reproduits par le fournisseur.
21 tests passent. Aucun nouveau retrait, entraînement ni écriture SQL.
Audit limité à trois calculs de prix, pas certification de toutes les features.
Voir [résultats et limites](us_oracle_remaining_discontinuities_audit.md#contrôle-après-huit-exclusions--1-790-titres).

## US — Exclusion complémentaire BASFY / PECO / FBRT

7 octobre 2026, décision utilisateur : retrait des trois titres des fichiers
d'univers US, sans correction des historiques. Huit fichiers modifiés ; univers
tradable/equities de 1 793 à 1 790, univers large de 2 691 à 2 688. Contrôle des
24 fichiers : aucun des huit titres exclus depuis KNTK/AMTB ne subsiste ; autres
symboles et ordre conservés. Aucun modèle, batch ou ligne SQL modifié. L'audit
précédent reste celui des 1 793 titres, pas une certification des 1 790 restants.
Voir [décision et effectifs](us_oracle_remaining_discontinuities_audit.md#décision-ultérieure--exclusion-basfy--peco--fbrt).

## US — Contrôle des 1 793 titres après cinq exclusions

7 octobre 2026 : scan de 4 957 887 barres terminé ; 18 grandes variations sur
14 titres, avec une relecture fournisseur bornée pour chaque titre. BASFY
(ratio ADR), PECO (classes pré-IPO/IPO) et FBRT (échange CMO/FBRT avec espèces)
restent prioritaires. EVVTY et ASTH conservent des réserves de liquidité/identité.
Les événements documentés d'autres titres ne permettent pas de classer toutes
les grandes variations comme erreurs. 21 tests ciblés passent. Aucun retrait
supplémentaire, entraînement, écriture SQL ou changement de batch.
Voir [périmètre, chiffres, sources et réserves](us_oracle_remaining_discontinuities_audit.md).

## US — Exclusion complémentaire DEC / TALO / INDV

7 octobre 2026, décision utilisateur : retrait des trois titres des fichiers
d'univers US plutôt que réparation de leurs historiques. Neuf fichiers
modifiés ; univers tradable/equities de 1 796 à 1 793 et univers large de
2 694 à 2 691. Les 24 fichiers des trois répertoires US ne contiennent plus
KNTK, AMTB, DEC, TALO ou INDV ; autres symboles et ordre conservés. Aucun
modèle ni donnée SQL modifié. Le scan précédent reste celui de 1 796 titres,
pas une nouvelle certification des 1 793 restants. Maintenir les exclusions
aux prochains renouvellements d'univers.
Voir [détail de la décision](us_oracle_post_exclusion_price_audit.md).

## US — Contrôle des features après exclusion KNTK / AMTB

7 octobre 2026 : scan terminé sur 1 796 titres et 4 964 562 barres, sans SQL
en écriture ni entraînement. Les anciens maxima disparaissent, mais DEC
présente un saut local de +1 907 % au regroupement 20:1 du 5 décembre 2023 ;
la relecture split-only le ramène à +0,35 %. TALO (+811 % en 2016) et INDV
(+572 % en 2022) conservent leurs sauts chez le fournisseur : identité,
prédécesseurs, ADR et ajustements restent à qualifier. 23 grandes variations
sur 17 titres ne sont pas une liste de 23 erreurs certifiées. Quinze tests
ciblés passent. Aucun retrait supplémentaire de symbole.
Voir [résultats, sources et prochaines vérifications](us_oracle_post_exclusion_price_audit.md).

## US — Retrait KNTK et AMTB des fichiers d'univers

7 octobre 2026 : décision utilisateur de retirer ces titres plutôt que de
réparer leurs historiques à ce stade. Sept fichiers modifiés dans
`config/univers`, `config/univers_batch` et `config/univers_bis`. Univers
tradable/equities : 1 798 → 1 796 titres ; univers large : 2 696 → 2 694.
Vérification des 24 fichiers de ces répertoires : aucune occurrence restante,
autres symboles et ordre conservés. Aucun modèle, processus, prédiction ou
ligne SQL modifié. Les anciens modèles ne sont pas réparés rétroactivement.
Maintenir l'exclusion lors des renouvellements d'univers.
Voir [l'audit et les limites](us_oracle_feature_outliers_audit.md).

## US — Futurs positifs du TOP10 réel H20, SL initial 7 % : LANCÉ

7 octobre 2026 : TOP10 figé d'abord par amplitude absolue réalisée, puis seuls
les positifs qualifiés conservés, sans remplacement. 3 133 occurrences retenues
sur 4 189 qualifiées (419 dates, univers 1 798 titres). Même archive de barres,
stop initial 7 %, quatre variantes et refus de budget explicite. 17 tests ciblés
passent, smoke trois séances terminé. Chaque variante est tentée indépendamment,
sans contourner un éventuel défaut de prix/volume. Connaissance du futur volontaire,
pas une validation prédictive ou une stratégie déployable ; aucun SQL ou entraînement.
Voir [protocole et suivi](us_realized_top10_positive_fixed_sl7.md).

## US — TOP10 des mouvements réels H20, SL initial 7 % : RELANCE APRÈS CORRECTIF

7 octobre 2026 : classement clairvoyant par amplitude absolue sur l'univers
1 798 titres, deux signes achetés LONG. 419 dates matures, 4 190 candidats,
dont un endpoint KLAC non qualifié exclu sans remplacement. Onze tests ciblés
passants. Smoke arrêté au premier achat J+1 sur PGNY : budget insuffisant pour
la quantité approuvée ; aucun PnL complet ni quatre runs lancés. Politique de
refus/redimensionnement à qualifier avant reprise ; aucun contournement.
Voir [protocole et blocage](us_realized_top10_fixed_sl7.md).

Après GO : refus explicite de l'ordre devenu incompatible avec le budget à
l'ouverture, sans resize ni débit, diagnostic détaillé. Mode strict inchangé
par défaut. Smoke v2 quatre variantes réussi ; 72 tests ciblés passants.
V2 : référence TOP10 prédit terminée, résultats inchangés, zéro refus.
Réel TOP10 : deux variantes avec TP terminées à +89,97 % (4 000 → 7 598,63 USD),
drawdown −36,65 %, 520 trades, 19 refus explicites. Trajectoires identiques
avec/sans échéance 20 séances. Sans TP/stop fixe bloqué après 365/437 séances :
ATEX volume nul le 18 juin 2026. Sans TP/trailing non lancé. Aucun résultat
complet pour ces deux dernières variantes ; qualification de volume requise.

## US — TOP10 complet, stop initial fixe à 7 %

7 octobre 2026 : quatre variantes terminées sur janvier 2025–septembre 2026.
TOP10 Oracle sans filtre futur ; stop initial à 93 % du fill réel, sizing,
TP et trailing inchangés. Les gaps peuvent dépasser 7 % de perte.
Comparateur : TOP10 complet ATR précédent, pas référence à labels observables.
Sans TP/sans trailing/échéance vingt séances après entrée : **+27,88 %**
(ancien ATR −2,52 %), 4 000 → 5 115,19 USD, drawdown −13,30 %, 300 trades,
28 % gagnants. Sans TP/avec trailing : +21,57 % (ancien +4,23 %).
Avec TP : encore perdant. Forte concentration des profits sur les meilleurs
trades ; variante exploratoire, pas de validation directionnelle ni promotion.
63 tests ciblés passants ; aucun entraînement ni SQL ni changement de production.
Voir [protocole et suivi](us_oracle_top10_fixed_sl7.md).

Suite Oracle × ATR TOP10 : quatre variantes terminées à SL initial 7 %.
L'intersection TOP20 % puis dix meilleurs Oracle donne exactement les mêmes
4 370 occurrences que le TOP10 Oracle seul sur ces 437 séances. Replay de
contrôle terminé : trajectoires quotidiennes, trades et métriques strictement
identiques au TOP10 Oracle seul. Aucun bénéfice additionnel de ce filtre sur ce jeu.
Deux nouveaux tests de sélection passent avec les huit tests de stop.

## US — Oracle TOP10 avec direction positive parfaite (contrefactuel)

7 octobre 2026 : huit replays terminés, référence TOP10 à labels observables contre
les seuls futurs positifs H20 du TOP10 initial, sans remplacement des exclus.
4 190 occurrences évaluables sur 4 370, dont 2 290 positives. Quatre sorties
figées, portefeuille réel simulé à 4 000 USD avec coûts et risque.
**Connaissance du futur volontaire : aucune capacité D1/D10 démontrée ni stratégie
déployable.** Sans TP, stop initial et échéance 20 séances après entrée :
−3,29 % pour la référence contre +195,62 % avec filtre positif parfait
(4 000 → 11 824,71 USD, drawdown −6,49 %, 148 trades). Les autres sorties
parfaites donnent +121,80 % à +141,98 %. Potentiel économique, pas signal validé.
Smoke terminé ; 17 tests ciblés passants. Aucun entraînement ni SQL.
Voir [protocole et résultats](us_oracle_top10_perfect_direction.md).

## US — Ancien bundle : diagnostic mensuel de la dégradation 2026

5 octobre 2026 : diagnostic des prédictions récupérées et labels H20 reconstruits
en lecture seule. Janvier est mauvais ; février et mars ne montrent pas une
dégradation uniforme. **Audit descriptif du contexte terminé, aucun veto robuste :
régime normal en janvier et forte concentration TTD. Attribution
portefeuille bloquée par les rapports anciens absents.** Aucun entraînement,
veto macro ou changement de production.
Voir [méthode, chiffres et limites](us_degradation_commune_2026q1_audit.md).

Suite du 5 octobre : [répétition et fiabilité LONG](us_bundle_repetition_fiabilite_long_audit.md)
terminées. Un signal par titre toutes les 20 séances ne résout pas janvier.
AUC opérationnelles globales 0,439–0,516 selon fenêtre, sans classement stable.
Scores presque constants sur certains titres : réserve technique à vérifier,
pas de bug démontré ni nouveau filtre promu. Dix tests ciblés passent.

Suite technique : [scores constants PENN/ROKU/GH](us_bundle_probabilites_constantes_diagnostic.md).
LONG CatBoost/vector, 501 dates par titre ; calibration fortement aplatie plausible,
mais artefacts absents des quatre sauvegardes : cause historique non certifiée.
Défaut séparé reproduit sur états à température négative : incohérence fit/predict.
Audit initial : 17 tests ciblés passants. Après GO, correctif de positivité et de
validation des états appliqué à Temperature/Vector Scaling : 89 tests ciblés
passent. États positifs compatibles ; anciens modèles et SQL inchangés. Ce correctif
ne certifie pas la cause et ne promet pas de résoudre les scores constants.

## US — Ratio D10/D1 et contexte macro : validation chronologique

**Décision du 5 octobre 2026 : EN VEILLE — corrélations confirmées,
exploitation prédictive et économique non démontrée.** Pas de suite immédiate,
pas de filtre LONG/SHORT ni de veto ajouté au régime de production. Cette
décision ne rejette pas définitivement toute information macro directionnelle.

Conditions de reprise :

- Historique prospectif macro/sentiment avec disponibilités et versions
  traçables, et lineage Oracle qualifié.
- Nouvelle période suffisamment longue avec labels H20 maturés ; la
  suffisance doit être définie dans le protocole, pas décidée après résultats.
- Hypothèse, variables, références et critères de validation figés avant
  consultation des nouveaux résultats, puis nouveau GO explicite.

Ne pas chercher davantage de seuils sur le même historique pour corriger les
périodes perdantes. Les corrélations restent descriptives ; leur intégration
au trading nécessiterait un avantage OOS stable puis une validation économique
avec coûts et risque. Aucun nouveau calcul ou entraînement n'est programmé.

Suite : [audit PIT/lineage](us_d10_d1_ratio_audit_pit_lineage.md). Aucun champion
futur observé dans 3 618 577 lignes ; agrégats macro/sentiment largement
reconstruits tardivement, versions historiques non certifiées. Pas de correction
attestée ni rejeu artificiel, aucune modification de production.

4 octobre 2026 : [rapport et protocole](us_d10_d1_ratio_validation_chronologique.md).
Corrélations du document GPT reproduites sur 1 676 ratios. Features macro
décalées d'une séance et entraînement purgé par maturité des labels H20.
La combinaison VIX/structure/variation/sentiment n'améliore pas stablement
les références en 2023–2025 ; 82 dates 2026 favorables mais non vierges et
couverture clairsemée. `NO_STABLE_INCREMENTAL_REGIME_SIGNAL`, aucun GO de
production ni bénéfice économique démontré. SQL en lecture seule.

## US — Intégration optionnelle du filtre Oracle × ATR

4 octobre 2026 : [contrat backtest et live](oracle_atr_amplitude_gate.md).
Filtre d’amplitude activé par défaut, désactivable par
`cascade.oracle_atr_enabled: false`. Aucun changement d’entraînement ni des
prédictions persistées. L’intégration ne constitue pas une validation de la
direction D1/D10 ou de la rentabilité économique ; les conclusions de l’audit
historique ci-dessous restent celles d’un enrichissement d’amplitude.

## US — Désaccord Oracle × ATR H20, audit figé

4 octobre 2026 : [protocole](us_oracle_atr_desaccord_protocole.md),
[résultats](us_oracle_atr_desaccord_resultats.md). 3 196 186 observations,
1 821 séances, 2019–2025 + T1 2026. BOTH/Oracle seul/ATR seul/NEITHER :
41,76/34,37/25,70/14,08 % vrais extrêmes. À strates date/ATR/vol60 communes,
Oracle ajoute +11,34 points d'extrêmes, positif dans chaque année, mais
augmente aussi D1. Oracle seul T1 2026 : D10 15,73 %, D1 19,35 %, H20
moyen −0,59 %. Avantage amplitude historique, pas de solution directionnelle
ni de GO production. Deux tests passent ; aucun fit ni SQL write.

## US — Actualisation macro 2026 du régime LONG

4 octobre 2026 : [recalcul détaillé](us_2026_regime_macro_actualise.md).
Couverture VIX/VXN/VIX3M/MOVE complète janvier–juin (123 lignes), analyse
des candidats figés du T1 uniquement. Modes archivés et build_snapshot
séquentiel/hystérésis concordent : blocage LONG le 30 mars, 29 exclusions.
H20 moyen +8,29 % après régime contre +8,68 % avant ; janvier/février
inchangés. Aucun réentraînement ni SQL write ; couverture ancienne absente
supersédée, réserves de vintage et de backtest économique maintenues.

## US — Confirmation figée secteur/breadth et régime LONG

4 octobre 2026 : [protocole](us_confirmation_secteur_breadth_protocole.md),
[résultats](us_confirmation_secteur_breadth_resultats.md). Huit variantes
sans fit ni SQL write. Le régime archivé n'exclut aucun des 502 candidats
de février 2025 (−13,74 % H20 moyen). RS+breadth ne confirme pas un gain
stable : 2023–2025 D10 24,69 % contre 24,78 %, D1 24,11 % contre 22,71 % ;
T1 2026 rendement +0,65 % contre +8,68 %, seulement 17,79 % des D10
conservés. Secteurs actuels non PIT, macro incomplète en 2026, pas de parité
intégrale régime ni de PnL économique. Deux tests ciblés passent. Aucun
GO production, aucune recommandation de retirer les protections existantes.

## US2025-COMBINATION — blocs momentum/volatilité/sentiment : exploratoire

4 octobre 2026 : [protocole et résultats](us_2025_combinaison_features_d10.md).
Sept scores de blocs à poids égaux,TOP10/TOP20 du pool ATR20×Oracle.
M+V TOP10 :6 814couples,32,05 %D10/20,08 %D1,+4,91 %rendementH20brut
contre22,18 %D10/+2,51 %pourlepool. Mseul/Vseul≈29 %D10 ; l'ajout de
sentiment dégrade M+V. Février :44,42 %D1 et−13,74 %brut ; M+V dépasse les
deux blocs en rendement seulement3mois/12. Piste à confirmer multi-années,
pas de validation indépendante sur2025, aucun PnL net/fit/SQL/GOlive.

## US2025-FEATURES — comparaison D1/D10 de 281 features : exploratoire

4 octobre 2026 : [audit détaillé et interprétation](us_2025_features_separation_d1_d10.md).
Intersection ATR20×Oracle :12 177D1/14 877D10. Momentum120 relatif meilleur
en H2 (AUC0,5730) qu'en H1 (0,5154), signe brut instable. Volatilité60 plus
régulière :AUC relative0,5329/0,5395,11mois/12positifs ; effet faible.
Sentiment agrégé≈hasard.14colonnes constantes,28constantes par date ;
consensus forward absent, valeurs imputées non assimilables à une source.
Rangs initiaux parmi futurs extrêmes corrigés sur tous les candidats à J ;
utiliser le rapport `feature-separation-review-20261004-v1/report.json`.
PIT/multiplicité/secteur/symboles non qualifiés :aucun GO trading, fit ou SQL.

## US2025 — ATR × Oracle H20 et news à sentiment > 0,9

Lancement du 4 octobre 2026 : [protocole et surveillance](us_2025_atr_oracle_news_sentiment.md).
Univers `univers_filtred_tradable.txt`, batch `model-factory-20261003082853-e98332`.
Expérience descriptive terminée : recouvrement TOP20 ATR14/ATR20 et Oracle
74,07 % / 74,54 %, aucune séance >=90 %. P(TOP20 | news >0,9 avant J)
19,12 % positif / 24,37 % négatif, base20,02 %. Parmi Oracle+news avant J,
hausses H20 57,36 % positif / 56,62 % négatif : négatif ≠ signal SHORT.
206 409 observations sentiment datées 2025 mais créées après 2025 : PIT non
certifié, résultats rétrospectifs sans causalité/GO trading. Pas de fit ni SQL.
Rapport : `artifacts/research/us_atr_oracle_sentiment/audit-20261004-v1/report.json`.
Compléments terminés le même jour : intersection ATR20 × Oracle =14,92 %
de l'univers ; vrais D1/D10 =18,15 %/22,18 %. Quatre variantes sentiment
comparées dans cette intersection : maximum à J, maximum sur chacune des
quatre séances J−3/J, tous les articles scorés sur quatre séances, puis
tous les articles scorés à J uniquement. Cette dernière retient 1 610
couples positifs (25,78 % D10 ; 18,88 % D1) et 1 948 négatifs (17,56 % D1 ;
21,61 % D10). Quatre séances avec tous les articles :0positif/5négatifs,
support non interprétable. **Enrichissement positif modeste, pas de signal
SHORT démontré ; aucun GO économique/PIT.** « Tous » porte sur le corpus
scoré, pas sur les éventuels articles sans inférence. Les variantes explorées
sur la même année ne sont pas des confirmations OOS indépendantes.
Règles exactes, tableaux D1–D10, artefacts, reproduction et limites dans la
[synthèse dédiée](us_2025_atr_oracle_news_sentiment.md#synthèse-des-variantes-testées--mise-à-jour-du-4-octobre-2026).
Seuil >0,95 à J (tous articles scorés) :447positifs/25,06 %D10 et
1 334négatifs/17,62 %D1. Cap dix par séance, classement par minimum du
jour :447positifs inchangés et1 270négatifs/17,80 %D1. Pas d'amélioration
directionnelle convaincante ; détails/reproduction section16 du même doc.
Ajout SMA5/10/20/50/100 au seuil >0,9 à J :576positifs au-dessus des cinq
moyennes,26,74 %D10 et20,31 %D1 ;757négatifs au-dessous,15,19 %D1 et21,40 %D10.
Petit enrichissement D10 sans amélioration démontrée, dégradation D1.
Moyennes ajustées incluant J, corpus scoré/PIT toujours réservés ; section17.
Ce lancement ne commence pas le Sprint 13 France.

## FR12-F — priorités fiscales Oracle et opérations sur titres, partiel

4 octobre 2026 : [dossier détaillé](../fr/sprint_12f_priorites_fiscales_operations_titres.md).
Classement de 40 titres affectant les intentions Oracle, sans lecture des
rendements. Rapports officiels X-FAB archivés : siège/action ordinaire et
absence de dividendes 2024–2025 documentés. Continuité fiscale annuelle et
autres familles CA non qualifiées ; Nexity 403. Aucun changement modèle,
serving ou table ; aucun alpha démontré. 11 tests ciblés 12-E/12-F passent.

## FR12-D — levée gratuite des blocages, partielle

Actualisation :137/209positifs,72inconnus sur47titres ; ADP2cas etArtois1cas
ajoutés par archivesEuronext/AMF. Overlay de refusArtois qualifié pour1intention,
sans tape économique réelle.28tests ciblés passent. Dividendes/couvertureCA
et revue juridique des autres cas toujours ouverts ; aucun achat/backtest.

[Bilan et travail restant](../fr/sprint_12d_levee_blocages_gratuits.md).
Revue des97inconnus initiaux :22positifs supplémentaires,134/209qualifiés,
75inconnus sur49titres ; aucune exonération déduite. Refus causal sans ouverture
implémenté et testé, pas encore de tape réelle promue. Pièce Ipsos archivée
confirmant paiement1,85EUR le3juillet2025, ex-date toujours inconnue. STIF :
paiement proposé, archive403, aucune admission.26tests ciblés etRuff passent.
**0chemin promu, aucune performance, aucune demande payante.** Les recherches
gratuites ne sont pas déclarées épuisées ; réserves de couverture CA maintenues.

## FR12-C — preuves fiscales et économiques, qualification partielle

[Bilan détaillé](../fr/sprint_12c_qualification_preuves_execution.md).
112/209couples titre/année TTF positifs rapprochés deBOFiP/ESMA,97inconnus.
Calendrier standardEURT+2 documenté, pas des règlements réellement observés.
Termes Planisware et paiement/montant Virbac corroborés séparément.
Euronext confirme Artois sans ouverture/transaction ;4autres dates2024 hors
fenêtre publique. Aucun chemin promu ni PnL, aucune réparation source ou fit.

## FR12-B — moteur de rejeu économique, données réelles bloquées

[Contrat et fonctionnement](../fr/sprint_12b_moteur_rejeu_economique.md).
Moteur LONG EUR indépendant US/CN, sizing frais inclus, coûts distincts,
cash/trades réconciliés, créances dividendes après vente et splits simples.
Audit des21 379 chemins :0qualifié, pas de fill ni PnL historique calculé.
Fiscalité ISIN/date, règlement, prix/statuts et preuves CA encore requis.
Tests synthétiques uniquement pour la mécanique ; pas de résultat ML ni GO live.

## FR12-A — qualification coûts/taxes/CA partielle

[Bilan et conditions de rejeu](../fr/sprint_12a_couts_taxes_operations_sur_titres.md).
Coûts génériques utilisateur configurables, composantes séparées. TTF historique
0,3 % puis0,4 % au1er avril2025 vérifiée BOFiP ; mappingISIN non qualifié.
21 379 chemins/118 titres :20 932 sans événement déclaré,388 champs dividendes
complets à revoir,50 bloqués dividendes,9 bloqués prix. Zéro modification source,
fit, SQL/live ou performance2026. Scénario de coûts prêt ; rejeu économique toujours bloqué.

## FR 11-A économique — préflight réalisé, rejeu bloqué

[Protocole et preuves](../fr/sprint_11a_references_economiques.md).
Tests6/7 :21 379 candidats disponibles,52 scores OOF absents selon labels futurs
complétés avec les fits arbres gelés, sans réentraînement. Scores connus identiques
à1e−12 ; intentions ATR/Oracle/contrôle uniforme exportées, aucun fill.
`BLOCKED_ECONOMIC_REPLAY` : PIT/CA économique non qualifiés, coûts/taxes FR inconnus.
Pas de résultat net, SQL/live/évaluation2026. Le Sprint11 événementiel reste distinct.

## FR Sprint 10-C1 — réparation fold3 : `BLOCKED_NO_VERIFIED_SOURCE_REPAIR`

14 997 candidats sur177 séances non utilisables tracés vers le manifeste ; six
publications ESMA non retrouvées (index0, noms directs testés404), 138 dates
touchées, écarts de prix indépendants également présents. Masque des14 features
identique au recalcul. Aucune donnée forcée, aucune correction source vérifiée :
fold3 toujours705/882. 105 tests FR passent ; zéro fit/SQL/évaluation2026.
[Rapport et conditions de déblocage](../fr/sprint_10c1_reparation_fold3.md).

## FR Sprint 10-C — qualification OOF : aucune extension admise à ce stade

Huit folds H5 revus sous train cumulatif et glissant504 : seuls4/5/6 complets
dans les deux plans, 459 séances potentielles, zéro nouveau fit/score. Fold3
cumulatif705/882 (79,93197 %, manque1 séance qualifiée) ; fold7 test99/126
(manque2), lacunes mars/avril2025. Exports détaillés par séance pour réparer à
la source sans assouplir les gates. 102 tests FR passent, 2026 intacte.
[Audit et plan de réparation](../fr/sprint_10c_qualification_historique_oracle_oof.md).

## FR Sprint 10-B — mutualisé H5 : `LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS`

Oracle arbres fixé, scores VAL/test hors fit dédupliqués causalement : 7 385
événements / 459 séances. Folds directionnels4/5 bloqués, seul6 entraînable
(219 séances, 3 438 lignes). Logistique choisie sur VAL AUC0,5383 ; test0,5023
contre momentum20 0,5245, LONG brut −0,495 %. Arbres test0,5556 non retenus
sur VAL : ne pas les promouvoir a posteriori. Un seul OOS, zéro évaluation2026,
aucun SQL/serving. 95 tests ciblés FR passent. Voir le
[rapport et protocole 10-B](../fr/sprint_10b_modele_directionnel_mutualise_h5.md).

## FR Sprint 10-A — direction H5 après Oracle : `NO_GO_FROZEN_REFERENCE`

5 362 candidats OOF Oracle sur 339 séances / 3 folds, 75 UID FR. AUC D10/D1
aléatoire 0,4838, momentum 5 jours 0,4887, momentum 20 jours 0,5194.
Le dernier score donne IC +0,0712 mais reste sous le gate AUC 0,53 ;
LONG perdant sur un fold, janvier 2025 partiel négatif. Support suffisant,
deux déciles inconnus dans le pool conservés au classement. Aucune direction
exploitable démontrée ; aucun modèle directionnel entraîné, aucun test 2026,
aucun SQL/serving. Voir le [rapport Sprint 10-A FR](../fr/sprint_10a_diagnostic_directionnel_h5.md).

## Pilote US H20 ATR contre Oracle — `HISTORICAL_AMPLITUDE_INCREMENT / QUALITY_RESERVE`

Archive OOF E22 O0, 12 folds, 1 512 séances (juillet 2019–juillet 2025),
2 557 086 lignes communes : précision TOP20 Oracle 44,19 %, ATR20/prix
42,54 %, aléatoire 20,02 %. Oracle gagne 12/12 folds, écart +1,65 point,
recouvrement 81,16 %. Hors 80 séances autour des splits NVIDIA : +1,61 point.
Les archives du réentraînement corrigé sous `work/` sont absentes ; ce test
historique ne valide pas le dernier Oracle corrigé ni la direction D1/D10.
Aucun entraînement, serving ou changement SQL. Voir le
[protocole et rapport détaillés](us_h20_atr_vs_oracle.md).

## Pilote borrow PIT après Oracle — `SAMPLE_READY / BLOCKED_NO_PROVIDER_HISTORY`

Un échantillon déterministe de 50 titres, 29 267 événements Oracle TOP20,
huit années et cinq quintiles de liquidité est prêt. Le contrôle PIT exige
frais d'emprunt, quantité disponible, identifiant permanent et disponibilité
avant 09:25 ET à la séance suivante. Aucun extrait fournisseur n'est présent :
pas de couverture réelle, d'entraînement ou d'AUC. L'historisation Alpaca
prospective fournit 22 734 lignes sur 13 jours seulement et aucun fee/quantité.
Un audit des RAW retrouve 156 statuts faussement non shortables sur 12 tickers,
causés par des doublons d'actifs ; le collecteur est corrigé pour les prochains
runs, les lignes passées restant à corriger ou exclure. Voir [le protocole de
faisabilité](borrow_pilot_feasibility_20261001.md).

## Oracle O0 corrigé, 14 folds OOF, puis P0g — `REFIT_COMPLETE / NO_GO_DIRECTION`

L'Oracle d'amplitude O0 a été réentraîné hors base sur ses 14 folds gelés après
reconstruction des prix NVIDIA et des cibles Oracle. Ses 2 908 295 prédictions
OOF donnent AUC 0,758141 et précision TOP10 50,435 %, proches du P0f publié.
Le TOP20 conserve 582 700 événements mais échange 9 041 entrées et sorties.
P0g a été rejoué sur ce nouveau gate, avec ses 84 features recalculées et ses
neuf fenêtres gelées : AUC D1/D10 0,481115 sur 179 475 observations OOS et
IC quotidien −0,029740. Sur 176 598 événements communs avec le rejeu à gate
fixe corrigé, l'AUC recule de 0,488053 à 0,480660. Pas de promotion ni
d'écriture SQL. Voir [le rapport complet](oracle_split_corrected_oracle14_p0g_replay_20261001.md).

## Replay P0g après correction des splits NVIDIA — `FIXED_ORACLE_GATE / NO_GO_DIRECTION`

Prix NVIDIA reconstruits sur base post-2024 pour 2 014 barres réelles, avec
facteurs 1/40 avant le split 2021 puis 1/10 avant celui de 2024. Les 40 labels
H20 traversant ces dates sont recalculés : rendement −4,27 % à +43,05 %, aucun
ne reste D1, 17 deviennent D10. Sur 69 136 labels valides des 40 dates,
304 déciles et 80 cibles Oracle extrêmes changent. Le jeu P0g à gate Oracle
OOF historique contient les mêmes 582 700 événements TOP20, 84 features et
neuf fenêtres de test que le P0g publié. Dans un replay apparié avec mêmes
features corrigées et même environnement, l'AUC D10/D1 passe de 0,5004
(anciens labels, 179 605 lignes OOS) à 0,4882 (labels corrigés, 179 612 lignes).
IC directionnel quotidien −0,0107 → −0,0212. Les scores Oracle amplitude
n'ont pas été réentraînés : résultat de sensibilité, pas un replay complet
Oracle → P0g. Aucun changement en base ou en serving. Voir
[le rapport de replay](oracle_split_corrected_p0g_replay_20260930.md).

## Audit des splits Oracle du 30 septembre 2026 — `QUARANTINE_RESEARCH / P0G_AUC_UNRECOMPUTED`

Sur 2 493 symboles et 4,93 M de barres réelles, 390 événements de split
Alpaca dédupliqués sont comparés aux prix locaux : 356 cohérents avec un
ajustement, 31 indéterminés, trois candidats non ajustés (NVDA 2021/2024,
SBS 2026). Quarante labels H20 NVIDIA précédemment valides et D1 traversent
les deux splits ; SBS n'a pas de label exposé. Un override de recherche met
ces 40 lignes en quarantaine et recalcule les rangs sur 40 dates. Dans le
TOP20 Oracle, 21 lignes sont écartées, 32 autres changent de décile, et le
nombre net D1 passe de 4 435 à 4 429 sur le panel de 56 dates étudié ; D10
reste à 3 635. UCO est testé séparément comme cas incertain. Un écran des
ruptures extrêmes trouve aussi 47 sauts sans split Alpaca proche, dont neuf
touchent des labels valides ; ils ne sont pas supprimés automatiquement.
L'AUC P0g 0,4904 ne peut pas être recalculée sans ses prédictions/artefacts
absents ; `NO_GO_DIRECTION` reste le verdict publié. Voir
[l'audit détaillé](oracle_split_label_audit_20260930.md).

## Recouvrement Oracle et dates officielles du 30 septembre 2026 — guidance

Statut : `INCONCLUSIVE / ZERO_PIT_ELIGIBLE`.
Les cinq révisions du pilote ont une ligne OOF, mais aucune n'entre dans le
TOP20 % brut d'Oracle ; leurs déciles réalisés sont D4/D7/D9/D8/D8. Sur 38
publications, trois seulement entrent dans ce TOP20 %, toutes `GROWTH_ONLY`.
Un second tirage figé avant lecture des sources et des labels compte 12 couples
émetteur/date : sept dates du calendrier sont décalées par rapport aux sources
officielles ; dix restent dans le TOP20 % à la date corrigée, sans remplacement.
Jointure temporelle stricte prototypée et testée, zéro événement réel admissible
faute d'horloges de décision/disponibilité et de revue indépendante.
Suivi : BBWI est un premier candidat de révision de ventes parmi les titres
Oracle présélectionnés (milieu −1,75 point), mais le score pertinent avant sa
publication matinale serait celui du 27/08, non celui du 28/08. Les labels
clôture→clôture existants passent de D3 à D8 en décalant la date d'un jour :
cible à reconstruire depuis l'entrée effective, aucune preuve prédictive.
GEO fournit un contrôle négatif : malgré une annonce de guidance « mise à jour »,
le revenu annuel annoncé reste environ 2,4 Md USD dans les deux publications.
Prototype de label ouvert→ouvert H20 exécuté sur BBWI, score du 27/08 puis
entrée théorique le 28/08 : −9,12 %, D1 provisoire dans 1 847 titres. Un
report d'une séance donne −1,42 %, D3 provisoire sur une autre cohorte.
Dans la base locale, seulement une barre quotidienne et aucun instant historique
de réception validé : résultat descriptif, pas backtest PIT.
Suivi intrajournalier : 60 minutes historiques Alpaca SIP BBWI récupérées
rétrospectivement pour le 28/08/2024. Rendement brut H20 selon ouverture
09 h 30 / 09 h 45 / 10 h 00 : −9,12 % / −5,94 % / −6,81 %, sans décile
transversal aux deux heures retardées. Les tables PIT locales commencent en
septembre 2026, donc aucune réception 2024 prouvée. E20-D reste NO_GO agrégé.
Tri supplémentaire des dix sources encore TOP20 % à la date officielle :
BBWI seule baisse chiffrée des ventes annuelles, BFH et GEO contrôles de
revenu inchangé, GL hausse de bénéfice opérationnel par action, MAC retrait
de guidance EPS/FFO, AR révision de prime gazière, AAL maintien de l'EPS,
HP capex à comparer, PEGA ACV et EBC outlook bancaire à résoudre. Familles
de métriques à garder séparées ; aucune nouvelle ligne PIT-éligible ni
entraînement D1/D10.
Autre tirage figé de 12 titres sur scores TOP20 % du calendrier et de sa
veille supposée, sans labels : 9/12 dates de calendrier sont décalées, donc
leurs scores sélectionnés ne précèdent pas la vraie date de publication.
Après correction, 11/12 restent TOP20 % ; LUV en sort. Le symbole PRKS en
2023 désigne un émetteur coté alors SEAS ; le contrôle local voit le même
instrument_id 23592 avant/après, soit un alias historique à dater.
Deux autres baisses de ventes annuelles figées avant les cibles : HAYW
−1,5 point et FMC −0,20 Md USD. Leurs proxies ouvert→ouvert H20 donnent
+2,95 % / D9 et +3,87 % / D8, contre −9,12 % / D1 pour BBWI. Le signe
de la révision ne suffit pas ; zéro nouvelle ligne PIT-éligible.
Audit des attentes historiques : 218 068 snapshots Yahoo REVENUE mais première
observation le 29/08/2026 ; zéro pour HAYW/FMC/BBWI avant leurs annonces,
zéro ligne REVENUE dans l'autre table de consensus. Le gap de l'ouverture
après annonce est positif pour HAYW/FMC et négatif pour BBWI, diagnostic
postpublication non utilisable pour une entrée à cette même ouverture.
Jointure as-of étendue aux guidances de croissance des ventes via une base
annuelle positive et comparable, avec abstention si elle manque ; 12 tests.
Audit du panel prospectif : Oracle OOF s'arrête au 30/06/2026, les dépôts SEC
locaux commencent le 13/09 et les barres journalières SPY s'arrêtent au 10/07.
Le canary ne possède pas d'artefact dans ce checkout. Les 54 517 lignes Yahoo
de revenu `CURRENT_YEAR` sont toutes à horizon relatif, sans exercice fiscal
identifié ; une surprise de guidance FY ne peut pas y être jointe telle quelle.
Statut inchangé : zéro décision Oracle + guidance + consensus PIT-éligible.
Journal prospectif P0j ajouté : timestamp UTC post-calcul, batch, champion,
score et rang TOP20 en JSONL sans label futur ; un replay ancien est exclu.
Les tests du journal passent. Aucun run courant ici : barres SPY arrêtées
au 10/07 et artefacts de champions/baseline absents de ce checkout.
Précontrôle P0j ajouté : un run quotidien implicite sur date ancienne est
bloqué avant écriture. L'audit du prix alternatif trouve 1 660 titres Business
Quant `raw` au 28/09, mais zéro SPY ; aucune insertion canonique ajustée.
Champions et baseline non retrouvés ; cinq tests du journal/précontrôle passent.
Pilote Alpaca SIP quotidien (lecture seule) : 60/60 couples titre-séance
SPY/AAPL/BBWI/HAYW/FMC communs avec EODHD ont la même clôture, et sept
séances de septembre sont accessibles pour les cinq titres. Contrôle de
splits : NVIDIA juin 2024 n'est pas ajusté dans `stock_bars_daily` malgré le
marquage `split`. Dix-neuf labels H20 du batch Oracle sont D1 avec rendement
−85,70 % à −89,72 % et qualité marquée valide ; l'ajustement 10:1 du prix
de départ donne +2,77 % à +43,05 % avant recalcul des déciles. Trois autres
fenêtres de split contrôlées concordent. Pas de switch fournisseur ni de
réécriture des labels ; audit global des ruptures nécessaire.
Voir [rapport et protocole](guidance_oracle_overlap_and_calendar_20260930.md).

## Vérification SEC du 30 septembre 2026 — cinq candidats guidance

Statut : `BLOCKED_FOR_ML_EVIDENCE_IMPROVED`.
Index 8-K et EX-99.1 retrouvés pour les cinq candidats ; anciennes valeurs
Autodesk corroborées. Sous convention horaire New York, trois acceptations
SEC sont postérieures à 16 h et deux antérieures à 09 h 30. Aucun cutoff
réel de batch Oracle certifié ; acceptation distincte de diffusion/réception.
Accès direct SEC : HTTP 403, aucun brut SEC archivé. Comparabilité comptable
Autodesk et change COLM documentés ; revue indépendante encore absente.
Contrôles locaux et frontières temporelles vérifiés, zéro événement ML-éligible.
Voir [preuves et limites](guidance_pit_followup_20260930.md).

## Pilote de référence du 30 septembre 2026 — guidance, dix émetteurs

Statut : `REVIEW_READY_PARTIAL_EVIDENCE_NOT_ML_READY`.
Sur deux fenêtres avril–août 2023/2024 : 38 publications inventoriées,
20 bruts archivés, 18 téléchargements échoués avec lecture web complémentaire.
13 objectifs annuels absolus chez trois émetteurs ; cinq révisions nominales
candidates (trois OLD/NEW explicites, deux comparaisons entre publications),
trois comparaisons inchangées. 37 propositions de classement et un cas CAT
en revue incomplète. Pas de vérité terrain humaine indépendante, de PIT validé,
de mesure prédictive ou d'événement ML-éligible. Aucun réglage du parseur.
Voir [rapport et inventaire sourcé](guidance_reference_pilot_20260930.md).

## Audit documentaire du 30 septembre 2026 — guidance

Statut : `DOCUMENTARY_FEASIBILITY_ONLY / DATA_NOT_READY_ML`.
Relecture E21-B4 à B8 et audit statique du collecteur, du parseur et de
l'appariement. Les artefacts historiques E21 ne sont pas présents dans ce
checkout. Sur six publications officielles de DECK/ULTA/ETSY sélectionnées
avant lecture : deux révisions explicites de ventes chez ULTA, un objectif
ponctuel nominalement inchangé chez DECK avec périmètre à vérifier, aucune
paire annuelle de revenus en dollars identifiée chez ETSY. Zéro événement
ML-éligible : revue humaine indépendante et disponibilité historique non
validées. Aucun rendement utilisé, aucun entraînement, aucune B9 ou modification
de production. Voir [audit et sources](guidance_feasibility_audit_20260930.md).

## Objet et règle de lecture

Ce document est l'index central des expériences ML et des recherches directement
liées à la sélection Oracle, à l'amplitude, à la direction et à leur
monétisation. Il doit être complété après chaque nouvelle campagne, y compris
lorsque son résultat est négatif.

Les documents historiques décrivent le protocole et les résultats observés à
leur date. Le code source, les contrats d'artefacts et les prédictions OOF restent
les sources de vérité pour reproduire une expérience. Un `GO_RESEARCH` autorise
une étape de confirmation ; il n'autorise jamais automatiquement le serving.

### États employés

| État | Signification |
|---|---|
| `GO` | gates de l'étape franchis ; la portée exacte est précisée |
| `GO_RESEARCH` | signal à confirmer, non déployable |
| `WEAK_SIGNAL` | information faible ou instable, sans promotion |
| `NO_GO` | hypothèse rejetée dans le contrat testé |
| `INCONCLUSIVE` | données, couverture ou période insuffisantes |
| `IN_PROGRESS` | campagne en cours, aucune conclusion définitive |
| `PROPOSED` | protocole préparé mais non exécuté |
| `STANDBY_ABONNEMENT` | protocole prêt, suspendu jusqu'à disponibilité du forfait requis |
| `ABANDON_COÛT` | source ou expérience volontairement arrêtée car l'accès requis est payant |
| `BLOCKED_NO_PIT_HISTORY` | hypothèse non rejetée, mais aucune source historique PIT suffisante |

## Résumé décisionnel actuel

1. **Oracle Extreme détecte réellement l'amplitude** : E6-A passe ses six
   gates OOF avec une relation monotone entre score et excursion future.
2. **La direction reste non résolue** : les formulations statiques,
   per-symbol, mutualisées, pairwise, path-aware, first-touch, régime et
   screener n'ont pas produit un avantage LONG/SHORT stable.
3. **Le long straddle est rejeté, y compris avec DTE adapté à l'horizon** :
   E6-B2 reste négatif à H3/H5/H10/H20. Les moyennes vont de `-14,39 %` à
   `-29,68 %`, les médianes sont toutes négatives et seulement 0 à 2 dates sur
   8 sont positives selon l'horizon.
4. **Aucune famille Eroya testée n'est promue**. Quelques effets descriptifs 
   existent, mais pas de gain directionnel Walk-Forward suffisamment stable.
5. **La surface Options directionnelle 45 DTE est rejetée** : aucune feature ne
   passe les gates préfixés. Les deux effets descriptifs H10/H20 sont instables
   et défavorables au SHORT ; le volume historique est non testable.
6. **Temporal D1/D10 V2 est fermé en `NO_GO_DATASET_A`** : sur 399 symboles,
   T0 Logistic reste meilleur à 0,5143 d'AUC same-date. Le meilleur T2
   logistique tombe à 0,5112 ; le plus grand delta T2 est +0,0066 mais avec une
   AUC absolue de 0,4961 et des buckets inversés. Dataset B/C n'est pas ouvert.
7. **E9 ferme la confirmation directionnelle post-signal** : attendre le close
   J+1/J+2/J+3/J+5 puis entrer à l'open suivant ne révèle pas le sens restant.
   La politique primaire D2 atteint 49,40 % de précision et -0,309 % net par
   date ; les groupes désignés SHORT continuent en réalité de monter.
8. **E10 rejette l'interprétation pullback LONG** : l'avantage découvert dans
   E9 ne se confirme pas du 10 juillet 2024 au 11 juillet 2025. Le delta
   quotidien contre Oracle LONG au même open vaut -0,056 point, IC95
   [-0,603 ; +0,436], avec 1/2 folds et 1/3 semestres favorables.
9. **Le diagnostic J+N sépare la reconnaissance du décile final du gain restant** :
   sur 582 306 signaux Oracle TOP20 OOF, le signe du prix atteint environ 80 %
   de reconnaissance D10 parmi les futurs vrais D1/D10 à J+8, mais seulement
   35,9 % de probabilité D10 parmi tous les candidats haussiers. Sur les D10
   reconnus, l'attente a déjà consommé environ 11,6 points de rendement net ;
   aucune règle LONG/SHORT J+1…J+19 ne bat le LONG Oracle immédiat dans ce
   diagnostic descriptif. Voir [révélation et coût d'attente](oracle_revelation_jn_vs_cost_of_waiting.md).

## Campagnes directionnelles récentes après Oracle

| ID | Expérience | Population/cible | Résultat essentiel | État | Documentation |
|---|---|---|---|---|---|
| D0 | Bundle Oracle + deux modèles Per-Symbol | Oracle Extreme puis branches ternaires LONG et SHORT par ticker | Architecture entraînement/prédiction/backtest rendue cohérente, mais la direction per-symbol conditionnelle n'a pas généralisé à 2026H1 | `NO_GO` ML pour le batch étudié ; capacité technique conservée | [Bundle Oracle + Per-Symbol](per_symbol/07_bundle_oracle_long_short.md) |
| D1 | Classifieur mutualisé D1/D10 | D1 contre D10 dans Oracle TOP20 OOF | Sans contexte : AUC 0,503 et IC quotidien +0,004 ; contexte symbole/secteur dégrade | `NO_GO` | [Modèle mutualisé](shared_directional_oracle_events.md#campagne-initiale-du-5-septembre-2026) |
| D1-P | Ranker pairwise D1/D10 | PairLogit groupé par date | AUC 0,500, IC +0,006 ; faible purification instable | `NO_GO` | [Objectif pairwise](shared_directional_oracle_events.md#objectif-pairwise) |
| E1 | Rendement signé continu multi-horizons | Rendements H3/H5/H10/H20 dans Oracle TOP20 OOF | IC proche de zéro, signe correct inférieur à 50 %, branche SHORT négative | `NO_GO` | [E1](shared_directional_oracle_events.md#e1--rendement-signé-continu-multi-horizons) |
| E2 | Deux probabilités indépendantes | `P(Hx >= +3%)` et `P(Hx <= -3%)` | SHORT rejeté partout ; petit signal LONG H3, AUC moyenne 0,544 et 9/9 folds > 0,50, mais probabilités mal calibrées | `GO_RESEARCH` LONG H3 uniquement | [E2](shared_directional_oracle_events.md#e2--deux-probabilités-directionnelles-indépendantes) |
| E2-B | Calibration imbriquée et confirmation LONG H3 | Platt sur validation de chaque fold, test OOF puis confirmation 2026H1 | Confirmation AUC 0,536 mais aucun lift top10 suffisant ; gates de confirmation et développement non franchis | `NO_GO` | [E2-B](shared_directional_oracle_events.md#e2-b--confirmation-long-h3-avec-calibration-imbriquée) |
| E3-A | Rentabilité path-aware binaire | Replay LONG et SHORT séparé, stop 2,5 ATR, TP 3 ATR/7 %, H20 | LONG AUC moyenne 0,541 mais lift économique -0,064 point ; SHORT AUC 0,508 et top10 -0,624 % | `NO_GO` | [E3](shared_directional_oracle_events.md#e3--deux-têtes-de-rentabilité-conditionnelles-au-chemin) |
| E3-A2 | Utilité économique path-aware | Rendement net prédit moins pénalité de perte extrême | IC fold LONG +0,009, SHORT -0,010 ; aucun côté ne passe les gates | `NO_GO` | [E3-A2](path_aware_economic_utility.md) |
| E3-R | Veto de risque path-aware | Rejeter les événements au risque extrême prévu | Réduit certains risques mais conflit avec la sélection de tête ; stabilité insuffisante | `NO_GO` production | [E3-R](path_risk_veto.md) |
| E3-D | Direction par asymétrie du tail-risk | Comparaison du risque prévu LONG contre SHORT | Décision correcte 49,9 %, lift négatif, aucun avantage au meilleur côté statique | `NO_GO` définitif pour cette formulation | [E3-D](path_risk_direction.md) |
| E4 | Première barrière symétrique touchée, quatre classes | `UP_FIRST`, `DOWN_FIRST`, `AMBIGUOUS`, `NO_TOUCH` | Surabstention et absence d'avantage directionnel stable | `NO_GO` | [E4](first_touch_directional.md) |
| E4-B | Première barrière, contrôle binaire | `UP_FIRST` contre `DOWN_FIRST`, cas ambigus retirés | AUC fold 0,501 ; couverture 4,10 %, précision 41,09 %, rendement -2,36 % | `NO_GO` | [E4-B](first_touch_binary.md) |
| E5 | Direction quotidienne du régime Oracle | Choisir un côté commun pour tout le panier du jour | Ridge Spearman 0,000 ; CatBoost -0,008 ; aucune stabilité exploitable | `NO_GO` | [E5](oracle_daily_regime_direction.md) |
| R1 | Ranker conditionnel au TOP20 Oracle | Ranking de rendement réel uniquement dans le pool Oracle | Retest batch corrigé : H3 IC +0,0148/spread +0,12 % ; H20 IC +0,0260/spread +0,67 %, mais stabilité insuffisante et LONG/SHORT `NO_GO` | `NO_GO` confirmé | [Ranker conditionnel](conditional_oracle_ranker.md) |
| C1 | Consensus des modèles OOF existants | Moyenne équipondérée de rangs quotidiens, 2 à 7 familles selon H3/H5/H10/H20, sans réentraînement ni optimisation | IC -0,0014 à +0,0118, inférieur au meilleur composant ; SHORT signé négatif partout ; unanimité et régime E5 ne sauvent pas la direction | `NO_GO` | [Audit de consensus OOF](oof_consensus_audit.md) |
| E9-A | Confirmation directionnelle après Oracle | Observer le prix à J+1/J+2/J+3/J+5, puis entrer LONG/SHORT au prochain open ; seuils choisis sur folds antérieurs | Primaire D2 : 49,40 % de précision, -0,309 % net quotidien, 1/12 folds positifs ; les signaux SHORT montent encore de +1,8 % à +3,2 % | `NO_GO`; E9-B fermé | [E9](oracle_post_signal_confirmation.md) |
| JN-H20 | Révélation progressive vs coût d'attente | Oracle TOP20 OOF, observation du rendement J→J+N pour N=1…19, entrée open suivant et sortie H20 d'origine | Reconnaissance parmi vrais tails 70 % à J+4, 80 % à J+8, 90 % à J+13, mais gain D10 consommé et aucune supériorité économique de la règle simple | `DIAGNOSTIC_NO_GO`, sans promotion | [Courbe J+N](oracle_revelation_jn_vs_cost_of_waiting.md) |
| E10 | Pullback LONG après Oracle | Seuil choisi sur E9 puis gelé à -0,25 % ; confirmation Oracle H20 OOF du 2024-07-10 au 2025-07-11, entrée LONG open J+2 | +0,732 % net quotidien mais benchmark +0,788 % ; delta -0,056 point, IC95 [-0,603 ; +0,436], 1/2 folds positifs | `NO_GO`; E10-B fermé | [E10](oracle_pullback_long.md) |
| T-V2-A | Temporal D1/D10 V2 — Dataset A | État J contre trajectoires `[J-N,...,J]`, N=3/5/10, Logistic/CatBoost/PairLogit, labels H20 autoritatifs | 21 variantes, 399 symboles ; T0 Logistic 0,5143, meilleur T2 Logistic 0,5112 ; aucun gain T2 >= +0,01, aucun candidat servable | `NO_GO_DATASET_A` final | [Temporal D1/D10 V2](temporal_d1d10_v2.md) |
| S1 | Règles screener PIT post-Oracle | Signaux screener LONG/SHORT H3/H10/H20 | Couverture fraîche 10,44 %, meilleurs effets instables ; aucun gate LONG/SHORT | `NO_GO_PREDICTIVE` | [Screener post-Oracle](screener_post_oracle.md) |
| S1-D | Recontrôle screener sur panel dense | Six signaux quotidiens recalculés sur tout le pool | Couverture réparée mais verdict prédictif inchangé | `NO_GO_PREDICTIVE` | [Panel dense](panel_screener_dense.md), [résultat](screener_post_oracle.md#source-dense-recommandée) |

## Campagnes directionnelles antérieures retrouvées dans les archives ML

Ces campagnes précèdent la série E1–E6. Elles sont importantes car plusieurs
hypothèses récentes en sont des reformulations. Elles ne doivent pas être
relancées sans information nouvelle.

| ID historique | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| GD-H20-V1 | GlobalDirection binaire D1/D10 | Modèle partagé avec features directionnelles minimales ; purification non monotone, seulement 2/3 folds favorables | `NO_GO` | [GlobalDirection H20](../experiences/archives_recherche/global_direction_h20.md#v1-binaire-seul-2026-08-26-premier-run) |
| GD-H20-C1/C2/C3 | Cibles binaire, ordinale et rank | D1 parfois réduit mais D10 non monotone ; rendement inférieur aux baselines | `NO_GO` intermédiaire | [Comparaison C1/C2/C3](../experiences/archives_recherche/global_direction_h20.md#c1-binaire--c2-ordinal--c3-rank-2026-08-26) |
| GD-H20-C4 | Ajout des features sectorielles | Échec des cinq critères pré-enregistrés contre B1 ; BAD5 augmente et GOOD5 diminue | `NO_GO` final | [Test sectoriel](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-SEP | Séparabilité univariée des features existantes | IC maximum 0,033, AUC direction maximum 0,515 ; les meilleures features expliquent davantage l'amplitude | `NO_GO` | [Séparabilité GlobalDirection](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-T0 | Audit de couverture temporelle | Historique `stock_scores_history` initialement trop discontinu pour les trajectoires | `INCONCLUSIVE_COVERAGE` initial | [Audit temporel](../experiences/archives_recherche/global_direction_temporal.md#audit-de-couverture-stock_scores_history-2026-08-26--insuffisant) |
| GD-T1 | Backfill PIT puis dérivées J-3/J-5/J-10 | 252 résultats : 0 GO, 108 NO-GO et 144 couvertures insuffisantes ; meilleure AUC environ 0,51 | `NO_GO` | [GlobalDirectionTemporal](../experiences/archives_recherche/global_direction_temporal.md#construire-la-couverture-via-le-backfill-pit-2026-08-27--résultat-inchangé) |
| DDR-1 | Estimates et révisions fondamentales | Données de consensus historiques absentes ; proxies trailing sans signal | `NON_TESTABLE` / `NO_GO` proxies | [DirectionalDataResearch — famille 1](../experiences/archives_recherche/directional_data_research.md#famille-1--estimateearnings-revisions-2026-08-26) |
| DDR-2 | Sentiment news événementiel | IC maximal absolu 0,028, AUC autour de 0,49–0,50 | `NO_GO` | [DirectionalDataResearch — famille 2](../experiences/archives_recherche/directional_data_research.md#famille-2--news-sentiment-événementiel-2026-08-26) |
| DDR-3 | Short interest et short volume historiques | Huit features, AUC maximum 0,501 et IC maximal absolu 0,044 | `NO_GO` | [DirectionalDataResearch — famille 3](../experiences/archives_recherche/directional_data_research.md#famille-3--short-interest--short-volume-2026-08-26) |
| DDR-4 | Options skew et insiders, premier audit | Options absentes de la base historique à cette date ; insiders non exploitables proprement | `NON_TESTABLE` historique | [DirectionalDataResearch — famille 4](../experiences/archives_recherche/directional_data_research.md#famille-4--options-skew--insiders-2026-08-26) |
| DDR-5 | Surprise earnings et distance aux résultats | `earn_surprise_eps_prev` AUC 0,519 et IC +0,034 stable, mais lift de tête nul et AUC sous le gate ; relecture 14 octobre : disponibilité/vintage PIT non démontrés par la jointure sur earnings_date | `WEAK_SIGNAL`, non promu, PIT à requalifier | [DirectionalDataResearch — famille 5](../experiences/archives_recherche/directional_data_research.md#famille-5--analyst-surprise-earnings--days-to-earnings-2026-08-27) |

Attention : l'ancien indicateur `dir_vs_amp` de
`modelFactory/global_direction/temporal.py` possède une définition amplitude
incorrecte. Les AUC directionnelles des campagnes GD-T restent utilisables, mais
leur comparaison direction/amplitude doit être recalculée avant réutilisation.

## E6 — amplitude Oracle et monétisation direction-neutral

| ID | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| E6-A | Audit OOF de l'amplitude Oracle | 600 717 observations ; TOP20/REST80 environ +86 % d'excursion relative ; Spearman quotidien 0,551 à 0,570 ; 6/6 gates | `GO` amplitude, pas direction | [Audit amplitude](oracle_amplitude_audit.md) |
| E6-B0 | Faisabilité historique des options | Snapshot local insuffisant ; REST historique utilisable, flat files bulk non autorisés dans le trial | `GO` pilote REST ciblé, `NO_GO` bulk actuel | [Faisabilité options](oracle_options_feasibility.md) |
| E6-B1 | Long straddle ATM fixe ~45 DTE | 588 événements, entrée NBBO 67,52 % ; rendement ask→bid négatif à H3/H5/H10/H20, jusqu'à -29,68 % à H20 | `NO_GO` pour 45 DTE fixe | [Résultat E6-B1](oracle_options_feasibility.md#résultat-e6-b1--straddle-45-dte) |
| E6-B2 | DTE adapté à chaque horizon | 588 événements sur 8 dates. Couverture H3/H5/H10/H20 : 43,71/42,35/23,13/41,33 %. Rendement net moyen : -15,76/-14,39/-22,33/-29,68 % ; médiane : -17,49/-19,31/-25,21/-33,22 % ; dates positives : 1/8, 2/8, 0/8, 0/8 | `NO_GO` ; adapter le DTE ne répare pas le straddle long | [Résultat E6-B2](oracle_options_feasibility.md#résultat-e6-b2--dte-adapté-à-lhorizon) |
| E6-B3 | Confirmation options indépendante | Était conditionnée au franchissement des gates E6-B2, qui ont échoué | `NO_GO` pour l'escalade du straddle long ; non exécutée | [Décision E6-B2](oracle_options_feasibility.md#verdict-e6-b2) |

## Nouvelles données directionnelles — campagnes Eroya et autres sources

Toutes ces expériences utilisent ou visent la population Oracle TOP20 OOF. Les
effets exploratoires ne sont pas des règles de production.

| Famille | Données testées | Conclusion actuelle | État | Documentation |
|---|---|---|---|---|
| Short volume | ratio quotidien, variations et niveaux disponibles | Pas de signal directionnel stable H3/H10/H20 | `NO_GO` | [POC Eroya — Short volume](eroya_directional_poc.md#short-volume) |
| Short interest | niveaux et observations PIT disponibles | Fréquence/couverture insuffisante et absence de lift robuste | `NO_GO` | [POC Eroya — Short interest](eroya_directional_poc.md#short-interest) |
| Analyst Insights | scores et observations analystes | Quelques candidats descriptifs, aucune confirmation intacte | `INCONCLUSIVE` | [Analyst Insights](eroya_directional_poc.md#analyst-insights) |
| Analyst revisions Yahoo | révisions et objectifs | Aucun signal durable dans le harnais historique | `NO_GO` | [Synthèse historique des données directionnelles](../experiences/archives_recherche/directional_data_research.md) |
| Form 4 / insiders | transactions d'initiés avec date de dépôt PIT | Effets LONG descriptifs non stables ; ablation modèle ne passe pas les gates | `NO_GO` | [Form 4](eroya_directional_poc.md#résultats-form-4-pit) |
| News/sentiment multi-source | sentiment et événements Eroya comparés aux données internes | Contenu partiellement nouveau mais aucune preuve historique directionnelle | `NO_GO` historique ; collecte prospective possible | [News Eroya](eroya_directional_poc.md#news-multi-source-eroya-versus-sentiment-existant) |
| Earnings/surprise EPS | résultats trimestriels, surprise brute, distance earnings | Surprise brute rejetée comme signal autonome | `NO_GO` | [Earnings](eroya_directional_poc.md#résultats-trimestriels-et-surprises-eps) |
| Dépôts 8-K | catégories structurées et compteurs événementiels | Information descriptive, mais répétitions et concentration interdisent une règle | `INCONCLUSIVE`, non promu | [8-K](eroya_directional_poc.md#dépôts-8-k-structurés) |
| Options directionnelles | prix, skew, profondeur et volume put/call sur surface 45 DTE | 625 événements/8 dates, 323 surfaces complètes. Mapping volume `v` corrigé : 129 surfaces quatre jambes, 119 avec cible. H3 AUC 0,619/IC 0,032 mais stabilité 1/4 années et LONG brut perdant ; H10/H20 incohérents | `NO_GO`, volume désormais testé | [Protocole et résultat E7](options_directional_poc.md#volume--mapping-eroya-corrigé-et-réévaluation-complète) |
| Quotes de clôture IEX | dernière quote quotidienne, spread, imbalance, microprice, profondeur et âge de quote | Couverture 88,8 %, mais aucun signal directionnel stable sur H3/H5/H10/H20 ; le niveau de profondeur H20 est un confondant de liquidité | `NO_GO` pour le snapshot quotidien | [Microstructure de clôture](closing_quote_microstructure.md) |
| Intraday 5 minutes de séance complète | barres Eroya ajustées, segmentation matin/après-midi, VWAP, volume et volatilité | 393 dates, 330 séances exploitables. Direction rejetée ; volatilité amplitude AUC 0,56/IC 0,18/6 sur 8 semestres, mais p Bonferroni 0,30. Aucun profil promu | `FAIT_NO_GO` | [Trajectoire de séance](intraday_session_path_pilot.md) |
| Trades/quotes séquentiels riches | NBBO/SIP, flux signé, trajectoire prix et liquidité | Collecte Eroya validée puis hypothèses rejetées : signed-flow simple/accéléré `NO_GO`; épuisement prix 5 min non répliqué sur 400 dates disjointes (AUC 0,490) | `FAIT_NO_GO` | [Flux signé](signed_trade_flow_pilot.md), [prix/liquidité tick](tick_price_liquidity_audit.md) |
| Déséquilibres d'enchère MOC/LOC | messages historiques d'auction imbalance disponibles avant la clôture | Aucun endpoint ou dataset correspondant dans le catalogue officiel Eroya au 8 septembre 2026 ; trades/NBBO ne remplacent pas ce flux | `BLOCKED_NO_DATA_SOURCE` | [Prix/liquidité tick](tick_price_liquidity_audit.md) |
| Chaîne Options OPRA complète | minute aggregates de tous les contrats ; idéalement trades+quotes signés | Plan Pro autorise `us-options-minute-aggs`; ticks OPRA exigent Premium. REST quatre jambes trop clairsemé. `flatfiles/list` a répondu 502 deux fois, donc aucun téléchargement | `STANDBY_ARCHIVE_SERVICE` | [Options E7 — chaîne complète](options_directional_poc.md#piste-suivante--chaîne-opra-complète) |
| Contexte intraday marché | trajectoires SPY/QQQ/IWM et VXX sur séance J | 364 événements alignés/305 tails. Meilleur directionnel IWM-SPY AUC 0,52 ; meilleurs amplitude SPY vol/VXX abs AUC 0,53. Toutes p Bonferroni=1, aucun gate complet | `FAIT_NO_GO` | [Contexte intraday marché](intraday_market_context_pilot.md) |
| Borrow fee / utilization / shares available | statut Alpaca actuel et disponibilité des sources historiques | Aucun historique PIT pluriannuel local ou Eroya ; FINRA SLATE repoussé à septembre 2028. La compatibilité live Alpaca `borrow_status` a été sécurisée | `BLOCKED_NO_PIT_HISTORY` | [Audit de faisabilité borrow](borrow_lending_data_feasibility.md) |
| 13F | positions institutionnelles trimestrielles retardées | Non testé, priorité faible pour H3/H10/H20 | `PROPOSED` faible priorité | [Limites options et ticks](eroya_directional_poc.md#options-tradesquotes-et-13f) |

## Expériences historiques Per-Symbol

| Campagne | Axes testés | Verdict durable | Documentation |
|---|---|---|---|
| S7 — whitelist de features | Réduction contrôlée des features per-symbol, comparaison architecture/champion | Mécanisme conservé, gain OOS rejeté | [S7 Feature whitelist](../experiences/archives_ml/synthese_s7_feature_whitelist_2026-08-18.md) |
| Per-Symbol Directional V2 F0/F1/F2/F3a/F3b | Familles directionnelles, architectures LSTM/LightGBM/CatBoost, champion et stabilité | Aucun gain OOS stable ; `NO_GO` | [Synthèse Per-Symbol V2](../experiences/archives_ml/synthese_per_symbol_v2_2026-08-19.md) |
| Sélection des tickers par F1 LONG/SHORT | Gates par côté, folds valides, listes STRICT et DISCOVERY | Outil de screening disponible ; ne prouve pas la performance portefeuille | [Sélection des candidats](per_symbol/06_selection_candidats_directionnels.md) |
| Entraînement conditionnel aux événements Oracle | Branches LONG/SHORT entraînées dans le bundle sur les événements Oracle | Technique fonctionnelle ; généralisation directionnelle rejetée sur le batch étudié | [Population conditionnelle](per_symbol/07_bundle_oracle_long_short.md#population-dentraînement-conditionnelle--étape-3) |

## Persistance, confirmation prix et filtre DIP

Ces expériences concernent principalement Global Ranking. Elles ne doivent pas
être attribuées à Oracle Extreme par erreur.

| Expérience | Population et résultat | Verdict actuel | Documentation |
|---|---|---|---|
| Persistance + confirmation prix après Oracle TOP10 | Taux GOOD resté pratiquement plat autour de 50,2–50,3 % | `NO_GO` pour Oracle | [Persistent tail price](../experiences/archives_recherche/persistent_tail_price.md#oracle-top10--hypothèse-non-soutenue) |
| Persistance Global Rank TOP10 + hausse | GOOD rate 0,521 → environ 0,556 sur un échantillon viable | Signal historique soutenu, distinct d'Oracle | [Persistent tail price — LONG](../experiences/archives_recherche/persistent_tail_price.md#global-rank-top10-long--hypothèse-soutenue) |
| Persistance Global Rank BOTTOM10 + baisse | GOOD SHORT environ 0,512 → 0,529 | `WEAK_SIGNAL` SHORT | [Persistent tail price — SHORT](../experiences/archives_recherche/persistent_tail_price.md#global-rank-bottom10-short--faible-gain) |
| TOP10 persistant + baisse récente | Rebond observé avec GOOD rate autour de 0,567 | Découverte exploratoire, non assimilable à une direction Oracle | [Inversion TOP10](../experiences/archives_recherche/persistent_tail_price.md#inversion-top10--baisse--signal-le-plus-fort) |
| DIP N4/X2 Global Rank | Filtre DIP puis veto de régime ; +5,5 % en 2025 OOS et +4,3 % en 2026H1 contre baselines négatives | `GO` historique dans son contrat Global Rank ; paramètres gelés | [Persistent TOP10 DIP](../experiences/archives_recherche/persistent_top10_dip.md#phase-3--audit-de-parité-reclaim-validation-oos-et-implémentation-2026-08-27) |
| DIP reclaim R50/R100 | Attendre la reprise consomme le rebond et dégrade D0 | `NO_GO`, garder entrée directe | [Reclaim](../experiences/archives_recherche/persistent_top10_dip.md#32-reclaim-r50r100--no-go) |
| Tiebreaker `dip_quality` | Amélioration mécanique et métriques favorables, mais seulement 18 substitutions OOS | `INCONCLUSIVE_LOW_SAMPLE` | [Tiebreaker DIP](../experiences/archives_recherche/Tiebreaker.md) |
| Smart sector cap | Cap exposition 20 % et hybride count/exposition/corrélation retirent ou ajoutent de mauvais ensembles de trades | C0 count=2 conservé ; C1/C2 `NO_GO` | [Smart sector cap](../experiences/archives_recherche/smart_sector_cap_verdict_2026-08-27.md) |

## Calibration et transformation des scores Oracle

| Expérience | Résultat | Statut | Documentation |
|---|---|---|---|
| Percentile quotidien `rank` | Transformation déterministe, sans cible ni fit ; préserve l'ordre relatif | Contrat adapté au gate percentile | [Calibration Oracle](../experiences/archives_recherche/calibration_oracle_exterme.md#rank--percentile-intra-jour-relatif) |
| Calibration isotonic | Mapping score → fréquence d'extrême ; améliore la sémantique probabiliste mais pas l'AUC ou le classement | Non utilisable en backtest strict sans artefact calibré PIT gelé | [Isotonic](../experiences/archives_recherche/calibration_oracle_exterme.md#isotonic--proba-calibrée-absolue-pav), [contrat actuel](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |
| Oracle brut `none` | Score OOS brut utilisé lorsque le consommateur reclasse quotidiennement et qu'aucun calibrateur PIT antérieur n'est disponible | Contrat actuel du backtest strict | [Entraînement/calibration Oracle](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |

## Oracle Extreme — campagnes de construction et d'ablation

| Campagne | Axes testés | Conclusion conservée | Documentation |
|---|---|---|---|
| Oracle historique TOP/BOTTOM | Deux modèles directionnels au-dessus du ranking | Les deux côtés apprenaient surtout une magnitude commune ; architecture remplacée | [Synthèse Oracle](../experiences/oracle_extreme.md) |
| Oracle O0 binaire | `D1 ∪ D10` contre le milieu, sans Global Rank comme entrée | Contrat actuel : magnitude uniquement, gate percentile quotidien | [Concept Oracle](oracle/01_concept_et_architecture.md) |
| Diagnostics hard negatives/confounders | Faux positifs, sévérité, features, fondamentaux, cas catastrophiques | Diagnostics utiles, pas de gate live automatiquement validé | [Diagnostics Oracle](oracle/06_diagnostics_et_historique.md) |
| Ablations Oracle 01–11 | Ranks XS, raw simple, momentum, tendance, volatilité, volume, RSI, régime, transformations et z-scores | Comparaison corrigée terminée : l'AUC seule donne un classement trompeur ; le meilleur gain d'amplitude TOP20 est seulement +0,0215 point/jour apparié | `config/features/oracle/` et [comparaison corrigée](oracle_ablation_corrected_comparison.md) |
| Combinaisons Oracle 12–14 | Retraits combinés marché/régime, engineered transforms et momentum | Aucun profil promu ; corrélations 0,974–0,980 avec la baseline et seulement ~3 % de décisions TOP20 modifiées, donc aucun ensemble justifié | [Comparaison corrigée](oracle_ablation_corrected_comparison.md) |

## Global Ranking et Per-Sector — historique B0 à B44

Les campagnes B0–B44 ont testé les familles de features, backends, objectifs de
ranking, profondeur historique, taille d'univers et volume. Le dossier suivant
contient les rapports détaillés batch par batch :
[campagnes Global Ranking](../experiences/campagnes_global_ranking/README.md).

| Série | Variantes documentées | Documentation |
|---|---|---|
| B0–B3 | baseline, sentiment, scores screener, short score | [B0](<../experiences/campagnes_global_ranking/test/B0 Baseline.md>), [B1](<../experiences/campagnes_global_ranking/test/B1 sentiement.md>), [B2](<../experiences/campagnes_global_ranking/test/B2 scores screnner.md>), [B3](<../experiences/campagnes_global_ranking/test/B3 scores short.md>) |
| B4–B14 | SPY, VIX/VXN/VIX3M/MOVE, fondamentaux, CAPM, macro, historique de scores, secteur et stacking | [B4](<../experiences/campagnes_global_ranking/test/B4 Short + SPY.md>), [B5](<../experiences/campagnes_global_ranking/test/B5 Short + SPY + Vix.md>), [B6](<../experiences/campagnes_global_ranking/test/B6 Short + SPY + Vxn.md>), [B7](<../experiences/campagnes_global_ranking/test/B7 Short + SPY + Vix3m.md>), [B8](<../experiences/campagnes_global_ranking/test/B8 Short + SPY + Move.md>), [B9](<../experiences/campagnes_global_ranking/test/B9 Short + SPY + Fondamentaux.md>), [B10](<../experiences/campagnes_global_ranking/test/B10 Short + SPY + CAPM.md>), [B11](<../experiences/campagnes_global_ranking/test/B11 Short + SPY + Macro.md>), [B12](<../experiences/campagnes_global_ranking/test/B12 Short + SPY + Score histo.md>), [B13](<../experiences/campagnes_global_ranking/test/B13 Short + SPY + sectoriel.md>), [B14](<../experiences/campagnes_global_ranking/test/B14 Short + SPY + stacking.md>) |
| B15–B19 | transformations T1/T2/T3 et profondeur/folds | [B15](<../experiences/campagnes_global_ranking/test/B15 Short + SPY + T1.md>), [B16](<../experiences/campagnes_global_ranking/test/B16 Short + SPY + T2.md>), [B17](<../experiences/campagnes_global_ranking/test/B17 Short + SPY + T3.md>), [B18](<../experiences/campagnes_global_ranking/test/B18 Short + SPY + from 2011 + max 8 slits.md>), [B19](<../experiences/campagnes_global_ranking/test/B19 Short + SPY + from 2011 + max 16 slits.md>) |
| B20–B27 | YetiRank, QueryRMSE, QuerySoftMax, puis variantes CAPM | [B20](<../experiences/campagnes_global_ranking/test/B20 Short + SPY + YetiRank.md>), [B21](<../experiences/campagnes_global_ranking/test/B21 Short + SPY + QueryRMSE.md>), [B22](<../experiences/campagnes_global_ranking/test/B22 Short + SPY + QuerySoftMax.md>), [B25](<../experiences/campagnes_global_ranking/test/B25 Short + SPY + CAPM + YetiRank.md>), [B26](<../experiences/campagnes_global_ranking/test/B26 Short + SPY + CAPM + QueryRMSE.md>), [B27](<../experiences/campagnes_global_ranking/test/B27 Short + SPY + CAPM + QuerySoftMax.md>) |
| B30–B34 | P1–P3, fondamentaux, historique scores, secteur, screener avec YetiRank | [B30](<../experiences/campagnes_global_ranking/test/B30 Short + SPY + YetiRank +  P1-3.md>), [B31](<../experiences/campagnes_global_ranking/test/B31 Short + SPY + Fondamentaux + YetiRank.md>), [B32](<../experiences/campagnes_global_ranking/test/B32 Short + SPY + Score histo + YetiRank.md>), [B33](<../experiences/campagnes_global_ranking/test/B33 Short + SPY + sectoriel + YetiRank.md>), [B34](<../experiences/campagnes_global_ranking/test/B34 scores screnner + YetiRank.md>) |
| B35–B39 | univers 196/300/393 et challenger XGBoost rank | [B35](<../experiences/campagnes_global_ranking/test/B35 B25 + symbols 196.md>), [B36](<../experiences/campagnes_global_ranking/test/B36 B20 + symbols 196.md>), [B37](<../experiences/campagnes_global_ranking/test/B37 B25 + symbols 393.md>), [B38](../experiences/campagnes_global_ranking/test/B38%20B25%20avec%20300%20symblos%20%28parmi%20les%20400%29.md), [B39](<../experiences/campagnes_global_ranking/test/B39-B25-XGBoost-rank-ndcg-P3-3.md>) |
| B40–B44 | volume features, configurations B4/B20/B25 et extension train 2024 | [B40](<../experiences/campagnes_global_ranking/test/B40-B4-volume-features-P3-5.md>), [B41](<../experiences/campagnes_global_ranking/test/B41-B25-volume-features-P3-5.md>), [B42](<../experiences/campagnes_global_ranking/test/B42-B20-volume-features-P3-5.md>), [B44](<../experiences/campagnes_global_ranking/test/B44-B41-config-global-only-train-end-2024-12-31.md>) |
| Synthèse Global/Per-Sector | comparaison de tous les horizons, champions, splits, régimes et backtests | [Rapport comparatif](<../experiences/campagnes_global_ranking/test/test_global_per_sector.md>), [synthèse durable](../experiences/global_ranking_et_per_sector.md) |

## Expériences risque, exécution et lifecycle liées à l'interprétation ML

Ces campagnes ne cherchent pas directement D1/D10, mais elles déterminent si un
signal ML observé peut être monétisé sans biais d'exécution.

| Campagne | Conclusion | Documentation |
|---|---|---|
| Audit du backtest historique | Biais pullback et propagation TP découverts puis corrigés ; nécessité de la parité production | [Audit backtest](../experiences/archives_recherche/backtest_audit.md) |
| TP / risk-execution | Plusieurs TP testés ; amélioration locale non confirmée OOS | [Synthèse TP/risk](../experiences/archives_ml/synthese_tp_risk_execution_2026-08-18.md) |
| Time-stop/parité | Différence entre lifecycle de recherche et production mise en évidence | [Synthèse risque/lifecycle](../experiences/risque_execution_lifecycle.md) |
| Drawdown controller B4 | Contrôleur et gates paper validés dans son contrat historique | [B4 paper](../experiences/archives_recherche/c2_b4_breaker_go_paper_2026-08-21.md) |
| Force-close catastrophe | `CLOSE_ALL` et `CLOSE_LONGS` à -8 % rejetés | [E44](../experiences/archives_recherche/b4_force_close_side_attribution.md) |
| Validation/recalibration | Séparation entraînement, calibration, promotion et OOS | [Synthèse validation](../experiences/validation_et_recalibration.md) |

## Pistes préparées mais non encore exécutées

| Priorité actuelle | Piste | Question | Statut | Protocole |
|---:|---|---|---|---|
| 1 | Flux signé trades/NBBO Eroya proche de la clôture | L'agression bid/ask et le déséquilibre NBBO ajoutent-ils une direction dans Oracle TOP20 ? | `FAIT_NO_GO` : agrégat 5 min instable ; accélération 30 min AUC 0,567 et 5/7 semestres, mais p=0,149 et p Bonferroni=1. Aucun modèle autorisé | [Flux signé trades/NBBO](signed_trade_flow_pilot.md) |
| 2 | Modèle temporel multi-horizon | Un apprentissage commun H3/H5/H10/H20 régularise-t-il la direction ? | `PROPOSED`, conditionnel à V2 | À formaliser |
| 3 | Portefeuille relatif | Un spread dollar-neutral peut-il monétiser un faible ranking sans direction absolue ? | `FAIT_NO_GO` : H3 net quasi nul ; H20 +0,304 % net par cohorte mais seulement 4/9 folds positifs, queue SHORT encore haussière | [Pré-gate portefeuille relatif](oracle_relative_portfolio.md) |

## Audit des 49 méthodes de la roadmap professionnelle

Cette section confronte
[la roadmap des méthodes quant](alpha_trade_quant_professional_methods_roadmap.md)
au code et aux expériences réellement présents au 6 septembre 2026. Les états
ont le sens suivant :

- `ACTIF` : méthode intégrée et utilisée dans l'application ou ses harnais ;
- `FAIT_NO_GO` : expérience exécutée, hypothèse non promue ;
- `EN_COURS` : campagne actuellement exécutée ;
- `PARTIEL` : une partie seulement du contrat a été testée ou industrialisée ;
- `À_FAIRE_CONDITIONNEL` : pertinent uniquement si son prérequis passe ;
- `À_FAIRE_PRIORITAIRE` : information nouvelle potentiellement utile ;
- `DIFFÉRÉ` : intérêt possible mais rapport signal/complexité faible maintenant ;
- `À_ÉVITER` : non justifié dans l'état actuel des preuves.

### 1–10 — formulation du signal et trajectoires

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 1 | Tail Classification D1/D10 | `FAIT_NO_GO` statique et temporel | GlobalDirection, le modèle mutualisé statique et Temporal V2 ont échoué. V2 trouve au mieux 0,5143 avec l'état statique ; les trajectoires ne l'améliorent pas. Voir [GlobalDirection](../experiences/archives_recherche/global_direction_h20.md), [shared directional](shared_directional_oracle_events.md) et [Temporal V2](temporal_d1d10_v2.md). |
| 2 | Temporal Feature Engineering | `FAIT_NO_GO` ancien et V2 | Après l'ancien test sur scores clairsemés, V2 a testé proprement 27 séries locales denses, N=3/5/10 et T0/T1/T2. Aucun T2 ne gagne +0,01 contre T0 ; N10 dégrade Logistic. Voir [historique temporel](../experiences/archives_recherche/global_direction_temporal.md) et [Temporal V2](temporal_d1d10_v2.md). |
| 3 | Meta-Labeling | `PARTIEL` | La cascade Oracle → spécialistes LONG/SHORT existe techniquement. L'entraînement directionnel conditionnel Oracle a échoué en généralisation ; le méta-label temporel n'est pas validé. Conserver l'architecture, pas la considérer comme alpha démontré. Voir [bundle](per_symbol/07_bundle_oracle_long_short.md). |
| 4 | Cross-Sectional Ranking | `ACTIF` global ; `FAIT_NO_GO` post-Oracle | Global Ranking est une brique complète. Le ranker restreint au TOP20 Oracle n'a pas franchi les gates ; PairLogit est retesté dans V2 sur les trajectoires. Voir [Global Ranking](global_ranking/README.md) et [ranker conditionnel](conditional_oracle_ranker.md). |
| 5 | Cross-Feature Divergence | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Plusieurs divergences existent déjà parmi les features EXPERT. L'ablation supplémentaire était conditionnée à un signal V2 ; Dataset A étant NO_GO, elle n'est pas ouverte. |
| 6 | Relative Trajectory | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Les niveaux de force relative et leurs deltas/pentes sont inclus dans V2. Une trajectoire stock moins secteur autonome n'est pas lancée, car le gate Dataset A préalable a échoué. |
| 7 | Multi-Horizon Agreement | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Les features multi-horizons et l'audit de consensus existent. Le test directionnel supplémentaire était conditionné à un V2 informatif ; il n'est pas ouvert. Voir [consensus OOF](oof_consensus_audit.md). |
| 8 | Persistence | `ACTIF` ailleurs ; `FAIT_NO_GO` D1/D10 V2 | V2 a inclus la fraction de variations positives sur N sans améliorer T0. Ne pas confondre ce résultat avec la persistance Global Rank/DIP. Voir [DIP historique](../experiences/archives_recherche/persistent_top10_dip.md). |
| 9 | Velocity / Acceleration | `FAIT_NO_GO` D1/D10 V2 | V2 a testé pentes, dispersion, persistance et accélération canonique dans T2. Aucun T2 ne franchit le gate de gain ; pas d'ablation séparée justifiée. |
| 10 | Change-Point Detection | `DIFFÉRÉ` | Aucun test causal dédié CUSUM/PELT n'a été trouvé. À envisager seulement si V2 montre qu'une dynamique simple existe mais reste mal captée ; sinon ce serait du feature mining supplémentaire. |

### 11–19 — conditionnement, spécialistes et modèles séquentiels

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 11 | Event-Conditioned Models | `PARTIEL` / majoritairement `FAIT_NO_GO` | Earnings, Form 4, news, analystes et 8-K ont été audités. Form 4 et earnings ne passent pas ; 8-K et Analyst Insights restent inconclusifs. Un nouveau modèle conditionné exige une série PIT plus dense ou une source nouvelle. Voir [POC Eroya](eroya_directional_poc.md). |
| 12 | Regime-Conditioned Models | `FAIT_NO_GO` pour la direction | Les régimes sont disponibles comme features et dans le risque. Le modèle directionnel quotidien de régime Oracle n'a produit aucun avantage stable. Ne pas créer maintenant des experts séparés par régime. Voir [E5](oracle_daily_regime_direction.md). |
| 13 | Mixture of Experts | `DIFFÉRÉ` | Aucun ensemble de patterns directionnels validés ne justifie encore un gating model. Requis : au moins deux experts complémentaires ayant chacun un avantage OOF. |
| 14 | Trajectory Clustering | `À_FAIRE_CONDITIONNEL` diagnostique | Non exécuté pour D1/D10. Autorisé uniquement après un signal V2, pour comprendre plusieurs formes de D1/D10 ; pas pour réoptimiser la même période. |
| 15 | Contrastive Learning | `À_ÉVITER` maintenant | Non implémenté et disproportionné sans séparabilité tabulaire préalable. |
| 16 | 1D-CNN / TCN | `NON_OUVERT` | Le prérequis T2 >= +0,01 d'AUC same-date contre T0 a échoué. Ajouter un réseau ne répondrait pas à l'absence de signal tabulaire. |
| 17 | LSTM séquentiel | `ACTIF` per-symbol générique ; `NON_OUVERT` D1/D10 | LSTM existe dans ModelFactory, mais le challenger mutualisé de polarité n'est pas lancé après le NO_GO tabulaire V2. |
| 18 | Transformer temporel | `À_ÉVITER` | Séquences de 4 à 11 observations et absence actuelle de signal ne justifient ni paramètres ni complexité supplémentaires. |
| 19 | Calibration | `ACTIF`, application conditionnelle | Platt/isotonic/temperature-vector et la gouvernance existent. E2-B a montré qu'une calibration correcte ne sauve pas un ranking faible. Calibrer Temporal uniquement après Dataset C et stabilité du classement. Voir [recalibration](recalibration_et_promotion.md). |

### 20–29 — protocole scientifique et traitement des données

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 20 | Feature Ablation | `ACTIF` et largement `FAIT` | Campagnes Global Ranking B0–B44, Oracle 01–14, Per-Symbol S7/V2 et sources Eroya. Continuer seulement par familles préfixées sur mêmes lignes, pas par suppression opportuniste. |
| 21 | Direction vs Amplitude Audit | `ACTIF` / `FAIT` | E6-A valide l'amplitude Oracle ; tous les harnais directionnels récents séparent rendement signé et amplitude. V2 recalcule correctement tail-vs-middle, contrairement à l'ancien `dir_vs_amp`. Voir [E6-A](oracle_amplitude_audit.md). |
| 22 | Same-Date Evaluation | `ACTIF` | Métrique centrale des modèles mutualisés, rankers, consensus et V2. Elle évite qu'un régime de date soit pris pour une séparation cross-sectionnelle. |
| 23 | Pairwise Ranking | `FAIT_NO_GO` statique et temporel | R1 PairLogit sur le pool Oracle a échoué. Dans V2, PairLogit reste sous 0,50 d'AUC same-date avec des buckets non monotones malgré les trajectoires. |
| 24 | Purged Walk-Forward | `ACTIF` | Oracle, Global Ranking, Per-Symbol et recherches partagées utilisent le WF. V2 impose `oracle_available_date < test_start`, donc les targets H20 du train sont connus avant le test. |
| 25 | Embargo / Leakage Controls | `ACTIF` | Assertions de features interdites/futures, garde de disponibilité target, Oracle OOF, preprocessing train-only et contrôles PIT sont présents. La confirmation finale V2 reste déclarée indisponible car 2018–2025 a déjà été observé. |
| 26 | Missingness as Information | `PARTIEL` | `is_filled`, âges de snapshots et âges d'événements existent dans plusieurs datasets. V2 local n'ajoute pas mécaniquement des centaines de flags. À compléter seulement pour les sources irrégulières réellement retenues. |
| 27 | Event Recency | `PARTIEL` / sources testées non promues | Distance aux earnings, récence Form 4/news/événements ont été testées dans les POC correspondants sans signal suffisant. Garder comme contrat standard pour toute nouvelle source événementielle. |
| 28 | Ensemble Models | `ACTIF` pour championnat ; `FAIT_NO_GO` pour consensus directionnel | La sélection de champion LSTM/LightGBM/CatBoost existe. Le consensus OOF des modèles directionnels n'améliore pas le meilleur composant ; ne pas rechercher des poids post-hoc. Voir [C1](oof_consensus_audit.md). |
| 29 | Feature Neutralization | `ACTIF` / `FAIT` | Features SPY/secteur, CAPM et cibles résiduelles ont été testées. Les campagnes Global Ranking montrent leur utilité contextuelle ; les cibles directionnelles résidualisées n'ont pas résolu D1/D10. Voir [campagnes Global](../experiences/campagnes_global_ranking/README.md) et [E1](shared_directional_oracle_events.md). |

### 30–39 — risque, portefeuille et formulations alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 30 | Risk Overlay | `ACTIF` | Moteur risque/exécution séparé, stops, TP, drawdown, volatilité cible et protections sont implémentés et documentés. Le risque ne doit pas être utilisé pour masquer un signal directionnel absent. Voir [risque/lifecycle](../experiences/risque_execution_lifecycle.md). |
| 31 | Portfolio Constraints | `ACTIF` ; portefeuille relatif `FAIT_NO_GO` | Max positions, exposition sectorielle, exposition brute/nette, drawdown et liquidité sont consommés par le backtest/production. Le pré-gate dollar-neutral dans le TOP20 Oracle obtient +0,304 % net par cohorte H20, mais seulement 4/9 folds positifs ; aucun replay n'est autorisé. Voir [portefeuille relatif Oracle](oracle_relative_portfolio.md). |
| 32 | Transaction Cost Awareness | `ACTIF` | Commission, slippage, spread, intérêt de marge et replay d'exécution font partie des contrats canoniques. Les diagnostics ML purs restent avant coûts ; tout GO doit ensuite passer le backtest net. |
| 33 | Probability Thresholding | `FAIT`, non promu | Les seuils 0,55/0,80/0,85/0,90 ont été comparés sur le bundle directionnel ; aucune politique robuste n'en est sortie. Ne pas reprendre un sweep fin sans nouveau modèle validé. |
| 34 | Symbol-Specific Thresholds | `À_ÉVITER` | Les gates de sélection de candidats per-symbol sont des contrôles de qualité, pas des seuils de trading optimisés par ticker. L'échantillon de tails reste trop faible pour cette recherche. |
| 35 | Per-Symbol Fine-Tuning | `FAIT_NO_GO` pour la mission Oracle | Les spécialistes LONG/SHORT et leur population conditionnelle Oracle sont implémentés. L'amélioration développement ne s'est pas généralisée. Capacité technique conservée, hypothèse ML non promue. |
| 36 | Hierarchical Models | `PARTIEL`, `DIFFÉRÉ` | Global, Per-Sector et Per-Symbol existent comme modules distincts, mais pas comme modèle hiérarchique joint avec shrinkage. Inutile avant un signal partagé stable. Voir [Per-Sector](per_sector/README.md). |
| 37 | Survival / Time-to-Event | `PARTIEL`, `FAIT_NO_GO` proche | First-touch, rentabilité path-aware et veto de risque ont étudié le chemin et l'ordre des barrières ; ils ont échoué. Un vrai modèle de durée n'est pas prioritaire tant que H20 reste le contrat. |
| 38 | Régression directe des rendements | `FAIT_NO_GO` | E1 a prédit le rendement signé H3/H5/H10/H20 ; IC proche de zéro et branche SHORT négative. Ne pas relancer sans données nouvelles. |
| 39 | Ordinal Classification | `FAIT_NO_GO` | GlobalDirection ordinal D1/milieu/D10 et objectif rank ont été testés sans battre les baselines. Dataset C V2 sera un audit de scoring du milieu, pas une réouverture opportuniste de cette cible. |

### 40–49 — méthodes avancées, robustesse et données alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 40 | Multitask Learning | `À_ÉVITER` maintenant | Aucun avantage à remélanger amplitude, direction et rendement après avoir clarifié leurs rôles. Une future tête multi-horizon directionnelle serait une expérience distincte, pas un modèle end-to-end. |
| 41 | Reinforcement Learning | `À_ÉVITER` | Ne résout ni la faiblesse informationnelle D1/D10 ni les problèmes de couverture. |
| 42 | Genetic Programming / Symbolic Search | `À_ÉVITER` | Risque de data mining excessif sur une période déjà largement observée. |
| 43 | SHAP Pattern Discovery | `À_FAIRE_CONDITIONNEL` diagnostique | Feature importance existe dans plusieurs entraînements, mais une analyse SHAP de trajectoires n'est utile qu'après un GO OOF V2. Elle n'est jamais une preuve autonome d'alpha. |
| 44 | Counterfactual Analysis | `PARTIEL` | Des contrefactuels de lifecycle/stops et de risque existent. Aucun contrefactuel directionnel de trajectoire n'est justifié avant un modèle V2 informatif. |
| 45 | Placebo Tests | `NON_DÉCLENCHÉ` pour V2 | Le placebo était obligatoire avant promotion d'une variante. Aucun T2 n'ayant passé le gate primaire, l'exécuter ne changerait pas la décision NO_GO et Dataset B reste fermé. |
| 46 | Bootstrap par Date | `NON_DÉCLENCHÉ` pour V2 | Le bootstrap du delta T2-T0 était prévu pour une variante candidate. Tous les deltas sont sous +0,01 ; aucun N n'est sélectionné et le contrôle n'est pas requis pour rejeter l'hypothèse. |
| 47 | Stability Selection | `PARTIEL` | Les gates fold/année et ablations par famille existent. La stabilité des rangs d'importance feature par fold n'est pas encore produite dans V2 ; à ajouter seulement pour une variante candidate. |
| 48 | Data Source Incrementality | `FAIT` sur les sources disponibles | Form 4 a eu une ablation modèle, les autres familles ont été comparées sur des populations communes lorsque la couverture le permettait. Aucune source Eroya testée n'est promue. Réouvrir seulement avec une série PIT réellement nouvelle et dense. |
| 49 | Alternative Data Families | `PARTIEL / NO_GO_TICKS_OPTIONS_VOLUME` | Flux signé, prix/liquidité et séance intraday sont rejetés. Le mapping Options `v` a été corrigé : le ratio volume call/put est enfin testable mais instable, H3 AUC 0,619 portée uniquement par 2022. Aucun feature n'est promu. Borrow fee/utilization et auction imbalance restent bloqués faute de source. Voir [Options E7](options_directional_poc.md), [flux signé](signed_trade_flow_pilot.md) et [prix/liquidité tick](tick_price_liquidity_audit.md). |

## Correctif transversal de qualité des labels Oracle

L'audit D10 a découvert 36 faux rendements issus des restructurations WFRD/CHRD
et 103 targets utilisant un prix D+H forward-fillé. Le correctif fail-closed est
implémenté : barres réelles aux deux extrémités, registre de ruptures d'identité,
quarantaine des sauts inexpliqués, traçabilité du rendement brut et segmentation
des features rolling. Le dry-run complet isole exactement 139 lignes sur
890 928. Voir [audit D10 et contrat corrigé](d10_corporate_action_anomaly_audit.md).

## P0 — audit de l’univers Oracle 400

L’univers statique du batch `model-factory-20260907170018-0e94ac` est audité
dans [P0 — univers Oracle 400](oracle_universe_p0_audit.md). Le biais de
sélection est confirmé : 112/400 symboles commencent après le début de la
période et 60 en 2020 ou après. Les 20 % de symboles les plus contributeurs
créent 41 % des tails ; leur fréquence est corrélée à 0,895 avec la volatilité
et 0,918 avec le range médian. Les snapshots PIT existants sont trop dégradés
pour servir immédiatement de gold standard. Statut : `FAIT_BIAIS_CONFIRMÉ`,
avec P0b bar-only/PIT qualifié comme prochaine étape avant tout réentraînement.

P0b est maintenant terminé. L'admission bar-only quotidienne depuis les 2 696
candidats produit 3,93 M de lignes et un univers médian de 1 550 titres.
Seulement 67,7 % des anciennes lignes passent les nouveaux gates quotidiens et
9,9 % des appartenances extrêmes changent. Les 20 % de symboles les plus
contributeurs produisent désormais 52,2 % des tails : sélectionner les titres
les plus volatils est explicitement rejeté. Voir
[P0b — univers dynamique](oracle_universe_p0b_dynamic.md). Statut :
`FAIT_DYNAMIC_BAR_ONLY`, avec capitalisation/type/pays historiques et titres
radiés restant à qualifier.

P0c compare ensuite, sur les mêmes 3,93 M lignes, le rendement brut, le
vol-scaled, le rang intra-quintile de volatilité et le rang sectoriel. Aucune
variante ne franchit tous les gates. `vol_strata` réduit la concentration de
52,2 % à 42,3 %, mais conserve 89,86 % de l'amplitude contre un gate préfixé à
90 %. Le seuil n'est pas relâché a posteriori ; le label brut reste canonique.
Voir [P0c — cibles Oracle](oracle_universe_p0c_targets.md). Statut :
`FAIT_NO_PROMOTION`, challenger `vol_strata` réservé à une confirmation future.

P0d construit ensuite, sans utiliser labels ni performances futures, un nouvel
échantillon de recherche de 400 titres depuis les 2 696 candidats. Après gates,
995 titres sont éligibles. La sortie respecte exactement les quotas : 260 mid,
100 large, 40 small ; volatilité 60/80/100/100/60 ; bêta 80 par quintile. Elle
couvre 44 secteurs, avec un maximum de 16 titres par secteur, et ne partage que
101 symboles avec l'ancien univers 400. Le fichier est reproductible par
cutoff/seed/hash, mais reste `RECONSTRUCTED_GRADE_B` et ne rend pas 2026H1 OOS.
Voir [P0d — univers équilibré 400](oracle_universe_p0d_balanced400.md). Statut :
`FAIT_BALANCED_400`, prochaine étape préfixée P0e de comparaison OOF à contrat
Oracle identique.

P0e compare ensuite le témoin `model-factory-20260907170018-0e94ac` au batch
Balanced 400 `model-factory-20260908183941-7826b4` sur 14 folds et 1 764 dates
OOF communes. Le nouvel univers augmente marginalement l'AUC (0,6851→0,6882),
mais diminue la précision TOP20 (40,00→38,94 %), le rappel
(41,37→39,14 %) et le lift d'amplitude (1,591→1,515). Les IC 95 % par blocs de
21 séances sont entièrement négatifs pour ces quatre mesures TOP20. Il ne gagne
que 2/15 semestres en AUC et 3/15 en lift d'amplitude. Statut :
`FAIT_NO_PROMOTION_PERFORMANCE`. L'ancien 400 reste un témoin biaisé et le
Balanced 400 un échantillon de recherche ; la suite est P0f sur l'univers large
dynamique. Voir [P0e — comparaison OOF](oracle_universe_p0e_comparison.md).

P0f est `FAIT_GO_RECHERCHE_AMPLITUDE`. Le batch de confirmation
`model-factory-20260909051302-323684` produit 3,93 M de labels, 14 folds et
2,91 M de prédictions OOS du 5 juillet 2018 au 11 juillet 2025. Sur les 1 512
dates communes avec le premier batch 12-fold, les prédictions et métriques sont
strictement identiques. Sur 1 764 dates face à l'ancien 400, les deltas TOP20
sont +4,08 points de précision, +2,74 points de rappel, +0,095 de lift amplitude
et +3,23 points de rétention ; tous les IC 95 % par blocs restent positifs. Face
au Balanced 400, les quatre deltas sont aussi positifs. P0f devient donc le
contrat de recherche recommandé pour l'Oracle d'amplitude. Il ne résout pas la
direction : son TOP10 contient 25,5 % de D1 et 25,0 % de D10. Le batch reste
`serving_ready=false` jusqu'à l'adaptation et la validation du serving. Voir
[P0f — entraînement dynamique](oracle_universe_p0f_dynamic_training.md).

P0g est `FAIT_NO_GO_DIRECTION`. Le témoin directionnel mutualisé figé,
sans contexte symbole/secteur, a été réentraîné sur les 582 700 événements
TOP20 OOS du batch P0f confirmé. Sur neuf folds et 179 605 observations D1/D10,
il obtient AUC 0,4904 et IC quotidien −0,0147. Le TOP LONG contient 46,88 % de
D10 contre 53,12 % de D1 ; le TOP SHORT produit −1,43 % de rendement signé.
Le dernier fold 2025 est favorable, mais les autres folds sont instables et
l'agrégat reste inférieur au hasard. Les variantes lourdes E1/E2 ne sont donc
pas relancées sans information PIT nouvelle. Le correctif technique reconstruit
désormais le cache directionnel manquant des batchs Oracle autonomes à partir
des seules lignes persistées traçables par `fold_start`. Voir
[P0g — impact directionnel](oracle_universe_p0g_directional_impact.md).

P0h est `IMPLÉMENTÉ_SHADOW_ONLY`. Le batch P0f dynamique peut désormais
calculer son admission PIT quotidienne, ses features, ses rangs et ses scores
Oracle en dehors des tables de serving. Les fragments Parquet portent
`prediction_mode=shadow`, `champion_t_start` et le gate TOP20 ; le rapport
porte `trading_eligible=false`. Sans `--oracle-shadow`, le batch reste
bloqué. L'IHM active automatiquement la case shadow lorsqu'elle détecte un
profil `pit_dynamic_bars`. Une première collecte 2025-07-14→2026-06-30
reste à exécuter, puis à évaluer lorsque les rendements H20 sont disponibles.
Voir [P0h — serving shadow dynamique](oracle_universe_p0h_shadow_serving.md).

P0i est `FAIT_GO_AMPLITUDE_SHADOW_NO_GO_TRADING`. Le run holdout dynamique
compte 462 461 labels H20 valides sur 230 séances. L'AUC atteint 0,7742 et le
lift d'amplitude TOP20 1,757 ; en 2026H1 ils restent respectivement à 0,7727 et
1,709. Les déciles du score sont parfaitement monotones sur le rendement
absolu. En revanche, parmi les vrais extrêmes retrouvés en 2026H1, 51,27 % sont
positifs : la direction reste pratiquement équilibrée. P0i valide donc le
détecteur d'amplitude, pas une stratégie LONG/SHORT. La suite autorisée est un
canary shadow P0j, sans alimentation des tables de trading.

Voir [P0i — évaluation holdout shadow](oracle_universe_p0i_shadow_evaluation.md).

P0j est `IMPLÉMENTÉ_CANARY_SHADOW`. Le canary quotidien choisit la dernière
séance EOD disponible, exécute l'admission P0b et l'Oracle dans des Parquet
isolés, contrôle couverture/distribution contre la baseline P0i, puis évalue
automatiquement les runs arrivés à H20 en reconstruisant les labels en dry-run.
Le registre est local, idempotent par date et protégé contre deux exécutions
simultanées. La tâche Windows est fournie mais n'est pas installée
automatiquement. P0j reste `research_only` et n'alimente aucune table ML.

Voir [P0j — canary quotidien](oracle_universe_p0j_daily_canary.md).

Premier run P0j réel : `FAIT_WARN_AGE_ONLY` au 10 juillet 2026. Les 2 097
scores et le TOP20 de 420 titres ont été écrits uniquement en Parquet. Le PSI
de 0,0182, la moyenne des scores et la couverture restent dans les bandes P0i ;
le seul avertissement est l'âge du champion, 548 jours. Les deux tables de
prédictions contiennent zéro ligne pour ce batch et cette date. L'évaluation
réalisée reste en attente des vingt séances futures.

La branche d'évaluation retardée a été validée séparément au 9 juin 2026 :
2 033 labels exploitables, AUC 0,8044, précision TOP20 47,17 % et lift
d'amplitude 1,884. Le registre a correctement basculé à une date évaluée sur
vingt requises, sans écrire en base.

La source EODHD étant volontairement arrêtée, `stock_bars_daily` se termine au
10 juillet 2026. P0j reste optionnel : sans nouvelle barre, la tâche quotidienne
est idempotente et ne produit aucune observation supplémentaire. Elle peut être
désinstallée sans supprimer les artefacts. Voir la section
[caractère optionnel et retrait propre](oracle_universe_p0j_daily_canary.md#caractère-optionnel-et-retrait-propre).

P0k est ouvert pour répondre à une limite de P0g : seul le classifieur D1/D10
direct a été revalidé sur le nouvel univers dynamique. Une campagne courte et
préfixée recontrôle les trois formulations réellement sensibles à la population
quotidienne — probabilités indépendantes E2, ranker conditionnel R1 et régime
quotidien E5. E4-B et les variantes lourdes ne sont autorisés que si ce premier
écran produit un signal stable. Voir
[P0k — revalidation directionnelle ciblée](oracle_universe_p0k_directional_revalidation.md).

## Pistes encore intéressantes après cet audit

### Priorité P0 — Temporal V2 fermé

Dataset A est terminé en `NO_GO_DATASET_A`. Bootstrap et placebo n'ont pas été
déclenchés, car aucune variante n'était éligible à une promotion. Dataset B/C,
N20, divergences, trajectoire relative, multi-horizon et réseaux séquentiels
restent fermés. Cette décision évite de chercher a posteriori un sous-groupe ou
un hyperparamètre favorable dans une hypothèse déjà rejetée.

### Priorité P1 — information véritablement nouvelle après l'échec V2

1. **Intraday 5 minutes de séance complète Eroya — `FAIT_NO_GO`** : 393 dates
   OOF ont été collectées et 330 séances passent la qualité. Aucun signal
   directionnel ne passe. La volatilité réalisée est descriptive pour
   l'amplitude (AUC 0,56, IC 0,18, 6/8 semestres) mais échoue Bonferroni à 0,30.
   Aucun modèle, profil ou stockage applicatif. Voir [trajectoire intraday de
   séance](intraday_session_path_pilot.md).
2. **Borrow fee/utilization/shares available — `BLOCKED_NO_PIT_HISTORY`** :
   piste squeeze/pression short pertinente, mais aucun historique PIT dense
   n'est disponible localement ou via Eroya. FINRA SLATE est repoussé à 2028.
   Voir [audit de faisabilité borrow](borrow_lending_data_feasibility.md).
3. **Capital flow signé — `FAIT_NO_GO`** : sur 200 événements, le flux agrégé
   échoue la stabilité. L'audit temporel préfixé ne le sauve pas : la meilleure
   accélération atteint AUC 0,567 et 5/7 semestres, mais p brute 0,149 et p
   Bonferroni 1,0. Aucun modèle ni découpage additionnel. Une famille séparée
   prix/spread/liquidité peut être auditée comme découverte sur les ticks déjà
   acquis, avec confirmation ultérieure obligatoire. Voir [flux signé
   trades/NBBO](signed_trade_flow_pilot.md).
4. **Épuisement du prix à la clôture — `FAIT_NO_GO`** : l'observation
   contrariante du premier échantillon ne se reproduit pas sur 400 dates
   disjointes. Le score fixe `-return_5m` obtient AUC 0,490, IC 0,005, p=0,627
   et 4/7 semestres favorables. La piste est fermée sans modèle. Une tentative
   initiale concentrée sur le ticker alphabétiquement premier a été interrompue
   avant rapport ; le correctif hash intra-date est testé. Voir [audit tick prix
   et liquidité](tick_price_liquidity_audit.md).
5. **Auction imbalance MOC/LOC — `BLOCKED_NO_DATA_SOURCE`** : cette donnée
   serait distincte des trades/NBBO et pertinente avant la clôture, mais le
   catalogue Eroya ne publie ni endpoint ni archive de messages de déséquilibre.
   Ne pas l'approximer à partir du dernier trade ou de la profondeur NBBO.
6. **Contexte intraday SPY/QQQ/IWM/VXX — `FAIT_NO_GO`** : 364 événements
   alignés et 305 tails. IWM-SPY atteint seulement AUC 0,52 ; volatilité SPY et
   mouvement VXX plafonnent à AUC amplitude 0,53. Tous les tests corrigés sont
   non significatifs. Voir [contexte intraday marché](intraday_market_context_pilot.md).

### Priorité P2 — uniquement après découverte d'un signal stable

- cross-feature divergence contrôlée ;
- trajectoire relative secteur/SPY ;
- cohérence multi-horizon ;
- SHAP et stability selection diagnostiques ;
- séquence aplatie puis TCN/1D-CNN ;
- intégration séparée dans LONG et SHORT, puis calibration et backtest net.

### Faible priorité ou arrêt actuel

- change-point avancé, clustering et mixture of experts sans patterns validés ;
- 13F/institutionnel pour des décisions H3–H20 ;
- LSTM D1/D10 avant TCN et avant preuve tabulaire ;
- Transformer, contrastive learning, multitask end-to-end, RL, genetic
  programming et seuils spécifiques par symbole.

## Multi-Horizon Oracle + Rolling Confirmation — `FAIT_WEAK_SIGNAL`

Quatre Oracle OOF H5/H10/H15/H20 sont alignés sur une coupe quotidienne
commune. Le POC pré-enregistré mesure MH0–MH3, la continuation après
J+5/J+10/J+15, la valeur incrémentale du consensus restant et une entrée
retardée symétrique S6-LS. Il est strictement `research_only` : aucune table,
aucun backtest et aucun flux live ne sont modifiés avant `GO_RESEARCH`.
L'univers courant `univers_filtred_equities.txt` implique un biais de survivance
et interdit `STRONG_GO`. Le run couvre réellement 284 symboles de juillet 2018
à juillet 2024. H5/H10/H15/H20 sont très corrélés (0,926–0,970), la sélection
multi-horizon contre REST n'est pas significative et S6-LS est négative. Un
signal exploratoire subsiste pour H20 seul + gagnant J+5 + Oracle restant
confirmé (écart quotidien +1,41 %, IC95 [+0,24 % ; +2,74 %]), mais il est
concentré dans les extrêmes et instable selon les années. Verdict `WEAK_SIGNAL` ;
phase 2 générale fermée, petit challenger OOS ciblé seulement. Voir
[protocole et mode d'emploi](multi_horizon_oracle_rolling_confirmation.md)
et [prompt de campagne](../../prompt/multi_horizon_oracle_rolling_confirmation_prompt.md).

Le challenger ciblé **Variante 2 — maintien rolling H5 jusqu'au TP** est
`FAIT_NO_GO`. Sur 30 566 entrées appariées, H20 fixe donne `+0,109 %` net/trade,
l'extension passive H60 `+0,120 %` et le rolling prix + H5 `-0,097 %`. Le rolling
perd `-0,217 %` par trade contre l'extension passive ; son delta quotidien
apparié vaut `-0,286 %`, IC95 `[-0,568 % ; -0,043 %]`. La cause principale est
le veto prix non positif, qui coupe 11 219 trades avant des récupérations
partielles. Le veto H5 seul est légèrement favorable sur sa sous-population,
mais trop faible et instable pour être promu. L'extension H60 seule n'est pas
significative et 95,5 % des trades sont inchangés face à H20. Aucun changement
du backtest ou du live. Voir la section résultat du
[protocole](multi_horizon_oracle_rolling_confirmation.md).

## E7 — Surveillance quotidienne KEEP / EXIT — `FAIT_NO_GO`

E7-A construit, pour chaque position H20 encore ouverte à une clôture, un état
PIT exécutable au prochain open. Il sépare strictement identité, features
observables et labels futurs (`KEEP`, avantage contre sortie immédiate, TP avant
stop, rendements et excursions futurs). `trade_id` est la future clé de groupe
anti-fuite et `label_end_date` la borne de purge. Le premier run a révélé puis
permis de corriger deux défauts avant entraînement : états de liquidation H20
obligatoire et historique technique tronqué à l'entrée. Son artefact est
supersédé ; E7-A doit être relancé. Aucun entraînement n'est autorisé avant le
nouvel audit de couverture, de distribution et de stabilité semestrielle. Voir
[E7 KEEP/EXIT](daily_position_keep_exit.md).

Le run E7-A corrigé contient 199 677 états sur 29 449 trades, une cible KEEP à
51,14 %, aucune décision H20 forcée et une couverture quasi complète. La forte
dérive semestrielle interdit une règle statique, mais l'état de position possède
assez de structure pour ouvrir E7-B. Trois modèles research-only sont prêts :
logistique calibrée, LightGBM calibré et LightGBM Huber sur l'avantage. Le gate
est le delta économique OOS de la première sortie contre H20, pas le F1.

E7-B est terminé sur six folds et 16 609 trades OOS. La meilleure politique,
LightGBM Huber sur l'avantage, ajoute `+0,080 %` par trade mais seulement
`+0,013 %` par date, IC95 `[-0,484 % ; +0,516 %]`, avec 2/6 folds positifs et
une corrélation score/avantage de `-0,016`. Les classifiers obtiennent AUC
environ 0,64 sans valeur économique stable. Le mécanisme évite fortement les
pertes de 2022H1 en sortant presque tout, puis détruit les gains de 2022H2 avec
la même réaction. Verdict `NO_GO` : aucun seuil ou modèle n'est promu.

## E8-A — Historique options PIT — `BLOCKED_NO_DENSE_PIT_HISTORY`

L'audit local reproductible ne trouve aucune table options en base. La meilleure
collecte comporte 625 événements, 155 symboles et 323 surfaces complètes
(51,68 %), mais seulement huit dates entre mai 2022 et juillet 2025, contre 504
requises. Les snapshots courants possèdent IV/Greeks/open interest sur quelques
contrats mais ne sont pas historiques. Il manque des quotes entrée/sortie
quotidiennes, IV/Greeks/OI historiques observés, taux, dividendes et ajustements
de contrats. E8-B n'est pas autorisé. Voir
[audit historique options PIT](options_pit_history_audit.md).

## E8-A2 — Source et coût d’acquisition — `ABANDON_COÛT`

Le TOP20 Oracle représente 28 736 événements sur les 504 dernières séances
éligibles, environ 57 par jour. Une collecte REST ciblée nécessite 363 511
tentatives pour une paire 45 DTE valorisée à H3/H5/H10/H20, soit environ
4,06 Gio bruts selon les hypothèses prudentes ; télécharger l’OPRA complet est
écarté. Un pilote de 60 dates réparties dans le temps représente 3 421 événements
et 43 276 tentatives. Le fournisseur techniquement préféré était ThetaData
Options Value, avec Massive Options Advanced comme repli opérationnel. Le
10 septembre 2026, la décision a été prise de ne souscrire à aucune source
payante : la campagne d'acquisition est donc fermée en `ABANDON_COÛT`.
Eroya n’est pas retenu tant que les droits de livraison des données américaines
ne sont pas confirmés. E8-B reste bloqué avant les gates du pilote. Voir
[source, coût et plan d’acquisition](options_acquisition_cost_audit.md).

## E8-A3 — Connecteur ThetaData et smoke — `ABANDON_COÛT`

Le connecteur REST v3 local et le smoke préfixé sont implémentés. Dix événements
Oracle TOP20 sont préparés sur cinq dates réparties de 2022 à 2024, avec un titre
faible et un titre fort en dollar-volume par date. Le premier run s’est arrêté
proprement avant tout appel : aucun Theta Terminal n’écoute sur le port 25503 et
`THETADATA_API_KEY` est absente. Ce résultat ne rejette pas la source. Après
démarrage du terminal, le même smoke doit vérifier contrats expirés, paire ATM
35–55 DTE et NBBO entrée/H3/H5/H10/H20. Artefact canonique du blocage :
`artifacts/research/thetadata_options/thetadata-options-smoke-20260910185522/report.json`.
Les 15 tests ciblés E8-A1/A2/A3 passent et le contrôle statique est propre.

La bibliothèque Python officielle publiée en 2026 permettrait aussi d'appeler
directement `option_list_contracts()` et `option_history_quote()` sans Theta
Terminal ni Java. Elle ne supprime toutefois pas l'obligation d'un abonnement
Options Value ou supérieur. La piste est donc abandonnée pour raison économique,
sans rejet scientifique de la donnée. Le connecteur research-only reste inactif,
aucun paquet ThetaData n'a été installé et E8-A4 n'est pas ouvert. Voir
[connecteur et procédure E8-A3](thetadata_options_smoke.md).

## E11 — Oracle H20 × Global Ranking H20 — `FAIT_NO_GO`

Le nouveau Global Ranking H20 strictement OOF contient 4,23 M de rangs sur
2 696 symboles et 13 folds. Son IC global CatBoost vaut `+0,0237`, mais aucun
candidat du championnat n''est éligible à cause de l''instabilité temporelle.
Le croisement propre avec l''Oracle P0f couvre 543 153 événements, 1 625 dates
et 1 461 symboles, soit 93,21 % des événements TOP20.

Dans le pool Oracle, l''IC tombe à `+0,0101`. Le haut du ranking pris en LONG
ajoute seulement `+11,8 bp` contre l''Oracle entier, IC95
`[-24,3 ; +45,8] bp`. Le bas reste haussier en valeur absolue et donne
`−1,329 %` net lorsqu''il est pris en SHORT. Le portefeuille LONG/SHORT vaut
`+8,4 bp`, IC95 `[-20,9 ; +36,6] bp`. Les trois verdicts sont `NO_GO` : le
ranking trie faiblement les rendements relatifs, mais ne distingue pas D1 de
D10. Aucun changement du serving, du backtest ou du live. Artefact canonique :
`artifacts/research/oracle_global_rank_cross/oracle-global-rank-cross-20260911141556`.
Voir [E11 — croisement Oracle H20 × Global Ranking H20](oracle_global_ranking_cross_e11.md).

## E12 — Pont de monétisation Oracle H20 — `FAIT_NO_GO_OR_BLOCKED`

E12 relie l'étude d'événements Oracle au contrat exécutable : open J+1,
sortie H20, déduplication, huit positions, comparaison priorité Oracle /
liquidité / 200 tirages aléatoires, filtre tradable PIT et lifecycle PROD. Sur
582 700 événements OOF, le rendement net fixe moyen reste positif à `+1,103 %`.
Après capacité, la priorité Oracle vaut `+2,540 %` et bat le 95e percentile de
tous les tirages aléatoires, mais son IC95 recouvre zéro.

Le replay PROD dynamique exécute 2 013 trades sur 1 160 dates et ne conserve que
`+0,276 %` moyen, IC95 journalier `[-0,290 ; +0,900] %`. Le lifecycle enlève
`2,119 points` aux mêmes événements H20, avec un IC95 du delta entièrement
négatif. Les 686 trailing stops perdent `-10,93 %` en moyenne ; 707 candidats
sont rejetés par le gap 3 %. Enfin, les snapshots tradables stricts ne couvrent
que 60/1 764 dates. La sensibilité `degraded` devient négative (`-0,791 %`),
mais ne constitue pas une preuve PIT canonique. Aucune promotion n'est
autorisée. Artefact canonique :
`artifacts/research/oracle_monetization_bridge/oracle-monetization-bridge-20260911154131`.
Voir [E12 — pont de monétisation Oracle H20](oracle_monetization_bridge_e12.md).

## E13 — Veto pré-entrée Oracle — `FAIT_NO_GO_OR_BLOCKED`

E13 entraîne un CatBoost mutualisé à prédire le futur motif `trailing_stop`
avec uniquement des variables disponibles au close J ou à l'open J+1. Les 13
folds sont strictement expanding et purgés : toute sortie d'un exemple train
précède le début du fold test. Sur 32 314 événements OOF, l'AUC vaut `0,6259` et
le taux de trailing progresse de 21,84 % dans le décile faible risque à 58,14 %
dans le décile fort risque.

Cette discrimination ne se transforme pas en avantage portefeuille. Le veto
primaire 20 %, dont le seuil est appris uniquement sur chaque train, donne
`+0,357 %` moyen contre `+0,328 %` pour la baseline, mais son delta journalier
est `-0,052 %`, IC95 `[-0,185 ; +0,087] %`. Le trailing sélectionné ne baisse
que de 33,35 % à 32,82 %, le Q05 se dégrade et la stabilité semestrielle échoue.
L'ATR% porte 26,48 % de l'importance : le modèle apprend surtout la mécanique
du stop proportionnel à l'ATR, pas une perte évitable. Les snapshots tradables
stricts ne couvrent que 53 dates. Aucun seuil n'est promu. Artefact canonique :
`artifacts/research/oracle_pre_entry_veto/oracle-pre-entry-veto-20260911155716`.
Voir [E13 — veto pré-entrée après Oracle](oracle_pre_entry_veto_e13.md).

## E14 — Cible économique pré-entrée — `FAIT_NO_GO_OR_BLOCKED`

E14 remplace le motif mécanique de sortie d'E13 par deux cibles OOF : rendement
net PROD winsorisé sur train et probabilité de perte nette. Sur 32 314
événements, l'IC utilité global vaut `+0,0364` et le score de non-perte
`+0,0592`. Le décile d'utilité supérieur rapporte `+1,162 %` avec 30,60 % de
pertes, contre `+0,433 %` et 49,20 % pour le décile inférieur, mais la relation
n'est pas monotone et l'IC quotidien moyen n'est que `+0,0047`.

Le veto primaire 20 % échoue : `+0,149 %` par date contre `+0,360 %` pour la
baseline, delta `-0,188 %`, IC95 `[-0,545 ; +0,132] %`, Q05 dégradé et seulement
6/14 semestres améliorés. L'hybride diagnostique Oracle/utilité 50/50 atteint
`+0,460 %` par date et améliore le Q05, mais son delta de `+0,063 %` est non
significatif et positif sur seulement 7/14 semestres. Aucun seuil ni poids n'est
promu. Les snapshots tradables stricts restent limités à 53 dates. Artefact :
`artifacts/research/oracle_pre_entry_utility/oracle-pre-entry-utility-20260911162146`.
Voir [E14 — cible économique pré-entrée](oracle_pre_entry_utility_e14.md).

## E15 — Audit structurel du lifecycle — `FAIT_NO_GO_OR_BLOCKED`

E15 croise quatre règles figées de trailing (PROD, activation après +0,5R,
après +1R, aucun trailing) avec TP PROD ou aucun TP. Le candidat primaire +0,5R
avec TP donne `+0,0419 %` par date sur événements appariés, IC95 recouvrant zéro,
puis `-0,0830 %` après capacité. Il dégrade Q05/Q01 et la confirmation depuis
2023 vaut `-0,2327 %`. Retarder le trailing transforme principalement les 686
trailing stops PROD en 457–498 stops initiaux plus profonds.

Le diagnostic sans TP révèle une convexité importante sur l'univers large :
`prod_no_tp` atteint `+1,810 %` moyen et un delta portefeuille de `+0,711 %`,
IC95 `[+0,078 ; +1,277] %`. Mais le delta passe de `+1,380 %` avant 2023 à
`-0,489 %` depuis 2023 ; sur les snapshots tradables dégradés, ce contrat tombe
à `-0,360 %`. Les 20 meilleurs trades portent 69 % du gain et la couche PIT
`full` ne couvre que 60 dates. Aucun contrat n'est promu et le lifecycle PROD
reste inchangé. Artefact canonique :
`artifacts/research/oracle_lifecycle_structural_audit/oracle-lifecycle-audit-20260911164445`.
Voir [E15 — audit structurel du lifecycle](oracle_lifecycle_structural_audit_e15.md).

## E16 — Reconstruction PIT de l’univers tradable — `FAIT_NO_GO_OR_BLOCKED`

E16 explique la couverture trompeuse d’E12/E15 : 1 750 dates ont un ancien run
`full`, mais 60 seulement restent canoniques après des publications `degraded`.
Ces anciens `full` ne couvrent ni `history_days`, ni `bars_available`, ni
`close_price`, ni `adv_usd`, et seulement 17,81 % des spreads : ils ne sont pas
requalifiés. La reconstruction bar-PIT couvre 1 764/1 764 séances et
582 698/582 700 événements. Le H20 fixe sous capacité vaut `+2,808 %`, mais le
lifecycle PROD seulement `+0,544 %`, IC95 recouvrant zéro.

`prod_no_tp` est globalement positif avec un IC95 de delta portefeuille > 0,
mais échoue depuis 2023 (`−0,2277 %`) et dégrade Q05 (`−15,44 %` à `−16,91 %`)
ainsi que Q01 (`−22,18 %` à `−22,65 %`). Le trailing après `+0,5R` reste
négatif après capacité et depuis 2023. Aucun contrat n’est promu. Artefact :
`artifacts/research/oracle_tradable_pit_reconstruction/oracle-tradable-pit-reconstruction-20260911192318`.
Voir [E16 — reconstruction PIT et réplication E12/E15](oracle_tradable_pit_reconstruction_e16.md).

## E17 — Bibliothèque d’alphas directionnels price-only H60/H120 — `FAIT_NO_GO`

E17 sort entièrement du pipeline Oracle et évalue six signaux price-only plus
un composite figé sur 1 798 actions, du 2018-07-01 au 2025-12-31. Le contrat est
PIT au close J, entrée open J+1, sortie open J+H+1, filtre de liquidité à J,
top/bottom 20 %, portefeuille 50/50 dollar-neutral, rebalance 20 séances et
6 bps aller-retour par jambe. Le rapport confirme `oracle_used=false`.

Le composite primaire H60 possède un IC positif (`+0,0138`, IC95 entièrement
positif), mais le rendement long/short de `+0,414 %` n’est pas significatif
(IC95 `[-0,430 ; +1,102] %`), seuls 46,67 % des semestres sont positifs et la
jambe SHORT perd `−2,288 %`. Verdict : `NO_GO` pour une stratégie directionnelle
symétrique.

Le momentum résiduel 120–10 à H120 est un `DISCOVERY_CANDIDATE` : IC `+0,0474`,
long/short `+1,664 %`, IC95 `[+0,552 ; +2,527] %`, 80 % de semestres positifs.
Mais la jambe SHORT reste perdante (`−4,368 %`) et le candidat a été identifié
après lecture des diagnostics. Il suggère un alpha de classement relatif ou
long-only à confirmer sur données nouvelles, pas une solution D1/D10. Les
métadonnées actuelles non historisées ajoutent un risque de survivorship bias.
Aucune promotion n’est autorisée. Artefact :
`artifacts/research/directional_alpha_book/directional-alpha-book-20260911194051`.
Voir [E17 — bibliothèque d’alphas price-only](directional_alpha_book_e17.md).

## E17-B — Confirmation prospective momentum résiduel H120 — `BLOCKED_DATA_UNAVAILABLE`

E17-B fige avant nouvelles observations le seul candidat exploratoire d’E17 :
momentum résiduel 120–10, H120, long-only TOP20, entrée open J+1, sortie open
J+121, rebalance 20 séances et 6 bps de coûts. La première date admissible est
le 14 septembre 2026 ; 2018–2025 est définitivement exclu de la confirmation.
Le contrat JSON est protégé par une empreinte canonique SHA-256.

Un verdict exige au moins 24 cohortes matures, quatre semestres d’entrée et 50
titres sélectionnés en moyenne. Il faut ensuite battre en moyenne et avec un
IC95 positif l’univers éligible et SPY, rester positif en absolu, être positif
sur au moins 60 % des semestres et respecter le gate de concentration. Les
seuls verdicts possibles sont `PENDING_DATA`, `NO_GO` et
`GO_RESEARCH_SHADOW_ONLY`. Le rapport initial est logiquement `PENDING_DATA`.
La base disponible s’arrêtant au 30 juin 2026, aucune observation postérieure
au début prospectif du 14 septembre 2026 n’existe. L’expérience est bloquée
jusqu’à reprise de l’alimentation des barres. Aucune promotion production n’est
autorisée.

Voir [E17-B — confirmation prospective](directional_alpha_book_confirmation_e17b.md).

## E17-C — Robustesse historique momentum résiduel H120 — `FAIT_NOT_ROBUST`

E17-C applique des contrôles verrouillés au candidat E17 sans revendiquer un
nouvel OOS. Sur 95 cohortes, le LONG net vaut `+7,696 %` et l’excès contre
l’univers `+2,294 %`, avec IC95 `[+0,959 ; +3,463] %`. Les cinq sous-univers
hash, les quatre calendriers et 14/21 secteurs sont positifs ; les 20 principaux
symboles ne portent que 13,36 % des contributions positives.

Le verdict reste `NOT_ROBUST` : l’excès contre SPY de `+1,194 %` a un IC95
`[-1,279 ; +4,093] %`, et le bloc 2021–2022 perd `−0,770 %` contre l’univers.
Le signal est donc un classement relatif diversifié mais dépendant du temps,
pas un alpha autonome universel ni une solution D1/D10. Aucun serving n’est
modifié. Artefact :
`artifacts/research/directional_alpha_book_robustness/e17c-robustness-20260911201018`.
Voir [E17-C — robustesse historique verrouillée](directional_alpha_book_robustness_e17c.md).

## E18-A — Attribution bêta, secteurs et régimes — `FAIT_MARKET_OR_SECTOR_EXPOSURE`

E18-A conserve exactement le momentum résiduel H120 et les 95 cohortes E17,
puis attribue la performance avec des informations PIT à J. Le portefeuille a
un bêta moyen de `1,021`. Sur `+7,696 %` nets par cohorte H120, la contribution
estimée du marché vaut environ `+6,990 %`. Le rendement beta-hedged tombe à
`+0,645 %`, IC95 `[-1,955 ; +3,263] %`.

La sélection n’est pas un simple pari sectoriel : l’excès sector-neutral contre
l’univers reste `+1,402 %`, IC95 `[+0,429 ; +2,239] %`. Mais la combinaison
sector-neutral + beta-hedged vaut `−0,238 %`, IC95 `[-2,360 ; +2,168] %`.
2021–2022 reste négatif sous toutes les décompositions et 2023–2025 devient
`−1,068 %` après neutralisation combinée. Aucun des quatre régimes SPY figés ne
présente à la fois IC95 positif et réplication temporelle. Verdict :
`MARKET_OR_SECTOR_EXPOSURE`, principalement marché. Aucun filtre de régime ni
serving n’est autorisé. Artefact :
`artifacts/research/directional_alpha_attribution/e18a-attribution-20260911201902`.
Voir [E18-A — attribution de l’alpha H120](directional_alpha_attribution_e18a.md).

## E19-A — Audit de disponibilité PIT des fondamentaux — `FAIT_PARTIAL_CONTRACT_BLOCKED`

E19-A audite 1 798 actions sur 2018–2025 et reconstruit une disponibilité SEC
conservatrice à la séance suivant le dépôt. Les 45 132 lignes SEC couvrent
1 621 symboles (`90,16 %`). Sur 2 369 379 lignes tradables, 89,57 % possèdent
au moins une comptabilité fraîche de moins de 180 jours ; l’âge médian est 50
jours. ROA, ROE, marges, croissance et revenue ont une couverture suffisante.
Les estimations forward, PEG et forward PE sont totalement absentes.

Le training reste interdit car le loader expose cinq défauts : utilisation le
jour même du filing, absence de période fiscale/form/accession, aucune priorité
multi-fournisseur, pas de prédécesseur antérieur au début et remplacement des
NaN par des constantes. Des incohérences sémantiques touchent aussi
debt/equity, EBITDA, dividend yield et estimate revision. Verdict :
`PARTIAL_CONTRACT_BLOCKED`, pas un manque de volume. Artefact :
`artifacts/research/fundamental_pit_availability/e19a-fundamental-pit-audit-20260911203804`.
Voir [E19-A — disponibilité PIT des fondamentaux](fundamental_pit_availability_e19a.md).

## E19-A2 — Correction du contrat PIT fondamental — `COMPLETE_DATA_READY`

Le loader applique désormais une date effective conservatrice : dépôt SEC à
J+1 et snapshots non-SEC au plus tôt le lendemain de leur collecte. Les
collisions utilisent une priorité déterministe, le dernier dépôt antérieur au
début de fenêtre est conservé et les absences sont encodées par des masques au
lieu de constantes sémantiques. La migration 0074 ajoute date de disponibilité,
période fiscale, formulaire, accession et dividende par action. Le mapper SEC
utilise désormais la dette financière, ne confond plus operating income et
EBITDA et sépare dividend/share du yield.

Le rafraîchissement SEC 2016–2025 a ensuite traité 1 798 symboles et persisté
59 358 lignes. Le nouvel audit canonique couvre 1 622 symboles SEC (90,21 % de
l’univers), 89,57 % des lignes quotidiennes avec une comptabilité fraîche de
moins de 180 jours et 99,28 % de lineage complet. Tous les gates passent ; le
verdict est `DATA_READY` et E19-B est désormais autorisée. Artefact :
`artifacts/research/fundamental_pit_availability/e19a-fundamental-pit-audit-20260912085103`.
Voir
[E19-A2 — contrat PIT fondamental](fundamental_pit_contract_e19a2.md).

## E19-B — Bibliothèque d’alphas fondamentaux PIT — `FAIT_VALUE_CANDIDATE_ONLY`

E19-B a été pré-enregistrée avant lecture des résultats puis exécutée sur
1 798 actions, 2018–2025, avec disponibilité SEC J+1, fraîcheur maximale de
180 jours, cinq folds OOF, 63 cohortes et neutralisation quotidienne secteur +
taille. Le composite qualité/valeur/croissance/levier/amélioration possède un
IC positif, mais aucun spread exploitable : à H60, IC `+0,46 %`, LONG
`+3,25 %`, SHORT `-3,32 %` et LONG/SHORT `-0,03 %`; depuis 2023 le spread vaut
`-0,28 %`. Son `GO_LONG` mécanique est expliqué par le rendement absolu : la
jambe LONG fait `-0,09 %` contre SPY à H60. Verdict scientifique composite :
`NO_GO`; aucun serving modifié.

La famille valeur, testée dès le protocole initial, ressort seule : à H60,
IC `+4,47 %` [borne 95 % `+3,31 %`] et spread net `+1,00 %` [borne
`+0,06 %`], avec 80 % des folds et semestres positifs. À H120, IC `+6,58 %`
et spread `+2,18 %` [borne `+0,33 %`], 100 % des folds positifs. Elle reste
positive depuis 2023. C’est un candidat de recherche relatif, pas encore une
stratégie short absolue. Prochaine action permise : confirmation E19-C valeur
seule, verrouillée et sans retuning. Artefact :
`artifacts/research/fundamental_alpha_book/fundamental-alpha-book-20260912112042`.
Voir [E19-B — bibliothèque fondamentale PIT](fundamental_alpha_book_e19b.md).

## E19-C — Confirmation verrouillée du facteur valeur — `FAIT_NO_GO`

E19-C a figé sans retuning le score valeur E19-B et l’a évalué sur deux blocs
qui n’avaient pas contribué aux métriques OOF précédentes : 2018-07-02 à
2020-07-01 et 2025-07-10 à 2025-12-31. Sur 33 cohortes H60, l’IC vaut
`-3,61 %` [IC95 `-5,15 ; -2,01 %`] et le spread net `-0,99 %`. À H120,
l’IC vaut `-5,23 %` et le spread `-1,59 %`. Le LONG sous-performe SPY de
`-2,16 %` à H60 et `-2,70 %` à H120.

Le holdout ancien est fortement négatif (`-1,63 %` H60 ; `-2,71 %` H120),
alors que 2025H2 est positif (`+1,35 %` ; `+3,25 %`). Les cinq sous-univers
hash sont négatifs aux deux horizons. Verdict `NO_GO` : le facteur est dépendant
de période et ne doit être ni promu, ni inversé, ni filtré a posteriori par un
régime choisi sur ces résultats. Aucun serving n’a changé. Artefact :
`artifacts/research/fundamental_value_confirmation/fundamental-value-confirmation-20260912114827`.
Voir [E19-C — confirmation valeur](fundamental_value_confirmation_e19c.md).

## E20-A — Audit PIT Opening Window après Oracle — `BLOCKED_NO_OPENING_WINDOW_DATA`

E20-A audite la matière nécessaire à une confirmation directionnelle au
prémarché et dans les 15/30/60 premières minutes de J+1. La population de
référence P0f compte 582 306 événements TOP20 OOF, 1 763 dates et 1 472
symboles entre juillet 2018 et juillet 2025. La table
`stock_opening_window_bars` existe mais contient zéro ligne : aucun événement,
aucune date et aucun symbole Oracle ne possèdent une ouverture appariable.

Le seul run de collecte a été correctement ignoré un dimanche fermé. E20-A ne
rejette donc pas le signal : elle bloque E20-B/C faute de données. Les règles
simples exigent au moins 126 dates et 5 000 événements ; un modèle exige 378
dates, 20 000 événements et quatre semestres. Une collecte future doit être
jointe à de nouveaux scores Oracle shadow ; elle ne chevauchera pas
automatiquement l’ancien OOF arrêté en juillet 2025. Aucun modèle, règle ou
serving n’a changé. Artefact canonique :
`artifacts/research/oracle_opening_window_availability/e20a-opening-availability-20260913211726`.
Voir [E20-A — disponibilité Opening Window](oracle_opening_window_availability_e20a.md).

## E20-B — Confirmation Opening Window price-only — `GO_RESEARCH_VOLUME_ABLATION`

Politique primaire figée : variation à 30 minutes, abstention sous ±0,50 %, OHLC uniquement. Sur 1 763 séances : 559 513 événements observés, couverture 96,09 %, précision globale 53,96 %, précision D1/D10 56,91 %, rendement cible signé quotidien +1,414 % avec IC95 [+1,226 % ; +1,619 %], 65,63 % de folds et 100 % de semestres positifs. Tous les gates passent. Ce n'est pas encore un PnL d'entrée à 10:00. E20-C volume incrémental est autorisée. Artefact : `artifacts/research/oracle_opening_price_confirmation/e20b-opening-price-only-20260914051444`. Voir [E20-B](oracle_opening_price_confirmation_e20b.md).
## POC Alpaca options trades versus barres — `GO_RESEARCH_ONLY`

Sur la séance du 11 septembre 2026, 10 contrats CALL/PUT ATM proches de DTE 10 sur AAPL, MSFT, NVDA, TSLA et AMD ont été comparés entre l'endpoint transactions et les barres une minute Alpaca. Les 10 volumes et compteurs de transactions concordent exactement ; ratios médians 1,0 et erreur relative médiane du VWAP recomposé 2,64 × 10⁻⁹.

Le POC autorise des features ML prospectives fondées sur transactions/volume Alpaca, mais ne prouve pas l'exhaustivité OPRA puisqu'il compare deux endpoints du même fournisseur. Provenance `UNVERIFIED_OPRA`, serving interdit et confirmation multi-jours requise avant activation d'un batch transactions complet. Artefact : `artifacts/research/options_delayed_trade_poc/poc-20260912224359/report.json`. Voir [Options retardées Alpaca et ajustements OCC](options_delayed_alpaca_occ.md).


## NYSE Auction History POC — `SMOKE_OK_RESEARCH_ONLY`

Le batch officiel `auction_imbalance_sync` demeure désactivé : Nasdaq NOII, NYSE live et NYSE TAQ historique complet sont commerciaux. Une route JSON non documentée utilisée par l'interface Web NYSE a été confirmée sur IBM le 11 septembre 2026 : six agrégats minute 09:25–09:30 avec imbalance, paired quantity et book clearing price.

Le mode univers a audité 1 798 symboles : 1 015 étaient présents dans les 2 273 symboles de l'interface NYSE. La collecte d'une séance a été limitée par le serveur après 51 réponses. Le POC sauvegarde désormais les résultats partiels et sait les reprendre sans doublon, mais la collecte quotidienne complète gratuite est jugée non fiable. Les données restent post-auction ; aucun serving, table ou batch planifié. Voir [POC NYSE Auction History](nyse_auction_history_poc.md).


## Procédure de mise à jour du registre

Après chaque expérience, ajouter ou mettre à jour une ligne avec :

```text
ID / nom
hypothèse falsifiable
population exacte
target et horizon
protocole OOF/PIT
artefact canonique
métriques principales
gates passés/échoués
verdict séparé LONG, SHORT et AMPLITUDE si applicable
lien vers le document détaillé
prochaine action autorisée
```

Ne jamais remplacer un `NO_GO` par une nouvelle interprétation sans nouvelle
information, nouveau contrat pré-enregistré et nouvelle validation. Conserver
les résultats négatifs : ils empêchent de répéter les mêmes recherches sous un
autre nom.

### E20-C — Ablation incrémentale du volume d'ouverture — NO-GO

Comparaison OOF appariée sur 354 967 événements, neuf folds temporels avec
embargo H20 : LightGBM prix seul contre le même modèle augmenté du volume SIP,
du nombre de transactions, de la taille moyenne et du VWAP aux checkpoints
5/15/30 minutes. Le volume augmente légèrement l'accuracy (+0,41 point) et
l'accuracy D1/D10 (+0,65 point), mais dégrade l'AUC (-0,0021), le rendement
cible signé (-0,047 point) et le rendement des décisions de confiance >= 0,55
(-0,123 point). L'AUC ne progresse que dans 4/9 folds et 3/10 semestres. Les
gates de stabilité et d'utilité économique échouent : ne pas intégrer ces
features et ne pas lancer de confirmation IEX. Artefact :
`artifacts/research/oracle_opening_volume_ablation/e20c-opening-volume-ablation-20260914170421`.
Voir [E20-C](oracle_opening_volume_ablation_e20c.md).

### E20-D — Replay économique price-only à 10:00 — NO-GO symétrique

Le replay de 2 259 trades après capacité rejette la politique LONG/SHORT :
le lifecycle donne -0,120 % par trade, IC95 journalier recouvrant zéro, et
7/15 semestres positifs. L'attribution montre +1,697 % en entrée contrefactuelle
à l'open mais -0,689 % en maintien H20 depuis l'entrée réellement possible à
10:00. Le retard coûte -2,386 points, avec IC95 entièrement négatif. Le SHORT
est structurellement mauvais (-4,015 % H20 depuis 10:00). Le LONG conserve
+2,822 % H20 et 10/15 semestres positifs, mais son IC95 recouvre zéro ; cette
découpe est post-hoc et exige une confirmation indépendante pré-enregistrée.
Artefact : `artifacts/research/oracle_opening_price_economic_replay/e20d-opening-price-economic-20260914175418`.
Voir [E20-D](oracle_opening_price_economic_replay_e20d.md).

### Meta Oracle A/B — veto des faux extremes : NO_GO F1

A : les scores Oracle seuls n'ajoutent rien au tri Oracle ; placebo et hasard
restent inferieurs. B : les 168 features d'origine ne donnent aucun gain
incremental a quota identique. Precision quotidienne Oracle keep80 47,01 %,
F1 Logistic 46,95 %, F1 CatBoost 46,97 %. Delta CatBoost -0,0398 point,
IC95 [-0,1675 ; +0,0955] ; seulement 4/9 folds et 1/6 annees positifs.
Le controle inverse universe-wide est significativement inferieur a Oracle.
Le holdout n'est pas charge et aucune promotion n'est autorisee. F2/F3 et
les variantes avancees ne sont pas testees ; ce NO_GO porte sur F1.
L'anomalie de reporting des bandes Oracle est corrigee : diagnostics A/B
recalcules en quatre bandes fixes 80-85/85-90/90-95/95-100 %, sans entrainement
ni changement des candidats, selections, rapports primaires ou verdicts.
Onze tests cibles passent ; les AUC par bande restent descriptives.

### Audit de complementarite directionnelle — HISTORICAL_DIAGNOSTIC_ONLY

Sur le nouvel Oracle `323684`, seules deux familles presentes sont alignables
sans selection future : dual-threshold et ranker conditionnel H3/H10/H20.
402 017 evenements et 1 134 dates par horizon ; anciens sept experts absents,
D1/D10 tail-only et observations d'ouverture exclus du panel principal.
Les correlations de scores sont faibles (0,10 a 0,22) mais aucun des six IC
residuels n'a un IC95 strictement positif avec blocs de 21 dates. H3 ranker
+0,0160, IC95 [-0,0008 ; +0,0295] ; H20 pratiquement nul. Ni ensemble supervise,
ni PnL, ni promotion. Le run v1 est supplante par v2, qui tient compte du H20
de selection Oracle et compare les scores sur les memes dates. Neuf tests passent.
Artefact : `artifacts/research/directional_complementarity/audit-20260914-v2`.
Voir [audit de complementarite, inventaire et limites](directional_complementarity_audit.md).

### E21 — Révisions chiffrées de guidance PIT — CLOSED / SUSPENDED_DATA_NOT_READY

**Décision finale du 15 septembre 2026 : piste fermée et suspendue.** Les
expériences E21-A à E21-B8 ont établi que l'information existe dans les
documents SEC, mais que la chaîne gratuite actuelle ne fournit pas une
couverture documentaire et sémantique suffisamment stable pour produire des
labels ML. Ce statut n'est pas un rejet de l'hypothèse économique : aucun test
directionnel propre n'a pu être autorisé.

Conséquences : aucun E21-B9 planifié, aucun entraînement, aucun branchement au
Meta Oracle, aucun backtest et aucun usage live. Le code de recherche,
les annotations et les artefacts sont conservés uniquement pour traçabilité.

Réouverture autorisée seulement si au moins une condition change
matériellement :

- source structurée de guidance historique réellement PIT et suffisamment
  couverte ;
- collecteur SEC démontré exhaustif par dépôt et annexe ;
- extracteur validé sur un nouveau corpus avec zéro faux intervalle, précision
  classée >=95 %, couverture NEW >=80 % et rappel de détection mesuré ;
- annotation humaine indépendante de la référence.

Les sections ci-dessous constituent l'historique de la piste fermée.

### E21-A — Revisions chiffrees de guidance PIT — BLOCKED_DATA_NOT_READY

Audit en lecture seule sur l'univers de 1 798 titres : 2 050 depots locaux du
3 au 11 septembre 2026, 203 lies a l'univers, 1 311 annexes referencees mais
zero contenu d'annexe telecharge. Le collecteur reconstruit mal les href et
perd le repertoire d'accession SEC, expliquant les 404. Correctif a faire,
non applique dans cet audit. Sur 100 documents bornes, 23 contiennent 69
passages candidats ; revue qualitative : vraies perspectives, realises et
boilerplate melanges. Aucune paire ancienne/nouvelle guidance confirmee.
Les depots sont posterieurs aux cours disponibles : pas de test directionnel
possible avec cet echantillon. Hypothese non rejetee ; pas d'entrainement,
de backtest ou de modification des batchs. Quatre tests cibles passent.
Artefact : `artifacts/research/guidance_pit_availability/e21a-20260914-v1`.
Voir [E21-A : contrat, exemples, blocages et prochaines etapes](guidance_pit_availability_e21a.md).

Suite E21 : URL SEC corrigées et smoke historique janvier–juin 2025 terminé.
14 annexes distinctes / six émetteurs ; neuf comparaisons numériques revues
sur cinq paires de publications. Les 18 fourchettes correspondent aux textes
locaux. ABM exclu pour changement de définition non-GAAP. 60 tests ciblés
passent. Statut : SMOKE_MANUEL_OK, toujours DATA_NOT_READY pour une expérience
directionnelle (disponibilité PIT et extraction sémantique non validées).
Voir [résultats détaillés et exclusions](guidance_historical_smoke_e21.md).

### E21-B — Extraction structurée — CLOSED / SUSPENDED_DATA_NOT_READY

Socle de recherche implémenté : suggestions sémantiques, champs validés
séparés, contrôle des hashes, revue avec sources immuables, comparabilité
fail-closed et prédécesseur observé. Smoke : 14 documents, 85 candidats,
zéro erreur, zéro paire automatiquement approuvée. Disponibilité historique,
corpus multi-années exhaustif et validation indépendante restent à acquérir.
Pas d'entraînement ni de modification des batchs quotidiens.
Voir [contrat E21-B et procédure de revue](guidance_structured_e21b.md).

Suite : archives submissions SEC et progression ajoutées ; 80 tests ciblés
passent. Collecte bornée ABM/TTC 2022-10 à 2024-12 lancée dans
`artifacts/research/guidance_historical_backfill/e21b-historical-2023-2024-v1`.
Résultat non encore analysé au lancement ; dates nouvelles mais émetteurs
connus, pas une confirmation indépendante par émetteur.

Résultat analysé : 19 dépôts/19 annexes, zéro erreur, zéro troncature ; pages
anciennes non nécessaires dans cette fenêtre. Extraction : 65 candidats,
18 avec suggestion de mesure unique. Revue nominale : 16 fourchettes annuelles
d'EPS ajusté retrouvées 16/16, sans revendication de rappel global ou de signal
boursier. Douze comparaisons nominales : trois hausses, quatre baisses de milieu,
cinq inchangées. Statut toujours DATA_NOT_READY : sémantique et preuve PIT
non approuvées. Référence dans `guidance_structured/e21b-2023-2024-v1/manual_reference.json`.

E21-B2 : rôles NEW_FORECAST/PRIOR_FORECAST/REALIZED_RESULT/AMBIGUOUS
implémentés avec abstention. Validation figée sur nouveaux émetteurs A/ADBE
2023 : huit annexes, zéro erreur, 71 candidats. Revue assistant : 66 prévisions
actuelles et cinq faux intervalles. 25/66 prévisions classées (37,9%),
46/71 abstentions. Classes prior/réalisé absentes de la référence, donc non
validées empiriquement. Couverture tableaux insuffisante ; DATA_NOT_READY.
89 tests ciblés passent. Aucun entraînement ni backtest.
Voir [protocole et résultats E21-B2](guidance_role_validation_e21b.md).

E21-B3 : lecteur de tableaux HTML implémenté avec provenance cellule/ligne,
en-têtes de période et colonnes ancien/actuel. Sur le corpus de développement
A/ADBE : couverture des prévisions détectées de 25/66 à 63/66 (95,5 %), trois
prévisions et cinq faux intervalles en abstention. Ce corpus ayant servi au
développement, ce n'est pas une validation indépendante. Aucun rendement,
entraînement, backtest ou batch quotidien modifié. Voir
[lecteur et limites E21-B3](guidance_table_extraction_e21b.md).

E21-B4 — validation indépendante CRM/BBY/FDX 2024 : 14 annexes, 12
publications productrices, 99 candidats, zéro erreur de collecte. Référence :
76 NEW, neuf PRIOR, 14 faux intervalles, zéro vrai réalisé. Règles figées :
précision classée 94,1 %, couverture NEW 14,5 %, PRIOR 55,6 % avec support
insuffisant, un faux intervalle accepté à cause d'une note inline XBRL.
Échec des trois gates pré-enregistrés ; aucun ajustement post-résultat.
Conclusion DATA_NOT_READY, pas d'entraînement/backtest. Voir
[protocole, matrice et diagnostic E21-B4](guidance_table_validation_protocol_e21b4.md).

E21-B5 — notes inline rejetées et headings Guidance/Forecast/Targets
généralisés. Confirmation gelée ABBV/ANF/CPB 2024 : 23 candidats, 15 NEW,
sept PRIOR, un réalisé. NEW reconnu 15/15 mais PRIOR 0/7, précision classée
68,2 %, gate échoué. Le réalisé unique reste en abstention. Cinq annexes ANF
manquées car leurs noms `pressrelease` ne contiennent pas EX99 : couverture
des dépôts complète mais couverture des annexes incomplète. Verdict FAIL,
DATA_NOT_READY ; aucun entraînement/backtest. Voir
[résultats E21-B5](guidance_table_validation_protocol_e21b4.md).

E21-B6/V3 — OLD→NEW, td/colspan et pressrelease implémentés. Confirmation
BWA/CCK/BJ 2024 : 52 candidats ; référence 34 NEW, huit PRIOR, dix faux
intervalles. NEW 33/34, PRIOR 7/8, mais sept paires de résultats multi-périodes
classées à tort REALIZED. Précision 85,1 %, gate zéro faux intervalle échoué.
REALIZED véritable absent et non validé. Verdict FAIL/DATA_NOT_READY ; aucun
entraînement/backtest. Voir [rapport E21-B6](guidance_table_validation_protocol_e21b4.md).

E21-B7/V4 — grammaire stricte des intervalles réalisés et rejet des paires
multi-périodes. Confirmation TDG/PH/KFY 2024 : 73 candidats, 58 NEW et 15
PRIOR. Les 51 décisions sont exactes (100 %) et PRIOR atteint 15/15, mais NEW
seulement 36/58 (62,1 %). Quatre vraies fourchettes KFY utilisant 'in the
range of X and Y' sont aussi manquées : rappel détecteur audité 73/77 (94,8 %),
rappel NEW bout en bout 36/62 (58,1 %). Verdict FAIL/DATA_NOT_READY, sans
entraînement/backtest. Voir [rapport E21-B7](guidance_table_validation_protocol_e21b4.md).

E21-B8/V5 — restauration de 'in the range of X and Y', flexions des verbes de
prévision et portée bornée des listes. Le smoke TDG/PH/KFY atteint 50/62 NEW
(80,6 %) et 15/15 PRIOR. La confirmation APOG/SYY/EL échoue : 44 candidats,
41 NEW et trois faux candidats correctement laissés ambigus ; précision 100 %
mais couverture NEW 17/41 (41,5 %). Le rappel de détection est non mesurable :
APOG ne couvre qu'un dépôt sur six et au moins 22 paires EL en notation
'$.xx' sont ignorées. Verdict FAIL/DATA_NOT_READY, sans entraînement/backtest.
Voir [rapport E21-B8](guidance_table_validation_protocol_e21b4.md).
Artefacts : `artifacts/research/meta_oracle/meta-oracle-a-20260914194645`
et `artifacts/research/meta_oracle/meta-oracle-b-20260914201547`.
Voir [protocole](meta_oracle.md) et [resultats et limites](meta_oracle_execution.md).

### E22 — Trajectoire pré-signal Oracle J−5 à J — NO_GO_H20

Trois variantes pré-enregistrées : O0 canonique, 35 lags ordonnés J−1 à J−5,
et 14 descripteurs compacts de la trajectoire J−5 à J. Le smoke H20 sur 50
symboles et 91 155 lignes termine sans écriture en base ni changement du
serving. Les lags bruts échouent ; la forme compacte améliore AUC (+0,0227) et
average precision (+0,0240), mais pas suffisamment la précision du TOP20
(+0,0022) et manque les gates de stabilité. Ce résultat n'est pas interprétable
scientifiquement sur 50 symboles.

Le smoke a détecté une faiblesse de protocole : les 12 premiers folds
s'arrêtaient à mi-2024. Avant le run complet, E22 a été corrigé pour conserver
les 12 folds valides les plus récents et couvrir la fin 2025. Une erreur neutre
de comptage du premier changement de signe a aussi été corrigée.

Le second smoke technique confirme les 12 folds récents du 8 juillet 2019 au
11 juillet 2025. E22 est prêt pour le run H20 complet sur 2 493 symboles ; aucun
résultat de smoke n'est utilisé pour promouvoir une variante.

Run complet terminé : 2 493 symboles, 2 557 086 prédictions OOS et 1 512 dates.
Les lags J−1 à J−5 n'ajoutent que +0,000519 d'AUC, +0,000809 d'average
precision et +0,000225 de précision TOP20 ; ils ne gagnent que 7/12 folds et
échouent quatre gates sur cinq. La forme compacte ajoute +0,000063 d'AUC,
+0,000019 d'average precision et perd 0,000027 de précision TOP20 ; 6/12 folds
gagnants. Verdict NO_GO_H20 : aucune modification de `oracle.json`, du serving,
des prédictions ou du backtest. Le signal du smoke 50 était un effet
d'échantillon.

Artefact complet :
`artifacts/research/oracle_trajectory/e22-h20-20260915190508`.

Voir [protocole, variantes, gates et smoke](oracle_trajectory_e22.md).

### E23 — D10 one-vs-rest avec trajectoires J−10 à J — NO_GO

Nouvelle formulation LONG-only dans le TOP20 Oracle OOF : D10 réel à H20 vaut
1 et tous les déciles D1 à D9 valent 0. Quatre variantes isolent l'état J, la
trajectoire price/volume, les onze scores quotidiens de sentiment J−10 à J et
leur combinaison. Les lags utilisent les séances globales exactes ; absence de
news et sentiment neutre restent distincts. Logistic et LightGBM contrôlent le
CatBoost primaire. Recherche uniquement, aucun serving ou SQL modifié.

Voir [contrat E23 et commandes](oracle_d10_trajectory_e23.md).

Smoke final : 50 symboles demandés, 33 dans le pool, 12 537 événements et deux
folds récents. Couverture news : 24,04 % à J, 67,58 % sur J−10 à J. Les quatre
variantes CatBoost terminent ; aucune métrique n'est interprétée sur ce petit
échantillon. Le chargement dense des lags a été séparé de la disponibilité des
labels futurs afin d'éviter une fuite par missingness. Dix-sept tests ciblés
passent. Artefact :
`artifacts/research/oracle_d10_trajectory/e23-smoke50-20260915-v2`.

Run complet : 582 700 événements, 1 472 symboles, neuf folds OOS de janvier
2021 à juillet 2025. Toutes les variantes et les trois modèles échouent aux
gates absolus ; toutes les trajectoires échouent aussi aux gates incrémentaux
contre l'état J. La meilleure AUC est LightGBM prix + sentiment à 0,5250, mais
son TOP10 gagne +0,727 %, sous le pool Oracle à +0,787 %. La meilleure sélection
économique est la baseline Logistic à J (+1,019 %, précision D10 25,22 %),
elle-même inférieure au classement par amplitude Oracle (+1,198 %, précision
D10 28,62 %) et instable. CatBoost sentiment est le meilleur signal
incrémental partiel (AUC +0,0098, AP +0,0117), sans amélioration économique
(+0,002 point) ni stabilité suffisante. Aucun serving ni SQL modifié. Artefact :
`artifacts/research/oracle_d10_trajectory/e23-d10-20260915203334`.

## P-MATH-0 — séparabilité non paramétrique — `NO_STABLE_SEPARATION`

Audit de l'espace d'information à J dans le pool Oracle OOF TOP20. Trois tâches
sont isolées : D1 contre D10, D10 contre D1–D9 et D1 contre D2–D10. Le
protocole combine MMD-RBF scalable, Energy Distance projetée,
Henze–Penrose/Friedman–Rafsky et classifier two-sample Logistic sur folds
chronologiques. Normalisation train-only, équilibrage et permutations
intra-date, combinaison Fisher et correction Holm empêchent les principaux
faux positifs. Aucun SQL ni serving modifié. Voir
[P-MATH-0](pmath0_nonparametric_separability.md).

Smoke technique validé sur 50 symboles demandés, 33 présents, 12 537
événements, 84 features et deux folds récents. Les trois tâches et les quatre
familles statistiques terminent ; cinq tests ciblés passent. Les métriques de
ce sous-univers alphabétique ne sont pas interprétées. Artefact :
`artifacts/research/pmath0_separability/pmath0-smoke50-20260916-v2`.

Run complet : 582 700 événements, 1 472 symboles, 84 features et neuf folds
OOS de janvier 2021 à juillet 2025. D1/D10 obtient une AUC Logistic médiane de
0,5077 et D10/reste 0,5096. D1/reste atteint 0,5380, mais seulement 5/9 folds
dépassent 0,53, contre le minimum gelé de 67 %. HP détecte une différence
multivariée stable sur les trois tâches ; MMD et Energy ne donnent pas les deux
confirmations stables exigées. Les trois verdicts restent donc
`NO_STABLE_SEPARATION`. Le faible signal asymétrique D1 ne doit pas être
promu ni servir à relâcher les gates ; P-MATH-1 devra ajouter une source
cross-asset réellement nouvelle. Aucun SQL ni serving modifié. Artefact :
`artifacts/research/pmath0_separability/pmath0-20260915232426`.

## P-MATH-1 — lead-lag cross-asset résiduel — `NO_GO_INCREMENTAL_LEAD_LAG`

P-MATH-1 teste une source d'information absente de P-MATH-0 : les mouvements
retardés des autres actions. Dans chaque fold, les rendements sont résidualisés
par SPY et le secteur avec des coefficients appris exclusivement sur le train.
Les leaders sont choisis sans labels et les arêtes J−1/J−2/J−3/J−5 doivent
conserver le même signe dans les deux moitiés chronologiques du train. Le test
compare pression seule, variables d'état seules et état augmenté de la pression.

Les gates ont été enregistrées avant le run : AUC pression médiane ≥ 0,53,
delta AUC médian ≥ +0,01, delta positif dans au moins 67 % des folds et gain de
rendement signé du top décile ≥ +0,25 %. Aucun lag 0, aucune écriture SQL et
aucun changement de serving. Voir
[P-MATH-1](pmath1_cross_asset_lead_lag.md).

Smoke technique validé sur 50 symboles demandés, 33 présents dans le pool,
12 537 événements et deux folds récents. Le graphe contient 448 arêtes
cumulées. Les cinq tests ciblés passent. Les AUC de ce petit sous-univers ne
sont pas interprétées. Artefact :
`artifacts/research/pmath1_cross_asset_lead_lag/pmath1-smoke50-20260916`.

Run complet : 582 700 événements, 1 472 symboles et neuf folds OOS. La
couverture pression atteint environ 93–94 % et chaque fold contient plus de
11 000 arêtes. Malgré cela, les AUC pression médianes valent 0,4956 pour
D1/D10, 0,4998 pour D10/reste et 0,4977 pour D1/reste. Les deltas AUC médians
sont compris entre +0,00001 et +0,00007, très loin du +0,01 requis ; les lifts
économiques médians sont également sous le gate. Le signal est nul OOS et la
piste est fermée sans tuning post-hoc. Artefact :
`artifacts/research/pmath1_cross_asset_lead_lag/pmath1-full-20260916-v2`.

## P-MATH-2 — signatures de trajectoire titre/marché/secteur — `NO_GO_INCREMENTAL_PATH_SIGNATURE`

Audit indépendant du graphe P-MATH-1. Le chemin J−19…J contient le temps, le
rendement du titre, SPY et le rendement médian du secteur. Les signatures
tensorielles exactes de profondeur 1, 2 et 3 sont testées avec une Logistic L2.
La profondeur 2 est primaire et la profondeur 3 confirmatoire. Même pool Oracle
OOF, mêmes trois tâches et mêmes folds que P-MATH-0/P-MATH-1. Aucun SQL ni
serving modifié. Voir [P-MATH-2](pmath2_low_depth_path_signatures.md).

Smoke technique validé sur 50 symboles demandés, 33 présents, 12 537
événements et deux folds. Couverture des chemins : 100 %. Les six tests ciblés
passent. Le témoin d'état chute lui-même sous 0,48 sur ce petit sous-univers ;
ses métriques ne sont donc pas utilisées pour statuer. Artefact :
`artifacts/research/pmath2_path_signatures/pmath2-smoke50-20260916`.

Run complet : 582 700 événements, 1 472 symboles, neuf folds et 100 % de
couverture des chemins. La profondeur 2 primaire obtient des AUC signature de
0,4996 (D1/D10), 0,4932 (D10/reste) et 0,5115 (D1/reste) ; ses deltas AUC sont
respectivement −0,0046, +0,00003 et +0,0016. La profondeur 3 confirmatoire ne
passe aucun gate non plus. Son meilleur signal, D1/reste, atteint AUC 0,5199 et
delta +0,0064 dans 6/9 folds, mais dégrade le rendement signé. La famille est
fermée sans recherche post-hoc de profondeur ou de fenêtre. Artefact :
`artifacts/research/pmath2_path_signatures/pmath2-full-20260916`.

## P‑MATH‑3 — quantiles conditionnels du rendement H20 — `NO_GO_DISTRIBUTION` / `NO_GO_DIRECTION`

Sept quantiles LightGBM pré-enregistrés (q05/q10/q25/q50/q75/q90/q95) sur les
événements Oracle OOF TOP20. Deux verdicts distincts : qualité de distribution
contre quantiles constants du train et séparation D1/D10 contre la Logistic
directe. Score primaire sans labels directionnels : `(q10 + q90)/2` ; q50 et
asymétrie sont secondaires. Même calendrier OOS et purge PIT que P‑MATH‑0 à 2.
Voir [protocole P‑MATH‑3](pmath3_conditional_quantiles.md). Aucun SQL ni
serving modifié.

Smoke technique : 50 symboles demandés, 33 présents, 12 537 événements et
deux folds ; les sept quantiles et les diagnostics terminent. Les résultats du
petit sous-univers ne sont pas interprétés. Artefact :
`artifacts/research/pmath3_conditional_quantiles/pmath3-smoke50-20260916`.

Run complet : 582 700 événements, 1 472 symboles, neuf folds OOS. Le pinball
moyen se dégrade de 1,67 % en médiane contre les quantiles constants du train
et n'est meilleur que dans 2/9 folds. La couverture q10/q90 est acceptable
(erreur médiane 2,40 points) mais insuffisante pour un GO distributionnel.
Le score primaire `(q10 + q90)/2` obtient AUC D1/D10 0,4793, contre 0,4890
pour la Logistic directe ; delta −0,0100 et lift du top décile quotidien
−0,527 point. Les gates directionnels échouent tous. q90/q95 ont des pinballs
individuels légèrement meilleurs dans 6/9 folds, indication exploratoire non
promue. Aucun serving ni backtest modifié. Artefact :
`artifacts/research/pmath3_conditional_quantiles/pmath3-full-20260916`.

### FR — Sprint 10-C2 : source officielle pour les clôtures litigieuses

Suivi économique au 4 octobre 2026 :
[passe publique gratuite et demande de preuves](../fr/demande_preuves_historiques_manquantes.md).
118 symboles, 21 379 fenêtres candidates, 212 intervalles CA ; quatre barres
officielles restent à corroborer, 97 couples fiscaux restent à revoir et un
refus causal sans ouverture est nécessaire pour Artois. Annonces émetteurs
partiellement corroborées, dont une erreur de paiement fournisseur pour ABC
Arbitrage. Aucun GO économique ni PnL ni serving ; aucun achat lancé.

Complément prioritaire : [Sprint 10-C3, réparation du fold7](../fr/sprint_10c3_reparation_fold7.md).
**Bilan final exécuté :** reconstruction ciblée98OHLC, aucune correction de prix,
fold7 admis126/126. Oracle OOF4/5/6/7 : NO_GO_INCREMENTAL_PILOT vsATR.
Direction sur deux folds6/7 : AUC0,5088, IC0,0272, spread brut−1,032 %,
**NO_GO_DIRECTIONAL_PILOT**. Réparation/confirmation terminée ; pas de serving,
SQL, performance2026 ni validation économique. Les statuts antérieurs de manque
de support ci-dessous sont historiques et dépassés pour le fold7 seulement.
Les 27 séances test manquantes n'ont pas de lacune ESMA dans les fenêtres
auditées. 104 couples titre/date nécessitent une corroboration de prix, dont
90 le 26 mars 2025. Collecte Euronext ciblée terminée, TLS vérifié : 90 titres
récupérés, 98 couples concordant sur les quatre OHLC EODHD et six non résolus.
Aucune admission, aucun nouvel entraînement, aucun serving modifié. Le Sprint10
reste ouvert ; reconstruire les preuves puis requalifier avant génération OOF.

Audit au 3 octobre 2026, sans entraînement ni mutation de données :
[rapport détaillé](../fr/sprint_10c2_audit_prix_independants.md).
Le fichier officiel Euronext de correction du 19 octobre 2020 est accessible
gratuitement. Sur 84 titres concernés par les lacunes du fold 3, 78 clôtures
corroborent EODHD seul, quatre les deux fournisseurs et deux aucun.
48 titres ont aussi des différences open/high/low, 83 de volume ; le XLSX ne
résout pas ces champs. **Fold toujours bloqué**, sans modification des seuils
ou sélection du modèle. Les preuves ESMA manquantes restent requises.
Rapport de référence :
`artifacts/fr/research/official_close_audit/euronext-20201019-audit-20261003-final/report.json`.
# Actualisation FR — Sprint 11-C, 4 octobre 2026

**Sprint 12-E :** [périmètre économique exploitable](../fr/sprint_12e_perimetre_exploitable.md).
Audit local exécuté sur 21 379 chemins, 16 032 contrôles partiels favorables,
zéro chemin entièrement qualifié. Fort biais de couverture entre intentions
Oracle (30,24 %) et contrôle uniforme (74,99 %). Aucun rendement consulté pour
sélectionner les preuves, aucun PnL ni nouveau fit. 31 tests ciblés passent.

**11-H :** [arbitrage préparatoire et disponibilité PIT](../fr/sprint_11h_arbitrage_et_disponibilite_pit.md).
38 preuves PDF intègres ; 33 décisions indépendantes PENDING et aucune
disponibilité historique Web qualifiée dans le dossier. Corroborations officielles
Nexans/SMCP repérées, sans promotion de label ni antidatation. Aucun fit.

**11-G :** [seconde passe documentaire, non indépendante](../fr/sprint_11g_seconde_passe_documentaire.md).
33/33 fiches relues ; contradiction Nexans et cas mixte Aramis maintenus en réserve.
Économies Maisons du Monde et TCAM Exosens distingués de la cible annuelle.
32 pages inspectées visuellement pour 27 fiches ; six fiches textuelles seulement.
Réserves de périmètre Klépierre et de sémantique SMCP/Arcure documentées.
Seconde passe technique achevée, 33 décisions indépendantes encore PENDING.
Pas de nouveau fit ni de backtest.

**Dernier état 11-F v4 :** [sources gratuites, comparabilité et seconde revue](../fr/sprint_11f_sources_gratuites_et_seconde_revue.md).
151 PDF extraits sans échec ; 23 paires proposées (13 UP/10 DOWN), 6 cas complexes
et 4 autres classifications. Seconde revue PENDING, pas d'autorisation ML.
Quatre annonces recoupent 26 observations Oracle à 1j/30j ; 4 observations train
exposées par fold externe, aucun D10 train exposé. Aucun fit guidance ; aucun
NO-GO statistique guidance. 61 tests ciblés passent. Gratuit non déclaré épuisé,
payant indispensable non démontré ; Sprint 11 reste ouvert.

**Suite11-E :** [complément gratuit guidance et seconde revue](../fr/sprint_11e_completion_gratuite_guidance.md).
126 PDF supplémentaires sans échec,143 avec11-D ;15 annonces proposées
(9 UP/6 DOWN) et deux cas réservés. Trois anciennes cibles retrouvées. Sur
9661 observations Oracle, seules deux annonces recoupent la fenêtre30j,
21 observations et zéro train exposé dans folds directionnels6/7. Aucun fit,
aucun NO-GO statistique guidance. Seconde revue autorisée encore PENDING,
support/vintage bloquants.57 tests ciblés passent. Pas de payant indispensable
démontré ; sources gratuites non déclarées épuisées, Sprint11 reste ouvert.

Suite documentaire **11-D** : [corpus guidance élargi et revue](../fr/sprint_11d_corpus_guidance_elargi.md).
105 nouveaux candidats, 17 PDF de 16 nouveaux émetteurs collectés et revus ;
quatre nouvelles annonces avec paire prospective chiffrée comparable (3 UP/1 DOWN).
Cumul avec la première revue : sept annonces (6 UP/1 DOWN), pas un dataset ML
admis. Anciennes prévisions manquantes, changements de périmètre, confirmations,
résultats passés, cible climatique et republication séparés. **Aucun modèle
AMF/DILA refait** ; pas de gain D1/D10 testé ni revendiqué. Guidance reste ouverte,
petit support, deuxième revue et disponibilité Web historique encore bloquants.

[Disponibilité, guidance et ablation AMF/DILA](../fr/sprint_11c_evenements_guidance_ablation.md) :
deux folds Oracle OOF H5, logistique fixe, délais de publication1/2 jours.
AMF AUC0,4788 ; DILA compteurs0,5143, delta+0,0036 mais spread brut négatif ;
combinaison0,4806 : NO-GO incrémental exploratoire. Pas de preuve PIT stricte
du vintage/Web, ni de backtest économique. Guidance : trois révisions
prospectives toutes UP, support insuffisant ; ce n'est pas un NO-GO statistique
de la guidance. 33 tests ciblés passent à la vérification finale cumulée,
aucun serving/SQL/2026.
## Audit US des régimes MV — 4 octobre 2026

[Résultats complets 2019–2026 T1](us_2019_2026_audit_regimes_combinaison.md) :
intersection ATR20 TOP20 × Oracle H20 TOP20, puis combinaison figée
momentum120 + volatilité60/ATR20, TOP10 du pool. Sept années et T1 2026
terminés : 27 mois négatifs sur 87 ; MV dépasse M et V en rendement moyen
sur seulement 2 années sur 7. D10 2025 32,05 % / D1 20,08 % ; T1 2026 D10
36,13 % / D1 11,19 %, rendement H20 brut +8,68 %, mais février ≈0 %.
Marché/macro/secteurs décrivent des variations, aucun veto prédictif stable
validé. VIX/VXN/VIX3M/MOVE absents au T1 2026, secteurs actuels non PIT,
bêta ancien souvent constant par défaut. Pas de nouveau fit, serving,
backtest économique ni écriture SQL. Suivi automatique clôturé à livraison.

## US — Capture des mouvements H20 ≥50 % — 6 octobre 2026

[Protocole et résultats](us_extreme50_capture.md). Audit descriptif figé,
batch `model-factory-20261003082853-e98332`, univers tradable courant,
2020–septembre 2026. Seuils absolus 50/100 %, Oracle/ATR/intersection et
10/20/50 premiers titres. Comparaison de précision et capture, hausses/baisses
séparées, fenêtres chevauchantes regroupées, contrôles des prix d'extrémité
et chemins des plus grands cas. Aucun fit, modèle, exits, batch planifié
ou SQL modifié. Run `artifacts/research/us_extreme50_capture/audit-20261006-v1`
terminé. 14 316 fenêtres ≥50 %, 2 366 groupes titre/signe après regroupement
des chevauchements ; 2020 représente 59,5 % des fenêtres. Oracle TOP20 :
précision 1,629 % / capture 67,71 % ; intersection 1,875 % / 60,55 % ;
10 premiers scores Oracle 6,557 % / 7,68 %. En 2025/2026, précision de
ces dix premiers 3,88 % / 4,52 % ; captures 10,08 % / 5,54 %.
2026 évaluable jusqu'au 2 septembre, pas septembre entier. INDV +603 % en 2022 comporte un saut
et des volumes nuls : qualité native du label insuffisante pour certifier
un gain réalisable. 58 tests ciblés passent. Pas de signal directionnel,
profit net ou nouveau modèle démontré ; prix/identités à qualifier avant
un éventuel test économique séparé. Ce n'est pas un NO-GO statistique d'une
nouvelle cible ≥50 %, qui n'a pas été entraînée.

### US — Qualification des prix suspects des sélections concentrées (6 octobre 2026)

[Dossier de qualification et sources primaires](us_extreme50_price_qualification.md).
100 chemins / 19 titres relus ; six réponses EODHD archivées pour INDV,
KNTK et REPX. INDV octobre 2022 : +534,50 % local contre +26,90 % ajusté
fournisseur, composante mécanique de split confirmée ; novembre reste
réservé (rupture reproduite par le fournisseur, volumes nuls, identité ADR
à résoudre). GRND traverse une combinaison d'entreprises. KNTK et REPX
conservent leurs rendements après comparaison des échelles de prix. Un
cours CLDX du 10 juin 2020 est corroboré exactement par la SEC (4,80 $).
Sensibilité rétrospective sans remplacement : 886 labels rendus inconnus,
25 occurrences ≥50 % retirées de l'évaluation ; dix premiers Oracle toujours
1 099 occurrences, précision ≈6,57 %. Qualification partielle seulement,
pas de certification de tous les chemins, pas de signal directionnel ni
profit démontré. Run `artifacts/research/us_extreme50_capture/price-qualification-20261006-v2`.
Aucun prix/label/modèle/SQL corrigé ; aucun rejeu économique lancé.

### US — Préparation figée du replay des sélections concentrées (6 octobre 2026)

[Protocole, couverture et réserves](us_concentrated_replay_protocol.md).
Période principale 2025–30 septembre 2026, après fin d'entraînement
au 31 décembre 2024 ; période déjà explorée, pas confirmation indépendante.
156 835 candidats / 818 titres / 437 séances, 408 884 barres archivées.
Oracle TOP10 et TOP10 dans Oracle ET ATR TOP20 sont strictement identiques
(4 370 occurrences / 138 titres). Réserves TOP10 : 17 fenêtres sur un saut
MP du 10 juillet 2025 (annonce officielle corroborée, prix non entièrement
certifiés), huit sur une barre BAND de volume nul le 18 juin 2026 ;
maturité de fin septembre et open après fin d'observation distingués des
anomalies. Aucun candidat remplacé ou supprimé selon son rendement futur.
Script SELECT-only, extraction annuelle reprenable, quatre tests nouveaux.
Run `artifacts/research/us_concentrated_replay/prepare-20261006-v1` terminé.
Pas de PnL calculé, pas de modèle/production/SQL modifié. Reste à qualifier
les réserves et la parité complète du contrat économique avant le replay.

### US — MP/BAND et contrat d'exécution des sélections concentrées (6 octobre 2026)

[Audit détaillé et réserves](us_concentrated_contract_qualification.md).
MP +50,616 % : événement officiel et clôture 45,23 $ corroborés ; ne pas
exclure automatiquement. BAND 18 juin 2026 : EODHD relu fournit volume
1 997 781, contre zéro local, OHLC inchangé ; correction non injectée.
Contrat de recherche explicitement résolu/empreinté ; CLI equity explicite
reprise dans l'adaptateur. Parité complète encore bloquée : defaults H20 /
trailing / time-stop distincts du protocole historique ; convention demi-spread
partagé contre spread complet du simulateur et pénalité d'entrée supplémentaire.
Tapes bout-en-bout et borrow SHORT restent à qualifier. Aucun PnL, changement
de modèle, moteur de production ou SQL. Rapport retenu :
`artifacts/research/us_concentrated_replay/qualification-contract-20261006-v2/report.json`.

**Suite après GO — contrat technique corrigé** : fallback full-spread égal
à deux fois le demi-spread partagé ; frais monétaires aux deux jambes, sans
pénalité canonique d'entrée de 5 bps ; coût RT forcé non doublé ; borrow en
séances. Contrat historique explicite sans modifier les défauts live, gardes
effectives contre sizing/protections de secours. 37 fixtures passent, dont
chaîne réelle PortfolioBuilder → Phase3/4/5/7 → BacktestEngine en LONG/SHORT
pour TP, stop initial et trailing. Overlay BAND d'une ligne archivé, pas SQL.
329 tests ciblés élargis passent sur la version finale ; avertissements pandas
et dépréciations de `--fees` non bloquants.
Attestation retenue : `artifacts/research/us_concentrated_replay/contract-validation-20261006-v3`.
Ce n'est pas un résultat de stratégie ni une certification de tous les chemins
live : tapes historiques, autres réserves TOP20, liquidation terminale explicite
et borrow SHORT restent à traiter. Aucun PnL historique ni modèle entraîné.

### US — Assemblage des tapes historiques concentrées (6 octobre 2026)

[Méthode, fichiers, suivi et réserves](us_concentrated_historical_tapes.md).
Pilote terminé : 360 candidats/côté, 352 tapes unitaires/côté, huit refus de gap
par côté. 45 tests ciblés passent. Les tapes emploient les phases 3/4/5/7 réelles,
avec une unité technique explicitement non approuvée par PortfolioBuilder.
Réserves nouvelles du pilote : 71 gaps au-delà du stop, 75 gaps favorables au TP
(convention conservatrice à revoir, pas forcément une anomalie), neuf transitions
watcher prévues après une sortie. Aucun de ces flags n'entraîne un remplacement
par un candidat rétrospectivement gagnant.
Traitement complet LONG/SHORT lancé sur 437 séances, avec shards quotidiens,
empreintes et reprise, dans `artifacts/research/us_concentrated_replay/tapes-history-20261006-v1`.
**Terminé, vérifié le 7 octobre 2026** : 437 séances, 874 shards, 3 496 fichiers
vérifiés par SHA256 sans écart ; 142 414 tapes unitaires par côté, soit 284 828.
20 144 chemins présentent un open au-delà du stop ; 11 130 une transition watcher
effective prévue après sortie ; 6 036 restent ouverts à la borne finale.
Ce sont des réserves à arbitrer, pas des pertes mesurées ; les drapeaux peuvent
se recouvrir. Les dix premiers Oracle donnent 3 547 tapes/côté, avec 148/188
gaps de stop LONG/SHORT et 481/392 transitions watcher après sortie.
Aucun PnL/entraînement/SQL. Prochaine action : parité des gaps et chronologie
watcher/OCO, puis portefeuille stateful et liquidation terminale. Qualification
des chemins, tradabilité/lineage et borrow restent des gates économiques.

### US — Variantes LONG sans TP, vingt séances après entrée (7 octobre 2026)

[Protocole et suivi](us_concentrated_exit_variants.md). Convention utilisateur :
sortie à la clôture entrée+20 séances, donc J+21 depuis le signal à J.
Quatre variantes figées : témoin actuel sans échéance, référence avec échéance,
sans TP/stop fixe, sans TP/trailing. Entrées unitaires identiques, aucun sweep.
Résolveur de recherche chronologique : gaps de stop à l'open, TP gappé au prix
limite conservateur, pas de watcher après sortie. Fonctions moteur partagées et
anciens artefacts inchangés ; parité économique encore à valider.
54 tests passent, pilote 352 entrées/variante terminé. Run complet lancé dans
`artifacts/research/us_concentrated_replay/exit-variants-history-20261007-v1`,
437 dates, reprise quotidienne. Aucun PnL, SQL ou modèle modifié. La future
comparaison exige portefeuille stateful, coûts, liquidation et qualification
des chemins/lineage ; une unité technique n'est pas un trade approuvé.

Reprise du 7 octobre après verrou Windows sur `progress.json` : 282 lots
vérifiés intègres (compteur bloqué à 281), aucune règle de variante changée.
Écriture atomique renforcée par temporaire unique et retries bornés ; 56 tests
passent. Lots achevés réutilisés ; journal de reprise `stderr.retry1.log`.

**Clôture du run variantes le 7 octobre** : 437/437 séances, 437 parquets
vérifiés SHA256, 569 656 lignes, quatre variantes pour chacune des 142 414
entrées LONG techniques. Pas d'événement ni activation effective après sortie
sur les trajectoires résolues contrôlées. La proportion atteignant l'échéance
est 4,4 % (référence TP), 59,5 % (sans TP/stop fixe), 29,6 % (sans TP/trailing).
Ce ne sont pas des win rates ni des rendements. Sur les dix premiers Oracle,
3 547 entrées/variante, zéro chemin bloqué par les seuls contrôles locaux.
Le témoin reconstruit change date/prix dans 8 617 cas versus l'ancienne tape :
parité moteur à raccorder avant PnL. Préparation terminée ; aucune supériorité
économique démontrée. Suite : portefeuille stateful, coûts et liquidation,
sans sélectionner après coup uniquement les futurs gagnants ou chemins propres.

**Raccordement portefeuille, 7 octobre 2026** — [Protocole et résultats détaillés](us_concentrated_portfolio_replay.md).
Adaptateur de recherche avec PositionSizer natif, equity/cash continus, huit
positions au plus, coûts aux deux jambes et sorties explicites validées sur gaps.
66 tests ciblés passent. Aucun entraînement, aucune écriture SQL, aucun changement
live. TOP10 = dix titres par jour : quatre variantes perdantes, respectivement
−10,08 %, −9,42 %, −11,81 %, −6,17 % ; pas de promotion de la meilleure variante
après observation. Réserves secteurs non PIT (bucket commun 50 %), contexte macro
non rejoué et absence de parité complète PortfolioBuilder/live. TOP20 % terminé :
−10,57 %, −10,85 %, −11,85 %, −8,21 %. Les premiers essais s'arrêtaient trop tôt
sur LBRDK, avant le sizing ; le contrôle final intervient après approbation d'une
quantité positive. LBRDK est non finançable le 7 juillet selon les règles PIT,
indépendamment de son volume nul/prix répété à partir du 20 juillet. Aucun
remplacement sur information future. Suite : qualifier les réserves historiques
avant résultat certifié ; aucune variante profitable à promouvoir ici.

**Raccordement au builder commun et ledger natif, 7 octobre 2026 — EN COURS.**
[Audit, hypothèses acceptées et reste à faire](us_concentrated_live_parity_audit.md).
Contrat confirmé : Oracle pur LONG-only, secteurs actuels explicitement acceptés
comme hypothèse non-PIT. Précontrôle : 156 835 couples date/symbole couverts en
secteurs, 437 séances couvertes en dates macro (pas une preuve de vintage).
Session de risque persistante + ledger natif incrémental : sizing commun,
fills J+1, frais aux deux jambes, règlements T+1, intérêts, watcher/lifecycle
masqués aux dates observées et gaps de sortie prioritaires. **209 tests ciblés
passent**, dont 13 fixtures du ledger ; aucune performance historique nouvelle.
L'orchestrateur macro/breaker/transitions, les ordres protecteurs et la qualité
des chemins détenus restent à qualifier avant certification et lancement
historique. Aucun modèle, batch en cours ou contenu SQL modifié.
# Mise à jour — raccordement portefeuille concentré, 7 octobre 2026

**Relance v2** : TOP20 v1 bloqué sur GPRE/2026-06-18, volume local nul.
Nouvelle réponse EODHD : volume 3 495 268, OHLC identiques. Overlay de recherche
versionné, non-PIT, sans écriture SQL ; contrôle maintenu. TOP10/TOP20 relancés
dans `live-portfolio-oracle_top10-20261007-v2` et
`live-portfolio-oracle_top20-20261007-v2`, avec les quatre sorties chacun.
Voir la section « Arrêt GPRE et relance versionnée » de l'audit lié ci-dessous.

Orchestrateur chronologique raccordé au builder commun, phases 3/4/5/7 et
comptabilité native : [audit détaillé](us_concentrated_live_parity_audit.md#raccordement-historique-et-lancement--7-octobre-2026).
235 tests ciblés passent ; quatre variantes validées sur un smoke de trente
séances. Backtests TOP10 (dix titres) et TOP20 % lancés sur 2025–septembre 2026,
quatre sorties par sélection, dans `artifacts/research/us_concentrated_replay/live-portfolio-oracle_top10-20261007-v1`
et `live-portfolio-oracle_top20-20261007-v1`. **EN COURS**, aucun verdict économique
à ce stade. Secteurs actuels non-PIT acceptés, macro archivées non certifiées
par vintage, fills OHLC simulés : ne pas présenter ce run comme des fills live.

## Audit qualité Oracle e98332 — 7 octobre 2026

[Chronologie et reproductibilité](us_oracle_reproducibility_audit.md), puis
[localisation des features extrêmes](us_oracle_feature_outliers_audit.md).
**ANOMALIE LOCALE IDENTIFIÉE, PAS DE RÉENTRAÎNEMENT.** Balayage lecture seule
de 4 967 964 barres / 1 798 titres. KNTK, 13 novembre 2018 : 0,002 → 91 dollars
en base reproduit daily_return=45 499, gap=47 749 et volatilité20≈10 173,89.
Reconstruction split-only EODHD actuelle : 99 → 91 dollars, −8,08 %. AMTB,
18 octobre 2018 : 0,108 → 30 local contre 26,25 → 30 reconstruit, +14,29 %.
Historiques suspects présents dans les deux tables de barres, identifiants
constants insuffisants, pollution des fenêtres longues. Preuves archivées,
neuf tests ciblés passent. Aucune écriture SQL ou modification des modèles/live.
Réparation ciblée, garde-fous features et comparaison après réentraînement
versionné restent à autoriser ; aucune garantie d'amélioration D1/D10.
# Suite de l'audit des prix Oracle — plan ciblé KNTK / AMTB

Le 7 octobre 2026, préparation en lecture seule d'un plan pour 309 dates dans
les deux tables de barres (265 KNTK, 35 AMTB anciennes, 9 AMTB en 2023 à revoir
séparément). Sauvegardes, empreintes et diff OHLCV disponibles ; huit tests
ciblés passent. Aucune réparation SQL ni aucun entraînement lancé.

La sensibilité hors base supprime les maxima aberrants KNTK, mais la relecture
EODHD conserve un rendement AMTB de +518 % le 4 septembre 2018. Ce mouvement
n'est pas certifié ; pas de réimportation aveugle ni de filtre automatique des
fortes variations. Suite : validation distincte des dossiers avant correction.
Voir [l'audit détaillé](us_oracle_feature_outliers_audit.md), section « Suite :
plan de réparation et sensibilité hors base » et les artefacts `repair-plan-v2`.

Qualification supplémentaire : 108 clôtures KNTK de 2017 compatibles avec les
fourchettes de bid du 10-K officiel ; deux splits confirmés par l'émetteur.
Les neuf dates AMTB figées avec volume nul en 2023 commencent au transfert
officiel Nasdaq→NYSE. La prise d'effet en séance du split AMTB est confirmée
au 24 octobre 2018 par Nasdaq, mais le +518 % reste non certifié. Périmètre
de correction proposé séparément : 265 dates KNTK + 9 AMTB 2023 ; AMTB 2018
reste en revue. Treize tests ciblés passent ; toujours aucune écriture SQL.

## 2026-10-08 — Filtre prospectif Oracle → GPT + Web (non évalué)

Implémentation optionnelle : TOP N Oracle par score prédit → recherche Web pour
chaque titre → 0 à K LONG documentés → risque canonique → compte principal PAPER.
N/K sont configurables, 10/5 par défaut. Toutes les réponses et les rejets sont
archivés ; évaluations H5/H10/H20 séparées, aucune fausse probabilité ni Kelly.
Statut : infrastructure et tests, **pas de résultat directionnel/économique**.
Accès au modèle confirmé par HTTP 200 le 8 octobre après un premier contrôle
`401 invalid_api_key` : blocage levé. Aucune analyse payante ni ordre lancé ;
le premier cycle Responses/Web reste à valider. Le batch planifié 1–9 est inchangé.
Voir [le fonctionnement complet](oracle_llm_directional_filter.md).

## 2026-10-10 — Consensus EODHD / macro producteurs publics / short volume

[Qualification, preuves, exploitation et limites PIT](consensus_eodhd_macro_publics_20261010.md).
Consensus : compte EODHD HTTP 200, `/calendar/trends` AAPL.US HTTP 403 ; aucun
achat, aucun payload de consensus archivé, produit/droits à confirmer.
Macro : première tranche BLS/H15, 4+5 séries, **107 versions persistées** ;
seconde exécution **0 nouvelle version / 107 inchangées**. Nouvelle table US,
SQL/Alembic 0096, batch public actif installé à 23:15 Paris lun–ven, TLS vérifié,
timestamps réels et révisions append-only. Pas de reconstitution historique PIT,
pas de raccordement automatique aux modèles ; VIX/VXN/VIX3M/MOVE inchangés.
BEA/G17/Census et indices privés restent hors première tranche.
Short volume laissé désactivé : droits non levés, aucun bénéfice directionnel
stable démontré justifiant une dépense. **Pas une nouvelle expérience D1/D10**,
pas d'entraînement ni de trading lancé.

## 2026-10-10 — Pilote historique options Alpaca : volume call/put

[Protocole, accès et limites](alpaca_options_historical_volume_pilot.md).
Accès du compte principal confirmé : catalogue expiré AAPL et 12 barres de
janvier 2025 reçus en HTTP 200. Le paramètre `feed=opra` est refusé par
l'endpoint bars ; provenance laissée `UNVERIFIED_OPRA`, pas de NBBO imputé.
Pilote figé sur janvier 2025 et 40 titres liquides sélectionnés avec les volumes
de décembre 2024 dans l'univers tradable actuel ; paires ATM à 20 DTE,
H3/H5/H10/H20, labels D1/D10 du plein univers qualifié. Aucun entraînement,
écriture SQL, ordre, modification de batch ou promotion live. Ce premier test
ne récupère pas de série historique OI/IV/Greeks. Résultats dans
`artifacts/research/alpaca_options_history/20261010-volume-pilot/report.json`.

Résultat terminé : **174 391 barres**, **719 paires titre/jour**, **37 titres**,
20 dates d'entrée, aucune erreur API. AUC H3/H5/H10/H20 :
**0,510 / 0,493 / 0,475 / 0,593**. H20 : 145 observations extrêmes, moitiés
0,566 / 0,625, mais forte superposition des rendements et aucune date avec assez
d'extrêmes pour l'AUC quotidienne (minimum 20). **Accès historique confirmé,
avantage stable non démontré**. Le signal apparié ATM n'est pas une réplication
du volume agrégé de l'audit prospectif ; pas de conclusion économique.

Sondage du début d'historique : **18 janvier 2024** observé pour chacun de
12 contrats CALL/PUT AAPL/MSFT/SPY, échéances février/mars 2024 ; 300 barres
journalières, première barre minute à 14:30 UTC, zéro barre sur la requête
antérieure depuis janvier 2023, réponses HTTP 200. Date plus ancienne que
février 2024 annoncé par la documentation, mais uniquement une frontière
observée sur cet échantillon et ce compte, pas une garantie exhaustive.
Preuves : `artifacts/research/alpaca_options_history/20261010-first-day/report.json`.

### Suite opérationnelle autorisée — backfill options US

[Backfill SQL, périmètre, contrôles et reprise](alpaca_options_history_backfill.md).
Demande distincte : remplir `stock_option_bars_delayed` du 20/01/2024 au
09/10/2026 sur les 1 790 titres du fichier tradable ; première séance le 22/01.
Barres **1Day**, paires ATM aux DTE 5/10/20 (tolérance 5), pas une chaîne complète.
Premier contrôle réel : 54 lignes A/AA insérées et relues ; cinq tests passent.
**Backfill complet lancé, pas déclaré terminé** : 60 860 tranches symbole/mois,
progression/RAW archivés, reprise et insertions courtes sans écraser l'existant.
`available_at` garde la réception réelle ; pas de snapshots/OI/IV/Greeks
rétrospectifs, pas de nouvelle conclusion directionnelle ni d'ordre.

## 2026-10-10 — Vidage demandé des six tables consensus Yahoo US

Collecte désactivée, aucun collecteur actif et dépendances vérifiées. Suppression
transactionnelle des seules six tables du batch `analyst_snapshot_collection`,
schémas conservés : **1 115 261 lignes supprimées**, six contrôles post-commit
à zéro. Sauvegarde ciblée préalable avec DDL, lignes JSONL compressées et hashes :
`backups/db/yahoo_consensus_before_clear/20261010T215706Z/manifest.json`.
Anciens dumps, résultats d'expériences et données options non supprimés. Aucun
autre batch modifié ou blocage levé ; ne pas réinjecter les archives automatiquement.

## 2026-10-11 — Filtre Oracle : choix GPT / DeepSeek

> Contrat historique du 11 octobre ; remplacé pour les nouveaux runs Web
> DeepSeek le 19 octobre par Search/Fetch natifs, sans OpenAI. Archives conservées.

Livraison technique, pas une nouvelle validation directionnelle : paramètre
`llm_directional_filter.provider`, libellés IHM dynamiques, décisions et protections
PAPER inchangées. DeepSeek analyse les preuves Web OpenAI, les deux API sont
nécessaires et facturées ; pas de recherche Web native DeepSeek supposée.
Configuration, requêtes et RAW des deux fournisseurs archivés ; anciens runs GPT
compatibles, aucun fallback automatique. Tests simulés, aucun appel LLM payant,
ordre ou écriture SQL de production pour cette livraison.
**519 tests passent** ; accès réel DeepSeek non testé avec la clé utilisateur.
[Guide et limites](oracle_llm_directional_filter.md#choix-du-fournisseur--mise-à-jour-du-11-octobre-2026).

## 2026-10-11 — Comparaison réelle GPT / DeepSeek, 11 titres

Diagnostic demandé, recherche uniquement, mêmes entrées parent et mêmes preuves
Web GPT réutilisées par DeepSeek ; pas une comparaison indépendante aveugle.
GPT : 11 réponses valides, **1 LONG / 3 SHORT / 7 ABSTAIN**. DeepSeek : neuf
réponses valides, **1 SHORT / 8 ABSTAIN**, deux réponses tronquées (FICO/FMC,
budget 6 000 tokens partagé avec le raisonnement). **Aucun candidat éligible**.
Résultat global PARTIAL_FAILED ; aucun retry, risque ou ordre. Le budget DeepSeek
reste à qualifier avant usage opérationnel, aucun avantage prédictif démontré.
[Protocole, tableau par titre et erreurs](llm_gpt_deepseek_comparison_11.md).

## 2026-10-11 — Options historiques février–mars 2024 × TOP20 Oracle

Audit SELECT seulement des barres déjà téléchargées, sans interrompre le backfill.
Signal figé volume CALL moins PUT en log, paire ATM même strike/échéance proche
de vingt jours. 10 994 observations sans Oracle ; 2 714 dans le TOP20 prédit
H20, déciles réels conservés sur l'univers complet. H20 AUC **0,519 → 0,509** ;
conditionnel février **0,502**, mars **0,535**. Aucun gain directionnel stable
démontré, aucun modèle ou filtre promu. Disponibilité PIT/provenance non certifiées,
lacune options le 2 février, deux mois et rendements chevauchants.
[Méthode, horizons et limites](alpaca_options_feb_mar_2024_directional_audit.md).

## 2026-10-11 — News/sentiment et mouvement du même jour, US 2025–2026

Audit SELECT uniquement de 367 851 observations article/titre, univers tradable
actuel de 1 790 titres. Seuil >0,9, groupes positifs/négatifs/mixtes distincts,
publications séparées avant ouverture, en séance et après clôture. Association
clôture veille→clôture : positif +0,611 % / +0,535 %, négatif −0,547 % / −0,569 %
(2025/2026). Avant ouverture, relation principalement dans le gap ; continuation
après ouverture faible et instable. Aucune vue PIT admissible avec les dernières
dates de mise à jour : **association descriptive, pas GO prédictif/trading**.
Aucune API, écriture SQL, modification de modèle ou batch. Trois tests passés.
[Résultats, protocole et limites](us_news_same_day_sentiment_audit.md).

## 2026-10-11 — P-PATH-0 : D1/D10 du mouvement dominant pendant vingt séances

Audit terminé, lectures SQL seulement, aucun entraînement ni modification de
modèle, label SQL, batch ou ordre. Depuis la clôture ajustée J, retenir la plus
grande excursion absolue parmi les high/low J+1…J20, avec son signe ; égalités
ambiguës exclues. Déciles calculés sur l'univers complet quotidien scoré avant
l'étude du pool Oracle TOP20 % ∩ ATR TOP20 %, pas sur le seul pool sélectionné.

2 743 313 observations, 1 790 titres, 1 555 dates ; 419 168 observations appariées
dans le pool sur 1 533 dates. 174 entrées du profil : 129 features + score Oracle
et 44 alias de rang monotone. Développement 2020–2022, orientations figées avec
labels déjà disponibles, confirmation 2023/2024 partielle/2025/2026 partielle.

Environ **15 % des observations changent de signe**, mais la majorité des D1/D10
reste dans la même queue. **Aucune des dix pistes choisies sur le développement
ne passe la confirmation**. AUC D1/D10 parcours 2025→2026 : score Oracle
0,5321→0,4929 ; ATR20 0,5357→0,4996 ; volatilité60 0,5360→0,4898.
Sensibilités sur les clôtures, grandes plages intraday et horizons non superposés
archivées. Verdict `NO_STABLE_UNIVARIATE_DOMINANT_PATH_SEPARATION` : pas un verdict
sur un nouveau modèle multivarié ou toutes les données de l'application.

2026 non vierge et couverture conditionnelle : 21 dates mai/juin sous 95 %,
labels archivés non qualifiés le 3 septembre ; aucune réparation SQL ici.
News/sentiment, consensus et VIX ne sont pas dans ce profil, donc non testés.
**41 tests ciblés passent**. Un éventuel Oracle entraîné sur l'amplitude du
parcours reste un protocole distinct, non lancé.
[Contrat, résultats et limites](oracle_dominant_path_separability_h20.md).

## 2026-10-11 — Oracle parcours H20 : mode séparé livré

Implémentation du training LightGBM et checkbox Pipeline, **pas un résultat de
performance sur l'univers réel**. Nouvelle cible TOP20 % des amplitudes maximales
HIGH/LOW entre J+1 et J20, disponibilité J21, WF purgé, checkpoints par tranche
et fold. Artefacts `oracle_path`, sans écriture dans les tables Oracle terminal.
L'Oracle actuel reste inchangé ; nouveau mode décoché par défaut et non servable.
Un entraînement minuscule sur données synthétiques valide techniquement les
modèles/OOS et la reprise, sans base externe. La campagne utilisateur reste à lancer.
[Guide d'entraînement IHM](oracle_path_training.md).

## 2026-10-12 — Oracle TP avant SL : mode LONG/SHORT séparé

Implémentation autorisée avec direction, **pas un résultat prédictif ou économique**.
Deux classifieurs LightGBM globaux distincts : TP 20 % avant SL 7 %, entrée J+1 open,
vingt séances, expiration à l'open J21 ; paramètres configurables et archivés.
La chronologie des contacts prime sur le signe terminal et le maximum absolu.
Gaps résolus à l'open, double contact intrabar exclu par sens, SL jamais ressuscité,
disponibilité conservatrice J22, WF purgé et abstention sur scores faibles/égaux.
Les rapports comparent aussi aux baselines directionnelles toujours LONG/SHORT.
Artefacts `oracle_barrier`, sans remplacer Oracle terminal/parcours ni leurs tables.
Case Pipeline décochée par défaut, recherche non servable, aucun ordre ni campagne
utilisateur lancé. Validation technique sur données synthétiques seulement.
[Guide et protocole](oracle_barrier_training.md).
