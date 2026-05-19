from __future__ import annotations

import json
import sys
from typing import cast

import pandas as pd

from screener import stock_screener
from screener.models import ScreenerChunkMetrics
from screener.models import ScreenerConfig
from screener.models import ScreenerRunReport


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


def test_stock_screener_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(stock_screener, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        stock_screener,
        "run_screener_with_report",
        lambda config, max_workers=None, as_of_date=None, snapshot_date=None, progress_callback=None: (
            pd.DataFrame(),
            ScreenerRunReport(
                run_id="stock-screener-20260425010101-abc123",
                benchmark_symbol=config.benchmark_symbol,
                chunk_size=config.chunk_size,
                workers=max_workers or 4,
                as_of_date=None,
                started_at="2026-04-25T01:01:01",
                finished_at="2026-04-25T01:01:03",
                duration_seconds=2.0,
                targeted_symbols=1200,
                chunks_total=3,
                chunks_completed=3,
                chunk_failures=0,
                recent_rows_loaded=50000,
                range_rows_loaded=1200,
                symbols_pass_history=700,
                symbols_pass_liquidity=300,
                symbols_pass_relative_strength=180,
                symbols_final=120,
                rows_avoided_estimate=250000,
                benchmark_load_seconds=0.02,
                pass1_seconds=0.7,
                pass2_seconds=0.4,
                upsert_seconds=0.1,
            ),
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stock_screener.py",
            "--chunk-size",
            "250",
            "--max-workers",
            "6",
            "--benchmark",
            "QQQ",
            "--liquidity-threshold-usd",
            "5000000",
            "--min-relative-strength-index",
            "105",
            "--historical-range-lookback-days",
            "252",
            "--min-historical-range-score",
            "80",
            "--first-pass-window-days",
            "504",
            "--disable-two-pass-loading",
        ],
    )

    stock_screener.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), stock_screener.RUN_SUMMARY_PREFIX)
    assert payload["chunk_size"] == 250
    assert payload["workers"] == 6
    assert payload["benchmark_symbol"] == "QQQ"
    assert payload["symbols_final"] == 120
    assert payload["rows_avoided_estimate"] == 250000


def test_stock_screener_main_emits_chunk_error_samples_when_available(monkeypatch, capsys) -> None:
    monkeypatch.setattr(stock_screener, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        stock_screener,
        "run_screener_with_report",
        lambda config, max_workers=None, as_of_date=None, snapshot_date=None, progress_callback=None: (
            pd.DataFrame(),
            ScreenerRunReport(
                run_id="stock-screener-20260425010101-abc123",
                benchmark_symbol=config.benchmark_symbol,
                chunk_size=config.chunk_size,
                workers=max_workers or 4,
                as_of_date=None,
                started_at="2026-04-25T01:01:01",
                finished_at="2026-04-25T01:01:03",
                chunk_failures=1,
                chunks_total=3,
                chunk_error_samples=[
                    {
                        "input_symbols": 2,
                        "sample_symbols": ["AAA", "BBB"],
                        "error_message": "db timeout",
                    }
                ],
            ),
        ),
    )
    monkeypatch.setattr(sys, "argv", ["stock_screener.py"])

    stock_screener.main()

    payload = _payload_from_stdout(capsys.readouterr().out.strip(), stock_screener.RUN_SUMMARY_PREFIX)
    assert payload["chunk_failures"] == 1
    assert payload["chunk_error_samples"] == [
        {
            "input_symbols": 2,
            "sample_symbols": ["AAA", "BBB"],
            "error_message": "db timeout",
        }
    ]


def test_stock_screener_main_uses_trade_date_as_as_of_date(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(stock_screener, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(stock_screener, "_emit_run_summary", lambda payload: None)
    monkeypatch.setattr(
        stock_screener,
        "run_screener_with_report",
        lambda config, max_workers=None, as_of_date=None, snapshot_date=None, progress_callback=None: captured.update(
            {
                "as_of_date": as_of_date,
                "snapshot_date": snapshot_date,
            }
        )
        or (
            pd.DataFrame(),
            ScreenerRunReport(
                run_id="stock-screener-20260425010101-abc123",
                benchmark_symbol=config.benchmark_symbol,
                chunk_size=config.chunk_size,
                workers=max_workers or 4,
                as_of_date=as_of_date.isoformat() if as_of_date else None,
                started_at="2026-04-25T01:01:01",
                finished_at="2026-04-25T01:01:03",
            ),
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stock_screener.py",
            "--trade-date",
            "2026-04-19",
        ],
    )

    stock_screener.main()

    assert str(captured["as_of_date"]) == "2026-04-19"
    assert str(captured["snapshot_date"]) == "2026-04-19"


def test_stock_screener_main_uses_strict_swing_cash_defaults(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(stock_screener, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(stock_screener, "_emit_run_summary", lambda payload: None)
    monkeypatch.setattr(
        stock_screener,
        "run_screener_with_report",
        lambda config, max_workers=None, as_of_date=None, snapshot_date=None, progress_callback=None: captured.update(
            {"config": config}
        )
        or (
            pd.DataFrame(),
            ScreenerRunReport(
                run_id="stock-screener-20260425010101-abc123",
                benchmark_symbol=config.benchmark_symbol,
                chunk_size=config.chunk_size,
                workers=max_workers or 4,
                as_of_date=None,
                started_at="2026-04-25T01:01:01",
                finished_at="2026-04-25T01:01:03",
            ),
        ),
    )
    monkeypatch.setattr(sys, "argv", ["stock_screener.py"])

    stock_screener.main()

    config = cast(ScreenerConfig, captured["config"])
    assert config.min_close_price == 10.0
    assert config.liquidity_threshold_usd == 30_000_000.0
    assert config.min_relative_strength_index == 100.0


def test_run_screener_with_report_emits_live_progress_callbacks(monkeypatch) -> None:
    class _FakeFuture:
        def __init__(self, result):
            self._result = result

        def result(self):
            return self._result

    class _FakeExecutor:
        def __init__(self, max_workers=None):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, func, *args, **kwargs):
            return _FakeFuture(func(*args, **kwargs))

    monkeypatch.setattr(stock_screener, "get_engine", lambda: object())
    monkeypatch.setattr(stock_screener, "load_spy_return_6m", lambda engine, config, as_of_date=None: 0.12)
    monkeypatch.setattr(stock_screener, "iter_symbol_chunks", lambda engine, chunk_size: [["AAA", "BBB"]])
    monkeypatch.setattr(stock_screener, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(stock_screener, "wait", lambda pending, return_when=None: (set(pending), set()))
    monkeypatch.setattr(stock_screener, "upsert_scores_snapshot", lambda engine, final_scores, chunksize=1000, snapshot_date=None: None)
    monkeypatch.setattr(
        stock_screener,
        "_process_chunk_two_passes",
        lambda symbols, config_dict, spy_return_6m, as_of_date_iso: (
            pd.DataFrame([{"symbol": "AAA", "total_score": 10.0}]),
            ScreenerChunkMetrics(
                input_symbols=len(symbols),
                recent_rows_loaded=20,
                range_rows_loaded=10,
                symbols_pass_history=2,
                symbols_pass_liquidity=2,
                symbols_pass_relative_strength=1,
                symbols_final=1,
            ),
        ),
    )

    progress_payloads: list[dict[str, object]] = []
    _, report = stock_screener.run_screener_with_report(
        config=stock_screener.ScreenerConfig(chunk_size=2),
        max_workers=1,
        progress_callback=progress_payloads.append,
    )

    assert report.chunks_total == 1
    assert report.chunks_completed == 1
    assert len(progress_payloads) >= 2
    assert progress_payloads[0]["progress_phase"] == "scan_chunks"
    assert progress_payloads[-1]["progress_current"] == 1
    assert progress_payloads[-1]["progress_total"] == 1


