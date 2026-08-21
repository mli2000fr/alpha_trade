"""Tests unitaires Oracle S3 — dataset (ablations) + train (métriques pures)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.dataset import (
    ablation_features,
    expert_feature_columns,
    lean_feature_columns,
)
from modelFactory.oracle.train import (
    decile_monotonicity,
    precision_recall_at_top_pct,
    roc_auc,
)


# ═══════════════════════════════════════════════════════════════════
# dataset — ablations O0/O1/O2
# ═══════════════════════════════════════════════════════════════════

class TestAblationFeatures:
    def test_o0_no_rank_no_extras(self):
        feats = ["momentum_20", "volume_ratio_20", "rolling_volatility_20", "atr_14_norm_xs_rank"]
        cols = ablation_features(feats, include_global_rank=False, include_oracle_extras=False)
        assert cols == feats
        assert "global_rank_20" not in cols
        assert "drawdown_20" not in cols

    def test_o1_adds_rank_and_extras(self):
        feats = ["momentum_20", "volume_ratio_20"]
        cols = ablation_features(feats, include_global_rank=True, include_oracle_extras=True)
        assert "global_rank_20" in cols
        assert "drawdown_20" in cols
        assert "high_low_position_20" in cols
        assert "momentum_20" in cols

    def test_o2_lean_families_only(self):
        feats = ["momentum_20", "rolling_volatility_20", "volume_ratio_20",
                 "rsi_14", "sma20_distance", "atr_14_norm"]
        cols = ablation_features(feats, include_global_rank=False,
                                 include_oracle_extras=False, lean=True)
        # rsi_14 / sma20_distance ne font pas partie des familles réduites
        assert "momentum_20" in cols
        assert "rolling_volatility_20" in cols
        assert "volume_ratio_20" in cols
        assert "atr_14_norm" in cols
        assert "rsi_14" not in cols
        assert "sma20_distance" not in cols

    def test_lean_feature_columns(self):
        feats = ["momentum_20", "rolling_volatility_20", "volume_ratio_20", "rsi_14", "foo"]
        assert lean_feature_columns(feats) == ["momentum_20", "rolling_volatility_20", "volume_ratio_20"]


# ═══════════════════════════════════════════════════════════════════
# train — métriques pures
# ═══════════════════════════════════════════════════════════════════

class TestRocAuc:
    def test_perfect(self):
        auc = roc_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9]))
        assert auc == pytest.approx(1.0)

    def test_random(self):
        auc = roc_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.9, 0.4, 0.6]))
        # scores mal classés → AUC < 1
        assert auc < 1.0

    def test_single_class_is_none(self):
        assert roc_auc(np.array([1, 1, 1]), np.array([0.1, 0.2, 0.3])) is None


class TestPrecisionRecall:
    def test_precision_at_top_pct(self):
        # 10 symboles sur 1 date : 1 vrai top10, score max → précision 1.0
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02"] * 10),
            "oracle_extreme10": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "score": np.arange(10.0, 0.0, -1.0),
        })
        pr = precision_recall_at_top_pct(df, "score", pct=0.10, min_universe=5)
        assert pr["precision"] == pytest.approx(1.0)
        assert pr["recall"] == pytest.approx(1.0)
        assert pr["n_dates"] == 1

    def test_below_min_universe_skipped(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02"] * 5),
            "oracle_extreme10": [1, 0, 0, 0, 0],
            "score": [5.0, 4.0, 3.0, 2.0, 1.0],
        })
        pr = precision_recall_at_top_pct(df, "score", pct=0.10, min_universe=10)
        assert pr["n_dates"] == 0


class TestDecileMonotonicity:
    def test_monotone_increasing(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02"] * 10),
            "score": np.arange(1.0, 11.0),                    # score croissant
            "future_return": np.arange(-0.10, 0.10, 0.02),    # croît avec le score
        })
        mono, _ = decile_monotonicity(df, "score")
        assert mono == pytest.approx(1.0)

    def test_no_relation(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02"] * 10),
            "score": np.arange(10.0, 0.0, -1.0),
            "future_return": [0.0, 0.1, -0.1, 0.05, -0.05, 0.02, -0.02, 0.01, -0.01, 0.0],
        })
        mono, _ = decile_monotonicity(df, "score")
        assert -1.0 <= mono <= 1.0
