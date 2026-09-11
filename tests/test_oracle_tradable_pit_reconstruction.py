from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle_tradable_pit_reconstruction import (
    E16Config,
    classify_instruments,
    reconstruct_bar_pit_panel,
)


def _bars(periods: int = 280, *, volume: float = 200_000.0) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": "AAA",
        "date": pd.bdate_range("2023-01-02", periods=periods),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "adj_close": 100.0,
        "volume": volume,
        "is_filled": False,
    })


def _instrument(symbol: str = "AAA") -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": [symbol], "instrument_eligible": [True],
        "instrument_reason": ["eligible_equity"],
    })


def test_reconstruction_uses_only_trailing_rows_and_passes_liquid_event() -> None:
    bars = _bars()
    event_date = bars.iloc[260]["date"]
    membership, audit, diagnostics = reconstruct_bar_pit_panel(
        bars,
        pd.DataFrame({"date": [event_date], "symbol": ["AAA"]}),
        _instrument(), E16Config(),
    )
    assert membership[["date", "symbol"]].to_dict("records") == [
        {"date": event_date, "symbol": "AAA"}
    ]
    assert audit.iloc[0]["history_sessions"] == 261
    assert diagnostics["event_evaluable_ratio"] == 1.0


def test_future_rows_cannot_change_eligibility_at_j() -> None:
    bars = _bars()
    event_date = bars.iloc[260]["date"]
    keys = pd.DataFrame({"date": [event_date], "symbol": ["AAA"]})
    first = reconstruct_bar_pit_panel(bars.iloc[:261], keys, _instrument(), E16Config())[1]
    changed = bars.copy()
    changed.loc[changed["date"] > event_date, "volume"] = 1.0
    second = reconstruct_bar_pit_panel(changed, keys, _instrument(), E16Config())[1]
    assert first.iloc[0]["is_tradable"] == second.iloc[0]["is_tradable"]
    assert first.iloc[0]["adv_usd_20d"] == pytest.approx(second.iloc[0]["adv_usd_20d"])


def test_synthetic_or_missing_bar_is_rejected_fail_closed() -> None:
    bars = _bars()
    bars.loc[260, "is_filled"] = True
    event_date = bars.iloc[260]["date"]
    membership, audit, _ = reconstruct_bar_pit_panel(
        bars, pd.DataFrame({"date": [event_date], "symbol": ["AAA"]}),
        _instrument(), E16Config(),
    )
    assert membership.empty
    assert audit.iloc[0]["reason"] == "bar_missing_or_invalid"


def test_low_adv_is_rejected() -> None:
    bars = _bars(volume=20_000.0)
    event_date = bars.iloc[260]["date"]
    membership, audit, _ = reconstruct_bar_pit_panel(
        bars, pd.DataFrame({"date": [event_date], "symbol": ["AAA"]}),
        _instrument(), E16Config(),
    )
    assert membership.empty
    assert audit.iloc[0]["reason"] in {"volume20_below_minimum", "adv20_below_minimum"}


def test_collective_instrument_is_excluded_without_excluding_reit_trust() -> None:
    metadata = pd.DataFrame({
        "symbol": ["ETF", "REIT"],
        "company_name": ["Example Leveraged ETF", "Example Realty Trust"],
        "asset_class": ["us_equity", "us_equity"],
    })
    result = classify_instruments(metadata).set_index("symbol")
    assert not bool(result.loc["ETF", "instrument_eligible"])
    assert bool(result.loc["REIT", "instrument_eligible"])


def test_config_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError):
        E16Config(min_history_sessions=19)
