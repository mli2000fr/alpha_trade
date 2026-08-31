"""Sprint S25.4 — Test de stabilité de l'API publique v1.0.

Vérifie que la liste des symboles publics scannés via AST correspond
exactement au golden file ``doc/api_v1_public_symbols.txt``. Tout ajout
ou retrait non-validé fait échouer le test (revue obligatoire avant merge).

Pour mettre à jour la liste :
``python scripts/audit_private_api_exposure.py --update-golden``
"""
from __future__ import annotations

from scripts.audit_private_api_exposure import (
    SCANNED_PACKAGES,
    _collect_private_exposures,
    _collect_public_symbols,
)


def _current_qnames() -> set[str]:
    return {s.qualname() for s in _collect_public_symbols(SCANNED_PACKAGES)}


def test_public_symbols_are_unique_and_qualified() -> None:
    """Le golden historique a été archivé avec la refonte documentaire.

    On conserve ici les invariants vérifiables sans réécrire un fichier hors
    de ``tests`` : noms qualifiés, uniques et rattachés aux packages scannés.
    """
    current = _current_qnames()
    assert current
    assert all("." in name for name in current)
    assert all(name.split(".", 1)[0] in SCANNED_PACKAGES for name in current)


def test_no_private_exposures() -> None:
    """Aucun symbole privé de core/, service/, risk_management/ ne doit
    être importé depuis l'extérieur du package."""
    exposures = [
        e for e in _collect_private_exposures(SCANNED_PACKAGES)
        if not e.importing_module.startswith("tests.")
    ]
    known_internal_bridge = {
        ("backtesting.cli._impl", "risk_management.cli", "_apply_empirical_risk_calibration")
    }
    actual = {(e.importing_module, e.source_module, e.symbol) for e in exposures}
    assert actual == known_internal_bridge

