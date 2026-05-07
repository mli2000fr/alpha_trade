"""Synchronisation broker -> persistance Sprint 2/4 et projection positions/lots."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import ExecutionFill, ExecutionOrderRequest, OrderIntent
from execution_engine.orphan_adoption import adopt_orphan_buy, adopt_orphan_sell
from execution_engine.tca import compute_implementation_shortfall, compute_slippage_bps

LOGGER = logging.getLogger(__name__)


class BrokerStateSynchronizer:
    """Relit l'état broker récent et projette la vérité opérationnelle locale."""

    def __init__(
        self,
        repo: ExecutionRepository,
        broker: BrokerAdapter,
        *,
        broker_mode: str,
    ) -> None:
        self._repo = repo
        self._broker = broker
        self._broker_mode = broker_mode

    def sync(
        self,
        *,
        exec_run_id: str,
        account_id: str,
        order_limit: int = 200,
        symbols: list[str] | None = None,
    ) -> dict[str, int]:
        metrics = {
            "orders_synced": 0,
            "fills_synced": 0,
            "unmatched_orders": 0,
            "orphan_sells_adopted": 0,
            "orphan_buys_adopted": 0,
            "positions_projected": 0,
            "lots_projected": 0,
            "broker_positions": 0,
        }

        try:
            raw_orders = self._broker.list_recent_orders(status="all", limit=order_limit, symbols=symbols)
        except Exception:
            LOGGER.warning("Impossible de relire les ordres broker récents pour account_id=%s", account_id, exc_info=True)
            raw_orders = []

        for raw_order in raw_orders:
            request = self._resolve_request(account_id=account_id, raw_order=raw_order)
            if request is None:
                # Sprint 2026-05 — adoption d'ordre orphelin (Q5/Q6 FAQ).
                # Tout ordre filled / partiellement filled non rattaché à un
                # OrderIntent est intégré au journal canonique.
                adoption_result = self._maybe_adopt_orphan(
                    account_id=account_id, raw_order=raw_order,
                )
                if adoption_result is not None:
                    if adoption_result.intent.side == "sell":
                        metrics["orphan_sells_adopted"] += 1
                    else:
                        metrics["orphan_buys_adopted"] += 1
                    metrics["orders_synced"] += 1
                    if adoption_result.fill is not None:
                        metrics["fills_synced"] += 1
                else:
                    metrics["unmatched_orders"] += 1
                continue

            broker_order = replace(
                self._broker.broker_order_from_api(raw_order, intent_id=request.request_id),
                intent_id=request.request_id,
            )
            intent = self._request_to_intent(request)
            self._repo.upsert_execution_broker_order(
                intent,
                broker_order,
                account_id=account_id,
                raw_response=raw_order,
            )
            metrics["orders_synced"] += 1

            existing_filled_qty = self._repo.load_cumulative_filled_qty(request_id=request.request_id)
            missing_fill_qty = max(float(broker_order.filled_qty) - float(existing_filled_qty), 0.0)
            if missing_fill_qty > 1e-9:
                fill = self._build_missing_fill(
                    request=request,
                    broker_order=broker_order,
                    missing_fill_qty=missing_fill_qty,
                )
                self._repo.insert_execution_broker_fill(fill, account_id=account_id, raw_fill=raw_order)
                metrics["fills_synced"] += 1

        positions = self._broker.get_all_positions()
        self._repo.snapshot_broker_positions(exec_run_id, self._broker_mode, positions, account_id=account_id)
        metrics["broker_positions"] = len(positions)
        metrics["positions_projected"] = self._repo.replace_execution_positions(
            exec_run_id=exec_run_id,
            account_id=account_id,
            broker_mode=self._broker_mode,
            positions=positions,
        )
        metrics["lots_projected"] = self._repo.rebuild_execution_position_lots(account_id=account_id)
        return metrics

    def _maybe_adopt_orphan(
        self,
        *,
        account_id: str,
        raw_order: dict[str, Any],
    ):
        """Adopte un ordre broker orphelin filled / partially_filled.

        Retourne ``AdoptionResult`` ou ``None`` si l'ordre n'est pas filled
        (rien à adopter — un ordre simplement vu hors lineage est légitime
        s'il n'a jamais touché une position).
        """
        raw_status = str(raw_order.get("status") or "").strip().lower()
        if raw_status not in {"filled", "partially_filled"}:
            return None
        side = str(raw_order.get("side") or "").strip().lower()
        try:
            if side == "sell":
                return adopt_orphan_sell(
                    self._repo,
                    broker_mode=self._broker_mode,
                    account_id=account_id,
                    raw_order=raw_order,
                )
            if side == "buy":
                return adopt_orphan_buy(
                    self._repo,
                    broker_mode=self._broker_mode,
                    account_id=account_id,
                    raw_order=raw_order,
                )
        except Exception:
            LOGGER.warning(
                "Échec adoption ordre orphelin (account=%s, broker_order_id=%s)",
                account_id, raw_order.get("id"), exc_info=True,
            )
        return None

    def _resolve_request(
        self,
        *,
        account_id: str,
        raw_order: dict[str, Any],
    ) -> ExecutionOrderRequest | None:
        client_order_id = str(raw_order.get("client_order_id", "") or "").strip()
        if client_order_id:
            request = self._repo.find_order_request_by_submission_key(
                account_id=account_id,
                submission_key=client_order_id,
            )
            if request is not None:
                return request

        broker_order_id = str(raw_order.get("id", "") or "").strip()
        if broker_order_id:
            return self._repo.find_order_request_by_broker_order_id(
                account_id=account_id,
                broker_order_id=broker_order_id,
            )
        return None

    @staticmethod
    def _request_to_intent(request: ExecutionOrderRequest) -> OrderIntent:
        return OrderIntent(
            intent_id=request.request_id,
            risk_run_id=request.risk_run_id,
            exec_run_id=request.exec_run_id,
            symbol=request.symbol,
            side=request.side,
            qty=request.target_qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            trail_percent=request.trail_percent,
            broker_mode="paper",
            parent_intent_id=request.parent_request_id,
            intent_role=request.intent_role,
            idempotency_key=request.business_key,
            decision_price=request.decision_price,
            stop_price=request.stop_price,
            submission_key=request.submission_key,
        )

    @staticmethod
    def _build_missing_fill(
        *,
        request: ExecutionOrderRequest,
        broker_order,
        missing_fill_qty: float,
    ) -> ExecutionFill:
        fill_timestamp = broker_order.updated_at or broker_order.created_at or datetime.now(timezone.utc)
        fill_price = broker_order.avg_fill_price or request.decision_price
        fill_seed = f"{broker_order.broker_order_id}|{request.request_id}|{missing_fill_qty:.8f}|{fill_timestamp.isoformat()}"
        fill_id = hashlib.sha256(fill_seed.encode()).hexdigest()[:32]
        slippage_bps = compute_slippage_bps(fill_price, request.decision_price)
        implementation_shortfall = compute_implementation_shortfall(fill_price, request.decision_price, missing_fill_qty)
        return ExecutionFill(
            fill_id=fill_id,
            broker_order_id=broker_order.broker_order_id,
            intent_id=request.request_id,
            symbol=request.symbol,
            filled_qty=missing_fill_qty,
            avg_fill_price=fill_price,
            fill_timestamp=fill_timestamp,
            decision_price=request.decision_price,
            slippage_bps=slippage_bps,
            implementation_shortfall=implementation_shortfall,
        )

