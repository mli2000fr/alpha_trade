# Alpha Trade - Stock Screener

Screener Swing Trade haute performance (Python + MySQL) avec pipeline en 3 passages:

1. Liquidite sur les 30 dernieres barres (`volume * close`).
2. Force relative sur 6 mois versus benchmark (par defaut `SPY`, charge une seule fois).
3. Position du dernier close dans le range 10 ans (score 0..100).

Le screener lit desormais la table `stock_bars_daily` (donnees daily nettoyees/alignees), et non plus directement `stock_bars`.

Le pipeline est execute en chunks de symboles (500 par defaut) et parallelise via `ProcessPoolExecutor`.

## Fichiers

- `dataIntegrityEngine/stock_screener.py`: orchestrateur principal.
- `dataIntegrityEngine/screener/db_io.py`: lecture/ecriture SQLAlchemy + PyMySQL.
- `dataIntegrityEngine/screener/pipeline.py`: calculs pandas vectorises.
- `dataIntegrityEngine/screener/models.py`: configuration centralisee.
- `tests/harness_screener.py`: harness local sans DB.
- `tests/harness_data_sanitizer.py`: smoke test local du sanitizer sans DB.

## Prerequis

Variables d'environnement MySQL:

- `LOGIN_DB`
- `PASSWORD_DB`

Variables d'environnement Finnhub:

- `FINNHUB_API_KEY` (ou `CLE_FINNHUB` pour compatibilité)

## Installation

```powershell
python -m pip install -r requirements.txt
```

## Execution du screener

```powershell
python -m dataIntegrityEngine.stock_screener
python -m dataIntegrityEngine.stock_screener --chunk-size 500 --max-workers 8 --benchmark SPY
```

## Mise a jour des secteurs depuis Finnhub

```powershell
python -m dataIntegrityEngine.update_sector
python -m dataIntegrityEngine.update_sector --limit 100 --sleep-seconds 1.1 --log-every 25
```

Le script lit les symboles de `stock_metadata` dont `sector` est vide, appelle Finnhub pour chaque symbole, puis met a jour `stock_metadata.sector` avec des logs de progression.

## Pipeline Event Sentiment (module 2)

Le module `event_sentiment` ingere les news fournisseur, aligne chaque evenement sur la bonne date de trading NYSE, applique un scoring FinBERT, enrichit les tickers/secteurs, calcule les macro impacts explicables, puis agrege les features journalieres par ticker et par secteur.

Schemas SQL associes:

- `database/sql/news/news_raw.sql`
- `database/sql/news/news_sentiment.sql`
- `database/sql/news/news_ticker_map.sql`
- `database/sql/news/macro_event_audit.sql`
- `database/sql/news/ticker_daily_sentiment_features.sql`
- `database/sql/news/sector_daily_sentiment_features.sql`
- `database/sql/news/news_ingestion_checkpoint.sql`

Execution:

```powershell
python -m event_sentiment
python -m event_sentiment --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z --symbols AAPL,MSFT,NVDA
python -m dataIntegrityEngine.event_sentiment_pipeline
```

Tests cibles du module:

```powershell
python -m pytest tests/test_event_temporal_alignment.py tests/test_event_macro_rules.py tests/test_event_aggregation.py tests/test_finbert_preprocessor.py
```

## Test local rapide (sans DB)

```powershell
python -m pytest
python tests/harness_screener.py
python tests/harness_data_sanitizer.py
```

## Sortie DB

Le script applique un upsert snapshot sur `stock_scores` : insertion/mise a jour des symboles calcules, puis purge des symboles absents du snapshot courant.

- `symbol`
- `liquidity_val`
- `relative_strength_index`
- `historical_range_score`
- `total_score`
- `last_updated_score`
- `is_candidate`
- `sector`
- `last_updated_scan`

## execution
# en une fois
import_alpaca_assets.py
update_sector.py


# au quotidien
import_alpaca_bar.py
data_sanitizer_daily.py

# une fois par mois
stock_screener.py

# au quotidien ou par semaine — dans cet ordre strict :
#  1. alpha_scanner.py       → scores quantitatifs (trend, vcp, final_score) SANS sentiment
#  2. sentiment_pipeline.py  → news → FinBERT → ticker_daily_features / sector_daily_features
#  3. signal_aggregator.py   → fusion quant + sentiment → final_score définitif dans stock_scores

python -m event_sentiment.signal_aggregator
python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
python -m event_sentiment.signal_aggregator --sentiment-weight 0.20 --macro-weight 0.10 --lookback-days 5

# Note : ne PAS utiliser --enable-sentiment dans alpha_scanner.py quand signal_aggregator.py
# est exécuté séparément (évite une double application du boost sentiment).

#  4. risk_management        → gestion de risque, sizing, portefeuille cible
python -m risk_management
python -m risk_management --account-equity 100000 --max-positions 10 --dry-run
python -m risk_management --trade-date 2026-04-17 --log-level DEBUG
```

## Module Gestion de Risque

Le package `risk_management/` s'exécute **après** `signal_aggregator.py`. Il :

1. Lit les candidats (`is_candidate = 1`) depuis `stock_scores`, triés par `final_score_sentiment` décroissant (score fusionné quant + sentiment, déjà calculé par `signal_aggregator`).
2. Calcule la taille de position via ATR(20) avec fallback equal-weight.
3. Vérifie les contraintes de risque (max positions, poids position/secteur, exposition brute, circuit breaker drawdown/daily loss).
4. Construit le portefeuille cible et journalise chaque décision dans `risk_decisions` et `portfolio_targets`.

Schémas SQL : `database/sql/risk/risk_decisions.sql`, `database/sql/risk/portfolio_targets.sql`.

Tests :

```powershell
python -m pytest tests/test_position_sizer.py tests/test_constraints.py tests/test_circuit_breaker.py tests/test_risk_checker.py tests/test_portfolio_builder.py

