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

