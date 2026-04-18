"""Tests unitaires — db_io V2 (load_predictions, load_win_rates, load_return_matrix)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text

from risk_management.db_io import RiskRepository


def _create_tables(engine):  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_predictions (
                symbol VARCHAR(20),
                predicted_proba DOUBLE,
                predicted_class INT,
                run_id VARCHAR(50),
                prediction_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_training_run (
                run_id VARCHAR(50) PRIMARY KEY,
                status VARCHAR(20),
                finished_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                run_id VARCHAR(50),
                symbol VARCHAR(20),
                directional_accuracy DOUBLE,
                split_name VARCHAR(10)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_bars_daily (
                symbol VARCHAR(20),
                "date" DATE,
                "close" DOUBLE,
                "high" DOUBLE,
                "low" DOUBLE
            )
        """))


@pytest.mark.unit
def test_load_predictions_returns_latest() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO model_predictions (symbol, predicted_proba, predicted_class, run_id, prediction_date)
            VALUES ('AAPL', 0.72, 1, 'run1', '2026-04-15'),
                   ('AAPL', 0.65, 1, 'run0', '2026-04-10')
        """))
    repo = RiskRepository(engine=engine)
    preds = repo.load_predictions(["AAPL"], date(2026, 4, 18))
    assert "AAPL" in preds
    assert preds["AAPL"].predicted_proba == 0.72


@pytest.mark.unit
def test_load_predictions_empty_symbols() -> None:
    engine = create_engine("sqlite:///:memory:")
    repo = RiskRepository(engine=engine)
    assert repo.load_predictions([], date(2026, 4, 18)) == {}


@pytest.mark.unit
def test_load_win_rates() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO model_training_run (run_id, status, finished_at)
            VALUES ('run1', 'completed', '2026-04-15 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO model_metrics (run_id, symbol, directional_accuracy, split_name)
            VALUES ('run1', 'AAPL', 0.62, 'test')
        """))
    repo = RiskRepository(engine=engine)
    wr = repo.load_win_rates(["AAPL"])
    assert "AAPL" in wr
    assert wr["AAPL"].directional_accuracy == 0.62


@pytest.mark.unit
def test_load_return_matrix() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        for i in range(5):
            conn.execute(text(f"""
                INSERT INTO stock_bars_daily (symbol, "date", "close", "high", "low")
                VALUES ('AAPL', '2026-04-{10+i:02d}', {150 + i}, {155 + i}, {148 + i})
            """))
    repo = RiskRepository(engine=engine)
    mat = repo.load_return_matrix(["AAPL"], lookback_days=10)
    assert not mat.empty
    assert "AAPL" in mat.columns

