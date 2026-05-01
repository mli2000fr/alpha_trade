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
    assert "0 → 5 000 $" in message


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


def test_workflow_launcher_starts_with_ml_train_by_default(monkeypatch) -> None:
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
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-1"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["include_ml_train"] is True


def test_workflow_launcher_can_include_ml_train(monkeypatch) -> None:
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
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: True)
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-2"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["include_ml_train"] is True


