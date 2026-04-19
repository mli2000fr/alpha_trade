"""Tests for execution_engine.reconciliation."""
from __future__ import annotations

from datetime import date
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from corporate_actions import reconciliation


# --- Tests pour corporate_actions.reconciliation ---
def test_reconcile_exact_match():
    internal = {"AAPL": 10.0, "MSFT": 5.0}
    broker = [
        {"symbol": "AAPL", "qty": 10.0},
        {"symbol": "MSFT", "qty": 5.0},
    ]
    diffs = reconciliation.reconcile_after_corporate_actions(internal, broker)
    assert all(d.action == "ok" for d in diffs)
    assert len(diffs) == 2
    assert diffs[0].delta == 0
    assert diffs[1].delta == 0

def test_reconcile_qty_mismatch():
    internal = {"AAPL": 10.0}
    broker = [
        {"symbol": "AAPL", "qty": 12.0},
    ]
    diffs = reconciliation.reconcile_after_corporate_actions(internal, broker, tolerance=0.5)
    assert len(diffs) == 1
    assert diffs[0].action == "qty_mismatch"
    assert diffs[0].delta == 2.0

def test_reconcile_investigate():
    internal = {"AAPL": 10.0}
    broker = [
        {"symbol": "AAPL", "qty": 10.0},
        {"symbol": "TSLA", "qty": 3.0},
    ]
    diffs = reconciliation.reconcile_after_corporate_actions(internal, broker)
    tsla = next(d for d in diffs if d.symbol == "TSLA")
    assert tsla.action == "investigate"
    assert tsla.internal_qty == 0.0
    assert tsla.broker_qty == 3.0

def test_reconcile_tolerance():
    internal = {"AAPL": 10.0}
    broker = [
        {"symbol": "AAPL", "qty": 10.005},
    ]
    diffs = reconciliation.reconcile_after_corporate_actions(internal, broker, tolerance=0.01)
    assert diffs[0].action == "ok"
    diffs2 = reconciliation.reconcile_after_corporate_actions(internal, broker, tolerance=0.001)
    assert diffs2[0].action == "qty_mismatch"

def test_reconcile_missing_broker():
    internal = {"AAPL": 10.0, "MSFT": 5.0}
    broker = [
        {"symbol": "AAPL", "qty": 10.0},
    ]
    diffs = reconciliation.reconcile_after_corporate_actions(internal, broker)
    msft = next(d for d in diffs if d.symbol == "MSFT")
    assert msft.broker_qty == 0.0
    assert msft.internal_qty == 5.0
    assert msft.action == "qty_mismatch"
