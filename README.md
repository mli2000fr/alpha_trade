# Alpha Trade - Stock Screener

Screener Swing Trade haute performance (Python + MySQL) avec pipeline en 3 passages:

1. Liquidite sur les 30 dernieres barres (`volume * close`).
2. Force relative sur 6 mois versus benchmark (par defaut `SPY`, charge une seule fois).
3. Position du dernier close dans le range 10 ans (score 0..100).

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

# une fois par mois
stock_screener.py

# au quoditien
import_alpaca_bar.py
data_sanitizer_daily.py


# au quoditien ou par semaine
alpha_scanner.py