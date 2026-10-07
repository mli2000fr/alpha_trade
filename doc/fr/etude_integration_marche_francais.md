# Étude d'intégration du marché actions français

État au 17 septembre 2026. Étude de faisabilité et POC de recherche uniquement : aucune table, stratégie, tâche planifiée ou exécution live France n'a été activée.

## Verdict

L'intégration d'Euronext Paris est réalisable, mais **pas par un simple switch US/FR**. Le code métier, les clés de données, le calendrier, la devise, les coûts et le courtier sont aujourd'hui largement américains. Il faut d'abord isoler un pipeline de recherche FR, puis adapter le cœur multi-marchés si une stratégie française passe les tests OOS nets de frais.

Les données françaises gratuites offrent une meilleure porte d'entrée que le short interest US sur un point précis : l'AMF publie un CSV historique des **positions courtes nettes rendues publiques** avec ISIN et date de publication. En revanche, ces déclarations sont rares et censurées par seuil. Le POC ci-dessous ne montre **pas** qu'elles permettent à elles seules de distinguer D1 de D10. Les données les plus susceptibles d'apporter un complément directionnel historique (révisions de consensus PIT, prêt de titres, carnet/enchères, flux d'options) ne sont pas confirmées à bas coût.

## 1. Audit du code et du schéma existants

| Couche | Contrat actuel observé | Impact FR |
| --- | --- | --- |
| Identité | `stock_metadata.symbol` est la PK ; `stock_bars_daily` a `(symbol,date)` ; `model_predictions` a `(symbol,prediction_date,run_id)` ; `global_rank_history` et `global_oracle_labels` sont également indexées par ticker seul. | Un ticker n'est pas une identité mondiale. Introduire un identifiant d'instrument stable, ISIN, MIC de cotation, devise et périodes de validité des symboles. Les contraintes uniques et jointures historiques doivent être revues ensemble. |
| Univers | Fichiers texte `config/univers` et `config/univers_batch`, `asset_class='us_equity'` dans le selector. | Univers FR séparé, actions ordinaires et éligibilité à la date J ; exclure ETF/ETN/fonds et titres trop illiquides. Ne pas interpréter `tradable` Alpaca comme éligibilité chez un courtier français. |
| Temps | `common/market_calendar.py` utilise NYSE / `America/New_York` ; `execution_engine.config` prévoit `market_calendar_name='NYSE'`. | Calendrier XPAR / Europe/Paris, jours fériés, heures d'enchère et horodatages UTC ; le paquet `pandas_market_calendars` installé reconnaît déjà `XPAR`, mais le code doit sélectionner le calendrier par marché. |
| ML | Benchmark par défaut `SPY`, cible optionnelle `target_excess_vs_spy`, features VIX/VXN/VIX3M/MOVE, régimes et breakers SPY ; labels Oracle classés par date sur l'univers chargé. | Modèles et profils de features FR distincts ; benchmark cohérent avec l'univers FR (pas SPY), macro euro, disponibilité PIT locale ; D1/D10 doivent être des quantiles de l'univers FR seulement, jamais US+FR mélangés. Entraînement français à zéro, aucun poids US servi en FR par défaut. |
| Prix | `stock_bars_daily` impose `data_adjustment='split'`; sa PK ne permet qu'une source canonique par ticker/date. | Vérifier prix brut/ajusté, splits, dividendes, opérations sur titres et delistings avant labels. Stocker les versions/provenances puis choisir un canonique. Les données EODHD et Yahoo doivent être rapprochées sur un échantillon. |
| Fondamentaux/événements | `stock_fundamentals_daily` contient les champs/formulaires SEC ; earnings/analystes/FINRA/Alpaca sont des flux US. | Adaptateurs France spécifiques : INFO-FINANCIERE/DILA, AMF, INPI et fournisseur financier choisi ; conserver `published_at`, `observed_at`, `available_at` et révisions. Les formulaires SEC ne se transposent pas. |
| Portefeuille et backtest | Valeurs, commissions et ADV décrits en USD ; portefeuille, coûts, slippage, risk overlays et protections liés au cycle US. | Portefeuille de base EUR ou conversion FX PIT explicite ; commissions du courtier, spreads, taxes françaises applicables selon instrument/date, tailles de lots, horaires et suspensions. Interdire un backtest mixte tant que ces règles ne sont pas couvertes. |
| Exécution | `execution_engine` et préflight passent par Alpaca ; sérialisation des ordres et protections Alpaca. | Adaptateur courtier Euronext Paris distinct, authentification, ordres, fills, OCO/protection, réconciliation et disponibilité du short. Aucune activation live française avant parité paper/live et confirmation contractuelle du courtier. |
| IHM/ops | Pages Pipeline, ML, Backtest, Selector, Risque, Exécution, Batch et Paramètres affichent les sources et runs sans contexte marché commun. | Un sélecteur de marché en amont, propagé aux commandes, artefacts, tables, diagnostics et exports ; filtrer les batchs US/FR. Afficher devise, MIC, calendrier, fournisseur, broker et profil de frais de chaque run. |

Références code : `common/market_calendar.py`, `common/universe_files.py`, `selector/filters.py`, `selector/db_io.py`, `modelFactory/config.py`, `modelFactory/oracle/build_labels.py`, `execution_engine/config.py`, `execution_engine/broker_adapter.py`, `backtesting/cli/_impl.py`, `database/sql/stock/stock_bars_daily.sql`, `database/sql/stock/stock_metadata.sql`, `database/sql/ml/model_predictions.sql`, `database/sql/ml/global_oracle_labels.sql`.

### Architecture recommandée

```text
                           sélection du marché (US | FR)
                                     |
                         instrument_master PIT
                 (instrument_id, ISIN, MIC, ticker, devise,
                  valid_from/to, type, broker_eligibility)
                                     |
             +-----------------------+-----------------------+
             |                                               |
       adaptateurs données US                          adaptateurs données FR
       NYSE / USD / SPY                              XPAR / EUR / benchmark FR
             |                                               |
       labels + modèles US                            labels + modèles FR
             +-----------------------+-----------------------+
                                     |
                    portefeuille / risque multi-devises
                                     |
                         adaptateur courtier du marché
```

Conserver **un dépôt applicatif**, pas une branche France divergente. À court terme, le POC doit rester dans des artefacts ou tables de recherche FR distinctes ; ne pas ajouter immédiatement des colonnes `market` à toutes les tables US ni réécrire la PK des 32 M+ barres en production. Après validation économique, migrer progressivement vers `instrument_id`, avec compatibilité US, tables volumineuses par étapes, tests de parité et plan de retour arrière. Une base physique France séparée n'est pas nécessaire par principe ; un schéma de recherche isolé peut toutefois protéger le système actuel pendant le POC.

## 2. Fournisseurs et intérêt directionnel

| Besoin | Source vérifiée au 17/09/2026 | Coût/accès | PIT/histoire | Limite pour D1/D10 |
| --- | --- | --- | --- | --- |
| Identité, prix EOD, splits/dividendes | EODHD couvre `PA` / `XPAR`; All World est affiché à **19,99 USD/mois**. Yahoo `*.PA` a répondu pour 18 actions du POC. | EODHD payant ; Yahoo utile seulement au POC personnel, sans SLA/licence contractuelle validée. | Profondeur historique à contrôler titre par titre et ajustements à rapprocher d'Euronext. | Prix seul a déjà peu séparé les tails US ; n'apporte pas automatiquement la direction en France. |
| Positions courtes publiques | **AMF / data.gouv.fr**, CSV officiel depuis 2012, ISIN, ratio, date de position et date de publication. | Gratuit, Licence Ouverte ; URL stable. | La publication J, non la date de position, pilote `available_at`; dans le POC, entrée au plus tôt la séance suivante. | Seuil public de 0,5 %, positions sous seuil invisibles, peu d'émetteurs touchés ; ce n'est pas le short volume quotidien ni les disponibilités de prêt. |
| Information réglementée | **INFO-FINANCIERE / DILA**, flux XML + pièce attachée. | Accès HTTPS libre. | Métadonnées et pièce horodatables ; extraction des événements et révisions à construire. | Potentiel pour surprises/guidance, mais extraction texte, ISIN et contrôle de disponibilité exigeants. |
| Rapports/comptes des entreprises | **INPI / RNE** via compte API. | Open data avec inscription. | Date de dépôt/publication et identité SIREN↔ISIN à vérifier. | Publication peu fréquente ; plus utile pour qualité/fondamentaux que direction H5-H20. |
| Transactions des dirigeants | Publications AMF, souvent PDF ; un jeu communautaire les parse. | Accès public, mais parsing communautaire non contrôlé humainement. | Date de publication obligatoire, erreurs de parsing possibles. | Signal parcimonieux ; ne pas servir sans validation contre source AMF. |
| Trades/quotes Euronext | Fichiers de transactions retardés d'au moins 15 min, gratuits pour usage interne ; Web Services historiques par offre. | Fichiers retardés gratuits, disponibilité garantie au moins 24 h ; Web Services/prix à confirmer. | Collecte prospective quotidienne possible, pas de backfill historique long gratuit garanti. | Trades sans sens agresseur/carnet complet ; flux d'ordres et enchères détaillés relèvent d'offres licenciées. |
| Consensus, prêt de titres, options, carnet d'ordres | Aucun fournisseur historique français, PIT, automatisable et bon marché n'a été validé dans cette étude. | Devis/licence requis avant hypothèse de coût. | La date d'observation d'un snapshot actuel ne reconstitue pas 2016–2025. | Ne pas remplacer une série historique par des données révisées d'aujourd'hui. |

EODHD est un fournisseur de prix/fondamentaux potentiel, **pas une preuve de signal directionnel**. Son site indique que certains cours ne sont pas directement des flux de place ; comparer les prix EOD contre une référence Euronext avant les labels/backtests. Le jeton EODHD déjà présent sur la machine n'a pas été utilisé pour ce POC.

### Courtier et frais : décisions séparées des données

L'adaptateur Alpaca actuel ne peut pas être présumé compatible avec des actions Euronext Paris. Même la documentation de l'offre Alpaca Europe décrit l'achat/vente d'actions et ETF **américains** en EUR pour des partenaires, non une couverture XPAR retail. Saxo publie une OpenAPI avec découverte d'instruments et placement d'ordres ; il reste à vérifier avec un compte réel l'éligibilité XPAR, les types d'ordres, les commissions et l'accès API. IBKR demeure une autre possibilité technique, mais le POC IBKR précédent a été abandonné par choix utilisateur : ne pas en faire une dépendance obligatoire. Le POC ML doit donc rester indépendant de tout compte de courtage.

En simulation, calculer les frais par courtier et par instrument, et traiter la taxe française sur les acquisitions d'actions lorsqu'elle s'applique **selon la liste et les règles en vigueur à la date du trade** ; ne pas plaquer les coûts US sur Paris. Le moteur SHORT doit rester désactivé en live jusqu'à preuve de disponibilité d'emprunt, de coût et de possibilité d'ordre sur les titres concernés.

Sources : [AMF positions courtes](https://www.data.gouv.fr/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012), [règle de publication AMF](https://www.amf-france.org/fr/ou-trouver-les-positions-courtes), [DILA INFO-FINANCIERE](https://www.data.gouv.fr/datasets/info-financiere), [INPI comptes](https://www.data.gouv.fr/datasets/documents-et-comptes-des-entreprises), [Euronext fichiers retardés](https://marketdata.euronext.com/data-reporting-service/trades-file), [Euronext produits de données](https://www.euronext.com/en/products-services/euronext-real-time-data), [EODHD Paris](https://eodhd.com/exchange/PA), [tarifs EODHD](https://eodhd.com/pricing), [Alpaca Europe](https://docs.alpaca.markets/eu/docs/about-broker-api), [Saxo OpenAPI ordres](https://developer.saxobank.com/openapi/learn/order-placement), [BOFiP taxe transactions](https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20250528).

## 3. POC exploratoire AMF × prix (sans modification de l'application)

### Accès et couverture

- CSV AMF officiel lu en mémoire via l'URL stable : **40 655 déclarations**, **269 ISIN historiques**, dates de publication ISO valides de 2012 à septembre 2026.
- En 2024–2025 : **7 255 déclarations mais seulement 116 ISIN distincts** ; il ne s'agit donc pas d'une feature dense pour tout l'univers français.
- 18 actions `.PA` avec ISIN connus ont été appariées manuellement ; Yahoo a répondu en EUR pour les 18, avec environ 1 919 séances par série sur la première fenêtre d'essai. Pas d'écriture en DB ni d'emploi du jeton EODHD.

### Contrat de test

1. Date signal = **date de début de publication AMF**, pas date de position. Exécution hypothétique = ouverture de la première séance XPAR **strictement après** la publication (prudence car l'heure de publication n'est pas fournie dans le CSV).
2. « Hausse short » = augmentation d'au moins 0,1 point de pourcentage d'un détenteur déjà observé, ou première déclaration publique à au moins 0,5 %. « Baisse short » = diminution d'au moins 0,1 point. Ce sont des règles de faisabilité, non optimisées.
3. Rendement = clôture H20 / ouverture d'entrée − 1, sans coûts ; les observations de rendement absolu >80 % ont été mises à part pour réduire les anomalies de corporate actions.
4. D1/D10 approximés sur **18 titres seulement** : deux titres par tail (~11,1 %). Il ne s'agit **pas** des vrais déciles d'un univers français tradable complet.
5. Séparation temporelle : développement 2018–2023, contrôle 2024–2025. Les événements d'un même titre ont été espacés d'au moins 20 séances pour le résumé principal.

| Période | Signal AMF | Événements indépendants | Excès H20 moyen vs panel 18 | Part bottom tail | Part top tail |
| --- | --- | ---: | ---: | ---: | ---: |
| 2018–2023 | Hausse short | 390 | −0,35 % | 14,1 % | 12,6 % |
| 2018–2023 | Baisse short | 338 | +0,17 % | 13,0 % | 13,0 % |
| 2024–2025 | Hausse short | 175 | −1,10 % | 10,9 % | 5,7 % |
| 2024–2025 | Baisse short | 136 | −1,15 % | 18,4 % | 12,5 % |

Référence mécanique de chaque tail sur 18 titres : ~11,1 %. Les deux directions ne sont **pas** stables : la baisse short n'est pas un signal LONG fiable sur la période de contrôle ; la hausse short indique parfois une sous-performance moyenne mais ne sélectionne pas proprement D1. **Verdict : source gratuite intéressante comme feature candidate ; NO-GO pour une règle D1/D10 autonome.** Aucun test Oracle conditionnel, commission, spread, taxe ni slippage n'a été fait. Les 18 titres sont sélectionnés parce qu'ils ont beaucoup de déclarations : biais fort, résultat non généralisable.

### POC sérieux suivant, uniquement si l'on veut poursuivre

1. Construire l'univers XPAR actions ordinaires par date (ISIN/MIC, cotations et retraits, filtres de liquidité PIT) et obtenir des prix EOD ajustés validés pour 2016–2025, puis les annonces AMF et les documents INFO-FINANCIERE.
2. Répéter la baseline Oracle France H5/H10/H20 et labels D1/D10 **sur cet univers entier** ; contrôler l'amplitude OOS avant toute direction. Les actions sans position courte publiée sont « non observées », pas « short=0 ».
3. Comparer Oracle seul, Oracle + positions AMF, Oracle + événements réglementés ; modèles simples avant modèles complexes, ablations et couverture mesurées. Validation walk-forward avec embargo H20 et disponibilité des annonces, par année/régime/capitalisation ; OOS final gelé.
4. Mesurer précision D1/D10 conditionnelle Oracle, calibration, abstention, couverture des jours/symboles, puis performance nette avec frais du courtier FR et disponibilité réelle du short. Une amélioration sur quelques émetteurs ne suffit pas pour déployer toute la France.

### POC complémentaire — métadonnées INFO-FINANCIERE, sans abonnement

Le script de recherche `scripts/research/fr_public_disclosures_poc.py` a interrogé l'[API publique INFO-FINANCIERE](https://www.data.gouv.fr/dataservices/api-info-financiere) et les cours Yahoo anonymes pour les mêmes 18 titres, 2018–2025. Il n'écrit aucune table de l'application. L'archive expose ISIN, titre, catégorie, horodatages officiels et URL du document. La règle temporelle retient le plus tardif des horodatages officiels et entre seulement à l'ouverture de la séance suivante. **Ces horodatages de transmission ne prouvent pas à eux seuls l'heure effective de mise à disposition publique** : le contrat PIT doit encore être vérifié. Les déciles restent **approximés sur 18 titres**, pas sur le marché français entier. Le rapport et les événements sont sous `artifacts/research/fr_public_disclosures/`.

Un lexique préétabli sur le titre de l'annonce repère les mentions de résultats/chiffre d'affaires/prévisions et les formulations clairement haussières ou baissières. Après séparation temporelle 2018–2023 / 2024–2025 et espacement d'au moins H jours des événements d'un même titre :

| Contrôle 2024–2025 | n indépendant | Excès moyen vs panel | Bottom ~10 % | Top ~10 % |
| --- | ---: | ---: | ---: | ---: |
| Toute annonce, H5 | 825 | +0,02 % | 11,0 % | 10,9 % |
| Titre financier, H5 | 141 | −0,32 % | 17,7 % | 17,0 % |
| Titre financier, H20 | 125 | −0,71 % | 16,8 % | 10,4 % |

Le taux mécanique de chaque tail vaut environ 11,1 %. L'effet H5 des titres financiers touche **les deux queues** : hypothèse d'amplitude à confirmer, **pas un signal D1/D10**. Il n'est pas porté par un unique symbole (17 titres ont des événements financiers en contrôle). Les formulations explicitement directionnelles sont trop rares : seulement 3 titres positifs et aucun titre négatif exploitables en contrôle. Il faudrait analyser le corps des documents et les révisions chiffrées, puis vérifier si cela apporte quelque chose **conditionnellement à l'Oracle**.

Deux PDF officiels ont été lus comme contrôle manuel de l'extractibilité : le [communiqué Valeo du 29 février 2024](https://fr.ftp.opendatasoft.com/datadila/INFOFI/MKW/2024/02/FCMKW116621_20240229.pdf) comporte une table « objectifs 2025 précédents / nouveaux » ; malgré un titre optimiste, l'objectif de chiffre d'affaires 2025 passe d'environ 27,5 Md€ à 24,5–25,5 Md€. Le [communiqué Ubisoft du 25 septembre 2024](https://fr.ftp.opendatasoft.com/datadila/INFOFI/MKW/2024/09/FCMKW133936_20240925.pdf) expose la révision des objectifs et des ventes décevantes, mais dans le POC le titre est dans le top tail H20 après l'entrée hypothétique du lendemain. Ces cas ne prouvent rien statistiquement ; ils montrent qu'il faut comparer **ancienne prévision, nouvelle prévision et attentes déjà incorporées dans le prix**, pas classer le seul titre du document en positif/négatif.

Point bloquant de qualité : des requêtes identiques de l'API DILA ont fourni des nombres historiques différents pendant l'audit (par exemple 305 à 385 lignes exportées pour un même ISIN/période ; le compteur `records` a aussi varié). Les chiffres ci-dessus sont exploratoires ; toute validation sérieuse exige de figer un export brut, ses empreintes et sa date de collecte, puis d'expliquer les écarts avant d'entraîner.

**Décision du POC gratuit** : pas de politique LONG/SHORT issue de ces titres d'annonces. Poursuivre uniquement si l'on accepte un POC limité d'extraction des tableaux de guidance, avec vérification humaine des paires ancienne/nouvelle et une date de publication réellement disponible ; sinon suspendre la piste et ne pas acheter EODHD pour elle seule.

**Premier palier réalisé le 17/09/2026** : [POC de faisabilité sur 120 émetteurs et 24 PDF](poc_guidance_120_emetteurs.md). Les exports ont été figés et un contrôle répété sur 20 ISIN n'a montré aucune dérive à court terme. Sur les 12 PDF présélectionnés par titre comme possibles révisions, quatre seulement contiennent une paire chiffrée ancienne/nouvelle directement comparable. Il n'y a toujours ni feature PIT validée ni test D1/D10 ; ce résultat ne justifie pas encore un essai sur 500 titres.

## 4. Ordre de livraison recommandé

**Phase A — recherche sans risque de régression US** : instrument master et univers FR en staging, prix/AMF/DILA historisés, contrôle PIT, labels France, POC Oracle/D1-D10 et coûts papier. Pas de switch live ni modification des ordres Alpaca.

**Phase B — moteur multi-marchés** si la recherche passe : propagation `market/instrument_id/currency` dans IHM, CLI, tables, artefacts et diagnostics ; calendriers/benchmarks/features/risk/costs par marché ; migrations progressives avec tests US inchangés et tests FR.

**Phase C — paper puis live** : contrat d'un courtier exécutant XPAR confirmé, essai de cotations et ordres, réconciliation/kill switch/protections, règles de prêt pour shorts et coût/taxe effectif. Par défaut France LONG-only tant que le short n'est pas validé.

Critère de décision : **l'intégration technique est possible, mais la disponibilité gratuite de la seule série AMF ne démontre pas une meilleure séparabilité D1/D10 qu'aux États-Unis**. Ne pas engager la refonte live avant un POC historique France complet et économiquement net.
