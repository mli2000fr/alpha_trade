"""Phase 7.1 — Tests contractuels d'imports (warn-only).

Vérifie que la configuration ``.importlinter`` est valide et que les contrats
chargent. Les violations résiduelles connues sont tolérées via ``xfail`` afin
de ne pas bloquer la CI le temps du triage backlog (cf. ``audit_global §7.1``).

Le jour où l'on souhaite passer bloquant : retirer ``xfail`` et corriger les
imports résiduels.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _import_linter_available() -> bool:
    try:
        import importlinter  # noqa: F401  (dépendance optionnelle dev)
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _import_linter_available(), reason="import-linter non installé (extras [dev])")
def test_importlinter_config_loads() -> None:
    """La config ``.importlinter`` doit être lisible et structurée."""
    from importlinter.application.use_cases import read_user_options

    config = Path(__file__).resolve().parent.parent / ".importlinter"
    assert config.is_file(), f"Config import-linter introuvable : {config}"
    options = read_user_options(config_filename=str(config))
    assert options is not None
    assert getattr(options, "session_options", {}) or getattr(options, "contracts_options", [])


@pytest.mark.skipif(not _import_linter_available(), reason="import-linter non installé (extras [dev])")
@pytest.mark.xfail(
    reason="Phase 7.1 : warn-only — passage bloquant après triage backlog (audit_global §7.1).",
    strict=False,
)
def test_importlinter_contracts_pass() -> None:
    """Lance les contrats import-linter ; ``xfail`` accepté tant qu'on warn-only."""
    from importlinter.application.use_cases import lint_imports

    config = Path(__file__).resolve().parent.parent / ".importlinter"
    exit_code = lint_imports(config_filename=str(config), is_debug_mode=False)
    assert exit_code == 0, "Au moins un contrat import-linter est en violation."

