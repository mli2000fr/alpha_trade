# Installation et démarrage

## Prérequis

- Python 3.12 ou supérieur ;
- MySQL accessible ;
- compte Alpaca paper au minimum ;
- EODHD recommandé pour les OHLCV ;
- Finnhub, SEC/FRED/Stooq/Yahoo selon les fonctions utilisées.

Installation développeur :

```powershell
python -m pip install -e ".[dev]"
```

Les extras utiles sont `observability`, `ml-challengers`, `formal`, `reporting`, `lineage`, `cache`, `async-db`, `security`, `mutation` et `orchestration`.

## Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "..."
$env:PASSWORD_DB = "..."
$env:ALPACA_API_KEY = "..."
$env:ALPACA_SECRET_KEY = "..."
$env:EODHD_API_TOKEN = "..."       # si provider EODHD
$env:FINNHUB_API_KEY = "..."       # selon calendrier/fondamentaux
```

Ne jamais remplacer les placeholders de `config.yaml` par des secrets en clair. `core.secrets` scanne les YAML et rejette les valeurs faibles ou sentinelles.

## Base de données

Appliquer les migrations :

```powershell
alembic upgrade head
```

Le helper `database/sql/all_tables.py` sait également exécuter les DDL historiques, mais Alembic est le mécanisme de versionnement à privilégier pour un environnement maintenu.

## Bootstrap des données

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.update_sector
```

Pour un historique EODHD long, utiliser `dataIntegrityEngine.backfill_eodhd_history`; le mode par défaut est défensif/dry-run et l'écriture doit être demandée explicitement.

## Lancer l'IHM

```powershell
python run.py
```

Le lanceur vérifie Streamlit. Un lancement direct reste possible via `streamlit run ihm/app.py`. L'IHM est une console locale d'orchestration et de supervision, pas un serveur multi-tenant exposé par défaut.

## Première validation

1. Vérifier la connexion DB et la présence des tables.
2. Vérifier le compte Alpaca sélectionné et son mode paper/live.
3. Exécuter les imports de bootstrap.
4. Lancer les étapes 1 à 6 et contrôler qu'un univers `full` est publié.
5. Vérifier qu'un champion ML compatible existe avant `ml_predict`.
6. Exécuter risque puis `run_execution.py simulate`.
7. Ne passer en paper qu'après réconciliation sans anomalie.

## Commandes de qualité

```powershell
pytest
ruff check .
mypy .
```

Les tests peuvent nécessiter une base dédiée et des variables d'environnement de test. Lire `pytest.ini`, `docker-compose.test.yml` et les fixtures avant d'exécuter une suite d'intégration.

