"""risk_management/liquidity.py — Liquidité, spread, borrow et slippage (Sprint Maître 10).

Garantit que chaque cible est exécutable et liquidable dans les conditions prévues.

Modules :
- ``SpreadSnapshot`` : spread bid-ask PIT avec fraîcheur de quote
- ``BorrowSnapshot`` : disponibilité short PIT (ETB/HTB, locate, fee, quantité)
- ``BorrowStatus`` : classification easy-to-borrow / hard-to-borrow / not-shortable
- ``ParticipationLimit`` : limites de participation ADV à l'entrée et en liquidation
- ``SlippageEstimator`` : estimation pre-trade du slippage (ADV, spread, vol, taille)
- ``LiquidityGate`` : gate combiné liquidité → GO/NO-GO pré-entrée

Usage ::

    from risk_management.liquidity import (
        SpreadSnapshot, BorrowSnapshot, BorrowStatus,
        ParticipationLimit, SlippageEstimator, LiquidityGate,
    )
    gate = LiquidityGate()
    result = gate.evaluate(symbol="AAPL", side="short", notional=10_000,
                           spread=spread_snap, borrow=borrow_snap,
                           adv_usd=50_000_000, atr=5.0)
    if not result.go:
        reject(reason=result.reason)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── BorrowStatus ────────────────────────────────────────────────────────────


class BorrowStatus(StrEnum):
    """Statut de disponibilité d'emprunt pour un short (Sprint Maître 10).

    - EASY_TO_BORROW (ETB) : disponible sans contrainte, fee standard
    - HARD_TO_BORROW (HTB) : disponible avec fee élevée, risque de recall
    - NOT_SHORTABLE : emprunt impossible
    """

    EASY_TO_BORROW = "easy_to_borrow"
    HARD_TO_BORROW = "hard_to_borrow"
    NOT_SHORTABLE = "not_shortable"

    @property
    def is_shortable(self) -> bool:
        return self in (BorrowStatus.EASY_TO_BORROW, BorrowStatus.HARD_TO_BORROW)

    @property
    def requires_locate(self) -> bool:
        """HTB nécessite une confirmation de locate avant l'entrée."""
        return self == BorrowStatus.HARD_TO_BORROW

    @property
    def fee_multiplier(self) -> float:
        """Multiplicateur de fee par rapport au taux standard."""
        return {
            BorrowStatus.EASY_TO_BORROW: 1.0,
            BorrowStatus.HARD_TO_BORROW: 5.0,
            BorrowStatus.NOT_SHORTABLE: float("inf"),
        }[self]


# ── SpreadSnapshot ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SpreadSnapshot:
    """Snapshot PIT du spread bid-ask (Sprint Maître 10).

    Attributes
    ----------
    symbol : str
    bid : float | None
        Meilleur prix bid.
    ask : float | None
        Meilleur prix ask.
    spread_bps : float | None
        Spread en bps (basis points). None si indisponible.
    quote_time : datetime | None
        Horodatage de la quote.
    max_age_seconds : float
        Âge maximum acceptable pour la quote (défaut 300s = 5min).
    source : str
        Source de la quote (ex: "iex", "consolidated", "alpaca").
    """

    symbol: str
    bid: float | None = None
    ask: float | None = None
    spread_bps: float | None = None
    quote_time: datetime | None = None
    max_age_seconds: float = 300.0
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.bid is not None and self.ask is not None and self.bid >= self.ask:
            raise ValueError(
                f"bid ({self.bid}) doit être < ask ({self.ask}) pour {self.symbol}"
            )

    @property
    def is_available(self) -> bool:
        """True si le spread est disponible et exploitable."""
        return (
            self.bid is not None
            and self.ask is not None
            and self.bid > 0
            and self.ask > 0
            and self.bid < self.ask
        )

    @property
    def is_stale(self) -> bool:
        """True si la quote est trop ancienne."""
        if self.quote_time is None:
            return True
        now = (
            datetime.now(self.quote_time.tzinfo)
            if self.quote_time.tzinfo is not None
            else datetime.now()
        )
        age = (now - self.quote_time).total_seconds()
        return age > self.max_age_seconds

    @property
    def mid_price(self) -> float | None:
        """Prix mid (bid+ask)/2."""
        if self.is_available:
            return (self.bid + self.ask) / 2.0  # type: ignore[operator]
        return None

    @property
    def effective_spread_bps(self) -> float | None:
        """Spread effectif en bps : (ask-bid)/mid * 10000."""
        if self.spread_bps is not None:
            return self.spread_bps
        if self.is_available:
            mid = self.mid_price
            if mid and mid > 0:
                return (self.ask - self.bid) / mid * 10000.0  # type: ignore[operator]
        return None


# ── BorrowSnapshot ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BorrowSnapshot:
    """Snapshot PIT de disponibilité d'emprunt pour short (Sprint Maître 10).

    Attributes
    ----------
    symbol : str
    status : BorrowStatus
        Statut de disponibilité (ETB/HTB/NOT_SHORTABLE).
    fee_annual : float | None
        Taux d'emprunt annualisé (ex: 0.003 = 0.3%/an, 0.05 = 5%/an pour HTB).
    quantity_available : int | None
        Nombre de titres empruntables.
    locate_required : bool
        True si un locate doit être confirmé avant l'entrée.
    locate_confirmed : bool
        True si le locate a été confirmé.
    locate_deadline : datetime | None
        Date limite du locate.
    recall_risk : float
        Probabilité estimée de recall (0-1). 0.0 = pas de risque, 1.0 = certain.
    as_of : datetime | None
        Horodatage de l'information.
    source : str
        Source des données (ex: "alpaca", "ibkr", "manual").
    """

    symbol: str
    status: BorrowStatus = BorrowStatus.EASY_TO_BORROW
    fee_annual: float | None = 0.003
    quantity_available: int | None = None
    locate_required: bool = False
    locate_confirmed: bool = False
    locate_deadline: datetime | None = None
    recall_risk: float = 0.0
    as_of: datetime | None = None
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.status == BorrowStatus.NOT_SHORTABLE:
            if self.fee_annual is not None and self.fee_annual != float("inf"):
                object.__setattr__(self, "fee_annual", float("inf"))
            object.__setattr__(self, "quantity_available", 0)
            object.__setattr__(self, "locate_required", False)
        if self.status == BorrowStatus.HARD_TO_BORROW:
            object.__setattr__(self, "locate_required", True)
        if not (0.0 <= self.recall_risk <= 1.0):
            raise ValueError(f"recall_risk doit être dans [0, 1] : {self.recall_risk}")

    @property
    def is_shortable(self) -> bool:
        """True si le titre peut être shorté."""
        return self.status.is_shortable

    @property
    def is_htb_blocked(self) -> bool:
        """True si HTB sans locate confirmé → entrée bloquée."""
        return (
            self.status == BorrowStatus.HARD_TO_BORROW
            and self.locate_required
            and not self.locate_confirmed
        )

    @property
    def effective_fee_annual(self) -> float:
        """Fee annual effective (float('inf') si non shortable)."""
        if self.fee_annual is not None:
            return self.fee_annual
        if self.status == BorrowStatus.NOT_SHORTABLE:
            return float("inf")
        return 0.003  # défaut standard

    def edge_cost_for_holding(self, holding_days: int = 10) -> float:
        """Coût d'emprunt en % pour une durée de détention donnée."""
        if not self.is_shortable:
            return float("inf")
        fee = self.effective_fee_annual
        if fee == float("inf"):
            return float("inf")
        return fee * (holding_days / 252.0)


# ── ParticipationLimit ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParticipationLimit:
    """Limites de participation ADV (Sprint Maître 10).

    Définit la fraction maximale de l'ADV qu'une position peut représenter,
    à l'entrée et en liquidation stressée.

    Attributes
    ----------
    max_pct_of_adv_entry : float
        Fraction max de l'ADV à l'entrée (ex: 0.01 = 1%).
    max_pct_of_adv_liquidation : float
        Fraction max de l'ADV en liquidation stressée (plus conservateur).
    max_notional_absolute : float | None
        Plafond absolu de notional (indépendant de l'ADV).
    min_adv_for_entry : float | None
        ADV minimum pour autoriser une entrée (ex: 1_000_000 = $1M/jour).
    """

    max_pct_of_adv_entry: float = 0.01
    max_pct_of_adv_liquidation: float = 0.005
    max_notional_absolute: float | None = None
    min_adv_for_entry: float | None = 1_000_000.0

    def __post_init__(self) -> None:
        if not (0 < self.max_pct_of_adv_entry <= 1):
            raise ValueError(
                f"max_pct_of_adv_entry doit être dans ]0, 1] : {self.max_pct_of_adv_entry}"
            )
        if not (0 < self.max_pct_of_adv_liquidation <= 1):
            raise ValueError(
                f"max_pct_of_adv_liquidation doit être dans ]0, 1] : {self.max_pct_of_adv_liquidation}"
            )

    def max_notional_entry(self, adv_usd: float) -> float:
        """Notional maximum à l'entrée basé sur l'ADV."""
        if adv_usd <= 0:
            return 0.0
        return adv_usd * self.max_pct_of_adv_entry

    def max_notional_liquidation(self, adv_usd: float) -> float:
        """Notional maximum en liquidation stressée basé sur l'ADV."""
        if adv_usd <= 0:
            return 0.0
        return adv_usd * self.max_pct_of_adv_liquidation

    def check_entry(self, notional: float, adv_usd: float) -> tuple[bool, str | None]:
        """Vérifie si un notional d'entrée respecte les limites.

        Returns
        -------
        (ok, reason) — ok=True si acceptable, sinon reason explique le rejet.
        """
        if self.min_adv_for_entry is not None and adv_usd < self.min_adv_for_entry:
            return False, f"adv_usd={adv_usd:.0f} < min_adv={self.min_adv_for_entry:.0f}"
        if adv_usd <= 0:
            return False, "adv_usd indisponible ou nul"
        if notional > self.max_notional_entry(adv_usd):
            return False, (
                f"notional={notional:.0f} > max_entry={self.max_notional_entry(adv_usd):.0f} "
                f"({self.max_pct_of_adv_entry*100:.1f}% ADV)"
            )
        if self.max_notional_absolute is not None and notional > self.max_notional_absolute:
            return False, f"notional={notional:.0f} > max_absolute={self.max_notional_absolute:.0f}"
        return True, None

    def check_liquidation(self, notional: float, adv_usd: float) -> tuple[bool, str | None]:
        """Vérifie si un notional peut être liquidé sans impact excessif."""
        if adv_usd <= 0:
            return False, "adv_usd indisponible pour liquidation"
        if notional > self.max_notional_liquidation(adv_usd):
            return False, (
                f"notional={notional:.0f} > max_liquidation="
                f"{self.max_notional_liquidation(adv_usd):.0f}"
            )
        return True, None


# ── SlippageEstimator ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SlippageEstimate:
    """Estimation pre-trade du slippage (Sprint Maître 10).

    Attributes
    ----------
    symbol : str
    total_slippage_bps : float
        Slippage total estimé en bps.
    spread_component_bps : float
        Composante spread (half-spread).
    impact_component_bps : float
        Composante impact de marché (Almgren-Chriss simplifié).
    volatility_component_bps : float
        Composante volatilité (adverse selection).
    is_stressed : bool
        True si l'estimation est en mode stressé (liquidation).
    """

    symbol: str
    total_slippage_bps: float = 0.0
    spread_component_bps: float = 0.0
    impact_component_bps: float = 0.0
    volatility_component_bps: float = 0.0
    is_stressed: bool = False

    @property
    def total_slippage_pct(self) -> float:
        return self.total_slippage_bps / 10000.0


@dataclass
class SlippageEstimator:
    """Estimateur de slippage pre-trade (Sprint Maître 10).

    Modèle simplifié Almgren-Chriss :
    - Composante spread : half-spread (bid-ask/2)
    - Composante impact : sqrt(participation_adv) × impact_factor
    - Composante volatilité : σ_daily × holding_risk_factor
    - Mode stressé : facteur multiplicateur sur toutes les composantes

    Parameters
    ----------
    impact_factor : float
        Facteur d'impact de marché (défaut 0.1 = 10% du sqrt).
    volatility_factor : float
        Facteur de volatilité pour adverse selection (défaut 0.5).
    stress_multiplier : float
        Multiplicateur en mode liquidation stressée (défaut 3.0).
    """

    impact_factor: float = 0.1
    volatility_factor: float = 0.5
    stress_multiplier: float = 3.0

    def estimate(
        self,
        symbol: str,
        *,
        notional: float,
        adv_usd: float,
        spread_bps: float | None = None,
        daily_vol_pct: float | None = None,
        is_stressed: bool = False,
    ) -> SlippageEstimate:
        """Estime le slippage total pour une transaction.

        Parameters
        ----------
        symbol : str
        notional : float
            Taille de la transaction en dollars.
        adv_usd : float
            Volume quotidien moyen en dollars.
        spread_bps : float | None
            Spread bid-ask en bps. Si None, estimé à 5 bps par défaut.
        daily_vol_pct : float | None
            Volatilité quotidienne en %. Si None, estimée à 2% par défaut.
        is_stressed : bool
            True pour une estimation en mode liquidation stressée.

        Returns
        -------
        SlippageEstimate
        """
        if adv_usd <= 0 or notional <= 0:
            return SlippageEstimate(symbol=symbol)

        # ── Participation ───────────────────────────────────────────────
        participation = notional / adv_usd

        # ── Composante spread (half-spread) ─────────────────────────────
        effective_spread = spread_bps if spread_bps is not None else 5.0
        spread_component = effective_spread / 2.0  # half-spread

        # ── Composante impact (sqrt Almgren-Chriss simplifié) ───────────
        impact_component = self.impact_factor * math.sqrt(participation) * 10000.0

        # ── Composante volatilité ───────────────────────────────────────
        vol = daily_vol_pct if daily_vol_pct is not None else 2.0
        volatility_component = self.volatility_factor * vol * math.sqrt(participation) * 100.0

        total = spread_component + impact_component + volatility_component

        if is_stressed:
            total *= self.stress_multiplier
            spread_component *= self.stress_multiplier
            impact_component *= self.stress_multiplier
            volatility_component *= self.stress_multiplier

        return SlippageEstimate(
            symbol=symbol,
            total_slippage_bps=total,
            spread_component_bps=spread_component,
            impact_component_bps=impact_component,
            volatility_component_bps=volatility_component,
            is_stressed=is_stressed,
        )

    def estimate_stressed(
        self,
        symbol: str,
        *,
        notional: float,
        adv_usd: float,
        spread_bps: float | None = None,
        daily_vol_pct: float | None = None,
    ) -> SlippageEstimate:
        """Raccourci pour estimation en mode liquidation stressée."""
        return self.estimate(
            symbol=symbol,
            notional=notional,
            adv_usd=adv_usd,
            spread_bps=spread_bps,
            daily_vol_pct=daily_vol_pct,
            is_stressed=True,
        )


# ── LiquidityGate ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LiquidityGateResult:
    """Résultat du gate de liquidité (Sprint Maître 10).

    Attributes
    ----------
    go : bool
        True si toutes les conditions de liquidité sont remplies.
    reason : str
        Raison du GO ou du NO-GO.
    spread_ok : bool
        Spread acceptable.
    borrow_ok : bool
        Emprunt disponible (pour shorts).
    adv_ok : bool
        ADV suffisant pour la taille demandée.
    participation_pct : float | None
        Participation estimée en % de l'ADV.
    estimated_slippage_bps : float | None
        Slippage estimé en bps.
    """

    go: bool
    reason: str = ""
    spread_ok: bool = True
    borrow_ok: bool = True
    adv_ok: bool = True
    participation_pct: float | None = None
    estimated_slippage_bps: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "go": self.go,
            "reason": self.reason,
            "spread_ok": self.spread_ok,
            "borrow_ok": self.borrow_ok,
            "adv_ok": self.adv_ok,
            "participation_pct": (
                round(self.participation_pct, 6) if self.participation_pct is not None else None
            ),
            "estimated_slippage_bps": (
                round(self.estimated_slippage_bps, 2) if self.estimated_slippage_bps is not None else None
            ),
        }


@dataclass
class LiquidityGate:
    """Gate de liquidité pré-entrée (Sprint Maître 10).

    Combine spread, borrow, ADV et slippage en une décision GO/NO-GO.
    Si le gate est NO-GO, l'entrée est bloquée AVANT le sizing.

    Parameters
    ----------
    participation_limit : ParticipationLimit
        Limites de participation ADV.
    slippage_estimator : SlippageEstimator
        Estimateur de slippage.
    max_spread_bps : float | None
        Spread maximum acceptable (None = pas de limite).
    require_fresh_quote : bool
        Si True, exige une quote non stale.
    max_slippage_bps : float | None
        Slippage total maximum acceptable (None = pas de limite).
    block_htb_without_locate : bool
        Si True, bloque les shorts HTB sans locate confirmé.
    """

    participation_limit: ParticipationLimit = field(default_factory=ParticipationLimit)
    slippage_estimator: SlippageEstimator = field(default_factory=SlippageEstimator)
    max_spread_bps: float | None = 50.0
    require_fresh_quote: bool = True
    max_slippage_bps: float | None = 200.0  # 2% max slippage
    block_htb_without_locate: bool = True

    def evaluate(
        self,
        symbol: str,
        side: str,
        notional: float,
        *,
        spread: SpreadSnapshot | None = None,
        borrow: BorrowSnapshot | None = None,
        adv_usd: float | None = None,
        daily_vol_pct: float | None = None,
    ) -> LiquidityGateResult:
        """Évalue toutes les conditions de liquidité.

        Parameters
        ----------
        symbol : str
        side : str
            "long" ou "short".
        notional : float
            Taille visée en dollars.
        spread : SpreadSnapshot | None
            Snapshot de spread.
        borrow : BorrowSnapshot | None
            Snapshot d'emprunt (obligatoire pour les shorts).
        adv_usd : float | None
            ADV 20j en dollars.
        daily_vol_pct : float | None
            Volatilité quotidienne en %.

        Returns
        -------
        LiquidityGateResult
        """
        reasons: list[str] = []
        spread_ok = True
        borrow_ok = True
        adv_ok = True

        # ── 1. Spread ──────────────────────────────────────────────────
        if spread is None:
            if self.require_fresh_quote:
                spread_ok = False
                reasons.append("quote_snapshot_manquant")
        else:
            if not spread.is_available:
                spread_ok = False
                reasons.append("spread_indisponible")
            elif self.require_fresh_quote and spread.is_stale:
                spread_ok = False
                reasons.append(f"quote_stale (>{spread.max_age_seconds:.0f}s)")
            elif (
                self.max_spread_bps is not None
                and spread.effective_spread_bps is not None
                and spread.effective_spread_bps > self.max_spread_bps
            ):
                spread_ok = False
                reasons.append(
                    f"spread={spread.effective_spread_bps:.1f}bps > max={self.max_spread_bps}bps"
                )

        # ── 2. Borrow (shorts uniquement) ───────────────────────────────
        is_short = side == "short"
        if is_short:
            if borrow is None:
                borrow_ok = False
                reasons.append("borrow_snapshot_manquant")
            elif not borrow.is_shortable:
                borrow_ok = False
                reasons.append(f"not_shortable ({borrow.status.value})")
            elif self.block_htb_without_locate and borrow.is_htb_blocked:
                borrow_ok = False
                reasons.append("HTB_sans_locate_confirme")

        # ── 3. ADV / Participation ──────────────────────────────────────
        participation_pct = None
        estimated_slippage_bps = None

        if adv_usd is not None and adv_usd > 0 and notional > 0:
            participation_pct = notional / adv_usd

            ok, reason = self.participation_limit.check_entry(notional, adv_usd)
            if not ok:
                adv_ok = False
                reasons.append(reason or "participation_excessive")

            # Estimer le slippage
            spread_bps = (
                spread.effective_spread_bps if spread and spread.is_available else None
            )
            slippage = self.slippage_estimator.estimate(
                symbol=symbol,
                notional=notional,
                adv_usd=adv_usd,
                spread_bps=spread_bps,
                daily_vol_pct=daily_vol_pct,
            )
            estimated_slippage_bps = slippage.total_slippage_bps

            if (
                self.max_slippage_bps is not None
                and estimated_slippage_bps > self.max_slippage_bps
            ):
                adv_ok = False
                reasons.append(
                    f"slippage_estime={estimated_slippage_bps:.1f}bps > max={self.max_slippage_bps}bps"
                )

        elif adv_usd is None or adv_usd <= 0:
            adv_ok = False
            reasons.append("adv_indisponible")

        # ── Synthèse ───────────────────────────────────────────────────
        if reasons:
            return LiquidityGateResult(
                go=False,
                reason="; ".join(reasons),
                spread_ok=spread_ok,
                borrow_ok=borrow_ok,
                adv_ok=adv_ok,
                participation_pct=participation_pct,
                estimated_slippage_bps=estimated_slippage_bps,
            )

        return LiquidityGateResult(
            go=True,
            reason="liquidite_ok",
            spread_ok=spread_ok,
            borrow_ok=borrow_ok,
            adv_ok=adv_ok,
            participation_pct=participation_pct,
            estimated_slippage_bps=estimated_slippage_bps,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_liquidity_pre_entry(
    symbol: str,
    side: str,
    notional: float,
    *,
    adv_usd: float | None = None,
    spread_bps: float | None = None,
    borrow_status: str | None = None,
) -> LiquidityGateResult:
    """Évalue rapidement la liquidité pré-entrée.

    Fonction pure utilisable comme veto dans un pipeline.
    """
    gate = LiquidityGate()

    spread = None
    if spread_bps is not None:
        mid = 100.0  # prix arbitraire pour reconstruire bid/ask
        half_spread = spread_bps / 10000.0 * mid / 2.0
        spread = SpreadSnapshot(
            symbol=symbol,
            bid=mid - half_spread,
            ask=mid + half_spread,
            spread_bps=spread_bps,
            quote_time=datetime.now(),
        )

    borrow = None
    if side == "short" and borrow_status is not None:
        status = BorrowStatus(borrow_status)
        borrow = BorrowSnapshot(symbol=symbol, status=status)

    return gate.evaluate(
        symbol=symbol,
        side=side,
        notional=notional,
        spread=spread,
        borrow=borrow,
        adv_usd=adv_usd,
    )


# ── PreSubmissionGate (Point 9.6) ───────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PreSubmissionResult:
    """Résultat de la réévaluation liquidité/borrow juste avant soumission broker.

    Point 9.6 — Ce DTO capture le verdict de la vérification pré-soumission :
    le spread, le borrow et l'ADV sont-ils toujours valides au moment de
    soumettre l'ordre au broker ?

    Attributes
    ----------
    go : bool
        True si l'ordre peut être soumis.
    reason : str
        Raison explicite du GO ou NO-GO.
    intent_id : str | None
        Identifiant de l'intent vérifié.
    symbol : str
        Symbole concerné.
    side : str
        "long" ou "short".
    liquidity_result : LiquidityGateResult | None
        Résultat détaillé du LiquidityGate sous-jacent.
    checked_at : datetime
        Horodatage de la vérification.
    spread_stale : bool
        True si la quote était stale au moment de la vérification.
    borrow_changed : bool
        True si le statut borrow a changé depuis la décision de risque
        (ex: ETB → HTB ou HTB → NOT_SHORTABLE).
    """

    go: bool
    reason: str = ""
    intent_id: str | None = None
    symbol: str = ""
    side: str = ""
    liquidity_result: LiquidityGateResult | None = None
    checked_at: datetime | None = None
    spread_stale: bool = False
    borrow_changed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "go": self.go,
            "reason": self.reason,
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": self.side,
            "liquidity_result": self.liquidity_result.to_dict() if self.liquidity_result else None,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "spread_stale": self.spread_stale,
            "borrow_changed": self.borrow_changed,
        }


@dataclass
class PreSubmissionGate:
    """Gate de réévaluation liquidité/borrow juste avant soumission broker.

    Point 9.6 — Ce gate est appelé **après** la décision de risque mais
    **avant** l'envoi de l'ordre au broker. Il revérifie que les conditions
    de marché n'ont pas changé défavorablement entre la décision et la
    soumission.

    Si le spread s'est élargi, le borrow est devenu indisponible, ou l'ADV
    est insuffisant, l'ordre est bloqué (NO-GO) avec une raison explicite.

    Parameters
    ----------
    liquidity_gate : LiquidityGate
        Le gate de liquidité sous-jacent.
    require_fresh_quote : bool
        Si True, exige une quote non stale (moins de max_quote_age_seconds).
        Défaut : True (plus strict que le LiquidityGate de décision).
    max_quote_age_seconds : float
        Âge max de la quote pour la réévaluation pré-soumission.
        Défaut : 30s (beaucoup plus strict que les ~5min de la décision).
    fail_closed_on_missing_data : bool
        Si True, bloque l'ordre si les données nécessaires sont absentes.
        Défaut : True (principe de précaution).
    """

    liquidity_gate: LiquidityGate = field(default_factory=LiquidityGate)
    require_fresh_quote: bool = True
    max_quote_age_seconds: float = 30.0
    fail_closed_on_missing_data: bool = True

    def evaluate(
        self,
        symbol: str,
        side: str,
        notional: float,
        *,
        spread: SpreadSnapshot | None = None,
        borrow: BorrowSnapshot | None = None,
        adv_usd: float | None = None,
        daily_vol_pct: float | None = None,
        intent_id: str | None = None,
        previous_borrow: BorrowSnapshot | None = None,
    ) -> PreSubmissionResult:
        """Réévalue les conditions de liquidité juste avant soumission.

        Parameters
        ----------
        symbol : str
        side : str
            "long" ou "short".
        notional : float
            Taille visée en dollars.
        spread : SpreadSnapshot | None
            Quote fraîche (doit avoir moins de ``max_quote_age_seconds``).
        borrow : BorrowSnapshot | None
            Statut borrow actuel.
        adv_usd : float | None
            ADV 20j en dollars.
        daily_vol_pct : float | None
            Volatilité quotidienne en %.
        intent_id : str | None
            Identifiant de l'intent pour traçabilité.
        previous_borrow : BorrowSnapshot | None
            Statut borrow au moment de la décision de risque, pour détecter
            un changement défavorable.

        Returns
        -------
        PreSubmissionResult
        """
        from datetime import datetime as _dt, timezone as _tz

        checked_at = _dt.now(_tz.utc)
        spread_stale = False
        borrow_changed = False

        # ── Vérification fraîcheur de la quote ─────────────────────
        if spread is not None and self.require_fresh_quote:
            if spread.quote_time is not None:
                quote_dt = spread.quote_time
                if quote_dt.tzinfo is None:
                    # Assume UTC si naive (rétrocompatibilité)
                    from datetime import timezone as _tz_mod
                    quote_dt = quote_dt.replace(tzinfo=_tz_mod.utc)
                age = (checked_at - quote_dt).total_seconds()
                if age > self.max_quote_age_seconds:
                    spread_stale = True
                    return PreSubmissionResult(
                        go=False,
                        reason=f"quote_stale_pre_soumission ({age:.0f}s > {self.max_quote_age_seconds:.0f}s)",
                        intent_id=intent_id,
                        symbol=symbol,
                        side=side,
                        checked_at=checked_at,
                        spread_stale=True,
                        borrow_changed=borrow_changed,
                    )

        # ── Détection changement borrow ────────────────────────────
        if (
            previous_borrow is not None
            and borrow is not None
            and borrow.status != previous_borrow.status
        ):
            borrow_changed = True
            # Si la situation s'est dégradée, on bloque
            if _borrow_degraded(previous_borrow.status, borrow.status):
                return PreSubmissionResult(
                    go=False,
                    reason=(
                        f"borrow_degrade: {previous_borrow.status.value} → "
                        f"{borrow.status.value}"
                    ),
                    intent_id=intent_id,
                    symbol=symbol,
                    side=side,
                    checked_at=checked_at,
                    spread_stale=spread_stale,
                    borrow_changed=True,
                )

        # ── Délégation au LiquidityGate ────────────────────────────
        pre_gate = LiquidityGate(
            participation_limit=self.liquidity_gate.participation_limit,
            slippage_estimator=self.liquidity_gate.slippage_estimator,
            max_spread_bps=self.liquidity_gate.max_spread_bps,
            require_fresh_quote=self.fail_closed_on_missing_data,
            max_slippage_bps=self.liquidity_gate.max_slippage_bps,
            block_htb_without_locate=self.liquidity_gate.block_htb_without_locate,
        )

        # ── Gestion données manquantes ─────────────────────────────
        is_short = side == "short"
        if self.fail_closed_on_missing_data:
            if spread is None:
                return PreSubmissionResult(
                    go=False,
                    reason="spread_indisponible_pre_soumission",
                    intent_id=intent_id,
                    symbol=symbol,
                    side=side,
                    checked_at=checked_at,
                    spread_stale=True,
                )
            if is_short and borrow is None:
                return PreSubmissionResult(
                    go=False,
                    reason="borrow_indisponible_pre_soumission",
                    intent_id=intent_id,
                    symbol=symbol,
                    side=side,
                    checked_at=checked_at,
                )

        liquidity_result = pre_gate.evaluate(
            symbol=symbol,
            side=side,
            notional=notional,
            spread=spread,
            borrow=borrow if is_short else None,
            adv_usd=adv_usd,
            daily_vol_pct=daily_vol_pct,
        )

        return PreSubmissionResult(
            go=liquidity_result.go,
            reason=liquidity_result.reason,
            intent_id=intent_id,
            symbol=symbol,
            side=side,
            liquidity_result=liquidity_result,
            checked_at=checked_at,
            spread_stale=spread_stale,
            borrow_changed=borrow_changed,
        )


def _borrow_degraded(old: BorrowStatus, new: BorrowStatus) -> bool:
    """True si le statut borrow s'est dégradé (ETB→HTB, ETB→NOT_SHORTABLE, HTB→NOT_SHORTABLE)."""
    severity = {
        BorrowStatus.EASY_TO_BORROW: 0,
        BorrowStatus.HARD_TO_BORROW: 1,
        BorrowStatus.NOT_SHORTABLE: 2,
    }
    return severity.get(new, 0) > severity.get(old, 0)


def check_pre_submission(
    symbol: str,
    side: str,
    notional: float,
    *,
    spread: SpreadSnapshot | None = None,
    borrow: BorrowSnapshot | None = None,
    adv_usd: float | None = None,
    daily_vol_pct: float | None = None,
    intent_id: str | None = None,
    previous_borrow: BorrowSnapshot | None = None,
) -> PreSubmissionResult:
    """Réévalue la liquidité/borrow juste avant soumission broker (Point 9.6).

    Helper pur utilisable comme veto dans la boucle de soumission de l'executor.
    Utilise un ``PreSubmissionGate`` avec les réglages par défaut (quote < 30s,
    fail-closed si données manquantes).

    Parameters
    ----------
    symbol : str
    side : str
        "long" ou "short".
    notional : float
        Taille visée en dollars.
    spread : SpreadSnapshot | None
        Quote fraîche bid/ask.
    borrow : BorrowSnapshot | None
        Statut borrow actuel.
    adv_usd : float | None
        ADV 20j en dollars.
    daily_vol_pct : float | None
        Volatilité quotidienne en %.
    intent_id : str | None
        Identifiant de l'intent pour traçabilité.
    previous_borrow : BorrowSnapshot | None
        Statut borrow au moment de la décision de risque.

    Returns
    -------
    PreSubmissionResult
    """
    gate = PreSubmissionGate()
    return gate.evaluate(
        symbol=symbol,
        side=side,
        notional=notional,
        spread=spread,
        borrow=borrow,
        adv_usd=adv_usd,
        daily_vol_pct=daily_vol_pct,
        intent_id=intent_id,
        previous_borrow=previous_borrow,
    )
