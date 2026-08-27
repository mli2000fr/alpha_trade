"""modelFactory/global_direction/audit_scores.py — Audit de couverture stock_scores_history.

Avant de re-tester le temporal sur les features de score, on audite la fréquence
RÉELLE des snapshots (2020-2026) :

- nombre de snapshots par symbole / par année ;
- % des jours de trading couverts (snapshot le jour même ET PIT : snapshot ≤ jour) ;
- gap médian/max entre snapshots consécutifs (en jours de TRADING) ;
- **couverture réelle des lags J-1 / J-3 / J-5 / J-10** : pour chaque date J, un
  snapshot PIT existe-t-il au jour de marché J−k ? (jours de marché réels du
  symbole, pas ``shift`` sur snapshots irréguliers) ;
- mêmes statistiques dans le **pool Oracle TOP20%**.

Features prioritaires (ordre) :
``relative_strength_index_neutralized, sentiment_net_agg, company_idio_signal_norm,
company_idio_score, sector_impact_agg, short_score, trend_score, weekly_trend_score``.

Usage :
    python -m modelFactory.global_direction.audit_scores --batch-id ... [--pool-pct 0.20]
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
from modelFactory.directional_data_research.harness import assemble_pool
from modelFactory.global_direction.config import resolve_global_direction_batch_id

LOGGER = logging.getLogger(__name__)

SCORE_FEATURES = [
    "relative_strength_index_neutralized",
    "sentiment_net_agg",
    "company_idio_signal_norm",
    "company_idio_score",
    "sector_impact_agg",
    "short_score",
    "trend_score",
    "weekly_trend_score",
]
LAG_DAYS = [1, 3, 5, 10]


def load_scores(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Snapshots bruts stock_scores_history (8 features prioritaires)."""
    cols = ", ".join(SCORE_FEATURES)
    placeholders = ",".join(["%s"] * len(symbols))
    q = f"""
        SELECT symbol, snapshot_date, {cols}
        FROM stock_scores_history
        WHERE symbol IN ({placeholders}) AND snapshot_date >= %s AND snapshot_date <= %s
    """
    df = pd.read_sql(q, engine, params=(*symbols, start_date, end_date))
    if df.empty:
        return df
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.dropna(subset=["snapshot_date", "symbol"])


def load_bars_dates(engine: Any, symbols: list[str], start_date: str, end_date: str) -> dict[str, np.ndarray]:
    """Calendrier de trading RÉEL par symbole (dates stock_bars_daily)."""
    placeholders = ",".join(["%s"] * len(symbols))
    q = f"""
        SELECT DISTINCT symbol, date FROM stock_bars_daily
        WHERE symbol IN ({placeholders}) AND date >= %s AND date <= %s
    """
    df = pd.read_sql(q, engine, params=(*symbols, start_date, end_date))
    if df.empty:
        return {}
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return {sym: np.array(sorted(g["date"].values), dtype="datetime64[ns]")
            for sym, g in df.groupby("symbol")}


def _pit_series(snap_dates: np.ndarray, snap_values: np.ndarray, trading_days: np.ndarray) -> pd.Series:
    """Valeur PIT (dernier snapshot ≤ jour) sur chaque jour de trading."""
    idx = np.searchsorted(snap_dates, trading_days, side="right") - 1
    valid = idx >= 0
    vals = np.full(len(trading_days), np.nan)
    vals[valid] = snap_values[idx[valid]]
    return pd.Series(vals, index=pd.Index(trading_days, name="date"))


def audit_universe(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Stats par symbole × année sur TOUT l'univers des symboles fournis."""
    scores = load_scores(engine, symbols, start_date, end_date)
    calendars = load_bars_dates(engine, symbols, start_date, end_date)
    if scores.empty or not calendars:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for sym in symbols:
        cal = calendars.get(sym)
        if cal is None or len(cal) == 0:
            continue
        ss = scores[scores["symbol"] == sym].sort_values("snapshot_date")
        snap_dates = ss["snapshot_date"].to_numpy()
        # jours de trading par année
        cal_idx = pd.DatetimeIndex(cal)
        for year in sorted({d.year for d in cal_idx}):
            m = (cal_idx.year == year)
            year_days = cal_idx[m]
            n_tdays = int(m.sum())
            # snapshots cette année-là
            snap_year = ss[(ss["snapshot_date"].dt.year == year)]
            n_snap = int(len(snap_year))
            # % jours de trading avec snapshot le jour même
            snap_on_day = int(cal_idx[m].isin(pd.DatetimeIndex(snap_dates)).sum())
            # gap entre snapshots consécutifs (en jours de trading), borné à cette année
            gaps: list[int] = []
            for a, b in zip(snap_dates[:-1], snap_dates[1:]):
                ia = np.searchsorted(cal, a)
                ib = np.searchsorted(cal, b)
                if ia < len(cal) and ib < len(cal) and ia < ib:
                    g = ib - ia
                    if g > 0:
                        gaps.append(g)
            gaps = [g for g in gaps]  # inclut les gaps inter-années, OK pour médiane
            rows.append({
                "symbol": sym, "year": str(year),
                "n_trading_days": n_tdays,
                "n_snapshots": n_snap,
                "snap_on_day_pct": round(100.0 * snap_on_day / n_tdays, 1) if n_tdays else None,
                "gap_median_td": float(np.median(gaps)) if gaps else None,
                "gap_max_td": float(np.max(gaps)) if gaps else None,
            })
    return pd.DataFrame(rows)


def audit_pool_lags(
    pool: pd.DataFrame,
    scores: pd.DataFrame,
    calendars: dict[str, np.ndarray],
) -> pd.DataFrame:
    """Couverture réelle des lags J-k dans le pool Oracle TOP20%.

    Pour chaque (date J, symbol) du pool, on localise le jour de trading réel
    J−k (calendrier du symbole) et on vérifie qu'un snapshot PIT y existe, pour
    chacune des 8 features prioritaires. On mesure aussi l'ÂGE du snapshot à J
    (distance forward-fill, en jours de trading) et on détaille par année.
    """
    feat_cols = [c for c in SCORE_FEATURES if c in scores.columns]
    out: dict[str, Any] = {"pool_rows": len(pool)}
    # valeurs PIT par symbole pour chaque feature
    pit_cache: dict[str, pd.DataFrame] = {}
    for sym, cal in calendars.items():
        ss = scores[scores["symbol"] == sym].sort_values("snapshot_date")
        if ss.empty:
            continue
        d = pd.DataFrame({"date": cal})
        for c in feat_cols:
            d[c] = _pit_series(ss["snapshot_date"].to_numpy(),
                               ss[c].to_numpy(dtype=float), cal).to_numpy()
        # âge (jours de trading) entre J et le snapshot PIT
        idx = np.searchsorted(ss["snapshot_date"].to_numpy(), cal, side="right") - 1
        snap_pos = np.searchsorted(cal, ss["snapshot_date"].to_numpy(), side="left")
        age = np.full(len(cal), np.nan)
        valid = idx >= 0
        age[valid] = np.arange(len(cal))[valid] - snap_pos[idx[valid]]
        d["__age_td"] = age
        pit_cache[sym] = d

    ages: list[float] = []
    lag_hits: dict[int, int] = {k: 0 for k in [0, *LAG_DAYS]}
    lag_tot: dict[int, int] = {k: 0 for k in [0, *LAG_DAYS]}
    by_year: dict[str, dict[int, list[bool]]] = {}

    for sym, g in pool.groupby("symbol"):
        cal = calendars.get(sym)
        d = pit_cache.get(sym)
        if cal is None or d is None:
            continue
        jd = g["date"].to_numpy(dtype="datetime64[ns]")
        years = g["date"].dt.year.astype(str).to_numpy()
        idx = np.searchsorted(cal, jd, side="right") - 1
        valid_all = idx >= 0
        for k in [0, *LAG_DAYS]:
            li = idx - k
            valid = valid_all & (li >= 0)
            lag_tot[k] += int(valid.sum())
            if valid.any():
                lag_dates = cal[li[valid]]
                lag_vals = d.set_index("date").reindex(pd.DatetimeIndex(lag_dates))[feat_cols[0]]
                hits = lag_vals.notna().to_numpy()
                lag_hits[k] += int(hits.sum())
                for y, h in zip(years[valid], hits):
                    by_year.setdefault(str(y), {k2: [] for k2 in [0, *LAG_DAYS]})
                    by_year[str(y)][k].append(bool(h))
        if valid_all.any():
            a = d.set_index("date").reindex(pd.DatetimeIndex(cal[idx[valid_all]]))["__age_td"]
            ages.extend(a.dropna().to_list())

    for k in [0, *LAG_DAYS]:
        out[f"lag_{k}_cover_pct"] = round(100.0 * lag_hits[k] / lag_tot[k], 2) if lag_tot[k] else None
    out["age_J_median_td"] = float(np.median(ages)) if ages else None
    out["age_J_p90_td"] = float(np.quantile(ages, 0.9)) if ages else None
    out["age_J_max_td"] = float(np.max(ages)) if ages else None

    # par année
    yrows: list[dict[str, Any]] = []
    for y in sorted(by_year):
        r: dict[str, Any] = {"year": y}
        for k in [0, *LAG_DAYS]:
            hits = by_year[y][k]
            r[f"lag_{k}_cover_pct"] = round(100.0 * sum(hits) / len(hits), 2) if hits else None
        yrows.append(r)
    out["_by_year"] = yrows
    return pd.DataFrame([out])


def format_pool_report(lag_row: dict[str, Any]) -> str:
    lines = ["=== COUVERTURE LAGS J-k DANS LE POOL ORACLE TOP20% (jours de marché réels) ==="]
    for k in [0, *LAG_DAYS]:
        v = lag_row.get(f"lag_{k}_cover_pct")
        lines.append(f"  J{'−' + str(k) if k else ''}: {v}%")
    lines.append(f"  Âge du snapshot PIT à J : médiane {lag_row.get('age_J_median_td')} j.t. "
                 f"| p90 {lag_row.get('age_J_p90_td')} j.t. | max {lag_row.get('age_J_max_td')} j.t.")
    lines.append("  — Par année —")
    lines.append("  year  lag_0  lag_1  lag_3  lag_5  lag_10")
    for r in lag_row.get("_by_year", []):
        vals = "  ".join(f"{r.get(f'lag_{k}_cover_pct') or '-'}" for k in [0, *LAG_DAYS])
        lines.append(f"  {r['year']}  {vals}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit couverture stock_scores_history.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--out", default="artifacts/audit_scores_coverage.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    pool = assemble_pool(engine, batch_id, start_date="2022-01-01", end_date="2026-05-29",
                         pool_pct=args.pool_pct)
    pool_syms = sorted(pool["symbol"].unique())
    LOGGER.info("pool Oracle top%.0f%% : %d lignes, %d symboles", args.pool_pct * 100,
                len(pool), len(pool_syms))

    # Univers complet (tous symboles avec scores, 2020-2026)
    all_scores = load_scores(engine, pool_syms, args.start_date, args.end_date)
    all_syms = sorted(all_scores["symbol"].unique())
    LOGGER.info("symboles avec snapshots (2020-2026) : %d / %d du pool",
                len(all_syms), len(pool_syms))
    uni = audit_universe(engine, all_syms, args.start_date, args.end_date)
    if uni.empty:
        raise SystemExit("Aucun snapshot.")
    # agrégé par année
    agg = uni.groupby("year").agg(
        n_symbols=("symbol", "nunique"),
        snapshots_med=("n_snapshots", "median"),
        snapshots_min=("n_snapshots", "min"),
        snapshots_max=("n_snapshots", "max"),
        snap_on_day_med=("snap_on_day_pct", "median"),
        gap_median=("gap_median_td", "median"),
        gap_max_med=("gap_max_td", "median"),
        gap_max_global=("gap_max_td", "max"),
    ).reset_index()

    # Pool : couverture des lags sur jours de marché réels
    calendars = load_bars_dates(engine, pool_syms, args.start_date, args.end_date)
    lags = audit_pool_lags(pool, all_scores, calendars)

    uni.to_csv(args.out, index=False)
    print(f"→ CSV : {args.out} ({len(uni)} lignes symbole×année)")

    print("\n=== AGRÉGAT PAR ANNÉE (univers pool, 2020-2026) ===")
    print(agg.to_string(index=False))
    print()
    print(format_pool_report(lags.to_dict("records")[0] if not lags.empty else {}))
    print("\nMédiane des gaps en JOURS DE TRADING entre snapshots ; snap_on_day = % jours de"
          " trading avec un snapshot le jour même (pas de forward-fill).")


if __name__ == "__main__":
    main()
