from pathlib import Path

from ihm.services.db_admin import (
    DatabaseTableSnapshot,
    PROTECTED_TABLES,
    build_table_purge_plan,
    discover_tables_from_sql_directory,
    list_grouped_tables,
)


def test_discover_tables_from_sql_directory_extracts_expected_names(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "purge.sql").write_text(
        """
        TRUNCATE TABLE stock_scores;
        DELETE FROM alpha_trade.news_raw;
        ALTER TABLE execution_runs ADD COLUMN account_id VARCHAR(32);
        """,
        encoding="utf-8",
    )

    tables = discover_tables_from_sql_directory(sql_dir)

    assert {"stock_scores", "news_raw", "execution_runs"}.issubset(tables)



def test_build_table_purge_plan_orders_children_before_parents_and_blocks_partial_selection() -> None:
    snapshot = DatabaseTableSnapshot(
        existing_tables=(
            "execution_broker_fills",
            "execution_broker_orders",
            "execution_order_requests",
            "execution_runs",
        ),
        row_estimates={
            "execution_broker_fills": 5,
            "execution_broker_orders": 2,
            "execution_order_requests": 2,
            "execution_runs": 1,
        },
        foreign_key_pairs=(
            ("execution_broker_fills", "execution_broker_orders"),
            ("execution_broker_orders", "execution_order_requests"),
            ("execution_order_requests", "execution_runs"),
        ),
    )

    blocked_plan = build_table_purge_plan(["execution_runs"], snapshot)
    full_plan = build_table_purge_plan(
        ["execution_runs", "execution_order_requests", "execution_broker_orders", "execution_broker_fills"],
        snapshot,
    )

    assert blocked_plan.operations == ()
    assert blocked_plan.blocked_by_dependencies == {"execution_runs": ("execution_order_requests",)}
    assert [operation.table_name for operation in full_plan.operations] == [
        "execution_broker_fills",
        "execution_broker_orders",
        "execution_order_requests",
        "execution_runs",
    ]



def test_build_table_purge_plan_ignores_protected_tables() -> None:
    snapshot = DatabaseTableSnapshot(
        existing_tables=("stock_bars", "stock_scores"),
        row_estimates={"stock_bars": 100, "stock_scores": 10},
        foreign_key_pairs=(),
    )

    plan = build_table_purge_plan(["stock_bars", "stock_scores"], snapshot)

    assert "stock_bars" in PROTECTED_TABLES
    assert plan.protected_tables == ("stock_bars",)
    assert [operation.table_name for operation in plan.operations] == ["stock_scores"]



def test_list_grouped_tables_exposes_existing_tables_with_functionality_group() -> None:
    snapshot = DatabaseTableSnapshot(
        existing_tables=("news_raw", "portfolio_targets", "execution_broker_orders", "custom_table"),
        row_estimates={"news_raw": 12, "portfolio_targets": 3, "execution_broker_orders": 4, "custom_table": 0},
        foreign_key_pairs=(),
    )

    grouped = list_grouped_tables(snapshot)

    assert any(entry.table_name == "news_raw" for entry in grouped["News / Sentiment"])
    assert any(entry.table_name == "portfolio_targets" for entry in grouped["Risk / Portefeuille"])
    assert any(entry.table_name == "execution_broker_orders" for entry in grouped["Exécution broker"])
    assert any(entry.table_name == "execution_order_requests" for entry in grouped["Exécution broker"])
    assert not any(entry.table_name == "execution_orders" for entry in grouped["Exécution broker"])
    assert not any(entry.table_name == "execution_fills" for entry in grouped["Exécution broker"])
    assert any(entry.table_name == "custom_table" for entry in grouped["Autres / non classées"])

