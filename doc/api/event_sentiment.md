# Inventaire API — event_sentiment

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `event_sentiment/__init__.py`

- ligne 13 — `def __getattr__(name: str):`
## `event_sentiment/aggregation.py`

- ligne 14 — `def _coerce_trade_date(series: pd.Series) -> pd.Series:`
- ligne 142 — `def build_sector_daily_features(`
- ligne 18 — `def _rolling_sum(series: pd.Series, window: int) -> pd.Series:`
- ligne 22 — `def _rolling_max(series: pd.Series, window: int) -> pd.Series:`
- ligne 26 — `def build_ticker_daily_features(`
- ligne 9 — `def _safe_series_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:`
## `event_sentiment/cli.py`

- ligne 113 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 18 — `def _utc_now_naive() -> datetime:`
- ligne 22 — `def _build_run_id(prefix: str) -> str:`
- ligne 26 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 290 — `def main() -> None:`
- ligne 33 — `def _coerce_int(value: object) -> int:`
- ligne 41 — `def _build_cli_run_summary(`
## `event_sentiment/config.py`

- ligne 21 — `class EventSentimentConfig:`
## `event_sentiment/db_io.py`

- ligne 24 — `class EventSentimentRepository:`
## `event_sentiment/history_backfill.py`

- ligne 102 — `class EventSentimentHistoryBackfillService:`
- ligne 27 — `def _utc_now_naive() -> datetime:`
- ligne 31 — `def _resolve_heartbeat_interval_seconds() -> float:`
- ligne 353 — `def _build_run_id(prefix: str) -> str:`
- ligne 357 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 361 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 392 — `def main(argv: list[str] | None = None) -> int:`
- ligne 48 — `def _format_log_context(**context: object) -> str:`
- ligne 54 — `def _log_phase(phase_name: str, **context: object) -> Iterator[None]:`
- ligne 92 — `class EventSentimentHistoryBackfillResult:`
## `event_sentiment/importe_news.py`

- ligne 115 — `def resolve_symbols_from_inputs(`
- ligne 145 — `def resolve_symbols(`
- ligne 15 — `def _normalize_symbols(symbols: list[str]) -> list[str]:`
- ligne 158 — `def _apply_symbol_guardrails(`
- ligne 185 — `def _warn_ignored_scoring_flags(args: argparse.Namespace, logger: logging.Logger) -> None:`
- ligne 201 — `def _coerce_utc_datetime(value: object) -> datetime | None:`
- ligne 209 — `def _resolve_checkpoint_aware_import_scope(`
- ligne 261 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 27 — `def _load_distinct_symbols(query: str) -> list[str]:`
- ligne 34 — `def get_all_symbols_from_stock_bars_daily():`
- ligne 362 — `def main():`
- ligne 39 — `def get_all_symbols_from_stock_scores(*, selected_only: bool = False) -> list[str]:`
- ligne 52 — `def get_all_symbols_from_stock_scores_history() -> list[str]:`
- ligne 63 — `def get_all_symbols_from_stock_scores_all() -> list[str]:`
- ligne 78 — `def get_all_symbols_from_tradable_universe() -> list[str]:`
## `event_sentiment/ingestion.py`

- ligne 34 — `def _resolve_iter_news_pages(provider: str) -> Callable[..., Any]:`
- ligne 43 — `class NewsIngestionService:`
## `event_sentiment/macro_rules.py`

- ligne 16 — `class IntensityWeights(NamedTuple):`
- ligne 8 — `class MacroRule:`
- ligne 99 — `class MacroRuleEngine:`
## `event_sentiment/mapping.py`

- ligne 13 — `class EntitySectorMapper:`
## `event_sentiment/models.py`

- ligne 26 — `class SentimentRecord:`
- ligne 46 — `class ContextualSentimentRecord:`
- ligne 7 — `class NormalizedNewsArticle:`
- ligne 76 — `class MacroImpactRecord:`
## `event_sentiment/pipeline.py`

- ligne 17 — `def _coerce_int(value: object) -> int:`
- ligne 25 — `class EventSentimentPipeline:`
## `event_sentiment/relevance_backfill.py`

- ligne 250 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 337 — `def main() -> None:`
- ligne 52 — `def _emit_run_summary(summary: dict[str, Any]) -> None:`
- ligne 59 — `def _build_run_id(prefix: str = "relevance-backfill") -> str:`
- ligne 63 — `def _parse_date(value: str | None) -> date | None:`
- ligne 69 — `def _parse_symbols(value: str | None) -> list[str] | None:`
- ligne 75 — `class RelevanceBackfillService:`
## `event_sentiment/relevance.py`

- ligne 106 — `def _text_contains(haystack: str, needle: str) -> bool:`
- ligne 125 — `def _ticker_variants(symbol: str) -> Iterable[str]:`
- ligne 132 — `def score_article_symbol(`
- ligne 61 — `class RelevanceWeights:`
- ligne 87 — `class RelevanceResult:`
- ligne 94 — `def _normalise_company_name(name: str | None) -> str | None:`
## `event_sentiment/scoring.py`

- ligne 17 — `class FinBERTSentimentService:`
- ligne 327 — `def _choose_contextual_text(`
- ligne 358 — `class ContextualFinBERTScorer(FinBERTSentimentService):`
## `event_sentiment/signal_aggregator.py`

- ligne 101 — `def _build_run_id(prefix: str) -> str:`
- ligne 105 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 127 — `def _is_missing_scalar(value: object) -> bool:`
- ligne 137 — `def _scalar_float(value: object, default: float = 0.0) -> float:`
- ligne 1446 — `def _load_scores_from_db(engine: Engine, all_symbols: bool) -> pd.DataFrame:`
- ligne 1469 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 150 — `def _scalar_int(value: object, default: int = 0) -> int:`
- ligne 1549 — `def main(argv: list[str] | None = None) -> int:`
- ligne 156 — `def _scalar_bool(value: object, default: bool = False) -> bool:`
- ligne 160 — `def _parse_timestamp(value: object) -> pd.Timestamp | None:`
- ligne 179 — `def _age_days_from_reference(value: object, *, reference_date: date) -> int:`
- ligne 186 — `def _read_sql_query_dataframe(statement: object, connection: object, *, params: dict[str, Any]) -> pd.DataFrame:`
- ligne 190 — `def _get_checkpoint_order_guard_status(`
- ligne 232 — `def _enforce_checkpoint_order_guard(`
- ligne 256 — `def _build_cli_run_summary(`
- ligne 311 — `class SentimentBoostConfig:`
- ligne 423 — `class SentimentSignalAggregator:`
- ligne 68 — `def _resolve_lock_dir() -> Path:`
- ligne 73 — `def _lock_path(trade_date: date, all_symbols: bool) -> Path:`
- ligne 78 — `def _is_already_run(trade_date: date, all_symbols: bool) -> bool:`
- ligne 82 — `def _mark_run_done(trade_date: date, all_symbols: bool) -> None:`
- ligne 97 — `def _utc_now_naive() -> datetime:`
## `event_sentiment/trading_calendar.py`

- ligne 15 — `class TemporalAlignmentResult:`
- ligne 22 — `class TradingCalendarAligner:`

