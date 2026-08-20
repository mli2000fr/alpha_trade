import json

rep = json.loads(open("artifacts/backtesting/b25_2025_rankw/report.json", encoding="utf-8").read())
params = rep.get("params", {})
print("=== params 2025 (config du run) ===")
print(json.dumps(params, indent=1, default=str)[:4000])
