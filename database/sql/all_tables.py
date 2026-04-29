# Dépendance runtime attendue : PyMySQL (déjà déclarée dans le projet)
"""
Script pour créer toutes les tables de la base MySQL en une seule exécution.
Ce script exécute tous les CREATE TABLE trouvés dans database/sql/*/*.sql.
"""
import os
import glob
import re
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


class CreateJob(TypedDict):
    path: str
    statement: str
    table_name: str
    references: list[str]


def get_all_sql_files():
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


def extract_create_table_statements(sql_content):
    """Extrait tous les CREATE TABLE ... ; du contenu SQL."""
    # Match CREATE TABLE ... ; (non greedy)
    pattern = re.compile(r'(CREATE TABLE[\s\S]+?;)', re.IGNORECASE)
    return pattern.findall(sql_content)


def _normalize_table_name(table_name: str) -> str:
    return table_name.replace('`', '').split('.')[-1].lower()


def _extract_created_table_name(statement: str) -> str:
    match = CREATE_TABLE_PATTERN.search(statement)
    if not match:
        return '<unknown>'
    return _normalize_table_name(match.group(1))


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


def _load_create_jobs() -> list[CreateJob]:
    jobs: list[CreateJob] = []
    for path in get_all_sql_files():
        with open(path, encoding='utf-8') as f:
            content = f.read()
        for stmt in extract_create_table_statements(content):
            jobs.append({
                'path': path,
                'statement': stmt,
                'table_name': _extract_created_table_name(stmt),
                'references': _extract_referenced_table_names(stmt),
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
                'Impossible de résoudre l\'ordre de création des tables. '\
                'Tables encore bloquées :\n' + '\n'.join(details)
            )

        pending_jobs = next_pending


def main():
    jobs = _load_create_jobs()

    print(f"Nombre de tables à créer : {len(jobs)}")
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            _execute_create_jobs(cursor, jobs)
        conn.commit()
        print("Toutes les tables ont été créées.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

