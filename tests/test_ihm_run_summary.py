from ihm.services.run_summary import aggregate_workflow_run_summary, build_latest_run_summary_rows, build_run_summary_caption


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


def test_build_run_summary_caption_uses_harmonized_labels_for_execution_and_corporate_actions() -> None:
    execution_caption = build_run_summary_caption(
        {
            "step_key": "execution",
            "run_summary": {
                "targeted_symbols": 5,
                "submitted_orders": 4,
                "filled_orders": 3,
                "skipped_orders": 1,
                "fill_rate": 0.75,
            },
        }
    )
    apply_caption = build_run_summary_caption(
        {
            "step_key": "corporate_actions_apply",
            "run_summary": {
                "pending_events": 6,
                "applied_events": 4,
                "skipped_events": 1,
            },
        }
    )

    assert "cibles=5" in execution_caption
    assert "soumis=4" in execution_caption
    assert "remplis=3" in execution_caption
    assert "ignorés=1" in execution_caption
    assert "taux d'exécution=0.75" in execution_caption
    assert "en attente=6" in apply_caption
    assert "appliqués=4" in apply_caption
    assert "ignorés=1" in apply_caption


def test_build_run_summary_caption_uses_enriched_risk_management_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "risk_management",
            "run_summary": {
                "targeted_symbols": 12,
                "accepted_symbols": 6,
                "reduced_symbols": 2,
                "rejected_symbols": 4,
                "gross_exposure_pct": 0.62,
                "max_target_weight": 0.10,
                "total_initial_risk_dollars": 3200.0,
                "atr_coverage_pct": 0.92,
                "prediction_coverage_pct": 0.75,
            },
        }
    )

    assert "cibles=12" in caption
    assert "acceptés=6" in caption
    assert "expo brute=0.62" in caption
    assert "couverture atr=0.92" in caption


def test_build_run_summary_caption_uses_enriched_execution_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "execution",
            "run_summary": {
                "targeted_symbols": 5,
                "submitted_orders": 4,
                "filled_orders": 3,
                "failed_orders": 1,
                "skipped_orders": 0,
                "fill_rate": 0.75,
                "total_target_notional": 24500.0,
                "total_initial_risk_dollars": 1800.0,
                "targets_with_broker_initial_stop": 4,
            },
        }
    )

    assert "notional cible=24500.0" in caption
    assert "risque init.=1800.0" in caption
    assert "stops broker=4" in caption


def test_build_run_summary_caption_uses_execution_protection_watch_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "execution_protection_watch",
            "run_summary": {
                "watched_items": 5,
                "triggered_items": 2,
                "transitioned_items": 2,
                "pending_items": 3,
                "terminal_items": 0,
                "skipped_existing_trailing": 0,
                "cancel_failed_items": 1,
                "trigger_check_count": 8,
            },
        }
    )

    assert "surveillés=5" in caption
    assert "transitions=2" in caption
    assert "annulations ko=1" in caption


def test_build_run_summary_caption_uses_execution_protection_watch_service_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "execution_protection_watch_service",
            "run_summary": {
                "iterations": 12,
                "cycles_with_work": 4,
                "idle_cycles": 8,
                "heartbeat_count": 3,
                "transitioned_items": 2,
                "consecutive_failures": 0,
                "max_consecutive_failures": 3,
            },
        }
    )

    assert "itérations=12" in caption
    assert "cycles actifs=4" in caption
    assert "heartbeats=3" in caption


def test_build_run_summary_caption_uses_screener_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "stock_screener",
            "run_summary": {
                "targeted_symbols": 1200,
                "symbols_final": 140,
                "symbols_pass_history": 800,
                "symbols_pass_liquidity": 300,
                "symbols_pass_relative_strength": 180,
                "chunk_failures": 0,
                "rows_avoided_estimate": 250000,
            },
        }
    )

    assert "cibles=1200" in caption
    assert "final=140" in caption
    assert "pass hist.=800" in caption
    assert "pass liq.=300" in caption
    assert "pass rs=180" in caption


def test_build_run_summary_caption_uses_alpha_scanner_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "alpha_scanner",
            "run_summary": {
                "requested_selection_size": 50,
                "selected_candidates": 18,
                "selected_sectors": 7,
                "selection_fill_ratio": 0.36,
                "workers": 4,
                "sector_cap_ratio": 0.3,
            },
        }
    )

    assert "demandé=50" in caption
    assert "retenus=18" in caption
    assert "secteurs=7" in caption
    assert "fill=0.36" in caption


def test_build_run_summary_caption_uses_sentiment_pipeline_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "sentiment_pipeline",
            "run_summary": {
                "resolved_symbols": 25,
                "fetched_articles": 120,
                "landed_articles": 90,
                "sentiment_inferred": 88,
                "macro_rows": 12,
                "ticker_day_rows": 40,
                "sector_day_rows": 9,
            },
        }
    )

    assert "symboles=25" in caption
    assert "fetch=120" in caption
    assert "landed=90" in caption
    assert "sentiments=88" in caption
    assert "macro=12" in caption


def test_build_run_summary_caption_uses_signal_aggregator_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "signal_aggregator",
            "run_summary": {
                "loaded_symbols": 18,
                "updated_symbols": 18,
                "signal_active_symbols": 7,
                "total_news": 42,
                "avg_final_score_sentiment": 0.6123,
                "max_final_score_sentiment": 0.88,
            },
        }
    )

    assert "chargés=18" in caption
    assert "maj=18" in caption
    assert "sent. actifs=7" in caption
    assert "news=42" in caption
    assert "score moy.=0.6123" in caption


def test_build_run_summary_caption_uses_earnings_resume_metrics_mapping() -> None:
    caption = build_run_summary_caption(
        {
            "step_key": "sync_earnings_calendar",
            "run_summary": {
                "symbols": 120,
                "symbols_skipped_resume": 45,
                "symbols_remaining": 7,
                "rows_upserted": 300,
                "batch_size": 50,
                "failed_symbols": 2,
            },
        }
    )

    assert "symboles=120" in caption
    assert "repris=45" in caption
    assert "à rejouer=7" in caption
    assert "rows upsert=300" in caption


def test_build_latest_run_summary_rows_preserves_scope_order_and_filters_missing_summaries() -> None:
    rows = build_latest_run_summary_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "status": "completed",
                "run_summary": {"workflow_steps_with_summary": 2, "targeted_symbols": 6},
            },
            {
                "run_id": "imp-1",
                "run_kind": "step",
                "step_key": "import_alpaca_bar",
                "status": "completed",
                "run_summary": {"targeted_symbols": 3, "successful_symbols": 2},
            },
            {
                "run_id": "san-empty",
                "run_kind": "step",
                "step_key": "data_sanitizer_daily",
                "status": "completed",
                "run_summary": {},
            },
        ],
        [
            {"label": "Workflow complet", "run_kind": "workflow"},
            {"label": "Import Alpaca Bar", "step_keys": ["import_alpaca_bar"]},
            {"label": "Data Sanitizer Daily", "step_keys": ["data_sanitizer_daily"]},
        ],
    )

    assert [row["scope"] for row in rows] == ["Workflow complet", "Import Alpaca Bar"]
    assert rows[0]["run_id"] == "wf-1"
    assert rows[1]["run_id"] == "imp-1"
    assert "cibles=3" in str(rows[1]["résumé métier"])


