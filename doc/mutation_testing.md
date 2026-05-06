# Mutation Testing — Phase C / S14

## Objectif

Mesurer la robustesse de la suite de tests sur les modules critiques
(`risk_management/`, `execution_engine/`, `corporate_actions/`) en
introduisant des mutations de code et en vérifiant que les tests les
détectent.

## Outil

[`mutmut`](https://mutmut.readthedocs.io/) (≥ 2.5). Configuré dans
`pyproject.toml` :

```toml
[tool.mutmut]
paths_to_mutate = "risk_management/,execution_engine/,corporate_actions/"
runner = "pytest -x -q --no-cov"
backup = false
```

## Wrapper CLI

`scripts/run_mutation_testing.py` :

```bash
python scripts/run_mutation_testing.py --module corporate_actions
python scripts/run_mutation_testing.py --all
```

Sortie : `artifacts/mutation_runs/<YYYY-MM-DD>/score.json`
Exit code : 1 si score < seuil (défaut 50 %).

## Cible

| Phase | Seuil | Module prioritaire |
|---|---|---|
| **S14 (baseline)** | 50 % | `corporate_actions` |
| **S14-bis** | 60 % | `risk_management` |
| **S14-ter** | 70 % | `execution_engine` |

Le seuil 70 % du plan `22_plan_10_10.md` est atteint progressivement
sur 2-3 itérations (mutation testing étant chronophage en CPU).

## Workflow CI

`.github/workflows/mutation_weekly.yml` — cron dimanche 06:00 UTC.

## Interprétation

* **killed** : la mutation a été détectée par un test → ✅
* **survived** : la mutation passe inaperçue → 🚨 ajouter un test
* **timeout** : test trop long → mutation à étudier au cas par cas
* **skipped** : code non couvert par les tests

