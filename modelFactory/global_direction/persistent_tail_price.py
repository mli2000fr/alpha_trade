"""modelFactory/global_direction/persistent_tail_price.py — persistent_tail_price_confirmation.

Expérience DIAGNOSTIQUE (aucun réentraînement, aucun changement risk/PROD).

Hypothèse : la combinaison
    persistance dans une queue du ranking (N jours)  +  confirmation du prix (ret_N)
sélectionne davantage de vrais bons LONG/SHORT que la queue seule.

Paramètres pré-enregistrés (NE PAS étendre) :
    N ∈ {2, 3, 4, 5} ; X ∈ {0%, 1%, 2%, 3%}.

A. Oracle Extreme : TOP10% `proba_extreme` (extreme_pct >= 0.90), persistant N jours.
   - LONG  : persistent_extreme_N  AND ret_N >= +X
   - SHORT : persistent_extreme_N  AND ret_N <= -X

B. Global Rank (global_rank_20, H20) :
   - predicted_TOP10  = global_rank_20 >= 0.90
   - predicted_BOTTOM10 = global_rank_20 <= 0.10
   - 4 diagnostics (TOP10/BOTTOM10 × prix +X/−X) pour mesurer aussi les INVERSIONS.

Évaluation (fwd H20) : `future_return` des labels Oracle (horizon 20).
   - « bon LONG »  = future_return > 0
   - « bon SHORT » = future_return < 0
On compare chaque filtre à sa BASE (queue seule, sans persistance ni prix).

Sortie : artifacts/persistent_tail_price.csv

Usage :
    python -m modelFactory.global_direction.persistent_tail_price --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import load_oracle_pool_proba
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL
from modelFactory.oracle.dataset import load_oracle_targets

LOGGER = logging.getLogger(__name__)

N_LIST = [2, 3, 4, 5]
X_LIST = [0.00, 0.01, 0.02, 0.03]
RANK_COL = "global_rank_20"
TOP10 = 0.90
BOTTOM10 = 0.10


def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Panel quotidien (date, symbol) : proba_extreme, global_rank_20, close, labels fwd."""
    # Labels Oracle (future_return H20, décile)
    targets = load_oracle_targets(engine, batch_id, horizon=20)
    lab = targets[["prediction_date", "symbol", DECILE_COL, RETURN_COL]].rename(
        columns={"prediction_date": "date"})
    lab["date"] = pd.to_datetime(lab["date"], errors="coerce").dt.normalize()
    lab["symbol"] = lab["symbol"].astype(str).str.upper()

    # Oracle proba_extreme (OOS PIT)
    oracle = load_oracle_pool_proba(batch_id)
    oracle["date"] = pd.to_datetime(oracle["date"], errors="coerce").dt.normalize()

    # Global rank H20
    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history "
        "WHERE date BETWEEN %s AND %s",
        engine, params=(start_date, end_date),
    )
    rank["date"] = pd.to_datetime(rank["date"], errors="coerce").dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    # Prix (adj_close) avec lookback pour ret_N
    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=20)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, adj_close FROM stock_bars_daily WHERE date BETWEEN %s AND %s",
        engine, params=(lb, end_date),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "adj_close"])

    df = lab.merge(oracle, on=["date", "symbol"], how="left")
    df = df.merge(rank, on=["date", "symbol"], how="left")
    df = df.merge(bars, on=["date", "symbol"], how="left")
    df = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df


def compute_persistence(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute : extreme_pct/top10_extreme, top10/bottom10 rank, ret_N, persistent_*_N."""
    out = df.copy()
    # Oracle percentile cross-sectionnel du jour
    out["extreme_pct"] = out.groupby("date")["proba_extreme"].rank(pct=True)
    out["top10_extreme"] = (out["extreme_pct"] >= TOP10).astype(int)
    out["top10_rank"] = (out[RANK_COL] >= TOP10).astype(int)
    out["bottom10_rank"] = (out[RANK_COL] <= BOTTOM10).astype(int)
    # Prix : ret_N = close[J]/close[J-N]-1 (intra-symbole)
    g = out.groupby("symbol")["adj_close"]
    for N in N_LIST:
        out[f"ret_{N}"] = out["adj_close"] / g.shift(N) - 1.0
        # persistance : TOUS les jours J-N+1..J dans la queue
        for base, col in (("extreme", "top10_extreme"), ("rank_top10", "top10_rank"),
                          ("rank_bottom10", "bottom10_rank")):
            series = out[col]
            roll = series.groupby(out["symbol"]).transform(
                lambda x: x.rolling(N, min_periods=N).min())
            out[f"persistent_{base}_{N}"] = roll
    return out


def evaluate(panel: pd.DataFrame) -> pd.DataFrame:
    """Construit le tableau (signal, N, X, n, mean/med fwd, bon% , base)."""
    rows: list[dict[str, Any]] = []
    all_mean = float(panel[RETURN_COL].mean())

    signals = [
        # (nom, masque base, direction)
        ("oracle_top10", panel["top10_extreme"] == 1, "long"),
        ("rank_top10", panel["top10_rank"] == 1, "long"),
        ("rank_bottom10", panel["bottom10_rank"] == 1, "short"),
    ]
    for name, base_mask, direction in signals:
        base = panel[base_mask]
        if len(base) == 0:
            continue
        if direction == "long":
            base_good = float((base[RETURN_COL] > 0).mean())
        else:
            base_good = float((base[RETURN_COL] < 0).mean())
        # Base (queue seule)
        rows.append({
            "signal": name, "N": 0, "X": "base",
            "n": int(len(base)), "mean_fwd": float(base[RETURN_COL].mean()),
            "med_fwd": float(base[RETURN_COL].median()),
            "good_rate": base_good, "baseline_pool": all_mean,
        })
        # Persistance seule (P_N)
        for N in N_LIST:
            pcol = {"oracle_top10": f"persistent_extreme_{N}",
                    "rank_top10": f"persistent_rank_top10_{N}",
                    "rank_bottom10": f"persistent_rank_bottom10_{N}"}[name]
            p = panel[(panel[pcol] == 1)]
            if len(p):
                rows.append({
                    "signal": name, "N": N, "X": "P",
                    "n": int(len(p)), "mean_fwd": float(p[RETURN_COL].mean()),
                    "med_fwd": float(p[RETURN_COL].median()),
                    "good_rate": (float((p[RETURN_COL] > 0).mean()) if direction == "long"
                                  else float((p[RETURN_COL] < 0).mean())),
                    "baseline_pool": all_mean,
                })
            # Persistance + prix
            for X in X_LIST:
                if direction == "long":
                    cond = (panel[pcol] == 1) & (panel[f"ret_{N}"] >= X)
                else:
                    cond = (panel[pcol] == 1) & (panel[f"ret_{N}"] <= -X)
                sub = panel[cond]
                if len(sub) == 0:
                    continue
                good = float((sub[RETURN_COL] > 0).mean()) if direction == "long" \
                    else float((sub[RETURN_COL] < 0).mean())
                rows.append({
                    "signal": name, "N": N, "X": f"{X:.0%}",
                    "n": int(len(sub)), "mean_fwd": float(sub[RETURN_COL].mean()),
                    "med_fwd": float(sub[RETURN_COL].median()),
                    "good_rate": good, "baseline_pool": all_mean,
                })

    # Cas contraires (inversions) : TOP10+baisse / BOTTOM10+hausse
    inv_rows: list[dict[str, Any]] = []
    for N in N_LIST:
        pc10 = f"persistent_rank_top10_{N}"
        pcb = f"persistent_rank_bottom10_{N}"
        for X in X_LIST:
            a = panel[(panel[pc10] == 1) & (panel[f"ret_{N}"] <= -X)]   # TOP10 + baisse
            b = panel[(panel[pcb] == 1) & (panel[f"ret_{N}"] >= X)]     # BOTTOM10 + hausse
            for name, sub in (("inv_top10_baisse", a), ("inv_bottom10_hausse", b)):
                if len(sub) == 0:
                    continue
                inv_rows.append({
                    "signal": name, "N": N, "X": f"{X:.0%}",
                    "n": int(len(sub)), "mean_fwd": float(sub[RETURN_COL].mean()),
                    "med_fwd": float(sub[RETURN_COL].median()),
                    "good_rate": float((sub[RETURN_COL] > 0).mean()),
                    "baseline_pool": all_mean,
                })
    return pd.DataFrame(rows + inv_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent_tail_price_confirmation.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--out", default="artifacts/persistent_tail_price.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    panel = load_panel(engine, batch_id, args.start_date, args.end_date)
    LOGGER.info("panel : %d lignes, %d dates, %d symboles",
                len(panel), panel["date"].nunique(), panel["symbol"].nunique())
    panel = compute_persistence(panel)
    result = evaluate(panel)
    result.to_csv(args.out, index=False)
    print(f"→ CSV : {args.out} ({len(result)} lignes)")

    # Rapport lisible : focus sur good_rate (rate de « vrais bons ») vs base
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    for name in result["signal"].unique():
        sub = result[result["signal"] == name]
        print(f"\n=== {name} (base pool mean fwd = {result['baseline_pool'].iloc[0]:.3f}) ===")
        sys.stdout.buffer.write(sub[["N", "X", "n", "mean_fwd", "med_fwd", "good_rate"]]
                                .to_string(index=False).encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
