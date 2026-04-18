"""Construction du portefeuille cible."""
from __future__ import annotations

import logging

import pandas as pd

from risk_management.config import RiskConfig
from risk_management.constraints import PortfolioState
from risk_management.conviction import compute_conviction
from risk_management.correlation_filter import filter_correlated
from risk_management.kelly import KellySizer
from risk_management.models import (
    CandidateScore,
    EnrichedCandidate,
    PortfolioEntry,
    PredictionInfo,
    PriceInfo,
    WinRateInfo,
)
from risk_management.position_sizer import PositionSizer
from risk_management.risk_checker import RiskCheckerImpl
from risk_management.circuit_breaker import PnLSnapshot

LOGGER = logging.getLogger(__name__)


class PortfolioBuilder:
    """Orchestre sizing + contraintes pour construire le portefeuille cible."""

    def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None = None) -> None:
        self._cfg = config
        self._sizer = PositionSizer(config)
        self._kelly_sizer = KellySizer(config) if config.enable_kelly_sizing else None
        self._pnl = pnl

    def build(
        self,
        candidates: list[CandidateScore],
        prices: dict[str, PriceInfo],
        predictions: dict[str, PredictionInfo] | None = None,
        win_rates: dict[str, WinRateInfo] | None = None,
        return_matrix: pd.DataFrame | None = None,
    ) -> list[PortfolioEntry]:
        """Construit la liste des PortfolioEntry."""
        predictions = predictions or {}
        win_rates = win_rates or {}

        # 1. Enrichir en EnrichedCandidate
        enriched: list[EnrichedCandidate] = []
        for c in candidates:
            pred = predictions.get(c.symbol)
            wr = win_rates.get(c.symbol)
            pp = pred.predicted_proba if pred else None
            hw = wr.directional_accuracy if wr else None
            conv = compute_conviction(c.score_used, pp, self._cfg.score_weight, self._cfg.prediction_weight)
            enriched.append(EnrichedCandidate(
                symbol=c.symbol, sector=c.sector, score_used=c.score_used,
                predicted_proba=pp, historical_win_rate=hw, conviction_score=conv,
            ))

        # 2. Trier par conviction DESC
        enriched.sort(key=lambda e: e.conviction_score, reverse=True)

        # 3. Filtre corrélation
        entries: list[PortfolioEntry] = []
        if return_matrix is not None and not return_matrix.empty:
            retained, rejections = filter_correlated(
                enriched, return_matrix, self._cfg.correlation_threshold, self._cfg.correlation_min_overlap,
            )
            for rej in rejections:
                # find the enriched candidate for the rejected symbol
                ec = next(e for e in enriched if e.symbol == rej.rejected_symbol)
                reason = f"corrélation {rej.correlation_value:.2f} > {rej.threshold} avec {rej.blocker_symbol}"
                reason = reason[:255]
                entries.append(self._make_entry_v2(
                    ec, prices.get(ec.symbol), 0, 0, "REJECTED", reason,
                    correlation_blocker=rej.blocker_symbol,
                    correlation_value=rej.correlation_value,
                ))
        else:
            retained = enriched

        # 4. Sizing + contraintes
        sector_map = {c.symbol: c.sector for c in candidates}
        state = PortfolioState()
        checker = RiskCheckerImpl(self._cfg, state=state, pnl=self._pnl, sector_map=sector_map)
        equity = self._cfg.account_equity

        for ec in retained:
            pi = prices.get(ec.symbol)
            if pi is None or pi.last_close <= 0:
                entries.append(self._make_entry_v2(ec, pi, 0, 0, "REJECTED", "prix indisponible"))
                continue

            # Sizing
            if self._kelly_sizer is not None:
                sizing = self._kelly_sizer.compute(pi, ec.predicted_proba, ec.historical_win_rate)
            else:
                sizing = self._sizer.compute(pi)

            if sizing.proposed_shares < 1:
                entries.append(self._make_entry_v2(
                    ec, pi, 0, 0, "REJECTED", "sizing insuffisant",
                    sizing_method=sizing.method,
                ))
                continue

            approved = int(checker.check_position_size(ec.symbol, sizing.proposed_shares, pi.last_close))
            if approved < 1:
                reason = "contrainte de risque"
                if checker.is_circuit_breaker_active():
                    reason = "circuit breaker actif"
                entries.append(self._make_entry_v2(
                    ec, pi, sizing.proposed_shares, 0, "REJECTED", reason,
                    sizing_method=sizing.method,
                ))
                continue

            decision = "ACCEPTED" if approved == sizing.proposed_shares else "REDUCED"
            reason = "OK" if decision == "ACCEPTED" else "réduit par contraintes"
            checker.accept(ec.symbol, ec.sector, approved, pi.last_close)

            notional = approved * pi.last_close
            weight = notional / equity if equity > 0 else 0.0

            # Compute Kelly-specific audit fields
            p_eff: float | None = None
            kf: float | None = None
            if self._kelly_sizer is not None and ec.predicted_proba is not None or ec.historical_win_rate is not None:
                cfg = self._cfg
                pp = ec.predicted_proba if ec.predicted_proba is not None else cfg.default_win_rate
                wr = ec.historical_win_rate if ec.historical_win_rate is not None else cfg.default_win_rate
                p_eff = max(0.001, min(cfg.prediction_confidence_weight * pp + cfg.historical_win_rate_weight * wr, 0.999))
                if p_eff >= cfg.min_effective_probability:
                    q = 1.0 - p_eff
                    raw = p_eff - q / cfg.assumed_payoff_ratio
                    kf = min(max(0.0, raw) * cfg.kelly_fraction_multiplier, cfg.max_position_weight)

            entries.append(PortfolioEntry(
                symbol=ec.symbol, sector=ec.sector, entry_price=pi.last_close,
                score_used=ec.score_used, score_source="final_score_sentiment",
                atr_20=pi.atr_20, proposed_shares=sizing.proposed_shares,
                approved_shares=approved, target_notional=notional, target_weight=weight,
                decision=decision, decision_reason=reason,
                conviction_score=ec.conviction_score, predicted_proba=ec.predicted_proba,
                historical_win_rate=ec.historical_win_rate, effective_probability=p_eff,
                kelly_fraction=kf, sizing_method=sizing.method,
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
            symbol=cand.symbol, sector=cand.sector, entry_price=price,
            score_used=cand.score_used, score_source="final_score_sentiment",
            atr_20=atr, proposed_shares=proposed, approved_shares=approved,
            target_notional=approved * price, target_weight=0.0,
            decision=decision, decision_reason=reason,
        )

    @staticmethod
    def _make_entry_v2(
        ec: EnrichedCandidate,
        pi: PriceInfo | None,
        proposed: int,
        approved: int,
        decision: str,
        reason: str,
        sizing_method: str = "",
        correlation_blocker: str | None = None,
        correlation_value: float | None = None,
    ) -> PortfolioEntry:
        price = pi.last_close if pi else 0.0
        atr = pi.atr_20 if pi else None
        return PortfolioEntry(
            symbol=ec.symbol, sector=ec.sector, entry_price=price,
            score_used=ec.score_used, score_source="final_score_sentiment",
            atr_20=atr, proposed_shares=proposed, approved_shares=approved,
            target_notional=approved * price, target_weight=0.0,
            decision=decision, decision_reason=reason,
            conviction_score=ec.conviction_score, predicted_proba=ec.predicted_proba,
            historical_win_rate=ec.historical_win_rate, sizing_method=sizing_method,
            correlation_blocker=correlation_blocker, correlation_value=correlation_value,
        )
