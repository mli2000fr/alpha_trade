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
import math
from dataclasses import replace
from typing import TYPE_CHECKING

from risk_management.config import RiskConfig

if TYPE_CHECKING:
    from service.market import MarketRegimesConfig
    from service.market import MarketRegimeSnapshot

LOGGER = logging.getLogger(__name__)


def apply_structural_market_guards(
    cfg: RiskConfig,
    *,
    market_regimes_config: "MarketRegimesConfig | None",
    equity: float | None,
) -> RiskConfig:
    """Applique les garde-fous structurels petit compte indépendamment du régime.

    ``market_regimes`` porte historiquement deux responsabilités :
    - la logique macro/régime (modes, blocages d'entrées, caps défensifs) ;
    - un garde-fou structurel petit capital (`enforce_min_notional` + slots max).

    Pour qu'une ablation `regime_off` coupe uniquement la logique macro sans
    supprimer ce garde-fou structurel, on applique ici la partie *small-account*
    même lorsque ``market_regimes.enabled = false``.
    """
    if market_regimes_config is None:
        return cfg

    enforce_min_notional = float(getattr(market_regimes_config, "enforce_min_notional", 0.0) or 0.0)
    if enforce_min_notional <= 0:
        return cfg

    updates: dict[str, float | int] = {"enforce_min_notional": enforce_min_notional}
    if equity is not None and equity > 0:
        allowed_slots = max(0, int(math.floor(float(equity) / enforce_min_notional)))
        updates["effective_max_positions_override"] = min(cfg.effective_max_positions, allowed_slots)

    new_cfg = replace(cfg, **updates)
    LOGGER.info(
        "structural_guard_applied: market_regimes_enabled=%s equity=%s base_min_position_notional=%.2f effective_min_notional=%.2f effective_max_positions=%s",
        bool(getattr(market_regimes_config, "enabled", False)),
        equity,
        cfg.min_position_notional,
        new_cfg.effective_min_notional,
        new_cfg.effective_max_positions,
    )
    return new_cfg


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

    if snapshot.max_position_weight is not None:
        updates["max_position_weight"] = float(snapshot.max_position_weight)

    if snapshot.max_sector_weight is not None:
        updates["max_sector_weight"] = float(snapshot.max_sector_weight)

    if snapshot.max_gross_exposure is not None:
        updates["max_gross_exposure"] = float(snapshot.max_gross_exposure)

    if not updates:
        return cfg

    new_cfg = replace(cfg, **updates)
    LOGGER.info(
        "regime_apply: trade_date=%s mode=%s updates=%s",
        snapshot.trade_date, snapshot.mode, updates,
    )
    return new_cfg


__all__ = ["apply_snapshot", "apply_structural_market_guards"]

