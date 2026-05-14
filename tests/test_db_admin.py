from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ihm.pages import db_admin as db_admin_page
from ihm.services.db_admin import (
    DatabaseTableSnapshot,
    PROTECTED_TABLES,
    TableCatalogEntry,
    build_table_purge_plan,
    discover_tables_from_sql_directory,
    execute_table_purge,
    list_grouped_tables,
    TablePurgeOperation,
    TablePurgePlan,
)


def test_discover_tables_from_sql_directory_extracts_expected_names(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    (sql_dir / "stock").mkdir(parents=True)
    (sql_dir / "news").mkdir(parents=True)
    (sql_dir / "stock" / "stock_scores.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha_trade.stock_scores (
            symbol VARCHAR(20) NOT NULL PRIMARY KEY
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "news" / "init_event_sentiment.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS alpha_trade.news_raw (
            article_id VARCHAR(128) NOT NULL PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS alpha_trade.news_sentiment (
            article_id VARCHAR(128) NOT NULL,
            CONSTRAINT fk_news_sentiment_article
                FOREIGN KEY (article_id) REFERENCES alpha_trade.news_raw(article_id)
        );
        """,
        encoding="utf-8",
    )

    tables = discover_tables_from_sql_directory(sql_dir)

    assert tables == {"stock_scores", "news_raw", "news_sentiment"}



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



def test_build_table_purge_plan_ignores_news_raw_like_other_protected_tables() -> None:
    snapshot = DatabaseTableSnapshot(
        existing_tables=("news_raw", "news_ticker_map", "news_ingestion_checkpoint", "news_sentiment"),
        row_estimates={
            "news_raw": 100,
            "news_ticker_map": 50,
            "news_ingestion_checkpoint": 5,
            "news_sentiment": 10,
        },
        foreign_key_pairs=(("news_sentiment", "news_raw"),),
    )

    plan = build_table_purge_plan(
        ["news_raw", "news_ticker_map", "news_ingestion_checkpoint", "news_sentiment"],
        snapshot,
    )

    assert "news_raw" in PROTECTED_TABLES
    assert "news_ticker_map" in PROTECTED_TABLES
    assert "news_ingestion_checkpoint" in PROTECTED_TABLES
    assert plan.protected_tables == ("news_ingestion_checkpoint", "news_raw", "news_ticker_map")
    assert [operation.table_name for operation in plan.operations] == ["news_sentiment"]



def test_list_grouped_tables_exposes_existing_tables_with_functionality_group() -> None:
    snapshot = DatabaseTableSnapshot(
        existing_tables=(
            "news_raw",
            "news_ticker_map",
            "news_ingestion_checkpoint",
            "portfolio_targets",
            "execution_broker_orders",
            "custom_table",
            "watcher_heartbeats",
            "account_risk_snapshots",
            "stock_quote_snapshots",
            "corporate_actions_audit_runs",
        ),
        row_estimates={
            "news_raw": 12,
            "news_ticker_map": 18,
            "news_ingestion_checkpoint": 2,
            "portfolio_targets": 3,
            "execution_broker_orders": 4,
            "custom_table": 0,
            "watcher_heartbeats": 1,
            "account_risk_snapshots": 2,
            "stock_quote_snapshots": 5,
            "corporate_actions_audit_runs": 1,
        },
        foreign_key_pairs=(),
    )

    grouped = list_grouped_tables(snapshot)

    news_raw_entry = next(entry for entry in grouped["News / Sentiment"] if entry.table_name == "news_raw")
    news_ticker_map_entry = next(entry for entry in grouped["News / Sentiment"] if entry.table_name == "news_ticker_map")
    checkpoint_entry = next(entry for entry in grouped["News / Sentiment"] if entry.table_name == "news_ingestion_checkpoint")

    assert any(entry.table_name == "news_raw" for entry in grouped["News / Sentiment"])
    assert news_raw_entry.protected is True
    assert news_ticker_map_entry.protected is True
    assert checkpoint_entry.protected is True
    assert any(entry.table_name == "portfolio_targets" for entry in grouped["Risk / Portefeuille"])
    assert any(entry.table_name == "account_risk_snapshots" for entry in grouped["Risk / Portefeuille"])
    assert any(entry.table_name == "execution_broker_orders" for entry in grouped["Exécution broker"])
    assert any(entry.table_name == "stock_quote_snapshots" for entry in grouped["Marché / Référentiel titres"])
    assert any(entry.table_name == "corporate_actions_audit_runs" for entry in grouped["Corporate Actions"])
    assert any(entry.table_name == "watcher_heartbeats" for entry in grouped["Observabilité / Runs"])
    assert any(entry.table_name == "execution_order_requests" for entry in grouped["Exécution broker"])
    assert not any(entry.table_name == "execution_orders" for entry in grouped["Exécution broker"])
    assert not any(entry.table_name == "execution_fills" for entry in grouped["Exécution broker"])
    assert any(entry.table_name == "custom_table" for entry in grouped["Autres / non classées"])


def test_apply_pending_widget_resets_clears_table_selection_and_confirmation(monkeypatch) -> None:
    session_state = {
        db_admin_page.PENDING_RESET_TABLES_KEY: ["stock_scores"],
        db_admin_page.PENDING_RESET_CONFIRM_KEY: True,
        db_admin_page._checkbox_key("stock_scores"): True,
        db_admin_page.CONFIRM_PURGE_KEY: True,
    }
    monkeypatch.setattr(db_admin_page.st, "session_state", session_state, raising=False)

    db_admin_page._apply_pending_widget_resets(
        {
            "Scoring": [
                TableCatalogEntry(
                    table_name="stock_scores",
                    functionality_group="Scoring",
                    exists_in_database=True,
                    protected=False,
                    row_estimate=12,
                )
            ]
        }
    )

    assert session_state[db_admin_page._checkbox_key("stock_scores")] is False
    assert session_state[db_admin_page.CONFIRM_PURGE_KEY] is False
    assert db_admin_page.PENDING_RESET_TABLES_KEY not in session_state
    assert db_admin_page.PENDING_RESET_CONFIRM_KEY not in session_state


def test_execute_table_purge_rejects_protected_tables_even_if_operation_is_injected() -> None:
    engine = create_engine("sqlite:///:memory:")
    plan = TablePurgePlan(
        selected_tables=("news_raw", "news_ticker_map", "news_ingestion_checkpoint"),
        operations=(
            TablePurgeOperation(
                table_name="news_raw",
                statement="DELETE FROM news_raw;",
                strategy="delete",
                reason="test guard",
            ),
            TablePurgeOperation(
                table_name="news_ticker_map",
                statement="DELETE FROM news_ticker_map;",
                strategy="delete",
                reason="test guard",
            ),
            TablePurgeOperation(
                table_name="news_ingestion_checkpoint",
                statement="DELETE FROM news_ingestion_checkpoint;",
                strategy="delete",
                reason="test guard",
            ),
        ),
        protected_tables=(),
        missing_tables=(),
        blocked_by_dependencies={},
        cycle_tables=(),
    )

    with pytest.raises(
        ValueError,
        match="Tables protégées : news_ingestion_checkpoint, news_raw, news_ticker_map",
    ):
        execute_table_purge(engine, plan)


