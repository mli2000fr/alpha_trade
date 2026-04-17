from screener.models import ScreenerConfig
from screener.stock_screener import run_screener


def test_run_screener_upserts_snapshot(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    fake_engine = object()

    monkeypatch.setattr("screener.stock_screener.get_engine", lambda: fake_engine)
    monkeypatch.setattr(
        "screener.stock_screener.load_spy_return_6m",
        lambda engine, config, as_of_date=None: 0.05,
    )
    monkeypatch.setattr("screener.stock_screener.iter_symbol_chunks", lambda engine, chunk_size, timeframe: iter(()))
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000: calls.append(("upsert", len(df))),
    )

    scores = run_screener(ScreenerConfig(), max_workers=1)

    assert scores.empty
    assert calls == [("upsert", 0)]


