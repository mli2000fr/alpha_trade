"""Sprint S25.1 — Tests pré-audit interne."""
from __future__ import annotations

from pathlib import Path

from scripts.run_pre_audit_checklist import _score, run_checks, write_reports


def test_run_checks_returns_results() -> None:
    results = run_checks()
    assert results, "La checklist programmable ne doit pas être vide"
    statuses = {r.status for r in results}
    assert statuses.issubset({"ok", "warn", "fail", "skip"})


def test_score_above_floor() -> None:
    results = run_checks()
    score = _score(results)
    # Plancher attendu : la majorité des items existent déjà.
    assert score["score"] >= 30.0, (
        f"Score programmable trop bas : {score} — items manquants : "
        f"{[r.item for r in results if r.status == 'fail']}"
    )


def test_write_reports_produces_files(tmp_path: Path) -> None:
    results = run_checks()
    json_path, md_path = write_reports(results, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    md = md_path.read_text("utf-8")
    assert "Pré-audit interne" in md
    assert "| Section |" in md

