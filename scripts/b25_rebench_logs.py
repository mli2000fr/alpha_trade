from pathlib import Path
import re

# chercher dans les logs le contenu affichant les params/flags
for logp in [
    "artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/_console.log",
    "artifacts/benchmarks/OOS2026_B25_P14_m8_v1/_console.log",
    "logs/ab_prodparity_2026_baseline_console.log",
]:
    p = Path(logp)
    print(f"=== {logp} : exists={p.exists()} ===")
    if p.exists():
        txt = p.read_text(encoding="utf-8", errors="replace")
        lines = txt.splitlines()
        print(f"  lignes: {len(lines)}")
        # afficher les lignes avec des mots cles de config
        for i, l in enumerate(lines[:60]):
            if any(k in l for k in ["Backtest Alpha", "TP=", "TS=", "max_positions",
                                     "trailing", "best_horizon", "atr", "tp_atr", "preset",
                                     "engine_mode", "phase", "capital=", "protection"]):
                print(f"  [{i}] {l[:180]}")
    print()
