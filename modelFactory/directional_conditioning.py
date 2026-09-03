"""Conditionnement directionnel sur les prédictions OOF de l'Oracle Extreme.

Le gate ne supprime jamais les lignes de marché utilisées comme historique de
séquence. Il borne uniquement les *endpoints* qui portent une cible et peuvent
donc devenir des observations d'entraînement/validation/test.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelFactory.oracle.extreme_gate import DEFAULT_POOL_PCT, compute_extreme_gate

ORACLE_PROBA_COLUMN = "directional_oracle_proba_extreme"
ORACLE_PERCENTILE_COLUMN = "directional_oracle_extreme_pct"
ORACLE_AVAILABLE_COLUMN = "directional_oracle_oof_available"
ORACLE_ELIGIBLE_COLUMN = "directional_oracle_eligible"
ORACLE_FOLD_COLUMN = "directional_oracle_fold_start"


def build_directional_oof_gate(
    oracle_oof: pd.DataFrame,
    *,
    pool_pct: float = DEFAULT_POOL_PCT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Construit le gate TOP-pct depuis les seules prédictions Oracle OOF.

    ``fold_start`` est obligatoire et non nul : son absence empêcherait de
    distinguer une vraie prédiction de test Walk-Forward d'un score recalculé
    in-sample avec un champion final.
    """
    required = {"date", "symbol", "proba_extreme", "fold_start"}
    missing = sorted(required - set(oracle_oof.columns))
    if missing:
        raise ValueError(f"directional_oracle_oof_missing_columns:{','.join(missing)}")
    if not 0.0 < float(pool_pct) < 1.0:
        raise ValueError("directional_oracle_pool_pct doit être dans ]0,1[.")

    frame = oracle_oof.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["proba_extreme"] = pd.to_numeric(frame["proba_extreme"], errors="coerce")
    frame["fold_start"] = pd.to_datetime(frame["fold_start"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date", "symbol", "proba_extreme", "fold_start"])
    frame = frame[np.isfinite(frame["proba_extreme"].to_numpy(dtype=float))]
    if frame.empty:
        raise ValueError("directional_oracle_oof_empty")
    duplicates = frame.duplicated(subset=["date", "symbol"], keep=False)
    if bool(duplicates.any()):
        raise ValueError(
            "directional_oracle_oof_duplicate_date_symbol:"
            f"rows={int(duplicates.sum())}"
        )

    gated = compute_extreme_gate(frame, pool_pct=float(pool_pct))
    gated = gated.rename(columns={
        "proba_extreme": ORACLE_PROBA_COLUMN,
        "extreme_pct": ORACLE_PERCENTILE_COLUMN,
        "extreme_gate": ORACLE_ELIGIBLE_COLUMN,
        "fold_start": ORACLE_FOLD_COLUMN,
    })
    gated[ORACLE_AVAILABLE_COLUMN] = True
    gated[ORACLE_ELIGIBLE_COLUMN] = gated[ORACLE_ELIGIBLE_COLUMN].astype(bool)
    gated = gated.sort_values(["date", "symbol"]).reset_index(drop=True)

    daily_sizes = gated.groupby("date")["symbol"].nunique()
    selected = int(gated[ORACLE_ELIGIBLE_COLUMN].sum())
    diagnostics: dict[str, Any] = {
        "schema_version": 1,
        "source": "oracle_walk_forward_oof_test",
        "oof_only": True,
        "pool_pct": float(pool_pct),
        "rows": int(len(gated)),
        "dates": int(gated["date"].nunique()),
        "symbols": int(gated["symbol"].nunique()),
        "eligible_rows": selected,
        "eligible_fraction": float(selected / len(gated)),
        "daily_universe_min": int(daily_sizes.min()),
        "daily_universe_median": float(daily_sizes.median()),
        "daily_universe_max": int(daily_sizes.max()),
        "first_date": str(gated["date"].min().date()),
        "last_date": str(gated["date"].max().date()),
    }
    return gated, diagnostics


def attach_directional_oof_gate(
    prepared_df: pd.DataFrame,
    oracle_gate_df: pd.DataFrame,
) -> pd.DataFrame:
    """Joint le gate OOF à un historique mono-symbole sans retirer de lignes."""
    if "date" not in prepared_df.columns:
        raise ValueError("directional_conditioning_requires_date")
    required = {
        "date",
        ORACLE_PROBA_COLUMN,
        ORACLE_PERCENTILE_COLUMN,
        ORACLE_AVAILABLE_COLUMN,
        ORACLE_ELIGIBLE_COLUMN,
        ORACLE_FOLD_COLUMN,
    }
    missing = sorted(required - set(oracle_gate_df.columns))
    if missing:
        raise ValueError(f"directional_oracle_gate_missing_columns:{','.join(missing)}")

    left = prepared_df.copy()
    attrs = dict(prepared_df.attrs)
    left["date"] = pd.to_datetime(left["date"], errors="raise").dt.normalize()
    gate = oracle_gate_df.loc[:, sorted(required)].copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="raise").dt.normalize()
    if bool(gate.duplicated(subset=["date"], keep=False).any()):
        raise ValueError("directional_oracle_gate_duplicate_date_for_symbol")

    out = left.merge(gate, on="date", how="left", validate="one_to_one")
    out[ORACLE_AVAILABLE_COLUMN] = out[ORACLE_AVAILABLE_COLUMN].eq(True)  # noqa: E712
    out[ORACLE_ELIGIBLE_COLUMN] = out[ORACLE_ELIGIBLE_COLUMN].eq(True)  # noqa: E712
    available = int(out[ORACLE_AVAILABLE_COLUMN].sum())
    eligible = int(out[ORACLE_ELIGIBLE_COLUMN].sum())
    attrs["directional_conditioning"] = {
        "enabled": True,
        "source": "oracle_walk_forward_oof_test",
        "rows": int(len(out)),
        "oof_available_rows": available,
        "eligible_rows": eligible,
        "oof_coverage": float(available / len(out)) if len(out) else 0.0,
        "eligible_fraction_all_rows": float(eligible / len(out)) if len(out) else 0.0,
        "eligible_fraction_oof_rows": float(eligible / available) if available else 0.0,
    }
    out.attrs = attrs
    return out


def eligible_target_mask(df: pd.DataFrame) -> pd.Series:
    """Lignes autorisées comme endpoints, avec cible finie et gate OOF vrai."""
    if "target" not in df.columns:
        raise ValueError("eligible_target_mask requiert une colonne 'target'.")
    target = pd.to_numeric(df["target"], errors="coerce")
    mask = pd.Series(np.isfinite(target), index=df.index, dtype=bool)
    if ORACLE_ELIGIBLE_COLUMN in df.columns:
        mask &= df[ORACLE_ELIGIBLE_COLUMN].eq(True)  # noqa: E712
    return mask


def filter_eligible_target_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Filtre les observations tabulaires sur la population Oracle OOF."""
    return df.loc[eligible_target_mask(df)].copy()
