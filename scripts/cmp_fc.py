"""Compare FC 100% vs FC 50%."""
import json, pandas as pd

BASE = "f:/projets/artifacts/ihm_backtesting_runs/run"

def analyze(rid):
    b = f"{BASE}/{rid}/artifacts"
    eq = pd.read_csv(f"{b}/equity_curve.csv")
    vals = eq["portfolio_value"].values
    final = float(vals[-1])
    start = float(vals[0])
    ret = (final / start - 1) * 100
    cagr = ((final / start) ** (1 / 6) - 1) * 100
    peak = vals[0]
    max_dd = 0.0
    for v in vals:
        if v > peak:
            peak = v
        dd = (v / peak - 1) * 100
        if dd < max_dd:
            max_dd = dd
    below = (vals < 2000).mean() * 100

    try:
        with open(f"{b}/report.json") as f:
            r = json.load(f)
        s = r["summary"]
        d = r["diagnostics"]
        return {
            "final": final, "ret": ret, "cagr": cagr, "max_dd": max_dd,
            "below": below, "trades": s["total_trades"], "pf": s["profit_factor"],
            "wr": s["win_rate_pct"], "tp": d["take_profit_exits"],
            "ts": d["trailing_stop_exits"], "tst": d["time_stop_exits"],
            "bcr": d.get("blocked_by_regime", 0),
        }
    except Exception:
        return {
            "final": final, "ret": ret, "cagr": cagr, "max_dd": max_dd,
            "below": below, "trades": "?", "pf": "?", "wr": "?",
            "tp": "?", "ts": "?", "tst": "?", "bcr": "?",
        }

fc100 = analyze("20260618_105139_2062ca08")
fc50 = analyze("20260618_122252_2833fff9")

print(f"{'Metrique':<22} {'FC 100%':<15} {'FC 50%':<15} {'Delta':<10}")
print("-" * 62)

keys = [
    ("Final", "final", "${:.0f}"),
    ("Return", "ret", "{:.1f}%"),
    ("CAGR", "cagr", "{:.1f}%"),
    ("Max DD", "max_dd", "{:.1f}%"),
    ("Days < 2000", "below", "{:.0f}%"),
    ("Trades", "trades", "{}"),
    ("Profit factor", "pf", "{:.3f}"),
    ("Win rate", "wr", "{:.1f}%"),
    ("TP exits", "tp", "{}"),
    ("TS exits", "ts", "{}"),
    ("Time exits", "tst", "{}"),
]

for label, key, fmt in keys:
    p = fc100[key]
    c = fc50[key]
    if isinstance(p, (int, float)) and isinstance(c, (int, float)):
        d = c - p
        if key in ("ret", "cagr", "max_dd", "below", "wr"):
            ds = f"{d:+.1f}pp"
        elif key in ("trades", "tp", "ts", "tst", "bcr"):
            ds = f"{d:+.0f}"
        else:
            ds = f"{d:+.3f}"
    else:
        ds = "-"
    print(f"{label:<22} {fmt.format(p):<15} {fmt.format(c):<15} {ds:<10}")
