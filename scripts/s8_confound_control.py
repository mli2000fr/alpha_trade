"""S8.2 — Contrôle des confounders : oracle_edge garde-t-il du pouvoir prédictif
après contrôle de global_rank_20 / score B25 / ATR ?

1. Corrélation partielle Spearman : ret ~ oracle_edge | global_rank_20 (et score, ATR)
2. Double tri : médiane global_rank_20 × quintiles oracle_edge → PF/WR/PnL
3. Régression OLS : ret ~ global_rank_20 + score + atr + oracle_edge (coefficient oracle)
"""
import pandas as pd
from scipy.stats import spearmanr

CSV = r"F:\projets\scripts\s8_trades_with_oracle.csv"


def partial_spearman(df, x, y, control):
    """Corrélation partielle de Spearman de x,y en contrôlant control (résidus de rang)."""
    for c in [x, y, control]:
        df = df.dropna(subset=[c])
    from scipy.stats import rankdata
    rx = rankdata(df[x])
    ry = rankdata(df[y])
    rc = rankdata(df[control])
    # résidus de rx/ry sur rc (régression simple)
    def resid(v, c_):
        b = pd.Series(v).corr(pd.Series(c_)) * (pd.Series(v).std() / pd.Series(c_).std())
        return pd.Series(v) - b * pd.Series(c_)
    rxr = resid(rx, rc)
    ryr = resid(ry, rc)
    rho = rxr.corr(ryr)
    # p-value approximée
    n = len(df)
    import numpy as np
    t = rho * np.sqrt((n - 3) / (1 - rho**2)) if abs(rho) < 1 else np.nan
    from scipy.stats import t as tdist
    p = 2 * (1 - tdist.cdf(abs(t), n - 3)) if not np.isnan(t) else float("nan")
    return rho, p, n


def bucket(g: pd.DataFrame, label: str) -> dict:
    n = len(g)
    if n == 0:
        return {"q": label, "n": 0}
    wins = g[g["ret"] > 0]
    gl = -g[g["ret"] <= 0]["pnl"].sum()
    pf = wins["pnl"].sum() / gl if gl > 0 else float("inf")
    return {"q": label, "n": n, "wr": round(100*len(wins)/n, 1),
            "pf": round(pf, 2) if pf != float("inf") else "inf",
            "pnl": round(g["pnl"].sum(), 0)}


def main() -> None:
    df = pd.read_csv(CSV)
    df["ret"] = df["ret"].astype(float)
    print(f"n={len(df)}")

    # ── 1. Corrélations partielles ──
    print("\n" + "=" * 80)
    print("1) Corrélation partielle Spearman : oracle_edge vs ret | <contrôles>")
    print("=" * 80)
    controls = {
        "sans contrôle": None,
        "global_rank_20": "global_rank_20",
        "score B25": "score",
        "ATR": "atr_impl",
        "global_rank + score + ATR": ["global_rank_20", "score", "atr_impl"],
    }
    for lab, ctrl in controls.items():
        if ctrl is None:
            sub = df.dropna(subset=["oracle_edge", "ret"])
            rho, p = spearmanr(sub["oracle_edge"], sub["ret"])
            print(f"  {lab:<28}: rho={rho:+.4f} (p={p:.4g}, n={len(sub)})")
        elif isinstance(ctrl, str):
            rho, p, n = partial_spearman(df[["oracle_edge", "ret", ctrl]], "oracle_edge", "ret", ctrl)
            print(f"  {lab:<28}: rho={rho:+.4f} (p={p:.4g}, n={n})")
        else:
            # contrôle multiple : régresse oracle_edge et ret sur tous les contrôles, corrél des résidus
            sub = df.dropna(subset=["oracle_edge", "ret", *ctrl]).copy()
            import numpy as np
            from scipy.stats import rankdata
            X = np.column_stack([rankdata(sub[c]) for c in ctrl])
            y = rankdata(sub["ret"])
            x = rankdata(sub["oracle_edge"])
            # résidus vs design
            def ols_resid(tgt, Xd):
                X1 = np.column_stack([np.ones(len(Xd)), Xd])
                beta, *_ = np.linalg.lstsq(X1, tgt, rcond=None)
                return tgt - X1 @ beta
            ry = ols_resid(y, X)
            rx = ols_resid(x, X)
            rho = np.corrcoef(rx, ry)[0, 1]
            n = len(sub)
            t = rho * np.sqrt((n - 3) / (1 - rho**2)) if abs(rho) < 1 else np.nan
            from scipy.stats import t as tdist
            p = 2 * (1 - tdist.cdf(abs(t), n - 3)) if not np.isnan(t) else float("nan")
            print(f"  {lab:<28}: rho={rho:+.4f} (p={p:.4g}, n={n})")

    # ── 2. Double tri : médiane global_rank_20 × quintiles oracle_edge ──
    print("\n" + "=" * 80)
    print("2) Double tri : global_rank_20 (médiane) × oracle_edge (quintiles)")
    print("=" * 80)
    sub = df.dropna(subset=["global_rank_20", "oracle_edge", "ret"]).copy()
    sub["gr_hi"] = sub["global_rank_20"] >= sub["global_rank_20"].median()
    sub["edge_q"] = pd.qcut(sub["oracle_edge"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    print(f"{'GR':<8} | " + " | ".join(f"Q{i}" for i in range(1, 6)) + " |  (PF / WR / PnL)")
    for gr_hi, gname in [(True, "GR élevé"), (False, "GR faible")]:
        g = sub[sub["gr_hi"] == gr_hi]
        cells = []
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            gg = g[g["edge_q"] == q]
            b = bucket(gg, q)
            cells.append(f"{b['pf']}/{b['wr']}/{b['pnl']}")
        print(f"{gname:<8} | " + " | ".join(c.ljust(14) for c in cells))

    # ── 3. OLS : ret ~ global_rank_20 + score + atr + oracle_edge ──
    print("\n" + "=" * 80)
    print("3) OLS (rangs) : ret ~ global_rank_20 + score + atr_impl + oracle_edge")
    print("=" * 80)
    import numpy as np
    from scipy.stats import rankdata
    o = df.dropna(subset=["ret", "oracle_edge", "global_rank_20", "score", "atr_impl"]).copy()
    X = np.column_stack([
        np.ones(len(o)),
        rankdata(o["global_rank_20"]),
        rankdata(o["score"]),
        rankdata(o["atr_impl"]),
        rankdata(o["oracle_edge"]),
    ])
    y = rankdata(o["ret"])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = n - k
    s2 = resid @ resid / dof
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    names = ["intercept", "global_rank_20", "score_B25", "atr_impl", "oracle_edge"]
    from scipy.stats import t as tdist
    print(f"  n={n}")
    for nm, b, s in zip(names, beta, se):
        tstat = b / s
        p = 2 * (1 - tdist.cdf(abs(tstat), dof))
        print(f"  {nm:<16}: beta={b:+.4f} (se={s:.4f}) t={tstat:+.2f} p={p:.4g}")


if __name__ == "__main__":
    main()
