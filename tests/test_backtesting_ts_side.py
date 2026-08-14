"""P2-4 — Trailing stop par côté (ts-long / ts-short) + fidélité live ATR."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backtesting.simulator import BacktestConfig, BacktestEngine, _effective_trailing_pct, _production_tp_price


def _cfg(ts_long: float | None = None, ts_short: float | None = None) -> BacktestConfig:
    return BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2020, 6, 30),
        trailing_stop_pct=0.07,
        trailing_stop_long_pct=ts_long,
        trailing_stop_short_pct=ts_short,
    )


def test_no_override_returns_derived() -> None:
    cfg = _cfg()
    assert _effective_trailing_pct(cfg, short=False, derived_pct=0.05) == 0.05
    assert _effective_trailing_pct(cfg, short=True, derived_pct=0.05) == 0.05


def test_override_acts_as_floor_and_is_side_specific() -> None:
    cfg = _cfg(ts_long=0.12)
    # long : élargi au plancher 0.12
    assert _effective_trailing_pct(cfg, short=False, derived_pct=0.05) == 0.12
    # long : déjà plus large que l'override → inchangé
    assert _effective_trailing_pct(cfg, short=False, derived_pct=0.15) == 0.15
    # short : jamais touché par ts_long
    assert _effective_trailing_pct(cfg, short=True, derived_pct=0.05) == 0.05


def test_short_override() -> None:
    cfg = _cfg(ts_short=0.10)
    assert _effective_trailing_pct(cfg, short=True, derived_pct=0.07) == 0.10
    assert _effective_trailing_pct(cfg, short=False, derived_pct=0.07) == 0.07


def test_defaults_none_preserve_legacy_behavior() -> None:
    cfg = BacktestConfig(start_date=date(2020, 1, 1), end_date=date(2020, 6, 30))
    assert cfg.trailing_stop_long_pct is None
    assert cfg.trailing_stop_short_pct is None
    assert _effective_trailing_pct(cfg, short=False, derived_pct=float(cfg.trailing_stop_pct)) == cfg.trailing_stop_pct


# ── P2-4 — fidélité live : risk_per_share = entry × atr_pct_20 × k ──────────


def _atr_engine(multiple: float) -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2020, 6, 30),
        atr_risk_stop_multiple=multiple,
    )
    return BacktestEngine(cfg)


def _atr_row(atr_pct: float | None = 0.03, risk: float | None = None, stop: float | None = None) -> pd.Series:
    return pd.Series({"atr_pct_20": atr_pct, "risk_per_share": risk, "stop_price_initial": stop})


def test_atr_risk_derivation_long() -> None:
    engine = _atr_engine(2.0)
    stop, risk = engine._resolve_initial_protection_state(
        row=_atr_row(), entry_price=100.0, fallback_initial_stop_pct=0.05, side="buy"
    )
    assert risk == pytest.approx(6.0)
    assert stop == pytest.approx(94.0)


def test_atr_risk_derivation_short() -> None:
    engine = _atr_engine(2.0)
    stop, risk = engine._resolve_initial_protection_state(
        row=_atr_row(), entry_price=100.0, fallback_initial_stop_pct=0.05, side="sell"
    )
    assert risk == pytest.approx(6.0)
    assert stop == pytest.approx(106.0)


def test_atr_risk_disabled_by_default_preserves_legacy() -> None:
    engine = _atr_engine(0.0)
    stop, risk = engine._resolve_initial_protection_state(
        row=_atr_row(), entry_price=100.0, fallback_initial_stop_pct=0.05, side="buy"
    )
    assert (stop, risk) == (None, None)


def test_atr_risk_missing_column_returns_none() -> None:
    engine = _atr_engine(2.0)
    row = pd.Series({"risk_per_share": None, "stop_price_initial": None})
    stop, risk = engine._resolve_initial_protection_state(
        row=row, entry_price=100.0, fallback_initial_stop_pct=0.05, side="buy"
    )
    assert (stop, risk) == (None, None)


def test_explicit_risk_takes_priority_over_atr() -> None:
    engine = _atr_engine(2.0)
    stop, risk = engine._resolve_initial_protection_state(
        row=_atr_row(atr_pct=0.03, risk=8.0), entry_price=100.0, fallback_initial_stop_pct=0.05, side="buy"
    )
    assert risk == pytest.approx(8.0)
    assert stop == pytest.approx(92.0)


# ── P2-4 — TP de production : min(ATR × tp_atr_multiple, prix × tp_max_pct) ──


def test_production_tp_long_atr_capped_by_pct() -> None:
    # entry 100, ATR 4% → ATR×3 = 12 > cap 7% → cap gagne
    tp = _production_tp_price(100.0, 0.04, 3.0, 0.07, short=False)
    assert tp == pytest.approx(107.0)


def test_production_tp_long_atr_below_cap() -> None:
    # entry 100, ATR 1% → ATR×3 = 3 < cap 7% → ATR gagne
    tp = _production_tp_price(100.0, 0.01, 3.0, 0.07, short=False)
    assert tp == pytest.approx(103.0)


def test_production_tp_short_direction_aware() -> None:
    tp = _production_tp_price(100.0, 0.01, 3.0, 0.07, short=True)
    assert tp == pytest.approx(97.0)


def test_production_tp_disabled_returns_none() -> None:
    assert _production_tp_price(100.0, 0.03, 0.0, 0.07, short=False) is None
    assert _production_tp_price(100.0, 0.03, 3.0, 0.0, short=False) is None
    assert _production_tp_price(100.0, None, 3.0, 0.07, short=False) is None
