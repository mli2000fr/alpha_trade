"""Sprint S24.2 — Test page IHM Sandbox health."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


@pytest.mark.e2e
def test_sandbox_health_renders_without_rollup() -> None:
    def _runner() -> None:
        from ihm.pages import sandbox_health
        sandbox_health.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception : {at.exception}"


@pytest.mark.e2e
def test_sandbox_health_renders_with_rollup(tmp_path: Path, monkeypatch) -> None:
    rollup = {
        "generated_at": "2026-05-06T00:00:00+00:00",
        "window_days": 30,
        "n_days_observed": 5,
        "streak_green": 3,
        "streak_red": 0,
        "n_success": 3,
        "n_failure": 1,
        "n_cancelled": 0,
        "last_failure": "2026-05-03",
        "calendar": [
            {"date": "2026-05-06", "status": "success"},
            {"date": "2026-05-05", "status": "success"},
            {"date": "2026-05-04", "status": "success"},
            {"date": "2026-05-03", "status": "failure"},
            {"date": "2026-05-02", "status": "missing"},
        ],
    }
    (tmp_path / "_rollup.json").write_text(json.dumps(rollup), "utf-8")
    monkeypatch.setenv("ALPHA_TRADE_SANDBOX_DIR", str(tmp_path))

    def _runner() -> None:
        from ihm.services import sandbox_health_loader
        sandbox_health_loader.DEFAULT_SANDBOX_DIR = Path(  # type: ignore[attr-defined]
            __import__("os").environ["ALPHA_TRADE_SANDBOX_DIR"]
        )
        from ihm.pages import sandbox_health
        sandbox_health.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception
    assert len(at.metric) >= 4

