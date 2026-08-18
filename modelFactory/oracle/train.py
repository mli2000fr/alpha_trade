"""modelFactory/oracle/train.py — Oracle TOP Model + ablations O0/O1/O2 (S3).

Entraîne un classifieur binaire ``P(vrai TOP 10 % | info à D)`` (second signal
au-dessus de B25) et compare 3 ablations de features (spec §7) :

- ``O0`` = features B25 (expert + xs_ranks), sans ``global_rank_20`` ;
- ``O1`` = O0 + ``global_rank_20`` + features Oracle spécialisées ;
- ``O2`` = familles réduites (momentum / volume / volatility / market regime).

Usage :
    python -m modelFactory.oracle.train --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.dataset import (
    TARGET_COL,
    ablation_features,
    build_dataset,
    split_dataset,
)

LOGGER = logging.getLogger(__name__)

_ABLATIONS: dict[str, dict[str, Any]] = {
    "O0": {"include_global_rank": False, "include_oracle_extras": False, "lean": False},
    "O1": {"include_global_rank": True, "include_oracle_extras": True, "lean": False},
    "O2": {"include_global_rank": False, "include_oracle_extras": False, "lean": True},
}


def get_universe_symbols(engine: Any, batch_id: str, horizon: int) -> list[str]:
    """Symboles de l'univers Oracle (distinct depuis global_oracle_labels)."""
    query = text(
        "SELECT DISTINCT symbol FROM global_oracle_labels "
        "WHERE batch_id = :bid AND horizon = :h ORDER BY symbol"
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"bid": batch_id, "h": horizon}).scalars().all()
    return [str(s) for s in rows]


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """AUC (Mann-Whitney) sans dépendance scikit-learn."""
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(y_score, dtype=float)
    mask = np.isfinite(s)
    y, s = y[mask], s[mask]
    pos = y == 1.0
    neg = y == 0.0
    if pos.sum() == 0 or neg.sum() == 0:
        return None
    ranks = pd.Series(s).rank(method="average").to_numpy()
    r_pos = ranks[pos].sum()
    auc = (r_pos - pos.sum() * (pos.sum() + 1) / 2.0) / (pos.sum() * neg.sum())
    return float(auc)


def precision_recall_at_top_pct(
    df: pd.DataFrame,
    score_col: str,
    pct: float = 0.10,
    min_universe: int = 20,
) -> dict[str, float | None]:
    """Précision/rappel cross-sectionnel du TOP pct (par date, moyenné)."""
    rows: list[dict[str, float]] = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, TARGET_COL])
        if len(g) < min_universe:
            continue
        n_top = max(1, int(np.ceil(len(g) * pct)))
        top = g.nlargest(n_top, score_col)
        prec = float(top[TARGET_COL].mean())
        n_actual = int(g[TARGET_COL].sum())
        recall = float(top[TARGET_COL].sum() / n_actual) if n_actual > 0 else None
        rows.append({"precision": prec, "recall": recall})
    if not rows:
        return {"precision": None, "recall": None, "n_dates": 0}
    frame = pd.DataFrame(rows)
    return {
        "precision": float(frame["precision"].mean()),
        "recall": float(frame["recall"].mean()),
        "n_dates": int(len(frame)),
    }


def decile_monotonicity(df: pd.DataFrame, score_col: str) -> tuple[float | None, pd.DataFrame]:
    """Déciles cross-sectionnels du score → mean future_return → Spearman."""
    sub = df.dropna(subset=[score_col, "future_return"]).copy()
    if sub.empty:
        return None, pd.DataFrame()
    sub["_dec"] = np.floor(sub.groupby("date")[score_col].rank(pct=True).clip(upper=1 - 1e-9) * 10).clip(0, 9).astype(int) + 1
    stats = sub.groupby("_dec")["future_return"].agg(mean="mean", median="median", count="count")
    if len(stats) < 2:
        return None, stats
    x = pd.Series(stats.index, dtype=float).rank().to_numpy()
    y = pd.Series(stats["mean"].to_numpy(dtype=float)).rank().to_numpy()
    corr = np.corrcoef(x, y)[0, 1]
    return float(corr) if np.isfinite(corr) else None, stats


def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    num_boost_round: int = 400,
) -> Any:
    """Classifieur binaire LightGBM avec early stopping (validation)."""
    import lightgbm as lgb

    scale_pos_weight = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))
    params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "scale_pos_weight": scale_pos_weight,
        "seed": 42,
    }
    dtrain = lgb.Dataset(X_train, label=y_train)
    dvalid = lgb.Dataset(X_valid, label=y_valid, reference=dtrain)
    model = lgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(20, verbose=False)],
    )
    return model


def evaluate_model(model: Any, valid_df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    """Métriques ML : capture (précision/rappel), AUC, monotonicité, importance."""
    proba = model.predict(valid_df[feature_cols].astype(float))
    valid = valid_df.copy()
    valid["_proba"] = proba

    pr = precision_recall_at_top_pct(valid, "_proba")
    auc = roc_auc(valid[TARGET_COL].to_numpy(), proba)
    mono, stats = decile_monotonicity(valid, "_proba")
    importance = model.feature_importance("gain")
    top_features = sorted(
        zip(feature_cols, importance), key=lambda t: t[1], reverse=True,
    )[:15]

    return {
        "precision_at_10pct": pr["precision"],
        "recall_at_10pct": pr["recall"],
        "n_dates": pr["n_dates"],
        "auc": auc,
        "decile_monotonicity": mono,
        "decile_stats": stats.to_dict("index") if not stats.empty else {},
        "top_features": [(f, round(g, 1)) for f, g in top_features],
    }


def run_ablation(
    batch_id: str,
    *,
    horizon: int = 20,
    start_date: str = "2020-01-01",
    end_date: str = "2026-05-29",
    train_cutoff: str = "2024-06-30",
    valid_start: str = "2025-01-01",
    n_symbols: int | None = None,
) -> dict[str, Any]:
    """Construit le dataset, entraîne et évalue O0/O1/O2 + baseline global_rank_20."""
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, batch_id, horizon)
    if n_symbols:
        symbols = symbols[:n_symbols]
    if not symbols:
        return {"status": "error", "reason": "no_universe"}

    dataset, feature_columns = build_dataset(
        engine, batch_id, symbols, start_date=start_date, end_date=end_date, horizon=horizon,
    )
    if dataset.empty:
        return {"status": "error", "reason": "empty_dataset"}

    train, valid = split_dataset(dataset, train_cutoff=train_cutoff, valid_start=valid_start)
    LOGGER.info("dataset rows=%d train=%d valid=%d features=%d symbols=%d",
                len(dataset), len(train), len(valid), len(feature_columns), len(symbols))

    # Baseline = bande top-10 % par global_rank_20 (proxy B25).
    baseline = precision_recall_at_top_pct(valid, "global_rank_20")

    report: dict[str, Any] = {"baseline_global_rank20": baseline}
    for name, cfg in _ABLATIONS.items():
        cols = [c for c in ablation_features(feature_columns, **cfg) if c in dataset.columns]
        LOGGER.info("ablation %s: %d features", name, len(cols))
        X_train = train[cols].astype(float)
        y_train = train[TARGET_COL].astype(int)
        X_valid = valid[cols].astype(float)
        y_valid = valid[TARGET_COL].astype(int)
        if len(X_train) == 0 or len(X_valid) == 0 or y_train.nunique() < 2:
            report[name] = {"error": "empty_or_constant_target"}
            continue
        model = train_lightgbm(X_train, y_train, X_valid, y_valid)
        report[name] = evaluate_model(model, valid, cols)
    return report


def format_report(report: dict[str, Any]) -> str:
    """Rapport lisible."""
    lines = ["=== ORACLE TOP MODEL — ablations O0/O1/O2 ==="]
    b = report.get("baseline_global_rank20") or {}
    lines.append(
        f"baseline global_rank_20 (top-10% band) : precision={b.get('precision')} "
        f"recall={b.get('recall')} ({b.get('n_dates')} dates)"
    )
    for name in ["O0", "O1", "O2"]:
        r = report.get(name) or {}
        if "error" in r:
            lines.append(f"{name}: {r['error']}")
            continue
        lines.append(
            f"{name}: precision@10%={r.get('precision_at_10pct')} "
            f"recall@10%={r.get('recall_at_10pct')} AUC={r.get('auc')} "
            f"mono={r.get('decile_monotonicity')} (n_dates={r.get('n_dates')})"
        )
        top = r.get("top_features") or []
        lines.append("   top features: " + ", ".join(f"{f}({g})" for f, g in top[:8]))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle TOP Model + ablations (S3).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--train-cutoff", default="2024-06-30")
    parser.add_argument("--valid-start", default="2025-01-01")
    parser.add_argument("--symbols", type=int, default=None, help="Limite le nb de symboles (smoke test).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    report = run_ablation(
        batch_id,
        horizon=args.horizon,
        start_date=args.start_date,
        end_date=args.end_date,
        train_cutoff=args.train_cutoff,
        valid_start=args.valid_start,
        n_symbols=args.symbols,
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
