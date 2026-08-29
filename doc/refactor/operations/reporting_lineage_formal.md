# Reporting, lineage et vérification formelle

Retour : [IHM et opérations](../16_ihm_et_operations.md)

## Reporting

`reporting/monthly_report.py` assemble les faits mensuels. `json_schema.py` valide le contrat machine et `pdf_renderer.py` produit une représentation PDF lorsque l'extra est installé. Le rendu ne recalcule pas les décisions : période, compte, devise et sources réconciliées doivent être explicites.

## Lineage

`lineage/event_listener.py` reçoit les événements de production. `graph_store.py` définit le stockage abstrait/local ; `neo4j_store.py` fournit le backend Neo4j optionnel. Runs, datasets, modèles, décisions et rapports sont raccordés par ids/fingerprints. Une panne de lineage ne doit ni inventer ni modifier un résultat métier.

## Vérification formelle

`formal/z3_invariants/` encode trois invariants critiques : absence de double exécution, idempotence des corporate actions et cohérence d'un bracket OCO synthétique. Ces preuves portent sur le modèle abstrait encodé, pas sur tout le broker/réseau. Toute évolution de règle doit aligner code, tests et hypothèses Z3.

## Tax

`tax/wash_sale.py` repère les situations wash-sale dans les transactions disponibles. Il s'agit d'un outil de conformité, pas d'un conseil fiscal ni d'une écriture automatique chez le broker.

