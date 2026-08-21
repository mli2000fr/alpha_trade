import re
from pathlib import Path

log = Path("artifacts/backtesting/cmp_b25_h20_2025_postfix_tp_m8.log")
txt = log.read_text(encoding="utf-8", errors="replace")

patterns = {
    "ret": r"PnL Net\s+\$([\d,\.\-]+)",
    "pf": r"Profit Factor\s+([\d\.]+)",
    "dd": r"Max Drawdown\s+([\d\.]+)",
    "trades": r"Nombre de trades\s+([\d]+)",
    "win": r"Win Rate\s+([\d\.]+)",
    "long": r"Trades Long\s+\d+\s+\(WR: [\d\.]+\%, PnL: \$([\d,\.\-]+)",
    "short": r"Trades Short\s+\d+\s+\(WR: [\d\.]+\%, PnL: \$([\d,\.\-]+)",
}
for k, pat in patterns.items():
    m = re.search(pat, txt)
    print(f"{k}: {m.group(1) if m else 'NO MATCH'}   [{pat}]")
