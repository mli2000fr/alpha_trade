# Portage live pipeline — Priorité 2 (gap filter d’entrée)

## Résumé exécutif

Cette passe finalise le **portage opérateur live** du point P2 le plus immédiat et directement actionnable :

- **le gap filter d’entrée (`max-entry-gap-pct`) est maintenant visible dans l’IHM Pipeline, propagé dans la commande d’exécution, accepté par `run_execution.py`, et couvert par des tests ciblés.**

---

## 1) Ce qui est désormais en place

### IHM Pipeline

Dans `ihm/pages/_execution_center/__init__.py`, l’expander :

- `Execution — transition trigger avancé & debug`

expose maintenant le champ :

- `Gap d'entrée max (fraction)`

Clé de session pilotée :

- `pipeline_execution_max_entry_gap_pct`

### Commande pipeline

Dans `ihm/services/pipeline_runner.py` :

- `PipelineLaunchOptions` porte `execution_max_entry_gap_pct`
- la construction de commande ajoute `--max-entry-gap-pct <valeur>` pour le step `execution`

### CLI live

Dans `run_execution.py` :

- le parser accepte `--max-entry-gap-pct`
- `run(...)` reçoit `max_entry_gap_pct`
- `_build_runtime_preset(...)` injecte cette valeur dans le preset runtime final

---

## 2) Pourquoi c’est utile

Ce filtre répond directement à l’un des constats du rapport d’audit :

- un run sans garde-fou d’entrée sur gap peut accepter des entrées trop agressives après ouverture/décalage violent
- en live/paper, cela améliore la discipline d’exécution sur les titres volatils ou lors de séances stressées

Exemple opérateur :

- `0.00` → désactivé
- `0.02` → bloque si l’écart dépasse 2 %
- `0.03` → bloque si l’écart dépasse 3 %

---

## 3) Préremplissage preset capital

Le preset petit compte testé dans cette passe préremplit bien aussi :

- `pipeline_execution_max_entry_gap_pct = 0.03`

Ce comportement est cohérent avec `config/capital_presets.yaml`.

---

## 4) Tests et validations exécutés

### Compilation

```powershell
python -m py_compile "F:\projets\run_execution.py" "F:\projets\ihm\services\pipeline_runner.py" "F:\projets\ihm\pages\_execution_center\__init__.py" "F:\projets\ihm\pages\_execution_center\_render_pending.py"
```

### Tests ciblés

```powershell
python -m pytest "F:\projets\tests\test_ihm_pipeline_runner.py" -q --no-cov -k "build_pipeline_command_injects_account_for_account_aware_steps"
python -m pytest "F:\projets\tests\test_execution_center_prefills.py" -q --no-cov -k "small_account_sets_expected_values"
python -m pytest "F:\projets\tests\test_ihm_pipeline_e2e.py" -q --no-cov -k "render_execution_block_returns_expected_keys"
```

Résultat : **OK**.

---

## 5) Fichiers concernés

- `F:\projets\run_execution.py`
- `F:\projets\ihm\services\pipeline_runner.py`
- `F:\projets\ihm\pages\_execution_center\__init__.py`
- `F:\projets\ihm\pages\_execution_center\_render_pending.py`
- `F:\projets\tests\test_ihm_pipeline_runner.py`
- `F:\projets\tests\test_execution_center_prefills.py`
- `F:\projets\tests\test_ihm_pipeline_e2e.py`

---

## Résumé opérationnel

Le pipeline live/paper peut maintenant être lancé depuis l’IHM avec un vrai réglage opérateur de type :

- **`Gap d'entrée max (fraction)` = `0.02` à `0.03`**

et cette valeur est effectivement transportée jusqu’à `run_execution.py`.

C’est donc un garde-fou d’exécution supplémentaire désormais **visible, paramétrable, propagé et testé**.

---

## Addendum — passe métier live complémentaire (`capital_preservation` + contrainte sectorielle)

### Résumé

Une passe métier complémentaire a ensuite été menée pour vérifier deux points live critiques :

- le durcissement réel du mode `capital_preservation` côté exécution live ;
- le caractère effectivement contraignant du cap sectoriel côté pipeline live.

### Constat principal

Le pipeline live transmettait déjà correctement la contrainte de portefeuille pertinente via l’étape Risk (`risk_max_sector_weight`), mais l’exécution live ne disposait pas encore d’un **filet de sécurité propre** si des `portfolio_targets` devenaient incompatibles avec le régime marché courant.

### Ce qui a été ajouté

#### 1. Propagation des garde-fous issus du snapshot régime

Dans `run_execution.py`, le snapshot régime live propage désormais aussi vers `ExecutionConfig` :

- `effective_max_positions`
- `max_position_weight`
- `max_sector_weight`

Ces valeurs sont injectées dans de nouveaux champs de configuration d’exécution :

- `regime_max_positions`
- `regime_max_position_weight`
- `regime_max_sector_weight`

#### 2. Filet de sécurité live avant soumission des intents

Dans `execution_engine/order_intents.py`, un filtre pur a été ajouté :

- `filter_targets_by_live_regime_guards(...)`

Ce filtre applique avant construction des intents :

- une borne sur le **poids max par ligne** ;
- une borne sur le **poids cumulé par secteur** ;
- une borne sur le **nombre max de positions**.

#### 3. Application effective dans l’executor live

Dans `execution_engine/executor.py`, ce filtre est exécuté avant `build_entry_intents(...)`.

Les blocages sont maintenant historisés avec des événements auditables de type :

- `SkippedByRegimeGuard[regime_max_position_weight]`
- `SkippedByRegimeGuard[regime_max_sector_weight]`
- `SkippedByRegimeGuard[regime_max_positions]`

Des métriques spécifiques sont également incrémentées côté exécution.

### Clarification métier importante

- `backtesting_max_sector_exposure_pct` reste un paramètre **backtest** ;
- côté live, la contrainte de portefeuille pertinente portée par le pipeline est bien **`risk_max_sector_weight`** ;
- cette contrainte est bien transmise jusqu’à l’étape 11 (`risk_management`) ;
- et l’exécution live dispose maintenant d’un **second garde-fou défensif** dérivé du régime marché.

### Fichiers concernés par cette passe complémentaire

- `F:\projets\execution_engine\config.py`
- `F:\projets\execution_engine\order_intents.py`
- `F:\projets\execution_engine\executor.py`
- `F:\projets\run_execution.py`
- `F:\projets\tests\test_order_intents.py`
- `F:\projets\tests\test_execution_engine_executor.py`
- `F:\projets\tests\test_execution_engine_config.py`
- `F:\projets\tests\test_execution_center_prefills.py`
- `F:\projets\tests\test_ihm_pipeline_runner.py`

### Validations exécutées

#### Compilation

```powershell
python -m py_compile "F:\projets\execution_engine\config.py" "F:\projets\execution_engine\order_intents.py" "F:\projets\execution_engine\executor.py" "F:\projets\run_execution.py" "F:\projets\tests\test_order_intents.py" "F:\projets\tests\test_execution_engine_executor.py" "F:\projets\tests\test_execution_engine_config.py" "F:\projets\tests\test_execution_center_prefills.py" "F:\projets\tests\test_ihm_pipeline_runner.py"
```

#### Tests ciblés

```powershell
pytest -q --no-cov "F:\projets\tests\test_order_intents.py" "F:\projets\tests\test_execution_engine_executor.py" "F:\projets\tests\test_execution_engine_config.py" "F:\projets\tests\test_execution_center_prefills.py" "F:\projets\tests\test_ihm_pipeline_runner.py" "F:\projets\tests\test_run_execution.py"
pytest -q --no-cov "F:\projets\tests\test_risk_regime_apply.py" "F:\projets\tests\test_constraints.py" "F:\projets\tests\test_market_regime.py"
```

Résultat : **OK**.

### Conclusion opérationnelle

Après cette passe complémentaire :

- le mode `capital_preservation` live est durci par des limites effectivement appliquées avant soumission ;
- le cap sectoriel côté pipeline live est bien pris en compte sur la chaîne IHM → Risk ;
- l’exécution live dispose désormais d’un garde-fou supplémentaire sectoriel / positions dérivé du régime marché.

