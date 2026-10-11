# Inventaire API — event_sentiment

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `event_sentiment/__init__.py`

Source SHA-256 : `78954fafae04f136d3ab5d4e4b1d276e3a261301259f57cf8a0c11cf127bff79`

- [__getattr__](../../event_sentiment/__init__.py) — ligne 13 : `def __getattr__(name: str)`

## `event_sentiment/__main__.py`

Source SHA-256 : `b2dc58c61513a8b728095c82bf5692a294e782da8f8ab72d55a2af4287e7dcf9`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `event_sentiment/aggregation.py`

Source SHA-256 : `ae66dcbaf81fa5bc92902c3fa90402308abbda43e413d33665953e2b9dfe4074`

- [_safe_series_divide](../../event_sentiment/aggregation.py) — ligne 9 : `def _safe_series_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series`
- [_coerce_trade_date](../../event_sentiment/aggregation.py) — ligne 14 : `def _coerce_trade_date(series: pd.Series) -> pd.Series`
- [_rolling_sum](../../event_sentiment/aggregation.py) — ligne 18 : `def _rolling_sum(series: pd.Series, window: int) -> pd.Series`
- [_rolling_max](../../event_sentiment/aggregation.py) — ligne 22 : `def _rolling_max(series: pd.Series, window: int) -> pd.Series`
- [build_ticker_daily_features](../../event_sentiment/aggregation.py) — ligne 26 : `def build_ticker_daily_features(article_df: pd.DataFrame, feature_version: str='v2', rolling_windows: tuple[int, ...]=DEFAULT_ROLLING_WINDOWS) -> pd.DataFrame`
- [build_sector_daily_features](../../event_sentiment/aggregation.py) — ligne 142 : `def build_sector_daily_features(sector_article_df: pd.DataFrame, macro_df: pd.DataFrame, feature_version: str='v2', rolling_windows: tuple[int, ...]=DEFAULT_ROLLING_WINDOWS) -> pd.DataFrame`

## `event_sentiment/cli.py`

Source SHA-256 : `4c1fd6af2478ca6af97c7c18f18c8f3457db064c5046ce31289024c515755c46`

- [_utc_now_naive](../../event_sentiment/cli.py) — ligne 18 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../event_sentiment/cli.py) — ligne 22 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../event_sentiment/cli.py) — ligne 26 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_coerce_int](../../event_sentiment/cli.py) — ligne 33 : `def _coerce_int(value: object) -> int`
- [_build_cli_run_summary](../../event_sentiment/cli.py) — ligne 41 : `def _build_cli_run_summary(*, stats: dict[str, object], started_at: datetime, finished_at: datetime, config: EventSentimentConfig | None=None) -> dict[str, object]`
- [build_arg_parser](../../event_sentiment/cli.py) — ligne 113 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../event_sentiment/cli.py) — ligne 289 : `def main() -> None`

## `event_sentiment/config.py`

Source SHA-256 : `70d13f89ef1519b5f62b1f95eaa6aaa3e8e7b95d499623e77ad1baab430d6dd0`

- [EventSentimentConfig](../../event_sentiment/config.py) — ligne 21 : `class EventSentimentConfig`
- [EventSentimentConfig.__post_init__](../../event_sentiment/config.py) — ligne 82 : `def __post_init__(self) -> None`
- [EventSentimentConfig.for_provider](../../event_sentiment/config.py) — ligne 137 : `def for_provider(cls, news_provider: NewsProvider, **overrides: object) -> 'EventSentimentConfig'`

## `event_sentiment/db_io.py`

Source SHA-256 : `d07cfb56a10427dd6f625087a6f8b0180af2880ee7020c3983d5e22e87ca8e8e`

- [EventSentimentRepository](../../event_sentiment/db_io.py) — ligne 24 : `class EventSentimentRepository`
- [EventSentimentRepository.__init__](../../event_sentiment/db_io.py) — ligne 25 : `def __init__(self) -> None`
- [EventSentimentRepository._table](../../event_sentiment/db_io.py) — ligne 30 : `def _table(self, table_name: str) -> Table`
- [EventSentimentRepository._normalize_mysql_scalar](../../event_sentiment/db_io.py) — ligne 36 : `def _normalize_mysql_scalar(value: Any) -> Any`
- [EventSentimentRepository._normalize_mysql_records](../../event_sentiment/db_io.py) — ligne 50 : `def _normalize_mysql_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]`
- [EventSentimentRepository._resolve_rowcount](../../event_sentiment/db_io.py) — ligne 57 : `def _resolve_rowcount(raw_rowcount: Any) -> int`
- [EventSentimentRepository._upsert_batch_size](../../event_sentiment/db_io.py) — ligne 65 : `def _upsert_batch_size() -> int`
- [EventSentimentRepository._chunk_records](../../event_sentiment/db_io.py) — ligne 82 : `def _chunk_records(records: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]`
- [EventSentimentRepository._upsert_retry_attempts](../../event_sentiment/db_io.py) — ligne 88 : `def _upsert_retry_attempts() -> int`
- [EventSentimentRepository._upsert_retry_backoff_seconds](../../event_sentiment/db_io.py) — ligne 105 : `def _upsert_retry_backoff_seconds() -> float`
- [EventSentimentRepository._is_retryable_mysql_operational_error](../../event_sentiment/db_io.py) — ligne 122 : `def _is_retryable_mysql_operational_error(exc: OperationalError) -> bool`
- [EventSentimentRepository._upsert](../../event_sentiment/db_io.py) — ligne 133 : `def _upsert(self, table_name: str, records: list[dict[str, Any]], key_columns: set[str]) -> int`
- [EventSentimentRepository._normalize_symbol](../../event_sentiment/db_io.py) — ligne 210 : `def _normalize_symbol(symbol: str) -> str`
- [EventSentimentRepository._build_contextual_relevance_filters](../../event_sentiment/db_io.py) — ligne 217 : `def _build_contextual_relevance_filters(min_relevance: float) -> tuple[list[str], dict[str, float]]`
- [EventSentimentRepository._build_pending_article_query](../../event_sentiment/db_io.py) — ligne 236 : `def _build_pending_article_query(self, *, count_only: bool, start_date: date | None=None, end_date: date | None=None, ingestion_source: str | None=None, symbols: list[str] | None=None)`
- [EventSentimentRepository.get_checkpoint](../../event_sentiment/db_io.py) — ligne 292 : `def get_checkpoint(self, source_name: str, symbol: str) -> dict[str, Any] | None`
- [EventSentimentRepository.get_checkpoints](../../event_sentiment/db_io.py) — ligne 309 : `def get_checkpoints(self, source_name: str, symbols: list[str]) -> dict[str, dict[str, Any]]`
- [EventSentimentRepository.load_tradable_universe_symbols](../../event_sentiment/db_io.py) — ligne 330 : `def load_tradable_universe_symbols(self) -> list[str]`
- [EventSentimentRepository.list_scored_trade_dates](../../event_sentiment/db_io.py) — ligne 360 : `def list_scored_trade_dates(self, start_date: date | None=None, end_date: date | None=None, ingestion_source: str | None=None) -> list[date]`
- [EventSentimentRepository.upsert_checkpoint](../../event_sentiment/db_io.py) — ligne 389 : `def upsert_checkpoint(self, source_name: str, symbol: str, watermark_published_at_utc: datetime | None, next_page_token: str | None, status: str, last_error: str | None=None) -> None`
- [EventSentimentRepository._checkpoint_stage_column](../../event_sentiment/db_io.py) — ligne 412 : `def _checkpoint_stage_column(stage: str) -> str`
- [EventSentimentRepository.touch_checkpoint_stage](../../event_sentiment/db_io.py) — ligne 424 : `def touch_checkpoint_stage(self, source_name: str, symbols: list[str], *, stage: str, touched_at: datetime | None=None) -> int`
- [EventSentimentRepository.list_ticker_map_symbols](../../event_sentiment/db_io.py) — ligne 451 : `def list_ticker_map_symbols(self, *, start_date: date | None=None, end_date: date | None=None, ingestion_source: str | None=None, symbols: list[str] | None=None) -> list[str]`
- [EventSentimentRepository.get_signal_aggregator_guard_status](../../event_sentiment/db_io.py) — ligne 490 : `def get_signal_aggregator_guard_status(self, *, source_name: str, symbols: list[str]) -> dict[str, Any]`
- [EventSentimentRepository.get_existing_article_ids](../../event_sentiment/db_io.py) — ligne 540 : `def get_existing_article_ids(self, article_ids: list[str]) -> set[str]`
- [EventSentimentRepository.get_article_ids_by_dedupe_hashes](../../event_sentiment/db_io.py) — ligne 550 : `def get_article_ids_by_dedupe_hashes(self, ingestion_source: str, dedupe_hashes: list[str]) -> dict[str, str]`
- [EventSentimentRepository.upsert_news_raw](../../event_sentiment/db_io.py) — ligne 580 : `def upsert_news_raw(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.upsert_news_ticker_map](../../event_sentiment/db_io.py) — ligne 588 : `def upsert_news_ticker_map(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.upsert_news_sentiment](../../event_sentiment/db_io.py) — ligne 600 : `def upsert_news_sentiment(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.upsert_news_ticker_sentiment](../../event_sentiment/db_io.py) — ligne 603 : `def upsert_news_ticker_sentiment(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.load_pending_contextual_pairs](../../event_sentiment/db_io.py) — ligne 611 : `def load_pending_contextual_pairs(self, limit: int=5000, min_relevance: float=0.0, *, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None) -> list[dict[str, Any]]`
- [EventSentimentRepository.count_pending_contextual_pairs](../../event_sentiment/db_io.py) — ligne 691 : `def count_pending_contextual_pairs(self, *, min_relevance: float=0.0, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None) -> int`
- [EventSentimentRepository.iter_ticker_map_for_relevance_backfill](../../event_sentiment/db_io.py) — ligne 753 : `def iter_ticker_map_for_relevance_backfill(self, batch_size: int=500, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None, rescore_all: bool=False)`
- [EventSentimentRepository.delete_ticker_map_below_score](../../event_sentiment/db_io.py) — ligne 841 : `def delete_ticker_map_below_score(self, threshold: float, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None) -> int`
- [EventSentimentRepository.get_active_finbert_fingerprints](../../event_sentiment/db_io.py) — ligne 889 : `def get_active_finbert_fingerprints(self, trade_date: date) -> list[str]`
- [EventSentimentRepository.upsert_macro_event_audit](../../event_sentiment/db_io.py) — ligne 918 : `def upsert_macro_event_audit(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.upsert_ticker_daily_features](../../event_sentiment/db_io.py) — ligne 930 : `def upsert_ticker_daily_features(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.upsert_sector_daily_features](../../event_sentiment/db_io.py) — ligne 933 : `def upsert_sector_daily_features(self, records: list[dict[str, Any]]) -> int`
- [EventSentimentRepository.count_pending_articles](../../event_sentiment/db_io.py) — ligne 936 : `def count_pending_articles(self, *, start_date: date | None=None, end_date: date | None=None, ingestion_source: str | None=None, symbols: list[str] | None=None) -> int`
- [EventSentimentRepository.load_pending_articles](../../event_sentiment/db_io.py) — ligne 954 : `def load_pending_articles(self, limit: int=1000, *, start_date: date | None=None, end_date: date | None=None, ingestion_source: str | None=None, symbols: list[str] | None=None) -> list[dict[str, Any]]`
- [EventSentimentRepository.load_feature_frames](../../event_sentiment/db_io.py) — ligne 976 : `def load_feature_frames(self, start_date: date | None=None, end_date: date | None=None, trade_dates: list[date] | None=None, ingestion_source: str | None=None, ticker_symbols: list[str] | None=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`

## `event_sentiment/event_sentiment_pipeline.py`

Source SHA-256 : `ef8ee4e6863d40d46575745f03a6f2ddcea50356ade0886e3f5e9e0c23873bd1`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `event_sentiment/history_backfill.py`

Source SHA-256 : `d6eb9eb1af66d49092cb84c658003cea3f96c31ecff355871e8b91e0416ca674`

- [_utc_now_naive](../../event_sentiment/history_backfill.py) — ligne 27 : `def _utc_now_naive() -> datetime`
- [_resolve_heartbeat_interval_seconds](../../event_sentiment/history_backfill.py) — ligne 31 : `def _resolve_heartbeat_interval_seconds() -> float`
- [_format_log_context](../../event_sentiment/history_backfill.py) — ligne 48 : `def _format_log_context(**context: object) -> str`
- [_log_phase](../../event_sentiment/history_backfill.py) — ligne 54 : `def _log_phase(phase_name: str, **context: object) -> Iterator[None]`
- [EventSentimentHistoryBackfillResult](../../event_sentiment/history_backfill.py) — ligne 92 : `class EventSentimentHistoryBackfillResult`
- [EventSentimentHistoryBackfillService](../../event_sentiment/history_backfill.py) — ligne 102 : `class EventSentimentHistoryBackfillService`
- [EventSentimentHistoryBackfillService.__init__](../../event_sentiment/history_backfill.py) — ligne 103 : `def __init__(self, repository: EventSentimentRepository | None=None, config: EventSentimentConfig | None=None) -> None`
- [EventSentimentHistoryBackfillService.resolve_bounds](../../event_sentiment/history_backfill.py) — ligne 111 : `def resolve_bounds(self, start_date: date | None=None, end_date: date | None=None, years: int | None=None, ingestion_source: str | None=None) -> tuple[date, date]`
- [EventSentimentHistoryBackfillService.list_trade_dates](../../event_sentiment/history_backfill.py) — ligne 150 : `def list_trade_dates(self, start_date: date, end_date: date, *, ingestion_source: str | None=None) -> list[date]`
- [EventSentimentHistoryBackfillService._chunk_dates](../../event_sentiment/history_backfill.py) — ligne 164 : `def _chunk_dates(trade_dates: Sequence[date], batch_days: int) -> list[list[date]]`
- [EventSentimentHistoryBackfillService.backfill](../../event_sentiment/history_backfill.py) — ligne 167 : `def backfill(self, start_date: date | None=None, end_date: date | None=None, years: int | None=None, batch_days: int | None=None, *, ingestion_source: str | None=None, ticker_symbols: list[str] | None=None) -> EventSentimentHistoryBackfillResult`
- [_build_run_id](../../event_sentiment/history_backfill.py) — ligne 353 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../event_sentiment/history_backfill.py) — ligne 357 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_build_arg_parser](../../event_sentiment/history_backfill.py) — ligne 361 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../event_sentiment/history_backfill.py) — ligne 391 : `def main(argv: list[str] | None=None) -> int`

## `event_sentiment/importe_news.py`

Source SHA-256 : `8b608e178d4e6891e3d188dfa61447c586704f4484bd2177dc53dda62a127683`

- [_normalize_symbols](../../event_sentiment/importe_news.py) — ligne 20 : `def _normalize_symbols(symbols: list[str]) -> list[str]`
- [_load_distinct_symbols](../../event_sentiment/importe_news.py) — ligne 32 : `def _load_distinct_symbols(query: str) -> list[str]`
- [get_all_symbols_from_stock_bars_daily](../../event_sentiment/importe_news.py) — ligne 39 : `def get_all_symbols_from_stock_bars_daily()`
- [get_all_symbols_from_stock_scores](../../event_sentiment/importe_news.py) — ligne 44 : `def get_all_symbols_from_stock_scores(*, selected_only: bool=False) -> list[str]`
- [get_all_symbols_from_stock_scores_history](../../event_sentiment/importe_news.py) — ligne 57 : `def get_all_symbols_from_stock_scores_history() -> list[str]`
- [get_all_symbols_from_stock_scores_all](../../event_sentiment/importe_news.py) — ligne 68 : `def get_all_symbols_from_stock_scores_all() -> list[str]`
- [get_all_symbols_from_tradable_universe](../../event_sentiment/importe_news.py) — ligne 83 : `def get_all_symbols_from_tradable_universe() -> list[str]`
- [resolve_symbols_from_inputs](../../event_sentiment/importe_news.py) — ligne 120 : `def resolve_symbols_from_inputs(*, symbols_csv: str | None, symbol_source: str, repository: EventSentimentRepository, logger: logging.Logger | None=None) -> tuple[list[str], str]`
- [resolve_symbols](../../event_sentiment/importe_news.py) — ligne 154 : `def resolve_symbols(args: argparse.Namespace, repository: EventSentimentRepository, logger: logging.Logger) -> tuple[list[str], str]`
- [_apply_symbol_guardrails](../../event_sentiment/importe_news.py) — ligne 167 : `def _apply_symbol_guardrails(*, symbol_source: str, symbols: list[str], max_symbols: int | None, logger: logging.Logger, parser: argparse.ArgumentParser) -> None`
- [_warn_ignored_scoring_flags](../../event_sentiment/importe_news.py) — ligne 194 : `def _warn_ignored_scoring_flags(args: argparse.Namespace, logger: logging.Logger) -> None`
- [_coerce_utc_datetime](../../event_sentiment/importe_news.py) — ligne 210 : `def _coerce_utc_datetime(value: object) -> datetime | None`
- [_resolve_checkpoint_aware_import_scope](../../event_sentiment/importe_news.py) — ligne 218 : `def _resolve_checkpoint_aware_import_scope(*, symbols: list[str], start_utc: datetime, end_utc: datetime, repository: EventSentimentRepository, config: EventSentimentConfig, logger: logging.Logger) -> tuple[list[str], dict[str, datetime], dict[str, bool], int]`
- [build_arg_parser](../../event_sentiment/importe_news.py) — ligne 270 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../event_sentiment/importe_news.py) — ligne 371 : `def main()`

## `event_sentiment/ingestion.py`

Source SHA-256 : `107dde5e3a10993a863fdf6a1b9b24328eab5a3ee5fc89f1e20640e97ebe4515`

- [_resolve_iter_news_pages](../../event_sentiment/ingestion.py) — ligne 34 : `def _resolve_iter_news_pages(provider: str) -> Callable[..., Any]`
- [NewsIngestionService](../../event_sentiment/ingestion.py) — ligne 43 : `class NewsIngestionService`
- [NewsIngestionService.__init__](../../event_sentiment/ingestion.py) — ligne 44 : `def __init__(self, repository, config) -> None`
- [NewsIngestionService._normalize_article](../../event_sentiment/ingestion.py) — ligne 74 : `def _normalize_article(self, payload: dict[str, Any]) -> NormalizedNewsArticle`
- [NewsIngestionService._normalize_symbol_list](../../event_sentiment/ingestion.py) — ligne 114 : `def _normalize_symbol_list(symbols: list[str] | None) -> list[str]`
- [NewsIngestionService._resolve_symbol_start](../../event_sentiment/ingestion.py) — ligne 119 : `def _resolve_symbol_start(self, symbol: str, start_utc: datetime | None, end_utc: datetime) -> datetime`
- [NewsIngestionService._resolve_persisted_article_ids](../../event_sentiment/ingestion.py) — ligne 128 : `def _resolve_persisted_article_ids(self, raw_rows: list[dict[str, Any]]) -> dict[str, str]`
- [NewsIngestionService._run_symbol](../../event_sentiment/ingestion.py) — ligne 149 : `def _run_symbol(self, symbol: str, start_utc: datetime, end_utc: datetime, resume_checkpoint: bool) -> dict[str, int]`
- [NewsIngestionService.run](../../event_sentiment/ingestion.py) — ligne 382 : `def run(self, start_utc: datetime | None, end_utc: datetime, symbols: list[str] | None=None, symbol_start_overrides: dict[str, datetime] | None=None, symbol_resume_overrides: dict[str, bool] | None=None, resume_checkpoints: bool=True, progress_callback: Callable[[dict[str, object]], None] | None=None) -> dict[str, int]`

## `event_sentiment/macro_rules.py`

Source SHA-256 : `64399e1f306b2440e5f3532373c316c1f713510f127ebe1382be63b943fa4870`

- [MacroRule](../../event_sentiment/macro_rules.py) — ligne 8 : `class MacroRule`
- [IntensityWeights](../../event_sentiment/macro_rules.py) — ligne 16 : `class IntensityWeights(NamedTuple)`
- [MacroRuleEngine](../../event_sentiment/macro_rules.py) — ligne 99 : `class MacroRuleEngine`
- [MacroRuleEngine.__init__](../../event_sentiment/macro_rules.py) — ligne 100 : `def __init__(self, rule_version: str='macro_rules_v1', intensity_weights: IntensityWeights | None=None) -> None`
- [MacroRuleEngine._compute_intensity](../../event_sentiment/macro_rules.py) — ligne 108 : `def _compute_intensity(self, hits: list[str], sentiment: SentimentRecord) -> float`
- [MacroRuleEngine.classify](../../event_sentiment/macro_rules.py) — ligne 126 : `def classify(self, article: NormalizedNewsArticle, sentiment: SentimentRecord) -> list[MacroImpactRecord]`

## `event_sentiment/mapping.py`

Source SHA-256 : `ac2b60cff1b9f8d3dace0913b86c296b84164aa6f250022057eedb1fd26684aa`

- [EntitySectorMapper](../../event_sentiment/mapping.py) — ligne 13 : `class EntitySectorMapper`
- [EntitySectorMapper.__init__](../../event_sentiment/mapping.py) — ligne 14 : `def __init__(self) -> None`
- [EntitySectorMapper._load_local_sectors](../../event_sentiment/mapping.py) — ligne 18 : `def _load_local_sectors(self, symbols: Iterable[str]) -> dict[str, dict]`
- [EntitySectorMapper.resolve](../../event_sentiment/mapping.py) — ligne 54 : `def resolve(self, symbols: Iterable[str], allow_fallback: bool=True) -> dict[str, dict]`

## `event_sentiment/models.py`

Source SHA-256 : `cbb39695e97aac2cf1b0abbf159e0c36f1105ffa4298fc386d0aa447be0ca29e`

- [NormalizedNewsArticle](../../event_sentiment/models.py) — ligne 7 : `class NormalizedNewsArticle`
- [SentimentRecord](../../event_sentiment/models.py) — ligne 26 : `class SentimentRecord`
- [ContextualSentimentRecord](../../event_sentiment/models.py) — ligne 46 : `class ContextualSentimentRecord`
- [MacroImpactRecord](../../event_sentiment/models.py) — ligne 76 : `class MacroImpactRecord`

## `event_sentiment/pipeline.py`

Source SHA-256 : `0bd9b69a3458c23447a5d394a6d606e45d15c9108fb7c2668a6dd03b0de26f8d`

- [_coerce_int](../../event_sentiment/pipeline.py) — ligne 17 : `def _coerce_int(value: object) -> int`
- [EventSentimentPipeline](../../event_sentiment/pipeline.py) — ligne 25 : `class EventSentimentPipeline`
- [EventSentimentPipeline.__init__](../../event_sentiment/pipeline.py) — ligne 26 : `def __init__(self, repository, config, progress_callback: Callable[[dict[str, object]], None] | None=None) -> None`
- [EventSentimentPipeline._touch_checkpoint_stage_if_supported](../../event_sentiment/pipeline.py) — ligne 46 : `def _touch_checkpoint_stage_if_supported(self, symbols: list[str], *, stage: str) -> int`
- [EventSentimentPipeline._coerce_utc](../../event_sentiment/pipeline.py) — ligne 56 : `def _coerce_utc(value: datetime | None) -> datetime | None`
- [EventSentimentPipeline._resolve_symbols](../../event_sentiment/pipeline.py) — ligne 63 : `def _resolve_symbols(self, symbols: list[str] | None) -> list[str]`
- [EventSentimentPipeline._resolve_time_window](../../event_sentiment/pipeline.py) — ligne 80 : `def _resolve_time_window(self, start_utc: datetime | None, end_utc: datetime | None) -> tuple[datetime, datetime]`
- [EventSentimentPipeline._build_pending_scope](../../event_sentiment/pipeline.py) — ligne 108 : `def _build_pending_scope(self, *, start_utc: datetime | None, end_utc: datetime | None, symbols: list[str] | None, skip_ingestion: bool) -> dict[str, object]`
- [EventSentimentPipeline._resolve_symbol_windows](../../event_sentiment/pipeline.py) — ligne 127 : `def _resolve_symbol_windows(self, start_utc: datetime | None, end_utc: datetime | None, symbols: list[str]) -> tuple[dict[str, datetime], dict[str, bool], datetime]`
- [EventSentimentPipeline._rows_to_articles](../../event_sentiment/pipeline.py) — ligne 201 : `def _rows_to_articles(pending_rows: list[dict[str, object]]) -> list[NormalizedNewsArticle]`
- [EventSentimentPipeline._capture_finbert_runtime_stats](../../event_sentiment/pipeline.py) — ligne 223 : `def _capture_finbert_runtime_stats(self, stats: dict[str, object]) -> None`
- [EventSentimentPipeline._resolve_scoring_mode](../../event_sentiment/pipeline.py) — ligne 231 : `def _resolve_scoring_mode(self) -> str`
- [EventSentimentPipeline._score_pending_batches](../../event_sentiment/pipeline.py) — ligne 241 : `def _score_pending_batches(self, pending_scope: dict[str, object], stats: dict[str, object], *, resolved_symbols: list[str], skip_features: bool=False) -> tuple[int, list[date], list[date]]`
- [EventSentimentPipeline._chunk_trade_dates](../../event_sentiment/pipeline.py) — ligne 342 : `def _chunk_trade_dates(trade_dates: Sequence[date], batch_days: int) -> list[list[date]]`
- [EventSentimentPipeline._flush_feature_aggregation](../../event_sentiment/pipeline.py) — ligne 347 : `def _flush_feature_aggregation(self, *, impacted_trade_dates: list[date], resolved_symbols: list[str], stats: dict[str, object], is_final: bool, flush_index: int | None=None) -> None`
- [EventSentimentPipeline._finalize_feature_aggregation](../../event_sentiment/pipeline.py) — ligne 419 : `def _finalize_feature_aggregation(self, *, impacted_trade_dates: list[date], remaining_impacted_trade_dates: list[date], resolved_symbols: list[str], stats: dict[str, object]) -> None`
- [EventSentimentPipeline.run](../../event_sentiment/pipeline.py) — ligne 435 : `def run(self, start_utc: datetime | None=None, end_utc: datetime | None=None, symbols: list[str] | None=None, *, skip_ingestion: bool=False, skip_features: bool=False) -> dict`
- [EventSentimentPipeline._ensure_contextual_scorer](../../event_sentiment/pipeline.py) — ligne 595 : `def _ensure_contextual_scorer(self) -> ContextualFinBERTScorer`
- [EventSentimentPipeline._count_pending_contextual_pairs](../../event_sentiment/pipeline.py) — ligne 609 : `def _count_pending_contextual_pairs(self, **kwargs: object) -> int | None`
- [EventSentimentPipeline._run_contextual_scoring](../../event_sentiment/pipeline.py) — ligne 615 : `def _run_contextual_scoring(self, pending_scope: dict[str, object], stats: dict[str, object]) -> tuple[dict[str, object], list[date]]`
- [EventSentimentPipeline._emit_ingestion_progress](../../event_sentiment/pipeline.py) — ligne 785 : `def _emit_ingestion_progress(self, stats: dict[str, object], payload: dict[str, object]) -> None`
- [EventSentimentPipeline._emit_progress](../../event_sentiment/pipeline.py) — ligne 799 : `def _emit_progress(self, stats: dict[str, object], *, current: int, total: int, label: str, phase: str, unit: str | None=None, item: str | None=None) -> None`

## `event_sentiment/relevance.py`

Source SHA-256 : `629141f4ace6d9cffaffeb03862b2b7fe69aa9f6d5c2c555b916d06fae088d4f`

- [RelevanceWeights](../../event_sentiment/relevance.py) — ligne 61 : `class RelevanceWeights`
- [RelevanceResult](../../event_sentiment/relevance.py) — ligne 87 : `class RelevanceResult`
- [_normalise_company_name](../../event_sentiment/relevance.py) — ligne 94 : `def _normalise_company_name(name: str | None) -> str | None`
- [_text_contains](../../event_sentiment/relevance.py) — ligne 106 : `def _text_contains(haystack: str, needle: str) -> bool`
- [_ticker_variants](../../event_sentiment/relevance.py) — ligne 125 : `def _ticker_variants(symbol: str) -> Iterable[str]`
- [score_article_symbol](../../event_sentiment/relevance.py) — ligne 132 : `def score_article_symbol(*, symbol: str, headline: str, summary: str | None=None, content: str | None=None, is_primary: bool=False, company_name: str | None=None, ticker_count: int=1, weights: RelevanceWeights | None=None) -> RelevanceResult`

## `event_sentiment/relevance_backfill.py`

Source SHA-256 : `2c2a89e327381302972123a8a4b9fc9a76d035079f8d574d56aaa676d1cf7909`

- [_emit_run_summary](../../event_sentiment/relevance_backfill.py) — ligne 52 : `def _emit_run_summary(summary: dict[str, Any]) -> None`
- [_build_run_id](../../event_sentiment/relevance_backfill.py) — ligne 59 : `def _build_run_id(prefix: str='relevance-backfill') -> str`
- [_parse_date](../../event_sentiment/relevance_backfill.py) — ligne 63 : `def _parse_date(value: str | None) -> date | None`
- [_parse_symbols](../../event_sentiment/relevance_backfill.py) — ligne 69 : `def _parse_symbols(value: str | None) -> list[str] | None`
- [RelevanceBackfillService](../../event_sentiment/relevance_backfill.py) — ligne 75 : `class RelevanceBackfillService`
- [RelevanceBackfillService.__init__](../../event_sentiment/relevance_backfill.py) — ligne 84 : `def __init__(self, repository: EventSentimentRepository, config: EventSentimentConfig, weights: RelevanceWeights | None=None) -> None`
- [RelevanceBackfillService.backfill_relevance](../../event_sentiment/relevance_backfill.py) — ligne 97 : `def backfill_relevance(self, *, batch_size: int=500, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None, dry_run: bool=False, rescore_all: bool=False) -> dict[str, int]`
- [RelevanceBackfillService.purge_below](../../event_sentiment/relevance_backfill.py) — ligne 151 : `def purge_below(self, *, threshold: float, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None, dry_run: bool=False) -> dict[str, int | float]`
- [RelevanceBackfillService.backfill_contextual](../../event_sentiment/relevance_backfill.py) — ligne 182 : `def backfill_contextual(self, *, batch_size: int=500, min_relevance: float=0.0, max_pairs: int | None=None, start_date: date | None=None, end_date: date | None=None, symbols: list[str] | None=None, ingestion_source: str | None=None, dry_run: bool=False) -> dict[str, int]`
- [build_arg_parser](../../event_sentiment/relevance_backfill.py) — ligne 250 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../event_sentiment/relevance_backfill.py) — ligne 336 : `def main() -> None`

## `event_sentiment/scoring.py`

Source SHA-256 : `94d08118b9e6282a467f47f0ea6f206f91e9855dd00da47965eecbb523dac656`

- [FinBERTSentimentService](../../event_sentiment/scoring.py) — ligne 17 : `class FinBERTSentimentService`
- [FinBERTSentimentService.__init__](../../event_sentiment/scoring.py) — ligne 18 : `def __init__(self, model_name: str='ProsusAI/finbert', model_version: str='finbert_v1', batch_size: int=16, max_length: int=256, model_revision: str | None=None) -> None`
- [FinBERTSentimentService.model_fingerprint](../../event_sentiment/scoring.py) — ligne 39 : `def model_fingerprint(self) -> str`
- [FinBERTSentimentService._get_torch_module](../../event_sentiment/scoring.py) — ligne 58 : `def _get_torch_module()`
- [FinBERTSentimentService._get_transformers_classes](../../event_sentiment/scoring.py) — ligne 64 : `def _get_transformers_classes()`
- [FinBERTSentimentService._is_cuda_runtime_error](../../event_sentiment/scoring.py) — ligne 70 : `def _is_cuda_runtime_error(exc: RuntimeError) -> bool`
- [FinBERTSentimentService._is_cuda_oom_error](../../event_sentiment/scoring.py) — ligne 75 : `def _is_cuda_oom_error(exc: RuntimeError) -> bool`
- [FinBERTSentimentService._next_smaller_gpu_batch_size](../../event_sentiment/scoring.py) — ligne 80 : `def _next_smaller_gpu_batch_size(cls, current_batch_size: int) -> int | None`
- [FinBERTSentimentService._resolve_hf_token](../../event_sentiment/scoring.py) — ligne 87 : `def _resolve_hf_token() -> str | None`
- [FinBERTSentimentService._export_hf_token_aliases](../../event_sentiment/scoring.py) — ligne 95 : `def _export_hf_token_aliases(token: str | None) -> None`
- [FinBERTSentimentService._clear_cuda_cache](../../event_sentiment/scoring.py) — ligne 101 : `def _clear_cuda_cache(self) -> None`
- [FinBERTSentimentService._load_model_for_device](../../event_sentiment/scoring.py) — ligne 109 : `def _load_model_for_device(self, device: str, force_reload: bool=False) -> None`
- [FinBERTSentimentService._ensure_model_loaded](../../event_sentiment/scoring.py) — ligne 137 : `def _ensure_model_loaded(self) -> None`
- [FinBERTSentimentService.adopt_runtime_from](../../event_sentiment/scoring.py) — ligne 145 : `def adopt_runtime_from(self, other: 'FinBERTSentimentService') -> None`
- [FinBERTSentimentService._infer_probabilities](../../event_sentiment/scoring.py) — ligne 161 : `def _infer_probabilities(self, batch_texts: list[str])`
- [FinBERTSentimentService._choose_text](../../event_sentiment/scoring.py) — ligne 205 : `def _choose_text(self, article: NormalizedNewsArticle) -> tuple[str, str]`
- [FinBERTSentimentService._infer_next_batch](../../event_sentiment/scoring.py) — ligne 217 : `def _infer_next_batch(self, texts: list[str], start: int)`
- [FinBERTSentimentService.score_articles](../../event_sentiment/scoring.py) — ligne 257 : `def score_articles(self, articles: Iterable[NormalizedNewsArticle]) -> list[SentimentRecord]`
- [_choose_contextual_text](../../event_sentiment/scoring.py) — ligne 327 : `def _choose_contextual_text(article: NormalizedNewsArticle, symbol: str, company_name: str | None) -> tuple[str, str]`
- [ContextualFinBERTScorer](../../event_sentiment/scoring.py) — ligne 358 : `class ContextualFinBERTScorer(FinBERTSentimentService)`
- [ContextualFinBERTScorer.score_pairs](../../event_sentiment/scoring.py) — ligne 367 : `def score_pairs(self, pairs: Iterable[tuple[NormalizedNewsArticle, str, str | None]]) -> list[ContextualSentimentRecord]`

## `event_sentiment/sentiment_pipeline.py`

Source SHA-256 : `99b20274d8ff8b8216d9526cca806a04029b7aec5ecc4a2faa1fd2b371ca925d`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `event_sentiment/signal_aggregator.py`

Source SHA-256 : `dba4f63ef944ec3ac1696a68884cab4f2046660e0c78840ffdade774fa937973`

- [_resolve_lock_dir](../../event_sentiment/signal_aggregator.py) — ligne 68 : `def _resolve_lock_dir() -> Path`
- [_lock_path](../../event_sentiment/signal_aggregator.py) — ligne 73 : `def _lock_path(trade_date: date, all_symbols: bool) -> Path`
- [_is_already_run](../../event_sentiment/signal_aggregator.py) — ligne 78 : `def _is_already_run(trade_date: date, all_symbols: bool) -> bool`
- [_mark_run_done](../../event_sentiment/signal_aggregator.py) — ligne 82 : `def _mark_run_done(trade_date: date, all_symbols: bool) -> None`
- [_utc_now_naive](../../event_sentiment/signal_aggregator.py) — ligne 97 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../event_sentiment/signal_aggregator.py) — ligne 101 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../event_sentiment/signal_aggregator.py) — ligne 105 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_is_missing_scalar](../../event_sentiment/signal_aggregator.py) — ligne 127 : `def _is_missing_scalar(value: object) -> bool`
- [_scalar_float](../../event_sentiment/signal_aggregator.py) — ligne 137 : `def _scalar_float(value: object, default: float=0.0) -> float`
- [_scalar_int](../../event_sentiment/signal_aggregator.py) — ligne 150 : `def _scalar_int(value: object, default: int=0) -> int`
- [_scalar_bool](../../event_sentiment/signal_aggregator.py) — ligne 156 : `def _scalar_bool(value: object, default: bool=False) -> bool`
- [_parse_timestamp](../../event_sentiment/signal_aggregator.py) — ligne 160 : `def _parse_timestamp(value: object) -> pd.Timestamp | None`
- [_age_days_from_reference](../../event_sentiment/signal_aggregator.py) — ligne 179 : `def _age_days_from_reference(value: object, *, reference_date: date) -> int`
- [_read_sql_query_dataframe](../../event_sentiment/signal_aggregator.py) — ligne 186 : `def _read_sql_query_dataframe(statement: object, connection: object, *, params: dict[str, Any]) -> pd.DataFrame`
- [_get_checkpoint_order_guard_status](../../event_sentiment/signal_aggregator.py) — ligne 190 : `def _get_checkpoint_order_guard_status(repository: object, *, source_name: str, symbols: list[str]) -> dict[str, object]`
- [_enforce_checkpoint_order_guard](../../event_sentiment/signal_aggregator.py) — ligne 232 : `def _enforce_checkpoint_order_guard(repository: object, *, source_name: str, symbols: list[str]) -> dict[str, object]`
- [_build_cli_run_summary](../../event_sentiment/signal_aggregator.py) — ligne 256 : `def _build_cli_run_summary(*, config: 'SentimentBoostConfig', trade_date: date, all_symbols: bool, loaded_symbols: int, updated_symbols: int, enriched: pd.DataFrame, started_at: datetime, finished_at: datetime, finbert_fingerprints: list[str] | None=None) -> dict[str, object]`
- [SentimentBoostConfig](../../event_sentiment/signal_aggregator.py) — ligne 311 : `class SentimentBoostConfig`
- [SentimentBoostConfig.__post_init__](../../event_sentiment/signal_aggregator.py) — ligne 345 : `def __post_init__(self) -> None`
- [SentimentBoostConfig._validate_horizon_weights](../../event_sentiment/signal_aggregator.py) — ligne 362 : `def _validate_horizon_weights(name: str, weights: tuple[tuple[int, float], ...]) -> None`
- [SentimentBoostConfig.from_global_config](../../event_sentiment/signal_aggregator.py) — ligne 374 : `def from_global_config(cls, config: dict | None=None, **overrides) -> 'SentimentBoostConfig'`
- [SentimentBoostConfig.to_fusion_weights](../../event_sentiment/signal_aggregator.py) — ligne 408 : `def to_fusion_weights(self) -> SentimentFusionWeights`
- [SentimentBoostConfig._normalized_horizon_weights](../../event_sentiment/signal_aggregator.py) — ligne 417 : `def _normalized_horizon_weights(weights: tuple[tuple[int, float], ...]) -> list[tuple[int, float]]`
- [SentimentSignalAggregator](../../event_sentiment/signal_aggregator.py) — ligne 423 : `class SentimentSignalAggregator`
- [SentimentSignalAggregator.__init__](../../event_sentiment/signal_aggregator.py) — ligne 432 : `def __init__(self, engine: Engine, config: SentimentBoostConfig | None=None) -> None`
- [SentimentSignalAggregator._emit_progress](../../event_sentiment/signal_aggregator.py) — ligne 437 : `def _emit_progress(self, summary: dict[str, object], *, current: int, total: int, label: str, phase: str, item: str | None=None, unit: str='étapes') -> None`
- [SentimentSignalAggregator._feature_fetch_window_days](../../event_sentiment/signal_aggregator.py) — ligne 462 : `def _feature_fetch_window_days(self, horizon_weights: tuple[tuple[int, float], ...]) -> int`
- [SentimentSignalAggregator._load_ticker_sentiment](../../event_sentiment/signal_aggregator.py) — ligne 470 : `def _load_ticker_sentiment(self, symbols: list[str], trade_date: date) -> pd.DataFrame`
- [SentimentSignalAggregator._load_sector_sentiment](../../event_sentiment/signal_aggregator.py) — ligne 535 : `def _load_sector_sentiment(self, sectors: list[str], trade_date: date) -> pd.DataFrame`
- [SentimentSignalAggregator._compute_time_decay_weight](../../event_sentiment/signal_aggregator.py) — ligne 584 : `def _compute_time_decay_weight(trade_dates: pd.Series, reference_date: date, half_life_days: float) -> pd.Series`
- [SentimentSignalAggregator._aggregate_ticker_window](../../event_sentiment/signal_aggregator.py) — ligne 608 : `def _aggregate_ticker_window(ticker_df: pd.DataFrame, min_news_count: int, reference_date: date, half_life_days: float) -> pd.DataFrame`
- [SentimentSignalAggregator._aggregate_sector_window](../../event_sentiment/signal_aggregator.py) — ligne 685 : `def _aggregate_sector_window(sector_df: pd.DataFrame, reference_date: date, half_life_days: float) -> pd.DataFrame`
- [SentimentSignalAggregator._normalize_to_01](../../event_sentiment/signal_aggregator.py) — ligne 740 : `def _normalize_to_01(series: pd.Series) -> pd.Series`
- [SentimentSignalAggregator._normalize_identifier](../../event_sentiment/signal_aggregator.py) — ligne 783 : `def _normalize_identifier(value: object) -> str | None`
- [SentimentSignalAggregator._normalize_signed_signal](../../event_sentiment/signal_aggregator.py) — ligne 790 : `def _normalize_signed_signal(series: pd.Series) -> pd.Series`
- [SentimentSignalAggregator._numeric_value](../../event_sentiment/signal_aggregator.py) — ligne 797 : `def _numeric_value(value: object, default: float=0.0) -> float`
- [SentimentSignalAggregator._compute_staleness_weight](../../event_sentiment/signal_aggregator.py) — ligne 801 : `def _compute_staleness_weight(cls, trade_date_value: object, *, reference_date: date, half_life_days: float) -> float`
- [SentimentSignalAggregator._latest_rows_by_key](../../event_sentiment/signal_aggregator.py) — ligne 818 : `def _latest_rows_by_key(df: pd.DataFrame, key_column: str) -> pd.DataFrame`
- [SentimentSignalAggregator._compose_horizon_signal](../../event_sentiment/signal_aggregator.py) — ligne 829 : `def _compose_horizon_signal(cls, row: dict[str, object], *, value_columns: dict[int, str], horizon_weights: tuple[tuple[int, float], ...], coverage_columns: dict[int, str] | None=None, coverage_cap: float=1.0) -> float`
- [SentimentSignalAggregator._aggregate_ticker_multi_horizon](../../event_sentiment/signal_aggregator.py) — ligne 857 : `def _aggregate_ticker_multi_horizon(self, ticker_df: pd.DataFrame, reference_date: date) -> pd.DataFrame`
- [SentimentSignalAggregator._aggregate_sector_multi_horizon](../../event_sentiment/signal_aggregator.py) — ligne 915 : `def _aggregate_sector_multi_horizon(self, sector_df: pd.DataFrame, reference_date: date) -> pd.DataFrame`
- [SentimentSignalAggregator.merge](../../event_sentiment/signal_aggregator.py) — ligne 964 : `def merge(self, scores_df: pd.DataFrame, trade_date: Optional[date]=None) -> pd.DataFrame`
- [SentimentSignalAggregator.save_to_db](../../event_sentiment/signal_aggregator.py) — ligne 1252 : `def save_to_db(self, enriched_df: pd.DataFrame) -> int`
- [_load_scores_from_db](../../event_sentiment/signal_aggregator.py) — ligne 1446 : `def _load_scores_from_db(engine: Engine, all_symbols: bool) -> pd.DataFrame`
- [_build_arg_parser](../../event_sentiment/signal_aggregator.py) — ligne 1469 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../event_sentiment/signal_aggregator.py) — ligne 1549 : `def main(argv: list[str] | None=None) -> int`

## `event_sentiment/trading_calendar.py`

Source SHA-256 : `9db1b92e1a46f8d2f80394a5ea7f94d038efaeb1eb51b55270d564cddec89d17`

- [TemporalAlignmentResult](../../event_sentiment/trading_calendar.py) — ligne 15 : `class TemporalAlignmentResult`
- [TradingCalendarAligner](../../event_sentiment/trading_calendar.py) — ligne 22 : `class TradingCalendarAligner`
- [TradingCalendarAligner.__init__](../../event_sentiment/trading_calendar.py) — ligne 23 : `def __init__(self, regular_session_maps_to_same_day: bool=False) -> None`
- [TradingCalendarAligner._load_calendar](../../event_sentiment/trading_calendar.py) — ligne 28 : `def _load_calendar()`
- [TradingCalendarAligner._is_trading_day](../../event_sentiment/trading_calendar.py) — ligne 39 : `def _is_trading_day(self, value: date) -> bool`
- [TradingCalendarAligner._next_trading_day](../../event_sentiment/trading_calendar.py) — ligne 44 : `def _next_trading_day(self, value: date) -> date`
- [TradingCalendarAligner.align](../../event_sentiment/trading_calendar.py) — ligne 63 : `def align(self, published_at_utc: datetime) -> TemporalAlignmentResult`
