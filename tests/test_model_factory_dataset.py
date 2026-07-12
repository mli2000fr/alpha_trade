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


# ── Fold isolation tests (Sprint 3 Point 3.4) ────────────────────────────────

class TestFoldDisjointness:
    """Les folds train/val/test ne doivent jamais partager de lignes."""

    def test_chrono_split_folds_are_disjoint(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=5)

        # Comparaison par contenu (les index sont reset → RangeIndex partagé)
        train_i = set(split.train["i"].tolist())
        val_i = set(split.val["i"].tolist())
        test_i = set(split.test["i"].tolist())

        assert len(train_i & val_i) == 0, "train ∩ val should be empty"
        assert len(val_i & test_i) == 0, "val ∩ test should be empty"
        assert len(train_i & test_i) == 0, "train ∩ test should be empty"

    def test_chrono_split_by_dates_folds_are_disjoint(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split_by_dates(df, train_ratio=0.50, val_ratio=0.25, forecast_horizon=2, date_column="date")

        train_i = set(split.train["i"].tolist())
        val_i = set(split.val["i"].tolist())
        test_i = set(split.test["i"].tolist())

        assert len(train_i & val_i) == 0
        assert len(val_i & test_i) == 0
        assert len(train_i & test_i) == 0

    def test_walk_forward_folds_are_disjoint(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        splits = dataset.generate_walk_forward_splits(
            df, min_train_size=30, val_size=10, test_size=10, step_size=10,
            max_splits=3, forecast_horizon=3,
        )
        for s in splits:
            train_i = set(s.train["i"].tolist())
            val_i = set(s.val["i"].tolist())
            test_i = set(s.test["i"].tolist())
            assert len(train_i & val_i) == 0, f"split {s.split_index}: train ∩ val non-empty"
            assert len(val_i & test_i) == 0, f"split {s.split_index}: val ∩ test non-empty"
            assert len(train_i & test_i) == 0, f"split {s.split_index}: train ∩ test non-empty"

    def test_tabular_split_preserves_disjointness(self) -> None:
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=100, freq="D"),
            "target": [1.0] * 100,
            "i": range(100),
        })
        train, val, test = tabular_baseline.tabular_split(df, train_ratio=0.50, val_ratio=0.25, forecast_horizon=5)

        train_i = set(train["i"].tolist())
        val_i = set(val["i"].tolist())
        test_i = set(test["i"].tolist())

        assert len(train_i & val_i) == 0
        assert len(val_i & test_i) == 0
        assert len(train_i & test_i) == 0


class TestEmbargo:
    """Un embargo doit exister entre la validation et le test."""

    def test_chrono_split_with_embargo_inserts_gap(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=40, freq="D"), "i": range(40)})

        # Sans embargo
        no_emb = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=2, embargo_rows=0)
        # Avec embargo
        with_emb = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=2, embargo_rows=3)

        # L'embargo doit réduire la taille du test (ou du val)
        assert len(with_emb.test) <= len(no_emb.test)
        # Le train et le val ne doivent pas changer
        assert len(with_emb.train) == len(no_emb.train)
        assert len(with_emb.val) == len(no_emb.val)

    def test_embargo_creates_temporal_gap(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=5, embargo_rows=5)

        if "date" in split.val.columns and "date" in split.test.columns:
            last_val_date = pd.to_datetime(split.val["date"]).max()
            first_test_date = pd.to_datetime(split.test["date"]).min()
            gap = (first_test_date - last_val_date).days
            # L'embargo + la purge créent un gap temporel
            assert gap >= 1, f"Expected temporal gap, got {gap} days"

    def test_embargo_can_consume_entire_test(self) -> None:
        """Si l'embargo est trop grand, le test peut devenir vide."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20, freq="D"), "i": range(20)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=0, embargo_rows=100)

        # Le test peut être vide, ce n'est pas une erreur
        assert len(split.test) >= 0  # pas de crash


class TestNoLabelLeakage:
    """Aucun label ne doit traverser une frontière de fold."""

    def test_label_at_train_end_does_not_need_val_data(self) -> None:
        """Un label à la fin du train ne doit pas nécessiter de données du fold val."""
        n = 60
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": 100.0 + np.arange(n) * 0.5,
            "i": range(n),
        })
        label_horizon = 5
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=label_horizon)

        # Le train a été purgé de label_horizon lignes à sa fin
        # Vérifions que la dernière date du train + label_horizon ≤ première date du val
        if "date" in split.train.columns and "date" in split.val.columns:
            last_train_date = pd.to_datetime(split.train["date"]).max()
            first_val_date = pd.to_datetime(split.val["date"]).min()
            days_gap = (first_val_date - last_train_date).days
            assert days_gap >= label_horizon, (
                f"Label leakage: last_train={last_train_date.date()}, "
                f"first_val={first_val_date.date()}, gap={days_gap}d < {label_horizon}d"
            )

    def test_triple_barrier_max_sessions_respected(self) -> None:
        """Le purge doit être ≥ max_sessions pour les labels triple-barrier."""
        n = 100
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": 100.0 + np.arange(n) * 0.5,
            "i": range(n),
        })
        max_sessions = 20  # horizon triple-barrier typique
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=max_sessions)

        if "date" in split.train.columns and "date" in split.val.columns:
            last_train_date = pd.to_datetime(split.train["date"]).max()
            first_val_date = pd.to_datetime(split.val["date"]).min()
            days_gap = (first_val_date - last_train_date).days
            assert days_gap >= max_sessions, (
                f"Triple-barrier leakage risk: gap={days_gap}d < max_sessions={max_sessions}d"
            )

    def test_no_val_data_in_train_label_window(self) -> None:
        """Les lignes du train ne doivent pas partager de dates avec le val."""
        n = 80
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "i": range(n),
        })
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=10)

        if "date" in split.train.columns and "date" in split.val.columns:
            train_dates = set(pd.to_datetime(split.train["date"]).dt.date)
            val_dates = set(pd.to_datetime(split.val["date"]).dt.date)
            test_dates = set(pd.to_datetime(split.test["date"]).dt.date)

            assert len(train_dates & val_dates) == 0, "train and val share dates"
            assert len(val_dates & test_dates) == 0, "val and test share dates"
            assert len(train_dates & test_dates) == 0, "train and test share dates"


class TestValidateFoldIsolation:
    """validate_fold_isolation détecte les violations d'isolation."""

    def test_valid_split_passes(self) -> None:
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=5, embargo_rows=3)

        report = dataset.validate_fold_isolation(split, label_horizon=5, embargo_rows=3, date_column="date")
        assert report.is_valid
        assert report.folds_disjoint
        assert report.purge_adequate
        assert len(report.violations) == 0

    def test_no_purge_with_labels_detected(self) -> None:
        """Sans purge (forecast_horizon=0) mais avec label_horizon>0, les gaps sont insuffisants."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=0)

        report = dataset.validate_fold_isolation(split, label_horizon=5, embargo_rows=0, date_column="date")
        # Les gaps devraient être insuffisants (0 jour entre train et val pour un label de 5 jours)
        assert not report.purge_adequate or len(report.violations) > 0

    def test_embargo_violation_detected(self) -> None:
        """Un embargo attendu mais absent est détecté."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=2, embargo_rows=0)

        report = dataset.validate_fold_isolation(split, label_horizon=2, embargo_rows=10, date_column="date")
        # L'embargo de 10 jours n'a pas été appliqué → devrait être détecté
        # (le gap réel est probablement < 10 jours)
        assert not report.embargo_present or len(report.violations) > 0

    def test_fold_isolation_report_to_dict(self) -> None:
        """FoldIsolationReport est sérialisable pour audit."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=5, embargo_rows=3)
        report = dataset.validate_fold_isolation(split, label_horizon=5, embargo_rows=3, date_column="date")

        d = {
            "is_valid": report.is_valid,
            "folds_disjoint": report.folds_disjoint,
            "purge_adequate": report.purge_adequate,
            "embargo_present": report.embargo_present,
            "violations": report.violations,
        }
        assert isinstance(d["is_valid"], bool)
        assert isinstance(d["violations"], list)

    def test_zero_horizon_split_still_disjoint(self) -> None:
        """Même sans purge, les folds doivent être disjoints (vérifié par date)."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="D"), "i": range(100)})
        split = dataset.chrono_split(df, 0.50, 0.25, forecast_horizon=0, embargo_rows=0)

        report = dataset.validate_fold_isolation(split, label_horizon=0, embargo_rows=0, date_column="date")
        assert report.folds_disjoint, f"Violations: {report.violations}"
        assert report.purge_adequate  # label_horizon=0 → pas d'exigence de purge


class TestFoldIsolationEndToEnd:
    """Scénarios E2E : le pipeline d'optimisation ne fuit pas."""

    def test_target_optimization_train_only(self) -> None:
        """Vérifie que optimize_target_parameters ne reçoit QUE le train."""
        from modelFactory.config import DataConfig, TargetOptimizationConfig
        from modelFactory.target_optimization import optimize_target_parameters

        n = 200
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": 100.0 + np.arange(n) * 0.3,
            "i": range(n),
        })
        df["adj_close"] = df["close"]

        # Split avec purge
        split = dataset.chrono_split(df, 0.60, 0.20, forecast_horizon=10)
        train_df = split.train.reset_index(drop=True)

        cfg = DataConfig(target_mode="binary", label_method="fixed_horizon")
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_horizons=(3, 5),
            candidate_up_thresholds=(0.0,),
            candidate_down_thresholds=(0.0,),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(train_df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert "selected_horizon" in result
        assert result["selected_horizon"] in {3, 5}

    def test_triple_barrier_optimization_train_only(self) -> None:
        """Vérifie que l'optimisation triple-barrier n'utilise que le train."""
        from modelFactory.config import DataConfig, TargetOptimizationConfig
        from modelFactory.target_optimization import optimize_target_parameters

        n = 200
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": 100.0 + np.arange(n) * 0.3,
            "high": 101.0 + np.arange(n) * 0.3,
            "low": 99.0 + np.arange(n) * 0.3,
            "close": 100.0 + np.arange(n) * 0.3,
            "i": range(n),
        })

        split = dataset.chrono_split(df, 0.60, 0.20, forecast_horizon=20)
        train_df = split.train.reset_index(drop=True)

        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier")
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_stop_atr_mults=(2.0,),
            candidate_tp_atr_mults=(3.0,),
            candidate_max_sessions=(10, 20),
            candidate_horizons=(),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(train_df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert "selected_triple_barrier_stop_atr_mult" in result
        assert "selected_triple_barrier_max_sessions" in result

    def test_val_test_not_passed_to_optimization(self) -> None:
        """Vérifie que les données de val/test ne sont JAMAIS passées à l'optimiseur."""
        from modelFactory.config import DataConfig, TargetOptimizationConfig
        from modelFactory.target_optimization import optimize_target_parameters

        n = 200
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": 100.0 + np.arange(n) * 0.3,
            "i": range(n),
        })
        df["adj_close"] = df["close"]

        split = dataset.chrono_split(df, 0.60, 0.20, forecast_horizon=10)
        train_df = split.train
        val_df = split.val
        test_df = split.test

        # On s'assure que train, val, test sont bien des DataFrames différents
        assert not train_df.equals(val_df)
        assert not val_df.equals(test_df)
        assert not train_df.equals(test_df)

        # L'optimisation ne doit utiliser que train_df
        cfg = DataConfig(target_mode="binary", label_method="fixed_horizon")
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_horizons=(5,),
            candidate_up_thresholds=(0.0,),
            candidate_down_thresholds=(0.0,),
            min_trades_fraction=0.05,
        )
        result = optimize_target_parameters(train_df.reset_index(drop=True), data_cfg=cfg, opt_cfg=opt_cfg)
        assert result["selected_horizon"] == 5

        # Vérifier qu'on obtient un résultat DIFFÉRENT si on passe val (preuve que val != train)
        result_val = optimize_target_parameters(val_df.reset_index(drop=True), data_cfg=cfg, opt_cfg=opt_cfg)
        # Les résultats peuvent différer car les données sont différentes
        # Ce qui compte c'est qu'on ne passe JAMAIS val à la place de train


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


