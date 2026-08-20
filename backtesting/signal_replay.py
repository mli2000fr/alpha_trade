"""Reconstruction predictions-first des signaux de trading.

Refactor Phase A (refactor/backtesting/audit_plan.md) :
- A2 : ``fuse()`` vectorisé (suppression du ``df.apply`` ligne par ligne).
- A3 : cascade de fallback factorisée via ``_pick_score_column`` +
       ``SCORE_FALLBACK_PRIORITY`` (au lieu de 4 branches dupliquées).

Sprint Maître 0 :
- ``predicted_side`` est produit par ``decide_ternary_side`` (policy partagée).
  Ce module ne recrée PAS de décision de side ; il lit la colonne
  ``predicted_side`` persistée, garantissant la parité backtest/live.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from core.ternary_decision_policy import DEFAULT_TERNARY_POLICY

LOGGER = logging.getLogger(__name__)

# Ordre de priorité des colonnes de score (du plus riche au plus brut).
SCORE_FALLBACK_PRIORITY: tuple[str, ...] = (
    "final_score_walk_forward",
    "final_score_sentiment",
    "final_score",
)


def _validate_prediction_policy_consistency(df: pd.DataFrame) -> None:
    """Vérifie que les prédictions utilisent bien la policy ternaire partagée (Sprint Maître 0).

    Les prédictions sans colonnes ternaires complètes ou avec des sides
    non conformes à la policy sont loggées mais ne bloquent pas le replay
    (rétrocompatibilité avec les données antérieures au Sprint 0).
    """
    policy_version = DEFAULT_TERNARY_POLICY.version
    if "decision_policy_version" in df.columns:
        legacy = df["decision_policy_version"].isna() | (df["decision_policy_version"] != policy_version)
        if legacy.any():
            LOGGER.info(
                "replay_signals legacy_predictions: %d/%d rows antérieures au policy v%d",
                legacy.sum(), len(df), policy_version,
            )
    # Vérification de cohérence basique
    valid_sides = {"long", "flat", "short"}
    unknown = ~df["predicted_side"].isin(valid_sides)
    if unknown.any():
        LOGGER.warning(
            "replay_signals unknown_predicted_side: %d rows (attendu long/flat/short)",
            unknown.sum(),
        )


def _pick_score_column(
    df: pd.DataFrame,
    preferred: str | None,
    fallback_priority: Iterable[str] = SCORE_FALLBACK_PRIORITY,
) -> tuple[pd.Series, pd.Series]:
    """Construit ``(score, score_source)`` à partir d'une cascade de colonnes.

    Prend d'abord ``preferred`` si fourni et présent, puis comble les NaN
    restants avec les colonnes du ``fallback_priority`` dans l'ordre.
    """
    columns_in_order: list[str] = []
    if preferred and preferred in df.columns:
        columns_in_order.append(preferred)
    for col in fallback_priority:
        if col in df.columns and col not in columns_in_order:
            columns_in_order.append(col)

    if not columns_in_order:
        raise ValueError(
            "scores_df doit contenir au moins une colonne parmi "
            f"{list(fallback_priority)} (ou ``preferred`` valide)."
        )

    score = pd.Series(np.nan, index=df.index, dtype=float)
    source = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in columns_in_order:
        col_series = pd.to_numeric(df[col], errors="coerce")
        missing_mask = score.isna() & col_series.notna()
        if not missing_mask.any():
            continue
        score = score.where(~missing_mask, col_series)
        source = source.where(~missing_mask, col)
    return score, source


def replay_signals(
    predictions_df: pd.DataFrame,
    scores_df: Optional[pd.DataFrame] = None,
    *,
    score_column: str | None = None,
    max_positions: int = 20,
    max_long_positions: int | None = None,
    max_short_positions: int | None = None,
    min_proba_long: float = 0.0,
    min_proba_short: float = 0.0,
    min_score_long: float | None = None,
    max_score_short: float | None = None,
) -> pd.DataFrame:
    """Reconstruit des signaux à partir des prédictions ternaires.

    ``predictions_df`` est la source de portée et de classement. ``scores_df``
    est joint uniquement pour fournir secteur, score et futurs vetos; aucun
    score absent ou élevé ne peut créer un signal sans prédiction ML.

    Returns
    -------
    DataFrame : trade_date, symbol, predicted_side, proba_long, proba_short,
                selection_score, long_rank, short_rank, selected, side,
                avec les éventuelles colonnes de contexte score.
    """
    required_prediction_columns = {
        "symbol", "trade_date", "predicted_side", "proba_long", "proba_short",
    }
    missing_prediction_columns = required_prediction_columns.difference(predictions_df.columns)
    if missing_prediction_columns:
        raise ValueError(
            "predictions_df requiert les colonnes ternaires: "
            f"{sorted(missing_prediction_columns)}"
        )
    if max_positions < 1:
        raise ValueError("max_positions doit être >= 1.")

    long_limit = max_positions if max_long_positions is None else max_long_positions
    short_limit = max_positions if max_short_positions is None else max_short_positions
    if not 0 <= long_limit <= max_positions:
        raise ValueError("max_long_positions doit être dans [0, max_positions].")
    if not 0 <= short_limit <= max_positions:
        raise ValueError("max_short_positions doit être dans [0, max_positions].")
    if not 0.0 <= min_proba_long <= 1.0:
        raise ValueError("min_proba_long doit être dans [0, 1].")
    if not 0.0 <= min_proba_short <= 1.0:
        raise ValueError("min_proba_short doit être dans [0, 1].")
    if min_score_long is not None and not 0.0 <= min_score_long <= 1.0:
        raise ValueError("min_score_long doit être dans [0, 1].")
    if max_score_short is not None and not 0.0 <= max_score_short <= 1.0:
        raise ValueError("max_score_short doit être dans [0, 1].")

    df = predictions_df.copy()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
    df["predicted_side"] = df["predicted_side"].astype(str).str.strip().str.lower()
    df["proba_long"] = pd.to_numeric(df["proba_long"], errors="coerce")
    df["proba_short"] = pd.to_numeric(df["proba_short"], errors="coerce")
    df = df.dropna(subset=["symbol", "trade_date"])
    df = df.drop_duplicates(subset=["symbol", "trade_date"], keep="last")

    # ── Sprint Maître 0 : valider que predicted_side vient de la policy ─
    _validate_prediction_policy_consistency(df)

    is_long = df["predicted_side"].eq("long") & df["proba_long"].notna()
    is_short = df["predicted_side"].eq("short") & df["proba_short"].notna()
    df = df.loc[is_long | is_short].copy()
    df["side"] = np.where(df["predicted_side"].eq("short"), "sell", "buy")
    df["selection_score"] = np.where(
        df["predicted_side"].eq("long"), df["proba_long"], df["proba_short"],
    )
    df["predicted_proba"] = df["selection_score"]
    df["conviction"] = df["selection_score"]
    df["conviction_source"] = "ml_ternary"
    df["long_rank"] = np.nan
    df["short_rank"] = np.nan
    long_mask = df["predicted_side"].eq("long")
    short_mask = df["predicted_side"].eq("short")
    df.loc[long_mask, "long_rank"] = df.loc[long_mask].groupby("trade_date")["proba_long"].rank(
        ascending=False, method="first"
    )
    df.loc[short_mask, "short_rank"] = df.loc[short_mask].groupby("trade_date")["proba_short"].rank(
        ascending=False, method="first"
    )
    df["rank"] = np.where(long_mask, df["long_rank"], df["short_rank"])
    df["selected"] = (
        (long_mask & (df["long_rank"] <= long_limit))
        | (short_mask & (df["short_rank"] <= short_limit))
    )

    # Le plafond total s'applique après les plafonds directionnels. Un tri
    # déterministe maintient les probabilités ML comme seule autorité de rang.
    selected = df.loc[df["selected"]].sort_values(
        ["trade_date", "selection_score", "symbol"],
        ascending=[True, False, True],
        kind="stable",
    )
    total_rank = selected.groupby("trade_date").cumcount() + 1
    df["selection_rank"] = np.nan
    df.loc[selected.index, "selection_rank"] = total_rank.to_numpy()
    df.loc[df["selected"] & (df["selection_rank"] > max_positions), "selected"] = False

    if scores_df is None or scores_df.empty:
        df["score"] = np.nan
        df["score_source"] = pd.NA
        df["sector"] = None
    else:
        base_columns = ["symbol", "trade_date"]
        optional_columns = [
            score_column,
            *SCORE_FALLBACK_PRIORITY,
            "sector",
            "score_source",
            "atr_pct_20",
        ]
        keep_columns = list(base_columns)
        for col in optional_columns:
            if col is not None and col in scores_df.columns and col not in keep_columns:
                keep_columns.append(col)
        context = scores_df[keep_columns].copy()
        context["symbol"] = context["symbol"].astype(str).str.strip().str.upper()
        context["trade_date"] = pd.to_datetime(context["trade_date"], errors="coerce").dt.normalize()
        context = context.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
        score, source = _pick_score_column(context, preferred=score_column)
        context["score"] = score
        context["score_source"] = source
        if "sector" not in context.columns:
            context["sector"] = None
        merge_columns = ["symbol", "trade_date", "score", "score_source", "sector"]
        df = df.merge(
            context[merge_columns],
            on=["symbol", "trade_date"],
            how="left",
        )
        # ── Fix asof atr_pct_20 (2026-08-20) ──────────────────────────────
        # Les snapshots de scores n'existent que sur une fraction des dates de
        # trading. Un merge EXACT laissait atr_pct_20=NaN sur ~83% des signaux,
        # ce qui désactivait le TP de production min(3×ATR, 7%) et le stop ATR
        # (2.5×ATR) → le simulateur retombait sur TP=12% fixe / trailing=7%
        # (défauts CLI --tp/--ts). On prend ici le dernier snapshot disponible
        # ≤ date du signal (point-in-time, pas de fuite future).
        if "atr_pct_20" in context.columns:
            atr_lookup = (
                context[["symbol", "trade_date", "atr_pct_20"]]
                .dropna(subset=["atr_pct_20"])
                .sort_values("trade_date")
            )
            if not atr_lookup.empty:
                df_sorted = df.sort_values("trade_date").copy()
                df_asof = pd.merge_asof(
                    df_sorted[["symbol", "trade_date"]],
                    atr_lookup,
                    on="trade_date",
                    by="symbol",
                    direction="backward",
                    allow_exact_matches=True,
                )
                df_sorted["atr_pct_20"] = df_asof["atr_pct_20"].to_numpy()
                df = df_sorted.sort_index()

    df["veto_reason"] = pd.NA
    probability_veto = (
        (df["predicted_side"].eq("long") & (df["proba_long"] < min_proba_long))
        | (df["predicted_side"].eq("short") & (df["proba_short"] < min_proba_short))
    )
    df.loc[probability_veto, "veto_reason"] = "ml_probability_below_threshold"
    if min_score_long is not None:
        long_score_veto = (
            df["predicted_side"].eq("long")
            & df["score"].notna()
            & (df["score"] < min_score_long)
        )
        df.loc[long_score_veto, "veto_reason"] = "technical_score_long_veto"
    if max_score_short is not None:
        short_score_veto = (
            df["predicted_side"].eq("short")
            & df["score"].notna()
            & (df["score"] > max_score_short)
        )
        df.loc[short_score_veto, "veto_reason"] = "technical_score_short_veto"
    df.loc[df["veto_reason"].notna(), "selected"] = False

    LOGGER.info(
        "Signaux ML-first reconstruits : %d jours, %d entrées sélectionnées",
        df["trade_date"].nunique(),
        int(df["selected"].sum()),
    )
    return df

