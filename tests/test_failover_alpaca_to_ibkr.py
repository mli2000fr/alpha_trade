"""Sprint S13.5 — Failover Alpaca → IBKR (read-only)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from core.broker_models import AccountSnapshot, OrderRequest
from service.broker_failover import (
    DEFAULT_RESUME_FLAG,
    FailoverBrokerClient,
    WriteSuspendedError,
)
from service.mock_broker import MockBroker


class _FlakyBroker:
    name = "flaky"

    def __init__(self, fail_n: int):
        self.calls = 0
        self.fail_n = fail_n

    def get_account(self) -> AccountSnapshot:
        self.calls += 1
        if self.calls <= self.fail_n:
            raise RuntimeError("boom")
        return AccountSnapshot(
            account_id="primary",
            equity=Decimal("1"),
            cash=Decimal("1"),
            buying_power=Decimal("1"),
        )

    def get_positions(self):
        raise RuntimeError("boom")

    def get_orders(self, status="all", since=None):
        raise RuntimeError("boom")

    def submit_order(self, request):
        return MockBroker(seed=99).submit_order(request)

    def cancel_order(self, order_id):
        return True

    def stream_trades(self, callback):
        raise NotImplementedError


@pytest.fixture()
def resume_flag(tmp_path):
    flag = tmp_path / "RESUME"
    yield flag
    if flag.exists():
        flag.unlink()


def test_failover_trips_after_threshold(resume_flag):
    primary = _FlakyBroker(fail_n=10)  # always fails
    secondary = MockBroker(seed=1)
    fb = FailoverBrokerClient(primary, secondary, circuit_breaker_threshold=3,
                              resume_flag_path=resume_flag)
    # Les 2 premières erreurs propagent ; la 3e bascule + retourne secondary.
    for _ in range(2):
        with pytest.raises(RuntimeError):
            fb.get_account()
    snap = fb.get_account()  # 3rd → trip + secondary
    assert fb.tripped is True
    assert snap.account_id.startswith("mock-")


def test_failover_blocks_writes_when_tripped(resume_flag):
    primary = _FlakyBroker(fail_n=10)
    secondary = MockBroker(seed=2)
    fb = FailoverBrokerClient(primary, secondary, circuit_breaker_threshold=1,
                              resume_flag_path=resume_flag)
    fb.get_account()  # trips
    assert fb.tripped is True
    with pytest.raises(WriteSuspendedError):
        fb.submit_order(OrderRequest(symbol="X", qty=Decimal("1"), side="buy"))


def test_resume_flag_resets_breaker(resume_flag):
    primary = _FlakyBroker(fail_n=10)
    secondary = MockBroker(seed=3)
    fb = FailoverBrokerClient(primary, secondary, circuit_breaker_threshold=1,
                              resume_flag_path=resume_flag)
    fb.get_account()
    assert fb.tripped is True
    resume_flag.parent.mkdir(parents=True, exist_ok=True)
    resume_flag.write_text("ok")
    # Après reset, le primary fail toujours mais writes ne sont plus bloquées.
    # Réinitialise le compteur en interne.
    assert fb.tripped is False  # parce que la sentinelle a été consommée


def test_failover_passthrough_when_primary_healthy(resume_flag):
    primary = _FlakyBroker(fail_n=0)
    secondary = MockBroker(seed=4)
    fb = FailoverBrokerClient(primary, secondary, circuit_breaker_threshold=3,
                              resume_flag_path=resume_flag)
    snap = fb.get_account()
    assert snap.account_id == "primary"
    assert fb.tripped is False

