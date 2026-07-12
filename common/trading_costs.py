"""common/trading_costs.py — Modèle canonique partagé de coûts de trading.

Sprint Maître 2 / Section 17 Point 3 :
- Ce module est la source unique de vérité pour les paramètres de coûts.
- Utilisé par ``modelFactory/labeling.py`` (triple-barrier labeling),
  ``risk_management/edge.py`` (EdgeCalculator) et à terme par
  ``backtesting/simulator.py``.
- Garantit que le même spread, commission, slippage et borrow fee
  sont utilisés partout → parité label/backtest.

Usage ::

    from common.trading_costs import TradingCostModel, DEFAULT_COST_MODEL

    costs = TradingCostModel(spread_bps=5.0, commission_bps=1.0, slippage_bps=2.0)
    round_trip_pct = costs.round_trip_cost_pct  # 0.0016
    edge_net = gross_return - round_trip_pct
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingCostModel:
    """Modèle canonique de coûts de trading (aller-retour).

    Tous les coûts sont exprimés en **points de base** (bps).
    1 bps = 0.0001 = 0.01%.

    Attributes
    ----------
    spread_bps : float
        Half-spread estimé en bps. Coût payé une fois à l'entrée,
        une fois à la sortie → ×2 dans le coût aller-retour.
    commission_bps : float
        Commission de courtage en bps par jambe.
    slippage_bps : float
        Slippage estimé en bps par jambe (hors impact volume).
    borrow_fee_annual : float
        Coût d'emprunt annualisé pour les shorts (ex: 0.003 = 0.3%/an).
        Appliqué proportionnellement à la durée de détention.
    min_tick : float
        Tick minimum en dollars (pour arrondi).
    """

    spread_bps: float = 5.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_fee_annual: float = 0.003
    min_tick: float = 0.01

    # ── Propriétés calculées ──────────────────────────────────────────────

    @property
    def per_leg_cost_bps(self) -> float:
        """Coût par jambe en bps (spread + commission + slippage)."""
        return self.spread_bps + self.commission_bps + self.slippage_bps

    @property
    def round_trip_cost_bps(self) -> float:
        """Coût aller-retour en bps (2 jambes)."""
        return 2.0 * self.per_leg_cost_bps

    @property
    def per_leg_cost_pct(self) -> float:
        """Coût par jambe en pourcentage (ex: 0.0008 = 8 bps)."""
        return self.per_leg_cost_bps / 10000.0

    @property
    def round_trip_cost_pct(self) -> float:
        """Coût aller-retour en pourcentage (ex: 0.0016 = 16 bps)."""
        return self.round_trip_cost_bps / 10000.0

    # ── Méthodes ──────────────────────────────────────────────────────────

    def deduct_round_trip(
        self,
        gross_return: float,
    ) -> float:
        """Déduit le coût aller-retour d'un rendement brut.

        Parameters
        ----------
        gross_return : float
            Rendement brut (ex: 0.02 = +2%).

        Returns
        -------
        float
            Rendement net après coûts aller-retour.
        """
        return gross_return - self.round_trip_cost_pct

    def borrow_cost_for_holding(
        self,
        holding_sessions: int,
        *,
        sessions_per_year: int = 252,
    ) -> float:
        """Coût d'emprunt proportionnel à la durée de détention.

        Parameters
        ----------
        holding_sessions : int
            Nombre de sessions de détention.
        sessions_per_year : int
            Nombre de sessions par an (252 par défaut).

        Returns
        -------
        float
            Coût d'emprunt en pourcentage du notionnel.
        """
        if self.borrow_fee_annual <= 0:
            return 0.0
        return self.borrow_fee_annual * (holding_sessions / sessions_per_year)

    def effective_cost_for_trade(
        self,
        gross_return: float,
        side: str,
        holding_sessions: int = 1,
    ) -> float:
        """Coût effectif total pour un trade complet.

        Parameters
        ----------
        gross_return : float
            Rendement brut.
        side : str
            "long" ou "short".
        holding_sessions : int
            Sessions de détention.

        Returns
        -------
        float
            Rendement net après TOUS les coûts (spread, comm, slippage, borrow).
        """
        net = self.deduct_round_trip(gross_return)
        if side == "short":
            net -= self.borrow_cost_for_holding(holding_sessions)
        return net

    def to_dict(self) -> dict:
        """Sérialise le modèle de coûts."""
        return {
            "spread_bps": self.spread_bps,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "borrow_fee_annual": self.borrow_fee_annual,
            "per_leg_cost_bps": self.per_leg_cost_bps,
            "round_trip_cost_bps": self.round_trip_cost_bps,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TradingCostModel":
        """Désérialise un modèle de coûts (ignore les champs calculés)."""
        return cls(
            spread_bps=float(d.get("spread_bps", 5.0)),
            commission_bps=float(d.get("commission_bps", 1.0)),
            slippage_bps=float(d.get("slippage_bps", 2.0)),
            borrow_fee_annual=float(d.get("borrow_fee_annual", 0.003)),
        )


# ── Default instance ────────────────────────────────────────────────────────

DEFAULT_COST_MODEL = TradingCostModel()
"""Modèle de coûts par défaut utilisé dans tout le projet.

- spread = 5 bps
- commission = 1 bps
- slippage = 2 bps
- round-trip = 16 bps (0.16%)
- borrow = 0.3%/an
"""
