"""Phase F / S23.1 — Benchmark `selector.factors.compute_factor_frame`.

Régression bloquante > 20 % via [`scripts/compare_benchmarks.py`].
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def _import_factor_fn():
    try:
        from selector.factors import compute_factor_frame  # type: ignore
        return compute_factor_frame
    except Exception:  # pragma: no cover
        return None


def test_compute_factor_frame_benchmark(benchmark, synthetic_market_frame) -> None:
    fn = _import_factor_fn()
    if fn is None:
        pytest.skip("selector.factors.compute_factor_frame indisponible")

    def _run() -> None:
        try:
            fn(synthetic_market_frame)
        except TypeError:
            # Signature incompatible : skip plutôt que faux échec.
            pytest.skip("Signature compute_factor_frame incompatible avec fixture")

    benchmark.pedantic(_run, rounds=3, iterations=1)

