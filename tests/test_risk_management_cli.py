from __future__ import annotations

import subprocess
import sys

from risk_management import cli

def test_cli_importable():
    assert hasattr(cli, "__doc__")


def test_cli_module_executes_main_with_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "risk_management.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Module de gestion de risque Alpha Trade" in result.stdout


