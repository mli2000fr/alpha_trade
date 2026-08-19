"""modelFactory/oracle/audit.py — Audit Oracle reproductible (S2).

Reproduit, **depuis la table `global_oracle_labels`** (construite en S1), les
métriques de l'audit Oracle (``doc/backtest_audit.md`` §19) :

- **TOP capture** : % des entrées LONG dont le titre était dans le TOP 10 % réel
  du jour (H20) — cible 16.7 % ;
- **BOTTOM capture** : % des entrées SHORT dans le BOTTOM 10 % — cible 8.2 % ;
- **répartition des déciles** des trades longs/shorts ;
- **courbe rendement/décile** + **monotonicité** (Spearman déciles ↔ rendement) ;
- **comparaison au golden** ``oracle_per_trade.csv`` (sortie de
  ``scripts/oracle_selection_audit.py``) : écart de pct_rank, match des déciles.

Usage :
    python -m modelFactory.oracle.audit --run-id 20260817_205031_2a2836d1
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id

LOGGER = logging.getLogger(__name__)

_RUN_ROOT = Path("artifacts/ihm_backtesting_runs/run")

_LABEL_COLUMNS = [
    "prediction_date", "symbol", "oracle_pct_rank", "oracle_decile",
    "oracle_extreme10", "future_return",
]


def load_trades(trades_path: Path | str) -> pd.DataFrame:
    """Charge et normalise ``trades.csv`` (signal_date + side buy/sell)."""
    df = pd.read_csv(trades_path, low_memory=False)
    df["signal_date"] = pd.to_datetime(df["signal_date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["signal_date"])
    df = df[df["side"].isin(["buy", "sell"])].copy()
    return df


def load_oracle_labels(
    engine: Any,
    batch_id: str,
    horizon: int = 20,
    start: Any = None,
    end: Any = None,
) -> pd.DataFrame:
    """Charge les labels Oracle depuis ``global_oracle_labels``.

    ``oracle_top10`` / ``oracle_bottom10`` sont dérivés localement depuis
    ``oracle_pct_rank`` (TOP = pct_rank ≥ 0.90, BOTTOM = pct_rank ≤ 0.10) :
    la colonne de la table est désormais ``oracle_extreme10`` (= TOP ∪ BOTTOM,
    target du modèle Oracle Extreme).
    """
    query = (
        "SELECT prediction_date, symbol, oracle_pct_rank, oracle_decile, "
        "oracle_extreme10, future_return "
        "FROM global_oracle_labels WHERE batch_id = :bid AND horizon = :h"
    )
    params: dict[str, Any] = {"bid": batch_id, "h": horizon}
    if start is not None:
        query += " AND prediction_date >= :start"
        params["start"] = start
    if end is not None:
        query += " AND prediction_date <= :end"
        params["end"] = end
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)
    df["prediction_date"] = pd.to_datetime(df["prediction_date"]).dt.normalize()
    # Dérivation locale top/bottom depuis pct_rank (définition cross-sectionnelle identique)
    if "oracle_pct_rank" in df.columns:
        df["oracle_top10"] = (df["oracle_pct_rank"] >= 0.90).astype(int)
        df["oracle_bottom10"] = (df["oracle_pct_rank"] <= 0.10).astype(int)
    return df


def attach_oracle_labels(trades_df: pd.DataFrame, oracle_df: pd.DataFrame) -> pd.DataFrame:
    """Joint les labels Oracle aux trades (clé : symbol + signal_date/prediction_date)."""
    return pd.merge(
        trades_df,
        oracle_df,
        left_on=["symbol", "signal_date"],
        right_on=["symbol", "prediction_date"],
        how="left",
        suffixes=("", "_label"),
    )


def compute_capture(labeled: pd.DataFrame) -> dict[str, Any]:
    """TOP/BOTTOM capture + répartition des déciles des trades."""
    longs = labeled[labeled["side"] == "buy"]
    shorts = labeled[labeled["side"] == "sell"]

    def _hist(df: pd.DataFrame) -> list[int]:
        if df.empty:
            return [0] * 10
        dec = df["oracle_decile"].dropna().astype(int)
        return [int((dec == d).sum()) for d in range(1, 11)]

    long_top = longs["oracle_top10"].dropna()
    short_bottom = shorts["oracle_bottom10"].dropna()

    return {
        "n_long": int(len(longs)),
        "n_short": int(len(shorts)),
        "top_capture_pct": 100.0 * float(long_top.mean()) if not long_top.empty else None,
        "bottom_capture_pct": 100.0 * float(short_bottom.mean()) if not short_bottom.empty else None,
        "long_decile_hist": _hist(longs),
        "short_decile_hist": _hist(shorts),
        "long_median_decile": float(longs["oracle_decile"].median()) if not longs.empty else None,
        "short_median_decile": float(shorts["oracle_decile"].median()) if not shorts.empty else None,
    }


def compute_decile_returns(oracle_df: pd.DataFrame) -> pd.DataFrame:
    """Courbe rendement/décile (mean/median/count de ``future_return`` par décile)."""
    if oracle_df.empty or "oracle_decile" not in oracle_df.columns:
        return pd.DataFrame(columns=["decile", "mean", "median", "count"]).set_index("decile")
    dec = oracle_df["oracle_decile"].dropna().astype(int)
    stats = oracle_df.loc[dec.index].copy()
    stats["oracle_decile"] = dec
    grouped = stats.groupby("oracle_decile")["future_return"].agg(
        mean="mean", median="median", count="count",
    )
    return grouped


def decile_monotonicity(decile_stats: pd.DataFrame) -> float | None:
    """Spearman (corrélation de rang) entre décile et rendement moyen.

    1.0 = parfaitement monotone croissant ; -1.0 = décroissant.
    """
    if decile_stats is None or decile_stats.empty or "mean" not in decile_stats.columns:
        return None
    stats = decile_stats.dropna(subset=["mean"])
    if len(stats) < 2:
        return None
    x = pd.Series(stats.index, dtype=float).rank().to_numpy()
    y = pd.Series(stats["mean"].to_numpy(dtype=float)).rank().to_numpy()
    corr = np.corrcoef(x, y)[0, 1]
    return float(corr) if np.isfinite(corr) else None


def compare_golden(labeled: pd.DataFrame, golden_df: pd.DataFrame) -> dict[str, Any]:
    """Compare les labels Oracle recalculés au golden ``oracle_per_trade.csv``.

    ``labeled`` : trades + colonnes ``oracle_pct_rank`` / ``oracle_decile`` /
    ``oracle_top10`` / ``oracle_bottom10`` (déjà jointes).
    ``golden_df`` : colonnes ``symbol, side, signal_date, horizon, pct_rank,
    decile, universe_size, fwd_ret``.
    """
    golden = golden_df.copy()
    golden["signal_date"] = pd.to_datetime(golden["signal_date"], errors="coerce").dt.normalize()

    merged = pd.merge(
        labeled,
        golden,
        left_on=["symbol", "side", "signal_date"],
        right_on=["symbol", "side", "signal_date"],
        how="inner",
        suffixes=("", "_golden"),
    )
    if merged.empty:
        return {"matched": 0, "max_pct_rank_diff": None, "mean_pct_rank_diff": None,
                "decile_match_pct": None, "top10_match_pct": None, "bottom10_match_pct": None}

    diff = (merged["oracle_pct_rank"] - merged["pct_rank"]).abs()
    dec_match = (merged["oracle_decile"].astype(int) == merged["decile"].astype(int)).mean() * 100.0
    golden_top10 = (merged["pct_rank"] >= 0.90).astype(int)
    golden_bottom10 = (merged["pct_rank"] <= 0.10).astype(int)
    top10_match = (merged["oracle_top10"].astype(int) == golden_top10).mean() * 100.0
    bottom10_match = (merged["oracle_bottom10"].astype(int) == golden_bottom10).mean() * 100.0

    return {
        "matched": int(len(merged)),
        "max_pct_rank_diff": float(diff.max()),
        "mean_pct_rank_diff": float(diff.mean()),
        "decile_match_pct": float(dec_match),
        "top10_match_pct": float(top10_match),
        "bottom10_match_pct": float(bottom10_match),
    }


def audit_run(
    engine: Any,
    run_dir: Path | str,
    batch_id: str,
    horizon: int = 20,
) -> dict[str, Any]:
    """Audit complet d'un run de backtest depuis ``global_oracle_labels``."""
    run_dir = Path(run_dir)
    trades = load_trades(run_dir / "trades.csv")
    if trades.empty:
        return {"status": "error", "reason": "no_trades"}

    start = trades["signal_date"].min()
    end = trades["signal_date"].max()
    oracle = load_oracle_labels(engine, batch_id, horizon, start=start.date(), end=end.date())
    if oracle.empty:
        return {"status": "error", "reason": "no_oracle_labels"}

    labeled = attach_oracle_labels(trades, oracle)
    matched = labeled["oracle_top10"].notna().sum()

    capture = compute_capture(labeled)
    decile_stats = compute_decile_returns(oracle)
    monotonicity = decile_monotonicity(decile_stats)
    spread = None
    if not decile_stats.empty and len(decile_stats) >= 2:
        spread = float(decile_stats["mean"].max() - decile_stats["mean"].min())

    golden_path = run_dir / "oracle_per_trade.csv"
    golden_cmp = None
    if golden_path.exists():
        golden_df = pd.read_csv(golden_path)
        golden_df = golden_df[golden_df["horizon"] == horizon]
        golden_cmp = compare_golden(labeled, golden_df)

    return {
        "status": "completed",
        "run_dir": str(run_dir),
        "batch_id": batch_id,
        "horizon": horizon,
        "n_trades": int(len(trades)),
        "n_matched": int(matched),
        "capture": capture,
        "decile_returns": decile_stats.to_dict("index"),
        "decile_monotonicity": monotonicity,
        "decile_spread": spread,
        "golden": golden_cmp,
    }


def format_report(result: dict[str, Any]) -> str:
    """Rapport lisible."""
    lines: list[str] = []
    if result.get("status") != "completed":
        return f"Audit: {result}"

    cap = result["capture"]
    lines.append("=== AUDIT ORACLE (global_oracle_labels) ===")
    lines.append(
        f"trades={result['n_trades']} matched={result['n_matched']} "
        f"(batch={result['batch_id']}, H{result['horizon']})"
    )
    lines.append(
        f"TOP capture  (longs dans top-10 %)   : {cap['top_capture_pct']:.1f}% "
        f"(n={cap['n_long']})  [cible 16.7%]"
    )
    lines.append(
        f"BOTTOM capture (shorts dans bottom-10 %) : {cap['bottom_capture_pct']:.1f}% "
        f"(n={cap['n_short']})  [cible 8.2%]"
    )
    lines.append(f"  déciles longs  D1..D10 : {cap['long_decile_hist']}")
    lines.append(f"  déciles shorts D1..D10 : {cap['short_decile_hist']}")
    lines.append(
        f"  décile médian longs={cap['long_median_decile']} "
        f"shorts={cap['short_median_decile']}"
    )

    dr = result.get("decile_returns") or {}
    if dr:
        lines.append("=== COURBE RENDEMENT/DÉCILE (univers entier) ===")
        lines.append("  D   mean      median    count")
        for dec, row in sorted(dr.items()):
            lines.append(
                f"  {int(dec):>2}  {row['mean']*100:>7.2f}%  {row['median']*100:>7.2f}%  {int(row['count']):>7}"
            )
    lines.append(
        f"monotonicité (Spearman) = {result['decile_monotonicity']}  "
        f"spread D10-D1 = {result['decile_spread']}"
    )

    golden = result.get("golden")
    if golden:
        lines.append("=== COMPARAISON GOLDEN (oracle_per_trade.csv) ===")
        lines.append(f"  matched={golden['matched']}")
        lines.append(
            f"  max|Δpct_rank|={golden['max_pct_rank_diff']:.6f}  "
            f"mean|Δpct_rank|={golden['mean_pct_rank_diff']:.6f}"
        )
        lines.append(
            f"  décile match={golden['decile_match_pct']:.2f}%  "
            f"top10 match={golden['top10_match_pct']:.2f}%  "
            f"bottom10 match={golden['bottom10_match_pct']:.2f}%"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Oracle reproductible (S2).")
    parser.add_argument("--run-id", required=True, help="Id du run de backtest (ex: 20260817_205031_2a2836d1).")
    parser.add_argument("--batch-id", default=None, help="Batch Global Model (défaut : config.yaml → backtest_batch_id).")
    parser.add_argument("--horizon", type=int, default=20)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    run_dir = _RUN_ROOT / args.run_id / "artifacts"
    result = audit_run(get_sqlalchemy_engine(), run_dir, batch_id, horizon=args.horizon)
    print(format_report(result))


if __name__ == "__main__":
    main()
