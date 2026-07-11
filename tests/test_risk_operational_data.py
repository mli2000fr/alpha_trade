from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from execution_engine.broker_adapter import BrokerAdapter
from risk_management.operational_data import (
    BacktestOperationalDataAdapter,
    LiveBrokerOperationalDataAdapter,
    OperationalDataUnavailable,
)


def _account() -> dict[str, object]:
    return {"equity": "100000", "cash": "40000", "settled_cash": "39000", "buying_power": "90000"}


def _position() -> dict[str, object]:
    return {"symbol": "AAPL", "side": "long", "qty": "10", "avg_entry_price": "100", "current_price": "105"}


def test_backtest_adapter_normalizes_positions_orders_and_account() -> None:
    snapshot = BacktestOperationalDataAdapter.build(
        account_id="paper-account",
        account=_account(),
        positions=[_position()],
        orders=[{"id": "o-1", "symbol": "AAPL", "side": "sell", "type": "stop", "qty": "10", "filled_qty": "2", "status": "partially_filled"}],
        as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    assert snapshot.account.buying_power == 90_000.0
    assert snapshot.positions[0].side == "long"
    assert snapshot.holdings[0].has_open_order is True
    assert snapshot.open_orders[0].has_partial_fill is True


def test_backtest_adapter_rejects_missing_buying_power() -> None:
    account = _account()
    del account["buying_power"]

    with pytest.raises(OperationalDataUnavailable, match="buying_power"):
        BacktestOperationalDataAdapter.build(
            account_id="paper-account",
            account=account,
            as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        )


def test_backtest_adapter_rejects_invalid_position() -> None:
    bad_position = _position()
    bad_position["side"] = "flat"

    with pytest.raises(OperationalDataUnavailable, match="position broker invalide"):
        BacktestOperationalDataAdapter.build(
            account_id="paper-account",
            account=_account(),
            positions=[bad_position],
            as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        )


def test_live_adapter_reads_all_operational_sources() -> None:
    broker = MagicMock(spec=BrokerAdapter)
    broker.get_account_snapshot.return_value = _account()
    broker.get_all_positions.return_value = [_position()]
    broker.list_recent_orders.return_value = []

    snapshot = LiveBrokerOperationalDataAdapter(
        broker,
        account_id="paper-account",
        broker_mode="paper",
    ).capture()

    assert snapshot.account.source == "broker:paper"
    broker.list_recent_orders.assert_called_once_with(status="open", limit=500)


def test_live_adapter_fails_closed_when_broker_read_fails() -> None:
    broker = MagicMock(spec=BrokerAdapter)
    broker.get_account_snapshot.side_effect = RuntimeError("offline")

    with pytest.raises(OperationalDataUnavailable, match="indisponible"):
        LiveBrokerOperationalDataAdapter(
            broker,
            account_id="paper-account",
            broker_mode="paper",
        ).capture()