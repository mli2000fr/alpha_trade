"""Construction du portefeuille cible."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import date

from pandas import DataFrame

from common.quantity_utils import QUANTITY_EPSILON, normalize_share_quantity
from core.conviction import fuse as _fuse_conviction_long
from core.conviction import fuse_short as _fuse_conviction_short
from core.direction import compute_initial_stop_price
from core.run_summary import attach_live_progress
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.constraints import PortfolioState
from risk_management.correlation_filter import filter_correlated_signed
from risk_management.enums import Decision, DecisionReasonCode, SizingMethod
from risk_management.kelly import KellySizer
from risk_management.models import (
    SelectionScore,
    EnrichedSelection,
    PortfolioEntry,
    PredictionInfo,
    PriceInfo,
    WinRateInfo,
)
from risk_management.position_sizer import PositionSizer
from risk_management.risk_checker import RiskCheckerImpl
from risk_management.concentration import (
    BreakoutConfirmationTracker,
    ConsecutiveLossTracker,
    SymbolTradeTracker,
)

LOGGER = logging.getLogger(__name__)


def _apply_regime_scoring_to_candidates(
    candidates: list[SelectionScore],
    regime_snapshot: object,
    rotation_state: object | None = None,
) -> list[SelectionScore]:
    """Applique les filtres de régime et les poids directionnels aux scores.

    Applique systématiquement les filtres événementiels (earnings_shield,
    buyback_blackout, yield_filter) dans **tous** les régimes, PUIS ajuste
    les poids directionnels uniquement en mode ``capital_preservation`` ou
    en cas de rotation forcée.

    En régime ``normal`` sans rotation, seuls les filtres événementiels
    sont appliqués (la fonction n'est plus une non-op stricte).
    """
    from selector.regime_scoring import MomentumRotationState

    mode = str(getattr(regime_snapshot, "mode", "normal") or "normal").strip().lower()
    rotated = (
        isinstance(rotation_state, MomentumRotationState)
        and rotation_state.is_ready()
        and rotation_state.should_rotate()
    )

    try:
        import pandas as pd
        from selector.regime_filters import apply_full_regime_to_candidates

        # ── P0 FIX (2026-06-25) : earnings_shield / buyback_blackout / yield_filter ──
        # Convertir en DataFrame pour appliquer les filtres événementiels
        rows: list[dict[str, object]] = []
        for c in candidates:
            rows.append({
                "symbol": c.symbol,
                "sector": c.sector,
                "score_used": c.score_used,
                "final_score": c.score_used,
            })
        df = pd.DataFrame(rows)

        df = apply_full_regime_to_candidates(
            df,
            regime_snapshot,
            score_column="final_score",
            sector_column="sector",
            symbol_column="symbol",
        )
        # Reconstruire la liste des candidats après filtrage événementiel
        if df.empty:
            return []
        shielded_symbols = set(str(s).upper() for s in df["symbol"])
        # Mettre à jour les scores pénalisés par le shield
        score_map = dict(zip(
            df["symbol"].astype(str).str.upper(),
            df["final_score"].astype(float),
        ))
        shielded_candidates: list[SelectionScore] = []
        for c in candidates:
            sym = c.symbol.upper()
            if sym not in shielded_symbols:
                continue  # exclus par strict_block
            new_score = score_map.get(sym, c.score_used)
            if new_score != c.score_used:
                shielded_candidates.append(SelectionScore(
                    symbol=c.symbol,
                    sector=c.sector,
                    score_used=float(new_score),
                    score_source=f"{c.score_source}_shielded",
                    company_idio_score=c.company_idio_score,
                    macro_regime_score=c.macro_regime_score,
                    company_idio_signal_norm=c.company_idio_signal_norm,
                    macro_regime_signal_norm=c.macro_regime_signal_norm,
                    company_idio_component=c.company_idio_component,
                    macro_regime_component=c.macro_regime_component,
                    quant_component=c.quant_component,
                    walk_forward_sentiment_weight=c.walk_forward_sentiment_weight,
                    walk_forward_macro_weight=c.walk_forward_macro_weight,
                    walk_forward_quant_weight=c.walk_forward_quant_weight,
                    calibration_run_id=c.calibration_run_id,
                    calibration_source=c.calibration_source,
                    snapshot_date=c.snapshot_date,
                    selection_rank=c.selection_rank,
                    selector_signal_mode="shielded",
                    selection_explanation=c.selection_explanation,
                    selector_earnings_blackout=c.selector_earnings_blackout,
                ))
            else:
                shielded_candidates.append(c)
        candidates = shielded_candidates

        # Si régime normal sans rotation → pas d'ajustement des poids directionnels
        if mode == "normal" and not rotated:
            return candidates

        # ── capital_preservation OU rotation : le régime directionnel est déjà appliqué ──
        # en amont par le selector (apply_regime_weights avec de vraies colonnes).
        # On ne refait PAS de rescoring ici — le DataFrame intermédiaire n'a pas les
        # colonnes de facteurs (trend_score, vcp_score, beta_126, etc.) nécessaires.
        # Seuls les filtres événementiels (earnings_shield, buyback, yield) sont
        # appliqués à ce niveau (cf. apply_full_regime_to_candidates plus haut).
        LOGGER.info(
            "Regime %s (rotation=%s) — rescoring directionnel déjà fait par le selector, "
            "on conserve les scores d'origine + filtres événementiels.",
            mode, rotated,
        )
        return candidates
    except Exception:
        LOGGER.warning(
            "apply_regime_weights / earnings_shield a échoué — candidats inchangés.",
            exc_info=True,
        )
        return candidates


def _apply_concentration_filters(
    candidates: list[SelectionScore],
    *,
    trade_tracker: object,
    loss_tracker: object,
    trade_date: date,
) -> list[SelectionScore]:
    """Filtre les candidats selon les règles de concentration (Priorité 4).

    - Bloque si le symbole a déjà atteint le max de trades dans la fenêtre
    - Bloque si le symbole est blacklisté (pertes consécutives)
    """
    filtered: list[SelectionScore] = []
    blocked_trade_count = 0
    blocked_blacklist = 0
    for c in candidates:
        symbol = str(c.symbol).strip().upper()
        c_side = getattr(c, "side", None)
        if not trade_tracker.allow_entry(symbol, trade_date, side=c_side):
            blocked_trade_count += 1
            continue
        if loss_tracker.is_blacklisted(symbol, trade_date, side=c_side):
            blocked_blacklist += 1
            continue
        filtered.append(c)
    if blocked_trade_count or blocked_blacklist:
        LOGGER.info(
            "Concentration filters: blocked %d (max trades) + %d (blacklist) / %d candidates",
            blocked_trade_count,
            blocked_blacklist,
            len(candidates),
        )
    return filtered


def _enforce_net_exposure_neutrality(
    accepted_entries: list[PortfolioEntry],
    *,
    equity: float,
    target: float,
    tolerance: float,
) -> list[PortfolioEntry]:
    """Sprint 5 — Réduit les positions du côté surpondéré pour ramener
    l'exposition nette dans le corridor [target - tolerance, target + tolerance].

    L'exposition nette est calculée comme (Σ longs - |Σ shorts|) / equity.
    Les positions du côté excédentaire sont réduites proportionnellement
    à leur poids actuel.
    """
    if equity <= 0 or not accepted_entries:
        return accepted_entries

    longs = [e for e in accepted_entries if getattr(e, "side", "buy") != "sell"]
    shorts = [e for e in accepted_entries if getattr(e, "side", "buy") == "sell"]

    long_notional = sum(e.target_notional for e in longs)
    short_notional = sum(abs(e.target_notional) for e in shorts)

    gross_exposure = (long_notional + short_notional) / equity
    net_exposure = (long_notional - short_notional) / equity

    lower = target - tolerance
    upper = target + tolerance

    if lower <= net_exposure <= upper:
        return accepted_entries  # déjà dans le corridor

    # Déterminer le côté à réduire
    if net_exposure > upper:
        # Trop long → réduire les longs
        excess = (net_exposure - target) * equity
        side_to_reduce = longs
        side_name = "longs"
    else:
        # Trop short → réduire les shorts
        excess = (target - net_exposure) * equity
        side_to_reduce = shorts
        side_name = "shorts"

    if not side_to_reduce or excess <= 0:
        return accepted_entries

    total_side_notional = sum(e.target_notional for e in side_to_reduce)
    if total_side_notional <= 0:
        return accepted_entries

    # Réduction proportionnelle au poids de chaque position
    reduction_ratio = min(1.0, excess / total_side_notional)
    modified: dict[str, PortfolioEntry] = {}
    total_reduced = 0.0

    for entry in side_to_reduce:
        reduced_shares = int(entry.approved_shares * (1.0 - reduction_ratio))
        reduced_notional = reduced_shares * entry.entry_price
        total_reduced += entry.target_notional - reduced_notional

        # Créer une copie modifiée (PortfolioEntry est frozen)
        from dataclasses import replace
        new_decision = Decision.REDUCED if reduced_shares < entry.approved_shares else entry.decision
        reason_suffix = f" | net_exposure={net_exposure:.2%} hors [{lower:.2%}, {upper:.2%}] → {side_name} réduits"
        new_reason = (entry.decision_reason or "") + reason_suffix
        new_reason = new_reason[:255]

        modified[entry.symbol] = replace(
            entry,
            approved_shares=float(reduced_shares),
            target_notional=reduced_notional,
            target_weight=reduced_notional / equity if equity > 0 else 0.0,
            decision=new_decision,
            decision_reason=new_reason,
        )

    # Reconstruire la liste en préservant l'ordre
    result: list[PortfolioEntry] = []
    for e in accepted_entries:
        result.append(modified.get(e.symbol, e))

    new_net = (sum(e.target_notional for e in result if getattr(e, "side", "buy") != "sell")
               - sum(abs(e.target_notional) for e in result if getattr(e, "side", "buy") == "sell")) / equity

    LOGGER.info(
        "Net exposure enforcement: net=%.2f%% → %.2f%% (target=%.2f%%, tol=±%.2f%%), "
        "%d %s réduits (ratio=%.1f%%, notional réduit=$%.0f)",
        net_exposure * 100,
        new_net * 100,
        target * 100,
        tolerance * 100,
        len(modified),
        side_name,
        reduction_ratio * 100,
        total_reduced,
    )

    return result


class PortfolioBuilder:
    """Orchestre sizing + contraintes pour construire le portefeuille cible."""

    def __init__(
        self,
        config: RiskConfig,
        pnl: PnLSnapshot | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        regime_snapshot: object | None = None,
        rotation_state: object | None = None,
        breakout_tracker: object | None = None,
        # Factor risk model (Priorité 3)
        factor_exposures: dict[str, object] | None = None,
        factor_covariance: object | None = None,
    ) -> None:
        self._cfg = config
        self._sizer = PositionSizer(config)
        self._kelly_sizer = KellySizer(config) if config.enable_kelly_sizing else None
        self._pnl = pnl
        self._circuit_breaker = circuit_breaker
        self._regime_snapshot = regime_snapshot
        self._rotation_state = rotation_state
        # Factor risk model (Priorité 3)
        self._factor_exposures: dict[str, object] = factor_exposures or {}
        self._factor_covariance: object | None = factor_covariance
        # Concentration filters (Priorité 4)
        self._concentration_trade_tracker = SymbolTradeTracker(
            max_trades=config.concentration_max_trades_per_symbol,
            window_days=config.concentration_window_calendar_days,
        )
        self._concentration_loss_tracker = ConsecutiveLossTracker(
            max_consecutive_losses=config.concentration_max_consecutive_losses,
            blacklist_duration_days=config.concentration_blacklist_duration_days,
        )
        # Anti-faux-départs (Quick Win 1) — peut être injecté depuis le CLI
        # pour persister l'état entre les runs live.
        if breakout_tracker is not None:
            self._breakout_tracker = breakout_tracker
        else:
            self._breakout_tracker = BreakoutConfirmationTracker(
                min_breakout_days=config.min_breakout_days,
            )
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
        candidates: list[SelectionScore],
        predictions: dict[str, PredictionInfo],
        win_rates: dict[str, WinRateInfo],
    ) -> list[EnrichedSelection]:
        enriched: list[EnrichedSelection] = []
        for candidate in candidates:
            prediction = predictions.get(candidate.symbol)
            win_rate = win_rates.get(candidate.symbol)
            if prediction is None:
                continue
            predicted_side = str(prediction.predicted_side or "").strip().lower()
            if predicted_side == "long" and prediction.proba_long is not None:
                side = "buy"
                effective_proba = prediction.proba_long
                conviction = _fuse_conviction_long(
                    quant_score=candidate.score_used,
                    predicted_proba=prediction.proba_long,
                )
            elif predicted_side == "short" and prediction.proba_short is not None:
                side = "sell"
                effective_proba = prediction.proba_short
                conviction = _fuse_conviction_short(
                    quant_score=candidate.score_used,
                    predicted_proba_short=prediction.proba_short,
                )
            else:
                continue
            historical_win_rate = win_rate.directional_accuracy if win_rate else None
            enriched.append(
                EnrichedSelection(
                    symbol=candidate.symbol,
                    sector=candidate.sector,
                    score_used=candidate.score_used,
                    score_source=candidate.score_source,
                    predicted_proba=effective_proba,
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
                    selection_rank=candidate.selection_rank,
                    selector_signal_mode=candidate.selector_signal_mode,
                    selection_explanation=candidate.selection_explanation,
                    selector_earnings_blackout=candidate.selector_earnings_blackout,
                    side=side,
                )
            )
        enriched.sort(
            key=lambda entry: (
                -entry.conviction_score,
                entry.symbol,
            )
        )
        return enriched

    def build(
        self,
        candidates: list[SelectionScore],
        prices: dict[str, PriceInfo],
        predictions: dict[str, PredictionInfo] | None = None,
        win_rates: dict[str, WinRateInfo] | None = None,
        return_matrix: DataFrame | None = None,
        trade_date: date | None = None,
    ) -> list[PortfolioEntry]:
        """Construit la liste des PortfolioEntry.

        Si un ``regime_snapshot`` a été fourni au constructeur et que le
        régime est défensif, les scores des candidats sont ajustés via
        :func:`selector.regime_scoring.apply_regime_weights` avant la
        construction du portefeuille.
        """
        predictions = predictions or {}
        win_rates = win_rates or {}

        # ── 0. Scoring directionnel (regime-aware + rotation factor) ──
        if self._regime_snapshot is not None and candidates:
            candidates = _apply_regime_scoring_to_candidates(
                candidates, self._regime_snapshot, rotation_state=self._rotation_state
            )

        # ── 0a. Contrat de sélection ML ternaire ────────────────────
        # Une prédiction complète est obligatoire. Elle détermine le côté;
        # ni le score ni le tagging short amont ne peuvent le faire.
        if candidates:
            before = len(candidates)
            filtered: list[SelectionScore] = []
            excluded_symbols: list[str] = []
            for c in candidates:
                sym = str(c.symbol).strip().upper()
                prediction = predictions.get(sym)
                predicted_side = str(getattr(prediction, "predicted_side", "") or "").strip().lower()
                has_directional_probability = (
                    (predicted_side == "long" and getattr(prediction, "proba_long", None) is not None)
                    or (predicted_side == "short" and getattr(prediction, "proba_short", None) is not None)
                )
                if not has_directional_probability:
                    excluded_symbols.append(sym)
                    continue
                filtered.append(replace(c, side="sell" if predicted_side == "short" else "buy"))
            if excluded_symbols:
                LOGGER.info(
                    "ML ternary selection: excluded %d symbols without a selectable prediction: %s",
                    len(excluded_symbols),
                    ", ".join(sorted(excluded_symbols)),
                )
            candidates = filtered

        # ── 0bis. Filtre anti-faux-départs (Quick Win 1) ────────────
        # P1 (2026-06-25) : les shorts ne sont plus exemptés du breakout filter.
        # Ils doivent apparaître min_breakout_days jours consécutifs comme les longs.
        if candidates and self._breakout_tracker is not None:
            trade_date_resolved = trade_date if trade_date is not None else date.today()
            candidate_symbols = [str(c.symbol).strip().upper() for c in candidates]
            self._breakout_tracker.record_selections(candidate_symbols, trade_date_resolved)
            before = len(candidates)
            candidates = [
                c for c in candidates
                if self._breakout_tracker.allow_entry(str(c.symbol))
            ]
            blocked_breakout = before - len(candidates)
            if blocked_breakout:
                LOGGER.info(
                    "Breakout filter: blocked %d candidates (min %d days not met)",
                    blocked_breakout,
                    self._breakout_tracker.min_breakout_days,
                )

        # ── 0ter. Vetos post-prédiction ─────────────────────────────
        if candidates:
            before = len(candidates)
            filtered: list[SelectionScore] = []
            for c in candidates:
                side = getattr(c, "side", "buy") or "buy"
                prediction = predictions[str(c.symbol).strip().upper()]
                if c.selector_earnings_blackout:
                    continue
                if side == "sell":
                    if prediction.proba_short is None or prediction.proba_short < self._cfg.min_proba_short:
                        continue
                else:
                    if prediction.proba_long is None or prediction.proba_long < self._cfg.min_proba_long:
                        continue
                filtered.append(c)
            candidates = filtered
            blocked_score = before - len(candidates)
            if blocked_score:
                LOGGER.info(
                    "Post-prediction vetoes blocked %d ML-ranked symbols by probability or explicit veto",
                    blocked_score,
                )

        # ── 0quat. Filtres de concentration (Priorité 4) ─────────────
        if candidates:
            candidates = _apply_concentration_filters(
                candidates,
                trade_tracker=self._concentration_trade_tracker,
                loss_tracker=self._concentration_loss_tracker,
                trade_date=trade_date if trade_date is not None else date.today(),
            )

        total_candidates = len(candidates)

        # 1. Enrichir puis trier par conviction DESC
        enriched = self._build_enriched_candidates(candidates, predictions, win_rates)
        enriched_by_symbol = {entry.symbol: entry for entry in enriched}

        # 2. Filtre corrélation (Pearson ou factoriel selon config)
        entries: list[PortfolioEntry] = []
        use_factor_filter = (
            self._cfg.enable_factor_model
            and self._cfg.use_factor_correlation_filter
            and self._factor_covariance is not None
            and bool(self._factor_exposures)
        )
        if use_factor_filter:
            # Phase E : filtre de corrélation basé sur le modèle factoriel
            from risk_management.factor_model import (
                FactorCovariance,
                FactorExposures,
                filter_by_factor_correlation,
            )
            fc = self._factor_covariance
            if isinstance(fc, FactorCovariance):
                typed_exposures: dict[str, FactorExposures] = {}
                for sym, exp in self._factor_exposures.items():
                    if isinstance(exp, FactorExposures):
                        typed_exposures[str(sym)] = exp
                retained, factor_rejections = filter_by_factor_correlation(
                    enriched,
                    typed_exposures,
                    fc,
                    max_factor_correlation=self._cfg.factor_correlation_threshold,
                )
                for rej in factor_rejections:
                    ec = enriched_by_symbol.get(rej.rejected_symbol)
                    if ec is None:
                        continue
                    reason = (
                        f"corrélation factorielle {rej.implied_correlation:.2f} "
                        f"> {rej.threshold} avec {rej.blocker_symbol}"
                    )[:255]
                    entries.append(self._make_entry_v2(
                        ec, prices.get(ec.symbol), 0, 0, Decision.REJECTED, reason,
                        decision_reason_code=DecisionReasonCode.FACTOR_CORRELATION_FILTER,
                        correlation_blocker=rej.blocker_symbol,
                        correlation_value=rej.implied_correlation,
                    ))
            else:
                retained = enriched
        elif return_matrix is not None and not return_matrix.empty:
            retained, rejections = filter_correlated_signed(
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

        # ── 2bis. Contraintes factorielles (Phase D — Priorité 3) ────────
        factor_check_performed = False
        if (
            self._cfg.enable_factor_model
            and self._factor_covariance is not None
            and bool(self._factor_exposures)
            and retained
        ):
            from risk_management.factor_model import (
                FactorCovariance,
                FactorExposures,
                check_factor_constraints,
            )
            fc = self._factor_covariance
            if isinstance(fc, FactorCovariance):
                typed_exposures: dict[str, FactorExposures] = {}
                for sym, exp in self._factor_exposures.items():
                    if isinstance(exp, FactorExposures):
                        typed_exposures[str(sym)] = exp
                factor_result = check_factor_constraints(
                    retained,
                    typed_exposures,
                    fc,
                    constraints={
                        "max_portfolio_beta": self._cfg.max_portfolio_beta,
                        "max_size_concentration": self._cfg.max_factor_concentration_pct,
                        "max_momentum_concentration": self._cfg.max_factor_concentration_pct,
                        "min_factor_diversification": self._cfg.min_factor_diversification,
                    },
                )
                factor_check_performed = True
                if factor_result.has_violations:
                    LOGGER.warning(
                        "Factor constraints violations: %s",
                        "; ".join(factor_result.violations),
                    )
                    # Filtrer les candidats qui aggravent les violations
                    before_filter = len(retained)
                    retained = factor_result.filtered_candidates
                    if len(retained) < before_filter:
                        LOGGER.info(
                            "Factor constraints: filtered %d → %d candidates",
                            before_filter, len(retained),
                        )
                if factor_result.decomposition is not None:
                    from risk_management.factor_model import format_risk_decomposition
                    LOGGER.info(
                        "Factor risk decomposition:\n%s",
                        format_risk_decomposition(factor_result.decomposition),
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
        minimum_viable_shares = QUANTITY_EPSILON if self._cfg.allow_fractional_shares else 1.0

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

            if sizing.proposed_shares < minimum_viable_shares:
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

            approved = normalize_share_quantity(
                checker.check_position_size(
                    ec.symbol,
                    sizing.proposed_shares,
                    pi.last_close,
                    side=ec.side,
                    adv_usd=pi.adv_usd,
                )
            )
            if approved < minimum_viable_shares:
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

            decision = Decision.ACCEPTED if abs(approved - sizing.proposed_shares) <= QUANTITY_EPSILON else Decision.REDUCED
            reason = "OK" if decision == Decision.ACCEPTED else checker.get_last_decision_reason()
            reason_code = DecisionReasonCode.OK if decision == Decision.ACCEPTED else checker.get_last_decision_reason_code()
            checker.accept(ec.symbol, ec.sector, approved, pi.last_close, side=ec.side)
            accepted_rank += 1

            notional = approved * pi.last_close
            weight = notional / equity if equity > 0 else 0.0
            risk_per_share = pi.atr_20 * self._cfg.atr_stop_multiple if pi.atr_20 is not None and pi.atr_20 > 0 else None
            risk_budget_dollars = equity * self._cfg.risk_per_trade_pct if equity > 0 else None
            initial_risk_dollars = approved * risk_per_share if risk_per_share is not None else None
            stop_price_initial = compute_initial_stop_price(
                ec.side,
                pi.last_close,
                risk_per_share=risk_per_share,
            )

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
                    kf = min(max(0.0, raw) * cfg.kelly_fraction_multiplier, cfg.max_kelly_fraction, cfg.max_position_weight)

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
                selection_rank=ec.selection_rank,
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
                side=ec.side,
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

        # ── P3 : Contrainte ADV agrégée au niveau portefeuille ──────────
        accepted_entries = [e for e in entries if e.decision in (Decision.ACCEPTED, Decision.REDUCED)]
        if accepted_entries:
            advs = [
                prices[entry.symbol].adv_usd
                for entry in accepted_entries
                if entry.symbol in prices and prices[entry.symbol].adv_usd is not None
            ]
            if advs:
                total_notional = sum(e.target_notional for e in accepted_entries)
                avg_adv = sum(advs) / len(advs)
                if avg_adv > 0 and total_notional > 0.05 * avg_adv:
                    LOGGER.warning(
                        "Portfolio notional ($%.0f) > 5%% ADV agrégé ($%.0f) — risque de liquidité en cas de liquidation",
                        total_notional,
                        avg_adv,
                    )

        # ── Sprint 5 : Contrainte de neutralité nette ──────────────────
        if self._cfg.enforce_net_exposure and accepted_entries:
            accepted_entries = _enforce_net_exposure_neutrality(
                accepted_entries,
                equity=equity,
                target=self._cfg.net_exposure_target,
                tolerance=self._cfg.net_exposure_tolerance,
            )
            # Re-sync entries list: replace modified accepted entries
            entry_by_symbol = {e.symbol: e for e in entries}
            for ae in accepted_entries:
                entry_by_symbol[ae.symbol] = ae
            entries = list(entry_by_symbol.values())

        return entries

    # ------------------------------------------------------------------

    @staticmethod
    def _make_entry_v2(
        ec: EnrichedSelection,
        pi: PriceInfo | None,
        proposed: float,
        approved: float,
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
            selection_rank=ec.selection_rank,
            score_snapshot_date=ec.snapshot_date,
            price_asof_date=pi.price_asof_date if pi else None,
            atr_asof_date=pi.atr_asof_date if pi else None,
            prediction_asof_date=ec.prediction_asof_date,
            ml_metrics_asof_date=ec.ml_metrics_asof_date,
            selector_signal_mode=ec.selector_signal_mode,
            selection_explanation=ec.selection_explanation,
            selector_earnings_blackout=ec.selector_earnings_blackout,
            side=ec.side,
        )
