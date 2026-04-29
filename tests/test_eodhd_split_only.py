"""Golden tests reconstruction split-only EODHD (Phase 2 plan §5.4 + §7.1 T-EOD-3).

Cas de référence : split NVDA **10:1** du 2024-06-10.
Les barres antérieures doivent voir leurs prix divisés par 10 et leur volume
multiplié par 10 pour rejoindre proprement les barres post-split.
"""
from __future__ import annotations

import pytest

from service.eodhd import adapters


SPLITS_NVDA = [
    {"date": "2024-06-10", "split": "10/1"},
    {"date": "2021-07-20", "split": "4/1"},
]


# ---------------------------------------------------------------------------
# parse_split_ratio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("10/1", 10.0),
        ("4/1", 4.0),
        ("1/2", 0.5),  # reverse split (split-down)
        (10.0, 10.0),
        ("3", 3.0),
    ],
)
def test_parse_split_ratio_ok(raw, expected):
    assert adapters.parse_split_ratio(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", None, "abc", "10/0", "-1", 0])
def test_parse_split_ratio_invalid(raw):
    with pytest.raises(ValueError):
        adapters.parse_split_ratio(raw)


# ---------------------------------------------------------------------------
# cumulative_split_factor
# ---------------------------------------------------------------------------


def test_cumulative_factor_post_split_is_one():
    # Le jour du split, le facteur est déjà 1 (la barre du jour est post-split)
    assert adapters.cumulative_split_factor(SPLITS_NVDA, "2024-06-10") == 1.0


def test_cumulative_factor_between_splits():
    # 2022-01-01 : seul le split 10:1 du 2024-06-10 est postérieur
    assert adapters.cumulative_split_factor(SPLITS_NVDA, "2022-01-01") == 10.0


def test_cumulative_factor_before_all_splits():
    # 2020-01-01 : les deux splits (10/1 et 4/1) postérieurs -> 40
    assert adapters.cumulative_split_factor(SPLITS_NVDA, "2020-01-01") == 40.0


# ---------------------------------------------------------------------------
# Golden NVDA 10:1
# ---------------------------------------------------------------------------


def test_golden_nvda_10_for_1_reconstruction():
    """Barre brute J-1 split + barre brute J+1 split -> jonction sans saut."""
    raw_bars = [
        # J-1 split : prix x10, volume /10 vs post-split
        {"date": "2024-06-07", "open": 1200.0, "high": 1210.0, "low": 1190.0, "close": 1205.0, "adjusted_close": 120.5, "volume": 30_000_000},
        # J+1 split : déjà à l échelle moderne
        {"date": "2024-06-11", "open": 122.0, "high": 124.0, "low": 121.0, "close": 123.5, "adjusted_close": 123.5, "volume": 300_000_000},
    ]
    out = adapters.eodhd_to_split_only(raw_bars, SPLITS_NVDA)

    assert len(out) == 2
    pre, post = out

    # Pre-split : divisé par 10
    assert pre["close"] == pytest.approx(120.5, rel=1e-9)
    assert pre["open"] == pytest.approx(120.0, rel=1e-9)
    assert pre["volume"] == 300_000_000  # 30M * 10
    assert pre["split_factor"] == 10.0

    # Post-split : inchangé
    assert post["close"] == pytest.approx(123.5)
    assert post["volume"] == 300_000_000
    assert post["split_factor"] == 1.0

    # Jonction sans saut : delta % entre pre.close et post.close < 5%
    delta = abs(post["close"] - pre["close"]) / pre["close"]
    assert delta < 0.05, f"saut anormal: {delta:.2%}"


def test_eodhd_to_split_only_skips_invalid_bars():
    raw = [
        {"date": "2024-06-11", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "adjusted_close": 1},
        {"date": "2024-06-12"},  # incomplet
        {"open": 1, "close": 1},  # pas de date
    ]
    out = adapters.eodhd_to_split_only(raw, [])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Mappage DB
# ---------------------------------------------------------------------------


def test_to_stock_bars_daily_row_shape():
    bar = {"date": "2024-06-07", "open": 120.0, "high": 121.0, "low": 119.0, "close": 120.5,
           "volume": 300_000_000, "adjusted_close": 120.5, "split_factor": 10.0}
    row = adapters.to_stock_bars_daily_row(bar, "NVDA")

    assert row["symbol"] == "NVDA"
    assert row["date"] == "2024-06-07"
    assert row["close"] == 120.5
    assert row["adj_close"] == 120.5
    assert row["data_adjustment"] == "split"
    assert row["data_source"] == "eodhd_eod"
    assert row["is_filled"] == 0


def test_to_stock_bars_row_uses_close_timestamp():
    bar = {"date": "2024-06-07", "open": 120.0, "high": 121.0, "low": 119.0, "close": 120.5,
           "volume": 300_000_000, "adjusted_close": 120.5, "split_factor": 10.0}
    row = adapters.to_stock_bars_row(bar, "NVDA")

    assert row["symbol"] == "NVDA"
    assert row["timeframe"] == "1D"
    assert row["timestamp"].year == 2024
    assert row["timestamp"].hour == adapters.US_CLOSE_UTC_HOUR
    assert row["close_price"] == 120.5
    assert row["data_source"] == "eodhd_eod"
    assert row["data_adjustment"] == "split"


# ---------------------------------------------------------------------------
# Fallback splits depuis adjusted_close (Option B plan)
# ---------------------------------------------------------------------------


def test_infer_splits_from_adjusted_close_detects_10_for_1():
    history = [
        {"date": "2024-06-07", "close": 1205.0, "adjusted_close": 120.5},
        {"date": "2024-06-10", "close": 120.5,  "adjusted_close": 120.5},  # post-split
        {"date": "2024-06-11", "close": 123.5,  "adjusted_close": 123.5},
    ]
    splits = adapters.infer_splits_from_adjusted_close(history)
    assert splits == [{"date": "2024-06-10", "split": "10/1"}]


def test_infer_splits_no_split_returns_empty():
    history = [
        {"date": "2024-06-07", "close": 100.0, "adjusted_close": 100.0},
        {"date": "2024-06-10", "close": 101.0, "adjusted_close": 101.0},
    ]
    assert adapters.infer_splits_from_adjusted_close(history) == []

