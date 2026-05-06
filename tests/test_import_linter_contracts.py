"""Phase 7.1 — Tests contractuels d'imports (warn-only).

S10.3 — Réécrit pour utiliser la CLI `lint-imports` (interface stable) au lieu
de l'API privée `importlinter.application.use_cases` qui change entre versions.

Le jour où l'on souhaite passer bloquant : retirer ``xfail`` sur le test
``test_importlinter_contracts_pass``.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _import_linter_available() -> bool:
    try:
        import importlinter  # noqa: F401  (dépendance optionnelle dev)
    except ImportError:
        return False
    return True


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / ".importlinter"


@pytest.mark.skipif(not _import_linter_available(), reason="import-linter non installé (extras [dev])")
def test_importlinter_config_loads() -> None:
    """La config ``.importlinter`` doit exister et exposer au moins un contrat."""
    assert _CONFIG_PATH.is_file(), f"Config import-linter introuvable : {_CONFIG_PATH}"

    # Vérification minimale indépendante de la version de la lib.
    raw = _CONFIG_PATH.read_text(encoding="utf-8")
    assert "[importlinter]" in raw, "Section [importlinter] manquante."
    assert "contract" in raw.lower(), "Aucun contrat défini dans .importlinter."


@pytest.mark.skipif(not _import_linter_available(), reason="import-linter non installé (extras [dev])")
@pytest.mark.xfail(
    reason="Phase 7.1 : warn-only — passage bloquant après triage backlog (audit_global §7.1).",
    strict=False,
)
def test_importlinter_contracts_pass() -> None:
    """Lance la CLI ``lint-imports`` ; ``xfail`` accepté tant qu'on warn-only."""
    # On invoque le module CLI plutôt que l'API privée pour rester compatible
    # avec toutes les versions ≥ 1.x (S10.3).
    cmd: list[str]
    if shutil.which("lint-imports"):
        cmd = ["lint-imports", "--config", str(_CONFIG_PATH)]
    else:
        cmd = [sys.executable, "-m", "importlinter", "--config", str(_CONFIG_PATH)]
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, (
        "Au moins un contrat import-linter est en violation.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

