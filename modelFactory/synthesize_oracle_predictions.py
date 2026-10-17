"""modelFactory/synthesize_oracle_predictions.py — Synchro Oracle Extreme → model_predictions.

Même logique que ``synthesize_global_rank_predictions.py`` : après une prédiction
Oracle Extreme (persistée dans ``oracle_extreme_predictions``), on synchronise les
``proba_extreme`` dans ``model_predictions`` (format per-symbol standard) via un
run synthétique, pour que :
  - la couverture ML du backtest pipeline (lue depuis ``model_predictions``) soit
    satisfaite pour un batch oracle-only (ex. b58b60) ;
  - le pipeline puisse consommer le signal Oracle comme univers per-symbol
    (mode cascade ``extreme_gate`` / ``oracle``).

Mapping (fidèle au composant Extreme Gate E6-E13, LONG-only top ``pool_pct``) :
  percentile intra-date de ``proba_extreme`` >= 1 - pool_pct  → side="long"
  sinon                                                        → side="flat"
  proba_long = proba_extreme (brut) ; proba_short = 0 ; proba_flat = 0.

Usage :
    python -m modelFactory.synthesize_oracle_predictions \\
        --batch-id model-factory-20260827233359-b58b60 \\
        [--pool-pct 0.20] [--start 2026-01-01] [--end 2026-05-29]
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.synthetic_prediction_run import ensure_synthetic_run

LOGGER = logging.getLogger(__name__)

_SYNTH_RUN_SUFFIX = "_oracle_synth"

_INSERT_PRED = text(
    "INSERT INTO alpha_trade.model_predictions "
    "(symbol, prediction_date, predicted_proba, predicted_class, run_id, "
    " selected_model, decision_threshold, signal_label, calibration_method, "
    " predicted_side, proba_long, proba_flat, proba_short, source) "
    "VALUES (:symbol, :prediction_date, :predicted_proba, :predicted_class, :run_id, "
    " :selected_model, :decision_threshold, :signal_label, :calibration_method, "
    " :predicted_side, :proba_long, :proba_flat, :proba_short, :source) "
    "ON DUPLICATE KEY UPDATE "
    "predicted_proba=VALUES(predicted_proba), predicted_class=VALUES(predicted_class), "
    "predicted_side=VALUES(predicted_side), proba_long=VALUES(proba_long), "
    "proba_flat=VALUES(proba_flat), proba_short=VALUES(proba_short), "
    "source=VALUES(source)"
)

_CHUNK = 2000


def synthesize(
    batch_id: str,
    *,
    pool_pct: float = 0.20,
    start: str | None = None,
    end: str | None = None,
    artifacts_dir: str = "artifacts/models",
) -> dict:
    """Synchronise les prédictions Oracle Extreme du batch dans model_predictions.

    Retourne ``{"status", "run_id", "inserted", "long_count", "flat_count"}``.
    """
    engine = get_sqlalchemy_engine()
    from modelFactory.oracle_path.train import is_path_batch
    path_mode = is_path_batch(artifacts_dir, batch_id)
    path_policy = None
    if path_mode:
        from common.config_loader import load_config
        from modelFactory.oracle_path.predict import load_contract
        load_contract(artifacts_dir, batch_id)
        path_policy = str((load_config().get("oracle_path") or {}).get("direction_policy", "abstain"))
        if path_policy not in ("long_only", "abstain"):
            raise ValueError("oracle_path.direction_policy : long_only ou abstain requis")
    run_id = f"{batch_id}{_SYNTH_RUN_SUFFIX}"

    # 2. Lecture des prédictions Oracle Extreme (table, filtre batch strict)
    _where = "batch_id = :batch_id"
    _params: dict = {"batch_id": batch_id}
    if start:
        _where += " AND prediction_date >= :start"
        _params["start"] = start
    if end:
        _where += " AND prediction_date <= :end"
        _params["end"] = end
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                f"SELECT prediction_date, symbol, proba_extreme "
                f"FROM alpha_trade.oracle_extreme_predictions "
                f"WHERE {_where} ORDER BY prediction_date, symbol"
            ), conn, params=_params,
        )
    if path_mode:
        # Read through the strict lineage contract before publishing a policy.
        from modelFactory.oracle.predictions_store import load_oracle_predictions
        checked = load_oracle_predictions(engine, batch_id=batch_id, start_date=start, end_date=end,
            artifacts_dir=artifacts_dir)
        df = checked.rename(columns={"date": "prediction_date"})
    if df.empty:
        return {"status": "error", "reason": "no rows in oracle_extreme_predictions", "run_id": run_id}
    ensure_synthetic_run(engine, batch_id=batch_id, run_id=run_id, symbol="__ORACLE_SYNTH__")

    # 3. Mapping fidèle Extreme Gate : percentile intra-date (PIT) >= 1-pool_pct → LONG
    df["_date"] = df["prediction_date"].astype(str).str[:10]
    df["_pct"] = df.groupby("_date")["proba_extreme"].rank(pct=True)
    if not 0 < pool_pct <= 1:
        raise ValueError("pool_pct doit appartenir à ]0,1]")
    df["side"] = df["_pct"].apply(lambda p: "long" if p >= (1.0 - pool_pct) else "flat")
    if path_policy == "abstain":
        df["side"] = "flat"
    elif path_policy == "long_only":
        # The Oracle/ATR/tradable gate owns the TOP pool. Mark every observed
        # row as a possible LONG policy input so a later tradable subset does
        # not lose candidates due to a different percentile denominator.
        df["side"] = "long"
    df["predicted_class"] = df["side"].apply(lambda s: 1 if s == "long" else 0)
    long_count = int((df["side"] == "long").sum())
    flat_count = int((df["side"] == "flat").sum())

    # 4. Upsert dans model_predictions (idempotent par (symbol, date, run_id))
    inserted = 0
    rows = df[["symbol", "prediction_date", "proba_extreme", "side", "predicted_class", "_pct"]].itertuples(index=False, name=None)
    params_list = [
        {
            "symbol": str(symbol).upper(),
            "prediction_date": str(d)[:10],
            "predicted_proba": float(percentile) if path_mode and side == "long" else (0.0 if path_mode else float(p)),
            "predicted_class": int(c),
            "run_id": run_id,
            "selected_model": "oracle_path_long_policy" if path_mode else "oracle_extreme_synth",
            "decision_threshold": 0.5,
            "signal_label": "path_amplitude_long_policy" if path_mode else "oracle_extreme",
            "calibration_method": "rank_policy" if path_mode else "none",
            "predicted_side": side,
            "proba_long": (float(percentile) if side == "long" else 0.0) if path_mode else float(p),
            "proba_flat": (1.0 if side == "flat" else 0.0) if path_mode else 0.0,
            "proba_short": 0.0,
            "source": "oracle_path_policy" if path_mode else "oracle_synth",
        }
        for symbol, d, p, side, c, percentile in rows
    ]
    for i in range(0, len(params_list), _CHUNK):
        with engine.begin() as conn:
            conn.execute(_INSERT_PRED, params_list[i:i + _CHUNK])
        inserted += len(params_list[i:i + _CHUNK])
        LOGGER.info("oracle synth progress %d/%d", inserted, len(params_list))

    LOGGER.info(
        "oracle→model_predictions done run_id=%s rows=%d long=%d flat=%d",
        run_id, inserted, long_count, flat_count,
    )
    return {
        "status": "completed",
        "run_id": run_id,
        "inserted": inserted,
        "long_count": long_count,
        "flat_count": flat_count,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s -- %(message)s")
    parser = argparse.ArgumentParser(description="Synchro Oracle Extreme → model_predictions")
    parser.add_argument("--batch-id", required=True, help="Batch Oracle Extreme (oracle_extreme_predictions).")
    parser.add_argument("--pool-pct", type=float, default=0.20, help="Top fraction LONG par proba_extreme (défaut 0.20).")
    parser.add_argument("--start", type=str, default=None, help="Borne début (YYYY-MM-DD, optionnel).")
    parser.add_argument("--end", type=str, default=None, help="Borne fin (YYYY-MM-DD, optionnel).")
    args = parser.parse_args()
    result = synthesize(
        args.batch_id,
        pool_pct=float(args.pool_pct),
        start=args.start,
        end=args.end,
    )
    print(result)


if __name__ == "__main__":
    main()
