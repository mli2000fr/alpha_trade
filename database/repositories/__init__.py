"""Façade ``database/repositories/`` — Phase 2.2 du refactor.

Chaque sous-module expose un *Repository* typé qui implémente le Protocol
correspondant défini dans ``core/interfaces.py``. Les modules historiques
(``database/assets.py``, ``stock_scores.py``, ``selector_reference.py``,
``run_business_summaries.py``) restent fonctionnels : les repositories
délèguent à leurs helpers existants pour préserver la rétrocompatibilité.

Migration progressive prévue dans les Phases 3.x (consommateurs métier
basculent vers les repositories au fil de leurs propres refactos).

Usage :

    from database.repositories import (
        AssetsRepository, BarsRepository, RunSummariesRepository,
        ScoresRepository, QuotesRepository,
    )

    repo = ScoresRepository()
    candidates = repo.list_candidates(limit=200)
"""
from __future__ import annotations

from database.repositories.assets import AssetsRepository
from database.repositories.bars import BarsRepository
from database.repositories.quotes import QuotesRepository
from database.repositories.run_summaries import RunSummariesRepository
from database.repositories.scores import ScoresRepository

__all__ = [
    "AssetsRepository",
    "BarsRepository",
    "QuotesRepository",
    "RunSummariesRepository",
    "ScoresRepository",
]

