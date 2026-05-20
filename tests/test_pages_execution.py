from __future__ import annotations

import pandas as pd

from ihm.pages import execution


class _DummyExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_common(monkeypatch, *, fills: pd.DataFrame, reconciliation: pd.DataFrame) -> dict[str, list[object]]:
    calls: dict[str, list[object]] = {
        "subheaders": [],
        "infos": [],
        "dataframes": [],
        "metrics": [],
        "captions": [],
        "expanders": [],
    }

    monkeypatch.setattr(execution, "db_available", lambda: True)
    monkeypatch.setattr(execution.st, "session_state", {}, raising=False)
    monkeypatch.setattr(execution.st, "header", lambda value: None)
    monkeypatch.setattr(execution.st, "subheader", lambda value: calls["subheaders"].append(value))
    monkeypatch.setattr(execution.st, "caption", lambda value: calls["captions"].append(value))
    monkeypatch.setattr(execution.st, "info", lambda value: calls["infos"].append(value))
    monkeypatch.setattr(execution.st, "error", lambda value: calls["infos"].append(value))
    monkeypatch.setattr(execution.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution.st, "selectbox", lambda label, options=None, *args, **kwargs: (options or [])[0] if (options or []) else None)
    monkeypatch.setattr(
        execution.st,
        "expander",
        lambda label, *args, **kwargs: calls["expanders"].append(label) or _DummyExpander(),
    )
    monkeypatch.setattr(execution, "metric_row", lambda metrics: calls["metrics"].append(metrics))
    monkeypatch.setattr(execution, "render_persistent_business_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "run_status_badge", lambda status: str(status))
    monkeypatch.setattr(execution, "heartbeat_badge", lambda *args, **kwargs: "heartbeat")
    monkeypatch.setattr(execution, "show_dataframe", lambda df, title=None, height=400: calls["dataframes"].append((title, df.copy() if hasattr(df, "copy") else df)))
    monkeypatch.setattr(execution, "render_symbol_table", lambda df, key=None, symbol_col=None, title=None, height=300: calls["dataframes"].append((title, df.copy() if hasattr(df, "copy") else df)))
    monkeypatch.setattr(execution, "get_run_summary", lambda record: record.get("run_summary") if record else None)
    monkeypatch.setattr(execution, "get_latest_run_business_summary", lambda **kwargs: None)
    monkeypatch.setattr(execution, "get_latest_execution_protection_watch_service_summary", lambda **kwargs: None)

    monkeypatch.setattr(
        execution,
        "get_execution_runs",
        lambda account_id=None: pd.DataFrame([
            {
                "exec_run_id": "exec-1",
                "status": "COMPLETED",
                "total_targets": 2,
                "total_submitted": 1,
                "total_filled": 0 if fills.empty else 1,
                "execution_profile": "overnight_cash_swing",
                "submission_window": "both",
                "account_id": "acct-1",
                "risk_run_id": "risk-1",
                "error_message": None,
            }
        ]),
    )
    monkeypatch.setattr(execution, "get_execution_account_constraints", lambda exec_run_id: {
        "account_type": "cash",
        "effective_pdt_rule": "off",
        "swing_only": True,
        "equity": 100000.0,
        "buying_power_available": 75000.0,
        "settled_cash_available": 75000.0,
        "daytrade_count": 0,
        "remaining_day_trade_slots": 0,
        "message": "snapshot broker preflight",
    })
    monkeypatch.setattr(
        execution,
        "get_execution_targets_snapshot",
        lambda exec_run_id: pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "candidate_rank": [4],
                "selector_signal_mode": ["strict"],
                "selection_explanation": ["mode=strict; rank=4"],
                "selector_earnings_blackout": [0],
                "target_shares": [100],
                "entry_price": [150.0],
            }
        ),
    )
    monkeypatch.setattr(execution, "get_execution_orders", lambda exec_run_id, **kwargs: pd.DataFrame({"symbol": ["AAPL"], "status": ["SUBMITTED"], "parent_intent_id": [None]}))
    monkeypatch.setattr(execution, "get_execution_fills", lambda exec_run_id, **kwargs: fills)
    monkeypatch.setattr(execution, "get_broker_positions", lambda account_id=None: pd.DataFrame({"symbol": ["AAPL"], "qty": [100]}))
    monkeypatch.setattr(execution, "get_execution_positions", lambda **kwargs: pd.DataFrame({"symbol": ["AAPL"], "net_qty": [100], "position_status": ["OPEN"]}))
    monkeypatch.setattr(execution, "get_execution_position_lots", lambda **kwargs: pd.DataFrame({"symbol": ["AAPL"], "opened_qty": [100], "remaining_qty": [100], "lot_status": ["OPEN"]}))
    monkeypatch.setattr(execution, "get_execution_reconciliation_results", lambda **kwargs: reconciliation)
    monkeypatch.setattr(execution, "get_execution_events", lambda exec_run_id: pd.DataFrame({"event_type": ["RUN_COMPLETED"]}))
    return calls


def test_pages_execution_importable():
    assert hasattr(execution, "__doc__")


def test_render_displays_reconciliation_actionable_block(monkeypatch) -> None:
    reconciliation = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "TSLA"],
            "action": ["buy_more", "investigate", "sell_excess"],
            "target_qty": [100.0, 0.0, 50.0],
            "internal_position_qty": [80.0, 12.0, 60.0],
            "broker_position_qty": [80.0, 12.0, 60.0],
            "position_delta": [-20.0, 12.0, 10.0],
            "has_open_protection": [True, True, False],
            "open_request_buy_qty": [0.0, 0.0, 0.0],
            "open_request_sell_qty": [0.0, 0.0, 0.0],
            "open_broker_buy_qty": [0.0, 0.0, 0.0],
            "open_broker_sell_qty": [0.0, 0.0, 0.0],
            "reconciliation_status": ["SAFE_AUTO", "MANUAL_REVIEW", "BLOCKED"],
            "reason_code": [None, "external_symbol", "missing_protection"],
            "created_at": ["2026-04-26T20:00:00"] * 3,
        }
    )
    calls = _patch_common(monkeypatch, fills=pd.DataFrame({"slippage_bps": [12.3]}), reconciliation=reconciliation)

    execution.render()

    assert "🧭 Réconciliation actionnable" in calls["subheaders"]
    assert any(metric for metric in calls["metrics"] if any(item[0] == "SAFE_AUTO" for item in metric))
    reconciliation_tables = [df for title, df in calls["dataframes"] if isinstance(df, pd.DataFrame) and "status_badge" in df.columns]
    assert reconciliation_tables
    assert list(reconciliation_tables[0]["status_badge"]) == ["🟢 SAFE_AUTO", "🟡 MANUAL_REVIEW", "🔴 BLOCKED"]


def test_render_explains_queued_run_without_fills(monkeypatch) -> None:
    calls = _patch_common(monkeypatch, fills=pd.DataFrame(), reconciliation=pd.DataFrame())

    execution.render()

    assert any("Aucun fill observé" in str(message) for message in calls["infos"])


def test_render_does_not_fallback_to_portfolio_targets_when_snapshot_missing(monkeypatch) -> None:
    calls = _patch_common(monkeypatch, fills=pd.DataFrame(), reconciliation=pd.DataFrame())
    monkeypatch.setattr(execution, "get_execution_targets_snapshot", lambda exec_run_id: pd.DataFrame())

    execution.render()

    assert any("Aucun snapshot de cibles figé" in str(message) for message in calls["infos"])
    assert any("portfolio_targets" in str(message) for message in calls["infos"])


def test_render_execution_snapshot_displays_selector_columns_when_available(monkeypatch) -> None:
    calls = _patch_common(monkeypatch, fills=pd.DataFrame(), reconciliation=pd.DataFrame())

    execution.render()

    target_tables = [
        df for title, df in calls["dataframes"]
        if title == "🎯 Snapshot des cibles consommées — contexte risk/selector figé"
    ]
    assert target_tables
    snapshot_df = target_tables[0]
    assert "candidate_rank" in snapshot_df.columns
    assert "selector_signal_mode" in snapshot_df.columns
    assert "selection_explanation" in snapshot_df.columns
    assert "selector_earnings_blackout" in snapshot_df.columns


def test_render_separates_run_scope_and_account_scope_context(monkeypatch) -> None:
    reconciliation = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "action": ["buy_more"],
            "target_qty": [100.0],
            "internal_position_qty": [80.0],
            "broker_position_qty": [80.0],
            "position_delta": [-20.0],
            "has_open_protection": [True],
            "open_request_buy_qty": [0.0],
            "open_request_sell_qty": [0.0],
            "open_broker_buy_qty": [0.0],
            "open_broker_sell_qty": [0.0],
            "reconciliation_status": ["SAFE_AUTO"],
            "reason_code": [None],
            "created_at": ["2026-04-26T20:00:00"],
        }
    )
    calls = _patch_common(monkeypatch, fills=pd.DataFrame({"slippage_bps": [12.3]}), reconciliation=reconciliation)

    execution.render()

    titles = [title for title, _ in calls["dataframes"]]
    assert "🧮 Positions projetées — scope run" in titles
    assert "🧮 Positions projetées — scope compte" in titles
    assert "🪵 Lots touchés par ce run" in titles
    assert "🪵 Lots reconstruits — scope compte" in titles
    assert "📚 Contexte compte — hors scope strict du run" in calls["expanders"]


# ---------------------------------------------------------------------------
# Sprint S3 / A-014 — alerte réconciliation diffs > 24h
# ---------------------------------------------------------------------------

def test_render_reconciliation_age_warning_on_old_unresolved_diffs(monkeypatch) -> None:
    """Un diff non résolu vieux de > 24h doit déclencher st.warning."""
    from datetime import datetime, timedelta, timezone

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S")
    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

    reconciliation = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "action": ["buy_more", "investigate"],
        "target_qty": [100.0, 0.0],
        "internal_position_qty": [80.0, 12.0],
        "broker_position_qty": [80.0, 12.0],
        "position_delta": [-20.0, 12.0],
        "has_open_protection": [True, True],
        "open_request_buy_qty": [0.0, 0.0],
        "open_request_sell_qty": [0.0, 0.0],
        "open_broker_buy_qty": [0.0, 0.0],
        "open_broker_sell_qty": [0.0, 0.0],
        "reconciliation_status": ["BLOCKED", "MANUAL_REVIEW"],
        "reason_code": ["missing_protection", "external_symbol"],
        "created_at": [old_ts, recent_ts],
    })

    warnings: list[str] = []
    calls = _patch_common(monkeypatch, fills=pd.DataFrame(), reconciliation=reconciliation)
    monkeypatch.setattr(execution.st, "warning", lambda msg: warnings.append(str(msg)))

    execution.render()

    assert any("24h" in w for w in warnings), "Warning 24h attendu pour diff non résolu vieux de 30h"


def test_render_no_age_warning_when_all_resolved(monkeypatch) -> None:
    """Pas de warning si les diffs non résolus sont récents."""
    from datetime import datetime, timedelta, timezone

    recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

    reconciliation = pd.DataFrame({
        "symbol": ["AAPL"],
        "action": ["buy_more"],
        "target_qty": [100.0],
        "internal_position_qty": [80.0],
        "broker_position_qty": [80.0],
        "position_delta": [-20.0],
        "has_open_protection": [True],
        "open_request_buy_qty": [0.0],
        "open_request_sell_qty": [0.0],
        "open_broker_buy_qty": [0.0],
        "open_broker_sell_qty": [0.0],
        "reconciliation_status": ["BLOCKED"],
        "reason_code": ["missing_protection"],
        "created_at": [recent_ts],
    })

    warnings: list[str] = []
    _patch_common(monkeypatch, fills=pd.DataFrame(), reconciliation=reconciliation)
    monkeypatch.setattr(execution.st, "warning", lambda msg: warnings.append(str(msg)))

    execution.render()

    assert not any("24h" in w for w in warnings), "Pas de warning 24h si diffs récents"
