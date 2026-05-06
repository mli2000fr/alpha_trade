"""Phase C / S16.4 + Sprint S21.5 — Lineage temps réel (graph store pluggable)."""
from lineage.graph_store import GraphStore, InMemoryGraphStore, Node, Edge  # noqa: F401

__all__ = [
    "GraphStore", "InMemoryGraphStore", "Node", "Edge",
    "register_lineage_listeners", "build_graph_store_from_env", "Neo4jGraphStore",
]


def __getattr__(name: str):  # pragma: no cover - lazy
    if name == "register_lineage_listeners":
        from lineage.event_listener import register_lineage_listeners
        return register_lineage_listeners
    if name == "build_graph_store_from_env":
        from lineage.neo4j_store import build_graph_store_from_env
        return build_graph_store_from_env
    if name == "Neo4jGraphStore":
        from lineage.neo4j_store import Neo4jGraphStore
        return Neo4jGraphStore
    raise AttributeError(name)

