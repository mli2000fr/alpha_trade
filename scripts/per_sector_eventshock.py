"""Phase D3 per-sector — Event shock : continuation vs reversal post-choc.

Hypothese (GPT post-D0) : apres un mouvement anormal RELATIF au secteur
(|abnormal_return_1d| eleve), y a-t-il continuation (drift) ou reversal ?
C'est une hypothese differente du momentum 20/60/120.

Scores testes (IC relatif + spread net, zones WF + holdout) :
  S_abr1 / S_abr3 / S_abr5 : abnormal return relatif 1/3/5j (continuation)
  R_abr1 / R_abr3 / R_abr5 : -abnormal (reversal)
  E_cont / E_rev          : conditionnes evenement (|abr1| >= 2x MAD intra-date),
                             score = +sign(abr1) (continuation) / -sign (reversal),
                             NaN hors evenement (lignes exclues de l'evaluation)
References : B0_random (harness), B4_relmom20 (momentum 20j relatif).

Usage : python scripts/per_sector_eventshock.py
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
    evaluate_period,
    parse_args,
)

LOGGER = logging.getLogger("per_sector_eventshock")


def add_event_scores(panel: pd.DataFrame) -> list[str]:
    """Ajoute les abnormal returns relatifs et les scores evenementiels."""
    # ret_3 : rendement cumule 3 jours
    panel["ret_3"] = panel.groupby("symbol")["close"].transform(
        lambda s: s / s.shift(3) - 1.0)
    for w, col in ((1, "ret_1"), (3, "ret_3"), (5, "ret_5")):
        med = panel.groupby(["date", "sector"])[col].transform("median")
        panel[f"abr{w}"] = panel[col] - med
    # seuil evenement : 2x MAD intra-date de abr1
    mad1 = panel.groupby("date")["abr1"].transform(
        lambda x: (x - x.median()).abs().median())
    ev = panel["abr1"].abs() >= 2.0 * mad1
    panel["E_cont"] = np.where(ev, np.sign(panel["abr1"]), np.nan)
    panel["E_rev"] = np.where(ev, -np.sign(panel["abr1"]), np.nan)
    for w in (1, 3, 5):
        panel[f"S_abr{w}"] = panel[f"abr{w}"]
        panel[f"R_abr{w}"] = -panel[f"abr{w}"]
    LOGGER.info("evenements |abr1| >= 2xMAD : %.2f %% des lignes",
                100.0 * float(ev.mean()))
    return ["S_abr1", "S_abr3", "S_abr5", "R_abr1", "R_abr3", "R_abr5",
            "E_cont", "E_rev"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _fh = logging.FileHandler(Path("logs") / "eventshock_progress.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(_fh)
    args = parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    symbols = _read_universe(args.universe)
    panel = build_panel(engine, symbols, pd.Timestamp(args.start).date(),
                        pd.Timestamp(args.end).date(), args.buffer_days)
    panel = add_sector_medians(panel, args.min_sector_size)
    add_baseline_scores(panel, args.seed)
    event_cols = add_event_scores(panel)
    score_cols = ["B0_random", "B4_relmom20"] + event_cols

    start_ts, hold_ts, end_ts = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start),
                                 pd.Timestamp(args.end))
    wf_zone = panel[(panel["date"] >= start_ts) & (panel["date"] < hold_ts)]
    hold_zone = panel[(panel["date"] >= hold_ts) & (panel["date"] <= end_ts)]

    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("PHASE D3 — EVENT SHOCK : continuation vs reversal post-choc relatif au secteur")
    lines.append(f"univers: {args.universe} ({len(symbols)} symboles)")
    lines.append(f"zones : WF {args.start} -> {args.holdout_start} (exclu) | "
                 f"HOLDOUT {args.holdout_start} -> {args.end}")
    lines.append(f"couts : aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> "
                 f"spread net = gross - {SPREAD_COST*10_000:.0f} bps")
    lines.append("evenement = |abr1| >= 2x MAD intra-date de abr1 ; "
                 "E_cont/E_rev evalues uniquement sur les lignes evenement")
    lines.append("")

    for zone_name, zone_df in (("WALK-FORWARD", wf_zone), ("HOLDOUT GELE", hold_zone)):
        lines.append("=" * 100)
        lines.append(f"ZONE : {zone_name}")
        lines.append("=" * 100)
        LOGGER.info("evaluation %s ...", zone_name)
        rows = evaluate_period(zone_df, zone_df["date"].min(), zone_df["date"].max(),
                               score_cols, max(args.min_date_size, 20))
        if not rows:
            LOGGER.warning("aucune ligne evaluee pour %s", zone_name)
            continue
        df = pd.DataFrame(rows)
        for h in HORIZONS:
            sub = df[df["horizon"] == h]
            if sub.empty:
                continue
            sub = sub.drop(columns=["horizon"])
            lines.append(f"[H{h}] IC relatif (Spearman/date vs rel_return) + spread quintile")
            lines.append(_fmt_table(sub))
            lines.append("")
        LOGGER.info("evaluation %s OK", zone_name)

    lines.append("")
    lines.append("Lecture : ic_mean = IC relatif moyen | ic_pos_pct = % dates IC>0 | "
                 "spread_net_bps = spread top-bottom net de 102 bps.")
    lines.append("Continuation = S_abr* / E_cont positifs ; Reversal = R_abr* / E_rev positifs. "
                 "Interet si ic_mean > 0.02 avec ic_pos_pct > 60 % ET spread_net_bps > 0, "
                 "stable WF -> holdout. H20 = horizon prioritaire (plan GPT).")

    out = "\n".join(lines)
    print(out)
    out_path = Path("logs") / f"per_sector_eventshock_{args.start}_{args.end}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
