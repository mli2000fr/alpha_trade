"""Analyse — « Quand Oracle TOP se trompe, de combien se trompe-t-il ? »

Source : artifacts/models/oracle/oracle-wf-20260818021140/oos_predictions.parquet
(Oracle TOP P(top10) H20, WF causal 2022-2026).

Méthode :
  - par date, rang pct de proba_top (classement Oracle) et de future_return (vérité) ;
  - top décile Oracle = proba_rank >= 0.9 (les ~10% qu'Oracle juge les meilleurs) ;
  - parmi ces choix, on regarde OÙ ils retombent réellement dans le classement futur
    (true_decile) et leur future_return réalisé → « quand il se trompe, de combien ? »
  - comparaison avec le top décile B25 (global_rank_20) et l'attente aléatoire (10%).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"
OUT = ROOT / "artifacts" / "oracle_top_error.md"


def _analyze(df: pd.DataFrame, label: str, rank_col: str) -> pd.DataFrame:
    r = df.copy()
    r["pred_rank"] = r.groupby("date")[rank_col].rank(pct=True)
    r["true_rank"] = r.groupby("date")["future_return"].rank(pct=True)
    r["true_decile"] = (r["true_rank"] * 10).clip(0, 9).astype(int) + 1
    r["is_top_decile"] = r["pred_rank"] >= 0.9
    top = r[r["is_top_decile"]]
    return top


def _report(top: pd.DataFrame, name: str) -> list[str]:
    lines = []
    n = len(top)
    capture = float((top["true_rank"] >= 0.9).mean())
    lines.append(f"### {name}")
    lines.append("")
    lines.append(f"- Observations dans le top décile prédit : **{n}**")
    lines.append(f"- **Capture** (vrais TOP 10 % atteints) : **{capture:.1%}**")
    lines.append(f"- **Erreur** (choix qui retombent ailleurs) : **{1 - capture:.1%}**")
    lines.append("")
    lines.append("| vrai décile | n | % des choix | future_return moyen | interprétation |")
    lines.append("|---|---|---|---|---|")
    dist = top.groupby("true_decile")["future_return"].agg(["count", "mean"])
    for d in range(1, 11):
        cnt = int(dist.loc[d, "count"]) if d in dist.index else 0
        mu = float(dist.loc[d, "mean"]) if d in dist.index else np.nan
        pct = cnt / n if n else 0.0
        interp = {
            1: "pire décile — catastrophe (très court)",
            2: "très bas",
            3: "bas",
            4: "bas-moyen",
            5: "moyen",
            6: "moyen",
            7: "moyen-haut",
            8: "haut",
            9: "très haut (presque)",
            10: "vrai TOP 10 % (juste)",
        }[d]
        lines.append(f"| D{d} | {cnt} | {pct:.1%} | {mu:+.4f} | {interp} |")
    lines.append("")
    # Quantifier « de combien il se trompe » : distance du vrai rang au seuil top10
    err = top[top["true_rank"] < 0.9]
    if len(err):
        # 0.95 = centre du top décile prédit ; distance moyenne au vrai rang
        lines.append(f"- **Parmi les erreurs ({len(err)} choix)** :")
        lines.append(f"  - vrai rang moyen : {float(err['true_rank'].mean()):.3f} (sur 0..1, 0 = pire)")
        lines.append(f"  - % d'erreurs dans le **pire décile D1** : {float((err['true_decile'] == 1).mean()):.1%}")
        lines.append(f"  - % d'erreurs dans les **3 pires déciles D1-D3** : {float((err['true_decile'] <= 3).mean()):.1%}")
        lines.append(f"  - future_return moyen des erreurs : {float(err['future_return'].mean()):+.4f}")
    lines.append("")
    return lines


def main() -> None:
    df = pd.read_parquet(PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year

    md = ["# Oracle TOP — quand il se trompe, de combien ?", ""]
    md.append(f"Source : `{PARQUET.name}` (WF causal H20, 2022-2026, {len(df):,} obs).")
    md.append("")

    # Full window
    top_oracle = _analyze(df, "Oracle", "proba_top")
    top_b25 = _analyze(df, "B25", "global_rank_20")
    md.append("## Toutes périodes (2022-2026)")
    md += _report(top_oracle, "Top décile ORACLE (P_top)")
    md += _report(top_b25, "Top décile B25 (global_rank_20) — comparaison")

    # OOS final 2025-2026
    oos = df[df["year"] >= 2025]
    top_oracle_oos = _analyze(oos, "Oracle", "proba_top")
    top_b25_oos = _analyze(oos, "B25", "global_rank_20")
    md.append("## OOS final 2025-2026 (hors entraînement)")
    md += _report(top_oracle_oos, "Top décile ORACLE (P_top) — 2025/2026")
    md += _report(top_b25_oos, "Top décile B25 (global_rank_20) — 2025/2026")

    md.append("## Lecture")
    md.append("")
    md.append("- Une distribution **en U** (forte densité D1 ET D10) = Oracle sélectionne l'**amplitude** "
              "(grands gagnants + grands perdants), pas la **direction**.")
    md.append("- « Quand Oracle se trompe » = dans le **pire cas**, ses choix retombent en D1/D2/D3 "
              "(vrais losers) -> l'erreur n'est PAS bénigne, elle est souvent **catastrophique**.")
    md.append("- Conséquence : filtrer/re-rank par Oracle peut retirer des gagnants ET injecter des losers.")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print("\nsaved:", OUT)


if __name__ == "__main__":
    main()
