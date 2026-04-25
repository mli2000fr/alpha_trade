from __future__ import annotations

from pathlib import Path


def test_build_global_screener_artifact_history_merges_default_run_history_and_manual_dirs(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import screener_artifact_history

    default_dir = tmp_path / "default"
    run_dir = tmp_path / "runs_out"
    manual_dir = tmp_path / "manual"

    monkeypatch.setattr(screener_artifact_history, "DEFAULT_SCREENER_ARTIFACTS_DIR", default_dir)
    monkeypatch.setattr(
        screener_artifact_history,
        "load_backtesting_history",
        lambda: [
            {
                "run_id": "run-2",
                "run_kind": "recommend-screener",
                "run_label": "Reco 2",
                "status": "completed",
                "executed_at": "2026-04-25T10:00:00",
                "finished_at": "2026-04-25T10:02:00",
                "screener_artifacts_dir": str(run_dir),
            },
            {
                "run_id": "run-1",
                "run_kind": "diagnose-screener",
                "run_label": "Diag 1",
                "status": "completed",
                "executed_at": "2026-04-24T10:00:00",
                "finished_at": "2026-04-24T10:05:00",
                "screener_artifacts_dir": str(run_dir),
            },
            {
                "run_id": "bt-1",
                "run_kind": "run",
                "run_label": "Backtest",
                "status": "completed",
                "executed_at": "2026-04-24T09:00:00",
                "finished_at": "2026-04-24T09:05:00",
                "screener_artifacts_dir": str(tmp_path / 'ignored'),
            },
        ],
    )

    def fake_summary(artifacts_dir: str) -> dict[str, object]:
        path = Path(artifacts_dir)
        return {
            "artifacts_dir": str(path),
            "available": True,
            "coverage_label": "2026-04-01 → 2026-04-03 (3 séance(s))",
            "updated_at_label": "2026-04-25 10:02",
            "updated_at_iso": f"2026-04-25T10:0{2 if path == run_dir else 1}:00",
            "baseline_name": "baseline",
            "objective_count": 4 if path == run_dir else 0,
            "scenario_count": 12,
            "file_count": 7,
            "market_regimes": ["bull", "bear"],
            "diagnostic_available": True,
            "recommendation_available": path == run_dir,
            "regime_analysis_available": True,
        }

    monkeypatch.setattr(screener_artifact_history, "build_screener_artifact_summary", fake_summary)

    entries = screener_artifact_history.build_global_screener_artifact_history([manual_dir])

    assert entries[0]["artifacts_dir"] == str(run_dir)
    assert {entry["artifacts_dir"] for entry in entries} == {str(run_dir), str(manual_dir), str(default_dir)}

    run_entry = entries[0]
    assert run_entry["run_count"] == 2
    assert run_entry["last_run_id"] == "run-2"
    assert run_entry["objective_count"] == 4
    assert run_entry["source_tags"] == ["runs IHM"]

    manual_entry = next(entry for entry in entries if entry["artifacts_dir"] == str(manual_dir))
    assert manual_entry["run_count"] == 0
    assert manual_entry["source_tags"] == ["sélection manuelle"]

    default_entry = next(entry for entry in entries if entry["artifacts_dir"] == str(default_dir))
    assert default_entry["source_tags"] == ["défaut"]


def test_format_screener_artifact_history_label_and_rows_are_ui_ready() -> None:
    from ihm.services.screener_artifact_history import (
        build_screener_artifact_history_rows,
        format_screener_artifact_history_label,
    )

    entry = {
        "artifacts_dir": "C:/tmp/screener",
        "artifacts_dir_label": "artifacts/screener_A",
        "available": True,
        "coverage_label": "2026-04-01 → 2026-04-03 (3 séance(s))",
        "updated_at_label": "2026-04-25 10:02",
        "baseline_name": "baseline",
        "objective_count": 4,
        "scenario_count": 12,
        "file_count": 7,
        "market_regime_count": 2,
        "run_count": 3,
        "last_run_label": "Recommandation screener",
        "last_run_status": "completed",
        "source_tags": ["défaut", "runs IHM"],
        "recommendation_available": True,
    }

    label = format_screener_artifact_history_label(entry)
    rows = build_screener_artifact_history_rows([entry])

    assert "artifacts/screener_A" in label
    assert "obj=4" in label
    assert "runs=3" in label
    assert rows[0]["Répertoire"] == "artifacts/screener_A"
    assert rows[0]["Disponible"] == "oui"
    assert rows[0]["Origines"] == "défaut, runs IHM"


