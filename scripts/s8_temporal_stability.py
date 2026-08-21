"""S8.2b — Stabilité temporelle de oracle_edge sur les trades B25 exécutés.

Découpe les 237 trades B25 par période (2025, 2026 H1, trimestres) et vérifie que
la relation « oracle_edge faible → trade moins bon » est stable dans le temps.

Question testée : est-ce que les trades à faible oracle_edge sont systématiquement
moins bons que ceux à oracle_edge élevé, quelle que soit la période ?
"""
import pandas as pd
from scipy.stats import spearmanr

CSV = r"F:\projets\scripts\s8_trades_with_oracle.csv"


def q_stats(g: pd.DataFrame) -> dict:
    n = len(g)
    if n == 0:
        return {"n": 0, "wr": float("nan"), "pf": float("nan"), "avg_ret": float("nan"), "pnl": 0.0}
    wins = g[g["ret"] > 0]
    gl = -g[g["ret"] <= 0]["pnl"].sum()
    pf = wins["pnl"].sum() / gl if gl > 0 else float("inf")
    return {"n": n, "wr": round(100*len(wins)/n, 1),
            "pf": round(pf, 2) if pf != float("inf") else "inf",
            "avg_ret": round(100*g["ret"].mean(), 2), "pnl": round(g["pnl"].sum(), 0)}


def period_report(df: pd.DataFrame, label: str, edge_col: str = "oracle_edge", ret_col: str = "ret") -> None:
    sub = df.dropna(subset=[edge_col, ret_col]).copy()
    n = len(sub)
    if n < 15:
        print(f"\n### {label}: n={n} (trop peu pour quintiles fiables)")
        return
    sub["q"] = pd.qcut(sub[edge_col], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    rho, p = spearmanr(sub[edge_col], sub[ret_col])
    # PF spread bas vs haut (Q1-Q2 vs Q3-Q5)
    lo = sub[sub["q"].isin(["Q1", "Q2"])]
    hi = sub[sub["q"].isin(["Q3", "Q4", "Q5"])]
    lo_s = q_stats(lo)
    hi_s = q_stats(hi)
    print(f"\n### {label}  (n={n})  Spearman rho={rho:+.3f} p={p:.3g}")
    print(f"    {'Q':<4}{'n':>4}{'WR%':>7}{'PF':>7}{'avgRet%':>9}{'PnL':>8}")
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        s = q_stats(sub[sub["q"] == q])
        print(f"    {q:<4}{s['n']:>4}{s['wr']:>7}{str(s['pf']):>7}{s['avg_ret']:>9}{s['pnl']:>8}")
    print(f"    → Q1-Q2 (edge bas) : PF={lo_s['pf']} / WR={lo_s['wr']}% / avgRet={lo_s['avg_ret']}%  "
          f"vs  Q3-Q5 (edge haut) : PF={hi_s['pf']} / WR={hi_s['wr']}% / avgRet={hi_s['avg_ret']}%")


def main() -> None:
    df = pd.read_csv(CSV)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df["ret"] = df["ret"].astype(float)
    df["oracle_edge"] = df["oracle_edge"].astype(float)
    print(f"Total trades B25 avec oracle_edge : {len(df)}")
    print(f"Répartition par année : {df['signal_date'].dt.year.value_counts().sort_index().to_dict()}")

    # Périodes
    periods = {
        "2025 (toute)": (df["signal_date"] >= "2025-01-01") & (df["signal_date"] <= "2025-12-31"),
        "2026 H1": (df["signal_date"] >= "2026-01-01") & (df["signal_date"] <= "2026-05-31"),
        "2025 H1": (df["signal_date"] >= "2025-01-01") & (df["signal_date"] <= "2025-06-30"),
        "2025 H2": (df["signal_date"] >= "2025-07-01") & (df["signal_date"] <= "2025-12-31"),
        "2026 Q1": (df["signal_date"] >= "2026-01-01") & (df["signal_date"] <= "2026-03-31"),
        "2026 Q2": (df["signal_date"] >= "2026-04-01") & (df["signal_date"] <= "2026-05-31"),
    }
    print("\n" + "=" * 96)
    print("S8.2b — Stabilité temporelle : oracle_edge quintiles × période")
    print("=" * 96)
    for label, mask in periods.items():
        period_report(df[mask], label)

    # vue compacte : pour chaque période, rho + PF spread
    print("\n" + "=" * 96)
    print("Vue compacte : rho et écart PF (Q3-Q5 vs Q1-Q2) par période")
    print("=" * 96)
    print(f"    {'Période':<18}{'n':>5}{'rho':>8}{'p':>8}{'PF_bas':>8}{'PF_haut':>9}{'écart':>7}")
    for label, mask in periods.items():
        sub = df[mask].dropna(subset=["oracle_edge", "ret"])
        if len(sub) < 15:
            print(f"    {label:<18}{len(sub):>5}  (trop peu)")
            continue
        sub = sub.copy()
        sub["q"] = pd.qcut(sub["oracle_edge"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
        rho, p = spearmanr(sub["oracle_edge"], sub["ret"])
        lo = q_stats(sub[sub["q"].isin(["Q1", "Q2"])])
        hi = q_stats(sub[sub["q"].isin(["Q3", "Q4", "Q5"])])
        print(f"    {label:<18}{len(sub):>5}{rho:>8.3f}{p:>8.3g}{str(lo['pf']):>8}{str(hi['pf']):>9}"
              f"{'—' if lo['pf']=='inf' or hi['pf']=='inf' else round(float(hi['pf'])-float(lo['pf']),2)}")


if __name__ == "__main__":
    main()
