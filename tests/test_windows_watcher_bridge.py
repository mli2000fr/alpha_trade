from __future__ import annotations

import tempfile
from pathlib import Path

from ihm.services import windows_watcher_bridge


class _CompletedProcess:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeScriptPath:
    def __init__(self, value: str) -> None:
        self._value = value

    def exists(self) -> bool:
        return True

    def __str__(self) -> str:
        return self._value


def test_run_allowed_bridge_script_rejects_unknown_script_key() -> None:
    try:
        windows_watcher_bridge.run_allowed_bridge_script("install")
    except ValueError as exc:
        assert "non autorisé" in str(exc)
    else:
        raise AssertionError("ValueError attendu")


def test_get_windows_watcher_status_returns_bridge_payload_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(windows_watcher_bridge.os, "name", "nt")
    monkeypatch.setattr(windows_watcher_bridge, "ALLOWED_BRIDGE_SCRIPTS", {"status": _FakeScriptPath("status.ps1")})
    monkeypatch.setattr(
        windows_watcher_bridge.subprocess,
        "run",
        lambda *args, **kwargs: _CompletedProcess(
            stdout='{"task":{"name":"AlphaTrade-ProtectionWatcher","exists":true},"service":{"name":"AlphaTradeProtectionWatcher","exists":false},"logSources":[],"bridge":{"script":"get_protection_watcher_status.ps1","mode":"read_only","allowlist":["status"]}}'
        ),
    )

    payload = windows_watcher_bridge.get_windows_watcher_status()

    assert payload["bridge_available"] is True
    assert payload["task"]["exists"] is True
    assert payload["service"]["exists"] is False


def test_list_windows_watcher_log_sources_formats_bridge_payload() -> None:
    rows = windows_watcher_bridge.list_windows_watcher_log_sources(
        {
            "logSources": [
                {"source": "Task Scheduler stdout", "runtime": "task", "kind": "stdout", "path": "C:/logs/task_stdout.log", "exists": True}
            ]
        }
    )

    assert rows == [
        {
            "source": "Task Scheduler stdout",
            "runtime": "task",
            "kind": "stdout",
            "path": "C:/logs/task_stdout.log",
            "exists": True,
        }
    ]


def test_read_windows_log_source_returns_tail_when_file_is_large() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "watcher.log"
        path.write_text("abcdefghij", encoding="utf-8")

        content = windows_watcher_bridge.read_windows_log_source(str(path), max_bytes=4)

    assert content == "ghij"


