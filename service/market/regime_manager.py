"""Orchestrateur principal — produit un ``MarketRegimeSnapshot`` par cycle.

Toutes les sources externes (macro, sentiment, earnings) sont injectables ;
le module n'a **aucune dépendance dure** sur la base de données ou les
providers. Cela garantit :

* parité live ↔ backtest (mêmes règles, providers différents) ;
* tests déterministes ;
* fallback neutre quand une source manque.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Literal, cast

from service.market.calendar_patterns import (
    CalendarPatternHit,
    evaluate_calendar_patterns,
)
from service.market.config import MarketRegimesConfig
from service.market.earnings_shield import (
    EarningsLookup,
    compute_earnings_shield,
)
from service.market.macro_signals import (
    MacroDataProvider,
    VixTermStructure,
    evaluate_vix,
    evaluate_vxn,
    evaluate_vix_term_structure,
    evaluate_yield_10y,
)
from service.market.models import MarketRegimeSnapshot, MarketRegimeState, RegimeMode, neutral_snapshot
from service.market.sentiment_regime import evaluate_sentiment_regime

LOGGER = logging.getLogger(__name__)

ExecutionContext = Literal["live", "backtest"]


class MacroDataUnavailableError(RuntimeError):
    """Levée quand un snapshot de régime exige des données macro indisponibles."""


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    snapshot: MarketRegimeSnapshot
    expires_at: float


_SNAPSHOT_CACHE: dict[tuple, _CacheEntry] = {}
_SOFT_SIGNAL_SOURCES = frozenset({"vix_high", "vix_curve_inverted", "yield_spike_10y", "sentiment_warning"})
_HARD_SIGNAL_SOURCES = frozenset({"yield_spike_10y_hard", "sentiment_critical"})


def _mode_strength(mode: RegimeMode) -> int:
    """Plus le rang est élevé, plus le mode est restrictif."""
    return {"normal": 0, "capital_preservation": 1, "close_only": 2, "cash_only": 3}[mode]


def _escalate(current: RegimeMode, candidate: str) -> RegimeMode:
    """Retient le mode le plus restrictif des deux."""
    if candidate not in ("normal", "capital_preservation", "close_only", "cash_only"):
        return current
    cand: RegimeMode = candidate  # type: ignore[assignment]
    return cand if _mode_strength(cand) > _mode_strength(current) else current


def _push_trace(
    trace: list[dict[str, Any]],
    *,
    source: str,
    label: str,
    triggered: bool,
    severity: str,
    message: str,
    resulting_mode: str = "normal",
    value: Any = None,
    threshold: Any = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "source": source,
        "label": label,
        "triggered": bool(triggered),
        "severity": severity,
        "message": message,
        "resulting_mode": resulting_mode,
    }
    if value is not None:
        payload["value"] = value
    if threshold is not None:
        payload["threshold"] = threshold
    if details:
        payload.update(details)
    trace.append(payload)


def _build_mode_why(mode: RegimeMode, reasons: list[str], trace: list[dict[str, Any]]) -> dict[str, Any]:
    triggered = [item for item in trace if item.get("triggered")]
    primary: dict[str, Any] | None = None
    for item in triggered:
        item_mode = str(item.get("resulting_mode") or "normal")
        if primary is None:
            primary = item
            continue
        primary_mode = str(primary.get("resulting_mode") or "normal")
        if _mode_strength(cast(RegimeMode, item_mode)) > _mode_strength(cast(RegimeMode, primary_mode)):
            primary = item

    if primary is not None:
        summary = str(primary.get("message") or f"Source déclenchante : {primary.get('label')}")
    elif mode == "normal":
        summary = "Aucun déclencheur défensif actif : le mode reste normal."
    elif reasons:
        summary = f"Mode {mode} activé par : {', '.join(reasons)}"
    else:
        summary = f"Mode {mode} actif sans raison structurée disponible."

    return {
        "final_mode": mode,
        "summary": summary,
        "primary_source": primary.get("source") if primary else None,
        "primary_label": primary.get("label") if primary else None,
        "triggered_sources": [str(item.get("source")) for item in triggered],
        "triggered_count": len(triggered),
    }


def _required_macro_data_quality_keys(config: MarketRegimesConfig) -> tuple[str, ...]:
    keys: list[str] = []
    if config.vix.enabled:
        keys.append("vix")
    if config.vxn.enabled:
        keys.append("vxn")
    if config.vix3m.enabled:
        keys.append("vix3m")
    if config.move.enabled:
        keys.append("move")
    if config.rvx.enabled:
        keys.append("rvx")
    if config.yields.enabled:
        keys.append("yield_10y")
    return tuple(keys)


def _resolve_missing_macro_data_quality(
    config: MarketRegimesConfig,
    data_quality: dict[str, str],
) -> dict[str, str]:
    return {
        key: str(data_quality.get(key, "missing"))
        for key in _required_macro_data_quality_keys(config)
        if str(data_quality.get(key, "missing")) != "ok"
    }


def _tighten_numeric_limit(current: int | float | None, candidate: int | float | None) -> int | float | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)


def _state_cache_key(previous_state: MarketRegimeState | None) -> tuple[Any, ...]:
    if previous_state is None:
        return (None,)
    return (
        previous_state.trade_date.toordinal(),
        previous_state.current_mode,
        previous_state.previous_mode,
        previous_state.entered_at.toordinal() if previous_state.entered_at else None,
        previous_state.last_transition_at.toordinal() if previous_state.last_transition_at else None,
        previous_state.last_hard_trigger_at.toordinal() if previous_state.last_hard_trigger_at else None,
        previous_state.soft_entry_streak,
        previous_state.soft_exit_streak,
        previous_state.hard_calm_streak,
        previous_state.days_in_current_mode,
        previous_state.release_remaining_days,
    )


def _count_triggered_sources(trace: list[dict[str, Any]], sources: frozenset[str]) -> int:
    return sum(1 for item in trace if item.get("triggered") and str(item.get("source")) in sources)


def _transition_without_hysteresis(
    trade_date: date,
    *,
    raw_mode: RegimeMode,
    previous_state: MarketRegimeState | None,
    hard_triggered: bool,
) -> tuple[RegimeMode, MarketRegimeState, str, int]:
    if previous_state is not None and previous_state.trade_date == trade_date:
        return previous_state.current_mode, previous_state, "reuse_same_day_state", previous_state.days_in_current_mode

    if previous_state is None:
        days_in_current_mode = 1
        previous_mode = None
        entered_at = trade_date if raw_mode != "normal" else None
    elif previous_state.current_mode == raw_mode:
        days_in_current_mode = max(1, previous_state.days_in_current_mode + 1)
        previous_mode = previous_state.previous_mode
        entered_at = previous_state.entered_at if raw_mode != "normal" else None
    else:
        days_in_current_mode = 1
        previous_mode = previous_state.current_mode
        entered_at = trade_date if raw_mode != "normal" else None

    next_state = MarketRegimeState(
        trade_date=trade_date,
        current_mode=raw_mode,
        previous_mode=previous_mode,
        entered_at=entered_at,
        last_transition_at=trade_date if previous_state is None or previous_state.current_mode != raw_mode else previous_state.last_transition_at,
        last_hard_trigger_at=trade_date if hard_triggered else (previous_state.last_hard_trigger_at if previous_state else None),
        soft_entry_streak=0,
        soft_exit_streak=0,
        hard_calm_streak=0 if hard_triggered else (previous_state.hard_calm_streak + 1 if previous_state and previous_state.last_hard_trigger_at else 0),
        days_in_current_mode=days_in_current_mode,
        release_remaining_days=previous_state.release_remaining_days if previous_state is not None else 0,
    )
    return raw_mode, next_state, "hysteresis_disabled", days_in_current_mode


def _apply_hysteresis(
    trade_date: date,
    *,
    raw_mode: RegimeMode,
    previous_state: MarketRegimeState | None,
    soft_signal_count: int,
    hard_triggered: bool,
    config: MarketRegimesConfig,
) -> tuple[RegimeMode, MarketRegimeState, str, int]:
    hysteresis_cfg = config.hysteresis
    if not hysteresis_cfg.enabled:
        return _transition_without_hysteresis(
            trade_date,
            raw_mode=raw_mode,
            previous_state=previous_state,
            hard_triggered=hard_triggered,
        )

    if previous_state is not None and previous_state.trade_date == trade_date:
        return previous_state.current_mode, previous_state, "reuse_same_day_state", previous_state.days_in_current_mode

    prev = previous_state or MarketRegimeState(trade_date=trade_date, current_mode="normal")

    if prev.current_mode == "normal":
        if hard_triggered and hysteresis_cfg.hard_trigger_immediate:
            final_mode = cast(RegimeMode, raw_mode if raw_mode != "normal" else "capital_preservation")
            next_state = MarketRegimeState(
                trade_date=trade_date,
                current_mode=final_mode,
                previous_mode=prev.current_mode,
                entered_at=trade_date,
                last_transition_at=trade_date,
                last_hard_trigger_at=trade_date,
                soft_entry_streak=0,
                soft_exit_streak=0,
                hard_calm_streak=0,
                days_in_current_mode=1,
            )
            return final_mode, next_state, "hard_enter", 1

        if soft_signal_count >= hysteresis_cfg.enter_soft_signals_required:
            entry_streak = prev.soft_entry_streak + 1
            if entry_streak >= hysteresis_cfg.enter_confirm_days:
                final_mode = cast(RegimeMode, raw_mode if raw_mode != "normal" else "capital_preservation")
                next_state = MarketRegimeState(
                    trade_date=trade_date,
                    current_mode=final_mode,
                    previous_mode=prev.current_mode,
                    entered_at=trade_date,
                    last_transition_at=trade_date,
                    last_hard_trigger_at=None,
                    soft_entry_streak=0,
                    soft_exit_streak=0,
                    hard_calm_streak=0,
                    days_in_current_mode=1,
                )
                return final_mode, next_state, "enter_defensive", 1

            next_state = MarketRegimeState(
                trade_date=trade_date,
                current_mode="normal",
                previous_mode=prev.previous_mode,
                entered_at=None,
                last_transition_at=prev.last_transition_at,
                last_hard_trigger_at=prev.last_hard_trigger_at,
                soft_entry_streak=entry_streak,
                soft_exit_streak=0,
                hard_calm_streak=prev.hard_calm_streak,
                days_in_current_mode=max(1, prev.days_in_current_mode + 1),
            )
            return "normal", next_state, "stay_normal_pending_entry", next_state.days_in_current_mode

        next_state = MarketRegimeState(
            trade_date=trade_date,
            current_mode="normal",
            previous_mode=prev.previous_mode,
            entered_at=None,
            last_transition_at=prev.last_transition_at,
            last_hard_trigger_at=prev.last_hard_trigger_at,
            soft_entry_streak=0,
            soft_exit_streak=0,
            hard_calm_streak=prev.hard_calm_streak,
            days_in_current_mode=max(1, prev.days_in_current_mode + 1),
        )
        return "normal", next_state, "stay_normal", next_state.days_in_current_mode

    hold_days = max(1, prev.days_in_current_mode + 1)
    hard_calm_streak = 0 if hard_triggered else (prev.hard_calm_streak + 1 if prev.last_hard_trigger_at else 0)

    if hard_triggered:
        final_mode = _escalate(prev.current_mode, raw_mode)
        transitioned = final_mode != prev.current_mode
        next_state = MarketRegimeState(
            trade_date=trade_date,
            current_mode=final_mode,
            previous_mode=prev.current_mode if transitioned else prev.previous_mode,
            entered_at=prev.entered_at or trade_date,
            last_transition_at=trade_date if transitioned else prev.last_transition_at,
            last_hard_trigger_at=trade_date,
            soft_entry_streak=0,
            soft_exit_streak=0,
            hard_calm_streak=0,
            days_in_current_mode=1 if transitioned else hold_days,
        )
        return final_mode, next_state, "hold_defensive_hard", next_state.days_in_current_mode

    if hold_days < hysteresis_cfg.min_hold_days_defensive:
        next_state = MarketRegimeState(
            trade_date=trade_date,
            current_mode=prev.current_mode,
            previous_mode=prev.previous_mode,
            entered_at=prev.entered_at or trade_date,
            last_transition_at=prev.last_transition_at,
            last_hard_trigger_at=prev.last_hard_trigger_at,
            soft_entry_streak=0,
            soft_exit_streak=0,
            hard_calm_streak=hard_calm_streak,
            days_in_current_mode=hold_days,
        )
        return prev.current_mode, next_state, "hold_defensive_min_hold", hold_days

    exit_streak = prev.soft_exit_streak + 1 if soft_signal_count <= hysteresis_cfg.exit_soft_signals_max else 0
    hard_exit_ready = prev.last_hard_trigger_at is None or hard_calm_streak >= hysteresis_cfg.hard_exit_confirm_days
    if exit_streak >= hysteresis_cfg.exit_confirm_days and hard_exit_ready:
        next_state = MarketRegimeState(
            trade_date=trade_date,
            current_mode="normal",
            previous_mode=prev.current_mode,
            entered_at=None,
            last_transition_at=trade_date,
            last_hard_trigger_at=prev.last_hard_trigger_at,
            soft_entry_streak=0,
            soft_exit_streak=0,
            hard_calm_streak=hard_calm_streak,
            days_in_current_mode=1,
        )
        return "normal", next_state, "exit_defensive", 1

    action = "hold_defensive_pending_exit" if exit_streak > 0 else "hold_defensive"
    next_state = MarketRegimeState(
        trade_date=trade_date,
        current_mode=prev.current_mode,
        previous_mode=prev.previous_mode,
        entered_at=prev.entered_at or trade_date,
        last_transition_at=prev.last_transition_at,
        last_hard_trigger_at=prev.last_hard_trigger_at,
        soft_entry_streak=0,
        soft_exit_streak=exit_streak,
        hard_calm_streak=hard_calm_streak,
        days_in_current_mode=hold_days,
    )
    return prev.current_mode, next_state, action, hold_days


def build_snapshot(
    trade_date: date,
    *,
    config: MarketRegimesConfig,
    equity: float | None = None,
    execution_context: ExecutionContext = "live",
    macro_provider: MacroDataProvider | None = None,
    sentiment_score_provider: Callable[[int], float | None] | None = None,
    earnings_lookup: EarningsLookup | None = None,
    previous_state: MarketRegimeState | None = None,
    use_cache: bool = True,
) -> MarketRegimeSnapshot:
    """Construit (ou retourne du cache) le snapshot de régime marché."""
    if not config.enabled:
        return neutral_snapshot(trade_date)

    cache_key = (
        trade_date.toordinal(),
        execution_context,
        round(equity or 0.0, 2),
        id(config),
        id(macro_provider),
        id(sentiment_score_provider),
        id(earnings_lookup),
        _state_cache_key(previous_state),
    )
    now = time.monotonic()
    if use_cache and config.cache_ttl_seconds > 0:
        entry = _SNAPSHOT_CACHE.get(cache_key)
        if entry is not None and entry.expires_at > now:
            return entry.snapshot

    reasons: list[str] = []
    active_patterns: list[str] = []
    risk_multiplier = 1.0
    sentiment_threshold_addon = 0.0
    screener_expansion_pct = 0.0
    blocked_sectors: list[str] = []
    block_high_beta = False
    high_beta_threshold = 1.2
    allow_new_entries = True
    mode: RegimeMode = "normal"
    effective_max_positions: int | None = None
    max_position_weight: float | None = None
    max_sector_weight: float | None = None
    max_gross_exposure: float | None = None
    soft_risk_multiplier = 1.0
    soft_blocked_sectors: list[str] = []
    soft_block_high_beta = False
    soft_high_beta_threshold: float | None = None
    soft_effective_max_positions: int | None = None
    soft_max_position_weight: float | None = None
    soft_max_sector_weight: float | None = None
    soft_max_gross_exposure: float | None = None
    soft_constraint_sources: list[str] = []
    macro_metrics: dict[str, Any] = {}
    sentiment_payload: dict[str, Any] = {}
    data_quality: dict[str, str] = {}
    decision_trace: list[dict[str, Any]] = []
    vix_high = False
    yield_rel: float | None = None
    yield_spike = False
    sentiment_level = "normal"

    # 1. Calendrier
    hits: list[CalendarPatternHit] = evaluate_calendar_patterns(config, trade_date)
    for hit in hits:
        active_patterns.append(hit.name)
        risk_multiplier *= hit.risk_mult
        sentiment_threshold_addon += hit.sentiment_threshold_addon
        screener_expansion_pct += hit.screener_expansion_pct
        if hit.block_new_entries:
            allow_new_entries = False
            reasons.append(f"calendar_block:{hit.name}")
        _push_trace(
            decision_trace,
            source=f"calendar:{hit.name}",
            label=f"Pattern calendaire `{hit.name}`",
            triggered=True,
            severity="warning" if hit.block_new_entries else "info",
            resulting_mode="normal",
            message=(
                f"Pattern `{hit.name}` actif"
                f" · risk×{hit.risk_mult:.2f}"
                f" · sentiment+={hit.sentiment_threshold_addon:.2f}"
                f" · screener+={hit.screener_expansion_pct:.0%}"
                + (" · blocage nouvelles entrées" if hit.block_new_entries else "")
            ),
            details={
                "pattern": hit.name,
                "risk_multiplier": hit.risk_mult,
                "sentiment_threshold_addon": hit.sentiment_threshold_addon,
                "screener_expansion_pct": hit.screener_expansion_pct,
                "block_new_entries": hit.block_new_entries,
            },
        )

    # 2. Macro VIX
    if config.vix.enabled:
        vix_value, vix_high, curve_inverted, dq = evaluate_vix(
            macro_provider,
            trade_date,
            high_threshold=config.vix.high_threshold,
            inverted_curve_min_spread=config.vix.inverted_curve_min_spread,
            inverted_curve_min_ratio=config.vix.inverted_curve_min_ratio,
        )
        vix_short_value: float | None = None
        if macro_provider is not None:
            try:
                vix_short_value = macro_provider.get_vix_short_term_close(trade_date)
            except Exception:
                vix_short_value = None
        macro_metrics["vix"] = vix_value
        macro_metrics["vix_short"] = vix_short_value
        macro_metrics["vix_curve_inverted"] = curve_inverted
        data_quality.update(dq)
        if vix_high:
            mode = _escalate(mode, "capital_preservation")
            reasons.append(f"vix_high:{vix_value:.1f}")
        _push_trace(
            decision_trace,
            source="vix_high",
            label="VIX élevé",
            triggered=vix_high,
            severity="warning" if vix_high else "info",
            resulting_mode="capital_preservation" if vix_high else "normal",
            value=vix_value,
            threshold=config.vix.high_threshold,
            message=(
                f"VIX élevé ({vix_value:.2f} ≥ {config.vix.high_threshold:.2f}) ⇒ capital_preservation"
                if vix_high and vix_value is not None
                else (
                    f"VIX sous seuil ({vix_value:.2f} < {config.vix.high_threshold:.2f})"
                    if vix_value is not None
                    else "VIX indisponible"
                )
            ),
        )
        if curve_inverted:
            mode = _escalate(mode, config.vix.inverted_curve_mode)
            reasons.append("vix_curve_inverted")
        _push_trace(
            decision_trace,
            source="vix_curve_inverted",
            label="Courbe VIX inversée",
            triggered=curve_inverted,
            severity="warning" if curve_inverted else "info",
            resulting_mode=config.vix.inverted_curve_mode if curve_inverted else "normal",
            value=vix_short_value,
            threshold=vix_value,
            message=(
                f"Courbe VIX inversée ({vix_short_value:.2f} > {vix_value:.2f}, Δ≥{config.vix.inverted_curve_min_spread:.2f}, ratio≥{config.vix.inverted_curve_min_ratio:.3f}) ⇒ {config.vix.inverted_curve_mode}"
                if curve_inverted and vix_short_value is not None and vix_value is not None
                else (
                    f"Courbe VIX non inversée (short={vix_short_value:.2f}, spot={vix_value:.2f}, Δmin={config.vix.inverted_curve_min_spread:.2f}, ratio_min={config.vix.inverted_curve_min_ratio:.3f})"
                    if vix_short_value is not None and vix_value is not None
                    else "Courbe VIX indisponible"
                )
            ),
            details={
                "vix": vix_value,
                "vix_short": vix_short_value,
                "min_spread": config.vix.inverted_curve_min_spread,
                "min_ratio": config.vix.inverted_curve_min_ratio,
            },
        )

    # 2b. Macro VXN (Nasdaq-100 volatility)
    if config.vxn.enabled:
        vxn_value, vxn_high, dq = evaluate_vxn(
            macro_provider,
            trade_date,
            high_threshold=config.vxn.high_threshold,
        )
        macro_metrics["vxn"] = vxn_value
        data_quality.update(dq)
        if vxn_high:
            mode = _escalate(mode, "capital_preservation")
            reasons.append(f"vxn_high:{vxn_value:.1f}")
        _push_trace(
            decision_trace,
            source="vxn_high",
            label="VXN élevé",
            triggered=vxn_high,
            severity="warning" if vxn_high else "info",
            resulting_mode="capital_preservation" if vxn_high else "normal",
            value=vxn_value,
            threshold=config.vxn.high_threshold,
            message=(
                f"VXN élevé ({vxn_value:.2f} ≥ {config.vxn.high_threshold:.2f}) ⇒ capital_preservation"
                if vxn_high and vxn_value is not None
                else (
                    f"VXN sous seuil ({vxn_value:.2f} < {config.vxn.high_threshold:.2f})"
                    if vxn_value is not None
                    else "VXN indisponible"
                )
            ),
        )

    # 2c. Term structure VIX/VIX3M (contango / backwardation)
    if config.vix3m.enabled:
        ts: VixTermStructure = evaluate_vix_term_structure(
            macro_provider,
            trade_date,
            backwardation_threshold=config.vix3m.backwardation_threshold,
        )
        macro_metrics["vix3m"] = ts.vix3m_value
        macro_metrics["vix_term_structure_ratio"] = ts.ratio
        macro_metrics["vix_backwardation"] = ts.backwardation
        data_quality.update(ts.data_quality)
        if ts.backwardation:
            mode = _escalate(mode, "capital_preservation")
            reasons.append("vix_backwardation")
        _push_trace(
            decision_trace,
            source="vix_backwardation",
            label="VIX/VIX3M backwardation",
            triggered=ts.backwardation,
            severity="warning" if ts.backwardation else "info",
            resulting_mode="capital_preservation" if ts.backwardation else "normal",
            value=ts.ratio,
            threshold=config.vix3m.backwardation_threshold,
            message=(
                f"Backwardation VIX/VIX3M (ratio={ts.ratio:.3f} > {config.vix3m.backwardation_threshold}) ⇒ capital_preservation"
                if ts.backwardation and ts.ratio is not None
                else (
                    f"Term structure normale (ratio={ts.ratio:.3f})"
                    if ts.ratio is not None
                    else "Term structure VIX/VIX3M indisponible"
                )
            ),
            details={
                "vix": ts.vix_value,
                "vix3m": ts.vix3m_value,
                "ratio": ts.ratio,
                "backwardation_threshold": config.vix3m.backwardation_threshold,
            },
        )

    # 2d. MOVE (ICE BofA Bond Volatility)
    if config.move.enabled:
        move_value: float | None = None
        if macro_provider is not None:
            try:
                move_value = macro_provider.get_move_close(trade_date)
            except Exception:
                move_value = None
        macro_metrics["move"] = move_value
        move_high = move_value is not None and move_value >= config.move.high_threshold
        data_quality["move"] = (
            "missing" if move_value is None
            else "ok"
        )
        if move_high:
            mode = _escalate(mode, "capital_preservation")
            reasons.append(f"move_high:{move_value:.1f}")
        _push_trace(
            decision_trace,
            source="move_high",
            label="MOVE élevé",
            triggered=move_high,
            severity="warning" if move_high else "info",
            resulting_mode="capital_preservation" if move_high else "normal",
            value=move_value,
            threshold=config.move.high_threshold,
            message=(
                f"MOVE élevé ({move_value:.2f} ≥ {config.move.high_threshold:.2f}) ⇒ capital_preservation"
                if move_high and move_value is not None
                else (
                    f"MOVE sous seuil ({move_value:.2f} < {config.move.high_threshold:.2f})"
                    if move_value is not None
                    else "MOVE indisponible"
                )
            ),
        )

    # 2e. RVX (Russell 2000 Volatility — Small Caps)
    if config.rvx.enabled:
        rvx_value: float | None = None
        if macro_provider is not None:
            try:
                rvx_value = macro_provider.get_rvx_close(trade_date)
            except Exception:
                rvx_value = None
        macro_metrics["rvx"] = rvx_value
        rvx_high = rvx_value is not None and rvx_value >= config.rvx.high_threshold
        data_quality["rvx"] = (
            "missing" if rvx_value is None
            else "ok"
        )
        if rvx_high:
            mode = _escalate(mode, "capital_preservation")
            reasons.append(f"rvx_high:{rvx_value:.1f}")
        _push_trace(
            decision_trace,
            source="rvx_high",
            label="RVX élevé",
            triggered=rvx_high,
            severity="warning" if rvx_high else "info",
            resulting_mode="capital_preservation" if rvx_high else "normal",
            value=rvx_value,
            threshold=config.rvx.high_threshold,
            message=(
                f"RVX élevé ({rvx_value:.2f} ≥ {config.rvx.high_threshold:.2f}) ⇒ capital_preservation"
                if rvx_high and rvx_value is not None
                else (
                    f"RVX sous seuil ({rvx_value:.2f} < {config.rvx.high_threshold:.2f})"
                    if rvx_value is not None
                    else "RVX indisponible"
                )
            ),
        )

    # 3. Macro Yield 10Y
    if config.yields.enabled:
        rel, spike, dq = evaluate_yield_10y(
            macro_provider,
            trade_date,
            lookback_days=config.yields.lookback_days,
            relative_spike_threshold=config.yields.relative_spike_threshold,
        )
        yield_rel = rel
        yield_spike = spike
        yield_history: list[float] | None = None
        if macro_provider is not None:
            try:
                yield_history = macro_provider.get_us10y_history(trade_date, config.yields.lookback_days)
            except Exception:
                yield_history = None
        macro_metrics["yield_10y"] = yield_history[-1] if yield_history else None
        macro_metrics["yield_10y_5d_pct"] = rel
        data_quality.update(dq)
        if spike:
            soft_blocked_sectors.extend(config.yields.block_sectors)
            soft_block_high_beta = soft_block_high_beta or config.yields.block_high_beta
            if config.yields.block_high_beta:
                if soft_high_beta_threshold is None:
                    soft_high_beta_threshold = config.yields.high_beta_threshold
                else:
                    soft_high_beta_threshold = min(soft_high_beta_threshold, config.yields.high_beta_threshold)
            soft_risk_multiplier *= config.yields.risk_mult
            reasons.append(f"yield_spike_10y:{rel:.3%}")
            if "yield_spike_10y" not in soft_constraint_sources:
                soft_constraint_sources.append("yield_spike_10y")
            if config.yields.soft_max_positions is not None:
                soft_effective_max_positions = cast(
                    int | None,
                    _tighten_numeric_limit(soft_effective_max_positions, int(config.yields.soft_max_positions)),
                )
            soft_max_position_weight = cast(
                float | None,
                _tighten_numeric_limit(soft_max_position_weight, config.yields.soft_max_position_weight),
            )
            soft_max_sector_weight = cast(
                float | None,
                _tighten_numeric_limit(soft_max_sector_weight, config.yields.soft_max_sector_weight),
            )
            soft_max_gross_exposure = cast(
                float | None,
                _tighten_numeric_limit(soft_max_gross_exposure, config.yields.soft_max_gross_exposure),
            )
        _push_trace(
            decision_trace,
            source="yield_spike_10y",
            label="Spike taux US 10Y",
            triggered=spike,
            severity="warning" if spike else "info",
            resulting_mode="normal",
            value=rel,
            threshold=config.yields.relative_spike_threshold,
            message=(
                f"Hausse 10Y sur {config.yields.lookback_days}j ({rel:.2%}) ≥ {config.yields.relative_spike_threshold:.2%}"
                if spike and rel is not None
                else (
                    f"10Y sous seuil ({rel:.2%} < {config.yields.relative_spike_threshold:.2%})"
                    if rel is not None
                    else "10Y indisponible"
                )
            ),
            details={
                "blocked_sectors": list(config.yields.block_sectors),
                "block_high_beta": config.yields.block_high_beta,
                "risk_multiplier": config.yields.risk_mult,
                "soft_max_positions": config.yields.soft_max_positions,
                "soft_max_position_weight": config.yields.soft_max_position_weight,
                "soft_max_sector_weight": config.yields.soft_max_sector_weight,
                "soft_max_gross_exposure": config.yields.soft_max_gross_exposure,
            },
        )

    if macro_provider is not None:
        get_source_summary = getattr(macro_provider, "get_macro_source_summary", None)
        if callable(get_source_summary):
            try:
                source_summary = get_source_summary()
            except Exception:
                source_summary = None
            if isinstance(source_summary, dict):
                source_effective = str(source_summary.get("source_effective") or "").strip().lower()
                if source_effective:
                    macro_metrics["source_effective"] = source_effective
                source_by_signal = source_summary.get("source_by_signal")
                if isinstance(source_by_signal, dict) and source_by_signal:
                    macro_metrics["source_by_signal"] = {
                        str(key): str(value)
                        for key, value in source_by_signal.items()
                        if str(key).strip() and str(value).strip()
                    }

    missing_macro_data_quality = _resolve_missing_macro_data_quality(config, data_quality)
    if _required_macro_data_quality_keys(config):
        data_quality["macro"] = "missing" if missing_macro_data_quality else "ok"
    if missing_macro_data_quality:
        macro_metrics["missing_data_quality"] = dict(missing_macro_data_quality)
        missing_macro_message = (
            f"Données macro indisponibles pour {trade_date.isoformat()} : {missing_macro_data_quality}"
        )
        _push_trace(
            decision_trace,
            source="macro_availability",
            label="Disponibilité macro",
            triggered=True,
            severity="warning" if config.allow_neutral_fallback_on_missing_macro_data else "critical",
            resulting_mode=mode,
            message=(
                missing_macro_message + " → fallback neutre, séance marquée data_quality=missing"
                if config.allow_neutral_fallback_on_missing_macro_data
                else missing_macro_message + " → échec strict du snapshot"
            ),
            details={"missing_data_quality": dict(missing_macro_data_quality)},
        )
        if config.allow_neutral_fallback_on_missing_macro_data:
            LOGGER.warning(
                "macro_availability: %s — fallback neutre, séance marquée data_quality=missing (mode tolérant)",
                missing_macro_message,
            )
        else:
            LOGGER.error("macro_availability: %s — échec strict du snapshot", missing_macro_message)
            raise MacroDataUnavailableError(missing_macro_message)

    # 4. Sentiment circuit breaker
    if config.sentiment_circuit_breaker.enabled:
        sent = evaluate_sentiment_regime(
            config.sentiment_circuit_breaker,
            score_provider=sentiment_score_provider,
            execution_context=execution_context,
        )
        reading = getattr(sentiment_score_provider, "last_reading", None)
        macro_metrics["sentiment_score"] = sent.score
        data_quality["sentiment"] = sent.data_quality
        sentiment_level = sent.level
        sentiment_payload = {
            "score": sent.score,
            "level": sent.level,
            "suggested_mode": sent.suggested_mode,
            "suggested_max_positions": sent.suggested_max_positions,
            "data_quality": sent.data_quality,
        }
        if reading is not None and hasattr(reading, "to_dict"):
            sentiment_payload.update(reading.to_dict())
        if sent.suggested_mode != "normal":
            mode = _escalate(mode, sent.suggested_mode)
        if sent.suggested_max_positions is not None:
            if sent.level == "warning":
                soft_effective_max_positions = (
                    sent.suggested_max_positions
                    if soft_effective_max_positions is None
                    else min(soft_effective_max_positions, sent.suggested_max_positions)
                )
                if "sentiment_warning" not in soft_constraint_sources:
                    soft_constraint_sources.append("sentiment_warning")
            else:
                effective_max_positions = (
                    sent.suggested_max_positions
                    if effective_max_positions is None
                    else min(effective_max_positions, sent.suggested_max_positions)
                )
        reasons.extend(sent.reasons)
        sentiment_message = {
            "critical": (
                f"Sentiment critique ({sent.score:.3f} ≤ {config.sentiment_circuit_breaker.critical_threshold:.3f}) ⇒ {sent.suggested_mode}"
                if sent.score is not None else "Sentiment critique"
            ),
            "warning": (
                f"Sentiment warning ({sent.score:.3f} ≤ {config.sentiment_circuit_breaker.warning_threshold:.3f}) ⇒ capital_preservation"
                if sent.score is not None else "Sentiment warning"
            ),
            "normal": (
                f"Sentiment neutre ({sent.score:.3f})"
                if sent.score is not None else f"Sentiment indisponible ({sent.data_quality})"
            ),
        }[sent.level]
        _push_trace(
            decision_trace,
            source=f"sentiment_{sent.level}",
            label="Sentiment agrégé marché",
            triggered=sent.level in {"warning", "critical"},
            severity="critical" if sent.level == "critical" else ("warning" if sent.level == "warning" else "info"),
            resulting_mode=sent.suggested_mode,
            value=sent.score,
            threshold=(
                config.sentiment_circuit_breaker.critical_threshold if sent.level == "critical"
                else config.sentiment_circuit_breaker.warning_threshold
            ),
            message=sentiment_message,
            details={
                "level": sent.level,
                "lookback_days": config.sentiment_circuit_breaker.lookback_days,
                "suggested_max_positions": sent.suggested_max_positions,
                "data_quality": sent.data_quality,
                "source_table": sentiment_payload.get("source"),
                "total_news_count": sentiment_payload.get("total_news_count"),
                "covered_days": sentiment_payload.get("covered_days"),
            },
        )

    # 4.b Choc de taux dur : escalade si le spike est très violent ou si les
    # signaux rates + VIX + sentiment warning s'empilent.
    if config.yields.enabled and yield_spike:
        hard_threshold = config.yields.hard_relative_spike_threshold
        hard_by_magnitude = (
            hard_threshold is not None
            and yield_rel is not None
            and yield_rel >= float(hard_threshold)
        )
        hard_by_stack = (
            (not config.yields.hard_requires_vix_high or vix_high)
            and (
                not config.yields.hard_requires_sentiment_warning
                or sentiment_level in {"warning", "critical"}
            )
        )
        hard_triggered = bool(hard_by_magnitude or hard_by_stack)
        hard_mode = (
            config.yields.hard_mode_backtest
            if execution_context == "backtest"
            else config.yields.hard_mode_live
        )
        if hard_triggered:
            mode = _escalate(mode, hard_mode)
            blocked_sectors.extend(config.yields.hard_block_sectors or config.yields.block_sectors)
            if config.yields.hard_risk_mult is not None:
                risk_multiplier = min(risk_multiplier, float(config.yields.hard_risk_mult))
            if config.yields.hard_max_positions is not None:
                effective_max_positions = cast(
                    int | None,
                    _tighten_numeric_limit(effective_max_positions, int(config.yields.hard_max_positions)),
                )
            max_position_weight = cast(
                float | None,
                _tighten_numeric_limit(max_position_weight, config.yields.hard_max_position_weight),
            )
            max_sector_weight = cast(
                float | None,
                _tighten_numeric_limit(max_sector_weight, config.yields.hard_max_sector_weight),
            )
            max_gross_exposure = cast(
                float | None,
                _tighten_numeric_limit(max_gross_exposure, config.yields.hard_max_gross_exposure),
            )
            reasons.append("yield_spike_10y_hard")
        _push_trace(
            decision_trace,
            source="yield_spike_10y_hard",
            label="Choc taux dur",
            triggered=hard_triggered,
            severity="critical" if hard_triggered else "info",
            resulting_mode=hard_mode if hard_triggered else mode,
            value=yield_rel,
            threshold=hard_threshold,
            message=(
                f"Choc taux dur ⇒ {hard_mode} (yield={yield_rel:.2%}, vix_high={vix_high}, sentiment={sentiment_level})"
                if hard_triggered and yield_rel is not None
                else "Conditions de choc taux dur non réunies"
            ),
            details={
                "hard_by_magnitude": hard_by_magnitude,
                "hard_by_stack": hard_by_stack,
                "hard_requires_vix_high": config.yields.hard_requires_vix_high,
                "hard_requires_sentiment_warning": config.yields.hard_requires_sentiment_warning,
                "hard_mode": hard_mode,
                "hard_block_sectors": list(config.yields.hard_block_sectors or config.yields.block_sectors),
                "hard_risk_mult": config.yields.hard_risk_mult,
                "hard_max_positions": config.yields.hard_max_positions,
                "hard_max_position_weight": config.yields.hard_max_position_weight,
                "hard_max_sector_weight": config.yields.hard_max_sector_weight,
                "hard_max_gross_exposure": config.yields.hard_max_gross_exposure,
                "vix_high": vix_high,
                "sentiment_level": sentiment_level,
            },
        )

    # 5. Earnings shield + buyback blackout
    earnings = compute_earnings_shield(
        trade_date,
        shield_cfg=config.earnings_shield,
        blackout_cfg=config.buyback_blackout,
        lookup=earnings_lookup,
    )

    # 6. Petit capital — allowed_slots = floor(equity / enforce_min_notional)
    enforce_min_notional = float(config.enforce_min_notional)
    allowed_slots: int | None = None
    if equity is not None and equity > 0 and enforce_min_notional > 0:
        allowed_slots_value = max(0, int(math.floor(equity / enforce_min_notional)))
        allowed_slots = allowed_slots_value
        if effective_max_positions is None:
            effective_max_positions = allowed_slots_value
        else:
            current_effective_max_positions = int(effective_max_positions)
            effective_max_positions = min(current_effective_max_positions, allowed_slots_value)
        if allowed_slots_value == 0:
            allow_new_entries = False
            reasons.append("equity_too_low_for_min_notional")
        _push_trace(
            decision_trace,
            source="min_notional_guard",
            label="Garde-fou min notional",
            triggered=allowed_slots_value == 0,
            severity="warning" if allowed_slots_value == 0 else "info",
            resulting_mode="normal",
            value=allowed_slots_value,
            threshold=enforce_min_notional,
            message=(
                f"Equity insuffisante pour le min notional ({equity:.2f}$ / min {enforce_min_notional:.2f}$)"
                if allowed_slots_value == 0
                else f"Capital compatible : {allowed_slots_value} slot(s) autorisé(s)"
            ),
            details={"equity": equity, "enforce_min_notional": enforce_min_notional},
        )

    raw_mode = mode
    soft_signal_count = _count_triggered_sources(decision_trace, _SOFT_SIGNAL_SOURCES)
    hard_triggered = bool(
        raw_mode in ("close_only", "cash_only")
        or _count_triggered_sources(decision_trace, _HARD_SIGNAL_SOURCES) > 0
    )
    mode, next_state, transition_action, state_age_days = _apply_hysteresis(
        trade_date,
        raw_mode=raw_mode,
        previous_state=previous_state,
        soft_signal_count=soft_signal_count,
        hard_triggered=hard_triggered,
        config=config,
    )
    # CP-V2 — fenêtre de release post-CP (point unique, appliqué aux deux chemins d'hystérésis).
    # Sémantique : après le dernier jour de signal CP, on MAINTIENT les restrictions CP pendant
    # `capital_preservation_release_sessions` séances, puis retour aux règles normales. Le compteur
    # est réarmé à chaque nouveau signal CP (raw_mode == capital_preservation).
    _release_sessions = int(getattr(config, "capital_preservation_release_sessions", 0) or 0)
    if _release_sessions > 0 and config.capital_preservation_policy == "cp_v2" and previous_state is not None:
        from dataclasses import replace as _replace_state
        if raw_mode == "capital_preservation":
            next_state = _replace_state(next_state, release_remaining_days=_release_sessions)
        elif mode == "normal" and previous_state.current_mode == "capital_preservation" and previous_state.release_remaining_days > 0:
            _release_left = max(0, previous_state.release_remaining_days - 1)
            mode = "capital_preservation"
            transition_action = "cp_release_hold"
            next_state = _replace_state(
                next_state,
                current_mode="capital_preservation",
                previous_mode=previous_state.previous_mode,
                entered_at=previous_state.entered_at,
                release_remaining_days=_release_left,
            )
        elif mode == "capital_preservation":
            next_state = _replace_state(
                next_state,
                release_remaining_days=max(0, previous_state.release_remaining_days - 1),
            )
    _push_trace(
        decision_trace,
        source="hysteresis",
        label="Machine d'état de régime",
        triggered=transition_action not in {"hysteresis_disabled", "stay_normal", "hold_defensive", "reuse_same_day_state"},
        severity="info",
        resulting_mode=mode,
        message=(
            f"Hystérésis : raw_mode={raw_mode} → final_mode={mode} via `{transition_action}`"
            if config.hysteresis.enabled
            else f"Hystérésis désactivée : mode final `{mode}`"
        ),
        details={
            "raw_mode": raw_mode,
            "final_mode": mode,
            "soft_signal_count": soft_signal_count,
            "hard_triggered": hard_triggered,
            "transition_action": transition_action,
            "previous_mode": previous_state.current_mode if previous_state is not None else None,
        },
    )

    global_soft_gate = (
        config.hysteresis.enabled
        and config.hysteresis.gate_soft_constraints_on_confirmed_entry
    )
    gate_soft_risk_multiplier = global_soft_gate or (
        config.hysteresis.enabled
        and config.hysteresis.gate_soft_risk_multiplier_on_confirmed_entry
    )
    gate_soft_position_limits = global_soft_gate or (
        config.hysteresis.enabled
        and config.hysteresis.gate_soft_position_limits_on_confirmed_entry
    )
    gate_soft_exposure_caps = global_soft_gate or (
        config.hysteresis.enabled
        and config.hysteresis.gate_soft_exposure_caps_on_confirmed_entry
    )
    gate_soft_sector_blocks = global_soft_gate or (
        config.hysteresis.enabled
        and config.hysteresis.gate_soft_sector_blocks_on_confirmed_entry
    )
    soft_entry_confirmed = mode != "normal"
    active_soft_constraint_families: list[str] = []
    deferred_soft_constraint_families: list[str] = []

    risk_multiplier_soft_present = abs(soft_risk_multiplier - 1.0) > 1e-9
    sector_blocks_soft_present = bool(soft_blocked_sectors or soft_block_high_beta)
    position_limits_soft_present = soft_effective_max_positions is not None
    exposure_caps_soft_present = any(
        value is not None
        for value in (soft_max_position_weight, soft_max_sector_weight, soft_max_gross_exposure)
    )

    if risk_multiplier_soft_present:
        if gate_soft_risk_multiplier and not soft_entry_confirmed:
            deferred_soft_constraint_families.append("risk_multiplier")
        else:
            risk_multiplier *= soft_risk_multiplier
            active_soft_constraint_families.append("risk_multiplier")

    if sector_blocks_soft_present:
        if gate_soft_sector_blocks and not soft_entry_confirmed:
            deferred_soft_constraint_families.append("sector_blocks")
        else:
            if soft_blocked_sectors:
                blocked_sectors.extend(soft_blocked_sectors)
            if soft_block_high_beta:
                block_high_beta = True
                if soft_high_beta_threshold is not None:
                    high_beta_threshold = min(high_beta_threshold, soft_high_beta_threshold)
            active_soft_constraint_families.append("sector_blocks")

    if position_limits_soft_present:
        if gate_soft_position_limits and not soft_entry_confirmed:
            deferred_soft_constraint_families.append("position_limits")
        else:
            effective_max_positions = cast(
                int | None,
                _tighten_numeric_limit(effective_max_positions, soft_effective_max_positions),
            )
            active_soft_constraint_families.append("position_limits")

    if exposure_caps_soft_present:
        if gate_soft_exposure_caps and not soft_entry_confirmed:
            deferred_soft_constraint_families.append("exposure_caps")
        else:
            max_position_weight = cast(
                float | None,
                _tighten_numeric_limit(max_position_weight, soft_max_position_weight),
            )
            max_sector_weight = cast(
                float | None,
                _tighten_numeric_limit(max_sector_weight, soft_max_sector_weight),
            )
            max_gross_exposure = cast(
                float | None,
                _tighten_numeric_limit(max_gross_exposure, soft_max_gross_exposure),
            )
            active_soft_constraint_families.append("exposure_caps")

    soft_constraints_active = bool(active_soft_constraint_families)
    deferred_soft_sources = tuple(dict.fromkeys(soft_constraint_sources)) if deferred_soft_constraint_families else ()
    _push_trace(
        decision_trace,
        source="soft_constraints_activation",
        label="Activation des contraintes soft",
        triggered=bool(soft_constraint_sources),
        severity="info" if soft_constraints_active else "warning",
        resulting_mode=mode,
        message=(
            f"Contraintes soft activées ({', '.join(active_soft_constraint_families)})"
            if soft_constraints_active and active_soft_constraint_families
            else (
                f"Contraintes soft différées en attente de confirmation ({', '.join(deferred_soft_constraint_families)})"
                if deferred_soft_constraint_families
                else "Aucune contrainte soft candidate à activer"
            )
        ),
        details={
            "global_soft_gate": global_soft_gate,
            "gate_soft_risk_multiplier": gate_soft_risk_multiplier,
            "gate_soft_position_limits": gate_soft_position_limits,
            "gate_soft_exposure_caps": gate_soft_exposure_caps,
            "gate_soft_sector_blocks": gate_soft_sector_blocks,
            "soft_entry_confirmed": soft_entry_confirmed,
            "soft_constraints_active": soft_constraints_active,
            "soft_sources": list(dict.fromkeys(soft_constraint_sources)),
            "deferred_soft_sources": list(deferred_soft_sources),
            "active_soft_constraint_families": list(active_soft_constraint_families),
            "deferred_soft_constraint_families": list(deferred_soft_constraint_families),
            "transition_action": transition_action,
        },
    )

    # 7. Modes restrictifs : ajustement allow_new_entries
    if mode in ("close_only", "cash_only"):
        allow_new_entries = False
        if mode == "close_only":
            reasons.append("mode_close_only")
        else:
            reasons.append("mode_cash_only")
    elif mode == "capital_preservation" and effective_max_positions is None:
        effective_max_positions = max(1, (effective_max_positions or 1))

    # Sprint 0 short — autorisation directionnelle (cf. plan_v2.md §C7)
    allowed_long_entries = allow_new_entries
    allowed_short_entries = False
    if mode == "capital_preservation":
        # En régime défensif, on autorise le short pour hedger
        allowed_long_entries = False
        allowed_short_entries = True
        reasons.append("short_allowed_capital_preservation")
    elif mode == "normal":
        # En régime normal, seul le long est autorisé (short = feature flag ML futur)
        allowed_short_entries = False

    capital_preservation_max_gross_exposure = config.capital_preservation_max_gross_exposure
    capital_preservation_gross_exposure_triggered = False
    # CP-V2 — budgets par side pendant capital_preservation (activés seulement si policy='cp_v2')
    max_long_exposure: float | None = None
    max_short_exposure: float | None = None
    if mode == "capital_preservation":
        if config.capital_preservation_policy == "cp_v2":
            if config.capital_preservation_max_long_exposure is not None:
                max_long_exposure = float(config.capital_preservation_max_long_exposure)
                reasons.append("cp_v2_max_long_exposure")
            if config.capital_preservation_reserved_short_exposure is not None:
                max_short_exposure = float(config.capital_preservation_reserved_short_exposure)
                reasons.append("cp_v2_reserved_short_exposure")
        if capital_preservation_max_gross_exposure is not None:
            previous_max_gross_exposure = max_gross_exposure
            max_gross_exposure = cast(
                float | None,
                _tighten_numeric_limit(max_gross_exposure, capital_preservation_max_gross_exposure),
            )
            capital_preservation_gross_exposure_triggered = max_gross_exposure != previous_max_gross_exposure
            if capital_preservation_gross_exposure_triggered:
                reasons.append("capital_preservation_max_gross_exposure")
    _push_trace(
        decision_trace,
        source="capital_preservation_gross_exposure",
        label="Cap gross exposure capital_preservation",
        triggered=capital_preservation_gross_exposure_triggered,
        severity="warning" if capital_preservation_gross_exposure_triggered else "info",
        resulting_mode=mode,
        value=max_gross_exposure,
        threshold=capital_preservation_max_gross_exposure,
        message=(
            f"Mode capital_preservation actif ⇒ max_gross_exposure resserrée à {max_gross_exposure:.2f}"
            if capital_preservation_gross_exposure_triggered and max_gross_exposure is not None
            else "Pas de resserrement générique de gross exposure lié à capital_preservation"
        ),
    )

    snap = MarketRegimeSnapshot(
        trade_date=trade_date,
        as_of=datetime.now(timezone.utc),
        mode=mode,
        risk_multiplier=max(0.0, risk_multiplier),
        sentiment_threshold_addon=sentiment_threshold_addon,
        screener_expansion_pct=screener_expansion_pct,
        effective_max_positions=effective_max_positions,
        enforced_min_notional=enforce_min_notional,
        allowed_slots=allowed_slots,
        max_tickers_per_sector=(
            config.sector_limits.max_tickers_per_sector
            if config.sector_limits.enabled else None
        ),
        max_position_weight=max_position_weight,
        max_sector_weight=max_sector_weight,
        max_gross_exposure=max_gross_exposure,
        max_long_exposure=max_long_exposure,
        max_short_exposure=max_short_exposure,
        blocked_sectors=tuple(dict.fromkeys(blocked_sectors)),
        block_high_beta=block_high_beta,
        high_beta_threshold=high_beta_threshold,
        earnings_shielded_symbols=cast(dict[str, Any], dict(earnings.shielded)),
        buyback_blackout_symbols=dict(earnings.buyback_blackout),
        earnings_negative_score_value=earnings.negative_score_value,
        allow_new_entries=allow_new_entries,
        allowed_long_entries=allowed_long_entries,
        allowed_short_entries=allowed_short_entries,
        active_patterns=tuple(active_patterns),
        reasons=tuple(reasons),
        macro=dict(macro_metrics),
        sentiment=dict(sentiment_payload),
        mode_why=_build_mode_why(mode, reasons, decision_trace),
        decision_trace=tuple(dict(item) for item in decision_trace),
        data_quality=dict(data_quality),
        raw_mode=raw_mode,
        previous_mode=previous_state.current_mode if previous_state is not None else None,
        transition_action=transition_action,
        hysteresis_applied=config.hysteresis.enabled,
        soft_signal_count=soft_signal_count,
        soft_constraints_active=soft_constraints_active,
        deferred_soft_sources=deferred_soft_sources,
        active_soft_constraint_families=tuple(active_soft_constraint_families),
        deferred_soft_constraint_families=tuple(deferred_soft_constraint_families),
        hard_triggered=hard_triggered,
        state_age_days=state_age_days,
        next_state=next_state,
    )

    if use_cache and config.cache_ttl_seconds > 0:
        _SNAPSHOT_CACHE[cache_key] = _CacheEntry(snap, now + config.cache_ttl_seconds)

    LOGGER.info(
        "market_regime trade_date=%s mode=%s risk_mult=%.2f effective_max_positions=%s "
        "allow_new_entries=%s patterns=%s reasons=%s",
        trade_date, snap.mode, snap.risk_multiplier, snap.effective_max_positions,
        snap.allow_new_entries, snap.active_patterns, snap.reasons,
    )
    return snap


def reset_cache() -> None:
    """Pour les tests."""
    _SNAPSHOT_CACHE.clear()


__all__ = ["build_snapshot", "reset_cache", "ExecutionContext"]

