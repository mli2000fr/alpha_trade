"""Services d'administration DB pour l'IHM Streamlit."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ihm.services.pipeline_runner import PROJECT_ROOT

SQL_DIRECTORY = PROJECT_ROOT / "database" / "sql"
PROTECTED_TABLES = frozenset({
    "stock_metadata",
    "stock_bars",
    "stock_bars_daily",
    "stock_bar",
    "stock_bar_daily",
    "news_raw",
    "news_ticker_map",
    "news_ingestion_checkpoint",
})

FUNCTIONALITY_GROUP_ORDER: tuple[str, ...] = (
    "Marché / Référentiel titres",
    "News / Sentiment",
    "ML / Modèles",
    "Risk / Portefeuille",
    "Exécution broker",
    "Corporate Actions",
    "Observabilité / Runs",
    "Autres / non classées",
)

FUNCTIONALITY_TABLES: dict[str, tuple[str, ...]] = {
    "Marché / Référentiel titres": (
        "stock_bars",
        "stock_bars_daily",
        "stock_metadata",
        "stock_scores",
        "stock_scores_history",
        "stock_quote_snapshots",
        "stock_macro_indicators_daily",
        "stock_earnings_calendar",
        "cleaning_audit_latest",
        "cleaning_audit_runs",
        "cleaning_audit_quotes_runs",
        "cleaning_audit_earnings_runs",
    ),
    "News / Sentiment": (
        "news_raw",
        "news_sentiment",
        "news_ticker_map",
        "news_ingestion_checkpoint",
        "macro_event_audit",
        "ticker_daily_sentiment_features",
        "sector_daily_sentiment_features",
    ),
    "ML / Modèles": (
        "model_registry",
        "model_training_run",
        "model_metrics",
        "model_governance",
        "model_predictions",
    ),
    "Risk / Portefeuille": (
        "risk_decisions",
        "portfolio_targets",
        "portfolio_cash_ledger",
        "account_risk_snapshots",
    ),
    "Exécution broker": (
        "execution_runs",
        "execution_targets_snapshot",
        "execution_order_requests",
        "execution_broker_orders",
        "execution_broker_fills",
        "execution_positions",
        "execution_position_lots",
        "execution_reconciliation_results",
        "execution_locks",
        "execution_events",
        "broker_account_snapshots",
        "broker_positions_snapshots",
    ),
    "Corporate Actions": (
        "corporate_actions_events",
        "corporate_actions_applications",
        "corporate_actions_audit_runs",
    ),
    "Observabilité / Runs": (
        "run_business_summaries",
        "watcher_heartbeats",
    ),
}

ADDITIONAL_KNOWN_TABLES = frozenset(
    {
        table_name
        for tables in FUNCTIONALITY_TABLES.values()
        for table_name in tables
    }
)

_CREATE_TABLE_PATTERN = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`?(?:\w+)`?\.)?`?(?P<table>\w+)`?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DatabaseTableSnapshot:
    existing_tables: tuple[str, ...]
    row_estimates: dict[str, int | None]
    foreign_key_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class TableCatalogEntry:
    table_name: str
    functionality_group: str
    exists_in_database: bool
    protected: bool
    row_estimate: int | None


@dataclass(frozen=True, slots=True)
class TablePurgeOperation:
    table_name: str
    statement: str
    strategy: str
    reason: str


@dataclass(frozen=True, slots=True)
class TablePurgePlan:
    selected_tables: tuple[str, ...]
    operations: tuple[TablePurgeOperation, ...]
    protected_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]
    blocked_by_dependencies: dict[str, tuple[str, ...]]
    cycle_tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TablePurgeResult:
    executed_tables: tuple[str, ...]
    executed_statements: tuple[str, ...]
    total_rows_affected: int


def _normalize_table_name(value: str) -> str:
    cleaned = value.strip().strip("`").strip()
    if not cleaned:
        return ""
    return cleaned.split(".")[-1].strip("`").lower()


def discover_tables_from_sql_directory(sql_directory: Path = SQL_DIRECTORY) -> set[str]:
    tables: set[str] = set()
    if not sql_directory.exists():
        return tables

    for path in sorted(sql_directory.rglob("*.sql")):
        content = path.read_text(encoding="utf-8", errors="replace")
        for match in _CREATE_TABLE_PATTERN.finditer(content):
            normalized = _normalize_table_name(match.group("table"))
            if normalized:
                tables.add(normalized)
    return tables


def _classify_table(table_name: str) -> str:
    for group_name, tables in FUNCTIONALITY_TABLES.items():
        if table_name in tables:
            return group_name

    if table_name.startswith("news_") or table_name.endswith("_sentiment_features"):
        return "News / Sentiment"
    if table_name.startswith("model_"):
        return "ML / Modèles"
    if table_name.startswith("execution_") or table_name.startswith("broker_"):
        return "Exécution broker"
    if table_name.startswith("corporate_actions_"):
        return "Corporate Actions"
    if table_name.startswith("portfolio_") or table_name.startswith("risk_"):
        return "Risk / Portefeuille"
    if table_name.startswith("watcher_"):
        return "Observabilité / Runs"
    if table_name.startswith("stock_") or table_name.startswith("cleaning_"):
        return "Marché / Référentiel titres"
    return "Autres / non classées"


def load_database_table_snapshot(engine: Engine) -> DatabaseTableSnapshot:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name, table_rows
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name
                """
            )
        ).fetchall()
        relations = conn.execute(
            text(
                """
                SELECT DISTINCT table_name AS child_table, referenced_table_name AS parent_table
                FROM information_schema.key_column_usage
                WHERE table_schema = DATABASE()
                  AND referenced_table_name IS NOT NULL
                ORDER BY child_table, parent_table
                """
            )
        ).fetchall()

    existing_tables = tuple(sorted(_normalize_table_name(str(row[0])) for row in rows if row[0]))
    row_estimates = {
        _normalize_table_name(str(row[0])): (int(row[1]) if row[1] is not None else None)
        for row in rows
        if row[0]
    }
    foreign_key_pairs = tuple(
        (
            _normalize_table_name(str(row[0])),
            _normalize_table_name(str(row[1])),
        )
        for row in relations
        if row[0] and row[1]
    )
    return DatabaseTableSnapshot(
        existing_tables=existing_tables,
        row_estimates=row_estimates,
        foreign_key_pairs=foreign_key_pairs,
    )


def list_grouped_tables(snapshot: DatabaseTableSnapshot) -> dict[str, list[TableCatalogEntry]]:
    declared_tables = discover_tables_from_sql_directory()
    all_tables = set(snapshot.existing_tables) | declared_tables | set(ADDITIONAL_KNOWN_TABLES)

    grouped: dict[str, list[TableCatalogEntry]] = {group_name: [] for group_name in FUNCTIONALITY_GROUP_ORDER}
    existing_set = set(snapshot.existing_tables)
    for table_name in sorted(all_tables):
        group_name = _classify_table(table_name)
        grouped.setdefault(group_name, []).append(
            TableCatalogEntry(
                table_name=table_name,
                functionality_group=group_name,
                exists_in_database=table_name in existing_set,
                protected=table_name in PROTECTED_TABLES,
                row_estimate=snapshot.row_estimates.get(table_name),
            )
        )

    return {group_name: entries for group_name, entries in grouped.items() if entries}


def _build_dependency_maps(
    foreign_key_pairs: Iterable[tuple[str, str]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    parents_by_child: dict[str, set[str]] = defaultdict(set)
    children_by_parent: dict[str, set[str]] = defaultdict(set)
    for child_table, parent_table in foreign_key_pairs:
        child = _normalize_table_name(child_table)
        parent = _normalize_table_name(parent_table)
        if not child or not parent:
            continue
        parents_by_child[child].add(parent)
        children_by_parent[parent].add(child)
    return parents_by_child, children_by_parent


def _topological_delete_order(
    selected_tables: set[str],
    foreign_key_pairs: Iterable[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    graph: dict[str, set[str]] = {table_name: set() for table_name in selected_tables}
    indegree: dict[str, int] = {table_name: 0 for table_name in selected_tables}

    for child_table, parent_table in foreign_key_pairs:
        child = _normalize_table_name(child_table)
        parent = _normalize_table_name(parent_table)
        if child not in selected_tables or parent not in selected_tables or child == parent:
            continue
        if parent in graph[child]:
            continue
        graph[child].add(parent)
        indegree[parent] += 1

    queue: deque[str] = deque(sorted(table_name for table_name, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while queue:
        table_name = queue.popleft()
        ordered.append(table_name)
        for parent in sorted(graph[table_name]):
            indegree[parent] -= 1
            if indegree[parent] == 0:
                queue.append(parent)

    cycle_tables = sorted(table_name for table_name in selected_tables if table_name not in ordered)
    if cycle_tables:
        ordered.extend(cycle_tables)
    return ordered, cycle_tables


def build_table_purge_plan(
    selected_tables: Iterable[str],
    snapshot: DatabaseTableSnapshot,
) -> TablePurgePlan:
    normalized_selection: list[str] = []
    seen: set[str] = set()
    for table_name in selected_tables:
        normalized = _normalize_table_name(table_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_selection.append(normalized)

    protected_tables = tuple(sorted(table_name for table_name in normalized_selection if table_name in PROTECTED_TABLES))
    existing_set = set(snapshot.existing_tables)
    requested_tables = [table_name for table_name in normalized_selection if table_name not in PROTECTED_TABLES]
    missing_tables = tuple(sorted(table_name for table_name in requested_tables if table_name not in existing_set))
    selectable_tables = {table_name for table_name in requested_tables if table_name in existing_set}

    parents_by_child, children_by_parent = _build_dependency_maps(snapshot.foreign_key_pairs)
    blocked_by_dependencies = {
        table_name: tuple(sorted(child_table for child_table in children_by_parent.get(table_name, set()) if child_table not in selectable_tables))
        for table_name in sorted(selectable_tables)
        if any(child_table not in selectable_tables for child_table in children_by_parent.get(table_name, set()))
    }

    if blocked_by_dependencies:
        return TablePurgePlan(
            selected_tables=tuple(normalized_selection),
            operations=(),
            protected_tables=protected_tables,
            missing_tables=missing_tables,
            blocked_by_dependencies=blocked_by_dependencies,
            cycle_tables=(),
        )

    ordered_tables, cycle_tables = _topological_delete_order(selectable_tables, snapshot.foreign_key_pairs)
    operations = tuple(
        TablePurgeOperation(
            table_name=table_name,
            statement=f"DELETE FROM `{table_name}`;",
            strategy="delete",
            reason=(
                "Suppression ordonnée pour respecter les clés étrangères."
                if parents_by_child.get(table_name) or children_by_parent.get(table_name)
                else "Suppression simple de toutes les lignes de la table."
            ),
        )
        for table_name in ordered_tables
    )
    return TablePurgePlan(
        selected_tables=tuple(normalized_selection),
        operations=operations,
        protected_tables=protected_tables,
        missing_tables=missing_tables,
        blocked_by_dependencies={},
        cycle_tables=tuple(cycle_tables),
    )


def execute_table_purge(engine: Engine, plan: TablePurgePlan) -> TablePurgeResult:
    protected_tables = tuple(
        sorted(
            {
                *plan.protected_tables,
                *(operation.table_name for operation in plan.operations if operation.table_name in PROTECTED_TABLES),
            }
        )
    )
    if protected_tables:
        raise ValueError(f"Tables protégées : {', '.join(protected_tables)}")
    if plan.missing_tables:
        raise ValueError(f"Tables introuvables en base : {', '.join(plan.missing_tables)}")
    if plan.blocked_by_dependencies:
        raise ValueError("Certaines tables sélectionnées sont bloquées par des tables dépendantes non sélectionnées.")

    executed_tables: list[str] = []
    executed_statements: list[str] = []
    total_rows_affected = 0
    with engine.begin() as conn:
        for operation in plan.operations:
            result = conn.execute(text(operation.statement))
            executed_tables.append(operation.table_name)
            executed_statements.append(operation.statement)
            rowcount_raw = getattr(result, "rowcount", None)
            rowcount = int(rowcount_raw) if isinstance(rowcount_raw, int) and rowcount_raw >= 0 else 0
            total_rows_affected += int(rowcount)

    return TablePurgeResult(
        executed_tables=tuple(executed_tables),
        executed_statements=tuple(executed_statements),
        total_rows_affected=total_rows_affected,
    )


