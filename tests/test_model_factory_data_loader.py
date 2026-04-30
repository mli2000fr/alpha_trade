from modelFactory import data_loader

def test_data_loader_importable():
    assert hasattr(data_loader, "__doc__")


def test_load_universe_bars_builds_symbol_and_date_filters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConn()

    def fake_read_sql(query, conn, params=None, parse_dates=None):
        captured["sql"] = str(query)
        captured["params"] = dict(params or {})
        captured["parse_dates"] = parse_dates
        return data_loader.pd.DataFrame({"symbol": [], "date": []})

    monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

    data_loader.load_universe_bars(FakeEngine(), symbols=["AAPL", "MSFT"], end_date=data_loader.date(2024, 1, 31))

    assert "symbol IN" in str(captured["sql"])
    assert captured["params"] == {"sym_0": "AAPL", "sym_1": "MSFT", "end_date": data_loader.date(2024, 1, 31)}
    assert captured["parse_dates"] == ["date"]


