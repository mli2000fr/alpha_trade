from __future__ import annotations

import json
import sys

import pandas as pd

from selector import alpha_scanner
from selector import cli as _selector_cli
from selector import scanner as _selector_scanner


def _payload_from_stdout(stdout: str, prefix: str) -> dict[str, object]:
    assert stdout.startswith(prefix)
    return json.loads(stdout[len(prefix):])


class _FakeScanner:
    def __init__(self, engine=None, config=None) -> None:
        self.config = config

    def run(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "rank": 1,
                    "symbol": "AAPL",
                    "sector": "Tech",
                    "final_score": 0.88,
                    "trend_vcp_component": 0.41,
                    "total_score_component": 0.29,
                    "rsi_component": 0.18,
                    "selector_signal_mode": "sector_neutralized",
                    "selection_explanation": "mode=sector_neutralized; trend_vcp=0.4100; total=0.2900; rsi=0.1800; final=0.8800",
                },
                {
                    "rank": 2,
                    "symbol": "NVDA",
                    "sector": "Tech",
                    "final_score": 0.81,
                    "trend_vcp_component": 0.39,
                    "total_score_component": 0.25,
                    "rsi_component": 0.17,
                    "selector_signal_mode": "sector_neutralized",
                    "selection_explanation": "mode=sector_neutralized; trend_vcp=0.3900; total=0.2500; rsi=0.1700; final=0.8100",
                },
                {
                    "rank": 3,
                    "symbol": "JPM",
                    "sector": "Financials",
                    "final_score": 0.74,
                    "trend_vcp_component": 0.36,
                    "total_score_component": 0.22,
                    "rsi_component": 0.16,
                    "selector_signal_mode": "sector_neutralized",
                    "selection_explanation": "mode=sector_neutralized; trend_vcp=0.3600; total=0.2200; rsi=0.1600; final=0.7400",
                },
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

    def get_last_data_quality_gate(self) -> dict[str, object]:
        return {
            "status": "warning",
            "reference_date": "2026-04-30",
            "blocking_checks": [],
            "warning_checks": ["market_cap"],
            "skipped_filters": ["market_cap_ttl"],
            "checks": {
                "market_cap": {
                    "status": "warning",
                    "filter_key": "market_cap_ttl",
                    "applied_filter_fallback": "skip_filter",
                }
            },
        }

    def get_last_preselection_audit(self) -> dict[str, object]:
        return {
            "status": "ok",
            "input_symbols": 12,
            "eligible_symbols": 5,
            "rejected_symbols": 7,
            "eligible_ratio": 0.4167,
            "reason_counts": {
                "history_status_blocked": 3,
                "below_min_close": 2,
                "below_liquidity_threshold": 2,
            },
            "sample_symbols_by_reason": {
                "history_status_blocked": ["ERR", "STALE"],
                "below_min_close": ["PENNY"],
            },
            "top_reasons": [
                {
                    "reason": "history_status_blocked",
                    "label": "history_status bloqué",
                    "count": 3,
                    "sample_symbols": ["ERR", "STALE"],
                }
            ],
        }

    def get_last_ablation_summary(self) -> dict[str, object]:
        return {
            "mode": "shadow",
            "variant_count": 1,
            "artifact_path": "F:/projets/artifacts/selector/ablation/demo.json",
            "primary": {
                "variant_id": "primary",
                "selected_candidates": 3,
                "top_symbols": ["AAPL", "NVDA", "JPM"],
            },
            "variants": [
                {
                    "variant_id": "no_spread",
                    "disabled_filters": ["spread"],
                    "selected_candidates": 4,
                    "top_symbols": ["AAPL", "NVDA", "JPM", "AMD"],
                    "overlap_with_primary": {"count": 3, "ratio_vs_primary": 1.0},
                    "selection_diff": {"added_symbols": ["AMD"], "removed_symbols": []},
                }
            ],
        }


def test_alpha_scanner_main_emits_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(_selector_cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(_selector_cli, "AlphaScanner", _FakeScanner)
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
    assert payload["schema_version"] == 1
    assert payload["requested_selection_size"] == 80
    assert payload["preset_profile"] == "strict_swing_cash"
    assert payload["preset_profile_version"] == "v1"
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
    assert payload["data_quality_gate"]["status"] == "warning"
    assert payload["data_quality_modes"] == {
        "spread": "block",
        "earnings_blackout": "block",
        "market_cap_ttl": "warn_skip_filter",
    }
    assert payload["skipped_filters"] == ["market_cap_ttl"]
    assert payload["preselection_rejections"]["input_symbols"] == 12
    assert payload["preselection_rejections"]["reason_counts"]["history_status_blocked"] == 3
    assert payload["ablation"]["mode"] == "shadow"
    assert payload["ablation"]["variant_count"] == 1
    assert payload["ablation"]["variants"][0]["variant_id"] == "no_spread"
    assert payload["ablation"]["variants"][0]["selection_diff"]["added_symbols"] == ["AMD"]
    assert payload["top_candidate_explanations"][0]["symbol"] == "AAPL"
    assert payload["top_candidate_explanations"][0]["selector_signal_mode"] == "sector_neutralized"
    explainability_payload = payload["top_candidate_explanations"][0]["candidate_explainability_payload"]
    assert explainability_payload["identity"]["symbol"] == "AAPL"
    assert explainability_payload["identity"]["rank"] == 1
    assert explainability_payload["score_components"]["trend_vcp_component"] == 0.41
    assert explainability_payload["selection_context"]["selector_signal_mode"] == "sector_neutralized"


def test_alpha_scanner_main_emits_blocked_summary_on_data_quality_gate(monkeypatch, capsys) -> None:
    class _BlockedScanner:
        def __init__(self, engine=None, config=None) -> None:
            self.config = config

        def run(self) -> pd.DataFrame:
            raise alpha_scanner.SelectorDataQualityError(
                {
                    "status": "blocked",
                    "reference_date": "2026-04-30",
                    "blocking_checks": ["quotes"],
                    "checks": {
                        "quotes": {"status": "blocked", "reason": "quotes_stale"},
                    },
                }
            )

    monkeypatch.setattr(_selector_cli, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(_selector_cli, "AlphaScanner", _BlockedScanner)
    monkeypatch.setattr(sys, "argv", ["alpha_scanner.py"])

    alpha_scanner.main()

    stdout = capsys.readouterr().out.strip().splitlines()
    payload = _payload_from_stdout(stdout[0], alpha_scanner.RUN_SUMMARY_PREFIX)
    assert payload["run_status"] == "blocked"
    assert payload["failure_reason"] == "data_quality_gate_blocked"
    assert payload["data_quality_gate"]["blocking_checks"] == ["quotes"]
    assert stdout[1] == "Run bloqué par le data quality gate selector."


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

    monkeypatch.setattr(scanner, "preflight_data_quality", lambda: {"status": "ok", "blocking_checks": []})
    monkeypatch.setattr(scanner, "_reset_selector_outputs", lambda: None)
    monkeypatch.setattr(scanner, "_iter_eligible_symbol_chunks", lambda: iter([["AAA", "BBB"], ["CCC"]]))
    monkeypatch.setattr(
        scanner,
        "_process_chunk",
        lambda symbols: pd.DataFrame([{"symbol": symbol, "sector": "Tech", "final_score": 1.0}] for symbol in symbols),
    )
    monkeypatch.setattr(scanner, "rank_and_select", lambda merged_df: merged_df.head(2).copy())
    monkeypatch.setattr(scanner, "update_database", lambda selected_df, scored_df=None: len(selected_df))
    monkeypatch.setattr(_selector_scanner, "ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(_selector_scanner, "wait", lambda pending, return_when=None: (set(pending), set()))

    result = scanner.run()

    assert len(result) == 2
    assert progress_payloads
    assert progress_payloads[0]["progress_phase"] == "scan_chunks"
    assert any(payload.get("progress_phase") == "rank_select" for payload in progress_payloads)
    assert any(payload.get("progress_current") == 2 and payload.get("progress_total") == 2 for payload in progress_payloads)


