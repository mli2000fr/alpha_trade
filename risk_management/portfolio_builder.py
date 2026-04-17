"""Construction du portefeuille cible."""
from __future__ import annotations

import logging

from risk_management.config import RiskConfig
from risk_management.constraints import PortfolioState
from risk_management.models import CandidateScore, PortfolioEntry, PriceInfo
from risk_management.position_sizer import PositionSizer
from risk_management.risk_checker import RiskCheckerImpl
from risk_management.circuit_breaker import PnLSnapshot

LOGGER = logging.getLogger(__name__)


class PortfolioBuilder:
    """Orchestre sizing + contraintes pour construire le portefeuille cible."""

    def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None = None) -> None:
        self._cfg = config
        self._sizer = PositionSizer(config)
        self._pnl = pnl

    def build(
        self,
        candidates: list[CandidateScore],
        prices: dict[str, PriceInfo],
    ) -> list[PortfolioEntry]:
        """Construit la liste des PortfolioEntry."""
        state = PortfolioState()
        sector_map = {c.symbol: c.sector for c in candidates}
        checker = RiskCheckerImpl(self._cfg, state=state, pnl=self._pnl, sector_map=sector_map)

        entries: list[PortfolioEntry] = []
        equity = self._cfg.account_equity

        for cand in candidates:
            pi = prices.get(cand.symbol)
            if pi is None or pi.last_close <= 0:
                entries.append(self._make_entry(cand, pi, 0, 0, "REJECTED", "prix indisponible"))
                continue


            sizing = self._sizer.compute(pi)
            if sizing.proposed_shares < 1:
                entries.append(self._make_entry(cand, pi, 0, 0, "REJECTED", "sizing insuffisant"))
                continue

            approved = int(checker.check_position_size(cand.symbol, sizing.proposed_shares, pi.last_close))
            if approved < 1:
                reason = "contrainte de risque"
                if checker.is_circuit_breaker_active():
                    reason = "circuit breaker actif"
                entries.append(self._make_entry(cand, pi, sizing.proposed_shares, 0, "REJECTED", reason))
                continue

            decision = "ACCEPTED" if approved == sizing.proposed_shares else "REDUCED"
            reason = "OK" if decision == "ACCEPTED" else "réduit par contraintes"
            checker.accept(cand.symbol, cand.sector, approved, pi.last_close)

            notional = approved * pi.last_close
            weight = notional / equity if equity > 0 else 0.0
            entries.append(PortfolioEntry(
                symbol=cand.symbol,
                sector=cand.sector,
                entry_price=pi.last_close,
                score_used=cand.score_used,
                score_source="final_score_sentiment",
                atr_20=pi.atr_20,
                proposed_shares=sizing.proposed_shares,
                approved_shares=approved,
                target_notional=notional,
                target_weight=weight,
                decision=decision,
                decision_reason=reason,
            ))

        return entries

    # ------------------------------------------------------------------
    @staticmethod
    def _make_entry(
        cand: CandidateScore,
        pi: PriceInfo | None,
        proposed: int,
        approved: int,
        decision: str,
        reason: str,
    ) -> PortfolioEntry:
        price = pi.last_close if pi else 0.0
        atr = pi.atr_20 if pi else None
        return PortfolioEntry(
            symbol=cand.symbol,
            sector=cand.sector,
            entry_price=price,
            score_used=cand.score_used,
            score_source="final_score_sentiment",
            atr_20=atr,
            proposed_shares=proposed,
            approved_shares=approved,
            target_notional=approved * price,
            target_weight=0.0,
            decision=decision,
            decision_reason=reason,
        )
