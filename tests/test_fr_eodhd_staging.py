from datetime import date

from service.fr.load_eodhd_staging import classify_bar


SESSIONS = {date(2016, 1, 4)}
BAR = {"date": "2016-01-04", "open": 10, "high": 11,
       "low": 9, "close": 10.5, "volume": 100,
       "adjusted_close": 9.5}


def test_fr_staging_classifies_valid_bar_without_claiming_raw_volume():
    day, quality, values = classify_bar(BAR, SESSIONS)
    assert day == date(2016, 1, 4)
    assert quality == "VALID"
    assert values["volume"] == 100
    assert values["adjusted"] == 9.5


def test_fr_staging_quarantines_placeholder_and_closed_day():
    fake = {**BAR, "open": 999999.9999, "high": 999999.9999,
            "low": 999999.9999, "close": 999999.9999, "volume": 0}
    assert classify_bar(fake, SESSIONS)[1] == "PLACEHOLDER"
    assert classify_bar({**BAR, "date": "2016-01-05"}, SESSIONS)[1] == "NON_SESSION"


def test_fr_staging_quarantines_bad_ohlc_and_price():
    assert classify_bar({**BAR, "high": 10}, SESSIONS)[1] == "BAD_OHLC"
    assert classify_bar({**BAR, "open": 0}, SESSIONS)[1] == "BAD_PRICE"
    assert classify_bar({**BAR, "volume": None}, SESSIONS)[1] == "BAD_VOLUME"
    assert classify_bar({**BAR, "volume": 0}, SESSIONS)[1] == "ZERO_VOLUME"
