import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from corporate_actions import processors, models
from datetime import date

def make_event(**kwargs):
    base = dict(
        provider="alpaca",
        provider_event_id="evt1",
        symbol="AAPL",
        ca_type=models.CaType.CASH_DIVIDEND,
        ex_date=date(2024, 1, 1),
        amount_per_share=1.23,
        id=42,
    )
    base.update(kwargs)
    return models.CorporateActionEvent(**base)

def make_position(**kwargs):
    base = dict(symbol="AAPL", qty=10, avg_entry_price=100.0)
    base.update(kwargs)
    return models.PositionSnapshot(**base)

# --- process_dividend ---
def test_process_dividend_basic():
    evt = make_event()
    pos = make_position()
    app, ledger = processors.process_dividend(evt, pos)
    assert app.position_qty_before == app.position_qty_after == pos.qty
    assert app.cash_impact == ledger.amount
    assert ledger.entry_type == "dividend_credit"
    assert ledger.currency == evt.currency
    assert ledger.event_id == evt.id
    assert ledger.symbol == evt.symbol
    assert ledger.amount == round(pos.qty * evt.amount_per_share, 2)
    assert "Dividend" in ledger.description

def test_process_dividend_special():
    evt = make_event(ca_type=models.CaType.SPECIAL_DIVIDEND)
    pos = make_position()
    app, ledger = processors.process_dividend(evt, pos)
    assert app.cash_impact == ledger.amount
    assert app.ca_type == models.CaType.SPECIAL_DIVIDEND

def test_process_dividend_asserts():
    evt = make_event(amount_per_share=None)
    pos = make_position()
    with pytest.raises(AssertionError):
        processors.process_dividend(evt, pos)
    evt2 = make_event(amount_per_share=0)
    with pytest.raises(AssertionError):
        processors.process_dividend(evt2, pos)
    evt3 = make_event(id=None)
    with pytest.raises(AssertionError):
        processors.process_dividend(evt3, pos)

# --- process_split ---
def test_process_split_basic():
    evt = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=3)
    pos = make_position(qty=10, avg_entry_price=100.0)
    evt.id = 99
    app, ledger = processors.process_split(evt, pos)
    assert app.position_qty_after == 15
    assert app.fractional_shares == 0.0
    assert app.cash_impact == 0.0
    assert app.cost_basis_after == round(100.0 / 1.5, 6)
    assert ledger is None

def test_process_split_reverse_with_fraction():
    evt = make_event(ca_type=models.CaType.REVERSE_SPLIT, split_from=3, split_to=1)
    pos = make_position(qty=10, avg_entry_price=90.0)
    evt.id = 100
    app, ledger = processors.process_split(evt, pos)
    assert app.position_qty_after == 3
    assert app.fractional_shares == pytest.approx(0.333333, abs=1e-5)
    assert app.cash_impact == pytest.approx(30.0, abs=1e-2)
    assert ledger is not None
    assert ledger.entry_type == "cash_in_lieu"
    assert "fractional shares" in ledger.description
    assert ledger.amount == pytest.approx(30.0, abs=1e-2)

def test_process_split_asserts():
    evt = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=3, id=None)
    pos = make_position()
    with pytest.raises(AssertionError):
        processors.process_split(evt, pos)
    evt2 = make_event(ca_type=models.CaType.SPLIT, split_from=2, split_to=3)
    pos2 = make_position()
    evt2.ca_type = "not_a_split"
    with pytest.raises(AssertionError):
        processors.process_split(evt2, pos2)

def test_process_split_zero_ratio():
    evt = make_event(ca_type=models.CaType.SPLIT, split_from=0, split_to=0)
    pos = make_position()
    evt.id = 101
    # split_ratio = 1.0, pas d'ajustement
    app, ledger = processors.process_split(evt, pos)
    assert app.position_qty_after == pos.qty
    assert app.fractional_shares == 0.0
    assert app.cash_impact == 0.0
    assert ledger is None

