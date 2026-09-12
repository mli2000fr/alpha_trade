from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import yaml
import pytest

from analyst_research import collector
from analyst_research.collector import SymbolCollection
from analyst_research.parsers import STATUS_OK
from analyst_research.universe import resolve_universe


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


def test_collect_symbol_includes_eps_trend_and_revisions(monkeypatch) -> None:
    class FakeTicker:
        earnings_estimate = pd.DataFrame({"avg": [1.5]}, index=pd.Index(["0q"], name="period"))
        revenue_estimate = pd.DataFrame({"avg": [100.0]}, index=pd.Index(["0q"], name="period"))
        eps_trend = pd.DataFrame(
            {"current": [1.5], "7daysAgo": [1.4], "30daysAgo": [1.3],
             "60daysAgo": [1.2], "90daysAgo": [1.1]},
            index=pd.Index(["0q"], name="period"),
        )
        eps_revisions = pd.DataFrame(
            {"upLast7days": [4], "upLast30days": [9],
             "downLast7days": [1], "downLast30days": [3]},
            index=pd.Index(["0q"], name="period"),
        )
        analyst_price_targets = {}
        recommendations = pd.DataFrame()

    monkeypatch.setattr(collector.yf, "Ticker", lambda _symbol: FakeTicker())
    result = collector.collect_symbol(
        "AAPL", observed_at=datetime.now(timezone.utc), timeout_seconds=5,
    )
    assert result.status == STATUS_OK
    assert len(result.eps_trend_rows) == 1
    assert len(result.eps_revision_rows) == 1
    assert result.families["eps_trend"] == STATUS_OK
    assert result.families["eps_revisions"] == STATUS_OK


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
    assert config["analyst_snapshot_collection"]["status"] == "ACTIVE_RESEARCH_ONLY"
    assert "recherche" in config["analyst_snapshot_collection"]["research_notice"].lower()
    business_quant = config["business_quant_analyst_snapshot"]
    assert business_quant["enabled"] is False
    assert business_quant["status"] == "REPLACED_BY_YAHOO"
    assert "connecteur de secours" in business_quant["research_notice"]


def test_analyst_universe_is_strict_and_never_falls_back(tmp_path: Path) -> None:
    universe = tmp_path / "universe.txt"
    universe.write_text("BBB,AAA", encoding="utf-8")
    resolved = resolve_universe(symbols_file=str(universe))
    assert resolved.symbols == ["AAA", "BBB"]
    assert resolved.source == f"file:{universe}"
    assert resolved.warnings == []
    with pytest.raises(FileNotFoundError):
        resolve_universe(symbols_file=str(tmp_path / "missing.txt"))
