from __future__ import annotations

import json
import sys

import pandas as pd

from selector import alpha_scanner


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


class _FakeScanner:
    def __init__(self, engine=None, config=None) -> None:
        self.config = config

    def run(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"rank": 1, "symbol": "AAPL", "sector": "Tech", "final_score": 0.88},
                {"rank": 2, "symbol": "NVDA", "sector": "Tech", "final_score": 0.81},
                {"rank": 3, "symbol": "JPM", "sector": "Financials", "final_score": 0.74},
            ]
        )

    # Phase 3.3.b — exposer un agrégat factice pour vérifier la propagation
    # vers ``rejected_by_filter`` du run_summary CLI.
    def get_aggregated_filter_stats(self) -> dict[str, int]:
        return {
            "input": 5,
            "output": 3,
            "rejected_price": 1,
            "rejected_spread": 1,
            "rescued_spread_iex": 0,
            "rejected_market_cap_stale": 0,
        }


def test_alpha_scanner_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(alpha_scanner, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(alpha_scanner, "AlphaScanner", _FakeScanner)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alpha_scanner.py",
            "--chunk-size",
            "300",
            "--selection-size",
            "80",
            "--max-workers",
            "6",
            "--liquidity-threshold",
            "25000000",
            "--min-close",
            "12",
            "--max-volatility-ratio",
            "0.8",
            "--min-relative-strength-index",
            "105",
            "--min-high-52w-proximity",
            "0.8",
            "--min-weekly-trend-score",
            "0.9",
            "--min-atr-pct-20",
            "0.02",
            "--max-atr-pct-20",
            "0.05",
            "--min-market-cap",
            "3000000000",
            "--min-beta-126",
            "1.2",
            "--max-spread-bps",
            "18",
            "--earnings-blackout-days",
            "5",
            "--max-anomaly-count",
            "12",
            "--sector-cap-ratio",
            "0.25",
            "--log-level",
            "DEBUG",
        ],
    )

    alpha_scanner.main()

    stdout = capsys.readouterr().out.strip().splitlines()
    payload = _payload_from_stdout(stdout[0], alpha_scanner.RUN_SUMMARY_PREFIX)
    assert payload["requested_selection_size"] == 80
    assert payload["selected_candidates"] == 3
    assert payload["selected_sectors"] == 2
    assert payload["workers"] == 6
    assert payload["sector_cap_ratio"] == 0.25
    assert payload["top_symbols"] == ["AAPL", "NVDA", "JPM"]
    # Phase 3.3.b — ``rejected_by_filter`` doit être agrégé dans le payload.
    assert payload["rejected_by_filter"] == {
        "input": 5,
        "output": 3,
        "rejected_price": 1,
        "rejected_spread": 1,
        "rescued_spread_iex": 0,
        "rejected_market_cap_stale": 0,
    }
    # Phase 3.3.c/d — visibilité IEX/TTL au run_summary.
    assert "max_spread_bps_iex" in payload
    assert "min_quote_size" in payload
    assert "market_cap_max_age_days" in payload


def test_alpha_scanner_run_emits_live_progress(monkeypatch) -> None:
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

    scanner = alpha_scanner.AlphaScanner(
        engine=None,
        config=alpha_scanner.AlphaScannerConfig.strict_swing_cash(chunk_size=2, selection_size=2, max_workers=1),
    )
    progress_payloads: list[dict[str, object]] = []
    scanner.progress_callback = progress_payloads.append

    monkeypatch.setattr(scanner, "_reset_selector_outputs", lambda: None)
    monkeypatch.setattr(scanner, "_iter_eligible_symbol_chunks", lambda: iter([["AAA", "BBB"], ["CCC"]]))
    monkeypatch.setattr(
        scanner,
        "_process_chunk",
        lambda symbols: pd.DataFrame([{"symbol": symbol, "sector": "Tech", "final_score": 1.0}] for symbol in symbols),
    )
    monkeypatch.setattr(scanner, "rank_and_select", lambda merged_df: merged_df.head(2).copy())
    monkeypatch.setattr(scanner, "update_database", lambda selected_df, scored_df=None: len(selected_df))
    monkeypatch.setattr(alpha_scanner, "ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(alpha_scanner, "wait", lambda pending, return_when=None: (set(pending), set()))

    result = scanner.run()

    assert len(result) == 2
    assert progress_payloads
    assert progress_payloads[0]["progress_phase"] == "scan_chunks"
    assert any(payload.get("progress_phase") == "rank_select" for payload in progress_payloads)
    assert any(payload.get("progress_current") == 2 and payload.get("progress_total") == 2 for payload in progress_payloads)


