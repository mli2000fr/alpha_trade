"""risk_management/shadow_engine.py — Moteur de shadow trading (Sprint Maître 14).

Exécute un modèle challenger en parallèle du champion live, sans ordre réel :
1. Produit les cibles shadow à partir des mêmes features PIT
2. Compare les décisions shadow vs live (side, taille, rejet)
3. Mesure la divergence et produit un rapport de cross-validation
4. Simule les fills shadow depuis les quotes observées

Usage ::

    from risk_management.shadow_engine import (
        ShadowEngine, ShadowRun, ShadowComparisonReport, ShadowFillSimulator,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── ShadowRunStatus ─────────────────────────────────────────────────────────


class ShadowRunStatus(StrEnum):
    """Statut d'un run shadow (Sprint Maître 14)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    DIVERGENT = "divergent"    # Différences détectées vs live
    CONVERGENT = "convergent"  # Aucune différence vs live
    FAILED = "failed"          # Erreur pendant le run


# ── ShadowDecision ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    """Décision shadow pour un symbole (Sprint Maître 14).

    Compare la décision du modèle shadow avec celle du champion live.
    """

    symbol: str
    side: str  # long / short / flat
    shadow_side: str
    shadow_shares: float = 0.0
    live_side: str = "flat"
    live_shares: float = 0.0
    side_match: bool = True
    shares_match: bool = True
    shares_delta_pct: float = 0.0
    shadow_edge: float | None = None
    live_edge: float | None = None
    shadow_price: float = 0.0
    live_price: float = 0.0
    divergence_reason: str | None = None

    @property
    def is_divergent(self) -> bool:
        """True si le shadow diffère du live."""
        return not self.side_match or not self.shares_match

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "shadow_side": self.shadow_side,
            "live_side": self.live_side,
            "shadow_shares": self.shadow_shares,
            "live_shares": self.live_shares,
            "side_match": self.side_match,
            "shares_match": self.shares_match,
            "shares_delta_pct": round(self.shares_delta_pct, 4),
            "is_divergent": self.is_divergent,
            "divergence_reason": self.divergence_reason,
        }


# ── ShadowComparisonReport ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ShadowComparisonReport:
    """Rapport de comparaison shadow vs live (Sprint Maître 14).

    Attributes
    ----------
    shadow_run_id : str
    live_run_id : str
    timestamp : datetime
    status : ShadowRunStatus
    total_decisions : int
    side_divergences : int
        Nombre de décisions où le side diffère.
    shares_divergences : int
        Nombre de décisions où les quantités diffèrent.
    avg_shares_delta_pct : float
        Delta moyen des quantités en %.
    symbols_only_shadow : list[str]
        Symboles présents uniquement dans le shadow.
    symbols_only_live : list[str]
        Symboles présents uniquement dans le live.
    decisions : tuple[ShadowDecision, ...]
    summary : str
    """

    shadow_run_id: str = ""
    live_run_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    status: ShadowRunStatus = ShadowRunStatus.PENDING
    total_decisions: int = 0
    side_divergences: int = 0
    shares_divergences: int = 0
    avg_shares_delta_pct: float = 0.0
    symbols_only_shadow: tuple[str, ...] = ()
    symbols_only_live: tuple[str, ...] = ()
    decisions: tuple[ShadowDecision, ...] = ()
    summary: str = ""

    @property
    def divergence_rate(self) -> float:
        """Taux de divergence (side OU shares)."""
        if self.total_decisions == 0:
            return 0.0
        divergent = sum(1 for d in self.decisions if d.is_divergent)
        return divergent / self.total_decisions

    @property
    def is_convergent(self) -> bool:
        """True si aucune divergence détectée."""
        return self.divergence_rate == 0.0 and len(self.symbols_only_shadow) == 0 and len(self.symbols_only_live) == 0

    @property
    def side_divergence_rate(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.side_divergences / self.total_decisions

    def to_dict(self) -> dict[str, object]:
        return {
            "shadow_run_id": self.shadow_run_id,
            "live_run_id": self.live_run_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "total_decisions": self.total_decisions,
            "side_divergences": self.side_divergences,
            "shares_divergences": self.shares_divergences,
            "avg_shares_delta_pct": round(self.avg_shares_delta_pct, 4),
            "symbols_only_shadow": list(self.symbols_only_shadow),
            "symbols_only_live": list(self.symbols_only_live),
            "divergence_rate": round(self.divergence_rate, 4),
            "is_convergent": self.is_convergent,
            "summary": self.summary,
        }


# ── ShadowFillSimulator ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    """Fill simulé à partir d'une quote observée (Sprint Maître 14)."""

    symbol: str
    side: str
    requested_shares: float
    filled_shares: float
    fill_price: float
    quote_bid: float | None = None
    quote_ask: float | None = None
    quote_time: datetime | None = None
    slippage_bps: float = 0.0
    is_partial: bool = False
    fill_reason: str = "filled"

    @property
    def fill_rate(self) -> float:
        if self.requested_shares <= 0:
            return 0.0
        return self.filled_shares / self.requested_shares

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "requested_shares": self.requested_shares,
            "filled_shares": self.filled_shares,
            "fill_price": round(self.fill_price, 2),
            "slippage_bps": round(self.slippage_bps, 1),
            "fill_rate": round(self.fill_rate, 4),
            "is_partial": self.is_partial,
        }


@dataclass
class ShadowFillSimulator:
    """Simule des fills à partir de quotes bid/ask observées (Sprint Maître 14).

    Contrairement au backtest qui utilise `entry_price` (prix théorique),
    le simulateur paper utilise les vraies quotes pour estimer :
    - Prix de fill réel (bid pour achat, ask pour vente)
    - Slippage vs mid-price
    - Partial fills (si quantité > liquidité disponible)
    """

    # Hypothèses de liquidité
    max_pct_of_adv_per_fill: float = 0.01  # 1% ADV max par fill
    partial_fill_probability: float = 0.05  # 5% de chance de partial fill
    slippage_std_bps: float = 2.0  # Écart-type du slippage en bps

    def simulate_fill(
        self,
        symbol: str,
        side: str,
        requested_shares: float,
        *,
        entry_price: float,
        bid: float | None = None,
        ask: float | None = None,
        adv_usd: float | None = None,
    ) -> SimulatedFill:
        """Simule un fill à partir des quotes disponibles.

        Parameters
        ----------
        symbol : str
        side : str
        requested_shares : float
        entry_price : float
            Prix de référence (théorique).
        bid : float | None
        ask : float | None
        adv_usd : float | None

        Returns
        -------
        SimulatedFill
        """
        import random
        import math

        # ── Prix de fill ───────────────────────────────────────────────
        if side == "long":
            fill_price = ask if ask is not None else entry_price
        else:
            fill_price = bid if bid is not None else entry_price

        # ── Slippage ────────────────────────────────────────────────────
        mid = entry_price
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2.0

        slippage_bps = 0.0
        if mid > 0:
            slippage_bps = abs(fill_price - mid) / mid * 10000.0
            # Ajouter un bruit gaussien
            slippage_bps += random.gauss(0, self.slippage_std_bps)

        # ── Partial fill ────────────────────────────────────────────────
        filled = requested_shares
        is_partial = False
        fill_reason = "filled"

        # Vérifier ADV
        if adv_usd is not None and adv_usd > 0:
            max_notional = adv_usd * self.max_pct_of_adv_per_fill
            max_shares = math.floor(max_notional / fill_price) if fill_price > 0 else float("inf")
            if requested_shares > max_shares:
                filled = float(max_shares)
                is_partial = True
                fill_reason = "adv_capped"

        # Partial fill aléatoire
        if not is_partial and random.random() < self.partial_fill_probability:
            filled = math.floor(requested_shares * random.uniform(0.5, 0.95))
            is_partial = True
            fill_reason = "partial_liquidity"

        return SimulatedFill(
            symbol=symbol,
            side=side,
            requested_shares=requested_shares,
            filled_shares=filled,
            fill_price=fill_price,
            quote_bid=bid,
            quote_ask=ask,
            slippage_bps=max(0.0, slippage_bps),
            is_partial=is_partial,
            fill_reason=fill_reason,
        )


# ── ShadowEngine ────────────────────────────────────────────────────────────


@dataclass
class ShadowEngine:
    """Moteur de shadow trading (Sprint Maître 14).

    Produit les décisions du modèle shadow et les compare au live.

    Le moteur est PUR : il compare des décisions déjà calculées,
    il n'appelle pas le modèle ML ni le bridge risque.
    """

    fill_simulator: ShadowFillSimulator = field(default_factory=ShadowFillSimulator)

    def compare(
        self,
        shadow_run_id: str,
        live_run_id: str,
        *,
        shadow_decisions: list[dict[str, object]],
        live_decisions: list[dict[str, object]],
    ) -> ShadowComparisonReport:
        """Compare les décisions shadow vs live.

        Parameters
        ----------
        shadow_run_id : str
        live_run_id : str
        shadow_decisions : list[dict]
            Chaque dict doit contenir : symbol, side, shares, price, edge
        live_decisions : list[dict]
            Même format.

        Returns
        -------
        ShadowComparisonReport
        """
        shadow_by_sym: dict[str, dict[str, object]] = {
            str(d["symbol"]): d for d in shadow_decisions
        }
        live_by_sym: dict[str, dict[str, object]] = {
            str(d["symbol"]): d for d in live_decisions
        }

        all_symbols = set(shadow_by_sym.keys()) | set(live_by_sym.keys())
        shadow_only = sorted(set(shadow_by_sym.keys()) - set(live_by_sym.keys()))
        live_only = sorted(set(live_by_sym.keys()) - set(shadow_by_sym.keys()))

        decisions: list[ShadowDecision] = []
        side_divs = 0
        shares_divs = 0
        total_delta = 0.0
        n_common = 0

        for sym in sorted(all_symbols):
            sd = shadow_by_sym.get(sym, {})
            ld = live_by_sym.get(sym, {})

            s_side = str(sd.get("side", "flat"))
            l_side = str(ld.get("side", "flat"))
            s_shares = float(sd.get("shares", 0))
            l_shares = float(ld.get("shares", 0))

            side_match = s_side == l_side
            delta_pct = 0.0
            if l_shares > 0:
                delta_pct = abs(s_shares - l_shares) / l_shares
            shares_match = delta_pct < 0.01  # < 1% tolérance

            reason = None
            if not side_match:
                reason = f"side: shadow={s_side} live={l_side}"
                side_divs += 1
            elif not shares_match:
                reason = f"shares: shadow={s_shares} live={l_shares} delta={delta_pct:.2%}"
                shares_divs += 1

            if sym in shadow_by_sym and sym in live_by_sym:
                n_common += 1
                total_delta += delta_pct

            decisions.append(ShadowDecision(
                symbol=sym,
                side=s_side,
                shadow_side=s_side,
                shadow_shares=s_shares,
                live_side=l_side,
                live_shares=l_shares,
                side_match=side_match,
                shares_match=shares_match,
                shares_delta_pct=delta_pct,
                shadow_edge=float(sd.get("edge", 0)) if sd.get("edge") is not None else None,
                live_edge=float(ld.get("edge", 0)) if ld.get("edge") is not None else None,
                shadow_price=float(sd.get("price", 0)),
                live_price=float(ld.get("price", 0)),
                divergence_reason=reason,
            ))

        avg_delta = total_delta / max(n_common, 1)

        # Déterminer le statut
        total_divs = side_divs + shares_divs + len(shadow_only) + len(live_only)
        if total_divs == 0:
            status = ShadowRunStatus.CONVERGENT
            summary = "Aucune divergence détectée — shadow == live"
        elif side_divs == 0 and len(shadow_only) == 0 and len(live_only) == 0:
            status = ShadowRunStatus.DIVERGENT
            summary = f"Divergence quantités uniquement: {shares_divs} symbols, delta moyen={avg_delta:.2%}"
        else:
            status = ShadowRunStatus.DIVERGENT
            parts: list[str] = []
            if side_divs > 0:
                parts.append(f"{side_divs} divergences de side")
            if shares_divs > 0:
                parts.append(f"{shares_divs} divergences de quantités")
            if shadow_only:
                parts.append(f"{len(shadow_only)} shadow-only")
            if live_only:
                parts.append(f"{len(live_only)} live-only")
            summary = "; ".join(parts)

        return ShadowComparisonReport(
            shadow_run_id=shadow_run_id,
            live_run_id=live_run_id,
            status=status,
            total_decisions=len(decisions),
            side_divergences=side_divs,
            shares_divergences=shares_divs,
            avg_shares_delta_pct=avg_delta,
            symbols_only_shadow=tuple(shadow_only),
            symbols_only_live=tuple(live_only),
            decisions=tuple(decisions),
            summary=summary,
        )

    def validate_shadow(
        self,
        report: ShadowComparisonReport,
        *,
        max_side_divergence_rate: float = 0.0,
        max_shares_delta_pct: float = 0.05,
    ) -> tuple[bool, str]:
        """Valide si le shadow peut être promu (promotion gate).

        Conditions :
        - Zéro divergence de side
        - Delta de quantité moyen < seuil
        - Aucun symbole shadow-only ou live-only

        Returns
        -------
        (passed, reason)
        """
        if report.side_divergence_rate > max_side_divergence_rate:
            return False, f"side_divergence_rate={report.side_divergence_rate:.2%} > {max_side_divergence_rate:.0%}"
        if report.avg_shares_delta_pct > max_shares_delta_pct:
            return False, f"avg_shares_delta={report.avg_shares_delta_pct:.2%} > {max_shares_delta_pct:.0%}"
        if len(report.symbols_only_shadow) > 0:
            return False, f"{len(report.symbols_only_shadow)} symboles shadow-only"
        if len(report.symbols_only_live) > 0:
            return False, f"{len(report.symbols_only_live)} symboles live-only"
        return True, "shadow_validé"


# ── Helpers ─────────────────────────────────────────────────────────────────


def compare_shadow_to_live(
    shadow_run_id: str,
    live_run_id: str,
    shadow_decisions: list[dict[str, object]],
    live_decisions: list[dict[str, object]],
) -> ShadowComparisonReport:
    """Compare les décisions shadow vs live (fonction pure)."""
    engine = ShadowEngine()
    return engine.compare(shadow_run_id, live_run_id, shadow_decisions=shadow_decisions, live_decisions=live_decisions)
