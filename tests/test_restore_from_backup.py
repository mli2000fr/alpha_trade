"""Sprint S12.1 — Tests du CLI ``scripts/restore_from_backup.py``."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import restore_from_backup as rfb


def test_dry_run_produces_report(tmp_path: Path, monkeypatch):
    # Pas de dump → erreur attendue mais le mode dry_run court-circuite la lecture.
    dump = tmp_path / "fake.sql.gz"
    dump.write_bytes(b"")  # exists pour passer la check
    rep = rfb.restore(
        dump_path=dump,
        target_host="localhost",
        target_db="alpha_trade",
        user="u", password="p",
        dry_run=True,
    )
    assert rep.dry_run is True
    assert rep.dump_loaded is False
    assert rep.errors == []


def test_dump_age_returns_none_for_missing_file(tmp_path: Path):
    assert rfb._detect_dump_age_seconds(tmp_path / "nope.sql") is None


def test_main_outputs_json(tmp_path, monkeypatch, capsys):
    dump = tmp_path / "fake.sql"
    dump.write_text("-- empty")
    rc = rfb.main([
        "--dump-path", str(dump),
        "--target-host", "localhost",
        "--target-db", "alpha_trade",
        "--dry-run",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["target_db"] == "alpha_trade"

