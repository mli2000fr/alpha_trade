# Inventaire API — ihm

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `ihm/__init__.py`

Source SHA-256 : `6f8316f4ea57d7d97e5161aa1b19c28361ce3ee436ad7c727d6918eb33bb7321`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `ihm/app.py`

Source SHA-256 : `8938638664f050ad7b9a63255532164bc4cc0b2749bd93545231b3c551e4786c`

- [_select_page](../../ihm/app.py) — ligne 78 : `def _select_page(label: str) -> None`
- [render](../../ihm/app.py) — ligne 230 : `def render() -> None`

## `ihm/components/__init__.py`

Source SHA-256 : `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `ihm/components/alpha_scanner_dependency.py`

Source SHA-256 : `59f80ae21d8eee58c39d5084c9bf5ad303ff2b6f9b8ec926ae64e6d780cf582d`

- [dependency_badge](../../ihm/components/alpha_scanner_dependency.py) — ligne 15 : `def dependency_badge(status: str, label: str) -> str`
- [get_dependency_payload](../../ihm/components/alpha_scanner_dependency.py) — ligne 21 : `def get_dependency_payload(diagnostic: DependencyDiagnostic | None, step_key: str) -> dict[str, object] | None`
- [format_dependency_latest_date](../../ihm/components/alpha_scanner_dependency.py) — ligne 31 : `def format_dependency_latest_date(value: object) -> str`
- [format_dependency_symbol_count](../../ihm/components/alpha_scanner_dependency.py) — ligne 36 : `def format_dependency_symbol_count(value: object) -> str`
- [build_alpha_scanner_dependency_rows](../../ihm/components/alpha_scanner_dependency.py) — ligne 43 : `def build_alpha_scanner_dependency_rows(diagnostic: DependencyDiagnostic | None) -> pd.DataFrame`
- [render_dependency_metrics](../../ihm/components/alpha_scanner_dependency.py) — ligne 68 : `def render_dependency_metrics(payload: dict[str, object]) -> None`
- [render_alpha_scanner_dependency_panel](../../ihm/components/alpha_scanner_dependency.py) — ligne 80 : `def render_alpha_scanner_dependency_panel(diagnostic: DependencyDiagnostic | None, *, title: str, expanded: bool=False, show_commands: bool=True) -> None`

## `ihm/components/db_controls.py`

Source SHA-256 : `c60a014bf216f32e099c78785af6d22793170e39b5f0020736c79a8510a83f8a`

- [render_db_connection_form](../../ihm/components/db_controls.py) — ligne 15 : `def render_db_connection_form(form_key: str, *, show_host_fields: bool=True) -> None`
- [render_db_unavailable](../../ihm/components/db_controls.py) — ligne 74 : `def render_db_unavailable(page_label: str, *, form_key: str) -> None`
- [render_query_diagnostic](../../ihm/components/db_controls.py) — ligne 80 : `def render_query_diagnostic(empty_message: str) -> bool`

## `ihm/components/help_tooltip.py`

Source SHA-256 : `c439b5f75b00da68d36ebd629032f7d9c5fdc941a78a39808ceaab971ee0618d`

- [_format_field](../../ihm/components/help_tooltip.py) — ligne 20 : `def _format_field(value: Any) -> str`
- [_help](../../ihm/components/help_tooltip.py) — ligne 26 : `def _help(page: str, key: str) -> str`
- [help_or_default](../../ihm/components/help_tooltip.py) — ligne 60 : `def help_or_default(page: str, key: str, default: str) -> str`

## `ihm/components/kpi_card.py`

Source SHA-256 : `ac22032a4a7d3ab222321ce8264100b6336ec91097367466b87ff525f03aabf1`

- [kpi_card](../../ihm/components/kpi_card.py) — ligne 9 : `def kpi_card(st_module, label: str, value: Any, delta: Any | None=None, help_key: str | None=None, page: str | None=None, level: str='neutral') -> None`

## `ihm/components/market_regime_banner.py`

Source SHA-256 : `9bfcd6c7d64b630f7000a5d0067c2ff1310edcccf0f6255d283a130e77cb140f`

- [load_latest_snapshot](../../ihm/components/market_regime_banner.py) — ligne 43 : `def load_latest_snapshot(directory: Path | None=None) -> dict[str, Any] | None`
- [render_market_regime_banner](../../ihm/components/market_regime_banner.py) — ligne 61 : `def render_market_regime_banner(*, snapshot: dict[str, Any] | None=None, compact: bool=True, show_link_hint: bool=True) -> dict[str, Any] | None`

## `ihm/components/metrics.py`

Source SHA-256 : `7f8dcbda11f647c98aa96fdc4fb6168c5cda17ef2b66af0a9bbb9dcf4169960f`

- [_to_float](../../ihm/components/metrics.py) — ligne 9 : `def _to_float(value: object, default: float=0.0) -> float`
- [to_int](../../ihm/components/metrics.py) — ligne 16 : `def to_int(value: object, default: int=0) -> int`
- [format_duration_hhmmss](../../ihm/components/metrics.py) — ligne 23 : `def format_duration_hhmmss(value: object) -> str`
- [metric_row](../../ihm/components/metrics.py) — ligne 35 : `def metric_row(metrics: list[tuple[str, str | int | float, str | None]]) -> None`

## `ihm/components/ops_command_panel.py`

Source SHA-256 : `c0a42d4c16edb8a4f3226c82affce4c9cdc87694760717b13b6a8b319bef889d`

- [_format_command](../../ihm/components/ops_command_panel.py) — ligne 35 : `def _format_command(command: list[str]) -> str`
- [render_ops_command_panel](../../ihm/components/ops_command_panel.py) — ligne 39 : `def render_ops_command_panel(key: OpsCommandKey, *, account_id: str | None=None, db_config: dict[str, str | None] | None=None, confirm_phrase: str | None=None, command_kwargs: dict[str, Any] | None=None, show_history: bool=True, history_limit: int=3) -> None`
- [_render_recent_runs](../../ihm/components/ops_command_panel.py) — ligne 151 : `def _render_recent_runs(key: OpsCommandKey, limit: int) -> None`

## `ihm/components/run_summary.py`

Source SHA-256 : `1a25ae474a610117fd9095fc1faf6a0326c55f6f733feff5e8cbcdbef0bad468`

- [_coerce_int](../../ihm/components/run_summary.py) — ligne 17 : `def _coerce_int(value: object) -> int`
- [_coerce_float](../../ihm/components/run_summary.py) — ligne 25 : `def _coerce_float(value: object) -> float`
- [_build_live_progress_text](../../ihm/components/run_summary.py) — ligne 33 : `def _build_live_progress_text(summary: Mapping[str, object]) -> str`
- [render_run_summary_block](../../ihm/components/run_summary.py) — ligne 63 : `def render_run_summary_block(record: Mapping[str, object] | None, *, title: str | None=None, max_metrics: int=6, heading_level: str='subheader', show_caption: bool=True) -> bool`
- [render_persistent_business_summary](../../ihm/components/run_summary.py) — ligne 114 : `def render_persistent_business_summary(record: Mapping[str, object] | None, *, title: str='🧭 Résumé métier persistant', max_metrics: int=6) -> bool`

## `ihm/components/screener_artifacts.py`

Source SHA-256 : `dc8ae44da6a837a67b049577022b2c13f2ebc5af30e5afd360776be7d4a8847c`

- [build_screener_artifact_history_dataframe](../../ihm/components/screener_artifacts.py) — ligne 20 : `def build_screener_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame`
- [render_shared_screener_artifact_selector](../../ihm/components/screener_artifacts.py) — ligne 24 : `def render_shared_screener_artifact_selector(*, selectbox_key: str, title: str, caption: str, empty_message: str, history_title: str) -> tuple[str, dict[str, object]]`

## `ihm/components/section_header.py`

Source SHA-256 : `e21b540f6b43375745fcbc824635c455e3ad34eb9b05f454b95d2997369f302d`

- [section_header](../../ihm/components/section_header.py) — ligne 7 : `def section_header(st_module, title: str, subtitle: str | None=None, help_key: str | None=None, page: str | None=None, icon: str | None=None) -> None`

## `ihm/components/status_badges.py`

Source SHA-256 : `0a547f36c711d867a019afe1a7516244ddee8ee6ae151a28387b525b3c58a43d`

- [badge](../../ihm/components/status_badges.py) — ligne 7 : `def badge(label: str, status: str='ok') -> str`
- [env_badge](../../ihm/components/status_badges.py) — ligne 13 : `def env_badge(var_name: str, value: str | None) -> str`
- [run_status_badge](../../ihm/components/status_badges.py) — ligne 20 : `def run_status_badge(status: str | None) -> str`
- [decision_badge](../../ihm/components/status_badges.py) — ligne 31 : `def decision_badge(decision: str) -> str`
- [classify_heartbeat_freshness](../../ihm/components/status_badges.py) — ligne 40 : `def classify_heartbeat_freshness(last_heartbeat_at: str | None, heartbeat_interval_seconds: float | int | None, *, service_status: str | None=None, now: datetime | None=None) -> tuple[str, str, int | None]`
- [heartbeat_badge](../../ihm/components/status_badges.py) — ligne 78 : `def heartbeat_badge(last_heartbeat_at: str | None, heartbeat_interval_seconds: float | int | None, *, service_status: str | None=None, now: datetime | None=None) -> str`

## `ihm/components/swing_score.py`

Source SHA-256 : `3898f024ee90c71a4ff632719f6405f2f7fc1dd07fa43e79c07355a38d51761e`

- [_read_uploaded_symbols](../../ihm/components/swing_score.py) — ligne 46 : `def _read_uploaded_symbols(uploaded) -> list[str]`
- [_cached_resolve_universe](../../ihm/components/swing_score.py) — ligne 59 : `def _cached_resolve_universe(symbol_source: str) -> list[str]`
- [_build_output_text](../../ihm/components/swing_score.py) — ligne 64 : `def _build_output_text(result: pd.DataFrame, top_n: int) -> str`
- [_render_result](../../ihm/components/swing_score.py) — ligne 69 : `def _render_result(result: pd.DataFrame, top_n: int, diagnostics: dict, source_symbols_count: int) -> None`
- [render_swing_score_block](../../ihm/components/swing_score.py) — ligne 95 : `def render_swing_score_block() -> None`

## `ihm/components/symbol_bars_dialog.py`

Source SHA-256 : `8f9f48967e32659e66fc6e45b0cd89651a2d0b2df1c3b7bd6a10411cc31147df`

- [_normalize_eodhd_payload](../../ihm/components/symbol_bars_dialog.py) — ligne 38 : `def _normalize_eodhd_payload(payload: list[dict[str, Any]]) -> pd.DataFrame`
- [_normalize_stooq_payload](../../ihm/components/symbol_bars_dialog.py) — ligne 51 : `def _normalize_stooq_payload(payload: list[dict[str, Any]]) -> pd.DataFrame`
- [_fetch_bars_eodhd](../../ihm/components/symbol_bars_dialog.py) — ligne 62 : `def _fetch_bars_eodhd(symbol: str, *, start: date, end: date) -> pd.DataFrame`
- [_fetch_bars_stooq](../../ihm/components/symbol_bars_dialog.py) — ligne 76 : `def _fetch_bars_stooq(symbol: str, *, start: date, end: date) -> pd.DataFrame`
- [load_symbol_bars](../../ihm/components/symbol_bars_dialog.py) — ligne 91 : `def load_symbol_bars(symbol: str, lookback_days: int=365) -> pd.DataFrame`
- [_render_dialog_body](../../ihm/components/symbol_bars_dialog.py) — ligne 108 : `def _render_dialog_body(symbol: str, default_lookback_days: int) -> None`
- [show_symbol_bars_dialog](../../ihm/components/symbol_bars_dialog.py) — ligne 167 : `def show_symbol_bars_dialog(symbol: str, lookback_days: int=365) -> None`

## `ihm/components/symbol_table.py`

Source SHA-256 : `9e7e301a8a56d7ce51fd3cdf896be5cfc0dad5c199e1e7dcfb47d9c4c013159f`

- [ActionSpec](../../ihm/components/symbol_table.py) — ligne 32 : `class ActionSpec`
- [_selected_row_index](../../ihm/components/symbol_table.py) — ligne 57 : `def _selected_row_index(table_key: str) -> int | None`
- [_resolve_symbol](../../ihm/components/symbol_table.py) — ligne 73 : `def _resolve_symbol(df: pd.DataFrame, row_index: int, symbol_col: str) -> str | None`
- [_render_action_bar](../../ihm/components/symbol_table.py) — ligne 85 : `def _render_action_bar(*, df: pd.DataFrame, row_index: int, symbol: str, table_key: str, extra_actions: list[ActionSpec], bars_lookback_days: int) -> None`
- [render_symbol_table](../../ihm/components/symbol_table.py) — ligne 126 : `def render_symbol_table(df: pd.DataFrame, *, key: str, symbol_col: str='symbol', title: str | None=None, height: int=400, extra_actions: list[ActionSpec] | None=None, bars_lookback_days: int=365, hide_index: bool=True) -> str | None`

## `ihm/components/tables.py`

Source SHA-256 : `423ed3cbd9fe164d02fef2c94e8bd0721f1184eccf591eb88ef46290f28ae579`

- [show_dataframe](../../ihm/components/tables.py) — ligne 8 : `def show_dataframe(df: pd.DataFrame, title: str | None=None, height: int=400) -> None`

## `ihm/components/watcher_documentation.py`

Source SHA-256 : `837f95c92bc330396eba51b47a84b29f4ac461d2628cb77b62960b5e309645cc`

- [build_watcher_documentation_panel_payload](../../ihm/components/watcher_documentation.py) — ligne 9 : `def build_watcher_documentation_panel_payload() -> dict[str, str]`
- [render_watcher_documentation_panel](../../ihm/components/watcher_documentation.py) — ligne 34 : `def render_watcher_documentation_panel(*, intro: str | None=None) -> None`

## `ihm/pages/__init__.py`

Source SHA-256 : `683a5946e93d455dbba923064c52c1c5e3fcbf84565dd01645be3814d61000c1`

- [run_page_if_standalone](../../ihm/pages/__init__.py) — ligne 7 : `def run_page_if_standalone(module_name: str, render_func: Callable[[], None]) -> None`

## `ihm/pages/_alpha_scanner_diagnostics.py`

Source SHA-256 : `35c054e66ff8d6892e8cf588e9823455633b0995c8f6aab215907606e7abf34b`

- [_alpha_scanner_dependency_block_reason](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 50 : `def _alpha_scanner_dependency_block_reason(dependency_diagnostic: dict[str, object] | None) -> str | None`
- [_threshold_widget_key](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 59 : `def _threshold_widget_key(step_key: str, metric_key: str) -> str`
- [_apply_alpha_scanner_dependency_threshold_state_to_session](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 63 : `def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds: dict[str, dict[str, float]]) -> None`
- [_prime_alpha_scanner_dependency_threshold_state](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 69 : `def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]`
- [_collect_alpha_scanner_dependency_threshold_inputs](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 83 : `def _collect_alpha_scanner_dependency_threshold_inputs() -> dict[str, dict[str, float]]`
- [_set_alpha_scanner_dependency_threshold_state](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 93 : `def _set_alpha_scanner_dependency_threshold_state(thresholds: dict[str, dict[str, float]]) -> None`
- [_render_alpha_scanner_dependency_threshold_editor](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 97 : `def _render_alpha_scanner_dependency_threshold_editor() -> None`
- [_render_dependency_health_inline](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 206 : `def _render_dependency_health_inline(step_key: str, dependency_diagnostic: dict[str, object] | None) -> None`
- [_render_dependency_action_feedback](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 214 : `def _render_dependency_action_feedback(latest_by_step: dict[str, dict[str, object]]) -> None`
- [_render_alpha_scanner_dependency_diagnostic](../../ihm/pages/_alpha_scanner_diagnostics.py) — ligne 249 : `def _render_alpha_scanner_dependency_diagnostic(dependency_diagnostic: dict[str, object] | None, options: PipelineLaunchOptions, db_config: dict[str, str | None], *, workflow_active: bool, active_by_step: dict[str, list[dict[str, object]]], all_runs: list[dict[str, object]], latest_by_step: dict[str, dict[str, object]]) -> None`

## `ihm/pages/_data_integrity.py`

Source SHA-256 : `ac1acb9dc8fb2a6d03d2c0054f28024b9e7fb4e43de5f94d10eb3e3612ac9bc7`

- [_coerce_date](../../ihm/pages/_data_integrity.py) — ligne 65 : `def _coerce_date(value: object, fallback: DateValue) -> DateValue`
- [_coerce_date_text](../../ihm/pages/_data_integrity.py) — ligne 69 : `def _coerce_date_text(value: object, fallback: DateValue) -> str`
- [_parse_iso_date_text](../../ihm/pages/_data_integrity.py) — ligne 76 : `def _parse_iso_date_text(value: object) -> DateValue | None`
- [_date_last_synced_key](../../ihm/pages/_data_integrity.py) — ligne 86 : `def _date_last_synced_key(widget_key: str) -> str`
- [_ensure_date_input_state](../../ihm/pages/_data_integrity.py) — ligne 90 : `def _ensure_date_input_state(canonical_key: str, widget_key: str, fallback: DateValue) -> str`
- [_sync_date_input](../../ihm/pages/_data_integrity.py) — ligne 118 : `def _sync_date_input(canonical_key: str, widget_key: str, raw_value: str) -> None`
- [_format_date_input_status](../../ihm/pages/_data_integrity.py) — ligne 123 : `def _format_date_input_status(raw_value: str, parsed_value: DateValue | None) -> str`
- [_register_new_run](../../ihm/pages/_data_integrity.py) — ligne 129 : `def _register_new_run(record: PipelineRunRecord, all_runs: list[dict[str, object]]) -> None`
- [_resolve_import_news_scope_preview](../../ihm/pages/_data_integrity.py) — ligne 141 : `def _resolve_import_news_scope_preview(symbols_csv: str, symbol_source: str) -> dict[str, object]`
- [_backfill_diag_int](../../ihm/pages/_data_integrity.py) — ligne 158 : `def _backfill_diag_int(diag: dict[str, object], key: str, default: int=0) -> int`
- [_backfill_diag_float](../../ihm/pages/_data_integrity.py) — ligne 167 : `def _backfill_diag_float(diag: dict[str, object], key: str, default: float=0.0) -> float`
- [_resolve_symbols_for_diagnostic](../../ihm/pages/_data_integrity.py) — ligne 177 : `def _resolve_symbols_for_diagnostic(symbols_csv: str | None, symbol_source: str) -> list[str]`
- [_render_backfill_completeness_panel](../../ihm/pages/_data_integrity.py) — ligne 191 : `def _render_backfill_completeness_panel(start_value: DateValue, end_value: DateValue, *, use_expander: bool=True, import_options: PipelineLaunchOptions | None=None, db_config: dict[str, str | None] | None=None, all_runs: list[dict[str, object]] | None=None) -> None`
- [_latest_step_run_for_panel](../../ihm/pages/_data_integrity.py) — ligne 417 : `def _latest_step_run_for_panel(latest_by_step: dict[str, dict[str, object]], step_specs: list[dict[str, object]]) -> tuple[dict[str, object] | None, dict[str, object] | None]`
- [_render_import_news_panel](../../ihm/pages/_data_integrity.py) — ligne 444 : `def _render_import_news_panel(options: PipelineLaunchOptions, db_config: dict[str, str | None], *, workflow_active: bool, active_by_step: dict[str, list[dict[str, object]]], all_runs: list[dict[str, object]], latest_by_step: dict[str, dict[str, object]]) -> None`

## `ihm/pages/_execution_center/__init__.py`

Source SHA-256 : `049099d18d9b53a85c0297e9f9e60a5fe0f7b49e336650efaa9fdadd164346b3`

- [_get_capital_presets](../../ihm/pages/_execution_center/__init__.py) — ligne 369 : `def _get_capital_presets() -> tuple[CapitalPreset, ...]`
- [_get_capital_preset_options](../../ihm/pages/_execution_center/__init__.py) — ligne 376 : `def _get_capital_preset_options() -> list[str]`
- [_format_capital_preset_label](../../ihm/pages/_execution_center/__init__.py) — ligne 380 : `def _format_capital_preset_label(preset_key: str) -> str`
- [_build_parameter_rerun_guidance_rows](../../ihm/pages/_execution_center/__init__.py) — ligne 387 : `def _build_parameter_rerun_guidance_rows() -> tuple[dict[str, str], ...]`
- [_normalize_ml_train_preset_key](../../ihm/pages/_execution_center/__init__.py) — ligne 398 : `def _normalize_ml_train_preset_key(preset_key: str | None) -> str`
- [_coerce_session_date](../../ihm/pages/_execution_center/__init__.py) — ligne 407 : `def _coerce_session_date(value: object, *, default: date) -> date`
- [_coerce_int](../../ihm/pages/_execution_center/__init__.py) — ligne 418 : `def _coerce_int(value: object, *, default: int | None) -> int`
- [_coerce_float](../../ihm/pages/_execution_center/__init__.py) — ligne 428 : `def _coerce_float(value: object, *, default: float | None) -> float`
- [_coerce_bool](../../ihm/pages/_execution_center/__init__.py) — ligne 438 : `def _coerce_bool(value: object, *, default: bool) -> bool`
- [_session_state_int](../../ihm/pages/_execution_center/__init__.py) — ligne 455 : `def _session_state_int(key: str, default: int | None) -> int`
- [_session_state_float](../../ihm/pages/_execution_center/__init__.py) — ligne 459 : `def _session_state_float(key: str, default: float | None) -> float`
- [_session_state_bool](../../ihm/pages/_execution_center/__init__.py) — ligne 463 : `def _session_state_bool(key: str, default: bool) -> bool`
- [_ensure_normalized_ml_train_preset_session_state](../../ihm/pages/_execution_center/__init__.py) — ligne 471 : `def _ensure_normalized_ml_train_preset_session_state(session_state: dict[str, object]) -> str`
- [_format_ml_train_preset_label](../../ihm/pages/_execution_center/__init__.py) — ligne 479 : `def _format_ml_train_preset_label(preset_key: str) -> str`
- [_build_ml_train_preset_session_state_values](../../ihm/pages/_execution_center/__init__.py) — ligne 489 : `def _build_ml_train_preset_session_state_values(preset_key: str) -> dict[str, object]`
- [_build_ml_train_preset_summary](../../ihm/pages/_execution_center/__init__.py) — ligne 527 : `def _build_ml_train_preset_summary(preset_key: str) -> str`
- [_is_selected_ml_train_preset_dirty](../../ihm/pages/_execution_center/__init__.py) — ligne 548 : `def _is_selected_ml_train_preset_dirty(session_state: dict[str, object]) -> bool`
- [_apply_selected_ml_train_preset](../../ihm/pages/_execution_center/__init__.py) — ligne 556 : `def _apply_selected_ml_train_preset(*, force: bool=False) -> None`
- [_apply_selected_capital_preset](../../ihm/pages/_execution_center/__init__.py) — ligne 572 : `def _apply_selected_capital_preset(defaults: PipelineExecutionDefaults | None, *, selected_account_id: str | None) -> None`
- [_apply_execution_prefills](../../ihm/pages/_execution_center/__init__.py) — ligne 604 : `def _apply_execution_prefills(selected_account_id: str | None) -> PipelineExecutionDefaults | None`
- [_build_execution_prefill_caption](../../ihm/pages/_execution_center/__init__.py) — ligne 677 : `def _build_execution_prefill_caption(defaults: PipelineExecutionDefaults | None) -> str | None`
- [LaunchOptionsContext](../../ihm/pages/_execution_center/__init__.py) — ligne 698 : `class LaunchOptionsContext`
- [_build_contextual_backlog_estimate_scope](../../ihm/pages/_execution_center/__init__.py) — ligne 716 : `def _build_contextual_backlog_estimate_scope(*, min_relevance: float, start_date_iso: str | None, end_date_iso: str | None, symbols_csv: str | None, ingestion_source: str | None) -> dict[str, object]`
- [_load_contextual_backlog_preview](../../ihm/pages/_execution_center/__init__.py) — ligne 733 : `def _load_contextual_backlog_preview(min_relevance: float, start_date_iso: str | None=None, end_date_iso: str | None=None, symbols_csv: str | None=None, ingestion_source: str | None=None) -> dict[str, object]`
- [_render_event_sentiment_block](../../ihm/pages/_execution_center/__init__.py) — ligne 786 : `def _render_event_sentiment_block() -> dict[str, Any]`
- [_render_signal_aggregator_block](../../ihm/pages/_execution_center/__init__.py) — ligne 1282 : `def _render_signal_aggregator_block() -> dict[str, Any]`
- [_render_live_confirmation_block](../../ihm/pages/_execution_center/__init__.py) — ligne 1401 : `def _render_live_confirmation_block(execution_mode: str) -> bool`
- [_render_screener_block](../../ihm/pages/_execution_center/__init__.py) — ligne 1446 : `def _render_screener_block() -> dict[str, Any]`
- [_render_risk_block](../../ihm/pages/_execution_center/__init__.py) — ligne 1569 : `def _render_risk_block(selected_capital_preset: CapitalPreset | None) -> dict[str, Any]`
- [_render_selector_block](../../ihm/pages/_execution_center/__init__.py) — ligne 1962 : `def _render_selector_block() -> dict[str, Any]`
- [_render_data_integrity_block](../../ihm/pages/_execution_center/__init__.py) — ligne 2268 : `def _render_data_integrity_block() -> dict[str, Any]`
- [_render_corporate_actions_block](../../ihm/pages/_execution_center/__init__.py) — ligne 2509 : `def _render_corporate_actions_block(trade_date: str) -> dict[str, Any]`
- [_build_launch_options](../../ihm/pages/_execution_center/__init__.py) — ligne 2703 : `def _build_launch_options() -> tuple[PipelineLaunchOptions, bool]`

## `ihm/pages/_execution_center/_render_pending.py`

Source SHA-256 : `30c6061c170ddb396e23bc3e4991401339f92bb3c5f4d1607de48184a4d0fd7d`

- [render_execution_block](../../ihm/pages/_execution_center/_render_pending.py) — ligne 35 : `def render_execution_block(execution_defaults: Any | None=None, selected_account_id: str | None=None) -> dict[str, Any]`
- [render_model_factory_block](../../ihm/pages/_execution_center/_render_pending.py) — ligne 122 : `def render_model_factory_block() -> dict[str, Any]`

## `ihm/pages/_shared.py`

Source SHA-256 : `6234315e7906075a78812d41d5dcb85760c7c52eeedd012430f65d68f09ed21a`

- [_tail_text](../../ihm/pages/_shared.py) — ligne 107 : `def _tail_text(value: str, max_lines: int=TAIL_LINES) -> str`
- [_to_optional_positive_int](../../ihm/pages/_shared.py) — ligne 114 : `def _to_optional_positive_int(value: int | float | None) -> int | None`
- [_rerun_app](../../ihm/pages/_shared.py) — ligne 121 : `def _rerun_app() -> None`
- [_render_run_summary](../../ihm/pages/_shared.py) — ligne 128 : `def _render_run_summary(record: dict[str, object] | None, *, compact: bool=False) -> None`
- [_render_log_block](../../ihm/pages/_shared.py) — ligne 181 : `def _render_log_block(title: str, content: str, *, key: str, expanded: bool=False) -> None`
- [_pipeline_step_label](../../ihm/pages/_shared.py) — ligne 194 : `def _pipeline_step_label(step_key: str) -> str`
- [_record_dependency_action_run](../../ihm/pages/_shared.py) — ligne 201 : `def _record_dependency_action_run(step_key: str, run_id: str) -> None`
- [_launch_pipeline_step](../../ihm/pages/_shared.py) — ligne 208 : `def _launch_pipeline_step(step_key: str, step_label: str, options: PipelineLaunchOptions, db_config: dict[str, str | None], all_runs: list[dict[str, object]], *, track_dependency_action: bool=False) -> None`
- [_status_badge](../../ihm/pages/_shared.py) — ligne 237 : `def _status_badge(status: str) -> str`
- [_is_workflow_run](../../ihm/pages/_shared.py) — ligne 249 : `def _is_workflow_run(run: dict[str, object]) -> bool`
- [_workflow_progress](../../ihm/pages/_shared.py) — ligne 253 : `def _workflow_progress(run: dict[str, object]) -> tuple[int, int, float, str]`
- [_build_watchdog_badge](../../ihm/pages/_shared.py) — ligne 264 : `def _build_watchdog_badge(record: dict[str, object] | None) -> str | None`
- [_render_watchdog_status](../../ihm/pages/_shared.py) — ligne 278 : `def _render_watchdog_status(record: dict[str, object] | None) -> None`
- [_sanitize_compare_ids](../../ihm/pages/_shared.py) — ligne 296 : `def _sanitize_compare_ids(run_ids: list[str], labels: dict[str, str], value: object) -> list[str]`
- [_render_step_result](../../ihm/pages/_shared.py) — ligne 301 : `def _render_step_result(record: dict[str, object] | None) -> None`
- [_render_risk_snapshot_freshness_warning](../../ihm/pages/_shared.py) — ligne 329 : `def _render_risk_snapshot_freshness_warning(record: dict[str, object]) -> None`

## `ihm/pages/_watcher_block.py`

Source SHA-256 : `8ccd7a210cb5639f0f6e225e739f712cada97b7adc9ba3141c55e5a9eede7760`

- [_build_watcher_handoff_rows](../../ihm/pages/_watcher_block.py) — ligne 38 : `def _build_watcher_handoff_rows(account_id: str | None, *, take_profit_pct: float=0.08, trailing_stop_pct: float=0.05, manual_buy_stop_loss_pct: float=0.05, trailing_trigger: str='multiple_r', trailing_r_multiple: float=0.0, trailing_profit_pct: float=0.03) -> list[dict[str, str]]`
- [_render_watcher_handoff_panel](../../ihm/pages/_watcher_block.py) — ligne 94 : `def _render_watcher_handoff_panel(options: PipelineLaunchOptions) -> None`
- [_render_watcher_launch_controls](../../ihm/pages/_watcher_block.py) — ligne 132 : `def _render_watcher_launch_controls(options: PipelineLaunchOptions) -> None`

## `ihm/pages/_workflow/__init__.py`

Source SHA-256 : `b0a65ce5e0d8a108728a9a4a082cc87acffbab6383969f64ccdb10444e44240b`

- [_resolve_delayed_workflow_start](../../ihm/pages/_workflow/__init__.py) — ligne 103 : `def _resolve_delayed_workflow_start(target_time: dt_time, *, now: datetime | None=None) -> datetime`
- [_parse_iso_datetime](../../ihm/pages/_workflow/__init__.py) — ligne 111 : `def _parse_iso_datetime(value: object) -> datetime | None`
- [_format_countdown](../../ihm/pages/_workflow/__init__.py) — ligne 121 : `def _format_countdown(total_seconds: int) -> str`
- [_rerun_app](../../ihm/pages/_workflow/__init__.py) — ligne 130 : `def _rerun_app() -> None`
- [_build_scheduled_countdown_caption](../../ihm/pages/_workflow/__init__.py) — ligne 137 : `def _build_scheduled_countdown_caption(run: dict[str, object], *, now: datetime | None=None) -> str | None`
- [_build_actual_start_caption](../../ihm/pages/_workflow/__init__.py) — ligne 151 : `def _build_actual_start_caption(run: dict[str, object]) -> str | None`
- [_build_workflow_scope_help_lines](../../ihm/pages/_workflow/__init__.py) — ligne 161 : `def _build_workflow_scope_help_lines() -> tuple[str, str, str]`
- [_build_workflow_scope_alert_lines](../../ihm/pages/_workflow/__init__.py) — ligne 169 : `def _build_workflow_scope_alert_lines() -> tuple[str, str]`
- [_workflow_mode_label](../../ihm/pages/_workflow/__init__.py) — ligne 176 : `def _workflow_mode_label(run: dict[str, object]) -> str`
- [_custom_workflow_checkbox_key](../../ihm/pages/_workflow/__init__.py) — ligne 199 : `def _custom_workflow_checkbox_key(step_key: str) -> str`
- [_build_run_provider_badge](../../ihm/pages/_workflow/__init__.py) — ligne 203 : `def _build_run_provider_badge(run: dict[str, object] | None) -> str | None`
- [_build_run_stooq_badge](../../ihm/pages/_workflow/__init__.py) — ligne 229 : `def _build_run_stooq_badge(run: dict[str, object] | None) -> str | None`
- [_build_run_symbol_progress_caption](../../ihm/pages/_workflow/__init__.py) — ligne 236 : `def _build_run_symbol_progress_caption(run: dict[str, object] | None) -> str | None`
- [_build_run_symbol_progress_payload](../../ihm/pages/_workflow/__init__.py) — ligne 244 : `def _build_run_symbol_progress_payload(run: dict[str, object] | None) -> tuple[float, str] | None`
- [_to_non_negative_int](../../ihm/pages/_workflow/__init__.py) — ligne 270 : `def _to_non_negative_int(value: object) -> int | None`
- [_build_run_progress_payload_from_explicit_summary](../../ihm/pages/_workflow/__init__.py) — ligne 280 : `def _build_run_progress_payload_from_explicit_summary(summary: dict[str, object]) -> tuple[float, str] | None`
- [_build_run_progress_payload_from_summary](../../ihm/pages/_workflow/__init__.py) — ligne 294 : `def _build_run_progress_payload_from_summary(step_key: str, summary: dict[str, object]) -> tuple[float, str] | None`
- [_build_run_progress_payload_from_logs](../../ihm/pages/_workflow/__init__.py) — ligne 318 : `def _build_run_progress_payload_from_logs(run: dict[str, object]) -> tuple[float, str] | None`
- [_build_workflow_child_run_payload](../../ihm/pages/_workflow/__init__.py) — ligne 354 : `def _build_workflow_child_run_payload(workflow_run: dict[str, object]) -> tuple[list[str], dict[str, str]]`
- [_prepare_workflow_child_run_state](../../ihm/pages/_workflow/__init__.py) — ligne 381 : `def _prepare_workflow_child_run_state(workflow_run: dict[str, object], child_run_ids: list[str], child_labels: dict[str, str]) -> tuple[str | None, bool, str | None, str | None, str | None]`
- [_cached_history](../../ihm/pages/_workflow/__init__.py) — ligne 436 : `def _cached_history() -> list[dict[str, object]]`
- [_merge_runs](../../ihm/pages/_workflow/__init__.py) — ligne 440 : `def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]`
- [_latest_run_by_step](../../ihm/pages/_workflow/__init__.py) — ligne 453 : `def _latest_run_by_step(all_runs: list[dict[str, object]]) -> dict[str, dict[str, object]]`
- [_build_history_rows](../../ihm/pages/_workflow/__init__.py) — ligne 462 : `def _build_history_rows(all_runs: list[dict[str, object]]) -> pd.DataFrame`
- [_should_render_active_run_live_progress](../../ihm/pages/_workflow/__init__.py) — ligne 488 : `def _should_render_active_run_live_progress(run: dict[str, object], *, active_workflow_run_ids: set[str] | None=None) -> bool`
- [_active_workflow_run_id](../../ihm/pages/_workflow/__init__.py) — ligne 503 : `def _active_workflow_run_id(all_runs: list[dict[str, object]]) -> str | None`
- [_resolve_runtime_center_default_selected_run_id](../../ihm/pages/_workflow/__init__.py) — ligne 515 : `def _resolve_runtime_center_default_selected_run_id(all_runs: list[dict[str, object]], run_ids: list[str]) -> str`
- [_prime_runtime_center_state](../../ihm/pages/_workflow/__init__.py) — ligne 528 : `def _prime_runtime_center_state(all_runs: list[dict[str, object]], run_ids: list[str], labels: dict[str, str]) -> list[str]`
- [_selected_dataframe_row_index](../../ihm/pages/_workflow/__init__.py) — ligne 568 : `def _selected_dataframe_row_index(table_key: str) -> int | None`
- [_resolve_history_selected_run_id](../../ihm/pages/_workflow/__init__.py) — ligne 584 : `def _resolve_history_selected_run_id(history_df: pd.DataFrame, *, table_key: str=WORKFLOW_HISTORY_TABLE_KEY) -> str | None`
- [_render_workflow_launcher](../../ihm/pages/_workflow/__init__.py) — ligne 598 : `def _render_workflow_launcher(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None]) -> None`
- [_render_runtime_center](../../ihm/pages/_workflow/__init__.py) — ligne 808 : `def _render_runtime_center() -> None`

## `ihm/pages/alpaca_accounts.py`

Source SHA-256 : `2b8380f3816ee0c84a619302ab2ce4fbeae7e82ec2744e98b8269447b38fc0b4`

- [_format_currency](../../ihm/pages/alpaca_accounts.py) — ligne 36 : `def _format_currency(value: object) -> str`
- [_format_bool](../../ihm/pages/alpaca_accounts.py) — ligne 44 : `def _format_bool(value: object) -> str`
- [_build_account_details_dataframe](../../ihm/pages/alpaca_accounts.py) — ligne 48 : `def _build_account_details_dataframe(account_payload: dict[str, Any]) -> pd.DataFrame`
- [_render_live_account_summary](../../ihm/pages/alpaca_accounts.py) — ligne 68 : `def _render_live_account_summary(account_payload: dict[str, Any]) -> None`
- [_render_capital_history](../../ihm/pages/alpaca_accounts.py) — ligne 87 : `def _render_capital_history(*, account_id: str, portfolio_history: pd.DataFrame, snapshot_history: pd.DataFrame) -> None`
- [_clear_page_caches](../../ihm/pages/alpaca_accounts.py) — ligne 127 : `def _clear_page_caches() -> None`
- [_build_failover_doctrine_dataframe](../../ihm/pages/alpaca_accounts.py) — ligne 137 : `def _build_failover_doctrine_dataframe(summary: dict[str, Any]) -> pd.DataFrame`
- [_render_failover_doctrine_panel](../../ihm/pages/alpaca_accounts.py) — ligne 151 : `def _render_failover_doctrine_panel() -> None`
- [render](../../ihm/pages/alpaca_accounts.py) — ligne 169 : `def render() -> None`

## `ihm/pages/backtesting/__init__.py`

Source SHA-256 : `fa38363eb87aa7cb03d43c58a2cd91fd481da9a66df5e35fa279e72ac4940104`

- [_to_float](../../ihm/pages/backtesting/__init__.py) — ligne 187 : `def _to_float(value: object, default: float=0.0) -> float`
- [_to_int](../../ihm/pages/backtesting/__init__.py) — ligne 194 : `def _to_int(value: object, default: int=0) -> int`
- [_parse_optional_int](../../ihm/pages/backtesting/__init__.py) — ligne 201 : `def _parse_optional_int(raw_value: str, *, label: str) -> int | None`
- [_parse_optional_float](../../ihm/pages/backtesting/__init__.py) — ligne 212 : `def _parse_optional_float(raw_value: str, *, label: str) -> float | None`
- [_to_date_value](../../ihm/pages/backtesting/__init__.py) — ligne 223 : `def _to_date_value(value: object, default: str)`
- [_get_capital_presets](../../ihm/pages/backtesting/__init__.py) — ligne 243 : `def _get_capital_presets() -> tuple[CapitalPreset, ...]`
- [_get_capital_preset_options](../../ihm/pages/backtesting/__init__.py) — ligne 250 : `def _get_capital_preset_options() -> list[str]`
- [_get_run_configuration_preset](../../ihm/pages/backtesting/__init__.py) — ligne 258 : `def _get_run_configuration_preset(preset_key: str) -> dict[str, object] | None`
- [_ensure_run_configuration_preset_session_key](../../ihm/pages/backtesting/__init__.py) — ligne 263 : `def _ensure_run_configuration_preset_session_key() -> str`
- [_format_run_configuration_preset_label](../../ihm/pages/backtesting/__init__.py) — ligne 272 : `def _format_run_configuration_preset_label(preset_key: str) -> str`
- [_apply_run_configuration_preset](../../ihm/pages/backtesting/__init__.py) — ligne 279 : `def _apply_run_configuration_preset(selected_preset_key: str) -> dict[str, object] | None`
- [_format_capital_preset_label](../../ihm/pages/backtesting/__init__.py) — ligne 297 : `def _format_capital_preset_label(preset_key: str) -> str`
- [_resolve_default_capital_preset_key](../../ihm/pages/backtesting/__init__.py) — ligne 304 : `def _resolve_default_capital_preset_key(equity: float | None) -> str`
- [_ensure_capital_preset_session_key](../../ihm/pages/backtesting/__init__.py) — ligne 311 : `def _ensure_capital_preset_session_key(session_key: str, equity: float | None, *, default_key: str | None=None) -> str`
- [_apply_run_capital_preset](../../ihm/pages/backtesting/__init__.py) — ligne 333 : `def _apply_run_capital_preset(selected_preset_key: str, equity: float) -> CapitalPreset | None`
- [_resolve_pipeline_backtest_defaults](../../ihm/pages/backtesting/__init__.py) — ligne 373 : `def _resolve_pipeline_backtest_defaults(*, engine_mode: str, selected_run_preset_key: str, auto_run_preset_key: str) -> dict[str, float | None]`
- [_load_dip_backtest_defaults](../../ihm/pages/backtesting/__init__.py) — ligne 413 : `def _load_dip_backtest_defaults() -> dict[str, Any]`
- [_apply_backfill_capital_preset](../../ihm/pages/backtesting/__init__.py) — ligne 439 : `def _apply_backfill_capital_preset(selected_preset_key: str, capital: float) -> CapitalPreset | None`
- [_tail_text](../../ihm/pages/backtesting/__init__.py) — ligne 459 : `def _tail_text(value: str, max_lines: int=TAIL_LINES) -> str`
- [_file_cache_signature](../../ihm/pages/backtesting/__init__.py) — ligne 466 : `def _file_cache_signature(path: Path) -> tuple[str, int, int] | None`
- [_read_cached_json_file](../../ihm/pages/backtesting/__init__.py) — ligne 477 : `def _read_cached_json_file(path_str: str, mtime_ns: int, size_bytes: int) -> dict[str, object] | None`
- [_read_cached_csv_file](../../ihm/pages/backtesting/__init__.py) — ligne 487 : `def _read_cached_csv_file(path_str: str, mtime_ns: int, size_bytes: int) -> pd.DataFrame`
- [_should_preload_runtime_details](../../ihm/pages/backtesting/__init__.py) — ligne 492 : `def _should_preload_runtime_details(status: str) -> bool`
- [_should_auto_refresh_runtime_center](../../ihm/pages/backtesting/__init__.py) — ligne 496 : `def _should_auto_refresh_runtime_center(*run_groups: list[dict[str, object]]) -> bool`
- [_is_runtime_center_auto_update_enabled](../../ihm/pages/backtesting/__init__.py) — ligne 500 : `def _is_runtime_center_auto_update_enabled() -> bool`
- [_render_log_block](../../ihm/pages/backtesting/__init__.py) — ligne 504 : `def _render_log_block(title: str, content: str, *, key: str, expanded: bool=False) -> None`
- [_status_badge](../../ihm/pages/backtesting/__init__.py) — ligne 517 : `def _status_badge(status: str) -> str`
- [_extract_run_batch_id](../../ihm/pages/backtesting/__init__.py) — ligne 528 : `def _extract_run_batch_id(run: dict[str, object]) -> str | None`
- [_extract_run_oracle_batch_id](../../ihm/pages/backtesting/__init__.py) — ligne 551 : `def _extract_run_oracle_batch_id(run: dict[str, object]) -> str | None`
- [_extract_run_dates](../../ihm/pages/backtesting/__init__.py) — ligne 570 : `def _extract_run_dates(run: dict[str, object]) -> tuple[str | None, str | None]`
- [_load_batch_comments](../../ihm/pages/backtesting/__init__.py) — ligne 600 : `def _load_batch_comments(batch_ids: tuple[str, ...]) -> dict[str, str]`
- [_format_run_inspect_label](../../ihm/pages/backtesting/__init__.py) — ligne 616 : `def _format_run_inspect_label(run: dict[str, object], batch_comments: dict[str, str]) -> str`
- [_merge_runs](../../ihm/pages/backtesting/__init__.py) — ligne 635 : `def _merge_runs() -> tuple[list[dict[str, object]], list[dict[str, object]]]`
- [_prime_runtime_center_state](../../ihm/pages/backtesting/__init__.py) — ligne 650 : `def _prime_runtime_center_state(run_ids: list[str], labels: dict[str, str]) -> None`
- [_selected_dataframe_row_index](../../ihm/pages/backtesting/__init__.py) — ligne 660 : `def _selected_dataframe_row_index(table_key: str) -> int | None`
- [_resolve_history_selected_run_id](../../ihm/pages/backtesting/__init__.py) — ligne 676 : `def _resolve_history_selected_run_id(history_df: pd.DataFrame, *, table_key: str=BACKTESTING_HISTORY_TABLE_KEY) -> str | None`
- [_resolve_history_selected_run_ids](../../ihm/pages/backtesting/__init__.py) — ligne 690 : `def _resolve_history_selected_run_ids(history_df: pd.DataFrame, *, table_key: str=BACKTESTING_HISTORY_TABLE_KEY) -> list[str]`
- [_clear_history_selection](../../ihm/pages/backtesting/__init__.py) — ligne 721 : `def _clear_history_selection(*, table_key: str=BACKTESTING_HISTORY_TABLE_KEY) -> None`
- [_parameter_reference_rows](../../ihm/pages/backtesting/__init__.py) — ligne 747 : `def _parameter_reference_rows(kind: str) -> list[dict[str, str]]`
- [_render_reference_table](../../ihm/pages/backtesting/__init__.py) — ligne 872 : `def _render_reference_table(kind: str) -> None`
- [_summarize_sector_multipliers](../../ihm/pages/backtesting/__init__.py) — ligne 880 : `def _summarize_sector_multipliers(path: Path) -> str`
- [_list_backtest_runs_with_trades](../../ihm/pages/backtesting/__init__.py) — ligne 894 : `def _list_backtest_runs_with_trades() -> list[str]`
- [_default_fidelity_baseline_catalog_path](../../ihm/pages/backtesting/__init__.py) — ligne 907 : `def _default_fidelity_baseline_catalog_path() -> Path`
- [_build_fidelity_baseline_catalog_rows](../../ihm/pages/backtesting/__init__.py) — ligne 911 : `def _build_fidelity_baseline_catalog_rows(catalog_path: Path | None=None) -> pd.DataFrame`
- [_build_pipeline_pit_status_message](../../ihm/pages/backtesting/__init__.py) — ligne 949 : `def _build_pipeline_pit_status_message(diagnostic: dict[str, object]) -> tuple[str, str]`
- [_build_ml_coverage_status_message](../../ihm/pages/backtesting/__init__.py) — ligne 999 : `def _build_ml_coverage_status_message(diagnostic: dict[str, object]) -> tuple[str, str]`
- [_render_pipeline_pit_hint](../../ihm/pages/backtesting/__init__.py) — ligne 1076 : `def _render_pipeline_pit_hint(*, engine_mode: str, start: str, end: str | None, selected_run_preset_key: str, auto_run_preset_key: str) -> None`
- [_render_ml_coverage_preflight](../../ihm/pages/backtesting/__init__.py) — ligne 1101 : `def _render_ml_coverage_preflight(*, engine_mode: str, ml_mode: str, ml_pit_strategy: str, start: str, end: str | None, selected_run_preset_key: str, auto_run_preset_key: str) -> None`
- [_build_overlay_options](../../ihm/pages/backtesting/__init__.py) — ligne 1171 : `def _build_overlay_options(*, engine_mode: str, selected_run_preset_key: str, auto_run_preset_key: str, use_live_protection_logic: bool) -> dict[str, Any]`
- [_build_run_options](../../ihm/pages/backtesting/__init__.py) — ligne 1532 : `def _build_run_options() -> BacktestRunOptions`
- [_build_backfill_options](../../ihm/pages/backtesting/__init__.py) — ligne 3030 : `def _build_backfill_options() -> BackfillScoresHistoryOptions`
- [_build_diagnose_screener_options](../../ihm/pages/backtesting/__init__.py) — ligne 3204 : `def _build_diagnose_screener_options() -> DiagnoseScreenerOptions`
- [_build_recommend_screener_options](../../ihm/pages/backtesting/__init__.py) — ligne 3364 : `def _build_recommend_screener_options() -> RecommendScreenerOptions`
- [_build_calibrate_sentiment_options](../../ihm/pages/backtesting/__init__.py) — ligne 3449 : `def _build_calibrate_sentiment_options() -> 'CalibrateSentimentWeightsOptions'`
- [_build_calibrate_conviction_options](../../ihm/pages/backtesting/__init__.py) — ligne 3532 : `def _build_calibrate_conviction_options() -> 'CalibrateConvictionWeightsOptions'`
- [_build_walk_forward_conviction_options](../../ihm/pages/backtesting/__init__.py) — ligne 3639 : `def _build_walk_forward_conviction_options() -> 'WalkForwardConvictionOptions'`
- [_build_walk_forward_sentiment_options](../../ihm/pages/backtesting/__init__.py) — ligne 3781 : `def _build_walk_forward_sentiment_options() -> 'WalkForwardSentimentOptions'`
- [_render_latest_artifacts](../../ihm/pages/backtesting/__init__.py) — ligne 3955 : `def _render_latest_artifacts() -> None`
- [_resolve_run_dir](../../ihm/pages/backtesting/__init__.py) — ligne 3982 : `def _resolve_run_dir(run_record: dict[str, object]) -> Path | None`
- [_resolve_run_artifact_path](../../ihm/pages/backtesting/__init__.py) — ligne 3990 : `def _resolve_run_artifact_path(run_dir: Path, filename: str) -> Path`
- [_load_run_report](../../ihm/pages/backtesting/__init__.py) — ligne 4000 : `def _load_run_report(run_record: dict[str, object]) -> dict[str, object] | None`
- [_load_equity_curve_df](../../ihm/pages/backtesting/__init__.py) — ligne 4014 : `def _load_equity_curve_df(run_record: dict[str, object]) -> pd.DataFrame`
- [_load_run_trades_df](../../ihm/pages/backtesting/__init__.py) — ligne 4033 : `def _load_run_trades_df(run_record: dict[str, object]) -> pd.DataFrame`
- [_load_market_regimes_df](../../ihm/pages/backtesting/__init__.py) — ligne 4059 : `def _load_market_regimes_df(run_record: dict[str, object]) -> pd.DataFrame`
- [_format_position_quantity](../../ihm/pages/backtesting/__init__.py) — ligne 4077 : `def _format_position_quantity(quantity: float) -> str`
- [_format_position_notional](../../ihm/pages/backtesting/__init__.py) — ligne 4084 : `def _format_position_notional(amount: float) -> str`
- [_resolve_trade_entry_notional](../../ihm/pages/backtesting/__init__.py) — ligne 4088 : `def _resolve_trade_entry_notional(trade: object) -> float | None`
- [_register_position_delta](../../ihm/pages/backtesting/__init__.py) — ligne 4103 : `def _register_position_delta(position_deltas: dict[pd.Timestamp, dict[str, float]], trade_date: pd.Timestamp, symbol: str, quantity_delta: float) -> None`
- [_build_position_detail_text](../../ihm/pages/backtesting/__init__.py) — ligne 4113 : `def _build_position_detail_text(symbol: str, quantity: float, entry_notional: float | None) -> str`
- [_build_daily_portfolio_snapshot_df](../../ihm/pages/backtesting/__init__.py) — ligne 4120 : `def _build_daily_portfolio_snapshot_df(equity_curve_df: pd.DataFrame, trades_df: pd.DataFrame, market_regimes_df: pd.DataFrame | None=None) -> pd.DataFrame`
- [_resolve_phase2_risk_summary](../../ihm/pages/backtesting/__init__.py) — ligne 4245 : `def _resolve_phase2_risk_summary(params: dict[str, object], artifacts: dict[str, object]) -> dict[str, object]`
- [_render_report_summary](../../ihm/pages/backtesting/__init__.py) — ligne 4257 : `def _render_report_summary(run_record: dict[str, object]) -> bool`
- [_batch_oracle_horizon](../../ihm/pages/backtesting/__init__.py) — ligne 4771 : `def _batch_oracle_horizon(batch_id: str) -> int`
- [_render_run_oracle_deciles](../../ihm/pages/backtesting/__init__.py) — ligne 4795 : `def _render_run_oracle_deciles(run_record: dict[str, object]) -> None`
- [_render_live_artifacts](../../ihm/pages/backtesting/__init__.py) — ligne 4908 : `def _render_live_artifacts(run_record: dict[str, object]) -> bool`
- [_coerce_metric_text](../../ihm/pages/backtesting/__init__.py) — ligne 4969 : `def _coerce_metric_text(value: object) -> str`
- [_format_fidelity_status](../../ihm/pages/backtesting/__init__.py) — ligne 4976 : `def _format_fidelity_status(status: object) -> str`
- [_build_fidelity_component_rows](../../ihm/pages/backtesting/__init__.py) — ligne 4985 : `def _build_fidelity_component_rows(fidelity: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_coverage_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5013 : `def _build_fidelity_coverage_rows(fidelity: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_provenance_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5037 : `def _build_fidelity_provenance_rows(fidelity: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_ml_cause_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5064 : `def _build_fidelity_ml_cause_rows(fidelity: dict[str, object]) -> pd.DataFrame`
- [_load_json_artifact_from_paths](../../ihm/pages/backtesting/__init__.py) — ligne 5084 : `def _load_json_artifact_from_paths(artifacts: dict[str, object], artifact_key: str) -> dict[str, object] | None`
- [_build_replay_diagnostic_session_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5098 : `def _build_replay_diagnostic_session_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_selection_target_parity_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5136 : `def _build_selection_target_parity_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_compare_to_live_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5159 : `def _build_compare_to_live_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_baseline_snapshot_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5224 : `def _build_fidelity_baseline_snapshot_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_baseline_check_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5238 : `def _build_fidelity_baseline_check_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_fidelity_symbol_matrix_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5261 : `def _build_fidelity_symbol_matrix_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_build_execution_broker_like_session_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5288 : `def _build_execution_broker_like_session_rows(payload: dict[str, object]) -> pd.DataFrame`
- [_resolve_screener_artifact_summary](../../ihm/pages/backtesting/__init__.py) — ligne 5324 : `def _resolve_screener_artifact_summary(run_record: dict[str, object]) -> dict[str, object] | None`
- [_build_screener_artifact_metric_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5334 : `def _build_screener_artifact_metric_rows(summary: dict[str, object]) -> list[tuple[str, str]]`
- [_build_screener_artifact_objective_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5351 : `def _build_screener_artifact_objective_rows(summary: dict[str, object]) -> pd.DataFrame`
- [_build_screener_artifact_file_rows](../../ihm/pages/backtesting/__init__.py) — ligne 5370 : `def _build_screener_artifact_file_rows(summary: dict[str, object]) -> pd.DataFrame`
- [_build_global_screener_history_dataframe](../../ihm/pages/backtesting/__init__.py) — ligne 5392 : `def _build_global_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame`
- [_render_screener_artifact_summary](../../ihm/pages/backtesting/__init__.py) — ligne 5396 : `def _render_screener_artifact_summary(run_record: dict[str, object]) -> bool`
- [_render_batch_diagnostics_block](../../ihm/pages/backtesting/__init__.py) — ligne 5466 : `def _render_batch_diagnostics_block() -> None`
- [_render_runtime_center_body](../../ihm/pages/backtesting/__init__.py) — ligne 5624 : `def _render_runtime_center_body(*, auto_refresh_enabled: bool) -> None`
- [_render_runtime_center_live](../../ihm/pages/backtesting/__init__.py) — ligne 6053 : `def _render_runtime_center_live() -> None`
- [_render_runtime_center_static](../../ihm/pages/backtesting/__init__.py) — ligne 6064 : `def _render_runtime_center_static() -> None`
- [render](../../ihm/pages/backtesting/__init__.py) — ligne 6068 : `def render() -> None`

## `ihm/pages/batches.py`

Source SHA-256 : `44583b7be1a07ba1fdead8e8fd751b8c7802d82973e51c77543f93dfa697a3d8`

- [_task_states](../../ihm/pages/batches.py) — ligne 42 : `def _task_states() -> tuple[dict[str, dict[str, Any]], str | None]`
- [_latest_collection_runs](../../ihm/pages/batches.py) — ligne 47 : `def _latest_collection_runs() -> tuple[dict[str, dict[str, Any]], str | None]`
- [_priority_badge](../../ihm/pages/batches.py) — ligne 100 : `def _priority_badge(priority: str) -> str`
- [_task_badge](../../ihm/pages/batches.py) — ligne 105 : `def _task_badge(task: dict[str, Any] | None) -> str`
- [_value](../../ihm/pages/batches.py) — ligne 116 : `def _value(value: Any) -> str`
- [_last_run_failed](../../ihm/pages/batches.py) — ligne 122 : `def _last_run_failed(row: dict[str, Any] | None) -> bool`
- [_utc_timestamp](../../ihm/pages/batches.py) — ligne 130 : `def _utc_timestamp(value: Any, *, naive_is_utc: bool) -> datetime | None`
- [_database_time_label](../../ihm/pages/batches.py) — ligne 144 : `def _database_time_label(value: Any) -> str`
- [_windows_last_run_failed](../../ihm/pages/batches.py) — ligne 151 : `def _windows_last_run_failed(task: dict[str, Any] | None, row: dict[str, Any] | None=None) -> bool`
- [_batch_title](../../ihm/pages/batches.py) — ligne 176 : `def _batch_title(status_bits: list[str], name: str, row: dict[str, Any] | None, task: dict[str, Any] | None=None, *, catalog_status: str='') -> str`
- [_render_last_run](../../ihm/pages/batches.py) — ligne 194 : `def _render_last_run(row: dict[str, Any] | None) -> None`
- [_render_batch](../../ihm/pages/batches.py) — ligne 217 : `def _render_batch(spec: BatchSpec, task: dict[str, Any] | None, db_run: dict[str, Any] | None, *, run_as: str, active: list[dict[str, object]], recent: dict[str, object] | None) -> None`
- [_render_bulk_result](../../ihm/pages/batches.py) — ligne 426 : `def _render_bulk_result(action: str, results: dict[str, Any], skipped: list[str]) -> None`
- [render](../../ihm/pages/batches.py) — ligne 447 : `def render() -> None`
- [render_market_batches](../../ihm/pages/batches.py) — ligne 461 : `def render_market_batches(market: str) -> None`

## `ihm/pages/compliance_audit.py`

Source SHA-256 : `95bf1271b0978a9edde0ae5b114c7b59084c856f8abf4da0d845d5db382a272a`

- [_level_bool](../../ihm/pages/compliance_audit.py) — ligne 24 : `def _level_bool(v: bool | None) -> str`
- [_level_count](../../ihm/pages/compliance_audit.py) — ligne 32 : `def _level_count(v: int | None, *, danger_at: int=1, warn_at: int=0) -> str`
- [_level_pct](../../ihm/pages/compliance_audit.py) — ligne 42 : `def _level_pct(v: float | None, *, ok_at: float, warn_at: float) -> str`
- [_fmt](../../ihm/pages/compliance_audit.py) — ligne 52 : `def _fmt(v) -> str`
- [render](../../ihm/pages/compliance_audit.py) — ligne 56 : `def render() -> None`

## `ihm/pages/corporate_actions.py`

Source SHA-256 : `231fd230f7db1b17c12df4f9853b216e347376894a389d42affacb5843b764d6`

- [render](../../ihm/pages/corporate_actions.py) — ligne 22 : `def render() -> None`

## `ihm/pages/db_admin.py`

Source SHA-256 : `7c1e80484344ef50703eefcca0577ba81b1a2336006ab03086a75397d2efa68a`

- [_checkbox_key](../../ihm/pages/db_admin.py) — ligne 28 : `def _checkbox_key(table_name: str) -> str`
- [_set_selection](../../ihm/pages/db_admin.py) — ligne 32 : `def _set_selection(grouped_tables: dict[str, list[TableCatalogEntry]], *, value: bool) -> None`
- [_apply_pending_widget_resets](../../ihm/pages/db_admin.py) — ligne 39 : `def _apply_pending_widget_resets(grouped_tables: dict[str, list[TableCatalogEntry]]) -> None`
- [_render_last_purge_feedback](../../ihm/pages/db_admin.py) — ligne 51 : `def _render_last_purge_feedback() -> None`
- [_build_execute_blockers](../../ihm/pages/db_admin.py) — ligne 71 : `def _build_execute_blockers(plan: TablePurgePlan, *, confirm_purge: bool) -> tuple[str, ...]`
- [_render_group](../../ihm/pages/db_admin.py) — ligne 92 : `def _render_group(group_name: str, entries: list[TableCatalogEntry]) -> None`
- [render](../../ihm/pages/db_admin.py) — ligne 135 : `def render() -> None`

## `ihm/pages/execution.py`

Source SHA-256 : `b1244efd25c5d45c04777fd67d32e917e1ad4396bd39d10278b379bf80f13b33`

- [_reconciliation_status_badge](../../ihm/pages/execution.py) — ligne 37 : `def _reconciliation_status_badge(status: object) -> str`
- [_prepare_reconciliation_display](../../ihm/pages/execution.py) — ligne 48 : `def _prepare_reconciliation_display(df: pd.DataFrame) -> pd.DataFrame`
- [_prepare_fills_display](../../ihm/pages/execution.py) — ligne 63 : `def _prepare_fills_display(df: pd.DataFrame) -> pd.DataFrame`
- [_normalized_symbol_set](../../ihm/pages/execution.py) — ligne 77 : `def _normalized_symbol_set(df: pd.DataFrame) -> set[str]`
- [_render_trade_pipeline_consistency](../../ihm/pages/execution.py) — ligne 87 : `def _render_trade_pipeline_consistency(*, fills: pd.DataFrame, lots: pd.DataFrame, reconciliation: pd.DataFrame) -> None`
- [_show_position_lots_table](../../ihm/pages/execution.py) — ligne 118 : `def _show_position_lots_table(df: pd.DataFrame, *, title: str, height: int=260) -> None`
- [_safe_iterable](../../ihm/pages/execution.py) — ligne 131 : `def _safe_iterable(value: object) -> list[object]`
- [_safe_int](../../ihm/pages/execution.py) — ligne 137 : `def _safe_int(value: object, default: int=0) -> int`
- [_render_reconciliation_age_warning](../../ihm/pages/execution.py) — ligne 152 : `def _render_reconciliation_age_warning(reconciliation: pd.DataFrame) -> None`
- [_render_live_freeze_banner](../../ihm/pages/execution.py) — ligne 179 : `def _render_live_freeze_banner(live_guard: dict[str, object]) -> None`
- [_render_reconciliation_j1_panel](../../ihm/pages/execution.py) — ligne 191 : `def _render_reconciliation_j1_panel(*, account_id: str | None, selected_trade_date: object, broker_mode: object) -> None`
- [_render_tca_panel](../../ihm/pages/execution.py) — ligne 247 : `def _render_tca_panel(*, account_id: str | None, exec_run_id: str) -> None`
- [render](../../ihm/pages/execution.py) — ligne 272 : `def render() -> None`

## `ihm/pages/fundamentals.py`

Source SHA-256 : `f444cd038b485c2be8142839052ec507ef4a6125ae6a1ba4f6667a8072099e9a`

- [_load_fundamentals_summary](../../ihm/pages/fundamentals.py) — ligne 54 : `def _load_fundamentals_summary() -> pd.DataFrame`
- [_load_coverage_stats](../../ihm/pages/fundamentals.py) — ligne 105 : `def _load_coverage_stats() -> dict[str, Any]`
- [_load_sector_distribution](../../ihm/pages/fundamentals.py) — ligne 135 : `def _load_sector_distribution() -> pd.DataFrame`
- [fundamentals_page](../../ihm/pages/fundamentals.py) — ligne 171 : `def fundamentals_page() -> None`
- [render](../../ihm/pages/fundamentals.py) — ligne 474 : `def render() -> None`
- [_start_fundamentals_fetch_subprocess](../../ihm/pages/fundamentals.py) — ligne 495 : `def _start_fundamentals_fetch_subprocess(*, universe_mode: str, populate_provider: str, populate_overwrite: bool, fund_start_date: _date, fund_end_date: _date) -> None`
- [_drain_output_queue](../../ihm/pages/fundamentals.py) — ligne 615 : `def _drain_output_queue() -> None`
- [_render_live_fundamentals_fetch](../../ihm/pages/fundamentals.py) — ligne 631 : `def _render_live_fundamentals_fetch() -> None`
- [_render_fundamentals_fetch_results](../../ihm/pages/fundamentals.py) — ligne 684 : `def _render_fundamentals_fetch_results() -> None`
- [_clear_fundamentals_fetch_state](../../ihm/pages/fundamentals.py) — ligne 740 : `def _clear_fundamentals_fetch_state() -> None`

## `ihm/pages/glossary.py`

Source SHA-256 : `1cebf6484fc4882462edd2e431b11f7a2073c53a3469fc9a509242ece2aacb40`

- [_matches](../../ihm/pages/glossary.py) — ligne 18 : `def _matches(query: str, term: str, entry: dict) -> bool`
- [render](../../ihm/pages/glossary.py) — ligne 31 : `def render() -> None`

## `ihm/pages/market_regime.py`

Source SHA-256 : `9f4b037df4ecb171a13fd8cef976f874d7edb721a305063036c75ad5229de3c1`

- [_load_yaml](../../ihm/pages/market_regime.py) — ligne 36 : `def _load_yaml() -> dict[str, Any]`
- [_list_history](../../ihm/pages/market_regime.py) — ligne 44 : `def _list_history(limit: int=50) -> list[Path]`
- [_load_history_df](../../ihm/pages/market_regime.py) — ligne 51 : `def _load_history_df(limit: int=50) -> pd.DataFrame`
- [_compute_live_snapshot](../../ihm/pages/market_regime.py) — ligne 80 : `def _compute_live_snapshot(trade_date: _date, equity: float | None) -> dict[str, Any]`
- [_populate_macro_table](../../ihm/pages/market_regime.py) — ligne 111 : `def _populate_macro_table(start_date: _date, end_date: _date) -> dict[str, Any]`
- [_recompute_regime_table](../../ihm/pages/market_regime.py) — ligne 127 : `def _recompute_regime_table(start_date: _date, end_date: _date, equity: float | None) -> dict[str, Any]`
- [_format_macro_import_command](../../ihm/pages/market_regime.py) — ligne 144 : `def _format_macro_import_command(start_date: _date, end_date: _date) -> str`
- [_format_regime_recompute_command](../../ihm/pages/market_regime.py) — ligne 154 : `def _format_regime_recompute_command(start_date: _date, end_date: _date, equity: float | None) -> str`
- [_format_macro_runtime_context](../../ihm/pages/market_regime.py) — ligne 167 : `def _format_macro_runtime_context(yaml_cfg: dict[str, Any]) -> str`
- [_compute_demo_snapshot](../../ihm/pages/market_regime.py) — ligne 202 : `def _compute_demo_snapshot(scenario: str, trade_date: _date, equity: float | None) -> dict[str, Any]`
- [_render_summary](../../ihm/pages/market_regime.py) — ligne 279 : `def _render_summary(snap: dict[str, Any]) -> None`
- [_oracle_study_command](../../ihm/pages/market_regime.py) — ligne 398 : `def _oracle_study_command(start, end, source, batch_id, artifacts_dir, date_batch_size=20, resume=True, missing_returns_policy='partial') -> str`
- [_oracle_study_default_source_index](../../ihm/pages/market_regime.py) — ligne 414 : `def _oracle_study_default_source_index(sources) -> int`
- [_render_oracle_atr_study](../../ihm/pages/market_regime.py) — ligne 419 : `def _render_oracle_atr_study() -> None`
- [render](../../ihm/pages/market_regime.py) — ligne 509 : `def render() -> None`

## `ihm/pages/ml.py`

Source SHA-256 : `77908120480705cd7cf2f7a7555f7c9f173740d29df60daeacd126936bd2ddb2`

- [_sorted_non_empty_strings](../../ihm/pages/ml.py) — ligne 45 : `def _sorted_non_empty_strings(values: list[object], *, reverse: bool=False) -> list[str]`
- [_build_prediction_audit_filter_options](../../ihm/pages/ml.py) — ligne 50 : `def _build_prediction_audit_filter_options(audit_df: pd.DataFrame, governance_df: pd.DataFrame) -> dict[str, list[str]]`
- [_build_prediction_audit_navigation_options](../../ihm/pages/ml.py) — ligne 70 : `def _build_prediction_audit_navigation_options(audit_df: pd.DataFrame) -> list[dict[str, str]]`
- [_resolve_navigation_symbol](../../ihm/pages/ml.py) — ligne 102 : `def _resolve_navigation_symbol(navigation_option: dict[str, str], available_symbols: list[str]) -> str | None`
- [_match_navigation_row](../../ihm/pages/ml.py) — ligne 112 : `def _match_navigation_row(audit_df: pd.DataFrame, navigation_option: dict[str, str]) -> pd.Series`
- [_focus_dataframe_on_navigation_row](../../ihm/pages/ml.py) — ligne 130 : `def _focus_dataframe_on_navigation_row(audit_df: pd.DataFrame, navigation_option: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_build_section_export_frame](../../ihm/pages/ml.py) — ligne 144 : `def _build_section_export_frame(section: str, frame: pd.DataFrame) -> pd.DataFrame`
- [_build_ml_run_export_dataframe](../../ihm/pages/ml.py) — ligne 152 : `def _build_ml_run_export_dataframe(*, run_id: str, focused_audit_row: pd.DataFrame, run_governance: pd.DataFrame, run_audit_rows: pd.DataFrame, run_predictions: pd.DataFrame, artifact_report: dict[str, object] | None) -> pd.DataFrame`
- [_build_ml_run_export_filename](../../ihm/pages/ml.py) — ligne 197 : `def _build_ml_run_export_filename(run_id: str, symbol: str | None=None) -> str`
- [_build_ml_run_export_zip_filename](../../ihm/pages/ml.py) — ligne 203 : `def _build_ml_run_export_zip_filename(run_id: str, symbol: str | None=None) -> str`
- [_to_csv_bytes](../../ihm/pages/ml.py) — ligne 207 : `def _to_csv_bytes(df: pd.DataFrame) -> bytes`
- [_artifact_export_json_bytes](../../ihm/pages/ml.py) — ligne 213 : `def _artifact_export_json_bytes(artifact_report: dict[str, object] | None, *, key: str, path_key: str) -> bytes`
- [_build_ml_run_export_readme_bytes](../../ihm/pages/ml.py) — ligne 241 : `def _build_ml_run_export_readme_bytes(*, export_df: pd.DataFrame, artifact_report: dict[str, object] | None, focused_audit_row: pd.DataFrame, selected_navigation: dict[str, str] | None, exported_at: str, run_id: str, symbol: str | None) -> bytes`
- [_build_ml_run_export_zip_bytes](../../ihm/pages/ml.py) — ligne 314 : `def _build_ml_run_export_zip_bytes(*, export_df: pd.DataFrame, artifact_report: dict[str, object] | None, focused_audit_row: pd.DataFrame, selected_navigation: dict[str, str] | None, exported_at: str, run_id: str, symbol: str | None) -> bytes`
- [_summarize_prediction_governance_audit](../../ihm/pages/ml.py) — ligne 353 : `def _summarize_prediction_governance_audit(audit_df: pd.DataFrame) -> dict[str, object]`
- [_summarize_ml_runtime_status](../../ihm/pages/ml.py) — ligne 372 : `def _summarize_ml_runtime_status(predict_record: dict[str, object] | None, risk_record: dict[str, object] | None) -> dict[str, object]`
- [_summarize_governance_thresholds](../../ihm/pages/ml.py) — ligne 400 : `def _summarize_governance_thresholds(artifact_report: dict[str, object] | None) -> dict[str, object]`
- [_prime_selected_symbol_state](../../ihm/pages/ml.py) — ligne 431 : `def _prime_selected_symbol_state(symbols: list[str]) -> str | None`
- [_render_champion_walk_forward_stability](../../ihm/pages/ml.py) — ligne 448 : `def _render_champion_walk_forward_stability(report: dict[str, object]) -> None`
- [render](../../ihm/pages/ml.py) — ligne 547 : `def render() -> None`

## `ihm/pages/ml_diagnostics.py`

Source SHA-256 : `f1ae3090c131731a0996ab926884da7811c01c0fe35322ec96e5136da759a058`

- [_format_symbol_source](../../ihm/pages/ml_diagnostics.py) — ligne 53 : `def _format_symbol_source(value: object) -> str`
- [_profile_summary](../../ihm/pages/ml_diagnostics.py) — ligne 61 : `def _profile_summary(profile: object) -> tuple[str, int]`
- [_render_directional_bundle_overview](../../ihm/pages/ml_diagnostics.py) — ligne 71 : `def _render_directional_bundle_overview(batch_id: str, contract: dict[str, Any], batch_status: str) -> None`
- [_render_directional_candidate_download](../../ihm/pages/ml_diagnostics.py) — ligne 210 : `def _render_directional_candidate_download(batch_id: str, batch_status: str, metadata_json: object=None) -> None`
- [_get_batch_training_logs](../../ihm/pages/ml_diagnostics.py) — ligne 403 : `def _get_batch_training_logs(batch_id: str) -> str`
- [_cached_query](../../ihm/pages/ml_diagnostics.py) — ligne 446 : `def _cached_query(query: str, params: dict[str, Any] | None=None) -> pd.DataFrame`
- [_cached_global_rank_all](../../ihm/pages/ml_diagnostics.py) — ligne 452 : `def _cached_global_rank_all(batch_id: str, horizon: int) -> pd.DataFrame`
- [_cached_oracle_oos](../../ihm/pages/ml_diagnostics.py) — ligne 458 : `def _cached_oracle_oos(batch_id: str) -> tuple[str | None, pd.DataFrame]`
- [_run_strategy_backtest](../../ihm/pages/ml_diagnostics.py) — ligne 463 : `def _run_strategy_backtest(rank_df: pd.DataFrame, best_horizon: int=20, min_rising_horizons: int=_MIN_RISING_HORIZONS, horizon_scores: dict[int, float] | None=None) -> dict[str, dict[str, float]]`
- [_bold_wf_rows](../../ihm/pages/ml_diagnostics.py) — ligne 564 : `def _bold_wf_rows(df: pd.DataFrame)`
- [_global_rank_all_query](../../ihm/pages/ml_diagnostics.py) — ligne 1008 : `def _global_rank_all_query(horizon: int) -> str`
- [_load_directional_realized_dataset](../../ihm/pages/ml_diagnostics.py) — ligne 1144 : `def _load_directional_realized_dataset(batch_id: str) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_directional_metrics_row](../../ihm/pages/ml_diagnostics.py) — ligne 1216 : `def _directional_metrics_row(side: str, horizon: int, result: dict[str, Any]) -> dict[str, object]`
- [_render_directional_side_detail](../../ihm/pages/ml_diagnostics.py) — ligne 1234 : `def _render_directional_side_detail(side: str, horizon: int, result: dict[str, Any]) -> None`
- [_render_directional_prediction_performance](../../ihm/pages/ml_diagnostics.py) — ligne 1318 : `def _render_directional_prediction_performance(batch_id: str) -> None`
- [_selected_row_index](../../ihm/pages/ml_diagnostics.py) — ligne 1514 : `def _selected_row_index(table_key: str) -> int | None`
- [_status_badge](../../ihm/pages/ml_diagnostics.py) — ligne 1530 : `def _status_badge(status: str) -> str`
- [_render_symbol_detail](../../ihm/pages/ml_diagnostics.py) — ligne 1540 : `def _render_symbol_detail(batch_id: str, symbol: str, model_role: str | None=None) -> None`
- [_classify_regime](../../ihm/pages/ml_diagnostics.py) — ligne 1660 : `def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str`
- [_render_regime_table](../../ihm/pages/ml_diagnostics.py) — ligne 1679 : `def _render_regime_table(batch_id: str, model_role: str | None=None) -> None`
- [_is_safe_batch_id](../../ihm/pages/ml_diagnostics.py) — ligne 1821 : `def _is_safe_batch_id(batch_id: str) -> bool`
- [_render_delete_batch_button](../../ihm/pages/ml_diagnostics.py) — ligne 1834 : `def _render_delete_batch_button(selected_batch: str, artifacts_dir: Path) -> None`
- [_batch_trains_oracle](../../ihm/pages/ml_diagnostics.py) — ligne 2031 : `def _batch_trains_oracle(batch: pd.Series) -> bool`
- [_oracle_periods](../../ihm/pages/ml_diagnostics.py) — ligne 2057 : `def _oracle_periods(batch_id: str) -> list[dict[str, Any]]`
- [_load_latest_oracle_oos](../../ihm/pages/ml_diagnostics.py) — ligne 2084 : `def _load_latest_oracle_oos(batch_id: str) -> tuple[str | None, pd.DataFrame]`
- [_batch_best_horizon](../../ihm/pages/ml_diagnostics.py) — ligne 2104 : `def _batch_best_horizon(batch_id: str) -> int`
- [_oracle_labels_worker](../../ihm/pages/ml_diagnostics.py) — ligne 2135 : `def _oracle_labels_worker(batch_id: str, horizon: int, strict: bool) -> None`
- [_launch_oracle_job](../../ihm/pages/ml_diagnostics.py) — ligne 2167 : `def _launch_oracle_job(batch_id: str, horizon: int, *, strict: bool) -> None`
- [_render_build_oracle_labels_button](../../ihm/pages/ml_diagnostics.py) — ligne 2181 : `def _render_build_oracle_labels_button(batch_id: str, horizon: int, *, for_oracle_extreme: bool=False) -> None`
- [_render_oracle_distribution](../../ihm/pages/ml_diagnostics.py) — ligne 2321 : `def _render_oracle_distribution(batch_id: str, row: pd.Series) -> None`
- [_oracle_split_table](../../ihm/pages/ml_diagnostics.py) — ligne 2535 : `def _oracle_split_table(picks: pd.DataFrame) -> dict[str, Any] | None`
- [_oracle_direction_split](../../ihm/pages/ml_diagnostics.py) — ligne 2561 : `def _oracle_direction_split(df: pd.DataFrame) -> dict[str, Any] | None`
- [_oracle_omniscient_split](../../ihm/pages/ml_diagnostics.py) — ligne 2588 : `def _oracle_omniscient_split(df: pd.DataFrame, top_pct: float=0.1) -> dict[str, Any] | None`
- [_render_oracle_quality](../../ihm/pages/ml_diagnostics.py) — ligne 2621 : `def _render_oracle_quality(batch_id: str, row: pd.Series) -> None`
- [_render_prediction_periods](../../ihm/pages/ml_diagnostics.py) — ligne 2822 : `def _render_prediction_periods(batch_id: str, batch: pd.Series) -> None`
- [_render_batch_detail](../../ihm/pages/ml_diagnostics.py) — ligne 3100 : `def _render_batch_detail(batch: pd.Series) -> None`
- [_render_global_rank_history](../../ihm/pages/ml_diagnostics.py) — ligne 3768 : `def _render_global_rank_history(batch_id: str) -> None`
- [_render_global_ranking_horizon_details](../../ihm/pages/ml_diagnostics.py) — ligne 3904 : `def _render_global_ranking_horizon_details(row: pd.Series) -> None`
- [_split_group_from_comment](../../ihm/pages/ml_diagnostics.py) — ligne 4172 : `def _split_group_from_comment(comment: str) -> tuple[str, str]`
- [render](../../ihm/pages/ml_diagnostics.py) — ligne 4195 : `def render() -> None`

## `ihm/pages/ops_infra.py`

Source SHA-256 : `00bf0118226fb3386bab5005abe1f5d164d59aec65279069e586cf2ef469ebb1`

- [_render_metrics_panel](../../ihm/pages/ops_infra.py) — ligne 56 : `def _render_metrics_panel() -> None`
- [_list_existing_archives](../../ihm/pages/ops_infra.py) — ligne 231 : `def _list_existing_archives(dest_dir_str: str, pattern: str='*.tar.gz') -> list[Path]`
- [_render_backup_ml_panel](../../ihm/pages/ops_infra.py) — ligne 242 : `def _render_backup_ml_panel(*, db_config: dict) -> None`
- [_render_backup_db_panel](../../ihm/pages/ops_infra.py) — ligne 347 : `def _render_backup_db_panel(*, db_config: dict) -> None`
- [_render_reset_ml_panel](../../ihm/pages/ops_infra.py) — ligne 463 : `def _render_reset_ml_panel() -> None`
- [_run_reset_ml_with_logs](../../ihm/pages/ops_infra.py) — ligne 525 : `def _run_reset_ml_with_logs(*, stop_active: bool=False, runs_only: bool=False) -> None`
- [_render_reset_ml_report](../../ihm/pages/ops_infra.py) — ligne 606 : `def _render_reset_ml_report(report: dict[str, object]) -> None`
- [render](../../ihm/pages/ops_infra.py) — ligne 656 : `def render() -> None`

## `ihm/pages/overview.py`

Source SHA-256 : `602ed230d1c53832cf76d47b6d1ea0cf96d7934676bd28d96f75e3ac4d066936`

- [_pipeline_summary_label](../../ihm/pages/overview.py) — ligne 47 : `def _pipeline_summary_label(step) -> str`
- [_coerce_float](../../ihm/pages/overview.py) — ligne 51 : `def _coerce_float(value: object, default: float=0.0) -> float`
- [_coerce_int](../../ihm/pages/overview.py) — ligne 58 : `def _coerce_int(value: object, default: int=0) -> int`
- [compute_daily_pnl](../../ihm/pages/overview.py) — ligne 70 : `def compute_daily_pnl(pnl_data: dict[str, object]) -> tuple[float, float]`
- [_render_pnl_widget](../../ihm/pages/overview.py) — ligne 89 : `def _render_pnl_widget(pnl_data: dict[str, object]) -> None`
- [_merge_pipeline_runs](../../ihm/pages/overview.py) — ligne 123 : `def _merge_pipeline_runs() -> list[dict[str, object]]`
- [_build_pipeline_summary_rows](../../ihm/pages/overview.py) — ligne 134 : `def _build_pipeline_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame`
- [_build_screener_history_dataframe](../../ihm/pages/overview.py) — ligne 149 : `def _build_screener_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame`
- [_build_screener_objective_rows](../../ihm/pages/overview.py) — ligne 153 : `def _build_screener_objective_rows(report: dict[str, object]) -> pd.DataFrame`
- [_build_screener_objective_metrics](../../ihm/pages/overview.py) — ligne 171 : `def _build_screener_objective_metrics(report: dict[str, object]) -> list[tuple[str, str, str | None]]`
- [load_eodhd_quota_snapshot](../../ihm/pages/overview.py) — ligne 181 : `def load_eodhd_quota_snapshot() -> dict[str, object]`
- [_build_eodhd_quota_feature_rows](../../ihm/pages/overview.py) — ligne 194 : `def _build_eodhd_quota_feature_rows(snapshot: dict[str, object]) -> pd.DataFrame`
- [render](../../ihm/pages/overview.py) — ligne 212 : `def render() -> None`

## `ihm/pages/parity.py`

Source SHA-256 : `6c59fb7391afd08452ddf29eb6bb3826d8198b89140800ec48cc1fee38f146f2`

- [_list_available_dates](../../ihm/pages/parity.py) — ligne 26 : `def _list_available_dates(root: Path=PARITY_ROOT) -> list[str]`
- [_load_summary](../../ihm/pages/parity.py) — ligne 36 : `def _load_summary(trade_date: str, root: Path=PARITY_ROOT) -> dict | None`
- [load_rolling_summaries](../../ihm/pages/parity.py) — ligne 47 : `def load_rolling_summaries(*, root: Path=PARITY_ROOT, window: int=30) -> list[dict[str, Any]]`
- [aggregate_top_divergent_symbols](../../ihm/pages/parity.py) — ligne 64 : `def aggregate_top_divergent_symbols(summaries: list[dict[str, Any]], *, top_n: int=20, threshold: float=0.0) -> list[dict[str, Any]]`
- [_badge_color](../../ihm/pages/parity.py) — ligne 110 : `def _badge_color(score: float, threshold: float=0.1) -> str`
- [_render_rolling_section](../../ihm/pages/parity.py) — ligne 118 : `def _render_rolling_section(st, pd, summaries: list[dict[str, Any]]) -> None`
- [_render_symbol_drilldown](../../ihm/pages/parity.py) — ligne 167 : `def _render_symbol_drilldown(st, pd, summaries: list[dict[str, Any]]) -> None`
- [render](../../ihm/pages/parity.py) — ligne 198 : `def render() -> None`

## `ihm/pages/pipeline.py`

Source SHA-256 : `47cf64896c8f785b8ffb2303c79829c7d888a3a82609815ca65fd99263239c58`

- [_coerce_ui_date](../../ihm/pages/pipeline.py) — ligne 171 : `def _coerce_ui_date(value: object, *, fallback: date) -> date`
- [_trade_date_or_today](../../ihm/pages/pipeline.py) — ligne 182 : `def _trade_date_or_today(options: PipelineLaunchOptions) -> date`
- [_resolve_data_integrity_scope_preview](../../ihm/pages/pipeline.py) — ligne 193 : `def _resolve_data_integrity_scope_preview(symbol_source: str, start_symbol: str | None=None) -> dict[str, object]`
- [_is_large_quote_history_run](../../ihm/pages/pipeline.py) — ligne 204 : `def _is_large_quote_history_run(estimate: dict[str, object] | None) -> bool`
- [_coerce_int_metric](../../ihm/pages/pipeline.py) — ligne 210 : `def _coerce_int_metric(value: object, *, default: int=0) -> int`
- [_coerce_float_metric](../../ihm/pages/pipeline.py) — ligne 217 : `def _coerce_float_metric(value: object, *, default: float=0.0) -> float`
- [_resolve_latest_selectbox_value](../../ihm/pages/pipeline.py) — ligne 224 : `def _resolve_latest_selectbox_value(widget_key: str, widget_value: object, *, default: str, allowed_values: tuple[str, ...]) -> str`
- [_render_period_sync_block](../../ihm/pages/pipeline.py) — ligne 240 : `def _render_period_sync_block(step_key: str, options: PipelineLaunchOptions, *, workflow_active: bool, active_for_step: list[dict[str, object]], db_config: dict[str, str | None], all_runs: list[dict[str, object]]) -> None`
- [_render_tradable_universe_publish_block](../../ihm/pages/pipeline.py) — ligne 483 : `def _render_tradable_universe_publish_block(options: PipelineLaunchOptions, *, workflow_active: bool, active_for_step: list[dict[str, object]], db_config: dict[str, str | None], all_runs: list[dict[str, object]]) -> None`
- [_build_execution_mode_banner_payload](../../ihm/pages/pipeline.py) — ligne 713 : `def _build_execution_mode_banner_payload(options: PipelineLaunchOptions, *, detected_broker_mode: str | None=None) -> tuple[str, str]`
- [_build_execution_account_banner_payload](../../ihm/pages/pipeline.py) — ligne 753 : `def _build_execution_account_banner_payload(options: PipelineLaunchOptions, *, detected_account_type: str | None=None) -> tuple[str, str]`
- [_build_fractional_trading_banner_payload](../../ihm/pages/pipeline.py) — ligne 799 : `def _build_fractional_trading_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]`
- [_build_capital_preset_banner_payload](../../ihm/pages/pipeline.py) — ligne 815 : `def _build_capital_preset_banner_payload(selected_preset_key: str | None, *, detected_preset_key: str | None=None, detected_equity: float | None=None) -> tuple[str, str] | None`
- [_build_execution_protection_banner_payload](../../ihm/pages/pipeline.py) — ligne 848 : `def _build_execution_protection_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]`
- [_build_live_risk_guard_banner_payload](../../ihm/pages/pipeline.py) — ligne 869 : `def _build_live_risk_guard_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]`
- [_build_long_only_banner_payload](../../ihm/pages/pipeline.py) — ligne 893 : `def _build_long_only_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str] | None`
- [_build_pipeline_scope_alert_lines](../../ihm/pages/pipeline.py) — ligne 916 : `def _build_pipeline_scope_alert_lines() -> tuple[str, str]`
- [_render_execution_mode_banner](../../ihm/pages/pipeline.py) — ligne 923 : `def _render_execution_mode_banner(options: PipelineLaunchOptions) -> None`
- [_build_universe_banner_payload](../../ihm/pages/pipeline.py) — ligne 970 : `def _build_universe_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]`
- [_build_swing_only_banner_payload](../../ihm/pages/pipeline.py) — ligne 1006 : `def _build_swing_only_banner_payload(options: PipelineLaunchOptions) -> tuple[str, str]`
- [_render_ml_inspection_link](../../ihm/pages/pipeline.py) — ligne 1026 : `def _render_ml_inspection_link(step_key: str) -> None`
- [_resolve_ml_train_scope_preview](../../ihm/pages/pipeline.py) — ligne 1047 : `def _resolve_ml_train_scope_preview(symbol_source: str, *, start_date: date | None=None, end_date: date | None=None) -> dict[str, object]`
- [_render_ml_scope_block](../../ihm/pages/pipeline.py) — ligne 1068 : `def _render_ml_scope_block(options: PipelineLaunchOptions, *, workflow_active: bool, active_for_step: list[dict[str, object]], db_config: dict[str, str | None], all_runs: list[dict[str, object]], step_key: str, selectbox_key: str, button_key: str, button_label: str, label_prefix: str, source_attr: str, start_symbol_attr: str | None=None, historical_range: bool=False, comment_session_key: str | None=None) -> None`
- [_ml_prediction_scope_options](../../ihm/pages/pipeline.py) — ligne 1239 : `def _ml_prediction_scope_options(options: PipelineLaunchOptions) -> PipelineLaunchOptions`
- [_render_ml_train_scope_block](../../ihm/pages/pipeline.py) — ligne 1249 : `def _render_ml_train_scope_block(options: PipelineLaunchOptions, *, workflow_active: bool, active_for_step: list[dict[str, object]], db_config: dict[str, str | None], all_runs: list[dict[str, object]]) -> None`
- [_render_ml_predict_scope_block](../../ihm/pages/pipeline.py) — ligne 1275 : `def _render_ml_predict_scope_block(options: PipelineLaunchOptions, *, workflow_active: bool, active_for_step: list[dict[str, object]], db_config: dict[str, str | None], all_runs: list[dict[str, object]]) -> None`
- [_build_pipeline_run_context](../../ihm/pages/pipeline.py) — ligne 1424 : `def _build_pipeline_run_context() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, object]], bool, dict[str, list[dict[str, object]]]]`
- [_normalize_pipeline_run_status](../../ihm/pages/pipeline.py) — ligne 1443 : `def _normalize_pipeline_run_status(value: object) -> str`
- [_safe_iterable](../../ihm/pages/pipeline.py) — ligne 1447 : `def _safe_iterable(value: object) -> list[object]`
- [_previous_pipeline_step_key](../../ihm/pages/pipeline.py) — ligne 1453 : `def _previous_pipeline_step_key(step_key: str) -> str | None`
- [_pipeline_state_machine_lock_reason](../../ihm/pages/pipeline.py) — ligne 1464 : `def _pipeline_state_machine_lock_reason(step_key: str, latest_by_step: dict[str, dict[str, object]]) -> str | None`
- [_render_live_execution_freeze_banner](../../ihm/pages/pipeline.py) — ligne 1490 : `def _render_live_execution_freeze_banner(live_guard: dict[str, object]) -> None`
- [_render_launchable_step_panel](../../ihm/pages/pipeline.py) — ligne 1502 : `def _render_launchable_step_panel(step: Any, options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None], *, workflow_active: bool, active_by_step: dict[str, list[dict[str, object]]], all_runs: list[dict[str, object]], latest_by_step: dict[str, dict[str, object]], dependency_diagnostic: dict[str, object] | None, live_guard: dict[str, object]) -> None`
- [_render_step_panels](../../ihm/pages/pipeline.py) — ligne 1772 : `def _render_step_panels(options: PipelineLaunchOptions, live_confirmed: bool, db_config: dict[str, str | None], live_guard: dict[str, object]) -> None`
- [render](../../ihm/pages/pipeline.py) — ligne 1824 : `def render() -> None`

## `ihm/pages/risk.py`

Source SHA-256 : `11f69c9194a1710ce13d772b067b279bce661be7ccd4be8c6605e91a11a02eaf`

- [_render_ml_gate_status](../../ihm/pages/risk.py) — ligne 21 : `def _render_ml_gate_status(record: dict[str, object] | None) -> None`
- [_render_shadow_compare](../../ihm/pages/risk.py) — ligne 55 : `def _render_shadow_compare(summary: dict[str, object], selected_run: str | None) -> None`
- [_render_postmortem_artifacts](../../ihm/pages/risk.py) — ligne 98 : `def _render_postmortem_artifacts(summary: dict[str, object]) -> None`
- [render](../../ihm/pages/risk.py) — ligne 123 : `def render() -> None`

## `ihm/pages/sandbox_health.py`

Source SHA-256 : `74b1170d1cbbeeb58c06ae764434b6793a2d399f6325ae48235f197cc2d193d5`

- [_streak_level](../../ihm/pages/sandbox_health.py) — ligne 24 : `def _streak_level(green: int) -> str`
- [render](../../ihm/pages/sandbox_health.py) — ligne 32 : `def render() -> None`

## `ihm/pages/screening.py`

Source SHA-256 : `4611c069be91b462aa1d111b397b6bbf47c258b6ee45841109c3c2abca6a2810`

- [_quality_summary_label](../../ihm/pages/screening.py) — ligne 45 : `def _quality_summary_label(step) -> str`
- [_merge_pipeline_runs](../../ihm/pages/screening.py) — ligne 49 : `def _merge_pipeline_runs() -> list[dict[str, object]]`
- [_build_quality_summary_rows](../../ihm/pages/screening.py) — ligne 60 : `def _build_quality_summary_rows(runs: list[dict[str, object]]) -> pd.DataFrame`
- [_build_artifact_history_dataframe](../../ihm/pages/screening.py) — ligne 75 : `def _build_artifact_history_dataframe(history_entries: list[dict[str, object]]) -> pd.DataFrame`
- [_build_objective_recommendation_rows](../../ihm/pages/screening.py) — ligne 79 : `def _build_objective_recommendation_rows(report: dict[str, object]) -> pd.DataFrame`
- [_build_objective_metric_cards](../../ihm/pages/screening.py) — ligne 97 : `def _build_objective_metric_cards(report: dict[str, object]) -> list[tuple[str, str, str | None]]`
- [_format_csv_preview_option](../../ihm/pages/screening.py) — ligne 114 : `def _format_csv_preview_option(file_info: dict[str, object]) -> str`
- [_build_csv_preview_inventory_dataframe](../../ihm/pages/screening.py) — ligne 122 : `def _build_csv_preview_inventory_dataframe(files: list[dict[str, object]]) -> pd.DataFrame`
- [_build_screening_display_dataframe](../../ihm/pages/screening.py) — ligne 138 : `def _build_screening_display_dataframe(df: pd.DataFrame) -> pd.DataFrame`
- [_resolve_selection_explainability_payload](../../ihm/pages/screening.py) — ligne 162 : `def _resolve_selection_explainability_payload(row: pd.Series) -> dict[str, object]`
- [_render_screener_csv_preview](../../ihm/pages/screening.py) — ligne 169 : `def _render_screener_csv_preview(artifacts_dir: str, selected_entry: dict[str, object]) -> None`
- [_render_objective_recommendations](../../ihm/pages/screening.py) — ligne 250 : `def _render_objective_recommendations(artifacts_dir: str) -> None`
- [render](../../ihm/pages/screening.py) — ligne 290 : `def render() -> None`

## `ihm/pages/settings.py`

Source SHA-256 : `4ec79abcbc4ab37174f60ed87280dd7fc2d362434c6e368578a44efffe4fcfd7`

- [_build_micro_capital_preset_warning_message](../../ihm/pages/settings.py) — ligne 142 : `def _build_micro_capital_preset_warning_message() -> str | None`
- [_render_capital_preset_warning_banner](../../ihm/pages/settings.py) — ligne 153 : `def _render_capital_preset_warning_banner() -> None`
- [_flash_message](../../ihm/pages/settings.py) — ligne 159 : `def _flash_message(kind: str, message: str) -> None`
- [_market_regime_label](../../ihm/pages/settings.py) — ligne 170 : `def _market_regime_label(value: str) -> str`
- [_preset_style_label](../../ihm/pages/settings.py) — ligne 174 : `def _preset_style_label(value: str) -> str`
- [_prime_bars_provider_widget_state](../../ihm/pages/settings.py) — ligne 178 : `def _prime_bars_provider_widget_state(current: str) -> str`
- [_render_bars_provider_settings](../../ihm/pages/settings.py) — ligne 194 : `def _render_bars_provider_settings()`
- [_threshold_widget_key](../../ihm/pages/settings.py) — ligne 274 : `def _threshold_widget_key(step_key: str, metric_key: str) -> str`
- [_apply_alpha_scanner_dependency_threshold_state_to_session](../../ihm/pages/settings.py) — ligne 278 : `def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds)`
- [_prime_alpha_scanner_dependency_threshold_state](../../ihm/pages/settings.py) — ligne 284 : `def _prime_alpha_scanner_dependency_threshold_state()`
- [_collect_alpha_scanner_dependency_threshold_inputs](../../ihm/pages/settings.py) — ligne 306 : `def _collect_alpha_scanner_dependency_threshold_inputs()`
- [_set_alpha_scanner_dependency_threshold_state](../../ihm/pages/settings.py) — ligne 316 : `def _set_alpha_scanner_dependency_threshold_state(thresholds)`
- [_apply_alpha_scanner_threshold_preset](../../ihm/pages/settings.py) — ligne 320 : `def _apply_alpha_scanner_threshold_preset(style: str, market_regime: str)`
- [_render_alpha_scanner_dependency_threshold_settings](../../ihm/pages/settings.py) — ligne 343 : `def _render_alpha_scanner_dependency_threshold_settings()`
- [_get_notifications_failure_log_download_payload](../../ihm/pages/settings.py) — ligne 511 : `def _get_notifications_failure_log_download_payload()`
- [_build_smtp_not_configured_warning_message](../../ihm/pages/settings.py) — ligne 518 : `def _build_smtp_not_configured_warning_message(smtp_cfg) -> str | None`
- [_build_var_env_upload_signature](../../ihm/pages/settings.py) — ligne 527 : `def _build_var_env_upload_signature(file_name: str, file_bytes: bytes) -> str`
- [_prepare_var_env_export](../../ihm/pages/settings.py) — ligne 532 : `def _prepare_var_env_export()`
- [_render_environment_variable_settings](../../ihm/pages/settings.py) — ligne 542 : `def _render_environment_variable_settings()`
- [_render_notifications_settings](../../ihm/pages/settings.py) — ligne 639 : `def _render_notifications_settings()`
- [_build_telegram_not_configured_warning_message](../../ihm/pages/settings.py) — ligne 771 : `def _build_telegram_not_configured_warning_message() -> str | None`
- [_render_telegram_notifications_settings](../../ihm/pages/settings.py) — ligne 781 : `def _render_telegram_notifications_settings() -> None`
- [_check_import](../../ihm/pages/settings.py) — ligne 860 : `def _check_import(name: str) -> str`
- [render](../../ihm/pages/settings.py) — ligne 868 : `def render()`

## `ihm/pages/supervision_ops.py`

Source SHA-256 : `b5c9f0865c7c6065a3ff579d5349531cf9a0c56ef03b710458210160ebbe7e0f`

- [_tail_text](../../ihm/pages/supervision_ops.py) — ligne 35 : `def _tail_text(content: str, max_lines: int=WATCHER_LOG_TAIL_LINES) -> str`
- [_render_log_block](../../ihm/pages/supervision_ops.py) — ligne 42 : `def _render_log_block(title: str, content: str, *, key: str, expanded: bool=False) -> None`
- [_render_selected_watcher_run](../../ihm/pages/supervision_ops.py) — ligne 55 : `def _render_selected_watcher_run(record: dict[str, object] | None, *, run_id: str, log_filter: str) -> None`
- [_render_selected_windows_log_source](../../ihm/pages/supervision_ops.py) — ligne 93 : `def _render_selected_windows_log_source(log_sources_df, *, source_name: str) -> None`
- [_render_watcher_runtime_observability](../../ihm/pages/supervision_ops.py) — ligne 124 : `def _render_watcher_runtime_observability(*, account_id: str | None) -> None`
- [_render_windows_runtime_observability](../../ihm/pages/supervision_ops.py) — ligne 182 : `def _render_windows_runtime_observability(*, account_id: str | None) -> None`
- [_render_windows_integration_panel](../../ihm/pages/supervision_ops.py) — ligne 215 : `def _render_windows_integration_panel(*, snapshot: dict[str, object]) -> None`
- [_render_coverage_artifact_panel](../../ihm/pages/supervision_ops.py) — ligne 231 : `def _render_coverage_artifact_panel(*, snapshot: dict[str, object]) -> None`
- [_restart_button_label](../../ihm/pages/supervision_ops.py) — ligne 252 : `def _restart_button_label(control_state: dict[str, object]) -> str`
- [_render_watcher_ops_controls](../../ihm/pages/supervision_ops.py) — ligne 256 : `def _render_watcher_ops_controls(*, account_id: str | None, snapshot: dict[str, object]) -> None`
- [render](../../ihm/pages/supervision_ops.py) — ligne 465 : `def render() -> None`

## `ihm/pages/tax_compliance.py`

Source SHA-256 : `62c0ad3012567b4256ef57b363140c7aa75df9bcf15c4134fc0e13f26f2365ad`

- [render](../../ihm/pages/tax_compliance.py) — ligne 25 : `def render() -> None`

## `ihm/pages/weights_calibration_runs.py`

Source SHA-256 : `893efaff2aa710349f1ef826d680d1968c34edd59a918a560fc0b45cf217c302`

- [_parse_json_payload](../../ihm/pages/weights_calibration_runs.py) — ligne 16 : `def _parse_json_payload(value: object) -> dict[str, object] | list[object]`
- [_build_candidates_frame](../../ihm/pages/weights_calibration_runs.py) — ligne 35 : `def _build_candidates_frame(value: object) -> pd.DataFrame`
- [_build_overview_metrics](../../ihm/pages/weights_calibration_runs.py) — ligne 52 : `def _build_overview_metrics(df: pd.DataFrame) -> dict[str, object]`
- [_prepare_drift_frames](../../ihm/pages/weights_calibration_runs.py) — ligne 83 : `def _prepare_drift_frames(df: pd.DataFrame, *, selected_run_id: str | None=None) -> dict[str, pd.DataFrame]`
- [_build_drift_metrics](../../ihm/pages/weights_calibration_runs.py) — ligne 137 : `def _build_drift_metrics(df: pd.DataFrame) -> dict[str, object]`
- [_build_drift_chart_frames](../../ihm/pages/weights_calibration_runs.py) — ligne 166 : `def _build_drift_chart_frames(all_drifts: pd.DataFrame, *, selected_drifts: pd.DataFrame | None=None) -> dict[str, pd.DataFrame]`
- [render](../../ihm/pages/weights_calibration_runs.py) — ligne 273 : `def render() -> None`

## `ihm/services/__init__.py`

Source SHA-256 : `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `ihm/services/account_defaults.py`

Source SHA-256 : `5438be6fab6f99f0df9373e7cf69ff9ecef94b232c6528b08c76441bf82bfd5f`

- [PipelineExecutionDefaults](../../ihm/services/account_defaults.py) — ligne 14 : `class PipelineExecutionDefaults`
- [_safe_float](../../ihm/services/account_defaults.py) — ligne 24 : `def _safe_float(value: object) -> float | None`
- [_extract_equity](../../ihm/services/account_defaults.py) — ligne 31 : `def _extract_equity(snapshot: dict[str, object]) -> float | None`
- [_infer_account_type](../../ihm/services/account_defaults.py) — ligne 35 : `def _infer_account_type(snapshot: dict[str, object]) -> Literal['margin', 'cash'] | None`
- [get_pipeline_execution_defaults](../../ihm/services/account_defaults.py) — ligne 48 : `def get_pipeline_execution_defaults(account_id: str | None) -> PipelineExecutionDefaults | None`
- [_get_pipeline_execution_defaults_impl](../../ihm/services/account_defaults.py) — ligne 59 : `def _get_pipeline_execution_defaults_impl(account_id: str | None) -> PipelineExecutionDefaults | None`

## `ihm/services/alpaca_accounts.py`

Source SHA-256 : `b463d7756d28ea7c06cbc28af125c89f01c618630e5acbd98af03c9660d823c2`

- [get_registered_accounts](../../ihm/services/alpaca_accounts.py) — ligne 15 : `def get_registered_accounts() -> list[BrokerAccount]`
- [resolve_selected_account_id](../../ihm/services/alpaca_accounts.py) — ligne 19 : `def resolve_selected_account_id(preferred_account_id: str | None=None) -> str | None`
- [build_account_label](../../ihm/services/alpaca_accounts.py) — ligne 30 : `def build_account_label(account: BrokerAccount) -> str`
- [_build_client](../../ihm/services/alpaca_accounts.py) — ligne 34 : `def _build_client(account_id: str) -> AlpacaTradingClient`
- [get_live_account](../../ihm/services/alpaca_accounts.py) — ligne 43 : `def get_live_account(account_id: str) -> dict[str, Any]`
- [close_position_all](../../ihm/services/alpaca_accounts.py) — ligne 48 : `def close_position_all(account_id: str, symbol: str) -> dict[str, Any]`
- [get_live_positions](../../ihm/services/alpaca_accounts.py) — ligne 62 : `def get_live_positions(account_id: str) -> pd.DataFrame`
- [get_live_orders](../../ihm/services/alpaca_accounts.py) — ligne 92 : `def get_live_orders(account_id: str, limit: int=_DEFAULT_ORDER_LIMIT) -> pd.DataFrame`
- [get_live_portfolio_history](../../ihm/services/alpaca_accounts.py) — ligne 130 : `def get_live_portfolio_history(account_id: str, *, period: str='1M', timeframe: str='1D') -> pd.DataFrame`

## `ihm/services/alpha_scanner_threshold_presets.py`

Source SHA-256 : `3c769f13807e2ca4fa5eec3ec52add3081e1da28b565320cb19336056b36c599`

- [_clamp_threshold](../../ihm/services/alpha_scanner_threshold_presets.py) — ligne 121 : `def _clamp_threshold(metric_key: str, value: float) -> float`
- [get_alpha_scanner_threshold_preset](../../ihm/services/alpha_scanner_threshold_presets.py) — ligne 129 : `def get_alpha_scanner_threshold_preset(*, style: PresetStyle, market_regime: MarketRegime) -> dict[str, dict[str, float]]`

## `ihm/services/backtesting_registry.py`

Source SHA-256 : `da21e9f14a77f10b78ba10f3416a3374f9faae2a57e1b9b4e717dfe543523091`

- [BacktestingRunRecord](../../ihm/services/backtesting_registry.py) — ligne 52 : `class BacktestingRunRecord`
- [BacktestingRunRecord.to_state](../../ihm/services/backtesting_registry.py) — ligne 73 : `def to_state(self) -> dict[str, object]`
- [_ManagedRun](../../ihm/services/backtesting_registry.py) — ligne 78 : `class _ManagedRun`
- [_ManagedRun.__post_init__](../../ihm/services/backtesting_registry.py) — ligne 91 : `def __post_init__(self) -> None`
- [_ensure_storage](../../ihm/services/backtesting_registry.py) — ligne 102 : `def _ensure_storage() -> None`
- [_append_tail](../../ihm/services/backtesting_registry.py) — ligne 108 : `def _append_tail(target: list[str], line: str) -> None`
- [_read_history_index](../../ihm/services/backtesting_registry.py) — ligne 114 : `def _read_history_index() -> dict[str, dict[str, object]]`
- [_write_history_index](../../ihm/services/backtesting_registry.py) — ligne 122 : `def _write_history_index(payload: dict[str, dict[str, object]]) -> None`
- [_persist_record](../../ihm/services/backtesting_registry.py) — ligne 127 : `def _persist_record(record: BacktestingRunRecord) -> None`
- [_reader](../../ihm/services/backtesting_registry.py) — ligne 134 : `def _reader(stream: subprocess.PIPE | None, stream_name: str, events: queue.Queue[tuple[str, str]]) -> None`
- [_creation_flags](../../ihm/services/backtesting_registry.py) — ligne 144 : `def _creation_flags() -> int`
- [_kill_process_tree](../../ihm/services/backtesting_registry.py) — ligne 150 : `def _kill_process_tree(process: subprocess.Popen[str]) -> None`
- [_kill_process_tree_by_pid](../../ihm/services/backtesting_registry.py) — ligne 164 : `def _kill_process_tree_by_pid(pid: int) -> None`
- [_parse_iso_datetime](../../ihm/services/backtesting_registry.py) — ligne 182 : `def _parse_iso_datetime(value: object) -> datetime | None`
- [_compute_elapsed_seconds](../../ihm/services/backtesting_registry.py) — ligne 192 : `def _compute_elapsed_seconds(executed_at: object) -> float`
- [_find_backtesting_run_dir](../../ihm/services/backtesting_registry.py) — ligne 199 : `def _find_backtesting_run_dir(run_id: str, run_kind: str | None=None) -> Path | None`
- [_find_active_backtesting_lock](../../ihm/services/backtesting_registry.py) — ligne 215 : `def _find_active_backtesting_lock(run_id: str | None=None) -> dict[str, object] | None`
- [_build_recovered_snapshot_from_lock](../../ihm/services/backtesting_registry.py) — ligne 227 : `def _build_recovered_snapshot_from_lock(payload: dict[str, object]) -> dict[str, object]`
- [_with_updates](../../ihm/services/backtesting_registry.py) — ligne 271 : `def _with_updates(record: BacktestingRunRecord, **updates: object) -> BacktestingRunRecord`
- [_append_to_log](../../ihm/services/backtesting_registry.py) — ligne 277 : `def _append_to_log(path_raw: str, text: str) -> None`
- [_drain_events](../../ihm/services/backtesting_registry.py) — ligne 300 : `def _drain_events(managed: _ManagedRun) -> bool`
- [_finalize_if_needed](../../ihm/services/backtesting_registry.py) — ligne 330 : `def _finalize_if_needed(managed: _ManagedRun) -> BacktestingRunRecord`
- [_tail_text](../../ihm/services/backtesting_registry.py) — ligne 389 : `def _tail_text(lines: list[str]) -> str`
- [_read_text_tail](../../ihm/services/backtesting_registry.py) — ligne 393 : `def _read_text_tail(path: Path, max_lines: int) -> str`
- [_run_dir_for](../../ihm/services/backtesting_registry.py) — ligne 414 : `def _run_dir_for(run_kind: BacktestingCommandKind, run_id: str) -> Path`
- [_resolve_screener_artifacts_dir](../../ihm/services/backtesting_registry.py) — ligne 418 : `def _resolve_screener_artifacts_dir(run_kind: BacktestingCommandKind, options: BacktestRunOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions) -> str | None`
- [_ensure_db_ready_for_run](../../ihm/services/backtesting_registry.py) — ligne 433 : `def _ensure_db_ready_for_run(run_kind: BacktestingCommandKind, db_config: dict[str, str | None] | None) -> None`
- [list_active_backtesting_runs_by_kind](../../ihm/services/backtesting_registry.py) — ligne 444 : `def list_active_backtesting_runs_by_kind(run_kind: BacktestingCommandKind) -> list[dict[str, object]]`
- [start_backtesting_run](../../ihm/services/backtesting_registry.py) — ligne 449 : `def start_backtesting_run(run_kind: BacktestingCommandKind, run_label: str, options: BacktestRunOptions | CNResearchReplayOptions | FRResearchReplayOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions | CalibrateSentimentWeightsOptions | WalkForwardSentimentOptions | WalkForwardConvictionOptions, *, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None) -> BacktestingRunRecord`
- [list_active_backtesting_runs](../../ihm/services/backtesting_registry.py) — ligne 583 : `def list_active_backtesting_runs() -> list[dict[str, object]]`
- [poll_backtesting_run](../../ihm/services/backtesting_registry.py) — ligne 600 : `def poll_backtesting_run(run_id: str) -> dict[str, object] | None`
- [stop_backtesting_run](../../ihm/services/backtesting_registry.py) — ligne 625 : `def stop_backtesting_run(run_id: str) -> bool`
- [load_backtesting_history](../../ihm/services/backtesting_registry.py) — ligne 667 : `def load_backtesting_history() -> list[dict[str, object]]`
- [get_backtesting_run_record](../../ihm/services/backtesting_registry.py) — ligne 673 : `def get_backtesting_run_record(run_id: str) -> dict[str, object] | None`
- [_resolve_backtesting_log_path](../../ihm/services/backtesting_registry.py) — ligne 680 : `def _resolve_backtesting_log_path(record: dict[str, object] | None, stream: Literal['stdout', 'stderr', 'all']='all') -> Path | None`
- [backtesting_log_available](../../ihm/services/backtesting_registry.py) — ligne 697 : `def backtesting_log_available(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all') -> bool`
- [read_backtesting_logs](../../ihm/services/backtesting_registry.py) — ligne 703 : `def read_backtesting_logs(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all', *, tail_lines: int | None=None) -> str`
- [build_backtesting_log_download_name](../../ihm/services/backtesting_registry.py) — ligne 717 : `def build_backtesting_log_download_name(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all') -> str`
- [delete_backtesting_runs_except](../../ihm/services/backtesting_registry.py) — ligne 727 : `def delete_backtesting_runs_except(keep_statuses: set[str] | tuple[str, ...] | frozenset[str] | None=None, *, stop_active: bool=True) -> dict[str, object]`
- [_purge_run_artifacts](../../ihm/services/backtesting_registry.py) — ligne 793 : `def _purge_run_artifacts(run_id: str, record: dict[str, object]) -> None`
- [count_backtesting_runs_by_status](../../ihm/services/backtesting_registry.py) — ligne 821 : `def count_backtesting_runs_by_status() -> dict[str, int]`
- [delete_backtesting_runs](../../ihm/services/backtesting_registry.py) — ligne 830 : `def delete_backtesting_runs(run_ids: list[str] | tuple[str, ...] | set[str], *, stop_active: bool=True) -> dict[str, object]`

## `ihm/services/backtesting_runner.py`

Source SHA-256 : `c688051e88a5ead13ba6fcdc0bf399748077abef9693f3ec093cb7952dfdcbf8`

- [BacktestRunOptions](../../ihm/services/backtesting_runner.py) — ligne 31 : `class BacktestRunOptions`
- [BacktestRunOptions.ml_first_selection_contract](../../ihm/services/backtesting_runner.py) — ligne 162 : `def ml_first_selection_contract(self) -> MLFirstSelectionContract`
- [BackfillScoresHistoryOptions](../../ihm/services/backtesting_runner.py) — ligne 174 : `class BackfillScoresHistoryOptions`
- [DiagnoseScreenerOptions](../../ihm/services/backtesting_runner.py) — ligne 191 : `class DiagnoseScreenerOptions`
- [RecommendScreenerOptions](../../ihm/services/backtesting_runner.py) — ligne 212 : `class RecommendScreenerOptions`
- [CalibrateSentimentWeightsOptions](../../ihm/services/backtesting_runner.py) — ligne 225 : `class CalibrateSentimentWeightsOptions`
- [CalibrateConvictionWeightsOptions](../../ihm/services/backtesting_runner.py) — ligne 239 : `class CalibrateConvictionWeightsOptions`
- [WalkForwardConvictionOptions](../../ihm/services/backtesting_runner.py) — ligne 254 : `class WalkForwardConvictionOptions`
- [WalkForwardSentimentOptions](../../ihm/services/backtesting_runner.py) — ligne 275 : `class WalkForwardSentimentOptions`
- [build_backtesting_command](../../ihm/services/backtesting_runner.py) — ligne 297 : `def build_backtesting_command(kind: BacktestingCommandKind, options: BacktestRunOptions | CNResearchReplayOptions | FRResearchReplayOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions | CalibrateSentimentWeightsOptions | CalibrateConvictionWeightsOptions | WalkForwardConvictionOptions | WalkForwardSentimentOptions) -> list[str]`
- [format_command_for_display](../../ihm/services/backtesting_runner.py) — ligne 756 : `def format_command_for_display(command: list[str]) -> str`

## `ihm/services/batch_management.py`

Source SHA-256 : `92b8db01a0e811b5d095b3c7343067510cceb51e6d23f3033474f492b907a250`

- [BatchSpec](../../ihm/services/batch_management.py) — ligne 63 : `class BatchSpec`
- [BatchSpec.runnable](../../ihm/services/batch_management.py) — ligne 88 : `def runnable(self) -> bool`
- [CommandResult](../../ihm/services/batch_management.py) — ligne 93 : `class CommandResult`
- [_split](../../ihm/services/batch_management.py) — ligne 100 : `def _split(value: Any) -> tuple[str, ...]`
- [_string_list](../../ihm/services/batch_management.py) — ligne 104 : `def _string_list(value: Any) -> tuple[str, ...]`
- [_default_task_name](../../ihm/services/batch_management.py) — ligne 111 : `def _default_task_name(batch_name: str) -> str`
- [_normalize_windows_task_time](../../ihm/services/batch_management.py) — ligne 116 : `def _normalize_windows_task_time(value: Any) -> str | None`
- [task_name_for_batch](../../ihm/services/batch_management.py) — ligne 128 : `def task_name_for_batch(batch_name: str) -> str`
- [load_batch_specs](../../ihm/services/batch_management.py) — ligne 133 : `def load_batch_specs(path: str | None=None) -> tuple[BatchSpec, ...]`
- [load_market_batch_specs](../../ihm/services/batch_management.py) — ligne 199 : `def load_market_batch_specs(market: str) -> tuple[BatchSpec, ...]`
- [supports_batch_execution](../../ihm/services/batch_management.py) — ligne 224 : `def supports_batch_execution(spec: BatchSpec) -> bool`
- [read_fr_inpi_mapping](../../ihm/services/batch_management.py) — ligne 228 : `def read_fr_inpi_mapping(spec: BatchSpec) -> dict | None`
- [read_fr_consensus_state](../../ihm/services/batch_management.py) — ligne 247 : `def read_fr_consensus_state(spec: BatchSpec) -> dict | None`
- [format_schedule](../../ihm/services/batch_management.py) — ligne 263 : `def format_schedule(spec: BatchSpec) -> str`
- [format_data_coverage](../../ihm/services/batch_management.py) — ligne 289 : `def format_data_coverage(spec: BatchSpec) -> str`
- [_powershell_prefix](../../ihm/services/batch_management.py) — ligne 325 : `def _powershell_prefix() -> list[str]`
- [build_install_command](../../ihm/services/batch_management.py) — ligne 329 : `def build_install_command(spec: BatchSpec, *, run_as: str='Interactive') -> list[str]`
- [build_run_command](../../ihm/services/batch_management.py) — ligne 382 : `def build_run_command(spec: BatchSpec) -> list[str]`
- [build_uninstall_command](../../ihm/services/batch_management.py) — ligne 425 : `def build_uninstall_command(spec: BatchSpec) -> list[str]`
- [format_command](../../ihm/services/batch_management.py) — ligne 432 : `def format_command(command: list[str]) -> str`
- [install_batch](../../ihm/services/batch_management.py) — ligne 436 : `def install_batch(spec: BatchSpec, *, run_as: str='Interactive', timeout_seconds: int=120) -> CommandResult`
- [uninstall_batch](../../ihm/services/batch_management.py) — ligne 448 : `def uninstall_batch(spec: BatchSpec, *, timeout_seconds: int=60) -> CommandResult`
- [_failed_command_result](../../ihm/services/batch_management.py) — ligne 458 : `def _failed_command_result(exc: Exception) -> CommandResult`
- [install_all_batches](../../ihm/services/batch_management.py) — ligne 462 : `def install_all_batches(specs: tuple[BatchSpec, ...] | list[BatchSpec], *, run_as: str='Interactive') -> dict[str, CommandResult]`
- [uninstall_all_batches](../../ihm/services/batch_management.py) — ligne 484 : `def uninstall_all_batches(specs: tuple[BatchSpec, ...] | list[BatchSpec]) -> dict[str, CommandResult]`
- [start_batch](../../ihm/services/batch_management.py) — ligne 496 : `def start_batch(spec: BatchSpec, *, db_config: dict[str, str | None] | None=None) -> PipelineRunRecord`
- [list_active_batch_runs](../../ihm/services/batch_management.py) — ligne 510 : `def list_active_batch_runs(batch_name: str | None=None) -> list[dict[str, object]]`
- [query_windows_task_states](../../ihm/services/batch_management.py) — ligne 518 : `def query_windows_task_states(timeout_seconds: int=15) -> tuple[dict[str, dict[str, Any]], str | None]`
- [read_batch_log_tail](../../ihm/services/batch_management.py) — ligne 566 : `def read_batch_log_tail(spec: BatchSpec, max_lines: int=80) -> str`
- [latest_cn_dragon_research_run](../../ihm/services/batch_management.py) — ligne 577 : `def latest_cn_dragon_research_run(spec: BatchSpec) -> dict[str, Any] | None`
- [read_cn_daily_quality_history](../../ihm/services/batch_management.py) — ligne 608 : `def read_cn_daily_quality_history(spec: BatchSpec, *, limit: int=7) -> tuple[dict[str, Any], ...]`

## `ihm/services/capital_presets.py`

Source SHA-256 : `7a51ee73b4000746864188720c5ba6525161af1b7cb7e411e12366449f55adb2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `ihm/services/cn_fold_launch.py`

Source SHA-256 : `0ac637611c0014c9e5061e5b8c9755a0bfa7acc11b10e2dc84353b2e7c9800a2`

- [CNResearchFoldOptions](../../ihm/services/cn_fold_launch.py) — ligne 22 : `class CNResearchFoldOptions`
- [fold_choices](../../ihm/services/cn_fold_launch.py) — ligne 32 : `def fold_choices(task: str) -> dict[str, tuple]`
- [validate_fold_options](../../ihm/services/cn_fold_launch.py) — ligne 51 : `def validate_fold_options(options: CNResearchFoldOptions, *, require_output: bool=False) -> None`
- [preflight_cn_fold](../../ihm/services/cn_fold_launch.py) — ligne 71 : `def preflight_cn_fold(options: CNResearchFoldOptions) -> None`
- [build_cn_fold_command](../../ihm/services/cn_fold_launch.py) — ligne 89 : `def build_cn_fold_command(options: CNResearchFoldOptions) -> list[str]`
- [start_cn_fold](../../ihm/services/cn_fold_launch.py) — ligne 100 : `def start_cn_fold(options: CNResearchFoldOptions)`

## `ihm/services/cn_fold_worker.py`

Source SHA-256 : `d99e8bc6dd3858545bc0feafd40bd630ad3bd261127a1def98d4a39f78002591`

- [progress_stage](../../ihm/services/cn_fold_worker.py) — ligne 15 : `def progress_stage(output_root: Path, model: str) -> str`
- [emit_progress](../../ihm/services/cn_fold_worker.py) — ligne 27 : `def emit_progress(*, task: str, stage: str, elapsed_seconds: int) -> None`
- [latest_progress_event](../../ihm/services/cn_fold_worker.py) — ligne 33 : `def latest_progress_event(journal: str) -> dict | None`
- [run_worker](../../ihm/services/cn_fold_worker.py) — ligne 49 : `def run_worker(*, task: str, horizon: int, semester: str, model: str, output_root: Path, heartbeat_seconds: float=30.0) -> dict`
- [main](../../ihm/services/cn_fold_worker.py) — ligne 84 : `def main() -> None`

## `ihm/services/cn_replay_launch.py`

Source SHA-256 : `4dcaa80255089004f0c3a628ba9fda718efecd20061f4c62ab74bba8e35ac8d1`

- [CNResearchReplayOptions](../../ihm/services/cn_replay_launch.py) — ligne 26 : `class CNResearchReplayOptions`
- [replay_choices](../../ihm/services/cn_replay_launch.py) — ligne 37 : `def replay_choices() -> dict[str, tuple]`
- [validate_replay_options](../../ihm/services/cn_replay_launch.py) — ligne 54 : `def validate_replay_options(options: CNResearchReplayOptions, *, require_output: bool=False) -> None`
- [preflight_cn_replay](../../ihm/services/cn_replay_launch.py) — ligne 79 : `def preflight_cn_replay(options: CNResearchReplayOptions) -> None`
- [build_cn_replay_command](../../ihm/services/cn_replay_launch.py) — ligne 106 : `def build_cn_replay_command(options: CNResearchReplayOptions) -> list[str]`

## `ihm/services/cn_replay_worker.py`

Source SHA-256 : `88fcab2cc8c34a80ad1763a4671c1c0fec84ea200425e25fecfa1e311f8b3965`

- [progress_stage](../../ihm/services/cn_replay_worker.py) — ligne 15 : `def progress_stage(output_root: Path) -> str`
- [emit_progress](../../ihm/services/cn_replay_worker.py) — ligne 26 : `def emit_progress(*, stage: str, elapsed_seconds: int) -> None`
- [latest_progress_event](../../ihm/services/cn_replay_worker.py) — ligne 32 : `def latest_progress_event(journal: str) -> dict | None`
- [run_worker](../../ihm/services/cn_replay_worker.py) — ligne 47 : `def run_worker(*, market_code: str, database_alias: str, semester: str, policy: str, seed: int, scenario: str, cost_profile: str, evidence: Path, output_root: Path, heartbeat_seconds: float=30.0) -> dict`
- [main](../../ihm/services/cn_replay_worker.py) — ligne 81 : `def main() -> None`

## `ihm/services/cn_research_market.py`

Source SHA-256 : `5444a8883dfcf6e6b9309b8a1fcd9af28fb6d823e5ddd7f25cda85d90e3842f2`

- [_render_cn_campaign_diagnostics](../../ihm/services/cn_research_market.py) — ligne 29 : `def _render_cn_campaign_diagnostics() -> None`
- [_render_cn_replay_panel](../../ihm/services/cn_research_market.py) — ligne 82 : `def _render_cn_replay_panel() -> None`
- [select_market](../../ihm/services/cn_research_market.py) — ligne 269 : `def select_market(page: PageKind) -> str`
- [load_cn_research_summary](../../ihm/services/cn_research_market.py) — ligne 282 : `def load_cn_research_summary(*, report_path: Path=DECISION_REPORT, universe_path: Path=CN_UNIVERSE) -> dict[str, Any]`
- [_render_cn_fold_panel](../../ihm/services/cn_research_market.py) — ligne 340 : `def _render_cn_fold_panel() -> None`
- [render_cn_research_view](../../ihm/services/cn_research_market.py) — ligne 492 : `def render_cn_research_view(page: PageKind) -> None`

## `ihm/services/cn_research_registry.py`

Source SHA-256 : `62926f6e6f06c497399e05a94505e89a759d93270c48a2c808c6035a7cdb362e`

- [load_campaign](../../ihm/services/cn_research_registry.py) — ligne 49 : `def load_campaign(campaign_id: str, *, root: Path=ROOT) -> dict[str, Any]`
- [list_campaigns](../../ihm/services/cn_research_registry.py) — ligne 104 : `def list_campaigns(*, root: Path=ROOT) -> list[dict[str, str]]`
- [model_metrics](../../ihm/services/cn_research_registry.py) — ligne 119 : `def model_metrics(campaign: dict[str, Any], horizon: int, model: str) -> tuple[dict[str, Any], list[dict[str, Any]]]`
- [directional_metrics](../../ihm/services/cn_research_registry.py) — ligne 160 : `def directional_metrics(campaign: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [directional_fold_metrics](../../ihm/services/cn_research_registry.py) — ligne 190 : `def directional_fold_metrics(campaign: dict[str, Any], horizon: int, policy: str) -> list[dict[str, Any]]`

## `ihm/services/compliance_loader.py`

Source SHA-256 : `7a8219e9f0ead6342505ebe779ad41c537bc1d57c54a24bc0ed9d1b8ea693f9a`

- [_safe_read_json](../../ihm/services/compliance_loader.py) — ligne 17 : `def _safe_read_json(path: Path) -> dict | None`
- [_latest_subdir](../../ihm/services/compliance_loader.py) — ligne 26 : `def _latest_subdir(root: Path) -> Path | None`
- [load_audit_chain_status](../../ihm/services/compliance_loader.py) — ligne 40 : `def load_audit_chain_status() -> dict[str, Any]`
- [load_dr_drill_status](../../ihm/services/compliance_loader.py) — ligne 68 : `def load_dr_drill_status() -> dict[str, Any]`
- [load_cve_status](../../ihm/services/compliance_loader.py) — ligne 87 : `def load_cve_status() -> dict[str, Any]`
- [load_coverage_status](../../ihm/services/compliance_loader.py) — ligne 111 : `def load_coverage_status() -> dict[str, Any]`
- [load_mutation_status](../../ihm/services/compliance_loader.py) — ligne 120 : `def load_mutation_status() -> dict[str, Any]`
- [load_tlaps_status](../../ihm/services/compliance_loader.py) — ligne 138 : `def load_tlaps_status() -> dict[str, Any]`
- [load_fuzz_status](../../ihm/services/compliance_loader.py) — ligne 152 : `def load_fuzz_status() -> dict[str, Any]`
- [load_sandbox_streak](../../ihm/services/compliance_loader.py) — ligne 166 : `def load_sandbox_streak() -> dict[str, Any]`
- [load_full_snapshot](../../ihm/services/compliance_loader.py) — ligne 188 : `def load_full_snapshot() -> dict[str, Any]`

## `ihm/services/db.py`

Source SHA-256 : `c0173e70965d5e587dff9af679edbfac50d1de86d7b8703ce888cb7b6ebf8490`

- [_set_state](../../ihm/services/db.py) — ligne 32 : `def _set_state(key: str, value: str | None) -> None`
- [_set_last_db_error](../../ihm/services/db.py) — ligne 39 : `def _set_last_db_error(message: str | None) -> None`
- [_set_last_query_error](../../ihm/services/db.py) — ligne 43 : `def _set_last_query_error(message: str | None) -> None`
- [get_last_db_error](../../ihm/services/db.py) — ligne 47 : `def get_last_db_error() -> str | None`
- [get_last_query_error](../../ihm/services/db.py) — ligne 51 : `def get_last_query_error() -> str | None`
- [get_runtime_db_config](../../ihm/services/db.py) — ligne 55 : `def get_runtime_db_config() -> dict[str, str | None]`
- [set_runtime_db_config](../../ihm/services/db.py) — ligne 81 : `def set_runtime_db_config(*, host: str, name: str, user: str, password: str) -> None`
- [clear_runtime_db_config](../../ihm/services/db.py) — ligne 90 : `def clear_runtime_db_config() -> None`
- [reset_db_caches](../../ihm/services/db.py) — ligne 97 : `def reset_db_caches(*, clear_errors: bool=False) -> None`
- [_build_database_url](../../ihm/services/db.py) — ligne 106 : `def _build_database_url(*, host: str, name: str, user: str, password: str) -> str`
- [_engine_options](../../ihm/services/db.py) — ligne 112 : `def _engine_options() -> dict[str, object]`
- [_format_db_connection_error](../../ihm/services/db.py) — ligne 122 : `def _format_db_connection_error(exc: Exception, *, host: str, name: str, user: str, source: str) -> str`
- [validate_db_connection_config](../../ihm/services/db.py) — ligne 152 : `def validate_db_connection_config(config: Mapping[str, str | None], *, source: str | None=None) -> str | None`
- [_get_cached_engine](../../ihm/services/db.py) — ligne 184 : `def _get_cached_engine(db_url: str) -> Engine`
- [get_engine](../../ihm/services/db.py) — ligne 188 : `def get_engine() -> Engine | None`
- [db_available](../../ihm/services/db.py) — ligne 220 : `def db_available() -> bool`
- [get_db_status](../../ihm/services/db.py) — ligne 224 : `def get_db_status() -> dict[str, str | bool | None]`
- [_format_query_error](../../ihm/services/db.py) — ligne 235 : `def _format_query_error(exc: Exception, query: str) -> str`
- [safe_query](../../ihm/services/db.py) — ligne 245 : `def safe_query(query: str, params: dict[str, Any] | None=None) -> pd.DataFrame`
- [safe_scalar](../../ihm/services/db.py) — ligne 263 : `def safe_scalar(query: str, params: dict[str, Any] | None=None) -> Any`
- [safe_execute](../../ihm/services/db.py) — ligne 282 : `def safe_execute(query: str, params: dict[str, Any] | None=None) -> bool`

## `ihm/services/db_admin.py`

Source SHA-256 : `c3f48903428a173b1143048ff88d0be71f06c8d4b08e6ab6d1ed3f9f7a31df60`

- [DatabaseTableSnapshot](../../ihm/services/db_admin.py) — ligne 165 : `class DatabaseTableSnapshot`
- [TableCatalogEntry](../../ihm/services/db_admin.py) — ligne 172 : `class TableCatalogEntry`
- [TablePurgeOperation](../../ihm/services/db_admin.py) — ligne 181 : `class TablePurgeOperation`
- [TablePurgePlan](../../ihm/services/db_admin.py) — ligne 189 : `class TablePurgePlan`
- [TablePurgeResult](../../ihm/services/db_admin.py) — ligne 199 : `class TablePurgeResult`
- [_normalize_table_name](../../ihm/services/db_admin.py) — ligne 205 : `def _normalize_table_name(value: str) -> str`
- [discover_tables_from_sql_directory](../../ihm/services/db_admin.py) — ligne 212 : `def discover_tables_from_sql_directory(sql_directory: Path=SQL_DIRECTORY) -> set[str]`
- [_classify_table](../../ihm/services/db_admin.py) — ligne 226 : `def _classify_table(table_name: str) -> str`
- [load_database_table_snapshot](../../ihm/services/db_admin.py) — ligne 248 : `def load_database_table_snapshot(engine: Engine) -> DatabaseTableSnapshot`
- [list_grouped_tables](../../ihm/services/db_admin.py) — ligne 293 : `def list_grouped_tables(snapshot: DatabaseTableSnapshot) -> dict[str, list[TableCatalogEntry]]`
- [_build_dependency_maps](../../ihm/services/db_admin.py) — ligne 314 : `def _build_dependency_maps(foreign_key_pairs: Iterable[tuple[str, str]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]`
- [_topological_delete_order](../../ihm/services/db_admin.py) — ligne 329 : `def _topological_delete_order(selected_tables: set[str], foreign_key_pairs: Iterable[tuple[str, str]]) -> tuple[list[str], list[str]]`
- [build_table_purge_plan](../../ihm/services/db_admin.py) — ligne 362 : `def build_table_purge_plan(selected_tables: Iterable[str], snapshot: DatabaseTableSnapshot) -> TablePurgePlan`
- [execute_table_purge](../../ihm/services/db_admin.py) — ligne 422 : `def execute_table_purge(engine: Engine, plan: TablePurgePlan) -> TablePurgeResult`

## `ihm/services/directional_prediction_diagnostics.py`

Source SHA-256 : `48c2682a2555013b730c9901a2ffb62e90d3abc4653b2e5c7e88a328dcb16347`

- [attach_forward_returns](../../ihm/services/directional_prediction_diagnostics.py) — ligne 13 : `def attach_forward_returns(predictions: pd.DataFrame, bars: pd.DataFrame, *, horizon: int, benchmark_symbol: str='SPY') -> pd.DataFrame`
- [oracle_top_fraction](../../ihm/services/directional_prediction_diagnostics.py) — ligne 56 : `def oracle_top_fraction(frame: pd.DataFrame, fraction: float=0.2) -> pd.DataFrame`
- [_daily_top_fraction](../../ihm/services/directional_prediction_diagnostics.py) — ligne 68 : `def _daily_top_fraction(frame: pd.DataFrame, score_column: str, fraction: float) -> pd.DataFrame`
- [evaluate_directional_top_decile](../../ihm/services/directional_prediction_diagnostics.py) — ligne 81 : `def evaluate_directional_top_decile(frame: pd.DataFrame, *, side: str, extreme_threshold: float=0.03) -> dict[str, Any]`

## `ihm/services/doc_links.py`

Source SHA-256 : `c52c4e3416ef5c696448c8db5a4c6ef48e55aed5fb697a4b926688fbd4bebc31`

- [DocRefResolution](../../ihm/services/doc_links.py) — ligne 32 : `class DocRefResolution`
- [DocRefResolution.has_local_content](../../ihm/services/doc_links.py) — ligne 48 : `def has_local_content(self) -> bool`
- [DocRefResolution.read_markdown](../../ihm/services/doc_links.py) — ligne 51 : `def read_markdown(self) -> str`
- [resolve_doc_ref](../../ihm/services/doc_links.py) — ligne 62 : `def resolve_doc_ref(doc_ref: str | None) -> DocRefResolution | None`
- [render_doc_ref_inline](../../ihm/services/doc_links.py) — ligne 95 : `def render_doc_ref_inline(st_module, doc_ref: str | None, *, key_suffix: str='') -> None`

## `ihm/services/email_notifier.py`

Source SHA-256 : `04fb7e84e74ec140c0b926a809add3a32a13414c8c1e8a0ac5689cce57e50e52`

- [_is_enabled](../../ihm/services/email_notifier.py) — ligne 57 : `def _is_enabled() -> bool`
- [_build_subject](../../ihm/services/email_notifier.py) — ligne 61 : `def _build_subject(event: str) -> str`
- [_build_body](../../ihm/services/email_notifier.py) — ligne 66 : `def _build_body(event: str, payload: dict[str, Any], *, ts: str) -> str`
- [_send_smtp](../../ihm/services/email_notifier.py) — ligne 77 : `def _send_smtp(subject: str, body: str) -> None`
- [send_notification](../../ihm/services/email_notifier.py) — ligne 117 : `def send_notification(event: str, payload: dict[str, Any] | None=None, *, raise_on_disabled: bool=False) -> bool`

## `ihm/services/fr_batch_view.py`

Source SHA-256 : `5136bfdfc927cfb8ab88dd66320e07855b3b3a8b53bbff01c4cdd6fbbe67a977`

- [render_fr_batches](../../ihm/services/fr_batch_view.py) — ligne 4 : `def render_fr_batches()`

## `ihm/services/fr_operations_view_18.py`

Source SHA-256 : `44b03dce96732f60340724e236987ca3aeb4eafe339b9862824255dbf9aa127a`

- [render_operations_preparation](../../ihm/services/fr_operations_view_18.py) — ligne 9 : `def render_operations_preparation(page)`

## `ihm/services/fr_replay_launch.py`

Source SHA-256 : `e0790c41b6fbf6328ebe70b40deb2f43da72edd26eda0aadf47e9472287a43df`

- [build_fr_replay_command](../../ihm/services/fr_replay_launch.py) — ligne 8 : `def build_fr_replay_command(options: FRResearchReplayOptions) -> list[str]`

## `ihm/services/fr_research_market.py`

Source SHA-256 : `753c0066947107c3f9c29ac8c12fa11c10932652bf675ca4f5601da6a59b8f1c`

- [_render_replay_panel](../../ihm/services/fr_research_market.py) — ligne 14 : `def _render_replay_panel(page: str) -> None`
- [render_fr_research_view](../../ihm/services/fr_research_market.py) — ligne 102 : `def render_fr_research_view(page: str) -> None`

## `ihm/services/fractional_trading_preferences.py`

Source SHA-256 : `2be6e7279e811328c2bde5396938074f0c13c7f4a73d5d6794c2dd40c45647fb`

- [_ensure_storage](../../ihm/services/fractional_trading_preferences.py) — ligne 17 : `def _ensure_storage() -> None`
- [FractionalTradingPreferences](../../ihm/services/fractional_trading_preferences.py) — ligne 22 : `class FractionalTradingPreferences`
- [FractionalTradingPreferences.to_dict](../../ihm/services/fractional_trading_preferences.py) — ligne 28 : `def to_dict(self) -> dict[str, Any]`
- [load_persisted_fractional_trading_preferences](../../ihm/services/fractional_trading_preferences.py) — ligne 36 : `def load_persisted_fractional_trading_preferences() -> FractionalTradingPreferences`
- [save_persisted_fractional_trading_preferences](../../ihm/services/fractional_trading_preferences.py) — ligne 52 : `def save_persisted_fractional_trading_preferences(prefs: FractionalTradingPreferences) -> FractionalTradingPreferences`

## `ihm/services/help_loader.py`

Source SHA-256 : `2f1ce43870a1883b979d7fb70e4f919754825948aaedf94e94ea781789655df3`

- [HelpYamlError](../../ihm/services/help_loader.py) — ligne 37 : `class HelpYamlError(RuntimeError)`
- [_read_yaml](../../ihm/services/help_loader.py) — ligne 41 : `def _read_yaml(path: pathlib.Path) -> dict[str, Any]`
- [_validate_entry](../../ihm/services/help_loader.py) — ligne 54 : `def _validate_entry(page: str, key: str, entry: Any) -> dict[str, Any] | None`
- [load_help](../../ihm/services/help_loader.py) — ligne 67 : `def load_help(page: str) -> Mapping[str, Any]`
- [reset_cache](../../ihm/services/help_loader.py) — ligne 93 : `def reset_cache() -> None`
- [help_dir](../../ihm/services/help_loader.py) — ligne 98 : `def help_dir() -> pathlib.Path`

## `ihm/services/market_data_provider.py`

Source SHA-256 : `d58081f74df6b66c96b00a0c736a0d71bf8ef64213837e65100127104483029c`

- [get_bars_provider](../../ihm/services/market_data_provider.py) — ligne 30 : `def get_bars_provider(config_path: Path | str | None=None) -> str`
- [set_bars_provider](../../ihm/services/market_data_provider.py) — ligne 50 : `def set_bars_provider(provider: str, config_path: Path | str | None=None) -> str`

## `ihm/services/ml_artifacts.py`

Source SHA-256 : `d55a339546cad3c350327944e49b45ac9eb02e0257e319172fd8a7175277c9d2`

- [get_model_artifacts_dir](../../ihm/services/ml_artifacts.py) — ligne 33 : `def get_model_artifacts_dir(artifacts_dir: Path | None=None) -> Path`
- [_symbol_sort_key](../../ihm/services/ml_artifacts.py) — ligne 37 : `def _symbol_sort_key(symbol: str) -> tuple[bool, str]`
- [list_ml_artifact_batches](../../ihm/services/ml_artifacts.py) — ligne 41 : `def list_ml_artifact_batches(artifacts_dir: Path | None=None) -> list[str]`
- [list_ml_artifact_symbols](../../ihm/services/ml_artifacts.py) — ligne 59 : `def list_ml_artifact_symbols(artifacts_dir: Path | None=None) -> list[str]`
- [load_batch_artifact_contract](../../ihm/services/ml_artifacts.py) — ligne 72 : `def load_batch_artifact_contract(batch_id: str, artifacts_dir: Path | None=None) -> dict[str, Any]`
- [list_directional_bundle_symbols](../../ihm/services/ml_artifacts.py) — ligne 106 : `def list_directional_bundle_symbols(batch_id: str, artifacts_dir: Path | None=None, role: str | None=None) -> list[str]`
- [_resolve_artifact_batch_dir](../../ihm/services/ml_artifacts.py) — ligne 129 : `def _resolve_artifact_batch_dir(batch_id: str, artifacts_dir: Path | None=None) -> Path`
- [resolve_batch_artifacts_root](../../ihm/services/ml_artifacts.py) — ligne 138 : `def resolve_batch_artifacts_root(batch_id: str, metadata: str | dict[str, Any] | None=None) -> Path`
- [has_per_symbol_artifacts](../../ihm/services/ml_artifacts.py) — ligne 197 : `def has_per_symbol_artifacts(batch_id: str, artifacts_dir: Path | None=None) -> bool`
- [_read_json_file](../../ihm/services/ml_artifacts.py) — ligne 213 : `def _read_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]`
- [_coerce_path](../../ihm/services/ml_artifacts.py) — ligne 228 : `def _coerce_path(value: Any) -> Path | None`
- [_path_exists](../../ihm/services/ml_artifacts.py) — ligne 236 : `def _path_exists(value: Any) -> bool`
- [_route_health](../../ihm/services/ml_artifacts.py) — ligne 241 : `def _route_health(model_name: str, route: dict[str, Any]) -> tuple[str, list[str], dict[str, bool]]`
- [_build_routes_dataframe](../../ihm/services/ml_artifacts.py) — ligne 261 : `def _build_routes_dataframe(config_data: dict[str, Any]) -> pd.DataFrame`
- [_build_ranking_dataframe](../../ihm/services/ml_artifacts.py) — ligne 294 : `def _build_ranking_dataframe(metrics_data: dict[str, Any]) -> pd.DataFrame`
- [_build_governance_thresholds_summary](../../ihm/services/ml_artifacts.py) — ligne 303 : `def _build_governance_thresholds_summary(config_data: dict[str, Any], metrics_data: dict[str, Any]) -> dict[str, Any]`
- [_finite_float](../../ihm/services/ml_artifacts.py) — ligne 327 : `def _finite_float(value: Any) -> float | None`
- [_selected_walk_forward_payload](../../ihm/services/ml_artifacts.py) — ligne 335 : `def _selected_walk_forward_payload(config_data: dict[str, Any], metrics_data: dict[str, Any], selected_model: str | None) -> tuple[dict[str, Any], int | None, str]`
- [_estimated_side_support](../../ihm/services/ml_artifacts.py) — ligne 366 : `def _estimated_side_support(split: dict[str, Any], side: str) -> int | None`
- [_side_stability](../../ihm/services/ml_artifacts.py) — ligne 379 : `def _side_stability(folds: list[dict[str, Any]], side: str) -> dict[str, Any]`
- [build_champion_walk_forward_stability](../../ihm/services/ml_artifacts.py) — ligne 417 : `def build_champion_walk_forward_stability(config_data: dict[str, Any], metrics_data: dict[str, Any], selected_model: str | None) -> dict[str, Any]`
- [_directional_selection_reason](../../ihm/services/ml_artifacts.py) — ligne 492 : `def _directional_selection_reason(side_summary: dict[str, Any]) -> str`
- [_is_discovery_side_candidate](../../ihm/services/ml_artifacts.py) — ligne 512 : `def _is_discovery_side_candidate(side_summary: dict[str, Any]) -> bool`
- [_directional_discovery_reason](../../ihm/services/ml_artifacts.py) — ligne 524 : `def _directional_discovery_reason(side_summary: dict[str, Any]) -> str`
- [_exclusive_directional_class](../../ihm/services/ml_artifacts.py) — ligne 540 : `def _exclusive_directional_class(eligible_long: bool, eligible_short: bool) -> str`
- [_artifact_report_branch_is_servable](../../ihm/services/ml_artifacts.py) — ligne 550 : `def _artifact_report_branch_is_servable(report: dict[str, Any]) -> bool`
- [build_directional_bundle_serving_coverage](../../ihm/services/ml_artifacts.py) — ligne 558 : `def build_directional_bundle_serving_coverage(batch_id: str, artifacts_dir: Path | None=None) -> dict[str, Any]`
- [build_batch_directional_candidate_selection](../../ihm/services/ml_artifacts.py) — ligne 598 : `def build_batch_directional_candidate_selection(batch_id: str, artifacts_dir: Path | None=None) -> dict[str, Any]`
- [format_directional_candidate_selection](../../ihm/services/ml_artifacts.py) — ligne 743 : `def format_directional_candidate_selection(selection: dict[str, Any]) -> str`
- [_load_optional_artifact_json](../../ihm/services/ml_artifacts.py) — ligne 786 : `def _load_optional_artifact_json(path: Path) -> dict[str, Any]`
- [load_ml_artifact_report](../../ihm/services/ml_artifacts.py) — ligne 791 : `def load_ml_artifact_report(symbol: str, artifacts_dir: Path | None=None) -> dict[str, Any]`

## `ihm/services/ml_reset.py`

Source SHA-256 : `dd74bf0efd9f88f0b524ee5354cd5b7dada3937e383a1a4fdcd43124f222ad3d`

- [_active_runs_for_dir](../../ihm/services/ml_reset.py) — ligne 75 : `def _active_runs_for_dir(rel: str) -> list[dict[str, object]]`
- [reset_ml_data](../../ihm/services/ml_reset.py) — ligne 88 : `def reset_ml_data(*, stop_active: bool=True, dry_run: bool=False, runs_only: bool=False, on_step: Callable[[str], None] | None=None) -> dict[str, object]`
- [build_reset_explanation](../../ihm/services/ml_reset.py) — ligne 312 : `def build_reset_explanation() -> str`

## `ihm/services/navigation.py`

Source SHA-256 : `cee4cd1c734ded1e30e3341a7949dc29fb85c6619a97217aa07ee7ded8ae2ec8`

- [NavigationPage](../../ihm/services/navigation.py) — ligne 26 : `class NavigationPage`
- [NavigationSection](../../ihm/services/navigation.py) — ligne 36 : `class NavigationSection`
- [_get_page](../../ihm/services/navigation.py) — ligne 92 : `def _get_page(key: str) -> NavigationPage`
- [get_navigation_sections](../../ihm/services/navigation.py) — ligne 99 : `def get_navigation_sections() -> tuple[NavigationSection, ...]`
- [get_navigation_pages](../../ihm/services/navigation.py) — ligne 179 : `def get_navigation_pages() -> tuple[NavigationPage, ...]`
- [get_navigation_page_labels](../../ihm/services/navigation.py) — ligne 183 : `def get_navigation_page_labels() -> list[str]`
- [get_navigation_page_mapping](../../ihm/services/navigation.py) — ligne 187 : `def get_navigation_page_mapping() -> dict[str, str]`
- [get_navigation_page_imports](../../ihm/services/navigation.py) — ligne 191 : `def get_navigation_page_imports() -> dict[str, str]`
- [build_primary_navigation_caption](../../ihm/services/navigation.py) — ligne 195 : `def build_primary_navigation_caption() -> str`
- [build_support_navigation_caption](../../ihm/services/navigation.py) — ligne 202 : `def build_support_navigation_caption() -> str`
- [build_section_navigation_caption](../../ihm/services/navigation.py) — ligne 210 : `def build_section_navigation_caption() -> str`

## `ihm/services/notifications.py`

Source SHA-256 : `94e8d5bfd8a376d0eebdd26f6e680fc94c2cdebdbdba7667be2fe49bdd7a0c01`

- [SmtpConfig](../../ihm/services/notifications.py) — ligne 54 : `class SmtpConfig`
- [SmtpConfig.is_configured](../../ihm/services/notifications.py) — ligne 65 : `def is_configured(self) -> bool`
- [_truthy](../../ihm/services/notifications.py) — ligne 69 : `def _truthy(value: object) -> bool`
- [load_smtp_config](../../ihm/services/notifications.py) — ligne 73 : `def load_smtp_config() -> SmtpConfig`
- [_read_log_tail](../../ihm/services/notifications.py) — ligne 128 : `def _read_log_tail(path: str | os.PathLike[str] | None, max_lines: int=LOG_TAIL_LINES) -> str`
- [collect_failed_step_context](../../ihm/services/notifications.py) — ligne 145 : `def collect_failed_step_context(record: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]`
- [_format_duration](../../ihm/services/notifications.py) — ligne 214 : `def _format_duration(seconds: object) -> str`
- [build_workflow_email](../../ihm/services/notifications.py) — ligne 230 : `def build_workflow_email(record: Mapping[str, Any], *, recipients: list[str], sender: str, failed_child: Mapping[str, Any] | None, log_excerpt: str) -> EmailMessage`
- [get_smtp_test_failure_log_path](../../ihm/services/notifications.py) — ligne 344 : `def get_smtp_test_failure_log_path() -> Path`
- [read_smtp_test_failure_log](../../ihm/services/notifications.py) — ligne 348 : `def read_smtp_test_failure_log() -> str`
- [clear_smtp_test_failure_log](../../ihm/services/notifications.py) — ligne 358 : `def clear_smtp_test_failure_log() -> None`
- [_write_smtp_test_failure_log](../../ihm/services/notifications.py) — ligne 366 : `def _write_smtp_test_failure_log(*, smtp_config: SmtpConfig, recipients: list[str], error: BaseException) -> Path | None`
- [_send_email_or_raise](../../ihm/services/notifications.py) — ligne 403 : `def _send_email_or_raise(message: EmailMessage, smtp_config: SmtpConfig) -> None`
- [_detect_default_smtp_ca_file](../../ihm/services/notifications.py) — ligne 426 : `def _detect_default_smtp_ca_file() -> str | None`
- [_resolve_smtp_ca_file](../../ihm/services/notifications.py) — ligne 437 : `def _resolve_smtp_ca_file(smtp_config: SmtpConfig) -> str | None`
- [_build_smtp_ssl_context](../../ihm/services/notifications.py) — ligne 444 : `def _build_smtp_ssl_context(smtp_config: SmtpConfig) -> ssl.SSLContext`
- [send_email](../../ihm/services/notifications.py) — ligne 453 : `def send_email(message: EmailMessage, smtp_config: SmtpConfig) -> bool`
- [_flag_path_for_record](../../ihm/services/notifications.py) — ligne 466 : `def _flag_path_for_record(record: Mapping[str, Any]) -> Path | None`
- [notify_run_finished](../../ihm/services/notifications.py) — ligne 476 : `def notify_run_finished(record: Mapping[str, Any], *, prefs: NotificationPreferences | None=None, smtp_config: SmtpConfig | None=None) -> bool`
- [send_test_email](../../ihm/services/notifications.py) — ligne 541 : `def send_test_email(prefs: NotificationPreferences, *, smtp_config: SmtpConfig | None=None) -> tuple[bool, str]`

## `ihm/services/notifications_preferences.py`

Source SHA-256 : `2e47254f14120019f3c0b052413219d146b1aa12b48e174f0e43be0a5e7e663b`

- [_ensure_storage](../../ihm/services/notifications_preferences.py) — ligne 30 : `def _ensure_storage() -> None`
- [NotificationPreferences](../../ihm/services/notifications_preferences.py) — ligne 35 : `class NotificationPreferences`
- [NotificationPreferences.to_dict](../../ihm/services/notifications_preferences.py) — ligne 42 : `def to_dict(self) -> dict[str, Any]`
- [NotificationPreferences.recipients_string](../../ihm/services/notifications_preferences.py) — ligne 49 : `def recipients_string(self) -> str`
- [is_valid_email](../../ihm/services/notifications_preferences.py) — ligne 53 : `def is_valid_email(value: str) -> bool`
- [parse_recipients](../../ihm/services/notifications_preferences.py) — ligne 57 : `def parse_recipients(raw: str | Iterable[str] | None) -> list[str]`
- [format_recipients](../../ihm/services/notifications_preferences.py) — ligne 85 : `def format_recipients(recipients: Iterable[str]) -> str`
- [_normalize_notify_on](../../ihm/services/notifications_preferences.py) — ligne 89 : `def _normalize_notify_on(raw: object) -> list[str]`
- [load_persisted_notification_preferences](../../ihm/services/notifications_preferences.py) — ligne 102 : `def load_persisted_notification_preferences() -> NotificationPreferences`
- [save_persisted_notification_preferences](../../ihm/services/notifications_preferences.py) — ligne 128 : `def save_persisted_notification_preferences(prefs: NotificationPreferences) -> NotificationPreferences`

## `ihm/services/ops_runner.py`

Source SHA-256 : `1355b619c5efaf6811e95ee1da2011409c7bdc979972dfaa9bcbd0878a25a136`

- [OpsCommandSpec](../../ihm/services/ops_runner.py) — ligne 68 : `class OpsCommandSpec`
- [_python](../../ihm/services/ops_runner.py) — ligne 240 : `def _python(*tail: str) -> list[str]`
- [_script](../../ihm/services/ops_runner.py) — ligne 244 : `def _script(script_relpath: str, *tail: str) -> list[str]`
- [_module](../../ihm/services/ops_runner.py) — ligne 248 : `def _module(module_name: str, *tail: str) -> list[str]`
- [build_ops_command](../../ihm/services/ops_runner.py) — ligne 252 : `def build_ops_command(key: OpsCommandKey, **kwargs: Any) -> list[str]`
- [start_ops_command](../../ihm/services/ops_runner.py) — ligne 467 : `def start_ops_command(key: OpsCommandKey, *, account_id: str | None=None, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, **command_kwargs: Any) -> PipelineRunRecord`
- [list_active_ops_runs](../../ihm/services/ops_runner.py) — ligne 498 : `def list_active_ops_runs(key: OpsCommandKey | None=None) -> list[dict[str, object]]`

## `ihm/services/ops_supervision.py`

Source SHA-256 : `44a40d90e3aae1635141d4599256e32981579c11ce92a515a6f5183919447d51`

- [_status_upper](../../ihm/services/ops_supervision.py) — ligne 43 : `def _status_upper(value: object) -> str`
- [_severity_rank](../../ihm/services/ops_supervision.py) — ligne 47 : `def _severity_rank(level: str) -> int`
- [_iter_records](../../ihm/services/ops_supervision.py) — ligne 51 : `def _iter_records(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> list[dict[str, object]]`
- [build_service_health_dataframe](../../ihm/services/ops_supervision.py) — ligne 57 : `def build_service_health_dataframe(records: pd.DataFrame | Iterable[Mapping[str, object]], *, now: datetime | None=None) -> pd.DataFrame`
- [build_latest_runs_dataframe](../../ihm/services/ops_supervision.py) — ligne 114 : `def build_latest_runs_dataframe(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> pd.DataFrame`
- [build_active_runs_dataframe](../../ihm/services/ops_supervision.py) — ligne 148 : `def build_active_runs_dataframe(active_runs: Iterable[Mapping[str, object]], *, account_id: str | None=None) -> pd.DataFrame`
- [build_run_lineage_dataframe](../../ihm/services/ops_supervision.py) — ligne 175 : `def build_run_lineage_dataframe(active_runs_df: pd.DataFrame) -> pd.DataFrame`
- [build_coverage_artifact_health](../../ihm/services/ops_supervision.py) — ligne 208 : `def build_coverage_artifact_health(payload: Mapping[str, object] | None) -> dict[str, object]`
- [load_coverage_artifact_health](../../ihm/services/ops_supervision.py) — ligne 270 : `def load_coverage_artifact_health(coverage_path: Path | None=None) -> dict[str, object]`
- [build_watcher_history_dataframe](../../ihm/services/ops_supervision.py) — ligne 285 : `def build_watcher_history_dataframe(records: Iterable[Mapping[str, object]]) -> pd.DataFrame`
- [build_windows_integration_dataframe](../../ihm/services/ops_supervision.py) — ligne 313 : `def build_windows_integration_dataframe(*, account_id: str | None=None) -> pd.DataFrame`
- [build_windows_runtime_dataframe](../../ihm/services/ops_supervision.py) — ligne 317 : `def build_windows_runtime_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame`
- [build_windows_log_sources_dataframe](../../ihm/services/ops_supervision.py) — ligne 366 : `def build_windows_log_sources_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame`
- [build_windows_bridge_dataframe](../../ihm/services/ops_supervision.py) — ligne 371 : `def build_windows_bridge_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame`
- [build_ops_alerts](../../ihm/services/ops_supervision.py) — ligne 396 : `def build_ops_alerts(service_health_df: pd.DataFrame, latest_runs_df: pd.DataFrame, active_runs_df: pd.DataFrame) -> list[dict[str, str]]`
- [build_watcher_control_state](../../ihm/services/ops_supervision.py) — ligne 482 : `def build_watcher_control_state(service_health_df: pd.DataFrame, active_runs_df: pd.DataFrame) -> dict[str, object]`
- [build_ops_supervision_snapshot](../../ihm/services/ops_supervision.py) — ligne 523 : `def build_ops_supervision_snapshot(*, account_id: str | None=None, now: datetime | None=None) -> dict[str, Any]`

## `ihm/services/orphan_adoption_service.py`

Source SHA-256 : `77eb01eeebd3c1c39f82f155f6b87c46851fe9a6d3e657efe359a03243fc7bed`

- [adopt_after_close](../../ihm/services/orphan_adoption_service.py) — ligne 20 : `def adopt_after_close(*, account_id: str, symbol: str, close_payload: dict[str, Any] | None) -> bool`

## `ihm/services/pipeline_lock.py`

Source SHA-256 : `ff4abf21f9f139aad70a932b4bdb9fafa64392dd1b979e568503df9a588d59ab`

- [_default_locks_dir](../../ihm/services/pipeline_lock.py) — ligne 33 : `def _default_locks_dir() -> Path`
- [set_locks_dir_for_tests](../../ihm/services/pipeline_lock.py) — ligne 52 : `def set_locks_dir_for_tests(path: Path | None) -> None`
- [_locks_dir](../../ihm/services/pipeline_lock.py) — ligne 62 : `def _locks_dir() -> Path`
- [_lock_path](../../ihm/services/pipeline_lock.py) — ligne 66 : `def _lock_path(scope: LockScope) -> Path`
- [_is_pid_alive](../../ihm/services/pipeline_lock.py) — ligne 72 : `def _is_pid_alive(pid: int) -> bool`
- [_get_process_started_at](../../ihm/services/pipeline_lock.py) — ligne 93 : `def _get_process_started_at(pid: int) -> datetime | None`
- [_parse_lock_datetime](../../ihm/services/pipeline_lock.py) — ligne 135 : `def _parse_lock_datetime(value: object) -> datetime | None`
- [LockHandle](../../ihm/services/pipeline_lock.py) — ligne 146 : `class LockHandle`
- [PipelineLockBusy](../../ihm/services/pipeline_lock.py) — ligne 156 : `class PipelineLockBusy(RuntimeError)`
- [PipelineLockBusy.__init__](../../ihm/services/pipeline_lock.py) — ligne 159 : `def __init__(self, scope: str, holder: dict[str, object])`
- [_read_lock](../../ihm/services/pipeline_lock.py) — ligne 168 : `def _read_lock(path: Path) -> dict[str, object] | None`
- [_is_lock_active](../../ihm/services/pipeline_lock.py) — ligne 178 : `def _is_lock_active(payload: dict[str, object] | None) -> bool`
- [list_active_locks](../../ihm/services/pipeline_lock.py) — ligne 227 : `def list_active_locks() -> list[dict[str, object]]`
- [acquire_lock](../../ihm/services/pipeline_lock.py) — ligne 246 : `def acquire_lock(scope: LockScope, *, owner: str, run_id: str, pid: int | None=None) -> LockHandle`
- [release_lock](../../ihm/services/pipeline_lock.py) — ligne 308 : `def release_lock(handle: LockHandle | None) -> None`
- [rebind_lock_pid](../../ihm/services/pipeline_lock.py) — ligne 329 : `def rebind_lock_pid(handle: LockHandle | None, *, pid: int) -> LockHandle | None`

## `ihm/services/pipeline_ml_defaults.py`

Source SHA-256 : `a43d87770ad6c3ce80345983560a31e9c4feccef5ea8749b68b74bec8a92591f`

- [is_catboost_available](../../ihm/services/pipeline_ml_defaults.py) — ligne 189 : `def is_catboost_available() -> bool`

## `ihm/services/pipeline_runner.py`

Source SHA-256 : `de7c743e76ffbe8640cca4badd9d220a955f473571fd1debc9324d80e6bcd8a9`

- [_resolve_bars_provider_for_ihm](../../ihm/services/pipeline_runner.py) — ligne 184 : `def _resolve_bars_provider_for_ihm() -> str`
- [_resolve_screener_custom_universe_file_from_config](../../ihm/services/pipeline_runner.py) — ligne 198 : `def _resolve_screener_custom_universe_file_from_config() -> str | None`
- [PipelineLaunchOptions](../../ihm/services/pipeline_runner.py) — ligne 352 : `class PipelineLaunchOptions`
- [PipelineLaunchOptions.ml_first_selection_contract](../../ihm/services/pipeline_runner.py) — ligne 538 : `def ml_first_selection_contract(self) -> MLFirstSelectionContract`
- [PipelineLaunchOptions.__post_init__](../../ihm/services/pipeline_runner.py) — ligne 682 : `def __post_init__(self) -> None`
- [PipelineStepDefinition](../../ihm/services/pipeline_runner.py) — ligne 708 : `class PipelineStepDefinition`
- [parse_pipeline_step_number](../../ihm/services/pipeline_runner.py) — ligne 720 : `def parse_pipeline_step_number(step_num: str) -> int | None`
- [is_canonical_pipeline_step_number](../../ihm/services/pipeline_runner.py) — ligne 733 : `def is_canonical_pipeline_step_number(step_num: str, *, min_step: int=1, max_step: int=12) -> bool`
- [is_workflow_core_step_number](../../ihm/services/pipeline_runner.py) — ligne 743 : `def is_workflow_core_step_number(step_num: str, *, min_step: int=1, max_step: int=12) -> bool`
- [PipelineRunResult](../../ihm/services/pipeline_runner.py) — ligne 751 : `class PipelineRunResult`
- [PipelineRunResult.to_state](../../ihm/services/pipeline_runner.py) — ligne 764 : `def to_state(self) -> dict[str, object]`
- [PipelineLiveSnapshot](../../ihm/services/pipeline_runner.py) — ligne 769 : `class PipelineLiveSnapshot`
- [get_pipeline_steps](../../ihm/services/pipeline_runner.py) — ligne 973 : `def get_pipeline_steps() -> tuple[PipelineStepDefinition, ...]`
- [pipeline_page_default_options](../../ihm/services/pipeline_runner.py) — ligne 977 : `def pipeline_page_default_options(*, trade_date: str) -> PipelineLaunchOptions`
- [resolve_step_display_name](../../ihm/services/pipeline_runner.py) — ligne 1000 : `def resolve_step_display_name(step: PipelineStepDefinition) -> str`
- [get_pipeline_workflow_steps](../../ihm/services/pipeline_runner.py) — ligne 1012 : `def get_pipeline_workflow_steps(*, start_step: WorkflowStartStep='1', include_ml_train: bool=False, include_corporate_actions_sync: bool=False, include_corporate_actions_apply: bool=False, selected_step_keys: tuple[str, ...] | None=None) -> tuple[PipelineStepDefinition, ...]`
- [get_pipeline_auxiliary_steps](../../ihm/services/pipeline_runner.py) — ligne 1060 : `def get_pipeline_auxiliary_steps() -> tuple[PipelineStepDefinition, ...]`
- [_normalize_trade_date](../../ihm/services/pipeline_runner.py) — ligne 1064 : `def _normalize_trade_date(value: str | None) -> str | None`
- [_normalize_run_id](../../ihm/services/pipeline_runner.py) — ligne 1069 : `def _normalize_run_id(value: str | None) -> str | None`
- [_normalize_optional_date](../../ihm/services/pipeline_runner.py) — ligne 1074 : `def _normalize_optional_date(value: str | None) -> str | None`
- [_normalize_symbol](../../ihm/services/pipeline_runner.py) — ligne 1079 : `def _normalize_symbol(value: str | None, default: str) -> str`
- [_normalize_optional_symbol](../../ihm/services/pipeline_runner.py) — ligne 1084 : `def _normalize_optional_symbol(value: str | None) -> str | None`
- [_normalize_symbol_list](../../ihm/services/pipeline_runner.py) — ligne 1089 : `def _normalize_symbol_list(value: str | None) -> str | None`
- [_with_default_sentiment_pending_max_batches](../../ihm/services/pipeline_runner.py) — ligne 1094 : `def _with_default_sentiment_pending_max_batches(options: PipelineLaunchOptions, *, default_value: int=0) -> PipelineLaunchOptions`
- [_build_powershell_file_command](../../ihm/services/pipeline_runner.py) — ligne 1112 : `def _build_powershell_file_command(script_path: Path, arguments: list[str] | None=None) -> list[str]`
- [_extend_event_sentiment_cli_common_args](../../ihm/services/pipeline_runner.py) — ligne 1124 : `def _extend_event_sentiment_cli_common_args(command: list[str], options: PipelineLaunchOptions, *, include_contextual_scoring: bool) -> None`
- [_extend_event_sentiment_runtime_args](../../ihm/services/pipeline_runner.py) — ligne 1179 : `def _extend_event_sentiment_runtime_args(command: list[str], options: PipelineLaunchOptions, *, include_feature_flush: bool=True) -> None`
- [_extend_event_sentiment_scope_args](../../ihm/services/pipeline_runner.py) — ligne 1214 : `def _extend_event_sentiment_scope_args(command: list[str], *, start_utc: str | None, end_utc: str | None, symbols: str | None) -> None`
- [_extend_relevance_backfill_scope_args](../../ihm/services/pipeline_runner.py) — ligne 1229 : `def _extend_relevance_backfill_scope_args(command: list[str], *, start_utc: str | None, end_utc: str | None, symbols: str | None, symbol_source: str | None=None, max_symbols: int | None=None) -> None`
- [_build_sentiment_standard_command](../../ihm/services/pipeline_runner.py) — ligne 1250 : `def _build_sentiment_standard_command(options: PipelineLaunchOptions, *, sentiment_start_utc: str | None, sentiment_end_utc: str | None, sentiment_symbols: str | None, sentiment_symbol_source: str | None=None, sentiment_max_symbols: int | None=None, skip_ingestion: bool) -> list[str]`
- [_build_sentiment_relevance_backfill_command](../../ihm/services/pipeline_runner.py) — ligne 1286 : `def _build_sentiment_relevance_backfill_command(options: PipelineLaunchOptions, *, sentiment_start_utc: str | None, sentiment_end_utc: str | None, sentiment_symbols: str | None, sentiment_symbol_source: str | None=None, sentiment_max_symbols: int | None=None) -> list[str]`
- [_build_sentiment_history_backfill_command](../../ihm/services/pipeline_runner.py) — ligne 1318 : `def _build_sentiment_history_backfill_command(*, sentiment_start_utc: str | None, sentiment_end_utc: str | None, ticker_symbols: str | None=None, ticker_symbol_source: str | None=None, ticker_max_symbols: int | None=None, ingestion_source: str | None=None) -> list[str]`
- [_build_sentiment_contextual_command](../../ihm/services/pipeline_runner.py) — ligne 1343 : `def _build_sentiment_contextual_command(options: PipelineLaunchOptions, *, sentiment_start_utc: str | None, sentiment_end_utc: str | None, sentiment_symbols: str | None, sentiment_symbol_source: str | None=None, sentiment_max_symbols: int | None=None) -> list[str]`
- [_build_import_news_command](../../ihm/services/pipeline_runner.py) — ligne 1401 : `def _build_import_news_command(options: PipelineLaunchOptions, *, import_start_date: str | None, import_end_date: str | None, import_symbols: str | None, import_symbol_source: str, import_max_symbols: int | None, resume_from_checkpoint: bool, force_symbol_source: bool=False) -> list[str]`
- [_extend_event_sentiment_powershell_args](../../ihm/services/pipeline_runner.py) — ligne 1444 : `def _extend_event_sentiment_powershell_args(command_args: list[str], options: PipelineLaunchOptions, *, include_contextual_scoring: bool) -> None`
- [_resolve_event_sentiment_scoring_mode](../../ihm/services/pipeline_runner.py) — ligne 1524 : `def _resolve_event_sentiment_scoring_mode(options: PipelineLaunchOptions) -> SentimentScoringMode`
- [_extend_import_news_cli_args](../../ihm/services/pipeline_runner.py) — ligne 1534 : `def _extend_import_news_cli_args(command: list[str], *, symbols: str | None, symbol_source: str, max_symbols: int | None, resume_from_checkpoint: bool=False) -> None`
- [_extend_import_news_powershell_args](../../ihm/services/pipeline_runner.py) — ligne 1554 : `def _extend_import_news_powershell_args(command_args: list[str], *, symbols: str | None, symbol_source: str, max_symbols: int | None, resume_from_checkpoint: bool=False) -> None`
- [_extend_event_sentiment_symbol_scope_args](../../ihm/services/pipeline_runner.py) — ligne 1574 : `def _extend_event_sentiment_symbol_scope_args(command: list[str], *, symbols: str | None, symbol_source: str, max_symbols: int | None) -> None`
- [_extend_relevance_backfill_powershell_args](../../ihm/services/pipeline_runner.py) — ligne 1590 : `def _extend_relevance_backfill_powershell_args(command_args: list[str], options: PipelineLaunchOptions) -> None`
- [_build_import_news_pending_loop_command](../../ihm/services/pipeline_runner.py) — ligne 1634 : `def _build_import_news_pending_loop_command(options: PipelineLaunchOptions, *, news_import_start_date: str | None, news_import_end_date: str | None, news_import_symbols: str | None, news_import_symbol_source: str, news_import_max_symbols: int | None, skip_import: bool=False) -> list[str]`
- [is_gpu_available](../../ihm/services/pipeline_runner.py) — ligne 1676 : `def is_gpu_available() -> bool`
- [_build_chained_ps_commands](../../ihm/services/pipeline_runner.py) — ligne 1685 : `def _build_chained_ps_commands(steps: list[tuple[str, list[str]]], title: str | None=None) -> list[str]`
- [build_pipeline_command](../../ihm/services/pipeline_runner.py) — ligne 1731 : `def build_pipeline_command(step_key: str, options: PipelineLaunchOptions) -> list[str]`
- [_wrap_llm_command](../../ihm/services/pipeline_runner.py) — ligne 2829 : `def _wrap_llm_command(phase: str, command: list[str], options: PipelineLaunchOptions) -> list[str]`
- [_llm_today_ny](../../ihm/services/pipeline_runner.py) — ligne 2875 : `def _llm_today_ny()`
- [format_command_for_display](../../ihm/services/pipeline_runner.py) — ligne 2880 : `def format_command_for_display(command: list[str]) -> str`
- [build_subprocess_env](../../ihm/services/pipeline_runner.py) — ligne 2884 : `def build_subprocess_env(db_config: dict[str, str | None] | None=None, base_env: dict[str, str] | None=None) -> dict[str, str]`
- [_build_live_snapshot](../../ihm/services/pipeline_runner.py) — ligne 2916 : `def _build_live_snapshot(*, step_key: str, command_display: str, status: PipelineExecutionStatus, stdout_lines: list[str], stderr_lines: list[str], started_at: datetime, started_perf: float, account_id: str | None, returncode: int | None=None) -> PipelineLiveSnapshot`
- [_stream_subprocess](../../ihm/services/pipeline_runner.py) — ligne 2943 : `def _stream_subprocess(command: list[str], *, step_key: str, account_id: str | None, env: dict[str, str], cwd: Path, timeout_seconds: int | None=None, on_update: Callable[[PipelineLiveSnapshot], None] | None=None) -> PipelineRunResult`
- [run_pipeline_step](../../ihm/services/pipeline_runner.py) — ligne 3085 : `def run_pipeline_step(step_key: str, options: PipelineLaunchOptions, *, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, on_update: Callable[[PipelineLiveSnapshot], None] | None=None) -> PipelineRunResult`

## `ihm/services/process_registry.py`

Source SHA-256 : `7ea0e24363b1d99a6629891efeae79ab3d0effe8e7fc7e83bec75678ee7a6a67`

- [PipelineRunRecord](../../ihm/services/process_registry.py) — ligne 83 : `class PipelineRunRecord`
- [PipelineRunRecord.to_state](../../ihm/services/process_registry.py) — ligne 123 : `def to_state(self) -> dict[str, object]`
- [_ManagedRun](../../ihm/services/process_registry.py) — ligne 128 : `class _ManagedRun`
- [_ManagedRun.__post_init__](../../ihm/services/process_registry.py) — ligne 140 : `def __post_init__(self) -> None`
- [_ManagedWorkflow](../../ihm/services/process_registry.py) — ligne 148 : `class _ManagedWorkflow`
- [_dispatch_finished_notification](../../ihm/services/process_registry.py) — ligne 164 : `def _dispatch_finished_notification(record: PipelineRunRecord) -> None`
- [_resolve_workflow_steps](../../ihm/services/process_registry.py) — ligne 179 : `def _resolve_workflow_steps(*, start_step: WorkflowStartStep, include_ml_train: bool, include_corporate_actions_sync: bool, include_corporate_actions_apply: bool, selected_step_keys: tuple[str, ...] | None=None) -> tuple[PipelineStepDefinition, ...]`
- [_format_workflow_core_step_ranges](../../ihm/services/process_registry.py) — ligne 199 : `def _format_workflow_core_step_ranges(steps: tuple[PipelineStepDefinition, ...]) -> str`
- [_workflow_scope_label](../../ihm/services/process_registry.py) — ligne 239 : `def _workflow_scope_label(*, start_step: WorkflowStartStep, include_corporate_actions_sync: bool, include_corporate_actions_apply: bool, selected_step_keys: tuple[str, ...] | None=None, steps: tuple[PipelineStepDefinition, ...] | None=None) -> str`
- [_workflow_step_label](../../ihm/services/process_registry.py) — ligne 265 : `def _workflow_step_label(*, start_step: WorkflowStartStep, include_ml_train: bool, include_corporate_actions_sync: bool, include_corporate_actions_apply: bool, selected_step_keys: tuple[str, ...] | None=None, steps: tuple[PipelineStepDefinition, ...] | None=None) -> str`
- [_workflow_command_display](../../ihm/services/process_registry.py) — ligne 293 : `def _workflow_command_display(*, start_step: WorkflowStartStep, include_ml_train: bool, include_corporate_actions_sync: bool, include_corporate_actions_apply: bool, total_steps: int, selected_step_keys: tuple[str, ...] | None=None, steps: tuple[PipelineStepDefinition, ...] | None=None) -> str`
- [_ensure_storage](../../ihm/services/process_registry.py) — ligne 322 : `def _ensure_storage() -> None`
- [_append_tail](../../ihm/services/process_registry.py) — ligne 328 : `def _append_tail(target: list[str], line: str) -> None`
- [_read_history_index](../../ihm/services/process_registry.py) — ligne 334 : `def _read_history_index() -> dict[str, dict[str, object]]`
- [_write_history_index](../../ihm/services/process_registry.py) — ligne 342 : `def _write_history_index(payload: dict[str, dict[str, object]]) -> None`
- [_persist_record](../../ihm/services/process_registry.py) — ligne 347 : `def _persist_record(record: PipelineRunRecord) -> None`
- [_record_artifact_path_from_record](../../ihm/services/process_registry.py) — ligne 355 : `def _record_artifact_path_from_record(record: dict[str, object]) -> Path`
- [_write_record_artifact](../../ihm/services/process_registry.py) — ligne 362 : `def _write_record_artifact(record: dict[str, object]) -> None`
- [_load_record_artifact](../../ihm/services/process_registry.py) — ligne 371 : `def _load_record_artifact(run_dir: Path) -> dict[str, object] | None`
- [_parse_run_id_datetime](../../ihm/services/process_registry.py) — ligne 382 : `def _parse_run_id_datetime(run_id: str, fallback_path: Path | None=None) -> str`
- [_file_line_count](../../ihm/services/process_registry.py) — ligne 397 : `def _file_line_count(path: Path) -> int`
- [_safe_read_text](../../ihm/services/process_registry.py) — ligne 407 : `def _safe_read_text(path: Path) -> str`
- [_read_positive_int_env](../../ihm/services/process_registry.py) — ligne 416 : `def _read_positive_int_env(name: str, default: int) -> int`
- [_run_log_max_bytes](../../ihm/services/process_registry.py) — ligne 427 : `def _run_log_max_bytes(stream: Literal['stdout', 'stderr', 'all']) -> int`
- [_run_log_max_line_chars](../../ihm/services/process_registry.py) — ligne 433 : `def _run_log_max_line_chars() -> int`
- [_truncate_log_line](../../ihm/services/process_registry.py) — ligne 437 : `def _truncate_log_line(line: str, max_chars: int) -> str`
- [_sanitize_log_chunk](../../ihm/services/process_registry.py) — ligne 453 : `def _sanitize_log_chunk(content: str) -> str`
- [_trim_file_to_max_bytes](../../ihm/services/process_registry.py) — ligne 460 : `def _trim_file_to_max_bytes(path: Path, max_bytes: int) -> None`
- [_infer_finished_at](../../ihm/services/process_registry.py) — ligne 484 : `def _infer_finished_at(run_dir: Path) -> str | None`
- [_recover_workflow_run_from_directory](../../ihm/services/process_registry.py) — ligne 499 : `def _recover_workflow_run_from_directory(run_dir: Path) -> tuple[dict[str, object] | None, dict[str, dict[str, object]]]`
- [_recover_step_run_from_directory](../../ihm/services/process_registry.py) — ligne 606 : `def _recover_step_run_from_directory(step_key: str, run_dir: Path, *, child_hints: dict[str, dict[str, object]]) -> dict[str, object] | None`
- [_recover_history_index_entries](../../ihm/services/process_registry.py) — ligne 660 : `def _recover_history_index_entries(existing_index: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]`
- [_normalize_inactive_scheduled_workflow_record](../../ihm/services/process_registry.py) — ligne 694 : `def _normalize_inactive_scheduled_workflow_record(record: dict[str, object], *, active_workflow_run_ids: set[str]) -> tuple[dict[str, object], bool]`
- [_infer_finished_at_from_record](../../ihm/services/process_registry.py) — ligne 721 : `def _infer_finished_at_from_record(record: dict[str, object]) -> str`
- [_normalize_inactive_orphan_active_record](../../ihm/services/process_registry.py) — ligne 734 : `def _normalize_inactive_orphan_active_record(record: dict[str, object], *, active_step_run_ids: set[str], active_workflow_run_ids: set[str]) -> tuple[dict[str, object], bool]`
- [_normalize_inactive_record](../../ihm/services/process_registry.py) — ligne 772 : `def _normalize_inactive_record(record: dict[str, object], *, active_step_run_ids: set[str], active_workflow_run_ids: set[str]) -> tuple[dict[str, object], bool]`
- [_reader](../../ihm/services/process_registry.py) — ligne 791 : `def _reader(stream: subprocess.PIPE | None, stream_name: str, events: queue.Queue[tuple[str, str]]) -> None`
- [_creation_flags](../../ihm/services/process_registry.py) — ligne 801 : `def _creation_flags() -> int`
- [_kill_process_tree](../../ihm/services/process_registry.py) — ligne 807 : `def _kill_process_tree(process: subprocess.Popen[str]) -> None`
- [_with_updates](../../ihm/services/process_registry.py) — ligne 821 : `def _with_updates(record: PipelineRunRecord, **updates: object) -> PipelineRunRecord`
- [_extract_run_summary](../../ihm/services/process_registry.py) — ligne 827 : `def _extract_run_summary(line: str) -> dict[str, object] | None`
- [_summary_int](../../ihm/services/process_registry.py) — ligne 841 : `def _summary_int(summary: dict[str, object], key: str) -> int`
- [_summary_float](../../ihm/services/process_registry.py) — ligne 849 : `def _summary_float(summary: dict[str, object], key: str) -> float | None`
- [_derive_watchdog_payload](../../ihm/services/process_registry.py) — ligne 857 : `def _derive_watchdog_payload(record: PipelineRunRecord) -> dict[str, object]`
- [_apply_watchdog_payload](../../ihm/services/process_registry.py) — ligne 914 : `def _apply_watchdog_payload(record: PipelineRunRecord) -> PipelineRunRecord`
- [_infer_ml_run_summary_from_logs](../../ihm/services/process_registry.py) — ligne 920 : `def _infer_ml_run_summary_from_logs(record: PipelineRunRecord) -> dict[str, object] | None`
- [_override_failed_status_run_summary](../../ihm/services/process_registry.py) — ligne 976 : `def _override_failed_status_run_summary(record: PipelineRunRecord, returncode: int | None) -> dict[str, object] | None`
- [_should_override_failed_status](../../ihm/services/process_registry.py) — ligne 1003 : `def _should_override_failed_status(record: PipelineRunRecord, returncode: int | None) -> bool`
- [_drain_events](../../ihm/services/process_registry.py) — ligne 1007 : `def _drain_events(managed: _ManagedRun) -> bool`
- [_finalize_if_needed](../../ihm/services/process_registry.py) — ligne 1074 : `def _finalize_if_needed(managed: _ManagedRun) -> PipelineRunRecord`
- [_tail_text](../../ihm/services/process_registry.py) — ligne 1163 : `def _tail_text(lines: list[str]) -> str`
- [_workflow_elapsed_seconds](../../ihm/services/process_registry.py) — ligne 1167 : `def _workflow_elapsed_seconds(managed: _ManagedWorkflow) -> float`
- [_count_lines](../../ihm/services/process_registry.py) — ligne 1174 : `def _count_lines(text: str) -> int`
- [_append_text](../../ihm/services/process_registry.py) — ligne 1178 : `def _append_text(path_value: str, content: str) -> None`
- [_append_bounded_text](../../ihm/services/process_registry.py) — ligne 1187 : `def _append_bounded_text(path_value: str, content: str, *, stream: Literal['stdout', 'stderr', 'all']) -> str`
- [_read_new_text](../../ihm/services/process_registry.py) — ligne 1196 : `def _read_new_text(path_value: str, offset: int) -> tuple[str, int]`
- [_prefix_chunk](../../ihm/services/process_registry.py) — ligne 1212 : `def _prefix_chunk(content: str, prefix: str) -> str`
- [_append_workflow_chunk](../../ihm/services/process_registry.py) — ligne 1218 : `def _append_workflow_chunk(managed: _ManagedWorkflow, stream: Literal['stdout', 'stderr'], content: str, *, prefix: str) -> None`
- [_append_workflow_event](../../ihm/services/process_registry.py) — ligne 1241 : `def _append_workflow_event(managed: _ManagedWorkflow, message: str, *, is_error: bool=False) -> None`
- [_update_workflow_record](../../ihm/services/process_registry.py) — ligne 1251 : `def _update_workflow_record(managed: _ManagedWorkflow, **updates: object) -> PipelineRunRecord`
- [_finalize_workflow_record](../../ihm/services/process_registry.py) — ligne 1258 : `def _finalize_workflow_record(managed: _ManagedWorkflow, *, status: RunStatus, returncode: int | None, workflow_completed_steps: int) -> PipelineRunRecord`
- [_sync_child_logs_to_workflow](../../ihm/services/process_registry.py) — ligne 1284 : `def _sync_child_logs_to_workflow(managed: _ManagedWorkflow, child_snapshot: dict[str, object] | None, *, step_label: str, offsets: dict[str, int]) -> None`
- [_run_pipeline_workflow](../../ihm/services/process_registry.py) — ligne 1302 : `def _run_pipeline_workflow(managed: _ManagedWorkflow, options: PipelineLaunchOptions, *, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, start_step: WorkflowStartStep='1', include_ml_train: bool=False, include_corporate_actions_sync: bool=False, include_corporate_actions_apply: bool=False, selected_step_keys: tuple[str, ...] | None=None, before_step: Callable[[PipelineStepDefinition, PipelineLaunchOptions, threading.Event], object] | None=None) -> None`
- [_poll_workflow_run](../../ihm/services/process_registry.py) — ligne 1487 : `def _poll_workflow_run(run_id: str, managed: _ManagedWorkflow) -> dict[str, object]`
- [_run_dir_for](../../ihm/services/process_registry.py) — ligne 1511 : `def _run_dir_for(step_key: str, run_id: str) -> Path`
- [_filesystem_safe_path_component](../../ihm/services/process_registry.py) — ligne 1515 : `def _filesystem_safe_path_component(value: str) -> str`
- [start_managed_run](../../ihm/services/process_registry.py) — ligne 1528 : `def start_managed_run(*, step_key: str, step_label: str, command: list[str], account_id: str | None=None, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, parent_run_id: str | None=None, workflow_correlation_id: str | None=None, notify_on_finish: bool=True) -> PipelineRunRecord`
- [start_pipeline_run](../../ihm/services/process_registry.py) — ligne 1608 : `def start_pipeline_run(step_key: str, step_label: str, options: PipelineLaunchOptions, *, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, parent_run_id: str | None=None, workflow_correlation_id: str | None=None) -> PipelineRunRecord`
- [start_pipeline_workflow](../../ihm/services/process_registry.py) — ligne 1670 : `def start_pipeline_workflow(options: PipelineLaunchOptions, *, db_config: dict[str, str | None] | None=None, timeout_seconds: int | None=None, start_step: WorkflowStartStep='1', include_ml_train: bool=False, include_corporate_actions_sync: bool=False, include_corporate_actions_apply: bool=False, selected_step_keys: tuple[str, ...] | None=None, scheduled_for: datetime | None=None, before_step: Callable[[PipelineStepDefinition, PipelineLaunchOptions, threading.Event], object] | None=None) -> PipelineRunRecord`
- [list_active_pipeline_runs](../../ihm/services/process_registry.py) — ligne 1855 : `def list_active_pipeline_runs() -> list[dict[str, object]]`
- [poll_pipeline_run](../../ihm/services/process_registry.py) — ligne 1869 : `def poll_pipeline_run(run_id: str) -> dict[str, object] | None`
- [stop_pipeline_run](../../ihm/services/process_registry.py) — ligne 1896 : `def stop_pipeline_run(run_id: str) -> bool`
- [load_pipeline_history](../../ihm/services/process_registry.py) — ligne 1920 : `def load_pipeline_history() -> list[dict[str, object]]`
- [get_pipeline_run_record](../../ihm/services/process_registry.py) — ligne 1960 : `def get_pipeline_run_record(run_id: str) -> dict[str, object] | None`
- [_resolve_pipeline_log_path](../../ihm/services/process_registry.py) — ligne 1980 : `def _resolve_pipeline_log_path(record: dict[str, object] | None, stream: Literal['stdout', 'stderr', 'all']='all') -> Path | None`
- [pipeline_log_available](../../ihm/services/process_registry.py) — ligne 1998 : `def pipeline_log_available(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all') -> bool`
- [read_pipeline_logs](../../ihm/services/process_registry.py) — ligne 2004 : `def read_pipeline_logs(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all') -> str`
- [build_log_download_name](../../ihm/services/process_registry.py) — ligne 2012 : `def build_log_download_name(run_id: str, stream: Literal['stdout', 'stderr', 'all']='all') -> str`
- [_retention_days](../../ihm/services/process_registry.py) — ligne 2022 : `def _retention_days() -> int`
- [rotate_pipeline_artifacts](../../ihm/services/process_registry.py) — ligne 2034 : `def rotate_pipeline_artifacts(retention_days: int | None=None) -> dict[str, int]`
- [_atexit_kill_all_children](../../ihm/services/process_registry.py) — ligne 2089 : `def _atexit_kill_all_children() -> None`
- [_ensure_lifecycle_hooks](../../ihm/services/process_registry.py) — ligne 2115 : `def _ensure_lifecycle_hooks() -> None`

## `ihm/services/queries.py`

Source SHA-256 : `4fa8d31d587445e0abb44508d2863806249b038ccb062b07981b46990addfa79`

- [_coerce_date](../../ihm/services/queries.py) — ligne 79 : `def _coerce_date(value: object) -> date | None`
- [_coverage_pct](../../ihm/services/queries.py) — ligne 95 : `def _coverage_pct(covered_symbols: int, eligible_symbols: int) -> float`
- [_coerce_int](../../ihm/services/queries.py) — ligne 101 : `def _coerce_int(value: object) -> int`
- [_safe_scalar_with_error](../../ihm/services/queries.py) — ligne 110 : `def _safe_scalar_with_error(query: str, params: dict[str, object] | None=None) -> tuple[object, str | None]`
- [_parse_json_object](../../ihm/services/queries.py) — ligne 115 : `def _parse_json_object(value: object) -> dict[str, object]`
- [_get_table_columns](../../ihm/services/queries.py) — ligne 127 : `def _get_table_columns(table_name: str) -> set[str]`
- [_build_stock_scores_query](../../ihm/services/queries.py) — ligne 138 : `def _build_stock_scores_query(available_columns: set[str]) -> str`
- [_attach_selection_explainability_payloads](../../ihm/services/queries.py) — ligne 164 : `def _attach_selection_explainability_payloads(df: pd.DataFrame) -> pd.DataFrame`
- [get_alpha_scanner_dependency_thresholds](../../ihm/services/queries.py) — ligne 175 : `def get_alpha_scanner_dependency_thresholds() -> dict[str, dict[str, float]]`
- [_build_quotes_dependency_payload](../../ihm/services/queries.py) — ligne 179 : `def _build_quotes_dependency_payload(*, today: date, eligible_symbols: int, latest_date: date | None, covered_symbols: int, query_error: str | None, thresholds: dict[str, float]) -> dict[str, object]`
- [_build_earnings_dependency_payload](../../ihm/services/queries.py) — ligne 237 : `def _build_earnings_dependency_payload(*, today: date, eligible_symbols: int, latest_date: date | None, covered_symbols: int, query_error: str | None, thresholds: dict[str, float]) -> dict[str, object]`
- [get_alpha_scanner_dependency_diagnostic](../../ihm/services/queries.py) — ligne 296 : `def get_alpha_scanner_dependency_diagnostic(*, today: date | None=None) -> dict[str, object]`
- [get_selection_count](../../ihm/services/queries.py) — ligne 395 : `def get_selection_count() -> int`
- [resolve_latest_selection_snapshot_date](../../ihm/services/queries.py) — ligne 400 : `def resolve_latest_selection_snapshot_date(trade_date: str | date | None) -> date | None`
- [get_backtesting_pit_history_diagnostic](../../ihm/services/queries.py) — ligne 437 : `def get_backtesting_pit_history_diagnostic(*, start: str | date | None, end: str | date | None, capital_preset_key: str | None) -> dict[str, object]`
- [_serialize_backtesting_ml_missing_rows](../../ihm/services/queries.py) — ligne 525 : `def _serialize_backtesting_ml_missing_rows(df: pd.DataFrame) -> list[dict[str, object]]`
- [_serialize_backtesting_ml_missing_days](../../ihm/services/queries.py) — ligne 538 : `def _serialize_backtesting_ml_missing_days(df: pd.DataFrame) -> list[dict[str, object]]`
- [get_live_ml_first_diagnostic](../../ihm/services/queries.py) — ligne 557 : `def get_live_ml_first_diagnostic() -> dict[str, object]`
- [get_backtesting_ml_coverage_diagnostic](../../ihm/services/queries.py) — ligne 618 : `def get_backtesting_ml_coverage_diagnostic(*, start: str | date | None, end: str | date | None, capital_preset_key: str | None, engine_mode: str='pipeline', ml_mode: str='auto', ml_pit_strategy: str='auto', missing_sample_limit: int=25, missing_days_limit: int=15) -> dict[str, object]`
- [get_stock_bars_daily_symbol_count](../../ihm/services/queries.py) — ligne 970 : `def get_stock_bars_daily_symbol_count() -> int`
- [get_top_selected_symbols](../../ihm/services/queries.py) — ligne 978 : `def get_top_selected_symbols(n: int=10) -> pd.DataFrame`
- [get_latest_risk_run_id](../../ihm/services/queries.py) — ligne 989 : `def get_latest_risk_run_id() -> str | None`
- [get_latest_exec_run](../../ihm/services/queries.py) — ligne 995 : `def get_latest_exec_run() -> pd.DataFrame`
- [get_stock_scores](../../ihm/services/queries.py) — ligne 1008 : `def get_stock_scores() -> pd.DataFrame`
- [get_risk_run_ids](../../ihm/services/queries.py) — ligne 1019 : `def get_risk_run_ids() -> list[str]`
- [get_risk_decisions](../../ihm/services/queries.py) — ligne 1025 : `def get_risk_decisions(run_id: str | None=None) -> pd.DataFrame`
- [get_portfolio_targets](../../ihm/services/queries.py) — ligne 1036 : `def get_portfolio_targets(run_id: str | None=None) -> pd.DataFrame`
- [get_shadow_drift_runs](../../ihm/services/queries.py) — ligne 1051 : `def get_shadow_drift_runs(live_run_id: str | None=None, limit: int=20) -> pd.DataFrame`
- [get_weights_calibration_runs](../../ihm/services/queries.py) — ligne 1080 : `def get_weights_calibration_runs(*, run_id: str | None=None, scope: str | None=None, market_regime_mode: str | None=None, horizon_days: int | None=None, lookback_months: int | None=None, eligible_for_live: bool | None=None, calibration_batch_id: str | None=None, limit: int=200) -> pd.DataFrame`
- [get_weights_calibration_run_ids](../../ihm/services/queries.py) — ligne 1172 : `def get_weights_calibration_run_ids(*, scope: str | None=None, market_regime_mode: str | None=None, horizon_days: int | None=None, lookback_months: int | None=None, eligible_for_live: bool | None=None, calibration_batch_id: str | None=None, limit: int=100) -> list[str]`
- [set_weights_calibration_live_eligibility](../../ihm/services/queries.py) — ligne 1196 : `def set_weights_calibration_live_eligibility(*, run_id: str, eligible: bool, reason: str | None=None) -> bool`
- [get_weights_calibration_segment_drifts](../../ihm/services/queries.py) — ligne 1240 : `def get_weights_calibration_segment_drifts(*, calibration_batch_id: str | None=None, source_run_id: str | None=None, comparison_kind: str | None=None, limit: int=200) -> pd.DataFrame`
- [get_execution_live_guard](../../ihm/services/queries.py) — ligne 1304 : `def get_execution_live_guard(account_id: str | None=None) -> dict[str, object]`
- [get_execution_reconciliation_j1_runs](../../ihm/services/queries.py) — ligne 1333 : `def get_execution_reconciliation_j1_runs(*, account_id: str | None=None, limit: int=20) -> pd.DataFrame`
- [get_execution_reconciliation_j1_diff_rows](../../ihm/services/queries.py) — ligne 1361 : `def get_execution_reconciliation_j1_diff_rows(*, account_id: str | None=None, trade_date: str | None=None) -> pd.DataFrame`
- [get_execution_tca_aggregates](../../ihm/services/queries.py) — ligne 1381 : `def get_execution_tca_aggregates(*, account_id: str | None=None, exec_run_id: str | None=None) -> dict[str, pd.DataFrame]`
- [get_execution_runs](../../ihm/services/queries.py) — ligne 1415 : `def get_execution_runs(limit: int=20, account_id: str | None=None) -> pd.DataFrame`
- [get_execution_events](../../ihm/services/queries.py) — ligne 1432 : `def get_execution_events(exec_run_id: str | None=None) -> pd.DataFrame`
- [get_execution_orders](../../ihm/services/queries.py) — ligne 1442 : `def get_execution_orders(exec_run_id: str | None=None, account_id: str | None=None) -> pd.DataFrame`
- [get_execution_account_constraints](../../ihm/services/queries.py) — ligne 1510 : `def get_execution_account_constraints(exec_run_id: str) -> dict[str, object]`
- [get_broker_positions](../../ihm/services/queries.py) — ligne 1557 : `def get_broker_positions(account_id: str | None=None) -> pd.DataFrame`
- [get_execution_fills](../../ihm/services/queries.py) — ligne 1575 : `def get_execution_fills(exec_run_id: str | None=None) -> pd.DataFrame`
- [get_execution_targets_snapshot](../../ihm/services/queries.py) — ligne 1623 : `def get_execution_targets_snapshot(exec_run_id: str) -> pd.DataFrame`
- [get_broker_account_snapshots_history](../../ihm/services/queries.py) — ligne 1670 : `def get_broker_account_snapshots_history(account_id: str, limit: int=200) -> pd.DataFrame`
- [get_execution_positions](../../ihm/services/queries.py) — ligne 1686 : `def get_execution_positions(*, account_id: str | None=None, exec_run_id: str | None=None, allow_account_fallback: bool=True) -> pd.DataFrame`
- [get_execution_position_lots](../../ihm/services/queries.py) — ligne 1733 : `def get_execution_position_lots(*, account_id: str | None=None, exec_run_id: str | None=None, allow_account_fallback: bool=True) -> pd.DataFrame`
- [get_execution_reconciliation_results](../../ihm/services/queries.py) — ligne 1783 : `def get_execution_reconciliation_results(*, exec_run_id: str | None=None, account_id: str | None=None, allow_account_fallback: bool=True) -> pd.DataFrame`
- [get_ca_events_summary](../../ihm/services/queries.py) — ligne 1855 : `def get_ca_events_summary() -> pd.DataFrame`
- [get_ca_events](../../ihm/services/queries.py) — ligne 1863 : `def get_ca_events(limit: int=100) -> pd.DataFrame`
- [get_ca_applications](../../ihm/services/queries.py) — ligne 1868 : `def get_ca_applications(limit: int=50) -> pd.DataFrame`
- [get_total_dividends](../../ihm/services/queries.py) — ligne 1873 : `def get_total_dividends() -> float`
- [_normalize_filter_values](../../ihm/services/queries.py) — ligne 1882 : `def _normalize_filter_values(values: list[str] | None) -> list[str]`
- [_append_in_clause](../../ihm/services/queries.py) — ligne 1891 : `def _append_in_clause(conditions: list[str], params: dict[str, object], *, column_sql: str, param_prefix: str, values: list[str] | None) -> None`
- [get_run_business_summaries](../../ihm/services/queries.py) — ligne 1911 : `def get_run_business_summaries(*, limit: int=50, step_keys: list[str] | None=None, entity_run_id: str | None=None, account_id: str | None=None, run_kind: str | None=None) -> pd.DataFrame`
- [get_latest_run_business_summary](../../ihm/services/queries.py) — ligne 1957 : `def get_latest_run_business_summary(*, step_key: str, entity_run_id: str | None=None, account_id: str | None=None, run_kind: str | None=None) -> dict[str, object] | None`
- [get_latest_execution_protection_watch_service_summary](../../ihm/services/queries.py) — ligne 1978 : `def get_latest_execution_protection_watch_service_summary(*, account_id: str | None=None, exec_run_id: str | None=None) -> dict[str, object] | None`
- [get_ops_service_summaries](../../ihm/services/queries.py) — ligne 2000 : `def get_ops_service_summaries(*, account_id: str | None=None, limit: int=20) -> pd.DataFrame`
- [get_ops_latest_critical_summaries](../../ihm/services/queries.py) — ligne 2014 : `def get_ops_latest_critical_summaries(*, account_id: str | None=None, limit: int=50) -> pd.DataFrame`
- [get_training_runs](../../ihm/services/queries.py) — ligne 2032 : `def get_training_runs(limit: int=20) -> pd.DataFrame`
- [get_completed_ml_training_batches](../../ihm/services/queries.py) — ligne 2037 : `def get_completed_ml_training_batches(limit: int=100) -> pd.DataFrame`
- [get_oracle_prediction_batches](../../ihm/services/queries.py) — ligne 2066 : `def get_oracle_prediction_batches(limit: int=50) -> pd.DataFrame`
- [get_ml_batch_comments](../../ihm/services/queries.py) — ligne 2091 : `def get_ml_batch_comments(batch_ids: list[str]) -> dict[str, str]`
- [get_model_metrics](../../ihm/services/queries.py) — ligne 2122 : `def get_model_metrics() -> pd.DataFrame`
- [get_model_governance](../../ihm/services/queries.py) — ligne 2127 : `def get_model_governance(limit: int=200, symbol: str | None=None, run_ids: list[str] | None=None, selection_modes: list[str] | None=None) -> pd.DataFrame`
- [get_prediction_symbols](../../ihm/services/queries.py) — ligne 2156 : `def get_prediction_symbols(limit: int=200) -> list[str]`
- [get_predictions](../../ihm/services/queries.py) — ligne 2162 : `def get_predictions(limit: int=100, symbol: str | None=None, run_ids: list[str] | None=None, served_models: list[str] | None=None) -> pd.DataFrame`
- [get_prediction_governance_audit](../../ihm/services/queries.py) — ligne 2186 : `def get_prediction_governance_audit(limit: int=100, symbol: str | None=None, run_ids: list[str] | None=None, selection_modes: list[str] | None=None, served_models: list[str] | None=None, governance_link_statuses: list[str] | None=None) -> pd.DataFrame`
- [get_stale_market_cap_stats](../../ihm/services/queries.py) — ligne 2272 : `def get_stale_market_cap_stats(*, cutoff_days: int=45) -> dict[str, int | float]`
- [get_backfill_completeness_diagnostic](../../ihm/services/queries.py) — ligne 2324 : `def get_backfill_completeness_diagnostic(*, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, contextual_min_relevance: float | None=None) -> dict[str, object]`
- [get_daily_pnl_data](../../ihm/services/queries.py) — ligne 2525 : `def get_daily_pnl_data() -> dict[str, object]`
- [get_batch_diagnostics_summary](../../ihm/services/queries.py) — ligne 2576 : `def get_batch_diagnostics_summary(batch_id: str | None=None) -> dict[str, object]`

## `ihm/services/run_summary.py`

Source SHA-256 : `f39caee42529d7de111531b2943b08ba239205b326f4e447c7008cc8f1bc2274`

- [_get_screener_persistence_status](../../ihm/services/run_summary.py) — ligne 230 : `def _get_screener_persistence_status(summary: Mapping[str, object]) -> str`
- [_get_screener_persistence_label](../../ihm/services/run_summary.py) — ligne 234 : `def _get_screener_persistence_label(summary: Mapping[str, object]) -> str | None`
- [_get_screener_chunk_error_samples](../../ihm/services/run_summary.py) — ligne 241 : `def _get_screener_chunk_error_samples(summary: Mapping[str, object]) -> list[Mapping[str, object]]`
- [_format_alpha_scanner_selection_detail_line](../../ihm/services/run_summary.py) — ligne 248 : `def _format_alpha_scanner_selection_detail_line(selection: Mapping[str, object]) -> str | None`
- [_format_alpha_scanner_preselection_detail_line](../../ihm/services/run_summary.py) — ligne 284 : `def _format_alpha_scanner_preselection_detail_line(summary: Mapping[str, object]) -> str | None`
- [_format_alpha_scanner_ablation_detail_lines](../../ihm/services/run_summary.py) — ligne 327 : `def _format_alpha_scanner_ablation_detail_lines(summary: Mapping[str, object]) -> list[str]`
- [_format_selector_mode_counts_line](../../ihm/services/run_summary.py) — ligne 382 : `def _format_selector_mode_counts_line(label: str, payload: object) -> str | None`
- [_normalize_fallback_journal_entries](../../ihm/services/run_summary.py) — ligne 397 : `def _normalize_fallback_journal_entries(payload: object) -> list[Mapping[str, object]]`
- [_format_empirical_calibration_fallback_lines](../../ihm/services/run_summary.py) — ligne 403 : `def _format_empirical_calibration_fallback_lines(payload: Mapping[str, object]) -> list[str]`
- [get_run_summary](../../ihm/services/run_summary.py) — ligne 453 : `def get_run_summary(record: Mapping[str, object] | None) -> dict[str, object]`
- [_step_key](../../ihm/services/run_summary.py) — ligne 460 : `def _step_key(record: Mapping[str, object] | None) -> str`
- [get_stooq_cross_check_status](../../ihm/services/run_summary.py) — ligne 466 : `def get_stooq_cross_check_status(record: Mapping[str, object] | None) -> str | None`
- [get_run_summary_metric_items](../../ihm/services/run_summary.py) — ligne 484 : `def get_run_summary_metric_items(record: Mapping[str, object] | None) -> list[tuple[str, object]]`
- [build_run_summary_caption](../../ihm/services/run_summary.py) — ligne 515 : `def build_run_summary_caption(record: Mapping[str, object] | None) -> str`
- [get_run_summary_detail_lines](../../ihm/services/run_summary.py) — ligne 522 : `def get_run_summary_detail_lines(record: Mapping[str, object] | None) -> list[str]`
- [find_latest_run_with_summary](../../ihm/services/run_summary.py) — ligne 978 : `def find_latest_run_with_summary(records: Sequence[Mapping[str, object]], *, step_keys: Iterable[str] | None=None, run_kind: str | None=None) -> dict[str, object] | None`
- [build_latest_run_summary_rows](../../ihm/services/run_summary.py) — ligne 995 : `def build_latest_run_summary_rows(records: Sequence[Mapping[str, object]], scopes: Sequence[Mapping[str, object]]) -> list[dict[str, object]]`
- [build_ordered_pipeline_step_scopes](../../ihm/services/run_summary.py) — ligne 1022 : `def build_ordered_pipeline_step_scopes(*, include_auxiliary: bool=True, max_main_step: int | None=None) -> list[dict[str, object]]`
- [build_pipeline_flow_caption](../../ihm/services/run_summary.py) — ligne 1043 : `def build_pipeline_flow_caption(*, include_auxiliary: bool=True, max_main_step: int | None=None) -> str`
- [_is_number](../../ihm/services/run_summary.py) — ligne 1051 : `def _is_number(value: Any) -> bool`
- [_to_float](../../ihm/services/run_summary.py) — ligne 1055 : `def _to_float(value: object) -> float | None`
- [_to_int](../../ihm/services/run_summary.py) — ligne 1061 : `def _to_int(value: object) -> int`
- [_coerce_float](../../ihm/services/run_summary.py) — ligne 1069 : `def _coerce_float(value: object) -> float`
- [_merge_nested_counts](../../ihm/services/run_summary.py) — ligne 1077 : `def _merge_nested_counts(target: dict[str, object], key: str, value: Mapping[str, object]) -> None`
- [_merge_scalar_metric](../../ihm/services/run_summary.py) — ligne 1087 : `def _merge_scalar_metric(target: dict[str, object], key: str, value: int | float) -> None`
- [_metric_rule](../../ihm/services/run_summary.py) — ligne 1108 : `def _metric_rule(key: str, value: object) -> str`
- [_infer_weight_key](../../ihm/services/run_summary.py) — ligne 1126 : `def _infer_weight_key(summary: Mapping[str, object], key: str) -> str | None`
- [aggregate_workflow_run_summary](../../ihm/services/run_summary.py) — ligne 1154 : `def aggregate_workflow_run_summary(child_runs: Iterable[Mapping[str, object]]) -> dict[str, object]`

## `ihm/services/sandbox_health_loader.py`

Source SHA-256 : `8371425a2fd1145c1a2e65c1186ae34555b5ac22cb9fd269a920257aaa3bd1bf`

- [load_rollup](../../ihm/services/sandbox_health_loader.py) — ligne 14 : `def load_rollup(sandbox_dir: Path | str | None=None) -> dict[str, Any]`
- [load_day](../../ihm/services/sandbox_health_loader.py) — ligne 26 : `def load_day(date_iso: str, sandbox_dir: Path | str | None=None) -> dict[str, Any]`

## `ihm/services/screener_artifact_history.py`

Source SHA-256 : `07e46bb683b5764d2850163445b6260d4b2710dc58a1829a656a603e2c0bca87`

- [normalize_screener_artifacts_dir](../../ihm/services/screener_artifact_history.py) — ligne 19 : `def normalize_screener_artifacts_dir(artifacts_dir: Path | str | None=None) -> str`
- [_artifacts_dir_label](../../ihm/services/screener_artifact_history.py) — ligne 23 : `def _artifacts_dir_label(artifacts_dir: str) -> str`
- [_last_run_timestamp](../../ihm/services/screener_artifact_history.py) — ligne 31 : `def _last_run_timestamp(run_record: dict[str, object]) -> str`
- [_history_sort_key](../../ihm/services/screener_artifact_history.py) — ligne 35 : `def _history_sort_key(entry: dict[str, Any]) -> tuple[str, str, str]`
- [build_screener_history_entry](../../ihm/services/screener_artifact_history.py) — ligne 43 : `def build_screener_history_entry(artifacts_dir: Path | str, *, runs: list[dict[str, object]] | None=None, source_tags: list[str] | set[str] | tuple[str, ...] | None=None) -> dict[str, Any]`
- [build_global_screener_artifact_history](../../ihm/services/screener_artifact_history.py) — ligne 80 : `def build_global_screener_artifact_history(additional_dirs: list[Path | str] | None=None) -> list[dict[str, Any]]`
- [resolve_selected_screener_artifacts_dir](../../ihm/services/screener_artifact_history.py) — ligne 119 : `def resolve_selected_screener_artifacts_dir(history_entries: list[dict[str, Any]], preferred_dir: Path | str | None=None, *, missing_source_tag: str='préférence persistée') -> tuple[str, dict[str, dict[str, Any]]]`
- [format_screener_artifact_history_label](../../ihm/services/screener_artifact_history.py) — ligne 145 : `def format_screener_artifact_history_label(entry: dict[str, Any]) -> str`
- [build_screener_artifact_history_rows](../../ihm/services/screener_artifact_history.py) — ligne 159 : `def build_screener_artifact_history_rows(entries: list[dict[str, Any]]) -> list[dict[str, object]]`

## `ihm/services/screener_preferences.py`

Source SHA-256 : `8536d8b8cc41c47ed713cb979161b0bfded95b517cbf984919ea9262f486a868`

- [_ensure_storage](../../ihm/services/screener_preferences.py) — ligne 17 : `def _ensure_storage() -> None`
- [_normalize_optional_dir](../../ihm/services/screener_preferences.py) — ligne 21 : `def _normalize_optional_dir(artifacts_dir: Path | str | None) -> str | None`
- [load_persisted_selected_screener_artifacts_dir](../../ihm/services/screener_preferences.py) — ligne 30 : `def load_persisted_selected_screener_artifacts_dir() -> str | None`
- [save_persisted_selected_screener_artifacts_dir](../../ihm/services/screener_preferences.py) — ligne 43 : `def save_persisted_selected_screener_artifacts_dir(artifacts_dir: Path | str | None) -> str | None`
- [_normalize_thresholds_payload](../../ihm/services/screener_preferences.py) — ligne 57 : `def _normalize_thresholds_payload(payload: object, *, defaults: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]`
- [load_persisted_alpha_scanner_dependency_thresholds](../../ihm/services/screener_preferences.py) — ligne 82 : `def load_persisted_alpha_scanner_dependency_thresholds(defaults: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]`
- [load_persisted_alpha_scanner_dependency_preset_metadata](../../ihm/services/screener_preferences.py) — ligne 95 : `def load_persisted_alpha_scanner_dependency_preset_metadata() -> dict[str, str | None]`
- [save_persisted_alpha_scanner_dependency_thresholds](../../ihm/services/screener_preferences.py) — ligne 112 : `def save_persisted_alpha_scanner_dependency_thresholds(thresholds: dict[str, dict[str, float]], *, defaults: dict[str, dict[str, float]], selected_style: str | None=None, selected_market_regime: str | None=None, selection_mode: str | None=None) -> dict[str, dict[str, float]]`
- [reset_persisted_alpha_scanner_dependency_thresholds](../../ihm/services/screener_preferences.py) — ligne 136 : `def reset_persisted_alpha_scanner_dependency_thresholds() -> None`

## `ihm/services/screener_recommendations.py`

Source SHA-256 : `e76febf5084224620b6c2870e0e2bb20d0474f50c81829aa4d081d017175cc1d`

- [get_screener_artifacts_dir](../../ihm/services/screener_recommendations.py) — ligne 37 : `def get_screener_artifacts_dir(artifacts_dir: Path | str | None=None) -> Path`
- [_count_data_rows](../../ihm/services/screener_recommendations.py) — ligne 44 : `def _count_data_rows(path: Path) -> int | None`
- [_format_size_label](../../ihm/services/screener_recommendations.py) — ligne 57 : `def _format_size_label(size_bytes: int) -> str`
- [_build_file_snapshot](../../ihm/services/screener_recommendations.py) — ligne 65 : `def _build_file_snapshot(root: Path, *, key: str, filename: str, kind: str) -> dict[str, Any]`
- [_coerce_scalar](../../ihm/services/screener_recommendations.py) — ligne 82 : `def _coerce_scalar(value: object) -> Any`
- [_extract_recommended_scenario](../../ihm/services/screener_recommendations.py) — ligne 93 : `def _extract_recommended_scenario(payload: dict[str, Any]) -> dict[str, Any] | None`
- [_build_objective_leaders](../../ihm/services/screener_recommendations.py) — ligne 110 : `def _build_objective_leaders(report: dict[str, Any]) -> list[dict[str, Any]]`
- [_read_json_file](../../ihm/services/screener_recommendations.py) — ligne 137 : `def _read_json_file(path: Path) -> tuple[dict[str, Any], str | None]`
- [_read_csv_file](../../ihm/services/screener_recommendations.py) — ligne 152 : `def _read_csv_file(path: Path) -> tuple[pd.DataFrame, str | None]`
- [_coverage_label](../../ihm/services/screener_recommendations.py) — ligne 161 : `def _coverage_label(metadata: dict[str, Any]) -> str`
- [_format_updated_at](../../ihm/services/screener_recommendations.py) — ligne 171 : `def _format_updated_at(path: Path) -> str`
- [_updated_at_iso](../../ihm/services/screener_recommendations.py) — ligne 178 : `def _updated_at_iso(path: Path) -> str | None`
- [_objective_order_key](../../ihm/services/screener_recommendations.py) — ligne 185 : `def _objective_order_key(objective: object) -> tuple[int, str]`
- [_build_objective_rows_from_summary](../../ihm/services/screener_recommendations.py) — ligne 193 : `def _build_objective_rows_from_summary(summary_payload: dict[str, Any]) -> pd.DataFrame`
- [_build_objective_rows_from_recommendations](../../ihm/services/screener_recommendations.py) — ligne 231 : `def _build_objective_rows_from_recommendations(recommendations: pd.DataFrame) -> pd.DataFrame`
- [_build_leaderboard](../../ihm/services/screener_recommendations.py) — ligne 284 : `def _build_leaderboard(recommendations: pd.DataFrame) -> pd.DataFrame`
- [load_screener_recommendation_report](../../ihm/services/screener_recommendations.py) — ligne 319 : `def load_screener_recommendation_report(artifacts_dir: Path | str | None=None) -> dict[str, Any]`
- [build_screener_artifact_summary](../../ihm/services/screener_recommendations.py) — ligne 381 : `def build_screener_artifact_summary(artifacts_dir: Path | str | None=None) -> dict[str, Any]`
- [list_screener_csv_files](../../ihm/services/screener_recommendations.py) — ligne 442 : `def list_screener_csv_files(artifacts_dir: Path | str | None=None, *, summary: dict[str, Any] | None=None) -> list[dict[str, Any]]`
- [load_screener_csv_preview](../../ihm/services/screener_recommendations.py) — ligne 458 : `def load_screener_csv_preview(artifacts_dir: Path | str | None=None, *, file_key: str | None=None, max_rows: int=100, summary: dict[str, Any] | None=None) -> dict[str, Any]`

## `ihm/services/security.py`

Source SHA-256 : `b7c8433d31a0209bddaeaa839d1f917c6d46d6936c1cb27e3c602f02c0f1037d`

- [auth_token_required](../../ihm/services/security.py) — ligne 25 : `def auth_token_required() -> bool`
- [_expected_token](../../ihm/services/security.py) — ligne 30 : `def _expected_token() -> str`
- [is_localhost_required](../../ihm/services/security.py) — ligne 34 : `def is_localhost_required() -> bool`
- [_resolve_server_address](../../ihm/services/security.py) — ligne 39 : `def _resolve_server_address() -> str`
- [is_listening_on_localhost_only](../../ihm/services/security.py) — ligne 46 : `def is_listening_on_localhost_only() -> bool`
- [render_auth_gate](../../ihm/services/security.py) — ligne 62 : `def render_auth_gate() -> bool`
- [render_security_banner](../../ihm/services/security.py) — ligne 92 : `def render_security_banner() -> None`

## `ihm/services/swing_score.py`

Source SHA-256 : `efeaf97ae211bfe1196e99d389c9022ca8cfe5a75c2c4422b11d58f23f5f3b72`

- [parse_symbols](../../ihm/services/swing_score.py) — ligne 81 : `def parse_symbols(text_content: str) -> list[str]`
- [_load_bars_chunk](../../ihm/services/swing_score.py) — ligne 97 : `def _load_bars_chunk(symbols: list[str]) -> pd.DataFrame`
- [load_bars](../../ihm/services/swing_score.py) — ligne 115 : `def load_bars(symbols: list[str], benchmark: str=BENCHMARK_SYMBOL) -> pd.DataFrame`
- [load_market_caps](../../ihm/services/swing_score.py) — ligne 130 : `def load_market_caps(symbols: list[str]) -> pd.DataFrame`
- [_true_range](../../ihm/services/swing_score.py) — ligne 157 : `def _true_range(frame: pd.DataFrame) -> pd.Series`
- [_beta_score](../../ihm/services/swing_score.py) — ligne 169 : `def _beta_score(beta: float | None) -> float`
- [_market_cap_fit_score](../../ihm/services/swing_score.py) — ligne 175 : `def _market_cap_fit_score(market_cap: float | None) -> float`
- [_percentile_score](../../ihm/services/swing_score.py) — ligne 181 : `def _percentile_score(series: pd.Series) -> pd.Series`
- [_symbol_metrics_from_group](../../ihm/services/swing_score.py) — ligne 186 : `def _symbol_metrics_from_group(symbol: str, frame: pd.DataFrame, sym_rets: pd.Series, bench_rets: pd.Series) -> dict[str, float | object] | None`
- [build_swing_scores](../../ihm/services/swing_score.py) — ligne 231 : `def build_swing_scores(bars: pd.DataFrame, market_caps: pd.DataFrame, symbols: list[str], benchmark: str=BENCHMARK_SYMBOL) -> tuple[pd.DataFrame, list[str]]`
- [compute_swing_scores](../../ihm/services/swing_score.py) — ligne 334 : `def compute_swing_scores(symbols: list[str]) -> tuple[pd.DataFrame, dict[str, object]]`
- [_load_tradable_universe_history_union](../../ihm/services/swing_score.py) — ligne 383 : `def _load_tradable_universe_history_union() -> list[str]`
- [resolve_universe_symbols](../../ihm/services/swing_score.py) — ligne 395 : `def resolve_universe_symbols(symbol_source: str) -> list[str]`

## `ihm/services/tax_data.py`

Source SHA-256 : `4ac2114a9da963c757f1884524c726dcfcc77deb81b81deb7965ad80a4e489fb`

- [TaxLotRow](../../ihm/services/tax_data.py) — ligne 17 : `class TaxLotRow`
- [lot_to_row](../../ihm/services/tax_data.py) — ligne 28 : `def lot_to_row(lot: Lot) -> TaxLotRow`
- [load_demo_lots](../../ihm/services/tax_data.py) — ligne 39 : `def load_demo_lots() -> list[Lot]`
- [filter_lots](../../ihm/services/tax_data.py) — ligne 53 : `def filter_lots(lots: Iterable[Lot], *, symbol: str | None=None, date_from: date | None=None, date_to: date | None=None) -> list[Lot]`
- [compute_report](../../ihm/services/tax_data.py) — ligne 72 : `def compute_report(lots: Sequence[Lot]) -> WashSaleReport`
- [lots_to_table](../../ihm/services/tax_data.py) — ligne 76 : `def lots_to_table(lots: Sequence[Lot], report: WashSaleReport) -> list[dict]`

## `ihm/services/theme_manager.py`

Source SHA-256 : `49c3bda28ccab0296d930f9e8b99d174db870daba9c3a309b475b7e7ff81a908`

- [get_current_theme](../../ihm/services/theme_manager.py) — ligne 26 : `def get_current_theme(state: dict | None=None) -> ThemeName`
- [set_theme](../../ihm/services/theme_manager.py) — ligne 34 : `def set_theme(state: dict, theme: ThemeName) -> None`
- [build_css](../../ihm/services/theme_manager.py) — ligne 38 : `def build_css(theme: ThemeName) -> str`
- [apply_theme_chrome](../../ihm/services/theme_manager.py) — ligne 163 : `def apply_theme_chrome(st_module, theme: ThemeName) -> None`
- [render_theme_toggle](../../ihm/services/theme_manager.py) — ligne 173 : `def render_theme_toggle(st_module) -> ThemeName`

## `ihm/services/varEnv.py`

Source SHA-256 : `1d24802a2b783131bbc82e833d613ffe1d15f98f367b265ee29f078a0a3ff99d`

- [get_var_env_streamlit](../../ihm/services/varEnv.py) — ligne 9 : `def get_var_env_streamlit() -> io.BytesIO`
- [get_var_env](../../ihm/services/varEnv.py) — ligne 30 : `def get_var_env() -> str`
- [get_conf_var_env](../../ihm/services/varEnv.py) — ligne 37 : `def get_conf_var_env() -> list`
- [set_var_env](../../ihm/services/varEnv.py) — ligne 69 : `def set_var_env(csv_bytes: bytes, apply: bool=True) -> dict`
- [set_env_registry](../../ihm/services/varEnv.py) — ligne 121 : `def set_env_registry(name, value)`

## `ihm/services/watcher_runtime.py`

Source SHA-256 : `d3889a73163f30a76823f96f62813dd147046f3f6057f094f9979b18b873f307`

- [_watcher_leader_lock_account](../../ihm/services/watcher_runtime.py) — ligne 42 : `def _watcher_leader_lock_account(account_id: str | None=None) -> str`
- [_force_release_local_watcher_leader_lock](../../ihm/services/watcher_runtime.py) — ligne 46 : `def _force_release_local_watcher_leader_lock(account_id: str | None=None) -> None`
- [build_watcher_doc_reference](../../ihm/services/watcher_runtime.py) — ligne 62 : `def build_watcher_doc_reference() -> dict[str, str]`
- [build_watcher_command](../../ihm/services/watcher_runtime.py) — ligne 71 : `def build_watcher_command(*, mode: str, account_id: str | None=None, exec_run_id: str | None=None, limit: int=DEFAULT_WATCHER_LIMIT, broker_mode: str='paper', profit_taker_pct: float=0.08, trailing_stop_pct: float=0.05, manual_buy_stop_loss_pct: float=0.05, trailing_activation_trigger: str='multiple_r', trailing_activation_r_multiple: float=0.0, trailing_activation_profit_pct: float=0.03, service_interval_seconds: float=DEFAULT_SERVICE_INTERVAL_SECONDS, idle_interval_seconds: float=DEFAULT_IDLE_INTERVAL_SECONDS, heartbeat_interval_seconds: float=DEFAULT_HEARTBEAT_INTERVAL_SECONDS, log_level: str='INFO') -> list[str]`
- [list_active_watcher_runs](../../ihm/services/watcher_runtime.py) — ligne 132 : `def list_active_watcher_runs(*, account_id: str | None=None) -> list[dict[str, object]]`
- [list_watcher_run_history](../../ihm/services/watcher_runtime.py) — ligne 143 : `def list_watcher_run_history(*, account_id: str | None=None, limit: int=50) -> list[dict[str, object]]`
- [get_watcher_run_record](../../ihm/services/watcher_runtime.py) — ligne 156 : `def get_watcher_run_record(run_id: str) -> dict[str, object] | None`
- [read_watcher_run_logs](../../ihm/services/watcher_runtime.py) — ligne 165 : `def read_watcher_run_logs(run_id: str, *, stream: str='all') -> str`
- [build_watcher_log_download_name](../../ihm/services/watcher_runtime.py) — ligne 171 : `def build_watcher_log_download_name(run_id: str, *, stream: str='all') -> str`
- [build_windows_integration_rows](../../ihm/services/watcher_runtime.py) — ligne 177 : `def build_windows_integration_rows(*, account_id: str | None=None) -> list[dict[str, str]]`
- [get_active_local_watcher_service](../../ihm/services/watcher_runtime.py) — ligne 211 : `def get_active_local_watcher_service(*, account_id: str | None=None) -> dict[str, object] | None`
- [get_active_watcher_once_run](../../ihm/services/watcher_runtime.py) — ligne 218 : `def get_active_watcher_once_run(*, account_id: str | None=None) -> dict[str, object] | None`
- [launch_watcher_once](../../ihm/services/watcher_runtime.py) — ligne 225 : `def launch_watcher_once(*, db_config: dict[str, str | None] | None=None, account_id: str | None=None, exec_run_id: str | None=None, limit: int=DEFAULT_WATCHER_LIMIT, broker_mode: str='paper', profit_taker_pct: float=0.08, trailing_stop_pct: float=0.05, manual_buy_stop_loss_pct: float=0.05, trailing_activation_trigger: str='multiple_r', trailing_activation_r_multiple: float=0.0, trailing_activation_profit_pct: float=0.03, log_level: str='INFO') -> PipelineRunRecord`
- [start_local_watcher_service](../../ihm/services/watcher_runtime.py) — ligne 266 : `def start_local_watcher_service(*, db_config: dict[str, str | None] | None=None, account_id: str | None=None, exec_run_id: str | None=None, limit: int=DEFAULT_WATCHER_LIMIT, broker_mode: str='paper', service_interval_seconds: float=DEFAULT_SERVICE_INTERVAL_SECONDS, idle_interval_seconds: float=DEFAULT_IDLE_INTERVAL_SECONDS, heartbeat_interval_seconds: float=DEFAULT_HEARTBEAT_INTERVAL_SECONDS, profit_taker_pct: float=0.08, trailing_stop_pct: float=0.05, manual_buy_stop_loss_pct: float=0.05, trailing_activation_trigger: str='multiple_r', trailing_activation_r_multiple: float=0.0, trailing_activation_profit_pct: float=0.03, log_level: str='INFO') -> PipelineRunRecord`
- [stop_local_watcher_service](../../ihm/services/watcher_runtime.py) — ligne 313 : `def stop_local_watcher_service(run_id: str) -> bool`
- [restart_local_watcher_service](../../ihm/services/watcher_runtime.py) — ligne 325 : `def restart_local_watcher_service(*, db_config: dict[str, str | None] | None=None, account_id: str | None=None, exec_run_id: str | None=None, limit: int=DEFAULT_WATCHER_LIMIT, broker_mode: str='paper', service_interval_seconds: float=DEFAULT_SERVICE_INTERVAL_SECONDS, idle_interval_seconds: float=DEFAULT_IDLE_INTERVAL_SECONDS, heartbeat_interval_seconds: float=DEFAULT_HEARTBEAT_INTERVAL_SECONDS, profit_taker_pct: float=0.08, trailing_stop_pct: float=0.05, manual_buy_stop_loss_pct: float=0.05, trailing_activation_trigger: str='multiple_r', trailing_activation_r_multiple: float=0.0, trailing_activation_profit_pct: float=0.03, log_level: str='INFO') -> PipelineRunRecord`
- [serialize_local_watcher_control_state](../../ihm/services/watcher_runtime.py) — ligne 365 : `def serialize_local_watcher_control_state(*, account_id: str | None=None) -> dict[str, Any]`
- [list_alpaca_account_ids](../../ihm/services/watcher_runtime.py) — ligne 389 : `def list_alpaca_account_ids() -> list[str]`
- [_resolve_target_account_ids](../../ihm/services/watcher_runtime.py) — ligne 403 : `def _resolve_target_account_ids(account_id: str | None) -> list[str | None]`
- [launch_watcher_once_for_all_accounts](../../ihm/services/watcher_runtime.py) — ligne 416 : `def launch_watcher_once_for_all_accounts(*, db_config: dict[str, str | None] | None=None, **kwargs: Any) -> list[PipelineRunRecord]`
- [start_local_watcher_service_for_all_accounts](../../ihm/services/watcher_runtime.py) — ligne 446 : `def start_local_watcher_service_for_all_accounts(*, db_config: dict[str, str | None] | None=None, **kwargs: Any) -> list[PipelineRunRecord]`
- [serialize_all_accounts_watcher_control_state](../../ihm/services/watcher_runtime.py) — ligne 474 : `def serialize_all_accounts_watcher_control_state() -> dict[str, Any]`

## `ihm/services/windows_watcher_bridge.py`

Source SHA-256 : `2c79ba5a03ed2dd9ee354b3b1616aa92b6da44683986a93b930c91cd4693d98b`

- [_bridge_unavailable_payload](../../ihm/services/windows_watcher_bridge.py) — ligne 25 : `def _bridge_unavailable_payload(reason: str, *, script_key: str='status') -> dict[str, Any]`
- [run_allowed_bridge_script](../../ihm/services/windows_watcher_bridge.py) — ligne 37 : `def run_allowed_bridge_script(script_key: str, *, arguments: list[str] | None=None, timeout_seconds: int=DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]`
- [get_windows_watcher_status](../../ihm/services/windows_watcher_bridge.py) — ligne 110 : `def get_windows_watcher_status(*, workspace_path: str | None=None, task_name: str=DEFAULT_TASK_NAME, service_name: str=DEFAULT_SERVICE_NAME, timeout_seconds: int=DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]`
- [list_windows_watcher_log_sources](../../ihm/services/windows_watcher_bridge.py) — ligne 127 : `def list_windows_watcher_log_sources(payload: dict[str, Any] | None) -> list[dict[str, object]]`
- [read_windows_log_source](../../ihm/services/windows_watcher_bridge.py) — ligne 152 : `def read_windows_log_source(path_value: str, *, max_bytes: int=MAX_IMPORTED_LOG_BYTES) -> str`

## `ihm/theme/__init__.py`

Source SHA-256 : `66dd59f124d628145f65e4150fb42d64525886281e237c161a97d1f4d21c952b`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `ihm/theme/badges.py`

Source SHA-256 : `a3be5e7cc79e3f36365e850df7834457de0c9179f8b6f1972fb7f750ae351bf5`

- [status_badge](../../ihm/theme/badges.py) — ligne 23 : `def status_badge(label: str, level: str='neutral') -> str`

## `ihm/theme/icons.py`

Source SHA-256 : `7b7ccd26aa392807bddc015d73457ce53d2705f8f1e4b0e10d9018c677c4e066`

- [get_icon](../../ihm/theme/icons.py) — ligne 35 : `def get_icon(name: str, default: str='•') -> str`

## `ihm/theme/palette.py`

Source SHA-256 : `70d38ab553dd4396595abb5d368765ffc5883d5547e2e76ec7ca4ec1b242088a`

- [get_palette](../../ihm/theme/palette.py) — ligne 35 : `def get_palette(theme: ThemeName='light') -> dict[str, str]`

## `ihm/theme/typography.py`

Source SHA-256 : `268518fdb1b854d88529ae04265354538d50be75555cd7e2e1d0289a98e1442c`

Module sans déclaration publique/privée de classe ou fonction au niveau module.
