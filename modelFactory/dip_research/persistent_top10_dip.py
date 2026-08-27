"""modelFactory/dip_research/persistent_top10_dip.py — persistent_top10_dip_validation.

Robustesse du signal « GlobalRank TOP10 persistant + baisse récente » (DIP).

Configurations pré-enregistrées (aucun nouveau sweep) :
    N ∈ {3, 4, 5} ; X ∈ {2%, 3%}

Conditions (signal connu à la clôture de J) :
    global_rank_20 >= 0.90 pendant N séances consécutives  (persistant)
    ret_N <= -X                                             (DIP)
    ret_N >= +X                                             (MOMENTUM)
    puis LONG à J+1.

Comparatifs :
    BASE     = TOP10 global_rank (sans condition)
    MOMENTUM = TOP10 persistant + ret_N >= +X
    DIP      = TOP10 persistant + ret_N <= -X

Mesures (fenêtre 20 séances après entrée J+1, via bars high/low/close) :
    D1..D10, BAD5, GOOD5, mean/median H20, P(ret>0), MFE, MAE,
    time-to-recovery, n signals, signals/month — par année, semestre, régime.

Usage :
    python -m modelFactory.dip_research.persistent_top10_dip --batch-id ...
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
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import DECILE_COL
from modelFactory.oracle.dataset import load_oracle_targets

LOGGER = logging.getLogger(__name__)

N_LIST = [3, 4, 5]
X_LIST = [0.02, 0.03]
RANK_COL = "global_rank_20"
TOP10 = 0.90
HOLD = 20  # séances après entrée

_FOLD_CUTS = [pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01"),
              pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"),
              pd.Timestamp("2026-01-01"), pd.Timestamp("2027-01-01")]


def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Panel : labels Oracle (décile), rank_20, bars OHLC (lookback + forward)."""
    targets = load_oracle_targets(engine, batch_id, horizon=20)
    lab = targets[["prediction_date", "symbol", DECILE_COL]].rename(columns={"prediction_date": "date"})
    lab["date"] = pd.to_datetime(lab["date"], errors="coerce").dt.normalize()
    lab["symbol"] = lab["symbol"].astype(str).str.upper()

    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history WHERE date BETWEEN %s AND %s",
        engine, params=(start_date, end_date),
    )
    rank["date"] = pd.to_datetime(rank["date"], errors="coerce").dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=20)).date().isoformat()
    fwd = (pd.Timestamp(end_date) + pd.Timedelta(days=45)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, open, high, low, close, adj_close FROM stock_bars_daily "
        "WHERE date BETWEEN %s AND %s",
        engine, params=(lb, fwd),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "close"])

    df = lab.merge(rank, on=["date", "symbol"], how="inner")
    df = df.merge(bars[["symbol", "date", "high", "low", "close", "adj_close"]],
                  on=["date", "symbol"], how="left")
    df = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df


def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    """Indexe les bars par symbole pour le slicing des fenêtres post-entrée."""
    out: dict[str, dict[str, np.ndarray]] = {}
    for sym, g in bars.sort_values("date").groupby("symbol"):
        out[sym] = {
            "date": g["date"].to_numpy(dtype="datetime64[ns]"),
            "high": g["high"].to_numpy(dtype=float),
            "low": g["low"].to_numpy(dtype=float),
            "close": g["close"].to_numpy(dtype=float),
        }
    return out


def forward_path_metrics(
    sym: str, j: pd.Timestamp, paths: dict[str, dict[str, np.ndarray]],
) -> dict[str, float | None]:
    """MFE / MAE / H20 / time-to-recovery pour un signal à J, entrée J+1 close, hold 20."""
    p = paths.get(sym)
    if p is None:
        return {"h20": None, "mfe": None, "mae": None, "ttr": None}
    dates = p["date"]
    idx = int(np.searchsorted(dates, np.datetime64(j), side="right"))  # premier > J = J+1
    entry_i = idx  # entrée à la clôture de J+1
    if entry_i >= len(dates) or entry_i + HOLD >= len(dates):
        return {"h20": None, "mfe": None, "mae": None, "ttr": None}
    entry = p["close"][entry_i]
    if not np.isfinite(entry) or entry <= 0:
        return {"h20": None, "mfe": None, "mae": None, "ttr": None}
    # fenêtre de détention : J+2..J+21 (20 séances après entrée)
    win_lo = entry_i + 1
    win_hi = entry_i + HOLD + 1  # exclusive -> J+1+HOLD
    closes = p["close"][win_lo:win_hi]
    highs = p["high"][win_lo:win_hi]
    lows = p["low"][win_lo:win_hi]
    if len(closes) < 1:
        return {"h20": None, "mfe": None, "mae": None, "ttr": None}
    h20 = closes[-1] / entry - 1.0
    mfe = float(np.nanmax(highs / entry - 1.0)) if np.isfinite(highs).any() else None
    mae = float(np.nanmin(lows / entry - 1.0)) if np.isfinite(lows).any() else None
    cum = closes / entry - 1.0
    rec = np.flatnonzero(cum >= 0.0)
    ttr = float(rec[0] + 1) if len(rec) else None  # nb de séances jusqu'au retour ≥ 0
    return {"h20": h20, "mfe": mfe, "mae": mae, "ttr": ttr}


def build_signal_rows(
    panel: pd.DataFrame,
    paths: dict[str, dict[str, np.ndarray]],
) -> list[pd.DataFrame]:
    """Calcule les signaux (BASE/MOMENTUM/DIP) avec métriques forward."""
    out = panel.copy()
    out["top10"] = (out[RANK_COL] >= TOP10).astype(int)
    g_close = out.groupby("symbol")["adj_close"]
    g_top = out.groupby("symbol")["top10"]
    for N in N_LIST:
        out[f"ret_{N}"] = out["adj_close"] / g_close.shift(N) - 1.0
        out[f"persist_{N}"] = g_top.transform(lambda x: x.rolling(N, min_periods=N).min())

    rows: list[dict[str, Any]] = []
    year = pd.to_datetime(out["date"]).dt.year
    semester = np.where(pd.to_datetime(out["date"]).dt.month <= 6, "S1", "S2")
    out["_year"] = year.astype(str)
    out["_sem"] = semester
    out["_fold"] = pd.cut(pd.to_datetime(out["date"]), bins=_FOLD_CUTS,
                          labels=["2022", "2023", "2024", "2025", "2026"]).astype(str)
    # régime (regime.ttx) — parse simple
    regime_map: dict[pd.Timestamp, str] = {}
    rfile = Path("regime_marche/regime.ttx")
    if rfile.exists():
        with open(rfile, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i == 0 or not line.strip():
                    continue
                parts = line.strip().split(",", 3)
                if len(parts) < 3:
                    continue
                try:
                    s = pd.Timestamp(parts[0].strip()).normalize()
                    e = pd.Timestamp(parts[1].strip()).normalize()
                    rg = str(parts[2]).strip().lower()
                    cur = s
                    while cur <= e:
                        regime_map[cur] = rg
                        cur += pd.Timedelta(days=1)
                except Exception:
                    continue
    out["_regime"] = out["date"].map(regime_map).fillna("unknown")

    for _, r in out[out["top10"] == 1].iterrows():
        base_meta = _meta(r)
        rows.append({"strategy": "BASE", "N": 0, "X": 0.0, **base_meta})
        sym = r["symbol"]
        j = r["date"]
        for N in N_LIST:
            if r[f"persist_{N}"] != 1:
                continue
            rn = r[f"ret_{N}"]
            for X in X_LIST:
                if rn is None or not np.isfinite(rn):
                    continue
                if rn <= -X:
                    rows.append({"strategy": "DIP", "N": N, "X": X, **base_meta})
                elif rn >= X:
                    rows.append({"strategy": "MOMENTUM", "N": N, "X": X, **base_meta})
    return rows


def _meta(r: pd.Series) -> dict[str, Any]:
    m = {
        "symbol": r["symbol"], "date": r["date"],
        "decile": int(r[DECILE_COL]) if pd.notna(r[DECILE_COL]) else None,
        "year": r["_year"], "sem": r["_sem"], "fold": r["_fold"], "regime": r["_regime"],
        "ret_N": float(r["ret_3"]) if pd.notna(r.get("ret_3")) else None,
    }
    return m


def aggregate(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:
    """Calcule les métriques forward (MFE/MAE/H20/recovery) + agrège par config."""
    # enrichir avec path metrics
    fpm = signals.apply(lambda r: forward_path_metrics(r["symbol"], r["date"], paths), axis=1, result_type="expand")
    signals = pd.concat([signals.reset_index(drop=True), fpm.reset_index(drop=True)], axis=1)

    out_rows: list[dict[str, Any]] = []
    for (strat, N, X), g in signals.groupby(["strategy", "N", "X"]):
        n = int(len(g))
        h20 = g["h20"].dropna()
        dec = g["decile"].dropna().astype(int)
        mfe = g["mfe"].dropna()
        mae = g["mae"].dropna()
        ttr = g["ttr"].dropna()
        sub = g.dropna(subset=["h20", "decile"]).copy()
        sub["_dec"] = sub["decile"].astype(int)
        bad5 = sub.loc[sub["_dec"] <= 5, "h20"].mean() if len(sub) else np.nan
        good5 = sub.loc[sub["_dec"] >= 6, "h20"].mean() if len(sub) else np.nan
        gains = h20[h20 > 0]
        losses = h20[h20 < 0]
        pf = float(gains.sum() / abs(losses.sum())) if len(gains) and len(losses) and losses.sum() != 0 else None
        dec_hist = {f"D{d}": int((dec == d).sum()) for d in range(1, 11)}
        months = max(1.0, len(pd.to_datetime(g["date"]).dt.to_period("M").unique()))
        out_rows.append({
            "strategy": strat, "N": N, "X": X,
            "n": n, "signals_month": round(n / months, 1),
            "mean_h20": float(h20.mean()) if len(h20) else None,
            "median_h20": float(h20.median()) if len(h20) else None,
            "p_positive": float((h20 > 0).mean()) if len(h20) else None,
            "pf": pf,
            "bad5": float(bad5) if np.isfinite(bad5) else None,
            "good5": float(good5) if np.isfinite(good5) else None,
            "good5_bad5": float(good5 - bad5) if np.isfinite(bad5) and np.isfinite(good5) else None,
            "mfe_mean": float(mfe.mean()) if len(mfe) else None,
            "mae_mean": float(mae.mean()) if len(mae) else None,
            "ttr_mean": float(ttr.mean()) if len(ttr) else None,
            **dec_hist,
        })
    return pd.DataFrame(out_rows)


def breakdown(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:
    """Par année / semestre / régime : mean_h20 + P>0 par stratégie."""
    fpm = signals.apply(lambda r: forward_path_metrics(r["symbol"], r["date"], paths), axis=1, result_type="expand")
    signals = pd.concat([signals.reset_index(drop=True), fpm.reset_index(drop=True)], axis=1)
    rows: list[dict[str, Any]] = []
    for by_col in ["year", "sem", "regime"]:
        for (strat, key), g in signals.groupby(["strategy", by_col]):
            h = g["h20"].dropna()
            rows.append({
                "by": by_col, "key": key, "strategy": strat, "n": int(len(g)),
                "mean_h20": float(h.mean()) if len(h) else None,
                "p_positive": float((h > 0).mean()) if len(h) else None,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent_top10_dip validation.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--out", default="artifacts/persistent_top10_dip.csv")
    parser.add_argument("--out-bd", default="artifacts/persistent_top10_dip_breakdown.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    panel = load_panel(engine, batch_id, args.start_date, args.end_date)
    LOGGER.info("panel : %d lignes, %d symboles", len(panel), panel["symbol"].nunique())

    lb = (pd.Timestamp(args.start_date) - pd.Timedelta(days=20)).date().isoformat()
    fwd = (pd.Timestamp(args.end_date) + pd.Timedelta(days=45)).date().isoformat()
    bars_all = pd.read_sql(
        "SELECT symbol, date, high, low, close FROM stock_bars_daily WHERE date BETWEEN %s AND %s",
        engine, params=(lb, fwd),
    )
    bars_all["date"] = pd.to_datetime(bars_all["date"], errors="coerce").dt.normalize()
    bars_all["symbol"] = bars_all["symbol"].astype(str).str.upper()
    paths = _per_symbol_paths(bars_all.dropna(subset=["date", "symbol", "close"]))

    sig = build_signal_rows(panel, paths)
    signals = pd.DataFrame(sig)
    LOGGER.info("signaux bruts : %d (BASE=%d, DIP=%d, MOMENTUM=%d)",
                len(signals),
                int((signals["strategy"] == "BASE").sum()),
                int((signals["strategy"] == "DIP").sum()),
                int((signals["strategy"] == "MOMENTUM").sum()))

    agg = aggregate(signals, paths)
    agg.to_csv(args.out, index=False)
    bd = breakdown(signals, paths)
    bd.to_csv(args.out_bd, index=False)
    print(f"→ CSV : {args.out} ({len(agg)} lignes) ; breakdown : {args.out_bd}")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    print("\n=== AGRÉGÉ (H20, entrée J+1) ===")
    cols = ["strategy", "N", "X", "n", "signals_month", "mean_h20", "median_h20",
            "p_positive", "pf", "bad5", "good5", "good5_bad5", "mfe_mean", "mae_mean", "ttr_mean"]
    sys.stdout.buffer.write(agg[cols].to_string(index=False).encode("utf-8", errors="replace"))
    print("\n=== BREAKDOWN (mean_h20 par année/sem/régime) ===")
    sys.stdout.buffer.write(bd.to_string(index=False).encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
