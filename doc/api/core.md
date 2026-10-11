# Inventaire API — core

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `core/__init__.py`

Source SHA-256 : `bf3cb9241026eeab699af2a1c8d9596cc4b382712f0f57b8a9f21f9ea6f4cf19`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `core/_deprecation.py`

Source SHA-256 : `eb535d6249fbc38fa3cd794906d7d614a493f9d09b6239b08cc3b6e0dd8254bc`

- [deprecated_v1](../../core/_deprecation.py) — ligne 18 : `def deprecated_v1(*, reason: str, since: str, removal: str='2.0') -> Callable[[F], F]`

## `core/broker_models.py`

Source SHA-256 : `a4b6985e5982de7f9855fe17b820d69fd06549e0b8b30cd8d0a308e37c981925`

- [AccountSnapshot](../../core/broker_models.py) — ligne 24 : `class AccountSnapshot`
- [BrokerPosition](../../core/broker_models.py) — ligne 38 : `class BrokerPosition`
- [OrderRequest](../../core/broker_models.py) — ligne 51 : `class OrderRequest`
- [BrokerOrderSnapshot](../../core/broker_models.py) — ligne 66 : `class BrokerOrderSnapshot`

## `core/conviction.py`

Source SHA-256 : `73a7ebedd03a080820c2fdaa715dd33b3931d6f365df6b3dfd3bd2cf453ae111`

- [ConvictionWeights](../../core/conviction.py) — ligne 36 : `class ConvictionWeights`
- [ConvictionWeights.__post_init__](../../core/conviction.py) — ligne 47 : `def __post_init__(self) -> None`
- [compute_conviction](../../core/conviction.py) — ligne 60 : `def compute_conviction(score_used: float, predicted_proba: float | None, score_weight: float, prediction_weight: float) -> float`
- [compute_conviction_short](../../core/conviction.py) — ligne 77 : `def compute_conviction_short(score_used: float, predicted_proba_short: float | None, score_weight: float, prediction_weight: float) -> float`
- [fuse](../../core/conviction.py) — ligne 90 : `def fuse(*, quant_score: float, predicted_proba: float | None, weights: ConvictionWeights | None=None) -> float`
- [fuse_short](../../core/conviction.py) — ligne 101 : `def fuse_short(*, quant_score: float, predicted_proba_short: float | None, weights: ConvictionWeights | None=None) -> float`
- [SentimentFusionWeights](../../core/conviction.py) — ligne 123 : `class SentimentFusionWeights`
- [SentimentFusionWeights.__post_init__](../../core/conviction.py) — ligne 139 : `def __post_init__(self) -> None`
- [fuse_sentiment](../../core/conviction.py) — ligne 150 : `def fuse_sentiment(*, quant_score: 'Number', sentiment_signal_norm: 'Number', macro_signal_norm: 'Number', weights: SentimentFusionWeights | None=None, signal_active: 'Number'=True) -> 'np.ndarray | float'`

## `core/direction.py`

Source SHA-256 : `898d40c0a8b5262135819796ac42b3cbc2aaa3a765133b9237274278ff0df5d2`

- [is_short_side](../../core/direction.py) — ligne 39 : `def is_short_side(side: str) -> bool`
- [is_long_side](../../core/direction.py) — ligne 50 : `def is_long_side(side: str) -> bool`
- [is_valid_side](../../core/direction.py) — ligne 59 : `def is_valid_side(side: str) -> bool`
- [normalize_side](../../core/direction.py) — ligne 64 : `def normalize_side(side: str | None, default: str=BUY) -> str`
- [direction_sign](../../core/direction.py) — ligne 82 : `def direction_sign(side: str) -> int`
- [closing_side](../../core/direction.py) — ligne 93 : `def closing_side(entry_side: str) -> str`
- [compute_take_profit_price](../../core/direction.py) — ligne 108 : `def compute_take_profit_price(entry_side: str, entry_price: float, tp_pct: float=0.12) -> float`
- [compute_initial_stop_price](../../core/direction.py) — ligne 129 : `def compute_initial_stop_price(entry_side: str, entry_price: float, risk_per_share: float | None=None, stop_pct: float | None=None) -> float | None`
- [compute_trailing_stop_price](../../core/direction.py) — ligne 154 : `def compute_trailing_stop_price(entry_side: str, reference_price: float, trailing_pct: float=0.1) -> float`
- [compute_trailing_activation_price](../../core/direction.py) — ligne 175 : `def compute_trailing_activation_price(entry_side: str, entry_price: float, r_multiple: float=2.0, risk_per_share: float | None=None, activation_profit_pct: float | None=None) -> float | None`
- [compute_pullback_limit_price](../../core/direction.py) — ligne 198 : `def compute_pullback_limit_price(entry_side: str, signal_price: float, offset_pct: float=0.01) -> float`
- [compute_realized_pnl](../../core/direction.py) — ligne 223 : `def compute_realized_pnl(entry_side: str, qty: float, entry_price: float, exit_price: float, fees: float=0.0) -> float`
- [compute_unrealized_pnl](../../core/direction.py) — ligne 248 : `def compute_unrealized_pnl(entry_side: str, qty: float, current_price: float, entry_price: float) -> float`
- [compute_return_pct](../../core/direction.py) — ligne 267 : `def compute_return_pct(entry_side: str, entry_price: float, exit_price: float) -> float`
- [compute_gross_notional](../../core/direction.py) — ligne 293 : `def compute_gross_notional(qty: float, price: float) -> float`
- [compute_net_notional](../../core/direction.py) — ligne 304 : `def compute_net_notional(side: str, qty: float, price: float) -> float`
- [compute_gross_exposure_pct](../../core/direction.py) — ligne 320 : `def compute_gross_exposure_pct(long_notional: float, short_notional: float, equity: float) -> float`
- [compute_net_exposure_pct](../../core/direction.py) — ligne 331 : `def compute_net_exposure_pct(long_notional: float, short_notional: float, equity: float) -> float`
- [normalize_target_side](../../core/direction.py) — ligne 346 : `def normalize_target_side(target: object) -> str`

## `core/eligibility.py`

Source SHA-256 : `053c4deee5fed7f7eed0b1188507e548b35a84de0bc8274c96381e82920965ee`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `core/feature_flags.py`

Source SHA-256 : `8476682f1a80a18e3cc49fcd815831f5de21284fe617e84b66761f26fd68a7b4`

- [_coerce_bool](../../core/feature_flags.py) — ligne 30 : `def _coerce_bool(value: Optional[str]) -> bool`
- [FeatureFlags](../../core/feature_flags.py) — ligne 37 : `class FeatureFlags`
- [FeatureFlags.from_env](../../core/feature_flags.py) — ligne 44 : `def from_env(cls, env: Optional[dict]=None) -> 'FeatureFlags'`
- [FeatureFlags.export_env](../../core/feature_flags.py) — ligne 51 : `def export_env(self, env: Optional[dict]=None) -> None`
- [FeatureFlags.to_run_summary](../../core/feature_flags.py) — ligne 70 : `def to_run_summary(self) -> dict`
- [is_sentiment_disabled](../../core/feature_flags.py) — ligne 78 : `def is_sentiment_disabled() -> bool`
- [is_ml_disabled](../../core/feature_flags.py) — ligne 82 : `def is_ml_disabled() -> bool`

## `core/filter_profiles.py`

Source SHA-256 : `02204b3a8289ab589874040a90713b2204927c46fb3e11c4196238324996c553`

- [StrictFilterProfile](../../core/filter_profiles.py) — ligne 37 : `class StrictFilterProfile`
- [StrictFilterProfile.__post_init__](../../core/filter_profiles.py) — ligne 61 : `def __post_init__(self) -> None`
- [StrictFilterProfile.to_backtest_filter_dict](../../core/filter_profiles.py) — ligne 99 : `def to_backtest_filter_dict(self) -> dict[str, float]`
- [StrictFilterProfile.to_scanner_config_kwargs](../../core/filter_profiles.py) — ligne 120 : `def to_scanner_config_kwargs(self) -> dict[str, float]`
- [StrictFilterProfile.iex_extensions](../../core/filter_profiles.py) — ligne 141 : `def iex_extensions(self) -> dict[str, float | int | None]`
- [StrictFilterProfile.apply_to_frame](../../core/filter_profiles.py) — ligne 155 : `def apply_to_frame(self, frame: pd.DataFrame, *, close_col: str='latest_close', adv_col: str='avg_dollar_volume_20d', volatility_ratio_col: str='volatility_ratio', relative_strength_col: str='relative_strength_index', atr_pct_col: str='atr_pct_20', weekly_trend_col: str='weekly_trend_score', ma200_col: str='ma200', high_52w_col: str='high_52w', market_cap_col: str='market_cap', beta_col: str='beta_126', spread_col: str='spread_bps', earnings_blackout_col: str='earnings_blackout') -> pd.DataFrame`
- [with_adaptive_adv](../../core/filter_profiles.py) — ligne 244 : `def with_adaptive_adv(base: StrictFilterProfile, equity: float, max_position_weight: float=0.1, target_pct_of_adv: float=0.01) -> StrictFilterProfile`

## `core/interfaces.py`

Source SHA-256 : `c7543ab996c7fe9e147ad1f43bc49af4c8fd571f09796a9be7d967f56af92d04`

- [PriceRepository](../../core/interfaces.py) — ligne 38 : `class PriceRepository(Protocol)`
- [PriceRepository.load_prices](../../core/interfaces.py) — ligne 41 : `def load_prices(self, symbols: Sequence[str], start: Optional[date]=None, end: Optional[date]=None) -> pd.DataFrame`
- [PriceRepository.load_latest_close](../../core/interfaces.py) — ligne 54 : `def load_latest_close(self, symbols: Sequence[str]) -> pd.Series`
- [ScoreRepository](../../core/interfaces.py) — ligne 60 : `class ScoreRepository(Protocol)`
- [ScoreRepository.load_scores](../../core/interfaces.py) — ligne 63 : `def load_scores(self, symbols: Sequence[str]) -> pd.DataFrame`
- [ScoreRepository.upsert_scores](../../core/interfaces.py) — ligne 70 : `def upsert_scores(self, scores: pd.DataFrame) -> int`
- [FactorEngine](../../core/interfaces.py) — ligne 80 : `class FactorEngine(Protocol)`
- [FactorEngine.compute](../../core/interfaces.py) — ligne 83 : `def compute(self, prices: pd.DataFrame) -> pd.DataFrame`
- [ScoringEngine](../../core/interfaces.py) — ligne 92 : `class ScoringEngine(Protocol)`
- [ScoringEngine.score](../../core/interfaces.py) — ligne 95 : `def score(self, factors: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame`
- [SentimentProvider](../../core/interfaces.py) — ligne 101 : `class SentimentProvider(Protocol)`
- [SentimentProvider.get_sentiment_scores](../../core/interfaces.py) — ligne 104 : `def get_sentiment_scores(self, symbols: Sequence[str], as_of: Optional[date]=None) -> pd.DataFrame`
- [RiskChecker](../../core/interfaces.py) — ligne 121 : `class RiskChecker(Protocol)`
- [RiskChecker.check_position_size](../../core/interfaces.py) — ligne 124 : `def check_position_size(self, symbol: str, proposed_shares: float, price: float) -> float`
- [RiskChecker.is_circuit_breaker_active](../../core/interfaces.py) — ligne 131 : `def is_circuit_breaker_active(self) -> bool`
- [OrderManager](../../core/interfaces.py) — ligne 137 : `class OrderManager(Protocol)`
- [OrderManager.submit_market_order](../../core/interfaces.py) — ligne 140 : `def submit_market_order(self, symbol: str, qty: float, side: str) -> str`
- [OrderManager.cancel_order](../../core/interfaces.py) — ligne 144 : `def cancel_order(self, order_id: str) -> bool`
- [BrokerPort](../../core/interfaces.py) — ligne 150 : `class BrokerPort(Protocol)`
- [BrokerPort.submit_order](../../core/interfaces.py) — ligne 153 : `def submit_order(self, symbol: str, qty: float, side: str, type_: str='market', **kwargs) -> str`
- [BrokerPort.cancel_order](../../core/interfaces.py) — ligne 164 : `def cancel_order(self, order_id: str) -> bool`
- [BrokerPort.get_order_status](../../core/interfaces.py) — ligne 168 : `def get_order_status(self, order_id: str) -> str`
- [BrokerPort.get_positions](../../core/interfaces.py) — ligne 172 : `def get_positions(self) -> list`
- [BrokerClient](../../core/interfaces.py) — ligne 182 : `class BrokerClient(Protocol)`
- [BrokerClient.get_account](../../core/interfaces.py) — ligne 191 : `def get_account(self) -> 'AccountSnapshot'`
- [BrokerClient.submit_order](../../core/interfaces.py) — ligne 195 : `def submit_order(self, request: 'OrderRequest') -> 'BrokerOrderSnapshot'`
- [BrokerClient.get_positions](../../core/interfaces.py) — ligne 199 : `def get_positions(self) -> list['BrokerPosition']`
- [BrokerClient.cancel_order](../../core/interfaces.py) — ligne 203 : `def cancel_order(self, order_id: str) -> bool`
- [BrokerClient.get_orders](../../core/interfaces.py) — ligne 207 : `def get_orders(self, status: str='all', since: datetime | None=None) -> list['BrokerOrderSnapshot']`
- [BrokerClient.stream_trades](../../core/interfaces.py) — ligne 215 : `def stream_trades(self, callback) -> Any`
- [MarketDataPort](../../core/interfaces.py) — ligne 225 : `class MarketDataPort(Protocol)`
- [MarketDataPort.fetch_bars](../../core/interfaces.py) — ligne 228 : `def fetch_bars(self, symbol: Symbol | str, timeframe: str, start_date: Optional[str]=None, *, adjustment: Adjustment='split', feed: Feed='iex') -> list[dict[str, Any]]`
- [MarketDataPort.fetch_latest_quotes](../../core/interfaces.py) — ligne 240 : `def fetch_latest_quotes(self, symbols: Sequence[Symbol | str]) -> dict[str, dict[str, Any]]`
- [BarsRepository](../../core/interfaces.py) — ligne 248 : `class BarsRepository(Protocol)`
- [BarsRepository.upsert_bars](../../core/interfaces.py) — ligne 251 : `def upsert_bars(self, symbol: Symbol | str, bars: pd.DataFrame, *, data_adjustment: str='split', data_source: str='alpaca_iex') -> int`
- [BarsRepository.load_bars](../../core/interfaces.py) — ligne 262 : `def load_bars(self, symbol: Symbol | str, start: date | None=None, end: date | None=None) -> pd.DataFrame`
- [ScoresRepository](../../core/interfaces.py) — ligne 273 : `class ScoresRepository(Protocol)`
- [ScoresRepository.list_symbols](../../core/interfaces.py) — ligne 276 : `def list_symbols(self, *, limit: int | None=None) -> list[str]`
- [ScoresRepository.upsert_scores](../../core/interfaces.py) — ligne 280 : `def upsert_scores(self, scores: pd.DataFrame) -> int`
- [RiskRepository](../../core/interfaces.py) — ligne 286 : `class RiskRepository(Protocol)`
- [RiskRepository.load_latest_decisions](../../core/interfaces.py) — ligne 289 : `def load_latest_decisions(self, account_id: AccountId | str) -> pd.DataFrame`
- [RiskRepository.record_run](../../core/interfaces.py) — ligne 293 : `def record_run(self, run_payload: Mapping[str, Any]) -> str`
- [ExecutionRepository](../../core/interfaces.py) — ligne 299 : `class ExecutionRepository(Protocol)`
- [ExecutionRepository.record_run](../../core/interfaces.py) — ligne 302 : `def record_run(self, run_payload: Mapping[str, Any]) -> str`
- [ExecutionRepository.load_orders](../../core/interfaces.py) — ligne 306 : `def load_orders(self, account_id: AccountId | str, since: date | datetime) -> pd.DataFrame`
- [NewsProvider](../../core/interfaces.py) — ligne 314 : `class NewsProvider(Protocol)`
- [NewsProvider.iter_news_pages](../../core/interfaces.py) — ligne 317 : `def iter_news_pages(self, start_utc: datetime, end_utc: datetime, symbols: Sequence[str] | None=None, limit: int=50) -> Iterator[tuple[list[dict[str, Any]], str | None]]`
- [CorporateActionProvider](../../core/interfaces.py) — ligne 329 : `class CorporateActionProvider(Protocol)`
- [CorporateActionProvider.fetch_actions](../../core/interfaces.py) — ligne 332 : `def fetch_actions(self, symbol: Symbol | str, since: date) -> list[dict[str, Any]]`
- [ConvictionAggregator](../../core/interfaces.py) — ligne 340 : `class ConvictionAggregator(Protocol)`
- [ConvictionAggregator.fuse](../../core/interfaces.py) — ligne 343 : `def fuse(self, *, quant_score: float, predicted_proba: float | None) -> float`

## `core/metrics.py`

Source SHA-256 : `41f832d5cc783b6102a114d35314921c0ba2d0092240144f8191a9abd24c7922`

- [_NoopMetric](../../core/metrics.py) — ligne 44 : `class _NoopMetric`
- [_NoopMetric.labels](../../core/metrics.py) — ligne 45 : `def labels(self, *_args: Any, **_kwargs: Any) -> '_NoopMetric'`
- [_NoopMetric.inc](../../core/metrics.py) — ligne 48 : `def inc(self, *_args: Any, **_kwargs: Any) -> None`
- [_NoopMetric.dec](../../core/metrics.py) — ligne 51 : `def dec(self, *_args: Any, **_kwargs: Any) -> None`
- [_NoopMetric.set](../../core/metrics.py) — ligne 54 : `def set(self, *_args: Any, **_kwargs: Any) -> None`
- [_NoopMetric.observe](../../core/metrics.py) — ligne 57 : `def observe(self, *_args: Any, **_kwargs: Any) -> None`
- [Counter](../../core/metrics.py) — ligne 60 : `def Counter(*_args: Any, **_kwargs: Any) -> _NoopMetric`
- [Gauge](../../core/metrics.py) — ligne 63 : `def Gauge(*_args: Any, **_kwargs: Any) -> _NoopMetric`
- [Histogram](../../core/metrics.py) — ligne 66 : `def Histogram(*_args: Any, **_kwargs: Any) -> _NoopMetric`
- [start_http_server](../../core/metrics.py) — ligne 69 : `def start_http_server(*_args: Any, **_kwargs: Any) -> None`
- [is_available](../../core/metrics.py) — ligne 73 : `def is_available() -> bool`
- [start_metrics_server](../../core/metrics.py) — ligne 120 : `def start_metrics_server(port: int | None=None, *, addr: str='0.0.0.0') -> bool`
- [record_run_summary](../../core/metrics.py) — ligne 159 : `def record_run_summary(module: str, status: str='OK') -> None`

## `core/ml_selection_contract.py`

Source SHA-256 : `790f806b57f41a11bb27ba957836dff6f347acfe9edca1ed75765b3515ddd431`

- [SelectionCapacity](../../core/ml_selection_contract.py) — ligne 43 : `class SelectionCapacity`
- [SelectionCapacity.__post_init__](../../core/ml_selection_contract.py) — ligne 50 : `def __post_init__(self) -> None`
- [MLFirstSelectionContract](../../core/ml_selection_contract.py) — ligne 64 : `class MLFirstSelectionContract`
- [MLFirstSelectionContract.__post_init__](../../core/ml_selection_contract.py) — ligne 96 : `def __post_init__(self) -> None`

## `core/run_summary.py`

Source SHA-256 : `0771c3f9f1ff09dcd6cf23eb8f24b07bbac139cf5dba194bab8bc6414a307706`

- [attach_schema_version](../../core/run_summary.py) — ligne 39 : `def attach_schema_version(summary: Mapping[str, Any] | MutableMapping[str, Any] | None, *, version: int=RUN_SUMMARY_SCHEMA_VERSION) -> dict[str, Any]`
- [merge_iex_bias_counters](../../core/run_summary.py) — ligne 54 : `def merge_iex_bias_counters(summary: MutableMapping[str, Any], counters: Mapping[str, Any] | None) -> None`
- [attach_live_progress](../../core/run_summary.py) — ligne 70 : `def attach_live_progress(summary: Mapping[str, Any] | MutableMapping[str, Any] | None, *, current: int, total: int, label: str, phase: str | None=None, unit: str | None=None, item: str | None=None) -> dict[str, Any]`
- [aggregate_data_source_mix](../../core/run_summary.py) — ligne 108 : `def aggregate_data_source_mix(counts: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> dict[str, Any]`
- [build_data_source_mix_check](../../core/run_summary.py) — ligne 153 : `def build_data_source_mix_check(counts: Mapping[str, Any] | Iterable[tuple[str, Any]] | None, *, min_dominant_ratio: float=DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO) -> dict[str, Any]`

## `core/secrets.py`

Source SHA-256 : `aabb4975bdc308f1160d3006dc421ff1b5a86f873ac6d46d4889d443803b5f0f`

- [SecretFinding](../../core/secrets.py) — ligne 57 : `class SecretFinding`
- [SecretFinding.to_dict](../../core/secrets.py) — ligne 66 : `def to_dict(self) -> dict[str, object]`
- [SecretConfigurationError](../../core/secrets.py) — ligne 76 : `class SecretConfigurationError(RuntimeError)`
- [resolve_env_placeholders](../../core/secrets.py) — ligne 80 : `def resolve_env_placeholders(value: Any, *, strict: bool=True) -> Any`
- [_mask](../../core/secrets.py) — ligne 111 : `def _mask(value: str) -> str`
- [_is_whitelisted_line](../../core/secrets.py) — ligne 117 : `def _is_whitelisted_line(line: str) -> bool`
- [_strip_value_for_scan](../../core/secrets.py) — ligne 127 : `def _strip_value_for_scan(line: str) -> str`
- [scan_text_for_literal_secrets](../../core/secrets.py) — ligne 134 : `def scan_text_for_literal_secrets(text: str, *, source_path: str='<memory>') -> list[SecretFinding]`
- [scan_yaml_for_literal_secrets](../../core/secrets.py) — ligne 175 : `def scan_yaml_for_literal_secrets(path: Path) -> list[SecretFinding]`
- [scan_repo_yaml_for_literal_secrets](../../core/secrets.py) — ligne 183 : `def scan_repo_yaml_for_literal_secrets(root: Path, *, exclude_dirs: tuple[str, ...]=('.venv', 'venv', '.git', 'tests', '__pycache__', 'htmlcov', 'alpha_trade.egg-info')) -> list[SecretFinding]`
- [assert_no_plaintext_secrets](../../core/secrets.py) — ligne 205 : `def assert_no_plaintext_secrets(config: dict[str, Any], *, paths: Iterable[Iterable[str]]=(('database', 'password'), ('database', 'user'), ('alpaca', 'api_key'), ('alpaca', 'secret_key'))) -> None`
- [assert_required_env_vars](../../core/secrets.py) — ligne 255 : `def assert_required_env_vars(names: Iterable[str]) -> None`

## `core/ternary_decision_policy.py`

Source SHA-256 : `67d195598fc58ea6864fe08e2fb112888a7b13723cd2eeccab4e169bb3689846`

- [TernaryDecision](../../core/ternary_decision_policy.py) — ligne 41 : `class TernaryDecision`
- [TernaryDecision.__post_init__](../../core/ternary_decision_policy.py) — ligne 59 : `def __post_init__(self) -> None`
- [TernaryDecisionPolicy](../../core/ternary_decision_policy.py) — ligne 69 : `class TernaryDecisionPolicy`
- [TernaryDecisionPolicy.__post_init__](../../core/ternary_decision_policy.py) — ligne 90 : `def __post_init__(self) -> None`
- [TernaryDecisionPolicy.to_dict](../../core/ternary_decision_policy.py) — ligne 100 : `def to_dict(self) -> dict[str, object]`
- [TernaryDecisionPolicy.from_dict](../../core/ternary_decision_policy.py) — ligne 110 : `def from_dict(cls, data: dict[str, object]) -> 'TernaryDecisionPolicy'`
- [_validate_probabilities](../../core/ternary_decision_policy.py) — ligne 127 : `def _validate_probabilities(proba_short: float, proba_flat: float, proba_long: float, *, tolerance: float=1e-06) -> str | None`
- [decide_ternary_side](../../core/ternary_decision_policy.py) — ligne 147 : `def decide_ternary_side(proba_short: float, proba_flat: float, proba_long: float, policy: TernaryDecisionPolicy | None=None) -> TernaryDecision`
- [decide_from_array](../../core/ternary_decision_policy.py) — ligne 252 : `def decide_from_array(proba_array: 'np.ndarray', policy: TernaryDecisionPolicy | None=None) -> TernaryDecision`
- [decide_ternary_side_batch](../../core/ternary_decision_policy.py) — ligne 281 : `def decide_ternary_side_batch(proba_matrix: 'np.ndarray', policy: TernaryDecisionPolicy | None=None) -> 'np.ndarray'`
- [BaselineArtifact](../../core/ternary_decision_policy.py) — ligne 360 : `class BaselineArtifact`
- [produce_baseline_artifact](../../core/ternary_decision_policy.py) — ligne 378 : `def produce_baseline_artifact(*, period_start: str, period_end: str, universe: list[str], metrics_by_side: dict[str, dict[str, float]], seed: int=42, code_sha: str | None=None, config_fingerprint: str | None=None, data_fingerprint: str | None=None, policy: TernaryDecisionPolicy | None=None, artifact_id: str | None=None) -> BaselineArtifact`
- [save_baseline_artifact](../../core/ternary_decision_policy.py) — ligne 471 : `def save_baseline_artifact(artifact: BaselineArtifact, base_dir: str='artifacts/baselines') -> str`

## `core/types.py`

Source SHA-256 : `3ba72a7db09c3ebb1318f26599bd0fa92597665c1e8f4a991655da9102f50835`

Module sans déclaration publique/privée de classe ou fonction au niveau module.
