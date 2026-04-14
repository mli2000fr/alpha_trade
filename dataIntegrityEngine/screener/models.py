from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ScreenerConfig:
    timeframe: str = "1D"
    chunk_size: int = 500
    liquidity_threshold_usd: float = 500_000.0
    benchmark_symbol: str = "SPY"
    lookback_liquidity_bars: int = 30
    lookback_relative_days: int = 183
    lookback_history_years: int = 10
    weight_liquidity: float = 0.2
    weight_relative_strength: float = 0.4
    weight_historical_range: float = 0.4

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(payload: dict) -> "ScreenerConfig":
        return ScreenerConfig(**payload)

