# Phase 7 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 7

La Phase 7 prolonge les Phases 3, 4 et 5 avec un objectif précis : **rejouer explicitement l’issue terminale des child orders d’exit**, et matérialiser aussi l’**annulation OCO du sibling**.

Après la Phase 5, le backtest savait déjà :

- rejouer les quantités d’entrée (Phase 3) ;
- rejouer les protections dérivées des child intents (Phase 4) ;
- rejouer la temporalité conservative du watcher de protection (Phase 5).

Mais un écart subsistait encore avec la pile live :

- le moteur de backtest continuait à résoudre localement la sortie à partir de niveaux et règles de protection ;
- il ne rejouait pas encore, comme source de vérité terminale, le fait qu’un child order précis ait été considéré comme « rempli » ;
- il ne matérialisait pas explicitement l’événement logique d’annulation OCO de l’autre jambe.

La Phase 7 a donc ajouté un mode **strictement opt-in** qui transforme l’exit terminal en événement rejoué explicitement dans le simulateur.

---

## Décision d’architecture

Comme pour les phases précédentes, toute la logique reste encapsulée côté `backtesting/`.

### Nouveau module créé

- `backtesting/exit_lifecycle_replay.py`

### Rôle du module

À partir du résultat Phase 5, ce module :

- relit les signaux enrichis par `watcher_replay` ;
- relit `high` et `low` historiques ;
- résout l’issue terminale de l’exit en utilisant la logique intrabar existante ;
- mappe la raison d’exit vers le rôle métier du child order (`take_profit`, `initial_stop`, `trailing_stop`) ;
- produit un `exit_frame` ;
- produit un `event_frame` ;
- enrichit le `signals_df` avec les colonnes terminales de replay.

### Colonnes terminales produites

- `replay_exit_date`
- `replay_exit_price`
- `replay_exit_reason`
- `replay_exit_intent_role`
- `replay_oco_sibling_canceled`
- `exit_lifecycle_replay_mode`

### Diagnostics produits

- `exit_rows`
- `events_generated`
- `filled_take_profit`
- `filled_initial_stop`
- `filled_trailing_stop`
- `oco_cancels`
- `bridge = execution_engine.oco_manager+exit_lifecycle_replay`

---

## Nouveau contrôle CLI

La Phase 7 introduit un nouveau flag dédié :

- `--phase7-mode off`
- `--phase7-mode exit_lifecycle_replay`

### Dépendance explicite

La Phase 7 dépend de la Phase 5 :

- `phase7_mode=exit_lifecycle_replay` exige `phase5_mode=watcher_replay`

et donc indirectement :

- `phase4_mode=protection_replay`
- `phase3_mode=execution_replay`
- `phase2_mode=risk_execution`

Cette contrainte est validée en **fail-fast** dans `backtesting/cli/_impl.py`.

---

## Intégration dans le moteur de backtest

### 1. `BacktestConfig`

`backtesting/simulator.py` supporte désormais :

- `exit_lifecycle_replay_mode = "off" | "exit_lifecycle_replay"`

Défaut :

- `off`

Donc le comportement historique ne change pas.

### 2. `_OpenPosition`

Les positions ouvertes peuvent maintenant embarquer, en mode Phase 7 :

- `explicit_exit_date`
- `explicit_exit_price`
- `explicit_exit_reason`
- `explicit_exit_intent_role`
- `explicit_oco_sibling_canceled`

### 3. Priorité à l’exit explicite

Dans `_try_close_positions(...)`, quand `exit_lifecycle_replay_mode="exit_lifecycle_replay"` est actif et qu’un exit explicite existe :

- le moteur attend exactement la date `replay_exit_date` ;
- il ferme la position au `replay_exit_price` ;
- il utilise `replay_exit_reason` comme source de vérité ;
- il incrémente le diagnostic `exit_lifecycle_replayed`.

En dehors de ce mode, le moteur continue à résoudre localement l’exit avec ses règles historiques / protections rejouées.

### Effet

La Phase 7 rapproche encore le moteur du comportement broker-like attendu :

- la sortie terminale n’est plus seulement déduite ;
- elle peut devenir un fait explicite rejoué dans le backtest.

---

## Événements lifecycle rejoués

La Phase 7 produit des événements structurés compatibles avec la sémantique métier execution :

- `EXIT_FILLED_TAKE_PROFIT`
- `EXIT_FILLED_INITIAL_STOP`
- `EXIT_FILLED_TRAILING_STOP`
- `OCO_CANCEL_TRIGGERED`

### Portée

Il s’agit d’un replay **backtesting-only** de la vérité terminale métier, pas d’une persistance broker réelle.

---

## Intégration IHM

La Phase 7 a été propagée jusqu’à l’IHM backtesting.

### Modifications

Dans `ihm/services/backtesting_runner.py` :

- ajout de `phase7_mode` dans `BacktestRunOptions`
- ajout du flag `--phase7-mode`

Dans `ihm/pages/backtesting.py` :

- ajout de la ligne de référence `phase7_mode`
- ajout d’un sélecteur UI :
  - `off`
  - `exit_lifecycle_replay`

### Défaut

- `phase7_mode = off`

Donc l’IHM ne modifie jamais implicitement un run standard.

---

## Artefacts Phase 7 livrés

Quand `phase7_mode = exit_lifecycle_replay` et qu’un `output_dir` est fourni, la Phase 7 produit :

- `phase7_exit_lifecycle_replay.csv`
- `phase7_exit_lifecycle_replay_events.csv`
- `phase7_exit_lifecycle_replay_signals.csv`
- `phase7_exit_lifecycle_replay_summary.json`

### Report structuré

Le `report.json` est enrichi avec :

- `params.phase7.enabled`
- `params.phase7.mode`
- `params.phase7.exit_lifecycle_replay`

Le `BacktestConfig` propagé dans le moteur expose aussi :

- `exit_lifecycle_replay_mode`

---

## Fichiers modifiés / créés

### Modifiés

- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`
- `tests/test_backtesting.py`
- `tests/test_phase2_bridges.py`
- `tests/test_ihm_backtesting_runner.py`
- `tests/test_pages_backtesting.py`

### Créés

- `backtesting/exit_lifecycle_replay.py`
- `prompt/backtest/phase7.md`

---

## Validation exécutée

### Suites ciblées exécutées

```powershell
pytest tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_phase2_bridges.py tests/test_backtesting.py -q --no-cov
```

### Couverture fonctionnelle validée

Les tests couvrent notamment :

- le parsing de `--phase7-mode` ;
- le défaut `phase7_mode = off` ;
- la propagation IHM → commande CLI ;
- le garde-fou `phase7 -> phase5` ;
- l’enrichissement terminal des signaux ;
- les diagnostics Phase 7 dans `report.json` ;
- les artefacts `phase7_exit_lifecycle_replay_*`.

### Résultat

- suite ciblée Phase 7 / CLI / IHM / bridges / backtesting : **vert**

---

## Garanties de non-régression live

La Phase 7 respecte la règle “zéro régression sur les pipelines live” car :

1. aucun comportement live de `execution_engine` n’a été modifié ;
2. aucun comportement live de `risk_management` n’a été modifié ;
3. la logique terminale reste entièrement encapsulée dans `backtesting/` ;
4. le moteur garde son comportement historique par défaut ;
5. l’activation est strictement opt-in et dépend d’une chaîne explicite de phases précédentes ;
6. l’IHM n’active rien implicitement.

---

## Limites connues / périmètre volontairement conservateur

La Phase 7 améliore nettement la fidélité du terminal exit lifecycle, mais reste volontairement prudente.

### Ce qu’elle fait

- elle rejoue l’issue terminale explicite ;
- elle matérialise l’annulation OCO logique du sibling ;
- elle réduit l’ambiguïté entre « niveau touché » et « ordre terminal considéré comme rempli » ;
- elle rapproche encore la sémantique du backtest de celle de l’exécution live.

### Ce qu’elle ne fait pas encore

- elle ne rejoue pas un carnet broker réel ;
- elle ne simule pas les partial fills multi-étapes ;
- elle ne reproduit pas l’ensemble des latences / erreurs / retries / états broker ;
- elle ne remplace pas la réconciliation live avec l’état broker réellement observé.

---

## Conclusion

La Phase 7 est maintenant livrée avec les propriétés suivantes :

- **strictement opt-in** ;
- **sans régression sur les pipelines live** ;
- **sans changement du chemin standard** ;
- **testée et documentée**.

Elle réduit encore l’écart entre :

- les protections et transitions rejouées des Phases 4 et 5 ;
- l’issue terminale attendue des child orders ;
- et la sortie effectivement matérialisée dans le backtest.

À ce stade, le backtest dispose désormais d’une chaîne avancée cohérente :

- Phase 2 : vrai chemin risk
- Phase 3 : replay d’exécution des entrées
- Phase 4 : replay des protections
- Phase 5 : replay du watcher
- Phase 7 : replay de l’exit terminal + OCO cancel logique

