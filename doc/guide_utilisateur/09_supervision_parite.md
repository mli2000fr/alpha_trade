# Supervision, parité et diagnostic

## Supervision Ops

Cette page agrège des sources différentes : services, runs IHM, workflow,
watcher local, intégration Windows, logs importés et alertes synthétiques. Leur
horloge et leur niveau de confiance peuvent différer.

### Watcher

Le watcher peut être piloté en local depuis l’IHM (start, stop, once) avec des
accusés et, dans certains cas, un override d’une intégration externe. Vérifier
d’abord qui possède réellement le watcher. Deux superviseurs concurrents
peuvent dupliquer des actions ou produire un état trompeur.

Les blocs distinguent logs live/historique IHM et statut/logs Windows réels.
L’intégration Windows explicite décrit la recommandation de déploiement. Un log
importé n’est pas une preuve que le service est encore vivant.

### Artefact coverage

La couverture d’artefacts mesure la disponibilité des fichiers nécessaires. Une
bonne couverture ne garantit ni compatibilité de schéma ni qualité du modèle ;
une mauvaise couverture explique des fallbacks ou absences de prédiction.

### Runs et corrélation

Les derniers runs critiques et les runs actifs doivent être rapprochés via la
corrélation workflow : pipeline, risque, exécution et autres processus ne sont
pas des listes indépendantes. Lors d’un incident, commencer par la chaîne liée
au même workflow et à la même date.

## Parité Backtest ↔ Live

La page compare les décisions de risque live à un replay backtest. Elle expose
vue rolling, symboles fréquemment divergents, drill-down et détail par date.

Une divergence peut provenir de : données ou timestamps, univers, modèle/batch,
configuration, état du portefeuille, ordre d’application des règles, précision
numérique ou comportement non déterministe. La page localise ; elle n’attribue
pas automatiquement la cause.

Procédure :

1. choisir une fenêtre et vérifier qu’elle contient des dates comparables ;
2. mesurer le taux global et la tendance rolling ;
3. identifier les symboles récurrents plutôt qu’un cas isolé ;
4. ouvrir le détail date/symbole et comparer entrées intermédiaires ;
5. classer l’écart par type ;
6. corriger la source, puis relancer le job de parité ;
7. conserver avant/après et identifiants.

La parité des décisions n’implique pas la parité des fills : elle porte sur le
périmètre implémenté par la page.

## Diagnostic ML

Cette page est une vue de recherche détaillée par batch, symbole, régime,
horizon, split et famille de modèle. Elle inclut Oracle Extreme, modèle global,
per-symbol/per-sector, distributions et historique des ranks.

Les graphiques et mini-backtests exploratoires aident à formuler une hypothèse ;
ils ne remplacent pas le backtest complet avec coûts, contrat et validation
préfixée. Toute commande générée doit être relue, notamment batchs et horizons.

## Calibrations de poids

La page conserve l’historique, le détail, la timeline et les tables d’un run de
calibration. Avant d’adopter un poids, vérifier provenance, période, objectif,
statut, validation walk-forward et destination de serving. Une calibration
terminée n’est pas nécessairement approuvée.

## Gravité opérationnelle

- critique : ordre/position/protection inattendu, compte erroné, données
  matérielles incohérentes, gate contourné ;
- élevée : processus bloqué, verrou orphelin confirmé, forte divergence de
  parité, artefacts essentiels absents ;
- moyenne : couverture partielle, calibration périmée, alertes répétées sans
  impact immédiat ;
- information : run terminé, métrique de suivi, événement attendu.

Voir [IHM et opérations](../16_ihm_et_operations.md),
[alertes et métriques](../operations/alerting_et_metriques.md) et
[parité](../backtesting/parite_live_backtest.md).
