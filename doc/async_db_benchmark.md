# Async DB benchmark — Sprint S28.4 / A10

- rows seeded : **500**
- runs per loader : **3**
- sync DSN : `sqlite:///:memory:`
- async DSN : `sqlite+aiosqlite:///:memory:`

## Résultats (médiane, secondes)

| Loader | Sync | Async | Δ % | Cible |
|---|---:|---:|---:|---:|
| market | 0.0007 | 0.0014 | -100.7 % | ≥ 30 % |
| scores | 0.0002 | 0.0008 | -359.5 % | ≥ 30 % |
| orders | 0.0001 | 0.0008 | -439.4 % | ≥ 30 % |

> Méthodologie : sqlite in-memory (CI), même schéma seedé sur les 2 engines.
> Pour reproduire en prod (asyncpg/Postgres) : passer `--dsn` et `--sync-dsn`.
