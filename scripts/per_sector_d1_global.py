"""Phase D1 per-sector — Global relatif (plan GPT post-D0, 2026-08-15).

Hypothese : le partage des ~400 titres dans UN SEUL modele global, avec
target = relative_return (future_return - mediane sectorielle du jour) et le
`sector` en feature categorielle, apprend-il l'alpha intra-sectoriel que les
11 modeles independants (~36 titres/date) ne peuvent pas apprendre ?

CONTRAINTE STRICTE : script standalone de recherche. AUCUNE modification de
modelFactory/ — tout est reutilise en lecture seule (compute_features,
build_cross_sectional_features, _prepare_global_symbol_frame, load_*).

Protocole (H20 uniquement, multiple testing reduit) :
  - Features : identiques au Global Model de prod (rangs percentiles,
    agregats sectoriels, exclusives cross-symbol, regime SPY) + features
    *_sector_neutral / *_sector_zscore (features sector-relatives GPT) +
    `sector` categoriel.
  - Target : rel20 = future_return(20j) - mediane_sectorielle(future_return, date),
    winsorisee 1%/99% PAR FOLD sur les quantiles train uniquement.
  - WF : 11 folds de 6 mois (2019-01 -> 2024-06-30), train = tout le passe.
  - Holdout gele : modele entraine sur tout <= 2024-06-30, prediction
    2024-07-01 -> 2025-12-31 (une seule consultation).
  - Metriques : IC relatif + spread quintile net (102 bps) + IC par
    secteur x fold + signal_capture / signal_minus_random (metriques GPT).

Usage :
  python scripts/per_sector_d1_global.py                     # run complet
  python scripts/per_sector_d1_global.py --folds 1 --iterations 30   # smoke
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modelFactory.config import (  # noqa: E402
    BaselineConfig,
    DataConfig,
    GlobalModelConfig,
    TrainingConfig,
)
from modelFactory.cross_sectional import (  # noqa: E402
    SECTOR_NEUTRAL_FEATURE_COLUMNS,
    SECTOR_ZSCORE_FEATURE_COLUMNS,
    build_cross_sectional_features,
    load_sector_groups,
)
from modelFactory.data_loader import (  # noqa: E402
    load_benchmark_bars,
    load_universe_bars,
)
from modelFactory.global_model import (  # noqa: E402
    _get_global_feature_columns,
    _prepare_global_symbol_frame,
)
from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    SPREAD_COST,
    ROUND_TRIP_BPS,
    _fmt_table,
    _read_universe,
    evaluate_period,
)

LOGGER = logging.getLogger("per_sector_d1_global")

# Oracle H20 net de D0 (rapport per_sector_dispersion) — metriques GPT de capture
ORACLE_NET_WF_H20 = 6852.0
ORACLE_NET_HOLDOUT_H20 = 2232.0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D1 per-sector : global relatif (H20)")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--train-start", default="2016-01-01", help="debut des features/train")
    p.add_argument("--wf-start", default="2019-01-01", help="debut des folds WF")
    p.add_argument("--holdout-start", default="2024-07-01", help="debut du holdout gele")
    p.add_argument("--end", default="2025-12-31", help="fin des donnees")
    p.add_argument("--folds", type=int, default=11, help="nb de folds WF de 6 mois")
    p.add_argument("--iterations", type=int, default=300, help="iterations CatBoost")
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--no-sector-cat", action="store_true",
                   help="ablation du secteur categoriel (diagnostic uniquement)")
    return p.parse_args()


def _build_cfg(args: argparse.Namespace) -> TrainingConfig:
    data = DataConfig(
        feature_set="expert",
        target_mode="regression",
        forecast_horizon=20,
        enable_cross_sectional_features=True,
        cross_sectional_min_universe=20,
        benchmark_symbol="SPY",
        training_start_date=date.fromisoformat(args.train_start),
        training_end_date=date.fromisoformat(args.end),
    )
    baseline = BaselineConfig(
        catboost_depth=args.depth,
        catboost_iterations=args.iterations,
        catboost_learning_rate=args.lr,
        catboost_l2_leaf_reg=3.0,
        catboost_border_count=128,
        catboost_random_strength=1.0,
        catboost_bagging_temperature=1.0,
        catboost_od_type="IncToDec",
        catboost_od_wait=20,
    )
    gm = GlobalModelConfig(enabled=True, use_cross_sectional_features=True,
                           model_name="catboost")
    return TrainingConfig(data=data, baseline=baseline, global_model=gm)


def _load_and_prepare(engine, cfg: TrainingConfig, args: argparse.Namespace):
    symbols = _read_universe(args.universe)
    start = pd.Timestamp(args.train_start).date()
    end = pd.Timestamp(args.end).date()
    universe_df = load_universe_bars(
        engine, symbols, start_date=start - timedelta(days=300), end_date=end)
    benchmark_df = load_benchmark_bars(
        engine, "SPY", start_date=start - timedelta(days=300), end_date=end)
    xs_df, _diag = build_cross_sectional_features(
        universe_df, benchmark_df=benchmark_df, min_universe_size=20)

    parts = []
    for sym in symbols:
        bars = universe_df[universe_df["symbol"] == sym]
        if len(bars) < 600:
            continue
        frame = _prepare_global_symbol_frame(
            bars.sort_values("date").reset_index(drop=True),
            cfg=cfg,
            benchmark_df=benchmark_df,
            sentiment_df=None,
            cross_sectional_df=xs_df,
            selector_df=None,
        )
        if not frame.empty:
            parts.append(frame)
    df = pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)

    sector_map: dict[str, str] = {}
    for gics, syms in load_sector_groups(engine).items():
        for s in syms:
            sector_map[s] = gics
    df["sector"] = df["symbol"].map(sector_map)
    df = df.dropna(subset=["sector"]).reset_index(drop=True)

    # relative return H20 (target D1) + version winsorisee intra-date pour le spread
    fr = df["future_return"]
    counts = df.groupby(["date", "sector"])["symbol"].transform("nunique")
    med = df.groupby(["date", "sector"])["future_return"].transform("median")
    df["rel_h20"] = (fr - med).where(counts >= args.min_sector_size)
    lo = df.groupby("date")["rel_h20"].transform(lambda x: x.quantile(0.01))
    hi = df.groupby("date")["rel_h20"].transform(lambda x: x.quantile(0.99))
    df["rel_h20_w"] = df["rel_h20"].clip(lower=lo, upper=hi)
    df["fut_h20"] = fr

    # baseline momentum relatif 20j (B4, reference harness)
    g = df.groupby("symbol", sort=False)["close"]
    df["ret_20"] = g.transform(lambda s: s / s.shift(20) - 1.0)
    med20 = df.groupby(["date", "sector"])["ret_20"].transform("median")
    df["B4_relmom20"] = (df["ret_20"] - med20).where(counts >= args.min_sector_size)
    rng = np.random.default_rng(args.seed)
    df["B0_random"] = rng.random(len(df))

    # features : identiques au Global Model + sector-neutral/zscore + secteur
    feat = list(_get_global_feature_columns(cfg))
    for c in list(SECTOR_NEUTRAL_FEATURE_COLUMNS) + list(SECTOR_ZSCORE_FEATURE_COLUMNS):
        if c in df.columns and c not in feat:
            feat.append(c)
    if not args.no_sector_cat:
        feat.append("sector")
    missing = [c for c in feat if c not in df.columns]
    if missing:
        LOGGER.warning("features manquantes retirees: %s", missing)
        feat = [c for c in feat if c in df.columns]
    return df, feat, sector_map


def _fit_predict_catboost(x_train: pd.DataFrame, y_train: pd.Series,
                          x_pred: pd.DataFrame, args) -> np.ndarray:
    from catboost import CatBoostRegressor

    cat_cols = ["sector"] if "sector" in x_train.columns else None
    model = CatBoostRegressor(
        iterations=args.iterations,
        depth=args.depth,
        learning_rate=args.lr,
        loss_function="RMSE",
        l2_leaf_reg=3.0,
        border_count=128,
        random_strength=1.0,
        bootstrap_type="Bayesian",
        bagging_temperature=1.0,
        random_seed=args.seed,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(x_train, y_train, cat_features=cat_cols)
    return model.predict(x_pred)


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))


def _fold_windows(args) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out = []
    t = pd.Timestamp(args.wf_start)
    hold = pd.Timestamp(args.holdout_start)
    while t < hold:
        out.append((t, min(t + pd.DateOffset(months=6), hold)))
        t = t + pd.DateOffset(months=6)
    return out[: args.folds]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    cfg = _build_cfg(args)

    LOGGER.info("preparation des features (lecture seule modelFactory) ...")
    df, feat, _sm = _load_and_prepare(engine, cfg, args)
    LOGGER.info("frame pret: %d lignes, %d features, %d secteurs",
                len(df), len(feat), df["sector"].nunique())

    wf_start = pd.Timestamp(args.wf_start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)

    # ── Walk-forward : 11 folds de 6 mois ──
    preds: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for fi, (t0, t1) in enumerate(_fold_windows(args)):
        train = df[df["date"] < t0]
        test = df[(df["date"] >= t0) & (df["date"] < t1)]
        tr_ok = train.dropna(subset=["rel_h20"])
        te_ok = test.dropna(subset=["rel_h20"])
        if len(tr_ok) < 10_000 or len(te_ok) < 1000:
            LOGGER.warning("fold %d: trop peu de lignes (train %d, test %d) — skip",
                           fi, len(tr_ok), len(te_ok))
            continue
        y = tr_ok["rel_h20"]
        lo_q, hi_q = y.quantile(0.01), y.quantile(0.99)
        y = y.clip(lower=lo_q, upper=hi_q)
        LOGGER.info("fold %d: %s -> %s | train %d, test %d", fi, t0.date(), t1.date(),
                    len(tr_ok), len(te_ok))
        p = _fit_predict_catboost(tr_ok[feat], y, te_ok[feat], args)
        te_ok = te_ok.assign(D1_pred=p)
        preds.append(te_ok[["symbol", "date", "D1_pred"]])
        ic = _spearman(te_ok["D1_pred"], te_ok["rel_h20"])
        per_sec = {}
        for sec, gs in te_ok.groupby("sector"):
            if len(gs) < 100:
                continue
            per_sec[sec] = round(_spearman(gs["D1_pred"], gs["rel_h20"]), 3)
        fold_rows.append({"fold": fi, "n_test": len(te_ok), "ic": round(ic, 4),
                          "per_sector": per_sec})

    # ── Holdout gele : train complet jusqu'a holdout_start ──
    train_all = df[df["date"] < hold_start]
    hold = df[(df["date"] >= hold_start) & (df["date"] <= end_ts)]
    tr_ok = train_all.dropna(subset=["rel_h20"])
    y = tr_ok["rel_h20"]
    y = y.clip(lower=y.quantile(0.01), upper=y.quantile(0.99))
    LOGGER.info("holdout: train %d lignes (<= %s) -> prediction %d lignes",
                len(tr_ok), hold_start.date(), len(hold))
    p_hold = _fit_predict_catboost(tr_ok[feat], y, hold[feat], args)
    hold = hold.assign(D1_pred=p_hold)
    preds.append(hold[["symbol", "date", "D1_pred"]])

    # ── Assemblage + evaluation harness ──
    oos = pd.concat(preds, ignore_index=True)
    eval_df = df.merge(oos, on=["symbol", "date"], how="left")
    eval_df = eval_df[eval_df["date"] >= wf_start]
    # le harness itere sur les 5 horizons : combler les absents par NaN (D1 = H20 seul)
    for h in HORIZONS:
        for col in (f"rel_h{h}", f"rel_h{h}_w", f"fut_h{h}"):
            if col not in eval_df.columns:
                eval_df[col] = np.nan
    score_cols = ["B0_random", "B4_relmom20", "D1_pred"]
    out_lines: list[str] = []
    out_lines.append("=" * 100)
    out_lines.append("PHASE D1 — GLOBAL RELATIF : 1 modele global, target = relative_return H20")
    out_lines.append(f"univers: {args.universe} | features: {len(feat)} (Global prod + "
                     f"sector-neutral/zscore + sector cat) | CatBoost d{args.depth} i{args.iterations}")
    out_lines.append(f"cout: aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> net = gross - {SPREAD_COST*10_000:.0f} bps")
    out_lines.append("")

    # IC par fold (global + par secteur)
    out_lines.append("IC relatif par fold (Spearman/date, pool du fold) :")
    for r in fold_rows:
        sec_str = " | ".join(f"{k}:{v}" for k, v in sorted(r["per_sector"].items()))
        out_lines.append(f"  fold {r['fold']:2d} : IC {r['ic']:+.3f} (n={r['n_test']})  [{sec_str}]")
    out_lines.append("")

    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        rows = evaluate_period(eval_df, zs, ze, score_cols, args.min_date_size)
        rows20 = [r for r in rows if r["horizon"] == 20]
        out_lines.append(f"ZONE : {zone_name}  [H20]")
        out_lines.append(_fmt_table(pd.DataFrame(rows20).drop(columns=["horizon"])))
        # Metriques de capture GPT (oracle H20 de D0)
        by_score = {r["score"]: r for r in rows20}
        if "D1_pred" in by_score and "B0_random" in by_score:
            oracle = ORACLE_NET_WF_H20 if zone_name == "WALK-FORWARD" else ORACLE_NET_HOLDOUT_H20
            d1 = by_score["D1_pred"]
            b0 = by_score["B0_random"]
            capture = max(d1["spread_net_bps"], 0.0) / oracle
            minus_random = d1["spread_net_bps"] - b0["spread_net_bps"]
            out_lines.append(
                f"  signal_capture = max(net,0)/oracle = {capture:.3f} | "
                f"signal_minus_random = {minus_random:+.0f} bps (oracle net H20 = {oracle:.0f})")
        out_lines.append("")

    out_lines.append("Lecture : ic_mean = IC relatif moyen | ic_pos_pct = % dates IC>0 | "
                     "spread_net_bps = top-bottom net de 102 bps.")
    out_lines.append("Interet D1 (pre-enregistre) : ic_mean > +0.02 avec ic_pos_pct > 60 % ET "
                     "spread_net > 0, stable WF -> holdout, sans dependre d'un seul secteur.")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / "per_sector_d1_global_2019-01-01_2025-12-31.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
