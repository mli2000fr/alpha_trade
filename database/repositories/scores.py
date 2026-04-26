"""Repository ``stock_scores`` (Phase 2.2)."""
from __future__ import annotations

import pandas as pd

from database import stock_scores as _legacy
from database.repositories._base import Repository


class ScoresRepository(Repository):
    """Repository ``stock_scores`` (snapshot screener / selector).

    Implémente le Protocol :class:`core.ScoresRepository` (pour la partie
    lecture). L'``upsert_scores`` reste à brancher Phase 3.2 quand le
    screener migrera vers cette façade.
    """

    def list_candidates(self, *, limit: int | None = None) -> list[str]:
        return _legacy.list_candidate_symbols(engine=self.engine, limit=limit)

    def upsert_scores(self, scores: pd.DataFrame) -> int:  # pragma: no cover - Phase 3.2
        raise NotImplementedError(
            "upsert_scores sera implémenté en Phase 3.2 (migration screener)."
        )

