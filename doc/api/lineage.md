# Inventaire API — lineage

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `lineage/__init__.py`

Source SHA-256 : `83bb66787e8e4f18cc5310e40ffb08577d78a23de21fa94498a004f24bbd463e`

- [__getattr__](../../lineage/__init__.py) — ligne 10 : `def __getattr__(name: str)`

## `lineage/event_listener.py`

Source SHA-256 : `f4e7c328059fe062e15faf0e3014a95566b3b0f38290edb72d955c5ce5669d80`

- [_emit_for_row](../../lineage/event_listener.py) — ligne 45 : `def _emit_for_row(table: Table, op: str, params: dict[str, Any], store: GraphStore) -> None`
- [_make_before_cursor_execute_handler](../../lineage/event_listener.py) — ligne 82 : `def _make_before_cursor_execute_handler(watched: dict[str, Table], store: GraphStore)`
- [register_lineage_listeners](../../lineage/event_listener.py) — ligne 122 : `def register_lineage_listeners(metadata: MetaData, store: GraphStore, *, tables: Iterable[str]=DEFAULT_TABLES, engine: Optional[Engine]=None) -> int`
- [clear_registry](../../lineage/event_listener.py) — ligne 155 : `def clear_registry() -> None`

## `lineage/graph_store.py`

Source SHA-256 : `0cda6bf63502e7aeb15596872b5476c7a65f02522a418e6b110784d7069de2ff`

- [Node](../../lineage/graph_store.py) — ligne 21 : `class Node`
- [Node.make](../../lineage/graph_store.py) — ligne 27 : `def make(cls, node_id: str, label: str, **properties: Any) -> 'Node'`
- [Node.to_dict](../../lineage/graph_store.py) — ligne 31 : `def to_dict(self) -> dict[str, Any]`
- [Edge](../../lineage/graph_store.py) — ligne 36 : `class Edge`
- [Edge.make](../../lineage/graph_store.py) — ligne 43 : `def make(cls, src: str, dst: str, relation: str, **properties: Any) -> 'Edge'`
- [Edge.to_dict](../../lineage/graph_store.py) — ligne 47 : `def to_dict(self) -> dict[str, Any]`
- [GraphStore](../../lineage/graph_store.py) — ligne 56 : `class GraphStore(Protocol)`
- [GraphStore.add_node](../../lineage/graph_store.py) — ligne 57 : `def add_node(self, node: Node) -> None`
- [GraphStore.add_edge](../../lineage/graph_store.py) — ligne 58 : `def add_edge(self, edge: Edge) -> None`
- [GraphStore.nodes](../../lineage/graph_store.py) — ligne 59 : `def nodes(self) -> Iterable[Node]`
- [GraphStore.edges](../../lineage/graph_store.py) — ligne 60 : `def edges(self) -> Iterable[Edge]`
- [GraphStore.clear](../../lineage/graph_store.py) — ligne 61 : `def clear(self) -> None`
- [InMemoryGraphStore](../../lineage/graph_store.py) — ligne 65 : `class InMemoryGraphStore`
- [InMemoryGraphStore.add_node](../../lineage/graph_store.py) — ligne 72 : `def add_node(self, node: Node) -> None`
- [InMemoryGraphStore.add_edge](../../lineage/graph_store.py) — ligne 76 : `def add_edge(self, edge: Edge) -> None`
- [InMemoryGraphStore.nodes](../../lineage/graph_store.py) — ligne 84 : `def nodes(self) -> list[Node]`
- [InMemoryGraphStore.edges](../../lineage/graph_store.py) — ligne 88 : `def edges(self) -> list[Edge]`
- [InMemoryGraphStore.clear](../../lineage/graph_store.py) — ligne 92 : `def clear(self) -> None`
- [InMemoryGraphStore.to_dict](../../lineage/graph_store.py) — ligne 98 : `def to_dict(self) -> dict[str, Any]`
- [InMemoryGraphStore.to_json](../../lineage/graph_store.py) — ligne 104 : `def to_json(self, *, indent: int | None=2) -> str`
- [InMemoryGraphStore.to_dot](../../lineage/graph_store.py) — ligne 107 : `def to_dot(self, *, name: str='lineage') -> str`

## `lineage/neo4j_store.py`

Source SHA-256 : `7d0ccc9115c1bdba4ef9dd277d6216c1118a40a955a784c97d6b9ab0323c1765`

- [Neo4jGraphStore](../../lineage/neo4j_store.py) — ligne 20 : `class Neo4jGraphStore`
- [Neo4jGraphStore.__init__](../../lineage/neo4j_store.py) — ligne 27 : `def __init__(self, uri: str, *, user: str='neo4j', password: str='neo4j', database: str='neo4j') -> None`
- [Neo4jGraphStore._safe_label](../../lineage/neo4j_store.py) — ligne 47 : `def _safe_label(label: str) -> str`
- [Neo4jGraphStore.add_node](../../lineage/neo4j_store.py) — ligne 51 : `def add_node(self, node: Node) -> None`
- [Neo4jGraphStore.add_edge](../../lineage/neo4j_store.py) — ligne 60 : `def add_edge(self, edge: Edge) -> None`
- [Neo4jGraphStore.nodes](../../lineage/neo4j_store.py) — ligne 71 : `def nodes(self) -> Iterable[Node]`
- [Neo4jGraphStore.edges](../../lineage/neo4j_store.py) — ligne 82 : `def edges(self) -> Iterable[Edge]`
- [Neo4jGraphStore.clear](../../lineage/neo4j_store.py) — ligne 93 : `def clear(self) -> None`
- [Neo4jGraphStore.close](../../lineage/neo4j_store.py) — ligne 97 : `def close(self) -> None`
- [build_graph_store_from_env](../../lineage/neo4j_store.py) — ligne 104 : `def build_graph_store_from_env() -> GraphStore`
