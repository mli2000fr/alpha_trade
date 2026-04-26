"""Tests unitaires — filtre de corrélation Pearson V2."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_management.correlation_filter import filter_correlated
from risk_management.models import EnrichedCandidate


def _ec(symbol: str, conviction: float) -> EnrichedCandidate:
    return EnrichedCandidate(
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


