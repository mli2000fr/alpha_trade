from modelFactory import orchestrator
from modelFactory.config import DataConfig, ModelConfig, TrainingConfig


def test_orchestrator_importable():
    assert hasattr(orchestrator, "__doc__")


def test_train_worker_loads_universe_when_cross_sectional_enabled(monkeypatch) -> None:
    cfg = TrainingConfig(
        data=DataConfig(enable_cross_sectional_features=True, benchmark_symbol="SPY"),
        model=ModelConfig(max_epochs=1),
        accelerator="cpu",
    )
    captured: dict[str, object] = {}

    import database.connection as db_connection

    monkeypatch.setattr(db_connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(orchestrator, "load_symbol_bars", lambda engine, symbol: "bars")
    monkeypatch.setattr(orchestrator, "load_benchmark_bars", lambda engine, benchmark_symbol: "benchmark")
    monkeypatch.setattr(orchestrator, "load_symbol_sentiment", lambda engine, symbol: "sentiment")
    monkeypatch.setattr(orchestrator, "load_universe_bars", lambda engine, symbols: {"symbols": list(symbols)})

    def fake_train_symbol(symbol, bars, cfg, engine, sentiment_df=None, benchmark_df=None, universe_df=None):
        captured["symbol"] = symbol
        captured["universe_df"] = universe_df
        return orchestrator.TrainResult(symbol, "run-1", "completed")

    monkeypatch.setattr(orchestrator, "train_symbol", fake_train_symbol)

    result = orchestrator._train_worker("AAPL", cfg, universe_symbols=["AAPL", "MSFT"])

    assert result.status == "completed"
    assert captured["symbol"] == "AAPL"
    assert captured["universe_df"] == {"symbols": ["AAPL", "MSFT"]}


