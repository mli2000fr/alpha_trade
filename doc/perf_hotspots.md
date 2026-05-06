# Profiling des 3 hotspots (Phase F / S23.2)

> Outil : [`scripts/profile_hotspot.py`](../scripts/profile_hotspot.py)
> (cProfile + pstats + gprof2dot/snakeviz si disponibles).
> Sortie : `artifacts/profiling/<YYYY-MM-DD>/{target}.prof|.txt|.svg`.

## Recalage des cibles

L'énoncé Phase F mentionne :

| Énoncé Phase F | Cible réelle dans le repo |
|---|---|
| `selector.factors.compute_minervini_vcp` | [`selector.factors.compute_factor_frame`](../selector/factors.py) (englobe Minervini + VCP) |
| `database.db_io.fetch_market_data` | [`selector.db_io.fetch_market_data`](../selector/db_io.py) (le module `database/db_io.py` n'existe pas) |
| `execution_engine.synthetic_bracket.evaluate` | [`execution_engine.oco_manager.OcoManager.check_and_cancel_sibling`](../execution_engine/oco_manager.py) (le module `synthetic_bracket.py` n'existe pas — la logique est répartie entre `executor.py`, `oco_manager.py`, `children_submission.py`, `protection_transition.py`) |

## Procédure

```powershell
# 1. Profile chaque hotspot
python scripts/profile_hotspot.py --target factors
python scripts/profile_hotspot.py --target db_io
python scripts/profile_hotspot.py --target oco

# 2. Visualiser interactif (optionnel)
pip install snakeviz
snakeviz artifacts/profiling/<date>/factors.prof
```

## Tableau avant / après

| Hotspot | Baseline (ms / iter) | Optimisé (ms / iter) | Gain | Date | Notes |
|---|---:|---:|---:|---|---|
| `compute_factor_frame` | _à mesurer_ | _à mesurer_ | _à mesurer_ | — | Vectoriser groupby ; pré-calcul beta_126. |
| `fetch_market_data` | _à mesurer_ | _à mesurer_ | _à mesurer_ | — | Streaming COPY / chunking ; LRU schéma. |
| `check_and_cancel_sibling` | _à mesurer_ | _à mesurer_ | _à mesurer_ | — | Court-circuit si pas de sibling ; éviter polls O(n²). |

## Critère Phase F

Cumul de gain ≥ 30 % validé via les benchmarks
[`tests/benchmarks/`](../tests/benchmarks) ; régression bloquante > 20 %
gérée par [`scripts/compare_benchmarks.py`](../scripts/compare_benchmarks.py).

