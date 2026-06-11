"""Modèles immutables pour la couche centralisée de régime marché.

Cette couche est consommée par :

* `risk_management/` (sizing, slots dynamiques, contraintes sectorielles)
* `execution_engine/` (mode `close_only`/`cash_only`, pré-flight summary)
* `backtesting/` (parité métier sur `phase2_mode=risk_execution`)
* `selector/` (earnings shield, blacklist sectorielle)

Le snapshot est **immutable** (`frozen=True, slots=True`) et calculé une
seule fois par cycle (live) ou par snapshot_date (backtest), garantissant la
cohérence multi-modules sans recalcul redondant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Mapping, cast

RegimeMode = Literal[
    "normal",              # comportement nominal
    "capital_preservation", # réduit risque, max_positions limité
    "close_only",          # plus d'entrées, gestion sorties OK (live)
    "cash_only",           # plus d'entrées du tout (backtest / risk)
]

EarningsShieldMode = Literal["strict_block", "negative_score"]


@dataclass(frozen=True, slots=True)
class MarketRegimeState:
    """État persistant minimal de la machine de régime entre deux snapshots."""

    trade_date: date
    current_mode: RegimeMode = "normal"
    previous_mode: RegimeMode | None = None
    entered_at: date | None = None
    last_transition_at: date | None = None
    last_hard_trigger_at: date | None = None
    soft_entry_streak: int = 0
    soft_exit_streak: int = 0
    hard_calm_streak: int = 0
    days_in_current_mode: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "current_mode": self.current_mode,
            "previous_mode": self.previous_mode,
            "entered_at": self.entered_at.isoformat() if self.entered_at else None,
            "last_transition_at": self.last_transition_at.isoformat() if self.last_transition_at else None,
            "last_hard_trigger_at": self.last_hard_trigger_at.isoformat() if self.last_hard_trigger_at else None,
            "soft_entry_streak": self.soft_entry_streak,
            "soft_exit_streak": self.soft_exit_streak,
            "hard_calm_streak": self.hard_calm_streak,
            "days_in_current_mode": self.days_in_current_mode,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarketRegimeState":
        def _parse_date(value: Any) -> date | None:
            if not value:
                return None
            return date.fromisoformat(str(value))

        return cls(
            trade_date=date.fromisoformat(str(payload["trade_date"])),
            current_mode=cast(RegimeMode, str(payload.get("current_mode") or "normal")),
            previous_mode=cast(RegimeMode | None, str(payload["previous_mode"]) if payload.get("previous_mode") else None),
            entered_at=_parse_date(payload.get("entered_at")),
            last_transition_at=_parse_date(payload.get("last_transition_at")),
            last_hard_trigger_at=_parse_date(payload.get("last_hard_trigger_at")),
            soft_entry_streak=int(payload.get("soft_entry_streak", 0) or 0),
            soft_exit_streak=int(payload.get("soft_exit_streak", 0) or 0),
            hard_calm_streak=int(payload.get("hard_calm_streak", 0) or 0),
            days_in_current_mode=int(payload.get("days_in_current_mode", 0) or 0),
        )


@dataclass(frozen=True, slots=True)
class MarketRegimeSnapshot:
    """Contexte marché immutable pour un cycle d'exécution / un trade_date backtest."""

    trade_date: date
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    mode: RegimeMode = "normal"
    risk_multiplier: float = 1.0
    sentiment_threshold_addon: float = 0.0
    screener_expansion_pct: float = 0.0

    effective_max_positions: int | None = None
    enforced_min_notional: float | None = None
    allowed_slots: int | None = None
    max_tickers_per_sector: int | None = None
    max_position_weight: float | None = None
    max_sector_weight: float | None = None
    max_gross_exposure: float | None = None

    blocked_sectors: tuple[str, ...] = ()
    blocked_symbols: tuple[str, ...] = ()
    block_high_beta: bool = False
    high_beta_threshold: float = 1.2

    # mapping {symbol: 'block' | 'negative_score'} pour earnings shield
    earnings_shielded_symbols: Mapping[str, EarningsShieldMode] = field(default_factory=dict)
    # mapping {symbol: ml_score_multiplier (ex: 0.7)}
    buyback_blackout_symbols: Mapping[str, float] = field(default_factory=dict)
    earnings_negative_score_value: float = -1.0

    allow_new_entries: bool = True
    active_patterns: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    macro: Mapping[str, Any] = field(default_factory=dict)
    sentiment: Mapping[str, Any] = field(default_factory=dict)
    mode_why: Mapping[str, Any] = field(default_factory=dict)
    decision_trace: tuple[Mapping[str, Any], ...] = ()
    data_quality: Mapping[str, str] = field(default_factory=dict)
    raw_mode: RegimeMode = "normal"
    previous_mode: RegimeMode | None = None
    transition_action: str | None = None
    hysteresis_applied: bool = False
    soft_signal_count: int = 0
    hard_triggered: bool = False
    state_age_days: int | None = None
    next_state: MarketRegimeState | None = None

    # ------------------------------------------------------------------
    # Helpers de lecture
    # ------------------------------------------------------------------
    def is_defensive(self) -> bool:
        return self.mode in ("capital_preservation", "close_only", "cash_only")

    def blocks_entry_for(self, symbol: str, sector: str | None) -> tuple[bool, str | None]:
        """Retourne (blocked, reason) pour un candidat à l'entrée."""
        if not self.allow_new_entries:
            return True, "regime_blocks_new_entries"
        if symbol in self.blocked_symbols:
            return True, "blocked_symbol"
        if sector and sector in self.blocked_sectors:
            return True, f"blocked_sector:{sector}"
        if symbol in self.earnings_shielded_symbols:
            mode = self.earnings_shielded_symbols[symbol]
            if mode == "strict_block":
                return True, "earnings_shield"
        return False, None

    def to_summary_dict(self) -> dict:
        """Représentation sérialisable pour pré-flight / run summary / artefacts."""
        return {
            "trade_date": self.trade_date.isoformat(),
            "as_of": self.as_of.isoformat(),
            "mode": self.mode,
            "risk_multiplier": self.risk_multiplier,
            "sentiment_threshold_addon": self.sentiment_threshold_addon,
            "screener_expansion_pct": self.screener_expansion_pct,
            "effective_max_positions": self.effective_max_positions,
            "enforced_min_notional": self.enforced_min_notional,
            "allowed_slots": self.allowed_slots,
            "max_tickers_per_sector": self.max_tickers_per_sector,
            "max_position_weight": self.max_position_weight,
            "max_sector_weight": self.max_sector_weight,
            "max_gross_exposure": self.max_gross_exposure,
            "blocked_sectors": list(self.blocked_sectors),
            "blocked_symbols": list(self.blocked_symbols),
            "block_high_beta": self.block_high_beta,
            "earnings_shielded_symbols": dict(self.earnings_shielded_symbols),
            "buyback_blackout_symbols": dict(self.buyback_blackout_symbols),
            "allow_new_entries": self.allow_new_entries,
            "active_patterns": list(self.active_patterns),
            "reasons": list(self.reasons),
            "macro": dict(self.macro),
            "sentiment": dict(self.sentiment),
            "mode_why": dict(self.mode_why),
            "decision_trace": [dict(item) for item in self.decision_trace],
            "data_quality": dict(self.data_quality),
            "raw_mode": self.raw_mode,
            "previous_mode": self.previous_mode,
            "transition_action": self.transition_action,
            "hysteresis_applied": self.hysteresis_applied,
            "soft_signal_count": self.soft_signal_count,
            "hard_triggered": self.hard_triggered,
            "state_age_days": self.state_age_days,
            "next_state": self.next_state.to_dict() if self.next_state is not None else None,
        }

    def to_dict(self) -> dict:
        """Alias de compatibilité pour les consommateurs IHM / JSON.

        ``MarketRegimeSnapshot`` est un dataclass `slots=True`, donc il ne faut
        jamais compter sur ``__dict__`` pour sa sérialisation.
        """
        return self.to_summary_dict()


def neutral_snapshot(trade_date: date) -> MarketRegimeSnapshot:
    """Snapshot neutre — utilisé en fallback quand `market_regimes.enabled=false`."""
    return MarketRegimeSnapshot(
        trade_date=trade_date,
        reasons=("regime_disabled_or_neutral_fallback",),
        data_quality={"regime": "disabled"},
    )


__all__ = [
    "MarketRegimeSnapshot",
    "MarketRegimeState",
    "RegimeMode",
    "EarningsShieldMode",
    "neutral_snapshot",
]

