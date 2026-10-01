# Sprint 18-D — Port OMS complet et doubles mock/replay

## Résultat

Le contrat `ExecutionBrokerPort` de `execution_engine/broker_router.py` reflète désormais **toutes les opérations réellement appelées** par l'exécuteur, le watcher, la synchronisation, la CLI et le kill switch. Les composants OMS concernés sont annotés contre ce port, non contre la classe concrète `BrokerAdapter`. L'adaptateur Alpaca existant conserve ses méthodes, ses payloads, son routage et ses effets US ; aucun algorithme d'ordre US n'a été remplacé.

| Famille | Opérations du port | Consommateurs |
| --- | --- | --- |
| Ordres | `submit_intent`, `submit_market_order`, `submit_oco_protection`, `replace_stop_order`, `poll_order_status`, `cancel_broker_order` | exécuteur, watcher, transitions de protection, clôtures US |
| Kill switch et synchronisation | `cancel_all_open_orders`, `list_recent_orders`, `broker_order_from_api` | CLI, synchronisation des ordres ouverts et fills |
| Compte et marché | `get_account_snapshot`, `get_account_equity`, `get_position`, `get_all_positions`, `get_latest_market_price`, `is_market_open` | capacité, portefeuille, trailing, watcher |

Le type `CancelResult` a été placé dans `execution_engine.models` pour être partagé sans importer Alpaca depuis le port. Il reste accessible depuis `execution_engine.broker_adapter` grâce à son import, afin de préserver les usages existants.

## Deux adaptateurs sans broker

`execution_engine/broker_doubles_18d.py` contient :

- `MockBrokerAdapter` : ordres et compte en mémoire, IDs locaux, **aucun fill automatique**. Un test peut injecter explicitement un changement de statut. Un fill TP injecté annule localement la jambe stop de son groupe OCO. Les positions et le cash fournis sont des snapshots de test : le mock ne prétend pas gérer un portefeuille économique.
- `ReplayBrokerAdapter` : rejoue seulement des soumissions, réponses de polling et annulations présentes dans une bande explicitement fournie. Une intention imprévue, une identité divergente, une bande épuisée ou une injection manuelle de fill lève `ReplayMismatch`. Il ne récupère pas de données historiques et n'envoie aucun ordre.

Ces deux classes ont `simulated=True` et ne construisent aucun client Alpaca ou CN. Le routeur paper/live refuse explicitement une factory qui les retourne, même si elles satisfont structurellement le port. Il refuse toujours `CN_A` **avant** l'appel à la factory. Elles servent aux tests et relectures locaux, pas au paper trading, au shadow 18-C ou à une route de production.

```text
US_EQ + paper/live → BrokerRouter → BrokerAdapter Alpaca historique
CN_A + paper/live → refus avant factory
Mock/Replay → utilisation directe en tests/relecture seulement
CN_A 18-C → shadow autonome, aucun BrokerRouter ni ordre
```

## Contrôles de non-régression

Les tests `tests/test_execution_broker_doubles_18d.py` valident conformité au port, statut sans fill, compte/prix en mémoire, OCO injecté, annulation, bande stricte et rejet d'une observation étrangère. `tests/test_execution_broker_router_18a.py` vérifie dorénavant que mock/replay ne peuvent entrer dans les modes paper/live. Les suites exécuteur, `run_execution`, watcher, OCO et synchronisation restent exécutées avec les doubles historiques du projet.

Ce sprint ne sélectionne pas de broker chinois et n'active ni paper/live CN ni ordonnanceur. Le [pilote 18-C](./sprint_18c_pilote_shadow_prospectif.md) reste suspendu jusqu'aux observations post-clôture du 8 octobre, selon son [TODO](./TODO_sprint_18c_post_cloture_2026_10_08.md). Le Sprint 19 reste conditionné à un GO économique, un broker/canal et une validation humaine distincte.

## Limites et étape ultérieure

Le port représente l'interface actuellement consommée, pas une abstraction universelle de tous les brokers. `BrokerAdapter` garde des conversions Alpaca internes ; un futur adaptateur CN exigerait une traduction des statuts, symbologies, comptes, ordres conditionnels/OCO et frais du canal choisi. La disponibilité d'une méthode dans le port ne vaut aucune preuve qu'un autre broker la prend en charge. La symétrie paper/live n'est pas autorisée par ce travail.
