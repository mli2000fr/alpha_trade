"""Offline checks for the French public-disclosure research experiment."""

import pandas as pd

from scripts.research.fr_public_disclosures_poc import (
    join_events,
    label_prices,
    normalize,
    safe_publication_date,
    thin,
)


def test_publication_uses_latest_official_timestamp_in_paris():
    fields = {
        "uin_dat_amf": "2024-06-01T23:30:00+00:00",
        "uin_dat_mar": "2024-06-01T20:00:00+00:00",
        "informationdeposee_inf_dat_emt": "2024-06-01T21:00:00+00:00",
    }
    assert safe_publication_date(fields) == pd.Timestamp("2024-06-02")


def test_same_day_disclosure_enters_next_session_only():
    disclosures = pd.DataFrame({
        "symbol": ["AAA.PA"],
        "published_date": [pd.Timestamp("2024-05-06")],
        "title": ["Résultats"],
        "financial_title": [True],
        "positive_title": [False],
        "negative_title": [False],
    })
    prices = pd.DataFrame({
        "symbol": ["AAA.PA", "AAA.PA", "AAA.PA"],
        "date": pd.to_datetime(["2024-05-06", "2024-05-07", "2024-05-08"]),
        "adjusted_open": [10.0, 11.0, 12.0],
        "adjusted_close": [10.5, 11.5, 12.5],
    })
    joined = join_events(disclosures, label_prices(prices, (2,)))
    assert joined.iloc[0]["date"] == pd.Timestamp("2024-05-07")
    assert abs(joined.iloc[0]["return_h2"] - (12.5 / 11.0 - 1)) < 1e-12


def test_thinning_uses_bar_distance_not_calendar_days():
    events = pd.DataFrame({
        "symbol": ["AAA.PA"] * 4,
        "bar_index": [1, 2, 5, 6],
    })
    assert thin(events, horizon=4).bar_index.tolist() == [1, 5]


def test_accent_normalization():
    assert normalize("Révision À LA HAUSSE") == "revision a la hausse"
