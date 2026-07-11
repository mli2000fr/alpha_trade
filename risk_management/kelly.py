"""Kelly sizer V3 — directionnel, shrinkage, fallback explicite (Sprint Maître 8)."""
from __future__ import annotations

import logging
import math

from risk_management.config import RiskConfig
from risk_management.enums import KellyFallback, SizingMethod
from risk_management.models import DirectionalWinRateInfo, PriceInfo, SizingResult
from risk_management.position_sizer import PositionSizer

LOGGER = logging.getLogger(__name__)


class KellySizer:
    """Sizing Kelly fractionnel directionnel avec cap ATR (Sprint Maître 8).

    Changements par rapport à V2 :
    - Utilise ``DirectionalWinRateInfo`` (hit rate + payoff directionnels)
      au lieu d'une accuracy générique.
    - Shrinkage bayésien sur faible échantillon (trade_count < min_trades).
    - Fallback explicite via ``KellyFallback`` (reject par défaut).
    - Le payoff n'est plus un paramètre global config, il vient du modèle.
    """

    def __init__(self, config: RiskConfig) -> None:
        self._cfg = config
        self._fallback = PositionSizer(config)

    def compute(
        self,
        price_info: PriceInfo,
        predicted_proba: float | None = None,
        historical_win_rate: float | None = None,
        *,
        directional_stats: DirectionalWinRateInfo | None = None,
        fallback: KellyFallback = KellyFallback.REJECT,
    ) -> SizingResult:
        """Calcule la taille de position via Kelly directionnel + cap ATR.

        Parameters
        ----------
        price_info : PriceInfo
        predicted_proba : float | None
            Probabilité calibrée du modèle (p_side).
        historical_win_rate : float | None
            Win rate historique (rétrocompatibilité, ignoré si directional_stats fourni).
        directional_stats : DirectionalWinRateInfo | None
            Statistiques directionnelles OOS (hit rate + payoff par side).
        fallback : KellyFallback
            Stratégie de repli si Kelly échoue (reject par défaut).

        Returns
        -------
        SizingResult
        """
        cfg = self._cfg
        symbol = price_info.symbol
        price = price_info.last_close

        if price <= 0:
            return SizingResult(
                symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_INVALID_PRICE
            )

        # ── 1. Probabilité effective ────────────────────────────────────
        pp = predicted_proba if predicted_proba is not None else cfg.default_win_rate
        wr = historical_win_rate if historical_win_rate is not None else cfg.default_win_rate
        p_eff = cfg.prediction_confidence_weight * pp + cfg.historical_win_rate_weight * wr
        p_eff = max(0.001, min(p_eff, 0.999))

        # ── 1b. Payoff directionnel ─────────────────────────────────────
        if directional_stats is not None:
            hit_rate = directional_stats.hit_rate
            payoff = directional_stats.payoff
            trade_count = directional_stats.trade_count
            # Shrinkage bayésien sur petit échantillon
            if trade_count < self._min_trades_for_full_kelly:
                hit_rate, payoff = self._apply_shrinkage(hit_rate, payoff, trade_count)
        else:
            hit_rate = p_eff
            payoff = cfg.assumed_payoff_ratio

        # ── 2. Seuil de probabilité effective ───────────────────────────
        if p_eff < cfg.min_effective_probability:
            LOGGER.info("p_eff=%.4f < seuil pour %s — fallback=%s.", p_eff, symbol, fallback.value)
            return self._handle_fallback(price_info, fallback)

        # ── 3. Kelly directionnel ───────────────────────────────────────
        q = 1.0 - hit_rate
        # Kelly classique: f* = p - q/b  avec b = payoff (avg_gain / avg_loss)
        raw_kelly = hit_rate - q / payoff
        fractional_kelly = max(0.0, raw_kelly) * cfg.kelly_fraction_multiplier
        fractional_kelly = min(fractional_kelly, cfg.max_kelly_fraction)
        fractional_kelly = min(fractional_kelly, cfg.max_position_weight)

        # ── 4. Kelly <= 0 → fallback ────────────────────────────────────
        if fractional_kelly <= 0:
            LOGGER.info(
                "Kelly <= 0 pour %s (hit_rate=%.4f payoff=%.2f) — fallback=%s.",
                symbol, hit_rate, payoff, fallback.value,
            )
            return self._handle_fallback(price_info, fallback)

        # ── 5. Shares Kelly ─────────────────────────────────────────────
        kelly_notional = cfg.account_equity * fractional_kelly
        kelly_shares = math.floor(kelly_notional / price)

        # ── 6. Cap ATR ──────────────────────────────────────────────────
        if price_info.atr_20 is not None and price_info.atr_20 > 0:
            risk_budget = (
                cfg.account_equity * cfg.risk_per_trade_pct * max(0.0, cfg.risk_multiplier)
            )
            risk_per_share = price_info.atr_20 * cfg.atr_stop_multiple
            if risk_per_share > 0:
                atr_shares_cap = math.floor(risk_budget / risk_per_share)
            else:
                atr_shares_cap = 0
            proposed = min(kelly_shares, atr_shares_cap)
            method = SizingMethod.KELLY_ATR
        else:
            proposed = kelly_shares
            method = SizingMethod.KELLY_ONLY

        proposed = max(proposed, 0)

        # ── 7. Notional minimum ─────────────────────────────────────────
        min_notional = cfg.effective_min_notional
        if proposed * price < min_notional:
            LOGGER.info("Notional Kelly insuffisant pour %s — rejet.", symbol)
            method_rej = (
                SizingMethod.REJECTED_NOTIONAL_BELOW_ENFORCED
                if cfg.enforce_min_notional is not None
                else SizingMethod.REJECTED_NOTIONAL
            )
            return SizingResult(symbol=symbol, proposed_shares=0, method=method_rej)

        if proposed < 1:
            return SizingResult(
                symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_ZERO_SHARES
            )

        return SizingResult(symbol=symbol, proposed_shares=proposed, method=method)

    # ── Méthodes privées ────────────────────────────────────────────────────

    @property
    def _min_trades_for_full_kelly(self) -> int:
        """Seuil en-dessous duquel un shrinkage bayésien est appliqué."""
        return 30

    @staticmethod
    def _apply_shrinkage(
        hit_rate: float,
        payoff: float,
        trade_count: int,
    ) -> tuple[float, float]:
        """Shrinkage bayésien vers un prior non informatif.

        prior_hit_rate = 0.50 (pile/face)
        prior_payoff = 1.0 (breakeven)
        prior_strength = 5 (poids du prior en trades équivalents)
        """
        prior_hit_rate = 0.50
        prior_payoff = 1.0
        prior_strength = 5.0

        w_data = trade_count / (trade_count + prior_strength)
        w_prior = 1.0 - w_data

        shrunk_hit_rate = w_data * hit_rate + w_prior * prior_hit_rate
        shrunk_payoff = w_data * payoff + w_prior * prior_payoff

        LOGGER.debug(
            "Shrinkage Kelly: hit_rate %.3f→%.3f payoff %.2f→%.2f (n=%d)",
            hit_rate, shrunk_hit_rate, payoff, shrunk_payoff, trade_count,
        )
        return shrunk_hit_rate, shrunk_payoff

    def _handle_fallback(
        self,
        price_info: PriceInfo,
        fallback: KellyFallback,
    ) -> SizingResult:
        """Applique la stratégie de fallback configurée."""
        if fallback == KellyFallback.REJECT:
            return SizingResult(
                symbol=price_info.symbol,
                proposed_shares=0,
                method=SizingMethod.REJECTED_ZERO_SHARES,
            )
        elif fallback == KellyFallback.MINIMAL_PROBE:
            # 1 share pour explorer le trade
            return SizingResult(
                symbol=price_info.symbol,
                proposed_shares=1.0,
                method=SizingMethod.ATR,
            )
        elif fallback == KellyFallback.ATR_FALLBACK:
            return self._fallback.compute(price_info)
        else:
            LOGGER.warning("Fallback inconnu: %s — rejet.", fallback)
            return SizingResult(
                symbol=price_info.symbol,
                proposed_shares=0,
                method=SizingMethod.REJECTED_ZERO_SHARES,
            )


# ── Helpers ─────────────────────────────────────────────────────────────────


def compute_kelly_fraction(
    hit_rate: float,
    payoff: float,
    *,
    kelly_multiplier: float = 0.25,
    max_fraction: float = 0.25,
    min_trades: int = 30,
    trade_count: int = 0,
) -> float:
    """Calcule la fraction Kelly fractionnelle (fonction pure, sans config).

    Parameters
    ----------
    hit_rate : float
        Taux de trades gagnants (0-1).
    payoff : float
        Ratio gain moyen / perte moyenne.
    kelly_multiplier : float
        Multiplicateur de sécurité sur le Kelly brut.
    max_fraction : float
        Plafond absolu de la fraction.
    min_trades : int
        Seuil de shrinkage.
    trade_count : int
        Nombre de trades OOS (pour shrinkage).

    Returns
    -------
    float
        Fraction Kelly (0.0 si Kelly ≤ 0).
    """
    if trade_count > 0 and trade_count < min_trades:
        hit_rate, payoff = KellySizer._apply_shrinkage(hit_rate, payoff, trade_count)

    if payoff <= 0 or hit_rate <= 0 or hit_rate >= 1.0:
        return 0.0

    q = 1.0 - hit_rate
    raw_kelly = hit_rate - q / payoff
    if raw_kelly <= 0:
        return 0.0

    fractional = raw_kelly * kelly_multiplier
    return min(fractional, max_fraction)


def compute_kelly_shares(
    notional: float,
    price: float,
    fraction: float,
    atr: float | None = None,
    risk_per_trade_pct: float = 0.01,
    atr_stop_multiple: float = 2.0,
    *,
    allow_fractional: bool = False,
) -> int | float:
    """Calcule le nombre de parts à partir d'une fraction Kelly.

    Parameters
    ----------
    notional : float
        Capital disponible (equity).
    price : float
        Prix unitaire.
    fraction : float
        Fraction Kelly.
    atr : float | None
        ATR pour le cap de risque.
    risk_per_trade_pct : float
        Budget de risque par trade.
    atr_stop_multiple : float
        Multiple d'ATR pour le stop.
    allow_fractional : bool
        Si True, autorise les parts fractionnaires.

    Returns
    -------
    int | float
        Nombre de parts (0 si invalide).
    """
    if price <= 0 or fraction <= 0:
        return 0

    kelly_shares = notional * fraction / price

    if atr is not None and atr > 0:
        risk_budget = notional * risk_per_trade_pct
        risk_per_share = atr * atr_stop_multiple
        if risk_per_share > 0:
            atr_shares = risk_budget / risk_per_share
            shares = min(kelly_shares, atr_shares)
        else:
            shares = kelly_shares
    else:
        shares = kelly_shares

    if allow_fractional:
        return max(shares, 0.0)
    else:
        return int(math.floor(max(shares, 0.0)))
