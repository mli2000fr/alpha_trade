"""Repository ``run_business_summaries`` (Phase 2.2)."""
from __future__ import annotations

from typing import Mapping

from database import run_business_summaries as _legacy
from database.repositories._base import Repository


class RunSummariesRepository(Repository):
    """Repository des ``run_summary`` (helper d'émission centralisé)."""

    def emit(self, summary: Mapping[str, object]) -> None:
        """Émet un ``run_summary`` (helper imprime sur stdout préfixé).

        Le helper :func:`database.run_business_summaries.emit_run_summary`
        ajoute ``schema_version`` (cf. Phase 1.3) avant sérialisation.
        """
        return _legacy.emit_run_summary(summary)


