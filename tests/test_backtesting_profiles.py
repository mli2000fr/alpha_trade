"""Tests Phase 6.1.e — profils CLI consolidés du backtest."""
from __future__ import annotations

import argparse

import pytest

from backtesting.profiles import BACKTEST_PROFILES, PROFILE_NAMES, apply_profile


def _ns(**kw) -> argparse.Namespace:
    base = dict(
        tp=0.08, ts=0.05, max_positions=20,
        commission_bps=5.0, slippage_bps=5.0,
        account_type="margin", pdt_rule="auto", swing_only=False,
        fees=None, profile="custom",
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_profiles_registry_contains_expected_keys() -> None:
    assert set(PROFILE_NAMES) == {"strict_swing_cash", "swing_cash_aggressive", "production-parity", "custom"}
    assert BACKTEST_PROFILES["custom"] == {}


def test_apply_profile_custom_or_none_is_noop() -> None:
    args = _ns()
    apply_profile(args, "custom", explicit_flags=set())
    apply_profile(args, None, explicit_flags=set())
    # rien n'a bougé
    assert args.tp == 0.08 and args.account_type == "margin" and args.swing_only is False


def test_apply_profile_strict_swing_cash_overrides_defaults() -> None:
    args = _ns()
    apply_profile(args, "strict_swing_cash", explicit_flags=set())
    assert args.account_type == "cash"
    assert args.pdt_rule == "auto"
    assert args.swing_only is True
    assert args.commission_bps == 5.0
    assert args.slippage_bps == 5.0
    assert args.tp == 0.08
    assert args.max_positions == 20


def test_apply_profile_swing_cash_aggressive_overrides_defaults() -> None:
    args = _ns()
    apply_profile(args, "swing_cash_aggressive", explicit_flags=set())
    assert args.tp == 0.12
    assert args.ts == 0.06
    assert args.slippage_bps == 8.0
    assert args.max_positions == 25
    assert args.swing_only is True


def test_apply_profile_explicit_flags_take_precedence() -> None:
    # L'opérateur a explicitement passé --tp 0.30 et --max-positions 7 ;
    # le profil ne doit PAS écraser ces valeurs.
    args = _ns(tp=0.30, max_positions=7)
    apply_profile(args, "swing_cash_aggressive", explicit_flags={"tp", "max_positions"})
    assert args.tp == 0.30  # respecté
    assert args.max_positions == 7  # respecté
    assert args.ts == 0.06  # appliqué par le profil
    assert args.slippage_bps == 8.0  # appliqué par le profil


def test_apply_profile_unknown_name_raises() -> None:
    args = _ns()
    # Les choices argparse filtrent en amont mais on garde un garde-fou explicite.
    with pytest.raises(ValueError, match="Profil backtest inconnu"):
        apply_profile(args, "ghost_profile", explicit_flags=set())


