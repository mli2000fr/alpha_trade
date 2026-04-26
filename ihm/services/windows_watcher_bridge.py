"""Pont très encadré entre l'IHM et l'observabilité Windows du watcher.

Ce module n'autorise que des opérations en lecture seule, via une allowlist
explicite de scripts PowerShell dédiés à la supervision.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "windows" / "get_protection_watcher_status.ps1"
DEFAULT_TASK_NAME = "AlphaTrade-ProtectionWatcher"
DEFAULT_SERVICE_NAME = "AlphaTradeProtectionWatcher"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_IMPORTED_LOG_BYTES = 128_000
ALLOWED_BRIDGE_SCRIPTS: dict[str, Path] = {
    "status": STATUS_SCRIPT_PATH,
}


def _bridge_unavailable_payload(reason: str, *, script_key: str = "status") -> dict[str, Any]:
    return {
        "bridge_available": False,
        "bridge_mode": "read_only",
        "script_key": script_key,
        "reason": reason,
        "task": {"exists": False, "state": "unknown"},
        "service": {"exists": False, "status": "unknown"},
        "logSources": [],
    }


def run_allowed_bridge_script(
    script_key: str,
    *,
    arguments: list[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if script_key not in ALLOWED_BRIDGE_SCRIPTS:
        raise ValueError(f"Script PowerShell non autorisé via le bridge IHM: {script_key}")
    if os.name != "nt":
        return _bridge_unavailable_payload("bridge_windows_only", script_key=script_key)

    script_path = ALLOWED_BRIDGE_SCRIPTS[script_key]
    if not script_path.exists():
        return _bridge_unavailable_payload(f"script_missing:{script_path}", script_key=script_key)

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *(arguments or []),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _bridge_unavailable_payload("timeout", script_key=script_key)
    except Exception as exc:
        return _bridge_unavailable_payload(f"bridge_error:{exc}", script_key=script_key)

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        return {
            **_bridge_unavailable_payload(f"returncode:{completed.returncode}", script_key=script_key),
            "stderr": stderr,
            "stdout": stdout,
        }
    if not stdout:
        return _bridge_unavailable_payload("empty_stdout", script_key=script_key)

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            **_bridge_unavailable_payload("invalid_json", script_key=script_key),
            "stdout": stdout,
            "stderr": stderr,
        }
    if not isinstance(payload, dict):
        return {
            **_bridge_unavailable_payload("unexpected_payload", script_key=script_key),
            "stdout": stdout,
            "stderr": stderr,
        }

    payload.setdefault("bridge_available", True)
    payload.setdefault("bridge_mode", "read_only")
    payload.setdefault("script_key", script_key)
    if stderr:
        payload.setdefault("stderr", stderr)
    return payload


def get_windows_watcher_status(
    *,
    workspace_path: str | None = None,
    task_name: str = DEFAULT_TASK_NAME,
    service_name: str = DEFAULT_SERVICE_NAME,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    args = ["-TaskName", task_name, "-ServiceName", service_name]
    if workspace_path:
        args.extend(["-WorkspacePath", workspace_path])
    payload = run_allowed_bridge_script("status", arguments=args, timeout_seconds=timeout_seconds)
    payload.setdefault("task", {})
    payload.setdefault("service", {})
    payload.setdefault("logSources", [])
    return payload


def list_windows_watcher_log_sources(payload: dict[str, Any] | None) -> list[dict[str, object]]:
    if not payload:
        return []
    raw_sources = payload.get("logSources")
    if not isinstance(raw_sources, list):
        return []

    rows: list[dict[str, object]] = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        path_value = str(source.get("path", "") or "").strip()
        exists = bool(source.get("exists", False))
        rows.append(
            {
                "source": str(source.get("source", "") or ""),
                "runtime": str(source.get("runtime", "") or ""),
                "kind": str(source.get("kind", "") or ""),
                "path": path_value,
                "exists": exists,
            }
        )
    return rows


def read_windows_log_source(path_value: str, *, max_bytes: int = MAX_IMPORTED_LOG_BYTES) -> str:
    cleaned_path = str(path_value or "").strip()
    if not cleaned_path:
        return ""
    path = Path(cleaned_path)
    if not path.exists() or not path.is_file():
        return ""

    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content.encode("utf-8", errors="replace")) <= max_bytes:
        return content

    encoded = content.encode("utf-8", errors="replace")
    tail = encoded[-max_bytes:]
    return tail.decode("utf-8", errors="replace")

