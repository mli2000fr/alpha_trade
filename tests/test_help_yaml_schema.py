"""Sprint S20 — Audit de schéma sur tous les YAML help.

Vérifie :
- aucun YAML help avec BOM utf-8 (régression S10.1)
- chaque entrée expose les 6 champs obligatoires
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ihm.services.help_loader import REQUIRED_FIELDS, help_dir


def _yaml_files() -> list[Path]:
    return sorted(help_dir().glob("*.yaml"))


def test_help_dir_exists() -> None:
    assert help_dir().is_dir(), f"Répertoire {help_dir()} introuvable"


def test_help_dir_has_yaml_files() -> None:
    files = _yaml_files()
    assert files, "Aucun YAML dans ihm/help/"


@pytest.mark.parametrize("path", _yaml_files(), ids=lambda p: p.name)
def test_yaml_has_no_utf8_bom(path: Path) -> None:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), (
        f"{path.name} contient un BOM utf-8 — régression S10.1"
    )


@pytest.mark.parametrize("path", _yaml_files(), ids=lambda p: p.name)
def test_yaml_entries_have_required_fields(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict), f"{path.name} n'est pas un mapping"
    failures: list[str] = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            failures.append(f"{key}: entrée non dict")
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            failures.append(f"{key}: champs manquants {missing}")
    assert not failures, (
        f"{path.name} — {len(failures)} entrée(s) invalides :\n"
        + "\n".join(failures[:10])
    )

