"""common/data_availability.py — Contrat Point-In-Time (PIT) pour les données.

Sprint Maître 2 :
- Définit le contrat de disponibilité temporelle : chaque donnée porte
  ``event_time``, ``available_at``, ``source``, ``source_revision``,
  ``ingested_at`` et ``timezone``.
- ``available_at <= decision_cutoff`` est la règle non négociable.
- Les valeurs manquantes sont remplacées par des états de qualité explicites
  (``QualityState``) — jamais de NaN sentinelle ambiguë.
- Fournit le rapport quotidien de couverture et fraîcheur.

Usage ::

    from common.data_availability import (
        DataAvailabilityInfo,
        QualityState,
        validate_availability,
        build_daily_quality_report,
    )

    avail = DataAvailabilityInfo(
        event_time=datetime(...),
        available_at=datetime(...),
        source="eodhd",
    )
    validate_availability(avail, decision_cutoff)  # lève si future data
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

LOGGER = logging.getLogger(__name__)


# ── Quality states — remplacent les NaN sentinelles ─────────────────────────

class QualityState(str, Enum):
    """État de qualité explicite pour une donnée.

    Remplace les NaN / None ambigus par des codes stables et auditables.
    """

    PRESENT = "present"               # donnée disponible et valide
    MISSING_STALE = "missing_stale"   # donnée absente car trop ancienne
    MISSING_NO_SOURCE = "missing_no_source"  # aucune source n'a cette donnée
    MISSING_ERROR = "missing_error"   # erreur lors de l'ingestion
    NOT_YET_AVAILABLE = "not_yet_available"  # pas encore publiée (PIT)
    DELISTED = "delisted"             # symbole radié
    HALTED = "halted"                 # trading suspendu
    UNKNOWN = "unknown"               # qualité indéterminée (fallback)


# ── Data availability contract ──────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class DataAvailabilityInfo:
    """Contrat de disponibilité temporelle d'une donnée.

    Chaque observation utilisée pour une prédiction DOIT avoir ce
    contrat renseigné (ou un équivalent dans sa table de provenance).

    Attributes
    ----------
    event_time : datetime
        Moment auquel l'événement sous-jacent s'est produit (ex. clôture).
    available_at : datetime
        Moment à partir duquel la donnée est disponible pour consommation.
        Règle : ``available_at <= decision_cutoff``.
    source : str
        Identifiant de la source (ex. ``"eodhd"``, ``"finnhub"``, ``"alpaca"``).
    source_revision : str | None
        Révision/version de la source (ex. tag de release).
    ingested_at : datetime | None
        Moment où la donnée a été ingérée dans le système.
    timezone : str
        Timezone IANA (ex. ``"America/New_York"``).
    quality : QualityState
        État de qualité de la donnée.
    """

    event_time: datetime
    available_at: datetime
    source: str
    source_revision: str | None = None
    ingested_at: datetime | None = None
    timezone: str = "America/New_York"
    quality: QualityState = QualityState.PRESENT

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source est obligatoire.")
        if self.available_at.tzinfo is None:
            object.__setattr__(self, "available_at", self.available_at.replace(tzinfo=timezone.utc))
        if self.event_time.tzinfo is None:
            object.__setattr__(self, "event_time", self.event_time.replace(tzinfo=timezone.utc))
        if self.ingested_at is not None and self.ingested_at.tzinfo is None:
            object.__setattr__(self, "ingested_at", self.ingested_at.replace(tzinfo=timezone.utc))
        if self.available_at < self.event_time:
            raise ValueError(
                f"available_at ({self.available_at}) ne peut pas être "
                f"antérieur à event_time ({self.event_time})."
            )


# ── Validation ──────────────────────────────────────────────────────────────

class FutureDataError(RuntimeError):
    """Levée quand une donnée future est détectée (violation PIT)."""

    def __init__(self, availability: DataAvailabilityInfo, cutoff: datetime) -> None:
        self.availability = availability
        self.cutoff = cutoff
        super().__init__(
            f"Donnée future détectée : available_at={availability.available_at} "
            f"> decision_cutoff={cutoff} (source={availability.source})"
        )


class StaleDataError(RuntimeError):
    """Levée quand une donnée critique est trop ancienne."""

    def __init__(self, availability: DataAvailabilityInfo, max_age_hours: float) -> None:
        self.availability = availability
        self.max_age_hours = max_age_hours
        super().__init__(
            f"Donnée stale : age={(datetime.now(timezone.utc) - availability.available_at).total_seconds() / 3600:.1f}h "
            f"> max={max_age_hours}h (source={availability.source})"
        )


def validate_availability(
    availability: DataAvailabilityInfo,
    decision_cutoff: datetime,
    *,
    max_age_hours: float | None = None,
) -> None:
    """Valide qu'une donnée est disponible et pas trop ancienne.

    Parameters
    ----------
    availability : DataAvailabilityInfo
    decision_cutoff : datetime
        Cutoff de la décision (les données doivent être disponibles avant).
    max_age_hours : float | None
        Si renseigné, lève ``StaleDataError`` si la donnée est plus vieille.

    Raises
    ------
    FutureDataError
        Si ``available_at > decision_cutoff``.
    StaleDataError
        Si la donnée est trop ancienne (critique uniquement).
    """
    # Règle PIT non négociable
    if availability.available_at > decision_cutoff:
        raise FutureDataError(availability, decision_cutoff)

    # Règle de fraîcheur (optionnelle, pour données critiques)
    if max_age_hours is not None:
        age = (decision_cutoff - availability.available_at).total_seconds() / 3600.0
        if age > max_age_hours:
            raise StaleDataError(availability, max_age_hours)


def validate_availability_or_degraded(
    availability: DataAvailabilityInfo,
    decision_cutoff: datetime,
    *,
    max_age_hours: float | None = None,
    critical: bool = True,
) -> QualityState:
    """Valide et retourne l'état de qualité effectif.

    Pour les données non critiques, une violation de fraîcheur
    dégrade l'état mais ne bloque pas.

    Parameters
    ----------
    availability : DataAvailabilityInfo
    decision_cutoff : datetime
    max_age_hours : float | None
    critical : bool
        Si True, les violations lèvent une exception. Si False, dégradent.

    Returns
    -------
    QualityState
        État effectif après validation.
    """
    # Future data → toujours bloquant
    if availability.available_at > decision_cutoff:
        if critical:
            raise FutureDataError(availability, decision_cutoff)
        return QualityState.NOT_YET_AVAILABLE

    # Stale → bloquant si critique, dégradé sinon
    if max_age_hours is not None:
        age = (decision_cutoff - availability.available_at).total_seconds() / 3600.0
        if age > max_age_hours:
            if critical:
                raise StaleDataError(availability, max_age_hours)
            return QualityState.MISSING_STALE

    return availability.quality


# ── Rapport quotidien de couverture et fraîcheur ────────────────────────────

@dataclass
class DailyQualityReport:
    """Rapport quotidien de qualité des données (Sprint Maître 2)."""

    report_date: str  # ISO date
    total_symbols: int
    symbols_with_data: int
    symbols_missing_data: int
    symbols_stale_data: int
    symbols_with_future_data: int
    coverage_ratio: float
    quality_by_source: dict[str, dict[str, int]]
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_date": self.report_date,
            "total_symbols": self.total_symbols,
            "symbols_with_data": self.symbols_with_data,
            "symbols_missing_data": self.symbols_missing_data,
            "symbols_stale_data": self.symbols_stale_data,
            "symbols_with_future_data": self.symbols_with_future_data,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "quality_by_source": self.quality_by_source,
            "alerts": self.alerts,
        }


def build_daily_quality_report(
    symbols: list[str],
    availability_map: dict[str, DataAvailabilityInfo],
    decision_cutoff: datetime,
    *,
    max_age_hours: float = 24.0,
) -> DailyQualityReport:
    """Produit le rapport quotidien de couverture et fraîcheur.

    Parameters
    ----------
    symbols : list[str]
        Liste des symboles de l'univers.
    availability_map : dict[str, DataAvailabilityInfo]
        Infos de disponibilité par symbole.
    decision_cutoff : datetime
        Cutoff de la décision.
    max_age_hours : float
        Âge maximal avant de considérer une donnée comme stale.

    Returns
    -------
    DailyQualityReport
    """
    total = len(symbols)
    with_data = 0
    missing = 0
    stale = 0
    future = 0
    quality_by_source: dict[str, dict[str, int]] = {}
    alerts: list[str] = []

    for sym in symbols:
        avail = availability_map.get(sym)
        if avail is None:
            missing += 1
            alerts.append(f"missing_data:{sym}")
            continue

        # Comptage par source/qualité
        source = avail.source
        quality = avail.quality.value
        if source not in quality_by_source:
            quality_by_source[source] = {}
        quality_by_source[source][quality] = quality_by_source[source].get(quality, 0) + 1

        # Vérifications PIT
        if avail.available_at > decision_cutoff:
            future += 1
            alerts.append(f"future_data:{sym}:{avail.source}")
            continue

        age_h = (decision_cutoff - avail.available_at).total_seconds() / 3600.0
        if age_h > max_age_hours:
            stale += 1
            alerts.append(f"stale_data:{sym}:{avail.source}:{age_h:.1f}h")
            continue

        with_data += 1

    coverage = with_data / total if total > 0 else 0.0

    if coverage < 0.90:
        alerts.append(f"low_coverage:{coverage:.1%}")

    if future > 0:
        alerts.append(f"FUTURE_DATA_DETECTED:{future}_symbols")

    return DailyQualityReport(
        report_date=decision_cutoff.strftime("%Y-%m-%d"),
        total_symbols=total,
        symbols_with_data=with_data,
        symbols_missing_data=missing,
        symbols_stale_data=stale,
        symbols_with_future_data=future,
        coverage_ratio=coverage,
        quality_by_source=quality_by_source,
        alerts=alerts,
    )


# ── Helpers pour l'intégration ──────────────────────────────────────────────

def make_availability_from_bar_date(
    bar_date: str | Any,
    source: str = "eodhd",
    *,
    market_close_hour_utc: int = 21,  # 16:00 ET = 21:00 UTC
) -> DataAvailabilityInfo:
    """Construit un DataAvailabilityInfo à partir d'une date de barre quotidienne.

    Suppose que la barre est disponible après la clôture du marché (21:00 UTC).
    """
    import pandas as pd

    if isinstance(bar_date, pd.Timestamp):
        event_dt = bar_date.to_pydatetime()
    elif isinstance(bar_date, str):
        event_dt = pd.Timestamp(bar_date).to_pydatetime()
    else:
        event_dt = pd.Timestamp(str(bar_date)).to_pydatetime()

    # La donnée est disponible le soir même après clôture
    available_dt = event_dt.replace(hour=market_close_hour_utc, minute=0, second=0, microsecond=0)
    if available_dt < event_dt:
        # Si event_time a déjà une heure > close, on ajoute un jour
        from datetime import timedelta
        available_dt = (event_dt + timedelta(days=1)).replace(
            hour=market_close_hour_utc, minute=0, second=0, microsecond=0,
        )

    return DataAvailabilityInfo(
        event_time=event_dt.replace(tzinfo=timezone.utc),
        available_at=available_dt.replace(tzinfo=timezone.utc),
        source=source,
        timezone="America/New_York",
    )
