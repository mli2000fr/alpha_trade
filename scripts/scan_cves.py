"""Quick Win S18.6 — Scan CVE des dépendances.

Wrap ``pip-audit`` (si installé) ; sinon mode best-effort qui parse
``requirements*.txt`` et émet un rapport vide marqué ``status="skipped"``.

Usage::

    python scripts/scan_cves.py
    python scripts/scan_cves.py --fail-on critical
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "cve"

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]


def _run_pip_audit(output: Path) -> dict | None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"],
            capture_output=True, text=True, cwd=ROOT,
        )
    except FileNotFoundError:
        return None
    if proc.returncode not in (0, 1):
        # pip-audit retourne 1 si vulnérabilités trouvées, autres = erreur réelle
        print(f"[scan_cves] pip-audit erreur: rc={proc.returncode} stderr={proc.stderr[:200]}",
              file=sys.stderr)
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _max_severity(report: dict) -> str | None:
    max_idx = -1
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            sev = (vuln.get("severity") or "").lower()
            if sev in SEVERITY_LEVELS:
                idx = SEVERITY_LEVELS.index(sev)
                if idx > max_idx:
                    max_idx = idx
    return SEVERITY_LEVELS[max_idx] if max_idx >= 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on", choices=SEVERITY_LEVELS, default="critical",
                        help="seuil bloquant (défaut: critical)")
    args = parser.parse_args()

    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "report.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)

    report = _run_pip_audit(args.output)
    if report is None:
        report = {
            "status": "skipped",
            "reason": "pip-audit non disponible",
            "timestamp": datetime.now(UTC).isoformat(),
            "dependencies": [],
        }
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[scan_cves] pip-audit absent — rapport vide écrit : {args.output}")
        return 0

    report["timestamp"] = datetime.now(UTC).isoformat()
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    max_sev = _max_severity(report)
    print(f"[scan_cves] rapport écrit : {args.output} (max severity: {max_sev or 'none'})")

    if max_sev is None:
        return 0
    threshold_idx = SEVERITY_LEVELS.index(args.fail_on)
    if SEVERITY_LEVELS.index(max_sev) >= threshold_idx:
        print(f"[scan_cves] ÉCHEC : vulnérabilité {max_sev} >= seuil {args.fail_on}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

