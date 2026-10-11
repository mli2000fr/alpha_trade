"""Shared outcomes independent of the runner's __main__ module identity."""
from dataclasses import dataclass, field
from typing import Any


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
