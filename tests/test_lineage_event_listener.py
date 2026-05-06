"""Sprint S21.5 — Tests listeners SQLAlchemy peuplant InMemoryGraphStore."""
from __future__ import annotations

import pytest
from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, create_engine, insert,
)

from lineage.event_listener import (
    DEFAULT_TABLES, clear_registry, register_lineage_listeners,
)
from lineage.graph_store import InMemoryGraphStore


@pytest.fixture()
def metadata_and_engine():
    md = MetaData()
    Table(
        "orders", md,
        Column("order_id", String(64), primary_key=True),
        Column("symbol", String(16), nullable=False),
        Column("run_id", String(64)),
    )
    Table(
        "execution_fills", md,
        Column("fill_id", String(64), primary_key=True),
        Column("order_id", String(64)),
        Column("symbol", String(16)),
    )
    Table(
        "bars", md,  # non utilisée → vérifie le no-op
        Column("id", Integer, primary_key=True),
        Column("ts", DateTime),
    )
    eng = create_engine("sqlite:///:memory:", future=True)
    md.create_all(eng)
    yield md, eng
    clear_registry()


def test_register_returns_count_of_attached_handlers(metadata_and_engine):
    md, eng = metadata_and_engine
    store = InMemoryGraphStore()
    n = register_lineage_listeners(md, store, engine=eng,
                                   tables=("orders", "execution_fills", "bars"))
    # 3 tables connues effectivement câblées
    assert n == 3


def test_unknown_table_silently_skipped(metadata_and_engine):
    md, eng = metadata_and_engine
    store = InMemoryGraphStore()
    n = register_lineage_listeners(md, store, engine=eng, tables=("ghost_table",))
    assert n == 0


def test_insert_creates_nodes_and_fk_edges(metadata_and_engine):
    md, eng = metadata_and_engine
    store = InMemoryGraphStore()
    register_lineage_listeners(md, store, engine=eng,
                               tables=("orders", "execution_fills"))

    orders = md.tables["orders"]
    fills = md.tables["execution_fills"]

    with eng.begin() as conn:
        conn.execute(insert(orders).values(order_id="O1", symbol="AAPL", run_id="R1"))
        conn.execute(insert(fills).values(fill_id="F1", order_id="O1", symbol="AAPL"))

    nodes = {n.id: n for n in store.nodes()}
    edges = list(store.edges())

    assert "orders:O1" in nodes
    assert "execution_fills:F1" in nodes

    # arête fill → order
    rels = {(e.src, e.dst, e.relation) for e in edges}
    assert ("execution_fills:F1", "order:O1", "child_of_order") in rels
    assert ("orders:O1", "run:R1", "produced_by_run") in rels


def test_default_tables_constant():
    assert "orders" in DEFAULT_TABLES
    assert "execution_fills" in DEFAULT_TABLES


def test_lazy_export_register():
    import lineage
    assert callable(lineage.register_lineage_listeners)
    assert callable(lineage.build_graph_store_from_env)


