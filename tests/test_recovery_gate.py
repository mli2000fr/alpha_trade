from __future__ import annotations

from service.forward_pit import recovery_gate


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar(self) -> int:
        return self.value


class _Connection:
    def __init__(self, value: int, calls: list[tuple[str, dict]]) -> None:
        self.value = value
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return _ScalarResult(self.value)


class _Engine:
    def __init__(self, value: int, calls: list[tuple[str, dict]]) -> None:
        self.value = value
        self.calls = calls

    def connect(self) -> _Connection:
        return _Connection(self.value, self.calls)


def test_generic_recovery_uses_forward_pit_success(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(recovery_gate, "get_sqlalchemy_engine", lambda: _Engine(1, calls))
    assert recovery_gate.has_recent_success("security_master_snapshot", 12)
    sql, params = calls[0]
    assert "pit_collection_runs" in sql
    assert "COMPLETED_WITH_WARNINGS" in sql
    assert params["batch"] == "security_master_snapshot"
    assert "cutoff" in params


def test_analyst_recovery_uses_legacy_collection_run(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(recovery_gate, "get_sqlalchemy_engine", lambda: _Engine(0, calls))
    assert not recovery_gate.has_recent_success("analyst_snapshot_collection", 10)
    sql, params = calls[0]
    assert "analyst_snapshot_collection_run" in sql
    assert "batch" not in params
    assert "cutoff" in params
