"""E4-B1b — Diagnostic earnings conditionnel à Oracle Extreme (UP vs DOWN).

Sans modèle. Population = pool Oracle Extreme (oracle_extreme10=1) restreint à
l'UNIVERS DE TRADE REEL (config/ticket_recherche.txt, 400 symboles),
target future_return_H20 : UP (>0) vs DOWN (<0).

Sources earnings : STRICTEMENT séparées (E4-B1a). Ici on teste l'hypothèse
SEC baseline YoY (croissance YoY réalisée, PIT à earnings_date) — le consensus
Finnhub n'a pas d'historique (0-2 sym/an 2015-25, 28 en 2026).

Features PIT (disponibles avant D) :
  eps_yoy_growth     = eps_actual / eps_actual(t-1 même période) - 1
  revenue_yoy_growth = idem
  days_since_earnings
  days_to_next_earnings
  post_earnings_1d / post_earnings_3d  (réaction cumulée APRÈS publication,
    utilisée UNIQUEMENT si déjà réalisée avant D : D >= date_next_k)

Buckets de fraîcheur (fixés à l'avance) : 0-1, 2-5, 6-10, 11-20, 21-40, 40+.

Diagnostics par feature x période (2022,2023,2024,2025,2026H1,ALL) et par bucket :
  AUC(UP/DOWN), mean/median UP vs DOWN, Cohen's d, p-value (Mann-Whitney = AUC),
  N, coverage.

Diagnostic secondaire (E3/E4-A) : BOTTOM ratés 2025-26 vs TOP capturés 2025-26.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

DATA = "artifacts/models/oracle/e2_feature_dataset.parquet"
OOS = "artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet"
TICKET = Path("config/ticket_recherche.txt")
OUT = "artifacts/models/oracle/e4b1b_earnings_diag.md"

FRESH_BUCKETS = [(0, 1), (2, 5), (6, 10), (11, 20), (21, 40), (40, 10**9)]
PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]

# Features à diagnostiquer (colonnes du df enrichi)
DIAG_FEATS = [
    "eps_yoy_growth", "revenue_yoy_growth",
    "days_since_earnings", "days_to_next_earnings",
    "post_earnings_1d", "post_earnings_3d",
]


def _auc(y: np.ndarray, s: np.ndarray) -> float:
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 10 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    try:
        u, _ = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        auc = u / (np.sum(y == 1) * np.sum(y == 0))
    except ValueError:
        return float("nan")
    return float(auc)


def _pval(y: np.ndarray, s: np.ndarray) -> float:
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 10 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    try:
        _, p = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        return float(p)
    except ValueError:
        return float("nan")


def _cohen_d(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna().to_numpy(dtype=float)
    b = b.dropna().to_numpy(dtype=float)
    if len(a) < 10 or len(b) < 10:
        return float("nan")
    sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
    if sp < 1e-12:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def _classify_sec(df: pd.DataFrame) -> pd.DataFrame:
    """Marque chaque ligne earnings : SEC baseline YoY / actual-only / consensus / unknown."""
    def parse_fp(fp):
        if not fp:
            return (None, None, None)
        fp = str(fp).strip()
        if len(fp) >= 5 and fp[:4].isdigit() and fp[4:] in ("Q1", "Q2", "Q3", "Q4", "FY"):
            return (int(fp[:4]), fp[4:], {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}[fp[4:]])
        return (None, None, None)

    df[["fy", "fp", "fp_rank"]] = df["fiscal_period"].apply(lambda x: pd.Series(parse_fp(x)))
    d = df.sort_values(["symbol", "fy", "fp_rank"])
    d["prev_eps_actual"] = d.groupby(["symbol", "fp_rank"])["eps_actual"].shift(1)
    d["prev_rev_actual"] = d.groupby(["symbol", "fp_rank"])["revenue_actual"].shift(1)
    est_ok = d["eps_estimate"].notna() & (d["eps_estimate"] != 0)
    same = (est_ok & d["prev_eps_actual"].notna() & (d["prev_eps_actual"] != 0) &
            ((d["eps_estimate"] - d["prev_eps_actual"]).abs() <= 1e-6 * d["eps_estimate"].abs().clip(lower=1.0)))
    d["source_eps"] = "unknown"
    d.loc[~est_ok & d["eps_actual"].notna(), "source_eps"] = "sec_actual_only"
    d.loc[est_ok & same, "source_eps"] = "sec_yoy_baseline"
    d.loc[est_ok & d["prev_eps_actual"].notna() & ~same, "source_eps"] = "finnhub_consensus"
    d.loc[est_ok & ~d["prev_eps_actual"].notna(), "source_eps"] = "sec_yoy_baseline"
    # croissance YoY (pour baseline + actual-only) : utilise eps_actual vs prev
    d["eps_yoy_growth"] = np.where(
        d["prev_eps_actual"].notna() & (d["prev_eps_actual"] != 0),
        d["eps_actual"] / d["prev_eps_actual"] - 1.0, np.nan)
    d["revenue_yoy_growth"] = np.where(
        d["prev_rev_actual"].notna() & (d["prev_rev_actual"] != 0),
        d["revenue_actual"] / d["prev_rev_actual"] - 1.0, np.nan)
    return d


def main() -> None:
    # ── Univers de trade réel (400 symboles) ──
    ticket_syms = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    print(f"univers 400 (ticket_recherche) : {len(ticket_syms)} symboles")

    # ── Population Extreme UP/DOWN ──
    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    for c_ in ("date",):
        ds[c_] = pd.to_datetime(ds[c_]).dt.normalize()
        oos[c_] = pd.to_datetime(oos[c_]).dt.normalize()
    m = ds.merge(oos[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner")
    m["true_top"] = (m["oracle_pct_rank"] >= 0.90).astype(int)
    m["true_bottom"] = (m["oracle_pct_rank"] <= 0.10).astype(int)
    m["oracle_rank"] = m.groupby("date")["proba_extreme"].rank(pct=True)
    m["pred_top"] = (m["oracle_rank"] >= 0.90).astype(int)
    m["grp"] = np.select(
        [(m["pred_top"] == 1) & (m["true_top"] == 1),
         (m["pred_top"] == 0) & (m["true_bottom"] == 1),
         (m["pred_top"] == 1) & (m["true_bottom"] == 1)],
        ["TOP_capture", "BOTTOM_rate", "BOTTOM_capture"], default="other")
    m["period"] = np.where(m["date"].dt.year < 2026, m["date"].dt.year.astype(str), "2026H1")
    # Population principale : pool Extreme (vrais extrêmes) restreint aux 400 symboles
    extreme = m[m["oracle_extreme10"] == 1].copy()
    extreme["up"] = (extreme["future_return"] > 0).astype(int)
    # retirer les zero-return (ni up ni down)
    extreme = extreme[extreme["future_return"] != 0].copy()
    extreme = extreme[extreme["symbol"].isin(set(ticket_syms))].copy()
    print(f"pool Extreme (restreint 400): {len(extreme):,} | UP={int((extreme['up']==1).sum()):,} "
          f"DOWN={int((extreme['up']==0).sum()):,}")

    # ── Earnings (source SEC uniquement) ──
    eng = get_sqlalchemy_engine()
    earn = pd.read_sql(text(
        "SELECT symbol, earnings_date, eps_estimate, eps_actual, revenue_estimate, revenue_actual, fiscal_period "
        "FROM stock_earnings_calendar"), eng)
    earn["symbol"] = earn["symbol"].astype(str).str.upper()
    earn["earnings_date"] = pd.to_datetime(earn["earnings_date"]).dt.normalize()
    earn = _classify_sec(earn)
    # garder les sources SEC exploitables (baseline YoY + actual-only) ; exclure consensus & unknown
    sec = earn[earn["source_eps"].isin(["sec_yoy_baseline", "sec_actual_only"])].copy()
    print(f"earnings SEC: {len(sec):,} | baseline={int((sec['source_eps']=='sec_yoy_baseline').sum()):,} "
          f"actual_only={int((sec['source_eps']=='sec_actual_only').sum()):,}")

    # ── Features PIT au jour D (dernier earnings <= D, PIT strict) ──
    # Boucle par symbole avec searchsorted : fiable, pas de piège merge_asof.
    ex = extreme.sort_values(["symbol", "date"]).reset_index(drop=True)
    sec_sorted = sec.sort_values(["symbol", "earnings_date"])
    earn_by_sym = {s: g for s, g in sec_sorted.groupby("symbol")}
    # réaction post-earnings : daily_return par (symbol, date)
    daily = ds[["symbol", "date", "daily_return"]].dropna().sort_values(["symbol", "date"])
    dmap = {s: g for s, g in daily.groupby("symbol")}
    n_rows = len(ex)
    last_date = np.full(n_rows, np.nan, dtype="datetime64[ns]")
    eps_g = np.full(n_rows, np.nan)
    rev_g = np.full(n_rows, np.nan)
    next_date = np.full(n_rows, np.nan, dtype="datetime64[ns]")
    post1 = np.full(n_rows, np.nan)
    post3 = np.full(n_rows, np.nan)
    for sym, g in ex.groupby("symbol", sort=False):
        eg = earn_by_sym.get(sym)
        if eg is None:
            continue
        edates = eg["earnings_date"].to_numpy()
        idx = ex.index[ex["symbol"] == sym]
        dts = ex.loc[idx, "date"].to_numpy()
        pos = np.searchsorted(edates, dts, side="right") - 1  # dernier <= D
        ok = pos >= 0
        last_date[idx[ok]] = edates[pos[ok]]
        eps_g[idx[ok]] = eg["eps_yoy_growth"].to_numpy()[pos[ok]]
        rev_g[idx[ok]] = eg["revenue_yoy_growth"].to_numpy()[pos[ok]]
        npos = np.searchsorted(edates, dts, side="left")  # premier > D
        nok = npos < len(edates)
        next_date[idx[nok]] = edates[npos[nok]]
        # réaction post-earnings : return des k premiers jours ouvrés après last earnings
        dg = dmap.get(sym)
        if dg is not None:
            ddates = dg["date"].to_numpy()
            drets = dg["daily_return"].to_numpy()
            for j, (orig_idx, d0, d_last) in enumerate(zip(idx[ok], dts[ok], edates[pos[ok]])):
                p = np.searchsorted(ddates, d_last, side="right")
                if p < len(ddates):
                    post1[orig_idx] = drets[p]
                    if p + 2 < len(ddates):
                        post3[orig_idx] = (1 + drets[p]) * (1 + drets[p + 1]) * (1 + drets[p + 2]) - 1.0
    feat = pd.DataFrame({
        "last_earnings_date": last_date,
        "eps_yoy_growth": eps_g,
        "revenue_yoy_growth": rev_g,
        "next_earnings_date": next_date,
        "post_earnings_1d": post1,
        "post_earnings_3d": post3,
    }, index=ex.index)
    # attention : NaT -> float numpy donne un très grand négatif, pas NaN -> masquer explicitement
    last_nat = pd.isna(feat["last_earnings_date"]).to_numpy()
    next_nat = pd.isna(feat["next_earnings_date"]).to_numpy()
    d_since = (ex["date"].to_numpy() - feat["last_earnings_date"].to_numpy()).astype("timedelta64[D]").astype(float)
    d_next = (feat["next_earnings_date"].to_numpy() - ex["date"].to_numpy()).astype("timedelta64[D]").astype(float)
    d_since[last_nat] = np.nan
    d_next[next_nat] = np.nan
    feat["days_since_earnings"] = d_since
    feat["days_to_next_earnings"] = d_next
    # PIT : la réaction n'est utilisable que si D est APRÈS la réaction (D >= date_next_k)
    # Simplification conservative : si days_since_earnings < 2 -> post_1d non dispo ; <4 -> post_3d non dispo
    feat.loc[feat["days_since_earnings"] < 2, "post_earnings_1d"] = np.nan
    feat.loc[feat["days_since_earnings"] < 4, "post_earnings_3d"] = np.nan

    # bucket de fraîcheur
    ds_since = feat["days_since_earnings"].fillna(10**9)
    feat["fresh_bucket"] = pd.cut(
        ds_since,
        bins=[-1] + [b[1] for b in FRESH_BUCKETS],
        labels=[f"{a}-{b}" if b < 10**9 else f"{a}+" for a, b in FRESH_BUCKETS],
    )

    full = ex.reset_index(drop=True).join(feat.reset_index(drop=True), how="left")
    # réattacher period/up/grp déjà dans ex (reset_index conserve tout)
    full = full.copy()
    print(f"full: {len(full):,} | couv. eps_yoy: {full['eps_yoy_growth'].notna().mean()*100:.1f}% | "
          f"couv. revenue_yoy: {full['revenue_yoy_growth'].notna().mean()*100:.1f}% | "
          f"couv. post_1d: {full['post_earnings_1d'].notna().mean()*100:.1f}%")

    # ── Diagnostic UP/DOWN par période ──
    md: list[str] = [
        "# E4-B1b — Diagnostic earnings conditionnel à Oracle Extreme (UP vs DOWN)",
        "",
        f"Population : pool Oracle Extreme (oracle_extreme10=1, future_return!=0) restreint aux "
        f"{len(ticket_syms)} symboles de l'univers de trade (`config/ticket_recherche.txt`). N={len(full):,} "
        f"(UP {int((full['up']==1).sum()):,} / DOWN {int((full['up']==0).sum()):,}).",
        "Source : SEC baseline YoY (croissance YoY réalisée, PIT). Consensus Finnhub EXCLU (pas d'historique).",
        "AUC = Mann-Whitney U normalisé (UP=1). p = test bilatéral. Strictement PIT.",
        "",
    ]
    for per in PERIODS:
        sub = full if per == "ALL" else full[full["period"] == per]
        if sub.empty:
            continue
        md.append(f"## UP/DOWN {per} (N={len(sub):,}, UP={int((sub['up']==1).sum()):,}, "
                  f"DOWN={int((sub['up']==0).sum()):,})")
        md.append("")
        md.append("| feature | AUC | mean UP | mean DOWN | median UP | median DOWN | Cohen d | p | N | cov% |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for f in DIAG_FEATS:
            s2 = sub[["up", f]].dropna()
            if len(s2) < 20:
                md.append(f"| {f} | - | - | - | - | - | - | - | {len(s2)} | 0 |")
                continue
            y = s2["up"].to_numpy()
            s = s2[f].to_numpy()
            up_v = s2.loc[s2["up"] == 1, f]
            dn_v = s2.loc[s2["up"] == 0, f]
            md.append(
                f"| {f} | {_auc(y, s):.3f} | {up_v.mean():.4f} | {dn_v.mean():.4f} | "
                f"{up_v.median():.4f} | {dn_v.median():.4f} | {_cohen_d(up_v, dn_v):+.3f} | "
                f"{_pval(y, s):.2e} | {len(s2):,} | {len(s2)/len(sub)*100:.0f} |"
            )

    # ── Diagnostic par bucket de fraîcheur (ALL) ──
    md.append("")
    md.append("## UP/DOWN par fraîcheur depuis earnings (ALL)")
    md.append("")
    md.append("| bucket (jours) | N | UP% | AUC eps_yoy | AUC post_1d | AUC post_3d |")
    md.append("|---|---|---|---|---|---|")
    for b in FRESH_BUCKETS:
        lab = f"{b[0]}-{b[1]}" if b[1] < 10**9 else f"{b[0]}+"
        sub = full[full["fresh_bucket"].astype(str) == lab]
        if sub.empty:
            continue
        row = f"| {lab} | {len(sub):,} | {sub['up'].mean()*100:.1f}% "
        for f in ("eps_yoy_growth", "post_earnings_1d", "post_earnings_3d"):
            s2 = sub[["up", f]].dropna()
            if len(s2) >= 20:
                row += f"| {_auc(s2['up'].to_numpy(), s2[f].to_numpy()):.3f} "
            else:
                row += "| - "
        md.append(row + "|")

    # ── Diagnostic secondaire : BOTTOM ratés vs TOP capturés (E3/E4-A) ──
    md.append("")
    md.append("## Secondaire : BOTTOM ratés vs TOP capturés — par période")
    md.append("")
    for per in PERIODS:
        sub = full if per == "ALL" else full[full["period"] == per]
        sub = sub[sub["grp"].isin(["BOTTOM_rate", "TOP_capture"])]
        if sub.empty:
            continue
        md.append(f"### {per} (N={len(sub):,}, BOTTOM_rate={int((sub['grp']=='BOTTOM_rate').sum()):,}, "
                  f"TOP_capture={int((sub['grp']=='TOP_capture').sum()):,})")
        md.append("")
        md.append("| feature | AUC(BOTTOM=1) | mean BOTTOM | mean TOP | median BOTTOM | median TOP | d | N |")
        md.append("|---|---|---|---|---|---|---|---|")
        for f in DIAG_FEATS:
            s2 = sub[["grp", f]].dropna()
            if len(s2) < 20:
                md.append(f"| {f} | - | - | - | - | - | - | {len(s2)} |")
                continue
            y = (s2["grp"] == "BOTTOM_rate").astype(int).to_numpy()
            s = s2[f].to_numpy()
            br = s2.loc[s2["grp"] == "BOTTOM_rate", f]
            tc = s2.loc[s2["grp"] == "TOP_capture", f]
            md.append(
                f"| {f} | {_auc(y, s):.3f} | {br.mean():.4f} | {tc.mean():.4f} | "
                f"{br.median():.4f} | {tc.median():.4f} | {_cohen_d(br, tc):+.3f} | {len(s2):,} |"
            )

    # ── Permutation null benchmark (shuffle labels) : features principales ──
    md.append("")
    md.append("## Permutation null (AUC sous labels permutés, 200 répliques, pool Extreme UP/DOWN ALL)")
    md.append("")
    md.append("| feature | AUC observé | p25 null | p50 null | p95 null | p99 null | p_perm (|AUC|>0.03) |")
    md.append("|---|---|---|---|---|---|---|")
    rng = np.random.default_rng(42)
    for f in DIAG_FEATS:
        s2 = full[["up", f]].dropna()
        if len(s2) < 1000:
            md.append(f"| {f} | - | - | - | - | - | - |")
            continue
        y0 = s2["up"].to_numpy()
        s0 = s2[f].to_numpy()
        obs = _auc(y0, s0)
        # null par permutation des labels (échantillon borné pour la vitesse)
        n = min(len(y0), 6000)
        idx = rng.choice(len(y0), n, replace=False)
        ys, ss = y0[idx], s0[idx]
        null = np.array([_auc(ys[rng.permutation(n)], ss) for _ in range(200)])
        null = null[np.isfinite(null)]
        if len(null) < 50:
            md.append(f"| {f} | {obs:.3f} | - | - | - | - | - |")
            continue
        p_perm = float(np.mean(np.abs(null - 0.5) >= abs(obs - 0.5)))
        md.append(
            f"| {f} | {obs:.3f} | {np.percentile(null,25):.3f} | {np.percentile(null,50):.3f} | "
            f"{np.percentile(null,95):.3f} | {np.percentile(null,99):.3f} | {p_perm:.3f} |"
        )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
