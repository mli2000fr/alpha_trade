from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "database" / "sql" / "all_tables.py"


def _load_all_tables_module():
    if "mysql" not in sys.modules:
        mysql_module = types.ModuleType("mysql")
        connector_module = types.ModuleType("mysql.connector")
        connector_module.connect = lambda **kwargs: None
        mysql_module.connector = connector_module
        sys.modules["mysql"] = mysql_module
        sys.modules["mysql.connector"] = connector_module

    spec = importlib.util.spec_from_file_location("database.sql.all_tables", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


all_tables = _load_all_tables_module()


def test_extract_create_table_statements_ignores_comments_and_non_create() -> None:
    sql_content = """
    -- CREATE TABLE ignored_comment (id INT);
    ALTER TABLE execution_runs ADD COLUMN account_id VARCHAR(32);
    /* CREATE TABLE ignored_block (id INT); */

    CREATE TABLE IF NOT EXISTS alpha_trade.parent_table (
        id BIGINT PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS alpha_trade.child_table (
        id BIGINT PRIMARY KEY,
        parent_id BIGINT NOT NULL,
        CONSTRAINT fk_child_parent FOREIGN KEY (parent_id)
            REFERENCES alpha_trade.parent_table(id)
    );
    """

    statements = all_tables.extract_create_table_statements(sql_content)

    assert [all_tables.extract_table_name(statement) for statement in statements] == [
        "parent_table",
        "child_table",
    ]


def test_load_table_definitions_deduplicates_and_orders_dependencies(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    (sql_dir / "news").mkdir(parents=True)

    (sql_dir / "news" / "init_event_sentiment.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha_trade.news_raw (
            article_id VARCHAR(128) NOT NULL PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS alpha_trade.news_sentiment (
            article_id VARCHAR(128) NOT NULL PRIMARY KEY,
            CONSTRAINT fk_news_sentiment_article FOREIGN KEY (article_id)
                REFERENCES alpha_trade.news_raw(article_id)
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "news" / "news_raw.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha_trade.news_raw (
            article_id VARCHAR(128) NOT NULL PRIMARY KEY,
            source VARCHAR(32) NULL
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "news" / "news_sentiment.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha_trade.news_sentiment (
            article_id VARCHAR(128) NOT NULL PRIMARY KEY,
            CONSTRAINT fk_news_sentiment_article FOREIGN KEY (article_id)
                REFERENCES alpha_trade.news_raw(article_id)
        );
        """,
        encoding="utf-8",
    )

    definitions = all_tables.load_table_definitions(sql_dir)
    by_table = {definition.table_name: definition for definition in definitions}

    assert sorted(by_table) == ["news_raw", "news_sentiment"]
    assert by_table["news_raw"].source_path.name == "news_raw.sql"
    assert by_table["news_sentiment"].source_path.name == "news_sentiment.sql"

    ordered = all_tables.order_table_definitions(definitions)

    assert [definition.table_name for definition in ordered] == ["news_raw", "news_sentiment"]


def test_load_table_definitions_handles_utf8_bom(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    (sql_dir / "execution").mkdir(parents=True)

    bom_file = sql_dir / "execution" / "execution_locks.sql"
    bom_file.write_text(
        "CREATE TABLE IF NOT EXISTS execution_locks (\n"
        "    account_id VARCHAR(32) NOT NULL PRIMARY KEY\n"
        ");\n",
        encoding="utf-8-sig",
    )

    definitions = all_tables.load_table_definitions(sql_dir)

    assert len(definitions) == 1
    assert definitions[0].table_name == "execution_locks"
    assert not definitions[0].statement.startswith("\ufeff")
    assert definitions[0].statement.startswith("CREATE TABLE")


def test_find_missing_dependencies_reports_unknown_parent() -> None:
    definition = all_tables.TableDefinition(
        table_name="child_table",
        statement="CREATE TABLE child_table (parent_id BIGINT);",
        source_path=Path("child_table.sql"),
        dependencies=("missing_parent",),
        statements_in_source=1,
    )

    missing = all_tables.find_missing_dependencies([definition])

    assert missing == {"child_table": ("missing_parent",)}


