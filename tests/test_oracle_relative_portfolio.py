from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.conditional_oracle_ranker import RANK_SCORE_COL
from modelFactory.oracle_relative_portfolio import (
    RelativePortfolioConfig,
    evaluate_relative_portfolio,
)


def _oof(*, aligned: bool) -> pd.DataFrame:
    rows = []
    for fold, date in enumerate(pd.to_datetime(["2024-01-02", "2024-07-02", "2025-01-02"])):
        returns = [-0.10, -0.03, 0.03, 0.10]
        scores = returns if aligned else list(reversed(returns))
        for idx, (ret, score) in enumerate(zip(returns, scores, strict=True)):
            rows.append({
                "date": date, "symbol": f"S{idx}", "fold_index": fold,
                "future_return": ret, RANK_SCORE_COL: score,
            })
    return pd.DataFrame(rows)


def test_relative_portfolio_selects_only_from_oof_score() -> None:
    config = RelativePortfolioConfig(
        commission_bps=0, slippage_bps=0, borrow_fee_annual=0,
        min_mean_net_cohort_return=0.001,
    )
    _, report = evaluate_relative_portfolio(_oof(aligned=True), horizon=20, config=config)
    assert report["mean_long_return"] == pytest.approx(0.10)
    assert report["mean_short_return"] == pytest.approx(-0.10)
    assert report["mean_portfolio_gross_return"] == pytest.approx(0.10)
    assert report["gates"]["replay_authorized"] is True


def test_relative_portfolio_rejects_inverted_unstable_signal() -> None:
    config = RelativePortfolioConfig(
        commission_bps=0, slippage_bps=0, borrow_fee_annual=0,
    )
    _, report = evaluate_relative_portfolio(_oof(aligned=False), horizon=20, config=config)
    assert report["mean_portfolio_net_return"] < 0
    assert report["gates"]["replay_authorized"] is False


def test_relative_portfolio_deducts_round_trip_and_borrow_costs() -> None:
    config = RelativePortfolioConfig(
        commission_bps=1, slippage_bps=2, borrow_fee_annual=0.003,
    )
    _, report = evaluate_relative_portfolio(_oof(aligned=True), horizon=20, config=config)
    expected_cost = 0.0006 + 0.5 * 0.003 * 20 / 252
    assert report["mean_portfolio_net_return"] == pytest.approx(0.10 - expected_cost)
