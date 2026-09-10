from __future__ import annotations

import gzip
import json

import pandas as pd

from modelFactory.directional_data_research.harness import analyze_features
from modelFactory.global_direction.dataset import DECILE_COL
from modelFactory.directional_data_research.eroya_features import (
    build_form4_features,
    build_event_features,
    evaluate_form4_signed_rules,
    load_form4_events,
    load_analyst_insights,
    merge_asof_by_symbol,
)
from modelFactory.directional_data_research.eroya_earnings_features import (
    build_earnings_features,
    load_earnings_events,
)


def test_short_volume_merge_never_uses_same_day_value() -> None:
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                         "symbol": ["AAA", "AAA"]})
    features = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"]),
                             "symbol": ["AAA"], "signal": [0.7]})
    result = merge_asof_by_symbol(pool, features, right_date="date", allow_exact=False)
    assert pd.isna(result.loc[result["date"] == pd.Timestamp("2025-01-02"), "signal"]).all()
    assert result.loc[result["date"] == pd.Timestamp("2025-01-03"), "signal"].iloc[0] == 0.7


def test_event_features_apply_only_from_available_date() -> None:
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                         "symbol": ["AAA", "AAA"]})
    events = pd.DataFrame({"symbol": ["AAA"],
                           "available_date": pd.to_datetime(["2025-01-03"]),
                           "signed": [1.0]})
    result = build_event_features(pool, events, prefix="analyst")
    assert result["analyst_signed_30d"].tolist() == [0.0, 1.0]
    assert pd.isna(result["analyst_days_since"].iloc[0])
    assert result["analyst_days_since"].iloc[1] == 0.0


def test_harness_reports_each_fold_ic_in_its_own_column() -> None:
    frame = pd.DataFrame({
        DECILE_COL: [1, 2, 9, 10, 1, 2, 9, 10],
        "signal": [1.0, 2.0, 9.0, 10.0, 10.0, 9.0, 2.0, 1.0],
        "fold_start": ["2022"] * 4 + ["2023"] * 4,
    })
    result = analyze_features(frame, ["signal"]).iloc[0]
    assert result["IC_2022"] > 0.9
    assert result["IC_2023"] < -0.9
    assert result["stabilite_signes_folds"] == "NON"


def test_analyst_insights_strict_mode_uses_last_updated(tmp_path) -> None:
    path = tmp_path / "insights.jsonl.gz"
    document = {"symbol_requested": "AAA", "payload": {"results": [{
        "ticker": "AAA", "firm": "Bank", "date": "2020-01-02",
        "last_updated": "2024-10-25T09:21:17Z", "rating_action": "upgrades",
        "rating": "buy", "price_target": 42.0,
    }]}}
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(document) + "\n")
    strict = load_analyst_insights(path, strict=True).iloc[0]
    sensitivity = load_analyst_insights(path, strict=False).iloc[0]
    assert strict["available_date"] == pd.Timestamp("2024-10-25")
    assert strict["signed"] == 1.0
    assert strict["rating_signed"] == 1.0
    assert sensitivity["available_date"] == pd.Timestamp("2020-01-03")


def test_form4_loader_keeps_only_market_purchase_and_sale_and_uses_next_day(tmp_path) -> None:
    path = tmp_path / "form4.jsonl.gz"
    common = {
        "accession_number": "A1", "owner_cik": "O1", "security_title": "Common",
        "direct_or_indirect": "D", "transaction_date": "2025-01-02",
        "filing_date": "2025-01-03", "transaction_shares": 10,
        "transaction_price_per_share": 20, "transaction_acquired_disposed": "A",
        "is_officer": True,
    }
    rows = [
        {**common, "transaction_code": "P", "transaction_value": 200},
        {**common, "transaction_code": "P", "transaction_value": 200},
        {**common, "accession_number": "A2", "transaction_code": "S",
         "transaction_acquired_disposed": "D", "aff_10b5_one": True},
        {**common, "accession_number": "A3", "transaction_code": "A"},
    ]
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"symbol_requested": "AAA", "payload": {"results": rows}}) + "\n")
    result = load_form4_events(path)
    assert result["transaction_code"].tolist() == ["P", "S"]
    assert result["signed"].tolist() == [1.0, -1.0]
    assert result["available_date"].eq(pd.Timestamp("2025-01-06")).all()
    assert result["signed_value"].tolist() == [200.0, -200.0]


def test_form4_features_never_use_filing_day_and_separate_10b5() -> None:
    pool = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07"]),
        "symbol": ["AAA", "AAA", "AAA"],
    })
    events = pd.DataFrame({
        "symbol": ["AAA", "AAA"],
        "available_date": pd.to_datetime(["2025-01-06", "2025-01-07"]),
        "transaction_code": ["P", "S"], "signed": [1.0, -1.0],
        "value": [100.0, 25.0], "signed_value": [100.0, -25.0],
        "aff_10b5_one": [False, True], "is_officer": [True, False],
        "is_director": [False, True],
    })
    result = build_form4_features(pool, events)
    assert result["eroya_form4_net_count_90d"].tolist() == [0.0, 1.0, 0.0]
    assert result["eroya_form4_net_value_90d"].tolist() == [0.0, 100.0, 75.0]
    assert result["eroya_form4_net_count_90d_no10b5"].tolist() == [0.0, 1.0, 1.0]


def test_form4_signed_rules_exclude_zero_ties() -> None:
    frame = pd.DataFrame({
        "fold_start": ["2024"] * 4,
        DECILE_COL: [10, 1, 5, 6],
        "future_return": [0.10, -0.08, 0.0, 0.01],
        "eroya_form4_net_count_90d": [1, -1, 0, 0],
        "eroya_form4_net_value_90d": [100, -100, 0, 0],
        "eroya_form4_net_count_90d_no10b5": [1, -1, 0, 0],
        "eroya_form4_net_value_90d_no10b5": [100, -100, 0, 0],
        "eroya_form4_officer_net_count_90d": [1, -1, 0, 0],
        "eroya_form4_director_net_count_90d": [1, -1, 0, 0],
        "eroya_form4_buy_count_90d": [1, 0, 0, 0],
        "eroya_form4_sell_count_90d": [0, 1, 0, 0],
    })
    result = evaluate_form4_signed_rules(frame)
    overall = result[(result["fold"] == "ALL") &
                     (result["rule"] == "net_count_90d")]
    assert overall.set_index("side")["n"].to_dict() == {"LONG": 1, "SHORT": 1}
    assert (overall["pnl_lift"] > 0).all()


def test_earnings_are_available_only_on_next_business_day(tmp_path) -> None:
    path = tmp_path / "earnings.jsonl.gz"
    document = {"symbol_requested": "AAA", "payload": {"results": {
        "events": [{"earningsDate": "2025-01-02T12:00:00Z", "eventType": "Earnings",
                    "epsEstimate": 1.0, "epsActual": 1.2, "surprisePercent": 20.0}]}}}
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(document) + "\n")
    events = load_earnings_events(path)
    assert events["available_date"].iloc[0] == pd.Timestamp("2025-01-03")
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                         "symbol": ["AAA", "AAA"]})
    result = build_earnings_features(pool, events)
    assert pd.isna(result["eroya_earnings_surprise_pct"].iloc[0])
    assert result["eroya_earnings_surprise_pct"].iloc[1] == 20.0


def test_earnings_friday_becomes_available_monday(tmp_path) -> None:
    path = tmp_path / "earnings.jsonl.gz"
    document = {"symbol_requested": "AAA", "payload": {"results": {
        "events": [{"earningsDate": "2025-01-03T21:05:00Z",
                    "eventType": "Earnings", "surprisePercent": -10.0}]}}}
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(document) + "\n")
    events = load_earnings_events(path)
    assert events["available_date"].iloc[0] == pd.Timestamp("2025-01-06")
