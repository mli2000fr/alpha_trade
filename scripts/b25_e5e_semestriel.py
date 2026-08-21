"""E5-E — Analyse SEMESTRIELLE 3×7 vs 4×13 (H1/H2), couverture-détectée.

Objectif : éviter qu'un semestre catastrophique soit masqué par un autre semestre
favorable. La stabilité est jugée sur les demi-années, pas sur les années complètes.

Règles :
- Les runs disponibles déterminent les semestres analysables (par fenêtre du run).
- Un semestre est INSUFFICIENT si :
  (a) aucun run ne couvre ce semestre ; OU
  (b) la couverture ML de prédictions B25 sur le semestre est < 90 % des dates
      attendues (~124 jours ouvrés) — sinon le backtest est dégradé.
- On ne réimpute JAMAIS un semestre manquant : il est marqué INSUFFICIENT.
- Métriques par semestre : Ret%, PF, DD%, net, N, LONG pnl, SHORT pnl.

Semestres cibles : 2022H1, 2022H2, 2023H1, 2023H2, 2024H1, 2024H2, 2025H1, 2025H2,
2026H1. 2026H2 hors scope (fin entraînement).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

ROOT = Path("artifacts/backtesting")
BATCH = "model-factory-20260811223551-ef2cd0"

# Fenêtres de run disponibles (3x7 / 4x13) → semestres couverts
RUNS = {
    "2022": {"3x7": "cmp_b25_h20_2022_postfix_tp_m8", "4x13": "cmp_b25_h20_2022_tp4x13_m8"},
    "2023h1": {"3x7": "cmp_b25_h20_2023h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2023h1_tp4x13_m8"},
    "2024h1": {"3x7": "cmp_b25_h20_2024h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2024h1_tp4x13_m8"},
    "2025": {"3x7": "cmp_b25_h20_2025_postfix_tp_m8", "4x13": "cmp_b25_h20_2025_tp4x13_m8"},
    "2026h1": {"3x7": "cmp_b25_h20_2026_postfix_tp_m8", "4x13": "cmp_b25_h20_2026_tp4x13_m8"},
}

# Semestres cibles : (label, année, semestre, début, fin, run_window)
SEMESTERS = [
    ("2022 H1", 2022, 1, "2022-01-03", "2022-06-30", "2022"),
    ("2022 H2", 2022, 2, "2022-07-01", "2022-12-31", "2022"),
    ("2023 H1", 2023, 1, "2023-01-03", "2023-06-30", "2023h1"),
    ("2023 H2", 2023, 2, "2023-07-01", "2023-12-31", None),
    ("2024 H1", 2024, 1, "2024-01-02", "2024-06-30", "2024h1"),
    ("2024 H2", 2024, 2, "2024-07-01", "2024-12-31", None),
    ("2025 H1", 2025, 1, "2025-01-02", "2025-06-30", "2025"),
    ("2025 H2", 2025, 2, "2025-07-01", "2025-12-31", "2025"),
    ("2026 H1", 2026, 1, "2026-01-02", "2026-05-31", "2026h1"),
]


def pred_coverage(sem_start: str, sem_end: str) -> float:
    """Fraction de dates ouvrées couvertes par les prédictions B25 sur le semestre."""
    eng = get_sqlalchemy_engine()
    q = text(
        "SELECT COUNT(DISTINCT prediction_date) AS ndays FROM model_predictions p "
        "JOIN model_training_run tr ON tr.run_id = p.run_id "
        "WHERE tr.batch_id = :b AND p.prediction_date BETWEEN :s AND :e"
    )
    with eng.connect() as c:
        r = c.execute(q, {"b": BATCH, "s": sem_start, "e": sem_end}).mappings().first()
    # dates ouvrées attendues ≈ jours calendaires * 5/7
    n_cal = (pd.Timestamp(sem_end) - pd.Timestamp(sem_start)).days + 1
    n_exp = max(int(n_cal * 5 / 7), 1)
    return min(1.0, (r.ndays or 0) / n_exp)


def load_summary(name: str) -> dict:
    import json
    j = json.loads((ROOT / name / "report.json").read_text(encoding="utf-8"))
    return j.get("summary", {})


def load_trades_window(name: str, d0: str, d1: str) -> pd.DataFrame:
    """Trades fermés entrés dans [d0, d1] (découpe semestrielle)."""
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    df = df[df["replay_exit_reason"].notna()].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    mask = (df["entry_date"] >= pd.Timestamp(d0)) & (df["entry_date"] <= pd.Timestamp(d1))
    return df[mask]


def equity_window(name: str, d0: str, d1: str) -> pd.Series:
    eq = pd.read_csv(ROOT / name / "equity_curve.csv")
    eq["trade_date"] = pd.to_datetime(eq["trade_date"])
    seg = eq[(eq["trade_date"] >= pd.Timestamp(d0)) & (eq["trade_date"] <= pd.Timestamp(d1))]
    return seg["portfolio_value"]


def max_drawdown(equity: pd.Series) -> float:
    """DD max en % (négatif)."""
    if len(equity) < 2:
        return 0.0
    cummax = equity.cummax()
    dd = (equity / cummax - 1.0).min()
    return float(dd * 100)


def window_metrics(name: str, d0: str, d1: str) -> dict:
    """Métriques par semestre : Ret% (equity), DD%, PF/net/N/L/S (trades entrés)."""
    eq = equity_window(name, d0, d1)
    ret = 0.0
    if len(eq) >= 2:
        ret = (eq.iloc[-1] / eq.iloc[0] - 1.0) * 100
    dd = max_drawdown(eq)
    tr = load_trades_window(name, d0, d1)
    pnl = tr["pnl"].astype(float)
    net = float(pnl.sum()) if len(pnl) else 0.0
    n = int(len(tr))
    pos = pnl[pnl > 0].sum()
    neg = -pnl[pnl < 0].sum()
    pf = float(pos / neg) if neg > 0 else float("inf")
    l = float(tr.loc[tr["side"].isin(["buy", "long", "L"]), "pnl"].astype(float).sum()) if len(tr) else 0.0
    s = float(tr.loc[tr["side"].isin(["sell", "short", "S"]), "pnl"].astype(float).sum()) if len(tr) else 0.0
    return {"ret": ret, "dd": dd, "pf": pf, "net": net, "n": n, "l": l, "s": s}


def main() -> None:
    print("=" * 120)
    print("E5-E — ANALYSE SEMESTRIELLE 3×7 vs 4×13 (stabilité par demi-année)")
    print("=" * 120)
    print(f"{'semestre':9} {'couvert.':>8} {'3x7 Ret%':>9} {'4x13 Ret%':>9} {'Δ Ret%':>8} "
          f"{'3x7 PF':>7} {'4x13 PF':>7} {'3x7 DD%':>8} {'4x13 DD%':>8} {'3x7 net':>9} "
          f"{'4x13 net':>9} {'3x7 N':>5} {'4x13 N':>5} {'3x7 L/S':>10} {'4x13 L/S':>10}   statut")
    print("-" * 120)

    for label, yr, sem, d0, d1, window in SEMESTERS:
        cov = pred_coverage(d0, d1)
        run_key = window
        if run_key is None or run_key not in RUNS:
            print(f"{label:9} {cov*100:7.1f}%   —   —   —   —   —   —   —   —   —   —   —   —   —   INSUFFICIENT (aucun run)")
            continue
        if cov < 0.90:
            print(f"{label:9} {cov*100:7.1f}%   —   —   —   —   —   —   —   —   —   —   —   —   —   INSUFFICIENT (couverture ML {cov*100:.0f}%)")
            continue

        s37 = window_metrics(RUNS[run_key]["3x7"], d0, d1)
        s413 = window_metrics(RUNS[run_key]["4x13"], d0, d1)

        print(f"{label:9} {cov*100:7.1f}% {s37['ret']:9.2f} {s413['ret']:9.2f} {s413['ret']-s37['ret']:8.2f} "
              f"{s37['pf']:7.2f} {s413['pf']:7.2f} {s37['dd']:8.2f} {s413['dd']:8.2f} {s37['net']:9.0f} {s413['net']:9.0f} "
              f"{s37['n']:5d} {s413['n']:5d} {s37['l']+s37['s']:>9.0f}/{s413['l']+s413['s']:>9.0f}   OK")


if __name__ == "__main__":
    main()
