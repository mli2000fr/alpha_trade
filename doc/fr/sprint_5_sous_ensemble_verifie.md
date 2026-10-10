# Sprint 5 France — qualification d'un sous-ensemble limité

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date : 2 octobre 2026. Cette procédure met en œuvre la décision de rechercher un **GO limité à un sous-ensemble vérifié**. Elle n'accorde pas encore le GO : le bilan automatique établit un pool de vérification, puis bloque toute promotion canonique tant que les preuves externes manquent. L'audit est reproductible par `python -m service.fr.sprint5_subset_audit` (identifiants FR en environnement) ; sortie détaillée : `artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json`.

## Résultat du tri initial

Sur 1 552 codes `Common Stock` EUR du snapshot EODHD Paris, **490** passent le préfiltre technique : ISIN déclaré de forme et checksum valides, non partagé par d'autres codes du snapshot, au moins **504 séances** classées `VALID` dans au moins deux années distinctes et aucun split EODHD non revu. Le pool contient **323 codes actuellement actifs et 167 actuellement radiés**. Parmi eux, **412 ont une première barre valide dès 2016** (263 actifs, 149 radiés dans le snapshot courant) ; ce n'est pas une preuve de cotation continue ou d'IPO. Les dates `first_valid`/`last_valid` décrivent des barres reçues, **pas** des dates officielles de cotation ou radiation. Les barres `ZERO_VOLUME` ne comptent jamais dans les 504. Les dividendes ne sont pas exclus du pool, car le prix brut n'est pas une série total-return ; leur traitement économique reste nécessaire avant d'utiliser des rendements ajustés.

**1 062 codes sont différés**, avec motifs pouvant se cumuler : 602 sans ISIN valide, 155 dans des groupes à ISIN partagé, 604 avec historique mécanique insuffisant et 271 ayant au moins un split non validé indépendamment. Ces nombres ne sont pas additionnables. Le préfiltre ne sélectionne pas seulement les survivants : les radiés demeurent représentés. Il ne garantit toutefois pas que le snapshot des radiés soit complet historiquement.

La colonne `verified_for_canonical` du rapport vaut **0**, intentionnellement. Ni l'ISIN déclaré par EODHD ni le suffixe `.PA` ne démontrent le MIC individuel ou sa période de validité. L'[annuaire d'instruments Euronext](https://live.euronext.com/en/products/equities) permet de contrôler des cotations actuelles ; la [donnée de référence historique Euronext](https://www.euronext.com/en/products-services/static-reference-data) est un produit distinct. Une page actuelle ne reconstitue pas rétrospectivement les entrées, sorties et changements de segment.

## Contrôle indépendant ESMA FIRDS — réalisé, mais partiel

Un second contrôle a interrogé l'[index officiel ESMA FIRDS et ses fichiers Full/Delta](https://www.esma.europa.eu/sites/default/files/library/esma65-8-5014_firds_-_instructions_for_download_of_full_and_delta_reference_files.pdf). Sept archives `FULINS_E`, correspondant à quatre instantanés datés du **11 janvier 2020, 8 janvier 2022, 13 janvier 2024 et 11 janvier 2025**, ont été téléchargées dans `artifacts/fr/esma_firds/pilot_snapshots/`. Leur MD5 a été comparé aux empreintes publiées par ESMA avant lecture. Le prototype reproductible est `service/fr/esma_firds_reference_pilot.py` et son rapport détaillé `artifacts/fr/esma_firds/sprint5_reference_pilot.json` (artefact local, non commité). L'analyse compare les ISIN des **490** candidats à chaque couple ISIN/MIC présent dans ces instantanés ; elle ne se fonde pas sur le suffixe du symbole.

| Observation sur les 490 candidats | 2020 | 2022 | 2024 | 2025 |
| --- | ---: | ---: | ---: | ---: |
| ISIN présent avec MIC `XPAR` | 288 | 267 | 235 | 225 |
| ISIN présent, uniquement avec d'autres MIC | 148 | 160 | 174 | 172 |
| ISIN non retrouvé dans l'instantané | 54 | 63 | 81 | 93 |

En réunissant les quatre dates, **306** candidats ont une preuve de présence `XPAR` à au moins une date, **179** n'ont été vus que sur d'autres MIC et **5** sont absents des quatre instantanés. **207** sont présents sur XPAR aux quatre dates. Ces catégories sont des résultats d'observation, **pas** des décisions d'admission ni des listes de titres historiquement négociables. Un titre observé sur XPAR en 2020 et 2022 a pu être interrompu entre ces dates ; la première date de négociation figurant dans un enregistrement FIRDS n'est pas une preuve de toutes les séances intermédiaires. À l'inverse, l'absence à une date ne démontre pas à elle seule que l'ISIN n'a jamais été coté sur XPAR. L'échantillon pré-enregistré de 20 codes contient **15** ISIN vus sur XPAR à au moins une date et **5** vus seulement sur d'autres MIC ; il n'a pas été retouché après constat.

La prochaine preuve d'identité doit reconstituer les changements **jour par jour** à partir d'un Full de départ et des fichiers `DLTINS` successifs, en contrôlant aussi les invalidations, les changements de symbole et les segments Euronext (`XPAR`, `ALXP`, `XMLI`). Une simple intersection des quatre Full ne suffit pas. Aucune ligne canonique n'a été créée par le contrôle ESMA.

## Contre-vérification des prix — fenêtre récente seulement

Le classeur gratuit [Euronext Cash Markets Daily Reports](https://live.euronext.com/en/resources/statistics/nextday-cash) examiné pour le 1er juillet 2024 contient des agrégats par marché et indices, **pas** les OHLC individuels des actions. En revanche, l'[export historique individuel Euronext](https://live.euronext.com/en/popout-page/getHistoricalPrice/FR0010208488-XPAR) donne bien des barres par ISIN/MIC sur les **deux dernières années environ**. Sept titres actifs `XPAR` de l'échantillon fixé ont été vérifiés par `service/fr/euronext_price_reference_pilot.py` ; les CSV et rapports de comparaison, avec empreintes SHA-256, sont sous `artifacts/fr/euronext_daily_reference/`. Les titres radiés `UFF.PA` et `CAS.PA` renvoient un export vide aujourd'hui : cet outil public ne couvre donc pas leur contrôle historique.

Sur chaque titre actif, **509 séances communes**, du 3 octobre 2024 au 1er octobre 2026, ont été comparées : **3 563 couples titre/séance**. `ANTIN`, `BB`, `ENGI`, `ERA`, `PRC` et `XFAB` n'ont aucun écart OHLC au-delà de 0,0001 € ; `CCN` a **4 écarts de champ OHLC sur deux séances**. Le 7 septembre 2026, la clôture EODHD de `CCN.PA` est **161,50 €** contre **159,50 €** dans l'export Euronext ; l'ouverture et le plus bas diffèrent aussi. Le 26 mars 2025, l'ouverture diffère de 0,09 €. `ENGI` a en outre **12 écarts de volume de 1 à 8 actions**, malgré l'absence de split déclaré dans son archive EODHD. Ces écarts doivent rester visibles : ni arrondi implicite ni remplacement silencieux de la valeur fournisseur. Les données Euronext individuelles ne prouvent ni les barres antérieures à octobre 2024 ni le *point-in-time* des corrections.

Depuis cette première vérification, le [rapport approfondi du Sprint 5](sprint_5_intervalles_esma_prix_radies_actions_2026-10-02.md#contre-vérification-yahoo-20182025) ajoute une seconde source fournisseur sur 2018–2025 : Yahoo couvre les 10 actifs pré-enregistrés, avec 17 408 séances communes et 63 écarts de champ OHLC sur 69 632 valeurs comparées. Cette corroboration ne remplace pas Euronext, n'établit pas le PIT et ne couvre aucun des 10 radiés de l'échantillon, que Yahoo renvoie désormais absents.

## Échantillon de validation pré-enregistré

L'audit tire de façon déterministe, par SHA-256 de `fr_s5_subset_v1:symbol`, **10 codes actuellement actifs et 10 radiés** parmi les 490. L'ordre et les symboles sont dans le JSON ; il ne faut pas remplacer les échecs par de nouveaux titres plus faciles à vérifier. Au premier calcul :

`ALAGO.PA,CCN.PA,ANTIN.PA,ALGRO.PA,PRC.PA,ENGI.PA,ERA.PA,MLAAH.PA,BB.PA,XFAB.PA,ALDEI.PA,MDW.PA,MLMAD.PA,LAF.PA,HEXA.PA,COM.PA,MAGIS.PA,UFF.PA,CAS.PA,BLV.PA`

Pour chaque code, conserver la source, l'URL ou le fichier, sa date de publication/observation et son hash, puis vérifier :

1. ISIN, type d'action, devise, **MIC individuel** et segment via une source indépendante du snapshot EODHD ; dater l'intervalle de validité et les changements de ticker.
2. Première/dernière date officielle de cotation, suspension et radiation lorsque pertinent ; ne jamais assimiler première/dernière barre à un événement officiel.
3. Compléter le contrôle récent déjà effectué par des séances **réparties depuis 2018**, y compris des titres radiés : ouverture, plus haut, plus bas, clôture, unité, devise et convention d'ajustement auprès d'une seconde source licenciée ou publique utilisable. Consigner les écarts, notamment `CCN.PA`, sans ajustement automatique opportuniste. Les barres 2016–2017 restent archivées mais hors du premier périmètre de promotion.
4. Actions sur titres pertinentes et leur effet prix/volume ; les titres à split sont différés par défaut tant qu'une revue indépendante n'est pas disponible.
5. Convention temporelle approuvée pour la recherche : preuve historique *as-of* si disponible ; sinon hypothèse J+1 explicitement marquée `ASSUMED_NEXT_SESSION`, séparée de `observed_at` du backfill 2026. Cette hypothèse autoriserait une étude de sensibilité, **pas** l'affirmation d'un PIT exact.

## Gate de promotion limité

Ne créer `instruments`, `instrument_listings`, `instrument_provider_symbols` et `stock_bars_daily` que pour les **titres et intervalles effectivement vérifiés**, avec provenance et règles versionnées. Un titre sans preuve de période XPAR ne devient pas XPAR par défaut. Une barre `ZERO_VOLUME`, `PLACEHOLDER`, `BAD_OHLC`, `BAD_PRICE` ou `NON_SESSION` n'est pas promue ; un jour sans barre reste manquant. `volume_shares`, `split_adjusted_close`, `total_return_close` et `vwap` ne sont pas déduits du volume split-ajusté ou de `adjusted_close` EODHD. Vérifier ensuite idempotence, absence de doublons `(instrument_id,session_date)`, couverture année/statut et exclusion explicite des autres titres.

Pour l'instant, l'archive et le staging sont complets, et les vérifications ESMA/prix ont commencé, mais **le gate limité demeure `PENDING_EXTERNAL_EVIDENCE`** : l'identité *as-of*, les prix à partir de 2018 et les actions sur titres ne sont pas tous validés. Les preuves 2016–2017 ne sont plus requises pour ce premier GO limité, puisque ces dates sont exclues. Aucune table canonique n'a été alimentée ; le Sprint 6 ne doit pas traiter le pool de 490, ni les 306 observés sur XPAR, comme un univers historique tradable. Cette décision est cohérente avec la [clôture technique du Sprint 5](sprint_5_cloture_2026-10-02.md).
