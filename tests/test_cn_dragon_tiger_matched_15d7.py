"""Outcome-blind D7 protocol and temporal matching gates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from service.market.cn_dragon_tiger_matched_15d7 import (
    audit, load_candidates, load_protocol, load_timely_snapshots, match_candidates,
)
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar

CALENDAR = Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml")
PROTOCOL = Path("config/research_cn/sprint15d7_dragon_tiger_protocol.yaml")
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def _snapshot(root: Path, *, observed="2026-09-29T22:30:00+00:00",
              events=None, name="snapshot-1.json") -> Path:
    folder = root / "2026-09-29"
    folder.mkdir(parents=True, exist_ok=True)
    rows = events if events is not None else [{
        "date": "2026-09-29", "exchange": "SSE", "code": "600001",
        "reason": "1", "payload_sha256": "a" * 64,
        "first_seen_at_utc": observed,
    }]
    payload = {
        "schema": "cn_dragon_tiger_observation_v1", "source": "SSE_SSE_STAR_SZSE_OFFICIAL",
        "trade_date": "2026-09-29", "observed_at_utc": observed,
        "provenance": {"sse": {"pages": 1}, "szse": {"pages": 1}},
        "counts": {"events": len(rows)}, "events": rows,
        "collection_context": {
            "phase": "before_open", "target_session": "2026-09-29",
            "next_open_session": "2026-09-30",
            "decision_cutoff_shanghai": "2026-09-30T09:15:00+08:00",
        },
    }
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _candidates(path: Path, **overrides) -> Path:
    rows = []
    symbols = [("600001", .92, .05), ("600002", .90, .06),
               ("600003", .88, .04), ("600004", .10, -.10)]
    symbols += [(f"600{code:03d}", .08 - code * .001, -.10)
                for code in range(5, 13)]
    for code, score, prior in symbols:
        rows.append({
            "decision_date": "2026-09-30", "exchange": "SSE", "code": code,
            "board_code": "MAIN", "oracle_score": score,
            "prior_return_5d": prior, "oracle_top20": True, "oracle_oos": True,
            "score_available_at_utc": "2026-09-29T15:00:00+00:00",
            "prior_return_available_at_utc": "2026-09-29T15:00:00+00:00",
            "model_trained_through": "2025-12-31", **overrides,
        })
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_preflight_waits_for_prospective_oracle_scores(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    report = audit(snapshot_root=root, calendar_path=CALENDAR, protocol_path=PROTOCOL,
                   output=tmp_path / "result", now=NOW)
    assert report["status"] == "WAITING_FOR_PROSPECTIVE_ORACLE_OOS_CANDIDATES"
    assert report["observations"]["sessions"] == 1
    assert report["observations"]["unique_event_symbols"] == 1
    assert report["outcomes_loaded"] is False
    assert report["training_performed"] is False
    assert not (tmp_path / "result" / "outcome_blind_matches.parquet").exists()


def test_latest_snapshot_before_cutoff_is_authoritative(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root, name="snapshot-1.json")
    _snapshot(root, observed="2026-09-30T00:30:00+00:00", events=[], name="snapshot-2.json")
    _snapshot(root, observed="2026-09-30T01:30:00+00:00", name="snapshot-3.json")
    selected, stats = load_timely_snapshots(root, load_calendar(CALENDAR), now=NOW)
    assert selected["2026-09-30"]["event_symbols"] == set()
    assert stats["late_files"] == 1
    assert stats["revisions"] == 1


def test_future_cutoff_snapshot_is_preview_only(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    before = datetime(2026, 9, 29, 23, 0, tzinfo=timezone.utc)
    calendar = load_calendar(CALENDAR)
    strict, strict_stats = load_timely_snapshots(root, calendar, now=before)
    preview, preview_stats = load_timely_snapshots(
        root, calendar, now=before, include_future_cutoffs=True,
    )
    assert strict == {}
    assert strict_stats["future_cutoffs"] == 1
    assert "2026-09-30" in preview
    assert preview_stats["future_cutoffs"] == 1


def test_matching_is_outcome_blind_and_respects_calipers(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    snapshots, _ = load_timely_snapshots(root, load_calendar(CALENDAR), now=NOW)
    candidates = load_candidates(_candidates(tmp_path / "candidates.parquet"),
                                 load_protocol(PROTOCOL), snapshots)
    matches, metrics = match_candidates(candidates, load_protocol(PROTOCOL))
    assert metrics["exposed_candidates"] == 1
    assert metrics["matched_exposed"] == 1
    assert metrics["matched_pairs"] == 1
    assert matches.iloc[0]["control_code"] == "600002"
    assert not any("target" in name or "future" in name for name in matches.columns)


def test_full_matching_audit_writes_only_outcome_blind_artifacts(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    path = _candidates(tmp_path / "candidates.parquet")
    report = audit(snapshot_root=root, calendar_path=CALENDAR, protocol_path=PROTOCOL,
                   candidates_path=path, output=tmp_path / "result", now=NOW)
    assert report["matching"]["matched_pairs"] == 1
    assert report["status"] != "MATCHING_READY_FOR_SEPARATE_OUTCOME_AUDIT"
    saved = pd.read_parquet(tmp_path / "result" / "outcome_blind_matches.parquet")
    assert len(saved) == 1
    assert not any("future" in column or "target" in column for column in saved)
    assert (tmp_path / "result" / "report.json").exists()


def test_csv_boolean_columns_are_validated(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    snapshots, _ = load_timely_snapshots(root, load_calendar(CALENDAR), now=NOW)
    parquet = _candidates(tmp_path / "candidates.parquet")
    csv = tmp_path / "candidates.csv"
    pd.read_parquet(parquet).to_csv(csv, index=False)
    frame = load_candidates(csv, load_protocol(PROTOCOL), snapshots)
    assert int(frame["exposed"].sum()) == 1


@pytest.mark.parametrize("override,expected", [
    ({"oracle_oos": False}, "genuinely OOS"),
    ({"score_available_at_utc": "2026-09-30T01:15:00+00:00"}, "unavailable before decision"),
    ({"model_trained_through": "2026-09-30"}, "trained on or after decision"),
])
def test_candidate_temporal_and_oos_guards(tmp_path, override, expected):
    root = tmp_path / "observations"
    _snapshot(root)
    snapshots, _ = load_timely_snapshots(root, load_calendar(CALENDAR), now=NOW)
    with pytest.raises(ValueError, match=expected):
        load_candidates(_candidates(tmp_path / "candidates.parquet", **override),
                        load_protocol(PROTOCOL), snapshots)


def test_rejects_outcome_columns_and_missing_snapshot(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    snapshots, _ = load_timely_snapshots(root, load_calendar(CALENDAR), now=NOW)
    path = _candidates(tmp_path / "candidates.parquet")
    frame = pd.read_parquet(path)
    frame["future_return_h20"] = .1
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="Outcome-bearing"):
        load_candidates(path, load_protocol(PROTOCOL), snapshots)
    frame = frame.drop(columns="future_return_h20")
    frame["decision_date"] = "2026-10-08"
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="Missing complete timely snapshots"):
        load_candidates(path, load_protocol(PROTOCOL), snapshots)


def test_audit_refuses_overwrite(tmp_path):
    root = tmp_path / "observations"
    _snapshot(root)
    output = tmp_path / "result"
    audit(snapshot_root=root, calendar_path=CALENDAR, protocol_path=PROTOCOL,
          output=output, now=NOW)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        audit(snapshot_root=root, calendar_path=CALENDAR, protocol_path=PROTOCOL,
              output=output, now=NOW)
