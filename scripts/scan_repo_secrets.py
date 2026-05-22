"""Sprint S8 — Scan des secrets littéraux dans le dépôt.

Scope actuel : fichiers ``*.yaml`` / ``*.yml`` du workspace, via le scanner
canonique :func:`core.secrets.scan_repo_yaml_for_literal_secrets`.

Usage::

    python scripts/scan_repo_secrets.py
    python scripts/scan_repo_secrets.py --root . --output artifacts/secret_scan/report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "secret_scan"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "report.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)

    from core.secrets import scan_repo_yaml_for_literal_secrets

    findings = scan_repo_yaml_for_literal_secrets(args.root)
    payload = {
        "status": "fail" if findings else "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "root": str(args.root),
        "findings_count": len(findings),
        "findings": [f.to_dict() for f in findings],
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[scan_repo_secrets] rapport écrit : {args.output} (findings={len(findings)})")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

