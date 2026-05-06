"""Sprint S24.1 — CLI : exécution batch du fuzzing différentiel.

Usage::

    python scripts/run_fuzz_diff.py --n 10000 --out artifacts/fuzz_runs/
    python scripts/run_fuzz_diff.py --n 500 --strict   # CI PR (rapide)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from backtesting.fuzz_runner import DEFAULT_FUZZ_DIR, run_fuzz_diff
from backtesting.fuzz_tolerance import FuzzTolerance


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    p = argparse.ArgumentParser(
        description="Fuzzing différentiel backtest replay vs live execution."
    )
    p.add_argument("--n", type=int, default=10_000,
                   help="Nombre de scénarios à générer (défaut 10 000).")
    p.add_argument("--out", type=Path, default=DEFAULT_FUZZ_DIR,
                   help="Dossier de sortie racine (défaut artifacts/fuzz_runs/).")
    p.add_argument("--seed", type=int, default=1234,
                   help="Master seed pour reproductibilité (défaut 1234).")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 si la moindre divergence est détectée.")
    p.add_argument("--max-divergence-rate", type=float, default=0.0,
                   help="Taux de divergence acceptable (défaut 0.0 = aucune).")
    args = p.parse_args(argv)

    tol = FuzzTolerance()
    report = run_fuzz_diff(
        args.n,
        tolerance=tol,
        out_dir=args.out,
        master_seed=args.seed,
    )
    rate = report.summary["divergence_rate"]
    print(
        f"[fuzz_diff] n={report.n_scenarios} diverged={report.n_diverged} "
        f"rate={rate:.6f} max_pnl_delta={report.summary['max_pnl_delta_usd']:.4f} "
        f"duration={report.duration_seconds}s"
    )
    if args.strict and report.n_diverged > 0:
        return 1
    if rate > args.max_divergence_rate:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

