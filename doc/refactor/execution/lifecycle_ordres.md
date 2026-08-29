# Lifecycle des ordres et machine d'état

Retour : [références Execution](README.md)

`executor.py` consomme un snapshot immuable des targets. Il photographie le broker, construit les deltas et produit des `OrderIntent`, puis des `ExecutionOrderRequest`. La soumission crée une observation broker ; seul un `ExecutionFill` modifie la quantité exécutée.

États terminaux usuels : filled, cancelled, rejected, expired. Partial fill reste non terminal tant que le reliquat peut vivre. `state_machine.py` refuse les transitions impossibles. Les client order ids assurent l'idempotence et la recherche après timeout.

Les transitions portefeuille défensives précèdent les entrées. Une reprise commence par sync broker et recherche des ordres existants ; ne jamais renvoyer une intention parce que la DB n'a pas reçu la réponse HTTP.

Invariants : somme fills <= request ; une quantité remplie agrège prix moyen pondéré ; request ≠ ordre ≠ fill ; compte/mode immuables ; aucun ordre nouveau en close-only/cash-only selon plan.

