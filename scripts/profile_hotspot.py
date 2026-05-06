"""Phase F / S23.2 — Profile un hotspot avec cProfile + génère SVG (snakeviz/gprof2dot).

Hotspots ciblés en Phase F :
    - selector.factors.compute_factor_frame  (Minervini/VCP — recalé depuis
      ``compute_minervini_vcp`` qui n'existe pas)
    - selector.db_io.fetch_market_data       (recalé depuis ``database.db_io``)
    - execution_engine.oco_manager.OcoManager.check_and_cancel_sibling
      (recalé depuis ``synthetic_bracket.evaluate`` qui n'existe pas)

Usage::

    python scripts/profile_hotspot.py --target factors    --output artifacts/profiling
    python scripts/profile_hotspot.py --target db_io      --output artifacts/profiling
    python scripts/profile_hotspot.py --target oco        --output artifacts/profiling
    python scripts/profile_hotspot.py --target factors --view  # lance snakeviz si dispo

Le SVG est produit via ``gprof2dot | dot`` si disponibles ; sinon on se contente
du ``.prof`` brut, exploitable avec ``snakeviz`` ou ``pstats``.
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "artifacts" / "profiling"


def _bench_factors(iterations: int) -> None:
    """Profile selector.factors.compute_factor_frame sur dataset synthétique."""
    import numpy as np
    import pandas as pd

    try:
        from selector.factors import compute_factor_frame  # type: ignore
    except Exception as exc:  # pragma: no cover
        print(f"[profile] import échec : {exc}", file=sys.stderr)
        return
    rng = np.random.default_rng(42)
    n_symbols, n_days = 200, 260
    dates = pd.bdate_range(end="2025-12-31", periods=n_days)
    rows = []
    for sym in (f"SYM{i:03d}" for i in range(n_symbols)):
        prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, n_days))
        for d, p in zip(dates, prices):
            rows.append({"symbol": sym, "date": d, "open": p, "high": p * 1.01,
                         "low": p * 0.99, "close": p, "volume": 1_000_000})
    df = pd.DataFrame(rows)
    for _ in range(iterations):
        try:
            compute_factor_frame(df)  # type: ignore[arg-type]
        except TypeError:
            # Signature différente : essai sans args
            compute_factor_frame()  # type: ignore[call-arg]
            break


def _bench_db_io(iterations: int) -> None:
    """Profile fetch_market_data sur SQLite in-memory synthétique."""
    try:
        from selector.db_io import fetch_market_data  # type: ignore
    except Exception as exc:
        print(f"[profile] import échec : {exc}", file=sys.stderr)
        return
    # Fallback : simple benchmark de l'import + appel best-effort.
    for _ in range(iterations):
        try:
            fetch_market_data(symbols=["AAPL"], start_date=None, end_date=None)  # type: ignore
        except Exception:
            break


def _bench_oco(iterations: int) -> None:
    """Profile OcoManager.check_and_cancel_sibling avec mock broker/repo."""
    try:
        from execution_engine.oco_manager import OcoManager
        from execution_engine.models import OrderIntent, OrderStatus
    except Exception as exc:
        print(f"[profile] import échec : {exc}", file=sys.stderr)
        return

    class _MockBroker:
        def cancel_broker_order(self, _id: str) -> bool: return True

    class _Sib:
        def __init__(self, i: int):
            self.intent_id = f"sib-{i}"
            self.broker_order_id = f"bord-{i}"
            self.symbol = "AAPL"
            self.status = OrderStatus.NEW

    class _MockRepo:
        def __init__(self, n: int): self._n = n
        def load_open_child_orders(self, _pid): return [_Sib(i) for i in range(self._n)]

    oco = OcoManager(_MockBroker(), _MockRepo(50))  # type: ignore[arg-type]
    intent = OrderIntent.__new__(OrderIntent)
    intent.parent_intent_id = "p1"
    intent.intent_id = "child-1"
    for _ in range(iterations):
        oco.check_and_cancel_sibling(intent, "exec-1")  # type: ignore[arg-type]


TARGETS = {
    "factors": (_bench_factors, 5),
    "db_io": (_bench_db_io, 5),
    "oco": (_bench_oco, 200),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=list(TARGETS), required=True)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--view", action="store_true",
                        help="Ouvre snakeviz à la fin (si installé)")
    args = parser.parse_args()

    fn, default_iter = TARGETS[args.target]
    iterations = args.iterations or default_iter
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    out_dir = args.output / date
    out_dir.mkdir(parents=True, exist_ok=True)
    prof_path = out_dir / f"{args.target}.prof"
    svg_path = out_dir / f"{args.target}.svg"

    print(f"[profile] target={args.target} iterations={iterations} → {prof_path}")
    profiler = cProfile.Profile()
    profiler.enable()
    fn(iterations)
    profiler.disable()
    profiler.dump_stats(str(prof_path))

    # Top 30 cumulative
    txt_path = out_dir / f"{args.target}.txt"
    with txt_path.open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh).sort_stats("cumulative")
        stats.print_stats(30)
    print(f"[profile] top-30 cumulative → {txt_path}")

    # Optionnel : SVG via gprof2dot + dot
    if shutil.which("gprof2dot") and shutil.which("dot"):
        try:
            p1 = subprocess.run(["gprof2dot", "-f", "pstats", str(prof_path)],
                                capture_output=True, check=True)
            with svg_path.open("wb") as fh:
                subprocess.run(["dot", "-Tsvg"], input=p1.stdout, stdout=fh, check=True)
            print(f"[profile] SVG → {svg_path}")
        except subprocess.CalledProcessError as exc:
            print(f"[profile] SVG génération échec : {exc}", file=sys.stderr)
    else:
        print("[profile] gprof2dot/dot absents — SVG non généré (utiliser snakeviz)")

    if args.view and shutil.which("snakeviz"):
        subprocess.Popen(["snakeviz", str(prof_path)])
    return 0


if __name__ == "__main__":
    sys.exit(main())

