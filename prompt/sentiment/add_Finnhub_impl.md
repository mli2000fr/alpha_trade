# Refactor Finnhub — synthèse d'implémentation

## ✅ Refactor minimal implémenté (étape 1)

### Backend `event_sentiment`
- **`event_sentiment/config.py`** : ajout `news_provider: Literal["alpaca","finnhub"]` (défaut backend `alpaca` pour rétro-compat), garde-fous `provider_ticker_relevance_mode` et `max_tickers_per_article`, fabrique `EventSentimentConfig.for_provider()`, registre `PROVIDER_REGISTRY`.
- **`event_sentiment/ingestion.py`** : seam provider `NEWS_PROVIDERS = {"alpaca": ..., "finnhub": ...}`, dispatch dynamique dans `NewsIngestionService.__init__` (avec fallback `getattr` pour ne pas casser `_DummyConfig` des tests existants), garde-fous Niveau 1 (filtrage articles trop bruyants + mode `strict` qui ne propage qu'au 1er ticker), nouveaux compteurs `filtered_too_many_tickers` / `strict_dropped_tickers` dans le summary.
- **`event_sentiment/cli.py`** : nouvelles options `--news-provider`, `--ticker-relevance-mode`, `--max-tickers-per-article` ; instanciation via `EventSentimentConfig.for_provider(...)` ; run summary enrichi (`news_provider`, `source_name`, `provider_ticker_relevance_mode`, compteurs garde-fous).

### Adaptateur Finnhub
- **`service/finnhub/news_client.py`** (nouveau) : `iter_news_pages` avec **même signature** que la version Alpaca, endpoint `https://finnhub.io/api/v1/company-news`, normalisation vers le format consommé par `_normalize_article` (ID stable de fallback, filtrage UTC fin côté client, `content=None`, garantie que le symbole interrogé reste dans `symbols`). Réutilise `_FINNHUB_RETRY_POLICY` + télémétrie.

### IHM
- **`ihm/services/pipeline_runner.py`** : nouveaux champs `sentiment_news_provider` (défaut `"finnhub"`) et `sentiment_ticker_relevance_mode` ; `build_pipeline_command("sentiment_pipeline", ...)` injecte **toujours** `--news-provider <value>` (et `--ticker-relevance-mode strict` si != défaut).
- **`ihm/pages/_execution_center/__init__.py`** : 2 nouveaux `selectbox` dans `_render_event_sentiment_block` (`pipeline_sentiment_news_provider` défaut `finnhub`, `pipeline_sentiment_ticker_relevance_mode` défaut `provider_default`), propagation jusqu'à `PipelineLaunchOptions`.

### Tests
- **Nouveaux** : `tests/test_finnhub_news_client.py` (4 tests : normalisation, filtrage fenêtre, ID stable de fallback, no-op symbols vides) ; `tests/test_event_sentiment_news_provider.py` (7 tests : fabrique config, validation, dispatch provider, filtres garde-fous Niveau 1).
- **Adaptés** : `tests/test_ihm_pipeline_runner.py` (cmd contient désormais `--news-provider`), `tests/test_ihm_pipeline_e2e.py` (jeu de clés étendu), `tests/test_event_sentiment_run_summaries.py` (fake config avec `for_provider`).

### Pas de migration DB (étape 1)
Les tables `news_raw`, `news_ticker_map`, `news_ingestion_checkpoint`, `news_sentiment`, etc. acceptent telles quelles `ingestion_source="finnhub"` / `source_name="finnhub_news"` / `article_id="finnhub:<id>"` (≤ 30 chars sur VARCHAR(128)). Checkpoints séparés par `source_name`. Coexistence Alpaca/Finnhub garantie via la clé unique `(ingestion_source, dedupe_hash)`.

### Vérifications passées
- `python -m event_sentiment --help` → expose `--news-provider`, `--ticker-relevance-mode`, `--max-tickers-per-article`
- 16 tests ciblés OK (4 Finnhub client + 7 provider seam + 2 pipeline runner sentiment + 1 e2e widget + 1 CLI summary + 1 ingestion routing déjà couvert)
- Les 2 échecs résiduels (`test_build_pipeline_command_ml_steps`, `test_signal_aggregator_main_emits_structured_summary`) **préexistaient** au refactor (non liés au périmètre Finnhub).

## ✅ Niveau 2/3 — Score de pertinence article→symbole (étape 2)

### Backend
- **`event_sentiment/relevance.py`** (nouveau) : scorer pure-Python déterministe (`score_article_symbol`) borné `[0,1]`. Composantes auditées : `company_name_hit`, `ticker_hit`, `is_primary`, pénalité multi-tickers. Constante `RELEVANCE_VERSION="v1"`, dataclass `RelevanceWeights` injectable.
- **`event_sentiment/ingestion.py`** : nouveau mode `"scored"` calcule `relevance_score` + `relevance_components` pour chaque paire `(article, symbole)`, applique le seuil `min_relevance_score` (filtrage avant insertion), enregistre les compteurs `relevance_scored` / `relevance_filtered` dans le summary.
- **`event_sentiment/aggregation.py`** : moyennes pondérées par `relevance_score` (`COALESCE → 1.0` rétro-compat) dans `build_ticker_daily_features` ; `relevance_weight_sum_*` exposé pour audit.
- **Migration `0027_news_ticker_map_relevance.py`** : ajoute `relevance_score FLOAT NULL` + `relevance_components JSON NULL` + index `idx_news_ticker_map_relevance`.

### CLI / IHM
- **CLI** : `--ticker-relevance-mode {provider_default,strict,scored}` + `--min-relevance-score`. Summary CLI étendu (`min_relevance_score`).
- **IHM** : selectbox du mode + `number_input` seuil dans `_render_event_sentiment_block` ; propagation vers `PipelineLaunchOptions.sentiment_ticker_relevance_mode` / `sentiment_min_relevance_score`.

### Tests
- `tests/test_event_relevance.py` (10 tests) — scorer déterministe, bornes, audit, insensibilité accents/casse.
- `tests/test_event_aggregation.py` étendu — moyennes pondérées, rétro-compat sans colonne.

---

## ✅ Niveau 4 — Re-scoring FinBERT contextualisé `(article, symbole)` (étape 3)

### Objectif
Le scoring FinBERT historique (table `news_sentiment`) produit **un score par article**, propagé tel quel à tous les tickers de `news_ticker_map`. Pour un article qui mentionne plusieurs sociétés (ex. « Apple beats earnings, suppliers Foxconn / TSMC under pressure »), cela attribue le **même** sentiment positif à AAPL et à TSM, alors que le contexte ticker-spécifique est ambigu pour TSM. Le **Niveau 4** produit un score FinBERT distinct par couple `(article, symbol)` en injectant un préfixe contextualisant le ticker dans le prompt.

### Stratégie de prompt (`scoring_version = "contextual_v1"`)
- `contextual_company` (par défaut) : `"For {company_name} ({SYMBOL}): {headline} [SEP] {summary}"`
- `contextual_symbol_only` : `"For {SYMBOL}: {headline} [SEP] {summary}"` (fallback si `company_name` absent)
- `contextual_headline_only` : minimal `"For {SYMBOL}: {headline}"` (fallback corps vide)

`scoring_version` est versionnée pour permettre une **invalidation et un re-scoring** en cas d'évolution (ex. `"contextual_v2"` avec extraction de phrases).

### Backend
- **`event_sentiment/models.py`** : nouveau dataclass `ContextualSentimentRecord` (mêmes champs que `SentimentRecord` + `symbol`, `scoring_version`).
- **`event_sentiment/scoring.py`** : nouvelle classe `ContextualFinBERTScorer(FinBERTSentimentService)` exposant `score_pairs(pairs: Iterable[tuple[NormalizedNewsArticle, str, str | None]])`. Réutilise `_infer_probabilities` + fallback CUDA→CPU de la classe parente ; seule la fabrique de texte change (`_choose_contextual_text`). `text_hash` distinct par symbole (différent prompt ⇒ digest différent).
- **`event_sentiment/config.py`** : trois nouveaux champs `EventSentimentConfig` :
  - `enable_contextual_scoring: bool = False` (opt-in)
  - `contextual_scoring_min_relevance: float = 0.0` (skip les paires sous le seuil — réutilise Niveau 2/3)
  - `contextual_scoring_max_pairs_per_run: int = 5000` (cap dur perf)
- **`event_sentiment/db_io.py`** :
  - `upsert_news_ticker_sentiment(records)` (clé `{article_id, symbol}`)
  - `load_pending_contextual_pairs(limit, min_relevance)` : LEFT JOIN sur `news_ticker_sentiment` pour ne renvoyer que les paires non-scorées, avec `company_name` lu depuis `stock_metadata`
  - `iter_ticker_map_for_relevance_backfill(...)` + `delete_ticker_map_below_score(...)` (helpers backfill, voir section suivante)
  - **`load_feature_frames`** modifié : `LEFT JOIN news_ticker_sentiment nts ON (nts.article_id, nts.symbol)` puis `COALESCE(nts.X, ns.X)` sur les six champs sentiment. **100% rétro-compatible** : si la table est vide, le comportement actuel est préservé bit-pour-bit.
- **`event_sentiment/pipeline.py`** : nouvelle étape `_run_contextual_scoring()` invoquée après `process_pending_sentiment` quand `enable_contextual_scoring=True`. Émet la phase `contextual_scoring` au `progress_callback`. Stats : `contextual_pairs_loaded`, `contextual_scored`, `contextual_min_relevance`, `contextual_cap`. Le scorer est instancié paresseusement (économie mémoire en mode legacy).

### CLI / IHM
- **CLI** : `--enable-contextual-scoring`, `--contextual-min-relevance`, `--contextual-max-pairs`. Summary enrichi (`contextual_pairs_loaded`, `contextual_scored`, `enable_contextual_scoring`, `contextual_scoring_min_relevance`, `contextual_scoring_max_pairs_per_run`).
- **IHM** : nouvel `expander` « Niveau 4 — Re-scoring FinBERT contextualisé (opt-in) » dans `_render_event_sentiment_block`. Checkbox + 2 number_inputs (`pipeline_sentiment_contextual_min_relevance` défaut `0.3`, `pipeline_sentiment_contextual_max_pairs` défaut `5000`). Propagation vers `PipelineLaunchOptions.sentiment_enable_contextual_scoring` / `sentiment_contextual_min_relevance` / `sentiment_contextual_max_pairs`. `pipeline_runner.build_pipeline_command("sentiment_pipeline", ...)` injecte les nouveaux flags.

### Migration DB
- **`alembic/versions/0028_news_ticker_sentiment.py`** + **`database/sql/news/news_ticker_sentiment.sql`** + ajout dans **`database/sql/news/init_event_sentiment.sql`**.
- Schéma `news_ticker_sentiment` :
  - PK composite `(article_id, symbol)`
  - FK `article_id → news_raw(article_id)` ON DELETE CASCADE
  - FK composite `(article_id, symbol) → news_ticker_map(article_id, symbol)` ON DELETE CASCADE
  - Indexes `idx_nts_symbol_label`, `idx_nts_net`, `idx_nts_fingerprint`, `idx_nts_scoring_version`
  - `scoring_version VARCHAR(30) DEFAULT 'contextual_v1'`, `model_fingerprint` NULLable (rétro-compat)

### Tests
- `tests/test_event_contextual_scoring.py` (6 tests) — `_choose_contextual_text` (3 stratégies), `score_pairs` (3 symboles → 3 records, `text_hash` distincts, `scoring_version`), early-return sur input vide. FinBERT mocké par stub déterministe (`_StubProbabilities` + monkeypatch `_infer_probabilities`).

### Garde-fous perf identifiés
1. **N×M tokenisations** : 1 article × K tickers ⇒ K appels FinBERT. Mitigations cumulables :
   - skip si `relevance_score < contextual_scoring_min_relevance` (recommandé `0.3` côté IHM)
   - cap dur `contextual_scoring_max_pairs_per_run` (défaut `5000`)
   - réutilisation du `batch_size` FinBERT existant pour grouper les prompts
2. **Désactivé par défaut** (`enable_contextual_scoring=False`) ⇒ aucun changement comportemental sans opt-in explicite CLI/IHM.

---

## ✅ Backfill batch — `event_sentiment.relevance_backfill` (étape 4)

### Objectif
Permettre l'application rétroactive du scoring de pertinence (Niveau 2/3) **et** du re-scoring FinBERT contextualisé (Niveau 4) sur les lignes `news_ticker_map` historiques (créées avant l'activation des Niveaux 2/3/4). Exposé en CLI **et** depuis l'IHM (étape pipeline `relevance_backfill`).

### Module
- **`event_sentiment/relevance_backfill.py`** (nouveau, exécutable via `python -m event_sentiment.relevance_backfill`) :
  - Classe `RelevanceBackfillService` avec deux phases indépendantes :
    1. `backfill_relevance(batch_size, start_date, end_date, symbols, dry_run, rescore_all)` — itère paginé via `iter_ticker_map_for_relevance_backfill` (default : `relevance_score IS NULL`), recalcule `relevance_score` + `relevance_components`, upsert. `--rescore-all` recalcule aussi les lignes déjà scorées (utile après évolution des poids).
    2. `backfill_contextual(batch_size, min_relevance, max_pairs, dry_run)` — paires sans entrée `news_ticker_sentiment`, charge FinBERT contextuel, persiste.
  - Méthode auxiliaire `purge_below(threshold, ...)` — DELETE des lignes `news_ticker_map.relevance_score < seuil` (FK CASCADE supprime aussi `news_ticker_sentiment` associé).
  - Émission `::alpha_trade_run_summary::` JSON consommable par le parser commun IHM (compteurs `relevance_scanned`, `relevance_rescored`, `relevance_purged`, `contextual_pairs_loaded`, `contextual_scored`, `duration_seconds`, `dry_run`, `run_id`).

### CLI
| Flag | Effet |
| --- | --- |
| `--batch-size 500` | Taille des batchs SQL paginés |
| `--start-date / --end-date YYYY-MM-DD` | Filtre par `effective_trade_date` |
| `--symbols AAPL,MSFT` | Restreint à un sous-univers |
| `--dry-run` | Aucun écriture DB (logs + summary uniquement) |
| `--rescore-all` | Recalcule même les lignes déjà scorées |
| `--purge-below 0.2` | Supprime les paires avec `relevance_score < 0.2` |
| `--rescore-contextual` | Phase 2 — déclenche le scoring FinBERT contextuel |
| `--contextual-min-relevance 0.3` | Seuil min pour activer le scoring contextuel |
| `--contextual-max-pairs 5000` | Cap dur du nombre de paires scorées |

### IHM
- **`pipeline_runner.py`** : nouvelle `PipelineStepDefinition(key="relevance_backfill", num="7bis", ...)` (déps : `sentiment_pipeline`). Champs `RunOptions` ajoutés : `backfill_relevance_dry_run / rescore_all / rescore_contextual / purge_below / batch_size`. `build_pipeline_command("relevance_backfill", ...)` construit `python -m event_sentiment.relevance_backfill ...` en réutilisant `sentiment_start_utc / end_utc / symbols`.
- **`_render_event_sentiment_block`** : nouvel `expander` « 7bis — Backfill relevance / contextual » qui collecte `dry_run`, `rescore_all`, `rescore_contextual`, `batch_size`, `purge_below`, propage vers `PipelineLaunchOptions`.

### Tests
- `tests/test_event_relevance_backfill.py` (5 tests) — repository fake + FinBERT mocké :
  - `backfill_relevance` : dry-run sans écriture / écriture effective / payload bien formé (relevance_score borné, components dict)
  - `purge_below` : dry-run renvoie 0 / appel réel renvoie compteur
  - `backfill_contextual` : dry-run skip FinBERT, renvoie compteurs cohérents

### Documentation
- `doc/event_sentiment.md` mis à jour (schéma `news_ticker_sentiment`, mode `enable_contextual_scoring`, CLI `relevance_backfill`).
- `doc/INDEX.md` / `doc/database.md` : entrées mises à jour.

### Vérifications passées
- 41/41 tests `event_sentiment` passent (31 historiques + 10 nouveaux : 6 Niveau 4 + 5 backfill — 1 commun avec relevance).
- Migration `0028_news_ticker_sentiment` symétrique (upgrade/downgrade), `down_revision = "0027_news_ticker_map_relevance"`.
- Aucun changement comportemental sans opt-in : `enable_contextual_scoring=False` par défaut, `LEFT JOIN ... COALESCE` rétrocompatible sur `load_feature_frames`.
