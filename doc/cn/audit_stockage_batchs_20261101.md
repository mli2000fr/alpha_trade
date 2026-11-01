# Stockage des batchs CN — audit du 1er novembre 2026

> État initial avant bascule. Voir désormais le
> [stockage SQL principal](stockage_sql_collectes.md) : les fichiers métier
> décrits ci-dessous sont migrés en SQL, et les producteurs/lecteurs adaptés.

Vérification du code, de `batch_cn.yaml`, des quatre sections CN encore
présentes dans `batch.yaml`, des fichiers locaux et de la base effective
`alpha_trade_cn`. Audit SQL en lecture seule, sans collecte fournisseur,
réactivation, migration ou suppression. Inventaire local :
`artifacts/operations/cn_storage_audit_20261101/inventory.json`.
Les nombres de lignes de cet inventaire sont des estimations MySQL,
pas des comptages exacts. Le dernier run d'ingestion enregistré parmi les
plus récents est terminé le 30 septembre 2026 ; cela ne prouve pas la
fraîcheur de toutes les familles de données.

Le stockage est **mixte** : l'ingestion de marché est SQL, mais les
observations Dragon/Tiger, les scores Oracle prospectifs et leurs
appariements sont encore conservés dans des fichiers métier.

| Batch | Configuration actuelle | Destination des données |
| --- | --- | --- |
| `cn_oracle_prospective_daily` | Désactivé, `BLOCKED_BAOSTOCK_RIGHTS` | Collecte BaoStock dans `cn_raw_payloads`, `cn_staging_rows`, `cn_ingestion_runs`, puis promotion canonique en SQL. Scores TOP20 et reçus Oracle en JSON/Parquet sous `artifacts/research/cn_oracle_prospective_15d8`. |
| `cn_daily_market_data_sync` | Désactivé, doublon D9 | Chemin générique d'ingestion BaoStock vers le staging SQL ; ne remplace pas la publication canonique D9. |
| `cn_historical_backfill` | Désactivé, manuel | Réponses brutes et lignes normalisées BaoStock en SQL. Checkpoints et bilans locaux en fichiers. La promotion canonique est une opération distincte. |
| `cn_dragon_tiger_after_close` | Désactivé, `BLOCKED_SSE_SZSE_AUTOMATION` | Observations métier JSON sous `artifacts/research/cn_dragon_tiger_15d6/observations`. Aucun dépôt SQL de ces événements dans ce chemin. |
| `cn_dragon_tiger_before_open` | Désactivé, même réserve | Même stockage JSON que le passage après clôture. |
| `cn_dragon_tiger_daily_match` | Activé, `RESEARCH_ONLY` | Lit les exports Oracle et snapshots précédents ; écrit `outcome_blind_matches.parquet` et les rapports locaux. Le contrat affirme `database_modified=false`. Ce n'est pas une collecte fournisseur. |
| `cn_daily_quality_17c` | Activé, lecture seule | Lit les tables et preuves D6/D9/D10, produit un bilan JSON local ; ne collecte pas de données de marché et n'écrit pas de table métier. |
| `cn_db_backup` | Activé | Lit `alpha_trade_cn`, écrit une sauvegarde sous `backups/cn/db` et un rapport local ; ces fichiers de sauvegarde sont attendus. |
| `cn_akshare_enrichment` | Désactivé, endpoints vides | Réservation non qualifiée, aucun collecteur actif à considérer comme alimentant SQL. |
| `cn_tushare_optional` | Désactivé | Connecteur optionnel vers le staging SQL ; aucune collecte active certifiée par cet audit. |

## Preuves dans le code et en base

- `service/baostock/ingestion.py::_persist` transmet les réponses au stockage
  SQL partagé `service/tushare/storage.py::persist_page`, qui insère dans
  `cn_raw_payloads` et `cn_staging_rows`. Les runs sont dans
  `cn_ingestion_runs`. Le nom du module partagé ne signifie pas que le
  fournisseur enregistré est Tushare : il reçoit explicitement `baostock`.
- `dataIntegrityEngine/cn_sprint7c_incremental.py` collecte puis utilise
  `service/market/cn_canonicalizer.py` pour la promotion canonique. Les
  tables existantes comprennent `stock_bars_daily`, `market_sessions`,
  `instruments`, `instrument_status_history`,
  `instrument_adjustment_factors`, `cn_daily_price_limits` et
  `cn_corporate_actions`.
- `service/market/cn_dragon_tiger_prospective_15d5.py::run` écrit un snapshot
  JSON contenant les événements et leur observation réelle.
- `modelFactory/cn_oracle_prospective_15d8.py` écrit
  `oracle_top20.parquet` et son rapport ; la base inventoriée ne contient
  aucune table de publication de ces scores prospectifs.
- `service/market/cn_dragon_tiger_matched_15d7.py` écrit les appariements
  Parquet ; le wrapper D10 ne remplace pas ce stockage par SQL.

Sur disque dans les racines opérationnelles examinées : deux snapshots D6,
un export Oracle TOP20 daté du 8 octobre 2026 et un fichier d'appariements
D10. D'autres répertoires d'expériences CN existent ; ces nombres ne
décrivent pas tous les anciens travaux de recherche du projet.

## Portée du constat

Les fichiers d'événements D6, de scores D8 et d'appariements D10 contiennent
des données métier ; ce ne sont pas uniquement des logs. Une politique
« toutes les données métier en SQL » n'est donc pas encore satisfaite côté
CN. Les logs, checkpoints, modèles, exports facultatifs et sauvegardes sont
à distinguer de ce stockage métier principal.

Cet audit ne modifie pas l'exploitation. Une future bascule SQL devra
conserver les dates d'observation réelles, les empreintes et les réserves
PIT/droits ; déplacer les anciens fichiers ne crée aucune disponibilité
historique supplémentaire et n'autorise pas une réactivation des collectes.
