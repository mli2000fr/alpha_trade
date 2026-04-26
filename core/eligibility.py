"""Façade pour les filtres SQL d'éligibilité ``stock_metadata``.

Phase 2.1 du refactor (`prompt/refactor/plan.md`, audit_database §6).

Le helper :func:`build_eligible_stock_metadata_filters` est aujourd'hui
défini dans ``database/assets.py``. Cette façade existe pour découpler les
modules amont (`screener`, `selector`, `dataIntegrityEngine`,
`corporate_actions`) de l'implémentation DB et préparer la migration
Phase 2.2 vers ``database/repositories/assets.py``.
"""
from __future__ import annotations

from database.assets import (
    ELIGIBLE_HISTORY_STATUSES,
    HISTORY_STATUS_EXCLUDED_BY_POLICY,
    HISTORY_STATUS_NO_HISTORY,
    HISTORY_STATUS_PENDING,
    HISTORY_STATUS_PROVIDER_ERROR,
    HISTORY_STATUS_READY,
    HISTORY_STATUS_SUSPENDED_OR_STALE,
    build_eligible_stock_metadata_filters,
)

__all__ = [
    "ELIGIBLE_HISTORY_STATUSES",
    "HISTORY_STATUS_EXCLUDED_BY_POLICY",
    "HISTORY_STATUS_NO_HISTORY",
    "HISTORY_STATUS_PENDING",
    "HISTORY_STATUS_PROVIDER_ERROR",
    "HISTORY_STATUS_READY",
    "HISTORY_STATUS_SUSPENDED_OR_STALE",
    "build_eligible_stock_metadata_filters",
]

