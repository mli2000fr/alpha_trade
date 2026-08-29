# Traçabilité de la refonte documentaire

## Méthode

La refonte a inventorié l'ensemble de `doc/` (184 fichiers au démarrage) puis analysé les packages source, points d'entrée, classes/fonctions, configuration, migrations et tests. Les documents historiques ont été utilisés pour repérer vocabulaire, décisions et sujets, puis vérifiés contre le code.

## Sources canoniques par sujet

- pipeline : `ihm/services/pipeline_runner.py` ;
- orchestration optionnelle : `flows/daily_pipeline.py` ;
- données/univers : `dataIntegrityEngine/`, `common/tradable_universe.py`, `common/publish_tradable_universe.py` ;
- ML : `modelFactory/cli.py`, `config.py`, `orchestrator.py`, `features.py`, `labeling.py` ;
- ranking : `modelFactory/global_ranking.py` ;
- Oracle : `modelFactory/oracle/` ;
- risque : `risk_management/` ;
- régime : `service/market/` ;
- exécution : `run_execution.py`, `execution_engine/` ;
- backtest : `backtesting/` ;
- persistance : `database/`, `alembic/` ;
- IHM : `ihm/` ;
- dépendances et outils : `pyproject.toml`, `pytest.ini`, `.importlinter` ;
- configuration runtime : `config.yaml` et dataclasses de chaque package.

## Limites et maintenance

La documentation décrit les contrats visibles dans le dépôt, pas l'état d'un broker, d'une base ou d'artefacts absents de l'espace de travail. Les valeurs expérimentales changent fréquemment : pour reproduire un run, conserver sa commande, sa configuration effective, son batch, ses fingerprints et son commit.

