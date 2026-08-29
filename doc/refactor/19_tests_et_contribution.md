# Tests, qualité et contribution

## Suites

`tests/` couvre unités, contrats, intégrations DB, CLI, parité, risk/execution, ML et IHM. `formal/` contient des vérifications Z3/TLA+ ou invariants institutionnels. Les tests de mutation ciblent surtout risque, exécution et corporate actions.

## Commandes

```powershell
pytest
pytest tests/<fichier>.py -q
pytest -x -q --no-cov
ruff check .
mypy .
```

Consulter `pytest.ini` pour marqueurs, timeout et couverture. `docker-compose.test.yml` fournit l'environnement DB de test lorsque nécessaire.

## Pyramide attendue

- unités pures pour calculs, règles, normalisation et transitions ;
- contrats pour CLI, schémas, features et interfaces ;
- intégration pour repositories/providers mockés ;
- parité live/backtest ;
- end-to-end paper/simulate limité ;
- tests de propriété/fuzz pour invariants financiers.

## Invariants critiques

- aucune fuite future ;
- publication d'univers atomique ;
- une application de dividende au plus ;
- conservation de valeur lors d'un split ;
- aucune quantité négative involontaire ;
- réponse d'ordre différente d'un fill ;
- réexécution idempotente ;
- limites de risque jamais dépassées par arrondi ;
- cash-only n'ouvre aucune position ;
- compte paper/live non ambigu.

## Processus de changement

1. localiser le propriétaire métier et les contrats ;
2. écrire/adapter le test qui exprime le comportement ;
3. modifier le minimum de couches ;
4. exécuter tests ciblés puis transverses ;
5. comparer schéma/config/CLI ;
6. documenter migration et rollback ;
7. pour une stratégie, respecter protocole OOS et promotion.

## Documentation

Les fichiers historiques hors `doc/refactor/` ne sont plus la référence maintenue. Lors d'un changement, mettre à jour le document thématique correspondant et vérifier les liens de l'index.

