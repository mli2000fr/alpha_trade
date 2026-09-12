from __future__ import annotations

from pathlib import Path

import yaml

from analyst_research import collector
from analyst_research.collector import SymbolCollection
from analyst_research.parsers import STATUS_OK


def test_run_collection_counts_eps_and_revenue_coverage_independently(monkeypatch) -> None:
    rows_by_symbol = {
        "EPS_ONLY": [{"estimate_type": "EPS"}],
        "REVENUE_ONLY": [{"estimate_type": "REVENUE"}],
        "BOTH": [{"estimate_type": "EPS"}, {"estimate_type": "REVENUE"}],
    }

    monkeypatch.setattr(collector, "AnalystSnapshotRepository", lambda: object())
    monkeypatch.setattr(collector.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        collector,
        "_collect_with_retries",
        lambda symbol, **_kwargs: SymbolCollection(
            symbol=symbol,
            status=STATUS_OK,
            estimates_rows=rows_by_symbol[symbol],
        ),
    )

    summary = collector.run_collection(
        list(rows_by_symbol),
        write_db=False,
        sleep_seconds=0.0,
        max_retries=0,
    )

    assert summary["eps_coverage"] == 0.6667
    assert summary["revenue_coverage"] == 0.6667


def test_analyst_launcher_honours_enabled_before_provider_call() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts" / "windows" / "analyst_snapshot_launcher.ps1").read_text(
        encoding="utf-8"
    )

    guard_position = content.index("if (-not $collectionEnabled)")
    provider_call_position = content.index("$collectScriptPath =")
    assert guard_position < provider_call_position
    assert "analyst_snapshot_collection.enabled=false" in content
    assert "exit 0" in content[guard_position:provider_call_position]


def test_active_analyst_collection_config_is_explicit() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "batch.yaml").read_text(encoding="utf-8"))
    assert config["analyst_snapshot_collection"]["enabled"] is True
