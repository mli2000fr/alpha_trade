from datetime import date

import pytest

from service.fr.identity import FrIdentityConflict, Validity, assert_no_overlap


def _row(uid: str, start: str, end: str | None, symbol: str = "ABC.PA") -> Validity:
    return Validity(uid, "eodhd:PA", symbol, date.fromisoformat(start),
                    date.fromisoformat(end) if end else None)


def test_reused_ticker_is_allowed_only_after_previous_mapping_ends() -> None:
    assert_no_overlap([_row("old", "2016-01-01", "2020-12-31"),
                       _row("new", "2021-01-01", None)])


def test_same_ticker_same_day_for_two_instruments_is_blocked() -> None:
    with pytest.raises(FrIdentityConflict, match="chevauchantes"):
        assert_no_overlap([_row("old", "2016-01-01", "2020-12-31"),
                           _row("new", "2020-12-31", None)])


def test_symbol_change_for_one_instrument_is_allowed() -> None:
    assert_no_overlap([_row("one", "2016-01-01", "2020-12-31", "OLD.PA"),
                       _row("one", "2021-01-01", None, "NEW.PA")])


def test_isin_cannot_be_double_listed_on_xpar_at_same_time() -> None:
    first = Validity("one", "listing:XPAR", "FR0000120073", date(2020, 1, 1))
    second = Validity("two", "listing:XPAR", "FR0000120073", date(2021, 1, 1))
    with pytest.raises(FrIdentityConflict, match="chevauchantes"):
        assert_no_overlap([first, second])


def test_invalid_period_is_blocked() -> None:
    with pytest.raises(FrIdentityConflict, match="inversée"):
        _row("one", "2024-01-02", "2024-01-01")
