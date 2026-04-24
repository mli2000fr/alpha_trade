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
    ]

    rows = overview._build_pipeline_summary_rows(runs)

    assert list(rows["scope"]) == ["Workflow complet", "Import Alpaca Bar", "Data Sanitizer Daily"]


