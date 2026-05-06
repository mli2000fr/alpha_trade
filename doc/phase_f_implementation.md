# Phase F — Mesures effectives (Sprints S22 + S23) — Récap d'implémentation

> Statut : **infrastructure livrée et fonctionnelle** ; les itérations
> métier (atteindre 90 % cov / 70 % mutation / -30 % gain perf) sont à
> exécuter selon la procédure ci-dessous.
> Date : 2026-05-06.

## Livrables

### S22 — Couverture branches > 90 % + mutation effective

| # | Livrable | Fichier(s) |
|---|---|---|
| S22.1 | `--cov-branch` activé + `coverage.json` produit ; gate à 60 (montée 60→75→85→90 par paliers documentés inline) | [`pytest.ini`](../pytest.ini) |
| S22.2 | Vérifie branches > 95 % sur 3 modules critiques | [`scripts/check_branch_coverage_critical.py`](../scripts/check_branch_coverage_critical.py) |
| S22.3 | Workflow mutation matrix sur 3 modules + threshold paramétrable (cible 70) | [`.github/workflows/mutation_weekly.yml`](../.github/workflows/mutation_weekly.yml) |
| S22.3 | Extracteur de mutants survivants | [`scripts/list_mutation_survivors.py`](../scripts/list_mutation_survivors.py) |
| S22.3 | Tableau de bord historique | [`doc/mutation_history.md`](mutation_history.md) |
| S22.4 | Property tests OCO synthetic bracket (4 invariants, hypothesis) | [`tests/property/test_synthetic_bracket_properties.py`](../tests/property/test_synthetic_bracket_properties.py) |

### S23 — Performance + scale

| # | Livrable | Fichier(s) |
|---|---|---|
| S23.1 | Suites pytest-benchmark (selector, screener, executor) | [`tests/benchmarks/`](../tests/benchmarks) |
| S23.1 | Comparateur baseline ↔ current avec garde-fou +20 % | [`scripts/compare_benchmarks.py`](../scripts/compare_benchmarks.py) |
| S23.1 | Baseline placeholder (à populer au 1er run main) | [`artifacts/benchmarks/baseline.json`](../artifacts/benchmarks/baseline.json) |
| S23.2 | Profiler cProfile + snakeviz/gprof2dot | [`scripts/profile_hotspot.py`](../scripts/profile_hotspot.py) |
| S23.2 | Doc avant/après (à remplir après mesures) | [`doc/perf_hotspots.md`](perf_hotspots.md) |
| S23.3 | POC async DB (factory + 3 loaders read-only, opt-in env var) | [`database/async_engine.py`](../database/async_engine.py), [`database/async_loaders.py`](../database/async_loaders.py) |
| S23.3 | Tests parité sync ↔ async | [`tests/test_async_loaders.py`](../tests/test_async_loaders.py) |
| S23.3 | Doc POC | [`doc/async_db_poc.md`](async_db_poc.md) |
| S23.4 | Bench pipeline 5 000 symboles (cible < 180 s) | [`scripts/bench_full_pipeline.py`](../scripts/bench_full_pipeline.py), [`doc/perf_pipeline.md`](perf_pipeline.md) |
| S23.5 | Scaffold découpage executor (PhaseContext + 4 phases stubs) | [`execution_engine/executor_phases.py`](../execution_engine/executor_phases.py) |

## Procédure d'exécution (ordre recommandé)

```powershell
# 1. Mesurer la couverture branches courante (S22.1)
pytest --cov=. --cov-branch --cov-report=json:coverage.json --cov-report=html:htmlcov

# 2. Vérifier modules critiques (S22.2)
python scripts/check_branch_coverage_critical.py --threshold 95

# 3. Lancer property tests OCO (S22.4)
pytest tests/property/test_synthetic_bracket_properties.py -v

# 4. Premier run mutation par module (S22.3) — itératif
python scripts/run_mutation_testing.py --module corporate_actions --threshold 50
python scripts/list_mutation_survivors.py --module corporate_actions
# → ajouter tests killer ciblés, relancer ; bumper à 70 quand stable

# 5. Premier run benchmarks → baseline (S23.1)
pytest tests/benchmarks --benchmark-json=artifacts/benchmarks/baseline.json
# Sur PR ultérieurs :
pytest tests/benchmarks --benchmark-json=current.json
python scripts/compare_benchmarks.py --baseline artifacts/benchmarks/baseline.json --current current.json

# 6. Profiler les hotspots (S23.2)
python scripts/profile_hotspot.py --target factors
python scripts/profile_hotspot.py --target db_io
python scripts/profile_hotspot.py --target oco

# 7. Activer POC async DB (S23.3)
$env:ALPHA_TRADE_ASYNC_DB = "1"
pip install aiosqlite "sqlalchemy[asyncio]"
pytest tests/test_async_loaders.py -v

# 8. Bench pipeline complet (S23.4)
python scripts/bench_full_pipeline.py --symbols 5000

# 9. Découpage executor (S23.5) — PR dédiée à risque maîtrisé
# Voir execution_engine/executor_phases.py (scaffold + 4 stubs NotImplementedError)
```

## Recalages d'API (énoncé Phase F vs repo réel)

| Énoncé | Réalité |
|---|---|
| `selector.factors.compute_minervini_vcp` | `selector.factors.compute_factor_frame` |
| `database.db_io.fetch_market_data` | `selector.db_io.fetch_market_data` (le module `database/db_io.py` n'existe pas) |
| `execution_engine.synthetic_bracket.evaluate` | `execution_engine.oco_manager.OcoManager.check_and_cancel_sibling` (la logique est répartie ; pas de module `synthetic_bracket.py`) |

## Critères de validation Phase F

| Critère | Sprint | Mesuré par | Statut |
|---|---|---|---|
| Couverture branches > 90 % global | S22.1 | `pytest --cov-branch` + `--cov-fail-under=90` | ⚠️ infra prête, atteindre par paliers |
| Couverture branches > 95 % sur risk/exec/CA | S22.2 | `scripts/check_branch_coverage_critical.py` | ⚠️ infra prête |
| Score mutation ≥ 70 % sur 3 modules | S22.3 | `scripts/run_mutation_testing.py --threshold 70` (CI hebdo) | ⚠️ infra prête |
| Property tests OCO mutuelle exclusion | S22.4 | `pytest -m property` | ✅ livré |
| Régression benchmark > 20 % bloquante | S23.1 | `scripts/compare_benchmarks.py` | ✅ livré (baseline à populer) |
| 3 hotspots profilés + optimisés | S23.2 | `scripts/profile_hotspot.py` + `doc/perf_hotspots.md` | ⚠️ infra prête |
| POC async DB opt-in | S23.3 | tests parité + `ALPHA_TRADE_ASYNC_DB=1` | ✅ livré |
| Pipeline complet < 3 min sur 5 000 symboles | S23.4 | `scripts/bench_full_pipeline.py` | ⚠️ infra prête |
| Executor < 500 lignes (4 phases extraites) | S23.5 | scaffold + PR dédiée | ⚠️ scaffold uniquement (refacto à risque, voir §8 plan 28) |

**Note cible Phase F : 9.1 → 9.5** une fois les 4 lignes ⚠️ passées en ✅
via les itérations métier.

