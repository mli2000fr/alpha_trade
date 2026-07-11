"""risk_management/drift_monitor.py — Surveillance de drift multi-dimensionnel (Sprint Maître 13).

Surveille 7 dimensions de drift :
1. Features (distribution shift vs baseline)
2. Probabilités (calibration drift)
3. Sides (changement de distribution long/flat/short)
4. Calibration (dégradation de la calibration)
5. PnL (dérive des rendements)
6. Coûts (augmentation des coûts de trading)
7. Exposition (changement d'exposition brute/nette)

Usage ::

    from risk_management.drift_monitor import (
        DriftMonitor, DriftDimension, DriftStatus, DriftReport,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── DriftDimension ──────────────────────────────────────────────────────────


class DriftDimension(StrEnum):
    """Dimensions de drift surveillées (Sprint Maître 13)."""

    FEATURES = "features"
    PROBABILITIES = "probabilities"
    SIDES = "sides"
    CALIBRATION = "calibration"
    PNL = "pnl"
    COSTS = "costs"
    EXPOSURE = "exposure"


# ── DriftStatus ─────────────────────────────────────────────────────────────


class DriftStatus(StrEnum):
    """Statut de drift (Sprint Maître 13)."""

    OK = "ok"         # Pas de drift détecté
    WARN = "warn"     # Drift modéré — log + alerte
    ALERT = "alert"   # Drift sévère — action requise (kill switch, rollback)


# ── DriftConfig ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DriftConfig:
    """Seuils de drift par dimension (Sprint Maître 13)."""

    # Features: PSI thresholds
    features_psi_warn: float = 0.10
    features_psi_alert: float = 0.25

    # Probabilities: KS test p-value
    proba_ks_warn: float = 0.05
    proba_ks_alert: float = 0.01

    # Sides: max change in side distribution (absolute %)
    sides_max_change_warn: float = 0.10  # 10% change
    sides_max_change_alert: float = 0.25  # 25% change

    # Calibration: max increase in Brier score
    calibration_brier_increase_warn: float = 0.01
    calibration_brier_increase_alert: float = 0.03

    # PnL: max drawdown from peak (%)
    pnl_drawdown_warn: float = 0.10
    pnl_drawdown_alert: float = 0.20

    # Costs: max increase in cost per trade (%)
    costs_increase_warn: float = 0.20
    costs_increase_alert: float = 0.50

    # Exposure: max change in gross exposure (%)
    exposure_change_warn: float = 0.15
    exposure_change_alert: float = 0.30


# ── DimensionDrift ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DimensionDrift:
    """État de drift d'une dimension (Sprint Maître 13)."""

    dimension: DriftDimension
    status: DriftStatus = DriftStatus.OK
    current_value: float | None = None
    baseline_value: float | None = None
    change_pct: float | None = None
    threshold_warn: float | None = None
    threshold_alert: float | None = None
    detail: str | None = None

    @property
    def is_drifting(self) -> bool:
        return self.status != DriftStatus.OK

    @property
    def is_critical(self) -> bool:
        return self.status == DriftStatus.ALERT


# ── DriftReport ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Rapport de drift complet (Sprint Maître 13).

    Attributes
    ----------
    timestamp : datetime
    model_id : str
    overall_status : DriftStatus
        Pire statut parmi toutes les dimensions.
    dimensions : tuple[DimensionDrift, ...]
    must_kill_switch : bool
        True si une dimension ALERT nécessite un kill switch.
    must_degrade : bool
        True si une dimension WARN nécessite une dégradation.
    summary : str
    """

    timestamp: datetime
    model_id: str = ""
    overall_status: DriftStatus = DriftStatus.OK
    dimensions: tuple[DimensionDrift, ...] = ()
    must_kill_switch: bool = False
    must_degrade: bool = False
    summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "model_id": self.model_id,
            "overall_status": self.overall_status.value,
            "must_kill_switch": self.must_kill_switch,
            "must_degrade": self.must_degrade,
            "summary": self.summary,
            "dimensions": [
                {
                    "dimension": d.dimension.value,
                    "status": d.status.value,
                    "current_value": round(d.current_value, 6) if d.current_value is not None else None,
                    "baseline_value": round(d.baseline_value, 6) if d.baseline_value is not None else None,
                    "change_pct": round(d.change_pct, 4) if d.change_pct is not None else None,
                    "detail": d.detail,
                }
                for d in self.dimensions
            ],
        }


# ── DriftMonitor ────────────────────────────────────────────────────────────


@dataclass
class DriftMonitor:
    """Surveille le drift sur 7 dimensions (Sprint Maître 13).

    Chaque dimension a ses propres seuils WARN/ALERT et sa propre
    métrique de comparaison (PSI, KS, changement absolu, etc.).
    """

    config: DriftConfig = field(default_factory=DriftConfig)

    def evaluate(
        self,
        model_id: str = "",
        *,
        features_psi: float | None = None,
        proba_ks_pvalue: float | None = None,
        sides_long_pct: float | None = None,
        sides_flat_pct: float | None = None,
        sides_short_pct: float | None = None,
        sides_baseline_long: float | None = None,
        sides_baseline_flat: float | None = None,
        sides_baseline_short: float | None = None,
        calibration_brier_current: float | None = None,
        calibration_brier_baseline: float | None = None,
        pnl_drawdown_pct: float | None = None,
        costs_current_bps: float | None = None,
        costs_baseline_bps: float | None = None,
        exposure_current_gross: float | None = None,
        exposure_baseline_gross: float | None = None,
    ) -> DriftReport:
        """Évalue le drift sur toutes les dimensions.

        Returns
        -------
        DriftReport
        """
        dims: list[DimensionDrift] = []
        cfg = self.config

        # ── 1. Features (PSI) ──────────────────────────────────────────
        if features_psi is not None:
            status = DriftStatus.OK
            if features_psi >= cfg.features_psi_alert:
                status = DriftStatus.ALERT
            elif features_psi >= cfg.features_psi_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.FEATURES,
                status=status,
                current_value=features_psi,
                threshold_warn=cfg.features_psi_warn,
                threshold_alert=cfg.features_psi_alert,
                detail=f"PSI={features_psi:.4f}",
            ))

        # ── 2. Probabilités (KS p-value) ───────────────────────────────
        if proba_ks_pvalue is not None:
            status = DriftStatus.OK
            if proba_ks_pvalue <= cfg.proba_ks_alert:
                status = DriftStatus.ALERT
            elif proba_ks_pvalue <= cfg.proba_ks_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.PROBABILITIES,
                status=status,
                current_value=proba_ks_pvalue,
                threshold_warn=cfg.proba_ks_warn,
                threshold_alert=cfg.proba_ks_alert,
                detail=f"KS p-value={proba_ks_pvalue:.4f}",
            ))

        # ── 3. Sides (changement de distribution) ──────────────────────
        if all(v is not None for v in [sides_long_pct, sides_baseline_long]):
            long_change = abs(sides_long_pct - sides_baseline_long)  # type: ignore[operator]
            flat_change = abs((sides_flat_pct or 0) - (sides_baseline_flat or 0))
            short_change = abs((sides_short_pct or 0) - (sides_baseline_short or 0))
            max_change = max(long_change, flat_change, short_change)
            status = DriftStatus.OK
            if max_change >= cfg.sides_max_change_alert:
                status = DriftStatus.ALERT
            elif max_change >= cfg.sides_max_change_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.SIDES,
                status=status,
                current_value=max_change,
                threshold_warn=cfg.sides_max_change_warn,
                threshold_alert=cfg.sides_max_change_alert,
                detail=f"max_side_change={max_change:.2%}",
            ))

        # ── 4. Calibration (Brier score) ───────────────────────────────
        if calibration_brier_current is not None and calibration_brier_baseline is not None:
            increase = calibration_brier_current - calibration_brier_baseline
            status = DriftStatus.OK
            if increase >= cfg.calibration_brier_increase_alert:
                status = DriftStatus.ALERT
            elif increase >= cfg.calibration_brier_increase_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.CALIBRATION,
                status=status,
                current_value=calibration_brier_current,
                baseline_value=calibration_brier_baseline,
                change_pct=increase / max(calibration_brier_baseline, 1e-10),
                threshold_warn=cfg.calibration_brier_increase_warn,
                threshold_alert=cfg.calibration_brier_increase_alert,
                detail=f"Brier increase={increase:.4f}",
            ))

        # ── 5. PnL (drawdown) ──────────────────────────────────────────
        if pnl_drawdown_pct is not None:
            status = DriftStatus.OK
            if pnl_drawdown_pct >= cfg.pnl_drawdown_alert:
                status = DriftStatus.ALERT
            elif pnl_drawdown_pct >= cfg.pnl_drawdown_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.PNL,
                status=status,
                current_value=pnl_drawdown_pct,
                threshold_warn=cfg.pnl_drawdown_warn,
                threshold_alert=cfg.pnl_drawdown_alert,
                detail=f"Drawdown={pnl_drawdown_pct:.2%}",
            ))

        # ── 6. Coûts ───────────────────────────────────────────────────
        if costs_current_bps is not None and costs_baseline_bps is not None:
            increase_pct = (
                (costs_current_bps - costs_baseline_bps) / max(costs_baseline_bps, 1.0)
            )
            status = DriftStatus.OK
            if increase_pct >= cfg.costs_increase_alert:
                status = DriftStatus.ALERT
            elif increase_pct >= cfg.costs_increase_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.COSTS,
                status=status,
                current_value=costs_current_bps,
                baseline_value=costs_baseline_bps,
                change_pct=increase_pct,
                threshold_warn=cfg.costs_increase_warn,
                threshold_alert=cfg.costs_increase_alert,
                detail=f"Cost increase={increase_pct:.1%}",
            ))

        # ── 7. Exposition ──────────────────────────────────────────────
        if exposure_current_gross is not None and exposure_baseline_gross is not None:
            change = abs(exposure_current_gross - exposure_baseline_gross)
            status = DriftStatus.OK
            if change >= cfg.exposure_change_alert:
                status = DriftStatus.ALERT
            elif change >= cfg.exposure_change_warn:
                status = DriftStatus.WARN
            dims.append(DimensionDrift(
                dimension=DriftDimension.EXPOSURE,
                status=status,
                current_value=exposure_current_gross,
                baseline_value=exposure_baseline_gross,
                change_pct=change,
                threshold_warn=cfg.exposure_change_warn,
                threshold_alert=cfg.exposure_change_alert,
                detail=f"Exposure change={change:.2%}",
            ))

        # ── Synthèse ───────────────────────────────────────────────────
        statuses = [d.status for d in dims]
        if DriftStatus.ALERT in statuses:
            overall = DriftStatus.ALERT
        elif DriftStatus.WARN in statuses:
            overall = DriftStatus.WARN
        else:
            overall = DriftStatus.OK

        alert_dims = [d.dimension.value for d in dims if d.status == DriftStatus.ALERT]
        warn_dims = [d.dimension.value for d in dims if d.status == DriftStatus.WARN]

        summary_parts: list[str] = []
        if alert_dims:
            summary_parts.append(f"ALERT: {', '.join(alert_dims)}")
        if warn_dims:
            summary_parts.append(f"WARN: {', '.join(warn_dims)}")
        if not summary_parts:
            summary_parts.append("OK: no drift detected")

        return DriftReport(
            timestamp=datetime.now(),
            model_id=model_id,
            overall_status=overall,
            dimensions=tuple(dims),
            must_kill_switch=len(alert_dims) > 0,
            must_degrade=len(warn_dims) > 0 and len(alert_dims) == 0,
            summary="; ".join(summary_parts),
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_drift(
    *,
    features_psi: float | None = None,
    proba_ks_pvalue: float | None = None,
    pnl_drawdown_pct: float | None = None,
    sides_max_change: float | None = None,
) -> DriftReport:
    """Évalue rapidement le drift sur les dimensions principales."""
    monitor = DriftMonitor()
    return monitor.evaluate(
        features_psi=features_psi,
        proba_ks_pvalue=proba_ks_pvalue,
        pnl_drawdown_pct=pnl_drawdown_pct,
        sides_long_pct=sides_max_change,
        sides_baseline_long=0.33,
        sides_baseline_flat=0.34,
        sides_baseline_short=0.33,
    )
