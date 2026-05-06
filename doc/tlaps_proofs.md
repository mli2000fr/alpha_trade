# Preuves TLAPS — Phase G / S24.3

> Sprint S24.3 — Engagement consultant TLA+ + livrables CI.

## Objectif

Compléter les preuves Z3 exécutables (`formal/z3_invariants/`) par
des preuves **TLAPS** sur les 3 invariants critiques :

1. `IdempotenceCA` — `NoDuplicate` : pas de double application CA.
2. `OCOBracket` — `MutualExclusion`, `SiblingCancelInitiated`,
   `NoActiveAfterFinalize`.
3. `NoDoubleExec` — `Singleton` : ≤ 1 fill par `idempotency_key`.

## Engagement consultant

* **Profil** : ingénieur senior TLA+ / TLAPS (5-10 j/h).
* **Livrables** :
  * fichiers `formal/tla/proofs/<spec>_proof.tla` ;
  * exécution réussie de `tlapm` sur les 3 specs (résultat dans
    `artifacts/formal_runs/<date>/tlaps.json` avec `n_failed = 0`) ;
  * documentation des hypothèses + steps.
* **Critères d'acceptation** : `python scripts/run_tlaps.py --strict`
  exit code 0 sur l'environnement Docker `tlaps/tlaps`.
* **Hash spec figées au lancement de la mission** :
  * `formal/tla/IdempotenceCA.tla` — voir git log.
  * `formal/tla/OCOBracket.tla`
  * `formal/tla/NoDoubleExec.tla`

## Reproductibilité locale

```bash
# Image Docker officielle TLAPS
docker run --rm -v $PWD/formal/tla:/tla tlaps/tlaps tlapm /tla/IdempotenceCA.tla
docker run --rm -v $PWD/formal/tla:/tla tlaps/tlaps tlapm /tla/OCOBracket.tla
docker run --rm -v $PWD/formal/tla:/tla tlaps/tlaps tlapm /tla/NoDoubleExec.tla
```

Ou wrapper Python (auto-détecte tlapm, fallback TLC) :

```bash
python scripts/run_tlaps.py --out artifacts/formal_runs/ --strict
```

## Format `artifacts/formal_runs/<date>/tlaps.json`

```json
{
  "generated_at": "...",
  "tool": "tlaps | tlc-fallback",
  "n_specs": 3,
  "n_ok": 3,
  "n_failed": 0,
  "results": [
    {"spec": "IdempotenceCA.tla", "tool": "tlaps", "ok": true,
     "returncode": 0, "stdout": "...", "stderr": ""}
  ]
}
```

## CI

* Job `tlaps` dans `.github/workflows/formal_verification.yml`,
  `continue-on-error: true` au lancement de la mission, basculement
  en `false` (bloquant) **une fois les preuves consultant intégrées**.
* Artefact `tlaps-<run_id>` conservé 90 j.

## Statut

| Spec | Z3 | TLAPS |
|---|---|---|
| `IdempotenceCA.tla` | ✅ exécutable | ⚠️ scaffolding livré, preuve consultant à venir |
| `OCOBracket.tla` | ✅ via `oco_synthetic_bracket.py` | ⚠️ idem |
| `NoDoubleExec.tla` | ✅ via `no_double_execution.py` | ⚠️ idem |

## Comment livrer une preuve

1. Le consultant dépose sa preuve dans
   `formal/tla/proofs/<SpecName>_proof.tla` (un fichier par invariant).
2. Tester localement :
   ```bash
   docker run --rm -v $PWD/formal/tla:/tla tlaps/tlaps \
     tlapm /tla/proofs/IdempotenceCA_proof.tla
   ```
3. Lancer le wrapper :
   ```bash
   python scripts/run_tlaps.py --strict
   ```
   exit code attendu : `0` ; `tlaps.json.n_failed == 0`.
4. Mettre à jour le tableau §Statut (⚠️ → ✅) et basculer
   `continue-on-error: false` dans `formal_verification.yml`.
5. Mettre à jour `doc/external_audit_checklist.md` (item TLA+ ⇒ ✅) et
   `formal/tla/README.md` (statut "stub" → "prouvé").

Tests automatisés du wrapper : `tests/test_run_tlaps.py` (mock
`subprocess.run`, vérifie fallback TLC, mode `--strict`, écriture
`tlaps.json`, gestion timeout).

Une fois la mission consultant terminée :
1. Supprimer `continue-on-error` dans le workflow.
2. Mettre à jour `doc/external_audit_checklist.md` (item TLA+ ⇒ ✅).
3. Mettre à jour `formal/tla/README.md` (statut "stub" → "prouvé").

