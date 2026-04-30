"""Tests Phase 6.2 — rotation des artefacts IHM (process_registry)."""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Recharge process_registry avec RUNS_DIR pointant sur tmp_path."""
    # On force la rétention par défaut (30j) sauf override par test.
    monkeypatch.delenv("IHM_RUNS_RETENTION_DAYS", raising=False)
    import ihm.services.process_registry as registry

    monkeypatch.setattr(registry, "RUNS_DIR", tmp_path / "runs", raising=True)
    monkeypatch.setattr(registry, "HISTORY_INDEX_PATH", tmp_path / "runs" / "history_index.json", raising=True)
    return registry


def _seed_history(registry, runs: dict[str, dict[str, object]]) -> None:
    registry._ensure_storage()
    registry._write_history_index(runs)


def test_rotate_pipeline_artifacts_keeps_recent_runs(isolated_registry, tmp_path: Path) -> None:
    now = datetime.now()
    history = {
        "recent": {"finished_at": (now - timedelta(days=1)).isoformat(timespec="seconds"), "step_key": "x"},
        "old": {"finished_at": (now - timedelta(days=90)).isoformat(timespec="seconds"), "step_key": "x"},
    }
    _seed_history(isolated_registry, history)

    result = isolated_registry.rotate_pipeline_artifacts(retention_days=30)
    assert result["retention_days"] == 30
    assert result["removed_runs"] == 1

    remaining = isolated_registry._read_history_index()
    assert "recent" in remaining and "old" not in remaining


def test_rotate_pipeline_artifacts_uses_executed_at_when_no_finished_at(isolated_registry) -> None:
    now = datetime.now()
    history = {
        "active": {"executed_at": (now - timedelta(days=2)).isoformat(timespec="seconds"), "step_key": "y"},
        "very_old_active": {"executed_at": (now - timedelta(days=120)).isoformat(timespec="seconds"), "step_key": "y"},
    }
    _seed_history(isolated_registry, history)

    isolated_registry.rotate_pipeline_artifacts(retention_days=30)

    remaining = isolated_registry._read_history_index()
    assert "active" in remaining and "very_old_active" not in remaining


def test_rotate_pipeline_artifacts_removes_old_dirs(isolated_registry, tmp_path: Path) -> None:
    runs_dir = isolated_registry.RUNS_DIR
    step_dir = runs_dir / "step_x"
    step_dir.mkdir(parents=True, exist_ok=True)

    fresh = step_dir / "fresh_run"
    fresh.mkdir()
    (fresh / "stdout.log").write_text("ok", encoding="utf-8")

    stale = step_dir / "stale_run"
    stale.mkdir()
    (stale / "stdout.log").write_text("ok", encoding="utf-8")
    # Anti-date le dossier "stale" à 60 jours.
    old_time = (datetime.now() - timedelta(days=60)).timestamp()
    import os
    os.utime(stale, (old_time, old_time))

    result = isolated_registry.rotate_pipeline_artifacts(retention_days=30)
    assert result["removed_dirs"] >= 1
    assert fresh.exists()
    assert not stale.exists()


def test_rotate_pipeline_artifacts_respects_env_default(isolated_registry, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IHM_RUNS_RETENTION_DAYS", "7")
    importlib.reload(isolated_registry)  # relit l'env
    # On vérifie juste l'API : le retour expose le bon retention_days.
    result = isolated_registry.rotate_pipeline_artifacts()
    assert result["retention_days"] == 7

