"""
backtesting/cli.py
===================
Interface CLI du module de backtesting.

Usage :
    python -m backtesting run --start 2016-01-01 --end 2026-04-20 --equity 100000
    python -m backtesting run --start 2020-01-01 --end 2026-04-20 --equity 50000 --tp 0.10 --ts 0.04
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import cast

from backtesting.fidelity import build_compare_to_live_summary, save_compare_to_live_summary
from common.capital_presets import (
    apply_backtest_defaults_from_preset,
    build_risk_config_kwargs_from_preset,
    build_screener_config_kwargs_from_preset,
    build_selector_config_kwargs_from_preset,
    capital_preset_fingerprint,
    resolve_capital_preset_for_equity,
    resolve_effective_capital_preset,
)
from common.market_calendar import nyse_session_dates
from common.utils import configure_root_logging

LOGGER = logging.getLogger(__name__)


def _resolve_phase2_ohlcv_history_start(
    start_date: date,
    *,
    atr_window: int,
    correlation_lookback_days: int,
) -> date:
    """Calcule un warm-up OHLCV suffisant pour la phase 2 risk.

    - ATR nécessite ``atr_window + 1`` clôtures pour produire ``atr_window`` true ranges.
    - Le filtre de corrélation requiert ``correlation_lookback_days + 1`` clôtures.

    La conversion trading days -> jours calendaires ajoute une marge conservative
    pour weekends et jours fériés afin d'éviter un faux `atr_20=None` au début du backtest.
    """
    required_trading_bars = max(int(atr_window) + 1, int(correlation_lookback_days) + 1)
    required_calendar_days = max(30, int(required_trading_bars * 7 / 5) + 10)
    return start_date - timedelta(days=required_calendar_days)


def _safe_print(*values: object, sep: str = " ", end: str = "\n") -> None:
    """Affiche un message même si stdout n'accepte pas certains caractères Unicode."""
    text = sep.join(str(v) for v in values) + end
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sanitized = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(sanitized)


def _coerce_date_value(value: object) -> date | None:
    import pandas as pd

    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return date(int(ts.year), int(ts.month), int(ts.day))


def _run_bars_source_preflight_or_skip(engine: object, start_date: date, end_date: date) -> dict[str, object]:
    from backtesting.data_loader import BACKTEST_REQUIRED_BARS_DATA_SOURCE, preflight_required_bars_data_source

    try:
        return dict(preflight_required_bars_data_source(engine, start_date, end_date))
    except RuntimeError as exc:
        if hasattr(engine, "connect"):
            raise
        LOGGER.warning(
            "Préflight OHLCV ignoré car le moteur injecté ne fournit pas l'inspection SQLAlchemy attendue.",
            exc_info=True,
        )
        return {
            "table_name": "stock_bars_daily",
            "date_column": None,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "required_data_source": BACKTEST_REQUIRED_BARS_DATA_SOURCE,
            "status": "skipped",
            "degraded_reasons": [],
            "rows_total": None,
            "required_rows": None,
            "counts": {},
            "sources_present": [],
            "dominant_source": None,
            "dominant_ratio": None,
            "mixed_sources_detected": False,
            "error": str(exc),
        }


def _extract_symbols_for_log(symbols: object) -> list[str]:
    if not isinstance(symbols, (list, tuple, set)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in symbols:
        symbol = str(value or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _format_symbol_preview(symbols: list[str], *, limit: int = 20) -> str:
    if not symbols:
        return ""
    preview = ", ".join(symbols[:limit])
    if len(symbols) > limit:
        preview += f" … (+{len(symbols) - limit})"
    return preview


def _emit_backtest_missing_coverage_logs(
    *,
    sentiment_mode: str,
    sentiment_diagnostics: object | None,
    ml_mode: str,
    ml_diagnostics: object | None,
) -> None:
    sentiment_missing_before = _extract_symbols_for_log(getattr(sentiment_diagnostics, "missing_symbols_before", ()))
    if sentiment_mode != "off" and sentiment_missing_before:
        message = (
            f"⚠️ Sentiment — symboles sans score sentiment avant fallback/rebuild ({len(sentiment_missing_before)}) : "
            f"{_format_symbol_preview(sentiment_missing_before)}"
        )
        LOGGER.warning(message)
        _safe_print(f"   {message}\n")

    sentiment_missing_after = _extract_symbols_for_log(getattr(sentiment_diagnostics, "missing_symbols_after", ()))
    if sentiment_mode != "off" and sentiment_missing_after:
        message = (
            f"⚠️ Sentiment — symboles encore sans score sentiment après préparation ({len(sentiment_missing_after)}) : "
            f"{_format_symbol_preview(sentiment_missing_after)}"
        )
        LOGGER.warning(message)
        _safe_print(f"   {message}\n")

    ml_missing_before = _extract_symbols_for_log(getattr(ml_diagnostics, "missing_symbols_before", ()))
    if ml_mode != "off" and ml_missing_before:
        message = (
            f"⚠️ ML — symboles sans prédiction / modèle entraîné disponible avant fallback/rebuild ({len(ml_missing_before)}) : "
            f"{_format_symbol_preview(ml_missing_before)}"
        )
        LOGGER.warning(message)
        _safe_print(f"   {message}\n")

    ml_missing_after = _extract_symbols_for_log(getattr(ml_diagnostics, "missing_symbols_after", ()))
    if ml_mode != "off" and ml_missing_after:
        message = (
            f"⚠️ ML — symboles encore sans couverture prédictive après préparation ({len(ml_missing_after)}) : "
            f"{_format_symbol_preview(ml_missing_after)}"
        )
        LOGGER.warning(message)
        _safe_print(f"   {message}\n")


def _build_execution_broker_like_summary(
    *,
    signals_df,
    phase2_mode: str,
    phase3_mode: str,
    phase4_mode: str,
    phase5_mode: str,
    phase7_mode: str,
    phase3_execution_replay_result,
    phase4_protection_replay_result,
    phase5_watcher_replay_result,
    phase7_exit_lifecycle_result,
):
    import pandas as pd

    latest_execution_lifecycle_result = next(
        (
            result
            for result in (
                phase7_exit_lifecycle_result,
                phase5_watcher_replay_result,
                phase4_protection_replay_result,
                phase3_execution_replay_result,
            )
            if result is not None
        ),
        None,
    )
    if latest_execution_lifecycle_result is None:
        return None
    try:
        from backtesting.execution_broker_like import build_execution_broker_like_summary

        latest_signals_df = getattr(latest_execution_lifecycle_result, "signals_df", signals_df)
        if not isinstance(latest_signals_df, pd.DataFrame):
            latest_signals_df = signals_df if isinstance(signals_df, pd.DataFrame) else None

        return build_execution_broker_like_summary(
            signals_df=latest_signals_df,
            order_lifecycle_frame=getattr(latest_execution_lifecycle_result, "order_lifecycle_frame", None),
            broker_event_frame=getattr(
                latest_execution_lifecycle_result,
                "broker_event_frame",
                getattr(latest_execution_lifecycle_result, "event_frame", None),
            ),
            phase_modes={
                "phase2_mode": phase2_mode,
                "phase3_mode": phase3_mode,
                "phase4_mode": phase4_mode,
                "phase5_mode": phase5_mode,
                "phase7_mode": phase7_mode,
            },
            diagnostics={
                "phase3_execution_replay": dict(phase3_execution_replay_result.diagnostics) if phase3_execution_replay_result is not None else {},
                "phase4_protection_replay": dict(phase4_protection_replay_result.diagnostics) if phase4_protection_replay_result is not None else {},
                "phase5_watcher_replay": dict(phase5_watcher_replay_result.diagnostics) if phase5_watcher_replay_result is not None else {},
                "phase7_exit_lifecycle_replay": dict(phase7_exit_lifecycle_result.diagnostics) if phase7_exit_lifecycle_result is not None else {},
            },
        )
    except Exception:
        return None


def _build_backtest_component_details(
    *,
    ohlcv_df,
    bars_source_preflight: dict[str, object] | None = None,
    execution_pivoted,
    start_date: date,
    end_date: date,
    ohlcv_start: date,
    signals_df,
    phase2_mode: str,
    phase3_mode: str,
    phase4_mode: str,
    phase5_mode: str,
    phase7_mode: str,
    phase2_risk_result,
    phase2_execution_result,
    phase3_execution_replay_result,
    phase4_protection_replay_result,
    phase5_watcher_replay_result,
    phase7_exit_lifecycle_result,
) -> tuple[dict[str, dict[str, object]], dict[str, object] | None]:
    import pandas as pd

    bars_preflight_reasons = []
    if isinstance(bars_source_preflight, dict):
        raw_reasons = bars_source_preflight.get("degraded_reasons", [])
        if isinstance(raw_reasons, list):
            bars_preflight_reasons = list(raw_reasons)

    bars_component_details = {
        "enabled": True,
        "rows_loaded": int(len(ohlcv_df)),
        "symbols_loaded": int(ohlcv_df["symbol"].nunique()) if "symbol" in ohlcv_df.columns else 0,
        "requested_start_date": start_date.isoformat(),
        "requested_end_date": end_date.isoformat(),
        "loaded_start_date": str(pd.Timestamp(ohlcv_df["trade_date"].min()).date()) if "trade_date" in ohlcv_df.columns and not ohlcv_df.empty else None,
        "loaded_end_date": str(pd.Timestamp(ohlcv_df["trade_date"].max()).date()) if "trade_date" in ohlcv_df.columns and not ohlcv_df.empty else None,
        "warmup_start_date": ohlcv_start.isoformat(),
        "calendar_sessions_loaded": int(len(execution_pivoted["close"].index)),
        "bars_source_preflight": dict(bars_source_preflight or {}),
        "degraded_reasons": bars_preflight_reasons,
    }
    risk_component_details = {
        "enabled": phase2_risk_result is not None,
        "mode": phase2_mode,
        "diagnostics": dict(phase2_risk_result.diagnostics) if phase2_risk_result is not None else {},
    }
    execution_broker_like_summary = _build_execution_broker_like_summary(
        signals_df=signals_df,
        phase2_mode=phase2_mode,
        phase3_mode=phase3_mode,
        phase4_mode=phase4_mode,
        phase5_mode=phase5_mode,
        phase7_mode=phase7_mode,
        phase3_execution_replay_result=phase3_execution_replay_result,
        phase4_protection_replay_result=phase4_protection_replay_result,
        phase5_watcher_replay_result=phase5_watcher_replay_result,
        phase7_exit_lifecycle_result=phase7_exit_lifecycle_result,
    )
    execution_component_details = {
        "enabled": any(
            result is not None
            for result in (
                phase2_execution_result,
                phase3_execution_replay_result,
                phase4_protection_replay_result,
                phase5_watcher_replay_result,
                phase7_exit_lifecycle_result,
            )
        ),
        "phase2_mode": phase2_mode,
        "phase3_mode": phase3_mode,
        "phase4_mode": phase4_mode,
        "phase5_mode": phase5_mode,
        "phase7_mode": phase7_mode,
        "phase2_execution": dict(phase2_execution_result.diagnostics) if phase2_execution_result is not None else {},
        "phase3_execution_replay": (
            dict(phase3_execution_replay_result.diagnostics)
            if phase3_execution_replay_result is not None
            else {}
        ),
        "phase4_protection_replay": (
            dict(phase4_protection_replay_result.diagnostics)
            if phase4_protection_replay_result is not None
            else {}
        ),
        "phase5_watcher_replay": (
            dict(phase5_watcher_replay_result.diagnostics)
            if phase5_watcher_replay_result is not None
            else {}
        ),
        "phase7_exit_lifecycle_replay": (
            dict(phase7_exit_lifecycle_result.diagnostics)
            if phase7_exit_lifecycle_result is not None
            else {}
        ),
        "broker_like": execution_broker_like_summary or {},
    }
    return {
        "bars": bars_component_details,
        "risk": risk_component_details,
        "execution": execution_component_details,
    }, execution_broker_like_summary


def _build_backtest_common_params(
    *,
    args: argparse.Namespace,
    fees_pct: float,
    effective_preset,
    preset_source: str,
    preset_fingerprint: str,
    engine_mode: str,
    phase2_mode: str,
    phase3_mode: str,
    phase4_mode: str,
    phase5_mode: str,
    phase7_mode: str,
    ml_pit_strategy: str,
    dividends_received: float,
    trading_constraints,
    bt_config,
    microstructure_cfg,
    risk_overlay_cfg,
    phase2_risk_result,
    phase2_execution_result,
    phase3_execution_replay_result,
    phase4_protection_replay_result,
    phase5_watcher_replay_result,
    phase7_exit_lifecycle_result,
    ml_coverage_gate: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "start": args.start,
        "end": args.end,
        "equity": args.equity,
        "tp": args.tp,
        "ts": args.ts,
        "max_positions": args.max_positions,
        "commission_bps": float(args.commission_bps),
        "slippage_bps": float(args.slippage_bps),
        "execution_costs": {
            "commission_bps": float(args.commission_bps),
            "slippage_bps": float(args.slippage_bps),
            "total_cost_bps": float(args.commission_bps) + float(args.slippage_bps),
            "cost_model": "explicit_commission_plus_slippage",
            "microstructure_model": args.slippage_model,
        },
        "fees_pct": fees_pct,
        "fees": args.fees,
        "profile": getattr(args, "profile", "custom"),
        "capital_preset_key": effective_preset.key,
        "capital_preset_source": preset_source,
        "capital_preset_fingerprint": preset_fingerprint,
        "engine_mode": engine_mode,
        "phase2_mode": phase2_mode,
        "phase3_mode": phase3_mode,
        "phase4_mode": phase4_mode,
        "phase5_mode": phase5_mode,
        "phase7_mode": phase7_mode,
        "macro_pit_mode": getattr(args, "effective_macro_pit_mode", getattr(args, "macro_pit_mode", "yaml_default")),
        "fidelity_baseline_id": getattr(args, "fidelity_baseline_id", None),
        "fidelity_baseline_catalog": getattr(args, "fidelity_baseline_catalog", None),
        "ml_pit_strategy": ml_pit_strategy,
        "conviction_weights": {
            "source": "core.conviction",
            "score_weight": 0.40,
            "prediction_weight": 0.60,
        },
        "dividends_received": float(dividends_received),
        "account_type": trading_constraints.account_type,
        "pdt_rule": trading_constraints.pdt_rule,
        "effective_pdt_rule": trading_constraints.effective_pdt_rule,
        "swing_only": trading_constraints.swing_only,
        "cash_settlement_days": getattr(trading_constraints, "cash_settlement_days", None),
        "sentiment_lookback": args.sentiment_lookback,
        "ml_mode": args.ml_mode,
        "sentiment_mode": args.sentiment_mode,
        "artifacts_dir": args.artifacts_dir,
        "score_column": args.score_column,
        "walk_forward_artifacts_dir": args.walk_forward_artifacts_dir,
        "macro_missing_policy": getattr(args, "macro_missing_policy", None),
        "execution_timing": bt_config.execution_timing,
        "entry_price_source": "next_session_open",
        "no_save": args.no_save,
        "risk_free_rate": float(getattr(args, "risk_free_rate", 0.0) or 0.0),
        "microstructure": {
            "slippage_model": args.slippage_model,
            "slippage_base_bps": float(args.slippage_base_bps),
            "slippage_impact_coef": float(args.slippage_impact_coef),
            "initial_stop_pct": float(args.initial_stop_pct),
            "max_entry_gap_pct": float(args.max_entry_gap_pct),
            "intrabar_priority": args.intrabar_priority,
            "is_default": microstructure_cfg.is_default(),
        },
        "risk_overlay": {
            "sizing_mode": args.sizing_mode,
            "sizing_min_weight_pct": float(args.sizing_min_weight_pct),
            "sizing_max_weight_pct": float(args.sizing_max_weight_pct),
            "regime_filter_enabled": bool(args.regime_filter),
            "regime_sma_window": int(args.regime_sma_window),
            "regime_bear_threshold": float(args.regime_bear_threshold),
            "max_sector_exposure_pct": float(args.max_sector_exposure_pct),
            "max_portfolio_dd_pct": float(args.max_portfolio_dd_pct),
            "dd_recovery_pct": float(args.dd_recovery_pct),
            "dd_rolling_peak_window_days": int(args.dd_rolling_peak_window_days),
            "dd_degraded_allocation_pct": float(args.dd_degraded_allocation_pct),
            "target_annual_vol": (
                float(args.target_annual_vol) if args.target_annual_vol is not None else None
            ),
            "is_default": risk_overlay_cfg.is_default(),
        },
        "ml_coverage_gate": dict(ml_coverage_gate or {}) if ml_coverage_gate else {
            "enabled": False,
            "allowed": True,
            "required_ratio": (
                float(getattr(args, "min_ml_coverage_ratio", 0.0))
                if getattr(args, "min_ml_coverage_ratio", None) is not None
                else None
            ),
        },
        "phase2": {
            "enabled": phase2_mode != "off",
            "mode": phase2_mode,
            "risk_bridge": phase2_risk_result.diagnostics if phase2_risk_result is not None else None,
            "execution_bridge": phase2_execution_result.diagnostics if phase2_execution_result is not None else None,
            "execution_tca": phase2_execution_result.tca_summary if phase2_execution_result is not None else None,
        },
        "phase3": {
            "enabled": phase3_mode != "off",
            "mode": phase3_mode,
            "execution_replay": (
                phase3_execution_replay_result.diagnostics
                if phase3_execution_replay_result is not None
                else None
            ),
        },
        "phase4": {
            "enabled": phase4_mode != "off",
            "mode": phase4_mode,
            "protection_replay": (
                phase4_protection_replay_result.diagnostics
                if phase4_protection_replay_result is not None
                else None
            ),
        },
        "phase5": {
            "enabled": phase5_mode != "off",
            "mode": phase5_mode,
            "watcher_replay": (
                phase5_watcher_replay_result.diagnostics
                if phase5_watcher_replay_result is not None
                else None
            ),
        },
        "phase7": {
            "enabled": phase7_mode != "off",
            "mode": phase7_mode,
            "exit_lifecycle_replay": (
                phase7_exit_lifecycle_result.diagnostics
                if phase7_exit_lifecycle_result is not None
                else None
            ),
        },
    }


def _collect_compare_to_live_trade_dates(
    *,
    scores_df,
    research_signals_df,
    phase2_risk_result,
    phase2_execution_result,
):
    import pandas as pd

    compare_dates: set[pd.Timestamp] = set()
    for frame in (scores_df, research_signals_df):
        if isinstance(frame, pd.DataFrame) and not frame.empty and "trade_date" in frame.columns:
            compare_dates.update(
                pd.DatetimeIndex(pd.to_datetime(frame["trade_date"], errors="coerce").dropna().dt.normalize().tolist())
            )
    if phase2_risk_result is not None:
        for entry in phase2_risk_result.entries:
            snapshot_date = _coerce_date_value(getattr(entry, "score_snapshot_date", None))
            if snapshot_date is None:
                continue
            compare_dates.add(pd.Timestamp(snapshot_date).normalize())
    if phase2_execution_result is not None:
        for target in phase2_execution_result.targets:
            target_date = _coerce_date_value(getattr(target, "trade_date", None))
            if target_date is None:
                continue
            compare_dates.add(pd.Timestamp(target_date).normalize())
    return sorted(compare_dates)


def _build_compare_to_live_artifacts(
    *,
    engine,
    output_dir: Path,
    fidelity_manifest: dict[str, object],
    scores_df,
    research_signals_df,
    phase2_risk_result,
    phase2_execution_result,
    phase7_exit_lifecycle_result,
    phase2_mode: str,
) -> tuple[dict[str, str], dict[str, object] | None]:
    import pandas as pd

    try:
        from execution_engine.db_io import ExecutionRepository
        from risk_management.db_io import RiskRepository

        compare_dates = _collect_compare_to_live_trade_dates(
            scores_df=scores_df,
            research_signals_df=research_signals_df,
            phase2_risk_result=phase2_risk_result,
            phase2_execution_result=phase2_execution_result,
        )
        risk_repo = RiskRepository(engine)
        execution_repo = ExecutionRepository(engine)
        live_risk_decisions: dict[str, pd.DataFrame] = {}
        live_portfolio_targets: dict[str, list[object]] = {}
        live_execution_targets: dict[str, list[object]] = {}
        live_execution_fills: dict[str, pd.DataFrame] = {}
        live_position_lots: dict[str, pd.DataFrame] = {}
        live_compare_context: dict[str, dict[str, object]] = {}
        for trade_date in compare_dates:
            trade_day = _coerce_date_value(trade_date)
            if trade_day is None:
                continue
            trade_key = trade_day.isoformat()
            live_risk_decisions[trade_key] = risk_repo.load_risk_decisions_for_date(
                trade_day,
                account_id="default",
            )
            risk_run_id = None
            if not live_risk_decisions[trade_key].empty and "run_id" in live_risk_decisions[trade_key].columns:
                risk_run_values = live_risk_decisions[trade_key]["run_id"].dropna().astype(str)
                if not risk_run_values.empty:
                    risk_run_id = str(risk_run_values.iloc[0]).strip() or None
            exec_context = None
            match_basis = "trade_date_latest"
            if risk_run_id:
                exec_context = execution_repo.load_execution_run_context_for_risk_run_id(
                    risk_run_id=risk_run_id,
                    account_id="default",
                    trade_date=trade_day,
                )
                if exec_context is not None:
                    match_basis = "risk_run_id"
            if exec_context is None:
                fallback_exec_run_id = execution_repo.load_latest_execution_run_id_for_date(
                    trade_date=trade_day,
                    account_id="default",
                )
                if fallback_exec_run_id is not None:
                    exec_context = execution_repo.load_execution_run_context(exec_run_id=fallback_exec_run_id)
                    if exec_context is not None:
                        match_basis = "exec_run_id_fallback"
            risk_decisions_basis = "trade_date_latest"
            exec_risk_run_id = str(exec_context.get("risk_run_id") or "").strip() if isinstance(exec_context, dict) else ""
            if exec_risk_run_id:
                risk_run_id = exec_risk_run_id
            if risk_run_id:
                try:
                    exact_risk_decisions = risk_repo.load_risk_decisions_for_run_id(
                        risk_run_id,
                        account_id="default",
                    )
                except Exception:
                    exact_risk_decisions = pd.DataFrame()
                if isinstance(exact_risk_decisions, pd.DataFrame) and not exact_risk_decisions.empty:
                    live_risk_decisions[trade_key] = exact_risk_decisions
                    risk_decisions_basis = "risk_run_id"
            try:
                live_portfolio_targets[trade_key] = cast(
                    list[object],
                    execution_repo.load_portfolio_targets(
                        risk_run_id=risk_run_id,
                        trade_date=trade_day,
                        account_id="default",
                    ),
                )
            except Exception:
                live_portfolio_targets[trade_key] = []
            try:
                exec_run_id = str(exec_context.get("exec_run_id") or "").strip() if isinstance(exec_context, dict) else ""
                if exec_run_id:
                    live_execution_targets[trade_key] = cast(
                        list[object],
                        execution_repo.load_execution_targets_snapshot(exec_run_id=exec_run_id),
                    )
                    live_execution_fills[trade_key] = execution_repo.load_execution_fills_for_run(
                        exec_run_id=exec_run_id,
                        account_id="default",
                    )
                    live_position_lots[trade_key] = execution_repo.load_execution_position_lots_for_open_run(
                        open_exec_run_id=exec_run_id,
                        account_id="default",
                    )
                else:
                    live_execution_targets[trade_key] = cast(
                        list[object],
                        execution_repo.load_latest_execution_targets_snapshot_for_date(
                            trade_date=trade_day,
                            account_id="default",
                        ),
                    )
                    live_execution_fills[trade_key] = pd.DataFrame()
                    live_position_lots[trade_key] = pd.DataFrame()
            except Exception:
                live_execution_targets[trade_key] = []
                live_execution_fills[trade_key] = pd.DataFrame()
                live_position_lots[trade_key] = pd.DataFrame()
            live_compare_context[trade_key] = {
                "trade_date": trade_key,
                "risk_run_id": risk_run_id,
                "exec_run_id": exec_context.get("exec_run_id") if isinstance(exec_context, dict) else None,
                "match_basis": match_basis,
                "risk_decisions_basis": risk_decisions_basis,
                "portfolio_targets_basis": "risk_run_id" if risk_run_id else "trade_date_latest",
            }

        compare_to_live_summary = build_compare_to_live_summary(
            fidelity_manifest=fidelity_manifest,
            research_signals_df=research_signals_df,
            risk_entries=phase2_risk_result.entries if phase2_risk_result is not None else (),
            execution_targets=phase2_execution_result.targets if phase2_execution_result is not None else (),
            execution_fills=getattr(phase2_execution_result, "fills", ()) if phase2_execution_result is not None else (),
            exit_signals_df=getattr(phase7_exit_lifecycle_result, "signals_df", pd.DataFrame()) if phase7_exit_lifecycle_result is not None else pd.DataFrame(),
            live_risk_decisions=live_risk_decisions,
            live_portfolio_targets=live_portfolio_targets,
            live_execution_targets=live_execution_targets,
            live_execution_fills=live_execution_fills,
            live_position_lots=live_position_lots,
            live_compare_context=live_compare_context,
            account_id="default",
            phase2_mode=phase2_mode,
        )
        return {
            key: str(path)
            for key, path in save_compare_to_live_summary(compare_to_live_summary, output_dir).items()
        }, compare_to_live_summary
    except Exception:
        LOGGER.warning("Compare-to-live Sprint 5 ignoré (données live indisponibles ?).", exc_info=True)
        return {}, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backtesting",
        description="Backtest intégré Alpha Trade (simulateur custom PIT)",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Lancer un backtest complet")
    run_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    run_p.add_argument("--end", default=str(date.today()), help="Date de fin (YYYY-MM-DD)")
    run_p.add_argument("--equity", type=float, default=100_000, help="Capital initial ($)")
    run_p.add_argument(
        "--capital-preset-key",
        default=None,
        help="Preset capital à utiliser pour charger les snapshots PIT et, si non contredit, préremplir les contraintes compte/positions.",
    )
    run_p.add_argument("--tp", type=float, default=0.08, help="Take-profit %% (défaut 0.08)")
    run_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %% (défaut 0.05)")
    run_p.add_argument("--max-positions", type=int, default=20, help="Positions max simultanées")
    run_p.add_argument(
        "--fees",
        type=float,
        default=None,
        help="DÉPRÉCIÉ — utiliser --commission-bps + --slippage-bps. "
        "Conservé pour rétro-compat : si fourni, écrase commission/slippage.",
    )
    run_p.add_argument(
        "--commission-bps",
        type=float,
        default=5.0,
        help="Commission par trade en bps (défaut: 5.0 = 5bps).",
    )
    run_p.add_argument(
        "--slippage-bps",
        type=float,
        default=5.0,
        help="Slippage simulé par trade en bps (défaut: 5.0 = 5bps).",
    )
    run_p.add_argument(
        "--profile",
        choices=["strict_swing_cash", "swing_cash_aggressive", "production-parity", "custom"],
        default="custom",
        help="Profil consolidé (Phase 6.1.e). Les flags CLI explicites overridrent toujours.",
    )
    run_p.add_argument(
        "--account-type",
        choices=["margin", "cash"],
        default="margin",
        help="Type de compte simulé: margin|cash",
    )
    run_p.add_argument(
    run_p.add_argument(
        "--swing-only",
        action="store_true",
        help="Interdire toute sortie le jour même de l'entrée",
    )
    run_p.add_argument(
        "--cash-settlement-days",
        type=int,
        default=1,
        help="Nombre de jours de règlement-livraison simulés pour un compte cash (défaut: 1).",
    )
    run_p.add_argument("--sentiment-lookback", type=int, default=365, help="Lookback sentiment (jours)")
    run_p.add_argument("--no-save", action="store_true", help="Ne pas sauvegarder les artefacts")
    run_p.add_argument(
        "--ml-mode",
        choices=["auto", "off", "rebuild-missing"],
        default="auto",
        help="Gestion des prédictions ML manquantes: auto|off|rebuild-missing",
    )
    run_p.add_argument(
        "--sentiment-mode",
        choices=["auto", "off", "rebuild-missing"],
        default="auto",
        help="Gestion du sentiment manquant: auto|off|rebuild-missing",
    )
    run_p.add_argument(
        "--artifacts-dir",
        default="artifacts/models",
        help="Répertoire des artefacts modèles pour reconstruire les prédictions ML",
    )
    run_p.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire cible pour sauvegarder les artefacts et le rapport structurés du run",
    )
    run_p.add_argument(
        "--score-column",
        choices=["auto", "final_score_walk_forward", "final_score_sentiment", "final_score"],
        default="auto",
        help="Colonne de score à privilégier pour le replay (défaut: auto).",
    )
    run_p.add_argument(
        "--walk-forward-artifacts-dir",
        default=None,
        help="Répertoire racine où chercher explicitement les meilleurs poids walk-forward à appliquer au backtest standard.",
    )
    run_p.add_argument(
        "--engine-mode",
        choices=["research", "pipeline"],
        default="research",
        help="Mode du moteur de backtest: research (rapide, tolérant) ou pipeline (strict PIT, diagnostics renforcés).",
    )
    run_p.add_argument(
        "--scores-pit-mode",
        choices=["exact", "asof_latest"],
        default="exact",
        help="Résolution PIT des scores: `exact` exige les snapshots du jour, `asof_latest` réutilise le dernier snapshot <= trade_date.",
    )
    run_p.add_argument(
        "--macro-pit-mode",
        choices=["yaml_default", "asof_inclusive", "j_minus_1_strict"],
        default="yaml_default",
        help="Politique PIT explicite pour la macro en backtest. `yaml_default` lit `market_regimes.macro_pit_mode_backtest`, `asof_inclusive` autorise <= J, `j_minus_1_strict` force strictement J-1.",
    )
    run_p.add_argument(
        "--ml-pit-strategy",
        choices=["auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"],
        default="auto",
        help="Stratégie PIT explicite pour la composante ML. `auto` conserve le comportement historique, `walk-forward-train-then-predict` fail-fast tant que non supporté.",
    )
    run_p.add_argument(
        "--phase2-mode",
        choices=["off", "risk", "risk_execution"],
        default="off",
        help="Phase 2 opt-in: `risk` branche le vrai risk_management pour générer les cibles, `risk_execution` ajoute en plus une simulation d'intents/fills via execution_engine. Par défaut `off` pour zéro régression.",
    )
    run_p.add_argument(
        "--phase3-mode",
        choices=["off", "execution_replay"],
        default="off",
        help="Phase 3 opt-in: `execution_replay` réinjecte chronologiquement les quantités issues du bridge risk+execution dans le moteur de backtest. Exige `--phase2-mode risk_execution`.",
    )
    run_p.add_argument(
        "--phase4-mode",
        choices=["off", "protection_replay"],
        default="off",
        help="Phase 4 opt-in: `protection_replay` rejoue les child intents de protection (TP/initial stop/trailing) dans le moteur de backtest. Exige `--phase3-mode execution_replay`.",
    )
    run_p.add_argument(
        "--phase5-mode",
        choices=["off", "watcher_replay"],
        default="off",
        help="Phase 5 opt-in: `watcher_replay` rejoue les transitions du watcher de protection (trigger -> promotion trailing) dans le moteur de backtest. Exige `--phase4-mode protection_replay`.",
    )
    run_p.add_argument(
        "--phase7-mode",
        choices=["off", "exit_lifecycle_replay"],
        default="off",
        help="Phase 7 opt-in: `exit_lifecycle_replay` rejoue explicitement l'issue terminale des child orders (exit + annulation OCO du sibling) dans le moteur de backtest. Exige `--phase5-mode watcher_replay`.",
    )
    macro_missing_group = run_p.add_mutually_exclusive_group()
    macro_missing_group.add_argument(
        "--allow-neutral-fallback-on-missing-macro-data",
        dest="macro_missing_policy",
        action="store_const",
        const="allow",
        help="Continue le backtest si la macro est indisponible et marque explicitement la séance en data_quality=missing.",
    )
    macro_missing_group.add_argument(
        "--fail-on-missing-macro-data",
        dest="macro_missing_policy",
        action="store_const",
        const="fail",
        help="Échoue explicitement si une donnée macro requise est indisponible.",
    )
    run_p.set_defaults(macro_missing_policy=None)
    run_p.add_argument(
        "--fidelity-baseline-id",
        default=None,
        help="Identifiant optionnel d'une baseline de non-régression fidélité à comparer au run courant.",
    )
    run_p.add_argument(
        "--fidelity-baseline-catalog",
        default=None,
        help="Chemin optionnel vers le catalogue JSON des baselines fidélité. Utilisé seulement si une comparaison baseline est demandée.",
    )
    # Phase A.6 (refactor) — risk-free rate annualisé pour Sharpe/Sortino.
    run_p.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.0,
        help="Taux sans risque annualisé (ex 0.04 = 4%%) déduit des returns avant Sharpe/Sortino.",
    )
    # Phase A.4 — seed pour reproductibilité (consigné dans run_metadata).
    run_p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed reproductibilité (consignée dans report.json[run_metadata]).",
    )

    # Sprint S3 / A-010 — cache Parquet pour accélérer les re-runs.
    run_p.add_argument(
        "--use-cache",
        action="store_true",
        default=False,
        help="Active le cache Parquet local pour OHLCV/scores/predictions (artifacts/backtest_cache/). "
        "Accélère les re-runs sur le même jeu de données. Ignorer si le dataset a changé.",
    )
    run_p.add_argument(
        "--cache-dir",
        default="artifacts/backtest_cache",
        help="Répertoire du cache Parquet (défaut: artifacts/backtest_cache/).",
    )

    # Sprint S3 / A-011 — bootstrap trades + analyse de sensibilité.
    run_p.add_argument(
        "--bootstrap-samples",
        type=int,
        default=0,
        help="Nombre d'itérations Monte Carlo pour le bootstrap des trades (G1). "
        "0 = désactivé. Recommandé : 1000.",
    )
    run_p.add_argument(
        "--sensitivity-analysis",
        action="store_true",
        default=False,
        help="Active l'analyse de sensibilité ±10%% sur tp/ts/fees_pct (G2). "
        "Résultats affichés après le rapport principal.",
    )

    # ------------------------------------------------------------------
    # Phase B (refactor) — micro-structure (slippage volume-aware,
    # initial stop dur, gap filter, intra-bar priority).
    # ------------------------------------------------------------------
    run_p.add_argument(
        "--slippage-model",
        choices=["fixed", "linear", "sqrt"],
        default="fixed",
        help="Modèle de slippage volume-aware additionnel (Phase B.1). 'fixed' = neutre.",
    )
    run_p.add_argument(
        "--slippage-base-bps",
        type=float,
        default=0.0,
        help="Composante fixe (bps) du slippage volume-aware additionnel.",
    )
    run_p.add_argument(
        "--slippage-impact-coef",
        type=float,
        default=0.0,
        help="Coefficient d'impact (bps) appliqué à size/ADV (Phase B.1).",
    )
    run_p.add_argument(
        "--initial-stop-pct",
        type=float,
        default=0.0,
        help="Stop-loss initial dur en fraction (Phase B.2). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--max-entry-gap-pct",
        type=float,
        default=0.0,
        help="Skip d'entrée si |open - prev_close| / prev_close > seuil (Phase B.3). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--intrabar-priority",
        choices=["conservative", "tp_first", "ts_first", "random"],
        default="conservative",
        help="Politique de résolution intra-bar TP/TS (Phase B.4). conservative = TS prioritaire (legacy).",
    )

    # ------------------------------------------------------------------
    # Phase C (refactor) — risk overlays (sizing, regime, sectoral, DD breaker, vol-target).
    # ------------------------------------------------------------------
    run_p.add_argument(
        "--sizing-mode",
        choices=["equal_weight", "conviction_weighted"],
        default="equal_weight",
        help="Mode de sizing du portefeuille (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-min-weight-pct",
        type=float,
        default=0.005,
        help="Poids min par position quand sizing=conviction_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-max-weight-pct",
        type=float,
        default=0.20,
        help="Poids max par position quand sizing=conviction_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--regime-filter",
        action="store_true",
        help="Active le filtre régime SMA200 sur le benchmark (Phase C.3).",
    )
    run_p.add_argument(
        "--regime-sma-window",
        type=int,
        default=200,
        help="Fenêtre SMA pour le filtre régime (défaut 200).",
    )
    run_p.add_argument(
        "--regime-bear-threshold",
        type=float,
        default=-0.02,
        help="Seuil bear (distance vs SMA) pour bloquer les nouvelles entrées.",
    )
    run_p.add_argument(
        "--max-sector-exposure-pct",
        type=float,
        default=0.0,
        help="Cap d'exposition par secteur en fraction (Phase C.4). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--max-portfolio-dd-pct",
        type=float,
        default=0.0,
        help="Drawdown max avant coupe-circuit nouvelles entrées (Phase C.5). 0.0 = désactivé.",
    )
    run_p.add_argument(
        "--dd-recovery-pct",
        type=float,
        default=0.95,
        help="Seuil de recovery pour rouvrir les entrées après coupe-circuit DD (Phase C.5).",
    )
    run_p.add_argument(
        "--dd-rolling-peak-window-days",
        type=int,
        default=252,
        help="Fenêtre (jours de bourse) du pic roulant utilisé par le coupe-circuit DD (Phase C.5).",
    )
    run_p.add_argument(
        "--dd-degraded-allocation-pct",
        type=float,
        default=0.02,
        help="Allocation max par entrée quand le coupe-circuit DD est trippé (0.0 = blocage total).",
    )
    run_p.add_argument(
        "--target-annual-vol",
        type=float,
        default=None,
        help="Cible de volatilité annualisée portefeuille (Phase C.2). Désactivé si non fourni.",
    )
    run_p.add_argument(
        "--min-ml-coverage-ratio",
        type=float,
        default=None,
        help="Seuil minimal de couverture ML autorisé en mode pipeline (0.80 = 80%%). 0 ou None = désactivé.",
    )

    # --- backfill-scores-history ---
    backfill_p = sub.add_parser(
        "backfill-scores-history",
        help="Reconstruire stock_scores_history en point-in-time depuis les bars déjà en base",
    )
    backfill_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    backfill_p.add_argument("--end", default=None, help="Date de fin explicite (YYYY-MM-DD)")
    backfill_p.add_argument("--capital", type=float, default=None, help="Capital de référence pour résoudre automatiquement un preset")
    backfill_p.add_argument("--capital-preset-key", default=None, help="Preset capital explicite à utiliser pour reconstruire les snapshots PIT")
    backfill_p.add_argument("--overwrite-existing", action="store_true", help="Recalculer aussi les dates déjà historisées")
    backfill_p.add_argument("--limit-days", type=int, default=None, help="Limiter à N séances (test progressif)")
    backfill_p.add_argument("--chunk-size", type=int, default=1000, help="Taille des chunks symboles screener/scanner")
    backfill_p.add_argument("--selection-size", type=int, default=100, help="Nombre final de candidats selector par séance")
    backfill_p.add_argument("--screener-workers", type=int, default=4, help="Nombre de workers ProcessPool pour le screener PIT")

    # --- diagnose-screener ---
    diag_p = sub.add_parser(
        "diagnose-screener",
        help="Mesurer l'impact PIT des paramètres screener jusqu'au portefeuille cible",
    )
    diag_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    diag_p.add_argument("--end", default=str(date.today()), help="Date de fin (YYYY-MM-DD)")
    diag_p.add_argument("--limit-days", type=int, default=None, help="Limiter à N séances (validation incrémentale)")
    diag_p.add_argument("--mode", choices=["oat", "grid"], default="oat", help="Balayage one-at-a-time ou grille complète")
    diag_p.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks symboles screener/scanner")
    diag_p.add_argument("--selection-size", type=int, default=100, help="Nombre final de candidats selector par séance")
    diag_p.add_argument("--max-positions", type=int, default=20, help="Nombre maximum de positions dans le portefeuille cible")
    diag_p.add_argument("--screener-workers", type=int, default=None, help="Nombre de workers ProcessPool pour le screener PIT")
    diag_p.add_argument("--max-scenarios", type=int, default=64, help="Garde-fou sur le nombre total de scénarios en mode grid")
    diag_p.add_argument(
        "--rs-values",
        default="100,102,105",
        help="Liste CSV des seuils min_relative_strength_index à tester",
    )
    diag_p.add_argument(
        "--range-lookback-values",
        default="252,504,756",
        help="Liste CSV des lookbacks historical_range_lookback_days à tester",
    )
    diag_p.add_argument(
        "--historical-range-score-values",
        default="65,70,75",
        help="Liste CSV des seuils min_historical_range_score à tester",
    )
    diag_p.add_argument(
        "--liquidity-threshold-values",
        default="20000000,30000000,40000000",
        help="Liste CSV des seuils liquidity_threshold_usd à tester",
    )
    diag_p.add_argument(
        "--output-dir",
        default="artifacts/screener_diagnostics",
        help="Répertoire cible pour les CSV/JSON diagnostics",
    )
    diag_p.add_argument(
        "--holdout-train-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre d'entraînement (YYYY-MM-DD). Active la validation hold-out.",
    )
    diag_p.add_argument(
        "--holdout-test-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre de test (YYYY-MM-DD).",
    )

    # --- recommend-screener ---
    recommend_p = sub.add_parser(
        "recommend-screener",
        help="Analyser summary_metrics.csv et recommander automatiquement le meilleur compromis",
    )
    recommend_p.add_argument(
        "--input-dir",
        default="artifacts/screener_diagnostics",
        help="Répertoire contenant summary_metrics.csv et éventuellement daily_metrics.csv",
    )
    recommend_p.add_argument(
        "--summary-csv",
        default=None,
        help="Chemin explicite vers un summary_metrics.csv à analyser",
    )
    recommend_p.add_argument(
        "--daily-csv",
        default=None,
        help="Chemin explicite vers un daily_metrics.csv pour enrichir l'analyse de robustesse",
    )
    recommend_p.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire cible pour scenario_recommendations.csv et recommendation_summary.json",
    )
    recommend_p.add_argument(
        "--baseline-name",
        default=None,
        help="Nom explicite du scénario baseline si l'auto-détection n'est pas suffisante",
    )
    recommend_p.add_argument(
        "--target-horizon",
        type=int,
        default=20,
        help="Horizon forward prioritaire pour l'analyse du compromis (défaut: 20)",
    )
    recommend_p.add_argument(
        "--holdout-train-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre d'entraînement (YYYY-MM-DD). Active la validation hold-out.",
    )
    recommend_p.add_argument(
        "--holdout-test-end",
        default=None,
        help="Phase 6.1.d — fin de la fenêtre de test (YYYY-MM-DD).",
    )

    calibrate_p = sub.add_parser(
        "calibrate-sentiment-weights",
        help="Calibrer les poids sentiment/macro à partir de stock_scores_history et des forward returns.",
    )
    calibrate_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    calibrate_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    calibrate_p.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour pour mesurer le spread")
    calibrate_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    calibrate_p.add_argument(
        "--output-dir",
        default="artifacts/sentiment_calibration",
        help="Répertoire cible pour les artefacts de calibration",
    )
    calibrate_p.add_argument(
        "--all-symbols",
        action="store_true",
        help="Utiliser tout l'univers historisé et pas seulement les candidats",
    )

    walk_forward_p = sub.add_parser(
        "walk-forward-sentiment",
        help="Calibration walk-forward stricte des poids sentiment/macro avec backtest portefeuille hors échantillon.",
    )
    walk_forward_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    walk_forward_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    walk_forward_p.add_argument("--top-n", type=int, default=20, help="Nombre de titres retenus pour les métriques de calibration")
    walk_forward_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    walk_forward_p.add_argument("--min-train-days", type=int, default=252, help="Séances minimales d'entraînement par fold")
    walk_forward_p.add_argument("--test-days", type=int, default=63, help="Séances hors échantillon par fold")
    walk_forward_p.add_argument("--step-days", type=int, default=None, help="Décalage entre folds (défaut = test-days)")
    walk_forward_p.add_argument("--max-positions", type=int, default=20, help="Nombre maximal de positions simultanées")
    walk_forward_p.add_argument("--equity", type=float, default=100_000, help="Capital initial ($)")
    walk_forward_p.add_argument("--tp", type=float, default=0.08, help="Take-profit %%)")
    walk_forward_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %%)")
    walk_forward_p.add_argument("--fees", type=float, default=0.001, help="Frais par trade (défaut 0.1%%)")
    walk_forward_p.add_argument(
        "--output-dir",
        default="artifacts/sentiment_walk_forward",
        help="Répertoire cible pour les artefacts walk-forward",
    )
    walk_forward_p.add_argument(
        "--all-symbols",
        action="store_true",
        help="Utiliser tout l'univers historisé et pas seulement les candidats",
    )

    return parser


def _explicit_flags(argv: list[str]) -> set[str]:
    """Retourne les noms d'attributs argparse explicitement passés sur la ligne de commande."""
    explicit: set[str] = set()
    mapping = {
        "--tp": "tp",
        "--ts": "ts",
        "--max-positions": "max_positions",
        "--chunk-size": "chunk_size",
        "--selection-size": "selection_size",
        "--commission-bps": "commission_bps",
        "--slippage-bps": "slippage_bps",
        "--account-type": "account_type",