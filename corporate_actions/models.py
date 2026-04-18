"""Modèles de données pour le module corporate_actions."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


# ---------------------------------------------------------------------------
# Types de corporate actions supportés
# ---------------------------------------------------------------------------

class CaType:
    CASH_DIVIDEND = "cash_dividend"
    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    SPECIAL_DIVIDEND = "special_dividend"
    ALL = frozenset({CASH_DIVIDEND, SPLIT, REVERSE_SPLIT, SPECIAL_DIVIDEND})


class CaStatus:
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Événement corporate action (brut, ingéré depuis un provider)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CorporateActionEvent:
    """Événement corporate action tel qu'ingéré depuis un provider."""
    provider: str
    provider_event_id: str | None
    symbol: str
    ca_type: str
    ex_date: date
    # Dividendes
    amount_per_share: float | None = None
    currency: str = "USD"
    # Splits
    split_from: int | None = None
    split_to: int | None = None
    # Dates optionnelles
    announcement_date: date | None = None
    record_date: date | None = None
    payable_date: date | None = None
    # Payload brut
    raw_payload: dict[str, Any] | None = None
    # État (rempli par le système)
    id: int | None = None
    status: str = CaStatus.PENDING
    error_message: str | None = None
    ingested_at: datetime | None = None
    applied_at: datetime | None = None

    @property
    def idempotency_key(self) -> str:
        """Clé d'idempotence déterministe SHA-256 tronquée à 32 chars."""
        if self.ca_type in (CaType.SPLIT, CaType.REVERSE_SPLIT):
            payload = f"{self.provider}|{self.symbol}|{self.ca_type}|{self.ex_date}|{self.split_from}:{self.split_to}"
        else:
            payload = f"{self.provider}|{self.symbol}|{self.ca_type}|{self.ex_date}|{self.amount_per_share}"
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    @property
    def split_ratio(self) -> float:
        """Ratio multiplicateur pour les splits (ex: 2.0 pour 2:1, 0.1 pour 1:10 reverse)."""
        if self.split_from and self.split_to and self.split_from > 0:
            return self.split_to / self.split_from
        return 1.0

    def validate(self) -> list[str]:
        """Retourne la liste des erreurs de validation (vide = valide)."""
        errors: list[str] = []
        if self.ca_type not in CaType.ALL:
            errors.append(f"ca_type inconnu: {self.ca_type}")
        if not self.symbol or not self.symbol.strip():
            errors.append("symbol manquant")
        if self.ca_type in (CaType.CASH_DIVIDEND, CaType.SPECIAL_DIVIDEND):
            if self.amount_per_share is None or self.amount_per_share <= 0:
                errors.append(f"amount_per_share invalide pour {self.ca_type}: {self.amount_per_share}")
        if self.ca_type in (CaType.SPLIT, CaType.REVERSE_SPLIT):
            if not self.split_from or self.split_from <= 0:
                errors.append(f"split_from invalide: {self.split_from}")
            if not self.split_to or self.split_to <= 0:
                errors.append(f"split_to invalide: {self.split_to}")
        return errors


# ---------------------------------------------------------------------------
# Application d'un corporate action (trace d'effet)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CorporateActionApplication:
    """Trace immuable d'un ajustement effectif sur une position."""
    event_id: int
    symbol: str
    ca_type: str
    position_qty_before: float
    position_qty_after: float
    cost_basis_before: float | None
    cost_basis_after: float | None
    cash_impact: float = 0.0
    fractional_shares: float = 0.0


# ---------------------------------------------------------------------------
# Entrée du cash ledger
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CashLedgerEntry:
    """Entrée immuable dans le ledger cash."""
    event_id: int | None
    symbol: str
    entry_type: str
    amount: float
    currency: str = "USD"
    description: str | None = None


# ---------------------------------------------------------------------------
# Position snapshot (pour le processing)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PositionSnapshot:
    """État d'une position pour le traitement corporate actions."""
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float = 0.0


