"""Repository ``stock_quote_snapshots`` (Phase 2.2)."""
from __future__ import annotations

from database import selector_reference as _legacy
from database.repositories._base import Repository


class QuotesRepository(Repository):
    """Repository des snapshots de quotes IEX (NBBO)."""

    def get_table(self):  # pragma: no cover - thin wrapper
        return _legacy.get_stock_quote_snapshots_table()

