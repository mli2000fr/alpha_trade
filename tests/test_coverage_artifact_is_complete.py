from __future__ import annotations

from pathlib import Path

from ihm.services.ops_supervision import build_coverage_artifact_health, load_coverage_artifact_health


def test_build_coverage_artifact_health_detects_complete_payload() -> None:
    summary = build_coverage_artifact_health(
        {
            "meta": {"branch_coverage": True},
            "totals": {
                "covered_lines": 120,
                "num_statements": 150,
                "percent_covered": 80.0,
                "num_branches": 20,
                "covered_branches": 18,
            },
            "files": {
                "pkg/a.py": {"executed_lines": [1, 2, 3]},
                "pkg/b.py": {"executed_lines": [4, 5]},
            },
        }
    )

    assert summary["status"] == "complete"
    assert summary["files_count"] == 2
    assert summary["executed_files"] == 2
    assert summary["branch_coverage"] is True


def test_build_coverage_artifact_health_flags_missing_branch_coverage() -> None:
    summary = build_coverage_artifact_health(
        {
            "meta": {},
            "totals": {
                "covered_lines": 10,
                "num_statements": 20,
                "percent_covered": 50.0,
            },
            "files": {
                "pkg/a.py": {"executed_lines": [1]},
            },
        }
    )

    assert summary["status"] == "incomplete"
    assert "branch coverage" in str(summary["message"]).lower()


def test_load_coverage_artifact_health_handles_missing_file(tmp_path: Path) -> None:
    summary = load_coverage_artifact_health(tmp_path / "coverage-missing.json")

    assert summary["status"] == "missing"
    assert str(summary["path"]).endswith("coverage-missing.json")


