"""Analyse les fichiers txt de Downloads : dates couvertes + nb lignes."""
from __future__ import annotations

from pathlib import Path

DL = Path("c:/Users/PC ming/Downloads")


def main() -> None:
    txts = sorted(DL.glob("*.txt"))
    print("fichiers .txt dans Downloads:", len(txts))
    for f in txts:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:  # noqa: BLE001
            print("  ERR", f.name, e)
            continue
        dates = set()
        ncols_ok = 0
        for ln in lines:
            parts = ln.split("|")
            if len(parts) >= 5 and len(parts[0]) == 8 and parts[0].isdigit():
                dates.add(parts[0])
                ncols_ok += 1
        dmin = min(dates) if dates else "-"
        dmax = max(dates) if dates else "-"
        print(f"  {f.name}: {len(lines):,} lignes | {len(dates)} dates | {dmin} -> {dmax} | lignes OK {ncols_ok:,}")


if __name__ == "__main__":
    main()
