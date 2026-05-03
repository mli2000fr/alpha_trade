"""État runtime in-memory pour le suivi live de Model Factory.

Ce module reste volontairement simple : un dictionnaire protégé par verrou,
mis à jour par l'orchestrateur et le trainer, puis relu périodiquement par le
CLI pour émettre des heartbeats structurés vers l'IHM.
"""
from __future__ import annotations

from threading import Lock
from typing import Any

_STATE_LOCK = Lock()
_STATE: dict[str, Any] = {}


def reset_runtime_status(initial: dict[str, Any] | None = None) -> None:
    with _STATE_LOCK:
        _STATE.clear()
        if initial:
            _STATE.update(initial)


def update_runtime_status(**updates: Any) -> dict[str, Any]:
    with _STATE_LOCK:
        _STATE.update(updates)
        return dict(_STATE)


def increment_runtime_counter(name: str, amount: int = 1) -> int:
    with _STATE_LOCK:
        current = int(_STATE.get(name, 0) or 0) + int(amount)
        _STATE[name] = current
        return current


def snapshot_runtime_status() -> dict[str, Any]:
    with _STATE_LOCK:
        return dict(_STATE)

