import json, pandas as pd

# Cohérence : report.json vs trades.csv pour 2026
rep = json.loads(open("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/report.json", encoding="utf-8").read())
print("=== report.json 2026 : clés summary ===")
s = rep.get("summary", {})
for k, v in s.items():
    if isinstance(v, (int, float, str)) and not isinstance(v, bool):
        print(f"  {k}: {v}")

# chercher n_trades dans tout le report
def find(o, key, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            find(v, key, out)
    elif isinstance(o, list):
        for x in o:
            find(x, key, out)

out = []
find(rep, "n_trades", out)
find(rep, "trades", out)
print("\nn_trades trouvés:", out[:10])

tr = pd.read_csv("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/trades.csv")
print("\ntrades.csv 2026 n =", len(tr))
print("symboles uniques:", tr["symbol"].nunique())
# est-ce que chaque ligne est un trade ou y a-t-il des ré-entrées ?
print("trade_status:", tr["trade_status"].value_counts().to_dict())
print("legacy_trade_match:", tr["legacy_trade_match"].value_counts(dropna=False).to_dict())
