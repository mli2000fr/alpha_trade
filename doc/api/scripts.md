# Inventaire API — scripts

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `scripts/analyze_oracle_ablation_campaign.py`

Source SHA-256 : `e3c41c71765ede59ce35395b84d902612b224e10d269d09ecb588e705c79aa34`

- [_load_batch](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 17 : `def _load_batch(engine, batch_id: str) -> tuple[dict[str, object], pd.DataFrame]`
- [_daily_top](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 41 : `def _daily_top(frame: pd.DataFrame, pct: float) -> pd.DataFrame`
- [_spearman_decile](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 61 : `def _spearman_decile(frame: pd.DataFrame, value: pd.Series) -> float | None`
- [_metrics](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 84 : `def _metrics(frame: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [_feature_count](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 138 : `def _feature_count(batch_id: str) -> int | None`
- [_paired_daily](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 155 : `def _paired_daily(candidate: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, object]`
- [main](../../scripts/analyze_oracle_ablation_campaign.py) — ligne 185 : `def main() -> None`

## `scripts/audit_blocked_batch_purge.py`

Source SHA-256 : `15eec0cba234d1276620f7055313c0ef21b737f27cd1ab004ed14a2cbe5c5f57`

- [main](../../scripts/audit_blocked_batch_purge.py) — ligne 27 : `def main()`

## `scripts/audit_bundle_prediction.py`

Source SHA-256 : `bde20d320ca45a4152f21643ce442e73eac8fc9f09f7e3ba956410a57e0a97e8`

- [main](../../scripts/audit_bundle_prediction.py) — ligne 99 : `def main() -> None`

## `scripts/audit_private_api_exposure.py`

Source SHA-256 : `cab035bbc1b4235e318396fb233e160429fbc5cdb4f51cbdcb2539b03378d9f4`

- [PublicSymbol](../../scripts/audit_private_api_exposure.py) — ligne 37 : `class PublicSymbol`
- [PublicSymbol.qualname](../../scripts/audit_private_api_exposure.py) — ligne 43 : `def qualname(self) -> str`
- [PrivateExposure](../../scripts/audit_private_api_exposure.py) — ligne 48 : `class PrivateExposure`
- [PrivateExposure.to_dict](../../scripts/audit_private_api_exposure.py) — ligne 53 : `def to_dict(self) -> dict`
- [_module_name](../../scripts/audit_private_api_exposure.py) — ligne 61 : `def _module_name(path: Path) -> str`
- [_iter_python_files](../../scripts/audit_private_api_exposure.py) — ligne 69 : `def _iter_python_files(packages: Iterable[str]) -> Iterable[Path]`
- [_collect_public_symbols](../../scripts/audit_private_api_exposure.py) — ligne 77 : `def _collect_public_symbols(packages: Iterable[str]) -> list[PublicSymbol]`
- [_collect_private_exposures](../../scripts/audit_private_api_exposure.py) — ligne 109 : `def _collect_private_exposures(packages: Iterable[str]) -> list[PrivateExposure]`
- [_load_golden](../../scripts/audit_private_api_exposure.py) — ligne 145 : `def _load_golden() -> set[str]`
- [write_report](../../scripts/audit_private_api_exposure.py) — ligne 154 : `def write_report(public: list[PublicSymbol], private: list[PrivateExposure], out_dir: Path) -> Path`
- [_emit_suggested_patches](../../scripts/audit_private_api_exposure.py) — ligne 184 : `def _emit_suggested_patches(private: list[PrivateExposure], out_dir: Path) -> Path`
- [main](../../scripts/audit_private_api_exposure.py) — ligne 259 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/audit_sprint5_us_parity.py`

Source SHA-256 : `345f99fb9f64f4de246bb6f32c7ba8e15ef49d788348086eb178ac1a371d4a07`

- [_stable_frame_hash](../../scripts/audit_sprint5_us_parity.py) — ligne 43 : `def _stable_frame_hash(frame: pd.DataFrame) -> str`
- [compare_symbol_and_instrument_reads](../../scripts/audit_sprint5_us_parity.py) — ligne 55 : `def compare_symbol_and_instrument_reads(engine: Engine, table: str, date_column: str, *, sample_size: int) -> dict[str, Any]`
- [audit_symbol_only_joins](../../scripts/audit_sprint5_us_parity.py) — ligne 112 : `def audit_symbol_only_joins(root: Path=ROOT) -> dict[str, Any]`
- [run](../../scripts/audit_sprint5_us_parity.py) — ligne 127 : `def run(engine: Engine, output_dir: Path, sample_size: int=25, *, coverage: dict[str, Any] | None=None) -> dict[str, Any]`
- [main](../../scripts/audit_sprint5_us_parity.py) — ligne 189 : `def main() -> None`

## `scripts/audit_sprint6_cn.py`

Source SHA-256 : `7e84ce927aaec5032ea626825728da35a882308e08581555b7900969ffe17de2`

- [_write_json](../../scripts/audit_sprint6_cn.py) — ligne 28 : `def _write_json(path: Path, payload: dict[str, Any]) -> None`
- [_configuration_audit](../../scripts/audit_sprint6_cn.py) — ligne 32 : `def _configuration_audit() -> dict[str, Any]`
- [_staging_counts](../../scripts/audit_sprint6_cn.py) — ligne 52 : `def _staging_counts() -> dict[str, int]`
- [run](../../scripts/audit_sprint6_cn.py) — ligne 65 : `def run(output_dir: Path) -> dict[str, Any]`
- [main](../../scripts/audit_sprint6_cn.py) — ligne 113 : `def main() -> None`

## `scripts/audit_us_instrument_mapping.py`

Source SHA-256 : `1d9b92f80c976a22c0771b289b08251204df9fa312f55fa07ef187aa545e407d`

- [MappingCandidate](../../scripts/audit_us_instrument_mapping.py) — ligne 42 : `class MappingCandidate`
- [_normalize_exchange](../../scripts/audit_us_instrument_mapping.py) — ligne 50 : `def _normalize_exchange(value: Any) -> str`
- [classify_stock_metadata](../../scripts/audit_us_instrument_mapping.py) — ligne 54 : `def classify_stock_metadata(row: dict[str, Any]) -> MappingCandidate`
- [load_stock_metadata](../../scripts/audit_us_instrument_mapping.py) — ligne 84 : `def load_stock_metadata(engine: Engine) -> list[dict[str, Any]]`
- [build_report](../../scripts/audit_us_instrument_mapping.py) — ligne 100 : `def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]`
- [run](../../scripts/audit_us_instrument_mapping.py) — ligne 132 : `def run(*, engine: Engine | None=None, output_path: str | Path=DEFAULT_OUTPUT) -> dict[str, Any]`
- [main](../../scripts/audit_us_instrument_mapping.py) — ligne 147 : `def main() -> None`

## `scripts/backup_db.py`

Source SHA-256 : `92317c82e8669084af5d0978b8d7283f75b93e0989bd8ac8c751e3174a708c92`

- [DbBackupReport](../../scripts/backup_db.py) — ligne 46 : `class DbBackupReport`
- [DbBackupReport.to_dict](../../scripts/backup_db.py) — ligne 63 : `def to_dict(self) -> dict`
- [_resolve_mysqldump](../../scripts/backup_db.py) — ligne 72 : `def _resolve_mysqldump(mysqldump_path: str | Path | None=None) -> str | None`
- [_have_mysqldump](../../scripts/backup_db.py) — ligne 80 : `def _have_mysqldump(mysqldump_path: str | Path | None=None) -> bool`
- [_list_dumps](../../scripts/backup_db.py) — ligne 84 : `def _list_dumps(dest_dir: Path, archive_prefix: str) -> list[Path]`
- [_build_dump_path](../../scripts/backup_db.py) — ligne 89 : `def _build_dump_path(dest_dir: Path, archive_prefix: str) -> Path`
- [_validate_identifiers](../../scripts/backup_db.py) — ligne 94 : `def _validate_identifiers(values: list[str], *, label: str) -> None`
- [_run_mysqldump](../../scripts/backup_db.py) — ligne 100 : `def _run_mysqldump(host: str, db: str, user: str, password: str, dump_path: Path, *, include_tables: list[str], exclude_tables: list[str], include_routines: bool, include_triggers: bool, mysqldump_path: str | Path | None) -> None`
- [_rotate](../../scripts/backup_db.py) — ligne 152 : `def _rotate(dest_dir: Path, archive_prefix: str, keep: int, dry_run: bool) -> tuple[list[str], list[str]]`
- [backup_db](../../scripts/backup_db.py) — ligne 174 : `def backup_db(*, host: str=DEFAULT_HOST, db: str=DEFAULT_DB, user: str='', password: str='', dest_dir: Path=DEFAULT_DEST_DIR, keep: int=DEFAULT_KEEP, archive_prefix: str | None=None, include_tables: list[str] | None=None, exclude_tables: list[str] | None=None, include_routines: bool=True, include_triggers: bool=True, mysqldump_path: str | Path | None=None, dry_run: bool=False) -> DbBackupReport`
- [_build_parser](../../scripts/backup_db.py) — ligne 308 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/backup_db.py) — ligne 348 : `def main(argv: list[str] | None=None) -> int`

## `scripts/backup_ml_artifacts.py`

Source SHA-256 : `29f7a21c884bae12aeba94945b83cf5c7dd0e188425a704d6575037d2fe4d726`

- [BackupReport](../../scripts/backup_ml_artifacts.py) — ligne 40 : `class BackupReport`
- [BackupReport.to_dict](../../scripts/backup_ml_artifacts.py) — ligne 53 : `def to_dict(self) -> dict`
- [_list_archives](../../scripts/backup_ml_artifacts.py) — ligne 62 : `def _list_archives(dest_dir: Path) -> list[Path]`
- [_build_archive_path](../../scripts/backup_ml_artifacts.py) — ligne 67 : `def _build_archive_path(dest_dir: Path) -> Path`
- [_rotate](../../scripts/backup_ml_artifacts.py) — ligne 72 : `def _rotate(dest_dir: Path, keep: int, dry_run: bool) -> tuple[list[str], list[str]]`
- [backup](../../scripts/backup_ml_artifacts.py) — ligne 96 : `def backup(*, artifacts_dir: Path=DEFAULT_ARTIFACTS_DIR, dest_dir: Path=DEFAULT_DEST_DIR, keep: int=DEFAULT_KEEP, dry_run: bool=False) -> BackupReport`
- [_build_parser](../../scripts/backup_ml_artifacts.py) — ligne 196 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/backup_ml_artifacts.py) — ligne 232 : `def main(argv: list[str] | None=None) -> int`

## `scripts/bench_full_pipeline.py`

Source SHA-256 : `a6ba23ad296b0eb8264317fbb2797e16059ac09727de15846fcdd857dae46c25`

- [_time_stage](../../scripts/bench_full_pipeline.py) — ligne 31 : `def _time_stage(name: str, fn) -> tuple[str, float, str | None, dict[str, object] | None]`
- [_build_synthetic_screener_prices](../../scripts/bench_full_pipeline.py) — ligne 40 : `def _build_synthetic_screener_prices(symbols: list[str])`
- [_stage_screener](../../scripts/bench_full_pipeline.py) — ligne 73 : `def _stage_screener(symbols: list[str]) -> dict[str, object]`
- [_stage_selector](../../scripts/bench_full_pipeline.py) — ligne 98 : `def _stage_selector(symbols: list[str]) -> dict[str, object]`
- [_stage_risk](../../scripts/bench_full_pipeline.py) — ligne 123 : `def _stage_risk(symbols: list[str]) -> dict[str, object]`
- [_stage_execution_dry_run](../../scripts/bench_full_pipeline.py) — ligne 142 : `def _stage_execution_dry_run(symbols: list[str]) -> dict[str, object]`
- [main](../../scripts/bench_full_pipeline.py) — ligne 156 : `def main() -> int`

## `scripts/build_equity_universe.py`

Source SHA-256 : `994d8a9234965a2ecf54d1d75f283747c06787165fe2d01ea141857e5e5c367d`

- [read_symbols](../../scripts/build_equity_universe.py) — ligne 25 : `def read_symbols(path: Path) -> list[str]`
- [filter_equity_symbols](../../scripts/build_equity_universe.py) — ligne 33 : `def filter_equity_symbols(symbols: list[str], metadata: pd.DataFrame) -> tuple[list[str], list[dict[str, str]]]`
- [load_metadata](../../scripts/build_equity_universe.py) — ligne 52 : `def load_metadata(engine: Engine, symbols: list[str]) -> pd.DataFrame`
- [main](../../scripts/build_equity_universe.py) — ligne 62 : `def main(argv: list[str] | None=None) -> int`

## `scripts/check_branch_coverage_critical.py`

Source SHA-256 : `0b35dad0b1b45f30911b5639bc8457265c9e34dcf847b53eed8d70e588574580`

- [_aggregate](../../scripts/check_branch_coverage_critical.py) — ligne 33 : `def _aggregate(report: dict, module: str) -> tuple[int, int]`
- [main](../../scripts/check_branch_coverage_critical.py) — ligne 52 : `def main() -> int`

## `scripts/check_doc_links.py`

Source SHA-256 : `4b0bd602d4e2f2221320eb02780471aa0c31c3a0bae69439afc97612e4f82593`

- [_is_external](../../scripts/check_doc_links.py) — ligne 24 : `def _is_external(target: str) -> bool`
- [_resolve](../../scripts/check_doc_links.py) — ligne 28 : `def _resolve(source: Path, target: str) -> Path`
- [find_dead_links](../../scripts/check_doc_links.py) — ligne 37 : `def find_dead_links(root: Path=DOC_DIR) -> list[dict]`
- [main](../../scripts/check_doc_links.py) — ligne 58 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/check_external_audit_freshness.py`

Source SHA-256 : `7109f9bef3fabdd9c0250bd3dd79e2c93799d8c88a47db7b80efd2e3370c250e`

- [_latest_report_date](../../scripts/check_external_audit_freshness.py) — ligne 26 : `def _latest_report_date() -> date | None`
- [main](../../scripts/check_external_audit_freshness.py) — ligne 49 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/check_no_todo.py`

Source SHA-256 : `fa37d2847c98d825d24284e9bdee80a8c80580e0a1c20471282fc4661239c8fd`

- [iter_python_files](../../scripts/check_no_todo.py) — ligne 48 : `def iter_python_files(root: Path)`
- [scan](../../scripts/check_no_todo.py) — ligne 57 : `def scan(root: Path) -> list[tuple[Path, int, str, str]]`
- [main](../../scripts/check_no_todo.py) — ligne 71 : `def main() -> int`

## `scripts/collect_yahoo_analyst_snapshots.py`

Source SHA-256 : `d041b3444447a6f8e6cecb82f27d9aacd063d25ff85997a2988eb94268ae922b`

- [_utcnow](../../scripts/collect_yahoo_analyst_snapshots.py) — ligne 48 : `def _utcnow()`
- [_setup_logging](../../scripts/collect_yahoo_analyst_snapshots.py) — ligne 55 : `def _setup_logging(log_file: str | None) -> None`
- [main](../../scripts/collect_yahoo_analyst_snapshots.py) — ligne 73 : `def main(argv: list[str] | None=None) -> int`

## `scripts/compare_benchmarks.py`

Source SHA-256 : `2387b86958d4414943874587618a9493dbcc061e18a4721f33165d240dbddc5f`

- [_index_by_name](../../scripts/compare_benchmarks.py) — ligne 25 : `def _index_by_name(report: dict) -> dict[str, float]`
- [main](../../scripts/compare_benchmarks.py) — ligne 37 : `def main() -> int`

## `scripts/compare_per_symbol_batches.py`

Source SHA-256 : `cd775e689778c8390a23e605feef62242704d2e3be69851fbbaa58c0923573a0`

- [_finite](../../scripts/compare_per_symbol_batches.py) — ligne 38 : `def _finite(value: object) -> float | None`
- [main](../../scripts/compare_per_symbol_batches.py) — ligne 43 : `def main() -> int`

## `scripts/eodhd_phase4_volume_audit.py`

Source SHA-256 : `15c740fe2005cc50df5c41437e3c4307ed352b9b5e5321d43898a16c7f28db78`

- [_fetch_pairs_from_db](../../scripts/eodhd_phase4_volume_audit.py) — ligne 55 : `def _fetch_pairs_from_db(session, symbols, start_date, end_date)`
- [_fetch_market_caps](../../scripts/eodhd_phase4_volume_audit.py) — ligne 77 : `def _fetch_market_caps(session, symbols)`
- [compute_volume_ratios](../../scripts/eodhd_phase4_volume_audit.py) — ligne 89 : `def compute_volume_ratios(pairs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]`
- [aggregate_by_symbol](../../scripts/eodhd_phase4_volume_audit.py) — ligne 105 : `def aggregate_by_symbol(ratios)`
- [_percentile](../../scripts/eodhd_phase4_volume_audit.py) — ligne 120 : `def _percentile(values, p)`
- [compute_avg_dollar_volume_20d](../../scripts/eodhd_phase4_volume_audit.py) — ligne 132 : `def compute_avg_dollar_volume_20d(pairs, source: str)`
- [assess_go_no_go](../../scripts/eodhd_phase4_volume_audit.py) — ligne 151 : `def assess_go_no_go(by_symbol, market_caps, avg_dollar_alpaca, avg_dollar_eodhd)`
- [_is_nan](../../scripts/eodhd_phase4_volume_audit.py) — ligne 188 : `def _is_nan(x)`
- [_resolve_symbols](../../scripts/eodhd_phase4_volume_audit.py) — ligne 192 : `def _resolve_symbols(arg_symbols, universe_name: str)`
- [main](../../scripts/eodhd_phase4_volume_audit.py) — ligne 200 : `def main(argv: Optional[list[str]]=None) -> int`

## `scripts/filter_ml_training_universe.py`

Source SHA-256 : `616d1c56f196482c40db094d774fa4a2321622670b2cb5c7b51bb702e49d3cf9`

- [_iso_date](../../scripts/filter_ml_training_universe.py) — ligne 40 : `def _iso_date(value: str) -> date`
- [_chunks](../../scripts/filter_ml_training_universe.py) — ligne 47 : `def _chunks(values: list[str], size: int) -> Iterable[list[str]]`
- [load_history_stats](../../scripts/filter_ml_training_universe.py) — ligne 70 : `def load_history_stats(engine: Engine, symbols: list[str], *, start_date: date, end_date: date, chunk_size: int) -> dict[str, dict[str, Any]]`
- [load_liquidity_exclusions](../../scripts/filter_ml_training_universe.py) — ligne 103 : `def load_liquidity_exclusions(engine: Engine, symbols: list[str], *, end_date: date, chunk_size: int, min_avg_volume_20d: int, min_market_cap: float, max_market_cap: float, min_daily_dollar_volume: float, min_price: float, max_avg_high_low_range_pct: float, max_spread_bps: float, spread_fallback_mode: str, spread_max_quote_age_days: int) -> tuple[dict[str, str], list[dict[str, Any]]]`
- [_serialize_date](../../scripts/filter_ml_training_universe.py) — ligne 161 : `def _serialize_date(value: Any) -> str`
- [build_parser](../../scripts/filter_ml_training_universe.py) — ligne 165 : `def build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/filter_ml_training_universe.py) — ligne 206 : `def main() -> int`

## `scripts/filter_universe_by_inception.py`

Source SHA-256 : `dc2a23fe0074a0f498a764f1a7d17e663908a4ce851897e77cecada11b09744e`

- [_iso_date](../../scripts/filter_universe_by_inception.py) — ligne 30 : `def _iso_date(value: str) -> date`
- [_read_symbols](../../scripts/filter_universe_by_inception.py) — ligne 37 : `def _read_symbols(path: Path) -> list[str]`
- [main](../../scripts/filter_universe_by_inception.py) — ligne 47 : `def main() -> int`

## `scripts/filter_universe_by_metadata_flags.py`

Source SHA-256 : `254e375936b1731353e2eb9577f9c07e47738f7431eb31e7b1621362994cbac6`

- [_read_symbols](../../scripts/filter_universe_by_metadata_flags.py) — ligne 28 : `def _read_symbols(path: Path) -> list[str]`
- [main](../../scripts/filter_universe_by_metadata_flags.py) — ligne 39 : `def main() -> int`

## `scripts/generate_data_lineage.py`

Source SHA-256 : `db85c5ff16e72dd98f26fdbf5285feafa7148d1f6961716cfe9a614bdba6b9f6`

- [LineageEntry](../../scripts/generate_data_lineage.py) — ligne 53 : `class LineageEntry`
- [ProviderEntry](../../scripts/generate_data_lineage.py) — ligne 66 : `class ProviderEntry`
- [_render_table](../../scripts/generate_data_lineage.py) — ligne 314 : `def _render_table(rows: list[LineageEntry]) -> str`
- [render_lineage_markdown](../../scripts/generate_data_lineage.py) — ligne 327 : `def render_lineage_markdown(*, primary_provider: str='eodhd') -> str`
- [render_provider_block](../../scripts/generate_data_lineage.py) — ligne 361 : `def render_provider_block() -> str`
- [discover_tables](../../scripts/generate_data_lineage.py) — ligne 390 : `def discover_tables(path: Path=ALL_TABLES_PY) -> set[str]`
- [_spec_table_names](../../scripts/generate_data_lineage.py) — ligne 397 : `def _spec_table_names() -> set[str]`
- [write_if_changed](../../scripts/generate_data_lineage.py) — ligne 412 : `def write_if_changed(path: Path, content: str) -> bool`
- [replace_block](../../scripts/generate_data_lineage.py) — ligne 425 : `def replace_block(text: str, *, begin: str, end: str, new_block: str) -> str`
- [_build_parser](../../scripts/generate_data_lineage.py) — ligne 438 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/generate_data_lineage.py) — ligne 460 : `def main(argv: list[str] | None=None) -> int`

## `scripts/generate_doc_index.py`

Source SHA-256 : `caa212ed9b068da676b089619fd57655947306bae052f4d4a085c288fbf7747e`

- [_category](../../scripts/generate_doc_index.py) — ligne 27 : `def _category(path: Path) -> str`
- [_sanitize_markdown_for_meta_extraction](../../scripts/generate_doc_index.py) — ligne 69 : `def _sanitize_markdown_for_meta_extraction(text: str) -> str`
- [_escape_markdown_table_cell](../../scripts/generate_doc_index.py) — ligne 77 : `def _escape_markdown_table_cell(value: str) -> str`
- [_plain_link_labels](../../scripts/generate_doc_index.py) — ligne 81 : `def _plain_link_labels(value: str) -> str`
- [_read_meta](../../scripts/generate_doc_index.py) — ligne 88 : `def _read_meta(path: Path) -> tuple[str, str]`
- [generate](../../scripts/generate_doc_index.py) — ligne 114 : `def generate() -> str`
- [main](../../scripts/generate_doc_index.py) — ligne 152 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/generate_oracle_ablation_profiles.py`

Source SHA-256 : `2ac74670799dcde10f87f54afcbe6ac89d3d015b40c9f0b7d0b055581d1c7b6b`

- [_is_xs](../../scripts/generate_oracle_ablation_profiles.py) — ligne 18 : `def _is_xs(feature: str) -> bool`
- [_is_zscore](../../scripts/generate_oracle_ablation_profiles.py) — ligne 22 : `def _is_zscore(feature: str) -> bool`
- [_is_engineered_transform](../../scripts/generate_oracle_ablation_profiles.py) — ligne 26 : `def _is_engineered_transform(feature: str) -> bool`
- [_is_momentum_return](../../scripts/generate_oracle_ablation_profiles.py) — ligne 35 : `def _is_momentum_return(feature: str) -> bool`
- [_is_trend_position](../../scripts/generate_oracle_ablation_profiles.py) — ligne 41 : `def _is_trend_position(feature: str) -> bool`
- [_is_volatility_range](../../scripts/generate_oracle_ablation_profiles.py) — ligne 50 : `def _is_volatility_range(feature: str) -> bool`
- [_is_volume_flow](../../scripts/generate_oracle_ablation_profiles.py) — ligne 56 : `def _is_volume_flow(feature: str) -> bool`
- [_is_rsi_mean_reversion](../../scripts/generate_oracle_ablation_profiles.py) — ligne 66 : `def _is_rsi_mean_reversion(feature: str) -> bool`
- [_is_market_relative_regime](../../scripts/generate_oracle_ablation_profiles.py) — ligne 73 : `def _is_market_relative_regime(feature: str) -> bool`
- [_raw_simple](../../scripts/generate_oracle_ablation_profiles.py) — ligne 83 : `def _raw_simple(feature: str) -> bool`
- [main](../../scripts/generate_oracle_ablation_profiles.py) — ligne 183 : `def main() -> None`

## `scripts/generate_sbom.py`

Source SHA-256 : `cdd33b7f5d056e9ba57a92cc685082cadb11b46505d17dbace418d1a7d090e44`

- [_parse_requirements](../../scripts/generate_sbom.py) — ligne 29 : `def _parse_requirements(path: Path) -> list[tuple[str, str | None]]`
- [_fallback_sbom](../../scripts/generate_sbom.py) — ligne 47 : `def _fallback_sbom(root: Path) -> dict`
- [_try_cyclonedx](../../scripts/generate_sbom.py) — ligne 82 : `def _try_cyclonedx(output: Path) -> bool`
- [main](../../scripts/generate_sbom.py) — ligne 94 : `def main() -> int`

## `scripts/list_mutation_survivors.py`

Source SHA-256 : `a8574bfa799dfa691134bd847c36be8c8a18f5c1a04e0531f77a5b13556069c9`

- [_list_survivors](../../scripts/list_mutation_survivors.py) — ligne 27 : `def _list_survivors() -> list[str]`
- [_show](../../scripts/list_mutation_survivors.py) — ligne 51 : `def _show(mutant_id: str) -> str`
- [main](../../scripts/list_mutation_survivors.py) — ligne 61 : `def main() -> int`

## `scripts/oracle_selection_audit.py`

Source SHA-256 : `5a7f98664524c2a004da77bb34b102cf01e0873f025d28e79ff04850af43e6df`

- [p](../../scripts/oracle_selection_audit.py) — ligne 33 : `def p(msg: str='') -> None`
- [main](../../scripts/oracle_selection_audit.py) — ligne 37 : `def main() -> None`

## `scripts/produce_baseline_artifact.py`

Source SHA-256 : `c5c539612308f6c14a2513bd539632e7703bbca41a5b7e0c7d33c3cb398f63a2`

- [_load_metrics](../../scripts/produce_baseline_artifact.py) — ligne 54 : `def _load_metrics(path: str) -> dict[str, dict[str, float]]`
- [main](../../scripts/produce_baseline_artifact.py) — ligne 73 : `def main() -> None`

## `scripts/prune_artifacts.py`

Source SHA-256 : `494efab4aba931902cb854d49ab49ac409e5fbc124e2b1bcf6c75672ef2809f0`

- [parse_duration](../../scripts/prune_artifacts.py) — ligne 35 : `def parse_duration(value: str) -> timedelta`
- [RetentionRule](../../scripts/prune_artifacts.py) — ligne 47 : `class RetentionRule`
- [PruneOutcome](../../scripts/prune_artifacts.py) — ligne 80 : `class PruneOutcome`
- [PruneOutcome.to_dict](../../scripts/prune_artifacts.py) — ligne 88 : `def to_dict(self) -> dict[str, object]`
- [_matches_keep](../../scripts/prune_artifacts.py) — ligne 99 : `def _matches_keep(path: Path, base: Path, patterns: tuple[str, ...]) -> bool`
- [_enumerate_files](../../scripts/prune_artifacts.py) — ligne 109 : `def _enumerate_files(base: Path) -> list[Path]`
- [_select_to_delete](../../scripts/prune_artifacts.py) — ligne 115 : `def _select_to_delete(rule: RetentionRule, base: Path, *, now: datetime, age_override: timedelta | None) -> tuple[list[Path], list[Path]]`
- [prune](../../scripts/prune_artifacts.py) — ligne 153 : `def prune(rules: tuple[RetentionRule, ...], *, artifacts_root: Path=ARTIFACTS_DIR, apply: bool=False, age_override: timedelta | None=None, rule_filter: str | None=None, now: datetime | None=None) -> list[PruneOutcome]`
- [_build_parser](../../scripts/prune_artifacts.py) — ligne 198 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/prune_artifacts.py) — ligne 217 : `def main(argv: list[str] | None=None) -> int`

## `scripts/purge_blocked_us_collectors.py`

Source SHA-256 : `04cf4e27b3be9d0ba9824d03581d2020f87433e00f95360d175d9909e8e8e6ef`

- [main](../../scripts/purge_blocked_us_collectors.py) — ligne 37 : `def main()`

## `scripts/refresh_documentation.py`

Source SHA-256 : `cf4375bce154218cd5e8a215cfb3f603450b1ed0697068fb4decc5d0ef65cdb3`

- [rel](../../scripts/refresh_documentation.py) — ligne 38 : `def rel(path)`
- [digest](../../scripts/refresh_documentation.py) — ligne 42 : `def digest(content)`
- [clean_notice](../../scripts/refresh_documentation.py) — ligne 46 : `def clean_notice(body)`
- [classification](../../scripts/refresh_documentation.py) — ligne 50 : `def classification(path)`
- [signatures](../../scripts/refresh_documentation.py) — ligne 73 : `def signatures(path)`
- [source_inventory](../../scripts/refresh_documentation.py) — ligne 99 : `def source_inventory()`
- [links](../../scripts/refresh_documentation.py) — ligne 114 : `def links(body)`
- [resolve_link](../../scripts/refresh_documentation.py) — ligne 121 : `def resolve_link(path, target)`
- [audit_links](../../scripts/refresh_documentation.py) — ligne 132 : `def audit_links()`
- [notice](../../scripts/refresh_documentation.py) — ligne 145 : `def notice(path, kind, date)`
- [write](../../scripts/refresh_documentation.py) — ligne 163 : `def write(path, content, changed)`
- [render_api](../../scripts/refresh_documentation.py) — ligne 174 : `def render_api(package, items, date)`
- [flat_keys](../../scripts/refresh_documentation.py) — ligne 190 : `def flat_keys(value, prefix='')`
- [config_inventory](../../scripts/refresh_documentation.py) — ligne 200 : `def config_inventory(date)`
- [navigation_inventory](../../scripts/refresh_documentation.py) — ligne 214 : `def navigation_inventory(date)`
- [schema_inventory](../../scripts/refresh_documentation.py) — ligne 225 : `def schema_inventory(date)`
- [table_cell](../../scripts/refresh_documentation.py) — ligne 256 : `def table_cell(value)`
- [batch_inventory](../../scripts/refresh_documentation.py) — ligne 260 : `def batch_inventory(date)`
- [module_inventory](../../scripts/refresh_documentation.py) — ligne 286 : `def module_inventory(items, date)`
- [registry](../../scripts/refresh_documentation.py) — ligne 295 : `def registry(date)`
- [repair_old_links](../../scripts/refresh_documentation.py) — ligne 304 : `def repair_old_links(changed)`
- [main](../../scripts/refresh_documentation.py) — ligne 359 : `def main()`

## `scripts/render_sprint5_constraint_sql.py`

Source SHA-256 : `6ab09f42f18c9823c7ff402bc9d292656e61203b5f70b29cd2edd40286e244d7`

- [_migration_module](../../scripts/render_sprint5_constraint_sql.py) — ligne 13 : `def _migration_module()`
- [render](../../scripts/render_sprint5_constraint_sql.py) — ligne 22 : `def render() -> str`
- [main](../../scripts/render_sprint5_constraint_sql.py) — ligne 53 : `def main() -> None`

## `scripts/research/cn_guidance_pdf_review_15d1.py`

Source SHA-256 : `44d4c6a088afc107d48b6565bb41c1d721a949f3a729779a275fbbe744780123`

- [classify](../../scripts/research/cn_guidance_pdf_review_15d1.py) — ligne 17 : `def classify(title: str, content: str) -> dict[str, object]`
- [review](../../scripts/research/cn_guidance_pdf_review_15d1.py) — ligne 35 : `def review(report_path: Path, output_path: Path) -> dict[str, object]`
- [main](../../scripts/research/cn_guidance_pdf_review_15d1.py) — ligne 80 : `def main() -> None`

## `scripts/research/fr_guidance_feasibility.py`

Source SHA-256 : `f7e77323de6b3239b06d41b4cbed9cab724a0eb01e6449d9191f73f70f285601`

- [fetch_bytes](../../scripts/research/fr_guidance_feasibility.py) — ligne 40 : `def fetch_bytes(url: str, *, max_bytes: int=15000000) -> bytes`
- [api_url](../../scripts/research/fr_guidance_feasibility.py) — ligne 56 : `def api_url(path: str, **params: object) -> str`
- [normalized](../../scripts/research/fr_guidance_feasibility.py) — ligne 60 : `def normalized(value: object) -> str`
- [sha](../../scripts/research/fr_guidance_feasibility.py) — ligne 65 : `def sha(value: bytes) -> str`
- [json_dump](../../scripts/research/fr_guidance_feasibility.py) — ligne 69 : `def json_dump(path: Path, value: object) -> None`
- [classify_title](../../scripts/research/fr_guidance_feasibility.py) — ligne 74 : `def classify_title(title: object) -> str | None`
- [issuer_groups](../../scripts/research/fr_guidance_feasibility.py) — ligne 89 : `def issuer_groups() -> list[dict]`
- [choose_issuers](../../scripts/research/fr_guidance_feasibility.py) — ligne 113 : `def choose_issuers(groups: list[dict], size: int, seed: str) -> list[dict]`
- [fetch_issuer](../../scripts/research/fr_guidance_feasibility.py) — ligne 134 : `def fetch_issuer(item: dict, run_dir: Path) -> tuple[dict, list[dict]]`
- [choose_pdfs](../../scripts/research/fr_guidance_feasibility.py) — ligne 172 : `def choose_pdfs(candidates: list[dict], seed: str, per_kind: int=12) -> list[dict]`
- [metadata_stage](../../scripts/research/fr_guidance_feasibility.py) — ligne 190 : `def metadata_stage(run_dir: Path, size: int, workers: int, seed: str) -> None`
- [pdf_stage](../../scripts/research/fr_guidance_feasibility.py) — ligne 228 : `def pdf_stage(run_dir: Path) -> None`
- [recheck_stage](../../scripts/research/fr_guidance_feasibility.py) — ligne 282 : `def recheck_stage(run_dir: Path, sample_size: int=20) -> None`
- [main](../../scripts/research/fr_guidance_feasibility.py) — ligne 321 : `def main() -> None`

## `scripts/research/fr_pilot_pdf_review.py`

Source SHA-256 : `58b81584aeaae92152cc289171299f85bd89277e8dfa68e42b06e0af1192b241`

- [run](../../scripts/research/fr_pilot_pdf_review.py) — ligne 9 : `def run(report_path, output_name='extraction')`

## `scripts/research/fr_public_disclosures_poc.py`

Source SHA-256 : `27e94ce5abe0bf320f52e4ce115aa8e3fc2d1e66e9cb22dae46dc9de8819e3b4`

- [fetch_json](../../scripts/research/fr_public_disclosures_poc.py) — ligne 51 : `def fetch_json(url: str, *, attempts: int=3) -> object`
- [normalize](../../scripts/research/fr_public_disclosures_poc.py) — ligne 64 : `def normalize(value: object) -> str`
- [safe_publication_date](../../scripts/research/fr_public_disclosures_poc.py) — ligne 69 : `def safe_publication_date(record: dict) -> pd.Timestamp | None`
- [load_disclosures](../../scripts/research/fr_public_disclosures_poc.py) — ligne 79 : `def load_disclosures() -> pd.DataFrame`
- [load_prices](../../scripts/research/fr_public_disclosures_poc.py) — ligne 115 : `def load_prices() -> pd.DataFrame`
- [label_prices](../../scripts/research/fr_public_disclosures_poc.py) — ligne 148 : `def label_prices(prices: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame`
- [join_events](../../scripts/research/fr_public_disclosures_poc.py) — ligne 173 : `def join_events(disclosures: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame`
- [thin](../../scripts/research/fr_public_disclosures_poc.py) — ligne 198 : `def thin(frame: pd.DataFrame, horizon: int=20) -> pd.DataFrame`
- [summarize](../../scripts/research/fr_public_disclosures_poc.py) — ligne 209 : `def summarize(events: pd.DataFrame, horizons: tuple[int, ...]) -> list[dict]`
- [main](../../scripts/research/fr_public_disclosures_poc.py) — ligne 237 : `def main() -> None`

## `scripts/research/fr_sprint14_smoke.py`

Source SHA-256 : `27e50a674fe8d380d40c768b99159f620e3d92b859c8073bf6ff82ec078763b8`

- [main](../../scripts/research/fr_sprint14_smoke.py) — ligne 14 : `def main()`

## `scripts/research/fr_sprint14_ui_smoke.py`

Source SHA-256 : `c435a39d45027363eb6e3296975fb4ea1ff8489788eed78bc3e8387a40c7a0dc`

- [main](../../scripts/research/fr_sprint14_ui_smoke.py) — ligne 10 : `def main()`

## `scripts/research/inspect_priority_pdf.py`

Source SHA-256 : `0bace0a61870ab7097fa4b4eefc22a835fad494e1304cd7dd39b32dc246207bb`

- [main](../../scripts/research/inspect_priority_pdf.py) — ligne 8 : `def main()`

## `scripts/research/oracle_atr_partial_refresh.py`

Source SHA-256 : `f66e168454ef2c20a657ac8e4c8ad7ac34069e781ccbe3a0c289f56ff0a406ba`

- [main](../../scripts/research/oracle_atr_partial_refresh.py) — ligne 16 : `def main()`

## `scripts/research/oracle_reveal_vs_wait_cost.py`

Source SHA-256 : `b22b512df7ac5ead02382b37d321e86ecee162c8c70b594e1e2a02f5591b0158`

- [price_panel](../../scripts/research/oracle_reveal_vs_wait_cost.py) — ligne 28 : `def price_panel(bars: pd.DataFrame) -> pd.DataFrame`
- [policy_rows](../../scripts/research/oracle_reveal_vs_wait_cost.py) — ligne 48 : `def policy_rows(events: pd.DataFrame, n: int, threshold: float, cost: float) -> pd.DataFrame`
- [summarize](../../scripts/research/oracle_reveal_vs_wait_cost.py) — ligne 70 : `def summarize(frame: pd.DataFrame, n: int, period: str, threshold: float, cost: float) -> dict`
- [run](../../scripts/research/oracle_reveal_vs_wait_cost.py) — ligne 128 : `def run(events_path: Path, output: Path, threshold: float=0.005, cost: float=0.0006) -> None`

## `scripts/research/us_2026_regime_refresh.py`

Source SHA-256 : `5906e810c9eaa0fce94e39a32c46d381824801e2a6f7bf9949fce915443259c8`

- [forbid_writes](../../scripts/research/us_2026_regime_refresh.py) — ligne 24 : `def forbid_writes(conn, cursor, statement, parameters, context, executemany)`
- [main](../../scripts/research/us_2026_regime_refresh.py) — ligne 29 : `def main()`

## `scripts/research/us_combination_history_regimes.py`

Source SHA-256 : `5b6f0ecdb4c9c4984cf831a310e0b6c4303eef660c92a27345958aeb9f4746a6`

- [historical_scores](../../scripts/research/us_combination_history_regimes.py) — ligne 26 : `def historical_scores(frame, champions, model_root=CHAMP)`
- [scores](../../scripts/research/us_combination_history_regimes.py) — ligne 52 : `def scores(pool)`
- [evaluate](../../scripts/research/us_combination_history_regimes.py) — ligne 61 : `def evaluate(data)`
- [main](../../scripts/research/us_combination_history_regimes.py) — ligne 68 : `def main()`

## `scripts/research/us_combination_regime_review.py`

Source SHA-256 : `16bd6cf264cc46e88c46270aaf39097782bcc2ac5586e90e07d193bb16db2f30`

- [spy_context](../../scripts/research/us_combination_regime_review.py) — ligne 17 : `def spy_context(bars)`
- [associations](../../scripts/research/us_combination_regime_review.py) — ligne 32 : `def associations(monthly, keys, scope)`
- [main](../../scripts/research/us_combination_regime_review.py) — ligne 45 : `def main()`

## `scripts/research/us_common_degradation_audit.py`

Source SHA-256 : `ec8a65d3a55188e09847c4c0bd48de972674e97f3a7ea1ba5a7e90f459979d4b`

- [month_summary](../../scripts/research/us_common_degradation_audit.py) — ligne 13 : `def month_summary(frame)`
- [run](../../scripts/research/us_common_degradation_audit.py) — ligne 31 : `def run()`

## `scripts/research/us_common_degradation_inventory.py`

Source SHA-256 : `07afa2680009a4ceb9875c59a064d8843d3e48aaec4610c265b334a374f56c7d`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `scripts/research/us_concentrated_contract_audit.py`

Source SHA-256 : `b55dc8fc6730217d4ca77d616f1a920e98b5d70c1a610475bb5030063e4dd968`

- [dump](../../scripts/research/us_concentrated_contract_audit.py) — ligne 23 : `def dump(path, value)`
- [frozen_configs](../../scripts/research/us_concentrated_contract_audit.py) — ligne 28 : `def frozen_configs()`
- [frozen_backtest_config](../../scripts/research/us_concentrated_contract_audit.py) — ligne 46 : `def frozen_backtest_config(start, end)`
- [validate_replay_tape](../../scripts/research/us_concentrated_contract_audit.py) — ligne 79 : `def validate_replay_tape(signals, calendar)`
- [classify_bar](../../scripts/research/us_concentrated_contract_audit.py) — ligne 115 : `def classify_bar(symbol, archived, refreshed)`
- [require_economic_gate](../../scripts/research/us_concentrated_contract_audit.py) — ligne 134 : `def require_economic_gate(report, root=Path('.'))`
- [run](../../scripts/research/us_concentrated_contract_audit.py) — ligne 144 : `def run(source, output, refresh=False)`

## `scripts/research/us_concentrated_contract_validate.py`

Source SHA-256 : `ef37abcbee7b433eeb22ade821c355260b0ced77ecca09358b07b4687cfed3d8`

- [band_overlay](../../scripts/research/us_concentrated_contract_validate.py) — ligne 22 : `def band_overlay(source, evidence)`
- [run](../../scripts/research/us_concentrated_contract_validate.py) — ligne 42 : `def run(output, source, evidence)`

## `scripts/research/us_concentrated_exit_variants.py`

Source SHA-256 : `53ab48131ca5058d84eb1b93901baac5e61aef0922c5d47b2a2c9bc7d8eae66c`

- [resolve_long_path](../../scripts/research/us_concentrated_exit_variants.py) — ligne 31 : `def resolve_long_path(signal, days, data, variant)`
- [run](../../scripts/research/us_concentrated_exit_variants.py) — ligne 128 : `def run(source, archive, contract, output, max_dates=None)`
- [main](../../scripts/research/us_concentrated_exit_variants.py) — ligne 237 : `def main()`

## `scripts/research/us_concentrated_fixed_stop.py`

Source SHA-256 : `e155b2517cd44074ddfc527ef927730bc12d543b4233e556b175c9272fcd69fe`

- [fixed_stop_protections](../../scripts/research/us_concentrated_fixed_stop.py) — ligne 9 : `def fixed_stop_protections(protection, stop_pct)`
- [FixedInitialStopLedger](../../scripts/research/us_concentrated_fixed_stop.py) — ligne 35 : `class FixedInitialStopLedger(OraclePortfolioLedger)`
- [FixedInitialStopLedger.__init__](../../scripts/research/us_concentrated_fixed_stop.py) — ligne 36 : `def __init__(self, *args, initial_stop_pct, **kwargs)`
- [FixedInitialStopLedger._build_entry_protections](../../scripts/research/us_concentrated_fixed_stop.py) — ligne 42 : `def _build_entry_protections(self, phase3, *, execution_config)`

## `scripts/research/us_concentrated_historical_tapes.py`

Source SHA-256 : `b8f3aee165d1c5f619445707e01b4b9acf142b54d84bd9b941a9f8d687a1c5bb`

- [digest](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 27 : `def digest(path)`
- [atomic_json](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 31 : `def atomic_json(path, value)`
- [verify_hashes](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 62 : `def verify_hashes(root, mapping)`
- [decision_rows](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 68 : `def decision_rows(candidates)`
- [apply_overlay](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 81 : `def apply_overlay(bars, overlay)`
- [entry_probe](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 91 : `def entry_probe(row, bar, atr)`
- [path_flags](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 111 : `def path_flags(row, bars, calendar)`
- [assemble_day](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 149 : `def assemble_day(frame, bars_by_symbol, opens, highs, lows, atrs, counts, execution)`
- [run](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 212 : `def run(source, contract, output, sides=('buy', 'sell'), max_dates=None)`
- [main](../../scripts/research/us_concentrated_historical_tapes.py) — ligne 327 : `def main()`

## `scripts/research/us_concentrated_live_parity_preflight.py`

Source SHA-256 : `f2979c43b72668899e8a4342e38e74e3486fe1d1528ab518b7ee3d9bff07762e`

- [coverage](../../scripts/research/us_concentrated_live_parity_preflight.py) — ligne 14 : `def coverage(candidates, snapshots)`
- [current_sector_coverage](../../scripts/research/us_concentrated_live_parity_preflight.py) — ligne 41 : `def current_sector_coverage(candidates, mapping)`
- [run](../../scripts/research/us_concentrated_live_parity_preflight.py) — ligne 54 : `def run(archive, output, sector_policy='historical_pit')`

## `scripts/research/us_concentrated_live_portfolio.py`

Source SHA-256 : `08b1cc3ca09c2f90d508bf4e62701c9249477d9308053c71ae223b36918ae94b`

- [apply_verified_volume_overlay](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 34 : `def apply_verified_volume_overlay(bars, path)`
- [ArchivedMacro](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 55 : `class ArchivedMacro`
- [ArchivedMacro.__init__](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 57 : `def __init__(self, frame)`
- [ArchivedMacro.value](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 64 : `def value(self, day, key)`
- [ArchivedMacro.get_vix_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 71 : `def get_vix_close(self, day)`
- [ArchivedMacro.get_vix_short_term_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 72 : `def get_vix_short_term_close(self, day)`
- [ArchivedMacro.get_vxn_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 73 : `def get_vxn_close(self, day)`
- [ArchivedMacro.get_vix3m_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 74 : `def get_vix3m_close(self, day)`
- [ArchivedMacro.get_move_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 75 : `def get_move_close(self, day)`
- [ArchivedMacro.get_rvx_close](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 76 : `def get_rvx_close(self, day)`
- [ArchivedMacro.get_us10y_history](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 77 : `def get_us10y_history(self, day, lookback_days)`
- [run_portfolio](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 81 : `def run_portfolio(*, frames, scores, sectors, macro, market_config, policy, variant, output, max_days=None, quality=None, initial_stop_pct=None, reject_constrained_entries=False, start_date='2025-01-01', end_date='2026-09-30', early_weakness_fraction=None, session_factory=OraclePortfolioSession)`
- [main](../../scripts/research/us_concentrated_live_portfolio.py) — ligne 311 : `def main()`

## `scripts/research/us_concentrated_perfect_direction.py`

Source SHA-256 : `2bedc7bda30d283fc00a8631763ab6d9cadea3becbe9fb4368261eb84cac9b6b`

- [hindsight_membership](../../scripts/research/us_concentrated_perfect_direction.py) — ligne 28 : `def hindsight_membership(candidates)`
- [main](../../scripts/research/us_concentrated_perfect_direction.py) — ligne 48 : `def main()`

## `scripts/research/us_concentrated_portfolio.py`

Source SHA-256 : `815298d2efb791a881e1fc275d0ed3ea87ebdee09dcebbb113ab1154c7c735eb`

- [PortfolioEvidenceError](../../scripts/research/us_concentrated_portfolio.py) — ligne 28 : `class PortfolioEvidenceError(ValueError)`
- [StatefulVariantPortfolio](../../scripts/research/us_concentrated_portfolio.py) — ligne 32 : `class StatefulVariantPortfolio(BacktestEngine)`
- [StatefulVariantPortfolio.run_tape](../../scripts/research/us_concentrated_portfolio.py) — ligne 35 : `def run_tape(self, signals, opens, close, high, low, volume, sector_map=None)`
- [merge_variant_signals](../../scripts/research/us_concentrated_portfolio.py) — ligne 188 : `def merge_variant_signals(original, variant)`
- [run](../../scripts/research/us_concentrated_portfolio.py) — ligne 213 : `def run(source, variants, archive, contract, output, policy='ORACLE_TOP10')`
- [main](../../scripts/research/us_concentrated_portfolio.py) — ligne 301 : `def main()`

## `scripts/research/us_concentrated_realized_top10.py`

Source SHA-256 : `930da3be6b81c213f282247211d6384e3c9d104b68734856488b31797188b3d4`

- [realized_membership](../../scripts/research/us_concentrated_realized_top10.py) — ligne 26 : `def realized_membership(labels)`
- [replay_scores](../../scripts/research/us_concentrated_realized_top10.py) — ligne 43 : `def replay_scores(membership, *, positive_only=False)`
- [run](../../scripts/research/us_concentrated_realized_top10.py) — ligne 53 : `def run(args)`
- [main](../../scripts/research/us_concentrated_realized_top10.py) — ligne 184 : `def main()`

## `scripts/research/us_concentrated_replay_prepare.py`

Source SHA-256 : `a75ef8dc882e575c5749d9f9bd7523b7ee5a1a1e688d3a891c8345fc38b99393`

- [dump](../../scripts/research/us_concentrated_replay_prepare.py) — ligne 20 : `def dump(path, payload)`
- [candidate_panel](../../scripts/research/us_concentrated_replay_prepare.py) — ligne 25 : `def candidate_panel(panel, start, end)`
- [inspect_paths](../../scripts/research/us_concentrated_replay_prepare.py) — ligne 35 : `def inspect_paths(candidates, bars, sessions, progress=None)`
- [run](../../scripts/research/us_concentrated_replay_prepare.py) — ligne 95 : `def run(source, output)`

## `scripts/research/us_concentrated_volume_refresh.py`

Source SHA-256 : `9a3b4d07500f4a6a5cde9a9ae311b2db78f8278937cc4e30abd98cd107bb088c`

- [qualify](../../scripts/research/us_concentrated_volume_refresh.py) — ligne 18 : `def qualify(original, refreshed)`
- [main](../../scripts/research/us_concentrated_volume_refresh.py) — ligne 33 : `def main()`

## `scripts/research/us_constant_probability_calibration_probe.py`

Source SHA-256 : `2cb0cc2176df5426461d66c8e63c2e1fcf806feb7d4583635125181c03307a5a`

- [run](../../scripts/research/us_constant_probability_calibration_probe.py) — ligne 13 : `def run()`

## `scripts/research/us_constant_probability_evidence.py`

Source SHA-256 : `a90c01ba818da92af26ff845f7225938ef59caf3a175fa7c7cc9941b770eb3c3`

- [inventory](../../scripts/research/us_constant_probability_evidence.py) — ligne 17 : `def inventory()`
- [scan](../../scripts/research/us_constant_probability_evidence.py) — ligne 54 : `def scan(archive)`

## `scripts/research/us_extreme50_capture.py`

Source SHA-256 : `b9180bd3d669cb4a15f0cebee6ccfbf63b1475446133f595e04d8dc58e50011f`

- [forbid_writes](../../scripts/research/us_extreme50_capture.py) — ligne 29 : `def forbid_writes(conn, cursor, statement, parameters, context, executemany)`
- [freeze_selection](../../scripts/research/us_extreme50_capture.py) — ligne 34 : `def freeze_selection(scores, atr)`
- [qualify_endpoints](../../scripts/research/us_extreme50_capture.py) — ligne 60 : `def qualify_endpoints(labels, bars)`
- [metrics](../../scripts/research/us_extreme50_capture.py) — ligne 91 : `def metrics(frame, *, as_of)`
- [cluster_events](../../scripts/research/us_extreme50_capture.py) — ligne 122 : `def cluster_events(tails)`
- [dump](../../scripts/research/us_extreme50_capture.py) — ligne 143 : `def dump(path, value)`
- [run](../../scripts/research/us_extreme50_capture.py) — ligne 147 : `def run(*, batch_id, symbol_source, start_date, end_date, output, artifacts_dir='artifacts/models')`
- [main](../../scripts/research/us_extreme50_capture.py) — ligne 279 : `def main()`

## `scripts/research/us_extreme50_price_qualification.py`

Source SHA-256 : `1fefc32b2e2e659012cc6589149f996df09e7fe4fca47f796135459f811bcbd8`

- [save](../../scripts/research/us_extreme50_price_qualification.py) — ligne 19 : `def save(path, payload)`
- [crosses](../../scripts/research/us_extreme50_price_qualification.py) — ligne 24 : `def crosses(start, end, boundary)`
- [qualify_path](../../scripts/research/us_extreme50_price_qualification.py) — ligne 29 : `def qualify_path(path)`
- [reservations](../../scripts/research/us_extreme50_price_qualification.py) — ligne 62 : `def reservations(frame)`
- [compare_vendor_paths](../../scripts/research/us_extreme50_price_qualification.py) — ligne 72 : `def compare_vendor_paths(paths, output)`
- [run](../../scripts/research/us_extreme50_price_qualification.py) — ligne 97 : `def run(source, output, refresh_provider=False)`

## `scripts/research/us_feature_combination_d10.py`

Source SHA-256 : `c66a2f20bbf31e860fecd4b3d3aef9da9b5786ce37e616d793f981092a02cce3`

- [build_scores](../../scripts/research/us_feature_combination_d10.py) — ligne 12 : `def build_scores(pool, news)`
- [pick](../../scripts/research/us_feature_combination_d10.py) — ligne 32 : `def pick(data, policy, fraction)`
- [metrics](../../scripts/research/us_feature_combination_d10.py) — ligne 39 : `def metrics(data)`
- [evaluate](../../scripts/research/us_feature_combination_d10.py) — ligne 59 : `def evaluate(selected)`
- [main](../../scripts/research/us_feature_combination_d10.py) — ligne 66 : `def main()`

## `scripts/research/us_feature_separation_audit.py`

Source SHA-256 : `4275db77cddc202cdaf03f7a9119845e1fee83951f7b9d85a10894409f9018ef`

- [auc](../../scripts/research/us_feature_separation_audit.py) — ligne 19 : `def auc(y, x)`
- [describe](../../scripts/research/us_feature_separation_audit.py) — ligne 29 : `def describe(data, feature, daily_rank=None)`
- [main](../../scripts/research/us_feature_separation_audit.py) — ligne 73 : `def main()`

## `scripts/research/us_feature_separation_review.py`

Source SHA-256 : `6ba408e37648dcb152b52b245d29f7e8f1d16e02a248d5886285862396bbcdaf`

- [main](../../scripts/research/us_feature_separation_review.py) — ligne 12 : `def main()`

## `scripts/research/us_intersection_sentiment_deciles.py`

Source SHA-256 : `1df0bf53dfbf2fcc00b2b715c385fa5c07f04bfca75b68a2e529697c0f4318ce`

- [all_articles_four_sessions](../../scripts/research/us_intersection_sentiment_deciles.py) — ligne 14 : `def all_articles_four_sessions(windows, news, lags=(-3, -2, -1, 0), threshold=0.9)`
- [top_daily](../../scripts/research/us_intersection_sentiment_deciles.py) — ligne 34 : `def top_daily(windows, news, count=10)`
- [main](../../scripts/research/us_intersection_sentiment_deciles.py) — ligne 50 : `def main()`

## `scripts/research/us_oracle_atr_disagreement.py`

Source SHA-256 : `13c4f350b56d08735a4265be0b4270f0dca4cc54d6b7cef1c06944828867db05`

- [classify](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 22 : `def classify(frame)`
- [daily_metrics](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 38 : `def daily_metrics(data)`
- [summarize](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 52 : `def summarize(daily)`
- [matched](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 64 : `def matched(frame)`
- [comparison_summary](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 103 : `def comparison_summary(frame)`
- [main](../../scripts/research/us_oracle_atr_disagreement.py) — ligne 124 : `def main()`

## `scripts/research/us_oracle_feature_outliers.py`

Source SHA-256 : `0963ae12ff5aad16f8f32bc15de0e573e095c1ea9a04b4af6605dc991eefab46`

- [diagnose_segment](../../scripts/research/us_oracle_feature_outliers.py) — ligne 18 : `def diagnose_segment(frame)`
- [run](../../scripts/research/us_oracle_feature_outliers.py) — ligne 38 : `def run(output, universe)`

## `scripts/research/us_oracle_h20_audit_interpretation.py`

Source SHA-256 : `c1d590907d3d7bf130312f2cfa63513d470a10f4c10d8729bbadd1cd706c1931`

- [run](../../scripts/research/us_oracle_h20_audit_interpretation.py) — ligne 17 : `def run(root)`

## `scripts/research/us_oracle_h20_dataset_audit.py`

Source SHA-256 : `eef24f7da260c0ca501636dbbde33b946bd7a22bf839cbe892da95df108debaa`

- [readonly_begin](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 30 : `def readonly_begin(conn)`
- [summarize_features](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 34 : `def summarize_features(frame, columns)`
- [restore_ranks](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 57 : `def restore_ranks(frame, columns)`
- [label_checks](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 74 : `def label_checks(frame, current_symbols, registry)`
- [audit_labels](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 136 : `def audit_labels(engine, batch_id, start, end, symbols, registry)`
- [run](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 153 : `def run(args)`
- [main](../../scripts/research/us_oracle_h20_dataset_audit.py) — ligne 277 : `def main()`

## `scripts/research/us_oracle_lineage_audit.py`

Source SHA-256 : `9d67dc966025845cfb9598c6eed1515dc0771a5c62c8da755346f61b957c1b91`

- [extract_window](../../scripts/research/us_oracle_lineage_audit.py) — ligne 15 : `def extract_window(lines)`
- [classify_scope](../../scripts/research/us_oracle_lineage_audit.py) — ligne 25 : `def classify_scope(frame, starts, first, last)`
- [run](../../scripts/research/us_oracle_lineage_audit.py) — ligne 37 : `def run(output)`

## `scripts/research/us_oracle_numeric_correction_comparison.py`

Source SHA-256 : `0f64fadfdc4d91b6c133ce8616b4b7134ed044993a0a13754c4bf4e93bdc6dbe`

- [run](../../scripts/research/us_oracle_numeric_correction_comparison.py) — ligne 12 : `def run(before, after)`

## `scripts/research/us_oracle_numeric_effect.py`

Source SHA-256 : `3fc3d3359eb9c7a7c34b62dc96ae65f042813e9404400ed3c1878c0551e90bea`

- [read_json](../../scripts/research/us_oracle_numeric_effect.py) — ligne 33 : `def read_json(path)`
- [validate_pair](../../scripts/research/us_oracle_numeric_effect.py) — ligne 37 : `def validate_pair(before, after)`
- [merge_targets](../../scripts/research/us_oracle_numeric_effect.py) — ligne 76 : `def merge_targets(features, labels)`
- [partition_indices](../../scripts/research/us_oracle_numeric_effect.py) — ligne 90 : `def partition_indices(data, fold)`
- [daily_metrics](../../scripts/research/us_oracle_numeric_effect.py) — ligne 105 : `def daily_metrics(predictions)`
- [paired_summary](../../scripts/research/us_oracle_numeric_effect.py) — ligne 130 : `def paired_summary(legacy, corrected, repetitions=1000)`
- [fit_pair_member](../../scripts/research/us_oracle_numeric_effect.py) — ligne 172 : `def fit_pair_member(data, columns, fold, threads)`
- [run](../../scripts/research/us_oracle_numeric_effect.py) — ligne 204 : `def run(args)`
- [main](../../scripts/research/us_oracle_numeric_effect.py) — ligne 319 : `def main()`

## `scripts/research/us_oracle_numeric_external.py`

Source SHA-256 : `e1173277a7ac7f0116fe185fd592a9a49792f8090fd6cf5817ea58f6cfbce846`

- [PrivateImports](../../scripts/research/us_oracle_numeric_external.py) — ligne 32 : `class PrivateImports(ast.NodeTransformer)`
- [PrivateImports.__init__](../../scripts/research/us_oracle_numeric_external.py) — ligne 33 : `def __init__(self, module, namespace)`
- [PrivateImports.visit_ImportFrom](../../scripts/research/us_oracle_numeric_external.py) — ligne 36 : `def visit_ImportFrom(self, node)`
- [legacy_compute](../../scripts/research/us_oracle_numeric_external.py) — ligne 48 : `def legacy_compute(commit)`
- [paired_builders](../../scripts/research/us_oracle_numeric_external.py) — ligne 66 : `def paired_builders(old_compute)`
- [compare_external_features](../../scripts/research/us_oracle_numeric_external.py) — ligne 95 : `def compare_external_features(old, new)`
- [run](../../scripts/research/us_oracle_numeric_external.py) — ligne 101 : `def run(args)`
- [main](../../scripts/research/us_oracle_numeric_external.py) — ligne 236 : `def main()`

## `scripts/research/us_oracle_numeric_top10.py`

Source SHA-256 : `d3f28d48123e25f6dc533da5bd82b1014235b340af3cbcc1c88f0cafdcd1026c`

- [validate_predictions](../../scripts/research/us_oracle_numeric_top10.py) — ligne 23 : `def validate_predictions(frame)`
- [select_top10](../../scripts/research/us_oracle_numeric_top10.py) — ligne 35 : `def select_top10(frame)`
- [daily_metrics](../../scripts/research/us_oracle_numeric_top10.py) — ligne 64 : `def daily_metrics(selected)`
- [summarize](../../scripts/research/us_oracle_numeric_top10.py) — ligne 92 : `def summarize(selected, daily)`
- [paired_deltas](../../scripts/research/us_oracle_numeric_top10.py) — ligne 129 : `def paired_deltas(old, new)`
- [load_pair](../../scripts/research/us_oracle_numeric_top10.py) — ligne 156 : `def load_pair(root, source)`
- [run](../../scripts/research/us_oracle_numeric_top10.py) — ligne 180 : `def run(args)`
- [main](../../scripts/research/us_oracle_numeric_top10.py) — ligne 233 : `def main()`

## `scripts/research/us_oracle_outlier_comparison.py`

Source SHA-256 : `3c99c61b3e0329a913246549f4fa4eb17de57b855e2385db5da9c68378f2fc99`

- [run](../../scripts/research/us_oracle_outlier_comparison.py) — ligne 17 : `def run(source, output)`

## `scripts/research/us_oracle_outlier_evidence.py`

Source SHA-256 : `3c890503af80e63bb2a80a6626cbf738463b8119180366de19d7460f58bcf808`

- [run](../../scripts/research/us_oracle_outlier_evidence.py) — ligne 18 : `def run(source, output)`

## `scripts/research/us_oracle_outlier_provenance.py`

Source SHA-256 : `0339a3a06341e9b2cb639fa0352e37007f8642f1cf5b5866f1e825d6012ecbf4`

- [run](../../scripts/research/us_oracle_outlier_provenance.py) — ligne 10 : `def run(root, output=None)`

## `scripts/research/us_oracle_price_repair_plan.py`

Source SHA-256 : `7058072e81db32b436a6aa8b60440535fc6f9ea453d771354a87ba1e6a2b3263`

- [validate_prices](../../scripts/research/us_oracle_price_repair_plan.py) — ligne 28 : `def validate_prices(frame)`
- [select_candidates](../../scripts/research/us_oracle_price_repair_plan.py) — ligne 44 : `def select_candidates(local, fresh)`
- [propose_existing](../../scripts/research/us_oracle_price_repair_plan.py) — ligne 61 : `def propose_existing(old, replacements, keys, fields)`
- [run](../../scripts/research/us_oracle_price_repair_plan.py) — ligne 83 : `def run(root, output)`

## `scripts/research/us_oracle_remaining_price_events.py`

Source SHA-256 : `bfd1c428e88438dc119a7b8debe10745b14b1c9713e8d67611a4bd70c38fd49e`

- [parse_events](../../scripts/research/us_oracle_remaining_price_events.py) — ligne 23 : `def parse_events(value)`
- [event_record](../../scripts/research/us_oracle_remaining_price_events.py) — ligne 39 : `def event_record(frame, event)`
- [run](../../scripts/research/us_oracle_remaining_price_events.py) — ligne 54 : `def run(output, events=None)`

## `scripts/research/us_oracle_repair_qualification.py`

Source SHA-256 : `79a3ef167b236ef68c7cb6148bc0042797b6860ce522e8fb7c5d9b1ff7f0cd93`

- [verify_plan_hashes](../../scripts/research/us_oracle_repair_qualification.py) — ligne 13 : `def verify_plan_hashes(plan)`
- [validate_parity](../../scripts/research/us_oracle_repair_qualification.py) — ligne 25 : `def validate_parity(daily, bars)`
- [run](../../scripts/research/us_oracle_repair_qualification.py) — ligne 46 : `def run(root, plan, output)`

## `scripts/research/us_oracle_top10_annual.py`

Source SHA-256 : `ba7cf4c8cf1a9623d2c205e968a3058476474e29bf14d78707cfddbd48620f2a`

- [select_scores](../../scripts/research/us_oracle_top10_annual.py) — ligne 36 : `def select_scores(frame)`
- [yearly_windows](../../scripts/research/us_oracle_top10_annual.py) — ligne 56 : `def yearly_windows(start, end)`
- [check_coverage](../../scripts/research/us_oracle_top10_annual.py) — ligne 65 : `def check_coverage(scores, calendar, start, end)`
- [gap_predictions](../../scripts/research/us_oracle_top10_annual.py) — ligne 76 : `def gap_predictions(output, historical, threads)`
- [prepare](../../scripts/research/us_oracle_top10_annual.py) — ligne 123 : `def prepare(output, start, end, threads)`
- [run](../../scripts/research/us_oracle_top10_annual.py) — ligne 180 : `def run(args)`

## `scripts/research/us_original_context_audit.py`

Source SHA-256 : `a138558b60f90ad1e0d4b08cc9fc527123fcefa2861c92e0e3013723318c2fbd`

- [lag_on_sessions](../../scripts/research/us_original_context_audit.py) — ligne 17 : `def lag_on_sessions(frame, sessions)`
- [statistics](../../scripts/research/us_original_context_audit.py) — ligne 24 : `def statistics(group)`
- [fixed_contexts](../../scripts/research/us_original_context_audit.py) — ligne 36 : `def fixed_contexts(frame)`
- [compare](../../scripts/research/us_original_context_audit.py) — ligne 50 : `def compare(group)`
- [run](../../scripts/research/us_original_context_audit.py) — ligne 73 : `def run()`

## `scripts/research/us_original_directional_monthly_audit.py`

Source SHA-256 : `7b3462b8718f770446f49f5e62bbd12c7dd111b60e61cb42caf59b09177cf79e`

- [long_mask](../../scripts/research/us_original_directional_monthly_audit.py) — ligne 16 : `def long_mask(frame)`
- [summarize](../../scripts/research/us_original_directional_monthly_audit.py) — ligne 22 : `def summarize(frame, policy)`
- [run](../../scripts/research/us_original_directional_monthly_audit.py) — ligne 37 : `def run()`

## `scripts/research/us_original_repetition_reliability_audit.py`

Source SHA-256 : `81de8bcb015402be1548f64096d569dab761e669a9af88175f13a9ed33f8d96d`

- [episode_selection](../../scripts/research/us_original_repetition_reliability_audit.py) — ligne 21 : `def episode_selection(frame, sessions, horizon=20)`
- [performance](../../scripts/research/us_original_repetition_reliability_audit.py) — ligne 43 : `def performance(frame)`
- [capped_day_weight](../../scripts/research/us_original_repetition_reliability_audit.py) — ligne 54 : `def capped_day_weight(frame, cap=0.1)`
- [reliability](../../scripts/research/us_original_repetition_reliability_audit.py) — ligne 67 : `def reliability(frame, prevalence)`
- [run](../../scripts/research/us_original_repetition_reliability_audit.py) — ligne 92 : `def run()`

## `scripts/research/us_ratio_lineage_audit.py`

Source SHA-256 : `de6b6fe0ee2da1e75be1327de67f704cb710ba103d3f577755dc7881b8a1455c`

- [run](../../scripts/research/us_ratio_lineage_audit.py) — ligne 12 : `def run()`

## `scripts/research/us_ratio_regime_validation.py`

Source SHA-256 : `dd5eb1a03b4936f38473b569862a9da53cb035e271ccce47c0661689c508afa3`

- [prepare](../../scripts/research/us_ratio_regime_validation.py) — ligne 19 : `def prepare(raw, maturity)`
- [training_mask](../../scripts/research/us_ratio_regime_validation.py) — ligne 46 : `def training_mask(frame, test_start)`
- [metrics](../../scripts/research/us_ratio_regime_validation.py) — ligne 50 : `def metrics(y, pred)`
- [block_ci](../../scripts/research/us_ratio_regime_validation.py) — ligne 57 : `def block_ci(delta, block=20, draws=1000)`
- [evaluate](../../scripts/research/us_ratio_regime_validation.py) — ligne 69 : `def evaluate(frame)`
- [run](../../scripts/research/us_ratio_regime_validation.py) — ligne 105 : `def run(output)`

## `scripts/research/us_sector_breadth_confirmation.py`

Source SHA-256 : `cbb6b29d8ab67d1e8e9244c6a89f030001c353f29a11d346c9bdaa61320324fc`

- [sector_context](../../scripts/research/us_sector_breadth_confirmation.py) — ligne 19 : `def sector_context(bars, sectors, sessions)`
- [regime_mask](../../scripts/research/us_sector_breadth_confirmation.py) — ligne 52 : `def regime_mask(frame)`
- [evaluate](../../scripts/research/us_sector_breadth_confirmation.py) — ligne 58 : `def evaluate(data, mask)`
- [main](../../scripts/research/us_sector_breadth_confirmation.py) — ligne 73 : `def main()`

## `scripts/research/us_sentiment_sma_deciles.py`

Source SHA-256 : `dc9a300a1c22fc53a9ed302c87d03ab2661ed69b0beefd621fbc9c80c69d7501`

- [moving_average_flags](../../scripts/research/us_sentiment_sma_deciles.py) — ligne 15 : `def moving_average_flags(bars)`
- [main](../../scripts/research/us_sentiment_sma_deciles.py) — ligne 31 : `def main()`

## `scripts/research/us_top10_2024_context_audit.py`

Source SHA-256 : `73898339aa1d27d5fcadacb2c29f51f01ce9687279565e92f43b3bed1222bbc7`

- [group_metrics](../../scripts/research/us_top10_2024_context_audit.py) — ligne 12 : `def group_metrics(frame, keys)`
- [run](../../scripts/research/us_top10_2024_context_audit.py) — ligne 30 : `def run(source, output)`

## `scripts/research/us_top10_early_weakness_audit.py`

Source SHA-256 : `53efa18f36f09dc05322f6f86af2341a883eef96596be3f341d226ccdcba8ebc`

- [early_paths](../../scripts/research/us_top10_early_weakness_audit.py) — ligne 26 : `def early_paths(scores, bars)`
- [summarize_paths](../../scripts/research/us_top10_early_weakness_audit.py) — ligne 68 : `def summarize_paths(paths)`
- [run](../../scripts/research/us_top10_early_weakness_audit.py) — ligne 92 : `def run(output)`

## `scripts/research/us_top10_early_weakness_replay.py`

Source SHA-256 : `c5d46996673016c7cf3e69d459ed32e663d9d8e7409f566ade3a0bf2b87fc7e1`

- [run](../../scripts/research/us_top10_early_weakness_replay.py) — ligne 17 : `def run(source, output)`

## `scripts/research/us_top10_equal_sizing.py`

Source SHA-256 : `02d9ef1e20ebb45f809bc6c316f9bf55daa4c36df91587c5ea74401b523dc2fc`

- [EqualProposalSizer](../../scripts/research/us_top10_equal_sizing.py) — ligne 29 : `class EqualProposalSizer`
- [EqualProposalSizer.__init__](../../scripts/research/us_top10_equal_sizing.py) — ligne 30 : `def __init__(self, config, prices)`
- [EqualProposalSizer.compute](../../scripts/research/us_top10_equal_sizing.py) — ligne 38 : `def compute(self, price)`
- [EqualProposalBuilder](../../scripts/research/us_top10_equal_sizing.py) — ligne 52 : `class EqualProposalBuilder(PortfolioBuilder)`
- [EqualProposalBuilder.build](../../scripts/research/us_top10_equal_sizing.py) — ligne 53 : `def build(self, candidates, prices, *args, **kwargs)`
- [EqualProposalSession](../../scripts/research/us_top10_equal_sizing.py) — ligne 58 : `class EqualProposalSession(OraclePortfolioSession)`
- [EqualProposalSession.decide](../../scripts/research/us_top10_equal_sizing.py) — ligne 59 : `def decide(self, *args, **kwargs)`
- [audit_sizes](../../scripts/research/us_top10_equal_sizing.py) — ligne 65 : `def audit_sizes(source)`
- [run](../../scripts/research/us_top10_equal_sizing.py) — ligne 78 : `def run(source, output)`

## `scripts/research/us_top10_relative_sector_audit.py`

Source SHA-256 : `eadf542e231f877e8d85245bbd81a300d12ba8f184f87b306455f1a2e70331f4`

- [trailing_returns](../../scripts/research/us_top10_relative_sector_audit.py) — ligne 13 : `def trailing_returns(prices, horizon=20)`
- [peer_context](../../scripts/research/us_top10_relative_sector_audit.py) — ligne 18 : `def peer_context(frame, minimum_peers=5)`
- [run](../../scripts/research/us_top10_relative_sector_audit.py) — ligne 39 : `def run(output)`

## `scripts/restore_from_backup.py`

Source SHA-256 : `332dc0c90ee6f4fd27fa055448ef7afca2070bb6160be40a836e75b6fae31908`

- [RestoreReport](../../scripts/restore_from_backup.py) — ligne 51 : `class RestoreReport`
- [RestoreReport.to_dict](../../scripts/restore_from_backup.py) — ligne 67 : `def to_dict(self) -> dict[str, object]`
- [_detect_dump_age_seconds](../../scripts/restore_from_backup.py) — ligne 76 : `def _detect_dump_age_seconds(dump_path: Path) -> float | None`
- [_stream_dump](../../scripts/restore_from_backup.py) — ligne 82 : `def _stream_dump(dump_path: Path) -> Iterable[bytes]`
- [_have_mysql_cli](../../scripts/restore_from_backup.py) — ligne 93 : `def _have_mysql_cli() -> bool`
- [_load_dump](../../scripts/restore_from_backup.py) — ligne 97 : `def _load_dump(dump_path: Path, host: str, db: str, user: str, password: str) -> None`
- [_run_alembic_upgrade](../../scripts/restore_from_backup.py) — ligne 123 : `def _run_alembic_upgrade() -> None`
- [_count_tables](../../scripts/restore_from_backup.py) — ligne 130 : `def _count_tables(target_db: str) -> dict[str, int]`
- [_verify_audit_chain](../../scripts/restore_from_backup.py) — ligne 151 : `def _verify_audit_chain() -> bool`
- [restore](../../scripts/restore_from_backup.py) — ligne 162 : `def restore(*, dump_path: Path, target_host: str, target_db: str, user: str, password: str, dry_run: bool=False, skip_alembic: bool=False, skip_audit: bool=False) -> RestoreReport`
- [_build_parser](../../scripts/restore_from_backup.py) — ligne 226 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/restore_from_backup.py) — ligne 241 : `def main(argv: list[str] | None=None) -> int`

## `scripts/run_broker_reconciliation.py`

Source SHA-256 : `4899039ec800aa135a76b3377ae7f492380b29a01c0e3f82aaeb5db72c65e671`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `scripts/run_daily_parity.py`

Source SHA-256 : `c351306095d5dabe16f326b74d5fb854a1cc876e2c6526c77cb549e0af043698`

- [_default_live_loader](../../scripts/run_daily_parity.py) — ligne 42 : `def _default_live_loader(trade_date: date, account_id: str) -> pd.DataFrame`
- [_stub_replay_loader](../../scripts/run_daily_parity.py) — ligne 51 : `def _stub_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame`
- [build_replay_risk_context](../../scripts/run_daily_parity.py) — ligne 68 : `def build_replay_risk_context(tag: str, trade_date: date) -> dict`
- [_persist_risk_layer_artifacts](../../scripts/run_daily_parity.py) — ligne 118 : `def _persist_risk_layer_artifacts(trade_date: date, live_ctx: dict, replay_ctx: dict, divergences: list[dict]) -> dict`
- [build_arg_parser](../../scripts/run_daily_parity.py) — ligne 191 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../scripts/run_daily_parity.py) — ligne 219 : `def main(argv: Optional[list[str]]=None) -> int`
- [_default_replay_loader](../../scripts/run_daily_parity.py) — ligne 309 : `def _default_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame`

## `scripts/run_formal_verification.py`

Source SHA-256 : `e9a88a9bef0cf3d7baa541466680eb19974b5e869b7c7dcadebcfac5f6e0367f`

- [main](../../scripts/run_formal_verification.py) — ligne 20 : `def main() -> int`

## `scripts/run_fuzz_diff.py`

Source SHA-256 : `1916b3aaf6ae8735629cd9bbe5c8ec8077f210f4d21810b07ee8b73954c0a41d`

- [main](../../scripts/run_fuzz_diff.py) — ligne 20 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/run_ml_regime_ablation.py`

Source SHA-256 : `e0ceeb7b10fb0c8fedf0d9935f0b798120d83393a3dbebe859f169448726c6fa`

- [WindowSpec](../../scripts/run_ml_regime_ablation.py) — ligne 53 : `class WindowSpec`
- [VariantSpec](../../scripts/run_ml_regime_ablation.py) — ligne 61 : `class VariantSpec`
- [RunPlan](../../scripts/run_ml_regime_ablation.py) — ligne 69 : `class RunPlan`
- [_iso_now](../../scripts/run_ml_regime_ablation.py) — ligne 106 : `def _iso_now() -> str`
- [_add_bool_argument](../../scripts/run_ml_regime_ablation.py) — ligne 110 : `def _add_bool_argument(parser: argparse.ArgumentParser, *, name: str, default: bool, help_enabled: str, help_disabled: str) -> None`
- [_read_json](../../scripts/run_ml_regime_ablation.py) — ligne 125 : `def _read_json(path: Path) -> dict[str, Any] | None`
- [_write_json](../../scripts/run_ml_regime_ablation.py) — ligne 134 : `def _write_json(path: Path, payload: Any) -> None`
- [_get_nested](../../scripts/run_ml_regime_ablation.py) — ligne 139 : `def _get_nested(payload: dict[str, Any] | None, *keys: str) -> Any`
- [_safe_float](../../scripts/run_ml_regime_ablation.py) — ligne 148 : `def _safe_float(value: Any) -> float | None`
- [_safe_int](../../scripts/run_ml_regime_ablation.py) — ligne 157 : `def _safe_int(value: Any) -> int | None`
- [_normalize_windows_from_file](../../scripts/run_ml_regime_ablation.py) — ligne 166 : `def _normalize_windows_from_file(path: Path) -> tuple[WindowSpec, ...]`
- [resolve_windows](../../scripts/run_ml_regime_ablation.py) — ligne 187 : `def resolve_windows(window_preset: str, windows_file: Path | None) -> tuple[WindowSpec, ...]`
- [write_frozen_runtime_configs](../../scripts/run_ml_regime_ablation.py) — ligne 193 : `def write_frozen_runtime_configs(*, base_config_path: Path, output_root: Path) -> dict[str, Path]`
- [build_backtest_command](../../scripts/run_ml_regime_ablation.py) — ligne 222 : `def build_backtest_command(args: argparse.Namespace, *, window: WindowSpec, variant: VariantSpec, config_path: Path, output_dir: Path) -> tuple[str, ...]`
- [build_run_plans](../../scripts/run_ml_regime_ablation.py) — ligne 318 : `def build_run_plans(args: argparse.Namespace, *, windows: tuple[WindowSpec, ...], config_paths: dict[str, Path]) -> tuple[RunPlan, ...]`
- [write_plan_manifest](../../scripts/run_ml_regime_ablation.py) — ligne 347 : `def write_plan_manifest(plans: tuple[RunPlan, ...], *, output_root: Path, config_paths: dict[str, Path], base_config_path: Path) -> Path`
- [write_powershell_launcher](../../scripts/run_ml_regime_ablation.py) — ligne 381 : `def write_powershell_launcher(plans: tuple[RunPlan, ...], *, output_root: Path) -> Path`
- [execute_plans](../../scripts/run_ml_regime_ablation.py) — ligne 404 : `def execute_plans(plans: tuple[RunPlan, ...], *, skip_existing: bool, stop_on_error: bool) -> list[dict[str, Any]]`
- [collect_run_row](../../scripts/run_ml_regime_ablation.py) — ligne 447 : `def collect_run_row(plan: RunPlan) -> dict[str, Any]`
- [collect_run_rows](../../scripts/run_ml_regime_ablation.py) — ligne 505 : `def collect_run_rows(plans: tuple[RunPlan, ...]) -> list[dict[str, Any]]`
- [_mean_or_none](../../scripts/run_ml_regime_ablation.py) — ligne 509 : `def _mean_or_none(values: list[float]) -> float | None`
- [_median_or_none](../../scripts/run_ml_regime_ablation.py) — ligne 513 : `def _median_or_none(values: list[float]) -> float | None`
- [_positive_count](../../scripts/run_ml_regime_ablation.py) — ligne 517 : `def _positive_count(values: list[float]) -> int`
- [compute_factorial_effects](../../scripts/run_ml_regime_ablation.py) — ligne 521 : `def compute_factorial_effects(rows: list[dict[str, Any]]) -> dict[str, Any]`
- [build_decision_summary](../../scripts/run_ml_regime_ablation.py) — ligne 632 : `def build_decision_summary(rows: list[dict[str, Any]], effects: dict[str, Any]) -> dict[str, Any]`
- [_markdown_table](../../scripts/run_ml_regime_ablation.py) — ligne 717 : `def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str`
- [build_decision_markdown](../../scripts/run_ml_regime_ablation.py) — ligne 726 : `def build_decision_markdown(*, rows: list[dict[str, Any]], effects: dict[str, Any], decision: dict[str, Any], output_root: Path) -> str`
- [write_rows_csv](../../scripts/run_ml_regime_ablation.py) — ligne 830 : `def write_rows_csv(rows: list[dict[str, Any]], path: Path) -> None`
- [write_summary_outputs](../../scripts/run_ml_regime_ablation.py) — ligne 843 : `def write_summary_outputs(*, rows: list[dict[str, Any]], effects: dict[str, Any], decision: dict[str, Any], output_root: Path) -> dict[str, Path]`
- [build_arg_parser](../../scripts/run_ml_regime_ablation.py) — ligne 866 : `def build_arg_parser() -> argparse.ArgumentParser`
- [run](../../scripts/run_ml_regime_ablation.py) — ligne 955 : `def run(argv: list[str] | None=None) -> int`

## `scripts/run_monthly_broker_report.py`

Source SHA-256 : `399f8e89968117b993b563be9ba8fdd95867610a8a33260306233605cf1f9a34`

- [_month_bounds](../../scripts/run_monthly_broker_report.py) — ligne 29 : `def _month_bounds(month: str) -> tuple[date, date]`
- [main](../../scripts/run_monthly_broker_report.py) — ligne 38 : `def main(argv: list[str] | None=None) -> int`

## `scripts/run_mutation_testing.py`

Source SHA-256 : `6bd0dc83490a93914f5bd0723f74661a91144d5b7a0664667cce767a8c814ed6`

- [_parse_mutmut_results](../../scripts/run_mutation_testing.py) — ligne 29 : `def _parse_mutmut_results(stdout: str) -> dict[str, int]`
- [_run_module](../../scripts/run_mutation_testing.py) — ligne 42 : `def _run_module(module: str) -> dict`
- [main](../../scripts/run_mutation_testing.py) — ligne 73 : `def main() -> int`

## `scripts/run_pre_audit_checklist.py`

Source SHA-256 : `4a3506035dc6626b47c9c8fa99a50e41a038db2f9479c28d59b80ad62f85591d`

- [CheckResult](../../scripts/run_pre_audit_checklist.py) — ligne 29 : `class CheckResult`
- [CheckResult.to_dict](../../scripts/run_pre_audit_checklist.py) — ligne 35 : `def to_dict(self) -> dict`
- [_exists](../../scripts/run_pre_audit_checklist.py) — ligne 39 : `def _exists(rel: str) -> Callable[[], CheckResult]`
- [_has_artifact](../../scripts/run_pre_audit_checklist.py) — ligne 48 : `def _has_artifact(rel_glob: str) -> Callable[[], CheckResult]`
- [run_checks](../../scripts/run_pre_audit_checklist.py) — ligne 96 : `def run_checks() -> list[CheckResult]`
- [_score](../../scripts/run_pre_audit_checklist.py) — ligne 105 : `def _score(results: Sequence[CheckResult]) -> dict`
- [write_reports](../../scripts/run_pre_audit_checklist.py) — ligne 119 : `def write_reports(results: list[CheckResult], out_dir: Path) -> tuple[Path, Path]`
- [main](../../scripts/run_pre_audit_checklist.py) — ligne 150 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/run_pre_live_checklist.py`

Source SHA-256 : `3f37989960d98aaa545b4550c6c9fd2ca08b846ec07ec7831d6d8ab20169658a`

- [_git_sha](../../scripts/run_pre_live_checklist.py) — ligne 39 : `def _git_sha() -> str | None`
- [_config_fingerprint](../../scripts/run_pre_live_checklist.py) — ligne 52 : `def _config_fingerprint(path: Path) -> str | None`
- [_build_parser](../../scripts/run_pre_live_checklist.py) — ligne 58 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../scripts/run_pre_live_checklist.py) — ligne 70 : `def main(argv: list[str] | None=None) -> int`

## `scripts/run_quarterly_weights_calibration.py`

Source SHA-256 : `19bf0a26e1d6191decbc5fc1dd2662f4324480aa5b944039ecf7caa194213a35`

- [_months_back](../../scripts/run_quarterly_weights_calibration.py) — ligne 40 : `def _months_back(reference: date, months: int) -> date`
- [_build_arg_parser](../../scripts/run_quarterly_weights_calibration.py) — ligne 51 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [_load_previous_calibration](../../scripts/run_quarterly_weights_calibration.py) — ligne 136 : `def _load_previous_calibration(output_root: Path, current_dir: Path) -> dict[str, Any] | None`
- [_compute_drift_pct](../../scripts/run_quarterly_weights_calibration.py) — ligne 158 : `def _compute_drift_pct(current: float, previous: float) -> float`
- [_serialize_result](../../scripts/run_quarterly_weights_calibration.py) — ligne 164 : `def _serialize_result(result: Any) -> dict[str, Any]`
- [_normalize_dates](../../scripts/run_quarterly_weights_calibration.py) — ligne 181 : `def _normalize_dates(payload: dict[str, Any]) -> dict[str, Any]`
- [_normalize_result_payload](../../scripts/run_quarterly_weights_calibration.py) — ligne 188 : `def _normalize_result_payload(result: Any) -> dict[str, Any]`
- [_extract_reference_final_value](../../scripts/run_quarterly_weights_calibration.py) — ligne 192 : `def _extract_reference_final_value(payload: dict[str, Any]) -> float | None`
- [_normalize_int_sequence](../../scripts/run_quarterly_weights_calibration.py) — ligne 210 : `def _normalize_int_sequence(values: list[int] | tuple[int, ...] | None, *, default: Sequence[int]) -> list[int]`
- [_serialize_drift](../../scripts/run_quarterly_weights_calibration.py) — ligne 215 : `def _serialize_drift(result: Any) -> dict[str, Any]`
- [_build_governance_summary](../../scripts/run_quarterly_weights_calibration.py) — ligne 219 : `def _build_governance_summary(segment_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]`
- [_supports_segment_drift](../../scripts/run_quarterly_weights_calibration.py) — ligne 237 : `def _supports_segment_drift(result: Any) -> bool`
- [run](../../scripts/run_quarterly_weights_calibration.py) — ligne 250 : `def run(*, end: date | None=None, lookback_months: int=12, threshold_drift_pct: float=0.05, output_root: Path=DEFAULT_OUTPUT_ROOT, no_alert: bool=False, segment_horizons: list[int] | None=None, segment_lookback_months: list[int] | None=None, reference_live_horizon_days: int=5, reference_live_lookback_months: int | None=None, min_live_observations: int=250, min_live_snapshot_days: int=20, min_live_symbols: int=10, calibrator_factory=None, notifier_factory=None) -> int`
- [main](../../scripts/run_quarterly_weights_calibration.py) — ligne 444 : `def main(argv: list[str] | None=None) -> int`

## `scripts/run_tlaps.py`

Source SHA-256 : `7c02c41a4342d7b0e63270b9662f9b906cd89ab677d3f215990931846b2adc65`

- [_run_tlapm](../../scripts/run_tlaps.py) — ligne 31 : `def _run_tlapm(spec: Path) -> dict`
- [_run_tlc](../../scripts/run_tlaps.py) — ligne 50 : `def _run_tlc(spec: Path) -> dict`
- [run_all](../../scripts/run_tlaps.py) — ligne 70 : `def run_all(out_dir: Path) -> dict`
- [main](../../scripts/run_tlaps.py) — ligne 100 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/sandbox_health_collect.py`

Source SHA-256 : `b76f86743cc3042c9ac9d84daf283308e7133aa86bdcc4985958a90a2ab4fc63`

- [_safe_read_json](../../scripts/sandbox_health_collect.py) — ligne 28 : `def _safe_read_json(path: Path) -> dict | None`
- [collect_health](../../scripts/sandbox_health_collect.py) — ligne 35 : `def collect_health(*, run_id: str, status: str, sha: str | None=None, reconciliation_path: Path | None=None, audit_chain_ok: bool | None=None, stage_durations: dict[str, float] | None=None) -> dict`
- [main](../../scripts/sandbox_health_collect.py) — ligne 64 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/sandbox_health_rollup.py`

Source SHA-256 : `88ea16ddeaed7bc6b85ac06cb25ca8a0322d345593f14598599f6a49c48c3a79`

- [compute_rollup](../../scripts/sandbox_health_rollup.py) — ligne 41 : `def compute_rollup(sandbox_dir: Path, *, window: int=DEFAULT_WINDOW, today: date | None=None) -> dict`
- [main](../../scripts/sandbox_health_rollup.py) — ligne 108 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/scan_cves.py`

Source SHA-256 : `255bee4f1569d48ff7c7fe6cb804e7372789121e5b7c18da13fab81e0e6937d2`

- [_run_pip_audit](../../scripts/scan_cves.py) — ligne 26 : `def _run_pip_audit(output: Path) -> dict | None`
- [_max_severity](../../scripts/scan_cves.py) — ligne 45 : `def _max_severity(report: dict) -> str | None`
- [main](../../scripts/scan_cves.py) — ligne 57 : `def main() -> int`

## `scripts/scan_repo_secrets.py`

Source SHA-256 : `c9602395673c593b3fdbdb9ee1e2afedde5f7b7cd0728b45c32e172673a6c778`

- [main](../../scripts/scan_repo_secrets.py) — ligne 23 : `def main(argv: list[str] | None=None) -> int`

## `scripts/send_batch_email.py`

Source SHA-256 : `b70b0958f9952769994e1977ba78137bc587be99bce97f7355478d43c2006fcd`

- [_read_run_log](../../scripts/send_batch_email.py) — ligne 37 : `def _read_run_log(log_file: str, *, max_lines: int, max_chars: int) -> str`
- [_extract_run_summaries](../../scripts/send_batch_email.py) — ligne 69 : `def _extract_run_summaries(log_text: str) -> list[dict]`
- [_as_count](../../scripts/send_batch_email.py) — ligne 84 : `def _as_count(value, default: int=0) -> int`
- [_first_count](../../scripts/send_batch_email.py) — ligne 93 : `def _first_count(summary: dict, names: tuple[str, ...], default: int=0) -> int`
- [_sum_first_counts](../../scripts/send_batch_email.py) — ligne 100 : `def _sum_first_counts(summaries: list[dict], names: tuple[str, ...]) -> int`
- [_sum_matching_counts](../../scripts/send_batch_email.py) — ligne 104 : `def _sum_matching_counts(summaries: list[dict], suffix: str) -> int`
- [_extract_error_message](../../scripts/send_batch_email.py) — ligne 115 : `def _extract_error_message(log_text: str, summary: dict, *, status: str) -> str`
- [_build_metrics](../../scripts/send_batch_email.py) — ligne 127 : `def _build_metrics(args, log_text: str) -> dict[str, object]`
- [_send_telegram_status](../../scripts/send_batch_email.py) — ligne 171 : `def _send_telegram_status(args) -> bool`
- [main](../../scripts/send_batch_email.py) — ligne 238 : `def main() -> int`

## `scripts/smoke_sprint6_cn.py`

Source SHA-256 : `a776f50dc8f6f153075fc42aa0f30330ed5690a45712c222362255e84034d1b3`

- [_page](../../scripts/smoke_sprint6_cn.py) — ligne 25 : `def _page(close_price: str) -> TusharePage`
- [run](../../scripts/smoke_sprint6_cn.py) — ligne 50 : `def run(output_path: Path) -> dict[str, Any]`
- [main](../../scripts/smoke_sprint6_cn.py) — ligne 139 : `def main() -> None`

## `scripts/verify_audit_chain.py`

Source SHA-256 : `78aaeed4adf0bef0e700ecc2668c3c44d2953863403b4da90905d17adcc167f6`

- [main](../../scripts/verify_audit_chain.py) — ligne 20 : `def main(argv: Sequence[str] | None=None) -> int`

## `scripts/verify_vault_rotation.py`

Source SHA-256 : `af55942ea85ad36786e2f0e66773d09f31ba3e4e1cecee8cfcefd9b075f039be`

- [_latest_version_age_days](../../scripts/verify_vault_rotation.py) — ligne 35 : `def _latest_version_age_days(vault: Any, key: str) -> tuple[int | None, float | None]`
- [verify](../../scripts/verify_vault_rotation.py) — ligne 76 : `def verify(keys: list[str], *, max_age_days: int=RETENTION_DAYS, vault: Any | None=None, output_dir: Path | None=None) -> dict[str, Any]`
- [main](../../scripts/verify_vault_rotation.py) — ligne 120 : `def main(argv: list[str] | None=None) -> int`
