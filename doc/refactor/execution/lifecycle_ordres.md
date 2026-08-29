# Lifecycle des ordres et machine d'état

Retour : [références Execution](README.md)

`executor.py` consomme un snapshot immuable des targets. Il photographie le broker, construit les deltas et produit des `OrderIntent`, puis des `ExecutionOrderRequest`. La soumission crée une observation broker ; seul un `ExecutionFill` modifie la quantité exécutée.

États terminaux usuels : filled, cancelled, rejected, expired. Partial fill reste non terminal tant que le reliquat peut vivre. `state_machine.py` refuse les transitions impossibles. Les client order ids assurent l'idempotence et la recherche après timeout.

Les transitions portefeuille défensives précèdent les entrées. Une reprise commence par sync broker et recherche des ordres existants ; ne jamais renvoyer une intention parce que la DB n'a pas reçu la réponse HTTP.

Invariants : somme fills <= request ; une quantité remplie agrège prix moyen pondéré ; request ≠ ordre ≠ fill ; compte/mode immuables ; aucun ordre nouveau en close-only/cash-only selon plan.

## Entités persistées

`ExecutionTarget` est la copie du target risque. `OrderIntent` est l'action métier avec rôle et clés d'idempotence/soumission. `ExecutionOrderRequest` est la tentative normalisée. `BrokerOrder` et `BrokerOrderObservation` représentent l'état externe. `ExecutionFill` est une exécution économique. `ExecutionPosition`/`Lot` reconstruisent l'inventaire. `ExecutionEvent` garde le journal.

## Rôles d'intention

Les rôles distinguent entrée, rebalance sell, initial stop, take profit, trailing, time-stop, adopted entry et autres transitions définies dans `IntentRole`. Le rôle conditionne côté, parenté, protection et réconciliation ; une simple chaîne buy/sell ne suffit pas.

## Clés

La business/idempotency key identifie l'action logique. La submission key identifie une tentative broker. Le client order id doit permettre une recherche après réponse perdue. Créer une nouvelle clé à chaque retry détruit l'idempotence.

## Machine d'état

Le statut local suit les observations broker. Une soumission acceptée n'est pas filled. Partial fill peut être observé plusieurs fois ; seule la différence nouvelle doit créer un fill. Cancelled/rejected/expired sont terminaux. Une observation en retard ne doit pas faire revenir un terminal vers pending.

## Deltas et ordre des opérations

Le moteur compare target qty et broker qty. Delta positif crée achat/cover selon côté ; négatif vente/réduction. Avant entrées, il exécute le transition plan : annulations incompatibles, liquidations et réductions. Les positions existantes sont intégrées au buying power et aux protections.

## Partial fills

Chaque fill possède quantité/prix/heure/id. Le prix moyen est pondéré. Les enfants protègent la quantité remplie, puis sont ajustés si de nouveaux fills arrivent. Le reliquat peut être annulé selon timeout/politique sans annuler la position déjà acquise.

## Timeout ambigu

Après un timeout de submit : ne pas considérer rejet, ne pas soumettre à nouveau. Interroger par client id, synchroniser ordres/fills, puis décider. Si le broker est inaccessible, laisser l'état `unknown/pending reconciliation` selon les statuts du code et bloquer les mutations concurrentes.

## Simulation, paper et live

Simulation produit des événements synthétiques sans broker réel. Paper utilise l'API paper et révèle contraintes réseau/order types. Live ajoute approval token/confirmation label et probes. Les trois modes doivent partager intents et state machine ; seuls adapter/fills diffèrent.

## Tests contractuels

`test_execution_state_machine.py`, executor/db_io, live approval, immutable plan, reconciliation, replay parity et cancel-all couvrent les frontières. Ajouter un golden lorsqu'un nouveau statut/role est introduit.
