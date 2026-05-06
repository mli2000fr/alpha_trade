"""Fixtures partagées pour les suites benchmark (Phase F / S23.1)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# Configuration par défaut : datasets compacts pour rester < 5 s par bench.
N_SYMBOLS_DEFAULT = 200
N_DAYS_DEFAULT = 252


@pytest.fixture(scope="session")
def synthetic_market_frame() -> pd.DataFrame:
    """DataFrame OHLCV synthétique reproductible (200 symboles × 252 jours)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end="2025-12-31", periods=N_DAYS_DEFAULT)
    rows = []
    for i in range(N_SYMBOLS_DEFAULT):
        sym = f"SYM{i:03d}"
        prices = 100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.012, N_DAYS_DEFAULT))
        for d, p in zip(dates, prices):
            rows.append({
                "symbol": sym,
                "date": d,
                "open": float(p),
                "high": float(p) * 1.01,
                "low": float(p) * 0.99,
                "close": float(p),
                "volume": int(rng.integers(500_000, 5_000_000)),
            })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture(scope="session")
def synthetic_symbols() -> list[str]:
    return [f"SYM{i:03d}" for i in range(N_SYMBOLS_DEFAULT)]

