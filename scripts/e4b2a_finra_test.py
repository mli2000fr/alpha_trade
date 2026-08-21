"""E4-B2A — test d'accès FINRA Daily Short Sale Volume (1 fichier)."""
from __future__ import annotations

import requests

URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol20240102.txt"


def main() -> None:
    r = requests.get(URL, timeout=30, headers={"User-Agent": "research/1.0"})
    print("status:", r.status_code, "len:", len(r.content))
    if r.status_code == 200:
        text = r.content.decode("utf-8", errors="replace")
        lines = text.splitlines()
        print("nb lignes:", len(lines))
        print("header:", lines[0])
        for ln in lines[1:6]:
            print("  ", ln)
        # combien de symboles distincts + colonnes
        import collections
        syms = set()
        total = 0
        for ln in lines[1:]:
            parts = ln.split("|")
            if len(parts) >= 4:
                syms.add(parts[1])
                total += 1
        print(f"lignes data={total:,} symboles distincts={len(syms):,}")


if __name__ == "__main__":
    main()
