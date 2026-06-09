"""Bridge opt-in entre le backtesting et le moteur réel de risk management."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING

import pandas as pd

from backtesting.signal_replay import _pick_score_column
from common.quantity_utils import normalize_share_quantity
from risk_management.config import RiskConfig
from risk_management.models import CandidateScore, PortfolioEntry, PredictionInfo, PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder
from risk_management.regime_apply import apply_snapshot

if TYPE_CHECKING:
    from service.market import MarketRegimesConfig


RISK_SIGNAL_COLUMNS = [
    "trade_date",
    "symbol",
    "selected",
    "rank",
    "candidate_rank",
    "score",
    "score_source",
    "conviction_score",
    "conviction_source",
    "predicted_proba",
    "selector_signal_mode",
    "selection_explanation",
    "selector_earnings_blackout",
    "target_weight",
    "target_notional",
    "approved_shares",
    "decision",
    "decision_reason",
    "decision_reason_code",
]


@dataclass(slots=True)
class RiskBridgeResult:
    entries: list[PortfolioEntry]
    signals_df: pd.DataFrame
    diagnostics: dict[str, object]
    regime_snapshots: dict[date, dict] = field(default_factory=dict)


def _normalize_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    if "trade_date" in normalized.columns:
        normalized["trade_date"] = pd.to_datetime(normalized["trade_date"], errors="coerce").dt.normalize()
    return normalized


def _resolve_float(row: pd.Series, column: str) -> float | None:
    value = row.get(column)
    if value is None or pd.isna(value):
        return None
    return float(value)


def _prepare_score_columns(scores_df: pd.DataFrame, *, preferred_score_column: str | None = None) -> pd.DataFrame:
    prepared = _normalize_trade_dates(scores_df)
    score_series, source_series = _pick_score_column(prepared, preferred=preferred_score_column)
    prepared["score"] = score_series.values
    if "score_source" in prepared.columns:
        prepared["score_source"] = prepared["score_source"].where(prepared["score_source"].notna(), source_series.values)
    else:
        prepared["score_source"] = source_series.values
    return prepared


def _build_candidates(scores_df: pd.DataFrame, snapshot_date: date) -> list[CandidateScore]:
    day_df = _normalize_trade_dates(scores_df)
    day_df = day_df.loc[day_df["trade_date"] == pd.Timestamp(snapshot_date)]
    if day_df.empty:
        return []

    candidates: list[CandidateScore] = []
    for _, row in day_df.iterrows():
        candidates.append(
            CandidateScore(
                symbol=str(row.get("symbol") or ""),
                sector=str(row.get("sector") or "Unknown"),
                score_used=float(row.get("score") if row.get("score") is not None and not pd.isna(row.get("score")) else row.get("final_score_sentiment", row.get("final_score", 0.0))),
                score_source=str(row.get("score_source") or "final_score_sentiment"),
                company_idio_score=_resolve_float(row, "company_idio_score"),
                macro_regime_score=_resolve_float(row, "macro_regime_score"),
                company_idio_signal_norm=_resolve_float(row, "company_idio_signal_norm"),
                macro_regime_signal_norm=_resolve_float(row, "macro_regime_signal_norm"),
                company_idio_component=_resolve_float(row, "company_idio_component"),
                macro_regime_component=_resolve_float(row, "macro_regime_component"),
                quant_component=_resolve_float(row, "quant_component"),
                walk_forward_sentiment_weight=_resolve_float(row, "walk_forward_sentiment_weight"),
                walk_forward_macro_weight=_resolve_float(row, "walk_forward_macro_weight"),
                walk_forward_quant_weight=_resolve_float(row, "walk_forward_quant_weight"),
                calibration_run_id=str(row.get("calibration_run_id")) if row.get("calibration_run_id") is not None and not pd.isna(row.get("calibration_run_id")) else None,
                calibration_source=str(row.get("calibration_source")) if row.get("calibration_source") is not None and not pd.isna(row.get("calibration_source")) else None,
                snapshot_date=snapshot_date,
                candidate_rank=int(row.get("candidate_rank")) if row.get("candidate_rank") is not None and not pd.isna(row.get("candidate_rank")) else None,
                selector_signal_mode=str(row.get("selector_signal_mode")) if row.get("selector_signal_mode") is not None and not pd.isna(row.get("selector_signal_mode")) else None,
                selection_explanation=str(row.get("selection_explanation")) if row.get("selection_explanation") is not None and not pd.isna(row.get("selection_explanation")) else None,
                selector_earnings_blackout=int(row.get("selector_earnings_blackout")) if row.get("selector_earnings_blackout") is not None and not pd.isna(row.get("selector_earnings_blackout")) else (
                    int(row.get("earnings_blackout")) if row.get("earnings_blackout") is not None and not pd.isna(row.get("earnings_blackout")) else None
                ),
            )
        )
    return candidates


def _compute_atr_20(high_series: pd.Series, low_series: pd.Series, close_series: pd.Series) -> float | None:
    if high_series.empty or low_series.empty or close_series.empty:
        return None
    prev_close = close_series.shift(1)
    tr_components = pd.concat(
        [
            (high_series - low_series).abs(),
            (high_series - prev_close).abs(),
            (low_series - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    atr = true_range.rolling(window=20, min_periods=20).mean().iloc[-1]
    if pd.isna(atr):
        return None
    return float(atr)


def _build_prices(
    *,
    close_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    snapshot_date: date,
    symbols: Iterable[str],
) -> dict[str, PriceInfo]:
    prices: dict[str, PriceInfo] = {}
    snapshot_ts = pd.Timestamp(snapshot_date)
    close_hist = close_df.loc[close_df.index <= snapshot_ts]
    high_hist = high_df.loc[high_df.index <= snapshot_ts]
    low_hist = low_df.loc[low_df.index <= snapshot_ts]
    for symbol in symbols:
        if symbol not in close_hist.columns:
            continue
        symbol_close = close_hist[symbol].dropna()
        if symbol_close.empty:
            continue
        last_close = float(symbol_close.iloc[-1])
        atr_20 = _compute_atr_20(
            high_hist[symbol].dropna() if symbol in high_hist.columns else pd.Series(dtype=float),
            low_hist[symbol].dropna() if symbol in low_hist.columns else pd.Series(dtype=float),
            symbol_close,
        )
        prices[symbol] = PriceInfo(
            symbol=symbol,
            last_close=last_close,
            atr_20=atr_20,
            price_asof_date=snapshot_date,
            atr_asof_date=snapshot_date if atr_20 is not None else None,
        )
    return prices


def _build_predictions(predictions_df: pd.DataFrame, snapshot_date: date) -> dict[str, PredictionInfo]:
    if predictions_df.empty:
        return {}
    normalized = _normalize_trade_dates(predictions_df)
    day_df = normalized.loc[normalized["trade_date"] == pd.Timestamp(snapshot_date)]
    result: dict[str, PredictionInfo] = {}
    for _, row in day_df.iterrows():
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        pred_class = int(row.get("predicted_class", 0) or 0)
        result[symbol] = PredictionInfo(
            symbol=symbol,
            predicted_proba=float(row.get("predicted_proba", 0.0) or 0.0),
            predicted_class=pred_class,
            run_id=str(row.get("run_id") or "backtest"),
            prediction_date=snapshot_date,
        )
    return result


def _build_return_matrix(close_df: pd.DataFrame, snapshot_date: date, symbols: list[str], lookback_days: int) -> pd.DataFrame | None:
    snapshot_ts = pd.Timestamp(snapshot_date)
    hist = close_df.loc[close_df.index <= snapshot_ts, [symbol for symbol in symbols if symbol in close_df.columns]].dropna(how="all")
    if hist.empty:
        return None
    returns = hist.pct_change(fill_method=None).dropna(how="all")
    if returns.empty:
        return None
    tail = returns.tail(lookback_days)
    return tail if not tail.empty else None


def portfolio_entries_to_signals(entries: list[PortfolioEntry], snapshot_date: date) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, entry in enumerate(entries, start=1):
        if entry.approved_shares <= 0:
            continue
        rows.append(
            {
                "trade_date": pd.Timestamp(snapshot_date),
                "symbol": entry.symbol,
                "selected": True,
                "rank": float(entry.decision_rank or entry.candidate_rank or idx),
                "candidate_rank": entry.candidate_rank,
                "score": float(entry.score_used),
                "score_source": entry.score_source,
                "conviction_score": float(entry.conviction_score),
                "conviction_source": (
                    "core.conviction:score_plus_prediction"
                    if entry.predicted_proba is not None
                    else "core.conviction:score_only"
                ),
                "predicted_proba": float(entry.predicted_proba) if entry.predicted_proba is not None else None,
                "selector_signal_mode": entry.selector_signal_mode,
                "selection_explanation": entry.selection_explanation,
                "selector_earnings_blackout": entry.selector_earnings_blackout,
                "target_weight": float(entry.target_weight),
                "target_notional": float(entry.target_notional),
                "approved_shares": normalize_share_quantity(entry.approved_shares),
                "decision": entry.decision,
                "decision_reason": entry.decision_reason,
                "decision_reason_code": str(entry.decision_reason_code) if entry.decision_reason_code is not None else None,
            }
        )
    return pd.DataFrame(rows, columns=RISK_SIGNAL_COLUMNS)


def build_phase2_risk_result(
    *,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    close_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    risk_config: RiskConfig,
    score_column: str | None = None,
    correlation_lookback_days: int | None = None,
    market_regimes_config: "MarketRegimesConfig | None" = None,
    equity_provider: Callable[[date], float] | None = None,
    macro_provider: object | None = None,
    sentiment_score_provider: Callable[[int], float | None] | None = None,
    earnings_lookup: Callable[[date, int, int], dict[str, date]] | None = None,
) -> RiskBridgeResult:
    """Construit les résultats phase 2 ``risk_execution``.

    Si ``market_regimes_config`` est fourni et activé, un ``MarketRegimeSnapshot``
    est calculé pour chaque ``snapshot_date`` puis appliqué à ``risk_config`` via
    :func:`risk_management.regime_apply.apply_snapshot`. Cela garantit la parité
    avec le live (``run_execution.py``).
    """
    normalized_scores = _prepare_score_columns(scores_df, preferred_score_column=score_column)
    snapshot_dates = sorted({pd.Timestamp(value).date() for value in normalized_scores["trade_date"].dropna().tolist()})
    all_entries: list[PortfolioEntry] = []
    signal_frames: list[pd.DataFrame] = []
    regime_snapshots_dump: dict[date, dict] = {}

    lookback = int(correlation_lookback_days or risk_config.correlation_lookback_days)

    # Diagnostics dédiés régime (Axe D du plan).
    regime_modes_count: dict[str, int] = {}
    entries_blocked_by_regime = 0
    slots_rejected_avoided = 0
    macro_data_quality_count: dict[str, int] = {}
    macro_missing_dates: list[str] = []

    use_regime = (
        market_regimes_config is not None
        and getattr(market_regimes_config, "enabled", False)
    )
    build_snapshot_fn = None
    if use_regime:
        from service.market import build_snapshot as _bs  # local import (parité)
        build_snapshot_fn = _bs

    for snapshot_date in snapshot_dates:
        candidates = _build_candidates(normalized_scores, snapshot_date)
        if not candidates:
            continue
        symbols = [candidate.symbol for candidate in candidates]
        prices = _build_prices(
            close_df=close_df,
            high_df=high_df,
            low_df=low_df,
            snapshot_date=snapshot_date,
            symbols=symbols,
        )
        predictions = _build_predictions(predictions_df, snapshot_date)
        return_matrix = _build_return_matrix(close_df, snapshot_date, symbols, lookback)

        cfg_for_day = risk_config
        snap = None
        if use_regime and build_snapshot_fn is not None:
            equity = (
                equity_provider(snapshot_date)
                if equity_provider is not None
                else risk_config.account_equity
            )
            snap = build_snapshot_fn(
                snapshot_date,
                config=market_regimes_config,
                equity=equity,
                execution_context="backtest",
                macro_provider=macro_provider,
                sentiment_score_provider=sentiment_score_provider,
                earnings_lookup=earnings_lookup,
            )
            regime_modes_count[snap.mode] = regime_modes_count.get(snap.mode, 0) + 1
            macro_quality = str(snap.data_quality.get("macro", "unknown") or "unknown")
            macro_data_quality_count[macro_quality] = macro_data_quality_count.get(macro_quality, 0) + 1
            if macro_quality == "missing":
                macro_missing_dates.append(snapshot_date.isoformat())
            regime_snapshots_dump[snapshot_date] = snap.to_summary_dict()
            cfg_for_day = apply_snapshot(risk_config, snap)
            if not snap.allow_new_entries:
                entries_blocked_by_regime += len(candidates)
                # On ignore les entrées de ce jour (cash_only / close_only / equity_too_low)
                continue
            # Compteur "ordres trop petits évités" : candidats > effective_max_positions
            if cfg_for_day.effective_max_positions < len(candidates):
                slots_rejected_avoided += max(0, len(candidates) - cfg_for_day.effective_max_positions)

        builder = PortfolioBuilder(cfg_for_day)
        entries = builder.build(candidates, prices, predictions=predictions, return_matrix=return_matrix)
        all_entries.extend(entries)
        signal_frames.append(portfolio_entries_to_signals(entries, snapshot_date))

    signals_df = pd.concat(signal_frames, ignore_index=True) if signal_frames else pd.DataFrame(columns=RISK_SIGNAL_COLUMNS)
    accepted_entries = [entry for entry in all_entries if entry.approved_shares > 0]
    diagnostics = {
        "snapshot_dates": len(snapshot_dates),
        "entries_total": len(all_entries),
        "entries_accepted": len(accepted_entries),
        "entries_rejected": sum(1 for entry in all_entries if entry.approved_shares <= 0),
        "signals_generated": len(signals_df),
        "bridge": "risk_management.portfolio_builder",
        "regime_enabled": bool(use_regime),
        "regime_mode_distribution": regime_modes_count,
        "entries_blocked_by_regime": entries_blocked_by_regime,
        "slots_rejected_avoided": slots_rejected_avoided,
        "macro_data_quality_distribution": macro_data_quality_count,
        "macro_missing_dates": macro_missing_dates,
        "macro_missing_dates_count": len(macro_missing_dates),
    }
    return RiskBridgeResult(
        entries=all_entries,
        signals_df=signals_df,
        diagnostics=diagnostics,
        regime_snapshots=regime_snapshots_dump,
    )


def entries_to_dataframe(entries: list[PortfolioEntry]) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame()
    return pd.DataFrame([asdict(entry) for entry in entries])


def save_phase2_risk_artifacts(result: RiskBridgeResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}
    entries_df = entries_to_dataframe(result.entries)
    signals_df = result.signals_df.copy()
    diagnostics_path = output_dir / "phase2_risk_summary.json"
    diagnostics_path.write_text(pd.Series(result.diagnostics).to_json(force_ascii=False, indent=2), encoding="utf-8")
    artifact_paths["phase2_risk_summary_json"] = str(diagnostics_path)
    if not entries_df.empty:
        entries_path = output_dir / "phase2_risk_entries.csv"
        entries_df.to_csv(entries_path, index=False)
        artifact_paths["phase2_risk_entries_csv"] = str(entries_path)
    if not signals_df.empty:
        signals_path = output_dir / "phase2_risk_signals.csv"
        signals_df.to_csv(signals_path, index=False)
        artifact_paths["phase2_risk_signals_csv"] = str(signals_path)
    return artifact_paths

