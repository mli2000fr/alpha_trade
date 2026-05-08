"""Tests Phase 6.3 — leader election du ProtectionWatcherService."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from execution_engine.config import ProtectionWatcherServiceConfig
from execution_engine.protection_watcher import (
    ProtectionTransitionWatcher,
    ProtectionWatcherService,
)


def _build_service(*, lock_returns: bool, raise_on_lock: bool = False) -> tuple[ProtectionWatcherService, MagicMock]:
    repo = MagicMock()
    if raise_on_lock:
        repo.acquire_execution_lock.side_effect = RuntimeError("table missing")
    else:
        repo.acquire_execution_lock.return_value = lock_returns
    repo.release_execution_lock.return_value = None
    repo.upsert_watcher_heartbeat.return_value = None
    repo.upsert_watcher_service_summary.return_value = None
    repo.engine = None

    watcher = MagicMock(spec=ProtectionTransitionWatcher)
    watcher._repo = repo
    watcher.run.return_value = []  # aucun item

    cfg = ProtectionWatcherServiceConfig(
        interval_seconds=0.01,
        idle_interval_seconds=0.01,
        heartbeat_interval_seconds=0.01,
        max_consecutive_failures=3,
        stop_when_idle=True,
        max_iterations=1,
    )
    service = ProtectionWatcherService(
        watcher,
        cfg,
        sleep_fn=lambda _s: None,
        monotonic_fn=lambda: 0.0,
    )
    return service, repo


def test_watcher_service_acquires_leader_lock_with_watcher_prefix() -> None:
    service, repo = _build_service(lock_returns=True)
    summary = service.run(account_id="paper_main", limit=10)

    assert repo.acquire_execution_lock.called
    call = repo.acquire_execution_lock.call_args
    assert call.kwargs["account_id"] == "watcher:paper_main"
    assert call.kwargs["ttl_seconds"] >= 60
    # Le summary final expose l'account du lock pour observabilité.
    assert summary["leader_lock_account"] == "watcher:paper_main"
    assert repo.refresh_execution_lock.called
    refresh_call = repo.refresh_execution_lock.call_args
    assert refresh_call.kwargs["account_id"] == "watcher:paper_main"
    assert refresh_call.kwargs["exec_run_id"] == summary["run_id"]
    # Et libère le lock à la sortie.
    assert repo.release_execution_lock.called
    release_call = repo.release_execution_lock.call_args
    assert release_call.kwargs["account_id"] == "watcher:paper_main"


def test_watcher_service_aborts_when_leader_lock_held() -> None:
    service, repo = _build_service(lock_returns=False)
    summary = service.run(account_id="paper_main", limit=10)

    assert summary["status"] == "LEADER_LOCK_HELD"
    assert summary["leader_lock_account"] == "watcher:paper_main"
    # On ne lance PAS la boucle ni de release si on n'a pas le lock.
    assert repo.release_execution_lock.called is False
    # Aucun cycle d'item n'a été exécuté.
    service._watcher.run.assert_not_called()


def test_watcher_service_continues_when_lock_table_missing() -> None:
    """Best-effort : si la table execution_locks n'existe pas, on log et on continue."""
    service, repo = _build_service(lock_returns=False, raise_on_lock=True)
    summary = service.run(account_id="paper_main", limit=10)

    assert summary["status"] in {"COMPLETED", "RUNNING"}
    # La boucle a tourné au moins une itération.
    assert service._watcher.run.called


