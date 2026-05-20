"""Construction du portefeuille cible."""
from __future__ import annotations

import logging
from collections.abc import Callable

from pandas import DataFrame

from core.conviction import ConvictionWeights
from core.conviction import fuse as _fuse_conviction
from core.run_summary import attach_live_progress
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.constraints import PortfolioState
from risk_management.correlation_filter import filter_correlated
from risk_management.enums import Decision, DecisionReasonCode, SizingMethod
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

LOGGER = logging.getLogger(__name__)


class PortfolioBuilder:
    """Orchestre sizing + contraintes pour construire le portefeuille cible."""

    def __init__(
        self,
        config: RiskConfig,
        pnl: PnLSnapshot | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._cfg = config
        self._sizer = PositionSizer(config)
        self._kelly_sizer = KellySizer(config) if config.enable_kelly_sizing else None
        self._pnl = pnl
        self._circuit_breaker = circuit_breaker
        self.progress_callback: Callable[[dict[str, object]], None] | None = None

    def _emit_progress(
        self,
        summary: dict[str, object],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        item: str | None = None,
        unit: str = "candidats",
    ) -> None:
        if not callable(self.progress_callback):
            return
        self.progress_callback(
            attach_live_progress(
                summary,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit,
                item=item,
            )
        )

    def _build_enriched_candidates(
        self,
        candidates: list[CandidateScore],
        predictions: dict[str, PredictionInfo],
        win_rates: dict[str, WinRateInfo],
    ) -> list[EnrichedCandidate]:
        enriched: list[EnrichedCandidate] = []
        for candidate in candidates:
            prediction = predictions.get(candidate.symbol)
            win_rate = win_rates.get(candidate.symbol)
            predicted_proba = prediction.predicted_proba if prediction else None
            historical_win_rate = win_rate.directional_accuracy if win_rate else None
            conviction = _fuse_conviction(
                quant_score=candidate.score_used,
                predicted_proba=predicted_proba,
                weights=ConvictionWeights(
                    score_weight=self._cfg.score_weight,
                    prediction_weight=self._cfg.prediction_weight,
                ),
            )
            enriched.append(
                EnrichedCandidate(
                    symbol=candidate.symbol,
                    sector=candidate.sector,
                    score_used=candidate.score_used,
                    score_source=candidate.score_source,
                    predicted_proba=predicted_proba,
                    historical_win_rate=historical_win_rate,
                    conviction_score=conviction,
                    company_idio_score=candidate.company_idio_score,
                    macro_regime_score=candidate.macro_regime_score,
                    company_idio_signal_norm=candidate.company_idio_signal_norm,
                    macro_regime_signal_norm=candidate.macro_regime_signal_norm,
                    company_idio_component=candidate.company_idio_component,
                    macro_regime_component=candidate.macro_regime_component,
                    quant_component=candidate.quant_component,
                    walk_forward_sentiment_weight=candidate.walk_forward_sentiment_weight,
                    walk_forward_macro_weight=candidate.walk_forward_macro_weight,
                    walk_forward_quant_weight=candidate.walk_forward_quant_weight,
                    calibration_run_id=candidate.calibration_run_id,
                    calibration_source=candidate.calibration_source,
                    snapshot_date=candidate.snapshot_date,
                    prediction_asof_date=prediction.prediction_date if prediction else None,
                    ml_metrics_asof_date=win_rate.asof_date if win_rate else None,
                    candidate_rank=candidate.candidate_rank,
                    selector_signal_mode=candidate.selector_signal_mode,
                    selection_explanation=candidate.selection_explanation,
                    selector_earnings_blackout=candidate.selector_earnings_blackout,
                )
            )
        enriched.sort(
            key=lambda entry: (
                -entry.conviction_score,
                entry.candidate_rank if entry.candidate_rank is not None else 10**9,
                entry.symbol,
            )
        )
        return enriched

    def build(
        self,
        candidates: list[CandidateScore],
        prices: dict[str, PriceInfo],
        predictions: dict[str, PredictionInfo] | None = None,
        win_rates: dict[str, WinRateInfo] | None = None,
        return_matrix: DataFrame | None = None,
    ) -> list[PortfolioEntry]:
        """Construit la liste des PortfolioEntry."""
        predictions = predictions or {}
        win_rates = win_rates or {}
        total_candidates = len(candidates)

        # 1. Enrichir puis trier par conviction DESC
        enriched = self._build_enriched_candidates(candidates, predictions, win_rates)
        enriched_by_symbol = {entry.symbol: entry for entry in enriched}

        # 2. Filtre corrélation
        entries: list[PortfolioEntry] = []
        if return_matrix is not None and not return_matrix.empty:
            retained, rejections = filter_correlated(
                enriched, return_matrix, self._cfg.correlation_threshold, self._cfg.correlation_min_overlap,
            )
            for rej in rejections:
                ec = enriched_by_symbol[rej.rejected_symbol]
                reason = f"corrélation {rej.correlation_value:.2f} > {rej.threshold} avec {rej.blocker_symbol}"
                reason = reason[:255]
                entries.append(self._make_entry_v2(
                    ec, prices.get(ec.symbol), 0, 0, Decision.REJECTED, reason,
                    decision_reason_code=DecisionReasonCode.CORRELATION_FILTER,
                    correlation_blocker=rej.blocker_symbol,
                    correlation_value=rej.correlation_value,
                ))
        else:
            retained = enriched

        processed_candidates = len(entries)
        if total_candidates > 0:
            self._emit_progress(
                {
                    "targeted_symbols": total_candidates,
                    "correlation_rejections": len(entries),
                    "retained_after_correlation": len(retained),
                },
                current=processed_candidates,
                total=total_candidates,
                label="🛡️ Progression risk management — construction portefeuille",
                phase="build_portfolio",
                item="filtre corrélation" if processed_candidates > 0 else None,
            )

        # 3. Sizing + contraintes
        sector_map = {c.symbol: c.sector for c in candidates}
        state = PortfolioState()
        checker = RiskCheckerImpl(
            self._cfg,
            state=state,
            pnl=self._pnl,
            sector_map=sector_map,
            circuit_breaker=self._circuit_breaker,
        )
        equity = self._cfg.account_equity
        accepted_rank = 0

        for ec in retained:
            pi = prices.get(ec.symbol)
            if pi is None or pi.last_close <= 0:
                entries.append(
                    self._make_entry_v2(
                        ec,
                        pi,
                        0,
                        0,
                        Decision.REJECTED,
                        "prix indisponible",
                        decision_reason_code=DecisionReasonCode.MISSING_PRICE,
                    )
                )
                processed_candidates += 1
                self._emit_progress(
                    {
                        "targeted_symbols": total_candidates,
                        "accepted_symbols": accepted_rank,
                        "processed_symbols": processed_candidates,
                        "retained_after_correlation": len(retained),
                    },
                    current=processed_candidates,
                    total=total_candidates,
                    label="🛡️ Progression risk management — construction portefeuille",
                    phase="build_portfolio",
                    item=ec.symbol,
                )
                continue

            # Sizing
            if self._kelly_sizer is not None:
                sizing = self._kelly_sizer.compute(pi, ec.predicted_proba, ec.historical_win_rate)
            else:
                sizing = self._sizer.compute(pi)

            if sizing.proposed_shares < 1:
                entries.append(self._make_entry_v2(
                    ec, pi, 0, 0, Decision.REJECTED, "sizing insuffisant",
                    decision_reason_code=DecisionReasonCode(str(sizing.method or SizingMethod.UNKNOWN)),
                    sizing_method=sizing.method,
                ))
                processed_candidates += 1
                self._emit_progress(
                    {
                        "targeted_symbols": total_candidates,
                        "accepted_symbols": accepted_rank,
                        "processed_symbols": processed_candidates,
                        "retained_after_correlation": len(retained),
                    },
                    current=processed_candidates,
                    total=total_candidates,
                    label="🛡️ Progression risk management — construction portefeuille",
                    phase="build_portfolio",
                    item=ec.symbol,
                )
                continue

            approved = int(checker.check_position_size(ec.symbol, sizing.proposed_shares, pi.last_close))
            if approved < 1:
                reason = checker.get_last_decision_reason()
                reason_code = checker.get_last_decision_reason_code()
                entries.append(self._make_entry_v2(
                    ec, pi, sizing.proposed_shares, 0, Decision.REJECTED, reason,
                    decision_reason_code=reason_code,
                    sizing_method=sizing.method,
                ))
                processed_candidates += 1
                self._emit_progress(
                    {
                        "targeted_symbols": total_candidates,
                        "accepted_symbols": accepted_rank,
                        "processed_symbols": processed_candidates,
                        "retained_after_correlation": len(retained),
                    },
                    current=processed_candidates,
                    total=total_candidates,
                    label="🛡️ Progression risk management — construction portefeuille",
                    phase="build_portfolio",
                    item=ec.symbol,
                )
                continue

            decision = Decision.ACCEPTED if approved == sizing.proposed_shares else Decision.REDUCED
            reason = "OK" if decision == Decision.ACCEPTED else checker.get_last_decision_reason()
            reason_code = DecisionReasonCode.OK if decision == Decision.ACCEPTED else checker.get_last_decision_reason_code()
            checker.accept(ec.symbol, ec.sector, approved, pi.last_close)
            accepted_rank += 1

            notional = approved * pi.last_close
            weight = notional / equity if equity > 0 else 0.0
            risk_per_share = pi.atr_20 * self._cfg.atr_stop_multiple if pi.atr_20 is not None and pi.atr_20 > 0 else None
            risk_budget_dollars = equity * self._cfg.risk_per_trade_pct if equity > 0 else None
            initial_risk_dollars = approved * risk_per_share if risk_per_share is not None else None
            stop_price_initial = max(0.0, pi.last_close - risk_per_share) if risk_per_share is not None else None

            # Compute Kelly-specific audit fields
            p_eff: float | None = None
            kf: float | None = None
            if self._kelly_sizer is not None and (ec.predicted_proba is not None or ec.historical_win_rate is not None):
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
                score_used=ec.score_used, score_source=ec.score_source,
                atr_20=pi.atr_20, proposed_shares=sizing.proposed_shares,
                approved_shares=approved, target_notional=notional, target_weight=weight,
                decision=decision, decision_reason=reason, decision_reason_code=reason_code,
                conviction_score=ec.conviction_score, predicted_proba=ec.predicted_proba,
                historical_win_rate=ec.historical_win_rate, effective_probability=p_eff,
                kelly_fraction=kf, sizing_method=sizing.method,
                company_idio_score=ec.company_idio_score,
                macro_regime_score=ec.macro_regime_score,
                company_idio_signal_norm=ec.company_idio_signal_norm,
                macro_regime_signal_norm=ec.macro_regime_signal_norm,
                company_idio_component=ec.company_idio_component,
                macro_regime_component=ec.macro_regime_component,
                quant_component=ec.quant_component,
                walk_forward_sentiment_weight=ec.walk_forward_sentiment_weight,
                walk_forward_macro_weight=ec.walk_forward_macro_weight,
                walk_forward_quant_weight=ec.walk_forward_quant_weight,
                calibration_run_id=ec.calibration_run_id,
                calibration_source=ec.calibration_source,
                candidate_rank=ec.candidate_rank,
                decision_rank=accepted_rank,
                stop_price_initial=stop_price_initial,
                risk_per_share=risk_per_share,
                risk_budget_dollars=risk_budget_dollars,
                initial_risk_dollars=initial_risk_dollars,
                score_snapshot_date=ec.snapshot_date,
                price_asof_date=pi.price_asof_date,
                atr_asof_date=pi.atr_asof_date,
                prediction_asof_date=ec.prediction_asof_date,
                ml_metrics_asof_date=ec.ml_metrics_asof_date,
                selector_signal_mode=ec.selector_signal_mode,
                selection_explanation=ec.selection_explanation,
                selector_earnings_blackout=ec.selector_earnings_blackout,
            ))
            processed_candidates += 1
            self._emit_progress(
                {
                    "targeted_symbols": total_candidates,
                    "accepted_symbols": accepted_rank,
                    "processed_symbols": processed_candidates,
                    "retained_after_correlation": len(retained),
                },
                current=processed_candidates,
                total=total_candidates,
                label="🛡️ Progression risk management — construction portefeuille",
                phase="build_portfolio",
                item=ec.symbol,
            )

        return entries

    # ------------------------------------------------------------------

    @staticmethod
    def _make_entry_v2(
        ec: EnrichedCandidate,
        pi: PriceInfo | None,
        proposed: int,
        approved: int,
        decision: Decision,
        reason: str,
        decision_reason_code: DecisionReasonCode | None = None,
        sizing_method: SizingMethod = SizingMethod.UNKNOWN,
        correlation_blocker: str | None = None,
        correlation_value: float | None = None,
    ) -> PortfolioEntry:
        price = pi.last_close if pi else 0.0
        atr = pi.atr_20 if pi else None
        return PortfolioEntry(
            symbol=ec.symbol, sector=ec.sector, entry_price=price,
            score_used=ec.score_used, score_source=ec.score_source,
            atr_20=atr, proposed_shares=proposed, approved_shares=approved,
            target_notional=approved * price, target_weight=0.0,
            decision=decision, decision_reason=reason, decision_reason_code=decision_reason_code,
            conviction_score=ec.conviction_score, predicted_proba=ec.predicted_proba,
            historical_win_rate=ec.historical_win_rate, sizing_method=sizing_method,
            correlation_blocker=correlation_blocker, correlation_value=correlation_value,
            company_idio_score=ec.company_idio_score,
            macro_regime_score=ec.macro_regime_score,
            company_idio_signal_norm=ec.company_idio_signal_norm,
            macro_regime_signal_norm=ec.macro_regime_signal_norm,
            company_idio_component=ec.company_idio_component,
            macro_regime_component=ec.macro_regime_component,
            quant_component=ec.quant_component,
            walk_forward_sentiment_weight=ec.walk_forward_sentiment_weight,
            walk_forward_macro_weight=ec.walk_forward_macro_weight,
            walk_forward_quant_weight=ec.walk_forward_quant_weight,
            calibration_run_id=ec.calibration_run_id,
            calibration_source=ec.calibration_source,
            candidate_rank=ec.candidate_rank,
            score_snapshot_date=ec.snapshot_date,
            price_asof_date=pi.price_asof_date if pi else None,
            atr_asof_date=pi.atr_asof_date if pi else None,
            prediction_asof_date=ec.prediction_asof_date,
            ml_metrics_asof_date=ec.ml_metrics_asof_date,
            selector_signal_mode=ec.selector_signal_mode,
            selection_explanation=ec.selection_explanation,
            selector_earnings_blackout=ec.selector_earnings_blackout,
        )
