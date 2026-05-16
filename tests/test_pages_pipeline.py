from datetime import datetime, time as dt_time, timedelta
from typing import cast

from ihm.pages import _workflow as workflow_page, pipeline


class _DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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


def test_resolve_history_selected_run_id_returns_run_id_from_dataframe_selection(monkeypatch) -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
            },
            {
                "run_id": "step-2",
                "run_kind": "step",
                "step_key": "risk_management",
                "step_label": "11. Risk",
                "status": "failed",
            },
        ]
    )
    monkeypatch.setattr(
        workflow_page.st,
        "session_state",
        {
            workflow_page.WORKFLOW_HISTORY_TABLE_KEY: {
                "selection": {"rows": [1]},
            }
        },
        raising=False,
    )

    assert workflow_page._resolve_history_selected_run_id(history_df) == "step-2"


def test_resolve_history_selected_run_id_returns_none_without_valid_selection(monkeypatch) -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
            }
        ]
    )
    monkeypatch.setattr(
        workflow_page.st,
        "session_state",
        {workflow_page.WORKFLOW_HISTORY_TABLE_KEY: {"selection": {"rows": [5]}}},
        raising=False,
    )

    assert workflow_page._resolve_history_selected_run_id(history_df) is None


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


def test_pipeline_page_exposes_clear_screener_vs_alpha_scanner_labels() -> None:
    assert "diagnostic dépendances alpha scanner" in pipeline.ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE.lower()
    assert "sélection finale stricte" in pipeline.ALPHA_SCANNER_PARAMS_TITLE.lower()
    assert "préfiltrage large" in pipeline.SCREENER_PARAMS_CAPTION.lower()


def test_build_execution_mode_banner_payload_marks_simulation_as_no_broker_orders() -> None:
    severity, message = pipeline._build_execution_mode_banner_payload(pipeline.PipelineLaunchOptions(execution_mode="simulate"))

    assert severity == "warning"
    assert "simulation" in message.lower()
    assert "aucun ordre" in message.lower()


def test_build_execution_mode_banner_payload_escalates_mode_mismatch() -> None:
    severity, message = pipeline._build_execution_mode_banner_payload(
        pipeline.PipelineLaunchOptions(account_id="acct-live", execution_mode="paper"),
        detected_broker_mode="live",
    )

    assert severity == "error"
    assert "incohérence" in message.lower()
    assert "acct-live" in message


def test_build_execution_account_banner_payload_marks_cash_off_as_green_swing_cash() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="cash", execution_pdt_rule="off")
    )

    assert severity == "success"
    assert "type de compte=cash" in message.lower()
    assert "règle pdt=off" in message.lower()
    assert "swing cash" in message.lower()


def test_build_execution_account_banner_payload_marks_margin_auto_as_yellow() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="margin", execution_pdt_rule="auto")
    )

    assert severity == "warning"
    assert "margin / pdt" in message.lower()
    assert "type de compte=margin" in message.lower()
    assert "règle pdt=auto" in message.lower()


def test_build_execution_account_banner_payload_marks_detected_mismatch_as_red() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="cash", execution_pdt_rule="off"),
        detected_account_type="margin",
        detected_pdt_rule="auto",
    )

    assert severity == "error"
    assert "type broker détecté : `margin`" in message.lower()
    assert "pdt détecté : `auto`" in message.lower()
    assert "incohérence critique" in message.lower()


def test_build_capital_preset_banner_payload_marks_detected_bucket_as_applied() -> None:
    payload = pipeline._build_capital_preset_banner_payload(
        "capital_0_5000",
        detected_preset_key="capital_0_5000",
        detected_equity=2_000.0,
    )

    assert payload is not None
    severity, message = payload
    assert severity == "success"
    assert "panier capital appliqué" in message.lower()
    assert "2 001 → 5 000 $" in message


def test_build_capital_preset_banner_payload_marks_custom_with_recommended_bucket() -> None:
    payload = pipeline._build_capital_preset_banner_payload(
        "custom",
        detected_preset_key="capital_50001_100000",
        detected_equity=52_000.0,
    )

    assert payload is not None
    severity, message = payload
    assert severity == "info"
    assert "personnalisé" in message.lower()
    assert "50 001 → 100 000 $" in message


def test_build_execution_protection_banner_payload_exposes_tp_and_auto_initial_stop() -> None:
    severity, message = pipeline._build_execution_protection_banner_payload(
        pipeline.PipelineLaunchOptions(
            execution_take_profit_pct=0.065,
            execution_trailing_stop_pct=0.04,
            execution_submission_window="pre_open",
            execution_trailing_trigger="multiple_r",
            execution_trailing_r_multiple=1.5,
        )
    )

    assert severity == "info"
    assert "+6.5 %" in message
    assert "1.50r" in message.lower()
    assert "-4.0 %" in message
    assert "pre_open" in message
    assert "stop initial" in message.lower()
    assert "calculé automatiquement" in message.lower()


def test_build_pipeline_scope_alert_lines_distinguishes_global_and_account_specific_steps() -> None:
    global_line, account_line = pipeline._build_pipeline_scope_alert_lines()

    assert "3→10" in global_line
    assert "globales" in global_line.lower()
    assert "partagées entre comptes" in global_line.lower()
    assert "11→12" in account_line
    assert "spécifiques au compte sélectionné" in account_line.lower()


def test_build_watcher_doc_reference_exposes_explicit_workspace_link() -> None:
    assert hasattr(pipeline, "render_watcher_documentation_panel")


def test_build_watcher_handoff_rows_exposes_post_execution_launch_guidance() -> None:
    rows = pipeline._build_watcher_handoff_rows("acct-1")

    assert len(rows) >= 4
    assert rows[0]["Mode"] == "Run once (CLI local)"
    assert "juste après l'étape 12" in rows[0]["Quand l'utiliser"].lower()
    assert "run_execution_protection_watch.py" in rows[0]["Comment lancer"]
    assert any(row["Mode"] == "Task Scheduler" for row in rows)


def test_render_ml_inspection_link_uses_pending_symbol_for_cross_page_navigation(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline, "list_ml_artifact_symbols", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda *args, **kwargs: "MSFT")
    monkeypatch.setattr(pipeline.st, "button", lambda *args, **kwargs: True)
    monkeypatch.setattr(pipeline.st, "rerun", lambda: None)

    pipeline._render_ml_inspection_link("ml_train")

    assert session_state[pipeline.ML_PENDING_SELECTED_SYMBOL_KEY] == "MSFT"
    assert session_state[pipeline.NAVIGATION_TARGET_PAGE_KEY] == "ml"
    assert "ihm_ml_selected_symbol" not in session_state


def test_build_workflow_scope_help_lines_explains_1_to_12_3_to_12_and_13_14() -> None:
    lines = workflow_page._build_workflow_scope_help_lines()

    assert len(lines) == 3
    assert "1 → 12" in lines[0]
    assert "3 → 12" in lines[1]
    assert "changement de compte alpaca" in lines[1].lower()
    assert "13" in lines[2]
    assert "14" in lines[2]
    assert "non incluses par défaut" in lines[2].lower()


def test_build_run_provider_badge_prefers_run_summary_provider() -> None:
    badge = workflow_page._build_run_provider_badge(
        {
            "run_summary": {"provider": "eodhd"},
            "command": ["python", "-m", "dataIntegrityEngine.import_alpaca_bar"],
        }
    )

    assert badge == "provider=eodhd"


def test_build_run_symbol_progress_caption_formats_current_symbol_and_total() -> None:
    caption = workflow_page._build_run_symbol_progress_caption(
        {
            "run_summary": {
                "current_symbol_index": 125,
                "current_symbol_total": 500,
                "current_symbol": "NVDA",
            }
        }
    )

    assert caption is not None
    assert "125/500" in caption
    assert "NVDA" in caption


def test_build_run_symbol_progress_payload_returns_fraction_and_caption() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "run_summary": {
                "current_symbol_index": 25,
                "current_symbol_total": 100,
                "current_symbol": "AAPL",
            }
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.25
    assert "25/100" in caption
    assert "AAPL" in caption


def test_build_run_symbol_progress_payload_uses_generic_summary_counters_for_data_sanitizer() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "data_sanitizer_daily",
            "run_summary": {
                "targeted_symbols": 100,
                "successful_symbols": 70,
                "skipped_symbols": 5,
                "failed_symbols": 10,
            },
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.85
    assert "85/100" in caption
    assert "sanitizeur" in caption.lower()


def test_build_run_symbol_progress_payload_falls_back_to_live_logs_when_summary_has_no_progress() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "sync_earnings_calendar",
            "run_summary": {},
            "stdout_tail": (
                "2026-05-03 08:00:00 INFO Finnhub earnings calendar progress | "
                "processed=40/120 records=300 completed=38 failed=2 latest_symbol=NVDA\n"
            ),
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert round(fraction, 4) == round(40 / 120, 4)
    assert "40/120" in caption
    assert "NVDA" in caption


def test_build_run_symbol_progress_payload_parses_traitement_log_pattern() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "data_sanitizer_daily",
            "stdout_tail": "2026-05-03 08:00:00 INFO Traitement 37/200: AAPL\n",
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.185
    assert "37/200" in caption
    assert "AAPL" in caption


def test_build_run_symbol_progress_payload_prefers_explicit_live_progress_fields() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "stock_screener",
            "run_summary": {
                "progress_current": 3,
                "progress_total": 8,
                "progress_label": "🔎 Progression stock screener",
                "progress_item": "chunk #3",
            },
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.375
    assert "3/8" in caption
    assert "chunk #3" in caption


def test_should_render_active_run_live_progress_returns_false_for_workflow_child_when_parent_workflow_is_active() -> None:
    should_render = workflow_page._should_render_active_run_live_progress(
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "parent_run_id": "wf-1",
        },
        active_workflow_run_ids={"wf-1"},
    )

    assert should_render is False


def test_should_render_active_run_live_progress_returns_true_for_standalone_step() -> None:
    should_render = workflow_page._should_render_active_run_live_progress(
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "parent_run_id": None,
        },
        active_workflow_run_ids={"wf-1"},
    )

    assert should_render is True


def test_workflow_launcher_starts_with_1_to_12_and_optional_steps_disabled_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-1"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["start_step"] == "1"
    assert captured["include_ml_train"] is True
    assert captured["include_corporate_actions_sync"] is False
    assert captured["include_corporate_actions_apply"] is False


def test_workflow_launcher_can_start_at_step_3_and_include_corporate_actions(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: "3")
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: True)
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-2"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["start_step"] == "3"
    assert captured["include_ml_train"] is True
    assert captured["include_corporate_actions_sync"] is True
    assert captured["include_corporate_actions_apply"] is True


def test_workflow_launcher_can_schedule_delayed_start(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(*args, **kwargs):
        key = kwargs.get("key")
        if key == workflow_page.WORKFLOW_DELAYED_START_ENABLED_KEY:
            return True
        return kwargs.get("value", False)

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(workflow_page.st, "time_input", lambda *args, **kwargs: dt_time(hour=2, minute=0))
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: kwargs.get("key") == "run_pipeline_workflow_all_steps")

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-delayed"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    scheduled_for = cast(datetime, captured["scheduled_for"])
    assert scheduled_for is not None
    assert scheduled_for.hour == 2
    assert scheduled_for.minute == 0


def test_build_scheduled_countdown_caption_displays_remaining_time() -> None:
    now = datetime(2026, 5, 7, 23, 0, 0)
    scheduled_for = now + timedelta(hours=3, minutes=15, seconds=4)

    caption = workflow_page._build_scheduled_countdown_caption(
        {
            "status": "scheduled",
            "scheduled_for": scheduled_for.isoformat(timespec="seconds"),
        },
        now=now,
    )

    assert caption is not None
    assert "2026-05-08 02:15:04" in caption
    assert "03:15:04" in caption
    assert "départ dans" in caption.lower()


def test_build_scheduled_countdown_caption_returns_none_for_non_scheduled_run() -> None:
    caption = workflow_page._build_scheduled_countdown_caption(
        {
            "status": "running",
            "scheduled_for": "2026-05-08T02:15:04",
        }
    )

    assert caption is None


def test_build_actual_start_caption_displays_actual_and_planned_times() -> None:
    caption = workflow_page._build_actual_start_caption(
        {
            "status": "running",
            "scheduled_for": "2026-05-08T02:00:00",
            "actual_started_at": "2026-05-08T02:00:07",
        }
    )

    assert caption is not None
    assert "démarrage réel" in caption.lower()
    assert "2026-05-08 02:00:07" in caption
    assert "2026-05-08 02:00:00" in caption
    assert "planifié pour" in caption.lower()


def test_build_actual_start_caption_returns_none_while_workflow_is_still_scheduled() -> None:
    caption = workflow_page._build_actual_start_caption(
        {
            "status": "scheduled",
            "scheduled_for": "2026-05-08T02:00:00",
            "actual_started_at": "2026-05-08T02:00:07",
        }
    )

    assert caption is None


def test_workflow_launcher_can_launch_explicit_selected_pipelines_in_order(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "markdown", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "divider", lambda: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "columns", lambda n: [_DummyContainer() for _ in range(n)])
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(*args, **kwargs):
        key = kwargs.get("key")
        if key == workflow_page.WORKFLOW_INCLUDE_ML_TRAIN_KEY:
            return kwargs.get("value", False)
        if key == workflow_page.WORKFLOW_INCLUDE_CA_SYNC_KEY:
            return False
        if key == workflow_page.WORKFLOW_INCLUDE_CA_APPLY_KEY:
            return False
        return key in {
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}import_alpaca_bar",
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}stock_screener",
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}execution",
        }

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(
        workflow_page.st,
        "button",
        lambda *args, **kwargs: kwargs.get("key") == "run_pipeline_workflow_selected_steps",
    )

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-custom"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["selected_step_keys"] == (
        "import_alpaca_bar",
        "stock_screener",
        "execution",
    )


def test_workflow_launcher_custom_selection_displays_7bis_between_7_and_8(monkeypatch) -> None:
    checkbox_labels: list[str] = []

    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "markdown", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "divider", lambda: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "columns", lambda n: [_DummyContainer() for _ in range(n)])
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(label, *args, **kwargs):
        checkbox_labels.append(str(label))
        return kwargs.get("value", False)

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: False)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    custom_labels = [label for label in checkbox_labels if label[:1].isdigit()]
    assert "7. Sentiment Pipeline" in custom_labels
    # Le label réel est "7bis. Recalcul relevance + contextual (7bis)" — on vérifie le préfixe
    assert any(label.startswith("7bis.") for label in custom_labels), (
        f"Aucun label 7bis trouvé dans : {custom_labels}"
    )
    assert "8. Signal Aggregator" in custom_labels
    idx_7 = custom_labels.index("7. Sentiment Pipeline")
    idx_7bis = next(i for i, l in enumerate(custom_labels) if l.startswith("7bis."))
    idx_8 = custom_labels.index("8. Signal Aggregator")
    assert idx_7 < idx_7bis < idx_8


def test_build_workflow_child_run_payload_returns_latest_runs_first_with_labels(monkeypatch) -> None:
    child_runs = {
        "run-step-1": {
            "step_label": "1. Import Bars",
            "status": "completed",
            "executed_at": "2026-05-02T20:12:59",
        },
        "run-step-2": {
            "step_label": "2. Sanitize",
            "status": "running",
            "executed_at": "2026-05-02T20:13:59",
        },
    }
    monkeypatch.setattr(workflow_page, "get_pipeline_run_record", lambda run_id: child_runs.get(run_id))

    child_ids, child_labels = workflow_page._build_workflow_child_run_payload(
        {
            "workflow_child_run_ids": ["run-step-1", "run-step-2", "run-step-2", "  ", None],
        }
    )

    assert child_ids == ["run-step-2", "run-step-1"]
    assert "2. Sanitize" in child_labels["run-step-2"]
    assert "🟨 En cours" in child_labels["run-step-2"]
    assert "1. Import Bars" in child_labels["run-step-1"]
    assert "🟢 Terminé" in child_labels["run-step-1"]


def test_prepare_workflow_child_run_state_auto_selects_current_run(monkeypatch) -> None:
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, last_auto_key = (
        workflow_page._prepare_workflow_child_run_state(
            {
                "run_id": "wf-1",
                "status": "running",
                "workflow_current_child_run_id": "run-step-2",
            },
            ["run-step-2", "run-step-1"],
            {
                "run-step-2": "2. Sanitize | run-step-2",
                "run-step-1": "1. Import Bars | run-step-1",
            },
        )
    )

    assert child_select_key == "workflow_child_run_select_wf-1"
    assert follow_enabled is True
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-2"
    assert last_auto_key == "workflow_child_run_last_auto_wf-1"
    assert workflow_page.st.session_state[child_select_key] == "run-step-2"


def test_prepare_workflow_child_run_state_preserves_manual_selection_when_follow_disabled(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-2": False,
        "workflow_child_run_select_wf-2": "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-2",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-2"
    assert follow_enabled is False
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-1"
    assert workflow_page.st.session_state[child_select_key] == "run-step-1"


def test_prepare_workflow_child_run_state_disables_follow_when_manual_selection_differs_current(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-3": True,
        "workflow_child_run_select_wf-3": "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-3",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-3"
    assert follow_enabled is False
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-1"
    assert workflow_page.st.session_state["workflow_child_run_autofollow_wf-3"] is False


def test_prepare_workflow_child_run_state_consumes_pending_reselect_to_current(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-4": False,
        "workflow_child_run_select_wf-4": "run-step-1",
        "workflow_child_run_pending_select_wf-4": "run-step-2",
        "workflow_child_run_pending_autofollow_wf-4": True,
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-4",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-4"
    assert follow_enabled is True
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-2"
    assert workflow_page.WORKFLOW_CHILD_PENDING_SELECT_KEY_PREFIX + "wf-4" not in workflow_page.st.session_state
    assert workflow_page.WORKFLOW_CHILD_PENDING_AUTOFOLLOW_KEY_PREFIX + "wf-4" not in workflow_page.st.session_state


def test_prime_runtime_center_state_prefers_active_workflow_parent_over_latest_child_run(monkeypatch) -> None:
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "running",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟨 En cours",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    compare_defaults = workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert compare_defaults == []
    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "wf-1"
    assert workflow_page.st.session_state[workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] == "wf-1"


def test_prime_runtime_center_state_promotes_auto_selected_child_run_back_to_active_workflow(monkeypatch) -> None:
    session_state = {
        workflow_page.SELECTED_RUN_KEY: "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "completed",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟢 Terminé",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "wf-1"
    assert workflow_page.st.session_state[workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] == "wf-1"


def test_prime_runtime_center_state_preserves_manual_child_selection_during_active_workflow(monkeypatch) -> None:
    session_state = {
        workflow_page.SELECTED_RUN_KEY: "run-step-1",
        workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY: "wf-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "completed",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟢 Terminé",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "run-step-1"


