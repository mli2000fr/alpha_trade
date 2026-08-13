import json

for label, path in [
    ("b25_p15_step3 (réf historique)", r"F:\projets\artifacts\backtesting\b25_p15_step3\report.json"),
    ("b25_p23_control", r"F:\projets\artifacts\backtesting\b25_p23_control\report.json"),
]:
    with open(path, encoding="utf-8") as fh:
        s = json.load(fh)["summary"]
    print(
        f"{label:<32} ret={s.get('total_return_pct'):.1f}% sharpe={s.get('sharpe_ratio'):.2f} "
        f"sortino={s.get('sortino_ratio'):.2f} dd={s.get('max_drawdown_pct'):.1f}% "
        f"pf={s.get('profit_factor'):.2f} trades={int(s.get('total_trades', 0))} pnl={s.get('pnl_net'):,.0f}"
    )
