"""Sprint S2 / A-014 — verrou cross-process pipeline ↔ backtesting.

Empêche qu'un workflow pipeline (``start_pipeline_workflow``) et un run
backtesting (``start_backtesting_run``) tournent simultanément, ce qui
provoquait des conflits sur ``stock_scores``, ``stock_bars_daily`` et les
artefacts ML. Implémentation fichier-lock JSON dans
``artifacts/ihm_pipeline_runs/.locks/<scope>.lock``.

Stratégie :
- Le lock contient ``{scope, owner, run_id, pid, acquired_at}``.
- Si un lock existant pointe vers un PID mort, il est récupéré (stale).
- ``acquire_lock`` lève :class:`PipelineLockBusy` si un autre scope est
  actif (ou le même scope avec PID vivant).
- ``release_lock`` est idempotent.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

LOGGER = logging.getLogger(__name__)

LockScope = Literal["pipeline", "backtesting"]
_VALID_SCOPES: tuple[str, ...] = ("pipeline", "backtesting")


def _default_locks_dir() -> Path:
    # Import tardif pour éviter une dépendance circulaire au chargement IHM.
    from ihm.services.pipeline_runner import PROJECT_ROOT

    return PROJECT_ROOT / "artifacts" / "ihm_pipeline_runs" / ".locks"


_LOCKS_DIR_OVERRIDE: Path | None = None
_LOCAL_MUTEX = threading.Lock()


def set_locks_dir_for_tests(path: Path | None) -> None:
    """Override le dossier de locks (réservé aux tests)."""
    global _LOCKS_DIR_OVERRIDE
    _LOCKS_DIR_OVERRIDE = Path(path) if path is not None else None


def _locks_dir() -> Path:
    return _LOCKS_DIR_OVERRIDE if _LOCKS_DIR_OVERRIDE is not None else _default_locks_dir()


def _lock_path(scope: LockScope) -> Path:
    if scope not in _VALID_SCOPES:
        raise ValueError(f"scope invalide : {scope!r}")
    return _locks_dir() / f"{scope}.lock"


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _get_process_started_at(pid: int) -> datetime | None:
    if pid <= 0:
        return None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
            )
            if not handle:
                return None
            try:
                creation_time = wintypes.FILETIME()
                exit_time = wintypes.FILETIME()
                kernel_time = wintypes.FILETIME()
                user_time = wintypes.FILETIME()
                success = ctypes.windll.kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation_time),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel_time),
                    ctypes.byref(user_time),
                )
                if not success:
                    return None
                filetime = (creation_time.dwHighDateTime << 32) | creation_time.dwLowDateTime
                unix_timestamp = (filetime - 116444736000000000) / 10_000_000
                return datetime.fromtimestamp(unix_timestamp)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)

        proc_dir = Path(f"/proc/{int(pid)}")
        if proc_dir.exists():
            return datetime.fromtimestamp(proc_dir.stat().st_ctime)
    except Exception:
        return None
    return None


def _parse_lock_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class LockHandle:
    """Référence à un verrou actif (utilisée pour ``release_lock``)."""

    scope: LockScope
    owner: str
    run_id: str
    pid: int
    path: Path


class PipelineLockBusy(RuntimeError):
    """Levée si un autre run détient un verrou conflictuel."""

    def __init__(self, scope: str, holder: dict[str, object]):
        self.scope = scope
        self.holder = holder
        super().__init__(
            f"Verrou '{scope}' deja detenu par owner={holder.get('owner')!r} "
            f"run_id={holder.get('run_id')!r} pid={holder.get('pid')!r}"
        )


def _read_lock(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        # Lock corrompu -> traité comme stale, on le purgera.
        return {"_corrupt": True}


def _is_lock_active(payload: dict[str, object] | None) -> bool:
    if not payload or payload.get("_corrupt"):
        return False
    pid = int(payload.get("pid") or 0)
    if not _is_pid_alive(pid):
        return False

    process_started_at = _get_process_started_at(pid)
    expected_started_at = _parse_lock_datetime(payload.get("process_started_at"))
    if process_started_at is None:
        return True
    if expected_started_at is not None:
        return abs((process_started_at - expected_started_at).total_seconds()) <= 2.0

    acquired_at = _parse_lock_datetime(payload.get("acquired_at"))
    if acquired_at is not None and process_started_at > acquired_at + timedelta(seconds=2):
        LOGGER.warning(
            "Lock '%s' considere obsolete : pid=%s reutilise (process started_at=%s > acquired_at=%s).",
            payload.get("scope"),
            pid,
            process_started_at.isoformat(timespec="seconds"),
            acquired_at.isoformat(timespec="seconds"),
        )
        return False
    return True


def list_active_locks() -> list[dict[str, object]]:
    """Retourne les verrous encore vivants (PID actif)."""
    out: list[dict[str, object]] = []
    locks_dir = _locks_dir()
    if not locks_dir.exists():
        return out
    for entry in locks_dir.glob("*.lock"):
        payload = _read_lock(entry)
        if _is_lock_active(payload) and payload is not None:
            out.append(dict(payload))
    return out


def acquire_lock(
    scope: LockScope,
    *,
    owner: str,
    run_id: str,
    pid: int | None = None,
) -> LockHandle:
    """Acquiert ``scope`` ; lève :class:`PipelineLockBusy` si conflit.

    Conflits :
    - même scope déjà tenu (PID vivant).
    - autre scope déjà tenu (PID vivant) -> exclusion mutuelle pipeline ↔
      backtesting.
    """
    if scope not in _VALID_SCOPES:
        raise ValueError(f"scope invalide : {scope!r}")
    pid_int = int(pid if pid is not None else os.getpid())
    process_started_at = _get_process_started_at(pid_int)
    locks_dir = _locks_dir()
    locks_dir.mkdir(parents=True, exist_ok=True)

    with _LOCAL_MUTEX:
        for other in _VALID_SCOPES:
            payload = _read_lock(_lock_path(other))
            if _is_lock_active(payload) and payload is not None:
                # Ignore self : on ne se bloque pas si on tient déjà la même
                # combinaison (idempotent).
                if (
                    other == scope
                    and str(payload.get("run_id")) == str(run_id)
                    and int(payload.get("pid") or 0) == pid_int
                ):
                    continue
                raise PipelineLockBusy(other, payload)
            if payload and not _is_lock_active(payload):
                # Stale : nettoyage opportuniste.
                try:
                    _lock_path(other).unlink(missing_ok=True)
                    LOGGER.info("Lock '%s' obsolete supprime (pid=%s mort).", other, payload.get("pid"))
                except Exception:
                    pass

        target = _lock_path(scope)
        body = {
            "scope": scope,
            "owner": str(owner),
            "run_id": str(run_id),
            "pid": pid_int,
            "acquired_at": datetime.now().isoformat(timespec="seconds"),
            "process_started_at": process_started_at.isoformat(timespec="seconds") if process_started_at is not None else None,
        }
        target.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    LOGGER.info("Lock '%s' acquis | owner=%s run_id=%s pid=%s", scope, owner, run_id, pid_int)
    return LockHandle(scope=scope, owner=str(owner), run_id=str(run_id), pid=pid_int, path=target)


def release_lock(handle: LockHandle | None) -> None:
    """Libère le verrou (idempotent). N'agit que si le run_id correspond."""
    if handle is None:
        return
    with _LOCAL_MUTEX:
        payload = _read_lock(handle.path)
        if payload and str(payload.get("run_id")) == handle.run_id:
            try:
                handle.path.unlink(missing_ok=True)
                LOGGER.info("Lock '%s' libere | run_id=%s", handle.scope, handle.run_id)
            except Exception:
                LOGGER.warning("Echec suppression lock %s", handle.path, exc_info=True)


__all__ = [
    "LockHandle",
    "LockScope",
    "PipelineLockBusy",
    "acquire_lock",
    "list_active_locks",
    "release_lock",
    "set_locks_dir_for_tests",
]

