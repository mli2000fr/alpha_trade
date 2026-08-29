# Stabilité de l’API v1 et dépréciation

## Objet

Cette référence décrit le contrat de compatibilité des façades Python du projet. Les noms explicitement exportés par les `__init__.py` sont les points d’entrée maintenus. Les inventaires du dossier `api/` facilitent la lecture du code, mais ne transforment pas tous les symboles importables en API stable.

## Compatibilité

Dans une même version majeure, un consommateur doit pouvoir continuer à appeler un symbole public avec les mêmes arguments obligatoires et interpréter son résultat. Ajouter un argument ou un champ optionnel est compatible. Renommer ou supprimer un symbole, rendre un argument obligatoire, changer une unité ou modifier silencieusement une sémantique est une rupture.

La compatibilité inclut dates, fuseaux, fractions contre pourcentages, directions, identifiants et sentinelles. Une signature Python inchangée avec une unité différente reste une rupture.

## Mécanisme exécutable

`core/_deprecation.py` fournit `deprecated_v1(reason=..., since=..., removal="2.0")`. Le décorateur conserve les métadonnées, émet un `DeprecationWarning` une seule fois par fonction et processus, et inscrit `__deprecated__`, `__deprecation_reason__`, `__deprecated_since__` et `__deprecated_removal__` sur le wrapper. Il ne supprime pas le comportement historique pendant la transition. `tests/test_deprecation_decorator.py` verrouille émission et métadonnées.

Les avertissements de dépréciation étant souvent masqués par Python, les tests et outils de migration doivent les activer explicitement.

## Audit des expositions privées

`scripts/audit_private_api_exposure.py` cherche les imports externes de symboles privés et propose des corrections. Une proposition d’export ou de décorateur exige une revue humaine : un appel existant à `_fonction` n’oblige pas à rendre cette fonction publique.

Pour faire évoluer une façade :

1. inventorier les consommateurs, l’IHM, les scripts et les tests ;
2. ajouter le nouveau point d’entrée et ses tests contractuels ;
3. conserver l’ancien nom comme adaptateur avec les mêmes unités ;
4. appliquer `deprecated_v1` avec motif et versions ;
5. migrer les consommateurs et auditer les imports privés ;
6. retirer l’adaptateur uniquement lors de la rupture annoncée.

## Hors contrat

Les helpers `_...`, structures internes de fichiers, logs textuels et détails d’implémentation ne sont pas stables. Les schémas persistés, payloads signés et formats tels que `report.json` ont leur propre contrat.

## Revue

- aucun nouvel import client depuis un symbole privé ;
- aucune unité modifiée sans migration explicite ;
- ancien et nouveau chemins testés pendant la transition ;
- message actionnable et version de retrait réaliste ;
- inventaire API et guide du module mis à jour.

