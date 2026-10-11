# Régime marché et comptes broker

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Régime Marché

La page affiche le mode effectif, un badge, un résumé et la trace de décision. La trace est plus importante que le seul libellé : elle indique données disponibles, règles et fallback. L’expander de configuration lit `config.yaml > market_regimes`; il ne prouve pas qu’un ancien run utilisait la configuration actuellement affichée.

La page peut alimenter `stock_macro_indicators_daily`, recalculer le régime sur une période, calculer un snapshot à la volée et afficher l’historique persisté. Import et recalcul refusent une fin antérieure au début. Les scénarios de démonstration sont non destructifs et ne remplacent pas un snapshot persisté consommé par un run.

Avant recalcul : vérifier période, fraîcheur/provider, calendrier et sauvegarde. Après : lire résumé et lignes détaillées, puis contrôler le snapshot réellement lié au run de risque.

## Étude quotidienne Oracle × ATR

Dans Régime Marché, le bloc d'alimentation choisit période, univers et batch
Oracle, affiche une commande et persiste par tranches. Le défaut d'univers est
univers_filtred_tradable.txt. Les cinq listes de rendements sont des futurs
réalisés signés, pas les directions prédites du modèle. La liste
predicted_oracle_score_order_returns_pct reste dans l'ordre du score Oracle.

Lire le statut, les compteurs et movement_quality. `missing_returns_policy`
indique la politique partielle/stricte choisie : partial avec zéro manquant peut
être COMPLETE et à couverture 100 %. Un horizon immature reste inconnu. Recalculer
les séances complètes après une correction source si nécessaire ; la reprise
ne détecte pas automatiquement toutes les corrections.
[Contrat et procédure](../ml/oracle_atr_market_regime_daily.md).

## Comptes Alpaca — opérations broker

La page sélectionne un compte déclaré, rafraîchit l’état live, affiche compte, positions, ordres, portfolio history et historique canonique Alpha Trade. L’absence de connexion DB masque l’historique canonique sans rendre le broker indisponible ; inversement un snapshot DB ne prouve pas l’état live.

Les actions de clôture sont des écritures broker. Vérifier compte, symbole, quantité, ordres ouverts, mode paper/live et protections avant confirmation. Après action, rafraîchir puis réconcilier.

Le bloc failover expose primaire, secondaire, seuil et sentinelle `RESUME`. IBKR reste le secours de lecture par doctrine. Ne pas créer la sentinelle avant diagnostic et réconciliation ; voir [failover](../operations/broker_failover.md).

## Lecture croisée

Un régime affiché, un compte sélectionné et un run d’exécution peuvent provenir de temps différents. Pour conclure, rapprocher account id, workflow/run id, timestamp, snapshot régime, positions et ordres.

