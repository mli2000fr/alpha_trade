"""Safety contract for insert-only CN 2026 catch-up."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from dataIntegrityEngine import cn_sprint7c_incremental as runner
from service.market.cn_canonicalizer import (
    _incremental_insert_sql, _incremental_timestamps, promote_pilot,
)
from service.market.cn_canonical_full import enrich_manifest
from service.baostock.client import BaoStockError
from service.market.cn_completed_session_guard import require_completed_session_end


def test_date_guard_rejects_historical_and_unfinished_cn_day():
    with pytest.raises(ValueError, match="2026-or-later"):
        runner.verify_bounds(date(2025, 12, 31), date(2026, 1, 2))
    with pytest.raises(ValueError, match="completed CN sessions"):
        runner.verify_bounds(date(2026, 1, 1), datetime.now(runner.ZoneInfo("Asia/Shanghai")).date())


def test_same_day_requires_explicit_flag_and_shanghai_close():
    shanghai = runner.ZoneInfo("Asia/Shanghai")
    day = date(2026, 9, 30)
    with pytest.raises(ValueError, match="completed CN sessions"):
        require_completed_session_end(day, now=datetime(2026, 9, 30, 18, 1, tzinfo=shanghai))
    with pytest.raises(ValueError, match="18:00"):
        require_completed_session_end(day, allow_same_day_after_close=True,
                                      now=datetime(2026, 9, 30, 17, 59, tzinfo=shanghai))
    require_completed_session_end(day, allow_same_day_after_close=True,
                                  now=datetime(2026, 9, 30, 18, 0, tzinfo=shanghai))
    with pytest.raises(ValueError, match="Future CN session"):
        require_completed_session_end(date(2026, 10, 1), allow_same_day_after_close=True,
                                      now=datetime(2026, 9, 30, 20, 0, tzinfo=shanghai))


def test_atomic_state_retries_transient_windows_access_denied(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"old": true}', encoding="utf-8")
    original_replace = Path.replace
    attempts = []
    sleeps = []

    def sometimes_denied(source, target):
        attempts.append(source)
        if len(attempts) < 3:
            raise PermissionError("Windows destination temporarily in use")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", sometimes_denied)
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    runner._atomic_state(path, {"new": True})
    assert len(attempts) == 3
    assert sleeps == [0.1, 0.2]
    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}


def test_incremental_insert_removes_upsert_and_retains_values():
    sql = _incremental_insert_sql(
        "INSERT INTO stock_bars_daily(x) VALUES (:x) ON DUPLICATE KEY UPDATE x=VALUES(x)"
    )
    assert sql == "INSERT IGNORE INTO stock_bars_daily(x) VALUES (:x)"
    with pytest.raises(ValueError, match="Expected canonical INSERT"):
        _incremental_insert_sql("UPDATE stock_bars_daily SET x=1")


def test_backfilled_bar_is_available_when_actually_observed():
    observed = datetime(2026, 9, 30, 5, 0, tzinfo=timezone.utc)
    seen, available = _incremental_timestamps(
        {"observed_at": observed, "available_at": observed}, date(2026, 9, 29)
    )
    assert seen == observed.replace(tzinfo=None)
    assert available == seen
    assert available > datetime(2026, 9, 29, 7, 0)


def test_prepare_existing_manifest_fails_before_collect(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("sh.600519", encoding="utf-8")
    monkeypatch.setattr(runner, "collect", lambda *_args, **_kwargs: pytest.fail("collect called"))
    with pytest.raises(FileExistsError, match="refuse overwrite"):
        runner.prepare(object(), start=date(2026, 1, 1), end=date(2026, 9, 29),
                       manifest=manifest, chunks_root=tmp_path / "chunks",
                       chunk_size=25, seed_manifest=manifest)


def test_incremental_canonicalizers_refuse_us_database(tmp_path):
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("sh.600519", encoding="utf-8")
    engine = SimpleNamespace(url=SimpleNamespace(database="alpha_trade"))
    with pytest.raises(RuntimeError, match="outside alpha_trade_cn"):
        promote_pilot(engine, manifest_path=manifest,
                      business_start_date=date(2026, 1, 1), business_end_date=date(2026, 9, 29))
    with pytest.raises(RuntimeError, match="outside alpha_trade_cn"):
        enrich_manifest(engine, manifest_path=manifest,
                        business_start_date=date(2026, 1, 1), business_end_date=date(2026, 9, 29))


def test_run_all_state_is_resumable_without_duplicate_chunk(monkeypatch, tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "chunk_0000.txt").write_text("sh.600519", encoding="utf-8")
    (chunks / "index.json").write_text(json.dumps({
        "chunk_count": 1, "chunks": ["chunk_0000.txt"],
    }), encoding="utf-8")
    calls = []
    def fake_run_chunk(_engine, *, start, end, manifest):
        calls.append((start, end, manifest.name))
        return {"status": "COMPLETED", "symbols": 1}
    monkeypatch.setattr(runner, "run_chunk", fake_run_chunk)
    options = {"start": date(2026, 1, 1), "end": date(2026, 9, 29),
               "chunks_root": chunks, "output_root": tmp_path / "output"}
    first = runner.run_all(object(), **options)
    second = runner.run_all(object(), **options)
    assert first["completed_chunks"] == second["completed_chunks"] == 1
    assert calls == [(options["start"], options["end"], "chunk_0000.txt")]
    state = json.loads((tmp_path / "output" / "state.json").read_text(encoding="utf-8"))
    assert state["chunks"]["0"]["status"] == "COMPLETED"


def test_collect_retries_transient_baostock_login_only(monkeypatch, tmp_path):
    calls = []
    sleeps = []
    def fake_collect(*_args, **_kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise UnicodeEncodeError("charmap", "服务器连接失败", 0, 1, "undefined")
        return {"requested": 2, "failed": 0}
    monkeypatch.setattr(runner, "collect", fake_collect)
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    result = runner._collect_chunk_with_network_retry(
        object(), start=date(2026, 1, 1), end=date(2026, 9, 29),
        manifest=tmp_path / "chunk.txt",
    )
    assert result["failed"] == 0
    assert len(calls) == 3
    assert sleeps == [15, 30]


def test_collect_retries_baostock_login_error_wrapped_by_cp1252(monkeypatch, tmp_path):
    calls = []
    sleeps = []

    def fake_collect(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 1:
            try:
                try:
                    raise ConnectionRefusedError(10061, "BaoStock connection refused")
                except ConnectionRefusedError:
                    raise UnicodeEncodeError("charmap", "服务器连接失败", 0, 1, "undefined")
            except UnicodeEncodeError as exc:
                raise BaoStockError("BaoStock adj_factor en échec: charmap") from exc
        return {"requested": 2, "failed": 0}

    monkeypatch.setattr(runner, "collect", fake_collect)
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    result = runner._collect_chunk_with_network_retry(
        object(), start=date(2026, 1, 1), end=date(2026, 9, 29),
        manifest=tmp_path / "chunk.txt",
    )
    assert result["failed"] == 0
    assert len(calls) == 2
    assert sleeps == [15]


def test_collect_does_not_retry_permanent_baostock_schema_error(monkeypatch, tmp_path):
    calls = []
    def fake_collect(*_args, **_kwargs):
        calls.append(1)
        raise BaoStockError("Schéma BaoStock incompatible pour daily")
    monkeypatch.setattr(runner, "collect", fake_collect)
    monkeypatch.setattr(runner.time, "sleep", lambda _: pytest.fail("unexpected retry"))
    with pytest.raises(BaoStockError, match="Schéma"):
        runner._collect_chunk_with_network_retry(
            object(), start=date(2026, 1, 1), end=date(2026, 9, 29),
            manifest=tmp_path / "chunk.txt",
        )
    assert len(calls) == 1
