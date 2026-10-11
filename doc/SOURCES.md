# Traçabilité de la refonte documentaire

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Méthode

La première refonte ci-dessous est une trace historique. Elle est complétée
par la [révision de tout le corpus du 10 octobre 2026](AUDIT_COMPLET_DOCUMENTATION_20261010.md).
Le [registre](audit/registre_documentaire.md) classe tous les fichiers ; les
[empreintes AST](audit/inventaire_sources.json) localisent les déclarations courantes.

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
- persistance : `database/`, `alembic/`, `alembic_cn/`, `alembic_fr/`, `database/router.py` ;
- IHM : `ihm/` ;
- dépendances et outils : `pyproject.toml`, `pytest.ini`, `.importlinter` ;
- configuration runtime : `config.yaml`, `config_cn.yaml`, `config_fr.yaml`,
  contextes `config/markets`, router `config/databases.yaml` et dataclasses ;
- batchs : `batch.yaml`, `batch_cn.yaml`, `batch_fr.yaml`,
  `ihm/services/batch_management.py` et launchers Windows ;
- calendrier de signal US : `common/us_signal_date.py`, CLI et wrappers GPT ;
- maintenance documentaire : `scripts/refresh_documentation.py`,
  `scripts/generate_doc_index.py` (lecture statique, sans exécution métier).

## Limites et maintenance

La documentation décrit les contrats visibles dans le dépôt, pas l'état d'un broker, d'une base ou d'artefacts absents de l'espace de travail. Les valeurs expérimentales changent fréquemment : pour reproduire un run, conserver sa commande, sa configuration effective, son batch, ses fingerprints et son commit.

### Traitement des documents expérimentaux historiques

Les documents de type benchmark B0–B44, campagnes Oracle, diagnostics semestriels, recherches DIP, ablations, calibration et essais de paramètres ont été lus comme archives. Ils ne sont pas incorporés intégralement. Seuls les sujets encore représentés dans le code courant sont cités dans `research/`, sous forme de synthèse sans reprendre les résultats détaillés. Les verdicts historiques ne priment jamais sur le comportement du code et de la configuration actuels.
