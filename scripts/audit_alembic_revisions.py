"""Audite la cohérence revision/down_revision de toutes les migrations alembic."""
from __future__ import annotations

import re
from pathlib import Path

files = sorted(Path("alembic/versions").glob("*.py"))
rev_map: dict[str, Path] = {}
missing: list[tuple[str, str, str]] = []  # (fichier, revision, down_revision)
dupes: list[str] = []

for f in files:
    txt = f.read_text(encoding="utf-8")
    m = re.search(r'^revision(?:_id)?\s*=\s*"([^"]+)"', txt, re.M)
    d = re.search(r'^down_revision\s*=\s*"([^"]+)"', txt, re.M)
    rev = m.group(1) if m else None
    down = d.group(1) if d else None
    if rev is None:
        print(f"[NO-REV] {f.name}")
        continue
    if rev in rev_map:
        dupes.append(rev)
    rev_map[rev] = f
    if down and down not in rev_map and down not in {r for r in rev_map}:
        # down peut être défini avant ; on vérifie après le scan
        missing.append((f.name, rev, down))
    print(f"{f.name}: rev={rev}  down={down}")

print("\n=== down_revision absents ===")
# re-vérifier après scan complet
for f in files:
    txt = f.read_text(encoding="utf-8")
    m = re.search(r'^revision(?:_id)?\s*=\s*"([^"]+)"', txt, re.M)
    d = re.search(r'^down_revision\s*=\s*"([^"]+)"', txt, re.M)
    if not m:
        continue
    rev = m.group(1)
    down = d.group(1) if d else None
    if down and down not in rev_map:
        print(f"  {f.name}: down_revision={down!r} ABSENT du map")

print("=== dups ===", dupes)
