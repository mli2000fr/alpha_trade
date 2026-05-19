from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_bench_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "bench_full_pipeline.py"
    spec = importlib.util.spec_from_file_location("bench_full_pipeline_test_module", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Impossible de charger scripts/bench_full_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_screener_uses_current_screener_pipeline_and_returns_details() -> None:
    bench = _load_bench_module()

    details = bench._stage_screener(["AAA", "BBB", "CCC"])

    assert details["mode"] == "synthetic_current_screener_pipeline"
    assert details["input_symbols"] == 3
    assert details["rows_generated"] > 0
    assert details["symbols_final"] >= 0


def test_main_writes_stage_details_to_benchmark_payload(monkeypatch, tmp_path) -> None:
    bench = _load_bench_module()

    monkeypatch.setattr(bench, "_stage_screener", lambda symbols: {"mode": "screener-test", "symbols": len(symbols)})
    monkeypatch.setattr(bench, "_stage_selector", lambda symbols: {"mode": "selector-test"})
    monkeypatch.setattr(bench, "_stage_risk", lambda symbols: {"mode": "risk-test"})
    monkeypatch.setattr(bench, "_stage_execution_dry_run", lambda symbols: {"mode": "execution-test"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bench_full_pipeline.py",
            "--symbols",
            "5",
            "--threshold",
            "999",
            "--output",
            str(tmp_path),
        ],
    )

    exit_code = bench.main()

    assert exit_code == 0
    outputs = sorted(tmp_path.glob("full_pipeline_*.json"))
    assert len(outputs) == 1
    payload = json.loads(outputs[0].read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["stages"]["screener"]["details"] == {"mode": "screener-test", "symbols": 5}
    assert payload["stages"]["selector"]["details"] == {"mode": "selector-test"}
    assert payload["stages"]["risk"]["details"] == {"mode": "risk-test"}
    assert payload["stages"]["execution_dry_run"]["details"] == {"mode": "execution-test"}

