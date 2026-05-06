"""S11.3 — Tests de l'auto-rollback champion ML."""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from modelFactory.auto_rollback import (
    auto_rollback_if_needed,
    count_consecutive_disabled_days,
)


def _decision(gate: str, model_id: str = "modelA"):
    return SimpleNamespace(gate=gate, model_id=model_id)


def test_count_consecutive_disabled_days_returns_streak_from_today():
    today = date(2026, 5, 6)
    decisions = [
        (today, _decision("disabled")),
        (today - timedelta(days=1), _decision("disabled")),
        (today - timedelta(days=2), _decision("disabled")),
        (today - timedelta(days=3), _decision("enabled")),  # break
        (today - timedelta(days=4), _decision("disabled")),  # n'est pas comptée
    ]
    assert count_consecutive_disabled_days(decisions) == 3


def test_count_consecutive_disabled_days_zero_when_latest_enabled():
    today = date(2026, 5, 6)
    decisions = [
        (today, _decision("enabled")),
        (today - timedelta(days=1), _decision("disabled")),
    ]
    assert count_consecutive_disabled_days(decisions) == 0


def test_count_consecutive_handles_dict_decisions():
    today = date(2026, 5, 6)
    decisions = [
        (today, {"gate": "disabled"}),
        (today - timedelta(days=1), {"gate": "disabled"}),
    ]
    assert count_consecutive_disabled_days(decisions) == 2


def test_no_rollback_below_threshold():
    today = date(2026, 5, 6)
    history = [(today, _decision("disabled")), (today - timedelta(days=1), _decision("disabled"))]
    outcome = auto_rollback_if_needed(
        "AAPL",
        threshold_days=3,
        decision_history_loader=lambda symbol, *, engine: history,
        challenger_resolver=lambda symbol, *, engine, current_champion: pytest.fail("ne doit pas être appelé"),
    )
    assert outcome.triggered is False
    assert outcome.reason == "below_threshold"
    assert outcome.consecutive_disabled_days == 2


def test_rollback_promotes_previous_challenger_after_3_days_dry_run():
    today = date(2026, 5, 6)
    history = [
        (today, _decision("disabled")),
        (today - timedelta(days=1), _decision("disabled")),
        (today - timedelta(days=2), _decision("disabled")),
    ]
    swap_calls: list[dict] = []
    notifs: list[str] = []

    class _Notifier:
        def notify_warning(self, msg: str) -> None:
            notifs.append(msg)

    outcome = auto_rollback_if_needed(
        "AAPL",
        threshold_days=3,
        dry_run=True,
        decision_history_loader=lambda symbol, *, engine: history,
        challenger_resolver=lambda symbol, *, engine, current_champion: "modelB",
        current_champion_loader=lambda symbol, *, engine: "modelA",
        champion_swapper=lambda *args, **kw: swap_calls.append(kw) or {"swapped": True},
        notifier_factory=lambda: _Notifier(),
    )
    assert outcome.triggered is True
    assert outcome.previous_champion == "modelA"
    assert outcome.promoted_challenger == "modelB"
    assert outcome.dry_run is True
    # En dry-run, swapper NON appelé.
    assert swap_calls == []
    # Notif émise.
    assert notifs and "DRY-RUN" in notifs[0]


def test_rollback_executes_swap_when_dry_run_false():
    today = date(2026, 5, 6)
    history = [(today - timedelta(days=i), _decision("disabled")) for i in range(3)]
    swap_calls: list[dict] = []

    outcome = auto_rollback_if_needed(
        "AAPL",
        threshold_days=3,
        dry_run=False,
        decision_history_loader=lambda symbol, *, engine: history,
        challenger_resolver=lambda symbol, *, engine, current_champion: "modelB",
        current_champion_loader=lambda symbol, *, engine: "modelA",
        champion_swapper=lambda symbol, **kw: swap_calls.append({"symbol": symbol, **kw}) or {"swapped": True},
    )
    assert outcome.triggered is True
    assert outcome.dry_run is False
    assert len(swap_calls) == 1
    assert swap_calls[0]["from_model"] == "modelA"
    assert swap_calls[0]["to_model"] == "modelB"
    assert "ml_gate_disabled_3" in swap_calls[0]["reason"]


def test_no_rollback_when_no_validated_challenger_available():
    today = date(2026, 5, 6)
    history = [(today - timedelta(days=i), _decision("disabled")) for i in range(3)]
    notifs: list[str] = []

    class _Notifier:
        def notify_warning(self, msg: str) -> None:
            notifs.append(msg)

    outcome = auto_rollback_if_needed(
        "AAPL",
        threshold_days=3,
        decision_history_loader=lambda symbol, *, engine: history,
        challenger_resolver=lambda symbol, *, engine, current_champion: None,
        current_champion_loader=lambda symbol, *, engine: "modelA",
        notifier_factory=lambda: _Notifier(),
    )
    assert outcome.triggered is False
    assert outcome.reason == "no_validated_challenger"
    assert notifs and "aucun challenger" in notifs[0]


def test_rollback_records_swap_failure_gracefully():
    today = date(2026, 5, 6)
    history = [(today - timedelta(days=i), _decision("disabled")) for i in range(3)]

    def _failing_swap(symbol, **kw):
        raise RuntimeError("DB write failed")

    outcome = auto_rollback_if_needed(
        "AAPL",
        threshold_days=3,
        dry_run=False,
        decision_history_loader=lambda symbol, *, engine: history,
        challenger_resolver=lambda symbol, *, engine, current_champion: "modelB",
        current_champion_loader=lambda symbol, *, engine: "modelA",
        champion_swapper=_failing_swap,
    )
    assert outcome.triggered is False
    assert "swap_failed" in outcome.reason
    assert outcome.promoted_challenger == "modelB"  # tentative consignée

