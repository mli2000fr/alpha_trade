"""Sprint S24.4 — Tests unitaires loaders compliance."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ihm.services import compliance_loader


@pytest.fixture
def fake_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(compliance_loader, "ARTIFACTS", tmp_path)
    return tmp_path


def test_load_dr_drill_status_empty(fake_artifacts: Path) -> None:
    payload = compliance_loader.load_dr_drill_status()
    assert payload["ok"] is None
    assert payload["last_date"] is None


def test_load_dr_drill_status_reads_latest(fake_artifacts: Path) -> None:
    folder = fake_artifacts / "dr_drill" / "2026-05-01"
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(
        json.dumps({"ok": True, "rto_minutes": 28, "rpo_minutes": 5}), "utf-8",
    )
    folder2 = fake_artifacts / "dr_drill" / "2026-05-03"
    folder2.mkdir(parents=True)
    (folder2 / "result.json").write_text(
        json.dumps({"ok": False, "rto_minutes": 99}), "utf-8",
    )
    payload = compliance_loader.load_dr_drill_status()
    assert payload["last_date"] == "2026-05-03"
    assert payload["ok"] is False
    assert payload["rto_minutes"] == 99


def test_load_cve_status(fake_artifacts: Path) -> None:
    sbom = fake_artifacts / "sbom"
    sbom.mkdir(parents=True)
    (sbom / "cve_scan_latest.json").write_text(
        json.dumps({"critical": 0, "high": 2, "scanned_at": "2026-05-06"}),
        "utf-8",
    )
    payload = compliance_loader.load_cve_status()
    assert payload["critical"] == 0
    assert payload["high"] == 2


def test_load_tlaps_status(fake_artifacts: Path) -> None:
    folder = fake_artifacts / "formal_runs" / "2026-05-06"
    folder.mkdir(parents=True)
    (folder / "tlaps.json").write_text(
        json.dumps({"n_ok": 3, "n_specs": 3, "n_failed": 0,
                    "tool": "tlaps"}),
        "utf-8",
    )
    payload = compliance_loader.load_tlaps_status()
    assert payload["n_ok"] == 3
    assert payload["tool"] == "tlaps"
    assert payload["date"] == "2026-05-06"


def test_load_fuzz_status(fake_artifacts: Path) -> None:
    folder = fake_artifacts / "fuzz_runs" / "2026-05-06"
    folder.mkdir(parents=True)
    (folder / "diff.json").write_text(
        json.dumps({
            "n_scenarios": 10000, "n_diverged": 0,
            "summary": {"divergence_rate": 0.0, "max_pnl_delta_usd": 0.0},
        }),
        "utf-8",
    )
    payload = compliance_loader.load_fuzz_status()
    assert payload["n_scenarios"] == 10000
    assert payload["n_diverged"] == 0
    assert payload["divergence_rate"] == 0.0


def test_load_full_snapshot_keys(fake_artifacts: Path) -> None:
    snap = compliance_loader.load_full_snapshot()
    assert set(snap.keys()) == {
        "hmac_chain", "dr_drill", "cve", "coverage",
        "mutation", "tlaps", "fuzz", "sandbox",
    }

