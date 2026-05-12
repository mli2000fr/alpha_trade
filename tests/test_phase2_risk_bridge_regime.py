"""Tests d'intégration ``risk_bridge`` + ``MarketRegimeSnapshot`` (Axe D)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from backtesting.risk_bridge import build_phase2_risk_result
from risk_management.config import RiskConfig
from service.market.config import (
    BuybackBlackoutConfig,
    CalendarPatternConfig,
    EarningsShieldConfig,
    MarketRegimesConfig,
    SectorLimitsConfig,
    SentimentBreakerConfig,
    SentinelConfig,
    VixConfig,
    YieldsConfig,
)
from service.market import reset_cache


def _make_inputs(trade_date: date):
    scores_df = pd.DataFrame({
        "trade_date": [trade_date, trade_date],
        "symbol": ["AAPL", "MSFT"],
        "sector": ["Technology", "Technology"],
        "score": [1.5, 1.2],
        "score_source": ["test", "test"],
    })
    predictions_df = pd.DataFrame()
    idx = pd.DatetimeIndex([pd.Timestamp(trade_date) - pd.Timedelta(days=i) for i in range(30)][::-1])
    close_df = pd.DataFrame({"AAPL": [100.0] * 30, "MSFT": [200.0] * 30}, index=idx)
    high_df = close_df + 2
    low_df = close_df - 2
    return scores_df, predictions_df, close_df, high_df, low_df


def test_risk_bridge_without_regime_keeps_legacy_behavior():
    trade_date = date(2025, 5, 1)
    scores_df, predictions_df, close_df, high_df, low_df = _make_inputs(trade_date)
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    res = build_phase2_risk_result(
        scores_df=scores_df, predictions_df=predictions_df,
        close_df=close_df, high_df=high_df, low_df=low_df,
        risk_config=cfg,
    )
    assert res.diagnostics["regime_enabled"] is False
    assert res.diagnostics["entries_blocked_by_regime"] == 0


def test_risk_bridge_cash_only_blocks_entries():
    """Sentiment critical en backtest -> mode cash_only -> entries bloquées."""
    reset_cache()
    trade_date = date(2025, 5, 1)
    scores_df, predictions_df, close_df, high_df, low_df = _make_inputs(trade_date)
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    mr = MarketRegimesConfig(
        enabled=True,
        sentinel=SentinelConfig(enabled=True),
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(
            enabled=True, critical_threshold=-0.2, critical_mode_backtest="cash_only",
        ),
        sector_limits=SectorLimitsConfig(enabled=False),
        earnings_shield=EarningsShieldConfig(enabled=False),
        buyback_blackout=BuybackBlackoutConfig(enabled=False),
        patterns={},
    )
    res = build_phase2_risk_result(
        scores_df=scores_df, predictions_df=predictions_df,
        close_df=close_df, high_df=high_df, low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
        sentiment_score_provider=lambda _d: -0.5,
        earnings_lookup=lambda *_: {},
    )
    assert res.diagnostics["regime_enabled"] is True
    assert res.diagnostics["entries_blocked_by_regime"] == 2
    assert "cash_only" in res.diagnostics["regime_mode_distribution"]


def test_risk_bridge_tax_day_pattern_reduces_risk_multiplier():
    reset_cache()
    trade_date = date(2025, 4, 15)
    scores_df, predictions_df, close_df, high_df, low_df = _make_inputs(trade_date)
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    mr = MarketRegimesConfig(
        enabled=True,
        patterns={
            "tax_day": CalendarPatternConfig(enabled=True, start="04-10", end="04-20", risk_mult=0.4),
        },
    )
    res = build_phase2_risk_result(
        scores_df=scores_df, predictions_df=predictions_df,
        close_df=close_df, high_df=high_df, low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
        earnings_lookup=lambda *_: {},
    )
    assert res.diagnostics["regime_enabled"] is True
    snap_dump = res.regime_snapshots[trade_date]
    assert "tax_day" in snap_dump["active_patterns"]
    assert snap_dump["risk_multiplier"] == 0.4

