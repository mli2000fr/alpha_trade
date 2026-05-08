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


def test_launch_watcher_once_for_all_accounts_iterates_over_all(monkeypatch) -> None:
    """Issue 1 (2026-05) — Boucle sur tous les comptes Alpaca déclarés."""
    monkeypatch.setattr(watcher_runtime, "list_alpaca_account_ids", lambda: ["acct-1", "acct-2", "acct-3"])
    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", lambda account_id=None: None)
    monkeypatch.setattr(watcher_runtime, "get_active_watcher_once_run", lambda account_id=None: None)

    started: list[str] = []

    def fake_start_managed_run(**kwargs):
        started.append(kwargs["account_id"])
        return _Record(f"watch-once-{kwargs['account_id']}")

    monkeypatch.setattr(watcher_runtime, "start_managed_run", fake_start_managed_run)

    records = watcher_runtime.launch_watcher_once_for_all_accounts(broker_mode="paper")

    assert started == ["acct-1", "acct-2", "acct-3"]
    assert [r.run_id for r in records] == ["watch-once-acct-1", "watch-once-acct-2", "watch-once-acct-3"]


def test_launch_watcher_once_for_all_accounts_skips_already_active(monkeypatch) -> None:
    """Issue 1 — Comptes déjà couverts par un service / once sont ignorés sans bloquer les autres."""
    monkeypatch.setattr(watcher_runtime, "list_alpaca_account_ids", lambda: ["acct-1", "acct-2"])

    def fake_active_service(account_id=None):
        return {"run_id": "svc-existing"} if account_id == "acct-1" else None

    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", fake_active_service)
    monkeypatch.setattr(watcher_runtime, "get_active_watcher_once_run", lambda account_id=None: None)

    started: list[str] = []

    def fake_start_managed_run(**kwargs):
        started.append(kwargs["account_id"])
        return _Record(f"watch-{kwargs['account_id']}")

    monkeypatch.setattr(watcher_runtime, "start_managed_run", fake_start_managed_run)

    records = watcher_runtime.launch_watcher_once_for_all_accounts(broker_mode="paper")

    assert started == ["acct-2"]
    assert len(records) == 1


def test_start_local_watcher_service_for_all_accounts_iterates(monkeypatch) -> None:
    """Issue 1 — Démarre un service par compte Alpaca."""
    monkeypatch.setattr(watcher_runtime, "list_alpaca_account_ids", lambda: ["a", "b"])
    monkeypatch.setattr(watcher_runtime, "get_active_local_watcher_service", lambda account_id=None: None)
    monkeypatch.setattr(watcher_runtime, "get_active_watcher_once_run", lambda account_id=None: None)

    started: list[str] = []

    def fake_start_managed_run(**kwargs):
        started.append(kwargs["account_id"])
        return _Record(f"svc-{kwargs['account_id']}")

    monkeypatch.setattr(watcher_runtime, "start_managed_run", fake_start_managed_run)

    records = watcher_runtime.start_local_watcher_service_for_all_accounts(broker_mode="paper")

    assert started == ["a", "b"]
    assert {r.run_id for r in records} == {"svc-a", "svc-b"}


def test_serialize_all_accounts_watcher_control_state_aggregates(monkeypatch) -> None:
    monkeypatch.setattr(watcher_runtime, "list_alpaca_account_ids", lambda: ["a", "b"])

    def fake_state(account_id=None):
        if account_id == "a":
            return {"local_service_active": True, "local_service_run_id": "svc-a", "local_once_active": False, "local_once_run_id": ""}
        return {"local_service_active": False, "local_service_run_id": "", "local_once_active": True, "local_once_run_id": "once-b"}

    monkeypatch.setattr(watcher_runtime, "serialize_local_watcher_control_state", fake_state)

    state = watcher_runtime.serialize_all_accounts_watcher_control_state()

    assert state["any_service_active"] is True
    assert state["any_once_active"] is True
    assert state["all_service_active"] is False
    assert set(state["accounts"].keys()) == {"a", "b"}


def test_launch_watcher_once_for_all_accounts_raises_when_no_account(monkeypatch) -> None:
    """Issue 1 — Si aucun compte n'a pu être lancé, on remonte clairement l'erreur."""
    monkeypatch.setattr(watcher_runtime, "list_alpaca_account_ids", lambda: ["a"])
    monkeypatch.setattr(
        watcher_runtime, "get_active_local_watcher_service",
        lambda account_id=None: {"run_id": "svc-existing"},
    )
    monkeypatch.setattr(watcher_runtime, "get_active_watcher_once_run", lambda account_id=None: None)

    try:
        watcher_runtime.launch_watcher_once_for_all_accounts(broker_mode="paper")
    except RuntimeError as exc:
        assert "Aucun watcher once" in str(exc)
    else:
        raise AssertionError("RuntimeError attendu")
