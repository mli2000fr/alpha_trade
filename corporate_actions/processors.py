"""Processeurs métier pour dividendes et splits."""
from __future__ import annotations

import logging
import math

from corporate_actions.models import (
    CaType,
    CashLedgerEntry,
    CorporateActionApplication,
    CorporateActionEvent,
    PositionSnapshot,
)

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dividendes
# ---------------------------------------------------------------------------

def process_dividend(
    event: CorporateActionEvent,
    position: PositionSnapshot,
) -> tuple[CorporateActionApplication, CashLedgerEntry]:
    """
    Traite un dividende cash sur une position existante.

    Retourne:
        - CorporateActionApplication (trace d'ajustement — qty inchangée)
        - CashLedgerEntry (crédit cash)
    """
    assert event.ca_type in (CaType.CASH_DIVIDEND, CaType.SPECIAL_DIVIDEND)
    assert event.amount_per_share is not None and event.amount_per_share > 0
    assert event.id is not None

    cash_amount = round(position.qty * event.amount_per_share, 2)

    application = CorporateActionApplication(
        event_id=event.id,
        symbol=event.symbol,
        ca_type=event.ca_type,
        position_qty_before=position.qty,
        position_qty_after=position.qty,  # unchanged
        cost_basis_before=position.avg_entry_price,
        cost_basis_after=position.avg_entry_price,  # unchanged
        cash_impact=cash_amount,
    )
    ledger = CashLedgerEntry(
        event_id=event.id,
        symbol=event.symbol,
        entry_type="dividend_credit",
        amount=cash_amount,
        currency=event.currency,
        description=f"Dividend {event.amount_per_share}/share × {position.qty} shares",
    )
    LOGGER.info(
        "Dividend processed | symbol=%s amount_per_share=%.4f qty=%.2f total=%.2f",
        event.symbol, event.amount_per_share, position.qty, cash_amount,
    )
    return application, ledger


# ---------------------------------------------------------------------------
# Splits / Reverse splits
# ---------------------------------------------------------------------------

def process_split(
    event: CorporateActionEvent,
    position: PositionSnapshot,
) -> tuple[CorporateActionApplication, CashLedgerEntry | None]:
    """
    Traite un split (ou reverse split) sur une position existante.

    Le split ajuste :
    - la quantité de parts : qty_new = qty_old × ratio
    - le cost basis : cost_new = cost_old / ratio
    La valeur totale de la position reste économiquement identique.

    En cas de fractions (reverse split), la partie fractionnaire
    est convertie en cash-in-lieu.

    Retourne:
        - CorporateActionApplication
        - CashLedgerEntry (cash-in-lieu si fractions, sinon None)
    """
    assert event.ca_type in (CaType.SPLIT, CaType.REVERSE_SPLIT)
    assert event.id is not None

    ratio = event.split_ratio
    raw_new_qty = position.qty * ratio
    # Pour les splits entiers, on arrondit. Pour les reverse splits on prend le floor.
    if ratio >= 1.0:
        new_qty = round(raw_new_qty, 6)
        fractional = 0.0
    else:
        new_qty = math.floor(raw_new_qty)
        fractional = raw_new_qty - new_qty

    new_cost_basis = (
        round(position.avg_entry_price / ratio, 6)
        if position.avg_entry_price and ratio != 0
        else position.avg_entry_price
    )

    # Cash-in-lieu pour les fractions
    cash_in_lieu = 0.0
    ledger_entry: CashLedgerEntry | None = None
    if fractional > 0.001:
        # Estimation : fraction × cost_basis_before (approximation raisonnable)
        cash_in_lieu = round(fractional * (position.avg_entry_price or 0), 2)
        ledger_entry = CashLedgerEntry(
            event_id=event.id,
            symbol=event.symbol,
            entry_type="cash_in_lieu",
            amount=cash_in_lieu,
            description=f"Cash-in-lieu for {fractional:.6f} fractional shares from {event.ca_type} {event.split_from}:{event.split_to}",
        )

    application = CorporateActionApplication(
        event_id=event.id,
        symbol=event.symbol,
        ca_type=event.ca_type,
        position_qty_before=position.qty,
        position_qty_after=new_qty,
        cost_basis_before=position.avg_entry_price,
        cost_basis_after=new_cost_basis,
        cash_impact=cash_in_lieu,
        fractional_shares=fractional,
    )

    LOGGER.info(
        "Split processed | symbol=%s ratio=%s qty=%.2f→%.2f cost=%.4f→%.4f fractional=%.6f",
        event.symbol, f"{event.split_from}:{event.split_to}",
        position.qty, new_qty,
        position.avg_entry_price or 0, new_cost_basis or 0, fractional,
    )
    return application, ledger_entry

