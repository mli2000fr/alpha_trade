"""Quick Win S18.6 — Génère un SBOM CycloneDX du projet.

Wrapper minimal autour de ``cyclonedx-bom`` (optionnel). Si la
dépendance n'est pas installée, génère un SBOM CycloneDX minimal en
pur Python depuis ``requirements.txt`` + ``pyproject.toml`` (mode
fallback déterministe pour CI sans réseau).

Usage::

    python scripts/generate_sbom.py
    python scripts/generate_sbom.py --output artifacts/sbom/2026-05-06/sbom.cdx.json

Phase C / S18.6.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "sbom"


def _parse_requirements(path: Path) -> list[tuple[str, str | None]]:
    items: list[tuple[str, str | None]] = []
    if not path.exists():
        return items
    pat = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)\s*([<>=!~]=?)?\s*([0-9A-Za-z.\-]+)?")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-r") or line.startswith("--"):
            continue
        m = pat.match(line)
        if not m:
            continue
        name = m.group(1).split("[")[0]
        version = m.group(3)
        items.append((name, version))
    return items


def _fallback_sbom(root: Path) -> dict:
    components = []
    seen: set[str] = set()
    for req in (root / "requirements.txt", root / "requirements-dev.txt"):
        for name, version in _parse_requirements(req):
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            comp = {
                "type": "library",
                "name": name,
                "purl": f"pkg:pypi/{name}" + (f"@{version}" if version else ""),
            }
            if version:
                comp["version"] = version
            components.append(comp)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": f"urn:uuid:alpha-trade-{datetime.now(UTC).isoformat()}",
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "tools": [{"name": "alpha_trade.scripts.generate_sbom", "version": "fallback"}],
            "component": {
                "type": "application",
                "name": "alpha_trade",
                "version": "0.1.0",
            },
        },
        "components": components,
    }


def _try_cyclonedx(output: Path) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "cyclonedx_py", "environment",
             "--output-format", "JSON", "--outfile", str(output)],
            check=True, cwd=ROOT,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="chemin du SBOM (défaut: artifacts/sbom/<date>/sbom.cdx.json)")
    parser.add_argument("--fallback-only", action="store_true",
                        help="ignore cyclonedx-bom et utilise le générateur interne")
    args = parser.parse_args()

    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "sbom.cdx.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.fallback_only and _try_cyclonedx(args.output):
        print(f"[sbom] CycloneDX généré via cyclonedx-bom : {args.output}")
        return 0

    sbom = _fallback_sbom(ROOT)
    args.output.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    print(f"[sbom] fallback CycloneDX écrit ({len(sbom['components'])} composants) : {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

