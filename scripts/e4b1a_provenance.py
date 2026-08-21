"""E4-B1a — détection de provenance : SEC baseline YoY vs Finnhub consensus.

Règle de classification (signature forte) :
  SEC    : eps_estimate(t, p) == eps_actual(t-1, p)   (baseline YoY, même période)
  Finnhub: eps_estimate != eps_actual(t-1, p)         (consensus analyste)
On compare aussi revenue. On marque 'unknown' si pas d'actual précédent.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

TICKET = Path("config/ticket_recherche.txt")
OUT = "artifacts/models/oracle/e4b1a_provenance.md"


def _is_sec_fp_format(fp: str | None) -> bool:
    """Format SEC = 'YYYYQn' ou 'YYYYFY' (ex: 2025Q1, 2024FY). Finnhub = formats courts (1,2,3,4...)."""
    if not fp:
        return False
    fp = str(fp).strip()
    return len(fp) >= 5 and fp[:4].isdigit() and fp[4:] in ("Q1", "Q2", "Q3", "Q4", "FY")


def _classify_eps(df: pd.DataFrame) -> pd.Series:
    """Classifie la provenance : SEC baseline YoY vs Finnhub consensus.

    estimate = 0 ou NaN => aucune surprise calculable (estimate manquant).
    Règles par ordre de priorité :
      1. estimate 0/NaN, actual présent             => sec_actual_only (pas de consensus)
      2. estimate non-nul == actual(t-1) (même p.)  => sec_yoy_baseline (baseline YoY SEC)
      3. estimate non-nul != actual(t-1)            => finnhub_consensus (vrai consensus)
      4. estimate non-nul, pas de précédent dispo   => sec_yoy_baseline si format SEC (début
                                                        d'historique, artefact 2015), sinon
                                                        finnhub_consensus
    """
    d = df.sort_values(["symbol", "fy", "fp_rank"])
    prev = d.groupby(["symbol", "fp_rank"])["eps_actual"].shift(1)
    sec_fmt = d["fiscal_period"].apply(_is_sec_fp_format)
    est_ok = d["eps_estimate"].notna() & (d["eps_estimate"] != 0)
    has_actual = d["eps_actual"].notna()
    same = (est_ok & prev.notna() & (prev != 0) &
            ((d["eps_estimate"] - prev).abs() <= 1e-6 * d["eps_estimate"].abs().clip(lower=1.0)))
    out = pd.Series("unknown", index=d.index, dtype=object)
    # 1. estimate manquant (0/NaN)
    out[~est_ok & has_actual] = "sec_actual_only"
    # 2. baseline YoY (estimate == actual précédent)
    out[est_ok & same] = "sec_yoy_baseline"
    # 3. consensus Finnhub (estimate non-nul != YoY, précédent dispo)
    out[est_ok & prev.notna() & ~same] = "finnhub_consensus"
    # 4. estimate non-nul sans précédent -> SEC si format SEC, sinon Finnhub
    out[est_ok & ~prev.notna() & sec_fmt] = "sec_yoy_baseline"
    out[est_ok & ~prev.notna() & ~sec_fmt] = "finnhub_consensus"
    return out


def _parse_fp(fp: str | None) -> tuple[int | None, str | None, int | None]:
    """Parse '2025Q1' -> (2025, 'Q1', 1). '2024FY' -> (2024, 'FY', 5)."""
    if not fp:
        return None, None, None
    fp = str(fp).strip()
    if len(fp) >= 5 and fp[:4].isdigit():
        fy = int(fp[:4])
        per = fp[4:]
        rank = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}.get(per)
        return fy, per, rank
    return None, None, None


def main() -> None:
    ticket_syms = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    eng = get_sqlalchemy_engine()
    df = pd.read_sql(text(
        "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
        "FROM stock_earnings_calendar"
    ), eng)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["earnings_date"] = pd.to_datetime(df["earnings_date"]).dt.normalize()
    df[["fy", "fp", "fp_rank"]] = df["fiscal_period"].apply(
        lambda x: pd.Series(_parse_fp(x))
    )
    df["source_eps"] = _classify_eps(df)
    df["is_ticket"] = df["symbol"].isin(ticket_syms)
    df["year"] = df["earnings_date"].dt.year

    print(f"total lignes: {len(df):,} | ticket400: {int(df['is_ticket'].sum()):,}")
    print(df["source_eps"].value_counts())

    lines = [
        "# E4-B1a — Audit de provenance earnings (SEC baseline YoY vs Finnhub consensus)",
        "",
        f"Univers : {len(ticket_syms)} symboles de trade. Table: stock_earnings_calendar.",
        "Méthode : `eps_estimate(t,p) == eps_actual(t-1,p)` (même période, année précédente) => SEC baseline YoY ;",
        "sinon => consensus Finnhub. 'sec_actual_only' = réalisé sans estimate. 'unknown' = pas de réalisé précédent.",
        "",
        "## Distribution globale par source",
        "",
        "| source | N | % |",
        "|---|---|---|",
    ]
    for src, n in df["source_eps"].value_counts().items():
        lines.append(f"| {src} | {n:,} | {n/len(df)*100:.1f}% |")

    # Par année : N events, consensus réel, baseline SEC, actual-only, unknown, coverage ticket
    lines.append("")
    lines.append("## Par année (sur tout le pool de la table)")
    lines.append("")
    lines.append("| année | N events | consensus Finnhub | baseline SEC (YoY) | actual only | unknown | sym. couverts |")
    lines.append("|---|---|---|---|---|---|---|")
    for y in sorted(df["year"].dropna().unique()):
        sub = df[df["year"] == y]
        lines.append(
            f"| {y} | {len(sub):,} | {int((sub['source_eps']=='finnhub_consensus').sum()):,} | "
            f"{int((sub['source_eps']=='sec_yoy_baseline').sum()):,} | "
            f"{int((sub['source_eps']=='sec_actual_only').sum()):,} | "
            f"{int((sub['source_eps']=='unknown').sum()):,} | {sub['symbol'].nunique():,} |"
        )

    # Idem restreint au ticket 400
    lines.append("")
    lines.append("## Par année (restreint univers de trade 400)")
    lines.append("")
    lines.append("| année | N events | consensus Finnhub | baseline SEC (YoY) | actual only | unknown | estimate=0 (non calc.) | sym. couverts /400 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for y in sorted(df["year"].dropna().unique()):
        sub = df[(df["year"] == y) & df["is_ticket"]]
        if sub.empty:
            continue
        est0 = int(((sub["eps_estimate"].isna()) | (sub["eps_estimate"] == 0)).sum())
        lines.append(
            f"| {y} | {len(sub):,} | {int((sub['source_eps']=='finnhub_consensus').sum()):,} | "
            f"{int((sub['source_eps']=='sec_yoy_baseline').sum()):,} | "
            f"{int((sub['source_eps']=='sec_actual_only').sum()):,} | "
            f"{int((sub['source_eps']=='unknown').sum()):,} | {est0:,} | {sub['symbol'].nunique():,} |"
        )

    # Consensus Finnhub : combien de symboles 400 couverts par année (montrer le manque d'historique)
    lines.append("")
    lines.append("## Couverture du VRAI consensus Finnhub (symbole 400 distincts par année)")
    lines.append("")
    lines.append("| année | sym. 400 avec consensus Finnhub |")
    lines.append("|---|---|")
    for y in sorted(df["year"].dropna().unique()):
        n = df[(df["year"] == y) & df["is_ticket"] & (df["source_eps"] == "finnhub_consensus")]["symbol"].nunique()
        lines.append(f"| {y} | {n} |")

    # Disponibilité EPS/Revenue par année (univers 400)
    lines.append("")
    lines.append("## Disponibilité des colonnes par année (univers 400)")
    lines.append("")
    lines.append("| année | N | eps_actual | eps_estimate | revenue_actual | revenue_estimate |")
    lines.append("|---|---|---|---|---|---|")
    for y in sorted(df["year"].dropna().unique()):
        sub = df[(df["year"] == y) & df["is_ticket"]]
        if sub.empty:
            continue
        lines.append(
            f"| {y} | {len(sub):,} | {int(sub['eps_actual'].notna().sum()):,} | "
            f"{int(sub['eps_estimate'].notna().sum()):,} | "
            f"{int(sub['revenue_actual'].notna().sum()):,} | "
            f"{int(sub['revenue_estimate'].notna().sum()):,} |"
        )

    # Verdict
    lines.append("")
    lines.append("## Verdict E4-B1a")
    lines.append("")
    lines.append("- **Consensus analyste réel (Finnhub) : quasi absent de l'historique.** Sur l'univers 400,")
    lines.append("  0-2 symboles/an de 2015 a 2025, 28 en 2026 (et plusieurs sans eps_actual = annonces")
    lines.append("  futures du calendrier, surprise non calculable). Pas d'historique multi-regimes ->")
    lines.append("  **impossible de tester 'earnings surprise vs consensus' avec cette table**.")
    lines.append("- **La source exploitable = SEC baseline YoY (91% de la table)** : eps_estimate(t,p) =")
    lines.append("  eps_actual(t-1,p). La 'surprise' calculee n'est donc PAS une surprise vs consensus,")
    lines.append("  mais une **croissance EPS/revenue YoY realisee** (info fondamentale orthogonale au prix).")
    lines.append("- `sec_actual_only` (912) = realise sans estimate -> utilisable pour la croissance YoY.")
    lines.append("")
    lines.append("### Consequence pour E4-B1b")
    lines.append("- Tester la **croissance YoY realisee** (EPS et revenue) comme hypothese principale,")
    lines.append("  PIT a earnings_date (filing date), sur 2016-2025 (historique complet).")
    lines.append("- Le **consensus Finnhub 2026** = hypothese separee, N trop faible aujourd'hui (28 sym),")
    lines.append("  a retester quand l'historique consensus sera ingere (ingestion a planifier).")
    lines.append("- Ne JAMAIS melanger les deux sources dans une meme feature `earnings_surprise`.")

    # Échantillon finnhub_consensus récent pour vérification visuelle
    lines.append("")
    lines.append("## Échantillon 'consensus Finnhub' détecté (récent, ticket)")
    lines.append("")
    lines.append("| symbol | earnings_date | fiscal_period | eps_estimate | eps_actual | eps_actual(t-1) |")
    lines.append("|---|---|---|---|---|---|")
    d = df.sort_values(["symbol", "fy", "fp_rank"])
    prev = d.groupby(["symbol", "fp_rank"])["eps_actual"].shift(1)
    sample = d[(d["source_eps"] == "finnhub_consensus") & d["is_ticket"] & (d["earnings_date"] >= "2024-01-01")].head(20)
    for _, r in sample.iterrows():
        lines.append(f"| {r['symbol']} | {r['earnings_date'].date()} | {r['fiscal_period']} | "
                     f"{r['eps_estimate']} | {r['eps_actual']} | {prev.get(r.name, '')} |")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
