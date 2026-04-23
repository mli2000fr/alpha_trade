from __future__ import annotations

import json
from pathlib import Path

from ihm.services.ml_artifacts import list_ml_artifact_symbols, load_ml_artifact_report


def test_list_ml_artifact_symbols_returns_sorted_symbol_directories(tmp_path: Path) -> None:
    (tmp_path / "MSFT").mkdir()
    (tmp_path / "MSFT" / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "AAPL").mkdir()
    (tmp_path / "AAPL" / "metrics.json").write_text("{}", encoding="utf-8")
    (tmp_path / "__GLOBAL__").mkdir()
    (tmp_path / "__GLOBAL__" / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.txt").write_text("ignored", encoding="utf-8")

    symbols = list_ml_artifact_symbols(tmp_path)

    assert symbols == ["AAPL", "MSFT", "__GLOBAL__"]


def test_load_ml_artifact_report_extracts_champion_routes_and_ranking(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir()
    (symbol_dir / "config.json").write_text(
        json.dumps(
            {
                "run_id": "run-123",
                "selection_mode": "auto_selected_champion",
                "selected_decision_threshold": 0.61,
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lstm_attention": {
                            "inference_backend": "lstm_attention",
                            "checkpoint_path": "best.ckpt",
                            "scaler_path": "scaler.pkl",
                            "config_path": str(symbol_dir / "config.json"),
                        },
                        "lightgbm": {
                            "status": "completed",
                            "inference_backend": "lightgbm_tabular",
                            "model_path": str(symbol_dir / "lightgbm_model.pkl"),
                            "config_path": str(symbol_dir / "config.json"),
                            "feature_columns": ["feat1", "feat2"],
                            "selected_decision_threshold": 0.61,
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (symbol_dir / "metrics.json").write_text(
        json.dumps(
            {
                "champion": {
                    "model_name": "lightgbm",
                    "selection_mode": "auto_selected_champion",
                    "selection_metric": "selection_score",
                    "selection_score": 0.91,
                },
                "challengers": {
                    "ranking": [
                        {
                            "rank": 1,
                            "model_name": "lightgbm",
                            "selection_score": 0.91,
                            "status": "selected_auto_champion",
                            "selection_eligible": True,
                        },
                        {
                            "rank": 2,
                            "model_name": "lstm_attention",
                            "selection_score": 0.64,
                            "status": "completed",
                            "selection_eligible": True,
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    report = load_ml_artifact_report("AAPL", tmp_path)

    assert report["errors"] == []
    assert report["selected_model"] == "lightgbm"
    assert report["selection_mode"] == "auto_selected_champion"
    assert report["run_id"] == "run-123"
    assert report["selected_decision_threshold"] == 0.61
    assert list(report["routes_df"]["model_name"]) == ["lstm_attention", "lightgbm"]
    assert report["routes_df"].loc[report["routes_df"]["model_name"] == "lightgbm", "inference_backend"].iloc[0] == "lightgbm_tabular"
    assert list(report["ranking_df"]["model_name"]) == ["lightgbm", "lstm_attention"]


def test_load_ml_artifact_report_handles_invalid_or_missing_files(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir()
    (symbol_dir / "config.json").write_text("{ invalid json", encoding="utf-8")

    report = load_ml_artifact_report("AAPL", tmp_path)

    assert report["selected_model"] is None
    assert report["routes_df"].empty
    assert report["ranking_df"].empty
    assert len(report["errors"]) == 2
    assert any("JSON invalide" in err for err in report["errors"])
    assert any("Fichier absent" in err for err in report["errors"])

