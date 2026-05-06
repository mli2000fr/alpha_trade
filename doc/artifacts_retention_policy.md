# Politique de rétention `artifacts/` (Sprint S4 — A-023)

> **Audience** : opérateurs / DevOps.
> **Objectif** : encadrer la croissance de `artifacts/` pour éviter la
> saturation disque, tout en garantissant la traçabilité long terme des
> runs critiques (modèles ML champion, backtests référence).
> **Scope** : tous les sous-dossiers de `artifacts/`. Tout nouveau
> sous-dossier doit être ajouté ici **et** dans
> [`scripts/prune_artifacts.py`](../scripts/prune_artifacts.py)
> (single source of truth dans le code).

---

## 1. Tableau de rétention

| Sous-dossier | Type contenu | Rétention | Politique de purge | Criticité |
|---|---|---|---|---|
| `artifacts/eodhd_cache/` | Tracker bulk EOD JSON | 90 j | rolling delete (mtime) | P3 |
| `artifacts/finnhub_cache/` | Profils société (TTL fichier 7 j) | 30 j | rolling delete | P3 |
| `artifacts/ihm_pipeline_runs/` | run_summary IHM pipeline | 60 j | garder N=200 derniers runs | P2 |
| `artifacts/ihm_backtesting_runs/` | Reports backtest IHM | 180 j | garder N=100 par profil | P2 |
| `artifacts/ihm_preferences/` | Préférences utilisateur | illimité | jamais purgé | P3 |
| `artifacts/models/` | Checkpoints ML | 365 j + champion ∞ | garder champion + N=3 challengers/symbole | **P1** |
| `artifacts/signal_aggregator_runs/` | Runs sentiment | 60 j | rolling delete | P3 |
| `artifacts/pre_live_checks/` | Rapports pre-live (audit) | **365 j** | rolling delete | **P1** |

**Notation**

- *Rolling delete* : suppression dès que `mtime` > rétention.
- *Garder N derniers* : trier desc par `mtime`, supprimer la queue.
- *Champion ∞* : un fichier identifié comme champion (`model_governance`)
  n'est **jamais** supprimé même au-delà de 365 j.

---

## 2. Procédure d'exécution

```powershell
# Inspection (dry-run, défaut) — produit artifacts/prune_report.json
python scripts/prune_artifacts.py

# Application réelle (irréversible)
python scripts/prune_artifacts.py --apply

# Cibler un seul sous-dossier
python scripts/prune_artifacts.py --apply --rule eodhd_cache

# Override d'âge ad hoc
python scripts/prune_artifacts.py --apply --older-than 14d --rule signal_aggregator_runs
```

Recommandation : exécuter en cron / tâche planifiée hebdomadaire (dimanche),
en dry-run d'abord, puis avec `--apply` après revue du rapport.

---

## 3. Règle d'or

Tout nouveau sous-dossier `artifacts/` doit :

1. Être ajouté dans `RETENTION_RULES` de
   [`scripts/prune_artifacts.py`](../scripts/prune_artifacts.py).
2. Apparaître dans le tableau §1 de ce document.
3. Avoir sa criticité documentée (P1 / P2 / P3).

Le test `tests/test_data_lineage_autogen.py` vérifie indirectement la
cohérence ; un test dédié à la couverture exhaustive du tableau ↔ règles
sera ajouté en S5/S9 (rétention en self-service).

---

## 4. Référence DR

La rétention long terme des données critiques (modèles champion, backtests
de calibration) est une brique de **disaster recovery**. Une procédure DR
formalisée (snapshot DB + bundle `artifacts/models/champion/`) sera traitée
en Sprint S5 et durcie en Sprint S9.

---

**Réf.** : `prompt/tod/08_sprint_plan.md` Sprint S4 ; A-023 du registre
d'anomalies ; `prompt/tod/14_sprint_S4_delivery_report.md`.

