# Sprint 15-D2 — Audit Dragon/Tiger historique SSE/SZSE

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Audit réalisé le 29 septembre 2026. **Verdict : source et identité des événements validées sur quatre séances échantillons ; contrat PIT historique et intérêt directionnel non démontrés.** Aucun entraînement, table, batch quotidien, backtest ou serving n'a été modifié.

## 1. Question et protocole verrouillé

La « Dragon/Tiger List » (`龙虎榜`) publie après une séance les titres dont le mouvement, la volatilité, le turnover ou d'autres critères réglementaires ont déclenché une divulgation, avec certains sièges de courtage acheteurs/vendeurs. Ce n'est ni un flux quotidien dense de capitaux, ni l'identité certaine d'un investisseur institutionnel. Un titre n'apparaît pas aléatoirement : **la sélection dépend déjà du mouvement réalisé du jour J**. Pour un signal à l'ouverture de J, la liste de J serait une fuite.

Quatre séances ont été fixées avant le rapprochement : 31/01/2024, 31/07/2024, 31/07/2025, 31/12/2025. Pour chacune, le pilote lit :

1. [SSE — tableau quotidien du marché principal](https://www.sse.com.cn/disclosure/diclosure/public/dailydata/) par son interface officielle `queryAllTradeOpenDate.do` (`flag=1`) ;
2. [SSE — tableau STAR](https://www.sse.com.cn/disclosure/diclosure/public/dailydatatib/) par `queryKCBTradeInfo.do` (`flag=1`) ;
3. [SZSE — informations de négociation publiques](https://www.szse.cn/disclosure/deal/public/index.html) par `ShowReport/data`, catalogue `1842_xxpl_after`, avec **toutes** les pages ;
4. l'archive Eastmoney `RPT_DAILYBILLBOARD_DETAILSNEW` comme comparateur, jamais comme vérité PIT.

Les vérifications comparent uniquement le couple **marché + code** sur une même date. Le pilote conserve aussi les événements officiels individuels et leur motif (`refType` SSE, texte `plyy` SZSE), mais **ne prétend pas avoir réconcilié motif par motif**. Le filtre actions A de ce pilote est `SH 60/68` ou `SZ 00/30`; les obligations convertibles, B shares, REITs et titres Beijing sont exclus. Avant une éventuelle production, il faudra remplacer ce filtre par le `instrument_id` et le security master **point-in-time**.

## 2. Résultats de la réconciliation

| Séance | Lignes officielles actions A | Couples marché–titre officiels | Couples Eastmoney actions A | Correspondances |
| --- | ---: | ---: | ---: | ---: |
| 31/01/2024 | 71 | 59 | 59 | 59/59 |
| 31/07/2024 | 58 | 49 | 49 | 49/49 |
| 31/07/2025 | 72 | 61 | 61 | 61/61 |
| 31/12/2025 | 66 | 59 | 59 | 59/59 |
| **Total** | **267** | **228** | **228** | **228/228** |

La première lecture incomplète du seul tableau SSE principal créait artificiellement des « manquants » STAR ; elle a été remplacée par la lecture **principal + STAR**. D'autres écarts venaient de l'inclusion de B shares, obligations convertibles et d'un REIT. Après correction du périmètre, aucun couple marché–titre ne diffère sur ces quatre dates. Ce résultat est **un contrôle d'identité sur un petit échantillon**, pas une preuve d'exhaustivité 2018–2025, de montants exacts ou de capacité prédictive. Les 267 lignes dépassent les 228 couples parce qu'un même titre peut figurer pour plusieurs motifs.

La pagination SZSE est contrôlée contre le nombre annoncé ; le 31/01/2024, par exemple, 36 lignes brutes réparties sur quatre pages. Les comptes bruts Eastmoney sont également contrôlés avant exclusion des instruments non-actions. La réponse SSE distingue les deux tableaux ; l'absence de STAR dans le premier n'est pas une absence d'événement.

## 3. Contrat temporel : blocage PIT

Les réponses officielles consultées portent une **date de transaction** (`tradeDate` SSE, `dqrq` SZSE), mais le pilote n'a pas établi une **heure historique de publication effective** ni une archive des corrections telle qu'observée au moment de chaque backtest. La date de transaction à minuit renvoyée par Eastmoney n'est pas une heure de diffusion. Il serait donc incorrect de considérer ces données comme connues à l'ouverture de J.

Règle de recherche prudente si l'on poursuit : événement de J utilisable **au plus tôt à J+1**, avec variante J+2 de sensibilité ; si une décision est prise avant l'ouverture, exiger une preuve que la publication était déjà disponible. Ce décalage reste un **proxy**, pas une certification PIT. En live, il faudra enregistrer `observed_at`, `available_at`, source, hash et version dès la collecte prospective.

Autre piège : `abnormalStart`/`unnormalStartDate` d'un motif pluri-journalier peut précéder la séance de publication. **Ne jamais dater la feature à ce début de fenêtre** : l'information n'existe publiquement qu'après l'événement divulgué.

## 4. Champs autorisés et interdits

L'archive Eastmoney retourne explicitement `D1_CLOSE_ADJCHRATE`, `D2_CLOSE_ADJCHRATE`, `D5_CLOSE_ADJCHRATE`, `D10_CLOSE_ADJCHRATE`, `D20_CLOSE_ADJCHRATE` et `D30_CLOSE_ADJCHRATE`. Ces champs contiennent des rendements **postérieurs** et sont interdits comme features. Le champ narratif `EXPLAIN` peut contenir un « taux de réussite » calculé après coup ; `FREE_MARKET_CAP` de l'archive actuelle n'est pas non plus une capitalisation PIT prouvée. Le pilote les repère dans le schéma mais **n'enregistre aucune de leurs valeurs**. Le fichier fournisseur local ne conserve que `TRADE_DATE`, `SECURITY_CODE`, `MARKET`, `EXPLANATION` et `CHANGE_TYPE`, eux-mêmes **non autorisés au ML** à ce stade.

Liste blanche *candidate pour un futur audit*, issue d'une source officielle datée et uniquement après disponibilité prouvée : code/exchange et motif, caractère achat/vente du **siège** si la définition est vérifiée, montants par siège et top 5, montant/volume de la séance. Ce n'est **pas** un feu vert immédiat : unités SSE/SZSE, détails par siège, dédoublonnage des motifs et éligibilité des titres doivent encore être réconciliés. Une ligne « 机构专用 » ou « 沪股通专用 » ne suffit pas à attribuer le flux à un bénéficiaire final.

## 5. Décision et suite

**15-D2 = `GO_SOURCE_IDENTITY_SAMPLE`, `NO_GO_HISTORICAL_PIT_ML`, `NO_SERVING_CHANGE`.** Les quatre séances prouvent qu'une collecte officielle historique ciblée est possible et que l'agrégateur retrouve les mêmes titres actions A sur cet échantillon. Elles ne démontrent ni l'heure de disponibilité, ni la stabilité de toute la période, ni la valeur ajoutée pour séparer D1/D10.

Avant tout modèle : (1) échantillonner et réconcilier davantage de séances sur chaque année/board et les radiations ; (2) rapprocher les motifs et montants siège par siège avec unités officielles ; (3) vérifier les droits et limites de collecte ; (4) enregistrer prospectivement les timestamps de publication/observation ; (5) calculer la couverture sur les **mêmes paires Oracle** avec décalage J+1/J+2 ; (6) pré-enregistrer une ablation OOF conditionnelle aux événements, prix/mouvement de J identiques dans les deux bras, séparée LONG/SHORT et par semestre. Sans ces étapes, une bonne performance pourrait simplement refléter le critère qui a mis le titre sur la liste.

Reproduction : `service/market/cn_dragon_tiger_pilot_15d2.py` produit `artifacts/research/cn_dragon_tiger_15d2/pilot-20260929-v3/report.json`, `official_event_sample.json` et `eastmoney_sanitized_sample.json`. Le rapport conserve les SHA-256 des réponses mais **pas les réponses Eastmoney brutes**. Trois tests ciblés passent dans `tests/test_cn_dragon_tiger_pilot_15d2.py`. Les essais v1/v2 restent séparés pour tracer le diagnostic du périmètre ; **v3 fait foi**.
