"""Phase C / S16.3 — Tests détecteur wash sale."""
from __future__ import annotations

from datetime import date

from tax import Lot, detect_wash_sales


def test_no_loss_no_wash_sale():
    lots = [
        Lot("buy1", "AAPL", date(2026, 1, 5), 100, 100.0),
        Lot("sell1", "AAPL", date(2026, 1, 20), -100, 110.0),  # gain
    ]
    r = detect_wash_sales(lots)
    assert r.adjustments == []


def test_wash_sale_with_replacement_within_30_days():
    lots = [
        Lot("buy1", "AAPL", date(2026, 1, 1), 100, 100.0),
        Lot("sell1", "AAPL", date(2026, 1, 20), -100, 90.0),  # perte 10/share
        Lot("buy2", "AAPL", date(2026, 2, 5), 50, 95.0),       # +16 j → wash
    ]
    r = detect_wash_sales(lots)
    assert len(r.adjustments) == 1
    a = r.adjustments[0]
    assert a.sale_lot_id == "sell1"
    assert a.replacement_lot_id == "buy2"
    assert a.disallowed_loss == 10.0 * 100  # (100 - 90) * 100


def test_no_wash_sale_when_replacement_outside_window():
    lots = [
        Lot("buy1", "AAPL", date(2025, 10, 1), 100, 100.0),  # >30j avant vente
        Lot("sell1", "AAPL", date(2026, 1, 20), -100, 90.0),
        Lot("buy2", "AAPL", date(2026, 3, 15), 50, 95.0),    # +54 j → hors fenêtre
    ]
    pnl = {"sell1": -1000.0}
    r = detect_wash_sales(lots, realized_pnl_per_sale=pnl)
    assert r.adjustments == []


def test_explicit_pnl_input():
    lots = [
        Lot("buy1", "AAPL", date(2026, 1, 1), 100, 100.0),
        Lot("sell1", "AAPL", date(2026, 1, 15), -100, 80.0),
        Lot("buy2", "AAPL", date(2026, 1, 20), 100, 82.0),
    ]
    pnl = {"sell1": -2000.0}
    r = detect_wash_sales(lots, realized_pnl_per_sale=pnl)
    assert len(r.adjustments) == 1
    assert r.adjustments[0].disallowed_loss == 2000.0
    assert r.adjusted_cost_basis["buy2"] == 2000.0
    assert r.total_disallowed_loss == 2000.0


