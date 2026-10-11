# Sprint 15-B0 — Audit financement sur marge et prêt de titres CN

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

**État au 27 septembre 2026 : `GO_SOURCE_CANDIDATE` pour un backfill de recherche depuis les bourses ; `NO_GO_ML_PIT_YET` pour l'ablation B2 du Sprint 16.** Des relevés journaliers par titre de 2018, 2020 et 2025 sont réellement accessibles depuis la France. Leur profondeur complète, leurs corrections et le contrat de disponibilité historique restent à démontrer. Aucun batch ni modèle de production n'est activé par B0.

## Pourquoi cette famille est différente de 15A

Les relevés `融资融券` viennent des déclarations des courtiers aux bourses de Shanghai et Shenzhen. Ils contiennent des montants de financement, des achats financés, des remboursements et des quantités de titres prêtés/vendus à découvert. Ce ne sont ni les « flux principaux » estimés par taille d'ordre d'Eastmoney, ni des quotes de disponibilité à emprunter chez un courtier, ni la preuve qu'un ordre short serait exécutable par α-Trade.

Le solde de financement (`rzye`) est un **stock**, l'achat financé (`rzmre`) et le remboursement (`rzche`) sont des **flux**. De même, l'encours de titres prêtés (`rqyl`) est un stock de titres, tandis que vente (`rqmcl`) et remboursement (`rqchl`) sont des flux en titres. Les variations de stocks ne se résument pas toujours à la différence achat/vente : corrections et ajustements peuvent intervenir. Les ratios doivent conserver leurs unités (CNY contre titres) et utiliser le float/turnover daté.

## Inventaire du projet

- `doc/cn/architecture_bases_batchs_configuration_cn.md` prévoit `cn_margin_lending_sync`, mais la recherche dans `service/`, `modelFactory/`, `config_cn.yaml` et `batch_cn.yaml` n'a trouvé aucun collecteur CN correspondant ni feature 15B prête.
- Le référentiel historique `config/univers_cn/canonical_full_2018_2025.txt` compte 5 405 actions `sh.`/`sz.`. La présence dans cet univers **n'implique pas** l'éligibilité au financement ou au prêt à une séance donnée.
- Les barres et univers PIT existants sont nécessaires aux ratios et contrôles, mais ne reconstituent pas les soldes `融资融券`.

## Smoke réel depuis le poste, en lecture seule

Trois séances distantes ont été interrogées via les endpoints officiels utilisés par AKShare. Les réponses n'ont pas été persistées en base. Shanghai : `https://query.sse.com.cn/marketdata/tradedata/queryMargin.do` avec `tabType=mxtype`, `detailsDate=YYYYMMDD`, taille de page demandée 5 000. Shenzhen : `https://www.szse.cn/api/report/ShowReport` avec `SHOWTYPE=xlsx`, `CATALOGID=1837_xxpl`, `TABKEY=tab2` et `txtDate=YYYY-MM-DD`.

| Séance | SSE : lignes JSON | SZSE : lignes XML dans le classeur XLSX | Observation |
|---|---:|---:|---|
| 2018-06-29 | 537 | 436 | HTTP 200, fichiers structurés |
| 2020-06-30 | 965 | 819 | HTTP 200, fichiers structurés |
| 2025-06-30 | 1 893 | 1 954 | HTTP 200, fichiers structurés |

Pour SZSE, le comptage inclut les lignes d'en-tête éventuelles : il **ne représente pas encore un nombre validé de titres**. Pour SSE, la réponse de 2025 indique `total=1893`, `pageCount=1`, `pageNo=1` et `stockCode`/champs de montants au niveau de chaque ligne. Le code `600519` apparaît aux trois dates SSE. Parmi les 537 codes SSE de 2018, **47 sont absents de la réponse 2025** : le service n'applique donc pas simplement la liste 2025 à tous les historiques. Cela ne prouve pas pour autant une couverture exhaustive des titres radiés.

Ces trois dates montrent une **profondeur possible**, pas une couverture quotidienne 2018–2025. Aucun backfill complet, contrôle des trous, rapprochement des totaux boursiers, contrôle des révisions ou mesure par board n'a encore été effectué.

## Sources, champs et pièges

| Source | Niveau et champs utiles | Limite actuelle |
|---|---|---|
| [SSE — détail officiel](https://www.sse.com.cn/market/othersdata/margin/detail/) | Par séance/titre : solde et achat de financement, remboursement, encours prêté, ventes et remboursements de titres ; CNY et titres séparés | La page précise que le détail concerne les titres éligibles et que le résumé inclut des soldes de titres sortis de la liste ; analyser ce périmètre par date |
| [SZSE — détail officiel](https://www.szse.cn/disclosure/margin/margin/index.html) | XLSX daté : achat/solde de financement, vente/encours/valeur de prêt | En-têtes et unités à vérifier dans les classeurs ; remboursements pas exposés dans l'interface AKShare utilisée pour ce test |
| [AKShare — wrappers SSE/SZSE](https://akshare.akfamily.xyz/data/stock/stock.html) | Fonctions `stock_margin_detail_sse(date)`, `stock_margin_detail_szse(date)`, listes d'éligibilité SZSE | Dépendance aux endpoints officiels ; pas de garantie de schéma ni de vintage historique |
| [Tushare — `margin_detail`](https://tushare.pro/document/2?doc_id=59) | Historique annoncé depuis 2010, schéma harmonisé SSE/SZSE, 2 000 points requis | Pas d'accès Tushare opérationnel dans le projet ; ne pas le rendre prérequis |
| [Tushare — `margin_secs`](https://www.tushare.pro/document/2?doc_id=326) | Liste des titres éligibles, annoncée avant séance | Même contrainte d'accès ; une liste historique officielle équivalente devra être testée |

Les [implémentations AKShare SSE](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_margin_sse.py) et [SZSE](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_margin_szse.py) servent ici de cartes des endpoints, pas de preuve de licence ou de stabilité. Les sources officielles font autorité sur les définitions. Les balances de prêt ne sont pas synonymes de disponibilité de titres à emprunter.

## Contrat PIT et sélection

1. **Moment connu** : une ligne de séance J ne peut pas être une feature d'une décision passée avant sa publication. Tushare annonce environ 08 h 30 le lendemain pour `margin_detail`, avec la donnée du vendredi SZSE disponible le lundi matin ; cette information tierce doit être confirmée auprès des bourses ou remplacée par un retard conservateur. L'archive officielle interrogée ne porte pas l'heure historique de publication.
2. **Version historique** : les endpoints fournissent la réponse courante à une ancienne date. Ils ne montrent pas, dans ce smoke, la valeur exacte telle qu'observée à J+1. Sans preuve des révisions, le backtest doit être présenté comme **PIT approximé**, non certifié.
3. **Éligibilité** : absence de ligne peut signifier non-éligibilité, sortie de liste, suspension, trou de collecte ou anomalie. Elle ne signifie pas `balance=0`. Construire d'abord la liste éligible datée et coder explicitement `INELIGIBLE`, `MISSING`, `OBSERVED_ZERO`.
4. **Biais de taille** : 537 + environ 435 lignes en 2018 et 1 893 + environ 1 953 en 2025 représentent des sous-univers très différents. Tester les résultats par board, taille, année et statut d'éligibilité ; comparer à une baseline sur **exactement les mêmes lignes éligibles**, pas seulement au B0 sur tout l'univers.
5. **Régime réglementaire** : la [suspension du prêt intermédié `转融券` au 11 juillet 2024](https://www.sse.com.cn/home/component/news/c/c_20240710_10759727.shtml) crée une rupture structurelle. `转融券` et `融券` ne doivent pas être fusionnés ; une faiblesse ou disparition du signal short après 2024 n'est pas nécessairement une erreur de collecte.
6. **Marché et exécution** : un signal de prêt/short CN n'autorise pas automatiquement un short de portefeuille. Dans le contrat actuel CN_A, l'usage éventuel est d'abord un diagnostic directionnel ou un veto LONG, séparé de l'exécution.

## Gate de Sprint 15-B1 avant toute ablation B2

- Tester une grille de séances échantillonnées chaque année 2018–2025, puis backfill journalier reprenable avec pagination, checksum et conservation brute ; comparer comptes/totaux à SSE/SZSE.
- Résoudre les codes via `instrument_id` historique, y compris radiés, et mesurer la couverture parmi les titres éligibles à chaque séance. Vérifier listes d'éligibilité officielles datées et exceptions.
- Formaliser source, unité, transformations, heure de publication, `observed_at`, `available_at` et politique de corrections. Si l'heure ou les vintages historiques restent inconnus, appliquer un décalage conservateur explicite et étiqueter le résultat `PIT_PROXY`.
- Mesurer les valeurs manquantes/zero, les stocks négatifs, ruptures de séries, remboursements, changements d'unités et cohérence du bilan de financement.
- Pré-enregistrer les features : solde/turnover, achats/turnover, remboursements, variations et surprises J-1/J-5/J-10 ; prêt en quantité/float et ventes/volume, **avec indicateur d'éligibilité et de régime**. Les normalisateurs ne voient que le passé disponible.
- Faire l'ablation B2 contre B0 sur les mêmes dates/titres éligibles, séparément LONG, veto SHORT, D1/D10 et amplitude, avec folds OOF et contrôle post-2024. Aucun seuil ni feature ne doit être choisi sur le holdout final.

**Suite recommandée : Sprint 15-B1, backfill pilote de quelques semaines réparties sur 2018–2025 et audit de qualité/PIT, avant de décider d'un backfill complet.** Contrairement à 15A, un historique gratuit par titre est réellement accessible ; la valeur directionnelle demeure entièrement non démontrée.
