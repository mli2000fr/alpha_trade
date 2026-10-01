# Sprint 15-B1 — Backfill pilote `融资融券` SSE/SZSE, 2018–2025

Suite exécutée : [15-B2 — rapprochement des listes et contrat PIT](./sprint_15b2_eligibilite_et_contrat_pit.md). Les constats ci-dessous décrivent l'état du pilote B1 ; B2 a depuis rapproché les 16 listes Shenzhen, sans lever les blocages SSE/vintages.

**Exécuté le 28 septembre 2026. Verdict : `GO_BACKFILL_RESEARCH`, mais `NO_GO_FEATURES_PIT` et `NO_GO_SPRINT16_B2` tant que l'éligibilité historique et la disponibilité/révision des données ne sont pas résolues.** Il s'agit de financement sur marge et de prêt de titres, non du money-flow Eastmoney du Sprint 15-A0.

## Périmètre réalisé

Le module de recherche `service/market/cn_margin_lending_pilot.py` interroge directement les archives officielles SSE et SZSE via HTTPS vérifié (Schannel Windows), sans installer AKShare ni écrire dans `alpha_trade_cn`. Les données brutes sont conservées avec SHA-256, état de reprise et mesures de qualité par séance. Une date marquée terminée n'est sautée au redémarrage que si ses deux fichiers bruts sont encore présents et conformes aux empreintes. Aucun batch planifié, schéma de production, feature, entraînement ou serving n'a été activé.

Deux échantillons complémentaires, choisis à partir des séances `open` du calendrier CN local :

| Échantillon | Définition | Séances terminées | Réponses officielles | Lignes SSE + SZSE | Échecs |
|---|---|---:|---:|---:|---:|
| Ancrages | Dernière séance ouverte de juin et décembre, chaque année 2018–2025 | 16/16 | 32 | 20 987 + 20 134 = **41 121** | 0 |
| Continuité | Cinq dernières séances ouvertes de juin, chaque année 2018–2025 | 40/40 | 80 | 49 769 + 46 966 = **96 735** | 0 |

Les huit derniers jours de juin sont présents dans les deux campagnes. Il y a donc 56 traitements réussis, mais 48 séances distinctes. Les **112 fichiers bruts** ont été revérifiés contre leurs SHA-256. Les états reproductibles sont [ancrages](../../artifacts/research/cn_margin_lending/sprint15b1_2018_2025/state.json) et [semaines](../../artifacts/research/cn_margin_lending/sprint15b1_june_weeks_2018_2025/state.json).

Relance ou reprise, depuis la racine du projet :

```powershell
python -m service.market.cn_margin_lending_pilot --sample-mode anchors --output-root artifacts/research/cn_margin_lending/sprint15b1_2018_2025
python -m service.market.cn_margin_lending_pilot --sample-mode june_week --output-root artifacts/research/cn_margin_lending/sprint15b1_june_weeks_2018_2025
```

Les endpoints et champs bruts sont documentés dans [15-B0](./sprint_15b0_audit_margin_lending_pit.md). Le parseur SZSE lit le XLSX officiel sans `openpyxl` : il conserve le classeur original et retire seulement le suffixe d'unité des en-têtes pour les contrôles. Par exemple, `融资买入额(元)` devient `融资买入额`, avec CNY préservé dans le brut ; `融券卖出量(股/份)` reste une quantité, jamais un montant.

## Couverture observée

Le dénominateur ci-dessous est **l'ensemble des actions cotées du référentiel CN à cette date**, non la liste des titres éligibles au financement. Le pourcentage est donc une part de l'univers actions, **pas** une mesure de complétude des fichiers boursiers. Les plages sont le minimum/maximum des cinq séances de juin de chaque année.

| Année | SSE : part des actions cotées observées | SZSE : part des actions cotées observées |
|---|---:|---:|
| 2018 | 36,42–36,45 % | 20,16 % |
| 2019 | 35,08–35,15 % | 19,66 % |
| 2020 | 55,13–55,32 % | 35,18–35,28 % |
| 2021 | 56,38–56,42 % | 38,11–38,24 % |
| 2022 | 58,56–58,59 % | 42,33–42,48 % |
| 2023 | 68,99–69,22 % | 59,09–59,15 % |
| 2024 | 70,06–70,14 % | 60,48–60,49 % |
| 2025 | 71,15 % | 62,39–62,41 % |

La sélection de titres autorisés s'est fortement étendue : comparer naïvement un modèle 2018 à 2025 sans contrôler l'éligibilité, le board et la taille produirait un effet de composition. Sur les ancrages, le 29/06/2018, **944** actions du référentiel sont présentes sur **3 533** cotées ; le 31/12/2025, **3 480** sur **5 183**. Ces quotients ne sont pas des taux de qualité fournisseur.

Le fichier officiel des [titres éligibles SZSE](https://www.szse.cn/disclosure/margin/object/index.html) a répondu en XLSX daté pour le 29/06/2018 et le 30/06/2025. Il n'a pas encore été rapproché, ligne à ligne et sur toutes les séances, des détails collectés. Pour SSE, la page officielle précise que le détail concerne les titres actuellement dans le périmètre de financement et que le résumé peut contenir des soldes de titres sortis de la liste. **Absent du détail ≠ zéro**.

## Contrôles effectués et écarts

Précision B3 : le montant SZSE de 898 339 992 247 CNY cité ci-dessous correspond à l'**encours de financement**. L'encours combiné détail est 902 020 889 402 CNY ; le résumé exact financement est 906 916 685 330 CNY. Voir le [rapprochement des six mesures en B3](./sprint_15b3_qualification_blocages.md) ; l'écart n'est pas une comparaison financement contre encours combiné.

- Sur les 16 ancrages et les 40 journées hebdomadaires : **0 doublon de code par bourse/séance**, **0 valeur négative** parmi les champs contrôlés, **0 cellule numérique manquante** dans les six mesures SZSE, **0 date SSE discordante** et **0 page SSE tronquée** selon le compteur de pagination. Tous les fichiers téléchargés sont lisibles et hachés.
- Pour SZSE, `融资余额 + 融券余额 = 融资融券余额` est exact sur les **46 966 lignes** des semaines. C'est une vérification de cohérence interne, non une preuve de vintage historique.
- Pour SSE, l'équation simplifiée `solde_financement_J = solde_J-1 + achats_J − remboursements_J` présente un résidu supérieur à 1 CNY pour **2 972 / 39 808** paires titre/séances successives (7,47 %). Ces résidus sont concentrés sur quatre transitions : 25→26/06/2019 (414 titres), 29→30/06/2020 (914), 24→25/06/2021 (709) et 28→29/06/2022 (935). Les autres transitions du pilote se réconcilient pratiquement à l'unité. L'[explication officielle SSE](https://www.sse.com.cn/market/othersdata/margin/detail/) inclut des composantes d'ajustement dans le remboursement : **ne pas remplacer** ces valeurs par une différence calculée. La cause exacte et les vintages de ces quatre épisodes restent à auditer.
- L'équation simplifiée sur l'encours de titres prêtés SSE a **378 / 39 808** résidus supérieurs à une unité, dont 326 en 2020. Là encore, la définition officielle prévoit plusieurs formes de restitution/ajustement ; ces cas ne sont pas effacés.
- Le total des soldes de financement dans les détails SSE est inférieur au résumé SSE sur les deux dates contrôlées : 548,246 Md CNY contre 553,522 Md au 29/06/2018 ; 918,833 Md contre 925,419 Md au 30/06/2025. Ceci est cohérent avec l'avertissement officiel sur les titres sortis du périmètre, mais le rapprochement exhaustif reste ouvert. Au 30/06/2025, le détail SZSE totalise 898,340 Md contre 906,916 Md CNY dans le résumé officiel ; cet écart d'environ 0,95 % **n'est pas expliqué** par ce pilote.

Ces écarts ne prouvent pas une anomalie de l'application : ils signalent que l'exactitude comptable et la définition du périmètre doivent être validées avant toute feature économique.

## Pourquoi le gate PIT reste fermé

1. Les archives datées obtenues aujourd'hui ne fournissent pas l'heure ni la valeur telles qu'observées en 2018–2025. Elles peuvent avoir subi des corrections. Le `started_at` du pilote est l'heure **actuelle de collecte**, pas une heure historique de disponibilité.
2. [Tushare documente](https://tushare.pro/document/2?doc_id=59) une mise à jour du détail vers 08 h 30 le lendemain et celle du vendredi SZSE le lundi matin. Cette déclaration tierce est utile pour construire un **proxy de délai conservateur**, mais n'établit pas un vintage officiel ligne par ligne.
3. Les listes datées de titres éligibles ne sont pas encore réconciliées. Il faut distinguer `INELIGIBLE`, `MISSING_SOURCE`, `OBSERVED_ZERO` et `REMOVED_WITH_BALANCE`. La comparaison B2 devra se faire sur exactement le même sous-univers éligible que B0.
4. La [suspension de `转融券` au 11/07/2024](https://www.sse.com.cn/home/component/news/c/c_20240710_10759727.shtml) marque une rupture réglementaire ; `融券` et `转融券` ne sont pas interchangeables, et un signal short ne crée pas une possibilité d'exécution short dans CN_A.

## Décision et prochaine tranche

**GO** pour un backfill de recherche SSE/SZSE limité, contrôlé et conservant les bruts. **NO-GO** pour injecter les mesures dans les folds D1/D10 ou ouvrir la variante B2 du Sprint 16 maintenant. Les résultats ne mesurent aucune performance prédictive.

**Sprint 15-B2 proposé :** construire le calendrier d'éligibilité daté SSE/SZSE ; expliquer les écarts détail/résumé et les quatre transitions de résidus ; définir un retard `available_at` conservateur et une politique de corrections/vintages ; seulement alors backfill complet et pré-enregistrement des features LONG/veto, avec analyse séparée avant/après juillet 2024. Ne créer de table canonique de production qu'une fois ces contrats validés.
