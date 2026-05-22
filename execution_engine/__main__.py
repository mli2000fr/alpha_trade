"""Point d'entrée: python -m execution_engine."""
from __future__ import annotations

import sys
import warnings

from execution_engine.cli import main


def _should_warn_deprecated_run_path(argv: list[str]) -> bool:
    first_positional = next((arg for arg in argv if not str(arg).startswith("-")), None)
    return first_positional != "cancel-all"


if __name__ == "__main__":
    if _should_warn_deprecated_run_path(sys.argv[1:]):
        warnings.warn(
            "`python -m execution_engine` est déprécié pour le flux `run`; utilisez `python run_execution.py` (ou `run`) à la place. `cancel-all` reste supporté via `python -m execution_engine cancel-all`.",
            DeprecationWarning,
            stacklevel=2,
        )
    main()
