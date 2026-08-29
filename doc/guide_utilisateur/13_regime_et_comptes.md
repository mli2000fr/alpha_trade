# Régime marché et comptes broker

## Régime Marché

La page affiche le mode effectif, un badge, un résumé et la trace de décision. La trace est plus importante que le seul libellé : elle indique données disponibles, règles et fallback. L’expander de configuration lit `config.yaml > market_regimes`; il ne prouve pas qu’un ancien run utilisait la configuration actuellement affichée.

La page peut alimenter `stock_macro_indicators_daily`, recalculer le régime sur une période, calculer un snapshot à la volée et afficher l’historique persisté. Import et recalcul refusent une fin antérieure au début. Les scénarios de démonstration sont non destructifs et ne remplacent pas un snapshot persisté consommé par un run.

Avant recalcul : vérifier période, fraîcheur/provider, calendrier et sauvegarde. Après : lire résumé et lignes détaillées, puis contrôler le snapshot réellement lié au run de risque.

## Comptes Alpaca

La page sélectionne un compte déclaré, rafraîchit l’état live, affiche compte, positions, ordres, portfolio history et historique canonique Alpha Trade. L’absence de connexion DB masque l’historique canonique sans rendre le broker indisponible ; inversement un snapshot DB ne prouve pas l’état live.

Les actions de clôture sont des écritures broker. Vérifier compte, symbole, quantité, ordres ouverts, mode paper/live et protections avant confirmation. Après action, rafraîchir puis réconcilier.

Le bloc failover expose primaire, secondaire, seuil et sentinelle `RESUME`. IBKR reste le secours de lecture par doctrine. Ne pas créer la sentinelle avant diagnostic et réconciliation ; voir [failover](../operations/broker_failover.md).

## Lecture croisée

Un régime affiché, un compte sélectionné et un run d’exécution peuvent provenir de temps différents. Pour conclure, rapprocher account id, workflow/run id, timestamp, snapshot régime, positions et ordres.

