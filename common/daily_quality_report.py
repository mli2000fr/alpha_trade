"""common/daily_quality_report.py — Rapport quotidien automatisé de qualité.

Sprint Maître 2 / Section 17 Point 2.4 :
- Combine couverture, fraîcheur, données futures et anomalies d'univers
  en un rapport quotidien automatisé.
- Détecte les symboles entrants/sortants, les changements de ticker,
  et les variations anormales de l'univers.
- Persiste le rapport en JSON dans ``artifacts/daily_quality/``.
- Conçu pour être appelé par un CLI, un scheduler ou un smoke test
  pré-session.

Usage ::

    from common.daily_quality_report import (
        build_and_persist_daily_report,
        detect_universe_anomalies,
        UniverseAnomalyReport,
    )

    report = build_and_persist_daily_report(
        trade_date=date.today(),
        symbols=universe_symbols,
        availability_map=avail_map,
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from common.data_availability import (
    DailyQualityReport,
    DataAvailabilityInfo,
    build_daily_quality_report,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_ARTIFACT_DIR = Path("artifacts/daily_quality")
MIN_COVERAGE_ALERT = 0.90


# ── Universe anomaly types ──────────────────────────────────────────────────

@dataclass
class UniverseAnomalyReport:
    """Rapport d'anomalies d'univers entre deux snapshots consécutifs."""

    previous_date: str | None  # None si pas d'historique
    current_date: str
    previous_count: int
    current_count: int
    symbols_added: list[str] = field(default_factory=list)
    symbols_removed: list[str] = field(default_factory=list)
    symbols_common: list[str] = field(default_factory=list)
    count_change_pct: float = 0.0
    is_anomalous: bool = False
    anomaly_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_date": self.previous_date,
            "current_date": self.current_date,
            "previous_count": self.previous_count,
            "current_count": self.current_count,
            "symbols_added": self.symbols_added,
            "symbols_removed": self.symbols_removed,
            "count_change_pct": round(self.count_change_pct, 4),
            "is_anomalous": self.is_anomalous,
            "anomaly_reasons": self.anomaly_reasons,
        }


# ── Universe anomaly detection ──────────────────────────────────────────────

def detect_universe_anomalies(
    current_symbols: list[str],
    previous_symbols: list[str] | None,
    current_date: str,
    previous_date: str | None = None,
    *,
    max_count_change_pct: float = 0.20,
    max_added_without_removed: int = 3,
    max_removed_without_added: int = 3,
) -> UniverseAnomalyReport:
    """Détecte les anomalies entre deux snapshots d'univers consécutifs.

    Une anomalie est déclenchée si :
    - La variation du nombre de symboles dépasse ``max_count_change_pct``.
    - Des symboles sont ajoutés sans qu'aucun ne soit retiré (alerte IPO massive).
    - Des symboles sont retirés sans qu'aucun ne soit ajouté (alerte delisting massif).

    Parameters
    ----------
    current_symbols : list[str]
        Symboles de l'univers aujourd'hui.
    previous_symbols : list[str] | None
        Symboles de l'univers au jour de bourse précédent. None = pas d'historique.
    current_date : str
        Date ISO du snapshot courant.
    previous_date : str | None
        Date ISO du snapshot précédent.
    max_count_change_pct : float
        Seuil de variation acceptable (0.20 = 20%).
    max_added_without_removed : int
        Nombre max d'ajouts sans retrait avant alerte.
    max_removed_without_added : int
        Nombre max de retraits sans ajout avant alerte.

    Returns
    -------
    UniverseAnomalyReport
    """
    current_set = {s.strip().upper() for s in current_symbols if s and s.strip()}

    if previous_symbols is None:
        return UniverseAnomalyReport(
            previous_date=previous_date,
            current_date=current_date,
            previous_count=0,
            current_count=len(current_set),
            symbols_added=sorted(current_set),
            symbols_removed=[],
            symbols_common=[],
            count_change_pct=1.0,
            is_anomalous=False,  # premier rapport = pas d'anomalie, juste informatif
        )

    previous_set = {s.strip().upper() for s in previous_symbols if s and s.strip()}
    added = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    common = sorted(current_set & previous_set)

    prev_count = len(previous_set)
    curr_count = len(current_set)
    count_change_pct = abs(curr_count - prev_count) / max(prev_count, 1)

    reasons: list[str] = []

    # Seuil de variation absolue
    if count_change_pct > max_count_change_pct:
        reasons.append(
            f"count_change_{count_change_pct:.1%}_gt_{max_count_change_pct:.0%}"
        )

    # Ajouts sans retraits (possible IPO massive ou bug de filtre)
    if added and not removed and len(added) > max_added_without_removed:
        reasons.append(f"only_added:{len(added)}_symbols_no_removals")

    # Retraits sans ajouts (possible delisting massif ou bug)
    if removed and not added and len(removed) > max_removed_without_added:
        reasons.append(f"only_removed:{len(removed)}_symbols_no_additions")

    is_anomalous = len(reasons) > 0

    return UniverseAnomalyReport(
        previous_date=previous_date,
        current_date=current_date,
        previous_count=prev_count,
        current_count=curr_count,
        symbols_added=added,
        symbols_removed=removed,
        symbols_common=common,
        count_change_pct=count_change_pct,
        is_anomalous=is_anomalous,
        anomaly_reasons=reasons,
    )


# ── Combined report ─────────────────────────────────────────────────────────

@dataclass
class CombinedDailyReport:
    """Rapport quotidien complet : qualité des données + anomalies d'univers."""

    quality: DailyQualityReport
    universe_anomalies: UniverseAnomalyReport | None
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "quality": self.quality.to_dict(),
        }
        if self.universe_anomalies is not None:
            result["universe_anomalies"] = self.universe_anomalies.to_dict()
        if self.report_path is not None:
            result["report_path"] = self.report_path
        return result


# ── Persistence ─────────────────────────────────────────────────────────────

def _load_previous_symbols(
    artifact_dir: Path,
    previous_date: str,
) -> list[str] | None:
    """Tente de charger les symboles du rapport précédent."""
    prev_path = artifact_dir / f"{previous_date}.json"
    if not prev_path.exists():
        return None
    try:
        data = json.loads(prev_path.read_text(encoding="utf-8"))
        quality = data.get("quality", {})
        # Les symboles ne sont pas stockés explicitement dans le rapport actuel.
        # On tente de les récupérer depuis une clé dédiée.
        symbols = data.get("universe_symbols")
        if symbols and isinstance(symbols, list):
            return [str(s) for s in symbols]
        # Fallback : reconstituer depuis quality_by_source
        return None
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        LOGGER.warning("Cannot load previous report %s: %s", prev_path, exc)
        return None


def _persist_report(
    report: CombinedDailyReport,
    artifact_dir: Path,
    symbols: list[str],
) -> Path:
    """Écrit le rapport en JSON atomique."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_date = report.quality.report_date
    payload = report.to_dict()
    # Stocker les symboles pour le rapport suivant
    payload["universe_symbols"] = sorted({s.strip().upper() for s in symbols if s and s.strip()})

    file_path = artifact_dir / f"{report_date}.json"
    tmp_path = artifact_dir / f".{report_date}.tmp"

    tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp_path.replace(file_path)  # atomic rename

    LOGGER.info("Daily quality report persisted: %s", file_path)
    return file_path


# ── Main entry point ────────────────────────────────────────────────────────

def build_and_persist_daily_report(
    trade_date: date,
    symbols: list[str],
    availability_map: dict[str, DataAvailabilityInfo],
    *,
    artifact_dir: Path | str | None = None,
    previous_symbols: list[str] | None = None,
    previous_date: str | None = None,
    max_age_hours: float = 24.0,
    decision_cutoff: datetime | None = None,
) -> CombinedDailyReport:
    """Construit et persiste le rapport quotidien complet.

    Parameters
    ----------
    trade_date : date
        Date de trading.
    symbols : list[str]
        Symboles de l'univers PIT à cette date.
    availability_map : dict[str, DataAvailabilityInfo]
        Infos de disponibilité par symbole (toutes sources confondues).
    artifact_dir : Path | str | None
        Répertoire de sortie. Défaut : ``artifacts/daily_quality/``.
    previous_symbols : list[str] | None
        Symboles de l'univers au jour précédent. Si None, tente de charger
        depuis le rapport précédent.
    previous_date : str | None
        Date ISO du snapshot précédent. Si None, aucun historique.
    max_age_hours : float
        Âge maximal avant stale.
    decision_cutoff : datetime | None
        Cutoff de décision. Si None, utilise trade_date à 21:00 UTC.

    Returns
    -------
    CombinedDailyReport
        Rapport combiné qualité + anomalies, avec le chemin de persistance.
    """
    from datetime import timezone as _dt_tz

    if decision_cutoff is None:
        decision_cutoff = datetime(trade_date.year, trade_date.month, trade_date.day, 21, 0, 0, tzinfo=_dt_tz.utc)

    target_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR
    report_date_str = trade_date.isoformat()

    # ── Quality report ──────────────────────────────────────────────────
    quality = build_daily_quality_report(
        symbols=symbols,
        availability_map=availability_map,
        decision_cutoff=decision_cutoff,
        max_age_hours=max_age_hours,
    )

    # ── Universe anomalies ──────────────────────────────────────────────
    if previous_symbols is None and previous_date is not None:
        previous_symbols = _load_previous_symbols(target_dir, previous_date)

    anomalies = detect_universe_anomalies(
        current_symbols=symbols,
        previous_symbols=previous_symbols,
        current_date=report_date_str,
        previous_date=previous_date,
    )

    # ── Combine ─────────────────────────────────────────────────────────
    report = CombinedDailyReport(
        quality=quality,
        universe_anomalies=anomalies,
    )

    # ── Persist ─────────────────────────────────────────────────────────
    report_path = _persist_report(report, target_dir, symbols)
    report.report_path = str(report_path)

    # ── Log anomalies ───────────────────────────────────────────────────
    if quality.alerts:
        for alert in quality.alerts:
            if "FUTURE_DATA" in alert or "low_coverage" in alert:
                LOGGER.error("QUALITY_ALERT: %s", alert)
            else:
                LOGGER.warning("QUALITY_ALERT: %s", alert)

    if anomalies.is_anomalous:
        LOGGER.error(
            "UNIVERSE_ANOMALY: %s → %s: %s",
            anomalies.previous_date,
            anomalies.current_date,
            "; ".join(anomalies.anomaly_reasons),
        )

    return report
