# Pilote de référence guidance — 30 septembre 2026

Statut : **REVIEW_READY_PARTIAL_EVIDENCE_NOT_ML_READY**. Propositions d'annotation par l'assistant, non vérité terrain indépendante. Aucun modèle entraîné, aucun rendement utilisé, aucune modification du parseur, de la base ou du serving.

## Résultat utile pour la recherche D1/D10

Le pilote comporte **38 publications de 10 émetteurs**, dans deux fenêtres identiques d'avril à août 2023 et 2024. **13 publications chez 3 émetteurs** contiennent un objectif annuel consolidé en dollars compatible avec la cible primaire. Elles fournissent **5 révisions nominales candidates : 3 baisses et 2 hausses**. Trois sont explicites dans un même communiqué ; deux reposent sur une comparaison de publications observées, sans certification du prédécesseur immédiat.

Ce sont des variations de prévisions d'entreprise, pas des rendements et pas des labels D1/D10. Leur présence établit l'existence d'informations annotables ; elle ne valide ni leur capacité directionnelle ni leur disponibilité avant l'instant de décision de l'Oracle. **Zéro événement est ML-éligible.**

La restriction aux revenus annuels absolus laisse de côté une grande partie de cet échantillon. Ce constat suggère une future représentation par mesure et par unité, avec abstention explicite, plutôt qu'une conversion forcée de toutes les annonces en dollars. Il ne justifie pas encore l'entraînement d'un nouveau classifieur.

## Sélection et limites

Les dix émetteurs fixés avant lecture sont AEO, COLM, NKE, WMT, TGT, LOW, HD, NOW, ADSK et CAT. La sélection est raisonnée dans l'univers local actuel, non aléatoire et non reconstruite historiquement. Les dates retenues sont du 1er avril au 31 août, pour chacune des deux années ; il ne s'agit **pas de deux années complètes d'annonces**. L'exhaustivité des publications intermédiaires hors résultats n'est pas certifiée.

Le protocole est conservé dans `work/guidance_reference_20260930/protocol.json`. Son hash de livraison ne constitue pas une preuve externe horodatée de préenregistrement. Aucun émetteur n'a été remplacé en fonction du contenu trouvé. NKE a une publication dans chaque fenêtre ; AEO n'en a qu'une dans celle de 2023. Autodesk ajoute une publication préliminaire le 31 mai 2024 : la confirmation du 11 juin ne devient pas une seconde révision.

## Collecte et provenance

- **20/38 pages HTML brutes archivées**, avec date de récupération UTC et SHA-256 vérifié ; leur texte est rendu localement avec repères de lignes.
- **18/38 téléchargements bruts en échec** : refus HTTP ou expiration, conservés dans le journal. Des vues web officielles ont permis une lecture complémentaire ; elles ne remplacent pas des snapshots bruts reproductibles.
- **37 propositions de classement**, plus CAT du 6 août 2024 laissé `REVIEW_INCOMPLETE` après lecture partielle de la vue longue. Aucun échec réseau n'est assimilé à une absence de guidance.
- Les dates affichées sur les pages sont des dates de publication déclarées. La récupération en 2026 ne prouve ni le contenu original ni l'heure de disponibilité historique en 2023/2024. Tous les champs PIT restent non validés.

## Révisions candidates

| Société / date | FY | OLD → NEW (M USD) | Variation du milieu | Preuve |
|---|---:|---|---:|---|
| [COLM 2023-08-01](https://investor.columbia.com/news-events/press-releases/detail/348/columbia-sportswear-company-reports-second-quarter-and) | 2023 | [3570, 3670] → [3530, 3590] | -1.6575 % | Explicite, même document |
| [LOW 2023-05-23](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-first-quarter-2023-sales-and-earnings-results-05-23-23) | 2023 | [88000, 90000] → [87000, 89000] | -1.1236 % | Explicite, même document |
| [LOW 2024-08-20](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-second-quarter-2024-sales-and-earnings-results-08-20-24) | 2024 | [84000, 85000] → [82700, 83200] | -1.8343 % | Explicite, même document |
| [ADSK 2023-08-23](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2024-second-quarter-results) | 2024 | [5355, 5455] → [5405, 5455] | +0.4625 % | Publications observées adjacentes |
| [ADSK 2024-08-29](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2025-second-quarter-results) | 2025 | [5990, 6090] → [6080, 6130] | +1.0762 % | Publications observées adjacentes |

Les nombres sont normalisés en **millions de dollars** ; la variation est `(milieu nouveau / milieu ancien - 1) × 100`. Lowe's 2023 conserve le qualificatif approximatif. Les deux hausses Autodesk ne sont que des comparaisons nominales : disponibilité d'une éventuelle annonce intermédiaire, effets de change et comparabilité du modèle de transaction restent à examiner. Elles ne sont pas promues en révisions économiques validées.

Trois comparaisons observées sont inchangées : COLM juillet 2024 contre avril ; LOW août 2023 contre mai ; ADSK juin 2024 contre la publication préliminaire de mai. Les mentions « inchangé/réaffirmé » de COLM avril 2023, COLM avril 2024 et LOW mai 2024 restent des affirmations de l'émetteur dont la source antérieure n'est pas archivée dans ce pilote. Un changement d'exercice n'est jamais une révision du même objectif.

## Cas qui doivent rester distincts

| Classe proposée | Publications | Sens |
|---|---:|---|
| Objectif annuel absolu | 13 | COLM, LOW, ADSK ; montant primaire annotable |
| Croissance seule | 11 | AEO, WMT, HD ; taux, parfois à change constant |
| Ventes comparables | 4 | TGT ; mesure distincte du revenu consolidé, période parfois restante |
| Abonnements seuls | 4 | NOW ; ne pas substituer au revenu total |
| Aucun objectif primaire identifié dans la page lue | 5 | NKE et pages courtes CAT ; ne prouve pas l'absence dans la conférence ou les annexes |
| Revue incomplète | 1 | CAT août 2024 ; classe sémantique non conclue |

Un cas particulièrement utile est HD : la prévision de mai 2024 exclut SRS ; celle d'août l'inclut. Une hausse des ventes totales attendues peut donc coexister avec une dégradation des ventes comparables. Les montants de contribution de SRS ou de la semaine supplémentaire ne sont pas le revenu annuel consolidé. Les communiqués correspondants sont liés dans l'inventaire ci-dessous.

Les proportions 13/38 et 3/10 décrivent uniquement ce pilote. Elles ne mesurent ni le rappel du parseur, ni la couverture de l'univers Oracle, ni la puissance statistique d'une expérience directionnelle. Les cinq candidats proviennent de trois sociétés ; ils ne sont pas cinq observations indépendantes de généralisation.

## Dossier de revue livré

Sous `work/guidance_reference_20260930/` :

- `sources.json`, `collection.json`, `raw/`, `text/` : inventaire, erreurs et provenance locale.
- `annotation_proposals.json`, `review_dataset.json` : propositions pour les 38 publications avec mesure, année fiscale, unité, preuve et motifs d'exclusion.
- `event_candidates.json` : 5 révisions candidates et 3 comparaisons inchangées, dédupliquées au niveau de la publication et de la mesure.
- `independent_review.json` : formulaire vierge, séparé des propositions et préservé par la régénération.
- `summary.json`, `manifest.json` : compteurs, statut des contrôles et empreintes des artefacts.
- `collect_sources.ps1`, `extract_text.py`, `build_review.py`, `report_template.md` : scripts et modèle de rapport. Le générateur assemble des annotations manuelles proposées ; ce n'est pas un nouveau parseur de guidance.

Contrôles exécutés : correspondance des 38 identifiants entre inventaire, collecte et annotations ; dates dans les fenêtres ; dix émetteurs prévus ; empreintes des 20 bruts ; bornes et unités numériques ; cohérence de mesure/exercice pour les comparaisons ; ordre des publications ; unicité des événements ; aucune promotion ML. Ces contrôles d'intégrité **ne valident pas** la lecture sémantique, l'exhaustivité ou le PIT.

## Travail suivant, précisément délimité

1. Un relecteur indépendant complète les 38 décisions, en commençant par les 13 montants primaires et leurs preuves OLD/NEW ; CAT août 2024 reste indéterminé jusque-là. Ne pas approuver automatiquement les propositions de l'assistant.
2. Pour les événements conservés, archiver une source historique officielle, établir l'heure disponible, la période et le périmètre, puis chercher les annonces intermédiaires avant d'accepter une paire entre publications. Documenter aussi les exclusions ; ne pas sélectionner les cas selon les rendements.
3. Évaluer ensuite l'extraction sur des documents complets indépendants. Les objectifs de l'audit précédent restent des gates non franchis : précision au moins 95 %, rappel NEW correct de bout en bout au moins 80 %, aucun faux intervalle accepté, validation des paires et du PIT. Ce pilote déjà lu ne peut pas servir de confirmation indépendante après réglage du parseur.
4. Seulement après ces validations, mesurer l'information directionnelle sur les événements sélectionnés par l'Oracle, avec disponibilité antérieure à la décision et validation temporelle. Une annonce postérieure à l'instant Oracle ne peut pas devenir une feature à cet instant ; elle impose un autre instant de décision et une autre cible. Garder un canal distinct pour les prévisions en pourcentage, abonnements et ventes comparables si une extension est ensuite préenregistrée.

La revue humaine et la preuve historique sont les dépendances restantes. Ce pilote prépare leur travail ; il ne les simule pas et n'affirme pas avoir résolu D1/D10.

## Inventaire sourcé des propositions

Repères `text` : fichiers locaux `text/<identifiant>.txt`. Repères `web` : vue textuelle observée le 30 septembre 2026, susceptible de changer et non archivée intégralement. Toutes les lignes restent en attente d'adjudication indépendante.

| Publication officielle | Proposition | Valeur nouvelle (M USD) | Trace | Note de revue |
|---|---|---|---|---|
| [ADSK_20230525](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2024-first-quarter-results) | PRIMARY_INTERVAL | [5355, 5455] | Vue web, brut absent ; Full Year Fiscal 2024, web L200-209 | Exercice clos le 31 janvier 2024. Ligne Revenue, ne pas confondre avec Billings. |
| [ADSK_20230823](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2024-second-quarter-results) | PRIMARY_INTERVAL | [5405, 5455] | Vue web, brut absent ; Full Year Fiscal 2024, web L193-208 | Hausse nominale par rapport à mai ; prédécesseur immédiat non certifié, hypothèses FX à vérifier. |
| [ADSK_20240531](https://investors.autodesk.com/news-releases/news-release-details/autodesk-reports-results-audit-committee-investigation-provides) | PRIMARY_INTERVAL | [5990, 6090] | Vue web, brut absent ; Full Year Fiscal 2025, web L89-101 | Publication préliminaire ; exercice clos le 31 janvier 2025. Première observation dans la fenêtre, pas nécessairement première annonce historique. |
| [ADSK_20240611](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2025-first-quarter-results) | PRIMARY_INTERVAL | [5990, 6090] | Vue web, brut absent ; Full Year Fiscal 2025, web L198-219 | Même fourchette que le 31 mai. Confirmation numérique ; ne pas compter une nouvelle révision. |
| [ADSK_20240829](https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2025-second-quarter-results) | PRIMARY_INTERVAL | [6080, 6130] | Vue web, brut absent ; Full Year Fiscal 2025, web L198-212 | Hausse nominale par rapport à juin ; effet du nouveau modèle de transaction et comparabilité économique à vérifier. |
| [AEO_20230524](https://investors.ae.com/press-releases/news-details/2023/AEO-Inc.-Reports-First-Quarter-Results-In-Line-with-Plan/default.aspx) | GROWTH_ONLY | — | Vue web, brut absent ; Outlook, web L47-49 | Revenu annuel : stable à légère baisse ; 250–270 M$ concerne le résultat opérationnel. |
| [AEO_20240529](https://investors.ae.com/press-releases/news-details/2024/AEO-Inc.-Reports-First-Quarter-Fiscal-2024-Results-Reflecting-Strong-Execution-on-Powering-Profitable-Growth-Strategy/default.aspx) | GROWTH_ONLY | — | Vue web, brut absent ; Outlook, web L52-55 | Revenu annuel +2 à +4 %, avec une semaine de ventes en moins ; montant en dollars = résultat opérationnel. |
| [AEO_20240829](https://investors.ae.com/press-releases/news-details/2024/AEO-Inc.-Reports-Record-Second-Quarter-Revenue-and-Meaningful-Operating-Margin-Expansion-Updates-Full-Year-Operating-Income-Outlook-to-the-High-End-of-Prior-Guidance/default.aspx) | GROWTH_ONLY | — | Vue web, brut absent ; Outlook, web L49-52 | Revenu annuel +2 à +3 %. Hausse du résultat opérationnel distincte du revenu. |
| [CAT_20230427](https://investors.caterpillar.com/news/news-details/2023/Caterpillar-Reports-First-Quarter-2023-Results/default.aspx) | NO_PRIMARY_IDENTIFIED_IN_RELEASE | — | Vue web, brut absent ; web L77-93 | Page de résultats : revenus trimestriels réalisés ; aucun objectif annuel absolu identifié. Annexes/conférence non examinées. |
| [CAT_20230801](https://investors.caterpillar.com/news/news-details/2023/Caterpillar-Reports-Second-Quarter-2023-Results/default.aspx) | NO_PRIMARY_IDENTIFIED_IN_RELEASE | — | Vue web, brut absent ; web L77-93 | Page de résultats : revenus trimestriels réalisés ; aucun objectif annuel absolu identifié. Annexes/conférence non examinées. |
| [CAT_20240425](https://investors.caterpillar.com/news/news-details/2024/Caterpillar-Reports-First-Quarter-2024-Results/default.aspx) | NO_PRIMARY_IDENTIFIED_IN_RELEASE | — | Vue web, brut absent ; web L77-90 | Page courte de résultats trimestriels ; aucun objectif annuel absolu identifié. Annexes/conférence non examinées. |
| [CAT_20240806](https://investors.caterpillar.com/news/news-details/2024/Caterpillar-Reports-Second-Quarter-2024-Results/default.aspx) | REVIEW_INCOMPLETE | — | Vue web, brut absent ; web page 4218 lines; keyword outlook L1934 | Téléchargement brut refusé ; vue web longue examinée partiellement. Absence de guidance non établie. |
| [COLM_20230427](https://investor.columbia.com/news-events/press-releases/detail/344/columbia-sportswear-company-reports-first-quarter-2023) | PRIMARY_INTERVAL | [3570, 3670] | Brut archivé ; text L62-64 | Montant déclaré inchangé ; prévision antérieure non archivée dans cette fenêtre. |
| [COLM_20230801](https://investor.columbia.com/news-events/press-releases/detail/348/columbia-sportswear-company-reports-second-quarter-and) | PRIMARY_INTERVAL | [3530, 3590] | Brut archivé ; text L73-75 | Ancien et nouveau figurent dans le même communiqué ; 3,46 Md$ correspond au réalisé 2022. |
| [COLM_20240425](https://investor.columbia.com/sec-filings/all-sec-filings/content/0001050797-24-000064/colmfy24q1exhibit991.htm) | PRIMARY_INTERVAL | [3350, 3420] | Brut archivé ; text L53-63 | Montant déclaré inchangé ; hypothèse de change modifiée. Ne pas utiliser le réalisé 2023 comme OLD. |
| [COLM_20240725](https://investor.columbia.com/news-events/press-releases/detail/364/columbia-sportswear-company-reports-second-quarter-2024) | PRIMARY_INTERVAL | [3350, 3420] | Brut archivé ; text L73-75 | Montant déclaré inchangé, également identique au communiqué d'avril. |
| [HD_20230516](https://ir.homedepot.com/news-releases/2023/05-16-2023-110108461) | GROWTH_ONLY | — | Brut archivé ; text L94-96 | Ventes totales et comparables prévues en baisse de 2 à 5 %, pas de total annuel dollar. |
| [HD_20230815](https://ir.homedepot.com/news-releases/2023/08-15-2023-110106515) | GROWTH_ONLY | — | Brut archivé ; text L92-94 | Confirmation de baisse de 2 à 5 % ; les intérêts en dollars ne sont pas les ventes. |
| [HD_20240514](https://ir.homedepot.com/news-releases/2024/05-14-2024-110058012) | GROWTH_ONLY | — | Brut archivé ; text L92-95 | Ventes totales +1 % incluant la 53e semaine ; SRS exclu. 2,3 Md$ = contribution semaine supplémentaire. |
| [HD_20240813](https://ir.homedepot.com/news-releases/2024/08-13-2024-110126639) | GROWTH_ONLY | — | Brut archivé ; text L95-100 | Ventes totales +2,5 à +3,5 %, SRS désormais inclus ; comparable -3 à -4 %. Rupture de périmètre, 6,4 Md$ = contribution SRS. |
| [LOW_20230523](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-first-quarter-2023-sales-and-earnings-results-05-23-23) | PRIMARY_INTERVAL | [87000, 89000] | Brut archivé ; text L35-38 | Fourchette approximative ; ancien/nouveau explicites pour FY2023. Calendrier 52 semaines, distinct du réalisé FY2022 à 53 semaines. |
| [LOW_20230822](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-second-quarter-2023-sales-and-earnings-results-08-22-23) | PRIMARY_INTERVAL | [87000, 89000] | Brut archivé ; text L29-32 | Fourchette approximative confirmée, identique à mai. |
| [LOW_20240521](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-first-quarter-2024-sales-and-earnings-results-05-21-24) | PRIMARY_INTERVAL | [84000, 85000] | Brut archivé ; text L30-34 | Prévision annuelle réaffirmée ; ancienne source hors fenêtre non archivée. |
| [LOW_20240820](https://corporate.lowes.com/newsroom/press-releases/lowes-reports-second-quarter-2024-sales-and-earnings-results-08-20-24) | PRIMARY_INTERVAL | [82700, 83200] | Brut archivé ; text L27-30 | Ancien/nouveau explicitement fournis pour FY2024. |
| [NKE_20230629](https://investors.nike.com/investors/news-events-and-reports/investor-news/investor-news-details/2023/NIKE-Inc.-Reports-Fiscal-2023-Fourth-Quarter-and-Full-Year-Results/default.aspx) | NO_PRIMARY_IDENTIFIED_IN_RELEASE | — | Vue web, brut absent ; web L38-88 | Montants annuels réalisés FY2023. Pas de prévision annuelle absolue identifiée dans le communiqué ; conférence non examinée. |
| [NKE_20240627](https://investors.nike.com/investors/news-events-and-reports/investor-news/investor-news-details/2024/NIKE-Inc.-Reports-Fiscal-2024-Fourth-Quarter-and-Full-Year-Results/default.aspx) | NO_PRIMARY_IDENTIFIED_IN_RELEASE | — | Vue web, brut absent ; web L38-88 | FY2025 outlook évoqué sans objectif annuel de revenu en dollars identifié ; réalisé FY2024 exclu. Conférence non examinée. |
| [NOW_20230426](https://newsroom.servicenow.com/press-releases/details/2023/ServiceNow-Reports-First-Quarter-2023-Financial-Results-04-26-2023-traffic/default.aspx) | SUBSCRIPTION_ONLY | — | Vue web, brut absent ; web L110-130 | Guidance d'abonnements 8 470–8 520 M$, pas revenu consolidé total. |
| [NOW_20230726](https://newsroom.servicenow.com/press-releases/details/2023/ServiceNow-Reports-Second-Quarter-2023-Financial-Results-07-26-2023-traffic/default.aspx) | SUBSCRIPTION_ONLY | — | Vue web, brut absent ; web L113-133 | Guidance d'abonnements 8 580–8 600 M$, pas revenu consolidé total. |
| [NOW_20240424](https://newsroom.servicenow.com/press-releases/details/2024/ServiceNow-Reports-First-Quarter-2024-Financial-Results-04-24-2024-traffic/default.aspx) | SUBSCRIPTION_ONLY | — | Vue web, brut absent ; web L115-134 | Guidance d'abonnements 10 560–10 575 M$, pas revenu consolidé total. |
| [NOW_20240724](https://newsroom.servicenow.com/press-releases/details/2024/ServiceNow-Reports-Second-Quarter-2024-Financial-Results-07-24-2024-traffic/default.aspx) | SUBSCRIPTION_ONLY | — | Vue web, brut absent ; web L142-161 | Guidance d'abonnements 10 575–10 585 M$ ; hypothèses FX actualisées, hors cible primaire. |
| [TGT_20230517](https://corporate.target.com/press/release/2023/05/target-corporation-reports-first-quarter-earnings) | COMPARABLE_SALES_ONLY | — | Brut archivé ; text L33-35 | Ventes comparables en faible baisse à faible hausse ; EPS et croissance du résultat opérationnel exclus. |
| [TGT_20230816](https://corporate.target.com/press/release/2023/08/target-corporation-reports-second-quarter-earnings) | COMPARABLE_SALES_ONLY | — | Brut archivé ; text L32-34 | Baisse comparable autour de mid-single digits pour le RESTE de l'année, pas un montant annuel consolidé. |
| [TGT_20240522](https://corporate.target.com/press/release/2024/05/target-corporation-reports-first-quarter-earnings) | COMPARABLE_SALES_ONLY | — | Brut archivé ; text L33-35 | Ventes comparables annuelles +0 à +2 % ; pas le revenu total en dollars. |
| [TGT_20240821](https://corporate.target.com/press/release/2024/08/target-corporation-reports-second-quarter-earnings) | COMPARABLE_SALES_ONLY | — | Brut archivé ; text L30-32 | Préférence pour la moitié basse de +0 à +2 % comparable ; amélioration EPS distincte. |
| [WMT_20230518](https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-23-000043/earningsreleasefy24q1.htm) | GROWTH_ONLY | — | Brut archivé ; text L640-641 | Croissance annuelle des ventes nettes à change constant : environ +3,5 % ; ne pas convertir en dollars. |
| [WMT_20230817](https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-23-000088/earningsreleasefy24q2.htm) | GROWTH_ONLY | — | Brut archivé ; text L645-659 | Croissance annuelle des ventes nettes à change constant : environ +4 à +4,5 %. |
| [WMT_20240516](https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-24-000088/earningsreleasefy25q1.htm) | GROWTH_ONLY | — | Brut archivé ; text L65; L767-769 | Haut de fourchette ou légèrement au-dessus de +3 à +4 %, à change constant ; pas un intervalle dollar. |
| [WMT_20240815](https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-24-000131/earningsreleasefy25q2.htm) | GROWTH_ONLY | — | Brut archivé ; text L774-776 | +3,75 à +4,75 % à change constant ; ancienne fourchette +3 à +4 %. |
