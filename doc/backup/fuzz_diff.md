# Fuzzing différentiel backtest replay ↔ live execution

> Sprint S24.1 — Phase G.

## Objectif

Détecter toute divergence non-intentionnelle entre :

* **Replay backtest** (référence rigoureuse, déterministe) ;
* **Live execution simulée** (exécution OCO bracket sur `MockBroker`).

La détection précoce de ces divergences évite les régressions
silencieuses entre la stratégie modélisée et son exécution réelle.

## Mode d'emploi

```bash
# Exécution locale rapide (CI PR)
python scripts/run_fuzz_diff.py --n 500 --strict

# Exécution complète (workflow hebdo)
python scripts/run_fuzz_diff.py --n 10000 --out artifacts/fuzz_runs/ --strict
```

## Format `artifacts/fuzz_runs/<YYYY-MM-DD>/diff.json`

```json
{
  "generated_at": "2026-05-06T04:00:00+00:00",
  "n_scenarios": 10000,
  "n_diverged": 0,
  "tolerance": {
    "price_abs": 1e-4,
    "qty_abs": 1e-6,
    "pnl_abs_usd": 0.01,
    "pnl_rel_pct": 0.001,
    "status_strict": true,
    "audit_strict": true
  },
  "divergences": [
    {
      "scenario_id": "sc-1234567",
      "seed": 1234567,
      "kind": "audit_hash | status_mismatch | qty_mismatch | pnl_mismatch",
      "live": {"pnl": 12.34, "tp_status": "FILLED", "audit_hash": "..."},
      "replay": {"pnl": 12.34, "tp_status": "FILLED", "audit_hash": "..."},
      "delta": {"pnl_abs": 0.0, "qty_abs": 0.0}
    }
  ],
  "summary": {
    "divergence_rate": 0.0,
    "max_pnl_delta_usd": 0.0,
    "master_seed": 1234
  },
  "config_hash": "ab12cd34ef56...",
  "duration_seconds": 12.45
}
```

## Tolérances

Champ | Défaut | Sémantique
---|---|---
`price_abs` | `1e-4` | Écart prix absolu accepté.
`qty_abs` | `1e-6` | Écart quantité fillée accepté.
`pnl_abs_usd` | `0.01` | PnL : tolérance absolue en $.
`pnl_rel_pct` | `0.001` | PnL : tolérance relative (0.1 %).
`status_strict` | `true` | Statuts OCO : égalité stricte.
`audit_strict` | `true` | Hash audit chain : égalité stricte.

Surcharge possible via `config.yaml` section `fuzz_diff`.

## Méthodologie

1. **Génération** : `random.Random(master_seed)` → suite déterministe
   de `FuzzScenario`.
2. **Exécution miroir** : chaque scénario est rejoué dans deux moteurs
   identiques (live & replay) ; toute différence implique un bug
   de symétrie.
3. **Comparaison** : ordre de priorité `audit_hash` > `status` > `qty`
   > `pnl`. Le premier mismatch détermine `kind`.
4. **Reproductibilité** : chaque divergence enregistre le `seed` permettant
   de rejouer le scénario incriminé en isolation.

## Gestion des divergences attendues

À ce jour, aucune divergence n'est tolérée (parité parfaite). Si une
divergence légitime apparaît (par ex. introduction d'un slippage live
volontaire), elle doit être :

1. Documentée dans une PR avec justification ;
2. Encodée dans `FuzzTolerance` (relâchement explicite) ;
3. Idéalement supprimée par convergence du moteur.

## CI

* Workflow `.github/workflows/fuzz_weekly.yml` — hebdo lundi 04:00 UTC.
* Job CI PR (à intégrer dans `ci.yml`) : `python scripts/run_fuzz_diff.py
  --n 500 --strict` (cible < 1 min sur runner standard).

## Tests

* `tests/test_fuzz_diff_runner.py` — smoke + détection divergence injectée.
* `tests/property/test_fuzz_backtest_vs_live_diff.py` — property (300
  scénarios `hypothesis`, focus parité scénario par scénario).
* `tests/property/test_fuzz_state_machine.py` — **stateful invariants**
  via `hypothesis.stateful.RuleBasedStateMachine`. Pilote
  `_run_engine` événement par événement et vérifie à chaque pas :
  * `MutualExclusion` : TP et SL ne sont jamais `FILLED` simultanément ;
  * `Finalisation` : après un `eod_close` final, aucune jambe ne reste
    à `NEW` ;
  * `Determinism` : `audit_hash` live ≡ replay ;
  * `QtyBound` : `qty_filled ≤ scenario.qty`.

