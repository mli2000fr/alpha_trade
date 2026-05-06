"""Sprint S25.5 — Détecte les liens markdown morts intra-repo dans `doc/`.

Sortie : ``artifacts/doc_audit/<date>/dead_links.json``.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = PROJECT_ROOT / "doc"

# Match [label](target) où target ne commence pas par http(s):// ni mailto:
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def _resolve(source: Path, target: str) -> Path:
    target = target.split("#", 1)[0]  # strip anchor
    if not target:
        return source  # lien vers une ancre interne uniquement
    if target.startswith("/"):
        return PROJECT_ROOT / target.lstrip("/")
    return (source.parent / target).resolve()


def find_dead_links(root: Path = DOC_DIR) -> list[dict]:
    dead: list[dict] = []
    for md in root.rglob("*.md"):
        try:
            text = md.read_text("utf-8")
        except Exception:
            continue
        for match in _LINK_RE.finditer(text):
            target = match.group(1).strip()
            if _is_external(target):
                continue
            resolved = _resolve(md, target)
            if not resolved.exists():
                dead.append({
                    "source": md.relative_to(PROJECT_ROOT).as_posix(),
                    "target": target,
                    "resolved": str(resolved),
                })
    return dead


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Check dead intra-repo doc links.")
    p.add_argument("--out", type=Path,
                   default=PROJECT_ROOT / "artifacts" / "doc_audit")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 si > 0 lien mort.")
    args = p.parse_args(argv)

    dead = find_dead_links()
    date_dir = args.out / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    target = date_dir / "dead_links.json"
    target.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_dead": len(dead),
        "dead_links": dead,
    }, indent=2), "utf-8")
    print(f"[doc_links] dead={len(dead)} -> {target}")
    for d in dead[:20]:
        print(f"  ! {d['source']} -> {d['target']}")
    return 1 if (args.strict and dead) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

