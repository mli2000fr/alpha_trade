from __future__ import annotations

import json
import sys

import pandas as pd

from screener import stock_screener
from screener.models import ScreenerRunReport


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


def test_stock_screener_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(stock_screener, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        stock_screener,
        "run_screener_with_report",
        lambda config, max_workers=None: (
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

