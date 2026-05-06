"""Sprint S26.3 / A17 — Tests scaffold pour ``execution_engine.executor_phases``.

Vérifie l'interface de l'orchestrateur et le fail-loud par défaut tant que
``ProductionExecutor`` n'est pas câblé. La suite round-trip bracket réelle
(comparaison ligne-à-ligne avec ``ProductionExecutor.execute_run`` sur un
broker mock) est planifiée dans une PR S26.3.b dédiée.
"""
from __future__ import annotations

import os

import pytest

from execution_engine import executor_phases as ep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyExecutor:
    """Executor minimal exposant les 4 méthodes ``_phase_*_impl``."""

    def __init__(self, *, fail_at: str | None = None):
        self.calls: list[str] = []
        self._fail_at = fail_at

    def _make(self, name: str):
        def impl(ctx):
            self.calls.append(name)
            ctx.metrics[f"{name}_called"] = True
            if self._fail_at == name:
                return ep.PhaseOutcome(ep.PhaseStatus.ABORT, reason=f"forced abort at {name}")
            return ep.PhaseOutcome(ep.PhaseStatus.CONTINUE)
        return impl

    def __getattr__(self, item):  # méthodes dynamiques _phase_*_impl
        if item.startswith("_phase_") and item.endswith("_impl"):
            return self._make(item.replace("_phase_", "").replace("_impl", ""))
        raise AttributeError(item)


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_phase_outcome_continue_default():
    out = ep.PhaseOutcome()
    assert out.status is ep.PhaseStatus.CONTINUE
    assert out.should_continue is True


def test_phase_outcome_abort_does_not_continue():
    out = ep.PhaseOutcome(ep.PhaseStatus.ABORT, reason="x")
    assert out.should_continue is False


def test_phase_context_defaults_are_isolated():
    a = ep.PhaseContext()
    b = ep.PhaseContext()
    a.metrics["k"] = 1
    a.events.append("evt")
    assert b.metrics == {}
    assert b.events == []


def test_is_phases_orchestrator_enabled(monkeypatch):
    monkeypatch.delenv(ep.ENV_TOGGLE, raising=False)
    assert ep.is_phases_orchestrator_enabled() is False
    monkeypatch.setenv(ep.ENV_TOGGLE, "1")
    assert ep.is_phases_orchestrator_enabled() is True
    monkeypatch.setenv(ep.ENV_TOGGLE, "no")
    assert ep.is_phases_orchestrator_enabled() is False


# ---------------------------------------------------------------------------
# Fail-loud par défaut : si l'executor n'expose pas les 4 méthodes _impl,
# chaque phase doit retourner un ABORT explicite ⇒ jamais de no-op silencieux
# en prod.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phase",
    [
        ep.phase_init_and_preflight,
        ep.phase_build_and_submit,
        ep.phase_poll_and_children,
        ep.phase_reconcile_and_finalize,
    ],
    ids=lambda p: p.__name__,
)
def test_phase_aborts_when_executor_not_wired(phase):
    class _NoImpl:
        pass
    out = phase(_NoImpl(), ep.PhaseContext())
    assert out.status is ep.PhaseStatus.ABORT
    assert "non câblé" in (out.reason or "")


# ---------------------------------------------------------------------------
# Orchestrateur ``run_phases`` : ordre, propagation d'abort, type-check.
# ---------------------------------------------------------------------------


def test_run_phases_executes_all_in_order_when_continue():
    executor = _DummyExecutor()
    ctx = ep.PhaseContext()
    metrics = ep.run_phases(executor, ctx)
    assert executor.calls == [
        "init_and_preflight",
        "build_and_submit",
        "poll_and_children",
        "reconcile_and_finalize",
    ]
    assert metrics is ctx.metrics
    for name in executor.calls:
        assert metrics[f"{name}_called"] is True


def test_run_phases_stops_at_first_abort():
    executor = _DummyExecutor(fail_at="build_and_submit")
    ctx = ep.PhaseContext()
    metrics = ep.run_phases(executor, ctx)
    # Phase 3 et 4 ne doivent PAS avoir été exécutées.
    assert executor.calls == ["init_and_preflight", "build_and_submit"]
    assert metrics["status"] == "ABORTED"
    assert metrics["abort_phase"] == "phase_build_and_submit"
    assert "forced abort" in metrics["abort_reason"]


def test_run_phases_rejects_non_outcome_returns():
    class _BadExecutor:
        def _phase_init_and_preflight_impl(self, ctx):
            return "not an outcome"

    with pytest.raises(TypeError, match="PhaseOutcome"):
        ep.run_phases(_BadExecutor(), ep.PhaseContext())


def test_run_phases_returns_metrics_even_on_first_phase_abort():
    executor = _DummyExecutor(fail_at="init_and_preflight")
    ctx = ep.PhaseContext()
    ctx.metrics["preset"] = "value"
    metrics = ep.run_phases(executor, ctx)
    assert metrics["preset"] == "value"  # état préexistant préservé
    assert metrics["status"] == "ABORTED"
    assert executor.calls == ["init_and_preflight"]

