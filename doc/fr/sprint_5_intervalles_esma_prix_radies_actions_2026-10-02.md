# Sprint 5 FR — intervalles ESMA, prix historiques, radiés, actions sur titres

État au 2 octobre 2026 : **audit en cours ; aucun `GO` canonique**. Ce document complète le [sous-ensemble vérifié](sprint_5_sous_ensemble_verifie.md) et la [clôture du Sprint 5](sprint_5_cloture_2026-10-02.md). Aucune table FR canonique ni aucun backtest n'a été alimenté par les contrôles ci-dessous.

**Décision de périmètre :** les barres 2016–2017 restent archivées pour la recherche et l'audit, mais ne sont pas candidates à la promotion canonique, au ML validé ni au backtest FR. Le premier périmètre candidat commence en **2018**, sans GO automatique au 1er janvier : seules les dates couvertes par un intervalle de cotation et toutes les autres preuves requises pourront être admises. Le premier Full ESMA utilisé date du 6 janvier 2018 ; les dates antérieures et les épisodes censurés à gauche restent hors preuve.

## Question et règle de preuve

Il faut distinguer trois choses qui ne sont pas interchangeables : (1) un ISIN/MIC déclaré négociable à une date donnée, (2) un prix historique exact pour cet instrument, (3) un rendement économiquement comparable après dividende, droit, scission, fusion ou regroupement. Le ticker et l'ISIN fournis *aujourd'hui* par EODHD ne prouvent pas l'identité de chaque barre ancienne. Une présence dans un fichier ESMA ne prouve pas qu'une barre particulière a été effectivement négociée. Les vérifications ne seront donc pas fusionnées en une simple case « valide ».

## Reconstitution quotidienne FIRDS ESMA

La [méthode FIRDS publiée par l'ESMA](https://www.esma.europa.eu/sites/default/files/library/esma65-8-5014_firds_-_instructions_for_download_of_full_and_delta_reference_files.pdf) impose un fichier `Full` de départ puis le rejeu ordonné des `Delta` : nouveau, modifié, terminé, annulé. Se fier uniquement aux snapshots annuels raterait des radiations, changements d'identité ou de lieu de cotation intermédiaires.

Le collecteur [esma_firds_download.py](../../service/fr/esma_firds_download.py) interroge l'index public ESMA, télécharge les fichiers officiels `FULINS_E` et `DLTINS` dans `artifacts/fr/esma_firds/replay_2018/`, reprend sans retélécharger les fichiers valides, contrôle les ZIP/CRC, le SHA-256 local et le MD5 officiel lorsqu'il existe. Il conserve des états d'échec et n'utilise pas de certificat TLS désactivé. Le rejeu [esma_firds_history.py](../../service/fr/esma_firds_history.py) filtre les 490 ISIN candidats et les MIC `XPAR`, `ALXP`, `XMLI`, puis sort versions et épisodes de cotation `as-of` avec origine et fin de chaque épisode. Le premier Full choisi est celui du 6 janvier 2018 : les épisodes déjà ouverts à cette date sont **censurés à gauche**. Ils ne prouvent pas une admission en 2016.

Le smoke sur le Full initial et les premiers Delta fonctionne : 418 des 490 ISIN possèdent un couple ISIN/MIC cible dans ce point de départ, 72 n'y apparaissent pas. Parmi ces 72, **68 n'ont leur première barre EODHD qu'à partir du 6 janvier 2018** ; leur absence initiale ne signifie donc pas à elle seule une erreur. Quatre ont des barres antérieures (`ALAVE.PA`, `MLGML.PA`, `STLAP.PA`, `URW.PA`) et exigent une vérification d'identité/ISIN/MIC spécifique. Le téléchargement est fini : **5 604 archives indexées, présentes et avec preuve de hash ; 0 échec local**. L'ancien `download_state.json` affiche `complete: false` parce que sa version du collecteur confondait absence de publication et absence de téléchargement. L'[audit de complétude](../../service/fr/esma_firds_gap_audit.py), enregistré dans `artifacts/fr/esma_firds/replay_2018/gap_audit.json`, sépare désormais ces deux notions : `download_verified_as_indexed: true`, `publication_continuity_verified: false`.

**Rejeu 2018 terminé :** 506/506 fichiers indexés traités, 1 230 versions et 431/490 candidats avec au moins un MIC cible. Le premier rapport immuable `history_2018.json` détectait 19 avertissements : 9 versions dont `FrDt` déclaré est le lendemain du fichier, et 10 chevauchements apparents dus à une publication rétroactive. La correction ne modifie pas les XML : elle sépare l'axe **première observation publique** (`archive_date`) de la **validité FIRDS déclarée** (`PblctnPrd/FrDt`). Le [recalcul traçable](../../service/fr/esma_firds_reframe.py) conserve le SHA-256 du rapport initial dans `history_2018_observed_v2.json`, préserve exactement les 1 230 événements bruts, supprime les 10 chevauchements d'observation et laisse visibles les 9 dates de validité au lendemain (7 `ALXP`, 2 `XPAR`). Il ne modifie aucune table canonique.

Parmi les **59 candidats sans MIC cible pendant 2018**, **55 n'ont leur première barre EODHD valide qu'après le 31 décembre 2018** : leur absence à cette date n'est pas une erreur d'identité démontrée. Les **4 autres** (`STLAP.PA`, `URW.PA`, `MLGML.PA`, `ALAVE.PA`) ont des barres antérieures mais aucun couple ISIN/MIC cible dans le rejeu 2018. Ils restent explicitement bloqués pour une vérification historique de l'ISIN et de la place ; ni leurs barres ni leur ticker courant ne résolvent cette divergence.

L'index public comporte **55 journées sans `DLTINS`**, dont **27 séances XPAR** : 20 en 2018, 2 en 2019, 1 en 2020, 3 en 2021 et 1 en 2026. Une seconde interrogation de l'index officiel par *nom de fichier*, indépendante du filtre sur la date de publication, ne trouve **aucun** `DLTINS_YYYYMMDD*` pour ces 27 séances ; elles ne sont donc pas un simple décalage de date dans notre première requête. Les autres dates tombent hors séance et ne sont pas un manque de cotation parisienne, sans être pour autant une preuve de continuité de publication. Un groupe atypique du 7 avril 2022 comprend à la fois un `01of01` vide (aucun `<FinInstrm>`) et un ensemble `01of02`/`02of02` ; il est isolé comme conflit de génération, sans fichier local manquant. Toute date sans Delta doit être traitée comme un intervalle de preuve incertain, non comme un jour sans changement. Les contrôles de reconstitution sur les Full ultérieurs restent à faire.

Rapports du rejeu 2018 et de son recalcul temporel :

```powershell
Get-Content F:\projets\log\batch\fr-esma-history-2018-20261002\stderr.log -Tail 5
Test-Path F:\projets\artifacts\fr\esma_firds\replay_2018\history_2018_observed_v2.json
```

Le téléchargement a atteint `5604/5604` sans erreur. Ne pas déplacer ces fichiers dans des tables métier tant que le rejeu et l'audit des journées manquantes et des événements contradictoires ne sont pas terminés.

Pour vérifier le rejeu 2018 indépendamment des Delta, les deux parties du **Full officiel du 29 décembre 2018** ont aussi été archivées sous `artifacts/fr/esma_firds/full_reconciliation_2018/2018/` (hash SHA-256 calculés). Le [recoupeur Full/rejeu](../../service/fr/esma_firds_full_reconcile.py) compare chaque couple ISIN/MIC cible actif au 29 décembre, ainsi que devise, CFI, première date de négociation et terminaison. Avec le rapport d'observation corrigé, le résultat `full_reconciliation_2018_observed_v2.json` est : **431 couples actifs reconstruits = 431 couples du Full, 0 couple manquant, 0 champ divergent, 0 doublon**. Commande reproductible :

```powershell
F:\projets\.venv\Scripts\python.exe -m service.fr.esma_firds_full_reconcile --history artifacts/fr/esma_firds/replay_2018/history_2018_observed_v2.json --output artifacts/fr/esma_firds/replay_2018/full_reconciliation_2018_observed_v2.json
```

Cette concordance renforce l'état de fin d'année, mais ne date **pas** le changement exact pendant une des 20 séances 2018 sans Delta. Les fenêtres de ces séances restent à isoler ou à recouper par une autre source avant un GO journalier.

Lorsque `gap_audit.json` indique `download_verified_as_indexed: true`, le rejeu des années ultérieures peut reprendre le rapport annuel vérifié sans retraiter les archives antérieures. Le rapport antérieur doit être un préfixe exact de l'index et porter le même pool/MIC ; le programme refuse sinon la reprise. Le passage **2019 est terminé** ; le passage **2020 est en cours** sous `log/batch/fr-esma-2020-observed-v2/`. La continuité des Delta reste un contrôle **distinct** :

```powershell
Get-Content F:\projets\log\batch\fr-esma-2020-observed-v2\stderr.log -Tail 10
Test-Path F:\projets\artifacts\fr\esma_firds\replay_2018\history_2020_observed_v2.json
```

Le rejeu 2019 est terminé : 1 300/1 300 archives indexées depuis le Full initial, 2 169 versions et 440/490 candidats avec au moins un MIC cible observé depuis 2018. La continuité quotidienne n'est toujours pas prouvée. Une seule anomalie nouvelle est enregistrée : `DLTINS_20190406_21of22.zip` publie pour `FR0004030708` (`ALDUB.PA`) une terminaison XPAR datée du 12 décembre 2017, sans version XPAR antérieure dans notre Full initial de 2018. Cet événement rétroactif ne démontre pas une radiation survenue en 2019 ; le couple XPAR reste à vérifier indépendamment. Les neuf avertissements de date `FrDt` future étaient déjà présents dans le rapport 2018.

Le passage 2020 a été lancé en arrière-plan à partir du rapport 2019. Le parseur journalise un point de progression tous les 50 fichiers. Le même mécanisme peut ensuite rejouer les autres années avec `--resume-from` pointant vers le rapport annuel achevé précédent. Un rapport partiel n'est jamais accepté comme base de reprise. En cas d'échec de téléchargement, corriger/reprendre ce téléchargement d'abord ; `--allow-incomplete` n'est autorisé que pour un diagnostic explicitement étiqueté incomplet.

## Prix plus anciens : vérification indépendante de 2016

L'[archive France 2016 de Bnains](https://www.bnains.org/archives/archives.php) a été téléchargée en lecture seule. C'est une source **tierce, non officielle et non PIT**, mais indépendante d'EODHD et indexée par ISIN/date, avec OHLCV. Le contrôle [bnains_price_reference_pilot.py](../../service/fr/bnains_price_reference_pilot.py) parcourt les ZIP mensuels/journaliers sans extraction, compare les quatre prix EODHD, et rapporte séparément les actifs et radiés. Les données et le rapport se trouvent sous `artifacts/fr/price_reference_bnains/`.

Résultat sur les **490 candidats**, sans sélection opportuniste : 406 ISIN figurent dans l'archive 2016 ; 89 963 lignes de référence, 89 652 dates communes avec EODHD ; 86 385 lignes (96,36 % des dates communes) ont les quatre prix à moins de 0,1 %, 655 autres à moins de 1 %, et 2 612 (2,91 %) ont au moins un prix à plus de 1 %. Il reste 311 lignes de référence sans barre EODHD le même jour. La présence d'un ISIN 2016 ne prouve pas à elle seule que le ticker EODHD actuel correspondait alors à ce titre ; les 84 non-jointures peuvent comprendre des introductions postérieures ou des changements d'ISIN.

Les radiés sont bien représentés : 147 ISIN aujourd'hui marqués `delisted`, soit 32 309 dates communes, dont 30 834 ont les quatre prix à moins de 0,1 %. Cela établit une corroboration partielle de prix anciens pour les radiés, **pas** une couverture survivorship-free complète : les radiés absents de l'inventaire EODHD initial ne peuvent pas apparaître dans ce contrôle.

Un écart systématique mérite une résolution avant apprentissage ou backtest. Huit titres ont un facteur médian `close EODHD / close archive` éloigné de plus de 1 %, mais presque constant dans l'année : `VIV.PA` ≈ 0,4133, `SW.PA` ≈ 0,7275, `KER.PA` ≈ 0,9301, entre autres. Tous trois ont pourtant zéro événement `splits` dans l'artefact EODHD collecté. Ceci **suggère** une réécriture/réajustement historique ou une action sur titre omise ; ce n'est pas encore la preuve du mécanisme exact. Le champ `close` EODHD ne doit pas être qualifié de brut par hypothèse sur ces lignes. Le contrôle doit être approfondi avec les avis officiels et la convention effective du fournisseur avant d'utiliser leurs rendements.

Les communiqués émetteurs confirment des événements *susceptibles* d'expliquer de tels facteurs, sans démontrer l'algorithme exact EODHD : [Vivendi a distribué Canal+, Havas et Louis Hachette en décembre 2024](https://www.vivendi.com/en/press-release/information-regarding-the-listings-of-canal-havas-and-louis-hachette-group/), [Sodexo a distribué Pluxee en février 2024](https://www.sodexo.com/news/newsroom/2024/sodexo-confirms-the-pluxee-spin-off) et [Kering a distribué des actions Puma en mai 2018](https://www.kering.com/en/news/exit-puma-from-now-effective-following-implementation-exceptional-distribution-in-kind-puma-se-shares/). Il faut vérifier la chronologie et les facteurs instrument par instrument avant de reconstruire un prix ou un rendement.

## Actions sur titres : ce qui est vérifié et ce qui manque

L'[audit EODHD des actions sur titres](../../service/fr/corporate_actions_audit.py) recense 428 événements `splits` et 4 512 dividendes sur l'inventaire collecté. La comparaison mécanique du ratio de prix autour d'un split juge 368 événements plausibles ; 47 ne concordent pas, 9 ont un voisin de prix trop distant et 4 n'ont pas de voisin exploitable. Un échec de cette heuristique n'est **pas** une preuve que l'événement fournisseur est faux : droits, scissions, restructurations et cours déjà réajustés ne se comportent pas comme un split ordinaire. De plus, 245 dividendes sont renseignés dans une devise autre que l'euro et 2 942 n'ont pas de date de déclaration ; le simple `ex-date` ne donne pas une disponibilité PIT complète.

Le pool préqualifié de 490 titres ne contient **aucun événement `splits` dans les artefacts EODHD** — c'est une conséquence du filtre technique, pas la preuve qu'il n'a subi aucune opération. Sur ce pool et pour **2018 et après**, il subsiste **2 099 dividendes**, dont **1 230 sans date de déclaration** et **99 en devise non EUR**. Il faut donc un contrôle des événements complexes et de la disponibilité PIT même pour ce pool « sans split ».

Exemples documentés par les émetteurs/Euronext : [Atos 2024](https://live.euronext.com/fr/products/equities/company-news/2024-11-08-lancement-dune-augmentation-capital-avec-maintien-du) a une opération de droits, incompatible avec une lecture naïve de son ratio EODHD comme simple split ; [Latécoère 2023](https://live.euronext.com/en/products/equities/company-news/2023-09-19-latecoere-reports-h1-2023-results) a un regroupement et un nouvel ISIN ; [Groupe Flo 2017](https://live.euronext.com/en/product/equities/fr0014004x25-xpar) a une augmentation avec droits au 13 juin. Le code fournisseur `FLO.PA` porte dans le snapshot actuel une autre identité ; ce cas, exclu des 490 candidats, démontre pourquoi un ticker seul ne peut relier les barres anciennes aux métadonnées courantes.

Le [contrat EODHD sur les prix historiques](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes) et son [API splits/dividendes](https://eodhd.com/financial-apis/api-splits-dividends) doivent être lus conjointement avec les observations empiriques ; une règle de multiplication globale des cours par le ratio `splits` serait dangereuse. Les avis officiels d'Euronext/émetteurs et, si nécessaire, l'historique payant Euronext restent la voie d'arbitrage des écarts matériels.

## Gates à fermer avant le GO du Sprint 5

1. Finir le téléchargement ESMA, quantifier les dates sans Delta, rejouer chaque année et examiner anomalies `New/Modified/Terminated/Cancelled`, réadmissions, changements d'ISIN/MIC. Les épisodes pré-2018 restent non prouvés par FIRDS seul.
2. Associer les prix 2016 à l'identité d'alors, pas seulement à l'ISIN courant ; traiter explicitement les 84 non-jointures et les 311 dates sans contrepartie.
3. Classer les 2 612 écarts de prix > 1 % par facteur stable, changement de facteur, arrondi, ticker réutilisé et action sur titre officielle. Ne pas corriger les barres automatiquement.
4. Résoudre les 47+9+4 splits non concluants et les cas à droits/scission/regroupement, au moins pour tout titre qu'on voudrait promouvoir dans l'univers tradable. Vérifier publication PIT et devise des dividendes.
5. Recontrôler les radiés hors inventaire fournisseur et les prix **à partir de 2018** par une preuve indépendante appropriée ; les contrôles 2016–2017, dont l'archive Bnains, demeurent des audits de recherche non bloquants pour ce périmètre réduit.
6. Seulement ensuite produire un manifeste par instrument/date avec `identity_verified`, `venue_interval_verified`, `price_verified`, `corporate_action_verified`, `pit_verified` et motifs de rejet. Aucun `GO` agrégé si un contrôle critique reste inconnu.

Tests ciblés : `python -m pytest -q --no-cov tests/test_fr_bnains_price_reference_pilot.py tests/test_fr_esma_firds_history.py tests/test_fr_esma_firds_reference_pilot.py tests/test_fr_corporate_actions_audit.py tests/test_fr_sprint5_subset_audit.py`.
