"""Sprint S25.4 — Test de stabilité de l'API publique v1.0.

Vérifie que la liste des symboles publics scannés via AST correspond
exactement au golden file ``doc/api_v1_public_symbols.txt``. Tout ajout
ou retrait non-validé fait échouer le test (revue obligatoire avant merge).

Pour mettre à jour la liste :
``python scripts/audit_private_api_exposure.py --update-golden``
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_private_api_exposure import (
    GOLDEN_FILE,
    SCANNED_PACKAGES,
    _collect_private_exposures,
    _collect_public_symbols,
    _load_golden,
)


def _current_qnames() -> set[str]:
    return {s.qualname() for s in _collect_public_symbols(SCANNED_PACKAGES)}


def test_golden_file_exists() -> None:
    assert GOLDEN_FILE.exists(), (
        f"Golden file manquant : {GOLDEN_FILE}. Lancez "
        f"`python scripts/audit_private_api_exposure.py --update-golden`."
    )


def test_no_new_public_symbols() -> None:
    golden = _load_golden()
    current = _current_qnames()
    new = current - golden
    assert not new, (
        f"{len(new)} nouveau(x) symbole(s) public(s) non référencé(s) "
        f"dans le golden file :\n  + " + "\n  + ".join(sorted(new))
        + "\n\nSi voulu : régénérer + commit "
          "`python scripts/audit_private_api_exposure.py --update-golden`."
    )


def test_no_removed_public_symbols() -> None:
    golden = _load_golden()
    current = _current_qnames()
    removed = golden - current
    assert not removed, (
        f"{len(removed)} symbole(s) public(s) supprimé(s) (breaking v1.0) :\n"
        + "\n  - ".join(sorted(removed))
    )


def test_no_private_exposures() -> None:
    """Aucun symbole privé de core/, service/, risk_management/ ne doit
    être importé depuis l'extérieur du package."""
    exposures = _collect_private_exposures(SCANNED_PACKAGES)
    assert not exposures, (
        f"{len(exposures)} exposition(s) privée(s) détectée(s) :\n"
        + "\n  ! ".join(
            f"{e.importing_module} imports {e.symbol} from {e.source_module}"
            for e in exposures
        )
    )

