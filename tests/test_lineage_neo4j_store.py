"""Sprint S21.5 — Tests Neo4jGraphStore (live + fallback).

Le test live nécessite ``ALPHA_TRADE_NEO4J_URI`` + ``neo4j`` installé.
"""
from __future__ import annotations

import os

import pytest

from lineage.graph_store import Edge, InMemoryGraphStore, Node


def test_build_graph_store_from_env_fallback_when_no_uri(monkeypatch):
    monkeypatch.delenv("ALPHA_TRADE_NEO4J_URI", raising=False)
    from lineage.neo4j_store import build_graph_store_from_env

    store = build_graph_store_from_env()
    assert isinstance(store, InMemoryGraphStore)


def test_neo4j_store_raises_without_driver(monkeypatch):
    """Sans le paquet ``neo4j``, l'instanciation lève RuntimeError."""
    import importlib
    import sys

    # Force ImportError pour ``neo4j``
    monkeypatch.setitem(sys.modules, "neo4j", None)
    from lineage.neo4j_store import Neo4jGraphStore

    with pytest.raises(RuntimeError):
        Neo4jGraphStore("bolt://nowhere:7687")


@pytest.mark.live
def test_neo4j_store_roundtrip_live():
    pytest.importorskip("neo4j")
    uri = os.getenv("ALPHA_TRADE_NEO4J_URI")
    if not uri:
        pytest.skip("ALPHA_TRADE_NEO4J_URI non défini.")
    from lineage.neo4j_store import Neo4jGraphStore

    store = Neo4jGraphStore(
        uri,
        user=os.getenv("ALPHA_TRADE_NEO4J_USER", "neo4j"),
        password=os.getenv("ALPHA_TRADE_NEO4J_PASSWORD", "neo4j"),
    )
    try:
        store.clear()
        store.add_node(Node.make("o1", "order", symbol="AAPL"))
        store.add_node(Node.make("f1", "fill", qty=10))
        store.add_edge(Edge.make("f1", "o1", "child_of_order"))
        nodes = {n.id for n in store.nodes()}
        assert {"o1", "f1"} <= nodes
        edges = list(store.edges())
        assert any(e.src == "f1" and e.dst == "o1" for e in edges)
    finally:
        store.clear()
        store.close()

