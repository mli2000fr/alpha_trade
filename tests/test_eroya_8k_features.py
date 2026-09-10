from __future__ import annotations

import gzip
import json

import pandas as pd

from modelFactory.directional_data_research.eroya_8k_features import (
    build_8k_count_features, load_8k_disclosures,
)


def test_8k_loader_deduplicates_cross_request_and_uses_next_business_day(tmp_path) -> None:
    path = tmp_path / "8k.jsonl.gz"
    item = {"tickers": ["AAA"], "accession_number": "A1",
            "filing_date": "2025-01-03", "primary_category": "risk_events",
            "secondary_category": "financial_integrity",
            "tertiary_category": "financial_restatement", "supporting_text": "x"}
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for requested in ("AAA", "BBB"):
            stream.write(json.dumps({"symbol_requested": requested,
                                     "payload": {"results": [item]}}) + "\n")
    events = load_8k_disclosures(path)
    assert len(events) == 1
    assert events["available_date"].iloc[0] == pd.Timestamp("2025-01-06")
    assert events["family"].iloc[0] == "distress"


def test_8k_features_never_use_filing_day() -> None:
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-03", "2025-01-06"]),
                         "symbol": ["AAA", "AAA"]})
    events = pd.DataFrame({"symbol": ["AAA"],
                           "available_date": pd.to_datetime(["2025-01-06"]),
                           "family": ["distress"]})
    result = build_8k_count_features(pool, events)
    assert result["eroya_8k_distress_5d"].tolist() == [0.0, 1.0]
