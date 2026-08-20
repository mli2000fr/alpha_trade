from pathlib import Path
import re

# 1. Chercher la config dans le log du run 2025
log = Path("artifacts/backtesting/b25_2025_rankw.log")
txt = log.read_text(encoding="utf-8", errors="replace")
print("=== log 2025 : taille", len(txt))

# chercher des traces de config
for kw in ["trailing_activation", "trailing_pct", "atr_risk_stop", "tp_atr", "tp_max",
           "max_positions", "short_selling", "sizing", "config.yaml", "launcher", "P14", "P13"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), txt)]
    if idxs:
        print(f"\n--- {kw} ({len(idxs)} occurrences) ---")
        for i in idxs[:4]:
            print("   ...", txt[max(0,i-60):i+120].replace("\n"," "))

# 2. le report.json du run 2025 (config embarquée?)
import json
rep = json.loads(open("artifacts/backtesting/b25_2025_rankw/report.json", encoding="utf-8").read())
print("\n=== report.json 2025 : clés de config ===")
def walk(o, prefix=""):
    if isinstance(o, dict):
        for k, v in o.items():
            kl = k.lower()
            if any(s in kl for s in ["config", "param", "trailing", "stop", "tp", "atr", "position", "leverage", "capital"]):
                if isinstance(v, (int, float, str, bool)):
                    print(f"  {prefix}{k}: {v}")
                else:
                    print(f"  {prefix}{k}: ({type(v).__name__})")
            elif isinstance(v, dict) and len(prefix) < 40:
                walk(v, prefix + k + ".")
walk(rep)
