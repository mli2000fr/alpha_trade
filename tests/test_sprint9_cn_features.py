from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dataIntegrityEngine.cn_sprint9_audit import audit
from modelFactory.cn_feature_panel import (
    CNFeatureProfile,
    assemble_candidate_panel,
    compute_symbol_features,
)

PROFILE = CNFeatureProfile(
    benchmark_provider_symbol="sh.000300",
    sector_taxonomy="SW_2021",
    sector_membership_mode="missing_until_pit_source",
    price_adjustment_mode="raw_with_factor_event_masks",
    warmup_sessions=252,
    min_cross_section=2,
)


def _bars(count: int = 270) -> pd.DataFrame:
    days = pd.bdate_range("2023-01-02", periods=count)
    close = 10.0 * 1.01 ** np.arange(count)
    return pd.DataFrame({
        "instrument_id": 1, "date": days, "open": close * 0.995,
        "high": close * 1.01, "low": close * 0.99, "close": close,
        "pre_close": close / 1.01, "volume": 1000.0,
        "amount": close * 1000.0, "daily_return": 0.01,
        "trading_status": "TRADE", "is_special_treatment": False,
        "available_at": days + pd.Timedelta(hours=9),
    })


@pytest.mark.parametrize("market,sector_mode", [
    ("US", "missing_until_pit_source"),
    ("CN_A", "impute_current"),
])
def test_cn_profile_rejects_us_or_imputed_sector(tmp_path: Path, market: str, sector_mode: str) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        f"profile: cn_price_v1\nmarket_code: {market}\ndatabase_alias: cn_primary\n"
        "return_horizons: [1, 3, 5, 10, 20, 60]\n"
        f"sector_membership_mode: {sector_mode}\n"
        "price_adjustment_mode: raw_with_factor_event_masks\n"
        "benchmark_provider_symbol: sh.000300\nsector_taxonomy: SW_2021\n"
        "warmup_sessions: 252\nmin_cross_section: 20\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        CNFeatureProfile.from_yaml(profile)


def test_symbol_features_are_backward_only() -> None:
    bars = _bars()
    before = compute_symbol_features(bars)
    after_bars = pd.concat([bars, bars.tail(1).assign(
        date=bars["date"].iloc[-1] + pd.Timedelta(days=1), close=999999.0,
        daily_return=100.0,
    )], ignore_index=True)
    after = compute_symbol_features(after_bars)
    for feature in ("return_20", "sma20_distance", "atr20_pct", "position_52w"):
        pd.testing.assert_series_equal(before[feature], after.iloc[:len(before)][feature], check_names=False)
    assert before["return_20"].iloc[-1] == pytest.approx(1.01 ** 20 - 1)


def test_factor_event_masks_raw_price_indicators() -> None:
    bars = _bars()
    factors = pd.DataFrame({"instrument_id": [1], "date": [bars["date"].iloc[-5]],
                            "available_at": [bars["date"].iloc[-5]]})
    features = compute_symbol_features(bars, factors)
    assert pd.isna(features["sma20_distance"].iloc[-1])
    assert pd.isna(features["position_52w"].iloc[-1])
    assert features["factor_event_recent20"].iloc[-1] == 1
    assert pd.notna(features["return_20"].iloc[-1])


def test_st_flag_comes_from_canonical_column() -> None:
    bars = _bars()
    bars.loc[bars.index[-1], "is_special_treatment"] = True
    assert compute_symbol_features(bars)["prior_st"].iloc[-1] == 1


def test_candidate_panel_uses_previous_session_and_masks_sector() -> None:
    day = pd.Timestamp("2024-01-10")
    prior = day - pd.Timedelta(days=1)
    decision = day + pd.Timedelta(hours=1)
    candidates = pd.DataFrame({
        "instrument_id": [1, 2], "provider_symbol": ["sh.600000", "sz.300001"],
        "session_date": [day] * 2, "asof_date": [prior] * 2,
        "decision_at": [decision] * 2, "source_available_at": [prior] * 2,
    })
    features = pd.DataFrame({
        "instrument_id": [1, 2], "date": [prior] * 2,
        "available_at": [prior] * 2, "max_input_available_at": [prior] * 2,
        "return_1": [0.01, -0.02],
        "return_20": [0.2, -0.1], "realized_vol20": [0.2, 0.4],
        "atr20_pct": [0.03, 0.06],
    })
    benchmark = pd.DataFrame({"date": [prior], "available_at": [prior],
                              "max_input_available_at": [prior],
                              "return_20": [0.05], "realized_vol20": [0.1]})
    result = assemble_candidate_panel(candidates, features, benchmark, pd.DataFrame(), profile=PROFILE)
    assert result["market_code"].eq("CN_A").all()
    assert result["sector_code"].isna().all()
    assert result["mask_sector"].eq(0).all()
    assert result["relative_return_20"].tolist() == pytest.approx([0.15, -0.15])
    assert result["cn_return20_rank"].tolist() == pytest.approx([1.0, 0.5])
    assert result["board_code"].tolist() == ["SH_MAIN", "CHINEXT"]


@pytest.mark.parametrize("field,value", [
    ("asof_date", pd.Timestamp("2024-01-10")),
    ("source_available_at", pd.Timestamp("2024-01-10 02:00:00")),
])
def test_candidate_panel_rejects_future_universe_information(field: str, value: pd.Timestamp) -> None:
    day = pd.Timestamp("2024-01-10")
    candidates = pd.DataFrame({
        "instrument_id": [1], "provider_symbol": ["sh.600000"],
        "session_date": [day], "asof_date": [day - pd.Timedelta(days=1)],
        "decision_at": [day + pd.Timedelta(hours=1)],
        "source_available_at": [day - pd.Timedelta(days=1)],
    })
    candidates[field] = value
    with pytest.raises(ValueError, match="PIT"):
        assemble_candidate_panel(candidates, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), profile=PROFILE)


def test_candidate_panel_rejects_late_bar() -> None:
    day = pd.Timestamp("2024-01-10")
    prior = day - pd.Timedelta(days=1)
    candidates = pd.DataFrame({
        "instrument_id": [1], "provider_symbol": ["sh.600000"],
        "session_date": [day], "asof_date": [prior],
        "decision_at": [day + pd.Timedelta(hours=1)], "source_available_at": [prior],
    })
    features = pd.DataFrame({"instrument_id": [1], "date": [prior],
                             "available_at": [day + pd.Timedelta(hours=2)],
                             "max_input_available_at": [day + pd.Timedelta(hours=2)]})
    with pytest.raises(ValueError, match="après la décision"):
        assemble_candidate_panel(candidates, features, pd.DataFrame(), pd.DataFrame(), profile=PROFILE)


def test_candidate_panel_rejects_late_historical_correction() -> None:
    day = pd.Timestamp("2024-01-10")
    prior = day - pd.Timedelta(days=1)
    candidates = pd.DataFrame({
        "instrument_id": [1], "provider_symbol": ["sh.600000"],
        "session_date": [day], "asof_date": [prior],
        "decision_at": [day + pd.Timedelta(hours=1)], "source_available_at": [prior],
    })
    features = pd.DataFrame({
        "instrument_id": [1], "date": [prior], "available_at": [prior],
        "max_input_available_at": [day + pd.Timedelta(hours=2)],
    })
    with pytest.raises(ValueError, match="après la décision"):
        assemble_candidate_panel(candidates, features, pd.DataFrame(), pd.DataFrame(), profile=PROFILE)


def test_annual_audit_checks_panel_checksum(tmp_path: Path) -> None:
    from modelFactory.cn_feature_panel import ROOT

    implementation_sha = hashlib.sha256((ROOT / "modelFactory" / "cn_feature_panel.py").read_bytes()).hexdigest()
    directory = tmp_path / "cn_price_v1" / "cn-feature-20200101-20201231-test"
    directory.mkdir(parents=True)
    panel = directory / "panel.parquet"
    panel.write_bytes(b"test-panel")
    report = {
        "implementation_sha256": implementation_sha,
        "panel_sha256": hashlib.sha256(panel.read_bytes()).hexdigest(),
        "feature_schema_fingerprint": "schema-v1",
        "rows": 1, "sessions": 1, "instruments": 1,
        "quality": {"duplicate_keys": 0, "late_source_rows": 0,
                    "research_ready_price_only": True,
                    "price20_coverage": 1.0, "benchmark_coverage": 1.0},
        "missing_fraction": {"position_52w": 0.0},
        "sector_membership_coverage": 0.0,
        "board_counts": {"SH_MAIN": 1},
    }
    (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")
    assert audit(tmp_path, start_year=2020, end_year=2020)["status"] == "PASS_PRICE_ONLY"
    panel.write_bytes(b"tampered")
    assert audit(tmp_path, start_year=2020, end_year=2020)["status"] == "INCOMPLETE_OR_FAILED"
