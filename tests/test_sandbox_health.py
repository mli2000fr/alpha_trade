"""Sprint S24.2 — Tests collecte + rollup sandbox health."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sandbox_health_collect import collect_health
from scripts.sandbox_health_rollup import compute_rollup


def test_collect_health_basic() -> None:
    payload = collect_health(
        run_id="42", status="success", sha="abc123",
        audit_chain_ok=True,
        stage_durations={"screener": 12.3},
    )
    assert payload["run_id"] == "42"
    assert payload["status"] == "success"
    assert payload["audit_chain_ok"] is True
    assert payload["stage_durations"]["screener"] == 12.3
    assert payload["sha"] == "abc123"
    assert payload["date"]


def test_collect_health_with_reconciliation(tmp_path: Path) -> None:
    recon = tmp_path / "recon.json"
    recon.write_text(json.dumps({"n_diffs": 0, "ok": True}), "utf-8")
    p = collect_health(
        run_id="1", status="success", reconciliation_path=recon,
    )
    assert p["reconciliation"] == {"n_diffs": 0, "ok": True}


def _write_health(root: Path, d: date, status: str) -> None:
    folder = root / d.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "health.json").write_text(
        json.dumps({"date": d.isoformat(), "status": status}), "utf-8",
    )


def test_compute_rollup_streak(tmp_path: Path) -> None:
    today = date(2026, 5, 6)
    # 5 jours verts d'affilée puis 1 rouge
    _write_health(tmp_path, today, "success")
    _write_health(tmp_path, date(2026, 5, 5), "success")
    _write_health(tmp_path, date(2026, 5, 4), "success")
    _write_health(tmp_path, date(2026, 5, 3), "failure")

    rollup = compute_rollup(tmp_path, window=10, today=today)
    assert rollup["window_days"] == 10
    assert rollup["streak_green"] == 3
    assert rollup["n_success"] == 3
    assert rollup["n_failure"] == 1
    assert rollup["last_failure"] == "2026-05-03"
    assert len(rollup["calendar"]) == 10
    # Premier élément = aujourd'hui
    assert rollup["calendar"][0]["date"] == "2026-05-06"
    # Jours sans health.json marqués "missing"
    assert any(c["status"] == "missing" for c in rollup["calendar"])


def test_compute_rollup_empty(tmp_path: Path) -> None:
    rollup = compute_rollup(tmp_path, window=5, today=date(2026, 5, 6))
    assert rollup["streak_green"] == 0
    assert rollup["n_success"] == 0
    assert rollup["n_failure"] == 0
    assert all(c["status"] == "missing" for c in rollup["calendar"])

