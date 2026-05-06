"""Phase C / S16.4 — Tests ``InMemoryGraphStore``."""
from __future__ import annotations

import json

from lineage import Edge, InMemoryGraphStore, Node


def test_add_node_and_edge():
    g = InMemoryGraphStore()
    g.add_node(Node.make("table:fills", "Table", source="alpaca"))
    g.add_node(Node.make("table:lots", "Table"))
    g.add_edge(Edge.make("table:fills", "table:lots", "feeds"))
    assert len(g.nodes()) == 2
    assert len(g.edges()) == 1


def test_add_edge_creates_implicit_nodes():
    g = InMemoryGraphStore()
    g.add_edge(Edge.make("a", "b", "rel"))
    assert {n.id for n in g.nodes()} == {"a", "b"}


def test_dedup_edges():
    g = InMemoryGraphStore()
    e = Edge.make("a", "b", "rel", weight=1)
    g.add_edge(e)
    g.add_edge(e)
    assert len(g.edges()) == 1


def test_export_dict_and_json():
    g = InMemoryGraphStore()
    g.add_node(Node.make("a", "X"))
    g.add_node(Node.make("b", "Y"))
    g.add_edge(Edge.make("a", "b", "depends_on"))
    d = g.to_dict()
    assert d["nodes"][0]["id"] in ("a", "b")
    assert d["edges"][0]["relation"] == "depends_on"
    parsed = json.loads(g.to_json())
    assert parsed == d


def test_export_dot():
    g = InMemoryGraphStore()
    g.add_node(Node.make("a", "X"))
    g.add_node(Node.make("b", "Y"))
    g.add_edge(Edge.make("a", "b", "feeds"))
    dot = g.to_dot()
    assert "digraph" in dot
    assert '"a" -> "b"' in dot
    assert "feeds" in dot


def test_clear():
    g = InMemoryGraphStore()
    g.add_node(Node.make("a", "X"))
    g.clear()
    assert g.nodes() == [] and g.edges() == []


def test_pipeline_lineage_simulation():
    """Vérifie qu'on dépasse facilement 50 nœuds sur un run pipeline simulé."""
    g = InMemoryGraphStore()
    for stage in ("ingest", "screener", "selector", "risk", "execution"):
        g.add_node(Node.make(f"stage:{stage}", "Stage"))
    for sym in (f"sym{i}" for i in range(60)):
        g.add_node(Node.make(f"symbol:{sym}", "Symbol"))
        g.add_edge(Edge.make("stage:screener", f"symbol:{sym}", "scored"))
    assert len(g.nodes()) >= 50

