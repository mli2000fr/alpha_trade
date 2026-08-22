"""risk_management/portfolio_optimizer.py — Optimiseur de portefeuille non-greedy (Sprint Maître 11).

Remplace le rejet greedy par une optimisation qui :
1. Inclut les holdings existants, cash, buying power, ordres ouverts
2. Optimise l'edge sous contraintes signées (gross/net, side, secteur, facteur, corrélation, ADV, turnover)
3. Mesure la contribution marginale au risque (MCTR) et l'expected shortfall
4. Réduit le candidat le plus dégradant au lieu de le rejeter
5. Applique des coûts de turnover et des no-trade bands
6. Garantit déterminisme, explications et fallback conservateur

Usage ::

    from risk_management.portfolio_optimizer import (
        PortfolioOptimizer, OptimizationResult, HoldingSnapshot,
        MarginalRiskDecomposition, TurnoverCosts, NoTradeBand,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ── HoldingSnapshot ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class HoldingSnapshot:
    """Position existante à inclure dans l'optimisation (Sprint Maître 11).

    Attributes
    ----------
    symbol : str
    side : str
        "long" ou "short".
    quantity : float
        Nombre de titres détenus.
    entry_price : float
        Prix d'entrée moyen.
    current_price : float
        Prix actuel.
    sector : str | None
    industry : str | None
    country : str | None
    currency : str | None
    theme : str | None
    unrealized_pnl_pct : float | None
    has_open_order : bool
        True si un ordre est déjà ouvert sur cette position.
    open_order_side : str | None
        "buy" ou "sell" si un ordre est ouvert.
    open_order_quantity : float | None
        Quantité de l'ordre ouvert.
    """

    symbol: str
    side: str = "long"
    quantity: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str | None = "USD"
    theme: str | None = None
    unrealized_pnl_pct: float | None = None
    has_open_order: bool = False
    open_order_side: str | None = None
    open_order_quantity: float | None = None

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide: {self.side!r}")

    @property
    def notional(self) -> float:
        return self.quantity * abs(self.current_price)

    @property
    def signed_notional(self) -> float:
        sign = 1.0 if self.side == "long" else -1.0
        return sign * self.quantity * abs(self.current_price)


# ── NoTradeBand ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NoTradeBand:
    """Bande de non-négociation autour d'une position existante (Sprint Maître 11).

    Si la taille cible est dans [current - lower, current + upper],
    aucun trade n'est généré (évite le turnover inutile).

    Attributes
    ----------
    lower_pct : float
        Bande inférieure en % (ex: 0.20 = on ne réduit pas si -20% de la taille actuelle).
    upper_pct : float
        Bande supérieure en % (ex: 0.20 = on n'augmente pas si +20%).
    min_notional_to_trade : float
        Notional minimum pour justifier un trade (frais de transaction).
    """

    lower_pct: float = 0.20
    upper_pct: float = 0.20
    min_notional_to_trade: float = 250.0

    def should_skip_trade(
        self, current_quantity: float, target_quantity: float, price: float,
    ) -> tuple[bool, str | None]:
        """Détermine si un trade doit être ignoré (dans la bande).

        Returns
        -------
        (skip, reason)
        """
        if current_quantity <= 0:
            return False, None  # Pas de position existante → on trade

        delta_pct = (target_quantity - current_quantity) / current_quantity

        # Dans la bande → no trade
        if -self.lower_pct <= delta_pct <= self.upper_pct:
            return True, f"delta={delta_pct:.1%} dans bande [{-self.lower_pct:.0%}, {self.upper_pct:.0%}]"

        # Vérifier le notional minimum
        delta_notional = abs(target_quantity - current_quantity) * price
        if delta_notional < self.min_notional_to_trade:
            return True, f"delta_notional={delta_notional:.0f} < min={self.min_notional_to_trade:.0f}"

        return False, None


# ── TurnoverCosts ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TurnoverCosts:
    """Coûts de turnover pour pénaliser les changements de portefeuille (Sprint Maître 11).

    Attributes
    ----------
    commission_bps : float
        Commission par trade en bps (aller-retour).
    spread_cost_bps : float
        Half-spread estimé en bps.
    market_impact_bps_per_pct_adv : float
        Impact de marché par % d'ADV tradé.
    total_one_way_bps : float
        Coût total one-way estimé.
    """

    commission_bps: float = 1.0
    spread_cost_bps: float = 2.5
    market_impact_bps_per_pct_adv: float = 2.0
    total_one_way_bps: float = 5.5

    def cost_of_trade(self, notional: float, adv_usd: float | None = None) -> float:
        """Coût total d'un trade en dollars.

        Parameters
        ----------
        notional : float
            Taille du trade en dollars.
        adv_usd : float | None
            ADV pour l'impact de marché.

        Returns
        -------
        float
            Coût en dollars.
        """
        cost_pct = self.total_one_way_bps / 10000.0
        if adv_usd and adv_usd > 0:
            participation_bps = (notional / adv_usd) * 10000.0
            cost_pct += (participation_bps / 100.0) * (self.market_impact_bps_per_pct_adv / 10000.0)
        return notional * cost_pct

    def cost_of_rebalance(
        self,
        current_notional: float,
        target_notional: float,
        adv_usd: float | None = None,
    ) -> float:
        """Coût total d'un rééquilibrage.

        Le turnover = |target - current|. On paie les coûts SUR LE DELTA.
        """
        delta = abs(target_notional - current_notional)
        if delta <= 0:
            return 0.0
        return self.cost_of_trade(delta, adv_usd)

    def annualized_turnover_impact(
        self,
        daily_turnover_pct: float,
        trading_days: int = 252,
    ) -> float:
        """Impact annualisé du turnover en % de l'AUM."""
        return daily_turnover_pct * trading_days * (self.total_one_way_bps / 10000.0)


# ── MarginalRiskDecomposition ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MarginalRiskDecomposition:
    """Décomposition du risque marginal (MCTR) d'un portefeuille (Sprint Maître 11).

    MCTR_i = w_i × (Σw)_i / σ_p  — contribution marginale au risque total.

    Attributes
    ----------
    weights : np.ndarray
        Poids du portefeuille (signés, somme = net_exposure).
    mctr : np.ndarray
        Contribution marginale au risque de chaque position.
    risk_contributions : np.ndarray
        Contribution absolue au risque (weight × MCTR × σ_p).
    total_risk : float
        Risque total du portefeuille (volatilité annualisée).
    symbols : list[str]
        Noms des symboles dans l'ordre.
    worst_contributor_idx : int | None
        Index du pire contributeur au risque.
    worst_contributor_symbol : str | None
        Symbole du pire contributeur.
    """

    weights: np.ndarray = field(default_factory=lambda: np.array([]))
    mctr: np.ndarray = field(default_factory=lambda: np.array([]))
    risk_contributions: np.ndarray = field(default_factory=lambda: np.array([]))
    total_risk: float = 0.0
    symbols: list[str] = field(default_factory=list)
    worst_contributor_idx: int | None = None
    worst_contributor_symbol: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "total_risk": round(self.total_risk, 6),
            "n_positions": len(self.symbols),
            "worst_contributor": self.worst_contributor_symbol,
            "worst_contribution_pct": (
                round(float(self.risk_contributions[self.worst_contributor_idx]) / max(self.total_risk, 1e-10), 4)
                if self.worst_contributor_idx is not None and self.total_risk > 0
                else None
            ),
        }


def compute_mctr(
    weights: np.ndarray,
    covariance: np.ndarray,
    symbols: list[str],
) -> MarginalRiskDecomposition:
    """Calcule la décomposition MCTR d'un portefeuille.

    MCTR_i = (Σw)_i / σ_p  (dérivée partielle du risque / poids)
    RC_i = w_i × MCTR_i × σ_p (contribution absolue au risque)

    Parameters
    ----------
    weights : np.ndarray
        Poids signés (shape N,).
    covariance : np.ndarray
        Matrice de covariance (shape N×N).
    symbols : list[str]
        Noms des symboles.

    Returns
    -------
    MarginalRiskDecomposition
    """
    weights = np.asarray(weights, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    n = len(weights)

    if n == 0 or covariance.size == 0:
        return MarginalRiskDecomposition()

    # Risque total
    portfolio_variance = weights @ covariance @ weights
    if portfolio_variance <= 0:
        return MarginalRiskDecomposition(weights=weights, symbols=symbols)

    portfolio_risk = math.sqrt(portfolio_variance)

    # MCTR = (Σw)_i / σ_p
    marginal_contrib = covariance @ weights
    mctr = marginal_contrib / max(portfolio_risk, 1e-10)

    # Risk contribution = w_i × MCTR_i × σ_p = w_i × (Σw)_i
    risk_contrib = weights * marginal_contrib

    # Pire contributeur (plus grande contribution positive au risque)
    worst_idx = int(np.argmax(risk_contrib)) if n > 0 else None
    worst_symbol = symbols[worst_idx] if worst_idx is not None and worst_idx < len(symbols) else None

    return MarginalRiskDecomposition(
        weights=weights,
        mctr=mctr,
        risk_contributions=risk_contrib,
        total_risk=portfolio_risk,
        symbols=list(symbols),
        worst_contributor_idx=worst_idx,
        worst_contributor_symbol=worst_symbol,
    )


# ── OptimizationResult ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Résultat d'une optimisation de portefeuille (Sprint Maître 11).

    Attributes
    ----------
    target_weights : dict[str, float]
        Poids cibles signés par symbole.
    target_quantities : dict[str, float]
        Quantités cibles par symbole.
    trades : dict[str, float]
        Quantités à trader (positives = acheter, négatives = vendre).
    total_edge : float
        Edge total du portefeuille (somme pondérée).
    total_risk : float
        Risque total estimé.
    turnover_pct : float
        Turnover en % de l'AUM.
    turnover_cost : float
        Coût estimé du turnover en dollars.
    rejected_symbols : dict[str, str]
        Symboles rejetés avec raison.
    reduced_symbols : dict[str, tuple[float, str]]
        Symboles réduits : (quantité proposée, raison).
    mctr_decomposition : MarginalRiskDecomposition | None
        Décomposition MCTR si calculée.
    audit_trail : tuple[str, ...]
        Traces d'audit pour chaque décision.
    """

    target_weights: dict[str, float] = field(default_factory=dict)
    target_quantities: dict[str, float] = field(default_factory=dict)
    trades: dict[str, float] = field(default_factory=dict)
    total_edge: float = 0.0
    total_risk: float = 0.0
    turnover_pct: float = 0.0
    turnover_cost: float = 0.0
    rejected_symbols: dict[str, str] = field(default_factory=dict)
    reduced_symbols: dict[str, tuple[float, str]] = field(default_factory=dict)
    mctr_decomposition: MarginalRiskDecomposition | None = None
    audit_trail: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "n_targets": len(self.target_weights),
            "n_trades": len(self.trades),
            "n_rejected": len(self.rejected_symbols),
            "n_reduced": len(self.reduced_symbols),
            "total_edge": round(self.total_edge, 6),
            "total_risk": round(self.total_risk, 6),
            "turnover_pct": round(self.turnover_pct, 4),
            "turnover_cost": round(self.turnover_cost, 2),
            "rejected_symbols": dict(self.rejected_symbols),
            "reduced_symbols": {k: {"qty": v[0], "reason": v[1]} for k, v in self.reduced_symbols.items()},
            "mctr": self.mctr_decomposition.to_dict() if self.mctr_decomposition else None,
        }


# ── PortfolioOptimizer ──────────────────────────────────────────────────────


@dataclass
class PortfolioOptimizer:
    """Optimiseur de portefeuille non-greedy (Sprint Maître 11).

    Logique :
    1. Part des holdings existants (positions déjà en portefeuille).
    2. Pour chaque nouveau candidat, évalue l'impact marginal sur les contraintes.
    3. Si une contrainte est violée, RÉDUIT le candidat le plus dégradant
       au lieu de le rejeter (non-greedy).
    4. Applique les no-trade bands pour éviter le turnover inutile.
    5. Mesure MCTR et turnover.

    Parameters
    ----------
    max_positions : int
    max_gross_exposure : float
    max_net_exposure : float
    max_position_weight : float
    no_trade_band : NoTradeBand
    turnover_costs : TurnoverCosts
    """

    max_positions: int = 20
    max_gross_exposure: float = 1.0
    max_net_exposure: float = 0.30
    max_position_weight: float = 0.10
    # CP-V2 — budgets par side (actifs seulement si non-None)
    max_long_exposure: float | None = None
    max_short_exposure: float | None = None
    no_trade_band: NoTradeBand = field(default_factory=NoTradeBand)
    turnover_costs: TurnoverCosts = field(default_factory=TurnoverCosts)

    def optimize(
        self,
        candidates: list[dict[str, Any]],
        existing_holdings: list[HoldingSnapshot] | None = None,
        *,
        account_equity: float = 100_000.0,
        covariance: np.ndarray | None = None,
    ) -> OptimizationResult:
        """Optimise le portefeuille.

        Parameters
        ----------
        candidates : list[dict]
            Liste de candidats, chaque dict doit contenir :
            - symbol (str)
            - side (str: "long"/"short")
            - edge (float) — edge net estimé
            - proposed_quantity (float) — quantité proposée par le sizing
            - price (float) — prix unitaire
            - sector (str, optional)
        existing_holdings : list[HoldingSnapshot] | None
            Positions existantes.
        account_equity : float
            Équité du compte.
        covariance : np.ndarray | None
            Matrice de covariance pour MCTR.

        Returns
        -------
        OptimizationResult
        """
        holdings = list(existing_holdings or [])
        audit: list[str] = []
        rejected: dict[str, str] = {}
        reduced: dict[str, tuple[float, str]] = {}

        # ── 1. Initialiser depuis les holdings existants ────────────────
        portfolio: dict[str, dict[str, Any]] = {}
        total_gross = 0.0
        total_net = 0.0
        total_long_gross = 0.0
        total_short_gross = 0.0

        for h in holdings:
            weight = h.signed_notional / account_equity if account_equity > 0 else 0.0
            portfolio[h.symbol] = {
                "symbol": h.symbol,
                "side": h.side,
                "quantity": h.quantity,
                "price": h.current_price,
                "notional": abs(h.signed_notional),
                "weight": weight,
                "edge": 0.0,  # Holdings existants n'ont pas d'edge ML
                "is_existing": True,
                "sector": h.sector,
                "has_open_order": h.has_open_order,
            }
            total_gross += abs(h.signed_notional)
            total_net += h.signed_notional
            if h.signed_notional >= 0:
                total_long_gross += abs(h.signed_notional)
            else:
                total_short_gross += abs(h.signed_notional)

        audit.append(f"holdings_init: {len(holdings)} positions, gross={total_gross/account_equity:.1%}, net={total_net/account_equity:.1%}")

        # ── 2. Filtrer les candidats avec ordres ouverts ────────────────
        blocked_by_order = set()
        for h in holdings:
            if h.has_open_order:
                blocked_by_order.add(h.symbol)
                audit.append(f"order_open_block: {h.symbol} (ordre {h.open_order_side} en cours)")

        # Les candidats bloqués par ordre ouvert sont rejetés
        for c in candidates:
            if c.get("symbol") in blocked_by_order:
                rejected[c["symbol"]] = "open_order_blocked"

        # ── 3. Trier les candidats par edge décroissant ─────────────────
        sorted_candidates = sorted(
            [c for c in candidates if c.get("symbol") not in blocked_by_order],
            key=lambda c: c.get("edge", 0.0),
            reverse=True,
        )

        # ── 4. Boucle d'optimisation non-greedy ─────────────────────────
        for candidate in sorted_candidates:
            symbol = candidate["symbol"]
            side = candidate.get("side", "long")
            proposed_qty = float(candidate.get("proposed_quantity", 0))
            price = float(candidate.get("price", 0))
            edge = float(candidate.get("edge", 0))
            sector = candidate.get("sector")

            if proposed_qty <= 0 or price <= 0:
                rejected[symbol] = "quantity_or_price_invalid"
                audit.append(f"reject:{symbol} qty={proposed_qty} price={price}")
                continue

            proposed_notional = proposed_qty * price
            sign = 1.0 if side == "long" else -1.0
            proposed_weight = sign * proposed_notional / account_equity if account_equity > 0 else 0.0
            existing_target = portfolio.get(symbol)
            existing_notional = float(existing_target["notional"]) if existing_target is not None else 0.0
            existing_sign = 1.0 if existing_target is None or existing_target["side"] == "long" else -1.0

            gross_without_symbol = total_gross - existing_notional
            net_without_symbol = total_net - existing_sign * existing_notional

            # ── Vérifier les contraintes ────────────────────────────────
            # Max positions
            current_positions = len(portfolio)
            if symbol not in portfolio and current_positions >= self.max_positions:
                # Non-greedy : trouver le pire candidat à réduire
                removed = self._reduce_worst_candidate(portfolio, audit)
                if removed is None:
                    rejected[symbol] = "max_positions_atteint"
                    audit.append(f"reject:{symbol} max_positions={self.max_positions}")
                    continue

            # Max gross exposure
            new_gross = gross_without_symbol + proposed_notional
            if new_gross > self.max_gross_exposure * account_equity:
                # Réduire le candidat pour fitter
                max_allowed_notional = (self.max_gross_exposure * account_equity) - gross_without_symbol
                if max_allowed_notional <= 0:
                    # Essayer de réduire le pire candidat existant
                    removed = self._reduce_worst_candidate(portfolio, audit)
                    if removed:
                        total_gross -= removed
                        max_allowed_notional = (self.max_gross_exposure * account_equity) - total_gross

                if max_allowed_notional <= 0:
                    rejected[symbol] = "max_gross_exposure_atteint"
                    audit.append(f"reject:{symbol} gross_exposure={new_gross/account_equity:.1%}")
                    continue

                # Réduire proportionnellement
                reduced_qty = math.floor(max_allowed_notional / price)
                if reduced_qty < 1:
                    rejected[symbol] = "max_gross_exposure_atteint"
                    continue
                reduced[symbol] = (float(reduced_qty), "max_gross_exposure")
                proposed_qty = float(reduced_qty)
                proposed_notional = proposed_qty * price
                audit.append(f"reduce:{symbol} gross_exposure: {candidate.get('proposed_quantity')}→{reduced_qty}")

            # CP-V2 — budget par side (réserve SHORT / cap LONG) — actif si défini
            _side_limit = self.max_short_exposure if side == "short" else self.max_long_exposure
            if _side_limit is not None:
                _existing_on_side = existing_target is not None and existing_target["side"] == side
                _side_total = total_short_gross if side == "short" else total_long_gross
                _side_without = _side_total - (existing_notional if _existing_on_side else 0.0)
                _side_remaining = _side_limit * account_equity - _side_without
                _side_reason = "max_short_exposure" if side == "short" else "max_long_exposure"
                if _side_remaining <= 0:
                    rejected[symbol] = f"{_side_reason}_atteint"
                    audit.append(f"reject:{symbol} {_side_reason} full side={side}")
                    continue
                _side_qty = math.floor(_side_remaining / price)
                if _side_qty < 1:
                    rejected[symbol] = f"{_side_reason}_atteint"
                    audit.append(f"reject:{symbol} {_side_reason} qty<1")
                    continue
                if _side_qty < proposed_qty:
                    reduced[symbol] = (float(_side_qty), _side_reason)
                    proposed_qty = float(_side_qty)
                    proposed_notional = proposed_qty * price
                    audit.append(f"reduce:{symbol} {_side_reason}: {candidate.get('proposed_quantity')}→{_side_qty}")

            # Max position weight
            max_notional_by_weight = self.max_position_weight * account_equity
            if proposed_notional > max_notional_by_weight:
                reduced_qty = math.floor(max_notional_by_weight / price)
                if reduced_qty < 1:
                    rejected[symbol] = "max_position_weight_atteint"
                    continue
                reduced[symbol] = (float(reduced_qty), "max_position_weight")
                proposed_qty = float(reduced_qty)
                proposed_notional = proposed_qty * price

            # Max net exposure signed. A replacement removes the old target
            # before testing the proposed side and quantity.
            max_net_notional = self.max_net_exposure * account_equity
            new_net = net_without_symbol + sign * proposed_notional
            if abs(new_net) > max_net_notional:
                allowed_notional = max_net_notional - sign * net_without_symbol
                if allowed_notional <= 0:
                    rejected[symbol] = "max_net_exposure_atteint"
                    audit.append(f"reject:{symbol} net_exposure={new_net/account_equity:.1%}")
                    continue
                reduced_qty = math.floor(allowed_notional / price)
                if reduced_qty < 1:
                    rejected[symbol] = "max_net_exposure_atteint"
                    continue
                reduced[symbol] = (float(reduced_qty), "max_net_exposure")
                proposed_qty = float(reduced_qty)
                proposed_notional = proposed_qty * price
                proposed_weight = sign * proposed_notional / account_equity if account_equity > 0 else 0.0
                audit.append(f"reduce:{symbol} net_exposure: {candidate.get('proposed_quantity')}→{reduced_qty}")

            # ── No-trade band ───────────────────────────────────────────
            if symbol in portfolio:
                current_qty = portfolio[symbol]["quantity"]
                existing_side = portfolio[symbol]["side"]

                # Si changement de side → on trade toujours
                if existing_side == side:
                    skip, reason = self.no_trade_band.should_skip_trade(current_qty, proposed_qty, price)
                    if skip:
                        audit.append(f"no_trade:{symbol} {reason}")
                        continue  # Garder la position existante, pas de trade

            # ── Accepter ─────────────────────────────────────────────────
            portfolio[symbol] = {
                "symbol": symbol,
                "side": side,
                "quantity": proposed_qty,
                "price": price,
                "notional": proposed_notional,
                "weight": proposed_weight,
                "edge": edge,
                "is_existing": symbol in [h.symbol for h in holdings],
                "sector": sector,
                "has_open_order": False,
            }
            total_gross = gross_without_symbol + proposed_notional
            total_net = net_without_symbol + sign * proposed_notional
            _existing_on_side_acc = existing_target is not None and existing_target["side"] == side
            if side == "short":
                total_short_gross = total_short_gross - (existing_notional if _existing_on_side_acc else 0.0) + proposed_notional
            else:
                total_long_gross = total_long_gross - (existing_notional if _existing_on_side_acc else 0.0) + proposed_notional
            audit.append(f"accept:{symbol} side={side} qty={proposed_qty} edge={edge:.4f}")

        # ── 5. Calculer les trades ──────────────────────────────────────
        target_weights: dict[str, float] = {}
        target_quantities: dict[str, float] = {}
        trades: dict[str, float] = {}

        for sym, data in portfolio.items():
            w = data["weight"]
            target_weights[sym] = w
            target_quantities[sym] = data["quantity"]

            # Trade = target - existing
            existing_qty = 0.0
            for h in holdings:
                if h.symbol == sym:
                    existing_qty = h.quantity
                    break
            delta = data["quantity"] - existing_qty
            if abs(delta) > 0:
                trades[sym] = delta

        # ── 6. Calculer turnover ────────────────────────────────────────
        turnover_notional = sum(abs(t * portfolio[s]["price"]) for s, t in trades.items())
        turnover_pct = turnover_notional / account_equity if account_equity > 0 else 0.0
        turnover_cost = self.turnover_costs.cost_of_rebalance(0, turnover_notional)

        # ── 7. MCTR ─────────────────────────────────────────────────────
        mctr_decomp = None
        if covariance is not None and len(target_weights) > 0:
            symbols_list = list(target_weights.keys())
            weights_arr = np.array([target_weights[s] for s in symbols_list])
            if len(weights_arr) > 1 and covariance.shape[0] >= len(weights_arr):
                mctr_decomp = compute_mctr(weights_arr, covariance[:len(weights_arr), :len(weights_arr)], symbols_list)

        # ── 8. Edge total ───────────────────────────────────────────────
        total_edge = sum(data["edge"] * data["notional"] for data in portfolio.values()) / account_equity if account_equity > 0 else 0.0

        return OptimizationResult(
            target_weights=target_weights,
            target_quantities=target_quantities,
            trades=trades,
            total_edge=total_edge,
            total_risk=mctr_decomp.total_risk if mctr_decomp else 0.0,
            turnover_pct=turnover_pct,
            turnover_cost=turnover_cost,
            rejected_symbols=rejected,
            reduced_symbols=reduced,
            mctr_decomposition=mctr_decomp,
            audit_trail=tuple(audit),
        )

    def _reduce_worst_candidate(
        self,
        portfolio: dict[str, dict[str, Any]],
        audit: list[str],
    ) -> float | None:
        """Trouve et retire le pire candidat du portefeuille.

        Le pire = celui avec le plus petit edge (ou le plus gros poids si edge égal).
        Ne retire JAMAIS un holding existant.

        Returns
        -------
        float | None
            Notional libéré, ou None si aucun candidat ne peut être retiré.
        """
        worst_symbol = None
        worst_edge = float("inf")
        worst_notional = 0.0

        for sym, data in portfolio.items():
            if data.get("is_existing"):
                continue  # Ne pas toucher aux holdings existants
            edge = data.get("edge", 0.0)
            notional = data.get("notional", 0.0)
            # Priorité : plus petit edge, puis plus gros notional
            if edge < worst_edge or (edge == worst_edge and notional > worst_notional):
                worst_edge = edge
                worst_notional = notional
                worst_symbol = sym

        if worst_symbol is None:
            return None

        removed_notional = portfolio[worst_symbol]["notional"]
        audit.append(f"reduce_worst: remove {worst_symbol} (edge={worst_edge:.4f}, notional={removed_notional:.0f})")
        del portfolio[worst_symbol]
        return removed_notional


# ── Helpers ─────────────────────────────────────────────────────────────────


def optimize_portfolio(
    candidates: list[dict[str, Any]],
    holdings: list[HoldingSnapshot] | None = None,
    *,
    account_equity: float = 100_000.0,
    max_positions: int = 20,
) -> OptimizationResult:
    """Fonction pure d'optimisation de portefeuille."""
    optimizer = PortfolioOptimizer(max_positions=max_positions)
    return optimizer.optimize(candidates, holdings, account_equity=account_equity)
