from ihm.pages import screening

def test_pages_screening_importable():
    assert hasattr(screening, "__doc__")


def test_build_quality_summary_rows_exposes_recent_pipeline_context() -> None:
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
    ]

    rows = screening._build_quality_summary_rows(runs)

    assert list(rows["scope"]) == ["Import Alpaca Bar", "Workflow complet"]


