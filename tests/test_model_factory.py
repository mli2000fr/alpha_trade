"""Tests unitaires pour modelFactory V1."""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch

from modelFactory.config import DataConfig, ModelConfig, TrainingConfig
from modelFactory.dataset import (
    ChronoSplit,
    FeatureScaler,
    SequenceDataset,
    build_sequences,
    chrono_split,
)
from modelFactory.features import FEATURE_COLUMNS, SENTIMENT_FEATURE_COLUMNS, build_target, compute_features, get_feature_columns
from modelFactory.model import LSTMAttentionClassifier, LSTMAttentionModule, TemporalAttention


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_bars(n: int = 600) -> pd.DataFrame:
    """Génère un DataFrame de bars synthétiques."""
    np.random.seed(42)
    dates = pd.bdate_range("2015-01-02", periods=n, freq="B")
    close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    close = np.maximum(close, 1.0)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    opn = close + np.random.randn(n) * 0.1
    volume = np.random.randint(100_000, 10_000_000, size=n).astype(float)
    daily_return = np.concatenate([[0.0], np.diff(close) / close[:-1]])
    return pd.DataFrame({
        "symbol": "TEST",
        "date": dates[:n],
        "open": opn,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "adj_close": close,
        "vwap": (high + low + close) / 3,
        "daily_return": daily_return,
        "is_filled": 0,
    })


def _make_sentiment(bars_df: pd.DataFrame) -> pd.DataFrame:
    """Génère un DataFrame de sentiment synthétique aligné sur les bars."""
    dates = bars_df["date"].unique()
    n = len(dates)
    np.random.seed(99)
    return pd.DataFrame({
        "symbol": "TEST",
        "trade_date": dates,
        "news_count_1d": np.random.randint(0, 10, size=n).astype(float),
        "sentiment_net_mean_1d": np.random.uniform(-1, 1, size=n),
        "sentiment_confidence_mean_1d": np.random.uniform(0, 1, size=n),
        "major_event_flag": np.random.choice([0.0, 1.0], size=n),
    })


# ===========================================================================
# Config tests
# ===========================================================================

class TestDataConfig:
    def test_defaults(self):
        cfg = DataConfig()
        assert cfg.sequence_length == 60
        assert cfg.forecast_horizon == 10
        assert cfg.training_start_date == date(2020, 1, 1)

    def test_invalid_sequence_length(self):
        with pytest.raises(ValueError):
            DataConfig(sequence_length=0)

    def test_invalid_ratios(self):
        with pytest.raises(ValueError):
            DataConfig(train_ratio=0.9, val_ratio=0.2)

    def test_invalid_training_start_date_type(self):
        with pytest.raises(ValueError):
            DataConfig(training_start_date="2020-01-01")  # type: ignore[arg-type]


class TestModelConfig:
    def test_defaults(self):
        cfg = ModelConfig()
        assert cfg.hidden_size == 256

    def test_invalid_hidden_size(self):
        with pytest.raises(ValueError):
            ModelConfig(hidden_size=0)

    def test_invalid_dropout(self):
        with pytest.raises(ValueError):
            ModelConfig(dropout=1.0)


class TestTrainingConfig:
    def test_defaults(self):
        cfg = TrainingConfig()
        assert cfg.max_workers == 4

    def test_invalid_workers(self):
        with pytest.raises(ValueError):
            TrainingConfig(max_workers=0)


# ===========================================================================
# Feature tests
# ===========================================================================

class TestFeatures:
    def test_compute_features_returns_expected_columns(self):
        bars = _make_bars(200)
        df = compute_features(bars)
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        assert not df[FEATURE_COLUMNS].isna().any().any()

    def test_compute_features_drops_warmup(self):
        bars = _make_bars(200)
        df = compute_features(bars)
        assert len(df) < 200  # warm-up rows dropped

    def test_build_target_binary(self):
        bars = _make_bars(200)
        df = compute_features(bars)
        target = build_target(df, horizon=5)
        assert target.isin([0.0, 1.0]).sum() + target.isna().sum() == len(target)
        # Last 5 rows should be NaN
        assert target.iloc[-5:].isna().all()

    def test_compute_features_with_sentiment(self):
        bars = _make_bars(200)
        sent = _make_sentiment(bars)
        df = compute_features(bars, sentiment_df=sent, include_sentiment=True)
        all_cols = get_feature_columns(include_sentiment=True)
        for col in all_cols:
            assert col in df.columns, f"Missing column: {col}"
        assert not df[all_cols].isna().any().any()

    def test_compute_features_sentiment_missing_days_filled(self):
        """Jours sans news doivent être remplis avec 0.0."""
        bars = _make_bars(200)
        # Sentiment vide
        sent = pd.DataFrame(columns=["symbol", "trade_date", "news_count_1d",
                                       "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "major_event_flag"])
        df = compute_features(bars, sentiment_df=sent, include_sentiment=True)
        for col in SENTIMENT_FEATURE_COLUMNS:
            assert (df[col] == 0.0).all(), f"{col} should be 0.0 when no sentiment data"

    def test_get_feature_columns_flag(self):
        base = get_feature_columns(False)
        extended = get_feature_columns(True)
        assert len(extended) == len(base) + len(SENTIMENT_FEATURE_COLUMNS)

    def test_compute_features_drops_rows_with_non_finite_active_features(self):
        bars = _make_bars(260)
        zero_idx = 220
        next_idx = zero_idx + 1
        for column in ["open", "high", "low", "close", "adj_close", "vwap"]:
            bars.loc[zero_idx, column] = 0.0
        bars.loc[next_idx, ["open", "high", "low", "close", "adj_close", "vwap"]] = [101.0, 102.0, 100.0, 101.0, 101.0, 101.0]

        df = compute_features(bars)

        active_features = get_feature_columns(False)
        assert np.isfinite(df[active_features].to_numpy(dtype=float)).all()
        retained_dates = set(pd.to_datetime(df["date"]).dt.date)
        assert bars.loc[zero_idx, "date"].date() not in retained_dates
        assert bars.loc[next_idx, "date"].date() not in retained_dates


# ===========================================================================
# Dataset / split tests
# ===========================================================================

class TestChronoSplit:
    def test_split_sizes(self):
        df = pd.DataFrame({"x": range(100)})
        split = chrono_split(df, 0.7, 0.15)
        assert len(split.train) == 70
        assert len(split.val) == 15
        assert len(split.test) == 15

    def test_no_overlap(self):
        df = pd.DataFrame({"i": range(100)})
        split = chrono_split(df, 0.7, 0.15)
        all_indices = list(split.train["i"]) + list(split.val["i"]) + list(split.test["i"])
        assert all_indices == list(range(100))


class TestFeatureScaler:
    def test_fit_transform(self):
        df = pd.DataFrame({col: np.random.randn(50) for col in FEATURE_COLUMNS})
        scaler = FeatureScaler()
        scaler.fit(df)
        transformed = scaler.transform(df)
        assert transformed.shape == (50, len(FEATURE_COLUMNS))
        # Mean ~0, std ~1 after transform
        assert abs(transformed.mean()) < 0.5

    def test_state_dict_roundtrip(self):
        df = pd.DataFrame({col: np.random.randn(50) for col in FEATURE_COLUMNS})
        scaler = FeatureScaler()
        scaler.fit(df)
        sd = scaler.state_dict()
        scaler2 = FeatureScaler.from_state_dict(sd)
        np.testing.assert_array_almost_equal(scaler.mean_, scaler2.mean_)
        np.testing.assert_array_almost_equal(scaler.std_, scaler2.std_)

    def test_state_dict_rejects_non_finite_statistics(self):
        with pytest.raises(ValueError, match="non finis"):
            FeatureScaler.from_state_dict(
                {
                    "mean": [float("nan")] * len(FEATURE_COLUMNS),
                    "std": [1.0] * len(FEATURE_COLUMNS),
                    "features": list(FEATURE_COLUMNS),
                }
            )


class TestBuildSequences:
    def test_shape(self):
        features = np.random.randn(100, 5).astype(np.float32)
        targets = np.random.choice([0.0, 1.0], size=100)
        X, y = build_sequences(features, targets, seq_len=10)
        assert X.shape[1] == 10
        assert X.shape[2] == 5
        assert len(X) == len(y)

    def test_nan_targets_excluded(self):
        features = np.random.randn(50, 3).astype(np.float32)
        targets = np.full(50, np.nan)
        X, y = build_sequences(features, targets, seq_len=10)
        assert len(X) == 0


class TestSequenceDataset:
    def test_getitem(self):
        X = np.random.randn(20, 10, 5).astype(np.float32)
        y = np.random.choice([0.0, 1.0], size=20).astype(np.float32)
        ds = SequenceDataset(X, y)
        assert len(ds) == 20
        x_i, y_i = ds[0]
        assert x_i.shape == (10, 5)
        assert y_i.dtype == torch.long


# ===========================================================================
# Model tests
# ===========================================================================

class TestTemporalAttention:
    def test_weights_sum_to_one(self):
        attn = TemporalAttention(hidden_size=32)
        x = torch.randn(4, 10, 32)
        context, weights = attn(x)
        assert context.shape == (4, 32)
        assert weights.shape == (4, 10)
        sums = weights.sum(dim=1)
        torch.testing.assert_close(sums, torch.ones(4), atol=1e-5, rtol=1e-5)


class TestLSTMAttentionClassifier:
    def test_forward_shape(self):
        model = LSTMAttentionClassifier(input_size=13, hidden_size=32, num_layers=1, dropout=0.0, num_classes=2)
        x = torch.randn(8, 60, 13)
        logits, attn_w = model(x)
        assert logits.shape == (8, 2)
        assert attn_w.shape == (8, 60)


class TestLSTMAttentionModule:
    def test_training_step(self):
        model = LSTMAttentionModule(input_size=5, hidden_size=16, num_layers=1, dropout=0.0)
        x = torch.randn(4, 10, 5)
        y = torch.randint(0, 2, (4,))
        loss = model.training_step((x, y), 0)
        assert loss.shape == ()
        assert loss.item() > 0


# ===========================================================================
# DB Registry tests (mocked)
# ===========================================================================

class TestDbRegistry:
    def test_load_candidate_symbols(self):
        from modelFactory.db_registry import load_candidate_symbols
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.scalars.return_value.all.return_value = ["AAPL", "MSFT"]
        result = load_candidate_symbols(mock_engine)
        assert result == ["AAPL", "MSFT"]

    def test_insert_predictions_empty(self):
        from modelFactory.db_registry import insert_predictions
        mock_engine = MagicMock()
        n = insert_predictions(mock_engine, pd.DataFrame())
        assert n == 0


# ===========================================================================
# CLI test
# ===========================================================================

class TestCli:
    def test_build_arg_parser(self):
        from modelFactory.cli import build_arg_parser
        parser = build_arg_parser()
        args = parser.parse_args(["--mode", "train", "--max-workers", "2"])
        assert args.mode == "train"
        assert args.max_workers == 2


# ===========================================================================
# Integration-like: full pipeline on synthetic data (no DB, no GPU)
# ===========================================================================

class TestEndToEndSynthetic:
    def test_datamodule_setup(self):
        """Test the full DataModule setup pipeline on synthetic bars."""
        bars = _make_bars(600)
        data_cfg = DataConfig(sequence_length=20, forecast_horizon=5, min_history_days=100)
        model_cfg = ModelConfig(batch_size=16)
        from modelFactory.dataset import SymbolDataModule
        dm = SymbolDataModule(bars, data_cfg, model_cfg)
        dm.setup()
        assert dm.train_ds is not None
        assert dm.val_ds is not None
        assert len(dm.train_ds) > 0
        assert len(dm.val_ds) > 0
        # Check shapes
        x, y = dm.train_ds[0]
        assert x.shape == (20, len(FEATURE_COLUMNS))

    def test_datamodule_with_sentiment(self):
        """Test DataModule avec features sentiment activées."""
        bars = _make_bars(600)
        sent = _make_sentiment(bars)
        data_cfg = DataConfig(sequence_length=20, forecast_horizon=5,
                              min_history_days=100, include_sentiment_features=True)
        model_cfg = ModelConfig(batch_size=16)
        from modelFactory.dataset import SymbolDataModule
        dm = SymbolDataModule(bars, data_cfg, model_cfg, sentiment_df=sent)
        dm.setup()
        assert dm.train_ds is not None
        expected_features = len(FEATURE_COLUMNS) + len(SENTIMENT_FEATURE_COLUMNS)
        assert dm.n_features == expected_features
        x, y = dm.train_ds[0]
        assert x.shape == (20, expected_features)
        # Scaler state_dict must include sentiment feature names
        sd = dm.scaler.state_dict()
        assert len(sd["features"]) == expected_features

    def test_datamodule_without_sentiment_unchanged(self):
        """Sans flag sentiment, le comportement reste identique."""
        bars = _make_bars(600)
        data_cfg = DataConfig(sequence_length=20, forecast_horizon=5, min_history_days=100)
        model_cfg = ModelConfig(batch_size=16)
        from modelFactory.dataset import SymbolDataModule
        dm = SymbolDataModule(bars, data_cfg, model_cfg)
        dm.setup()
        assert dm.n_features == len(FEATURE_COLUMNS)
        x, _ = dm.train_ds[0]
        assert x.shape == (20, len(FEATURE_COLUMNS))


class TestGpuExecutionBehavior:
    def test_datamodule_enables_pin_memory_when_cuda_available(self, monkeypatch):
        monkeypatch.setattr("modelFactory.dataset.torch.cuda.is_available", lambda: True)
        from modelFactory.dataset import SymbolDataModule

        bars = _make_bars(600)
        dm = SymbolDataModule(bars, DataConfig(sequence_length=20, forecast_horizon=5, min_history_days=100), ModelConfig(batch_size=16))
        dm.setup()

        assert dm.train_dataloader().pin_memory is True

    def test_datamodule_forces_num_workers_zero_on_windows_with_cuda(self, monkeypatch):
        monkeypatch.setattr("modelFactory.dataset.torch.cuda.is_available", lambda: True)
        monkeypatch.setattr("modelFactory.dataset.os.name", "nt")
        from modelFactory.dataset import SymbolDataModule

        bars = _make_bars(600)
        dm = SymbolDataModule(bars, DataConfig(sequence_length=20, forecast_horizon=5, min_history_days=100), ModelConfig(batch_size=16))
        dm.setup()

        train_loader = dm.train_dataloader()
        assert train_loader.num_workers == 0
        assert train_loader.pin_memory is True

    def test_orchestrator_runs_sequentially_when_gpu_available_in_auto_mode(self, monkeypatch):
        from modelFactory.orchestrator import run_training_batch

        cfg = TrainingConfig(max_workers=4, accelerator="auto")
        engine = MagicMock()
        train_calls: list[str] = []

        def fake_train_worker(symbol: str, _cfg: TrainingConfig):
            train_calls.append(symbol)
            return SimpleResult(symbol)

        @dataclass
        class SimpleResult:
            symbol: str
            run_id: str = "run"
            status: str = "completed"
            metrics: dict | None = None
            skip_reason: str | None = None

        monkeypatch.setattr("modelFactory.orchestrator.torch.cuda.is_available", lambda: True)
        monkeypatch.setattr("modelFactory.orchestrator.load_candidate_symbols", lambda _engine: ["AAPL", "MSFT"])
        monkeypatch.setattr("modelFactory.orchestrator._train_worker", fake_train_worker)

        results = run_training_batch(cfg, engine)

        assert train_calls == ["AAPL", "MSFT"]
        assert [r.symbol for r in results] == ["AAPL", "MSFT"]


class TestPredictorDeviceResolution:
    def test_predictor_device_cpu_when_requested(self):
        from modelFactory.predictor import _resolve_inference_device

        assert _resolve_inference_device("cpu").type == "cpu"

    def test_predictor_device_auto_uses_cuda_when_available(self, monkeypatch):
        from modelFactory.predictor import _resolve_inference_device

        monkeypatch.setattr("modelFactory.predictor.torch.cuda.is_available", lambda: True)
        assert _resolve_inference_device("auto").type == "cuda"

    def test_predictor_device_gpu_falls_back_to_cpu_when_unavailable(self, monkeypatch):
        from modelFactory.predictor import _resolve_inference_device

        monkeypatch.setattr("modelFactory.predictor.torch.cuda.is_available", lambda: False)
        assert _resolve_inference_device("gpu").type == "cpu"

    def test_predictor_latest_feature_date_must_match_cutoff(self):
        from modelFactory.predictor import _has_matching_latest_feature_date

        df = pd.DataFrame({"date": pd.to_datetime(["2020-01-07", "2020-01-08"])})

        assert _has_matching_latest_feature_date(df, date(2020, 1, 8)) is True
        assert _has_matching_latest_feature_date(df, date(2020, 1, 9)) is False


