# Diagnostic et reprise — pipeline `event_sentiment`

## Objet

Ce document trace le diagnostic, les corrections apportées et la reprise opératoire effectuée pour le pipeline sentiment, avec priorité sur le flux IHM **7.bis** (`scripts/windows/import_news_and_score_pending.ps1`) et sur le drift schéma/code bloquant l’alimentation de `ticker_daily_sentiment_features` / `sector_daily_sentiment_features`.

---

## 1. Causes racines identifiées

### 1.1 Drift orchestration sur le script 7.bis

Le wrapper PowerShell mélangeait deux responsabilités :

1. importer des news brutes,
2. scorer le backlog `pending`.

Problèmes constatés :

- le comptage `pending` portait sur tout `news_raw` / `news_sentiment`, pas sur le **scope réellement importé** ;
- la relance Python de `event_sentiment` ne repassait pas la fenêtre `--start-utc/--end-utc` ;
- l’étape pouvait donc repartir sur des checkpoints globaux et dériver vers un backlog historique plus large que la fenêtre demandée.

### 1.2 Drift schéma SQL / code sur les features ticker

`event_sentiment/aggregation.py` produit les colonnes pondérées suivantes :

- `relevance_weight_sum_1d`
- `relevance_weight_sum_3d`
- `relevance_weight_sum_5d`
- `relevance_weight_sum_10d`
- `relevance_weight_sum_20d`

Ces colonnes étaient absentes des SQL canoniques de création de table, ce qui pouvait bloquer les `upsert` de `ticker_daily_sentiment_features`.

### 1.3 Autre drift SQL détecté

La table `news_sentiment` utilisait déjà `model_fingerprint` côté code / SQL dédié, mais le bootstrap global `database/sql/news/init_event_sentiment.sql` n’était pas aligné.

---

## 2. Correctifs code appliqués

### 2.1 `event_sentiment/db_io.py`

- ajout d’un logger ;
- durcissement de `_upsert()` : les colonnes absentes du schéma réel sont ignorées avec warning au lieu de faire échouer l’upsert ;
- ajout d’une construction générique de requête backlog pending ;
- ajout de `count_pending_articles(...)` ;
- extension de `load_pending_articles(...)` avec filtres :
  - `start_date`
  - `end_date`
  - `ingestion_source`
  - `symbols`

Objectif : compter / charger le backlog `pending` de manière **bornée**, compatible avec le vrai scope d’un run 7.bis.

### 2.2 `event_sentiment/pipeline.py`

- ajout du mode `skip_ingestion` ;
- ajout de `_build_pending_scope(...)` ;
- en mode `skip_ingestion=True`, la pipeline :
  - ne relance pas l’ingestion,
  - résout seulement une fenêtre temporelle,
  - charge le backlog pending déjà présent en base, borné par provider + dates.

Objectif : permettre un **scoring backlog-only** sûr, sans ré-ingestion parasite.

### 2.3 `event_sentiment/cli.py`

- ajout du flag `--skip-ingestion` ;
- transmission du flag à `EventSentimentPipeline.run(...)`.

### 2.4 `scripts/windows/import_news_and_score_pending.ps1`

- comptage du backlog scoped via `EventSentimentRepository.count_pending_articles(...)` ;
- ajout d’une résolution explicite de la fenêtre UTC du run ;
- relance du scoring via :

```powershell
python -u -m event_sentiment --skip-ingestion --news-provider ... --start-utc ... --end-utc ...
```

- summary enrichi avec compteurs globaux et scoped ;
- warning explicite si backlog global > backlog scoped.

---

## 3. Correctifs SQL appliqués

### 3.1 `database/sql/news/ticker_daily_sentiment_features.sql`

Ajout des colonnes :

- `relevance_weight_sum_1d`
- `relevance_weight_sum_3d`
- `relevance_weight_sum_5d`
- `relevance_weight_sum_10d`
- `relevance_weight_sum_20d`

### 3.2 `database/sql/news/init_event_sentiment.sql`

Alignement du bootstrap global avec le runtime :

- ajout de `model_fingerprint` + index sur `news_sentiment` ;
- ajout des colonnes `relevance_weight_sum_*` sur `ticker_daily_sentiment_features`.

---

## 4. Validation automatisée côté dépôt

Les tests ciblés de régression ont été adaptés puis relancés avec succès, notamment sur :

- pipeline `skip_ingestion`
- résumés de run
- compatibilité repository backlog pending
- tolérance `_upsert()` au drift de schéma

Campagne validée en ciblé via `pytest --no-cov`.

---

## 5. Reprise opératoire effectuée le 2026-05-12

### 5.1 État initial observé au moment de la reprise effective

Le run réel d’import pur était coûteux, car `event_sentiment/importe_news.py` parcourt un univers large de symboles. Pour éviter de relancer un import brut inutilement long, la reprise s’est appuyée sur le backlog déjà en base.

### 5.2 Mesure avant scoring backlog-only

Constat sur la base active :

- backlog pending `alpaca` sur `2026-05-05` → `2026-05-12` : **66**
- backlog pending global : **66**
- features déjà présentes, mais run de consolidation requis après scoring.

### 5.3 Commande exécutée pour vider le backlog scoped

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment --skip-ingestion --news-provider alpaca --start-utc 2026-05-05T00:00:00Z --end-utc 2026-05-12T23:59:59Z --enable-contextual-scoring --contextual-min-relevance 0.3 --contextual-max-pairs 5000
```

Résultat observé :

- `sentiment_inferred = 66`
- `contextual_pairs_loaded = 88`
- `contextual_scored = 88`
- `macro_rows = 8`
- `ticker_day_rows = 1152`
- `sector_day_rows = 229`
- `finbert_model_fingerprint = 90a2fcfb70d7c918`

### 5.4 Rejeu `history_backfill`

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment.history_backfill --start-date 2026-05-05 --end-date 2026-05-12 --batch-days 8
```

Résultat observé :

- `trade_dates_processed = 6`
- `ticker_rows_upserted = 1152`
- `sector_rows_upserted = 229`

### 5.5 Fusion quant + sentiment (`signal_aggregator`)

Le périmètre `candidates` était vide dans `stock_scores` (`is_candidate = 1` → 0 ligne). Pour propager malgré tout les features sentiment reconstruites dans `stock_scores`, la fusion a été lancée sur **tous les symboles** :

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-05-12
```

Résultat observé :

- `loaded_symbols = 1281`
- `updated_symbols = 1281`
- `signal_active_symbols = 97`
- `avg_final_score_sentiment = 0.1228`
- `max_final_score_sentiment = 0.2015`

Un verrou d’idempotence a été créé pour `2026-05-12_all`.

---

## 6. État final vérifié

### 6.1 Backlog

Après scoring scoped :

- backlog pending `alpaca` sur `2026-05-05` → `2026-05-12` : **0**
- backlog pending global : **0**

### 6.2 Features remplies

Sur la fenêtre `2026-05-05` → `2026-05-12` :

- `ticker_daily_sentiment_features`
  - `rows_count = 1152`
  - `symbol_count = 719`
  - `min_date = 2026-05-05`
  - `max_date = 2026-05-12`

- `sector_daily_sentiment_features`
  - `rows_count = 229`
  - `sector_count = 52`
  - `min_date = 2026-05-05`
  - `max_date = 2026-05-12`

### 6.3 `stock_scores`

Après `signal_aggregator --all-symbols --trade-date 2026-05-12` :

- `rows_count = 1281`
- `active_count = 97`
- `avg_score = 0.1228`
- `max_score = 0.2015`
- `last_updated_sentiment = 2026-05-11 22:45:39 UTC`

---

## 7. Commandes de vérification / reprise

### Vérifier backlog pending

```powershell
Set-Location "F:\projets"
python -u -c "from datetime import date; from event_sentiment.db_io import EventSentimentRepository as R; r=R(); print(r.count_pending_articles(start_date=date(2026,5,5), end_date=date(2026,5,12), ingestion_source='alpaca')); print(r.count_pending_articles())"
```

### Rejouer uniquement le scoring sur backlog déjà importé

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment --skip-ingestion --news-provider alpaca --start-utc 2026-05-05T00:00:00Z --end-utc 2026-05-12T23:59:59Z --enable-contextual-scoring --contextual-min-relevance 0.3 --contextual-max-pairs 5000
```

### Rejouer le backfill features

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment.history_backfill --start-date 2026-05-05 --end-date 2026-05-12 --batch-days 8
```

### Rejouer la fusion `stock_scores`

```powershell
Set-Location "F:\projets"
python -u -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-05-12 --allow-rerun
```

---

## 8. Points d’attention restants

1. Le correctif 7.bis est opérationnel côté **scoring backlog scoped**.
2. Le backlog pending observé lors de cette reprise est désormais **vidé**.
3. Le point de coût principal reste l’**ingestion brute** quand elle repart sur un univers trop large de symboles.
4. Pour réduire ce coût, `event_sentiment/importe_news.py` a ensuite été **optimisé** :
   - l’univers par défaut n’est plus `stock_bars_daily`, mais `stock_scores` ;
   - un nouveau paramètre `--symbol-source` permet de choisir explicitement entre :
     - `stock_scores` (défaut, recommandé),
     - `candidates`,
     - `stock_bars_daily` (ancien comportement large) ;
   - un paramètre `--symbols` permet de borner manuellement l’import à une shortlist ;
   - un paramètre `--batch-size` permet d’ajuster la granularité des batchs ;
   - un garde-fou `--max-symbols` permet de refuser explicitement un run trop large ;
   - un warning fort est émis quand `--symbol-source stock_bars_daily` dépasse un seuil de volumétrie.
5. Cette optimisation a aussi été **propagée dans l’IHM** :
   - le panneau `7.bis Import des news brutes` expose désormais :
     - l’univers de symboles (`stock_scores` / `candidates` / `stock_bars_daily`),
     - une shortlist CSV explicite,
     - un cap sécurité `max-symbols` ;
   - l'IHM affiche maintenant un **résumé live du scope réellement résolu avant lancement** :
     - source effective,
     - nombre de symboles,
     - extrait des premiers symboles,
     - alerte si `max-symbols` bloquerait le run ;
   - le wrapper Windows `scripts/windows/import_news_and_score_pending.ps1` propage maintenant ces options à :
     - `importe_news.py`,
     - `python -m event_sentiment --skip-ingestion`,
     - `event_sentiment.relevance_backfill`.
6. Le wrapper 7.bis résout aussi désormais le **scope réel de symboles** quand l'utilisateur choisit `stock_scores` ou `candidates`, afin que le comptage `pending`, le scoring backlog-only et le `relevance_backfill` restent alignés avec l'univers importé.
7. Mesure DB ayant motivé cette optimisation :
   - `stock_bars_daily_distinct_symbols = 12244`
   - `stock_scores_total = 1281`
   - `stock_scores_candidates = 0`

---

## 9. Audit final — échantillon de lignes réelles

### 9.1 `ticker_daily_sentiment_features`

Exemples relevés sur `trade_date = 2026-05-12` :

- `NVDA`
  - `news_count_1d = 6`
  - `relevance_weight_sum_1d = 6.0`
  - `sentiment_net_mean_1d = 0.1335`
  - `sentiment_net_sum_1d = 0.8012`
  - `major_event_flag = 1`
- `AMZN`
  - `news_count_1d = 5`
  - `relevance_weight_sum_1d = 5.0`
  - `sentiment_net_mean_1d = -0.1092`
  - `sentiment_net_sum_1d = -0.5461`
  - `major_event_flag = 1`
- `MSFT`
  - `news_count_1d = 4`
  - `relevance_weight_sum_1d = 4.0`
  - `sentiment_net_mean_1d = 0.0856`
  - `sentiment_confidence_mean_1d = 0.8196`

Lecture audit : les colonnes `relevance_weight_sum_*` sont bien présentes et alimentées ; les valeurs sont cohérentes avec un mapping `provider_default` (pondération ~= nombre d’articles quand `relevance_score` est implicite à 1).

### 9.2 `sector_daily_sentiment_features`

Exemples relevés sur `trade_date = 2026-05-12` :

- `Technology`
  - `sector_news_count_1d = 9`
  - `sector_sentiment_net_mean_1d = 0.3460`
  - `sector_impact_score = 0.1709`
  - `macro_event_flag = 1`
- `Semiconductors`
  - `sector_news_count_1d = 8`
  - `sector_sentiment_net_mean_1d = 0.1820`
  - `sector_impact_score = 0.0`
  - `macro_event_flag = 0`
- `Biotechnology`
  - `sector_news_count_1d = 6`
  - `sector_sentiment_net_sum_1d = 3.6744`
  - `sector_impact_score = 0.0`

Lecture audit : la table sectorielle contient bien à la fois les signaux agrégés de news et les drapeaux / intensités macro.

### 9.3 `stock_scores`

Exemples relevés après `signal_aggregator --all-symbols --trade-date 2026-05-12` :

- `AKAM`
  - `total_score = 80.15625`
  - `final_score_sentiment = 0.2015`
  - `signal_active = 1`
  - `total_news = 20`
  - `sentiment_net_agg = 0.7652`
  - `sector_impact_agg = 0.3826`
- `APLD`
  - `final_score_sentiment = 0.1978`
  - `signal_active = 1`
  - `total_news = 3`
- `XAR`
  - `sector = NULL`
  - `final_score_sentiment = 0.1941`
  - `signal_active = 1`

Lecture audit : l’enrichissement `stock_scores` est bien matérialisé, y compris pour des symboles sans secteur renseigné (macro agrégé à 0.0 dans ce cas).

---

## 10. Conclusion

Les objectifs prioritaires ont été couverts :

- drift schéma/code corrigé ;
- SQL canoniques réalignés ;
- pipeline rendue compatible `skip_ingestion` ;
- script 7.bis corrigé pour traiter un backlog **scoped** ;
- backlog pending de la fenêtre cible vidé ;
- `history_backfill` rejoué ;
- `ticker_daily_sentiment_features` et `sector_daily_sentiment_features` vérifiées alimentées ;
- `signal_aggregator` rejoué avec succès sur `stock_scores`.

