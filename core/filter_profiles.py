"""Façade centrale pour les profils de filtres swing cash.

Phase 2.1 du refactor (`prompt/refactor/plan.md`).

Le profil canonique :data:`STRICT_SWING_CASH_FILTERS` est défini dans
``selector/strict_filter_profiles.py``. Ce module sert de **façade
publique** pour permettre aux modules amont (screener, backtesting,
event_sentiment) d'importer le profil sans dépendance directe vers
``selector/`` :

    from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile

La migration progressive des call-sites historiques se fait dans les
Phases 3.2 (screener) et 3.3 (selector).
"""
from __future__ import annotations

from selector.strict_filter_profiles import (
    STRICT_SWING_CASH_FILTERS,
    StrictFilterProfile,
)

__all__ = ["STRICT_SWING_CASH_FILTERS", "StrictFilterProfile"]

