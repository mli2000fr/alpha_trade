from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory import oof_consensus_audit as consensus


def _oof(*, reverse: bool = False, dates: int = 20, symbols: int = 20) -> pd.DataFrame:
    rows = []
    for date_index, date in enumerate(pd.date_range("2023-01-02", periods=dates, freq="B")):
        for symbol_index in range(symbols):
            signal = symbol_index / (symbols - 1)
            score = 1.0 - signal if reverse else signal
            rows.append({
                "date": date,
                "symbol": f"S{symbol_index:03d}",
                "future_return": (signal - 0.5) * 0.20,
                "fold_index": date_index // 2,
                "score": score,
                "up": score,
                "down": 1.0 - score,
            })
    return pd.DataFrame(rows)


def test_load_component_normalizes_within_each_date(tmp_path: Path) -> None:
    path = tmp_path / "oof.parquet"
    _oof().to_parquet(path, index=False)
    loaded = consensus.load_component(
        tmp_path, {"path": "oof.parquet", "score": {"type": "column", "column": "score"}}
    )
    assert loaded["component_rank"].between(0, 1).all()
    assert loaded.groupby("date")["component_rank"].max().eq(1.0).all()
    assert "future_return" in loaded and "fold_index" in loaded


def test_difference_score_and_duplicate_guard(tmp_path: Path) -> None:
    frame = _oof(dates=2)
    path = tmp_path / "oof.parquet"
    frame.to_parquet(path, index=False)
    loaded = consensus.load_component(
        tmp_path,
        {"path": "oof.parquet", "score": {"type": "difference", "positive": "up", "negative": "down"}},
    )
    assert loaded.sort_values(["date", "symbol"])["component_rank"].is_monotonic_increasing is False
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    duplicated.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="non unique"):
        consensus.load_component(
            tmp_path, {"path": "oof.parquet", "score": {"type": "column", "column": "score"}}
        )


def test_consensus_detects_shared_directional_signal(tmp_path: Path) -> None:
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    _oof().to_parquet(first, index=False)
    frame = _oof()
    frame["score"] += np.tile(np.linspace(-0.01, 0.01, 20), 20)
    frame.to_parquet(second, index=False)
    families = [
        {"name": "a", "components": [{"path": first.name, "score": {"type": "column", "column": "score"}}]},
        {"name": "b", "components": [{"path": second.name, "score": {"type": "column", "column": "score"}}]},
    ]
    panel, diagnostics = consensus.build_horizon_panel(tmp_path, 3, families)
    metrics = consensus.evaluate_score(panel, "consensus_score", 0.20)
    assert diagnostics["family_count"] == 2
    assert metrics["mean_daily_ic"] > 0.99
    assert metrics["selection"]["long"]["mean_signed_return"] > 0
    assert metrics["selection"]["short"]["mean_signed_return"] > 0


def test_run_audit_writes_reproducible_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "oof.parquet"
    _oof().to_parquet(source, index=False)
    manifest = {
        "oracle_batch_id": "oracle-test",
        "selection_fraction": 0.20,
        "horizons": {"3": {"families": [
            {"name": "signal", "components": [
                {"path": source.name, "score": {"type": "column", "column": "score"}}
            ]}
        ]}},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "result"
    report = consensus.run_audit(manifest_path, output, project_root=tmp_path)
    assert report["research_only"] is True
    assert report["results"]["3"]["verdict"] in {"GO_RESEARCH", "NO_GO"}
    assert (output / "report.json").exists()
    assert (output / "consensus_predictions.parquet").exists()


def test_daily_overlay_filters_each_side_without_lookahead() -> None:
    frame = _oof(dates=4, symbols=20).rename(columns={"score": "consensus_score"})
    overlay = pd.DataFrame({
        "date": sorted(frame["date"].unique()),
        "daily_overlay_score": [1.0, -1.0, 1.0, -1.0],
    })
    result = consensus.evaluate_daily_overlay(frame, overlay, fraction=0.20)
    assert result["available_dates"] == 4
    assert result["date_coverage"] == 1.0
    assert result["long_coverage_vs_tail"] == pytest.approx(0.5)
    assert result["short_coverage_vs_tail"] == pytest.approx(0.5)
