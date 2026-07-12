import pandas as pd
import numpy as np

from modelFactory import dataset
from modelFactory import global_model, tabular_baseline

def test_dataset_importable():
    assert hasattr(dataset, "__doc__")


def test_build_sequences_builds_windows_and_skips_non_finite_targets() -> None:
    features = np.arange(10, dtype=float).reshape(5, 2)
    targets = np.array([0.0, 1.0, 2.0, np.nan, 1.0])

    sequences, labels = dataset.build_sequences(features, targets, seq_len=3)

    assert sequences.shape == (2, 3, 2)
    assert sequences.tolist() == [features[0:3].tolist(), features[2:5].tolist()]
    assert labels.tolist() == [2.0, 1.0]


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


def test_prepare_symbol_frame_merges_selector_context_features() -> None:
    n = 260
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = pd.Series([100.0 + i for i in range(n)], dtype=float)
    bars = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
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
    selector_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "date": [dates[-1]],
            "trend_score": [0.88],
            "vcp_score": [0.66],
            "selector_signal_mode": ["sector_neutralized"],
        }
    )
    cfg = dataset.DataConfig(include_selector_context_features=True)

    prepared = dataset.prepare_symbol_frame(bars, cfg, selector_df=selector_df)

    assert "selector_trend_score" in prepared.columns
    assert "selector_mode_sector_neutralized" in prepared.columns
    assert prepared.iloc[-1]["selector_trend_score"] == 0.88


def test_future_return_not_in_feature_columns() -> None:
    """Anti-leakage : future_return ne doit jamais apparaître dans FEATURE_COLUMNS.

    Les features listées dans `get_feature_columns()` sont utilisées pour
    construire les inputs de l'entraînement. `future_return` est la target
    dérivée — la laisser entrer dans les features serait une fuite directe.
    """
    from modelFactory.features import FEATURE_COLUMNS, EXPERT_FEATURE_COLUMNS, SENTIMENT_FEATURE_COLUMNS, get_feature_columns

    forbidden = {"future_return", "target"}
    base_cols = set(get_feature_columns())
    expert_cols = set(get_feature_columns(feature_set="expert"))
    sentiment_cols = set(get_feature_columns(include_sentiment=True))

    assert base_cols.isdisjoint(forbidden), f"Colonnes interdites dans feature_cols de base: {base_cols & forbidden}"
    assert expert_cols.isdisjoint(forbidden), f"Colonnes interdites dans feature_cols expert: {expert_cols & forbidden}"
    assert sentiment_cols.isdisjoint(forbidden), f"Colonnes interdites dans feature_cols sentiment: {sentiment_cols & forbidden}"

    assert "future_return" not in FEATURE_COLUMNS
    assert "future_return" not in EXPERT_FEATURE_COLUMNS
    assert "future_return" not in SENTIMENT_FEATURE_COLUMNS


def test_scaler_fit_only_on_train_split() -> None:
    """Anti-leakage : le scaler doit être fitté uniquement sur le split train.

    Vérification que `FeatureScaler.fit()` sur le train et `transform()` sur
    le test ne produit pas une normalisation identique à celle qui utiliserait
    les stats du test (ce qui serait une fuite).
    """
    import numpy as np
    from modelFactory.dataset import FeatureScaler, chrono_split

    n = 100
    # Deux segments de distribution très différente
    low_vals = [float(i) * 0.01 for i in range(60)]
    high_vals = [100.0 + float(i) for i in range(40)]
    all_vals = low_vals + high_vals

    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=n, freq="D"), "f1": all_vals})
    split = chrono_split(df, 0.6, 0.2)

    scaler = FeatureScaler(feature_names=["f1"])
    scaler.fit(split.train)

    # mean_ et std_ doivent correspondre à la distribution du train (valeurs faibles)
    assert scaler.mean_ is not None
    assert scaler.std_ is not None
    assert scaler.mean_[0] < 1.0, "Le mean du scaler doit refléter uniquement le train (valeurs < 1)"
    assert scaler.std_[0] < 1.0, "Le std du scaler doit refléter uniquement le train (std faible)"

    # Le test transformé doit produire des valeurs très éloignées de 0 (shift de distribution)
    test_transformed = scaler.transform(split.test)
    assert np.abs(test_transformed[:, 0]).mean() > 50.0, (
        "Les valeurs test transformées avec les stats train doivent être très éloignées de 0 "
        "(preuve que le scaler est bien fitté seulement sur train)"
    )


def test_chrono_split_no_overlap_between_train_val_test() -> None:
    """Intégrité temporelle : aucun recouvrement d'index entre train, val et test."""
    n = 100
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=n, freq="D"), "i": range(n)})

    split = dataset.chrono_split(df, 0.60, 0.20, forecast_horizon=3)

    train_idx = set(split.train["i"].tolist())
    val_idx = set(split.val["i"].tolist())
    test_idx = set(split.test["i"].tolist())

    assert train_idx.isdisjoint(val_idx), "Recouvrement entre train et val détecté"
    assert train_idx.isdisjoint(test_idx), "Recouvrement entre train et test détecté"
    assert val_idx.isdisjoint(test_idx), "Recouvrement entre val et test détecté"

    if not split.train.empty:
        if not split.val.empty:
            assert max(split.train["i"]) < min(split.val["i"]), "train doit précéder val chronologiquement"
        if not split.test.empty:
            assert max(split.val["i"]) < min(split.test["i"]) if not split.val.empty else True, (
                "val doit précéder test chronologiquement"
            )


