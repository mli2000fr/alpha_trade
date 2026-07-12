"""Bridge opt-in entre le backtesting et le moteur réel de risk management."""
from __future__ import annotations

import logging
from datetime import datetime, time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING

import pandas as pd

from backtesting.signal_replay import _pick_score_column
from common.quantity_utils import normalize_share_quantity
from risk_management.config import RiskConfig
from risk_management.decision_fingerprint import (
    AuditLogEntry,
    DecisionAuditLog,
    build_decision_fingerprint,
    build_position_fingerprint,
)
from risk_management.models import SelectionScore, PortfolioEntry, PredictionInfo, PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder
from risk_management.regime_apply import apply_snapshot, apply_structural_market_guards
from risk_management.selection_contract import build_candidate_from_prediction, build_rankings

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from service.market import MarketRegimesConfig


RISK_SIGNAL_COLUMNS = (
    "trade_date",
    "symbol",
    "side",
    "selected",
    "rank",
    "selection_rank",
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
)


@dataclass(slots=True)
class RiskBridgeResult:
    entries: list[PortfolioEntry]
    signals_df: pd.DataFrame
    diagnostics: dict[str, object]
    regime_snapshots: dict[date, dict] = field(default_factory=dict)
    decision_audit_logs: dict[date, DecisionAuditLog] = field(default_factory=dict)


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
    # Lorsqu'une colonne de score explicite est demandée, la source résolue
    # prend priorité sur un éventuel score_source préexistant.
    if "score_source" in prepared.columns and preferred_score_column is None:
        prepared["score_source"] = prepared["score_source"].where(prepared["score_source"].notna(), source_series.values)
    else:
        prepared["score_source"] = source_series.values
    return prepared


def _build_selection_inputs(scores_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]:
    day_df = _normalize_trade_dates(scores_df)
    day_df = day_df.loc[day_df["trade_date"] == pd.Timestamp(snapshot_date)]
    if day_df.empty:
        return []
    return _build_selection_inputs_from_day(day_df, snapshot_date)


def _build_selection_inputs_from_day(day_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]:
    """Construit les ``SelectionScore`` depuis un DataFrame déjà filtré sur le jour.

    Parameters
    ----------
    day_df : pd.DataFrame
        DataFrame contenant UNIQUEMENT les lignes du ``snapshot_date``
        (peut avoir déjà subi un ajustement régime via :func:`apply_regime_weights`).
    snapshot_date : date
        Date de snapshot pour le champ ``snapshot_date`` des sélections.
    """
    if day_df.empty:
        return []

    selection_inputs: list[SelectionScore] = []
    for _, row in day_df.iterrows():
        # Sprint 2 — lire le side depuis le DataFrame si présent (Option C short)
        side = str(row.get("side") or "buy").strip().lower()
        if side not in ("buy", "sell"):
            side = "buy"

        selection_inputs.append(
            SelectionScore(
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
                selection_rank=int(row.get("selection_rank")) if row.get("selection_rank") is not None and not pd.isna(row.get("selection_rank")) else None,
                selector_signal_mode=str(row.get("selector_signal_mode")) if row.get("selector_signal_mode") is not None and not pd.isna(row.get("selector_signal_mode")) else None,
                selection_explanation=str(row.get("selection_explanation")) if row.get("selection_explanation") is not None and not pd.isna(row.get("selection_explanation")) else None,
                selector_earnings_blackout=int(row.get("selector_earnings_blackout")) if row.get("selector_earnings_blackout") is not None and not pd.isna(row.get("selector_earnings_blackout")) else (
                    int(row.get("earnings_blackout")) if row.get("earnings_blackout") is not None and not pd.isna(row.get("earnings_blackout")) else None
                ),
                side=side,
            )
        )
    return selection_inputs


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
    volume_df: pd.DataFrame | None = None,
    snapshot_date: date,
    symbols: Iterable[str],
) -> dict[str, PriceInfo]:
    prices: dict[str, PriceInfo] = {}
    snapshot_ts = pd.Timestamp(snapshot_date)
    close_hist = close_df.loc[close_df.index <= snapshot_ts]
    high_hist = high_df.loc[high_df.index <= snapshot_ts]
    low_hist = low_df.loc[low_df.index <= snapshot_ts]
    vol_hist = None if volume_df is None else volume_df.loc[volume_df.index <= snapshot_ts]
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
        # ADV 20j : moyenne(close × volume) sur la fenêtre glissante
        adv_usd = None
        if vol_hist is not None and symbol in vol_hist.columns:
            symbol_vol = vol_hist[symbol].dropna()
            # Aligner close et volume sur les mêmes index
            common_idx = symbol_close.index.intersection(symbol_vol.index)
            if len(common_idx) >= 20:
                aligned_close = symbol_close.loc[common_idx]
                aligned_vol = symbol_vol.loc[common_idx]
                dollar_vol = aligned_close * aligned_vol
                adv_usd = float(dollar_vol.tail(20).mean())

        prices[symbol] = PriceInfo(
            symbol=symbol,
            last_close=last_close,
            atr_20=atr_20,
            price_asof_date=snapshot_date,
            atr_asof_date=snapshot_date if atr_20 is not None else None,
            adv_usd=adv_usd,
        )
    return prices


def _build_predictions(predictions_df: pd.DataFrame, snapshot_date: date) -> dict[str, PredictionInfo]:
    if predictions_df.empty:
        return {}
    normalized = _normalize_trade_dates(predictions_df)
    day_df = normalized.loc[normalized["trade_date"] == pd.Timestamp(snapshot_date)]
    result: dict[str, PredictionInfo] = {}
    for _, row in day_df.iterrows():
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        pred_class = int(row.get("predicted_class", 0) or 0)
        result[symbol] = PredictionInfo(
            symbol=symbol,
            predicted_proba=float(row.get("predicted_proba", 0.0) or 0.0),
            predicted_class=pred_class,
            run_id=str(row.get("run_id") or "backtest"),
            prediction_date=snapshot_date,
            # ML Sprint 3 — colonnes ternaires optionnelles
            predicted_side=str(row.get("predicted_side")) if row.get("predicted_side") and pd.notna(row.get("predicted_side")) else None,
            proba_long=float(row.get("proba_long")) if row.get("proba_long") and pd.notna(row.get("proba_long")) else None,
            proba_flat=float(row.get("proba_flat")) if row.get("proba_flat") and pd.notna(row.get("proba_flat")) else None,
            proba_short=float(row.get("proba_short")) if row.get("proba_short") and pd.notna(row.get("proba_short")) else None,
        )
    return result


def _build_ml_selection_inputs_from_day(
    day_scores: pd.DataFrame,
    predictions: dict[str, PredictionInfo],
    snapshot_date: date,
) -> list[SelectionScore]:
    """Adapt complete ternary ML predictions for the legacy builder boundary.

    Nominal score, side and rank are derived solely from the ML prediction.
    Selector columns are retained only as informational veto context.
    """
    candidates_by_symbol = {}
    rows_by_symbol: dict[str, pd.Series] = {}
    for _, row in day_scores.iterrows():
        symbol = str(row.get("symbol") or "").strip().upper()
        prediction = predictions.get(symbol)
        if not symbol or prediction is None:
            continue
        if (
            prediction.proba_long is None
            or prediction.proba_flat is None
            or prediction.proba_short is None
            or not prediction.run_id
        ):
            LOGGER.warning("ML_FIRST_REJECT missing_ml_prediction symbol=%s date=%s", symbol, snapshot_date)
            continue
        try:
            candidate = build_candidate_from_prediction(
                symbol=symbol,
                trade_date=snapshot_date,
                predicted_side=prediction.predicted_side,
                proba_long=prediction.proba_long,
                proba_flat=prediction.proba_flat,
                proba_short=prediction.proba_short,
                proba=prediction.predicted_proba,
                model_run_id=prediction.run_id,
            )
        except (TypeError, ValueError) as exc:
            LOGGER.warning("ML_FIRST_REJECT invalid_ml_prediction symbol=%s error=%s", symbol, exc)
            continue
        if candidate.is_actionable():
            candidates_by_symbol[symbol] = candidate
            rows_by_symbol[symbol] = row

    long_ranked, short_ranked = build_rankings(list(candidates_by_symbol.values()))
    inputs: list[SelectionScore] = []
    for candidate in [*long_ranked, *short_ranked]:
        row = rows_by_symbol[candidate.symbol]
        if bool(row.get("selector_earnings_blackout") or row.get("earnings_blackout")):
            LOGGER.info("ML_FIRST_VETO earnings_blackout symbol=%s", candidate.symbol)
            continue
        # ── Section 17 Point 5.2 : adapter canonique MLRankedCandidate → SelectionScore
        from risk_management.selection_contract import to_selection_score as _to_ss

        inputs.append(
            _to_ss(
                candidate,
                sector=str(row.get("sector") or "Unknown"),
                snapshot_date=snapshot_date,
                selector_signal_mode=str(row.get("selector_signal_mode") or "ml_first"),
                selection_explanation=str(row.get("selection_explanation") or "ML-ranked candidate"),
            )
        )
    return inputs


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


def _resolve_regime_snapshot_dates(close_df: pd.DataFrame, execution_dates: list[date]) -> list[date]:
    if not execution_dates:
        return []
    if close_df.empty or close_df.index.empty:
        return execution_dates
    market_dates = sorted({pd.Timestamp(value).date() for value in close_df.index.tolist()})
    if not market_dates:
        return execution_dates
    start_date = min(execution_dates)
    end_date = max(execution_dates)
    aligned_dates = [market_date for market_date in market_dates if start_date <= market_date <= end_date]
    return aligned_dates or execution_dates


def portfolio_entries_to_signals(entries: list[PortfolioEntry], snapshot_date: date) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, entry in enumerate(entries, start=1):
        if entry.approved_shares <= 0:
            continue
        rows.append(
            {
                "trade_date": pd.Timestamp(snapshot_date),
                "symbol": entry.symbol,
                "side": entry.side,
                "selected": True,
                "rank": float(entry.decision_rank or entry.selection_rank or idx),
                "selection_rank": entry.selection_rank,
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
    return pd.DataFrame(rows, columns=list(RISK_SIGNAL_COLUMNS))


def _concat_signal_frames(signal_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    non_empty_signal_frames = [frame for frame in signal_frames if not frame.empty]
    if not non_empty_signal_frames:
        return pd.DataFrame(columns=list(RISK_SIGNAL_COLUMNS))
    return pd.concat(non_empty_signal_frames, ignore_index=True).reindex(columns=RISK_SIGNAL_COLUMNS)


def build_phase2_risk_result(
    *,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    close_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    volume_df: pd.DataFrame | None = None,
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

    Si ``market_regimes_config`` est fourni, les garde-fous structurels petit
    compte (``enforce_min_notional`` + cap de slots) sont appliqués même quand
    ``enabled=false``. Quand la couche régime est activée, un
    ``MarketRegimeSnapshot`` est ensuite calculé pour chaque ``snapshot_date``
    puis appliqué via :func:`risk_management.regime_apply.apply_snapshot`.
    Cela garantit la parité avec le live (``run_execution.py``) tout en
    découplant l'ablation macro des garde-fous structurels.
    """
    normalized_scores = _prepare_score_columns(scores_df, preferred_score_column=score_column)
    execution_dates = sorted({pd.Timestamp(value).date() for value in normalized_scores["trade_date"].dropna().tolist()})
    all_entries: list[PortfolioEntry] = []
    signal_frames: list[pd.DataFrame] = []
    regime_snapshots_dump: dict[date, dict] = {}
    decision_audit_logs: dict[date, DecisionAuditLog] = {}

    lookback = int(correlation_lookback_days or risk_config.correlation_lookback_days)

    # Diagnostics dédiés régime (Axe D du plan).
    regime_modes_count: dict[str, int] = {}
    entries_blocked_by_regime = 0
    slots_rejected_avoided = 0
    macro_data_quality_count: dict[str, int] = {}
    macro_missing_dates: list[str] = []

    structural_cfg = apply_structural_market_guards(
        risk_config,
        market_regimes_config=market_regimes_config,
        equity=risk_config.account_equity,
    )
    structural_guard_applied = structural_cfg is not risk_config

    use_regime = (
        market_regimes_config is not None
        and getattr(market_regimes_config, "enabled", False)
    )
    build_snapshot_fn = None
    if use_regime:
        from service.market import build_snapshot as _bs  # local import (parité)
        build_snapshot_fn = _bs

    # ── Rotation factor : tracker de performance momentum ──────────────
    from selector.regime_scoring import MomentumRotationState
    rotation_state = MomentumRotationState(lookback_weeks=4, threshold=-0.03)
    prev_equity: float | None = None

    snapshot_dates = _resolve_regime_snapshot_dates(close_df, execution_dates) if use_regime else execution_dates
    previous_regime_state = None
    for snapshot_date in snapshot_dates:
        # ── 0. Régime snapshot (doit être résolu avant les sélections pour le
        #     scoring directionnel) ──────────────────────────────────────────
        cfg_for_day = structural_cfg
        snap = None
        if use_regime and build_snapshot_fn is not None:
            equity = (
                equity_provider(snapshot_date)
                if equity_provider is not None
                else structural_cfg.account_equity
            )
            snap = build_snapshot_fn(
                snapshot_date,
                config=market_regimes_config,
                equity=equity,
                execution_context="backtest",
                macro_provider=macro_provider,
                sentiment_score_provider=sentiment_score_provider,
                earnings_lookup=earnings_lookup,
                previous_state=previous_regime_state,
            )
            previous_regime_state = getattr(snap, "next_state", None)
            regime_modes_count[snap.mode] = regime_modes_count.get(snap.mode, 0) + 1
            macro_quality = str(snap.data_quality.get("macro", "unknown") or "unknown")
            macro_data_quality_count[macro_quality] = macro_data_quality_count.get(macro_quality, 0) + 1
            if macro_quality == "missing":
                macro_missing_dates.append(snapshot_date.isoformat())
            regime_snapshots_dump[snapshot_date] = snap.to_summary_dict()
            cfg_for_day = apply_snapshot(structural_cfg, snap)
            # ── Recovery gate : si SPY repasse au-dessus de sa SMA50, le marché
            #     rebondit → sortir du mode défensif → réautoriser les entrées.
            if (
                getattr(snap, "mode", "normal") == "capital_preservation"
                and bool(getattr(risk_config, "short_require_bearish_benchmark", False))
                and "SPY" in close_df.columns
            ):
                # Filtrer jusqu'à la date du snapshot pour éviter le look-ahead
                snap_ts = pd.Timestamp(snapshot_date)
                spy_hist = close_df["SPY"].loc[close_df.index <= snap_ts].dropna()
                if len(spy_hist) >= 50:
                    spy_sma50 = float(spy_hist.iloc[-50:].mean())
                    spy_close = float(spy_hist.iloc[-1])
                    if spy_close > spy_sma50:
                        # Le marché rebondit → on réautorise les entrées (longs et shorts)
                        object.__setattr__(snap, "allowed_long_entries", True)
                        object.__setattr__(snap, "allow_new_entries", True)
                        LOGGER.info(
                            "Recovery gate: longs re-allowed — SPY close=%.2f > SMA50=%.2f (date=%s)",
                            spy_close, spy_sma50, snapshot_date,
                        )
            if not snap.allow_new_entries:
                entries_blocked_by_regime += len(_build_selection_inputs(normalized_scores, snapshot_date))
                continue
            # Compteur "ordres trop petits évités" : sélections > effective_max_positions
            day_selection_inputs_pre = _build_selection_inputs(normalized_scores, snapshot_date)
            if cfg_for_day.effective_max_positions < len(day_selection_inputs_pre):
                slots_rejected_avoided += max(0, len(day_selection_inputs_pre) - cfg_for_day.effective_max_positions)

        # ── 1. Vetos selector/régime postérieurs au ranking ML ─────────
        day_scores = normalized_scores.loc[
            normalized_scores["trade_date"] == pd.Timestamp(snapshot_date)
        ]
        if snap is not None and not day_scores.empty:
            from selector.regime_filters import apply_full_regime_to_candidates
            # ── P0 FIX (2026-06-25) : earnings_shield / buyback_blackout / yield_filter ──
            day_scores = apply_full_regime_to_candidates(
                day_scores.copy(),
                snap,
                score_column="final_score",
                sector_column="sector",
                symbol_column="symbol",
            )

        # ── 1bis. Alimenter le rotation factor avec le retour quotidien ──
        if equity_provider is not None and snap is not None:
            try:
                current_equity = float(equity_provider(snapshot_date))
                if prev_equity is not None and prev_equity > 0:
                    daily_return = (current_equity / prev_equity) - 1.0
                    rotation_state.record(daily_return)
                prev_equity = current_equity
            except Exception:
                pass

        predictions = _build_predictions(predictions_df, snapshot_date)
        selection_inputs = _build_ml_selection_inputs_from_day(day_scores, predictions, snapshot_date)
        n_sells = sum(1 for selection in selection_inputs if selection.side == "sell")
        if n_sells > 0:
            LOGGER.info(
                "Option C selections: date=%s total=%d shorts=%d symbols=%s",
                snapshot_date,
                len(selection_inputs),
                n_sells,
                [selection.symbol for selection in selection_inputs if selection.side == "sell"][:5],
            )
        symbols = [selection.symbol for selection in selection_inputs]
        prices: dict[str, PriceInfo] = {}
        return_matrix = None
        if selection_inputs:
            prices = _build_prices(
                close_df=close_df,
                high_df=high_df,
                low_df=low_df,
                volume_df=volume_df,
                snapshot_date=snapshot_date,
                symbols=symbols,
            )
            return_matrix = _build_return_matrix(close_df, snapshot_date, symbols, lookback)

        if not selection_inputs:
            continue

        # ── Factor risk model (Priorité 3) : construire les exposures ──
        factor_exposures: dict[str, object] = {}
        factor_covariance: object | None = None
        if risk_config.enable_factor_model:
            try:
                from risk_management.factor_model import (
                    build_exposures_from_score_frame,
                    build_factor_returns,
                    estimate_factor_covariance,
                )
                factor_exposures_raw = build_exposures_from_score_frame(
                    day_scores, snapshot_date,
                )
                factor_exposures = {
                    sym: exp for sym, exp in factor_exposures_raw.items()
                }
                # Construire les rendements factoriels et estimer la covariance
                factor_returns = build_factor_returns(
                    symbols=list(set(symbols) | set(factor_exposures.keys())),
                    close_prices=close_df,
                    benchmark_prices=None,  # SPY sera cherché dans close_df
                    factor_exposures_map=factor_exposures_raw,
                )
                if factor_returns is not None:
                    factor_covariance = estimate_factor_covariance(
                        factor_returns,
                        lookback_days=risk_config.factor_lookback_days,
                        ewma_half_life=risk_config.factor_ewma_half_life,
                        estimation_date=snapshot_date,
                        stock_returns=return_matrix if return_matrix is not None else None,
                    )
                if factor_covariance is not None:
                    LOGGER.debug(
                        "Factor model: date=%s exposures=%d factors=%s",
                        snapshot_date,
                        len(factor_exposures),
                        getattr(factor_covariance, "factor_names", []),
                    )
            except Exception:
                LOGGER.warning(
                    "Factor model construction failed for %s",
                    snapshot_date,
                    exc_info=True,
                )

        builder = PortfolioBuilder(
            cfg_for_day,
            rotation_state=rotation_state,
            factor_exposures=factor_exposures if factor_exposures else None,
            factor_covariance=factor_covariance,
        )
        entries = builder.build(selection_inputs, prices, predictions=predictions, return_matrix=return_matrix)
        model_run_ids = sorted({prediction.run_id for prediction in predictions.values() if prediction.run_id})
        model_run_id = "|".join(model_run_ids)
        regime_mode = str(getattr(snap, "mode", "normal") or "normal")
        universe_fingerprint = ",".join(sorted(candidate.symbol for candidate in selection_inputs))
        decision_fingerprint = build_decision_fingerprint(
            snapshot_date,
            f"backtest-{snapshot_date.isoformat()}",
            config_fingerprint=cfg_for_day.fingerprint,
            model_run_id=model_run_id,
            universe_fingerprint=universe_fingerprint,
            regime_mode=regime_mode,
            candidate_count=len(selection_inputs),
        )
        audit_log = DecisionAuditLog(
            trade_date=snapshot_date,
            run_id=decision_fingerprint.run_id,
            decision_fingerprint=decision_fingerprint,
        )
        decision_timestamp = datetime.combine(snapshot_date, time.min)
        for entry in entries:
            position_fingerprint = build_position_fingerprint(
                entry.symbol,
                "short" if entry.side == "sell" else "long",
                decision_fingerprint.fingerprint,
                predicted_proba=float(entry.predicted_proba or 0.0),
                p_side=float(entry.predicted_proba or 0.0),
                price=entry.entry_price,
                atr=entry.atr_20,
                config_fingerprint=cfg_for_day.fingerprint,
            )
            audit_log.add_entry(AuditLogEntry(
                trade_date=snapshot_date,
                timestamp=decision_timestamp,
                run_id=decision_fingerprint.run_id,
                symbol=entry.symbol,
                side="short" if entry.side == "sell" else "long",
                decision=str(entry.decision),
                reason=entry.decision_reason,
                proposed_shares=entry.proposed_shares,
                approved_shares=entry.approved_shares,
                entry_price=entry.entry_price,
                stop_price=entry.stop_price_initial,
                fingerprint=position_fingerprint.fingerprint,
                predicted_proba=entry.predicted_proba,
                atr=entry.atr_20,
                config_fingerprint=cfg_for_day.fingerprint,
                model_run_id=model_run_id,
            ))
        decision_audit_logs[snapshot_date] = audit_log
        n_entry_sells = sum(1 for e in entries if getattr(e, "side", "buy") == "sell")
        n_accepted_sells = sum(1 for e in entries if getattr(e, "side", "buy") == "sell" and e.approved_shares > 0)
        if n_sells > 0:
            LOGGER.info(
                "Option C entries: date=%s total=%d sells=%d accepted_sells=%d decisions=%s",
                snapshot_date,
                len(entries),
                n_entry_sells,
                n_accepted_sells,
                [(e.symbol, e.side, e.decision, e.decision_reason) for e in entries if getattr(e, "side", "buy") == "sell"],
            )
        all_entries.extend(entries)
        signal_frames.append(portfolio_entries_to_signals(entries, snapshot_date))

    signals_df = _concat_signal_frames(signal_frames)
    accepted_entries = [entry for entry in all_entries if entry.approved_shares > 0]
    diagnostics = {
        "snapshot_dates": len(snapshot_dates),
        "entries_total": len(all_entries),
        "entries_accepted": len(accepted_entries),
        "entries_rejected": sum(1 for entry in all_entries if entry.approved_shares <= 0),
        "signals_generated": len(signals_df),
        "bridge": "risk_management.portfolio_builder",
        "regime_enabled": bool(use_regime),
        "structural_guard_applied": structural_guard_applied,
        "structural_guard_min_notional": (
            float(structural_cfg.effective_min_notional)
            if structural_guard_applied
            else None
        ),
        "structural_guard_effective_max_positions": (
            int(structural_cfg.effective_max_positions)
            if structural_guard_applied
            else None
        ),
        "regime_mode_distribution": regime_modes_count,
        "entries_blocked_by_regime": entries_blocked_by_regime,
        "slots_rejected_avoided": slots_rejected_avoided,
        "macro_data_quality_distribution": macro_data_quality_count,
        "macro_missing_dates": macro_missing_dates,
        "macro_missing_dates_count": len(macro_missing_dates),
        "rotation_factor_enabled": True,
        "rotation_triggered": rotation_state.should_rotate(),
        "rotation_cumulative_return": rotation_state.cumulative_return(),
        "rotation_data_points": len(rotation_state._daily_returns),
        "factor_model_enabled": bool(risk_config.enable_factor_model),
        "factor_correlation_filter": bool(risk_config.use_factor_correlation_filter),
        "decision_audit_logs": len(decision_audit_logs),
    }
    return RiskBridgeResult(
        entries=all_entries,
        signals_df=signals_df,
        diagnostics=diagnostics,
        regime_snapshots=regime_snapshots_dump,
        decision_audit_logs=decision_audit_logs,
    )


def entries_to_dataframe(entries: list[PortfolioEntry]) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame()
    return pd.DataFrame([asdict(entry) for entry in entries])


def _regime_snapshots_to_dataframe(regime_snapshots: dict[date, dict]) -> pd.DataFrame:
    if not regime_snapshots:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for snapshot_date in sorted(regime_snapshots):
        payload = regime_snapshots.get(snapshot_date) or {}
        mode_why = payload.get("mode_why") if isinstance(payload.get("mode_why"), dict) else {}
        data_quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
        rows.append(
            {
                "trade_date": snapshot_date.isoformat(),
                "market_regime": payload.get("mode"),
                "raw_mode": payload.get("raw_mode"),
                "transition_action": payload.get("transition_action"),
                "allow_new_entries": payload.get("allow_new_entries"),
                "risk_multiplier": payload.get("risk_multiplier"),
                "effective_max_positions": payload.get("effective_max_positions"),
                "soft_signal_count": payload.get("soft_signal_count"),
                "hard_triggered": payload.get("hard_triggered"),
                "macro_data_quality": data_quality.get("macro"),
                "summary": mode_why.get("summary"),
                "primary_source": mode_why.get("primary_source"),
            }
        )
    return pd.DataFrame(rows)


def save_phase2_risk_artifacts(result: RiskBridgeResult, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}
    entries_df = entries_to_dataframe(result.entries)
    signals_df = result.signals_df.copy()
    diagnostics_path = output_dir / "phase2_risk_summary.json"
    diagnostics_path.write_text(pd.Series(result.diagnostics).to_json(force_ascii=False, indent=2), encoding="utf-8")
    artifact_paths["phase2_risk_summary_json"] = str(diagnostics_path)
    regimes_df = _regime_snapshots_to_dataframe(result.regime_snapshots)
    if not regimes_df.empty:
        regimes_path = output_dir / "market_regimes.csv"
        regimes_df.to_csv(regimes_path, index=False)
        artifact_paths["market_regimes"] = str(regimes_path)
    if not entries_df.empty:
        entries_path = output_dir / "phase2_risk_entries.csv"
        entries_df.to_csv(entries_path, index=False)
        artifact_paths["phase2_risk_entries_csv"] = str(entries_path)
    if result.decision_audit_logs:
        audit_logs_path = output_dir / "phase2_risk_decision_audit.json"
        audit_logs_path.write_text(
            pd.Series({
                trade_date.isoformat(): audit_log.to_dict()
                for trade_date, audit_log in result.decision_audit_logs.items()
            }).to_json(force_ascii=False, indent=2),
            encoding="utf-8",
        )
        artifact_paths["phase2_risk_decision_audit_json"] = str(audit_logs_path)
    if not signals_df.empty:
        signals_path = output_dir / "phase2_risk_signals.csv"
        signals_df.to_csv(signals_path, index=False)
        artifact_paths["phase2_risk_signals_csv"] = str(signals_path)
    return artifact_paths

