"""Phase D5 per-sector — volume / liquidite comme DETECTEUR DE MAGNITUDE.

Plan GPT post-D9-A2 : ne plus optimiser idio_vol60 ; chercher d'autres variables
qui predisent l'amplitude |relative_return_H20|, IDEALEMENT independantes de
l'idio-vol.

Deux volets :
  D5-A : pour chaque variable volume, mesurer uniquement l'amplitude
         (pas de direction) :
           - mag_ic = Spearman(var, |rel_h20_w|) par date -> mean / % pos
           - P_ext_diff = P(extreme|top 30%) - P(extreme|bottom 30%)
         avec extremes = top/bottom 20% intra-date (protocole D9-A2).
  D5-B : independance vs idio_vol60 :
           - mag_ic partiel de chaque variable par tercile d'idio-vol
             (low p<=0.30 / mid 0.30-0.70 / high p>=0.70)
           - pour la meilleure variable : P(extreme) par quintile de volume
             A L'INTERIEUR de chaque tercile d'idio-vol.
         Si le volume ajoute une separation conditionnelle -> 2e dimension.

Standalone, lecture seule modelFactory. Usage : python scripts/per_sector_d5_volume.py
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

from scripts.per_sector_d4_dispersion import _build_panel, _rel_sector  # noqa: E402
from scripts.per_sector_baselines import ROUND_TRIP_BPS  # noqa: E402

LOGGER = logging.getLogger("per_sector_d5")
H = 20


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D5 per-sector : volume -> magnitude")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--buffer-days", type=int, default=360)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _add_volume_features(panel: pd.DataFrame, args: argparse.Namespace) -> dict[str, str]:
    g = panel.groupby("symbol", sort=False)
    panel["S_vr20"] = panel["vr20"]  # alias du ratio deja calcule par _build_panel (D4)
    panel["S_vr60"] = panel["volume"] / g["volume"].transform(
        lambda s: s.rolling(60).mean()).clip(lower=1.0)
    panel["S_vrz20"] = (panel["volume"] - g["volume"].transform(
        lambda s: s.rolling(20).mean())) / g["volume"].transform(
        lambda s: s.rolling(20).std()).clip(lower=1e-9)
    panel["dollar"] = panel["volume"] * panel["close"]
    panel["S_dv20"] = panel["dollar"] / g["dollar"].transform(
        lambda s: s.rolling(20).mean()).clip(lower=1.0)
    panel["S_dvz20"] = (panel["dollar"] - g["dollar"].transform(
        lambda s: s.rolling(20).mean())) / g["dollar"].transform(
        lambda s: s.rolling(20).std()).clip(lower=1e-9)
    ms = args.min_sector_size
    panel["S_vr20_rel"] = _rel_sector(panel, "vr20", ms)
    panel["S_vrz20_rel"] = _rel_sector(panel, "S_vrz20", ms)
    panel["S_dv20_rel"] = _rel_sector(panel, "S_dv20", ms)
    return {
        "S_vr20": "volume/avg20",
        "S_vr60": "volume/avg60",
        "S_vrz20": "volume z-score 20j",
        "S_vr20_rel": "volume/avg20 relatif secteur",
        "S_vrz20_rel": "volume z-score relatif secteur",
        "S_dv20": "dollar volume / avg20",
        "S_dvz20": "dollar volume z-score",
        "S_dv20_rel": "dollar volume relatif secteur",
    }


def _quintile_by_rank(x: pd.Series) -> pd.Series:
    """Quintile 0-4 base sur le rang (robuste aux ex-aequo, contrairement a qcut)."""
    n = max(len(x), 1)
    r = x.rank(method="first")
    return np.minimum((r - 1) * 5 // n, 4).astype(int)


def _mag_a(zone: pd.DataFrame, score_cols: dict[str, str], min_date_size: int) -> pd.DataFrame:
    sub = zone.dropna(subset=["rel_h20_w", "idio60"]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    qdir = sub.groupby("date")["rel_h20_w"].transform(_quintile_by_rank)
    sub["_extreme"] = qdir.isin([0, 4]).astype(int)
    rows = []
    for sc, label in score_cols.items():
        s = sub.dropna(subset=[sc])
        if len(s) < 5000:
            rows.append({"score": sc, "label": label, "mag_ic": np.nan,
                         "mag_ic_pos": np.nan, "p_ext_diff_pp": np.nan})
            continue
        ic = s.groupby("date").apply(
            lambda grp: float(grp[sc].rank().corr(grp["rel_h20_w"].abs().rank())),
            include_groups=False).dropna()
        qv = s.groupby("date")[sc].transform(_quintile_by_rank)
        s = s.assign(_qv=qv)
        p_hi = float(s.loc[s["_qv"] == 4.0, "_extreme"].mean() * 100)
        p_lo = float(s.loc[s["_qv"] == 0.0, "_extreme"].mean() * 100)
        rows.append({
            "score": sc, "label": label,
            "mag_ic": round(float(ic.mean()), 3),
            "mag_ic_pos": round(float((ic > 0).mean() * 100), 1),
            "p_ext_diff_pp": round(p_hi - p_lo, 2),
        })
    return pd.DataFrame(rows)


def _mag_b(zone: pd.DataFrame, score_cols: dict[str, str], min_date_size: int) -> pd.DataFrame:
    """mag_ic partiel par tercile d'idio_vol60 (independance conditionnelle)."""
    sub = zone.dropna(subset=["rel_h20_w", "idio60"]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    p_idio = sub.groupby("date")["idio60"].rank(pct=True)
    sub["_terc"] = np.select([p_idio <= 0.30, p_idio >= 0.70], [0, 2], default=1)
    rows = []
    for sc, label in score_cols.items():
        s = sub.dropna(subset=[sc])
        out = {"score": sc, "label": label}
        for t, name in ((0, "low_idio"), (1, "mid_idio"), (2, "high_idio")):
            st = s[s["_terc"] == t]
            if len(st) < 5000:
                out[f"mag_ic_{name}"] = np.nan
                continue
            ic = st.groupby("date").apply(
                lambda grp: float(grp[sc].rank().corr(grp["rel_h20_w"].abs().rank())),
                include_groups=False).dropna()
            out[f"mag_ic_{name}"] = round(float(ic.mean()), 3)
        rows.append(out)
    return pd.DataFrame(rows)


def _quintile_in_tercile(zone: pd.DataFrame, sc: str, min_date_size: int) -> pd.DataFrame:
    sub = zone.dropna(subset=["rel_h20_w", "idio60", sc]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    p_idio = sub.groupby("date")["idio60"].rank(pct=True)
    sub["_terc"] = np.select([p_idio <= 0.30, p_idio >= 0.70], [0, 2], default=1)
    qv = sub.groupby("date")[sc].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    qdir = sub.groupby("date")["rel_h20_w"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    sub = sub.assign(_qv=qv, _ext=(qdir.isin([0.0, 4.0])).astype(int))
    rows = []
    for t, tname in ((0, "low_idio"), (1, "mid_idio"), (2, "high_idio")):
        for qi in range(5):
            g = sub[(sub["_terc"] == t) & (sub["_qv"] == qi)]
            rows.append({"idio_tercile": tname, "vol_quintile": f"Q{qi+1}",
                         "P_extreme_pct": round(float(g["_ext"].mean() * 100), 1),
                         "n": len(g)})
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    LOGGER.info("construction du panel ...")
    panel = _build_panel(engine, args)
    vol_cols = _add_volume_features(panel, args)
    score_cols = {"S_idio60": "idio_vol60 (reference)"}
    score_cols.update(vol_cols)
    _missing = [c for c in score_cols if c not in panel.columns]
    LOGGER.info("panel colonnes (%d) | manquantes: %s | volume dans panel: %s",
                len(panel.columns), _missing, "volume" in panel.columns)

    wf_start = pd.Timestamp(args.start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)

    out_lines = [
        "=" * 100,
        "PHASE D5 — VOLUME / LIQUIDITE comme DETECTEUR DE MAGNITUDE [H20, pas de direction]",
        f"metrique : mag_ic = Spearman(var, |rel_h20|) par date ; P_ext_diff = "
        f"P(extreme|top30%) - P(extreme|bottom30%), extremes = top/bottom 20% intra-date",
        f"cout rappel : {ROUND_TRIP_BPS:.0f} bps/jambe",
        "",
    ]
    best_wf: str | None = None
    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = panel[(panel["date"] >= zs) & (panel["date"] <= ze)]
        LOGGER.info("D5-A %s ...", zone_name)
        a = _mag_a(zone, score_cols, args.min_date_size)
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name} — D5-A amplitude (mag_ic + P_ext_diff)")
        out_lines.append(a.to_string(index=False))
        out_lines.append("")
        LOGGER.info("D5-B %s ...", zone_name)
        b = _mag_b(zone, score_cols, args.min_date_size)
        out_lines.append(f"ZONE : {zone_name} — D5-B mag_ic partiel par tercile d'idio_vol60")
        out_lines.append(b.to_string(index=False))
        out_lines.append("")
        if zone_name == "WALK-FORWARD" and not a.empty:
            valid = a.dropna(subset=["mag_ic"])
            best_wf = str(valid.loc[valid["mag_ic"].idxmax(), "score"])
    if best_wf:
        for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                    ("HOLDOUT GELE", (hold_start, end_ts))):
            zone = panel[(panel["date"] >= zs) & (panel["date"] <= ze)]
            out_lines.append(f"ZONE : {zone_name} — P(extreme) par quintile de {best_wf} "
                             f"A L'INTERIEUR des terciles d'idio_vol60")
            out_lines.append(_quintile_in_tercile(zone, best_wf, args.min_date_size).to_string(index=False))
            out_lines.append("")

    out_lines.append("Lecture : une variable volume est une 2e brique magnitude si "
                     "(a) mag_ic > +0.10 et p_ext_diff > +10 pp, stable WF->holdout ; "
                     "ET (b) D5-B : mag_ic partiel > +0.05 dans AU MOINS un tercile d'idio "
                     "(idealement les 3) — i.e. information ADDITIVE a idio_vol60.")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / f"per_sector_d5_volume_{args.start}_{args.end}.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
