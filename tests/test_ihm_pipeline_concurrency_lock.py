"""Sprint S2 / A-014 — verrou cross-process pipeline ↔ backtesting.

Vérifie que :
- ``acquire_lock("pipeline", ...)`` puis ``acquire_lock("backtesting", ...)``
  lève :class:`PipelineLockBusy`.
- ``release_lock`` libère et autorise une seconde acquisition.
- Lock obsolète (PID mort) → récupération automatique.
- ``set_locks_dir_for_tests`` permet l'isolation par tmp_path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ihm.services.pipeline_lock import (
    PipelineLockBusy,
    acquire_lock,
    list_active_locks,
    release_lock,
    set_locks_dir_for_tests,
)


@pytest.fixture(autouse=True)
def _isolated_locks_dir(tmp_path: Path):
    set_locks_dir_for_tests(tmp_path)
    yield
    set_locks_dir_for_tests(None)


def test_pipeline_blocks_backtesting():
    handle = acquire_lock("pipeline", owner="t", run_id="r1")
    try:
        with pytest.raises(PipelineLockBusy) as exc:
            acquire_lock("backtesting", owner="t", run_id="r2")
        assert exc.value.scope == "pipeline"
    finally:
        release_lock(handle)


def test_backtesting_blocks_pipeline():
    handle = acquire_lock("backtesting", owner="t", run_id="rb")
    try:
        with pytest.raises(PipelineLockBusy):
            acquire_lock("pipeline", owner="t", run_id="rp")
    finally:
        release_lock(handle)


def test_release_allows_reacquisition():
    h1 = acquire_lock("pipeline", owner="t", run_id="r1")
    release_lock(h1)
    h2 = acquire_lock("backtesting", owner="t", run_id="r2")
    release_lock(h2)
    assert list_active_locks() == []


def test_release_is_idempotent():
    handle = acquire_lock("pipeline", owner="t", run_id="r1")
    release_lock(handle)
    # Deuxième appel : ne lève pas.
    release_lock(handle)
    release_lock(None)


def test_stale_lock_dead_pid_is_reclaimed(tmp_path: Path):
    # Forge un lock pointant vers un PID très improbable d'être vivant.
    fake_payload = {
        "scope": "pipeline",
        "owner": "ghost",
        "run_id": "stale",
        "pid": 999999999,
        "acquired_at": "2026-01-01T00:00:00",
    }
    (tmp_path / "pipeline.lock").write_text(json.dumps(fake_payload), encoding="utf-8")

    # Doit pouvoir acquérir, le lock obsolète sera nettoyé.
    handle = acquire_lock("backtesting", owner="t", run_id="r1")
    try:
        active = list_active_locks()
        assert any(entry.get("scope") == "backtesting" for entry in active)
        assert not any(entry.get("owner") == "ghost" for entry in active)
    finally:
        release_lock(handle)


def test_same_run_id_is_idempotent():
    h1 = acquire_lock("pipeline", owner="t", run_id="r1", pid=os.getpid())
    try:
        # Re-acquérir le même scope/run_id/pid ne lève pas.
        h2 = acquire_lock("pipeline", owner="t", run_id="r1", pid=os.getpid())
        release_lock(h2)
    finally:
        release_lock(h1)

