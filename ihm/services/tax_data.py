"""Sprint S19.4 — Service IHM ``tax_data``.

Adapter mince (sans logique métier dans la page) qui fournit les lots
``tax.wash_sale.Lot`` à partir de la base ou d'un payload de
démonstration. La page ``tax_compliance`` ne consomme QUE ce service.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence

from tax.wash_sale import Lot, WashSaleReport, detect_wash_sales


@dataclass(frozen=True, slots=True)
class TaxLotRow:
    """Représentation table-friendly d'un lot pour l'IHM."""

    lot_id: str
    symbol: str
    trade_date: date
    qty: float
    price: float
    side: str  # "BUY" / "SELL"


def lot_to_row(lot: Lot) -> TaxLotRow:
    return TaxLotRow(
        lot_id=lot.lot_id,
        symbol=lot.symbol,
        trade_date=lot.trade_date,
        qty=lot.qty,
        price=lot.price,
        side="BUY" if lot.is_acquisition else "SELL",
    )


def load_demo_lots() -> list[Lot]:
    """Jeu de démo (utilisé tant que le câblage DB ``fills`` n'est pas
    branché — voir S21.4 du plan 28).
    """
    today = date.today()
    return [
        Lot("demo-001", "AAPL", today - timedelta(days=45), 100, 180.0),
        Lot("demo-002", "AAPL", today - timedelta(days=20), -50, 170.0),
        Lot("demo-003", "AAPL", today - timedelta(days=10), 50, 175.0),
        Lot("demo-004", "MSFT", today - timedelta(days=60), 30, 410.0),
        Lot("demo-005", "MSFT", today - timedelta(days=5), -30, 400.0),
    ]


def filter_lots(
    lots: Iterable[Lot],
    *,
    symbol: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Lot]:
    out: list[Lot] = []
    for lot in lots:
        if symbol and lot.symbol != symbol:
            continue
        if date_from and lot.trade_date < date_from:
            continue
        if date_to and lot.trade_date > date_to:
            continue
        out.append(lot)
    return out


def compute_report(lots: Sequence[Lot]) -> WashSaleReport:
    return detect_wash_sales(list(lots))


def lots_to_table(lots: Sequence[Lot], report: WashSaleReport) -> list[dict]:
    """Sérialise pour ``st.dataframe`` (avec flag wash sale)."""
    flagged_sales = {a.sale_lot_id for a in report.adjustments}
    flagged_replacements = {a.replacement_lot_id for a in report.adjustments}
    rows: list[dict] = []
    for lot in lots:
        wash_flag = ""
        if lot.lot_id in flagged_sales:
            wash_flag = "⚠️ wash sale"
        elif lot.lot_id in flagged_replacements:
            wash_flag = "↩️ remplacement"
        rows.append(
            {
                "lot_id": lot.lot_id,
                "symbol": lot.symbol,
                "trade_date": lot.trade_date.isoformat(),
                "side": "BUY" if lot.is_acquisition else "SELL",
                "qty": lot.qty,
                "price": lot.price,
                "wash_sale": wash_flag,
                "adjusted_cost_basis": report.adjusted_cost_basis.get(lot.lot_id, 0.0),
            }
        )
    return rows

