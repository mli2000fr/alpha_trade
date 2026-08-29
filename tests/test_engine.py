import sys
import os
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

# Ajout du dossier parent au sys.path pour import corporate_actions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from corporate_actions.engine import CorporateActionEngine
from corporate_actions.models import CorporateActionEvent, CaType, CaStatus, PositionSnapshot

class DummyProvider:
    def __init__(self, events=None):
        self._events = events or []
        self.fetch_events_called = False
    def fetch_events(self, symbols=None, start_date=None, end_date=None):
        self.fetch_events_called = True
        return self._events

def make_event(symbol="AAPL", ca_type=CaType.CASH_DIVIDEND, ex_date=date(2026, 4, 10), amount=1.0):
    evt = CorporateActionEvent(
        provider="alpaca",
        provider_event_id="div-001",
        symbol=symbol,
        ca_type=ca_type,
        amount_per_share=amount,
        ex_date=ex_date,
    )
    return evt

def test_sync_insert(monkeypatch):
    events = [make_event(symbol="AAPL"), make_event(symbol="MSFT")]
    provider = DummyProvider(events)
    repo = MagicMock()
    repo.load_existing_event_symbols.return_value = []
    repo.insert_event.side_effect = [1, 2]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.sync(symbols=["AAPL", "MSFT"])
    assert stats["inserted"] == 2
    assert stats["duplicates"] == 0
    assert provider.fetch_events_called

def test_sync_duplicates(monkeypatch):
    events = [make_event(symbol="AAPL")]
    provider = DummyProvider(events)
    repo = MagicMock()
    repo.load_existing_event_symbols.return_value = []
    repo.insert_event.side_effect = [-1]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.sync(symbols=["AAPL"])
    assert stats["inserted"] == 0
    assert stats["duplicates"] == 1

def test_sync_invalid(monkeypatch):
    class InvalidEvent:
        def validate(self):
            return ["error"]
        symbol = "AAPL"
    provider = DummyProvider([InvalidEvent()])
    repo = MagicMock()
    repo.load_existing_event_symbols.return_value = []
    engine = CorporateActionEngine(provider, repo)
    stats = engine.sync(symbols=["AAPL"])
    assert stats["invalid"] == 1

def test_sync_skip_existing(monkeypatch):
    events = [make_event(symbol="AAPL")]
    provider = DummyProvider(events)
    repo = MagicMock()
    repo.load_existing_event_symbols.return_value = ["AAPL"]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.sync(symbols=["AAPL"], skip_existing=True)
    assert stats["inserted"] == 0
    assert stats["fetched"] == 0

def test_apply_no_pending(monkeypatch):
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = []
    engine = CorporateActionEngine(provider, repo)
    stats = engine.apply()
    assert stats == {"applied": 0, "skipped": 0, "failed": 0}

def test_apply_with_position(monkeypatch):
    event = make_event(symbol="AAPL")
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.return_value = False
    repo.load_latest_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100, "market_value": 1000}]
    # Patch process_dividend
    with patch("corporate_actions.engine.process_dividend") as proc_div:
        app = MagicMock()
        ledger = MagicMock()
        proc_div.return_value = (app, ledger)
        # On force event.id pour que mark_applied soit appelé
        event.id = 123
        engine = CorporateActionEngine(provider, repo)
        stats = engine.apply()
        assert stats["applied"] == 1
        repo.insert_application.assert_called_once()
        repo.insert_cash_ledger.assert_called_once()
        repo.mark_applied.assert_called_once_with(123)

def test_apply_already_applied(monkeypatch):
    event = make_event(symbol="AAPL")
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.return_value = True
    repo.load_latest_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100, "market_value": 1000}]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.apply()
    assert stats["skipped"] == 1

def test_apply_no_position(monkeypatch):
    event = make_event(symbol="AAPL")
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.return_value = False
    repo.load_latest_positions.return_value = []
    engine = CorporateActionEngine(provider, repo)
    stats = engine.apply()
    assert stats["skipped"] == 1

def test_apply_split(monkeypatch):
    event = make_event(symbol="AAPL", ca_type=CaType.SPLIT)
    event.split_from = 1.0
    event.split_to = 2.0
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.return_value = False
    repo.load_latest_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100, "market_value": 1000}]
    with patch("corporate_actions.engine.process_split") as proc_split:
        app = MagicMock()
        ledger = MagicMock()
        proc_split.return_value = (app, ledger)
        event.id = 456
        engine = CorporateActionEngine(provider, repo)
        stats = engine.apply()
        assert stats["applied"] == 1
        repo.insert_application.assert_called_once()
        repo.insert_cash_ledger.assert_called_once()
        repo.mark_applied.assert_called_once_with(456)

def test_apply_unsupported_type(monkeypatch):
    event = make_event(symbol="AAPL", ca_type="UNSUPPORTED")
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.return_value = False
    repo.load_latest_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100, "market_value": 1000}]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.apply()
    assert stats["failed"] == 1

def test_apply_exception(monkeypatch):
    event = make_event(symbol="AAPL")
    provider = DummyProvider()
    repo = MagicMock()
    repo.load_pending_events.return_value = [event]
    repo.is_event_applied.side_effect = Exception("fail")
    repo.load_latest_positions.return_value = [{"symbol": "AAPL", "qty": 10, "avg_entry_price": 100, "market_value": 1000}]
    engine = CorporateActionEngine(provider, repo)
    stats = engine.apply()
    assert stats["failed"] == 1

