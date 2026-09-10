from __future__ import annotations

import pandas as pd

from modelFactory.oracle.dynamic_universe import compute_dynamic_membership
import modelFactory.oracle.dataset as oracle_dataset


def _bars(symbol: str = "AAA", rows: int = 530) -> pd.DataFrame:
    return pd.DataFrame({"symbol": symbol, "date": pd.bdate_range("2020-01-01", periods=rows),
                         "close": 50.0, "volume": 1_000_000.0, "is_filled": 0})


def test_dynamic_membership_requires_504_real_sessions() -> None:
    bars = _bars()
    membership, diagnostics = compute_dynamic_membership(
        bars, start_date="2020-01-01", end_date="2022-12-31")
    assert membership["date"].min() == bars.loc[503, "date"]
    assert diagnostics["rows"] == len(bars) - 503
    assert diagnostics["symbols"] == 1


def test_dynamic_membership_applies_price_liquidity_and_filled_gates() -> None:
    bars = _bars()
    bars.loc[491:510, "volume"] = 1.0
    bars.loc[511, "close"] = 5.0
    bars.loc[512:518, "is_filled"] = 1
    membership, _ = compute_dynamic_membership(
        bars, start_date="2020-01-01", end_date="2022-12-31")
    admitted = set(membership["date"])
    assert bars.loc[510, "date"] not in admitted
    assert bars.loc[511, "date"] not in admitted
    assert bars.loc[518, "date"] not in admitted


def test_feature_ranks_are_computed_after_daily_membership_filter(monkeypatch) -> None:
    day = pd.Timestamp("2024-01-02")
    bars = pd.DataFrame({
        "symbol": ["AAA", "BBB", "CCC"], "date": [day, day, day],
        "adj_close": [1.0, 2.0, 3.0],
    })
    monkeypatch.setattr(oracle_dataset, "load_universe_bars", lambda *a, **k: bars)
    monkeypatch.setattr(oracle_dataset, "load_benchmark_bars", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(oracle_dataset, "load_security_discontinuities", lambda: {})
    monkeypatch.setattr(oracle_dataset, "split_frame_on_discontinuities", lambda frame, *a: [frame])

    def fake_features(segment, **kwargs):
        frame = segment.copy()
        frame["momentum_3"] = frame["adj_close"]
        return frame

    monkeypatch.setattr(oracle_dataset, "compute_features", fake_features)
    membership = pd.DataFrame({"date": [day, day], "symbol": ["BBB", "CCC"]})
    result = oracle_dataset.build_feature_matrix(
        object(), ["AAA", "BBB", "CCC"], start_date="2024-01-02", end_date="2024-01-02",
        membership=membership,
    ).sort_values("symbol")
    assert result["symbol"].tolist() == ["BBB", "CCC"]
    assert result["momentum_3_xs_rank"].tolist() == [0.5, 1.0]
