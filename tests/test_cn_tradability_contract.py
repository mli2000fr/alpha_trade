from datetime import date, datetime, timedelta

from service.market.cn_tradability_contract import assess_execution_data, assess_pretrade

SESSION = date(2025, 6, 20)
OPEN = datetime(2025, 6, 20, 9, 25)
CLOSE = datetime(2025, 6, 20, 16, 0)


def test_delisting_date_is_inclusive_but_absent_terminal_bar_cannot_fill() -> None:
    candidate = assess_pretrade(
        session_date=SESSION, decision_at=OPEN,
        listing_date=date(2010, 1, 1), delisting_date=SESSION,
    )
    assert candidate.state == "CANDIDATE"
    assert assess_execution_data(bar_present=False, trading_status=None, limit_policy=None).reason == "NO_SESSION_BAR"
    assert assess_pretrade(
        session_date=SESSION + timedelta(days=1), decision_at=OPEN + timedelta(days=1),
        listing_date=date(2010, 1, 1), delisting_date=SESSION,
    ).reason == "AFTER_DELISTING_DATE"


def test_eight_status_conflicts_are_excluded_only_when_known() -> None:
    inputs = {
        "session_date": SESSION, "decision_at": OPEN, "listing_date": date(2010, 1, 1),
        "delisting_date": None, "trading_status": "SUSPENDED|SOURCE_CONFLICT",
    }
    assert assess_pretrade(**inputs, status_available_at=CLOSE).state == "CANDIDATE"
    assert assess_pretrade(**inputs, status_available_at=OPEN - timedelta(minutes=1)).reason == "SOURCE_STATUS_CONFLICT"
    result = assess_execution_data(
        bar_present=True, trading_status="SUSPENDED|SOURCE_CONFLICT", limit_policy="CN_MAIN_10PCT_V1",
    )
    assert result.state == "EXCLUDED" and result.reason == "SOURCE_STATUS_CONFLICT"


def test_unknown_price_limits_are_not_lookahead_filters() -> None:
    inputs = {
        "session_date": SESSION, "decision_at": OPEN, "listing_date": date(2010, 1, 1),
        "delisting_date": None, "limit_policy": "OBSERVED_OUTSIDE_DERIVED_LIMIT_V1",
    }
    assert assess_pretrade(**inputs, limit_available_at=CLOSE).state == "CANDIDATE"
    assert assess_pretrade(**inputs, limit_available_at=OPEN - timedelta(minutes=1)).reason == "UNVERIFIED_PRICE_LIMIT"
    assert assess_execution_data(
        bar_present=True, trading_status="TRADE", limit_policy="OBSERVED_OUTSIDE_DERIVED_LIMIT_V1",
    ).state == "UNVERIFIABLE"
    assert assess_execution_data(
        bar_present=True, trading_status="TRADE", limit_policy=None,
    ).state == "UNVERIFIABLE"
    assert assess_execution_data(
        bar_present=True, trading_status="TRADE", limit_policy="CN_MAIN_10PCT_V1",
    ).state == "DATA_CHECKS_PASSED"
    assert assess_execution_data(
        bar_present=True, trading_status="TRADE", limit_policy="CN_MAIN_10PCT_V1", locked_up=True,
    ).reason == "LOCKED_LIMIT_SIDE_DEPENDENT"
