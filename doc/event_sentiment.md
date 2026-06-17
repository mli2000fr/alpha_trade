# Event Sentiment — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `event_sentiment/` et les commandes utiles pour :

- ingérer des news financières depuis EODHD Financial News Feed, Alpaca News ou Finnhub,
- scorer les articles avec FinBERT,
- produire des features journalières par ticker et par secteur,
- fusionner le signal sentiment avec les scores quantitatifs dans `stock_scores`.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `event_sentiment/__init__.py` | Package Python |
| `event_sentiment/__main__.py` | Point d'entrée `python -m event_sentiment` |
| `event_sentiment/cli.py` | CLI du pipeline principal |
| `event_sentiment/pipeline.py` | Orchestrateur `EventSentimentPipeline` |
| `event_sentiment/sentiment_pipeline.py` | Pipeline principal de scoring sentiment |
| `event_sentiment/event_sentiment_pipeline.py` | Pipeline complet d'événements + sentiment |
| `event_sentiment/ingestion.py` | Ingestion et normalisation des news provider (`EODHD` / `Alpaca` / `Finnhub`) |
| `event_sentiment/importe_news.py` | Import des news brutes |
| `event_sentiment/scoring.py` | Scoring FinBERT |
| `event_sentiment/macro_rules.py` | Détection de règles macro / événements majeurs |
| `event_sentiment/aggregation.py` | Agrégations journalières ticker / secteur |
| `event_sentiment/signal_aggregator.py` | Fusion quant + sentiment → `final_score_sentiment` |
| `event_sentiment/relevance.py` | Calcul de pertinence article→ticker |
| `event_sentiment/relevance_backfill.py` | Backfill de la pertinence |
| `event_sentiment/history_backfill.py` | Backfill historique du sentiment |
| `event_sentiment/db_io.py` | Accès base de données du module |
| `event_sentiment/trading_calendar.py` | Alignement temporel vers séance de trading |
| `event_sentiment/mapping.py` | Résolution ticker → secteur |
| `event_sentiment/models.py` | Modèles de données news / sentiment |
| `event_sentiment/config.py` | Configuration du module |

---

## 2. Prérequis

### 2.1 Pour exécuter le pipeline news + FinBERT

#### Versionnement FinBERT (Phase 4.1.c)

Chaque ligne `news_sentiment` est tracée par la colonne `model_fingerprint`
(`SHA256[:16]` de `model_name + revision + max_length + model_version`).
Pour épingler le checkpoint Hugging Face :

```powershell
python -m event_sentiment --finbert-revision <commit_sha_ou_tag>
```

Le `run_summary` du pipeline expose `finbert_model_fingerprint`. Le
`run_summary` de `signal_aggregator` expose `finbert_model_fingerprints`
(liste agrégée sur la fenêtre de 30 jours précédant la `trade_date`).

> **Providers supportés** : `eodhd`, `alpaca`, `finnhub`.
> **Défaut actuel** : `eodhd` (`source_name = eodhd_news`, `provider_name = eodhd`).
> Backlog : SEC EDGAR 8-K (cf. `audit_global.md` Long terme).

#### Obligatoires


- `stock_scores` avec des candidats (`is_candidate = 1`) si aucun symbole n'est passé explicitement
- `news_raw`
- `news_ticker_map`
- `news_sentiment`
- `macro_event_audit`
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`
- `news_ingestion_checkpoint`

#### Optionnelle / activée par migration Niveau 4

- `news_ticker_sentiment` (requise uniquement si `--enable-contextual-scoring` ou si l'on veut exploiter le backfill contextuel)

#### Variables d'environnement requises

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

Selon le provider de news choisi :

- mode `--news-provider alpaca` :

```powershell
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
```

- mode `--news-provider finnhub` :

```powershell
$env:FINNHUB_API_KEY = "..."
```

- mode `--news-provider eodhd` *(défaut recommandé)* :

```powershell
$env:EODHD_API_TOKEN = "..."
```

#### Dépendances externes utiles

- accès réseau au provider de news utilisé (`EODHD`, `Alpaca News` ou `Finnhub`)
- téléchargement du modèle HuggingFace `ProsusAI/finbert`

### 2.2 Pour exécuter seulement la fusion `signal_aggregator`

#### Obligatoires

- `stock_scores`

#### Optionnelles mais fortement recommandées

- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

Le module est tolérant :

- si les tables sentiment sont absentes, la fusion continue avec un signal neutre ;
- si peu de news existent sur la fenêtre, le boost sentiment reste neutre ;
- le score quantitatif `final_score` n'est jamais supprimé.

---

## 3. Commandes utiles

### Pipeline complet event sentiment

```powershell
python -m event_sentiment
python -m event_sentiment --news-provider eodhd
```

### Pipeline borné sur une fenêtre UTC

```powershell
python -m event_sentiment --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z
```

### Pipeline limité à quelques symboles

```powershell
python -m event_sentiment --symbols AAPL,MSFT,NVDA
```

### Basculer explicitement de provider news

```powershell
python -m event_sentiment --news-provider eodhd
python -m event_sentiment --news-provider alpaca
python -m event_sentiment --news-provider finnhub
```

### Fusion quant + sentiment sur les seuls candidats

```powershell
python -m event_sentiment.signal_aggregator
```

### Fusion quant + sentiment sur tous les symboles et une date donnée

```powershell
python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
```

### Ajuster les poids de fusion

```powershell
python -m event_sentiment.signal_aggregator --sentiment-weight 0.20 --macro-weight 0.10 --lookback-days 5 --min-news-count 2
```

### Activer le scoring de pertinence article → ticker (Niveau 2/3)

```powershell
python -m event_sentiment --news-provider eodhd --ticker-relevance-mode scored --min-relevance-score 0.30
```

### Activer le re-scoring FinBERT contextualisé `(article, symbole)` (Niveau 4)

```powershell
python -m event_sentiment --news-provider eodhd --ticker-relevance-mode scored --min-relevance-score 0.30 --enable-contextual-scoring --contextual-min-relevance 0.30 --contextual-max-pairs 5000
```

### Backfill historique `relevance_score` / `news_ticker_sentiment`

```powershell
python -m event_sentiment.relevance_backfill --dry-run --batch-size 500 --start-date 2026-01-01 --end-date 2026-01-31
python -m event_sentiment.relevance_backfill --batch-size 500 --start-date 2026-01-01 --end-date 2026-01-31 --rescore-contextual --contextual-min-relevance 0.30
```

### Appliquer les migrations Alembic `0027` puis `0028`

> Les fichiers `alembic/versions/0027_news_ticker_map_relevance.py` et `alembic/versions/0028_news_ticker_sentiment.py` ne se lancent pas directement avec `python <fichier>`. Il faut viser leurs **identifiants de révision Alembic**.
>
> Si `from alembic.config import Config` échoue dans votre venv, installe d'abord les dépendances dev du projet (`pip install -e ".[dev]"`) ou au minimum `alembic`.

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

```powershell
$code = @"
from alembic.config import Config
from alembic import command
from database.connection import get_database_url

cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', get_database_url())
command.upgrade(cfg, '0027_news_ticker_map_relevance')
"@
python -c $code
```

```powershell
$code = @"
from alembic.config import Config
from alembic import command
from database.connection import get_database_url

cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', get_database_url())
command.upgrade(cfg, '0028_news_ticker_sentiment')
"@
python -c $code
```

### Formule de fusion ternaire (Phase 4.1.b)

Depuis Phase 4.1.b, la formule de fusion `final_score_sentiment` est
**centralisée** dans `core.conviction.fuse_sentiment` ; `signal_aggregator`
ne fait que déléguer :

```python
from core.conviction import fuse_sentiment
from event_sentiment.signal_aggregator import SentimentBoostConfig

config = SentimentBoostConfig()
final = fuse_sentiment(
    quant_score=...,
    sentiment_signal_norm=...,
    macro_signal_norm=...,
    weights=config.to_fusion_weights(),
    signal_active=...,
)
```

Les colonnes intermédiaires (`quant_component`, `company_idio_component`,
`macro_regime_component`) restent reconstruites localement par `merge`
pour préserver le contrat consommé par `save_to_db` et l'IHM. Pour les
détails de la formule, voir `doc/core_common.md` § "Fusion sentiment ternaire".

### Correspondance avec l'IHM

Depuis `ihm/pages/pipeline.py`, le workflow quotidien 1→14 lance bien ensuite :

```powershell
python -m event_sentiment ...
python -m event_sentiment.signal_aggregator ...
```

L'IHM expose désormais les options backend réellement supportées par ces deux points d'entrée.

Pour `sentiment_pipeline` (step 7 IHM canonique), le lancement n'appelle plus un unique `python -m event_sentiment`, mais une chaîne fixe :

1. `event_sentiment/importe_news.py` sur `stock_scores_all` ;
2. `python -m event_sentiment.relevance_backfill` sur les **candidats** (ou override CSV) ;
3. `python -m event_sentiment --skip-ingestion --skip-features --scoring-mode standard_only` sur les **candidats** (ou override CSV) ;
4. `python -m event_sentiment --skip-ingestion --skip-features --scoring-mode contextual_only` sur les **candidats** (ou override CSV) ;
5. `python -m event_sentiment.history_backfill --ingestion-source <provider> --ticker-symbol-source candidates` pour reconstruire `ticker_daily_sentiment_features` côté candidats et `sector_daily_sentiment_features` sur le scope large importé.

Les paramètres exposés côté IHM restent :

- `--start-utc`
- `--end-utc`
- `--symbols`
- `--news-provider`
- `--ticker-relevance-mode`
- `--min-relevance-score`
- `--scoring-mode contextual_only`
- `--enable-contextual-scoring`
- `--contextual-min-relevance`
- `--contextual-max-pairs`
- `--sentiment-pending-limit`
- `--sentiment-pending-max-batches`
- `--feature-flush-every-n-batches`
- `--finbert-batch-size`

Points importants :

- dans le step 7 IHM, si `symbols` est laissé vide, **les sous-étapes ciblées candidats** rechargent automatiquement `stock_scores.is_candidate = 1`, alors que l'**import brut canonique** reste piloté sur `stock_scores_all` ;
- les dates UTC restent optionnelles : sans fenêtre explicite, le backend retombe sur sa logique de checkpoints/backfill.
- le mode de pertinence `scored` active le stockage de `relevance_score` / `relevance_components` dans `news_ticker_map` ;
- le step 7 IHM exécute désormais toujours la chaîne canonique **import large → relevance candidats → standard candidats → contextual candidats → features ticker candidats / secteur large** ; les replays ciblés continuent de passer par `7.bis` ;
- `contextual_scoring_max_pairs_per_run` est un cap **par run** : si vous laissez `5000`, le run score au plus `5000` paires contextuelles puis un run suivant reprend le lot suivant tant qu'il reste des couples absents de `news_ticker_sentiment` ;
- la case `Ajouter le contextual à ce backfill 7bis` du bloc `7bis — Backfill relevance / contextual` n'est pas un doublon de ce mode : elle ajoute seulement `--rescore-contextual` au CLI dédié `python -m event_sentiment.relevance_backfill` ;
- ordre recommandé en IHM pour enrichir un historique existant : `Contextual only` puis `Rebuild daily sentiment features only`, puis éventuellement `signal_aggregator`.

Le workflow complet IHM **n'inclut plus automatiquement** ce step `7bis` : il reste disponible comme outil auxiliaire pour rejouer la pertinence article→symbole et, si activé, le contextual sur un historique déjà importé.

Pour `signal_aggregator` (`python -m event_sentiment.signal_aggregator`) :

- `--trade-date`
- `--all-symbols`
- `--sentiment-weight`
- `--macro-weight`
- `--lookback-days`
- `--min-news-count`
- `--time-decay-half-life-days`
- `--log-level`

L'IHM calcule implicitement le poids quantitatif comme `1 - sentiment_weight - macro_weight`, exactement comme le backend. Si la somme `sentiment + macro` dépasse `1.0`, le backend rejettera le lancement.

---

## 4. Ce que fait le pipeline

### 4.1 Résolution de l'univers

Pour le CLI nu `python -m event_sentiment`, si `--symbols` n'est pas fourni, `EventSentimentPipeline` charge les symboles candidats depuis `stock_scores` avec `is_candidate = 1`.

⚠️ Le step 7 IHM canonique applique désormais un contrat différent : **import brut large sur `stock_scores_all`**, puis **phases ticker/contextual ciblées candidats** via des flags explicites au moment de construire chaque sous-commande.

### 4.2 Résolution des fenêtres temporelles

Le pipeline utilise `news_ingestion_checkpoint` pour :

1. reprendre au watermark précédent ;
2. ajouter un overlap configurable ;
3. forcer un backfill plus large si un symbole réapparaît après une longue période.

### 4.3 Ingestion et normalisation des news

`NewsIngestionService` :

1. appelle le provider de news configuré (`EODHD`, `Alpaca` ou `Finnhub`) ;
2. normalise les payloads ;
3. aligne l'article sur une séance de trading effective ;
4. construit les lignes `news_raw` et `news_ticker_map` ;
5. en mode `scored`, calcule `relevance_score` / `relevance_components` par couple `(article, symbole)` avant insertion.

### 4.3.1 Spécificités EODHD

- endpoint utilisé : `GET /news` côté EODHD ;
- pagination encapsulée via un `next_token` synthétique basé sur `offset` ;
- symboles provider normalisés via `service.eodhd.symbols.from_eodhd`, qui retourne bien un tuple `(project_symbol, exchange)` ;
- exemple : `AAPL.US -> ("AAPL", "US")`, `BRK-B.US -> ("BRK.B", "US")` ;
- les métadonnées provider `tags` et `sentiment` sont conservées dans `news_raw.raw_payload` pour audit ;
- le sentiment EODHD reste **audit-only** : FinBERT demeure la source de vérité pour `news_sentiment`.

### 4.3.2 Politique de persistance

- pas de migration DB spécifique requise pour EODHD ;
- le mapping canonique article → symbole reste `news_ticker_map` ;
- `news_raw` ne matérialise pas de colonnes dédiées `symbols` / `tags` ;
- ces données restent disponibles dans `raw_payload`.

### 4.4 Scoring et macro

Ensuite le pipeline :

1. charge les articles pending ;
2. applique FinBERT ;
3. persiste `news_sentiment` ;
4. si activé, re-score les couples `(article, symbole)` dans `news_ticker_sentiment` ;
5. génère des lignes `macro_event_audit`.

### 4.5 Agrégations journalières

Le pipeline calcule ensuite :

- les features ticker dans `ticker_daily_sentiment_features` ;
- les features secteur dans `sector_daily_sentiment_features`.

### 4.6 Fusion avec les scores quantitatifs

`SentimentSignalAggregator` charge `stock_scores` puis calcule :

- une composante quant par défaut à 75 % ;
- une composante sentiment ticker à 15 % ;
- une composante macro sectorielle à 10 %.

Le résultat est écrit dans `stock_scores.final_score_sentiment` avec des colonnes d'audit comme :

- `sentiment_net_agg`
- `sector_impact_agg`
- `signal_active`
- `total_news`
- `final_score_sentiment`

---

## 5. Pourquoi le module peut produire peu ou pas de signal

### 5.1 Aucun symbole traité

Causes probables :

1. `stock_scores` ne contient aucun `is_candidate = 1` ;
2. aucun symbole explicite n'a été passé ;
3. la fenêtre temporelle résolue ne couvre rien d'utile.

### 5.2 Aucun boost sentiment visible

Causes probables :

1. trop peu d'articles sur la fenêtre (`min_news_count`) ;
2. tables `ticker_daily_sentiment_features` ou `sector_daily_sentiment_features` absentes ;
3. signal neutralisé par manque de données ;
4. lancement du `signal_aggregator` avant le pipeline news.

### 5.3 Peu de news ingérées

Causes probables :

1. credentials du provider de news manquants (`EODHD_API_TOKEN`, `ALPACA_*` ou `FINNHUB_API_KEY` selon le mode) ;
2. fenêtre trop courte ;
3. checkpoints déjà avancés ;
4. symboles trop restrictifs.

Le point d'entrée `python -m event_sentiment` émet aussi un `run_summary` structuré sur stdout avec le préfixe :

- `::alpha_trade_run_summary::`

Champs notables :

- `resolved_symbols`
- `fetched_articles`
- `landed_articles`
- `sentiment_inferred`
- `macro_rows`
- `ticker_day_rows`
- `sector_day_rows`

Le point d'entrée `python -m event_sentiment.signal_aggregator` émet lui aussi un `run_summary` structuré, notamment avec :

- `loaded_symbols`
- `updated_symbols`
- `signal_active_symbols`
- `total_news`
- `avg_final_score_sentiment`
- `max_final_score_sentiment`

Ces résumés sont consommés côté IHM pour enrichir le centre d'exécution, `Overview` et `Screening`.

---

## 6. Vérifications utiles

### Import brut borné avec `importe_news.py`

Le script `event_sentiment/importe_news.py` n'importe plus implicitement tout `stock_bars_daily`.

Options utiles :

- `--symbol-source stock_scores` : défaut, recommandé ;
- `--symbol-source candidates` : univers `stock_scores.is_candidate=1` ;
- `--symbol-source stock_bars_daily` : ancien comportement large ;
- `--symbols AAPL,MSFT,NVDA` : shortlist explicite prioritaire ;
- `--max-symbols 500` : garde-fou qui refuse un univers trop volumineux.

Exemples :

```powershell
python event_sentiment/importe_news.py --start-date 2026-05-05 --end-date 2026-05-12
python event_sentiment/importe_news.py --start-date 2026-05-05 --end-date 2026-05-12 --news-provider eodhd
python event_sentiment/importe_news.py --start-date 2026-05-05 --end-date 2026-05-12 --symbol-source candidates --max-symbols 250
python event_sentiment/importe_news.py --start-date 2026-05-05 --end-date 2026-05-12 --symbols AAPL,MSFT,NVDA
```

### Vérifier le backfill `relevance_score`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT article_id, symbol, relevance_score FROM news_ticker_map WHERE relevance_score IS NOT NULL ORDER BY updated_at DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les scores contextuels `news_ticker_sentiment`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT article_id, symbol, scoring_version, sentiment_label, sentiment_net_score FROM news_ticker_sentiment ORDER BY updated_at DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les checkpoints news

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT source_name, symbol, status, watermark_published_at_utc FROM news_ingestion_checkpoint ORDER BY updated_at DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les features ticker récentes

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, trade_date, news_count_1d, sentiment_net_mean_1d FROM ticker_daily_sentiment_features ORDER BY trade_date DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier que la fusion a bien écrit dans `stock_scores`

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, final_score, final_score_sentiment, signal_active, total_news FROM stock_scores ORDER BY last_updated_sentiment DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés ingestion / scoring / agrégation

```powershell
python -m pytest tests/test_eodhd_symbols.py tests/test_eodhd_news_client.py tests/test_event_sentiment_news_provider.py tests/test_ingestion.py tests/test_scoring.py tests/test_event_aggregation.py tests/test_event_macro_rules.py tests/test_event_temporal_alignment.py -q -o addopts=""
```

### Tests ciblés pipeline et fusion

```powershell
python -m pytest tests/test_event_sentiment_importe_news.py tests/test_event_sentiment_run_summaries.py tests/test_ihm_pipeline_runner.py tests/test_ihm_pipeline_e2e.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. exécuter `python -m event_sentiment` ;
2. vérifier que les features journalières sont bien alimentées ;
3. lancer `python -m event_sentiment.signal_aggregator` ;
4. seulement ensuite lancer le module de risque ou le backtesting.

### Séquence recommandée

```powershell
python -m event_sentiment --news-provider eodhd --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z
python -m event_sentiment.signal_aggregator --trade-date 2026-04-17
```
