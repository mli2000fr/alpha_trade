"""modelFactory/global_direction/separability.py — Séparabilité D1..D10 (pool Oracle).

Étude (étape 7-8 du plan recherche) : dans le pool **Oracle TOP20%** uniquement,
pour chaque feature disponible à J, on mesure si elle distingue les futurs
MAUVAIS longs (D1-D5) des BONS longs (D6-D10), conditionnellement au fait qu'un
mouvement extrême est probable.

Par feature :
- median_D1 .. median_D10 ; mean BAD5 / GOOD5 ; delta GOOD5−BAD5 ;
- Spearman(feature, décile futur) ;
- AUC(D1-D3 vs D8-D10) et AUC(D1 vs D10) ;
- **amplitude_separability** : AUC(feature, extrême D1∪D10 vs D2-D9) ;
- **direction_separability** : AUC(feature, bon long D6-D10 vs mauvais D1-D5) ;
- stabilité du signe de l'IC par fold WF (une feature n'est directionnelle que
  si son signe est stable hors échantillon).

Une feature peut être excellente pour l'AMPLITUDE mais mauvaise pour la DIRECTION
→ elle ferait réapprendre Oracle Extreme à GlobalDirection (à éviter).

Usage :
    python -m modelFactory.global_direction.separability --batch-id ... [--symbols N]
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
from modelFactory.global_direction.dataset import (
    DECILE_COL,
    RETURN_COL,
    build_sector_features,
    expert_feature_columns,
)
from modelFactory.oracle.dataset import build_feature_matrix, load_oracle_targets
from modelFactory.oracle.train import get_universe_symbols, roc_auc

LOGGER = logging.getLogger(__name__)
_ORACLE_ROOT = Path("artifacts/models/oracle")


def load_oracle_pool_proba(batch_id: str) -> pd.DataFrame:
    """``proba_extreme`` OOS Oracle (PIT) pour définir le pool TOP20% du jour."""
    runs = sorted(_ORACLE_ROOT.glob("oracle-wf-*"))
    run_dir = None
    for r in reversed(runs):
        tagf = r / "batch_id.txt"
        if tagf.exists() and tagf.read_text(encoding="utf-8").strip() == batch_id:
            run_dir = r
            break
    if run_dir is None and runs:
        run_dir = runs[-1]
    if run_dir is None:
        return pd.DataFrame()
    df = pd.read_parquet(run_dir / "oos_predictions.parquet")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df[["date", "symbol", "proba_extreme"]].dropna(subset=["date", "symbol"])


def build_pool_features(
    engine: Any,
    batch_id: str,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    horizon: int = 20,
    pool_pct: float = 0.20,
) -> tuple[pd.DataFrame, list[str]]:
    """Features PIT + labels (décile/rendement) + pool Oracle TOP20% du jour."""
    feats = build_feature_matrix(engine, symbols, start_date=start_date, end_date=end_date)
    if feats.empty:
        return pd.DataFrame(), []
    base_cols = [c for c in expert_feature_columns() if c in feats.columns]
    xs_cols = [c for c in feats.columns if c.endswith("_xs_rank")]
    feature_columns = base_cols + xs_cols

    sector_frame, sector_cols = build_sector_features(
        engine, symbols, start_date=start_date, end_date=end_date, base_cols=feature_columns,
    )
    if sector_cols:
        feats = feats.merge(sector_frame, on=["symbol", "date"], how="left")
        feature_columns = feature_columns + sector_cols

    targets = load_oracle_targets(engine, batch_id, horizon)
    oracle = load_oracle_pool_proba(batch_id)

    df = feats.merge(
        targets[["prediction_date", "symbol", DECILE_COL, RETURN_COL]],
        left_on=["date", "symbol"], right_on=["prediction_date", "symbol"], how="inner",
    ).drop(columns=["prediction_date"])
    df = df.merge(oracle, on=["date", "symbol"], how="inner")
    if df.empty:
        return pd.DataFrame(), feature_columns

    # Pool Oracle : top pool_pct du jour par proba_extreme (PIT)
    df["_eg_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[df["_eg_pct"] >= (1.0 - pool_pct)]
    df["fold_start"] = pd.cut(
        pd.to_datetime(df["date"]),
        bins=[pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01"),
              pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"),
              pd.Timestamp("2026-01-01"), pd.Timestamp("2027-01-01")],
        labels=["2022", "2023", "2024", "2025", "2026"],
    ).astype(str)
    return df, feature_columns


def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:
    s = series.astype(float)
    if s.nunique() < 2 or decile.nunique() < 2:
        return None
    try:
        c = s.corr(decile, method="spearman")
        return float(c) if np.isfinite(c) else None
    except Exception:
        return None


def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 3), good=(8, 10)) -> float | None:
    mask = decile.isin([*bad, *good])
    if mask.sum() < 2:
        return None
    y = np.where(decile[mask].isin(good), 1.0, 0.0)
    s = series[mask].astype(float).to_numpy()
    return roc_auc(y, s)


def analyze_separability(
    pool: pd.DataFrame,
    feature_columns: list[str],
) -> pd.DataFrame:
    """Par feature : séparabilité amplitude vs direction + stabilité par fold."""
    rows: list[dict[str, Any]] = []
    dec = pool[DECILE_COL].astype(int)
    ic_folds: dict[str, list[float | None]] = {}
    for col in feature_columns:
        if col not in pool.columns:
            continue
        s = pool[col].astype(float)
        med = {d: float(s[dec == d].median()) if (dec == d).any() else float("nan") for d in range(1, 11)}
        bad5 = float(s[dec <= 5].mean()) if (dec <= 5).any() else float("nan")
        good5 = float(s[dec >= 6].mean()) if (dec >= 6).any() else float("nan")
        ic = _ic_spearman(s, dec)
        auc_d1d3_d8d10 = _auc_bad_good(s, dec, bad=(1, 3), good=(8, 10))
        auc_d1_d10 = _auc_bad_good(s, dec, bad=(1,), good=(10,))
        # amplitude : extrême (D1∪D10) vs milieu (D2-D9)
        amp_mask = dec.isin([1, 10, 2, 3, 4, 5, 6, 7, 8, 9])
        amp_y = np.where(dec[amp_mask].isin([1, 10]), 1.0, 0.0)
        amp_s = s[amp_mask].astype(float).to_numpy()
        auc_amplitude = roc_auc(amp_y, amp_s)
        # direction : bon (D6-D10) vs mauvais (D1-D5)
        dir_mask = dec.isin(list(range(1, 11)))
        dir_y = np.where(dec[dir_mask] >= 6, 1.0, 0.0)
        dir_s = s[dir_mask].astype(float).to_numpy()
        auc_direction = roc_auc(dir_y, dir_s)
        # IC par fold (stabilité du signe)
        per_fold_ic: list[float] = []
        for _, g in pool.groupby("fold_start"):
            icf = _ic_spearman(g[col].astype(float), g[DECILE_COL].astype(int))
            if icf is not None:
                per_fold_ic.append(icf)
        sign_stable = "—"
        if len(per_fold_ic) >= 2:
            n_pos = sum(1 for v in per_fold_ic if v > 0)
            n_neg = sum(1 for v in per_fold_ic if v < 0)
            sign_stable = "OUI" if (n_pos == len(per_fold_ic) or n_neg == len(per_fold_ic)) else "NON"
        ic_folds[col] = per_fold_ic
        rows.append({
            "feature": col,
            **{f"med_D{d}": med[d] for d in range(1, 11)},
            "mean_BAD5": bad5, "mean_GOOD5": good5,
            "delta_GOOD5_BAD5": good5 - bad5,
            "IC_decile": ic,
            "AUC_D1D3_vs_D8D10": auc_d1d3_d8d10,
            "AUC_D1_vs_D10": auc_d1_d10,
            "AUC_amplitude": auc_amplitude,
            "AUC_direction": auc_direction,
            "dir_vs_amp": (auc_direction - auc_amplitude) if (auc_direction is not None and auc_amplitude is not None) else None,
            "stabilite_signes_folds": sign_stable,
            "n_ic_folds": len(per_fold_ic),
        })
    df = pd.DataFrame(rows)
    # IC moyen par fold (colonne de lecture)
    fold_labels = ["2022", "2023", "2024", "2025", "2026"]
    for fl in fold_labels:
        df[f"IC_{fl}"] = [np.mean([v for v in ic_folds.get(f, []) if v is not None]) if ic_folds.get(f) else None
                          for f in df["feature"]]
    return df


def format_report(df: pd.DataFrame, top_n: int = 15) -> str:
    lines = [f"=== SÉPARABILITÉ D1..D10 dans le pool Oracle TOP20% — {len(df)} features ==="]
    # Top par IC décile
    top_ic = df.sort_values("IC_decile", key=lambda s: s.fillna(-99), ascending=False).head(top_n)
    lines.append("\n--- TOP par IC(décile) ---")
    lines.append(top_ic[["feature", "IC_decile", "AUC_D1_vs_D10", "AUC_amplitude",
                         "AUC_direction", "dir_vs_amp", "stabilite_signes_folds"]].to_string(index=False))
    # Top par AUC direction
    top_dir = df.sort_values("AUC_direction", key=lambda s: s.fillna(-99), ascending=False).head(top_n)
    lines.append("\n--- TOP par AUC_direction (D6-D10 vs D1-D5) ---")
    lines.append(top_dir[["feature", "AUC_direction", "AUC_amplitude", "dir_vs_amp",
                          "IC_decile", "delta_GOOD5_BAD5", "stabilite_signes_folds"]].to_string(index=False))
    # Amplitude forte mais direction faible (= réapprend Oracle, à éviter)
    lines.append("\n--- Amplitude forte / direction faible (piège : réapprend Oracle) ---")
    top_amp = df.sort_values("AUC_amplitude", key=lambda s: s.fillna(-99), ascending=False).head(10)
    lines.append(top_amp[["feature", "AUC_amplitude", "AUC_direction", "dir_vs_amp"]].to_string(index=False))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité D1..D10 dans le pool Oracle TOP20%.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--symbols", type=int, default=None)
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, batch_id, 20)
    if args.symbols:
        symbols = symbols[: args.symbols]

    pool, feature_columns = build_pool_features(
        engine, batch_id, symbols,
        start_date=args.start_date, end_date=args.end_date,
    )
    if pool.empty:
        raise SystemExit("Pool vide.")
    LOGGER.info("pool Oracle top20%% : %d lignes, %d dates, %d features",
                len(pool), pool["date"].nunique(), len(feature_columns))

    result = analyze_separability(pool, feature_columns)
    out_path = Path("artifacts/global_direction_separability.csv")
    result.to_csv(out_path, index=False)
    print(f"→ CSV : {out_path}")
    print(format_report(result, top_n=args.top_n))


if __name__ == "__main__":
    main()
