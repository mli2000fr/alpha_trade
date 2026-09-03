from __future__ import annotations

import json
from pathlib import Path

from ihm.services.ml_artifacts import (
    build_batch_directional_candidate_selection,
    build_champion_walk_forward_stability,
    build_directional_bundle_serving_coverage,
    format_directional_candidate_selection,
    has_per_symbol_artifacts,
    list_directional_bundle_symbols,
    list_ml_artifact_batches,
    list_ml_artifact_symbols,
    load_batch_artifact_contract,
    load_ml_artifact_report,
    resolve_batch_artifacts_root,
)


def _write_directional_symbol_artifacts(
    batch_dir: Path,
    symbol: str,
    *,
    long_values: list[float],
    short_values: list[float],
    selected_model_eligible: bool | None = None,
) -> None:
    symbol_dir = batch_dir / symbol
    symbol_dir.mkdir(parents=True)
    config = {
        "selected_forecast_horizon": 20,
        "selection_mode": "auto_selected_champion",
        "artifact_routes": {"selected_model": "lightgbm", "models": {}},
    }
    if selected_model_eligible is not None:
        config["selected_model_eligible"] = selected_model_eligible
    (symbol_dir / "config.json").write_text(
        json.dumps(config),
        encoding="utf-8",
    )
    splits = [
        {
            "split_index": index,
            "test_rows": 100,
            "f1_long": f1_long,
            "f1_short": f1_short,
            "f1_flat": 0.20,
            "f1_macro": (f1_long + f1_short + 0.20) / 3,
            "true_long_pct": 30.0,
            "true_short_pct": 30.0,
        }
        for index, (f1_long, f1_short) in enumerate(zip(long_values, short_values, strict=True))
    ]
    (symbol_dir / "metrics.json").write_text(
        json.dumps(
            {
                "champion": {"model_name": "lightgbm"},
                "baseline_lightgbm": {
                    "horizons": {"h20": {"walk_forward": {"n_splits": len(splits), "splits": splits}}}
                },
            }
        ),
        encoding="utf-8",
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


def test_resolve_batch_artifacts_root_uses_configured_custom_directory(tmp_path: Path) -> None:
    custom_root = tmp_path / "models_screening"
    (custom_root / "batch-custom").mkdir(parents=True)
    metadata = {"cli_options": {"artifacts_dir": str(custom_root)}}

    resolved = resolve_batch_artifacts_root("batch-custom", metadata)

    assert resolved == custom_root.resolve()


def test_resolve_batch_artifacts_root_accepts_path_already_scoped_to_batch(tmp_path: Path) -> None:
    batch_dir = tmp_path / "models_screening" / "batch-custom"
    batch_dir.mkdir(parents=True)
    metadata = {"training_config": {"artifacts_dir": str(batch_dir)}}

    resolved = resolve_batch_artifacts_root("batch-custom", metadata)

    assert resolved == batch_dir.parent.resolve()


def test_batch_directional_candidate_selection_builds_three_exclusive_lists(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-1"
    _write_directional_symbol_artifacts(
        batch_dir, "BOTH", long_values=[0.50, 0.45, 0.40], short_values=[0.55, 0.45, 0.40]
    )
    _write_directional_symbol_artifacts(
        batch_dir, "LONG", long_values=[0.50, 0.45, 0.40], short_values=[0.10, 0.15, 0.20]
    )
    _write_directional_symbol_artifacts(
        batch_dir, "SHORT", long_values=[0.10, 0.15, 0.20], short_values=[0.50, 0.45, 0.40]
    )
    _write_directional_symbol_artifacts(
        batch_dir, "REJECT", long_values=[0.10, 0.15, 0.20], short_values=[0.10, 0.15, 0.20]
    )
    _write_directional_symbol_artifacts(
        batch_dir, "POTENTIAL",
        long_values=[0.73, 0.60, 0.50, 0.40, 0.00],
        short_values=[0.10, 0.15, 0.20, 0.10, 0.15],
    )
    internal = batch_dir / "__GLOBAL__"
    internal.mkdir()
    (internal / "config.json").write_text("{}", encoding="utf-8")

    assert has_per_symbol_artifacts("batch-1", tmp_path) is True
    result = build_batch_directional_candidate_selection("batch-1", tmp_path)

    assert result["scanned_symbols"] == 5
    assert result["eligible_symbols"] == 3
    assert result["long_only"] == ["LONG"]
    assert result["short_only"] == ["SHORT"]
    assert result["long_short"] == ["BOTH"]
    assert result["strict"]["eligible_symbols"] == 3
    assert result["discovery"]["eligible_symbols"] == 4
    assert result["discovery"]["long_only"] == ["LONG", "POTENTIAL"]
    audit = result["audit_df"].set_index("symbol")
    assert audit.loc["BOTH", "selected_model"] == "lightgbm"
    assert audit.loc["BOTH", "selected_horizon"] == 20
    assert audit.loc["BOTH", "classification"] == "LONG_SHORT"
    assert audit.loc["LONG", "classification"] == "LONG_ONLY"
    assert audit.loc["SHORT", "classification"] == "SHORT_ONLY"
    assert audit.loc["POTENTIAL", "classification"] == "REJECTED"
    assert audit.loc["POTENTIAL", "discovery_classification"] == "LONG_ONLY"
    assert audit.loc["POTENTIAL", "long_discovery_reason"] == "high_potential_fragile_fold"
    assert audit.loc["REJECT", "classification"] == "REJECTED"


def test_directional_bundle_uses_each_specialized_branch_for_its_owned_side(tmp_path: Path) -> None:
    batch_dir = tmp_path / "bundle-1"
    batch_dir.mkdir()
    (batch_dir / "cascade_manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "cascade_type": "oracle_extreme_plus_per_symbol_directional",
            "oracle": {"status": "completed", "profile": {"profile_id": "oracle", "feature_columns": ["o"]}},
            "per_symbol": {
                "long": {"profile": {"profile_id": "long", "feature_columns": ["l"]}},
                "short": {"profile": {"profile_id": "short", "feature_columns": ["s"]}},
            },
        }),
        encoding="utf-8",
    )
    # The LONG model is intentionally poor on f1_short; the SHORT model is
    # intentionally poor on f1_long.  Cross-side scores must not reject them.
    _write_directional_symbol_artifacts(
        batch_dir / "directions" / "long", "BOTH",
        long_values=[0.50, 0.45, 0.40], short_values=[0.05, 0.10, 0.15],
    )
    _write_directional_symbol_artifacts(
        batch_dir / "directions" / "short", "BOTH",
        long_values=[0.05, 0.10, 0.15], short_values=[0.55, 0.45, 0.40],
    )
    _write_directional_symbol_artifacts(
        batch_dir / "directions" / "long", "LONG_ONLY",
        long_values=[0.50, 0.45, 0.40], short_values=[0.05, 0.10, 0.15],
    )
    for direction in ("long", "short"):
        _write_directional_symbol_artifacts(
            batch_dir / "directions" / direction, "INELIGIBLE",
            long_values=[0.60, 0.55, 0.50], short_values=[0.60, 0.55, 0.50],
            selected_model_eligible=direction != "long",
        )

    contract = load_batch_artifact_contract("bundle-1", tmp_path)
    assert contract["is_directional_bundle"] is True
    assert has_per_symbol_artifacts("bundle-1", tmp_path) is True
    assert list_directional_bundle_symbols("bundle-1", tmp_path, "direction_long") == ["BOTH", "INELIGIBLE", "LONG_ONLY"]
    assert list_directional_bundle_symbols("bundle-1", tmp_path, "direction_short") == ["BOTH", "INELIGIBLE"]

    result = build_batch_directional_candidate_selection("bundle-1", tmp_path)
    coverage = build_directional_bundle_serving_coverage("bundle-1", tmp_path)

    assert result["batch_kind"] == "directional_bundle"
    assert result["long_short"] == ["BOTH"]
    assert result["long_only"] == []
    assert result["scanned_symbols"] == 3
    assert result["servable_symbols"] == 1
    assert result["unservable_symbols"] == ["INELIGIBLE", "LONG_ONLY"]
    assert coverage["trained_paired_symbols"] == ["BOTH", "INELIGIBLE"]
    assert coverage["servable_paired_symbols"] == ["BOTH"]
    assert coverage["unservable_symbols"] == ["INELIGIBLE"]
    audit = result["audit_df"].set_index("symbol")
    assert audit.loc["BOTH", "long_selected_model"] == "lightgbm"
    assert audit.loc["BOTH", "short_selected_model"] == "lightgbm"
    assert audit.loc["BOTH", "classification"] == "LONG_SHORT"
    assert audit.loc["INELIGIBLE", "classification"] == "REJECTED"
    assert bool(audit.loc["INELIGIBLE", "pair_servable"]) is False


def test_directional_candidate_file_contains_comma_separated_exclusive_lists() -> None:
    payload = format_directional_candidate_selection(
        {
            "batch_id": "batch-1",
            "generated_at": "2026-08-31T12:00:00+00:00",
            "long_only": ["MSFT", "AAPL"],
            "short_only": ["TSLA"],
            "long_short": ["NVDA", "AMD"],
            "discovery": {
                "long_only": ["SM", "CPRI"],
                "short_only": ["BEN"],
                "long_short": ["AAL"],
            },
        }
    )

    assert "[LONG_ONLY]\nAAPL,MSFT" in payload
    assert "[SHORT_ONLY]\nTSLA" in payload
    assert "[LONG_SHORT]\nAMD,NVDA" in payload
    assert "[DISCOVERY_LONG_ONLY]\nCPRI,SM" in payload
    assert "[DISCOVERY_SHORT_ONLY]\nBEN" in payload
    assert "[DISCOVERY_LONG_SHORT]\nAAL" in payload
    assert "f1_macro exclu" in payload
    assert "AAPL, MSFT" not in payload


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


def test_champion_walk_forward_stability_rejects_high_f1_with_low_side_support() -> None:
    metrics = {
        "walk_forward": {
            "n_splits": 3,
            "splits": [
                {
                    "split_index": index,
                    "test_rows": 20,
                    "f1_long": 0.90,
                    "f1_short": 0.90,
                    "true_long_pct": 20.0,
                    "true_short_pct": 20.0,
                }
                for index in range(3)
            ],
        }
    }

    result = build_champion_walk_forward_stability({}, metrics, "lstm_attention")

    assert list(result["folds_df"]["support_long"]) == [4, 4, 4]
    assert result["long"]["valid_folds"] == 0
    assert result["short"]["valid_folds"] == 0
    assert result["long"]["status"] == "insufficient_folds"
    assert result["short"]["status"] == "insufficient_folds"

