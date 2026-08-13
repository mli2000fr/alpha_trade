"""P1-6 — Rolling IC 6/12 mois du signal B25 (stabilité temporelle).

À partir de l'IC journalier (artifacts/metrics/ic_by_regime_b25_daily.csv) :
- IC moyen glissant sur 126 et 252 séances (6/12 mois de trading)
- % de fenêtres glissantes positives
- séquence négative max (jours consécutifs IC < 0)
- drawdown du cumul d'IC (« drawdown du signal »)

Usage : python scripts/analyze_rolling_ic_b25.py
"""
import os
import sys

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd

IC_CSV = r"F:\projets\artifacts\metrics\ic_by_regime_b25_daily.csv"
OUT_DIR = r"F:\projets\artifacts\metrics"
WINDOWS = (63, 126, 252)  # 3, 6 et 12 mois de trading


def _neg_streak(s: pd.Series) -> int:
    """Plus longue séquence de valeurs < 0."""
    best = cur = 0
    for v in s:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def main() -> None:
    df = pd.read_csv(IC_CSV)
    df["d"] = pd.to_datetime(df["d"], utc=False)
    df = df.sort_values("d").reset_index(drop=True)

    ic_cols = ["ic_raw", "ic_vs", "ic_sn", "ic_vs_sn"]
    labels = {
        "ic_raw": "IC brut",
        "ic_vs": "IC vol-scalé",
        "ic_sn": "IC sector-neutral",
        "ic_vs_sn": "IC vol-scalé sector-neutral",
    }

    print("=" * 110)
    print("P1-6 — ROLLING IC B25 (rank global H10)")
    print("=" * 110)

    rows = []
    out_cols = ["d"]
    for col in ic_cols:
        s = df[col]
        cum = s.cumsum()
        cum_peak = cum.cummax()
        signal_dd = (cum - cum_peak).min()
        longest_neg = _neg_streak(s)
        rows.append(
            {
                "metrique": labels[col],
                "jours_IC": int(s.notna().sum()),
                "ic_moyen": round(float(s.mean()), 4),
                "ic_ir": round(float(s.mean() / s.std(ddof=0)), 2) if s.std(ddof=0) > 0 else np.nan,
                "pct_jours_pos": round(float((s > 0).mean() * 100), 1),
                "sequence_neg_max": longest_neg,
                "signal_dd_ic": round(float(signal_dd), 2),
            }
        )
        for w in WINDOWS:
            r = s.rolling(w, min_periods=max(10, w // 2)).mean()
            out_cols.append(f"{col}_roll{w}")
            df[f"{col}_roll{w}"] = r
            rows.append(
                {
                    "metrique": f"{labels[col]} — roll {w}j",
                    "jours_IC": int(r.notna().sum()),
                    "ic_moyen": round(float(r.mean()), 4),
                    "ic_ir": round(float(r.mean() / r.std(ddof=0)), 2) if r.std(ddof=0) > 0 else np.nan,
                    "pct_jours_pos": round(float((r > 0).mean() * 100), 1),
                    "sequence_neg_max": _neg_streak(r),
                    "signal_dd_ic": np.nan,
                }
            )
        # fenêtres glissantes : stats des fenêtres 126/252j pour ce col
        for w in (126, 252):
            r = s.rolling(w, min_periods=w).mean().dropna()
            if len(r):
                rows.append(
                    {
                        "metrique": f"{labels[col]} — fenêtres {w}j",
                        "jours_IC": len(r),
                        "ic_moyen": round(float(r.mean()), 4),
                        "ic_ir": round(float(r.mean() / r.std(ddof=0)), 2) if r.std(ddof=0) > 0 else np.nan,
                        "pct_jours_pos": round(float((r > 0).mean() * 100), 1),
                        "sequence_neg_max": np.nan,
                        "signal_dd_ic": np.nan,
                    }
                )

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False))

    # focus ic_sn (référence) : fenêtres 126j détaillées
    print("\nFenêtres 126j de l'IC sector-neutral — pires et meilleures :")
    r126 = df["ic_sn"].rolling(126, min_periods=126).mean().dropna()
    r126 = pd.DataFrame({"fin_fenetre": df["d"].iloc[r126.index], "ic_sn_126j": r126.values})
    print("Pires 5 fenêtres :")
    print(r126.nsmallest(5, "ic_sn_126j").to_string(index=False))
    print("Meilleures 5 fenêtres :")
    print(r126.nlargest(5, "ic_sn_126j").to_string(index=False))

    # évolution annuelle (référence déjà calculée en P1-5, rappel)
    df["year"] = df["d"].dt.year
    print("\nIC sector-neutral moyen par année (rappel) :")
    print(df.groupby("year")["ic_sn"].agg(ic_moyen="mean", jours="count", pct_pos=lambda x: round(float((x > 0).mean() * 100), 1)).round(4).to_string())

    os.makedirs(OUT_DIR, exist_ok=True)
    df[out_cols + ["year"]].to_csv(os.path.join(OUT_DIR, "rolling_ic_b25.csv"), index=False)
    summary.to_csv(os.path.join(OUT_DIR, "rolling_ic_b25_summary.csv"), index=False)
    print(f"\nSauvegardé : {OUT_DIR}\\rolling_ic_b25.csv / _summary.csv")


if __name__ == "__main__":
    main()
