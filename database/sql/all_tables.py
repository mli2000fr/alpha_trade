# Pour installer le connecteur MySQL : pip install mysql-connector-python
"""
Script pour créer toutes les tables de la base MySQL en une seule exécution.
Ce script exécute tous les CREATE TABLE trouvés dans database/sql/*/*.sql.
"""
import os
import glob
import mysql.connector

# Paramètres de connexion à adapter
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'root'),
    'database': os.environ.get('MYSQL_DATABASE', 'alpha_trade'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
}

SQL_DIR = os.path.join(os.path.dirname(__file__))
LEGACY_EXECUTION_SQL_BASENAMES = {
    'execution_orders.sql',
    'execution_fills.sql',
}


def get_all_sql_files():
    """Récupère tous les fichiers .sql dans les sous-dossiers hors bundle legacy retiré."""
    return [
        f for f in glob.glob(os.path.join(SQL_DIR, '*', '*.sql'))
        if not os.path.basename(f).startswith('truncate_')
        and os.path.basename(f) not in LEGACY_EXECUTION_SQL_BASENAMES
    ]


def extract_create_table_statements(sql_content):
    """Extrait tous les CREATE TABLE ... ; du contenu SQL."""
    import re
    # Match CREATE TABLE ... ; (non greedy)
    pattern = re.compile(r'(CREATE TABLE[\s\S]+?;)', re.IGNORECASE)
    return pattern.findall(sql_content)


def main():
    sql_files = get_all_sql_files()
    all_statements = []
    for path in sql_files:
        with open(path, encoding='utf-8') as f:
            content = f.read()
            stmts = extract_create_table_statements(content)
            all_statements.extend(stmts)

    print(f"Nombre de tables à créer : {len(all_statements)}")
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            for stmt in all_statements:
                print(f"Execution : {stmt.splitlines()[0][:80]} ...")
                cursor.execute(stmt)
        conn.commit()
        print("Toutes les tables ont été créées.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

