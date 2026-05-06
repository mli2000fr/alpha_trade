"""Sprint S21.5 — Listeners SQLAlchemy peuplant un :class:`GraphStore`.

SQLAlchemy Core n'expose pas d'événements ``after_insert/update/delete``
sur les objets :class:`~sqlalchemy.Table` (ces hooks existent uniquement
côté ORM ``Mapper``). Pour rester compatible avec l'usage Core dominant
dans ``database/repositories/``, on hooke l'événement ``after_execute``
de l':class:`~sqlalchemy.engine.Engine` et on inspecte la clause SQL
exécutée pour identifier la table cible et l'opération.

Tables observées par défaut : ``bars``, ``orders``, ``execution_fills``,
``risk_decisions``, ``risk_runs``. Les tables inconnues sont ignorées.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData, Table
from sqlalchemy.sql import Delete, Insert, Update

from lineage.graph_store import Edge, GraphStore, Node

LOGGER = logging.getLogger(__name__)

#: Tables observées par défaut.
DEFAULT_TABLES: tuple[str, ...] = (
    "bars", "orders", "execution_fills", "risk_decisions", "risk_runs",
)

#: Colonnes FK reconnues → relation lineage.
FK_TO_RELATION: dict[str, str] = {
    "run_id": "produced_by_run",
    "order_id": "child_of_order",
    "parent_id": "child_of",
    "fill_id": "originated_from_fill",
    "symbol": "concerns_symbol",
}

# Pour ne pas réenregistrer plusieurs fois les mêmes handlers
_REGISTERED: set[tuple[int, int]] = set()


def _emit_for_row(
    table: Table,
    op: str,
    params: dict[str, Any],
    store: GraphStore,
) -> None:
    pk_cols = list(table.primary_key.columns)
    if not pk_cols:
        return
    pk_name = pk_cols[0].name
    pk_val = params.get(pk_name)
    if pk_val is None:
        return
    node_id = f"{table.name}:{pk_val}"
    try:
        scalar_props = {
            k: v for k, v in params.items()
            if isinstance(v, (str, int, float, bool))
        }
        store.add_node(Node.make(node_id, table.name, op=op, **scalar_props))
        for col, rel in FK_TO_RELATION.items():
            if col == pk_name:
                continue
            val = params.get(col)
            if val is None:
                continue
            parent_label = (
                "run" if col == "run_id"
                else "order" if col == "order_id"
                else col.replace("_id", "")
            )
            parent_id = f"{parent_label}:{val}"
            store.add_edge(Edge.make(node_id, parent_id, rel))
    except Exception:  # noqa: BLE001
        LOGGER.exception("[lineage] handler %s/%s failed", table.name, op)


def _make_before_cursor_execute_handler(
    watched: dict[str, Table],
    store: GraphStore,
):
    def _handler(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        try:
            compiled = getattr(context, "compiled", None)
            if compiled is None:
                return
            clauseelement = getattr(compiled, "statement", None)
            if isinstance(clauseelement, Insert):
                op = "insert"
            elif isinstance(clauseelement, Update):
                op = "update"
            elif isinstance(clauseelement, Delete):
                op = "delete"
            else:
                return
            target = clauseelement.table
            tname = getattr(target, "name", None)
            if tname not in watched:
                return
            tbl = watched[tname]

            # context.compiled_parameters : liste de dicts
            params_list = getattr(context, "compiled_parameters", None) or []
            if not params_list and isinstance(parameters, dict):
                params_list = [parameters]
            elif not params_list and isinstance(parameters, (list, tuple)):
                params_list = [p for p in parameters if isinstance(p, dict)]

            for p in params_list:
                if isinstance(p, dict):
                    _emit_for_row(tbl, op, p, store)
        except Exception:  # noqa: BLE001
            LOGGER.exception("[lineage] before_cursor_execute handler failed")

    return _handler


def register_lineage_listeners(
    metadata: MetaData,
    store: GraphStore,
    *,
    tables: Iterable[str] = DEFAULT_TABLES,
    engine: Optional[Engine] = None,
) -> int:
    """Attache un handler ``before_cursor_execute`` à ``engine`` (ou à toute
    Engine via :class:`~sqlalchemy.engine.Engine` si ``engine=None``) qui
    pousse nœuds + arêtes dans ``store`` pour les INSERT/UPDATE/DELETE
    des ``tables`` listées présentes dans ``metadata``.

    Retourne le nombre de tables effectivement câblées.
    """
    watched: dict[str, Table] = {}
    for tname in tables:
        tbl = metadata.tables.get(tname)
        if tbl is not None:
            watched[tname] = tbl
    if not watched:
        return 0

    target = engine if engine is not None else Engine
    key = (id(target), id(store))
    if key in _REGISTERED:
        return len(watched)

    handler = _make_before_cursor_execute_handler(watched, store)
    event.listen(target, "before_cursor_execute", handler)
    _REGISTERED.add(key)
    return len(watched)


def clear_registry() -> None:
    """Utile en tests : vide le cache de déduplication."""
    _REGISTERED.clear()


__all__ = [
    "DEFAULT_TABLES",
    "FK_TO_RELATION",
    "register_lineage_listeners",
    "clear_registry",
]



