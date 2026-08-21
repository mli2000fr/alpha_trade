"""S8.2b (étendu) — Stabilité temporelle de oracle_edge sur trades B25 exécutés.

5 périodes : 2022, 2023H1, 2024H1, 2025, 2026H1.
Pour chaque période : oracle_edge quintiles → WR/PF/PnL/avgRet + Spearman.
Question : les trades à faible oracle_edge sont-ils systématiquement moins bons ?
"""
import pandas as pd
from scipy.stats import spearmanr

RUNS = {
    "2022": r"F:\projets\artifacts\ihm_backtesting_runs\run\s8-ext-2022\artifacts\trade_audit_log.csv",
    "2023H1": r"F:\projets\artifacts\ihm_backtesting_runs\run\s8-ext-2023h1\artifacts\trade_audit_log.csv",
    "2024H1": r"F:\projets\artifacts\ihm_backtesting_runs\run\s8-ext-2024h1\artifacts\trade_audit_log.csv",
    "2025-26": r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_205031_2a2836d1\artifacts\trade_audit_log.csv",
}
ORACLE_TOP = r"F:\projets\artifacts\models\oracle\oracle-wf-20260818021140\oos_predictions.parquet"
ORACLE_BOTTOM = r"F:\projets\artifacts\models\oracle\oracle-wf-20260818035339\oos_predictions.parquet"


def load_trades(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["event_type"] == "exit_closed"].copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df["entry_price"] = df["entry_price"].astype(float)
    df["exit_price"] = df["exit_price"].astype(float)
    df["ret"] = df.apply(lambda r: r["exit_price"] / r["entry_price"] - 1.0 if r["side"] == "buy"
                         else 1.0 - r["exit_price"] / r["entry_price"], axis=1)
    return df


def load_oracle() -> pd.DataFrame:
    top = pd.read_parquet(ORACLE_TOP, columns=["date", "symbol", "proba_top"])
    bot = pd.read_parquet(ORACLE_BOTTOM, columns=["date", "symbol", "proba_bottom"])
    for d in (top, bot):
        d["date"] = pd.to_datetime(d["date"])
        d["symbol"] = d["symbol"].str.upper()
    m = top.merge(bot, on=["date", "symbol"], how="outer")
    m["oracle_edge"] = m["proba_top"] - m["proba_bottom"]
    return m


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


def main() -> None:
    oracle = load_oracle()

    # assemblage des trades par période
    frames = {}
    for name, path in RUNS.items():
        t = load_trades(path)
        if name == "2025-26":
            t = t[(t["signal_date"] >= "2025-01-01") & (t["signal_date"] <= "2026-05-31")]
            frames["2025"] = t[t["signal_date"] <= "2025-12-31"].copy()
            frames["2026H1"] = t[t["signal_date"] >= "2026-01-01"].copy()
        else:
            frames[name] = t

    print("=" * 100)
    print("S8.2b étendu — oracle_edge quintiles × 5 périodes (trades B25 exécutés)")
    print("=" * 100)
    print(f"    {'Période':<8}{'n':>5}{'join%':>7}{'rho':>8}{'p':>8}{'PF_bas':>8}{'PF_haut':>9}{'écart':>8}")
    for name in ["2022", "2023H1", "2024H1", "2025", "2026H1"]:
        t = frames[name]
        m = t.merge(oracle, left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
        n_join = m["oracle_edge"].notna().sum()
        join_pct = 100 * n_join / len(m)
        m = m.dropna(subset=["oracle_edge", "ret"]).copy()
        n = len(m)
        if n < 15:
            print(f"    {name:<8}{n:>5}{join_pct:>7.1f}  (trop peu de trades)")
            continue
        m["q"] = pd.qcut(m["oracle_edge"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
        rho, p = spearmanr(m["oracle_edge"], m["ret"])
        lo = q_stats(m[m["q"].isin(["Q1", "Q2"])])
        hi = q_stats(m[m["q"].isin(["Q3", "Q4", "Q5"])])
        pf_lo = float(lo["pf"]) if lo["pf"] != "inf" else float("nan")
        pf_hi = float(hi["pf"]) if hi["pf"] != "inf" else float("nan")
        print(f"    {name:<8}{n:>5}{join_pct:>7.1f}{rho:>8.3f}{p:>8.3g}{pf_lo:>8.2f}{pf_hi:>9.2f}{pf_hi-pf_lo:>8.2f}")
        # détail quintiles
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            s = q_stats(m[m["q"] == q])
            print(f"        {q:<4} n={s['n']:>3} WR={s['wr']:>5}% PF={str(s['pf']):>5} avgRet={s['avg_ret']:>6}% PnL={s['pnl']:>7}")

    # Vue globale consolidée (toutes périodes)
    print("\n" + "=" * 100)
    print("Consolidé (toutes périodes confondues) : oracle_edge quintiles")
    print("=" * 100)
    allm = pd.concat([frames[k].merge(oracle, left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
                      for k in ["2022", "2023H1", "2024H1", "2025", "2026H1"]], ignore_index=True)
    allm = allm.dropna(subset=["oracle_edge", "ret"]).copy()
    allm["q"] = pd.qcut(allm["oracle_edge"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        s = q_stats(allm[allm["q"] == q])
        print(f"    {q:<4} n={s['n']:>4} WR={s['wr']:>5}% PF={str(s['pf']):>5} avgRet={s['avg_ret']:>6}% PnL={s['pnl']:>7}")
    rho, p = spearmanr(allm["oracle_edge"], allm["ret"])
    print(f"    Spearman global : rho={rho:+.4f} (p={p:.4g}, n={len(allm)})")
    allm.to_csv(r"F:\projets\scripts\s8_trades_all_periods.csv", index=False)
    print(f"\n-> sauvegardé scripts/s8_trades_all_periods.csv ({len(allm)} trades)")


if __name__ == "__main__":
    main()
