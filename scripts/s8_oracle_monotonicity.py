"""S8.1 — Monotonie du score Oracle sur les trades B25 réellement exécutés.

Pour chaque trade B25 (baseline production, 237 trades, config réelle), récupère le
score Oracle disponible à l'entrée (P_top / P_bottom / oracle_edge = P_top - P_bottom)
et classe en quintiles → PF / WR / PnL / durée.

S8.2 (initial) : compare les quantiles sur les confounders disponibles
(global_rank_20, score B25, ATR implicite, secteur, sens, durée).

Sources :
- Trades : artifacts/ihm_backtesting_runs/run/20260817_205031_2a2836d1/artifacts/trade_audit_log.csv
- Oracle TOP  : artifacts/models/oracle/oracle-wf-20260818021140/oos_predictions.parquet
- Oracle BOTTOM : artifacts/models/oracle/oracle-wf-20260818035339/oos_predictions.parquet
Join Oracle sur (symbol, signal_date) — le score Oracle du jour du signal.
"""
import pandas as pd

TRADES = r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_205031_2a2836d1\artifacts\trade_audit_log.csv"
ORACLE_TOP = r"F:\projets\artifacts\models\oracle\oracle-wf-20260818021140\oos_predictions.parquet"
ORACLE_BOTTOM = r"F:\projets\artifacts\models\oracle\oracle-wf-20260818035339\oos_predictions.parquet"


def load_trades() -> pd.DataFrame:
    df = pd.read_csv(TRADES)
    df = df[df["event_type"] == "exit_closed"].copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df["entry_price"] = df["entry_price"].astype(float)
    df["exit_price"] = df["exit_price"].astype(float)
    df["ret"] = df.apply(lambda r: r["exit_price"] / r["entry_price"] - 1.0 if r["side"] == "buy"
                         else 1.0 - r["exit_price"] / r["entry_price"], axis=1)
    # ATR implicite depuis le stop initial (stop = 3.5×ATR)
    df["atr_impl"] = df.apply(
        lambda r: abs(r["replay_initial_stop_price"] - r["entry_price"]) / 3.5
        if pd.notna(r["replay_initial_stop_price"]) else float("nan"), axis=1)
    return df


def load_oracle() -> pd.DataFrame:
    top = pd.read_parquet(ORACLE_TOP, columns=["date", "symbol", "proba_top", "global_rank_20"])
    bot = pd.read_parquet(ORACLE_BOTTOM, columns=["date", "symbol", "proba_bottom"])
    top["date"] = pd.to_datetime(top["date"])
    bot["date"] = pd.to_datetime(bot["date"])
    top["symbol"] = top["symbol"].str.upper()
    bot["symbol"] = bot["symbol"].str.upper()
    m = top.merge(bot, on=["date", "symbol"], how="outer")
    m["oracle_edge"] = m["proba_top"] - m["proba_bottom"]
    return m


def bucket_stats(g: pd.DataFrame, label: str) -> dict:
    n = len(g)
    if n == 0:
        return {"q": label, "n": 0}
    wins = g[g["ret"] > 0]
    losses = g[g["ret"] <= 0]
    gw = wins["pnl"].sum()
    gl = -losses["pnl"].sum()
    pf = gw / gl if gl > 0 else float("inf")
    return {
        "q": label, "n": n,
        "wr": round(100 * len(wins) / n, 1),
        "pf": round(pf, 2) if pf != float("inf") else "inf",
        "pnl": round(g["pnl"].sum(), 0),
        "avg_pnl": round(g["pnl"].mean(), 1),
        "avg_ret": round(100 * g["ret"].mean(), 2),
        "avg_dur": round(g["holding_days"].mean(), 1),
        "long_pct": round(100 * (g["side"] == "buy").mean(), 1),
        "atr_med": round(g["atr_impl"].median(), 2) if "atr_impl" in g else float("nan"),
        "score_med": round(g["score"].median(), 4),
        "gr_med": round(g["global_rank_20"].median(), 3) if "global_rank_20" in g else float("nan"),
        "top_sector": g["sector"].mode().iloc[0] if "sector" in g else "n/a",
    }


def main() -> None:
    trades = load_trades()
    oracle = load_oracle()

    # join sur (symbol, signal_date)
    merged = trades.merge(oracle, left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
    n_join = merged["proba_top"].notna().sum()
    print(f"Trades B25: {len(trades)} | jointures Oracle OK: {n_join} ({100*n_join/len(trades):.1f}%)")

    m = merged.dropna(subset=["proba_top", "proba_bottom"]).copy()
    print(f"Trades avec score Oracle complet: {len(m)}")

    # ── S8.1 : quintiles par oracle_edge ──
    print("\n" + "=" * 104)
    print("S8.1 — Monotonie oracle_edge (P_top − P_bottom) sur trades B25, quintiles")
    print("=" * 104)
    m["edge_q"] = pd.qcut(m["oracle_edge"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    rows = [bucket_stats(sub, str(q)) for q, sub in m.groupby("edge_q", observed=True)]
    hdr = ["q", "n", "wr", "pf", "pnl", "avg_pnl", "avg_ret", "avg_dur", "long_pct", "atr_med", "score_med", "gr_med", "top_sector"]
    print(" | ".join(h.rjust(9) for h in hdr))
    for r in rows:
        print(" | ".join(str(r[h]).rjust(9) if isinstance(r[h], str) else str(r[h]).rjust(9) for h in hdr))

    # ── S8.1b : quintiles par P_top seul ──
    print("\n" + "=" * 104)
    print("S8.1b — Monotonie P_top seul, quintiles")
    print("=" * 104)
    m["ptop_q"] = pd.qcut(m["proba_top"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    rows = [bucket_stats(sub, str(q)) for q, sub in m.groupby("ptop_q", observed=True)]
    for r in rows:
        print(" | ".join(str(r[h]).rjust(9) if isinstance(r[h], str) else str(r[h]).rjust(9) for h in hdr))

    # ── S8.1c : quintiles par P_bottom seul ──
    print("\n" + "=" * 104)
    print("S8.1c — Monotonie P_bottom seul (inverse attendu), quintiles")
    print("=" * 104)
    m["pbot_q"] = pd.qcut(m["proba_bottom"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    rows = [bucket_stats(sub, str(q)) for q, sub in m.groupby("pbot_q", observed=True)]
    for r in rows:
        print(" | ".join(str(r[h]).rjust(9) if isinstance(r[h], str) else str(r[h]).rjust(9) for h in hdr))

    # ── Monotonicité (corrélation rang) oracle_edge vs return ──
    from scipy.stats import spearmanr
    valid = m.dropna(subset=["oracle_edge", "ret"])
    rho, p = spearmanr(valid["oracle_edge"], valid["ret"])
    print(f"\nSpearman oracle_edge vs trade_ret : rho={rho:.4f} (p={p:.4g}) n={len(valid)}")
    rho2, p2 = spearmanr(valid["proba_top"], valid["ret"])
    print(f"Spearman P_top vs trade_ret       : rho={rho2:.4f} (p={p2:.4g})")

    # ── S8.2 : corrélation oracle_edge avec les confounders ──
    print("\n" + "=" * 104)
    print("S8.2 — Confounders : corrélation Spearman de oracle_edge avec les autres variables")
    print("=" * 104)
    for col, lab in [("global_rank_20", "global_rank_20"), ("score", "score B25"),
                     ("atr_impl", "ATR implicite"), ("ret", "return trade (controle)")]:
        sub = valid.dropna(subset=[col])
        if len(sub) < 10:
            print(f"  {lab:<22}: n trop faible")
            continue
        r, pv = spearmanr(sub["oracle_edge"], sub[col])
        print(f"  {lab:<22}: rho={r:+.4f} (n={len(sub)})")

    # sauvegarde
    m.to_csv(r"F:\projets\scripts\s8_trades_with_oracle.csv", index=False)
    print(f"\n-> sauvegardé scripts/s8_trades_with_oracle.csv ({len(m)} trades avec score Oracle)")


if __name__ == "__main__":
    main()
