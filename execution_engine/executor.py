"""Production Executor — orchestrateur principal du module execution_engine.

Architecture Synthetic Bracket :
    Le broker Alpaca ne supporte PAS trailing_stop comme leg d'un bracket natif.
    Le pattern est donc un "synthetic bracket" :
      1. Soumettre l'ordre d'entree (market ou limit)
      2. Poller / attendre le fill
      3. Apres fill : soumettre separement un trailing_stop + un limit take-profit
      4. Gerer le OCO logique cote applicatif (si l'un est rempli, cancel l'autre)
"""
from __future__ import annotations

from dataclasses import replace
import logging
import time
import uuid
from datetime import date, datetime, timezone
from collections import Counter
from typing import Any, Callable, Optional

from core.run_summary import attach_live_progress
from execution_engine.account_state import (
    _AccountConstraintState,
    InvalidBrokerSnapshotError,
    build_account_constraint_state as _build_account_constraint_state_impl,
    estimate_intent_notional as _estimate_intent_notional_impl,
    reserve_account_capacity_for_intent as _reserve_account_capacity_for_intent_impl,
    safe_float as _safe_float_impl,
    should_defer_children as _should_defer_children_impl,
)
from execution_engine.audit import (
    build_run_id,
    event_to_db_dict,
    make_event,
)
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.broker_state_sync import BrokerStateSynchronizer
from execution_engine.children_submission import (
    submit_children as _submit_children_impl,
    submit_rebalance_orders as _submit_rebalance_orders_impl,
)
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    ExecutionEvent,
    ExecutionFill,
    IntentRole,
    OrderIntent,
    OrderStatus,
    ReconcileDiff,
    ReconciliationStatus,
)
from execution_engine.oco_manager import OcoManager
from execution_engine.order_intents import (
    apply_live_leverage_to_targets,
    build_entry_intents,
    filter_targets_by_live_regime_guards,
    intent_to_alpaca_payload,
    resolve_initial_stop_price,
    split_entry_intents_by_gap_filter,
)
from execution_engine.protection_transition import (
    maybe_activate_dynamic_trailing as _maybe_activate_dynamic_trailing_impl,
)
from execution_engine.reconciliation import reconcile_execution_state
from execution_engine.state_machine import is_terminal
from execution_engine.tca import build_tca_summary, compute_implementation_shortfall, compute_slippage_bps
from service.alpaca.trading_client import BrokerApiError

LOGGER = logging.getLogger(__name__)


# Sprint S7 - extracted to ``execution_engine.account_state``.
# Re-exported here for backwards compatibility (tests/test_execution_engine_executor.py).


class ProductionExecutor:
    """Orchestrateur de l execution."""

    def __init__(
        self,
        config: ExecutionConfig,
        repo: ExecutionRepository,
        broker: BrokerAdapter,
        oco: OcoManager,
        circuit_breaker: Optional[Any] = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self._cfg = config
        self._repo = repo
        self._broker = broker
        self._oco = oco
        self._circuit_breaker = circuit_breaker
        self._progress_callback = progress_callback
        # ── Point 9.6 : données de réévaluation pré-soumission ─────
        self._pre_submission_spreads: dict[str, object] | None = None
        self._pre_submission_borrows: dict[str, object] | None = None
        self._pre_submission_adv: dict[str, float] | None = None
        self._pre_submission_daily_vol: dict[str, float] | None = None
        # ── Point 11 : fingerprints de décision pour traçabilité ──
        self._decision_fingerprints: dict[str, str] | None = None

    def set_pre_submission_data(
        self,
        *,
        spreads: dict[str, object] | None = None,
        borrows: dict[str, object] | None = None,
        adv: dict[str, float] | None = None,
        daily_vol: dict[str, float] | None = None,
    ) -> None:
        """Injecte les données de marché pour la réévaluation pré-soumission (Point 9.6).

        Appelé avant ``execute_run()`` pour fournir les snapshots spread/borrow/ADV
        frais qui seront utilisés pour revérifier chaque intent juste avant
        soumission broker.

        Parameters
        ----------
        spreads : dict[str, SpreadSnapshot] | None
            Quotes bid/ask par symbole.
        borrows : dict[str, BorrowSnapshot] | None
            Statuts borrow par symbole.
        adv : dict[str, float] | None
            ADV 20j en dollars par symbole.
        daily_vol : dict[str, float] | None
            Volatilité quotidienne en % par symbole.
        """
        self._pre_submission_spreads = spreads
        self._pre_submission_borrows = borrows
        self._pre_submission_adv = adv
        self._pre_submission_daily_vol = daily_vol

    def set_decision_fingerprints(
        self,
        fingerprints: dict[str, str],
    ) -> None:
        """Injecte les fingerprints de décision par symbole (Point 11).

        Appelé avant ``execute_run()`` pour associer chaque ``OrderIntent``
        à la décision de risque qui l'a produite.
        """
        self._decision_fingerprints = fingerprints

    def _emit_progress(
        self,
        metrics: dict[str, Any],
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        item: str | None = None,
        unit: str = "symboles",
    ) -> None:
        if not callable(self._progress_callback):
            return
        payload = dict(metrics)
        payload["last_phase"] = phase
        self._progress_callback(
            attach_live_progress(
                payload,
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit=unit,
                item=item,
            )
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def execute_run(
        self,
        risk_run_id: str | None = None,
        trade_date: date | None = None,
    ) -> dict[str, Any]:
        exec_run_id = build_run_id()
        # Métrique Prometheus : incrémente le compteur de runs
        try:
            from service.prometheus_metrics import bump_execution_run
            bump_execution_run()
        except Exception:
            pass
        resolved_account_id = self._cfg.resolved_account_id
        metrics: dict[str, Any] = {
            "exec_run_id": exec_run_id,
            "risk_run_id": risk_run_id,
            "trade_date": trade_date.isoformat() if hasattr(trade_date, "isoformat") else trade_date,
            "status": "RUNNING",
            "targets": 0, "submitted": 0, "filled": 0, "failed": 0, "skipped": 0,
            "rebalance_submitted": 0, "rebalance_failed": 0,
            "constraint_blocked": 0, "children_deferred": 0,
            "child_take_profit_orders_submitted": 0,
            "child_initial_stop_orders_submitted": 0,
            "child_trailing_stop_orders_submitted": 0,
            "child_order_submit_failures": 0,
            "targets_eligible_for_dynamic_trailing": 0,
            "dynamic_trailing_trigger_checks": 0,
            "dynamic_trailing_activations": 0,
            "dynamic_trailing_timeouts": 0,
            "dynamic_trailing_cancel_failures": 0,
        }
        events: list[ExecutionEvent] = []
        fills: list[ExecutionFill] = []
        consecutive_failures = 0
        lock_acquired = False

        try:
            # Phase 1 — Init
            events.append(make_event(exec_run_id, EventType.RUN_STARTED, f"Exec run {exec_run_id} started"))
            lock_acquired = self._repo.acquire_execution_lock(account_id=resolved_account_id, exec_run_id=exec_run_id)
            if not lock_acquired:
                events.append(make_event(
                    exec_run_id,
                    EventType.RUN_LOCKED,
                    f"Execution already active for account_id={resolved_account_id}",
                    payload={"account_id": resolved_account_id},
                ))
                metrics["status"] = "ABORTED"
                return metrics

            # Phase 2 — Pre-flight
            targets = self._repo.load_portfolio_targets(
                risk_run_id=risk_run_id,
                trade_date=trade_date,
                account_id=resolved_account_id,
            )
            if not targets:
                events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "No portfolio targets found"))
                metrics["status"] = "ABORTED"
                self._emit_progress(
                    metrics,
                    current=0,
                    total=1,
                    label="⚙️ Progression execution — pré-check",
                    phase="precheck",
                    unit="étapes",
                )
                return metrics

            actual_risk_run_id = targets[0].risk_run_id
            actual_trade_date = trade_date or targets[0].trade_date
            if actual_trade_date is not None:
                try:
                    previous_closes = self._repo.load_previous_closes_asof(
                        symbols=[str(target.symbol).strip().upper() for target in targets],
                        trade_date=actual_trade_date,
                    )
                except Exception:
                    previous_closes = {}
                    LOGGER.debug("Impossible de charger les previous_close pour le gap filter live.", exc_info=True)
                if not isinstance(previous_closes, dict):
                    previous_closes = {}
                if previous_closes:
                    enriched_targets = []
                    for target in targets:
                        symbol_upper = str(target.symbol).strip().upper()
                        previous_close = previous_closes.get(symbol_upper)
                        if previous_close is None:
                            enriched_targets.append(target)
                            continue
                        enriched_targets.append(replace(target, previous_close=float(previous_close)))
                    targets = enriched_targets
            loaded_targets_count = len(targets)

            target_by_intent_id: dict[str, Any] = {}

            self._repo.insert_execution_run(
                exec_run_id=exec_run_id,
                risk_run_id=actual_risk_run_id,
                trade_date=actual_trade_date or targets[0].trade_date,
                broker_mode=self._cfg.broker_mode,
                dry_run=self._cfg.dry_run,
                total_targets=len(targets),
                account_id=resolved_account_id,
                execution_profile=self._cfg.execution_profile,
                submission_window=self._cfg.submission_window,
            )

            # Circuit breaker check (injection)
            if self._circuit_breaker is not None:
                try:
                    # E23 — breaker adaptatif (b1-b4) : alimenter régime SPY du jour
                    # + machine d'état (equity / peak) AVANT is_active()/allocation_scale().
                    # B0 : no-op (is_adaptive=False), comportement historique intact.
                    if getattr(self._circuit_breaker, "is_adaptive", False):
                        try:
                            _bd = getattr(self._cfg, "trade_date", None) or actual_trade_date
                            if _bd is None and targets:
                                _bd = targets[0].trade_date
                            _pnl = getattr(self._circuit_breaker, "_pnl", None)
                            _eq_now = float(getattr(_pnl, "portfolio_current_value", 0.0) or 0.0)
                            _hwm_now = float(getattr(_pnl, "portfolio_high_watermark", 0.0) or 0.0)
                            _hwm_now = max(_hwm_now, _eq_now)
                            if hasattr(self._circuit_breaker, "set_spy_regime"):
                                self._circuit_breaker.set_spy_regime(_bd)
                            if hasattr(self._circuit_breaker, "update_adaptive"):
                                self._circuit_breaker.update_adaptive(_eq_now, _hwm_now)
                        except Exception as exc:  # noqa: BLE001 — best-effort
                            LOGGER.warning("Adaptive breaker update failed: %s", exc)
                    if self._circuit_breaker.is_active():
                        events.append(make_event(exec_run_id, EventType.CIRCUIT_BREAKER_ACTIVE, "CB active — aborting"))
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        metrics["status"] = "ABORTED"
                        self._emit_progress(
                            metrics,
                            current=1,
                            total=1,
                            label="⚙️ Progression execution — arrêt circuit breaker",
                            phase="precheck",
                            unit="étapes",
                        )
                        return metrics
                    # Mode dégradé (allocation réduite) : on continue mais on le logue
                    if hasattr(self._circuit_breaker, "allocation_scale"):
                        # Mise à jour du streak de recovery avant calcul de l'échelle
                        _entry_mode = getattr(self._cfg, "entry_mode", None)
                        _equity = (
                            float(self._circuit_breaker._pnl.portfolio_current_value)
                            if getattr(self._circuit_breaker, "_pnl", None) is not None
                            and self._circuit_breaker._pnl.portfolio_current_value is not None
                            else 0.0
                        )
                        if hasattr(self._circuit_breaker, "update_regime_streak"):
                            self._circuit_breaker.update_regime_streak(_entry_mode, _equity)
                        _scale = self._circuit_breaker.allocation_scale(entry_mode=_entry_mode)
                        if _scale < 1.0:
                            LOGGER.warning(
                                "Circuit breaker mode dégradé actif — allocation_scale=%.2f%%",
                                _scale * 100.0,
                            )
                            events.append(make_event(
                                exec_run_id,
                                EventType.CIRCUIT_BREAKER_ACTIVE,
                                f"CB degraded mode — allocation_scale={_scale:.2%}",
                            ))
                            metrics["cb_allocation_scale"] = _scale

                    # Force-close : liquider partiellement les positions si le breaker trippe
                    if (
                        self._cfg.force_close_on_breaker
                        and self._circuit_breaker is not None
                        and hasattr(self._circuit_breaker, "just_tripped")
                        and self._circuit_breaker.just_tripped()
                    ):
                        force_pct = float(getattr(self._cfg, "force_close_pct", 0.50))
                        LOGGER.warning(
                            "Force-close partiel (%.0f%%) actif — liquidation des positions les plus perdantes",
                            force_pct * 100,
                        )
                        try:
                            positions = self._broker.list_positions()
                            # Sprint 3 — tri side-aware : on liquide les plus gros perdants
                            # Pour les shorts, le PnL est correctement signé (positif si gain)
                            pos_with_pnl = []
                            for pos in positions:
                                symbol = str(getattr(pos, "symbol", ""))
                                side = str(getattr(pos, "side", "long") or "long").strip().lower()
                                qty = float(getattr(pos, "qty", 0) or 0)
                                unrealized = float(getattr(pos, "unrealized_pl", 0) or 0)
                                # qty absolue > 0 (long ou short)
                                abs_qty = abs(qty)
                                if abs_qty > 0 and symbol:
                                    pos_with_pnl.append((symbol, abs_qty, unrealized, side))
                            # Trier par PnL croissant (pires pertes d'abord)
                            pos_with_pnl.sort(key=lambda x: x[2])
                            n_close = max(1, int(len(pos_with_pnl) * force_pct + 0.5))
                            to_close = pos_with_pnl[:n_close]
                            
                            for symbol, qty, _, pos_side in to_close:
                                # Sprint 3 — close side directionnel
                                if pos_side in ("sell", "short"):
                                    close_side = "buy"  # buy-to-cover
                                else:
                                    close_side = "sell"
                                LOGGER.warning("Force-close: liquidating %s (side=%s) x%.4f -> %s",
                                              symbol, pos_side, qty, close_side)
                                try:
                                    self._broker.submit_order(
                                        symbol=symbol, qty=qty, side=close_side, order_type="market",
                                    )
                                except Exception as exc:
                                    LOGGER.error("Force-close failed for %s: %s", symbol, exc)
                            
                            events.append(make_event(
                                exec_run_id,
                                EventType.CIRCUIT_BREAKER_ACTIVE,
                                f"Force-close partiel ({force_pct:.0%}): {n_close}/{len(pos_with_pnl)} positions liquidées",
                            ))
                        except Exception as exc:
                            LOGGER.error("Force-close broker error: %s", exc)

                except Exception as exc:
                    LOGGER.warning("Circuit breaker check failed: %s", exc)

            # Market hours check
            if not self._cfg.allow_outside_rth and not self._cfg.dry_run:
                try:
                    if not self._broker.is_market_open():
                        events.append(make_event(exec_run_id, EventType.PRECHECK_FAILED, "Market closed"))
                        self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                        metrics["status"] = "ABORTED"
                        self._emit_progress(
                            metrics,
                            current=1,
                            total=1,
                            label="⚙️ Progression execution — marché fermé",
                            phase="precheck",
                            unit="étapes",
                        )
                        return metrics
                except Exception:
                    LOGGER.warning("Cannot check market clock — proceeding")

            try:
                account_state = self._build_account_constraint_state()
            except InvalidBrokerSnapshotError as exc:
                LOGGER.error(
                    "Préflight execution avorté — snapshot broker invalide | account=%s broker_mode=%s : %s",
                    self._cfg.resolved_account_id,
                    self._cfg.broker_mode,
                    exc,
                )
                events.append(make_event(
                    exec_run_id,
                    EventType.PRECHECK_FAILED,
                    f"Snapshot broker rejeté: {exc}",
                    payload={
                        "reason": "invalid_broker_snapshot",
                        "account_id": self._cfg.resolved_account_id,
                        "broker_mode": self._cfg.broker_mode,
                    },
                ))
                self._repo.update_execution_run_status(exec_run_id, "ABORTED")
                metrics["status"] = "ABORTED"
                self._emit_progress(
                    metrics,
                    current=1,
                    total=1,
                    label="⚙️ Progression execution — snapshot broker invalide",
                    phase="precheck",
                    unit="étapes",
                )
                return metrics
            events.append(make_event(
                exec_run_id,
                EventType.ACCOUNT_CONSTRAINT_APPLIED,
                (
                    f"Account constraints: type={account_state.account_type} "
                    f"swing_only={account_state.swing_only}"
                ),
                payload={
                    "account_type": account_state.account_type,
                    "swing_only": account_state.swing_only,
                    "equity": account_state.equity,
                    "buying_power_available": account_state.buying_power_available,
                    "settled_cash_available": account_state.settled_cash_available,
                    "daytrade_count": account_state.daytrade_count,
                    "leverage_feature_enabled": account_state.leverage_feature_enabled,
                    "leverage_active": account_state.leverage_active,
                    "effective_leverage": account_state.effective_leverage,
                    "leverage_configured_max": account_state.leverage_configured_max,
                    "leverage_target_budget": account_state.leverage_target_budget,
                    "leverage_broker_buying_power": account_state.leverage_broker_buying_power,
                    "leverage_buying_power_field": account_state.leverage_buying_power_field,
                    "leverage_reason": account_state.leverage_reason,
                },
            ))
            metrics["account_equity"] = round(float(account_state.equity), 2)
            metrics["buying_power_available"] = round(float(account_state.buying_power_available), 2)
            metrics["settled_cash_available"] = round(float(account_state.settled_cash_available), 2)
            metrics["daytrade_count"] = int(account_state.daytrade_count)
            metrics["leverage_feature_enabled"] = bool(account_state.leverage_feature_enabled)
            metrics["leverage_active"] = bool(account_state.leverage_active)
            metrics["leverage_configured_max"] = round(float(account_state.leverage_configured_max), 4)
            metrics["effective_leverage"] = round(float(account_state.effective_leverage), 4)
            metrics["leverage_target_budget"] = round(float(account_state.leverage_target_budget), 2)
            metrics["leverage_broker_buying_power"] = (
                round(float(account_state.leverage_broker_buying_power), 2)
                if account_state.leverage_broker_buying_power is not None
                else None
            )
            metrics["leverage_buying_power_field"] = account_state.leverage_buying_power_field
            metrics["leverage_reason"] = account_state.leverage_reason
            self._snapshot_account_constraints(exec_run_id, account_state)

            # Sprint S9 — Cash ledger consistency check (best-effort)
            try:
                from execution_engine.cash_ledger_guard import check_cash_ledger_consistency
                # Récupère la market value depuis le broker si disponible
                _market_value = 0.0
                try:
                    positions = self._broker.list_positions()
                    _market_value = sum(
                        abs(float(getattr(p, "market_value", 0) or 0))
                        for p in (positions or [])
                    )
                except Exception:
                    LOGGER.debug("Cash ledger guard: impossible de récupérer la market value.", exc_info=True)
                check_cash_ledger_consistency(
                    settled_cash=float(account_state.settled_cash_available),
                    unsettled_cash=0.0,  # sera enrichi quand le broker le fournira
                    market_value=_market_value,
                    reported_equity=float(account_state.equity),
                    account_id=resolved_account_id,
                )
            except Exception:
                LOGGER.debug("Cash ledger guard indisponible.", exc_info=True)

            targets, leverage_target_summary = apply_live_leverage_to_targets(
                targets=targets,
                effective_leverage=account_state.effective_leverage,
                active=account_state.leverage_active,
                allow_fractional_shares=self._cfg.allow_fractional_shares,
            )
            metrics["leverage_target_scale"] = round(float(leverage_target_summary["target_scale"]), 4)
            metrics["targets_scaled_for_leverage"] = int(leverage_target_summary["scaled_targets"])
            metrics["gross_exposure_before_leverage"] = round(float(leverage_target_summary["gross_exposure_before"]), 6)
            metrics["gross_exposure_after_leverage"] = round(float(leverage_target_summary["gross_exposure_after"]), 6)
            metrics["total_target_notional_before_leverage"] = round(float(leverage_target_summary["total_target_notional_before"]), 2)
            metrics["total_target_notional_after_leverage"] = round(float(leverage_target_summary["total_target_notional_after"]), 2)
            events.append(make_event(
                exec_run_id,
                EventType.LEVERAGE_EVALUATED,
                (
                    f"Leverage {'applied' if account_state.leverage_active else 'inactive'}: "
                    f"effective={account_state.effective_leverage:.2f}x "
                    f"target_scale={float(leverage_target_summary['target_scale']):.2f}x "
                    f"scaled_targets={int(leverage_target_summary['scaled_targets'])}"
                ),
                payload={
                    "leverage_feature_enabled": account_state.leverage_feature_enabled,
                    "leverage_active": account_state.leverage_active,
                    "effective_leverage": account_state.effective_leverage,
                    "leverage_configured_max": account_state.leverage_configured_max,
                    "leverage_target_scale": leverage_target_summary["target_scale"],
                    "scaled_targets": leverage_target_summary["scaled_targets"],
                    "gross_exposure_before": leverage_target_summary["gross_exposure_before"],
                    "gross_exposure_after": leverage_target_summary["gross_exposure_after"],
                    "total_target_notional_before": leverage_target_summary["total_target_notional_before"],
                    "total_target_notional_after": leverage_target_summary["total_target_notional_after"],
                    "leverage_reason": account_state.leverage_reason,
                },
            ))
            fractionable_by_symbol: dict[str, bool] = {}
            if self._cfg.allow_fractional_shares and targets:
                try:
                    fractionable_by_symbol = self._repo.load_fractionable_asset_map(
                        [str(target.symbol).strip().upper() for target in targets]
                    )
                except Exception:
                    LOGGER.debug("Impossible de charger les métadonnées fractionable pour les garde-fous live.", exc_info=True)
            filtered_targets, blocked_by_regime_guards = filter_targets_by_live_regime_guards(
                targets=targets,
                config=self._cfg,
                fractionable_by_symbol=fractionable_by_symbol,
            )
            if blocked_by_regime_guards:
                metrics["targets_loaded"] = loaded_targets_count
                metrics["targets_blocked_by_regime_guards"] = len(blocked_by_regime_guards)
                for blocked in blocked_by_regime_guards:
                    reason = str(blocked.get("reason") or "regime_guard")
                    metrics[f"skipped_by_{reason}"] = int(metrics.get(f"skipped_by_{reason}", 0)) + 1
                    events.append(make_event(
                        exec_run_id,
                        EventType.INTENT_SKIPPED_ACCOUNT_CONSTRAINT,
                        f"SkippedByRegimeGuard[{reason}]: {blocked.get('symbol')}",
                        symbol=str(blocked.get("symbol") or "") or None,
                        payload=dict(blocked),
                    ))
                targets = filtered_targets
            metrics.setdefault("targets_loaded", loaded_targets_count)
            metrics["targets"] = len(targets)
            metrics["total_target_notional"] = round(sum(float(t.target_notional or (t.target_shares * t.entry_price)) for t in targets), 2)
            metrics["total_initial_risk_dollars"] = round(sum(float(t.initial_risk_dollars or 0.0) for t in targets), 2)
            metrics["total_risk_budget_dollars"] = round(sum(float(t.risk_budget_dollars or 0.0) for t in targets), 2)
            metrics["max_target_weight"] = round(max((float(t.target_weight) for t in targets), default=0.0), 4)
            metrics["targets_with_risk_controls"] = sum(1 for t in targets if t.stop_price_initial is not None or (t.risk_per_share or 0.0) > 0)
            metrics["targets_with_broker_initial_stop"] = sum(
                1 for t in targets
                if resolve_initial_stop_price(float(t.entry_price), t) is not None
            )
            metrics["selector_signal_mode_counts"] = dict(
                Counter(
                    str(getattr(target, "selector_signal_mode", "") or "").strip() or "unknown"
                    for target in targets
                )
            )
            metrics["selector_rank_available"] = sum(
                1 for target in targets if getattr(target, "selection_rank", None) is not None
            )
            metrics["selector_rank_coverage_pct"] = round(
                (float(metrics["selector_rank_available"]) / float(len(targets))) * 100.0,
                2,
            ) if targets else 0.0
            metrics["selector_earnings_blackout_targets"] = sum(
                1
                for target in targets
                if int(getattr(target, "selector_earnings_blackout", 0) or 0) > 0
            )
            metrics["targets_eligible_for_dynamic_trailing"] = int(metrics["targets_with_broker_initial_stop"]) if self._cfg.enable_dynamic_trailing_transition else 0
            metrics["targets_with_trailing_fallback"] = max(
                len(targets) - int(metrics["targets_with_broker_initial_stop"]),
                0,
            )
            metrics["stale_price_targets"] = sum(
                1 for t in targets
                if t.price_asof_date is not None and actual_trade_date is not None and t.price_asof_date < actual_trade_date
            )
            target_by_symbol = {t.symbol: t for t in targets}
            events.append(make_event(exec_run_id, EventType.PRECHECK_OK, f"{len(targets)} targets loaded"))
            if metrics["stale_price_targets"] > 0:
                events.append(make_event(
                    exec_run_id,
                    EventType.PRECHECK_OK,
                    f"WARNING: {metrics['stale_price_targets']} targets utilisent un price_asof_date antérieur au trade_date",
                    payload={"stale_price_targets": metrics["stale_price_targets"]},
                ))
            self._emit_progress(
                metrics,
                current=len(targets),
                total=max(len(targets), 1),
                label="⚙️ Progression execution — pré-check & chargement des cibles",
                phase="precheck",
            )
            try:
                self._repo.snapshot_execution_targets(
                    exec_run_id=exec_run_id,
                    account_id=resolved_account_id,
                    targets=targets,
                )
            except Exception as exc:
                LOGGER.debug("Target snapshot skipped: %s", exc)

            # Phase 2b — Corporate actions : alerter sur splits/dividendes pending
            try:
                from corporate_actions.db_io import CorporateActionRepository
                ca_repo = CorporateActionRepository(engine=self._repo.engine)
                pending_events = ca_repo.load_pending_events(as_of=actual_trade_date)
                if pending_events:
                    target_symbols = {t.symbol.upper() for t in targets}
                    pending_for_targets = [e for e in pending_events if e.symbol.upper() in target_symbols]
                    if pending_for_targets:
                        symbols_str = ", ".join(sorted({e.symbol for e in pending_for_targets}))
                        LOGGER.warning(
                            "Corporate actions pending NON appliquees pour %d symboles cibles : %s. "
                            "Les quantites/prix peuvent etre obsoletes. Executer 'python -m corporate_actions apply' avant.",
                            len(pending_for_targets), symbols_str,
                        )
                        events.append(make_event(
                            exec_run_id, EventType.PRECHECK_OK,
                            f"WARNING: {len(pending_for_targets)} corporate actions pending pour {symbols_str}",
                        ))
            except Exception as exc:
                LOGGER.debug("Corporate actions check skipped: %s", exc)

            # Phase 3 — Build intents, filter duplicates
            entry_intents = build_entry_intents(
                targets, self._cfg, exec_run_id,
                decision_fingerprints=self._decision_fingerprints,
            )
            for target, intent in zip(targets, entry_intents):
                target_by_intent_id[str(intent.intent_id)] = target
            if entry_intents and float(getattr(self._cfg, "max_entry_gap_pct", 0.0) or 0.0) > 0.0:
                latest_prices: dict[str, float] = {}
                for target in targets:
                    try:
                        latest_price = self._broker.get_latest_market_price(target.symbol)
                    except Exception:
                        latest_price = None
                    if latest_price is not None:
                        latest_prices[str(target.symbol).strip().upper()] = float(latest_price)
                entry_intents, blocked_by_gap = split_entry_intents_by_gap_filter(
                    targets=targets,
                    intents=entry_intents,
                    config=self._cfg,
                    latest_market_prices=latest_prices,
                )
                if blocked_by_gap:
                    metrics["skipped_by_gap_filter"] = len(blocked_by_gap)
                    for blocked in blocked_by_gap:
                        events.append(make_event(
                            exec_run_id,
                            EventType.INTENT_SKIPPED_ACCOUNT_CONSTRAINT,
                            f"SkippedByGapFilter: {blocked.get('symbol')}",
                            symbol=str(blocked.get("symbol") or "") or None,
                            payload=dict(blocked),
                        ))
            # Axe C — court-circuit des nouvelles entrées si entry_mode bloque
            if self._cfg.blocks_new_entries and entry_intents:
                LOGGER.warning(
                    "execution_engine: entry_mode=%s -> %d entry intents court-circuitées.",
                    self._cfg.entry_mode, len(entry_intents),
                )
                for intent in entry_intents:
                    events.append(make_event(
                        exec_run_id, EventType.INTENT_SKIPPED_DUPLICATE,
                        f"SkippedByRegime[{self._cfg.entry_mode}]: {intent.symbol}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                metrics["skipped_by_regime"] = len(entry_intents)
                entry_intents = []
            existing_keys: set[str] = set()
            if not self._cfg.dry_run:
                try:
                    existing_keys = self._repo.load_submitted_idempotency_keys(exec_run_id)
                except Exception:
                    pass

            new_intents: list[OrderIntent] = []
            for intent in entry_intents:
                if intent.idempotency_key in existing_keys:
                    events.append(make_event(
                        exec_run_id, EventType.INTENT_SKIPPED_DUPLICATE,
                        f"Duplicate: {intent.symbol}", symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    metrics["skipped"] += 1
                else:
                    events.append(make_event(
                        exec_run_id, EventType.INTENT_BUILT,
                        f"Intent: {intent.symbol} {intent.side} {intent.qty}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    new_intents.append(intent)
            self._emit_progress(
                metrics,
                current=len(new_intents),
                total=max(len(entry_intents), 1),
                label="⚙️ Progression execution — construction des intents",
                phase="build_intents",
            )

            # Phase 4 — Submit entries
            submitted_orders: dict[str, tuple[OrderIntent, BrokerOrder]] = {}
            batch_count = 0
            submit_total = max(len(new_intents), 1)
            submit_processed = 0
            for intent in new_intents:
                submit_processed += 1
                if not self._reserve_account_capacity_for_intent(intent, account_state, exec_run_id, events, metrics):
                    self._emit_progress(
                        metrics,
                        current=submit_processed,
                        total=submit_total,
                        label="⚙️ Progression execution — soumission des ordres d'entrée",
                        phase="submit_entries",
                        item=intent.symbol,
                    )
                    continue

                # Kill switch
                if self._cfg.enable_kill_switch and consecutive_failures >= self._cfg.max_consecutive_failures:
                    events.append(make_event(exec_run_id, EventType.KILL_SWITCH_ACTIVATED,
                                             f"Kill switch after {consecutive_failures} failures"))
                    # Métrique Prometheus
                    try:
                        from service.prometheus_metrics import set_kill_switch_active
                        set_kill_switch_active(True)
                    except Exception:
                        pass
                    # Alerte système multi-canal
                    try:
                        from service.alerting import send_system_alert
                        send_system_alert(
                            event="KILL_SWITCH_ACTIVATED",
                            payload={
                                "exec_run_id": exec_run_id,
                                "consecutive_failures": consecutive_failures,
                                "max_consecutive_failures": self._cfg.max_consecutive_failures,
                                "account_id": resolved_account_id,
                            },
                            severity="critical",
                        )
                    except Exception:
                        LOGGER.debug("Kill switch alert indisponible.", exc_info=True)
                    break

                # Throttle
                if batch_count > 0 and batch_count % self._cfg.execution_batch_size == 0:
                    events.append(make_event(exec_run_id, EventType.THROTTLE_WAIT, "Batch throttle"))
                if self._cfg.inter_order_delay_ms > 0 and batch_count > 0:
                    time.sleep(self._cfg.inter_order_delay_ms / 1000.0)

                # Persist intent
                self._persist_order_request_state(intent, status=OrderStatus.NEW)

                if self._cfg.dry_run:
                    self._persist_order_request_state(intent, status=OrderStatus.SIMULATED)
                    events.append(make_event(
                        exec_run_id, EventType.DRY_RUN_SIMULATED,
                        f"DRY RUN: {intent.symbol} {intent.side} {intent.qty}",
                        symbol=intent.symbol, intent_id=intent.intent_id,
                    ))
                    metrics["submitted"] += 1
                    batch_count += 1
                    self._emit_progress(
                        metrics,
                        current=submit_processed,
                        total=submit_total,
                        label="⚙️ Progression execution — soumission des ordres d'entrée",
                        phase="submit_entries",
                        item=intent.symbol,
                    )
                    continue

                # ── Point 9.6 : réévaluation liquidité/borrow pré-soumission ──
                pre_submission_blocked = False
                if self._pre_submission_spreads is not None or self._pre_submission_borrows is not None:
                    try:
                        from risk_management.liquidity import check_pre_submission

                        notional = abs(intent.qty * (intent.decision_price or 0.0))
                        sym = intent.symbol.upper()
                        side = "short" if intent.side == "sell" else "long"

                        spread_snap = (
                            self._pre_submission_spreads.get(sym)
                            if self._pre_submission_spreads else None
                        )
                        borrow_snap = (
                            self._pre_submission_borrows.get(sym)
                            if self._pre_submission_borrows else None
                        )
                        adv = (
                            self._pre_submission_adv.get(sym)
                            if self._pre_submission_adv else None
                        )
                        vol = (
                            self._pre_submission_daily_vol.get(sym)
                            if self._pre_submission_daily_vol else None
                        )

                        result = check_pre_submission(
                            symbol=sym,
                            side=side,
                            notional=notional,
                            spread=spread_snap,      # type: ignore[arg-type]
                            borrow=borrow_snap,        # type: ignore[arg-type]
                            adv_usd=adv,
                            daily_vol_pct=vol,
                            intent_id=intent.intent_id,
                        )

                        if not result.go:
                            LOGGER.warning(
                                "Pre-submission gate NO-GO pour %s: %s",
                                sym, result.reason,
                            )
                            events.append(make_event(
                                exec_run_id, EventType.ORDER_REJECTED,
                                f"Pre-submission gate: {result.reason}",
                                symbol=intent.symbol,
                                intent_id=intent.intent_id,
                            ))
                            self._persist_order_request_state(
                                intent,
                                status=OrderStatus.REJECTED,
                                failure_reason=f"pre_submission_gate: {result.reason}",
                            )
                            metrics["skipped"] = metrics.get("skipped", 0) + 1
                            pre_submission_blocked = True
                    except Exception:
                        LOGGER.debug(
                            "Pre-submission gate indisponible pour %s, "
                            "poursuite sans vérification.",
                            intent.symbol, exc_info=True,
                        )

                if pre_submission_blocked:
                    self._emit_progress(
                        metrics,
                        current=submit_processed,
                        total=submit_total,
                        label="⚙️ Progression execution — soumission des ordres d'entrée",
                        phase="submit_entries",
                        item=intent.symbol,
                    )
                    continue

                # Submit to broker avec retry UNIQUEMENT sur erreurs reseau / 5xx / 429
                # Les erreurs 4xx (403 = client_order_id duplique, symbole interdit, etc.)
                # sont des erreurs permanentes : on ne retante PAS.
                order: BrokerOrder | None = None
                for attempt in range(self._cfg.max_order_retries + 1):
                    try:
                        order = self._broker.submit_intent(intent)
                        consecutive_failures = 0
                        break
                    except BrokerApiError as exc:
                        # Erreur 4xx : permanente, log detaille + pas de retry
                        body_info = f" — {exc.body[:200]}" if exc.body else ""
                        LOGGER.error(
                            "Ordre refuse par le broker [%s] %s : %s%s",
                            exc.status_code, intent.symbol, exc, body_info,
                        )
                        consecutive_failures += 1
                        metrics["failed"] += 1
                        events.append(make_event(
                            exec_run_id, EventType.ORDER_REJECTED,
                            f"[{exc.status_code}] {intent.symbol}: {str(exc)[:200]}",
                            symbol=intent.symbol, intent_id=intent.intent_id,
                        ))
                        self._persist_order_request_state(
                            intent,
                            status=OrderStatus.REJECTED,
                            failure_reason=f"[{exc.status_code}] {str(exc)[:200]}",
                        )
                        break  # pas de retry sur 4xx
                    except Exception as exc:
                        # Erreur reseau / timeout : on retente avec backoff
                        LOGGER.warning("Submit failed for %s attempt %d: %s", intent.symbol, attempt, exc)
                        if attempt < self._cfg.max_order_retries:
                            time.sleep(self._cfg.retry_base_delay_seconds * (2 ** attempt))
                        else:
                            consecutive_failures += 1
                            metrics["failed"] += 1
                            events.append(make_event(
                                exec_run_id, EventType.ORDER_REJECTED,
                                f"Submit failed after retries: {intent.symbol}",
                                symbol=intent.symbol, intent_id=intent.intent_id,
                            ))
                            self._persist_order_request_state(
                                intent,
                                status=OrderStatus.FAILED,
                                failure_reason=str(exc)[:200],
                            )

                if order is not None:
                    events.append(make_event(
                        exec_run_id, EventType.ORDER_SUBMITTED,
                        f"Submitted: {intent.symbol} → {order.broker_order_id}",
                        symbol=intent.symbol, broker_order_id=order.broker_order_id,
                        intent_id=intent.intent_id,
                    ))
                    submitted_orders[intent.intent_id] = (intent, order)
                    metrics["submitted"] += 1
                    self._persist_order_request_state(intent, status=order.status)
                    self._persist_broker_order_state(intent, order)

                batch_count += 1
                self._emit_progress(
                    metrics,
                    current=submit_processed,
                    total=submit_total,
                    label="⚙️ Progression execution — soumission des ordres d'entrée",
                    phase="submit_entries",
                    item=intent.symbol,
                )

            # Phase 5 — Poll fills
            # Si le marche est ferme, les ordres resteront en "accepted" (SUBMITTED)
            # et ne seront remplis qu'a l'ouverture : on saute le polling pour eviter
            # d'attendre 120s × N ordres inutilement.
            market_open_for_poll = True
            if not self._cfg.dry_run:
                try:
                    market_open_for_poll = self._broker.is_market_open()
                except Exception:
                    market_open_for_poll = False

            if not self._cfg.dry_run and market_open_for_poll:
                poll_total = max(len(submitted_orders), 1)
                poll_processed = 0
                for intent_id, (intent, order) in list(submitted_orders.items()):
                    poll_processed += 1
                    filled_order = self._poll_until_terminal(order.broker_order_id, intent.intent_id, exec_run_id)
                    if filled_order and filled_order.status == OrderStatus.FILLED:
                        metrics["filled"] += 1
                        fill = self._build_fill(filled_order, intent)
                        fills.append(fill)
                        try:
                            self._repo.insert_execution_broker_fill(fill, account_id=resolved_account_id)
                        except Exception:
                            LOGGER.debug("Could not persist Sprint 2 fill", exc_info=True)

                        try:
                            from execution_engine.protection_state_bridge import (
                                build_protection_state_from_fill,
                                persist_protection_state,
                                verify_fill_protection_consistency,
                            )
                            protection_state = build_protection_state_from_fill(
                                symbol=fill.symbol,
                                side="short" if intent.side == "sell" else "long",
                                fill_qty=fill.filled_qty,
                                fill_price=fill.avg_fill_price,
                                decision_price=fill.decision_price,
                                parent_intent_id=intent.intent_id,
                                decision_fingerprint=intent.decision_fingerprint,
                            )
                            protection_ok, protection_issues = verify_fill_protection_consistency(protection_state)
                            protection_state["verification"] = {
                                "ok": protection_ok,
                                "issues": protection_issues,
                            }
                            persist_protection_state(protection_state, exec_run_id=exec_run_id)
                            if not protection_ok:
                                metrics["protection_breaches"] = int(metrics.get("protection_breaches", 0) or 0) + 1
                                events.append(make_event(
                                    exec_run_id, EventType.ORDER_REJECTED,
                                    f"Protection contract breach: {'; '.join(protection_issues)}",
                                    symbol=intent.symbol,
                                    intent_id=intent.intent_id,
                                ))
                                LOGGER.error("Protection contract breach for %s: %s", intent.symbol, protection_issues)
                        except Exception:
                            metrics["protection_persistence_failures"] = int(metrics.get("protection_persistence_failures", 0) or 0) + 1
                            LOGGER.exception("Protection state persistence failed for %s", intent.symbol)

                        # Slippage alert
                        if abs(fill.slippage_bps) > self._cfg.max_slippage_bps:
                            events.append(make_event(
                                exec_run_id, EventType.SLIPPAGE_ALERT,
                                f"Slippage {fill.slippage_bps:.1f} bps on {intent.symbol}",
                                symbol=intent.symbol,
                            ))
                            # Alerte système (best-effort, anti-doublon via send_system_alert)
                            try:
                                from service.alerting import send_system_alert
                                send_system_alert(
                                    event="SLIPPAGE_EXCEEDED",
                                    payload={
                                        "exec_run_id": exec_run_id,
                                        "symbol": intent.symbol,
                                        "slippage_bps": round(fill.slippage_bps, 2),
                                        "max_slippage_bps": self._cfg.max_slippage_bps,
                                        "account_id": resolved_account_id,
                                    },
                                    severity="warning",
                                )
                            except Exception:
                                LOGGER.debug("Slippage alert indisponible.", exc_info=True)

                        # Phase 6 — Submit children (synthetic bracket)
                        child_events = self._submit_children(
                            intent,
                            filled_order,
                            exec_run_id,
                            account_state=account_state,
                            metrics=metrics,
                            target=target_by_intent_id.get(str(intent.intent_id)) or target_by_symbol.get(intent.symbol),
                        )
                        events.extend(child_events)

                        submitted_orders[intent_id] = (intent, filled_order)
                    elif filled_order:
                        events.append(make_event(
                            exec_run_id, EventType.ORDER_CANCELED if filled_order.status == OrderStatus.CANCELED else EventType.ORDER_REJECTED,
                            f"{filled_order.status}: {intent.symbol}",
                            symbol=intent.symbol, broker_order_id=filled_order.broker_order_id,
                        ))
                    self._emit_progress(
                        metrics,
                        current=poll_processed,
                        total=poll_total,
                        label="⚙️ Progression execution — suivi des fills",
                        phase="poll_fills",
                        item=intent.symbol,
                    )
            elif not self._cfg.dry_run and not market_open_for_poll and submitted_orders:
                LOGGER.info(
                    "Marche ferme — %d ordres soumis, pas de polling. "
                    "Les ordres seront remplis a l'ouverture (time_in_force=day).",
                    len(submitted_orders),
                )
                events.append(make_event(
                    exec_run_id, EventType.PRECHECK_OK,
                    f"Market closed — {len(submitted_orders)} orders queued, no polling. "
                    "They will fill at next market open.",
                ))
                self._emit_progress(
                    metrics,
                    current=len(submitted_orders),
                    total=max(len(submitted_orders), 1),
                    label="⚙️ Progression execution — ordres en attente d'ouverture marché",
                    phase="poll_fills",
                )

            if not self._cfg.dry_run:
                try:
                    sync_metrics = BrokerStateSynchronizer(
                        self._repo,
                        self._broker,
                        broker_mode=self._cfg.broker_mode,
                    ).sync(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        order_limit=max(200, len(submitted_orders) * 10) if submitted_orders else 200,
                    )
                    sync_metrics = {key: int(value or 0) for key, value in sync_metrics.items()}
                    metrics["broker_orders_synced"] = sync_metrics["orders_synced"]
                    metrics["broker_fills_synced"] = sync_metrics["fills_synced"]
                    metrics["broker_positions_observed"] = sync_metrics["broker_positions"]
                    metrics["execution_positions_projected"] = sync_metrics["positions_projected"]
                    metrics["execution_position_lots_projected"] = sync_metrics["lots_projected"]
                    metrics["broker_sync_unmatched_orders"] = sync_metrics["unmatched_orders"]
                    events.append(make_event(
                        exec_run_id,
                        EventType.BROKER_SYNC_COMPLETED,
                        (
                            "Broker sync completed: "
                            f"orders={sync_metrics['orders_synced']} fills={sync_metrics['fills_synced']} "
                            f"positions={sync_metrics['positions_projected']} lots={sync_metrics['lots_projected']}"
                        ),
                        payload=sync_metrics,
                    ))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — synchronisation broker",
                        phase="broker_sync",
                        unit="étapes",
                    )
                except Exception as exc:
                    LOGGER.warning("Broker state sync failed: %s", exc, exc_info=True)
                    events.append(make_event(
                        exec_run_id,
                        EventType.BROKER_SYNC_FAILED,
                        f"Broker sync failed: {str(exc)[:160]}",
                    ))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — synchronisation broker",
                        phase="broker_sync",
                        unit="étapes",
                    )

            # Phase 7b — Sprint S26 (gap P3) — Filet de sécurité TP/SL post-sync.
            # Cas overnight : l'entrée a été soumise marché fermé, _submit_children
            # n'a pas tourné, mais à l'ouverture le broker l'a remplie. La sync
            # broker (Phase 7) vient de matérialiser ces fills en base. On arme
            # maintenant les TP + STOP manquants pour chaque parent FILLED qui
            # n'a aucun enfant ouvert chez le broker.
            if not self._cfg.dry_run:
                try:
                    unprotected = self._repo.load_unprotected_filled_parents(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                    )
                except Exception as exc:
                    LOGGER.warning("load_unprotected_filled_parents failed: %s", exc, exc_info=True)
                    unprotected = []

                metrics["children_armed_post_sync"] = 0
                metrics["children_armed_post_sync_failed"] = 0
                for row in unprotected:
                    try:
                        parent_intent, filled_order = self._reconstruct_parent_for_arming(row)
                    except Exception as exc:
                        LOGGER.warning(
                            "Impossible de reconstruire le parent pour armement TP/SL (symbol=%s): %s",
                            row.get("symbol"), exc,
                        )
                        metrics["children_armed_post_sync_failed"] += 1
                        continue
                    try:
                        child_events = self._submit_children(
                            parent_intent,
                            filled_order,
                            exec_run_id,
                            account_state=account_state,
                            metrics=metrics,
                            target=target_by_intent_id.get(str(parent_intent.intent_id)) or target_by_symbol.get(parent_intent.symbol),
                        )
                        events.extend(child_events)
                        metrics["children_armed_post_sync"] += 1
                        events.append(make_event(
                            exec_run_id,
                            EventType.CHILDREN_SUBMITTED,
                            f"Post-sync TP/SL armés pour {parent_intent.symbol}",
                            symbol=parent_intent.symbol,
                            intent_id=parent_intent.intent_id,
                            payload={
                                "fill_qty": filled_order.filled_qty,
                                "fill_price": filled_order.avg_fill_price,
                                "trigger": "post_broker_sync",
                            },
                        ))
                    except Exception as exc:
                        metrics["children_armed_post_sync_failed"] += 1
                        LOGGER.warning(
                            "Échec armement post-sync TP/SL pour %s: %s",
                            parent_intent.symbol, exc, exc_info=True,
                        )

            # Phase 8 — Reconciliation
            if self._cfg.reconcile_after_submit and not self._cfg.dry_run:
                try:
                    positions = self._broker.get_all_positions()
                    self._repo.snapshot_broker_positions(exec_run_id, self._cfg.broker_mode, positions, account_id=resolved_account_id)
                    reconciliation_results = reconcile_execution_state(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        targets=targets,
                        broker_positions=positions,
                        internal_positions=self._repo.load_execution_positions(account_id=resolved_account_id),
                        open_order_state=self._repo.load_open_reconciliation_order_state(account_id=resolved_account_id),
                        protection_state=self._repo.load_reconciliation_protection_state(account_id=resolved_account_id),
                        tolerance=self._cfg.effective_reconcile_tolerance_shares,
                        buying_power_available=account_state.buying_power_available,
                    )
                    self._repo.replace_execution_reconciliation_results(
                        exec_run_id=exec_run_id,
                        account_id=resolved_account_id,
                        results=reconciliation_results,
                    )
                    action_results = [result for result in reconciliation_results if result.action != "none"]
                    safe_auto_results = [result for result in action_results if result.reconciliation_status == ReconciliationStatus.SAFE_AUTO]
                    manual_review_results = [result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.MANUAL_REVIEW]
                    blocked_results = [result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.BLOCKED]
                    metrics["reconciliation_results"] = len(reconciliation_results)
                    metrics["reconciliation_safe_auto"] = len([result for result in reconciliation_results if result.reconciliation_status == ReconciliationStatus.SAFE_AUTO])
                    metrics["reconciliation_manual_review"] = len(manual_review_results)
                    metrics["reconciliation_blocked"] = len(blocked_results)
                    if action_results or manual_review_results or blocked_results:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_DIFF,
                                                 (
                                                     "Reconciliation analyzed: "
                                                     f"actionable={len(action_results)} "
                                                     f"safe_auto={len(safe_auto_results)} "
                                                     f"manual_review={len(manual_review_results)} "
                                                     f"blocked={len(blocked_results)}"
                                                 ),
                                                 payload={
                                                     "actionable": len(action_results),
                                                     "safe_auto": len(safe_auto_results),
                                                     "manual_review": len(manual_review_results),
                                                     "blocked": len(blocked_results),
                                                 }))
                        if self._cfg.auto_rebalance_on_reconcile and safe_auto_results:
                            safe_auto_diffs = [
                                ReconcileDiff(
                                    symbol=result.symbol,
                                    target_qty=float(result.target_qty),
                                    broker_qty=result.broker_position_qty,
                                    delta=result.position_delta,
                                    action=result.action,
                                )
                                for result in safe_auto_results
                            ]
                            rebalance_events = self._submit_rebalance_orders(
                                safe_auto_diffs, exec_run_id, targets, metrics, account_state,
                            )
                            events.extend(rebalance_events)
                    else:
                        events.append(make_event(exec_run_id, EventType.RECONCILE_OK, "Reconciliation OK"))
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — réconciliation",
                        phase="reconcile",
                        unit="étapes",
                    )
                except Exception as exc:
                    LOGGER.warning("Reconciliation failed: %s", exc)
                    self._emit_progress(
                        metrics,
                        current=1,
                        total=1,
                        label="⚙️ Progression execution — réconciliation",
                        phase="reconcile",
                        unit="étapes",
                    )

            # Phase 9 — TCA
            if self._cfg.enable_tca and fills:
                tca = build_tca_summary(fills, self._cfg.max_slippage_bps)
                metrics["tca_total_filled"] = int(tca.total_filled)
                metrics["tca_total_notional"] = float(tca.total_notional)
                metrics["tca_avg_slippage_bps"] = float(tca.avg_slippage_bps)
                metrics["tca_max_slippage_bps"] = float(tca.max_slippage_bps)
                metrics["tca_total_implementation_shortfall"] = float(tca.total_implementation_shortfall)
                metrics["tca_slippage_alerts"] = int(tca.slippage_alerts)
                events.append(make_event(
                    exec_run_id, EventType.TCA_SUMMARY,
                    f"TCA: avg_slip={tca.avg_slippage_bps:.1f}bps alerts={tca.slippage_alerts}",
                    payload={
                        "total_filled": tca.total_filled,
                        "avg_slippage_bps": tca.avg_slippage_bps,
                        "max_slippage_bps": tca.max_slippage_bps,
                        "total_implementation_shortfall": tca.total_implementation_shortfall,
                    },
                ))

            # Phase 10 — Finalize
            events.append(make_event(exec_run_id, EventType.RUN_COMPLETED,
                                     f"Run completed: {metrics}"))
            self._repo.update_execution_run_status(
                exec_run_id, "COMPLETED",
                total_submitted=metrics["submitted"], total_filled=metrics["filled"],
            )
            metrics["status"] = "COMPLETED"
            self._emit_progress(
                metrics,
                current=1,
                total=1,
                label="⚙️ Progression execution — finalisation",
                phase="finalize",
                unit="étapes",
            )

        except Exception as exc:
            LOGGER.exception("Execution run failed: %s", exc)
            events.append(make_event(exec_run_id, EventType.RUN_FAILED, str(exc)[:255]))
            try:
                self._repo.update_execution_run_status(exec_run_id, "FAILED", error_message=str(exc)[:255])
            except Exception:
                pass
            metrics["status"] = "FAILED"
            self._emit_progress(
                metrics,
                current=1,
                total=1,
                label="⚙️ Progression execution — échec du run",
                phase="failed",
                unit="étapes",
            )
        finally:
            self._persist_events(events)
            if lock_acquired:
                try:
                    self._repo.release_execution_lock(account_id=resolved_account_id, exec_run_id=exec_run_id)
                except Exception:
                    LOGGER.warning("Unable to release execution lock for account_id=%s", resolved_account_id, exc_info=True)
        return metrics

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Sprint S7 - account capacity helpers (delegated to ``account_state``).
    # ------------------------------------------------------------------

    def _build_account_constraint_state(self) -> _AccountConstraintState:
        return _build_account_constraint_state_impl(self._cfg, self._broker)

    @staticmethod
    def _safe_float(value: object, *, default: float = 0.0) -> float:
        return _safe_float_impl(value, default=default)

    def _estimate_intent_notional(self, intent: OrderIntent) -> float:
        return _estimate_intent_notional_impl(intent)

    def _reserve_account_capacity_for_intent(
        self,
        intent: OrderIntent,
        account_state: _AccountConstraintState,
        exec_run_id: str,
        events: list[ExecutionEvent],
        metrics: dict[str, int],
    ) -> bool:
        return _reserve_account_capacity_for_intent_impl(
            intent, account_state, exec_run_id, events, metrics
        )

    def _should_defer_children(
        self,
        account_state: _AccountConstraintState,
    ) -> tuple[bool, str | None]:
        return _should_defer_children_impl(account_state)

    def _poll_until_terminal(self, broker_order_id: str, intent_id: str, exec_run_id: str) -> BrokerOrder | None:
        deadline = time.monotonic() + self._cfg.fill_timeout_seconds
        while time.monotonic() < deadline:
            try:
                order = self._broker.poll_order_status(broker_order_id, intent_id)
                if is_terminal(order.status):
                    return order
                time.sleep(self._cfg.poll_interval_seconds)
            except Exception as exc:
                LOGGER.warning("Poll error for %s: %s", broker_order_id, exc)
                time.sleep(self._cfg.poll_interval_seconds)
        LOGGER.warning("Fill timeout for order %s", broker_order_id)
        return None

    def _build_fill(self, order: BrokerOrder, intent: OrderIntent) -> ExecutionFill:
        fill_price = order.avg_fill_price or intent.decision_price
        slip = compute_slippage_bps(fill_price, intent.decision_price)
        ishort = compute_implementation_shortfall(fill_price, intent.decision_price, order.filled_qty)
        return ExecutionFill(
            fill_id=uuid.uuid4().hex[:16],
            broker_order_id=order.broker_order_id,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            filled_qty=order.filled_qty,
            avg_fill_price=fill_price,
            fill_timestamp=datetime.now(timezone.utc),
            decision_price=intent.decision_price,
            slippage_bps=slip,
            implementation_shortfall=ishort,
        )

    def _snapshot_account_constraints(self, exec_run_id: str, account_state: _AccountConstraintState) -> None:
        if account_state.equity <= 0.0:
            # Hardening live : ne jamais persister un snapshot 0/négatif (cf. InvalidBrokerSnapshotError).
            LOGGER.warning(
                "Snapshot broker non persisté — equity invalide=%.4f | account=%s broker_mode=%s exec_run_id=%s",
                account_state.equity,
                self._cfg.resolved_account_id,
                self._cfg.broker_mode,
                exec_run_id,
            )
            return
        try:
            self._repo.snapshot_broker_account(
                exec_run_id,
                account_id=self._cfg.resolved_account_id,
                broker_mode=self._cfg.broker_mode,
                snapshot={
                    "equity": account_state.equity,
                    "cash": account_state.settled_cash_available,
                    "settled_cash": account_state.settled_cash_available,
                    "buying_power": account_state.buying_power_available,
                    "daytrade_count": account_state.daytrade_count,
                    "account_type": account_state.account_type,
                    "swing_only": account_state.swing_only,
                    "leverage_feature_enabled": account_state.leverage_feature_enabled,
                    "leverage_active": account_state.leverage_active,
                    "leverage_configured_max": account_state.leverage_configured_max,
                    "effective_leverage": account_state.effective_leverage,
                    "leverage_target_budget": account_state.leverage_target_budget,
                    "leverage_broker_buying_power": account_state.leverage_broker_buying_power,
                    "leverage_buying_power_field": account_state.leverage_buying_power_field,
                    "leverage_reason": account_state.leverage_reason,
                },
                snapshot_kind="preflight",
            )
        except Exception:
            LOGGER.debug("Could not persist broker account snapshot", exc_info=True)

    def _persist_order_request_state(
        self,
        intent: OrderIntent,
        *,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        try:
            self._repo.upsert_execution_order_request_from_intent(
                intent,
                account_id=self._cfg.resolved_account_id,
                status=status,
                failure_reason=failure_reason,
            )
        except Exception:
            LOGGER.debug("Could not persist Sprint 2 request for %s", intent.intent_id, exc_info=True)

    def _persist_broker_order_state(self, intent: OrderIntent, order: BrokerOrder) -> None:
        try:
            self._repo.upsert_execution_broker_order(
                intent,
                order,
                account_id=self._cfg.resolved_account_id,
                raw_payload={
                    **intent_to_alpaca_payload(intent),
                    "decision_fingerprint": intent.decision_fingerprint,
                },
            )
        except Exception:
            LOGGER.debug("Could not persist Sprint 2 broker order for %s", intent.intent_id, exc_info=True)

    def _persist_child_order_state(
        self,
        intent: OrderIntent,
        order: BrokerOrder,
    ) -> None:
        self._persist_order_request_state(intent, status=order.status)
        self._persist_broker_order_state(intent, order)

    def _cancel_child_for_transition(
        self,
        intent: OrderIntent,
        order: BrokerOrder,
        exec_run_id: str,
    ) -> tuple[bool, BrokerOrder]:
        try:
            cancel_requested = self._broker.cancel_broker_order(order.broker_order_id)
        except Exception:
            return False, order
        if not cancel_requested:
            return False, order

        latest_order = order
        deadline = time.monotonic() + self._cfg.cancel_timeout_seconds
        while time.monotonic() < deadline:
            try:
                latest_order = self._broker.poll_order_status(order.broker_order_id, intent.intent_id)
            except Exception:
                time.sleep(self._cfg.poll_interval_seconds)
                continue
            if latest_order.status == OrderStatus.CANCELED:
                self._persist_child_order_state(intent, latest_order)
                return True, latest_order
            if latest_order.status in {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.EXPIRED}:
                self._persist_child_order_state(intent, latest_order)
                return False, latest_order
            time.sleep(self._cfg.poll_interval_seconds)
        return False, latest_order

    def _maybe_activate_dynamic_trailing(
        self,
        parent: OrderIntent,
        fill_qty: float,
        fill_price: float,
        exec_run_id: str,
        *,
        target: Any | None,
        initial_stop_intent: OrderIntent | None,
        initial_stop_order: BrokerOrder | None,
        metrics: dict[str, int],
    ) -> list[ExecutionEvent]:
        return _maybe_activate_dynamic_trailing_impl(
            self,
            parent,
            fill_qty,
            fill_price,
            exec_run_id,
            target=target,
            initial_stop_intent=initial_stop_intent,
            initial_stop_order=initial_stop_order,
            metrics=metrics,
        )

    def _submit_children(
        self,
        parent: OrderIntent,
        filled_order: BrokerOrder,
        exec_run_id: str,
        *,
        account_state: _AccountConstraintState,
        metrics: dict[str, int],
        target: Any | None = None,
    ) -> list[ExecutionEvent]:
        return _submit_children_impl(
            self,
            parent,
            filled_order,
            exec_run_id,
            account_state=account_state,
            metrics=metrics,
            target=target,
        )

    # ------------------------------------------------------------------
    # Sprint S26 (gap P3) — Reconstruction parent pour armement TP/SL post-sync.
    # Voir Phase 7b dans ``execute_run``.
    # ------------------------------------------------------------------
    def _reconstruct_parent_for_arming(self, row: dict[str, Any]) -> tuple[OrderIntent, BrokerOrder]:
        symbol = str(row["symbol"]).strip().upper()
        fill_qty = float(row.get("fill_qty") or 0.0)
        fill_price = float(row.get("fill_price") or 0.0)
        decision_price = float(row.get("decision_price") or fill_price or 0.0)
        target_qty = float(row.get("target_qty") or fill_qty)
        order_type = str(row.get("order_type") or "market")
        limit_price = row.get("limit_price")
        limit_price_value = float(limit_price) if limit_price not in (None, "") else None
        broker_mode = str(row.get("broker_mode") or self._cfg.broker_mode)
        parent_intent = OrderIntent(
            intent_id=str(row["parent_intent_id"]),
            risk_run_id=str(row.get("risk_run_id") or ""),
            exec_run_id=str(row["exec_run_id"]),
            symbol=symbol,
            side=str(row.get("side") or "buy"),
            qty=target_qty,
            order_type=order_type,
            limit_price=limit_price_value,
            trail_percent=None,
            broker_mode=broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=str(row.get("business_key") or row.get("submission_key") or row["parent_intent_id"]),
            decision_price=decision_price,
            stop_price=None,
            submission_key=str(row["submission_key"]) if row.get("submission_key") else None,
        )
        filled_order = BrokerOrder(
            broker_order_id=str(row.get("parent_broker_order_id") or ""),
            client_order_id=str(row.get("submission_key") or ""),
            intent_id=str(row["parent_intent_id"]),
            symbol=symbol,
            side=str(row.get("side") or "buy"),
            qty=target_qty,
            filled_qty=fill_qty,
            avg_fill_price=fill_price,
            status=OrderStatus.FILLED,
            order_type=order_type,
            limit_price=limit_price_value,
            stop_price=None,
            trail_percent=None,
            created_at=None,
            updated_at=None,
        )
        return parent_intent, filled_order

    def _submit_rebalance_orders(
        self,
        action_diffs: list,
        exec_run_id: str,
        targets: list,
        metrics: dict[str, int],
        account_state: _AccountConstraintState,
    ) -> list[ExecutionEvent]:
        return _submit_rebalance_orders_impl(
            self,
            action_diffs,
            exec_run_id,
            targets,
            metrics,
            account_state,
        )

    def _persist_events(self, events: list[ExecutionEvent]) -> None:
        for ev in events:
            try:
                self._repo.insert_execution_event(event_to_db_dict(ev))
            except Exception:
                LOGGER.debug("Could not persist event %s", ev.event_type)
