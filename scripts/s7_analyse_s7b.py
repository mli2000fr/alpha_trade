"""S7-B — Pipeline réel (champion sélectionné) + analyse oracle architecture (diagnostic).

Niveau A (obligatoire) : pour chaque run (bl/dc/dv), prendre le CHAMPION sélectionné
par selection_score (is_selected_model=1) pour chaque symbole, puis comparer les
métriques du champion sur les 39 symboles communs.

Niveau B (secondaire, diagnostic uniquement — AUCUN changement de pipeline) :
si on avait choisi l'architecture sur max directional_accuracy (ou max test_f1_macro)
au lieu de selection_score, qu'aurait-on obtenu ? Compare les "oracle champions".

Aucune modification de selection_score. Aucune optimisation.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine

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


def _wilcoxon(a, b):
    if not _HAS_SCIPY or len(a) != len(b) or len(a) < 6:
        return float("nan")
    try:
        return float(_scipy_stats.wilcoxon(a, b).pvalue)
    except Exception:
        return float("nan")


def _stats(vals):
    v = [x for x in vals if x is not None and np.isfinite(x)]
    if not v:
        return {"n": 0, "mean": None, "median": None, "std": None}
    return {
        "n": len(v),
        "mean": float(np.mean(v)),
        "median": float(np.median(v)),
        "std": float(np.std(v)),
    }


def _paired(a, b):
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


def _load_all():
    eng = get_sqlalchemy_engine()
    run_ids = {run: {} for run in RUNS}
    for run, (run_dir, _label) in RUNS.items():
        for sym in SYMBOLS:
            cfg_path = _batch_dir(run_dir) / sym / "config.json"
            if not cfg_path.exists():
                continue
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            run_ids[run][sym] = cfg.get("run_id")

    all_rids = {rid for m in run_ids.values() for rid in m.values()}
    gov = {}
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
    met = {}
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
    return run_ids, gov, met


def _per_symbol_metric(run_ids, gov, met, picker):
    """Retourne {run: {sym: value}} où picker(gov_row, dacc) -> value ou None."""
    out = {run: {sym: None for sym in SYMBOLS} for run in RUNS}
    for run in RUNS:
        for sym in SYMBOLS:
            rid = run_ids[run].get(sym)
            if not rid or rid not in gov:
                continue
            dacc = (met.get(rid) or {}).get if False else None
            dacc_map = met.get(rid) or {}
            out[run][sym] = picker(gov[rid], dacc_map)
    return out


def main() -> None:
    run_ids, gov, met = _load_all()

    # ---------------------------------------------------------------
    # Niveau A — Champion actuel (is_selected_model=1)
    # ---------------------------------------------------------------
    champ_arch = {run: {} for run in RUNS}
    for run in RUNS:
        for sym in SYMBOLS:
            rid = run_ids[run].get(sym)
            if not rid or rid not in gov:
                continue
            for mname, row in gov[rid].items():
                if row["is_selected"]:
                    champ_arch[run][sym] = mname

    print("=== S7-B niveau A — CHAMPION ACTUEL (selection_score) ===")
    for run in RUNS:
        dist = Counter(champ_arch[run].values())
        print("  %s champion dist: %s" % (run, dict(dist)))

    champ_metrics = {
        "selection_score": {run: {sym: (gov[run_ids[run][sym]][champ_arch[run][sym]]["selection_score"] if sym in champ_arch[run] else None) for sym in SYMBOLS} for run in RUNS},
        "test_f1_macro": {run: {sym: (gov[run_ids[run][sym]][champ_arch[run][sym]]["test_f1_macro"] if sym in champ_arch[run] else None) for sym in SYMBOLS} for run in RUNS},
        "directional_accuracy": {run: {sym: ((met.get(run_ids[run][sym]) or {}).get(champ_arch[run][sym]) if sym in champ_arch[run] else None) for sym in SYMBOLS} for run in RUNS},
    }

    md = ["# S7-B — Pipeline réel (champion sélectionné par selection_score)", ""]
    md.append("## Niveau A — Champion actuel (39 symboles communs)")
    md.append("")
    md.append("| Métrique | run | n | mean | median | | paire | delta | % améliorés | p |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for metric in ["selection_score", "test_f1_macro", "directional_accuracy"]:
        for run in RUNS:
            st = _stats(list(champ_metrics[metric][run].values()))
            md.append("| %s | %s | %d | %.4f | %.4f | | | | | |" % (metric, run, st["n"], st["mean"] or 0, st["median"] or 0))
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(champ_metrics[metric][ra], champ_metrics[metric][rb])
            md.append("| %s (paire) | %s->%s | %d | %+.4f | %.0f%% | | | | | %s |" % (
                metric, ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100,
                ("%.4f" % pr["wilcoxon_p"]) if pr["wilcoxon_p"] is not None else "n/a"))
        md.append("")
        print("\n[champion] %s" % metric)
        for run in RUNS:
            st = _stats(list(champ_metrics[metric][run].values()))
            print("  %s: n=%d mean=%.4f med=%.4f" % (run, st["n"], st["mean"] or 0, st["median"] or 0))
        for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
            pr = _paired(champ_metrics[metric][ra], champ_metrics[metric][rb])
            print("  %s->%s: delta=%+.4f (%d sym, %.0f%% améliorés, p=%s)" % (
                ra, rb, pr["delta_mean"] or 0, pr["n"], (pr["pct_improved"] or 0) * 100,
                ("%.4f" % pr["wilcoxon_p"]) if pr["wilcoxon_p"] is not None else "n/a"))

    # ---------------------------------------------------------------
    # Niveau B — Oracle architecture (diagnostic) : choisir sur dacc / f1
    # ---------------------------------------------------------------
    print("\n=== S7-B niveau B — ORACLE architecture (diagnostic) ===")

    def _oracle(metric_key):
        """Choisit l'arch avec max(metric) par symbole (oracle), pas selection_score."""
        orac_arch = {run: {} for run in RUNS}
        for run in RUNS:
            for sym in SYMBOLS:
                rid = run_ids[run].get(sym)
                if not rid or rid not in gov:
                    continue
                best, bestval = None, None
                for mname, row in gov[rid].items():
                    if metric_key == "directional_accuracy":
                        val = (met.get(rid) or {}).get(mname)
                    else:
                        val = row.get(metric_key)
                    if val is None:
                        continue
                    if bestval is None or val > bestval:
                        best, bestval = mname, val
                orac_arch[run][sym] = best
        return orac_arch

    for metric_key, label in [("directional_accuracy", "directional_accuracy (test)"), ("test_f1_macro", "test_f1_macro")]:
        oa = _oracle(metric_key)
        print("\n  Oracle sur %s — distribution arch par run:" % label)
        for run in RUNS:
            dist = Counter(oa[run].values())
            print("    %s: %s" % (run, dict(dist)))
        # métriques de l'oracle (dacc + f1 + selection_score de l'arch oracle)
        orac_metrics = {
            "selection_score": {run: {sym: (gov[run_ids[run][sym]][oa[run][sym]]["selection_score"] if sym in oa[run] else None) for sym in SYMBOLS} for run in RUNS},
            "test_f1_macro": {run: {sym: (gov[run_ids[run][sym]][oa[run][sym]]["test_f1_macro"] if sym in oa[run] else None) for sym in SYMBOLS} for run in RUNS},
            "directional_accuracy": {run: {sym: ((met.get(run_ids[run][sym]) or {}).get(oa[run][sym]) if sym in oa[run] else None) for sym in SYMBOLS} for run in RUNS},
        }
        md.append("## Niveau B — Oracle architecture (diagnostic : max %s)" % label)
        md.append("")
        md.append("| Métrique | run | n | mean | | paire | delta | % améliorés |")
        md.append("|---|---|---|---|---|---|---|---|")
        for mm in ["selection_score", "test_f1_macro", "directional_accuracy"]:
            for run in RUNS:
                st = _stats(list(orac_metrics[mm][run].values()))
                md.append("| %s | %s | %d | %.4f | | | | |" % (mm, run, st["n"], st["mean"] or 0))
            for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
                pr = _paired(orac_metrics[mm][ra], orac_metrics[mm][rb])
                md.append("| %s (paire) | %s->%s | %d | %+.4f | %.0f%% | | |" % (
                    mm, ra, rb, pr["n"], pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100))
            md.append("")
        print("  [oracle %s] métriques :" % label)
        for mm in ["selection_score", "test_f1_macro", "directional_accuracy"]:
            for run in RUNS:
                st = _stats(list(orac_metrics[mm][run].values()))
                print("    %s %s: mean=%.4f" % (mm, run, st["mean"] or 0))
            for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]:
                pr = _paired(orac_metrics[mm][ra], orac_metrics[mm][rb])
                print("    %s %s->%s: delta=%+.4f (%.0f%% améliorés)" % (mm, ra, rb, pr["delta_mean"] or 0, (pr["pct_improved"] or 0) * 100))

    out = ROOT / "artifacts" / "s7_in_sample"
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "niveau_a_champion": {mm: {run: _stats(list(champ_metrics[mm][run].values())) for run in RUNS} for mm in champ_metrics},
        "niveau_a_paired": {mm: {f"{ra}->{rb}": _paired(champ_metrics[mm][ra], champ_metrics[mm][rb]) for (ra, rb) in [("bl", "dc"), ("bl", "dv"), ("dc", "dv")]} for mm in champ_metrics},
        "champion_architecture": {run: dict(Counter(champ_arch[run].values())) for run in RUNS},
    }
    (out / "rapport_s7b.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "rapport_s7b.md").write_text("\n".join(md), encoding="utf-8")
    print("\n  ->", out / "rapport_s7b.md")


if __name__ == "__main__":
    main()
