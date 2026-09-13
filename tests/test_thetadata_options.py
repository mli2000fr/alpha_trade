from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modelFactory.thetadata_options import (
    ThetaDataClient,
    ThetaOptionPair,
    choose_atm_pair,
    select_synchronized_pair_quote,
)
from modelFactory.thetadata_options_smoke import (
    ThetaSmokeConfig,
    assess_smoke,
    select_smoke_events,
)


class _Response:
    status_code = 200
    ok = True
    headers: dict[str, str] = {}
    content = b'[{"symbol":"AAPL"}]'
    text = content.decode()

    def json(self):
        return [{"symbol": "AAPL"}]


class _Session:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict, float]] = []

    def get(self, url: str, *, params: dict, timeout: float):
        self.calls.append((url, params, timeout))
        return _Response()


def test_client_rejects_remote_base_url() -> None:
    with pytest.raises(ValueError, match="endpoint HTTP local"):
        ThetaDataClient(base_url="https://example.com/v3")


def test_client_forces_json_and_records_response() -> None:
    session = _Session()
    records: list[dict] = []
    client = ThetaDataClient(session=session, recorder=records.append)
    rows = client.list_quoted_contracts("aapl", date(2024, 1, 2), max_dte=55)
    assert rows == [{"symbol": "AAPL"}]
    assert session.calls[0][1]["format"] == "json"
    assert session.calls[0][1]["symbol"] == "AAPL"
    assert records[0]["rows"] == 1
    assert "payload" in records[0]


def test_choose_atm_pair_requires_both_rights_and_dte() -> None:
    contracts = [
        {"expiration": "2024-02-16", "strike": 99, "right": "call"},
        {"expiration": "2024-02-16", "strike": 99, "right": "put"},
        {"expiration": "2024-02-16", "strike": 101, "right": "call"},
    ]
    pair = choose_atm_pair(
        contracts, symbol="abc", spot=100, entry_date=date(2024, 1, 2),
        min_dte=35, max_dte=55, target_dte=45,
    )
    assert pair == ThetaOptionPair("ABC", date(2024, 2, 16), 99.0, 45)


def test_synchronized_quote_selects_first_and_rejects_crossed_quotes() -> None:
    rows = [
        {"right": "call", "timestamp": "2024-01-02T09:35:00", "bid": 1.0, "ask": 1.2},
        {"right": "put", "timestamp": "2024-01-02T09:35:00", "bid": 0.9, "ask": 1.1},
        {"right": "call", "timestamp": "2024-01-02T09:36:00", "bid": 1.3, "ask": 1.2},
        {"right": "put", "timestamp": "2024-01-02T09:36:00", "bid": 0.8, "ask": 1.0},
    ]
    quote = select_synchronized_pair_quote(rows, prefer="first")
    assert quote is not None
    assert quote["timestamp"].startswith("2024-01-02T09:35:00")
    assert quote["call"]["ask"] == 1.2
    assert quote["call"]["quote_timestamp"].startswith("2024-01-02T09:35:00")


def test_select_smoke_events_spreads_dates_and_liquidity() -> None:
    dates = pd.date_range("2024-01-02", periods=5, freq="B")
    oracle = pd.DataFrame([
        {"date": current, "symbol": symbol, "mh0": True}
        for current in dates for symbol in ("LOW", "MID", "HIGH")
    ])
    bars = pd.DataFrame([
        {"date": current, "symbol": symbol, "close": 10, "volume": volume}
        for current in dates
        for symbol, volume in (("LOW", 100), ("MID", 500), ("HIGH", 1000))
    ])
    selected = select_smoke_events(
        oracle, bars, config=ThetaSmokeConfig(dates=5, symbols_per_date=2),
        start_date="2024-01-02", end_date="2024-01-08",
    )
    assert len(selected) == 10
    assert set(selected["symbol"]) == {"LOW", "HIGH"}
    assert selected[selected["symbol"].eq("LOW")]["liquidity_rank_in_top20"].eq(1 / 3).all()
    assert selected[selected["symbol"].eq("HIGH")]["liquidity_rank_in_top20"].eq(1).all()


def test_assessment_opens_pilot_only_when_every_gate_passes() -> None:
    config = ThetaSmokeConfig()
    results = pd.DataFrame({
        "expiration": ["2024-02-16"] * 10,
        "historically_expired": [True] * 10,
        "status": ["complete"] * 10,
        "timestamps_match_requested_dates": [True] * 10,
    })
    assessment = assess_smoke(results, config=config)
    assert assessment["verdict"] == "GO_E8_A2_PILOT_60_DATES"
    blocked = assess_smoke(results.iloc[:1], config=config, terminal_error="terminal_unreachable")
    assert blocked["verdict"] == "BLOCKED_THETA_TERMINAL_NOT_RUNNING"
