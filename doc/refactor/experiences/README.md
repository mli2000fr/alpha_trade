# Synthèses des expériences historiques

Ce répertoire conserve les enseignements des campagnes de recherche sans mélanger résultats historiques et comportement actuel.

Les fichiers originaux restent dans `doc/` et ne sont pas modifiés. Les synthèses de ce dossier sont autonomes : elles décrivent question, protocole, conclusion durable, limites et relation avec le code courant.

## Index

- [Oracle : évolution TOP/BOTTOM vers Extreme](oracle_extreme.md)
- [Global Ranking, per-sector et variantes B0–B44](global_ranking_et_per_sector.md)
- [Lifecycle, stops, drawdown et exposition](risque_execution_lifecycle.md)
- [Filtres DIP, direction et données nouvelles](filtres_et_direction.md)
- [Anti-overfitting, calibration et recalibration](validation_et_recalibration.md)

## Ce qu’une synthèse ne garantit pas

Une métrique historique dépend de la base, du batch, de l’univers, des coûts et du lifecycle de son run. Elle n’est pas une valeur de production actuelle. Pour reproduire une expérience, les archives originales et leurs artefacts restent nécessaires.

## Règle de promotion

Une expérience devient documentation fonctionnelle uniquement lorsque son comportement existe dans le code courant et peut être activé par la configuration/CLI. Le guide du module documente alors le contrat exécutable et pointe vers la synthèse historique pour le contexte.

Retour : [index général](../README.md)

