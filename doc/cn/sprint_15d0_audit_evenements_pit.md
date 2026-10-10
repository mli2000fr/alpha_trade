# Sprint 15-D0 — Audit PIT des événements CN_A

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Audit réalisé le 29 septembre 2026, en lecture seule. Objet : déterminer si les **prévisions de résultats publiées par l'émetteur** et les listes **Dragon/Tiger** peuvent compléter l'Oracle Extreme CN pour distinguer D1 et D10. Aucune table, collecte planifiée, feature, expérience ML, backtest ou règle de serving n'a été ajoutée.

## Verdict

| Famille | Historique consultable | Utilisation historique aujourd'hui | Prochaine décision |
| --- | --- | --- | --- |
| Prévisions de résultats de l'émetteur (`业绩预告`) | **Oui, piste concrète** : archive officielle CNINFO, documents PDF identifiés, dates de publication. | **Recherche sous proxy PIT seulement**, après validation d'un délai prudent, des corrections et de l'extraction. Pas encore de signal numérique ni de certification PIT. | **15-D1 ciblé** : constituer un échantillon de documents, extraire bornes/année/révisions et mesurer la couverture sur tout l'Oracle OOF. |
| Dragon/Tiger (`龙虎榜`, informations de transactions rendues publiques) | Oui : pages des bourses et archive agrégée Eastmoney consultables ; Tushare annonce une série historique mais n'est pas accessible au projet. | **Pas de GO modèle** : heure de disponibilité/identité des opérateurs non prouvées, sélection par mouvement du jour ; API agrégée contient des rendements futurs explicites. | Audit séparé 15-D2, seulement après réconciliation officielle et suppression stricte des champs ex post. |
| Autres annonces/holdings | Catalogue officiel consultable, mais familles non auditées quantitativement dans C0/D0. | Aucune feature autorisée. | Prioriser seulement après l'audit des deux familles ci-dessus ; distinguer annonces, actions économiques et dates d'effet. |

Ce n'est **pas une preuve de performance directionnelle**. Le bénéfice éventuel des annonces d'émetteurs peut être limité par leur fréquence : il faut comparer des événements réellement récents, pas propager une vieille annonce pendant une année entière.

## 1. Inventaire réel du projet

La base `alpha_trade_cn` contient 21 tables. `cn_raw_payloads` a 21 816 charges (16 270 `baostock/daily`, 5 530 `baostock/adj_factor`, huit index, sept calendriers, un référentiel) et `cn_staging_rows` 8 663 120 lignes ; aucune famille prévision, rapport CNINFO ou Dragon/Tiger. `cn_corporate_actions` a 24 972 lignes, **toutes** de type `adjustment_factor_change` : ce ne sont ni des prévisions de bénéfice, ni des achats institutionnels, ni un historique d'annonces librement utilisable avant publication. Aucun branchement vers les features Oracle OOF CN n'existe.

L'[architecture cible](./architecture_bases_batchs_configuration_cn.md) mentionne `cn_top_list_sync`, `cn_events_sync` et `cn_institutional_holdings_sync`, mais ce sont des **batchs envisagés**, pas la description de collectes effectives. Ne pas confondre non plus le normaliseur `sec_corporate_events` US avec les événements CN.

## 2. Prévisions officielles d'émetteurs : ce qui a été vérifié

[CNINFO](https://www.cninfo.com.cn/new/fulltextSearch), plateforme officielle de publication des annonces des sociétés chinoises, expose des notices et PDF. Un smoke de son endpoint public `POST /new/hisAnnouncement/query` (sans installation de paquet et sans écriture) a été effectué avec `column=szse`, `category=category_yjygjxz_szsh`, `seDate` et `pageSize=30`. Sur janvier 2024, la réponse annonce **2 832 notices, 94 pages** ; 29 des 30 titres de la première page contiennent littéralement « 业绩预告 ». Il s'agit du volume retourné par la catégorie, **pas** du nombre de prévisions financières validées ni de sociétés uniques. La pagination est indispensable. Une recherche par titre exige le couple `code,orgId` obtenu par `POST /new/information/topSearch/query` ; le seul code à six chiffres a renvoyé zéro notice dans le test.

Pour `300054` sur 2024–2025, six PDF distincts ont été retrouvés (publication, exercice et titre à contrôler) :

| Heure fournie en Chine (UTC+8) | Titre abrégé | Identifiant PDF | Lecture PIT |
| --- | --- | --- | --- |
| 24/01/2024 00:00:00 | Prévision annuelle 2023 | `1218978691` | Heure apparemment normalisée ; pas de trading à l'ouverture le même jour. |
| 26/06/2024 00:00:00 | Prévision semestre 2024 | `1220455425` | Même réserve. |
| 09/10/2024 00:00:00 | Prévision T3 2024 | `1221341313` | Même réserve. |
| 15/01/2025 18:16:11 | Prévision annuelle 2024 | `1222342396` | Heure précise, après séance ; exploitable au plus tôt séance suivante après validation. |
| 09/07/2025 00:00:00 | Prévision semestre 2025 | `1224104095` | Heure apparemment normalisée. |
| 10/10/2025 00:00:00 | Prévision T3 2025 | `1224702208` | Heure apparemment normalisée. |

Ainsi **cinq horodatages sur six sont exactement 00:00:00**. Un titre/PDF daté et un identifiant stable sont utiles, mais ne prouvent pas que le PDF était disponible à l'ouverture de cette date. Un [document officiel de correction de prévision](https://static.cninfo.com.cn/finalpage/2025-04-23/1223214895.PDF) illustre qu'ancienne et nouvelle fourchette peuvent coexister : il faut reconstruire les versions par publication, pas écraser l'ancienne valeur avec la dernière.

[Tushare `forecast`](https://tushare.pro/document/2?doc_id=45) documente une forme structurée (`ann_date`, période fiscale, type, bornes de variation et de bénéfice, première annonce, cause). Cette description est utile pour le schéma cible, mais le compte Tushare de ce projet n'est pas opérationnel depuis la France ; **aucune ligne Tushare `forecast` n'a été testée localement**. Elle ne peut donc servir à certifier CNINFO.

### Petit échantillon Oracle : titres versus dates de décision

Même échantillon diagnostique que [15-C0](./sprint_15c0_audit_analystes_pit.md) : 16 codes Shenzhen tirés parmi les paires éligibles 2024H1–2025H2 ; il n'est pas représentatif de l'univers CN complet. CNINFO trouve au moins une annonce dans la période 2024–2025 pour **14/16 titres** (13/16 ont une annonce datée de 2024, 13/16 de 2025). Deux codes n'en ont aucune sur cette période (`002451`, `300332`). L'archive 2023–2025 a **62 notices** sur ces 16 codes, dont 15 possèdent au moins une notice.

Jointure exploratoire sur **279 paires titre-date distinctes**, filtrées `oracle_extreme20=true` et `evaluation_common_valid=true` dans les quatre fichiers 15-B5 `2024H1` à `2025H2`, retard 2. Aucune information de jour J ou postérieure à J n'a été comptée ; les dates de publication ont été converties en UTC+8 et exigées strictement **antérieures** à la date du signal. Fenêtres en **jours calendaires**, non séances :

| Ancienneté de la dernière notice CNINFO avant le signal | Paires couvertes | Part diagnostique |
| --- | ---: | ---: |
| Au plus 20 jours | 21/279 | 7,5 % |
| Au plus 90 jours | 93/279 | 33,3 % |
| Au plus 365 jours | 273/279 | 97,8 % |
| Au moins une notice antérieure, même plus ancienne | 277/279 | 99,3 % |

Ces chiffres comptent **la présence d'un PDF**, sans extraire chiffre, signe, exercice fiscal, caractère corrigé ni publication effective à l'heure de décision. La dernière ligne est particulièrement trompeuse : une annonce vieille de plus d'un an n'est pas une nouveauté directionnelle. Les paires Oracle sont corrélées par titre et la sélection 15-B5 inclut l'éligibilité de la marge ; **ne pas extrapoler ces taux à tous les TOP20 Oracle CN**. Les documents sont lus dans leur archive actuelle : sans journal historique des versions ni heure fiable pour les entrées à minuit, ce n'est qu'un **proxy PIT de recherche**.

## 3. Dragon/Tiger : disponibilité et risques de fuite

La [Bourse de Shanghai](https://www.sse.com.cn/disclosure/diclosure/public/inquirydata/index.shtml?secCode=600117) affiche des informations publiques depuis le 01/01/2017 ; elle précise que les montants concernent les transactions d'enchères, pas les blocs ou opérations après marché. La [Bourse de Shenzhen](https://investor.szse.cn/disclosure/deal/public/index.html) expose également sa rubrique de transactions publiques. Les pages confirment la nature officielle de l'événement, **pas** une extraction machine complète, les heures historiques ni la couverture de tous les titres Oracle. Une liste est publiée **après l'activité de la séance J** ; elle ne doit jamais être utilisée pour décider un achat au début de J.

Smoke de l'API agrégée Eastmoney `RPT_DAILYBILLBOARD_DETAILSNEW` pour le 31/01/2024 : `success=true`, **81 lignes**, neuf pages au format dix lignes. Elle retourne notamment `TRADE_DATE`, `SECURITY_CODE`, `EXPLANATION`, achats/ventes/montant net. Elle retourne **aussi** `D1_CLOSE_ADJCHRATE`, `D2_CLOSE_ADJCHRATE`, `D5_CLOSE_ADJCHRATE`, `D10_CLOSE_ADJCHRATE`, `D20_CLOSE_ADJCHRATE`, `D30_CLOSE_ADJCHRATE` : ce sont des rendements **postérieurs à l'événement**, fuites de labels évidentes. `EXPLAIN` peut contenir un taux de réussite calculé a posteriori ; ne pas l'utiliser comme feature sans audit champ par champ. Le `TRADE_DATE` est à minuit dans la réponse et ne prouve pas l'heure de publication. La liste contient aussi des titres BJ : filtrage strict `CN_A` et mapping PIT obligatoires.

[Tushare](https://tushare.pro/document/1?doc_id=108) annonce `top_list` à partir de 2005 et une mise à jour vers 20 h ; [ses détails institutionnels `top_inst`](https://tushare.pro/document/2?doc_id=107) décrivent sièges de courtage, côté achat/vente et montant, avec seuil d'accès distinct. Ces disponibilités **ne sont pas testées sur le compte utilisateur**. Une ligne « siège institutionnel » ne permet pas d'identifier le bénéficiaire réel ni de prouver un achat institutionnel net de l'ensemble du marché.

Même si les montants sont fiables, le signal est **sélectionné parce que le cours ou le turnover de J a déjà été extrême** : comparer uniquement les titres inscrits à une baseline non conditionnelle créerait un biais. Le protocole futur devra conditionner sur l'univers et les informations connus à J+1, puis comparer des lignes identiques avec/sans attributs Dragon/Tiger.

## 4. Contrat PIT minimal pour toute suite

1. **Identité** : `instrument_id` CN, code et nom valides à la date, board et radiations. Dédupliquer les annonces par `announcementId`/PDF hash ; Dragon/Tiger par exchange, séance, code et motif, sans écraser les corrections.
2. **Temporalité** : stocker `event_session`, `announced_at` réel si prouvé, `source_observed_at`, `available_at`, `version_observed_at` et heure de décision. Par défaut une annonce à heure 00:00:00 n'est pas réputée connue à l'ouverture de ce jour. Pour un backtest de recherche, comparer délais conservateurs J+1 et J+2 ; ne pas appeler cela PIT certifié sans preuve de diffusion historique.
3. **Sémantique guidance** : exercice fiscal, période couverte, métrique (`net_profit`, croissance %, recettes, etc.), unité (souvent 万元), bornes min/max, signe, prévision initiale/correction, auteur émetteur. Un trimestre 2024 et une année 2023 ne sont pas comparables. Calculer la surprise seulement par rapport à une valeur *antérieure et publique*, pas au résultat réalisé futur.
4. **Sémantique Dragon/Tiger** : distinguer montant total de la liste, sièges acheteurs/vendeurs, motif d'inscription et effet de marché ; aucun champ de rendement `D1…D30` ou commentaire de succès a posteriori dans la feature set. L'événement J n'est disponible qu'après publication, au plus tôt à J+1 pour une décision avant ouverture sous réserve de validation.
5. **Couverture** : mesurer sur tout Oracle TOP20 OOF H20, par semestre, taille, board, secteurs, D1/D10 réel, radiations et présence de PDF/champs extraits. Publier taux de documents bruts, rapports valides, événements récents et anciennes/nouvelles valeurs comparables, pas seulement le nombre de sociétés vues une fois.
6. **Licence et stabilité** : accès public au site ≠ droit de moissonner et d'utiliser massivement dans une application. Confirmer conditions CNINFO/bourses/Eastmoney et quotas avant un backfill à grande échelle ou un batch quotidien.

## 5. Décision de recherche

**15-D1 recommandé, borné et sans entraînement initial** : sur une cohorte Oracle OOF 2024–2025 pré-enregistrée couvrant Shenzhen puis Shanghai, télécharger un petit nombre de PDF CNINFO originaux et leurs éventuelles corrections ; valider manuellement dates, année fiscale, unités, ancien/nouveau ; produire un extracteur testé et une table de couverture par événement. Ensuite seulement décider d'une ablation prix seul vs données émetteur sous proxy PIT conservateur. La faible part de notices à moins de 20 jours impose un calcul de puissance et une politique d'abstention ; ne pas transformer les `273/279` annonces de moins de 365 jours en signal « frais ».

**15-D2 Dragon/Tiger séparé** : échantillon officiel SSE/SZSE daté, réconciliation avec Eastmoney, heure de disponibilité et liste blanche de champs préenregistrée. Aucun mélange avec 15-D1 ni avec les flux quotidiens 15-A0.

Statut : `SPRINT_15D0_AUDIT_COMPLETE`, `GUIDANCE_HISTORICAL_RESEARCH_PROXY_CANDIDATE`, `DRAGON_TIGER_PIT_UNPROVEN`, `NO_ML_TRAINING`, `NO_SERVING_CHANGE`.
