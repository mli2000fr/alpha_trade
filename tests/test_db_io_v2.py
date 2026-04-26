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
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(32), trade_date DATE, symbol VARCHAR(20),
                decision VARCHAR(20), reason VARCHAR(255), score_used DOUBLE,
                score_source VARCHAR(40), entry_price DOUBLE, proposed_shares INT,
                approved_shares INT, target_weight DOUBLE, sector VARCHAR(60),
                conviction_score DOUBLE, predicted_proba DOUBLE, historical_win_rate DOUBLE,
                effective_probability DOUBLE, kelly_fraction DOUBLE, sizing_method VARCHAR(20),
                correlation_blocker VARCHAR(20), correlation_value DOUBLE,
                company_idio_score DOUBLE, macro_regime_score DOUBLE,
                company_idio_signal_norm DOUBLE, macro_regime_signal_norm DOUBLE,
                company_idio_component DOUBLE, macro_regime_component DOUBLE, quant_component DOUBLE,
                walk_forward_sentiment_weight DOUBLE, walk_forward_macro_weight DOUBLE, walk_forward_quant_weight DOUBLE,
                calibration_run_id VARCHAR(64), calibration_source VARCHAR(64), account_id VARCHAR(32)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(32), trade_date DATE, symbol VARCHAR(20),
                shares INT, entry_price DOUBLE, target_weight DOUBLE,
                sector VARCHAR(60), score_used DOUBLE, score_source VARCHAR(40),
                conviction_score DOUBLE, sizing_method VARCHAR(20), kelly_fraction DOUBLE,
                company_idio_score DOUBLE, macro_regime_score DOUBLE,
                company_idio_signal_norm DOUBLE, macro_regime_signal_norm DOUBLE,
                company_idio_component DOUBLE, macro_regime_component DOUBLE, quant_component DOUBLE,
                walk_forward_sentiment_weight DOUBLE, walk_forward_macro_weight DOUBLE, walk_forward_quant_weight DOUBLE,
                calibration_run_id VARCHAR(64), calibration_source VARCHAR(64), account_id VARCHAR(32)
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


@pytest.mark.unit
def test_write_risk_decisions_persists_walk_forward_metadata() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    repo = RiskRepository(engine=engine)

    written = repo.write_risk_decisions([
        {
            "run_id": "risk-run-1",
            "trade_date": date(2026, 4, 18),
            "symbol": "AAPL",
            "decision": "ACCEPTED",
            "reason": "OK",
            "score_used": 0.91,
            "score_source": "final_score_walk_forward",
            "entry_price": 150.0,
            "proposed_shares": 50,
            "approved_shares": 40,
            "target_weight": 0.06,
            "sector": "Tech",
            "conviction_score": 0.87,
            "predicted_proba": 0.72,
            "historical_win_rate": 0.61,
            "effective_probability": 0.67,
            "kelly_fraction": 0.08,
            "sizing_method": "kelly_atr",
            "correlation_blocker": None,
            "correlation_value": None,
            "company_idio_score": 0.8,
            "macro_regime_score": 0.2,
            "company_idio_signal_norm": 0.9,
            "macro_regime_signal_norm": 0.6,
            "company_idio_component": 0.18,
            "macro_regime_component": 0.06,
            "quant_component": 0.67,
            "walk_forward_sentiment_weight": 0.2,
            "walk_forward_macro_weight": 0.1,
            "walk_forward_quant_weight": 0.7,
            "calibration_run_id": "wf-001",
            "calibration_source": "walk_forward",
        }
    ], account_id="paper")

    assert written == 1
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM risk_decisions")).mappings().one()
    assert row["score_source"] == "final_score_walk_forward"
    assert row["walk_forward_sentiment_weight"] == 0.2
    assert row["walk_forward_macro_weight"] == 0.1
    assert row["walk_forward_quant_weight"] == 0.7
    assert row["calibration_run_id"] == "wf-001"
    assert row["account_id"] == "paper"


@pytest.mark.unit
def test_write_portfolio_targets_persists_walk_forward_metadata() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    repo = RiskRepository(engine=engine)

    written = repo.write_portfolio_targets([
        {
            "run_id": "risk-run-1",
            "trade_date": date(2026, 4, 18),
            "symbol": "AAPL",
            "shares": 40,
            "entry_price": 150.0,
            "target_weight": 0.06,
            "sector": "Tech",
            "score_used": 0.91,
            "score_source": "final_score_walk_forward",
            "conviction_score": 0.87,
            "sizing_method": "kelly_atr",
            "kelly_fraction": 0.08,
            "company_idio_score": 0.8,
            "macro_regime_score": 0.2,
            "company_idio_signal_norm": 0.9,
            "macro_regime_signal_norm": 0.6,
            "company_idio_component": 0.18,
            "macro_regime_component": 0.06,
            "quant_component": 0.67,
            "walk_forward_sentiment_weight": 0.2,
            "walk_forward_macro_weight": 0.1,
            "walk_forward_quant_weight": 0.7,
            "calibration_run_id": "wf-001",
            "calibration_source": "walk_forward",
        }
    ], account_id="paper")

    assert written == 1
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM portfolio_targets")).mappings().one()
    assert row["score_source"] == "final_score_walk_forward"
    assert row["company_idio_component"] == 0.18
    assert row["macro_regime_component"] == 0.06
    assert row["quant_component"] == 0.67
    assert row["calibration_source"] == "walk_forward"
    assert row["account_id"] == "paper"


