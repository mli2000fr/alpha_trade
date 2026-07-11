"""Tests d'intégration ``risk_bridge`` + ``MarketRegimeSnapshot`` (Axe D)."""
from __future__ import annotations

import warnings
from datetime import date
from typing import cast

import pandas as pd

from backtesting.risk_bridge import RISK_SIGNAL_COLUMNS, _concat_signal_frames, build_phase2_risk_result
from risk_management.config import RiskConfig
from service.market import reset_cache
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


def _long_predictions(trade_date: date, symbols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": [trade_date] * len(symbols),
            "symbol": symbols,
            "predicted_class": [2] * len(symbols),
            "predicted_proba": [0.90] * len(symbols),
            "predicted_side": ["long"] * len(symbols),
            "proba_long": [0.90] * len(symbols),
            "proba_flat": [0.05] * len(symbols),
            "proba_short": [0.05] * len(symbols),
            "run_id": ["test-run"] * len(symbols),
        }
    )


def _make_inputs(trade_date: date):
    scores_df = pd.DataFrame({
        "trade_date": [trade_date, trade_date],
        "symbol": ["AAPL", "MSFT"],
        "sector": ["Technology", "Technology"],
        "final_score": [1.5, 1.2],
        "score": [1.5, 1.2],
        "score_source": ["test", "test"],
    })
    predictions_df = _long_predictions(trade_date, ["AAPL", "MSFT"])
    idx = pd.DatetimeIndex([pd.Timestamp(trade_date) - pd.Timedelta(days=i) for i in range(30)][::-1])
    close_df = pd.DataFrame({"AAPL": [100.0] * 30, "MSFT": [200.0] * 30}, index=idx)
    high_df = close_df + 2
    low_df = close_df - 2
    return scores_df, predictions_df, close_df, high_df, low_df


def test_concat_signal_frames_ignores_empty_frames_without_futurewarning() -> None:
    empty_frame = pd.DataFrame(columns=RISK_SIGNAL_COLUMNS)
    non_empty_frame = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2025-05-01"),
                "symbol": "AAPL",
                "selected": True,
                "rank": 1.0,
                "selection_rank": 1,
                "score": 1.5,
                "score_source": "test",
                "conviction_score": 1.5,
                "conviction_source": "test",
                "predicted_proba": None,
                "selector_signal_mode": None,
                "selection_explanation": None,
                "selector_earnings_blackout": None,
                "target_weight": 0.2,
                "target_notional": 20_000.0,
                "approved_shares": 200.0,
                "decision": "approved",
                "decision_reason": "ok",
                "decision_reason_code": None,
            }
        ],
        columns=RISK_SIGNAL_COLUMNS,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", FutureWarning)
        result = _concat_signal_frames([empty_frame, non_empty_frame, empty_frame.copy()])
    caught = caught or []

    assert tuple(result.columns) == RISK_SIGNAL_COLUMNS
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "AAPL"
    assert not any(
        warning.category is FutureWarning
        and "DataFrame concatenation with empty or all-NA entries" in str(warning.message)
        for warning in caught
    )


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


def test_risk_bridge_regime_off_keeps_structural_small_account_guard():
    trade_date = date(2025, 5, 1)
    symbols = [f"SYM{i:02d}" for i in range(12)]
    scores_df = pd.DataFrame({
        "trade_date": [trade_date] * len(symbols),
        "symbol": symbols,
        "sector": ["Technology"] * len(symbols),
        "final_score": [float(100 - i) for i in range(len(symbols))],
        "score": [float(100 - i) for i in range(len(symbols))],
        "score_source": ["test"] * len(symbols),
    })
    predictions_df = _long_predictions(trade_date, symbols)
    idx = pd.DatetimeIndex([pd.Timestamp(trade_date) - pd.Timedelta(days=i) for i in range(30)][::-1])
    close_df = pd.DataFrame({symbol: [100.0] * 30 for symbol in symbols}, index=idx)
    high_df = close_df + 2
    low_df = close_df - 2
    cfg = RiskConfig(account_equity=5_000, min_position_notional=100, max_positions=20, max_sector_weight=1.0)
    mr = MarketRegimesConfig(enabled=False, enforce_min_notional=500.0)

    res = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
    )

    assert res.diagnostics["regime_enabled"] is False
    accepted_symbols = {entry.symbol for entry in res.entries if entry.approved_shares > 0}
    assert len(accepted_symbols) == 10
    assert accepted_symbols == set(symbols[:10])


def test_risk_bridge_q2_ablation_structural_guard_prevents_zero_signal_collapse(caplog):
    trade_date = date(2020, 5, 1)
    symbols = ["AAPL", "MSFT", "NVDA"]
    scores_df = pd.DataFrame({
        "trade_date": [trade_date] * len(symbols),
        "symbol": symbols,
        "sector": ["Technology"] * len(symbols),
        "final_score": [3.0, 2.0, 1.0],
        "score": [3.0, 2.0, 1.0],
        "score_source": ["test"] * len(symbols),
    })
    predictions_df = _long_predictions(trade_date, symbols)
    idx = pd.DatetimeIndex([pd.Timestamp(trade_date) - pd.Timedelta(days=i) for i in range(30)][::-1])
    close_df = pd.DataFrame({symbol: [100.0] * 30 for symbol in symbols}, index=idx)
    high_df = close_df + 2
    low_df = close_df - 2
    cfg = RiskConfig(account_equity=2_000, min_position_notional=500, max_positions=3)

    legacy = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=cfg,
    )

    assert legacy.diagnostics["regime_enabled"] is False
    assert legacy.diagnostics["structural_guard_applied"] is False
    assert legacy.diagnostics["entries_accepted"] == 0
    assert legacy.diagnostics["signals_generated"] == 0
    assert {str(entry.decision_reason_code) for entry in legacy.entries} == {"rejected_notional"}

    mr = MarketRegimesConfig(enabled=False, enforce_min_notional=155.0)
    with caplog.at_level("INFO"):
        guarded = build_phase2_risk_result(
            scores_df=scores_df,
            predictions_df=predictions_df,
            close_df=close_df,
            high_df=high_df,
            low_df=low_df,
            risk_config=cfg,
            market_regimes_config=mr,
        )

    assert guarded.diagnostics["regime_enabled"] is False
    assert guarded.diagnostics["structural_guard_applied"] is True
    assert guarded.diagnostics["structural_guard_min_notional"] == 155.0
    assert guarded.diagnostics["structural_guard_effective_max_positions"] == 3
    assert guarded.diagnostics["entries_accepted"] == 3
    assert guarded.diagnostics["signals_generated"] == 3
    assert {entry.symbol for entry in guarded.entries if entry.approved_shares > 0} == set(symbols)
    assert any("structural_guard_applied:" in record.getMessage() for record in caplog.records)


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


def test_risk_bridge_capital_preservation_snapshot_exposes_generic_gross_exposure_cap():
    reset_cache()
    trade_date = date(2025, 5, 1)
    scores_df, predictions_df, close_df, high_df, low_df = _make_inputs(trade_date)
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    mr = MarketRegimesConfig(
        enabled=True,
        capital_preservation_max_gross_exposure=0.45,
        vix=VixConfig(enabled=True, high_threshold=25.0),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )

    class _MacroProvider:
        def get_vix_close(self, _):
            return 30.0

        def get_vix_short_term_close(self, _):
            return 24.0

        def get_us10y_history(self, _, lookback):
            return None

    res = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
        macro_provider=_MacroProvider(),
        earnings_lookup=lambda *_: {},
    )

    assert res.regime_snapshots[trade_date]["mode"] == "capital_preservation"
    assert res.regime_snapshots[trade_date]["max_gross_exposure"] == 0.45


def test_risk_bridge_collects_macro_missing_dates_when_fallback_allowed() -> None:
    reset_cache()
    trade_date = date(2025, 5, 1)
    scores_df, predictions_df, close_df, high_df, low_df = _make_inputs(trade_date)
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    mr = MarketRegimesConfig(
        enabled=True,
        allow_neutral_fallback_on_missing_macro_data=True,
        vix=VixConfig(enabled=True),
        yields=YieldsConfig(enabled=False),
    )

    res = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
        macro_provider=None,
        earnings_lookup=lambda *_: {},
    )

    assert res.diagnostics["macro_missing_dates_count"] == 1
    assert res.diagnostics["macro_missing_dates"] == [trade_date.isoformat()]
    macro_distribution = cast(dict[str, int], res.diagnostics["macro_data_quality_distribution"])
    assert macro_distribution["missing"] == 1
    assert res.regime_snapshots[trade_date]["data_quality"]["macro"] == "missing"


def test_risk_bridge_regime_snapshots_follow_backtest_market_calendar_when_scores_have_gaps() -> None:
    reset_cache()
    score_dates = [date(2025, 5, 1), date(2025, 5, 5)]
    market_dates = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-05-01"),
            pd.Timestamp("2025-05-02"),
            pd.Timestamp("2025-05-05"),
        ]
    )
    scores_df = pd.DataFrame(
        {
            "trade_date": [score_dates[0], score_dates[0], score_dates[1], score_dates[1]],
            "symbol": ["AAPL", "MSFT", "AAPL", "MSFT"],
            "sector": ["Technology", "Technology", "Technology", "Technology"],
            "final_score": [1.5, 1.2, 1.4, 1.1],
            "score": [1.5, 1.2, 1.4, 1.1],
            "score_source": ["test", "test", "test", "test"],
        }
    )
    predictions_df = pd.DataFrame()
    close_df = pd.DataFrame(
        {
            "AAPL": [100.0, 101.0, 102.0],
            "MSFT": [200.0, 201.0, 202.0],
        },
        index=market_dates,
    )
    high_df = close_df + 2
    low_df = close_df - 2
    cfg = RiskConfig(account_equity=100_000, min_position_notional=100, max_positions=5)
    mr = MarketRegimesConfig(
        enabled=True,
        allow_neutral_fallback_on_missing_macro_data=True,
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )

    res = build_phase2_risk_result(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        risk_config=cfg,
        market_regimes_config=mr,
        earnings_lookup=lambda *_: {},
    )

    assert sorted(res.regime_snapshots) == [date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 5)]
    assert res.diagnostics["snapshot_dates"] == 3
    assert set(res.regime_snapshots) - {score_dates[0], score_dates[1]} == {date(2025, 5, 2)}


