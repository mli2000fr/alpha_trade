"""S7-A — Feature effect contrôlé par architecture (in-sample).

Pour chacune des 3 architectures (lstm_attention, lightgbm, catboost), comparer
BL (18 feats) vs DC (9 feats) vs DV (12 feats) sur les 39 symboles communs.
Objectif : isoler l'effet des features sans confondre avec le champion.

Métriques par architecture (model_governance / model_metrics) :
  - selection_score
  - test_f1_macro
  - directional_accuracy (model_metrics, split=test)
  - IC in-sample LSTM (wf_preds parquet : proba vs future_return)

Comparaisons appariées : DC-BL, DV-BL, DV-DC (delta moyen, % symboles améliorés,
test de Wilcoxon signé).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "bl": ("artifacts/models_s7_bl", "baseline (18)"),
    "dc": ("artifacts/models_s7_dc", "directional core (9)"),
    "dv": ("artifacts/models_s7_dv", "directional+volume (12)"),
}
ARCHS = ["lstm_attention", "lightgbm", "catboost"]
SYMBOLS_40 = [
    "ACI","ACIW","AGNC","AN","ARQT","AXS","BAH","BJ","BKD","CAKE","CMC","CNM",
    "COMP","CPRI","CRBG","ENS","FLO","FLR","FTV","GEN","INVH","IOT","LEA","LNC",
    "MGY","MKC","MWA","NE","PLNT","RHI","RVLV","RVTY","SHOO","TDC","VIPS","VOYA",
    "VRNS","VTRS","WMG","YETI",
]
EXCLUDE = {"CRBG"}
SYMBOLS = [s for s in SYMBOLS_40 if s not in EXCLUDE]

try:
    from scipy import stats as _scipy_stats
    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _HAS_SCIPY = False


def _batch_dir(run_dir: str) -> Path:
    base = ROOT / run_dir
    subdirs = sorted([p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")])
    return subdirs[0] if subdirs else base


def _wilcoxon(a: list[float], b: list[float]) -> float:
    if not _HAS_SCIPY:
        return float("nan")
    if len(a) != len(b) or len(a) < 6:
        return float("nan")
    try:
        return float(_scipy_stats.wilcoxon(a, b).pvalue)
    except Exception:
        return float("nan")


def _stats(vals: list[float]) -> dict:
    v = [x for x in vals if x is not None and np.isfinite(x)]
    if not v:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n": len(v),
        "mean": float(np.mean(v)),
        "median": float(np.median(v)),
        "std": float(np.std(v)),
        "min": float(np.min(v)),
        "max": float(np.max(v)),
    }


def _paired(a: dict, b: dict, label_a: str, label_b: str) -> dict:
    """Comparaison appariée sur les symboles communs de 2 runs."""
    keys = [k for k in a if k in b and a[k] is not None and b[k] is not None and np.isfinite(a[k]) and np.isfinite(b[k])]
    if not keys:
        return {"n": 0, "delta_mean": None, "pct_improved": None, "wilcoxon_p": None}
    da = [a[k] for k in keys]
    db = [b[k] for k in keys]
    delta = [db[i] - da[i] for i in range(len(keys))]
    return {
        "n": len(keys),
        "delta_mean": float(np.mean(delta)),
        "pct_improved": float(np.mean([1 if d > 0 else 0 for d in delta])),
        "wilcoxon_p": _wilcoxon(da, db),
    }


def main() -> None:
    eng = get_sqlalchemy_engine()

    # 1. run_ids per-symbol depuis les config.json
    run_ids = {run: {} for run in RUNS}
    config = {run: {} for run in RUNS}
    for run, (run_dir, _label) in RUNS.items():
        for sym in SYMBOLS:
            cfg_path = _batch_dir(run_dir) / sym / "config.json"
            if not cfg_path.exists():
                continue
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            config[run][sym] = cfg
            run_ids[run][sym] = cfg.get("run_id")

    # 2. governance + metrics (bulk)
    all_rids = {rid for m in run_ids.values() for rid in m.values()}
    gov = {}  # rid -> {model_name: row}
    with eng.connect() as c:
        rows = c.execute(
            text(
                "SELECT run_id, model_name, selection_score, test_f1_macro, is_selected_model, `rank` "
                "FROM model_governance WHERE run_id IN :rids"
            ).bindparams(bindparam("rids", expanding=True)),
            {"rids": sorted(all_rids)},
        ).fetchall()
    for r in rows:
        gov.setdefault(r[0], {})[r[1]] = {
            "selection_score": float(r[2]) if r[2] is not None else None,
            "test_f1_macro": float(r[3]) if r[3] is not None else None,
            "is_selected": bool(r[4]),
            "rank": r[5],
        }

    met = {}  # rid -> {model_name: directional_accuracy (test)}
    with eng.connect() as c:
        rows = c.execute(
            text(
                "SELECT run_id, model_name, directional_accuracy FROM model_metrics "
                "WHERE run_id IN :rids AND split_name = 'test'"
            ).bindparams(bindparam("rids", expanding=True)),
            {"rids": sorted(all_rids)},
        ).fetchall()
    for r in rows:
        if r[2] is not None:
            met.setdefault(r[0], {})[r[1]] = float(r[2])

    # 3. IC LSTM in-sample depuis wf_preds
    ic = {run: {} for run in RUNS}
    for run, (run_dir, _label) in RUNS.items():
        wf_dir = _batch_dir(run_dir) / "_per_symbol_wf_preds"
        for sym in SYMBOLS:
            p = wf_dir / f"{sym}.parquet"
            if not p.exists():
                continue
            try:
                df = pd.read_parquet(p)
                if len(df) >= 5 and "proba_long" in df and "future_return" in df:
                    ic[run][sym] = float(df["proba_long"].corr(df["future_return"], method="spearman"))
            except Exception:
                continue

    # 4. Rapports par architecture
    out = ROOT / "artifacts" / "s7_in_sample"
    out.mkdir(parents=True, exist_ok=True)
    report = {"runs": {}, "architectures": {}, "couverture": {}}
    for run in RUNS:
        report["runs"][run] = {"label": RUNS[run][1], "run_id_example": next(iter(run_ids[run].values()), None)}

    md = ["# S7-A — Feature effect contrôlé par architecture (in-sample, 39 symboles)", ""]
    for arch in ARCHS:
        md.append(f"## Architecture : `{arch}`")
        md.append("")
        # collecter les métriques par run
        coll = {run: {sym: None for sym in SYMBOLS} for run in RUNS}
        coll_f1 = {run: {sym: None for sym in SYMBOLS} for run in RUNS}
        coll_dacc = {run: {sym: None for sym in SYMBOLS} for run in RUNS}
        for run in RUNS:
            for sym in SYMBOLS:
                rid = run_ids[run].get(sym)
                if rid and rid in gov and arch in gov[rid]:
                    coll[run][sym] = gov[rid][arch]["selection_score"]
                    coll_f1[run][sym] = gov[rid][arch]["test_f1_macro"]
                if rid and rid in met and arch in met[rid]:
                    coll_dacc[run][sym] = met[rid][arch]

        md.append("### selection_score (moyenne/échantillon par symbole)")
        md.append("| run | n | mean | median | std | min | max |")
        md.append("|---|---|---|---|---|---|---|")
        for run in RUNS:
            st = _stats(list(coll[run].values()))
            md.append("| %s (%s) | %d | %.4f | %.4f | %.4f | %.4f | %.4f |" % (
                run, RUNS[run][1], st["n"], st["mean"] or 0, st["median"] or 0, st["std"] or 0, st["min"] or 0, st["max"] or 0))
        md.append("")
        md.append("**Comparaisons appariées (selection_score)**")
        md.append("| paire | n | delta_mean | % symboles améliorés | Wilcoxon p |")
        md.append("|---|---|---|---|---|")
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(coll[ra], coll[rb], ra, rb)
            md.append("| %s->%s | %d | %+.4f | %.0f%% | %s |" % (
                ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100,
                ("%.4f" % pr["wilcoxon_p"]) if pr["wilcoxon_p"] is not None else "n/a"))
        md.append("")

        md.append("### test_f1_macro")
        md.append("| run | n | mean | median | | paire | delta | % améliorés |")
        md.append("|---|---|---|---|---|---|---|---|")
        for run in RUNS:
            st = _stats(list(coll_f1[run].values()))
            md.append("| %s | %d | %.4f | %.4f | | | | |" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(coll_f1[ra], coll_f1[rb], ra, rb)
            md.append("| %s->%s | %d | %+.4f | %.0f%% | | | |" % (ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100))
        md.append("")

        md.append("### directional_accuracy (test)")
        md.append("| run | n | mean | median | | paire | delta | % améliorés |")
        md.append("|---|---|---|---|---|---|---|---|")
        for run in RUNS:
            st = _stats(list(coll_dacc[run].values()))
            md.append("| %s | %d | %.4f | %.4f | | | | |" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(coll_dacc[ra], coll_dacc[rb], ra, rb)
            md.append("| %s->%s | %d | %+.4f | %.0f%% | | | |" % (ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100))
        md.append("")

        report["architectures"][arch] = {
            "selection_score": {run: _stats(list(coll[run].values())) for run in RUNS},
            "paired_selection": {f"{ra}->{rb}": _paired(coll[ra], coll[rb], ra, rb) for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]},
            "test_f1_macro": {run: _stats(list(coll_f1[run].values())) for run in RUNS},
            "directional_accuracy": {run: _stats(list(coll_dacc[run].values())) for run in RUNS},
        }
        print(f"\n=== {arch} — selection_score ===")
        for run in RUNS:
            st = _stats(list(coll[run].values()))
            print("  %s: n=%d mean=%.4f med=%.4f" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(coll[ra], coll[rb], ra, rb)
            print("  %s->%s: delta=%+.4f (%d sym, %.0f%% améliorés, p=%s)" % (
                ra, rb, pr["delta_mean"] or 0, pr["n"], (pr["pct_improved"] or 0) * 100,
                ("%.4f" % pr["wilcoxon_p"]) if pr["wilcoxon_p"] is not None else "n/a"))
        print(f"  {arch} test_f1_macro:", {run: (_stats(list(coll_f1[run].values()))["mean"]) for run in RUNS})
        print(f"  {arch} directional_accuracy(test):", {run: (_stats(list(coll_dacc[run].values()))["mean"]) for run in RUNS})

    # 5. IC LSTM in-sample
    md.append("## IC LSTM in-sample (wf_preds : proba vs future_return, Spearman)")
    md.append("| run | n | mean IC | median IC | | paire | delta IC | % améliorés |")
    md.append("|---|---|---|---|---|---|---|---|")
    for run in RUNS:
        st = _stats(list(ic[run].values()))
        md.append("| %s | %d | %.4f | %.4f | | | | |" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
    for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
        pr = _paired(ic[ra], ic[rb], ra, rb)
        md.append("| %s->%s | %d | %+.4f | %.0f%% | | | |" % (ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100))
    print("\n=== IC LSTM in-sample ===")
    for run in RUNS:
        st = _stats(list(ic[run].values()))
        print("  %s: n=%d mean=%.4f med=%.4f" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
    for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
        pr = _paired(ic[ra], ic[rb], ra, rb)
        print("  %s->%s IC: delta=%+.4f (%d sym, %.0f%% améliorés, p=%s)" % (
            ra, rb, pr["delta_mean"] or 0, pr["n"], (pr["pct_improved"] or 0) * 100,
            ("%.4f" % pr["wilcoxon_p"]) if pr["wilcoxon_p"] is not None else "n/a"))

    report["ic_lstm_in_sample"] = {run: _stats(list(ic[run].values())) for run in RUNS}
    report["ic_lstm_paired"] = {f"{ra}->{rb}": _paired(ic[ra], ic[rb], ra, rb) for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]}

    (out / "rapport_s7a.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "rapport_s7a.md").write_text("\n".join(md), encoding="utf-8")
    print("\n  ->", out / "rapport_s7a.md")


if __name__ == "__main__":
    main()

