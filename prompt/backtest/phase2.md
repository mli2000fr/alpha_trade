# Phase 2 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 2

La Phase 2 visait à **augmenter la fidélité aval du backtest** en réutilisant les briques réelles de `risk_management` et `execution_engine`, tout en respectant la contrainte principale du projet:

- **zéro régression sur les pipelines live** ;
- **comportement par défaut inchangé** ;
- **activation strictement opt-in** depuis le backtesting.

L’idée directrice a été de **ne pas modifier le runtime live** des modules de risque et d’exécution, mais d’ajouter des **bridges dédiés côté `backtesting/`**.

---

## Principe d’architecture retenu

Au lieu de dupliquer la logique de sizing/risk/execution dans le backtest, la Phase 2 introduit deux adaptateurs:

- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`

### 1. `risk_bridge.py`

Ce bridge transforme les snapshots PIT du backtest en entrées compréhensibles par le moteur réel de risque:

- `CandidateScore`
- `PriceInfo`
- `PredictionInfo`
- matrice de rendements pour le filtre de corrélation

Puis il appelle le vrai:

- `risk_management.portfolio_builder.PortfolioBuilder.build(...)`

Enfin, il reconvertit les `PortfolioEntry` en un `signals_df` compatible avec le moteur de simulation vectorisé du backtest.

### 2. `execution_bridge.py`

Ce bridge prend les `PortfolioEntry` produits par le bridge risk et les adapte vers:

- `ExecutionTarget`

Puis il réutilise les primitives pures de `execution_engine`:

- `build_entry_intents(...)`
- `build_take_profit_intent(...)`
- `build_trailing_stop_intent(...)`
- `build_initial_stop_intent(...)`
- `compute_slippage_bps(...)`
- `compute_implementation_shortfall(...)`
- `build_tca_summary(...)`

Les fills sont simulés **sans broker**, de manière déterministe, au prix d’entrée cible.

---

## Intégration CLI livrée

Le backtest dispose maintenant d’un flag opt-in explicite:

- `--phase2-mode off`
- `--phase2-mode risk`
- `--phase2-mode risk_execution`

### Sémantique

- `off`
  - conserve le chemin historique:
    - `replay_signals(...)`
    - puis `BacktestEngine.run(...)`
- `risk`
  - remplace uniquement la reconstruction de signaux par le bridge `risk_management`
- `risk_execution`
  - ajoute en plus la simulation d’intents/fills/TCA via `execution_engine`

### Garantie importante

Le chemin par défaut reste **strictement identique** au comportement précédent.

En particulier, dans `backtesting/cli/_impl.py`, les imports suivants sont désormais **paresseux** et n’ont lieu que si Phase 2 est activée:

- `risk_management.config.RiskConfig`
- `backtesting.risk_bridge.*`
- `execution_engine.config.ExecutionConfig`
- `backtesting.execution_bridge.*`

Cela évite de charger les couches risque/exécution quand `phase2_mode="off"`.

---

## Intégration IHM livrée

La Phase 2 a été exposée côté IHM backtesting, avec un défaut neutre:

- nouveau champ `phase2_mode` dans `ihm/services/backtesting_runner.py`
- nouvelle option de commande `--phase2-mode`
- nouvelle ligne de référence utilisateur dans `ihm/pages/backtesting.py`
- nouveau sélecteur UI:
  - `off`
  - `risk`
  - `risk_execution`

Le défaut reste:

- `phase2_mode = off`

Donc l’IHM n’introduit **aucune activation implicite**.

---

## Artefacts Phase 2 livrés

### Artefacts risque

Quand `phase2_mode != off` et qu’un `output_dir` est fourni:

- `phase2_risk_summary.json`
- `phase2_risk_entries.csv`
- `phase2_risk_signals.csv`

### Artefacts exécution

Quand `phase2_mode = risk_execution` et qu’un `output_dir` est fourni:

- `phase2_execution_targets.csv`
- `phase2_execution_entry_intents.csv`
- `phase2_execution_child_intents.csv`
- `phase2_execution_fills.csv`
- `phase2_execution_tca_summary.json`
- `phase2_execution_summary.json`

### Report structuré

Le `report.json` enrichit désormais `params.phase2` avec:

- `enabled`
- `mode`
- diagnostics `risk_bridge`
- diagnostics `execution_bridge`
- résumé `execution_tca`

Le tout reste purement descriptif et **n’impacte pas** les pipelines live.

---

## Fichiers modifiés / créés

### Modifiés

- `backtesting/cli/_impl.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`
- `tests/test_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`
- `tests/test_pages_backtesting.py`

### Créés

- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `tests/test_phase2_bridges.py`
- `prompt/backtest/phase2.md`

---

## Validation exécutée

### Suites pytest exécutées

```powershell
pytest -q --no-cov tests/test_phase2_bridges.py tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_backtesting.py
pytest -q --no-cov tests/test_backtesting_refactor.py
```

### Résultat

- suites ciblées Phase 2: **vert**
- suite de compatibilité backtesting/refactor: **vert**

---

## Garanties de non-régression live

Cette livraison respecte la contrainte utilisateur “zéro régression sur les pipelines live” car:

1. aucun comportement live de `risk_management` n’a été modifié ;
2. aucun comportement live de `execution_engine` n’a été modifié ;
3. le chemin par défaut du backtest reste `phase2_mode=off` ;
4. les imports et appels Phase 2 sont conditionnels ;
5. l’IHM n’active rien implicitement.

En pratique:

- les pipelines 1→12 existants ne changent pas de comportement du seul fait de cette Phase 2 ;
- la fidélité supplémentaire n’est disponible que si l’utilisateur la demande explicitement.

---

## Limites connues / périmètre volontairement conservateur

La Phase 2 livrée reste volontairement prudente:

1. la simulation d’exécution n’envoie aucun ordre broker ;
2. les fills Phase 2 sont simulés de façon déterministe au prix cible ;
3. le bridge exécution sert d’abord à auditer:
   - intents
   - protections
   - TCA
4. le moteur vectorisé du backtest reste la source principale de PnL simulée.

Autrement dit, la Phase 2 améliore surtout:

- la **fidélité des décisions de portefeuille** ;
- la **traçabilité des intentions d’exécution** ;
- la **comparabilité future** entre backtest et exécution réelle.

---

## Conclusion

La **Phase 2 est maintenant implémentée** dans un mode:

- **strictement opt-in** ;
- **sans régression sur le chemin standard** ;
- **documenté et testé**.

Le backtest peut désormais, sur demande, s’appuyer sur les briques réelles de:

- `risk_management`
- `execution_engine`

sans contaminer le comportement live existant.

