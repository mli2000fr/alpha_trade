"""Tests Phase 5.2.c — kill switch global ``python -m execution_engine cancel-all``."""
from __future__ import annotations

import os
import runpy
import warnings
from datetime import datetime
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from execution_engine import cli as exec_cli
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from service.alpaca.trading_client import BrokerApiError

# ---------------------------------------------------------------------------
# CLI parsing — sous-commandes
# ---------------------------------------------------------------------------


def test_cli_default_subcommand_is_run() -> None:
    """Phase 5.2.c — compat IHM : sans sous-commande explicite, on route vers `run`."""
    args = exec_cli.parse_args(["--broker-mode", "paper", "--dry-run"])
    assert args.command == "run"
    assert args.broker_mode == "paper"
    assert args.dry_run is True


def test_cli_run_defaults_align_with_cash_swing_profile() -> None:
    args = exec_cli.parse_args(["--broker-mode", "paper"])

    assert args.command == "run"
    assert args.account_type == "cash"
    assert args.swing_only is True


def test_cli_run_accepts_run_execution_aliases() -> None:
    args = exec_cli.parse_args(["--date", "2026-04-19", "--run-id", "risk-123"])

    assert args.command == "run"
    assert args.trade_date == "2026-04-19"
    assert args.risk_run_id == "risk-123"


def test_cli_run_accepts_canonical_paper_mode_syntax() -> None:
    args = exec_cli.parse_args(["paper", "--run-id", "risk-123"])

    assert args.command == "run"
    assert args.broker_mode == "paper"
    assert args.dry_run is False
    assert args.risk_run_id == "risk-123"


def test_cli_run_accepts_canonical_simulate_mode_syntax() -> None:
    args = exec_cli.parse_args(["simulate", "--run-id", "risk-123"])

    assert args.command == "run"
    assert args.broker_mode == "paper"
    assert args.dry_run is True
    assert args.risk_run_id == "risk-123"


def test_cli_run_accepts_canonical_launcher_flags() -> None:
    args = exec_cli.parse_args([
        "--broker-mode", "paper",
        "--auto-rebalance",
        "--auto-watcher",
        "--submission-window", "pre_open",
        "--debug",
    ])

    assert args.command == "run"
    assert args.auto_rebalance is True
    assert args.auto_watcher is True
    assert args.submission_window == "pre_open"
    assert args.debug is True


def test_cli_explicit_run_subcommand() -> None:
    args = exec_cli.parse_args(["run", "--broker-mode", "live"])
    assert args.command == "run"
    assert args.broker_mode == "live"


def test_cli_cancel_all_subcommand_parses() -> None:
    args = exec_cli.parse_args(["cancel-all", "--account", "live1", "--dry-run"])
    assert args.command == "cancel-all"
    assert args.account == "live1"
    assert args.dry_run is True
    assert args.broker_mode == "paper"  # default


def test_cli_cancel_all_live_requires_confirm_account() -> None:
    """Phase 5.2.c — garde-fou live : --confirm-account doit valoir --account."""
    with (
        patch.object(exec_cli, "ExecutionRepository"),
        patch.object(exec_cli, "AlpacaTradingClient"),
        pytest.raises(SystemExit),
    ):
            exec_cli.main(["cancel-all", "--account", "live1", "--broker-mode", "live"])

    with (
        patch.object(exec_cli, "ExecutionRepository"),
        patch.object(exec_cli, "AlpacaTradingClient"),
        pytest.raises(SystemExit),
    ):
            exec_cli.main([
                "cancel-all", "--account", "live1", "--broker-mode", "live",
                "--confirm-account", "live2",
            ])


def test_cli_main_exports_feature_flags_before_running(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def _capture(args) -> None:
        seen["disable_sentiment"] = os.environ.get("ALPHA_TRADE_DISABLE_SENTIMENT")
        seen["disable_ml"] = os.environ.get("ALPHA_TRADE_DISABLE_ML")
        assert args.command == "run"

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_SENTIMENT", raising=False)
    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    monkeypatch.setattr(exec_cli, "configure_root_logging", lambda **_: None)
    monkeypatch.setattr(exec_cli, "_run_execution", _capture)

    exec_cli.main(["--disable-sentiment", "--disable-ml"])

    assert seen == {"disable_sentiment": "1", "disable_ml": "1"}


def test_cli_run_delegates_to_canonical_run_execution_launcher(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        exec_cli.run_execution,
        "resolve_mode_from_broker_mode",
        lambda *, broker_mode, dry_run: "simulate" if dry_run else broker_mode,
    )
    monkeypatch.setattr(
        exec_cli.run_execution,
        "abort_missing_env",
        lambda **kwargs: captured.setdefault("abort", dict(kwargs)),
    )
    monkeypatch.setattr(
        exec_cli.run_execution,
        "run",
        lambda **kwargs: captured.setdefault("run", dict(kwargs)),
    )

    exec_cli.main([
        "--broker-mode", "paper",
        "--dry-run",
        "--date", "2026-04-19",
        "--run-id", "risk-123",
        "--account", "paper1",
        "--auto-rebalance",
        "--auto-watcher",
        "--debug",
        "--submission-window", "pre_open",
        "--disable-sentiment",
        "--disable-ml",
    ])

    assert captured["abort"] == {"account_id": "paper1", "mode": "simulate"}
    forwarded = cast(dict[str, Any], captured["run"])
    assert forwarded["mode"] == "simulate"
    assert forwarded["run_id"] == "risk-123"
    assert forwarded["trade_date"] == "2026-04-19"
    assert forwarded["account_id"] == "paper1"
    assert forwarded["auto_rebalance"] is True
    assert forwarded["auto_watcher"] is True
    assert forwarded["debug"] is True
    assert forwarded["submission_window"] == "pre_open"
    assert os.environ.get("ALPHA_TRADE_DISABLE_SENTIMENT") == "1"
    assert os.environ.get("ALPHA_TRADE_DISABLE_ML") == "1"


# ---------------------------------------------------------------------------
# BrokerAdapter.cancel_all_open_orders
# ---------------------------------------------------------------------------


def _make_broker_with_client(open_orders, cancel_side_effect=None):
    client = MagicMock()
    client.list_orders.return_value = open_orders
    if cancel_side_effect is not None:
        client.cancel_order.side_effect = cancel_side_effect
    else:
        client.cancel_order.return_value = True
    cfg = ExecutionConfig(broker_mode="paper", account_id="acct1")
    return BrokerAdapter(client, cfg), client


def test_cancel_all_open_orders_returns_empty_when_no_open() -> None:
    broker, client = _make_broker_with_client([])
    results = broker.cancel_all_open_orders()
    assert results == []
    client.list_orders.assert_called_once_with(status="open", limit=500)
    client.cancel_order.assert_not_called()


def test_cancel_all_open_orders_dry_run_does_not_call_cancel() -> None:
    broker, client = _make_broker_with_client([
        {"id": "ord-1", "symbol": "AAPL"},
        {"id": "ord-2", "symbol": "MSFT"},
    ])
    results = broker.cancel_all_open_orders(dry_run=True)
    assert len(results) == 2
    assert all(r.canceled and r.error == "dry_run" for r in results)
    client.cancel_order.assert_not_called()


def test_cancel_all_open_orders_handles_broker_api_error_per_order() -> None:
    """Phase 5.2.c — un échec d'un ordre n'interrompt pas la boucle."""
    broker, client = _make_broker_with_client(
        [
            {"id": "ord-1", "symbol": "AAPL"},
            {"id": "ord-2", "symbol": "MSFT"},
            {"id": "ord-3", "symbol": "GOOG"},
        ],
        cancel_side_effect=[True, BrokerApiError(422, "boom"), True],
    )
    results = broker.cancel_all_open_orders()
    assert [r.broker_order_id for r in results] == ["ord-1", "ord-2", "ord-3"]
    assert results[0].canceled is True
    assert results[1].canceled is False
    assert "boom" in (results[1].error or "")
    assert results[2].canceled is True


def test_cancel_all_open_orders_skips_orders_without_id() -> None:
    broker, client = _make_broker_with_client([
        {"symbol": "AAPL"},  # missing id
        {"id": "ord-2", "symbol": "MSFT"},
    ])
    results = broker.cancel_all_open_orders()
    assert len(results) == 2
    assert results[0].canceled is False
    assert results[0].error == "missing broker_order_id"
    assert results[1].canceled is True


# ---------------------------------------------------------------------------
# Handler _run_cancel_all : persistance + run_summary
# ---------------------------------------------------------------------------


def test_cancel_all_persists_kill_switch_run_and_emits_summary(capsys) -> None:
    """E2E light : cancel-all écrit en DB (mock) + émet ::alpha_trade_run_summary::."""
    fake_repo = MagicMock()
    fake_client = MagicMock()
    fake_client.list_orders.return_value = [
        {"id": "ord-1", "symbol": "AAPL"},
        {"id": "ord-2", "symbol": "MSFT"},
    ]
    fake_client.cancel_order.return_value = True

    with (
        patch.object(exec_cli, "ExecutionRepository", return_value=fake_repo),
        patch.object(exec_cli, "AlpacaTradingClient", return_value=fake_client),
        patch.object(exec_cli, "configure_root_logging"),
    ):
        exec_cli.main([
            "cancel-all", "--account", "paper1", "--broker-mode", "paper",
            "--reason", "test kill",
        ])

    # Persist appelé une fois avec les bons args
    assert fake_repo.persist_kill_switch_run.call_count == 1
    kw = fake_repo.persist_kill_switch_run.call_args.kwargs
    assert kw["account_id"] == "paper1"
    assert kw["broker_mode"] == "paper"
    assert kw["reason"] == "test kill"
    assert kw["dry_run"] is False
    assert len(kw["results"]) == 2
    assert all(r["canceled"] for r in kw["results"])
    assert isinstance(kw["started_at"], datetime)
    assert isinstance(kw["finished_at"], datetime)

    # run_summary émis sur stdout
    captured = capsys.readouterr().out
    assert "::alpha_trade_run_summary::" in captured
    summary_line = next(line for line in captured.splitlines() if line.startswith("::alpha_trade_run_summary::"))
    payload = exec_cli.json.loads(summary_line.removeprefix("::alpha_trade_run_summary::"))
    assert payload["schema_version"] == 1
    assert payload["command"] == "cancel-all"
    assert payload["account_id"] == "paper1"
    assert payload["canceled"] == 2
    assert payload["failed"] == 0
    assert payload["event_type"] == "KILL_SWITCH_TRIGGERED"


def test_cancel_all_dry_run_marks_dry_run_true(capsys) -> None:
    fake_repo = MagicMock()
    fake_client = MagicMock()
    fake_client.list_orders.return_value = [{"id": "ord-1", "symbol": "AAPL"}]

    with (
        patch.object(exec_cli, "ExecutionRepository", return_value=fake_repo),
        patch.object(exec_cli, "AlpacaTradingClient", return_value=fake_client),
        patch.object(exec_cli, "configure_root_logging"),
    ):
        exec_cli.main([
            "cancel-all", "--account", "paper1", "--dry-run",
        ])

    fake_client.cancel_order.assert_not_called()
    kw = fake_repo.persist_kill_switch_run.call_args.kwargs
    assert kw["dry_run"] is True
    captured = capsys.readouterr().out
    assert "dry_run=True" in captured


def test_execution_facade_deprecation_warning(monkeypatch) -> None:
    captured: list[list[str]] = []

    monkeypatch.setattr(exec_cli, "main", lambda argv=None: captured.append(list(argv or [])))
    monkeypatch.setattr("sys.argv", ["python", "--broker-mode", "paper"])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        runpy.run_module("execution_engine.__main__", run_name="__main__")

    caught_warnings = list(caught or [])
    assert captured == [[]]
    assert any(item.category is DeprecationWarning for item in caught_warnings)
    assert any("run_execution.py" in str(item.message) for item in caught_warnings)


def test_execution_facade_cancel_all_does_not_warn(monkeypatch) -> None:
    captured: list[list[str]] = []

    monkeypatch.setattr(exec_cli, "main", lambda argv=None: captured.append(list(argv or [])))
    monkeypatch.setattr("sys.argv", ["python", "cancel-all", "--dry-run"])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        runpy.run_module("execution_engine.__main__", run_name="__main__")

    caught_warnings = list(caught or [])
    assert captured == [[]]
    assert not [item for item in caught_warnings if item.category is DeprecationWarning]

