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


def _extract_trade_events_df(pf) -> Optional[pd.DataFrame]:
    return getattr(pf, "trade_events_df", None)


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


def _normalize_symbol_column(df: pd.DataFrame, column_name: str = "symbol") -> pd.DataFrame:
    normalized = df.copy()
    if column_name in normalized.columns:
        normalized[column_name] = normalized[column_name].astype(str).str.strip().str.upper()
    return normalized


def _normalize_datetime_columns(df: pd.DataFrame, *column_names: str) -> pd.DataFrame:
    normalized = df.copy()
    for column_name in column_names:
        if column_name in normalized.columns:
            normalized[column_name] = pd.to_datetime(normalized[column_name], errors="coerce")
    return normalized


def _coalesce_columns(frame: pd.DataFrame, columns: tuple[str, ...], *, default: object = None) -> pd.Series:
    result = pd.Series([default] * len(frame), index=frame.index, dtype="object")
    for column_name in columns:
        if column_name not in frame.columns:
            continue
        candidate = frame[column_name]
        result = result.where(result.notna(), candidate)
    return result


def _with_trade_merge_seq(frame: pd.DataFrame, *, execution_date_col: str) -> pd.DataFrame:
    enriched = frame.copy()
    symbol_series = enriched.get("symbol", pd.Series(index=enriched.index, dtype="object")).fillna("").astype(str)
    execution_series = pd.to_datetime(
        enriched.get(execution_date_col, pd.Series(index=enriched.index, dtype="datetime64[ns]")),
        errors="coerce",
    )
    enriched["_trade_merge_symbol"] = symbol_series.str.strip().str.upper()
    enriched["_trade_merge_execution_date"] = execution_series
    enriched["_trade_merge_seq"] = enriched.groupby(
        ["_trade_merge_symbol", "_trade_merge_execution_date"],
        dropna=False,
    ).cumcount()
    return enriched


def _build_legacy_trade_export_frame(pf) -> tuple[pd.DataFrame, str]:
    closed_trades_df = _extract_closed_trades_df(pf)
    if closed_trades_df is not None:
        legacy = _normalize_symbol_column(closed_trades_df.copy())
        legacy = _normalize_datetime_columns(legacy, "signal_date", "entry_date", "exit_date")
        if "entry_date" in legacy.columns and "execution_date" not in legacy.columns:
            legacy["execution_date"] = legacy["entry_date"]
        if "exit_date" in legacy.columns and "trade_status" not in legacy.columns:
            legacy["trade_status"] = np.where(legacy["exit_date"].notna(), "closed", "open")
        legacy["trade_export_source"] = "closed_trades_df"
        legacy["pipeline_reconciled"] = False
        return legacy, "closed_trades_df"

    readable = getattr(getattr(pf, "trades", None), "records_readable", None)
    if readable is None:
        return pd.DataFrame(), "none"
    readable_df = readable.copy() if isinstance(readable, pd.DataFrame) else pd.DataFrame(readable)
    if readable_df.empty:
        return readable_df, "vectorbt_records_readable"
    readable_df["trade_export_source"] = "vectorbt_records_readable"
    readable_df["pipeline_reconciled"] = False
    return readable_df, "vectorbt_records_readable"


def _build_pipeline_trade_export_frame(
    pipeline_signals_df: pd.DataFrame | None,
    *,
    legacy_trades_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    if pipeline_signals_df is None or pipeline_signals_df.empty:
        return pd.DataFrame(), {
            "pipeline_signal_rows": 0,
            "pipeline_closed_rows": 0,
            "pipeline_open_rows": 0,
            "legacy_matches": 0,
            "legacy_unmatched_rows": int(len(legacy_trades_df)),
        }

    pipeline = _normalize_symbol_column(pipeline_signals_df.copy())
    pipeline = _normalize_datetime_columns(
        pipeline,
        "trade_date",
        "signal_date",
        "execution_date",
        "replay_exit_date",
        "watcher_trigger_date",
        "watcher_transition_effective_date",
    )
    pipeline_export = pd.DataFrame(index=pipeline.index)
    pipeline_export["symbol"] = pipeline.get("symbol", pd.Series(index=pipeline.index, dtype="object"))
    pipeline_export["trade_date"] = _coalesce_columns(pipeline, ("trade_date", "signal_date"))
    pipeline_export["signal_date"] = _coalesce_columns(pipeline, ("signal_date", "trade_date"))
    pipeline_export["execution_date"] = _coalesce_columns(pipeline, ("execution_date",))
    pipeline_export["quantity"] = pd.to_numeric(
        _coalesce_columns(pipeline, ("filled_qty", "approved_shares", "target_shares")),
        errors="coerce",
    )
    pipeline_export["entry_price"] = pd.to_numeric(
        _coalesce_columns(pipeline, ("fill_price", "signal_fill_price", "entry_price", "decision_price")),
        errors="coerce",
    )
    pipeline_export["exit_date"] = _coalesce_columns(pipeline, ("replay_exit_date", "exit_date"))
    pipeline_export["exit_price"] = pd.to_numeric(
        _coalesce_columns(pipeline, ("replay_exit_price", "exit_price")),
        errors="coerce",
    )
    pipeline_export["exit_reason"] = _coalesce_columns(pipeline, ("replay_exit_reason", "exit_reason"))
    pipeline_export["exit_intent_role"] = _coalesce_columns(
        pipeline,
        ("replay_exit_intent_role", "exit_intent_role"),
    )
    pipeline_export["oco_sibling_canceled"] = _coalesce_columns(
        pipeline,
        ("replay_oco_sibling_canceled", "oco_sibling_canceled"),
    ).astype("boolean").fillna(False).astype(bool)
    pipeline_export["sector"] = _coalesce_columns(pipeline, ("sector", "signal_sector"))
    pipeline_export["selector_signal_mode"] = _coalesce_columns(pipeline, ("selector_signal_mode",))
    pipeline_export["selection_explanation"] = _coalesce_columns(pipeline, ("selection_explanation",))
    pipeline_export["entry_reason"] = _coalesce_columns(pipeline, ("entry_reason",))
    pipeline_export["watcher_transition_state"] = _coalesce_columns(pipeline, ("watcher_transition_state",))
    pipeline_export["watcher_trigger_date"] = _coalesce_columns(pipeline, ("watcher_trigger_date",))
    pipeline_export["watcher_transition_effective_date"] = _coalesce_columns(
        pipeline,
        ("watcher_transition_effective_date",),
    )
    pipeline_export["trade_export_source"] = "phase3_to_phase7_pipeline"
    pipeline_export["pipeline_reconciled"] = True
    pipeline_export["trade_status"] = np.where(
        pd.to_datetime(pipeline_export["exit_date"], errors="coerce").notna(),
        "closed",
        "open",
    )
    pipeline_export["holding_days"] = (
        pd.to_datetime(pipeline_export["exit_date"], errors="coerce")
        - pd.to_datetime(pipeline_export["execution_date"], errors="coerce")
    ).dt.days
    pipeline_export["estimated_pnl_price_only"] = (
        pd.to_numeric(pipeline_export["exit_price"], errors="coerce")
        - pd.to_numeric(pipeline_export["entry_price"], errors="coerce")
    ) * pd.to_numeric(pipeline_export["quantity"], errors="coerce")
    pipeline_export["estimated_return_pct_price_only"] = np.where(
        pd.to_numeric(pipeline_export["entry_price"], errors="coerce") > 0,
        (
            (pd.to_numeric(pipeline_export["exit_price"], errors="coerce")
             / pd.to_numeric(pipeline_export["entry_price"], errors="coerce"))
            - 1.0
        ) * 100.0,
        np.nan,
    )
    quantity_numeric = pd.to_numeric(pipeline_export["quantity"], errors="coerce")
    entry_price_numeric = pd.to_numeric(pipeline_export["entry_price"], errors="coerce")
    exit_price_numeric = pd.to_numeric(pipeline_export["exit_price"], errors="coerce")
    closed_mask = pd.to_datetime(pipeline_export["exit_date"], errors="coerce").notna()
    pipeline_export["entry_cost"] = np.where(closed_mask, quantity_numeric * entry_price_numeric, np.nan)
    pipeline_export["proceeds"] = np.where(closed_mask, quantity_numeric * exit_price_numeric, np.nan)
    pipeline_export["pnl"] = pipeline_export["proceeds"] - pipeline_export["entry_cost"]
    pipeline_export["return_pct"] = np.where(
        pipeline_export["entry_cost"] > 0,
        (pipeline_export["pnl"] / pipeline_export["entry_cost"]) * 100.0,
        np.nan,
    )

    pipeline_merge = _with_trade_merge_seq(pipeline_export, execution_date_col="execution_date")
    legacy_merge = _with_trade_merge_seq(legacy_trades_df, execution_date_col="execution_date") if not legacy_trades_df.empty else pd.DataFrame()
    merge_columns = ["_trade_merge_symbol", "_trade_merge_execution_date", "_trade_merge_seq"]
    if not legacy_merge.empty:
        legacy_subset_columns = [
            column
            for column in [
                *merge_columns,
                "quantity",
                "entry_price",
                "exit_price",
                "entry_cost",
                "proceeds",
                "pnl",
                "return_pct",
                "holding_days",
                "exit_reason",
                "sector",
                "signal_date",
            ]
            if column in legacy_merge.columns
        ]
        pipeline_merge = pipeline_merge.merge(
            legacy_merge[legacy_subset_columns],
            on=merge_columns,
            how="left",
            indicator="_legacy_merge",
            suffixes=("", "__legacy"),
        )
        for column_name in ("quantity", "entry_price", "exit_price", "entry_cost", "proceeds", "pnl", "return_pct", "holding_days", "exit_reason", "sector", "signal_date"):
            legacy_column = f"{column_name}__legacy"
            if legacy_column in pipeline_merge.columns:
                if column_name in pipeline_merge.columns:
                    pipeline_merge[column_name] = pipeline_merge[column_name].where(pipeline_merge[column_name].notna(), pipeline_merge[legacy_column])
                else:
                    pipeline_merge[column_name] = pipeline_merge[legacy_column]
                pipeline_merge.drop(columns=[legacy_column], inplace=True)
        matched_legacy = int((pipeline_merge["_legacy_merge"] == "both").sum())
        pipeline_merge["legacy_trade_match"] = pipeline_merge["_legacy_merge"] == "both"
        pipeline_merge.drop(columns=["_legacy_merge"], inplace=True)
    else:
        matched_legacy = 0
        pipeline_merge["legacy_trade_match"] = False

    pipeline_merge.drop(columns=[column for column in merge_columns if column in pipeline_merge.columns], inplace=True)
    return pipeline_merge, {
        "pipeline_signal_rows": int(len(pipeline_export)),
        "pipeline_closed_rows": int((pipeline_export["trade_status"] == "closed").sum()),
        "pipeline_open_rows": int((pipeline_export["trade_status"] == "open").sum()),
        "legacy_matches": matched_legacy,
        "legacy_unmatched_rows": max(int(len(legacy_trades_df)) - matched_legacy, 0),
    }


def build_trade_export_bundle(
    pf,
    *,
    pipeline_signals_df: pd.DataFrame | None = None,
    corporate_actions_summary: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    legacy_trades_df, legacy_source = _build_legacy_trade_export_frame(pf)
    pipeline_export_df, reconciliation_counts = _build_pipeline_trade_export_frame(
        pipeline_signals_df,
        legacy_trades_df=legacy_trades_df,
    )
    if not pipeline_export_df.empty:
        export_df = pipeline_export_df
        export_source = "phase3_to_phase7_pipeline"
    else:
        export_df = legacy_trades_df
        export_source = legacy_source

    summary: dict[str, object] = {
        "source": export_source,
        "row_count": int(len(export_df)),
        "legacy_source": legacy_source,
        "legacy_closed_rows": int(len(legacy_trades_df)),
        **reconciliation_counts,
        "export_closed_rows": int((export_df.get("trade_status", pd.Series(dtype="object")) == "closed").sum()) if not export_df.empty else 0,
        "export_open_rows": int((export_df.get("trade_status", pd.Series(dtype="object")) == "open").sum()) if not export_df.empty else 0,
        "price_adjustment_convention": (
            str(corporate_actions_summary.get("price_adjustment_convention") or "split_adjusted_prices_plus_cash_ledger")
            if isinstance(corporate_actions_summary, dict)
            else "split_adjusted_prices_plus_cash_ledger"
        ),
    }
    return export_df, summary


def load_corporate_actions_summary(
    start_date,
    end_date,
    *,
    account_id: str | None = None,
    engine=None,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "price_adjustment_convention": "split_adjusted_prices_plus_cash_ledger",
        "split_adjusted_prices": True,
        "dividends_reflected_in_prices": False,
        "cash_ledger_entry_types": {},
        "dividend_cash_total": 0.0,
        "cash_in_lieu_total": 0.0,
        "total_cash_impact": 0.0,
        "source_table": "portfolio_cash_ledger",
    }
    try:
        from sqlalchemy import text  # type: ignore

        if engine is None:
            from database.connection import get_sqlalchemy_engine  # type: ignore

            engine = get_sqlalchemy_engine()
        clauses = ["DATE(occurred_at) BETWEEN :start_date AND :end_date"]
        params: dict[str, object] = {"start_date": start_date, "end_date": end_date}
        if account_id:
            clauses.append("account_id = :account_id")
            params["account_id"] = account_id
        where_clause = " AND ".join(clauses)
        stmt = text(
            f"SELECT entry_type, COUNT(*) AS row_count, COALESCE(SUM(amount), 0) AS total_amount "
            f"FROM portfolio_cash_ledger WHERE {where_clause} GROUP BY entry_type"
        )
        with engine.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(stmt, params).fetchall()
        cash_types: dict[str, dict[str, float | int]] = {}
        for row in rows:
            entry_type = str(row[0] or "unknown")
            row_count = int(row[1] or 0)
            total_amount = float(row[2] or 0.0)
            cash_types[entry_type] = {"row_count": row_count, "total_amount": total_amount}
        summary["cash_ledger_entry_types"] = cash_types
        summary["dividend_cash_total"] = float(cash_types.get("dividend_credit", {}).get("total_amount", 0.0))
        summary["cash_in_lieu_total"] = float(cash_types.get("cash_in_lieu", {}).get("total_amount", 0.0))
        summary["total_cash_impact"] = float(sum(float(payload.get("total_amount", 0.0)) for payload in cash_types.values()))
        return summary
    except Exception as exc:
        LOGGER.debug("load_corporate_actions_summary fallback par défaut : %s", exc)
        return summary


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
    # Sprint 4 — métriques directionnelles long/short
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate_pct: float = 0.0
    short_win_rate_pct: float = 0.0
    long_pnl_total: float = 0.0
    short_pnl_total: float = 0.0
    force_close_exits: int = 0
    # Sprint 5 — force-close par side (ML)
    force_close_exits_long: int = 0
    force_close_exits_short: int = 0

    def to_serializable_dict(self) -> dict[str, float | int | str]:
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
            # Sprint 4 — directionnelles
            "long_trades": int(self.long_trades),
            "short_trades": int(self.short_trades),
            "long_win_rate_pct": float(self.long_win_rate_pct),
            "short_win_rate_pct": float(self.short_win_rate_pct),
            "long_pnl_total": float(self.long_pnl_total),
            "short_pnl_total": float(self.short_pnl_total),
            "force_close_exits": int(self.force_close_exits),
            "force_close_exits_long": int(self.force_close_exits_long),
            "force_close_exits_short": int(self.force_close_exits_short),
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
            # Sprint 4 — split directionnel
            "Trades Long": f"{self.long_trades} (WR: {self.long_win_rate_pct:.1f}%, PnL: ${self.long_pnl_total:,.2f})",
            "Trades Short": f"{self.short_trades} (WR: {self.short_win_rate_pct:.1f}%, PnL: ${self.short_pnl_total:,.2f})",
            "Force-close (total)": self.force_close_exits,
            "Force-close Long": self.force_close_exits_long,
            "Force-close Short": self.force_close_exits_short,
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
    summary = load_corporate_actions_summary(
        start_date,
        end_date,
        account_id=account_id,
        engine=engine,
    )
    dividend_cash_total = summary.get("dividend_cash_total", 0.0)
    return float(dividend_cash_total or 0.0)


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
        # Sprint 4 — split directionnel long/short
        long_trades = 0
        short_trades = 0
        long_win_rate = 0.0
        short_win_rate = 0.0
        long_pnl_total = 0.0
        short_pnl_total = 0.0
        force_close_exits = 0
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
            # Sprint 4 — directionnelles
            if "side" in trades_df.columns:
                long_mask = trades_df["side"] == "buy"
                short_mask = trades_df["side"] == "sell"
                long_trades = int(long_mask.sum())
                short_trades = int(short_mask.sum())
                if long_trades > 0:
                    long_win_rate = float((pnl[long_mask] > 0).mean() * 100)
                    long_pnl_total = float(pnl[long_mask].sum())
                if short_trades > 0:
                    short_win_rate = float((pnl[short_mask] > 0).mean() * 100)
                    short_pnl_total = float(pnl[short_mask].sum())
            if "exit_reason" in trades_df.columns:
                force_close_exits = int((trades_df["exit_reason"] == "force_close_breaker").sum())
                # Sprint 5 — force-close par side
                fc_long = 0
                fc_short = 0
                if force_close_exits > 0 and "side" in trades_df.columns:
                    fc_mask = trades_df["exit_reason"] == "force_close_breaker"
                    fc_long = int((fc_mask & (trades_df["side"] == "buy")).sum())
                    fc_short = int((fc_mask & (trades_df["side"] == "sell")).sum())
            else:
                force_close_exits = 0
                fc_long = 0
                fc_short = 0
        else:
            win_rate = 0.0
            avg_dur = 0.0
            pf_factor = 0.0
            long_trades = 0
            short_trades = 0
            long_win_rate = 0.0
            short_win_rate = 0.0
            long_pnl_total = 0.0
            short_pnl_total = 0.0
            force_close_exits = 0
            fc_long = 0
            fc_short = 0

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
            # Sprint 4 — directionnelles
            long_trades=long_trades,
            short_trades=short_trades,
            long_win_rate_pct=long_win_rate,
            short_win_rate_pct=short_win_rate,
            long_pnl_total=long_pnl_total,
            short_pnl_total=short_pnl_total,
            force_close_exits=force_close_exits,
            # Sprint 5 — force-close par side
            force_close_exits_long=fc_long,
            force_close_exits_short=fc_short,
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


def save_trades_csv(
    pf,
    output_dir: Path | None = None,
    *,
    pipeline_signals_df: pd.DataFrame | None = None,
    corporate_actions_summary: dict[str, object] | None = None,
) -> Path:
    """Exporte la liste des trades en CSV."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "trades.csv"
    try:
        trades_df, export_summary = build_trade_export_bundle(
            pf,
            pipeline_signals_df=pipeline_signals_df,
            corporate_actions_summary=corporate_actions_summary,
        )
        trades_df.to_csv(str(filepath), index=False)
        LOGGER.info(
            "Trades exportés : %s (%d lignes, source=%s)",
            filepath,
            len(trades_df),
            export_summary.get("source", "unknown"),
        )
    except Exception as exc:
        LOGGER.warning("Impossible d'exporter les trades : %s", exc)
    return filepath


def save_trade_audit_csv(pf, output_dir: Path | None = None) -> Path:
    """Exporte le journal d'audit détaillé des événements de trade."""
    out = output_dir or ARTIFACTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / "trade_audit_log.csv"
    try:
        trade_events_df = _extract_trade_events_df(pf)
        audit_df = (
            trade_events_df.copy()
            if trade_events_df is not None
            else pd.DataFrame(columns=["event_type"])
        )
        audit_df.to_csv(str(filepath), index=False)
        LOGGER.info("Audit trade exporté : %s (%d événements)", filepath, len(audit_df))
    except Exception as exc:
        LOGGER.warning("Impossible d'exporter l'audit trade : %s", exc)
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
    fidelity: dict[str, object] | None = None,
    corporate_actions: dict[str, object] | None = None,
    trade_export: dict[str, object] | None = None,
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
        "fidelity": fidelity or {},
        "corporate_actions": corporate_actions or {},
        "trade_export": trade_export or {},
    }
    filepath.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Rapport JSON sauvegardé : %s", filepath)
    return filepath



