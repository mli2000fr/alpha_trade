# Dépendance runtime attendue : PyMySQL (déjà déclarée dans le projet)
"""
Script pour créer toutes les tables de la base MySQL en une seule exécution.
Ce script exécute tous les CREATE TABLE trouvés dans database/sql/*/*.sql.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import pymysql


def _get_env(*names: str, default: str) -> str:
    """Retourne la première variable d'environnement non vide trouvée."""
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value
    return default


# Paramètres de connexion compatibles avec la convention projet et l'ancien script.
MYSQL_CONFIG = {
    'host': _get_env('DB_HOST', 'MYSQL_HOST', default='localhost'),
    'user': _get_env('LOGIN_DB', 'MYSQL_USER', default='root'),
    'password': _get_env('PASSWORD_DB', 'MYSQL_PASSWORD', default='root'),
    'database': _get_env('DB_NAME', 'MYSQL_DATABASE', default='alpha_trade'),
    'port': int(_get_env('DB_PORT', 'MYSQL_PORT', default='3306')),
    'charset': 'utf8mb4',
}

SQL_DIR = os.path.join(os.path.dirname(__file__))

CREATE_TABLE_PATTERN = re.compile(
    r'CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([`\w.]+)',
    re.IGNORECASE,
)
REFERENCES_PATTERN = re.compile(
    r'REFERENCES\s+([`\w.]+)',
    re.IGNORECASE,
)
CREATE_STATEMENT_PATTERN = re.compile(r'(CREATE\s+TABLE[\s\S]+?;)', re.IGNORECASE)
SQL_BLOCK_COMMENT_PATTERN = re.compile(r'/\*[\s\S]*?\*/')
SQL_LINE_COMMENT_PATTERN = re.compile(r'--[^\r\n]*')


class CreateJob(TypedDict):
    path: str
    statement: str
    table_name: str
    references: list[str]


@dataclass(frozen=True, slots=True)
class TableDefinition:
    table_name: str
    statement: str
    source_path: Path
    dependencies: tuple[str, ...]
    statements_in_source: int


def get_all_sql_files() -> list[str]:
    """Récupère tous les fichiers .sql canoniques (récursif).

    Filtres:
    - exclut ``truncate_*.sql`` (scripts de purge, non utilisables à la création) ;
    - exclut ``migration_*.sql`` (scripts d'ALTER TABLE one-shot, non idempotents
      lors d'une recréation à neuf).
    """
    return sorted([
        f for f in glob.glob(os.path.join(SQL_DIR, '**', '*.sql'), recursive=True)
        if not os.path.basename(f).startswith('truncate_')
        and not os.path.basename(f).startswith('migration_')
    ])


def _strip_sql_comments(sql_content: str) -> str:
    without_block_comments = SQL_BLOCK_COMMENT_PATTERN.sub('', sql_content)
    return SQL_LINE_COMMENT_PATTERN.sub('', without_block_comments)


def extract_create_table_statements(sql_content: str) -> list[str]:
    """Extrait tous les CREATE TABLE ... ; du contenu SQL sans commentaires."""
    cleaned_content = _strip_sql_comments(sql_content)
    return [statement.strip() for statement in CREATE_STATEMENT_PATTERN.findall(cleaned_content)]


def _normalize_table_name(table_name: str) -> str:
    return table_name.replace('`', '').split('.')[-1].lower()


def _extract_created_table_name(statement: str) -> str:
    match = CREATE_TABLE_PATTERN.search(statement)
    if not match:
        return '<unknown>'
    return _normalize_table_name(match.group(1))


def extract_table_name(statement: str) -> str:
    """API publique testable pour extraire le nom de table d'un CREATE TABLE."""
    return _extract_created_table_name(statement)


def _extract_referenced_table_names(statement: str) -> list[str]:
    return [
        _normalize_table_name(match)
        for match in REFERENCES_PATTERN.findall(statement)
    ]


def _is_missing_fk_dependency_error(exc: Exception) -> bool:
    if not isinstance(exc, pymysql.err.OperationalError):
        return False
    errno = exc.args[0] if exc.args else None
    message = str(exc).lower()
    return errno == 1824 or 'failed to open the referenced table' in message


def _read_sql_file(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig')


def _definition_priority(definition: TableDefinition) -> tuple[int, int, int, str]:
    expected_name = f'{definition.table_name}.sql'
    filename = definition.source_path.name.lower()
    return (
        0 if filename == expected_name else 1,
        definition.statements_in_source,
        len(str(definition.source_path)),
        str(definition.source_path).lower(),
    )


def load_table_definitions(sql_dir: str | Path = SQL_DIR) -> list[TableDefinition]:
    root = Path(sql_dir)
    definitions_by_table: dict[str, TableDefinition] = {}
    for path in sorted(root.rglob('*.sql')):
        if path.name.startswith('truncate_') or path.name.startswith('migration_'):
            continue
        statements = extract_create_table_statements(_read_sql_file(path))
        statements_in_source = len(statements)
        for statement in statements:
            definition = TableDefinition(
                table_name=_extract_created_table_name(statement),
                statement=statement.lstrip('\ufeff').strip(),
                source_path=path,
                dependencies=tuple(_extract_referenced_table_names(statement)),
                statements_in_source=statements_in_source,
            )
            current = definitions_by_table.get(definition.table_name)
            if current is None or _definition_priority(definition) < _definition_priority(current):
                definitions_by_table[definition.table_name] = definition
    return sorted(definitions_by_table.values(), key=lambda item: item.table_name)


def find_missing_dependencies(definitions: list[TableDefinition]) -> dict[str, tuple[str, ...]]:
    available_tables = {definition.table_name for definition in definitions}
    missing: dict[str, tuple[str, ...]] = {}
    for definition in definitions:
        unresolved = tuple(dep for dep in definition.dependencies if dep not in available_tables)
        if unresolved:
            missing[definition.table_name] = unresolved
    return missing


def order_table_definitions(definitions: list[TableDefinition]) -> list[TableDefinition]:
    missing = find_missing_dependencies(definitions)
    if missing:
        details = ', '.join(f'{table}: {deps}' for table, deps in sorted(missing.items()))
        raise RuntimeError(f'Dépendances de tables introuvables: {details}')

    ordered: list[TableDefinition] = []
    available_tables: set[str] = set()
    pending = list(sorted(definitions, key=lambda item: item.table_name))

    while pending:
        ready = [definition for definition in pending if set(definition.dependencies).issubset(available_tables)]
        if not ready:
            blocked = ', '.join(
                f'{definition.table_name}: {definition.dependencies}' for definition in pending
            )
            raise RuntimeError(f"Impossible de résoudre l'ordre des tables: {blocked}")
        ordered.extend(ready)
        available_tables.update(definition.table_name for definition in ready)
        ready_names = {definition.table_name for definition in ready}
        pending = [definition for definition in pending if definition.table_name not in ready_names]

    return ordered


def _load_create_jobs() -> list[CreateJob]:
    jobs: list[CreateJob] = []
    for definition in order_table_definitions(load_table_definitions(SQL_DIR)):
        jobs.append({
            'path': str(definition.source_path),
            'statement': definition.statement,
            'table_name': definition.table_name,
            'references': list(definition.dependencies),
        })
    return jobs


def _format_job_label(job: CreateJob) -> str:
    table_name = job['table_name']
    file_name = os.path.basename(job['path'])
    return f'{table_name} ({file_name})'


def _execute_create_jobs(cursor, jobs: list[CreateJob]) -> None:
    pending_jobs = list(jobs)
    executed_tables: set[str] = set()
    pass_index = 0

    while pending_jobs:
        pass_index += 1
        progressed = False
        next_pending: list[CreateJob] = []
        print(f'Passe #{pass_index} - tables restantes : {len(pending_jobs)}')

        for job in pending_jobs:
            statement = job['statement']
            label = _format_job_label(job)
            try:
                print(f'Execution : {statement.splitlines()[0][:80]} ... [{label}]')
                cursor.execute(statement)
                executed_tables.add(job['table_name'])
                progressed = True
            except Exception as exc:
                if _is_missing_fk_dependency_error(exc):
                    next_pending.append(job)
                    print(f'Différée (dépendance FK non prête) : {label} -> {exc}')
                    continue
                raise RuntimeError(f'Echec SQL sur {label}: {exc}') from exc

        if not progressed:
            details = []
            for job in next_pending:
                references = [ref for ref in job['references'] if ref not in executed_tables]
                ref_text = ', '.join(references) if references else 'inconnue'
                details.append(f'- {_format_job_label(job)} ; dépendances restantes : {ref_text}')
            raise RuntimeError(
                'Impossible de résoudre l\'ordre de création des tables. '
                'Tables encore bloquées :\n' + '\n'.join(details)
            )

        pending_jobs = next_pending


def main() -> None:
    jobs = _load_create_jobs()

    print(f"Nombre de tables à créer : {len(jobs)}")
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            _execute_create_jobs(cursor, jobs)
        conn.commit()
        print('Toutes les tables ont été créées.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()

