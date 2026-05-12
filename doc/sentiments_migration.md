# Migration des résultats du pipeline « Import + score + history_backfill + relevance_backfill auto »

> Date d'analyse : 2026-05-10  
> Périmètre : bouton **7.bis Import des news brutes** dans la page pipeline, puis exécution déportée sur un autre PC et réinjection des résultats sur le PC principal.

---

## Synthèse courte

Oui, ce traitement peut être déporté sur un PC secondaire qui tourne 24h/24, **à condition de migrer la base `news/sentiment` produite par le run**, et pas seulement les logs.

Le bouton / la commande déclenche en réalité **4 sous-traitements** :

1. import brut des news ;
2. boucle automatique du pipeline sentiment jusqu'à ce qu'il n'y ait plus d'articles `pending` ;
3. reconstruction historique des features journalières ;
4. backfill de `relevance_score` (et éventuellement contextual rescore si activé côté relevance backfill).

Les **tables réellement écrites** par cette chaîne sont principalement :

- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `news_ticker_sentiment`
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `news_ingestion_checkpoint`

Et **optionnellement** si le run est lancé depuis l'IHM Streamlit (pas juste via PowerShell manuel) :

- `run_business_summaries`
- artefacts dans `artifacts/ihm_pipeline_runs/...`

La stratégie la plus simple et la plus sûre pour réinjecter sur le PC principal est :

- faire tourner le job long sur le PC 24/7 ;
- exporter **toutes les tables news/sentiment** ci-dessus par dump SQL ;
- sur le PC principal, sauvegarder les tables locales actuelles ;
- remplacer ces tables par la version calculée sur le PC 24/7 ;
- optionnellement copier les logs et les artefacts IHM si vous voulez aussi récupérer la traçabilité visuelle.

---

## 1. Commande réellement lancée par le bouton

### Point d'entrée IHM

Le bouton se trouve dans `ihm/pages/_data_integrity.py` et construit un preview de commande via `build_pipeline_command("import_news_pending_loop", ...)`.

Depuis les derniers correctifs, ce panneau affiche aussi un **résumé live du scope réellement résolu** avant lancement (source effective + nombre de symboles + aperçu), sans appeler le provider de news.

Dans `ihm/services/pipeline_runner.py`, la clé `import_news_pending_loop` fabrique un appel PowerShell vers :

- `scripts/windows/import_news_and_score_pending.ps1`

avec les arguments IHM (`StartDate`, `EndDate`, `NewsProvider`, options de scoring contextuel, batch size du relevance backfill, etc.).

Le bouton propage maintenant aussi :

- `symbol_source` (`stock_scores` par défaut, `candidates`, `stock_bars_daily`) ;
- `symbols` en CSV si une shortlist explicite est saisie ;
- `max_symbols` comme garde-fou dur.

### Ce que fait réellement le script PowerShell

Le script `scripts/windows/import_news_and_score_pending.ps1` enchaîne :

1. `event_sentiment/importe_news.py`
2. boucle `python -m event_sentiment` jusqu'à `pending = 0`
3. `python -m event_sentiment.history_backfill`
4. `python -m event_sentiment.relevance_backfill`

Important : **la boucle `python -m event_sentiment` ne fait pas que scorer**. Elle relance aussi une ingestion pilotée par checkpoint, puis calcule/persiste les sentiments, les signaux macro et les features journalières.

---

## 2. Ce que chaque sous-étape lit et écrit

## 2.1 `event_sentiment/importe_news.py`

### Tables lues

- `stock_scores` : univers d'import par défaut (`SELECT DISTINCT symbol FROM stock_scores`)
- `stock_bars_daily` : uniquement si l'utilisateur choisit explicitement `--symbol-source stock_bars_daily`
- `stock_metadata` : résolution secteur / company name via `EntitySectorMapper`
- `news_ingestion_checkpoint` : lecture éventuelle d'état par symbole
- `news_raw` : déduplication des articles existants

### Tables écrites

- `news_raw`
- `news_ticker_map`
- `news_ingestion_checkpoint`

### Effet métier

Cette étape peuple la matière première : article brut + mapping article → ticker + checkpoint d'avancement par source et par symbole.

Par défaut, l'univers est maintenant **borné à `stock_scores`**. Une shortlist explicite ou un cap `max-symbols` permet d'encadrer encore davantage la volumétrie.

---

## 2.2 Boucle `python -m event_sentiment` jusqu'à `pending = 0`

### Tables lues

- `stock_scores` : charge les symboles candidats si aucun symbole n'est passé en argument
- `stock_metadata` : utilisé pendant le contextual scoring / relevance / sector mapping
- `news_ingestion_checkpoint`
- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `news_ticker_sentiment`
- `macro_event_audit`

### Tables écrites

- `news_ingestion_checkpoint`
- `news_raw` *(car la pipeline ré-ingère aussi selon les checkpoints)*
- `news_ticker_map`
- `news_sentiment`
- `news_ticker_sentiment` *(si `--enable-contextual-scoring` est activé)*
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

### Effet métier

Cette boucle transforme les news brutes en signaux exploitables :

- score FinBERT article ;
- score FinBERT contextualisé article/symbole ;
- audit macro par secteur ;
- features journalières par ticker et par secteur.

---

## 2.3 `python -m event_sentiment.history_backfill`

### Tables lues

- `news_raw`
- `news_sentiment`
- `news_ticker_map`
- `news_ticker_sentiment`
- `macro_event_audit`

### Tables écrites

- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

### Effet métier

Recalcule l'historique des features sur toute la période demandée.  
Autrement dit, même si ces tables ont déjà été partiellement remplies pendant la boucle `event_sentiment`, cette étape les **complète / reconstruit** sur la fenêtre historique.

---

## 2.4 `python -m event_sentiment.relevance_backfill`

### Tables lues

- `news_ticker_map`
- `news_raw`
- `stock_metadata`
- `news_ticker_sentiment` *(si rescore contextual activé côté relevance backfill)*

### Tables écrites

- `news_ticker_map` (`relevance_score`, `relevance_components`)
- `news_ticker_sentiment` *(uniquement si `--rescore-contextual` est demandé)*

### Effet métier

Cette étape backfill les scores de pertinence article → ticker sur l'historique.  
Dans votre exemple de commande, il y a :

- `-EnableContextualScoring`
- mais **pas** `-RelevanceBackfillRescoreContextual`

Donc :

- le **contextual scoring principal** se produit pendant la boucle `python -m event_sentiment` ;
- le `relevance_backfill` final sert surtout à remplir / mettre à jour `news_ticker_map.relevance_score` sur la fenêtre historique.

---

## 3. Tables réellement créées / modifiées par cette commande

## 3.1 Tables de sortie à migrer absolument

| Table | Rôle | Pourquoi la migrer ? |
|---|---|---|
| `news_raw` | articles bruts normalisés | base source de tout le pipeline |
| `news_ticker_map` | mapping article → ticker + relevance | indispensable pour relier news et symboles |
| `news_sentiment` | score FinBERT par article | nécessaire à l'agrégation downstream |
| `news_ticker_sentiment` | score FinBERT contextualisé par `(article, symbol)` | nécessaire si scoring contextuel activé |
| `macro_event_audit` | classification macro / sectorielle | alimente les features sectorielles |
| `ticker_daily_sentiment_features` | features journalières par symbole | consommées downstream par l'application |
| `sector_daily_sentiment_features` | features journalières par secteur | consommées downstream par l'application |
| `news_ingestion_checkpoint` | état d'avancement d'ingestion par source/symbole | utile pour reprendre plus tard sans repartir de zéro |

## 3.2 Tables seulement lues par le pipeline

Ces tables **ne sont pas produites** par la commande, mais elles doivent être cohérentes sur le PC 24/7 pour que le calcul soit correct :

- `stock_bars_daily` (univers de symboles de l'import brut)
- `stock_scores` (univers candidat utilisé par `python -m event_sentiment`)
- `stock_metadata` (secteur / company_name)

Si ces tables diffèrent fortement entre les deux PC, le résultat du pipeline peut différer.

## 3.3 Tables optionnelles liées au lancement IHM

Si le run est lancé **depuis l'IHM**, le registre des runs peut aussi écrire :

- `run_business_summaries`

Mais si vous lancez directement la commande PowerShell dans un terminal sur le PC 24/7, cette table ne sera généralement **pas** alimentée par ce mécanisme IHM.

---

## 4. Fichiers et artefacts créés

## 4.1 Toujours créés, même en lancement manuel

Les modules Python configurent des logs de fichier dans `log/` :

- `log/importe_news.log`
- `log/event_sentiment.log`
- `log/event_sentiment_history_backfill.log`
- `log/event_sentiment_backfill.log`

Ces fichiers sont utiles pour l'audit, mais **ils ne suffisent pas** pour réinjecter les résultats métiers.

## 4.2 Créés seulement si le run passe par l'IHM

Si le run est lancé via la page pipeline, `ihm/services/process_registry.py` crée des artefacts dans :

- `artifacts/ihm_pipeline_runs/history_index.json`
- `artifacts/ihm_pipeline_runs/import_news_pending_loop/<run_id>/stdout.log`
- `artifacts/ihm_pipeline_runs/import_news_pending_loop/<run_id>/stderr.log`
- `artifacts/ihm_pipeline_runs/import_news_pending_loop/<run_id>/combined.log`
- `artifacts/ihm_pipeline_runs/import_news_pending_loop/<run_id>/record.json`

Si vous exécutez la commande PowerShell **hors IHM**, ces artefacts n'existent pas.

## 4.3 Cache modèle local éventuel

Le scoring FinBERT charge `ProsusAI/finbert` via `transformers.from_pretrained(...)`.  
Le cache Hugging Face / Transformers peut donc être créé sur le PC 24/7 dans le profil utilisateur Windows.

Ce cache est utile pour éviter un re-téléchargement, mais **il n'est pas nécessaire** pour transférer les résultats calculés vers le PC principal.

---

## 5. Ce qu'il faut faire sur le PC 24h/24

## 5.1 Pré-requis avant de lancer le long run

Sur le PC 24/7, il faut idéalement :

- le **même code** que sur le PC principal ;
- le **même schéma DB** (`database/sql/news/*.sql` + migrations Alembic déjà appliquées) ;
- les dépendances Python installées ;
- les credentials DB (`LOGIN_DB`, `PASSWORD_DB`) ;
- une base `alpha_trade` cohérente avec au minimum :
  - `stock_bars_daily`
  - `stock_scores`
  - `stock_metadata`

### Point d'attention DB

D'après `database/connection.py`, la majorité du projet utilise par défaut :

- hôte DB : `localhost`
- base : `alpha_trade`

Donc, en pratique, si vous avez un MySQL local sur chaque PC, vous aurez **deux bases distinctes**, et il faudra bien faire un export/import des tables de résultats.

---

## 5.2 Export recommandé une fois le calcul terminé

### Recommandation

Le plus simple est d'exporter **tout le domaine news/sentiment**, pas seulement une partie par date.

Tables à dumper ensemble :

- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `news_ticker_sentiment`
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `news_ingestion_checkpoint`

Optionnel :

- `run_business_summaries`
- `artifacts/ihm_pipeline_runs`
- `log/*.log`

### Exemple PowerShell d'export SQL sur le PC 24/7

> À adapter au chemin réel de `mysqldump.exe` si nécessaire.

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$exportDir = "F:\exports\sentiment_$ts"
New-Item -ItemType Directory -Path $exportDir -Force | Out-Null

$dumpFile = Join-Path $exportDir 'sentiment_tables.sql'

& mysqldump \
  "--user=$env:LOGIN_DB" \
  "--password=$env:PASSWORD_DB" \
  "--single-transaction" \
  "--skip-lock-tables" \
  "--default-character-set=utf8mb4" \
  alpha_trade \
  news_raw news_ticker_map news_sentiment news_ticker_sentiment \
  macro_event_audit ticker_daily_sentiment_features sector_daily_sentiment_features \
  news_ingestion_checkpoint \
  "--result-file=$dumpFile"

Copy-Item "F:\projets\log\importe_news.log" -Destination $exportDir -ErrorAction SilentlyContinue
Copy-Item "F:\projets\log\event_sentiment.log" -Destination $exportDir -ErrorAction SilentlyContinue
Copy-Item "F:\projets\log\event_sentiment_history_backfill.log" -Destination $exportDir -ErrorAction SilentlyContinue
Copy-Item "F:\projets\log\event_sentiment_backfill.log" -Destination $exportDir -ErrorAction SilentlyContinue

Compress-Archive -Path "$exportDir\*" -DestinationPath "$exportDir.zip" -Force
```

Si vous avez lancé le job via l'IHM du PC 24/7 et que vous voulez aussi récupérer l'historique visuel des runs :

```powershell
Copy-Item "F:\projets\artifacts\ihm_pipeline_runs" -Destination (Join-Path $exportDir 'ihm_pipeline_runs') -Recurse -Force -ErrorAction SilentlyContinue
```

---

## 6. Ce qu'il faut faire sur le PC principal pour réinjecter

## 6.1 Mode recommandé : le PC 24/7 est la source autoritaire

C'est le mode le plus simple.

### Étapes

1. sauvegarder les tables locales actuelles ;
2. vider les tables `news/sentiment` locales ;
3. importer le dump SQL du PC 24/7 ;
4. relancer l'application.

### Sauvegarde locale avant import

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupFile = "F:\backups\before_sentiment_import_$ts.sql"

& mysqldump \
  "--user=$env:LOGIN_DB" \
  "--password=$env:PASSWORD_DB" \
  "--single-transaction" \
  "--skip-lock-tables" \
  "--default-character-set=utf8mb4" \
  alpha_trade \
  news_raw news_ticker_map news_sentiment news_ticker_sentiment \
  macro_event_audit ticker_daily_sentiment_features sector_daily_sentiment_features \
  news_ingestion_checkpoint \
  "--result-file=$backupFile"
```

### Purge locale puis import

```powershell
$sqlReset = @"
SET FOREIGN_KEY_CHECKS=0;
TRUNCATE TABLE news_ticker_sentiment;
TRUNCATE TABLE macro_event_audit;
TRUNCATE TABLE news_sentiment;
TRUNCATE TABLE news_ticker_map;
TRUNCATE TABLE ticker_daily_sentiment_features;
TRUNCATE TABLE sector_daily_sentiment_features;
TRUNCATE TABLE news_ingestion_checkpoint;
TRUNCATE TABLE news_raw;
SET FOREIGN_KEY_CHECKS=1;
"@

$sqlReset | & mysql "--user=$env:LOGIN_DB" "--password=$env:PASSWORD_DB" alpha_trade
Get-Content "F:\imports\sentiment_tables.sql" | & mysql "--user=$env:LOGIN_DB" "--password=$env:PASSWORD_DB" "--default-character-set=utf8mb4" alpha_trade
```

Ensuite, si vous avez copié les logs / artefacts :

```powershell
Copy-Item "F:\imports\ihm_pipeline_runs" -Destination "F:\projets\artifacts\ihm_pipeline_runs" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "F:\imports\*.log" -Destination "F:\projets\log" -Force -ErrorAction SilentlyContinue
```

---

## 6.2 Mode avancé : fusionner sans remplacer tout l'existant

Si votre PC principal continue à produire ses propres données `news/sentiment`, un simple import brut peut provoquer des conflits de clés primaires / unicité.

Dans ce cas, la bonne méthode est :

1. importer le dump du PC 24/7 dans une **base temporaire** (ex: `alpha_trade_import`) ;
2. fusionner table par table avec `INSERT ... SELECT ... ON DUPLICATE KEY UPDATE` ;
3. vérifier les volumes ;
4. supprimer la base temporaire.

C'est faisable, mais plus complexe.  
Si votre but est surtout de récupérer un gros historique 2020 → 2025 calculé sur le PC 24/7, le **mode remplacement autoritaire** est le plus robuste.

---

## 7. Ordre de dépendance à respecter

### Ordre logique d'export/import

1. `news_raw`
2. `news_ticker_map`
3. `news_sentiment`
4. `macro_event_audit`
5. `news_ticker_sentiment`
6. `ticker_daily_sentiment_features`
7. `sector_daily_sentiment_features`
8. `news_ingestion_checkpoint`

### Pourquoi

- `news_ticker_map` dépend de `news_raw`
- `news_sentiment` dépend de `news_raw`
- `macro_event_audit` dépend de `news_raw`
- `news_ticker_sentiment` dépend de `news_raw` **et** de `news_ticker_map`
- les tables `ticker_daily_sentiment_features` et `sector_daily_sentiment_features` n'ont pas de FK directes vers ces tables, mais elles sont **dérivées** d'elles

---

## 8. Ce qu'il n'est pas nécessaire de migrer

Vous n'avez **pas besoin** de migrer pour ce sujet :

- `stock_bars_daily`
- `stock_scores`
- `stock_metadata`
- les caches EODHD / Finnhub
- le cache Hugging Face / Transformers

sauf si vous voulez que le PC principal reproduise exactement l'environnement de calcul du PC 24/7.

Pour **utiliser les résultats déjà calculés**, la migration des tables `news/sentiment` suffit.

---

## 9. Vérifications après import sur le PC principal

### Vérification 1 — volumes par table

```sql
SELECT 'news_raw' AS table_name, COUNT(*) AS rows_n FROM news_raw
UNION ALL
SELECT 'news_ticker_map', COUNT(*) FROM news_ticker_map
UNION ALL
SELECT 'news_sentiment', COUNT(*) FROM news_sentiment
UNION ALL
SELECT 'news_ticker_sentiment', COUNT(*) FROM news_ticker_sentiment
UNION ALL
SELECT 'macro_event_audit', COUNT(*) FROM macro_event_audit
UNION ALL
SELECT 'ticker_daily_sentiment_features', COUNT(*) FROM ticker_daily_sentiment_features
UNION ALL
SELECT 'sector_daily_sentiment_features', COUNT(*) FROM sector_daily_sentiment_features
UNION ALL
SELECT 'news_ingestion_checkpoint', COUNT(*) FROM news_ingestion_checkpoint;
```

### Vérification 2 — plus aucun article pending côté sentiment article

```sql
SELECT COUNT(*) AS pending_articles
FROM news_raw nr
LEFT JOIN news_sentiment ns ON ns.article_id = nr.article_id
WHERE ns.article_id IS NULL;
```

### Vérification 3 — plage temporelle réellement importée

```sql
SELECT
    MIN(effective_trade_date) AS min_trade_date,
    MAX(effective_trade_date) AS max_trade_date,
    COUNT(*) AS articles_n
FROM news_raw;
```

### Vérification 4 — features journalières bien reconstruites

```sql
SELECT
    MIN(trade_date) AS min_trade_date,
    MAX(trade_date) AS max_trade_date,
    COUNT(*) AS rows_n
FROM ticker_daily_sentiment_features;
```

---

## 10. Réponse directe à vos 2 questions

## 10.1 Quelles tables / quels fichiers sont créés par le bouton ?

### Tables principales écrites

- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `news_ticker_sentiment`
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `news_ingestion_checkpoint`

### Fichiers créés

Toujours :

- `log/importe_news.log`
- `log/event_sentiment.log`
- `log/event_sentiment_history_backfill.log`
- `log/event_sentiment_backfill.log`

Seulement si lancement via IHM :

- `artifacts/ihm_pipeline_runs/history_index.json`
- `artifacts/ihm_pipeline_runs/import_news_pending_loop/<run_id>/*`
- éventuellement une ligne de résumé dans `run_business_summaries`

## 10.2 Que faut-il faire sur le PC 24/7 pour extraire tous les résultats puis les injecter sur l'autre PC ?

### Sur le PC 24/7

- laisser tourner la commande jusqu'à la fin ;
- exporter par dump SQL les 8 tables `news/sentiment` ;
- optionnellement zipper les logs et les artefacts IHM.

### Sur le PC principal

- faire une sauvegarde locale avant import ;
- vider les tables `news/sentiment` locales ;
- importer le dump SQL du PC 24/7 ;
- copier les logs / artefacts si vous voulez aussi la traçabilité ;
- vérifier les comptages SQL après import.

---

## 11. Recommandation pratique finale

Pour votre cas d'usage « gros calcul historique 2020 → 2025 sur un PC dédié, puis récupération sur le PC principal », la meilleure approche est :

1. garder le PC 24/7 comme **machine de calcul** ;
2. considérer ses tables `news/sentiment` comme la **source autoritaire** ;
3. transférer périodiquement un **dump SQL complet** du domaine sentiment ;
4. remplacer ce domaine sur le PC principal ;
5. ne copier les logs / artefacts IHM que si vous avez besoin d'audit humain.

C'est beaucoup plus simple et plus fiable que d'essayer de recopier seulement des morceaux de tables ou uniquement les fichiers de logs.

