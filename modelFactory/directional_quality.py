"""Quality gate for serving directional Per-Symbol bundles.

The training UI exposes two candidate sets (STRICT and DISCOVERY).  This
module is the runtime contract: a backtest can only emit a LONG/SHORT when the
corresponding specialized branch satisfies the selected Walk-Forward gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

VALID_DIRECTIONAL_GATE_LEVELS = frozenset({"strict", "discovery", "off"})


@dataclass(frozen=True)
class DirectionalQualityGate:
    batch_id: str
    level: str
    scanned_symbols: int
    allowed_long: frozenset[str]
    allowed_short: frozenset[str]
    audit_df: pd.DataFrame


def load_directional_quality_gate(
    batch_id: str,
    artifacts_dir: Path | str,
    *,
    level: str = "strict",
) -> DirectionalQualityGate:
    """Load the same side-specific gate shown/downloaded by Diagnostic ML."""
    normalized_level = str(level or "strict").strip().lower()
    if normalized_level not in VALID_DIRECTIONAL_GATE_LEVELS:
        raise ValueError(
            "directional_bundle_gate must be one of: strict, discovery, off"
        )

    # Lazy import keeps the model runtime independent from Streamlit startup
    # while reusing one authoritative implementation of the WF calculations.
    from ihm.services.ml_artifacts import build_batch_directional_candidate_selection

    selection: dict[str, Any] = build_batch_directional_candidate_selection(
        batch_id,
        Path(artifacts_dir),
    )
    audit_df = selection.get("audit_df")
    if not isinstance(audit_df, pd.DataFrame):
        audit_df = pd.DataFrame()

    if normalized_level == "off":
        symbols = {
            str(value).strip().upper()
            for value in audit_df.get("symbol", pd.Series(dtype="object"))
            if str(value).strip()
        }
        allowed_long = allowed_short = symbols
    else:
        group = selection.get(normalized_level) or {}
        both = set(group.get("long_short") or [])
        allowed_long = set(group.get("long_only") or []) | both
        allowed_short = set(group.get("short_only") or []) | both

    return DirectionalQualityGate(
        batch_id=str(batch_id),
        level=normalized_level,
        scanned_symbols=int(selection.get("scanned_symbols") or len(audit_df)),
        allowed_long=frozenset(str(v).strip().upper() for v in allowed_long),
        allowed_short=frozenset(str(v).strip().upper() for v in allowed_short),
        audit_df=audit_df.copy(),
    )


def apply_directional_quality_gate(
    predictions: pd.DataFrame,
    gate: DirectionalQualityGate,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Turn ineligible directional decisions into FLAT, side by side."""
    result = predictions.copy()
    counts = {
        "long_before": 0,
        "short_before": 0,
        "long_rejected": 0,
        "short_rejected": 0,
    }
    if result.empty or "symbol" not in result.columns or "predicted_side" not in result.columns:
        return result, counts

    symbols = result["symbol"].astype(str).str.strip().str.upper()
    sides = result["predicted_side"].astype(str).str.strip().str.lower()
    long_mask = sides.eq("long")
    short_mask = sides.eq("short")
    reject_long = long_mask & ~symbols.isin(gate.allowed_long)
    reject_short = short_mask & ~symbols.isin(gate.allowed_short)
    rejected = reject_long | reject_short

    counts.update(
        long_before=int(long_mask.sum()),
        short_before=int(short_mask.sum()),
        long_rejected=int(reject_long.sum()),
        short_rejected=int(reject_short.sum()),
    )
    result.loc[rejected, "predicted_side"] = "flat"
    for column in ("cascade_score", "selection_score"):
        if column in result.columns:
            result.loc[rejected, column] = 0.0
    if "directional_quality_rejected" not in result.columns:
        result["directional_quality_rejected"] = False
    result.loc[rejected, "directional_quality_rejected"] = True
    result["directional_quality_rejected"] = result["directional_quality_rejected"].astype(bool)
    return result, counts
