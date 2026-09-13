from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.options_acquisition_cost_audit import (
    AcquisitionAssumptions,
    build_report,
    estimate_collection,
    load_oracle_population,
)


def test_load_population_uses_mh0_and_period(tmp_path) -> None:
    path = tmp_path / "oracle.parquet"
    pd.DataFrame({
        "date": ["2022-03-06", "2022-03-07", "2022-03-07"],
        "symbol": ["OLD", "TOP", "REST"],
        "mh0": [True, True, False],
    }).to_parquet(path, index=False)
    result = load_oracle_population(path, start_date="2022-03-07")
    assert result["symbol"].tolist() == ["TOP"]


def test_load_population_falls_back_to_h20_percentile(tmp_path) -> None:
    path = tmp_path / "oracle.parquet"
    pd.DataFrame({
        "date": ["2024-01-02", "2024-01-02"],
        "symbol": ["TOP", "REST"], "pct_h20": [0.8, 0.799],
    }).to_parquet(path, index=False)
    result = load_oracle_population(path, start_date="2024-01-01")
    assert result["symbol"].tolist() == ["TOP"]


def test_estimate_single_pair_request_math() -> None:
    assumptions = AcquisitionAssumptions(retry_overhead_rate=0.15)
    result = estimate_collection(
        100, quote_requests_per_event=10, assumptions=assumptions,
    )
    assert result["contract_reference_requests"] == 100
    assert result["quote_requests"] == 1000
    assert result["base_requests"] == 1100
    assert result["attempted_requests_with_retry_budget"] == 1265
    assert result["projected_complete_events_at_observed_rate"] == 51


def test_report_spreads_pilot_dates_and_uses_latest_dates_for_gate() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        "symbol": ["A", "B", "C"],
    })
    report = build_report(
        frame, source_path="oracle.parquet",  # type: ignore[arg-type]
        assumptions=AcquisitionAssumptions(minimum_dates=3, pilot_dates=2),
    )
    assert report["estimates"]["pilot"]["population"]["date_start"] == "2024-01-02"
    assert report["estimates"]["pilot"]["population"]["date_end"] == "2024-01-04"
    assert report["estimates"]["minimum_504_dates"]["population"]["events"] == 3
    assert report["decision"]["purchase_or_download_performed"] is False


def test_not_enough_dates_is_blocking() -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-02"]), "symbol": ["A"]})
    with pytest.raises(ValueError, match="dates disponibles"):
        build_report(
            frame, source_path="oracle.parquet",  # type: ignore[arg-type]
            assumptions=AcquisitionAssumptions(minimum_dates=2, pilot_dates=1),
        )
