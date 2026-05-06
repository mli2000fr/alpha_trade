"""Sous-package interne d'``import_eodhd_bar`` (refactor S7-bis).

Le module historique :mod:`dataIntegrityEngine.import_eodhd_bar` reste le
point d'entrée public (CLI + tests). Les sous-modules ci-dessous découpent
sa logique par responsabilité tout en respectant les ``monkeypatch.setattr``
historiques de la suite de tests : toutes les fonctions patchables restent
exposées au niveau du shim, et l'orchestrateur les appelle via
``import dataIntegrityEngine.import_eodhd_bar as _shim``.
"""

__all__: list[str] = []

