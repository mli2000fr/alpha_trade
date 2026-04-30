"""Alias retrocompatible - la definition canonique est dans
``core.filter_profiles`` depuis la Phase 3.2.c du refactor.
Ce module conserve les imports historiques afin de ne pas casser les
appelants legacy (IHM ``ihm/services/pipeline_runner.py``, scripts
``prompt/fix_swing/``, tests). Toute nouvelle reference doit utiliser
``from core.filter_profiles import ...``.
"""
from __future__ import annotations
from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile
__all__ = ["STRICT_SWING_CASH_FILTERS", "StrictFilterProfile"]
