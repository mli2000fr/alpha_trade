from pathlib import Path
import re, json

# chercher la commande CLI exacte dans les logs du run prodparity 2026
for name in ["artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/_console.log",
             "artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/compare_to_live_summary.md"]:
    p = Path(name)
    print(f"=== {name} ===")
    if p.exists():
        txt = p.read_text(encoding="utf-8", errors="replace")
        # chercher des commandes
        for m in re.finditer(r"(python\S*\s+-m\s+backtesting[^\n]*|backtesting\s+run[^\n]*)", txt):
            print("  CMD:", m.group(0)[:300])
        # chercher les flags
        for kw in ["--atr-risk-stop", "--tp-atr", "--tp-max", "--max-positions", "--sizing", "--intrabar", "--atr-ts"]:
            for m in re.finditer(re.escape(kw) + r"[^\s]*", txt):
                print("  FLAG:", m.group(0)[:100])
                break
    else:
        print("  absent")
    print()
