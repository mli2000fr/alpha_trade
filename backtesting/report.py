"""
backtesting/report.py
======================
Génération du rapport de backtest : métriques clés + equity curve.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)
ARTIFACTS_DIR = Path("artifacts") / "backtesting"


def _as_float(value) -> float:
    """Convertit une valeur scalaire vectorbt/pandas en float."""
    if hasattr(value, "iloc"):
        return float(value.iloc[0])
    return float(value)


def _as_int(value) -> int:
    """Convertit une valeur scalaire vectorbt/pandas en int."""
    if hasattr(value, "iloc"):
        return int(value.iloc[0])
    return int(value)


def _clean_metric(value: float, default: float = 0.0) -> float:
    """Normalise NaN/inf vers une valeur par défaut pour l'affichage."""
    if math.isnan(value) or math.isinf(value):
        return default
    return value


def _extract_equity_curve(pf) -> pd.Series:
    """Retourne la courbe de valeur sous forme de Series pandas."""
    equity = pf.value() if hasattr(pf, "value") else getattr(pf, "equity_curve")
    if isinstance(equity, pd.DataFrame):
        if equity.shape[1] != 1:
            raise ValueError("Equity curve ambigüe: plusieurs colonnes détectées.")
        equity = equity.iloc[:, 0]
    if not isinstance(equity, pd.Series):
        equity = pd.Series(equity)
    return equity.astype(float)


def _extract_closed_trades_df(pf) -> Optional[pd.DataFrame]:
    return getattr(pf, "closed_trades_df", None)


def extract_diagnostics(pf) -> dict[str, object]:
    diagnostics = getattr(pf, "diagnostics", None)
    if diagnostics is None:
        return {}
    to_dict = getattr(diagnostics, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, dict):
            return result
        return {}
    if isinstance(diagnostics, dict):
        return diagnostics
    return {}


@dataclass
class BacktestReport:
    """Résumé des métriques de backtest."""
    initial_equity: float
    final_value: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    avg_trade_duration_days: float
    profit_factor: float
    # Phase 6.1.c — rendement total dividendes inclus.
    dividends_received: float = 0.0
    total_return_with_dividends_pct: float = 0.0
    # Phase A.5 (refactor) — métriques de risque additionnelles.
    calmar_ratio: float = 0.0
    ulcer_index: float = 0.0
    # Phase A.6 — risk-free rate annualisé utilisé pour Sharpe/Sortino.
    risk_free_rate: float = 0.0

    def to_serializable_dict(self) -> dict[str, float | int]:
        # Phase A.7 — conserver +inf comme sentinel JSON-friendly ("inf").
        def _serialize_float(value: float) -> float | str:
            if math.isinf(value):
                return "inf" if value > 0 else "-inf"
            if math.isnan(value):
                return 0.0
            return float(value)

        return {
            "initial_equity": float(self.initial_equity),
            "final_value": float(self.final_value),
            "total_return_pct": float(self.total_return_pct),
            "total_return_price_only_pct": float(self.total_return_pct),
            "total_return_with_dividends_pct": float(self.total_return_with_dividends_pct),
            "dividends_received": float(self.dividends_received),
            "cagr_pct": float(self.cagr_pct),
            "sharpe_ratio": float(self.sharpe_ratio),
            "sortino_ratio": float(self.sortino_ratio),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "calmar_ratio": _serialize_float(self.calmar_ratio),
            "ulcer_index": float(self.ulcer_index),
            "risk_free_rate": float(self.risk_free_rate),
            "total_trades": int(self.total_trades),
            "win_rate_pct": float(self.win_rate_pct),
            "avg_trade_duration_days": float(self.avg_trade_duration_days),
            "profit_factor": _serialize_float(self.profit_factor),
        }

    def to_dict(self) -> dict:
        # Affichage humain : profit_factor inf devient "∞".
        pf_display = "∞" if math.isinf(self.profit_factor) and self.profit_factor > 0 else f"{self.profit_factor:.2f}"
        calmar_display = "∞" if math.isinf(self.calmar_ratio) and self.calmar_ratio > 0 else f"{self.calmar_ratio:.3f}"
        return {
            "Capital initial": f"${self.initial_equity:,.0f}",
            "Valeur finale": f"${self.final_value:,.2f}",
            "Rendement total (prix)": f"{self.total_return_pct:.2f}%",
            "Rendement total (avec div.)": f"{self.total_return_with_dividends_pct:.2f}%",
            "Dividendes encaissés": f"${self.dividends_received:,.2f}",
            "CAGR": f"{self.cagr_pct:.2f}%",
            "Sharpe Ratio": f"{self.sharpe_ratio:.3f}",
            "Sortino Ratio": f"{self.sortino_ratio:.3f}",
            "Calmar Ratio": calmar_display,
            "Ulcer Index": f"{self.ulcer_index:.3f}",
            "Max Drawdown": f"{self.max_drawdown_pct:.2f}%",
            "Nombre de trades": self.total_trades,
            "Win Rate": f"{self.win_rate_pct:.1f}%",
            "Durée moy. trade (j)": f"{self.avg_trade_duration_days:.1f}",
            "Profit Factor": pf_display,
        }

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("        RAPPORT DE BACKTEST — ALPHA TRADE")
        print("=" * 60)
        for k, v in self.to_dict().items():
            print(f"  {k:<25} {v}")
        print("=" * 60 + "\n")


def load_dividends_received(
    start_date,
    end_date,
    *,
    account_id: str | None = None,
    engine=None,
) -> float:
    """Phase 6.1.c — somme des dividendes crédités sur la période.

    Lit ``portfolio_cash_ledger`` (entry_type = 'dividend_credit') si
    disponible. Tolérant : retourne ``0.0`` si la table ou la connexion
    n'est pas accessible (ex: tests sans DB).
    """
    try:
        from sqlalchemy import text  # type: ignore

        if engine is None:
            from database.connection import get_sqlalchemy_engine  # type: ignore

            engine = get_sqlalchemy_engine()
        clauses = [
            "entry_type = 'dividend_credit'",
            "DATE(occurred_at) BETWEEN :start_date AND :end_date",
        ]
        params: dict[str, object] = {"start_date": start_date, "end_date": end_date}
        if account_id:
            clauses.append("account_id = :account_id")
            params["account_id"] = account_id
        where_clause = " AND ".join(clauses)
        stmt = text(
            f"SELECT COALESCE(SUM(amount), 0) FROM portfolio_cash_ledger WHERE {where_clause}"
        )
        with engine.connect() as conn:  # type: ignore[attr-defined]
            result = conn.execute(stmt, params).scalar()
        return float(result or 0.0)
    except Exception as exc:
        LOGGER.debug("load_dividends_received fallback 0.0 : %s", exc)
        return 0.0


def _compute_ulcer_index(equity: pd.Series) -> float:
    """Ulcer Index = sqrt(mean(drawdown_i^2)) en pourcentage.

    Mesure la "douleur" cumulée des drawdowns (Martin & McCann, 1989).
    """
    if equity.empty:
        return 0.0
    running_peak = equity.cummax()
    dd_pct = ((equity / running_peak) - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(dd_pct))))


def _compute_calmar(cagr_pct: float, max_dd_pct: float) -> float:
    """Calmar Ratio = CAGR / |Max Drawdown|.

    +inf si MDD ≈ 0 et CAGR > 0 (sentinel A.7).
    """
    if max_dd_pct <= 1e-9:
        if cagr_pct > 0:
            return float("inf")
        return 0.0
    return float(cagr_pct / max_dd_pct)


def generate_report(
    pf,
    initial_equity: float,
    *,
    dividends_received: float = 0.0,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = 252,
) -> BacktestReport:
    """Extrait les métriques depuis un portefeuille compatible vectorbt/BacktestResult.

    Phase A.5/A.6/A.7 :
    - ajout Calmar + Ulcer Index ;
    - paramétrage ``risk_free_rate`` (annualisé, déduit des returns avant Sharpe/Sortino) ;
    - profit_factor = +inf conservé comme sentinel (au lieu de 0).
    """
    rf_daily = float(risk_free_rate) / float(trading_days_per_year) if trading_days_per_year else 0.0
    closed_trades_df = _extract_closed_trades_df(pf)
    if closed_trades_df is not None:
        equity = _extract_equity_curve(pf)
        final_val = float(equity.iloc[-1]) if not equity.empty else float(initial_equity)
        total_ret = (final_val / initial_equity - 1) * 100 if initial_equity else 0.0
        n_days = len(equity)
        n_years = max(n_days / trading_days_per_year, 0.01)
        cagr = ((final_val / initial_equity) ** (1 / n_years) - 1) * 100 if initial_equity > 0 else 0.0

        daily_returns = equity.pct_change().dropna()
        excess_returns = daily_returns - rf_daily
        sharpe = 0.0
        sortino = 0.0
        if not excess_returns.empty:
            returns_std = float(excess_returns.std(ddof=0))
            if returns_std > 0:
                sharpe = _clean_metric(float(excess_returns.mean() / returns_std) * math.sqrt(trading_days_per_year))
            downside = excess_returns[excess_returns < 0]
            downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
            if downside_std > 0:
                sortino = _clean_metric(float(excess_returns.mean() / downside_std) * math.sqrt(trading_days_per_year))

        if equity.empty:
            max_dd = 0.0
            ulcer = 0.0
        else:
            running_peak = equity.cummax()
            drawdown = (equity / running_peak) - 1.0
            max_dd = _clean_metric(abs(float(drawdown.min())) * 100)
            ulcer = _compute_ulcer_index(equity)

        calmar = _compute_calmar(cagr, max_dd)

        trades_df = closed_trades_df.copy()
        n_trades = int(len(trades_df))
        if n_trades > 0:
            pnl = trades_df["pnl"].astype(float)
            win_rate = float((pnl > 0).mean() * 100)
            avg_dur = float(trades_df["holding_days"].astype(float).mean())
            gains = float(pnl[pnl > 0].sum())
            losses = float(pnl[pnl < 0].sum())
            # Phase A.7 — conserver +inf comme sentinel au lieu de mapper à 0.
            if losses < 0:
                pf_factor = gains / abs(losses)
            elif gains > 0:
                pf_factor = float("inf")
            else:
                pf_factor = 0.0
        else:
            win_rate = 0.0
            avg_dur = 0.0
            pf_factor = 0.0

        return BacktestReport(
            initial_equity=initial_equity,
            final_value=final_val,
            total_return_pct=total_ret,
            cagr_pct=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown_pct=max_dd,
            total_trades=n_trades,
            win_rate_pct=win_rate,
            avg_trade_duration_days=avg_dur,
            profit_factor=pf_factor,
            dividends_received=float(dividends_received),
            total_return_with_dividends_pct=(
                ((final_val + float(dividends_received)) / initial_equity - 1) * 100
                if initial_equity
                else 0.0
            ),
            calmar_ratio=calmar,
            ulcer_index=ulcer,
            risk_free_rate=float(risk_free_rate),
        )

    final_val = _as_float(pf.final_value())
    total_ret = (final_val / initial_equity - 1) * 100
    n_days = len(pf.wrapper.index)
    n_years = max(n_days / trading_days_per_year, 0.01)
    cagr = ((final_val / initial_equity) ** (1 / n_years) - 1) * 100
    sharpe = _clean_metric(_as_float(pf.sharpe_ratio())) if hasattr(pf, "sharpe_ratio") else 0.0
    sortino = _clean_metric(_as_float(pf.sortino_ratio())) if hasattr(pf, "sortino_ratio") else 0.0
    max_dd = _clean_metric(_as_float(pf.max_drawdown()) * 100)
    trades = pf.trades.closed if hasattr(pf.trades, "closed") else pf.trades
    n_trades = _as_int(trades.count()) if hasattr(trades, "count") else 0
    win_rate = _clean_metric(_as_float(trades.win_rate()) * 100) if n_trades > 0 else 0.0
    try:
        avg_dur = _clean_metric(_as_float(trades.duration.mean())) if n_trades > 0 else 0.0
    except Exception:
        avg_dur = 0.0
    try:
        # Phase A.7 — vbt expose +inf si pas de pertes : on ne mappe plus à 0.
        raw_pf = _as_float(trades.profit_factor()) if n_trades > 0 else 0.0
        pf_factor = raw_pf if not math.isnan(raw_pf) else 0.0
    except Exception:
        pf_factor = 0.0
    # Calmar/Ulcer best-effort sur l'equity vbt si disponible.
    ulcer = 0.0
    try:
        equity_for_metrics = _extract_equity_curve(pf)
        ulcer = _compute_ulcer_index(equity_for_metrics)
    except Exception:
        ulcer = 0.0
    calmar = _compute_calmar(cagr, max_dd)
    return BacktestReport(
        initial_equity=initial_equity, final_value=final_val,
        total_return_pct=total_ret, cagr_pct=cagr,
        sharpe_ratio=sharpe, sortino_ratio=sortino,
        max_drawdown_pct=max_dd, total_trades=n_trades,
        win_rate_pct=win_rate, avg_trade_duration_days=avg_dur,
        profit_factor=pf_factor,
        dividends_received=float(dividends_received),
        total_return_with_dividends_pct=(
            ((final_val + float(dividends_received)) / initial_equity - 1) * 100
            if initial_equity
            else 0.0
        ),
        calmar_ratio=calmar,
        ulcer_index=ulcer,
        risk_free_rate=float(risk_free_rate),
    )


def save_equity_curve(pf, output_dir: Path | None = None) -> Path:
    """Sauvegarde l'equity curve en PNG."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "equity_curve.png"
    try:
        fig = pf.plot_value()
        fig.update_layout(
            title="Alpha Trade — Equity Curve (Backtest)",
            xaxis_title="Date", yaxis_title="Valeur ($)",
            template="plotly_white",
        )
        fig.write_image(str(filepath), width=1400, height=600)
        LOGGER.info("Equity curve sauvegardée : %s", filepath)
    except Exception:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            equity = _extract_equity_curve(pf)
            plt.figure(figsize=(14, 6))
            plt.plot(equity.index, equity.values, linewidth=1)
            plt.title("Alpha Trade — Equity Curve (Backtest)")
            plt.xlabel("Date")
            plt.ylabel("Valeur ($)")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(str(filepath), dpi=150)
            plt.close()
            LOGGER.info("Equity curve (matplotlib fallback) : %s", filepath)
        except Exception as exc2:
            LOGGER.error("Échec sauvegarde equity curve : %s", exc2)
    return filepath


def save_trades_csv(pf, output_dir: Path | None = None) -> Path:
    """Exporte la liste des trades en CSV."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "trades.csv"
    try:
        closed_trades_df = _extract_closed_trades_df(pf)
        trades_df = pf.trades.records_readable if closed_trades_df is None else pf.trades.records_readable
        trades_df.to_csv(str(filepath), index=False)
        LOGGER.info("Trades exportés : %s (%d trades)", filepath, len(trades_df))
    except Exception as exc:
        LOGGER.warning("Impossible d'exporter les trades : %s", exc)
    return filepath


def save_equity_curve_csv(pf, output_dir: Path | None = None) -> Path:
    """Exporte la série d'equity curve en CSV pour réutilisation IHM."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "equity_curve.csv"
    try:
        equity = _extract_equity_curve(pf)
        equity_df = equity.reset_index()
        equity_df.columns = ["trade_date", "portfolio_value"]
        equity_df.to_csv(str(filepath), index=False)
        LOGGER.info("Equity curve CSV exportée : %s", filepath)
    except Exception as exc:
        LOGGER.warning("Impossible d'exporter l'equity curve CSV : %s", exc)
    return filepath


def save_report_json(
    report: BacktestReport,
    output_dir: Path | None = None,
    *,
    artifacts: dict[str, str] | None = None,
    params: dict[str, object] | None = None,
    diagnostics: dict[str, object] | None = None,
    run_metadata: dict[str, object] | None = None,
) -> Path:
    """Sauvegarde un manifeste JSON des métriques et artefacts du backtest.

    Phase A.4 : ajout du bloc ``run_metadata`` (git sha, python version,
    dataset hash, seed, etc.) pour la reproductibilité.
    """
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "report.json"
    payload = {
        "summary": report.to_serializable_dict(),
        "artifacts": artifacts or {},
        "params": params or {},
        "diagnostics": diagnostics or {},
        "run_metadata": run_metadata or {},
    }
    filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Rapport JSON sauvegardé : %s", filepath)
    return filepath



