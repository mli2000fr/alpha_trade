from __future__ import annotations

import pandas as pd

from service.market.cn_guidance_pilot_15d1 import (
    PERIODS,
    classify_document,
    coverage_summary,
    join_prior_announcements,
    select_top20,
)
from scripts.research.cn_guidance_pdf_review_15d1 import classify


def test_pdf_review_keeps_numeric_values_quarantined() -> None:
    result = classify(
        "2024年年度业绩预亏公告更正公告",
        "前次业绩预告情况。原预计 27,100-32,100 万元。更正后预计 32,100-35,000 万元。单位：万元",
    )
    assert result["fiscal_year"] == 2024
    assert result["fiscal_period"] == "年度"
    assert result["correction"] is True
    assert result["has_prior_section"] is True
    assert result["has_new_section"] is True
    assert result["declared_units"] == ["万元"]
    assert result["numeric_status"] == "QUARANTINED_MANUAL_VALIDATION_REQUIRED"
    assert classify("2023年度业绩预告", "")["fiscal_year"] == 2023


def test_periods_are_2023_to_2025_quarters_without_2025_q4() -> None:
    assert PERIODS[0] == "2023-03-31"
    assert PERIODS[-1] == "2025-09-30"
    assert len(PERIODS) == 11


def test_select_top20_matches_oracle_order_and_paired_mask() -> None:
    frame = pd.DataFrame({
        "session_date": pd.to_datetime(["2025-01-03"] * 6),
        "instrument_id": [3, 2, 1, 4, 5, 6],
        "target_quality_valid": [True] * 5 + [False],
        "baseline_score": [0.1] * 5 + [None],
        "oracle_score": [0.8, 0.9, 0.9, 0.2, 0.1, 0.99],
    })
    selected = select_top20(frame, 0.20)
    assert selected["instrument_id"].tolist() == [1]


def test_same_day_and_future_announcements_never_join() -> None:
    top = pd.DataFrame({
        "local_symbol": ["000001"] * 3,
        "session_date": pd.to_datetime(["2025-01-10", "2025-01-11", "2025-04-20"]),
        "semester": ["2025H1"] * 3,
        "board_code": ["SZ_MAIN"] * 3,
        "oracle_decile": [1, 10, 5],
    })
    discovery = pd.DataFrame({"local_symbol": ["000001", "000001"],
                              "notice_date": ["2025-01-10", "2025-01-20"]})
    joined = join_prior_announcements(top, discovery).sort_values("session_date")
    assert pd.isna(joined.iloc[0]["notice_date"])
    assert joined.iloc[1]["age_calendar_days"] == 1
    assert joined.iloc[2]["age_calendar_days"] == 90
    assert coverage_summary(joined)["overall"]["within_90d"] == 2


def test_correction_is_quarantined_not_promoted_as_numeric_feature() -> None:
    title = "2024年年度业绩预亏公告更正公告"
    text = "二、前次业绩预告情况 原预计亏损27000-32100万元。三、更正后的业绩预告情况 亏损32100-35000万元。"
    result = classify_document(title, text)
    assert result == {
        "fiscal_year": 2024,
        "fiscal_period": "年度",
        "correction": True,
        "has_prior_section": True,
        "has_new_section": True,
        "extraction_status": "MANUAL_REVIEW_REQUIRED",
    }
