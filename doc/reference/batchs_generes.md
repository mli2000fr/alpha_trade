# Catalogues de batchs déclarés — référence générée

Extraction YAML au 2026-10-10, sans importer le service ni interroger Windows/SQL.
Les valeurs sont déclaratives : enabled ne prouve ni exécutable ni installé.
Le catalogue IHM applique aussi ses blocages et, pour les familles CN non raccordées, sa mise en sommeil.
Les noms d'état BLOCKED/PENDING priment ; aucune consigne de réactivation n'est déduite ici.
[Contrats et état effectif du catalogue](../operations/catalogue_batchs_actuel.md).

## `batch.yaml`

| Batch | enabled déclaré | Statut déclaré | Priorité | Principal (heures/minutes ; jours ; fuseau) | Secours | Reprise déclarée |
| --- | --- | --- | --- | --- | --- | --- |
| `us_pipeline` | True | ACTIVE | P0 | 22 / 45 ; 1,2,3,4,5 ; Europe/Paris | — | Séance US J figée au lancement, même après minuit. Étape 1 EODHD : contrôle des cours J non remplis, couverture minimale bars_collection.min_coverage_ratio (95 %) et SPY obligatoire. Absence → arrêt, pas de repli vers J-1. Jours fériés exclus ; pas de second passage. |
| `cn_dragon_tiger_after_close` | False | BLOCKED_SSE_SZSE_AUTOMATION | P2 | 17 / 30 ; tous ; China Standard Time | — | Snapshot de la séance CN J à 17:30 Asia/Shanghai ; première observation réelle, sans historique PIT reconstruit. |
| `cn_dragon_tiger_before_open` | False | BLOCKED_SSE_SZSE_AUTOMATION | P2 | 8 / 30 ; tous ; China Standard Time | — | Snapshot avant le seuil prudent de 09:15 Asia/Shanghai sur la précédente séance ouverte ; week-ends et jours fériés respectés. |
| `cn_oracle_prospective_daily` | False | BLOCKED_BAOSTOCK_RIGHTS | P1 | 18 / 15 ; tous ; China Standard Time | — | Séance J close vers décision K suivante ; lots reprenables. Aucun score rétrodaté si le passage manque son cutoff. |
| `cn_dragon_tiger_daily_match` | True | RESEARCH_ONLY | P2 | 9 / 30 ; tous ; China Standard Time | — | Une décision K après son cutoff de 09:15 Shanghai ; appariement quotidien immuable et sans issue H20. |
| `ml_artifacts_backup` | True | ACTIVE | P0 | 1 / 0 ; 6 ; Europe/Paris | — | Snapshot complet de artifacts/models ; conservation pilotée par keep (actuellement 5 archives) |
| `db_core_backup` | True | ACTIVE | P0 | 1 / 0 ; 0 ; Europe/Paris | — | Base alpha_trade complète sauf news_raw ; conservation des 5 dernières archives |
| `db_news_raw_backup` | True | ACTIVE | P0 | 20 / 0 ; 0 ; Europe/Paris | — | Table news_raw uniquement ; conservation des 3 dernières archives hebdomadaires |
| `market_cap_sync` | True | ACTIVE | P0 | 20 / 0 ; 1,4 ; Europe/Paris | 23 / 0 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `earnings_calendar_sync` | False | INTEGRATED_IN_US_PIPELINE | P1 | 23 / 0 ; 0,3,5 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
| `analyst_snapshot_collection` | False | BLOCKED_YAHOO_AUTOMATED_ACCESS | P1 | 22 / 0 ; tous ; Europe/Paris | 4 / 0 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `latest_quotes_sync` | False | INTEGRATED_IN_US_PIPELINE | P0 | 17 / 15 ; 1,2,3,4,5 ; America/New_York | — | lookback_days=7 ; lookahead_days=— |
| `daily_bars_sync` | True | ACTIVE | P0 | 3 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | lookback_days=10 ; lookahead_days=— |
| `security_master_snapshot` | True | ACTIVE | P0 | 1 / 0 ; 1,2,3,4,5 ; Europe/Paris | 6 / 0 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `corporate_actions_sync` | True | ACTIVE | P0 | 0 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
| `sec_edgar_incremental` | True | ACTIVE | P0 | 20 / 0 ; 1,2,3,4,5,6 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
| `borrow_status_snapshot` | True | ACTIVE | P1 | 15 / 45 ; 1,2,3,4,5 ; America/New_York | 22 / 25 (conditionnel) | Disponibilité short réellement observée à 15:45 New York ; second passage conditionnel à 22:25 NY le même jour US. Aucun historique J-7/J ni snapshot préouverture reconstruit. |
| `business_quant_analyst_snapshot` | False | REPLACED_BY_YAHOO | P1 | 16 / 0 ; 1,2,3,4,5 ; America/New_York | — | lookback_days=— ; lookahead_days=— |
| `oracle_options_indicative_snapshot` | True | ACTIVE_RESEARCH_ONLY | P2 | 16 / 20 ; 1,2,3,4,5 ; America/New_York | 22 / 20 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `options_delayed_bars_sync` | True | ACTIVE_RESEARCH_ONLY | P2 | 17 / 0 ; 1,2,3,4,5 ; America/New_York | 23 / 0 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `option_contract_adjustment_sync` | True | ACTIVE_RESEARCH_ONLY | P2 | 1 / 15 ; 1,2,3,4,5,6 ; Europe/Paris | 6 / 15 (conditionnel) | lookback_days=— ; lookahead_days=— |
| `oracle_opening_window_sync` | True | ACTIVE_RESEARCH_ONLY | P3 | 15 / 50 ; 1,2,3,4,5 ; America/New_York | — | lookback_days=7 ; lookahead_days=— |
| `sec_corporate_events_normalize` | True | ACTIVE | P3 | 23 / 0 ; 1,2,3,4,5,6 ; Europe/Paris | — | lookback_days=— ; lookahead_days=— |
| `sec_institutional_ownership_normalize` | True | ACTIVE | P4 | 23 / 0 ; 2,4,6 ; Europe/Paris | — | lookback_days=— ; lookahead_days=— |
| `fred_alfred_vintage_sync` | False | BLOCKED_FRED_ARCHIVE_ML_RIGHTS | P4 | 14 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | lookback_days=— ; lookahead_days=— |
| `finra_short_volume_sync` | False | BLOCKED_FINRA_PREDICTIVE_USE | P1 | 23 / 0 ; 1,2,3,4,5 ; America/New_York | — | lookback_days=7 ; lookahead_days=— |
| `auction_imbalance_sync` | False | BLOCKED_NO_FREE_OFFICIAL_FEED | P3 | — / 0 ; tous ; Windows local | — | lookback_days=— ; lookahead_days=— |
| `securities_lending_sync` | False | PENDING_PROVIDER | P1 | — / 0 ; tous ; Windows local | — | lookback_days=— ; lookahead_days=— |
| `official_options_nbbo_sync` | False | BLOCKED_FREE_NO_NBBO_SOURCE | P2 | — / 0 ; tous ; Windows local | — | lookback_days=— ; lookahead_days=— |

## `batch_cn.yaml`

| Batch | enabled déclaré | Statut déclaré | Priorité | Principal (heures/minutes ; jours ; fuseau) | Secours | Reprise déclarée |
| --- | --- | --- | --- | --- | --- | --- |
| `cn_db_backup` | True | ACTIVE | P0 | 4 / 0 ; 0 ; Europe/Paris | — | lookback_days=— ; lookahead_days=— |
| `cn_daily_market_data_sync` | False | DISABLED_DUPLICATE_D9 | P0 | 10 / 0 ; 1,2,3,4,5 ; Asia/Shanghai | — | lookback_days=10 ; lookahead_days=— |
| `cn_historical_backfill` | False | DISABLED | P0 | — / 0 ; tous ; Asia/Shanghai | — | lookback_days=— ; lookahead_days=— |
| `cn_daily_quality_17c` | True | ACTIVE | P0 | 20 / 30 ; 1,2,3,4,5 ; Europe/Paris | — | 20h30 Paris lundi-vendredi, soit J+1 à 02h30/03h30 Shanghai : contrôle de la séance CN J (veille civile Shanghai), sans reconstitution d'une prévision manquée. Si J fermé : SKIP. |
| `cn_akshare_enrichment` | False | DISABLED | P2 | — / 0 ; tous ; Asia/Shanghai | — | lookback_days=— ; lookahead_days=— |
| `cn_tushare_optional` | False | DISABLED | P3 | — / 0 ; tous ; Asia/Shanghai | — | lookback_days=7 ; lookahead_days=— |

## `batch_fr.yaml`

| Batch | enabled déclaré | Statut déclaré | Priorité | Principal (heures/minutes ; jours ; fuseau) | Secours | Reprise déclarée |
| --- | --- | --- | --- | --- | --- | --- |
| `fr_calendar_snapshot` | True | ACTIVE_RESEARCH | P0 | 6 / 0 ; 0 ; Europe/Paris | — | J-7 à J+370, calendrier de bibliothèque XPAR ; relance idempotente par date d'observation. |
| `fr_security_master_sync` | True | ACTIVE_RESEARCH | P0 | 5 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | Passage 5h Paris avant absence 7h30-20h ; publications jusqu'à J-1, recouvrement 7 jours, rattrapage borné à 31 jours. Fragments absents : checkpoint non avancé. |
| `fr_daily_bars_sync` | True | ACTIVE_RESEARCH | P0 | 22 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | J-7/J après 22h Paris ; avant 22h : J-7/J-1. Reprise explicite, relance normale rafraîchissant les corrections. |
| `fr_corporate_actions_sync` | True | ACTIVE_RESEARCH | P0 | 23 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | J-31/J fournisseur pour le warmup, dividendes et splits ; deux requêtes par titre. Réponse vide = observation fournisseur, pas preuve officielle d'absence d'événement. |
| `fr_amf_short_sync` | True | ACTIVE_RESEARCH | P1 | 21 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | Snapshot de l'export AMF complet courant ; historique reconstruit, pas vintage historique. |
| `fr_dila_disclosures_sync` | True | ACTIVE_RESEARCH | P1 | 21 / 30 ; 1,2,3,4,5 ; Europe/Paris | — | J-7/J sur la date de transmission AMF ; métadonnées pour les ISIN vérifiés, versions conservées. |
| `fr_fundamentals_sync` | False | BLOCKED_INPI_RETENTION | P2 | 20 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | Lots de 25 émetteurs au plus, pagination et documents repris au checkpoint ; jusqu'à 500 appels/run et 5000/jour UTC, revue des documents tous les 7 jours. Pas de reconstruction PIT historique. |
| `fr_consensus_snapshot` | False | BLOCKED_YAHOO_AUTOMATED_ACCESS | P3 | 20 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | Snapshot réellement observé à J, reprise des titres incomplets du jour ; les succès ne sont pas rechargés le même jour. Pas de reconstruction J-7/J. |
| `fr_borrow_snapshot` | False | PENDING_PROVIDER | P3 | 20 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
| `fr_options_mifir_trade_sync` | True | ACTIVE_RESEARCH | P3 | 6 / 0 ; 1,2,3,4,5,6 ; Europe/Paris | — | lookback_days=0 ; lookahead_days=— |
| `fr_options_snapshot` | False | PENDING_PROVIDER | P3 | 20 / 0 ; 1,2,3,4,5 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
| `fr_db_backup` | True | ACTIVE | P0 | 3 / 0 ; 0 ; Europe/Paris | — | Sauvegarde complète alpha_trade_fr ; dimanche 03:00 Paris, keep configurable. |
| `fr_artifacts_backup` | True | ACTIVE | P0 | 2 / 0 ; 6 ; Europe/Paris | — | lookback_days=7 ; lookahead_days=— |
