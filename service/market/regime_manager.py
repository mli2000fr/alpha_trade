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
from typing import Callable, Literal

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
    macro_metrics: dict[str, float | None] = {}
    data_quality: dict[str, str] = {}

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

    # 2. Macro VIX
    if config.vix.enabled:
        vix_value, vix_high, curve_inverted, dq = evaluate_vix(
            macro_provider, trade_date, high_threshold=config.vix.high_threshold
        )
        macro_metrics["vix"] = vix_value
        data_quality.update(dq)
        if vix_high:
            mode = _escalate(mode, "capital_preservation")
            reasons.append(f"vix_high:{vix_value:.1f}")
        if curve_inverted:
            mode = _escalate(mode, config.vix.inverted_curve_mode)
            reasons.append("vix_curve_inverted")

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

    # 4. Sentiment circuit breaker
    if config.sentiment_circuit_breaker.enabled:
        sent = evaluate_sentiment_regime(
            config.sentiment_circuit_breaker,
            score_provider=sentiment_score_provider,
            execution_context=execution_context,
        )
        macro_metrics["sentiment_score"] = sent.score
        data_quality["sentiment"] = sent.data_quality
        if sent.suggested_mode != "normal":
            mode = _escalate(mode, sent.suggested_mode)
        if sent.suggested_max_positions is not None:
            effective_max_positions = (
                sent.suggested_max_positions
                if effective_max_positions is None
                else min(effective_max_positions, sent.suggested_max_positions)
            )
        reasons.extend(sent.reasons)

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
            effective_max_positions = min(effective_max_positions, allowed_slots)
        if allowed_slots == 0:
            allow_new_entries = False
            reasons.append("equity_too_low_for_min_notional")

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
        earnings_shielded_symbols=dict(earnings.shielded),
        buyback_blackout_symbols=dict(earnings.buyback_blackout),
        earnings_negative_score_value=earnings.negative_score_value,
        allow_new_entries=allow_new_entries,
        active_patterns=tuple(active_patterns),
        reasons=tuple(reasons),
        macro=dict(macro_metrics),
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

