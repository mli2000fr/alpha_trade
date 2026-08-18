"""Tests anti-leakage Oracle Layer — Sprint S0 (§27).

Couvre (cf. doc/ml_oracle.md §27) :
- T1 : ``oracle_available_date > prediction_date`` pour toutes les observations ;
- T3 : aucune feature issue de D+1 ou plus (garde structurelle S0) ;
- T4 : ``oracle_rank/decile/future_return/...`` jamais dans les features ;
- T2 / T5 : stubs marqués skip — câblés en S4 (walk-forward).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modelFactory.oracle.leakage import (
    FORBIDDEN_ORACLE_FEATURES,
    assert_availability_after_prediction,
    assert_no_forbidden_features,
    assert_no_future_features,
    assert_no_future_oracle_read,
    assert_training_cutoff_valid,
)


# ═══════════════════════════════════════════════════════════════════
# T1 — oracle_available_date > prediction_date
# ═══════════════════════════════════════════════════════════════════

class TestAvailabilityAfterPrediction:
    def test_ok_when_available_after_prediction(self):
        df = pd.DataFrame({
            "prediction_date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
            "oracle_exit_date": pd.to_datetime(["2022-01-31", "2022-02-01"]),
            "oracle_available_date": pd.to_datetime(["2022-02-01", "2022-02-02"]),
        })
        assert_availability_after_prediction(df)  # ne doit pas lever

    def test_raises_when_available_not_after_prediction(self):
        df = pd.DataFrame({
            "prediction_date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
            "oracle_exit_date": pd.to_datetime(["2022-01-31", "2022-02-01"]),
            "oracle_available_date": pd.to_datetime(["2022-02-01", "2022-01-04"]),
        })
        with pytest.raises(ValueError, match="T1"):
            assert_availability_after_prediction(df)

    def test_raises_when_exit_before_prediction(self):
        df = pd.DataFrame({
            "prediction_date": pd.to_datetime(["2022-01-03"]),
            "oracle_exit_date": pd.to_datetime(["2021-12-31"]),
            "oracle_available_date": pd.to_datetime(["2022-02-01"]),
        })
        with pytest.raises(ValueError, match="T1"):
            assert_availability_after_prediction(df)

    def test_raises_when_columns_missing(self):
        with pytest.raises(ValueError, match="T1"):
            assert_availability_after_prediction(pd.DataFrame({"symbol": ["AAPL"]}))

    def test_ok_on_empty(self):
        assert_availability_after_prediction(pd.DataFrame())


# ═══════════════════════════════════════════════════════════════════
# T4 — colonnes Oracle jamais en features
# ═══════════════════════════════════════════════════════════════════

class TestNoForbiddenFeatures:
    def test_ok_on_clean_features(self):
        assert_no_forbidden_features(
            ["momentum_20", "rolling_volatility_20", "volume_ratio_20"]
        )

    @pytest.mark.parametrize("bad_col", sorted(FORBIDDEN_ORACLE_FEATURES))
    def test_raises_on_forbidden_column(self, bad_col):
        with pytest.raises(ValueError, match="T4"):
            assert_no_forbidden_features(["momentum_20", bad_col, "volume_ratio_20"])


# ═══════════════════════════════════════════════════════════════════
# T3 — aucune feature issue de D+1 (garde structurelle S0)
# ═══════════════════════════════════════════════════════════════════

class TestNoFutureFeatures:
    def test_ok_on_clean_features(self):
        assert_no_future_features(["momentum_20", "rolling_volatility_20"])

    @pytest.mark.parametrize(
        "bad_col",
        ["future_return_20", "future_volatility", "next_close", "oracle_rank"],
    )
    def test_raises_on_future_like_feature(self, bad_col):
        with pytest.raises(ValueError, match="T3"):
            assert_no_future_features(["momentum_20", bad_col])


# ═══════════════════════════════════════════════════════════════════
# T2 / T5 — câblés en S4 (walk-forward)
# ═══════════════════════════════════════════════════════════════════

class TestTrainingCutoff:
    def test_ok_when_cutoff_covers_labels(self):
        assert_training_cutoff_valid(
            training_cutoff=date(2022, 1, 1),
            max_oracle_available_date=date(2021, 12, 31),
        )

    def test_raises_on_leakage(self):
        with pytest.raises(ValueError, match="T2"):
            assert_training_cutoff_valid(
                training_cutoff=date(2022, 1, 1),
                max_oracle_available_date=date(2022, 2, 1),
            )

    def test_none_is_noop(self):
        assert_training_cutoff_valid(
            training_cutoff=date(2022, 1, 1),
            max_oracle_available_date=None,
        )


class TestNoFutureOracleRead:
    def test_ok_when_available_before_today(self):
        assert_no_future_oracle_read(
            today=date(2022, 2, 1),
            oracle_available_date=date(2022, 1, 31),
        )

    def test_raises_on_future_label(self):
        with pytest.raises(ValueError, match="T5"):
            assert_no_future_oracle_read(
                today=date(2022, 1, 1),
                oracle_available_date=date(2022, 2, 1),
            )

    def test_none_is_noop(self):
        assert_no_future_oracle_read(today=date(2022, 1, 1), oracle_available_date=None)
