"""Analyse in-sample des 3 runs S7 (feature whitelist) — comparaison appariée sur 39 symboles communs.

Runs :
- bl : artifacts/models_s7_bl (baseline v1 18 feats, WL OFF)
- dc : artifacts/models_s7_dc (directional core 9 feats, WL ON)
- dv : artifacts/models_s7_dv (directional+volume 12 feats, WL ON)

CRBG est exclu partout (skippé dc/dv, insuffisance de données cross/whitelist).
Sortie : rapport console + artifacts/s7_in_sample/rapport.json + rapport.md
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "bl": ("artifacts/models_s7_bl", "S7 exp A baseline (18) WL OFF"),
    "dc": ("artifacts/models_s7_dc", "S7 exp B directional core (9) WL ON"),
    "dv": ("artifacts/models_s7_dv", "S7 exp C directional+volume (12) WL ON"),
}
SYMBOLS_40 = [
    "ACI","ACIW","AGNC","AN","ARQT","AXS","BAH","BJ","BKD","CAKE","CMC","CNM",
    "COMP","CPRI","CRBG","ENS","FLO","FLR","FTV","GEN","INVH","IOT","LEA","LNC",
    "MGY","MKC","MWA","NE","PLNT","RHI","RVLV","RVTY","SHOO","TDC","VIPS","VOYA",
    "VRNS","VTRS","WMG","YETI",
]
EXCLUDE = {"CRBG"}


def _batch_dir(run_dir: str) -> Path:
    base = ROOT / run_dir
    subdirs = sorted([p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")])
    return subdirs[0] if subdirs else base


def _load_config(run_dir: str, symbol: str):
    cfg_path = _batch_dir(run_dir) / symbol / "config.json"
    if not cfg_path.exists():
        return None
    with open(cfg_path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    symbols = [s for s in SYMBOLS_40 if s not in EXCLUDE]
    data = {run: {} for run in RUNS}
    for run, (run_dir, label) in RUNS.items():
        for sym in symbols:
            cfg = _load_config(run_dir, sym)
            if cfg is None:
                data[run][sym] = None
                continue
            data[run][sym] = {
                "architecture": cfg.get("architecture_selected"),
                "selection_mode": cfg.get("selection_mode"),
                "feature_count": len(cfg.get("feature_columns", [])),
                "feature_columns": cfg.get("feature_columns", []),
                "feature_whitelist": (cfg.get("feature_contract") or {}).get("feature_whitelist"),
                "selection_score": cfg.get("champion_selection", {}).get("selection_score")
                if isinstance(cfg.get("champion_selection"), dict) else None,
            }

    # Couverture commune
    common = [s for s in symbols if all(data[r].get(s) is not None for r in RUNS)]
    print("=== S7 analyse in-sample — %d symboles communs (CRBG exclu) ===" % len(common))

    # 1. Vérification features par run
    print("\n--- Features vérifiées par run ---")
    for run, label in RUNS.items():
        counts = Counter(d["feature_count"] for d in data[run].values() if d)
        feats = next((d["feature_columns"] for d in data[run].values() if d), [])
        print(f"  {run} ({label}): count par symbole={dict(counts)} | nb=feat={len(feats)}")

    # 2. Champions par run
    print("\n--- Champions (architecture_selected) par run ---")
    arch_dist = {}
    for run, label in RUNS.items():
        dist = Counter(d["architecture"] for d in data[run].values() if d)
        arch_dist[run] = dist
        print(f"  {run}: {dict(dist)}")

    # 3. Matrice champions (appariée, 39 symboles)
    print("\n--- Matrice champion par symbole × run ---")
    rows = []
    for sym in common:
        arch = [data[r][sym]["architecture"] for r in RUNS]
        rows.append((sym, arch))
    header = "  %-6s %-14s %-14s %-14s %s" % ("sym", "bl", "dc", "dv", "note")
    print(header)
    for sym, arch in rows:
        same = "SAME" if len(set(arch)) == 1 else "DIFF"
        print("  %-6s %-14s %-14s %-14s %s" % (sym, arch[0], arch[1], arch[2], same))

    # 4. Synthèse
    n_diff = sum(1 for _, arch in rows if len(set(arch)) > 1)
    print("\n--- Synthèse ---")
    print("  symboles comparés:", len(common))
    print("  symboles où le champion diffère entre runs:", n_diff, "/", len(common))
    for run, dist in arch_dist.items():
        print("  %s: %s" % (run, dict(dist)))

    # 5. Persistance
    out = ROOT / "artifacts" / "s7_in_sample"
    out.mkdir(parents=True, exist_ok=True)
    report = {"symbols_common": common, "runs": {}, "champion_matrix": rows}
    for run in RUNS:
        report["runs"][run] = {
            "label": RUNS[run][1],
            "architectures": dict(arch_dist[run]),
            "symbols": {s: data[run][s] for s in common},
        }
    (out / "rapport.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = ["# S7 — Analyse in-sample (39 symboles communs)", ""]
    md.append("| Sym | bl (baseline 18) | dc (dir. 9) | dv (dir+vol 12) | Note |")
    md.append("|---|---|---|---|---|")
    for sym, arch in rows:
        note = "SAME" if len(set(arch)) == 1 else "**DIFF**"
        md.append("| %s | %s | %s | %s | %s |" % (sym, arch[0], arch[1], arch[2], note))
    (out / "rapport.md").write_text("\n".join(md), encoding="utf-8")
    print("\n  → rapport.json + rapport.md dans", out)


if __name__ == "__main__":
    main()
