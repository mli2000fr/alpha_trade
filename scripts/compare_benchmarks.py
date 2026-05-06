"""Phase F / S23.1 — Compare deux rapports ``pytest-benchmark`` JSON et bloque
toute régression > 20 % sur la moyenne d'un benchmark donné.

Usage::

    pytest tests/benchmarks --benchmark-json=current.json
    python scripts/compare_benchmarks.py \
        --baseline artifacts/benchmarks/baseline.json \
        --current current.json \
        --max-regression-pct 20

Exit codes :
    0 — OK (pas de régression > seuil)
    1 — Régression détectée
    2 — Erreur (fichier manquant/illisible)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _index_by_name(report: dict) -> dict[str, float]:
    """Map ``fullname -> mean_seconds`` depuis un rapport pytest-benchmark."""
    out: dict[str, float] = {}
    for entry in report.get("benchmarks", []):
        name = entry.get("fullname") or entry.get("name")
        stats = entry.get("stats", {})
        mean = stats.get("mean")
        if name and isinstance(mean, (int, float)):
            out[name] = float(mean)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--max-regression-pct", type=float, default=20.0)
    parser.add_argument("--strict-missing", action="store_true",
                        help="Échoue si un benchmark baseline n'est pas présent dans current.")
    args = parser.parse_args()

    for p in (args.baseline, args.current):
        if not p.exists():
            print(f"[bench-compare] fichier absent : {p}", file=sys.stderr)
            return 2

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        current = json.loads(args.current.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[bench-compare] JSON illisible : {exc}", file=sys.stderr)
        return 2

    base_idx = _index_by_name(baseline)
    cur_idx = _index_by_name(current)

    if not base_idx:
        print("[bench-compare] baseline vide — premier run, OK")
        return 0

    regressions: list[tuple[str, float, float, float]] = []
    missing: list[str] = []
    print(f"[bench-compare] seuil régression = +{args.max_regression_pct} %")
    for name, base_mean in sorted(base_idx.items()):
        cur_mean = cur_idx.get(name)
        if cur_mean is None:
            missing.append(name)
            continue
        delta_pct = (cur_mean - base_mean) / base_mean * 100.0
        flag = "OK" if delta_pct <= args.max_regression_pct else "REGRESSION"
        print(f"  · {name}: base={base_mean*1000:.2f}ms cur={cur_mean*1000:.2f}ms "
              f"Δ={delta_pct:+.1f}% [{flag}]")
        if delta_pct > args.max_regression_pct:
            regressions.append((name, base_mean, cur_mean, delta_pct))

    if missing and args.strict_missing:
        print(f"[bench-compare] benchmarks manquants en current : {missing}", file=sys.stderr)
        return 1

    if regressions:
        print(f"[bench-compare] ÉCHEC : {len(regressions)} régression(s) > "
              f"{args.max_regression_pct} %", file=sys.stderr)
        return 1
    print("[bench-compare] OK — aucune régression bloquante.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

