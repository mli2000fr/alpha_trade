"""risk_management/edge.py — Estimation directionnelle de l'edge net (Sprint Maître 8).

Remplace l'accuracy générique par des statistiques OOS directionnelles :
- Hit rate, payoff, tail loss par side/régime.
- Shrinkage bayésien sur petits échantillons.
- Edge net = gross return - coûts (spread, commission, slippage, borrow).
- Rejet par défaut si edge net ≤ 0.

Usage ::

    from risk_management.edge import DirectionalEdgeEstimate, EdgeCalculator
    calc = EdgeCalculator(config)
    edge = calc.estimate(side="long", hit_rate=0.55, payoff=1.5,
                         n_trades=50, borrow_fee=0.003)
    if edge.net_edge <= 0:
        reject  # pas de sizing
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


# ── DirectionalEdgeEstimate ─────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class DirectionalEdgeEstimate:
    """Estimation directionnelle de l'edge net (Sprint Maître 8).

    Attributes
    ----------
    side : str
        ``"long"`` ou ``"short"``.
    gross_edge : float
        Rendement brut espéré (hit_rate * payoff - (1-hit_rate) * 1).
    cost_pct : float
        Coûts totaux en % (spread + commission + slippage + borrow).
    net_edge : float
        Edge net après coûts. Si ≤ 0, le trade est rejeté.
    hit_rate : float
        Taux de trades gagnants OOS (0-1).
    payoff : float
        Ratio gain moyen / perte moyenne.
    tail_loss : float | None
        Pire perte observée en % (positive, ex: 0.15 = 15%).
    sample_size : int
        Nombre de trades dans l'échantillon OOS.
    uncertainty : float
        Incertitude estimée (erreur standard du edge).
    shrinkage_applied : bool
        True si un shrinkage bayésien a été appliqué (petit échantillon).
    """

    side: str
    gross_edge: float
    cost_pct: float
    net_edge: float
    hit_rate: float
    payoff: float
    tail_loss: float | None = None
    sample_size: int = 0
    uncertainty: float = 0.0
    shrinkage_applied: bool = False

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide : {self.side!r}")
        if not (0.0 <= self.hit_rate <= 1.0):
            raise ValueError(f"hit_rate hors bornes : {self.hit_rate}")
        if self.payoff < 0:
            raise ValueError(f"payoff doit être >= 0 : {self.payoff}")
        # payoff=0 is allowed when sample_size=0 (no trades to estimate from)

    @property
    def is_tradable(self) -> bool:
        """True si l'edge net est strictement positif."""
        return self.net_edge > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "side": self.side,
            "gross_edge": round(self.gross_edge, 6),
            "cost_pct": round(self.cost_pct, 6),
            "net_edge": round(self.net_edge, 6),
            "hit_rate": round(self.hit_rate, 4),
            "payoff": round(self.payoff, 4),
            "tail_loss": round(self.tail_loss, 4) if self.tail_loss is not None else None,
            "sample_size": self.sample_size,
            "uncertainty": round(self.uncertainty, 6),
            "shrinkage_applied": self.shrinkage_applied,
            "is_tradable": self.is_tradable,
        }


# ── EdgeCalculator ──────────────────────────────────────────────────────────

@dataclass
class EdgeCalculator:
    """Calcule l'edge net directionnel (Sprint Maître 8).

    Parameters
    ----------
    spread_bps, commission_bps, slippage_bps : float
        Coûts en bps (1 bps = 0.0001).
    borrow_fee_annual : float
        Coût d'emprunt annualisé (ex: 0.003 = 0.3%/an).
    min_sample_size : int
        Taille d'échantillon en dessous de laquelle un shrinkage est appliqué.
    shrinkage_prior_hit_rate : float
        Prior bayésien pour le hit rate (0.5 = non informatif).
    shrinkage_prior_payoff : float
        Prior bayésien pour le payoff (1.0 = non informatif).
    shrinkage_strength : float
        Force du shrinkage (poids du prior). 1.0 = prior complet, 0.0 = pas de shrinkage.
    """

    spread_bps: float = 5.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_fee_annual: float = 0.003
    min_sample_size: int = 30
    shrinkage_prior_hit_rate: float = 0.50
    shrinkage_prior_payoff: float = 1.0
    shrinkage_strength: float = 5.0  # poids du prior en trades équivalents

    @property
    def total_cost_bps(self) -> float:
        return 2 * (self.spread_bps + self.commission_bps + self.slippage_bps)

    @property
    def cost_pct(self) -> float:
        return self.total_cost_bps / 10000.0

    def estimate(
        self,
        *,
        side: str,
        hit_rate: float,
        payoff: float,
        n_trades: int,
        tail_loss: float | None = None,
        holding_days: int = 10,
    ) -> DirectionalEdgeEstimate:
        """Estime l'edge net directionnel.

        Parameters
        ----------
        side : str
        hit_rate : float
            Taux de trades gagnants OOS (0-1).
        payoff : float
            Ratio gain moyen / perte moyenne.
        n_trades : int
            Nombre de trades dans l'échantillon OOS.
        tail_loss : float | None
            Pire perte observée.
        holding_days : int
            Durée de détention estimée (pour borrow fee).

        Returns
        -------
        DirectionalEdgeEstimate
        """
        # ── Shrinkage bayésien sur petit échantillon ──────────────────
        shrinkage_applied = False
        if n_trades < self.min_sample_size:
            w_data = n_trades / (n_trades + self.shrinkage_strength)
            w_prior = 1.0 - w_data
            hit_rate = w_data * hit_rate + w_prior * self.shrinkage_prior_hit_rate
            payoff = w_data * payoff + w_prior * self.shrinkage_prior_payoff
            shrinkage_applied = True

        # ── Edge brut ─────────────────────────────────────────────────
        # E[return] = hit_rate * avg_gain - (1-hit_rate) * avg_loss
        # avg_gain = payoff * avg_loss → E[return] = avg_loss * (hit_rate * payoff - (1-hit_rate))
        # On normalise avg_loss = 1 (unité de risque)
        gross_edge = hit_rate * payoff - (1.0 - hit_rate) * 1.0

        # ── Coûts ─────────────────────────────────────────────────────
        cost = self.cost_pct
        # Borrow fee short
        if side == "short" and self.borrow_fee_annual > 0:
            cost += self.borrow_fee_annual * (holding_days / 252.0)

        net_edge = gross_edge - cost

        # ── Incertitude ───────────────────────────────────────────────
        # Erreur standard du edge (approximation binomiale)
        if n_trades > 0:
            se_hit_rate = math.sqrt(hit_rate * (1.0 - hit_rate) / n_trades)
            uncertainty = se_hit_rate * (payoff + 1.0)  # sensibilité du edge au hit rate
        else:
            uncertainty = 1.0

        return DirectionalEdgeEstimate(
            side=side,
            gross_edge=gross_edge,
            cost_pct=cost,
            net_edge=net_edge,
            hit_rate=hit_rate,
            payoff=payoff,
            tail_loss=tail_loss,
            sample_size=n_trades,
            uncertainty=uncertainty,
            shrinkage_applied=shrinkage_applied,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────

def compute_edge_from_trades(
    returns: np.ndarray,
    *,
    side: str = "long",
    cost_pct: float = 0.0016,
    min_sample_size: int = 30,
) -> DirectionalEdgeEstimate:
    """Calcule l'edge net à partir d'un historique de rendements de trades.

    Parameters
    ----------
    returns : np.ndarray
        Rendements nets de chaque trade (signés selon le side).
    side : str
    cost_pct : float
        Coûts déjà déduits ou à déduire.
    min_sample_size : int
        Seuil de shrinkage.

    Returns
    -------
    DirectionalEdgeEstimate
    """
    returns = np.asarray(returns, float)
    n = len(returns)
    if n == 0:
        return DirectionalEdgeEstimate(
            side=side, gross_edge=0.0, cost_pct=cost_pct, net_edge=0.0,
            hit_rate=0.0, payoff=0.0, sample_size=0,
        )

    wins = returns[returns > 0]
    losses = returns[returns < 0]

    hit_rate = len(wins) / n if n > 0 else 0.0
    avg_gain = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 1.0
    # payoff=0 quand avg_gain=0 (pas de gains); sinon ratio normal
    payoff = avg_gain / avg_loss if (avg_loss > 0 and avg_gain > 0) else 0.0
    tail_loss = float(np.min(returns)) if n > 0 else None

    gross_edge = hit_rate * payoff - (1.0 - hit_rate)
    net_edge = gross_edge - cost_pct

    # Shrinkage
    shrinkage = n < min_sample_size

    return DirectionalEdgeEstimate(
        side=side,
        gross_edge=gross_edge,
        cost_pct=cost_pct,
        net_edge=net_edge,
        hit_rate=hit_rate,
        payoff=payoff,
        tail_loss=tail_loss,
        sample_size=n,
        uncertainty=math.sqrt(hit_rate * (1.0 - hit_rate) / n) * (payoff + 1.0) if n > 1 else 1.0,
        shrinkage_applied=shrinkage,
    )
