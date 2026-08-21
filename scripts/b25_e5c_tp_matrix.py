"""E5-C : matrice TP — comparaison des variantes (2025 et 2026 séparément).

Variantes (tout le reste strictement identique à la baseline canonique
B25_POST_TP_FIX_P14_M8 = min(3xATR, 7%)):
  - 4x10 : min(4xATR, 10%)
  - 4x13 : min(4xATR, 13%)
  - 5x16 : min(5xATR, 16%)
  - notp  : min(50xATR, 100%)  <- TP jamais atteint (seuls trailing/time_stop)

Question centrale : quelle zone TP capture davantage les gros mouvements sans
laisser exploser les erreurs directionnelles ?
Criteres : Si une variante gagne seulement en 2025 mais perd en 2026 -> NO-GO.
Si 4xATR/10% ou 4xATR/13% améliore les deux de façon cohérente -> GO.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("artifacts/backtesting")


def load_summary(name):
    rp = ROOT / name / "report.json"
    if not rp.exists():
        return None, None
    j = json.loads(rp.read_text(encoding="utf-8"))
    return j.get("summary", {}), j.get("params", {})


def load_trades(name):
    f = ROOT / name / "trade_audit_log.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    # Garde uniquement les trades fermés
    closed = df[df["replay_exit_reason"].notna() | df["exit_reason"].notna()].copy()
    return closed


RUNS = {
    "base": {"2025": "cmp_b25_h20_2025_postfix_tp_m8", "2026": "cmp_b25_h20_2026_postfix_tp_m8"},
    "4x10": {"2025": "cmp_b25_h20_2025_tp4x10_m8", "2026": "cmp_b25_h20_2026_tp4x10_m8"},
    "4x13": {"2025": "cmp_b25_h20_2025_tp4x13_m8", "2026": "cmp_b25_h20_2026_tp4x13_m8"},
    "5x16": {"2025": "cmp_b25_h20_2025_tp5x16_m8", "2026": "cmp_b25_h20_2026_tp5x16_m8"},
    "notp": {"2025": "cmp_b25_h20_2025_notp_m8", "2026": "cmp_b25_h20_2026_notp_m8"},
}

LABEL = {
    "base": "3xATR/7% (baseline)",
    "4x10": "4xATR/10%",
    "4x13": "4xATR/13%",
    "5x16": "5xATR/16%",
    "notp": "no-TP",
}


def normalize_reason(r):
    """Normalise les exit reasons pour regroupement."""
    if r is None or (isinstance(r, float) and pd.isna(r)):
        return "NA"
    r = str(r).lower()
    if "take_profit" in r or "tp" in r.split("_") or r == "tp":
        return "TP"
    if "trailing" in r:
        return "TRAIL"
    if "time_stop" in r or "time stop" in r:
        return "TIME_STOP"
    if "stop" in r:
        return "STOP"
    if "force_close" in r or "force close" in r:
        return "FORCE_CLOSE"
    return r[:24]


def analyze_year(year):
    rows = []
    for key, dirs in RUNS.items():
        name = dirs[year]
        summary, params = load_summary(name)
        if summary is None:
            rows.append({"variant": key, "label": LABEL[key], "status": "ABSENT"})
            continue
        trades = load_trades(name)
        exit_counts = {}
        n_tp = n_trail = n_ts = 0
        mean_hold = None
        ret_by_reason = {}
        if trades is not None and len(trades):
            # raison de sortie prioritairement replay (source de vérité du pipeline)
            reason_col = "replay_exit_reason" if trades["replay_exit_reason"].notna().any() else "exit_reason"
            reasons = trades[reason_col].map(normalize_reason)
            exit_counts = reasons.value_counts().to_dict()
            n_tp = exit_counts.get("TP", 0)
            n_trail = exit_counts.get("TRAIL", 0)
            n_ts = exit_counts.get("TIME_STOP", 0)
            hold = trades["holding_days"].dropna()
            if len(hold):
                mean_hold = float(hold.mean())
            # PnL par raison (retour moyen)
            ret = trades[["return_pct", reason_col]].copy()
            ret["reason"] = ret[reason_col].map(normalize_reason)
            ret_by_reason = ret.groupby("reason")["return_pct"].agg(["count", "mean", "sum"]).round(4).to_dict("index")
        rows.append({
            "variant": key,
            "label": LABEL[key],
            "status": "OK",
            "ret": summary.get("total_return_pct", 0),
            "pf": summary.get("profit_factor", 0),
            "sharpe": summary.get("sharpe_ratio", 0),
            "dd": summary.get("max_drawdown_pct", 0),
            "n": summary.get("total_trades", 0),
            "win": summary.get("win_rate_pct", 0),
            "l_pnl": summary.get("long_pnl_total", 0),
            "s_pnl": summary.get("short_pnl_total", 0),
            "net": summary.get("pnl_net", 0),
            "dur": mean_hold,
            "n_tp": n_tp,
            "n_trail": n_trail,
            "n_ts": n_ts,
            "ret_by_reason": ret_by_reason,
        })
    return rows


def print_year(year):
    rows = analyze_year(year)
    print(f"\n{'=' * 110}")
    print(f"E5-C — MATRICE TP — {year}")
    print(f"{'=' * 110}")
    print(f"{'variante':22} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'N':>4} "
          f"{'Win%':>6} {'L_pnl':>9} {'S_pnl':>9} {'net':>9} {'dur_j':>6} "
          f"{'nTP':>4} {'nTr':>4} {'nTS':>4}")
    print("-" * 110)
    for r in rows:
        if r.get("status") != "OK":
            print(f"{r['label']:22} {r['status']}")
            continue
        print(f"{r['label']:22} {r['ret']:8.2f} {r['pf']:6.2f} {r['sharpe']:7.2f} "
              f"{r['dd']:7.2f} {r['n']:4d} {r['win']:6.1f} {r['l_pnl']:9.0f} "
              f"{r['s_pnl']:9.0f} {r['net']:9.0f} {r['dur']:6.2f} "
              f"{r['n_tp']:4d} {r['n_trail']:4d} {r['n_ts']:4d}")
    # Détail par raison de sortie (retour moyen)
    print(f"\nRetour moyen par raison de sortie ({year}) :")
    print(f"{'variante':22} " + " | ".join(f"{k:>8}" for k in ["TP", "TRAIL", "STOP", "TIME_STOP"]))
    for r in rows:
        if r.get("status") != "OK":
            continue
        rb = r["ret_by_reason"]
        cells = []
        for k in ["TP", "TRAIL", "STOP", "TIME_STOP"]:
            v = rb.get(k, {})
            if v:
                cells.append(f"{v['mean']*100:6.2f}({v['count']})")
            else:
                cells.append(f"{'-':>8}")
        print(f"{r['label']:22} " + " | ".join(f"{c:>8}" for c in cells))


if __name__ == "__main__":
    years = sys.argv[1:] or ["2025", "2026"]
    for y in years:
        print_year(y)
