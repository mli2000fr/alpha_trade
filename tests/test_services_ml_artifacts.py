from __future__ import annotations

import json
from pathlib import Path

from ihm.services.ml_artifacts import (
    build_champion_walk_forward_stability,
    list_ml_artifact_batches,
    list_ml_artifact_symbols,
    load_ml_artifact_report,
)


def test_list_ml_artifact_batches_detects_campaign_directories(tmp_path: Path) -> None:
    for batch_id in ("campaign-old", "campaign-new"):
        symbol_dir = tmp_path / batch_id / "AAPL"
        symbol_dir.mkdir(parents=True)
        (symbol_dir / "config.json").write_text("{}", encoding="utf-8")
    legacy_symbol_dir = tmp_path / "MSFT"
    legacy_symbol_dir.mkdir()
    (legacy_symbol_dir / "config.json").write_text("{}", encoding="utf-8")

    assert list_ml_artifact_batches(tmp_path) == ["campaign-old", "campaign-new"]


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
    (symbol_dir / "best.ckpt").write_text("checkpoint", encoding="utf-8")
    (symbol_dir / "scaler.pkl").write_text("scaler", encoding="utf-8")
    (symbol_dir / "lightgbm_model.pkl").write_text("model", encoding="utf-8")
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
    assert report["health_status"] == "healthy"
    assert report["manifest_health"] == "healthy"
    assert report["config_health"] == "healthy"
    assert report["metrics_health"] == "healthy"
    assert report["degraded_reasons"] == []
    assert report["selected_route_health"] == "healthy"
    assert list(report["routes_df"]["model_name"]) == ["lstm_attention", "lightgbm"]
    assert report["routes_df"].loc[report["routes_df"]["model_name"] == "lightgbm", "inference_backend"].iloc[0] == "lightgbm_tabular"
    assert report["routes_df"].loc[report["routes_df"]["model_name"] == "lightgbm", "route_health"].iloc[0] == "healthy"
    assert list(report["ranking_df"]["model_name"]) == ["lightgbm", "lstm_attention"]


def test_load_ml_artifact_report_marks_selected_route_degraded_when_paths_missing(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir()
    config_path = symbol_dir / "config.json"
    metrics_path = symbol_dir / "metrics.json"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "run-999",
                "selection_mode": "auto_selected_champion",
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lightgbm": {
                            "inference_backend": "lightgbm_tabular",
                            "config_path": str(config_path),
                            "model_path": str(symbol_dir / "missing_model.pkl"),
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps({"champion": {"model_name": "lightgbm", "selection_mode": "auto_selected_champion"}}),
        encoding="utf-8",
    )

    report = load_ml_artifact_report("AAPL", tmp_path)

    assert report["health_status"] == "degraded"
    assert report["manifest_health"] == "healthy"
    assert report["config_health"] == "healthy"
    assert report["metrics_health"] == "healthy"
    assert report["selected_route_health"] == "missing_paths"
    assert "lightgbm:model_path_missing" in report["selected_route_errors"]
    assert "lightgbm:model_path_missing" in report["degraded_reasons"]
    assert report["routes_df"].loc[0, "route_health"] == "missing_paths"


def test_load_ml_artifact_report_handles_invalid_or_missing_files(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir()
    (symbol_dir / "config.json").write_text("{ invalid json", encoding="utf-8")

    report = load_ml_artifact_report("AAPL", tmp_path)

    assert report["selected_model"] is None
    assert report["health_status"] == "invalid"
    assert report["manifest_health"] == "invalid"
    assert report["config_health"] == "invalid"
    assert report["metrics_health"] == "invalid"
    assert report["routes_df"].empty
    assert report["ranking_df"].empty
    assert len(report["errors"]) == 2
    assert len(report["degraded_reasons"]) == 2
    assert any("JSON invalide" in err for err in report["errors"])
    assert any("Fichier absent" in err for err in report["errors"])


def test_champion_walk_forward_stability_uses_selected_model_and_horizon() -> None:
    def split(index: int, f1_long: float, f1_short: float) -> dict[str, object]:
        return {
            "split_index": index,
            "test_start_date": f"202{index}-01-01",
            "test_end_date": f"202{index}-06-30",
            "test_rows": 100,
            "f1_macro": 0.40,
            "f1_long": f1_long,
            "f1_short": f1_short,
            "f1_flat": 0.20,
            "true_long_pct": 40.0,
            "true_short_pct": 35.0,
        }

    metrics = {
        # Ce bloc ne doit pas être utilisé car le champion est LightGBM.
        "walk_forward": {"n_splits": 1, "splits": [split(9, 0.01, 0.01)]},
        "baseline_lightgbm": {
            "horizons": {
                "h10": {"walk_forward": {"n_splits": 1, "splits": [split(8, 0.10, 0.10)]}},
                "h20": {
                    "walk_forward": {
                        "status": "completed",
                        "n_splits": 3,
                        "splits": [
                            split(0, 0.50, 0.50),
                            split(1, 0.45, 0.10),
                            split(2, 0.40, 0.45),
                        ],
                    }
                },
            }
        },
    }

    result = build_champion_walk_forward_stability(
        {"selected_forecast_horizon": 20}, metrics, "lightgbm"
    )

    assert result["available"] is True
    assert result["selected_horizon"] == 20
    assert result["source"] == "baseline_lightgbm.horizons.h20.walk_forward"
    assert result["evaluated_folds"] == 3
    assert result["long"]["status"] == "stable"
    assert result["short"]["status"] == "fragile"
    assert result["overall_status"] == "long_only_stable"
    assert list(result["folds_df"]["fold"]) == [0, 1, 2]
    assert list(result["folds_df"]["support_long"]) == [40, 40, 40]


def test_champion_walk_forward_stability_reports_insufficient_folds() -> None:
    metrics = {
        "walk_forward": {
            "n_splits": 2,
            "splits": [
                {"split_index": 0, "test_rows": 100, "f1_long": 0.70, "f1_short": 0.60,
                 "true_long_pct": 40.0, "true_short_pct": 35.0},
                {"split_index": 1, "test_rows": 100, "f1_long": 0.72, "f1_short": 0.62,
                 "true_long_pct": 42.0, "true_short_pct": 33.0},
            ],
        }
    }

    result = build_champion_walk_forward_stability({}, metrics, "lstm_attention")

    assert result["long"]["status"] == "insufficient_folds"
    assert result["short"]["status"] == "insufficient_folds"
    assert result["overall_status"] == "not_stable"

