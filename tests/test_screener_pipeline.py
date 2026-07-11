from datetime import datetime, timezone

import numpy as np
import pandas as pd

from screener.models import ScreenerConfig
from screener import RESULT_COLUMNS, compute_scores_from_prices
from screener.pipeline import evaluate_objective_tradability


def _make_symbol_frame(symbol: str, base_price: float, drift: float, volume: float, rows: int = 2600) -> pd.DataFrame:
    dates = pd.bdate_range(end=datetime.now(timezone.utc), periods=rows)
    trend = np.linspace(0.0, drift, rows)
    close = base_price * (1.0 + trend)
    high = close * 1.01
    low = close * 0.99

    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": dates,
            "close_price": close,
            "high_price": high,
            "low_price": low,
            "volume": np.full(rows, volume),
        }
    )


def test_compute_scores_filters_illiquid_symbols_and_sorts_descending() -> None:
    config = ScreenerConfig(
        liquidity_threshold_usd=500_000.0,
        min_relative_strength_index=90.0,
        min_historical_range_score=0.0,
    )
    prices = pd.concat(
        [
            _make_symbol_frame("AAA", base_price=50.0, drift=0.30, volume=25_000),
            _make_symbol_frame("BBB", base_price=20.0, drift=0.02, volume=2_000),
            _make_symbol_frame("CCC", base_price=100.0, drift=-0.05, volume=12_000),
        ],
        ignore_index=True,
    )

    scores = compute_scores_from_prices(prices, spy_return_6m=0.06, config=config)

    assert list(scores.columns) == RESULT_COLUMNS
    assert "BBB" not in set(scores["symbol"])
    assert list(scores["total_score"]) == sorted(scores["total_score"], reverse=True)
    assert scores["total_score"].between(0.0, 100.0).all()
    assert scores.iloc[0]["symbol"] == "AAA"
    assert set(scores["is_candidate"]) == {0}
    assert scores["sector"].isna().all()
    assert scores["last_updated_score"].notna().all()
    assert scores["last_updated_scan"].notna().all()
    assert (scores["last_updated_score"] == scores["last_updated_scan"]).all()


def test_compute_scores_returns_empty_frame_when_benchmark_is_invalid() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0, min_historical_range_score=0.0)
    prices = _make_symbol_frame("AAA", base_price=50.0, drift=0.10, volume=1_000)

    scores = compute_scores_from_prices(prices, spy_return_6m=-1.0, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_returns_empty_frame_for_empty_input() -> None:
    scores = compute_scores_from_prices(pd.DataFrame(), spy_return_6m=0.05, config=ScreenerConfig())

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_excludes_symbols_with_insufficient_history() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0, min_history_days=252, min_historical_range_score=0.0)
    prices = _make_symbol_frame("NEW", base_price=30.0, drift=0.15, volume=20_000, rows=120)

    scores = compute_scores_from_prices(prices, spy_return_6m=0.03, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_excludes_symbols_below_min_close_price() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0, min_close_price=5.0, min_historical_range_score=0.0)
    prices = _make_symbol_frame("PENNY", base_price=2.0, drift=0.05, volume=100_000, rows=400)

    scores = compute_scores_from_prices(prices, spy_return_6m=0.03, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_excludes_symbols_below_min_relative_strength() -> None:
    config = ScreenerConfig(
        liquidity_threshold_usd=100.0,
        min_relative_strength_index=105.0,
        min_historical_range_score=0.0,
    )
    prices = _make_symbol_frame("LAG", base_price=50.0, drift=0.01, volume=50_000, rows=400)

    scores = compute_scores_from_prices(prices, spy_return_6m=0.05, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_objective_tradability_does_not_gate_on_relative_strength() -> None:
    config = ScreenerConfig(
        liquidity_threshold_usd=100.0,
        min_relative_strength_index=999.0,
    )
    prices = _make_symbol_frame("LAG", base_price=50.0, drift=0.01, volume=50_000, rows=400)

    members = evaluate_objective_tradability(prices, ["LAG", "MISSING"], config)

    assert members[0].is_tradable is True
    assert members[0].tradability_reason_code == "tradable"
    assert members[1].is_tradable is False
    assert members[1].tradability_reason_code == "bars_unavailable"


def test_objective_tradability_records_objective_rejection_reason() -> None:
    config = ScreenerConfig(
        liquidity_threshold_usd=10_000_000.0,
        min_relative_strength_index=1.0,
    )
    prices = _make_symbol_frame("ILLIQ", base_price=20.0, drift=0.50, volume=100, rows=400)

    member = evaluate_objective_tradability(prices, ["ILLIQ"], config)[0]

    assert member.is_tradable is False
    assert member.tradability_reason_code == "adv_below_minimum"
    assert member.adv_usd is not None


def test_compute_scores_uses_recent_range_window_not_full_history() -> None:
    recent_rows = 400
    old_rows = 400
    old_dates = pd.bdate_range(end=datetime.now(timezone.utc) - pd.Timedelta(days=800), periods=old_rows)
    recent_dates = pd.bdate_range(end=datetime.now(timezone.utc), periods=recent_rows)
    old_close = np.full(old_rows, 200.0)
    recent_close = np.linspace(90.0, 110.0, recent_rows)
    prices = pd.DataFrame(
        {
            "symbol": ["AAA"] * (old_rows + recent_rows),
            "timestamp": old_dates.tolist() + recent_dates.tolist(),
            "close_price": np.concatenate([old_close, recent_close]),
            "high_price": np.concatenate([old_close * 1.01, recent_close * 1.01]),
            "low_price": np.concatenate([old_close * 0.99, recent_close * 0.99]),
            "volume": np.full(old_rows + recent_rows, 200_000),
        }
    )
    config = ScreenerConfig(
        liquidity_threshold_usd=100.0,
        min_relative_strength_index=90.0,
        historical_range_lookback_days=252,
        min_historical_range_score=80.0,
        first_pass_window_days=800,
    )

    scores = compute_scores_from_prices(prices, spy_return_6m=0.01, config=config)

    assert not scores.empty
    assert scores.iloc[0]["historical_range_score"] >= 80.0


# --- Phase 3.2.c — alignement sur core/filter_profiles ---------------------

def test_screener_config_from_filter_profile_maps_shared_thresholds() -> None:
    from core.filter_profiles import STRICT_SWING_CASH_FILTERS
    from screener.models import ScreenerConfig

    config = ScreenerConfig.from_filter_profile(STRICT_SWING_CASH_FILTERS)

    assert config.min_close_price == STRICT_SWING_CASH_FILTERS.min_close
    assert config.liquidity_threshold_usd == STRICT_SWING_CASH_FILTERS.min_avg_dollar_volume_20d
    assert config.min_relative_strength_index == STRICT_SWING_CASH_FILTERS.min_relative_strength_index


def test_screener_config_strict_swing_cash_accepts_overrides() -> None:
    from screener.models import ScreenerConfig

    config = ScreenerConfig.strict_swing_cash(chunk_size=42, weight_liquidity=0.10)

    assert config.chunk_size == 42
    assert config.weight_liquidity == 0.10
    # Seuils communs alignés sur le profil partagé.
    assert config.min_close_price == 10.0
    assert config.liquidity_threshold_usd == 30_000_000.0


def test_screener_config_effective_first_pass_window_days_expands_short_calendar_window() -> None:
    config = ScreenerConfig(first_pass_window_days=252, min_history_days=252)

    assert config.first_pass_window_days == 252
    assert config.effective_first_pass_window_days == 400


def test_screener_config_effective_first_pass_window_days_preserves_larger_explicit_window() -> None:
    config = ScreenerConfig(first_pass_window_days=504, min_history_days=252, lookback_relative_days=183)

    assert config.effective_first_pass_window_days == 504

