"""Profils CLI consolidés pour le backtest (Phase 6.1.e).

Source de vérité unique pour les jeux de paramètres backtest récurrents
(``strict_swing_cash``, ``swing_cash_aggressive``, ``custom``). Les valeurs
sont alignées sur :mod:`core.filter_profiles` (filtres) et sur les
conventions live (TP/TS/max_positions/account_type/pdt_rule/swing_only).

Les flags CLI explicites overridrent toujours les valeurs du profil
(défaut argparse < profil < CLI explicite).
"""
from __future__ import annotations

from typing import Any

# Profils stables. ``None`` = ne pas surcharger le défaut argparse.
BACKTEST_PROFILES: dict[str, dict[str, Any]] = {
    "strict_swing_cash": {
        "tp": 0.08,
        "ts": 0.05,
        "max_positions": 20,
        "commission_bps": 5.0,
        "slippage_bps": 5.0,
        "account_type": "cash",
        "pdt_rule": "auto",
        "swing_only": True,
    },
    "swing_cash_aggressive": {
        "tp": 0.12,
        "ts": 0.06,
        "max_positions": 25,
        "commission_bps": 5.0,
        "slippage_bps": 8.0,
        "account_type": "cash",
        "pdt_rule": "auto",
        "swing_only": True,
    },
    # custom = pas de surcharge ; on garde les défauts CLI.
    "custom": {},
}

PROFILE_NAMES = tuple(BACKTEST_PROFILES.keys())


def apply_profile(args, profile_name: str | None, *, explicit_flags: set[str]) -> None:
    """Applique les valeurs d'un profil à ``args`` sans écraser les flags explicites.

    ``explicit_flags`` contient les noms d'attributs (ex: ``"tp"``) que
    l'opérateur a explicitement passés sur la ligne de commande.
    """
    if not profile_name or profile_name == "custom":
        return
    profile = BACKTEST_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(f"Profil backtest inconnu : {profile_name}")
    for key, value in profile.items():
        if value is None:
            continue
        if key in explicit_flags:
            continue
        setattr(args, key, value)


__all__ = ["BACKTEST_PROFILES", "PROFILE_NAMES", "apply_profile"]

