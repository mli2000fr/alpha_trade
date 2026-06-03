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
