"""modelFactory/synthesize_global_rank_predictions.py — P1-4 Option A.

Synthétise des prédictions per-symbol dans ``model_predictions`` à partir de
``global_rank_history`` pour rendre la cascade **purement rank-driven**.

Le batch B25 (per_sector) n'a pas de modèles per-symbol. La cascade
(Global Rank × proba per-symbol) exige pourtant des probas par ticker.
On les dérive des rangs eux-mêmes :

    proba_long  = global_rank_{best_h}      (top → score = rank²)
    proba_short = 1 - global_rank_{best_h}  (bottom → score = (1-rank)²)

Monotone dans chaque groupe → l'ordre de sélection de la cascade reste
exactement celui du rang global. Le filtre proba (min_prob 0.10) laisse
passer tous les top/bottom.

Usage :
    python -m modelFactory.synthesize_global_rank_predictions \
        --batch-id model-factory-20260811223551-ef2cd0 --best-h 10
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)

_SYNTH_RUN_SUFFIX = "_globalrank_synth"

_INSERT_PRED = text(
    "INSERT INTO alpha_trade.model_predictions "
    "(symbol, prediction_date, predicted_proba, predicted_class, run_id, "
    " selected_model, decision_threshold, signal_label, calibration_method, "
    " predicted_side, proba_long, proba_flat, proba_short) "
    "VALUES (:symbol, :prediction_date, :predicted_proba, :predicted_class, :run_id, "
    " :selected_model, :decision_threshold, :signal_label, :calibration_method, "
    " :predicted_side, :proba_long, :proba_flat, :proba_short) "
    "ON DUPLICATE KEY UPDATE "
    "predicted_proba=VALUES(predicted_proba), predicted_class=VALUES(predicted_class), "
    "predicted_side=VALUES(predicted_side), proba_long=VALUES(proba_long), "
    "proba_flat=VALUES(proba_flat), proba_short=VALUES(proba_short)"
)

_CHUNK = 2000


def synthesize(batch_id: str, best_h: int, *, top_pct: float = 0.10) -> dict:
    engine = get_sqlalchemy_engine()
    run_id = f"{batch_id}{_SYNTH_RUN_SUFFIX}"
    rank_col = f"global_rank_{best_h}"

    with engine.connect() as conn:
        cols = [r[0] for r in conn.execute(text(
            "SHOW COLUMNS FROM alpha_trade.global_rank_history"
        )).fetchall()]
        if rank_col not in cols:
            return {"status": "error", "reason": f"missing column {rank_col}"}

        # 1. Run synthétique dans model_training_run (pour le JOIN batch_id)
        conn.execute(text(
            "INSERT INTO alpha_trade.model_training_run "
            "(run_id, batch_id, registry_id, symbol, status, started_at, finished_at) "
            "VALUES (:run_id, :batch_id, 0, :symbol, 'completed', :now, :now) "
            "ON DUPLICATE KEY UPDATE batch_id=VALUES(batch_id)"
        ), {"run_id": run_id, "batch_id": batch_id, "symbol": "__GLOBAL_RANK_SYNTH__",
            "now": datetime.now(timezone.utc)})
        conn.commit()

        rows = conn.execute(text(
            f"SELECT symbol, `date`, {rank_col} FROM alpha_trade.global_rank_history "
            f"WHERE batch_id = :batch_id AND {rank_col} IS NOT NULL ORDER BY `date`, symbol"
        ), {"batch_id": batch_id}).fetchall()
    if not rows:
        return {"status": "error", "reason": "no rows in global_rank_history"}

    inserted = 0
    for i in range(0, len(rows), _CHUNK):
        chunk = rows[i:i + _CHUNK]
        params_list = []
        for symbol, d, rank in chunk:
            rank = float(rank)
            if rank >= 1.0 - top_pct:
                side = "long"
                plong, pshort = rank, 1.0 - rank
            elif rank <= top_pct:
                side = "short"
                plong, pshort = rank, 1.0 - rank
            else:
                side = "flat"
                plong, pshort = rank, 1.0 - rank
            params_list.append({
                "symbol": str(symbol),
                "prediction_date": d,
                "predicted_proba": rank,
                "predicted_class": 1 if side == "long" else 0,
                "run_id": run_id,
                "selected_model": "global_ranking_synth",
                "decision_threshold": 0.5,
                "signal_label": "global_rank",
                "calibration_method": "none",
                "predicted_side": side,
                "proba_long": plong,
                "proba_flat": 0.0,
                "proba_short": pshort,
            })
        with engine.begin() as conn:
            for p in params_list:
                conn.execute(_INSERT_PRED, p)
        inserted += len(params_list)
        if i % (10 * _CHUNK) == 0:
            LOGGER.info("synthesize progress %d/%d", i, len(rows))

    LOGGER.info("synthesize done run_id=%s rows=%d", run_id, inserted)
    return {"status": "completed", "run_id": run_id, "inserted": inserted}


def neutralize_illiquid(batch_id: str, *, end_date: str = "2018-12-31") -> dict:
    """P1-4 : neutralise les prédictions synthétiques des symboles illiquides.

    Réutilise EXACTEMENT le filtre liquidité production
    (``modelFactory.liquidity_filter.filter_symbols_by_liquidity``) avec les
    seuils par défaut (spread <= 40 bps, volume 20j >= 500k, cap >= 500M,
    amplitude High-Low <= 5%).

    Les lignes ``model_predictions`` du run synthétique sont mises à
    ``flat`` (probas à 0) — la cascade les rejettera. Aucune autre table
    ni le moteur de backtest ne sont touchés.
    """
    from modelFactory.liquidity_filter import filter_symbols_by_liquidity

    engine = get_sqlalchemy_engine()
    run_id = f"{batch_id}{_SYNTH_RUN_SUFFIX}"

    with engine.connect() as conn:
        sym_rows = conn.execute(text(
            "SELECT DISTINCT symbol FROM alpha_trade.global_rank_history WHERE batch_id = :bid"
        ), {"bid": batch_id}).fetchall()
    symbols = sorted({str(r[0]) for r in sym_rows})
    if not symbols:
        return {"status": "error", "reason": "no symbols in global_rank_history"}

    excluded, diag = filter_symbols_by_liquidity(
        engine,
        symbols,
        end_date=date.fromisoformat(end_date),
    )
    if not excluded:
        return {"status": "completed", "neutralized": 0, "excluded": []}

    # Ne toucher QUE le run synthétique
    for i in range(0, len(excluded), _CHUNK):
        chunk = excluded[i:i + _CHUNK]
        placeholders = ", ".join(f":s{j}" for j in range(len(chunk)))
        with engine.begin() as conn:
            conn.execute(text(
                f"UPDATE alpha_trade.model_predictions "
                f"SET predicted_side = 'flat', predicted_proba = 0.0, predicted_class = 0, "
                f"    proba_long = 0.0, proba_flat = 1.0, proba_short = 0.0 "
                f"WHERE run_id = :run_id AND symbol IN ({placeholders})"
            ), {"run_id": run_id, **{f"s{j}": s for j, s in enumerate(chunk)}})

    LOGGER.info("neutralize_illiquid done run_id=%s excluded=%d", run_id, len(excluded))
    return {"status": "completed", "neutralized": len(excluded), "excluded": excluded}


def main() -> None:
    parser = argparse.ArgumentParser(description="P1-4 : synthétiser les probas per-symbol depuis les rangs globaux.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--best-h", type=int, default=10, help="Meilleur horizon du batch (B25 → 10)")
    parser.add_argument("--top-pct", type=float, default=0.10)
    parser.add_argument("--apply-liquidity-filter", action="store_true",
                        help="Neutralise les symboles illiquides (filtre production) dans le run synthétique")
    parser.add_argument("--filter-end-date", default="2018-12-31",
                        help="Date de snapshot du filtre liquidité (défaut: 2018-12-31, avant le backtest)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.apply_liquidity_filter:
        print(neutralize_illiquid(args.batch_id, end_date=args.filter_end_date))
    else:
        print(synthesize(args.batch_id, args.best_h, top_pct=args.top_pct))


if __name__ == "__main__":
    main()
