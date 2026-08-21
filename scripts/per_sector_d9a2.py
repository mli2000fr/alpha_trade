"""Phase D9-A2 per-sector — comprendre idio_vol60 : amplitude vs tilt directionnel.

Protocole strict (fige avant resultats, plan GPT post-D9-A1) :
  - extremes = top/bottom 20 % intra-date de rel_h20_w ;
  - high_idio = p_ext(idio_vol60) >= 0.70 ; low_idio = p_ext <= 0.30 ;
  - H20, memes couts (102 bps), WF 2019-2024 puis holdout gele ;
  - aucune re-optimisation apres avoir vu le holdout.

Analyses :
  1. Matrice 2x2 : Down/Up extreme x Low/High idio (4 cellules de P).
  2. Test 1 magnitude pure : P(extreme|high) - P(extreme|low).
  3. Test 2 direction conditionnelle : P(up|extreme,high) - 50 % (et low).
  4. Test 3 interaction : IC du D1_pred restreint aux rows high vs low
     ("quand idio_vol est eleve, D1 distingue-t-il mieux gagnants/perdants ?").
  5. Controle random-gate : D1 + gate 60/70/80 vs D1 + gate ALEATOIRE au meme
     taux de selection (seed fixe) — un filtre quelconque n'ameliore-t-il pas
     mecaniquement le spread ?
  6. M3 blending monotone : D1 x (a + b p_ext), a,b fits en validation WF
     (regression sans intercept sur rows WF), appliques au holdout.

Usage : python scripts/per_sector_d9a2.py
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
    HORIZONS,
    ROUND_TRIP_BPS,
    SPREAD_COST,
    _fmt_table,
    evaluate_period,
)
from scripts.per_sector_d1_global import (  # noqa: E402
    _build_cfg,
    _load_and_prepare,
)
from scripts.per_sector_d4_dispersion import _beta_idio  # noqa: E402
from scripts.per_sector_d9a import _run_d1_folds  # noqa: E402

LOGGER = logging.getLogger("per_sector_d9a2")
GATES = [0.60, 0.70, 0.80]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D9-A2 per-sector : comprendre idio_vol60")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--train-start", default="2016-01-01")
    p.add_argument("--wf-start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--folds", type=int, default=11)
    p.add_argument("--iterations", type=int, default=300)
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--no-sector-cat", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def _cell_analysis(zone: pd.DataFrame, min_date_size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = zone.dropna(subset=["rel_h20_w", "idio60", "D1_pred"]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    qdir = sub.groupby("date")["rel_h20_w"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    sub["_up"] = (qdir == 4.0).astype(int)
    sub["_down"] = (qdir == 0.0).astype(int)
    sub["_extreme"] = ((qdir == 4.0) | (qdir == 0.0)).astype(int)
    sub["_high"] = (sub["p_ext"] >= 0.70).astype(int)
    sub["_low"] = (sub["p_ext"] <= 0.30).astype(int)

    cells = pd.DataFrame([
        {"cellule": "Low idio x Down extreme", "n": int(((sub["_low"] == 1) & (sub["_down"] == 1)).sum()),
         "P_cell_pct": round(float(((sub["_low"] == 1) & (sub["_down"] == 1)).mean() * 100), 2)},
        {"cellule": "Low idio x Up extreme", "n": int(((sub["_low"] == 1) & (sub["_up"] == 1)).sum()),
         "P_cell_pct": round(float(((sub["_low"] == 1) & (sub["_up"] == 1)).mean() * 100), 2)},
        {"cellule": "High idio x Down extreme", "n": int(((sub["_high"] == 1) & (sub["_down"] == 1)).sum()),
         "P_cell_pct": round(float(((sub["_high"] == 1) & (sub["_down"] == 1)).mean() * 100), 2)},
        {"cellule": "High idio x Up extreme", "n": int(((sub["_high"] == 1) & (sub["_up"] == 1)).sum()),
         "P_cell_pct": round(float(((sub["_high"] == 1) & (sub["_up"] == 1)).mean() * 100), 2)},
    ])

    hi = sub[sub["_high"] == 1]
    lo = sub[sub["_low"] == 1]
    p_ext_hi = float(hi["_extreme"].mean()) * 100
    p_ext_lo = float(lo["_extreme"].mean()) * 100
    p_up_hi = float(hi.loc[hi["_extreme"] == 1, "_up"].mean()) * 100 if (hi["_extreme"] == 1).any() else np.nan
    p_up_lo = float(lo.loc[lo["_extreme"] == 1, "_up"].mean()) * 100 if (lo["_extreme"] == 1).any() else np.nan

    def _ic_restricted(s: pd.DataFrame) -> float:
        ic = s.groupby("date").apply(
            lambda g: float(g["D1_pred"].rank().corr(g["rel_h20_w"].rank())),
            include_groups=False)
        return float(ic.dropna().mean())

    tests = pd.DataFrame([
        {"test": "T1 magnitude pure : P(extreme|high) - P(extreme|low) (pp)",
         "valeur": round(p_ext_hi - p_ext_lo, 2)},
        {"test": "T2a direction cond : P(up|extreme,high) - 50% (pp)",
         "valeur": round(p_up_hi - 50.0, 2) if not np.isnan(p_up_hi) else np.nan},
        {"test": "T2b direction cond : P(up|extreme,low) - 50% (pp)",
         "valeur": round(p_up_lo - 50.0, 2) if not np.isnan(p_up_lo) else np.nan},
        {"test": "T3 interaction : IC(D1|high) vs IC(D1|low)",
         "valeur": round(_ic_restricted(hi) - _ic_restricted(lo), 4)},
        {"test": "  IC(D1|high_idio)", "valeur": round(_ic_restricted(hi), 4)},
        {"test": "  IC(D1|low_idio)", "valeur": round(_ic_restricted(lo), 4)},
        {"test": "P(extreme|high) % / P(extreme|low) %",
         "valeur": round(p_ext_hi, 2)},
        {"test": "", "valeur": round(p_ext_lo, 2)},
    ])
    return cells, tests


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    cfg = _build_cfg(args)

    LOGGER.info("preparation des features ...")
    df, feat, _ = _load_and_prepare(engine, cfg, args)

    df["ret_1"] = df["daily_return"]
    df["sector_ret"] = df.groupby(["date", "sector"])["ret_1"].transform("mean")
    reg = df.groupby("symbol", group_keys=False).apply(_beta_idio, include_groups=False)
    df = df.join(reg)
    df["p_ext"] = df.groupby("date")["idio60"].rank(pct=True)
    df["p_ext"] = df["p_ext"].where(df["idio60"].notna())

    preds = _run_d1_folds(df, feat, args)
    eval_df = df.merge(preds, on=["symbol", "date"], how="left")
    wf_start = pd.Timestamp(args.wf_start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)
    eval_df = eval_df[eval_df["date"] >= wf_start]

    d1p = eval_df["D1_pred"]
    pe = eval_df["p_ext"]
    eval_df["A0_global"] = d1p
    for g in GATES:
        eval_df[f"A2_g{int(g*100):02d}"] = d1p.where(pe >= g)
    # controle random-gate : meme taux de selection, selection aleatoire intra-date
    rng = np.random.default_rng(1234)
    rnd = pd.Series(rng.random(len(eval_df)), index=eval_df.index)
    for g in GATES:
        rate = 1.0 - g  # fraction conservee
        th = eval_df.groupby("date")["D1_pred"].transform(
            lambda s: rnd.loc[s.index].quantile(1.0 - rate))
        eval_df[f"RG_g{int(g*100):02d}"] = d1p.where(rnd >= th)
    # M3 blending monotone : D1 x (a + b p_ext), a,b fits sur WF (validation)
    wf_rows = eval_df[(eval_df["date"] >= wf_start) & (eval_df["date"] < hold_start)]
    X = np.column_stack([wf_rows["D1_pred"], wf_rows["D1_pred"] * wf_rows["p_ext"]])
    y = wf_rows["rel_h20_w"].to_numpy()
    mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
    a, b = np.linalg.lstsq(X[mask], y[mask], rcond=None)[0]
    LOGGER.info("M3 fit WF : a=%.4f b=%.4f", a, b)
    eval_df["M3_blend"] = d1p * (a + b * pe)

    for h in HORIZONS:
        for col in (f"rel_h{h}", f"rel_h{h}_w", f"fut_h{h}"):
            if col not in eval_df.columns:
                eval_df[col] = np.nan

    score_cols = (["B0_random", "B4_relmom20", "A0_global"]
                  + [f"A2_g{int(g*100):02d}" for g in GATES]
                  + [f"RG_g{int(g*100):02d}" for g in GATES]
                  + ["M3_blend"])

    out_lines = [
        "=" * 100,
        "PHASE D9-A2 — IDIO_VOL60 : AMPLITUDE vs TILT DIRECTIONNEL [H20, OOS pur]",
        f"extremes = top/bottom 20% intra-date | high = p_ext>=70% | low = p_ext<=30% | "
        f"cout {ROUND_TRIP_BPS:.0f} bps/jambe",
        "RG_gXX = controle RANDOM-gate au meme taux de selection (seed 1234). "
        "M3_blend = D1 x (a+b p_ext), a,b fits WF uniquement.",
        "",
    ]

    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = eval_df[(eval_df["date"] >= zs) & (eval_df["date"] <= ze)]
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name}")
        cells, tests = _cell_analysis(zone, args.min_date_size)
        out_lines.append("Matrice 2x2 (P par cellule, % des rows) :")
        out_lines.append(_fmt_table(cells))
        out_lines.append("Tests :")
        out_lines.append(_fmt_table(tests))
        out_lines.append("")
        rows = evaluate_period(zone, zs, ze, score_cols, args.min_date_size)
        rows20 = [r for r in rows if r["horizon"] == 20]
        out_lines.append("Direction (IC relatif + spread net) :")
        out_lines.append(_fmt_table(pd.DataFrame(rows20).drop(columns=["horizon"])))
        out_lines.append("")

    out_lines.append("Lecture : T1 stable WF->holdout => amplitude reelle. "
                     "T2 positif seulement holdout => tilt regime. "
                     "T3 > 0 => D1 plus fiable quand idio_vol eleve. "
                     "A2 doit battre A0 ET son controle RG au meme taux.")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / "per_sector_d9a2_2019-01-01_2025-12-31.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
