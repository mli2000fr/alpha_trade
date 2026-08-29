# Sécurité live et protection de l’argent réel

## Principe

Le passage live est un changement d’autorité, pas un simple paramètre. Chaque
action doit rendre visibles compte, environnement, mode, dry-run, portefeuille
cible et protections.

## Barrières

- séparation paper/live et comptes ;
- confirmations explicites et motifs opérateur ;
- gates données/ML/risque ;
- kill switch ;
- protections parent/enfants et watcher secondaire ;
- réconciliation broker et J+1 ;
- journalisation des événements ;
- limites capital, position, secteur et drawdown.

## Avant activation

Valider parité, couverture, contrat d’exécution, coûts, corporate actions,
positions initiales, calendrier et rollback. Commencer par une exposition
contrôlée selon la politique validée. La réussite d’un backtest n’est pas une
autorisation live.

## Incident

Priorité : connaître positions et ordres réels, éviter les doublons, maintenir
ou restaurer les protections, puis réconcilier la base. Le kill switch annule
les ordres ouverts mais ne liquide pas nécessairement les positions. Toute
action doit conserver compte, heure et motif.

Voir [supervision/sécurité](supervision_et_securite.md),
[guide Exécution](../guide_utilisateur/07_execution.md) et
[runbook opérateur](../22_runbook_exploitation.md).
