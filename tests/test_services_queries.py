from ihm.services import queries


def test_get_alpha_scanner_dependency_diagnostic_flags_both_dependencies_red(monkeypatch):
    from datetime import date

    queries.get_alpha_scanner_dependency_diagnostic.clear()

    def fake_safe_scalar(query, params=None):
        if "COUNT(DISTINCT sm.symbol)" in query:
            return 200
        if "FROM stock_quote_snapshots q" in query and "MAX(q.quote_date)" in query:
            return "2026-04-10"
        if "FROM stock_quote_snapshots q" in query and "COUNT(DISTINCT q.symbol)" in query:
            return 10
        if "FROM stock_earnings_calendar e" in query and "MAX(e.earnings_date)" in query:
            return None
        if "FROM stock_earnings_calendar e" in query and "COUNT(DISTINCT e.symbol)" in query:
            return 0
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_scalar", fake_safe_scalar)
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    diagnostic = queries.get_alpha_scanner_dependency_diagnostic(today=date(2026, 4, 25))
    dependencies = dict(diagnostic["dependencies"])

    assert diagnostic["eligible_symbols"] == 200
    assert diagnostic["all_red"] is True
    quotes = dict(dependencies["sync_latest_quotes"])
    earnings = dict(dependencies["sync_earnings_calendar"])
    assert quotes["status"] == "red"
    assert quotes["latest_date"] == "2026-04-10"
    assert quotes["covered_symbols"] == 10
    assert quotes["coverage_pct"] == 5.0
    assert earnings["status"] == "red"
    assert earnings["latest_date"] is None
    assert earnings["covered_symbols"] == 0


def test_get_alpha_scanner_dependency_diagnostic_exposes_exact_metrics(monkeypatch):
    from datetime import date

    queries.get_alpha_scanner_dependency_diagnostic.clear()

    def fake_safe_scalar(query, params=None):
        if "COUNT(DISTINCT sm.symbol)" in query:
            return 100
        if "FROM stock_quote_snapshots q" in query and "MAX(q.quote_date)" in query:
            return "2026-04-25"
        if "FROM stock_quote_snapshots q" in query and "COUNT(DISTINCT q.symbol)" in query:
            return 90
        if "FROM stock_earnings_calendar e" in query and "MAX(e.earnings_date)" in query:
            return "2026-05-05"
        if "FROM stock_earnings_calendar e" in query and "COUNT(DISTINCT e.symbol)" in query:
            return 6
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_scalar", fake_safe_scalar)
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    diagnostic = queries.get_alpha_scanner_dependency_diagnostic(today=date(2026, 4, 25))
    dependencies = dict(diagnostic["dependencies"])

    assert diagnostic["all_red"] is False
    assert diagnostic["any_red_or_orange"] is True
    quotes = dict(dependencies["sync_latest_quotes"])
    earnings = dict(dependencies["sync_earnings_calendar"])
    assert quotes["status"] == "green"
    assert quotes["latest_date"] == "2026-04-25"
    assert quotes["coverage_pct"] == 90.0
    assert earnings["status"] == "orange"
    assert earnings["latest_date"] == "2026-05-05"
    assert earnings["coverage_pct"] == 6.0
    assert earnings["covered_symbols"] == 6


def test_get_alpha_scanner_dependency_thresholds_can_be_overridden(monkeypatch):
    monkeypatch.setattr(
        queries,
        "load_persisted_alpha_scanner_dependency_thresholds",
        lambda defaults: {
            **defaults,
            "sync_latest_quotes": {
                **defaults["sync_latest_quotes"],
                "coverage_warn_pct": 70.0,
            },
        },
    )

    thresholds = queries.get_alpha_scanner_dependency_thresholds()

    assert thresholds["sync_latest_quotes"]["coverage_warn_pct"] == 70.0
    assert thresholds["sync_earnings_calendar"]["coverage_warn_pct"] == queries.ALPHA_SCANNER_DEPENDENCY_THRESHOLDS["sync_earnings_calendar"]["coverage_warn_pct"]

def test_services_queries_importable():
    assert hasattr(queries, "__doc__")


def test_get_weights_calibration_runs_builds_schema_aware_query(monkeypatch):
    import pandas as pd

    queries.get_weights_calibration_runs.clear()
    calls: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(
        queries,
        "_get_table_columns",
        lambda table_name: {
            "run_id",
            "calibrated_at",
            "scope",
            "market_regime_mode",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "eligible_for_live",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "best_weights",
            "candidates",
            "final_value",
            "schema_version",
        },
    )

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame([
            {
                "run_id": "wcr-001",
                "scope": "risk",
                "market_regime_mode": "capital_preservation",
                "metric_name": "sharpe",
                "metric_value": 1.42,
            }
        ])

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_weights_calibration_runs(
        scope="risk",
        market_regime_mode="capital_preservation",
        horizon_days=5,
        lookback_months=12,
        eligible_for_live=True,
        limit=25,
    )

    assert not df.empty
    assert calls
    query, params = calls[0]
    assert "market_regime_mode" in query
    assert "LOWER(COALESCE(scope, '')) = :scope" in query
    assert "LOWER(COALESCE(market_regime_mode, 'all')) = :market_regime_mode" in query
    assert "horizon_days = :horizon_days" in query
    assert "lookback_months = :lookback_months" in query
    assert "COALESCE(eligible_for_live, 0) = :eligible_for_live" in query
    assert "LIMIT 25" in query
    assert params == {
        "scope": "risk",
        "market_regime_mode": "capital_preservation",
        "horizon_days": 5,
        "lookback_months": 12,
        "eligible_for_live": 1,
    }


def test_get_weights_calibration_run_ids_returns_run_id_list(monkeypatch):
    import pandas as pd

    queries.get_weights_calibration_run_ids.clear()
    monkeypatch.setattr(
        queries,
        "get_weights_calibration_runs",
        lambda **kwargs: pd.DataFrame([{"run_id": "wcr-002"}, {"run_id": "wcr-001"}]),
    )

    run_ids = queries.get_weights_calibration_run_ids(scope="risk", market_regime_mode="all", limit=10)

    assert run_ids == ["wcr-002", "wcr-001"]


def test_get_weights_calibration_segment_drifts_builds_query(monkeypatch):
    import pandas as pd

    queries.get_weights_calibration_segment_drifts.clear()
    calls: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(
        queries,
        "_get_table_columns",
        lambda table_name: {
            "run_id",
            "compared_at",
            "comparison_kind",
            "calibration_batch_id",
            "source_run_id",
            "target_run_id",
            "source_segment_key",
            "target_segment_key",
            "metric_name",
            "metric_delta",
            "final_value_drift_pct",
            "payload",
            "schema_version",
        },
    )

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame([{"run_id": "wcsd-001", "comparison_kind": "vs_reference_live_segment"}])

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_weights_calibration_segment_drifts(
        calibration_batch_id="batch-001",
        source_run_id="wcr-001",
        comparison_kind="vs_reference_live_segment",
        limit=20,
    )

    assert not df.empty
    query, params = calls[0]
    assert "FROM weights_calibration_segment_drifts" in query
    assert "calibration_batch_id = :calibration_batch_id" in query
    assert "source_run_id = :source_run_id" in query
    assert "comparison_kind = :comparison_kind" in query
    assert params == {
        "calibration_batch_id": "batch-001",
        "source_run_id": "wcr-001",
        "comparison_kind": "vs_reference_live_segment",
    }


def test_get_stock_scores_builds_schema_aware_query_and_attaches_explainability_payload(monkeypatch):
    import pandas as pd

    queries.get_stock_scores.clear()
    calls: list[str] = []

    def fake_safe_query(query, params=None):
        calls.append(query)
        if query.startswith("SHOW COLUMNS FROM stock_scores"):
            return pd.DataFrame(
                {
                    "Field": [
                        "symbol",
                        "sector",
                        "is_candidate",
                        "candidate_rank",
                        "total_score",
                        "final_score",
                        "final_score_sentiment",
                        "trend_score",
                        "vcp_score",
                        "relative_strength_index",
                        "trend_vcp_component",
                        "total_score_component",
                        "rsi_component",
                        "selector_signal_mode",
                        "selection_explanation",
                    ]
                }
            )
        return pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "sector": "Technology",
                    "is_candidate": 1,
                    "candidate_rank": 1,
                    "total_score": 91.0,
                    "final_score": 0.88,
                    "final_score_sentiment": 0.55,
                    "trend_score": 0.82,
                    "vcp_score": 0.71,
                    "relative_strength_index": 67.0,
                    "trend_vcp_component": 0.41,
                    "total_score_component": 0.29,
                    "rsi_component": 0.18,
                    "selector_signal_mode": "sector_neutralized",
                    "selection_explanation": "mode=sector_neutralized; trend_vcp=0.4100; total=0.2900; rsi=0.1800; final=0.8800",
                }
            ]
        )

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_stock_scores()

    assert len(calls) == 2
    assert "candidate_rank" in calls[1]
    assert "selector_signal_mode" in calls[1]
    payload = df.iloc[0]["candidate_explainability_payload"]
    assert payload["identity"]["symbol"] == "AAPL"
    assert payload["identity"]["candidate_rank"] == 1
    assert payload["score_components"]["trend_vcp_component"] == 0.41
    assert payload["selection_context"]["selector_signal_mode"] == "sector_neutralized"


def test_get_stock_scores_avoids_selecting_missing_explainability_columns(monkeypatch):
    import pandas as pd

    queries.get_stock_scores.clear()
    calls: list[str] = []

    def fake_safe_query(query, params=None):
        calls.append(query)
        if query.startswith("SHOW COLUMNS FROM stock_scores"):
            return pd.DataFrame(
                {
                    "Field": [
                        "symbol",
                        "sector",
                        "is_candidate",
                        "total_score",
                        "final_score",
                        "final_score_sentiment",
                    ]
                }
            )
        return pd.DataFrame(
            [
                {
                    "symbol": "MSFT",
                    "sector": "Technology",
                    "is_candidate": 0,
                    "total_score": 88.0,
                    "final_score": 0.73,
                    "final_score_sentiment": 0.44,
                }
            ]
        )

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_stock_scores()

    assert "trend_vcp_component" not in calls[1]
    payload = df.iloc[0]["candidate_explainability_payload"]
    assert payload["identity"]["symbol"] == "MSFT"
    assert payload["score_components"]["trend_vcp_component"] is None


def test_get_backtesting_pit_history_diagnostic_reports_available_history(monkeypatch):
    queries.get_backtesting_pit_history_diagnostic.clear()

    def fake_safe_scalar(query, params=None):
        if "SHOW COLUMNS FROM stock_scores_history" in query:
            return "capital_preset_key"
        if "SELECT COUNT(*) FROM stock_scores_history" in query:
            return 42
        if "COUNT(DISTINCT snapshot_date)" in query:
            return 7
        if "SELECT MIN(snapshot_date)" in query:
            return "2024-01-01"
        if "SELECT MAX(snapshot_date)" in query:
            return "2025-04-29"
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_scalar", fake_safe_scalar)
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    payload = queries.get_backtesting_pit_history_diagnostic(
        start="2024-01-01",
        end="2025-04-29",
        capital_preset_key="capital_50001_100000",
    )

    assert payload["status"] == "available"
    assert payload["capital_preset_filtered"] is True
    assert payload["rows"] == 42
    assert payload["snapshot_days"] == 7
    assert payload["first_snapshot_date"] == "2024-01-01"
    assert payload["last_snapshot_date"] == "2025-04-29"


def test_get_backtesting_pit_history_diagnostic_reports_missing_history(monkeypatch):
    queries.get_backtesting_pit_history_diagnostic.clear()

    def fake_safe_scalar(query, params=None):
        if "SHOW COLUMNS FROM stock_scores_history" in query:
            return "capital_preset_key"
        if "SELECT COUNT(*) FROM stock_scores_history" in query:
            return 0
        if "COUNT(DISTINCT snapshot_date)" in query:
            return 0
        if "SELECT MIN(snapshot_date)" in query:
            return None
        if "SELECT MAX(snapshot_date)" in query:
            return None
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_scalar", fake_safe_scalar)
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    payload = queries.get_backtesting_pit_history_diagnostic(
        start="2024-01-01",
        end="2024-01-31",
        capital_preset_key="capital_50001_100000",
    )

    assert payload["status"] == "missing"
    assert payload["rows"] == 0
    assert payload["snapshot_days"] == 0
    assert payload["capital_preset_key"] == "capital_50001_100000"


def test_get_backtesting_ml_coverage_diagnostic_reports_partial_coverage(monkeypatch):
    import pandas as pd

    queries.get_backtesting_ml_coverage_diagnostic.clear()
    safe_query_calls: list[tuple[str, dict[str, object] | None]] = []

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: ("capital_preset_key", None),
    )

    error_states = iter([None, None, None])

    def fake_get_last_query_error():
        return next(error_states)

    def fake_safe_query(query, params=None):
        safe_query_calls.append((query, params))
        if "expected_candidate_symbol_dates" in query:
            return pd.DataFrame(
                [
                    {
                        "expected_candidate_symbol_dates": 4,
                        "expected_snapshot_days": 2,
                        "expected_symbols": 3,
                        "covered_prediction_symbol_dates": 2,
                        "covered_snapshot_days": 1,
                        "covered_symbols": 2,
                        "missing_prediction_symbol_dates": 2,
                        "missing_snapshot_days": 1,
                        "missing_symbols": 1,
                        "first_snapshot_date": "2024-01-02",
                        "last_snapshot_date": "2024-01-03",
                    }
                ]
            )
        if "ORDER BY expected.snapshot_date ASC, expected.symbol ASC" in query:
            return pd.DataFrame(
                [
                    {"trade_date": "2024-01-03", "symbol": " aapl "},
                    {"trade_date": "2024-01-03", "symbol": "msft"},
                ]
            )
        if "GROUP BY expected.snapshot_date" in query:
            return pd.DataFrame([{"trade_date": "2024-01-03", "missing_count": "2"}])
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)
    monkeypatch.setattr(queries, "get_last_query_error", fake_get_last_query_error)

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-02",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
        engine_mode="pipeline",
        ml_mode="auto",
        ml_pit_strategy="auto",
        missing_sample_limit=2,
        missing_days_limit=1,
    )

    assert payload["status"] == "partial"
    assert payload["capital_preset_filtered"] is True
    assert payload["effective_strategy"] == "use-persisted"
    assert payload["persist_enabled"] is False
    assert payload["expected_candidate_symbol_dates"] == 4
    assert payload["covered_prediction_symbol_dates"] == 2
    assert payload["missing_prediction_symbol_dates"] == 2
    assert payload["coverage_pct"] == 50.0
    assert payload["missing_rows_sample"] == [
        {"trade_date": "2024-01-03", "symbol": "AAPL"},
        {"trade_date": "2024-01-03", "symbol": "MSFT"},
    ]
    assert payload["missing_days_sample"] == [{"trade_date": "2024-01-03", "missing_count": 2}]
    assert "2/4" in str(payload["fast_mode_estimate"]["summary"])
    assert "2 prédiction(s)" in str(payload["rebuild_missing_estimate"]["summary"])
    assert safe_query_calls[1][1] is not None
    assert safe_query_calls[1][1]["missing_sample_limit"] == 2
    assert safe_query_calls[2][1] is not None
    assert safe_query_calls[2][1]["missing_days_limit"] == 1


def test_get_backtesting_ml_coverage_diagnostic_reports_complete_coverage(monkeypatch):
    import pandas as pd

    queries.get_backtesting_ml_coverage_diagnostic.clear()

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: (None, None),
    )
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    def fake_safe_query(query, params=None):
        if "expected_candidate_symbol_dates" in query:
            return pd.DataFrame(
                [
                    {
                        "expected_candidate_symbol_dates": 3,
                        "expected_snapshot_days": 2,
                        "expected_symbols": 2,
                        "covered_prediction_symbol_dates": 3,
                        "covered_snapshot_days": 2,
                        "covered_symbols": 2,
                        "missing_prediction_symbol_dates": 0,
                        "missing_snapshot_days": 0,
                        "missing_symbols": 0,
                        "first_snapshot_date": "2024-01-02",
                        "last_snapshot_date": "2024-01-03",
                    }
                ]
            )
        if "ORDER BY expected.snapshot_date ASC, expected.symbol ASC" in query:
            return pd.DataFrame(columns=["trade_date", "symbol"])
        if "GROUP BY expected.snapshot_date" in query:
            return pd.DataFrame(columns=["trade_date", "missing_count"])
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-02",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
        engine_mode="research",
        ml_mode="auto",
        ml_pit_strategy="auto",
    )

    assert payload["status"] == "complete"
    assert payload["capital_preset_filtered"] is False
    assert payload["coverage_pct"] == 100.0
    assert payload["persist_enabled"] is True
    assert payload["missing_rows_sample"] == []
    assert payload["missing_days_sample"] == []
    assert payload["fast_mode_estimate"]["missing_prediction_symbol_dates"] == 0
    assert payload["rebuild_missing_estimate"]["pairs_to_attempt"] == 0


def test_get_backtesting_ml_coverage_diagnostic_reports_missing_expected_history(monkeypatch):
    import pandas as pd

    queries.get_backtesting_ml_coverage_diagnostic.clear()

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: ("capital_preset_key", None),
    )
    monkeypatch.setattr(queries, "get_last_query_error", lambda: None)

    def fake_safe_query(query, params=None):
        if "expected_candidate_symbol_dates" in query:
            return pd.DataFrame(
                [
                    {
                        "expected_candidate_symbol_dates": 0,
                        "expected_snapshot_days": 0,
                        "expected_symbols": 0,
                        "covered_prediction_symbol_dates": 0,
                        "covered_snapshot_days": 0,
                        "covered_symbols": 0,
                        "missing_prediction_symbol_dates": 0,
                        "missing_snapshot_days": 0,
                        "missing_symbols": 0,
                        "first_snapshot_date": None,
                        "last_snapshot_date": None,
                    }
                ]
            )
        if "ORDER BY expected.snapshot_date ASC, expected.symbol ASC" in query:
            return pd.DataFrame(columns=["trade_date", "symbol"])
        if "GROUP BY expected.snapshot_date" in query:
            return pd.DataFrame(columns=["trade_date", "missing_count"])
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-02",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
    )

    assert payload["status"] == "missing_expected_history"
    assert payload["reason"].startswith("Aucun candidat PIT attendu")
    assert payload["coverage_pct"] == 0.0


def test_get_backtesting_ml_coverage_diagnostic_returns_disabled_without_query(monkeypatch):
    queries.get_backtesting_ml_coverage_diagnostic.clear()

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: (_ for _ in ()).throw(AssertionError("unexpected scalar query")),
    )
    monkeypatch.setattr(
        queries,
        "safe_query",
        lambda query, params=None: (_ for _ in ()).throw(AssertionError("unexpected SQL query")),
    )

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-02",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
        ml_mode="off",
    )

    assert payload["status"] == "disabled"
    assert payload["effective_strategy"] == "disabled"
    assert "ML désactivé" in str(payload["reason"])


def test_get_backtesting_ml_coverage_diagnostic_rejects_invalid_dates(monkeypatch):
    queries.get_backtesting_ml_coverage_diagnostic.clear()

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: (_ for _ in ()).throw(AssertionError("unexpected scalar query")),
    )
    monkeypatch.setattr(
        queries,
        "safe_query",
        lambda query, params=None: (_ for _ in ()).throw(AssertionError("unexpected SQL query")),
    )

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-10",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
    )

    assert payload["status"] == "invalid_input"
    assert payload["expected_candidate_symbol_dates"] == 0
    assert payload["missing_rows_sample"] == []


def test_get_backtesting_ml_coverage_diagnostic_reports_unavailable_when_missing_rows_query_fails(monkeypatch):
    import pandas as pd

    queries.get_backtesting_ml_coverage_diagnostic.clear()
    calls: list[str] = []

    monkeypatch.setattr(
        queries,
        "_safe_scalar_with_error",
        lambda query, params=None: ("capital_preset_key", None),
    )

    error_states = iter([None, "synthetic query failure"])

    def fake_get_last_query_error():
        return next(error_states)

    def fake_safe_query(query, params=None):
        calls.append(query)
        if "expected_candidate_symbol_dates" in query:
            return pd.DataFrame(
                [
                    {
                        "expected_candidate_symbol_dates": 4,
                        "expected_snapshot_days": 2,
                        "expected_symbols": 3,
                        "covered_prediction_symbol_dates": 2,
                        "covered_snapshot_days": 1,
                        "covered_symbols": 2,
                        "missing_prediction_symbol_dates": 2,
                        "missing_snapshot_days": 1,
                        "missing_symbols": 1,
                        "first_snapshot_date": "2024-01-02",
                        "last_snapshot_date": "2024-01-03",
                    }
                ]
            )
        if "ORDER BY expected.snapshot_date ASC, expected.symbol ASC" in query:
            return pd.DataFrame(columns=["trade_date", "symbol"])
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)
    monkeypatch.setattr(queries, "get_last_query_error", fake_get_last_query_error)

    payload = queries.get_backtesting_ml_coverage_diagnostic(
        start="2024-01-02",
        end="2024-01-03",
        capital_preset_key="capital_50001_100000",
    )

    assert payload["status"] == "unavailable"
    assert payload["reason"] == "synthetic query failure"
    assert payload["query_error"] == "synthetic query failure"
    assert len(calls) == 2


def test_get_predictions_can_filter_by_symbol(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_predictions(symbol="AAPL", limit=25)

    assert "WHERE symbol = :symbol" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}
    assert "selected_model" in captured["query"]


def test_get_predictions_can_filter_by_run_id_and_served_model(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_predictions(run_ids=["run-1"], served_models=["lightgbm"], limit=25)

    assert "run_id IN (:prediction_run_id_0)" in captured["query"]
    assert "selected_model IN (:served_model_0)" in captured["query"]
    assert captured["params"] == {"prediction_run_id_0": "run-1", "served_model_0": "lightgbm"}


def test_get_prediction_symbols_returns_list(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(queries, "safe_query", lambda query: pd.DataFrame({"symbol": ["AAPL", "MSFT"]}))

    result = queries.get_prediction_symbols()

    assert result == ["AAPL", "MSFT"]


def test_get_model_governance_can_filter_by_symbol(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_model_governance(symbol="AAPL", limit=10)

    assert "FROM model_governance" in captured["query"]
    assert "WHERE symbol = :symbol" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}


def test_get_model_governance_can_filter_by_run_id_and_selection_mode(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_model_governance(run_ids=["run-1"], selection_modes=["auto_selected_champion"], limit=10)

    assert "run_id IN (:run_id_0)" in captured["query"]
    assert "selection_mode IN (:selection_mode_0)" in captured["query"]
    assert captured["params"] == {"run_id_0": "run-1", "selection_mode_0": "auto_selected_champion"}


def test_get_prediction_governance_audit_can_filter_by_symbol(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_prediction_governance_audit(symbol="AAPL", limit=15)

    assert "FROM model_predictions p" in captured["query"]
    assert "LEFT JOIN model_governance served" in captured["query"]
    assert "LEFT JOIN model_governance champion" in captured["query"]
    assert "served.model_name = p.selected_model" in captured["query"]
    assert "champion.is_selected_model = 1" in captured["query"]
    assert "governance_served_artifact_symbol" in captured["query"]
    assert "governance_champion_artifact_symbol" in captured["query"]
    assert "WHERE symbol = :symbol" in captured["query"]
    assert "governance_link_status" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}


def test_get_prediction_governance_audit_can_filter_by_audit_dimensions(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_prediction_governance_audit(
        run_ids=["run-1"],
        selection_modes=["auto_selected_champion"],
        served_models=["lightgbm"],
        governance_link_statuses=["aligned"],
        limit=15,
    )

    assert "FROM (" in captured["query"]
    assert "run_id IN (:audit_run_id_0)" in captured["query"]
    assert "governance_selection_mode IN (:audit_selection_mode_0)" in captured["query"]
    assert "served_model IN (:audit_served_model_0)" in captured["query"]
    assert "governance_link_status IN (:audit_link_status_0)" in captured["query"]
    assert captured["params"] == {
        "audit_run_id_0": "run-1",
        "audit_selection_mode_0": "auto_selected_champion",
        "audit_served_model_0": "lightgbm",
        "audit_link_status_0": "aligned",
    }


def test_get_prediction_governance_audit_without_symbol_has_no_params(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_prediction_governance_audit(limit=5)

    assert "WHERE p.symbol = :symbol" not in captured["query"]
    assert captured["params"] is None


def test_get_run_business_summaries_builds_filters_and_caption(monkeypatch):
    import pandas as pd

    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return pd.DataFrame(
            {
                "summary_run_id": ["risk-1"],
                "source_run_id": ["risk-1"],
                "entity_run_id": ["risk-1"],
                "parent_summary_run_id": [None],
                "step_key": ["risk_management"],
                "run_kind": ["step"],
                "status": ["completed"],
                "account_id": ["acct-1"],
                "trade_date": ["2026-04-24"],
                "started_at": ["2026-04-24T10:00:00"],
                "finished_at": ["2026-04-24T10:00:05"],
                "summary_json": ['{"targeted_symbols": 5, "accepted_symbols": 3}'],
                "created_at": ["2026-04-24T10:00:05"],
                "updated_at": ["2026-04-24T10:00:05"],
            }
        )

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_run_business_summaries(step_keys=["risk_management"], entity_run_id="risk-1", account_id="acct-1", limit=10)

    assert "FROM run_business_summaries" in captured["query"]
    assert "entity_run_id = :entity_run_id" in captured["query"]
    assert "account_id = :account_id" in captured["query"]
    assert "step_key IN (:summary_step_key_0)" in captured["query"]
    assert captured["params"] == {"entity_run_id": "risk-1", "account_id": "acct-1", "summary_step_key_0": "risk_management"}
    assert df.iloc[0]["run_summary"] == {"targeted_symbols": 5, "accepted_symbols": 3}
    caption = str(df.iloc[0]["summary_caption"])
    assert "=5" in caption
    assert "=3" in caption


def test_get_latest_run_business_summary_returns_first_row(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        queries,
        "get_run_business_summaries",
        lambda **kwargs: pd.DataFrame(
            [{"summary_run_id": "exec-1", "step_key": "execution", "run_summary": {"submitted_orders": 4}, "summary_caption": "soumis=4"}]
        ),
    )

    row = queries.get_latest_run_business_summary(step_key="execution", entity_run_id="exec-1")

    assert row is not None
    assert row["summary_run_id"] == "exec-1"
    assert row["run_summary"] == {"submitted_orders": 4}


def test_get_latest_execution_protection_watch_service_summary_prefers_exec_run_scope(monkeypatch):
    queries.get_latest_execution_protection_watch_service_summary.clear()
    calls = []

    def fake_get_latest_run_business_summary(**kwargs):
        calls.append(kwargs)
        if kwargs.get("entity_run_id") == "exec-1":
            return {"summary_run_id": "svc-exec-1", "run_summary": {"iterations": 5}}
        return {"summary_run_id": "svc-account-1", "run_summary": {"iterations": 2}}

    monkeypatch.setattr(queries, "get_latest_run_business_summary", fake_get_latest_run_business_summary)

    row = queries.get_latest_execution_protection_watch_service_summary(account_id="acct-1", exec_run_id="exec-1")

    assert row is not None
    assert row["summary_run_id"] == "svc-exec-1"
    assert calls[0]["step_key"] == "execution_protection_watch_service"
    assert calls[0]["entity_run_id"] == "exec-1"
    assert calls[0]["run_kind"] == "service"


def test_get_latest_execution_protection_watch_service_summary_falls_back_to_account_scope(monkeypatch):
    queries.get_latest_execution_protection_watch_service_summary.clear()
    calls = []

    def fake_get_latest_run_business_summary(**kwargs):
        calls.append(kwargs)
        if kwargs.get("entity_run_id") == "exec-1":
            return None
        return {"summary_run_id": "svc-account-1", "run_summary": {"iterations": 7}}

    monkeypatch.setattr(queries, "get_latest_run_business_summary", fake_get_latest_run_business_summary)

    row = queries.get_latest_execution_protection_watch_service_summary(account_id="acct-1", exec_run_id="exec-1")

    assert row is not None
    assert row["summary_run_id"] == "svc-account-1"
    assert len(calls) == 2
    assert calls[1]["step_key"] == "execution_protection_watch_service"
    assert calls[1]["account_id"] == "acct-1"
    assert calls[1]["run_kind"] == "service"


def test_get_ops_service_summaries_filters_on_service_step(monkeypatch):
    import pandas as pd

    queries.get_ops_service_summaries.clear()
    captured = {}
    expected = pd.DataFrame({"summary_run_id": ["svc-1"]})

    def fake_get_run_business_summaries(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(queries, "get_run_business_summaries", fake_get_run_business_summaries)

    result = queries.get_ops_service_summaries(account_id="acct-1", limit=12)

    assert result is expected
    assert captured == {
        "limit": 12,
        "step_keys": ["execution_protection_watch_service"],
        "account_id": "acct-1",
        "run_kind": "service",
    }


def test_get_ops_latest_critical_summaries_filters_expected_step_keys(monkeypatch):
    import pandas as pd

    queries.get_ops_latest_critical_summaries.clear()
    captured = {}
    expected = pd.DataFrame({"summary_run_id": ["crit-1"]})

    def fake_get_run_business_summaries(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(queries, "get_run_business_summaries", fake_get_run_business_summaries)

    result = queries.get_ops_latest_critical_summaries(account_id="acct-1", limit=33)

    assert result is expected
    assert captured["limit"] == 33
    assert captured["account_id"] == "acct-1"
    assert captured["step_keys"] == [
        "pipeline_workflow",
        "risk_management",
        "execution",
        "execution_protection_watch",
        "corporate_actions_run",
    ]


def test_get_execution_orders_includes_stop_and_trailing_fields(monkeypatch):
    queries.get_execution_orders.clear()
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        import pandas as pd

        return pd.DataFrame({"intent_id": ["req-1"]})

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_orders(exec_run_id="exec-1")

    assert "FROM execution_order_requests req" in captured["query"]
    assert "LEFT JOIN execution_broker_orders bo" in captured["query"]
    assert "stop_price" in captured["query"]
    assert "trail_percent" in captured["query"]
    assert captured["params"] == {"eid": "exec-1"}


def test_get_execution_orders_does_not_query_legacy_tables(monkeypatch):
    import pandas as pd

    queries.get_execution_orders.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_orders(exec_run_id="exec-legacy")

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(calls) == 1
    assert "FROM execution_order_requests req" in calls[0][0]
    assert "execution_orders" not in calls[0][0]


def test_get_execution_fills_reads_v2_schema(monkeypatch):
    import pandas as pd

    queries.get_execution_fills.clear()
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return pd.DataFrame({"fill_id": ["fill-1"]})

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_fills(exec_run_id="exec-1")

    assert "FROM execution_broker_fills" in captured["query"]
    assert "request_id AS intent_id" in captured["query"]
    assert captured["params"] == {"eid": "exec-1"}


def test_get_execution_fills_does_not_query_legacy_tables(monkeypatch):
    import pandas as pd

    queries.get_execution_fills.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_fills(exec_run_id="exec-legacy")

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(calls) == 1
    assert "FROM execution_broker_fills" in calls[0][0]
    assert "execution_fills" not in calls[0][0]


def test_get_execution_orders_can_filter_by_account_id(monkeypatch):
    queries.get_execution_orders.clear()
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_orders(account_id="acct-1")

    assert "WHERE req.account_id = :account_id" in captured["query"]
    assert captured["params"] == {"account_id": "acct-1"}


def test_get_execution_account_constraints_falls_back_to_broker_snapshot(monkeypatch):
    import pandas as pd

    queries.get_execution_account_constraints.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        if "FROM execution_events" in query:
            return pd.DataFrame(columns=["message", "payload_json", "created_at"])
        if "FROM broker_account_snapshots" in query:
            return pd.DataFrame([
                {
                    "snapshot_kind": "preflight",
                    "equity": 100000.0,
                    "cash": 80000.0,
                    "settled_cash": 75000.0,
                    "buying_power": 75000.0,
                    "daytrade_count": 0,
                    "raw_payload_json": '{"account_type":"cash","effective_pdt_rule":"off","swing_only":true}',
                    "created_at": "2026-04-26T20:00:00",
                }
            ])
        raise AssertionError(query)

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    payload = queries.get_execution_account_constraints("exec-1")

    assert payload["account_type"] == "cash"
    assert payload["effective_pdt_rule"] == "off"
    assert payload["swing_only"] is True
    assert payload["buying_power_available"] == 75000.0
    assert payload["settled_cash_available"] == 75000.0
    assert "snapshot broker preflight" in str(payload["message"]).lower()
    assert len(calls) == 2


def test_get_broker_account_snapshots_history_scopes_account(monkeypatch):
    queries.get_broker_account_snapshots_history.clear()
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_broker_account_snapshots_history("acct-2", limit=25)

    assert "FROM broker_account_snapshots" in captured["query"]
    assert "WHERE account_id = :account_id" in captured["query"]
    assert "LIMIT 25" in captured["query"]
    assert captured["params"] == {"account_id": "acct-2"}


def test_get_execution_targets_snapshot_scopes_exec_run(monkeypatch):
    queries.get_execution_targets_snapshot.clear()
    captured = {}

    monkeypatch.setattr(
        queries,
        "_get_table_columns",
        lambda table_name: {
            "exec_run_id",
            "account_id",
            "risk_run_id",
            "trade_date",
            "symbol",
            "candidate_rank",
            "decision_rank",
            "selector_signal_mode",
            "selection_explanation",
            "selector_earnings_blackout",
            "side",
            "target_shares",
            "entry_price",
            "target_weight",
            "stop_price_initial",
            "risk_per_share",
            "risk_budget_dollars",
            "initial_risk_dollars",
            "target_notional",
            "price_asof_date",
            "atr_asof_date",
            "created_at",
        },
    )

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_targets_snapshot("exec-42")

    assert "FROM execution_targets_snapshot" in captured["query"]
    assert "candidate_rank" in captured["query"]
    assert "selector_signal_mode" in captured["query"]
    assert "selection_explanation" in captured["query"]
    assert "selector_earnings_blackout" in captured["query"]
    assert "WHERE exec_run_id = :eid" in captured["query"]
    assert captured["params"] == {"eid": "exec-42"}


def test_get_execution_positions_prefers_exec_run_scope(monkeypatch):
    import pandas as pd

    queries.get_execution_positions.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        if "FROM execution_positions" in query and params == {"eid": "exec-1"}:
            return pd.DataFrame({"symbol": ["AAPL"]})
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_positions(account_id="acct-1", exec_run_id="exec-1")

    assert not df.empty
    assert "source_exec_run_id = :eid" in calls[0][0]
    assert calls[0][1] == {"eid": "exec-1"}


def test_get_execution_positions_can_disable_account_fallback(monkeypatch):
    import pandas as pd

    queries.get_execution_positions.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_positions(account_id="acct-1", exec_run_id="exec-empty", allow_account_fallback=False)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(calls) == 1
    assert calls[0][1] == {"eid": "exec-empty"}


def test_get_execution_position_lots_scopes_account(monkeypatch):
    queries.get_execution_position_lots.clear()
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_position_lots(account_id="acct-lots")

    assert "FROM execution_position_lots" in captured["query"]
    assert "WHERE account_id = :account_id" in captured["query"]
    assert captured["params"] == {"account_id": "acct-lots"}


def test_get_execution_position_lots_prefers_exec_run_scope(monkeypatch):
    import pandas as pd

    queries.get_execution_position_lots.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        if params == {"eid": "exec-lots-1"}:
            return pd.DataFrame({"symbol": ["AAPL"]})
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_position_lots(account_id="acct-lots", exec_run_id="exec-lots-1")

    assert not df.empty
    assert "open_exec_run_id = :eid OR close_exec_run_id = :eid" in calls[0][0]
    assert calls[0][1] == {"eid": "exec-lots-1"}


def test_get_execution_position_lots_can_disable_account_fallback(monkeypatch):
    import pandas as pd

    queries.get_execution_position_lots.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_position_lots(account_id="acct-lots", exec_run_id="exec-empty", allow_account_fallback=False)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(calls) == 1
    assert calls[0][1] == {"eid": "exec-empty"}


def test_get_execution_reconciliation_results_prefers_exec_run_scope(monkeypatch):
    import pandas as pd

    queries.get_execution_reconciliation_results.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        if "FROM execution_reconciliation_results" in query and params == {"eid": "exec-1"}:
            return pd.DataFrame({"symbol": ["AAPL"], "reconciliation_status": ["SAFE_AUTO"]})
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_reconciliation_results(exec_run_id="exec-1", account_id="acct-1")

    assert not df.empty
    assert "WHERE exec_run_id = :eid" in calls[0][0]
    assert "CASE reconciliation_status" in calls[0][0]
    assert calls[0][1] == {"eid": "exec-1"}


def test_get_execution_reconciliation_results_scopes_account_when_run_empty(monkeypatch):
    import pandas as pd

    queries.get_execution_reconciliation_results.clear()
    calls = []
    expected = pd.DataFrame({"symbol": ["AAPL"]})

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        if params == {"eid": "exec-empty"}:
            return pd.DataFrame()
        return expected

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    result = queries.get_execution_reconciliation_results(exec_run_id="exec-empty", account_id="acct-1")

    assert result is expected
    assert calls[1][1] == {"account_id": "acct-1"}
    assert "WHERE account_id = :account_id" in calls[1][0]


def test_get_execution_reconciliation_results_can_disable_account_fallback(monkeypatch):
    import pandas as pd

    queries.get_execution_reconciliation_results.clear()
    calls = []

    def fake_safe_query(query, params=None):
        calls.append((query, params))
        return pd.DataFrame()

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    df = queries.get_execution_reconciliation_results(exec_run_id="exec-empty", account_id="acct-1", allow_account_fallback=False)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(calls) == 1
    assert calls[0][1] == {"eid": "exec-empty"}


def test_get_execution_live_guard_detects_running_live(monkeypatch):
    import pandas as pd

    queries.get_execution_live_guard.clear()

    monkeypatch.setattr(
        queries,
        "safe_query",
        lambda query, params=None: pd.DataFrame(
            [{
                "exec_run_id": "exec-live-1",
                "account_id": "acct-1",
                "trade_date": "2026-05-22",
                "broker_mode": "live",
                "status": "RUNNING",
                "started_at": "2026-05-22T14:30:00",
            }]
        ),
    )

    result = queries.get_execution_live_guard(account_id="acct-1")

    assert result["active"] is True
    assert result["count"] == 1
    assert result["run_ids"] == ["exec-live-1"]


def test_get_execution_reconciliation_j1_runs_flattens_summary(monkeypatch):
    import pandas as pd

    queries.get_execution_reconciliation_j1_runs.clear()
    monkeypatch.setattr(
        queries,
        "get_run_business_summaries",
        lambda **kwargs: pd.DataFrame(
            [{
                "run_summary": {
                    "trade_date": "2026-05-21",
                    "source_kind": "csv",
                    "statement_path": "F:/tmp/alpaca.csv",
                    "activity_count": 4,
                    "inserted": 4,
                    "diff_count": 2,
                    "diff_types": {"missing_internal": 1, "price_mismatch": 1},
                },
                "created_at": "2026-05-22T06:00:00",
            }]
        ),
    )

    df = queries.get_execution_reconciliation_j1_runs(account_id="acct-1")

    assert df.iloc[0]["trade_date"] == "2026-05-21"
    assert df.iloc[0]["diff_count"] == 2
    assert "missing_internal=1" in df.iloc[0]["diff_types_label"]


def test_get_execution_tca_aggregates_returns_grouped_frames(monkeypatch):
    import pandas as pd

    queries.get_execution_tca_aggregates.clear()
    monkeypatch.setattr(
        queries,
        "safe_query",
        lambda query, params=None: pd.DataFrame(
            {
                "account_id": ["acct-1", "acct-1"],
                "exec_run_id": ["exec-1", "exec-1"],
                "symbol": ["AAPL", "MSFT"],
                "filled_qty": [10.0, 5.0],
                "avg_fill_price": [100.0, 200.0],
                "fill_timestamp": pd.to_datetime(["2026-05-05T10:00:00Z", "2026-05-06T10:00:00Z"]),
                "slippage_bps": [5.0, 20.0],
                "implementation_shortfall": [1.0, 2.0],
            }
        ),
    )

    result = queries.get_execution_tca_aggregates(account_id="acct-1")

    assert set(result.keys()) == {"monthly", "by_bucket", "by_run"}
    assert result["monthly"].iloc[0]["fill_count"] == 2
    assert set(result["by_bucket"]["slippage_bucket"].tolist()) == {"0-10 bps", "10-25 bps"}


