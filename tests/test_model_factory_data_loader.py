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

    data_loader.load_universe_bars(
        FakeEngine(),
        symbols=["AAPL", "MSFT"],
        start_date=data_loader.date(2019, 1, 31),
        end_date=data_loader.date(2024, 1, 31),
    )

    assert "symbol IN" in str(captured["sql"])
    assert captured["params"] == {
        "sym_0": "AAPL",
        "sym_1": "MSFT",
        "start_date": data_loader.date(2019, 1, 31),
        "end_date": data_loader.date(2024, 1, 31),
    }
    assert captured["parse_dates"] == ["date"]


def test_resolve_history_window_start_date_subtracts_years_with_leap_day_fallback() -> None:
    assert data_loader.resolve_history_window_start_date(data_loader.date(2024, 2, 29), 5) == data_loader.date(2019, 2, 28)


def test_resolve_training_start_date_prefers_explicit_date() -> None:
    assert data_loader.resolve_training_start_date(
        data_loader.date(2026, 4, 17),
        training_start_date=data_loader.date(2020, 1, 1),
        history_window_years=10,
    ) == data_loader.date(2020, 1, 1)


def test_load_symbol_latest_bar_dates_builds_grouped_query(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return [
                {"symbol": "AAPL", "latest_date": data_loader.date(2026, 4, 17)},
                {"symbol": "MSFT", "latest_date": data_loader.date(2026, 4, 16)},
            ]

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            captured["sql"] = str(query)
            captured["params"] = dict(params or {})
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConn()

    result = data_loader.load_symbol_latest_bar_dates(
        FakeEngine(),
        ["AAPL", "MSFT"],
        end_date=data_loader.date(2026, 4, 17),
    )

    assert "GROUP BY symbol" in str(captured["sql"])
    assert result == {
        "AAPL": data_loader.date(2026, 4, 17),
        "MSFT": data_loader.date(2026, 4, 16),
    }
    assert captured["params"] == {
        "sym_0": "AAPL",
        "sym_1": "MSFT",
        "end_date": data_loader.date(2026, 4, 17),
    }


