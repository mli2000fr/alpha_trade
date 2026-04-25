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

