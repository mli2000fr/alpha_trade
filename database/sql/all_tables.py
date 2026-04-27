"""Crée toutes les tables SQL du projet dans un ordre compatible avec les FK."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
import os
from pathlib import Path
import re

import pymysql

MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "root"),
    "db": os.environ.get("MYSQL_DATABASE", "alpha_trade"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "charset": "utf8mb4",
    "autocommit": False,
}

SQL_DIR = Path(__file__).resolve().parent
SQL_FILE_ENCODING = "utf-8-sig"

CREATE_TABLE_PATTERN = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`?(?:\w+)`?\.)?`?(?P<table>\w+)`?",
    re.IGNORECASE,
)
REFERENCES_PATTERN = re.compile(
    r"\bREFERENCES\s+(?:`?(?:\w+)`?\.)?`?(?P<table>\w+)`?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class TableDefinition:
    table_name: str
    statement: str
    source_path: Path
    dependencies: tuple[str, ...]
    statements_in_source: int


def _normalize_table_name(value: str) -> str:
    cleaned = value.strip().strip("`").strip()
    if not cleaned:
        return ""
    return cleaned.split(".")[-1].strip("`").lower()


def get_all_sql_files(sql_directory: Path = SQL_DIR) -> list[Path]:
    """Liste récursivement tous les fichiers SQL candidats."""
    return sorted(
        path
        for path in sql_directory.rglob("*.sql")
        if path.is_file() and not path.name.startswith("truncate_")
    )


def _read_sql_file(path: Path) -> str:
    """Lit un fichier SQL en supprimant automatiquement un BOM UTF-8 éventuel."""
    return path.read_text(encoding=SQL_FILE_ENCODING, errors="replace")


def _split_sql_statements(sql_content: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(sql_content):
        char = sql_content[index]
        next_char = sql_content[index + 1] if index + 1 < len(sql_content) else ""
        previous_char = sql_content[index - 1] if index > 0 else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                current.append(char)
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            if char == "\n":
                current.append(char)
            index += 1
            continue

        if not in_single and not in_double and not in_backtick:
            if char == "-" and next_char == "-":
                in_line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue

        if char == "'" and not in_double and not in_backtick and previous_char != "\\":
            in_single = not in_single
        elif char == '"' and not in_single and not in_backtick and previous_char != "\\":
            in_double = not in_double
        elif char == "`" and not in_single and not in_double:
            in_backtick = not in_backtick

        if char == ";" and not in_single and not in_double and not in_backtick:
            statement = "".join(current).lstrip("\ufeff").strip()
            if statement:
                statements.append(f"{statement};")
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    tail = "".join(current).lstrip("\ufeff").strip()
    if tail:
        statements.append(tail)
    return statements


def extract_create_table_statements(sql_content: str) -> list[str]:
    """Extrait les CREATE TABLE complets du contenu SQL."""
    return [
        statement
        for statement in _split_sql_statements(sql_content)
        if CREATE_TABLE_PATTERN.search(statement)
    ]


def extract_table_name(statement: str) -> str:
    match = CREATE_TABLE_PATTERN.search(statement)
    if match is None:
        return ""
    return _normalize_table_name(match.group("table"))


def extract_referenced_tables(statement: str) -> tuple[str, ...]:
    dependencies = {
        _normalize_table_name(match.group("table"))
        for match in REFERENCES_PATTERN.finditer(statement)
    }
    dependencies.discard("")
    return tuple(sorted(dependencies))


def _definition_priority(definition: TableDefinition) -> tuple[int, int, int, str]:
    return (
        0 if definition.source_path.stem.lower() == definition.table_name else 1,
        definition.statements_in_source,
        len(definition.source_path.parts),
        definition.source_path.as_posix(),
    )


def load_table_definitions(sql_directory: Path = SQL_DIR) -> list[TableDefinition]:
    """Construit le catalogue canonique des tables en dédupliquant les doublons."""
    definitions_by_table: dict[str, TableDefinition] = {}

    for path in get_all_sql_files(sql_directory):
        content = _read_sql_file(path)
        statements = extract_create_table_statements(content)
        for statement in statements:
            table_name = extract_table_name(statement)
            if not table_name:
                continue
            candidate = TableDefinition(
                table_name=table_name,
                statement=statement,
                source_path=path,
                dependencies=extract_referenced_tables(statement),
                statements_in_source=len(statements),
            )
            current = definitions_by_table.get(table_name)
            if current is None or _definition_priority(candidate) < _definition_priority(current):
                definitions_by_table[table_name] = candidate

    return sorted(definitions_by_table.values(), key=lambda definition: definition.table_name)


def find_missing_dependencies(definitions: list[TableDefinition]) -> dict[str, tuple[str, ...]]:
    known_tables = {definition.table_name for definition in definitions}
    missing: dict[str, tuple[str, ...]] = {}
    for definition in definitions:
        missing_refs = sorted(
            dependency
            for dependency in definition.dependencies
            if dependency not in known_tables and dependency != definition.table_name
        )
        if missing_refs:
            missing[definition.table_name] = tuple(missing_refs)
    return missing


def order_table_definitions(definitions: list[TableDefinition]) -> list[TableDefinition]:
    """Trie les tables pour créer d'abord les parents, puis les enfants."""
    definitions_by_table = {definition.table_name: definition for definition in definitions}
    children_by_parent: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {definition.table_name: 0 for definition in definitions}

    for definition in definitions:
        for dependency in definition.dependencies:
            if dependency == definition.table_name or dependency not in definitions_by_table:
                continue
            if definition.table_name in children_by_parent[dependency]:
                continue
            children_by_parent[dependency].add(definition.table_name)
            indegree[definition.table_name] += 1

    heap: list[tuple[tuple[int, int, int, str], str]] = [
        (_definition_priority(definitions_by_table[table_name]), table_name)
        for table_name, degree in indegree.items()
        if degree == 0
    ]
    heapq.heapify(heap)

    ordered: list[TableDefinition] = []
    while heap:
        _, table_name = heapq.heappop(heap)
        ordered.append(definitions_by_table[table_name])
        for child_table in sorted(children_by_parent.get(table_name, ())):
            indegree[child_table] -= 1
            if indegree[child_table] == 0:
                heapq.heappush(heap, (_definition_priority(definitions_by_table[child_table]), child_table))

    if len(ordered) != len(definitions):
        remaining_tables = sorted(
            table_name for table_name, degree in indegree.items() if degree > 0
        )
        raise ValueError(
            "Cycle de dépendances détecté entre les tables : "
            + ", ".join(remaining_tables)
        )

    return ordered


def main() -> None:
    definitions = load_table_definitions()
    if not definitions:
        print("Aucune table CREATE TABLE trouvée dans database/sql.")
        return

    missing_dependencies = find_missing_dependencies(definitions)
    if missing_dependencies:
        print("Attention : dépendances référencées mais absentes du catalogue SQL :")
        for table_name, dependencies in sorted(missing_dependencies.items()):
            print(f"  - {table_name}: {', '.join(dependencies)}")

    ordered_definitions = order_table_definitions(definitions)
    print(f"Nombre de tables à créer : {len(ordered_definitions)}")
    for index, definition in enumerate(ordered_definitions, start=1):
        relative_path = definition.source_path.relative_to(SQL_DIR).as_posix()
        deps = ", ".join(definition.dependencies) if definition.dependencies else "aucune"
        print(f"{index:02d}. {definition.table_name} <- {relative_path} | dépendances: {deps}")

    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        cursor = conn.cursor()
        try:
            for index, definition in enumerate(ordered_definitions, start=1):
                relative_path = definition.source_path.relative_to(SQL_DIR).as_posix()
                print(f"[{index}/{len(ordered_definitions)}] Exécution : {definition.table_name} ({relative_path})")
                cursor.execute(definition.statement)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()

    print("Toutes les tables ont été créées dans l'ordre des dépendances.")


if __name__ == "__main__":
    main()

