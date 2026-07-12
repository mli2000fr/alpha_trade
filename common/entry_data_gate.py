"""common/entry_data_gate.py — Gate bloquant les entrées sur données critiques.

Sprint Maître 2 / Section 17 Point 2.5 :
- Chaque entrée (long ou short) doit avoir ses données critiques présentes,
  non futures et non stales avant d'être autorisée.
- Une donnée critique absente, future ou stale → l'entrée est BLOQUÉE.
- Une donnée optionnelle absente/stale → l'entrée est DÉGRADÉE mais pas bloquée.
- Ce gate est appelé AVANT la prédiction ML et le sizing risque.

Usage ::

    from common.entry_data_gate import (
        EntryDataGate,
        EntryDataGateResult,
        check_entry_data_readiness,
        CANONICAL_ENTRY_SOURCES,
    )

    gate = EntryDataGate(critical_sources=["price_data", "volume_adv"])
    result = gate.check(symbol="AAPL", availability_map=avail_map, cutoff=cutoff)
    if not result.go:
        raise EntryDataBlocked(result)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from common.data_availability import (
    DataAvailabilityInfo,
    QualityState,
)

LOGGER = logging.getLogger(__name__)


# ── Canonical source classification for entry decisions ─────────────────────

#: Sources de données CRITIQUES pour toute entrée.
#: L'absence, la future data ou la staleness d'une source critique BLOQUE l'entrée.
CANONICAL_CRITICAL_SOURCES: tuple[str, ...] = (
    "price_data",        # OHLCV — nécessaire pour le prix d'entrée
    "volume_adv",        # ADV — nécessaire pour le sizing et la liquidité
)

#: Sources de données REQUISES pour une entrée.
#: L'absence dégrade l'entrée (taille réduite) mais ne bloque pas totalement.
CANONICAL_REQUIRED_SOURCES: tuple[str, ...] = (
    "borrow",            # Disponibilité short — obligatoire pour les shorts
    "universe",          # Appartenance à l'univers tradable
    "corporate_actions", # Splits, dividendes — pour ajustement
)

#: Sources de données OPTIONNELLES (overlay).
#: L'absence est ignorée.
CANONICAL_OPTIONAL_SOURCES: tuple[str, ...] = (
    "sentiment",         # Sentiment news
    "macro",             # Indicateurs macro
    "regime",            # Régime de marché
    "earnings",          # Prochain earnings date
)

#: Toutes les sources reconnues pour une entrée.
CANONICAL_ENTRY_SOURCES: dict[str, str] = {
    **{s: "critical" for s in CANONICAL_CRITICAL_SOURCES},
    **{s: "required" for s in CANONICAL_REQUIRED_SOURCES},
    **{s: "optional" for s in CANONICAL_OPTIONAL_SOURCES},
}


# ── Per-source gate result ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SourceGateResult:
    """Résultat du gate pour une source de données."""

    source: str
    criticality: str  # "critical", "required", "optional"
    passed: bool
    reason: str
    quality: str  # valeur de QualityState


# ── Entry gate result ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EntryDataGateResult:
    """Résultat complet du gate d'entrée pour un symbole."""

    symbol: str
    go: bool
    blocking_sources: list[str] = field(default_factory=list)
    degraded_sources: list[str] = field(default_factory=list)
    per_source: dict[str, SourceGateResult] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "go": self.go,
            "blocking_sources": self.blocking_sources,
            "degraded_sources": self.degraded_sources,
            "per_source": {
                src: {
                    "criticality": r.criticality,
                    "passed": r.passed,
                    "reason": r.reason,
                    "quality": r.quality,
                }
                for src, r in self.per_source.items()
            },
            "summary": self.summary,
        }


# ── Entry data gate ─────────────────────────────────────────────────────────

class EntryDataGate:
    """Gate de données pour les décisions d'entrée.

    Vérifie que toutes les sources critiques sont présentes, non futures
    et non stales avant d'autoriser une entrée sur un symbole.

    Parameters
    ----------
    critical_sources : tuple[str, ...]
        Sources dont l'absence/staleness BLOQUE l'entrée.
    required_sources : tuple[str, ...]
        Sources dont l'absence DÉGRADE l'entrée (taille réduite).
    optional_sources : tuple[str, ...]
        Sources dont l'absence est ignorée.
    max_age_hours : float | None
        Âge maximal pour les données critiques (None = pas de limite).
    """

    def __init__(
        self,
        critical_sources: tuple[str, ...] = CANONICAL_CRITICAL_SOURCES,
        required_sources: tuple[str, ...] = CANONICAL_REQUIRED_SOURCES,
        optional_sources: tuple[str, ...] = CANONICAL_OPTIONAL_SOURCES,
        max_age_hours: float = 26.0,  # EOD + 5h marge = 26h
    ) -> None:
        self._critical = set(critical_sources)
        self._required = set(required_sources)
        self._optional = set(optional_sources)
        self._all_known = self._critical | self._required | self._optional
        self.max_age_hours = max_age_hours

        # Vérifie qu'il n'y a pas d'overlap
        overlap_cr = self._critical & self._required
        overlap_co = self._critical & self._optional
        overlap_ro = self._required & self._optional
        if overlap_cr or overlap_co or overlap_ro:
            raise ValueError(
                f"Overlap entre les catégories de sources: "
                f"critical&required={overlap_cr}, "
                f"critical&optional={overlap_co}, "
                f"required&optional={overlap_ro}"
            )

    def _criticality(self, source: str) -> str:
        if source in self._critical:
            return "critical"
        if source in self._required:
            return "required"
        return "optional"

    def check(
        self,
        symbol: str,
        availability_map: dict[str, DataAvailabilityInfo],
        decision_cutoff: datetime,
    ) -> EntryDataGateResult:
        """Vérifie la disponibilité des données pour un symbole.

        Parameters
        ----------
        symbol : str
            Symbole à vérifier.
        availability_map : dict[str, DataAvailabilityInfo]
            Infos de disponibilité par source (ex. ``{"price_data": ..., "volume_adv": ...}``).
        decision_cutoff : datetime
            Cutoff de décision.

        Returns
        -------
        EntryDataGateResult
        """
        per_source: dict[str, SourceGateResult] = {}
        blocking: list[str] = []
        degraded: list[str] = []

        for source in self._all_known:
            avail = availability_map.get(source)

            # ── Absent ─────────────────────────────────────────────────
            if avail is None:
                reason = f"missing:{source}"
                quality = QualityState.MISSING_NO_SOURCE.value

                if source in self._critical:
                    result = SourceGateResult(source, "critical", False, reason, quality)
                    blocking.append(source)
                elif source in self._required:
                    result = SourceGateResult(source, "required", False, reason, quality)
                    degraded.append(source)
                else:
                    result = SourceGateResult(source, "optional", True, reason, quality)

                per_source[source] = result
                continue

            # ── Future data ────────────────────────────────────────────
            if avail.available_at > decision_cutoff:
                reason = (
                    f"future:{source}:avail={avail.available_at.isoformat()}"
                    f":cutoff={decision_cutoff.isoformat()}"
                )
                quality = QualityState.NOT_YET_AVAILABLE.value

                if source in self._critical:
                    result = SourceGateResult(source, "critical", False, reason, quality)
                    blocking.append(source)
                elif source in self._required:
                    result = SourceGateResult(source, "required", False, reason, quality)
                    degraded.append(source)
                else:
                    result = SourceGateResult(source, "optional", True, reason, quality)

                per_source[source] = result
                continue

            # ── Stale data ─────────────────────────────────────────────
            age_h = (decision_cutoff - avail.available_at).total_seconds() / 3600.0
            if self.max_age_hours is not None and age_h > self.max_age_hours:
                reason = f"stale:{source}:age={age_h:.1f}h:max={self.max_age_hours}h"
                quality = QualityState.MISSING_STALE.value

                if source in self._critical:
                    result = SourceGateResult(source, "critical", False, reason, quality)
                    blocking.append(source)
                elif source in self._required:
                    result = SourceGateResult(source, "required", False, reason, quality)
                    degraded.append(source)
                else:
                    result = SourceGateResult(source, "optional", True, reason, quality)

                per_source[source] = result
                continue

            # ── Quality degraded ───────────────────────────────────────
            if avail.quality not in (QualityState.PRESENT, QualityState.UNKNOWN):
                reason = f"degraded_quality:{source}:{avail.quality.value}"
                quality = avail.quality.value

                if source in self._critical:
                    result = SourceGateResult(source, "critical", False, reason, quality)
                    blocking.append(source)
                elif source in self._required:
                    result = SourceGateResult(source, "required", False, reason, quality)
                    degraded.append(source)
                else:
                    result = SourceGateResult(source, "optional", True, reason, quality)

                per_source[source] = result
                continue

            # ── OK ─────────────────────────────────────────────────────
            reason = f"ok:{source}:age={age_h:.1f}h"
            quality = avail.quality.value
            result = SourceGateResult(source, self._criticality(source), True, reason, quality)
            per_source[source] = result

        go = len(blocking) == 0

        # Construire le résumé
        if go:
            summary_parts = ["GO"]
            if degraded:
                summary_parts.append(f"degraded:{','.join(sorted(degraded))}")
            summary = "; ".join(summary_parts)
        else:
            summary = f"NO-GO: blocked by {','.join(sorted(blocking))}"

        return EntryDataGateResult(
            symbol=symbol,
            go=go,
            blocking_sources=sorted(blocking),
            degraded_sources=sorted(degraded),
            per_source=per_source,
            summary=summary,
        )


# ── Convenience function ────────────────────────────────────────────────────

def check_entry_data_readiness(
    symbol: str,
    availability_map: dict[str, DataAvailabilityInfo],
    decision_cutoff: datetime,
    *,
    critical_sources: tuple[str, ...] = CANONICAL_CRITICAL_SOURCES,
    max_age_hours: float = 26.0,
) -> EntryDataGateResult:
    """Vérifie si les données critiques sont prêtes pour une entrée.

    Version simplifiée de ``EntryDataGate`` n'utilisant que les sources
    critiques. Les sources required/optional ne sont pas vérifiées.

    Parameters
    ----------
    symbol : str
        Symbole à vérifier.
    availability_map : dict[str, DataAvailabilityInfo]
        Infos PIT par source.
    decision_cutoff : datetime
        Cutoff de décision.
    critical_sources : tuple[str, ...]
        Sources à vérifier (défaut : prix + ADV).
    max_age_hours : float
        Âge maximal (défaut 26h = EOD + marge).

    Returns
    -------
    EntryDataGateResult
    """
    gate = EntryDataGate(
        critical_sources=critical_sources,
        required_sources=(),
        optional_sources=(),
        max_age_hours=max_age_hours,
    )
    return gate.check(symbol, availability_map, decision_cutoff)


# ── Exception for blocked entries ───────────────────────────────────────────

class EntryDataBlocked(RuntimeError):
    """Levée quand une entrée est bloquée par le gate de données critiques."""

    def __init__(self, result: EntryDataGateResult) -> None:
        self.result = result
        super().__init__(result.summary)
