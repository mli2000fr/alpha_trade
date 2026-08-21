"""Analyse MFE/MAE : baseline vs C (outil permanent, Point 8).

Pour chaque trade (exit_closed des trade_audit_log), calcule depuis stock_bars_daily :
- MFE (favorable excursion) : max potentiel dans le sens du trade après entrée
- MAE (adverse excursion)   : pire excursion contre le trade
- rendement final (calculé depuis entry_price/exit_price, sens LONG/SHORT)
- ratio réalisation = final_return / MFE (combien du potentiel est capturé)
Compare baseline (4x/13%) vs C (5x/16%) globalement et par dimension.

Usage (depuis la racine projet) :
    f:/projets/.venv/Scripts/python.exe -u scripts/mfe_mae_analysis.py

Résultats 2026-08-18 documentés dans doc/ml/synthese_tp_risk_execution_2026-08-18.md §5.
"""
import pandas as pd
from sqlalchemy import text
from database.connection import get_sqlalchemy_engine

RUNS = {
    "baseline": r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_205031_2a2836d1\artifacts\trade_audit_log.csv",
    "C": r"F:\projets\artifacts\ihm_backtesting_runs\run\tp-sweep-c\artifacts\trade_audit_log.csv",
}


def load_trades(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["event_type"] == "exit_closed"].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    if "replay_exit_date" in df.columns and df["replay_exit_date"].notna().any():
        df["exit_date"] = pd.to_datetime(df["replay_exit_date"])
    else:
        df["exit_date"] = df["entry_date"] + pd.to_timedelta(df["holding_days"].fillna(0).astype(int), unit="D")
    df["entry_price"] = df["entry_price"].astype(float)
    df["exit_price"] = df["exit_price"].astype(float)
    return df


def load_bars(symbols, start, end) -> pd.DataFrame:
    """Charge high/low des barres pour les symboles entre start et end."""
    engine = get_sqlalchemy_engine()
    syms = sorted(set(symbols))
    placeholders = ",".join(f":s{i}" for i in range(len(syms)))
    params = {f"s{i}": s for i, s in enumerate(syms)}
    params["start"] = start
    params["end"] = end
    q = text(f"""
        SELECT UPPER(TRIM(symbol)) AS symbol, `date`, high, low
        FROM stock_bars_daily
        WHERE symbol IN ({placeholders}) AND `date` BETWEEN :start AND :end
    """)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    df["symbol"] = df["symbol"].str.upper()
    return df


def final_return(row: pd.Series) -> float:
    if row["side"] == "buy":
        return row["exit_price"] / row["entry_price"] - 1.0
    return 1.0 - row["exit_price"] / row["entry_price"]


def mfe_mae_from_bars(row: pd.Series, bars: pd.DataFrame):
    """Retourne (mfe, mae) en magnitude positive dans le sens du trade."""
    sub = bars[(bars["symbol"] == row["symbol"]) &
               (bars["date"] > row["entry_date"]) &
               (bars["date"] <= row["exit_date"])]
    if sub.empty:
        # fallback : inclure le jour d'entrée
        sub = bars[(bars["symbol"] == row["symbol"]) &
                   (bars["date"] >= row["entry_date"]) &
                   (bars["date"] <= row["exit_date"])]
    if sub.empty:
        return float("nan"), float("nan")
    entry = row["entry_price"]
    hi = sub["high"].max()
    lo = sub["low"].min()
    if row["side"] == "buy":
        mfe = hi / entry - 1.0
        mae = 1.0 - lo / entry
    else:
        mfe = 1.0 - lo / entry
        mae = hi / entry - 1.0
    return max(mfe, 0.0), max(mae, 0.0)


def summarize(g: pd.DataFrame, label: str) -> dict:
    n = len(g)
    if n == 0:
        return {"label": label, "n": 0}
    wins = g[g["final_return"] > 0]
    losses = g[g["final_return"] <= 0]
    return {
        "label": label,
        "n": n,
        "mfe_med": round(100 * g["mfe"].median(), 2),
        "mae_med": round(100 * g["mae"].median(), 2),
        "mfe_win": round(100 * wins["mfe"].median(), 2) if len(wins) else float("nan"),
        "mfe_loss": round(100 * losses["mfe"].median(), 2) if len(losses) else float("nan"),
        "mae_win": round(100 * wins["mae"].median(), 2) if len(wins) else float("nan"),
        "mae_loss": round(100 * losses["mae"].median(), 2) if len(losses) else float("nan"),
        "avg_profit": round(100 * wins["final_return"].mean(), 2) if len(wins) else float("nan"),
        "avg_loss": round(100 * losses["final_return"].mean(), 2) if len(losses) else float("nan"),
        "realize_med": round(100 * g["realization"].median(), 1),
        "wr": round(100 * len(wins) / n, 1),
    }


def main() -> None:
    frames = {}
    for name, path in RUNS.items():
        t = load_trades(path)
        t["final_return"] = t.apply(final_return, axis=1)
        frames[name] = t

    # barres pour tous les symboles impliqués
    all_syms = set()
    for t in frames.values():
        all_syms |= set(t["symbol"].dropna().unique())
    start = min(t["entry_date"].min() for t in frames.values()) - pd.Timedelta(days=3)
    end = max(t["exit_date"].max() for t in frames.values()) + pd.Timedelta(days=1)
    bars = load_bars(all_syms, start.date(), end.date())
    print(f"barres chargées : {len(bars)} lignes, {bars['symbol'].nunique()} symboles")

    # MFE/MAE par trade
    for name, t in frames.items():
        vals = t.apply(lambda r: pd.Series(mfe_mae_from_bars(r, bars), index=["mfe", "mae"]), axis=1)
        t["mfe"] = vals["mfe"]
        t["mae"] = vals["mae"]
        t["realization"] = t["final_return"] / t["mfe"].replace(0, float("nan"))
        frames[name] = t

    print("\n" + "=" * 96)
    print("A) SYNTHÈSE GLOBALE baseline vs C")
    print("=" * 96)
    cols = ["label", "n", "mfe_med", "mae_med", "mfe_win", "mfe_loss",
            "mae_win", "mae_loss", "avg_profit", "avg_loss", "realize_med", "wr"]
    for name, t in frames.items():
        s = summarize(t, name)
        print(f"  {s['label']:<9} n={s['n']:<4} MFE_med={s['mfe_med']:>6}%  MAE_med={s['mae_med']:>6}%  "
              f"MFE_w={s['mfe_win']:>6}%  MFE_l={s['mfe_loss']:>6}%  MAE_w={s['mae_win']:>6}%  MAE_l={s['mae_loss']:>6}%  "
              f"Pmoy={s['avg_profit']:>6}%  Lmoy={s['avg_loss']:>6}%  Réalisation={s['realize_med']:>5}%  WR={s['wr']}%")

    print("\n" + "=" * 96)
    print("B) PAR SENS (LONG/SHORT)")
    print("=" * 96)
    for name, t in frames.items():
        for side in ["buy", "sell"]:
            s = summarize(t[t["side"] == side], f"{name}/{side}")
            print(f"  {s['label']:<20} n={s['n']:<4} MFE_med={s['mfe_med']:>6}%  MAE_med={s['mae_med']:>6}%  "
                  f"MFE_w={s['mfe_win']:>6}%  MFE_l={s['mfe_loss']:>6}%  MAE_w={s['mae_win']:>6}%  MAE_l={s['mae_loss']:>6}%  "
                  f"Pmoy={s['avg_profit']:>6}%  Lmoy={s['avg_loss']:>6}%  Réal={s['realize_med']:>5}%  WR={s['wr']}%")

    print("\n" + "=" * 96)
    print("C) PAR DURÉE (jours)")
    print("=" * 96)
    buckets = [(0, 5), (5, 10), (10, 20), (20, 10_000)]
    for name, t in frames.items():
        t = t.copy()
        t["dur"] = (t["exit_date"] - t["entry_date"]).dt.days
        for lo, hi in buckets:
            sub = t[(t["dur"] >= lo) & (t["dur"] < hi)]
            s = summarize(sub, f"{name} [{lo}-{hi}j)")
            print(f"  {s['label']:<24} n={s['n']:<4} MFE_med={s['mfe_med']:>6}%  MAE_med={s['mae_med']:>6}%  "
                  f"MFE_w={s['mfe_win']:>6}%  MFE_l={s['mfe_loss']:>6}%  Réal={s['realize_med']:>5}%  WR={s['wr']}%")

    print("\n" + "=" * 96)
    print("D) PAR TYPE DE SORTIE")
    print("=" * 96)
    for name, t in frames.items():
        for reason in ["take_profit", "trailing_stop", "time_stop"]:
            s = summarize(t[t["exit_reason"] == reason], f"{name}/{reason}")
            print(f"  {s['label']:<24} n={s['n']:<4} MFE_med={s['mfe_med']:>6}%  MAE_med={s['mae_med']:>6}%  "
                  f"MFE_w={s['mfe_win']:>6}%  MFE_l={s['mfe_loss']:>6}%  Réal={s['realize_med']:>5}%  WR={s['wr']}%")

    # persistance pour analyse ultérieure (traceabilité)
    for name, t in frames.items():
        t.to_csv(rf"F:\projets\scripts\mfe_mae_{name}.csv", index=False)
        print(f"\n  -> sauvegardé mfe_mae_{name}.csv ({len(t)} trades)")


if __name__ == "__main__":
    main()
