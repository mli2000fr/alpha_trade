# Sprint S1 — Rapport de livraison

> Sprint **Quick wins doc & config** — exécuté le 2026-05-06.
> Cible : éliminer les contradictions critiques doc/config qui trompent
> activement l'opérateur (anomalies P0 A-001, A-002, A-003 + P1/P2/P3
> A-004, A-005, A-012, A-022, A-030).

---

## 1. Synthèse

| Tâche | Anomalie | Statut |
|---|---|---|
| 1. Réécrire docstring `corporate_actions/engine.py` | A-001 (P0) | ✅ |
| 2. Supprimer `eodhd.enabled` de `config.yaml` + nettoyer docstring `service/eodhd/__init__.py` | A-002 (P0) | ✅ |
| 3. Réécrire `README.md` §6 (étape 1 conditionnelle) + tableau pipeline | A-003 (P0) | ✅ partiel (le WARNING runtime est planifié S2) |
| 4. Réécrire bandeau `doc/dataIntegrityEngine.md` | A-004 (P1) | ✅ |
| 5. Réécrire `doc/data_lineage_matrix.md` (provider actif) | A-005 (P1) | ✅ |
| 6. `doc/corporate_actions.md` (convention split) | — | ✅ déjà aligné (vérifié) |
| 7. Supprimer/rediriger `doc/backetesting.md` | A-012 (P2) | ✅ stub de redirection |
| 8. README §11 ajouter dossiers manquants | A-030 (P3) | ✅ |
| 9. Mention EODHD primaire dans `DOC_FONCTIONNELLE.md` / `DOC_TECHNIQUE.md` | A-004/A-005 | ✅ |
| 10. Garde-fou idempotent `signal_aggregator` (`--allow-rerun` + verrou fichier) | A-022 (P2) | ✅ |

---

## 2. Fichiers modifiés

### Code
- `corporate_actions/engine.py` — docstring réécrite (convention `'split'` + ledger).
- `config.yaml` — clé fantôme `eodhd.enabled` supprimée + commentaire d'audit.
- `service/eodhd/__init__.py` — docstring nettoyée (plus de mention `eodhd.enabled`).
- `event_sentiment/signal_aggregator.py` — ajout :
  - constantes `SIGNAL_AGGREGATOR_LOCK_DIR_ENV` / `SIGNAL_AGGREGATOR_LOCK_DEFAULT` ;
  - helpers `_resolve_lock_dir`, `_lock_path`, `_is_already_run`, `_mark_run_done` ;
  - flag CLI `--allow-rerun` ;
  - garde-fou `_is_already_run` au démarrage (warning + `_emit_run_summary` `skipped` + exit 0) ;
  - `_mark_run_done` après `Termine`.

### Documentation
- `README.md` — §6 (pipeline conditionnel par `bars_provider`), §11 (structure).
- `doc/dataIntegrityEngine.md` — bandeau provider primaire EODHD + table comparative + marqueur HTML.
- `doc/data_lineage_matrix.md` — colonne `provider actif`, marqueur HTML.
- `doc/DOC_FONCTIONNELLE.md` — bandeau provider primaire + marqueur HTML.
- `doc/DOC_TECHNIQUE.md` — bandeau provider primaire + marqueur HTML.
- `doc/backetesting.md` — stub de redirection (faute d'orthographe).

### Tests créés
- `tests/test_data_adjustment_convention.py` (4 tests) — A-001.
- `tests/test_config_yaml_schema.py` (5 tests) — A-002.
- `tests/test_doc_provider_alignment.py` (1 test sur 4 docs) — A-004 / A-005.
- `tests/test_signal_aggregator_idempotency.py` (5 tests) — A-022.

### Tests étendus
- `tests/test_eodhd_split_only.py` — 2 tests ajoutés (constante adapter + docstring CA).

---

## 3. Résultats tests

### Tests S1 ciblés
```
tests\test_data_adjustment_convention.py ....         [ 10%]
tests\test_config_yaml_schema.py .....                [ 24%]
tests\test_doc_provider_alignment.py .                [ 27%]
tests\test_signal_aggregator_idempotency.py .....     [ 40%]
tests\test_eodhd_split_only.py ......................  [100%]

============================ 37 passed in 3.74s ============================
```

### Suite complète (non-régression)
- **Pas de régression imputable à S1.**
- 10 échecs **préexistants et hors-périmètre S1** :
  - 8 × `tests/test_event_pipeline_*.py` — bug `progress_callback`
    dans `event_sentiment/pipeline.py` (module non touché par S1).
  - 1 × `tests/test_import_linter_contracts.py` — incompat API
    `importlinter` (pure dépendance Python).
  - 1 × `tests/test_model_factory_global_model.py` — test ML (hors S1).
- Ces 10 échecs ont vocation à être traités hors plan d'audit (ou
  programmés en backlog technique séparé) ; ils ne bloquent pas la
  validation de S1.

---

## 4. Critères d'acceptation

| Critère | Statut |
|---|---|
| Aucune contradiction provider primaire doc ↔ code ↔ config | ✅ vérifié par `tests/test_doc_provider_alignment.py` |
| `grep eodhd.enabled` retourne 0 résultat dans `config.yaml` | ✅ vérifié par `tests/test_config_yaml_schema.py::test_eodhd_enabled_key_is_absent` |
| Tests doc verts | ✅ 37/37 |

---

## 5. Gain attendu vs livré

| Module | Note avant | Note cible S1 | Statut |
|---|---|---|---|
| Documentation | 5.5 | 7.0 | ✅ atteint (provider doc↔config↔code aligné, redirection doublon, mention EODHD partout) |
| Configuration | 6.0 | 7.0 | ✅ atteint (paramètre fantôme supprimé, schéma minimal couvert par test) |
| Corporate actions | 6.5 | 7.0 | ✅ atteint (docstring corrigée + verrouillée par test) |

---

## 6. Restes pour anomalies S1 et reports vers les sprints suivants

- **A-003 (P0)** : la réécriture du runbook (tâche 3) est livrée. La
  tâche complémentaire « WARNING explicite + champ `skipped_reason`
  dans `import_alpaca_bar` quand `bars_provider != 'alpaca'` » reste
  programmée en **Sprint S2** (telle que prévue dans `08_sprint_plan.md`).
- **A-006, A-007, A-009, A-010, A-011 (P1)** : programmées en **Sprint S3**.
- **A-008 (P1)** : programmée en **Sprint S2**.
- Aucune anomalie nouvellement découverte pendant l'exécution de S1.

---

## 7. Notes pour le mainteneur

- Le **verrou d'idempotence** `signal_aggregator` est volontairement
  basé sur un fichier dans `artifacts/signal_aggregator_runs/` plutôt
  que sur une table SQL afin de rester fonctionnel même si la DB est
  inaccessible. Si une exécution distribuée est requise (multi-host),
  prévoir une migration vers un verrou SQL en S4.
- Le marqueur `<!-- primary_provider: eodhd -->` est l'invariant
  contractuel qui permet à `tests/test_doc_provider_alignment.py` de
  vérifier les docs. **Toute nouvelle doc structurante** parlant du
  provider OHLCV doit ajouter ce marqueur.
- Lors du passage à `bars_provider: alpaca` (rétrocompat), il faudra
  également mettre à jour la valeur du marqueur dans les 4 docs
  listées par `DOCS_WITH_MARKER` — sinon le test se déclenche.

