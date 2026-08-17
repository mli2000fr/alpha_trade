"""modelFactory/oracle/build_labels.py — Pré-calcul des labels Oracle H20 (S1).

Construit la table ``alpha_trade.global_oracle_labels`` (cf. doc/ml_oracle.md §3) :

1. **Univers** = ``global_rank_history`` (batch_id, colonne de rang canonique non
   NULL), **contrôlé bit-for-bit** contre ``model_predictions`` (run synthétique
   ``{batch_id}_globalrank_synth``) — le pool réellement consommé par la cascade.
2. **Prix** = ``stock_bars_daily`` (``adj_close`` sinon ``close``), pivot + ffill
   (même logique que ``scripts/oracle_selection_audit.py``).
3. ``future_return_20 = px[D+20] / px[D] − 1``.
4. Par date : ``oracle_pct_rank`` (fraction de l'univers ≤ rendement, définition
   identique à l'audit), ``oracle_decile``, ``oracle_top10`` / ``oracle_bottom10``
   (TOP/BOTTOM 10 % **cross-sectionnel de l'univers du jour** — jamais de seuil de
   rendement absolu).
5. ``oracle_exit_date = D + H`` ; ``oracle_available_date = exit + offset`` (jours
   ouvrés du calendrier bourse).
6. Upsert **idempotent + chunké** (``ON DUPLICATE KEY UPDATE``).

Usage :
    python -m modelFactory.oracle.build_labels \
        --batch-id model-factory-20260811223551-ef2cd0 \
        --start-date 2016-01-01 --end-date 2025-12-31
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.config import resolve_oracle_batch_id
from modelFactory.oracle.leakage import assert_availability_after_prediction

LOGGER = logging.getLogger(__name__)

_SYNTH_RUN_SUFFIX = "_globalrank_synth"
_MIN_RANK_UNIVERSE = 20   # univers cross-sectionnel minimum pour calculer un rang
_CHUNK = 2000

_COLUMNS = [
    "prediction_date", "symbol", "batch_id", "horizon",
    "future_return", "oracle_pct_rank", "oracle_decile",
    "oracle_top10", "oracle_bottom10", "oracle_exit_date", "oracle_available_date",
]

_UPSERT = text(
    "INSERT INTO alpha_trade.global_oracle_labels "
    "(prediction_date, symbol, batch_id, horizon, future_return, oracle_pct_rank, "
    " oracle_decile, oracle_top10, oracle_bottom10, oracle_exit_date, oracle_available_date) "
    "VALUES (:prediction_date, :symbol, :batch_id, :horizon, :future_return, :oracle_pct_rank, "
    " :oracle_decile, :oracle_top10, :oracle_bottom10, :oracle_exit_date, :oracle_available_date) "
    "ON DUPLICATE KEY UPDATE "
    "future_return=VALUES(future_return), oracle_pct_rank=VALUES(oracle_pct_rank), "
    "oracle_decile=VALUES(oracle_decile), oracle_top10=VALUES(oracle_top10), "
    "oracle_bottom10=VALUES(oracle_bottom10), oracle_exit_date=VALUES(oracle_exit_date), "
    "oracle_available_date=VALUES(oracle_available_date), created_at=CURRENT_TIMESTAMP"
)


def _iso(value: Any) -> str:
    """Normalise une date en chaîne ISO (YYYY-MM-DD) pour comparaison."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)[:10]


def load_universe_from_ranks(
    engine: Any,
    batch_id: str,
    horizon: int,
) -> set[tuple[str, str]]:
    """Univers = couples ``(date_iso, symbol)`` de ``global_rank_history``."""
    rank_col = f"global_rank_{horizon}"
    query = text(
        f"SELECT DISTINCT `date`, symbol FROM global_rank_history "
        f"WHERE batch_id = :bid AND {rank_col} IS NOT NULL"
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"bid": batch_id}).fetchall()
    return {(_iso(d), str(s)) for d, s in rows}


def load_universe_from_predictions(engine: Any, batch_id: str) -> set[tuple[str, str]]:
    """Univers = couples ``(date_iso, symbol)`` du run synthétique ``model_predictions``."""
    run_id = f"{batch_id}{_SYNTH_RUN_SUFFIX}"
    query = text(
        "SELECT DISTINCT prediction_date, symbol FROM model_predictions WHERE run_id = :rid"
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"rid": run_id}).fetchall()
    return {(_iso(d), str(s)) for d, s in rows}


def check_universe_equality(
    rank_keys: Iterable[tuple[str, str]],
    pred_keys: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Contrôle bit-for-bit ``global_rank_history`` ↔ ``model_predictions``.

    Returns:
        dict : ``equal`` + compteurs + échantillons des divergences.
    """
    ranks = set(rank_keys)
    preds = set(pred_keys)
    only_ranks = sorted(ranks - preds)
    only_preds = sorted(preds - ranks)
    return {
        "equal": not only_ranks and not only_preds,
        "n_ranks": len(ranks),
        "n_preds": len(preds),
        "only_in_ranks": len(only_ranks),
        "only_in_preds": len(only_preds),
        "samples_only_ranks": only_ranks[:10],
        "samples_only_preds": only_preds[:10],
    }


def load_close_matrix(engine: Any, symbols: list[str], start_date: str) -> pd.DataFrame:
    """Charge ``stock_bars_daily`` en matrice large (index=date, colonnes=symbol).

    ``px = COALESCE(adj_close, close)``, puis pivot + ``ffill`` — identique à l'audit.
    Évite ``pivot_table`` (trop lent sur ~1 M de lignes) : fetchall + dedup + ``unstack``.
    """
    query = text(
        "SELECT symbol, `date` AS d, CAST(COALESCE(adj_close, close) AS DOUBLE) AS px "
        "FROM stock_bars_daily WHERE symbol IN :syms AND `date` >= :start "
        "ORDER BY d, symbol, data_source"
    ).bindparams(bindparam("syms", expanding=True))
    with engine.connect() as conn:
        rows = conn.execute(query, {"syms": symbols, "start": start_date}).fetchall()
    if not rows:
        return pd.DataFrame()
    bars = pd.DataFrame(rows, columns=["symbol", "d", "px"])
    # MySQL DECIMAL → decimal.Decimal ; conversion explicite en float (sinon
    # `fwd / ref - 1.0` lève TypeError sur les Decimal).
    bars["px"] = pd.to_numeric(bars["px"], errors="coerce")
    bars = bars.drop_duplicates(subset=["d", "symbol"], keep="last")
    close = bars.set_index(["d", "symbol"])["px"].unstack()
    close = close.sort_index().ffill()
    close.index = pd.to_datetime(close.index)
    return close


def compute_cross_sectional_ranks(
    returns: pd.Series,
    top_pct: float = 0.10,
) -> pd.DataFrame:
    """Rangs cross-sectionnels intra-date (définition identique à l'audit §19).

    - ``oracle_pct_rank = fraction de l'univers dont le rendement ≤ celui du titre``
      (équivalent à ``(returns <= returns[sym]).mean()``) ;
    - ``oracle_decile = ceil(pct_rank × 10)`` borné [1, 10] ;
    - ``oracle_top10 = pct_rank >= 1 − top_pct`` ; ``oracle_bottom10 = pct_rank <= top_pct``.

    Les NaN d'entrée sont ignorés (retirés avant le calcul).
    """
    returns = pd.Series(returns, dtype=float).dropna()
    if returns.empty:
        return pd.DataFrame(columns=[
            "oracle_pct_rank", "oracle_decile", "oracle_top10", "oracle_bottom10",
        ])
    n = len(returns)
    pct_rank = returns.rank(method="max", ascending=True) / n
    decile = np.ceil(pct_rank * 10.0).clip(1, 10).astype(int)
    top10 = (pct_rank >= 1.0 - top_pct).astype(int)
    bottom10 = (pct_rank <= top_pct).astype(int)
    return pd.DataFrame({
        "oracle_pct_rank": pct_rank,
        "oracle_decile": decile,
        "oracle_top10": top10,
        "oracle_bottom10": bottom10,
    }, index=returns.index)


def _upsert_rows(engine: Any, rows: list[tuple[Any, ...]]) -> int:
    """Upsert idempotent + chunké dans ``global_oracle_labels``."""
    inserted = 0
    for start in range(0, len(rows), _CHUNK):
        chunk = rows[start:start + _CHUNK]
        params_list = [dict(zip(_COLUMNS, row)) for row in chunk]
        with engine.begin() as conn:
            conn.execute(_UPSERT, params_list)
        inserted += len(params_list)
        if start % (20 * _CHUNK) == 0:
            LOGGER.info("build_labels upsert progress %d/%d", start, len(rows))
    return inserted


def build_labels(
    batch_id: str,
    *,
    horizon: int = 20,
    start_date: str | None = None,
    end_date: str | None = None,
    engine: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Construit et persiste les labels Oracle H20 pour ``batch_id``.

    Returns:
        dict de synthèse (status, batch_id, universe_equal, n_rows, n_labeled, …).
    """
    engine = engine or get_sqlalchemy_engine()

    # ── 1. Univers (bit-for-bit) ──
    rank_keys = load_universe_from_ranks(engine, batch_id, horizon)
    pred_keys = load_universe_from_predictions(engine, batch_id)
    universe_check = check_universe_equality(rank_keys, pred_keys)
    if not universe_check["equal"]:
        LOGGER.error("Univers divergent: %s", universe_check)
        raise RuntimeError(
            "Univers global_rank_history ≠ model_predictions (bit-for-bit) : "
            f"only_in_ranks={universe_check['only_in_ranks']}, "
            f"only_in_preds={universe_check['only_in_preds']}. "
            "Arbitrer la divergence avant de construire les labels Oracle."
        )

    uni_by_day: dict[date, set[str]] = {}
    for d_iso, sym in rank_keys:
        d = date.fromisoformat(d_iso)
        uni_by_day.setdefault(d, set()).add(sym)

    all_dates = sorted(uni_by_day)
    if not all_dates:
        return {"status": "error", "reason": "empty_universe", "universe_check": universe_check}

    if start_date:
        all_dates = [d for d in all_dates if d >= date.fromisoformat(start_date)]
    if end_date:
        all_dates = [d for d in all_dates if d <= date.fromisoformat(end_date)]
    if not all_dates:
        return {"status": "error", "reason": "empty_window", "universe_check": universe_check}

    symbols = sorted({s for _, s in rank_keys})
    close = load_close_matrix(engine, symbols, all_dates[0].isoformat())
    if close.empty:
        return {"status": "error", "reason": "no_bars", "universe_check": universe_check}

    # ── 2. Boucle par date (vectorisée) ──
    rows: list[tuple[Any, ...]] = []
    n_labeled = 0
    n_unavailable = 0
    skipped_dates = 0

    for d in all_dates:
        ts = pd.Timestamp(d)
        pos = close.index.get_indexer([ts])[0]
        if pos < 0:
            skipped_dates += 1
            continue
        exit_pos = pos + horizon
        if exit_pos >= len(close):
            continue  # fenêtre future incomplète → rien à stocker (queue de la série)

        ref = close.iloc[pos]
        fwd = close.iloc[exit_pos]
        full_ret = (fwd / ref - 1.0).replace([np.inf, -np.inf], np.nan)
        uni_syms = sorted(uni_by_day[d])
        day_ret = full_ret.reindex(uni_syms)  # conserve l'ordre + NaN
        finite_ret = day_ret.dropna()

        if len(finite_ret) >= _MIN_RANK_UNIVERSE:
            ranked = compute_cross_sectional_ranks(finite_ret, top_pct=0.10)
            pct_s = ranked["oracle_pct_rank"].reindex(uni_syms)
            dec_s = ranked["oracle_decile"].reindex(uni_syms)
            top_s = ranked["oracle_top10"].reindex(uni_syms)
            bot_s = ranked["oracle_bottom10"].reindex(uni_syms)
        else:
            pct_s = pd.Series(np.nan, index=uni_syms, dtype=float)
            dec_s = pd.Series(np.nan, index=uni_syms, dtype=float)
            top_s = pd.Series(np.nan, index=uni_syms, dtype=float)
            bot_s = pd.Series(np.nan, index=uni_syms, dtype=float)

        exit_date = close.index[exit_pos].date()
        avail_pos = exit_pos + 1
        available_date = close.index[avail_pos].date() if avail_pos < len(close) else None

        rets = day_ret.to_numpy(dtype=float)
        pcts = pct_s.to_numpy(dtype=float)
        decs = dec_s.to_numpy(dtype=float)
        tops = top_s.to_numpy(dtype=float)
        bots = bot_s.to_numpy(dtype=float)

        for i, sym in enumerate(uni_syms):
            fr = rets[i]
            if np.isfinite(fr) and np.isfinite(pcts[i]):
                rows.append((
                    d, sym, batch_id, horizon, float(fr),
                    float(pcts[i]), int(decs[i]), int(tops[i]), int(bots[i]),
                    exit_date, available_date,
                ))
                n_labeled += 1
            else:
                rows.append((
                    d, sym, batch_id, horizon,
                    float(fr) if np.isfinite(fr) else None,
                    None, None, None, None,
                    exit_date, available_date,
                ))
                n_unavailable += 1

    labels_df = pd.DataFrame(rows, columns=_COLUMNS)
    if not labels_df.empty:
        # ── T1 sur données réelles (bloquant) ──
        assert_availability_after_prediction(labels_df)

    if dry_run:
        return {
            "status": "dry_run", "batch_id": batch_id, "horizon": horizon,
            "universe_check": universe_check, "n_rows": len(labels_df),
            "n_labeled": n_labeled, "n_unavailable": n_unavailable,
            "skipped_dates": skipped_dates, "n_symbols": len(symbols),
        }

    inserted = _upsert_rows(engine, rows) if rows else 0
    LOGGER.info(
        "build_labels done batch_id=%s rows=%d labeled=%d unavailable=%d skipped_dates=%d",
        batch_id, inserted, n_labeled, n_unavailable, skipped_dates,
    )
    return {
        "status": "completed", "batch_id": batch_id, "horizon": horizon,
        "universe_check": universe_check, "n_rows": inserted,
        "n_labeled": n_labeled, "n_unavailable": n_unavailable,
        "skipped_dates": skipped_dates, "n_symbols": len(symbols),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Construit les labels Oracle H20 (S1).")
    parser.add_argument("--batch-id", default=None,
                        help="Batch Global Model (défaut : config.yaml → backtest_batch_id).")
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD inclus.")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD inclus.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule sans écrire en base (diagnostic).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    batch_id = args.batch_id or resolve_oracle_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu (config.yaml → batch_diagnostics.backtest_batch_id).")

    result = build_labels(
        batch_id,
        horizon=args.horizon,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
    )
    print(result)


if __name__ == "__main__":
    main()
