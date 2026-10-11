# Inventaire API — modelFactory

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `modelFactory/__init__.py`

Source SHA-256 : `6c6f43fab8be2a1765b48d430b2addccff3f9f64799b58acbbe7993fc234edd3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/__main__.py`

Source SHA-256 : `b580fa132e06c790b9f8dc15032d8dbc95741b1dc8953fa3b0d8e70dc0db7b50`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/analyze_p21_attribution.py`

Source SHA-256 : `dfedb10f24972b15e4d3f25442913477612848771e2134d02fb11e7088253847`

- [factor_for](../../modelFactory/analyze_p21_attribution.py) — ligne 36 : `def factor_for(eff_bps: float) -> float`
- [_variant_stats](../../modelFactory/analyze_p21_attribution.py) — ligne 49 : `def _variant_stats(trades: pd.DataFrame, label: str, w: pd.Series) -> dict`
- [main](../../modelFactory/analyze_p21_attribution.py) — ligne 68 : `def main(run_dir: str, out_json: str | None, min_trades: int) -> None`

## `modelFactory/auto_rollback.py`

Source SHA-256 : `82de13e48f2c91a615aaa416cb3804f67035d27cfd0f894d04dfa837befbd8ea`

- [AutoRollbackOutcome](../../modelFactory/auto_rollback.py) — ligne 32 : `class AutoRollbackOutcome`
- [AutoRollbackOutcome.to_dict](../../modelFactory/auto_rollback.py) — ligne 43 : `def to_dict(self) -> dict[str, Any]`
- [count_consecutive_disabled_days](../../modelFactory/auto_rollback.py) — ligne 57 : `def count_consecutive_disabled_days(decisions: list[tuple[date, Any]]) -> int`
- [auto_rollback_if_needed](../../modelFactory/auto_rollback.py) — ligne 77 : `def auto_rollback_if_needed(symbol: str, *, engine: Any=None, threshold_days: int=3, dry_run: bool=True, decision_history_loader: Callable[..., list[tuple[date, Any]]], challenger_resolver: Callable[..., Optional[str]], champion_swapper: Optional[Callable[..., dict[str, Any]]]=None, current_champion_loader: Optional[Callable[..., Optional[str]]]=None, notifier_factory: Optional[Callable[[], Any]]=None) -> AutoRollbackOutcome`
- [_coerce_date](../../modelFactory/auto_rollback.py) — ligne 204 : `def _coerce_date(value: Any) -> date`
- [decision_history_loader_sql](../../modelFactory/auto_rollback.py) — ligne 212 : `def decision_history_loader_sql(symbol: str, *, engine: Any, threshold_days: int=14, table: str='ml_drift_runs') -> list[tuple[date, Any]]`
- [current_champion_loader_sql](../../modelFactory/auto_rollback.py) — ligne 260 : `def current_champion_loader_sql(symbol: str, *, engine: Any) -> Optional[str]`
- [champion_swapper_sql](../../modelFactory/auto_rollback.py) — ligne 283 : `def champion_swapper_sql(symbol: str, *, from_model: Optional[str], to_model: str, engine: Any, reason: str, dry_run: bool=False, version: Optional[str]=None) -> dict[str, Any]`

## `modelFactory/backfill_global_rank_history.py`

Source SHA-256 : `0818d2bd2efeeb5bf7eeaf459a67982c6b73fc3f84661f8b3f439426913e0820`

- [_resolve_engine](../../modelFactory/backfill_global_rank_history.py) — ligne 28 : `def _resolve_engine()`
- [backfill_global_rank_history](../../modelFactory/backfill_global_rank_history.py) — ligne 42 : `def backfill_global_rank_history(batch_id: str, *, parquet_path: Path | None=None) -> dict`
- [main](../../modelFactory/backfill_global_rank_history.py) — ligne 114 : `def main() -> None`

## `modelFactory/batch_diagnostics.py`

Source SHA-256 : `09bfef22196063ec97d0a653d2ee10270cae0e5d0719c9d07a6dbfcb97926465`

- [_sanitize_float](../../modelFactory/batch_diagnostics.py) — ligne 29 : `def _sanitize_float(value: Any) -> float | None`
- [Section7Filters](../../modelFactory/batch_diagnostics.py) — ligne 146 : `class Section7Filters`
- [Section7Filters.is_active](../../modelFactory/batch_diagnostics.py) — ligne 168 : `def is_active(self) -> bool`
- [BatchFilters](../../modelFactory/batch_diagnostics.py) — ligne 176 : `class BatchFilters`
- [_load_config_defaults](../../modelFactory/batch_diagnostics.py) — ligne 192 : `def _load_config_defaults() -> dict[str, Any]`
- [_load_section7_config](../../modelFactory/batch_diagnostics.py) — ligne 203 : `def _load_section7_config() -> dict[str, Any]`
- [_compute_section7_filters](../../modelFactory/batch_diagnostics.py) — ligne 209 : `def _compute_section7_filters(df: pd.DataFrame, *, s7_cfg: dict[str, Any] | None=None) -> Section7Filters`
- [persist_batch_diagnostics](../../modelFactory/batch_diagnostics.py) — ligne 295 : `def persist_batch_diagnostics(engine: Engine, batch_id: str, *, top_n: int | None=None, bottom_n: int | None=None, weak_long_threshold: float | None=None, weak_short_threshold: float | None=None) -> int`
- [_get_latest_completed_batch_id](../../modelFactory/batch_diagnostics.py) — ligne 517 : `def _get_latest_completed_batch_id(engine: Engine) -> str | None`
- [get_batch_filters](../../modelFactory/batch_diagnostics.py) — ligne 527 : `def get_batch_filters(engine: Engine, batch_id: str | None=None, *, prefer_top_n: int | None=None) -> BatchFilters`
- [filter_predictions](../../modelFactory/batch_diagnostics.py) — ligne 688 : `def filter_predictions(predictions: pd.DataFrame, filters: BatchFilters, *, side_column: str='predicted_side', symbol_column: str='symbol', boost_prefer_sizing: bool=False, prefer_multiplier: float | None=None) -> pd.DataFrame`

## `modelFactory/batch_logs.py`

Source SHA-256 : `61d2ed89a953cc2907c9bf527dd2f503bfadcdfbadd918cd4868700923ee275c`

- [_safe_name](../../modelFactory/batch_logs.py) — ligne 30 : `def _safe_name(batch_id: str) -> str`
- [_scan_log_files](../../modelFactory/batch_logs.py) — ligne 34 : `def _scan_log_files() -> list[Path]`
- [extract_batch_log_lines](../../modelFactory/batch_logs.py) — ligne 47 : `def extract_batch_log_lines(batch_id: str) -> list[str]`
- [persist_batch_log](../../modelFactory/batch_logs.py) — ligne 59 : `def persist_batch_log(batch_id: str) -> Path | None`
- [read_batch_log](../../modelFactory/batch_logs.py) — ligne 85 : `def read_batch_log(batch_id: str) -> str | None`
- [backfill_existing_batches](../../modelFactory/batch_logs.py) — ligne 96 : `def backfill_existing_batches() -> dict[str, int]`
- [batch_logs_text](../../modelFactory/batch_logs.py) — ligne 143 : `def batch_logs_text(batch_id: str) -> str`

## `modelFactory/calibration.py`

Source SHA-256 : `fe4002d2b309bf2e28c9bac1c022c00e158945b145fd09379df9c1203678a6d1`

- [margin_from_logits](../../modelFactory/calibration.py) — ligne 12 : `def margin_from_logits(logits: np.ndarray | torch.Tensor) -> np.ndarray`
- [PlattCalibrator](../../modelFactory/calibration.py) — ligne 24 : `class PlattCalibrator`
- [PlattCalibrator.method](../../modelFactory/calibration.py) — ligne 33 : `def method(self) -> str`
- [PlattCalibrator.fit](../../modelFactory/calibration.py) — ligne 36 : `def fit(self, margins: np.ndarray, targets: np.ndarray) -> 'PlattCalibrator'`
- [PlattCalibrator.predict_proba](../../modelFactory/calibration.py) — ligne 62 : `def predict_proba(self, margins: np.ndarray | torch.Tensor) -> np.ndarray`
- [PlattCalibrator.state_dict](../../modelFactory/calibration.py) — ligne 67 : `def state_dict(self) -> dict[str, Any]`
- [PlattCalibrator.from_state_dict](../../modelFactory/calibration.py) — ligne 77 : `def from_state_dict(cls, state: dict[str, Any]) -> 'PlattCalibrator'`
- [margins_from_logits_or_margin](../../modelFactory/calibration.py) — ligne 86 : `def margins_from_logits_or_margin(values: np.ndarray | torch.Tensor) -> np.ndarray`
- [probabilities_to_pseudo_logits](../../modelFactory/calibration.py) — ligne 97 : `def probabilities_to_pseudo_logits(probabilities: np.ndarray) -> np.ndarray`
- [calibrator_from_state_dict](../../modelFactory/calibration.py) — ligne 116 : `def calibrator_from_state_dict(state: dict[str, Any] | None) -> PlattCalibrator | TemperatureScaler | VectorScaler | None`
- [_positive_temperature](../../modelFactory/calibration.py) — ligne 133 : `def _positive_temperature(value: float) -> float`
- [_multiclass_logits](../../modelFactory/calibration.py) — ligne 140 : `def _multiclass_logits(values: np.ndarray | torch.Tensor) -> torch.Tensor`
- [_multiclass_labels](../../modelFactory/calibration.py) — ligne 148 : `def _multiclass_labels(labels: np.ndarray, x: torch.Tensor) -> torch.Tensor`
- [_vector_biases](../../modelFactory/calibration.py) — ligne 157 : `def _vector_biases(values: np.ndarray | None, classes: int | None=None) -> np.ndarray | None`
- [TemperatureScaler](../../modelFactory/calibration.py) — ligne 167 : `class TemperatureScaler`
- [TemperatureScaler.__post_init__](../../modelFactory/calibration.py) — ligne 193 : `def __post_init__(self) -> None`
- [TemperatureScaler.method](../../modelFactory/calibration.py) — ligne 197 : `def method(self) -> str`
- [TemperatureScaler.fit](../../modelFactory/calibration.py) — ligne 200 : `def fit(self, logits: np.ndarray, labels: np.ndarray) -> 'TemperatureScaler'`
- [TemperatureScaler.predict](../../modelFactory/calibration.py) — ligne 239 : `def predict(self, logits: np.ndarray | torch.Tensor) -> np.ndarray`
- [TemperatureScaler.predict_proba](../../modelFactory/calibration.py) — ligne 254 : `def predict_proba(self, logits: np.ndarray | torch.Tensor) -> np.ndarray`
- [TemperatureScaler.state_dict](../../modelFactory/calibration.py) — ligne 258 : `def state_dict(self) -> dict[str, Any]`
- [TemperatureScaler.from_state_dict](../../modelFactory/calibration.py) — ligne 267 : `def from_state_dict(cls, state: dict[str, Any]) -> 'TemperatureScaler'`
- [VectorScaler](../../modelFactory/calibration.py) — ligne 280 : `class VectorScaler`
- [VectorScaler.__post_init__](../../modelFactory/calibration.py) — ligne 310 : `def __post_init__(self) -> None`
- [VectorScaler.method](../../modelFactory/calibration.py) — ligne 315 : `def method(self) -> str`
- [VectorScaler.fit](../../modelFactory/calibration.py) — ligne 318 : `def fit(self, logits: np.ndarray, labels: np.ndarray) -> 'VectorScaler'`
- [VectorScaler.predict](../../modelFactory/calibration.py) — ligne 367 : `def predict(self, logits: np.ndarray | torch.Tensor) -> np.ndarray`
- [VectorScaler.predict_proba](../../modelFactory/calibration.py) — ligne 388 : `def predict_proba(self, logits: np.ndarray | torch.Tensor) -> np.ndarray`
- [VectorScaler.state_dict](../../modelFactory/calibration.py) — ligne 392 : `def state_dict(self) -> dict[str, Any]`
- [VectorScaler.from_state_dict](../../modelFactory/calibration.py) — ligne 402 : `def from_state_dict(cls, state: dict[str, Any]) -> 'VectorScaler'`

## `modelFactory/catboost_baseline.py`

Source SHA-256 : `85fdf1966f35f366090adc4ce823d67b113332da82c40cc36a7666a3d010790b`

- [_import_catboost](../../modelFactory/catboost_baseline.py) — ligne 16 : `def _import_catboost() -> Any`
- [run_catboost_baseline](../../modelFactory/catboost_baseline.py) — ligne 21 : `def run_catboost_baseline(prepared_df: pd.DataFrame, cfg: TrainingConfig, *, artifact_dir: Path | None=None, ternary_policy: 'TernaryDecisionPolicy | None'=None) -> dict[str, Any]`

## `modelFactory/champion_selection.py`

Source SHA-256 : `bf60499631d50a117f86adaa3eb2467f4fd0f2c13ca6cfc47eafa3154fc50021`

- [ArtifactSignatureError](../../modelFactory/champion_selection.py) — ligne 44 : `class ArtifactSignatureError(RuntimeError)`
- [ArtifactSignatureError.__init__](../../modelFactory/champion_selection.py) — ligne 47 : `def __init__(self, reason: str, *, path: Path | None=None) -> None`
- [_artifact_path_from_value](../../modelFactory/champion_selection.py) — ligne 53 : `def _artifact_path_from_value(value: object) -> Path | None`
- [_sha256_file](../../modelFactory/champion_selection.py) — ligne 61 : `def _sha256_file(path: Path) -> str`
- [build_artifact_signature_manifest](../../modelFactory/champion_selection.py) — ligne 69 : `def build_artifact_signature_manifest(*, symbol: str, run_id: str | None, selected_model: str | None, artifact_routes_models: dict[str, dict[str, Any]]) -> dict[str, Any]`
- [persist_artifact_signature_manifest](../../modelFactory/champion_selection.py) — ligne 105 : `def persist_artifact_signature_manifest(manifest_path: Path, *, symbol: str, run_id: str | None, selected_model: str | None, artifact_routes_models: dict[str, dict[str, Any]]) -> dict[str, Any]`
- [verify_route_artifact_signatures](../../modelFactory/champion_selection.py) — ligne 125 : `def verify_route_artifact_signatures(*, manifest_path: Path, model_name: str, route: dict[str, Any], required: bool) -> None`
- [is_under_quarantine](../../modelFactory/champion_selection.py) — ligne 170 : `def is_under_quarantine(model_name: str, symbol: str, *, min_runs: int, min_days: int, lookup: QuarantineLookup, now: Optional[datetime]=None) -> tuple[bool, str]`
- [_finite_float](../../modelFactory/champion_selection.py) — ligne 207 : `def _finite_float(value: Any) -> float | None`
- [_walk_forward_payload](../../modelFactory/champion_selection.py) — ligne 215 : `def _walk_forward_payload(result: dict[str, Any]) -> dict[str, Any]`
- [_estimated_directional_support](../../modelFactory/champion_selection.py) — ligne 223 : `def _estimated_directional_support(split: dict[str, Any], side: str) -> int | None`
- [directional_selection_evidence](../../modelFactory/champion_selection.py) — ligne 236 : `def directional_selection_evidence(result: dict[str, Any], metric: str) -> dict[str, Any]`
- [selection_score_from_result](../../modelFactory/champion_selection.py) — ligne 291 : `def selection_score_from_result(result: dict[str, Any], metric: str='selection_score') -> float`
- [evaluate_selection_eligibility](../../modelFactory/champion_selection.py) — ligne 354 : `def evaluate_selection_eligibility(model_name: str, result: dict[str, Any], artifact_route: dict[str, Any] | None) -> tuple[bool, str | None]`
- [_validate_metric_gates](../../modelFactory/champion_selection.py) — ligne 405 : `def _validate_metric_gates(result: dict[str, Any]) -> str | None`
- [annotate_challengers](../../modelFactory/champion_selection.py) — ligne 469 : `def annotate_challengers(challengers: dict[str, dict[str, Any]], artifact_routes_models: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]`
- [select_champion](../../modelFactory/champion_selection.py) — ligne 485 : `def select_champion(challengers: dict[str, dict[str, Any]], artifact_routes_models: dict[str, dict[str, Any]], champion_cfg: ChampionSelectionConfig, *, quarantine_lookup: QuarantineLookup | None=None, symbol: str | None=None, selection_metric_override: str | None=None) -> dict[str, Any]`
- [build_challenger_ranking](../../modelFactory/champion_selection.py) — ligne 606 : `def build_challenger_ranking(challengers: dict[str, dict[str, Any]], artifact_routes_models: dict[str, dict[str, Any]], champion_name: str, *, selection_mode: str, champion_cfg: ChampionSelectionConfig, selection_metric_override: str | None=None) -> list[dict[str, Any]]`

## `modelFactory/cleanup_incomplete_batches.py`

Source SHA-256 : `73006ae76cbd2d64b60ab3bfc8519c723c1fb4c056c13009a56ba7d805791141`

- [_is_safe_batch_id](../../modelFactory/cleanup_incomplete_batches.py) — ligne 16 : `def _is_safe_batch_id(batch_id: str) -> bool`
- [list_batches](../../modelFactory/cleanup_incomplete_batches.py) — ligne 29 : `def list_batches(include_completed: bool=False) -> list[str]`
- [cleanup_batches](../../modelFactory/cleanup_incomplete_batches.py) — ligne 63 : `def cleanup_batches(dry_run: bool=False, include_completed: bool=False) -> dict`
- [main](../../modelFactory/cleanup_incomplete_batches.py) — ligne 153 : `def main() -> None`

## `modelFactory/cli.py`

Source SHA-256 : `a269e74706b15c3a203266791245fe7e3b4cd7158cc5f37cedaf5a0d585edbdb`

- [_safe_print](../../modelFactory/cli.py) — ligne 49 : `def _safe_print(message: object) -> None`
- [enforce_directional_bundle_target_options](../../modelFactory/cli.py) — ligne 58 : `def enforce_directional_bundle_target_options(opts: argparse.Namespace) -> argparse.Namespace`
- [_resolve_synth_best_h](../../modelFactory/cli.py) — ligne 77 : `def _resolve_synth_best_h(opts, batch_id: str | None) -> int`
- [_load_live_dip_config](../../modelFactory/cli.py) — ligne 119 : `def _load_live_dip_config() -> dict | None`
- [PredictionPersistenceError](../../modelFactory/cli.py) — ligne 142 : `class PredictionPersistenceError(RuntimeError)`
- [_persist_predictions_with_policy](../../modelFactory/cli.py) — ligne 146 : `def _persist_predictions_with_policy(engine, chunk: pd.DataFrame, *, insert_fn, operation: str, prediction_date: date | None=None, required: bool=False) -> None`
- [_directional_bundle_prediction_coverage](../../modelFactory/cli.py) — ligne 187 : `def _directional_bundle_prediction_coverage(engine, batch_id: str, *, start_date: date | None=None, end_date: date | None=None) -> tuple[int, int]`
- [_require_directional_bundle_predictions](../../modelFactory/cli.py) — ligne 221 : `def _require_directional_bundle_predictions(engine, batch_id: str, *, start_date: date | None=None, end_date: date | None=None, expected_dates: int=1) -> tuple[int, int]`
- [_parse_symbol_source_arg](../../modelFactory/cli.py) — ligne 258 : `def _parse_symbol_source_arg(value: str) -> str`
- [_generate_and_save_batch_report](../../modelFactory/cli.py) — ligne 269 : `def _generate_and_save_batch_report(engine: Engine, batch_id: str) -> None`
- [_resolve_predict_batch_id](../../modelFactory/cli.py) — ligne 294 : `def _resolve_predict_batch_id(artifacts_dir: Path, *, historical: bool=True) -> str | None`
- [_require_live_global_ranks](../../modelFactory/cli.py) — ligne 320 : `def _require_live_global_ranks(results: dict[str, int], *, day: str, batch_id: str) -> None`
- [_require_live_synthesis](../../modelFactory/cli.py) — ligne 330 : `def _require_live_synthesis(result: dict, *, day: str, batch_id: str) -> None`
- [_resolve_last_bar_date](../../modelFactory/cli.py) — ligne 335 : `def _resolve_last_bar_date(engine) -> date | None`
- [_load_synth_frame_for_range](../../modelFactory/cli.py) — ligne 350 : `def _load_synth_frame_for_range(engine, batch_id: str, dates) -> 'pd.DataFrame'`
- [_build_training_batch_command](../../modelFactory/cli.py) — ligne 381 : `def _build_training_batch_command(raw_args: list[str]) -> tuple[str, str]`
- [_build_training_batch_metadata](../../modelFactory/cli.py) — ligne 386 : `def _build_training_batch_metadata(opts: argparse.Namespace, cfg: TrainingConfig) -> str`
- [_parse_selector_signal_modes_arg](../../modelFactory/cli.py) — ligne 422 : `def _parse_selector_signal_modes_arg(values: list[str] | None) -> tuple[str, ...]`
- [_parse_iso_date_arg](../../modelFactory/cli.py) — ligne 435 : `def _parse_iso_date_arg(value: str) -> date`
- [_LiveRunSummaryEmitter](../../modelFactory/cli.py) — ligne 442 : `class _LiveRunSummaryEmitter`
- [_LiveRunSummaryEmitter.__init__](../../modelFactory/cli.py) — ligne 443 : `def __init__(self, *, run_id: str, mode: str, heartbeat_interval_seconds: float, watchdog_timeout_seconds: int, debug_train: bool) -> None`
- [_LiveRunSummaryEmitter.__enter__](../../modelFactory/cli.py) — ligne 461 : `def __enter__(self) -> '_LiveRunSummaryEmitter'`
- [_LiveRunSummaryEmitter.__exit__](../../modelFactory/cli.py) — ligne 468 : `def __exit__(self, exc_type, exc, tb) -> None`
- [_LiveRunSummaryEmitter._run](../../modelFactory/cli.py) — ligne 473 : `def _run(self) -> None`
- [_LiveRunSummaryEmitter.emit_now](../../modelFactory/cli.py) — ligne 477 : `def emit_now(self) -> None`
- [build_arg_parser](../../modelFactory/cli.py) — ligne 511 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../modelFactory/cli.py) — ligne 864 : `def main(args: list[str] | None=None) -> None`
- [_load_drift_baseline](../../modelFactory/cli.py) — ligne 1906 : `def _load_drift_baseline(engine, *, days: int=30)`
- [_emit_run_summary](../../modelFactory/cli.py) — ligne 1933 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_build_run_summary](../../modelFactory/cli.py) — ligne 1940 : `def _build_run_summary(*, mode: str, run_id: str, opts: argparse.Namespace, cfg: TrainingConfig, started_at: datetime, finished_at: datetime, symbols_total: int, completed: int, skipped: int, failed: int, quarantined: int, drift_decision: object | None=None) -> dict[str, object]`

## `modelFactory/cn_corporate_action_a2.py`

Source SHA-256 : `1371ab890bb490a5a30da4274678f46dad3a4ff3d6a97d7ef161d38880e3b530`

- [_decimal](../../modelFactory/cn_corporate_action_a2.py) — ligne 42 : `def _decimal(value: Any) -> Decimal | None`
- [_day](../../modelFactory/cn_corporate_action_a2.py) — ligne 52 : `def _day(value: Any) -> date | None`
- [_sha_json](../../modelFactory/cn_corporate_action_a2.py) — ligne 61 : `def _sha_json(value: Any) -> str`
- [classify](../../modelFactory/cn_corporate_action_a2.py) — ligne 65 : `def classify(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]`
- [load_events](../../modelFactory/cn_corporate_action_a2.py) — ligne 171 : `def load_events() -> tuple[list[dict[str, Any]], list[date], dict[int, date | None]]`
- [_cache_file](../../modelFactory/cn_corporate_action_a2.py) — ligne 229 : `def _cache_file(root: Path, symbol: str, year: int) -> Path`
- [_write_atomic](../../modelFactory/cn_corporate_action_a2.py) — ligne 233 : `def _write_atomic(path: Path, value: Any) -> None`
- [collect](../../modelFactory/cn_corporate_action_a2.py) — ligne 240 : `def collect(*, root: Path=OUTPUT, max_new_groups: int | None=None, shard_index: int=0, shard_count: int=1, finalize_only: bool=False) -> dict[str, Any]`
- [_audit_gate](../../modelFactory/cn_corporate_action_a2.py) — ligne 331 : `def _audit_gate(dates: dict[int, list[date]], sessions: list[date], delistings: dict[int, date | None]) -> dict[str, Any]`
- [main](../../modelFactory/cn_corporate_action_a2.py) — ligne 377 : `def main() -> None`

## `modelFactory/cn_directional_diagnostic.py`

Source SHA-256 : `11c75a91252a9625cb2a13b2b5d718c3fbb07921c58a37eac2f9baa448dfc0de`

- [load_protocol](../../modelFactory/cn_directional_diagnostic.py) — ligne 32 : `def load_protocol(path: Path) -> dict[str, Any]`
- [combine_oos](../../modelFactory/cn_directional_diagnostic.py) — ligne 61 : `def combine_oos(lightgbm: pd.DataFrame, catboost: pd.DataFrame) -> pd.DataFrame`
- [prepare_pool](../../modelFactory/cn_directional_diagnostic.py) — ligne 92 : `def prepare_pool(frame: pd.DataFrame, *, minimum: int) -> tuple[pd.DataFrame, dict[str, int]]`
- [policy_masks](../../modelFactory/cn_directional_diagnostic.py) — ligne 119 : `def policy_masks(pool: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.Series]`
- [counts](../../modelFactory/cn_directional_diagnostic.py) — ligne 143 : `def counts(pool: pd.DataFrame, mask: pd.Series, *, scope: pd.Series | None=None) -> dict[str, float | int | None]`
- [metrics](../../modelFactory/cn_directional_diagnostic.py) — ligne 162 : `def metrics(value: dict[str, float | int | None], reference: dict[str, float | int | None]) -> dict[str, float | int | None]`
- [_sum_counts](../../modelFactory/cn_directional_diagnostic.py) — ligne 184 : `def _sum_counts(values: list[dict[str, float | int | None]]) -> dict[str, float | int | None]`
- [summarize](../../modelFactory/cn_directional_diagnostic.py) — ligne 190 : `def summarize(folds: list[dict[str, Any]]) -> dict[str, Any]`
- [evaluate_fold](../../modelFactory/cn_directional_diagnostic.py) — ligne 228 : `def evaluate_fold(pool: pd.DataFrame, *, config: dict[str, Any], horizon: int, semester: str) -> dict[str, Any]`
- [run](../../modelFactory/cn_directional_diagnostic.py) — ligne 256 : `def run(*, config_path: Path=DEFAULT_CONFIG, ranking_root: Path=RANKING_OUTPUT, output_root: Path=DEFAULT_OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_directional_diagnostic.py) — ligne 308 : `def main() -> None`

## `modelFactory/cn_dragon_tiger_preflight_15d5.py`

Source SHA-256 : `89f1394dddac2d3d048a2548ef71408a4b09f6b40cadd4f0fbe24d67a17444c2`

- [summarize_deciles](../../modelFactory/cn_dragon_tiger_preflight_15d5.py) — ligne 10 : `def summarize_deciles(source: dict, window: int) -> dict`
- [preflight](../../modelFactory/cn_dragon_tiger_preflight_15d5.py) — ligne 39 : `def preflight(report: dict) -> dict`
- [main](../../modelFactory/cn_dragon_tiger_preflight_15d5.py) — ligne 67 : `def main() -> None`

## `modelFactory/cn_economic_decision_13c.py`

Source SHA-256 : `fd7c679586fcaeb414318ff333e01c2fad4daefcfd1c227a173f88d260e324c8`

- [_key](../../modelFactory/cn_economic_decision_13c.py) — ligne 46 : `def _key(semester: str, policy: str, seed: int, scenario: str, cost: str) -> str`
- [_cohorts](../../modelFactory/cn_economic_decision_13c.py) — ligne 50 : `def _cohorts() -> list[tuple[str, int, str, str]]`
- [_metric](../../modelFactory/cn_economic_decision_13c.py) — ligne 56 : `def _metric(row: dict[str, Any], name: str) -> float | None`
- [_verify](../../modelFactory/cn_economic_decision_13c.py) — ligne 66 : `def _verify(report: dict[str, Any], policies: tuple[str, ...], reference: dict[str, Any] | None=None) -> None`
- [_summarize](../../modelFactory/cn_economic_decision_13c.py) — ligne 123 : `def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]`
- [analyze](../../modelFactory/cn_economic_decision_13c.py) — ligne 135 : `def analyze(base: dict[str, Any], momentum: dict[str, Any] | None=None) -> dict[str, Any]`
- [run](../../modelFactory/cn_economic_decision_13c.py) — ligne 240 : `def run(*, base_path: Path=BASE, momentum_path: Path | None=None, output_root: Path=OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_decision_13c.py) — ligne 261 : `def main() -> None`

## `modelFactory/cn_economic_materiality_13b5.py`

Source SHA-256 : `7b8842799ae3a64c41f93b2a6e7e47e730e19ca4595c13b52c56418079477747`

- [analyze](../../modelFactory/cn_economic_materiality_13b5.py) — ligne 38 : `def analyze(original: dict[str, Any], overlays: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]`
- [run](../../modelFactory/cn_economic_materiality_13b5.py) — ligne 112 : `def run(*, original_path: Path=ORIGINAL, overlay_paths: list[tuple[str, Path]] | None=None, output_root: Path=OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_materiality_13b5.py) — ligne 146 : `def main() -> None`

## `modelFactory/cn_economic_preflight.py`

Source SHA-256 : `9db56aea7489b08c20eb47c7ca2c39c8bbbed29cb3662567b4fd838e8a3088b8`

- [load_protocol](../../modelFactory/cn_economic_preflight.py) — ligne 38 : `def load_protocol(path: Path) -> dict[str, Any]`
- [select_policies](../../modelFactory/cn_economic_preflight.py) — ligne 78 : `def select_policies(frame: pd.DataFrame, *, minimum: int) -> tuple[pd.DataFrame, dict[str, pd.Series]]`
- [audit_exposure](../../modelFactory/cn_economic_preflight.py) — ligne 103 : `def audit_exposure(candidates: pd.DataFrame, *, sessions: list[date], action_dates: dict[int, list[date]], delistings: dict[int, date | None]) -> dict[str, Any]`
- [run](../../modelFactory/cn_economic_preflight.py) — ligne 153 : `def run(*, config_path: Path=DEFAULT_CONFIG, output_root: Path=DEFAULT_OUTPUT, ranking_root: Path=RANKING_OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_preflight.py) — ligne 307 : `def main() -> None`

## `modelFactory/cn_economic_remediation_13b2.py`

Source SHA-256 : `3fc64780ffe711b2430abe8b7e4e7d3748387051cb5b8d15bfe3b26524c75d01`

- [build](../../modelFactory/cn_economic_remediation_13b2.py) — ligne 32 : `def build(*, base: Path=BASE, output: Path=OUTPUT) -> dict`
- [main](../../modelFactory/cn_economic_remediation_13b2.py) — ligne 180 : `def main() -> None`

## `modelFactory/cn_economic_remediation_13b3.py`

Source SHA-256 : `104f958652bc735a10bd91377513022888d52e72f511af5c670c61987e92e7d6`

- [promote](../../modelFactory/cn_economic_remediation_13b3.py) — ligne 32 : `def promote(event: dict[str, Any], rows: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]`
- [build](../../modelFactory/cn_economic_remediation_13b3.py) — ligne 54 : `def build(*, base: Path=BASE, output: Path=OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_remediation_13b3.py) — ligne 134 : `def main() -> None`

## `modelFactory/cn_economic_remediation_13b4.py`

Source SHA-256 : `8ca8b33f5f9b122d1c89ca1e4c278e5101371b3aca59b58354a13035df1db49b`

- [promote](../../modelFactory/cn_economic_remediation_13b4.py) — ligne 55 : `def promote(event: dict[str, Any], rows: list[dict[str, Any]], previous: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]`
- [build](../../modelFactory/cn_economic_remediation_13b4.py) — ligne 104 : `def build(*, base: Path=BASE, output: Path=OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_remediation_13b4.py) — ligne 193 : `def main() -> None`

## `modelFactory/cn_economic_remediation_13b5.py`

Source SHA-256 : `93d02ea46f8c1a1bd446978e7f07077550ee760c13ee2bb10e847352e4205505`

- [promote](../../modelFactory/cn_economic_remediation_13b5.py) — ligne 62 : `def promote(event: dict[str, Any], rows: list[dict[str, Any]], previous: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]`
- [build](../../modelFactory/cn_economic_remediation_13b5.py) — ligne 124 : `def build(*, base: Path=BASE, output: Path=OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_remediation_13b5.py) — ligne 221 : `def main() -> None`

## `modelFactory/cn_economic_replay_13b.py`

Source SHA-256 : `a1fbacb9afa377df7e1fc929f273388cbd3448be3d9dfad68a95007dab720aa5`

- [_sha_json](../../modelFactory/cn_economic_replay_13b.py) — ligne 47 : `def _sha_json(value: Any) -> str`
- [_source](../../modelFactory/cn_economic_replay_13b.py) — ligne 52 : `def _source(semester: str) -> tuple[Path, dict[str, Any]]`
- [select_momentum](../../modelFactory/cn_economic_replay_13b.py) — ligne 65 : `def select_momentum(frame: pd.DataFrame) -> pd.DataFrame`
- [eligible_signal_dates](../../modelFactory/cn_economic_replay_13b.py) — ligne 78 : `def eligible_signal_dates(sessions: list[date], *, horizon: int=20) -> set[date]`
- [_tie_priority](../../modelFactory/cn_economic_replay_13b.py) — ligne 83 : `def _tie_priority(semester: str, signal_date: date, instrument_id: int, seed: int) -> Decimal`
- [make_intents](../../modelFactory/cn_economic_replay_13b.py) — ligne 88 : `def make_intents(selected: pd.DataFrame, *, semester: str, seed: int, valid_dates: set[date], ticket: Decimal, policy: str) -> list[CNIntent]`
- [_benchmark_csi300](../../modelFactory/cn_economic_replay_13b.py) — ligne 103 : `def _benchmark_csi300(conn: Any, start: date, end: date) -> dict[str, Any]`
- [summarize_replay](../../modelFactory/cn_economic_replay_13b.py) — ligne 122 : `def summarize_replay(result: Any, *, capital: Decimal) -> dict[str, Any]`
- [aggregate_runs](../../modelFactory/cn_economic_replay_13b.py) — ligne 185 : `def aggregate_runs(runs: dict[str, dict[str, Any]]) -> dict[str, Any]`
- [run](../../modelFactory/cn_economic_replay_13b.py) — ligne 211 : `def run(*, output_root: Path=DEFAULT_OUTPUT, evidence_path: Path=DEFAULT_EVIDENCE, semesters: list[str] | None=None, policies: list[str] | None=None, seeds: list[int] | None=None, scenarios: list[str] | None=None, cost_profiles: list[str] | None=None) -> dict[str, Any]`
- [main](../../modelFactory/cn_economic_replay_13b.py) — ligne 341 : `def main() -> None`

## `modelFactory/cn_feature_panel.py`

Source SHA-256 : `e27c40f6f353a8a54ae249c2cbbe0a200b142a7415bb1c583982d51d3f1cf57e`

- [CNFeatureProfile](../../modelFactory/cn_feature_panel.py) — ligne 36 : `class CNFeatureProfile`
- [CNFeatureProfile.from_yaml](../../modelFactory/cn_feature_panel.py) — ligne 45 : `def from_yaml(cls, path: Path) -> CNFeatureProfile`
- [_rolling_return](../../modelFactory/cn_feature_panel.py) — ligne 64 : `def _rolling_return(values: pd.Series, periods: int) -> pd.Series`
- [compute_symbol_features](../../modelFactory/cn_feature_panel.py) — ligne 69 : `def compute_symbol_features(bars: pd.DataFrame, factor_events: pd.DataFrame | None=None) -> pd.DataFrame`
- [assemble_candidate_panel](../../modelFactory/cn_feature_panel.py) — ligne 134 : `def assemble_candidate_panel(candidates: pd.DataFrame, features: pd.DataFrame, benchmark: pd.DataFrame, limits: pd.DataFrame, *, profile: CNFeatureProfile) -> pd.DataFrame`
- [_load_frames](../../modelFactory/cn_feature_panel.py) — ligne 207 : `def _load_frames(engine: Engine, *, start: date, end: date, profile: CNFeatureProfile, universe_policy: CNUniversePolicy) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [build_panel](../../modelFactory/cn_feature_panel.py) — ligne 259 : `def build_panel(*, start: date, end: date, profile_path: Path=DEFAULT_PROFILE, universe_policy_path: Path=DEFAULT_UNIVERSE_POLICY, output_root: Path | None=None) -> dict[str, Any]`

## `modelFactory/cn_global_ranking_aggregate.py`

Source SHA-256 : `e3776bbc4d59fd41078feadce66e60a2ab362d3b79a347b285100f327037a564`

- [_find_run](../../modelFactory/cn_global_ranking_aggregate.py) — ligne 24 : `def _find_run(root: Path, *, horizon: int, semester: str, model: str, config_sha: str, code_sha: str, audit_sha: str) -> tuple[Path, dict[str, Any]] | None`
- [_monthly_bootstrap](../../modelFactory/cn_global_ranking_aggregate.py) — ligne 41 : `def _monthly_bootstrap(frame: pd.DataFrame, *, tail_pct: float, repetitions: int, alpha: float, seed: int) -> dict[str, float | int]`
- [_subgroups](../../modelFactory/cn_global_ranking_aggregate.py) — ligne 74 : `def _subgroups(frame: pd.DataFrame, *, tail_pct: float) -> dict[str, Any]`
- [aggregate](../../modelFactory/cn_global_ranking_aggregate.py) — ligne 100 : `def aggregate(*, config_path: Path=DEFAULT_CONFIG, root: Path=DEFAULT_OUTPUT, require_complete: bool=False) -> dict[str, Any]`
- [main](../../modelFactory/cn_global_ranking_aggregate.py) — ligne 195 : `def main() -> None`

## `modelFactory/cn_global_ranking_posthoc.py`

Source SHA-256 : `0b2f373cc3c95fc2520da11b41cb869771aaa89c2dd9be7e6bf09c7d15a61e39`

- [diagnose](../../modelFactory/cn_global_ranking_posthoc.py) — ligne 22 : `def diagnose(*, config_path: Path=DEFAULT_CONFIG, root: Path=DEFAULT_OUTPUT) -> dict[str, object]`
- [main](../../modelFactory/cn_global_ranking_posthoc.py) — ligne 54 : `def main() -> None`

## `modelFactory/cn_global_ranking_walk_forward.py`

Source SHA-256 : `d9a28587ccd02cd8e4fb473b66a532219933070386779451f3c3fc2276c6547a`

- [RankingProtocol](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 43 : `class RankingProtocol`
- [RankingProtocol.load](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 48 : `def load(cls, path: Path) -> RankingProtocol`
- [_attach_oracle_pool](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 70 : `def _attach_oracle_pool(test: pd.DataFrame, *, horizon: int, semester: str, root: Path=ORACLE_OUTPUT) -> tuple[pd.DataFrame, list[str]]`
- [_fit](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 111 : `def _fit(model_name: str, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, *, protocol: RankingProtocol, features: list[str], model_path: Path) -> np.ndarray`
- [_tails](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 145 : `def _tails(frame: pd.DataFrame, score: str, pct: float) -> tuple[pd.DataFrame, pd.DataFrame]`
- [ranking_metrics](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 154 : `def ranking_metrics(frame: pd.DataFrame, *, score: str, tail_pct: float) -> dict[str, Any]`
- [fold_metrics](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 182 : `def fold_metrics(frame: pd.DataFrame, protocol: RankingProtocol) -> dict[str, Any]`
- [run](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 213 : `def run(*, horizon: int, semester: str, model_name: str, config_path: Path=DEFAULT_CONFIG, output_root: Path=DEFAULT_OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_global_ranking_walk_forward.py) — ligne 281 : `def main() -> None`

## `modelFactory/cn_margin_calendar_15b6.py`

Source SHA-256 : `d90583873a4ae5eecf1ac07df2074b9ba87ae96151c21d165ab0fb09958f7168`

- [load_protocol](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 36 : `def load_protocol(path: Path=CONFIG) -> dict`
- [bounds](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 62 : `def bounds(semester: str) -> tuple[pd.Timestamp, pd.Timestamp]`
- [split_extension](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 70 : `def split_extension(frame: pd.DataFrame, semester: str, cap: int=600000)`
- [load_frame](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 111 : `def load_frame(sources: dict, label_audit: dict, end_year: int, features: list[str]) -> pd.DataFrame`
- [source_fingerprints](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 133 : `def source_fingerprints(sources: dict) -> dict`
- [directional_calendar](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 140 : `def directional_calendar(dates: list, semester: str) -> dict`
- [audit](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 158 : `def audit(config: Path=CONFIG, output: Path=OUTPUT) -> dict`
- [train_extension](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 200 : `def train_extension(semester: str, config: Path=CONFIG, output: Path=OUTPUT) -> dict`
- [main](../../modelFactory/cn_margin_calendar_15b6.py) — ligne 250 : `def main()`

## `modelFactory/cn_margin_directional_15b8.py`

Source SHA-256 : `c3d53533fc2722f781461217972f0e3b25e94521e76f9a1b8e1172ea2e8a8287`

- [locked_inputs](../../modelFactory/cn_margin_directional_15b8.py) — ligne 42 : `def locked_inputs(b5_root: Path, b6_root: Path, b7_root: Path) -> tuple[dict, dict, dict]`
- [load_history](../../modelFactory/cn_margin_directional_15b8.py) — ligne 66 : `def load_history(*, semester: str, lag: int, columns: list[str], roots: dict, inputs: dict) -> pd.DataFrame`
- [split_fold](../../modelFactory/cn_margin_directional_15b8.py) — ligne 92 : `def split_fold(frame: pd.DataFrame, *, task: str, semester: str, inputs: dict, calendar: dict) -> dict[str, pd.DataFrame]`
- [sample_train](../../modelFactory/cn_margin_directional_15b8.py) — ligne 122 : `def sample_train(train: pd.DataFrame, limit: int) -> pd.DataFrame`
- [make_model](../../modelFactory/cn_margin_directional_15b8.py) — ligne 129 : `def make_model(name: str, inputs: dict)`
- [finite_features](../../modelFactory/cn_margin_directional_15b8.py) — ligne 145 : `def finite_features(parts: dict[str, pd.DataFrame], columns: list[str]) -> None`
- [train_fold](../../modelFactory/cn_margin_directional_15b8.py) — ligne 155 : `def train_fold(*, task: str, semester: str, model_name: str, inputs: dict, calendar: dict, roots: dict, output: Path) -> dict`
- [date_weights](../../modelFactory/cn_margin_directional_15b8.py) — ligne 201 : `def date_weights(frame: pd.DataFrame) -> np.ndarray`
- [weighted_auc](../../modelFactory/cn_margin_directional_15b8.py) — ligne 207 : `def weighted_auc(frame: pd.DataFrame, score: str) -> float`
- [daily_top](../../modelFactory/cn_margin_directional_15b8.py) — ligne 214 : `def daily_top(frame: pd.DataFrame, score: str, pct: float) -> pd.DataFrame`
- [score_metrics](../../modelFactory/cn_margin_directional_15b8.py) — ligne 224 : `def score_metrics(frame: pd.DataFrame, variant: str, pct: float) -> dict`
- [bootstrap_delta_auc](../../modelFactory/cn_margin_directional_15b8.py) — ligne 231 : `def bootstrap_delta_auc(frame: pd.DataFrame, *, variant: str, reps: int, alpha_each: float, seed: int) -> dict`
- [aggregate](../../modelFactory/cn_margin_directional_15b8.py) — ligne 248 : `def aggregate(*, output: Path, inputs: dict) -> dict`
- [run](../../modelFactory/cn_margin_directional_15b8.py) — ligne 313 : `def run(*, output: Path=OUTPUT, b5_root: Path=B5_ROOT, b6_root: Path=B6_ROOT, b7_root: Path=B7_ROOT) -> dict`
- [main](../../modelFactory/cn_margin_directional_15b8.py) — ligne 343 : `def main() -> None`

## `modelFactory/cn_margin_features_15b5.py`

Source SHA-256 : `304a0f7836b477f1fbd7e9f057bec8f7748cc2e337425817cdf1989f18de5810`

- [rolling_row](../../modelFactory/cn_margin_features_15b5.py) — ligne 39 : `def rolling_row(row: dict, index: int, history: deque) -> dict`
- [strict_join](../../modelFactory/cn_margin_features_15b5.py) — ligne 67 : `def strict_join(events: pd.DataFrame, margins: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame`
- [oracle_pool](../../modelFactory/cn_margin_features_15b5.py) — ligne 87 : `def oracle_pool(frame: pd.DataFrame) -> pd.DataFrame`
- [join_price](../../modelFactory/cn_margin_features_15b5.py) — ligne 94 : `def join_price(events: pd.DataFrame, price: pd.DataFrame) -> pd.DataFrame`
- [attach_targets](../../modelFactory/cn_margin_features_15b5.py) — ligne 105 : `def attach_targets(frame: pd.DataFrame) -> None`
- [build_features](../../modelFactory/cn_margin_features_15b5.py) — ligne 112 : `def build_features(root: Path, output: Path, snapshot: dict, state: dict) -> dict`
- [run](../../modelFactory/cn_margin_features_15b5.py) — ligne 161 : `def run(root: Path=OUTPUT, output: Path=DEST) -> dict`
- [main](../../modelFactory/cn_margin_features_15b5.py) — ligne 284 : `def main()`

## `modelFactory/cn_margin_features_audit_15b5.py`

Source SHA-256 : `a148038933c572093c0265f45383a491fca1eebb8cdaebbb3073e7bdb29c2433`

- [run](../../modelFactory/cn_margin_features_audit_15b5.py) — ligne 15 : `def run(root: Path, dataset_root: Path=OUTPUT) -> dict`
- [main](../../modelFactory/cn_margin_features_audit_15b5.py) — ligne 96 : `def main()`

## `modelFactory/cn_margin_preflight_15b7.py`

Source SHA-256 : `0e8d9f5a6c0435dd6a4620cdc86bcc5937779f3853486fbc028376d75fd7b142`

- [historical_xshe_ids](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 36 : `def historical_xshe_ids(b5_root: Path, b4_root: Path=B4_ROOT) -> set[int]`
- [validated_sources](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 53 : `def validated_sources(b5_root: Path, b6_root: Path) -> tuple[dict, dict, dict]`
- [decision_calendar](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 102 : `def decision_calendar(sources: dict) -> dict[pd.Timestamp, pd.Timestamp]`
- [join_2021](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 118 : `def join_2021(semester: str, *, sources: dict, label_audit: dict, b5_root: Path, report: dict, output: Path) -> dict`
- [task_gate](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 183 : `def task_gate(frame: pd.DataFrame, *, task: str, semester: str, full_calendar: dict, cfg: dict) -> dict`
- [run](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 246 : `def run(*, b5_root: Path=B5_ROOT, b6_root: Path=B6_ROOT, output: Path=OUTPUT) -> dict`
- [main](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 308 : `def main()`
- [report_summary](../../modelFactory/cn_margin_preflight_15b7.py) — ligne 320 : `def report_summary(report: dict) -> dict`

## `modelFactory/cn_oracle_aggregate.py`

Source SHA-256 : `9da51d3bf86db77c9134b1718b8af10222f16fd482d02b148554989f490b8d27`

- [_find_run](../../modelFactory/cn_oracle_aggregate.py) — ligne 24 : `def _find_run(root: Path, *, horizon: int, semester: str, model: str, config_sha: str, code_sha: str, audit_sha: str) -> tuple[Path, dict[str, Any]] | None`
- [_monthly_bootstrap](../../modelFactory/cn_oracle_aggregate.py) — ligne 41 : `def _monthly_bootstrap(frame: pd.DataFrame, *, top_pct: float, repetitions: int, alpha: float, seed: int) -> dict[str, float | int]`
- [aggregate](../../modelFactory/cn_oracle_aggregate.py) — ligne 67 : `def aggregate(*, config_path: Path=DEFAULT_CONFIG, root: Path=DEFAULT_OUTPUT, require_complete: bool=False) -> dict[str, Any]`
- [main](../../modelFactory/cn_oracle_aggregate.py) — ligne 152 : `def main() -> None`

## `modelFactory/cn_oracle_labels.py`

Source SHA-256 : `0de94d64adc1d46d9b9e4efdbcab7bfc44d8a6115c3c839f788a1a5680f85b3a`

- [CNLabelPolicy](../../modelFactory/cn_oracle_labels.py) — ligne 40 : `class CNLabelPolicy`
- [CNLabelPolicy.from_yaml](../../modelFactory/cn_oracle_labels.py) — ligne 45 : `def from_yaml(cls, path: Path) -> CNLabelPolicy`
- [_interval_count](../../modelFactory/cn_oracle_labels.py) — ligne 71 : `def _interval_count(prefix: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray`
- [_mark_reason](../../modelFactory/cn_oracle_labels.py) — ligne 76 : `def _mark_reason(reasons: np.ndarray, condition: np.ndarray, label: str) -> None`
- [_symbol_labels](../../modelFactory/cn_oracle_labels.py) — ligne 80 : `def _symbol_labels(candidates: pd.DataFrame, bars: pd.DataFrame, calendar: pd.DataFrame, *, horizon: int) -> pd.DataFrame`
- [compute_horizon_labels](../../modelFactory/cn_oracle_labels.py) — ligne 211 : `def compute_horizon_labels(candidates: pd.DataFrame, bars: pd.DataFrame, calendar: pd.DataFrame, *, horizon: int, min_rank_cross_section: int=20) -> pd.DataFrame`
- [_resolve_feature_panel](../../modelFactory/cn_oracle_labels.py) — ligne 255 : `def _resolve_feature_panel(year: int, feature_root: Path) -> tuple[Path, dict[str, Any]]`
- [_load_data](../../modelFactory/cn_oracle_labels.py) — ligne 273 : `def _load_data(engine: Engine, *, start: date, end: date, candidate_ids: set[int]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_file_sha](../../modelFactory/cn_oracle_labels.py) — ligne 318 : `def _file_sha(path: Path) -> str`
- [build_year](../../modelFactory/cn_oracle_labels.py) — ligne 326 : `def build_year(*, year: int, config_path: Path=DEFAULT_CONFIG, feature_root: Path=DEFAULT_FEATURE_ROOT, output_root: Path=DEFAULT_OUTPUT_ROOT, start_date: date | None=None, end_date: date | None=None) -> dict[str, Any]`

## `modelFactory/cn_oracle_prospective_15d8.py`

Source SHA-256 : `04feb2e4e693aec0b1bf34e984852d39019f778cc6d33982ae73f63f193700dd`

- [_sha](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 38 : `def _sha(path: Path) -> str`
- [_path](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 46 : `def _path(value: str) -> Path`
- [load_contract](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 51 : `def load_contract(path: Path=DEFAULT_CONFIG) -> dict`
- [decision_window](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 92 : `def decision_window(decision_day: date, *, now: datetime, calendar: dict) -> dict`
- [_load_market](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 107 : `def _load_market(engine, *, previous: date, now: datetime, profile: CNFeatureProfile, policy: CNUniversePolicy) -> dict`
- [_preopen_members](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 174 : `def _preopen_members(inputs: dict, *, decision_day: date, previous: date, cutoff: datetime, policy: CNUniversePolicy) -> tuple[pd.DataFrame, dict]`
- [_known_factors_for_future](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 225 : `def _known_factors_for_future(factors: pd.DataFrame) -> tuple[pd.DataFrame, int]`
- [top20_candidates](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 239 : `def top20_candidates(panel: pd.DataFrame, scores: np.ndarray, *, top_pct: float, minimum_count: int, minimum_coverage: float) -> tuple[pd.DataFrame, dict]`
- [check](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 259 : `def check(*, decision_day: date, contract_path: Path=DEFAULT_CONFIG, now: datetime | None=None, engine=None) -> dict`
- [run](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 307 : `def run(*, decision_day: date, contract_path: Path=DEFAULT_CONFIG, now: datetime | None=None, engine=None, output_root: Path | None=None) -> dict`
- [main](../../modelFactory/cn_oracle_prospective_15d8.py) — ligne 420 : `def main() -> None`

## `modelFactory/cn_oracle_walk_forward.py`

Source SHA-256 : `8505ce143423620128e135f1cd013daae30303ea219b365d09ab7185d8010a31`

- [_sha](../../modelFactory/cn_oracle_walk_forward.py) — ligne 33 : `def _sha(path: Path) -> str`
- [Protocol](../../modelFactory/cn_oracle_walk_forward.py) — ligne 42 : `class Protocol`
- [Protocol.load](../../modelFactory/cn_oracle_walk_forward.py) — ligne 47 : `def load(cls, path: Path) -> Protocol`
- [_report_for_year](../../modelFactory/cn_oracle_walk_forward.py) — ligne 66 : `def _report_for_year(folder: Path, year: int, implementation_sha: str) -> tuple[Path, dict[str, Any]]`
- [_sources](../../modelFactory/cn_oracle_walk_forward.py) — ligne 77 : `def _sources(protocol: Protocol) -> tuple[dict[int, tuple[Path, Path]], dict[str, Any]]`
- [semester_bounds](../../modelFactory/cn_oracle_walk_forward.py) — ligne 99 : `def semester_bounds(name: str) -> tuple[pd.Timestamp, pd.Timestamp]`
- [_training_sample](../../modelFactory/cn_oracle_walk_forward.py) — ligne 109 : `def _training_sample(frame: pd.DataFrame, limit: int) -> pd.DataFrame`
- [split_fold](../../modelFactory/cn_oracle_walk_forward.py) — ligne 117 : `def split_fold(frame: pd.DataFrame, *, test_semester: str, validation_sessions: int, min_train_sessions: int, max_train_rows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- [_load_frame](../../modelFactory/cn_oracle_walk_forward.py) — ligne 148 : `def _load_frame(sources: dict[int, tuple[Path, Path]], *, horizon: int, features: list[str], semester: str, max_train_rows: int, validation_sessions: int) -> pd.DataFrame`
- [_matrix](../../modelFactory/cn_oracle_walk_forward.py) — ligne 184 : `def _matrix(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame`
- [_fit](../../modelFactory/cn_oracle_walk_forward.py) — ligne 189 : `def _fit(model_name: str, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, protocol: Protocol, model_path: Path) -> np.ndarray`
- [_top_rows](../../modelFactory/cn_oracle_walk_forward.py) — ligne 227 : `def _top_rows(frame: pd.DataFrame, score: str, top_pct: float) -> pd.DataFrame`
- [score_metrics](../../modelFactory/cn_oracle_walk_forward.py) — ligne 235 : `def score_metrics(frame: pd.DataFrame, *, score: str, top_pct: float) -> dict[str, Any]`
- [fold_metrics](../../modelFactory/cn_oracle_walk_forward.py) — ligne 255 : `def fold_metrics(frame: pd.DataFrame, protocol: Protocol) -> dict[str, Any]`
- [run](../../modelFactory/cn_oracle_walk_forward.py) — ligne 285 : `def run(*, config_path: Path=DEFAULT_CONFIG, output_root: Path=DEFAULT_OUTPUT, horizon: int, semester: str, model_name: str) -> dict[str, Any]`
- [main](../../modelFactory/cn_oracle_walk_forward.py) — ligne 344 : `def main() -> None`

## `modelFactory/cn_portfolio_replay.py`

Source SHA-256 : `315ec49eab7f8d4170aa32fcd808c621408cb42132a13f2095d25addd80884e1`

- [load_verified_action_evidence](../../modelFactory/cn_portfolio_replay.py) — ligne 35 : `def load_verified_action_evidence(path: Path) -> dict[int, dict[str, Any]]`
- [convert_verified_actions](../../modelFactory/cn_portfolio_replay.py) — ligne 53 : `def convert_verified_actions(action_rows: list[Any], evidence: dict[int, dict[str, Any]] | None) -> tuple[list[CNAction], set[tuple[date, int]]]`
- [_digest_rows](../../modelFactory/cn_portfolio_replay.py) — ligne 107 : `def _digest_rows(*groups: list[Any]) -> str`
- [_query_ids](../../modelFactory/cn_portfolio_replay.py) — ligne 117 : `def _query_ids(conn: Connection, sql: str, ids: list[int], **params: Any)`
- [load_inputs](../../modelFactory/cn_portfolio_replay.py) — ligne 122 : `def load_inputs(path: Path) -> tuple[dict[str, Any], list[CNIntent]]`
- [load_cn_market](../../modelFactory/cn_portfolio_replay.py) — ligne 149 : `def load_cn_market(conn: Connection, *, start: date, end: date, instrument_ids: list[int], evidence: dict[int, dict[str, Any]] | None=None) -> tuple[list[date], list[CNInstrument], list[CNBar], list[CNAction]]`
- [run](../../modelFactory/cn_portfolio_replay.py) — ligne 236 : `def run(*, intent_path: Path, output_dir: Path, scenario: str, cost_profile_key: str, initial_cash_cny: Decimal, allow_research_proxy: bool, pending_policy: str='carry', max_wait_sessions: int=3, max_positions: int=8, evidence_path: Path | None=None, auto_exit_after_full_sessions: int | None=None) -> dict[str, Any]`
- [main](../../modelFactory/cn_portfolio_replay.py) — ligne 341 : `def main() -> None`

## `modelFactory/cn_suspended_followthrough_13b2.py`

Source SHA-256 : `c8cacdd1cf8b448964286f9c66e8bfba4790d8d976a456e9cb66c968bffa1f2d`

- [run](../../modelFactory/cn_suspended_followthrough_13b2.py) — ligne 35 : `def run(*, evidence_path: Path=EVIDENCE, original: Path=ORIGINAL, output: Path=OUTPUT) -> dict`
- [main](../../modelFactory/cn_suspended_followthrough_13b2.py) — ligne 119 : `def main() -> None`

## `modelFactory/cn_veto_economic_replay.py`

Source SHA-256 : `df3cd063f6049e1eebf1e4fba403c47fe649ad81d344e792c75e7c2393be22f2`

- [load_protocol](../../modelFactory/cn_veto_economic_replay.py) — ligne 54 : `def load_protocol(path: Path) -> dict[str, Any]`
- [merge_labels](../../modelFactory/cn_veto_economic_replay.py) — ligne 88 : `def merge_labels(pool: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame`
- [classify_feasibility](../../modelFactory/cn_veto_economic_replay.py) — ligne 111 : `def classify_feasibility(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series`
- [proxy_returns](../../modelFactory/cn_veto_economic_replay.py) — ligne 138 : `def proxy_returns(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame`
- [policy_summary](../../modelFactory/cn_veto_economic_replay.py) — ligne 166 : `def policy_summary(frame: pd.DataFrame, mask: pd.Series, config: dict[str, Any]) -> dict[str, Any]`
- [_aggregate_metrics](../../modelFactory/cn_veto_economic_replay.py) — ligne 186 : `def _aggregate_metrics(parts: list[pd.DataFrame], config: dict[str, Any]) -> dict[str, Any]`
- [run](../../modelFactory/cn_veto_economic_replay.py) — ligne 197 : `def run(*, config_path: Path=DEFAULT_CONFIG, ranking_root: Path=RANKING_OUTPUT, output_root: Path=DEFAULT_OUTPUT) -> dict[str, Any]`
- [main](../../modelFactory/cn_veto_economic_replay.py) — ligne 281 : `def main() -> None`

## `modelFactory/conditional_oracle_ranker.py`

Source SHA-256 : `178f26734f874efbf390070b78d7e4ab54fdf8ccf47b7501aa9932ea4b9622a5`

- [ConditionalRankerConfig](../../modelFactory/conditional_oracle_ranker.py) — ligne 49 : `class ConditionalRankerConfig`
- [ConditionalRankerConfig.__post_init__](../../modelFactory/conditional_oracle_ranker.py) — ligne 67 : `def __post_init__(self) -> None`
- [attach_conditional_rank_target](../../modelFactory/conditional_oracle_ranker.py) — ligne 86 : `def attach_conditional_rank_target(oracle_pool: pd.DataFrame, forward_panel: pd.DataFrame, *, horizon: int) -> pd.DataFrame`
- [_fit_ranker](../../modelFactory/conditional_oracle_ranker.py) — ligne 103 : `def _fit_ranker(train: pd.DataFrame, valid: pd.DataFrame | None, features: list[str], categoricals: list[str], config: ConditionalRankerConfig, *, iterations: int | None=None) -> Any`
- [_tail](../../modelFactory/conditional_oracle_ranker.py) — ligne 156 : `def _tail(frame: pd.DataFrame, score: str, fraction: float, *, low: bool) -> pd.DataFrame`
- [_side_metrics](../../modelFactory/conditional_oracle_ranker.py) — ligne 167 : `def _side_metrics(selected: pd.DataFrame, *, side: str, up_threshold: float, down_threshold: float) -> dict[str, Any]`
- [_matched_expectation](../../modelFactory/conditional_oracle_ranker.py) — ligne 198 : `def _matched_expectation(frame: pd.DataFrame, fraction: float, *, side: str, up_threshold: float, down_threshold: float) -> dict[str, Any]`
- [_daily_ic_values](../../modelFactory/conditional_oracle_ranker.py) — ligne 227 : `def _daily_ic_values(frame: pd.DataFrame, score: str) -> np.ndarray`
- [_ndcg_at_fraction](../../modelFactory/conditional_oracle_ranker.py) — ligne 236 : `def _ndcg_at_fraction(frame: pd.DataFrame, score: str, fraction: float) -> float | None`
- [_selection_pair](../../modelFactory/conditional_oracle_ranker.py) — ligne 256 : `def _selection_pair(frame: pd.DataFrame, score: str, config: ConditionalRankerConfig) -> dict[str, Any]`
- [evaluate_ranker](../../modelFactory/conditional_oracle_ranker.py) — ligne 278 : `def evaluate_ranker(frame: pd.DataFrame, config: ConditionalRankerConfig) -> dict[str, Any]`
- [_load_global_rank_baseline](../../modelFactory/conditional_oracle_ranker.py) — ligne 382 : `def _load_global_rank_baseline(engine: Any, batch_id: str | None, horizon: int, start_date: str, end_date: str) -> pd.DataFrame`
- [_load_e2b_baseline](../../modelFactory/conditional_oracle_ranker.py) — ligne 411 : `def _load_e2b_baseline(artifact: Path | None) -> pd.DataFrame`
- [_merge_baselines](../../modelFactory/conditional_oracle_ranker.py) — ligne 439 : `def _merge_baselines(dataset: pd.DataFrame, global_rank: pd.DataFrame, e2b: pd.DataFrame) -> pd.DataFrame`
- [_fold_stability](../../modelFactory/conditional_oracle_ranker.py) — ligne 453 : `def _fold_stability(folds: list[dict[str, Any]]) -> dict[str, Any]`
- [_development_gates](../../modelFactory/conditional_oracle_ranker.py) — ligne 474 : `def _development_gates(overall: dict[str, Any], stability: dict[str, Any], fold_count: int) -> dict[str, Any]`
- [train_horizon](../../modelFactory/conditional_oracle_ranker.py) — ligne 521 : `def train_horizon(dataset: pd.DataFrame, features: list[str], categoricals: list[str], config: ConditionalRankerConfig, horizon: int, artifact_dir: Path) -> dict[str, Any]`
- [run_campaign](../../modelFactory/conditional_oracle_ranker.py) — ligne 620 : `def run_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, config: ConditionalRankerConfig, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, global_rank_batch_id: str | None=None, e2b_artifact: Path | None=None) -> tuple[Path, dict[str, Any]]`
- [_format_campaign](../../modelFactory/conditional_oracle_ranker.py) — ligne 735 : `def _format_campaign(path: Path, campaign: dict[str, Any]) -> str`
- [main](../../modelFactory/conditional_oracle_ranker.py) — ligne 751 : `def main() -> None`

## `modelFactory/config.py`

Source SHA-256 : `1b86275815950ad1269275163d404275c58bd126818b1adacb5f49ff2a2996f9`

- [DataConfig](../../modelFactory/config.py) — ligne 10 : `class DataConfig`
- [DataConfig.__post_init__](../../modelFactory/config.py) — ligne 96 : `def __post_init__(self) -> None`
- [CalibrationConfig](../../modelFactory/config.py) — ligne 148 : `class CalibrationConfig`
- [CalibrationConfig.__post_init__](../../modelFactory/config.py) — ligne 155 : `def __post_init__(self) -> None`
- [WalkForwardConfig](../../modelFactory/config.py) — ligne 165 : `class WalkForwardConfig`
- [WalkForwardConfig.__post_init__](../../modelFactory/config.py) — ligne 175 : `def __post_init__(self) -> None`
- [BaselineConfig](../../modelFactory/config.py) — ligne 189 : `class BaselineConfig`
- [BaselineConfig.__post_init__](../../modelFactory/config.py) — ligne 222 : `def __post_init__(self) -> None`
- [GlobalModelConfig](../../modelFactory/config.py) — ligne 270 : `class GlobalModelConfig`
- [GlobalModelConfig.__post_init__](../../modelFactory/config.py) — ligne 310 : `def __post_init__(self) -> None`
- [TargetOptimizationConfig](../../modelFactory/config.py) — ligne 322 : `class TargetOptimizationConfig`
- [TargetOptimizationConfig.__post_init__](../../modelFactory/config.py) — ligne 345 : `def __post_init__(self) -> None`
- [ThresholdOptimizationConfig](../../modelFactory/config.py) — ligne 377 : `class ThresholdOptimizationConfig`
- [ThresholdOptimizationConfig.__post_init__](../../modelFactory/config.py) — ligne 386 : `def __post_init__(self) -> None`
- [ChampionSelectionConfig](../../modelFactory/config.py) — ligne 402 : `class ChampionSelectionConfig`
- [ChampionSelectionConfig.__post_init__](../../modelFactory/config.py) — ligne 417 : `def __post_init__(self) -> None`
- [ModelConfig](../../modelFactory/config.py) — ligne 433 : `class ModelConfig`
- [ModelConfig.__post_init__](../../modelFactory/config.py) — ligne 453 : `def __post_init__(self) -> None`
- [ReproducibilityConfig](../../modelFactory/config.py) — ligne 481 : `class ReproducibilityConfig`
- [ReproducibilityConfig.__post_init__](../../modelFactory/config.py) — ligne 487 : `def __post_init__(self) -> None`
- [TrainingConfig](../../modelFactory/config.py) — ligne 493 : `class TrainingConfig`
- [TrainingConfig.__post_init__](../../modelFactory/config.py) — ligne 534 : `def __post_init__(self) -> None`

## `modelFactory/cross_sectional.py`

Source SHA-256 : `ee7e5892c06e8bc3cd9280931b592b1b3f021a625ab32bae128cc3ad2a13921d`

- [_sector_neutral_column_name](../../modelFactory/cross_sectional.py) — ligne 75 : `def _sector_neutral_column_name(source_col: str) -> str`
- [_sector_zscore_column_name](../../modelFactory/cross_sectional.py) — ligne 117 : `def _sector_zscore_column_name(source_col: str) -> str`
- [_compute_symbol_raw_values](../../modelFactory/cross_sectional.py) — ligne 151 : `def _compute_symbol_raw_values(sym_df: pd.DataFrame, benchmark_returns: pd.DataFrame | None) -> pd.DataFrame`
- [_build_benchmark_returns](../../modelFactory/cross_sectional.py) — ligne 203 : `def _build_benchmark_returns(benchmark_df: pd.DataFrame | None) -> pd.DataFrame`
- [_load_sector_mapping](../../modelFactory/cross_sectional.py) — ligne 220 : `def _load_sector_mapping(engine) -> dict[str, str]`
- [_map_to_gics_sector](../../modelFactory/cross_sectional.py) — ligne 321 : `def _map_to_gics_sector(db_sector: str) -> str`
- [load_sector_groups](../../modelFactory/cross_sectional.py) — ligne 330 : `def load_sector_groups(engine) -> dict[str, list[str]]`
- [_compute_sector_features](../../modelFactory/cross_sectional.py) — ligne 350 : `def _compute_sector_features(raw_panel: pd.DataFrame, sector_map: dict[str, str], *, min_symbols_per_sector: int=3) -> pd.DataFrame`
- [_compute_cross_symbol_features](../../modelFactory/cross_sectional.py) — ligne 459 : `def _compute_cross_symbol_features(raw_panel: pd.DataFrame, sector_map: dict[str, str], *, min_symbols_per_sector: int=5) -> pd.DataFrame`
- [_compute_sector_neutral_features](../../modelFactory/cross_sectional.py) — ligne 578 : `def _compute_sector_neutral_features(raw_panel: pd.DataFrame, sector_map: dict[str, str], *, min_symbols_per_sector: int=3) -> pd.DataFrame`
- [build_cross_sectional_features_from_db](../../modelFactory/cross_sectional.py) — ligne 634 : `def build_cross_sectional_features_from_db(engine, symbols: list[str], *, benchmark_df: pd.DataFrame | None=None, min_universe_size: int=20, start_date=None, end_date=None, sector_map: dict[str, str] | None=None, min_symbols_per_sector: int=3, feature_subset: list[str] | None=None) -> tuple[pd.DataFrame, dict[str, Any]]`
- [build_cross_sectional_features](../../modelFactory/cross_sectional.py) — ligne 792 : `def build_cross_sectional_features(universe_df: pd.DataFrame | None, *, benchmark_df: pd.DataFrame | None=None, min_universe_size: int=20, sector_map: dict[str, str] | None=None, min_symbols_per_sector: int=3, feature_subset: list[str] | None=None) -> tuple[pd.DataFrame, dict[str, Any]]`
- [merge_cross_sectional_features](../../modelFactory/cross_sectional.py) — ligne 889 : `def merge_cross_sectional_features(symbol_df: pd.DataFrame, cross_sectional_df: pd.DataFrame | None) -> pd.DataFrame`

## `modelFactory/data_loader.py`

Source SHA-256 : `57534a5c2496f2f5dc1d6679a9fdebc403091b13b929a882bc1f5e5e1a1fce1c`

- [_get_table_columns](../../modelFactory/data_loader.py) — ligne 52 : `def _get_table_columns(engine: Engine, table_name: str) -> set[str]`
- [_coerce_date_value](../../modelFactory/data_loader.py) — ligne 60 : `def _coerce_date_value(value: object) -> date | None`
- [_subtract_years](../../modelFactory/data_loader.py) — ligne 74 : `def _subtract_years(anchor_date: date, years: int) -> date`
- [resolve_training_start_date](../../modelFactory/data_loader.py) — ligne 81 : `def resolve_training_start_date(anchor_date: date | None, training_start_date: date | None=None, history_window_years: int | None=None) -> date | None`
- [resolve_history_window_start_date](../../modelFactory/data_loader.py) — ligne 93 : `def resolve_history_window_start_date(anchor_date: date | None, history_window_years: int | None) -> date | None`
- [_build_in_clause](../../modelFactory/data_loader.py) — ligne 98 : `def _build_in_clause(symbols: list[str]) -> tuple[str, dict[str, object]]`
- [load_symbol_latest_bar_date](../../modelFactory/data_loader.py) — ligne 108 : `def load_symbol_latest_bar_date(engine: Engine, symbol: str, end_date: date | None=None) -> date | None`
- [load_symbol_latest_bar_dates](../../modelFactory/data_loader.py) — ligne 122 : `def load_symbol_latest_bar_dates(engine: Engine, symbols: list[str], end_date: date | None=None) -> dict[str, date]`
- [load_universe_latest_bar_date](../../modelFactory/data_loader.py) — ligne 149 : `def load_universe_latest_bar_date(engine: Engine, symbols: list[str] | None=None, end_date: date | None=None) -> date | None`
- [load_available_trading_dates](../../modelFactory/data_loader.py) — ligne 172 : `def load_available_trading_dates(engine: Engine, symbols: list[str] | None=None, start_date: date | None=None, end_date: date | None=None) -> list[date]`
- [load_historical_prediction_scopes_from_scores_history](../../modelFactory/data_loader.py) — ligne 213 : `def load_historical_prediction_scopes_from_scores_history(engine: Engine, *, start_date: date, end_date: date, symbols: list[str] | None=None, signal_modes: tuple[str, ...] | list[str] | None=None, max_selection_rank: int | None=None, exclude_earnings_blackout: bool=False) -> dict[date, list[str]]`
- [load_symbol_bars](../../modelFactory/data_loader.py) — ligne 302 : `def load_symbol_bars(engine: Engine, symbol: str, end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [load_benchmark_bars](../../modelFactory/data_loader.py) — ligne 339 : `def load_benchmark_bars(engine: Engine, benchmark_symbol: str='SPY', end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [load_universe_bars](../../modelFactory/data_loader.py) — ligne 356 : `def load_universe_bars(engine: Engine, symbols: list[str] | None=None, end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [_load_universe_bars_chunk](../../modelFactory/data_loader.py) — ligne 390 : `def _load_universe_bars_chunk(engine: Engine, symbols: list[str] | None, end_date: date | None, start_date: date | None) -> pd.DataFrame`
- [load_symbol_sentiment](../../modelFactory/data_loader.py) — ligne 419 : `def load_symbol_sentiment(engine: Engine, symbol: str, end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [load_symbols_sentiment](../../modelFactory/data_loader.py) — ligne 458 : `def load_symbols_sentiment(engine: Engine, symbols: list[str], end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [load_symbols_selector_context](../../modelFactory/data_loader.py) — ligne 495 : `def load_symbols_selector_context(engine: Engine, symbols: list[str], end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`
- [load_symbol_selector_context](../../modelFactory/data_loader.py) — ligne 557 : `def load_symbol_selector_context(engine: Engine, symbol: str, end_date: date | None=None, start_date: date | None=None) -> pd.DataFrame`

## `modelFactory/dataset.py`

Source SHA-256 : `f8e6957f05c341075ef25ba03a8852daffcd045f079ebf7f3ad01f79567d0ce5`

- [ChronoSplit](../../modelFactory/dataset.py) — ligne 34 : `class ChronoSplit`
- [WalkForwardSplit](../../modelFactory/dataset.py) — ligne 42 : `class WalkForwardSplit`
- [_validate_ordered_frame](../../modelFactory/dataset.py) — ligne 51 : `def _validate_ordered_frame(df: pd.DataFrame, *, date_column: str | None=None) -> None`
- [_purged_bounds](../../modelFactory/dataset.py) — ligne 60 : `def _purged_bounds(*, start: int, end: int, purge_tail: int) -> tuple[int, int]`
- [_embargoed_start](../../modelFactory/dataset.py) — ligne 72 : `def _embargoed_start(*, val_end: int, embargo_rows: int) -> int`
- [_purge_by_dates](../../modelFactory/dataset.py) — ligne 83 : `def _purge_by_dates(df: pd.DataFrame, *, start_dates: pd.Index, purge_tail_dates: int, date_column: str='date') -> pd.DataFrame`
- [chrono_split](../../modelFactory/dataset.py) — ligne 98 : `def chrono_split(df: pd.DataFrame, train_ratio: float, val_ratio: float, *, forecast_horizon: int=0, embargo_rows: int=0, date_column: str | None='date') -> ChronoSplit`
- [generate_walk_forward_splits](../../modelFactory/dataset.py) — ligne 134 : `def generate_walk_forward_splits(df: pd.DataFrame, *, min_train_size: int, val_size: int, test_size: int, step_size: int, max_splits: int, forecast_horizon: int=0, embargo_rows: int=0, max_train_size: int=0, date_column: str | None='date') -> list[WalkForwardSplit]`
- [chrono_split_by_dates](../../modelFactory/dataset.py) — ligne 191 : `def chrono_split_by_dates(df: pd.DataFrame, *, train_ratio: float, val_ratio: float, forecast_horizon: int=0, embargo_dates: int=0, date_column: str='date') -> ChronoSplit`
- [generate_walk_forward_splits_by_dates](../../modelFactory/dataset.py) — ligne 224 : `def generate_walk_forward_splits_by_dates(df: pd.DataFrame, *, min_train_dates: int, val_dates: int, test_dates: int, step_dates: int, max_splits: int, forecast_horizon: int=0, embargo_dates: int=0, date_column: str='date') -> list[WalkForwardSplit]`
- [FoldIsolationReport](../../modelFactory/dataset.py) — ligne 300 : `class FoldIsolationReport`
- [validate_fold_isolation](../../modelFactory/dataset.py) — ligne 316 : `def validate_fold_isolation(split: ChronoSplit, *, label_horizon: int=0, embargo_rows: int=0, date_column: str | None='date') -> FoldIsolationReport`
- [FeatureScaler](../../modelFactory/dataset.py) — ligne 453 : `class FeatureScaler`
- [FeatureScaler.__init__](../../modelFactory/dataset.py) — ligne 456 : `def __init__(self, feature_names: list[str] | None=None) -> None`
- [FeatureScaler.fit](../../modelFactory/dataset.py) — ligne 461 : `def fit(self, df: pd.DataFrame) -> 'FeatureScaler'`
- [FeatureScaler.transform](../../modelFactory/dataset.py) — ligne 468 : `def transform(self, df: pd.DataFrame) -> np.ndarray`
- [FeatureScaler.state_dict](../../modelFactory/dataset.py) — ligne 473 : `def state_dict(self) -> dict`
- [FeatureScaler.from_state_dict](../../modelFactory/dataset.py) — ligne 482 : `def from_state_dict(cls, d: dict) -> 'FeatureScaler'`
- [build_sequences](../../modelFactory/dataset.py) — ligne 506 : `def build_sequences(features: np.ndarray, targets: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]`
- [build_sequence_dataset](../../modelFactory/dataset.py) — ligne 531 : `def build_sequence_dataset(df: pd.DataFrame, scaler: FeatureScaler, seq_len: int, *, is_regression: bool=False) -> SequenceDataset | None`
- [SequenceDataset](../../modelFactory/dataset.py) — ligne 546 : `class SequenceDataset(Dataset)`
- [SequenceDataset.__init__](../../modelFactory/dataset.py) — ligne 547 : `def __init__(self, X: np.ndarray, y: np.ndarray, *, is_regression: bool=False) -> None`
- [SequenceDataset.__len__](../../modelFactory/dataset.py) — ligne 552 : `def __len__(self) -> int`
- [SequenceDataset.__getitem__](../../modelFactory/dataset.py) — ligne 555 : `def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]`
- [SymbolDataModule](../../modelFactory/dataset.py) — ligne 569 : `class SymbolDataModule(L.LightningDataModule)`
- [SymbolDataModule.__init__](../../modelFactory/dataset.py) — ligne 572 : `def __init__(self, bars_df: pd.DataFrame, data_cfg: DataConfig, model_cfg: ModelConfig, sentiment_df: pd.DataFrame | None=None, benchmark_df: pd.DataFrame | None=None, universe_df: pd.DataFrame | None=None, selector_df: pd.DataFrame | None=None, reproducibility_seed: int=42, *, cross_sectional_df: pd.DataFrame | None=None, include_global_stacking: bool=False, fundamental_df: pd.DataFrame | None=None, oracle_gate_df: pd.DataFrame | None=None) -> None`
- [SymbolDataModule.setup](../../modelFactory/dataset.py) — ligne 649 : `def setup(self, stage: Optional[str]=None) -> None`
- [SymbolDataModule.train_dataloader](../../modelFactory/dataset.py) — ligne 707 : `def train_dataloader(self) -> DataLoader`
- [SymbolDataModule.val_dataloader](../../modelFactory/dataset.py) — ligne 711 : `def val_dataloader(self) -> DataLoader`
- [SymbolDataModule.test_dataloader](../../modelFactory/dataset.py) — ligne 715 : `def test_dataloader(self) -> DataLoader`
- [SymbolDataModule._build_dataloader](../../modelFactory/dataset.py) — ligne 719 : `def _build_dataloader(self, dataset: SequenceDataset, *, shuffle: bool) -> DataLoader`
- [prepare_symbol_frame](../../modelFactory/dataset.py) — ligne 740 : `def prepare_symbol_frame(bars_df: pd.DataFrame, data_cfg: DataConfig, sentiment_df: pd.DataFrame | None=None, benchmark_df: pd.DataFrame | None=None, universe_df: pd.DataFrame | None=None, selector_df: pd.DataFrame | None=None, *, cross_sectional_df: pd.DataFrame | None=None, include_global_stacking: bool=False, fundamental_df: pd.DataFrame | None=None, oracle_gate_df: pd.DataFrame | None=None) -> pd.DataFrame`

## `modelFactory/db_registry.py`

Source SHA-256 : `3ccb49c5631829a2fe09062e616b8518bdc5a77fb208358323a95dc3c0940133`

- [_write_batch_delete_audit](../../modelFactory/db_registry.py) — ligne 28 : `def _write_batch_delete_audit(event: str, batch_id: str, reason: str, source: str) -> None`
- [audit_batch_delete](../../modelFactory/db_registry.py) — ligne 51 : `def audit_batch_delete(batch_id: str, source: str) -> None`
- [audit_batch_delete_attempt](../../modelFactory/db_registry.py) — ligne 56 : `def audit_batch_delete_attempt(batch_id: str, reason: str, source: str='') -> None`
- [_source_priority](../../modelFactory/db_registry.py) — ligne 111 : `def _source_priority(source: str | None) -> int`
- [_required_text](../../modelFactory/db_registry.py) — ligne 118 : `def _required_text(value: Any, *, field_name: str) -> str`
- [_required_finite_float](../../modelFactory/db_registry.py) — ligne 125 : `def _required_finite_float(value: Any, *, field_name: str) -> float`
- [_validate_predictions_frame](../../modelFactory/db_registry.py) — ligne 135 : `def _validate_predictions_frame(predictions: pd.DataFrame) -> None`
- [_normalize_symbols](../../modelFactory/db_registry.py) — ligne 141 : `def _normalize_symbols(symbols: list[str]) -> list[str]`
- [_normalize_signal_modes](../../modelFactory/db_registry.py) — ligne 153 : `def _normalize_signal_modes(signal_modes: tuple[str, ...] | list[str] | None) -> tuple[str, ...]`
- [_load_distinct_symbols](../../modelFactory/db_registry.py) — ligne 165 : `def _load_distinct_symbols(engine: Engine, query: str) -> list[str]`
- [has_score_context_filter](../../modelFactory/db_registry.py) — ligne 171 : `def has_score_context_filter(*, signal_modes: tuple[str, ...] | list[str] | None=None, max_selection_rank: int | None=None, exclude_earnings_blackout: bool=False) -> bool`
- [filter_symbols_by_score_context](../../modelFactory/db_registry.py) — ligne 180 : `def filter_symbols_by_score_context(engine: Engine, symbols: list[str], *, signal_modes: tuple[str, ...] | list[str] | None=None, max_selection_rank: int | None=None, exclude_earnings_blackout: bool=False) -> tuple[list[str], dict[str, Any]]`
- [_optional_float](../../modelFactory/db_registry.py) — ligne 285 : `def _optional_float(value: Any) -> float | None`
- [_optional_int](../../modelFactory/db_registry.py) — ligne 295 : `def _optional_int(value: Any) -> int | None`
- [build_governance_rows](../../modelFactory/db_registry.py) — ligne 304 : `def build_governance_rows(*, run_id: str, symbol: str, challengers: dict[str, Any], artifact_routes_models: dict[str, Any], selected_model: str, selection_mode: str, selection_metric: str, ranking: list[dict[str, Any]] | None=None) -> list[dict[str, Any]]`
- [_resolve_batch_market_code](../../modelFactory/db_registry.py) — ligne 376 : `def _resolve_batch_market_code(engine: Engine, batch_id: str | None, market_code: str | None) -> str`
- [ensure_registry_entry](../../modelFactory/db_registry.py) — ligne 396 : `def ensure_registry_entry(engine: Engine, symbol: str, architecture: str='lstm_attention', *, batch_id: str | None=None, market_code: str | None=None) -> int`
- [insert_training_batch](../../modelFactory/db_registry.py) — ligne 452 : `def insert_training_batch(engine: Engine, *, batch_id: str, command_line: str, command_argv_json: str, metadata_json: str, symbol_source: str, universe_date: date | None, requested_symbol_count: int | None, training_start_date: date | None, training_end_date: date | None, started_at: datetime, comment: str | None=None, stacking_enabled: bool=False, symbols: str | None=None, market_code: str | None=None, universe_id: str | None=None, universe_fingerprint: str | None=None) -> None`
- [update_training_batch](../../modelFactory/db_registry.py) — ligne 514 : `def update_training_batch(engine: Engine, batch_id: str, **kwargs: Any) -> None`
- [insert_training_run](../../modelFactory/db_registry.py) — ligne 526 : `def insert_training_run(engine: Engine, run_id: str, registry_id: int, symbol: str, status: str='pending', train_start_date: date | None=None, train_end_date: date | None=None, batch_id: str | None=None, model_role: str | None=None, market_code: str | None=None) -> None`
- [update_training_run](../../modelFactory/db_registry.py) — ligne 553 : `def update_training_run(engine: Engine, run_id: str, **kwargs: Any) -> None`
- [_delete_predictions_chunked](../../modelFactory/db_registry.py) — ligne 562 : `def _delete_predictions_chunked(conn: Any, run_ids: list[str], chunk_size: int) -> int`
- [delete_batch_rows](../../modelFactory/db_registry.py) — ligne 591 : `def delete_batch_rows(engine: Engine, batch_id: str, *, lock_wait_timeout: int=60, chunk_size: int=10000, retries: int=5) -> dict[str, int]`
- [load_training_run](../../modelFactory/db_registry.py) — ligne 730 : `def load_training_run(engine: Engine, symbol: str, run_id: str | None=None, batch_id: str | None=None) -> dict[str, Any] | None`
- [insert_metrics](../../modelFactory/db_registry.py) — ligne 774 : `def insert_metrics(engine: Engine, run_id: str, symbol: str, split_name: str, metrics: dict[str, float], *, model_name: str='lstm_attention', horizon: int | None=None) -> None`
- [count_completed_runs](../../modelFactory/db_registry.py) — ligne 816 : `def count_completed_runs(engine: Engine, symbol: str, model_name: str) -> tuple[int, datetime | None]`
- [upsert_metrics_full](../../modelFactory/db_registry.py) — ligne 849 : `def upsert_metrics_full(engine: Engine, *, run_id: str, symbol: str, metrics: dict[str, Any]) -> None`
- [upsert_directional_oos_metrics](../../modelFactory/db_registry.py) — ligne 880 : `def upsert_directional_oos_metrics(engine: Engine, *, run_id: str, symbol: str, as_of_date: date, metrics_by_split: dict[str, dict[str, dict[str, float | int | None]]], policy_version: int=1) -> None`
- [replace_model_governance](../../modelFactory/db_registry.py) — ligne 939 : `def replace_model_governance(engine: Engine, *, run_id: str, symbol: str, challengers: dict[str, Any], artifact_routes_models: dict[str, Any], selected_model: str, selection_mode: str, selection_metric: str, ranking: list[dict[str, Any]] | None=None) -> int`
- [insert_predictions](../../modelFactory/db_registry.py) — ligne 992 : `def insert_predictions(engine: Engine, predictions: pd.DataFrame) -> int`
- [load_score_symbols](../../modelFactory/db_registry.py) — ligne 1106 : `def load_score_symbols(engine: Engine) -> list[str]`
- [load_score_context](../../modelFactory/db_registry.py) — ligne 1113 : `def load_score_context(engine: Engine, *, limit: int | None=None) -> pd.DataFrame`
- [load_stock_scores_symbols](../../modelFactory/db_registry.py) — ligne 1120 : `def load_stock_scores_symbols(engine: Engine) -> list[str]`
- [load_stock_scores_history_symbols](../../modelFactory/db_registry.py) — ligne 1135 : `def load_stock_scores_history_symbols(engine: Engine) -> list[str]`
- [load_stock_scores_all_symbols](../../modelFactory/db_registry.py) — ligne 1150 : `def load_stock_scores_all_symbols(engine: Engine) -> list[str]`
- [_load_ticket_recherche_symbols](../../modelFactory/db_registry.py) — ligne 1169 : `def _load_ticket_recherche_symbols() -> list[str]`
- [detect_batch_training_mode](../../modelFactory/db_registry.py) — ligne 1181 : `def detect_batch_training_mode(engine: Engine, batch_id: str | None) -> str`
- [get_serving_batch](../../modelFactory/db_registry.py) — ligne 1272 : `def get_serving_batch(engine: Engine, *, market_code: str | None=None) -> str | None`
- [set_serving_batch](../../modelFactory/db_registry.py) — ligne 1302 : `def set_serving_batch(engine: Engine, *, batch_id: str, market_code: str | None=None) -> None`
- [load_symbols_for_source](../../modelFactory/db_registry.py) — ligne 1321 : `def load_symbols_for_source(engine: Engine, symbol_source: str, *, trade_date: date | None=None, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY) -> list[str]`
- [load_tradable_universe_symbols](../../modelFactory/db_registry.py) — ligne 1348 : `def load_tradable_universe_symbols(engine: Engine, *, trade_date: date, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY) -> list[str]`
- [load_stock_bars_daily_symbols](../../modelFactory/db_registry.py) — ligne 1371 : `def load_stock_bars_daily_symbols(engine: Engine) -> list[str]`

## `modelFactory/dense_screener_panel.py`

Source SHA-256 : `1635135fcf0d93b58fe4e780e698301b58338334c78d399f53374922704aaf97`

- [load_oracle_population](../../modelFactory/dense_screener_panel.py) — ligne 27 : `def load_oracle_population(gate_path: Path, *, start_date: str | None=None, end_date: str | None=None, pool_pct: float=0.2) -> pd.DataFrame`
- [load_bars](../../modelFactory/dense_screener_panel.py) — ligne 57 : `def load_bars(engine: Any, symbols: list[str], *, start_date: pd.Timestamp, end_date: pd.Timestamp, lookback_calendar_days: int=800, chunk_size: int=500) -> pd.DataFrame`
- [_calendar_window_return](../../modelFactory/dense_screener_panel.py) — ligne 80 : `def _calendar_window_return(dates: pd.Series, closes: pd.Series, days: int) -> np.ndarray`
- [_daily_percentile](../../modelFactory/dense_screener_panel.py) — ligne 92 : `def _daily_percentile(frame: pd.DataFrame, column: str, mask: pd.Series | None=None) -> pd.Series`
- [compute_dense_panel](../../modelFactory/dense_screener_panel.py) — ligne 101 : `def compute_dense_panel(oracle_population: pd.DataFrame, bars: pd.DataFrame, config: ScreenerConfig | None=None) -> pd.DataFrame`
- [build_quality_report](../../modelFactory/dense_screener_panel.py) — ligne 211 : `def build_quality_report(panel: pd.DataFrame) -> pd.DataFrame`
- [write_artifacts](../../modelFactory/dense_screener_panel.py) — ligne 223 : `def write_artifacts(panel: pd.DataFrame, *, output_dir: Path, batch_id: str, config: ScreenerConfig, pool_pct: float) -> None`
- [parse_args](../../modelFactory/dense_screener_panel.py) — ligne 254 : `def parse_args() -> argparse.Namespace`
- [main](../../modelFactory/dense_screener_panel.py) — ligne 267 : `def main() -> int`

## `modelFactory/dip_research/__init__.py`

Source SHA-256 : `335c95b015670137aa29311f92c28a2ce15e5f0f79f932c3e470d7230aa5e353`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/dip_research/dip_context_pattern_analysis.py`

Source SHA-256 : `b365d66d8aef52f3cd0686985cb4f627032c115df574825d4e78710e1e1ee8ae`

- [_quiet](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 53 : `def _quiet() -> None`
- [_plog](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 60 : `def _plog(msg: str) -> None`
- [build_dip_events](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 67 : `def build_dip_events(engine: Any) -> pd.DataFrame`
- [assert_events](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 124 : `def assert_events(events: pd.DataFrame) -> None`
- [_reg](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 151 : `def _reg(feature: str, family: str, source: str) -> None`
- [_ema](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 155 : `def _ema(s: pd.Series, span: int) -> pd.Series`
- [_compute_bars_features](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 159 : `def _compute_bars_features(bars: pd.DataFrame) -> pd.DataFrame`
- [_compute_beta126](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 217 : `def _compute_beta126(dip_bars: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame`
- [_compute_market_features](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 259 : `def _compute_market_features(engine: Any) -> pd.DataFrame`
- [_load_universe_bars](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 298 : `def _load_universe_bars(engine: Any, top_n: int=3000, bars_start: str=_BARS_START, bars_end: str=_BARS_END) -> pd.DataFrame`
- [_compute_breadth_ranks](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 320 : `def _compute_breadth_ranks(engine: Any, top_n: int=3000, bars_start: str=_BARS_START, bars_end: str=_BARS_END)`
- [_compute_sector_features](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 353 : `def _compute_sector_features(engine: Any, uni: pd.DataFrame)`
- [build_features](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 378 : `def build_features(engine: Any, events: pd.DataFrame, *, smoke: bool=False) -> pd.DataFrame`
- [_register_meta](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 545 : `def _register_meta() -> None`
- [_load_panel](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 618 : `def _load_panel()`
- [_feature_set](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 627 : `def _feature_set(df: pd.DataFrame, fam: dict[str, str]) -> list[str]`
- [_auc_rank](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 643 : `def _auc_rank(y: np.ndarray, score: np.ndarray) -> float`
- [_group_stats](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 654 : `def _group_stats(s1: pd.Series, s2: pd.Series) -> dict`
- [_run_analyses](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 674 : `def _run_analyses(smoke: bool=False) -> None`
- [_build_report](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 993 : `def _build_report(master, wl, ex, q12, ctx, null_max, q_df, feats, n_events=None, control_path=None) -> None`
- [_prod_universe](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 1075 : `def _prod_universe(engine) -> pd.DataFrame`
- [_auc_for](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 1092 : `def _auc_for(y: np.ndarray, score: np.ndarray) -> float`
- [_run_deltas](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 1096 : `def _run_deltas(engine, smoke: bool=False) -> None`
- [main](../../modelFactory/dip_research/dip_context_pattern_analysis.py) — ligne 1327 : `def main() -> None`

## `modelFactory/dip_research/dip_quality_static_model.py`

Source SHA-256 : `a8589c54acdd438b4d0967ddd44ae2c333e9d8efc36009df458abe150ee6f657`

- [_greedy_compact](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 85 : `def _greedy_compact(main: pd.DataFrame) -> list[str]`
- [run_dataset](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 108 : `def run_dataset(engine: Any, *, smoke: bool=False) -> None`
- [_load_dataset](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 164 : `def _load_dataset() -> pd.DataFrame`
- [_run_lr_wf](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 170 : `def _run_lr_wf(df: pd.DataFrame, feats: list[str], y_al: np.ndarray, folds, lgb: bool=False, min_train: int=MIN_TRAIN)`
- [_fit_lgb_early](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 205 : `def _fit_lgb_early(X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray) -> np.ndarray`
- [_pr_auc](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 220 : `def _pr_auc(y: np.ndarray, score: np.ndarray) -> float`
- [run_models](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 227 : `def run_models(*, smoke: bool=False) -> None`
- [_sector_map](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 391 : `def _sector_map(engine) -> dict[str, str]`
- [_select_per_day](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 399 : `def _select_per_day(cands: pd.DataFrame, order_col: str, top_pct: float | None, sector_cap: int, max_positions: int) -> pd.DataFrame`
- [run_portfolio](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 428 : `def run_portfolio(engine: Any, *, smoke: bool=False) -> None`
- [run_report](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 566 : `def run_report() -> None`
- [_quintile_mono](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 720 : `def _quintile_mono(quint: pd.DataFrame) -> bool`
- [_q](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 728 : `def _q(quint: pd.DataFrame, qi: int)`
- [main](../../modelFactory/dip_research/dip_quality_static_model.py) — ligne 739 : `def main() -> None`

## `modelFactory/dip_research/dip_temporal_pattern_feasibility.py`

Source SHA-256 : `6629748292e71e8fc9c9db910383312ef233994fa59b936da36bad8af03032de`

- [_quiet](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 115 : `def _quiet() -> None`
- [_plog](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 122 : `def _plog(msg: str) -> None`
- [run_events](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 132 : `def run_events(engine: Any, *, smoke: bool=False) -> None`
- [_load_market_features](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 143 : `def _load_market_features(engine: Any, bs: str, be: str, uni_start: str, top_n: int) -> pd.DataFrame`
- [build_daily_panel](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 160 : `def build_daily_panel(engine: Any, symbols: list[str], *, smoke: bool=False) -> pd.DataFrame`
- [_shape_metrics](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 228 : `def _shape_metrics(x: np.ndarray) -> dict[str, float]`
- [run_panel](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 251 : `def run_panel(engine: Any, *, smoke: bool=False) -> None`
- [_load_temporal](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 315 : `def _load_temporal(engine: Any) -> pd.DataFrame`
- [_prod_universe](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 322 : `def _prod_universe(engine: Any, df: pd.DataFrame) -> pd.DataFrame`
- [_select_features](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 339 : `def _select_features(df: pd.DataFrame) -> list[str]`
- [run_coverage](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 368 : `def run_coverage(engine: Any, *, smoke: bool=False) -> list[str]`
- [_build_reps](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 436 : `def _build_reps(seq: pd.DataFrame, feats: list[str]) -> dict[str, pd.DataFrame]`
- [_chrono_folds](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 465 : `def _chrono_folds(dates: np.ndarray, n_folds: int=N_FOLDS, purge_days: int=PURGE_DAYS, min_train: int=MIN_TRAIN)`
- [_fit_predict](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 494 : `def _fit_predict(rep_train: pd.DataFrame, rep_val: pd.DataFrame, y_tr: np.ndarray, model: str='lr', rng: np.random.Generator | None=None) -> np.ndarray`
- [_fold_metrics](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 521 : `def _fold_metrics(y_val: np.ndarray, score: np.ndarray, fwd_val: np.ndarray) -> dict[str, float]`
- [_summarize](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 535 : `def _summarize(aucs: list[float]) -> dict[str, float]`
- [run_models](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 546 : `def run_models(engine: Any, *, smoke: bool=False) -> None`
- [_pr_auc_score](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 850 : `def _pr_auc_score(y: np.ndarray, score: np.ndarray) -> float`
- [run_report](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 861 : `def run_report() -> None`
- [_quintile_monotonicity](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 986 : `def _quintile_monotonicity(quint: pd.DataFrame) -> str`
- [main](../../modelFactory/dip_research/dip_temporal_pattern_feasibility.py) — ligne 1002 : `def main() -> None`

## `modelFactory/dip_research/persistent_tail_price.py`

Source SHA-256 : `b677f43887fc7565d21abc4d304aaa1ea42b4ca916cd36c6d4b41e7dbbdb4a3b`

- [load_panel](../../modelFactory/dip_research/persistent_tail_price.py) — ligne 57 : `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [compute_persistence](../../modelFactory/dip_research/persistent_tail_price.py) — ligne 97 : `def compute_persistence(df: pd.DataFrame) -> pd.DataFrame`
- [evaluate](../../modelFactory/dip_research/persistent_tail_price.py) — ligne 119 : `def evaluate(panel: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/dip_research/persistent_tail_price.py) — ligne 199 : `def main() -> None`

## `modelFactory/dip_research/persistent_top10_dip.py`

Source SHA-256 : `4531a93b5d3bdd796ae387e8d1c2efe665a8ae29717309f76e6a91802cb09f53`

- [load_panel](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 55 : `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [_per_symbol_paths](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 88 : `def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]`
- [forward_path_metrics](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 101 : `def forward_path_metrics(sym: str, j: pd.Timestamp, paths: dict[str, dict[str, np.ndarray]]) -> dict[str, float | None]`
- [build_signal_rows](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 133 : `def build_signal_rows(panel: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> list[pd.DataFrame]`
- [_meta](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 195 : `def _meta(r: pd.Series) -> dict[str, Any]`
- [aggregate](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 205 : `def aggregate(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame`
- [breakdown](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 246 : `def breakdown(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame`
- [main](../../modelFactory/dip_research/persistent_top10_dip.py) — ligne 262 : `def main() -> None`

## `modelFactory/dip_research/persistent_top10_dip_parity.py`

Source SHA-256 : `4c2a7080e5aa69c0baf38c01cb538ee90d7d613cd7133ea9942867c5000c7aa8`

- [build_signals_parity](../../modelFactory/dip_research/persistent_top10_dip_parity.py) — ligne 61 : `def build_signals_parity(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [_schedule_local](../../modelFactory/dip_research/persistent_top10_dip_parity.py) — ligne 117 : `def _schedule_local(signals: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame`
- [capacity_attribution](../../modelFactory/dip_research/persistent_top10_dip_parity.py) — ligne 133 : `def capacity_attribution(signals: pd.DataFrame, result: Any, trading_days: pd.DatetimeIndex, max_positions: int=20) -> dict[str, float]`
- [main](../../modelFactory/dip_research/persistent_top10_dip_parity.py) — ligne 230 : `def main() -> None`

## `modelFactory/dip_research/persistent_top10_dip_portfolio.py`

Source SHA-256 : `915be3ae83e75c71769c68598149294ad84793aa94b65967acff1f99373857c7`

- [_load_regime_map](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 66 : `def _load_regime_map() -> dict[pd.Timestamp, str]`
- [load_regime_map_db](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 91 : `def load_regime_map_db(engine: Any) -> dict[pd.Timestamp, str]`
- [build_signals](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 122 : `def build_signals(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [_pivot](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 185 : `def _pivot(bars: pd.DataFrame, col: str) -> pd.DataFrame`
- [load_ohlcv_pivots](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 189 : `def load_ohlcv_pivots(engine: Any, start_date: str, end_date: str, symbols: list[str]) -> dict[str, pd.DataFrame]`
- [build_config](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 202 : `def build_config(start_date: str, end_date: str) -> BacktestConfig`
- [_enrich_atr](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 244 : `def _enrich_atr(signals: pd.DataFrame, pivots: dict[str, pd.DataFrame]) -> pd.DataFrame`
- [run_variant](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 265 : `def run_variant(engine: Any, signals: pd.DataFrame, pivots: dict[str, pd.DataFrame], start_date: str, end_date: str, name: str) -> dict[str, Any]`
- [_metrics](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 277 : `def _metrics(res: Any, raw_signals: pd.DataFrame, reg_map: dict[pd.Timestamp, str], variant: str) -> dict[str, Any]`
- [main](../../modelFactory/dip_research/persistent_top10_dip_portfolio.py) — ligne 352 : `def main() -> None`

## `modelFactory/dip_research/persistent_top10_dip_reclaim.py`

Source SHA-256 : `7fbfa067105ba13fbb06abda679f3c949b1f6b3e3570e6eec7018802aa9c24e7`

- [load_panel](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 69 : `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [_per_symbol_paths](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 102 : `def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]`
- [_build_rank_index](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 115 : `def _build_rank_index(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], float]`
- [_find_reclaim](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 127 : `def _find_reclaim(sym: str, j: pd.Timestamp, start_price: float, dip_price: float, pct: float, paths: dict[str, dict[str, np.ndarray]], rank_index: dict[tuple[str, pd.Timestamp], float]) -> tuple[pd.Timestamp | None, float | None, int | None]`
- [forward_metrics_from_entry](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 157 : `def forward_metrics_from_entry(sym: str, entry_date: pd.Timestamp, paths: dict[str, dict[str, np.ndarray]]) -> dict[str, float | None]`
- [build_reclaim_rows](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 185 : `def build_reclaim_rows(panel: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]], rank_index: dict[tuple[str, pd.Timestamp], float]) -> pd.DataFrame`
- [signal_diagnostics](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 243 : `def signal_diagnostics(signals: pd.DataFrame) -> dict[str, Any]`
- [metrics_per_strategy](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 268 : `def metrics_per_strategy(signals: pd.DataFrame) -> pd.DataFrame`
- [cost_of_delay](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 299 : `def cost_of_delay(signals: pd.DataFrame) -> pd.DataFrame`
- [build_signals_for_backtest](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 316 : `def build_signals_for_backtest(signals: pd.DataFrame, name: str, reg_map: dict[pd.Timestamp, str]) -> pd.DataFrame`
- [main](../../modelFactory/dip_research/persistent_top10_dip_reclaim.py) — ligne 338 : `def main() -> None`

## `modelFactory/directional_alpha_attribution.py`

Source SHA-256 : `ba07b7ae8f3054f0a3874919c20c67147907f9d7d11ed9a392fc9df03c9a0eb3`

- [load_locked_protocol](../../modelFactory/directional_alpha_attribution.py) — ligne 26 : `def load_locked_protocol(path: Path=DEFAULT_PROTOCOL) -> dict[str, Any]`
- [build_ex_ante_context](../../modelFactory/directional_alpha_attribution.py) — ligne 42 : `def build_ex_ante_context(bars: pd.DataFrame, benchmark: pd.DataFrame, protocol: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_sector_neutral_leg](../../modelFactory/directional_alpha_attribution.py) — ligne 108 : `def _sector_neutral_leg(group: pd.DataFrame, protocol: dict[str, Any]) -> tuple[float, float, float, int] | None`
- [build_attribution_cohorts](../../modelFactory/directional_alpha_attribution.py) — ligne 135 : `def build_attribution_cohorts(frame: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame`
- [_bootstrap_ci](../../modelFactory/directional_alpha_attribution.py) — ligne 208 : `def _bootstrap_ci(values: pd.Series, protocol: dict[str, Any], *, seed_offset: int=0) -> tuple[float, float]`
- [summarize](../../modelFactory/directional_alpha_attribution.py) — ligne 227 : `def summarize(cohorts: pd.DataFrame, protocol: dict[str, Any], *, seed: int=0) -> dict[str, Any]`
- [classify_attribution](../../modelFactory/directional_alpha_attribution.py) — ligne 250 : `def classify_attribution(cohorts: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]`
- [run](../../modelFactory/directional_alpha_attribution.py) — ligne 321 : `def run(*, protocol_path: Path, output_root: Path) -> Path`
- [main](../../modelFactory/directional_alpha_attribution.py) — ligne 379 : `def main() -> None`

## `modelFactory/directional_alpha_book.py`

Source SHA-256 : `66eafb091b09f17ae13ebba65d57311579743d27a5099527e07c5190d9b1ce5b`

- [E17Config](../../modelFactory/directional_alpha_book.py) — ligne 48 : `class E17Config`
- [E17Config.__post_init__](../../modelFactory/directional_alpha_book.py) — ligne 67 : `def __post_init__(self) -> None`
- [E17Config.round_trip_cost](../../modelFactory/directional_alpha_book.py) — ligne 76 : `def round_trip_cost(self) -> float`
- [load_sector_reference](../../modelFactory/directional_alpha_book.py) — ligne 80 : `def load_sector_reference(engine: Engine, symbols: list[str]) -> pd.DataFrame`
- [_rolling_beta](../../modelFactory/directional_alpha_book.py) — ligne 101 : `def _rolling_beta(group: pd.DataFrame) -> pd.Series`
- [build_price_alpha_panel](../../modelFactory/directional_alpha_book.py) — ligne 107 : `def build_price_alpha_panel(bars: pd.DataFrame, benchmark: pd.DataFrame, instruments: pd.DataFrame, sectors: pd.DataFrame, config: E17Config) -> pd.DataFrame`
- [_safe_spearman](../../modelFactory/directional_alpha_book.py) — ligne 233 : `def _safe_spearman(group: pd.DataFrame, score: str, target: str) -> float`
- [_bootstrap](../../modelFactory/directional_alpha_book.py) — ligne 240 : `def _bootstrap(values: pd.Series, config: E17Config, horizon: int) -> tuple[float, float]`
- [select_rebalance_dates](../../modelFactory/directional_alpha_book.py) — ligne 252 : `def select_rebalance_dates(dates: pd.Series, config: E17Config) -> set[pd.Timestamp]`
- [evaluate_alpha](../../modelFactory/directional_alpha_book.py) — ligne 257 : `def evaluate_alpha(panel: pd.DataFrame, alpha: str, horizon: int, config: E17Config) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]`
- [build_gates](../../modelFactory/directional_alpha_book.py) — ligne 331 : `def build_gates(results: dict[str, dict[str, Any]], config: E17Config) -> dict[str, bool]`
- [run](../../modelFactory/directional_alpha_book.py) — ligne 355 : `def run(*, symbol_source: str, output_root: Path, config: E17Config) -> Path`
- [main](../../modelFactory/directional_alpha_book.py) — ligne 442 : `def main() -> None`

## `modelFactory/directional_alpha_book_confirmation.py`

Source SHA-256 : `278ea0f721e1576954e2462cd70f682cf8694775dd7b253d9131a56214293357`

- [load_locked_preregistration](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 41 : `def load_locked_preregistration(path: Path=DEFAULT_PREREGISTRATION) -> dict[str, Any]`
- [_bootstrap_ci](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 65 : `def _bootstrap_ci(values: pd.Series, protocol: dict[str, Any]) -> tuple[float, float]`
- [build_confirmation_cohorts](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 82 : `def build_confirmation_cohorts(panel: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame`
- [decide_confirmation](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 146 : `def decide_confirmation(cohorts: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]`
- [run](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 236 : `def run(*, preregistration_path: Path, end_date: str, output_root: Path) -> Path`
- [main](../../modelFactory/directional_alpha_book_confirmation.py) — ligne 306 : `def main() -> None`

## `modelFactory/directional_alpha_book_robustness.py`

Source SHA-256 : `d362b526b84e0794be2c62edd214776a7e6c1284f5cd3914d75504be05ee3cc6`

- [load_locked_protocol](../../modelFactory/directional_alpha_book_robustness.py) — ligne 25 : `def load_locked_protocol(path: Path=DEFAULT_PROTOCOL) -> dict[str, Any]`
- [assign_symbol_hash_fold](../../modelFactory/directional_alpha_book_robustness.py) — ligne 41 : `def assign_symbol_hash_fold(symbol: str, *, folds: int, salt: str) -> int`
- [select_offset_dates](../../modelFactory/directional_alpha_book_robustness.py) — ligne 46 : `def select_offset_dates(dates: pd.Series, *, rebalance_sessions: int, offset: int) -> set[pd.Timestamp]`
- [evaluate_long_top](../../modelFactory/directional_alpha_book_robustness.py) — ligne 53 : `def evaluate_long_top(frame: pd.DataFrame, protocol: dict[str, Any], *, calendar_offset: int, cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_bootstrap_ci](../../modelFactory/directional_alpha_book_robustness.py) — ligne 121 : `def _bootstrap_ci(values: pd.Series, protocol: dict[str, Any], *, seed_offset: int=0) -> tuple[float, float]`
- [summarize_cohorts](../../modelFactory/directional_alpha_book_robustness.py) — ligne 140 : `def summarize_cohorts(cohorts: pd.DataFrame, protocol: dict[str, Any], *, seed_offset: int=0) -> dict[str, Any]`
- [positive_contribution_concentration](../../modelFactory/directional_alpha_book_robustness.py) — ligne 175 : `def positive_contribution_concentration(constituents: pd.DataFrame) -> float`
- [evaluate_robustness](../../modelFactory/directional_alpha_book_robustness.py) — ligne 186 : `def evaluate_robustness(frame: pd.DataFrame, protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]`
- [run](../../modelFactory/directional_alpha_book_robustness.py) — ligne 333 : `def run(*, protocol_path: Path, output_root: Path) -> Path`
- [main](../../modelFactory/directional_alpha_book_robustness.py) — ligne 375 : `def main() -> None`

## `modelFactory/directional_complementarity_audit.py`

Source SHA-256 : `281de5af08c2f553b104eb7c9cfc3fc7d1f183331614dd08ed138071e26824ff`

- [aligned_panel](../../modelFactory/directional_complementarity_audit.py) — ligne 17 : `def aligned_panel(root, definitions)`
- [daily_corr](../../modelFactory/directional_complementarity_audit.py) — ligne 46 : `def daily_corr(frame, left, right)`
- [block_ci](../../modelFactory/directional_complementarity_audit.py) — ligne 52 : `def block_ci(values, block, samples=2000)`
- [residual_oof](../../modelFactory/directional_complementarity_audit.py) — ligne 66 : `def residual_oof(panel, family, others, horizon, minimum_train=252, test_size=126)`
- [audit_panel](../../modelFactory/directional_complementarity_audit.py) — ligne 92 : `def audit_panel(panel, families, horizon)`
- [run](../../modelFactory/directional_complementarity_audit.py) — ligne 136 : `def run(root, output)`
- [main](../../modelFactory/directional_complementarity_audit.py) — ligne 190 : `def main()`

## `modelFactory/directional_conditioning.py`

Source SHA-256 : `ce5514e504cf634f41dba6187fa39de396c86a68dba0c78e2aa0f740a294b059`

- [build_directional_oof_gate](../../modelFactory/directional_conditioning.py) — ligne 28 : `def build_directional_oof_gate(oracle_oof: pd.DataFrame, *, pool_pct: float=DEFAULT_POOL_PCT) -> tuple[pd.DataFrame, dict[str, Any]]`
- [load_or_rebuild_directional_oof_gate](../../modelFactory/directional_conditioning.py) — ligne 94 : `def load_or_rebuild_directional_oof_gate(engine: Any, *, oracle_batch_id: str, gate_path: Path | str, pool_pct: float=DEFAULT_POOL_PCT) -> tuple[pd.DataFrame, dict[str, Any]]`
- [attach_directional_oof_gate](../../modelFactory/directional_conditioning.py) — ligne 156 : `def attach_directional_oof_gate(prepared_df: pd.DataFrame, oracle_gate_df: pd.DataFrame) -> pd.DataFrame`
- [eligible_target_mask](../../modelFactory/directional_conditioning.py) — ligne 202 : `def eligible_target_mask(df: pd.DataFrame) -> pd.Series`
- [filter_eligible_target_rows](../../modelFactory/directional_conditioning.py) — ligne 213 : `def filter_eligible_target_rows(df: pd.DataFrame) -> pd.DataFrame`

## `modelFactory/directional_data_research/__init__.py`

Source SHA-256 : `e1c45f63555ecc409ecfa87cc9022caa13214fb2e567fe8cb29ee411a3843455`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/directional_data_research/analyst_revisions.py`

Source SHA-256 : `3f22d65dc287f106014770fa8cc14e580e1f53807fdef7340a9df4be1bc8f5c4`

- [load_earnings_calendar](../../modelFactory/directional_data_research/analyst_revisions.py) — ligne 71 : `def load_earnings_calendar(engine: Any) -> pd.DataFrame`
- [build_features](../../modelFactory/directional_data_research/analyst_revisions.py) — ligne 85 : `def build_features(pool: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/analyst_revisions.py) — ligne 154 : `def main() -> None`

## `modelFactory/directional_data_research/close_exhaustion_confirmation.py`

Source SHA-256 : `09a0a7acb62d1628a4c151fad579a7bd514f1ec29b9f361bbb62bd5496304eae`

- [select_disjoint_events](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 25 : `def select_disjoint_events(gate: pd.DataFrame, excluded_features: pd.DataFrame, *, start_date: str, end_date: str, count: int) -> pd.DataFrame`
- [exhaustion_feature](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 50 : `def exhaustion_feature(trades: pd.DataFrame) -> dict[str, Any]`
- [evaluate](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 66 : `def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [_progress](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 104 : `def _progress(path: Path, message: str) -> None`
- [run](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 110 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/close_exhaustion_confirmation.py) — ligne 163 : `def main() -> None`

## `modelFactory/directional_data_research/closing_quote_microstructure.py`

Source SHA-256 : `5f11e20ad39b50627659cc6cccb7aa88189502f5f5c7245a71974021fd065a6a`

- [load_closing_quotes](../../modelFactory/directional_data_research/closing_quote_microstructure.py) — ligne 48 : `def load_closing_quotes(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [derive_closing_quote_features](../../modelFactory/directional_data_research/closing_quote_microstructure.py) — ligne 87 : `def derive_closing_quote_features(raw: pd.DataFrame) -> pd.DataFrame`
- [summarize_coverage](../../modelFactory/directional_data_research/closing_quote_microstructure.py) — ligne 143 : `def summarize_coverage(pool: pd.DataFrame, features: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]`
- [evaluate_gates](../../modelFactory/directional_data_research/closing_quote_microstructure.py) — ligne 166 : `def evaluate_gates(diagnostics: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]`
- [main](../../modelFactory/directional_data_research/closing_quote_microstructure.py) — ligne 213 : `def main() -> None`

## `modelFactory/directional_data_research/earnings_revisions.py`

Source SHA-256 : `5f6b946dc247ecb9cb77877c8b47714b2bec5d199e4aad2da42396653bb49ba2`

- [load_earnings_features](../../modelFactory/directional_data_research/earnings_revisions.py) — ligne 51 : `def load_earnings_features(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [derive_earnings_features](../../modelFactory/directional_data_research/earnings_revisions.py) — ligne 77 : `def derive_earnings_features(raw: pd.DataFrame) -> pd.DataFrame`
- [merge_into_pool](../../modelFactory/directional_data_research/earnings_revisions.py) — ligne 93 : `def merge_into_pool(pool: pd.DataFrame, feats: pd.DataFrame, price_map: pd.DataFrame) -> pd.DataFrame`
- [load_close_prices](../../modelFactory/directional_data_research/earnings_revisions.py) — ligne 118 : `def load_close_prices(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/earnings_revisions.py) — ligne 143 : `def main() -> None`

## `modelFactory/directional_data_research/eroya_8k_features.py`

Source SHA-256 : `830b243664eec8e0b39620c40d4cedced5b06d00339fdfa8be2f74a98b9c10db`

- [load_8k_disclosures](../../modelFactory/directional_data_research/eroya_8k_features.py) — ligne 62 : `def load_8k_disclosures(path: Path) -> pd.DataFrame`
- [build_8k_count_features](../../modelFactory/directional_data_research/eroya_8k_features.py) — ligne 96 : `def build_8k_count_features(pool: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame`
- [evaluate_family_rules](../../modelFactory/directional_data_research/eroya_8k_features.py) — ligne 116 : `def evaluate_family_rules(frame: pd.DataFrame) -> pd.DataFrame`
- [evaluate_tertiary_discovery](../../modelFactory/directional_data_research/eroya_8k_features.py) — ligne 152 : `def evaluate_tertiary_discovery(pool: pd.DataFrame, events: pd.DataFrame, *, window_days: int=20) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/eroya_8k_features.py) — ligne 189 : `def main() -> int`

## `modelFactory/directional_data_research/eroya_earnings_features.py`

Source SHA-256 : `4f7867cb86549b52bffb2170b076d9e4bd8102747ba2b265c0a769402471fe4f`

- [load_earnings_events](../../modelFactory/directional_data_research/eroya_earnings_features.py) — ligne 35 : `def load_earnings_events(path: Path) -> pd.DataFrame`
- [build_earnings_features](../../modelFactory/directional_data_research/eroya_earnings_features.py) — ligne 64 : `def build_earnings_features(pool: pd.DataFrame, events: pd.DataFrame, *, max_age_days: int=90) -> pd.DataFrame`
- [evaluate_signed_rules](../../modelFactory/directional_data_research/eroya_earnings_features.py) — ligne 84 : `def evaluate_signed_rules(frame: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/eroya_earnings_features.py) — ligne 122 : `def main() -> int`

## `modelFactory/directional_data_research/eroya_features.py`

Source SHA-256 : `a8d335325bb84cb9c8ad5ca4536a19fa4aeb7cf6c648c99ade45e5cd6a38fe0f`

- [find_collection](../../modelFactory/directional_data_research/eroya_features.py) — ligne 44 : `def find_collection(dataset: str, root: Path=DEFAULT_ROOT, *, min_symbols: int=100) -> Path`
- [assemble_bundle_pool_at_horizon](../../modelFactory/directional_data_research/eroya_features.py) — ligne 67 : `def assemble_bundle_pool_at_horizon(engine: Any, batch_id: str, *, start_date: str, end_date: str, horizon: int) -> pd.DataFrame`
- [iter_payloads](../../modelFactory/directional_data_research/eroya_features.py) — ligne 105 : `def iter_payloads(path: Path) -> Iterable[tuple[str, dict[str, Any]]]`
- [load_short_volume](../../modelFactory/directional_data_research/eroya_features.py) — ligne 114 : `def load_short_volume(path: Path) -> pd.DataFrame`
- [load_short_interest](../../modelFactory/directional_data_research/eroya_features.py) — ligne 153 : `def load_short_interest(path: Path, calendar_path: Path=FINRA_CALENDAR) -> pd.DataFrame`
- [_nested_history](../../modelFactory/directional_data_research/eroya_features.py) — ligne 187 : `def _nested_history(payload: dict[str, Any], key: str) -> list[dict[str, Any]]`
- [load_analyst_events](../../modelFactory/directional_data_research/eroya_features.py) — ligne 195 : `def load_analyst_events(path: Path) -> pd.DataFrame`
- [load_analyst_insights](../../modelFactory/directional_data_research/eroya_features.py) — ligne 217 : `def load_analyst_insights(path: Path, *, strict: bool) -> pd.DataFrame`
- [load_insider_events](../../modelFactory/directional_data_research/eroya_features.py) — ligne 261 : `def load_insider_events(path: Path) -> pd.DataFrame`
- [load_form4_events](../../modelFactory/directional_data_research/eroya_features.py) — ligne 279 : `def load_form4_events(path: Path) -> pd.DataFrame`
- [build_form4_features](../../modelFactory/directional_data_research/eroya_features.py) — ligne 339 : `def build_form4_features(pool: pd.DataFrame, events: pd.DataFrame, *, prefix: str='eroya_form4') -> pd.DataFrame`
- [build_event_features](../../modelFactory/directional_data_research/eroya_features.py) — ligne 402 : `def build_event_features(pool: pd.DataFrame, events: pd.DataFrame, *, prefix: str) -> pd.DataFrame`
- [merge_asof_by_symbol](../../modelFactory/directional_data_research/eroya_features.py) — ligne 456 : `def merge_asof_by_symbol(pool: pd.DataFrame, features: pd.DataFrame, *, right_date: str, allow_exact: bool, max_age_days: int | None=None) -> pd.DataFrame`
- [analyze_complete_cases](../../modelFactory/directional_data_research/eroya_features.py) — ligne 478 : `def analyze_complete_cases(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame`
- [evaluate_policy_by_fold](../../modelFactory/directional_data_research/eroya_features.py) — ligne 519 : `def evaluate_policy_by_fold(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame`
- [evaluate_form4_signed_rules](../../modelFactory/directional_data_research/eroya_features.py) — ligne 549 : `def evaluate_form4_signed_rules(frame: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/eroya_features.py) — ligne 615 : `def main() -> int`

## `modelFactory/directional_data_research/form4_long_model_ablation.py`

Source SHA-256 : `2ebd6672dbc4614703b2e9ecaaf7c84c53d2b60d61bf839fe0b1cd12178a5b33`

- [restrict_experiment_period](../../modelFactory/directional_data_research/form4_long_model_ablation.py) — ligne 45 : `def restrict_experiment_period(frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame`
- [prepare_form4_model_features](../../modelFactory/directional_data_research/form4_long_model_ablation.py) — ligne 54 : `def prepare_form4_model_features(pool: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame`
- [evaluate_long_score](../../modelFactory/directional_data_research/form4_long_model_ablation.py) — ligne 76 : `def evaluate_long_score(frame: pd.DataFrame, score_column: str, *, top_fraction: float=0.1) -> dict[str, float | int | None]`
- [run_ablation](../../modelFactory/directional_data_research/form4_long_model_ablation.py) — ligne 94 : `def run_ablation(*, batch_id: str, start_date: str, end_date: str, horizon: int, profile_path: Path, output: Path, iterations: int=600, depth: int=6, learning_rate: float=0.03) -> dict`
- [main](../../modelFactory/directional_data_research/form4_long_model_ablation.py) — ligne 206 : `def main() -> int`

## `modelFactory/directional_data_research/harness.py`

Source SHA-256 : `40a3ed28749bad55a2b6af97553d2fa1651385c907d2a828e67be4ca02d16555`

- [load_oracle_pool_proba](../../modelFactory/directional_data_research/harness.py) — ligne 34 : `def load_oracle_pool_proba(batch_id: str, oracle_run: str | None=None) -> pd.DataFrame`
- [assemble_pool](../../modelFactory/directional_data_research/harness.py) — ligne 68 : `def assemble_pool(engine: Any, batch_id: str, *, start_date: str, end_date: str, horizon: int=20, pool_pct: float=0.2, oracle_run: str | None=None, labels_parquet: str | Path | None=None, oracle_pool_parquet: str | Path | None=None) -> pd.DataFrame`
- [_ic_spearman](../../modelFactory/directional_data_research/harness.py) — ligne 158 : `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None`
- [_auc_bad_good](../../modelFactory/directional_data_research/harness.py) — ligne 169 : `def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 5), good=(6, 10)) -> float | None`
- [analyze_features](../../modelFactory/directional_data_research/harness.py) — ligne 178 : `def analyze_features(pool: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame`
- [format_report](../../modelFactory/directional_data_research/harness.py) — ligne 235 : `def format_report(df: pd.DataFrame, top_n: int=12) -> str`

## `modelFactory/directional_data_research/intraday_market_context_pilot.py`

Source SHA-256 : `a3796d65f978575978b23dbd9aae08a82a9b09fa936f9dbcab036e3e59427514`

- [fetch_asset_range](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 31 : `def fetch_asset_range(client: EroyaClient, symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, dict[str, Any]]`
- [daily_asset_features](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 62 : `def daily_asset_features(bars: pd.DataFrame, symbol: str) -> pd.DataFrame`
- [build_market_features](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 89 : `def build_market_features(asset_frames: dict[str, pd.DataFrame]) -> pd.DataFrame`
- [evaluate](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 108 : `def evaluate(events: pd.DataFrame, market: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 134 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/intraday_market_context_pilot.py) — ligne 173 : `def main() -> None`

## `modelFactory/directional_data_research/intraday_session_path_pilot.py`

Source SHA-256 : `08dbcebd14495bc23677417690fe4c7ba5e348ac697736b54e800bf780be27eb`

- [select_unique_date_events](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 33 : `def select_unique_date_events(gate: pd.DataFrame, *, start_date: str, end_date: str, count: int) -> pd.DataFrame`
- [fetch_bars](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 51 : `def fetch_bars(client: EroyaClient, symbol: str, date: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]`
- [regular_session_bars](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 63 : `def regular_session_bars(bars: pd.DataFrame) -> pd.DataFrame`
- [session_features](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 76 : `def session_features(bars: pd.DataFrame) -> dict[str, Any]`
- [_evaluate_family](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 113 : `def _evaluate_family(data: pd.DataFrame, features: list[str], target: str, continuous_target: str, *, minimum_rows: int, total_tests: int) -> dict[str, Any]`
- [evaluate](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 154 : `def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [_progress](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 179 : `def _progress(path: Path, message: str) -> None`
- [run](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 185 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/intraday_session_path_pilot.py) — ligne 236 : `def main() -> None`

## `modelFactory/directional_data_research/news_sentiment.py`

Source SHA-256 : `de475cc4c79b97536d36e8a3d5c3fbed6d1f12848eeb3ac895ddcd47efa44cab`

- [load_sentiment_daily](../../modelFactory/directional_data_research/news_sentiment.py) — ligne 48 : `def load_sentiment_daily(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [build_news_features](../../modelFactory/directional_data_research/news_sentiment.py) — ligne 82 : `def build_news_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/news_sentiment.py) — ligne 110 : `def main() -> None`

## `modelFactory/directional_data_research/options_volume_repair.py`

Source SHA-256 : `1f9106605eeee65a49207b8ed5187f326cb0928968874b75951b9538230b46a5`

- [aggregate_four_leg_volumes](../../modelFactory/directional_data_research/options_volume_repair.py) — ligne 25 : `def aggregate_four_leg_volumes(values: dict[str, float | None]) -> dict[str, Any]`
- [_load_config](../../modelFactory/directional_data_research/options_volume_repair.py) — ligne 42 : `def _load_config(source: Path) -> OptionsDirectionalConfig`
- [run](../../modelFactory/directional_data_research/options_volume_repair.py) — ligne 49 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/options_volume_repair.py) — ligne 118 : `def main() -> None`

## `modelFactory/directional_data_research/short_interest.py`

Source SHA-256 : `bc0c177e717bdb3999824fe947017f1b0ace581b60a9b2b454904f1e8ab0699a`

- [load_daily_short_volume](../../modelFactory/directional_data_research/short_interest.py) — ligne 52 : `def load_daily_short_volume() -> pd.DataFrame`
- [load_short_interest](../../modelFactory/directional_data_research/short_interest.py) — ligne 63 : `def load_short_interest() -> pd.DataFrame`
- [build_daily_features](../../modelFactory/directional_data_research/short_interest.py) — ligne 78 : `def build_daily_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame`
- [build_short_interest_features](../../modelFactory/directional_data_research/short_interest.py) — ligne 107 : `def build_short_interest_features(pool: pd.DataFrame, si: pd.DataFrame) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/short_interest.py) — ligne 133 : `def main() -> None`

## `modelFactory/directional_data_research/signed_flow_pilot.py`

Source SHA-256 : `4c08806a8924d49fc0dac4ecda62375ead226467b3b3b365d82ee28de6c07512`

- [_event_hash](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 30 : `def _event_hash(date: pd.Timestamp, symbol: str) -> str`
- [select_events](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 34 : `def select_events(gate: pd.DataFrame, *, start_date: str, end_date: str, count: int) -> pd.DataFrame`
- [_window](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 64 : `def _window(date: pd.Timestamp, minutes: int) -> tuple[str, str]`
- [fetch_ticks](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 70 : `def fetch_ticks(client: EroyaClient, endpoint: str, symbol: str, start: str, end: str, *, max_records: int, page_limit: int=50000) -> tuple[pd.DataFrame, dict[str, Any]]`
- [signed_flow_features](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 102 : `def signed_flow_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> dict[str, Any]`
- [evaluate_direction](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 147 : `def evaluate_direction(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 198 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/signed_flow_pilot.py) — ligne 252 : `def main() -> None`

## `modelFactory/directional_data_research/signed_flow_temporal_audit.py`

Source SHA-256 : `fc8759af2db1015477d8bf8dfecfe8549dfa77933c10c579320aea9c98bd87ab`

- [_tick_time](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 34 : `def _tick_time(frame: pd.DataFrame) -> pd.Series`
- [temporal_features](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 38 : `def temporal_features(trades: pd.DataFrame, quotes: pd.DataFrame, close_utc: str) -> dict[str, Any]`
- [candidate_features](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 72 : `def candidate_features() -> list[str]`
- [evaluate](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 83 : `def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [_progress](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 135 : `def _progress(path: Path, message: str) -> None`
- [run](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 142 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/signed_flow_temporal_audit.py) — ligne 199 : `def main() -> None`

## `modelFactory/directional_data_research/tick_price_liquidity_audit.py`

Source SHA-256 : `55ad78754a46ce5c483bf4c9e71691194ae16856712f44502867b928138b8b0f`

- [event_features](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 22 : `def event_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> dict[str, Any]`
- [build_features](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 65 : `def build_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame`
- [_semester_rows](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 77 : `def _semester_rows(data: pd.DataFrame, feature: str, target: str) -> tuple[list[dict[str, Any]], float]`
- [evaluate](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 88 : `def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 147 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/directional_data_research/tick_price_liquidity_audit.py) — ligne 171 : `def main() -> None`

## `modelFactory/directional_data_research/yahoo_analyst_features.py`

Source SHA-256 : `5d324640aed628669e732acc4bc549bc548563a5d132f5eeee06a8415b2088b9`

- [assemble_pool_db](../../modelFactory/directional_data_research/yahoo_analyst_features.py) — ligne 68 : `def assemble_pool_db(engine: Any, batch_id: str, *, start_date: str, end_date: str, horizon: int=20, pool_pct: float=0.2) -> pd.DataFrame`
- [_event_arrays](../../modelFactory/directional_data_research/yahoo_analyst_features.py) — ligne 128 : `def _event_arrays(ev: pd.DataFrame) -> dict[str, np.ndarray]`
- [build_features](../../modelFactory/directional_data_research/yahoo_analyst_features.py) — ligne 141 : `def build_features(pool: pd.DataFrame, ud: dict[str, pd.DataFrame]) -> pd.DataFrame`
- [main](../../modelFactory/directional_data_research/yahoo_analyst_features.py) — ligne 208 : `def main() -> None`

## `modelFactory/directional_data_research/yahoo_sources.py`

Source SHA-256 : `3eb87f711881853e4f0e1e10fcd7ec90b4f37d75fe70e8243d7318d061e6313d`

- [_grade_num](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 48 : `def _grade_num(g: Any) -> float`
- [normalize_ud](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 54 : `def normalize_ud(df: pd.DataFrame) -> pd.DataFrame`
- [_cache_path](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 84 : `def _cache_path(symbol: str) -> Path`
- [download_upgrades_downgrades](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 88 : `def download_upgrades_downgrades(symbol: str, *, force: bool=False, sleep_s: float=0.4) -> pd.DataFrame`
- [download_many](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 116 : `def download_many(symbols: list[str], *, force: bool=False, sleep_s: float=0.4, log_every: int=25) -> dict[str, pd.DataFrame]`
- [load_all](../../modelFactory/directional_data_research/yahoo_sources.py) — ligne 127 : `def load_all(symbols: list[str]) -> dict[str, pd.DataFrame]`

## `modelFactory/directional_quality.py`

Source SHA-256 : `54513c94ed70db92392532fcf0c9aa52f1217fedaa2696afb3b929f9944a6b9a`

- [DirectionalQualityGate](../../modelFactory/directional_quality.py) — ligne 20 : `class DirectionalQualityGate`
- [load_directional_quality_gate](../../modelFactory/directional_quality.py) — ligne 29 : `def load_directional_quality_gate(batch_id: str, artifacts_dir: Path | str, *, level: str='strict') -> DirectionalQualityGate`
- [apply_directional_quality_gate](../../modelFactory/directional_quality.py) — ligne 77 : `def apply_directional_quality_gate(predictions: pd.DataFrame, gate: DirectionalQualityGate) -> tuple[pd.DataFrame, dict[str, int]]`

## `modelFactory/directional_serving.py`

Source SHA-256 : `c8db18db32e18b4a7dbc5e6e80d82d06701098136c658225524072df82428476`

- [_explicit_bool](../../modelFactory/directional_serving.py) — ligne 12 : `def _explicit_bool(value: Any) -> bool | None`
- [selected_model_is_eligible](../../modelFactory/directional_serving.py) — ligne 26 : `def selected_model_is_eligible(config: Mapping[str, Any] | None) -> bool`
- [training_result_is_servable](../../modelFactory/directional_serving.py) — ligne 33 : `def training_result_is_servable(metrics: Mapping[str, Any] | None) -> bool`

## `modelFactory/drift_monitor.py`

Source SHA-256 : `62bc4e2f13647eb703cc2fc66c79d87c29a3be4a7f29de69f130f70747948300`

- [DriftReport](../../modelFactory/drift_monitor.py) — ligne 42 : `class DriftReport`
- [DriftReport.to_payload](../../modelFactory/drift_monitor.py) — ligne 52 : `def to_payload(self) -> dict[str, Any]`
- [_ks_two_sample](../../modelFactory/drift_monitor.py) — ligne 70 : `def _ks_two_sample(a: np.ndarray, b: np.ndarray) -> tuple[float, float]`
- [_psi](../../modelFactory/drift_monitor.py) — ligne 101 : `def _psi(now: np.ndarray, baseline: np.ndarray, *, buckets: int=10) -> float`
- [compute_drift](../../modelFactory/drift_monitor.py) — ligne 123 : `def compute_drift(today_predictions: Sequence[float], baseline_predictions: Sequence[float], *, model_id: str, ks_warn: float=DEFAULT_KS_WARN, ks_alert: float=DEFAULT_KS_ALERT, psi_warn: float=DEFAULT_PSI_WARN, psi_alert: float=DEFAULT_PSI_ALERT) -> DriftReport`
- [persist_drift_run](../../modelFactory/drift_monitor.py) — ligne 174 : `def persist_drift_run(report: DriftReport, *, engine: Any, run_id: str | None=None) -> str`

## `modelFactory/drift_policy.py`

Source SHA-256 : `ff206df382a0b7a647442a6221f9a7b6b9608a9daf032d510961d93a79d67b29`

- [MLPolicyDecision](../../modelFactory/drift_policy.py) — ligne 47 : `class MLPolicyDecision`
- [MLPolicyDecision.to_dict](../../modelFactory/drift_policy.py) — ligne 61 : `def to_dict(self) -> dict[str, Any]`
- [evaluate_drift_gate](../../modelFactory/drift_policy.py) — ligne 65 : `def evaluate_drift_gate(report: DriftReport | None, *, kill_on: tuple[str, ...]=DEFAULT_KILL_STATUSES, warn_grace: bool=True) -> MLPolicyDecision`
- [apply_kill_switch](../../modelFactory/drift_policy.py) — ligne 195 : `def apply_kill_switch(decision: MLPolicyDecision, predictions_df: pd.DataFrame, *, proba_columns: tuple[str, ...]=('predicted_proba', 'raw_proba')) -> pd.DataFrame`
- [persist_kill_switch_event](../../modelFactory/drift_policy.py) — ligne 224 : `def persist_kill_switch_event(decision: MLPolicyDecision, *, engine: Any) -> None`
- [summary_fields](../../modelFactory/drift_policy.py) — ligne 268 : `def summary_fields(decision: MLPolicyDecision | None) -> dict[str, Any]`

## `modelFactory/eroya_directional_poc.py`

Source SHA-256 : `3bf628413426e8847d3fc86cf339c351c223c1c1a17d2dfb6d4c098332ca7946`

- [_normalize_api_url](../../modelFactory/eroya_directional_poc.py) — ligne 33 : `def _normalize_api_url(url_or_path: str) -> str`
- [_windows_trust_context](../../modelFactory/eroya_directional_poc.py) — ligne 60 : `def _windows_trust_context() -> ssl.SSLContext`
- [_SystemTrustAdapter](../../modelFactory/eroya_directional_poc.py) — ligne 72 : `class _SystemTrustAdapter(HTTPAdapter)`
- [_SystemTrustAdapter.__init__](../../modelFactory/eroya_directional_poc.py) — ligne 73 : `def __init__(self, *args: Any, **kwargs: Any) -> None`
- [_SystemTrustAdapter.init_poolmanager](../../modelFactory/eroya_directional_poc.py) — ligne 77 : `def init_poolmanager(self, *args: Any, **kwargs: Any) -> None`
- [_SystemTrustAdapter.proxy_manager_for](../../modelFactory/eroya_directional_poc.py) — ligne 81 : `def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any)`
- [DatasetSpec](../../modelFactory/eroya_directional_poc.py) — ligne 87 : `class DatasetSpec`
- [EroyaClient](../../modelFactory/eroya_directional_poc.py) — ligne 129 : `class EroyaClient`
- [EroyaClient.__init__](../../modelFactory/eroya_directional_poc.py) — ligne 130 : `def __init__(self, api_key: str, *, timeout_seconds: float=30.0, max_retries: int=3, session: requests.Session | None=None) -> None`
- [EroyaClient.get](../../modelFactory/eroya_directional_poc.py) — ligne 141 : `def get(self, url_or_path: str, *, params: dict[str, Any] | None=None) -> requests.Response`
- [_request_for](../../modelFactory/eroya_directional_poc.py) — ligne 155 : `def _request_for(spec: DatasetSpec, symbol: str, *, start_date: str | None, end_date: str | None, probe: bool) -> tuple[str, dict[str, Any]]`
- [_safe_error](../../modelFactory/eroya_directional_poc.py) — ligne 186 : `def _safe_error(response: requests.Response) -> str | None`
- [_result_count](../../modelFactory/eroya_directional_poc.py) — ligne 199 : `def _result_count(payload: Any) -> int | None`
- [probe_entitlements](../../modelFactory/eroya_directional_poc.py) — ligne 211 : `def probe_entitlements(client: EroyaClient, datasets: Iterable[str], *, symbol: str='AAPL') -> list[dict[str, Any]]`
- [collect_dataset](../../modelFactory/eroya_directional_poc.py) — ligne 227 : `def collect_dataset(client: EroyaClient, spec: DatasetSpec, symbols: list[str], destination: Path, *, start_date: str | None, end_date: str | None, max_pages: int) -> dict[str, Any]`
- [_api_key](../../modelFactory/eroya_directional_poc.py) — ligne 262 : `def _api_key() -> str`
- [_dataset_names](../../modelFactory/eroya_directional_poc.py) — ligne 269 : `def _dataset_names(raw: str, defaults: tuple[str, ...]) -> list[str]`
- [main](../../modelFactory/eroya_directional_poc.py) — ligne 277 : `def main() -> int`

## `modelFactory/evaluation.py`

Source SHA-256 : `23acb8389aa1ac726e556c4ea5825d5a36c6036bee55c31e02b9640b50dbbdd3`

- [_validate_proba_array](../../modelFactory/evaluation.py) — ligne 21 : `def _validate_proba_array(proba: np.ndarray, *, tol: float=1e-06) -> str | None`
- [multiclass_auc_one_vs_rest](../../modelFactory/evaluation.py) — ligne 35 : `def multiclass_auc_one_vs_rest(y_true: np.ndarray, y_proba: np.ndarray) -> dict[str, float | None]`
- [multiclass_brier_score](../../modelFactory/evaluation.py) — ligne 80 : `def multiclass_brier_score(y_true: np.ndarray, y_proba: np.ndarray) -> float | None`
- [multiclass_log_loss](../../modelFactory/evaluation.py) — ligne 102 : `def multiclass_log_loss(y_true: np.ndarray, y_proba: np.ndarray, *, eps: float=1e-15) -> float | None`
- [multiclass_balanced_accuracy](../../modelFactory/evaluation.py) — ligne 127 : `def multiclass_balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float | None`
- [compute_multiclass_metrics](../../modelFactory/evaluation.py) — ligne 147 : `def compute_multiclass_metrics(y_true: np.ndarray, y_proba: np.ndarray, *, class_names: tuple[str, ...]=('short', 'flat', 'long')) -> dict[str, Any]`
- [compute_directional_oos_metrics](../../modelFactory/evaluation.py) — ligne 244 : `def compute_directional_oos_metrics(probabilities: np.ndarray, future_returns: np.ndarray, *, policy: TernaryDecisionPolicy | None=None) -> dict[str, dict[str, float | int | None]]`
- [check_model_collapse](../../modelFactory/evaluation.py) — ligne 284 : `def check_model_collapse(y_proba: np.ndarray, *, min_action_rate: float=0.01, min_class_fraction: float=0.005, max_single_class_fraction: float=0.99) -> tuple[bool, str | None]`
- [compute_business_score](../../modelFactory/evaluation.py) — ligne 342 : `def compute_business_score(*, precision_long: float, coverage_at_threshold: float, avg_future_return_on_actions: float | None=None, hit_rate_on_actions: float | None=None) -> float`
- [bucket_analysis](../../modelFactory/evaluation.py) — ligne 362 : `def bucket_analysis(probabilities: np.ndarray, labels: np.ndarray, future_returns: np.ndarray | None=None, *, n_buckets: int=5) -> dict[str, Any]`
- [compute_threshold_metrics](../../modelFactory/evaluation.py) — ligne 438 : `def compute_threshold_metrics(probabilities: np.ndarray, labels: np.ndarray, future_returns: np.ndarray | None, *, decision_threshold: float, n_buckets: int=5) -> dict[str, Any]`
- [optimize_decision_threshold](../../modelFactory/evaluation.py) — ligne 508 : `def optimize_decision_threshold(probabilities: np.ndarray, labels: np.ndarray, future_returns: np.ndarray | None, *, candidate_thresholds: tuple[float, ...] | list[float], default_threshold: float, min_action_rate: float, max_action_rate: float, min_precision_long: float, n_buckets: int=5) -> dict[str, Any]`
- [align_sequence_rows](../../modelFactory/evaluation.py) — ligne 587 : `def align_sequence_rows(df: pd.DataFrame, seq_len: int) -> pd.DataFrame`

## `modelFactory/factor_features.py`

Source SHA-256 : `ada98e6f68d2486c717dbc3a29c64188e6eac8c16daefa00e1d4857bfe0631f5`

- [compute_factor_features](../../modelFactory/factor_features.py) — ligne 37 : `def compute_factor_features(df: pd.DataFrame, benchmark_df: pd.DataFrame | None=None) -> pd.DataFrame`
- [fill_factor_defaults](../../modelFactory/factor_features.py) — ligne 123 : `def fill_factor_defaults(df: pd.DataFrame) -> pd.DataFrame`

## `modelFactory/feature_logging.py`

Source SHA-256 : `6f4a9d955bd0954692aea25a75c563ec00188571b9a7bd62106b838d393650c5`

- [log_feature_values](../../modelFactory/feature_logging.py) — ligne 28 : `def log_feature_values(df: pd.DataFrame, feature_columns: list[str], *, label: str) -> None`
- [log_feature_weights](../../modelFactory/feature_logging.py) — ligne 63 : `def log_feature_weights(model: Any, feature_columns: list[str], *, label: str) -> None`
- [_extract_importance](../../modelFactory/feature_logging.py) — ligne 90 : `def _extract_importance(model: Any) -> np.ndarray | None`
- [log_feature_duplicates](../../modelFactory/feature_logging.py) — ligne 131 : `def log_feature_duplicates(df: pd.DataFrame, feature_columns: list[str], *, label: str) -> None`

## `modelFactory/feature_profiles.py`

Source SHA-256 : `be1054581ba3ee20c73f4b7de1e16424912b2d1ec4b9e799da78cae6551b99a5`

- [directional_target_contract](../../modelFactory/feature_profiles.py) — ligne 28 : `def directional_target_contract() -> dict[str, Any]`
- [profile_directory](../../modelFactory/feature_profiles.py) — ligne 45 : `def profile_directory(direction: Direction, root: Path=PROFILE_ROOT) -> Path`
- [discover_feature_profiles](../../modelFactory/feature_profiles.py) — ligne 49 : `def discover_feature_profiles(direction: Direction, root: Path=PROFILE_ROOT) -> list[str]`
- [resolve_profile_path](../../modelFactory/feature_profiles.py) — ligne 57 : `def resolve_profile_path(direction: Direction, name: str, root: Path=PROFILE_ROOT) -> Path`
- [load_feature_profile](../../modelFactory/feature_profiles.py) — ligne 69 : `def load_feature_profile(direction: Direction, name: str, root: Path=PROFILE_ROOT) -> dict[str, Any]`
- [apply_feature_profile](../../modelFactory/feature_profiles.py) — ligne 90 : `def apply_feature_profile(cfg: TrainingConfig, profile: dict[str, Any], direction: Direction) -> TrainingConfig`

## `modelFactory/features.py`

Source SHA-256 : `1e0014e248610d84cc315adc73a53e54803e83ce5f1857edbf2beba677cf636e`

- [_positive_denominator_ratio](../../modelFactory/features.py) — ligne 19 : `def _positive_denominator_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series`
- [_zscore_column_name](../../modelFactory/features.py) — ligne 210 : `def _zscore_column_name(source_col: str) -> str`
- [apply_feature_whitelist](../../modelFactory/features.py) — ligne 397 : `def apply_feature_whitelist(full_columns: list[str], whitelist: object) -> list[str]`
- [get_feature_columns](../../modelFactory/features.py) — ligne 431 : `def get_feature_columns(include_sentiment: bool=False, feature_set: str='v1', include_cross_sectional: bool=False, include_screener_scores: bool=False, include_short_score: bool=False, include_macro_vix: bool=False, include_macro_vxn: bool=False, include_macro_vix3m: bool=False, include_macro_move: bool=False, include_global_stacking: bool=False, include_fundamentals: bool=False, include_factors: bool=False, include_macro_regime: bool=False, include_score_components: bool=False, include_volume_features: bool=False, feature_whitelist_enabled: bool=False, feature_whitelist: tuple[str, ...]=()) -> list[str]`
- [fingerprint](../../modelFactory/features.py) — ligne 545 : `def fingerprint(*, include_sentiment: bool=False, feature_set: str='v1', include_cross_sectional: bool=False, include_screener_scores: bool=False, include_short_score: bool=False, include_macro_vix: bool=False, include_macro_vxn: bool=False, include_macro_vix3m: bool=False, include_macro_move: bool=False, include_global_stacking: bool=False, include_fundamentals: bool=False, include_factors: bool=False, include_macro_regime: bool=False, include_score_components: bool=False, include_volume_features: bool=False, feature_whitelist_enabled: bool=False, feature_whitelist: tuple[str, ...]=(), feature_columns: list[str] | None=None) -> str`
- [normalize_feature_columns](../../modelFactory/features.py) — ligne 618 : `def normalize_feature_columns(value: object) -> list[str] | None`
- [build_feature_contract](../../modelFactory/features.py) — ligne 627 : `def build_feature_contract(*, include_sentiment: bool=False, feature_set: str='v1', include_cross_sectional: bool=False, include_screener_scores: bool=False, include_short_score: bool=False, include_macro_vix: bool=False, include_macro_vxn: bool=False, include_macro_vix3m: bool=False, include_macro_move: bool=False, include_global_stacking: bool=False, include_fundamentals: bool=False, include_factors: bool=False, include_macro_regime: bool=False, include_score_components: bool=False, include_volume_features: bool=False, feature_whitelist_enabled: bool=False, feature_whitelist: tuple[str, ...]=(), feature_columns: list[str] | None=None, scaler_feature_names: list[str] | None=None) -> dict[str, object]`
- [validate_feature_contract](../../modelFactory/features.py) — ligne 705 : `def validate_feature_contract(contract_payload: object, *, include_sentiment: bool=False, feature_set: str='v1', include_cross_sectional: bool=False, include_screener_scores: bool=False, include_short_score: bool=False, include_macro_vix: bool=False, include_macro_vxn: bool=False, include_macro_vix3m: bool=False, include_macro_move: bool=False, include_global_stacking: bool=False, include_fundamentals: bool=False, include_factors: bool=False, include_macro_regime: bool=False, include_score_components: bool=False, include_volume_features: bool=False, feature_whitelist_enabled: bool=False, feature_whitelist: tuple[str, ...]=(), persisted_feature_columns: object=None, persisted_feature_fingerprint: object=None, scaler_feature_names: object=None, route_feature_columns: object=None, route_feature_fingerprint: object=None, runtime_feature_columns: object=None, allow_legacy_missing_contract: bool=False) -> str | None`
- [_merge_macro_features](../../modelFactory/features.py) — ligne 881 : `def _merge_macro_features(df: pd.DataFrame, *, include_vix: bool=False, include_vxn: bool=False, include_vix3m: bool=False, include_move: bool=False) -> pd.DataFrame`
- [_fill_macro_defaults](../../modelFactory/features.py) — ligne 1002 : `def _fill_macro_defaults(df: pd.DataFrame, include_vix: bool, include_vxn: bool, include_vix3m: bool, include_move: bool) -> None`
- [compute_features](../../modelFactory/features.py) — ligne 1026 : `def compute_features(df: pd.DataFrame, sentiment_df: pd.DataFrame | None=None, include_sentiment: bool=False, benchmark_df: pd.DataFrame | None=None, feature_set: str='v1', selector_df: pd.DataFrame | None=None, include_screener_scores: bool=False, include_short_score: bool=False, include_macro_vix: bool=False, include_macro_vxn: bool=False, include_macro_vix3m: bool=False, include_macro_move: bool=False, include_fundamentals: bool=False, fundamental_df: pd.DataFrame | None=None, include_factors: bool=False, include_macro_regime: bool=False, include_score_components: bool=False, include_volume_features: bool=False) -> pd.DataFrame`
- [compute_rank_interactions](../../modelFactory/features.py) — ligne 1536 : `def compute_rank_interactions(df: pd.DataFrame) -> pd.DataFrame`
- [build_target](../../modelFactory/features.py) — ligne 1574 : `def build_target(df: pd.DataFrame, horizon: int=5, mode: str='binary', positive_threshold: float=0.0, negative_threshold: float=0.0, *, skip_winsorize: bool=False, skip_vol_scaling: bool=False, excess_vs_spy: bool=False) -> pd.Series`
- [compute_future_return](../../modelFactory/features.py) — ligne 1646 : `def compute_future_return(df: pd.DataFrame, horizon: int=5) -> pd.Series`
- [build_multi_horizon_targets](../../modelFactory/features.py) — ligne 1652 : `def build_multi_horizon_targets(df: pd.DataFrame, horizons: tuple[int, ...], mode: str='binary', positive_threshold: float=0.0, negative_threshold: float=0.0, *, skip_winsorize: bool=False, skip_vol_scaling: bool=False, excess_vs_spy: bool=False) -> pd.DataFrame`
- [standardize_regression_target](../../modelFactory/features.py) — ligne 1703 : `def standardize_regression_target(prepared_df: pd.DataFrame, train_mask: 'pd.Series | None'=None) -> pd.DataFrame`
- [_build_adjusted_price_frame](../../modelFactory/features.py) — ligne 1747 : `def _build_adjusted_price_frame(df: pd.DataFrame) -> pd.DataFrame`
- [_range_position](../../modelFactory/features.py) — ligne 1776 : `def _range_position(close: pd.Series, window: int) -> pd.Series`
- [_rsi](../../modelFactory/features.py) — ligne 1781 : `def _rsi(close: pd.Series, period: int=14) -> pd.Series`
- [_atr_norm](../../modelFactory/features.py) — ligne 1791 : `def _atr_norm(high: pd.Series, low: pd.Series, close: pd.Series, period: int=14) -> pd.Series`
- [_atr_value](../../modelFactory/features.py) — ligne 1802 : `def _atr_value(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series`
- [_adx](../../modelFactory/features.py) — ligne 1813 : `def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int=14) -> pd.Series`

## `modelFactory/first_touch_binary.py`

Source SHA-256 : `fb615003426fda39570316cd42b2d8dd20b7baadb7427d85721d88e1fe906fee`

- [add_binary_target](../../modelFactory/first_touch_binary.py) — ligne 70 : `def add_binary_target(frame: pd.DataFrame) -> pd.DataFrame`
- [_fit_binary](../../modelFactory/first_touch_binary.py) — ligne 80 : `def _fit_binary(train: pd.DataFrame, valid: pd.DataFrame | None, features: list[str], categoricals: list[str], config: SharedDirectionalConfig, *, iterations: int | None=None) -> Any`
- [score_binary_model](../../modelFactory/first_touch_binary.py) — ligne 118 : `def score_binary_model(model: Any, frame: pd.DataFrame, features: list[str], categoricals: list[str]) -> pd.DataFrame`
- [train_first_touch_binary](../../modelFactory/first_touch_binary.py) — ligne 137 : `def train_first_touch_binary(dataset: pd.DataFrame, features: list[str], categoricals: list[str], training: SharedDirectionalConfig, target_config: FirstTouchConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_first_touch_binary_campaign](../../modelFactory/first_touch_binary.py) — ligne 239 : `def run_first_touch_binary_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, training_config: SharedDirectionalConfig | None=None, target_config: FirstTouchConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/first_touch_binary.py) — ligne 344 : `def _summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/first_touch_binary.py) — ligne 360 : `def main() -> None`

## `modelFactory/first_touch_directional.py`

Source SHA-256 : `380f15dab45d323d6843aa01ec0ebea6efe0a896aaa7da8b694ea525ab0b13ac`

- [FirstTouchConfig](../../modelFactory/first_touch_directional.py) — ligne 72 : `class FirstTouchConfig`
- [FirstTouchConfig.__post_init__](../../modelFactory/first_touch_directional.py) — ligne 83 : `def __post_init__(self) -> None`
- [build_first_touch_panel](../../modelFactory/first_touch_directional.py) — ligne 98 : `def build_first_touch_panel(bars: pd.DataFrame, config: FirstTouchConfig) -> pd.DataFrame`
- [attach_first_touch_targets](../../modelFactory/first_touch_directional.py) — ligne 176 : `def attach_first_touch_targets(pool: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame`
- [_fit_multiclass](../../modelFactory/first_touch_directional.py) — ligne 188 : `def _fit_multiclass(train: pd.DataFrame, valid: pd.DataFrame | None, features: list[str], categoricals: list[str], config: SharedDirectionalConfig, *, iterations: int | None=None) -> Any`
- [_score_model](../../modelFactory/first_touch_directional.py) — ligne 221 : `def _score_model(model: Any, frame: pd.DataFrame, features: list[str], categoricals: list[str]) -> pd.DataFrame`
- [apply_first_touch_policy](../../modelFactory/first_touch_directional.py) — ligne 235 : `def apply_first_touch_policy(frame: pd.DataFrame, margin: float) -> pd.DataFrame`
- [_cvar](../../modelFactory/first_touch_directional.py) — ligne 252 : `def _cvar(values: pd.Series, fraction: float=0.05) -> float | None`
- [_concentration](../../modelFactory/first_touch_directional.py) — ligne 259 : `def _concentration(selected: pd.DataFrame) -> float | None`
- [_policy_metrics](../../modelFactory/first_touch_directional.py) — ligne 267 : `def _policy_metrics(frame: pd.DataFrame, margin: float, catastrophic: float) -> dict[str, Any]`
- [evaluate_first_touch_oos](../../modelFactory/first_touch_directional.py) — ligne 313 : `def evaluate_first_touch_oos(frame: pd.DataFrame, config: FirstTouchConfig | None=None, margins: tuple[float, ...]=DIAGNOSTIC_MARGINS) -> dict[str, Any]`
- [_stability](../../modelFactory/first_touch_directional.py) — ligne 368 : `def _stability(oof: pd.DataFrame, config: FirstTouchConfig) -> dict[str, Any]`
- [_gates](../../modelFactory/first_touch_directional.py) — ligne 391 : `def _gates(overall: dict[str, Any], stability: dict[str, Any], config: FirstTouchConfig) -> dict[str, Any]`
- [train_first_touch](../../modelFactory/first_touch_directional.py) — ligne 417 : `def train_first_touch(dataset: pd.DataFrame, features: list[str], categoricals: list[str], training: SharedDirectionalConfig, target_config: FirstTouchConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_first_touch_campaign](../../modelFactory/first_touch_directional.py) — ligne 496 : `def run_first_touch_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, training_config: SharedDirectionalConfig | None=None, target_config: FirstTouchConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/first_touch_directional.py) — ligne 593 : `def _summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/first_touch_directional.py) — ligne 610 : `def main() -> None`

## `modelFactory/fr_benchmark_features.py`

Source SHA-256 : `8be0fb534c2bfa3a2a5dbca83ad8d18106d64fb3aa9fb20ed77077f4b3db0d6e`

- [load_config](../../modelFactory/fr_benchmark_features.py) — ligne 38 : `def load_config(path: Path) -> dict`
- [benchmark_windows](../../modelFactory/fr_benchmark_features.py) — ligne 59 : `def benchmark_windows(rows: pd.DataFrame, sessions: list[str]) -> pd.DataFrame`
- [enrich](../../modelFactory/fr_benchmark_features.py) — ligne 97 : `def enrich(base: pd.DataFrame, benchmark: pd.DataFrame, sessions: list[str], variance_floor=1e-12) -> pd.DataFrame`
- [run](../../modelFactory/fr_benchmark_features.py) — ligne 157 : `def run(config_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_benchmark_features.py) — ligne 254 : `def main() -> None`

## `modelFactory/fr_direction_h5_audit.py`

Source SHA-256 : `43e3a5123dd8f6eee9a43e557eb77590d4d4b54203917e856f03b7cf81d03124`

- [load_config](../../modelFactory/fr_direction_h5_audit.py) — ligne 24 : `def load_config(path: Path) -> dict`
- [rank_selection](../../modelFactory/fr_direction_h5_audit.py) — ligne 53 : `def rank_selection(frame: pd.DataFrame, column: str, fraction: float, seed: int, ascending: bool=False) -> pd.DataFrame`
- [safe_auc](../../modelFactory/fr_direction_h5_audit.py) — ligne 74 : `def safe_auc(target: pd.Series, scores: pd.Series) -> float | None`
- [evaluate](../../modelFactory/fr_direction_h5_audit.py) — ligne 78 : `def evaluate(pool: pd.DataFrame, column: str, cfg: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]`
- [verdict](../../modelFactory/fr_direction_h5_audit.py) — ligne 163 : `def verdict(results: list[dict], cfg: dict) -> dict`
- [run](../../modelFactory/fr_direction_h5_audit.py) — ligne 197 : `def run(path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_direction_h5_audit.py) — ligne 332 : `def main() -> None`

## `modelFactory/fr_direction_h5_shared.py`

Source SHA-256 : `f4876fe8703b140bcc404e267aa1d10d360ed6da441881215d520f00c7ff0d45`

- [load_config](../../modelFactory/fr_direction_h5_shared.py) — ligne 31 : `def load_config(path: Path) -> dict`
- [ternary_target](../../modelFactory/fr_direction_h5_shared.py) — ligne 75 : `def ternary_target(deciles: pd.Series) -> pd.Series`
- [causal_oracle_history](../../modelFactory/fr_direction_h5_shared.py) — ligne 86 : `def causal_oracle_history(predictions: pd.DataFrame, source_folds: list[dict], cfg: dict) -> pd.DataFrame`
- [support_for](../../modelFactory/fr_direction_h5_shared.py) — ligne 108 : `def support_for(frame: pd.DataFrame, phase: str, expected_sessions: int, cfg: dict) -> dict`
- [choose_champion](../../modelFactory/fr_direction_h5_shared.py) — ligne 138 : `def choose_champion(validation: dict) -> str`
- [probability_score](../../modelFactory/fr_direction_h5_shared.py) — ligne 144 : `def probability_score(model, features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]`
- [verdict](../../modelFactory/fr_direction_h5_shared.py) — ligne 153 : `def verdict(folds: list[dict], cfg: dict) -> dict`
- [run](../../modelFactory/fr_direction_h5_shared.py) — ligne 177 : `def run(path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_direction_h5_shared.py) — ligne 377 : `def main() -> None`

## `modelFactory/fr_economic_qualification_12a.py`

Source SHA-256 : `b68efdf392ad15082a9d7e87ae79da508caf0e6c6ac0a03ec448dac9df824517`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/fr_economic_references_11a.py`

Source SHA-256 : `9ecae2bae1af85f52b06cc2e6f967a1290421df749dc140f7dc16887bf274fa0`

- [run](../../modelFactory/fr_economic_references_11a.py) — ligne 18 : `def run(profile: Path, output: Path) -> dict`

## `modelFactory/fr_eodhd_euronext_sample_audit.py`

Source SHA-256 : `9222c1b345dc53624efde850743221d08528b004be7e60be769fa2b221dd45f4`

- [parse_reference](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 31 : `def parse_reference(html: str) -> dict`
- [choose_sample](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 59 : `def choose_sample() -> list[dict]`
- [compare_rows](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 73 : `def compare_rows(reference: dict, provider: dict) -> tuple[dict, list[dict]]`
- [fetch](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 122 : `def fetch(url: str, context, data: dict | None=None) -> bytes`
- [collect_one](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 130 : `def collect_one(candidate: dict, output: Path, context, *, start_requested: str='2024-10-03', end_requested: str='2026-10-02') -> dict`
- [run](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 171 : `def run(output: Path, sleep: float) -> dict`
- [recompute](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 211 : `def recompute(output: Path, name: str='header_checked') -> dict`
- [resume_failed](../../modelFactory/fr_eodhd_euronext_sample_audit.py) — ligne 243 : `def resume_failed(previous: Path, output: Path, sleep: float, attempts: int=2) -> dict`

## `modelFactory/fr_event_data_qualification_11b.py`

Source SHA-256 : `11afbde655f61ce27493cc934a0012cb03357761c968cef358ff7ab758ee46ca`

- [main](../../modelFactory/fr_event_data_qualification_11b.py) — ligne 9 : `def main()`

## `modelFactory/fr_event_direction_11c.py`

Source SHA-256 : `0b7916e2ffda5dafba16d6485d4ac0731978a7b723174f7ef26c9b4304f148e6`

- [main](../../modelFactory/fr_event_direction_11c.py) — ligne 8 : `def main()`

## `modelFactory/fr_execution_evidence_12c.py`

Source SHA-256 : `f915ede109f4fbafcffff4d6f3b56677e4f53282a53f158526f69f5f6938cd5f`

- [main](../../modelFactory/fr_execution_evidence_12c.py) — ligne 10 : `def main()`

## `modelFactory/fr_exploitable_scope_12e.py`

Source SHA-256 : `4f87ac7efa86864d9bbb1a9339e7ea50da19f7db450219aec26db4f80a38d135`

- [main](../../modelFactory/fr_exploitable_scope_12e.py) — ligne 9 : `def main()`

## `modelFactory/fr_feature_panel.py`

Source SHA-256 : `6adf701cb6fa32fb68e4166c94a26442ed269fde0dda4e6244c9dc1b28726552`

- [load_profile](../../modelFactory/fr_feature_panel.py) — ligne 70 : `def load_profile(path: Path) -> dict`
- [compute_symbol_features](../../modelFactory/fr_feature_panel.py) — ligne 102 : `def compute_symbol_features(bars: pd.DataFrame, sessions: list[date]) -> pd.DataFrame`
- [assemble_panel](../../modelFactory/fr_feature_panel.py) — ligne 151 : `def assemble_panel(candidates: pd.DataFrame, features: pd.DataFrame, identities: dict, session_times: dict, profile: dict) -> pd.DataFrame`
- [_coverage](../../modelFactory/fr_feature_panel.py) — ligne 185 : `def _coverage(frame: pd.DataFrame) -> dict`
- [build_panel](../../modelFactory/fr_feature_panel.py) — ligne 196 : `def build_panel(*, start: date, end: date, profile_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_feature_panel.py) — ligne 381 : `def main() -> None`

## `modelFactory/fr_feature_profile_freeze.py`

Source SHA-256 : `62f63025e508f45325e37fdb4d99dbe8e02b4589e9a91f0c1c9f5a1351bf3514`

- [load_policy](../../modelFactory/fr_feature_profile_freeze.py) — ligne 36 : `def load_policy(path: Path) -> dict`
- [qualify](../../modelFactory/fr_feature_profile_freeze.py) — ligne 64 : `def qualify(panel: pd.DataFrame, policy: dict, sessions: list[str]) -> tuple[pd.DataFrame, list[dict]]`
- [run](../../modelFactory/fr_feature_profile_freeze.py) — ligne 137 : `def run(policy_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_feature_profile_freeze.py) — ligne 199 : `def main() -> None`

## `modelFactory/fr_fold3_repair_audit.py`

Source SHA-256 : `fcb882b6ecc98f6557e1c2741bdf8c331e57db3cef9d3f584426f9eeefa23dd3`

- [window_blockers](../../modelFactory/fr_fold3_repair_audit.py) — ligne 26 : `def window_blockers(proofs: dict, symbol: str, days: list[str]) -> list[dict]`
- [probe_official](../../modelFactory/fr_fold3_repair_audit.py) — ligne 37 : `def probe_official(days: list[str]) -> list[dict]`
- [audit_bounds](../../modelFactory/fr_fold3_repair_audit.py) — ligne 66 : `def audit_bounds(folds: list[dict], fold_id: int, phase: str) -> dict`
- [run](../../modelFactory/fr_fold3_repair_audit.py) — ligne 75 : `def run(output_root: Path, probe: bool=False, fold_id: int=3, phase: str='train') -> dict`
- [main](../../modelFactory/fr_fold3_repair_audit.py) — ligne 191 : `def main()`

## `modelFactory/fr_fold7_confirmation.py`

Source SHA-256 : `01d4b94e325183c4fef54bbe4ed23e044ac4f3b3713090bef14b12254a5724f8`

- [run](../../modelFactory/fr_fold7_confirmation.py) — ligne 16 : `def run(rebuild: Path) -> dict`

## `modelFactory/fr_fold7_euronext_proofs.py`

Source SHA-256 : `cb473457ccf5fca2d3bfcc9dee83f2a2b8214c36aa95bb550d24240d3b3ee92a`

- [run](../../modelFactory/fr_fold7_euronext_proofs.py) — ligne 14 : `def run(requests_path: Path, output: Path) -> None`

## `modelFactory/fr_fold7_price_evidence_review.py`

Source SHA-256 : `93d0b87c52d039890a82b06eca5244a262108af755f600b916faec83c11af2f3`

- [comparison](../../modelFactory/fr_fold7_price_evidence_review.py) — ligne 14 : `def comparison(reference: dict | None, provider: dict | None) -> str`
- [run](../../modelFactory/fr_fold7_price_evidence_review.py) — ligne 24 : `def run(ledger_path: Path, collection: Path) -> dict`

## `modelFactory/fr_fold7_price_requests.py`

Source SHA-256 : `bea4c58cbffdf3956c343a3ca04d2c6d64e69667bfd49036a1bfb5f1f2a8ba66`

- [requested_pairs](../../modelFactory/fr_fold7_price_requests.py) — ligne 17 : `def requested_pairs(frame: pd.DataFrame) -> list[tuple[str, str]]`
- [run](../../modelFactory/fr_fold7_price_requests.py) — ligne 27 : `def run(diagnostics: Path, output: Path) -> dict`

## `modelFactory/fr_fold7_rebuild.py`

Source SHA-256 : `f4f63f1bcbf6d43be1e37f91bfb1aa775614259c97b0cd1c06017a5afb13fc21`

- [sha](../../modelFactory/fr_fold7_rebuild.py) — ligne 25 : `def sha(path: Path) -> str`
- [write_json](../../modelFactory/fr_fold7_rebuild.py) — ligne 33 : `def write_json(path: Path, value: dict) -> None`
- [verified_pairs](../../modelFactory/fr_fold7_rebuild.py) — ligne 38 : `def verified_pairs(ledger_path: Path, collection: Path) -> dict`
- [overlay_row](../../modelFactory/fr_fold7_rebuild.py) — ligne 77 : `def overlay_row(original: dict, proof: dict) -> dict`
- [build_overlay](../../modelFactory/fr_fold7_rebuild.py) — ligne 97 : `def build_overlay(output: Path, ledger: Path, collection: Path) -> dict`
- [run](../../modelFactory/fr_fold7_rebuild.py) — ligne 148 : `def run(output: Path) -> None`

## `modelFactory/fr_free_blocker_review.py`

Source SHA-256 : `b9f3dddd21100b0957974614df75259cd62d099a698b313b4a64242431c95f2a`

- [main](../../modelFactory/fr_free_blocker_review.py) — ligne 9 : `def main()`

## `modelFactory/fr_guidance_corpus_11d.py`

Source SHA-256 : `e48610fa676f7071d71658fcceebc65a6212f825afb0eee4be093c6c645ed04e`

- [main](../../modelFactory/fr_guidance_corpus_11d.py) — ligne 8 : `def main()`

## `modelFactory/fr_labels.py`

Source SHA-256 : `6eecf1c481ae12e8794cc802c2d9baaed08123c02b37756d225f9c5387aded6b`

- [load_config](../../modelFactory/fr_labels.py) — ligne 22 : `def load_config(path: Path) -> dict`
- [path_label](../../modelFactory/fr_labels.py) — ligne 55 : `def path_label(decision: str, horizon: int, sessions: list[str], bars: dict, admitted: dict, isin: str, cutoff: str) -> dict`
- [rank_labels](../../modelFactory/fr_labels.py) — ligne 107 : `def rank_labels(frame: pd.DataFrame, min_count=20, min_coverage=0.8, top_fraction=0.2) -> pd.DataFrame`
- [make_fold_plan](../../modelFactory/fr_labels.py) — ligne 145 : `def make_fold_plan(sessions: list[str], cfg: dict) -> list[dict]`
- [run](../../modelFactory/fr_labels.py) — ligne 174 : `def run(config_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_labels.py) — ligne 382 : `def main() -> None`

## `modelFactory/fr_labels_review.py`

Source SHA-256 : `b77d1f9fee513defa34161ce0ee434728293b85bd7544e69e8b13b5e46315d28`

- [join_panels](../../modelFactory/fr_labels_review.py) — ligne 21 : `def join_panels(labels: pd.DataFrame, price: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame`
- [phase_mask](../../modelFactory/fr_labels_review.py) — ligne 45 : `def phase_mask(frame: pd.DataFrame, fold: dict, phase: str, development_end: str) -> pd.Series`
- [fold_support](../../modelFactory/fr_labels_review.py) — ligne 59 : `def fold_support(frame: pd.DataFrame, folds: list[dict], sessions: list[str], cfg: dict) -> list[dict]`
- [choose_cases](../../modelFactory/fr_labels_review.py) — ligne 107 : `def choose_cases(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame`
- [read_payload](../../modelFactory/fr_labels_review.py) — ligne 128 : `def read_payload(archive: Path, metadata: dict, kind: str) -> tuple[list, str]`
- [review_cases](../../modelFactory/fr_labels_review.py) — ligne 138 : `def review_cases(selected: pd.DataFrame, archive: Path, sessions: list[str], cfg: dict) -> tuple[list, dict]`
- [run](../../modelFactory/fr_labels_review.py) — ligne 184 : `def run(config_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_labels_review.py) — ligne 271 : `def main() -> None`

## `modelFactory/fr_official_close_audit.py`

Source SHA-256 : `94854bfcf0c3c3913dd4f8d3a6892ecb9166305a63ab236c6dd9126d33338d5a`

- [read_closes](../../modelFactory/fr_official_close_audit.py) — ligne 23 : `def read_closes(path: Path) -> dict`
- [verdict](../../modelFactory/fr_official_close_audit.py) — ligne 53 : `def verdict(official: float | None, eodhd: float, yahoo: float, tolerance: float=0.0001) -> str`
- [run](../../modelFactory/fr_official_close_audit.py) — ligne 60 : `def run(workbook: Path, output: Path) -> dict`

## `modelFactory/fr_opening_evidence_overlay.py`

Source SHA-256 : `d024146710c32b1a117d1832a518ca69f9ebfc7ffbf6f9c4dfff6df3f6368de9`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/fr_oracle_h5_pilot.py`

Source SHA-256 : `e59e6c13d84225649037d0c9af49ecd5278ffe351c81a6c9c02256db164427d1`

- [load_config](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 30 : `def load_config(path: Path) -> dict`
- [deterministic_score](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 71 : `def deterministic_score(day: str, uid: str, seed: int) -> float`
- [feature_matrix](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 75 : `def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame`
- [select_phase](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 83 : `def select_phase(frame: pd.DataFrame, fold: dict, phase: str, cfg: dict) -> pd.DataFrame`
- [score_metrics](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 98 : `def score_metrics(frame: pd.DataFrame, score: np.ndarray, cfg: dict) -> tuple[dict, pd.DataFrame]`
- [choose_champion](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 144 : `def choose_champion(validation: dict) -> str`
- [verdict](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 149 : `def verdict(folds: list[dict], cfg: dict) -> dict`
- [run](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 196 : `def run(config_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_oracle_h5_pilot.py) — ligne 337 : `def main() -> None`

## `modelFactory/fr_oracle_oof_qualification.py`

Source SHA-256 : `447700c35dfa23217ad6284c22450bc08414226e09b65e934af6356b7cddc268`

- [rolling_folds](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 19 : `def rolling_folds(folds: list[dict], sessions: list[str], window: int) -> list[dict]`
- [complete_folds](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 31 : `def complete_folds(support: list[dict]) -> list[int]`
- [potential_history](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 44 : `def potential_history(frame: pd.DataFrame, folds: list[dict], admitted: list[int], cfg: dict) -> pd.DataFrame`
- [gap_details](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 66 : `def gap_details(frame: pd.DataFrame, folds: list[dict], sessions: list[str], cfg: dict) -> pd.DataFrame`
- [run](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 93 : `def run(config_path: Path, output_root: Path) -> dict`
- [main](../../modelFactory/fr_oracle_oof_qualification.py) — ligne 205 : `def main()`

## `modelFactory/fr_portfolio_replay_12b.py`

Source SHA-256 : `a47fa69152c2246e5dbf3d9785c890d6fe8abd491aad71332b9f2cd9357d5f8e`

- [write](../../modelFactory/fr_portfolio_replay_12b.py) — ligne 17 : `def write(path, payload)`
- [audit](../../modelFactory/fr_portfolio_replay_12b.py) — ligne 25 : `def audit(preflight: Path, qualification: Path, output: Path) -> dict`
- [main](../../modelFactory/fr_portfolio_replay_12b.py) — ligne 63 : `def main()`

## `modelFactory/fr_provider_exploratory_13b.py`

Source SHA-256 : `0b53228129c355903a9a2315a48216432f9cb5b3d7f96d51fe61b1f76404c4f2`

- [main](../../modelFactory/fr_provider_exploratory_13b.py) — ligne 7 : `def main()`

## `modelFactory/fr_public_evidence_requests.py`

Source SHA-256 : `41a86e998d9226e3615ac906a4f7e789fd5c355e055ab45d5d9b584d34cdca9d`

- [main](../../modelFactory/fr_public_evidence_requests.py) — ligne 10 : `def main()`

## `modelFactory/fr_tape_reporting_13b.py`

Source SHA-256 : `840b2c4263c34ff9b07250ff0ab7b9ccaf4cf9c565a11e09e68d09a4c6c1d441`

- [main](../../modelFactory/fr_tape_reporting_13b.py) — ligne 8 : `def main()`

## `modelFactory/fr_validation_protocol_13a.py`

Source SHA-256 : `a032db21b24c3448c942bda77949e1c1e04b77f8f67da4a55f3b2c417c806f26`

- [main](../../modelFactory/fr_validation_protocol_13a.py) — ligne 9 : `def main()`

## `modelFactory/fundamental_alpha_book.py`

Source SHA-256 : `5a527789e3e33977f6338c70aefd8032bb2ba6a13f694e7b47837bf78d055da2`

- [E19BConfig](../../modelFactory/fundamental_alpha_book.py) — ligne 65 : `class E19BConfig`
- [E19BConfig.__post_init__](../../modelFactory/fundamental_alpha_book.py) — ligne 94 : `def __post_init__(self) -> None`
- [E19BConfig.round_trip_cost](../../modelFactory/fundamental_alpha_book.py) — ligne 105 : `def round_trip_cost(self) -> float`
- [_numeric](../../modelFactory/fundamental_alpha_book.py) — ligne 109 : `def _numeric(frame: pd.DataFrame, column: str) -> pd.Series`
- [_cross_section_rank](../../modelFactory/fundamental_alpha_book.py) — ligne 115 : `def _cross_section_rank(values: pd.Series, dates: pd.Series, eligible: pd.Series, sign: int, config: E19BConfig) -> pd.Series`
- [_prepare_fundamental_snapshots](../../modelFactory/fundamental_alpha_book.py) — ligne 135 : `def _prepare_fundamental_snapshots(raw: pd.DataFrame) -> pd.DataFrame`
- [build_family_scores](../../modelFactory/fundamental_alpha_book.py) — ligne 156 : `def build_family_scores(panel: pd.DataFrame, config: E19BConfig) -> pd.DataFrame`
- [_standardize](../../modelFactory/fundamental_alpha_book.py) — ligne 182 : `def _standardize(values: pd.Series, dates: pd.Series, minimum: int) -> pd.Series`
- [add_neutralized_views](../../modelFactory/fundamental_alpha_book.py) — ligne 194 : `def add_neutralized_views(panel: pd.DataFrame, config: E19BConfig) -> pd.DataFrame`
- [build_walk_forward_folds](../../modelFactory/fundamental_alpha_book.py) — ligne 236 : `def build_walk_forward_folds(dates: Iterable[pd.Timestamp], config: E19BConfig) -> pd.DataFrame`
- [assign_oos_folds](../../modelFactory/fundamental_alpha_book.py) — ligne 258 : `def assign_oos_folds(panel: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame`
- [_safe_spearman](../../modelFactory/fundamental_alpha_book.py) — ligne 267 : `def _safe_spearman(group: pd.DataFrame, score: str, target: str) -> float`
- [_bootstrap](../../modelFactory/fundamental_alpha_book.py) — ligne 274 : `def _bootstrap(values: pd.Series, config: E19BConfig, horizon: int, salt: int) -> tuple[float, float]`
- [evaluate_alpha](../../modelFactory/fundamental_alpha_book.py) — ligne 286 : `def evaluate_alpha(panel: pd.DataFrame, alpha: str, view: str, horizon: int, config: E19BConfig) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [build_gates](../../modelFactory/fundamental_alpha_book.py) — ligne 374 : `def build_gates(results: dict[str, dict[str, Any]], config: E19BConfig) -> dict[str, Any]`
- [build_panel](../../modelFactory/fundamental_alpha_book.py) — ligne 409 : `def build_panel(engine: Any, symbols: list[str], config: E19BConfig) -> pd.DataFrame`
- [_neutrality_diagnostics](../../modelFactory/fundamental_alpha_book.py) — ligne 484 : `def _neutrality_diagnostics(panel: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/fundamental_alpha_book.py) — ligne 502 : `def run(*, symbol_source: str, output_root: Path, config: E19BConfig) -> Path`
- [main](../../modelFactory/fundamental_alpha_book.py) — ligne 584 : `def main() -> None`

## `modelFactory/fundamental_features.py`

Source SHA-256 : `2ba585a491d413d680c1c2e50a770d7cfc29bd786e59a681f431a85fb12bf9e6`

- [_normalized_source](../../modelFactory/fundamental_features.py) — ligne 138 : `def _normalized_source(value: Any) -> str`
- [_apply_availability_contract](../../modelFactory/fundamental_features.py) — ligne 142 : `def _apply_availability_contract(frame: pd.DataFrame) -> pd.DataFrame`
- [load_fundamentals_from_db](../../modelFactory/fundamental_features.py) — ligne 169 : `def load_fundamentals_from_db(symbols: list[str], start_date: str | pd.Timestamp, end_date: str | pd.Timestamp, *, engine=None) -> pd.DataFrame`
- [forward_fill_fundamentals](../../modelFactory/fundamental_features.py) — ligne 270 : `def forward_fill_fundamentals(fund_df: pd.DataFrame, date_range: pd.DatetimeIndex) -> pd.DataFrame`
- [derive_features](../../modelFactory/fundamental_features.py) — ligne 334 : `def derive_features(df: pd.DataFrame) -> pd.DataFrame`
- [merge_fundamentals](../../modelFactory/fundamental_features.py) — ligne 387 : `def merge_fundamentals(bars_df: pd.DataFrame, *, engine=None, fundamental_df: pd.DataFrame | None=None) -> pd.DataFrame`
- [fetch_and_store_fundamentals](../../modelFactory/fundamental_features.py) — ligne 472 : `def fetch_and_store_fundamentals(symbols: list[str], *, engine=None, session=None, provider: str='eodhd', start_date: str | None=None, end_date: str | None=None) -> dict[str, Any]`
- [_extract_quarterly_fundamentals](../../modelFactory/fundamental_features.py) — ligne 663 : `def _extract_quarterly_fundamentals(symbol: str, raw_payload: dict[str, Any]) -> list[dict[str, Any]]`
- [_get_prev_year_quarter](../../modelFactory/fundamental_features.py) — ligne 831 : `def _get_prev_year_quarter(quarter_date: str) -> str | None`
- [_fetch_fundamentals_record](../../modelFactory/fundamental_features.py) — ligne 843 : `def _fetch_fundamentals_record(symbol: str, *, provider: str='eodhd', session=None) -> dict[str, Any]`
- [_extract_eodhd_highlights](../../modelFactory/fundamental_features.py) — ligne 886 : `def _extract_eodhd_highlights(highlights: dict) -> dict[str, Any]`
- [_extract_eodhd_valuation](../../modelFactory/fundamental_features.py) — ligne 927 : `def _extract_eodhd_valuation(valuation: dict) -> dict[str, Any]`
- [_extract_eodhd_technicals](../../modelFactory/fundamental_features.py) — ligne 945 : `def _extract_eodhd_technicals(technicals: dict) -> dict[str, Any]`
- [_upsert_fundamentals_row](../../modelFactory/fundamental_features.py) — ligne 959 : `def _upsert_fundamentals_row(engine: Any, symbol: str, trade_date: Any, fetched_at: Any, record: dict[str, Any], source: str='EODHD') -> None`
- [_enrich_sec_with_market_ratios](../../modelFactory/fundamental_features.py) — ligne 1028 : `def _enrich_sec_with_market_ratios(symbol: str, min_date: Any, max_date: Any) -> None`
- [_resolve_cli_symbols](../../modelFactory/fundamental_features.py) — ligne 1064 : `def _resolve_cli_symbols(symbol_source: str, *, start_date: str | None=None, end_date: str | None=None) -> list[str]`
- [main](../../modelFactory/fundamental_features.py) — ligne 1115 : `def main() -> None`

## `modelFactory/fundamental_pit_availability_audit.py`

Source SHA-256 : `60c856eec624a678384ccd7a6768f0df0a42fbd4165e8ca3d5361bcb58f67df8`

- [E19AConfig](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 50 : `class E19AConfig`
- [next_market_session](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 63 : `def next_market_session(dates: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series`
- [load_fundamentals](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 77 : `def load_fundamentals(engine: Engine, symbols: list[str], *, end_date: str) -> pd.DataFrame`
- [reconstruct_daily_availability](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 114 : `def reconstruct_daily_availability(eligible_rows: pd.DataFrame, fundamentals: pd.DataFrame, calendar: pd.DatetimeIndex, config: E19AConfig) -> pd.DataFrame`
- [loader_contract_audit](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 160 : `def loader_contract_audit(table_columns: set[str]) -> dict[str, Any]`
- [summarize_source_rows](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 188 : `def summarize_source_rows(fundamentals: pd.DataFrame) -> list[dict[str, Any]]`
- [build_report](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 202 : `def build_report(*, symbols: list[str], eligible_rows: pd.DataFrame, fundamentals: pd.DataFrame, daily: pd.DataFrame, table_columns: set[str], duplicate_stats: dict[str, int], global_table_summary: dict[str, Any], config: E19AConfig) -> dict[str, Any]`
- [run](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 339 : `def run(*, symbol_source: str, source_panel: Path, output_root: Path, config: E19AConfig) -> Path`
- [main](../../modelFactory/fundamental_pit_availability_audit.py) — ligne 406 : `def main() -> None`

## `modelFactory/fundamental_value_confirmation.py`

Source SHA-256 : `57af7fdaf45c31b46aa9679d6554901e86d28f0f583064226164ea324bafff0a`

- [E19CConfig](../../modelFactory/fundamental_value_confirmation.py) — ligne 21 : `class E19CConfig`
- [E19CConfig.cost](../../modelFactory/fundamental_value_confirmation.py) — ligne 36 : `def cost(self) -> float`
- [file_sha256](../../modelFactory/fundamental_value_confirmation.py) — ligne 40 : `def file_sha256(path: Path) -> str`
- [hash_partition](../../modelFactory/fundamental_value_confirmation.py) — ligne 48 : `def hash_partition(symbol: str, partitions: int) -> int`
- [holdout_mask](../../modelFactory/fundamental_value_confirmation.py) — ligne 53 : `def holdout_mask(panel: pd.DataFrame, config: E19CConfig) -> pd.Series`
- [label_windows](../../modelFactory/fundamental_value_confirmation.py) — ligne 58 : `def label_windows(panel: pd.DataFrame, config: E19CConfig) -> pd.Series`
- [_bootstrap](../../modelFactory/fundamental_value_confirmation.py) — ligne 66 : `def _bootstrap(values: pd.Series, config: E19CConfig, horizon: int, salt: int) -> tuple[float, float]`
- [evaluate](../../modelFactory/fundamental_value_confirmation.py) — ligne 78 : `def evaluate(panel: pd.DataFrame, horizon: int, config: E19CConfig, *, partition: int | None=None) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]`
- [build_gates](../../modelFactory/fundamental_value_confirmation.py) — ligne 115 : `def build_gates(results: dict[str, Any], hashes: pd.DataFrame) -> dict[str, bool]`
- [run](../../modelFactory/fundamental_value_confirmation.py) — ligne 122 : `def run(e19b_dir: Path, output_root: Path, config: E19CConfig) -> Path`
- [main](../../modelFactory/fundamental_value_confirmation.py) — ligne 151 : `def main() -> None`

## `modelFactory/global_benchmark_runner.py`

Source SHA-256 : `35c39a1a64b006c94c614cd98708f6dc55a284490d54d25203ec92901818248b`

- [GlobalBenchmarkConfig](../../modelFactory/global_benchmark_runner.py) — ligne 45 : `class GlobalBenchmarkConfig`
- [GlobalBenchmarkReport](../../modelFactory/global_benchmark_runner.py) — ligne 69 : `class GlobalBenchmarkReport`
- [GlobalBenchmarkReport.to_dict](../../modelFactory/global_benchmark_runner.py) — ligne 105 : `def to_dict(self) -> dict[str, Any]`
- [GlobalBenchmarkRunner](../../modelFactory/global_benchmark_runner.py) — ligne 155 : `class GlobalBenchmarkRunner`
- [GlobalBenchmarkRunner.__init__](../../modelFactory/global_benchmark_runner.py) — ligne 181 : `def __init__(self, symbols: list[str], training_cfg: TrainingConfig, *, benchmark_cfg: GlobalBenchmarkConfig | None=None, engine: Any=None, data_provider: Any=None) -> None`
- [GlobalBenchmarkRunner.run](../../modelFactory/global_benchmark_runner.py) — ligne 217 : `def run(self) -> GlobalBenchmarkReport`
- [GlobalBenchmarkRunner._load_multi_symbol_data](../../modelFactory/global_benchmark_runner.py) — ligne 256 : `def _load_multi_symbol_data(self) -> pd.DataFrame | None`
- [GlobalBenchmarkRunner._compute_per_symbol_baselines](../../modelFactory/global_benchmark_runner.py) — ligne 280 : `def _compute_per_symbol_baselines(self, prepared_df: pd.DataFrame) -> dict[str, dict[str, SimpleBaselineResult]]`
- [GlobalBenchmarkRunner._aggregate_baselines](../../modelFactory/global_benchmark_runner.py) — ligne 319 : `def _aggregate_baselines(by_symbol: dict[str, dict[str, SimpleBaselineResult]]) -> dict[str, SimpleBaselineResult]`
- [GlobalBenchmarkRunner._run_global_challenger](../../modelFactory/global_benchmark_runner.py) — ligne 347 : `def _run_global_challenger(self, seed: int, baseline_threshold: float) -> ChallengerResult | None`
- [GlobalBenchmarkRunner._train_on_prepared_df](../../modelFactory/global_benchmark_runner.py) — ligne 482 : `def _train_on_prepared_df(self, df: pd.DataFrame, cfg: TrainingConfig, seed: int) -> dict[str, Any]`
- [GlobalBenchmarkRunner._select_champion](../../modelFactory/global_benchmark_runner.py) — ligne 597 : `def _select_champion(self, report: GlobalBenchmarkReport, baseline_threshold: float) -> GlobalBenchmarkReport`
- [GlobalBenchmarkRunner._build_summary](../../modelFactory/global_benchmark_runner.py) — ligne 621 : `def _build_summary(self, report: GlobalBenchmarkReport, baseline_threshold: float) -> dict[str, Any]`

## `modelFactory/global_direction/__init__.py`

Source SHA-256 : `a6743aa41a438817593f4d933cac4b897ce99afce8ab6c403973421afeb63477`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/global_direction/audit_scores.py`

Source SHA-256 : `2c1d6688682037d2366d8240e7f2ea580fd3333ce5da9bae7c24b26347a66cdb`

- [load_scores](../../modelFactory/global_direction/audit_scores.py) — ligne 51 : `def load_scores(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [load_bars_dates](../../modelFactory/global_direction/audit_scores.py) — ligne 68 : `def load_bars_dates(engine: Any, symbols: list[str], start_date: str, end_date: str) -> dict[str, np.ndarray]`
- [_pit_series](../../modelFactory/global_direction/audit_scores.py) — ligne 84 : `def _pit_series(snap_dates: np.ndarray, snap_values: np.ndarray, trading_days: np.ndarray) -> pd.Series`
- [audit_universe](../../modelFactory/global_direction/audit_scores.py) — ligne 93 : `def audit_universe(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [audit_pool_lags](../../modelFactory/global_direction/audit_scores.py) — ligne 139 : `def audit_pool_lags(pool: pd.DataFrame, scores: pd.DataFrame, calendars: dict[str, np.ndarray]) -> pd.DataFrame`
- [format_pool_report](../../modelFactory/global_direction/audit_scores.py) — ligne 220 : `def format_pool_report(lag_row: dict[str, Any]) -> str`
- [main](../../modelFactory/global_direction/audit_scores.py) — ligne 235 : `def main() -> None`

## `modelFactory/global_direction/conditioning.py`

Source SHA-256 : `1819cdc15575353cb19acc899bca051df4c8f1a9a8237811e50075a26538be92`

- [_ic_spearman](../../modelFactory/global_direction/conditioning.py) — ligne 52 : `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None`
- [_auc](../../modelFactory/global_direction/conditioning.py) — ligne 63 : `def _auc(series: pd.Series, decile: pd.Series, good: tuple=(6, 10), bad: tuple=(1, 5)) -> float | None`
- [_top_decile_stats](../../modelFactory/global_direction/conditioning.py) — ligne 72 : `def _top_decile_stats(sub: pd.DataFrame, feature: str) -> dict[str, float | None]`
- [measure_depth](../../modelFactory/global_direction/conditioning.py) — ligne 91 : `def measure_depth(pool: pd.DataFrame, panel: pd.DataFrame, base_features: list[str]) -> pd.DataFrame`
- [main](../../modelFactory/global_direction/conditioning.py) — ligne 143 : `def main() -> None`

## `modelFactory/global_direction/config.py`

Source SHA-256 : `cdcce0520a10385e1e018a01dab3528cea1db7e05d426930d99d684eee2527a2`

- [GlobalDirectionConfig](../../modelFactory/global_direction/config.py) — ligne 25 : `class GlobalDirectionConfig`
- [load_global_direction_config](../../modelFactory/global_direction/config.py) — ligne 35 : `def load_global_direction_config(path: Path | str=_CONFIG_PATH) -> GlobalDirectionConfig`
- [resolve_global_direction_batch_id](../../modelFactory/global_direction/config.py) — ligne 68 : `def resolve_global_direction_batch_id(path: Path | str=_CONFIG_PATH) -> str | None`

## `modelFactory/global_direction/dataset.py`

Source SHA-256 : `c659658599c769c3d4c6c89c17cab6c522be88574d0ba1c4fd5a2f4a7f6f0c62`

- [select_direction_features](../../modelFactory/global_direction/dataset.py) — ligne 94 : `def select_direction_features(available: list[str], mode: str='minimal') -> list[str]`
- [build_sector_features](../../modelFactory/global_direction/dataset.py) — ligne 130 : `def build_sector_features(engine: Any, symbols: list[str], *, start_date: str, end_date: str, base_cols: list[str]) -> tuple[pd.DataFrame, list[str]]`
- [gd_labels_from_oracle](../../modelFactory/global_direction/dataset.py) — ligne 192 : `def gd_labels_from_oracle(targets: pd.DataFrame, target_mode: str='binary') -> pd.DataFrame`
- [build_dataset](../../modelFactory/global_direction/dataset.py) — ligne 230 : `def build_dataset(engine: Any, batch_id: str, symbols: list[str], *, start_date: str, end_date: str, horizon: int=20, feature_mode: str='minimal', target_mode: str='binary') -> tuple[pd.DataFrame, list[str]]`

## `modelFactory/global_direction/pipeline.py`

Source SHA-256 : `248384148837883b65bbd368036099a66d4343ea4403723ec313ba17762354c0`

- [_latest_run](../../modelFactory/global_direction/pipeline.py) — ligne 52 : `def _latest_run(root: Path, prefix: str, tag_batch: str | None=None) -> Path | None`
- [load_run_oos](../../modelFactory/global_direction/pipeline.py) — ligne 67 : `def load_run_oos(run_dir: Path) -> pd.DataFrame`
- [load_b25_ranks](../../modelFactory/global_direction/pipeline.py) — ligne 74 : `def load_b25_ranks(engine: Any, batch_id: str) -> pd.DataFrame`
- [load_regime_map](../../modelFactory/global_direction/pipeline.py) — ligne 86 : `def load_regime_map(path: Path=_REGIME_FILE) -> dict[pd.Timestamp, str]`
- [build_pool](../../modelFactory/global_direction/pipeline.py) — ligne 119 : `def build_pool(combined: pd.DataFrame, pool_pct: float) -> pd.DataFrame`
- [select_top_m24](../../modelFactory/global_direction/pipeline.py) — ligne 127 : `def select_top_m24(pool: pd.DataFrame, score_col: str, m24: int) -> pd.DataFrame`
- [compute_metrics](../../modelFactory/global_direction/pipeline.py) — ligne 143 : `def compute_metrics(picks: pd.DataFrame, label: str='') -> dict[str, Any]`
- [quintile_gradient](../../modelFactory/global_direction/pipeline.py) — ligne 174 : `def quintile_gradient(pool: pd.DataFrame, score_col: str) -> pd.DataFrame`
- [fold_go_reproducibility](../../modelFactory/global_direction/pipeline.py) — ligne 196 : `def fold_go_reproducibility(pool: pd.DataFrame, score_col: str, key: str='fold_start') -> pd.DataFrame`
- [breakdown](../../modelFactory/global_direction/pipeline.py) — ligne 234 : `def breakdown(pool: pd.DataFrame, variant_picks: dict[str, pd.DataFrame], key: str) -> pd.DataFrame`
- [_fmt_metrics](../../modelFactory/global_direction/pipeline.py) — ligne 265 : `def _fmt_metrics(m: dict[str, Any]) -> str`
- [quintile_distribution](../../modelFactory/global_direction/pipeline.py) — ligne 274 : `def quintile_distribution(pool: pd.DataFrame, score_col: str) -> pd.DataFrame`
- [_dist_gradient_summary](../../modelFactory/global_direction/pipeline.py) — ligne 305 : `def _dist_gradient_summary(dist: pd.DataFrame) -> str`
- [_fmt_dist](../../modelFactory/global_direction/pipeline.py) — ligne 315 : `def _fmt_dist(dist: pd.DataFrame) -> str`
- [run_pipeline](../../modelFactory/global_direction/pipeline.py) — ligne 329 : `def run_pipeline(*, batch_id: str, gd_runs: dict[str, str] | str | None, oracle_run: str | None, pool_pct: float, m24: int) -> dict[str, Any]`
- [main](../../modelFactory/global_direction/pipeline.py) — ligne 480 : `def main() -> None`

## `modelFactory/global_direction/separability.py`

Source SHA-256 : `566ad55d8efaf93f355d0b9ed9e8808a59f94d48a2bb049465439d8402e3b8f4`

- [load_oracle_pool_proba](../../modelFactory/global_direction/separability.py) — ligne 49 : `def load_oracle_pool_proba(batch_id: str) -> pd.DataFrame`
- [build_pool_features](../../modelFactory/global_direction/separability.py) — ligne 67 : `def build_pool_features(engine: Any, batch_id: str, symbols: list[str], *, start_date: str, end_date: str, horizon: int=20, pool_pct: float=0.2) -> tuple[pd.DataFrame, list[str]]`
- [_ic_spearman](../../modelFactory/global_direction/separability.py) — ligne 116 : `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None`
- [_auc_bad_good](../../modelFactory/global_direction/separability.py) — ligne 127 : `def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 3), good=(8, 10)) -> float | None`
- [analyze_separability](../../modelFactory/global_direction/separability.py) — ligne 136 : `def analyze_separability(pool: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame`
- [format_report](../../modelFactory/global_direction/separability.py) — ligne 199 : `def format_report(df: pd.DataFrame, top_n: int=15) -> str`
- [main](../../modelFactory/global_direction/separability.py) — ligne 218 : `def main() -> None`

## `modelFactory/global_direction/temporal.py`

Source SHA-256 : `dcbc2602fd25294a3af86c2ce11584eaaac09b3ce262e9a561061ae88b66182e`

- [_temporal_columns](../../modelFactory/global_direction/temporal.py) — ligne 75 : `def _temporal_columns(base: str) -> list[str]`
- [_slope](../../modelFactory/global_direction/temporal.py) — ligne 88 : `def _slope(series: pd.Series, window: int) -> pd.Series`
- [load_bars_panel](../../modelFactory/global_direction/temporal.py) — ligne 95 : `def load_bars_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [load_score_panel](../../modelFactory/global_direction/temporal.py) — ligne 113 : `def load_score_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [_score_history_columns](../../modelFactory/global_direction/temporal.py) — ligne 140 : `def _score_history_columns(engine: Any) -> list[str]`
- [load_sector_panel](../../modelFactory/global_direction/temporal.py) — ligne 148 : `def load_sector_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> tuple[pd.DataFrame, list[str]]`
- [build_panel](../../modelFactory/global_direction/temporal.py) — ligne 168 : `def build_panel(engine: Any, symbols: list[str], start_date: str, end_date: str, *, with_derivations: bool=True) -> tuple[pd.DataFrame, list[str], dict[str, Any]]`
- [_ic_spearman](../../modelFactory/global_direction/temporal.py) — ligne 290 : `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None`
- [_auc](../../modelFactory/global_direction/temporal.py) — ligne 301 : `def _auc(series: pd.Series, decile: pd.Series, good: tuple=(6, 10), bad: tuple=(1, 5)) -> float | None`
- [_auc_d1_d10](../../modelFactory/global_direction/temporal.py) — ligne 310 : `def _auc_d1_d10(series: pd.Series, decile: pd.Series) -> float | None`
- [_auc_amplitude](../../modelFactory/global_direction/temporal.py) — ligne 314 : `def _auc_amplitude(series: pd.Series, decile: pd.Series) -> float | None`
- [run_separability](../../modelFactory/global_direction/temporal.py) — ligne 323 : `def run_separability(pool: pd.DataFrame, base_features: list[str], temporal_cols: list[str]) -> pd.DataFrame`
- [format_report](../../modelFactory/global_direction/temporal.py) — ligne 419 : `def format_report(out: pd.DataFrame, base_features: list[str]) -> str`
- [main](../../modelFactory/global_direction/temporal.py) — ligne 439 : `def main() -> None`

## `modelFactory/global_direction/walk_forward.py`

Source SHA-256 : `2b295976be3c498405922ab93fadc77ec63c887afb92037026c1585f2b5d9fd2`

- [_train_lightgbm_multiclass](../../modelFactory/global_direction/walk_forward.py) — ligne 51 : `def _train_lightgbm_multiclass(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=400) -> Any`
- [_train_lightgbm_regression](../../modelFactory/global_direction/walk_forward.py) — ligne 87 : `def _train_lightgbm_regression(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=400) -> Any`
- [_auc_d10_vs_d1](../../modelFactory/global_direction/walk_forward.py) — ligne 122 : `def _auc_d10_vs_d1(oos: pd.DataFrame) -> float | None`
- [run_walk_forward](../../modelFactory/global_direction/walk_forward.py) — ligne 132 : `def run_walk_forward(dataset: pd.DataFrame, feature_columns: list[str], *, test_windows: list[tuple[str, str]]=DEFAULT_TEST_WINDOWS, target_mode: str='binary') -> dict[str, Any]`
- [persist_oos](../../modelFactory/global_direction/walk_forward.py) — ligne 233 : `def persist_oos(oos: pd.DataFrame, run_id: str, batch_id: str | None=None) -> Path`
- [format_report](../../modelFactory/global_direction/walk_forward.py) — ligne 248 : `def format_report(result: dict[str, Any]) -> str`
- [main](../../modelFactory/global_direction/walk_forward.py) — ligne 277 : `def main() -> None`

## `modelFactory/global_model.py`

Source SHA-256 : `ba87feeb80fd5f5259cf7425d8f8ab155fe34cda983c2aad6db3834c1836e266`

- [_get_global_feature_columns](../../modelFactory/global_model.py) — ligne 61 : `def _get_global_feature_columns(cfg: TrainingConfig) -> list[str]`
- [_import_lightgbm](../../modelFactory/global_model.py) — ligne 102 : `def _import_lightgbm() -> Any`
- [_import_catboost](../../modelFactory/global_model.py) — ligne 108 : `def _import_catboost() -> Any`
- [_prepare_global_symbol_frame](../../modelFactory/global_model.py) — ligne 114 : `def _prepare_global_symbol_frame(bars_df: pd.DataFrame, *, cfg: TrainingConfig, benchmark_df: pd.DataFrame | None, sentiment_df: pd.DataFrame | None, cross_sectional_df: pd.DataFrame | None, selector_df: pd.DataFrame | None) -> pd.DataFrame`
- [_split_global_by_dates](../../modelFactory/global_model.py) — ligne 166 : `def _split_global_by_dates(df: pd.DataFrame, *, train_ratio: float, val_ratio: float, forecast_horizon: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [_build_global_estimator](../../modelFactory/global_model.py) — ligne 182 : `def _build_global_estimator(cfg: TrainingConfig, *, resolved_seed: int) -> tuple[str, Any]`
- [_compute_by_symbol_metrics](../../modelFactory/global_model.py) — ligne 261 : `def _compute_by_symbol_metrics(df: pd.DataFrame, probabilities: np.ndarray, *, decision_threshold: float, partition_name: str='test') -> dict[str, dict[str, Any]]`
- [_aggregate_wf_per_symbol_metrics](../../modelFactory/global_model.py) — ligne 305 : `def _aggregate_wf_per_symbol_metrics(fold_metrics_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]`
- [train_global_model](../../modelFactory/global_model.py) — ligne 358 : `def train_global_model(symbols: list[str], cfg: TrainingConfig, *, artifacts_dir: Path, engine: Any) -> dict[str, Any]`
- [train_global_model_wf](../../modelFactory/global_model.py) — ligne 726 : `def train_global_model_wf(symbols: list[str], cfg: TrainingConfig, *, artifacts_dir: Path, engine: Any) -> dict[str, Any]`

## `modelFactory/global_ranking.py`

Source SHA-256 : `ba80d380c13c3da12e86da3ef902519f23616a20280d44c2e32b90b09eb4ce33`

- [_classify_sector_group](../../modelFactory/global_ranking.py) — ligne 83 : `def _classify_sector_group(sector: str) -> str`
- [_xs_rank_column_name](../../modelFactory/global_ranking.py) — ligne 130 : `def _xs_rank_column_name(source_col: str) -> str`
- [_directional_features_subset](../../modelFactory/global_ranking.py) — ligne 134 : `def _directional_features_subset() -> list[str] | None`
- [_compute_sector_neutral_inplace](../../modelFactory/global_ranking.py) — ligne 149 : `def _compute_sector_neutral_inplace(df: pd.DataFrame, feature_columns: list[str], engine: Any) -> int`
- [_prepare_global_ranking_frame](../../modelFactory/global_ranking.py) — ligne 243 : `def _prepare_global_ranking_frame(bars_df: pd.DataFrame, cfg: TrainingConfig, *, benchmark_df: pd.DataFrame | None=None, sentiment_df: pd.DataFrame | None=None, selector_df: pd.DataFrame | None=None, cross_sectional_df: pd.DataFrame | None=None, symbol: str | None=None) -> pd.DataFrame`
- [_get_ranking_feature_columns](../../modelFactory/global_ranking.py) — ligne 284 : `def _get_ranking_feature_columns(cfg: TrainingConfig) -> list[str]`
- [compute_ic_rank](../../modelFactory/global_ranking.py) — ligne 417 : `def compute_ic_rank(predicted: np.ndarray, actual: np.ndarray) -> float | None`
- [compute_cross_sectional_ic](../../modelFactory/global_ranking.py) — ligne 440 : `def compute_cross_sectional_ic(pred_df: pd.DataFrame, *, score_col: str='proba_long', return_col: str='future_return', date_col: str='date', vol_col: str | None='rolling_volatility_20', min_symbols_per_date: int=10) -> dict[str, Any]`
- [_compute_mean_importance](../../modelFactory/global_ranking.py) — ligne 500 : `def _compute_mean_importance(split_importances: list[dict[str, float]], feature_names: list[str]) -> dict[str, float]`
- [_compute_decile_spread](../../modelFactory/global_ranking.py) — ligne 515 : `def _compute_decile_spread(pred_df: pd.DataFrame, *, score_col: str='predicted_score', return_col: str='actual_return', n_deciles: int=10) -> dict[str, float]`
- [_import_lightgbm](../../modelFactory/global_ranking.py) — ligne 568 : `def _import_lightgbm() -> Any`
- [_import_xgboost](../../modelFactory/global_ranking.py) — ligne 573 : `def _import_xgboost() -> Any`
- [_import_catboost](../../modelFactory/global_ranking.py) — ligne 578 : `def _import_catboost(as_ranker: bool=False) -> Any`
- [_build_ranking_estimator](../../modelFactory/global_ranking.py) — ligne 586 : `def _build_ranking_estimator(cfg: TrainingConfig, *, resolved_seed: int) -> tuple[str, Any]`
- [_build_ranking_estimators](../../modelFactory/global_ranking.py) — ligne 595 : `def _build_ranking_estimators(cfg: TrainingConfig, *, resolved_seed: int, model_names: list[str] | None=None) -> list[tuple[str, Any]]`
- [_compute_ranking_targets](../../modelFactory/global_ranking.py) — ligne 687 : `def _compute_ranking_targets(df: pd.DataFrame, *, horizons: tuple[int, ...], smoothing_horizons: tuple[int, ...], factor_cols: list[str], sector_map: dict[str, str] | None=None, raw_target: bool=False) -> pd.DataFrame`
- [train_global_ranking_wf](../../modelFactory/global_ranking.py) — ligne 831 : `def train_global_ranking_wf(symbols: list[str], cfg: TrainingConfig, *, artifacts_dir: Path, engine: Any) -> dict[str, Any]`
- [predict_global_rank](../../modelFactory/global_ranking.py) — ligne 1934 : `def predict_global_rank(universe_df: pd.DataFrame, artifacts_dir: Path, *, benchmark_df: pd.DataFrame | None=None, engine: Any | None=None) -> pd.DataFrame | None`

## `modelFactory/labeling.py`

Source SHA-256 : `8b39e90a5701bc349a9bcf1aeda2fc22def80e8d9be3586c44a10059a3f07cce`

- [TripleBarrierConfig](../../modelFactory/labeling.py) — ligne 48 : `class TripleBarrierConfig`
- [TripleBarrierConfig.__post_init__](../../modelFactory/labeling.py) — ligne 90 : `def __post_init__(self) -> None`
- [TripleBarrierConfig.total_cost_bps](../../modelFactory/labeling.py) — ligne 105 : `def total_cost_bps(self) -> float`
- [TripleBarrierConfig.cost_pct](../../modelFactory/labeling.py) — ligne 110 : `def cost_pct(self) -> float`
- [TripleBarrierLabel](../../modelFactory/labeling.py) — ligne 116 : `class TripleBarrierLabel`
- [_compute_atr](../../modelFactory/labeling.py) — ligne 163 : `def _compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int=14) -> np.ndarray`
- [_deduct_costs](../../modelFactory/labeling.py) — ligne 188 : `def _deduct_costs(gross_return: float, cfg: TripleBarrierConfig, *, holding_sessions: int=1) -> float`
- [_resolve_exit](../../modelFactory/labeling.py) — ligne 206 : `def _resolve_exit(*, entry_price: float, side: str, stop_price: float, tp_price: float, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, opens: np.ndarray, max_sessions: int, start_idx: int) -> dict`
- [build_triple_barrier_label](../../modelFactory/labeling.py) — ligne 325 : `def build_triple_barrier_label(*, entry_idx: int, side: str, prices: dict, cfg: TripleBarrierConfig) -> TripleBarrierLabel`
- [build_triple_barrier_labels](../../modelFactory/labeling.py) — ligne 435 : `def build_triple_barrier_labels(df_ohlc: pd.DataFrame, cfg: TripleBarrierConfig, *, side: str='long', signal_column: str | None=None) -> pd.DataFrame`
- [build_triple_barrier_targets](../../modelFactory/labeling.py) — ligne 518 : `def build_triple_barrier_targets(df_ohlc: pd.DataFrame, cfg: TripleBarrierConfig) -> pd.DataFrame`
- [compare_label_methods](../../modelFactory/labeling.py) — ligne 547 : `def compare_label_methods(df_ohlc: pd.DataFrame, cfg: TripleBarrierConfig, *, fixed_horizon: int=10, fixed_up_threshold: float=0.02, fixed_down_threshold: float=-0.02) -> dict`

## `modelFactory/lightgbm_baseline.py`

Source SHA-256 : `1d61c9608440a36bd3e9a2b31da11a048214660c30cf9450ed268d0db287c9a0`

- [_import_lightgbm](../../modelFactory/lightgbm_baseline.py) — ligne 16 : `def _import_lightgbm() -> Any`
- [run_lightgbm_baseline](../../modelFactory/lightgbm_baseline.py) — ligne 22 : `def run_lightgbm_baseline(prepared_df: pd.DataFrame, cfg: TrainingConfig, *, artifact_dir: Path | None=None, ternary_policy: 'TernaryDecisionPolicy | None'=None) -> dict[str, Any]`

## `modelFactory/liquidity_filter.py`

Source SHA-256 : `c4e6c141496bde349c18fb4bd8ea800c4cf7f474c485a604bda0e397b2ed3f47`

- [filter_symbols_by_liquidity](../../modelFactory/liquidity_filter.py) — ligne 104 : `def filter_symbols_by_liquidity(engine: Engine, symbols: list[str], *, end_date: date | None=None, min_avg_volume_20d: int=DEFAULT_MIN_AVG_VOLUME_20D, min_market_cap: float=DEFAULT_MIN_MARKET_CAP, max_market_cap: float=DEFAULT_MAX_MARKET_CAP, max_avg_high_low_range_pct: float=DEFAULT_MAX_AVG_HIGH_LOW_RANGE_PCT, min_daily_dollar_volume: float=DEFAULT_MIN_DAILY_DOLLAR_VOLUME, min_price: float=DEFAULT_MIN_PRICE, min_days: int=10, max_spread_bps: float=DEFAULT_MAX_SPREAD_BPS, spread_fallback_mode: str=DEFAULT_SPREAD_FALLBACK_MODE, spread_max_quote_age_days: int=DEFAULT_SPREAD_MAX_QUOTE_AGE_DAYS) -> tuple[list[str], dict[str, Any]]`
- [_apply_spread_filter](../../modelFactory/liquidity_filter.py) — ligne 324 : `def _apply_spread_filter(engine: Engine, symbols: list[str], already_filtered: dict[str, str], *, end_date: date, max_spread_bps: float, fallback_mode: str, max_quote_age_days: int) -> dict[str, Any]`

## `modelFactory/lstm_benchmark_adapter.py`

Source SHA-256 : `f506e9311f0eff3cc0a585a1d652ea45713572b2933a1331708c9c1ed1d52228`

- [_build_sequences](../../modelFactory/lstm_benchmark_adapter.py) — ligne 58 : `def _build_sequences(df: pd.DataFrame, feature_cols: list[str], seq_len: int, target_col: str='target') -> tuple[np.ndarray, np.ndarray]`
- [_validate_target_distribution](../../modelFactory/lstm_benchmark_adapter.py) — ligne 84 : `def _validate_target_distribution(y_train: np.ndarray, y_val: np.ndarray) -> dict[str, object]`
- [run_lstm_benchmark](../../modelFactory/lstm_benchmark_adapter.py) — ligne 97 : `def run_lstm_benchmark(prepared_df: pd.DataFrame, cfg: Any, *, seq_len: int=DEFAULT_SEQ_LEN, batch_size: int=DEFAULT_BATCH_SIZE, max_epochs: int=DEFAULT_MAX_EPOCHS, patience: int=DEFAULT_PATIENCE, hidden_size: int=DEFAULT_HIDDEN_SIZE, num_layers: int=DEFAULT_NUM_LAYERS, dropout: float=DEFAULT_DROPOUT, learning_rate: float=DEFAULT_LEARNING_RATE, artifact_dir: Path | None=None) -> dict[str, Any]`

## `modelFactory/meta_oracle.py`

Source SHA-256 : `51a5ccd6cb68ce5fd01346ed424f949a9f8a7ff18fda3cd6311923dd5ac1a5df`

- [MetaConfig](../../modelFactory/meta_oracle.py) — ligne 30 : `class MetaConfig`
- [assemble](../../modelFactory/meta_oracle.py) — ligne 41 : `def assemble(gate: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame`
- [training_rows](../../modelFactory/meta_oracle.py) — ligne 59 : `def training_rows(panel, train_dates, test_start)`
- [keep_quota](../../modelFactory/meta_oracle.py) — ligne 63 : `def keep_quota(panel: pd.DataFrame, score: str, quotas: pd.Series) -> pd.DataFrame`
- [precision](../../modelFactory/meta_oracle.py) — ligne 70 : `def precision(frame)`
- [bootstrap_delta](../../modelFactory/meta_oracle.py) — ligne 74 : `def bootstrap_delta(values, config)`
- [evaluate](../../modelFactory/meta_oracle.py) — ligne 89 : `def evaluate(panel, feature_columns, config)`
- [selection_policies](../../modelFactory/meta_oracle.py) — ligne 170 : `def selection_policies(scored)`
- [oracle_band_ids](../../modelFactory/meta_oracle.py) — ligne 182 : `def oracle_band_ids(percentiles)`
- [oracle_band_diagnostics](../../modelFactory/meta_oracle.py) — ligne 191 : `def oracle_band_diagnostics(scored)`
- [refresh_oracle_bands](../../modelFactory/meta_oracle.py) — ligne 207 : `def refresh_oracle_bands(run_path)`
- [report_selections](../../modelFactory/meta_oracle.py) — ligne 224 : `def report_selections(scored, config)`
- [decide](../../modelFactory/meta_oracle.py) — ligne 263 : `def decide(comparisons, periods, buckets, stage)`
- [main](../../modelFactory/meta_oracle.py) — ligne 285 : `def main()`

## `modelFactory/model.py`

Source SHA-256 : `da38ef718153761b43d3bcabc822910643647f9a56af197fd40ecbe7125e8ebb`

- [TemporalAttention](../../modelFactory/model.py) — ligne 24 : `class TemporalAttention(nn.Module)`
- [TemporalAttention.__init__](../../modelFactory/model.py) — ligne 27 : `def __init__(self, hidden_size: int) -> None`
- [TemporalAttention.forward](../../modelFactory/model.py) — ligne 31 : `def forward(self, lstm_out: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]`
- [LSTMAttentionClassifier](../../modelFactory/model.py) — ligne 49 : `class LSTMAttentionClassifier(nn.Module)`
- [LSTMAttentionClassifier.__init__](../../modelFactory/model.py) — ligne 56 : `def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float, num_classes: int=2) -> None`
- [LSTMAttentionClassifier.forward](../../modelFactory/model.py) — ligne 70 : `def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]`
- [LSTMAttentionModule](../../modelFactory/model.py) — ligne 89 : `class LSTMAttentionModule(L.LightningModule)`
- [LSTMAttentionModule.__init__](../../modelFactory/model.py) — ligne 96 : `def __init__(self, input_size: int, hidden_size: int=128, num_layers: int=2, dropout: float=0.3, learning_rate: float=0.001, weight_decay: float=1e-05, num_classes: int=2, ternary_weight_short: float=1.0, ternary_weight_flat: float=1.5, ternary_weight_long: float=1.0) -> None`
- [LSTMAttentionModule.forward](../../modelFactory/model.py) — ligne 174 : `def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]`
- [LSTMAttentionModule._shared_step](../../modelFactory/model.py) — ligne 177 : `def _shared_step(self, batch: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]`
- [LSTMAttentionModule.training_step](../../modelFactory/model.py) — ligne 201 : `def training_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> torch.Tensor`
- [LSTMAttentionModule.validation_step](../../modelFactory/model.py) — ligne 213 : `def validation_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None`
- [LSTMAttentionModule.test_step](../../modelFactory/model.py) — ligne 242 : `def test_step(self, batch: tuple[torch.Tensor, torch.Tensor], batch_idx: int) -> None`
- [LSTMAttentionModule.configure_optimizers](../../modelFactory/model.py) — ligne 268 : `def configure_optimizers(self) -> torch.optim.Optimizer`

## `modelFactory/model_benchmark.py`

Source SHA-256 : `a9d05a8cd60d1e507f0749044c1ddf319738e72c4ddb6c1b3e17d869138fb304`

- [SimpleBaselineResult](../../modelFactory/model_benchmark.py) — ligne 43 : `class SimpleBaselineResult`
- [SimpleBaselines](../../modelFactory/model_benchmark.py) — ligne 56 : `class SimpleBaselines`
- [SimpleBaselines.always_flat](../../modelFactory/model_benchmark.py) — ligne 70 : `def always_flat(y_train: np.ndarray, y_val: np.ndarray) -> SimpleBaselineResult`
- [SimpleBaselines.momentum](../../modelFactory/model_benchmark.py) — ligne 85 : `def momentum(returns_train: np.ndarray, returns_val: np.ndarray, y_train: np.ndarray, y_val: np.ndarray, *, lookback: int=20) -> SimpleBaselineResult`
- [SimpleBaselines.mean_reversion](../../modelFactory/model_benchmark.py) — ligne 122 : `def mean_reversion(returns_train: np.ndarray, returns_val: np.ndarray, y_train: np.ndarray, y_val: np.ndarray, *, lookback: int=20) -> SimpleBaselineResult`
- [SimpleBaselines.logistic](../../modelFactory/model_benchmark.py) — ligne 152 : `def logistic(X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray, *, is_ternary: bool=False) -> SimpleBaselineResult`
- [BenchmarkConfig](../../modelFactory/model_benchmark.py) — ligne 214 : `class BenchmarkConfig`
- [ChallengerResult](../../modelFactory/model_benchmark.py) — ligne 230 : `class ChallengerResult`
- [BenchmarkReport](../../modelFactory/model_benchmark.py) — ligne 249 : `class BenchmarkReport`
- [BenchmarkReport.to_dict](../../modelFactory/model_benchmark.py) — ligne 273 : `def to_dict(self) -> dict[str, Any]`
- [BenchmarkRunner](../../modelFactory/model_benchmark.py) — ligne 316 : `class BenchmarkRunner`
- [BenchmarkRunner.__init__](../../modelFactory/model_benchmark.py) — ligne 338 : `def __init__(self, prepared_df: pd.DataFrame, training_cfg: TrainingConfig, *, benchmark_cfg: BenchmarkConfig | None=None) -> None`
- [BenchmarkRunner.run](../../modelFactory/model_benchmark.py) — ligne 352 : `def run(self) -> BenchmarkReport`
- [BenchmarkRunner._resolve_symbol](../../modelFactory/model_benchmark.py) — ligne 406 : `def _resolve_symbol(self) -> str`
- [BenchmarkRunner._get_feature_columns](../../modelFactory/model_benchmark.py) — ligne 411 : `def _get_feature_columns(self) -> list[str]`
- [BenchmarkRunner._run_challenger](../../modelFactory/model_benchmark.py) — ligne 429 : `def _run_challenger(self, model_name: str, seed: int, df: pd.DataFrame, report: BenchmarkReport, baseline_threshold: float) -> None`
- [BenchmarkRunner._select_champion](../../modelFactory/model_benchmark.py) — ligne 600 : `def _select_champion(self, report: BenchmarkReport, baseline_threshold: float) -> BenchmarkReport`
- [BenchmarkRunner._build_summary](../../modelFactory/model_benchmark.py) — ligne 624 : `def _build_summary(self, report: BenchmarkReport, baseline_threshold: float) -> dict[str, Any]`
- [run_model_benchmark](../../modelFactory/model_benchmark.py) — ligne 664 : `def run_model_benchmark(prepared_df: pd.DataFrame, training_cfg: TrainingConfig, *, n_seeds: int=3, base_seed: int=42) -> BenchmarkReport`
- [_count_lightgbm_leaves](../../modelFactory/model_benchmark.py) — ligne 697 : `def _count_lightgbm_leaves(dump: dict[str, Any]) -> int`
- [_count_leaves_recursive](../../modelFactory/model_benchmark.py) — ligne 710 : `def _count_leaves_recursive(node: dict[str, Any]) -> int`
- [persist_benchmark_report](../../modelFactory/model_benchmark.py) — ligne 726 : `def persist_benchmark_report(report: BenchmarkReport, *, artifact_dir: Path | str | None=None) -> Path`
- [load_benchmark_report](../../modelFactory/model_benchmark.py) — ligne 768 : `def load_benchmark_report(path: Path | str) -> dict[str, Any]`
- [BenchmarkQualityReport](../../modelFactory/model_benchmark.py) — ligne 787 : `class BenchmarkQualityReport`
- [validate_benchmark_quality](../../modelFactory/model_benchmark.py) — ligne 799 : `def validate_benchmark_quality(report: BenchmarkReport, *, min_improvement_vs_baseline: float=0.01, max_latency_ms: float=60000, max_f1_std_across_seeds: float=0.1) -> BenchmarkQualityReport`

## `modelFactory/multi_horizon_oracle_rolling.py`

Source SHA-256 : `0bacdc48673fa3882b0887b2a61da4775ad1671fee31ee59c3c0349537f5d975`

- [RollingConfig](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 34 : `class RollingConfig`
- [RollingConfig.__post_init__](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 43 : `def __post_init__(self) -> None`
- [RollingConfig.round_trip_cost](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 50 : `def round_trip_cost(self) -> float`
- [read_universe](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 54 : `def read_universe(path: Path) -> list[str]`
- [file_sha256](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 62 : `def file_sha256(path: Path) -> str`
- [validate_batch_horizons](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 70 : `def validate_batch_horizons(batch_ids: dict[int, str], artifacts_root: Path) -> None`
- [_profile_contract](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 81 : `def _profile_contract(batch_id: str, artifacts_root: Path) -> dict[str, Any] | None`
- [audit_profile_contracts](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 94 : `def audit_profile_contracts(batch_ids: dict[int, str], artifacts_root: Path) -> dict[str, Any]`
- [_prepare_prediction](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 108 : `def _prepare_prediction(frame: pd.DataFrame, horizon: int, symbols: set[str]) -> pd.DataFrame`
- [align_predictions](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 126 : `def align_predictions(frames: dict[int, pd.DataFrame], symbols: Iterable[str]) -> tuple[pd.DataFrame, dict[str, Any]]`
- [score_correlations](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 173 : `def score_correlations(aligned: pd.DataFrame) -> pd.DataFrame`
- [selection_overlaps](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 177 : `def selection_overlaps(aligned: pd.DataFrame) -> pd.DataFrame`
- [build_price_panel](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 191 : `def build_price_panel(bars: pd.DataFrame) -> pd.DataFrame`
- [attach_paths](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 222 : `def attach_paths(aligned: pd.DataFrame, prices: pd.DataFrame, round_trip_cost: float) -> pd.DataFrame`
- [attach_benchmark_paths](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 258 : `def attach_benchmark_paths(events: pd.DataFrame, benchmark_prices: pd.DataFrame) -> pd.DataFrame`
- [deduplicate_entries](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 281 : `def deduplicate_entries(events: pd.DataFrame, variant: str) -> pd.DataFrame`
- [_price_group](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 298 : `def _price_group(values: pd.Series, strong: float) -> pd.Series`
- [block_bootstrap_mean](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 304 : `def block_bootstrap_mean(values_by_date: pd.Series, config: RollingConfig) -> tuple[float, float]`
- [build_event_study](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 319 : `def build_event_study(events: pd.DataFrame, config: RollingConfig) -> pd.DataFrame`
- [build_selection_control](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 353 : `def build_selection_control(events: pd.DataFrame, config: RollingConfig) -> pd.DataFrame`
- [build_s6_ls](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 384 : `def build_s6_ls(events: pd.DataFrame, config: RollingConfig) -> tuple[pd.DataFrame, dict[str, Any]]`
- [_rolling_winner_delta](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 408 : `def _rolling_winner_delta(events: pd.DataFrame, variant: str, config: RollingConfig) -> dict[str, Any]`
- [evaluate_verdict](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 437 : `def evaluate_verdict(event_study: pd.DataFrame, events: pd.DataFrame, config: RollingConfig) -> dict[str, Any]`
- [_markdown_report](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 501 : `def _markdown_report(report: dict[str, Any]) -> str`
- [run](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 519 : `def run(*, engine: Any, batch_ids: dict[int, str], universe_file: Path, start_date: str, end_date: str, artifacts_root: Path, output_root: Path, config: RollingConfig) -> Path`
- [main](../../modelFactory/multi_horizon_oracle_rolling.py) — ligne 588 : `def main() -> None`

## `modelFactory/nyse_auction_history_poc.py`

Source SHA-256 : `f9a4b8f46838df65eadf782f7d4dc686eb39aee7f01b51567af4d68f516f2681`

- [NyseRateLimitError](../../modelFactory/nyse_auction_history_poc.py) — ligne 38 : `class NyseRateLimitError(RuntimeError)`
- [_request_json](../../modelFactory/nyse_auction_history_poc.py) — ligne 44 : `def _request_json(session: requests.Session, path: str, params: dict[str, str], attempts: int=4) -> Any`
- [_hash_payload](../../modelFactory/nyse_auction_history_poc.py) — ligne 82 : `def _hash_payload(payload: Any) -> str`
- [_parse_symbols](../../modelFactory/nyse_auction_history_poc.py) — ligne 87 : `def _parse_symbols(value: str) -> list[str]`
- [_candidate_dates](../../modelFactory/nyse_auction_history_poc.py) — ligne 96 : `def _candidate_dates(start: date, end: date, limit: int) -> list[date]`
- [_resolve_input_symbols](../../modelFactory/nyse_auction_history_poc.py) — ligne 106 : `def _resolve_input_symbols(symbols: str | None, symbol_source: str | None) -> list[str]`
- [_parse_symbol_file](../../modelFactory/nyse_auction_history_poc.py) — ligne 121 : `def _parse_symbol_file(path: Path) -> list[str]`
- [_rotate_symbols](../../modelFactory/nyse_auction_history_poc.py) — ligne 132 : `def _rotate_symbols(symbols: list[str], *, key: str) -> tuple[list[str], int]`
- [summarize_auction_rows](../../modelFactory/nyse_auction_history_poc.py) — ligne 139 : `def summarize_auction_rows(rows: list[dict[str, Any]], *, observed_at: datetime) -> dict[str, Any] | None`
- [_load_realized_returns](../../modelFactory/nyse_auction_history_poc.py) — ligne 203 : `def _load_realized_returns(symbols: list[str], start: date, end: date) -> pd.DataFrame`
- [_feature_diagnostics](../../modelFactory/nyse_auction_history_poc.py) — ligne 247 : `def _feature_diagnostics(panel: pd.DataFrame) -> list[dict[str, Any]]`
- [run](../../modelFactory/nyse_auction_history_poc.py) — ligne 281 : `def run(args: argparse.Namespace) -> Path`
- [build_parser](../../modelFactory/nyse_auction_history_poc.py) — ligne 461 : `def build_parser() -> argparse.ArgumentParser`
- [main](../../modelFactory/nyse_auction_history_poc.py) — ligne 480 : `def main(argv: list[str] | None=None) -> int`

## `modelFactory/oof_consensus_audit.py`

Source SHA-256 : `6b41639ce6e077cc118a6f84fc17d6a312a3db15de864266d68eec66513c71e0`

- [_resolve](../../modelFactory/oof_consensus_audit.py) — ligne 23 : `def _resolve(root: Path, value: str) -> Path`
- [_score](../../modelFactory/oof_consensus_audit.py) — ligne 28 : `def _score(frame: pd.DataFrame, definition: dict[str, Any]) -> pd.Series`
- [load_component](../../modelFactory/oof_consensus_audit.py) — ligne 46 : `def load_component(root: Path, component: dict[str, Any]) -> pd.DataFrame`
- [build_family](../../modelFactory/oof_consensus_audit.py) — ligne 70 : `def build_family(root: Path, family: dict[str, Any]) -> pd.DataFrame`
- [build_horizon_panel](../../modelFactory/oof_consensus_audit.py) — ligne 99 : `def build_horizon_panel(root: Path, horizon: int, families: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]`
- [_daily_ic](../../modelFactory/oof_consensus_audit.py) — ligne 147 : `def _daily_ic(frame: pd.DataFrame, score: str) -> pd.Series`
- [_selection_metrics](../../modelFactory/oof_consensus_audit.py) — ligne 157 : `def _selection_metrics(frame: pd.DataFrame, score: str, fraction: float) -> dict[str, Any]`
- [evaluate_score](../../modelFactory/oof_consensus_audit.py) — ligne 192 : `def evaluate_score(frame: pd.DataFrame, score: str, fraction: float) -> dict[str, Any]`
- [evaluate_agreement](../../modelFactory/oof_consensus_audit.py) — ligne 227 : `def evaluate_agreement(frame: pd.DataFrame, fraction: float) -> dict[str, Any]`
- [pairwise_correlations](../../modelFactory/oof_consensus_audit.py) — ligne 257 : `def pairwise_correlations(frame: pd.DataFrame) -> list[dict[str, Any]]`
- [evaluate_daily_overlay](../../modelFactory/oof_consensus_audit.py) — ligne 282 : `def evaluate_daily_overlay(frame: pd.DataFrame, overlay: pd.DataFrame, *, fraction: float) -> dict[str, Any]`
- [load_daily_overlay](../../modelFactory/oof_consensus_audit.py) — ligne 311 : `def load_daily_overlay(root: Path, definition: dict[str, Any]) -> pd.DataFrame`
- [evaluate_gates](../../modelFactory/oof_consensus_audit.py) — ligne 329 : `def evaluate_gates(consensus: dict[str, Any], baselines: dict[str, Any]) -> dict[str, Any]`
- [run_audit](../../modelFactory/oof_consensus_audit.py) — ligne 354 : `def run_audit(manifest_path: Path, output: Path, *, project_root: Path) -> dict[str, Any]`
- [main](../../modelFactory/oof_consensus_audit.py) — ligne 419 : `def main() -> None`

## `modelFactory/options_acquisition_cost_audit.py`

Source SHA-256 : `63936e592f6d15cad7919c9b67854b92800c76aacf712cbb6fcb6c5d3fd2acba`

- [AcquisitionAssumptions](../../modelFactory/options_acquisition_cost_audit.py) — ligne 20 : `class AcquisitionAssumptions`
- [AcquisitionAssumptions.__post_init__](../../modelFactory/options_acquisition_cost_audit.py) — ligne 28 : `def __post_init__(self) -> None`
- [load_oracle_population](../../modelFactory/options_acquisition_cost_audit.py) — ligne 39 : `def load_oracle_population(path: Path, *, start_date: str, end_date: str | None=None) -> pd.DataFrame`
- [_latest_dates](../../modelFactory/options_acquisition_cost_audit.py) — ligne 63 : `def _latest_dates(frame: pd.DataFrame, count: int) -> pd.DataFrame`
- [_spread_dates](../../modelFactory/options_acquisition_cost_audit.py) — ligne 70 : `def _spread_dates(frame: pd.DataFrame, count: int) -> pd.DataFrame`
- [summarize_population](../../modelFactory/options_acquisition_cost_audit.py) — ligne 85 : `def summarize_population(frame: pd.DataFrame) -> dict[str, Any]`
- [estimate_collection](../../modelFactory/options_acquisition_cost_audit.py) — ligne 99 : `def estimate_collection(event_count: int, *, quote_requests_per_event: int, assumptions: AcquisitionAssumptions) -> dict[str, Any]`
- [provider_matrix](../../modelFactory/options_acquisition_cost_audit.py) — ligne 127 : `def provider_matrix() -> list[dict[str, Any]]`
- [build_report](../../modelFactory/options_acquisition_cost_audit.py) — ligne 177 : `def build_report(population: pd.DataFrame, *, source_path: Path, assumptions: AcquisitionAssumptions) -> dict[str, Any]`
- [run](../../modelFactory/options_acquisition_cost_audit.py) — ligne 230 : `def run(*, oracle_path: Path, output_root: Path, start_date: str, end_date: str | None, assumptions: AcquisitionAssumptions) -> Path`
- [main](../../modelFactory/options_acquisition_cost_audit.py) — ligne 248 : `def main() -> None`

## `modelFactory/options_directional_poc.py`

Source SHA-256 : `935401965bc341fdc09ba8727d9dac83b7746f970a2365e1deddc36a3f1f705c`

- [OptionsDirectionalConfig](../../modelFactory/options_directional_poc.py) — ligne 41 : `class OptionsDirectionalConfig`
- [OptionsDirectionalConfig.__post_init__](../../modelFactory/options_directional_poc.py) — ligne 54 : `def __post_init__(self) -> None`
- [select_events](../../modelFactory/options_directional_poc.py) — ligne 63 : `def select_events(source: pd.DataFrame, *, start_date: str, end_date: str, dates_per_semester: int, max_symbols_per_date: int | None=None) -> pd.DataFrame`
- [attach_signal_close](../../modelFactory/options_directional_poc.py) — ligne 98 : `def attach_signal_close(events: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame`
- [choose_surface_contracts](../../modelFactory/options_directional_poc.py) — ligne 108 : `def choose_surface_contracts(contracts: list[dict[str, Any]], *, spot: float, signal_date: date, config: OptionsDirectionalConfig) -> dict[str, Any] | None`
- [_results](../../modelFactory/options_directional_poc.py) — ligne 158 : `def _results(response: Any) -> list[dict[str, Any]]`
- [fetch_surface_contracts](../../modelFactory/options_directional_poc.py) — ligne 166 : `def fetch_surface_contracts(client: EroyaClient, symbol: str, signal_date: date, spot: float, config: OptionsDirectionalConfig) -> dict[str, Any] | None`
- [_nanoseconds](../../modelFactory/options_directional_poc.py) — ligne 191 : `def _nanoseconds(session_date: date, clock: str) -> int`
- [fetch_close_quote](../../modelFactory/options_directional_poc.py) — ligne 195 : `def fetch_close_quote(client: EroyaClient, ticker: str, session_date: date, config: OptionsDirectionalConfig) -> dict[str, Any] | None`
- [fetch_daily_volume](../../modelFactory/options_directional_poc.py) — ligne 222 : `def fetch_daily_volume(client: EroyaClient, ticker: str, session_date: date) -> float | None`
- [_normal_cdf](../../modelFactory/options_directional_poc.py) — ligne 238 : `def _normal_cdf(value: float) -> float`
- [_black_price](../../modelFactory/options_directional_poc.py) — ligne 242 : `def _black_price(forward: float, strike: float, years: float, sigma: float, side: str) -> float`
- [implied_volatility](../../modelFactory/options_directional_poc.py) — ligne 253 : `def implied_volatility(price: float, *, forward: float, strike: float, years: float, side: str) -> float | None`
- [compute_features](../../modelFactory/options_directional_poc.py) — ligne 271 : `def compute_features(*, spot: float, surface: dict[str, Any], quotes: dict[str, dict[str, Any]], volumes: dict[str, float | None]) -> dict[str, Any]`
- [evaluate_event](../../modelFactory/options_directional_poc.py) — ligne 324 : `def evaluate_event(client: EroyaClient, event: dict[str, Any], config: OptionsDirectionalConfig) -> dict[str, Any]`
- [_safe_daily_ic](../../modelFactory/options_directional_poc.py) — ligne 357 : `def _safe_daily_ic(frame: pd.DataFrame, feature: str, target: str) -> pd.Series`
- [evaluate_feature](../../modelFactory/options_directional_poc.py) — ligne 366 : `def evaluate_feature(frame: pd.DataFrame, feature: str, target: str, fraction: float) -> dict[str, Any]`
- [evaluate_features](../../modelFactory/options_directional_poc.py) — ligne 404 : `def evaluate_features(frame: pd.DataFrame, config: OptionsDirectionalConfig) -> dict[str, Any]`
- [run](../../modelFactory/options_directional_poc.py) — ligne 430 : `def run(client_factory: Any, events_path: Path, output: Path, *, start_date: str, end_date: str, max_symbols_per_date: int | None, max_workers: int, config: OptionsDirectionalConfig) -> dict[str, Any]`
- [main](../../modelFactory/options_directional_poc.py) — ligne 510 : `def main() -> None`

## `modelFactory/options_pit_history_audit.py`

Source SHA-256 : `e2b77a62f1a8ce141af31025cbfc36d03ab6b8aa8a6534d47d6ded8e2d9e3e1d`

- [OptionsPitRequirements](../../modelFactory/options_pit_history_audit.py) — ligne 21 : `class OptionsPitRequirements`
- [audit_database](../../modelFactory/options_pit_history_audit.py) — ligne 32 : `def audit_database(engine: Engine) -> dict[str, Any]`
- [_read_json](../../modelFactory/options_pit_history_audit.py) — ligne 47 : `def _read_json(path: Path) -> dict[str, Any]`
- [audit_directional_collection](../../modelFactory/options_pit_history_audit.py) — ligne 55 : `def audit_directional_collection(path: Path) -> dict[str, Any]`
- [audit_snapshot_file](../../modelFactory/options_pit_history_audit.py) — ligne 90 : `def audit_snapshot_file(path: Path) -> dict[str, Any]`
- [audit_local_artifacts](../../modelFactory/options_pit_history_audit.py) — ligne 128 : `def audit_local_artifacts(root: Path) -> dict[str, Any]`
- [assess_readiness](../../modelFactory/options_pit_history_audit.py) — ligne 145 : `def assess_readiness(database: dict[str, Any], artifacts: dict[str, Any], requirements: OptionsPitRequirements) -> dict[str, Any]`
- [run](../../modelFactory/options_pit_history_audit.py) — ligne 190 : `def run(*, artifacts_root: Path, output_root: Path, requirements: OptionsPitRequirements) -> Path`
- [main](../../modelFactory/options_pit_history_audit.py) — ligne 232 : `def main() -> None`

## `modelFactory/oracle/__init__.py`

Source SHA-256 : `d10ed80e54b4373debddca9ccea02ae5ca205e6e149f364f0391187e3adc1028`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/oracle/artifact_contract.py`

Source SHA-256 : `880a5824ea51b2588a8dbcaae697334664f221325de7074f7b0e36f62d2805c0`

- [_positive_horizon](../../modelFactory/oracle/artifact_contract.py) — ligne 9 : `def _positive_horizon(value: Any) -> int | None`
- [resolve_oracle_artifact_horizon](../../modelFactory/oracle/artifact_contract.py) — ligne 17 : `def resolve_oracle_artifact_horizon(batch_id: str | None, artifacts_root: Path | str=Path('artifacts/models')) -> int | None`
- [oracle_horizon_badge](../../modelFactory/oracle/artifact_contract.py) — ligne 74 : `def oracle_horizon_badge(batch_id: str | None, artifacts_root: Path | str=Path('artifacts/models')) -> str`

## `modelFactory/oracle/audit.py`

Source SHA-256 : `c1d8a0dcb2df6176ef06fb222205e85760a22fea60a30ca063a3b3f1f8bd1645`

- [load_trades](../../modelFactory/oracle/audit.py) — ligne 41 : `def load_trades(trades_path: Path | str) -> pd.DataFrame`
- [load_oracle_labels](../../modelFactory/oracle/audit.py) — ligne 50 : `def load_oracle_labels(engine: Any, batch_id: str, horizon: int=20, start: Any=None, end: Any=None) -> pd.DataFrame`
- [attach_oracle_labels](../../modelFactory/oracle/audit.py) — ligne 87 : `def attach_oracle_labels(trades_df: pd.DataFrame, oracle_df: pd.DataFrame) -> pd.DataFrame`
- [compute_capture](../../modelFactory/oracle/audit.py) — ligne 99 : `def compute_capture(labeled: pd.DataFrame) -> dict[str, Any]`
- [compute_decile_returns](../../modelFactory/oracle/audit.py) — ligne 125 : `def compute_decile_returns(oracle_df: pd.DataFrame) -> pd.DataFrame`
- [decile_monotonicity](../../modelFactory/oracle/audit.py) — ligne 138 : `def decile_monotonicity(decile_stats: pd.DataFrame) -> float | None`
- [compare_golden](../../modelFactory/oracle/audit.py) — ligne 154 : `def compare_golden(labeled: pd.DataFrame, golden_df: pd.DataFrame) -> dict[str, Any]`
- [audit_run](../../modelFactory/oracle/audit.py) — ligne 194 : `def audit_run(engine: Any, run_dir: Path | str, batch_id: str, horizon: int=20) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/audit.py) — ligne 244 : `def format_report(result: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/audit.py) — ligne 300 : `def main() -> None`

## `modelFactory/oracle/build_labels.py`

Source SHA-256 : `b2f9cfd69cc011391c130eb325cc525380dc17f3790b039271edf4f75e11d653`

- [PriceMatrices](../../modelFactory/oracle/build_labels.py) — ligne 93 : `class PriceMatrices`
- [_set_reason_where_empty](../../modelFactory/oracle/build_labels.py) — ligne 102 : `def _set_reason_where_empty(reasons: pd.Series, mask: pd.Series, reason: str) -> None`
- [classify_target_quality](../../modelFactory/oracle/build_labels.py) — ligne 112 : `def classify_target_quality(*, symbol: str, start: pd.Timestamp, end: pd.Timestamp, start_price: float | None, end_price: float | None, start_source: str | None, end_source: str | None, extreme_breaks: int, registry: dict[str, tuple[Any, ...]]) -> str | None`
- [_iso](../../modelFactory/oracle/build_labels.py) — ligne 140 : `def _iso(value: Any) -> str`
- [load_universe_from_ranks](../../modelFactory/oracle/build_labels.py) — ligne 147 : `def load_universe_from_ranks(engine: Any, batch_id: str, horizon: int) -> set[tuple[str, str]]`
- [load_universe_from_predictions](../../modelFactory/oracle/build_labels.py) — ligne 163 : `def load_universe_from_predictions(engine: Any, batch_id: str) -> set[tuple[str, str]]`
- [load_universe_from_bars](../../modelFactory/oracle/build_labels.py) — ligne 174 : `def load_universe_from_bars(engine: Any, symbols: list[str], *, start_date: str | None=None, end_date: str | None=None) -> set[tuple[str, str]]`
- [check_universe_equality](../../modelFactory/oracle/build_labels.py) — ligne 208 : `def check_universe_equality(rank_keys: Iterable[tuple[str, str]], pred_keys: Iterable[tuple[str, str]]) -> dict[str, Any]`
- [load_price_matrices](../../modelFactory/oracle/build_labels.py) — ligne 232 : `def load_price_matrices(engine: Any, symbols: list[str], start_date: str) -> PriceMatrices`
- [nyse_sessions](../../modelFactory/oracle/build_labels.py) — ligne 276 : `def nyse_sessions(start: str | date, end: str | date) -> pd.DatetimeIndex`
- [label_calendar](../../modelFactory/oracle/build_labels.py) — ligne 283 : `def label_calendar(start: str | date, end: str | date, horizon: int) -> dict[date, tuple[date, date]]`
- [load_stored_membership](../../modelFactory/oracle/build_labels.py) — ligne 294 : `def load_stored_membership(engine: Any, batch_id: str, horizon: int, start_date: str | None, end_date: str | None) -> set[tuple[str, str]]`
- [load_close_matrix](../../modelFactory/oracle/build_labels.py) — ligne 309 : `def load_close_matrix(engine: Any, symbols: list[str], start_date: str) -> pd.DataFrame`
- [compute_cross_sectional_ranks](../../modelFactory/oracle/build_labels.py) — ligne 314 : `def compute_cross_sectional_ranks(returns: pd.Series, top_pct: float=0.1) -> pd.DataFrame`
- [_upsert_rows](../../modelFactory/oracle/build_labels.py) — ligne 346 : `def _upsert_rows(engine: Any, rows: list[tuple[Any, ...]]) -> int`
- [build_labels](../../modelFactory/oracle/build_labels.py) — ligne 360 : `def build_labels(batch_id: str, *, horizon: int=20, start_date: str | None=None, end_date: str | None=None, engine: Any | None=None, dry_run: bool=False, strict_universe: bool=True, symbols: list[str] | None=None, output_parquet: str | None=None, progress_callback: Callable[[int, int, str], None] | None=None, universe_mode: str='static_bars', prediction_dates: list[str] | None=None) -> dict[str, Any]`
- [main](../../modelFactory/oracle/build_labels.py) — ligne 691 : `def main() -> None`

## `modelFactory/oracle/catastrophic_detector.py`

Source SHA-256 : `2e59d49efa9d03ab3550a7b9c0972a3fa66c153edc5ccb2f8f1cb73939073a27`

- [_auc](../../modelFactory/oracle/catastrophic_detector.py) — ligne 51 : `def _auc(y_true, y_score)`
- [_build_dataset](../../modelFactory/oracle/catastrophic_detector.py) — ligne 56 : `def _build_dataset(engine, batch_id: str, horizon: int=20, start: str='2022-01-01') -> pd.DataFrame`
- [_rejection_tradeoff](../../modelFactory/oracle/catastrophic_detector.py) — ligne 90 : `def _rejection_tradeoff(v: pd.DataFrame, score_col: str, cat_col: str) -> list[dict[str, Any]]`
- [run_catastrophic_detector_wf](../../modelFactory/oracle/catastrophic_detector.py) — ligne 114 : `def run_catastrophic_detector_wf(batch_id: str, *, target_pct: float=0.1, horizon: int=20, algos: tuple[str, ...]=('catboost', 'lightgbm')) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/catastrophic_detector.py) — ligne 177 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/catastrophic_detector.py) — ligne 197 : `def main() -> None`

## `modelFactory/oracle/combine.py`

Source SHA-256 : `35c8748589d6be2403225a1fac9ca13707522a124c8eab538913900d18b8083d`

- [combine_scores](../../modelFactory/oracle/combine.py) — ligne 41 : `def combine_scores(global_rank: np.ndarray, p_top: np.ndarray, *, method: str='weighted', alpha: float=0.5) -> np.ndarray`
- [isotonic_regression](../../modelFactory/oracle/combine.py) — ligne 62 : `def isotonic_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]`
- [calibrate_p_extreme](../../modelFactory/oracle/combine.py) — ligne 100 : `def calibrate_p_extreme(df: pd.DataFrame, *, method: str='identity', fit_x: np.ndarray | None=None, fit_y: np.ndarray | None=None) -> pd.Series`
- [apply_oracle_calibration](../../modelFactory/oracle/combine.py) — ligne 126 : `def apply_oracle_calibration(oos_df: pd.DataFrame, method: str='none', *, selection_folds: list[str] | None=None, calibration_df: pd.DataFrame | None=None) -> pd.DataFrame`
- [_evaluate_on_folds](../../modelFactory/oracle/combine.py) — ligne 199 : `def _evaluate_on_folds(oos_df: pd.DataFrame, score: pd.Series, folds: list[str]) -> dict[str, Any]`
- [run_combination_search](../../modelFactory/oracle/combine.py) — ligne 211 : `def run_combination_search(oos_df: pd.DataFrame, *, selection_folds: list[str], final_folds: list[str], alpha_grid: tuple[float, ...]=DEFAULT_ALPHA_GRID) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/combine.py) — ligne 257 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/combine.py) — ligne 283 : `def main() -> None`

## `modelFactory/oracle/config.py`

Source SHA-256 : `1f9bca2e4f76fe8c73d4314718380404c800246b5526b640b3e5257777e205e0`

- [OracleConfig](../../modelFactory/oracle/config.py) — ligne 27 : `class OracleConfig`
- [load_oracle_config](../../modelFactory/oracle/config.py) — ligne 37 : `def load_oracle_config(path: Path | str=_CONFIG_PATH) -> OracleConfig`
- [load_backtest_batch_id](../../modelFactory/oracle/config.py) — ligne 78 : `def load_backtest_batch_id(path: Path | str=_CONFIG_PATH) -> str | None`
- [resolve_oracle_batch_id](../../modelFactory/oracle/config.py) — ligne 91 : `def resolve_oracle_batch_id(path: Path | str=_CONFIG_PATH) -> str | None`

## `modelFactory/oracle/confound_validation.py`

Source SHA-256 : `ba2c71b61c9b7158e74c8801fc4a527c8f316b52a54898a4e6c794acceb09391`

- [_average_random_tradeoff](../../modelFactory/oracle/confound_validation.py) — ligne 36 : `def _average_random_tradeoff(df: pd.DataFrame, cat_col: str, seeds: int) -> list[dict[str, Any]]`
- [run_confound_validation](../../modelFactory/oracle/confound_validation.py) — ligne 55 : `def run_confound_validation(batch_id: str, *, horizon: int=20, start: str='2022-01-01') -> dict[str, Any]`
- [_print_table](../../modelFactory/oracle/confound_validation.py) — ligne 94 : `def _print_table(title: str, rows: list[dict[str, Any]]) -> str`
- [format_report](../../modelFactory/oracle/confound_validation.py) — ligne 105 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/confound_validation.py) — ligne 119 : `def main() -> None`

## `modelFactory/oracle/dataset.py`

Source SHA-256 : `07308b74e60f19ad500d3814eeef2e2fd8f2ed32483ff527fbab6c3838038671`

- [expert_feature_columns](../../modelFactory/oracle/dataset.py) — ligne 68 : `def expert_feature_columns() -> list[str]`
- [deduplicate_oracle_feature_columns](../../modelFactory/oracle/dataset.py) — ligne 73 : `def deduplicate_oracle_feature_columns(features: list[str]) -> list[str]`
- [lean_feature_columns](../../modelFactory/oracle/dataset.py) — ligne 78 : `def lean_feature_columns(features: list[str]) -> list[str]`
- [build_feature_matrix](../../modelFactory/oracle/dataset.py) — ligne 84 : `def build_feature_matrix(engine: Any, symbols: list[str], *, start_date: str, end_date: str, feature_set: str='expert', generator_options: dict[str, Any] | None=None, membership: pd.DataFrame | None=None) -> pd.DataFrame`
- [load_global_rank_feature](../../modelFactory/oracle/dataset.py) — ligne 192 : `def load_global_rank_feature(engine: Any, batch_id: str) -> pd.DataFrame`
- [load_oracle_targets](../../modelFactory/oracle/dataset.py) — ligne 203 : `def load_oracle_targets(engine: Any, batch_id: str, horizon: int=20) -> pd.DataFrame`
- [load_oracle_membership](../../modelFactory/oracle/dataset.py) — ligne 218 : `def load_oracle_membership(engine: Any, batch_id: str, horizon: int=20) -> pd.DataFrame`
- [build_dataset](../../modelFactory/oracle/dataset.py) — ligne 235 : `def build_dataset(engine: Any, batch_id: str, symbols: list[str], *, start_date: str, end_date: str, horizon: int=20, require_global_rank: bool=True, need_targets: bool=True, feature_whitelist: list[str] | tuple[str, ...] | None=None, generator_options: dict[str, Any] | None=None, restrict_features_to_targets: bool=False, feature_membership: pd.DataFrame | None=None) -> tuple[pd.DataFrame, list[str]]`
- [split_dataset](../../modelFactory/oracle/dataset.py) — ligne 357 : `def split_dataset(df: pd.DataFrame, *, train_cutoff: str, valid_start: str) -> tuple[pd.DataFrame, pd.DataFrame]`
- [ablation_features](../../modelFactory/oracle/dataset.py) — ligne 370 : `def ablation_features(feature_columns: list[str], *, include_global_rank: bool, include_oracle_extras: bool, lean: bool=False) -> list[str]`

## `modelFactory/oracle/directional_features.py`

Source SHA-256 : `902a04edf731e864270affbd27b3284ae2d8f2286c98c0c13e7ec9aaf3935caa`

- [_cs_spearman](../../modelFactory/oracle/directional_features.py) — ligne 37 : `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int=30) -> float | None`
- [build_directional_features](../../modelFactory/oracle/directional_features.py) — ligne 48 : `def build_directional_features(engine, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [run_directional_diagnostic](../../modelFactory/oracle/directional_features.py) — ligne 113 : `def run_directional_diagnostic(batch_id: str, *, horizon: int=20, start: str='2022-01-01') -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/directional_features.py) — ligne 153 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/directional_features.py) — ligne 169 : `def main() -> None`

## `modelFactory/oracle/dynamic_universe.py`

Source SHA-256 : `f2a17e900df8151ccfceab188247153c00ce0cb858282f62aec5c0c67baf3043`

- [DynamicUniverseThresholds](../../modelFactory/oracle/dynamic_universe.py) — ligne 12 : `class DynamicUniverseThresholds`
- [compute_dynamic_membership](../../modelFactory/oracle/dynamic_universe.py) — ligne 22 : `def compute_dynamic_membership(bars: pd.DataFrame, *, start_date: str, end_date: str, thresholds: DynamicUniverseThresholds | None=None) -> tuple[pd.DataFrame, dict[str, Any]]`
- [load_dynamic_universe_from_bars](../../modelFactory/oracle/dynamic_universe.py) — ligne 75 : `def load_dynamic_universe_from_bars(engine: Any, symbols: list[str], *, start_date: str, end_date: str, thresholds: DynamicUniverseThresholds | None=None) -> tuple[pd.DataFrame, dict[str, Any]]`

## `modelFactory/oracle/error_severity.py`

Source SHA-256 : `acabd117dceec440059c741fa630ce3f5e8410bb36e0ffbaec718641bed28640`

- [_rank_quality](../../modelFactory/oracle/error_severity.py) — ligne 49 : `def _rank_quality(valid: pd.DataFrame, score_col: str) -> dict[str, Any]`
- [_mag_corr](../../modelFactory/oracle/error_severity.py) — ligne 71 : `def _mag_corr(valid: pd.DataFrame, score_col: str) -> float | None`
- [run_error_severity_experiment](../../modelFactory/oracle/error_severity.py) — ligne 85 : `def run_error_severity_experiment(batch_id: str, *, train_cutoff: str='2024-06-30', valid_start: str='2025-01-01', horizon: int=20, algos: tuple[str, ...]=('catboost', 'lightgbm')) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/error_severity.py) — ligne 158 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/error_severity.py) — ligne 176 : `def main() -> None`

## `modelFactory/oracle/extreme_gate.py`

Source SHA-256 : `8c34a4760d6e5f872ab9bb1bb0dd1b1a59c4ffe1ad3bcd07576d5b906c088af9`

- [compute_extreme_gate](../../modelFactory/oracle/extreme_gate.py) — ligne 40 : `def compute_extreme_gate(df: pd.DataFrame, pool_pct: float=DEFAULT_POOL_PCT, proba_col: str='proba_extreme', date_col: str='date') -> pd.DataFrame`
- [build_oracle_rank_map](../../modelFactory/oracle/extreme_gate.py) — ligne 76 : `def build_oracle_rank_map(df: pd.DataFrame, proba_col: str='proba_extreme', date_col: str='date') -> dict[str, dict[str, float]]`

## `modelFactory/oracle/feature_diagnostic.py`

Source SHA-256 : `25e3bffbd38d5593ce7966fa47941f72f7cdaa816b4e77954470492718b5abb1`

- [_cs_spearman](../../modelFactory/oracle/feature_diagnostic.py) — ligne 54 : `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int=30) -> float | None`
- [_feature_columns](../../modelFactory/oracle/feature_diagnostic.py) — ligne 66 : `def _feature_columns(dataset: pd.DataFrame, feature_columns: list[str]) -> list[str]`
- [run_feature_diagnostic](../../modelFactory/oracle/feature_diagnostic.py) — ligne 74 : `def run_feature_diagnostic(batch_id: str, *, horizon: int=20, start: str='2022-01-01') -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/feature_diagnostic.py) — ligne 135 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/feature_diagnostic.py) — ligne 167 : `def main() -> None`

## `modelFactory/oracle/fundamental_diagnostic.py`

Source SHA-256 : `b4ef192065a32467db660b01914a55c1bf258f710961a32a1d2ed0cec4ec0112`

- [_cs_spearman](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 41 : `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int=30) -> float | None`
- [_auc](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 52 : `def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None`
- [_load_earnings](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 68 : `def _load_earnings(engine, symbols: list[str]) -> pd.DataFrame`
- [_load_fundamentals](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 89 : `def _load_fundamentals(engine, symbols: list[str]) -> pd.DataFrame`
- [_load_sentiment](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 103 : `def _load_sentiment(engine, symbols: list[str]) -> pd.DataFrame`
- [run_fundamental_diagnostic](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 117 : `def run_fundamental_diagnostic(batch_id: str, *, horizon: int=20, start: str='2022-01-01') -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 196 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/fundamental_diagnostic.py) — ligne 215 : `def main() -> None`

## `modelFactory/oracle/hard_negatives.py`

Source SHA-256 : `cf7cb3c30ccae3b4aec9b70f7fb3abf775b735e747a8e5c9d4ca2496a18a0fa5`

- [_intra_date_rank](../../modelFactory/oracle/hard_negatives.py) — ligne 57 : `def _intra_date_rank(df: pd.DataFrame, score_col: str) -> pd.Series`
- [_intra_date_corr](../../modelFactory/oracle/hard_negatives.py) — ligne 61 : `def _intra_date_corr(df: pd.DataFrame, a: str, b: str) -> float | None`
- [_train_model](../../modelFactory/oracle/hard_negatives.py) — ligne 75 : `def _train_model(algo: str, X_tr, y_tr, X_va, y_va, sample_weight=None)`
- [_diagnose](../../modelFactory/oracle/hard_negatives.py) — ligne 83 : `def _diagnose(valid: pd.DataFrame, ptop_col: str, pbot_col: str) -> dict[str, Any]`
- [run_hard_negative_experiment](../../modelFactory/oracle/hard_negatives.py) — ligne 121 : `def run_hard_negative_experiment(batch_id: str, *, train_cutoff: str='2024-06-30', valid_start: str='2025-01-01', horizon: int=20, algos: tuple[str, ...]=('catboost', 'lightgbm')) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/hard_negatives.py) — ligne 199 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/hard_negatives.py) — ligne 218 : `def main() -> None`

## `modelFactory/oracle/leakage.py`

Source SHA-256 : `08ab1e60c2af916f40e90d806ea981d1b4c20ec3d082d4043fd5636344379599`

- [assert_availability_after_prediction](../../modelFactory/oracle/leakage.py) — ligne 42 : `def assert_availability_after_prediction(df: pd.DataFrame, *, prediction_col: str='prediction_date', exit_col: str='oracle_exit_date', available_col: str='oracle_available_date') -> None`
- [assert_no_forbidden_features](../../modelFactory/oracle/leakage.py) — ligne 80 : `def assert_no_forbidden_features(feature_columns: Iterable[str]) -> None`
- [assert_no_future_features](../../modelFactory/oracle/leakage.py) — ligne 88 : `def assert_no_future_features(feature_columns: Iterable[str]) -> None`
- [assert_training_cutoff_valid](../../modelFactory/oracle/leakage.py) — ligne 105 : `def assert_training_cutoff_valid(*, training_cutoff: Any, max_oracle_available_date: Any) -> None`
- [assert_no_future_oracle_read](../../modelFactory/oracle/leakage.py) — ligne 127 : `def assert_no_future_oracle_read(*, today: Any, oracle_available_date: Any) -> None`

## `modelFactory/oracle/metrics.py`

Source SHA-256 : `3fb33f0ff93757208e1cb349255eeaefe41c4b1e9a27dbd7d0eb056be29d14e4`

- [roc_auc](../../modelFactory/oracle/metrics.py) — ligne 12 : `def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None`
- [precision_recall_at_top_pct](../../modelFactory/oracle/metrics.py) — ligne 28 : `def precision_recall_at_top_pct(df: pd.DataFrame, score_col: str, pct: float=0.1, min_universe: int=20, target_col: str='oracle_extreme10') -> dict[str, float | None]`
- [decile_monotonicity](../../modelFactory/oracle/metrics.py) — ligne 57 : `def decile_monotonicity(df: pd.DataFrame, score_col: str) -> tuple[float | None, pd.DataFrame]`

## `modelFactory/oracle/predict_history.py`

Source SHA-256 : `d434a31ffb24842e14f9010918048e33d9e85b546f8a64d352da467a76cedf6f`

- [has_oracle_champions](../../modelFactory/oracle/predict_history.py) — ligne 38 : `def has_oracle_champions(batch_id: str | None) -> bool`
- [_load_champions_meta](../../modelFactory/oracle/predict_history.py) — ligne 45 : `def _load_champions_meta(batch_id: str) -> list[dict[str, Any]]`
- [predict_oracle_extreme_history](../../modelFactory/oracle/predict_history.py) — ligne 60 : `def predict_oracle_extreme_history(engine: Any, batch_id: str, start_date: str, end_date: str, *, horizon: int | None=None, symbols: list[str] | None=None, persist_chunk_dates: int=DEFAULT_PERSIST_CHUNK_DATES, shadow_mode: bool=False, shadow_artifacts_root: Path | str | None=None) -> dict[str, Any]`

## `modelFactory/oracle/predictions_store.py`

Source SHA-256 : `cf4868147edc2420b913baea1344bf514559800d89f9d4e1a26ad2e8be898b52`

- [ensure_oracle_predictions_table](../../modelFactory/oracle/predictions_store.py) — ligne 58 : `def ensure_oracle_predictions_table(engine: Any) -> None`
- [write_oracle_predictions](../../modelFactory/oracle/predictions_store.py) — ligne 64 : `def write_oracle_predictions(engine: Any, df: pd.DataFrame, batch_id: str) -> int`
- [load_oracle_predictions](../../modelFactory/oracle/predictions_store.py) — ligne 113 : `def load_oracle_predictions(engine: Any, *, batch_id: str, start_date: str | None=None, end_date: str | None=None, require_batch: bool=True) -> pd.DataFrame`

## `modelFactory/oracle/research/dip_quality_synthesis.py`

Source SHA-256 : `ebf08223d1e6313f1bf65f3b346beb01cf87a4ec6c6454ed122865dde147c6e6`

- [metrics_from_trades](../../modelFactory/oracle/research/dip_quality_synthesis.py) — ligne 28 : `def metrics_from_trades(df)`

## `modelFactory/oracle/research/tiebreak_t0_t1_compare.py`

Source SHA-256 : `2aeefd5fc8dfe4aadb1a704c5b610c6b77b2088b21a1dc15add03a8149068a3c`

- [metrics_from_trades](../../modelFactory/oracle/research/tiebreak_t0_t1_compare.py) — ligne 33 : `def metrics_from_trades(df: pd.DataFrame) -> dict`
- [main](../../modelFactory/oracle/research/tiebreak_t0_t1_compare.py) — ligne 64 : `def main() -> None`

## `modelFactory/oracle/security_continuity.py`

Source SHA-256 : `586ee86ed58184c84cdc62e86fb7ed6a60da5ec109507c04b2ea2248554ba8a2`

- [SecurityDiscontinuity](../../modelFactory/oracle/security_continuity.py) — ligne 22 : `class SecurityDiscontinuity`
- [SecurityDiscontinuity.crosses](../../modelFactory/oracle/security_continuity.py) — ligne 28 : `def crosses(self, start: pd.Timestamp, end: pd.Timestamp) -> bool`
- [load_security_discontinuities](../../modelFactory/oracle/security_continuity.py) — ligne 33 : `def load_security_discontinuities(path: str | Path | None=None) -> dict[str, tuple[SecurityDiscontinuity, ...]]`
- [path_crosses_known_discontinuity](../../modelFactory/oracle/security_continuity.py) — ligne 59 : `def path_crosses_known_discontinuity(symbol: str, start: pd.Timestamp, end: pd.Timestamp, registry: dict[str, tuple[SecurityDiscontinuity, ...]]) -> bool`
- [split_frame_on_discontinuities](../../modelFactory/oracle/security_continuity.py) — ligne 71 : `def split_frame_on_discontinuities(frame: pd.DataFrame, symbol: str, registry: dict[str, tuple[SecurityDiscontinuity, ...]]) -> Iterable[pd.DataFrame]`

## `modelFactory/oracle/train.py`

Source SHA-256 : `c2ec5e0adc7784858bd70f1b4519a6f40d3cdd2ae100e279cb5fb8aa584b75f7`

- [get_universe_symbols](../../modelFactory/oracle/train.py) — ligne 44 : `def get_universe_symbols(engine: Any, batch_id: str, horizon: int) -> list[str]`
- [roc_auc](../../modelFactory/oracle/train.py) — ligne 55 : `def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None`
- [precision_recall_at_top_pct](../../modelFactory/oracle/train.py) — ligne 71 : `def precision_recall_at_top_pct(df: pd.DataFrame, score_col: str, pct: float=0.1, min_universe: int=20, target_col: str=TARGET_COL) -> dict[str, float | None]`
- [decile_monotonicity](../../modelFactory/oracle/train.py) — ligne 103 : `def decile_monotonicity(df: pd.DataFrame, score_col: str) -> tuple[float | None, pd.DataFrame]`
- [train_lightgbm](../../modelFactory/oracle/train.py) — ligne 118 : `def train_lightgbm(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=400, sample_weight: np.ndarray | None=None) -> Any`
- [train_catboost](../../modelFactory/oracle/train.py) — ligne 159 : `def train_catboost(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=300, sample_weight: np.ndarray | None=None) -> Any`
- [_proba_catboost](../../modelFactory/oracle/train.py) — ligne 197 : `def _proba_catboost(model: Any, X: pd.DataFrame) -> np.ndarray`
- [train_lightgbm_regressor](../../modelFactory/oracle/train.py) — ligne 202 : `def train_lightgbm_regressor(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=400) -> Any`
- [train_catboost_regressor](../../modelFactory/oracle/train.py) — ligne 236 : `def train_catboost_regressor(X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame, y_valid: pd.Series, num_boost_round: int=300) -> Any`
- [evaluate_model](../../modelFactory/oracle/train.py) — ligne 266 : `def evaluate_model(model: Any, valid_df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]`
- [run_ablation](../../modelFactory/oracle/train.py) — ligne 291 : `def run_ablation(batch_id: str, *, horizon: int=20, start_date: str='2020-01-01', end_date: str='2026-05-29', train_cutoff: str='2024-06-30', valid_start: str='2025-01-01', n_symbols: int | None=None) -> dict[str, Any]`
- [format_report](../../modelFactory/oracle/train.py) — ligne 338 : `def format_report(report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/train.py) — ligne 361 : `def main() -> None`

## `modelFactory/oracle/walk_forward.py`

Source SHA-256 : `54e42ad56505b701ac2596471e8043da0b7659b272cc45d47796a56c2afbaa24`

- [build_folds](../../modelFactory/oracle/walk_forward.py) — ligne 64 : `def build_folds(dataset: pd.DataFrame, test_windows: list[tuple[str, str]]) -> list[dict[str, Any]]`
- [build_folds_adaptive](../../modelFactory/oracle/walk_forward.py) — ligne 117 : `def build_folds_adaptive(dataset: pd.DataFrame, *, min_train_dates: int, val_dates: int, test_dates: int, step_dates: int, max_splits: int, forecast_horizon: int=20, materialize: bool=True) -> list[dict[str, Any]]`
- [run_walk_forward](../../modelFactory/oracle/walk_forward.py) — ligne 217 : `def run_walk_forward(dataset: pd.DataFrame, feature_columns: list[str], *, test_windows: list[tuple[str, str]] | None=None, folds: list[dict[str, Any]] | None=None, ablation: str='O1', memory_optimized: bool=False) -> dict[str, Any]`
- [persist_oos](../../modelFactory/oracle/walk_forward.py) — ligne 358 : `def persist_oos(oos: pd.DataFrame, run_id: str, batch_id: str | None=None, *, models: list[dict[str, Any]] | None=None, feature_columns: list[str] | None=None) -> str | None`
- [format_report](../../modelFactory/oracle/walk_forward.py) — ligne 422 : `def format_report(result: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle/walk_forward.py) — ligne 455 : `def main() -> None`

## `modelFactory/oracle_ablation_amplitude_compare.py`

Source SHA-256 : `4daa1adaae82d1e2336a8e128bca9690c6b488b414f71d371414c82ad3e7b1d0`

- [prepare_labels](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 24 : `def prepare_labels(path: Path, start_date: str, end_date: str) -> pd.DataFrame`
- [load_scores](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 47 : `def load_scores(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame`
- [key_fingerprint](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 64 : `def key_fingerprint(frame: pd.DataFrame) -> int`
- [_daily_spearman](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 69 : `def _daily_spearman(group: pd.DataFrame) -> float`
- [evaluate_batch](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 75 : `def evaluate_batch(scores: pd.DataFrame, labels: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]`
- [compare_batches](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 120 : `def compare_batches(engine: Any, batch_ids: list[str], labels_path: Path, *, start_date: str, end_date: str, baseline_batch_id: str, output: Path) -> dict[str, Any]`
- [main](../../modelFactory/oracle_ablation_amplitude_compare.py) — ligne 172 : `def main() -> None`

## `modelFactory/oracle_amplitude_audit.py`

Source SHA-256 : `1f876f7226f54c383415445978086c5e8ba8ac8d83482dc855bc0b651515cb8c`

- [AmplitudeAuditConfig](../../modelFactory/oracle_amplitude_audit.py) — ligne 39 : `class AmplitudeAuditConfig`
- [AmplitudeAuditConfig.__post_init__](../../modelFactory/oracle_amplitude_audit.py) — ligne 55 : `def __post_init__(self) -> None`
- [load_oof_gate](../../modelFactory/oracle_amplitude_audit.py) — ligne 72 : `def load_oof_gate(path: Path, config: AmplitudeAuditConfig) -> tuple[pd.DataFrame, dict[str, Any]]`
- [build_amplitude_panel](../../modelFactory/oracle_amplitude_audit.py) — ligne 116 : `def build_amplitude_panel(bars: pd.DataFrame, config: AmplitudeAuditConfig) -> pd.DataFrame`
- [attach_amplitude](../../modelFactory/oracle_amplitude_audit.py) — ligne 215 : `def attach_amplitude(gate: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame`
- [assign_groups](../../modelFactory/oracle_amplitude_audit.py) — ligne 222 : `def assign_groups(events: pd.DataFrame, config: AmplitudeAuditConfig) -> pd.DataFrame`
- [_safe_mean](../../modelFactory/oracle_amplitude_audit.py) — ligne 233 : `def _safe_mean(series: pd.Series) -> float | None`
- [_safe_spearman](../../modelFactory/oracle_amplitude_audit.py) — ligne 238 : `def _safe_spearman(group: pd.DataFrame, metric: str) -> float | None`
- [build_daily_comparisons](../../modelFactory/oracle_amplitude_audit.py) — ligne 246 : `def build_daily_comparisons(events: pd.DataFrame, metric: str, *, min_daily_universe: int) -> pd.DataFrame`
- [summarize_daily_comparison](../../modelFactory/oracle_amplitude_audit.py) — ligne 278 : `def summarize_daily_comparison(daily: pd.DataFrame) -> dict[str, Any]`
- [decile_table](../../modelFactory/oracle_amplitude_audit.py) — ligne 313 : `def decile_table(events: pd.DataFrame, metrics: list[str]) -> pd.DataFrame`
- [evaluate_amplitude](../../modelFactory/oracle_amplitude_audit.py) — ligne 327 : `def evaluate_amplitude(events: pd.DataFrame, config: AmplitudeAuditConfig) -> tuple[dict[str, Any], pd.DataFrame]`
- [run_amplitude_audit](../../modelFactory/oracle_amplitude_audit.py) — ligne 389 : `def run_amplitude_audit(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, config: AmplitudeAuditConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/oracle_amplitude_audit.py) — ligne 468 : `def _summary(path: Path, report: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle_amplitude_audit.py) — ligne 485 : `def main() -> None`

## `modelFactory/oracle_balanced_universe.py`

Source SHA-256 : `8c47747361460f42ce82eb2503ce1a91d83791d86058547b6542300ebd2d315b`

- [is_excluded_security_name](../../modelFactory/oracle_balanced_universe.py) — ligne 24 : `def is_excluded_security_name(names: pd.Series) -> pd.Series`
- [git_commit](../../modelFactory/oracle_balanced_universe.py) — ligne 37 : `def git_commit() -> str | None`
- [read_symbols](../../modelFactory/oracle_balanced_universe.py) — ligne 49 : `def read_symbols(path: Path) -> list[str]`
- [allocation_matrix](../../modelFactory/oracle_balanced_universe.py) — ligne 58 : `def allocation_matrix() -> dict[tuple[str, int], int]`
- [select_balanced](../../modelFactory/oracle_balanced_universe.py) — ligne 74 : `def select_balanced(candidates: pd.DataFrame, *, seed: int, sector_cap: int=40, foreign_proxy_cap: int=60) -> tuple[pd.DataFrame, list[dict[str, Any]]]`
- [run](../../modelFactory/oracle_balanced_universe.py) — ligne 144 : `def run(source: Path, cutoff: str, seed: int, output_file: Path, output_root: Path) -> Path`
- [main](../../modelFactory/oracle_balanced_universe.py) — ligne 313 : `def main() -> None`

## `modelFactory/oracle_canary.py`

Source SHA-256 : `abfb4c4b01a9d53b3ecf18e5d2cc5c63ee4e08fe3e9f2a0718ce57bb3b7d0d3b`

- [_json_safe](../../modelFactory/oracle_canary.py) — ligne 35 : `def _json_safe(value: Any) -> Any`
- [_write_json_atomic](../../modelFactory/oracle_canary.py) — ligne 49 : `def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None`
- [load_config](../../modelFactory/oracle_canary.py) — ligne 58 : `def load_config(path: Path) -> dict[str, Any]`
- [load_symbols](../../modelFactory/oracle_canary.py) — ligne 67 : `def load_symbols(path: Path) -> list[str]`
- [latest_benchmark_date](../../modelFactory/oracle_canary.py) — ligne 76 : `def latest_benchmark_date(engine: Any, symbol: str='SPY') -> str`
- [_percentile](../../modelFactory/oracle_canary.py) — ligne 87 : `def _percentile(values: np.ndarray, current: float) -> float`
- [monitor_distribution](../../modelFactory/oracle_canary.py) — ligne 92 : `def monitor_distribution(current: pd.DataFrame, baseline: pd.DataFrame, *, model_id: str, champion_age_days: int | None=None) -> dict[str, Any]`
- [daily_realized_metrics](../../modelFactory/oracle_canary.py) — ligne 141 : `def daily_realized_metrics(frame: pd.DataFrame) -> dict[str, Any]`
- [_load_state](../../modelFactory/oracle_canary.py) — ligne 162 : `def _load_state(path: Path, batch_id: str) -> dict[str, Any]`
- [_mature_dates](../../modelFactory/oracle_canary.py) — ligne 168 : `def _mature_dates(engine: Any, dates: list[str], horizon: int, benchmark: str) -> list[str]`
- [evaluate_matured](../../modelFactory/oracle_canary.py) — ligne 181 : `def evaluate_matured(state: dict[str, Any], *, state_path: Path, config: dict[str, Any], engine: Any, symbols: list[str]) -> int`
- [run_canary](../../modelFactory/oracle_canary.py) — ligne 246 : `def run_canary(config_path: Path, *, prediction_date: str | None=None, force: bool=False) -> dict[str, Any]`
- [main](../../modelFactory/oracle_canary.py) — ligne 325 : `def main() -> None`

## `modelFactory/oracle_conditional_quantiles_pmath3.py`

Source SHA-256 : `d13a7575c27a2d9d35329ad449f5757ece59588ac1d605026266a580b55ff7b8`

- [pinball_loss](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 36 : `def pinball_loss(target: np.ndarray, forecast: np.ndarray, quantile: float) -> float`
- [rearrange_quantiles](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 41 : `def rearrange_quantiles(predictions: np.ndarray) -> tuple[np.ndarray, float]`
- [tail_scores](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 50 : `def tail_scores(predictions: np.ndarray, quantiles: list[float]) -> dict[str, np.ndarray]`
- [select_train_rows](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 63 : `def select_train_rows(train: pd.DataFrame, maximum: int, seed: int) -> pd.DataFrame`
- [daily_top_fraction](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 72 : `def daily_top_fraction(frame: pd.DataFrame, score: str, fraction: float=0.1) -> pd.Series`
- [_fold_specs](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 79 : `def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [_split](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 91 : `def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [fit_quantile_models](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 99 : `def fit_quantile_models(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, quantiles: list[float], model_config: dict[str, Any], seed: int) -> np.ndarray`
- [_fold_metrics](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 126 : `def _fold_metrics(train: pd.DataFrame, test: pd.DataFrame, features: list[str], config: dict[str, Any], fold_index: int) -> tuple[dict[str, Any], pd.DataFrame]`
- [summarize](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 208 : `def summarize(folds: list[dict[str, Any]], gates: dict[str, Any], primary: str) -> dict[str, Any]`
- [run](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 247 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_conditional_quantiles_pmath3.py) — ligne 313 : `def main() -> None`

## `modelFactory/oracle_d10_trajectory_e23.py`

Source SHA-256 : `23dfdfcbd9e008eacc6d0c023f30b04b8a0f9fad4d30d3354ee2c8c089c29211`

- [attach_d10_one_vs_rest](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 29 : `def attach_d10_one_vs_rest(frame: pd.DataFrame) -> pd.DataFrame`
- [_session_map](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 38 : `def _session_map(dates: Iterable[Any]) -> dict[pd.Timestamp, int]`
- [attach_exact_session_lags](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 44 : `def attach_exact_session_lags(pool: pd.DataFrame, history: pd.DataFrame, source_columns: list[str], *, max_lag: int, prefix: str, session_map: dict[pd.Timestamp, int], include_current: bool, fill_zero_columns: set[str] | None=None) -> tuple[pd.DataFrame, list[str]]`
- [add_path_summaries](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 80 : `def add_path_summaries(frame: pd.DataFrame, *, source: str, ordered_columns: list[str], prefix: str) -> tuple[pd.DataFrame, list[str]]`
- [load_sentiment_daily](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 108 : `def load_sentiment_daily(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame`
- [add_sentiment_summaries](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 157 : `def add_sentiment_summaries(frame: pd.DataFrame, daily_columns: list[str], max_lag: int) -> tuple[pd.DataFrame, list[str]]`
- [_date_weights](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 177 : `def _date_weights(frame: pd.DataFrame) -> np.ndarray`
- [_prepare](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 183 : `def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame`
- [fit_model](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 188 : `def fit_model(name: str, train: pd.DataFrame, valid: pd.DataFrame, features: list[str], *, threads: int) -> tuple[Any, int | None]`
- [predict_probability](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 238 : `def predict_probability(model: Any, frame: pd.DataFrame, features: list[str]) -> np.ndarray`
- [_average_precision](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 242 : `def _average_precision(labels: pd.Series, scores: pd.Series) -> float | None`
- [_tail](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 250 : `def _tail(frame: pd.DataFrame, score: str, fraction: float) -> pd.DataFrame`
- [_selection](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 259 : `def _selection(frame: pd.DataFrame) -> dict[str, Any]`
- [evaluate](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 274 : `def evaluate(frame: pd.DataFrame, fractions: list[float]) -> dict[str, Any]`
- [latest_fold_specs](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 308 : `def latest_fold_specs(dataset: pd.DataFrame, wf: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [_split](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 320 : `def _split(dataset: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [train_variant](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 330 : `def train_variant(dataset: pd.DataFrame, features: list[str], specs: list[dict[str, Any]], *, model_name: str, fractions: list[float], threads: int) -> tuple[pd.DataFrame, dict[str, Any]]`
- [absolute_gates](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 378 : `def absolute_gates(result: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]`
- [incremental_gates](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 399 : `def incremental_gates(result: dict[str, Any], baseline: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]`
- [run](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 422 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_d10_trajectory_e23.py) — ligne 564 : `def main() -> None`

## `modelFactory/oracle_daily_regime.py`

Source SHA-256 : `f37edfccbdfbdc084ef5453f71f69facd4bb5c095ea52374e8d069b5dda81533`

- [DailyRegimeConfig](../../modelFactory/oracle_daily_regime.py) — ligne 93 : `class DailyRegimeConfig`
- [DailyRegimeConfig.__post_init__](../../modelFactory/oracle_daily_regime.py) — ligne 104 : `def __post_init__(self) -> None`
- [_numeric](../../modelFactory/oracle_daily_regime.py) — ligne 115 : `def _numeric(group: pd.DataFrame, column: str) -> pd.Series`
- [build_daily_regime_panel](../../modelFactory/oracle_daily_regime.py) — ligne 119 : `def build_daily_regime_panel(events: pd.DataFrame, *, min_daily_candidates: int=20) -> tuple[pd.DataFrame, list[str], dict[str, Any]]`
- [_prepare_numeric](../../modelFactory/oracle_daily_regime.py) — ligne 200 : `def _prepare_numeric(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame`
- [_fit_ridge](../../modelFactory/oracle_daily_regime.py) — ligne 209 : `def _fit_ridge(train: pd.DataFrame, features: list[str], alpha: float) -> Any`
- [_fit_catboost](../../modelFactory/oracle_daily_regime.py) — ligne 224 : `def _fit_catboost(train: pd.DataFrame, valid: pd.DataFrame | None, features: list[str], training: SharedDirectionalConfig, *, iterations: int | None=None) -> Any`
- [apply_daily_policy](../../modelFactory/oracle_daily_regime.py) — ligne 255 : `def apply_daily_policy(frame: pd.DataFrame, threshold: float) -> pd.DataFrame`
- [_cvar](../../modelFactory/oracle_daily_regime.py) — ligne 273 : `def _cvar(values: pd.Series, fraction: float=0.05) -> float | None`
- [_policy_metrics](../../modelFactory/oracle_daily_regime.py) — ligne 280 : `def _policy_metrics(frame: pd.DataFrame, threshold: float, catastrophic: float) -> dict[str, Any]`
- [evaluate_daily_predictions](../../modelFactory/oracle_daily_regime.py) — ligne 322 : `def evaluate_daily_predictions(frame: pd.DataFrame, config: DailyRegimeConfig | None=None) -> dict[str, Any]`
- [_trend_baselines](../../modelFactory/oracle_daily_regime.py) — ligne 355 : `def _trend_baselines(frame: pd.DataFrame, config: DailyRegimeConfig) -> dict[str, Any]`
- [_stability](../../modelFactory/oracle_daily_regime.py) — ligne 369 : `def _stability(oof: pd.DataFrame, model_name: str, config: DailyRegimeConfig) -> dict[str, Any]`
- [_gates](../../modelFactory/oracle_daily_regime.py) — ligne 393 : `def _gates(overall: dict[str, Any], stability: dict[str, Any], config: DailyRegimeConfig) -> dict[str, Any]`
- [train_daily_regime](../../modelFactory/oracle_daily_regime.py) — ligne 422 : `def train_daily_regime(panel: pd.DataFrame, features: list[str], training: SharedDirectionalConfig, config: DailyRegimeConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_daily_regime_campaign](../../modelFactory/oracle_daily_regime.py) — ligne 515 : `def run_daily_regime_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, training_config: SharedDirectionalConfig | None=None, regime_config: DailyRegimeConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/oracle_daily_regime.py) — ligne 620 : `def _summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/oracle_daily_regime.py) — ligne 636 : `def main() -> None`

## `modelFactory/oracle_global_rank_cross.py`

Source SHA-256 : `422ef687d70316814b4dbb61b4b5c980f6b0e20835b27c70719147bdbdaa56a5`

- [E11Config](../../modelFactory/oracle_global_rank_cross.py) — ligne 29 : `class E11Config`
- [E11Config.__post_init__](../../modelFactory/oracle_global_rank_cross.py) — ligne 42 : `def __post_init__(self) -> None`
- [E11Config.round_trip_cost](../../modelFactory/oracle_global_rank_cross.py) — ligne 51 : `def round_trip_cost(self) -> float`
- [E11Config.bootstrap_config](../../modelFactory/oracle_global_rank_cross.py) — ligne 54 : `def bootstrap_config(self) -> RollingConfig`
- [load_oof_inputs](../../modelFactory/oracle_global_rank_cross.py) — ligne 65 : `def load_oof_inputs(oracle_gate_path: Path, global_rank_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]`
- [build_cross_events](../../modelFactory/oracle_global_rank_cross.py) — ligne 80 : `def build_cross_events(oracle: pd.DataFrame, ranking: pd.DataFrame, bars: pd.DataFrame, config: E11Config) -> tuple[pd.DataFrame, dict[str, Any]]`
- [_daily_ic](../../modelFactory/oracle_global_rank_cross.py) — ligne 183 : `def _daily_ic(group: pd.DataFrame, rank_col: str, minimum: int) -> float`
- [_group_metrics](../../modelFactory/oracle_global_rank_cross.py) — ligne 190 : `def _group_metrics(frame: pd.DataFrame, group_column: str) -> pd.DataFrame`
- [summarize_daily](../../modelFactory/oracle_global_rank_cross.py) — ligne 208 : `def summarize_daily(events: pd.DataFrame) -> pd.DataFrame`
- [summarize_experiment](../../modelFactory/oracle_global_rank_cross.py) — ligne 238 : `def summarize_experiment(events: pd.DataFrame, coverage: dict[str, Any], config: E11Config) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [evaluate](../../modelFactory/oracle_global_rank_cross.py) — ligne 277 : `def evaluate(metrics: dict[str, Any], config: E11Config) -> dict[str, Any]`
- [run](../../modelFactory/oracle_global_rank_cross.py) — ligne 323 : `def run(*, oracle_gate_path: Path, global_rank_path: Path, output_root: Path, config: E11Config) -> Path`
- [main](../../modelFactory/oracle_global_rank_cross.py) — ligne 399 : `def main() -> None`

## `modelFactory/oracle_lead_lag_pmath1.py`

Source SHA-256 : `9af281bc5fc98d013adb1da382c74051efd6e5b3550d23e2fc9019d7cb8f9879`

- [ResidualModel](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 39 : `class ResidualModel`
- [adjusted_return_panel](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 44 : `def adjusted_return_panel(bars: pd.DataFrame) -> pd.DataFrame`
- [benchmark_returns](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 56 : `def benchmark_returns(frame: pd.DataFrame) -> pd.Series`
- [fit_residual_model](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 64 : `def fit_residual_model(returns: pd.DataFrame, market: pd.Series, sector_by_symbol: dict[str, str], train_dates: pd.Index, *, min_observations: int) -> tuple[ResidualModel, pd.DataFrame]`
- [_corr_and_overlap](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 100 : `def _corr_and_overlap(frame: pd.DataFrame, series: pd.Series) -> tuple[pd.Series, pd.Series]`
- [learn_stable_edges](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 105 : `def learn_stable_edges(residuals: pd.DataFrame, train_dates: pd.Index, *, lags: list[int], max_candidate_leaders: int, max_edges_per_follower: int, min_half_overlap: int, min_abs_half_correlation: float, min_symbol_train_observations: int) -> pd.DataFrame`
- [compute_pressure](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 158 : `def compute_pressure(residuals: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame`
- [_fold_specs](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 181 : `def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [_split](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 191 : `def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_signed_return](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 198 : `def _signed_return(task: str, frame: pd.DataFrame) -> pd.Series`
- [evaluate_task](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 203 : `def evaluate_task(train: pd.DataFrame, test: pd.DataFrame, features: list[str], task: str, config: dict[str, Any], seed: int) -> dict[str, Any]`
- [summarize](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 250 : `def summarize(rows: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]`
- [run](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 272 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_lead_lag_pmath1.py) — ligne 354 : `def main() -> None`

## `modelFactory/oracle_lifecycle_structural_audit.py`

Source SHA-256 : `b28addcc54c810e4308f6fe7cdf2d5495d7f48e56d3a890dd74d62f7e0c4136c`

- [LifecycleContract](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 37 : `class LifecycleContract`
- [E15Config](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 56 : `class E15Config`
- [E15Config.__post_init__](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 63 : `def __post_init__(self) -> None`
- [_activation_threshold_r](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 71 : `def _activation_threshold_r(mode: TrailingMode) -> float | None`
- [simulate_contract_long](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 79 : `def simulate_contract_long(symbol_bars: pd.DataFrame, *, signal_date: pd.Timestamp, contract: LifecycleContract, config: E12Config) -> dict[str, Any] | None`
- [build_contract_outcomes](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 164 : `def build_contract_outcomes(events: pd.DataFrame, prepared_bars: pd.DataFrame, contracts: tuple[LifecycleContract, ...], config: E12Config) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]`
- [schedule_contract_capacity](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 197 : `def schedule_contract_capacity(panel: pd.DataFrame, max_positions: int) -> pd.DataFrame`
- [summarize_contract](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 215 : `def summarize_contract(frame: pd.DataFrame, config: E15Config) -> dict[str, Any]`
- [paired_delta](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 236 : `def paired_delta(baseline: pd.DataFrame, candidate: pd.DataFrame, config: E15Config) -> dict[str, Any]`
- [portfolio_delta](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 254 : `def portfolio_delta(baseline: pd.DataFrame, candidate: pd.DataFrame, config: E15Config) -> dict[str, float]`
- [semester_comparison](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 268 : `def semester_comparison(baseline: pd.DataFrame, candidate: pd.DataFrame) -> list[dict[str, Any]]`
- [_period_delta](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 286 : `def _period_delta(baseline: pd.DataFrame, candidate: pd.DataFrame, *, start: str | None=None, end: str | None=None) -> float`
- [run](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 307 : `def run(*, oracle_gate_path: Path, output_root: Path, config: E15Config) -> Path`
- [main](../../modelFactory/oracle_lifecycle_structural_audit.py) — ligne 430 : `def main() -> None`

## `modelFactory/oracle_monetization_bridge.py`

Source SHA-256 : `485af1ac3e18e56254f89df11400766e78ae006feafda15353612b571cf24faf`

- [E12Config](../../modelFactory/oracle_monetization_bridge.py) — ligne 33 : `class E12Config`
- [E12Config.__post_init__](../../modelFactory/oracle_monetization_bridge.py) — ligne 49 : `def __post_init__(self) -> None`
- [E12Config.round_trip_cost](../../modelFactory/oracle_monetization_bridge.py) — ligne 56 : `def round_trip_cost(self) -> float`
- [E12Config.bootstrap_config](../../modelFactory/oracle_monetization_bridge.py) — ligne 59 : `def bootstrap_config(self) -> RollingConfig`
- [build_fixed_h20_events](../../modelFactory/oracle_monetization_bridge.py) — ligne 69 : `def build_fixed_h20_events(oracle_gate: pd.DataFrame, bars: pd.DataFrame, config: E12Config) -> pd.DataFrame`
- [deduplicate_non_overlapping](../../modelFactory/oracle_monetization_bridge.py) — ligne 129 : `def deduplicate_non_overlapping(events: pd.DataFrame) -> pd.DataFrame`
- [select_with_capacity](../../modelFactory/oracle_monetization_bridge.py) — ligne 144 : `def select_with_capacity(events: pd.DataFrame, config: E12Config, *, policy: Policy, seed: int=0, exit_column: str='terminal_date') -> pd.DataFrame`
- [load_exact_tradable_membership](../../modelFactory/oracle_monetization_bridge.py) — ligne 186 : `def load_exact_tradable_membership(engine: Engine, *, start_date: pd.Timestamp, end_date: pd.Timestamp, preset: str, quality: str) -> tuple[pd.DataFrame, dict[str, Any]]`
- [filter_by_membership](../../modelFactory/oracle_monetization_bridge.py) — ligne 227 : `def filter_by_membership(events: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame`
- [simulate_prod_long](../../modelFactory/oracle_monetization_bridge.py) — ligne 234 : `def simulate_prod_long(symbol_bars: pd.DataFrame, *, signal_date: pd.Timestamp, config: E12Config) -> dict[str, Any] | None`
- [replay_lifecycle_on_selected](../../modelFactory/oracle_monetization_bridge.py) — ligne 294 : `def replay_lifecycle_on_selected(selected: pd.DataFrame, prepared_bars: pd.DataFrame, config: E12Config) -> tuple[pd.DataFrame, pd.DataFrame]`
- [replay_lifecycle_with_dynamic_capacity](../../modelFactory/oracle_monetization_bridge.py) — ligne 317 : `def replay_lifecycle_with_dynamic_capacity(events: pd.DataFrame, prepared_bars: pd.DataFrame, config: E12Config, *, policy: Policy='oracle_score', seed: int=0) -> tuple[pd.DataFrame, pd.DataFrame]`
- [summarize_returns](../../modelFactory/oracle_monetization_bridge.py) — ligne 383 : `def summarize_returns(frame: pd.DataFrame, *, config: E12Config, return_column: str='net_return') -> dict[str, Any]`
- [random_capacity_distribution](../../modelFactory/oracle_monetization_bridge.py) — ligne 403 : `def random_capacity_distribution(events: pd.DataFrame, config: E12Config) -> tuple[pd.DataFrame, pd.DataFrame]`
- [run](../../modelFactory/oracle_monetization_bridge.py) — ligne 421 : `def run(*, oracle_gate_path: Path, output_root: Path, config: E12Config) -> Path`
- [main](../../modelFactory/oracle_monetization_bridge.py) — ligne 573 : `def main() -> None`

## `modelFactory/oracle_opening_price_backfill.py`

Source SHA-256 : `c7e7e3f292d592529cdfdb3f28d833582c8634d48e9bf7f24d71a3d27db014e3`

- [BackfillConfig](../../modelFactory/oracle_opening_price_backfill.py) — ligne 45 : `class BackfillConfig`
- [BackfillConfig.__post_init__](../../modelFactory/oracle_opening_price_backfill.py) — ligne 57 : `def __post_init__(self) -> None`
- [file_sha256](../../modelFactory/oracle_opening_price_backfill.py) — ligne 66 : `def file_sha256(path: Path) -> str`
- [_chunks](../../modelFactory/oracle_opening_price_backfill.py) — ligne 74 : `def _chunks(values: list[str], size: int) -> Iterable[list[str]]`
- [build_event_schedule](../../modelFactory/oracle_opening_price_backfill.py) — ligne 79 : `def build_event_schedule(oracle_path: Path, *, start_date: str | None=None, end_date: str | None=None) -> pd.DataFrame`
- [normalize_alpaca_pages](../../modelFactory/oracle_opening_price_backfill.py) — ligne 93 : `def normalize_alpaca_pages(pages: list[tuple[dict[str, Any], int]], *, session_date: pd.Timestamp) -> pd.DataFrame`
- [_atomic_json](../../modelFactory/oracle_opening_price_backfill.py) — ligne 138 : `def _atomic_json(path: Path, payload: dict[str, Any]) -> None`
- [_new_state](../../modelFactory/oracle_opening_price_backfill.py) — ligne 147 : `def _new_state(*, batch_id: str, horizon: int, oracle_path: Path, schedule: pd.DataFrame, config: BackfillConfig) -> dict[str, Any]`
- [load_or_create_state](../../modelFactory/oracle_opening_price_backfill.py) — ligne 162 : `def load_or_create_state(state_path: Path, *, batch_id: str, horizon: int, oracle_path: Path, schedule: pd.DataFrame, config: BackfillConfig) -> dict[str, Any]`
- [_fetch_session](../../modelFactory/oracle_opening_price_backfill.py) — ligne 185 : `def _fetch_session(session: requests.Session, headers: dict[str, str], *, session_date: pd.Timestamp, symbols: list[str], config: BackfillConfig) -> tuple[pd.DataFrame, int]`
- [_consolidate](../../modelFactory/oracle_opening_price_backfill.py) — ligne 212 : `def _consolidate(partition_dir: Path, output_path: Path) -> int`
- [run](../../modelFactory/oracle_opening_price_backfill.py) — ligne 224 : `def run(*, batch_id: str, horizon: int, oracle_path: Path, output_dir: Path, config: BackfillConfig, feature_config: E20BConfig, start_date: str | None=None, end_date: str | None=None, max_sessions: int | None=None) -> Path`
- [main](../../modelFactory/oracle_opening_price_backfill.py) — ligne 353 : `def main() -> None`

## `modelFactory/oracle_opening_price_confirmation.py`

Source SHA-256 : `8c02fbffffb3fb1c205811b0e333b6f4198742896b4d133ac62fe10707f60645`

- [E20BConfig](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 32 : `class E20BConfig`
- [E20BConfig.__post_init__](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 53 : `def __post_init__(self) -> None`
- [build_price_only_features](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 62 : `def build_price_only_features(rows: pd.DataFrame, config: E20BConfig) -> pd.DataFrame`
- [attach_price_only_features](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 137 : `def attach_price_only_features(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame`
- [_moving_block_ci](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 152 : `def _moving_block_ci(values: pd.Series, config: E20BConfig) -> tuple[float | None, float | None]`
- [evaluate_rules](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 169 : `def evaluate_rules(joined: pd.DataFrame, config: E20BConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [decide](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 240 : `def decide(summary: pd.DataFrame, config: E20BConfig) -> dict[str, Any]`
- [_load_labeled_events](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 289 : `def _load_labeled_events(engine: Any, *, batch_id: str, horizon: int, oracle_path: Path, start_date: str | None, end_date: str | None) -> pd.DataFrame`
- [load_price_features](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 306 : `def load_price_features(path: Path) -> pd.DataFrame`
- [run](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 319 : `def run(*, batch_id: str, horizon: int, oracle_path: Path, output_root: Path, config: E20BConfig, start_date: str | None=None, end_date: str | None=None, features_path: Path | None=None) -> Path`
- [main](../../modelFactory/oracle_opening_price_confirmation.py) — ligne 396 : `def main() -> None`

## `modelFactory/oracle_opening_price_economic_replay.py`

Source SHA-256 : `9f560e3ca32368fccfb66e004c71afd0ca35b91d9f0568e2a1a2e39d7d3d8e65`

- [E20DConfig](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 32 : `class E20DConfig`
- [E20DConfig.round_trip_cost](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 54 : `def round_trip_cost(self) -> float`
- [E20DConfig.bootstrap_config](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 57 : `def bootstrap_config(self)`
- [select_price_confirmed](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 65 : `def select_price_confirmed(events: pd.DataFrame, config: E20DConfig) -> pd.DataFrame`
- [_return](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 89 : `def _return(side: int, exit_price: float, entry_price: float) -> float`
- [simulate_delayed_trade](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 93 : `def simulate_delayed_trade(symbol_bars: pd.DataFrame, event: Any, *, policy: EntryDayPolicy, config: E20DConfig) -> dict[str, Any] | None`
- [build_outcomes](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 207 : `def build_outcomes(events: pd.DataFrame, bars: pd.DataFrame, config: E20DConfig)`
- [schedule_capacity](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 242 : `def schedule_capacity(frame: pd.DataFrame, max_positions: int) -> pd.DataFrame`
- [summarize](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 262 : `def summarize(frame: pd.DataFrame, config: E20DConfig) -> dict[str, Any]`
- [paired_policy_delta](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 310 : `def paired_policy_delta(primary: pd.DataFrame, sensitivity: pd.DataFrame, config: E20DConfig)`
- [run](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 326 : `def run(*, events_path: Path, output_root: Path, config: E20DConfig) -> Path`
- [main](../../modelFactory/oracle_opening_price_economic_replay.py) — ligne 386 : `def main() -> None`

## `modelFactory/oracle_opening_volume_ablation.py`

Source SHA-256 : `969230bdb6795f5eff17ef8686847929f1317886505169966a6f736092f10d27`

- [E20CConfig](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 30 : `class E20CConfig`
- [E20CConfig.__post_init__](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 56 : `def __post_init__(self) -> None`
- [feature_columns](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 68 : `def feature_columns(checkpoint: int) -> tuple[list[str], list[str]]`
- [prepare_dataset](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 94 : `def prepare_dataset(events: pd.DataFrame, features: pd.DataFrame, config: E20CConfig) -> pd.DataFrame`
- [build_folds](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 145 : `def build_folds(dates: pd.Series, config: E20CConfig) -> list[dict[str, Any]]`
- [_model](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 163 : `def _model(config: E20CConfig) -> lgb.LGBMClassifier`
- [_safe_auc](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 174 : `def _safe_auc(target: pd.Series, probability: np.ndarray) -> float`
- [_metrics](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 178 : `def _metrics(frame: pd.DataFrame, probability: np.ndarray, config: E20CConfig) -> dict[str, float | int]`
- [evaluate](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 198 : `def evaluate(dataset: pd.DataFrame, config: E20CConfig) -> tuple[pd.DataFrame, pd.DataFrame]`
- [summarize](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 242 : `def summarize(folds: pd.DataFrame, predictions: pd.DataFrame, config: E20CConfig) -> dict[str, Any]`
- [run](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 298 : `def run(*, batch_id: str, horizon: int, oracle_path: Path, features_path: Path, output_root: Path, config: E20CConfig) -> Path`
- [main](../../modelFactory/oracle_opening_volume_ablation.py) — ligne 340 : `def main() -> None`

## `modelFactory/oracle_opening_volume_backfill.py`

Source SHA-256 : `18bb98c1bff89ae46105aa28e03f7741d7f9c7a24ac1e107d8a89445a5be2f38`

- [BackfillConfig](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 45 : `class BackfillConfig`
- [BackfillConfig.__post_init__](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 57 : `def __post_init__(self) -> None`
- [file_sha256](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 66 : `def file_sha256(path: Path) -> str`
- [_chunks](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 74 : `def _chunks(values: list[str], size: int) -> Iterable[list[str]]`
- [build_event_schedule](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 79 : `def build_event_schedule(oracle_path: Path, *, start_date: str | None=None, end_date: str | None=None) -> pd.DataFrame`
- [normalize_alpaca_pages](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 93 : `def normalize_alpaca_pages(pages: list[tuple[dict[str, Any], int]], *, session_date: pd.Timestamp) -> pd.DataFrame`
- [build_price_volume_features](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 140 : `def build_price_volume_features(rows: pd.DataFrame, config: E20BConfig) -> pd.DataFrame`
- [_atomic_json](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 165 : `def _atomic_json(path: Path, payload: dict[str, Any]) -> None`
- [_new_state](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 174 : `def _new_state(*, batch_id: str, horizon: int, oracle_path: Path, schedule: pd.DataFrame, config: BackfillConfig) -> dict[str, Any]`
- [load_or_create_state](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 189 : `def load_or_create_state(state_path: Path, *, batch_id: str, horizon: int, oracle_path: Path, schedule: pd.DataFrame, config: BackfillConfig) -> dict[str, Any]`
- [_fetch_session](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 212 : `def _fetch_session(session: requests.Session, headers: dict[str, str], *, session_date: pd.Timestamp, symbols: list[str], config: BackfillConfig) -> tuple[pd.DataFrame, int]`
- [_consolidate](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 239 : `def _consolidate(partition_dir: Path, output_path: Path) -> int`
- [run](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 251 : `def run(*, batch_id: str, horizon: int, oracle_path: Path, output_dir: Path, config: BackfillConfig, feature_config: E20BConfig, start_date: str | None=None, end_date: str | None=None, max_sessions: int | None=None) -> Path`
- [main](../../modelFactory/oracle_opening_volume_backfill.py) — ligne 380 : `def main() -> None`

## `modelFactory/oracle_opening_window_availability_audit.py`

Source SHA-256 : `29c4a179313f0e496d5f8b4c76465410d3e4683fc404ae46a71b9383b7c5a5ab`

- [E20AConfig](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 30 : `class E20AConfig`
- [load_oracle_events](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 45 : `def load_oracle_events(path: Path) -> pd.DataFrame`
- [attach_next_oracle_session](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 63 : `def attach_next_oracle_session(events: pd.DataFrame) -> pd.DataFrame`
- [table_summary](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 72 : `def table_summary(engine: Engine) -> dict[str, Any]`
- [load_opening_rows](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 98 : `def load_opening_rows(engine: Engine, *, start_session: pd.Timestamp, end_session: pd.Timestamp, config: E20AConfig) -> pd.DataFrame`
- [build_symbol_session_coverage](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 133 : `def build_symbol_session_coverage(rows: pd.DataFrame) -> pd.DataFrame`
- [_semester](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 164 : `def _semester(values: pd.Series) -> pd.Series`
- [build_report](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 169 : `def build_report(*, events: pd.DataFrame, coverage: pd.DataFrame, global_summary: dict[str, Any], recent_runs: list[dict[str, Any]], oracle_path: Path, config: E20AConfig) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]`
- [load_recent_runs](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 285 : `def load_recent_runs(engine: Engine) -> list[dict[str, Any]]`
- [run](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 299 : `def run(*, oracle_path: Path, output_root: Path, config: E20AConfig) -> Path`
- [main](../../modelFactory/oracle_opening_window_availability_audit.py) — ligne 327 : `def main() -> None`

## `modelFactory/oracle_options_feasibility.py`

Source SHA-256 : `dcaa2ed9c4f37a78c91ae9b8268b0d3d887c377503cbaf2c523c1c03360e863e`

- [OptionsFeasibilityConfig](../../modelFactory/oracle_options_feasibility.py) — ligne 22 : `class OptionsFeasibilityConfig`
- [iter_jsonl_gzip](../../modelFactory/oracle_options_feasibility.py) — ligne 35 : `def iter_jsonl_gzip(paths: Iterable[Path]) -> Iterable[dict[str, Any]]`
- [audit_snapshot_collections](../../modelFactory/oracle_options_feasibility.py) — ligne 45 : `def audit_snapshot_collections(paths: Iterable[Path]) -> dict[str, Any]`
- [assess_remote_evidence](../../modelFactory/oracle_options_feasibility.py) — ligne 114 : `def assess_remote_evidence(evidence: dict[str, Any]) -> dict[str, Any]`
- [build_report](../../modelFactory/oracle_options_feasibility.py) — ligne 139 : `def build_report(snapshot: dict[str, Any], evidence: dict[str, Any], config: OptionsFeasibilityConfig | None=None) -> dict[str, Any]`
- [main](../../modelFactory/oracle_options_feasibility.py) — ligne 190 : `def main() -> None`

## `modelFactory/oracle_options_pilot.py`

Source SHA-256 : `8dbf3af4f45bc41daf08009d65ef32baf93247daa35ee097dfe53f404103746b`

- [OptionsPilotConfig](../../modelFactory/oracle_options_pilot.py) — ligne 32 : `class OptionsPilotConfig`
- [OptionsPilotConfig.__post_init__](../../modelFactory/oracle_options_pilot.py) — ligne 46 : `def __post_init__(self) -> None`
- [_clock](../../modelFactory/oracle_options_pilot.py) — ligne 59 : `def _clock(value: str) -> time`
- [_ns](../../modelFactory/oracle_options_pilot.py) — ligne 63 : `def _ns(value: datetime) -> int`
- [select_pilot_events](../../modelFactory/oracle_options_pilot.py) — ligne 67 : `def select_pilot_events(events: pd.DataFrame, *, dates_per_semester: int=1, max_symbols_per_date: int | None=None, start_date: str='2022-03-07', end_date: str='2025-07-11') -> pd.DataFrame`
- [build_event_schedule](../../modelFactory/oracle_options_pilot.py) — ligne 108 : `def build_event_schedule(events: pd.DataFrame, bars: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame`
- [choose_contract_pair](../../modelFactory/oracle_options_pilot.py) — ligne 142 : `def choose_contract_pair(contracts: list[dict[str, Any]], *, spot: float, entry_date: date, config: OptionsPilotConfig) -> dict[str, Any] | None`
- [_results](../../modelFactory/oracle_options_pilot.py) — ligne 180 : `def _results(response: Any) -> list[dict[str, Any]]`
- [fetch_contract_pair](../../modelFactory/oracle_options_pilot.py) — ligne 188 : `def fetch_contract_pair(client: EroyaClient, symbol: str, entry_date: date, spot: float, config: OptionsPilotConfig) -> dict[str, Any] | None`
- [fetch_quote](../../modelFactory/oracle_options_pilot.py) — ligne 205 : `def fetch_quote(client: EroyaClient, ticker: str, session_date: date, *, start_clock: str, end_clock: str, order: str) -> dict[str, Any] | None`
- [fetch_pair_quote](../../modelFactory/oracle_options_pilot.py) — ligne 227 : `def fetch_pair_quote(client: EroyaClient, pair: dict[str, Any], session_date: date, *, start_clock: str, end_clock: str, order: str, max_skew_seconds: int) -> dict[str, Any] | None`
- [evaluate_event](../../modelFactory/oracle_options_pilot.py) — ligne 247 : `def evaluate_event(client: EroyaClient, event: dict[str, Any], config: OptionsPilotConfig) -> dict[str, Any]`
- [summarize](../../modelFactory/oracle_options_pilot.py) — ligne 325 : `def summarize(results: pd.DataFrame, config: OptionsPilotConfig) -> dict[str, Any]`
- [run_pilot](../../modelFactory/oracle_options_pilot.py) — ligne 345 : `def run_pilot(client: EroyaClient, events_path: Path, output: Path, *, dates_per_semester: int, max_symbols_per_date: int | None, start_date: str, end_date: str, config: OptionsPilotConfig) -> dict[str, Any]`
- [main](../../modelFactory/oracle_options_pilot.py) — ligne 399 : `def main() -> None`

## `modelFactory/oracle_path_signatures_pmath2.py`

Source SHA-256 : `ff73ae9da8782b186638328859c90d02f4b944b9207573adf108d74bbe3b3e69`

- [signature_feature_names](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 38 : `def signature_feature_names(depth: int, channels: tuple[str, ...]=CHANNELS) -> list[str]`
- [tensor_signature_batch](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 46 : `def tensor_signature_batch(increments: np.ndarray, depth: int=3) -> np.ndarray`
- [build_sector_factor](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 75 : `def build_sector_factor(returns: pd.DataFrame, sector_by_symbol: dict[str, str]) -> tuple[pd.DataFrame, dict[str, str]]`
- [build_signature_panel](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 85 : `def build_signature_panel(events: pd.DataFrame, returns: pd.DataFrame, market: pd.Series, sector_factors: pd.DataFrame, sector_by_symbol: dict[str, str], *, window: int, max_depth: int, min_valid_asset_sessions: int, chunk_size: int) -> tuple[pd.DataFrame, list[str]]`
- [_fold_specs](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 144 : `def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [_split](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 154 : `def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_signed_return](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 163 : `def _signed_return(task: str, frame: pd.DataFrame) -> pd.Series`
- [_fit_score](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 168 : `def _fit_score(train: pd.DataFrame, test: pd.DataFrame, columns: list[str], cfg: dict[str, Any], seed: int) -> np.ndarray`
- [evaluate_task](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 178 : `def evaluate_task(train: pd.DataFrame, test: pd.DataFrame, state_features: list[str], signature_names: list[str], task: str, config: dict[str, Any], seed: int) -> list[dict[str, Any]]`
- [summarize](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 213 : `def summarize(metrics: pd.DataFrame, gates: dict[str, Any], depth: int) -> dict[str, Any]`
- [run](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 238 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_path_signatures_pmath2.py) — ligne 316 : `def main() -> None`

## `modelFactory/oracle_post_signal_confirmation.py`

Source SHA-256 : `5a12b7d7cbd0ce80bbc2f79771df22ed1f65701fd7ee0c7a6826edcb9ea28dee`

- [E9Config](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 25 : `class E9Config`
- [E9Config.__post_init__](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 41 : `def __post_init__(self) -> None`
- [E9Config.round_trip_cost](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 52 : `def round_trip_cost(self) -> float`
- [prepare_price_panel](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 56 : `def prepare_price_panel(bars: pd.DataFrame, delays: tuple[int, ...]) -> pd.DataFrame`
- [attach_confirmation_paths](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 89 : `def attach_confirmation_paths(oracle_events: pd.DataFrame, prices: pd.DataFrame, benchmark_prices: pd.DataFrame, sector_map: dict[str, str], config: E9Config) -> pd.DataFrame`
- [_signal_column](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 139 : `def _signal_column(basis: str, delay: int) -> str`
- [_policy_rows](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 145 : `def _policy_rows(frame: pd.DataFrame, *, basis: str, delay: int, threshold: float, round_trip_cost: float) -> pd.DataFrame`
- [select_threshold](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 161 : `def select_threshold(history: pd.DataFrame, *, basis: str, delay: int, config: E9Config) -> tuple[float, list[dict[str, Any]]]`
- [build_prequential_decisions](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 185 : `def build_prequential_decisions(events: pd.DataFrame, config: E9Config) -> tuple[pd.DataFrame, pd.DataFrame]`
- [_semester](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 210 : `def _semester(values: pd.Series) -> pd.Series`
- [summarize_policies](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 215 : `def summarize_policies(events: pd.DataFrame, decisions: pd.DataFrame, config: E9Config) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [summarize_sides](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 261 : `def summarize_sides(decisions: pd.DataFrame, config: E9Config) -> pd.DataFrame`
- [evaluate_verdict](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 283 : `def evaluate_verdict(summary: pd.DataFrame, config: E9Config) -> dict[str, Any]`
- [run](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 308 : `def run(*, phase1_artifact: Path, output_root: Path, config: E9Config) -> Path`
- [main](../../modelFactory/oracle_post_signal_confirmation.py) — ligne 352 : `def main() -> None`

## `modelFactory/oracle_pre_entry_utility.py`

Source SHA-256 : `0f6fc7fb0b7d01c76a342ce8c52785aa2e406bab346a1247df6b596d1c3a7c3a`

- [E14Config](../../modelFactory/oracle_pre_entry_utility.py) — ligne 44 : `class E14Config`
- [E14Config.__post_init__](../../modelFactory/oracle_pre_entry_utility.py) — ligne 55 : `def __post_init__(self) -> None`
- [fit_oof_economic_heads](../../modelFactory/oracle_pre_entry_utility.py) — ligne 62 : `def fit_oof_economic_heads(panel: pd.DataFrame, config: E14Config) -> tuple[pd.DataFrame, list[dict[str, Any]]]`
- [add_priority_scores](../../modelFactory/oracle_pre_entry_utility.py) — ligne 154 : `def add_priority_scores(panel: pd.DataFrame) -> pd.DataFrame`
- [schedule_economic_capacity](../../modelFactory/oracle_pre_entry_utility.py) — ligne 171 : `def schedule_economic_capacity(panel: pd.DataFrame, *, max_positions: int, priority_column: str='oracle_priority', keep_column: str | None=None) -> pd.DataFrame`
- [_rank_ic](../../modelFactory/oracle_pre_entry_utility.py) — ligne 196 : `def _rank_ic(frame: pd.DataFrame, score: str) -> float`
- [economic_model_diagnostics](../../modelFactory/oracle_pre_entry_utility.py) — ligne 207 : `def economic_model_diagnostics(panel: pd.DataFrame) -> dict[str, Any]`
- [_evaluate_policy](../../modelFactory/oracle_pre_entry_utility.py) — ligne 236 : `def _evaluate_policy(baseline: pd.DataFrame, candidate: pd.DataFrame, config: E14Config) -> dict[str, Any]`
- [run](../../modelFactory/oracle_pre_entry_utility.py) — ligne 247 : `def run(*, oracle_gate_path: Path, output_root: Path, config: E14Config) -> Path`
- [main](../../modelFactory/oracle_pre_entry_utility.py) — ligne 378 : `def main() -> None`

## `modelFactory/oracle_pre_entry_veto.py`

Source SHA-256 : `022c9a245260b82628db5dc4e88a8deca105a38d1f90127edd5d7723d66441ca`

- [E13Config](../../modelFactory/oracle_pre_entry_veto.py) — ligne 56 : `class E13Config`
- [E13Config.__post_init__](../../modelFactory/oracle_pre_entry_veto.py) — ligne 67 : `def __post_init__(self) -> None`
- [add_pre_entry_features](../../modelFactory/oracle_pre_entry_veto.py) — ligne 74 : `def add_pre_entry_features(events: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame`
- [build_outcome_panel](../../modelFactory/oracle_pre_entry_veto.py) — ligne 123 : `def build_outcome_panel(events: pd.DataFrame, prepared_bars: pd.DataFrame, lifecycle: E12Config) -> tuple[pd.DataFrame, pd.DataFrame]`
- [fit_oof_risk](../../modelFactory/oracle_pre_entry_veto.py) — ligne 143 : `def fit_oof_risk(panel: pd.DataFrame, config: E13Config) -> tuple[pd.DataFrame, list[dict[str, Any]]]`
- [add_daily_vetoes](../../modelFactory/oracle_pre_entry_veto.py) — ligne 204 : `def add_daily_vetoes(panel: pd.DataFrame, fractions: tuple[float, ...]) -> pd.DataFrame`
- [schedule_dynamic_capacity](../../modelFactory/oracle_pre_entry_veto.py) — ligne 214 : `def schedule_dynamic_capacity(panel: pd.DataFrame, *, max_positions: int, keep_column: str | None=None) -> pd.DataFrame`
- [_summary](../../modelFactory/oracle_pre_entry_veto.py) — ligne 237 : `def _summary(frame: pd.DataFrame, config: E13Config) -> dict[str, Any]`
- [_paired_daily_delta](../../modelFactory/oracle_pre_entry_veto.py) — ligne 256 : `def _paired_daily_delta(baseline: pd.DataFrame, candidate: pd.DataFrame, config: E13Config) -> dict[str, float]`
- [_semester_stability](../../modelFactory/oracle_pre_entry_veto.py) — ligne 269 : `def _semester_stability(baseline: pd.DataFrame, candidate: pd.DataFrame) -> list[dict[str, Any]]`
- [_feature_diagnostics](../../modelFactory/oracle_pre_entry_veto.py) — ligne 285 : `def _feature_diagnostics(panel: pd.DataFrame) -> dict[str, Any]`
- [_binary_auc](../../modelFactory/oracle_pre_entry_veto.py) — ligne 305 : `def _binary_auc(labels: pd.Series, scores: pd.Series) -> float`
- [_risk_model_diagnostics](../../modelFactory/oracle_pre_entry_veto.py) — ligne 317 : `def _risk_model_diagnostics(panel: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/oracle_pre_entry_veto.py) — ligne 340 : `def run(*, oracle_gate_path: Path, output_root: Path, config: E13Config) -> Path`
- [main](../../modelFactory/oracle_pre_entry_veto.py) — ligne 473 : `def main() -> None`

## `modelFactory/oracle_prospective_journal.py`

Source SHA-256 : `f41422ee019dfaa0616be3840f4dc3567ab5aa6525755abe8c80cff9925088e8`

- [journal_freshness](../../modelFactory/oracle_prospective_journal.py) — ligne 18 : `def journal_freshness(prediction_date: str, observed_at: datetime) -> str`
- [canary_input_preflight](../../modelFactory/oracle_prospective_journal.py) — ligne 26 : `def canary_input_preflight(config: dict, prediction_date: str, observed_at: datetime, *, explicit_date: bool=False, workspace_root: Path=Path('.')) -> dict`
- [write_prospective_score_journal](../../modelFactory/oracle_prospective_journal.py) — ligne 50 : `def write_prospective_score_journal(scores: pd.DataFrame, *, artifact_dir: Path, batch_id: str, prediction_date: str, run_started_at: datetime, observed_at: datetime) -> dict`

## `modelFactory/oracle_pullback_long.py`

Source SHA-256 : `05674e5204d6926e29685cfe4c2642759f11527c3523213a72e8e7bd2226f749`

- [E10Config](../../modelFactory/oracle_pullback_long.py) — ligne 26 : `class E10Config`
- [E10Config.__post_init__](../../modelFactory/oracle_pullback_long.py) — ligne 38 : `def __post_init__(self) -> None`
- [E10Config.round_trip_cost](../../modelFactory/oracle_pullback_long.py) — ligne 49 : `def round_trip_cost(self) -> float`
- [E10Config.bootstrap_config](../../modelFactory/oracle_pullback_long.py) — ligne 52 : `def bootstrap_config(self) -> RollingConfig`
- [_normalise_events](../../modelFactory/oracle_pullback_long.py) — ligne 63 : `def _normalise_events(frame: pd.DataFrame, *, fold_column: str) -> pd.DataFrame`
- [select_pullbacks](../../modelFactory/oracle_pullback_long.py) — ligne 83 : `def select_pullbacks(events: pd.DataFrame, threshold: float) -> pd.DataFrame`
- [compare_with_delayed_long](../../modelFactory/oracle_pullback_long.py) — ligne 88 : `def compare_with_delayed_long(events: pd.DataFrame, threshold: float, config: E10Config) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [choose_discovery_threshold](../../modelFactory/oracle_pullback_long.py) — ligne 174 : `def choose_discovery_threshold(events: pd.DataFrame, config: E10Config) -> tuple[float, pd.DataFrame]`
- [build_confirmation_events](../../modelFactory/oracle_pullback_long.py) — ligne 194 : `def build_confirmation_events(predictions: pd.DataFrame, prices: pd.DataFrame, *, start_date: str, end_date: str, config: E10Config) -> pd.DataFrame`
- [evaluate_confirmation](../../modelFactory/oracle_pullback_long.py) — ligne 237 : `def evaluate_confirmation(metrics: dict[str, Any], config: E10Config) -> dict[str, Any]`
- [_profile_summary](../../modelFactory/oracle_pullback_long.py) — ligne 257 : `def _profile_summary(artifacts_root: Path, batch_id: str) -> dict[str, Any]`
- [run](../../modelFactory/oracle_pullback_long.py) — ligne 270 : `def run(*, discovery_artifact: Path, confirmation_batch_id: str, confirmation_start: str, confirmation_end: str, artifacts_root: Path, output_root: Path, config: E10Config) -> Path`
- [main](../../modelFactory/oracle_pullback_long.py) — ligne 374 : `def main() -> None`

## `modelFactory/oracle_relative_portfolio.py`

Source SHA-256 : `13be9cf9cae05c60a4355ae74be3b24b6b5bf9dc481ed0e95e5dd255f360a4d1`

- [RelativePortfolioConfig](../../modelFactory/oracle_relative_portfolio.py) — ligne 24 : `class RelativePortfolioConfig`
- [RelativePortfolioConfig.__post_init__](../../modelFactory/oracle_relative_portfolio.py) — ligne 33 : `def __post_init__(self) -> None`
- [_semester](../../modelFactory/oracle_relative_portfolio.py) — ligne 40 : `def _semester(value: pd.Timestamp) -> str`
- [_daily_cohorts](../../modelFactory/oracle_relative_portfolio.py) — ligne 45 : `def _daily_cohorts(oof: pd.DataFrame, *, horizon: int, config: RelativePortfolioConfig) -> pd.DataFrame`
- [_group_metrics](../../modelFactory/oracle_relative_portfolio.py) — ligne 91 : `def _group_metrics(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]`
- [evaluate_relative_portfolio](../../modelFactory/oracle_relative_portfolio.py) — ligne 104 : `def evaluate_relative_portfolio(oof: pd.DataFrame, *, horizon: int, config: RelativePortfolioConfig) -> tuple[pd.DataFrame, dict[str, Any]]`
- [run](../../modelFactory/oracle_relative_portfolio.py) — ligne 143 : `def run(artifact: Path, output: Path, config: RelativePortfolioConfig) -> dict[str, Any]`
- [main](../../modelFactory/oracle_relative_portfolio.py) — ligne 186 : `def main() -> None`

## `modelFactory/oracle_rolling_lifecycle.py`

Source SHA-256 : `59d084da8a3d75ca3d64328dbcf9493a4c373a853ec54a2d28a51562f19ccc80`

- [LifecycleConfig](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 31 : `class LifecycleConfig`
- [LifecycleConfig.__post_init__](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 44 : `def __post_init__(self) -> None`
- [LifecycleConfig.round_trip_cost](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 56 : `def round_trip_cost(self) -> float`
- [prepare_bars](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 60 : `def prepare_bars(bars: pd.DataFrame) -> pd.DataFrame`
- [build_delayed_candidates](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 98 : `def build_delayed_candidates(events: pd.DataFrame) -> pd.DataFrame`
- [_exit_payload](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 116 : `def _exit_payload(*, policy: str, signal_date: pd.Timestamp, symbol: str, entry_date: pd.Timestamp, entry_price: float, exit_date: pd.Timestamp, exit_price: float, exit_reason: str, holding_sessions: int, config: LifecycleConfig, checkpoints_passed: int) -> dict[str, Any]`
- [simulate_trade](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 133 : `def simulate_trade(symbol_bars: pd.DataFrame, *, signal_date: pd.Timestamp, decision_date: pd.Timestamp, policy: str, h5_rank: dict[tuple[pd.Timestamp, str], float], config: LifecycleConfig) -> dict[str, Any] | None`
- [simulate_paired](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 227 : `def simulate_paired(candidates: pd.DataFrame, bars: pd.DataFrame, aligned: pd.DataFrame, config: LifecycleConfig) -> tuple[pd.DataFrame, pd.DataFrame]`
- [summarize](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 259 : `def summarize(trades: pd.DataFrame, config: LifecycleConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- [run](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 313 : `def run(phase1_artifact: Path, *, output_root: Path, config: LifecycleConfig) -> Path`
- [main](../../modelFactory/oracle_rolling_lifecycle.py) — ligne 372 : `def main() -> None`

## `modelFactory/oracle_separability_pmath0.py`

Source SHA-256 : `aa90f3d50f0219d7686b84ae776b8bc6aa4578fea82dded8d9e095237ec3a3fd`

- [Preprocessor](../../modelFactory/oracle_separability_pmath0.py) — ligne 44 : `class Preprocessor`
- [attach_task](../../modelFactory/oracle_separability_pmath0.py) — ligne 53 : `def attach_task(frame: pd.DataFrame, task: str) -> pd.DataFrame`
- [balanced_by_date](../../modelFactory/oracle_separability_pmath0.py) — ligne 72 : `def balanced_by_date(frame: pd.DataFrame, *, max_per_class: int, seed: int) -> pd.DataFrame`
- [permute_within_date](../../modelFactory/oracle_separability_pmath0.py) — ligne 113 : `def permute_within_date(labels: np.ndarray, dates: Iterable[Any], rng: np.random.Generator) -> np.ndarray`
- [fit_preprocessor](../../modelFactory/oracle_separability_pmath0.py) — ligne 126 : `def fit_preprocessor(train: pd.DataFrame, features: list[str], *, lower_q: float, upper_q: float, max_missing_rate: float) -> Preprocessor`
- [transform](../../modelFactory/oracle_separability_pmath0.py) — ligne 156 : `def transform(frame: pd.DataFrame, preprocessor: Preprocessor) -> np.ndarray`
- [median_bandwidth](../../modelFactory/oracle_separability_pmath0.py) — ligne 164 : `def median_bandwidth(values: np.ndarray, *, max_rows: int, seed: int) -> float`
- [rff_embedding](../../modelFactory/oracle_separability_pmath0.py) — ligne 175 : `def rff_embedding(values: np.ndarray, *, bandwidth: float, components: int, seed: int) -> np.ndarray`
- [mmd2_from_embedding](../../modelFactory/oracle_separability_pmath0.py) — ligne 191 : `def mmd2_from_embedding(embedding: np.ndarray, labels: np.ndarray) -> float`
- [make_projections](../../modelFactory/oracle_separability_pmath0.py) — ligne 200 : `def make_projections(dimension: int, count: int, seed: int) -> np.ndarray`
- [sliced_energy](../../modelFactory/oracle_separability_pmath0.py) — ligne 208 : `def sliced_energy(projected: np.ndarray, labels: np.ndarray) -> float`
- [mst_edges](../../modelFactory/oracle_separability_pmath0.py) — ligne 219 : `def mst_edges(values: np.ndarray) -> np.ndarray`
- [hp_divergence](../../modelFactory/oracle_separability_pmath0.py) — ligne 225 : `def hp_divergence(labels: np.ndarray, edges: np.ndarray) -> float`
- [hp_bayes_error_bounds](../../modelFactory/oracle_separability_pmath0.py) — ligne 235 : `def hp_bayes_error_bounds(divergence: float) -> tuple[float, float]`
- [empirical_test](../../modelFactory/oracle_separability_pmath0.py) — ligne 243 : `def empirical_test(observed: float, null: list[float]) -> dict[str, float]`
- [fisher_pvalue](../../modelFactory/oracle_separability_pmath0.py) — ligne 258 : `def fisher_pvalue(values: Iterable[float]) -> float`
- [holm_adjust](../../modelFactory/oracle_separability_pmath0.py) — ligne 266 : `def holm_adjust(values: dict[str, float]) -> dict[str, float]`
- [_fold_specs](../../modelFactory/oracle_separability_pmath0.py) — ligne 281 : `def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]`
- [_split](../../modelFactory/oracle_separability_pmath0.py) — ligne 298 : `def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]`
- [audit_fold](../../modelFactory/oracle_separability_pmath0.py) — ligne 309 : `def audit_fold(train: pd.DataFrame, test: pd.DataFrame, features: list[str], *, config: dict[str, Any], seed: int) -> dict[str, Any]`
- [summarize_task](../../modelFactory/oracle_separability_pmath0.py) — ligne 380 : `def summarize_task(folds: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]`
- [apply_global_gates](../../modelFactory/oracle_separability_pmath0.py) — ligne 405 : `def apply_global_gates(summaries: dict[str, Any], gates: dict[str, Any]) -> None`
- [run](../../modelFactory/oracle_separability_pmath0.py) — ligne 451 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_separability_pmath0.py) — ligne 556 : `def main() -> None`

## `modelFactory/oracle_tradable_pit_reconstruction.py`

Source SHA-256 : `3fe4ea4093c05d5be0961254ff1db636b55cfd11c717572128a508956c14fb8b`

- [E16Config](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 53 : `class E16Config`
- [E16Config.__post_init__](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 62 : `def __post_init__(self) -> None`
- [load_instrument_reference](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 69 : `def load_instrument_reference(engine: Engine, symbols: list[str]) -> pd.DataFrame`
- [classify_instruments](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 85 : `def classify_instruments(metadata: pd.DataFrame) -> pd.DataFrame`
- [reconstruct_bar_pit_panel](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 111 : `def reconstruct_bar_pit_panel(bars: pd.DataFrame, event_keys: pd.DataFrame, instruments: pd.DataFrame, config: E16Config) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- [audit_legacy_snapshots](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 205 : `def audit_legacy_snapshots(engine: Engine, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]`
- [_e12_replay](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 241 : `def _e12_replay(events: pd.DataFrame, membership: pd.DataFrame, prepared: pd.DataFrame, config: E16Config) -> tuple[dict[str, Any], pd.DataFrame]`
- [_e15_replay](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 260 : `def _e15_replay(events: pd.DataFrame, membership: pd.DataFrame, prepared: pd.DataFrame, config: E16Config) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]`
- [run](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 298 : `def run(*, oracle_gate_path: Path, output_root: Path, config: E16Config) -> Path`
- [main](../../modelFactory/oracle_tradable_pit_reconstruction.py) — ligne 382 : `def main() -> None`

## `modelFactory/oracle_trajectory_e22.py`

Source SHA-256 : `5c5d66e925d265118d32bae5c31113ed066addfc5619b213130d41f830aa8a2e`

- [_session_order](../../modelFactory/oracle_trajectory_e22.py) — ligne 33 : `def _session_order(frame: pd.DataFrame) -> pd.Series`
- [add_ordered_lags](../../modelFactory/oracle_trajectory_e22.py) — ligne 39 : `def add_ordered_lags(frame: pd.DataFrame, source_columns: list[str], lag_sessions: int=5) -> tuple[pd.DataFrame, list[str]]`
- [_longest_signed_streak](../../modelFactory/oracle_trajectory_e22.py) — ligne 68 : `def _longest_signed_streak(values: np.ndarray) -> float`
- [add_path_shape_features](../../modelFactory/oracle_trajectory_e22.py) — ligne 83 : `def add_path_shape_features(frame: pd.DataFrame, window: int=6) -> tuple[pd.DataFrame, list[str]]`
- [_average_precision](../../modelFactory/oracle_trajectory_e22.py) — ligne 155 : `def _average_precision(y_true: pd.Series, scores: pd.Series) -> float | None`
- [summarize_oos](../../modelFactory/oracle_trajectory_e22.py) — ligne 170 : `def summarize_oos(oos: pd.DataFrame) -> dict[str, Any]`
- [_delta](../../modelFactory/oracle_trajectory_e22.py) — ligne 201 : `def _delta(value: float | None, baseline: float | None) -> float | None`
- [compare_variant](../../modelFactory/oracle_trajectory_e22.py) — ligne 205 : `def compare_variant(variant: dict[str, Any], baseline: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]`
- [build_latest_adaptive_folds](../../modelFactory/oracle_trajectory_e22.py) — ligne 247 : `def build_latest_adaptive_folds(dataset: pd.DataFrame, *, min_train_dates: int, val_dates: int, test_dates: int, step_dates: int, max_splits: int, forecast_horizon: int) -> list[dict[str, Any]]`
- [run](../../modelFactory/oracle_trajectory_e22.py) — ligne 301 : `def run(args: argparse.Namespace) -> Path`
- [main](../../modelFactory/oracle_trajectory_e22.py) — ligne 398 : `def main() -> None`

## `modelFactory/oracle_universe_audit.py`

Source SHA-256 : `b7933100f162777b51450c29590fa99dbf7e42e56112ab47db407adf6e333755`

- [parse_symbols](../../modelFactory/oracle_universe_audit.py) — ligne 30 : `def parse_symbols(raw: str | None) -> list[str]`
- [source_path](../../modelFactory/oracle_universe_audit.py) — ligne 34 : `def source_path(source: str) -> Path | None`
- [_read_symbols](../../modelFactory/oracle_universe_audit.py) — ligne 41 : `def _read_symbols(engine: Any, sql: str, symbols: list[str], **params: Any) -> pd.DataFrame`
- [_concentration](../../modelFactory/oracle_universe_audit.py) — ligne 46 : `def _concentration(values: pd.Series) -> dict[str, float | int]`
- [_safe](../../modelFactory/oracle_universe_audit.py) — ligne 58 : `def _safe(value: Any) -> Any`
- [_pct](../../modelFactory/oracle_universe_audit.py) — ligne 70 : `def _pct(value: Any) -> str`
- [run](../../modelFactory/oracle_universe_audit.py) — ligne 74 : `def run(batch_id: str, output_root: Path=OUTPUT_ROOT) -> Path`
- [main](../../modelFactory/oracle_universe_audit.py) — ligne 327 : `def main() -> None`

## `modelFactory/oracle_universe_p0e_compare.py`

Source SHA-256 : `3f2d2e503c3a6bbfef8d63fa681db764b4d091680b09e514ae7f5714b5dbbcc9`

- [load_oof](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 18 : `def load_oof(engine: Any, batch_id: str, horizon: int=20) -> pd.DataFrame`
- [daily_top_metrics](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 36 : `def daily_top_metrics(frame: pd.DataFrame, pct: float) -> pd.DataFrame`
- [summarize](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 63 : `def summarize(frame: pd.DataFrame) -> dict[str, Any]`
- [grouped_metrics](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 94 : `def grouped_metrics(frame: pd.DataFrame, column: str) -> pd.DataFrame`
- [grouped_core_metrics](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 102 : `def grouped_core_metrics(frame: pd.DataFrame, column: str) -> pd.DataFrame`
- [moving_block_interval](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 125 : `def moving_block_interval(values: pd.Series, *, seed: int=20260908) -> tuple[float, float]`
- [paired_daily_comparison](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 139 : `def paired_daily_comparison(old: pd.DataFrame, new: pd.DataFrame, pct: float) -> dict[str, Any]`
- [common_symbol_control](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 153 : `def common_symbol_control(old: pd.DataFrame, new: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 170 : `def run(old_batch: str, new_batch: str, output_root: Path, new_selection_csv: Path | None=None) -> Path`
- [main](../../modelFactory/oracle_universe_p0e_compare.py) — ligne 211 : `def main() -> None`

## `modelFactory/oracle_universe_p0i_evaluate.py`

Source SHA-256 : `ff80de804f0cefba1ce0b1eda13cf895ef464292f713c38ff2ab748dc48d46ea`

- [load_shadow](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 27 : `def load_shadow(run_dir: Path) -> pd.DataFrame`
- [prepare_evaluation](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 45 : `def prepare_evaluation(scores: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]`
- [amplitude_deciles](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 83 : `def amplitude_deciles(frame: pd.DataFrame) -> tuple[float | None, pd.DataFrame]`
- [summarize_amplitude](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 104 : `def summarize_amplitude(frame: pd.DataFrame) -> dict[str, Any]`
- [grouped_summary](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 147 : `def grouped_summary(frame: pd.DataFrame, column: str) -> pd.DataFrame`
- [universe_turnover](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 154 : `def universe_turnover(scores: pd.DataFrame) -> dict[str, float | int]`
- [selection_concentration](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 171 : `def selection_concentration(frame: pd.DataFrame, pct: float=0.2) -> dict[str, float | int]`
- [score_drift](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 187 : `def score_drift(frame: pd.DataFrame) -> dict[str, Any]`
- [direction_diagnostic](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 194 : `def direction_diagnostic(frame: pd.DataFrame, pct: float=0.2) -> dict[str, float | int]`
- [run](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 214 : `def run(shadow_dir: Path, labels_path: Path, output_root: Path, *, reference_batch: str | None=None, reference_start: str | None=None, reference_end: str | None=None) -> Path`
- [main](../../modelFactory/oracle_universe_p0i_evaluate.py) — ligne 293 : `def main() -> None`

## `modelFactory/oracle_universe_target_audit.py`

Source SHA-256 : `df452323feeb6d1afb20e879e528c522c354614c7698661cb67ded0bfadf69f7`

- [_rank](../../modelFactory/oracle_universe_target_audit.py) — ligne 21 : `def _rank(frame: pd.DataFrame, score: str, groups: list[str]) -> pd.Series`
- [_top_share](../../modelFactory/oracle_universe_target_audit.py) — ligne 25 : `def _top_share(counts: pd.Series, fraction: float=0.2) -> float`
- [_variant_metrics](../../modelFactory/oracle_universe_target_audit.py) — ligne 31 : `def _variant_metrics(frame: pd.DataFrame, prefix: str, raw_extreme: pd.Series) -> dict[str, Any]`
- [run](../../modelFactory/oracle_universe_target_audit.py) — ligne 77 : `def run(labels_path: Path, output_root: Path, min_sector_members: int=20) -> Path`
- [main](../../modelFactory/oracle_universe_target_audit.py) — ligne 190 : `def main() -> None`

## `modelFactory/orchestrator.py`

Source SHA-256 : `619e2162cdc1c9846279d47b2a3c71af9ab481dac9e95bbfabd78c76ce08e404`

- [get_last_liquidity_diagnostics](../../modelFactory/orchestrator.py) — ligne 56 : `def get_last_liquidity_diagnostics() -> dict[str, Any]`
- [_oracle_requires_global_rank](../../modelFactory/orchestrator.py) — ligne 65 : `def _oracle_requires_global_rank(cfg: TrainingConfig) -> bool`
- [_oracle_generator_options](../../modelFactory/orchestrator.py) — ligne 70 : `def _oracle_generator_options(cfg: TrainingConfig, profile: dict[str, Any] | None) -> dict[str, Any]`
- [_insufficient_oracle_universe_reason](../../modelFactory/orchestrator.py) — ligne 98 : `def _insufficient_oracle_universe_reason(symbols: list[str]) -> str | None`
- [_with_batch_artifacts_dir](../../modelFactory/orchestrator.py) — ligne 111 : `def _with_batch_artifacts_dir(cfg: TrainingConfig, batch_id: str) -> TrainingConfig`
- [_inject_global_model_into_symbol_artifacts](../../modelFactory/orchestrator.py) — ligne 123 : `def _inject_global_model_into_symbol_artifacts(symbol: str, cfg: TrainingConfig, global_result: dict, engine: Engine | None=None) -> None`
- [_gpu_requested_or_available](../../modelFactory/orchestrator.py) — ligne 248 : `def _gpu_requested_or_available(cfg: TrainingConfig) -> bool`
- [_filter_symbols_by_mode](../../modelFactory/orchestrator.py) — ligne 252 : `def _filter_symbols_by_mode(engine: Engine, symbols: list[str], *, mode: str, cfg: TrainingConfig) -> list[str]`
- [_train_worker](../../modelFactory/orchestrator.py) — ligne 381 : `def _train_worker(symbol: str, cfg: TrainingConfig, universe_symbols: list[str] | None=None, *, cross_sectional_cache: pd.DataFrame | None=None, fundamental_cache: pd.DataFrame | None=None, batch_id: str | None=None) -> TrainResult`
- [train_oracle_extreme](../../modelFactory/orchestrator.py) — ligne 542 : `def train_oracle_extreme(cfg: TrainingConfig, engine: Engine, batch_id: str, symbols: Optional[list[str]] | None=None) -> dict[str, Any]`
- [run_training_batch](../../modelFactory/orchestrator.py) — ligne 803 : `def run_training_batch(cfg: TrainingConfig, engine: Engine, symbols: Optional[list[str]]=None, *, mode: str='rebuild-all', symbol_source: SymbolSource='tradable-universe', universe_date: date | None=None, start_symbol: str | None=None, batch_id: str | None=None) -> list[TrainResult]`

## `modelFactory/path_aware_directional.py`

Source SHA-256 : `a60770acc52373e0584733928ff1352829433f408734882a59dbe4f219983621`

- [BarrierRaceConfig](../../modelFactory/path_aware_directional.py) — ligne 57 : `class BarrierRaceConfig`
- [BarrierRaceConfig.__post_init__](../../modelFactory/path_aware_directional.py) — ligne 71 : `def __post_init__(self) -> None`
- [BarrierRaceConfig.labeler_kwargs](../../modelFactory/path_aware_directional.py) — ligne 76 : `def labeler_kwargs(self) -> dict[str, Any]`
- [build_path_label_panel](../../modelFactory/path_aware_directional.py) — ligne 92 : `def build_path_label_panel(bars: pd.DataFrame, config: BarrierRaceConfig) -> pd.DataFrame`
- [attach_path_targets](../../modelFactory/path_aware_directional.py) — ligne 145 : `def attach_path_targets(oracle_pool: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame`
- [_head_metrics](../../modelFactory/path_aware_directional.py) — ligne 157 : `def _head_metrics(work: pd.DataFrame, target: str, probability: str) -> dict[str, Any]`
- [_concentration](../../modelFactory/path_aware_directional.py) — ligne 167 : `def _concentration(selected: pd.DataFrame, return_col: str) -> dict[str, Any]`
- [_side_metrics](../../modelFactory/path_aware_directional.py) — ligne 183 : `def _side_metrics(selected: pd.DataFrame, pool: pd.DataFrame, *, side: str) -> dict[str, Any]`
- [evaluate_path_aware_oos](../../modelFactory/path_aware_directional.py) — ligne 214 : `def evaluate_path_aware_oos(frame: pd.DataFrame, top_fraction: float=0.1) -> dict[str, Any]`
- [_fold_stability](../../modelFactory/path_aware_directional.py) — ligne 275 : `def _fold_stability(folds: list[dict[str, Any]], overall: dict[str, Any]) -> dict[str, Any]`
- [train_path_aware](../../modelFactory/path_aware_directional.py) — ligne 310 : `def train_path_aware(dataset: pd.DataFrame, feature_columns: list[str], categorical_columns: list[str], config: SharedDirectionalConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_path_aware_campaign](../../modelFactory/path_aware_directional.py) — ligne 426 : `def run_path_aware_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, training_config: SharedDirectionalConfig | None=None, barrier_config: BarrierRaceConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_format_summary](../../modelFactory/path_aware_directional.py) — ligne 559 : `def _format_summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/path_aware_directional.py) — ligne 579 : `def main() -> None`

## `modelFactory/path_aware_utility.py`

Source SHA-256 : `092c96cc191c56807f3b48d78ecdb60169717c9797cb31bff88356ff5cb80a48`

- [EconomicUtilityConfig](../../modelFactory/path_aware_utility.py) — ligne 59 : `class EconomicUtilityConfig`
- [EconomicUtilityConfig.__post_init__](../../modelFactory/path_aware_utility.py) — ligne 68 : `def __post_init__(self) -> None`
- [_catboost_common](../../modelFactory/path_aware_utility.py) — ligne 79 : `def _catboost_common(config: SharedDirectionalConfig, iterations: int | None) -> dict[str, Any]`
- [target_winsor_bounds](../../modelFactory/path_aware_utility.py) — ligne 95 : `def target_winsor_bounds(train: pd.DataFrame, target_column: str, config: EconomicUtilityConfig) -> tuple[float, float]`
- [_fit_return_model](../../modelFactory/path_aware_utility.py) — ligne 111 : `def _fit_return_model(train: pd.DataFrame, valid: pd.DataFrame | None, feature_columns: list[str], categorical_columns: list[str], training: SharedDirectionalConfig, utility: EconomicUtilityConfig, target_column: str, *, iterations: int | None=None, bounds: tuple[float, float] | None=None) -> tuple[Any, tuple[float, float]]`
- [_fit_tail_risk_model](../../modelFactory/path_aware_utility.py) — ligne 146 : `def _fit_tail_risk_model(train: pd.DataFrame, valid: pd.DataFrame | None, feature_columns: list[str], categorical_columns: list[str], training: SharedDirectionalConfig, utility: EconomicUtilityConfig, target_column: str, *, iterations: int | None=None) -> Any`
- [add_economic_scores](../../modelFactory/path_aware_utility.py) — ligne 191 : `def add_economic_scores(frame: pd.DataFrame, config: EconomicUtilityConfig) -> pd.DataFrame`
- [_mean_daily_spearman](../../modelFactory/path_aware_utility.py) — ligne 211 : `def _mean_daily_spearman(frame: pd.DataFrame, score_col: str, return_col: str) -> float | None`
- [_cvar](../../modelFactory/path_aware_utility.py) — ligne 220 : `def _cvar(values: pd.Series, fraction: float=0.05) -> float | None`
- [_concentration](../../modelFactory/path_aware_utility.py) — ligne 228 : `def _concentration(selected: pd.DataFrame, return_col: str) -> dict[str, Any]`
- [_economic_side_metrics](../../modelFactory/path_aware_utility.py) — ligne 244 : `def _economic_side_metrics(selected: pd.DataFrame, pool: pd.DataFrame, *, side: str, config: EconomicUtilityConfig) -> dict[str, Any]`
- [evaluate_economic_oos](../../modelFactory/path_aware_utility.py) — ligne 293 : `def evaluate_economic_oos(frame: pd.DataFrame, config: EconomicUtilityConfig | None=None) -> dict[str, Any]`
- [_fold_stability](../../modelFactory/path_aware_utility.py) — ligne 330 : `def _fold_stability(folds: list[dict[str, Any]], overall: dict[str, Any]) -> dict[str, Any]`
- [_best_iterations](../../modelFactory/path_aware_utility.py) — ligne 363 : `def _best_iterations(model: Any) -> int`
- [train_path_utility](../../modelFactory/path_aware_utility.py) — ligne 368 : `def train_path_utility(dataset: pd.DataFrame, feature_columns: list[str], categorical_columns: list[str], training: SharedDirectionalConfig, utility: EconomicUtilityConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_path_utility_campaign](../../modelFactory/path_aware_utility.py) — ligne 516 : `def run_path_utility_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, training_config: SharedDirectionalConfig | None=None, barrier_config: BarrierRaceConfig | None=None, utility_config: EconomicUtilityConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_format_summary](../../modelFactory/path_aware_utility.py) — ligne 619 : `def _format_summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/path_aware_utility.py) — ligne 638 : `def main() -> None`

## `modelFactory/path_risk_direction.py`

Source SHA-256 : `83d790d2090c9a7edfb3be9443a454d8352d44ca01b63df07aea07cc96be74fc`

- [RiskDirectionConfig](../../modelFactory/path_risk_direction.py) — ligne 36 : `class RiskDirectionConfig`
- [RiskDirectionConfig.__post_init__](../../modelFactory/path_risk_direction.py) — ligne 43 : `def __post_init__(self) -> None`
- [add_daily_risk_asymmetry](../../modelFactory/path_risk_direction.py) — ligne 52 : `def add_daily_risk_asymmetry(frame: pd.DataFrame) -> pd.DataFrame`
- [apply_direction_policy](../../modelFactory/path_risk_direction.py) — ligne 68 : `def apply_direction_policy(frame: pd.DataFrame, margin: float) -> pd.DataFrame`
- [_cvar](../../modelFactory/path_risk_direction.py) — ligne 88 : `def _cvar(values: pd.Series, fraction: float=0.05) -> float | None`
- [_concentration](../../modelFactory/path_risk_direction.py) — ligne 96 : `def _concentration(selected: pd.DataFrame) -> dict[str, Any]`
- [_policy_metrics](../../modelFactory/path_risk_direction.py) — ligne 112 : `def _policy_metrics(policy_frame: pd.DataFrame, config: RiskDirectionConfig) -> dict[str, Any]`
- [evaluate_risk_direction](../../modelFactory/path_risk_direction.py) — ligne 165 : `def evaluate_risk_direction(frame: pd.DataFrame, config: RiskDirectionConfig | None=None, margins: tuple[float, ...]=DIAGNOSTIC_MARGINS) -> dict[str, Any]`
- [_stability](../../modelFactory/path_risk_direction.py) — ligne 186 : `def _stability(frame: pd.DataFrame, config: RiskDirectionConfig) -> dict[str, Any]`
- [_gates](../../modelFactory/path_risk_direction.py) — ligne 216 : `def _gates(primary: dict[str, Any], stability: dict[str, Any], config: RiskDirectionConfig) -> dict[str, Any]`
- [_semesters](../../modelFactory/path_risk_direction.py) — ligne 242 : `def _semesters(frame: pd.DataFrame, config: RiskDirectionConfig) -> dict[str, Any]`
- [run_risk_direction_campaign](../../modelFactory/path_risk_direction.py) — ligne 253 : `def run_risk_direction_campaign(utility_artifact: Path, *, output_root: Path | None=None, config: RiskDirectionConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/path_risk_direction.py) — ligne 293 : `def _summary(path: Path, report: dict[str, Any]) -> str`
- [main](../../modelFactory/path_risk_direction.py) — ligne 309 : `def main() -> None`

## `modelFactory/path_risk_veto.py`

Source SHA-256 : `dc6e39dd507b85f9002a709ef957db6d80c47f43b8a1f3770a22f5ae00bb6242`

- [RiskVetoConfig](../../modelFactory/path_risk_veto.py) — ligne 31 : `class RiskVetoConfig`
- [RiskVetoConfig.__post_init__](../../modelFactory/path_risk_veto.py) — ligne 39 : `def __post_init__(self) -> None`
- [_cvar](../../modelFactory/path_risk_veto.py) — ligne 50 : `def _cvar(values: pd.Series, fraction: float=0.05) -> float | None`
- [_veto_mask](../../modelFactory/path_risk_veto.py) — ligne 58 : `def _veto_mask(frame: pd.DataFrame, risk_column: str, fraction: float) -> pd.Series`
- [add_daily_risk_vetoes](../../modelFactory/path_risk_veto.py) — ligne 77 : `def add_daily_risk_vetoes(frame: pd.DataFrame, fractions: tuple[float, ...]=DIAGNOSTIC_VETO_FRACTIONS) -> pd.DataFrame`
- [_concentration](../../modelFactory/path_risk_veto.py) — ligne 88 : `def _concentration(frame: pd.DataFrame, return_column: str) -> dict[str, Any]`
- [_metrics](../../modelFactory/path_risk_veto.py) — ligne 104 : `def _metrics(frame: pd.DataFrame, return_column: str, config: RiskVetoConfig) -> dict[str, Any]`
- [_comparison](../../modelFactory/path_risk_veto.py) — ligne 126 : `def _comparison(baseline: pd.DataFrame, selected: pd.DataFrame, return_column: str, config: RiskVetoConfig) -> dict[str, Any]`
- [_candidate_sets](../../modelFactory/path_risk_veto.py) — ligne 163 : `def _candidate_sets(frame: pd.DataFrame, top_fraction: float) -> dict[str, dict[str, pd.DataFrame]]`
- [evaluate_risk_veto](../../modelFactory/path_risk_veto.py) — ligne 179 : `def evaluate_risk_veto(frame: pd.DataFrame, config: RiskVetoConfig | None=None, fractions: tuple[float, ...]=DIAGNOSTIC_VETO_FRACTIONS) -> dict[str, Any]`
- [_stability_for_policy](../../modelFactory/path_risk_veto.py) — ligne 210 : `def _stability_for_policy(frame: pd.DataFrame, policy: str, side: str, config: RiskVetoConfig) -> dict[str, Any]`
- [_gates](../../modelFactory/path_risk_veto.py) — ligne 248 : `def _gates(primary: dict[str, Any], stability: dict[str, Any], config: RiskVetoConfig) -> dict[str, Any]`
- [_semester_results](../../modelFactory/path_risk_veto.py) — ligne 277 : `def _semester_results(frame: pd.DataFrame, config: RiskVetoConfig) -> dict[str, Any]`
- [load_oof_inputs](../../modelFactory/path_risk_veto.py) — ligne 299 : `def load_oof_inputs(utility_artifact: Path, directional_artifact: Path | None) -> pd.DataFrame`
- [run_risk_veto_campaign](../../modelFactory/path_risk_veto.py) — ligne 315 : `def run_risk_veto_campaign(utility_artifact: Path, *, directional_artifact: Path | None=None, output_root: Path | None=None, config: RiskVetoConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_summary](../../modelFactory/path_risk_veto.py) — ligne 362 : `def _summary(path: Path, report: dict[str, Any]) -> str`
- [main](../../modelFactory/path_risk_veto.py) — ligne 379 : `def main() -> None`

## `modelFactory/position_keep_exit_dataset.py`

Source SHA-256 : `8d32288fae415344214473899d65edcdd70c382552ef13e59220a04bee8eea70`

- [KeepExitDatasetConfig](../../modelFactory/position_keep_exit_dataset.py) — ligne 52 : `class KeepExitDatasetConfig`
- [KeepExitDatasetConfig.__post_init__](../../modelFactory/position_keep_exit_dataset.py) — ligne 62 : `def __post_init__(self) -> None`
- [KeepExitDatasetConfig.round_trip_cost](../../modelFactory/position_keep_exit_dataset.py) — ligne 72 : `def round_trip_cost(self) -> float`
- [_sha256](../../modelFactory/position_keep_exit_dataset.py) — ligne 76 : `def _sha256(path: Path) -> str`
- [prepare_oracle_features](../../modelFactory/position_keep_exit_dataset.py) — ligne 84 : `def prepare_oracle_features(aligned: pd.DataFrame) -> pd.DataFrame`
- [prepare_market_features](../../modelFactory/position_keep_exit_dataset.py) — ligne 106 : `def prepare_market_features(spy_bars: pd.DataFrame) -> pd.DataFrame`
- [_safe_return](../../modelFactory/position_keep_exit_dataset.py) — ligne 120 : `def _safe_return(end: float, start: float) -> float`
- [build_position_states](../../modelFactory/position_keep_exit_dataset.py) — ligne 124 : `def build_position_states(fixed_trades: pd.DataFrame, bars: pd.DataFrame, oracle: pd.DataFrame, *, config: KeepExitDatasetConfig) -> pd.DataFrame`
- [audit_univariate](../../modelFactory/position_keep_exit_dataset.py) — ligne 280 : `def audit_univariate(states: pd.DataFrame, *, min_states: int) -> pd.DataFrame`
- [summarize_quality](../../modelFactory/position_keep_exit_dataset.py) — ligne 303 : `def summarize_quality(states: pd.DataFrame) -> dict[str, Any]`
- [run](../../modelFactory/position_keep_exit_dataset.py) — ligne 334 : `def run(lifecycle_artifact: Path, *, output_root: Path, config: KeepExitDatasetConfig) -> Path`
- [main](../../modelFactory/position_keep_exit_dataset.py) — ligne 392 : `def main() -> None`

## `modelFactory/position_keep_exit_walk_forward.py`

Source SHA-256 : `ba698883072ca67928ade2c84bd3ea37f285f1d8983b7f884bc8c8771804f4fd`

- [WalkForwardConfig](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 39 : `class WalkForwardConfig`
- [WalkForwardConfig.__post_init__](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 48 : `def __post_init__(self) -> None`
- [build_purged_folds](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 56 : `def build_purged_folds(states: pd.DataFrame, config: WalkForwardConfig) -> list[dict[str, Any]]`
- [equal_trade_weights](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 104 : `def equal_trade_weights(frame: pd.DataFrame) -> np.ndarray`
- [_finite_matrix](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 110 : `def _finite_matrix(frame: pd.DataFrame) -> pd.DataFrame`
- [fit_platt](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 114 : `def fit_platt(y: np.ndarray, raw_probability: np.ndarray, weights: np.ndarray) -> LogisticRegression | None`
- [apply_platt](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 124 : `def apply_platt(calibrator: LogisticRegression | None, raw_probability: np.ndarray) -> np.ndarray`
- [fit_predict_models](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 132 : `def fit_predict_models(train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame, *, seed: int) -> dict[str, dict[str, np.ndarray]]`
- [replay_first_exit](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 194 : `def replay_first_exit(states: pd.DataFrame, scores: np.ndarray, *, threshold: float) -> pd.DataFrame`
- [select_threshold](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 223 : `def select_threshold(validation: pd.DataFrame, scores: np.ndarray, *, classifier: bool) -> dict[str, float]`
- [_safe_auc](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 248 : `def _safe_auc(y: pd.Series, scores: np.ndarray) -> float`
- [run_walk_forward](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 252 : `def run_walk_forward(states: pd.DataFrame, config: WalkForwardConfig) -> tuple[pd.DataFrame, pd.DataFrame]`
- [summarize](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 310 : `def summarize(policy_trades: pd.DataFrame, folds: pd.DataFrame, config: WalkForwardConfig) -> dict[str, Any]`
- [run](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 348 : `def run(dataset_artifact: Path, *, output_root: Path, config: WalkForwardConfig) -> Path`
- [main](../../modelFactory/position_keep_exit_walk_forward.py) — ligne 393 : `def main() -> None`

## `modelFactory/predict_per_sector.py`

Source SHA-256 : `015f6850df6c31a9c5a2eeb3530b6084e922ac8faa3e5d246ea6847dfd9c49df`

- [_last_bar_date](../../modelFactory/predict_per_sector.py) — ligne 33 : `def _last_bar_date() -> date | None`
- [_parse_args](../../modelFactory/predict_per_sector.py) — ligne 44 : `def _parse_args(argv: list[str]) -> tuple[str, int, str, date | None, date | None]`
- [main](../../modelFactory/predict_per_sector.py) — ligne 77 : `def main() -> None`

## `modelFactory/predictor.py`

Source SHA-256 : `5053a2791fe2feee17680c0a456215b15367b7e483756026b2a63ab48d43d49e`

- [_batch_has_per_symbol_or_sector](../../modelFactory/predictor.py) — ligne 73 : `def _batch_has_per_symbol_or_sector(engine: 'Engine', batch_id: str | None) -> bool`
- [ArtifactIntegrityError](../../modelFactory/predictor.py) — ligne 128 : `class ArtifactIntegrityError(RuntimeError)`
- [ArtifactIntegrityError.__init__](../../modelFactory/predictor.py) — ligne 131 : `def __init__(self, reason: str, *, path: Path | None=None) -> None`
- [_record_db_issue](../../modelFactory/predictor.py) — ligne 137 : `def _record_db_issue(*, operation: str, symbol: str | None=None, reason: str) -> None`
- [_record_artifact_issue](../../modelFactory/predictor.py) — ligne 151 : `def _record_artifact_issue(symbol: str, *, reason: str, path: Path | None=None) -> None`
- [_record_prediction_fallback](../../modelFactory/predictor.py) — ligne 160 : `def _record_prediction_fallback(symbol: str, *, requested_model: object, served_model: object, reason: str) -> None`
- [_load_json_dict](../../modelFactory/predictor.py) — ligne 176 : `def _load_json_dict(path: Path, *, symbol: str, artifact_kind: str) -> dict[str, Any]`
- [_load_optional_calibrator](../../modelFactory/predictor.py) — ligne 203 : `def _load_optional_calibrator(calibrator_path: Path | None, *, symbol: str, selected_model: str) -> Any`
- [_apply_optional_calibration](../../modelFactory/predictor.py) — ligne 231 : `def _apply_optional_calibration(*, symbol: str, selected_model: str, calibrator: Any, margin: np.ndarray, calibrator_path: Path | None, raw_proba: float) -> tuple[float, str]`
- [_apply_optional_multiclass_calibration](../../modelFactory/predictor.py) — ligne 267 : `def _apply_optional_multiclass_calibration(*, symbol: str, selected_model: str, calibrator: Any, raw_probabilities: np.ndarray, calibrator_path: Path | None, logits: np.ndarray | None=None) -> tuple[np.ndarray, str]`
- [_extract_positive_class_probability](../../modelFactory/predictor.py) — ligne 321 : `def _extract_positive_class_probability(prediction_output: Any, *, symbol: str, selected_model: str, model_path: Path, target_mode: str='binary') -> float`
- [_persist_predictions_best_effort](../../modelFactory/predictor.py) — ligne 364 : `def _persist_predictions_best_effort(engine: 'Engine', result: pd.DataFrame, *, symbol: str) -> None`
- [_path_from_value](../../modelFactory/predictor.py) — ligne 383 : `def _path_from_value(value: object) -> Path | None`
- [_numeric_threshold](../../modelFactory/predictor.py) — ligne 391 : `def _numeric_threshold(value: object, default: float) -> float`
- [_resolve_route_decision_threshold](../../modelFactory/predictor.py) — ligne 400 : `def _resolve_route_decision_threshold(route: dict[str, object], cfg_data: dict[str, Any]) -> float | None`
- [_resolve_artifact_signature_manifest_path](../../modelFactory/predictor.py) — ligne 407 : `def _resolve_artifact_signature_manifest_path(cfg_data: dict[str, Any], *, config_path: Path) -> Path`
- [_verify_route_signature_if_needed](../../modelFactory/predictor.py) — ligne 413 : `def _verify_route_signature_if_needed(*, cfg_data: dict[str, Any], route: dict[str, object], manifest_path: Path, symbol: str) -> None`
- [_build_prediction_result](../../modelFactory/predictor.py) — ligne 443 : `def _build_prediction_result(*, symbol: str, prediction_date: date, proba: float, pred_class: int, run_id: str, raw_proba: float, decision_threshold: float, signal_label: str, calibration_method: str, selected_model: str, predicted_side: str | None=None, proba_long: float | None=None, proba_flat: float | None=None, proba_short: float | None=None, decision_policy_version: int=1, decision_reason: str | None=None, data_availability: DataAvailabilityInfo | None=None, data_quality: QualityState=QualityState.PRESENT, source: str | None=None) -> pd.DataFrame`
- [_has_matching_latest_feature_date](../../modelFactory/predictor.py) — ligne 500 : `def _has_matching_latest_feature_date(df: pd.DataFrame, cutoff_date: date | None) -> bool`
- [_pit_validate_bars](../../modelFactory/predictor.py) — ligne 512 : `def _pit_validate_bars(bars: pd.DataFrame, *, symbol: str, cutoff_date: date | None) -> None`
- [_pit_build_availability](../../modelFactory/predictor.py) — ligne 560 : `def _pit_build_availability(bars: pd.DataFrame, *, symbol: str, cutoff_date: date | None, source: str='eodhd') -> DataAvailabilityInfo | None`
- [_record_route_fallback_if_any](../../modelFactory/predictor.py) — ligne 585 : `def _record_route_fallback_if_any(symbol: str, route: dict[str, object]) -> None`
- [_resolve_inference_device](../../modelFactory/predictor.py) — ligne 604 : `def _resolve_inference_device(accelerator: str='auto') -> torch.device`
- [_resolve_artifact_paths](../../modelFactory/predictor.py) — ligne 621 : `def _resolve_artifact_paths(symbol: str, artifacts_dir: Path, engine: 'Engine', run_id: Optional[str], batch_id: Optional[str]=None) -> tuple[Path, Path, Path, Optional[str]]`
- [_classify_prediction_source](../../modelFactory/predictor.py) — ligne 696 : `def _classify_prediction_source(engine: 'Engine', symbol: str, selected_run_id: str | None) -> str`
- [_resolve_sector_run](../../modelFactory/predictor.py) — ligne 728 : `def _resolve_sector_run(engine: 'Engine', symbol: str, batch_id: str | None=None) -> dict | None`
- [_check_feature_contract](../../modelFactory/predictor.py) — ligne 801 : `def _check_feature_contract(cfg_data: dict, *, symbol: str, config_path: Path) -> str | None`
- [_LightGBMBoosterAdapter](../../modelFactory/predictor.py) — ligne 850 : `class _LightGBMBoosterAdapter`
- [_LightGBMBoosterAdapter.__init__](../../modelFactory/predictor.py) — ligne 853 : `def __init__(self, booster: Any) -> None`
- [_LightGBMBoosterAdapter.predict_proba](../../modelFactory/predictor.py) — ligne 856 : `def predict_proba(self, X: Any) -> np.ndarray`
- [_LightGBMBoosterAdapter.predict](../../modelFactory/predictor.py) — ligne 862 : `def predict(self, X: Any) -> np.ndarray`
- [_load_tabular_model](../../modelFactory/predictor.py) — ligne 868 : `def _load_tabular_model(model_path: Path, *, selected_model: str) -> Any`
- [_cached_tabular_model](../../modelFactory/predictor.py) — ligne 901 : `def _cached_tabular_model(model_path_str: str, cache_token: tuple[int, int], selected_model: str) -> Any`
- [_cached_scaler](../../modelFactory/predictor.py) — ligne 906 : `def _cached_scaler(scaler_path_str: str, cache_token: tuple[int, int]) -> Any`
- [_cached_calibrator](../../modelFactory/predictor.py) — ligne 912 : `def _cached_calibrator(calibrator_path_str: str, cache_token: tuple[int, int]) -> Any`
- [_cached_lstm_module](../../modelFactory/predictor.py) — ligne 918 : `def _cached_lstm_module(ckpt_path_str: str, cache_token: tuple[int, int], device_str: str) -> Any`
- [_safe_cache_token](../../modelFactory/predictor.py) — ligne 927 : `def _safe_cache_token(path: Path) -> tuple[int, int]`
- [load_tabular_model_cached](../../modelFactory/predictor.py) — ligne 935 : `def load_tabular_model_cached(model_path: Path, *, selected_model: str) -> Any`
- [load_scaler_cached](../../modelFactory/predictor.py) — ligne 940 : `def load_scaler_cached(scaler_path: Path) -> Any`
- [load_calibrator_cached](../../modelFactory/predictor.py) — ligne 944 : `def load_calibrator_cached(calibrator_path: Path) -> Any`
- [load_lstm_module_cached](../../modelFactory/predictor.py) — ligne 948 : `def load_lstm_module_cached(ckpt_path: Path, device: Any) -> Any`
- [clear_model_cache](../../modelFactory/predictor.py) — ligne 952 : `def clear_model_cache() -> None`
- [clear_prediction_data_cache](../../modelFactory/predictor.py) — ligne 960 : `def clear_prediction_data_cache() -> None`
- [_load_benchmark_bars_cached](../../modelFactory/predictor.py) — ligne 975 : `def _load_benchmark_bars_cached(engine: 'Engine', benchmark_symbol: str, *, cutoff_date: date | None) -> pd.DataFrame`
- [_load_cross_sectional_features_cached](../../modelFactory/predictor.py) — ligne 1002 : `def _load_cross_sectional_features_cached(engine: 'Engine', *, required_symbol: str, cutoff_date: date | None, benchmark_symbol: str, benchmark_df: pd.DataFrame | None, min_universe_size: int, feature_subset: list[str] | None=None, sector_map: dict[str, str] | None=None) -> pd.DataFrame`
- [_resolve_selected_model_route](../../modelFactory/predictor.py) — ligne 1063 : `def _resolve_selected_model_route(cfg_data: dict, ckpt_path: Path, scaler_path: Path, config_path: Path) -> dict[str, object]`
- [_build_lstm_fallback_route](../../modelFactory/predictor.py) — ligne 1124 : `def _build_lstm_fallback_route(cfg_data: dict, *, ckpt_path: Path, scaler_path: Path, config_path: Path, requested_model: object, reason: str) -> dict[str, object]`
- [_load_data_cfg_from_payload](../../modelFactory/predictor.py) — ligne 1150 : `def _load_data_cfg_from_payload(cfg_data: dict, *, ps_features: dict[str, Any] | None=None) -> DataConfig`
- [_prepare_prediction_frame](../../modelFactory/predictor.py) — ligne 1195 : `def _prepare_prediction_frame(symbol: str, *, data_cfg: DataConfig, engine: 'Engine', cutoff_date: date | None, include_global_stacking: bool=False) -> pd.DataFrame`
- [_predict_with_global_model](../../modelFactory/predictor.py) — ligne 1360 : `def _predict_with_global_model(symbol: str, *, cfg_data: dict, config_path: Path, model_path: Path, calibrator_path: Path | None, engine: 'Engine', prediction_date: date | None, as_of_date: date | None, persist: bool, ps_features: dict[str, Any] | None=None, source: str | None=None) -> Optional[pd.DataFrame]`
- [_predict_with_tabular_model](../../modelFactory/predictor.py) — ligne 1392 : `def _predict_with_tabular_model(symbol: str, *, selected_model: str, cfg_data: dict, model_path: Path, calibrator_path: Path | None, engine: 'Engine', prediction_date: date | None, as_of_date: date | None, persist: bool, feature_columns: list[str] | None=None, decision_threshold: float | None=None, config_path: Path | None=None, route_feature_fingerprint: object=None, route_feature_contract: object=None, ps_features: dict[str, Any] | None=None, source: str | None=None) -> Optional[pd.DataFrame]`
- [predict_symbol](../../modelFactory/predictor.py) — ligne 1736 : `def predict_symbol(symbol: str, artifacts_dir: Path, engine: 'Engine', prediction_date: Optional[date]=None, run_id: Optional[str]=None, batch_id: Optional[str]=None, as_of_date: Optional[date]=None, persist: bool=True, accelerator: str='auto') -> Optional[pd.DataFrame]`
- [_directional_bundle_root](../../modelFactory/predictor.py) — ligne 2227 : `def _directional_bundle_root(artifacts_dir: Path, batch_id: str | None) -> Path | None`
- [DirectionalBundleContractError](../../modelFactory/predictor.py) — ligne 2243 : `class DirectionalBundleContractError(RuntimeError)`
- [_resolve_bundle_artifact_path](../../modelFactory/predictor.py) — ligne 2247 : `def _resolve_bundle_artifact_path(bundle_root: Path, config_path: Path, value: Any) -> Path | None`
- [validate_directional_bundle_for_prediction](../../modelFactory/predictor.py) — ligne 2255 : `def validate_directional_bundle_for_prediction(bundle_root: Path, symbols: list[str], *, require_oracle: bool=True) -> tuple[list[str], dict[str, list[str]]]`
- [predict_directional_symbol](../../modelFactory/predictor.py) — ligne 2353 : `def predict_directional_symbol(symbol: str, bundle_root: Path, engine: 'Engine', prediction_date: Optional[date]=None, as_of_date: Optional[date]=None, persist: bool=True, accelerator: str='auto') -> Optional[pd.DataFrame]`
- [load_cascade_config](../../modelFactory/predictor.py) — ligne 2452 : `def load_cascade_config() -> dict[str, Any]`
- [load_extreme_gate_config](../../modelFactory/predictor.py) — ligne 2494 : `def load_extreme_gate_config() -> dict[str, Any]`
- [load_per_symbol_features](../../modelFactory/predictor.py) — ligne 2537 : `def load_per_symbol_features(artifacts_dir: Path) -> dict[str, Any]`
- [upsert_global_ranks](../../modelFactory/predictor.py) — ligne 2579 : `def upsert_global_ranks(batch_id: str, trade_date: str, ranks: list[dict[str, Any]], engine: Any | None=None) -> int`
- [resolve_global_rank_artifacts_dir](../../modelFactory/predictor.py) — ligne 2658 : `def resolve_global_rank_artifacts_dir(artifacts_dir: Path, batch_id: str) -> Path`
- [predict_global_rank_history](../../modelFactory/predictor.py) — ligne 2671 : `def predict_global_rank_history(start_date: str, end_date: str, batch_id: str, *, artifacts_dir: Path | None=None, engine: Any | None=None, symbols: list[str] | None=None) -> dict[str, int]`
- [compute_per_symbol_cross_sectional_ic](../../modelFactory/predictor.py) — ligne 2819 : `def compute_per_symbol_cross_sectional_ic(engine: Any, batch_id: str, *, horizon: int=5, min_symbols_per_date: int=10) -> dict[str, Any]`
- [CascadePrediction](../../modelFactory/predictor.py) — ligne 2943 : `class CascadePrediction`
- [load_global_ranks_from_db](../../modelFactory/predictor.py) — ligne 2952 : `def load_global_ranks_from_db(trade_date: str, batch_id: str, *, engine: Any | None=None) -> pd.DataFrame`
- [_load_best_horizon_for_batch](../../modelFactory/predictor.py) — ligne 3019 : `def _load_best_horizon_for_batch(batch_id: str, *, engine: Any | None=None) -> int | None`
- [_load_momentum_for_symbols](../../modelFactory/predictor.py) — ligne 3046 : `def _load_momentum_for_symbols(trade_date: str, symbols: list[str], *, engine: Any | None=None) -> dict[str, tuple[float | None, float | None]]`
- [prepare_oracle_tradable_percentiles](../../modelFactory/predictor.py) — ligne 3097 : `def prepare_oracle_tradable_percentiles(scores: dict[str, float], *, tradable_symbols: set[str] | None=None, policy: str='off') -> tuple[dict[str, float], dict[str, int | str]]`
- [cascade_select](../../modelFactory/predictor.py) — ligne 3142 : `def cascade_select(trade_date: str, batch_id: str, per_symbol_preds: dict[str, CascadePrediction], *, top_pct: float | None=None, min_prob: float | None=None, engine: Any | None=None, best_h: int | None=None, short_momentum_filter: str | None=None, short_momentum_max_pct: float | None=None, rank_mode: str='ml', rank_seed: int=42, oracle_rank_map: dict[str, dict[str, float]] | None=None, oracle_filter_pct: float | None=None, oracle_pool_pct: float | None=None, extreme_gate_pct: float | None=None, extreme_gate_per_symbol: str='filter', extreme_gate_shorts: bool=False, extreme_gate_direction_margin: float=0.02, extreme_gate_dip_saturated: bool=False, extreme_gate_dip_band: float=0.02, oracle_tradable_symbols: set[str] | None=None, oracle_tradable_policy: str='off', oracle_atr_enabled: bool | None=None, oracle_atr_values: dict[str, float] | None=None, saturation_slots: int | None=None, dip_stats: dict[str, Any] | None=None, dip_filter_config: dict[str, Any] | None=None) -> list[tuple[str, str, float]]`
- [_apply_dip_quality_policy](../../modelFactory/predictor.py) — ligne 3664 : `def _apply_dip_quality_policy(policy: str, quality_map: dict, date_key: str, candidates: list[tuple[str, str, float]]) -> tuple[list[tuple[str, str, float]], dict[str, float]]`
- [_apply_dip_quality_tiebreak](../../modelFactory/predictor.py) — ligne 3715 : `def _apply_dip_quality_tiebreak(proba_map: dict[str, float], quality_map: dict, date_key: str) -> dict[str, float]`
- [apply_cascade_to_predictions](../../modelFactory/predictor.py) — ligne 3760 : `def apply_cascade_to_predictions(preds_df: pd.DataFrame, batch_id: str, *, top_pct: float | None=None, min_prob: float | None=None, engine: Any | None=None, best_h: int | None=None, short_momentum_filter: str | None=None, short_momentum_max_pct: float | None=None, rank_mode: str='ml', rank_seed: int=42, oracle_rank_map: dict[str, dict[str, float]] | None=None, oracle_filter_pct: float | None=None, oracle_pool_pct: float | None=None, extreme_gate_pct: float | None=None, extreme_gate_per_symbol: str='filter', extreme_gate_shorts: bool=False, extreme_gate_direction_margin: float=0.02, extreme_gate_dip_saturated: bool=False, extreme_gate_dip_band: float=0.02, oracle_tradable_map: dict[str, set[str]] | None=None, oracle_tradable_policy: str='off', oracle_atr_enabled: bool | None=None, oracle_atr_map: dict[str, dict[str, float]] | None=None, saturation_slots: int | None=None, dip_filter_config: dict[str, Any] | None=None, dip_quality_map: dict | None=None, dip_quality_policy: str='none') -> pd.DataFrame`
- [_try_compute_global_rank_for_prediction](../../modelFactory/predictor.py) — ligne 4139 : `def _try_compute_global_rank_for_prediction(artifacts_dir: Path, engine: Any, prediction_date: date | None) -> None`
- [_warn_global_rank_fallbacks](../../modelFactory/predictor.py) — ligne 4213 : `def _warn_global_rank_fallbacks() -> None`
- [predict_batch](../../modelFactory/predictor.py) — ligne 4227 : `def predict_batch(symbols: list[str], artifacts_dir: Path, engine: 'Engine', prediction_date: Optional[date]=None, batch_id: Optional[str]=None, as_of_date: Optional[date]=None, persist: bool=True, accelerator: str='auto', max_workers: int=1) -> pd.DataFrame`

## `modelFactory/report.py`

Source SHA-256 : `41827a107f7e5393d1a239a0ca5f40545bbcc6db40e59f523c6e1a348c1662a5`

- [_classify_regime](../../modelFactory/report.py) — ligne 283 : `def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str`
- [_safe_query](../../modelFactory/report.py) — ligne 297 : `def _safe_query(engine: Engine, query: str, params: dict | None=None) -> pd.DataFrame`
- [_df_to_md](../../modelFactory/report.py) — ligne 305 : `def _df_to_md(df: pd.DataFrame) -> str`
- [_append_champion_status](../../modelFactory/report.py) — ligne 315 : `def _append_champion_status(lines: list[str], champion_df: pd.DataFrame, champion_by_model_df: pd.DataFrame | None=None) -> None`
- [_append_global_ranking_horizon_details](../../modelFactory/report.py) — ligne 358 : `def _append_global_ranking_horizon_details(lines: list[str], metadata_json_str: str | None) -> None`
- [_append_backtest_results](../../modelFactory/report.py) — ligne 578 : `def _append_backtest_results(lines: list[str], batch_id: str | None, metadata_json: str | None=None) -> None`
- [_oracle_split_table](../../modelFactory/report.py) — ligne 731 : `def _oracle_split_table(picks: pd.DataFrame) -> dict | None`
- [_oracle_direction_split](../../modelFactory/report.py) — ligne 757 : `def _oracle_direction_split(df: pd.DataFrame) -> dict | None`
- [_oracle_omniscient_split](../../modelFactory/report.py) — ligne 782 : `def _oracle_omniscient_split(df: pd.DataFrame, top_pct: float=0.1) -> dict | None`
- [_append_oracle_extreme_quality](../../modelFactory/report.py) — ligne 815 : `def _append_oracle_extreme_quality(lines: list[str], engine: Engine, batch_id: str) -> None`
- [_global_rank_all_query_report](../../modelFactory/report.py) — ligne 1040 : `def _global_rank_all_query_report(horizon: int) -> str`
- [_report_best_horizon](../../modelFactory/report.py) — ligne 1051 : `def _report_best_horizon(detail_df: pd.DataFrame) -> int`
- [_oracle_distribution_md](../../modelFactory/report.py) — ligne 1068 : `def _oracle_distribution_md(sel: pd.DataFrame, title: str) -> list[str]`
- [_append_one_oracle_distribution](../../modelFactory/report.py) — ligne 1087 : `def _append_one_oracle_distribution(lines: list[str], engine: Engine, batch_id: str, model_df: pd.DataFrame, *, horizon: int, label: str) -> None`
- [_append_oracle_distribution](../../modelFactory/report.py) — ligne 1156 : `def _append_oracle_distribution(lines: list[str], engine: Engine, batch_id: str) -> None`
- [_report_trains_oracle](../../modelFactory/report.py) — ligne 1284 : `def _report_trains_oracle(detail_df: pd.DataFrame) -> bool`
- [_oracle_periods_report](../../modelFactory/report.py) — ligne 1301 : `def _oracle_periods_report(engine: Engine, batch_id: str) -> list[dict]`
- [_append_prediction_periods](../../modelFactory/report.py) — ligne 1320 : `def _append_prediction_periods(lines: list[str], engine: Engine, batch_id: str) -> None`
- [_build_regime_table](../../modelFactory/report.py) — ligne 1471 : `def _build_regime_table(engine: Engine, batch_id: str) -> pd.DataFrame`
- [generate_batch_report](../../modelFactory/report.py) — ligne 1602 : `def generate_batch_report(engine: Engine, batch_id: str) -> str`

## `modelFactory/reproducibility.py`

Source SHA-256 : `82c596fb68c23d27f5217e743d880236b61c5d394f58bebd83a958eedaaf5a75`

- [normalize_seed](../../modelFactory/reproducibility.py) — ligne 18 : `def normalize_seed(seed: int) -> int`
- [derive_seed](../../modelFactory/reproducibility.py) — ligne 23 : `def derive_seed(base_seed: int, *parts: object) -> int`
- [seed_worker](../../modelFactory/reproducibility.py) — ligne 30 : `def seed_worker(base_seed: int, worker_id: int) -> None`
- [build_torch_generator](../../modelFactory/reproducibility.py) — ligne 41 : `def build_torch_generator(seed: int) -> torch.Generator`
- [apply_reproducibility](../../modelFactory/reproducibility.py) — ligne 47 : `def apply_reproducibility(config: ReproducibilityConfig, *, context: str | None=None) -> dict[str, Any]`

## `modelFactory/run_predict.py`

Source SHA-256 : `4d12b8eff9f5ef6e16376c92d3c42348c9e77d97df84b1ecc1b80b77f4c17e2d`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/run_train.py`

Source SHA-256 : `2f31ce83769db8e3c561b5d2ac49dfb9622100defbdc12ea2305d78f1d1384f2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `modelFactory/runtime_status.py`

Source SHA-256 : `d1d274d4041133c9c31efa6bcaaa7d7666786e84e1cb4453e4993667d56d1bbc`

- [reset_runtime_status](../../modelFactory/runtime_status.py) — ligne 16 : `def reset_runtime_status(initial: dict[str, Any] | None=None) -> None`
- [update_runtime_status](../../modelFactory/runtime_status.py) — ligne 23 : `def update_runtime_status(**updates: Any) -> dict[str, Any]`
- [increment_runtime_counter](../../modelFactory/runtime_status.py) — ligne 29 : `def increment_runtime_counter(name: str, amount: int=1) -> int`
- [snapshot_runtime_status](../../modelFactory/runtime_status.py) — ligne 36 : `def snapshot_runtime_status() -> dict[str, Any]`

## `modelFactory/screener_post_oracle.py`

Source SHA-256 : `24833199f1e91e0f6da6a4c1e7bd8b9ca0e9cfc74bb051532585f3c7507a82c5`

- [ScreenerAuditConfig](../../modelFactory/screener_post_oracle.py) — ligne 63 : `class ScreenerAuditConfig`
- [ScreenerAuditConfig.__post_init__](../../modelFactory/screener_post_oracle.py) — ligne 82 : `def __post_init__(self) -> None`
- [available_screener_features](../../modelFactory/screener_post_oracle.py) — ligne 103 : `def available_screener_features(engine: Any) -> tuple[list[str], list[str]]`
- [load_screener_snapshots](../../modelFactory/screener_post_oracle.py) — ligne 111 : `def load_screener_snapshots(engine: Any, symbols: list[str], *, start_date: str, end_date: str, capital_preset_key: str, feature_columns: list[str]) -> pd.DataFrame`
- [merge_screener_asof](../../modelFactory/screener_post_oracle.py) — ligne 145 : `def merge_screener_asof(pool: pd.DataFrame, snapshots: pd.DataFrame, *, feature_columns: list[str], max_age_days: int) -> pd.DataFrame`
- [load_dense_screener_panel](../../modelFactory/screener_post_oracle.py) — ligne 181 : `def load_dense_screener_panel(path: Path, *, start_date: str, end_date: str) -> tuple[pd.DataFrame, list[str], list[str]]`
- [attach_outcome](../../modelFactory/screener_post_oracle.py) — ligne 209 : `def attach_outcome(dataset: pd.DataFrame, panel: pd.DataFrame, *, horizon: int, up_threshold: float, down_threshold: float, max_abs_future_return: float) -> pd.DataFrame`
- [_equal_date_metrics](../../modelFactory/screener_post_oracle.py) — ligne 238 : `def _equal_date_metrics(frame: pd.DataFrame, side: str) -> dict[str, Any]`
- [evaluate_rule](../../modelFactory/screener_post_oracle.py) — ligne 261 : `def evaluate_rule(frame: pd.DataFrame, feature: str, side: str, orientation: str, threshold: float) -> dict[str, Any]`
- [discover_rule](../../modelFactory/screener_post_oracle.py) — ligne 300 : `def discover_rule(train: pd.DataFrame, feature: str, side: str, min_retention: float) -> dict[str, Any] | None`
- [feature_coverage](../../modelFactory/screener_post_oracle.py) — ligne 340 : `def feature_coverage(dataset: pd.DataFrame, features: Iterable[str], categories: dict[str, str]) -> pd.DataFrame`
- [reliability_tables](../../modelFactory/screener_post_oracle.py) — ligne 372 : `def reliability_tables(dataset: pd.DataFrame, features: Iterable[str], bins: int) -> pd.DataFrame`
- [coverage_by_semester](../../modelFactory/screener_post_oracle.py) — ligne 421 : `def coverage_by_semester(dataset: pd.DataFrame, features: Iterable[str]) -> pd.DataFrame`
- [snapshot_presence_summary](../../modelFactory/screener_post_oracle.py) — ligne 442 : `def snapshot_presence_summary(dataset: pd.DataFrame) -> pd.DataFrame`
- [run_walk_forward_rules](../../modelFactory/screener_post_oracle.py) — ligne 481 : `def run_walk_forward_rules(dataset: pd.DataFrame, features: list[str], config: ScreenerAuditConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [run_campaign](../../modelFactory/screener_post_oracle.py) — ligne 604 : `def run_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, config: ScreenerAuditConfig, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, dense_panel_path: Path | None=None) -> tuple[Path, dict[str, Any]]`
- [main](../../modelFactory/screener_post_oracle.py) — ligne 736 : `def main() -> None`

## `modelFactory/shared_directional.py`

Source SHA-256 : `e61e02c540dddac1e3518f5b7bf180e7be02797e0b0236dc46356b25f6fd6149`

- [SharedDirectionalConfig](../../modelFactory/shared_directional.py) — ligne 60 : `class SharedDirectionalConfig`
- [SharedDirectionalConfig.__post_init__](../../modelFactory/shared_directional.py) — ligne 87 : `def __post_init__(self) -> None`
- [load_profile](../../modelFactory/shared_directional.py) — ligne 126 : `def load_profile(path: Path | str=DEFAULT_PROFILE) -> dict[str, Any]`
- [_prepare_gate](../../modelFactory/shared_directional.py) — ligne 146 : `def _prepare_gate(gate: pd.DataFrame, pool_pct: float) -> pd.DataFrame`
- [_load_gate](../../modelFactory/shared_directional.py) — ligne 171 : `def _load_gate(path: Path, pool_pct: float) -> pd.DataFrame`
- [build_shared_dataset](../../modelFactory/shared_directional.py) — ligne 177 : `def build_shared_dataset(engine: Any, oracle_batch_id: str, symbols: list[str], *, start_date: str, end_date: str, gate_path: Path, profile: dict[str, Any], config: SharedDirectionalConfig) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]`
- [build_forward_return_panel](../../modelFactory/shared_directional.py) — ligne 268 : `def build_forward_return_panel(bars: pd.DataFrame, benchmark: pd.DataFrame, sector_map: dict[str, str], horizons: Iterable[int], *, sector_min_members: int=5) -> tuple[pd.DataFrame, dict[str, Any]]`
- [load_forward_return_panel](../../modelFactory/shared_directional.py) — ligne 363 : `def load_forward_return_panel(engine: Any, symbols: list[str], *, start_date: str, end_date: str, horizons: Iterable[int], sector_min_members: int) -> tuple[pd.DataFrame, dict[str, Any]]`
- [attach_signed_return_target](../../modelFactory/shared_directional.py) — ligne 396 : `def attach_signed_return_target(oracle_pool: pd.DataFrame, forward_panel: pd.DataFrame, *, horizon: int, residualization: str) -> pd.DataFrame`
- [attach_dual_threshold_targets](../../modelFactory/shared_directional.py) — ligne 421 : `def attach_dual_threshold_targets(oracle_pool: pd.DataFrame, forward_panel: pd.DataFrame, *, horizon: int, up_threshold: float, down_threshold: float) -> pd.DataFrame`
- [amplitude_weights](../../modelFactory/shared_directional.py) — ligne 445 : `def amplitude_weights(future_return: pd.Series, config: SharedDirectionalConfig) -> np.ndarray`
- [clip_signed_targets_from_train](../../modelFactory/shared_directional.py) — ligne 456 : `def clip_signed_targets_from_train(train: pd.DataFrame, valid: pd.DataFrame | None, config: SharedDirectionalConfig) -> tuple[pd.DataFrame, pd.DataFrame | None, tuple[float, float]]`
- [binary_probability_to_ternary](../../modelFactory/shared_directional.py) — ligne 482 : `def binary_probability_to_ternary(probability_long: Iterable[float]) -> pd.DataFrame`
- [_prepare_X](../../modelFactory/shared_directional.py) — ligne 496 : `def _prepare_X(frame: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame`
- [_fit_catboost](../../modelFactory/shared_directional.py) — ligne 505 : `def _fit_catboost(train: pd.DataFrame, valid: pd.DataFrame | None, numeric: list[str], categorical: list[str], config: SharedDirectionalConfig, *, iterations: int | None=None) -> Any`
- [_tail](../../modelFactory/shared_directional.py) — ligne 573 : `def _tail(frame: pd.DataFrame, score: str, fraction: float, ascending: bool) -> pd.DataFrame`
- [_mean_daily_ic](../../modelFactory/shared_directional.py) — ligne 581 : `def _mean_daily_ic(frame: pd.DataFrame, return_col: str='future_return') -> float | None`
- [_semester_label](../../modelFactory/shared_directional.py) — ligne 590 : `def _semester_label(value: Any) -> str`
- [evaluate_signed_return_oos](../../modelFactory/shared_directional.py) — ligne 595 : `def evaluate_signed_return_oos(frame: pd.DataFrame, top_fraction: float) -> dict[str, Any]`
- [_fit_dual_head](../../modelFactory/shared_directional.py) — ligne 672 : `def _fit_dual_head(train: pd.DataFrame, valid: pd.DataFrame | None, feature_columns: list[str], categorical_columns: list[str], config: SharedDirectionalConfig, target_column: str, *, iterations: int | None=None) -> Any`
- [evaluate_dual_oos](../../modelFactory/shared_directional.py) — ligne 699 : `def evaluate_dual_oos(frame: pd.DataFrame, top_fraction: float) -> dict[str, Any]`
- [summarize_dual_fold_stability](../../modelFactory/shared_directional.py) — ligne 812 : `def summarize_dual_fold_stability(folds: list[dict[str, Any]]) -> dict[str, Any]`
- [_probability_logit](../../modelFactory/shared_directional.py) — ligne 840 : `def _probability_logit(probability: Iterable[float]) -> np.ndarray`
- [fit_non_inverting_platt](../../modelFactory/shared_directional.py) — ligne 845 : `def fit_non_inverting_platt(raw_probability: Iterable[float], target: Iterable[int], *, max_iter: int=100) -> tuple[PlattCalibrator, dict[str, Any]]`
- [apply_platt](../../modelFactory/shared_directional.py) — ligne 876 : `def apply_platt(calibrator: PlattCalibrator, raw_probability: Iterable[float]) -> np.ndarray`
- [_expected_calibration_error](../../modelFactory/shared_directional.py) — ligne 882 : `def _expected_calibration_error(labels: np.ndarray, probability: np.ndarray, bins: int=10) -> float`
- [_long_selection_metrics](../../modelFactory/shared_directional.py) — ligne 894 : `def _long_selection_metrics(frame: pd.DataFrame) -> dict[str, Any]`
- [_matched_pool_expectation](../../modelFactory/shared_directional.py) — ligne 912 : `def _matched_pool_expectation(frame: pd.DataFrame, fraction: float) -> dict[str, Any]`
- [evaluate_long_confirmation](../../modelFactory/shared_directional.py) — ligne 929 : `def evaluate_long_confirmation(frame: pd.DataFrame, fractions: Iterable[float]=(0.05, 0.1, 0.2)) -> dict[str, Any]`
- [evaluate_oos](../../modelFactory/shared_directional.py) — ligne 991 : `def evaluate_oos(frame: pd.DataFrame, top_fraction: float, *, probability_score: bool=True) -> dict[str, Any]`
- [train_shared_directional](../../modelFactory/shared_directional.py) — ligne 1039 : `def train_shared_directional(dataset: pd.DataFrame, feature_columns: list[str], categorical_columns: list[str], config: SharedDirectionalConfig, artifact_dir: Path) -> dict[str, Any]`
- [train_dual_directional](../../modelFactory/shared_directional.py) — ligne 1186 : `def train_dual_directional(dataset: pd.DataFrame, feature_columns: list[str], categorical_columns: list[str], config: SharedDirectionalConfig, artifact_dir: Path) -> dict[str, Any]`
- [train_long_confirmation](../../modelFactory/shared_directional.py) — ligne 1311 : `def train_long_confirmation(dataset: pd.DataFrame, feature_columns: list[str], categorical_columns: list[str], config: SharedDirectionalConfig, artifact_dir: Path) -> dict[str, Any]`
- [run_experiment](../../modelFactory/shared_directional.py) — ligne 1480 : `def run_experiment(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, config: SharedDirectionalConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [run_signed_return_campaign](../../modelFactory/shared_directional.py) — ligne 1563 : `def run_signed_return_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, horizons: Iterable[int]=(3, 5, 10, 20), profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, config: SharedDirectionalConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_format_signed_campaign](../../modelFactory/shared_directional.py) — ligne 1701 : `def _format_signed_campaign(path: Path, campaign: dict[str, Any]) -> str`
- [run_dual_threshold_campaign](../../modelFactory/shared_directional.py) — ligne 1724 : `def run_dual_threshold_campaign(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, horizons: Iterable[int]=(3, 5, 10, 20), profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, config: SharedDirectionalConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [_format_dual_campaign](../../modelFactory/shared_directional.py) — ligne 1858 : `def _format_dual_campaign(path: Path, campaign: dict[str, Any]) -> str`
- [run_long_confirmation_experiment](../../modelFactory/shared_directional.py) — ligne 1877 : `def run_long_confirmation_experiment(engine: Any, oracle_batch_id: str, *, start_date: str, end_date: str, profile_path: Path=DEFAULT_PROFILE, artifacts_root: Path=DEFAULT_ARTIFACTS_ROOT, symbols_limit: int | None=None, config: SharedDirectionalConfig | None=None) -> tuple[Path, dict[str, Any]]`
- [run_long_untouched_confirmation](../../modelFactory/shared_directional.py) — ligne 1961 : `def run_long_untouched_confirmation(engine: Any, artifact_dir: Path, *, start_date: str, end_date: str) -> tuple[Path, dict[str, Any]]`
- [_format_long_confirmation](../../modelFactory/shared_directional.py) — ligne 2089 : `def _format_long_confirmation(path: Path, contract: dict[str, Any]) -> str`
- [_format_untouched_confirmation](../../modelFactory/shared_directional.py) — ligne 2104 : `def _format_untouched_confirmation(path: Path, result: dict[str, Any]) -> str`
- [_format_summary](../../modelFactory/shared_directional.py) — ligne 2117 : `def _format_summary(path: Path, contract: dict[str, Any]) -> str`
- [main](../../modelFactory/shared_directional.py) — ligne 2138 : `def main() -> None`

## `modelFactory/synthesize_global_rank_predictions.py`

Source SHA-256 : `dc10177ee6ff0db9df5dea98d363986924745ecce292a846634137cdcb72b504`

- [synthesize](../../modelFactory/synthesize_global_rank_predictions.py) — ligne 54 : `def synthesize(batch_id: str, best_h: int, *, top_pct: float=0.1, dip_config: dict | None=None, start: str | None=None, end: str | None=None) -> dict`
- [_build_dip_long_set](../../modelFactory/synthesize_global_rank_predictions.py) — ligne 172 : `def _build_dip_long_set(engine, batch_id: str, rank_col: str, *, n: int=4, threshold: float=0.9, dip_pct: float=0.02) -> set[tuple[str, str]]`
- [neutralize_illiquid](../../modelFactory/synthesize_global_rank_predictions.py) — ligne 229 : `def neutralize_illiquid(batch_id: str, *, end_date: str='2018-12-31') -> dict`
- [main](../../modelFactory/synthesize_global_rank_predictions.py) — ligne 278 : `def main() -> None`

## `modelFactory/synthesize_oracle_predictions.py`

Source SHA-256 : `659d92a3ad3808078d94fd5550e5ee049057483dea2b2a5ad249e5a97f8347d3`

- [synthesize](../../modelFactory/synthesize_oracle_predictions.py) — ligne 55 : `def synthesize(batch_id: str, *, pool_pct: float=0.2, start: str | None=None, end: str | None=None) -> dict`
- [main](../../modelFactory/synthesize_oracle_predictions.py) — ligne 139 : `def main() -> None`

## `modelFactory/synthetic_prediction_run.py`

Source SHA-256 : `147ce1b2ca8a60dd590a8184890f37ed7f3766f581093ec586918c4766e0e4b5`

- [ensure_synthetic_run](../../modelFactory/synthetic_prediction_run.py) — ligne 9 : `def ensure_synthetic_run(engine, *, batch_id: str, run_id: str, symbol: str) -> None`

## `modelFactory/tabular_baseline.py`

Source SHA-256 : `cccab44129ad6e49d45a047dd4bdb9ac4576fba3510de442b042054ff4b2b9c0`

- [tabular_split](../../modelFactory/tabular_baseline.py) — ligne 36 : `def tabular_split(df: pd.DataFrame, *, train_ratio: float, val_ratio: float, forecast_horizon: int=0, embargo_rows: int=0, by_dates: bool=False, embargo_dates: int=0) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [binary_auc](../../modelFactory/tabular_baseline.py) — ligne 89 : `def binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None`
- [expected_calibration_error](../../modelFactory/tabular_baseline.py) — ligne 111 : `def expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int=10) -> float`
- [compute_tabular_metrics](../../modelFactory/tabular_baseline.py) — ligne 123 : `def compute_tabular_metrics(labels: np.ndarray, proba: np.ndarray, future_returns: np.ndarray, decision_threshold: float, *, raw_proba_all: np.ndarray | None=None, target_raw: np.ndarray | None=None, is_ternary: bool=False, ternary_policy: 'TernaryDecisionPolicy | None'=None) -> dict[str, Any]`
- [fit_tabular_calibrator](../../modelFactory/tabular_baseline.py) — ligne 206 : `def fit_tabular_calibrator(val_raw_proba: np.ndarray, labels: np.ndarray, cfg: TrainingConfig, *, target_mode: str='binary') -> PlattCalibrator | TemperatureScaler | VectorScaler | None`
- [_fit_ternary_calibrator](../../modelFactory/tabular_baseline.py) — ligne 236 : `def _fit_ternary_calibrator(raw_proba_all: np.ndarray, labels: np.ndarray, cfg: TrainingConfig) -> VectorScaler | None`
- [apply_tabular_calibration](../../modelFactory/tabular_baseline.py) — ligne 267 : `def apply_tabular_calibration(raw_proba: np.ndarray, calibrator: PlattCalibrator | TemperatureScaler | VectorScaler | None, *, target_mode: str='binary') -> np.ndarray`
- [_compute_regression_metrics](../../modelFactory/tabular_baseline.py) — ligne 293 : `def _compute_regression_metrics(pred: np.ndarray, target: np.ndarray, future_return: np.ndarray, *, bias_correction: float=0.0) -> dict[str, Any]`
- [run_tabular_baseline](../../modelFactory/tabular_baseline.py) — ligne 400 : `def run_tabular_baseline(prepared_df: pd.DataFrame, cfg: TrainingConfig, *, model_name: str, model_builder: Callable[[int], Any], artifact_dir: Path | None=None, save_callback: Callable[[Any, Path], None] | None=None, model_extension: str='.pkl', ternary_policy: 'TernaryDecisionPolicy | None'=None, by_dates: bool=False, embargo_dates: int=0, symbol_tag: str='', forecast_horizon_override: int | None=None, feature_columns_override: list[str] | None=None) -> dict[str, Any]`
- [save_baseline_artifact](../../modelFactory/tabular_baseline.py) — ligne 726 : `def save_baseline_artifact(result: dict[str, Any], *, artifact_dir: Path, period_start: date | str, period_end: date | str, universe_run_id: str='', code_version: str='', data_fingerprint: str, config_fingerprint: str, symbol_tag: str='__BATCH__') -> Path`
- [run_tabular_walk_forward](../../modelFactory/tabular_baseline.py) — ligne 839 : `def run_tabular_walk_forward(prepared_df: pd.DataFrame, cfg: TrainingConfig, *, model_name: str, model_builder: Callable[[int], Any], ternary_policy: 'TernaryDecisionPolicy | None'=None, by_dates: bool=False, symbol_tag: str='', forecast_horizon_override: int | None=None, feature_columns_override: list[str] | None=None) -> dict[str, Any]`

## `modelFactory/target_optimization.py`

Source SHA-256 : `efedded1fccdc67fd0654d978462cbebd6398d6e3bbb3d152a1bfe1ad966cfae`

- [TargetCandidateResult](../../modelFactory/target_optimization.py) — ligne 29 : `class TargetCandidateResult`
- [TripleBarrierCandidateResult](../../modelFactory/target_optimization.py) — ligne 46 : `class TripleBarrierCandidateResult`
- [score_target_candidate](../../modelFactory/target_optimization.py) — ligne 64 : `def score_target_candidate(df: pd.DataFrame, *, horizon: int, data_cfg: DataConfig, min_trades_fraction: float, positive_threshold: float | None=None, negative_threshold: float | None=None) -> TargetCandidateResult`
- [score_triple_barrier_candidate](../../modelFactory/target_optimization.py) — ligne 153 : `def score_triple_barrier_candidate(df: pd.DataFrame, *, stop_atr_mult: float, tp_atr_mult: float, max_sessions: int, data_cfg: DataConfig, min_trades_fraction: float) -> TripleBarrierCandidateResult`
- [optimize_triple_barrier_parameters](../../modelFactory/target_optimization.py) — ligne 248 : `def optimize_triple_barrier_parameters(df: pd.DataFrame, *, data_cfg: DataConfig, opt_cfg: TargetOptimizationConfig) -> dict[str, Any]`
- [optimize_target_parameters](../../modelFactory/target_optimization.py) — ligne 303 : `def optimize_target_parameters(df: pd.DataFrame, *, data_cfg: DataConfig, opt_cfg: TargetOptimizationConfig) -> dict[str, Any]`
- [optimize_target_horizon](../../modelFactory/target_optimization.py) — ligne 404 : `def optimize_target_horizon(df: pd.DataFrame, *, data_cfg: DataConfig, opt_cfg: TargetOptimizationConfig) -> dict[str, Any]`

## `modelFactory/temporal_tail_classifier_v2.py`

Source SHA-256 : `ac1ca9dc2be7beb938f78ce796dd3b9f609171a0680e7c8a1da231e25284a664`

- [Fold](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 46 : `class Fold`
- [load_config](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 52 : `def load_config(path: Path) -> dict[str, Any]`
- [_rolling_slope](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 69 : `def _rolling_slope(values: np.ndarray) -> float`
- [add_temporal_features](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 76 : `def add_temporal_features(frame: pd.DataFrame, base_features: list[str], window: int, *, positive_fraction_features: set[str], acceleration_features: set[str]) -> tuple[pd.DataFrame, dict[str, list[str]]]`
- [make_folds](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 150 : `def make_folds(dates: pd.Series, config: dict[str, Any]) -> list[Fold]`
- [_date_weights](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 165 : `def _date_weights(frame: pd.DataFrame) -> np.ndarray`
- [fit_predict](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 171 : `def fit_predict(model_name: str, train: pd.DataFrame, test: pd.DataFrame, features: list[str], model_config: dict[str, Any], seed: int, threads: int) -> np.ndarray`
- [_safe_auc](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 223 : `def _safe_auc(y: pd.Series | np.ndarray, score: pd.Series | np.ndarray) -> float | None`
- [preload_metric_dependencies](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 232 : `def preload_metric_dependencies() -> None`
- [_same_date_auc](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 244 : `def _same_date_auc(frame: pd.DataFrame) -> pd.Series`
- [evaluate_oof](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 253 : `def evaluate_oof(frame: pd.DataFrame) -> dict[str, Any]`
- [audit_labels](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 318 : `def audit_labels(labels: pd.DataFrame) -> dict[str, Any]`
- [build_dataset](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 348 : `def build_dataset(engine: Any, batch_id: str, gate_path: Path, profile_path: Path, config: dict[str, Any], cache_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]`
- [run_variant](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 395 : `def run_variant(frame: pd.DataFrame, features: list[str], representation: str, window: int | None, model_name: str, config: dict[str, Any], threads: int) -> tuple[pd.DataFrame, dict[str, Any]]`
- [_markdown_report](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 443 : `def _markdown_report(report: dict[str, Any], comparison: pd.DataFrame) -> str`
- [run](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 461 : `def run(args: argparse.Namespace) -> dict[str, Any]`
- [main](../../modelFactory/temporal_tail_classifier_v2.py) — ligne 605 : `def main() -> None`

## `modelFactory/thetadata_options.py`

Source SHA-256 : `563418f10c5b683ca81c9067641071b82e2516e03c2d623887cad1cd9f46e922`

- [ThetaDataError](../../modelFactory/thetadata_options.py) — ligne 19 : `class ThetaDataError(RuntimeError)`
- [ThetaDataUnavailable](../../modelFactory/thetadata_options.py) — ligne 23 : `class ThetaDataUnavailable(ThetaDataError)`
- [ThetaDataHttpError](../../modelFactory/thetadata_options.py) — ligne 27 : `class ThetaDataHttpError(ThetaDataError)`
- [ThetaDataHttpError.__init__](../../modelFactory/thetadata_options.py) — ligne 28 : `def __init__(self, status_code: int, message: str) -> None`
- [ThetaOptionPair](../../modelFactory/thetadata_options.py) — ligne 34 : `class ThetaOptionPair`
- [_validate_base_url](../../modelFactory/thetadata_options.py) — ligne 41 : `def _validate_base_url(value: str) -> str`
- [_rows_from_payload](../../modelFactory/thetadata_options.py) — ligne 50 : `def _rows_from_payload(payload: Any) -> list[dict[str, Any]]`
- [ThetaDataClient](../../modelFactory/thetadata_options.py) — ligne 61 : `class ThetaDataClient`
- [ThetaDataClient.__init__](../../modelFactory/thetadata_options.py) — ligne 64 : `def __init__(self, *, base_url: str=DEFAULT_BASE_URL, timeout_seconds: float=60.0, max_retries: int=2, session: requests.Session | None=None, recorder: Callable[[dict[str, Any]], None] | None=None) -> None`
- [ThetaDataClient.get_rows](../../modelFactory/thetadata_options.py) — ligne 76 : `def get_rows(self, path: str, *, params: dict[str, Any]) -> list[dict[str, Any]]`
- [ThetaDataClient.list_quoted_contracts](../../modelFactory/thetadata_options.py) — ligne 117 : `def list_quoted_contracts(self, symbol: str, session_date: date, *, max_dte: int) -> list[dict[str, Any]]`
- [ThetaDataClient.history_quotes](../../modelFactory/thetadata_options.py) — ligne 125 : `def history_quotes(self, pair: ThetaOptionPair, session_date: date, *, start_time: str, end_time: str, interval: str='1m') -> list[dict[str, Any]]`
- [choose_atm_pair](../../modelFactory/thetadata_options.py) — ligne 137 : `def choose_atm_pair(contracts: list[dict[str, Any]], *, symbol: str, spot: float, entry_date: date, min_dte: int=35, max_dte: int=55, target_dte: int=45) -> ThetaOptionPair | None`
- [_normalize_quote](../../modelFactory/thetadata_options.py) — ligne 173 : `def _normalize_quote(row: dict[str, Any]) -> dict[str, Any] | None`
- [select_synchronized_pair_quote](../../modelFactory/thetadata_options.py) — ligne 191 : `def select_synchronized_pair_quote(rows: list[dict[str, Any]], *, prefer: str, max_skew_seconds: int=60) -> dict[str, Any] | None`

## `modelFactory/thetadata_options_smoke.py`

Source SHA-256 : `c2bbbf2c5873aafed472ef0d75a12c3b9d66acb852efd662c5733fd6ad6b5cd4`

- [ThetaSmokeConfig](../../modelFactory/thetadata_options_smoke.py) — ligne 37 : `class ThetaSmokeConfig`
- [ThetaSmokeConfig.__post_init__](../../modelFactory/thetadata_options_smoke.py) — ligne 52 : `def __post_init__(self) -> None`
- [_spaced](../../modelFactory/thetadata_options_smoke.py) — ligne 63 : `def _spaced(values: list[pd.Timestamp], count: int) -> list[pd.Timestamp]`
- [select_smoke_events](../../modelFactory/thetadata_options_smoke.py) — ligne 71 : `def select_smoke_events(oracle: pd.DataFrame, bars: pd.DataFrame, *, config: ThetaSmokeConfig, start_date: str, end_date: str) -> pd.DataFrame`
- [_flat_quote](../../modelFactory/thetadata_options_smoke.py) — ligne 118 : `def _flat_quote(prefix: str, quote: dict[str, Any], output: dict[str, Any]) -> None`
- [evaluate_smoke_event](../../modelFactory/thetadata_options_smoke.py) — ligne 126 : `def evaluate_smoke_event(client: ThetaDataClient, event: dict[str, Any], config: ThetaSmokeConfig) -> dict[str, Any]`
- [assess_smoke](../../modelFactory/thetadata_options_smoke.py) — ligne 182 : `def assess_smoke(results: pd.DataFrame, *, config: ThetaSmokeConfig, terminal_error: str | None=None) -> dict[str, Any]`
- [run](../../modelFactory/thetadata_options_smoke.py) — ligne 226 : `def run(*, oracle_path: Path, output_root: Path, base_url: str, start_date: str, end_date: str, config: ThetaSmokeConfig) -> Path`
- [main](../../modelFactory/thetadata_options_smoke.py) — ligne 293 : `def main() -> None`

## `modelFactory/trainer.py`

Source SHA-256 : `cfd9dbf8979a731097f1401067cf16c300395141b5bff6d7df9cf91ca0b651a7`

- [_build_ternary_policy](../../modelFactory/trainer.py) — ligne 32 : `def _build_ternary_policy(cfg: TrainingConfig) -> TernaryDecisionPolicy`
- [effective_champion_selection_metric](../../modelFactory/trainer.py) — ligne 81 : `def effective_champion_selection_metric(model_role: str, configured_metric: str) -> str`
- [_atomic_write_json](../../modelFactory/trainer.py) — ligne 90 : `def _atomic_write_json(path: Path, data: Any, *, indent: int=2) -> None`
- [_metric_to_float](../../modelFactory/trainer.py) — ligne 121 : `def _metric_to_float(value: Any) -> float | None`
- [_format_metric](../../modelFactory/trainer.py) — ligne 134 : `def _format_metric(value: Any) -> str`
- [_EpochProgressLogger](../../modelFactory/trainer.py) — ligne 139 : `class _EpochProgressLogger(Callback)`
- [_EpochProgressLogger.__init__](../../modelFactory/trainer.py) — ligne 142 : `def __init__(self, *, symbol: str, phase: str, debug_enabled: bool=False, split_index: int | None=None) -> None`
- [_EpochProgressLogger.on_validation_epoch_end](../../modelFactory/trainer.py) — ligne 156 : `def on_validation_epoch_end(self, trainer: 'L.Trainer', pl_module: L.LightningModule) -> None`
- [TrainResult](../../modelFactory/trainer.py) — ligne 195 : `class TrainResult`
- [TrainResult.__init__](../../modelFactory/trainer.py) — ligne 198 : `def __init__(self, symbol: str, run_id: str, status: str, metrics: Optional[dict[str, Any]]=None, skip_reason: Optional[str]=None) -> None`
- [_extract_best_epoch](../../modelFactory/trainer.py) — ligne 212 : `def _extract_best_epoch(checkpoint_path: Path) -> int | None`
- [_build_loader](../../modelFactory/trainer.py) — ligne 226 : `def _build_loader(dataset: SequenceDataset | None, batch_size: int, *, shuffle: bool, seed: int) -> DataLoader | None`
- [_selection_score_from_metrics](../../modelFactory/trainer.py) — ligne 245 : `def _selection_score_from_metrics(metrics: dict[str, Any]) -> float`
- [_build_challenger_summary](../../modelFactory/trainer.py) — ligne 261 : `def _build_challenger_summary(*, val_metrics: dict[str, Any], test_metrics: dict[str, Any], walk_forward_metrics: dict[str, Any], calibration_method: str, selection_score: float, horizons: dict[str, Any] | None=None) -> dict[str, Any]`
- [_skip_train_symbol](../../modelFactory/trainer.py) — ligne 284 : `def _skip_train_symbol(*, symbol: str, run_id: str, reason: str, engine: Optional[Engine]) -> TrainResult`
- [_record_training_db_issue](../../modelFactory/trainer.py) — ligne 300 : `def _record_training_db_issue(symbol: str, run_id: str, *, operation: str, exc: Exception) -> None`
- [_run_training_registry_writes](../../modelFactory/trainer.py) — ligne 315 : `def _run_training_registry_writes(engine: Engine, *, run_id: str, symbol: str, trainer: Any, best_ckpt: Path, scaler_path: Path, config_path: Path, val_metrics: dict[str, Any], test_metrics: dict[str, Any], walk_forward_metrics: dict[str, Any], all_metrics: dict[str, Any], challengers: dict[str, Any], artifact_routes_models: dict[str, Any], selected_architecture: str, selection_mode: str, selection_metric: str, challenger_ranking: list[dict[str, Any]], lstm_horizons: dict[str, Any] | None=None) -> None`
- [_build_feature_contract_for_columns](../../modelFactory/trainer.py) — ligne 447 : `def _build_feature_contract_for_columns(cfg: TrainingConfig, feature_columns: list[str]) -> dict[str, Any] | None`
- [_build_tabular_artifact_route](../../modelFactory/trainer.py) — ligne 472 : `def _build_tabular_artifact_route(*, metrics: dict[str, Any] | None, config_path: Path, feature_contract: dict[str, Any] | None, default_backend: str) -> dict[str, Any]`
- [_prepare_target_optimization_summary](../../modelFactory/trainer.py) — ligne 496 : `def _prepare_target_optimization_summary(*, bars_df: 'pd.DataFrame', cfg: TrainingConfig, sentiment_df: 'pd.DataFrame | None'=None, benchmark_df: 'pd.DataFrame | None'=None, universe_df: 'pd.DataFrame | None'=None, selector_df: 'pd.DataFrame | None'=None, fundamental_df: 'pd.DataFrame | None'=None) -> dict[str, Any]`
- [_collect_outputs](../../modelFactory/trainer.py) — ligne 546 : `def _collect_outputs(model: LSTMAttentionModule, dataloader: DataLoader | None, device: torch.device) -> dict[str, np.ndarray]`
- [_binary_auc](../../modelFactory/trainer.py) — ligne 610 : `def _binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None`
- [_expected_calibration_error](../../modelFactory/trainer.py) — ligne 635 : `def _expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int=10) -> float`
- [_compute_metrics](../../modelFactory/trainer.py) — ligne 657 : `def _compute_metrics(outputs: dict[str, np.ndarray], *, decision_threshold: float, calibrator: PlattCalibrator | TemperatureScaler | None=None, future_returns: np.ndarray | None=None, ternary_policy: 'TernaryDecisionPolicy | None'=None) -> dict[str, Any]`
- [_fit_calibrator](../../modelFactory/trainer.py) — ligne 863 : `def _fit_calibrator(outputs: dict[str, np.ndarray], cfg: TrainingConfig) -> PlattCalibrator | TemperatureScaler | None`
- [_evaluate_best_checkpoint](../../modelFactory/trainer.py) — ligne 900 : `def _evaluate_best_checkpoint(ckpt_path: Path, *, batch_size: int, val_ds: SequenceDataset | None, test_ds: SequenceDataset | None, val_frame: 'pd.DataFrame | None', test_frame: 'pd.DataFrame | None', cfg: TrainingConfig, ternary_policy: 'TernaryDecisionPolicy | None'=None) -> tuple[dict[str, Any], dict[str, Any], PlattCalibrator | TemperatureScaler | None, dict[str, Any], float, dict[str, np.ndarray]]`
- [_aggregate_walk_forward_metrics](../../modelFactory/trainer.py) — ligne 993 : `def _aggregate_walk_forward_metrics(split_metrics: list[dict[str, Any]]) -> dict[str, Any]`
- [_run_walk_forward_validation](../../modelFactory/trainer.py) — ligne 1047 : `def _run_walk_forward_validation(symbol: str, prepared_df: 'pd.DataFrame', cfg: TrainingConfig) -> dict[str, Any]`
- [train_symbol](../../modelFactory/trainer.py) — ligne 1340 : `def train_symbol(symbol: str, bars_df: 'pd.DataFrame', cfg: TrainingConfig, engine: Optional[Engine]=None, sentiment_df: 'pd.DataFrame | None'=None, benchmark_df: 'pd.DataFrame | None'=None, universe_df: 'pd.DataFrame | None'=None, selector_df: 'pd.DataFrame | None'=None, *, cross_sectional_df: 'pd.DataFrame | None'=None, batch_id: str | None=None, fundamental_df: 'pd.DataFrame | None'=None, oracle_gate_df: 'pd.DataFrame | None'=None) -> TrainResult`

## `modelFactory/trainer_sector.py`

Source SHA-256 : `f494038a227277eace1e5891fef6268b3cae5d00e99afa463ba5e97e1a6aaea9`

- [_prepare_sector_data](../../modelFactory/trainer_sector.py) — ligne 48 : `def _prepare_sector_data(symbols: list[str], cfg: TrainingConfig, engine: Any, *, sentiment_df: pd.DataFrame | None=None, benchmark_df: pd.DataFrame | None=None, universe_df: pd.DataFrame | None=None, selector_df: pd.DataFrame | None=None, fundamental_df: pd.DataFrame | None=None, cross_sectional_df: pd.DataFrame | None=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]`
- [_persist_sector_metrics](../../modelFactory/trainer_sector.py) — ligne 240 : `def _persist_sector_metrics(engine: Any, sector_name: str, run_id: str, *, lgbm_result: dict[str, Any], cb_result: dict[str, Any], champion: str='lightgbm', batch_id: str | None=None, sector_dir: Path | None=None, symbols: list[str] | None=None, cfg: Any=None, has_symbol_feat: bool=False) -> None`
- [_train_sector_models](../../modelFactory/trainer_sector.py) — ligne 375 : `def _train_sector_models(sector_name: str, symbols: list[str], engine: Any, cfg: TrainingConfig, *, sentiment_df: pd.DataFrame | None=None, benchmark_df: pd.DataFrame | None=None, universe_df: pd.DataFrame | None=None, selector_df: pd.DataFrame | None=None, fundamental_df: pd.DataFrame | None=None, cross_sectional_df: pd.DataFrame | None=None, batch_id: str | None=None) -> dict[str, Any]`
- [run_per_sector_batch](../../modelFactory/trainer_sector.py) — ligne 772 : `def run_per_sector_batch(symbols: list[str], engine: Any, cfg: TrainingConfig, *, batch_id: str | None=None) -> list[dict[str, Any]]`
- [_load_benchmark](../../modelFactory/trainer_sector.py) — ligne 895 : `def _load_benchmark(engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None`
- [_load_sentiment_for_symbols](../../modelFactory/trainer_sector.py) — ligne 908 : `def _load_sentiment_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None`
- [_load_universe](../../modelFactory/trainer_sector.py) — ligne 926 : `def _load_universe(symbols: list[str], engine: Any) -> pd.DataFrame | None`
- [_load_selector_for_symbols](../../modelFactory/trainer_sector.py) — ligne 935 : `def _load_selector_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None`
- [_load_fundamentals_for_symbols](../../modelFactory/trainer_sector.py) — ligne 953 : `def _load_fundamentals_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None`

## `modelFactory/universe_guard.py`

Source SHA-256 : `965fdbe702bcc70c85f6ff9a0097dcfd48ebdbb5d7f075824b19998ef302df7a`

- [compute_min_breadth](../../modelFactory/universe_guard.py) — ligne 27 : `def compute_min_breadth(reference_size: int, pct: float) -> int`
- [load_min_universe_pct](../../modelFactory/universe_guard.py) — ligne 34 : `def load_min_universe_pct() -> float`
- [load_reference_universe_size](../../modelFactory/universe_guard.py) — ligne 51 : `def load_reference_universe_size() -> int`
- [load_min_universe_breadth](../../modelFactory/universe_guard.py) — ligne 65 : `def load_min_universe_breadth() -> int`
- [current_universe_size](../../modelFactory/universe_guard.py) — ligne 70 : `def current_universe_size(engine, trade_date: date) -> int`
- [enforce_min_universe_breadth](../../modelFactory/universe_guard.py) — ligne 90 : `def enforce_min_universe_breadth(symbol_count: int, *, trade_date: date | None=None, batch_id: str | None=None, minimum: int | None=None, block: bool=True) -> bool`

## `modelFactory/us_atr_oracle_pilot.py`

Source SHA-256 : `1442a4dece3d197e4517aefd28fd74cb161bc0e79904324ff6ac8c965898aa34`

- [sha256](../../modelFactory/us_atr_oracle_pilot.py) — ligne 19 : `def sha256(path: Path) -> str`
- [atr_panel](../../modelFactory/us_atr_oracle_pilot.py) — ligne 24 : `def atr_panel(bars: pd.DataFrame) -> pd.DataFrame`
- [validate_oof](../../modelFactory/us_atr_oracle_pilot.py) — ligne 43 : `def validate_oof(frame: pd.DataFrame) -> None`
- [daily_metrics](../../modelFactory/us_atr_oracle_pilot.py) — ligne 55 : `def daily_metrics(frame: pd.DataFrame, *, pct: float=0.2, seed: int=17, min_universe: int=20) -> pd.DataFrame`
- [summarize](../../modelFactory/us_atr_oracle_pilot.py) — ligne 95 : `def summarize(daily: pd.DataFrame) -> dict`
- [split_window_sensitivity](../../modelFactory/us_atr_oracle_pilot.py) — ligne 116 : `def split_window_sensitivity(panel: pd.DataFrame) -> dict`
- [run](../../modelFactory/us_atr_oracle_pilot.py) — ligne 130 : `def run(source: Path, output: Path) -> Path`
- [main](../../modelFactory/us_atr_oracle_pilot.py) — ligne 207 : `def main() -> None`

## `modelFactory/us_atr_oracle_realized_audit.py`

Source SHA-256 : `1f579b89407f1fbd66a66b34714fea833c3c5fc1d8ac3a5a18e25728f9df089d`

- [compare](../../modelFactory/us_atr_oracle_realized_audit.py) — ligne 15 : `def compare(panel: pd.DataFrame, labels: pd.DataFrame, atr: str) -> dict`
- [compare_sentiment_at_j](../../modelFactory/us_atr_oracle_realized_audit.py) — ligne 44 : `def compare_sentiment_at_j(windows: pd.DataFrame, labels: pd.DataFrame) -> dict`
- [run](../../modelFactory/us_atr_oracle_realized_audit.py) — ligne 73 : `def run(panel_path: Path, output: Path)`

## `modelFactory/us_atr_oracle_sentiment_audit.py`

Source SHA-256 : `7cff49b7e2384a18aecf323ff5b2a07ba48936ff1901e85ae69b6870b535ced6`

- [overlap](../../modelFactory/us_atr_oracle_sentiment_audit.py) — ligne 22 : `def overlap(panel: pd.DataFrame, atr_column: str) -> tuple[pd.DataFrame, dict]`
- [news_windows](../../modelFactory/us_atr_oracle_sentiment_audit.py) — ligne 47 : `def news_windows(panel: pd.DataFrame, news: pd.DataFrame, sessions: list) -> tuple[pd.DataFrame, list[dict]]`
- [run](../../modelFactory/us_atr_oracle_sentiment_audit.py) — ligne 90 : `def run(batch: str, universe: Path, output: Path) -> dict`
