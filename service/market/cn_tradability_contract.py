"""Contrat PIT minimal pour le futur univers négociable CN_A.

Ce module ne publie pas encore l'univers Sprint 8. Il distingue la candidature
connue avant séance de la vérification rétrospective d'une séance exécutée.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


@dataclass(frozen=True)
class TradabilityAssessment:
    state: Literal["CANDIDATE", "EXCLUDED", "UNVERIFIABLE", "DATA_CHECKS_PASSED"]
    reason: str


def _known_at(available_at: datetime | None, decision_at: datetime) -> bool:
    return available_at is not None and available_at <= decision_at


def assess_pretrade(
    *,
    session_date: date,
    decision_at: datetime,
    listing_date: date | None,
    delisting_date: date | None,
    trading_status: str | None = None,
    status_available_at: datetime | None = None,
    limit_policy: str | None = None,
    limit_available_at: datetime | None = None,
) -> TradabilityAssessment:
    """N'utilise jamais un statut ou une limite encore inconnus à ``decision_at``.

    La date de radiation est inclusive : des barres existent ce jour-là pour
    une partie des titres radiés. « CANDIDATE » n'affirme pas qu'un ordre sera
    exécuté ; les vérifications de séance restent nécessaires.
    """
    if listing_date is None or session_date < listing_date:
        return TradabilityAssessment("EXCLUDED", "NOT_YET_LISTED_OR_UNKNOWN_LISTING")
    if delisting_date is not None and session_date > delisting_date:
        return TradabilityAssessment("EXCLUDED", "AFTER_DELISTING_DATE")
    if _known_at(status_available_at, decision_at) and trading_status:
        if "SOURCE_CONFLICT" in trading_status:
            return TradabilityAssessment("EXCLUDED", "SOURCE_STATUS_CONFLICT")
        if trading_status.startswith("SUSPENDED"):
            return TradabilityAssessment("EXCLUDED", "KNOWN_SUSPENSION")
    if _known_at(limit_available_at, decision_at) and limit_policy == "OBSERVED_OUTSIDE_DERIVED_LIMIT_V1":
        return TradabilityAssessment("EXCLUDED", "UNVERIFIED_PRICE_LIMIT")
    return TradabilityAssessment("CANDIDATE", "PRETRADE_PIT_CHECKS_PASSED")


def assess_execution_data(
    *,
    bar_present: bool,
    trading_status: str | None,
    limit_policy: str | None,
    locked_up: bool | None = None,
    locked_down: bool | None = None,
) -> TradabilityAssessment:
    """Qualifie les données de séance ; ne simule ni carnet ni ordre exécuté."""
    if not bar_present:
        return TradabilityAssessment("EXCLUDED", "NO_SESSION_BAR")
    if trading_status is None:
        return TradabilityAssessment("UNVERIFIABLE", "MISSING_TRADING_STATUS")
    if "SOURCE_CONFLICT" in trading_status:
        return TradabilityAssessment("EXCLUDED", "SOURCE_STATUS_CONFLICT")
    if trading_status.startswith("SUSPENDED"):
        return TradabilityAssessment("EXCLUDED", "SUSPENDED_SESSION")
    if limit_policy is None or limit_policy == "OBSERVED_OUTSIDE_DERIVED_LIMIT_V1":
        return TradabilityAssessment("UNVERIFIABLE", "UNVERIFIED_PRICE_LIMIT")
    if locked_up or locked_down:
        return TradabilityAssessment("UNVERIFIABLE", "LOCKED_LIMIT_SIDE_DEPENDENT")
    return TradabilityAssessment("DATA_CHECKS_PASSED", "EXECUTION_DATA_CHECKS_PASSED")
