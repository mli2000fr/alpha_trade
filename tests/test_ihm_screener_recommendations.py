from __future__ import annotations
import json
import pandas as pd
from ihm.services.screener_recommendations import load_screener_recommendation_report
def test_load_screener_recommendation_report_reads_phase7_artifacts(tmp_path) -> None:
    (tmp_path / "metadata.json").write_text(
        json.dumps(
            {
                "baseline_name": "baseline",
                "trading_dates": ["2026-04-01", "2026-04-02", "2026-04-03"],
                "market_regimes": ["bull", "bear"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "recommendation_summary_by_objective.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "available_objectives": ["robust", "offensive", "bear_defensive", "executable_compromise"],
                "cross_regime_analysis_available": True,
                "bear_market_data_available": True,
                "objectives": {
                    "robust": {
                        "label": "robuste",
                        "scope": "cross_regime",
                        "description": "Privilégie la stabilité.",
                        "recommended_scenario": {
                            "scenario_name": "robusto",
                            "rank": 1,
                            "objective_score": 0.81,
                            "overall_score": 0.74,
                            "reason": "Bon pire cas cross-régimes.",
                        },
                    },
                    "offensive": {
                        "label": "offensif",
                        "scope": "global",
                        "recommended_scenario": {
                            "scenario_name": "rocket",
                            "rank": 1,
                            "objective_score": 0.88,
                            "overall_score": 0.69,
                            "reason": "Upside forward dominant.",
                        },
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "objective": "robust",
                "objective_label": "robuste",
                "objective_scope": "cross_regime",
                "rank": 1,
                "scenario_name": "robusto",
                "objective_score": 0.81,
                "overall_score": 0.74,
                "objective_reason": "Bon pire cas cross-régimes.",
            },
            {
                "objective": "offensive",
                "objective_label": "offensif",
                "objective_scope": "global",
                "rank": 1,
                "scenario_name": "rocket",
                "objective_score": 0.88,
                "overall_score": 0.69,
                "objective_reason": "Upside forward dominant.",
            },
        ]
    ).to_csv(tmp_path / "scenario_recommendations_by_objective.csv", index=False)
    report = load_screener_recommendation_report(tmp_path)
    assert report["available"] is True
    assert report["coverage_label"] == "2026-04-01 → 2026-04-03 (3 séance(s))"
    assert list(report["objective_rows_df"]["objective"]) == ["robust", "offensive"]
    assert report["objective_rows_df"].iloc[0]["scenario_name"] == "robusto"
    assert report["leaderboard_df"].iloc[1]["scenario_name"] == "rocket"
def test_load_screener_recommendation_report_falls_back_to_csv_when_summary_missing(tmp_path) -> None:
    pd.DataFrame(
        [
            {
                "objective": "executable_compromise",
                "objective_label": "meilleur compromis exécutable",
                "objective_scope": "global",
                "rank": 1,
                "scenario_name": "deployable",
                "objective_score": 0.79,
                "overall_score": 0.72,
                "objective_reason": "Conversion portefeuille robuste.",
            },
            {
                "objective": "robust",
                "objective_label": "robuste",
                "objective_scope": "cross_regime",
                "rank": 1,
                "scenario_name": "steady",
                "objective_score": 0.77,
                "overall_score": 0.75,
                "objective_reason": "Stable sur tous les régimes.",
            },
        ]
    ).to_csv(tmp_path / "scenario_recommendations_by_objective.csv", index=False)
    report = load_screener_recommendation_report(tmp_path)
    assert report["available"] is True
    assert set(report["objective_rows_df"]["scenario_name"]) == {"deployable", "steady"}
    assert any("recommendation_summary_by_objective.json" in error for error in report["errors"])
