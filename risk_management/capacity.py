"""risk_management/capacity.py — Estimation de capacité (Sprint Maître 10).

Estime la capacité d'exécution par stratégie, secteur et symbole en fonction
de l'ADV, du spread, et des contraintes de participation.

Usage ::

    from risk_management.capacity import CapacityEstimator, CapacityEstimate
    estimator = CapacityEstimator()
    cap = estimator.estimate_symbol(symbol="AAPL", adv_usd=50_000_000, spread_bps=3.0)
    print(f"Max shares: {cap.max_shares_at_price(150.0)}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── CapacityEstimate ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CapacityEstimate:
    """Estimation de capacité pour un symbole ou une stratégie (Sprint Maître 10).

    Attributes
    ----------
    scope : str
        Portée de l'estimation : "symbol", "sector", "strategy".
    scope_key : str
        Identifiant dans la portée (ex: "AAPL", "Tech", "momentum").
    max_notional : float
        Notional maximum recommandé.
    max_shares : int | None
        Nombre maximum de titres (si prix fourni).
    turnover_days : float
        Jours estimés pour liquider la position en conditions normales.
    turnover_days_stressed : float
        Jours estimés pour liquider en conditions stressées.
    adv_usd : float
        ADV utilisé pour l'estimation.
    participation_pct : float
        Participation max utilisée.
    is_constrained_by_adv : bool
        True si la capacité est limitée par l'ADV.
    is_constrained_by_spread : bool
        True si la capacité est limitée par le spread.
    """

    scope: str
    scope_key: str
    max_notional: float = 0.0
    max_shares: int | None = None
    turnover_days: float = 0.0
    turnover_days_stressed: float = 0.0
    adv_usd: float = 0.0
    participation_pct: float = 0.01
    is_constrained_by_adv: bool = False
    is_constrained_by_spread: bool = False

    def max_shares_at_price(self, price: float) -> int:
        """Nombre maximum de titres à un prix donné."""
        if price <= 0:
            return 0
        return int(math.floor(self.max_notional / price))

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "scope_key": self.scope_key,
            "max_notional": round(self.max_notional, 2),
            "max_shares": self.max_shares,
            "turnover_days": round(self.turnover_days, 1),
            "turnover_days_stressed": round(self.turnover_days_stressed, 1),
            "adv_usd": round(self.adv_usd, 2),
            "participation_pct": round(self.participation_pct, 6),
            "is_constrained_by_adv": self.is_constrained_by_adv,
            "is_constrained_by_spread": self.is_constrained_by_spread,
        }


# ── CapacityEstimator ───────────────────────────────────────────────────────


@dataclass
class CapacityEstimator:
    """Estimateur de capacité par symbole, secteur et stratégie (Sprint Maître 10).

    La capacité est le notional maximum qu'une stratégie peut allouer à un
    symbole sans dépasser les limites de participation ADV ni générer un
    slippage excessif.

    Parameters
    ----------
    max_participation_pct : float
        Participation max de l'ADV (défaut 1%).
    max_participation_stressed_pct : float
        Participation max en liquidation stressée (défaut 0.5%).
    max_slippage_bps : float
        Slippage max acceptable en bps (défaut 50 bps = 0.5%).
    max_spread_bps : float | None
        Spread max pour considérer le titre comme "liquide" (None = pas de filtre).
    min_adv_for_capacity : float
        ADV minimum pour estimer une capacité (défaut $1M).
    """

    max_participation_pct: float = 0.01
    max_participation_stressed_pct: float = 0.005
    max_slippage_bps: float = 50.0
    max_spread_bps: float | None = 20.0
    min_adv_for_capacity: float = 1_000_000.0

    def estimate_symbol(
        self,
        symbol: str,
        *,
        adv_usd: float,
        spread_bps: float | None = None,
        price: float | None = None,
    ) -> CapacityEstimate:
        """Estime la capacité pour un symbole unique.

        Parameters
        ----------
        symbol : str
        adv_usd : float
            Volume quotidien moyen en dollars.
        spread_bps : float | None
            Spread bid-ask en bps.
        price : float | None
            Prix unitaire (pour calculer max_shares).

        Returns
        -------
        CapacityEstimate
        """
        constrained_by_adv = False
        constrained_by_spread = False

        if adv_usd <= 0 or adv_usd < self.min_adv_for_capacity:
            return CapacityEstimate(
                scope="symbol",
                scope_key=symbol,
                max_notional=0.0,
                adv_usd=adv_usd,
                is_constrained_by_adv=True,
            )

        # ── Capacité nominale basée sur l'ADV ──────────────────────────
        max_notional = adv_usd * self.max_participation_pct

        # ── Ajustement spread ───────────────────────────────────────────
        if spread_bps is not None and self.max_spread_bps is not None:
            if spread_bps > self.max_spread_bps:
                # Spread élevé → réduction de capacité
                spread_ratio = self.max_spread_bps / max(spread_bps, 1.0)
                max_notional *= spread_ratio
                constrained_by_spread = True

        # ── Ajustement slippage ─────────────────────────────────────────
        # Capacité telle que le slippage estimé ≤ max_slippage_bps
        # Slippage ≈ spread/2 + impact_factor * sqrt(participation) * 10000
        # On résout pour participation_max
        impact_factor = 0.1
        half_spread = (spread_bps or 5.0) / 2.0
        remaining_bps = max(0.0, self.max_slippage_bps - half_spread)
        if remaining_bps > 0:
            max_participation_from_slippage = (remaining_bps / (impact_factor * 10000.0)) ** 2
            max_notional_from_slippage = adv_usd * max_participation_from_slippage
            max_notional = min(max_notional, max_notional_from_slippage)

        if max_notional <= 0:
            constrained_by_adv = True
            max_notional = 0.0

        # ── Turnover ────────────────────────────────────────────────────
        turnover_days = 0.0
        turnover_days_stressed = 0.0
        if adv_usd > 0 and max_notional > 0:
            # En conditions normales
            daily_capacity = adv_usd * self.max_participation_pct
            turnover_days = max_notional / daily_capacity if daily_capacity > 0 else float("inf")
            # En conditions stressées
            daily_stressed = adv_usd * self.max_participation_stressed_pct
            turnover_days_stressed = (
                max_notional / daily_stressed if daily_stressed > 0 else float("inf")
            )

        max_shares = None
        if price is not None and price > 0:
            max_shares = int(math.floor(max_notional / price))

        return CapacityEstimate(
            scope="symbol",
            scope_key=symbol,
            max_notional=max_notional,
            max_shares=max_shares,
            turnover_days=turnover_days,
            turnover_days_stressed=turnover_days_stressed,
            adv_usd=adv_usd,
            participation_pct=self.max_participation_pct,
            is_constrained_by_adv=constrained_by_adv,
            is_constrained_by_spread=constrained_by_spread,
        )

    def estimate_sector(
        self,
        sector: str,
        symbols: list[str],
        adv_map: dict[str, float],
        spread_map: dict[str, float] | None = None,
    ) -> CapacityEstimate:
        """Estime la capacité agrégée pour un secteur.

        La capacité secteur est la somme des capacités symbole,
        avec un facteur de corrélation implicite.

        Parameters
        ----------
        sector : str
            Nom du secteur.
        symbols : list[str]
            Liste des symboles du secteur.
        adv_map : dict[str, float]
            Mapping symbole → ADV.
        spread_map : dict[str, float] | None
            Mapping symbole → spread_bps.

        Returns
        -------
        CapacityEstimate
        """
        total_notional = 0.0
        total_adv = 0.0
        constrained_by_adv = False
        constrained_by_spread = False

        for sym in symbols:
            adv = adv_map.get(sym, 0.0)
            spread = spread_map.get(sym) if spread_map else None
            total_adv += adv

            sym_cap = self.estimate_symbol(sym, adv_usd=adv, spread_bps=spread)
            total_notional += sym_cap.max_notional
            if sym_cap.is_constrained_by_adv:
                constrained_by_adv = True
            if sym_cap.is_constrained_by_spread:
                constrained_by_spread = True

        # Facteur de corrélation intra-secteur (réduction de 30%)
        correlation_discount = 0.70
        total_notional *= correlation_discount

        turnover_days = 0.0
        if total_adv > 0 and total_notional > 0:
            turnover_days = total_notional / (total_adv * self.max_participation_pct)

        return CapacityEstimate(
            scope="sector",
            scope_key=sector,
            max_notional=total_notional,
            turnover_days=turnover_days,
            turnover_days_stressed=turnover_days * 2.0 if turnover_days > 0 else 0.0,
            adv_usd=total_adv,
            is_constrained_by_adv=constrained_by_adv,
            is_constrained_by_spread=constrained_by_spread,
        )

    def estimate_strategy(
        self,
        strategy_name: str,
        symbol_capacities: list[CapacityEstimate],
        *,
        max_positions: int = 20,
        correlation_factor: float = 0.60,
    ) -> CapacityEstimate:
        """Estime la capacité totale d'une stratégie.

        Prend les N meilleures capacités symbole et applique un facteur
        de corrélation inter-symboles.

        Parameters
        ----------
        strategy_name : str
            Nom de la stratégie.
        symbol_capacities : list[CapacityEstimate]
            Capacités par symbole (triées par max_notional décroissant).
        max_positions : int
            Nombre maximum de positions.
        correlation_factor : float
            Facteur de corrélation moyen (0-1). 1.0 = pas de corrélation.
            Plus c'est bas, plus les symboles sont corrélés → moins de capacité.

        Returns
        -------
        CapacityEstimate
        """
        # Prendre les top N
        sorted_caps = sorted(symbol_capacities, key=lambda c: c.max_notional, reverse=True)
        top_caps = sorted_caps[:max_positions]

        total_notional = sum(c.max_notional for c in top_caps)
        total_adv = sum(c.adv_usd for c in top_caps)

        # Facteur de diversification : sqrt(N) * correlation_factor
        # Plus il y a de positions décorrélées, plus la capacité effective est élevée
        diversification = math.sqrt(len(top_caps)) * correlation_factor
        effective_notional = total_notional * min(diversification, 1.0)

        return CapacityEstimate(
            scope="strategy",
            scope_key=strategy_name,
            max_notional=effective_notional,
            turnover_days=0.0,
            adv_usd=total_adv,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def estimate_symbol_capacity(
    symbol: str,
    adv_usd: float,
    *,
    spread_bps: float | None = None,
    price: float | None = None,
    max_participation_pct: float = 0.01,
) -> CapacityEstimate:
    """Fonction pure d'estimation de capacité symbole."""
    estimator = CapacityEstimator(max_participation_pct=max_participation_pct)
    return estimator.estimate_symbol(symbol, adv_usd=adv_usd, spread_bps=spread_bps, price=price)
