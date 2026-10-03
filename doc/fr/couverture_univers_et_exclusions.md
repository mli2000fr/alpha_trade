# Couverture de l'univers France et motifs d'exclusion

État mesuré le 3 octobre 2026, depuis les archives EODHD téléchargées au 1er octobre 2026. Les chiffres décrivent la couverture de notre application, et non une liste exhaustive de toutes les entreprises françaises.

## Univers disponible et univers exploitable

| Niveau | Nombre | Signification |
| --- | ---: | --- |
| Liste EODHD PA active, tous types | 1 376 | Actions, ETF, fonds et indices |
| Actions ordinaires déclarées actives dans cette liste | 631 | Séries fournisseur ; pas forcément une société unique par code |
| Actions ordinaires déclarées radiées | 923 | Codes historiques conservés dans la liste fournisseur |
| Séries d'actions archivées en EUR | **1 552** | **630 actives + 922 radiées** après filtre de devise |
| Candidats après préqualification | **490** | Identité et historique suffisants pour poursuivre les vérifications |
| Titres admis en recherche historique J+1 | **330** | **294 actifs + 36 radiés**, avec au moins une période admissible |
| Titres entraînables au moins une fois | **168** | Gates supplémentaires d'historique et liquidité du Sprint 6-B |

Le chiffre correct est 1 552, et non 1 152. Il désigne des séries fournisseur actives et radiées, pas 1 552 sociétés négociables aujourd'hui. Les deux séries d'actions non retenues lors du passage 1 554 → 1 552 sont hors de la sélection EUR.

La liste brute comprend aussi 725 ETF, 2 fonds et 18 indices déclarés actifs, ainsi que 434 ETF et 5 fonds déclarés radiés. Ces produits ne font pas partie de cette archive d'actions ordinaires en EUR.

Euronext indique **plus de 800 sociétés cotées à Paris** sur sa [page officielle Paris](https://www.euronext.com/fr/markets/paris). C'est un ordre de grandeur du marché actuel, différent de notre inventaire EODHD PA. La différence de périmètre et de couverture interdit de présenter nos 631 séries actives ou nos 330 titres de recherche comme l'intégralité du marché. Un code fournisseur, un instrument/ISIN, une ligne de cotation et une société émettrice ne sont pas des unités interchangeables.

## Pourquoi 490 candidats sur 1 552 séries ?

Le rapport `artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json` dénombre 490 candidats et 1 062 dossiers différés. Les principaux motifs techniques sont :

| Motif | Séries concernées |
| --- | ---: |
| ISIN absent ou invalide | 602 |
| Historique valide insuffisant | 604 |
| ISIN partagé par plusieurs codes fournisseur | 155 |
| Split sans validation indépendante | 271 |

**Les catégories se recouvrent : leurs nombres ne s'additionnent pas.** Une même série peut manquer d'ISIN, avoir trop peu de barres et contenir une opération non validée. Ces exclusions ne prouvent pas une mauvaise qualité économique de la société : plusieurs dossiers sont seulement insuffisamment documentés.

Les 490 candidats portent encore à ce stade des réserves sur les dates historiques de cotation, le MIC individuel, la disponibilité PIT et les preuves indépendantes de prix. Ce statut candidat ne permet pas l'entraînement à lui seul.

## Pourquoi 330 titres sur les 490 candidats ?

Le rapport `artifacts/fr/sprint5_limited_2018_2026/report.json` applique les preuves disponibles **par titre et par séance** :

- cohérence de l'ISIN et de la cotation avec la référence ESMA/Euronext ;
- exclusion des périodes de suspension/radiation ou des périodes d'identité non attribuables ;
- classification action et MIC admissible ;
- barres valides avec volume positif ;
- corroboration indépendante des prix et convention de disponibilité conservatrice J+1.

Le principal motif de rejet de lignes est `INDEPENDENT_PRICE_CORROBORATION_MISSING` : **230 628 barres**. Il existe également des barres à volume nul/invalide, des journées de publication manquantes et des périodes sans référence MIC active. Ces compteurs sont des **barres**, pas des symboles : on ne doit pas les convertir en nombre de sociétés exclues.

Les 330 titres ont au moins une période admissible. Cela ne signifie pas que toutes leurs barres 2018–2026 sont admises. Le manifeste contient 561 001 observations `RESEARCH_J1_ELIGIBLE` et 250 953 rejets.

Le `GO_RESEARCH_J1` est limité à la recherche et conserve les réserves de disponibilité historiques. Les 330 titres ne sont pas une certification de tradabilité ou d'exécution.

## Pourquoi seulement 168 entraînables ?

Le [Sprint 6-B](sprint_6b_historique_liquidite.md) impose 252 observations d'historique admissible, 15 observations minimum sur les 20 dernières séances XPAR, un prix d'au moins 1 € et une valeur échangée moyenne d'au moins 500 000 €. Il produit 170 046 lignes entraînables et 390 955 lignes inéligibles.

Les 168 titres franchissent ces gates au moins une fois. Leur nombre quotidien varie. L'année 2018 est la chauffe : aucun historique 2016–2017 non validé n'est utilisé pour accélérer artificiellement cette étape.

## Comment élargir ensuite

L'élargissement doit cibler les dossiers différés : résoudre les codes/ISIN partagés, obtenir les identités prédécesseures et leurs dates, valider les opérations sur titres, compléter la référence historique et obtenir une preuve indépendante de prix plus large. Un nouveau manifeste versionné permettra alors de refaire les étapes 6-B, 6-C et les panels.

Il ne faut pas transformer automatiquement les 1 552 séries en population d'entraînement, ni supprimer leurs archives : elles restent utiles pour reprendre les dossiers. Le benchmark interne du [Sprint 6-C](sprint_6c_identite_benchmark_secteurs.md) représente le sous-ensemble de recherche ; il n'est pas un indice officiel de toute la France.

## Où retrouver les preuves

- inventaire fournisseur : `artifacts/fr/eodhd/backfill_2016/universe.json` ;
- collecte : `artifacts/fr/eodhd/backfill_2016/summary.json` ;
- préqualification : `artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json` ;
- manifeste limité et exclusions : `artifacts/fr/sprint5_limited_2018_2026/` ;
- historique/liquidité : `artifacts/fr/sprint6b_liquidity/` ;
- identités et benchmark de recherche : `artifacts/fr/sprint6c_reference/`.
