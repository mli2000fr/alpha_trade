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


def test_get_execution_orders_includes_stop_and_trailing_fields(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    queries.get_execution_orders(exec_run_id="exec-1")

    assert "FROM execution_orders" in captured["query"]
    assert "stop_price" in captured["query"]
    assert "trail_percent" in captured["query"]
    assert captured["params"] == {"eid": "exec-1"}


