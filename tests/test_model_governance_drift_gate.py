from __future__ import annotations

import json
from pathlib import Path

from ihm.pages import ml
from ihm.services.ml_artifacts import load_ml_artifact_report


def test_load_ml_artifact_report_exposes_governance_thresholds_and_ablation(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "AAPL"
    symbol_dir.mkdir()
    model_path = symbol_dir / "lightgbm_model.pkl"
    model_path.write_text("model", encoding="utf-8")

    config_path = symbol_dir / "config.json"
    metrics_path = symbol_dir / "metrics.json"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "run-ml-1",
                "selection_mode": "fallback_default_champion",
                "selection_reason": "quarantine_min_days",
                "selected_model_eligible": False,
                "selected_decision_threshold": 0.55,
                "threshold_optimization": {
                    "enabled": True,
                    "min_action_rate": 0.05,
                    "max_action_rate": 0.25,
                    "min_precision_long": 0.60,
                },
                "artifact_routes": {
                    "selected_model": "lightgbm",
                    "models": {
                        "lightgbm": {
                            "inference_backend": "lightgbm_tabular",
                            "config_path": str(config_path),
                            "model_path": str(model_path),
                            "selected_decision_threshold": 0.55,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "champion": {
                    "model_name": "lightgbm",
                    "selection_mode": "fallback_default_champion",
                },
                "challengers": {"ranking": []},
                "threshold_optimization": {
                    "enabled": True,
                    "selection_status": "fallback_default_threshold",
                    "selected_threshold": 0.55,
                    "selected_business_score": 1.23,
                    "constraints": {
                        "min_action_rate": 0.05,
                        "max_action_rate": 0.25,
                        "min_precision_long": 0.60,
                    },
                    "selected_metrics": {
                        "coverage_at_threshold": 0.08,
                        "precision_long": 0.64,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (symbol_dir / "attribution_summary.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "scenario": "quant_only",
                        "ic_mean": 0.12,
                        "hit_rate": 0.55,
                        "portfolio_return": 0.01,
                        "portfolio_sharpe": 1.1,
                        "alpha_vs_benchmark": 0.002,
                        "n_dates": 12,
                        "n_obs": 120,
                    }
                ],
                "regime_results": {
                    "bull": [
                        {
                            "scenario": "sentiment_only",
                            "ic_mean": 0.21,
                            "hit_rate": 0.61,
                            "portfolio_return": 0.015,
                            "portfolio_sharpe": 1.4,
                            "alpha_vs_benchmark": 0.004,
                            "n_dates": 6,
                            "n_obs": 60,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    report = load_ml_artifact_report("AAPL", tmp_path)

    governance_thresholds = report["governance_thresholds"]
    assert governance_thresholds["enabled"] is True
    assert governance_thresholds["selection_status"] == "fallback_default_threshold"
    assert governance_thresholds["selected_threshold"] == 0.55
    assert governance_thresholds["selected_action_rate"] == 0.08
    assert governance_thresholds["selected_precision_long"] == 0.64
    assert governance_thresholds["selected_model_eligible"] is False
    assert not report["attribution_results_df"].empty
    assert not report["attribution_regimes_df"].empty

    summary = ml._summarize_governance_thresholds(report)
    assert summary["selection_mode"] == "fallback_default_champion"
    assert summary["selection_reason"] == "quarantine_min_days"
    assert summary["selected_model_eligible"] is False

