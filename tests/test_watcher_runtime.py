from __future__ import annotations

from ihm.services import watcher_runtime


class _Record:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id


def test_build_watcher_command_supports_once_and_service_modes() -> None:
    once_command = watcher_runtime.build_watcher_command(mode="once", account_id="acct-1", limit=25)
    service_command = watcher_runtime.build_watcher_command(
        mode="service",
        account_id="acct-1",
        limit=25,
        service_interval_seconds=15.0,
        idle_interval_seconds=45.0,
        heartbeat_interval_seconds=90.0,
    )

    assert "run_execution_protection_watch.py" in " ".join(once_command)
    assert "INFO" in once_command
    assert "--mode" in once_command and "once" in once_command
    assert "--account" in once_command and "acct-1" in once_command
    assert "--service-interval-seconds" in service_command
    assert "90.0" in service_command


def test_build_watcher_command_propagates_tp_and_trailing_configuration() -> None:
    command = watcher_runtime.build_watcher_command(
        mode="once",
        account_id="acct-1",
        profit_taker_pct=0.065,
        trailing_stop_pct=0.04,
        trailing_activation_trigger="profit_pct",
        trailing_activation_profit_pct=0.025,
    )

    assert "--profit-taker-pct" in command
    assert command[command.index("--profit-taker-pct") + 1] == "0.065"
    assert "--trailing-stop-pct" in command
    assert command[command.index("--trailing-stop-pct") + 1] == "0.04"
    assert "--trailing-activation-trigger" in command
    assert command[command.index("--trailing-activation-trigger") + 1] == "profit_pct"


def test_launch_watcher_once_uses_managed_run(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", lambda account_id=None: None)
    monkeypatch.setattr(watcher_runtime, "get_active_watcher_once_run", lambda account_id=None: None)

    def fake_start_managed_run(**kwargs):
        captured.update(kwargs)
        return _Record("watch-once-1")

    monkeypatch.setattr(watcher_runtime, "start_managed_run", fake_start_managed_run)

    record = watcher_runtime.launch_watcher_once(
        db_config={"host": "localhost"},
        account_id="acct-1",
        limit=12,
        profit_taker_pct=0.07,
        trailing_stop_pct=0.04,
        trailing_activation_trigger="profit_pct",
        trailing_activation_profit_pct=0.02,
    )

    assert record.run_id == "watch-once-1"
    assert captured["step_key"] == watcher_runtime.WATCHER_ONCE_STEP_KEY
    assert captured["account_id"] == "acct-1"
    assert "once" in captured["command"]
    assert captured["command"][captured["command"].index("--profit-taker-pct") + 1] == "0.07"
    assert captured["command"][captured["command"].index("--trailing-stop-pct") + 1] == "0.04"
    assert captured["command"][captured["command"].index("--trailing-activation-trigger") + 1] == "profit_pct"


def test_start_local_watcher_service_rejects_existing_local_service(monkeypatch) -> None:
    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", lambda account_id=None: {"run_id": "svc-1"})

    try:
        watcher_runtime.start_local_watcher_service(account_id="acct-1")
    except RuntimeError as exc:
        assert "déjà actif" in str(exc)
    else:
        raise AssertionError("RuntimeError attendu")


def test_stop_local_watcher_service_rejects_non_local_service_run(monkeypatch) -> None:
    monkeypatch.setattr(watcher_runtime, "get_pipeline_run_record", lambda run_id: {"step_key": watcher_runtime.WATCHER_ONCE_STEP_KEY})

    try:
        watcher_runtime.stop_local_watcher_service("run-1")
    except RuntimeError as exc:
        assert "services watcher lancés depuis l'IHM" in str(exc)
    else:
        raise AssertionError("RuntimeError attendu")


def test_stop_local_watcher_service_releases_local_leader_lock(monkeypatch) -> None:
    released: list[str | None] = []

    monkeypatch.setattr(
        watcher_runtime,
        "get_pipeline_run_record",
        lambda run_id: {
            "step_key": watcher_runtime.WATCHER_SERVICE_STEP_KEY,
            "account_id": "acct-1",
        },
    )
    monkeypatch.setattr(watcher_runtime, "stop_pipeline_run", lambda run_id: True)
    monkeypatch.setattr(
        watcher_runtime,
        "_force_release_local_watcher_leader_lock",
        lambda account_id=None: released.append(account_id),
    )

    assert watcher_runtime.stop_local_watcher_service("run-1") is True
    assert released == ["acct-1"]


def test_list_watcher_run_history_filters_step_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        watcher_runtime,
        "load_pipeline_history",
        lambda: [
            {"run_id": "watch-1", "step_key": watcher_runtime.WATCHER_ONCE_STEP_KEY, "account_id": "acct-1"},
            {"run_id": "pipe-1", "step_key": "pipeline_workflow", "account_id": "acct-1"},
            {"run_id": "watch-2", "step_key": watcher_runtime.WATCHER_SERVICE_STEP_KEY, "account_id": "acct-2"},
        ],
    )

    rows = watcher_runtime.list_watcher_run_history(account_id="acct-1")

    assert [row["run_id"] for row in rows] == ["watch-1"]


def test_read_watcher_run_logs_returns_empty_for_non_watcher_run(monkeypatch) -> None:
    monkeypatch.setattr(watcher_runtime, "get_watcher_run_record", lambda run_id: None)

    assert watcher_runtime.read_watcher_run_logs("run-1", stream="all") == ""


def test_build_windows_integration_rows_includes_account_specific_commands() -> None:
    rows = watcher_runtime.build_windows_integration_rows(account_id="acct-1")

    assert len(rows) == 3
    assert any("install_protection_watcher_task.ps1" in row["command"] for row in rows)
    assert all("acct-1" in row["command"] for row in rows)


def test_restart_local_watcher_service_stops_then_starts(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", lambda account_id=None: {"run_id": "svc-1"})
    monkeypatch.setattr(watcher_runtime, "stop_local_watcher_service", lambda run_id: calls.append(("stop", run_id)) or True)

    def fake_start_local_watcher_service(**kwargs):
        calls.append(("start", kwargs["account_id"]))
        calls.append(("manual_sl", kwargs["manual_buy_stop_loss_pct"]))
        calls.append(("profit_taker", kwargs["profit_taker_pct"]))
        return _Record("svc-2")

    monkeypatch.setattr(watcher_runtime, "start_local_watcher_service", fake_start_local_watcher_service)

    record = watcher_runtime.restart_local_watcher_service(
        account_id="acct-1",
        manual_buy_stop_loss_pct=0.06,
        profit_taker_pct=0.09,
    )

    assert record.run_id == "svc-2"
    assert calls == [("stop", "svc-1"), ("start", "acct-1"), ("manual_sl", 0.06), ("profit_taker", 0.09)]



