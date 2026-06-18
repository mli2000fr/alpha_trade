"""Compare two backtest runs."""
import json, pandas as pd

BASE = "f:/projets/artifacts/ihm_backtesting_runs/run"

def analyze(run_id):
    b = f"{BASE}/{run_id}/artifacts"
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

    days_below = (vals < 2000).mean() * 100

    try:
        with open(f"{b}/report.json") as f:
            r = json.load(f)
        s = r["summary"]
        d = r["diagnostics"]
        trades = s["total_trades"]
        pf = s["profit_factor"]
        wr = s["win_rate_pct"]
        tp = d["take_profit_exits"]
        ts = d["trailing_stop_exits"]
        tst = d["time_stop_exits"]
        bcr = d.get("blocked_by_regime", 0)
        bcb = d.get("blocked_by_breakout", 0)
    except Exception:
        trades = None; pf = None; wr = None; tp = None; ts = None; tst = None; bcr = None; bcb = None

    eq["trade_date"] = pd.to_datetime(eq["trade_date"])
    eq["year"] = eq["trade_date"].dt.year
    years = {}
    for y, grp in eq.groupby("year"):
        yr = (grp["portfolio_value"].iloc[-1] / grp["portfolio_value"].iloc[0] - 1) * 100
        years[y] = yr

    return {
        "final": final, "ret": ret, "cagr": cagr, "max_dd": max_dd,
        "below": days_below, "trades": trades, "pf": pf, "wr": wr,
        "tp": tp, "ts": ts, "tst": tst, "bcr": bcr, "bcb": bcb,
        "years": years,
    }

prev = analyze("20260618_071638_7878deed")
curr = analyze("20260618_105139_2062ca08")

print(f"{'Metrique':<25} {'Avant (7878)':<20} {'Apres (2062)':<20} {'Delta':<10}")
print("-" * 75)

def fmt_val(v, template):
    if v is None:
        return "N/A"
    return template.format(v)

keys = [
    ("Final value", "final", "${:.0f}"),
    ("Total return", "ret", "{:.1f}%"),
    ("CAGR", "cagr", "{:.1f}%"),
    ("Max DD", "max_dd", "{:.1f}%"),
    ("Days < 2000", "below", "{:.0f}%"),
    ("Total trades", "trades", "{}"),
    ("Profit factor", "pf", "{:.3f}"),
    ("Win rate", "wr", "{:.1f}%"),
    ("Take profit exits", "tp", "{}"),
    ("Trailing stop exits", "ts", "{}"),
    ("Time stop exits", "tst", "{}"),
    ("Blocked by regime", "bcr", "{}"),
    ("Blocked by breakout", "bcb", "{}"),
]

for label, key, tmpl in keys:
    pv = prev[key]
    cv = curr[key]
    if isinstance(pv, (int, float)) and isinstance(cv, (int, float)):
        delta = cv - pv
        if key in ("ret", "cagr", "max_dd", "below", "wr"):
            ds = f"{delta:+.1f}pp"
        elif key in ("trades", "tp", "ts", "tst", "bcr", "bcb"):
            ds = f"{delta:+.0f}"
        else:
            ds = f"{delta:+.3f}"
    else:
        ds = "-"
    print(f"{label:<25} {fmt_val(pv, tmpl):<20} {fmt_val(cv, tmpl):<20} {ds:<10}")

print()
print("=== YEARLY ===")
print(f"{'Year':<8} {'Avant':<12} {'Apres':<12} {'Delta':<10}")
for y in sorted(set(list(prev["years"].keys()) + list(curr["years"].keys()))):
    py = prev["years"].get(y)
    cy = curr["years"].get(y)
    if py is not None and cy is not None:
        d = cy - py
        print(f"{y:<8} {py:+6.1f}%     {cy:+6.1f}%     {d:+6.1f}pp")
    elif py is not None:
        print(f"{y:<8} {py:+6.1f}%     {'N/A':<12}")
    else:
        print(f"{y:<8} {'N/A':<12} {cy:+6.1f}%")
