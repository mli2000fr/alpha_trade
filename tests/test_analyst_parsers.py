"""Tests des parsers Yahoo analyst (RESEARCH ONLY)."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from analyst_research.features import revision_pct
from analyst_research.parsers import (
    HORIZON_MAP,
    ProviderSchemaChangedError,
    compute_raw_hash,
    parse_estimate,
    parse_recommendations,
    parse_targets,
)

OBS = datetime(2026, 8, 27, 22, 30)  # UTC
AVAIL = datetime(2026, 8, 28, 20, 0)  # UTC
SNAP = date(2026, 8, 27)


def _est_df(periods=("0q", "+1q", "0y", "+1y")):
    return pd.DataFrame(
        {"avg": [1.5, 2.1, 6.0, 6.4],
         "low": [1.3, 1.9, 5.5, 5.9],
         "high": [1.7, 2.4, 6.6, 7.0],
         "numberOfAnalysts": [12, 10, 20, 18],
         "growth": [0.05, 0.02, 0.10, 0.08]},
        index=pd.Index(periods, name="period"),
    )


def test_estimate_parser_horizons_and_values():
    rows = parse_estimate(_est_df(), estimate_type="EPS", symbol="AAPL",
                          snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL)
    assert len(rows) == 4
    by_h = {r["horizon_raw"]: r for r in rows}
    assert by_h["0q"]["horizon_normalized"] == "CURRENT_QUARTER"
    assert by_h["+1q"]["horizon_normalized"] == "NEXT_QUARTER"
    assert by_h["0y"]["horizon_normalized"] == "CURRENT_YEAR"
    assert by_h["+1y"]["horizon_normalized"] == "NEXT_YEAR"
    r = by_h["0q"]
    assert r["estimate_type"] == "EPS"
    assert r["avg_value"] == 1.5
    assert r["low_value"] == 1.3
    assert r["high_value"] == 1.7
    assert r["analyst_count"] == 12
    assert r["growth_value"] == 0.05
    assert r["relative_horizon_only"] is True
    assert r["fiscal_period_end"] is None
    assert r["fiscal_year"] is None
    assert r["snapshot_date"] == SNAP
    assert r["available_at"] == AVAIL
    assert r["raw_hash"] and len(r["raw_hash"]) == 64


def test_estimate_parser_missing_value_null_not_zero():
    df = _est_df()
    df.loc["0q", "low"] = float("nan")
    rows = parse_estimate(df, estimate_type="EPS", symbol="AAPL",
                          snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL)
    assert rows[0]["low_value"] is None  # jamais 0


def test_estimate_parser_empty():
    assert parse_estimate(pd.DataFrame(), estimate_type="EPS", symbol="AAPL",
                          snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL) == []
    assert parse_estimate(None, estimate_type="EPS", symbol="AAPL",
                          snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL) == []


def test_estimate_parser_schema_change_raises():
    df = _est_df().drop(columns=["avg"])
    with pytest.raises(ProviderSchemaChangedError):
        parse_estimate(df, estimate_type="EPS", symbol="AAPL",
                       snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL)


def test_target_parser():
    rows = parse_targets({"current": 250.0, "low": 200.0, "mean": 270.0,
                          "median": 265.0, "high": 320.0}, symbol="AAPL",
                         snapshot_date=SNAP, observed_at=OBS, available_at=AVAIL)
    assert len(rows) == 1
    r = rows[0]
    assert r["current_price"] == 250.0
    assert r["target_mean"] == 270.0
    assert r["target_median"] == 265.0
    assert r["target_high"] == 320.0
    assert r["target_low"] == 200.0
    assert r["analyst_count"] is None  # Yahoo ne fournit pas ce champ


def test_target_parser_empty():
    assert parse_targets({}, symbol="AAPL", snapshot_date=SNAP,
                         observed_at=OBS, available_at=AVAIL) == []
    assert parse_targets(None, symbol="AAPL", snapshot_date=SNAP,
                         observed_at=OBS, available_at=AVAIL) == []


def test_recommendation_parser_one_row_per_period():
    df = pd.DataFrame({"period": ["0m", "-1m", "-2m"],
                       "strongBuy": [3, 2, 2], "buy": [10, 11, 10],
                       "hold": [5, 6, 7], "sell": [1, 1, 1],
                       "strongSell": [0, 0, 1]})
    rows = parse_recommendations(df, symbol="AAPL", snapshot_date=SNAP,
                                 observed_at=OBS, available_at=AVAIL)
    assert len(rows) == 3
    by_p = {r["period_raw"]: r for r in rows}
    assert by_p["0m"]["strong_buy"] == 3
    assert by_p["0m"]["buy"] == 10
    assert by_p["0m"]["hold"] == 5
    assert by_p["0m"]["sell"] == 1
    assert by_p["0m"]["strong_sell"] == 0
    assert by_p["-2m"]["strong_sell"] == 1


def test_recommendation_parser_empty():
    assert parse_recommendations(pd.DataFrame(), symbol="AAPL", snapshot_date=SNAP,
                                 observed_at=OBS, available_at=AVAIL) == []


def test_revision_pct_rules():
    # révision % avec dénom = abs(old)
    assert revision_pct(4.18, 4.25) == pytest.approx((4.18 - 4.25) / 4.25)
    # old négatif → abs(old)
    assert revision_pct(0.5, -0.5) == pytest.approx(2.0)
    # old ≈ 0 → NULL (pas de division par zéro / fausse révision)
    assert revision_pct(1.0, 0.0) is None
    assert revision_pct(1.0, 1e-12) is None
    # valeurs manquantes → NULL
    assert revision_pct(None, 1.0) is None
    assert revision_pct(1.0, None) is None


def test_raw_hash_deterministic():
    assert compute_raw_hash({"a": 1, "b": [1, 2]}) == compute_raw_hash({"a": 1, "b": [1, 2]})
    assert compute_raw_hash({"a": 1}) != compute_raw_hash({"a": 2})


def test_horizon_map():
    assert HORIZON_MAP["0q"] == "CURRENT_QUARTER"
    assert HORIZON_MAP["+1q"] == "NEXT_QUARTER"
    assert HORIZON_MAP["0y"] == "CURRENT_YEAR"
    assert HORIZON_MAP["+1y"] == "NEXT_YEAR"
