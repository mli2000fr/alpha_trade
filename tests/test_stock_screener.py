import logging

import pandas as pd

from common.tradable_universe import UniverseMember
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


def test_run_screener_preserves_previous_snapshot_when_run_is_empty(monkeypatch) -> None:
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
        lambda engine, df, chunksize=1000, snapshot_date=None: calls.append(("upsert", len(df))),
    )

    scores = run_screener(ScreenerConfig(), max_workers=1)

    assert scores.empty
    assert calls == []


def test_run_screener_with_report_marks_empty_run_as_preserved(monkeypatch) -> None:
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
        lambda engine, df, chunksize=1000, snapshot_date=None: calls.append(("upsert", len(df))),
    )

    scores, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert scores.empty
    assert calls == []
    assert report.persistence_status == "preserved_previous_scores_empty_run"
    assert report.persisted_rows == 0
    assert report.purge_performed is False
    assert report.archive_performed is False
    assert report.chunk_error_samples == []


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
        lambda engine, df, chunksize=1000, snapshot_date=None: upsert_calls.append((engine, len(df))),
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
    assert report.persistence_status == "replaced_scores_full_run"
    assert report.persisted_rows == 1
    assert report.purge_performed is True
    assert report.archive_performed is True


def test_run_screener_publishes_complete_objective_universe(monkeypatch) -> None:
    fake_engine = object()
    published: list[tuple[str, list[UniverseMember]]] = []
    failed: list[tuple[str, str]] = []
    chunk_scores = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "liquidity_val": 10.0,
                "relative_strength_index": 110.0,
                "historical_range_score": 80.0,
                "total_score": 95.0,
                "last_updated_score": pd.Timestamp("2026-04-24 00:00:00"),
                "sector": None,
                "last_updated_scan": pd.Timestamp("2026-04-24 00:00:00"),
            }
        ]
    )
    members = (
        UniverseMember("AAA", True, "tradable", data_quality_grade="degraded"),
        UniverseMember("BBB", False, "adv_below_minimum", data_quality_grade="degraded"),
    )
    metrics = ScreenerChunkMetrics(
        input_symbols=2,
        symbols_final=1,
        universe_members=members,
    )

    monkeypatch.setattr("screener.stock_screener.get_engine", lambda: fake_engine)
    monkeypatch.setattr("screener.stock_screener.ProcessPoolExecutor", _ImmediateExecutor)
    monkeypatch.setattr("screener.stock_screener.wait", _immediate_wait)
    monkeypatch.setattr("screener.stock_screener.load_spy_return_6m", lambda *args, **kwargs: 0.05)
    monkeypatch.setattr("screener.stock_screener.iter_symbol_chunks", lambda *args, **kwargs: iter([["AAA", "BBB"]]))
    monkeypatch.setattr(
        "screener.stock_screener._process_chunk_two_passes",
        lambda *args, **kwargs: (chunk_scores.copy(), metrics),
    )
    monkeypatch.setattr("screener.stock_screener.upsert_scores_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr("screener.stock_screener.universe_schema_available", lambda engine: True)
    monkeypatch.setattr("screener.stock_screener.begin_universe_run", lambda *args, **kwargs: "universe-run-1")
    monkeypatch.setattr(
        "screener.stock_screener.publish_universe_run",
        lambda engine, run_id, rows: published.append((run_id, list(rows))),
    )
    monkeypatch.setattr(
        "screener.stock_screener.fail_universe_run",
        lambda engine, run_id, reason: failed.append((run_id, reason)),
    )

    _, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert [(run_id, [row.symbol for row in rows]) for run_id, rows in published] == [
        ("universe-run-1", ["AAA", "BBB"])
    ]
    assert failed == []
    assert report.universe_run_id == "universe-run-1"
    assert report.universe_persistence_status == "completed_degraded"
    assert report.universe_rows_written == 2


def test_run_screener_with_report_preserves_previous_snapshot_when_chunk_failures_exist(monkeypatch) -> None:
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
                "sector": None,
                "last_updated_scan": pd.Timestamp("2026-04-24 00:00:00"),
            }
        ]
    )
    failed_chunk_metrics = ScreenerChunkMetrics(
        input_symbols=2,
        recent_rows_loaded=480,
        range_rows_loaded=1,
        symbols_pass_history=2,
        symbols_pass_liquidity=1,
        symbols_pass_relative_strength=1,
        symbols_final=1,
        failed=True,
        error_message="db timeout",
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
        lambda symbols, config_dict, spy_return_6m, as_of_date_iso: (chunk_scores.copy(), failed_chunk_metrics),
    )
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000, snapshot_date=None: upsert_calls.append((engine, len(df))),
    )

    scores, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert list(scores["symbol"]) == ["AAA"]
    assert upsert_calls == []
    assert report.chunk_failures == 1
    assert report.symbols_final == 1
    assert report.persistence_status == "preserved_previous_scores_partial_run"
    assert report.persisted_rows == 0
    assert report.purge_performed is False
    assert report.archive_performed is False
    assert report.chunk_error_samples == [
        {
            "input_symbols": 2,
            "sample_symbols": ["AAA", "BBB"],
            "error_message": "db timeout",
        }
    ]


def test_run_screener_with_report_logs_enriched_partial_run_context(monkeypatch, caplog) -> None:
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
                "sector": None,
                "last_updated_scan": pd.Timestamp("2026-04-24 00:00:00"),
            }
        ]
    )
    failed_chunk_metrics = ScreenerChunkMetrics(
        input_symbols=2,
        recent_rows_loaded=480,
        range_rows_loaded=1,
        symbols_pass_history=2,
        symbols_pass_liquidity=1,
        symbols_pass_relative_strength=1,
        symbols_final=1,
        failed=True,
        error_message="db timeout",
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
        lambda symbols, config_dict, spy_return_6m, as_of_date_iso: (chunk_scores.copy(), failed_chunk_metrics),
    )
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000, snapshot_date=None: None,
    )

    with caplog.at_level(logging.WARNING):
        _, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert report.persistence_status == "preserved_previous_scores_partial_run"
    assert f"run_id={report.run_id}" in caplog.text
    assert "Run screener partiel preserve" in caplog.text
    assert "ratio=100.00%" in caplog.text
    assert "sample_count=1" in caplog.text
    assert "sample=1/1" in caplog.text
    assert "error=db timeout" in caplog.text


def test_run_screener_with_report_caps_chunk_error_samples(monkeypatch) -> None:
    fake_engine = object()

    monkeypatch.setattr("screener.stock_screener.get_engine", lambda: fake_engine)
    monkeypatch.setattr("screener.stock_screener.ProcessPoolExecutor", _ImmediateExecutor)
    monkeypatch.setattr("screener.stock_screener.wait", _immediate_wait)
    monkeypatch.setattr(
        "screener.stock_screener.load_spy_return_6m",
        lambda engine, config, as_of_date=None: 0.05,
    )
    monkeypatch.setattr(
        "screener.stock_screener.iter_symbol_chunks",
        lambda engine, chunk_size: iter([[f"SYM{i}", f"ALT{i}"] for i in range(6)]),
    )

    def _failed_chunk(symbols, config_dict, spy_return_6m, as_of_date_iso):
        return pd.DataFrame(), ScreenerChunkMetrics(
            input_symbols=len(symbols),
            failed=True,
            error_message=f"chunk failure {symbols[0]}",
        )

    monkeypatch.setattr("screener.stock_screener._process_chunk_two_passes", _failed_chunk)
    monkeypatch.setattr(
        "screener.stock_screener.upsert_scores_snapshot",
        lambda engine, df, chunksize=1000, snapshot_date=None: None,
    )

    scores, report = run_screener_with_report(ScreenerConfig(), max_workers=1)

    assert scores.empty
    assert report.chunk_failures == 6
    assert len(report.chunk_error_samples) == 5
    sample_errors = {sample["error_message"] for sample in report.chunk_error_samples}
    assert sample_errors.issubset({f"chunk failure SYM{i}" for i in range(6)})
    assert "chunk failure SYM0" in sample_errors
