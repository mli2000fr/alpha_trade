"""Application d'un ``MarketRegimeSnapshot`` à un ``RiskConfig``.

Helper pur qui retourne un nouveau ``RiskConfig`` (via ``dataclasses.replace``)
en intégrant les contraintes du régime marché : ``risk_multiplier``,
``effective_max_positions``, ``enforce_min_notional`` et
``max_tickers_per_sector``.

Ce point unique d'application est utilisé à la fois par :

* ``risk_management/cli.py`` (live)
* ``backtesting/risk_bridge.py`` (backtest, parité)

Le snapshot peut être ``None`` (mode rétrocompat) — dans ce cas la fonction
retourne la config inchangée.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from risk_management.config import RiskConfig

if TYPE_CHECKING:
    from service.market import MarketRegimeSnapshot

LOGGER = logging.getLogger(__name__)


def apply_snapshot(
    cfg: RiskConfig,
    snapshot: MarketRegimeSnapshot | None,
) -> RiskConfig:
    """Retourne un nouveau ``RiskConfig`` ajusté au snapshot de régime."""
    if snapshot is None:
        return cfg

    updates: dict = {}

    # Multiplicateur de risque cumulatif (régime ne dégrade jamais en silence)
    if abs(snapshot.risk_multiplier - 1.0) > 1e-9:
        updates["risk_multiplier"] = float(snapshot.risk_multiplier) * float(cfg.risk_multiplier)

    if snapshot.enforced_min_notional is not None and snapshot.enforced_min_notional > 0:
        updates["enforce_min_notional"] = float(snapshot.enforced_min_notional)

    if snapshot.effective_max_positions is not None:
        updates["effective_max_positions_override"] = max(0, int(snapshot.effective_max_positions))

    if snapshot.max_tickers_per_sector is not None:
        updates["max_tickers_per_sector"] = int(snapshot.max_tickers_per_sector)

    if not updates:
        return cfg

    new_cfg = replace(cfg, **updates)
    LOGGER.info(
        "regime_apply: trade_date=%s mode=%s updates=%s",
        snapshot.trade_date, snapshot.mode, updates,
    )
    return new_cfg


__all__ = ["apply_snapshot"]

