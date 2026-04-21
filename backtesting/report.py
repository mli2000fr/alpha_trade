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

    def to_serializable_dict(self) -> dict[str, float | int]:
        return {
            "initial_equity": float(self.initial_equity),
            "final_value": float(self.final_value),
            "total_return_pct": float(self.total_return_pct),
            "cagr_pct": float(self.cagr_pct),
            "sharpe_ratio": float(self.sharpe_ratio),
            "sortino_ratio": float(self.sortino_ratio),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "total_trades": int(self.total_trades),
            "win_rate_pct": float(self.win_rate_pct),
            "avg_trade_duration_days": float(self.avg_trade_duration_days),
            "profit_factor": float(self.profit_factor),
        }

    def to_dict(self) -> dict:
        return {
            "Capital initial": f"${self.initial_equity:,.0f}",
            "Valeur finale": f"${self.final_value:,.2f}",
            "Rendement total": f"{self.total_return_pct:.2f}%",
            "CAGR": f"{self.cagr_pct:.2f}%",
            "Sharpe Ratio": f"{self.sharpe_ratio:.3f}",
            "Sortino Ratio": f"{self.sortino_ratio:.3f}",
            "Max Drawdown": f"{self.max_drawdown_pct:.2f}%",
            "Nombre de trades": self.total_trades,
            "Win Rate": f"{self.win_rate_pct:.1f}%",
            "Durée moy. trade (j)": f"{self.avg_trade_duration_days:.1f}",
            "Profit Factor": f"{self.profit_factor:.2f}",
        }

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("        RAPPORT DE BACKTEST — ALPHA TRADE")
        print("=" * 60)
        for k, v in self.to_dict().items():
            print(f"  {k:<25} {v}")
        print("=" * 60 + "\n")


def generate_report(pf, initial_equity: float) -> BacktestReport:
    """Extrait les métriques depuis un vbt.Portfolio."""
    closed_trades_df = _extract_closed_trades_df(pf)
    if closed_trades_df is not None:
        equity = _extract_equity_curve(pf)
        final_val = float(equity.iloc[-1]) if not equity.empty else float(initial_equity)
        total_ret = (final_val / initial_equity - 1) * 100 if initial_equity else 0.0
        n_days = len(equity)
        n_years = max(n_days / 252, 0.01)
        cagr = ((final_val / initial_equity) ** (1 / n_years) - 1) * 100 if initial_equity > 0 else 0.0

        daily_returns = equity.pct_change().dropna()
        sharpe = 0.0
        sortino = 0.0
        if not daily_returns.empty:
            returns_std = float(daily_returns.std(ddof=0))
            if returns_std > 0:
                sharpe = _clean_metric(float(daily_returns.mean() / returns_std) * math.sqrt(252))
            downside = daily_returns[daily_returns < 0]
            downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
            if downside_std > 0:
                sortino = _clean_metric(float(daily_returns.mean() / downside_std) * math.sqrt(252))

        if equity.empty:
            max_dd = 0.0
        else:
            running_peak = equity.cummax()
            drawdown = (equity / running_peak) - 1.0
            max_dd = _clean_metric(abs(float(drawdown.min())) * 100)

        trades_df = closed_trades_df.copy()
        n_trades = int(len(trades_df))
        if n_trades > 0:
            pnl = trades_df["pnl"].astype(float)
            win_rate = float((pnl > 0).mean() * 100)
            avg_dur = float(trades_df["holding_days"].astype(float).mean())
            gains = float(pnl[pnl > 0].sum())
            losses = float(pnl[pnl < 0].sum())
            pf_factor = gains / abs(losses) if losses < 0 else (float("inf") if gains > 0 else 0.0)
            pf_factor = _clean_metric(pf_factor, default=0.0)
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
        )

    final_val = _as_float(pf.final_value())
    total_ret = (final_val / initial_equity - 1) * 100
    n_days = len(pf.wrapper.index)
    n_years = max(n_days / 252, 0.01)
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
        pf_factor = _clean_metric(_as_float(trades.profit_factor())) if n_trades > 0 else 0.0
    except Exception:
        pf_factor = 0.0
    return BacktestReport(
        initial_equity=initial_equity, final_value=final_val,
        total_return_pct=total_ret, cagr_pct=cagr,
        sharpe_ratio=sharpe, sortino_ratio=sortino,
        max_drawdown_pct=max_dd, total_trades=n_trades,
        win_rate_pct=win_rate, avg_trade_duration_days=avg_dur,
        profit_factor=pf_factor,
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
) -> Path:
    """Sauvegarde un manifeste JSON des métriques et artefacts du backtest."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "report.json"
    payload = {
        "summary": report.to_serializable_dict(),
        "artifacts": artifacts or {},
        "params": params or {},
        "diagnostics": diagnostics or {},
    }
    filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Rapport JSON sauvegardé : %s", filepath)
    return filepath



