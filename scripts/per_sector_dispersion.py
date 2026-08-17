"""Phase D0 per-sector — Dispersion / Economic Ceiling (oracle).

Repond a : « meme avec une prediction PARFAITE, combien pouvait-on gagner ? »
Et : « y a-t-il assez de dispersion intra-sectorielle pour que le ranking soit
rentable apres 102 bps de couts ? »

Pour chaque secteur x date x horizon :
  - Dispersion de relative_return : std, P90-P10, P75-P25, MAD (en bps)
  - Oracle spread : top 20% vs bottom 20% PAR le rendement futur relatif
    (information parfaite, diagnostic uniquement) -> brut et net de couts
  - Memes spreads pour B0 (hasard), B4 (momentum relatif) et S_short_score
    -> predictability ceiling : meilleur signal / oracle

Zones : WF 2019-01 -> 2024-06 | HOLDOUT 2024-07 -> 2025-12.

Usage : python scripts/per_sector_dispersion.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    SPREAD_COST,
    ROUND_TRIP_BPS,
    _fmt_table,
    _read_universe,
    add_baseline_scores,
    add_sector_medians,
    build_panel,
    parse_args,
)
from scripts.per_sector_baselines_signals import add_signal_scores  # noqa: E402

LOGGER = logging.getLogger("per_sector_dispersion")


def _spread_by_group(df: pd.DataFrame, score_col: str, value_col: str) -> pd.Series:
    """Spread top/bottom quintile du score, par (date, secteur). Vectorise."""
    r = df.groupby(["date", "sector"])[score_col].transform(lambda x: x.rank(pct=True))
    top = df[value_col].where(r >= 0.8)
    bot = df[value_col].where(r <= 0.2)
    top_m = top.groupby([df["date"], df["sector"]]).mean()
    bot_m = bot.groupby([df["date"], df["sector"]]).mean()
    return top_m - bot_m


def _dispersion(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    med = df.groupby(["date", "sector"])[value_col].transform("median")
    q = df.groupby(["date", "sector"])[value_col].quantile([0.10, 0.25, 0.75, 0.90]).unstack()
    std = df.groupby(["date", "sector"])[value_col].std()
    mad = (df[value_col] - med).abs().groupby([df["date"], df["sector"]]).median()
    out = pd.DataFrame({
        "std": std,
        "p10": q[0.10], "p25": q[0.25], "p75": q[0.75], "p90": q[0.90],
        "mad": mad,
    })
    out["p9010"] = (out["p90"] - out["p10"]) * 10_000
    out["p7525"] = (out["p75"] - out["p25"]) * 10_000
    out["mad_bps"] = out["mad"] * 10_000
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _fh = logging.FileHandler(Path("logs") / "dispersion_progress.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(_fh)
    args = parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    symbols = _read_universe(args.universe)
    panel = build_panel(engine, symbols, pd.Timestamp(args.start).date(),
                        pd.Timestamp(args.end).date(), args.buffer_days)
    panel = add_sector_medians(panel, args.min_sector_size)
    add_baseline_scores(panel, args.seed)
    panel, _ = add_signal_scores(panel, engine, args.start, args.end)
    panel["S_short_score"] = panel["S_short_score"].astype(float)

    start_ts, hold_ts, end_ts = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start),
                                 pd.Timestamp(args.end))
    zones = {
        "WALK-FORWARD": (start_ts, hold_ts - pd.Timedelta(days=1)),
        "HOLDOUT GELE": (hold_ts, end_ts),
    }

    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("PHASE D0 — DISPERSION INTRA-SECTORIELLE & ECONOMIC CEILING (ORACLE)")
    lines.append(f"univers: {args.universe} ({len(symbols)} symboles)")
    lines.append(f"couts : aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> spread net = gross - "
                 f"{SPREAD_COST*10_000:.0f} bps")
    lines.append("oracle = top 20% vs bottom 20% PAR le rendement futur relatif (information "
                 "parfaite, diagnostic)")
    lines.append("p9010/p7525/mad = dispersion de relative_return intra-secteur, en bps")
    lines.append("")

    ceiling_rows: list[dict] = []
    for zone_name, (z_start, z_end) in zones.items():
        lines.append("=" * 100)
        lines.append(f"ZONE : {zone_name}")
        lines.append("=" * 100)
        for h in HORIZONS:
            rel_col = f"rel_h{h}"
            sub = panel[(panel["date"] >= z_start) & (panel["date"] <= z_end)].dropna(subset=[rel_col])
            # min 5 symboles par (date, secteur)
            size = sub.groupby(["date", "sector"])["symbol"].transform("nunique")
            sub = sub[size >= 5].copy()
            if sub.empty:
                continue
            LOGGER.info("D0 %s H%d : %d lignes, %d secteurs-dates ...", zone_name, h,
                        len(sub), sub.groupby(["date", "sector"]).ngroups)
            disp = _dispersion(sub, rel_col)
            oracle = _spread_by_group(sub, rel_col, rel_col)
            b0 = _spread_by_group(sub, "B0_random", rel_col)
            b4 = _spread_by_group(sub, "B4_relmom20", rel_col)
            short = _spread_by_group(sub.dropna(subset=["S_short_score"]),
                                     "S_short_score", rel_col)

            per_sec: list[dict] = []
            for sec in sorted(sub["sector"].unique()):
                d = disp.loc[(slice(None), sec), :]
                o = oracle.loc[(slice(None), sec)]
                b0s = b0.loc[(slice(None), sec)]
                b4s = b4.loc[(slice(None), sec)]
                sh = short.loc[(slice(None), sec)]
                og, on = float(o.mean()), float(o.mean() - SPREAD_COST)
                b4n = float(b4s.mean() - SPREAD_COST)
                per_sec.append({
                    "sector": sec,
                    "n_dates": int(len(o)),
                    "p9010_bps": float(d["p9010"].mean()),
                    "oracle_gross": og * 10_000,
                    "oracle_net": on * 10_000,
                    "B0_net": float(b0s.mean() - SPREAD_COST) * 10_000,
                    "B4_net": b4n * 10_000,
                    "short_net": float(sh.mean() - SPREAD_COST) * 10_000,
                    "ceiling_used_pct": float(b4n / on * 100) if on > 0 else float("nan"),
                })
            # TOTAL (pooled, toutes secteurs)
            og_p = float(oracle.mean()); on_p = og_p - SPREAD_COST
            b4n_p = float(b4.mean() - SPREAD_COST)
            per_sec.append({
                "sector": "TOTAL",
                "n_dates": int(len(oracle)),
                "p9010_bps": float(disp["p9010"].mean()),
                "oracle_gross": og_p * 10_000,
                "oracle_net": on_p * 10_000,
                "B0_net": float(b0.mean() - SPREAD_COST) * 10_000,
                "B4_net": b4n_p * 10_000,
                "short_net": float(short.mean() - SPREAD_COST) * 10_000,
                "ceiling_used_pct": float(b4n_p / on_p * 100) if on_p > 0 else float("nan"),
            })
            ceiling_rows.append({
                "zone": zone_name, "horizon": h,
                "oracle_net_bps": on_p * 10_000,
                "B4_net_bps": b4n_p * 10_000,
                "short_net_bps": float(short.mean() - SPREAD_COST) * 10_000,
                "ceiling_used_pct": float(b4n_p / on_p * 100) if on_p > 0 else float("nan"),
            })
            df = pd.DataFrame(per_sec)
            lines.append("")
            lines.append(f"[H{h}] {zone_name} — dispersion + oracle spread par secteur (bps)")
            lines.append(_fmt_table(df))
            lines.append("")

    lines.append("=" * 100)
    lines.append("SYNTHESE ECONOMIC CEILING (pooled) : oracle net = plafond avec prediction parfaite ;")
    lines.append("B4_net = meilleur signal technique ; ceiling_used_pct = part du plafond capturee.")
    lines.append("")
    cd = pd.DataFrame(ceiling_rows)
    lines.append(_fmt_table(cd))
    lines.append("")
    lines.append("Lecture : oracle_net >> 102 bps = du potentiel economique existe (le probleme devient "
                 "« comment le predire ») ; oracle_net proche de 0 ou negatif = le secteur ne vaut pas "
                 "la peine d'etre ranke apres couts.")

    out = "\n".join(lines)
    print(out)
    out_path = Path("logs") / f"per_sector_dispersion_{args.start}_{args.end}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
