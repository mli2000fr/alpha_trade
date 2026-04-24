from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScreenerConfig:
    chunk_size: int = 500
    liquidity_threshold_usd: float = 500_000.0
    benchmark_symbol: str = "SPY"
    min_history_days: int = 252
    min_close_price: float = 5.0
    lookback_liquidity_bars: int = 30
    lookback_relative_days: int = 183
    lookback_history_years: int = 10
    weight_liquidity: float = 0.2
    weight_relative_strength: float = 0.4
    weight_historical_range: float = 0.4
    enable_two_pass_loading: bool = True
    first_pass_window_days: int = 400

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.liquidity_threshold_usd < 0:
            raise ValueError("liquidity_threshold_usd doit être positif.")
        if self.min_history_days < 2:
            raise ValueError("min_history_days doit être supérieur ou égal à 2.")
        if self.min_close_price <= 0:
            raise ValueError("min_close_price doit être strictement positif.")
        if self.lookback_liquidity_bars < 1:
            raise ValueError("lookback_liquidity_bars doit être supérieur ou égal à 1.")
        if self.lookback_relative_days < 1:
            raise ValueError("lookback_relative_days doit être supérieur ou égal à 1.")
        if self.lookback_history_years < 1:
            raise ValueError("lookback_history_years doit être supérieur ou égal à 1.")
        if self.first_pass_window_days < self.lookback_relative_days:
            raise ValueError("first_pass_window_days doit couvrir au minimum lookback_relative_days.")

        weights = (
            self.weight_liquidity,
            self.weight_relative_strength,
            self.weight_historical_range,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Les poids du screener doivent être positifs.")
        if sum(weights) <= 0:
            raise ValueError("La somme des poids du screener doit être strictement positive.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "ScreenerConfig":
        normalized_payload = dict(payload)
        normalized_payload.pop("timeframe", None)
        return ScreenerConfig(**normalized_payload)


@dataclass(frozen=True, slots=True)
class ScreenerChunkMetrics:
    input_symbols: int = 0
    recent_rows_loaded: int = 0
    range_rows_loaded: int = 0
    symbols_pass_history: int = 0
    symbols_pass_liquidity: int = 0
    symbols_pass_relative_strength: int = 0
    symbols_final: int = 0
    rows_avoided_estimate: int = 0
    pass1_seconds: float = 0.0
    pass2_seconds: float = 0.0
    duration_seconds: float = 0.0
    failed: bool = False
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ScreenerRunReport:
    run_id: str
    benchmark_symbol: str
    chunk_size: int
    workers: int
    as_of_date: str | None
    started_at: str
    finished_at: str | None = None
    duration_seconds: float = 0.0
    targeted_symbols: int = 0
    chunks_total: int = 0
    chunks_completed: int = 0
    chunk_failures: int = 0
    recent_rows_loaded: int = 0
    range_rows_loaded: int = 0
    symbols_pass_history: int = 0
    symbols_pass_liquidity: int = 0
    symbols_pass_relative_strength: int = 0
    symbols_final: int = 0
    rows_avoided_estimate: int = 0
    benchmark_load_seconds: float = 0.0
    pass1_seconds: float = 0.0
    pass2_seconds: float = 0.0
    upsert_seconds: float = 0.0

    def to_summary_dict(self) -> dict[str, object]:
        return asdict(self)
