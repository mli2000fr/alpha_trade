from event_sentiment import mapping

def test_entity_sector_mapper_load_local_sectors(monkeypatch):
    class DummyEngine:
        def connect(self):
            class Conn:
                def execute(self, stmt):
                    class Result:
                        def all(self):
                            return [("AAPL", "Tech", None), ("MSFT", None, None)]
                    return Result()
                def __enter__(self): return self
                def __exit__(self, exc_type, exc, tb): return False
            return Conn()
    monkeypatch.setattr(mapping, "get_sqlalchemy_engine", lambda: DummyEngine())
    monkeypatch.setattr(mapping, "get_stock_metadata_table", lambda: type("T", (), {"c": type("C", (), {"symbol": None, "sector": None, "last_updated": None})})())
    mapper = mapping.EntitySectorMapper()
    result = mapper._load_local_sectors(["AAPL", "MSFT"])
    assert "AAPL" in result
    assert result["AAPL"]["sector"] == "Tech"
    assert "sector_source" in result["AAPL"]
