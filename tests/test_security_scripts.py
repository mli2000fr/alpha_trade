"""Phase C / S18.6 — Tests SBOM + scan CVE (mode fallback)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_generate_sbom_fallback(tmp_path):
    out = tmp_path / "sbom.cdx.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_sbom.py"),
         "--output", str(out), "--fallback-only"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["bomFormat"] == "CycloneDX"
    assert data["specVersion"] == "1.5"
    assert isinstance(data["components"], list)
    assert len(data["components"]) > 0


def test_scan_cves_runs(tmp_path):
    out = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "scan_cves.py"),
         "--output", str(out)],
        capture_output=True, text=True,
    )
    # Code 0 si pas de critique (ou pip-audit absent → skipped)
    assert proc.returncode in (0, 1)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "timestamp" in data

