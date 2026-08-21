"""Phase D7 per-sector — earnings comme information directionnelle (protocole REVISE).

Retour GPT (2026-08-16) — points methodologiques integres :
1. `earnings_date` = date de DEPOT SEC (10-Q/10-K/20-F), pas la date d'annonce.
   Interpretation honnete : « l'information financiere officiellement observable
   dans les filings SEC predit-elle le rendement futur ? » (pas la surprise d'annonce).
2. `eps_estimate` = meme trimestre de l'exercice precedent => la « surprise » est
   une CROISSANCE YoY. Variables nommees `eps_yoy` / `rev_yoy` (growth).
   « surprise » reste reserve au consensus analyste (non disponible).
3. Pas de look-ahead, deux experiences separees :
   E1 = entree au 1er jour de cotation apres le depot (features connues a D).
   E2 = on attend 1/3/5 jours de cotation, on calcule la reaction, PUIS on entre.
4. Blocs (une hypothese = une experience) :
   D7-A eps_yoy/rev_yoy (direction) · D7-B versions relatives secteur ·
   D7-C reaction 1/3/5j (+ rel secteur) [E1/E2] · D7-D matrice 2x2 signe(yoy) x
   signe(reaction) · D7-E x terciles idio_vol60 · D7-F incremental vs D1_pred.
5. Metriques : IC(direction), spread net, P(up|extreme)/P(down|extreme).
   Criteres GO : IC WF ET holdout > +0.03 + spread net > 0 + gain vs Global
   reproductible ; GO conditionnel si ~+0.02 tres stable + spread fort ;
   STOP si IC ~ 0, spread < 0, gain 2025 seulement, ou disparition apres
   conditionnement par Global/idio.

Usage : python scripts/per_sector_d7_earnings.py [--skip-d1f]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.per_sector_baselines import (  # noqa: E402
    ROUND_TRIP_BPS,
    SPREAD_COST,
    _fmt_table,
    _read_universe,
)
from scripts.per_sector_d4_dispersion import _build_panel  # noqa: E402
from scripts.per_sector_d1_global import (  # noqa: E402
    _build_cfg,
    _load_and_prepare,
)
from scripts.per_sector_d9a import _run_d1_folds  # noqa: E402

LOGGER = logging.getLogger("per_sector_d7")
LAGS = (1, 3, 5)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D7 per-sector : earnings -> direction (protocole revise)")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--buffer-days", type=int, default=360)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--min-ev-per-date", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    # D1 (Global) pour D7-F
    p.add_argument("--train-start", default="2016-01-01")
    p.add_argument("--folds", type=int, default=11)
    p.add_argument("--iterations", type=int, default=300)
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--skip-d1f", action="store_true", help="ne pas calculer D1 OOF (D7-F)")
    p.add_argument("--no-sector-cat", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def _load_events(engine, args: argparse.Namespace) -> pd.DataFrame:
    symbols = _read_universe(args.universe)
    in_clause = ",".join(f"'{s}'" for s in sorted(symbols))
    q = (f"SELECT symbol, earnings_date, eps_estimate, eps_actual, "
         f"revenue_estimate, revenue_actual, fiscal_period FROM stock_earnings_calendar "
         f"WHERE symbol IN ({in_clause}) "
         f"AND earnings_date >= '{args.start}' AND earnings_date <= '{args.end}'")
    with engine.connect() as conn:
        ev = pd.read_sql(q, conn)
    if ev.empty:
        return ev
    ev["earnings_date"] = pd.to_datetime(ev["earnings_date"])
    # croissance YoY (baseline = meme trimestre exercice precedent), PAS un consensus
    ev["eps_yoy"] = (ev["eps_actual"] - ev["eps_estimate"]) / ev["eps_estimate"].abs().clip(lower=1e-9)
    ev["rev_yoy"] = (ev["revenue_actual"] - ev["revenue_estimate"]) / ev["revenue_estimate"].abs().clip(lower=1e-9)
    return ev


def _sym_panels(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        sym: grp.sort_values("date").reset_index(drop=True)
        for sym, grp in panel.groupby("symbol", sort=False)
    }


def _event_rows(panel: pd.DataFrame, ev: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """E1 (entree lendemain du depot) et E2 (entree apres 1/3/5 j, reaction observee).

    La reaction de l'evenement (symbole D) est close[entree]/close[D] - 1 ;
    la reaction relative retire le cumul du rendement moyen du secteur sur la
    meme fenetre (moyenne des ret_1 quotidiens sectoriels), calculee PIT.
    """
    sym_panels = _sym_panels(panel)
    e1_rows: list[dict[str, object]] = []
    e2_rows: list[dict[str, object]] = []
    for (sym, d), sub in ev.groupby(["symbol", "earnings_date"]):
        sp = sym_panels.get(sym)
        if sp is None or len(sp) < 7:
            continue
        dts = pd.Timestamp(d)
        pre = sp[sp["date"] <= dts]
        after = sp.index[sp["date"] > dts]
        if pre.empty or len(after) < 5:
            continue
        c_d = float(pre.iloc[-1]["close"])  # dernier cours connu au moment du depot
        idx0 = int(after[0])
        last = sub.iloc[-1]
        base: dict[str, object] = {
            "symbol": sym,
            "eps_yoy": last.get("eps_yoy", np.nan),
            "rev_yoy": last.get("rev_yoy", np.nan),
            "filing_date": dts,
        }
        r0 = sp.loc[idx0]
        e1_rows.append({**base, "date": r0["date"], "entry_lag": 1, "E_r": np.nan, "E_r_rel": np.nan})
        for n in LAGS:
            i = idx0 + (n - 1)
            if i >= len(sp) - 1:
                continue
            ri = sp.loc[i]
            r_n = float(ri["close"] / c_d - 1.0)
            sec_cum = float(np.prod(1.0 + sp.loc[idx0:i, "sector_ret"].fillna(0.0)) - 1.0)
            e2_rows.append({**base, "date": ri["date"], "entry_lag": n,
                            "E_r": r_n, "E_r_rel": r_n - sec_cum})
    e1 = pd.DataFrame(e1_rows)
    e2 = pd.DataFrame(e2_rows)
    ctx = panel[["symbol", "date", "sector", "rel_h20", "rel_h20_w", "idio60"]].drop_duplicates(["symbol", "date"])
    merged = []
    for frame in (e1, e2):
        if frame.empty:
            merged.append(frame)
            continue
        frame["date"] = pd.to_datetime(frame["date"])
        frame["filing_date"] = pd.to_datetime(frame["filing_date"])
        merged.append(frame.merge(ctx, on=["symbol", "date"], how="left"))
    return merged[0], merged[1]


def _add_yoy_sector_rel(rows: pd.DataFrame, zone_bounds: tuple[pd.Timestamp, pd.Timestamp]) -> pd.DataFrame:
    """eps_yoy_sec / rev_yoy_sec = z-score du YoY au sein du secteur (pool zone)."""
    lo, hi = zone_bounds
    z = rows[(rows["date"] >= lo) & (rows["date"] <= hi)].copy()
    if z.empty:
        return z
    for col in ("eps_yoy", "rev_yoy"):
        grp = z.groupby("sector")[col]
        mu = grp.transform("mean")
        sd = grp.transform("std")
        z[f"{col}_sec"] = (z[col] - mu) / sd.clip(lower=1e-9)
    return z


def _ic_spread(rows: pd.DataFrame, score: str, min_ev: int) -> dict[str, object] | None:
    sub = rows.dropna(subset=[score, "rel_h20_w"]).copy()
    if len(sub) < 300:
        return None
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_ev]
    if len(sub) < 300:
        return None
    ics = sub.groupby("date").apply(
        lambda g: float(g[score].rank().corr(g["rel_h20_w"].rank())),
        include_groups=False).dropna()
    q = sub.groupby("date")[score].transform(
        lambda x: np.minimum((x.rank(method="first") - 1) * 5 // max(len(x), 1), 4))
    top = sub.loc[q == 4, "rel_h20_w"]
    bot = sub.loc[q == 0, "rel_h20_w"]
    spread = float(top.mean() - bot.mean())
    return {
        "n_rows": int(len(sub)),
        "n_dates": int(len(ics)),
        "ic_dir": round(float(ics.mean()), 3),
        "ic_pos_pct": round(float((ics > 0).mean() * 100), 1),
        "spread_net_bps": round(spread * 10_000 - SPREAD_COST, 1),
    }


def _dir_table(rows: pd.DataFrame, scores: list[str], min_ev: int) -> pd.DataFrame:
    out = []
    for sc in scores:
        r = _ic_spread(rows, sc, min_ev)
        out.append({"score": sc, **(r or {"n_rows": 0, "n_dates": 0, "ic_dir": np.nan,
                                         "ic_pos_pct": np.nan, "spread_net_bps": np.nan})})
    return pd.DataFrame(out)


def _cell(rows: pd.DataFrame) -> dict[str, object]:
    """Stats d'une cellule : mean rel, P(extreme up/down), P(up|extreme)."""
    sub = rows.dropna(subset=["rel_h20_w"]).copy()
    if len(sub) < 30:
        return {"n": 0}
    q = sub.groupby("date")["rel_h20_w"].transform(
        lambda x: np.minimum((x.rank(method="first") - 1) * 5 // max(len(x), 1), 4))
    ext_up = (q == 4) & (sub["rel_h20_w"] > 0)
    ext_dn = (q == 0) & (sub["rel_h20_w"] < 0)
    ext = (q == 4) | (q == 0)
    up = sub["rel_h20_w"] > 0
    return {
        "n": int(len(sub)),
        "mean_rel_bps": round(float(sub["rel_h20_w"].mean() * 10_000), 1),
        "P_ext_up_pct": round(float(ext_up.mean() * 100), 1),
        "P_ext_dn_pct": round(float(ext_dn.mean() * 100), 1),
        "P_up_given_ext_pct": round(float((up & ext).sum() / max(ext.sum(), 1) * 100), 1),
    }


def _matrix_2x2(rows: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    out = []
    for sx in ("+", "-"):
        for sy in ("+", "-"):
            sel = rows.copy()
            sel = sel[sel[x].notna() & sel[y].notna()]
            sel = sel[(sel[x] > 0) if sx == "+" else (sel[x] <= 0)]
            sel = sel[(sel[y] > 0) if sy == "+" else (sel[y] <= 0)]
            out.append({"cellule": f"{x}{sx} × {y}{sy}", **_cell(sel)})
    return pd.DataFrame(out)


def _idio_yoy_cells(rows: pd.DataFrame) -> pd.DataFrame:
    sub = rows.dropna(subset=["idio60", "eps_yoy", "rel_h20_w"]).copy()
    if len(sub) < 100:
        return pd.DataFrame([{"cellule": "pas assez de lignes", "n": len(sub)}])
    sub["_t"] = sub.groupby("date")["idio60"].transform(
        lambda x: np.minimum((x.rank(method="first") - 1) * 3 // max(len(x), 1), 2))
    out = []
    for t in (0.0, 1.0, 2.0):
        for sy in ("+", "-"):
            sel = sub[sub["_t"] == t]
            sel = sel[(sel["eps_yoy"] > 0) if sy == "+" else (sel["eps_yoy"] <= 0)]
            out.append({"cellule": f"idio_t{t+1:.0f} × yoy{sy}", **_cell(sel)})
    return pd.DataFrame(out)


def _ic_d1(rows: pd.DataFrame, min_ev: int) -> dict[str, object]:
    sub = rows.dropna(subset=["D1_pred", "rel_h20_w"]).copy()
    if len(sub) < 300:
        return {}
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_ev]
    if len(sub) < 300:
        return {}
    ics = sub.groupby("date").apply(
        lambda g: float(g["D1_pred"].rank().corr(g["rel_h20_w"].rank())),
        include_groups=False).dropna()
    q = sub.groupby("date")["D1_pred"].transform(
        lambda x: np.minimum((x.rank(method="first") - 1) * 5 // max(len(x), 1), 4))
    spread = float(sub.loc[q == 4, "rel_h20_w"].mean() - sub.loc[q == 0, "rel_h20_w"].mean())
    return {"n_rows": int(len(sub)), "n_dates": int(len(ics)),
            "ic_dir": round(float(ics.mean()), 3),
            "ic_pos_pct": round(float((ics > 0).mean() * 100), 1),
            "spread_net_bps": round(spread * 10_000 - SPREAD_COST, 1)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    ev = _load_events(engine, args)
    LOGGER.info("evenements charges : %d lignes", len(ev))
    if len(ev) < 100:
        out_path = Path("logs") / f"per_sector_d7_earnings_{args.start}_{args.end}.txt"
        msg = f"PHASE D7 — BLOQUE PAR LES DONNEES : {len(ev)} annonces disponibles."
        print(msg)
        out_path.write_text(msg + "\n", encoding="utf-8")
        return

    LOGGER.info("construction du panel ...")
    panel = _build_panel(engine, args)
    e1, e2 = _event_rows(panel, ev)
    LOGGER.info("lignes evenement : E1=%d E2=%d", len(e1), len(e2))

    if not args.skip_d1f:
        LOGGER.info("D7-F : preparation des features D1 (Global) + OOF ...")
        args.wf_start = args.start  # alias attendu par _run_d1_folds / _fold_windows
        pred_cache = Path("artifacts/per_sector_cache/d7_d1_preds.parquet")
        if pred_cache.exists():
            LOGGER.info("D1_pred charges depuis le cache %s", pred_cache)
            preds = pd.read_parquet(pred_cache)
        else:
            cfg = _build_cfg(args)
            df1, feat, _sm = _load_and_prepare(engine, cfg, args)
            preds = _run_d1_folds(df1, feat, args)
            pred_cache.parent.mkdir(parents=True, exist_ok=True)
            preds.to_parquet(pred_cache, index=False)
        pred_cols = preds[["symbol", "date", "D1_pred"]]
        panel = panel.merge(pred_cols, on=["symbol", "date"], how="left")
        e1 = e1.merge(pred_cols, on=["symbol", "date"], how="left")
        e2 = e2.merge(pred_cols, on=["symbol", "date"], how="left")
        LOGGER.info("D1_pred fusionne : %d lignes", panel["D1_pred"].notna().sum())

    wf_bounds = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start))
    ho_bounds = (pd.Timestamp(args.holdout_start), pd.Timestamp(args.end))

    out_lines = [
        "=" * 100,
        "PHASE D7 — EARNINGS comme INFORMATION DIRECTIONNELLE [protocole revise, H20]",
        f"{len(ev)} annonces SEC | earnings_date = date de DEPOT (10-Q/10-K/20-F) | "
        f"'surprise' = croissance YoY (pas de consensus) | cout {ROUND_TRIP_BPS:.0f} bps/jambe",
        "E1 = entree au 1er jour apres depot | E2 = attente 1/3/5 j puis entree (reaction observee)",
        "",
    ]

    for zone_name, bounds in (("WALK-FORWARD", wf_bounds), ("HOLDOUT GELE", ho_bounds)):
        z_e1 = _add_yoy_sector_rel(e1, bounds)
        z_e2 = _add_yoy_sector_rel(e2, bounds)
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name}")
        out_lines.append("-- D7-A : direction, YoY seul (E1) --")
        out_lines.append(_fmt_table(_dir_table(
            z_e1, ["eps_yoy", "rev_yoy"], args.min_ev_per_date)))
        out_lines.append("-- D7-B : YoY relatif secteur (E1) --")
        out_lines.append(_fmt_table(_dir_table(
            z_e1, ["eps_yoy_sec", "rev_yoy_sec"], args.min_ev_per_date)))
        out_lines.append("-- D7-C : reaction prix 1/3/5j (E2, entree apres reaction) --")
        r_rows = []
        for n in LAGS:
            sub = z_e2[z_e2["entry_lag"] == n]
            t = _dir_table(sub, ["E_r", "E_r_rel"], args.min_ev_per_date)
            t.insert(0, "lag", n)
            r_rows.append(t)
        out_lines.append(_fmt_table(pd.concat(r_rows, ignore_index=True)))
        out_lines.append("-- D7-D : matrice 2x2 signe(eps_yoy) x signe(reaction r1 rel) (E2 lag 1) --")
        m = z_e2[z_e2["entry_lag"] == 1]
        out_lines.append(_fmt_table(_matrix_2x2(m, "eps_yoy", "E_r_rel")))
        out_lines.append("-- D7-E : terciles idio_vol60 x signe(eps_yoy) (E2 lag 1) --")
        out_lines.append(_fmt_table(_idio_yoy_cells(m)))
        if "D1_pred" in panel.columns:
            out_lines.append("-- D7-F : incremental vs D1_pred (Global) --")
            z_panel = panel[(panel["date"] >= bounds[0]) & (panel["date"] <= bounds[1])]
            base = _ic_d1(z_panel, args.min_date_size)
            on_e1 = _ic_d1(z_e1, args.min_ev_per_date)
            pos = _ic_d1(z_e1[z_e1["eps_yoy"] > 0], args.min_ev_per_date)
            neg = _ic_d1(z_e1[z_e1["eps_yoy"] <= 0], args.min_ev_per_date)
            f_rows = pd.DataFrame([
                {"scope": "D1 zone entiere", **(base or {})},
                {"scope": "D1 sur lignes evenement (E1)", **(on_e1 or {})},
                {"scope": "D1 | eps_yoy > 0", **(pos or {})},
                {"scope": "D1 | eps_yoy <= 0", **(neg or {})},
            ])
            out_lines.append(_fmt_table(f_rows))
        out_lines.append("")

    out_lines.append("Criteres GO (GPT 2026-08-16) : IC WF ET holdout > +0.03 + spread net > 0 + gain vs Global reproductible ;")
    out_lines.append("GO conditionnel si IC ~ +0.02 tres stable + spread fort + complementarite idio ; STOP si IC ~ 0,")
    out_lines.append("spread < 0, gain 2025 seulement, ou disparition apres conditionnement Global/idio.")
    out_lines.append("Rappel semantique : depots SEC != annonces (info partiellement pricee avant) — ne pas rejeter")
    out_lines.append("l'hypothese earnings sur le seul IC ; la surprise vs consensus reste non testee (donnees payantes).")

    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / f"per_sector_d7_earnings_{args.start}_{args.end}.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
