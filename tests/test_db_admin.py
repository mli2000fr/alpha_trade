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


def test_render_last_purge_feedback_displays_success_and_clears_session_state(monkeypatch) -> None:
    session_state = {
        db_admin_page.LAST_PURGE_FEEDBACK_KEY: {
            "executed_tables": ["stock_scores", "model_metrics"],
            "total_rows_affected": 17,
        }
    }
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(db_admin_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(db_admin_page.st, "success", lambda message: messages.append(("success", str(message))))
    monkeypatch.setattr(db_admin_page.st, "caption", lambda message: messages.append(("caption", str(message))))

    db_admin_page._render_last_purge_feedback()

    assert messages[0] == (
        "success",
        "Vidage terminé pour 2 table(s). Total de lignes affectées : 17.",
    )
    assert "`stock_scores`" in messages[1][1]
    assert db_admin_page.LAST_PURGE_FEEDBACK_KEY not in session_state


def test_build_execute_blockers_requires_confirmation_before_enabling_button() -> None:
    plan = TablePurgePlan(
        selected_tables=("stock_scores",),
        operations=(
            TablePurgeOperation(
                table_name="stock_scores",
                statement="DELETE FROM `stock_scores`;",
                strategy="delete",
                reason="Suppression simple.",
            ),
        ),
        protected_tables=(),
        missing_tables=(),
        blocked_by_dependencies={},
        cycle_tables=(),
    )

    blockers_without_confirmation = db_admin_page._build_execute_blockers(plan, confirm_purge=False)
    blockers_with_confirmation = db_admin_page._build_execute_blockers(plan, confirm_purge=True)

    assert blockers_without_confirmation == (
        "Cochez la case de confirmation pour activer le bouton d'exécution.",
    )
    assert blockers_with_confirmation == ()


def test_execute_table_purge_rejects_protected_tables_even_if_operation_is_injected() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
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
    finally:
        engine.dispose()


def test_execute_table_purge_deletes_rows_and_reports_affected_count() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL, FOREIGN KEY(parent_id) REFERENCES parent(id))"
            )
            conn.exec_driver_sql("INSERT INTO parent (id) VALUES (1), (2)")
            conn.exec_driver_sql("INSERT INTO child (id, parent_id) VALUES (10, 1), (11, 1), (12, 2)")

        snapshot = DatabaseTableSnapshot(
            existing_tables=("child", "parent"),
            row_estimates={"child": 3, "parent": 2},
            foreign_key_pairs=(("child", "parent"),),
        )
        plan = build_table_purge_plan(["parent", "child"], snapshot)

        result = execute_table_purge(engine, plan)

        with engine.connect() as conn:
            remaining_child = conn.exec_driver_sql("SELECT COUNT(*) FROM child").scalar_one()
            remaining_parent = conn.exec_driver_sql("SELECT COUNT(*) FROM parent").scalar_one()

        assert [operation.table_name for operation in plan.operations] == ["child", "parent"]
        assert result.executed_tables == ("child", "parent")
        assert result.total_rows_affected == 5
        assert remaining_child == 0
        assert remaining_parent == 0
    finally:
        engine.dispose()


