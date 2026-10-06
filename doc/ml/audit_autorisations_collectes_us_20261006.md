# US — Audit des autorisations de collecte des batchs

Date de vérification : 6 octobre 2026. Périmètre : catalogue `US_EQ` effectivement présenté par la page Batch, fournisseurs réellement appelés et conditions publiques officielles.

## 1. Conclusion et limites

À l'ouverture de l'audit, le catalogue contenait **25 batchs US : 20 activés et 5 désactivés**. Les 25 ont été examinés, y compris les traitements locaux et sauvegardes. Le tableau ci-dessous conserve cette photographie initiale ; les blocages appliqués après GO sont décrits en section 14.

Il n'est pas possible de certifier que toutes les collectes actuelles sont autorisées pour tous les usages futurs d'Alpha Trade. Les réserves les plus fortes concernent :

1. `analyst_snapshot_collection` : collecte automatisée Yahoo via yfinance ;
2. la branche Yahoo de `market_cap_sync` ;
3. `fred_alfred_vintage_sync` : archivage API et usage ML ;
4. `finra_short_volume_sync` : constitution de base et usage prédictif/ML.

**Recommandation conservatoire : suspendre ces usages tant qu'une permission adaptée n'est pas établie.** Pour `market_cap_sync`, l'objectif est de conserver SEC et les fournisseurs autorisés, pas d'abandonner la capitalisation : le code exige actuellement l'ordre Yahoo puis Finnhub, donc une adaptation est nécessaire avant de supprimer seulement Yahoo.

Business Quant appelle une vérification du contrat et des droits de classification. Nasdaq et OCC nécessitent une clarification de la portée des permissions publiques pour notre archivage automatisé. Alpaca et SEC disposent de voies de collecte documentées ; cela reste conditionné aux droits du compte, aux flux et aux modalités d'accès.

Cet audit n'est ni une consultation juridique, ni un constat d'infraction. Les contrats particuliers acceptés par l'utilisateur peuvent modifier l'analyse. Ils n'ont pas été consultés. Les conditions web peuvent évoluer : cette photographie ne prouve pas leur contenu lors des anciennes collectes.

**Aucun batch US n'a été désactivé pendant cet audit. Aucun collecteur, entraînement ou backtest n'a été lancé. Aucun code, configuration, tâche Windows ou enregistrement SQL n'a été modifié. Seul ce document a été créé.**

## 2. Méthode et code examiné

L'inventaire provient de `ihm.services.batch_management.load_market_batch_specs("US_EQ")`, pas d'une déduction à partir des noms. Les libellés `ACTIVE` et `RESEARCH_ONLY` sont des états techniques, pas des licences.

Sources locales principales :

- `batch.yaml`, `ihm/services/batch_management.py` ;
- `service/forward_pit/batch.py`, handlers et persistance ;
- `service/forward_pit/options_delayed.py` ;
- `scripts/windows/earnings_calendar_launcher.ps1` et `dataIntegrityEngine/sync_earnings_calendar.py` ;
- `dataIntegrityEngine/sync_latest_quotes.py` ;
- `analyst_research/collector.py` et `database/repositories/analyst_snapshots.py` ;
- `modelFactory/fundamental_features.py`, `service/yahoo/clientYahooFinance.py` ;
- `database/sql/forward_pit/forward_pit_tables.sql`.

Les états suivants sont des conclusions d'audit, **non des nouveaux statuts appliqués dans la configuration** :

- **SUSPENSION RECOMMANDÉE** : restriction explicite pertinente, sans permission particulière établie ;
- **CONTRAT À QUALIFIER** : accès ou licence documentés, mais couverture exacte de notre usage non démontrée ;
- **MAINTIEN SOUS CONDITIONS** : pas de motif identifié imposant un arrêt général, sous les conditions précisées ;
- **LOCAL** : pas de nouvelle collecte externe ; droits des données entrantes toujours applicables ;
- **INACTIF** : désactivé dans le catalogue, à ne pas réactiver sur la seule foi de sa disponibilité technique.

## 3. Inventaire complet

Les écritures de supervision dans `pit_collection_runs` et, pour les collecteurs concernés, `pit_raw_payloads`, s'ajoutent aux tables métier indiquées.

| Batch | Activé | Source réelle / nature | Stockage ou sortie principale | Conclusion |
|---|---|---|---|---|
| `daily_bars_sync` | Oui | Business Quant `/quotes`, EOD brut | `stock_bars_daily_versions` | CONTRAT À QUALIFIER : plan, archivage et usage interne |
| `security_master_snapshot` | Oui | Nasdaq `nasdaqlisted.txt`/`otherlisted.txt`, puis Business Quant `/universe` aux jours configurés | `security_master_snapshots`, `security_master_changes` | CONTRAT À QUALIFIER : Nasdaq et classification BQ |
| `corporate_actions_sync` | Oui | Business Quant `/corporate_actions` et fournisseur Alpaca corporate actions | `corporate_action_source_events` | CONTRAT À QUALIFIER pour BQ ; distinguer la branche Alpaca |
| `market_cap_sync` | Oui | SEC primaire → Yahoo/yfinance → Finnhub | fondamentaux et capitalisation, couverture par fournisseur | SUSPENSION RECOMMANDÉE de Yahoo ; adapter le composite |
| `latest_quotes_sync` | Oui | Collecteur historique Alpaca IEX, fenêtre de dates | snapshots de quotes et audit de synchronisation | MAINTIEN SOUS CONDITIONS Alpaca ; pas Yahoo dans cette route historique |
| `sec_edgar_incremental` | Oui | SEC index EDGAR, document primaire, annexes optionnelles | `sec_filing_raw`, `sec_filing_documents` | MAINTIEN SOUS CONDITIONS SEC, sans redistribution automatique des documents |
| `earnings_calendar_sync` | Oui | Finnhub, choix par défaut du CLI appelé par le launcher | calendrier de publications | MAINTIEN SOUS CONDITIONS : personnel, droits du plan, conservation |
| `analyst_snapshot_collection` | Oui | Yahoo via yfinance : estimations, tendances/révisions EPS, objectifs, recommandations | tables analystes gérées par `AnalystSnapshotRepository` | SUSPENSION RECOMMANDÉE sans permission automatisation Yahoo |
| `borrow_status_snapshot` | Oui | Alpaca `/v2/assets` | `stock_borrow_status_snapshots` | MAINTIEN SOUS CONDITIONS ; disponibilité broker, pas taux de prêt |
| `finra_short_volume_sync` | Oui | Fichiers publics FINRA CNMS quotidiens | `stock_short_volume_daily` | SUSPENSION RECOMMANDÉE pour l'archivage/ML prévu |
| `oracle_options_indicative_snapshot` | Oui | Contrats Alpaca et snapshots options `indicative`, avec cours IEX | `stock_option_snapshots` | MAINTIEN SOUS CONDITIONS ; données indicatives, pas NBBO officiel |
| `options_delayed_bars_sync` | Oui | Contrats Alpaca, cours IEX, historique options après délai | `stock_option_contract_versions`, `stock_option_bars_delayed` | MAINTIEN SOUS CONDITIONS ; provenance conservée `UNVERIFIED_OPRA` |
| `option_contract_adjustment_sync` | Oui | RSS Information Memos OCC ; métadonnées seulement | `option_contract_adjustments` et réponse brute | CONTRAT À QUALIFIER : RSS spécifique / conditions générales |
| `oracle_opening_window_sync` | Oui | Historique Alpaca SIP retardé, fenêtres d'ouverture | `stock_opening_window_bars`, `stock_opening_window_bar_versions` | MAINTIEN SOUS CONDITIONS ; respecter entitlement et délai |
| `fred_alfred_vintage_sync` | Oui | API FRED observations / vintage du jour | `macro_vintage_observations` et payloads | SUSPENSION RECOMMANDÉE sans permission couvrant stockage et ML |
| `sec_corporate_events_normalize` | Oui | Extraction locale des documents SEC déjà stockés | `sec_corporate_events` | LOCAL ; pas de nouveau fournisseur |
| `sec_institutional_ownership_normalize` | Oui | Lecture locale des dépôts SEC | `sec_ownership_snapshots` | LOCAL ; permissions des documents d'origine à conserver |
| `ml_artifacts_backup` | Oui | Fichiers locaux des modèles | sauvegardes d'artefacts | LOCAL ; ne crée pas de nouveaux droits sur données embarquées |
| `db_core_backup` | Oui | MySQL local, hors `news_raw` | sauvegarde DB | LOCAL ; peut répliquer les données à conservation restreinte |
| `db_news_raw_backup` | Oui | MySQL local, `news_raw` seulement | sauvegarde dédiée | LOCAL ; cet audit ne valide pas chaque origine historique des news |
| `pit_data_quality_daily` | Non | SQL de contrôles locaux | `pit_data_quality_metrics`, `pit_data_quality_issues` | INACTIF / LOCAL, pas de nouvelle collecte |
| `business_quant_analyst_snapshot` | Non | Ancien candidat Business Quant, remplacé dans le catalogue | `stock_analyst_consensus_snapshots` si réactivé | INACTIF ; ne pas réactiver sans qualification du plan |
| `securities_lending_sync` | Non | Aucun fournisseur validé | aucune collecte active qualifiée | INACTIF ; conserver le blocage fournisseur |
| `official_options_nbbo_sync` | Non | Aucune source gratuite NBBO officielle validée | aucune collecte active qualifiée | INACTIF ; ne pas assimiler les barres/indicatif à ce besoin |
| `auction_imbalance_sync` | Non | Aucun flux officiel gratuit qualifié | aucune collecte active qualifiée | INACTIF ; ancien POC distinct du batch quotidien |

## 4. Yahoo : deux chemins actifs, pas seulement les analystes

Les [conditions officielles Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001), rubrique de conduite, interdisent l'accès ou la collecte automatisés sans permission préalable expresse. Une licence de bibliothèque, une API non documentée ou le caractère personnel de la recherche ne constituent pas cette permission.

Constats dans le projet :

- `analyst_research/collector.py` importe directement yfinance ;
- `service/yahoo/clientYahooFinance.py` utilise également yfinance pour les fondamentaux ;
- `market_cap_sync` appelle cette branche pour les symboles non couverts par SEC ;
- le handler refuse une liste de fallbacks différente de `yahoo_finance,finnhub`.

L'usage Yahoo n'est donc pas une hypothèse fondée sur un libellé. Il existe dans deux chemins exécutables. Une adaptation future devrait permettre SEC seul ou SEC → Finnhub, avec contrôle de couverture, plutôt que tronquer les listes ou masquer les erreurs.

Attention à `latest_quotes_sync` : le module sous-jacent sait utiliser Yahoo en mode « latest » sans dates, mais le batch fournit une fenêtre historique. Cette route utilise les quotes historiques Alpaca. La simple présence d'un import Yahoo ne suffit pas à condamner ce batch.

## 5. FRED/ALFRED : la gratuité n'autorise pas notre archivage ML

Les [conditions FRED actuelles](https://fred.stlouisfed.org/legal/), sections « Prohibitions for FRED API », points **k et l**, restreignent expressément l'usage lié au développement/entraînement ML et le stockage, cache, archivage ou incorporation du contenu dans une base. La clé API ne constitue pas une dérogation. Les droits des séries tierces restent en outre distincts.

Notre handler stocke réponses brutes et observations dans `macro_vintage_observations` : la réserve existe donc dès la collecte, pas seulement lors d'un futur entraînement. La recherche des références Python à cette table n'a pas montré un raccordement direct actuel aux entraîneurs : **ne pas prétendre que tous les modèles actuels ont déjà utilisé cette nouvelle table**.

À obtenir : permission écrite pour notre archivage prospectif et analyse/ML, ou sources primaires adaptées. BLS, BEA et Federal Reserve peuvent être étudiés séparément ; cela ne résout pas automatiquement les séries CBOE/ICE. Ne supprimer aucune archive automatiquement avant examen des obligations applicables.

## 6. FINRA : restriction prédictive explicite

Le [catalogue Short Sale Volume](https://www.finra.org/finra-data/browse-catalog/short-sale-volume) annonce un accès gratuit non commercial, mais renvoie aux [conditions FINRA](https://www.finra.org/terms-of-use). Leurs restrictions **d, e et m** concernent respectivement les bases sauf permission expresse, la copie en masse/extraction, et le ML/analytics prédictif, notamment la prédiction de transactions de portefeuille. Le téléchargement public ne démontre pas une dérogation couvrant notre usage.

Le handler télécharge les fichiers `CNMSshvolYYYYMMDD.txt`, conserve les réponses et peuple `stock_short_volume_daily`. L'objectif déclaré est de construire des données utiles à la direction : il faut une permission adaptée ou un contrat distinct. Un éventuel changement vers l'API FINRA doit lui-même être licencié ; ce n'est pas une solution automatique.

Cette recommandation est contractuelle, indépendante du résultat historique NO-GO de cette famille de features. Ces volumes ne sont pas du short interest ni une mesure de coût/utilisation du prêt.

## 7. Business Quant : vérifier la licence effective

Les [conditions Business Quant](https://businessquant.com/terms-of-use) encadrent l'usage interne pendant l'abonnement et la redistribution ; le plan gratuit est présenté comme une évaluation avant achat. Elles traitent séparément les classifications sectorielles/industrielles et limitent les usages concurrents. Elles ne constituent pas une interdiction générale de tout ML interne. La [licence de classification](https://businessquant.com/industry-classification) doit être vérifiée lorsque ces champs sont conservés.

Trois chemins actifs sont concernés :

- `daily_bars_sync` collecte EOD brut ;
- `corporate_actions_sync` collecte les événements de cette source en plus d'Alpaca ;
- `security_master_snapshot` importe son univers, notamment les champs `sector` et `industry` et les payloads bruts.

À demander au fournisseur : nom du plan, droits de stockage historique/PIT et ML interne, durée de conservation, sort des archives après abonnement, droit exact sur les champs de classification reçus. Si l'accès actuel est seulement une évaluation gratuite, ne pas promouvoir ces branches en pipeline permanent sans confirmation. Le secret API n'a pas été lu et ne prouverait de toute façon pas la licence.

La branche Alpaca de corporate actions et la branche Nasdaq du security master sont séparables techniquement. Pour Nasdaq, résoudre également la réserve ci-dessous. `daily_bars_sync` refuse actuellement `canonical_upsert` : sa table de versions RAW n'est pas un remplacement complet de `stock_bars_daily` ajustée/EODHD.

## 8. Nasdaq : téléchargement documenté, portée d'archivage à préciser

Les [définitions du Symbol Directory](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs) et l'[aide officielle](https://www.nasdaqtrader.com/Trader.aspx?id=help) documentent les fichiers quotidiens. Les [conditions générales Nasdaq Trader](https://nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain) restreignent la copie et prévoient des permissions spécifiques. La [page Symbol Lookup](https://nasdaqtrader.com/trader.aspx?id=symbollookup) contient une exception pour des catégories « Events Data » : **ne pas l'étendre automatiquement à tous les fichiers du répertoire**.

Le code stocke des snapshots quotidiens du référentiel et leurs changements. Une confirmation portant précisément sur `nasdaqlisted.txt` et `otherlisted.txt`, leur archivage multi-date et l'usage interne automatisé est préférable à une certification générale. Il ne collecte pas le Nasdaq Fund Network : ne pas lui appliquer mécaniquement les clauses propres aux fonds.

Conclusion : clarification requise ; avec l'exigence utilisateur d'autorisation démontrée avant collecte, suspendre cette branche par précaution jusqu'à réponse, sans la qualifier pour autant d'illégale.

## 9. OCC : distinguer RSS, PDFs et licence de données

Les [conditions spécifiques RSS OCC](https://www.theocc.com/specialpages/legal/occ-rss-feeds) permettent un usage non commercial, interdisent modification/redistribution du flux sans accord, et incorporent les [conditions générales](https://www.theocc.com/specialpages/legal/terms-and-conditions). Celles-ci restreignent notamment les systèmes automatisés. Leur articulation avec un agrégateur RSS et une base de métadonnées dérivées mérite une confirmation ; elle ne permet pas de déclarer tout scraping OCC autorisé.

Le collecteur actuel ne télécharge que le RSS `infomemo-rss` et parse les métadonnées de Contract Adjustment. Il conserve `RSS_METADATA_ONLY_CLOUDFLARE_BLOCKED` : ce n'est pas une récupération exhaustive des documents et il ne faut pas contourner le blocage des pages de détail. La licence des services de données payants OCC ne doit pas être transposée sans preuve à ce RSS.

Recommandation : permission ciblée sur collecte, conservation et extraction interne ; pas de promotion production/ML ni d'extension PDF sur une simple présomption.

## 10. Alpaca : voie API documentée, droits du compte à conserver

La [documentation Market Data](https://docs.alpaca.markets/us/docs/about-market-data-api) décrit Basic : IEX actions, options indicatives en temps réel et historique avec restriction des quinze dernières minutes. Les droits API effectifs et les [accords/disclosures](https://alpaca.markets/disclosures) acceptés par le compte doivent couvrir l'usage privé, la conservation et les flux. La redistribution ou un service à des tiers nécessite une qualification différente.

Le PDF générique [Terms and Conditions](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf) comporte une clause territoriale US alors que le [support officiel](https://alpaca.markets/support/is-alpaca-available-outside-the-us) décrit des comptes internationaux : ne pas conclure à une interdiction depuis la France sans identifier le contrat effectivement applicable au compte.

Constats techniques, distincts des licences :

- `latest_quotes_sync` récupère l'historique IEX ; sa couverture limitée ne devient pas un NBBO consolidé ;
- `borrow_status_snapshot` récupère les attributs des assets du courtier, pas un flux securities lending complet ;
- `oracle_options_indicative_snapshot` conserve un feed explicitement indicatif ;
- `options_delayed_bars_sync` impose au moins 16 minutes après clôture et conserve la provenance non vérifiée des barres ;
- `oracle_opening_window_sync` impose SIP retardé ; une réponse refusée ne doit pas être contournée ;
- `corporate_actions_sync` passe aussi par le fournisseur Alpaca existant.

Pas de recommandation de suspendre toutes les branches Alpaca sur le seul motif qu'elles sont gratuites. Archiver les accords réellement acceptés et les entitlements est néanmoins nécessaire avant validation juridique définitive.

## 11. SEC et Finnhub

### SEC

La [politique SEC Developer Resources](https://www.sec.gov/about/developer-resources) prévoit le téléchargement automatisé identifié, avec une limite totale de 10 requêtes/seconde par utilisateur, toutes machines confondues. Les index et accès structurés sont documentés. Ce droit d'accès n'est pas une licence générale de redistribution des pièces produites par les émetteurs.

Le batch applique un User-Agent configurable et des pauses. Le respect agrégé reste à vérifier si `sec_edgar_incremental`, les fondamentaux et d'autres traitements SEC sont exécutés en parallèle. Les documents primaires et annexes `EX-99.*` doivent conserver origine et dates ; leur analyse interne ne doit pas être assimilée à une autorisation de publier les documents complets.

Les deux normalisations SEC sont locales ; pas de motif de suspension générale identifié dans cet audit.

### Finnhub

Les [conditions Finnhub](https://finnhub.io/terms-of-service) limitent les plans ordinaires à l'usage personnel sauf accord contraire, restreignent le partage des données/résultats dérivés et prévoient la suppression des données à la fin de l'abonnement correspondant. Un accès professionnel même interne doit être expressément couvert.

`earnings_calendar_sync` appelle le CLI sans `--provider` : le défaut est **Finnhub**, pas SEC. `market_cap_sync` conserve Finnhub en dernier fallback. Aucun motif ne justifie un arrêt général pour une utilisation personnelle couverte ; il faut toutefois préparer le traitement de fin de droits, y compris dumps, payloads et copies de restauration. Le paramètre de conservation des sauvegardes n'est pas une licence de conservation fournisseur.

## 12. Actions proposées, sans application dans cet audit

### Avant poursuite des collectes à fortes réserves

1. Décider de la suspension Yahoo, FRED et FINRA ; ne pas remplacer les droits manquants par une étiquette de quarantaine.
2. Permettre un composite capitalisation sans Yahoo, avec couverture mesurée et sans modifier silencieusement la hiérarchie.
3. Qualifier le contrat Business Quant et les classifications ; conserver uniquement les branches/familles couvertes.
4. Demander Nasdaq et OCC une autorisation ciblée d'archivage automatisé, si l'on exige une preuve positive.

### Registre des permissions à constituer

Pour chaque source : fournisseur, endpoint/famille, contrat et version, compte/plan sans secret, périmètre personnel/professionnel, collecte automatisée, stockage, durée, analyse/ML, dérivés, redistribution, attribution et fin de droits. Un fichier de preuve contractuelle ne doit jamais contenir token ou mot de passe.

### Sauvegardes et données déjà collectées

Ne pas supprimer toutes les archives indistinctement. Identifier les enregistrements par source et les usages de modèles avant toute décision de retrait. Prévoir la propagation des obligations aux restaurations : une sauvegarde ne doit pas réintroduire des données dont les droits ont expiré. Cet audit ne décide ni la licéité historique de chaque copie ni une purge.

### Informations IHM à corriger après GO

Les descriptions devraient expliciter fournisseur réel et droits non qualifiés. En particulier : earnings = Finnhub par défaut ; SEC incremental = SEC ; Yahoo = pas validé par yfinance ; FRED/FINRA = pas autorisés pour tout usage prédictif ; OCC = RSS partiel ; Business Quant = dépend du contrat, pas « gratuit donc libre ».

## 13. Ce que cet audit ne couvre pas

Il ne certifie pas tous les imports manuels, toutes les anciennes news, les fournisseurs historiques des tables, ni chaque URL utilisée par les chercheurs hors catalogue Batch. EODHD, les scripts ponctuels et les données incorporées dans des modèles anciens demandent leur propre lineage si l'on veut un audit exhaustif de toute l'application.

Documents connexes : [audit FR](../fr/audit_autorisations_collectes_20261006.md), [audit CN](../cn/audit_autorisations_collectes_20261006.md).

## 14. Décision appliquée après GO — 6 octobre 2026

L'utilisateur a demandé le blocage des trois collecteurs et l'ajout de commentaires. Dans `batch.yaml`, les trois entrées suivantes ont désormais `enabled: false`, avec motifs visibles dans l'IHM et étapes de déblocage :

| Batch | Statut de blocage |
|---|---|
| `analyst_snapshot_collection` | `BLOCKED_YAHOO_AUTOMATED_ACCESS` |
| `fred_alfred_vintage_sync` | `BLOCKED_FRED_ARCHIVE_ML_RIGHTS` |
| `finra_short_volume_sync` | `BLOCKED_FINRA_PREDICTIVE_USE` |

Le catalogue passe à **17 activés / 8 désactivés**. Le blocage est contrôlé dans l'IHM, les launchers Windows et les points d'entrée CLI des collecteurs : changer seulement `enabled` ou utiliser `-Force` ne suffit pas. Pour lever le blocage après validation de droits, modifier explicitement le statut et l'activation.

Repère IHM commun aux trois marchés : les huit collecteurs bloqués pour droits ou par prudence portent le préfixe **⛔ ⚖️ DROITS / PRUDENCE**, avec titre gras de couleur normale (noir en thème clair), indépendamment du dernier résultat d'exécution. À la demande de l'utilisateur, ce blocage n'impose pas de titre rouge ; le rouge reste utilisé pour les échecs des autres batchs. Un avertissement interne rappelle de ne pas relancer sans validation. Les blocages techniques et d'absence de fournisseur ne sont pas assimilés à cette catégorie. Les motifs et conditions de déblocage restent affichés sous le titre.

Les tâches installées n'ont pas été supprimées ni modifiées dans Windows ; leur launcher saute la collecte. Aucune donnée existante n'a été supprimée et aucun batch en cours n'a été interrompu. Les fonctions internes de collecte restent du code disponible : ce garde-fou n'est pas un contrôle d'accès contre un développeur qui les appellerait directement.

**`market_cap_sync` n'est pas inclus dans ces trois blocages et reste inchangé. Sa branche Yahoo reste une réserve ouverte : une adaptation SEC → Finnhub ou une permission Yahoo est encore nécessaire.** Ne pas interpréter les trois désactivations comme une résolution de toutes les réserves de l'audit.

Tests dédiés : `tests/test_us_batch_rights_blocks.py` (visibilité, activation seule, CLI sans SQL/fournisseur et garde-fous Windows).

## 15. Purge demandée après blocage — 6 octobre 2026

L'utilisateur a demandé de retirer les données des collecteurs bloqués, puis précisé de **laisser CN intact** et de supprimer les fichiers de quarantaine FR.

La purge US est limitée à Yahoo analystes (`provider=yahoo`), FINRA CNMS (`provider=finra_cnms`) et FRED (`provider=fred_alfred`), ainsi qu'aux payloads et journaux correspondants dans les tables partagées. Les autres sources restent intactes. Le script `scripts/purge_blocked_us_collectors.py` prévisualise par défaut ; `--execute` exige les collecteurs bloqués, vérifie la base `alpha_trade`, refuse les clés étrangères entrantes non qualifiées et supprime par transactions de 10 000 lignes. Le rapport d'exécution sans payload est dans `artifacts/operations/blocked_collectors_purge` ; son champ `complete` et les compteurs après purge font foi.

FR : les 3 494 fichiers du répertoire `artifacts/fr/operations/fr_fundamentals_sync/quarantine` ont été supprimés. Après confirmation explicite supplémentaire de l'utilisateur, les 629 fichiers des observations/checkpoints INPI et des dossiers Yahoo `daily_observations`, `days` et `poc` ont également été supprimés : **4 123 fichiers au total**. Le rapport `fr-20261006.json` énumère les chemins traités. Les correspondances d'identité `mapping` et le compteur `request_quota.json` sont conservés. **Les anciennes archives et checkpoints ne sont plus disponibles ; ne pas considérer la collecte comme complète avant une nouvelle qualification autorisée.** Les collecteurs restent bloqués.

Aucun modèle, aucune donnée CN et aucune sauvegarde préexistante n'ont été supprimés. Aucune nouvelle copie des données purgées n'a été créée. Les sauvegardes existantes peuvent encore contenir ces données ; ce nettoyage n'est donc pas une certification d'effacement de toutes les copies historiques. Une restauration devra respecter les exclusions de sources.
