# Inventaire API — core

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `core/_deprecation.py`

- ligne 18 — `def deprecated_v1(*, reason: str, since: str, removal: str = "2.0") -> Callable[[F], F]:`
## `core/broker_models.py`

- ligne 24 — `class AccountSnapshot:`
- ligne 38 — `class BrokerPosition:`
- ligne 51 — `class OrderRequest:`
- ligne 66 — `class BrokerOrderSnapshot:`
## `core/conviction.py`

- ligne 101 — `def fuse_short(`
- ligne 123 — `class SentimentFusionWeights:`
- ligne 150 — `def fuse_sentiment(`
- ligne 36 — `class ConvictionWeights:`
- ligne 60 — `def compute_conviction(`
- ligne 77 — `def compute_conviction_short(`
- ligne 90 — `def fuse(`
## `core/direction.py`

- ligne 108 — `def compute_take_profit_price(`
- ligne 129 — `def compute_initial_stop_price(`
- ligne 154 — `def compute_trailing_stop_price(`
- ligne 175 — `def compute_trailing_activation_price(`
- ligne 198 — `def compute_pullback_limit_price(`
- ligne 223 — `def compute_realized_pnl(`
- ligne 248 — `def compute_unrealized_pnl(`
- ligne 267 — `def compute_return_pct(`
- ligne 293 — `def compute_gross_notional(qty: float, price: float) -> float:`
- ligne 304 — `def compute_net_notional(side: str, qty: float, price: float) -> float:`
- ligne 320 — `def compute_gross_exposure_pct(`
- ligne 331 — `def compute_net_exposure_pct(`
- ligne 346 — `def normalize_target_side(target: object) -> str:`
- ligne 39 — `def is_short_side(side: str) -> bool:`
- ligne 50 — `def is_long_side(side: str) -> bool:`
- ligne 59 — `def is_valid_side(side: str) -> bool:`
- ligne 64 — `def normalize_side(side: str | None, default: str = BUY) -> str:`
- ligne 82 — `def direction_sign(side: str) -> int:`
- ligne 93 — `def closing_side(entry_side: str) -> str:`
## `core/feature_flags.py`

- ligne 30 — `def _coerce_bool(value: Optional[str]) -> bool:`
- ligne 37 — `class FeatureFlags:`
- ligne 78 — `def is_sentiment_disabled() -> bool:`
- ligne 82 — `def is_ml_disabled() -> bool:`
## `core/filter_profiles.py`

- ligne 244 — `def with_adaptive_adv(`
- ligne 37 — `class StrictFilterProfile:`
## `core/interfaces.py`

- ligne 101 — `class SentimentProvider(Protocol):`
- ligne 121 — `class RiskChecker(Protocol):`
- ligne 137 — `class OrderManager(Protocol):`
- ligne 150 — `class BrokerPort(Protocol):`
- ligne 182 — `class BrokerClient(Protocol):`
- ligne 225 — `class MarketDataPort(Protocol):`
- ligne 248 — `class BarsRepository(Protocol):`
- ligne 273 — `class ScoresRepository(Protocol):`
- ligne 286 — `class RiskRepository(Protocol):`
- ligne 299 — `class ExecutionRepository(Protocol):`
- ligne 314 — `class NewsProvider(Protocol):`
- ligne 329 — `class CorporateActionProvider(Protocol):`
- ligne 340 — `class ConvictionAggregator(Protocol):`
- ligne 38 — `class PriceRepository(Protocol):`
- ligne 60 — `class ScoreRepository(Protocol):`
- ligne 80 — `class FactorEngine(Protocol):`
- ligne 92 — `class ScoringEngine(Protocol):`
## `core/metrics.py`

- ligne 120 — `def start_metrics_server(port: int | None = None, *, addr: str = "0.0.0.0") -> bool:`
- ligne 159 — `def record_run_summary(module: str, status: str = "OK") -> None:`
- ligne 73 — `def is_available() -> bool:`
## `core/ml_selection_contract.py`

- ligne 43 — `class SelectionCapacity:`
- ligne 64 — `class MLFirstSelectionContract:`
## `core/run_summary.py`

- ligne 108 — `def aggregate_data_source_mix(`
- ligne 153 — `def build_data_source_mix_check(`
- ligne 39 — `def attach_schema_version(`
- ligne 54 — `def merge_iex_bias_counters(`
- ligne 70 — `def attach_live_progress(`
## `core/secrets.py`

- ligne 108 — `def _mask(value: str) -> str:`
- ligne 114 — `def _is_whitelisted_line(line: str) -> bool:`
- ligne 124 — `def _strip_value_for_scan(line: str) -> str:`
- ligne 131 — `def scan_text_for_literal_secrets(`
- ligne 172 — `def scan_yaml_for_literal_secrets(path: Path) -> list[SecretFinding]:`
- ligne 180 — `def scan_repo_yaml_for_literal_secrets(`
- ligne 202 — `def assert_no_plaintext_secrets(`
- ligne 252 — `def assert_required_env_vars(names: Iterable[str]) -> None:`
- ligne 54 — `class SecretFinding:`
- ligne 73 — `class SecretConfigurationError(RuntimeError):`
- ligne 77 — `def resolve_env_placeholders(value: Any, *, strict: bool = True) -> Any:`
## `core/ternary_decision_policy.py`

- ligne 127 — `def _validate_probabilities(`
- ligne 147 — `def decide_ternary_side(`
- ligne 252 — `def decide_from_array(`
- ligne 281 — `def decide_ternary_side_batch(`
- ligne 360 — `class BaselineArtifact:`
- ligne 378 — `def produce_baseline_artifact(`
- ligne 41 — `class TernaryDecision:`
- ligne 471 — `def save_baseline_artifact(`
- ligne 69 — `class TernaryDecisionPolicy:`

