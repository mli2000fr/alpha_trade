"""Sprint S24.1 — Property-based fuzz BacktestVsLive.

Exécute la même séquence d'événements dans le moteur **replay backtest**
et le moteur **live simulé** (cf. ``backtesting/fuzz_runner._run_engine``)
puis vérifie sous fuzz que les résultats sont identiques aux tolérances
près. Complète la batterie ``tests/property/test_synthetic_bracket_*``
en se concentrant sur la **parité** plutôt que sur les invariants OCO.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from backtesting.fuzz_runner import FuzzScenario, _run_engine
from backtesting.fuzz_tolerance import FuzzTolerance

pytestmark = pytest.mark.property


_KIND = st.sampled_from(("tick", "partial_fill", "cancel", "broker_error", "eod_close"))


@st.composite
def _scenario(draw):
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    entry = draw(st.floats(min_value=10.0, max_value=500.0,
                            allow_nan=False, allow_infinity=False))
    tp = entry * draw(st.floats(min_value=1.005, max_value=1.05,
                                 allow_nan=False, allow_infinity=False))
    sl = entry * draw(st.floats(min_value=0.95, max_value=0.995,
                                 allow_nan=False, allow_infinity=False))
    qty = float(draw(st.integers(min_value=1, max_value=1000)))
    n_events = draw(st.integers(min_value=1, max_value=12))
    events = tuple(
        (
            draw(_KIND),
            draw(st.floats(min_value=-0.05, max_value=0.05,
                           allow_nan=False, allow_infinity=False)),
        )
        for _ in range(n_events)
    )
    return FuzzScenario(
        seed=seed, qty=qty,
        entry_price=round(entry, 4),
        tp_price=round(tp, 4),
        sl_price=round(sl, 4),
        events=events,
    )


@settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(scenario=_scenario())
def test_backtest_vs_live_parity(scenario: FuzzScenario) -> None:
    tol = FuzzTolerance()
    live = _run_engine(scenario, is_live=True)
    replay = _run_engine(scenario, is_live=False)
    # PnL & qty
    assert tol.accepts_pnl(live.pnl, replay.pnl), (
        f"PnL divergent : live={live.pnl} replay={replay.pnl} "
        f"events={scenario.events!r}"
    )
    assert tol.accepts_qty(live.qty_filled, replay.qty_filled)
    # Statuts OCO strictement identiques
    assert (live.tp_status, live.sl_status) == (replay.tp_status, replay.sl_status)
    # Audit chain hash identique (déterminisme bout-en-bout)
    assert live.audit_hash == replay.audit_hash


def test_inject_divergence_is_detected_by_runner() -> None:
    """Garde-fou : si on force une divergence, le runner doit la voir."""
    from backtesting.fuzz_runner import run_fuzz_diff

    report = run_fuzz_diff(
        50,
        out_dir=None,
        inject_divergence=True,
    )
    assert report.n_diverged == report.n_scenarios, (
        "L'injection volontaire doit faire diverger 100 % des scénarios."
    )
    assert report.summary["divergence_rate"] == 1.0

