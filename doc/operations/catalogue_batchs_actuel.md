# Catalogue opérationnel des batchs — 10 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Inventaire rapproché de `ihm/services/batch_management.py`, des trois YAML,
des runners et des lanceurs. « Actif » décrit la configuration ; cela ne
prouve ni installation Windows, ni réussite du dernier run, ni GO ML.
Les commandes de la carte IHM font autorité pour le launcher et le catalogue.

## US — batch.yaml, 25 entrées, 16 actives

| Batch | État actuel | Fournisseur / stockage principal |
| --- | --- | --- |
| us_pipeline | Actif PAPER | Workflow 1–14 configuré, tables métier US ; détail ci-dessous |
| daily_bars_sync | Actif | Business Quant → pit_raw_payloads, stock_bars_daily_versions ; pas import EODHD canonique |
| security_master_snapshot | Actif | Nasdaq directory / Business Quant → security_master_snapshots, security_master_changes |
| corporate_actions_sync | Actif | Business Quant / Alpaca → corporate_action_source_events ; distinct de l'application portefeuille |
| sec_edgar_incremental | Actif | SEC → sec_filing_raw, sec_filing_documents ; primaire et annexes EX-99 selon option |
| market_cap_sync | Actif | SEC primaire, Yahoo puis Finnhub fallback → stock_fundamentals_daily |
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
| analyst_snapshot_collection | ⛔ Droits/prudence | BLOCKED_YAHOO_AUTOMATED_ACCESS ; pas de reprise automatique |
| business_quant_analyst_snapshot | Désactivé, remplacé | REPLACED_BY_YAHOO ; le remplaçant est lui-même bloqué actuellement |
| fred_alfred_vintage_sync | ⛔ Droits/prudence | BLOCKED_FRED_ARCHIVE_ML_RIGHTS |
| finra_short_volume_sync | ⛔ Droits/prudence | BLOCKED_FINRA_PREDICTIVE_USE |
| securities_lending_sync | Fournisseur manquant | PENDING_PROVIDER ; pas de connecteur gratuit qualifié pour le besoin complet |
| official_options_nbbo_sync | Source manquante | BLOCKED_FREE_NO_NBBO_SOURCE ; bars/mémos partiels ne fournissent pas le NBBO |
| auction_imbalance_sync | Source manquante | BLOCKED_NO_FREE_OFFICIAL_FEED ; pas un flux exploitable simulé |

La plupart des nouveaux batchs US journalisent dans pit_collection_runs et
pit_raw_payloads, en plus des tables métier listées. Le RAW peut croître à
chaque observation sans doublon métier. Les noms de fournisseur absents du YAML
ne rendent pas une normalisation locale indépendante de sa source amont SEC.

La collecte de capitalisation n'impose pas un filtre : `config.yaml/market_cap`
est actuellement en **liquidity_only**. Le fallback Yahoo du batch capitalisation
n'est pas le batch de consensus Yahoo ; les restrictions de ce dernier ne
doivent pas être extrapolées à une autorisation générale des autres usages.

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

## FR — batch_fr.yaml, 13 entrées, 9 actives

| Batch | État actuel | Source / destination |
| --- | --- | --- |
| fr_calendar_snapshot | Recherche active | Bibliothèque XPAR → fichiers calendrier |
| fr_security_master_sync | Recherche active | ESMA/Euronext → référentiel versionné, fichiers |
| fr_daily_bars_sync | Recherche active | EODHD → fichiers et staging SQL FR, pas canonique |
| fr_corporate_actions_sync | Recherche active | EODHD/preuves publiques → fichiers versionnés |
| fr_amf_short_sync | Recherche active | Export public AMF → fichiers ; positions déclarées, pas borrow |
| fr_dila_disclosures_sync | Recherche active | DILA info financière → métadonnées versionnées |
| fr_options_mifir_trade_sync | Recherche active, quarantaine | Transactions différées Euronext + FIRDS → fichiers ; ni OI ni NBBO complet |
| fr_db_backup | Actif | alpha_trade_fr → backups/fr/db, keep=3 |
| fr_artifacts_backup | Actif | artifacts/fr + artifacts/models/fr_eq → backups/fr/artifacts, keep=3 |
| fr_fundamentals_sync | ⛔ Droits/prudence | BLOCKED_INPI_RETENTION |
| fr_consensus_snapshot | ⛔ Droits/prudence | BLOCKED_YAHOO_AUTOMATED_ACCESS |
| fr_borrow_snapshot | Fournisseur manquant | PENDING_PROVIDER |
| fr_options_snapshot | Source complète manquante | PENDING_PROVIDER ; MiFIR partiel ne remplace pas ce contrat complet |

Le staging quotidien utilise fr_ingestion_runs, fr_raw_payloads,
fr_provider_bars_staging et fr_staging_progress. Les autres familles ne sont
pas automatiquement normalisées dans les tables métier. Rapports de runner :
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
