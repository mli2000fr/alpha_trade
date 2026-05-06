"""Phase C / S16.4 — ``InMemoryGraphStore`` + interface ``GraphStore``.

Implémentation pur Python pour générer un graphe de lineage sans
dépendre de Neo4j. L'adaptateur Neo4j est opt-in (cf.
``lineage/neo4j_store.py``).

Format d'export :

* ``to_dict()`` — dictionnaire JSON-sérialisable.
* ``to_dot()`` — graphviz DOT (visualisable avec ``dot -Tpng``).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    properties: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def make(cls, node_id: str, label: str, **properties: Any) -> "Node":
        return cls(id=node_id, label=label,
                   properties=tuple(sorted(properties.items())))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "properties": dict(self.properties)}


@dataclass(frozen=True, slots=True)
class Edge:
    src: str
    dst: str
    relation: str
    properties: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def make(cls, src: str, dst: str, relation: str, **properties: Any) -> "Edge":
        return cls(src=src, dst=dst, relation=relation,
                   properties=tuple(sorted(properties.items())))

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "relation": self.relation,
            "properties": dict(self.properties),
        }


class GraphStore(Protocol):
    def add_node(self, node: Node) -> None: ...
    def add_edge(self, edge: Edge) -> None: ...
    def nodes(self) -> Iterable[Node]: ...
    def edges(self) -> Iterable[Edge]: ...
    def clear(self) -> None: ...


@dataclass
class InMemoryGraphStore:
    """Stockage en mémoire (déterministe, thread-safe)."""

    _nodes: dict[str, Node] = field(default_factory=dict)
    _edges: set[Edge] = field(default_factory=set)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def add_node(self, node: Node) -> None:
        with self._lock:
            self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        with self._lock:
            # autoriser créations d'arêtes vers des nœuds non encore ajoutés
            self._edges.add(edge)
            for nid in (edge.src, edge.dst):
                self._nodes.setdefault(
                    nid, Node(id=nid, label="unknown", properties=()))

    def nodes(self) -> list[Node]:
        with self._lock:
            return sorted(self._nodes.values(), key=lambda n: n.id)

    def edges(self) -> list[Edge]:
        with self._lock:
            return sorted(self._edges, key=lambda e: (e.src, e.dst, e.relation))

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._edges.clear()

    # ---------- exports ----------
    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes()],
            "edges": [e.to_dict() for e in self.edges()],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_dot(self, *, name: str = "lineage") -> str:
        lines = [f'digraph "{name}" {{', '  rankdir=LR;']
        for n in self.nodes():
            lbl = f"{n.label}\\n{n.id}".replace('"', '\\"')
            lines.append(f'  "{n.id}" [label="{lbl}"];')
        for e in self.edges():
            lines.append(f'  "{e.src}" -> "{e.dst}" [label="{e.relation}"];')
        lines.append("}")
        return "\n".join(lines)

