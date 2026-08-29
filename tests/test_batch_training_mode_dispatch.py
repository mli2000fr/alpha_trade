"""Tests unitaires — détection du mode d'entraînement d'un batch (dispatch predict)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from modelFactory.db_registry import detect_batch_training_mode


def _engine() -> "create_engine":  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE model_training_batch (
                batch_id VARCHAR(64) PRIMARY KEY,
                command_argv_json TEXT,
                command_line TEXT,
                metadata_json TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE model_training_run (
                run_id VARCHAR(64) PRIMARY KEY,
                batch_id VARCHAR(64),
                symbol VARCHAR(32)
            )
        """))
    return engine


def _insert_batch(engine, batch_id: str, argv: list[str] | None, command_line: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO model_training_batch (batch_id, command_argv_json, command_line) "
                "VALUES (:bid, :argv, :line)"
            ),
            {
                "bid": batch_id,
                "argv": json.dumps(argv) if argv is not None else None,
                "line": command_line,
            },
        )


def _insert_run(engine, run_id: str, batch_id: str, symbol: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO model_training_run (run_id, batch_id, symbol) VALUES (:r, :b, :s)"),
            {"r": run_id, "b": batch_id, "s": symbol},
        )


@pytest.mark.unit
def test_detect_per_sector_from_argv_json() -> None:
    engine = _engine()
    _insert_batch(engine, "B25", ["--mode", "train", "--training-mode", "per_sector"], None)
    assert detect_batch_training_mode(engine, "B25") == "per_sector"


@pytest.mark.unit
def test_detect_per_sector_from_command_line() -> None:
    engine = _engine()
    _insert_batch(engine, "B25", None, "python -m modelFactory --training-mode per_sector --comment x")
    assert detect_batch_training_mode(engine, "B25") == "per_sector"


@pytest.mark.unit
def test_detect_per_symbol_from_argv() -> None:
    engine = _engine()
    _insert_batch(engine, "B4", ["--training-mode", "per_symbol"], None)
    assert detect_batch_training_mode(engine, "B4") == "per_symbol"


@pytest.mark.unit
def test_detect_per_sector_from_sentinel_run() -> None:
    engine = _engine()
    _insert_run(engine, "B25_globalrank_synth", "B25", "__GLOBAL_RANK_SYNTH__")
    _insert_run(engine, "B25_industrials", "B25", "Industrials")
    assert detect_batch_training_mode(engine, "B25") == "per_sector"


@pytest.mark.unit
def test_detect_per_sector_from_gics_sector_names() -> None:
    engine = _engine()
    for symbol in ("Energy", "Financials", "Utilities", "Industrials"):
        _insert_run(engine, f"B25_{symbol.lower()}", "B25", symbol)
    assert detect_batch_training_mode(engine, "B25") == "per_sector"


@pytest.mark.unit
def test_detect_defaults_to_per_symbol_when_unknown() -> None:
    engine = _engine()
    assert detect_batch_training_mode(engine, "unknown-batch") == "per_symbol"


@pytest.mark.unit
def test_detect_none_batch_id_returns_per_symbol() -> None:
    engine = _engine()
    assert detect_batch_training_mode(engine, None) == "per_symbol"
