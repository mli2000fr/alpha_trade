"""Tests unitaires de la couche centralisée Market-Aware (Axe A).

Couvre :

* C01 — package ``service.market`` exporte les symboles attendus
* C03–C08 — patterns calendaires (Tax Day / Sept Slump / Santa / January / OpEx / Month-End)
* C09–C10 — VIX / 10Y yield evaluation + fallback neutre quand provider absent
* C18 — sentiment circuit breaker (warning / critical / live vs backtest)
* C12–C14 — earnings shield + buyback blackout
* C15 — allowed_slots = floor(equity / enforce_min_notional)
* C19 — sentiment warning réduit ``effective_max_positions`` à 2
* C30 — parser YAML de ``market_regimes`` + ``risk_management.trailing_stop``
"""
from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from service.market import (
    MarketRegimeState,
    MarketRegimesConfig,
    MacroDataUnavailableError,
    build_snapshot,
    neutral_snapshot,
    parse_market_regimes,
    parse_trailing_stop,
    reset_cache,
)
from service.market.calendar_patterns import (
    is_month_end_window,
    is_third_friday,
)
from service.market.config import (
    BuybackBlackoutConfig,
    CalendarPatternConfig,
    EarningsShieldConfig,
    RegimeHysteresisConfig,
    SectorLimitsConfig,
    SentimentBreakerConfig,
    SentinelConfig,
    VixConfig,
    YieldsConfig,
)
from service.market.earnings_shield import compute_earnings_shield
from service.market.macro_signals import evaluate_vix, evaluate_yield_10y
from service.market.macro_signals import MacroDataProvider
from service.market.sentiment_regime import evaluate_sentiment_regime
from service.market.macro_providers import CompositeMacroProvider


# ---------------------------------------------------------------------------
# Calendar patterns (C03–C08)
# ---------------------------------------------------------------------------

def test_third_friday_detection():
    assert is_third_friday(date(2025, 4, 18)) is True   # 3e vendredi avril 2025
    assert is_third_friday(date(2025, 5, 16)) is True
    assert is_third_friday(date(2025, 5, 9)) is False
    assert is_third_friday(date(2025, 5, 17)) is False  # samedi


def test_month_end_window():
    # 30 mai 2025 = vendredi (dernier jour ouvré du mois)
    # business_days_from_end=2 -> reculer de 2 jours ouvrés depuis 30/05 -> 28/05
    # fenêtre inclusive [28, 30]
    assert is_month_end_window(date(2025, 5, 30), 2) is True
    assert is_month_end_window(date(2025, 5, 29), 2) is True
    assert is_month_end_window(date(2025, 5, 28), 2) is True
    assert is_month_end_window(date(2025, 5, 27), 2) is False


def _build_calendar_only_cfg(**patterns) -> MarketRegimesConfig:
    return MarketRegimesConfig(
        enabled=True,
        sentinel=SentinelConfig(enabled=True),
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
        sector_limits=SectorLimitsConfig(enabled=False),
        earnings_shield=EarningsShieldConfig(enabled=False),
        buyback_blackout=BuybackBlackoutConfig(enabled=False),
        patterns=patterns,
    )


def test_tax_day_pattern_active():
    cfg = _build_calendar_only_cfg(
        tax_day=CalendarPatternConfig(enabled=True, start="04-10", end="04-20", risk_mult=0.4),
    )
    reset_cache()
    snap = build_snapshot(date(2025, 4, 15), config=cfg, equity=None, earnings_lookup=lambda *_: {})
    assert "tax_day" in snap.active_patterns
    assert snap.risk_multiplier == pytest.approx(0.4)


def test_santa_rally_increases_risk_mult():
    cfg = _build_calendar_only_cfg(
        santa_rally=CalendarPatternConfig(enabled=True, start="12-20", end="12-31", risk_mult=1.15),
    )
    reset_cache()
    snap = build_snapshot(date(2025, 12, 24), config=cfg, equity=None, earnings_lookup=lambda *_: {})
    assert "santa_rally" in snap.active_patterns
    assert snap.risk_multiplier == pytest.approx(1.15)


def test_opex_block_entries_mode():
    cfg = _build_calendar_only_cfg(
        institutional_opex=CalendarPatternConfig(
            enabled=True, rule="3rd_friday", mode="block_entries",
        ),
    )
    reset_cache()
    snap = build_snapshot(date(2025, 4, 18), config=cfg, equity=None, earnings_lookup=lambda *_: {})
    assert "institutional_opex" in snap.active_patterns
    assert snap.allow_new_entries is False


# ---------------------------------------------------------------------------
# Macro signals (C09–C10)
# ---------------------------------------------------------------------------

class _StubMacroProvider:
    def __init__(self, vix=None, vix_short=None, history=None):
        self._vix = vix
        self._vix_short = vix_short
        self._history = history

    def get_vix_close(self, _):
        return self._vix

    def get_vix_short_term_close(self, _):
        return self._vix_short

    def get_us10y_history(self, _, lookback):
        return self._history


def test_vix_high_triggers_capital_preservation_via_macro():
    val, high, inverted, dq = evaluate_vix(
        cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=30.0))),
        date(2025, 5, 1),
        high_threshold=25.0,
    )
    assert val == 30.0
    assert high is True
    assert inverted is False
    assert dq == {"vix": "ok"}


def test_vix_no_provider_fallback_neutral():
    val, high, inverted, dq = evaluate_vix(None, date(2025, 5, 1), high_threshold=25.0)
    assert val is None and high is False and inverted is False
    assert dq == {"vix": "no_provider"}


def test_yield_spike_detected():
    rel, spike, dq = evaluate_yield_10y(
        cast(MacroDataProvider, cast(object, _StubMacroProvider(history=[4.0, 4.05, 4.1, 4.15, 4.2, 4.25]))),
        date(2025, 5, 1),
        lookback_days=5,
        relative_spike_threshold=0.05,
    )
    assert rel == pytest.approx((4.25 - 4.0) / 4.0)
    assert spike is True


def test_yield_no_provider_fallback():
    rel, spike, dq = evaluate_yield_10y(None, date(2025, 5, 1), lookback_days=5, relative_spike_threshold=0.05)
    assert rel is None and spike is False
    assert dq == {"yield_10y": "no_provider"}


def test_snapshot_marks_macro_missing_when_fallback_allowed() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        allow_neutral_fallback_on_missing_macro_data=True,
        vix=VixConfig(enabled=True),
        yields=YieldsConfig(enabled=False),
    )
    reset_cache()

    snap = build_snapshot(date(2025, 5, 1), config=cfg, equity=2_000.0, macro_provider=None, earnings_lookup=lambda *_: {})

    assert snap.data_quality["vix"] == "no_provider"
    assert snap.data_quality["macro"] == "missing"
    assert snap.macro["missing_data_quality"] == {"vix": "no_provider"}


def test_snapshot_serializes_effective_macro_source_summary() -> None:
    class _StooqOnlyVixProvider:
        source_name = "stooq"

        def get_vix_close(self, _):
            return 16.99

        def get_vix_short_term_close(self, _):
            return None

        def get_us10y_history(self, _, lookback):
            return None

    class _EodhdOnlyShortVixProvider:
        source_name = "eodhd"

        def get_vix_close(self, _):
            return None

        def get_vix_short_term_close(self, _):
            return 14.15

        def get_us10y_history(self, _, lookback):
            return None

    cfg = MarketRegimesConfig(
        enabled=True,
        vix=VixConfig(enabled=True),
        yields=YieldsConfig(enabled=False),
    )
    provider = CompositeMacroProvider([_StooqOnlyVixProvider(), _EodhdOnlyShortVixProvider()])
    reset_cache()

    snap = build_snapshot(date(2025, 5, 1), config=cfg, equity=2_000.0, macro_provider=provider, earnings_lookup=lambda *_: {})

    assert snap.macro["vix"] == pytest.approx(16.99)
    assert snap.macro["vix_short"] == pytest.approx(14.15)
    assert snap.macro["source_effective"] == "mixed"
    assert snap.macro["source_by_signal"] == {"vix": "stooq", "vix_short": "eodhd"}


def test_snapshot_exposes_latest_10y_value() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(enabled=True, lookback_days=5, relative_spike_threshold=0.05),
    )
    provider = _StubMacroProvider(history=[4.0, 4.05, 4.10, 4.15, 4.20])
    reset_cache()

    snap = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        macro_provider=cast(MacroDataProvider, cast(object, provider)),
        earnings_lookup=lambda *_: {},
    )

    assert snap.macro["yield_10y"] == pytest.approx(4.20)
    assert snap.macro["yield_10y_5d_pct"] == pytest.approx((4.20 - 4.0) / 4.0)


def test_snapshot_raises_when_macro_missing_and_fail_fast_enabled() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        allow_neutral_fallback_on_missing_macro_data=False,
        vix=VixConfig(enabled=True),
        yields=YieldsConfig(enabled=False),
    )
    reset_cache()

    with pytest.raises(MacroDataUnavailableError):
        build_snapshot(date(2025, 5, 1), config=cfg, equity=2_000.0, macro_provider=None, earnings_lookup=lambda *_: {})


# ---------------------------------------------------------------------------
# Sentiment circuit breaker (C18, C19)
# ---------------------------------------------------------------------------

def test_sentiment_warning_caps_max_positions():
    cfg = SentimentBreakerConfig(enabled=True, warning_threshold=-0.15, critical_threshold=-0.30, warning_max_positions=2)
    res = evaluate_sentiment_regime(cfg, score_provider=lambda _d: -0.20, execution_context="live")
    assert res.level == "warning"
    assert res.suggested_mode == "capital_preservation"
    assert res.suggested_max_positions == 2


def test_sentiment_critical_live_close_only():
    cfg = SentimentBreakerConfig(enabled=True, critical_threshold=-0.30,
                                 critical_mode_live="close_only", critical_mode_backtest="cash_only")
    res_live = evaluate_sentiment_regime(cfg, score_provider=lambda _d: -0.50, execution_context="live")
    res_bt = evaluate_sentiment_regime(cfg, score_provider=lambda _d: -0.50, execution_context="backtest")
    assert res_live.suggested_mode == "close_only"
    assert res_bt.suggested_mode == "cash_only"


# ---------------------------------------------------------------------------
# Earnings shield + buyback blackout (C12–C14)
# ---------------------------------------------------------------------------

def test_earnings_shield_strict_block():
    cfg = EarningsShieldConfig(enabled=True, days_before=2, days_after=2, mode="strict_block")
    blackout = BuybackBlackoutConfig(enabled=False)
    res = compute_earnings_shield(
        date(2025, 5, 1),
        shield_cfg=cfg, blackout_cfg=blackout,
        lookup=lambda d, lb, la: {"AAPL": date(2025, 5, 2), "MSFT": date(2025, 5, 10)},
    )
    assert res.shielded == {"AAPL": "strict_block"}
    assert res.buyback_blackout == {}


def test_earnings_shield_negative_score_mode():
    cfg = EarningsShieldConfig(enabled=True, days_before=2, days_after=2, mode="negative_score", negative_score_value=-1.0)
    blackout = BuybackBlackoutConfig(enabled=False)
    res = compute_earnings_shield(
        date(2025, 5, 1),
        shield_cfg=cfg, blackout_cfg=blackout,
        lookup=lambda d, lb, la: {"AAPL": date(2025, 5, 1)},
    )
    assert res.shielded == {"AAPL": "negative_score"}
    assert res.negative_score_value == -1.0


def test_buyback_blackout_applies_multiplier():
    shield = EarningsShieldConfig(enabled=False)
    blackout = BuybackBlackoutConfig(enabled=True, days_before_earnings=14, ml_score_multiplier=0.7)
    res = compute_earnings_shield(
        date(2025, 5, 1),
        shield_cfg=shield, blackout_cfg=blackout,
        lookup=lambda d, lb, la: {"AAPL": date(2025, 5, 10), "MSFT": date(2025, 5, 20)},
    )
    # AAPL J+9 -> dans la fenêtre 14j ; MSFT J+19 -> hors fenêtre
    assert res.buyback_blackout == {"AAPL": 0.7}


# ---------------------------------------------------------------------------
# Snapshot end-to-end : petit capital (C15) + cache TTL
# ---------------------------------------------------------------------------

def test_snapshot_disabled_returns_neutral():
    cfg = MarketRegimesConfig(enabled=False)
    snap = build_snapshot(date(2025, 5, 1), config=cfg)
    assert snap.mode == "normal"
    assert snap.allow_new_entries is True
    assert snap.reasons == ("regime_disabled_or_neutral_fallback",)


def test_snapshot_small_capital_allowed_slots():
    cfg = MarketRegimesConfig(enabled=True, enforce_min_notional=155.0)
    reset_cache()
    snap = build_snapshot(date(2025, 5, 1), config=cfg, equity=2000.0, earnings_lookup=lambda *_: {})
    # floor(2000 / 155) = 12
    assert snap.allowed_slots == 12
    assert snap.effective_max_positions == 12
    assert snap.allow_new_entries is True


def test_snapshot_equity_below_min_notional_blocks_entries():
    cfg = MarketRegimesConfig(enabled=True, enforce_min_notional=155.0)
    reset_cache()
    snap = build_snapshot(date(2025, 5, 1), config=cfg, equity=100.0, earnings_lookup=lambda *_: {})
    assert snap.allowed_slots == 0
    assert snap.allow_new_entries is False
    assert "equity_too_low_for_min_notional" in snap.reasons


def test_neutral_snapshot_helper():
    s = neutral_snapshot(date(2025, 5, 1))
    assert s.mode == "normal"
    assert s.risk_multiplier == 1.0


def test_snapshot_exposes_structured_why_mode_and_sentiment_payload():
    class _Provider:
        def __init__(self):
            self.last_reading = None

        def __call__(self, lookback_days: int):
            class _Reading:
                def to_dict(self_nonlocal):
                    return {
                        "source": "ticker_daily_sentiment_features",
                        "lookback_days": lookback_days,
                        "total_news_count": 42,
                        "covered_days": 6,
                        "data_quality": "ok",
                    }

            self.last_reading = _Reading()
            return -0.20

    cfg = MarketRegimesConfig(
        enabled=True,
        vix=VixConfig(enabled=True, high_threshold=25.0),
        sentiment_circuit_breaker=SentimentBreakerConfig(
            enabled=True,
            warning_threshold=-0.15,
            critical_threshold=-0.30,
            warning_max_positions=2,
        ),
    )
    reset_cache()
    snap = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2000.0,
        macro_provider=cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=30.0, vix_short=31.0))),
        sentiment_score_provider=_Provider(),
        earnings_lookup=lambda *_: {},
    )

    assert snap.mode == "capital_preservation"
    assert snap.sentiment["level"] == "warning"
    assert snap.sentiment["source"] == "ticker_daily_sentiment_features"
    assert snap.macro["vix_curve_inverted"] is True
    assert snap.mode_why["final_mode"] == "capital_preservation"
    assert snap.mode_why["triggered_count"] >= 1
    assert any(item["source"] == "vix_high" and item["triggered"] for item in snap.decision_trace)
    assert any(item["source"] == "sentiment_warning" and item["triggered"] for item in snap.decision_trace)


def test_snapshot_capital_preservation_applies_generic_max_gross_exposure() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        capital_preservation_max_gross_exposure=0.45,
        vix=VixConfig(enabled=True, high_threshold=25.0),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    reset_cache()

    snap = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        macro_provider=cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=30.0, vix_short=24.0))),
        earnings_lookup=lambda *_: {},
    )

    assert snap.mode == "capital_preservation"
    assert snap.max_gross_exposure == pytest.approx(0.45)
    assert "capital_preservation_max_gross_exposure" in snap.reasons
    assert any(
        item["source"] == "capital_preservation_gross_exposure" and item["triggered"]
        for item in snap.decision_trace
    )


def test_snapshot_rates_shock_stack_escalates_to_cash_only_in_backtest():
    cfg = MarketRegimesConfig(
        enabled=True,
        vix=VixConfig(enabled=True, high_threshold=25.0),
        yields=YieldsConfig(
            enabled=True,
            lookback_days=5,
            relative_spike_threshold=0.05,
            block_sectors=("Technology", "Real Estate", "Consumer Cyclical", "Financial Services"),
            risk_mult=0.45,
            soft_max_positions=2,
            soft_max_position_weight=0.20,
            soft_max_sector_weight=0.25,
            soft_max_gross_exposure=0.50,
            hard_relative_spike_threshold=0.08,
            hard_mode_backtest="cash_only",
            hard_requires_vix_high=True,
            hard_requires_sentiment_warning=True,
            hard_max_positions=1,
            hard_max_position_weight=0.15,
            hard_max_sector_weight=0.20,
            hard_max_gross_exposure=0.35,
        ),
        sentiment_circuit_breaker=SentimentBreakerConfig(
            enabled=True,
            warning_threshold=-0.15,
            critical_threshold=-0.30,
            warning_max_positions=2,
        ),
    )
    reset_cache()

    snap = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=cast(
            MacroDataProvider,
            cast(object, _StubMacroProvider(vix=30.0, vix_short=31.0, history=[4.0, 4.05, 4.1, 4.15, 4.2, 4.4])),
        ),
        sentiment_score_provider=lambda _lookback: -0.20,
        earnings_lookup=lambda *_: {},
    )

    assert snap.mode == "cash_only"
    assert snap.allow_new_entries is False
    assert snap.max_gross_exposure == pytest.approx(0.35)
    assert snap.max_position_weight == pytest.approx(0.15)
    assert snap.max_sector_weight == pytest.approx(0.20)
    assert snap.effective_max_positions == 1
    assert "Real Estate" in snap.blocked_sectors
    assert "yield_spike_10y_hard" in snap.reasons
    assert any(item["source"] == "yield_spike_10y_hard" and item["triggered"] for item in snap.decision_trace)


def test_hysteresis_requires_soft_confirmation_before_entering_defensive_mode() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        hysteresis=RegimeHysteresisConfig(enabled=True, enter_soft_signals_required=1, enter_confirm_days=2, min_hold_days_defensive=2),
        vix=VixConfig(enabled=True, high_threshold=25.0),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=30.0, vix_short=24.0)))
    reset_cache()

    day_1 = build_snapshot(date(2025, 5, 1), config=cfg, equity=2_000.0, macro_provider=provider, earnings_lookup=lambda *_: {})
    day_2 = build_snapshot(
        date(2025, 5, 2),
        config=cfg,
        equity=2_000.0,
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
        previous_state=day_1.next_state,
    )

    assert day_1.raw_mode == "capital_preservation"
    assert day_1.mode == "normal"
    assert day_1.transition_action == "stay_normal_pending_entry"
    assert day_1.soft_constraints_active is False
    assert day_2.mode == "capital_preservation"
    assert day_2.transition_action == "enter_defensive"
    assert day_2.next_state is not None
    assert day_2.next_state.current_mode == "capital_preservation"


def test_r9_1_gates_soft_constraints_until_defensive_entry_is_confirmed() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        hysteresis=RegimeHysteresisConfig(
            enabled=True,
            enter_soft_signals_required=1,
            enter_confirm_days=2,
            min_hold_days_defensive=2,
            gate_soft_constraints_on_confirmed_entry=True,
        ),
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(
            enabled=True,
            lookback_days=5,
            relative_spike_threshold=0.05,
            risk_mult=0.45,
            soft_max_positions=2,
            soft_max_position_weight=0.20,
            soft_max_sector_weight=0.25,
            soft_max_gross_exposure=0.50,
        ),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(history=[4.0, 4.05, 4.10, 4.15, 4.20, 4.25])))
    reset_cache()

    day_1 = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
    )
    day_2 = build_snapshot(
        date(2025, 5, 2),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
        previous_state=day_1.next_state,
    )

    assert day_1.raw_mode == "normal"
    assert day_1.mode == "normal"
    assert day_1.transition_action == "stay_normal_pending_entry"
    assert day_1.soft_signal_count == 1
    assert day_1.soft_constraints_active is False
    assert day_1.deferred_soft_sources == ("yield_spike_10y",)
    assert day_1.risk_multiplier == pytest.approx(1.0)
    assert day_1.effective_max_positions == 12
    assert day_1.max_position_weight is None
    assert day_1.max_sector_weight is None
    assert day_1.max_gross_exposure is None
    assert day_1.blocked_sectors == ()

    assert day_2.mode == "capital_preservation"
    assert day_2.transition_action == "enter_defensive"
    assert day_2.soft_constraints_active is True
    assert day_2.deferred_soft_sources == ()
    assert day_2.risk_multiplier == pytest.approx(0.45)
    assert day_2.effective_max_positions == 2
    assert day_2.max_position_weight == pytest.approx(0.20)
    assert day_2.max_sector_weight == pytest.approx(0.25)
    assert day_2.max_gross_exposure == pytest.approx(0.50)
    assert "Technology" in day_2.blocked_sectors


def test_r10_selective_gating_delays_caps_but_keeps_risk_and_sector_soft_constraints_immediate() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        hysteresis=RegimeHysteresisConfig(
            enabled=True,
            enter_soft_signals_required=1,
            enter_confirm_days=2,
            min_hold_days_defensive=2,
            gate_soft_position_limits_on_confirmed_entry=True,
            gate_soft_exposure_caps_on_confirmed_entry=True,
        ),
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(
            enabled=True,
            lookback_days=5,
            relative_spike_threshold=0.05,
            risk_mult=0.45,
            soft_max_positions=2,
            soft_max_position_weight=0.20,
            soft_max_sector_weight=0.25,
            soft_max_gross_exposure=0.50,
            block_sectors=("Technology", "Growth"),
            block_high_beta=True,
            high_beta_threshold=1.1,
        ),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(history=[4.0, 4.05, 4.10, 4.15, 4.20, 4.25])))
    reset_cache()

    day_1 = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
    )
    day_2 = build_snapshot(
        date(2025, 5, 2),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
        previous_state=day_1.next_state,
    )

    assert day_1.mode == "normal"
    assert day_1.transition_action == "stay_normal_pending_entry"
    assert day_1.soft_constraints_active is True
    assert day_1.active_soft_constraint_families == ("risk_multiplier", "sector_blocks")
    assert day_1.deferred_soft_constraint_families == ("position_limits", "exposure_caps")
    assert day_1.deferred_soft_sources == ("yield_spike_10y",)
    assert day_1.risk_multiplier == pytest.approx(0.45)
    assert "Technology" in day_1.blocked_sectors
    assert day_1.block_high_beta is True
    assert day_1.high_beta_threshold == pytest.approx(1.1)
    assert day_1.effective_max_positions == 12
    assert day_1.max_position_weight is None
    assert day_1.max_sector_weight is None
    assert day_1.max_gross_exposure is None

    assert day_2.mode == "capital_preservation"
    assert day_2.transition_action == "enter_defensive"
    assert day_2.active_soft_constraint_families == (
        "risk_multiplier",
        "sector_blocks",
        "position_limits",
        "exposure_caps",
    )
    assert day_2.deferred_soft_constraint_families == ()
    assert day_2.risk_multiplier == pytest.approx(0.45)
    assert day_2.effective_max_positions == 2
    assert day_2.max_position_weight == pytest.approx(0.20)
    assert day_2.max_sector_weight == pytest.approx(0.25)
    assert day_2.max_gross_exposure == pytest.approx(0.50)


def test_hysteresis_holds_then_exits_after_confirmed_calm_days() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        hysteresis=RegimeHysteresisConfig(
            enabled=True,
            enter_soft_signals_required=1,
            enter_confirm_days=1,
            exit_soft_signals_max=0,
            exit_confirm_days=2,
            min_hold_days_defensive=3,
            hard_exit_confirm_days=1,
        ),
        vix=VixConfig(enabled=True, high_threshold=25.0),
        yields=YieldsConfig(enabled=False),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    hot_provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=30.0, vix_short=24.0)))
    calm_provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(vix=18.0, vix_short=17.0)))
    reset_cache()

    day_1 = build_snapshot(date(2025, 5, 1), config=cfg, equity=2_000.0, macro_provider=hot_provider, earnings_lookup=lambda *_: {})
    day_2 = build_snapshot(date(2025, 5, 2), config=cfg, equity=2_000.0, macro_provider=calm_provider, earnings_lookup=lambda *_: {}, previous_state=day_1.next_state)
    day_3 = build_snapshot(date(2025, 5, 5), config=cfg, equity=2_000.0, macro_provider=calm_provider, earnings_lookup=lambda *_: {}, previous_state=day_2.next_state)
    day_4 = build_snapshot(date(2025, 5, 6), config=cfg, equity=2_000.0, macro_provider=calm_provider, earnings_lookup=lambda *_: {}, previous_state=day_3.next_state)

    assert day_1.mode == "capital_preservation"
    assert day_2.mode == "capital_preservation"
    assert day_2.transition_action == "hold_defensive_min_hold"
    assert day_3.mode == "capital_preservation"
    assert day_3.transition_action == "hold_defensive_pending_exit"
    assert day_4.mode == "normal"
    assert day_4.transition_action == "exit_defensive"


def test_hysteresis_hard_trigger_enters_immediately() -> None:
    cfg = MarketRegimesConfig(
        enabled=True,
        hysteresis=RegimeHysteresisConfig(enabled=True, enter_soft_signals_required=2, enter_confirm_days=3),
        vix=VixConfig(enabled=False),
        yields=YieldsConfig(
            enabled=True,
            lookback_days=5,
            relative_spike_threshold=0.05,
            hard_relative_spike_threshold=0.08,
            hard_mode_backtest="cash_only",
            hard_requires_vix_high=False,
            hard_requires_sentiment_warning=False,
        ),
        sentiment_circuit_breaker=SentimentBreakerConfig(enabled=False),
    )
    provider = cast(MacroDataProvider, cast(object, _StubMacroProvider(history=[4.0, 4.05, 4.1, 4.15, 4.2, 4.4])))
    reset_cache()

    snap = build_snapshot(
        date(2025, 5, 1),
        config=cfg,
        equity=2_000.0,
        execution_context="backtest",
        macro_provider=provider,
        earnings_lookup=lambda *_: {},
    )

    assert snap.raw_mode == "cash_only"
    assert snap.mode == "cash_only"
    assert snap.hard_triggered is True
    assert snap.transition_action == "hard_enter"


# ---------------------------------------------------------------------------
# YAML parser (C30)
# ---------------------------------------------------------------------------

def test_parse_market_regimes_minimal():
    cfg = parse_market_regimes(None)
    assert cfg.enabled is False
    assert cfg.enforce_min_notional == 155.0


def test_parse_market_regimes_full():
    raw = {
        "enabled": True,
        "enforce_min_notional": 200,
        "hysteresis": {
            "enabled": True,
            "enter_confirm_days": 4,
            "min_hold_days_defensive": 7,
            "gate_soft_constraints_on_confirmed_entry": True,
        },
        "vix": {"enabled": True, "high_threshold": 30.0},
        "patterns": {
            "tax_day": {"enabled": True, "start": "04-10", "end": "04-20", "risk_mult": 0.5},
        },
    }
    cfg = parse_market_regimes(raw)
    assert cfg.enabled is True
    assert cfg.enforce_min_notional == 200.0
    assert cfg.hysteresis.enabled is True
    assert cfg.hysteresis.enter_confirm_days == 4
    assert cfg.hysteresis.min_hold_days_defensive == 7
    assert cfg.hysteresis.gate_soft_constraints_on_confirmed_entry is True
    assert cfg.vix.enabled is True and cfg.vix.high_threshold == 30.0
    assert cfg.patterns["tax_day"].enabled is True
    assert cfg.patterns["tax_day"].risk_mult == 0.5


def test_parse_market_regimes_supports_selective_soft_gating_flags() -> None:
    raw = {
        "enabled": True,
        "hysteresis": {
            "enabled": True,
            "gate_soft_position_limits_on_confirmed_entry": True,
            "gate_soft_exposure_caps_on_confirmed_entry": True,
            "gate_soft_risk_multiplier_on_confirmed_entry": False,
            "gate_soft_sector_blocks_on_confirmed_entry": False,
        },
    }

    cfg = parse_market_regimes(raw)

    assert cfg.hysteresis.enabled is True
    assert cfg.hysteresis.gate_soft_constraints_on_confirmed_entry is False
    assert cfg.hysteresis.gate_soft_position_limits_on_confirmed_entry is True
    assert cfg.hysteresis.gate_soft_exposure_caps_on_confirmed_entry is True
    assert cfg.hysteresis.gate_soft_risk_multiplier_on_confirmed_entry is False
    assert cfg.hysteresis.gate_soft_sector_blocks_on_confirmed_entry is False


def test_market_regime_state_roundtrip() -> None:
    state = MarketRegimeState(
        trade_date=date(2025, 5, 1),
        current_mode="capital_preservation",
        previous_mode="normal",
        entered_at=date(2025, 5, 1),
        last_transition_at=date(2025, 5, 1),
        last_hard_trigger_at=date(2025, 5, 1),
        soft_entry_streak=2,
        soft_exit_streak=0,
        hard_calm_streak=1,
        days_in_current_mode=3,
    )

    restored = MarketRegimeState.from_dict(state.to_dict())

    assert restored == state


def test_parse_trailing_stop_defaults():
    ts = parse_trailing_stop(None)
    assert ts.enabled is False
    assert ts.mode == "fixed"
    assert ts.atr_period == 14
    assert ts.atr_multiplier == 2.5


