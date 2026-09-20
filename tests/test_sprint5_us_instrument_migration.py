from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from scripts.audit_sprint5_us_parity import (
    _stable_frame_hash,
    audit_symbol_only_joins,
)
from service.market.bootstrap_us_instruments import (
    FACT_TABLES,
    TICKER_PATTERN,
    _advance_months,
)


def _load_migration(filename: str):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fact_column_and_constraint_scopes_are_identical() -> None:
    columns_migration = _load_migration("0087_us_fact_instrument_columns.py")
    constraints_migration = _load_migration("0088_us_fact_instrument_constraints.py")
    assert set(columns_migration.FACT_TABLES) == set(FACT_TABLES)
    assert set(constraints_migration.TABLE_DATES) == set(FACT_TABLES)


def test_legacy_trigger_rejects_an_ambiguous_us_ticker() -> None:
    constraints_migration = _load_migration("0088_us_fact_instrument_constraints.py")
    trigger_sql = constraints_migration._trigger_sql("model_predictions", "INSERT")
    assert "ambiguous legacy US instrument identity" in trigger_sql
    assert "SELECT COUNT(*) FROM instruments" in trigger_sql
    assert "EXISTS (" in trigger_sql
    assert "FROM stock_metadata sm" in trigger_sql
    assert "known_i.market_code='US_EQ'" in trigger_sql


def test_constraint_migration_uses_real_pit_date_columns_and_is_resumable() -> None:
    constraints_migration = _load_migration("0088_us_fact_instrument_constraints.py")
    assert constraints_migration.TABLE_DATES["stock_fundamentals_daily"] == "trade_date"
    assert constraints_migration.TABLE_DATES["stock_analyst_consensus_snapshots"] == "observed_at"
    source = Path(constraints_migration.__file__).read_text(encoding="utf-8")
    assert "index_name in existing_indexes and fk_name in existing_fks" in source
    assert "if index_name not in existing_indexes" in source
    assert "if fk_name not in existing_fks" in source
    assert "AND m.symbol IS NOT NULL" in source


def test_ticker_classifier_excludes_aggregate_model_rows() -> None:
    assert TICKER_PATTERN.fullmatch("BF.A")
    assert TICKER_PATTERN.fullmatch("BRK-B")
    assert not TICKER_PATTERN.fullmatch("Health Care")
    assert not TICKER_PATTERN.fullmatch("__GLOBAL__")


def test_date_backfill_cursor_supports_quarter_chunks() -> None:
    assert str(_advance_months(pd.Timestamp("2024-11-15").date(), 3)) == "2025-02-01"


def test_frame_hash_is_row_order_independent() -> None:
    first = pd.DataFrame({"symbol": ["B", "A"], "value": [2.0, 1.0]})
    second = first.iloc[::-1].reset_index(drop=True)
    assert _stable_frame_hash(first) == _stable_frame_hash(second)


def test_no_critical_symbol_only_join_remains() -> None:
    report = audit_symbol_only_joins(Path(__file__).resolve().parents[1])
    assert report["critical_count"] == 0, report["findings"]
