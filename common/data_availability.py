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
from datetime import datetime, timezone as _tz
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
            object.__setattr__(self, "available_at", self.available_at.replace(tzinfo=_tz.utc))
        if self.event_time.tzinfo is None:
            object.__setattr__(self, "event_time", self.event_time.replace(tzinfo=_tz.utc))
        if self.ingested_at is not None and self.ingested_at.tzinfo is None:
            object.__setattr__(self, "ingested_at", self.ingested_at.replace(tzinfo=_tz.utc))
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
            f"Donnée stale : age={(datetime.now(_tz.utc) - availability.available_at).total_seconds() / 3600:.1f}h "
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


# ── Universal PIT enrichment helper (Section 17 Point 2.1) ─────────────────

def enrich_dataframe_with_pit(
    df: "pd.DataFrame",
    *,
    source: str,
    event_time_col: str | None = None,
    available_at_col: str | None = None,
    default_available_at: datetime | None = None,
    source_revision: str | None = None,
    ingested_at: datetime | None = None,
    tz_name: str = "America/New_York",
    quality: QualityState = QualityState.PRESENT,
    date_col: str = "date",
    available_at_hour_utc: int = 21,
) -> "pd.DataFrame":
    """Enrichit un DataFrame avec les colonnes PIT canoniques.

    Conçu pour être appelé par TOUS les loaders de données afin que chaque
    DataFrame porte systématiquement les métadonnées temporelles requises
    par le contrat PIT (Sprint Maître 2 / Section 17 Point 2.1).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame à enrichir (modifié par copie).
    source : str
        Identifiant de la source (``"eodhd"``, ``"finnhub"``, ``"alpaca"``, …).
    event_time_col : str | None
        Colonne à utiliser comme ``event_time``. Si None, utilise ``date_col``
        avec l'heure ``available_at_hour_utc``.
    available_at_col : str | None
        Colonne à utiliser comme ``available_at``. Si None, utilise
        ``date_col`` + ``available_at_hour_utc`` UTC.
    default_available_at : datetime | None
        Valeur fixe si aucune colonne n'est disponible.
    source_revision : str | None
        Révision/version de la source.
    ingested_at : datetime | None
        Horodatage d'ingestion.
    tz_name : str
        Timezone IANA.
    quality : QualityState
        État de qualité.
    date_col : str
        Colonne de date à utiliser si ``event_time_col``/``available_at_col``
        ne sont pas fournies.
    available_at_hour_utc : int
        Heure UTC à laquelle la donnée devient disponible (défaut 21h = 16h EST).

    Returns
    -------
    pd.DataFrame
        DataFrame enrichi (copie).
    """
    import pandas as pd

    df = df.copy()

    # ── event_time ──────────────────────────────────────────────────────
    if event_time_col is not None and event_time_col in df.columns:
        df["event_time"] = pd.to_datetime(df[event_time_col], utc=True)
    elif date_col in df.columns:
        df["event_time"] = pd.to_datetime(df[date_col], utc=True) + pd.Timedelta(
            hours=available_at_hour_utc
        )
    else:
        df["event_time"] = pd.NaT  # type: ignore[assignment]

    # ── available_at ────────────────────────────────────────────────────
    if available_at_col is not None and available_at_col in df.columns:
        df["available_at"] = pd.to_datetime(df[available_at_col], utc=True)
    elif date_col in df.columns:
        df["available_at"] = pd.to_datetime(df[date_col], utc=True) + pd.Timedelta(
            hours=available_at_hour_utc
        )
    elif default_available_at is not None:
        df["available_at"] = default_available_at
    else:
        df["available_at"] = pd.NaT  # type: ignore[assignment]

    # ── Métadonnées scalaires ───────────────────────────────────────────
    df["data_source"] = source
    df["source_revision"] = source_revision
    from datetime import timezone as _dt_timezone

    df["ingested_at"] = ingested_at or datetime.now(_dt_timezone.utc)
    df["data_timezone"] = tz_name
    df["data_quality"] = quality.value

    return df


def build_availability_from_row(
    row: "pd.Series",
    *,
    fallback_source: str = "unknown",
) -> DataAvailabilityInfo:
    """Construit un ``DataAvailabilityInfo`` à partir d'une ligne DataFrame enrichie.

    Attend les colonnes produites par :func:`enrich_dataframe_with_pit`.

    Parameters
    ----------
    row : pd.Series
        Ligne du DataFrame enrichi.
    fallback_source : str
        Source par défaut si ``data_source`` est absent.

    Returns
    -------
    DataAvailabilityInfo
    """
    from datetime import datetime as dt
    import pandas as pd

    event_time = row.get("event_time")
    available_at = row.get("available_at")
    source = str(row.get("data_source", fallback_source) or fallback_source)
    source_revision = row.get("source_revision")
    ingested_at = row.get("ingested_at")
    tz = str(row.get("data_timezone", "America/New_York") or "America/New_York")
    quality_raw = row.get("data_quality", "present")
    try:
        quality = QualityState(str(quality_raw))
    except ValueError:
        quality = QualityState.PRESENT

    # Conversion des timestamps
    _na_strings = {"NaT", "nat", "NAT", "None", ""}
    if isinstance(event_time, str):
        if event_time not in _na_strings:
            event_time = dt.fromisoformat(event_time)
        else:
            event_time = None
    if isinstance(available_at, str):
        if available_at not in _na_strings:
            available_at = dt.fromisoformat(available_at)
        else:
            available_at = None
    if isinstance(ingested_at, str):
        if ingested_at not in _na_strings:
            ingested_at = dt.fromisoformat(ingested_at)
        else:
            ingested_at = None

    if event_time is None or (isinstance(event_time, (dt, pd.Timestamp)) and pd.isna(event_time)):
        event_time = dt.now(_tz.utc)
    if available_at is None or (isinstance(available_at, (dt, pd.Timestamp)) and pd.isna(available_at)):
        available_at = dt.now(_tz.utc)

    return DataAvailabilityInfo(
        event_time=event_time,  # type: ignore[arg-type]
        available_at=available_at,  # type: ignore[arg-type]
        source=source,
        source_revision=str(source_revision) if source_revision is not None and not pd.isna(source_revision) else None,  # type: ignore[arg-type]
        ingested_at=ingested_at if ingested_at is not None and not pd.isna(ingested_at) else None,  # type: ignore[arg-type]
        timezone=tz,
        quality=quality,
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
        event_time=event_dt.replace(tzinfo=_tz.utc),
        available_at=available_dt.replace(tzinfo=_tz.utc),
        source=source,
        timezone="America/New_York",
    )
