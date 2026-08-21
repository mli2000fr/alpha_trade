from pathlib import Path

log = Path("artifacts/backtesting/cmp_b25_h20_2025_postfix_tp_m8.log")
raw = log.read_bytes()
print("taille:", len(raw))
print("== premiers octets ==")
print(raw[:200])
print("== derniers 200 octets ==")
print(raw[-200:])
# chercher "PnL Net" en bytes
import re
hits = [m.start() for m in re.finditer(b"PnL Net", raw)]
print("occurrences 'PnL Net' (bytes):", len(hits), hits[:5])
if hits:
    print("contexte:", raw[hits[0]-50:hits[0]+60])
