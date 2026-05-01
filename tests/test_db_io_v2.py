"""Tests unitaires — db_io Sprint 1 (lectures PIT + écritures canoniques)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text

from risk_management.db_io import RiskRepository


def _create_tables(engine):  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_scores_history (
                snapshot_date DATE,
                symbol VARCHAR(20),
                sector VARCHAR(50),
                final_score DOUBLE,
                final_score_sentiment DOUBLE,
                final_score_walk_forward DOUBLE,
                is_candidate INT,
                walk_forward_sentiment_weight DOUBLE,
                walk_forward_macro_weight DOUBLE,
                walk_forward_quant_weight DOUBLE,
                calibration_run_id VARCHAR(64),
                calibration_source VARCHAR(64)
            )
        """))
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
            CREATE TABLE IF NOT EXISTS account_risk_snapshots (
                account_id VARCHAR(32),
                trade_date DATE,
                cash DOUBLE,
                equity DOUBLE,
                buying_power DOUBLE,
                high_watermark DOUBLE,
                daily_realized_pnl DOUBLE,
                daily_unrealized_pnl DOUBLE,
                daily_total_pnl DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS broker_account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id VARCHAR(32),
                snapshot_kind VARCHAR(20),
                cash DOUBLE,
                equity DOUBLE,
                buying_power DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(32), account_id VARCHAR(32), trade_date DATE, symbol VARCHAR(20),
                candidate_rank INT, decision_rank INT,
                decision VARCHAR(20), reason VARCHAR(255), score_used DOUBLE,
                score_source VARCHAR(40), score_snapshot_date DATE,
                entry_price DOUBLE, atr_20 DOUBLE, price_asof_date DATE, proposed_shares INT,
                approved_shares INT, target_notional DOUBLE, target_weight DOUBLE, sector VARCHAR(60),
                conviction_score DOUBLE, predicted_proba DOUBLE, historical_win_rate DOUBLE,
                prediction_asof_date DATE, ml_metrics_asof_date DATE,
                effective_probability DOUBLE, kelly_fraction DOUBLE, sizing_method VARCHAR(20),
                correlation_blocker VARCHAR(20), correlation_value DOUBLE,
                stop_price_initial DOUBLE, risk_per_share DOUBLE, risk_budget_dollars DOUBLE,
                initial_risk_dollars DOUBLE, atr_asof_date DATE,
                company_idio_score DOUBLE, macro_regime_score DOUBLE,
                company_idio_signal_norm DOUBLE, macro_regime_signal_norm DOUBLE,
                company_idio_component DOUBLE, macro_regime_component DOUBLE, quant_component DOUBLE,
                walk_forward_sentiment_weight DOUBLE, walk_forward_macro_weight DOUBLE,
                walk_forward_quant_weight DOUBLE, calibration_run_id VARCHAR(64), calibration_source VARCHAR(64)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(32), account_id VARCHAR(32), trade_date DATE, symbol VARCHAR(20),
                decision_rank INT, side VARCHAR(10),
                shares INT, entry_price DOUBLE, atr_20 DOUBLE, price_asof_date DATE,
                stop_price_initial DOUBLE, risk_per_share DOUBLE, risk_budget_dollars DOUBLE,
                initial_risk_dollars DOUBLE, target_notional DOUBLE, target_weight DOUBLE,
                sector VARCHAR(60), score_used DOUBLE, score_source VARCHAR(40),
                conviction_score DOUBLE, sizing_method VARCHAR(20), kelly_fraction DOUBLE, atr_asof_date DATE,
                company_idio_score DOUBLE, macro_regime_score DOUBLE,
                company_idio_signal_norm DOUBLE, macro_regime_signal_norm DOUBLE,
                company_idio_component DOUBLE, macro_regime_component DOUBLE, quant_component DOUBLE,
                walk_forward_sentiment_weight DOUBLE, walk_forward_macro_weight DOUBLE,
                walk_forward_quant_weight DOUBLE, calibration_run_id VARCHAR(64), calibration_source VARCHAR(64)
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
                   ('AAPL', 0.65, 1, 'run0', '2026-04-10'),
                   ('AAPL', 0.91, 1, 'future-run', '2026-04-20')
        """))
    repo = RiskRepository(engine=engine)
    preds = repo.load_predictions_asof(["AAPL"], date(2026, 4, 18))
    assert "AAPL" in preds
    assert preds["AAPL"].predicted_proba == 0.72
    assert preds["AAPL"].prediction_date == date(2026, 4, 15)


@pytest.mark.unit
def test_load_predictions_empty_symbols() -> None:
    engine = create_engine("sqlite:///:memory:")
    repo = RiskRepository(engine=engine)
    assert repo.load_predictions_asof([], date(2026, 4, 18)) == {}


@pytest.mark.unit
def test_load_candidates_asof_uses_history_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector, final_score_sentiment, final_score_walk_forward, is_candidate,
                walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                calibration_run_id, calibration_source
            )
            VALUES
                ('2026-04-18', 'AAPL', 'Tech', 0.81, 0.92, 1, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-19', 'AAPL', 'Tech', 0.10, 0.11, 1, 0.2, 0.1, 0.7, 'wf-002', 'walk_forward')
        """))
    repo = RiskRepository(engine=engine)
    candidates = repo.load_candidates_asof(date(2026, 4, 18))
    assert len(candidates) == 1
    assert candidates[0].score_used == 0.92
    assert candidates[0].snapshot_date == date(2026, 4, 18)


@pytest.mark.unit
def test_load_candidates_asof_falls_back_to_latest_snapshot_before_trade_date(caplog) -> None:
    """Si stock_scores_history n'a pas encore de ligne pour trade_date, on doit
    retomber sur le dernier snapshot_date <= trade_date contenant des candidats."""
    import logging

    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector, final_score_sentiment, final_score_walk_forward, is_candidate,
                walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                calibration_run_id, calibration_source
            )
            VALUES
                ('2026-04-30', 'AAPL', 'Tech', 0.81, 0.92, 1, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-30', 'MSFT', 'Tech', 0.55, 0.60, 1, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-30', 'IBM',  'Tech', 0.10, 0.20, 0, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward')
        """))
    repo = RiskRepository(engine=engine)
    with caplog.at_level(logging.WARNING, logger="risk_management.db_io"):
        candidates = repo.load_candidates_asof(date(2026, 5, 1))

    assert [c.symbol for c in candidates] == ["AAPL", "MSFT"]
    assert candidates[0].snapshot_date == date(2026, 4, 30)
    assert any("fallback PIT" in rec.message for rec in caplog.records)


@pytest.mark.unit
def test_load_candidates_asof_returns_empty_when_no_history_at_all(caplog) -> None:
    import logging

    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    repo = RiskRepository(engine=engine)
    with caplog.at_level(logging.WARNING, logger="risk_management.db_io"):
        candidates = repo.load_candidates_asof(date(2026, 5, 1))
    assert candidates == []
    assert any("aucun snapshot stock_scores_history" in rec.message for rec in caplog.records)


@pytest.mark.unit
def test_load_win_rates() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO model_training_run (run_id, status, finished_at)
            VALUES ('run1', 'completed', '2026-04-15 10:00:00'),
                   ('run2', 'completed', '2026-04-21 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO model_metrics (run_id, symbol, directional_accuracy, split_name)
            VALUES ('run1', 'AAPL', 0.62, 'test'),
                   ('run2', 'AAPL', 0.90, 'test')
        """))
    repo = RiskRepository(engine=engine)
    wr = repo.load_win_rates_asof(["AAPL"], date(2026, 4, 18))
    assert "AAPL" in wr
    assert wr["AAPL"].directional_accuracy == 0.62
    assert wr["AAPL"].asof_date == date(2026, 4, 15)


@pytest.mark.unit
def test_load_prices_asof_uses_price_and_atr_before_trade_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        for day, close_, high_, low_ in [
            (10, 100.0, 101.0, 99.0),
            (11, 102.0, 104.0, 101.0),
            (12, 103.0, 105.0, 102.0),
            (13, 104.0, 106.0, 103.0),
            (14, 110.0, 112.0, 109.0),
            (15, 130.0, 131.0, 129.0),
        ]:
            conn.execute(text(f"""
                INSERT INTO stock_bars_daily (symbol, "date", "close", "high", "low")
                VALUES ('AAPL', '2026-04-{day:02d}', {close_}, {high_}, {low_})
            """))
    repo = RiskRepository(engine=engine)
    prices = repo.load_prices_asof(["AAPL"], date(2026, 4, 14), atr_window=3)
    assert prices["AAPL"].last_close == 110.0
    assert prices["AAPL"].price_asof_date == date(2026, 4, 14)
    assert prices["AAPL"].atr_20 is not None
    assert prices["AAPL"].atr_asof_date == date(2026, 4, 14)


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
        conn.execute(text("""
            INSERT INTO stock_bars_daily (symbol, "date", "close", "high", "low")
            VALUES ('AAPL', '2026-04-20', 999, 1000, 998)
        """))
    repo = RiskRepository(engine=engine)
    mat = repo.load_return_matrix_asof(["AAPL"], date(2026, 4, 14), lookback_days=10)
    assert not mat.empty
    assert "AAPL" in mat.columns


@pytest.mark.unit
def test_load_account_risk_snapshot_returns_latest_before_trade_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO account_risk_snapshots (
                account_id, trade_date, cash, equity, buying_power, high_watermark,
                daily_realized_pnl, daily_unrealized_pnl, daily_total_pnl
            ) VALUES
                ('paper', '2026-04-17', 100000, 101000, 100000, 105000, -100, -50, -150),
                ('paper', '2026-04-19', 90000, 91000, 90000, 105000, -200, -100, -300)
        """))
    repo = RiskRepository(engine=engine)
    snapshot = repo.load_account_risk_snapshot("paper", date(2026, 4, 18))
    assert snapshot is not None
    assert snapshot.trade_date == date(2026, 4, 17)
    assert snapshot.equity == 101000


@pytest.mark.unit
def test_load_account_risk_snapshot_falls_back_to_broker_account_snapshots() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO broker_account_snapshots (
                account_id, snapshot_kind, cash, equity, buying_power, created_at
            ) VALUES
                ('paper', 'preflight', 95000, 101000, 150000, '2026-04-17 20:00:00'),
                ('paper', 'preflight', 97000, 103500, 155000, '2026-04-18 20:00:00')
        """))
    repo = RiskRepository(engine=engine)

    snapshot = repo.load_account_risk_snapshot("paper", date(2026, 4, 18))

    assert snapshot is not None
    assert snapshot.account_id == "paper"
    assert snapshot.trade_date == date(2026, 4, 18)
    assert snapshot.cash == 97000
    assert snapshot.equity == 103500
    assert snapshot.buying_power == 155000
    assert snapshot.high_watermark == 103500
    assert snapshot.daily_total_pnl is None


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
            "atr_20": 5.0,
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
            "candidate_rank": 1,
            "decision_rank": 1,
            "target_notional": 6000.0,
            "stop_price_initial": 140.0,
            "risk_per_share": 10.0,
            "risk_budget_dollars": 1000.0,
            "initial_risk_dollars": 400.0,
            "score_snapshot_date": date(2026, 4, 18),
            "price_asof_date": date(2026, 4, 18),
            "atr_asof_date": date(2026, 4, 18),
            "prediction_asof_date": date(2026, 4, 15),
            "ml_metrics_asof_date": date(2026, 4, 15),
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
    assert row["atr_20"] == 5.0
    assert row["risk_per_share"] == 10.0
    assert row["score_snapshot_date"] == "2026-04-18"


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
            "atr_20": 5.0,
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
            "decision_rank": 1,
            "target_notional": 6000.0,
            "stop_price_initial": 140.0,
            "risk_per_share": 10.0,
            "risk_budget_dollars": 1000.0,
            "initial_risk_dollars": 400.0,
            "price_asof_date": date(2026, 4, 18),
            "atr_asof_date": date(2026, 4, 18),
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
    assert row["atr_20"] == 5.0
    assert row["decision_rank"] == 1
    assert row["stop_price_initial"] == 140.0

