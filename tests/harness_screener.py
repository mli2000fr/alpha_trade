from datetime import datetime, timezone
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from screener.models import ScreenerConfig
from screener import compute_scores_from_prices


def _make_symbol_frame(symbol: str, base_price: float, drift: float, volume: float, rows: int = 2600) -> pd.DataFrame:
    dates = pd.bdate_range(end=datetime.now(timezone.utc), periods=rows)
    trend = np.linspace(0.0, drift, rows)
    close = base_price * (1.0 + trend)
    high = close * 1.01
    low = close * 0.99

    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": dates,
            "close_price": close,
            "high_price": high,
            "low_price": low,
            "volume": np.full(rows, volume),
        }
    )


def main() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=500_000.0)

    aaa = _make_symbol_frame("AAA", base_price=50.0, drift=0.30, volume=25_000)
    bbb = _make_symbol_frame("BBB", base_price=20.0, drift=0.02, volume=2_000)
    ccc = _make_symbol_frame("CCC", base_price=100.0, drift=-0.05, volume=12_000)

    prices = pd.concat([aaa, bbb, ccc], ignore_index=True)
    spy_return_6m = 0.06

    scores = compute_scores_from_prices(prices, spy_return_6m=spy_return_6m, config=config)
    print(scores.head(10).to_string(index=False))

    assert "BBB" not in set(scores["symbol"]), "BBB doit etre filtre au passage liquidite"
    assert "AAA" in set(scores["symbol"]), "AAA devrait passer le pipeline"


if __name__ == "__main__":
    main()

