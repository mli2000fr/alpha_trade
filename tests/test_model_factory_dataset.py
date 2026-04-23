import pandas as pd

from modelFactory import dataset

def test_dataset_importable():
    assert hasattr(dataset, "__doc__")


def test_generate_walk_forward_splits_is_chronological() -> None:
    df = pd.DataFrame({"i": range(900)})

    splits = dataset.generate_walk_forward_splits(
        df,
        min_train_size=400,
        val_size=100,
        test_size=100,
        step_size=100,
        max_splits=3,
    )

    assert len(splits) == 3
    assert splits[0].train["i"].iloc[0] == 0
    assert splits[0].train["i"].iloc[-1] == 399
    assert splits[0].val["i"].iloc[0] == 400
    assert splits[0].test["i"].iloc[0] == 500
    assert splits[1].train["i"].iloc[-1] == 499
    assert splits[2].test["i"].iloc[-1] == 799


def test_prepare_symbol_frame_adds_future_return() -> None:
    n = 260
    bars = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
            "date": pd.date_range("2020-01-01", periods=n, freq="D"),
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.0 + i for i in range(n)],
            "volume": [1_000_000.0] * n,
            "adj_close": [100.0 + i for i in range(n)],
            "vwap": [100.0 + i for i in range(n)],
            "daily_return": [0.0] * n,
            "is_filled": [0] * n,
        }
    )
    benchmark = bars.assign(symbol="SPY")
    cfg = dataset.DataConfig(feature_set="expert", benchmark_symbol="SPY")

    prepared = dataset.prepare_symbol_frame(bars, cfg, benchmark_df=benchmark)

    assert "future_return" in prepared.columns
    assert "relative_strength_20" in prepared.columns


def test_prepare_symbol_frame_merges_cross_sectional_features() -> None:
    n = 260
    dates = pd.date_range("2020-01-01", periods=n, freq="D")

    def _bars(symbol: str, base: float) -> pd.DataFrame:
        close = pd.Series([base + i for i in range(n)], dtype=float)
        return pd.DataFrame(
            {
                "symbol": [symbol] * n,
                "date": dates,
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.98,
                "close": close,
                "volume": [1_000_000.0] * n,
                "adj_close": close,
                "vwap": close,
                "daily_return": [0.0] * n,
                "is_filled": [0] * n,
            }
        )

    bars = _bars("AAPL", 100.0)
    benchmark = _bars("SPY", 90.0)
    universe = pd.concat([bars, _bars("MSFT", 110.0), _bars("NVDA", 120.0)], ignore_index=True)
    cfg = dataset.DataConfig(feature_set="expert", benchmark_symbol="SPY", enable_cross_sectional_features=True, cross_sectional_min_universe=2)

    prepared = dataset.prepare_symbol_frame(bars, cfg, benchmark_df=benchmark, universe_df=universe)

    assert "ret_20_rank" in prepared.columns
    assert "relative_strength_20_rank" in prepared.columns
    assert prepared.attrs["cross_sectional_diagnostics"]["enabled"] is True


