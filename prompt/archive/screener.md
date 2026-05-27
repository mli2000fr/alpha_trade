# Prompt — audit source-first et plan d’amélioration de `screener/`

## Objectif

Tu dois reprendre la partie `screener/` en te basant **d’abord sur les codes sources**. Les docs peuvent aider au contexte, mais **la vérité est dans le code**.

Ta mission comporte 2 volets :

1. **confirmer l’audit ci-dessous sur le code courant** ;
2. **implémenter un plan de correction et de durcissement** sans casser les contrats existants.

---

## Sources de vérité à lire en priorité

### Cœur du screener
- `screener/stock_screener.py`
- `screener/pipeline.py`
- `screener/db_io.py`
- `screener/models.py`
- `screener/__init__.py`

### Dépendances directes / contrats aval
- `core/filter_profiles.py`
- `selector/filters.py`
- `selector/ranking.py`
- `backtesting/backfill_scores_history.py`
- `backtesting/screener_diagnostics/_impl.py`
- `ihm/services/pipeline_runner.py`
- `ihm/pages/_execution_center/__init__.py`

### Tests existants à utiliser comme filet de sécurité
- `tests/test_screener_pipeline.py`
- `tests/test_screener_db_io.py`
- `tests/test_stock_screener.py`
- `tests/test_screener_run_summaries.py`
- `tests/test_ihm_pipeline_runner.py`
- `tests/test_screener_diagnostics.py`
- `tests/test_data_source_consistency_runtime.py`

---

## État actuel observé

### Forces confirmées
- Le découpage `db_io.py` / `pipeline.py` / `stock_screener.py` est globalement propre.
- Le chargement **2 passes** est une bonne optimisation : fenêtre récente pour filtrer, puis agrégats historiques sur survivants seulement.
- Les calculs métier principaux sont lisibles :
  - historique minimal,
  - prix minimum,
  - liquidité,
  - force relative vs benchmark,
  - score de range historique,
  - score total pondéré.
- Le module est déjà **bien couvert en tests unitaires ciblés**.
- Vérification locale faite :
  - `python -m pytest tests/test_screener_pipeline.py tests/test_screener_db_io.py tests/test_stock_screener.py tests/test_screener_run_summaries.py -q --no-cov`
  - résultat observé : **tests ciblés verts**.

---

## Anomalies / écarts prouvés par lecture du code

## 1) Risque critique : un run vide efface `stock_scores`

### Preuves code
- Dans `screener/stock_screener.py`, `run_screener_with_report()` appelle toujours `upsert_scores_snapshot(...)`, même si `final_scores` est vide.
- Dans `screener/db_io.py`, `upsert_scores_snapshot()` fait :
  - `DELETE FROM stock_scores` si `scores_df.empty`.

### Impact
- Un incident amont (benchmark absent, erreur DB partielle, univers vide inattendu, chunk failures massifs) peut **vider la table live `stock_scores`**.
- Le log `critical` existe, mais il arrive **après** que le choix de persistance destructive soit déjà acté.

### Correctif attendu
- Interdire l’effacement silencieux par défaut.
- Introduire une stratégie explicite, par exemple :
  - `preserve_previous_scores_on_empty_run=True` par défaut, ou
  - exception si run vide inattendu, ou
  - flag explicite `allow_empty_snapshot_replace`.
- Documenter la politique choisie.
- Ajouter tests de non-régression.

---

## 2) Risque critique : purge destructive même si des chunks ont échoué

### Preuves code
- `screener/stock_screener.py` tolère les erreurs chunk : `_process_chunk_two_passes()` renvoie un `DataFrame` vide + `ScreenerChunkMetrics(failed=True, ...)`.
- `run_screener_with_report()` agrège quand même les résultats partiels et appelle `upsert_scores_snapshot(...)`.
- `screener/db_io.py` appelle ensuite `_purge_missing_scores(engine, symbols)` qui supprime tout symbole absent du snapshot final.

### Impact
- Si certains chunks échouent, les symboles non calculés peuvent être **supprimés de `stock_scores`** alors qu’il s’agit d’un run partiel.
- On obtient une photo silencieusement tronquée, alors que le système connaît déjà `chunk_failures`.

### Correctif attendu
- Empêcher `_purge_missing_scores()` si `chunk_failures > 0`.
- Décider d’une politique claire pour les runs partiels :
  - soit abort global avant persistance,
  - soit upsert partiel **sans purge**,
  - soit persistance dans une table de staging puis promotion atomique seulement si run complet.
- Exposer cet état dans le résumé de run et dans les logs opérateur.
- Ajouter tests dédiés.

---

## 3) Bug fonctionnel : `--trade-date` n’est pas utilisé comme borne PIT du screener

### Preuves code
- Dans `screener/stock_screener.py`, l’argument CLI `--trade-date` est parsé en `snapshot_date_override`.
- Mais l’appel à `run_screener_with_report(...)` ne passe **pas** `as_of_date=snapshot_date_override`.
- Le même `trade_date` est bien propagé par l’IHM dans `ihm/services/pipeline_runner.py`.

### Impact
- En CLI / pipeline IHM, `--trade-date` sert à **archiver** dans `stock_scores_history`, mais **ne borne pas les données de marché lues**.
- Le snapshot journalier peut donc être enregistré à une date logique donnée tout en utilisant des données plus récentes.
- C’est un risque PIT / cohérence temporelle.

### Correctif attendu
- Passer `as_of_date=snapshot_date_override` quand `--trade-date` est renseigné.
- Si besoin, distinguer explicitement :
  - `--trade-date` = date logique métier,
  - `--as-of-date` = borne de lecture des données,
  - mais garder une valeur par défaut cohérente quand une seule date est fournie.
- Ajouter tests CLI / orchestration.

---

## 4) Incohérence de stratégie : le screener live n’utilise pas le profil partagé strict alors qu’il existe

### Preuves code
- `screener/models.py` expose `ScreenerConfig.from_filter_profile(...)` et `ScreenerConfig.strict_swing_cash(...)`.
- `core/filter_profiles.py` contient `STRICT_SWING_CASH_FILTERS`.
- Pourtant `screener/stock_screener.py::main()` construit encore un `ScreenerConfig(...)` “manuel” avec défauts live :
  - `min_close_price=5.0`
  - `liquidity_threshold_usd=10_000_000.0`
- En parallèle, le selector live IHM est explicitement strict (`STRICT_SWING_CASH_FILTERS`) via ses commandes et tests.

### Impact
- Il existe de nouveau **deux vérités opérationnelles** :
  - screener amont plus permissif,
  - selector aval strict.
- Cela augmente le coût CPU/DB, élargit inutilement l’univers amont, et rend les diagnostics plus ambigus.

### Correctif attendu
- Décider explicitement entre deux modes :
  1. screener live aligné par défaut sur `STRICT_SWING_CASH_FILTERS` ;
  2. screener volontairement plus permissif, mais alors ce différentiel doit être assumé, documenté, testé et nommé.
- Si le différentiel est conservé, créer un profil screener dédié explicite au lieu d’un implicite “défauts en dur”.

---

## 5) Incohérence de baseline dans les outils de backfill / diagnostic

### Preuves code
- `backtesting/backfill_scores_history.py` : par défaut `self.screener_config = screener_config or ScreenerConfig()`.
- `backtesting/screener_diagnostics/_impl.py` : par défaut `self.base_screener_config = base_screener_config or ScreenerConfig()`.
- En revanche le scanner aval utilise `AlphaScannerConfig.strict_swing_cash()` par défaut.

### Impact
- Les outils PIT / diagnostics peuvent partir d’une base screener par défaut différente du mode strict partagé.
- Cela complique la lecture des résultats et la comparaison live vs backtest.

### Correctif attendu
- Revoir les defaults pour expliciter la baseline souhaitée.
- Harmoniser live / backfill / diagnostics autour d’une stratégie unique ou de profils explicitement nommés.

---

## 6) Gap de robustesse : les erreurs détaillées de chunks ne remontent pas assez haut

### Preuves code
- `ScreenerChunkMetrics` contient `error_message`.
- `summary` agrège `chunk_failures` mais pas de liste d’erreurs, ni d’échantillon, ni de symboles concernés.
- `_append_completed_results()` fusionne les métriques mais perd l’information détaillée.

### Impact
- En exploitation, on sait qu’il y a eu des échecs, mais pas facilement **pourquoi**, ni sur quels lots.
- Diagnostic plus lent si incident partiel intermittent.

### Correctif attendu
- Remonter au moins :
  - un compteur,
  - un petit échantillon d’erreurs (`first_n_chunk_errors`),
  - éventuellement la taille et/ou la plage de symboles du chunk fautif.
- Sans exploser la taille du `run_summary`.

---

## 7) Dette périphérique : script de bench branché sur une API obsolète

### Preuves code
- `scripts/bench_full_pipeline.py` importe `from screener.runner import run_screener`.
- Dans l’arborescence courante, le point d’entrée réel est `screener.stock_screener`.

### Impact
- Le benchmark n’est pas aligné sur l’implémentation réelle du screener.
- Les mesures de perf peuvent devenir trompeuses ou tomber en fallback.

### Correctif attendu
- Réaligner le bench sur l’API réelle.
- Éviter les fallbacks silencieux si le but est une mesure fiable.

---

## Points à surveiller mais à revalider avant correction

Ne pas les traiter comme bugs certains sans relecture/mesure complémentaire :

- gestion des exceptions `future.result()` hors erreurs métier capturées dans le worker ;
- coût mémoire de `symbol_chunks = list(iter_symbol_chunks(...))` ;
- opportunité d’une persistance en table de staging + swap atomique ;
- pertinence métier de renommer `relative_strength_index` (ce n’est pas le RSI de Wilder).

---

## Plan d’amélioration priorisé

## P0 — sécurité et cohérence temporelle
1. Corriger la sémantique de `--trade-date` / `as_of_date`.
2. Bloquer toute purge destructive sur run vide inattendu.
3. Bloquer la purge des symboles manquants si `chunk_failures > 0`.
4. Définir une politique officielle pour les runs partiels.
5. Ajouter tests sur ces cas.

## P1 — alignement des profils et cohérence live/backtest
1. Décider si le screener live doit adopter `STRICT_SWING_CASH_FILTERS`.
2. Harmoniser les defaults dans :
   - `screener.stock_screener`
   - `backtesting.backfill_scores_history`
   - `backtesting.screener_diagnostics`
3. Si plusieurs profils doivent coexister, les rendre explicites et nommés.
4. Ajouter tests d’alignement de config.

## P2 — observabilité et exploitabilité
1. Remonter un échantillon des erreurs de chunks.
2. Logguer plus clairement le mode de persistance choisi : complet, partiel sans purge, abort, etc.
3. Étendre le `run_summary` sans le rendre trop verbeux.

## P3 — dette périphérique / outillage
1. Réparer `scripts/bench_full_pipeline.py`.
2. Vérifier que les docs IHM / README ne promettent pas une sémantique différente de celle du code.

---

## Changements attendus

### Code
Modifier au minimum si nécessaire :
- `screener/stock_screener.py`
- `screener/db_io.py`
- `screener/models.py` si besoin de config/politique
- `backtesting/backfill_scores_history.py`
- `backtesting/screener_diagnostics/_impl.py`
- `scripts/bench_full_pipeline.py`
- éventuels points d’intégration IHM si contrat CLI ajusté

### Tests
Ajouter / adapter des tests couvrant au minimum :
- `--trade-date` borne bien les lectures via `as_of_date` ;
- un run vide n’efface pas silencieusement `stock_scores` ;
- un run partiel avec `chunk_failures > 0` ne purge pas les symboles absents ;
- l’alignement de profil par défaut choisi ;
- le bench appelle le bon point d’entrée.

---

## Contraintes d’implémentation

- Préserver les API publiques autant que possible.
- Préférer de petits changements ciblés plutôt qu’un gros refactor.
- Si un comportement destructif change, rendre la nouvelle politique **explicite** dans le code et les logs.
- Ne pas inventer des comportements métier non justifiés par le code actuel.
- Toute nouvelle option CLI doit être testée.

---

## Définition de terminé

Le travail est terminé seulement si :

- les anomalies P0 sont corrigées ;
- les tests existants pertinents restent verts ;
- de nouveaux tests couvrent les cas de sécurité ajoutés ;
- la stratégie de configuration par défaut est cohérente et explicitée ;
- le bench n’utilise plus un import obsolète ;
- un court résumé final liste :
  - anomalies corrigées,
  - décisions de design prises,
  - impacts potentiels sur l’exploitation.

---

## Commandes utiles

```powershell
python -m pytest tests/test_screener_pipeline.py tests/test_screener_db_io.py tests/test_stock_screener.py tests/test_screener_run_summaries.py -q --no-cov
python -m pytest tests/test_ihm_pipeline_runner.py -q --no-cov
python -m pytest tests/test_screener_diagnostics.py -q --no-cov
```

