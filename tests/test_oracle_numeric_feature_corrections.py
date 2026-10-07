"""Numerical contracts shared by Oracle and the other compute_features callers."""
import numpy as np
import pandas as pd
import pytest

from modelFactory.factor_features import compute_factor_features, FACTOR_FEATURE_COLUMNS
from modelFactory import features


def factor_inputs(n=320):
    rng = np.random.default_rng(783)
    dates = pd.bdate_range('2020-01-01', periods=n)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, .01, n))))
    returns = close.pct_change(fill_method=None)
    benchmark = pd.DataFrame(dict(date=dates, close=close, adj_close=close, daily_return=np.nan))
    stock = pd.DataFrame(dict(date=dates, daily_return=returns))
    return stock, benchmark


def test_null_persisted_benchmark_returns_derived_from_prices():
    stock, benchmark = factor_inputs()
    result = compute_factor_features(stock, benchmark)
    assert result.beta_252.iloc[-1] == pytest.approx(1)
    assert result.alpha_252.iloc[-1] == pytest.approx(0, abs=1e-10)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)
    assert result.momentum_252_vs_market.iloc[-1] == pytest.approx(0)
    assert benchmark.daily_return.isna().all()


def test_prices_take_priority_over_stale_zero_stored_returns():
    stock, benchmark = factor_inputs()
    benchmark.daily_return = 0.
    result = compute_factor_features(stock, benchmark)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)


def test_adjusted_benchmark_prices_absorb_split():
    stock, benchmark = factor_inputs()
    benchmark.loc[:159, 'close'] *= 2
    result = compute_factor_features(stock, benchmark)
    assert result.beta_252.iloc[-1] == pytest.approx(1)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)


def test_known_beta_alpha_and_index_alignment():
    stock, benchmark = factor_inputs()
    stock.daily_return = stock.daily_return * 1.7 + .0002
    stock.index = np.arange(1000, 1320)
    result = compute_factor_features(stock, benchmark)
    assert result.index.equals(stock.index)
    assert result.beta_252.iloc[-1] == pytest.approx(1.7)
    assert result.alpha_252.iloc[-1] == pytest.approx(.0002 * 252)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)
    expected = (stock.daily_return.tail(252).sum() - benchmark.adj_close.pct_change(fill_method=None).tail(252).sum())
    assert result.momentum_252_vs_market.iloc[-1] == pytest.approx(expected)


def test_missing_benchmark_date_not_forward_filled_or_zero_filled():
    stock, benchmark = factor_inputs()
    # Returns-only client: a missing benchmark date must exclude BOTH sides.
    benchmark['daily_return'] = stock.daily_return
    benchmark = benchmark[['date', 'daily_return']].drop(index=300)
    stock.daily_return *= 2
    stock.loc[300, 'daily_return'] = 10.
    result = compute_factor_features(stock, benchmark)
    assert result.beta_252.iloc[-1] == pytest.approx(2)
    assert result.alpha_252.iloc[-1] == pytest.approx(0, abs=1e-10)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)


def test_insufficient_valid_pairs_keep_defaults():
    stock, benchmark = factor_inputs()
    benchmark = benchmark.iloc[-100:]
    result = compute_factor_features(stock, benchmark)
    assert result.beta_252.eq(1).all()
    assert result.r_squared_252.eq(0).all()
    assert result.momentum_252_vs_market.eq(0).all()


def test_missing_price_date_does_not_create_multisession_daily_return():
    stock, benchmark = factor_inputs()
    stock.daily_return *= 2
    # Both this missing date and the following price difference are unobservable
    # daily pairs; the other exact pairs still recover beta=2.
    benchmark = benchmark.drop(index=300)
    result = compute_factor_features(stock, benchmark)
    assert result.beta_252.iloc[-1] == pytest.approx(2)
    assert result.alpha_252.iloc[-1] == pytest.approx(0, abs=1e-10)
    assert result.r_squared_252.iloc[-1] == pytest.approx(1)


def test_future_benchmark_prices_do_not_change_past_factors():
    stock, benchmark = factor_inputs()
    first = compute_factor_features(stock.iloc[:260], benchmark)
    altered = benchmark.copy()
    altered.loc[260:, ['close', 'adj_close']] *= 10
    second = compute_factor_features(stock.iloc[:260], altered)
    pd.testing.assert_frame_equal(first[FACTOR_FEATURE_COLUMNS], second[FACTOR_FEATURE_COLUMNS])


def test_duplicate_benchmark_dates_rejected():
    stock, benchmark = factor_inputs()
    benchmark = pd.concat([benchmark, benchmark.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match='unique'):
        compute_factor_features(stock, benchmark)


@pytest.mark.parametrize('denominator', [0., 1e-12, 1e-8, -1., np.nan, np.inf])
def test_degenerate_ratio_neutral_instead_of_dividing_by_epsilon(denominator):
    result = features._positive_denominator_ratio(pd.Series([100.]), pd.Series([denominator]))
    assert result.iloc[0] == 0


def test_ordinary_ratios_preserved_without_output_cap():
    result = features._positive_denominator_ratio(pd.Series([50., -.1, 100.]), pd.Series([.02, .01, 1e-6]))
    assert result.tolist() == pytest.approx([2500, -10, 1e8])


def test_numeric_version_changes_only_affected_feature_fingerprints(monkeypatch):
    expert = features.fingerprint(feature_set='expert')
    factor = features.fingerprint(feature_set='v1', include_factors=True)
    baseline = features.fingerprint(feature_set='v1')
    monkeypatch.setattr(features, 'NUMERICAL_FEATURE_CONTRACT_VERSION', 'different-version')
    assert features.fingerprint(feature_set='expert') != expert
    assert features.fingerprint(feature_set='v1', include_factors=True) != factor
    assert features.fingerprint(feature_set='v1') == baseline


def test_expert_pipeline_neutralizes_zero_range_and_near_zero_volatility():
    n = 360
    close = 100 * 1.001 ** np.arange(n)
    bars = pd.DataFrame(dict(symbol=['X'] * n, date=pd.bdate_range('2020-01-01', periods=n),
        open=close, high=close * 1.01, low=close * .99, close=close, adj_close=close,
        volume=np.full(n, 100000.), vwap=close, daily_return=np.nan, is_filled=0))
    bars.loc[n-1, ['high', 'low']] = close[-1]
    result = features.compute_features(bars, feature_set='expert')
    assert len(result) > 0
    assert result.log_return.iloc[-1] > 0
    assert result.intraday_range.iloc[-1] == 0
    assert result.log_return_div_intraday_range.iloc[-1] == 0
    assert result.rsi_14.iloc[-1] > 90
    assert result.rolling_volatility_20.iloc[-1] < 1e-8
    assert result.rsi_14_div_volatility_20.iloc[-1] == 0
    assert np.isfinite(result[features.INTERACTION_FEATURES].to_numpy()).all()
