"""modelFactory/directional_data_research/yahoo_analyst_features.py — Features analystes PIT (Yahoo).

Famille « analyst » réelle (comble le gap d'``analyst_revisions.py`` qui était
INDISPONIBLE faute de données) : upgrades/downgrades/initiations + variations de
target price issues de ``Ticker.upgrades_downgrades`` (Yahoo).

Discipline PIT STRICTE :
- une feature à la date J n'utilise que des événements publiés STRICTEMENT AVANT J
  (``published_at < J``) — aucune information du jour J, aucune donnée future.
- pool = Oracle TOP20% du jour par ``proba_extreme`` (OOS PIT, lu en base
  ``oracle_extreme_predictions`` + labels ``global_oracle_labels``).
- harnais de séparabilité AVANT tout modèle (IC décile, AUC D1-D5 vs D6-D10,
  AUC D1-D3 vs D8-D10, dir_vs_amp, stabilité par fold).

Features (comptes dans fenêtres glissantes (J−w, J), w ∈ {3,7,30,60}) :
- ``upgrades_3d..60d`` / ``downgrades_3d..60d`` / ``net_upgrades_3d..60d``
- ``rating_delta_sum_7d/30d/60d`` : Σ(ToGrade−FromGrade) numérisé (échelle 1-5)
- ``pt_delta_sum_7d/30d/60d`` : Σ(currentPriceTarget−priorPriceTarget)
- ``breadth_30d`` : nb de firmes distinctes actives sur 30 j
- ``days_since_last_rating`` : jours depuis le dernier événement < J
- ``rating_actions_60d`` : nb total d'événements sur 60 j

Usage :
    python -m modelFactory.directional_data_research.yahoo_analyst_features \
        [--batch-id ...] [--start-date ...] [--end-date ...] [--limit-symbols N] \
        [--no-download] [--out artifacts/directional_data_research_yahoo_analyst.csv]
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
    _FOLD_CUTS,
    analyze_features,
    format_report,
)
from modelFactory.directional_data_research.yahoo_sources import (
    download_many,
    load_all,
    normalize_ud,
)
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL
from modelFactory.oracle.dataset import load_oracle_targets
from modelFactory.oracle.predictions_store import load_oracle_predictions

LOGGER = logging.getLogger(__name__)

WINDOWS = (3, 7, 30, 60)

FEATURES = [
    "upgrades_3d", "upgrades_7d", "upgrades_30d", "upgrades_60d",
    "downgrades_3d", "downgrades_7d", "downgrades_30d", "downgrades_60d",
    "net_upgrades_3d", "net_upgrades_7d", "net_upgrades_30d", "net_upgrades_60d",
    "rating_delta_sum_7d", "rating_delta_sum_30d", "rating_delta_sum_60d",
    "pt_delta_sum_7d", "pt_delta_sum_30d", "pt_delta_sum_60d",
    "breadth_30d", "days_since_last_rating", "rating_actions_60d",
]


def assemble_pool_db(
    engine: Any,
    batch_id: str,
    *,
    start_date: str,
    end_date: str,
    horizon: int = 20,
    pool_pct: float = 0.20,
) -> pd.DataFrame:
    """Pool Oracle TOP20% (date, symbol, proba_extreme, oracle_decile,
    future_return, fold_start, year, regime) — source : DB (pas de parquet OOS).

    Reproduit le schéma de ``harness.assemble_pool`` mais lit les prédictions
    OOS dans ``oracle_extreme_predictions`` (la table production).
    """
    targets = load_oracle_targets(engine, batch_id, horizon)
    pred = load_oracle_predictions(engine, batch_id=batch_id)
    if targets.empty or pred.empty:
        return pd.DataFrame()
    df = targets[["prediction_date", "symbol", DECILE_COL, RETURN_COL]].merge(
        pred[["date", "symbol", "proba_extreme"]],
        left_on=["prediction_date", "symbol"], right_on=["date", "symbol"],
        how="inner",
    ).drop(columns=["prediction_date"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if df.empty:
        return pd.DataFrame()
    df = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]
    df["_eg_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[df["_eg_pct"] >= (1.0 - pool_pct)].drop(columns=["_eg_pct"])
    if df.empty:
        return df
    df["fold_start"] = pd.cut(pd.to_datetime(df["date"]), bins=_FOLD_CUTS,
                              labels=["2022", "2023", "2024", "2025", "2026"]).astype(str)
    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(str)
    # Régime (regime.ttx)
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
    df["regime"] = df["date"].map(regime_map).fillna("unknown")
    return df.reset_index(drop=True)


def _event_arrays(ev: pd.DataFrame) -> dict[str, np.ndarray]:
    """Tableaux numpy triés d'un symbole (dates normalisées au jour)."""
    e = ev.sort_values("published_at")
    return {
        "days": e["published_at"].to_numpy(dtype="datetime64[D]"),
        "up": (e["action"].to_numpy() == "up").astype(np.int64) if len(e) else np.array([], dtype=np.int64),
        "down": (e["action"].to_numpy() == "down").astype(np.int64) if len(e) else np.array([], dtype=np.int64),
        "delta": pd.to_numeric(e["rating_delta"], errors="coerce").fillna(0.0).to_numpy(dtype=float) if len(e) else np.array([], dtype=float),
        "pt": pd.to_numeric(e["pt_delta"], errors="coerce").fillna(0.0).to_numpy(dtype=float) if len(e) else np.array([], dtype=float),
        "firms": e["Firm"].to_numpy() if len(e) and "Firm" in e.columns else np.array([], dtype=object),
    }


def build_features(pool: pd.DataFrame, ud: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Features analystes PIT par (date J, symbol) — événements strictement < J."""
    out = pool[["date", "symbol"]].drop_duplicates(subset=["date", "symbol"]).reset_index(drop=True)
    syms = out["symbol"].to_numpy()
    dj = out["date"].to_numpy(dtype="datetime64[D]")
    n = len(out)

    for f in FEATURES:
        out[f] = np.nan
    out["has_yahoo_data"] = 0

    for sym in np.unique(syms):
        pos = np.flatnonzero(syms == sym)
        jd = dj[pos]
        ev = ud.get(sym)
        if ev is None or len(ev) == 0:
            continue  # pas de couverture Yahoo → NaN (inconnu)
        out.loc[out.index[pos], "has_yahoo_data"] = 1
        a = _event_arrays(ev)
        days = a["days"]

        # bornes : événements avec day ∈ (J−w, J) → day < J et day > J−w
        i_hi = np.searchsorted(days, jd, side="left")           # day < J
        i_lo30 = np.searchsorted(days, jd - np.timedelta64(30, "D"), side="left")
        cum_up = np.concatenate([[0], np.cumsum(a["up"])])
        cum_down = np.concatenate([[0], np.cumsum(a["down"])])
        cum_delta = np.concatenate([[0], np.cumsum(a["delta"])])
        cum_pt = np.concatenate([[0], np.cumsum(a["pt"])])

        for w in WINDOWS:
            i_lo = np.searchsorted(days, jd - np.timedelta64(w, "D"), side="left")
            up = cum_up[i_hi] - cum_up[i_lo]
            down = cum_down[i_hi] - cum_down[i_lo]
            out.loc[out.index[pos], f"upgrades_{w}d"] = up
            out.loc[out.index[pos], f"downgrades_{w}d"] = down
            out.loc[out.index[pos], f"net_upgrades_{w}d"] = up - down

        for w in (7, 30, 60):
            i_lo = np.searchsorted(days, jd - np.timedelta64(w, "D"), side="left")
            out.loc[out.index[pos], f"rating_delta_sum_{w}d"] = cum_delta[i_hi] - cum_delta[i_lo]
            out.loc[out.index[pos], f"pt_delta_sum_{w}d"] = cum_pt[i_hi] - cum_pt[i_lo]

        # breadth_30d : firmes distinctes dans (J−30, J)
        br = np.full(len(jd), np.nan)
        firms = a["firms"]
        for k in range(len(jd)):
            b = i_hi[k]
            a_lo = i_lo30[k]
            if b > a_lo:
                br[k] = np.unique(firms[a_lo:b]).size
        out.loc[out.index[pos], "breadth_30d"] = br

        # days_since_last_rating : dernier événement < J
        i_last = i_hi - 1
        valid = i_last >= 0
        age = np.full(len(jd), np.nan)
        if valid.any():
            age[valid] = (jd[valid] - days[i_last[valid]]).astype("timedelta64[D]").astype(float)
        out.loc[out.index[pos], "days_since_last_rating"] = age

        # rating_actions_60d : nb total d'événements dans (J−60, J)
        i_lo60 = np.searchsorted(days, jd - np.timedelta64(60, "D"), side="left")
        out.loc[out.index[pos], "rating_actions_60d"] = i_hi - i_lo60

    return out.drop(columns=["has_yahoo_data"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité famille analyst Yahoo (pool Oracle TOP20%).")
    parser.add_argument("--batch-id", default="model-factory-20260829001206-035b52")
    parser.add_argument("--start-date", default="2022-07-05")
    parser.add_argument("--end-date", default="2025-01-03")
    parser.add_argument("--limit-symbols", type=int, default=None)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out", default="artifacts/directional_data_research_yahoo_analyst.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    engine = get_sqlalchemy_engine()
    pool = assemble_pool_db(engine, args.batch_id,
                            start_date=args.start_date, end_date=args.end_date)
    if pool.empty:
        raise SystemExit("Pool Oracle vide — vérifier batch_id/fenêtre.")
    LOGGER.info("pool Oracle top20%% : %d lignes, %d symboles, %s → %s",
                len(pool), pool["symbol"].nunique(), pool["date"].min().date(), pool["date"].max().date())

    symbols = sorted(pool["symbol"].unique().tolist())
    if args.limit_symbols:
        symbols = symbols[: args.limit_symbols]
    LOGGER.info("symboles à traiter : %d", len(symbols))

    if args.no_download:
        ud = load_all(symbols)
    else:
        ud = download_many(symbols, force=args.force)
    n_cov = sum(1 for df in ud.values() if df is not None and len(df) > 0)
    LOGGER.info("couverture Yahoo : %d/%d symboles avec événements", n_cov, len(symbols))

    feat = build_features(pool, ud)
    merged = pool.merge(feat, on=["date", "symbol"], how="left")
    merged = merged.drop_duplicates(subset=["date", "symbol"])

    result = analyze_features(merged, FEATURES)
    result.to_csv(args.out, index=False)
    print(f"\n→ CSV : {args.out} ({len(result)} lignes)")
    print(format_report(result, top_n=len(FEATURES)))
    print("\nCohérence (moyenne de lignes non-vides par feature) :")
    print(result[["feature", "n_obs"]].to_string(index=False))


if __name__ == "__main__":
    main()
