"""
backtesting/report_schema.py
=============================
Phase D.5 (refactor) — schéma typé du payload `report.json` produit par
``backtesting.report.save_report_json``.

Volontairement basé sur des **dataclasses standard** (pas de Pydantic) pour
éviter d'ajouter une dépendance lourde au projet. Si un jour Pydantic est
introduit (côté IHM ou API), l'upgrade est mécanique : remplacer ``@dataclass``
par ``pydantic.BaseModel`` et conserver les mêmes annotations.

Le module fournit deux usages :

1. **Documentation typée** — un consommateur (notebook, IHM, dashboard) peut
   importer ces dataclasses pour bénéficier de l'autocomplétion.
2. **Validation runtime** — ``validate_report_payload(payload)`` vérifie qu'un
   dict respecte les clés obligatoires et types attendus, en levant
   ``ReportSchemaError`` sinon. Les clés inconnues sont tolérées (forward
   compatibility) et reportées en warnings.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)


class ReportSchemaError(ValueError):
    """Erreur levée si le payload report.json ne respecte pas le schéma."""


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SummarySchema:
    """Bloc ``summary`` du report."""

    initial_equity: float
    final_value: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    avg_trade_duration_days: float
    profit_factor: float | str  # 'inf' sentinel toléré
    # Phase A.5 (refactor) — ratios additionnels.
    calmar_ratio: float = 0.0
    ulcer_index: float = 0.0


@dataclass(slots=True)
class MicrostructureParamsSchema:
    """Sous-bloc ``params.microstructure`` (Phase B refactor)."""

    slippage_model: str = "fixed"
    slippage_base_bps: float = 0.0
    slippage_impact_coef: float = 0.0
    initial_stop_pct: float = 0.0
    max_entry_gap_pct: float = 0.0
    intrabar_priority: str = "conservative"
    is_default: bool = True


@dataclass(slots=True)
class RiskOverlayParamsSchema:
    """Sous-bloc ``params.risk_overlay`` (Phase C refactor)."""

    sizing_mode: str = "equal_weight"
    sizing_min_weight_pct: float = 0.005
    sizing_max_weight_pct: float = 0.20
    regime_filter_enabled: bool = False
    regime_sma_window: int = 200
    regime_bear_threshold: float = -0.02
    max_sector_exposure_pct: float = 0.0
    max_portfolio_dd_pct: float = 0.0
    dd_recovery_pct: float = 0.95
    dd_rolling_peak_window_days: int = 252
    dd_degraded_allocation_pct: float = 0.02
    target_annual_vol: float | None = None
    is_default: bool = True


@dataclass(slots=True)
class RunMetadataSchema:
    """Bloc ``run_metadata`` (Phase A.4 refactor)."""

    git_sha: str | None = None
    python_version: str | None = None
    platform: str | None = None
    seed: int | None = None
    dataset_hash: str | None = None
    generated_at: str | None = None


@dataclass(slots=True)
class DiagnosticsSchema:
    """Bloc ``diagnostics`` — compteurs simulator."""

    blocked_same_day_exits: int = 0
    blocked_cash_entries: int = 0
    executed_day_trades: int = 0
    blocked_entry_gap: int = 0
    initial_stop_exits: int = 0
    take_profit_exits: int = 0
    trailing_stop_exits: int = 0
    blocked_by_regime: int = 0
    blocked_by_sectoral_cap: int = 0
    blocked_by_drawdown_breaker: int = 0


@dataclass(slots=True)
class BacktestReportSchema:
    """Schéma haut niveau du payload `report.json`."""

    summary: SummarySchema
    params: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    diagnostics: DiagnosticsSchema = field(default_factory=DiagnosticsSchema)
    run_metadata: RunMetadataSchema = field(default_factory=RunMetadataSchema)
    fidelity: dict[str, Any] = field(default_factory=dict)
    corporate_actions: dict[str, Any] = field(default_factory=dict)
    trade_export: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation runtime
# ---------------------------------------------------------------------------


_SUMMARY_REQUIRED: tuple[str, ...] = (
    "initial_equity",
    "final_value",
    "total_return_pct",
    "sharpe_ratio",
    "max_drawdown_pct",
    "total_trades",
    "win_rate_pct",
)


def _check_type(value: Any, expected: tuple[type, ...], path: str) -> None:
    if not isinstance(value, expected):
        raise ReportSchemaError(
            f"{path}: type {type(value).__name__} inattendu, attendu un de {[t.__name__ for t in expected]}."
        )


def validate_report_payload(payload: dict[str, Any], *, strict: bool = False) -> BacktestReportSchema:
    """Valide un dict ``report.json`` et retourne une instance typée.

    Parameters
    ----------
    payload : dict
        Le contenu JSON désérialisé.
    strict : bool
        Si True, refuse les clés inconnues à la racine. Sinon (défaut), elles
        sont tolérées et un debug log est émis (forward compatibility).

    Raises
    ------
    ReportSchemaError
        Si une clé obligatoire est manquante ou si un type est invalide.
    """
    if not isinstance(payload, dict):
        raise ReportSchemaError("Payload racine doit être un dict.")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ReportSchemaError("`summary` est requis et doit être un dict.")

    missing = [k for k in _SUMMARY_REQUIRED if k not in summary]
    if missing:
        raise ReportSchemaError(f"summary: clés manquantes {missing}.")

    profit_factor = summary.get("profit_factor", 0.0)
    if not isinstance(profit_factor, (int, float, str)):
        raise ReportSchemaError("summary.profit_factor doit être un nombre ou la chaîne 'inf'.")

    summary_obj = SummarySchema(
        initial_equity=float(summary["initial_equity"]),
        final_value=float(summary["final_value"]),
        total_return_pct=float(summary["total_return_pct"]),
        cagr_pct=float(summary.get("cagr_pct", 0.0)),
        sharpe_ratio=float(summary["sharpe_ratio"]),
        sortino_ratio=float(summary.get("sortino_ratio", 0.0)),
        max_drawdown_pct=float(summary["max_drawdown_pct"]),
        total_trades=int(summary["total_trades"]),
        win_rate_pct=float(summary["win_rate_pct"]),
        avg_trade_duration_days=float(summary.get("avg_trade_duration_days", 0.0)),
        profit_factor=profit_factor,
        calmar_ratio=float(summary.get("calmar_ratio", 0.0)),
        ulcer_index=float(summary.get("ulcer_index", 0.0)),
    )

    params = payload.get("params", {}) or {}
    _check_type(params, (dict,), "params")

    artifacts = payload.get("artifacts", {}) or {}
    _check_type(artifacts, (dict,), "artifacts")

    diagnostics_payload = payload.get("diagnostics", {}) or {}
    _check_type(diagnostics_payload, (dict,), "diagnostics")
    diagnostics_fields = getattr(DiagnosticsSchema, "__dataclass_fields__", {})
    diagnostics_obj = DiagnosticsSchema(
        **{k: int(v) for k, v in diagnostics_payload.items() if k in diagnostics_fields}
    )

    run_metadata_payload = payload.get("run_metadata", {}) or {}
    _check_type(run_metadata_payload, (dict,), "run_metadata")
    run_metadata_fields = getattr(RunMetadataSchema, "__dataclass_fields__", {})
    run_metadata_obj = RunMetadataSchema(
        **{
            k: v
            for k, v in run_metadata_payload.items()
            if k in run_metadata_fields
        }
    )

    fidelity_payload = payload.get("fidelity", {}) or {}
    _check_type(fidelity_payload, (dict,), "fidelity")

    corporate_actions_payload = payload.get("corporate_actions", {}) or {}
    _check_type(corporate_actions_payload, (dict,), "corporate_actions")

    trade_export_payload = payload.get("trade_export", {}) or {}
    _check_type(trade_export_payload, (dict,), "trade_export")

    known_root = {
        "summary",
        "params",
        "artifacts",
        "diagnostics",
        "run_metadata",
        "fidelity",
        "corporate_actions",
        "trade_export",
    }
    extra = set(payload.keys()) - known_root
    if extra:
        message = f"Clés racine inconnues: {sorted(extra)}"
        if strict:
            raise ReportSchemaError(message)
        LOGGER.debug("validate_report_payload: %s (toléré, strict=False).", message)

    return BacktestReportSchema(
        summary=summary_obj,
        params=dict(params),
        artifacts={str(k): str(v) for k, v in artifacts.items()},
        diagnostics=diagnostics_obj,
        run_metadata=run_metadata_obj,
        fidelity=dict(fidelity_payload),
        corporate_actions=dict(corporate_actions_payload),
        trade_export=dict(trade_export_payload),
    )


__all__ = [
    "BacktestReportSchema",
    "DiagnosticsSchema",
    "MicrostructureParamsSchema",
    "ReportSchemaError",
    "RiskOverlayParamsSchema",
    "RunMetadataSchema",
    "SummarySchema",
    "validate_report_payload",
]

