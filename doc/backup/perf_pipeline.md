# Pipeline complet — performance < 3 min sur 5 000 symboles (Phase F / S23.4)

> Cible : `screener → selector → risk → execution(dry-run)` en **< 180 s**
> sur runner `ubuntu-latest` (4 cores) avec dataset synthétique 5 000 symboles.

## Outil

[`scripts/bench_full_pipeline.py`](../../scripts/bench_full_pipeline.py) :

```powershell
python scripts/bench_full_pipeline.py --symbols 5000 --output artifacts/benchmarks
```

Produit `artifacts/benchmarks/full_pipeline_<date>.json` :

```json
{
  "timestamp": "...",
  "symbols": 5000,
  "total_seconds": 0.0,
  "threshold_seconds": 180.0,
  "passed": true,
  "stages": {
    "screener": {
      "seconds": 0.0,
      "error": null,
      "details": {
        "mode": "synthetic_current_screener_pipeline",
        "input_symbols": 5000,
        "rows_generated": 1400000,
        "symbols_final": 0,
        "benchmark_symbol": "SPY",
        "chunk_size": 1000
      }
    },
    "selector": {
      "seconds": 0.0,
      "error": null,
      "details": {
        "input_symbols": 200,
        "rows_generated": 12000,
        "factor_rows": 200
      }
    },
    "risk": {
      "seconds": 0.0,
      "error": null,
      "details": {
        "symbols_processed": 1000,
        "requested_symbols": 1000
      }
    },
    "execution_dry_run": {
      "seconds": 0.0,
      "error": null,
      "details": {
        "symbols_processed": 5000,
        "allocation_counter": 40000
      }
    }
  }
}
```

Notes :

- le stage `screener` n'utilise plus une API historique `screener.runner` ; il benchmarke désormais les primitives actuelles de `screener.pipeline` avec une `ScreenerConfig.strict_swing_cash()` sur données synthétiques ;
- chaque stage peut rester en `WARN` avec `error` renseigné sans faire échouer globalement le script (outillage best-effort) ;
- le bloc `details` sert à confirmer que le bench exécute bien le chemin nominal attendu.

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
- Données synthétiques générées en RAM pour le screener et le selector ; le screener benchmarke actuellement ~280 jours ouvrés synthétiques par symbole.
- Pas de cache disque : chaque run repart de zéro.

