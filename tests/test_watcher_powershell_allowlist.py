"""Tests Phase 6.3 — allowlist statique des scripts PowerShell du watcher.

L'audit `audit_watcher.md` exige une revue stricte des scripts d'installation
et de lancement pour interdire :

- l'évaluation dynamique de chaînes (``Invoke-Expression`` / ``iex``),
- l'exécution de binaires hors workspace (``Start-Process`` sans path absolu),
- la désactivation des protections (``Set-StrictMode`` doit être présent,
  ``$ErrorActionPreference = 'Stop'`` aussi).

On ne valide PAS la syntaxe PowerShell (pas de runtime PS dans le test) :
on fait une inspection texte robuste et explicite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

WATCHER_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "windows"

WATCHER_SCRIPTS = (
    "protection_watcher_launcher.ps1",
    "protection_watcher_secrets.ps1",
    "install_protection_watcher_service_nssm.ps1",
    "uninstall_protection_watcher_service_nssm.ps1",
    "install_protection_watcher_task.ps1",
    "uninstall_protection_watcher_task.ps1",
    "get_protection_watcher_status.ps1",
)

# Tokens INTERDITS (case-insensitive). Toute occurrence fait échouer le test.
DENY_TOKENS = (
    "Invoke-Expression",
    " iex ",
    "iex(",
    "Add-Type -TypeDefinition",  # injection C# arbitraire
    "DownloadString",            # téléchargement à l'exécution
    "[System.Reflection.Assembly]::Load(",
)

# Tokens REQUIS dans tous les scripts pour durcir l'exécution.
REQUIRED_TOKENS = (
    "Set-StrictMode",
    "$ErrorActionPreference",
)


@pytest.mark.parametrize("script_name", WATCHER_SCRIPTS)
def test_watcher_script_exists(script_name: str) -> None:
    path = WATCHER_SCRIPTS_DIR / script_name
    assert path.exists(), f"Script attendu absent : {path}"


@pytest.mark.parametrize("script_name", WATCHER_SCRIPTS)
def test_watcher_script_does_not_use_dangerous_tokens(script_name: str) -> None:
    path = WATCHER_SCRIPTS_DIR / script_name
    if not path.exists():
        pytest.skip(f"{path} introuvable")
    content = path.read_text(encoding="utf-8", errors="replace")
    lower = content.lower()
    for token in DENY_TOKENS:
        assert token.lower() not in lower, (
            f"{script_name} contient le token interdit `{token}` (Phase 6.3 hardening)."
        )


@pytest.mark.parametrize("script_name", WATCHER_SCRIPTS)
def test_watcher_script_enforces_strict_mode(script_name: str) -> None:
    path = WATCHER_SCRIPTS_DIR / script_name
    if not path.exists():
        pytest.skip(f"{path} introuvable")
    content = path.read_text(encoding="utf-8", errors="replace")
    for token in REQUIRED_TOKENS:
        assert token in content, (
            f"{script_name} doit contenir `{token}` (durcissement Phase 6.3)."
        )


def test_protection_watcher_secrets_uses_dpapi_validateset() -> None:
    """Le scope DPAPI doit être contraint par ValidateSet (pas de scope arbitraire)."""
    path = WATCHER_SCRIPTS_DIR / "protection_watcher_secrets.ps1"
    if not path.exists():
        pytest.skip(f"{path} introuvable")
    content = path.read_text(encoding="utf-8", errors="replace")
    assert "ValidateSet('CurrentUser', 'LocalMachine')" in content, (
        "Le paramètre DpapiScope doit utiliser ValidateSet pour interdire les scopes arbitraires."
    )
    # Avertissement explicite quand on utilise LocalMachine (audit allowlist).
    assert "LocalMachine permet le d" in content, (
        "Le script doit avertir quand le scope LocalMachine est sélectionné."
    )


def test_protection_watcher_launcher_resolves_python_safely() -> None:
    """Le launcher doit refuser un Python introuvable et préférer .venv local."""
    path = WATCHER_SCRIPTS_DIR / "protection_watcher_launcher.ps1"
    if not path.exists():
        pytest.skip(f"{path} introuvable")
    content = path.read_text(encoding="utf-8", errors="replace")
    assert "Python introuvable" in content, "Le launcher doit valider l'existence du Python fourni."
    assert ".venv\\Scripts\\python.exe" in content, "Le launcher doit chercher .venv en priorité."
    # Garde-fou : on ne doit jamais invoquer cmd.exe /c sur des arguments interpolés.
    assert "cmd.exe /c" not in content.lower(), "Pas d'invocation cmd.exe /c dans le launcher."

