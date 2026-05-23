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
    evaluate_vix,
    evaluate_yield_10y,
)
from service.market.models import MarketRegimeSnapshot, RegimeMode, neutral_snapshot
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


def build_snapshot(
    trade_date: date,
    *,
    config: MarketRegimesConfig,
    equity: float | None = None,
    execution_context: ExecutionContext = "live",
    macro_provider: MacroDataProvider | None = None,
    sentiment_score_provider: Callable[[int], float | None] | None = None,
    earnings_lookup: EarningsLookup | None = None,
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
    macro_metrics: dict[str, Any] = {}
    sentiment_payload: dict[str, Any] = {}
    data_quality: dict[str, str] = {}
    decision_trace: list[dict[str, Any]] = []

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
            macro_provider, trade_date, high_threshold=config.vix.high_threshold
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
                f"Courbe VIX inversée ({vix_short_value:.2f} > {vix_value:.2f}) ⇒ {config.vix.inverted_curve_mode}"
                if curve_inverted and vix_short_value is not None and vix_value is not None
                else (
                    f"Courbe VIX non inversée ({vix_short_value:.2f} ≤ {vix_value:.2f})"
                    if vix_short_value is not None and vix_value is not None
                    else "Courbe VIX indisponible"
                )
            ),
            details={"vix": vix_value, "vix_short": vix_short_value},
        )

    # 3. Macro Yield 10Y
    if config.yields.enabled:
        rel, spike, dq = evaluate_yield_10y(
            macro_provider,
            trade_date,
            lookback_days=config.yields.lookback_days,
            relative_spike_threshold=config.yields.relative_spike_threshold,
        )
        macro_metrics["yield_10y_5d_pct"] = rel
        data_quality.update(dq)
        if spike:
            blocked_sectors.extend(config.yields.block_sectors)
            block_high_beta = config.yields.block_high_beta
            high_beta_threshold = config.yields.high_beta_threshold
            risk_multiplier *= config.yields.risk_mult
            reasons.append(f"yield_spike_10y:{rel:.3%}")
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
            },
        )

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
        if not config.allow_neutral_fallback_on_missing_macro_data:
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
        allowed_slots = max(0, int(math.floor(equity / enforce_min_notional)))
        if effective_max_positions is None:
            effective_max_positions = allowed_slots
        else:
            effective_max_positions = min(int(effective_max_positions), allowed_slots)
        if allowed_slots == 0:
            allow_new_entries = False
            reasons.append("equity_too_low_for_min_notional")
        _push_trace(
            decision_trace,
            source="min_notional_guard",
            label="Garde-fou min notional",
            triggered=allowed_slots == 0,
            severity="warning" if allowed_slots == 0 else "info",
            resulting_mode="normal",
            value=allowed_slots,
            threshold=enforce_min_notional,
            message=(
                f"Equity insuffisante pour le min notional ({equity:.2f}$ / min {enforce_min_notional:.2f}$)"
                if allowed_slots == 0
                else f"Capital compatible : {allowed_slots} slot(s) autorisé(s)"
            ),
            details={"equity": equity, "enforce_min_notional": enforce_min_notional},
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
        blocked_sectors=tuple(dict.fromkeys(blocked_sectors)),
        block_high_beta=block_high_beta,
        high_beta_threshold=high_beta_threshold,
        earnings_shielded_symbols=cast(dict[str, Any], dict(earnings.shielded)),
        buyback_blackout_symbols=dict(earnings.buyback_blackout),
        earnings_negative_score_value=earnings.negative_score_value,
        allow_new_entries=allow_new_entries,
        active_patterns=tuple(active_patterns),
        reasons=tuple(reasons),
        macro=dict(macro_metrics),
        sentiment=dict(sentiment_payload),
        mode_why=_build_mode_why(mode, reasons, decision_trace),
        decision_trace=tuple(dict(item) for item in decision_trace),
        data_quality=dict(data_quality),
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

