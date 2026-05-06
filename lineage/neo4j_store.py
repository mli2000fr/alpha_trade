"""Sprint S21.5 — Implémentation Neo4j (opt-in) du contrat :class:`GraphStore`.

Activation : pip install neo4j
Sélection automatique via :func:`build_graph_store_from_env` si la
variable d'environnement ``ALPHA_TRADE_NEO4J_URI`` est définie.

Toutes les opérations utilisent ``MERGE`` pour rester idempotentes.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from lineage.graph_store import Edge, GraphStore, InMemoryGraphStore, Node

LOGGER = logging.getLogger(__name__)


class Neo4jGraphStore:
    """Adaptateur Neo4j (driver officiel ``neo4j``).

    L'écriture est ``MERGE``-based pour permettre la réémission sans
    duplication. Les labels Cypher sont validés (alphanum + underscore).
    """

    def __init__(
        self,
        uri: str,
        *,
        user: str = "neo4j",
        password: str = "neo4j",
        database: str = "neo4j",
    ) -> None:
        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Le paquet 'neo4j' n'est pas installé : pip install neo4j"
            ) from exc
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    # ------- API GraphStore ---------------------------------------------

    @staticmethod
    def _safe_label(label: str) -> str:
        out = "".join(c for c in label if c.isalnum() or c == "_")
        return out or "Node"

    def add_node(self, node: Node) -> None:
        label = self._safe_label(node.label)
        props = dict(node.properties)
        with self._driver.session(database=self._database) as session:
            session.run(
                f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                id=node.id, props=props,
            )

    def add_edge(self, edge: Edge) -> None:
        rel = self._safe_label(edge.relation).upper() or "REL"
        props = dict(edge.properties)
        with self._driver.session(database=self._database) as session:
            session.run(
                "MERGE (a {id: $src}) "
                "MERGE (b {id: $dst}) "
                f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                src=edge.src, dst=edge.dst, props=props,
            )

    def nodes(self) -> Iterable[Node]:
        with self._driver.session(database=self._database) as session:
            res = session.run("MATCH (n) RETURN labels(n) AS labels, n.id AS id, properties(n) AS props")
            out = []
            for r in res:
                lbls = r["labels"] or ["Node"]
                props = dict(r["props"] or {})
                props.pop("id", None)
                out.append(Node.make(r["id"], lbls[0], **props))
            return out

    def edges(self) -> Iterable[Edge]:
        with self._driver.session(database=self._database) as session:
            res = session.run(
                "MATCH (a)-[r]->(b) RETURN a.id AS src, b.id AS dst, "
                "type(r) AS rel, properties(r) AS props"
            )
            return [
                Edge.make(r["src"], r["dst"], r["rel"], **(r["props"] or {}))
                for r in res
            ]

    def clear(self) -> None:
        with self._driver.session(database=self._database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:  # noqa: BLE001
            pass


def build_graph_store_from_env() -> GraphStore:
    """Retourne ``Neo4jGraphStore`` si ``ALPHA_TRADE_NEO4J_URI`` défini, sinon InMemory."""
    uri = os.getenv("ALPHA_TRADE_NEO4J_URI")
    if not uri:
        return InMemoryGraphStore()
    user = os.getenv("ALPHA_TRADE_NEO4J_USER", "neo4j")
    password = os.getenv("ALPHA_TRADE_NEO4J_PASSWORD", "neo4j")
    database = os.getenv("ALPHA_TRADE_NEO4J_DB", "neo4j")
    try:
        return Neo4jGraphStore(uri, user=user, password=password, database=database)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Neo4j indisponible (%s) — fallback InMemory.", exc)
        return InMemoryGraphStore()


__all__ = ["Neo4jGraphStore", "build_graph_store_from_env"]

