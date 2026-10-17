"""Repository ``stock_quote_snapshots`` (Phase 2.2)."""
from __future__ import annotations

from database import selector_reference as _legacy
from database.repositories._base import Repository


class QuotesRepository(Repository):
    """Snapshots bid/ask avec provenance ; IEX n'est pas un NBBO consolidé."""

    def get_table(self):  # pragma: no cover - thin wrapper
        return _legacy.get_stock_quote_snapshots_table()

