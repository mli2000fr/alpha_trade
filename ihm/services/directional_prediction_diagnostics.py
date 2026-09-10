"""Mesure OOS des probabilités directionnelles servies par un bundle ML."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


SUPPORTED_HORIZONS = (3, 5, 10, 20)


def attach_forward_returns(
    predictions: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    horizon: int,
    benchmark_symbol: str = "SPY",
) -> pd.DataFrame:
    """Ajoute les rendements futurs à H séances, sans utiliser de jours calendaires."""
    if predictions.empty or bars.empty:
        return pd.DataFrame()
    h = int(horizon)
    if h not in SUPPORTED_HORIZONS:
        raise ValueError(f"Horizon non supporté: {h}")

    prices = bars[["symbol", "date", "adj_close"]].copy()
    prices["symbol"] = prices["symbol"].astype(str).str.upper()
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    prices["adj_close"] = pd.to_numeric(prices["adj_close"], errors="coerce")
    prices = prices.dropna(subset=["symbol", "date", "adj_close"])
    prices = prices.drop_duplicates(["symbol", "date"], keep="last").sort_values(["symbol", "date"])
    prices["future_return"] = (
        prices.groupby("symbol", sort=False)["adj_close"].shift(-h) / prices["adj_close"] - 1.0
    )

    benchmark = prices[prices["symbol"] == benchmark_symbol.upper()][["date", "future_return"]].rename(
        columns={"future_return": "benchmark_future_return"}
    )
    assets = prices[["symbol", "date", "future_return"]]

    out = predictions.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["prediction_date"] = pd.to_datetime(out["prediction_date"]).dt.normalize()
    out = out.merge(
        assets,
        left_on=["symbol", "prediction_date"],
        right_on=["symbol", "date"],
        how="left",
    ).drop(columns=["date"])
    out = out.merge(benchmark, left_on="prediction_date", right_on="date", how="left").drop(columns=["date"])
    out["excess_future_return"] = out["future_return"] - out["benchmark_future_return"]
    return out


def oracle_top_fraction(frame: pd.DataFrame, fraction: float = 0.20) -> pd.DataFrame:
    """Filtre le pool Oracle avec la même règle percentile que la cascade."""
    if frame.empty or "proba_extreme" not in frame.columns:
        return pd.DataFrame(columns=frame.columns)
    if "oracle_top_pool" in frame.columns:
        return frame.loc[frame["oracle_top_pool"].fillna(False).astype(bool)].copy()
    valid = frame.dropna(subset=["prediction_date", "proba_extreme"]).copy()
    valid["_oracle_percentile"] = valid.groupby("prediction_date")["proba_extreme"].rank(pct=True)
    selected = valid.loc[valid["_oracle_percentile"] >= (1.0 - float(fraction))].copy()
    return selected.drop(columns=["_oracle_percentile"])


def _daily_top_fraction(frame: pd.DataFrame, score_column: str, fraction: float) -> pd.DataFrame:
    """Sélection déterministe des ceil(N*fraction) meilleurs scores de chaque date."""
    if frame.empty:
        return frame.copy()
    selected: list[pd.DataFrame] = []
    for _, day in frame.sort_values(["prediction_date", score_column, "symbol"]).groupby(
        "prediction_date", sort=True
    ):
        n = max(1, int(np.ceil(len(day) * float(fraction))))
        selected.append(day.sort_values([score_column, "symbol"], ascending=[False, True]).head(n))
    return pd.concat(selected, ignore_index=True) if selected else frame.iloc[0:0].copy()


def evaluate_directional_top_decile(
    frame: pd.DataFrame,
    *,
    side: str,
    extreme_threshold: float = 0.03,
) -> dict[str, Any]:
    """Évalue le top 10 % quotidien de P(LONG) ou P(SHORT) sur rendements arrivés à maturité."""
    normalized_side = str(side).strip().lower()
    if normalized_side not in {"long", "short"}:
        raise ValueError(f"Side invalide: {side!r}")
    probability = f"proba_{normalized_side}"
    required = ["prediction_date", "symbol", probability, "future_return"]
    if frame.empty or any(column not in frame.columns for column in required):
        return {"eligible": pd.DataFrame(), "picks": pd.DataFrame(), "metrics": {}, "by_symbol": pd.DataFrame()}

    # La sélection doit être faite avec l'information disponible à la date de
    # prédiction. On ne retire donc pas les observations non encore arrivées à
    # maturité avant de construire le top 10 %, sinon un candidat récent sans
    # label futur serait remplacé rétrospectivement par le suivant du classement.
    eligible = frame.dropna(subset=["prediction_date", "symbol", probability]).copy()
    eligible[probability] = pd.to_numeric(eligible[probability], errors="coerce")
    eligible["future_return"] = pd.to_numeric(eligible["future_return"], errors="coerce")
    eligible = eligible.dropna(subset=[probability])
    eligible = eligible[eligible[probability].between(0.0, 1.0)]
    if eligible.empty:
        return {"eligible": eligible, "picks": eligible.copy(), "metrics": {}, "by_symbol": pd.DataFrame()}

    direction = 1.0 if normalized_side == "long" else -1.0
    eligible["signed_return"] = direction * eligible["future_return"]
    if "excess_future_return" in eligible.columns:
        eligible["signed_excess_return"] = direction * pd.to_numeric(
            eligible["excess_future_return"], errors="coerce"
        )
    else:
        eligible["signed_excess_return"] = np.nan

    selected = _daily_top_fraction(eligible, probability, 0.10)
    picks = selected.dropna(subset=["future_return"]).copy()
    matured_eligible = eligible.dropna(subset=["future_return"])
    if picks.empty:
        return {
            "eligible": eligible,
            "selected": selected,
            "picks": picks,
            "metrics": {
                "n_eligible": len(eligible),
                "n_selected": len(selected),
                "n_picks": 0,
                "n_dates": 0,
                "n_symbols": 0,
            },
            "by_symbol": pd.DataFrame(),
        }
    picks["direction_hit"] = picks["signed_return"] > 0.0
    picks["extreme_hit"] = picks["signed_return"] >= float(extreme_threshold)
    eligible_hit_rate = float((matured_eligible["signed_return"] > 0.0).mean())
    daily = picks.groupby("prediction_date", sort=True)["signed_return"].mean()

    metrics = {
        "n_eligible": len(eligible),
        "n_selected": len(selected),
        "n_picks": len(picks),
        "n_dates": int(picks["prediction_date"].nunique()),
        "n_symbols": int(picks["symbol"].nunique()),
        "hit_rate": float(picks["direction_hit"].mean()),
        "baseline_hit_rate": eligible_hit_rate,
        "hit_lift_pp": float((picks["direction_hit"].mean() - eligible_hit_rate) * 100.0),
        "extreme_hit_rate": float(picks["extreme_hit"].mean()),
        "mean_signed_return": float(picks["signed_return"].mean()),
        "median_signed_return": float(picks["signed_return"].median()),
        "mean_signed_excess_return": float(picks["signed_excess_return"].mean()),
        "profitable_date_rate": float((daily > 0.0).mean()),
        "worst_date_return": float(daily.min()),
    }

    by_symbol = (
        picks.groupby("symbol", as_index=False)
        .agg(
            observations=("symbol", "size"),
            hit_rate=("direction_hit", "mean"),
            extreme_hit_rate=("extreme_hit", "mean"),
            mean_signed_return=("signed_return", "mean"),
            median_signed_return=("signed_return", "median"),
            mean_probability=(probability, "mean"),
        )
        .sort_values(["observations", "mean_signed_return"], ascending=[False, False])
    )
    return {
        "eligible": eligible,
        "selected": selected,
        "picks": picks,
        "metrics": metrics,
        "by_symbol": by_symbol,
    }
