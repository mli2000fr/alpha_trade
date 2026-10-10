# Sprint 15-C0 — Audit des analystes et prévisions PIT (CN_A)

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Audit du 29 septembre 2026. **Verdict : NO-GO pour entraîner sur un historique PIT 2018–2025 avec les données actuellement disponibles.** Aucun modèle, batch, table ou serving n'a été modifié. Une collecte prospective reste envisageable, sous réserve des droits et de la qualité de la source.

## Objectif et contrat de données

On cherche des révisions d'estimations *connues au moment de la décision* après Oracle Extreme, non la dernière estimation disponible aujourd'hui. Un rapport exploitable doit identifier le titre, le courtier, l'analyste, la métrique et son unité, l'exercice fiscal, la valeur et la version, la date/heure de publication, la date/heure d'ingestion fournisseur, la première observation locale et `available_at`. Le consensus doit pouvoir être reconstruit seulement avec les rapports disponibles à J, sans compléter le passé avec des rapports ultérieurs.

Lorsque l'API fournit seulement un jour de publication, une première collecte ne doit pas utiliser le rapport à l'ouverture de ce jour ; au plus tôt à la séance suivante et jamais avant la première observation locale. Cette règle prudente ne peut pas transformer une archive collectée en 2026 en historique PIT 2018–2025 : corrections et insertions tardives resteraient invisibles.

## Inventaire local

Lecture de la base `alpha_trade_cn` par le routage CN du projet : 21 tables, aucune table d'analystes, consensus ou prévisions. `cn_raw_payloads` compte 21 816 lignes (familles BaoStock : cours quotidiens, facteurs, indices, calendrier, référentiel), et `cn_staging_rows` 8 663 120 lignes, sans observations analystes. Le staging Tushare générique existant ne signifie pas que `report_rc` a été collecté. Aucun historique analyste n'est aujourd'hui joignable aux événements Oracle OOF.

## Sources et limites

| Source | Atout attesté | Blocage pour ce projet |
| --- | --- | --- |
| [Tushare `report_rc`](https://tushare.pro/document/2?doc_id=292) | Prévisions de courtiers historiques depuis 2010, dates de rapport et métriques. | Accès du compte utilisateur depuis la France impossible dans le contexte actuel ; disponibilité PIT et couverture Oracle à prouver. La documentation consultée indique essai 2 000 points/10 appels par jour et accès formel 8 000 points/100 000 appels par jour. Ne pas confondre avec son corpus séparé de rapports de courtiers. |
| [RQData `consensus`](https://www.ricequant.com/doc/rqdata/python/alternative-data) | Consensus quotidien, rapports par courtier, exercice fiscal, `create_tm` et `rice_create_tm`. `report_range=0` peut corriger rétroactivement des valeurs ; `3` évite les compléments. Avant le 09/06/2022, `rice_create_tm` reprend `create_tm`. | Aucun accès, échantillon authentifié, prix, licence ni couverture Oracle vérifiés. Candidat à qualifier, pas source acquise. |
| [Eastmoney via AKShare](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_research_report_em.py) | API publique `report/list` : rapports datés, courtier, `infoCode`, EPS/PE ; accès en lecture seule vérifié. | Pas de vintage ni timestamp d'ingestion historique, couverture hétérogène ; licence de collecte automatisée et stabilité à confirmer. |
| BaoStock actuel | Cours, facteurs, référentiel et calendrier. | Pas de prévisions de courtiers dans le flux ingéré. |

**Attention fiscale :** le client AKShare nomme certaines colonnes EPS « année courante » à partir de l'année renvoyée par l'API au moment de l'appel, même pour un rapport ancien. Ni l'année 2026 ni celle du `publishDate` ne doivent être affectées automatiquement à une prévision. Vérifier les champs bruts et le rapport source/PDF avant toute construction ancienne/nouvelle prévision.

## Smoke Eastmoney du 29/09/2026

Appels de lecture seule à `https://reportapi.eastmoney.com/report/list` avec `code`, `beginTime=2018-01-01`, `endTime=2025-12-31`, `pageNo` et filtres neutres. Ces chiffres décrivent **l'archive vue en 2026**, pas ce qui était disponible alors.

Trois titres connus montrent la profondeur potentielle mais sont biaisés vers les suivis populaires : `000001` compte 21/31/14/7 rapports en 2018/2021/2024/2025 ; `600519` 46/75/99/79 ; `300750` 34/50/66/44.

Échantillon diagnostique plus pertinent : 16 codes tirés avec graine `20260929` parmi les paires Oracle/labels éligibles 2024H1–2025H2 du jeu 15-B5 : `300054,002451,300027,000603,002045,300025,301372,003040,300332,002399,002073,300657,300766,000547,002234,301009`. Quatre radiés du référentiel 15-B4 ont été ajoutés : `300742,002619,000861,300309`. Ce petit échantillon ne représente ni tout l'univers CN, ni la couverture exacte par date de signal.

| Couverture parmi les 16 codes Oracle | Titres |
| --- | ---: |
| Au moins un rapport 2018–2025 | 14/16 |
| Au moins un rapport daté de 2024 | 5/16 |
| Au moins un rapport daté de 2025 | 5/16 |
| Aucun rapport | 2/16 |

En 2024 : `300054,000603,002045,002399,300657` ; en 2025 : `300054,000603,002045,300657,301009`. Un rapport dans l'année ne suffit pas pour obtenir deux prévisions comparables du même courtier ni un consensus récent multibroker à chaque événement. Deux des quatre radiés ont des rapports retrouvés (`300742`, `300309`), deux non (`002619`, `000861`) ; aucune conclusion de biais de survivance ne peut être tirée sur quatre cas.

La pagination est piégeuse : `pageSize=5000` demandé pour `300054`, mais 100 lignes sur la page 1 et `TotalPage=2`. La page 2 ajoute 12 lignes jusqu'au 20/08/2018 : **112 rapports**, pas 100. Il faut suivre `TotalPage`, sans supposer que la taille demandée est honorée. `publishDate` apparaît à minuit ; ce n'est pas une preuve de diffusion à cette heure. La réponse ne contient pas de journal de corrections ou de premières observations historiques.

## Conditions de reprise

1. Droit et quota de collecte validés, accès depuis la France ; si RQData, obtenir un échantillon exportable 2024–2025 incluant publications, ingestions et modes de correction.
2. Identité PIT `instrument_id` avec renommages et radiations ; rapports dédupliqués par identifiant **et version**, sans écrasement de l'historique observé.
3. Vérification manuelle de l'exercice fiscal, des unités, du type de rapport et des rapports PDF avant calcul ancien/nouveau EPS ou dispersion.
4. Couverture calculée sur **tout** le TOP20 Oracle OOF, par séance, semestre, board, taille et radiations : au moins un rapport, deux rapports comparables, deux courtiers, ancien/nouveau, âge de publication. Comparer titres couverts et non couverts.
5. Preuve de disponibilité PIT : publication ≠ ingestion fournisseur ≠ première observation locale ≠ disponibilité pour décision. Une version corrigée aujourd'hui ne doit pas contaminer une date passée.
6. Seulement après ces gates, pré-enregistrer une ablation prix seul vs analystes sur les mêmes lignes, folds purgés et coûts, sans sélectionner l'échantillon d'après les résultats futurs.

Si Eastmoney reste la seule source accessible, un pilote **prospectif versionné** peut démarrer après accord de licence, mais ne débloque pas l'expérience historique 15-C1. État : `SPRINT_15C0_AUDIT_COMPLETE`, `HISTORICAL_PIT_NO_GO`, `PROSPECTIVE_PILOT_CONDITIONAL`, `ML_NOT_STARTED`, `SERVING_UNCHANGED`.
