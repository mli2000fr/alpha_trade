# Accès base asynchrone — POC opt-in

## Statut

L’async n’est pas le chemin de production par défaut. `database/async_engine.py` ne l’active que lorsque `ALPHA_TRADE_ASYNC_DB` vaut `1`, `true`, `yes` ou `on`. Si toggle, SQLAlchemy asyncio, driver ou DSN manque, les helpers retournent `None`; l’appelant doit reprendre le chemin synchrone.

## Composants

- `database/async_engine.py` crée un `AsyncEngine` avec `pool_pre_ping=True` ;
- `ALPHA_TRADE_ASYNC_DSN` fournit le DSN ; `sqlite+aiosqlite:///:memory:` est le fallback de test ;
- `database/async_loaders.py` lit OHLCV, scores d’un run screener et ordres ouverts.

Les loaders sont read-only et ne forment pas une couche repository générale. Les valeurs SQL sont paramétrées. Le nom de table configurable doit rester une entrée contrôlée.

## Contrat de retour

- `[]` : requête valide sans résultat ou symboles vides ;
- `list[dict]` : lecture réussie ;
- `None` : async indisponible ou erreur, donc fallback sync obligatoire.

Ne jamais assimiler `None` à « aucune donnée ».

## Évaluation

Installer l’extra `async-db` de `pyproject.toml`, utiliser un DSN isolé, activer le toggle et lancer `tests/test_async_loaders.py`. Comparer contenu, ordre, erreurs et latence au chemin sync.

Les anciens benchmarks restent des résultats de POC. Une promotion demanderait intégration réelle aux call-sites, fallback observé, pool/timeouts/annulation, transactions, charge concurrente, parité MySQL et mesures reproductibles.

