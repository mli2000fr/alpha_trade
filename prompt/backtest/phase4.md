# Phase 4 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 4

La Phase 4 prolonge la Phase 3 avec un objectif clair : **aligner aussi les sorties du backtest sur les protections d’exécution simulées**, et pas seulement sur les quantités d’entrée.

Après la Phase 3, un écart subsistait encore :

- les entrées pouvaient déjà être rejouées chronologiquement via `execution_replay` ;
- mais les sorties du moteur de backtest restaient encore pilotées par la logique interne simplifiée du simulateur (`profit_taker_pct`, `trailing_stop_pct`, stop initial local), même quand des `child_intents` broker-like avaient été produits côté exécution.

L’objectif de la Phase 4 a donc été de livrer un mode **strictement opt-in** capable de :

1. relire les protections issues des `child_intents` (`take_profit`, `initial_stop`, `trailing_stop`) ;
2. enrichir les signaux rejoués avec ces niveaux de protection ;
3. faire prioritairement piloter les sorties du moteur par ces protections rejouées ;
4. conserver **strictement inchangé** le chemin historique quand la fonctionnalité n’est pas activée.

---

## Décision d’architecture

Comme pour les phases précédentes, la règle de non-régression live a été respectée en restant entièrement côté `backtesting/`.

### Nouveau module créé

- `backtesting/execution_lifecycle_replay.py`

Ce module ne modifie aucun composant live. Il agit comme un adaptateur entre :

- le résultat de `backtesting/execution_replay.py` (Phase 3),
- et le moteur `backtesting/simulator.py`.

### Rôle du module

Il prend :

- les `entry_intents`
- les `child_intents`
- les `fills`
- les `targets`

et reconstruit un calendrier de protections backtesting-friendly, avec notamment :

- `replay_take_profit_price`
- `replay_initial_stop_price`
- `replay_trailing_stop_pct`
- `replay_trailing_activation_price`
- `replay_trailing_activation_mode`

Ces données sont ensuite fusionnées dans le `signals_df` enrichi.

---

## Nouveau contrôle CLI

La Phase 4 introduit un nouveau flag séparé :

- `--phase4-mode off`
- `--phase4-mode protection_replay`

### Dépendance explicite

La Phase 4 dépend de la Phase 3 :

- `phase4_mode=protection_replay` exige `phase3_mode=execution_replay`

et donc indirectement :

- `phase2_mode=risk_execution`

Cette dépendance est validée en **fail-fast** dans la CLI.

### Pourquoi un flag séparé ?

Parce que la Phase 4 ne se contente pas d’enrichir les diagnostics :

- elle change la **source de vérité des exits** pour les runs opt-in ;
- il était donc essentiel de séparer clairement :
  - la fidélité des entrées (Phase 3),
  - la fidélité des protections/sorties (Phase 4).

---

## Intégration dans le moteur de backtest

### 1. `BacktestConfig`

`backtesting/simulator.py` a été étendu avec :

- `protection_replay_mode = "off" | "protection_replay"`

Défaut :

- `off`

Donc aucun run standard n’est impacté.

### 2. `_OpenPosition`

Les positions ouvertes peuvent désormais embarquer, en mode Phase 4 :

- un take-profit rejoué,
- un initial stop rejoué,
- un trailing stop rejoué,
- un prix d’activation du trailing,
- l’état d’activation du trailing.

### 3. `_try_close_positions(...)`

Le moteur de sorties a été enrichi pour utiliser, quand ils existent et uniquement si `protection_replay_mode="protection_replay"` :

- `replay_take_profit_price`
- `replay_initial_stop_price`
- `replay_trailing_stop_pct`
- `replay_trailing_activation_price`

Sinon, il retombe sur la logique historique du simulateur.

Autrement dit :

- **Phase 4 activée** → priorité aux protections dérivées des `child_intents`
- **Phase 4 désactivée** → comportement historique inchangé

### 4. Activation du trailing

La Phase 4 apporte aussi une première couche de fidélité sur la promotion du stop vers trailing :

- avant activation, le moteur reste gouverné par l’initial stop / take-profit rejoués ;
- après activation, le trailing stop rejoué devient la protection active.

Cela rapproche le backtest du comportement attendu d’une pile broker-like, tout en restant dans une enveloppe prudente et contrôlée.

---

## Intégration IHM

La Phase 4 a été propagée jusqu’à l’IHM backtesting.

### Modifications

Dans `ihm/services/backtesting_runner.py` :

- ajout de `phase4_mode` dans `BacktestRunOptions`
- ajout de `--phase4-mode` dans la commande générée

Dans `ihm/pages/backtesting.py` :

- ajout de la ligne de référence `phase4_mode`
- ajout d’un sélecteur UI :
  - `off`
  - `protection_replay`

### Défaut

- `phase4_mode = off`

Donc l’IHM ne modifie jamais implicitement les exits d’un backtest standard.

---

## Artefacts Phase 4 livrés

Quand `phase4_mode = protection_replay` et qu’un `output_dir` est fourni, la Phase 4 produit :

- `phase4_protection_replay.csv`
- `phase4_protection_replay_signals.csv`
- `phase4_protection_replay_summary.json`

Ces artefacts viennent s’ajouter aux artefacts déjà produits par les Phases 2 et 3.

### Report structuré

Le `report.json` est enrichi avec :

- `params.phase4.enabled`
- `params.phase4.mode`
- `params.phase4.protection_replay`

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

- `backtesting/execution_lifecycle_replay.py`
- `prompt/backtest/phase4.md`

---

## Validation exécutée

### Suites pytest exécutées

```powershell
pytest -q --no-cov tests/test_phase2_bridges.py tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_backtesting.py
pytest -q --no-cov tests/test_backtesting_refactor.py
```

### Résultat

- suites ciblées Phase 4 / CLI / IHM / moteur / replay : **vert**
- suite de compatibilité backtesting/refactor : **vert**

---

## Garanties de non-régression live

La Phase 4 respecte la règle “zéro régression sur les pipelines live” car :

1. aucun comportement live de `execution_engine` n’a été modifié ;
2. aucun comportement live de `risk_management` n’a été modifié ;
3. toute la logique Phase 4 est encapsulée dans `backtesting/` ;
4. le moteur garde son comportement historique par défaut ;
5. l’activation est conditionnelle à un enchaînement explicite :
   - Phase 2
   - puis Phase 3
   - puis Phase 4
6. l’IHM ne force aucune activation implicite.

En pratique :

- les pipelines live existants ne changent pas ;
- les backtests standards ne changent pas ;
- seuls les runs opt-in bénéficient de la fidélité supplémentaire sur les protections.

---

## Limites connues / périmètre volontairement conservateur

La Phase 4 améliore sensiblement la fidélité des exits, mais reste volontairement prudente.

### Ce qu’elle fait

- elle réutilise les protections dérivées des child intents ;
- elle rapproche les sorties du backtest du comportement attendu côté exécution ;
- elle renforce la cohérence entre :
  - décision de risque,
  - exécution simulée,
  - protections actives,
  - PnL backtest.

### Ce qu’elle ne fait pas encore

- elle ne reproduit pas tout le cycle de vie OMS/broker ;
- elle ne gère pas encore des fills partiels multi-étapes ;
- elle ne reconstitue pas encore un watcher de protection complet avec événements persistés dans la boucle PnL ;
- elle reste une approximation prudente des transitions de protection, pas une réplique totale du runtime live.

---

## Conclusion

La Phase 4 est maintenant livrée avec les propriétés suivantes :

- **strictement opt-in** ;
- **sans régression sur les pipelines live** ;
- **sans changement du chemin standard** ;
- **testée et documentée**.

Elle réduit encore l’écart entre :

- les `PortfolioEntry` issus du vrai moteur de risque,
- les child intents d’exécution simulés,
- et les règles de sortie effectivement appliquées par le backtest.

La suite logique d’une Phase 5, si elle est souhaitée, serait d’aller vers un replay encore plus fin du cycle de vie d’exécution : transitions, événements, protections promues/cancelled, et éventuellement scénarios de fills partiels — toujours dans une enveloppe backtesting-only et strictement opt-in.

