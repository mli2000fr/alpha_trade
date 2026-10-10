# Inventaire API — analyst_research

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `analyst_research/__init__.py`

Source SHA-256 : `f5b5a269fd66306d522c332aa9de6c134cc4f83f67d17ea30c497cf7e502a021`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `analyst_research/available_at.py`

Source SHA-256 : `83c6d342a780d646f12e600e9b00fad89d152797571d48106b269edbae35a521`

- [to_utc_naive](../../analyst_research/available_at.py) — ligne 29 : `def to_utc_naive(dt: datetime) -> datetime`
- [snapshot_date_of](../../analyst_research/available_at.py) — ligne 36 : `def snapshot_date_of(observed_at: datetime) -> date`
- [resolve_available_at](../../analyst_research/available_at.py) — ligne 45 : `def resolve_available_at(observed_at: datetime) -> datetime`
- [decision_cutoff](../../analyst_research/available_at.py) — ligne 67 : `def decision_cutoff(trading_day: date) -> datetime`

## `analyst_research/collector.py`

Source SHA-256 : `7d4a5222205c9358db20cd753479f944309fc415b4f6d528d20fc4065277edfe`

- [_utcnow](../../analyst_research/collector.py) — ligne 28 : `def _utcnow() -> datetime`
- [SymbolCollection](../../analyst_research/collector.py) — ligne 59 : `class SymbolCollection`
- [_classify_exception](../../analyst_research/collector.py) — ligne 71 : `def _classify_exception(e: BaseException) -> str`
- [_collect_family](../../analyst_research/collector.py) — ligne 82 : `def _collect_family(ticker: Any, attr: str, parser: Callable[..., list[dict]], ctx: dict[str, Any]) -> tuple[str, list[dict]]`
- [collect_symbol](../../analyst_research/collector.py) — ligne 104 : `def collect_symbol(symbol: str, *, observed_at: datetime, timeout_seconds: float) -> SymbolCollection`
- [_collect_with_timeout](../../analyst_research/collector.py) — ligne 169 : `def _collect_with_timeout(symbol: str, *, observed_at: datetime, timeout_seconds: float) -> SymbolCollection`
- [_collect_with_retries](../../analyst_research/collector.py) — ligne 179 : `def _collect_with_retries(symbol: str, *, observed_at: datetime, timeout_seconds: float, max_retries: int, base_backoff: float=1.0) -> SymbolCollection`
- [run_collection](../../analyst_research/collector.py) — ligne 198 : `def run_collection(universe: list[str], *, write_db: bool=False, dry_run: bool=False, sleep_seconds: float=0.25, timeout_seconds: float=20.0, max_retries: int=2, run_id: str | None=None, log_every: int=25) -> dict[str, Any]`

## `analyst_research/features.py`

Source SHA-256 : `1f3fbc96d51e8a507db319479c4c59f18b0c44f2964f454f3bedc6a42fb34bc8`

- [revision_pct](../../analyst_research/features.py) — ligne 40 : `def revision_pct(new: float | None, old: float | None, *, epsilon: float=PCT_EPSILON) -> float | None`
- [_rollover_dates](../../analyst_research/features.py) — ligne 49 : `def _rollover_dates(engine: Any, symbol: str, lo: datetime, hi: datetime) -> set[date]`
- [estimate_revision_series](../../analyst_research/features.py) — ligne 65 : `def estimate_revision_series(symbol: str, estimate_type: str, horizon_normalized: str, repo: AnalystSnapshotRepository | None=None, engine: Any=None) -> pd.DataFrame`
- [target_revision_series](../../analyst_research/features.py) — ligne 119 : `def target_revision_series(symbol: str, repo: AnalystSnapshotRepository | None=None) -> pd.DataFrame`
- [target_upside](../../analyst_research/features.py) — ligne 144 : `def target_upside(mean_target: float | None, pit_price: float | None) -> float | None`
- [xs_rank](../../analyst_research/features.py) — ligne 151 : `def xs_rank(df: pd.DataFrame, value_col: str, date_col: str='available_at') -> pd.Series`

## `analyst_research/monitor.py`

Source SHA-256 : `f6895fd381eb8c0ed5e0e5d95fb0b0aa4b948e91705cdb6c4bc44847dd4feb91`

- [_fmt](../../analyst_research/monitor.py) — ligne 19 : `def _fmt(v)`
- [cmd_status](../../analyst_research/monitor.py) — ligne 27 : `def cmd_status() -> int`
- [cmd_errors](../../analyst_research/monitor.py) — ligne 49 : `def cmd_errors() -> int`
- [cmd_history](../../analyst_research/monitor.py) — ligne 62 : `def cmd_history(symbol: str, horizon: str | None) -> int`
- [main](../../analyst_research/monitor.py) — ligne 99 : `def main(argv: list[str] | None=None) -> int`

## `analyst_research/parsers.py`

Source SHA-256 : `dda6e946d6ddf9838e65f99515f512117af685ab52ed7b474eb6833510aeadb6`

- [ProviderSchemaChangedError](../../analyst_research/parsers.py) — ligne 53 : `class ProviderSchemaChangedError(ValueError)`
- [ParseError](../../analyst_research/parsers.py) — ligne 57 : `class ParseError(ValueError)`
- [_num](../../analyst_research/parsers.py) — ligne 63 : `def _num(v: Any) -> float | None`
- [_int](../../analyst_research/parsers.py) — ligne 75 : `def _int(v: Any) -> int | None`
- [_jsonable](../../analyst_research/parsers.py) — ligne 80 : `def _jsonable(v: Any) -> Any`
- [compute_raw_hash](../../analyst_research/parsers.py) — ligne 104 : `def compute_raw_hash(payload: Any) -> str`
- [_period_series](../../analyst_research/parsers.py) — ligne 112 : `def _period_series(df: pd.DataFrame) -> pd.Series`
- [_norm_estimate_row](../../analyst_research/parsers.py) — ligne 121 : `def _norm_estimate_row(period: str, row: pd.Series, *, estimate_type: str, provider: str, symbol: str, snapshot_date: date, observed_at: datetime, available_at: datetime, payload: Any, schema_version: str) -> dict[str, Any]`
- [parse_estimate](../../analyst_research/parsers.py) — ligne 161 : `def parse_estimate(df: Any, *, estimate_type: str, symbol: str, provider: str=PROVIDER, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str=SCHEMA_VERSION) -> list[dict[str, Any]]`
- [_parse_eps_analysis_rows](../../analyst_research/parsers.py) — ligne 199 : `def _parse_eps_analysis_rows(df: Any, *, value_columns: Mapping[str, str], symbol: str, provider: str, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str) -> list[dict[str, Any]]`
- [parse_eps_trend](../../analyst_research/parsers.py) — ligne 247 : `def parse_eps_trend(df: Any, *, symbol: str, provider: str=PROVIDER, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str=SCHEMA_VERSION) -> list[dict[str, Any]]`
- [parse_eps_revisions](../../analyst_research/parsers.py) — ligne 273 : `def parse_eps_revisions(df: Any, *, symbol: str, provider: str=PROVIDER, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str=SCHEMA_VERSION) -> list[dict[str, Any]]`
- [parse_targets](../../analyst_research/parsers.py) — ligne 312 : `def parse_targets(d: Any, *, symbol: str, provider: str=PROVIDER, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str=SCHEMA_VERSION) -> list[dict[str, Any]]`
- [parse_recommendations](../../analyst_research/parsers.py) — ligne 351 : `def parse_recommendations(df: Any, *, symbol: str, provider: str=PROVIDER, snapshot_date: date, observed_at: datetime, available_at: datetime, schema_version: str=SCHEMA_VERSION) -> list[dict[str, Any]]`

## `analyst_research/universe.py`

Source SHA-256 : `9076554fe6a50162dad9521e656ac67caf29612e27d0554d73e1b20ee4710cd6`

- [UniverseResolution](../../analyst_research/universe.py) — ligne 30 : `class UniverseResolution`
- [_split_symbols](../../analyst_research/universe.py) — ligne 38 : `def _split_symbols(raw: str | Iterable[str]) -> list[str]`
- [read_symbols_file](../../analyst_research/universe.py) — ligne 50 : `def read_symbols_file(path: str | Path) -> list[str]`
- [resolve_universe](../../analyst_research/universe.py) — ligne 57 : `def resolve_universe(name: str | None=None, symbols_override: str | None=None, *, symbols_file: str | None=None) -> UniverseResolution`
