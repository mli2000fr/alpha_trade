# Catalogue opérationnel des batchs — 10 octobre 2026

Mise à jour du 18 octobre : **huit collecteurs utilisent l'export fixe
`config/univers_batch/stock_bars_daily.txt`** : `eodhd_consensus_snapshot`,
`eodhd_ipo_calendar_sync`, `market_cap_sync`, `borrow_status_snapshot`,
`eodhd_news_ingestion_sync`, `options_delayed_bars_sync`,
`oracle_options_indicative_snapshot` et `oracle_opening_window_sync`.
Il contient 13 105 symboles et n'est pas régénéré automatiquement depuis SQL.
Le consensus conserve son contrôle de couverture de 95 % sur le fichier tradable.
Les IPO restent filtrées après réception du calendrier marché entier.
`us_pipeline` et les autres batchs restent inchangés. Historique, horaires,
secours, notifications et budgets conservés ; les news peuvent être incomplètes
sur ce périmètre élargi avec les plafonds actuels.

Ajout du 16 octobre : **`eodhd_news_ingestion_sync`**, P1, activé et tâche Windows
installée : 20h30 Paris tous les jours ; univers actuel étendu précisé ci-dessus.
Ingestion/archives uniquement, sans FinBERT/LLM ; workflow et scoring du vendredi
inchangés. [Fonctionnement, smoke réel et limites](eodhd_news_ingestion_sync.md).

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Inventaire rapproché de `ihm/services/batch_management.py`, des trois YAML,
des runners et des lanceurs. « Actif » décrit la configuration ; cela ne
prouve ni installation Windows, ni réussite du dernier run, ni GO ML.
Les commandes de la carte IHM font autorité pour le launcher et le catalogue.

Ajout du 15 octobre : **`fr_consensus_snapshot`** utilise désormais EODHD, pas
Yahoo ; accès et stockage FR testés, deux tables dédiées dans `alpha_trade_fr`.
Statut `ACTIVE_RESEARCH`, `enabled:true` sur demande utilisateur le 15 octobre,
20h Paris tous les jours, notifications FR communes. Aucun batch US modifié.
[Champs, reprise, compteurs et limites PIT](../fr/consensus_eodhd_collecte_quotidienne.md).

Ajout du 11 octobre : **`eodhd_consensus_snapshot`** (P1), activé dans `batch.yaml`,
table dédiée EODHD, principal 22h15 Paris / secours conditionnel 4h15.
Accès vérifié HTTP 200 après souscription Calendar & News ; aucune table Yahoo
utilisée. [Champs, SQL 0099, activation et limites PIT](eodhd_consensus_snapshot.md).

Ajout du 11 octobre : **`eodhd_ipo_calendar_sync`** (P2), activé et tâche Windows
`AlphaTrade-EodhdIpoCalendarSync` installée. Principal 1h / secours conditionnel
5h Paris, tous les jours ; tables dédiées créées, backfill mensuel 2016–2026 lancé.
[Périmètre, champs, reprise et limites PIT](eodhd_ipo_calendar.md).

## US — batch.yaml, 26 entrées, 17 actives

| Batch | État actuel | Fournisseur / stockage principal |
| --- | --- | --- |
| us_pipeline | Actif PAPER | Workflow 1–14 configuré, tables métier US ; détail ci-dessous |
| daily_bars_sync | Actif | Business Quant → pit_raw_payloads, stock_bars_daily_versions ; pas import EODHD canonique |
| security_master_snapshot | Actif | Nasdaq directory / Business Quant → security_master_snapshots, security_master_changes |
| corporate_actions_sync | Actif | Business Quant / Alpaca → corporate_action_source_events ; distinct de l'application portefeuille |
| sec_edgar_incremental | Actif | SEC → sec_filing_raw, sec_filing_documents ; primaire et annexes EX-99 selon option |
| market_cap_sync | Actif | Faits SEC/Finnhub → stock_fundamentals_daily ; capitalisations SEC × clôture qualifiée puis Finnhub → stock_market_cap_daily ; mesures séparées grand univers/tradable, sans Yahoo |
| borrow_status_snapshot | Actif | Alpaca → stock_borrow_status_snapshots ; disponibilité indicative ETB, pas coût de prêt complet |
| oracle_options_indicative_snapshot | Recherche active | Alpaca → stock_option_snapshots ; données indicatives, pas NBBO officiel certifié |
| options_delayed_bars_sync | Recherche active | Alpaca → stock_option_contract_versions, stock_option_bars_delayed ; pas quotes NBBO |
| option_contract_adjustment_sync | Recherche active | OCC → option_contract_adjustments, stock_option_contract_versions ; mémos à qualifier |
| oracle_opening_window_sync | Recherche active | Alpaca IEX → stock_opening_window_bars et versions ; volume non consolidé |
| sec_corporate_events_normalize | Actif | Lecture SEC locale → sec_corporate_events |
| sec_institutional_ownership_normalize | Actif | Lecture SEC locale → sec_ownership_snapshots |
| ml_artifacts_backup | Actif | Fichiers → backups/ml ; keep=5 configuré |
| db_core_backup | Actif | alpha_trade sauf news_raw → backups/db ; keep=5 |
| db_news_raw_backup | Actif | news_raw seule → backups/db ; keep=3, chaque dimanche 20:00 Paris |
| latest_quotes_sync | Désactivé, intégré | Étape 4 du pipeline, quotes Alpaca, J−7/J |
| earnings_calendar_sync | Désactivé, intégré | Étape 5 du pipeline, Finnhub configuré, J−7/J+30 |
| analyst_snapshot_collection | ⛔ Droits/prudence, désactivé | BLOCKED_YAHOO_AUTOMATED_ACCESS ; nouvelle désactivation utilisateur le 10/10 ; données conservées, aucun nouvel appel ; voir doc/ml/yahoo_analyst_pit.md |
| business_quant_analyst_snapshot | Désactivé, remplacé | REPLACED_BY_YAHOO ; collecteur Yahoo remplaçant lui-même désactivé, pas de droit Yahoo présumé |
| fred_alfred_vintage_sync | ⛔ Droits/prudence | BLOCKED_FRED_ARCHIVE_ML_RIGHTS |
| public_macro_snapshot_sync | Recherche active, 23:15 Paris lun–ven | BLS + Federal Reserve Board H15 → macro_public_observation_versions ; première tranche du remplacement public, pas de raccordement modèle automatique |
| finra_short_volume_sync | ⛔ Droits/prudence | BLOCKED_FINRA_PREDICTIVE_USE |
| securities_lending_sync | Fournisseur manquant | PENDING_PROVIDER ; pas de connecteur gratuit qualifié pour le besoin complet |
| official_options_nbbo_sync | Source manquante | BLOCKED_FREE_NO_NBBO_SOURCE ; bars/mémos partiels ne fournissent pas le NBBO |
| auction_imbalance_sync | Source manquante | BLOCKED_NO_FREE_OFFICIAL_FEED ; pas un flux exploitable simulé |

La plupart des nouveaux batchs US journalisent dans pit_collection_runs et
pit_raw_payloads, en plus des tables métier listées. Le RAW peut croître à
chaque observation sans doublon métier. Les noms de fournisseur absents du YAML
ne rendent pas une normalisation locale indépendante de sa source amont SEC.

La collecte de capitalisation n'impose pas un filtre : `config.yaml/market_cap`
est actuellement en **liquidity_only**. Depuis le 18/10/2026, le batch de
capitalisation et le publieur ne sélectionnent plus Yahoo : SEC puis Finnhub.
Le retrait n'autorise aucune autre collecte Yahoo encore présente dans les
anciens outils. [Mesure de couverture et limites](retrait_yahoo_capitalisations_pipeline_20261018.md).

### us_pipeline

Horaire : 22:45 Paris, séances US lundi–vendredi, après clôture ; date de séance
figée même après minuit. Sélection fonctionnelle dans `config.yaml/us_pipeline`,
planning/univers/fenêtres dans `batch.yaml/us_pipeline`.

- lundi–jeudi : 1–7, 9–14 ; vendredi : 1–14 ; T1 exclu ;
- univers commun : config/univers_batch/univers_filtred_tradable.txt ;
- mode PAPER et compte default ; LIVE interdit ; arrêt au premier échec ;
- options fraîches, pas de reprise de la session IHM : GPT désactivé dans ces
  options du scheduler même si la case IHM est cochée par défaut ;
- import EODHD cible J, attend la publication et exige sa couverture ;
- watcher sain réutilisé ou démarré avant étape 12 PAPER ; reste actif après le run ;
- 13 synchronise les corporate actions, 14 les applique au ledger ; compte
  paper exigé même si execution_mode=simulate.

[Contrat complet](us_pipeline.md). Ne pas réactiver quotes/earnings autonomes
pour obtenir les mêmes collectes deux fois sans besoin explicite.

## CN — deux catalogues conservés, 10 entrées visibles, 3 actives

| Batch | Catalogue | État / effet actuel |
| --- | --- | --- |
| cn_db_backup | batch_cn.yaml | Actif ; alpha_trade_cn → backups/cn/db, keep=3 |
| cn_daily_quality_17c | batch_cn.yaml | Actif, lecture seule ; bloquant tant que D9 requis est désactivé |
| cn_dragon_tiger_daily_match | batch.yaml | Recherche active, artefacts D10 ; ne peut inventer D6/Oracle manquants |
| cn_oracle_prospective_daily | batch.yaml | ⛔ BLOCKED_BAOSTOCK_RIGHTS ; collecte/promotion D9 arrêtée |
| cn_dragon_tiger_after_close | batch.yaml | ⛔ BLOCKED_SSE_SZSE_AUTOMATION |
| cn_dragon_tiger_before_open | batch.yaml | ⛔ BLOCKED_SSE_SZSE_AUTOMATION |
| cn_daily_market_data_sync | batch_cn.yaml | Désactivé, doublon D9 ; ne pas ajouter un second propriétaire canonique |
| cn_historical_backfill | batch_cn.yaml | Désactivé, backfill manuel ; pas une collecte quotidienne raccordée |
| cn_akshare_enrichment | batch_cn.yaml | Désactivé/non qualifié ; choisir famille et droits avant un POC dédié |
| cn_tushare_optional | batch_cn.yaml | Désactivé/non qualifié ; fournisseur optionnel, pas une dépendance active |

Quatre noms de recherche restent dans batch.yaml en attendant la bascule
contrôlée 17-D. Doublon entre catalogues refusé. Historique CN : fichiers
de runs et artefacts CN, pas pit_collection_runs US. D10/17-C activés ne
signifient pas chaîne quotidienne CN opérationnelle.

## FR — batch_fr.yaml, 14 entrées, 11 actives

| Batch | État actuel | Source / destination |
| --- | --- | --- |
| fr_calendar_snapshot | Recherche active | Bibliothèque XPAR → `fr_calendar_sessions_research` et archives |
| fr_security_master_sync | Recherche active | ESMA/Euronext → `fr_reference_versions_research` et archives |
| fr_daily_bars_sync | Recherche active | EODHD → fichiers et staging SQL FR, pas canonique |
| fr_corporate_actions_sync | Recherche active | EODHD → `fr_corporate_actions_research` et archives |
| fr_amf_short_sync | Recherche active | Export public AMF → `fr_amf_positions_research` ; positions déclarées, pas borrow |
| fr_dila_disclosures_sync | Recherche active | DILA → `fr_dila_disclosures_research`, métadonnées versionnées |
| fr_options_mifir_trade_sync | Recherche active, quarantaine | Transactions différées Euronext + FIRDS → fichiers sources et quatre tables `fr_option_mifir_*` dans `alpha_trade_fr` ; ni OI ni NBBO complet. [Stockage SQL et reprise](../fr/options_mifir_stockage_sql.md) |
| fr_options_open_interest_sync | Recherche active, OI publique non qualifiée | Chaînes publiques Euronext Paris → trois tables `fr_option_oi_public_*` ; 6h30 et 20h30 Paris lun-sam. Dates OI/expiration inconnues, anomalies conservées, aucun filtre directionnel. [Contrat de collecte](../fr/options_open_interest_public.md) |
| fr_db_backup | Actif | alpha_trade_fr → backups/fr/db, keep=3 |
| fr_artifacts_backup | Actif | artifacts/fr + artifacts/models/fr_eq → backups/fr/artifacts, keep=3 |
| fr_fundamentals_sync | ⛔ Droits/prudence | BLOCKED_INPI_RETENTION |
| fr_consensus_snapshot | Activé par configuration, source EODHD testée | ACTIVE_RESEARCH — installer/réinstaller la tâche Windows |
| fr_borrow_snapshot | Fournisseur manquant | PENDING_PROVIDER |
| fr_options_snapshot | Source complète manquante | PENDING_PROVIDER ; MiFIR partiel ne remplace pas ce contrat complet |

Le staging quotidien utilise fr_ingestion_runs, fr_raw_payloads,
fr_provider_bars_staging et fr_staging_progress. Depuis le 27 octobre, les
[familles complémentaires et archives sont aussi en SQL de recherche](../fr/batchs_stockage_sql_20261027.md),
avec `fr_batch_research_documents` et `fr_batch_research_file_versions` pour les
preuves et reçus. Aucun remplissage canonique automatique. Rapports de runner :
artifacts/fr/operations/runs/<batch>/*.json. Le statut SUCCESS ne prouve pas
une libération PIT, fiscale, économique ou broker.

## Installation, lancement, notifications et secours

**Workflow & Orchestration → Batch → marché choisi** : commande d'installation,
boutons installer/réinstaller, lancer maintenant, désinstaller, logs, raisons de
blocage, couverture J−N/J ou second passage. Les actions globales n'agissent
que sur ce marché ; l'installation concerne les entrées enabled=true compatibles,
la désinstallation les tâches installées hors runs actifs.

Les tâches communes utilisent wscript.exe + wrapper caché, puis PowerShell.
Triggers horaires et filtrage heure/jour/fuseau au launcher ; NextRunTime
Windows n'est donc pas forcément l'heure effective de collecte.
Interactive nécessite une session disponible. Lancer maintenant contourne
l'horaire, **jamais le kill switch ou les droits**. Ne pas forcer les fenêtres
prospectives pour reconstituer des observations manquées.

US : secours conditionnel déjà prévu pour certains snapshots ; succès récent
COMPLETED ou COMPLETED_WITH_WARNINGS → SKIP. Les batchs FR/CN actifs n'ont
actuellement pas de second passage déclaré. Notifications mail et Telegram
au launcher, détails d'erreur et compteurs ; contrôle des deux destinations
nécessaire si le transport lui-même échoue.

Horaires/marges : [FR/CN](horaires_fr_cn_presence_pc.md),
[US et contrats de collecte](forward_pit_batches.md).
Les rapports de recherche hors launcher n'envoient pas automatiquement ces
notifications ; les exercices FR 18 affichent seulement des aperçus NOT_SENT.

## Entrées retirées

Ne plus chercher dans le catalogue actuel : pit_data_quality_daily (US),
cn_staging_quality_daily, cn_baostock_smoke, cn_master_calendar_sync,
fr_pit_quality_daily, fr_consensus_borrow_options. Fonctions/historiques peuvent
subsister pour recherche et traçabilité ; leur présence ne réinstalle pas un job.
Les exemples anciens utilisant ces noms sont des exemples historiques.

Qualification du 10 octobre : le consensus EODHD renvoie 403 avec la clé actuelle,
sans achat. Macro directe : première collecte 107 versions, seconde 0 nouvelle,
tâche PublicMacroSnapshotSync installée. FRED et FINRA restent bloqués.
Voir [les produits, droits, preuves et limites PIT](../ml/consensus_eodhd_macro_publics_20261010.md).
