# Sprint 15-B3 — Qualification des blocages financement/prêt de titres

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Suite préparée : [15-B4 — dataset quotidien et pré-enregistrement](./sprint_15b4_dataset_szse_et_preregistration.md). Collecteur et smoke validés ; collecte complète encore à lancer.

Exécuté le 28 septembre 2026. Suite de [15-B2](./sprint_15b2_eligibilite_et_contrat_pit.md).

**Conclusion : Shenzhen peut justifier la préparation d'une expérience de recherche sous proxy explicite. Les données ne sont pas certifiées PIT strictes, et Shanghai reste exclu de cette expérience.** Aucun résultat directionnel n'a été mesuré.

## Travaux réellement effectués

Le service `service/market/cn_margin_lending_blocker_audit.py` réalise un audit borné :

1. conservation d'annonces et pièces jointes officielles d'éligibilité Shanghai ;
2. nouvelle collecte des huit relevés Shanghai encadrant les quatre épisodes de résidus ;
3. contrôle du résumé Shanghai sur ces quatre transitions ;
4. téléchargement des **40 listes quotidiennes Shenzhen** correspondant aux semaines de juin du pilote 2018–2025 ;
5. réconciliation des six mesures Shenzhen entre détail et résumé au 30 juin 2025.

Toutes les sorties sont dans `artifacts/research/cn_margin_lending/sprint15b3_blockers/`. Les pièces, réponses et reçus sont conservés avec empreinte SHA-256 et date réelle d'observation. Le service vérifie les hashes des sources B1 avant comparaison. Il ne lit ni n'écrit les tables applicatives, ne crée pas de migration et n'active aucun batch.

Le premier passage a été interrompu par un verrouillage bref Windows du remplacement de `report.json`. Une reprise bornée du checkpoint a été ajoutée ; le run final est `COMPLETED`, sans échec de source. Une réexécution depuis le cache termine en quelques secondes, sans remplacer les observations téléchargées ni leurs reçus.

## 1. Shanghai : une voie de reconstruction existe, pas encore une liste complète

Deux annonces datées et leurs pièces jointes Word binaires ont été effectivement téléchargées :

| Annonce officielle | Publication | Date d'effet | Périmètre annoncé |
|---|---|---|---|
| [Ajustement du deuxième trimestre 2018](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20180706_10784918.shtml) | 2018-07-06 | 2018-07-09 | 525 actions et 28 ETF |
| [Ajustement du quatrième trimestre 2019](https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20210531_5478095.shtml) | 2020-01-10 | 2020-01-13 | 800 actions et 59 ETF, hors STAR Market |

Ces nombres sont ceux annoncés dans les pages officielles : **les listes Word n'ont pas encore été extraites et rapprochées ligne à ligne**. Les deux liens de pièces jointes de la page 2018 renvoient des fichiers au même hash ; ils ne représentent pas deux listes indépendantes.

Un [retrait ponctuel publié le 30 avril 2021](https://www.sse.com.cn/disclosure/magin/announcement/ssereport/c/c_20210430_5448906.shtml), effectif le 6 mai, concerne cinq titres soumis à un avertissement de risque. Cela démontre qu'une simple reconduction des listes trimestrielles serait insuffisante.

Le calendrier à construire doit intégrer :

- une liste initiale complète avant le début de la période ;
- chaque nouvelle liste trimestrielle, avec sa date d'effet distincte de la publication ;
- les retraits et ajouts ponctuels entre deux listes ;
- les règles spécifiques STAR et les introductions concernées ;
- les autorisations du jour, distinctes de la présence dans une liste générale.

**Interdit :** utiliser l'annonce de juillet 2018 pour classer juin 2018, ou utiliser la liste courante 2026 pour toute l'histoire. La présence de pièces officielles rend la reconstruction possible à étudier, pas déjà achevée.

## 2. Shanghai : stabilité actuelle et comptabilité

Les huit relevés relus sont : 25/26 juin 2019, 29/30 juin 2020, 24/25 juin 2021 et 28/29 juin 2022.

Sur ces nouvelles lectures :

- zéro code ajouté ou retiré par rapport aux fichiers B1 correspondants ;
- zéro ligne économique changée sur les six mesures comparées ;
- les résidus par titre identifiés en B2 ne disparaissent donc pas par une nouvelle requête.

La comparaison ignore l'ordre des lignes et les métadonnées de pagination, mais contrôle les dates, les doublons et les valeurs économiques. **Elle prouve seulement la stabilité entre deux collectes actuelles du même site. Ce n'est ni un fournisseur indépendant ni une preuve de vintage en 2019.**

Le résumé SSE possède aussi les champs de remboursement nécessaires au contrôle :

| Transition du résumé | Résidu de financement, CNY |
|---|---:|
| 2019-06-25 → 2019-06-26 | 0 |
| 2020-06-29 → 2020-06-30 | 0 |
| 2021-06-24 → 2021-06-25 | −19 892 |
| 2022-06-28 → 2022-06-29 | +18 400 |

L'identité globale est exacte sur deux épisodes, mais pas sur les deux autres. Elle ne peut donc pas servir à « corriger » automatiquement les lignes.

La [définition SSE](https://www.sse.com.cn/market/othersdata/margin/sum/) distingue les flux, ajustements et encours de titres sortis du périmètre. Les données publiques testées ne donnent pas une décomposition suffisante pour attribuer les résidus observés. L'origine économique exacte reste **non démontrée**.

Les **3 019 transitions** de B2 restent en quarantaine ; aucune valeur originale n'a été remplacée par une valeur dérivée.

## 3. Shenzhen : extension quotidienne du rapprochement

Les 40 listes des semaines de juin ont été téléchargées et rapprochées des **46 966 lignes** du détail B1 :

- 40/40 journées rapprochées ;
- aucun instrument du détail hors liste ;
- aucun instrument de la liste sans détail sur ces 40 journées ;
- les changements de liste au cours d'une même semaine sont présents dans les fichiers datés, et non imputés à partir d'un ancrage.

Exemples : les effectifs passent de 820 à 818 pendant la semaine 2020, de 976 à 981 en 2021, et de 1 745 à 1 750 en 2023. Ces effectifs comprennent les instruments hors actions présents dans les listes de la bourse ; le futur ML devra joindre le référentiel CN pour les exclure.

Avec les 16 ancrages de B2, cela représente **48 journées distinctes échantillonnées**. Cela ne couvre pas encore toutes les séances 2018–2025. Le seul absent de B2, l'ETF `159200` au 31 décembre 2025, reste enregistré.

## 4. Shenzhen : comparaison des mêmes champs et unités

Un résumé officiel XLSX au 30 juin 2025 a été conservé séparément. Il publie les montants en CNY et les quantités en actions/parts. Le parseur refuse un changement d'unité, par exemple des centaines de millions de CNY à la place de CNY.

| Mesure | Somme du détail | Résumé officiel | Résumé − détail |
|---|---:|---:|---:|
| Achats financés, CNY | 81 507 554 435 | 81 507 554 435 | 0 |
| Encours de financement, CNY | 898 339 992 247 | 906 916 685 330 | 8 576 693 083 |
| Ventes prêtées, actions/parts | 30 982 566 | 30 982 566 | 0 |
| Quantité prêtée restante | 676 330 874 | 676 393 274 | 62 400 |
| Valeur des titres prêtés, CNY | 3 680 897 155 | 3 681 212 734 | 315 579 |
| Encours combiné, CNY | 902 020 889 402 | 910 597 898 064 | 8 577 008 662 |

Le montant **898 339 992 247** utilisé dans les constats B1 est l'encours de financement, **pas** l'encours combiné. La comparaison initiale avait un résumé arrondi ; B3 fournit les montants précis et distingue clairement les mesures.

La concordance des flux et la différence des encours sont **compatibles** avec des encours résiduels hors de la liste actuelle. Le [guide officiel Shenzhen 2023](https://docs.static.szse.cn/www/marketServices/deal/finance/busRules/W020230901534859402978.pdf) prévoit la poursuite des déclarations après un retrait jusqu'à extinction. Mais nous n'avons pas les lignes hors liste permettant d'attribuer les 8,577 milliards : **ce n'est pas une réconciliation exhaustive démontrée**.

Il est interdit de répartir arbitrairement ce déficit entre les titres observés, de multiplier les encours par un facteur de correction ou d'utiliser le résumé comme s'il avait exactement le même périmètre.

## 5. Disponibilité et corrections : ce qui est établi

Le guide Shenzhen 2023 distingue :

- les listes annoncées avant l'ouverture ;
- les données de la séance précédente publiées avant l'ouverture suivante ;
- les déclarations/corrections d'urgence avant publication ;
- certaines corrections ultérieures réservées au contrôle réglementaire.

Il autorise aussi l'absence de déclaration lorsqu'encours antérieurs et activité sont tous nuls. **Une absence n'est donc pas nécessairement une panne, mais elle ne suffit pas non plus à prouver un zéro.**

Ce guide fournit une base réglementaire de délai, pas l'horodatage historique de chaque réponse ni une certification de toute la période 2018–2025. Les versions antérieures des règles devront être prises en compte avant de qualifier cette période strictement.

Le protocole de B2 reste inchangé :

```text
date du relevé
→ clôture de la deuxième séance ouverte suivante : research_available_at_proxy
→ décision seulement après ce proxy
→ entrée éventuelle à une ouverture ultérieure
```

Ce retard ne neutralise pas une archive révisée longtemps après sa publication. Les reçus B3 portent donc `historical_vintage_proven=false`. Aucune date de collecte actuelle n'est rebaptisée date historique de disponibilité.

Pour la collecte prospective, une observation doit rester immuable. Une correction crée une nouvelle version reçue à un nouvel instant ; la jointure doit choisir une version reçue avant la décision. Cette architecture est spécifiée ici mais **aucun nouveau batch prospectif n'a été activé**.

## 6. Décision pratique

| Usage | Décision |
|---|---|
| Analyse descriptive des bruts échantillonnés | Possible, en conservant périmètres et limites |
| Préparation d'une expérience Shenzhen sous proxy | Défendable, avec pré-enregistrement et backfill quotidien contrôlé |
| Entraînement immédiat avec les 48 journées | Non : échantillon d'audit, pas dataset d'entraînement |
| Intégration Shanghai dans l'expérience | Non : éligibilité complète et résidus non qualifiés |
| Backtest présenté comme PIT strict certifié | Non : vintages historiques non prouvés |
| Déploiement ML/live | Non : aucune performance prédictive testée |

Verdict du rapport : `NO_GO_STRICT_PIT_PROXY_RESEARCH_REQUIRES_PREREGISTRATION`.

**On ne rejette pas la piste directionnelle : elle n'a pas encore été testée.** On réduit son périmètre à la partie la mieux contrôlée, au lieu d'exiger que les blocages Shanghai soient tous résolus pour commencer toute recherche.

## Prochaine étape proposée : 15-B4

Préparer puis collecter un dataset Shenzhen quotidien, sous contrat de recherche explicitement non certifié PIT :

1. pré-enregistrer les périodes, le retard en séances, les sous-univers et les critères de décision avant de regarder les performances ;
2. backfill des détails et des listes datées, avec reprise, hashes, limites de requêtes et rapport de couverture ;
3. joindre les actions CN historiquement cotées, sans ETF et sans utiliser la liste actuelle pour le passé ;
4. garder les absences et zéros observés distincts ; contrôler unités, changements de périmètre et fenêtres de calcul ;
5. préparer un petit nombre de features : intensité des achats financés normalisée par les échanges et évolution des encours, avec références comparables et effets taille/secteur ;
6. évaluer LONG/veto et D1/D10 en folds temporels purgés, sur le même sous-univers que la baseline, avec analyse séparée avant/après la rupture réglementaire de juillet 2024 ;
7. comparer plusieurs retards conservateurs préfixés pour la sensibilité, sans rechercher le meilleur retard sur le test final.

Les flux de prêt ne rendent pas les shorts exécutables dans CN_A. Leurs unités et le régime réglementaire doivent être vérifiés avant toute normalisation par volume. Un résultat positif sous archive/proxy restera un résultat exploratoire, à confirmer prospectivement.

Cette prochaine tranche **n'est pas lancée automatiquement** par B3. Aucun run lourd n'est encore en cours.

## Reproduction

```powershell
python -u -m service.market.cn_margin_lending_blocker_audit
python -m pytest tests/test_cn_margin_lending_blocker_audit.py tests/test_cn_margin_lending_contract_audit.py tests/test_cn_margin_lending_pilot.py -q --no-cov
```

Tests : comparaison économique indépendante de l'ordre, dates erronées rejetées, conservation des reçus, altération de cache détectée, mesures nommées et unités validées, plus garde-fous B1/B2. Le rapport ne constitue pas une validation de toute l'application.
