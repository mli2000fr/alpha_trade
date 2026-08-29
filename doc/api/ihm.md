# Inventaire API — ihm

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `ihm/app.py`

- ligne 78 — `def _select_page(label: str) -> None:`
## `ihm/components/alpha_scanner_dependency.py`

- ligne 15 — `def dependency_badge(status: str, label: str) -> str:`
- ligne 21 — `def get_dependency_payload(diagnostic: DependencyDiagnostic | None, step_key: str) -> dict[str, object] | None:`
- ligne 31 — `def format_dependency_latest_date(value: object) -> str:`
- ligne 36 — `def format_dependency_symbol_count(value: object) -> str:`
- ligne 43 — `def build_alpha_scanner_dependency_rows(diagnostic: DependencyDiagnostic | None) -> pd.DataFrame:`
- ligne 68 — `def render_dependency_metrics(payload: dict[str, object]) -> None:`
- ligne 80 — `def render_alpha_scanner_dependency_panel(`
## `ihm/components/db_controls.py`

- ligne 15 — `def render_db_connection_form(form_key: str, *, show_host_fields: bool = True) -> None:`
- ligne 74 — `def render_db_unavailable(page_label: str, *, form_key: str) -> None:`
- ligne 80 — `def render_query_diagnostic(empty_message: str) -> bool:`
## `ihm/components/help_tooltip.py`

- ligne 20 — `def _format_field(value: Any) -> str:`
- ligne 26 — `def _help(page: str, key: str) -> str:`
- ligne 60 — `def help_or_default(page: str, key: str, default: str) -> str:`
## `ihm/components/kpi_card.py`

- ligne 9 — `def kpi_card(`
## `ihm/components/market_regime_banner.py`

- ligne 43 — `def load_latest_snapshot(directory: Path | None = None) -> dict[str, Any] | None:`
- ligne 61 — `def render_market_regime_banner(`
## `ihm/components/metrics.py`

- ligne 16 — `def to_int(value: object, default: int = 0) -> int:`
- ligne 23 — `def format_duration_hhmmss(value: object) -> str:`
- ligne 35 — `def metric_row(metrics: list[tuple[str, str | int | float, str | None]]) -> None:`
- ligne 9 — `def _to_float(value: object, default: float = 0.0) -> float:`
## `ihm/components/ops_command_panel.py`

- ligne 151 — `def _render_recent_runs(key: OpsCommandKey, limit: int) -> None:`
- ligne 35 — `def _format_command(command: list[str]) -> str:`
- ligne 39 — `def render_ops_command_panel(`
## `ihm/components/run_summary.py`

- ligne 114 — `def render_persistent_business_summary(`
- ligne 17 — `def _coerce_int(value: object) -> int:`
- ligne 25 — `def _coerce_float(value: object) -> float:`
- ligne 33 — `def _build_live_progress_text(summary: Mapping[str, object]) -> str:`
- ligne 63 — `def render_run_summary_block(`
## `ihm/components/screener_artifacts.py`

- ligne 20 — `def build_screener_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 24 — `def render_shared_screener_artifact_selector(`
## `ihm/components/section_header.py`

- ligne 7 — `def section_header(`
## `ihm/components/status_badges.py`

- ligne 13 — `def env_badge(var_name: str, value: str | None) -> str:`
- ligne 20 — `def run_status_badge(status: str | None) -> str:`
- ligne 31 — `def decision_badge(decision: str) -> str:`
- ligne 40 — `def classify_heartbeat_freshness(`
- ligne 7 — `def badge(label: str, status: str = "ok") -> str:`
- ligne 78 — `def heartbeat_badge(`
## `ihm/components/swing_score.py`

- ligne 45 — `def _read_uploaded_symbols(uploaded) -> list[str]:`
- ligne 58 — `def _cached_resolve_universe(symbol_source: str) -> list[str]:`
- ligne 63 — `def _build_output_text(result: pd.DataFrame, top_n: int) -> str:`
- ligne 68 — `def _render_result(result: pd.DataFrame, top_n: int, diagnostics: dict, source_symbols_count: int) -> None:`
- ligne 94 — `def render_swing_score_block() -> None:`
## `ihm/components/symbol_bars_dialog.py`

- ligne 108 — `def _render_dialog_body(symbol: str, default_lookback_days: int) -> None:`
- ligne 167 — `def show_symbol_bars_dialog(symbol: str, lookback_days: int = 365) -> None:`
- ligne 38 — `def _normalize_eodhd_payload(payload: list[dict[str, Any]]) -> pd.DataFrame:`
- ligne 51 — `def _normalize_stooq_payload(payload: list[dict[str, Any]]) -> pd.DataFrame:`
- ligne 62 — `def _fetch_bars_eodhd(symbol: str, *, start: date, end: date) -> pd.DataFrame:`
- ligne 76 — `def _fetch_bars_stooq(symbol: str, *, start: date, end: date) -> pd.DataFrame:`
- ligne 91 — `def load_symbol_bars(symbol: str, lookback_days: int = 365) -> pd.DataFrame:`
## `ihm/components/symbol_table.py`

- ligne 126 — `def render_symbol_table(`
- ligne 32 — `class ActionSpec:`
- ligne 57 — `def _selected_row_index(table_key: str) -> int | None:`
- ligne 73 — `def _resolve_symbol(df: pd.DataFrame, row_index: int, symbol_col: str) -> str | None:`
- ligne 85 — `def _render_action_bar(`
## `ihm/components/tables.py`

- ligne 8 — `def show_dataframe(df: pd.DataFrame, title: str | None = None, height: int = 400) -> None:`
## `ihm/components/watcher_documentation.py`

- ligne 34 — `def render_watcher_documentation_panel(*, intro: str | None = None) -> None:`
- ligne 9 — `def build_watcher_documentation_panel_payload() -> dict[str, str]:`
## `ihm/pages/__init__.py`

- ligne 7 — `def run_page_if_standalone(module_name: str, render_func: Callable[[], None]) -> None:`
## `ihm/pages/_alpha_scanner_diagnostics.py`

- ligne 206 — `def _render_dependency_health_inline(step_key: str, dependency_diagnostic: dict[str, object] | None) -> None:`
- ligne 214 — `def _render_dependency_action_feedback(latest_by_step: dict[str, dict[str, object]]) -> None:`
- ligne 249 — `def _render_alpha_scanner_dependency_diagnostic(`
- ligne 50 — `def _alpha_scanner_dependency_block_reason(dependency_diagnostic: dict[str, object] | None) -> str | None:`
- ligne 59 — `def _threshold_widget_key(step_key: str, metric_key: str) -> str:`
- ligne 63 — `def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds: dict[str, dict[str, float]]) -> None:`
- ligne 69 — `def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]:`
- ligne 83 — `def _collect_alpha_scanner_dependency_threshold_inputs() -> dict[str, dict[str, float]]:`
- ligne 93 — `def _set_alpha_scanner_dependency_threshold_state(thresholds: dict[str, dict[str, float]]) -> None:`
- ligne 97 — `def _render_alpha_scanner_dependency_threshold_editor() -> None:`
## `ihm/pages/_data_integrity.py`

- ligne 104 — `def _sync_date_input(canonical_key: str, widget_key: str, raw_value: str) -> None:`
- ligne 109 — `def _format_date_input_status(raw_value: str, parsed_value: DateValue | None) -> str:`
- ligne 115 — `def _register_new_run(record: PipelineRunRecord, all_runs: list[dict[str, object]]) -> None:`
- ligne 127 — `def _resolve_import_news_scope_preview(`
- ligne 144 — `def _backfill_diag_int(diag: dict[str, object], key: str, default: int = 0) -> int:`
- ligne 153 — `def _backfill_diag_float(diag: dict[str, object], key: str, default: float = 0.0) -> float:`
- ligne 163 — `def _resolve_symbols_for_diagnostic(`
- ligne 177 — `def _render_backfill_completeness_panel(`
- ligne 403 — `def _latest_step_run_for_panel(`
- ligne 430 — `def _render_import_news_panel(`
- ligne 51 — `def _coerce_date(value: object, fallback: DateValue) -> DateValue:`
- ligne 55 — `def _coerce_date_text(value: object, fallback: DateValue) -> str:`
- ligne 62 — `def _parse_iso_date_text(value: object) -> DateValue | None:`
- ligne 72 — `def _date_last_synced_key(widget_key: str) -> str:`
- ligne 76 — `def _ensure_date_input_state(canonical_key: str, widget_key: str, fallback: DateValue) -> str:`
## `ihm/pages/_execution_center/__init__.py`

- ligne 1241 — `def _render_signal_aggregator_block() -> dict[str, Any]:`
- ligne 1360 — `def _render_live_confirmation_block(execution_mode: str) -> bool:`
- ligne 1405 — `def _render_screener_block() -> dict[str, Any]:`
- ligne 1528 — `def _render_risk_block(selected_capital_preset: CapitalPreset | None) -> dict[str, Any]:`
- ligne 1921 — `def _render_selector_block() -> dict[str, Any]:`
- ligne 2227 — `def _render_data_integrity_block() -> dict[str, Any]:`
- ligne 2468 — `def _render_corporate_actions_block(trade_date: str) -> dict[str, Any]:`
- ligne 2617 — `def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]:`
- ligne 357 — `def _get_capital_presets() -> tuple[CapitalPreset, ...]:`
- ligne 364 — `def _get_capital_preset_options() -> list[str]:`
- ligne 368 — `def _format_capital_preset_label(preset_key: str) -> str:`
- ligne 375 — `def _build_parameter_rerun_guidance_rows() -> tuple[dict[str, str], ...]:`
- ligne 386 — `def _normalize_ml_train_preset_key(preset_key: str | None) -> str:`
- ligne 395 — `def _coerce_session_date(value: object, *, default: date) -> date:`
- ligne 406 — `def _coerce_int(value: object, *, default: int | None) -> int:`
- ligne 416 — `def _coerce_float(value: object, *, default: float | None) -> float:`
- ligne 426 — `def _coerce_bool(value: object, *, default: bool) -> bool:`
- ligne 443 — `def _session_state_int(key: str, default: int | None) -> int:`
- ligne 447 — `def _session_state_float(key: str, default: float | None) -> float:`
- ligne 451 — `def _session_state_bool(key: str, default: bool) -> bool:`
- ligne 459 — `def _ensure_normalized_ml_train_preset_session_state(session_state: dict[str, object]) -> str:`
- ligne 467 — `def _format_ml_train_preset_label(preset_key: str) -> str:`
- ligne 477 — `def _build_ml_train_preset_session_state_values(preset_key: str) -> dict[str, object]:`
- ligne 515 — `def _build_ml_train_preset_summary(preset_key: str) -> str:`
- ligne 536 — `def _is_selected_ml_train_preset_dirty(session_state: dict[str, object]) -> bool:`
- ligne 544 — `def _apply_selected_ml_train_preset(*, force: bool = False) -> None:`
- ligne 560 — `def _apply_selected_capital_preset(`
- ligne 589 — `def _apply_execution_prefills(selected_account_id: str | None) -> PipelineExecutionDefaults | None:`
- ligne 662 — `def _build_execution_prefill_caption(defaults: PipelineExecutionDefaults | None) -> str | None:`
- ligne 683 — `class LaunchOptionsContext:`
- ligne 701 — `def _build_contextual_backlog_estimate_scope(`
- ligne 718 — `def _load_contextual_backlog_preview(`
- ligne 771 — `def _render_event_sentiment_block() -> dict[str, Any]:`
## `ihm/pages/_execution_center/_render_pending.py`

- ligne 122 — `def render_model_factory_block() -> dict[str, Any]:`
- ligne 35 — `def render_execution_block(`
## `ihm/pages/_shared.py`

- ligne 107 — `def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:`
- ligne 114 — `def _to_optional_positive_int(value: int | float | None) -> int | None:`
- ligne 121 — `def _rerun_app() -> None:`
- ligne 128 — `def _render_run_summary(record: dict[str, object] | None, *, compact: bool = False) -> None:`
- ligne 181 — `def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:`
- ligne 194 — `def _pipeline_step_label(step_key: str) -> str:`
- ligne 201 — `def _record_dependency_action_run(step_key: str, run_id: str) -> None:`
- ligne 208 — `def _launch_pipeline_step(`
- ligne 237 — `def _status_badge(status: str) -> str:`
- ligne 249 — `def _is_workflow_run(run: dict[str, object]) -> bool:`
- ligne 253 — `def _workflow_progress(run: dict[str, object]) -> tuple[int, int, float, str]:`
- ligne 264 — `def _build_watchdog_badge(record: dict[str, object] | None) -> str | None:`
- ligne 278 — `def _render_watchdog_status(record: dict[str, object] | None) -> None:`
- ligne 296 — `def _sanitize_compare_ids(run_ids: list[str], labels: dict[str, str], value: object) -> list[str]:`
- ligne 301 — `def _render_step_result(record: dict[str, object] | None) -> None:`
- ligne 329 — `def _render_risk_snapshot_freshness_warning(record: dict[str, object]) -> None:`
## `ihm/pages/_watcher_block.py`

- ligne 132 — `def _render_watcher_launch_controls(options: PipelineLaunchOptions) -> None:`
- ligne 38 — `def _build_watcher_handoff_rows(`
- ligne 94 — `def _render_watcher_handoff_panel(options: PipelineLaunchOptions) -> None:`
## `ihm/pages/_workflow/__init__.py`

- ligne 103 — `def _resolve_delayed_workflow_start(target_time: dt_time, *, now: datetime | None = None) -> datetime:`
- ligne 111 — `def _parse_iso_datetime(value: object) -> datetime | None:`
- ligne 121 — `def _format_countdown(total_seconds: int) -> str:`
- ligne 130 — `def _rerun_app() -> None:`
- ligne 137 — `def _build_scheduled_countdown_caption(run: dict[str, object], *, now: datetime | None = None) -> str | None:`
- ligne 151 — `def _build_actual_start_caption(run: dict[str, object]) -> str | None:`
- ligne 161 — `def _build_workflow_scope_help_lines() -> tuple[str, str, str]:`
- ligne 169 — `def _build_workflow_scope_alert_lines() -> tuple[str, str]:`
- ligne 176 — `def _workflow_mode_label(run: dict[str, object]) -> str:`
- ligne 199 — `def _custom_workflow_checkbox_key(step_key: str) -> str:`
- ligne 203 — `def _build_run_provider_badge(run: dict[str, object] | None) -> str | None:`
- ligne 229 — `def _build_run_stooq_badge(run: dict[str, object] | None) -> str | None:`
- ligne 236 — `def _build_run_symbol_progress_caption(run: dict[str, object] | None) -> str | None:`
- ligne 244 — `def _build_run_symbol_progress_payload(run: dict[str, object] | None) -> tuple[float, str] | None:`
- ligne 270 — `def _to_non_negative_int(value: object) -> int | None:`
- ligne 280 — `def _build_run_progress_payload_from_explicit_summary(summary: dict[str, object]) -> tuple[float, str] | None:`
- ligne 294 — `def _build_run_progress_payload_from_summary(step_key: str, summary: dict[str, object]) -> tuple[float, str] | None:`
- ligne 318 — `def _build_run_progress_payload_from_logs(run: dict[str, object]) -> tuple[float, str] | None:`
- ligne 354 — `def _build_workflow_child_run_payload(workflow_run: dict[str, object]) -> tuple[list[str], dict[str, str]]:`
- ligne 381 — `def _prepare_workflow_child_run_state(`
- ligne 436 — `def _cached_history() -> list[dict[str, object]]:`
- ligne 440 — `def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]:`
- ligne 453 — `def _latest_run_by_step(all_runs: list[dict[str, object]]) -> dict[str, dict[str, object]]:`
- ligne 462 — `def _build_history_rows(all_runs: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 488 — `def _should_render_active_run_live_progress(`
- ligne 503 — `def _active_workflow_run_id(all_runs: list[dict[str, object]]) -> str | None:`
- ligne 515 — `def _resolve_runtime_center_default_selected_run_id(all_runs: list[dict[str, object]], run_ids: list[str]) -> str:`
- ligne 528 — `def _prime_runtime_center_state(all_runs: list[dict[str, object]], run_ids: list[str], labels: dict[str, str]) -> list[str]:`
- ligne 568 — `def _selected_dataframe_row_index(table_key: str) -> int | None:`
- ligne 584 — `def _resolve_history_selected_run_id(`
- ligne 598 — `def _render_workflow_launcher(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None:`
- ligne 808 — `def _render_runtime_center() -> None:`
## `ihm/pages/alpaca_accounts.py`

- ligne 127 — `def _clear_page_caches() -> None:`
- ligne 137 — `def _build_failover_doctrine_dataframe(summary: dict[str, Any]) -> pd.DataFrame:`
- ligne 151 — `def _render_failover_doctrine_panel() -> None:`
- ligne 169 — `def render() -> None:`
- ligne 36 — `def _format_currency(value: object) -> str:`
- ligne 44 — `def _format_bool(value: object) -> str:`
- ligne 48 — `def _build_account_details_dataframe(account_payload: dict[str, Any]) -> pd.DataFrame:`
- ligne 68 — `def _render_live_account_summary(account_payload: dict[str, Any]) -> None:`
- ligne 87 — `def _render_capital_history(*, account_id: str, portfolio_history: pd.DataFrame, snapshot_history: pd.DataFrame) -> None:`
## `ihm/pages/backtesting/__init__.py`

- ligne 1046 — `def _render_pipeline_pit_hint(`
- ligne 1071 — `def _render_ml_coverage_preflight(`
- ligne 1141 — `def _build_overlay_options(`
- ligne 1502 — `def _build_run_options() -> BacktestRunOptions:`
- ligne 178 — `def _to_float(value: object, default: float = 0.0) -> float:`
- ligne 185 — `def _to_int(value: object, default: int = 0) -> int:`
- ligne 192 — `def _parse_optional_int(raw_value: str, *, label: str) -> int | None:`
- ligne 203 — `def _parse_optional_float(raw_value: str, *, label: str) -> float | None:`
- ligne 214 — `def _to_date_value(value: object, default: str):`
- ligne 234 — `def _get_capital_presets() -> tuple[CapitalPreset, ...]:`
- ligne 241 — `def _get_capital_preset_options() -> list[str]:`
- ligne 249 — `def _get_run_configuration_preset(preset_key: str) -> dict[str, object] | None:`
- ligne 254 — `def _ensure_run_configuration_preset_session_key() -> str:`
- ligne 263 — `def _format_run_configuration_preset_label(preset_key: str) -> str:`
- ligne 270 — `def _apply_run_configuration_preset(selected_preset_key: str) -> dict[str, object] | None:`
- ligne 2808 — `def _build_backfill_options() -> BackfillScoresHistoryOptions:`
- ligne 288 — `def _format_capital_preset_label(preset_key: str) -> str:`
- ligne 295 — `def _resolve_default_capital_preset_key(equity: float | None) -> str:`
- ligne 2982 — `def _build_diagnose_screener_options() -> DiagnoseScreenerOptions:`
- ligne 302 — `def _ensure_capital_preset_session_key(`
- ligne 3142 — `def _build_recommend_screener_options() -> RecommendScreenerOptions:`
- ligne 3227 — `def _build_calibrate_sentiment_options() -> "CalibrateSentimentWeightsOptions":`
- ligne 324 — `def _apply_run_capital_preset(selected_preset_key: str, equity: float) -> CapitalPreset | None:`
- ligne 3307 — `def _build_calibrate_conviction_options() -> "CalibrateConvictionWeightsOptions":`
- ligne 3414 — `def _build_walk_forward_conviction_options() -> "WalkForwardConvictionOptions":`
- ligne 3556 — `def _build_walk_forward_sentiment_options() -> "WalkForwardSentimentOptions":`
- ligne 364 — `def _resolve_pipeline_backtest_defaults(`
- ligne 3727 — `def _render_latest_artifacts() -> None:`
- ligne 3754 — `def _resolve_run_dir(run_record: dict[str, object]) -> Path | None:`
- ligne 3762 — `def _resolve_run_artifact_path(run_dir: Path, filename: str) -> Path:`
- ligne 3772 — `def _load_run_report(run_record: dict[str, object]) -> dict[str, object] | None:`
- ligne 3786 — `def _load_equity_curve_df(run_record: dict[str, object]) -> pd.DataFrame:`
- ligne 3805 — `def _load_run_trades_df(run_record: dict[str, object]) -> pd.DataFrame:`
- ligne 3831 — `def _load_market_regimes_df(run_record: dict[str, object]) -> pd.DataFrame:`
- ligne 3849 — `def _format_position_quantity(quantity: float) -> str:`
- ligne 3856 — `def _format_position_notional(amount: float) -> str:`
- ligne 3860 — `def _resolve_trade_entry_notional(trade: object) -> float | None:`
- ligne 3875 — `def _register_position_delta(`
- ligne 3885 — `def _build_position_detail_text(symbol: str, quantity: float, entry_notional: float | None) -> str:`
- ligne 3892 — `def _build_daily_portfolio_snapshot_df(`
- ligne 4017 — `def _resolve_phase2_risk_summary(`
- ligne 4029 — `def _render_report_summary(run_record: dict[str, object]) -> bool:`
- ligne 404 — `def _load_dip_backtest_defaults() -> dict[str, Any]:`
- ligne 430 — `def _apply_backfill_capital_preset(selected_preset_key: str, capital: float) -> CapitalPreset | None:`
- ligne 450 — `def _tail_text(value: str, max_lines: int = TAIL_LINES) -> str:`
- ligne 4528 — `def _render_live_artifacts(run_record: dict[str, object]) -> bool:`
- ligne 457 — `def _file_cache_signature(path: Path) -> tuple[str, int, int] | None:`
- ligne 4589 — `def _coerce_metric_text(value: object) -> str:`
- ligne 4596 — `def _format_fidelity_status(status: object) -> str:`
- ligne 4605 — `def _build_fidelity_component_rows(fidelity: dict[str, object]) -> pd.DataFrame:`
- ligne 4633 — `def _build_fidelity_coverage_rows(fidelity: dict[str, object]) -> pd.DataFrame:`
- ligne 4657 — `def _build_fidelity_provenance_rows(fidelity: dict[str, object]) -> pd.DataFrame:`
- ligne 468 — `def _read_cached_json_file(path_str: str, mtime_ns: int, size_bytes: int) -> dict[str, object] | None:`
- ligne 4684 — `def _build_fidelity_ml_cause_rows(fidelity: dict[str, object]) -> pd.DataFrame:`
- ligne 4704 — `def _load_json_artifact_from_paths(artifacts: dict[str, object], artifact_key: str) -> dict[str, object] | None:`
- ligne 4718 — `def _build_replay_diagnostic_session_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 4756 — `def _build_selection_target_parity_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 4779 — `def _build_compare_to_live_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 478 — `def _read_cached_csv_file(path_str: str, mtime_ns: int, size_bytes: int) -> pd.DataFrame:`
- ligne 483 — `def _should_preload_runtime_details(status: str) -> bool:`
- ligne 4844 — `def _build_fidelity_baseline_snapshot_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 4858 — `def _build_fidelity_baseline_check_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 487 — `def _should_auto_refresh_runtime_center(*run_groups: list[dict[str, object]]) -> bool:`
- ligne 4881 — `def _build_fidelity_symbol_matrix_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 4908 — `def _build_execution_broker_like_session_rows(payload: dict[str, object]) -> pd.DataFrame:`
- ligne 491 — `def _is_runtime_center_auto_update_enabled() -> bool:`
- ligne 4944 — `def _resolve_screener_artifact_summary(run_record: dict[str, object]) -> dict[str, object] | None:`
- ligne 495 — `def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:`
- ligne 4954 — `def _build_screener_artifact_metric_rows(summary: dict[str, object]) -> list[tuple[str, str]]:`
- ligne 4971 — `def _build_screener_artifact_objective_rows(summary: dict[str, object]) -> pd.DataFrame:`
- ligne 4990 — `def _build_screener_artifact_file_rows(summary: dict[str, object]) -> pd.DataFrame:`
- ligne 5012 — `def _build_global_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 5016 — `def _render_screener_artifact_summary(run_record: dict[str, object]) -> bool:`
- ligne 508 — `def _status_badge(status: str) -> str:`
- ligne 5086 — `def _render_batch_diagnostics_block() -> None:`
- ligne 519 — `def _extract_run_batch_id(run: dict[str, object]) -> str | None:`
- ligne 5244 — `def _render_runtime_center_body(*, auto_refresh_enabled: bool) -> None:`
- ligne 542 — `def _extract_run_dates(run: dict[str, object]) -> tuple[str | None, str | None]:`
- ligne 5672 — `def _render_runtime_center_live() -> None:`
- ligne 5683 — `def _render_runtime_center_static() -> None:`
- ligne 5687 — `def render() -> None:`
- ligne 572 — `def _load_batch_comments(batch_ids: tuple[str, ...]) -> dict[str, str]:`
- ligne 588 — `def _format_run_inspect_label(run: dict[str, object], batch_comments: dict[str, str]) -> str:`
- ligne 607 — `def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]:`
- ligne 620 — `def _prime_runtime_center_state(run_ids: list[str], labels: dict[str, str]) -> None:`
- ligne 630 — `def _selected_dataframe_row_index(table_key: str) -> int | None:`
- ligne 646 — `def _resolve_history_selected_run_id(`
- ligne 660 — `def _resolve_history_selected_run_ids(`
- ligne 691 — `def _clear_history_selection(*, table_key: str = BACKTESTING_HISTORY_TABLE_KEY) -> None:`
- ligne 717 — `def _parameter_reference_rows(kind: str) -> list[dict[str, str]]:`
- ligne 842 — `def _render_reference_table(kind: str) -> None:`
- ligne 850 — `def _summarize_sector_multipliers(path: Path) -> str:`
- ligne 864 — `def _list_backtest_runs_with_trades() -> list[str]:`
- ligne 877 — `def _default_fidelity_baseline_catalog_path() -> Path:`
- ligne 881 — `def _build_fidelity_baseline_catalog_rows(catalog_path: Path | None = None) -> pd.DataFrame:`
- ligne 919 — `def _build_pipeline_pit_status_message(diagnostic: dict[str, object]) -> tuple[str, str]:`
- ligne 969 — `def _build_ml_coverage_status_message(diagnostic: dict[str, object]) -> tuple[str, str]:`
## `ihm/pages/compliance_audit.py`

- ligne 24 — `def _level_bool(v: bool | None) -> str:`
- ligne 32 — `def _level_count(v: int | None, *, danger_at: int = 1, warn_at: int = 0) -> str:`
- ligne 42 — `def _level_pct(v: float | None, *, ok_at: float, warn_at: float) -> str:`
- ligne 52 — `def _fmt(v) -> str:`
- ligne 56 — `def render() -> None:`
## `ihm/pages/corporate_actions.py`

- ligne 22 — `def render() -> None:`
## `ihm/pages/db_admin.py`

- ligne 135 — `def render() -> None:`
- ligne 28 — `def _checkbox_key(table_name: str) -> str:`
- ligne 32 — `def _set_selection(grouped_tables: dict[str, list[TableCatalogEntry]], *, value: bool) -> None:`
- ligne 39 — `def _apply_pending_widget_resets(grouped_tables: dict[str, list[TableCatalogEntry]]) -> None:`
- ligne 51 — `def _render_last_purge_feedback() -> None:`
- ligne 71 — `def _build_execute_blockers(plan: TablePurgePlan, *, confirm_purge: bool) -> tuple[str, ...]:`
- ligne 92 — `def _render_group(group_name: str, entries: list[TableCatalogEntry]) -> None:`
## `ihm/pages/execution.py`

- ligne 118 — `def _show_position_lots_table(df: pd.DataFrame, *, title: str, height: int = 260) -> None:`
- ligne 131 — `def _safe_iterable(value: object) -> list[object]:`
- ligne 137 — `def _safe_int(value: object, default: int = 0) -> int:`
- ligne 152 — `def _render_reconciliation_age_warning(reconciliation: pd.DataFrame) -> None:`
- ligne 179 — `def _render_live_freeze_banner(live_guard: dict[str, object]) -> None:`
- ligne 191 — `def _render_reconciliation_j1_panel(`
- ligne 247 — `def _render_tca_panel(*, account_id: str | None, exec_run_id: str) -> None:`
- ligne 272 — `def render() -> None:`
- ligne 37 — `def _reconciliation_status_badge(status: object) -> str:`
- ligne 48 — `def _prepare_reconciliation_display(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 63 — `def _prepare_fills_display(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 77 — `def _normalized_symbol_set(df: pd.DataFrame) -> set[str]:`
- ligne 87 — `def _render_trade_pipeline_consistency(`
## `ihm/pages/fundamentals.py`

- ligne 115 — `def _load_sector_distribution() -> pd.DataFrame:`
- ligne 151 — `def fundamentals_page() -> None:`
- ligne 34 — `def _load_fundamentals_summary() -> pd.DataFrame:`
- ligne 468 — `def render() -> None:`
- ligne 489 — `def _start_fundamentals_fetch_subprocess(`
- ligne 618 — `def _drain_output_queue() -> None:`
- ligne 634 — `def _render_live_fundamentals_fetch() -> None:`
- ligne 687 — `def _render_fundamentals_fetch_results() -> None:`
- ligne 743 — `def _clear_fundamentals_fetch_state() -> None:`
- ligne 85 — `def _load_coverage_stats() -> dict[str, Any]:`
## `ihm/pages/glossary.py`

- ligne 18 — `def _matches(query: str, term: str, entry: dict) -> bool:`
- ligne 31 — `def render() -> None:`
## `ihm/pages/market_regime.py`

- ligne 111 — `def _populate_macro_table(start_date: _date, end_date: _date) -> dict[str, Any]:`
- ligne 127 — `def _recompute_regime_table(start_date: _date, end_date: _date, equity: float | None) -> dict[str, Any]:`
- ligne 144 — `def _format_macro_import_command(start_date: _date, end_date: _date) -> str:`
- ligne 154 — `def _format_regime_recompute_command(start_date: _date, end_date: _date, equity: float | None) -> str:`
- ligne 167 — `def _format_macro_runtime_context(yaml_cfg: dict[str, Any]) -> str:`
- ligne 202 — `def _compute_demo_snapshot(scenario: str, trade_date: _date, equity: float | None) -> dict[str, Any]:`
- ligne 279 — `def _render_summary(snap: dict[str, Any]) -> None:`
- ligne 36 — `def _load_yaml() -> dict[str, Any]:`
- ligne 398 — `def render() -> None:`
- ligne 44 — `def _list_history(limit: int = 50) -> list[Path]:`
- ligne 51 — `def _load_history_df(limit: int = 50) -> pd.DataFrame:`
- ligne 80 — `def _compute_live_snapshot(trade_date: _date, equity: float | None) -> dict[str, Any]:`
## `ihm/pages/ml_diagnostics.py`

- ligne 1091 — `def _batch_trains_oracle(batch: pd.Series) -> bool:`
- ligne 1117 — `def _oracle_periods(batch_id: str) -> list[dict[str, Any]]:`
- ligne 1141 — `def _load_latest_oracle_oos(batch_id: str) -> tuple[str | None, pd.DataFrame]:`
- ligne 1161 — `def _batch_best_horizon(batch_id: str) -> int:`
- ligne 1189 — `def _oracle_labels_worker(batch_id: str, horizon: int, strict: bool) -> None:`
- ligne 1221 — `def _launch_oracle_job(batch_id: str, horizon: int, *, strict: bool) -> None:`
- ligne 1235 — `def _render_build_oracle_labels_button(`
- ligne 1375 — `def _render_oracle_distribution(batch_id: str, row: pd.Series) -> None:`
- ligne 1585 — `def _oracle_split_table(picks: pd.DataFrame) -> dict[str, Any] | None:`
- ligne 1611 — `def _oracle_direction_split(df: pd.DataFrame) -> dict[str, Any] | None:`
- ligne 163 — `def _bold_wf_rows(df: pd.DataFrame):`
- ligne 1638 — `def _oracle_omniscient_split(df: pd.DataFrame, top_pct: float = 0.10) -> dict[str, Any] | None:`
- ligne 1671 — `def _render_oracle_quality(batch_id: str, row: pd.Series) -> None:`
- ligne 1856 — `def _render_prediction_periods(batch_id: str, batch: pd.Series) -> None:`
- ligne 1994 — `def _render_batch_detail(batch: pd.Series) -> None:`
- ligne 2604 — `def _render_global_rank_history(batch_id: str) -> None:`
- ligne 2740 — `def _render_global_ranking_horizon_details(row: pd.Series) -> None:`
- ligne 3008 — `def _split_group_from_comment(comment: str) -> tuple[str, str]:`
- ligne 3031 — `def render() -> None:`
- ligne 38 — `def _get_batch_training_logs(batch_id: str) -> str:`
- ligne 582 — `def _global_rank_all_query(horizon: int) -> str:`
- ligne 62 — `def _run_strategy_backtest(`
- ligne 649 — `def _selected_row_index(table_key: str) -> int | None:`
- ligne 665 — `def _status_badge(status: str) -> str:`
- ligne 675 — `def _render_symbol_detail(batch_id: str, symbol: str) -> None:`
- ligne 793 — `def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str:`
- ligne 812 — `def _render_regime_table(batch_id: str) -> None:`
- ligne 951 — `def _render_delete_batch_button(selected_batch: str, artifacts_dir: Path) -> None:`
## `ihm/pages/ml.py`

- ligne 102 — `def _resolve_navigation_symbol(navigation_option: dict[str, str], available_symbols: list[str]) -> str | None:`
- ligne 112 — `def _match_navigation_row(audit_df: pd.DataFrame, navigation_option: dict[str, str]) -> pd.Series:`
- ligne 130 — `def _focus_dataframe_on_navigation_row(`
- ligne 144 — `def _build_section_export_frame(section: str, frame: pd.DataFrame) -> pd.DataFrame:`
- ligne 152 — `def _build_ml_run_export_dataframe(`
- ligne 197 — `def _build_ml_run_export_filename(run_id: str, symbol: str | None = None) -> str:`
- ligne 203 — `def _build_ml_run_export_zip_filename(run_id: str, symbol: str | None = None) -> str:`
- ligne 207 — `def _to_csv_bytes(df: pd.DataFrame) -> bytes:`
- ligne 213 — `def _artifact_export_json_bytes(`
- ligne 241 — `def _build_ml_run_export_readme_bytes(`
- ligne 314 — `def _build_ml_run_export_zip_bytes(`
- ligne 353 — `def _summarize_prediction_governance_audit(audit_df: pd.DataFrame) -> dict[str, object]:`
- ligne 372 — `def _summarize_ml_runtime_status(`
- ligne 400 — `def _summarize_governance_thresholds(artifact_report: dict[str, object] | None) -> dict[str, object]:`
- ligne 431 — `def _prime_selected_symbol_state(symbols: list[str]) -> str | None:`
- ligne 448 — `def render() -> None:`
- ligne 45 — `def _sorted_non_empty_strings(values: list[object], *, reverse: bool = False) -> list[str]:`
- ligne 50 — `def _build_prediction_audit_filter_options(`
- ligne 70 — `def _build_prediction_audit_navigation_options(audit_df: pd.DataFrame) -> list[dict[str, str]]:`
## `ihm/pages/ops_infra.py`

- ligne 231 — `def _list_existing_archives(dest_dir_str: str, pattern: str = "*.tar.gz") -> list[Path]:`
- ligne 242 — `def _render_backup_ml_panel(*, db_config: dict) -> None:`
- ligne 347 — `def _render_backup_db_panel(*, db_config: dict) -> None:`
- ligne 463 — `def _render_reset_ml_panel() -> None:`
- ligne 525 — `def _run_reset_ml_with_logs(*, stop_active: bool = False, runs_only: bool = False) -> None:`
- ligne 56 — `def _render_metrics_panel() -> None:`
- ligne 606 — `def _render_reset_ml_report(report: dict[str, object]) -> None:`
- ligne 656 — `def render() -> None:`
## `ihm/pages/overview.py`

- ligne 123 — `def _merge_pipeline_runs() -> list[dict[str, object]]:`
- ligne 134 — `def _build_pipeline_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 149 — `def _build_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 153 — `def _build_screener_objective_rows(report: dict[str, object]) -> pd.DataFrame:`
- ligne 171 — `def _build_screener_objective_metrics(report: dict[str, object]) -> list[tuple[str, str, str | None]]:`
- ligne 181 — `def load_eodhd_quota_snapshot() -> dict[str, object]:`
- ligne 194 — `def _build_eodhd_quota_feature_rows(snapshot: dict[str, object]) -> pd.DataFrame:`
- ligne 212 — `def render() -> None:`
- ligne 47 — `def _pipeline_summary_label(step) -> str:`
- ligne 51 — `def _coerce_float(value: object, default: float = 0.0) -> float:`
- ligne 58 — `def _coerce_int(value: object, default: int = 0) -> int:`
- ligne 70 — `def compute_daily_pnl(pnl_data: dict[str, object]) -> tuple[float, float]:`
- ligne 89 — `def _render_pnl_widget(pnl_data: dict[str, object]) -> None:`
## `ihm/pages/parity.py`

- ligne 110 — `def _badge_color(score: float, threshold: float = 0.10) -> str:`
- ligne 118 — `def _render_rolling_section(st, pd, summaries: list[dict[str, Any]]) -> None:`
- ligne 167 — `def _render_symbol_drilldown(st, pd, summaries: list[dict[str, Any]]) -> None:`
- ligne 198 — `def render() -> None:`
- ligne 26 — `def _list_available_dates(root: Path = PARITY_ROOT) -> list[str]:`
- ligne 36 — `def _load_summary(trade_date: str, root: Path = PARITY_ROOT) -> dict | None:`
- ligne 47 — `def load_rolling_summaries(`
- ligne 64 — `def aggregate_top_divergent_symbols(`
## `ihm/pages/pipeline.py`

- ligne 1007 — `def _render_ml_scope_block(`
- ligne 1177 — `def _render_ml_train_scope_block(`
- ligne 1203 — `def _render_ml_predict_scope_block(`
- ligne 1287 — `def _build_pipeline_run_context() -> tuple[`
- ligne 1306 — `def _normalize_pipeline_run_status(value: object) -> str:`
- ligne 1310 — `def _safe_iterable(value: object) -> list[object]:`
- ligne 1316 — `def _previous_pipeline_step_key(step_key: str) -> str | None:`
- ligne 1327 — `def _pipeline_state_machine_lock_reason(`
- ligne 1348 — `def _render_live_execution_freeze_banner(live_guard: dict[str, object]) -> None:`
- ligne 1360 — `def _render_launchable_step_panel(`
- ligne 154 — `def _coerce_ui_date(value: object, *, fallback: date) -> date:`
- ligne 1614 — `def _render_step_panels(`
- ligne 165 — `def _trade_date_or_today(options: PipelineLaunchOptions) -> date:`
- ligne 1666 — `def render() -> None:`
- ligne 176 — `def _resolve_data_integrity_scope_preview(symbol_source: str, start_symbol: str | None = None) -> dict[str, object]:`
- ligne 187 — `def _is_large_quote_history_run(estimate: dict[str, object] | None) -> bool:`
- ligne 193 — `def _coerce_int_metric(value: object, *, default: int = 0) -> int:`
- ligne 200 — `def _coerce_float_metric(value: object, *, default: float = 0.0) -> float:`
- ligne 207 — `def _resolve_latest_selectbox_value(`
- ligne 223 — `def _render_period_sync_block(`
- ligne 463 — `def _render_tradable_universe_publish_block(`
- ligne 652 — `def _build_execution_mode_banner_payload(`
- ligne 692 — `def _build_execution_account_banner_payload(`
- ligne 738 — `def _build_fractional_trading_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:`
- ligne 754 — `def _build_capital_preset_banner_payload(`
- ligne 787 — `def _build_execution_protection_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:`
- ligne 808 — `def _build_live_risk_guard_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:`
- ligne 832 — `def _build_long_only_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str] | None:`
- ligne 855 — `def _build_pipeline_scope_alert_lines() -> tuple[str, str]:`
- ligne 862 — `def _render_execution_mode_banner(options: PipelineLaunchOptions) -> None:`
- ligne 909 — `def _build_universe_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:`
- ligne 945 — `def _build_swing_only_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]:`
- ligne 965 — `def _render_ml_inspection_link(step_key: str) -> None:`
- ligne 986 — `def _resolve_ml_train_scope_preview(`
## `ihm/pages/risk.py`

- ligne 123 — `def render() -> None:`
- ligne 21 — `def _render_ml_gate_status(record: dict[str, object] | None) -> None:`
- ligne 55 — `def _render_shadow_compare(summary: dict[str, object], selected_run: str | None) -> None:`
- ligne 98 — `def _render_postmortem_artifacts(summary: dict[str, object]) -> None:`
## `ihm/pages/sandbox_health.py`

- ligne 24 — `def _streak_level(green: int) -> str:`
- ligne 32 — `def render() -> None:`
## `ihm/pages/screening.py`

- ligne 114 — `def _format_csv_preview_option(file_info: dict[str, object]) -> str:`
- ligne 122 — `def _build_csv_preview_inventory_dataframe(files: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 138 — `def _build_screening_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 162 — `def _resolve_selection_explainability_payload(row: pd.Series) -> dict[str, object]:`
- ligne 169 — `def _render_screener_csv_preview(artifacts_dir: str, selected_entry: dict[str, object]) -> None:`
- ligne 250 — `def _render_objective_recommendations(artifacts_dir: str) -> None:`
- ligne 290 — `def render() -> None:`
- ligne 45 — `def _quality_summary_label(step) -> str:`
- ligne 49 — `def _merge_pipeline_runs() -> list[dict[str, object]]:`
- ligne 60 — `def _build_quality_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 75 — `def _build_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame:`
- ligne 79 — `def _build_objective_recommendation_rows(report: dict[str, object]) -> pd.DataFrame:`
- ligne 97 — `def _build_objective_metric_cards(report: dict[str, object]) -> list[tuple[str, str, str | None]]:`
## `ihm/pages/settings.py`

- ligne 132 — `def _build_micro_capital_preset_warning_message() -> str | None:`
- ligne 143 — `def _render_capital_preset_warning_banner() -> None:`
- ligne 149 — `def _flash_message(kind: str, message: str) -> None:`
- ligne 160 — `def _market_regime_label(value: str) -> str:`
- ligne 164 — `def _preset_style_label(value: str) -> str:`
- ligne 168 — `def _prime_bars_provider_widget_state(current: str) -> str:`
- ligne 184 — `def _render_bars_provider_settings():`
- ligne 264 — `def _threshold_widget_key(step_key: str, metric_key: str) -> str:`
- ligne 268 — `def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds):`
- ligne 274 — `def _prime_alpha_scanner_dependency_threshold_state():`
- ligne 296 — `def _collect_alpha_scanner_dependency_threshold_inputs():`
- ligne 306 — `def _set_alpha_scanner_dependency_threshold_state(thresholds):`
- ligne 310 — `def _apply_alpha_scanner_threshold_preset(style: str, market_regime: str):`
- ligne 333 — `def _render_alpha_scanner_dependency_threshold_settings():`
- ligne 501 — `def _get_notifications_failure_log_download_payload():`
- ligne 508 — `def _build_smtp_not_configured_warning_message(smtp_cfg) -> str | None:`
- ligne 517 — `def _build_var_env_upload_signature(file_name: str, file_bytes: bytes) -> str:`
- ligne 522 — `def _prepare_var_env_export():`
- ligne 532 — `def _render_environment_variable_settings():`
- ligne 629 — `def _render_notifications_settings():`
- ligne 761 — `def _check_import(name: str) -> str:`
- ligne 769 — `def render():`
## `ihm/pages/supervision_ops.py`

- ligne 124 — `def _render_watcher_runtime_observability(*, account_id: str | None) -> None:`
- ligne 182 — `def _render_windows_runtime_observability(*, account_id: str | None) -> None:`
- ligne 215 — `def _render_windows_integration_panel(*, snapshot: dict[str, object]) -> None:`
- ligne 231 — `def _render_coverage_artifact_panel(*, snapshot: dict[str, object]) -> None:`
- ligne 252 — `def _restart_button_label(control_state: dict[str, object]) -> str:`
- ligne 256 — `def _render_watcher_ops_controls(*, account_id: str | None, snapshot: dict[str, object]) -> None:`
- ligne 35 — `def _tail_text(content: str, max_lines: int = WATCHER_LOG_TAIL_LINES) -> str:`
- ligne 42 — `def _render_log_block(title: str, content: str, *, key: str, expanded: bool = False) -> None:`
- ligne 465 — `def render() -> None:`
- ligne 55 — `def _render_selected_watcher_run(record: dict[str, object] | None, *, run_id: str, log_filter: str) -> None:`
- ligne 93 — `def _render_selected_windows_log_source(log_sources_df, *, source_name: str) -> None:`
## `ihm/pages/tax_compliance.py`

- ligne 25 — `def render() -> None:`
## `ihm/pages/weights_calibration_runs.py`

- ligne 137 — `def _build_drift_metrics(df: pd.DataFrame) -> dict[str, object]:`
- ligne 16 — `def _parse_json_payload(value: object) -> dict[str, object] | list[object]:`
- ligne 166 — `def _build_drift_chart_frames(`
- ligne 273 — `def render() -> None:`
- ligne 35 — `def _build_candidates_frame(value: object) -> pd.DataFrame:`
- ligne 52 — `def _build_overview_metrics(df: pd.DataFrame) -> dict[str, object]:`
- ligne 83 — `def _prepare_drift_frames(`
## `ihm/services/account_defaults.py`

- ligne 14 — `class PipelineExecutionDefaults:`
- ligne 24 — `def _safe_float(value: object) -> float | None:`
- ligne 31 — `def _extract_equity(snapshot: dict[str, object]) -> float | None:`
- ligne 35 — `def _infer_account_type(snapshot: dict[str, object]) -> Literal["margin", "cash"] | None:`
- ligne 48 — `def get_pipeline_execution_defaults(account_id: str | None) -> PipelineExecutionDefaults | None:`
- ligne 59 — `def _get_pipeline_execution_defaults_impl(account_id: str | None) -> PipelineExecutionDefaults | None:`
## `ihm/services/alpaca_accounts.py`

- ligne 130 — `def get_live_portfolio_history(`
- ligne 15 — `def get_registered_accounts() -> list[BrokerAccount]:`
- ligne 19 — `def resolve_selected_account_id(preferred_account_id: str | None = None) -> str | None:`
- ligne 30 — `def build_account_label(account: BrokerAccount) -> str:`
- ligne 34 — `def _build_client(account_id: str) -> AlpacaTradingClient:`
- ligne 43 — `def get_live_account(account_id: str) -> dict[str, Any]:`
- ligne 48 — `def close_position_all(account_id: str, symbol: str) -> dict[str, Any]:`
- ligne 62 — `def get_live_positions(account_id: str) -> pd.DataFrame:`
- ligne 92 — `def get_live_orders(account_id: str, limit: int = _DEFAULT_ORDER_LIMIT) -> pd.DataFrame:`
## `ihm/services/alpha_scanner_threshold_presets.py`

- ligne 121 — `def _clamp_threshold(metric_key: str, value: float) -> float:`
- ligne 129 — `def get_alpha_scanner_threshold_preset(`
## `ihm/services/backtesting_registry.py`

- ligne 100 — `def _ensure_storage() -> None:`
- ligne 106 — `def _append_tail(target: list[str], line: str) -> None:`
- ligne 112 — `def _read_history_index() -> dict[str, dict[str, object]]:`
- ligne 120 — `def _write_history_index(payload: dict[str, dict[str, object]]) -> None:`
- ligne 125 — `def _persist_record(record: BacktestingRunRecord) -> None:`
- ligne 132 — `def _reader(stream: subprocess.PIPE | None, stream_name: str, events: queue.Queue[tuple[str, str]]) -> None:  # type: ignore[type-arg]`
- ligne 142 — `def _creation_flags() -> int:`
- ligne 148 — `def _kill_process_tree(process: subprocess.Popen[str]) -> None:`
- ligne 162 — `def _kill_process_tree_by_pid(pid: int) -> None:`
- ligne 180 — `def _parse_iso_datetime(value: object) -> datetime | None:`
- ligne 190 — `def _compute_elapsed_seconds(executed_at: object) -> float:`
- ligne 197 — `def _find_backtesting_run_dir(run_id: str, run_kind: str | None = None) -> Path | None:`
- ligne 213 — `def _find_active_backtesting_lock(run_id: str | None = None) -> dict[str, object] | None:`
- ligne 225 — `def _build_recovered_snapshot_from_lock(payload: dict[str, object]) -> dict[str, object]:`
- ligne 269 — `def _with_updates(record: BacktestingRunRecord, **updates: object) -> BacktestingRunRecord:`
- ligne 275 — `def _drain_events(managed: _ManagedRun) -> bool:`
- ligne 309 — `def _finalize_if_needed(managed: _ManagedRun) -> BacktestingRunRecord:`
- ligne 370 — `def _tail_text(lines: list[str]) -> str:`
- ligne 374 — `def _read_text_tail(path: Path, max_lines: int) -> str:`
- ligne 395 — `def _run_dir_for(run_kind: BacktestingCommandKind, run_id: str) -> Path:`
- ligne 399 — `def _resolve_screener_artifacts_dir(`
- ligne 414 — `def _ensure_db_ready_for_run(`
- ligne 425 — `def list_active_backtesting_runs_by_kind(run_kind: BacktestingCommandKind) -> list[dict[str, object]]:`
- ligne 430 — `def start_backtesting_run(`
- ligne 50 — `class BacktestingRunRecord:`
- ligne 547 — `def list_active_backtesting_runs() -> list[dict[str, object]]:`
- ligne 564 — `def poll_backtesting_run(run_id: str) -> dict[str, object] | None:`
- ligne 589 — `def stop_backtesting_run(run_id: str) -> bool:`
- ligne 631 — `def load_backtesting_history() -> list[dict[str, object]]:`
- ligne 637 — `def get_backtesting_run_record(run_id: str) -> dict[str, object] | None:`
- ligne 644 — `def _resolve_backtesting_log_path(`
- ligne 661 — `def backtesting_log_available(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> bool:`
- ligne 667 — `def read_backtesting_logs(`
- ligne 681 — `def build_backtesting_log_download_name(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:`
- ligne 691 — `def delete_backtesting_runs_except(`
- ligne 757 — `def _purge_run_artifacts(run_id: str, record: dict[str, object]) -> None:`
- ligne 76 — `class _ManagedRun:`
- ligne 785 — `def count_backtesting_runs_by_status() -> dict[str, int]:`
- ligne 794 — `def delete_backtesting_runs(`
## `ihm/services/backtesting_runner.py`

- ligne 156 — `class BackfillScoresHistoryOptions:`
- ligne 173 — `class DiagnoseScreenerOptions:`
- ligne 194 — `class RecommendScreenerOptions:`
- ligne 207 — `class CalibrateSentimentWeightsOptions:`
- ligne 221 — `class CalibrateConvictionWeightsOptions:`
- ligne 236 — `class WalkForwardConvictionOptions:`
- ligne 25 — `class BacktestRunOptions:`
- ligne 257 — `class WalkForwardSentimentOptions:`
- ligne 279 — `def build_backtesting_command(`
- ligne 680 — `def format_command_for_display(command: list[str]) -> str:`
## `ihm/services/compliance_loader.py`

- ligne 111 — `def load_coverage_status() -> dict[str, Any]:`
- ligne 120 — `def load_mutation_status() -> dict[str, Any]:`
- ligne 138 — `def load_tlaps_status() -> dict[str, Any]:`
- ligne 152 — `def load_fuzz_status() -> dict[str, Any]:`
- ligne 166 — `def load_sandbox_streak() -> dict[str, Any]:`
- ligne 17 — `def _safe_read_json(path: Path) -> dict | None:`
- ligne 188 — `def load_full_snapshot() -> dict[str, Any]:`
- ligne 26 — `def _latest_subdir(root: Path) -> Path | None:`
- ligne 40 — `def load_audit_chain_status() -> dict[str, Any]:`
- ligne 68 — `def load_dr_drill_status() -> dict[str, Any]:`
- ligne 87 — `def load_cve_status() -> dict[str, Any]:`
## `ihm/services/db_admin.py`

- ligne 133 — `class DatabaseTableSnapshot:`
- ligne 140 — `class TableCatalogEntry:`
- ligne 149 — `class TablePurgeOperation:`
- ligne 157 — `class TablePurgePlan:`
- ligne 167 — `class TablePurgeResult:`
- ligne 173 — `def _normalize_table_name(value: str) -> str:`
- ligne 180 — `def discover_tables_from_sql_directory(sql_directory: Path = SQL_DIRECTORY) -> set[str]:`
- ligne 194 — `def _classify_table(table_name: str) -> str:`
- ligne 216 — `def load_database_table_snapshot(engine: Engine) -> DatabaseTableSnapshot:`
- ligne 261 — `def list_grouped_tables(snapshot: DatabaseTableSnapshot) -> dict[str, list[TableCatalogEntry]]:`
- ligne 282 — `def _build_dependency_maps(`
- ligne 297 — `def _topological_delete_order(`
- ligne 330 — `def build_table_purge_plan(`
- ligne 390 — `def execute_table_purge(engine: Engine, plan: TablePurgePlan) -> TablePurgeResult:`
## `ihm/services/db.py`

- ligne 106 — `def _build_database_url(*, host: str, name: str, user: str, password: str) -> str:`
- ligne 112 — `def _engine_options() -> dict[str, object]:`
- ligne 122 — `def _format_db_connection_error(`
- ligne 152 — `def validate_db_connection_config(`
- ligne 184 — `def _get_cached_engine(db_url: str) -> Engine:`
- ligne 188 — `def get_engine() -> Engine | None:`
- ligne 220 — `def db_available() -> bool:`
- ligne 224 — `def get_db_status() -> dict[str, str | bool | None]:`
- ligne 235 — `def _format_query_error(exc: Exception, query: str) -> str:`
- ligne 245 — `def safe_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:`
- ligne 263 — `def safe_scalar(query: str, params: dict[str, Any] | None = None) -> Any:`
- ligne 282 — `def safe_execute(query: str, params: dict[str, Any] | None = None) -> bool:`
- ligne 32 — `def _set_state(key: str, value: str | None) -> None:`
- ligne 39 — `def _set_last_db_error(message: str | None) -> None:`
- ligne 43 — `def _set_last_query_error(message: str | None) -> None:`
- ligne 47 — `def get_last_db_error() -> str | None:`
- ligne 51 — `def get_last_query_error() -> str | None:`
- ligne 55 — `def get_runtime_db_config() -> dict[str, str | None]:`
- ligne 81 — `def set_runtime_db_config(*, host: str, name: str, user: str, password: str) -> None:`
- ligne 90 — `def clear_runtime_db_config() -> None:`
- ligne 97 — `def reset_db_caches(*, clear_errors: bool = False) -> None:`
## `ihm/services/doc_links.py`

- ligne 32 — `class DocRefResolution:`
- ligne 62 — `def resolve_doc_ref(doc_ref: str | None) -> DocRefResolution | None:`
- ligne 95 — `def render_doc_ref_inline(st_module, doc_ref: str | None, *, key_suffix: str = "") -> None:`
## `ihm/services/email_notifier.py`

- ligne 117 — `def send_notification(`
- ligne 57 — `def _is_enabled() -> bool:`
- ligne 61 — `def _build_subject(event: str) -> str:`
- ligne 66 — `def _build_body(event: str, payload: dict[str, Any], *, ts: str) -> str:`
- ligne 77 — `def _send_smtp(subject: str, body: str) -> None:`
## `ihm/services/fractional_trading_preferences.py`

- ligne 17 — `def _ensure_storage() -> None:`
- ligne 22 — `class FractionalTradingPreferences:`
- ligne 36 — `def load_persisted_fractional_trading_preferences() -> FractionalTradingPreferences:`
- ligne 52 — `def save_persisted_fractional_trading_preferences(`
## `ihm/services/help_loader.py`

- ligne 37 — `class HelpYamlError(RuntimeError):`
- ligne 41 — `def _read_yaml(path: pathlib.Path) -> dict[str, Any]:`
- ligne 54 — `def _validate_entry(page: str, key: str, entry: Any) -> dict[str, Any] | None:`
- ligne 67 — `def load_help(page: str) -> Mapping[str, Any]:`
- ligne 93 — `def reset_cache() -> None:`
- ligne 98 — `def help_dir() -> pathlib.Path:`
## `ihm/services/market_data_provider.py`

- ligne 30 — `def get_bars_provider(config_path: Path | str | None = None) -> str:`
- ligne 50 — `def set_bars_provider(provider: str, config_path: Path | str | None = None) -> str:`
## `ihm/services/ml_artifacts.py`

- ligne 103 — `def _build_routes_dataframe(config_data: dict[str, Any]) -> pd.DataFrame:`
- ligne 136 — `def _build_ranking_dataframe(metrics_data: dict[str, Any]) -> pd.DataFrame:`
- ligne 145 — `def _build_governance_thresholds_summary(config_data: dict[str, Any], metrics_data: dict[str, Any]) -> dict[str, Any]:`
- ligne 16 — `def get_model_artifacts_dir(artifacts_dir: Path | None = None) -> Path:`
- ligne 169 — `def _load_optional_artifact_json(path: Path) -> dict[str, Any]:`
- ligne 174 — `def load_ml_artifact_report(symbol: str, artifacts_dir: Path | None = None) -> dict[str, Any]:`
- ligne 20 — `def _symbol_sort_key(symbol: str) -> tuple[bool, str]:`
- ligne 24 — `def list_ml_artifact_batches(artifacts_dir: Path | None = None) -> list[str]:`
- ligne 42 — `def list_ml_artifact_symbols(artifacts_dir: Path | None = None) -> list[str]:`
- ligne 55 — `def _read_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:`
- ligne 70 — `def _coerce_path(value: Any) -> Path | None:`
- ligne 78 — `def _path_exists(value: Any) -> bool:`
- ligne 83 — `def _route_health(model_name: str, route: dict[str, Any]) -> tuple[str, list[str], dict[str, bool]]:`
## `ihm/services/ml_reset.py`

- ligne 312 — `def build_reset_explanation() -> str:`
- ligne 75 — `def _active_runs_for_dir(rel: str) -> list[dict[str, object]]:`
- ligne 88 — `def reset_ml_data(`
## `ihm/services/navigation.py`

- ligne 177 — `def get_navigation_pages() -> tuple[NavigationPage, ...]:`
- ligne 181 — `def get_navigation_page_labels() -> list[str]:`
- ligne 185 — `def get_navigation_page_mapping() -> dict[str, str]:`
- ligne 189 — `def get_navigation_page_imports() -> dict[str, str]:`
- ligne 193 — `def build_primary_navigation_caption() -> str:`
- ligne 200 — `def build_support_navigation_caption() -> str:`
- ligne 208 — `def build_section_navigation_caption() -> str:`
- ligne 26 — `class NavigationPage:`
- ligne 36 — `class NavigationSection:`
- ligne 91 — `def _get_page(key: str) -> NavigationPage:`
- ligne 98 — `def get_navigation_sections() -> tuple[NavigationSection, ...]:`
## `ihm/services/notifications_preferences.py`

- ligne 102 — `def load_persisted_notification_preferences() -> NotificationPreferences:`
- ligne 128 — `def save_persisted_notification_preferences(prefs: NotificationPreferences) -> NotificationPreferences:`
- ligne 30 — `def _ensure_storage() -> None:`
- ligne 35 — `class NotificationPreferences:`
- ligne 53 — `def is_valid_email(value: str) -> bool:`
- ligne 57 — `def parse_recipients(raw: str | Iterable[str] | None) -> list[str]:`
- ligne 85 — `def format_recipients(recipients: Iterable[str]) -> str:`
- ligne 89 — `def _normalize_notify_on(raw: object) -> list[str]:`
## `ihm/services/notifications.py`

- ligne 128 — `def _read_log_tail(path: str | os.PathLike[str] | None, max_lines: int = LOG_TAIL_LINES) -> str:`
- ligne 145 — `def collect_failed_step_context(record: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]:`
- ligne 214 — `def _format_duration(seconds: object) -> str:`
- ligne 230 — `def build_workflow_email(`
- ligne 344 — `def get_smtp_test_failure_log_path() -> Path:`
- ligne 348 — `def read_smtp_test_failure_log() -> str:`
- ligne 358 — `def clear_smtp_test_failure_log() -> None:`
- ligne 366 — `def _write_smtp_test_failure_log(`
- ligne 403 — `def _send_email_or_raise(message: EmailMessage, smtp_config: SmtpConfig) -> None:`
- ligne 426 — `def _detect_default_smtp_ca_file() -> str | None:`
- ligne 437 — `def _resolve_smtp_ca_file(smtp_config: SmtpConfig) -> str | None:`
- ligne 444 — `def _build_smtp_ssl_context(smtp_config: SmtpConfig) -> ssl.SSLContext:`
- ligne 453 — `def send_email(message: EmailMessage, smtp_config: SmtpConfig) -> bool:`
- ligne 466 — `def _flag_path_for_record(record: Mapping[str, Any]) -> Path | None:`
- ligne 476 — `def notify_run_finished(`
- ligne 54 — `class SmtpConfig:`
- ligne 541 — `def send_test_email(`
- ligne 69 — `def _truthy(value: object) -> bool:`
- ligne 73 — `def load_smtp_config() -> SmtpConfig:`
## `ihm/services/ops_runner.py`

- ligne 240 — `def _python(*tail: str) -> list[str]:`
- ligne 244 — `def _script(script_relpath: str, *tail: str) -> list[str]:`
- ligne 248 — `def _module(module_name: str, *tail: str) -> list[str]:`
- ligne 252 — `def build_ops_command(key: OpsCommandKey, **kwargs: Any) -> list[str]:`
- ligne 467 — `def start_ops_command(`
- ligne 498 — `def list_active_ops_runs(key: OpsCommandKey | None = None) -> list[dict[str, object]]:`
- ligne 68 — `class OpsCommandSpec:`
## `ihm/services/ops_supervision.py`

- ligne 114 — `def build_latest_runs_dataframe(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> pd.DataFrame:`
- ligne 148 — `def build_active_runs_dataframe(`
- ligne 175 — `def build_run_lineage_dataframe(active_runs_df: pd.DataFrame) -> pd.DataFrame:`
- ligne 208 — `def build_coverage_artifact_health(payload: Mapping[str, object] | None) -> dict[str, object]:`
- ligne 270 — `def load_coverage_artifact_health(coverage_path: Path | None = None) -> dict[str, object]:`
- ligne 285 — `def build_watcher_history_dataframe(records: Iterable[Mapping[str, object]]) -> pd.DataFrame:`
- ligne 313 — `def build_windows_integration_dataframe(*, account_id: str | None = None) -> pd.DataFrame:`
- ligne 317 — `def build_windows_runtime_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:`
- ligne 366 — `def build_windows_log_sources_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:`
- ligne 371 — `def build_windows_bridge_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:`
- ligne 396 — `def build_ops_alerts(`
- ligne 43 — `def _status_upper(value: object) -> str:`
- ligne 47 — `def _severity_rank(level: str) -> int:`
- ligne 482 — `def build_watcher_control_state(`
- ligne 51 — `def _iter_records(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> list[dict[str, object]]:`
- ligne 523 — `def build_ops_supervision_snapshot(`
- ligne 57 — `def build_service_health_dataframe(`
## `ihm/services/orphan_adoption_service.py`

- ligne 20 — `def adopt_after_close(`
## `ihm/services/pipeline_lock.py`

- ligne 135 — `def _parse_lock_datetime(value: object) -> datetime | None:`
- ligne 146 — `class LockHandle:`
- ligne 156 — `class PipelineLockBusy(RuntimeError):`
- ligne 168 — `def _read_lock(path: Path) -> dict[str, object] | None:`
- ligne 178 — `def _is_lock_active(payload: dict[str, object] | None) -> bool:`
- ligne 227 — `def list_active_locks() -> list[dict[str, object]]:`
- ligne 246 — `def acquire_lock(`
- ligne 308 — `def release_lock(handle: LockHandle | None) -> None:`
- ligne 329 — `def rebind_lock_pid(handle: LockHandle | None, *, pid: int) -> LockHandle | None:`
- ligne 33 — `def _default_locks_dir() -> Path:`
- ligne 52 — `def set_locks_dir_for_tests(path: Path | None) -> None:`
- ligne 62 — `def _locks_dir() -> Path:`
- ligne 66 — `def _lock_path(scope: LockScope) -> Path:`
- ligne 72 — `def _is_pid_alive(pid: int) -> bool:`
- ligne 93 — `def _get_process_started_at(pid: int) -> datetime | None:`
## `ihm/services/pipeline_ml_defaults.py`

- ligne 186 — `def is_catboost_available() -> bool:`
## `ihm/services/pipeline_runner.py`

- ligne 1003 — `def _normalize_optional_symbol(value: str | None) -> str | None:`
- ligne 1008 — `def _normalize_symbol_list(value: str | None) -> str | None:`
- ligne 1013 — `def _with_default_sentiment_pending_max_batches(`
- ligne 1031 — `def _build_powershell_file_command(script_path: Path, arguments: list[str] | None = None) -> list[str]:`
- ligne 1043 — `def _extend_event_sentiment_cli_common_args(`
- ligne 1098 — `def _extend_event_sentiment_runtime_args(`
- ligne 1133 — `def _extend_event_sentiment_scope_args(`
- ligne 1148 — `def _extend_relevance_backfill_scope_args(`
- ligne 1169 — `def _build_sentiment_standard_command(`
- ligne 1205 — `def _build_sentiment_relevance_backfill_command(`
- ligne 1237 — `def _build_sentiment_history_backfill_command(`
- ligne 1262 — `def _build_sentiment_contextual_command(`
- ligne 1320 — `def _build_import_news_command(`
- ligne 1363 — `def _extend_event_sentiment_powershell_args(`
- ligne 1443 — `def _resolve_event_sentiment_scoring_mode(options: PipelineLaunchOptions) -> SentimentScoringMode:`
- ligne 1453 — `def _extend_import_news_cli_args(`
- ligne 1473 — `def _extend_import_news_powershell_args(`
- ligne 1493 — `def _extend_event_sentiment_symbol_scope_args(`
- ligne 1509 — `def _extend_relevance_backfill_powershell_args(`
- ligne 1553 — `def _build_import_news_pending_loop_command(`
- ligne 1595 — `def is_gpu_available() -> bool:`
- ligne 1604 — `def _build_chained_ps_commands(`
- ligne 1650 — `def build_pipeline_command(step_key: str, options: PipelineLaunchOptions) -> list[str]:`
- ligne 173 — `def _resolve_bars_provider_for_ihm() -> str:`
- ligne 187 — `def _resolve_screener_custom_universe_file_from_config() -> str | None:`
- ligne 2627 — `def format_command_for_display(command: list[str]) -> str:`
- ligne 2631 — `def build_subprocess_env(`
- ligne 2663 — `def _build_live_snapshot(`
- ligne 2690 — `def _stream_subprocess(`
- ligne 2832 — `def run_pipeline_step(`
- ligne 341 — `class PipelineLaunchOptions:`
- ligne 673 — `class PipelineStepDefinition:`
- ligne 685 — `def parse_pipeline_step_number(step_num: str) -> int | None:`
- ligne 698 — `def is_canonical_pipeline_step_number(step_num: str, *, min_step: int = 1, max_step: int = 12) -> bool:`
- ligne 708 — `def is_workflow_core_step_number(step_num: str, *, min_step: int = 1, max_step: int = 12) -> bool:`
- ligne 716 — `class PipelineRunResult:`
- ligne 734 — `class PipelineLiveSnapshot:`
- ligne 922 — `def get_pipeline_steps() -> tuple[PipelineStepDefinition, ...]:`
- ligne 926 — `def resolve_step_display_name(step: PipelineStepDefinition) -> str:`
- ligne 938 — `def get_pipeline_workflow_steps(`
- ligne 979 — `def get_pipeline_auxiliary_steps() -> tuple[PipelineStepDefinition, ...]:`
- ligne 983 — `def _normalize_trade_date(value: str | None) -> str | None:`
- ligne 988 — `def _normalize_run_id(value: str | None) -> str | None:`
- ligne 993 — `def _normalize_optional_date(value: str | None) -> str | None:`
- ligne 998 — `def _normalize_symbol(value: str | None, default: str) -> str:`
## `ihm/services/process_registry.py`

- ligne 1001 — `def _should_override_failed_status(record: PipelineRunRecord, returncode: int | None) -> bool:`
- ligne 1005 — `def _drain_events(managed: _ManagedRun) -> bool:`
- ligne 1072 — `def _finalize_if_needed(managed: _ManagedRun) -> PipelineRunRecord:`
- ligne 1160 — `def _tail_text(lines: list[str]) -> str:`
- ligne 1164 — `def _workflow_elapsed_seconds(managed: _ManagedWorkflow) -> float:`
- ligne 1171 — `def _count_lines(text: str) -> int:`
- ligne 1175 — `def _append_text(path_value: str, content: str) -> None:`
- ligne 1184 — `def _append_bounded_text(path_value: str, content: str, *, stream: Literal["stdout", "stderr", "all"]) -> str:`
- ligne 1193 — `def _read_new_text(path_value: str, offset: int) -> tuple[str, int]:`
- ligne 1209 — `def _prefix_chunk(content: str, prefix: str) -> str:`
- ligne 1215 — `def _append_workflow_chunk(managed: _ManagedWorkflow, stream: Literal["stdout", "stderr"], content: str, *, prefix: str) -> None:`
- ligne 1238 — `def _append_workflow_event(managed: _ManagedWorkflow, message: str, *, is_error: bool = False) -> None:`
- ligne 1248 — `def _update_workflow_record(managed: _ManagedWorkflow, **updates: object) -> PipelineRunRecord:`
- ligne 1255 — `def _finalize_workflow_record(`
- ligne 128 — `class _ManagedRun:`
- ligne 1281 — `def _sync_child_logs_to_workflow(`
- ligne 1299 — `def _run_pipeline_workflow(`
- ligne 1464 — `def _poll_workflow_run(run_id: str, managed: _ManagedWorkflow) -> dict[str, object]:`
- ligne 147 — `class _ManagedWorkflow:`
- ligne 1488 — `def _run_dir_for(step_key: str, run_id: str) -> Path:`
- ligne 1492 — `def _filesystem_safe_path_component(value: str) -> str:`
- ligne 1505 — `def start_managed_run(`
- ligne 1583 — `def start_pipeline_run(`
- ligne 163 — `def _dispatch_finished_notification(record: PipelineRunRecord) -> None:`
- ligne 1642 — `def start_pipeline_workflow(`
- ligne 178 — `def _resolve_workflow_steps(`
- ligne 1825 — `def list_active_pipeline_runs() -> list[dict[str, object]]:`
- ligne 1839 — `def poll_pipeline_run(run_id: str) -> dict[str, object] | None:`
- ligne 1866 — `def stop_pipeline_run(run_id: str) -> bool:`
- ligne 1890 — `def load_pipeline_history() -> list[dict[str, object]]:`
- ligne 1930 — `def get_pipeline_run_record(run_id: str) -> dict[str, object] | None:`
- ligne 1950 — `def _resolve_pipeline_log_path(`
- ligne 1968 — `def pipeline_log_available(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> bool:`
- ligne 1974 — `def read_pipeline_logs(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:`
- ligne 198 — `def _format_workflow_core_step_ranges(steps: tuple[PipelineStepDefinition, ...]) -> str:`
- ligne 1982 — `def build_log_download_name(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:`
- ligne 1992 — `def _retention_days() -> int:`
- ligne 2004 — `def rotate_pipeline_artifacts(retention_days: int | None = None) -> dict[str, int]:`
- ligne 2059 — `def _atexit_kill_all_children() -> None:`
- ligne 2085 — `def _ensure_lifecycle_hooks() -> None:`
- ligne 237 — `def _workflow_scope_label(`
- ligne 263 — `def _workflow_step_label(`
- ligne 291 — `def _workflow_command_display(`
- ligne 320 — `def _ensure_storage() -> None:`
- ligne 326 — `def _append_tail(target: list[str], line: str) -> None:`
- ligne 332 — `def _read_history_index() -> dict[str, dict[str, object]]:`
- ligne 340 — `def _write_history_index(payload: dict[str, dict[str, object]]) -> None:`
- ligne 345 — `def _persist_record(record: PipelineRunRecord) -> None:`
- ligne 353 — `def _record_artifact_path_from_record(record: dict[str, object]) -> Path:`
- ligne 360 — `def _write_record_artifact(record: dict[str, object]) -> None:`
- ligne 369 — `def _load_record_artifact(run_dir: Path) -> dict[str, object] | None:`
- ligne 380 — `def _parse_run_id_datetime(run_id: str, fallback_path: Path | None = None) -> str:`
- ligne 395 — `def _file_line_count(path: Path) -> int:`
- ligne 405 — `def _safe_read_text(path: Path) -> str:`
- ligne 414 — `def _read_positive_int_env(name: str, default: int) -> int:`
- ligne 425 — `def _run_log_max_bytes(stream: Literal["stdout", "stderr", "all"]) -> int:`
- ligne 431 — `def _run_log_max_line_chars() -> int:`
- ligne 435 — `def _truncate_log_line(line: str, max_chars: int) -> str:`
- ligne 451 — `def _sanitize_log_chunk(content: str) -> str:`
- ligne 458 — `def _trim_file_to_max_bytes(path: Path, max_bytes: int) -> None:`
- ligne 482 — `def _infer_finished_at(run_dir: Path) -> str | None:`
- ligne 497 — `def _recover_workflow_run_from_directory(run_dir: Path) -> tuple[dict[str, object] | None, dict[str, dict[str, object]]]:`
- ligne 604 — `def _recover_step_run_from_directory(`
- ligne 658 — `def _recover_history_index_entries(existing_index: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:`
- ligne 692 — `def _normalize_inactive_scheduled_workflow_record(`
- ligne 719 — `def _infer_finished_at_from_record(record: dict[str, object]) -> str:`
- ligne 732 — `def _normalize_inactive_orphan_active_record(`
- ligne 770 — `def _normalize_inactive_record(`
- ligne 789 — `def _reader(stream: subprocess.PIPE | None, stream_name: str, events: queue.Queue[tuple[str, str]]) -> None:  # type: ignore[type-arg]`
- ligne 799 — `def _creation_flags() -> int:`
- ligne 805 — `def _kill_process_tree(process: subprocess.Popen[str]) -> None:`
- ligne 819 — `def _with_updates(record: PipelineRunRecord, **updates: object) -> PipelineRunRecord:`
- ligne 825 — `def _extract_run_summary(line: str) -> dict[str, object] | None:`
- ligne 83 — `class PipelineRunRecord:`
- ligne 839 — `def _summary_int(summary: dict[str, object], key: str) -> int:`
- ligne 847 — `def _summary_float(summary: dict[str, object], key: str) -> float | None:`
- ligne 855 — `def _derive_watchdog_payload(record: PipelineRunRecord) -> dict[str, object]:`
- ligne 912 — `def _apply_watchdog_payload(record: PipelineRunRecord) -> PipelineRunRecord:`
- ligne 918 — `def _infer_ml_run_summary_from_logs(record: PipelineRunRecord) -> dict[str, object] | None:`
- ligne 974 — `def _override_failed_status_run_summary(record: PipelineRunRecord, returncode: int | None) -> dict[str, object] | None:`
## `ihm/services/queries.py`

- ligne 1008 — `def get_stock_scores() -> pd.DataFrame:`
- ligne 101 — `def _coerce_int(value: object) -> int:`
- ligne 1019 — `def get_risk_run_ids() -> list[str]:`
- ligne 1025 — `def get_risk_decisions(run_id: str | None = None) -> pd.DataFrame:`
- ligne 1036 — `def get_portfolio_targets(run_id: str | None = None) -> pd.DataFrame:`
- ligne 1051 — `def get_shadow_drift_runs(live_run_id: str | None = None, limit: int = 20) -> pd.DataFrame:`
- ligne 1080 — `def get_weights_calibration_runs(`
- ligne 110 — `def _safe_scalar_with_error(query: str, params: dict[str, object] | None = None) -> tuple[object, str | None]:`
- ligne 115 — `def _parse_json_object(value: object) -> dict[str, object]:`
- ligne 1172 — `def get_weights_calibration_run_ids(`
- ligne 1196 — `def set_weights_calibration_live_eligibility(`
- ligne 1240 — `def get_weights_calibration_segment_drifts(`
- ligne 127 — `def _get_table_columns(table_name: str) -> set[str]:`
- ligne 1304 — `def get_execution_live_guard(account_id: str | None = None) -> dict[str, object]:`
- ligne 1333 — `def get_execution_reconciliation_j1_runs(`
- ligne 1361 — `def get_execution_reconciliation_j1_diff_rows(`
- ligne 138 — `def _build_stock_scores_query(available_columns: set[str]) -> str:`
- ligne 1381 — `def get_execution_tca_aggregates(`
- ligne 1415 — `def get_execution_runs(limit: int = 20, account_id: str | None = None) -> pd.DataFrame:`
- ligne 1432 — `def get_execution_events(exec_run_id: str | None = None) -> pd.DataFrame:`
- ligne 1442 — `def get_execution_orders(`
- ligne 1510 — `def get_execution_account_constraints(exec_run_id: str) -> dict[str, object]:`
- ligne 1557 — `def get_broker_positions(account_id: str | None = None) -> pd.DataFrame:`
- ligne 1575 — `def get_execution_fills(`
- ligne 1623 — `def get_execution_targets_snapshot(exec_run_id: str) -> pd.DataFrame:`
- ligne 164 — `def _attach_selection_explainability_payloads(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 1670 — `def get_broker_account_snapshots_history(account_id: str, limit: int = 200) -> pd.DataFrame:`
- ligne 1686 — `def get_execution_positions(`
- ligne 1733 — `def get_execution_position_lots(`
- ligne 175 — `def get_alpha_scanner_dependency_thresholds() -> dict[str, dict[str, float]]:`
- ligne 1783 — `def get_execution_reconciliation_results(`
- ligne 179 — `def _build_quotes_dependency_payload(`
- ligne 1855 — `def get_ca_events_summary() -> pd.DataFrame:`
- ligne 1863 — `def get_ca_events(limit: int = 100) -> pd.DataFrame:`
- ligne 1868 — `def get_ca_applications(limit: int = 50) -> pd.DataFrame:`
- ligne 1873 — `def get_total_dividends() -> float:`
- ligne 1882 — `def _normalize_filter_values(values: list[str] | None) -> list[str]:`
- ligne 1891 — `def _append_in_clause(`
- ligne 1911 — `def get_run_business_summaries(`
- ligne 1957 — `def get_latest_run_business_summary(`
- ligne 1978 — `def get_latest_execution_protection_watch_service_summary(`
- ligne 2000 — `def get_ops_service_summaries(`
- ligne 2014 — `def get_ops_latest_critical_summaries(`
- ligne 2032 — `def get_training_runs(limit: int = 20) -> pd.DataFrame:`
- ligne 2037 — `def get_completed_ml_training_batches(limit: int = 100) -> pd.DataFrame:`
- ligne 2066 — `def get_oracle_prediction_batches(limit: int = 50) -> pd.DataFrame:`
- ligne 2088 — `def get_ml_batch_comments(batch_ids: list[str]) -> dict[str, str]:`
- ligne 2119 — `def get_model_metrics() -> pd.DataFrame:`
- ligne 2124 — `def get_model_governance(`
- ligne 2153 — `def get_prediction_symbols(limit: int = 200) -> list[str]:`
- ligne 2159 — `def get_predictions(`
- ligne 2183 — `def get_prediction_governance_audit(`
- ligne 2269 — `def get_stale_market_cap_stats(*, cutoff_days: int = 45) -> dict[str, int | float]:`
- ligne 2321 — `def get_backfill_completeness_diagnostic(`
- ligne 237 — `def _build_earnings_dependency_payload(`
- ligne 2522 — `def get_daily_pnl_data() -> dict[str, object]:`
- ligne 2573 — `def get_batch_diagnostics_summary() -> dict[str, object]:`
- ligne 296 — `def get_alpha_scanner_dependency_diagnostic(*, today: date | None = None) -> dict[str, object]:`
- ligne 395 — `def get_selection_count() -> int:`
- ligne 400 — `def resolve_latest_selection_snapshot_date(trade_date: str | date | None) -> date | None:`
- ligne 437 — `def get_backtesting_pit_history_diagnostic(`
- ligne 525 — `def _serialize_backtesting_ml_missing_rows(df: pd.DataFrame) -> list[dict[str, object]]:`
- ligne 538 — `def _serialize_backtesting_ml_missing_days(df: pd.DataFrame) -> list[dict[str, object]]:`
- ligne 557 — `def get_live_ml_first_diagnostic() -> dict[str, object]:`
- ligne 618 — `def get_backtesting_ml_coverage_diagnostic(`
- ligne 79 — `def _coerce_date(value: object) -> date | None:`
- ligne 95 — `def _coverage_pct(covered_symbols: int, eligible_symbols: int) -> float:`
- ligne 970 — `def get_stock_bars_daily_symbol_count() -> int:`
- ligne 978 — `def get_top_selected_symbols(n: int = 10) -> pd.DataFrame:`
- ligne 989 — `def get_latest_risk_run_id() -> str | None:`
- ligne 995 — `def get_latest_exec_run() -> pd.DataFrame:`
## `ihm/services/run_summary.py`

- ligne 1012 — `def build_ordered_pipeline_step_scopes(`
- ligne 1033 — `def build_pipeline_flow_caption(*, include_auxiliary: bool = True, max_main_step: int | None = None) -> str:`
- ligne 1041 — `def _is_number(value: Any) -> bool:`
- ligne 1045 — `def _to_float(value: object) -> float | None:`
- ligne 1051 — `def _to_int(value: object) -> int:`
- ligne 1059 — `def _coerce_float(value: object) -> float:`
- ligne 1067 — `def _merge_nested_counts(target: dict[str, object], key: str, value: Mapping[str, object]) -> None:`
- ligne 1077 — `def _merge_scalar_metric(target: dict[str, object], key: str, value: int | float) -> None:`
- ligne 1098 — `def _metric_rule(key: str, value: object) -> str:`
- ligne 1116 — `def _infer_weight_key(summary: Mapping[str, object], key: str) -> str | None:`
- ligne 1144 — `def aggregate_workflow_run_summary(child_runs: Iterable[Mapping[str, object]]) -> dict[str, object]:`
- ligne 230 — `def _get_screener_persistence_status(summary: Mapping[str, object]) -> str:`
- ligne 234 — `def _get_screener_persistence_label(summary: Mapping[str, object]) -> str | None:`
- ligne 241 — `def _get_screener_chunk_error_samples(summary: Mapping[str, object]) -> list[Mapping[str, object]]:`
- ligne 248 — `def _format_alpha_scanner_selection_detail_line(selection: Mapping[str, object]) -> str | None:`
- ligne 284 — `def _format_alpha_scanner_preselection_detail_line(summary: Mapping[str, object]) -> str | None:`
- ligne 327 — `def _format_alpha_scanner_ablation_detail_lines(summary: Mapping[str, object]) -> list[str]:`
- ligne 382 — `def _format_selector_mode_counts_line(label: str, payload: object) -> str | None:`
- ligne 397 — `def _normalize_fallback_journal_entries(payload: object) -> list[Mapping[str, object]]:`
- ligne 403 — `def _format_empirical_calibration_fallback_lines(payload: Mapping[str, object]) -> list[str]:`
- ligne 453 — `def get_run_summary(record: Mapping[str, object] | None) -> dict[str, object]:`
- ligne 460 — `def _step_key(record: Mapping[str, object] | None) -> str:`
- ligne 466 — `def get_stooq_cross_check_status(record: Mapping[str, object] | None) -> str | None:`
- ligne 484 — `def get_run_summary_metric_items(record: Mapping[str, object] | None) -> list[tuple[str, object]]:`
- ligne 515 — `def build_run_summary_caption(record: Mapping[str, object] | None) -> str:`
- ligne 522 — `def get_run_summary_detail_lines(record: Mapping[str, object] | None) -> list[str]:`
- ligne 968 — `def find_latest_run_with_summary(`
- ligne 985 — `def build_latest_run_summary_rows(`
## `ihm/services/sandbox_health_loader.py`

- ligne 14 — `def load_rollup(sandbox_dir: Path | str | None = None) -> dict[str, Any]:`
- ligne 26 — `def load_day(date_iso: str, sandbox_dir: Path | str | None = None) -> dict[str, Any]:`
## `ihm/services/screener_artifact_history.py`

- ligne 119 — `def resolve_selected_screener_artifacts_dir(`
- ligne 145 — `def format_screener_artifact_history_label(entry: dict[str, Any]) -> str:`
- ligne 159 — `def build_screener_artifact_history_rows(entries: list[dict[str, Any]]) -> list[dict[str, object]]:`
- ligne 19 — `def normalize_screener_artifacts_dir(artifacts_dir: Path | str | None = None) -> str:`
- ligne 23 — `def _artifacts_dir_label(artifacts_dir: str) -> str:`
- ligne 31 — `def _last_run_timestamp(run_record: dict[str, object]) -> str:`
- ligne 35 — `def _history_sort_key(entry: dict[str, Any]) -> tuple[str, str, str]:`
- ligne 43 — `def build_screener_history_entry(`
- ligne 80 — `def build_global_screener_artifact_history(`
## `ihm/services/screener_preferences.py`

- ligne 112 — `def save_persisted_alpha_scanner_dependency_thresholds(`
- ligne 136 — `def reset_persisted_alpha_scanner_dependency_thresholds() -> None:`
- ligne 17 — `def _ensure_storage() -> None:`
- ligne 21 — `def _normalize_optional_dir(artifacts_dir: Path | str | None) -> str | None:`
- ligne 30 — `def load_persisted_selected_screener_artifacts_dir() -> str | None:`
- ligne 43 — `def save_persisted_selected_screener_artifacts_dir(artifacts_dir: Path | str | None) -> str | None:`
- ligne 57 — `def _normalize_thresholds_payload(`
- ligne 82 — `def load_persisted_alpha_scanner_dependency_thresholds(`
- ligne 95 — `def load_persisted_alpha_scanner_dependency_preset_metadata() -> dict[str, str | None]:`
## `ihm/services/screener_recommendations.py`

- ligne 110 — `def _build_objective_leaders(report: dict[str, Any]) -> list[dict[str, Any]]:`
- ligne 137 — `def _read_json_file(path: Path) -> tuple[dict[str, Any], str | None]:`
- ligne 152 — `def _read_csv_file(path: Path) -> tuple[pd.DataFrame, str | None]:`
- ligne 161 — `def _coverage_label(metadata: dict[str, Any]) -> str:`
- ligne 171 — `def _format_updated_at(path: Path) -> str:`
- ligne 178 — `def _updated_at_iso(path: Path) -> str | None:`
- ligne 185 — `def _objective_order_key(objective: object) -> tuple[int, str]:`
- ligne 193 — `def _build_objective_rows_from_summary(summary_payload: dict[str, Any]) -> pd.DataFrame:`
- ligne 231 — `def _build_objective_rows_from_recommendations(recommendations: pd.DataFrame) -> pd.DataFrame:`
- ligne 284 — `def _build_leaderboard(recommendations: pd.DataFrame) -> pd.DataFrame:`
- ligne 319 — `def load_screener_recommendation_report(artifacts_dir: Path | str | None = None) -> dict[str, Any]:`
- ligne 37 — `def get_screener_artifacts_dir(artifacts_dir: Path | str | None = None) -> Path:`
- ligne 381 — `def build_screener_artifact_summary(artifacts_dir: Path | str | None = None) -> dict[str, Any]:`
- ligne 44 — `def _count_data_rows(path: Path) -> int | None:`
- ligne 442 — `def list_screener_csv_files(`
- ligne 458 — `def load_screener_csv_preview(`
- ligne 57 — `def _format_size_label(size_bytes: int) -> str:`
- ligne 65 — `def _build_file_snapshot(root: Path, *, key: str, filename: str, kind: str) -> dict[str, Any]:`
- ligne 82 — `def _coerce_scalar(value: object) -> Any:`
- ligne 93 — `def _extract_recommended_scenario(payload: dict[str, Any]) -> dict[str, Any] | None:`
## `ihm/services/security.py`

- ligne 25 — `def auth_token_required() -> bool:`
- ligne 30 — `def _expected_token() -> str:`
- ligne 34 — `def is_localhost_required() -> bool:`
- ligne 39 — `def _resolve_server_address() -> str:`
- ligne 46 — `def is_listening_on_localhost_only() -> bool:`
- ligne 62 — `def render_auth_gate() -> bool:`
- ligne 92 — `def render_security_banner() -> None:`
## `ihm/services/swing_score.py`

- ligne 114 — `def load_bars(symbols: list[str], benchmark: str = BENCHMARK_SYMBOL) -> pd.DataFrame:`
- ligne 129 — `def load_market_caps(symbols: list[str]) -> pd.DataFrame:`
- ligne 156 — `def _true_range(frame: pd.DataFrame) -> pd.Series:`
- ligne 168 — `def _beta_score(beta: float | None) -> float:`
- ligne 174 — `def _market_cap_fit_score(market_cap: float | None) -> float:`
- ligne 180 — `def _percentile_score(series: pd.Series) -> pd.Series:`
- ligne 185 — `def _symbol_metrics_from_group(`
- ligne 230 — `def build_swing_scores(`
- ligne 333 — `def compute_swing_scores(symbols: list[str]) -> tuple[pd.DataFrame, dict[str, object]]:`
- ligne 382 — `def _load_tradable_universe_history_union() -> list[str]:`
- ligne 394 — `def resolve_universe_symbols(symbol_source: str) -> list[str]:`
- ligne 80 — `def parse_symbols(text_content: str) -> list[str]:`
- ligne 96 — `def _load_bars_chunk(symbols: list[str]) -> pd.DataFrame:`
## `ihm/services/tax_data.py`

- ligne 17 — `class TaxLotRow:`
- ligne 28 — `def lot_to_row(lot: Lot) -> TaxLotRow:`
- ligne 39 — `def load_demo_lots() -> list[Lot]:`
- ligne 53 — `def filter_lots(`
- ligne 72 — `def compute_report(lots: Sequence[Lot]) -> WashSaleReport:`
- ligne 76 — `def lots_to_table(lots: Sequence[Lot], report: WashSaleReport) -> list[dict]:`
## `ihm/services/theme_manager.py`

- ligne 163 — `def apply_theme_chrome(st_module, theme: ThemeName) -> None:`
- ligne 173 — `def render_theme_toggle(st_module) -> ThemeName:`
- ligne 26 — `def get_current_theme(state: dict | None = None) -> ThemeName:`
- ligne 34 — `def set_theme(state: dict, theme: ThemeName) -> None:`
- ligne 38 — `def build_css(theme: ThemeName) -> str:`
## `ihm/services/varEnv.py`

- ligne 121 — `def set_env_registry(name, value):`
- ligne 30 — `def get_var_env() -> str:`
- ligne 37 — `def get_conf_var_env() -> list:`
- ligne 69 — `def set_var_env(csv_bytes: bytes, apply: bool = True) -> dict:`
- ligne 9 — `def get_var_env_streamlit() -> io.BytesIO:`
## `ihm/services/watcher_runtime.py`

- ligne 132 — `def list_active_watcher_runs(*, account_id: str | None = None) -> list[dict[str, object]]:`
- ligne 143 — `def list_watcher_run_history(*, account_id: str | None = None, limit: int = 50) -> list[dict[str, object]]:`
- ligne 156 — `def get_watcher_run_record(run_id: str) -> dict[str, object] | None:`
- ligne 165 — `def read_watcher_run_logs(run_id: str, *, stream: str = "all") -> str:`
- ligne 171 — `def build_watcher_log_download_name(run_id: str, *, stream: str = "all") -> str:`
- ligne 177 — `def build_windows_integration_rows(*, account_id: str | None = None) -> list[dict[str, str]]:`
- ligne 211 — `def get_active_local_watcher_service(*, account_id: str | None = None) -> dict[str, object] | None:`
- ligne 218 — `def get_active_watcher_once_run(*, account_id: str | None = None) -> dict[str, object] | None:`
- ligne 225 — `def launch_watcher_once(`
- ligne 266 — `def start_local_watcher_service(`
- ligne 313 — `def stop_local_watcher_service(run_id: str) -> bool:`
- ligne 325 — `def restart_local_watcher_service(`
- ligne 365 — `def serialize_local_watcher_control_state(*, account_id: str | None = None) -> dict[str, Any]:`
- ligne 389 — `def list_alpaca_account_ids() -> list[str]:`
- ligne 403 — `def _resolve_target_account_ids(account_id: str | None) -> list[str | None]:`
- ligne 416 — `def launch_watcher_once_for_all_accounts(`
- ligne 42 — `def _watcher_leader_lock_account(account_id: str | None = None) -> str:`
- ligne 446 — `def start_local_watcher_service_for_all_accounts(`
- ligne 46 — `def _force_release_local_watcher_leader_lock(account_id: str | None = None) -> None:`
- ligne 474 — `def serialize_all_accounts_watcher_control_state() -> dict[str, Any]:`
- ligne 62 — `def build_watcher_doc_reference() -> dict[str, str]:`
- ligne 71 — `def build_watcher_command(`
## `ihm/services/windows_watcher_bridge.py`

- ligne 110 — `def get_windows_watcher_status(`
- ligne 127 — `def list_windows_watcher_log_sources(payload: dict[str, Any] | None) -> list[dict[str, object]]:`
- ligne 152 — `def read_windows_log_source(path_value: str, *, max_bytes: int = MAX_IMPORTED_LOG_BYTES) -> str:`
- ligne 25 — `def _bridge_unavailable_payload(reason: str, *, script_key: str = "status") -> dict[str, Any]:`
- ligne 37 — `def run_allowed_bridge_script(`
## `ihm/theme/badges.py`

- ligne 23 — `def status_badge(label: str, level: str = "neutral") -> str:`
## `ihm/theme/icons.py`

- ligne 35 — `def get_icon(name: str, default: str = "•") -> str:`
## `ihm/theme/palette.py`

- ligne 35 — `def get_palette(theme: ThemeName = "light") -> dict[str, str]:`

