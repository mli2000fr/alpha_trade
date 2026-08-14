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
import json
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


def _parse_sector_multipliers_json(raw: str | None) -> dict[str, float] | None:
    """Parse ``--sector-multipliers-json`` (JSON {secteur: facteur} ou @fichier)."""
    if not raw or not raw.strip():
        return None
    text_value = raw.strip()
    if text_value.startswith("@"):
        try:
            text_value = Path(text_value[1:]).read_text(encoding="utf-8")
        except Exception as exc:
            raise argparse.ArgumentTypeError(f"--sector-multipliers-json: fichier illisible : {exc}") from exc
    try:
        payload = json.loads(text_value)
        if not isinstance(payload, dict):
            raise ValueError("attendu un objet JSON {secteur: facteur}")
        multipliers = {str(k).strip(): float(v) for k, v in payload.items() if str(k).strip()}
        return multipliers or None
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"--sector-multipliers-json invalide : {exc}") from exc


def _load_sector_map_for_sizing(engine: object) -> dict[str, str]:
    """Charge le mapping symbole → secteur (stock_metadata) pour le sizing sectoriel."""
    try:
        from modelFactory.cross_sectional import _load_sector_mapping

        return _load_sector_mapping(engine)
    except Exception:
        LOGGER.warning("_load_sector_map_for_sizing: mapping indisponible → sizing sectoriel inactif", exc_info=True)
        return {}


def _load_benchmark_close(
    engine: object,
    start_date: date,
    end_date: date,
    *,
    benchmark_symbol: str = "SPY",
    warmup_days: int = 400,
) -> pd.Series | None:
    """Charge le close du benchmark (SPY) depuis stock_bars_daily, avec warmup.

    Utilisé par le filtre régime (Phase C.3) et l'overlay bull strict (P2-3).
    Retourne une Series indexée par Timestamp, ou None si indisponible.
    """
    import pandas as _pd
    from sqlalchemy import text as _text

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                _text(
                    "SELECT `date`, COALESCE(adj_close, `close`) AS px "
                    "FROM stock_bars_daily "
                    "WHERE symbol = :sym AND data_source = 'eodhd_eod' "
                    "AND `date` >= :start_date AND `date` <= :end_date "
                    "ORDER BY `date` ASC"
                ),
                {
                    "sym": benchmark_symbol,
                    "start_date": start_date - timedelta(days=warmup_days),
                    "end_date": end_date,
                },
            ).all()
        if not rows:
            LOGGER.warning("_load_benchmark_close: aucune barre %s eodhd_eod trouvée.", benchmark_symbol)
            return None
        series = _pd.Series(
            [float(px) for _, px in rows],
            index=_pd.to_datetime([d for d, _ in rows], utc=False),
            dtype=float,
        )
        series = series[~series.index.duplicated(keep="last")].sort_index()
        return series
    except Exception:
        LOGGER.warning("_load_benchmark_close: benchmark indisponible → overlay régime/bull-strict inactifs.", exc_info=True)
        return None


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
        "atr_ts": float(getattr(args, "atr_ts", 0.0) or 0.0),
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
        "swing_only": trading_constraints.swing_only,
        "cash_settlement_days": getattr(trading_constraints, "cash_settlement_days", None),
        "allow_fractional_shares": bool(getattr(args, "allow_fractional_shares", False)),
        "sentiment_lookback": args.sentiment_lookback,
        "ml_mode": args.ml_mode,
        "ml_batch_id": args.ml_batch_id,
        "sentiment_mode": args.sentiment_mode,
        "artifacts_dir": args.artifacts_dir,
        "config_path": getattr(args, "config_path", None),
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
        "time_stop": {
            "enabled": bool(getattr(bt_config, "time_stop_enabled", False)),
            "max_business_days": int(getattr(bt_config, "time_stop_max_business_days", 8)),
            "min_tp_progress_ratio": float(getattr(bt_config, "time_stop_min_tp_progress_ratio", 0.5)),
            "near_zero_return_pct": float(getattr(bt_config, "time_stop_near_zero_return_pct", 0.005)),
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
            "dd_regime_ramp_up_enabled": bool(args.dd_regime_ramp_up_enabled),
            "dd_regime_ramp_up_pct_per_day": float(args.dd_regime_ramp_up_pct_per_day),
            "dd_regime_ramp_up_max_pct": float(args.dd_regime_ramp_up_max_pct),
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
    run_p.add_argument("--tp", type=float, default=0.12, help="Take-profit %% (défaut 0.12)")
    run_p.add_argument("--ts", type=float, default=0.07, help="Trailing stop %% (défaut 0.07)")
    run_p.add_argument(
        "--ts-long", type=float, default=None,
        help="Trailing stop %% pour les LONGS uniquement (None = --ts). Plancher : n'élargit jamais l'autre jambe (P2-4).",
    )
    run_p.add_argument(
        "--ts-short", type=float, default=None,
        help="Trailing stop %% pour les SHORTS uniquement (None = --ts). Plancher : n'élargit jamais l'autre jambe (P2-4).",
    )
    run_p.add_argument(
        "--atr-risk-stop-multiple", type=float, default=0.0,
        help="Fidélité live (P2-4) : si > 0, dérive risk_per_share = entry_price × atr_pct_20 × multiple "
             "(comme portfolio_builder, longs ET shorts) quand le replay ne fournit ni stop_price_initial ni "
             "risk_per_share. 0 = désactivé (legacy : trailing fixe --ts).",
    )
    run_p.add_argument(
        "--tp-atr-multiple", type=float, default=0.0,
        help="P2-4 : TP de production = min(ATR × multiple, prix × --tp-max-pct). 0 = legacy (max(12%% fixe, 2R)).",
    )
    run_p.add_argument(
        "--tp-max-pct", type=float, default=0.0,
        help="P2-4 : plafond TP en fraction du prix (prod 0.07). Requiert --tp-atr-multiple > 0.",
    )
    run_p.add_argument(
        "--use-canonical-costs", action="store_true", default=False,
        help="Modèle de coûts canonique (spread 5bps, comm 1bps, slippage 2bps, borrow 0.3%%/an) — parité label/simulateur.",
    )
    run_p.add_argument(
        "--atr-ts", type=float, default=0.0,
        help="Multiplicateur ATR pour trailing stop adaptatif (0 = désactivé, utilise --ts fixe). "
             "Ex: 2.0 → stop = peak − 2×ATR_20. Le stop le plus large des deux (fixe vs ATR) est utilisé.",
    )
    run_p.add_argument(
        "--use-live-protection-logic",
        dest="use_live_protection_logic",
        action="store_true",
        default=True,
        help="Utilise la logique live pour TP/SL/trailing (par défaut).",
    )
    run_p.add_argument(
        "--use-fixed-protection-logic",
        dest="use_live_protection_logic",
        action="store_false",
        help="Force la logique historique fixe (TP/TS + initial_stop_pct).",
    )
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
        "--swing-only",
        action="store_true",
        help="Interdire toute sortie le jour même de l'entrée",
    )
    run_p.add_argument(
        "--allow-fractional-shares",
        action="store_true",
        default=False,
        help="Active les quantités fractionnaires côté replay/simulateur quand le moteur le supporte.",
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
        "--filter-no-ml",
        action="store_true",
        help="Exclure les candidats sans modèle ML entraîné (pas de predicted_proba dans model_predictions).",
    )
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
        "--ml-batch-id",
        default=None,
        help="Campagne ML explicitement utilisée pour --ml-mode rebuild-missing.",
    )
    run_p.add_argument(
        "--config-path",
        default=None,
        help="Chemin YAML alternatif pour charger la configuration runtime (notamment `market_regimes`) sans modifier `config.yaml`.",
    )
    run_p.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire cible pour sauvegarder les artefacts et le rapport structurés du run",
    )
    # P2 (2026-06-25) : persistence cross-run des trackers de concentration
    run_p.add_argument(
        "--tracker-state",
        default=None,
        help="Chemin vers un fichier tracker_state.json à charger avant le run "
        "(persistance cross-run des SymbolTradeTracker / ConsecutiveLossTracker / BreakoutConfirmationTracker).",
    )
    run_p.add_argument(
        "--load-tracker-state",
        action="store_true",
        default=False,
        help="Charge le tracker state depuis artifacts/backtesting/tracker_state.json (raccourci pour --tracker-state).",
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
    # Sprint S11 : activé par défaut, --no-cache pour désactiver.
    run_p.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Désactive le cache Parquet local (artifacts/backtest_cache/). "
        "Par défaut le cache est actif pour accélérer les re-runs.",
    )
    run_p.add_argument(
        "--cache-dir",
        default="artifacts/backtest_cache",
        help="Répertoire du cache Parquet (défaut: artifacts/backtest_cache/).",
    )

    # Sprint S3 / A-011 → Sprint S11 : bootstrap trades activé par défaut.
    run_p.add_argument(
        "--bootstrap-samples",
        type=int,
        default=500,
        help="Nombre d'itérations Monte Carlo pour le bootstrap des trades (G1). "
        "0 = désactivé. Défaut S11 : 500.",
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
    # Sprint S11 : microstructure activée par défaut avec des valeurs réalistes.
    run_p.add_argument(
        "--slippage-model",
        choices=["fixed", "linear", "sqrt"],
        default="sqrt",
        help="Modèle de slippage volume-aware additionnel (Phase B.1). 'sqrt' = Almgren-Chriss par défaut (S11).",
    )
    run_p.add_argument(
        "--slippage-base-bps",
        type=float,
        default=2.0,
        help="Composante fixe (bps) du slippage volume-aware additionnel. Défaut S11 : 2 bps.",
    )
    run_p.add_argument(
        "--slippage-impact-coef",
        type=float,
        default=5.0,
        help="Coefficient d'impact (bps) appliqué à sqrt(size/ADV) (Phase B.1). Défaut S11 : 5 bps.",
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
        default=0.03,
        help="Skip d'entrée si |open - prev_close| / prev_close > seuil (Phase B.3). Défaut S11 : 3%%.",
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
    # P4 — modèle d'exécution intraday
    run_p.add_argument(
        "--execution-model",
        choices=["next_open", "arrival_price", "twap", "vwap"],
        default="next_open",
        help="Modèle de prix d'exécution intraday (P4). next_open = legacy. "
        "arrival_price = open + slippage directionnel. twap/vwap = prix moyen journalier.",
    )
    run_p.add_argument(
        "--execution-split-threshold-adv-pct",
        type=float,
        default=0.0,
        help="Seuil ADV (ex: 0.01 = 1%%) au-delà duquel l'ordre est échelonné (P4). 0 = désactivé.",
    )
    run_p.add_argument(
        "--execution-arrival-slippage-factor",
        type=float,
        default=0.5,
        help="Facteur de slippage pour arrival_price (P4). 0.5 = demi-range journalière.",
    )
    # P3 — commission tiercée
    run_p.add_argument(
        "--use-tiered-commission",
        action="store_true",
        default=False,
        help="Active la commission tiercée P3 (fixe + taux par tranche de capital) "
        "au lieu du fees_pct plat legacy.",
    )
    # P1 — spread réel
    run_p.add_argument(
        "--no-spread-cost",
        action="store_true",
        default=False,
        help="Désactive le coût du spread réel P1 (utilise uniquement le slippage_bps comme fallback).",
    )
    run_p.add_argument(
        "--sizing-mode",
        choices=["equal_weight", "conviction_weighted", "rank_weighted"],
        default="equal_weight",
        help="Mode de sizing du portefeuille (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-min-weight-pct",
        type=float,
        default=0.005,
        help="Poids min par position quand sizing=conviction_weighted/rank_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--sizing-max-weight-pct",
        type=float,
        default=0.20,
        help="Poids max par position quand sizing=conviction_weighted/rank_weighted (Phase C.1).",
    )
    run_p.add_argument(
        "--sector-multipliers-json",
        type=str,
        default=None,
        help="P2-1 inc.3 : multiplicateurs sectoriels au format JSON {secteur: facteur} "
             "appliqués après le poids de base (ex: {\"Retail\":1.25,\"Health Care\":0.5}).",
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
        "--bull-strict-mode",
        choices=["off", "no_shorts", "no_trades"],
        default="off",
        help="P2-3 : overlay no-trades en bull strict (SPY>SMA200 ET ret60j>+3%%). "
             "no_shorts = bloque les shorts ; no_trades = bloque tout.",
    )
    run_p.add_argument(
        "--bull-strict-sma-window",
        type=int,
        default=200,
        help="P2-3 : fenêtre SMA pour la détection bull strict (défaut 200).",
    )
    run_p.add_argument(
        "--bull-strict-ret-window",
        type=int,
        default=60,
        help="P2-3 : fenêtre de rendement SPY pour la détection bull strict (défaut 60).",
    )
    run_p.add_argument(
        "--bull-strict-ret-threshold",
        type=float,
        default=0.03,
        help="P2-3 : seuil de rendement SPY (fraction) pour la détection bull strict (défaut 0.03).",
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
        default=0.92,
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
        "--dd-regime-ramp-up-enabled",
        action="store_true",
        default=False,
        help="Active le ramp-up progressif de l'allocation dégradée quand le régime repasse en 'normal'.",
    )
    run_p.add_argument(
        "--dd-regime-ramp-up-pct-per-day",
        type=float,
        default=0.025,
        help="Bonus quotidien d'allocation (en points de %%) par jour consécutif en régime normal.",
    )
    run_p.add_argument(
        "--dd-regime-ramp-up-max-pct",
        type=float,
        default=0.40,
        help="Plafond de l'allocation après ramp-up (ex. 0.40 = 40%% max).",
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
    run_p.add_argument(
        "--conviction-calibration-mode",
        choices=["off", "auto", "pinned"],
        default="off",
        help="Mode calibration conviction/Kelly pour Phase 2 : "
             "`off` = comportement standard (défaut) ; "
             "`auto` = charge la dernière calibration éligible avec window_end <= start du backtest (PIT) ; "
             "`pinned` = utilise le run_id explicite (--conviction-calibration-run-id), enforces window_end <= start.",
    )
    run_p.add_argument(
        "--conviction-calibration-run-id",
        default=None,
        help="run_id explicite d'un run weights_calibration_runs (scope=risk) à appliquer (mode=pinned). "
             "Si window_end > start, le backtest refuse le run pour éviter le look-ahead.",
    )
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
    backfill_p.add_argument("--selection-size", type=int, default=60, help="Nombre final de candidats selector par séance")
    backfill_p.add_argument("--selection-size-short", type=int, default=None, help="Nombre de shorts par séance (défaut = selection-size). Sprint 6.")
    backfill_p.add_argument("--screener-workers", type=int, default=4, help="Nombre de workers ProcessPool pour le screener PIT")
    backfill_p.add_argument(
        "--universe-only",
        action="store_true",
        help="Alimente uniquement tradable_universe_runs + tradable_universe_history depuis stock_scores_history existant (pas de recalcul screener/selector).",
    )
    backfill_p.add_argument(
        "--symbol-source",
        default="ticket-recherche",
        help="Source de l'univers des symboles à scorer (tradable-universe, stock-bars-daily, ticket-recherche). "
             "Défaut: ticket-recherche (config/ticket_recherche.txt).",
    )

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
    diag_p.add_argument(
        "--capital-preset-key",
        default=None,
        help="Preset capital à utiliser pour les snapshots PIT (ex: capital_0_2000). Si absent, utilise le preset par défaut.",
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
    calibrate_p.add_argument(
        "--symbol-source",
        default=None,
        help="Source de l'univers (tradable-universe, stock-bars-daily, ticket-recherche). "
             "Si non renseigné, utilise le comportement par défaut (--all-symbols ou candidats).",
    )
    calibrate_p.add_argument(
        "--capital-preset-key",
        default=None,
        help="Preset capital à utiliser pour filtrer stock_scores_history (ex: capital_0_2000). Si absent, tous les presets sont mélangés.",
    )

    # P2 (2026-06-25) — calibration conviction (quant/ML) + Kelly
    conv_cal_p = sub.add_parser(
        "calibrate-conviction-weights",
        help="Calibrer les poids de conviction (quant/ML) et les paramètres Kelly.",
    )
    conv_cal_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    conv_cal_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    conv_cal_p.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour")
    conv_cal_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    conv_cal_p.add_argument(
        "--output-dir",
        default="artifacts/conviction_calibration",
        help="Répertoire cible pour les artefacts de calibration",
    )
    conv_cal_p.add_argument(
        "--scope",
        choices=["conviction", "kelly", "all"],
        default="all",
        help="Scope de calibration : conviction seule, Kelly seule, ou les deux (défaut: all)",
    )
    conv_cal_p.add_argument(
        "--backtest-kelly",
        action="store_true",
        default=False,
        help="Activer la calibration Kelly via BacktestEngine (coûteux, ~27 backtests complets par direction)",
    )
    # Sprint 6 — top-N directionnel
    conv_cal_p.add_argument("--top-n-long", type=int, default=None, help="Top-N longs pour la calibration (défaut = top-n)")
    conv_cal_p.add_argument("--top-n-short", type=int, default=None, help="Top-N shorts pour la calibration (défaut = top-n)")

    # Sprint 4 — walk-forward conviction orchestrateur
    wf_conv_p = sub.add_parser(
        "walk-forward-conviction",
        help="Walk-forward complet conviction + Kelly + validation OOS par folds (Sprint 4).",
    )
    wf_conv_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    wf_conv_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    wf_conv_p.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour")
    wf_conv_p.add_argument("--horizons", default="5,10,20", help="Horizons forward CSV à évaluer")
    wf_conv_p.add_argument("--min-train-days", type=int, default=252, help="Jours calendaires minimum d'entraînement par fold")
    wf_conv_p.add_argument("--test-days", type=int, default=63, help="Jours calendaires hors échantillon par fold")
    wf_conv_p.add_argument("--step-days", type=int, default=None, help="Décalage entre folds (défaut = test-days)")
    wf_conv_p.add_argument(
        "--output-dir",
        default="artifacts/walk_forward_conviction",
        help="Répertoire cible pour les artefacts",
    )
    wf_conv_p.add_argument(
        "--backtest-kelly",
        action="store_true",
        default=False,
        help="Activer la calibration Kelly via BacktestEngine dans chaque fold train",
    )
    # Sprint 5 — grilles symétriques market-neutral
    wf_conv_p.add_argument(
        "--symmetric-grid",
        default=None,
        choices=["60/60", "80/80", "100/100", "40/40", "20/20"],
        help="Grille symétrique long/short prédéfinie. Surcharge --top-n-long/--top-n-short.",
    )
    wf_conv_p.add_argument("--top-n-long", type=int, default=None, help="Top-N longs (défaut = top-n)")
    wf_conv_p.add_argument("--top-n-short", type=int, default=None, help="Top-N shorts (défaut = top-n)")
    wf_conv_p.add_argument(
        "--enforce-net-exposure",
        action="store_true",
        default=False,
        help="Active la contrainte de neutralité nette dans le backtest de validation OOS",
    )
    wf_conv_p.add_argument(
        "--net-exposure-target",
        type=float,
        default=0.0,
        help="Exposition nette cible (0.0 = market-neutral, 0.30 = biais long 30%%)",
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
    walk_forward_p.add_argument("--ts", type=float, default=0.05, help="Trailing stop %%")
    walk_forward_p.add_argument(
        "--atr-ts", type=float, default=0.0,
        help="Multiplicateur ATR pour trailing stop adaptatif (0 = désactivé, utilise --ts fixe). "
             "Ex: 2.0 → stop = peak - 2*ATR_20. Recommandé 1.5-2.5 pour microcaps.",
    )
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
    walk_forward_p.add_argument(
        "--symbol-source",
        default=None,
        help="Source de l'univers (tradable-universe, stock-bars-daily, ticket-recherche). "
             "Si non renseigné, utilise le comportement par défaut (--all-symbols ou candidats).",
    )
    walk_forward_p.add_argument(
        "--capital-preset-keys",
        default=None,
        help="Presets capital à utiliser (CSV, ex: capital_0_2000,capital_2001_5000). "
             "Si absent, tous les presets sont mélangés. "
             "Pour 3000€: capital_0_2000,capital_2001_5000,capital_5001_10000.",
    )
    # Retrocompatibilité : --capital-preset-key (singulier)
    walk_forward_p.add_argument(
        "--capital-preset-key",
        default=None,
        help=argparse.SUPPRESS,  # déprécié, utiliser --capital-preset-keys
    )

    # ── Section 17 Point 7-R1 : walk-forward financier ──────────────────
    wf_fin_p = sub.add_parser(
        "walk-forward-financial",
        help="Walk-forward financier intégré : replay OOS avec bridge ML-first + risque directionnel.",
    )
    wf_fin_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    wf_fin_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    wf_fin_p.add_argument("--equity", type=float, default=100_000, help="Capital initial ($)")
    wf_fin_p.add_argument("--commission-bps", type=float, default=5.0, help="Commission (bps)")
    wf_fin_p.add_argument("--slippage-bps", type=float, default=5.0, help="Slippage (bps)")
    wf_fin_p.add_argument("--train-days", type=int, default=504, help="Jours de train par fold")
    wf_fin_p.add_argument("--val-days", type=int, default=126, help="Jours de validation par fold")
    wf_fin_p.add_argument("--test-days", type=int, default=126, help="Jours de test par fold")
    wf_fin_p.add_argument("--step-days", type=int, default=126, help="Pas entre folds")
    wf_fin_p.add_argument("--purge-days", type=int, default=5, help="Jours de purge entre train et val")
    wf_fin_p.add_argument("--embargo-days", type=int, default=10, help="Jours d'embargo après val")
    wf_fin_p.add_argument("--max-positions", type=int, default=20, help="Positions max")
    wf_fin_p.add_argument("--output", default=None, help="Chemin du rapport JSON de sortie")
    wf_fin_p.add_argument("--n-trials", type=int, default=100, help="Essais pour Deflated Sharpe")

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
        "--swing-only": "swing_only",
        "--allow-fractional-shares": "allow_fractional_shares",
        "--cash-settlement-days": "cash_settlement_days",
        "--fees": "fees",
        "--capital-preset-key": "capital_preset_key",
        "--capital": "capital",
        "--max-portfolio-dd-pct": "max_portfolio_dd_pct",
        "--dd-recovery-pct": "dd_recovery_pct",
        "--dd-rolling-peak-window-days": "dd_rolling_peak_window_days",
        "--dd-degraded-allocation-pct": "dd_degraded_allocation_pct",
        "--dd-regime-ramp-up-enabled": "dd_regime_ramp_up_enabled",
        "--dd-regime-ramp-up-pct-per-day": "dd_regime_ramp_up_pct_per_day",
        "--dd-regime-ramp-up-max-pct": "dd_regime_ramp_up_max_pct",
        "--target-annual-vol": "target_annual_vol",
        "--min-ml-coverage-ratio": "min_ml_coverage_ratio",
        "--max-sector-exposure-pct": "max_sector_exposure_pct",
        "--max-entry-gap-pct": "max_entry_gap_pct",
    }
    for token in argv:
        key = token.split("=", 1)[0]
        if key in mapping:
            explicit.add(mapping[key])
    return explicit


def _infer_programmatic_explicit_flags(args: argparse.Namespace, *, argv: list[str]) -> set[str]:
    """Préserve les overrides injectés hors CLI réelle.

    Certains tests appellent directement ``_run_backtest(args)`` avec un
    ``Namespace`` déjà rempli. Si ``sys.argv`` ne contient pas la sous-commande
    ``run``, on considère ces valeurs comme explicites pour éviter qu'un preset
    capital ne les écrase silencieusement.
    """
    if "run" in {str(token).strip().lower() for token in argv}:
        return set()
    inferable_fields = {
        "tp",
        "ts",
        "max_positions",
        "commission_bps",
        "slippage_bps",
        "account_type",
        "swing_only",
        "allow_fractional_shares",
        "cash_settlement_days",
        "fees",
        "capital_preset_key",
        "max_portfolio_dd_pct",
        "target_annual_vol",
        "min_ml_coverage_ratio",
    }
    explicit: set[str] = set()
    for field_name in inferable_fields:
        if not hasattr(args, field_name):
            continue
        value = getattr(args, field_name)
        if value is None:
            continue
        if field_name == "max_portfolio_dd_pct" and float(value or 0.0) <= 0.0:
            continue
        explicit.add(field_name)
    return explicit


def _run_statistical_validation(
    args: argparse.Namespace,
    pf: object,
    *,
    fees_pct: float,
    output_dir: "Path | None",
) -> None:
    """Sprint S3 / A-011 — Bootstrap trades + analyse de sensibilité post-backtest.

    Activé uniquement si ``--bootstrap-samples > 0`` ou ``--sensitivity-analysis``.
    """
    bootstrap_n = int(getattr(args, "bootstrap_samples", 0) or 0)
    do_sensitivity = bool(getattr(args, "sensitivity_analysis", False))
    if not bootstrap_n and not do_sensitivity:
        return

    import json as _json
    import pandas as _pd
    from backtesting.statistical_validation import bootstrap_trades, parameter_sensitivity
    from backtesting.report import _extract_closed_trades_df

    # --- G1. Bootstrap ---
    if bootstrap_n > 0:
        _safe_print(f"\n📐 Bootstrap Monte Carlo ({bootstrap_n} itérations)...")
        try:
            closed_trades = _extract_closed_trades_df(pf)
            if closed_trades is None:
                raise AttributeError("closed_trades_df indisponible")
        except Exception:
            try:
                closed_trades = pf.closed_trades.records_readable
            except Exception:
                closed_trades = _pd.DataFrame()

        if closed_trades.empty or "return_pct" not in closed_trades.columns:
            _safe_print("   ⚠️ Aucun trade clôturé disponible pour le bootstrap.")
        else:
            br = bootstrap_trades(
                closed_trades,
                n_iterations=bootstrap_n,
                initial_equity=float(getattr(args, "equity", 100_000)),
                seed=getattr(args, "seed", 0),
            )
            _safe_print(f"   Return moyen           : {br.mean_total_return_pct:.2f}%")
            _safe_print(
                f"   IC {int(0.95 * 100)}%% return          : [{br.ci_low_total_return_pct:.2f}%, {br.ci_high_total_return_pct:.2f}%]"
            )
            _safe_print(f"   Sharpe moyen           : {br.mean_sharpe:.3f}")
            _safe_print(
                f"   IC {int(0.95 * 100)}%% Sharpe          : [{br.ci_low_sharpe:.3f}, {br.ci_high_sharpe:.3f}]"
            )
            _safe_print(f"   Max DD moyen           : {br.mean_max_dd_pct:.2f}%")
            _safe_print(f"   Win rate               : {br.win_rate_pct:.1f}%\n")
            if output_dir is not None:
                bootstrap_path = output_dir / "bootstrap_result.json"
                bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
                bootstrap_path.write_text(
                    _json.dumps(br.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                _safe_print(f"   → {bootstrap_path}")

    # --- G2. Sensibilité ---
    if do_sensitivity:
        _safe_print("\n📊 Analyse de sensibilité ±10% (tp / ts / fees_pct)...")
        try:
            from backtesting.data_loader import load_ohlcv, load_predictions, load_scores, pivot_ohlcv
            from backtesting.resilience import prepare_scores_for_sentiment_mode
            from backtesting.signal_replay import replay_signals
            from backtesting.simulator import BacktestConfig, BacktestEngine
            from database.connection import get_sqlalchemy_engine as _gse
            from datetime import datetime as _dt

            _engine = _gse()
            _start = _dt.strptime(args.start, "%Y-%m-%d").date()
            _end = _dt.strptime(args.end, "%Y-%m-%d").date()
            _ohlcv_df = load_ohlcv(_engine, _start, _end)
            _pivoted = pivot_ohlcv(_ohlcv_df)

            from backtesting.data_loader import load_scores as _ls
            _score_result = _ls(
                _engine,
                _start,
                _end,
                capital_preset_key=getattr(args, "capital_preset_key", None),
                scores_pit_mode=getattr(args, "scores_pit_mode", "exact"),
            )
            _scores_df = _score_result.frame if hasattr(_score_result, "frame") else _score_result

            base_params = {
                "tp": float(args.tp),
                "ts": float(args.ts),
                "fees_pct": fees_pct,
            }

            def _metric_fn(params: dict) -> float:
                _tp = float(params.get("tp", 0.08))
                _ts = float(params.get("ts", 0.05))
                _fees = float(params.get("fees_pct", 0.001))
                _predictions_df = load_predictions(_engine, _start, _end)
                _signals = replay_signals(
                    _predictions_df,
                    _scores_df,
                    max_positions=int(args.max_positions),
                )
                _cfg = BacktestConfig(
                    start_date=_start, end_date=_end,
                    initial_equity=float(args.equity),
                    profit_taker_pct=_tp, trailing_stop_pct=_ts,
                    max_positions=int(args.max_positions),
                    fees_pct=_fees,
                )
                _pf = BacktestEngine(_cfg).run(
                    open=_pivoted["open"], close=_pivoted["close"],
                    high=_pivoted["high"], low=_pivoted["low"],
                    signals_df=_signals,
                )
                try:
                    return float(_pf.total_return())
                except Exception:
                    return 0.0

            sens_df = parameter_sensitivity(base_params, _metric_fn)
            if not sens_df.empty:
                _safe_print(sens_df.to_string(index=False))
                if output_dir is not None:
                    sens_path = output_dir / "sensitivity_analysis.csv"
                    sens_df.to_csv(sens_path, index=False)
                    _safe_print(f"\n   → {sens_path}")
        except Exception as exc:  # noqa: BLE001
            _safe_print(f"   ⚠️ Analyse de sensibilité échouée : {exc}")


def _resolve_pipeline_preset_float(preset, *keys: str, default: float | None = None) -> float | None:
    values = getattr(preset, "values", {}) or {}
    for key in keys:
        raw = values.get(key)
        if raw in {None, ""}:
            continue
        return float(raw)
    return default


def _apply_pipeline_defensive_defaults_from_preset(
    args: argparse.Namespace,
    *,
    effective_preset,
    engine_mode: str,
    explicit_flags: set[str],
) -> None:
    if str(engine_mode or "research").strip().lower() != "pipeline":
        return

    if (
        "commission_bps" not in explicit_flags
        and float(getattr(args, "commission_bps", 0.0) or 0.0) <= 5.0
    ):
        args.commission_bps = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_commission_bps_stress",
            default=15.0,
        )

    if (
        "slippage_bps" not in explicit_flags
        and float(getattr(args, "slippage_bps", 0.0) or 0.0) <= 5.0
    ):
        args.slippage_bps = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_slippage_bps_stress",
            default=15.0,
        )

    # P2 — microstructure slippage volume-aware : résoudre les défauts depuis le preset capital
    if (
        "slippage_base_bps" not in explicit_flags
        and float(getattr(args, "slippage_base_bps", 0.0) or 0.0) <= 2.0
    ):
        args.slippage_base_bps = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_slippage_base_bps",
            default=2.0,
        )

    if (
        "slippage_impact_coef" not in explicit_flags
        and float(getattr(args, "slippage_impact_coef", 0.0) or 0.0) <= 5.0
    ):
        args.slippage_impact_coef = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_slippage_impact_coef",
            default=5.0,
        )

    # P3 — commission tiercée : désactivée par défaut (Alpaca = commission-free).
    # L'utilisateur peut l'activer explicitement avec --use-tiered-commission.
    if (
        "use_tiered_commission" not in explicit_flags
        and not getattr(args, "use_tiered_commission", False)
    ):
        # Ne plus forcer l'activation auto : Alpaca n'a pas de commission.
        pass

    if (
        "max_portfolio_dd_pct" not in explicit_flags
        and float(getattr(args, "max_portfolio_dd_pct", 0.0) or 0.0) <= 0.0
    ):
        args.max_portfolio_dd_pct = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_max_portfolio_dd_pct",
            "risk_max_drawdown_pct",
            default=0.12,
        )

    if (
        "max_sector_exposure_pct" not in explicit_flags
        and float(getattr(args, "max_sector_exposure_pct", 0.0) or 0.0) <= 0.0
    ):
        args.max_sector_exposure_pct = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_max_sector_exposure_pct",
            "risk_max_sector_weight",
            default=0.25,
        )

    if (
        "max_entry_gap_pct" not in explicit_flags
        and float(getattr(args, "max_entry_gap_pct", 0.0) or 0.0) <= 0.0
    ):
        args.max_entry_gap_pct = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_max_entry_gap_pct",
            default=0.03,
        )

    if (
        "target_annual_vol" not in explicit_flags
        and getattr(args, "target_annual_vol", None) is None
    ):
        args.target_annual_vol = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_target_annual_vol",
            default=0.15,
        )

    if (
        "min_ml_coverage_ratio" not in explicit_flags
        and getattr(args, "min_ml_coverage_ratio", None) is None
    ):
        args.min_ml_coverage_ratio = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_min_ml_coverage_ratio",
            default=0.80,
        )

    if "dd_rolling_peak_window_days" not in explicit_flags:
        resolved_window = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_rolling_peak_window_days",
            default=252.0,
        )
        if resolved_window is not None:
            args.dd_rolling_peak_window_days = int(resolved_window)

    if "dd_degraded_allocation_pct" not in explicit_flags:
        resolved_alloc = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_degraded_allocation_pct",
            default=0.02,
        )
        if resolved_alloc is not None:
            args.dd_degraded_allocation_pct = float(resolved_alloc)

    if "dd_recovery_pct" not in explicit_flags:
        resolved_recovery = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_recovery_pct",
            default=0.92,
        )
        if resolved_recovery is not None:
            args.dd_recovery_pct = float(resolved_recovery)

    # Ramp-up régime : résolus depuis le preset si non explicites
    if "dd_regime_ramp_up_enabled" not in explicit_flags:
        resolved_ramp_enabled = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_regime_ramp_up_enabled",
            default=0.0,
        )
        if resolved_ramp_enabled is not None:
            args.dd_regime_ramp_up_enabled = bool(resolved_ramp_enabled)
    if "dd_regime_ramp_up_pct_per_day" not in explicit_flags:
        resolved_ramp_day = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_regime_ramp_up_pct_per_day",
            default=0.025,
        )
        if resolved_ramp_day is not None:
            args.dd_regime_ramp_up_pct_per_day = float(resolved_ramp_day)
    if "dd_regime_ramp_up_max_pct" not in explicit_flags:
        resolved_ramp_max = _resolve_pipeline_preset_float(
            effective_preset,
            "backtesting_dd_regime_ramp_up_max_pct",
            default=0.40,
        )
        if resolved_ramp_max is not None:
            args.dd_regime_ramp_up_max_pct = float(resolved_ramp_max)


def _enforce_ml_coverage_gate(
    *,
    engine_mode: str,
    ml_mode: str,
    ml_diagnostics,
    min_ml_coverage_ratio: float | None,
) -> dict[str, object]:
    from backtesting.fidelity import evaluate_ml_coverage_gate

    def _as_float(value: object) -> float:
        return float(value) if value not in {None, ""} else 0.0

    gate = evaluate_ml_coverage_gate(
        engine_mode=engine_mode,
        ml_mode=ml_mode,
        ml_diagnostics=ml_diagnostics,
        min_coverage_ratio=min_ml_coverage_ratio,
    )
    if gate.get("enabled"):
        _safe_print(
            "   ml_coverage_gate=enabled coverage={:.2%} threshold={:.2%}\n".format(
                _as_float(gate.get("coverage_ratio")),
                _as_float(gate.get("required_ratio")),
            )
        )
    if gate.get("enabled") and not gate.get("allowed"):
        _safe_print(
            "❌ Couverture ML insuffisante pour un run pipeline : {:.2%} < {:.2%}. Relancez avec une meilleure couverture, `--ml-mode off`, ou un seuil explicite plus bas.\n".format(
                _as_float(gate.get("coverage_ratio")),
                _as_float(gate.get("required_ratio")),
            )
        )
        sys.exit(1)
    return gate


def _run_backtest(args: argparse.Namespace) -> None:
    """Exécute le backtest complet."""
    from datetime import datetime

    import pandas as pd

    from backtesting.fidelity import (
        build_selection_target_parity_summary,
        build_fidelity_baseline_comparison,
        build_fidelity_baseline_snapshot,
        PitHistoryRequiredError,
        build_replay_diagnostic_summary,
        build_fidelity_symbol_matrix,
        PitMlStrategyUnsupportedError,
        build_fidelity_manifest,
        save_selection_target_parity_summary,
        save_fidelity_baseline_comparison,
        save_fidelity_baseline_snapshot,
        save_fidelity_symbol_matrix,
        save_replay_diagnostic_summary,
        save_coverage_summary,
        save_fidelity_manifest,
    )
    from database.connection import get_sqlalchemy_engine
    from backtesting.data_loader import (
        load_ohlcv,
        load_predictions,
        load_scores,
        load_spreads,
        load_tradable_universe_scope,
        pivot_ohlcv,
    )
    from backtesting.resilience import prepare_predictions_for_ml_mode, prepare_scores_for_sentiment_mode
    from backtesting.signal_replay import replay_signals
    from backtesting.trading_constraints import build_current_trading_constraints
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from backtesting.microstructure import MicrostructureConfig, SlippageConfig, ExecutionModelConfig
    from backtesting.risk_overlay import (
        BullStrictConfig,
        DrawdownCircuitBreaker,
        RegimeFilterConfig,
        RiskOverlayConfig,
        SectoralCapConfig,
        SizingConfig,
    )
    from backtesting.profiles import apply_profile
    from backtesting.run_metadata import build_run_metadata
    from backtesting.report import (
        build_trade_export_bundle,
        extract_diagnostics,
        generate_report,
        load_corporate_actions_summary,
        load_dividends_received,
        save_trade_audit_csv,
        save_equity_curve,
        save_equity_curve_csv,
        save_report_json,
        save_trades_csv,
    )
    from risk_management.config import RiskConfig
    from service.market import MacroDataUnavailableError

    # Phase 6.1.e — appliquer le profil avant tout (sans écraser les flags explicites).
    explicit_flags = _explicit_flags(sys.argv[1:])
    explicit_flags |= _infer_programmatic_explicit_flags(args, argv=sys.argv[1:])
    apply_profile(args, getattr(args, "profile", None), explicit_flags=explicit_flags)

    effective_preset, preset_source = resolve_effective_capital_preset(
        capital_preset_key=getattr(args, "capital_preset_key", None),
        equity=float(getattr(args, "equity", 0.0) or 0.0),
    )
    detected_from_equity = resolve_capital_preset_for_equity(float(getattr(args, "equity", 0.0) or 0.0))
    if preset_source == "explicit_key" and detected_from_equity is not None and detected_from_equity.key != effective_preset.key:
        _safe_print(
            f"⚠️ Preset explicite `{effective_preset.key}` prioritaire sur le bucket détecté depuis equity `{detected_from_equity.key}`."
        )
    args.capital_preset_key = effective_preset.key
    preset_applied_values = apply_backtest_defaults_from_preset(vars(args), effective_preset, explicit_flags=explicit_flags)
    for field_name, value in preset_applied_values.items():
        setattr(args, field_name, value)
    preset_fingerprint = capital_preset_fingerprint(effective_preset)
    preset_fractional_flag = bool(build_risk_config_kwargs_from_preset(effective_preset).get("allow_fractional_shares", False))
    args.allow_fractional_shares = bool(getattr(args, "allow_fractional_shares", False) or preset_fractional_flag)

    # Phase 6.1.b — gestion --fees (déprécié) vs commission/slippage_bps.
    if args.fees is not None:
        import warnings as _warnings
        _warnings.warn(
            "--fees est déprécié (Phase 6.1.b). Utiliser --commission-bps + --slippage-bps.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Convertit fees pct (ex 0.001 = 10bps) en bps total côté commission.
        total_bps = float(args.fees) * 10_000.0
        args.commission_bps = total_bps
        args.slippage_bps = 0.0
    fees_pct = (float(args.commission_bps) + float(args.slippage_bps)) / 10_000.0

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    engine_mode = str(getattr(args, "engine_mode", "research") or "research").strip().lower()
    scores_pit_mode = str(getattr(args, "scores_pit_mode", "exact") or "exact").strip().lower()
    macro_pit_mode = str(getattr(args, "macro_pit_mode", "yaml_default") or "yaml_default").strip().lower()
    ml_pit_strategy = str(getattr(args, "ml_pit_strategy", "auto") or "auto").strip().lower()
    phase2_mode = str(getattr(args, "phase2_mode", "off") or "off").strip().lower()
    phase3_mode = str(getattr(args, "phase3_mode", "off") or "off").strip().lower()
    phase4_mode = str(getattr(args, "phase4_mode", "off") or "off").strip().lower()
    phase5_mode = str(getattr(args, "phase5_mode", "off") or "off").strip().lower()
    phase7_mode = str(getattr(args, "phase7_mode", "off") or "off").strip().lower()
    strict_pit = engine_mode == "pipeline"
    _apply_pipeline_defensive_defaults_from_preset(
        args,
        effective_preset=effective_preset,
        engine_mode=engine_mode,
        explicit_flags=explicit_flags,
    )
    phase2_risk_config = None
    conviction_calibration_mode = str(
        getattr(args, "conviction_calibration_mode", "off") or "off"
    ).strip().lower()
    conviction_calibration_run_id = str(
        getattr(args, "conviction_calibration_run_id", "") or ""
    ).strip() or None
    _conviction_calibration_diagnostic: dict[str, object] = {
        "requested_mode": conviction_calibration_mode,
        "requested_run_id": conviction_calibration_run_id,
        "status": "disabled",
        "applied_run_id": None,
        "window_start": None,
        "window_end": None,
        "applied_overrides": {},
        "fallback_reason": None,
    }
    if phase2_mode != "off":
        # ── Section 17 Point 6.1 : loader unifié ────────────────────────
        # Priorité : defaults < config.yaml < capital_preset < CLI args
        from risk_management.config import load_risk_config

        # Sprint 2 — short selling (Option C) : activé si le preset a un seuil short.
        _preset_has_short_threshold = (
            float(effective_preset.values.get("risk_min_score_threshold_short", -1) or -1) >= 0
        )

        phase2_risk_config = load_risk_config(
            equity=float(args.equity),
            cli_overrides={
                "account_equity": float(args.equity),
                "max_positions": int(args.max_positions),
                "short_selling_enabled": _preset_has_short_threshold,
                "max_short_positions": 2,
                "short_min_score": 0.0,
                "short_rotation_required": True,
            },
        )

        _safe_print(f"   short_selling_enabled={_preset_has_short_threshold} (preset={effective_preset.key})")

        # Flag CLI pour exclure les sélections sans ML.
        if getattr(args, "filter_no_ml", False):
            phase2_risk_config = phase2_risk_config.with_overrides(
                filter_unmodeled_selections=True,
            )
            LOGGER.info("filter-no-ml activé : exclusion des sélections sans modèle ML entraîné")

    # ── Conviction/Kelly calibration opt-in (Phase 2 only) ──────────────
    if phase2_risk_config is not None and conviction_calibration_mode != "off":
        try:
            from risk_management.cli import _apply_empirical_risk_calibration as _apply_cal
            from risk_management.db_io import RiskRepository as _RiskRepo

            _risk_repo = _RiskRepo(engine)
            if conviction_calibration_mode == "pinned":
                if conviction_calibration_run_id is None:
                    _conviction_calibration_diagnostic["status"] = "error_no_run_id"
                    _conviction_calibration_diagnostic["fallback_reason"] = (
                        "mode=pinned mais aucun --conviction-calibration-run-id fourni"
                    )
                    _safe_print("❌ Calibration conviction: mode=pinned mais --conviction-calibration-run-id manquant.")
                    sys.exit(1)
                _cal_payload = _risk_repo.load_latest_empirical_risk_calibration(
                    start, run_id=conviction_calibration_run_id
                )
                if _cal_payload is None:
                    _conviction_calibration_diagnostic["status"] = "error_run_not_found"
                    _conviction_calibration_diagnostic["fallback_reason"] = (
                        f"run_id={conviction_calibration_run_id} introuvable dans "
                        "weights_calibration_runs (scope=risk)"
                    )
                    _safe_print(f"❌ Calibration conviction pinned: run_id={conviction_calibration_run_id} introuvable.")
                    sys.exit(1)
                _cal_window_end = _cal_payload.get("window_end")
                if _cal_window_end is not None and _cal_window_end > start:
                    _conviction_calibration_diagnostic.update(
                        {
                            "status": "refused_lookahead",
                            "applied_run_id": conviction_calibration_run_id,
                            "window_end": str(_cal_window_end),
                            "fallback_reason": (
                                f"PIT safety: window_end={_cal_window_end} > start={start} → look-ahead refusé"
                            ),
                        }
                    )
                    _safe_print(
                        f"❌ Calibration conviction pinned: window_end={_cal_window_end} > start={start}. "
                        "Run refusé pour éviter le look-ahead."
                    )
                    sys.exit(1)
            else:
                _cal_payload = _risk_repo.load_latest_empirical_risk_calibration(start, run_id=None)
            if _cal_payload is not None and _cal_payload.get("status") == "selected":
                _original_config = phase2_risk_config
                phase2_risk_config = _apply_cal(phase2_risk_config, _cal_payload)
                _applied = phase2_risk_config is not _original_config
                _best_weights = _cal_payload.get("best_weights", {})
                _overrides: dict[str, object] = {}
                if _applied and isinstance(_best_weights, dict):
                    for _field in (
                        "score_weight",
                        "prediction_weight",
                        "kelly_fraction_multiplier",
                        "min_effective_probability",
                        "assumed_payoff_ratio",
                    ):
                        if _field in _best_weights:
                            _overrides[_field] = float(_best_weights[_field])
                _conviction_calibration_diagnostic.update(
                    {
                        "status": "applied" if _applied else "no_change",
                        "applied_run_id": _cal_payload.get("run_id"),
                        "window_start": str(_cal_payload.get("window_start") or ""),
                        "window_end": str(_cal_payload.get("window_end") or ""),
                        "applied_overrides": _overrides,
                        "metric_name": _cal_payload.get("metric_name"),
                        "metric_value": _cal_payload.get("metric_value"),
                        "segment_key": _cal_payload.get("segment_key"),
                        "fallback_reason": _cal_payload.get("fallback_reason"),
                        "fallback_level": _cal_payload.get("fallback_level"),
                        "eligible_for_live": _cal_payload.get("eligible_for_live"),
                    }
                )
                _safe_print(
                    "   conviction_calibration: mode={} run_id={} window_end={} overrides={}\n".format(
                        conviction_calibration_mode,
                        _cal_payload.get("run_id"),
                        _cal_payload.get("window_end"),
                        list(_overrides.keys()),
                    )
                )
            elif _cal_payload is not None and _cal_payload.get("status") == "blocked_by_governance":
                _conviction_calibration_diagnostic.update(
                    {
                        "status": "blocked_by_governance",
                        "applied_run_id": _cal_payload.get("run_id"),
                        "fallback_reason": _cal_payload.get("eligibility_reason") or "eligible_for_live=False",
                    }
                )
                _safe_print(
                    "   ⚠️ Calibration conviction: run bloqué par gouvernance (eligible_for_live=False). "
                    "Comportement standard conservé.\n"
                )
            else:
                _conviction_calibration_diagnostic.update(
                    {
                        "status": "not_found",
                        "fallback_reason": f"Aucun run calibration éligible trouvé avec window_end <= {start}",
                    }
                )
                _safe_print(
                    f"   ⚠️ Calibration conviction ({conviction_calibration_mode}): aucun run éligible trouvé "
                    f"pour start={start}. Comportement standard conservé.\n"
                )
        except SystemExit:
            raise
        except Exception as _cal_exc:
            _conviction_calibration_diagnostic.update(
                {"status": "error", "fallback_reason": str(_cal_exc)}
            )
            LOGGER.warning("Calibration conviction load failed: %s", _cal_exc, exc_info=True)
            if conviction_calibration_mode == "pinned":
                _safe_print(
                    f"❌ Calibration conviction pinned: erreur de chargement ({_cal_exc}). "
                    "Run arrêté pour éviter un replay avec des poids par défaut.\n"
                )
                sys.exit(1)
            _safe_print(
                f"   ⚠️ Calibration conviction: erreur de chargement ({_cal_exc}). "
                "Comportement standard conservé.\n"
            )
    _safe_print(f"   conviction_calibration_mode={conviction_calibration_mode}\n")

    if phase3_mode != "off" and phase2_mode != "risk_execution":
        _safe_print(
            "❌ La Phase 3 `execution_replay` exige `--phase2-mode risk_execution` pour disposer des cibles et fills d'exécution."
        )
        sys.exit(1)
    if phase4_mode != "off" and phase3_mode != "execution_replay":
        _safe_print(
            "❌ La Phase 4 `protection_replay` exige `--phase3-mode execution_replay` pour disposer d'un calendrier d'exécution rejouable."
        )
        sys.exit(1)
    if phase5_mode != "off" and phase4_mode != "protection_replay":
        _safe_print(
            "❌ La Phase 5 `watcher_replay` exige `--phase4-mode protection_replay` pour disposer des protections rejouées."
        )
        sys.exit(1)
    if phase7_mode != "off" and phase5_mode != "watcher_replay":
        _safe_print(
            "❌ La Phase 7 `exit_lifecycle_replay` exige `--phase5-mode watcher_replay` pour disposer du lifecycle du watcher."
        )
        sys.exit(1)

    trading_constraints = build_current_trading_constraints(
        account_type=args.account_type,
        swing_only=args.swing_only,
        cash_settlement_days=int(getattr(args, "cash_settlement_days", 1) or 0),
    )

    _safe_print(f"\n🚀 Backtest Alpha Trade : {start} → {end}, capital={args.equity:,.0f}$")
    _safe_print(f"   preset_capital={effective_preset.key} ({preset_source}) | fingerprint={preset_fingerprint}\n")
    _safe_print(f"   TP={args.tp*100:.1f}%, TS={args.ts*100:.1f}%, max_positions={args.max_positions}\n")
    _safe_print(
        "   protection_logic={}\n".format(
            "live_like" if bool(getattr(args, "use_live_protection_logic", True)) else "fixed_legacy"
        )
    )
    _safe_print(f"   engine_mode={engine_mode} strict_pit={strict_pit}\n")
    _safe_print(f"   scores_pit_mode={scores_pit_mode}\n")
    _safe_print(f"   macro_pit_mode={macro_pit_mode}\n")
    _safe_print(f"   phase2_mode={phase2_mode}\n")
    _safe_print(f"   phase3_mode={phase3_mode}\n")
    _safe_print(f"   phase4_mode={phase4_mode}\n")
    _safe_print(f"   phase5_mode={phase5_mode}\n")
    _safe_print(f"   phase7_mode={phase7_mode}\n")
    _safe_print(f"   ml_mode={args.ml_mode}, sentiment_mode={args.sentiment_mode}\n")
    _safe_print(f"   allow_fractional_shares={bool(args.allow_fractional_shares)}\n")
    _safe_print(f"   ml_pit_strategy={ml_pit_strategy}\n")
    _safe_print(f"   macro_missing_policy={getattr(args, 'macro_missing_policy', None) or 'yaml_default'}\n")
    _safe_print(
        "   score_column={} walk_forward_artifacts_dir={}\n".format(
            args.score_column,
            args.walk_forward_artifacts_dir or "auto-disabled",
        )
    )
    _safe_print(
        "   account_type={} swing_only={} cash_settlement_days={}\n".format(
            trading_constraints.account_type,
            trading_constraints.swing_only,
            trading_constraints.cash_settlement_days,
        )
    )
    _safe_print("   convention_exécution=signal J → entrée J+1 au vrai open\n")

    # 1. Charger les données
    engine = get_sqlalchemy_engine()

    # Sprint S3 / A-010 → Sprint S11 : cache Parquet actif par défaut, --no-cache pour désactiver.
    use_cache = not bool(getattr(args, "no_cache", False))
    cache: object
    if use_cache:
        from backtesting.cache import ParquetCache
        cache = ParquetCache(cache_dir=getattr(args, "cache_dir", "artifacts/backtest_cache"), enabled=True)
        _safe_print(f"   cache=enabled dir={getattr(args, 'cache_dir', 'artifacts/backtest_cache')}\n")
    else:
        from backtesting.cache import ParquetCache
        cache = ParquetCache(enabled=False)
    ohlcv_start = (
        _resolve_phase2_ohlcv_history_start(
            start,
            atr_window=phase2_risk_config.atr_window,
            correlation_lookback_days=phase2_risk_config.correlation_lookback_days,
        )
        if phase2_risk_config is not None
        else start
    )

    try:
        bars_source_preflight = _run_bars_source_preflight_or_skip(engine, ohlcv_start, end)
    except RuntimeError as exc:
        _safe_print(f"❌ {exc}")
        sys.exit(1)
    _safe_print(
        "   preflight_ohlcv_source={} rows_required={} rows_total={} status={}\n".format(
            bars_source_preflight.get("required_data_source"),
            bars_source_preflight.get("required_rows"),
            bars_source_preflight.get("rows_total"),
            bars_source_preflight.get("status"),
        )
    )
    if bars_source_preflight.get("mixed_sources_detected"):
        _safe_print(
            "   ⚠️ Fenêtre OHLCV mixte détectée {} — le backtest filtrera strictement `{}`.\n".format(
                bars_source_preflight.get("counts"),
                bars_source_preflight.get("required_data_source"),
            )
        )

    _safe_print("📊 Chargement OHLCV...")
    _ohlcv_cache_key = f"ohlcv_{ohlcv_start}_{end}"
    ohlcv_df = cache.get_or_load(_ohlcv_cache_key, lambda: load_ohlcv(engine, ohlcv_start, end))
    if ohlcv_df.empty:
        _safe_print("❌ Aucune donnée OHLCV trouvée. Vérifiez la base de données.")
        sys.exit(1)
    universe_trade_dates = pd.to_datetime(ohlcv_df["trade_date"], errors="coerce")
    universe_trade_dates = universe_trade_dates[
        (universe_trade_dates >= pd.Timestamp(start))
        & (universe_trade_dates <= pd.Timestamp(end))
    ]
    try:
        universe_scope_df = load_tradable_universe_scope(
            engine,
            universe_trade_dates.dropna().unique(),
            capital_preset_key=effective_preset.key,
        )
    except Exception as exc:
        _safe_print(f"❌ Univers tradable PIT indisponible: {exc}")
        sys.exit(1)
    if universe_scope_df.empty:
        _safe_print("❌ Univers tradable PIT vide sur la période demandée.")
        sys.exit(1)
    if ohlcv_start < start:
        _safe_print(
            "   warmup_ohlcv={} jours calendaires ({} → {}) pour ATR/corrélation phase2\n".format(
                (start - ohlcv_start).days,
                ohlcv_start,
                start,
            )
        )
        first_loaded_trade_date = pd.Timestamp(ohlcv_df["trade_date"].min()).date()
        if first_loaded_trade_date >= start:
            _safe_print(
                "   ⚠️ warmup incomplet: aucune barre OHLCV antérieure à {} n'a été chargée ; l'ATR phase2 peut rester indisponible.\n".format(
                    start,
                )
            )

    _safe_print("📈 Chargement scores...")
    try:
        score_load_result = load_scores(
            engine,
            start,
            end,
            capital_preset_key=effective_preset.key,
            scores_pit_mode=scores_pit_mode,
            strict_pit=strict_pit,
            return_diagnostics=True,
        )
    except PitHistoryRequiredError as exc:
        _safe_print(f"❌ {exc}")
        _safe_print("   En mode `pipeline`, le backtest exige des snapshots PIT historisés dans `stock_scores_history`.")
        sys.exit(1)
    scores_df = score_load_result.frame
    score_load_diagnostics = score_load_result.diagnostics
    if scores_df.empty:
        _safe_print("❌ Aucun score candidat trouvé sur la période demandée.")
        _safe_print("   Vérifie d'abord :")
        _safe_print("   - que `stock_scores_history` contient des snapshots historiques ;")
        _safe_print("   - ou, à défaut, que `stock_scores` contient un snapshot récent exploitable.")
        _safe_print("   Pour un vrai backtest 10 ans, il faut historiser les snapshots dans `stock_scores_history`.")
        sys.exit(1)

    prepared_scores = prepare_scores_for_sentiment_mode(
        engine,
        scores_df,
        sentiment_mode=args.sentiment_mode,
        walk_forward_artifacts_dir=Path(args.walk_forward_artifacts_dir) if args.walk_forward_artifacts_dir else None,
        engine_mode=engine_mode,
        return_diagnostics=True,
    )
    if hasattr(prepared_scores, "frame") and hasattr(prepared_scores, "diagnostics"):
        scores_df = prepared_scores.frame
        sentiment_diagnostics = prepared_scores.diagnostics
    else:
        scores_df = prepared_scores
        sentiment_diagnostics = None

    _safe_print("🤖 Chargement prédictions ML...")
    preds_df = load_predictions(engine, start, end, batch_id=args.ml_batch_id)
    try:
        prepared_predictions = prepare_predictions_for_ml_mode(
            engine,
            universe_scope_df,
            preds_df,
            ml_mode=args.ml_mode,
            artifacts_dir=Path(args.artifacts_dir),
            batch_id=args.ml_batch_id,
            engine_mode=engine_mode,
            ml_pit_strategy=ml_pit_strategy,
            return_diagnostics=True,
        )
    except PitMlStrategyUnsupportedError as exc:
        _safe_print(f"❌ {exc}")
        sys.exit(1)
    if hasattr(prepared_predictions, "frame") and hasattr(prepared_predictions, "diagnostics"):
        preds_df = prepared_predictions.frame
        ml_diagnostics = prepared_predictions.diagnostics
    else:
        preds_df = prepared_predictions
        ml_diagnostics = None

    # ── Filtre batch diagnostics (ML quality gate) ──
    # Exclut les prédictions dont le symbole est dans les listes
    # exclude_long / exclude_short du dernier batch complété.
    _bt_filtered_count = 0
    _bt_boosted_count = 0
    try:
        from modelFactory.batch_diagnostics import get_batch_filters, filter_predictions
        # Utilise le batch_id configuré pour le backtest (config.yaml → backtest_batch_id).
        # Si vide, get_batch_filters utilise automatiquement le dernier batch.
        _bt_batch_id: str | None = None
        try:
            import yaml as _yaml_bt_cfg
            with open("config.yaml", encoding="utf-8") as _fh_bt_cfg:
                _cfg_bt_cfg = _yaml_bt_cfg.safe_load(_fh_bt_cfg) or {}
            _bt_batch_id = str(
                (_cfg_bt_cfg.get("batch_diagnostics") or {}).get("backtest_batch_id", "") or ""
            ).strip() or None
        except Exception:
            pass
        _bt_filters = get_batch_filters(engine, batch_id=_bt_batch_id)
        if _bt_filters.batch_id and not preds_df.empty:
            # ── Étape 1 : exclure ──
            _bt_before = len(preds_df)
            preds_df = filter_predictions(preds_df, _bt_filters)
            _bt_filtered_count = _bt_before - len(preds_df)
            if _bt_filtered_count > 0:
                _s7_info = ""
                if _bt_filters.section7.is_active():
                    _s7 = _bt_filters.section7
                    _s7_info = " §7(exclude_all={} flat_path={} long_only={} short_only={})".format(
                        len(_s7.exclude_all), len(_s7.exclude_flat_pathological),
                        len(_s7.long_only), len(_s7.short_only),
                    )
                _safe_print(
                    "   batch_diagnostics: filtered {}/{} predictions "
                    "(batch={} exclude_long={} exclude_short={}){}\n".format(
                        _bt_filtered_count, _bt_before,
                        _bt_filters.batch_id,
                        len(_bt_filters.exclude_long),
                        len(_bt_filters.exclude_short),
                        _s7_info,
                    )
                )

            # ── Étape 2 : booster score prefer (side-aware, parité live) ──
            # Boost uniquement la proba correspondant au predicted_side,
            # et seulement pour les symboles dans le top N (prefer).
            # Cela impacte le selection_score → sizing, en amont des
            # contraintes de risque, comme dans le live (Option C).
            if _bt_filters.prefer and not preds_df.empty:
                _prefer_mult = 1.2
                try:
                    import yaml as _yaml_bt
                    with open("config.yaml", encoding="utf-8") as _fh_bt:
                        _cfg_bt = _yaml_bt.safe_load(_fh_bt) or {}
                    _prefer_mult = float(
                        (_cfg_bt.get("batch_diagnostics") or {}).get(
                            "prefer_sizing_multiplier", 1.2
                        )
                    )
                except Exception:
                    pass
                _prefer_set = _bt_filters.prefer
                _boosted = 0
                # Boost proba_long uniquement pour les prefer prédits long
                if "proba_long" in preds_df.columns and "predicted_side" in preds_df.columns:
                    _mask_long = (
                        preds_df["symbol"].astype(str).str.upper().isin(_prefer_set)
                        & (preds_df["predicted_side"].astype(str).str.lower() == "long")
                    )
                    if _mask_long.any():
                        preds_df.loc[_mask_long, "proba_long"] = (
                            preds_df.loc[_mask_long, "proba_long"] * _prefer_mult
                        ).clip(upper=1.0)
                        _boosted += int(_mask_long.sum())
                # Boost proba_short uniquement pour les prefer prédits short
                if "proba_short" in preds_df.columns and "predicted_side" in preds_df.columns:
                    _mask_short = (
                        preds_df["symbol"].astype(str).str.upper().isin(_prefer_set)
                        & (preds_df["predicted_side"].astype(str).str.lower() == "short")
                    )
                    if _mask_short.any():
                        preds_df.loc[_mask_short, "proba_short"] = (
                            preds_df.loc[_mask_short, "proba_short"] * _prefer_mult
                        ).clip(upper=1.0)
                        _boosted += int(_mask_short.sum())
                _bt_boosted_count = _boosted
                if _bt_boosted_count > 0:
                    _safe_print(
                        "   batch_diagnostics: boosted {} prefer symbols "
                        "x{:.1f} (batch={})\n".format(
                            _bt_boosted_count, _prefer_mult,
                            _bt_filters.batch_id,
                        )
                    )

            # ── §7.0 — log monitor symbols ──
            if _bt_filters.section7.is_active() and _bt_filters.section7.monitor:
                _safe_print(
                    "   batch_diagnostics §7 MONITOR (⚠️ à surveiller): {}\n".format(
                        ", ".join(sorted(_bt_filters.section7.monitor)),
                    )
                )
    except Exception as _bt_exc:
        LOGGER.warning(
            "batch_diagnostics backtest filter skipped (non-blocking): %s",
            _bt_exc,
        )

    # ── Cascade ML (Étape 7) : filtre Global Rank → Per-Symbol ──
    _cascade_batch_id: str | None = None
    _cascade_filtered_count = 0
    _cascade_enabled = False
    try:
        import yaml as _yaml_cas
        with open("config.yaml", encoding="utf-8") as _fh_cas:
            _cfg_cas = _yaml_cas.safe_load(_fh_cas) or {}
        _cas_cfg = _cfg_cas.get("cascade") or {}
        _cascade_enabled = bool(_cas_cfg.get("enabled", True))
        _cascade_batch_id = str(
            (_cfg_cas.get("batch_diagnostics") or {}).get("backtest_batch_id", "") or ""
        ).strip() or None

        if not _cascade_enabled:
            pass  # cascade désactivée → rien à faire
        elif not _cascade_batch_id:
            _safe_print(
                "❌ Cascade ML activée (cascade.enabled=true) mais "
                "batch_diagnostics.backtest_batch_id n'est pas renseigné dans config.yaml.\n"
                "   → Renseigner le batch_id du Global Model à utiliser pour le backtest."
            )
            sys.exit(1)
        elif preds_df.empty:
            _safe_print(
                "🔀 cascade: aucune prédiction ML à filtrer (preds_df vide)."
            )
        else:
            from modelFactory.predictor import apply_cascade_to_predictions
            _cas_before = len(preds_df)
            preds_df = apply_cascade_to_predictions(
                preds_df, _cascade_batch_id, engine=engine,
            )
            _cas_passed = int(preds_df.loc[preds_df["predicted_side"] != "flat"].shape[0]) if "predicted_side" in preds_df.columns else 0
            _cascade_filtered_count = _cas_before - _cas_passed

            if _cas_passed == 0 and _cas_before > 0:
                _safe_print(
                    "❌ Cascade ML : 0/{} prédictions ont passé le filtre (batch={}).\n"
                    "   → Vérifier global_rank_history (10. ML Predict → Prédire l'univers)\n"
                    "   → Vérifier cascade.top_pct (actuel: {}) et cascade.min_prob (actuel: {})\n"
                    "   → backtest interrompu car aucune prédiction viable.".format(
                        _cas_before, _cascade_batch_id,
                        float(_cas_cfg.get("top_pct", 0.20)),
                        float(_cas_cfg.get("min_prob", 0.55)),
                    )
                )
                sys.exit(1)

            _safe_print(
                "   🔀 cascade: {} predictions → flat, {} passed (batch={})\n".format(
                    _cascade_filtered_count, _cas_passed, _cascade_batch_id,
                )
            )
    except SystemExit:
        raise
    except Exception as _cas_exc:
        if _cascade_enabled:
            _safe_print(
                "❌ Cascade ML activée (cascade.enabled=true) mais échec du filtre : {}\n"
                "   Vérifier que global_rank_history est peuplée pour le batch {} "
                "(lancer 10. ML Predict → Prédire l'univers sélectionné d'abord).".format(
                    _cas_exc, _cascade_batch_id or "?",
                )
            )
            sys.exit(1)
        LOGGER.warning(
            "cascade backtest filter skipped (cascade.enabled=false): %s", _cas_exc,
        )

    _emit_backtest_missing_coverage_logs(
        sentiment_mode=str(args.sentiment_mode or "auto"),
        sentiment_diagnostics=sentiment_diagnostics,
        ml_mode=str(args.ml_mode or "auto"),
        ml_diagnostics=ml_diagnostics,
    )
    ml_coverage_gate = _enforce_ml_coverage_gate(
        engine_mode=engine_mode,
        ml_mode=str(args.ml_mode or "auto"),
        ml_diagnostics=ml_diagnostics,
        min_ml_coverage_ratio=getattr(args, "min_ml_coverage_ratio", None),
    )

    # 2. Pivoter OHLCV
    pivoted = pivot_ohlcv(ohlcv_df)

    # P1 — Charger les spreads réels depuis stock_quote_snapshots
    spread_df = None
    if not bool(getattr(args, "no_spread_cost", False)):
        try:
            _safe_print("📊 Chargement spreads bid-ask (P1)...")
            spread_df = load_spreads(engine, start, end)
            if spread_df.empty:
                _safe_print("   ⚠️ Aucun spread chargé — fallback au slippage_bps.")
            else:
                _safe_print(f"   ✅ {len(spread_df)} jours × {len(spread_df.columns)} symboles chargés.")
        except Exception as _spread_exc:
            _safe_print(f"   ⚠️ Spreads indisponibles ({_spread_exc}) — fallback au slippage_bps.")

    nyse_sessions = pd.DatetimeIndex(nyse_session_dates(ohlcv_start, end))
    if len(nyse_sessions) > 0:
        original_session_count = len(pivoted["close"].index)
        pivoted = {
            key: frame.loc[frame.index.intersection(nyse_sessions)].copy()
            for key, frame in pivoted.items()
        }
        filtered_session_count = len(pivoted["close"].index)
        if filtered_session_count != original_session_count:
            LOGGER.info(
                "Calendrier NYSE appliqué : %d date(s) OHLCV hors séance retirée(s).",
                original_session_count - filtered_session_count,
            )
    backtest_start_ts = pd.Timestamp(start)
    backtest_end_ts = pd.Timestamp(end)
    execution_pivoted = {
        key: frame.loc[(frame.index >= backtest_start_ts) & (frame.index <= backtest_end_ts)].copy()
        for key, frame in pivoted.items()
    }

    # 3. Reconstruire les signaux
    _safe_print("🔄 Reconstruction des signaux de conviction...")
    phase2_risk_result = None
    phase2_execution_result = None
    phase3_execution_replay_result = None
    phase4_protection_replay_result = None
    phase5_watcher_replay_result = None
    phase7_exit_lifecycle_result = None
    phase2_risk_run_id = f"bt_phase2_{start:%Y%m%d}_{end:%Y%m%d}"
    research_signals_df = pd.DataFrame()
    from execution_engine.config import ExecutionConfig, load_leverage_config_from_yaml, load_time_stop_config_from_yaml

    execution_config = ExecutionConfig(
        broker_mode="paper",
        dry_run=True,
        account_type=args.account_type,
        swing_only=args.swing_only,
        allow_fractional_shares=bool(args.allow_fractional_shares),
        simulated_account_equity=float(args.equity),
        profit_taker_pct=float(args.tp),
        trailing_stop_pct=float(args.ts),
        leverage=load_leverage_config_from_yaml(),
        time_stop=load_time_stop_config_from_yaml(),
    )
    if phase2_mode == "off":
        research_signals_df = replay_signals(
            preds_df,
            scores_df,
            score_column=None if args.score_column == "auto" else args.score_column,
            max_positions=args.max_positions,
        )
        signals_df = research_signals_df
    else:
        from backtesting.risk_bridge import build_phase2_risk_result

        # Sprint Market-Aware — parite live/backtest : on charge ``market_regimes``
        # depuis ``config.yaml`` et on branche un MacroDataProvider EODHD/Stooq
        # pour rejouer fidelement les decisions de regime (Axes A+D du plan).
        _mr_cfg_for_bt = None
        _macro_provider_for_bt = None
        try:
            from common.config_loader import load_config as _load_yaml_bt
            from service.market import (
                build_default_macro_provider as _build_macro_bt,
                parse_market_regimes as _parse_mr_bt,
                resolve_macro_pit_mode as _resolve_macro_pit_mode_bt,
            )
            _yaml_bt = _load_yaml_bt(getattr(args, "config_path", None))
            _mr_cfg_for_bt = _parse_mr_bt(_yaml_bt.get("market_regimes"))
            args.effective_macro_pit_mode = _resolve_macro_pit_mode_bt(
                _yaml_bt,
                execution_context="backtest",
                macro_pit_mode=macro_pit_mode,
            )
            macro_missing_policy = str(getattr(args, "macro_missing_policy", "") or "").strip().lower()
            if macro_missing_policy in {"allow", "fail"}:
                _mr_cfg_for_bt = replace(
                    _mr_cfg_for_bt,
                    allow_neutral_fallback_on_missing_macro_data=(macro_missing_policy == "allow"),
                )
            args.macro_missing_policy = (
                "allow"
                if getattr(_mr_cfg_for_bt, "allow_neutral_fallback_on_missing_macro_data", False)
                else "fail"
            )
            if getattr(_mr_cfg_for_bt, "enabled", False):
                try:
                    _macro_provider_for_bt = _build_macro_bt(
                        _yaml_bt,
                        execution_context="backtest",
                        macro_pit_mode=macro_pit_mode,
                        engine=engine,
                    )
                except TypeError:
                    _macro_provider_for_bt = _build_macro_bt(_yaml_bt)
        except Exception:
            _mr_cfg_for_bt = None
            _macro_provider_for_bt = None
            args.effective_macro_pit_mode = macro_pit_mode
            args.macro_missing_policy = str(getattr(args, "macro_missing_policy", None) or "disabled")

        try:
            phase2_risk_result = build_phase2_risk_result(
                scores_df=scores_df,
                predictions_df=preds_df if isinstance(preds_df, pd.DataFrame) else pd.DataFrame(),
                close_df=pivoted["close"],
                high_df=pivoted["high"],
                low_df=pivoted["low"],
                volume_df=pivoted.get("volume"),
                risk_config=phase2_risk_config,
                score_column=None if args.score_column == "auto" else args.score_column,
                market_regimes_config=_mr_cfg_for_bt,
                macro_provider=_macro_provider_for_bt,
            )
        except MacroDataUnavailableError as exc:
            _safe_print(f"❌ {exc}")
            _safe_print(
                "   Astuce : relancer avec `--allow-neutral-fallback-on-missing-macro-data` pour continuer le backtest tout en marquant la séance en `data_quality=missing`."
            )
            sys.exit(1)
        signals_df = phase2_risk_result.signals_df
        research_signals_df = phase2_risk_result.signals_df.copy()
        _safe_print(
            "   Phase 2 risk bridge: snapshots={} entries={} accepted={} signals={}\n".format(
                phase2_risk_result.diagnostics.get("snapshot_dates", 0),
                phase2_risk_result.diagnostics.get("entries_total", 0),
                phase2_risk_result.diagnostics.get("entries_accepted", 0),
                phase2_risk_result.diagnostics.get("signals_generated", 0),
            )
        )
        if phase2_mode == "risk_execution":
            if phase3_mode == "execution_replay":
                from backtesting.execution_replay import simulate_phase3_execution_replay

                phase3_execution_replay_result = simulate_phase3_execution_replay(
                    phase2_risk_result.entries,
                    execution_config=execution_config,
                    open_df=execution_pivoted["open"],
                    risk_run_id_prefix=phase2_risk_run_id,
                )
                phase2_execution_result = phase3_execution_replay_result.execution_result
                signals_df = phase3_execution_replay_result.signals_df
                if phase4_mode == "protection_replay":
                    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay

                    phase4_protection_replay_result = build_phase4_protection_replay(
                        phase3_execution_replay_result,
                        execution_config=execution_config,
                    )
                    signals_df = phase4_protection_replay_result.signals_df
                    if phase5_mode == "watcher_replay":
                        from backtesting.protection_watcher_replay import build_phase5_watcher_replay

                        phase5_watcher_replay_result = build_phase5_watcher_replay(
                            phase4_protection_replay_result,
                            high_df=execution_pivoted["high"],
                        )
                        signals_df = phase5_watcher_replay_result.signals_df
                        if phase7_mode == "exit_lifecycle_replay":
                            from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay

                            phase7_exit_lifecycle_result = build_phase7_exit_lifecycle_replay(
                                phase5_watcher_replay_result,
                                high_df=execution_pivoted["high"],
                                low_df=execution_pivoted["low"],
                                intrabar_priority=args.intrabar_priority,
                                swing_only=args.swing_only,
                            )
                            signals_df = phase7_exit_lifecycle_result.signals_df
                            _safe_print(
                                "   Phase 7 exit lifecycle replay: exits={} oco_cancels={} trailing={}\n".format(
                                    phase7_exit_lifecycle_result.diagnostics.get("exit_rows", 0),
                                    phase7_exit_lifecycle_result.diagnostics.get("oco_cancels", 0),
                                    phase7_exit_lifecycle_result.diagnostics.get("filled_trailing_stop", 0),
                                )
                            )
                        _safe_print(
                            "   Phase 5 watcher replay: transitions={} pending={} failed={}\n".format(
                                phase5_watcher_replay_result.diagnostics.get("transitioned_items", 0),
                                phase5_watcher_replay_result.diagnostics.get("pending_items", 0),
                                phase5_watcher_replay_result.diagnostics.get("failed_items", 0),
                            )
                        )
                    _safe_print(
                        "   Phase 4 protection replay: protections={} trailing={} initial_stop={}\n".format(
                            phase4_protection_replay_result.diagnostics.get("protections_replayed", 0),
                            phase4_protection_replay_result.diagnostics.get("trailing_stop_protections", 0),
                            phase4_protection_replay_result.diagnostics.get("initial_stop_protections", 0),
                        )
                    )
                _safe_print(
                    "   Phase 3 execution replay: scheduled_entries={} signals={} skipped_no_next_session={}\n".format(
                        phase3_execution_replay_result.diagnostics.get("scheduled_entries", 0),
                        phase3_execution_replay_result.diagnostics.get("signals_generated", 0),
                        phase3_execution_replay_result.diagnostics.get("skipped_no_next_session", 0),
                    )
                )
            else:
                from backtesting.execution_bridge import simulate_phase2_execution

                phase2_execution_result = simulate_phase2_execution(
                    phase2_risk_result.entries,
                    execution_config=execution_config,
                    trade_date=end,
                    risk_run_id=phase2_risk_run_id,
                )
            _safe_print(
                "   Phase 2 execution bridge: targets={} entry_intents={} child_intents={} fills={}\n".format(
                    phase2_execution_result.diagnostics.get("targets", 0),
                    phase2_execution_result.diagnostics.get("entry_intents", 0),
                    phase2_execution_result.diagnostics.get("child_intents", 0),
                    phase2_execution_result.diagnostics.get("fills", 0),
                )
            )

    # 4. Backtest
    _safe_print("⚡ Exécution du backtest vectorbt...")

    # Phase B/C (refactor) — construire les bundles micro-structure et risk overlay
    # depuis les flags CLI. Tout est neutre par défaut (legacy preserved).
    microstructure_cfg = MicrostructureConfig(
        slippage=SlippageConfig(
            base_bps=float(args.slippage_base_bps),
            impact_coef=float(args.slippage_impact_coef),
            model=args.slippage_model,
        ),
        initial_stop_pct=(0.0 if bool(getattr(args, "use_live_protection_logic", True)) else float(args.initial_stop_pct)),
        max_entry_gap_pct=float(args.max_entry_gap_pct),
        intrabar_priority=args.intrabar_priority,
        execution_model=ExecutionModelConfig(
            model=getattr(args, "execution_model", "next_open") or "next_open",
            split_threshold_adv_pct=float(getattr(args, "execution_split_threshold_adv_pct", 0.0) or 0.0),
            arrival_slippage_factor=float(getattr(args, "execution_arrival_slippage_factor", 0.5) or 0.5),
        ),
    )
    _bull_strict_mode = str(getattr(args, "bull_strict_mode", "off") or "off").strip().lower()
    _needs_benchmark = bool(args.regime_filter) or _bull_strict_mode != "off"
    benchmark_close: pd.Series | None = None
    if _needs_benchmark:
        benchmark_close = _load_benchmark_close(engine, start, end)

    risk_overlay_cfg = RiskOverlayConfig(
        sizing=SizingConfig(
            mode=args.sizing_mode,
            min_weight_pct=float(args.sizing_min_weight_pct),
            max_weight_pct=float(args.sizing_max_weight_pct),
            sector_multipliers=(
                _parse_sector_multipliers_json(getattr(args, "sector_multipliers_json", None))
            ),
            sector_map=(
                _load_sector_map_for_sizing(engine)
                if getattr(args, "sector_multipliers_json", None)
                else None
            ),
        ),
        regime_filter=RegimeFilterConfig(
            enabled=bool(args.regime_filter),
            sma_window=int(args.regime_sma_window),
            bear_threshold=float(args.regime_bear_threshold),
        ),
        bull_strict=BullStrictConfig(
            enabled=_bull_strict_mode != "off",
            mode=_bull_strict_mode if _bull_strict_mode in ("no_shorts", "no_trades") else "no_shorts",
            sma_window=int(getattr(args, "bull_strict_sma_window", 200) or 200),
            ret_window=int(getattr(args, "bull_strict_ret_window", 60) or 60),
            ret_threshold=float(getattr(args, "bull_strict_ret_threshold", 0.03) or 0.03),
        ),
        sectoral_cap=SectoralCapConfig(
            enabled=float(args.max_sector_exposure_pct) > 0.0,
            max_sector_exposure_pct=float(args.max_sector_exposure_pct) or 0.40,
        ),
        drawdown_breaker=DrawdownCircuitBreaker(
            enabled=float(args.max_portfolio_dd_pct) > 0.0,
            max_dd_pct=float(args.max_portfolio_dd_pct) or 0.20,
            recovery_pct=float(args.dd_recovery_pct),
            rolling_peak_window_days=int(args.dd_rolling_peak_window_days),
            degraded_entry_allocation_pct=float(args.dd_degraded_allocation_pct),
            regime_ramp_up_enabled=bool(args.dd_regime_ramp_up_enabled),
            regime_ramp_up_pct_per_day=float(args.dd_regime_ramp_up_pct_per_day),
            regime_ramp_up_max_pct=float(args.dd_regime_ramp_up_max_pct),
            regime_ramp_up_peak_window_days=int(getattr(args, "dd_regime_ramp_up_peak_window_days", 5) or 5),
            force_close_on_breaker=(
                bool(getattr(args, "force_close_on_breaker", False))
                or bool(
                    __import__("common.config_loader", fromlist=["load_config"]).load_config()
                    .get("risk_management", {})
                    .get("force_close_on_breaker", False)
                )
            ),
            force_close_pct=float(
                __import__("common.config_loader", fromlist=["load_config"]).load_config()
                .get("risk_management", {})
                .get("force_close_pct", 0.50)
            ),
        ),
        target_annual_vol=(
            float(args.target_annual_vol) if args.target_annual_vol is not None else None
        ),
    )

    bt_config = BacktestConfig(
        start_date=start, end_date=end,
        initial_equity=args.equity,
        risk_config=RiskConfig(
            account_equity=float(args.equity),
            max_positions=int(args.max_positions),
            allow_fractional_shares=bool(args.allow_fractional_shares),
        ),
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        trailing_stop_long_pct=getattr(args, "ts_long", None),
        trailing_stop_short_pct=getattr(args, "ts_short", None),
        atr_risk_stop_multiple=float(getattr(args, "atr_risk_stop_multiple", 0.0) or 0.0),
        tp_atr_multiple=float(getattr(args, "tp_atr_multiple", 0.0) or 0.0),
        tp_max_pct=float(getattr(args, "tp_max_pct", 0.0) or 0.0),
        use_canonical_costs=bool(getattr(args, "use_canonical_costs", False)),
        atr_trailing_stop_multiplier=float(getattr(args, "atr_ts", 0.0) or 0.0),
        use_live_protection_logic=bool(getattr(args, "use_live_protection_logic", True)),
        max_positions=args.max_positions,
        fees_pct=fees_pct,
        commission_bps=float(args.commission_bps),
        slippage_bps=float(args.slippage_bps),
        use_tiered_commission=bool(getattr(args, "use_tiered_commission", False)),
        exec_config=execution_config,
        trading_constraints=trading_constraints,
        microstructure=microstructure_cfg,
        risk_overlay=risk_overlay_cfg,
        benchmark_close=benchmark_close,
        seed=getattr(args, "seed", None),
        execution_replay_mode=phase3_mode,
        protection_replay_mode=phase4_mode,
        watcher_replay_mode=phase5_mode,
        exit_lifecycle_replay_mode=phase7_mode,
    )
    # P2 (2026-06-25) : charger l'état des trackers si un fichier est fourni
    _tracker_state_path: Path | None = None
    if hasattr(args, "tracker_state") and args.tracker_state:
        _tracker_state_path = Path(str(args.tracker_state))
    elif hasattr(args, "load_tracker_state") and args.load_tracker_state:
        _tracker_state_path = Path("artifacts/backtesting/tracker_state.json")
    if _tracker_state_path is not None and _tracker_state_path.exists():
        try:
            _snapshot = json.loads(_tracker_state_path.read_text(encoding="utf-8"))
            bt_engine = BacktestEngine(bt_config)
            bt_engine.load_tracker_state(_snapshot)
            _safe_print(f"📂 Tracker state chargé depuis {_tracker_state_path}")
        except Exception as _exc:
            LOGGER.warning("Tracker state load failed, using fresh trackers: %s", _exc)
            bt_engine = BacktestEngine(bt_config)
    else:
        bt_engine = BacktestEngine(bt_config)
    pf = bt_engine.run(
        open=execution_pivoted["open"], close=execution_pivoted["close"], high=execution_pivoted["high"], low=execution_pivoted["low"],
        volume=execution_pivoted.get("volume"),
        spread_df=spread_df,
        signals_df=signals_df,
    )
    diagnostics = extract_diagnostics(pf)

    # P2 (2026-06-25) : sauvegarder l'état des trackers pour le prochain run
    if pf.tracker_snapshot and args.output_dir and not getattr(args, "no_save", False):
        try:
            _save_path = Path(args.output_dir) / "tracker_state.json"
            _save_path.parent.mkdir(parents=True, exist_ok=True)
            _save_path.write_text(
                json.dumps(pf.tracker_snapshot, indent=2, default=str),
                encoding="utf-8",
            )
            _safe_print(f"💾 Tracker state saved to {_save_path}")
        except Exception as _exc:
            LOGGER.warning("Tracker state save failed: %s", _exc)

    # Phase 6.1.c — dividendes encaissés (best-effort, fallback 0.0 si DB indispo).
    dividends_received = load_dividends_received(start, end, engine=engine)
    corporate_actions_summary = load_corporate_actions_summary(start, end, engine=engine)
    pipeline_trade_truth_df = next(
        (
            getattr(result, "signals_df", None)
            for result in (
                phase7_exit_lifecycle_result,
                phase5_watcher_replay_result,
                phase4_protection_replay_result,
                phase3_execution_replay_result,
            )
            if result is not None and getattr(result, "signals_df", None) is not None
        ),
        None,
    )
    _, trade_export_summary = build_trade_export_bundle(
        pf,
        pipeline_signals_df=pipeline_trade_truth_df,
        corporate_actions_summary=corporate_actions_summary,
    )

    # 5. Rapport
    report = generate_report(
        pf,
        args.equity,
        dividends_received=dividends_received,
        risk_free_rate=float(getattr(args, "risk_free_rate", 0.0) or 0.0),
    )
    report.print_summary()

    # Sprint S3 / A-011 — bootstrap Monte Carlo + analyse de sensibilité.
    _run_statistical_validation(args, pf, fees_pct=fees_pct, output_dir=Path(args.output_dir) if args.output_dir else None)

    output_dir = Path(args.output_dir) if args.output_dir else None
    artifact_paths: dict[str, str] = {}
    component_details, execution_broker_like_summary = _build_backtest_component_details(
        ohlcv_df=ohlcv_df,
        bars_source_preflight=bars_source_preflight,
        execution_pivoted=execution_pivoted,
        start_date=start,
        end_date=end,
        ohlcv_start=ohlcv_start,
        signals_df=signals_df,
        phase2_mode=phase2_mode,
        phase3_mode=phase3_mode,
        phase4_mode=phase4_mode,
        phase5_mode=phase5_mode,
        phase7_mode=phase7_mode,
        phase2_risk_result=phase2_risk_result,
        phase2_execution_result=phase2_execution_result,
        phase3_execution_replay_result=phase3_execution_replay_result,
        phase4_protection_replay_result=phase4_protection_replay_result,
        phase5_watcher_replay_result=phase5_watcher_replay_result,
        phase7_exit_lifecycle_result=phase7_exit_lifecycle_result,
    )
    fidelity_manifest = build_fidelity_manifest(
        engine_mode=engine_mode,
        start_date=start,
        end_date=end,
        capital_preset_key=effective_preset.key,
        score_diagnostics=score_load_diagnostics,
        sentiment_diagnostics=sentiment_diagnostics,
        ml_diagnostics=ml_diagnostics,
        sentiment_mode=args.sentiment_mode,
        ml_mode=args.ml_mode,
        ml_pit_strategy=ml_pit_strategy,
        component_details=component_details,
        requested_score_column=str(args.score_column or "auto"),
        walk_forward_artifacts_dir=str(args.walk_forward_artifacts_dir or ""),
    )
    replay_diagnostic_summary = build_replay_diagnostic_summary(
        scores_df=scores_df,
        predictions_df=preds_df if isinstance(preds_df, pd.DataFrame) else None,
        signals_df=signals_df if isinstance(signals_df, pd.DataFrame) else None,
        fidelity_manifest=fidelity_manifest,
    )
    selection_target_parity_summary = (
        build_selection_target_parity_summary(
            research_signals_df=research_signals_df,
            risk_entries=phase2_risk_result.entries,
            phase2_mode=phase2_mode,
        )
        if phase2_risk_result is not None
        else None
    )

    common_params = _build_backtest_common_params(
        args=args,
        fees_pct=fees_pct,
        effective_preset=effective_preset,
        preset_source=preset_source,
        preset_fingerprint=preset_fingerprint,
        engine_mode=engine_mode,
        phase2_mode=phase2_mode,
        phase3_mode=phase3_mode,
        phase4_mode=phase4_mode,
        phase5_mode=phase5_mode,
        phase7_mode=phase7_mode,
        ml_pit_strategy=ml_pit_strategy,
        dividends_received=float(dividends_received),
        trading_constraints=trading_constraints,
        bt_config=bt_config,
        microstructure_cfg=microstructure_cfg,
        risk_overlay_cfg=risk_overlay_cfg,
        phase2_risk_result=phase2_risk_result,
        phase2_execution_result=phase2_execution_result,
        phase3_execution_replay_result=phase3_execution_replay_result,
        phase4_protection_replay_result=phase4_protection_replay_result,
        phase5_watcher_replay_result=phase5_watcher_replay_result,
        phase7_exit_lifecycle_result=phase7_exit_lifecycle_result,
    )
    common_params["conviction_calibration"] = _conviction_calibration_diagnostic

    # Phase A.4 — métadonnées de reproductibilité.
    run_metadata = build_run_metadata(
        seed=getattr(args, "seed", None),
        dataset_frames={
            "ohlcv": ohlcv_df,
            "scores": scores_df,
            "predictions": preds_df if isinstance(preds_df, pd.DataFrame) else None,
        },
    )

    if output_dir is not None:
        _safe_print("📝 Sauvegarde du rapport structuré...")
        equity_curve_csv_path = save_equity_curve_csv(pf, output_dir=output_dir)
        trade_audit_csv_path = save_trade_audit_csv(pf, output_dir=output_dir)
        artifact_paths["equity_curve_csv"] = str(equity_curve_csv_path)
        artifact_paths["trade_audit_csv"] = str(trade_audit_csv_path)
        # Diagnostic quotidien circuit breaker drawdown (C.5)
        if hasattr(pf, "drawdown_breaker_df") and not pf.drawdown_breaker_df.empty:
            _dd_breaker_path = Path(output_dir) / "drawdown_breaker_daily.csv"
            pf.drawdown_breaker_df.to_csv(_dd_breaker_path, index=False)
            artifact_paths["drawdown_breaker_daily_csv"] = str(_dd_breaker_path)
            _safe_print(f"   → {_dd_breaker_path}")
        fidelity_manifest_path = save_fidelity_manifest(fidelity_manifest, output_dir)
        artifact_paths["fidelity_manifest_json"] = str(fidelity_manifest_path)
        coverage_summary_path = save_coverage_summary(fidelity_manifest, output_dir)
        artifact_paths["coverage_summary_json"] = str(coverage_summary_path)
        # Matrice symbole × état PIT (anomalie 5.5)
        fidelity_symbol_matrix = build_fidelity_symbol_matrix(
            scores_df=scores_df,
            predictions_df=preds_df if isinstance(preds_df, pd.DataFrame) else None,
            fidelity_manifest=fidelity_manifest,
        )
        symbol_matrix_paths = save_fidelity_symbol_matrix(fidelity_symbol_matrix, output_dir)
        artifact_paths.update({key: str(path) for key, path in symbol_matrix_paths.items()})
        replay_diagnostic_paths = save_replay_diagnostic_summary(replay_diagnostic_summary, output_dir)
        artifact_paths.update({key: str(path) for key, path in replay_diagnostic_paths.items()})
        selection_target_parity_paths: dict[str, str] = {}
        if selection_target_parity_summary is not None:
            selection_target_parity_paths = {
                key: str(path)
                for key, path in save_selection_target_parity_summary(selection_target_parity_summary, output_dir).items()
            }
            artifact_paths.update(selection_target_parity_paths)
        compare_to_live_paths, compare_to_live_summary = _build_compare_to_live_artifacts(
            engine=engine,
            output_dir=output_dir,
            fidelity_manifest=fidelity_manifest,
            scores_df=scores_df,
            research_signals_df=research_signals_df,
            phase2_risk_result=phase2_risk_result,
            phase2_execution_result=phase2_execution_result,
            phase7_exit_lifecycle_result=phase7_exit_lifecycle_result,
            phase2_mode=phase2_mode,
        )
        artifact_paths.update(compare_to_live_paths)
        if phase2_risk_result is not None:
            from backtesting.risk_bridge import save_phase2_risk_artifacts

            artifact_paths.update(save_phase2_risk_artifacts(phase2_risk_result, output_dir))
        if phase2_execution_result is not None and phase3_execution_replay_result is None:
            from backtesting.execution_bridge import save_phase2_execution_artifacts

            artifact_paths.update(save_phase2_execution_artifacts(phase2_execution_result, output_dir))
        if phase3_execution_replay_result is not None:
            from backtesting.execution_replay import save_phase3_execution_replay_artifacts

            phase3_artifacts = cast(
                dict[str, str],
                save_phase3_execution_replay_artifacts(phase3_execution_replay_result, output_dir),
            )
            artifact_paths.update(phase3_artifacts)
        if phase4_protection_replay_result is not None:
            from backtesting.execution_lifecycle_replay import save_phase4_protection_replay_artifacts

            phase4_artifacts = cast(
                dict[str, str],
                save_phase4_protection_replay_artifacts(phase4_protection_replay_result, output_dir),
            )
            artifact_paths.update(phase4_artifacts)
        if phase5_watcher_replay_result is not None:
            from backtesting.protection_watcher_replay import save_phase5_watcher_replay_artifacts

            phase5_artifacts = cast(
                dict[str, str],
                save_phase5_watcher_replay_artifacts(phase5_watcher_replay_result, output_dir),
            )
            artifact_paths.update(phase5_artifacts)
        if phase7_exit_lifecycle_result is not None:
            from backtesting.exit_lifecycle_replay import save_phase7_exit_lifecycle_replay_artifacts

            phase7_artifacts = cast(
                dict[str, str],
                save_phase7_exit_lifecycle_replay_artifacts(phase7_exit_lifecycle_result, output_dir),
            )
            artifact_paths.update(phase7_artifacts)
        fidelity_baseline_snapshot = build_fidelity_baseline_snapshot(
            fidelity_manifest=fidelity_manifest,
            replay_diagnostic_summary=replay_diagnostic_summary,
            selection_target_parity_summary=selection_target_parity_summary,
            compare_to_live_summary=compare_to_live_summary,
            execution_broker_like_summary=execution_broker_like_summary,
            baseline_id=str(getattr(args, "fidelity_baseline_id", "") or "").strip() or None,
        )
        fidelity_baseline_snapshot_path = save_fidelity_baseline_snapshot(fidelity_baseline_snapshot, output_dir)
        artifact_paths["fidelity_baseline_snapshot_json"] = str(fidelity_baseline_snapshot_path)
        fidelity_baseline_id = str(getattr(args, "fidelity_baseline_id", "") or "").strip() or None
        fidelity_baseline_catalog_raw = str(getattr(args, "fidelity_baseline_catalog", "") or "").strip()
        fidelity_baseline_catalog_path = (
            Path(fidelity_baseline_catalog_raw)
            if fidelity_baseline_catalog_raw
            else (Path("config") / "fidelity_baseline_catalog.json" if fidelity_baseline_id else None)
        )
        if fidelity_baseline_catalog_path is not None:
            fidelity_baseline_comparison = build_fidelity_baseline_comparison(
                fidelity_baseline_snapshot,
                catalog_path=fidelity_baseline_catalog_path,
                baseline_id=fidelity_baseline_id,
            )
            fidelity_baseline_paths = {
                key: str(path)
                for key, path in save_fidelity_baseline_comparison(fidelity_baseline_comparison, output_dir).items()
            }
            artifact_paths.update(fidelity_baseline_paths)
            _safe_print(
                "   Sprint 6 baseline fidélité: status={} baseline={} checks={} failed={}\n".format(
                    fidelity_baseline_comparison.get("status", "unknown"),
                    fidelity_baseline_comparison.get("baseline_id") or fidelity_baseline_id or "auto",
                    fidelity_baseline_comparison.get("checked_count", 0),
                    fidelity_baseline_comparison.get("failed_count", 0),
                )
            )
        report_json_path = save_report_json(
            report,
            output_dir=output_dir,
            artifacts=artifact_paths,
            params=common_params,
            diagnostics=diagnostics,
            run_metadata=run_metadata,
            fidelity=fidelity_manifest,
            corporate_actions=corporate_actions_summary,
            trade_export=trade_export_summary,
        )
        artifact_paths["report_json"] = str(report_json_path)
        _safe_print(f"   → {report_json_path}")
        _safe_print(f"   → {equity_curve_csv_path}")
        _safe_print(f"   → {trade_audit_csv_path}")
        _safe_print(f"   → {fidelity_manifest_path}")
        _safe_print(f"   → {coverage_summary_path}")
        _safe_print(f"   → {fidelity_baseline_snapshot_path}")
        for path in replay_diagnostic_paths.values():
            _safe_print(f"   → {path}")
        for path in selection_target_parity_paths.values():
            _safe_print(f"   → {path}")
        if fidelity_baseline_catalog_path is not None:
            for path in fidelity_baseline_paths.values():
                _safe_print(f"   → {path}")

    # 6. Artefacts
    if not args.no_save:
        _safe_print("💾 Sauvegarde des artefacts...")
        equity_curve_path = save_equity_curve(pf, output_dir=output_dir)
        trades_csv_path = save_trades_csv(
            pf,
            output_dir=output_dir,
            pipeline_signals_df=pipeline_trade_truth_df,
            corporate_actions_summary=corporate_actions_summary,
        )
        artifact_paths["equity_curve_png"] = str(equity_curve_path)
        artifact_paths["trades_csv"] = str(trades_csv_path)
        _safe_print(f"   → {equity_curve_path}")
        _safe_print(f"   → {trades_csv_path}")

        if output_dir is not None:
            save_report_json(
                report,
                output_dir=output_dir,
                artifacts=artifact_paths,
                params=common_params,
                diagnostics=diagnostics,
                run_metadata=run_metadata,
                fidelity=fidelity_manifest,
                corporate_actions=corporate_actions_summary,
                trade_export=trade_export_summary,
            )

    _safe_print("✅ Backtest terminé.\n")


def _run_backfill_scores_history(args: argparse.Namespace) -> None:
    """Exécute le backfill PIT de stock_scores_history."""
    from datetime import datetime

    from backtesting.backfill_scores_history import BackfillScoresHistoryService
    from backtesting.data_loader import preflight_required_bars_data_source
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from screener.models import ScreenerConfig
    from selector.alpha_scanner import AlphaScannerConfig

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None
    explicit_flags = _explicit_flags(sys.argv[1:])
    effective_preset, preset_source = resolve_effective_capital_preset(
        capital_preset_key=getattr(args, "capital_preset_key", None),
        equity=float(args.capital) if getattr(args, "capital", None) is not None else None,
    )
    detected_from_capital = (
        resolve_capital_preset_for_equity(float(args.capital)) if getattr(args, "capital", None) is not None else None
    )
    if preset_source == "explicit_key" and detected_from_capital is not None and detected_from_capital.key != effective_preset.key:
        _safe_print(
            f"⚠️ Preset explicite `{effective_preset.key}` prioritaire sur le bucket détecté depuis capital `{detected_from_capital.key}`."
        )
    screener_kwargs = build_screener_config_kwargs_from_preset(effective_preset)
    selector_kwargs = build_selector_config_kwargs_from_preset(effective_preset)
    preset_selection_size = int(selector_kwargs.pop("selection_size"))
    effective_selection_size = int(args.selection_size) if "selection_size" in explicit_flags else preset_selection_size
    # Sprint 6 — short selection size override
    short_size_arg = getattr(args, "selection_size_short", None)
    effective_short_size = int(short_size_arg) if short_size_arg is not None else effective_selection_size
    preset_fingerprint = capital_preset_fingerprint(effective_preset)

    _safe_print(f"\n🧱 Backfill stock_scores_history : start={start} end={end or 'auto'}")
    _safe_print(
        f"   overwrite={args.overwrite_existing} limit_days={args.limit_days or 'all'} "
        f"chunk_size={args.chunk_size} selection_size={args.selection_size} short_size={effective_short_size}\n"
    )
    _safe_print(
        f"   preset_capital={effective_preset.key} ({preset_source}) selection_size_effective={effective_selection_size} fingerprint={preset_fingerprint}\n"
    )

    service = BackfillScoresHistoryService(
        screener_config=ScreenerConfig.strict_swing_cash(chunk_size=args.chunk_size, **screener_kwargs),
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=args.chunk_size,
            selection_size=effective_selection_size,
            short_selection_size=effective_short_size,
            **selector_kwargs,
        ),
        sentiment_config=SentimentBoostConfig(),
        screener_max_workers=args.screener_workers,
        capital_preset_key=effective_preset.key,
        config_fingerprint=preset_fingerprint,
        symbol_source=getattr(args, "symbol_source", None),
    )

    if getattr(args, "universe_only", False):
        _safe_print("\n🧱 Mode universe-only : alimentation tradable_universe_runs + tradable_universe_history depuis stock_scores_history existant.\n")
        result = service.backfill_universe_only(
            start_date=start,
            end_date=end,
            overwrite_existing=args.overwrite_existing,
            limit_days=args.limit_days,
        )
        _safe_print("\n✅ Rattrapage univers terminé")
        _safe_print(f"   Période              : {result.start_date} → {result.end_date}")
        _safe_print(f"   Runs univers créés    : {result.universe_runs_created}")
        _safe_print(f"   Lignes univers écrites: {result.universe_rows_written}\n")
        return

    resolve_end_date = getattr(service, "resolve_end_date", None)
    if callable(resolve_end_date):
        resolved_preflight_end = resolve_end_date(start, explicit_end_date=end)
    else:
        resolved_preflight_end = end or start
    try:
        preflight = _run_bars_source_preflight_or_skip(getattr(service, "engine", None), start, resolved_preflight_end)
    except RuntimeError as exc:
        _safe_print(f"❌ {exc}")
        sys.exit(1)
    _safe_print(
        "   preflight_ohlcv_source={} rows_required={} rows_total={} status={} resolved_end={}\n".format(
            preflight.get("required_data_source"),
            preflight.get("required_rows"),
            preflight.get("rows_total"),
            preflight.get("status"),
            resolved_preflight_end,
        )
    )
    if preflight.get("mixed_sources_detected"):
        _safe_print(
            "   ⚠️ Fenêtre PIT mixte détectée {} — le backfill reconstruit uniquement depuis `{}`.\n".format(
                preflight.get("counts"),
                preflight.get("required_data_source"),
            )
        )
    result = service.backfill(
        start_date=start,
        end_date=end,
        overwrite_existing=args.overwrite_existing,
        limit_days=args.limit_days,
    )

    _safe_print("\n✅ Backfill terminé")
    _safe_print(f"   Période résolue        : {result.start_date} → {result.end_date}")
    _safe_print(f"   Séances traitées       : {result.trading_days_processed}/{result.trading_days_requested}")
    _safe_print(f"   Séances ignorées       : {result.trading_days_skipped_existing}")
    _safe_print(f"   Lignes insérées        : {result.rows_inserted}")
    _safe_print(f"   Runs univers créés     : {result.universe_runs_created}")
    _safe_print(f"   Lignes univers écrites : {result.universe_rows_written}\n")


def _parse_csv_values(raw: str, *, cast_type):
    values = []
    for token in (part.strip() for part in raw.split(",")):
        if not token:
            continue
        values.append(cast_type(token))
    return values


def _run_screener_diagnostics(args: argparse.Namespace) -> None:
    """Exécute le diagnostic PIT phase 4 du screener."""
    from datetime import datetime

    from backtesting.screener_diagnostics import (
        ScreenerDiagnosticsService,
        build_screener_grid_scenarios,
        build_screener_oat_scenarios,
        export_holdout_validation,
        export_screener_objective_recommendations,
        export_screener_regime_recommendations,
        export_screener_recommendations,
        export_screener_diagnostics,
        recommend_screener_scenarios_by_objective,
        recommend_screener_scenarios_by_regime,
        recommend_screener_scenarios,
        validate_recommendations_holdout,
    )
    from event_sentiment.signal_aggregator import SentimentBoostConfig
    from risk_management.config import RiskConfig
    from screener.models import ScreenerConfig
    from selector.alpha_scanner import AlphaScannerConfig

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    rs_values = _parse_csv_values(args.rs_values, cast_type=float)
    range_values = _parse_csv_values(args.range_lookback_values, cast_type=int)
    hist_score_values = _parse_csv_values(args.historical_range_score_values, cast_type=float)
    liquidity_values = _parse_csv_values(args.liquidity_threshold_values, cast_type=float)

    base_screener_config = ScreenerConfig.strict_swing_cash(chunk_size=args.chunk_size)
    if args.mode == "grid":
        scenarios = build_screener_grid_scenarios(
            base_screener_config,
            rs_values=rs_values,
            range_lookback_values=range_values,
            historical_range_score_values=hist_score_values,
            liquidity_threshold_values=liquidity_values,
            max_scenarios=args.max_scenarios,
        )
    else:
        scenarios = build_screener_oat_scenarios(
            base_screener_config,
            rs_values=rs_values,
            range_lookback_values=range_values,
            historical_range_score_values=hist_score_values,
            liquidity_threshold_values=liquidity_values,
        )

    _safe_print(f"\n🧪 Diagnostic screener phase 4 : {start} → {end}")
    _safe_print(
        f"   mode={args.mode} scénarios={len(scenarios)} limit_days={args.limit_days or 'all'} "
        f"chunk_size={args.chunk_size} selection_size={args.selection_size} max_positions={args.max_positions} "
        f"capital_preset_key={args.capital_preset_key or 'default'}\n"
    )

    service = ScreenerDiagnosticsService(
        base_screener_config=base_screener_config,
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=args.chunk_size,
            selection_size=args.selection_size,
        ),
        sentiment_config=SentimentBoostConfig(),
        risk_config=RiskConfig(max_positions=args.max_positions),
        screener_max_workers=args.screener_workers,
        capital_preset_key=args.capital_preset_key,
    )
    result = service.analyze_period(
        start_date=start,
        end_date=end,
        scenarios=scenarios,
        limit_days=args.limit_days,
    )
    recommendation_frame, recommendation_summary = recommend_screener_scenarios(
        result.summary_metrics,
        daily_metrics=result.daily_metrics,
        baseline_name=result.baseline_name,
    )
    regime_recommendations, regime_summary, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
        result.summary_metrics_by_regime,
        daily_metrics=result.daily_metrics,
        baseline_name=result.baseline_name,
    )
    objective_recommendations, objective_summary = recommend_screener_scenarios_by_objective(
        result.summary_metrics,
        daily_metrics=result.daily_metrics,
        summary_metrics_by_regime=result.summary_metrics_by_regime,
        baseline_name=result.baseline_name,
    )
    artifacts = export_screener_diagnostics(result, args.output_dir)
    artifacts.update(export_screener_recommendations(recommendation_frame, recommendation_summary, args.output_dir))
    if not regime_recommendations.empty or not cross_regime_recommendations.empty:
        artifacts.update(
            export_screener_regime_recommendations(
                regime_recommendations,
                regime_summary,
                cross_regime_recommendations,
                cross_regime_summary,
                args.output_dir,
            )
        )
    if not objective_recommendations.empty:
        artifacts.update(
            export_screener_objective_recommendations(
                objective_recommendations,
                objective_summary,
                args.output_dir,
            )
        )

    # Phase 6.1.d — validation hold-out optionnelle.
    if getattr(args, "holdout_train_end", None) and getattr(args, "holdout_test_end", None):
        holdout_df, holdout_summary = validate_recommendations_holdout(
            result.daily_metrics,
            train_end=args.holdout_train_end,
            test_end=args.holdout_test_end,
        )
        if not holdout_df.empty:
            artifacts.update(export_holdout_validation(holdout_df, holdout_summary, args.output_dir))
            _safe_print(
                "Hold-out (Phase 6.1.d) : {} scénarios, top_k_stable_ratio={:.2f}, avg_rank_delta={:+.2f}".format(
                    holdout_summary.get("scenarios_evaluated"),
                    float(holdout_summary.get("stable_top_k_ratio", 0.0)),
                    float(holdout_summary.get("avg_rank_delta", 0.0)),
                )
            )

    _safe_print("✅ Diagnostic terminé")
    _safe_print(f"   Séances évaluées    : {len(result.trading_dates)}")
    _safe_print(f"   Baseline            : {result.baseline_name}")
    _safe_print(f"   Résumé CSV          : {artifacts['summary_metrics']}")
    _safe_print(f"   Journal quotidien   : {artifacts['daily_metrics']}")
    _safe_print(f"   Scénarios           : {artifacts['scenarios']}")
    _safe_print(f"   Métadonnées         : {artifacts['metadata']}\n")
    _safe_print(f"   Recommandations CSV : {artifacts['scenario_recommendations']}")
    _safe_print(f"   Résumé reco JSON    : {artifacts['recommendation_summary']}\n")
    if "market_regimes" in artifacts:
        _safe_print(f"   Régimes marché CSV  : {artifacts['market_regimes']}")
    if "summary_metrics_by_regime" in artifacts:
        _safe_print(f"   Résumé par régime   : {artifacts['summary_metrics_by_regime']}")
    if "scenario_recommendations_by_regime" in artifacts:
        _safe_print(f"   Reco par régime CSV : {artifacts['scenario_recommendations_by_regime']}")
    if "cross_regime_recommendations" in artifacts:
        _safe_print(f"   Reco cross-régimes  : {artifacts['cross_regime_recommendations']}")
    if "cross_regime_recommendation_summary" in artifacts:
        _safe_print(f"   Résumé cross-régime : {artifacts['cross_regime_recommendation_summary']}\n")
    if "scenario_recommendations_by_objective" in artifacts:
        _safe_print(f"   Reco par objectif   : {artifacts['scenario_recommendations_by_objective']}")
    if "recommendation_summary_by_objective" in artifacts:
        _safe_print(f"   Résumé objectifs    : {artifacts['recommendation_summary_by_objective']}\n")

    if recommendation_summary.get("status") == "ok":
        best = recommendation_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis : {} (overall={:.3f}, robustesse={:.3f}, survie={:.3f}, forward={:.3f})".format(
                best["scenario_name"],
                float(best["overall_score"]),
                float(best["robustness_score"]),
                float(best["survival_score"]),
                float(best["forward_quality_score"]),
            )
        )
        _safe_print(f"   Raison              : {best['reason']}\n")

    if cross_regime_summary.get("status") == "ok":
        best_cross = cross_regime_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis cross-régimes : {} (score={:.3f}, mean={:.3f}, worst={:.3f}, coverage={:.3f})".format(
                best_cross["scenario_name"],
                float(best_cross["cross_regime_overall_score"]),
                float(best_cross["mean_regime_overall_score"]),
                float(best_cross["worst_regime_overall_score"]),
                float(best_cross["regime_coverage_ratio"]),
            )
        )
        _safe_print()

    if objective_summary.get("status") == "ok":
        _safe_print("Recommandations adaptatives par objectif :")
        for objective_name in objective_summary.get("available_objectives", []):
            payload = objective_summary.get("objectives", {}).get(objective_name, {})
            best_objective = payload.get("recommended_scenario")
            if not isinstance(best_objective, dict) or not best_objective:
                continue
            _safe_print(
                " - {} : {} (objective_score={:.3f}, overall={:.3f})".format(
                    payload.get("label", objective_name),
                    best_objective.get("scenario_name", "?"),
                    float(best_objective.get("objective_score", 0.0)),
                    float(best_objective.get("overall_score", 0.0)),
                )
            )
        _safe_print()

    if not result.summary_metrics.empty:
        preferred_columns = [
            column
            for column in [
                "scenario_name",
                "days_evaluated",
                "days_failed",
                "selector_selection_count_mean",
                "portfolio_target_count_mean",
                "portfolio_survival_ratio_mean",
                "selector_forward_return_20d_mean",
                "portfolio_forward_return_20d_mean",
                "delta_portfolio_survival_ratio_mean",
                "delta_portfolio_forward_return_20d_mean",
            ]
            if column in result.summary_metrics.columns
        ]
        preview = result.summary_metrics.loc[:, preferred_columns].copy()
        sort_column = next(
            (
                column
                for column in (
                    "portfolio_forward_return_20d_mean",
                    "portfolio_survival_ratio_mean",
                    "delta_portfolio_forward_return_20d_mean",
                    "delta_portfolio_survival_ratio_mean",
                )
                if column in preview.columns
            ),
            None,
        )
        if sort_column is not None:
            preview = preview.sort_values(sort_column, ascending=False).head(10)
        else:
            preview = preview.head(10)
        _safe_print("Top scénarios (aperçu):")
        _safe_print(preview.to_string(index=False))
        _safe_print()

    if not recommendation_frame.empty:
        recommendation_preview_columns = [
            column
            for column in [
                "rank",
                "scenario_name",
                "recommendation_label",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
                "confidence_score",
            ]
            if column in recommendation_frame.columns
        ]
        recommendation_preview = recommendation_frame.loc[:, recommendation_preview_columns].head(10)
        _safe_print("Classement phase 5 (aperçu):")
        _safe_print(recommendation_preview.to_string(index=False))
        _safe_print()

    if not regime_recommendations.empty:
        regime_preview_columns = [
            column
            for column in [
                "market_regime",
                "rank",
                "scenario_name",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
            ]
            if column in regime_recommendations.columns
        ]
        regime_preview = regime_recommendations.loc[:, regime_preview_columns].head(12)
        _safe_print("Classement phase 6 par régime (aperçu):")
        _safe_print(regime_preview.to_string(index=False))
        _safe_print()

    if not cross_regime_recommendations.empty:
        cross_preview_columns = [
            column
            for column in [
                "cross_regime_rank",
                "scenario_name",
                "recommendation_label",
                "cross_regime_overall_score",
                "mean_regime_overall_score",
                "worst_regime_overall_score",
                "regime_coverage_ratio",
            ]
            if column in cross_regime_recommendations.columns
        ]
        _safe_print("Classement cross-régimes (aperçu):")
        _safe_print(cross_regime_recommendations.loc[:, cross_preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not objective_recommendations.empty:
        objective_preview_columns = [
            column
            for column in [
                "objective",
                "objective_label",
                "objective_scope",
                "rank",
                "scenario_name",
                "objective_score",
                "overall_score",
                "objective_recommendation_label",
            ]
            if column in objective_recommendations.columns
        ]
        _safe_print("Classement phase 7 par objectif (aperçu):")
        _safe_print(objective_recommendations.loc[:, objective_preview_columns].head(16).to_string(index=False))
        _safe_print()


def _run_screener_recommendation(args: argparse.Namespace) -> None:
    """Analyse un summary_metrics.csv existant et produit une recommandation phase 5."""
    import pandas as pd

    from backtesting.screener_diagnostics import (
        export_holdout_validation,
        export_screener_objective_recommendations,
        export_screener_recommendations,
        export_screener_regime_recommendations,
        recommend_screener_scenarios_by_objective,
        recommend_screener_scenarios,
        recommend_screener_scenarios_by_regime,
        summarize_screener_diagnostics_by_regime,
        validate_recommendations_holdout,
    )

    input_dir = Path(args.input_dir)
    summary_path = Path(args.summary_csv) if args.summary_csv else input_dir / "summary_metrics.csv"
    daily_path = Path(args.daily_csv) if args.daily_csv else input_dir / "daily_metrics.csv"
    output_dir = Path(args.output_dir) if args.output_dir else summary_path.parent

    if not summary_path.exists():
        _safe_print(f"❌ summary_metrics.csv introuvable : {summary_path}")
        sys.exit(1)

    summary_df = pd.read_csv(summary_path)
    daily_df = pd.read_csv(daily_path) if daily_path.exists() else pd.DataFrame()

    recommendation_frame, recommendation_summary = recommend_screener_scenarios(
        summary_df,
        daily_metrics=daily_df if not daily_df.empty else None,
        baseline_name=args.baseline_name,
        target_horizon=args.target_horizon,
    )
    artifacts = export_screener_recommendations(recommendation_frame, recommendation_summary, output_dir)
    regime_recommendations = pd.DataFrame()
    cross_regime_recommendations = pd.DataFrame()
    cross_regime_summary: dict[str, object] = {"status": "empty", "message": "Aucune analyse par régime disponible."}
    objective_recommendations = pd.DataFrame()
    objective_summary: dict[str, object] = {"status": "empty", "message": "Aucune analyse par objectif disponible."}
    summary_by_regime = pd.DataFrame()
    if not daily_df.empty and "market_regime" in daily_df.columns:
        summary_by_regime = summarize_screener_diagnostics_by_regime(daily_df, baseline_name=args.baseline_name)
        regime_recommendations, regime_summary, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
            summary_by_regime,
            daily_metrics=daily_df,
            baseline_name=args.baseline_name,
            target_horizon=args.target_horizon,
        )
        if not regime_recommendations.empty or not cross_regime_recommendations.empty:
            artifacts.update(
                export_screener_regime_recommendations(
                    regime_recommendations,
                    regime_summary,
                    cross_regime_recommendations,
                    cross_regime_summary,
                    output_dir,
                )
            )
    objective_recommendations, objective_summary = recommend_screener_scenarios_by_objective(
        summary_df,
        daily_metrics=daily_df if not daily_df.empty else None,
        summary_metrics_by_regime=summary_by_regime if not summary_by_regime.empty else None,
        baseline_name=args.baseline_name,
        target_horizon=args.target_horizon,
    )
    if not objective_recommendations.empty:
        artifacts.update(
            export_screener_objective_recommendations(
                objective_recommendations,
                objective_summary,
                output_dir,
            )
        )

    # Phase 6.1.d — validation hold-out optionnelle.
    if getattr(args, "holdout_train_end", None) and getattr(args, "holdout_test_end", None) and not daily_df.empty:
        holdout_df, holdout_summary = validate_recommendations_holdout(
            daily_df,
            train_end=args.holdout_train_end,
            test_end=args.holdout_test_end,
        )
        if not holdout_df.empty:
            artifacts.update(export_holdout_validation(holdout_df, holdout_summary, output_dir))
            _safe_print(
                "Hold-out (Phase 6.1.d) : {} scénarios, top_k_stable_ratio={:.2f}, avg_rank_delta={:+.2f}".format(
                    holdout_summary.get("scenarios_evaluated"),
                    float(holdout_summary.get("stable_top_k_ratio", 0.0)),
                    float(holdout_summary.get("avg_rank_delta", 0.0)),
                )
            )

    _safe_print("✅ Analyse phase 5/6 terminée")
    _safe_print(f"   Summary source      : {summary_path}")
    _safe_print(f"   Daily source        : {daily_path if daily_path.exists() else 'absent'}")
    _safe_print(f"   Recommandations CSV : {artifacts['scenario_recommendations']}")
    _safe_print(f"   Résumé reco JSON    : {artifacts['recommendation_summary']}\n")
    if "scenario_recommendations_by_regime" in artifacts:
        _safe_print(f"   Reco par régime CSV : {artifacts['scenario_recommendations_by_regime']}")
    if "cross_regime_recommendations" in artifacts:
        _safe_print(f"   Reco cross-régimes  : {artifacts['cross_regime_recommendations']}")
    if "cross_regime_recommendation_summary" in artifacts:
        _safe_print(f"   Résumé cross-régime : {artifacts['cross_regime_recommendation_summary']}\n")
    if "scenario_recommendations_by_objective" in artifacts:
        _safe_print(f"   Reco par objectif   : {artifacts['scenario_recommendations_by_objective']}")
    if "recommendation_summary_by_objective" in artifacts:
        _safe_print(f"   Résumé objectifs    : {artifacts['recommendation_summary_by_objective']}\n")

    if recommendation_summary.get("status") == "ok":
        best = recommendation_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis : {} (overall={:.3f}, robustesse={:.3f}, survie={:.3f}, forward={:.3f})".format(
                best["scenario_name"],
                float(best["overall_score"]),
                float(best["robustness_score"]),
                float(best["survival_score"]),
                float(best["forward_quality_score"]),
            )
        )
        _safe_print(f"   Raison              : {best['reason']}\n")

    if cross_regime_summary.get("status") == "ok":
        best_cross = cross_regime_summary["recommended_scenario"]
        _safe_print(
            "Meilleur compromis cross-régimes : {} (score={:.3f}, mean={:.3f}, worst={:.3f}, coverage={:.3f})".format(
                best_cross["scenario_name"],
                float(best_cross["cross_regime_overall_score"]),
                float(best_cross["mean_regime_overall_score"]),
                float(best_cross["worst_regime_overall_score"]),
                float(best_cross["regime_coverage_ratio"]),
            )
        )
        _safe_print()

    if objective_summary.get("status") == "ok":
        _safe_print("Recommandations adaptatives par objectif :")
        for objective_name in objective_summary.get("available_objectives", []):
            payload = objective_summary.get("objectives", {}).get(objective_name, {})
            best_objective = payload.get("recommended_scenario")
            if not isinstance(best_objective, dict) or not best_objective:
                continue
            _safe_print(
                " - {} : {} (objective_score={:.3f}, overall={:.3f})".format(
                    payload.get("label", objective_name),
                    best_objective.get("scenario_name", "?"),
                    float(best_objective.get("objective_score", 0.0)),
                    float(best_objective.get("overall_score", 0.0)),
                )
            )
        _safe_print()

    if not recommendation_frame.empty:
        preview_columns = [
            column
            for column in [
                "rank",
                "scenario_name",
                "recommendation_label",
                "overall_score",
                "robustness_score",
                "survival_score",
                "forward_quality_score",
                "confidence_score",
                "recommendation_warnings",
            ]
            if column in recommendation_frame.columns
        ]
        _safe_print("Top recommandations (aperçu):")
        _safe_print(recommendation_frame.loc[:, preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not cross_regime_recommendations.empty:
        cross_preview_columns = [
            column
            for column in [
                "cross_regime_rank",
                "scenario_name",
                "recommendation_label",
                "cross_regime_overall_score",
                "mean_regime_overall_score",
                "worst_regime_overall_score",
                "regime_coverage_ratio",
            ]
            if column in cross_regime_recommendations.columns
        ]
        _safe_print("Top recommandations cross-régimes (aperçu):")
        _safe_print(cross_regime_recommendations.loc[:, cross_preview_columns].head(10).to_string(index=False))
        _safe_print()

    if not objective_recommendations.empty:
        objective_preview_columns = [
            column
            for column in [
                "objective",
                "objective_label",
                "objective_scope",
                "rank",
                "scenario_name",
                "objective_score",
                "overall_score",
                "objective_recommendation_label",
                "objective_reason",
            ]
            if column in objective_recommendations.columns
        ]
        _safe_print("Top recommandations phase 7 (aperçu):")
        _safe_print(objective_recommendations.loc[:, objective_preview_columns].head(16).to_string(index=False))
        _safe_print()


def _run_calibrate_sentiment_weights(args: argparse.Namespace) -> None:
    from datetime import datetime

    from backtesting.sentiment_calibration import SentimentWeightCalibrator

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())

    _safe_print(f"\n🧪 Calibration poids sentiment : {start} → {end}")
    _safe_print(
        f"   horizons={','.join(str(horizon) for horizon in horizons)} top_n={args.top_n} "
        f"all_symbols={args.all_symbols} capital_preset_key={args.capital_preset_key or 'all'} "
        f"output_dir={args.output_dir}\n"
    )

    calibrator = SentimentWeightCalibrator()
    result, ranking_df, artifacts = calibrator.calibrate(
        start_date=start,
        end_date=end,
        horizons=horizons,
        top_n=args.top_n,
        selected_only=not args.all_symbols,
        output_dir=Path(args.output_dir),
        capital_preset_keys=args.capital_preset_key,
        symbol_source=getattr(args, "symbol_source", None) or None,
    )

    _safe_print("✅ Calibration terminée")
    _safe_print(f"   Scénarios évalués   : {result.scenarios_evaluated}")
    _safe_print(f"   Lignes évaluées     : {result.rows_evaluated}")
    _safe_print(f"   Meilleur scénario   : {result.best_scenario_name}")
    _safe_print(f"   Score global        : {result.best_overall_score:.4f}")
    if artifacts:
        _safe_print(f"   CSV classement      : {artifacts.get('calibration_csv')}")
        _safe_print(f"   JSON meilleur       : {artifacts.get('best_json')}\n")
    if not ranking_df.empty:
        preview_columns = [
            column
            for column in [
                "scenario_name",
                "sentiment_weight",
                "macro_weight",
                "quant_weight",
                "overall_score",
                "score_5d",
                "score_10d",
                "score_20d",
            ]
            if column in ranking_df.columns
        ]
        _safe_print("Top scénarios calibration (aperçu):")
        _safe_print(ranking_df.loc[:, preview_columns].head(10).to_string(index=False))
        _safe_print()


# P2 (2026-06-25) — calibration conviction (quant/ML) + Kelly
def _run_calibrate_conviction_weights(args: argparse.Namespace) -> None:
    from datetime import datetime

    from backtesting.weights_calibration import (
        EmpiricalRiskCalibrator,
        persist_calibration_run,
    )

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())

    _safe_print(f"\n🎯 Calibration conviction (quant/ML) + Kelly : {start} → {end}")
    top_n_long = getattr(args, "top_n_long", None)
    top_n_short = getattr(args, "top_n_short", None)
    _safe_print(
        f"   horizons={','.join(str(h) for h in horizons)} top_n={args.top_n} "
        f"top_n_long={top_n_long or args.top_n} top_n_short={top_n_short or args.top_n} "
        f"scope={args.scope} output_dir={args.output_dir}\n"
    )

    calibrator = EmpiricalRiskCalibrator()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for horizon in horizons:
        _safe_print(f"── Horizon {horizon}j ──")
        try:
            run, fold_df, oos_df, signals_df, artifacts = calibrator.walk_forward_backtest(
                start_date=start,
                end_date=end,
                output_dir=output_dir / f"horizon_{horizon}d",
                top_n=args.top_n,
                top_n_long=top_n_long,
                top_n_short=top_n_short,
                horizon_days=horizon,
                use_backtest_kelly=bool(getattr(args, "backtest_kelly", False)),
            )
            _safe_print(f"   Folds évalués       : {run.folds_evaluated}")
            _safe_print(f"   Meilleur scénario   : {run.latest_best_scenario_name}")
            _safe_print(f"   Sharpe              : {run.sharpe_ratio:.3f}")
            _safe_print(f"   Return total        : {run.total_return_pct:.1f}%")
            if run.best_weights:
                _safe_print(f"   Meilleurs poids     : {run.best_weights}")

            # Persister en DB si disponible
            try:
                persist_calibration_run(
                    run,
                    engine=None,  # auto-detect
                    run_summary=run,
                )
            except Exception:
                pass
        except Exception as exc:
            _safe_print(f"   ⚠️ Échec horizon {horizon}j : {exc}")

    _safe_print("\n✅ Calibration conviction terminée")


def _run_walk_forward_conviction(args: argparse.Namespace) -> None:
    """Sprint 4 — walk-forward complet conviction + Kelly + validation OOS."""
    from datetime import datetime

    from backtesting.weights_calibration import EmpiricalRiskCalibrator
    from selector.config import resolve_symmetric_grid

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())
    use_backtest_kelly = bool(getattr(args, "backtest_kelly", False))

    # Sprint 5 — résolution des grilles symétriques
    symmetric_grid = getattr(args, "symmetric_grid", None)
    top_n_long = getattr(args, "top_n_long", None)
    top_n_short = getattr(args, "top_n_short", None)
    enforce_net_exposure = bool(getattr(args, "enforce_net_exposure", False))
    net_exposure_target = float(getattr(args, "net_exposure_target", 0.0))

    if symmetric_grid:
        selection_size, short_selection_size = resolve_symmetric_grid(symmetric_grid)
        _safe_print(f"   Grille symétrique   : {symmetric_grid} → {selection_size}L / {short_selection_size}S")
    else:
        selection_size = top_n_long or args.top_n
        short_selection_size = top_n_short or args.top_n

    _safe_print(f"\n🔄 Walk-forward conviction : {start} → {end}")
    _safe_print(
        f"   horizons={','.join(str(h) for h in horizons)} top_n_long={selection_size} top_n_short={short_selection_size} "
        f"min_train_days={args.min_train_days} test_days={args.test_days} "
        f"backtest_kelly={use_backtest_kelly} net_exposure={'enforced' if enforce_net_exposure else 'free'} "
        f"output_dir={args.output_dir}\n"
    )

    calibrator = EmpiricalRiskCalibrator()

    for horizon in horizons:
        _safe_print(f"── Horizon {horizon}j ──")
        try:
            report = calibrator.walk_forward_optimize(
                start_date=start,
                end_date=end,
                output_dir=Path(args.output_dir) / f"horizon_{horizon}d",
                top_n=args.top_n,
                horizon_days=horizon,
                min_train_days=args.min_train_days,
                test_days=args.test_days,
                step_days=args.step_days,
                use_backtest_kelly=use_backtest_kelly,
                # Sprint 5 — market-neutral params
                top_n_long=selection_size if selection_size != args.top_n else None,
                top_n_short=short_selection_size if short_selection_size != args.top_n else None,
                enforce_net_exposure=enforce_net_exposure,
                net_exposure_target=net_exposure_target if enforce_net_exposure else None,
            )
            summary = report.get("summary", {})
            folds = report.get("folds", [])
            best = report.get("best_overall_scenario", {})
            _safe_print(f"   Folds évalués       : {summary.get('folds_evaluated', 0)}")
            _safe_print(f"   Sharpe OOS moyen    : {summary.get('oos_sharpe_mean', 0):.4f} ± {summary.get('oos_sharpe_std', 0):.4f}")
            if best:
                _safe_print(f"   Meilleur fold       : {best.get('fold_index')} (Sharpe OOS: {best.get('oos_sharpe_combined', 0):.4f})")
            for f in folds:
                _safe_print(
                    f"   Fold {f['fold_index']:02d} | train Sharpe={f['train_sharpe']:.3f} "
                    f"| OOS long={f['oos_sharpe_long']:.3f} short={f['oos_sharpe_short']:.3f} "
                    f"combined={f['oos_sharpe_combined']:.3f}"
                )
        except Exception as exc:
            _safe_print(f"   ⚠️ Échec horizon {horizon}j : {exc}")

    _safe_print("\n✅ Walk-forward conviction terminé")


def _run_walk_forward_sentiment(args: argparse.Namespace) -> None:
    from datetime import datetime

    from backtesting.sentiment_calibration import SentimentWeightCalibrator

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())

    _safe_print(f"\n🧭 Walk-forward sentiment : {start} → {end}")
    _safe_print(
        "   horizons={} top_n={} min_train_days={} test_days={} step_days={} max_positions={} capital_preset_key={} output_dir={}\n".format(
            ",".join(str(horizon) for horizon in horizons),
            args.top_n,
            args.min_train_days,
            args.test_days,
            args.step_days,
            args.max_positions,
            args.capital_preset_key or "all",
            args.output_dir,
        )
    )

    # Résoudre les presets (nouveau format CSV prioritaire, fallback singulier)
    preset_keys: str | list[str] | None = None
    if getattr(args, "capital_preset_keys", None):
        preset_keys = str(args.capital_preset_keys)
    elif getattr(args, "capital_preset_key", None):
        preset_keys = str(args.capital_preset_key)

    calibrator = SentimentWeightCalibrator()
    result, fold_df, _, _, artifacts = calibrator.walk_forward_backtest(
        start_date=start,
        end_date=end,
        horizons=horizons,
        top_n=args.top_n,
        selected_only=not args.all_symbols,
        min_train_days=args.min_train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        max_positions=args.max_positions,
        initial_equity=args.equity,
        profit_taker_pct=args.tp,
        trailing_stop_pct=args.ts,
        fees_pct=args.fees,
        output_dir=Path(args.output_dir),
        capital_preset_keys=preset_keys,
        atr_trailing_stop_multiplier=args.atr_ts,
        symbol_source=getattr(args, "symbol_source", None) or None,
    )

    _safe_print("✅ Walk-forward terminé")
    _safe_print(f"   Folds évalués       : {result.folds_evaluated}")
    _safe_print(f"   Lignes OOS          : {result.out_of_sample_rows}")
    _safe_print(f"   Jours OOS           : {result.out_of_sample_days}")
    _safe_print(f"   Dernier meilleur    : {result.latest_best_scenario_name}")
    _safe_print(f"   Valeur finale       : {result.final_value:,.2f}$")
    _safe_print(f"   Rendement total     : {result.total_return_pct:.2f}%")
    _safe_print(f"   Sharpe              : {result.sharpe_ratio:.3f}")
    _safe_print(f"   Max drawdown        : {result.max_drawdown_pct:.2f}%")
    if artifacts:
        _safe_print(f"   Rapport JSON        : {artifacts.get('report_json')}")
        _safe_print(f"   Folds CSV           : {artifacts.get('walk_forward_folds_csv')}")
        _safe_print(f"   Scores OOS CSV      : {artifacts.get('walk_forward_out_of_sample_scores_csv')}")
        _safe_print(f"   Signaux CSV         : {artifacts.get('walk_forward_selected_signals_csv')}\n")
    if not fold_df.empty:
        preview_columns = [
            column
            for column in [
                "fold_index",
                "train_start_date",
                "train_end_date",
                "test_start_date",
                "test_end_date",
                "best_scenario_name",
                "best_train_overall_score",
                "out_of_sample_overall_score",
            ]
            if column in fold_df.columns
        ]
        _safe_print("Folds walk-forward (aperçu):")
        _safe_print(fold_df.loc[:, preview_columns].to_string(index=False))
        _safe_print()


def _run_walk_forward_financial(args: argparse.Namespace) -> None:
    """Section 17 Point 7-R1 : walk-forward financier intégré."""
    import logging
    from datetime import date as dt_date

    from backtesting.statistical_validation import WalkForwardPlan
    from backtesting.walk_forward_engine import (
        WalkForwardConfig,
        create_db_data_provider,
        generate_walk_forward_report,
        run_walk_forward,
    )
    from risk_management.config import load_risk_config

    LOGGER = logging.getLogger(__name__)

    start = dt_date.fromisoformat(args.start)
    end = dt_date.fromisoformat(args.end)

    _safe_print(f"\n🔄 Walk-forward financier : {start} → {end}")
    _safe_print(f"   equity={args.equity:.0f} train={args.train_days}j val={args.val_days}j test={args.test_days}j step={args.step_days}j")
    _safe_print(f"   purge={args.purge_days}j embargo={args.embargo_days}j max_positions={args.max_positions}")

    # 1. Construire les folds
    plan_folds: list[WalkForwardPlan] = []
    current = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    fold_idx = 0

    while current + pd.Timedelta(days=args.train_days + args.val_days + args.test_days) <= end_ts:
        train_start = current
        train_end = train_start + pd.Timedelta(days=args.train_days)
        val_start = train_end + pd.Timedelta(days=args.purge_days)
        val_end = val_start + pd.Timedelta(days=args.val_days)
        test_start = val_end + pd.Timedelta(days=args.embargo_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)

        plan = WalkForwardPlan(
            train_start=train_start.strftime("%Y-%m-%d"),
            train_end=train_end.strftime("%Y-%m-%d"),
            val_start=val_start.strftime("%Y-%m-%d"),
            val_end=val_end.strftime("%Y-%m-%d"),
            test_start=test_start.strftime("%Y-%m-%d"),
            test_end=test_end.strftime("%Y-%m-%d"),
            purge_days=args.purge_days,
            embargo_days=args.embargo_days,
            fold_index=fold_idx,
        )
        plan_folds.append(plan)
        current += pd.Timedelta(days=args.step_days)
        fold_idx += 1

    _safe_print(f"   Folds planifiés : {len(plan_folds)}")

    if not plan_folds:
        _safe_print("   ⚠️ Aucun fold possible avec les paramètres donnés.")
        return

    # 2. Charger les données complètes
    from common.database import get_engine

    engine = get_engine()
    try:
        from backtesting.data_loader import load_scores, load_predictions, load_ohlcv

        scores_df = load_scores(engine, start, end)
        _safe_print(f"   Scores chargés : {len(scores_df)} lignes")
    except Exception:
        LOGGER.warning("Impossible de charger les scores", exc_info=True)
        scores_df = pd.DataFrame()

    try:
        from backtesting.data_loader import load_predictions as _load_pred
        predictions_df = _load_pred(engine, start, end)
        _safe_print(f"   Prédictions chargées : {len(predictions_df)} lignes")
    except Exception:
        predictions_df = None

    try:
        ohlcv = load_ohlcv(engine, start, end)
        close_df = ohlcv.get("close") if ohlcv is not None and isinstance(ohlcv, dict) else None
        high_df = ohlcv.get("high") if ohlcv is not None and isinstance(ohlcv, dict) else None
        low_df = ohlcv.get("low") if ohlcv is not None and isinstance(ohlcv, dict) else None
        volume_df = ohlcv.get("volume") if ohlcv is not None and isinstance(ohlcv, dict) else None
        _safe_print(f"   OHLCV chargé")
    except Exception:
        close_df = high_df = low_df = volume_df = None

    # 3. Config risque unifiée
    risk_config = load_risk_config(
        equity=args.equity,
        cli_overrides={
            "account_equity": args.equity,
            "max_positions": args.max_positions,
            "dry_run": True,
        },
    )
    _safe_print(f"   Config fingerprint : {risk_config.fingerprint}")

    # 4. DataProvider
    provider = create_db_data_provider(
        scores_df=scores_df,
        predictions_df=predictions_df,
        close_df=close_df,
        high_df=high_df,
        low_df=low_df,
        volume_df=volume_df,
    )

    # 5. Exécuter le walk-forward
    wf_config = WalkForwardConfig(
        initial_equity=args.equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
    )

    result = run_walk_forward(
        plan_folds=plan_folds,
        config=risk_config,
        wf_config=wf_config,
        data_provider=provider,
        n_trials=args.n_trials,
    )

    _safe_print(f"\n📊 Résultats : {result.n_folds} folds, {result.n_folds_positive} positifs")
    _safe_print(f"   Sharpe médian    : {result.median_sharpe:.3f}")
    _safe_print(f"   Sharpe p25       : {result.percentile_25_sharpe:.3f}")
    _safe_print(f"   Rendement médian : {result.median_return_pct:.1f}%")
    _safe_print(f"   DD médian        : {result.median_max_dd_pct:.1f}%")
    _safe_print(f"   Profit factor    : {result.median_profit_factor:.2f}")
    _safe_print(f"   Stabilité folds  : {result.fold_stability_pct:.0f}%")
    _safe_print(f"   Coûts/alpha      : {result.avg_cost_ratio_pct:.0f}%")
    if result.deflated_sharpe is not None:
        _safe_print(f"   Deflated Sharpe  : {result.deflated_sharpe:.3f} (p={result.deflated_sharpe_pvalue:.4f})")
    if result.promotion_score is not None:
        _safe_print(f"   Promotion score  : {result.promotion_score:.3f} ({'✅ PROMOTABLE' if result.is_promotable else '❌ NON PROMOTABLE'})")

    # 6. Rapport
    report = generate_walk_forward_report(
        result=result,
        config=risk_config,
        plan_folds=plan_folds,
        output_path=args.output,
    )

    gates = report._compute_gates()
    passed = sum(1 for g in gates.values() if isinstance(g, dict) and g.get("passed"))
    total = sum(1 for g in gates.values() if isinstance(g, dict))
    _safe_print(f"\n🚦 Gates : {passed}/{total} passés")
    for name, gate in gates.items():
        if isinstance(gate, dict):
            status = "✅" if gate["passed"] else "❌"
            _safe_print(f"   {status} {name}: {gate['value']} (seuil: {gate['threshold']})")

    if args.output:
        _safe_print(f"\n📄 Rapport écrit : {args.output}")


def main() -> None:
    configure_root_logging()
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        if args.ml_mode != "off" and not str(args.ml_batch_id or "").strip():
            parser.error("--ml-batch-id est obligatoire lorsque --ml-mode n'est pas off.")
        _run_backtest(args)
    elif args.command == "backfill-scores-history":
        _run_backfill_scores_history(args)
    elif args.command == "diagnose-screener":
        _run_screener_diagnostics(args)
    elif args.command == "recommend-screener":
        _run_screener_recommendation(args)
    elif args.command == "calibrate-sentiment-weights":
        _run_calibrate_sentiment_weights(args)
    elif args.command == "calibrate-conviction-weights":
        _run_calibrate_conviction_weights(args)
    elif args.command == "walk-forward-conviction":
        _run_walk_forward_conviction(args)
    elif args.command == "walk-forward-sentiment":
        _run_walk_forward_sentiment(args)
    elif args.command == "walk-forward-financial":
        _run_walk_forward_financial(args)
    else:
        parser.print_help()
        sys.exit(1)


