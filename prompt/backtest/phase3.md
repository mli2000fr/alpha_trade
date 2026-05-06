# Phase 3 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 3

La Phase 3 visait à franchir une étape supplémentaire de fidélité backtesting, **sans toucher aux pipelines live** et sans modifier le comportement standard déjà stabilisé en Phases 1 et 2.

Après la Phase 1 (fidélité PIT amont) et la Phase 2 (bridges opt-in vers `risk_management` et `execution_engine`), il restait un écart important :

- la Phase 2 produisait des diagnostics d’exécution réalistes ;
- mais le **PnL du backtest** restait principalement piloté par le replay classique des signaux ;
- les quantités et décisions d’exécution simulées n’étaient pas encore **réinjectées chronologiquement** dans le moteur de backtest.

L’objectif de la Phase 3 a donc été de livrer un mode **opt-in** capable de :

1. repartir des `PortfolioEntry` issus du vrai moteur de risque ;
2. rejouer chronologiquement les cibles / intents / fills simulés sur les séances J+1 ;
3. réinjecter les quantités exécutées dans le moteur de backtest ;
4. conserver le chemin historique intact quand ce mode n’est pas demandé.

---

## Décision d’architecture

Pour éviter toute régression live, la Phase 3 n’a **pas** modifié les modules d’exécution live.

Au lieu de cela, elle introduit un nouveau composant purement backtesting :

- `backtesting/execution_replay.py`

Ce module complète les bridges de la Phase 2 :

- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`

### Principe

Le nouveau replay Phase 3 :

- prend les `PortfolioEntry` acceptés ;
- résout leur séance d’exécution réelle dans le backtest via la prochaine séance disponible (J+1) ;
- lit le vrai `open` de cette séance ;
- reconstruit :
  - `ExecutionTarget`
  - `OrderIntent` d’entrée
  - enfants de protection (TP / trailing stop / initial stop)
  - `ExecutionFill`
- génère un `signals_df` enrichi, contenant notamment :
  - `approved_shares`
  - `filled_qty`
  - `fill_price`
  - `execution_date`
- demande ensuite au moteur `BacktestEngine` de respecter ces quantités quand le mode opt-in est actif.

---

## Nouveau contrôle CLI

La Phase 3 introduit un nouveau flag séparé :

- `--phase3-mode off`
- `--phase3-mode execution_replay`

### Pourquoi un flag distinct ?

Il aurait été possible d’étendre `phase2_mode`, mais ce choix aurait brouillé la frontière entre :

- la **fidélité diagnostique** de Phase 2 ;
- la **réinjection effective des quantités d’exécution** en Phase 3.

Le flag dédié permet de garder une progression claire :

- `phase2_mode=off` → backtest historique
- `phase2_mode=risk` → vrai risque, PnL standard
- `phase2_mode=risk_execution` → vrai risque + diagnostics exécution
- `phase2_mode=risk_execution` + `phase3_mode=execution_replay` → vrai risque + exécution simulée + réinjection des quantités dans le moteur

### Règle de compatibilité

La combinaison suivante est obligatoire :

- `phase3_mode=execution_replay` exige `phase2_mode=risk_execution`

Sinon la CLI fait un **fail-fast explicite**, pour éviter tout comportement implicite ou incohérent.

---

## Intégration dans le moteur de backtest

### 1. `backtesting/execution_replay.py`

Nouveau module responsable de :

- programmer les `PortfolioEntry` sur la vraie séance d’exécution suivante ;
- fabriquer les `ExecutionTarget`, `OrderIntent`, `ExecutionFill` ;
- produire un `ExecutionReplayResult` ;
- écrire les artefacts Phase 3.

### 2. `backtesting/simulator.py`

Le moteur `BacktestEngine` a été étendu avec un contrôle opt-in :

- `BacktestConfig.execution_replay_mode = "off" | "execution_replay"`

Par défaut :

- `off`

Donc le comportement standard ne change pas.

Quand `execution_replay_mode="execution_replay"`, le moteur sait désormais utiliser les quantités présentes dans les signaux si elles existent :

- `filled_qty`
- `approved_shares`
- `target_shares`

La priorité reste strictement bornée à ce mode opt-in.

### 3. Réutilisation du moteur existant

Le moteur de backtest ne change pas de nature :

- il reste stateful ;
- il garde la convention `signal J → exécution J+1 open` ;
- il conserve la logique existante de sorties / micro-structure / cash / PDT / swing.

La nouveauté est qu’en mode Phase 3, les **quantités d’entrée** ne sont plus simplement dérivées du budget backtest classique : elles peuvent être imposées par le replay d’exécution simulé.

---

## Intégration IHM

La Phase 3 a été propagée à l’IHM backtesting avec un défaut neutre.

### Modifications

Dans `ihm/services/backtesting_runner.py` :

- ajout de `phase3_mode` dans `BacktestRunOptions`
- ajout du flag CLI `--phase3-mode`

Dans `ihm/pages/backtesting.py` :

- ajout d’une ligne de référence utilisateur `phase3_mode`
- ajout d’un sélecteur UI :
  - `off`
  - `execution_replay`

### Défaut

- `phase3_mode = off`

Cela garantit qu’aucun utilisateur IHM n’active Phase 3 sans le demander explicitement.

---

## Artefacts Phase 3 livrés

Quand `phase3_mode = execution_replay` et qu’un `output_dir` est fourni, la livraison Phase 3 écrit :

- les artefacts d’exécution Phase 2 réutilisés :
  - `phase2_execution_targets.csv`
  - `phase2_execution_entry_intents.csv`
  - `phase2_execution_child_intents.csv`
  - `phase2_execution_fills.csv`
  - `phase2_execution_tca_summary.json`
  - `phase2_execution_summary.json`
- les nouveaux artefacts Phase 3 :
  - `phase3_execution_replay_signals.csv`
  - `phase3_execution_replay_summary.json`

Le `report.json` est enrichi avec :

- `params.phase3.enabled`
- `params.phase3.mode`
- `params.phase3.execution_replay`

et conserve bien sûr les blocs déjà existants Phase 1 / Phase 2.

---

## Fichiers modifiés / créés

### Modifiés

- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`
- `tests/test_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`
- `tests/test_pages_backtesting.py`
- `tests/test_phase2_bridges.py`

### Créé

- `backtesting/execution_replay.py`
- `prompt/backtest/phase3.md`

---

## Validation exécutée

### Suites pytest exécutées

```powershell
pytest -q --no-cov tests/test_phase2_bridges.py tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_backtesting.py
pytest -q --no-cov tests/test_backtesting_refactor.py
```

### Résultat

- suites ciblées Phase 3 / CLI / IHM / bridges : **vert**
- suite de compatibilité backtesting/refactor : **vert**

---

## Garanties de non-régression live

Cette Phase 3 respecte la règle “zéro régression sur les pipelines live” pour les raisons suivantes :

1. aucun comportement live de `execution_engine` n’a été modifié ;
2. aucun comportement live de `risk_management` n’a été modifié ;
3. le replay Phase 3 est encapsulé dans `backtesting/execution_replay.py` ;
4. le moteur `BacktestEngine` reste inchangé par défaut grâce à `execution_replay_mode="off"` ;
5. la CLI et l’IHM n’activent rien implicitement ;
6. la combinaison invalide `phase3_mode=execution_replay` sans `phase2_mode=risk_execution` est refusée explicitement.

En pratique :

- les pipelines live existants ne changent pas ;
- les runs de backtest standards ne changent pas ;
- la Phase 3 n’apparaît que dans un chemin opt-in strictement borné.

---

## Limites connues / périmètre volontairement conservateur

La Phase 3 livrée reste volontairement prudente.

### Ce qu’elle fait

- elle améliore la cohérence entre :
  - les décisions du moteur de risque ;
  - les intents/fills simulés ;
  - les quantités réellement rejouées dans le backtest.

### Ce qu’elle ne fait pas encore

- elle ne remplace pas un OMS / broker réel ;
- elle ne soumet aucun ordre ;
- elle ne pilote pas encore un state machine d’exécution complet dans la boucle PnL ;
- elle ne transforme pas encore le backtest en simulation broker full lifecycle.

Autrement dit, la Phase 3 fournit un **execution replay chronologique réaliste mais contrôlé**, pas une reproduction intégrale de la pile live.

---

## Conclusion

La Phase 3 est maintenant livrée avec les propriétés suivantes :

- **strictement opt-in** ;
- **sans régression sur les pipelines live** ;
- **sans changement du chemin standard** ;
- **testée et documentée**.

Elle réduit l’écart entre :

- les cibles issues du vrai moteur de risque,
- les intents/fills simulés de la couche exécution,
- et le PnL effectivement rejoué par le backtest.

La suite logique, si on veut aller plus loin en Phase 4, serait d’explorer un replay encore plus fin du cycle de vie d’exécution (transitions, protections, événements), toujours dans une enveloppe backtesting-only et opt-in.

