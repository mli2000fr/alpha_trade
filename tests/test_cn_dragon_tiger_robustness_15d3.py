import pytest

from service.market.cn_dragon_tiger_robustness_15d3 import (
    choose_dates,
    seat_integrity,
)


def test_choose_dates_are_deterministic_calendar_terciles() -> None:
    assert choose_dates(["2024-01-01", "2024-01-02", "2024-01-03",
                         "2024-01-04", "2024-01-05", "2024-01-08"]) == (
        "2024-01-03", "2024-01-05")
    with pytest.raises(ValueError):
        choose_dates(["2024-01-02", "2024-01-01", "2024-01-03"])


def test_seat_integrity_checks_count_and_amounts() -> None:
    row = {"exchange": "SSE", "buy_seat_names": "a,b",
           "buy_seat_amounts": "10.5,20", "sell_seat_names": "c",
           "sell_seat_amounts": "30"}
    result = seat_integrity(row)
    assert result["buy"]["count_match"]
    assert result["sell"]["all_amounts_nonnegative"]
    assert not seat_integrity({**row, "buy_seat_amounts": "10.5"})["buy"]["count_match"]
    assert not seat_integrity({**row, "sell_seat_amounts": "-30"})["sell"]["all_amounts_nonnegative"]
