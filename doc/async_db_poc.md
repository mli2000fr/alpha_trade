# POC async DB I/O — asyncpg / aiosqlite (Phase F / S23.3)

> Cible : 3 loaders read-only chauds portés en async, parité résultat
> avec versions sync, **opt-in via env var** `ALPHA_TRADE_ASYNC_DB=1`
> (défaut OFF — fallback sync inchangé).

## Modules livrés

| Fichier | Rôle |
|---|---|
| [`database/async_engine.py`](../database/async_engine.py) | Factory `make_async_engine()` (asyncpg pour Postgres, aiosqlite pour SQLite). |
| [`database/async_loaders.py`](../database/async_loaders.py) | Versions async des 3 loaders read-only chauds. |
| [`tests/test_async_loaders.py`](../tests/test_async_loaders.py) | Parité résultat sync ↔ async (skipif aiosqlite absent). |

## Loaders async livrés (POC)

1. `fetch_market_data_async(symbols, start, end)` — historique OHLCV.
2. `fetch_scores_async(run_id)` — scores screener par run.
3. `fetch_open_orders_async(account_id)` — ordres ouverts (read-only).

## Activation

```powershell
$env:ALPHA_TRADE_ASYNC_DB = "1"
$env:ALPHA_TRADE_ASYNC_DSN = "sqlite+aiosqlite:///./alpha_trade.db"
python scripts/bench_full_pipeline.py --symbols 5000
```

Si l'env var est absente ou si `aiosqlite/asyncpg` ne sont pas installés,
le pipeline retombe automatiquement sur les loaders sync.

## Critère Phase F

| Métrique | Cible |
|---|---|
| p50 latence batch 5 000 symboles | −30 % vs sync |
| p95 | −30 % vs sync |
| Parité DataFrame sync ↔ async | 100 % (test) |

## Risques

- `asyncpg` requiert PostgreSQL ; en CI on utilise `aiosqlite` uniquement.
- Le toggle env var préserve la prod : aucune régression possible si OFF.
- Le code sync n'est pas dépublié : la migration complète sera décidée
  après audit du POC (Phase G).

## Dépendances

Optionnelles, ajoutées dans `requirements.txt` :

```
# Phase F / S23.3 — POC async DB I/O (opt-in via ALPHA_TRADE_ASYNC_DB=1)
aiosqlite>=0.19
asyncpg>=0.29 ; python_version >= "3.11"
```

