# Failover broker Alpaca vers IBKR

## Doctrine codée

`service/broker_failover.py` fournit `FailoverBrokerClient`. Le primaire reçoit toutes les opérations tant que son circuit est fermé. Après trois erreurs de lecture consécutives par défaut, les lectures basculent sur le secondaire et toutes les écritures restent suspendues. Une réussite secondaire ne réarme jamais le primaire.

Les lectures concernent compte, positions, ordres et flux. `submit_order` et `cancel_order` lèvent `WriteSuspendedError` quand le breaker est ouvert. C’est une continuité d’observation, pas une bascule de trading vers IBKR.

Chaque réussite primaire remet le compteur à zéro. Chaque exception l’incrémente. Au seuil, `_trip()` journalise, notifie si possible, sert la lecture depuis le secondaire et suspend les écritures.

## Reprise humaine

La sentinelle par défaut est `artifacts/failover/RESUME`. Lorsqu’elle est détectée, le wrapper tente de la supprimer, ferme le breaker et remet le compteur à zéro.

Créer la sentinelle uniquement après :

1. diagnostic du primaire ;
2. inventaire ordres/positions via les sources disponibles ;
3. réconciliation des écarts ;
4. confirmation qu’aucune écriture concurrente n’est en cours ;
5. validation opérateur enregistrée.

Vérifier sa disparition après le premier appel. Ne jamais contourner `WriteSuspendedError` avec un client direct. Après reprise, relancer preflight et réconciliation avant ordre.

`build_failover_doctrine_summary()` expose primaire, secondaire, seuil, mode et chemin de sentinelle à l’IHM. `tests/test_failover_alpaca_to_ibkr.py` verrouille le comportement. Voir aussi [IBKR](../execution/ibkr.md).

