# Mutation testing — historique hebdomadaire (Phase F / S22.3)

> Cible Phase F : score mutmut **≥ 70 %** sur les 3 modules critiques
> (`corporate_actions/`, `risk_management/`, `execution_engine/`).
> Workflow CI : [`.github/workflows/mutation_weekly.yml`](../.github/workflows/mutation_weekly.yml)
> (cron dimanche 06:00 UTC).

## Méthodologie

1. Le workflow lance `python scripts/run_mutation_testing.py --module <m> --threshold 70`
   en matrix sur les 3 modules.
2. Chaque run produit `artifacts/mutation_runs/<YYYY-MM-DD>/score.json` et
   un artefact GH Actions `mutation-<module>-<run_id>`.
3. Les survivants sont listés via `scripts/list_mutation_survivors.py`
   pour itération (ajout de tests killer ciblés).
4. Une fois le seuil atteint module par module, le `--threshold` est figé
   à 70 dans le workflow.

## Tableau de bord

| Date (UTC) | corporate_actions | risk_management | execution_engine | Notes |
|---|---:|---:|---:|---|
| _baseline_ | _à mesurer_ | _à mesurer_ | _à mesurer_ | Premier run après bascule à `--threshold 70`. |

> Le tableau est mis à jour manuellement après chaque run hebdo en collant
> la valeur `score_pct` lue dans `artifacts/mutation_runs/<date>/score.json`.

## Itération sur survivants

```powershell
# Localement, sur un module donné
mutmut run --paths-to-mutate corporate_actions --runner "pytest -x -q --no-cov"
python scripts/list_mutation_survivors.py --module corporate_actions
# → artifacts/mutation_runs/<date>/survivors.json
```

Pour chaque survivant :

1. Lire la diff (`mutmut show <id>`).
2. Identifier le test qui aurait dû tuer ce mutant.
3. Ajouter une assertion ciblée (préférer un test atomique à un test e2e).
4. Relancer le run sur le module et vérifier `killed += 1`.

## Politique d'exclusion

Sont exclus du périmètre mutation testing :

- code legacy `@deprecated_v1` ;
- CLIs (`__main__`, scripts one-shot) ;
- code défensif `# pragma: no cover` justifié.

| 2026-05-17 | 2026-05-17 | None | None | None |
| 2026-05-24 | 2026-05-24 | None | None | None |
