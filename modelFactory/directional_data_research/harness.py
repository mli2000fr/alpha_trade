"""modelFactory/directional_data_research/harness.py — Harnais de séparabilité.

Pool = Oracle TOP20% (``proba_extreme`` OOS PIT) + labels ``oracle_decile`` /
``future_return``. Pour toute nouvelle feature à J (fusionnée au pool), calcule
AVANT tout modèle :

- median D1..D10 ; mean BAD5 / GOOD5 ; delta GOOD5−BAD5 ;
- IC Spearman(feature, décile futur) ;
- AUC(D1-D5 vs D6-D10) et AUC(D1-D3 vs D8-D10) ;
- AUC_amplitude (D1∪D10 vs D2-D9) vs AUC_direction (D6-D10 vs D1-D5) ;
- IC par fold (stabilité du signe OOS).

Usage :
    from modelFactory.directional_data_research.harness import assemble_pool, analyze_features
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL
from modelFactory.oracle.dataset import load_oracle_targets
from modelFactory.oracle.train import roc_auc

_ORACLE_ROOT = Path("artifacts/models/oracle")
_FOLD_CUTS = [pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01"),
              pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"),
              pd.Timestamp("2026-01-01"), pd.Timestamp("2027-01-01")]


def load_oracle_pool_proba(batch_id: str, oracle_run: str | None = None) -> pd.DataFrame:
    """``proba_extreme`` OOS Oracle (PIT) pour définir le pool TOP20% du jour."""
    if oracle_run:
        run_dir = _ORACLE_ROOT / oracle_run
    else:
        # Les bundles récents conservent leur gate OOF exacte dans le dossier
        # du batch. Elle a priorité sur tout fallback global afin de ne jamais
        # mélanger les prédictions d'un autre entraînement Oracle.
        bundle_gate = Path("artifacts/models") / batch_id / "_oracle_oof_gate.parquet"
        if bundle_gate.exists():
            frame = pd.read_parquet(bundle_gate)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
            if "directional_oracle_proba_extreme" in frame.columns:
                frame = frame.rename(columns={
                    "directional_oracle_proba_extreme": "proba_extreme"})
            required = ["date", "symbol", "proba_extreme"]
            if all(column in frame.columns for column in required):
                return frame[required].dropna(subset=["date", "symbol"])
        runs = sorted(_ORACLE_ROOT.glob("oracle-wf-*"))
        run_dir = None
        for r in reversed(runs):
            tagf = r / "batch_id.txt"
            if tagf.exists() and tagf.read_text(encoding="utf-8").strip() == batch_id:
                run_dir = r
                break
        if run_dir is None and runs:
            run_dir = runs[-1]
    if run_dir is None or not run_dir.exists():
        return pd.DataFrame()
    df = pd.read_parquet(run_dir / "oos_predictions.parquet")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df[["date", "symbol", "proba_extreme"]].dropna(subset=["date", "symbol"])


def assemble_pool(
    engine: Any,
    batch_id: str,
    *,
    start_date: str,
    end_date: str,
    horizon: int = 20,
    pool_pct: float = 0.20,
    oracle_run: str | None = None,
) -> pd.DataFrame:
    """Pool Oracle TOP20% + labels décile/rendement + fold/année/régime.

    Retourne (date, symbol, proba_extreme, oracle_decile, future_return,
    fold_start, year, regime) — SANS features (elles seront fusionnées par la
    famille de données testée).
    """
    targets = load_oracle_targets(engine, batch_id, horizon)
    oracle = load_oracle_pool_proba(batch_id, oracle_run)
    df = targets[["prediction_date", "symbol", DECILE_COL, RETURN_COL]].merge(
        oracle, left_on=["prediction_date", "symbol"], right_on=["date", "symbol"],
        how="inner",
    ).drop(columns=["prediction_date"])
    if df.empty:
        return pd.DataFrame()
    df = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]
    df["_eg_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[df["_eg_pct"] >= (1.0 - pool_pct)]
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
    return df


def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:
    s = series.astype(float)
    if s.nunique() < 2 or decile.nunique() < 2:
        return None
    try:
        c = s.corr(decile, method="spearman")
        return float(c) if np.isfinite(c) else None
    except Exception:
        return None


def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 5), good=(6, 10)) -> float | None:
    mask = decile.isin([*bad, *good])
    if mask.sum() < 2:
        return None
    y = np.where(decile[mask].isin(good), 1.0, 0.0)
    s = series[mask].astype(float).to_numpy()
    return roc_auc(y, s)


def analyze_features(pool: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Batterie de séparabilité par feature (direction vs amplitude, stabilité)."""
    rows: list[dict[str, Any]] = []
    dec = pool[DECILE_COL].astype(int)
    ic_folds: dict[str, dict[str, float]] = {}

    for col in feature_columns:
        if col not in pool.columns:
            continue
        s = pool[col].astype(float)
        med = {d: float(s[dec == d].median()) if (dec == d).any() else float("nan") for d in range(1, 11)}
        bad5 = float(s[dec <= 5].mean()) if (dec <= 5).any() else float("nan")
        good5 = float(s[dec >= 6].mean()) if (dec >= 6).any() else float("nan")
        ic = _ic_spearman(s, dec)
        auc_d1d5_d6d10 = _auc_bad_good(s, dec, bad=(1, 5), good=(6, 10))
        auc_d1d3_d8d10 = _auc_bad_good(s, dec, bad=(1, 3), good=(8, 10))
        # amplitude : D1∪D10 vs D2-D9
        amp_y = np.where(dec.isin([1, 10]), 1.0, 0.0)
        auc_amplitude = roc_auc(amp_y, s.astype(float).to_numpy())
        # direction : D6-D10 vs D1-D5
        dir_y = np.where(dec >= 6, 1.0, 0.0)
        auc_direction = roc_auc(dir_y, s.astype(float).to_numpy())
        # IC par fold (stabilité du signe)
        per_fold_ic: dict[str, float] = {}
        for fold_name, g in pool.groupby("fold_start"):
            icf = _ic_spearman(g[col].astype(float), g[DECILE_COL].astype(int))
            if icf is not None:
                per_fold_ic[str(fold_name)] = icf
        sign_stable = "—"
        if len(per_fold_ic) >= 2:
            values = list(per_fold_ic.values())
            n_pos = sum(1 for value in values if value > 0)
            n_neg = sum(1 for value in values if value < 0)
            sign_stable = "OUI" if (n_pos == len(per_fold_ic) or n_neg == len(per_fold_ic)) else "NON"
        ic_folds[col] = per_fold_ic
        rows.append({
            "feature": col,
            **{f"med_D{d}": med[d] for d in range(1, 11)},
            "mean_BAD5": bad5, "mean_GOOD5": good5, "delta_GOOD5_BAD5": good5 - bad5,
            "IC_decile": ic,
            "AUC_D1D5_vs_D6D10": auc_d1d5_d6d10,
            "AUC_D1D3_vs_D8D10": auc_d1d3_d8d10,
            "AUC_amplitude": auc_amplitude,
            "AUC_direction": auc_direction,
            "dir_vs_amp": (auc_direction - auc_amplitude) if (auc_direction is not None and auc_amplitude is not None) else None,
            "stabilite_signes_folds": sign_stable,
            "n_ic_folds": len(per_fold_ic),
            "n_obs": len(s),
        })
    out = pd.DataFrame(rows)
    for fl in ["2022", "2023", "2024", "2025", "2026"]:
        out[f"IC_{fl}"] = [
            ic_folds.get(feature, {}).get(fl) for feature in out["feature"]
        ]
    return out


def format_report(df: pd.DataFrame, top_n: int = 12) -> str:
    lines = [f"=== SÉPARABILITÉ famille de données — {len(df)} features (pool Oracle TOP20%) ==="]
    lines.append("\n--- TOP par AUC_direction (D6-D10 vs D1-D5) ---")
    top = df.sort_values("AUC_direction", key=lambda x: x.fillna(-99), ascending=False).head(top_n)
    lines.append(top[["feature", "AUC_direction", "AUC_amplitude", "dir_vs_amp",
                      "IC_decile", "AUC_D1D3_vs_D8D10", "delta_GOOD5_BAD5",
                      "stabilite_signes_folds"]].to_string(index=False))
    lines.append("\n--- TOP par IC(décile) ---")
    top_ic = df.sort_values("IC_decile", key=lambda x: x.fillna(-99), ascending=False).head(top_n)
    lines.append(top_ic[["feature", "IC_decile", "AUC_direction", "stabilite_signes_folds"]].to_string(index=False))
    return "\n".join(lines)
