from datetime import date, datetime, timezone

import pytest

from modelFactory.cn_dragon_tiger_preflight_15d5 import preflight, summarize_deciles
from service.market.cn_dragon_tiger_prospective_15d5 import build_snapshot


def _stamp() -> datetime:
    return datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)


def test_prospective_snapshot_excludes_seat_payload_and_tracks_first_seen():
    row = {
        "date": "2026-09-30", "exchange": "SSE", "code": "600000",
        "reason_code": "Z1", "buy_seat_names": "private seat",
        "buy_seat_amounts": "12345",
    }
    first = build_snapshot(date(2026, 9, 30), [row], [], [], _stamp(), {})
    assert first["retrospective"] is False
    assert first["pit_usable"] is False
    assert first["counts"]["first_seen"] == 1
    assert "private seat" not in str(first)
    assert "12345" not in str(first)
    changed = {**row, "buy_seat_amounts": "12346"}
    second = build_snapshot(date(2026, 9, 30), [changed], [], [first],
                            datetime(2026, 9, 30, 11, tzinfo=timezone.utc), {})
    assert second["counts"]["changed_payload_since_last"] == 1
    assert second["events"][0]["first_seen_at_utc"] == first["observed_at_utc"]


def test_retrospective_and_future_dates_do_not_claim_pit():
    old = build_snapshot(date(2025, 9, 30), [], [], [], _stamp(), {})
    assert old["retrospective"] is True
    assert old["pit_usable"] is False
    with pytest.raises(ValueError, match="Future"):
        build_snapshot(date(2026, 10, 1), [], [], [], _stamp(), {})


def test_preflight_requires_no_same_day_and_reports_unmatched_counts():
    deciles = {
        "1": {"oracle_top20_rows": 100, "event_within_5_sessions": 30,
              "event_within_20_sessions": 40},
        "10": {"oracle_top20_rows": 100, "event_within_5_sessions": 10,
               "event_within_20_sessions": 20},
    }
    source = {
        "status": "COVERAGE_PROXY_ONLY_NO_ML_GO",
        "same_day_event_used": False, "mapping": {"unmapped_events": 0},
        "coverage": {"JPLUS1": {"realized_deciles": deciles},
                     "JPLUS2": {"realized_deciles": deciles}},
    }
    result = preflight(source)
    assert result["status"] == "NO_GO_ML_PENDING_RIGHTS_PIT_MATCHING"
    assert result["analyses"][result["primary"]]["d1_share_among_covered_extremes"] == 0.75
    assert summarize_deciles(source["coverage"]["JPLUS2"], 5)["d1_no_event"] == 70
    source["same_day_event_used"] = True
    with pytest.raises(ValueError, match="Same-day"):
        preflight(source)
