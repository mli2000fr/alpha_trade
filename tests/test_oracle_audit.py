"""Tests unitaires de l'audit Oracle — Sprint S2 (fonctions pures, sans DB)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.audit import (
    compare_golden,
    compute_capture,
    compute_decile_returns,
    decile_monotonicity,
)


def _labeled_frame(sides: list[str], tops: list[float | None], bottoms: list[float | None],
                   deciles: list[int | None]) -> pd.DataFrame:
    return pd.DataFrame({
        "side": sides,
        "oracle_top10": tops,
        "oracle_bottom10": bottoms,
        "oracle_decile": deciles,
    })


# ═══════════════════════════════════════════════════════════════════
# compute_capture
# ═══════════════════════════════════════════════════════════════════

class TestComputeCapture:
    def test_full_capture(self):
        df = _labeled_frame(
            ["buy", "buy", "sell", "sell"],
            [1, 1, None, None],
            [None, None, 1, 1],
            [10, 10, 1, 1],
        )
        cap = compute_capture(df)
        assert cap["top_capture_pct"] == pytest.approx(100.0)
        assert cap["bottom_capture_pct"] == pytest.approx(100.0)

    def test_partial_capture(self):
        # 4 longs, 1 dans le top10 → 25% ; 4 shorts, 1 dans le bottom10 → 25%
        df = _labeled_frame(
            ["buy"] * 4 + ["sell"] * 4,
            [1, 0, 0, 0] + [None] * 4,
            [None] * 4 + [1, 0, 0, 0],
            [10, 5, 5, 5] + [1, 5, 5, 5],
        )
        cap = compute_capture(df)
        assert cap["top_capture_pct"] == pytest.approx(25.0)
        assert cap["bottom_capture_pct"] == pytest.approx(25.0)

    def test_nan_ignored(self):
        df = _labeled_frame(["buy", "buy"], [1, None], [None, None], [10, None])
        cap = compute_capture(df)
        assert cap["top_capture_pct"] == pytest.approx(100.0)  # NaN exclu du calcul


# ═══════════════════════════════════════════════════════════════════
# compute_decile_returns + decile_monotonicity
# ═══════════════════════════════════════════════════════════════════

class TestDecileReturns:
    def test_decile_means(self):
        df = pd.DataFrame({
            "oracle_decile": [1, 1, 10, 10],
            "future_return": [-0.10, -0.20, 0.10, 0.20],
        })
        stats = compute_decile_returns(df)
        assert stats.loc[1, "mean"] == pytest.approx(-0.15)
        assert stats.loc[10, "mean"] == pytest.approx(0.15)

    def test_monotonicity_perfectly_increasing(self):
        stats = pd.DataFrame(
            {"mean": [-0.17, -0.09, -0.05, -0.03, -0.01, 0.01, 0.03, 0.06, 0.10, 0.21]},
            index=range(1, 11),
        )
        assert decile_monotonicity(stats) == pytest.approx(1.0)

    def test_monotonicity_decreasing_is_negative(self):
        stats = pd.DataFrame(
            {"mean": [0.21, 0.10, 0.06, 0.03, 0.01, -0.01, -0.03, -0.05, -0.09, -0.17]},
            index=range(1, 11),
        )
        assert decile_monotonicity(stats) == pytest.approx(-1.0)


# ═══════════════════════════════════════════════════════════════════
# compare_golden
# ═══════════════════════════════════════════════════════════════════

class TestCompareGolden:
    def test_perfect_match(self):
        labeled = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "side": ["buy", "sell"],
            "signal_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "oracle_pct_rank": [0.95, 0.05],
            "oracle_decile": [10, 1],
            "oracle_top10": [1, 0],
            "oracle_bottom10": [0, 1],
        })
        golden = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "side": ["buy", "sell"],
            "signal_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "horizon": [20, 20],
            "pct_rank": [0.95, 0.05],
            "decile": [10, 1],
            "universe_size": [394, 394],
            "fwd_ret": [0.1, -0.1],
        })
        cmp = compare_golden(labeled, golden)
        assert cmp["matched"] == 2
        assert cmp["max_pct_rank_diff"] == pytest.approx(0.0)
        assert cmp["decile_match_pct"] == pytest.approx(100.0)
        assert cmp["top10_match_pct"] == pytest.approx(100.0)
        assert cmp["bottom10_match_pct"] == pytest.approx(100.0)

    def test_divergence_detected(self):
        labeled = pd.DataFrame({
            "symbol": ["AAPL"],
            "side": ["buy"],
            "signal_date": pd.to_datetime(["2025-01-02"]),
            "oracle_pct_rank": [0.85],
            "oracle_decile": [9],
            "oracle_top10": [0],
            "oracle_bottom10": [0],
        })
        golden = pd.DataFrame({
            "symbol": ["AAPL"],
            "side": ["buy"],
            "signal_date": pd.to_datetime(["2025-01-02"]),
            "horizon": [20],
            "pct_rank": [0.95],
            "decile": [10],
            "universe_size": [394],
            "fwd_ret": [0.1],
        })
        cmp = compare_golden(labeled, golden)
        assert cmp["max_pct_rank_diff"] == pytest.approx(0.10)
        assert cmp["decile_match_pct"] == pytest.approx(0.0)
        assert cmp["top10_match_pct"] == pytest.approx(0.0)
