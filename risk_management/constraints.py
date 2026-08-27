"""Contraintes de risque appliquées lors de la construction du portefeuille.

Sprint Maître 6 — contraintes directionnelles :
- ``PortfolioState`` enrichi : long/short counts, long/short notionals,
  gross, net.
- ``ConstraintChecker.check()`` reçoit ``side`` et applique les caps
  directionnels (max_long_positions, max_short_positions).
- Contrainte ADV : fail-closed (exige ``adv_usd``, rejette si absent).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from common.quantity_utils import QUANTITY_EPSILON, normalize_share_quantity
from risk_management.config import RiskConfig
from risk_management.enums import DecisionReasonCode

LOGGER = logging.getLogger(__name__)

_REASON_TO_CODE = {
    "OK": DecisionReasonCode.OK,
    "max_positions atteint": DecisionReasonCode.CONSTRAINT_MAX_POSITIONS,
    "max_long_positions atteint": DecisionReasonCode.CONSTRAINT_MAX_POSITIONS,
    "max_short_positions atteint": DecisionReasonCode.CONSTRAINT_MAX_POSITIONS,
    "max_tickers_per_sector atteint": DecisionReasonCode.CONSTRAINT_MAX_TICKERS_PER_SECTOR,
    "max_gross_exposure atteint": DecisionReasonCode.CONSTRAINT_MAX_GROSS_EXPOSURE,
    "max_position_weight atteint": DecisionReasonCode.CONSTRAINT_MAX_POSITION_WEIGHT,
    "max_sector_weight atteint": DecisionReasonCode.CONSTRAINT_MAX_SECTOR_WEIGHT,
    "sector_exposure_cap atteint": DecisionReasonCode.SECTOR_EXPOSURE_CAP,
    "sector_corr_threshold atteint": DecisionReasonCode.SECTOR_CORR_THRESHOLD,
    "min_position_notional non atteint": DecisionReasonCode.CONSTRAINT_MIN_POSITION_NOTIONAL,
    "max_position_pct_of_adv atteint": DecisionReasonCode.CONSTRAINT_MAX_POSITION_PCT_OF_ADV,
    "adv_unavailable": DecisionReasonCode.CONSTRAINT_MAX_POSITION_PCT_OF_ADV,
}


@dataclass(slots=True)
class PortfolioState:
    """État courant du portefeuille en construction (Sprint Maître 6).

    Enrichi avec les compteurs directionnels long/short.
    """

    total_notional: float = 0.0
    position_count: int = 0
    # ── Sprint Maître 6 : compteurs directionnels ──────────────────────
    long_count: int = 0
    short_count: int = 0
    long_notional: float = 0.0
    short_notional: float = 0.0
    sector_notional: dict[str, float] = field(default_factory=dict)
    sector_ticker_count: dict[str, int] = field(default_factory=dict)
    # Smart sector cap (C2) : symboles par secteur pour la corrélation intra.
    sector_symbols: dict[str, list[str]] = field(default_factory=dict)

    @property
    def gross_notional(self) -> float:
        """Exposition brute = long_notional + short_notional."""
        return self.long_notional + self.short_notional

    @property
    def net_notional(self) -> float:
        """Exposition nette = long_notional - short_notional."""
        return self.long_notional - self.short_notional

    @property
    def total_notional_signed(self) -> float:
        """Alias rétrocompatible : exposition brute."""
        return self.gross_notional

    def add_position(
        self,
        *,
        notional: float,
        sector: str,
        side: str = "long",
        symbol: str = "",
    ) -> None:
        """Enregistre une position dans le state (side-aware).

        Parameters
        ----------
        notional : float
            Notionnel de la position (toujours positif).
        sector : str
            Secteur du symbole.
        side : str
            ``"long"`` ou ``"short"``.
        symbol : str
            Symbole (pour le ticker count).
        """
        is_short = side.strip().lower() in ("short", "sell")
        self.total_notional += notional
        self.position_count += 1
        if is_short:
            self.short_count += 1
            self.short_notional += notional
        else:
            self.long_count += 1
            self.long_notional += notional

        # Sector tracking
        current_sector_notional = self.sector_notional.get(sector, 0.0)
        self.sector_notional[sector] = current_sector_notional + notional
        current_ticker_count = self.sector_ticker_count.get(sector, 0)
        self.sector_ticker_count[sector] = current_ticker_count + 1
        # Smart sector cap (C2) : mémoriser le symbole pour la corrélation intra.
        if symbol:
            self.sector_symbols.setdefault(sector, []).append(symbol)


class ConstraintChecker:
    """Vérifie les contraintes de risque et retourne les shares autorisées."""

    def __init__(self, config: RiskConfig) -> None:
        self._cfg = config

    def _normalize_approved_shares(self, shares: float) -> float:
        if shares <= 0:
            return 0.0
        if self._cfg.allow_fractional_shares:
            return normalize_share_quantity(shares)
        return float(int(shares))

    @staticmethod
    def reason_to_code(reason: str) -> DecisionReasonCode:
        return _REASON_TO_CODE.get(str(reason or "").strip() or "OK", DecisionReasonCode.CONSTRAINT_UNKNOWN)

    def _hybrid_corr_ok(self, state: PortfolioState, sector: str, symbol: str) -> bool:
        """C2 : corrélation moyenne PIT < seuil avec les positions du secteur.

        S'appuie sur la carte paire PIT injectée par jour (``cfg.sector_corr_map``).
        Donnée manquante → refuse (fail-closed PIT).
        """
        members = state.sector_symbols.get(sector, [])
        if not members:
            return True  # pas d'autre position du secteur → sans objet
        corr_map = getattr(self._cfg, "sector_corr_map", None)
        if not corr_map:
            return False  # pas de carte PIT → refuse (sûr)
        vals: list[float] = []
        for m in members:
            v = corr_map.get(symbol, {}).get(m)
            if v is None:
                v = corr_map.get(m, {}).get(symbol)
            if v is None:
                return False  # donnée corr manquante → refuse (PIT strict)
            vals.append(float(v))
        if not vals:
            return True
        return (sum(vals) / len(vals)) < float(self._cfg.sector_corr_threshold)

    def check(
        self,
        symbol: str,
        sector: str,
        proposed_shares: float,
        price: float,
        state: PortfolioState,
        *,
        side: str = "long",
        adv_usd: float | None = None,
        selection_rank: int | None = None,
    ) -> tuple[float, str]:
        """Retourne (approved_shares, reason). reason == 'OK' si aucune réduction.

        Sprint Maître 6 :
        - ``side`` ajouté pour les caps directionnels.
        - ADV fail-closed : si ``max_position_pct_of_adv`` est configuré
          et ``adv_usd`` absent → rejet.
        """
        equity = self._cfg.account_equity
        proposed_shares = self._normalize_approved_shares(proposed_shares)
        minimum_viable_shares = QUANTITY_EPSILON if self._cfg.allow_fractional_shares else 1.0
        reduction_reason: str | None = None
        is_short = side.strip().lower() in ("short", "sell")

        # ── Sprint Maître 6 : cap directionnel short ──────────────────
        if is_short and state.short_count >= self._cfg.max_short_positions:
            return 0.0, "max_short_positions atteint"

        # ── Sprint Maître 6 : cap directionnel long ───────────────────
        resolved_max_long = (
            self._cfg.max_long_positions
            if self._cfg.max_long_positions is not None
            else self._cfg.max_positions
        )
        if not is_short and state.long_count >= resolved_max_long:
            return 0.0, "max_long_positions atteint"

        # max positions (effectif — peut être réduit par le régime)
        if state.position_count >= self._cfg.effective_max_positions:
            return 0.0, "max_positions atteint"

        # ── Smart sector cap (chantier research 2026-08-27) ────────────
        # Mode "count"    (C0) = comportement actuel (max_tickers_per_sector).
        # Mode "exposure" (C1) = remplace le ticker-count par une limite
        #   d'exposition sectorielle post-entrée (refuse, ne réduit pas).
        # Mode "hybrid"   (C2) = max 2 tickers + un 3e exceptionnel SI
        #   exposition post-entrée <= cap ET corrélation moyenne PIT avec les
        #   positions du secteur < seuil ; jamais plus de 3 tickers. Le 3e
        #   candidat est par construction le meilleur encore disponible du
        #   secteur (traitement par selection_rank croissant).
        _cap_mode = str(getattr(self._cfg, "sector_cap_mode", "count") or "count").strip().lower()
        if _cap_mode == "exposure":
            _expo_after = (state.sector_notional.get(sector, 0.0) + proposed_shares * price) / equity
            if _expo_after > float(self._cfg.sector_exposure_cap_pct) + 1e-12:
                return 0.0, "sector_exposure_cap atteint"
        elif _cap_mode == "hybrid":
            _current_n = state.sector_ticker_count.get(sector, 0)
            if _current_n >= 3:
                return 0.0, "max_tickers_per_sector atteint"
            if _current_n == 2:
                _expo_after = (state.sector_notional.get(sector, 0.0) + proposed_shares * price) / equity
                if _expo_after > float(self._cfg.sector_exposure_cap_pct) + 1e-12:
                    return 0.0, "sector_exposure_cap atteint"
                if not self._hybrid_corr_ok(state, sector, symbol):
                    return 0.0, "sector_corr_threshold atteint"
                LOGGER.info(
                    "smart_sector_cap hybrid: 3e ticker accepté secteur=%s symbol=%s rank=%s",
                    sector, symbol, selection_rank,
                )
        else:
            # C0 / "count" : comportement actuel inchangé
            if self._cfg.max_tickers_per_sector is not None:
                current_n = state.sector_ticker_count.get(sector, 0)
                if current_n >= self._cfg.max_tickers_per_sector:
                    return 0.0, "max_tickers_per_sector atteint"

        notional = proposed_shares * price
        original_notional = notional

        # max gross exposure (total) — borne dure
        if (state.gross_notional + notional) / equity > self._cfg.max_gross_exposure:
            max_notional = equity * self._cfg.max_gross_exposure - state.gross_notional
            if max_notional <= 0:
                return 0.0, "max_gross_exposure atteint"
            proposed_shares = self._normalize_approved_shares(max_notional / price)
            notional = proposed_shares * price
            if proposed_shares < minimum_viable_shares:
                return 0.0, "max_gross_exposure atteint"
            reduction_reason = "max_gross_exposure atteint"

        # CP-V2 — budget par side (réserve SHORT / cap LONG) pendant capital_preservation.
        # La capacité SHORT est réservée à l'intérieur du gross total : les longs existants
        # ne peuvent pas la consommer. Inactif si les champs ne sont pas définis (prod_legacy).
        _side_limit = self._cfg.max_short_exposure if is_short else self._cfg.max_long_exposure
        if _side_limit is not None:
            _current_side = state.short_notional if is_short else state.long_notional
            _side_remaining = equity * _side_limit - _current_side
            if _side_remaining <= 0:
                return 0.0, ("max_short_exposure atteint" if is_short else "max_long_exposure atteint")
            _side_shares = self._normalize_approved_shares(_side_remaining / price)
            if _side_shares < minimum_viable_shares:
                return 0.0, ("max_short_exposure atteint" if is_short else "max_long_exposure atteint")
            if _side_shares < proposed_shares:
                proposed_shares = _side_shares
                notional = proposed_shares * price
                reduction_reason = "max_short_exposure atteint" if is_short else "max_long_exposure atteint"

        # max position weight
        max_pos_notional = equity * self._cfg.max_position_weight
        if notional > max_pos_notional:
            proposed_shares = self._normalize_approved_shares(max_pos_notional / price)
            notional = proposed_shares * price
            if proposed_shares < minimum_viable_shares:
                return 0.0, "max_position_weight atteint"
            reduction_reason = "max_position_weight atteint"

        # max sector weight
        current_sector = state.sector_notional.get(sector, 0.0)
        max_sector_notional = equity * self._cfg.max_sector_weight
        if (current_sector + notional) > max_sector_notional:
            remaining = max_sector_notional - current_sector
            if remaining <= 0:
                return 0.0, "max_sector_weight atteint"
            proposed_shares = self._normalize_approved_shares(remaining / price)
            notional = proposed_shares * price
            if proposed_shares < minimum_viable_shares:
                return 0.0, "max_sector_weight atteint"
            reduction_reason = "max_sector_weight atteint"

        # ── Sprint Maître 6 : ADV fail-closed ─────────────────────────
        if self._cfg.max_position_pct_of_adv is not None:
            if adv_usd is None or adv_usd <= 0:
                return 0.0, "adv_unavailable"
            max_notional_from_adv = adv_usd * self._cfg.max_position_pct_of_adv
            if notional > max_notional_from_adv:
                proposed_shares = self._normalize_approved_shares(max_notional_from_adv / price)
                notional = proposed_shares * price
                if proposed_shares < minimum_viable_shares:
                    return 0.0, "max_position_pct_of_adv atteint"
                reduction_reason = "max_position_pct_of_adv atteint"
                LOGGER.info(
                    "Position réduite par contrainte ADV pour %s : $%.0f → $%.0f (%.1f%% ADV)",
                    symbol,
                    original_notional,
                    notional,
                    self._cfg.max_position_pct_of_adv * 100,
                )

        # min position notional
        if notional < self._cfg.effective_min_notional:
            return 0.0, reduction_reason or "min_position_notional non atteint"

        return proposed_shares, reduction_reason or "OK"

    # ── Section 17 Point 6.5 : revalidation post-portefeuille ─────────

    def revalidate_portfolio(
        self,
        state: PortfolioState,
        *,
        positions: list[dict[str, object]] | None = None,
    ) -> list[str]:
        """Revalide TOUTES les contraintes après construction du portefeuille.

        Cette méthode doit être appelée APRÈS que toutes les positions
        ont été acceptées, réduites, neutralisées et arrondies. Elle
        vérifie que l'état final respecte bien les contraintes globales.

        Parameters
        ----------
        state : PortfolioState
            État final du portefeuille après assemblage.
        positions : list[dict] | None
            Détail des positions pour les vérifications symbol-level.
            Chaque dict doit contenir: symbol, sector, notional, adv_usd.

        Returns
        -------
        list[str]
            Liste des violations (vide = portefeuille conforme).
        """
        violations: list[str] = []
        equity = self._cfg.account_equity

        # 1. Caps directionnels
        if state.long_count > (
            self._cfg.max_positions
            if self._cfg.max_long_positions is None
            else self._cfg.max_long_positions
        ):
            violations.append(
                f"long_count_exceeded:{state.long_count}>"
                f"{self._cfg.max_long_positions or self._cfg.max_positions}"
            )
        if state.short_count > self._cfg.max_short_positions:
            violations.append(
                f"short_count_exceeded:{state.short_count}>{self._cfg.max_short_positions}"
            )

        # 2. Max positions totales
        if state.position_count > self._cfg.effective_max_positions:
            violations.append(
                f"position_count_exceeded:{state.position_count}>"
                f"{self._cfg.effective_max_positions}"
            )

        # 3. Gross exposure
        gross_pct = state.gross_notional / equity
        if gross_pct > self._cfg.max_gross_exposure + 1e-8:
            violations.append(
                f"gross_exposure_exceeded:{gross_pct:.3f}>{self._cfg.max_gross_exposure}"
            )

        # 3bis. CP-V2 — budgets par side (actifs seulement si définis)
        if self._cfg.max_long_exposure is not None and equity > 0:
            long_pct = state.long_notional / equity
            if long_pct > self._cfg.max_long_exposure + 1e-8:
                violations.append(
                    f"long_exposure_exceeded:{long_pct:.3f}>{self._cfg.max_long_exposure}"
                )
        if self._cfg.max_short_exposure is not None and equity > 0:
            short_pct = state.short_notional / equity
            if short_pct > self._cfg.max_short_exposure + 1e-8:
                violations.append(
                    f"short_exposure_exceeded:{short_pct:.3f}>{self._cfg.max_short_exposure}"
                )

        # 4. Net exposure (si enforce_net_exposure)
        if self._cfg.enforce_net_exposure:
            net_pct = state.net_notional / equity
            target = self._cfg.net_exposure_target
            tol = self._cfg.net_exposure_tolerance
            if abs(net_pct - target) > tol + 1e-8:
                violations.append(
                    f"net_exposure_violation:|{net_pct:.3f}-{target}|>{tol}"
                )

        # 5. Secteur
        max_sector_notional = equity * self._cfg.max_sector_weight
        for sector_name, sector_notional in state.sector_notional.items():
            if sector_notional > max_sector_notional + 1e-8:
                violations.append(
                    f"sector_weight_exceeded:{sector_name}:"
                    f"{sector_notional:.0f}>{max_sector_notional:.0f}"
                )

        # 6. Tickers par secteur
        if self._cfg.max_tickers_per_sector is not None:
            for sector_name, count in state.sector_ticker_count.items():
                if count > self._cfg.max_tickers_per_sector:
                    violations.append(
                        f"sector_ticker_count_exceeded:{sector_name}:"
                        f"{count}>{self._cfg.max_tickers_per_sector}"
                    )

        # 7. Contrôles symbol-level (si positions fournies)
        if positions:
            for pos in positions:
                notional = float(pos.get("notional", 0))
                symbol = str(pos.get("symbol", "?"))
                # Poids max par position
                if notional > equity * self._cfg.max_position_weight + 1e-8:
                    violations.append(
                        f"position_weight_exceeded:{symbol}:"
                        f"{notional:.0f}>{equity * self._cfg.max_position_weight:.0f}"
                    )
                # Min notional
                if 0 < notional < self._cfg.effective_min_notional:
                    violations.append(
                        f"min_notional_violation:{symbol}:"
                        f"{notional:.0f}<{self._cfg.effective_min_notional:.0f}"
                    )

        return violations
