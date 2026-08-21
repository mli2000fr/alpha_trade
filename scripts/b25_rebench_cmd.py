from pathlib import Path

p = Path("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/_console.log")
txt = p.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
print("=== ligne 0 (CMD) ===")
print(lines[0])
print()
print("=== lignes 1-2 ===")
for l in lines[1:3]:
    print(l[:500])
print()
# aussi chercher le log du run 2025 prodparity si disponible
for cand in [
    "artifacts/backtesting/cmp_b25_h20_2025_prodparity_p23_m8/compare_to_live_summary.md",
]:
    c = Path(cand)
    if c.exists():
        print(f"=== {cand} ===")
        print(c.read_text(encoding="utf-8", errors="replace")[:500])
