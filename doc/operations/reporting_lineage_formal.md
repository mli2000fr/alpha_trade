# Reporting mensuel, lineage, fiscalité et vérification formelle

Retour : [IHM et opérations](../16_ihm_et_operations.md)

## Rapport mensuel

`reporting/monthly_report.py` reçoit des données déjà agrégées : compte, période, fills, événements cash, PnL réalisé FIFO et nombre de trades. Il ne relit pas le broker et ne recalcule pas les lots.

Le contrat `monthly_report.v1` expose PnL réalisé, dividendes, retenues, frais, slippage moyen, nombres de fills/trades et signature. Les frais cash et de fills sont additionnés. Le slippage est la moyenne non pondérée de `(fill-expected)/expected × 10 000`; un expected price ≤ 0 produit 0 bps et doit être contrôlé comme anomalie de référence.

## Signature et schéma

Le payload sans signature est sérialisé avec clés triées et séparateurs canoniques, puis signé HMAC-SHA256. `verify_signature()` compare en temps constant. La signature prouve l’intégrité vis-à-vis du secret partagé, pas l’exactitude des données ni l’identité d’un utilisateur.

`reporting/json_schema.py` définit champs requis et types. Une évolution incompatible crée une nouvelle `schema_version`. Le secret n’est jamais stocké avec le rapport. `pdf_renderer.py` produit une vue lorsque l’extra est installé ; le JSON signé reste le contrat machine.

Avant publication, vérifier compte, devise, période, unicité des événements, statement, PnL FIFO, corporate actions, retenues et frais. Archiver source/run ids et vérifier la signature après écriture.

## Lineage

`lineage/graph_store.py` définit `Node`, `Edge` et `GraphStore`. `InMemoryGraphStore` est déterministe et thread-safe, déduplique les arêtes et exporte JSON/DOT. Une arête vers un nœud absent crée un placeholder `unknown`.

`event_listener.py` observe les instructions SQLAlchemy Core, reconnaît insert/update/delete et crée des relations depuis run, order, parent, fill et symbol.

Les noms de tables par défaut historiques (`bars`, `orders`, `execution_fills`, `risk_decisions`, `risk_runs`) ne correspondent pas tous nécessairement au schéma courant. Le listener ne câble que les tables présentes dans le `MetaData`; un retour 0 signifie aucune table observée. Ce lineage est opt-in et partiel, pas une capture exhaustive.

`neo4j_store.py` fournit un backend optionnel. Une panne de lineage ne modifie jamais un résultat métier et doit être rattrapable depuis les ids persistés.

## Vérification formelle

`formal/tla/` contient modèles/preuves TLA+ pour double exécution, OCO et idempotence corporate actions. `formal/z3_invariants/` encode des invariants analogues.

La preuve no-double-execution suppose un lock exclusif et démontre que deux acteurs ne réussissent pas pour la même clé. Elle ne prouve pas que tout chemin réseau acquiert effectivement ce lock. Une sortie `skipped` sans Z3 n’équivaut pas à une preuve exécutée.

Toute évolution d’ordre, lock ou corporate action doit aligner modèle abstrait, preuve, implémentation et tests.

## Fiscalité

Voir [Fiscalité et wash sale](fiscalite_wash_sale.md). Ce module est une aide simplifiée, pas un conseil fiscal.

## Tests

Tester sérialisation stable, signature valide/invalide, schéma, rapport vide, référence nulle, graph store concurrent, listener sans table, relations FK, exports déterministes et preuves avec/sans dépendance.

