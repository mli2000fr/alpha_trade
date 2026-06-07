"""Sprint S7 — Helpers run-summary CLI extraits de ``selector.alpha_scanner``.

Émission/formatage des entêtes ``::alpha_trade_run_summary::`` consommées
par l'IHM streamlit. Aucune dépendance DB.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pandas as pd

from core.filter_profiles import STRICT_SWING_CASH_FILTERS
from core.run_summary import attach_schema_version
from database.run_business_summaries import persist_run_business_summary
from selector.config import RUN_SUMMARY_PREFIX
from selector.explainability import build_candidate_explainability_payload

if TYPE_CHECKING:
    from selector.config import AlphaScannerConfig


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


STEP_KEY = "selector"


def _emit_run_summary(summary: dict[str, object]) -> None:
    if not bool(summary.get("progress_live")):
        try:
            persist_run_business_summary(
                summary=summary,
                step_key=STEP_KEY,
                run_kind="step",
                status=str(summary.get("run_status", summary.get("status", "")) or "") or None,
                summary_run_id=str(summary.get("run_id", "") or "") or None,
                entity_run_id=str(summary.get("run_id", "") or "") or None,
                trade_date=summary.get("trade_date"),
                started_at=summary.get("started_at"),
                finished_at=summary.get("finished_at"),
            )
        except Exception:
            pass
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_top_candidate_explanations(result: pd.DataFrame, *, limit: int = 5) -> list[dict[str, object]]:
    if result.empty or "symbol" not in result.columns:
        return []
    rows: list[dict[str, object]] = []
    for _, row in result.head(limit).iterrows():
        explainability_payload = build_candidate_explainability_payload(row.to_dict())
        rows.append(
            {
                "rank": int(row["rank"]) if "rank" in result.columns and pd.notna(row.get("rank")) else None,
                "symbol": str(row.get("symbol") or "").strip(),
                "sector": None if pd.isna(row.get("sector")) else str(row.get("sector")),
                "final_score": None if pd.isna(row.get("final_score")) else round(float(row.get("final_score")), 4),
                "trend_vcp_component": None
                if pd.isna(row.get("trend_vcp_component"))
                else round(float(row.get("trend_vcp_component")), 4),
                "total_score_component": None
                if pd.isna(row.get("total_score_component"))
                else round(float(row.get("total_score_component")), 4),
                "rsi_component": None
                if pd.isna(row.get("rsi_component"))
                else round(float(row.get("rsi_component")), 4),
                "selector_signal_mode": None
                if pd.isna(row.get("selector_signal_mode"))
                else str(row.get("selector_signal_mode")),
                "selection_explanation": None
                if pd.isna(row.get("selection_explanation"))
                else str(row.get("selection_explanation")),
                "candidate_explainability_payload": explainability_payload,
            }
        )
    return rows


def _build_cli_run_summary(
    *,
    config: AlphaScannerConfig,
    result: pd.DataFrame,
    started_at: datetime,
    finished_at: datetime,
    rejected_by_filter: dict[str, int] | None = None,
    run_status: str = "completed",
    failure_reason: str | None = None,
    data_quality_gate: dict[str, object] | None = None,
    preselection_rejections: dict[str, object] | None = None,
    ablation: dict[str, object] | None = None,
) -> dict[str, object]:
    selected_symbols = (
        result["symbol"].astype(str).tolist()[:5]
        if "symbol" in result.columns and not result.empty
        else []
    )
    sector_breakdown = (
        result["sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
        .value_counts()
        .to_dict()
        if "sector" in result.columns and not result.empty
        else {}
    )
    max_final_score = None
    avg_final_score = None
    if "final_score" in result.columns and not result.empty:
        numeric_final_score = pd.Series(
            pd.to_numeric(result["final_score"], errors="coerce"),
            index=result.index,
        ).dropna()
        if not numeric_final_score.empty:
            max_final_score = round(float(numeric_final_score.max()), 4)
            avg_final_score = round(float(numeric_final_score.mean()), 4)

    small_selected_sectors = {
        sector: count
        for sector, count in sector_breakdown.items()
        if int(count) < 3
    }
    top_candidate_explanations = _build_top_candidate_explanations(result)

    return attach_schema_version({
        "run_id": _build_run_id("alpha-scanner"),
        "run_status": str(run_status).strip() or "completed",
        "failure_reason": failure_reason,
        "preset_profile": str(getattr(config, "preset_profile", STRICT_SWING_CASH_FILTERS.name)).strip()
        or STRICT_SWING_CASH_FILTERS.name,
        "preset_profile_version": getattr(config, "preset_profile_version", None),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "chunk_size": config.chunk_size,
        "requested_selection_size": config.selection_size,
        "selected_candidates": int(len(result)),
        "selection_fill_ratio": round((len(result) / config.selection_size), 4)
        if config.selection_size > 0
        else 0.0,
        "workers": config.max_workers or min(8, os.cpu_count() or 1),
        "sector_cap_ratio": round(float(config.sector_cap_ratio), 4),
        "selected_sectors": int(result["sector"].nunique())
        if "sector" in result.columns and not result.empty
        else 0,
        "sector_breakdown": sector_breakdown,
        "top_symbols": selected_symbols,
        "max_final_score": max_final_score,
        "avg_final_score": avg_final_score,
        "max_anomaly_count": config.max_anomaly_count,
        "max_spread_bps": config.max_spread_bps,
        "max_spread_bps_iex": config.max_spread_bps_iex,
        "min_quote_size": config.min_quote_size,
        "market_cap_max_age_days": config.market_cap_max_age_days,
        "earnings_blackout_days": config.earnings_blackout_days,
        "data_quality_modes": {
            "spread": config.spread_data_quality_mode,
            "earnings_blackout": config.earnings_data_quality_mode,
            "market_cap_ttl": config.market_cap_filter_data_quality_mode,
        },
        "skipped_filters": (
            list(data_quality_gate.get("skipped_filters", []))
            if isinstance(data_quality_gate, dict)
            else []
        ),
        "small_selected_sectors": small_selected_sectors,
        "top_candidate_explanations": top_candidate_explanations,
        "preselection_rejections": preselection_rejections,
        "ablation": ablation,
        "data_quality_gate": data_quality_gate,
        # Phase 3.3.b — agrégat des rejets par filtre (cross-chunks).
        "rejected_by_filter": dict(sorted((rejected_by_filter or {}).items())),
    })


def _summarize_zero_candidate_filters(rejected_by_filter: dict[str, int] | None) -> str:
    stats = {str(key): int(value) for key, value in (rejected_by_filter or {}).items()}
    if not stats:
        return "rejets_par_filtre indisponibles"

    label_map = {
        "rejected_volatility": "volatilite_relative",
        "rejected_relative_strength": "force_relative",
        "rejected_beta": "beta",
        "rejected_atr": "atr_pct",
        "rejected_weekly": "weekly",
        "rejected_spread": "spread",
        "rejected_ma200": "ma200",
        "rejected_market_cap": "market_cap",
        "rejected_high_52w": "high_52w",
        "rejected_earnings_blackout": "earnings_blackout",
    }
    ranked_rejections = sorted(
        (
            (label_map.get(key, key), value)
            for key, value in stats.items()
            if key.startswith("rejected_") and value > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    top_rejections = ", ".join(f"{label}={value}" for label, value in ranked_rejections[:4])
    if not top_rejections:
        top_rejections = "aucun rejet significatif capture"

    survivors = int(stats.get("input", 0))
    stage_order = (
        "rejected_etf",
        "rejected_history",
        "rejected_price",
        "rejected_market_liquidity",
        "rejected_volatility",
        "rejected_atr",
        "rejected_relative_strength",
        "rejected_ma200",
        "rejected_high_52w",
        "rejected_weekly",
        "rejected_market_cap",
        "rejected_market_cap_stale",
        "rejected_beta",
        "rejected_spread",
        "rejected_earnings_blackout",
        "rejected_score_liquidity",
        "rejected_sanitizer",
        "rejected_anomalies",
        "rejected_missing_days",
    )
    remaining_after_stage: dict[str, int] = {}
    for key in stage_order:
        survivors = max(survivors - int(stats.get(key, 0)), 0)
        remaining_after_stage[key] = survivors

    extra_hints: list[str] = []
    before_beta = remaining_after_stage.get("rejected_market_cap_stale", 0)
    before_spread = remaining_after_stage.get("rejected_beta", 0)
    after_spread = remaining_after_stage.get("rejected_spread", 0)
    if before_spread > 0 and after_spread == 0 and int(stats.get("rejected_spread", 0)) == before_spread:
        extra_hints.append(f"tous_les_survivants_avant_spread={before_spread} ont ete rejetes_au_spread")
    if before_beta > 0 and int(stats.get("rejected_beta", 0)) >= max(10, before_beta // 2):
        extra_hints.append(
            f"beta_tres_selectif={stats.get('rejected_beta', 0)}/{before_beta} rejetes_apres_market_cap"
        )

    detail = f"top_rejets=[{top_rejections}]"
    if extra_hints:
        detail += " | " + " | ".join(extra_hints)
    return detail


__all__ = [
    "_utc_now_naive",
    "_build_run_id",
    "_emit_run_summary",
    "_build_cli_run_summary",
    "_summarize_zero_candidate_filters",
]

