"""modelFactory/directional_data_research/analyst_revisions.py — Famille analyst.

Priorité de features (demande) :
1. EPS estimate revision 7d/30d/90d   → **INDISPONIBLE** (pas de série d'estimates ;
   `eps_estimate_current/next` = 0 lignes non-null dans stock_fundamentals_daily)
2. revenue estimate revision          → **INDISPONIBLE**
3. nb révisions hauss./baiss.         → **INDISPONIBLE** (aucune table analyst/rating)
4. dispersion des estimates           → **INDISPONIBLE**
5. changement du consensus            → **INDISPONIBLE**
6. changement du target price         → **INDISPONIBLE**
7. analyst upgrades/downgrades        → **INDISPONIBLE**
8. **earnings surprise précédente**   → ✅ `stock_earnings_calendar`
   (`eps_estimate`/`eps_actual`, `revenue_estimate`/`revenue_actual`)
9. **jours jusqu'aux earnings**       → ✅ `stock_earnings_calendar` (`earnings_date`)

Features construites (PIT strict, pool Oracle TOP20%) :
- ``earn_surprise_eps_prev`` : (eps_actual − eps_estimate)/|eps_estimate| du dernier
  earnings RAPPORTÉ (earnings_date ≤ J), fenêtre 130 j — PIT.
- ``earn_surprise_rev_prev`` : idem sur le revenu.
- ``earn_surprise_abs_eps`` : |surprise eps| (magnitude).
- ``days_to_earnings`` : prochain earnings planifié ≥ J (calendrier) − J.
- ``earn_count_90d`` : nb d'earnings rapportés sur les 90 derniers jours.

Discipline : harnais de séparabilité AVANT tout modèle (IC décile, AUC
D1-D5 vs D6-D10, AUC D1-D3 vs D8-D10, dir_vs_amp, stabilité par fold).

Usage :
    python -m modelFactory.directional_data_research.analyst_revisions
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
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.config import resolve_global_direction_batch_id

LOGGER = logging.getLogger(__name__)

FEATURES = [
    "earn_surprise_eps_prev",
    "earn_surprise_rev_prev",
    "earn_surprise_abs_eps",
    "days_to_earnings",
    "earn_count_90d",
]

# Familles demandées et indisponibles (loggées, non inventées).
UNAVAILABLE = [
    "eps_estimate_revision_7d/30d/90d",
    "revenue_estimate_revision",
    "nb_revisions_haussieres_baissieres",
    "dispersion_des_estimates",
    "changement_du_consensus",
    "changement_du_target_price",
    "analyst_upgrades_downgrades",
]


def load_earnings_calendar(engine: Any) -> pd.DataFrame:
    df = pd.read_sql(
        """SELECT symbol, earnings_date, eps_estimate, eps_actual,
                  revenue_estimate, revenue_actual
           FROM stock_earnings_calendar""",
        engine,
    )
    df["earnings_date"] = pd.to_datetime(df["earnings_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for c in ["eps_estimate", "eps_actual", "revenue_estimate", "revenue_actual"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["earnings_date", "symbol"])


def build_features(pool: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """Fusionne les features analyst au pool (date J, symbol), PIT strict."""
    out = pool[["date", "symbol"]].drop_duplicates(subset=["date", "symbol"]).reset_index(drop=True)
    syms = out["symbol"].to_numpy()
    dates = out["date"].to_numpy(dtype="datetime64[ns]")

    # Surprise par événement (connue à partir de earnings_date)
    ev = cal.copy()
    ev["eps_surprise"] = (ev["eps_actual"] - ev["eps_estimate"]) / ev["eps_estimate"].abs().replace(0, np.nan)
    ev["rev_surprise"] = (ev["revenue_actual"] - ev["revenue_estimate"]) / ev["revenue_estimate"].abs().replace(0, np.nan)
    ev_eps = ev[ev["eps_surprise"].notna()][["symbol", "earnings_date", "eps_surprise"]].sort_values("earnings_date")
    ev_rev = ev[ev["rev_surprise"].notna()][["symbol", "earnings_date", "rev_surprise"]].sort_values("earnings_date")
    cal_ed = cal[["symbol", "earnings_date"]].dropna().sort_values("earnings_date")

    def _asof_pit(events: pd.DataFrame, col: str, window_days: float) -> np.ndarray:
        """Dernière valeur d'événement <= J par symbole, fenêtre window_days, PIT."""
        arr = np.full(len(out), np.nan)
        for sym in np.unique(syms):
            pos = np.flatnonzero(syms == sym)
            jd = dates[pos]
            e = events[events["symbol"] == sym]
            if e.empty:
                continue
            m = pd.merge_asof(
                pd.DataFrame({"date": jd}), e, left_on="date", right_on="earnings_date",
                direction="backward",
            )
            age = (jd - m["earnings_date"].to_numpy(dtype="datetime64[ns]")).astype("timedelta64[D]").astype(float)
            v = m[col].to_numpy(dtype=float)
            v[age > window_days] = np.nan
            arr[pos] = v
        return arr

    out["earn_surprise_eps_prev"] = _asof_pit(ev_eps, "eps_surprise", 130.0)
    out["earn_surprise_rev_prev"] = _asof_pit(ev_rev, "rev_surprise", 130.0)
    out["earn_surprise_abs_eps"] = np.abs(_asof_pit(ev_eps, "eps_surprise", 130.0))

    # --- days_to_earnings (prochain earnings planifié >= J, calendrier) ---
    dte = np.full(len(out), np.nan)
    for sym in np.unique(syms):
        pos = np.flatnonzero(syms == sym)
        jd = dates[pos]
        e = cal_ed[cal_ed["symbol"] == sym]
        if e.empty:
            continue
        m = pd.merge_asof(
            pd.DataFrame({"date": jd}), e, left_on="date", right_on="earnings_date",
            direction="forward",
        )
        ed = m["earnings_date"].to_numpy(dtype="datetime64[ns]")
        with np.errstate(invalid="ignore"):
            dte[pos] = (ed - jd).astype("timedelta64[D]").astype(float)
    out["days_to_earnings"] = dte

    # --- earn_count_90d : nb d'earnings rapportés dans les 90 derniers jours ---
    cnt = np.zeros(len(out), dtype=float)
    for sym in np.unique(syms):
        pos = np.flatnonzero(syms == sym)
        jd = dates[pos]
        ed = ev_eps.loc[ev_eps["symbol"] == sym, "earnings_date"].to_numpy(dtype="datetime64[ns]")
        if len(ed) == 0:
            continue
        lo = jd[:, None] - np.timedelta64(90, "D")
        cnt[pos] = ((ed[None, :] <= jd[:, None]) & (ed[None, :] > lo)).sum(axis=1)
    out["earn_count_90d"] = cnt

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité famille analyst (pool Oracle TOP20%).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--oracle-run", default=None)
    parser.add_argument("--out", default="artifacts/directional_data_research_analyst.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    for f in UNAVAILABLE:
        LOGGER.info("Feature INDISPONIBLE (non inventée) : %s", f)

    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                         oracle_run=args.oracle_run)
    if pool.empty:
        raise SystemExit("Pool Oracle vide.")
    LOGGER.info("pool Oracle top20%% : %d lignes, %d symboles", len(pool), pool["symbol"].nunique())

    cal = load_earnings_calendar(engine)
    LOGGER.info("calendrier earnings : %d événements, %d symboles",
                len(cal), cal["symbol"].nunique())
    feat = build_features(pool, cal)
    merged = pool.merge(feat, on=["date", "symbol"], how="left")
    merged = merged.drop_duplicates(subset=["date", "symbol"])

    result = analyze_features(merged, FEATURES)
    result.to_csv(args.out, index=False)
    print(f"→ CSV : {args.out} ({len(result)} lignes)")
    print(format_report(result, top_n=12))


if __name__ == "__main__":
    main()
