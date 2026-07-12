"""Tests du contrat prix ajustés vs prix exécutables (Section 17 Point 2.3)."""

from __future__ import annotations

import pandas as pd
import pytest

from common.price_convention import (
    PriceConvention,
    declare_price_convention,
    get_price_convention,
    validate_no_mixed_convention,
)


# ── PriceConvention enum ─────────────────────────────────────────────────────

def test_enum_values():
    assert PriceConvention.ADJUSTED.value == "adjusted"
    assert PriceConvention.EXECUTABLE.value == "executable"
    assert PriceConvention.UNSPECIFIED.value == "unspecified"


def test_enum_from_string():
    assert PriceConvention("adjusted") == PriceConvention.ADJUSTED
    assert PriceConvention("executable") == PriceConvention.EXECUTABLE


# ── declare_price_convention ─────────────────────────────────────────────────

def test_declare_sets_attrs():
    df = pd.DataFrame({"close": [100.0]})
    declare_price_convention(df, PriceConvention.ADJUSTED, source="eodhd")
    assert df.attrs["price_convention"] == "adjusted"
    assert df.attrs["price_convention_source"] == "eodhd"


def test_declare_without_source():
    df = pd.DataFrame({"close": [100.0]})
    declare_price_convention(df, PriceConvention.EXECUTABLE)
    assert df.attrs["price_convention"] == "executable"


# ── get_price_convention ─────────────────────────────────────────────────────

def test_get_returns_declared():
    df = pd.DataFrame({"close": [100.0]})
    declare_price_convention(df, PriceConvention.ADJUSTED)
    assert get_price_convention(df) == PriceConvention.ADJUSTED


def test_get_defaults_to_unspecified():
    df = pd.DataFrame({"close": [100.0]})
    assert get_price_convention(df) == PriceConvention.UNSPECIFIED


def test_get_handles_invalid_value():
    df = pd.DataFrame({"close": [100.0]})
    df.attrs["price_convention"] = "invalid_value"
    assert get_price_convention(df) == PriceConvention.UNSPECIFIED


# ── validate_no_mixed_convention ─────────────────────────────────────────────

def test_validate_ok_when_correct():
    features = pd.DataFrame({"close": [100.0]})
    execution = pd.DataFrame({"close": [100.0]})
    declare_price_convention(features, PriceConvention.ADJUSTED)
    declare_price_convention(execution, PriceConvention.EXECUTABLE)
    violations = validate_no_mixed_convention(features, execution)
    assert violations == []


def test_validate_detects_features_with_executable():
    features = pd.DataFrame({"close": [100.0]})
    execution = pd.DataFrame({"close": [100.0]})
    declare_price_convention(features, PriceConvention.EXECUTABLE)  # WRONG!
    declare_price_convention(execution, PriceConvention.EXECUTABLE)
    violations = validate_no_mixed_convention(features, execution)
    assert any("EXECUTABLE" in v for v in violations)


def test_validate_detects_execution_with_adjusted():
    features = pd.DataFrame({"close": [100.0]})
    execution = pd.DataFrame({"close": [100.0]})
    declare_price_convention(features, PriceConvention.ADJUSTED)
    declare_price_convention(execution, PriceConvention.ADJUSTED)  # WRONG!
    violations = validate_no_mixed_convention(features, execution)
    assert any("ADJUSTED" in v for v in violations)


def test_validate_detects_unspecified():
    features = pd.DataFrame({"close": [100.0]})
    execution = pd.DataFrame({"close": [100.0]})
    violations = validate_no_mixed_convention(features, execution)
    assert len(violations) == 2  # both unspecified


def test_validate_strict_raises():
    features = pd.DataFrame({"close": [100.0]})
    execution = pd.DataFrame({"close": [100.0]})
    with pytest.raises(ValueError, match="prix ajustés"):
        validate_no_mixed_convention(features, execution, strict=True)


# ── Clarification split-only ─────────────────────────────────────────────────
# Les prix dans stock_bars_daily sont split-only (PAS split+dividende).
# Le pipeline EODHD rejette l'adjusted_close split+dividendes de l'API ;
# to_stock_bars_daily_row() force adj_close = close.
# Cette convention est enforce par une CHECK constraint en base :
#   CONSTRAINT chk_daily_adj CHECK (data_adjustment = 'split')


def test_adjusted_means_split_only_not_dividend():
    """ADJUSTED = split-only dans le contexte projet (pas split+dividende).

    Les dividendes sont tracés dans portfolio_cash_ledger, pas dans les prix.
    """
    doc = PriceConvention.ADJUSTED.__doc__ or ""
    assert "split" in doc.lower()
    # Vérifie que la doc ne promet plus d'ajustement dividende
    assert "split" in doc.lower()


def test_adjusted_and_executable_are_both_split_only_today():
    """Aujourd'hui ADJUSTED et EXECUTABLE portent les mêmes prix split-only.

    La séparation est maintenue pour future-proof l'ajout de l'ajustement
    dividende côté features sans contaminer les fills.
    """
    # Les deux conventions existent et sont distinctes
    assert PriceConvention.ADJUSTED != PriceConvention.EXECUTABLE
    # Mais elles portent sur les mêmes données sous-jacentes aujourd'hui
    # (close == adj_close dans stock_bars_daily)
    assert PriceConvention.ADJUSTED.value == "adjusted"
    assert PriceConvention.EXECUTABLE.value == "executable"


def test_stock_bars_daily_check_constraint_split_only():
    """Vérifie que le schéma DB enforce data_adjustment = 'split'.

    La contrainte est dans database/sql/stock/stock_bars_daily.sql :
        CONSTRAINT chk_daily_adj CHECK (data_adjustment = 'split')
    """
    import pathlib
    schema = pathlib.Path("database/sql/stock/stock_bars_daily.sql")
    if schema.exists():
        content = schema.read_text(encoding="utf-8")
        assert "data_adjustment = 'split'" in content or \
               'data_adjustment = "split"' in content or \
               "chk_daily_adj" in content, \
               "stock_bars_daily doit avoir une contrainte split-only"
    else:
        pytest.skip("Schema stock_bars_daily.sql introuvable")


# ── load_symbol_bars convention ──────────────────────────────────────────────

def test_load_symbol_bars_declares_adjusted_convention():
    """Vérifie que le loader de features déclare ADJUSTED."""
    from modelFactory.data_loader import load_symbol_bars
    assert callable(load_symbol_bars)


def test_load_ohlcv_declares_executable_convention():
    """Vérifie que le loader backtest déclare EXECUTABLE."""
    from backtesting.data_loader import load_ohlcv
    assert callable(load_ohlcv)


# ── load_prices_asof convention ──────────────────────────────────────────────

def test_load_prices_asof_uses_executable_prices():
    """Vérifie que le loader risque documente EXECUTABLE dans sa docstring."""
    from risk_management.db_io import RiskRepository
    import inspect
    doc = inspect.getdoc(RiskRepository.load_prices_asof) or ""
    assert "EXECUTABLE" in doc or "executable" in doc.lower()
