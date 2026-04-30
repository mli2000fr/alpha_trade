"""Repository ``stock_metadata`` (Phase 2.2).

Façade orientée objet sur les helpers de ``database/assets.py``.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from database import assets as _legacy
from database.repositories._base import Repository


class AssetsRepository(Repository):
    """Repository ``stock_metadata`` (assets univers Alpaca).

    Délègue aux helpers historiques pour préserver la compatibilité ;
    sera étoffé Phase 3.1 (filtres TTL ``market_cap_refreshed_at``).
    """

    def list_eligible_symbols(self, *, limit: int | None = None) -> list[str]:
        return _legacy.list_eligible_stock_symbols(limit=limit, engine=self.engine)

    def get_symbols_missing_sector(self, *, limit: int | None = None) -> list[str]:
        return _legacy.get_symbols_missing_sector(limit=limit)

    def get_symbols_missing_fundamentals(self, *, limit: int | None = None) -> list[str]:
        return _legacy.get_symbols_missing_fundamentals(limit=limit)

    def list_stale_market_cap(self, *, max_age_days: int, limit: int | None = None) -> list[str]:
        """Phase 3.1.e — symboles dont ``market_cap_refreshed_at`` est périmé."""
        return _legacy.get_symbols_with_stale_market_cap(
            max_age_days=max_age_days, limit=limit
        )

    def count_stale_market_cap(self, *, max_age_days: int) -> tuple[int, int]:
        """Phase 3.1.e — ``(stale_count, eligible_total)`` pour ``stale_market_cap_pct``."""
        return _legacy.count_eligible_symbols_with_stale_market_cap(max_age_days=max_age_days)

    def update_fundamentals(
        self,
        symbol: str,
        *,
        sector: str | None = None,
        market_cap: float | None = None,
    ) -> int:
        return _legacy.update_stock_metadata_fundamentals(
            symbol, sector=sector, market_cap=market_cap
        )

    def insert_assets(self, assets: Iterable[Mapping[str, object]]) -> int:
        return _legacy.insert_assets_to_db(assets)

    def mark_history_status(
        self,
        symbol: str,
        history_status: str,
        *,
        bars_available: bool | None = None,
    ) -> int:
        return _legacy.update_symbol_history_status(
            symbol, history_status, bars_available=bars_available
        )

