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


def synthesize(batch_id: str, best_h: int, *, top_pct: float = 0.10,
               dip_config: dict | None = None) -> dict:
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

    # ── Persistent Rank DIP filter (LIVE — config prod_*) ──
    # Appliqué à la branche LONG uniquement : un top-rank n'est marqué `long`
    # que s'il passe la persistance N + la baisse X. Sinon → `flat` (exclu du
    # risk/execution live). Même logique que selector/dip_filter.py (cascade
    # backtest), mais ici au point de PERSISTANCE des prédictions (live).
    dip_long: set[tuple[str, str]] | None = None
    _dip_n = 0
    _dip_threshold = 0.90
    _dip_pct = 0.02
    if dip_config and bool(dip_config.get("enabled", False)):
        _dip_n = int(dip_config.get("persist_days", 4) or 4)
        _dip_threshold = float(dip_config.get("rank_threshold", 0.90) or 0.90)
        _dip_pct = float(dip_config.get("dip_pct", 0.02) or 0.02)
        # PRUDENCE : reclaim_ratio n'est PAS supporté par le chemin live
        # (_build_dip_long_set = D0 direct vectorisé). Si activé en prod, le
        # backtest (selector/dip_filter.filter_day_candidates) appliquerait le
        # reclaim mais le live pas → divergence. On le refuse ici explicitement.
        _dip_reclaim = dip_config.get("reclaim_ratio")
        if _dip_reclaim:
            LOGGER.warning(
                "synthesize DIP filter (prod): reclaim_ratio=%s NON supporté live "
                "(D0 direct uniquement) — reclaim ignoré. Activez-le uniquement en backtest.",
                _dip_reclaim,
            )
        dip_long = _build_dip_long_set(
            engine, batch_id, rank_col,
            n=_dip_n, threshold=_dip_threshold, dip_pct=_dip_pct,
        )
        LOGGER.info(
            "synthesize DIP filter (prod): N=%d X=%.2f rank>=%.2f — %d (symbol,date) passent",
            _dip_n, _dip_pct, _dip_threshold, len(dip_long or set()),
        )

    inserted = 0
    _dip_trace = {"long_brut": 0, "long_retenu": 0, "long_filtre": 0}
    for i in range(0, len(rows), _CHUNK):
        chunk = rows[i:i + _CHUNK]
        params_list = []
        for symbol, d, rank in chunk:
            rank = float(rank)
            if rank >= 1.0 - top_pct:
                side = "long"
                _dip_trace["long_brut"] += 1
                # DIP filter live : persistance + baisse sinon flat
                if dip_long is not None and (str(symbol), str(d)) not in dip_long:
                    side = "flat"
                    _dip_trace["long_filtre"] += 1
                else:
                    _dip_trace["long_retenu"] += 1
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

    # Log de passage sur la règle DIP live (vérifiable dans les logs prod).
    LOGGER.info(
        "DIP_FILTER prod run_id=%s long_brut=%d long_retenu=%d long_filtre=%d",
        run_id, _dip_trace["long_brut"], _dip_trace["long_retenu"], _dip_trace["long_filtre"],
    )
    LOGGER.info("synthesize done run_id=%s rows=%d", run_id, inserted)
    return {"status": "completed", "run_id": run_id, "inserted": inserted}


def _build_dip_long_set(
    engine,
    batch_id: str,
    rank_col: str,
    *,
    n: int = 4,
    threshold: float = 0.90,
    dip_pct: float = 0.02,
) -> set[tuple[str, str]]:
    """Construit l'ensemble {(symbol, date)} qui passe la persistance + dip.

    PIT : le DIP à J utilise les rangs J..J-(n-1) (persistance) et le prix
    close[J] vs close[J-n] (baisse). Rejoue la logique de selector/dip_filter.
    """
    import pandas as pd
    with engine.connect() as conn:
        ranks = pd.read_sql(
            text(
                f"SELECT symbol, `date`, {rank_col} AS rank_val "
                f"FROM alpha_trade.global_rank_history "
                f"WHERE batch_id = :bid AND {rank_col} IS NOT NULL ORDER BY symbol, `date`"
            ),
            conn, params={"bid": batch_id},
        )
        prices = pd.read_sql(
            text(
                "SELECT symbol, `date`, close FROM alpha_trade.stock_bars_daily "
                "ORDER BY symbol, `date`"
            ),
            conn,
        )
    if ranks.empty or prices.empty:
        return set()
    ranks["date"] = pd.to_datetime(ranks["date"]).dt.normalize()
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    ranks["symbol"] = ranks["symbol"].astype(str).str.upper()
    prices["symbol"] = prices["symbol"].astype(str).str.upper()

    # Persistance : min des rangs sur les n dernières séances (par symbole)
    ranks["_rank_ok"] = (ranks["rank_val"] >= threshold).astype(int)
    ranks["_persist"] = ranks.groupby("symbol")["_rank_ok"].transform(
        lambda x: x.rolling(n, min_periods=n).min())
    # Prix : close[J] / close[J-n] - 1
    prices["_ret_n"] = prices.groupby("symbol")["close"].transform(
        lambda x: x / x.shift(n) - 1.0)

    m = ranks.merge(prices[["symbol", "date", "_ret_n"]], on=["symbol", "date"], how="left")
    # Condition prix selon le SIGNE de dip_pct — même convention que
    # selector/dip_filter._dip_pass : >0 = baisse >= X (DIP) ; <0 = hausse >= |X|.
    _thr = -float(dip_pct)
    if float(dip_pct) >= 0:
        passed = m[(m["_persist"] == 1) & (m["_ret_n"].notna()) & (m["_ret_n"] <= _thr)]
    else:
        passed = m[(m["_persist"] == 1) & (m["_ret_n"].notna()) & (m["_ret_n"] >= _thr)]
    return {(str(r["symbol"]), str(pd.Timestamp(r["date"]).date())) for _, r in passed.iterrows()}


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
    parser.add_argument("--no-dip-filter", action="store_true",
                        help="Désactive le filtre DIP live même si persistent_dip_filter_long.prod_enabled=true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Config DIP live (clés prod_*) — chargée depuis config.yaml.
    dip_config = None
    if not args.no_dip_filter:
        try:
            from selector.dip_filter import load_dip_filter_config
            dip_config = load_dip_filter_config("prod")
            LOGGER.info("synthesize DIP config (prod): %s", dip_config)
        except Exception:
            LOGGER.exception("synthesize DIP config indisponible — DIP désactivé")
            dip_config = None

    if args.apply_liquidity_filter:
        print(neutralize_illiquid(args.batch_id, end_date=args.filter_end_date))
    else:
        print(synthesize(args.batch_id, args.best_h, top_pct=args.top_pct, dip_config=dip_config))


if __name__ == "__main__":
    main()
