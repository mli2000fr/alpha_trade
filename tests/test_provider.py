import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import date
from corporate_actions.provider import (
    AlpacaCorporateActionProvider,
    CorporateActionProvider,
)
from corporate_actions.models import CaType, CorporateActionEvent

class DummySession:
    def __init__(self):
        self.headers = {}
        self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {
                    "corporate_actions": {
                        "cash_dividends": [
                            {"id": "d1", "symbol": "AAPL", "rate": 1.5, "ex_date": "2024-01-01"}
                        ],
                        "forward_splits": [
                            {"id": "s1", "symbol": "AAPL", "old_rate": 2, "new_rate": 3, "ex_date": "2024-01-02"}
                        ],
                        "reverse_splits": [
                            {"id": "r1", "symbol": "AAPL", "old_rate": 3, "new_rate": 1, "ex_date": "2024-01-03"}
                        ]
                    }
                }
        return Resp()

def test_provider_interface():
    class Dummy(CorporateActionProvider):
        def fetch_events(self, symbols, start_date=None, end_date=None):
            return ["ok"]
    d = Dummy()
    assert d.fetch_events(["AAPL"]) == ["ok"]

def test_alpaca_provider_fetch_events(monkeypatch):
    # Patch credentials
    monkeypatch.setattr("service.alpaca.clientAlpaca.get_alpaca_credentials", lambda account_id=None: ("k","s"))
    session = DummySession()
    provider = AlpacaCorporateActionProvider(session=session)
    events = provider.fetch_events(["AAPL"], start_date=date(2024,1,1), end_date=date(2024,1,31))
    assert any(e.ca_type == CaType.CASH_DIVIDEND for e in events)
    assert any(e.ca_type == CaType.SPLIT for e in events)
    assert any(e.ca_type == CaType.REVERSE_SPLIT for e in events)
    assert all(isinstance(e, CorporateActionEvent) for e in events)
    # Pagination: no next_page_token, so only one call
    assert len(session.calls) == 1

def test_parse_dividend():
    raw = {"id": "d1", "symbol": "AAPL", "rate": 1.5, "ex_date": "2024-01-01", "special": True}
    evt = AlpacaCorporateActionProvider._parse_dividend(raw)
    assert evt.ca_type == CaType.SPECIAL_DIVIDEND
    assert evt.amount_per_share == 1.5
    assert evt.symbol == "AAPL"
    assert evt.ex_date == date(2024,1,1)

def test_parse_split():
    raw = {"id": "s1", "symbol": "AAPL", "old_rate": 2, "new_rate": 3, "ex_date": "2024-01-02"}
    evt = AlpacaCorporateActionProvider._parse_split(raw, CaType.SPLIT)
    assert evt.ca_type == CaType.SPLIT
    assert evt.split_from == 2
    assert evt.split_to == 3
    assert evt.symbol == "AAPL"
    assert evt.ex_date == date(2024,1,2)

def test_normalize_split_ratio():
    d, n = AlpacaCorporateActionProvider._normalize_split_ratio(2, 3)
    assert (d, n) == (2, 3)
    d, n = AlpacaCorporateActionProvider._normalize_split_ratio("3", "1")
    assert (d, n) == (3, 1)
    with pytest.raises(ValueError):
        AlpacaCorporateActionProvider._normalize_split_ratio(0, 1)
    with pytest.raises(ValueError):
        AlpacaCorporateActionProvider._normalize_split_ratio(1, 0)

