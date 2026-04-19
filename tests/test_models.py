import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import date, datetime
from corporate_actions import models

# --- CorporateActionEvent ---
def make_event(**kwargs):
    base = dict(
        provider="alpaca",
        provider_event_id="evt1",
        symbol="AAPL",
        ca_type=models.CaType.CASH_DIVIDEND,
        ex_date=date(2024, 1, 1),
        amount_per_share=1.23,
    )
    base.update(kwargs)
    return models.CorporateActionEvent(**base)

def test_idempotency_key_dividend():
    evt = make_event()
    key = evt.idempotency_key
    evt2 = make_event()
    assert key == evt2.idempotency_key
    evt3 = make_event(amount_per_share=2.0)
    assert key != evt3.idempotency_key

def test_idempotency_key_split():
    evt = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=3)
    key = evt.idempotency_key
    evt2 = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=3)
    assert key == evt2.idempotency_key
    evt3 = make_event(ca_type=models.CaType.SPLIT, split_from=3, split_to=2)
    assert key != evt3.idempotency_key

def test_split_ratio():
    evt = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=4)
    assert evt.split_ratio == 2.0
    evt2 = make_event(ca_type=models.CaType.REVERSE_SPLIT, split_from=10, split_to=1)
    assert evt2.split_ratio == 0.1
    evt3 = make_event(ca_type=models.CaType.SPLIT, split_from=None, split_to=None)
    assert evt3.split_ratio == 1.0

def test_validate_ok():
    evt = make_event()
    assert evt.validate() == []
    evt2 = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=1)
    assert evt2.validate() == []

def test_validate_errors():
    evt = make_event(ca_type="unknown")
    assert "ca_type inconnu" in evt.validate()[0]
    evt2 = make_event(symbol=" ")
    assert "symbol manquant" in evt2.validate()[0]
    evt3 = make_event(amount_per_share=0)
    assert "amount_per_share invalide" in evt3.validate()[0]
    evt4 = make_event(ca_type=models.CaType.SPLIT, split_from=0, split_to=2)
    errors = evt4.validate()
    assert any("split_from invalide" in e for e in errors)
    evt5 = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=0)
    errors = evt5.validate()
    assert any("split_to invalide" in e for e in errors)

# --- CorporateActionApplication ---
def test_corporate_action_application_immutability():
    app = models.CorporateActionApplication(
        event_id=1, symbol="AAPL", ca_type=models.CaType.SPLIT,
        position_qty_before=10, position_qty_after=20,
        cost_basis_before=100.0, cost_basis_after=50.0,
        cash_impact=0.0, fractional_shares=0.0
    )
    with pytest.raises(Exception):
        app.symbol = "MSFT"

# --- CashLedgerEntry ---
def test_cash_ledger_entry_defaults():
    entry = models.CashLedgerEntry(event_id=1, symbol="AAPL", entry_type="dividend", amount=10.0)
    assert entry.currency == "USD"
    assert entry.description is None

def test_cash_ledger_entry_immutability():
    entry = models.CashLedgerEntry(event_id=1, symbol="AAPL", entry_type="dividend", amount=10.0)
    with pytest.raises(Exception):
        entry.amount = 20.0

# --- PositionSnapshot ---
def test_position_snapshot_defaults():
    snap = models.PositionSnapshot(symbol="AAPL", qty=10, avg_entry_price=100.0)
    assert snap.market_value == 0.0
    snap.market_value = 123.45
    assert snap.market_value == 123.45

