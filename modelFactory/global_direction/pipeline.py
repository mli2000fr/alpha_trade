"""modelFactory/global_direction/pipeline.py — Pipeline de test GlobalDirection H20.

Oracle = GATE (top ``pool_pct`` du jour par ``proba_extreme``), GlobalDirection
= RANKING (top ``m24`` dans le pool par ``direction_score``). LONG only.

Compare :
    A = Oracle pur          (pool → top m24 par proba_extreme)
    B = Oracle + B25        (pool → top m24 par global_rank_20)
    C = Oracle + GD         (pool → top m24 par direction_score)

Diagnostics obligatoires (sur les picks de chaque variante) :
    D1% · D10% · D10/D1 · mean future_return H20 · median · P(return>0) ·
    coverage · n — + résultats par fold WF, par semestre, par régime.

Critère principal : dans le pool Oracle, gradient des quintiles de
``direction_score`` — direction_score ↑ ⇒ D10 ↑ ET D1 ↓ (gradient stable).

Usage :
    python -m modelFactory.global_direction.pipeline \
        --batch-id model-factory-20260811223551-ef2cd0
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import (
    DECILE_COL,
    DIRECTION_SCORE_COL,
    RETURN_COL,
)
from modelFactory.oracle.config import load_backtest_batch_id

LOGGER = logging.getLogger(__name__)

_GD_ROOT = Path("artifacts/models/global_direction")
_ORACLE_ROOT = Path("artifacts/models/oracle")
_REGIME_FILE = Path("regime_marche/regime.ttx")


# ── Chargement des runs / rangs / labels ──────────────────────────────────

def _latest_run(root: Path, prefix: str, tag_batch: str | None = None) -> Path | None:
    """Dernier run ``prefix-*`` ; si ``tag_batch``, préfère un run taggé au batch."""
    if not root.exists():
        return None
    runs = sorted(root.glob(f"{prefix}-*"))
    if not runs:
        return None
    if tag_batch:
        for r in reversed(runs):
            tagf = r / "batch_id.txt"
            if tagf.exists() and tagf.read_text(encoding="utf-8").strip() == tag_batch:
                return r
    return runs[-1]


def load_run_oos(run_dir: Path) -> pd.DataFrame:
    df = pd.read_parquet(run_dir / "oos_predictions.parquet")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date", "symbol"])
    return df


def load_b25_ranks(engine: Any, batch_id: str) -> pd.DataFrame:
    """Rangs B25 H10 + H20 depuis ``global_rank_history`` (baselines B0/B1)."""
    query = text(
        "SELECT `date`, symbol, global_rank_10, global_rank_20 "
        "FROM global_rank_history WHERE batch_id = :bid"
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"bid": batch_id}, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df.dropna(subset=["date", "symbol"])


def load_regime_map(path: Path = _REGIME_FILE) -> dict[pd.Timestamp, str]:
    """Date (normalisée) → régime depuis regime_marche/regime.ttx.

    Le fichier est un CSV « sale » : la colonne ``Justification_Historique``
    contient des virgules → on parse manuellement (split sur les 3 premières
    virgules) au lieu de ``read_csv``.
    """
    out: dict[pd.Timestamp, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line or i == 0:
                continue
            parts = line.split(",", 3)  # date_debut, date_fin, regime, justification
            if len(parts) < 3:
                continue
            try:
                start = pd.Timestamp(str(parts[0]).strip()).normalize()
                end = pd.Timestamp(str(parts[1]).strip()).normalize()
                regime = str(parts[2]).strip().lower()
            except Exception:
                continue
            cur = start
            while cur <= end:
                out[cur] = regime
                cur += pd.Timedelta(days=1)
    return out


# ── Sélection des variantes ───────────────────────────────────────────────

def build_pool(combined: pd.DataFrame, pool_pct: float) -> pd.DataFrame:
    """Pool Oracle : top ``pool_pct`` du jour par proba_extreme (PIT)."""
    df = combined.dropna(subset=["proba_extreme"]).copy()
    df["_eg_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df["_pool"] = df["_eg_pct"] >= (1.0 - float(pool_pct))
    return df


def select_top_m24(pool: pd.DataFrame, score_col: str, m24: int) -> pd.DataFrame:
    """Dans le pool, top ``m24`` par ``score_col`` (par date, LONG only)."""
    parts: list[pd.DataFrame] = []
    for _, g in pool[pool["_pool"]].groupby("date"):
        g = g.dropna(subset=[score_col])
        if g.empty:
            continue
        g = g.sort_values(score_col, ascending=False)
        parts.append(g.head(int(m24)))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


# ── Diagnostics ───────────────────────────────────────────────────────────

def compute_metrics(picks: pd.DataFrame, label: str = "") -> dict[str, Any]:
    if picks is None or picks.empty:
        return {"label": label, "n": 0}
    n = len(picks)
    d1 = int((picks[DECILE_COL] == 1).sum())
    d10 = int((picks[DECILE_COL] == 10).sum())
    middle = int(((picks[DECILE_COL] >= 2) & (picks[DECILE_COL] <= 9)).sum())
    fr = pd.to_numeric(picks[RETURN_COL], errors="coerce")
    # Distribution complète D1..D10 + composites (BAD5/GOOD5/VERY_BAD/VERY_GOOD)
    probs = {f"D{d}": 100.0 * float((picks[DECILE_COL] == d).mean()) for d in range(1, 11)}
    bad5 = sum(probs[f"D{d}"] for d in range(1, 6))
    good5 = sum(probs[f"D{d}"] for d in range(6, 11))
    very_bad = 5 * probs["D1"] + 4 * probs["D2"] + 3 * probs["D3"] + 2 * probs["D4"] + probs["D5"]
    very_good = probs["D6"] + 2 * probs["D7"] + 3 * probs["D8"] + 4 * probs["D9"] + 5 * probs["D10"]
    return {
        "label": label,
        "d1_pct": 100.0 * d1 / n,
        "middle_pct": 100.0 * middle / n,
        "d10_pct": 100.0 * d10 / n,
        "good_bad": (d10 / max(1, d1)),  # GOOD/BAD = D10/D1
        "mean_ret": float(fr.mean()) if fr.notna().any() else float("nan"),
        "median_ret": float(fr.median()) if fr.notna().any() else float("nan"),
        "p_pos": 100.0 * float((fr > 0).mean()) if fr.notna().any() else float("nan"),
        "coverage": int(picks["date"].nunique()),
        "n": n,
        **probs,
        "bad5": bad5, "good5": good5,
        "very_bad": very_bad, "very_good": very_good,
    }


def quintile_gradient(pool: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Gradient par quintile (cross-sectionnel par jour) de ``score_col``.

    Critère principal : Q1 (bas) → Q5 (haut) doit montrer D10 ↑, D1 ↓ et
    GOOD/BAD (D10/D1) ↑. Colonnes : n, D1%, Middle%, D10%, GOOD/BAD, mean, med.
    """
    df = pool[pool["_pool"]].dropna(subset=[score_col, DECILE_COL]).copy()
    if df.empty:
        return pd.DataFrame()
    df["_q"] = (
        np.floor(df.groupby("date")[score_col].rank(pct=True).clip(upper=1 - 1e-9) * 5)
        .clip(0, 4).astype(int) + 1
    )
    rows: list[dict[str, Any]] = []
    for q in range(1, 6):
        g = df[df["_q"] == q]
        m = compute_metrics(g, label=f"Q{q}")
        m["quintile"] = q
        rows.append(m)
    return pd.DataFrame(rows)


def fold_go_reproducibility(pool: pd.DataFrame, score_col: str, key: str = "fold_start") -> pd.DataFrame:
    """GO pré-enregistré par fold : Q5 doit avoir D1 ↓, D10 ↑ et GOOD/BAD ↑ vs Q1.

    Returns: frame (bucket, ok, d1_delta, d10_delta, good_bad_q1, good_bad_q5, n_q1, n_q5).
    """
    df = pool[pool["_pool"]].dropna(subset=[score_col, DECILE_COL, key]).copy()
    if df.empty:
        return pd.DataFrame()
    df["_q"] = (
        np.floor(df.groupby("date")[score_col].rank(pct=True).clip(upper=1 - 1e-9) * 5)
        .clip(0, 4).astype(int) + 1
    )
    rows: list[dict[str, Any]] = []
    for k, g in df.groupby(key):
        q1 = g[g["_q"] == 1]
        q5 = g[g["_q"] == 5]
        if q1.empty or q5.empty:
            continue
        def _s(x):
            n = len(x)
            d1 = 100.0 * (x[DECILE_COL] == 1).mean()
            d10 = 100.0 * (x[DECILE_COL] == 10).mean()
            gb = (x[DECILE_COL] == 10).sum() / max(1, (x[DECILE_COL] == 1).sum())
            return n, d1, d10, gb
        n1, d1q1, d10q1, gb1 = _s(q1)
        n5, d1q5, d10q5, gb5 = _s(q5)
        ok = bool((d1q5 < d1q1) and (d10q5 > d10q1) and (gb5 > gb1))
        rows.append({
            "bucket": k, "ok": ok,
            "d1_delta": d1q5 - d1q1, "d10_delta": d10q5 - d10q1,
            "good_bad_q1": gb1, "good_bad_q5": gb5,
            "n_q1": n1, "n_q5": n5,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def breakdown(pool: pd.DataFrame, variant_picks: dict[str, pd.DataFrame], key: str) -> pd.DataFrame:
    """Métriques (mean_ret, D1%, D10%) par ``key`` (fold/semestre/régime)."""
    rows: list[dict[str, Any]] = []
    for label, picks in variant_picks.items():
        if picks.empty:
            continue
        if key == "semester":
            picks = picks.copy()
            picks["_bk"] = pd.to_datetime(picks["date"]).dt.to_period("Q").astype(str).str[:4] + \
                "-" + np.where(pd.to_datetime(picks["date"]).dt.month <= 6, "H1", "H2")
        elif key == "fold":
            picks = picks.copy()
            picks["_bk"] = picks["fold_start"].astype(str).str[:4]
        elif key == "regime":
            regime_map = load_regime_map()
            picks = picks.copy()
            picks["_bk"] = pd.to_datetime(picks["date"]).dt.normalize().map(regime_map).fillna("unknown")
        else:
            continue
        for bk, g in picks.groupby("_bk"):
            m = compute_metrics(g)
            rows.append({"bucket": bk, "variant": label,
                         "mean_ret": m["mean_ret"], "d1_pct": m["d1_pct"],
                         "d10_pct": m["d10_pct"], "n": m["n"]})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["bucket", "variant"])


# ── Rapport ───────────────────────────────────────────────────────────────

def _fmt_metrics(m: dict[str, Any]) -> str:
    if not m or m.get("n", 0) == 0:
        return "—"
    return (f"D1={m['d1_pct']:.1f}% Mid={m['middle_pct']:.1f}% D10={m['d10_pct']:.1f}% "
            f"GOOD/BAD={m['good_bad']:.2f} "
            f"mean={m['mean_ret']*100:+.2f}% med={m['median_ret']*100:+.2f}% "
            f"P>0={m['p_pos']:.1f}% cov={m['coverage']} n={m['n']}")


def quintile_distribution(pool: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Distribution D1..D10 + composites par quintile de ``score_col`` (pool).

    Composites (GPT) :
    - BAD5     = P(D1-D5) ; GOOD5 = P(D6-D10) ;
    - VERY_BAD = 5·P(D1)+4·P(D2)+3·P(D3)+2·P(D4)+P(D5) ;
    - VERY_GOOD = P(D6)+2·P(D7)+3·P(D8)+4·P(D9)+5·P(D10).
    Le vrai gradient recherché : Q1→Q5 ⇒ P(D1..D5) ↓ et P(D6..D10) ↑.
    """
    df = pool[pool["_pool"]].dropna(subset=[score_col, DECILE_COL]).copy()
    if df.empty:
        return pd.DataFrame()
    df["_q"] = (
        np.floor(df.groupby("date")[score_col].rank(pct=True).clip(upper=1 - 1e-9) * 5)
        .clip(0, 4).astype(int) + 1
    )
    rows: list[dict[str, Any]] = []
    for q in range(1, 6):
        g = df[df["_q"] == q]
        n = len(g)
        probs = {d: 100.0 * float((g[DECILE_COL] == d).mean()) for d in range(1, 11)}
        row: dict[str, Any] = {"quintile": q, "n": n}
        row.update({f"D{d}": probs[d] for d in range(1, 11)})
        row["BAD5"] = sum(probs[d] for d in range(1, 6))
        row["GOOD5"] = sum(probs[d] for d in range(6, 11))
        row["VERY_BAD"] = 5 * probs[1] + 4 * probs[2] + 3 * probs[3] + 2 * probs[4] + probs[5]
        row["VERY_GOOD"] = probs[6] + 2 * probs[7] + 3 * probs[8] + 4 * probs[9] + 5 * probs[10]
        rows.append(row)
    return pd.DataFrame(rows)


def _dist_gradient_summary(dist: pd.DataFrame) -> str:
    """Résumé de monotonie de la distribution D1..D10 sur les quintiles."""
    if len(dist) < 2:
        return "—"
    bad_mono = all(bool(dist[f"D{d}"].is_monotonic_decreasing) for d in range(1, 6))
    good_mono = all(bool(dist[f"D{d}"].is_monotonic_increasing) for d in range(6, 11))
    return (f"P(D1-D5) décroissant ({'OUI' if bad_mono else 'NON'}), "
            f"P(D6-D10) croissant ({'OUI' if good_mono else 'NON'})")


def _fmt_dist(dist: pd.DataFrame) -> str:
    """Formate la distribution D1..D10 par quintile en tableau."""
    hdr = ("Q   n      " + " ".join(f"{f'D{d}':>5}" for d in range(1, 11))
           + "  BAD5 GOOD5 V_BAD V_GOOD")
    lines = [hdr]
    for _, r in dist.iterrows():
        cells = " ".join(f"{r[f'D{d}']:>5.1f}" for d in range(1, 11))
        lines.append(
            f"Q{int(r['quintile'])} {int(r['n']):>6} {cells} "
            f"{r['BAD5']:>5.1f} {r['GOOD5']:>5.1f} {r['VERY_BAD']:>5.1f} {r['VERY_GOOD']:>6.1f}"
        )
    return "\n".join(lines)


def run_pipeline(
    *,
    batch_id: str,
    gd_runs: dict[str, str] | str | None,
    oracle_run: str | None,
    pool_pct: float,
    m24: int,
) -> dict[str, Any]:
    engine = get_sqlalchemy_engine()

    oracle_dir = (_ORACLE_ROOT / oracle_run) if oracle_run else _latest_run(_ORACLE_ROOT, "oracle-wf", batch_id)
    if oracle_dir is None or not oracle_dir.exists():
        raise SystemExit("Aucun run Oracle trouvé.")
    oracle = load_run_oos(oracle_dir)
    ranks = load_b25_ranks(engine, batch_id)

    # Normaliser gd_runs en {label: run_dir}
    if isinstance(gd_runs, str):
        gd_runs = {"C_Oracle+GD": gd_runs}
    elif gd_runs is None:
        latest = _latest_run(_GD_ROOT, "global-direction-wf", batch_id)
        gd_runs = {"C_Oracle+GD": latest.name if latest else None}
    resolved: dict[str, Path] = {}
    for label, run in gd_runs.items():
        d = (_GD_ROOT / run) if run else _latest_run(_GD_ROOT, "global-direction-wf", batch_id)
        if d is None or not d.exists():
            raise SystemExit(f"Run GlobalDirection introuvable : {run}")
        resolved[label] = d

    # Fusionner tous les runs GD sur (date, symbol) ; déciles/rendement du 1er.
    base: pd.DataFrame | None = None
    gd_score_cols: dict[str, str] = {}
    for label, d in resolved.items():
        gd = load_run_oos(d)
        need = {DECILE_COL, RETURN_COL}
        if not need.issubset(gd.columns):
            raise SystemExit(f"Run GD {label} illisible (attendues {sorted(need)}) : {list(gd.columns)}")
        score_col = "gd_" + "".join(c for c in label if c.isalnum())
        gd = gd.rename(columns={DIRECTION_SCORE_COL: score_col})
        gd_score_cols[label] = score_col
        if base is None:
            # fold_start = fold WF (commun à tous les runs GD) — conservé pour
            # le diagnostic GO par fold.
            base = gd[["date", "symbol", score_col, DECILE_COL, RETURN_COL, "fold_start"]].copy()
        else:
            base = base.merge(gd[["date", "symbol", score_col]], on=["date", "symbol"], how="inner")
    assert base is not None
    combined = base.merge(
        oracle[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner"
    )
    combined = combined.merge(
        ranks[["date", "symbol", "global_rank_10", "global_rank_20"]],
        on=["date", "symbol"], how="left",
    )
    if combined.empty:
        raise SystemExit("Aucun chevauchement GD ∩ Oracle.")

    pool = build_pool(combined, pool_pct)
    n_pool_dates = int(pool[pool["_pool"]]["date"].nunique())
    n_pool_obs = int(pool["_pool"].sum())

    variant_picks: dict[str, pd.DataFrame] = {
        "A_Oracle": select_top_m24(pool, "proba_extreme", m24),
        "B0_Oracle+B25H10": select_top_m24(pool, "global_rank_10", m24),
        "B1_Oracle+B25H20": select_top_m24(pool, "global_rank_20", m24),
    }
    for label, sc in gd_score_cols.items():
        variant_picks[label] = select_top_m24(pool, sc, m24)

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"GLOBALDIRECTION H20 — PIPELINE (Oracle gate top {pool_pct*100:.0f}% → TOP {m24})")
    lines.append(f"GD runs : {', '.join(resolved.keys())} | Oracle run : {oracle_dir.name} | batch : {batch_id}")
    lines.append(f"Pool Oracle top{pool_pct*100:.0f}% : {n_pool_dates} dates, {n_pool_obs} obs")
    lines.append("=" * 72)

    lines.append("\n--- VARIANTES (TOP %d dans le pool, LONG only) ---" % m24)
    lines.append(f"{'Variante':<22}{'D1%':>7}{'Mid%':>7}{'D10%':>7}{'GOOD/BAD':>9}{'mean':>8}{'med':>8}{'P>0':>7}{'cov':>6}{'n':>7}")
    metrics_all: dict[str, dict[str, Any]] = {}
    for label, picks in variant_picks.items():
        m = compute_metrics(picks, label)
        metrics_all[label] = m
        if m["n"] == 0:
            lines.append(f"{label:<22}  (aucun pick)")
            continue
        lines.append(
            f"{label:<22}{m['d1_pct']:>6.1f}%{m['middle_pct']:>6.1f}%{m['d10_pct']:>6.1f}%"
            f"{m['good_bad']:>9.2f}{m['mean_ret']*100:>+7.2f}%{m['median_ret']*100:>+7.2f}%"
            f"{m['p_pos']:>6.1f}%{m['coverage']:>6}{m['n']:>7}"
        )

    # Distribution complète D1..D10 + composites (BAD5/GOOD5/VERY_BAD/VERY_GOOD) par variante
    lines.append("\n--- DISTRIBUTION D1..D10 PAR VARIANTE (sélection top %d) ---" % m24)
    lines.append("Variante   " + " ".join(f"{f'D{d}':>5}" for d in range(1, 11))
                 + "  BAD5 GOOD5 V_BAD V_GOOD")
    for label, m in metrics_all.items():
        if m["n"] == 0:
            continue
        cells = " ".join(f"{m[f'D{d}']:>5.1f}" for d in range(1, 11))
        lines.append(
            f"{label:<11}{cells} {m['bad5']:>5.1f} {m['good5']:>5.1f} "
            f"{m['very_bad']:>5.1f} {m['very_good']:>6.1f}"
        )

    # Critère principal (V2/GPT) : distribution D1..D10 par quintile, par run GD
    gradients: dict[str, pd.DataFrame] = {}
    go_by: dict[str, pd.DataFrame] = {}
    for label, sc in gd_score_cols.items():
        dist = quintile_distribution(pool, sc)
        gradients[label] = dist
        lines.append(f"\n--- CRITÈRE PRINCIPAL — {label} : distribution D1..D10 par quintile (pool Oracle) ---")
        if dist.empty:
            lines.append("  (vide)")
        else:
            lines.append(_fmt_dist(dist))
            lines.append("→ " + _dist_gradient_summary(dist))
        go = fold_go_reproducibility(pool, sc, "fold_start")
        go_by[label] = go
        if not go.empty:
            n_ok = int(go["ok"].sum())
            lines.append(f"→ GO par fold (Q5 : D1↓, D10↑, GOOD/BAD↑) : {n_ok}/{len(go)} folds satisfaits.")

    lines.append("\n--- PAR FOLD WF (mean_ret %) ---")
    bd = breakdown(pool, variant_picks, "fold")
    if not bd.empty:
        lines.append(bd.pivot(index="bucket", columns="variant", values="mean_ret")
                     .reindex(columns=list(variant_picks)).to_string())
    lines.append("\n--- PAR SEMESTRE (mean_ret %) ---")
    bs = breakdown(pool, variant_picks, "semester")
    if not bs.empty:
        lines.append(bs.pivot(index="bucket", columns="variant", values="mean_ret")
                     .reindex(columns=list(variant_picks)).to_string())
    lines.append("\n--- PAR RÉGIME (mean_ret %) ---")
    br = breakdown(pool, variant_picks, "regime")
    if not br.empty:
        lines.append(br.pivot(index="bucket", columns="variant", values="mean_ret")
                     .reindex(columns=list(variant_picks)).to_string())

    report = "\n".join(lines)
    return {
        "report": report,
        "metrics": {label: compute_metrics(p) for label, p in variant_picks.items()},
        "gradients": gradients,
        "go_by_fold": go_by,
        "variant_picks": variant_picks,
        "pool": pool,
        "gd_runs": {k: v.name for k, v in resolved.items()},
        "oracle_run": oracle_dir.name,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de test GlobalDirection H20.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--gd-run", action="append", default=None,
                        help="Nom d'un run GlobalDirection (répétable, ex. --gd-run C1:x --gd-run C2:y).")
    parser.add_argument("--oracle-run", default=None, help="Nom du run Oracle (sinon dernier taggé).")
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--m24", type=int, default=24)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    gd_runs: dict[str, str] | str | None = None
    if args.gd_run:
        gd_runs = {}
        for item in args.gd_run:
            if ":" in item:
                label, run = item.split(":", 1)
                gd_runs[label] = run
            else:
                gd_runs["C_Oracle+GD"] = item

    result = run_pipeline(
        batch_id=batch_id,
        gd_runs=gd_runs,
        oracle_run=args.oracle_run,
        pool_pct=args.pool_pct,
        m24=args.m24,
    )
    print(result["report"])


if __name__ == "__main__":
    main()
