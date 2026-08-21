from pathlib import Path
import re

log = Path("artifacts/backtesting/b25_2025_rankw.log")
txt = log.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
print("=== 40 premières lignes ===")
for l in lines[:40]:
    print(l[:200])
