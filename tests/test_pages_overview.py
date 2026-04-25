from ihm.pages import overview

def test_pages_overview_importable():
    assert hasattr(overview, "__doc__")


def test_build_pipeline_summary_rows_exposes_latest_workflow_and_upstream_runs() -> None:
    runs = [
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "step_key": "pipeline_workflow",
            "status": "completed",
            "run_summary": {"workflow_steps_with_summary": 2, "targeted_symbols": 6, "successful_symbols": 5},
        },
        {
            "run_id": "imp-1",
            "run_kind": "step",
            "step_key": "import_alpaca_bar",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "successful_symbols": 2},
        },
        {
            "run_id": "san-1",
            "run_kind": "step",
            "step_key": "data_sanitizer_daily",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "successful_symbols": 3},
        },
        {
            "run_id": "scr-1",
            "run_kind": "step",
            "step_key": "stock_screener",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "symbols_final": 2},
        },
    ]

    rows = overview._build_pipeline_summary_rows(runs)

    assert list(rows["scope"]) == ["Workflow complet", "Import Alpaca Bar", "Data Sanitizer Daily", "Stock Screener"]


def test_build_screener_objective_rows_exposes_operational_leaders() -> None:
    rows = overview._build_screener_objective_rows(
        {
            "objective_rows_df": overview.pd.DataFrame(
                [
                    {
                        "objective": "robust",
                        "objective_label": "robuste",
                        "scenario_name": "steady",
                        "objective_scope": "cross_regime",
                        "objective_score": 0.77,
                        "overall_score": 0.75,
                    }
                ]
            )
        }
    )

    assert list(rows.columns) == ["objectif", "label", "scénario", "périmètre", "score objectif", "score global"]
    assert rows.iloc[0]["scénario"] == "steady"


def test_build_screener_history_dataframe_exposes_shared_artifact_rows() -> None:
    history_df = overview._build_screener_history_dataframe(
        [
            {
                "artifacts_dir": "C:/tmp/screener_a",
                "artifacts_dir_label": "artifacts/screener_a",
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
            }
        ]
    )

    assert history_df.iloc[0]["Origines"] == "défaut, runs IHM"
    assert history_df.iloc[0]["Runs IHM"] == 3


