"""Tests unitaires — PortfolioBuilder."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_management.config import RiskConfig
from risk_management.models import (
    DirectionalWinRateInfo,
    PredictionInfo,
    PriceInfo,
    SelectionScore,
    WinRateInfo,
)
from risk_management.portfolio_builder import PortfolioBuilder


def _cfg(**overrides) -> RiskConfig:  # type: ignore[no-untyped-def]
    defaults = {
        "account_equity": 100_000,
        "risk_per_trade_pct": 0.01,
        "atr_stop_multiple": 2.0,
        "max_positions": 3,
        "max_position_weight": 0.10,
        "max_sector_weight": 0.30,
        "min_position_notional": 500.0,
        "min_breakout_days": 1,  # test: confirmation immédiate
    }
    defaults.update(overrides)
    return RiskConfig(**defaults)


def _candidates() -> list[SelectionScore]:
    return [
        SelectionScore("AAPL", "Tech", 0.95),
        SelectionScore("MSFT", "Tech", 0.90),
        SelectionScore("XOM", "Energy", 0.85),
        SelectionScore("LOW", "Retail", 0.80),
    ]


def _prices() -> dict[str, PriceInfo]:
    return {
        "AAPL": PriceInfo("AAPL", 150.0, 5.0),
        "MSFT": PriceInfo("MSFT", 300.0, 8.0),
        "XOM": PriceInfo("XOM", 100.0, 3.0),
        "LOW": PriceInfo("LOW", 50.0, 2.0),
    }


def _long_predictions(symbols: list[str]) -> dict[str, PredictionInfo]:
    return {
        symbol: PredictionInfo(
            symbol, 0.80, 1, "run1",
            predicted_side="long", proba_long=0.80, proba_flat=0.10, proba_short=0.10,
        )
        for symbol in symbols
    }


def _directional_stats(symbol: str, side: str = "long") -> DirectionalWinRateInfo:
    return DirectionalWinRateInfo(
        symbol=symbol,
        side=side,
        hit_rate=0.60,
        payoff=1.5,
        trade_count=100,
        run_id="run1",
    )


def test_build_respects_max_positions() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices(), predictions=_long_predictions([c.symbol for c in _candidates()]))
    accepted = [e for e in entries if e.approved_shares > 0]
    assert len(accepted) <= 3


def test_missing_price_rejected() -> None:
    builder = PortfolioBuilder(_cfg())
    cands = [SelectionScore("NOPE", "Tech", 0.99)]
    entries = builder.build(cands, {}, predictions=_long_predictions(["NOPE"]))
    assert entries[0].decision == "REJECTED"
    assert "prix" in entries[0].decision_reason
    assert entries[0].decision_reason_code == "missing_price"


def test_missing_atr_rejected() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": PriceInfo("AAPL", 150.0, None)},
        predictions=_long_predictions(["AAPL"]),
    )
    assert entries[0].decision == "REJECTED"
    assert "sizing" in entries[0].decision_reason
    assert entries[0].decision_reason_code == "rejected_atr_missing"


def test_accepted_entries_have_positive_weight() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices(), predictions=_long_predictions([c.symbol for c in _candidates()]))
    for e in entries:
        if e.decision in ("ACCEPTED", "REDUCED"):
            assert e.target_weight > 0
            assert e.approved_shares >= 1


def test_score_source_is_final_score_sentiment() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices())
    for e in entries:
        assert e.score_source == "final_score_sentiment"


# ---- V2 tests ----

def test_v2_correlation_rejection_appears_in_entries() -> None:
    rng = np.random.RandomState(42)
    base = rng.randn(60)
    mat = pd.DataFrame({"AAPL": base, "MSFT": base + rng.randn(60) * 0.05})
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        _candidates(), _prices(),
        predictions=_long_predictions([c.symbol for c in _candidates()]),
        return_matrix=mat,
    )
    corr_rejected = [e for e in entries if e.correlation_blocker is not None]
    assert len(corr_rejected) >= 1
    assert all(entry.decision_reason_code == "correlation_filter" for entry in corr_rejected)


def test_v2_kelly_sizing_used_when_enabled() -> None:
    cfg = _cfg(enable_kelly_sizing=True)
    builder = PortfolioBuilder(cfg)
    preds = _long_predictions(["AAPL"])
    wrs = {"AAPL": WinRateInfo("AAPL", 0.60, "test", "run1")}
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
        predictions=preds, win_rates=wrs,
        directional_win_rates={"AAPL": _directional_stats("AAPL")},
    )
    accepted = [e for e in entries if e.approved_shares > 0]
    assert len(accepted) == 1
    assert accepted[0].sizing_method in ("kelly_atr", "kelly_only")


def test_v2_rejects_symbols_without_ternary_predictions() -> None:
    builder = PortfolioBuilder(_cfg())
    v2 = builder.build(_candidates(), _prices())
    assert v2 == []


def test_post_prediction_score_vetoes_do_not_change_ml_selection_authority() -> None:
    builder = PortfolioBuilder(
        _cfg(min_score_veto_long=0.70, max_score_veto_short=0.20)
    )
    candidates = [
        SelectionScore("AAPL", "Tech", 0.60),
        SelectionScore("MSFT", "Tech", 0.40),
    ]
    predictions = {
        "AAPL": PredictionInfo("AAPL", 0.95, 1, "run1", "long", 0.95, 0.03, 0.02),
        "MSFT": PredictionInfo("MSFT", 0.05, 0, "run1", "short", 0.05, 0.03, 0.92),
    }

    assert builder.build(candidates, _prices(), predictions=predictions) == []


def test_v2_conviction_score_in_entry() -> None:
    preds = _long_predictions(["AAPL"])
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
        predictions=preds,
    )
    e = entries[0]
    assert e.conviction_score == pytest.approx(0.80)


def test_short_uses_proba_short_for_kelly_and_audit() -> None:
    cfg = _cfg(enable_kelly_sizing=True)
    builder = PortfolioBuilder(cfg)
    preds = {
        "AAPL": PredictionInfo(
            "AAPL",
            0.20,
            0,
            "run1",
            predicted_side="short",
            proba_long=0.20,
            proba_flat=0.10,
            proba_short=0.80,
        )
    }
    wrs = {"AAPL": WinRateInfo("AAPL", 0.60, "test", "run1")}

    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.20, side="sell")],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
        predictions=preds,
        win_rates=wrs,
        directional_win_rates={"AAPL": _directional_stats("AAPL", "short")},
    )

    entry = entries[0]
    assert entry.predicted_proba == pytest.approx(0.80)
    assert entry.conviction_score == pytest.approx(0.80)
    expected_p_eff = cfg.prediction_confidence_weight * 0.80 + cfg.historical_win_rate_weight * 0.60
    assert entry.effective_probability == pytest.approx(expected_p_eff)


def test_kelly_rejects_negative_directional_edge() -> None:
    builder = PortfolioBuilder(_cfg(enable_kelly_sizing=True))
    predictions = _long_predictions(["AAPL"])
    directional_stats = DirectionalWinRateInfo(
        symbol="AAPL",
        side="long",
        hit_rate=0.45,
        payoff=0.8,
        trade_count=100,
        run_id="run1",
    )

    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
        predictions=predictions,
        directional_win_rates={"AAPL": directional_stats},
    )

    assert entries[0].approved_shares == 0
    assert entries[0].decision_reason_code == "abstention_gate"


def test_builder_enforces_short_cap_and_places_stop_above_entry() -> None:
    cfg = _cfg(max_positions=3, max_long_positions=3, max_short_positions=1)
    builder = PortfolioBuilder(cfg)
    candidates = [
        SelectionScore("AAPL", "Tech", 0.20),
        SelectionScore("MSFT", "Tech", 0.20),
    ]
    predictions = {
        symbol: PredictionInfo(
            symbol,
            0.10,
            0,
            "run1",
            predicted_side="short",
            proba_long=0.10,
            proba_flat=0.10,
            proba_short=0.80,
        )
        for symbol in ("AAPL", "MSFT")
    }

    entries = builder.build(candidates, _prices(), predictions=predictions)

    accepted = [entry for entry in entries if entry.approved_shares > 0]
    assert len(accepted) == 1
    assert accepted[0].side == "sell"
    assert accepted[0].stop_price_initial > accepted[0].entry_price
    assert any(entry.decision_reason == "max_short_positions atteint" for entry in entries)


def test_builder_propagates_walk_forward_metadata() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        [
            SelectionScore(
                "AAPL",
                "Tech",
                0.91,
                score_source="final_score_walk_forward",
                walk_forward_sentiment_weight=0.2,
                walk_forward_macro_weight=0.1,
                walk_forward_quant_weight=0.7,
                calibration_run_id="wf-001",
                calibration_source="walk_forward",
            )
        ],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
            predictions=_long_predictions(["AAPL"]),
    )

    entry = entries[0]
    assert entry.score_source == "final_score_walk_forward"
    assert entry.walk_forward_sentiment_weight == 0.2
    assert entry.walk_forward_macro_weight == 0.1
    assert entry.walk_forward_quant_weight == 0.7
    assert entry.calibration_run_id == "wf-001"


def test_builder_preserves_selector_rank_and_metadata() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        [
            SelectionScore(
                "AAPL",
                "Tech",
                0.91,
                    selection_rank=5,
                selector_signal_mode="sector_neutralized",
                selection_explanation="mode=sector_neutralized; rank=5",
                selector_earnings_blackout=0,
            )
        ],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
            predictions=_long_predictions(["AAPL"]),
    )

    entry = entries[0]
    assert entry.selection_rank == 5
    assert entry.selector_signal_mode == "sector_neutralized"
    assert entry.selection_explanation == "mode=sector_neutralized; rank=5"
    assert entry.selector_earnings_blackout == 0


def test_builder_supports_fractional_entries_when_enabled() -> None:
    cfg = _cfg(
        account_equity=1_000,
        risk_per_trade_pct=0.01,
        atr_stop_multiple=2.0,
        max_positions=3,
        max_position_weight=0.50,
        max_sector_weight=0.80,
        min_position_notional=100.0,
        allow_fractional_shares=True,
    )
    builder = PortfolioBuilder(cfg)

    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": PriceInfo("AAPL", 500.0, 10.0)},
            predictions=_long_predictions(["AAPL"]),
    )

    assert len(entries) == 1
    assert entries[0].decision == "ACCEPTED"
    assert entries[0].proposed_shares == 0.5
    assert entries[0].approved_shares == 0.5
    assert entries[0].target_notional == 250.0


