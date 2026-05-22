"""
backtesting/analytics.py
=========================
Phase D — analytics avancés post-backtest.

- D1. Comparaison vs benchmark (alpha, beta, IR, capture ratios).
- D2. Attribution sectorielle + monthly returns table.
- D3. HTML interactif (Plotly).
- D4. VaR / CVaR 1d-95%, tail ratio, omega ratio.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sprint S3 / A-006 — Convention canonique : MTM(close) + cumulative(ledger).
# ---------------------------------------------------------------------------


def compute_total_return_with_dividends(
    initial_equity: float,
    final_value_mtm: float,
    dividends_received: float,
) -> dict[str, float]:
    """Retourne ``{mtm_return_pct, dividend_yield_pct, total_return_pct}``.

    Phase 6.1.c / A-006 : applique la convention canonique
    ``MTM(stock_bars_daily.close) + cumulative(portfolio_cash_ledger)``
    (cf. ``README.md:15-16``). ``final_value_mtm`` doit être l'equity
    portefeuille **avant** crédit des dividendes (mark-to-market pur).
    Le ``dividends_received`` provient de
    :func:`backtesting.report.load_dividends_received` qui agrège
    ``portfolio_cash_ledger.entry_type='dividend_credit'``.

    Conformité parité backtest ↔ live : les analytics doivent toujours
    additionner les flux cash dividendes pour correspondre à
    ``broker_account_snapshots.equity`` côté live.
    """
    if initial_equity <= 0:
        return {"mtm_return_pct": 0.0, "dividend_yield_pct": 0.0, "total_return_pct": 0.0}
    initial = float(initial_equity)
    mtm_return_pct = (float(final_value_mtm) / initial - 1.0) * 100.0
    dividend_yield_pct = (float(dividends_received) / initial) * 100.0
    total_return_pct = mtm_return_pct + dividend_yield_pct
    return {
        "mtm_return_pct": mtm_return_pct,
        "dividend_yield_pct": dividend_yield_pct,
        "total_return_pct": total_return_pct,
    }


def compare_total_return_to_oracle(
    *,
    initial_equity: float,
    final_value_mtm: float,
    dividends_received: float,
    oracle_total_return_pct: float,
    tolerance_bps: float = 25.0,
) -> dict[str, float | bool]:
    """Compare le rendement total calculé à un oracle externe.

    ``delta_bps`` est exprimé en points de base de performance totale
    (1 % = 100 bps). ``within_tolerance`` est vrai si l'écart absolu respecte
    la tolérance fournie.
    """
    computed = compute_total_return_with_dividends(
        initial_equity=initial_equity,
        final_value_mtm=final_value_mtm,
        dividends_received=dividends_received,
    )
    oracle_total_return_pct = float(oracle_total_return_pct)
    delta_bps = (float(computed["total_return_pct"]) - oracle_total_return_pct) * 100.0
    return {
        **computed,
        "oracle_total_return_pct": oracle_total_return_pct,
        "delta_bps": delta_bps,
        "tolerance_bps": float(tolerance_bps),
        "within_tolerance": abs(delta_bps) <= float(tolerance_bps),
    }


# ---------------------------------------------------------------------------
# D1 — Benchmark comparison
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BenchmarkAnalytics:
    alpha_annualized_pct: float
    beta: float
    information_ratio: float
    tracking_error_pct: float
    up_capture: float
    down_capture: float
    benchmark_return_pct: float

    def to_dict(self) -> dict[str, float]:
        return {
            "alpha_annualized_pct": float(self.alpha_annualized_pct),
            "beta": float(self.beta),
            "information_ratio": float(self.information_ratio),
            "tracking_error_pct": float(self.tracking_error_pct),
            "up_capture": float(self.up_capture),
            "down_capture": float(self.down_capture),
            "benchmark_return_pct": float(self.benchmark_return_pct),
        }


def compute_benchmark_analytics(
    equity: pd.Series,
    benchmark_close: pd.Series,
    *,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = 252,
) -> BenchmarkAnalytics:
    """Comparaison portfolio vs benchmark (CAPM-like)."""
    if equity.empty or benchmark_close.empty:
        return BenchmarkAnalytics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    aligned = pd.concat(
        [equity.rename("pf"), benchmark_close.rename("bm")],
        axis=1,
    ).dropna()
    if len(aligned) < 5:
        return BenchmarkAnalytics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    pf_ret = aligned["pf"].pct_change().dropna()
    bm_ret = aligned["bm"].pct_change().dropna()
    common = pf_ret.index.intersection(bm_ret.index)
    pf_ret = pf_ret.loc[common]
    bm_ret = bm_ret.loc[common]
    rf_daily = float(risk_free_rate) / float(trading_days_per_year)
    pf_excess = pf_ret - rf_daily
    bm_excess = bm_ret - rf_daily
    var_bm = float(bm_excess.var(ddof=0))
    beta = float((pf_excess.cov(bm_excess)) / var_bm) if var_bm > 0 else 0.0
    alpha_daily = float(pf_excess.mean() - beta * bm_excess.mean())
    alpha_ann = ((1.0 + alpha_daily) ** trading_days_per_year - 1.0) * 100.0
    diff = pf_ret - bm_ret
    te = float(diff.std(ddof=0)) * math.sqrt(trading_days_per_year)
    ir = float(diff.mean() / diff.std(ddof=0)) * math.sqrt(trading_days_per_year) if diff.std(ddof=0) > 0 else 0.0
    up_mask = bm_ret > 0
    down_mask = bm_ret < 0
    up_capture = (
        float(pf_ret[up_mask].mean() / bm_ret[up_mask].mean())
        if up_mask.any() and bm_ret[up_mask].mean() != 0
        else 0.0
    )
    down_capture = (
        float(pf_ret[down_mask].mean() / bm_ret[down_mask].mean())
        if down_mask.any() and bm_ret[down_mask].mean() != 0
        else 0.0
    )
    bm_total = (aligned["bm"].iloc[-1] / aligned["bm"].iloc[0] - 1.0) * 100.0
    return BenchmarkAnalytics(
        alpha_annualized_pct=alpha_ann,
        beta=beta,
        information_ratio=ir,
        tracking_error_pct=te * 100.0,
        up_capture=up_capture,
        down_capture=down_capture,
        benchmark_return_pct=bm_total,
    )


# ---------------------------------------------------------------------------
# D2 — Attribution sectorielle + monthly returns
# ---------------------------------------------------------------------------


def sector_attribution(closed_trades_df: pd.DataFrame) -> pd.DataFrame:
    """Attribution PnL par secteur."""
    if closed_trades_df is None or closed_trades_df.empty or "sector" not in closed_trades_df.columns:
        return pd.DataFrame(columns=["sector", "n_trades", "total_pnl", "avg_return_pct", "win_rate_pct"])
    grouped = closed_trades_df.groupby(closed_trades_df["sector"].fillna("Unknown"))
    return pd.DataFrame(
        {
            "n_trades": grouped["pnl"].count().astype(int),
            "total_pnl": grouped["pnl"].sum().astype(float),
            "avg_return_pct": grouped["return_pct"].mean().astype(float),
            "win_rate_pct": (grouped["pnl"].apply(lambda x: float((x > 0).mean() * 100.0))),
        }
    ).reset_index().rename(columns={"sector": "sector"})


def monthly_returns_table(equity: pd.Series) -> pd.DataFrame:
    """Pivot table année × mois des returns mensuels (% )."""
    if equity.empty:
        return pd.DataFrame()
    monthly = equity.resample("M").last().pct_change().dropna() * 100.0
    if monthly.empty:
        return pd.DataFrame()
    df = pd.DataFrame({"year": monthly.index.year, "month": monthly.index.month, "ret_pct": monthly.values})
    pivot = df.pivot(index="year", columns="month", values="ret_pct")
    pivot.columns = [
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]
        for m in pivot.columns
    ]
    pivot["YTD"] = ((1 + pivot.fillna(0) / 100.0).prod(axis=1) - 1.0) * 100.0
    return pivot


# ---------------------------------------------------------------------------
# D4 — Tail / VaR / CVaR / Omega
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TailAnalytics:
    var_95_pct: float
    cvar_95_pct: float
    tail_ratio: float
    omega_ratio: float

    def to_dict(self) -> dict[str, float]:
        return {
            "var_95_pct": float(self.var_95_pct),
            "cvar_95_pct": float(self.cvar_95_pct),
            "tail_ratio": float(self.tail_ratio),
            "omega_ratio": float(self.omega_ratio),
        }


def compute_tail_analytics(equity: pd.Series, *, alpha: float = 0.05) -> TailAnalytics:
    if equity.empty:
        return TailAnalytics(0.0, 0.0, 0.0, 0.0)
    rets = equity.pct_change().dropna()
    if rets.empty:
        return TailAnalytics(0.0, 0.0, 0.0, 0.0)
    var_q = float(np.quantile(rets, alpha)) * 100.0
    tail = rets[rets <= np.quantile(rets, alpha)]
    cvar = float(tail.mean()) * 100.0 if not tail.empty else 0.0
    high_tail = float(np.quantile(rets, 1 - alpha))
    low_tail = abs(float(np.quantile(rets, alpha)))
    tail_ratio = high_tail / low_tail if low_tail > 0 else 0.0
    pos = rets[rets > 0].sum()
    neg = abs(rets[rets < 0].sum())
    omega = float(pos / neg) if neg > 0 else float("inf") if pos > 0 else 0.0
    return TailAnalytics(var_q, cvar, tail_ratio, omega)


# ---------------------------------------------------------------------------
# D3 — HTML interactif Plotly
# ---------------------------------------------------------------------------


def save_equity_curve_html(equity: pd.Series, output_path: Path) -> Path | None:
    """Sauvegarde la courbe d'equity en HTML interactif. Retourne None si Plotly indisponible."""
    try:
        import plotly.graph_objects as go  # type: ignore
    except ImportError:
        LOGGER.debug("Plotly indisponible — HTML interactif ignoré.")
        return None
    if equity.empty:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, mode="lines", name="Equity"))
    running_peak = equity.cummax()
    dd = (equity / running_peak - 1.0) * 100.0
    fig.add_trace(go.Scatter(x=dd.index, y=dd.values, mode="lines", name="Drawdown %", yaxis="y2"))
    fig.update_layout(
        title="Alpha Trade — Equity Curve & Drawdown (interactif)",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        yaxis2=dict(title="Drawdown (%)", overlaying="y", side="right"),
        template="plotly_white",
    )
    fig.write_html(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# D5 — Schéma JSON-friendly (sans dépendance pydantic)
# ---------------------------------------------------------------------------


def build_extended_report_payload(
    *,
    summary: dict[str, Any],
    benchmark: BenchmarkAnalytics | None = None,
    tail: TailAnalytics | None = None,
    sector_attr: pd.DataFrame | None = None,
    monthly_returns: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Construit un payload extended pour ``report.json``."""
    payload: dict[str, Any] = {"summary": summary}
    if benchmark is not None:
        payload["benchmark"] = benchmark.to_dict()
    if tail is not None:
        payload["tail"] = tail.to_dict()
    if sector_attr is not None and not sector_attr.empty:
        payload["sector_attribution"] = sector_attr.to_dict(orient="records")
    if monthly_returns is not None and not monthly_returns.empty:
        payload["monthly_returns"] = monthly_returns.reset_index().to_dict(orient="records")
    return payload


__all__ = [
    "BenchmarkAnalytics",
    "TailAnalytics",
    "build_extended_report_payload",
    "compute_benchmark_analytics",
    "compute_tail_analytics",
    "compare_total_return_to_oracle",
    "compute_total_return_with_dividends",
    "monthly_returns_table",
    "save_equity_curve_html",
    "sector_attribution",
]

