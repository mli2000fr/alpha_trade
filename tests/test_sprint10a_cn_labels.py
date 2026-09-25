from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dataIntegrityEngine.cn_sprint10a_audit import audit
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_oracle_labels import CNLabelPolicy, compute_horizon_labels


def _sample() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=12)
    calendar = pd.DataFrame({
        "session_date": dates, "open_at_utc": dates + pd.Timedelta(hours=1),
    })
    candidates = pd.DataFrame({
        "session_date": [dates[1]] * 25,
        "instrument_id": list(range(1, 26)),
        "provider_symbol": [f"sh.{600000 + value}" for value in range(1, 26)],
        "board_code": ["SH_MAIN"] * 25,
        "universe_run_id": ["cn8-test"] * 25,
        "decision_at": [dates[1]] * 25,
    })
    rows = []
    for instrument in range(1, 26):
        for offset, day in enumerate(dates):
            rows.append({
                "instrument_id": instrument, "date": day, "open": 10.0,
                "close": 10 * (1 + instrument * offset / 1000),
                "pre_close": 10 * (1 + instrument * max(offset - 1, 0) / 1000),
                "volume": 1000, "daily_return": instrument / 1000,
                "trading_status": "TRADE", "available_at": day + pd.Timedelta(hours=8),
                "limit_policy": "CN_MAIN_10PCT_V1", "locked_up": 0, "locked_down": 0,
                "factor_event": 0, "factor_value": np.nan,
                "previous_factor_value": np.nan, "factor_available_at": pd.NaT,
            })
    bars = pd.DataFrame(rows)
    return candidates, bars, calendar


def test_cn_label_policy_refuses_other_market_or_horizons(tmp_path: Path) -> None:
    path = tmp_path / "labels_cn.yaml"
    original = (Path(__file__).resolve().parents[1] / "config" / "labels_cn.yaml").read_text(encoding="utf-8")
    assert CNLabelPolicy.from_yaml(Path(__file__).resolve().parents[1] / "config" / "labels_cn.yaml").horizons == (5, 10, 15, 20)
    path.write_text(original.replace("market_code: CN_A", "market_code: US"), encoding="utf-8")
    with pytest.raises(ValueError, match="contrat|Contrat"):
        CNLabelPolicy.from_yaml(path)


def test_labels_are_future_available_and_ranked_intra_date() -> None:
    candidates, bars, calendar = _sample()
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    assert len(labels) == 25
    assert labels["target_quality_valid"].all()
    assert labels["available_date"].eq(calendar["session_date"].iloc[7]).all()
    assert labels["exit_date"].eq(calendar["session_date"].iloc[6]).all()
    assert labels["oracle_decile"].min() == 1
    assert labels["oracle_decile"].max() == 10
    assert labels["oracle_extreme20"].sum() >= 4
    assert labels["rank_universe_count"].eq(25).all()
    assert labels["market_code"].eq("CN_A").all()


def test_quality_quarantines_missing_suspended_factor_and_late_revision() -> None:
    candidates, bars, calendar = _sample()
    day3, day4, day5 = calendar["session_date"].iloc[[3, 4, 5]]
    bars = bars.loc[~(bars["instrument_id"].eq(4) & bars["date"].eq(day3))].copy()
    bars.loc[bars["instrument_id"].eq(2) & bars["date"].eq(day4), "trading_status"] = "SUSPENDED"
    bars.loc[bars["instrument_id"].eq(3) & bars["date"].eq(day5), "factor_event"] = 1
    bars.loc[bars["instrument_id"].eq(5) & bars["date"].eq(day4), "available_at"] = pd.Timestamp("2025-01-01")
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    reasons = labels.set_index("instrument_id")["target_quality_reason"]
    assert reasons.loc[2] == "SUSPENDED_OR_STATUS_CONFLICT"
    assert reasons.loc[3] == "UNVERIFIED_FACTOR_ADJUSTMENT"
    assert reasons.loc[4] == "MISSING_PATH_BAR"
    assert reasons.loc[5] == "SOURCE_AFTER_LABEL_AVAILABILITY"
    assert labels["target_quality_valid"].sum() == 21
    assert labels.loc[~labels["target_quality_valid"], "oracle_decile"].isna().all()
    assert labels.loc[labels["target_quality_valid"], "rank_universe_count"].eq(21).all()


def test_limit_locked_is_not_removed_from_price_deciles() -> None:
    candidates, bars, calendar = _sample()
    bars.loc[
        bars["instrument_id"].eq(1) & bars["date"].eq(calendar["session_date"].iloc[1]),
        "locked_up",
    ] = 1
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    row = labels.set_index("instrument_id").loc[1]
    assert bool(row["target_quality_valid"])
    assert pd.notna(row["oracle_decile"])
    assert bool(row["entry_limit_locked"])
    assert not bool(row["execution_data_eligible"])


def test_verified_adjustment_stays_in_price_deciles() -> None:
    candidates, bars, calendar = _sample()
    event_day = calendar["session_date"].iloc[5]
    mask = bars["instrument_id"].eq(6) & bars["date"].eq(event_day)
    prior_close = bars.loc[bars["instrument_id"].eq(6) & bars["date"].eq(calendar["session_date"].iloc[4]), "close"].iloc[0]
    bars.loc[mask, "factor_event"] = 1
    bars.loc[mask, "factor_value"] = 1.02
    bars.loc[mask, "previous_factor_value"] = 1.0
    bars.loc[mask, "pre_close"] = prior_close / 1.02
    bars.loc[mask, "daily_return"] = bars.loc[mask, "close"] / bars.loc[mask, "pre_close"] - 1
    bars.loc[mask, "factor_available_at"] = event_day + pd.Timedelta(hours=8)
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    row = labels.set_index("instrument_id").loc[6]
    assert bool(row["target_quality_valid"])
    assert bool(row["path_factor_event"])
    assert not bool(row["path_factor_unverified"])
    assert pd.notna(row["oracle_decile"])


def test_tail_without_exit_or_availability_is_quarantined() -> None:
    candidates, bars, calendar = _sample()
    candidates["session_date"] = calendar["session_date"].iloc[9]
    candidates["decision_at"] = calendar["session_date"].iloc[9]
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    assert not labels["target_quality_valid"].any()
    assert labels["target_quality_reason"].eq("FUTURE_HORIZON_UNAVAILABLE").all()


def test_small_cross_section_cannot_receive_deciles() -> None:
    candidates, bars, calendar = _sample()
    candidates = candidates.head(19)
    labels = compute_horizon_labels(candidates, bars, calendar, horizon=5)
    assert labels["target_quality_reason"].eq("INSUFFICIENT_RANK_UNIVERSE").all()
    assert labels["oracle_decile"].isna().all()


def test_annual_audit_detects_early_label_availability(tmp_path: Path) -> None:
    folder = tmp_path / "cn_oracle_labels_v1" / "cn-labels-20200101-20201231-test"
    folder.mkdir(parents=True)
    implementation_sha = hashlib.sha256((ROOT / "modelFactory" / "cn_oracle_labels.py").read_bytes()).hexdigest()
    frame = pd.DataFrame({
        "market_code": ["CN_A"] * 20,
        "session_date": [pd.Timestamp("2020-01-02")] * 20,
        "instrument_id": range(1, 21),
        "decision_at": [pd.Timestamp("2020-01-02")] * 20,
        "exit_date": [pd.Timestamp("2020-01-09")] * 20,
        "available_date": [pd.Timestamp("2020-01-10")] * 20,
        "available_at_utc": [pd.Timestamp("2020-01-10 01:00")] * 20,
        "target_quality_valid": [True] * 20,
        "target_quality_reason": ["OK"] * 20,
        "rank_universe_count": [20] * 20,
        "oracle_decile": list(range(1, 11)) * 2,
        "oracle_extreme20": [value in (1, 10) for value in list(range(1, 11)) * 2],
        "path_limit_locked": [False] * 20,
        "execution_data_eligible": [True] * 20,
    })
    horizons = {}
    for horizon in (5, 10, 15, 20):
        path = folder / f"h{horizon}.parquet"
        frame.to_parquet(path, index=False)
        horizons[str(horizon)] = {"rows": 20, "panel_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    report = {"implementation_sha256": implementation_sha, "candidate_rows": 20,
              "feature_panel_sha256": "source", "horizons": horizons}
    report_path = folder / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    assert audit(tmp_path, start_year=2020, end_year=2020)["status"] == "PASS_LABELS_PRICE_ONLY"
    frame["available_date"] = pd.Timestamp("2020-01-08")
    path = folder / "h5.parquet"
    frame.to_parquet(path, index=False)
    report["horizons"]["5"]["panel_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report_path.write_text(json.dumps(report), encoding="utf-8")
    assert audit(tmp_path, start_year=2020, end_year=2020)["status"] == "INCOMPLETE_OR_FAILED"
