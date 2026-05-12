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
from typing import Any, Literal, Mapping

RegimeMode = Literal[
    "normal",              # comportement nominal
    "capital_preservation", # réduit risque, max_positions limité
    "close_only",          # plus d'entrées, gestion sorties OK (live)
    "cash_only",           # plus d'entrées du tout (backtest / risk)
]

EarningsShieldMode = Literal["strict_block", "negative_score"]


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
    "RegimeMode",
    "EarningsShieldMode",
    "neutral_snapshot",
]

