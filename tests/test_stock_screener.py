import pandas as pd

from screener.models import ScreenerChunkMetrics, ScreenerConfig
from screener.stock_screener import run_screener, run_screener_with_report


class _ImmediateFuture:
    def __init__(self, value) -> None:
        self._value = value

    def result(self):
        return self._value


class _ImmediateExecutor:
    def __init__(self, max_workers=None) -> None:
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def submit(self, fn, *args, **kwargs):
        return _ImmediateFuture(fn(*args, **kwargs))


def _immediate_wait(pending, return_when=None):
    return set(pending), set()


def test_run_screener_upserts_snapshot(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    fake_engine = object()

    monkeypatch.setattr("screener.stock_screener.get_engine", lambda: fake_engine)
    monkeypatch.setattr(
        "screener.stock_screener.load_spy_return_6m",
        lambda engine, config, as_of_date=None: 0.05,
    )
    monkeypatch.setattr("screener.stock_screener.iter_symbol_chunks", lambda engine, chunk_size: iter(()))
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000: calls.append(("upsert", len(df))),
    )

    scores = run_screener(ScreenerConfig(), max_workers=1)

    assert scores.empty
    assert calls == [("upsert", 0)]


def test_run_screener_with_report_aggregates_two_pass_metrics(monkeypatch) -> None:
    upsert_calls: list[tuple[object, int]] = []
    fake_engine = object()
    chunk_scores = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "liquidity_val": 10.0,
                "relative_strength_index": 110.0,
                "historical_range_score": 80.0,
                "total_score": 95.0,
                "last_updated_score": pd.Timestamp("2026-04-24 00:00:00"),
                "is_candidate": 0,
                "sector": None,
                "last_updated_scan": pd.Timestamp("2026-04-24 00:00:00"),
            }
        ]
    )
    chunk_metrics = ScreenerChunkMetrics(
        input_symbols=2,
        recent_rows_loaded=480,
        range_rows_loaded=1,
        symbols_pass_history=2,
        symbols_pass_liquidity=1,
        symbols_pass_relative_strength=1,
        symbols_final=1,
        rows_avoided_estimate=2519,
        pass1_seconds=0.12,
        pass2_seconds=0.03,
        duration_seconds=0.20,
    )

    monkeypatch.setattr("screener.stock_screener.get_engine", lambda: fake_engine)
    monkeypatch.setattr("screener.stock_screener.ProcessPoolExecutor", _ImmediateExecutor)
    monkeypatch.setattr("screener.stock_screener.wait", _immediate_wait)
    monkeypatch.setattr(
        "screener.stock_screener.load_spy_return_6m",
        lambda engine, config, as_of_date=None: 0.05,
    )
    monkeypatch.setattr(
        "screener.stock_screener.iter_symbol_chunks",
        lambda engine, chunk_size: iter([["AAA", "BBB"]]),
    )
    monkeypatch.setattr(
        "screener.stock_screener._process_chunk_two_passes",
        lambda symbols, config_dict, spy_return_6m, as_of_date_iso: (chunk_scores.copy(), chunk_metrics),
    )
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000: upsert_calls.append((engine, len(df))),
    )

    scores, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert list(scores["symbol"]) == ["AAA"]
    assert upsert_calls == [(fake_engine, 1)]
    assert report.targeted_symbols == 2
    assert report.chunks_total == 1
    assert report.chunks_completed == 1
    assert report.chunk_failures == 0
    assert report.recent_rows_loaded == 480
    assert report.range_rows_loaded == 1
    assert report.symbols_pass_history == 2
    assert report.symbols_pass_liquidity == 1
    assert report.symbols_pass_relative_strength == 1
    assert report.symbols_final == 1
    assert report.rows_avoided_estimate == 2519
