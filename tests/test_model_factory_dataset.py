import pandas as pd

from modelFactory import dataset
from modelFactory import global_model, tabular_baseline

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


def test_chrono_split_purges_train_and_val_boundaries_for_forecast_horizon() -> None:
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20, freq="D"), "i": range(20)})

    split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=2)

    assert split.train["i"].tolist() == list(range(8))
    assert split.val["i"].tolist() == [10, 11, 12]
    assert split.test["i"].tolist() == [15, 16, 17, 18, 19]


def test_generate_walk_forward_splits_purges_boundary_windows() -> None:
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=24, freq="D"), "i": range(24)})

    splits = dataset.generate_walk_forward_splits(
        df,
        min_train_size=8,
        val_size=4,
        test_size=4,
        step_size=4,
        max_splits=2,
        forecast_horizon=2,
    )

    assert [row for row in splits[0].train["i"].tolist()] == [0, 1, 2, 3, 4, 5]
    assert splits[0].val["i"].tolist() == [8, 9]
    assert splits[0].test["i"].tolist() == [12, 13, 14, 15]
    assert splits[1].train["i"].tolist() == list(range(10))
    assert splits[1].val["i"].tolist() == [12, 13]


def test_tabular_split_purges_future_horizon_rows() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=18, freq="D"),
            "target": [1.0] * 18,
            "future_return": [0.01] * 18,
            "feat": [float(i) for i in range(18)],
        }
    )

    train_df, val_df, test_df = tabular_baseline.tabular_split(df, train_ratio=0.5, val_ratio=0.25, forecast_horizon=2)

    assert train_df["feat"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert val_df["feat"].tolist() == [9.0, 10.0]
    assert test_df["feat"].tolist() == [13.0, 14.0, 15.0, 16.0, 17.0]


def test_global_date_split_purges_last_dates_before_next_bucket() -> None:
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    df = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["AAPL"] * 8 + ["MSFT"] * 8,
            "target": [1.0] * 16,
        }
    ).sort_values(["date", "symbol"]).reset_index(drop=True)

    train_df, val_df, test_df = global_model._split_global_by_dates(df, train_ratio=0.5, val_ratio=0.25, forecast_horizon=1)

    assert sorted(train_df["date"].dt.strftime("%Y-%m-%d").unique().tolist()) == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert sorted(val_df["date"].dt.strftime("%Y-%m-%d").unique().tolist()) == ["2024-01-05"]
    assert sorted(test_df["date"].dt.strftime("%Y-%m-%d").unique().tolist()) == ["2024-01-07", "2024-01-08"]


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


