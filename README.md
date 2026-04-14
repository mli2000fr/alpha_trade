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

## Prerequis

Variables d'environnement MySQL:

- `LOGIN_DB`
- `PASSWORD_DB`

## Installation

```powershell
python -m pip install -r requirements.txt
```

## Execution du screener

```powershell
python -m dataIntegrityEngine.stock_screener
python -m dataIntegrityEngine.stock_screener --chunk-size 500 --max-workers 8 --benchmark SPY
```

## Test local rapide (sans DB)

```powershell
python tests/harness_screener.py
```

## Sortie DB

Le script recree `stock_scores` puis insere rapidement avec `to_sql(method='multi')`:

- `symbol`
- `liquidity_val`
- `relative_strength_index`
- `historical_range_score`
- `total_score`
- `last_updated`

