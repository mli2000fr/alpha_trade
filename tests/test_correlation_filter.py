"""Tests unitaires — filtre de corrélation Pearson V2."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_management.correlation_filter import (
    CORRELATION_CONVENTION_PRICE_ONLY,
    CORRELATION_CONVENTION_TOTAL_RETURN,
    build_return_matrix,
    filter_correlated,
)
from risk_management.models import EnrichedSelection


def _ec(symbol: str, conviction: float) -> EnrichedSelection:
    return EnrichedSelection(
        symbol=symbol, sector="Tech", score_used=conviction,
        score_source="conviction_score",
        predicted_proba=None, historical_win_rate=None, conviction_score=conviction,
    )


def _returns_matrix(symbols: list[str], n: int = 60, corr_value: float = 0.95) -> pd.DataFrame:
    """Génère une matrice de rendements synthétique avec corrélation contrôlée."""
    rng = np.random.RandomState(42)
    base = rng.randn(n)
    data: dict[str, np.ndarray] = {}
    for i, s in enumerate(symbols):
        noise = rng.randn(n) * (1 - abs(corr_value))
        data[s] = base * corr_value + noise if corr_value >= 0 else -base * abs(corr_value) + noise
    return pd.DataFrame(data)


@pytest.mark.unit
def test_high_correlation_rejects_lower_conviction() -> None:
    cands = [_ec("AAPL", 0.9), _ec("MSFT", 0.7)]
    mat = _returns_matrix(["AAPL", "MSFT"], corr_value=0.95)
    retained, rejections = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert len(retained) == 1
    assert retained[0].symbol == "AAPL"
    assert len(rejections) == 1
    assert rejections[0].rejected_symbol == "MSFT"
    assert rejections[0].blocker_symbol == "AAPL"


@pytest.mark.unit
def test_low_correlation_keeps_both() -> None:
    rng = np.random.RandomState(42)
    mat = pd.DataFrame({"A": rng.randn(60), "B": rng.randn(60)})
    cands = [_ec("A", 0.9), _ec("B", 0.7)]
    retained, rejections = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert len(retained) == 2
    assert len(rejections) == 0


@pytest.mark.unit
def test_missing_data_no_rejection() -> None:
    mat = pd.DataFrame({"AAPL": np.random.randn(60)})
    cands = [_ec("AAPL", 0.9), _ec("NOPE", 0.7)]
    retained, rejections = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert len(retained) == 2
    assert len(rejections) == 0


@pytest.mark.unit
def test_insufficient_overlap_no_rejection() -> None:
    mat = _returns_matrix(["AAPL", "MSFT"], n=10, corr_value=0.99)
    cands = [_ec("AAPL", 0.9), _ec("MSFT", 0.7)]
    retained, rejections = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert len(retained) == 2
    assert len(rejections) == 0


@pytest.mark.unit
def test_negative_correlation_no_rejection() -> None:
    rng = np.random.RandomState(42)
    base = rng.randn(60)
    # Explicitly negate to ensure negative correlation
    mat = pd.DataFrame({"AAPL": base, "MSFT": -base})
    cands = [_ec("AAPL", 0.9), _ec("MSFT", 0.7)]
    retained, rejections = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert len(retained) == 2
    assert len(rejections) == 0


@pytest.mark.unit
def test_deterministic_order() -> None:
    cands = [_ec("AAPL", 0.9), _ec("MSFT", 0.7), _ec("GOOG", 0.5)]
    mat = _returns_matrix(["AAPL", "MSFT", "GOOG"], corr_value=0.95)
    r1, rej1 = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    r2, rej2 = filter_correlated(cands, mat, threshold=0.80, min_overlap=40)
    assert [c.symbol for c in r1] == [c.symbol for c in r2]
    assert [r.rejected_symbol for r in rej1] == [r.rejected_symbol for r in rej2]


@pytest.mark.unit
def test_build_return_matrix_price_only_vs_total_return_conventions() -> None:
    closes = pd.DataFrame(
        {
            "KO": [100.0, 100.0, 100.0],
            "PG": [100.0, 100.0, 100.0],
        },
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    dividends = pd.DataFrame(
        {
            "KO": [0.0, 1.0, 0.0],
            "PG": [0.0, 0.0, 0.0],
        },
        index=closes.index,
    )

    price_only = build_return_matrix(closes, convention=CORRELATION_CONVENTION_PRICE_ONLY)
    total_return = build_return_matrix(
        closes,
        cash_dividends=dividends,
        convention=CORRELATION_CONVENTION_TOTAL_RETURN,
    )

    assert price_only.iloc[1]["KO"] == pytest.approx(0.0)
    assert total_return.iloc[1]["KO"] == pytest.approx(0.01)
    assert total_return.iloc[1]["PG"] == pytest.approx(0.0)


@pytest.mark.unit
def test_build_return_matrix_rejects_unknown_convention() -> None:
    with pytest.raises(ValueError):
        build_return_matrix(pd.DataFrame({"AAPL": [1.0, 2.0]}), convention="mystery")


