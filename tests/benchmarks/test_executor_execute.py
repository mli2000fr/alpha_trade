"""Phase F / S23.1 — Benchmark `ProductionExecutor.execute_run` en mode dry-run
avec `MockBroker` + repository in-memory minimal.
"""
from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.benchmark


def _build_executor():
    try:
        from execution_engine.executor import ProductionExecutor
        from execution_engine.config import ExecutionConfig
        from execution_engine.oco_manager import OcoManager
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"execution_engine indisponible : {exc}")

    # Repository minimal : tous les hooks no-op pour focaliser le bench
    # sur l'orchestrateur execute_run.
    class _NoopRepo:
        engine = None
        def acquire_execution_lock(self, **_): return True
        def release_execution_lock(self, **_): return None
        def load_portfolio_targets(self, **_): return []
        def insert_execution_run(self, **_): return None
        def snapshot_execution_targets(self, **_): return None
        def update_execution_run_status(self, *_a, **_k): return None
        def insert_execution_event(self, *_a, **_k): return None
        def load_submitted_idempotency_keys(self, *_a, **_k): return set()
        def load_open_child_orders(self, *_a, **_k): return []

    class _NoopBroker:
        def is_market_open(self) -> bool: return False
        def get_account(self): return None
        def get_all_positions(self): return []

    try:
        cfg = ExecutionConfig()  # type: ignore[call-arg]
    except TypeError:
        pytest.skip("ExecutionConfig requiert des args — bench non isolable")

    return ProductionExecutor(
        config=cfg,
        repo=_NoopRepo(),  # type: ignore[arg-type]
        broker=_NoopBroker(),  # type: ignore[arg-type]
        oco=OcoManager(_NoopBroker(), _NoopRepo()),  # type: ignore[arg-type]
    )


def test_executor_execute_run_benchmark(benchmark) -> None:
    executor = _build_executor()

    def _run() -> None:
        executor.execute_run(risk_run_id="bench", trade_date=date.today())

    benchmark.pedantic(_run, rounds=5, iterations=1)

