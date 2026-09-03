"""Point-in-time validation for persisted ML predictions used by backtests."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class PredictionPitViolationError(RuntimeError):
    """Raised when a prediction was produced by a model unavailable as-of date."""


@dataclass(frozen=True)
class PredictionPitAudit:
    checked_rows: int
    invalid_rows: int


def assert_directional_bundle_predictions_pit(
    predictions: pd.DataFrame,
) -> PredictionPitAudit:
    """Fail closed unless both directional models predate every prediction.

    A persisted prediction is not automatically OOS/PIT.  For a directional
    bundle, ``proba_long`` and ``proba_short`` come from two different runs;
    both ``train_end_date`` values must therefore be strictly earlier than the
    simulated ``trade_date``.  Missing lineage or cut-off metadata is unsafe
    and is rejected as well.
    """
    if predictions.empty:
        return PredictionPitAudit(checked_rows=0, invalid_rows=0)

    required = {
        "symbol",
        "trade_date",
        "direction_long_run_id",
        "direction_short_run_id",
        "direction_long_train_end_date",
        "direction_short_train_end_date",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise PredictionPitViolationError(
            "Audit PIT directionnel impossible : métadonnées manquantes dans "
            f"model_predictions ({', '.join(missing)})."
        )

    frame = predictions.copy()
    trade_date = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    long_end = pd.to_datetime(
        frame["direction_long_train_end_date"], errors="coerce"
    ).dt.normalize()
    short_end = pd.to_datetime(
        frame["direction_short_train_end_date"], errors="coerce"
    ).dt.normalize()
    long_run = frame["direction_long_run_id"].astype("string").str.strip()
    short_run = frame["direction_short_run_id"].astype("string").str.strip()

    valid = (
        trade_date.notna()
        & long_run.notna()
        & long_run.ne("")
        & short_run.notna()
        & short_run.ne("")
        & long_end.notna()
        & short_end.notna()
        & long_end.lt(trade_date)
        & short_end.lt(trade_date)
    )
    invalid = frame.loc[~valid].copy()
    if invalid.empty:
        return PredictionPitAudit(checked_rows=len(frame), invalid_rows=0)

    invalid["_trade_date"] = trade_date.loc[invalid.index]
    invalid["_long_end"] = long_end.loc[invalid.index]
    invalid["_short_end"] = short_end.loc[invalid.index]
    examples: list[str] = []
    for _, row in invalid.head(5).iterrows():
        examples.append(
            "{}@{} (LONG fin={}, SHORT fin={})".format(
                row.get("symbol", "?"),
                row["_trade_date"].date()
                if pd.notna(row["_trade_date"])
                else "inconnue",
                row["_long_end"].date()
                if pd.notna(row["_long_end"])
                else "inconnue",
                row["_short_end"].date()
                if pd.notna(row["_short_end"])
                else "inconnue",
            )
        )
    raise PredictionPitViolationError(
        "Fuite temporelle ML : {}/{} prédictions du bundle directionnel ont "
        "été produites par au moins un modèle qui n'existait pas encore à la "
        "date simulée (train_end_date doit être strictement antérieure). "
        "Exemples : {}. Utiliser des prédictions walk-forward réellement OOS "
        "ou commencer le backtest après les deux fins d'entraînement."
        .format(len(invalid), len(frame), "; ".join(examples))
    )
