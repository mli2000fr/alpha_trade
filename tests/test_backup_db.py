from __future__ import annotations

import os
import time
from pathlib import Path

from scripts import backup_db as module


def test_backup_can_exclude_news_raw(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_dump(host, db, user, password, dump_path, **kwargs):
        captured.update(kwargs)
        dump_path.write_bytes(b"gzip-dump")

    monkeypatch.setattr(module, "_have_mysqldump", lambda: True)
    monkeypatch.setattr(module, "_run_mysqldump", fake_dump)
    report = module.backup_db(
        user="user", password="secret", dest_dir=tmp_path, keep=5,
        archive_prefix="alpha_trade_without_news", exclude_tables=["news_raw"],
    )

    assert report.errors == []
    assert report.exclude_tables == ["news_raw"]
    assert captured["exclude_tables"] == ["news_raw"]
    assert captured["include_tables"] == []
    assert Path(report.dump_path or "").name.startswith("alpha_trade_without_news_")


def test_backup_can_include_only_news_raw_without_routines(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_dump(host, db, user, password, dump_path, **kwargs):
        captured.update(kwargs)
        dump_path.write_bytes(b"gzip-dump")

    monkeypatch.setattr(module, "_have_mysqldump", lambda: True)
    monkeypatch.setattr(module, "_run_mysqldump", fake_dump)
    report = module.backup_db(
        user="user", password="secret", dest_dir=tmp_path, keep=3,
        archive_prefix="alpha_trade_news_raw", include_tables=["news_raw"],
        include_routines=False,
    )

    assert report.errors == []
    assert captured["include_tables"] == ["news_raw"]
    assert captured["exclude_tables"] == []
    assert captured["include_routines"] is False


def test_rotation_is_scoped_by_archive_prefix_and_keeps_exact_count(tmp_path: Path) -> None:
    for index in range(4):
        path = tmp_path / f"alpha_trade_news_raw_2026010{index}_000000.sql.gz"
        path.write_bytes(b"x")
        stamp = time.time() + index
        path.touch()
        path.chmod(0o644)
        os.utime(path, (stamp, stamp))
    unrelated = tmp_path / "alpha_trade_without_news_20260101_000000.sql.gz"
    unrelated.write_bytes(b"core")

    rotated, kept = module._rotate(
        tmp_path, archive_prefix="alpha_trade_news_raw", keep=3, dry_run=False,
    )

    assert len(rotated) == 1
    assert len(kept) == 3
    assert unrelated.exists()


def test_table_filters_are_mutually_exclusive(tmp_path: Path) -> None:
    report = module.backup_db(
        dest_dir=tmp_path, include_tables=["news_raw"], exclude_tables=["other"],
        dry_run=True,
    )
    assert any("mutuellement exclusifs" in error for error in report.errors)
