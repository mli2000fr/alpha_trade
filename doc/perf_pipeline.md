# Pipeline complet — performance < 3 min sur 5 000 symboles (Phase F / S23.4)

> Cible : `screener → selector → risk → execution(dry-run)` en **< 180 s**
> sur runner `ubuntu-latest` (4 cores) avec dataset synthétique 5 000 symboles.

## Outil

[`scripts/bench_full_pipeline.py`](../scripts/bench_full_pipeline.py) :

```powershell
python scripts/bench_full_pipeline.py --symbols 5000 --output artifacts/benchmarks
```

Produit `artifacts/benchmarks/full_pipeline_<date>.json` :

```json
{
  "timestamp": "...",
  "symbols": 5000,
  "total_seconds": 0.0,
  "stages": {
    "screener": 0.0,
    "selector": 0.0,
    "risk": 0.0,
    "execution_dry_run": 0.0
  },
  "passed": true,
  "threshold_seconds": 180.0
}
```

## Tableau temps par étape (à remplir)

| Étape | Baseline (s) | Cible (s) | Notes |
|---|---:|---:|---|
| screener | _à mesurer_ | < 60 | Principalement I/O DB. |
| selector | _à mesurer_ | < 80 | `compute_factor_frame` — voir [`perf_hotspots.md`](perf_hotspots.md). |
| risk | _à mesurer_ | < 20 | Sizing + circuit breaker. |
| execution (dry-run) | _à mesurer_ | < 20 | `MockBroker` ; pas d'I/O réseau. |
| **total** | _à mesurer_ | **< 180** | Condition #10 du `28_plan_10_10_2.md`. |

## Intégration CI

Job hebdomadaire dédié (lourd, 5 000 symboles) :
runner `ubuntu-latest` + `pytest -m slow` ou exécution directe du script.

## Méthodologie de mesure

- 5 runs consécutifs, on retient la médiane.
- Données synthétiques générées en RAM (`float32`, 252 jours) → ~5 GB max.
- Pas de cache disque : chaque run repart de zéro.

