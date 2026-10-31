"""Shared outcomes independent of the runner's __main__ module identity."""
from dataclasses import dataclass, field
from typing import Any
from contextlib import contextmanager


@dataclass
class Outcome:
    requested: int = 0
    received: int = 0
    persisted: int = 0
    empty: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class BatchRunError(RuntimeError):
    """Blocking error carrying counters even under python -m execution."""
    def __init__(self, message: str, outcome: Outcome):
        super().__init__(message)
        self.outcome = outcome


@contextmanager
def preserve_outcome(outcome):
    """Keep nested provider counters on a subsequent collector/SQL failure."""
    try:
        yield
    except BatchRunError:
        raise
    except Exception as exc:
        raise BatchRunError(str(exc),outcome) from exc
