"""Phase 7.7 — Shadow compare **offline** (audit_global §7.7).

Compare deux runs (live vs simulé) déjà persistés et calcule un rapport de
drift symboles / quantités / prix / convictions. Le mode shadow **live
continu** (boucle parallèle) reste backlog Long terme : cf.
``prompt/refactor/backlog_long_terme.md``.

API minimale, indépendante de la DB : la fonction principale travaille sur
deux DataFrames d'orders (un par run). Le câblage CLI / repository est laissé
à un futur sprint (l'intérêt principal Phase 7 est d'avoir l'algorithme de
diff testable et la table de persistance prête).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowDriftReport:
    live_run_id: str
    simulated_run_id: str
    symbols_only_in_live: list[str] = field(default_factory=list)
    symbols_only_in_sim: list[str] = field(default_factory=list)
    avg_qty_drift_pct: float | None = None
    avg_price_drift_pct: float | None = None
    avg_conviction_drift: float | None = None
    per_symbol: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "live_run_id": self.live_run_id,
            "simulated_run_id": self.simulated_run_id,
            "symbols_only_in_live": self.symbols_only_in_live,
            "symbols_only_in_sim": self.symbols_only_in_sim,
            "avg_qty_drift_pct": self.avg_qty_drift_pct,
            "avg_price_drift_pct": self.avg_price_drift_pct,
            "avg_conviction_drift": self.avg_conviction_drift,
            "per_symbol": self.per_symbol,
            "schema_version": 1,
        }


def compare_runs(
    live_orders: pd.DataFrame,
    simulated_orders: pd.DataFrame,
    *,
    live_run_id: str,
    simulated_run_id: str,
    qty_col: str = "qty",
    price_col: str = "price",
    conviction_col: str = "conviction",
    symbol_col: str = "symbol",
) -> ShadowDriftReport:
    """Diffe deux ensembles d'orders et retourne un rapport agrégé.

    Hypothèses :
    - Les colonnes ``qty_col``, ``price_col``, ``conviction_col`` sont
      optionnelles ; les drifts associés sont ``None`` si absents.
    - Une ligne = un order par symbole. En cas de doublons, l'agrégation est
      ``sum`` pour qty, ``mean`` pour price/conviction.
    """
    live = _normalize(live_orders, symbol_col, qty_col, price_col, conviction_col)
    sim = _normalize(simulated_orders, symbol_col, qty_col, price_col, conviction_col)

    live_syms = set(live.index)
    sim_syms = set(sim.index)
    only_live = sorted(live_syms - sim_syms)
    only_sim = sorted(sim_syms - live_syms)
    common = sorted(live_syms & sim_syms)

    qty_drifts: list[float] = []
    price_drifts: list[float] = []
    conv_drifts: list[float] = []
    per_symbol: list[dict[str, Any]] = []

    for sym in common:
        live_row = live.loc[sym]
        sim_row = sim.loc[sym]
        entry: dict[str, Any] = {"symbol": sym}
        if not np.isnan(live_row.get(qty_col, np.nan)) and not np.isnan(sim_row.get(qty_col, np.nan)):
            denom = max(abs(sim_row[qty_col]), 1e-9)
            d = (live_row[qty_col] - sim_row[qty_col]) / denom
            qty_drifts.append(d)
            entry["qty_drift_pct"] = float(d)
        if not np.isnan(live_row.get(price_col, np.nan)) and not np.isnan(sim_row.get(price_col, np.nan)):
            denom = max(abs(sim_row[price_col]), 1e-9)
            d = (live_row[price_col] - sim_row[price_col]) / denom
            price_drifts.append(d)
            entry["price_drift_pct"] = float(d)
        if not np.isnan(live_row.get(conviction_col, np.nan)) and not np.isnan(sim_row.get(conviction_col, np.nan)):
            d = float(live_row[conviction_col] - sim_row[conviction_col])
            conv_drifts.append(d)
            entry["conviction_drift"] = d
        per_symbol.append(entry)

    return ShadowDriftReport(
        live_run_id=live_run_id,
        simulated_run_id=simulated_run_id,
        symbols_only_in_live=only_live,
        symbols_only_in_sim=only_sim,
        avg_qty_drift_pct=float(np.mean(qty_drifts)) if qty_drifts else None,
        avg_price_drift_pct=float(np.mean(price_drifts)) if price_drifts else None,
        avg_conviction_drift=float(np.mean(conv_drifts)) if conv_drifts else None,
        per_symbol=per_symbol,
    )


def _normalize(
    df: pd.DataFrame,
    symbol_col: str,
    qty_col: str,
    price_col: str,
    conviction_col: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[qty_col, price_col, conviction_col]).rename_axis(symbol_col)
    work = df.copy()
    if symbol_col not in work.columns:
        raise ValueError(f"Colonne '{symbol_col}' manquante dans le DataFrame d'orders.")
    aggs: dict[str, str] = {}
    if qty_col in work.columns:
        aggs[qty_col] = "sum"
    if price_col in work.columns:
        aggs[price_col] = "mean"
    if conviction_col in work.columns:
        aggs[conviction_col] = "mean"
    if aggs:
        work = work.groupby(symbol_col, as_index=True).agg(aggs)
    else:
        work = work.set_index(symbol_col)
    return work


def persist_shadow_run(report: ShadowDriftReport, *, engine: Any, run_id: str | None = None) -> str:
    """Insère ``report`` dans ``shadow_drift_runs``."""
    from sqlalchemy import text

    rid = run_id or f"shd-{uuid.uuid4().hex[:12]}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO shadow_drift_runs
                    (run_id, compared_at, live_run_id, simulated_run_id,
                     symbols_only_in_live, symbols_only_in_sim,
                     avg_qty_drift_pct, avg_price_drift_pct, avg_conviction_drift,
                     payload, schema_version)
                VALUES
                    (:run_id, :compared_at, :live, :sim,
                     :only_live, :only_sim,
                     :qty, :price, :conv,
                     :payload, :schema_version)
                """
            ),
            {
                "run_id": rid,
                "compared_at": datetime.utcnow(),
                "live": report.live_run_id,
                "sim": report.simulated_run_id,
                "only_live": json.dumps(report.symbols_only_in_live),
                "only_sim": json.dumps(report.symbols_only_in_sim),
                "qty": report.avg_qty_drift_pct,
                "price": report.avg_price_drift_pct,
                "conv": report.avg_conviction_drift,
                "payload": json.dumps(report.to_payload()),
                "schema_version": 1,
            },
        )
    return rid


__all__ = ["ShadowDriftReport", "compare_runs", "persist_shadow_run"]

