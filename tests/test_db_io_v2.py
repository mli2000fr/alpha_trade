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
                selection_rank INT,
                earnings_blackout INT,
                selector_signal_mode VARCHAR(32),
                selection_explanation VARCHAR(255),
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
                predicted_side VARCHAR(10),
                proba_long DOUBLE,
                proba_flat DOUBLE,
                proba_short DOUBLE,
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
                "low" DOUBLE,
                volume DOUBLE
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
                selection_rank INT, decision_rank INT,
                selector_signal_mode VARCHAR(32), selection_explanation VARCHAR(255), selector_earnings_blackout INT,
                decision VARCHAR(20), reason VARCHAR(255), score_used DOUBLE,
                score_source VARCHAR(40), score_snapshot_date DATE,
                entry_price DOUBLE, atr_20 DOUBLE, price_asof_date DATE, proposed_shares INT,
                approved_shares INT, target_notional DOUBLE, target_weight DOUBLE, sector VARCHAR(60),
                conviction_score DOUBLE, predicted_proba DOUBLE, historical_win_rate DOUBLE,
                prediction_asof_date DATE, ml_metrics_asof_date DATE,
                effective_probability DOUBLE, kelly_fraction DOUBLE, sizing_method VARCHAR(100),
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
                selection_rank INT, decision_rank INT,
                selector_signal_mode VARCHAR(32), selection_explanation VARCHAR(255), selector_earnings_blackout INT,
                side VARCHAR(10),
                shares INT, entry_price DOUBLE, atr_20 DOUBLE, price_asof_date DATE,
                stop_price_initial DOUBLE, risk_per_share DOUBLE, risk_budget_dollars DOUBLE,
                initial_risk_dollars DOUBLE, target_notional DOUBLE, target_weight DOUBLE,
                sector VARCHAR(60), score_used DOUBLE, score_source VARCHAR(40),
                conviction_score DOUBLE, sizing_method VARCHAR(100), kelly_fraction DOUBLE, atr_asof_date DATE,
                company_idio_score DOUBLE, macro_regime_score DOUBLE,
                company_idio_signal_norm DOUBLE, macro_regime_signal_norm DOUBLE,
                company_idio_component DOUBLE, macro_regime_component DOUBLE, quant_component DOUBLE,
                walk_forward_sentiment_weight DOUBLE, walk_forward_macro_weight DOUBLE,
                walk_forward_quant_weight DOUBLE, calibration_run_id VARCHAR(64), calibration_source VARCHAR(64)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weights_calibration_runs (
                run_id VARCHAR(40) PRIMARY KEY,
                calibrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scope VARCHAR(16),
                calibration_batch_id VARCHAR(40),
                market_regime_mode VARCHAR(32) DEFAULT 'all',
                segment_key VARCHAR(160),
                horizon_days INT DEFAULT 5,
                lookback_months INT DEFAULT 12,
                window_start DATE,
                window_end DATE,
                metric_name VARCHAR(32),
                metric_value DOUBLE,
                best_weights JSON,
                candidates JSON,
                distinct_snapshot_days INT,
                distinct_symbols INT,
                eligible_for_live INT DEFAULT 0,
                eligibility_reason VARCHAR(255),
                observations_evaluated INT,
                scenarios_evaluated INT,
                latest_best_scenario_name VARCHAR(255),
                final_value DOUBLE,
                total_return_pct DOUBLE,
                sharpe_ratio DOUBLE,
                max_drawdown_pct DOUBLE,
                artifact_dir VARCHAR(512),
                git_sha VARCHAR(40),
                schema_version INT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weights_calibration_segment_drifts (
                run_id VARCHAR(40) PRIMARY KEY,
                compared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                comparison_kind VARCHAR(48),
                calibration_batch_id VARCHAR(40),
                source_run_id VARCHAR(40),
                target_run_id VARCHAR(40),
                source_segment_key VARCHAR(160),
                target_segment_key VARCHAR(160),
                metric_name VARCHAR(32),
                metric_delta DOUBLE,
                final_value_drift_pct DOUBLE,
                payload JSON,
                schema_version INT
            )
        """))


@pytest.mark.unit
def test_load_predictions_returns_latest() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
                 INSERT INTO model_predictions (
                  symbol, predicted_proba, predicted_class, predicted_side,
                  proba_long, proba_flat, proba_short, run_id, prediction_date
                 )
                 VALUES ('AAPL', 0.72, 1, 'long', 0.72, 0.18, 0.10, 'run1', '2026-04-15'),
                     ('AAPL', 0.65, 1, 'long', 0.65, 0.20, 0.15, 'run0', '2026-04-10'),
                     ('AAPL', 0.91, 1, 'long', 0.91, 0.05, 0.04, 'future-run', '2024-01-31')
        """))
    repo = RiskRepository(engine=engine)
    preds = repo.load_predictions_asof(["AAPL"], date(2026, 4, 18))
    assert "AAPL" in preds
    assert preds["AAPL"].predicted_proba == 0.72
    assert preds["AAPL"].predicted_side == "long"
    assert preds["AAPL"].proba_short == 0.10
    assert preds["AAPL"].prediction_date == date(2026, 4, 15)


@pytest.mark.unit
def test_load_predictions_empty_symbols() -> None:
    engine = create_engine("sqlite:///:memory:")
    repo = RiskRepository(engine=engine)
    assert repo.load_predictions_asof([], date(2026, 4, 18)) == {}


@pytest.mark.unit
def test_load_selection_inputs_asof_uses_history_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector, final_score_sentiment, final_score_walk_forward, selection_rank,
                walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                calibration_run_id, calibration_source
            )
            VALUES
                ('2026-04-18', 'AAPL', 'Tech', 0.81, 0.92, 1, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-19', 'AAPL', 'Tech', 0.10, 0.11, 1, 0.2, 0.1, 0.7, 'wf-002', 'walk_forward')
        """))
    repo = RiskRepository(engine=engine)
    candidates = repo.load_selection_inputs_asof(date(2026, 4, 18))
    assert len(candidates) == 1
    assert candidates[0].score_used == 0.92


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_returns_latest_applicable_run() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-old', 'risk', 'all', 5, 12, 1, '2025-01-01', '2025-12-31', 'sharpe', 1.10,
                 '{"score_weight": 0.4, "prediction_weight": 0.6, "kelly_fraction_multiplier": 0.25}', '[]', 1),
                ('risk-new', 'risk', 'all', 5, 12, 1, '2025-04-01', '2026-03-31', 'sharpe', 1.35,
                 '{"score_weight": 0.3, "prediction_weight": 0.7, "kelly_fraction_multiplier": 0.5}', '[]', 1)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(date(2026, 4, 1), horizon_days=5, lookback_months=12)

    assert calibration is not None
    assert calibration["run_id"] == "risk-new"
    assert calibration["metric_name"] == "sharpe"
    assert calibration["best_weights"]["score_weight"] == pytest.approx(0.3)
    assert calibration["best_weights"]["prediction_weight"] == pytest.approx(0.7)
    assert calibration["market_regime_mode"] == "all"
    assert calibration["fallback_level"] == "exact_segment"


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_prefers_requested_market_regime_mode() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-all', 'risk', 'all', 5, 12, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.20,
                 '{"score_weight": 0.4, "prediction_weight": 0.6}', '[]', 2),
                ('risk-cap-pres', 'risk', 'capital_preservation', 5, 12, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.35,
                 '{"score_weight": 0.2, "prediction_weight": 0.8}', '[]', 2)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["run_id"] == "risk-cap-pres"
    assert calibration["market_regime_mode"] == "capital_preservation"
    assert calibration["requested_market_regime_mode"] == "capital_preservation"
    assert calibration["market_regime_fallback_used"] is False
    assert calibration["fallback_level"] == "exact_segment"


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_falls_back_to_all_market_regime_mode() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-all', 'risk', 'all', 5, 12, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.20,
                 '{"score_weight": 0.4, "prediction_weight": 0.6}', '[]', 2)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="close_only",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["run_id"] == "risk-all"
    assert calibration["market_regime_mode"] == "all"
    assert calibration["requested_market_regime_mode"] == "close_only"
    assert calibration["market_regime_fallback_used"] is True
    assert calibration["fallback_level"] == "regime_all"


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_blocks_ineligible_segment_for_live() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                eligibility_reason, window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-blocked', 'risk', 'capital_preservation', 5, 12, 0,
                 'insufficient_snapshot_days', '2025-01-01', '2026-03-31', 'sharpe', 1.05,
                 '{"score_weight": 0.2, "prediction_weight": 0.8}', '[]', 2)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["status"] == "blocked_by_governance"
    assert calibration["eligible_for_live"] is False
    assert calibration["eligibility_reason"] == "insufficient_snapshot_days"
    assert calibration["fallback_level"] == "blocked_governance_exact_segment"


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_falls_back_to_same_regime_nearest_window() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-cap-6m', 'risk', 'capital_preservation', 5, 6, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.18,
                 '{"score_weight": 0.22, "prediction_weight": 0.78}', '[]', 2),
                ('risk-all-24m', 'risk', 'all', 5, 24, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.10,
                 '{"score_weight": 0.35, "prediction_weight": 0.65}', '[]', 2)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["run_id"] == "risk-cap-6m"
    assert calibration["market_regime_mode"] == "capital_preservation"
    assert calibration["lookback_months"] == 6
    assert calibration["requested_horizon_days"] == 5
    assert calibration["requested_lookback_months"] == 12
    assert calibration["requested_segment_key"] == "regime=capital_preservation|horizon=5d|window=12m"
    assert calibration["market_regime_fallback_used"] is True
    assert calibration["fallback_level"] == "same_regime_nearest_window"
    assert calibration["fallback_policy_source"] in {"config_yaml", "defaults", "defaults_invalid_config", "defaults_on_config_error"}
    assert isinstance(calibration["fallback_journal"], list)
    assert calibration["fallback_journal"][0]["level"] == "exact_segment"
    assert calibration["fallback_journal"][0]["outcome"] == "no_candidate"
    assert calibration["fallback_journal"][2]["level"] == "same_regime_nearest_window"
    assert calibration["fallback_journal"][2]["selected"] is True
    assert "niveau=same_regime_nearest_window" in str(calibration["fallback_reason"])


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_prefers_eligible_broader_fallback_over_blocked_exact_segment() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                eligibility_reason, window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-cap-blocked', 'risk', 'capital_preservation', 5, 12, 0,
                 'insufficient_snapshot_days', '2025-01-01', '2026-03-31', 'sharpe', 1.05,
                 '{"score_weight": 0.2, "prediction_weight": 0.8}', '[]', 2),
                ('risk-cap-6m', 'risk', 'capital_preservation', 5, 6, 1,
                 NULL, '2025-01-01', '2026-03-31', 'sharpe', 1.15,
                 '{"score_weight": 0.3, "prediction_weight": 0.7}', '[]', 2)
        """))
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["run_id"] == "risk-cap-6m"
    assert calibration["status"] == "selected"
    assert calibration["eligible_for_live"] is True
    assert calibration["fallback_level"] == "same_regime_nearest_window"
    assert calibration["fallback_journal"][0]["outcome"] == "blocked_candidate_available"


@pytest.mark.unit
def test_load_latest_empirical_risk_calibration_honors_yaml_fallback_policy_order(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO weights_calibration_runs (
                run_id, scope, market_regime_mode, horizon_days, lookback_months, eligible_for_live,
                window_start, window_end, metric_name, metric_value, best_weights, candidates, schema_version
            ) VALUES
                ('risk-cap-6m', 'risk', 'capital_preservation', 5, 6, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.18,
                 '{"score_weight": 0.22, "prediction_weight": 0.78}', '[]', 2),
                ('risk-all-24m', 'risk', 'all', 5, 24, 1, '2025-01-01', '2026-03-31', 'sharpe', 1.10,
                 '{"score_weight": 0.35, "prediction_weight": 0.65}', '[]', 2)
        """))
    monkeypatch.setattr(
        "risk_management.db_io.load_config",
        lambda: {
            "risk_management": {
                "empirical_calibration": {
                    "fallback_levels": [
                        "exact_segment",
                        "regime_all",
                        "regime_all_nearest_window",
                        "same_regime_nearest_window",
                    ]
                }
            }
        },
    )
    repo = RiskRepository(engine=engine)

    calibration = repo.load_latest_empirical_risk_calibration(
        date(2026, 4, 1),
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
    )

    assert calibration is not None
    assert calibration["run_id"] == "risk-all-24m"
    assert calibration["fallback_level"] == "regime_all_nearest_window"
    assert calibration["fallback_policy_source"] == "config_yaml"


@pytest.mark.unit
def test_load_selection_inputs_asof_propagates_score_metadata() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector, final_score_sentiment, final_score_walk_forward, selection_rank,
                earnings_blackout, selector_signal_mode, selection_explanation
            )
            VALUES
                ('2026-04-18', 'AAPL', 'Tech', 0.81, 0.92, 7, 1, 'sector_neutralized', 'mode=sector_neutralized; rank=7')
        """))
    repo = RiskRepository(engine=engine)

    candidates = repo.load_selection_inputs_asof(date(2026, 4, 18))

    assert len(candidates) == 1
    assert candidates[0].selection_rank == 7
    assert candidates[0].selector_signal_mode == "sector_neutralized"
    assert candidates[0].selection_explanation == "mode=sector_neutralized; rank=7"
    assert candidates[0].selector_earnings_blackout == 1


@pytest.mark.unit
def test_load_selection_inputs_asof_falls_back_to_latest_snapshot_before_trade_date(caplog) -> None:
    """Si stock_scores_history n'a pas encore de ligne pour trade_date, on doit
    retomber sur le dernier snapshot_date <= trade_date contenant des candidats."""
    import logging

    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stock_scores_history (
                snapshot_date, symbol, sector, final_score_sentiment, final_score_walk_forward, selection_rank,
                walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                calibration_run_id, calibration_source
            )
            VALUES
                ('2026-04-30', 'AAPL', 'Tech', 0.81, 0.92, 1, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-30', 'MSFT', 'Tech', 0.55, 0.60, 2, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward'),
                ('2026-04-30', 'IBM',  'Tech', 0.10, 0.20, NULL, 0.2, 0.1, 0.7, 'wf-001', 'walk_forward')
        """))
    repo = RiskRepository(engine=engine)
    with caplog.at_level(logging.INFO, logger="risk_management.db_io"):
        candidates = repo.load_selection_inputs_asof(date(2026, 5, 1))

    assert [c.symbol for c in candidates] == ["AAPL", "MSFT", "IBM"]
    assert candidates[0].snapshot_date == date(2026, 4, 30)
    assert any("PIT as-of" in rec.message for rec in caplog.records)


@pytest.mark.unit
def test_load_selection_inputs_asof_returns_empty_when_no_history_at_all(caplog) -> None:
    import logging

    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    repo = RiskRepository(engine=engine)
    with caplog.at_level(logging.WARNING, logger="risk_management.db_io"):
        candidates = repo.load_selection_inputs_asof(date(2026, 5, 1))
    assert candidates == []
    assert any("aucun snapshot de scores exploitable" in rec.message for rec in caplog.records)


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
            VALUES ('AAPL', '2024-01-31', 999, 1000, 998)
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
            "selection_rank": 1,
            "selector_signal_mode": "strict",
            "selection_explanation": "mode=strict; rank=1",
            "selector_earnings_blackout": 0,
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
    assert row["selector_signal_mode"] == "strict"
    assert row["selection_explanation"] == "mode=strict; rank=1"
    assert row["selector_earnings_blackout"] == 0
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
            "selection_rank": 3,
            "selector_signal_mode": "sector_neutralized",
            "selection_explanation": "mode=sector_neutralized; rank=3",
            "selector_earnings_blackout": 0,
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
    assert row["selection_rank"] == 3
    assert row["selector_signal_mode"] == "sector_neutralized"
    assert row["selection_explanation"] == "mode=sector_neutralized; rank=3"
    assert row["selector_earnings_blackout"] == 0
    assert row["atr_20"] == 5.0
    assert row["decision_rank"] == 1
    assert row["stop_price_initial"] == 140.0


@pytest.mark.unit
def test_load_account_equity_breakdown_filters_future_dividends() -> None:
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_cash_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id VARCHAR(32),
                entry_type VARCHAR(30),
                amount DOUBLE,
                created_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            INSERT INTO broker_account_snapshots (
                account_id, snapshot_kind, cash, equity, buying_power, created_at
            ) VALUES
                ('paper', 'preflight', 1000, 1100, 1500, '2026-04-18 20:00:00')
        """))
        conn.execute(text("""
            INSERT INTO portfolio_cash_ledger (account_id, entry_type, amount, created_at)
            VALUES
                ('paper', 'dividend_credit', 10.0, '2026-04-18 10:00:00'),
                ('paper', 'dividend_credit', 20.0, '2026-04-19 10:00:00')
        """))
    repo = RiskRepository(engine=engine)

    breakdown = repo.load_account_equity_breakdown("paper", date(2026, 4, 18))

    assert breakdown["cash"] == 1000.0
    assert breakdown["dividends_ledger"] == 10.0
    assert breakdown["source"] == "broker_account_snapshots"


