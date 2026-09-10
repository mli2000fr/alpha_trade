from __future__ import annotations

from ihm.pages import backtesting as page


def test_extract_run_oracle_batch_has_priority_over_ml_batch() -> None:
    run = {
        "command": [
            "python", "-m", "backtesting", "run",
            "--ml-batch-id", "ml-h20",
            "--oracle-batch-id", "oracle-h5",
        ]
    }
    assert page._extract_run_oracle_batch_id(run) == "oracle-h5"


def test_extract_run_oracle_batch_falls_back_to_ml_batch() -> None:
    run = {"command_display": "python -m backtesting run --ml-batch-id bundle-h10"}
    assert page._extract_run_oracle_batch_id(run) == "bundle-h10"


def test_batch_oracle_horizon_prefers_artifact(monkeypatch) -> None:
    monkeypatch.setattr(page, "resolve_oracle_artifact_horizon", lambda batch_id: 5)
    assert page._batch_oracle_horizon("oracle-h5") == 5
