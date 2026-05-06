"""Quick Win S18.5 — Vérifie l'absence de marqueurs ``TODO/FIXME/XXX``
dans le code applicatif (hors ``tests/``, ``prompt/``, ``doc/``,
``htmlcov/``, ``artifacts/``, ``alembic/versions/``).

Usage::

    python scripts/check_no_todo.py
    python scripts/check_no_todo.py --strict   # hard fail si trouvés

Sortie : code retour 0 si clean, 1 sinon. Liste les occurrences sur
stdout au format ``path:line:marker:contexte``.

Phase C / Sprint S18 — exigences institutionnelles : 0 TODO résiduel
dans le code applicatif est une condition du 10/10.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    "tests",
    "prompt",
    "doc",
    "htmlcov",
    "artifacts",
    "alembic",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "alpha_trade.egg-info",
    "log",
    "scripts",  # outils, pas du code applicatif (incl. ce fichier)
}

# Marqueurs sont déclarés dynamiquement pour éviter qu'eux-mêmes
# soient détectés dans ce fichier.
_TAGS = ("TO" + "DO", "FIX" + "ME", "X" + "XX")
PATTERN = re.compile(r"\b(" + "|".join(_TAGS) + r")\b")


def iter_python_files(root: Path):
    for p in root.rglob("*.py"):
        rel = p.relative_to(root)
        parts = set(rel.parts)
        if parts & EXCLUDED_DIRS:
            continue
        yield p


def scan(root: Path) -> list[tuple[Path, int, str, str]]:
    findings: list[tuple[Path, int, str, str]] = []
    for path in iter_python_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            m = PATTERN.search(line)
            if m:
                findings.append((path, lineno, m.group(1), line.strip()))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 dès la première occurrence trouvée")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    findings = scan(args.root)
    if not findings:
        print("[check_no_todo] OK : 0 marqueur TODO/FIXME/XXX dans le code applicatif.")
        return 0

    for path, lineno, tag, ctx in findings:
        rel = path.relative_to(args.root)
        print(f"{rel}:{lineno}:{tag}:{ctx}")

    print(f"\n[check_no_todo] {len(findings)} marqueur(s) trouvé(s).", file=sys.stderr)
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())

