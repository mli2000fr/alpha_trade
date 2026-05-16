# Phase 5 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 5

La Phase 5 prolonge la Phase 4 avec un objectif précis : **rejouer la logique de transition du watcher de protection**, et pas seulement rejouer des niveaux de stop/TP statiques.

Après la Phase 4, le backtest pouvait déjà :

- rejouer les quantités d’entrée (Phase 3),
- rejouer les protections dérivées des `child_intents` (Phase 4),

mais il restait un écart important avec le comportement live :

- la promotion `initial_stop -> trailing_stop` du watcher de protection n’était pas encore modélisée comme un événement lifecycle distinct ;
- le moteur backtest activait les protections rejouées sans reconstituer explicitement le moment où le watcher déclenche la transition.

La Phase 5 a donc introduit un mode **strictement opt-in** qui rejoue le cycle de vie du watcher de protection dans une version conservative et backtesting-only.

---

## Décision d’architecture

Comme pour les phases précédentes, aucune logique live n’a été modifiée.

### Nouveau module créé

- `backtesting/protection_watcher_replay.py`

Ce module reste entièrement côté `backtesting/` et ne dépend pas du runtime broker/DB live.

### Rôle du module

À partir du résultat Phase 4, il :

- relit les protections rejouées,
- relit le `high` historique journalier,
- détecte la date où le trigger de trailing est atteint,
- reconstruit une date de transition effective conservative,
- produit :
  - une `lifecycle_frame`,
  - une `event_frame`,
  - un `signals_df` enrichi pour le moteur,
  - des diagnostics structurés.

Le module expose explicitement des états lifecycle comme :

- `pending`
- `transitioned`
- `failed`
- `not_applicable`

et génère des événements compatibles avec la sémantique métier existante :

- `PROTECTION_TRIGGER_HIT`
- `PROTECTION_TRANSITION_COMPLETED`
- `PROTECTION_TRANSITION_FAILED`

---

## Nouveau contrôle CLI

La Phase 5 introduit un nouveau flag dédié :

- `--phase5-mode off`
- `--phase5-mode watcher_replay`

### Dépendance explicite

La Phase 5 dépend de la Phase 4 :

- `phase5_mode=watcher_replay` exige `phase4_mode=protection_replay`

et donc indirectement :

- `phase3_mode=execution_replay`
- `phase2_mode=risk_execution`

Cette dépendance est validée en **fail-fast** dans la CLI.

---

## Intégration dans le moteur de backtest

### 1. `BacktestConfig`

`backtesting/simulator.py` a été étendu avec :

- `watcher_replay_mode = "off" | "watcher_replay"`

Défaut :

- `off`

Donc aucun comportement standard n’est modifié.

### 2. `_OpenPosition`

Les positions peuvent désormais embarquer, en mode Phase 5 :

- `watcher_transition_state`
- `watcher_trigger_date`
- `watcher_transition_effective_date`

### 3. Temporalité conservative

La Phase 5 adopte volontairement une convention conservative et simple pour rester robuste en fréquence journalière :

- le **trigger** du trailing est détecté sur une séance donnée ;
- la **promotion effective** du trailing n’entre en vigueur qu’à partir de la séance suivante disponible.

Cela évite d’introduire des hypothèses intraday agressives impossibles à garantir avec des barres daily.

### 4. Effet dans `_try_close_positions(...)`

Quand `watcher_replay_mode="watcher_replay"` est actif, le moteur n’active le trailing rejoué qu’à partir de `watcher_transition_effective_date`.

Conséquence :

- avant cette date, l’initial stop / TP rejoués restent la protection active ;
- après cette date, le trailing stop rejoué devient la protection active.

La Phase 5 améliore donc la fidélité du **timing de promotion du trailing**, sans altérer les runs standard.

---

## Intégration IHM

La Phase 5 a été propagée jusqu’à l’IHM backtesting.

### Modifications

Dans `ihm/services/backtesting_runner.py` :

- ajout de `phase5_mode` dans `BacktestRunOptions`
- ajout du flag `--phase5-mode`

Dans `ihm/pages/backtesting.py` :

- ajout de la ligne de référence `phase5_mode`
- ajout d’un sélecteur UI :
  - `off`
  - `watcher_replay`

### Défaut

- `phase5_mode = off`

Donc l’IHM ne change jamais implicitement le comportement d’un backtest standard.

---

## Artefacts Phase 5 livrés

Quand `phase5_mode = watcher_replay` et qu’un `output_dir` est fourni, la Phase 5 produit :

- `phase5_watcher_replay_lifecycle.csv`
- `phase5_watcher_replay_events.csv`
- `phase5_watcher_replay_signals.csv`
- `phase5_watcher_replay_summary.json`

### Report structuré

Le `report.json` est enrichi avec :

- `params.phase5.enabled`
- `params.phase5.mode`
- `params.phase5.watcher_replay`

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

### Créé

- `backtesting/protection_watcher_replay.py`
- `prompt/backtest/phase5.md`

---

## Validation exécutée

### Suites pytest exécutées

```powershell
pytest -q --no-cov tests/test_phase2_bridges.py tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_backtesting.py
pytest -q --no-cov tests/test_backtesting_refactor.py
```

### Résultat

- suites ciblées Phase 5 / CLI / IHM / moteur / watcher replay : **vert**
- suite de compatibilité backtesting/refactor : **vert**

---

## Garanties de non-régression live

La Phase 5 respecte la règle “zéro régression sur les pipelines live” car :

1. aucun comportement live de `execution_engine` n’a été modifié ;
2. aucun comportement live de `risk_management` n’a été modifié ;
3. tout le replay du watcher est encapsulé dans `backtesting/` ;
4. le moteur garde son comportement historique par défaut ;
5. l’activation est strictement conditionnée par l’enchaînement opt-in :
   - Phase 2
   - puis Phase 3
   - puis Phase 4
   - puis Phase 5
6. l’IHM n’active rien implicitement.

En pratique :

- les pipelines live existants ne changent pas ;
- les backtests standards ne changent pas ;
- seuls les runs explicitement opt-in bénéficient de cette fidélité supplémentaire.

---

## Limites connues / périmètre volontairement conservateur

La Phase 5 améliore la fidélité lifecycle des protections, mais reste volontairement prudente.

### Ce qu’elle fait

- elle rejoue le trigger et la transition du watcher ;
- elle introduit une temporalité conservative compatible daily ;
- elle rapproche le backtest du comportement post-exécution live.

### Ce qu’elle ne fait pas encore

- elle ne reproduit pas le service persistant complet du watcher ;
- elle ne simule pas les interactions broker/DB réelles ;
- elle ne rejoue pas encore des transitions complexes avec erreurs/cancel partiels multiples ;
- elle ne couvre pas encore les fills partiels multi-étapes.

---

## Conclusion

La Phase 5 est maintenant livrée avec les propriétés suivantes :

- **strictement opt-in** ;
- **sans régression sur les pipelines live** ;
- **sans changement du chemin standard** ;
- **testée et documentée**.

Elle réduit encore l’écart entre :

- les protections dérivées des child intents,
- la logique de transition du watcher,
- et les règles de sortie réellement rejouées dans le backtest.

La suite logique d’une Phase 6, si elle est souhaitée, serait d’explorer des scénarios plus fins de lifecycle d’exécution, par exemple :

- transitions plus riches,
- événements persistés plus détaillés,
- scénarios de fills partiels,
- rejets / promotions / annulations plus réalistes,

le tout toujours dans une enveloppe **backtesting-only** et **strictement opt-in**.

