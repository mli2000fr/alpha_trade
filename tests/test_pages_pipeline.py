from ihm.pages import pipeline


def test_pages_pipeline_importable():
    assert hasattr(pipeline, "__doc__")


def test_pipeline_page_no_longer_exposes_legacy_strict_preset_preferences() -> None:
    assert not hasattr(pipeline, "_sync_alpha_scanner_strict_preset_preference")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_WIDGET_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_PREFS_KEY")


def test_build_history_rows_uses_public_run_summary_caption_helper() -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
                "workflow_completed_steps": 2,
                "workflow_total_steps": 3,
                "duration_seconds": 12,
                "stdout_lines": 4,
                "stderr_lines": 0,
                "run_summary": {
                    "workflow_steps_with_summary": 2,
                    "targeted_symbols": 6,
                    "successful_symbols": 5,
                },
            }
        ]
    )

    row = history_df.iloc[0].to_dict()
    assert row["type"] == "workflow"
    assert row["progression"] == "2/3"
    assert "étapes résumées=2" in str(row["résumé métier"])


def test_alpha_scanner_dependency_block_reason_requires_both_dependencies_red() -> None:
    diagnostic = {
        "all_red": True,
        "dependencies": {
            "sync_latest_quotes": {"status": "red"},
            "sync_earnings_calendar": {"status": "red"},
        },
    }

    reason = pipeline._alpha_scanner_dependency_block_reason(diagnostic)

    assert reason is not None
    assert "Alpha Scanner" in reason


def test_alpha_scanner_dependency_block_reason_is_none_when_not_all_red() -> None:
    diagnostic = {
        "all_red": False,
        "dependencies": {
            "sync_latest_quotes": {"status": "green"},
            "sync_earnings_calendar": {"status": "red"},
        },
    }

    assert pipeline._alpha_scanner_dependency_block_reason(diagnostic) is None


