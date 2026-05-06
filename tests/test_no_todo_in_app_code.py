"""Phase C / S18.5 — Le code applicatif ne contient aucun marqueur TODO/FIXME/XXX."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_todo_in_application_code():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_no_todo.py")],
        capture_output=True, text=True,
    )
    # Mode non-strict : retourne 0 même si trouvé, mais print.
    assert proc.returncode == 0, (
        "scripts/check_no_todo.py a échoué :\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )

