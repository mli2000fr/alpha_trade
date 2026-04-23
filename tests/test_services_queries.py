from ihm.services import queries

def test_services_queries_importable():
    assert hasattr(queries, "__doc__")


def test_get_predictions_can_filter_by_symbol(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    result = queries.get_predictions(symbol="AAPL", limit=25)

    assert result == "ok"
    assert "WHERE symbol = :symbol" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}
    assert "selected_model" in captured["query"]


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

    result = queries.get_model_governance(symbol="AAPL", limit=10)

    assert result == "ok"
    assert "FROM model_governance" in captured["query"]
    assert "WHERE symbol = :symbol" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}


def test_get_prediction_governance_audit_can_filter_by_symbol(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    result = queries.get_prediction_governance_audit(symbol="AAPL", limit=15)

    assert result == "ok"
    assert "FROM model_predictions p" in captured["query"]
    assert "LEFT JOIN model_governance served" in captured["query"]
    assert "LEFT JOIN model_governance champion" in captured["query"]
    assert "served.model_name = p.selected_model" in captured["query"]
    assert "champion.is_selected_model = 1" in captured["query"]
    assert "WHERE p.symbol = :symbol" in captured["query"]
    assert "governance_link_status" in captured["query"]
    assert captured["params"] == {"symbol": "AAPL"}


def test_get_prediction_governance_audit_without_symbol_has_no_params(monkeypatch):
    captured = {}

    def fake_safe_query(query, params=None):
        captured["query"] = query
        captured["params"] = params
        return "ok"

    monkeypatch.setattr(queries, "safe_query", fake_safe_query)

    result = queries.get_prediction_governance_audit(limit=5)

    assert result == "ok"
    assert "WHERE p.symbol = :symbol" not in captured["query"]
    assert captured["params"] is None


