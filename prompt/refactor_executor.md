# Audit compatibilité `execution_engine` ↔ `risk_management`

_Date_: 2026-05-20

## 1. Objectif

Vérifier que le module `execution_engine` consomme correctement la sortie de
`risk_management`, identifier les incohérences opérationnelles, appliquer les
adaptations minimales réellement bloquantes, puis proposer un plan de
convergence exploitable.

---

## 2. Périmètre audité

### Entry points / lanceurs
- `run_execution.py`
- `execution_engine/cli.py`
- `execution_engine/__main__.py`
- `risk_management/cli.py`
- `ihm/services/pipeline_runner.py`

### Contrats runtime / DB
- `risk_management/audit.py`
- `risk_management/db_io.py`
- `execution_engine/db_io.py`
- `execution_engine/models.py`
- `risk_management/models.py`
- `database/run_business_summaries.py`

### Config partagée / YAML
- `execution_engine/config.py`
- `risk_management/config.py`
- `config.yaml`

### Validation ciblée
- `tests/test_execution_engine_config.py`
- `tests/test_execution_db_io.py`
- `tests/test_execution_cli_cancel_all.py`
- `tests/test_run_execution.py`

---

## 3. Verdict synthétique

### Conclusion courte
Le couple `risk_management` → `execution_engine` est **globalement compatible**
pour le flux principal (`portfolio_targets` → `execution_targets` → ordres),
mais l’audit a confirmé plusieurs écarts de cohérence autour du **scope de
compte implicite**, des **defaults CLI** et du **branchage YAML partagé**.

### État après adaptations appliquées
- **Compatibilité DB risk → execution corrigée** pour le compte implicite
  `default`, y compris sur l’historique déjà persisté avec `account_id = NULL`
  dans `run_business_summaries`.
- **Defaults du CLI direct `execution_engine` réalignés** sur le profil
  opérationnel `cash / PDT off / swing_only on`, cohérent avec `run_execution.py`
  et l’IHM.
- **`run_execution.run()` réaligné** avec son propre parseur et les presets.
- **`risk_management.trailing_stop` est désormais réellement consommé** par les
  chemins de lancement `execution`.

### Verdict détaillé
- **P0 bloquants** : 2 trouvés, 2 corrigés.
- **P1 cohérence opérationnelle** : 3 trouvés, 3 corrigés.
- **P2 / gouvernance / dette** : le périmètre audité est désormais largement stabilisé ; ne restent surtout que des sujets d’extension hors de ce scope.

---

## 4. Cartographie du contrat `risk_management` → `execution_engine`

## 4.1 Contrat principal de données

`risk_management` persiste :
- `risk_decisions`
- `portfolio_targets`
- `run_business_summaries(step_key='risk_management')`

`execution_engine` recharge :
- `portfolio_targets` via `ExecutionRepository.load_portfolio_targets(...)`
- le dernier `risk_run_id` via `run_business_summaries`
- le garde-fou “dernier run = 0 cible” via `_resolve_latest_risk_run_from_summary(...)`

## 4.2 Contrat de modèle utile

### Champs bien transportés côté risk → execution
Le mapping est cohérent pour les champs suivants :
- `run_id` → `risk_run_id`
- `symbol`
- `shares` → `target_shares`
- `entry_price`
- `target_weight`
- `candidate_rank`
- `decision_rank`
- `selector_signal_mode`
- `selection_explanation`
- `selector_earnings_blackout`
- `stop_price_initial`
- `risk_per_share`
- `risk_budget_dollars`
- `initial_risk_dollars`
- `target_notional`
- `conviction_score`
- `sizing_method`
- `kelly_fraction`

Cela est cohérent avec :
- `risk_management/audit.py`
- `risk_management/db_io.py`
- `execution_engine/db_io.py`
- `execution_engine/models.py`

## 4.3 Contrat de lancement / paramètres opérateur

### Chemin canonique actuel
Le chemin le plus complet est :
- IHM → `run_execution.py`

Ce wrapper ajoute des garde-fous que `python -m execution_engine` n’applique pas
encore tous de manière native.

---

## 5. Adaptations appliquées pendant cet audit

## 5.1 P0 — Compatibilité historique et compte implicite `default`

### Problème
`risk_management` pouvait persister un résumé dans `run_business_summaries`
avec `account_id = NULL` pour le compte implicite, tandis que
`execution_engine` recherchait strictement `account_id = 'default'`.

### Impact
- résolution erronée du dernier `risk_run_id`
- perte possible du garde-fou :
  **si le dernier run risk a produit 0 cible, execution ne doit surtout pas
  retomber sur un ancien `portfolio_targets`**

### Correction appliquée
#### `execution_engine/db_io.py`
- `_resolve_latest_risk_run_from_summary(...)` traite désormais
  `account_id IS NULL` comme synonyme historique de `default`

#### `risk_management/cli.py`
- normalisation explicite du scope de compte vers `default`
  lors de :
  - `shadow_compare`
  - `persist_decisions(...)`
  - `persist_portfolio_targets(...)`
  - `persist_run_business_summary(...)`

### Validation
- test ajouté :
  `tests/test_execution_db_io.py::test_load_latest_portfolio_targets_treats_null_summary_account_as_default`

---

## 5.2 P1 — Defaults CLI incohérents entre lanceurs

### Problème
Le CLI direct `execution_engine` utilisait par défaut :
- `account_type = margin`
- `pdt_rule = auto`
- `swing_only = False`

alors que :
- `run_execution.py`
- l’IHM
- les presets capital

sont centrés sur :
- `cash`
- `off`
- `True`

### Impact
Un opérateur lançant `python -m execution_engine` pouvait obtenir un comportement
très différent du chemin canonique IHM / `run_execution.py`.

### Correction appliquée
#### `execution_engine/cli.py`
- `--account-type` → défaut `cash`
- `--pdt-rule` → défaut `off`
- `--swing-only` → `BooleanOptionalAction`, défaut `True`

#### `run_execution.py`
- defaults de l’API `run(...)` réalignés sur :
  - `account_type='cash'`
  - `pdt_rule='off'`
  - `swing_only=True`

### Validation
- test ajouté :
  `tests/test_execution_cli_cancel_all.py::test_cli_run_defaults_align_with_cash_swing_profile`
- tests existants `test_run_execution.py` toujours verts

---

## 5.3 P1 — Faux levier YAML sur `risk_management.trailing_stop`

### Problème
Le commentaire et le modèle `ExecutionConfig.trailing_stop` laissaient entendre
que `config.yaml > risk_management.trailing_stop` pilotait l’executor, mais le
runtime `execution` ne chargeait pas effectivement cette section.

### Impact
Risque de **paramètre fantôme** : l’opérateur croit agir via `config.yaml`, mais
le runtime continue sur les valeurs par défaut du dataclass.

### Correction appliquée
#### `execution_engine/config.py`
- ajout de `load_trailing_stop_config_from_yaml(...)`

#### `run_execution.py`
- injection de `trailing_stop=load_trailing_stop_config_from_yaml()` dans
  `ExecutionConfig(...)`

#### `execution_engine/cli.py`
- même injection pour le CLI direct

### Validation
- test ajouté :
  `tests/test_execution_engine_config.py::test_load_trailing_stop_config_from_yaml_uses_risk_management_section`

---

## 6. Audit de cohérence détaillé

## 6.1 Points cohérents / bien implémentés

### A. Contrat `portfolio_targets`
Le schéma lu par `execution_engine` est cohérent avec ce que `risk_management`
écrit aujourd’hui.

### B. Cibles enrichies
Les champs utiles au contrôle d’exécution et au post-mortem sont bien transportés :
- stop initial
- risque par action
- budget de risque
- notional cible
- rangs / mode selector

### C. Scope `account_id` sur `portfolio_targets`
Le chargement des cibles par compte est correctement géré côté execution.

### D. Persistance snapshot d’exécution
`execution_targets_snapshot` conserve bien une photographie compatible des cibles
risk consommées.

---

## 6.2 Anomalies / incohérences restantes

## A-EXE-001 — Doctrine launcher execution unifiée

### Constat initial
Le wrapper `run_execution.py` ajoutait des comportements absents du CLI direct
`execution_engine` :
- preflight live bloquant
- hard fail si equity broker indisponible
- injection explicite d’un `CircuitBreaker`
- preflight `market_regime`
- affichage opérateur enrichi
- support `auto_watcher`
- propagation des feature flags `--disable-sentiment` / `--disable-ml`

### Risque
Deux entry points “execution” existent avec des niveaux de sécurité différents.
Un opérateur peut croire lancer l’équivalent du run canonique alors qu’il lance
une version plus bas niveau.

### Doctrine retenue
`run_execution.py` devient le **launcher canonique unique** pour le flux `run`.

`python -m execution_engine` reste supporté, mais comme **façade de compatibilité**
qui délègue le sous-chemin `run` à `run_execution.py`. La sous-commande
`cancel-all` reste native à `execution_engine`.

### Correction appliquée
- `execution_engine/cli.py` délègue désormais le flux `run` vers :
  - `run_execution.resolve_mode_from_broker_mode(...)`
  - `run_execution.abort_missing_env(...)`
  - `run_execution.run(...)`
- `run_execution.py` expose explicitement le helper canonique de résolution de
  mode et accepte les overrides runtime nécessaires au shim de compatibilité
  (`submission_window`, trailing activation, timeouts, slippage, batch, etc.)
- le CLI direct `execution_engine` expose désormais aussi les flags canoniques
  manquants (`--debug`, `--auto-rebalance`, `--submission-window`,
  `--auto-watcher`)
- `doc/execution_engine.md` documente cette doctrine opérateur

### Statut
**Corrigé**.

### Recommandation
Conserver cette gouvernance :
1. toute nouvelle option opérateur `run` est d’abord implémentée dans
   `run_execution.py` ;
2. `execution_engine/cli.py` ne fait que la relayer si une compatibilité
   historique est nécessaire ;
3. `cancel-all` reste un point d’entrée natif spécifique à `execution_engine`.

---

## A-EXE-002 — Ancien levier fantôme `config.yaml > execution.modes`

### Constat initial
Les clés :
- `execution.modes.close_only_allows_position_management`
- `execution.modes.cash_only_allows_new_entries`

étaient présentes dans `config.yaml`, mais l’audit textuel n’avait trouvé aucune
lecture active dans le code Python.

### Risque
Paramètres fantômes / faux levier opérateur.

### Correction appliquée
- la section `execution.modes` a été retirée de `config.yaml`
- un garde-fou anti-régression a été ajouté dans
  `tests/test_config_yaml_schema.py::test_execution_modes_section_is_absent`
- la doc d’audit précise désormais que le runtime dérive `entry_mode` depuis le
  snapshot `market_regime`, pas depuis `config.yaml`

### Statut
**Corrigé**.

### Recommandation
Conserver l’absence de cette section tant qu’aucun branchement runtime explicite
n’existe.

---

## A-EXE-003 — Ancienne dépendance IHM `deps="run_risk"` incohérente

### Constat initial
Dans `ihm/services/pipeline_runner.py`, l’étape :
- `key="execution"`

portait :
- `deps="run_risk"`

alors que l’étape déclarée est :
- `key="risk_management"`

### Risque
Incohérence de cartographie fonctionnelle, confusion IHM/documentation, voire bug
si cette clé est exploitée programmatiquement ailleurs.

### Correction appliquée
- `ihm/services/pipeline_runner.py` utilise désormais `deps="risk_management"`
- un test de contrat verrouille ce mapping :
  `tests/test_ihm_pipeline_runner.py::test_execution_step_depends_on_risk_management_contract_name`

### Statut
**Corrigé**.

### Recommandation
Conserver `risk_management` comme nom contractuel unique sur la cartographie
IHM/runtime.

---

## A-EXE-004 — Dette Ruff résiduelle sur le périmètre executor

### Constat
La passe initiale laissait encore des dettes Ruff sur le périmètre audité.
La passe suivante a nettoyé le sous-périmètre ciblé :
- `execution_engine/config.py`
- `execution_engine/cli.py`
- `execution_engine/db_io.py`
- `run_execution.py`
- `ihm/services/pipeline_runner.py`
- `tests/test_execution_engine_config.py`
- `tests/test_execution_db_io.py`
- `tests/test_execution_cli_cancel_all.py`
- `tests/test_run_execution.py`
- `tests/test_run_execution_blocks_on_preflight_fail.py`
- `tests/test_ihm_pipeline_runner.py`
- `tests/test_config_yaml_schema.py`
- `tests/test_executor.py`
- `tests/test_execution_engine_executor.py`
- `tests/test_executor_phases.py`

La passe Ruff complémentaire a confirmé que `execution_engine/db_io.py` est
désormais propre sur ce périmètre, et a nettoyé les tests executor historiques
restants (notamment `datetime.UTC`, imports et variables locales inutilisées).

Des dettes Ruff plus larges restent possibles hors de ce sous-périmètre,
mais elles ne concernent plus `execution_engine/db_io.py` ni les tests executor
historiques explicitement traités ici.

### Risque
Dette de maintenabilité, bruit CI, signal qualité dégradé.

### Statut
**Corrigé sur le périmètre ciblé de cette passe, y compris `db_io.py` et les tests executor historiques prioritaires**.

### Recommandation
Poursuivre séparément la réduction de dette sur le périmètre executor élargi,
sans le mélanger à des changements de contrat runtime.

---

## 7. Plan proposé

## P0 — Robustesse cross-step / contrats runtime
1. **Conserver la normalisation `default`** désormais en place.
2. **Conserver** le test d’intégration complet désormais ajouté sur la chaîne
   `risk_management -> run_business_summaries -> execution_engine.load_portfolio_targets()`
   pour les cas :
   - compte explicite
   - compte implicite `default`
   - dernier run à 0 cible

## P1 — Convergence des lanceurs execution
1. **Conserver** `run_execution.py` comme launcher canonique unique du flux `run`.
2. Maintenir `execution_engine/cli.py` comme shim de compatibilité pour `run`
   et point d’entrée natif pour `cancel-all`.
3. Continuer à harmoniser les noms d’arguments entre les deux CLI quand c’est
   pertinent, mais sans recréer de logique métier dupliquée.

## P1 — Éliminer les paramètres fantômes
1. Conserver l’absence de `execution.modes` dans `config.yaml`.
2. Maintenir le garde-fou `tests/test_config_yaml_schema.py::test_execution_modes_section_is_absent`.
3. Conserver le test anti-régression pour `risk_management.trailing_stop` désormais branché.

## P2 — Hygiène / observabilité
1. Passe Ruff dédiée sur :
   - `execution_engine/*.py`
   - `tests/test_execution_*.py`
   - `run_execution.py`
2. Remplacer progressivement `timezone.utc` par `datetime.UTC` sur le périmètre
   executor si le style du repo converge vers cette règle.
3. **Conserver** la doc opérateur désormais clarifiée :
   - `run_execution.py` = launcher canonique
   - `python -m execution_engine` = compatibilité `run` + `cancel-all` natif

---

## 8. Validations exécutées

## Tests passés
```powershell
Set-Location "F:\projets"
python -m pytest tests\test_execution_engine_config.py tests\test_execution_db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py --no-cov -q
```

### Résultat
```text
............................................................................... [100%]
```

## Validation complémentaire — passe suivante
```powershell
Set-Location "F:\projets"
python -m pytest tests\test_execution_engine_config.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_ihm_pipeline_runner.py tests\test_config_yaml_schema.py --no-cov -q
python -m ruff check execution_engine\config.py execution_engine\cli.py run_execution.py ihm\services\pipeline_runner.py tests\test_execution_engine_config.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_ihm_pipeline_runner.py tests\test_config_yaml_schema.py --output-format concise
```

### Résultat
```text
......................................................................................................................... [100%]
All checks passed!
```

## Validation complémentaire — passe Ruff executor élargie
```powershell
Set-Location "F:\projets"
python -m ruff check execution_engine\config.py execution_engine\cli.py execution_engine\db_io.py run_execution.py ihm\services\pipeline_runner.py tests\test_execution_engine_config.py tests\test_execution_db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_ihm_pipeline_runner.py tests\test_config_yaml_schema.py tests\test_executor.py tests\test_execution_engine_executor.py tests\test_executor_phases.py --output-format concise
python -m pytest tests\test_execution_engine_config.py tests\test_execution_db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_ihm_pipeline_runner.py tests\test_config_yaml_schema.py tests\test_executor.py tests\test_execution_engine_executor.py tests\test_executor_phases.py --no-cov -q
```

### Résultat
```text
All checks passed!
............................................................................................................................................................................................ [100%]
```

## Validation complémentaire — fermeture A-EXE-001
```powershell
Set-Location "F:\projets"
python -m pytest tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_execution_db_io.py tests\test_ihm_pipeline_runner.py tests\test_entrypoints_and_market_calendar.py --no-cov -q
python -m ruff check execution_engine\cli.py run_execution.py execution_engine\__main__.py execution_engine\db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_execution_db_io.py tests\test_ihm_pipeline_runner.py tests\test_entrypoints_and_market_calendar.py doc\execution_engine.md --output-format concise
python -m pytest tests\test_execution_engine_config.py tests\test_execution_db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py tests\test_run_execution_blocks_on_preflight_fail.py tests\test_ihm_pipeline_runner.py tests\test_config_yaml_schema.py tests\test_executor.py tests\test_execution_engine_executor.py tests\test_executor_phases.py tests\test_entrypoints_and_market_calendar.py --no-cov -q
```

### Résultat
```text
..................................................................................................................... [100%]
All checks passed!
............................................................................................................................................................................................................. [100%]
```

## Lint ciblé exécuté
```powershell
Set-Location "F:\projets"
python -m ruff check execution_engine\config.py execution_engine\cli.py execution_engine\db_io.py risk_management\cli.py run_execution.py tests\test_execution_engine_config.py tests\test_execution_db_io.py tests\test_execution_cli_cancel_all.py tests\test_run_execution.py --output-format concise
```

### Résultat
- **pas de régression fonctionnelle bloquante détectée**
- **la dette Ruff initiale a été résorbée sur le périmètre executor/tests explicitement traité dans cet audit**
- des écarts peuvent encore subsister hors de ce sous-ensemble, notamment dans d’autres modules non audités ici

---

## 9. Fichiers modifiés dans cette passe

- `execution_engine/db_io.py`
- `risk_management/cli.py`
- `execution_engine/cli.py`
- `execution_engine/config.py`
- `run_execution.py`
- `doc/execution_engine.md`
- `tests/test_execution_db_io.py`
- `tests/test_execution_cli_cancel_all.py`
- `tests/test_execution_engine_config.py`
- `tests/test_executor.py`
- `tests/test_execution_engine_executor.py`
- `tests/test_executor_phases.py`
- `tests/test_run_execution.py`
- `tests/test_entrypoints_and_market_calendar.py`

---

## 10. Verdict final

Le module `execution_engine` est **désormais compatible de façon plus robuste**
avec `risk_management` sur les points les plus sensibles du contrat runtime :
- résolution du dernier run risk par compte
- compte implicite `default`
- defaults opérateur cohérents
- consommation effective du YAML `risk_management.trailing_stop`
- doctrine launcher unifiée (`run_execution.py` canonique, `execution_engine` en shim de compatibilité pour `run`)
- test cross-step complet `run_business_summaries -> load_portfolio_targets()`

Les principaux risques résiduels ne portent plus sur le **mapping risk → execution**
ni sur la **coexistence de deux launchers execution divergents**. Les travaux
restants relèvent désormais surtout d’extensions hors de ce périmètre audité
(nouveaux launchers, nouvelle doc transverse, nouvelles surfaces de lint non
encore visées).

Les sujets initialement ouverts sur la **doctrine opérateur** et le **test
cross-step** ont été refermés dans cette passe.

