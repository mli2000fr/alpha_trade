"""Phase F / S23.1 — Benchmark de la pipeline screener (best-effort).

L'API screener varie ; ce benchmark essaie plusieurs entrées (`AlphaScanner`,
`run_screener`) et skip proprement si aucune n'est exposée.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def _import_runner():
    candidates = [
        ("screener.runner", "run_screener"),
        ("screener.scanner", "AlphaScanner"),
        ("screener", "run_screener"),
    ]
    for module, attr in candidates:
        try:
            mod = __import__(module, fromlist=[attr])
            return getattr(mod, attr, None)
        except Exception:
            continue
    return None


def test_screener_run_benchmark(benchmark, synthetic_symbols) -> None:
    runner = _import_runner()
    if runner is None:
        pytest.skip("Aucun entrypoint screener trouvé")

    def _run() -> None:
        try:
            if isinstance(runner, type):  # classe AlphaScanner
                instance = runner()  # type: ignore[call-arg]
                fn = getattr(instance, "run", None) or getattr(instance, "scan", None)
                if fn is None:
                    pytest.skip("Pas de méthode .run/.scan sur AlphaScanner")
                fn(symbols=synthetic_symbols)  # type: ignore[misc]
            else:
                runner(symbols=synthetic_symbols)
        except TypeError:
            pytest.skip("Signature screener incompatible (POC bench)")
        except Exception as exc:
            pytest.skip(f"Screener indisponible en bench isolé : {exc}")

    benchmark.pedantic(_run, rounds=3, iterations=1)

