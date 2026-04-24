from ihm.services.run_summary import aggregate_workflow_run_summary, build_run_summary_caption


def test_aggregate_workflow_run_summary_merges_numeric_and_nested_counters() -> None:
    aggregated = aggregate_workflow_run_summary(
        [
            {
                "run_id": "run-import",
                "step_key": "import_alpaca_bar",
                "step_label": "1. Import",
                "status": "completed",
                "run_summary": {
                    "targeted_symbols": 3,
                    "successful_symbols": 2,
                    "max_calendar_gap_days": 8,
                    "history_status_counts": {"ready": 2, "provider_error": 1},
                },
            },
            {
                "run_id": "run-sanitize",
                "step_key": "data_sanitizer_daily",
                "step_label": "2. Sanitize",
                "status": "completed",
                "run_summary": {
                    "targeted_symbols": 3,
                    "successful_symbols": 3,
                    "max_calendar_gap_days": 2,
                    "status_breakdown": {"success": 3, "failed": 0},
                },
            },
        ]
    )

    assert aggregated["workflow_steps_with_summary"] == 2
    assert aggregated["targeted_symbols"] == 6
    assert aggregated["successful_symbols"] == 5
    assert aggregated["max_calendar_gap_days"] == 8
    assert aggregated["history_status_counts"] == {"ready": 2, "provider_error": 1}
    assert aggregated["status_breakdown"] == {"success": 3, "failed": 0}
    assert len(aggregated["workflow_step_summaries"]) == 2


def test_build_run_summary_caption_uses_workflow_metrics() -> None:
    record = {
        "step_key": "pipeline_workflow",
        "run_summary": {
            "workflow_steps_with_summary": 2,
            "targeted_symbols": 6,
            "successful_symbols": 5,
            "failed_symbols": 1,
        },
    }

    caption = build_run_summary_caption(record)

    assert "étapes résumées=2" in caption
    assert "cibles=6" in caption
    assert "succès=5" in caption


def test_aggregate_workflow_run_summary_uses_weighted_average_and_latest_thresholds() -> None:
    aggregated = aggregate_workflow_run_summary(
        [
            {
                "run_id": "run-exec-1",
                "step_key": "execution",
                "step_label": "Execution 1",
                "status": "completed",
                "run_summary": {
                    "submitted_orders": 2,
                    "filled_orders": 1,
                    "fill_rate": 0.5,
                    "avg_slippage_bps": 10.0,
                    "max_slippage_bps_threshold": 30,
                    "account_ids": ["paper-a"],
                    "dry_run": False,
                },
            },
            {
                "run_id": "run-exec-2",
                "step_key": "execution",
                "step_label": "Execution 2",
                "status": "completed",
                "run_summary": {
                    "submitted_orders": 4,
                    "filled_orders": 4,
                    "fill_rate": 1.0,
                    "avg_slippage_bps": 20.0,
                    "max_slippage_bps_threshold": 25,
                    "account_ids": ["paper-b", "paper-a"],
                    "dry_run": True,
                },
            },
        ]
    )

    assert aggregated["fill_rate"] == 0.8333
    assert aggregated["avg_slippage_bps"] == 18.0
    assert aggregated["max_slippage_bps_threshold"] == 25
    assert aggregated["account_ids"] == ["paper-a", "paper-b"]
    assert aggregated["dry_run"] is True

