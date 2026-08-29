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

La commande `pytest` applique par défaut couverture lignes+branches sur tout le dépôt, rapport terminal/HTML/JSON et seuil global 70 %. Pour un diagnostic rapide sans ce coût, utiliser `--no-cov` explicitement ; ne pas présenter alors le run comme validation de couverture.

Marqueurs déclarés : `unit`, `integration`, `slow`, `e2e`, `property`, `formal`, `benchmark` et `live`. Les marqueurs sont stricts : une faute est une erreur de collecte. Exemples :

```powershell
pytest -m unit --no-cov
pytest -m "integration and not live"
pytest -m formal
pytest -m e2e
```

Les tests `live` nécessitent un service externe et ne doivent pas être lancés contre un compte live réel sans environnement isolé. Les intégrations MySQL utilisent une base dédiée ; ne jamais pointer les fixtures destructives vers la base opérationnelle.

## Pyramide attendue

- unités pures pour calculs, règles, normalisation et transitions ;
- contrats pour CLI, schémas, features et interfaces ;
- intégration pour repositories/providers mockés ;
- parité live/backtest ;
- end-to-end paper/simulate limité ;
- tests de propriété/fuzz pour invariants financiers.

Les fonctions pures de calcul n’utilisent ni réseau ni DB. Les adapters providers sont testés avec réponses enregistrées/mocks couvrant pagination, timeout et payload invalide. Les CLI sont testés sur parsing, config effective, code retour et summary, pas seulement sur import.

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

## Qualité statique et architecture

`ruff` cible Python 3.12, longueur 120 et règles E/W/F/I/UP/B/C4/SIM. `mypy` tolère les imports tiers sans stubs mais vérifie le code typé. `.importlinter` interdit à `core` de dépendre des modules métier et limite les imports directs des clients providers ; quelques composition roots sont explicitement autorisés.

Les contrats d’import encore en xfail/warn-only ne doivent pas être interprétés comme inexistants : une nouvelle violation ne doit pas agrandir le backlog.

## Couverture, mutation et formal

`mutmut` cible `risk_management/`, `execution_engine/` et `corporate_actions/` avec runner sans couverture. Les mutants survivants indiquent souvent un invariant mal testé, mais certains sont équivalents et doivent être triés.

L’extra `formal` installe Z3. Une preuve marquée skipped faute de dépendance ne compte pas comme preuve exécutée. Les modèles TLA+ nécessitent leur propre outillage.

## Tests ML et backtest

Fixer seed, folds, batch, dates, univers et features. Les tests unitaires vérifient anti-fuite et transformations ; les performances statistiques ne doivent pas rendre la CI instable sur une base mutable. Les campagnes longues produisent un artefact/review séparé et leurs gates sont pré-déclarés.

## Checklist de revue

- aucun secret ou credential de test commité ;
- aucune dépendance réseau dans une unité ;
- timezone/date et PIT couverts ;
- idempotence testée sur double appel ;
- account id couvert en multi-compte ;
- nouvelles tables migrées et rollback évalué ;
- nouveau flag testé dans CLI, YAML et IHM si exposé ;
- summary/reason codes vérifiés ;
- documentation thématique et API mises à jour.

## Documentation

Les fichiers historiques hors `doc/refactor/` ne sont plus la référence maintenue. Lors d'un changement, mettre à jour le document thématique correspondant et vérifier les liens de l'index.
