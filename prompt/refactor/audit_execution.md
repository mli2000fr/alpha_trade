# Audit — `execution_engine`

> Périmètre : `execution_engine/` (`executor.py`, `broker_adapter.py`, `cli.py`,
> `oco_manager.py`, `order_intents.py`, `config.py`, `db_io.py`, `models.py`,
> `audit.py`, `protection_watcher.py`, `broker_state_sync.py`).
> Inclut les points d'entrée racine `run_execution.py` et
> `run_execution_protection_watch.py`.
> Sources : `doc/execution_engine.md`, `doc/watcher.md`, code listé,
> tests `tests/test_execution_engine_*`, `tests/test_run_execution.py`,
> `tests/test_broker_adapter.py`, `tests/test_trading_client.py`.

---

## 1. Résumé exécutif

`execution_engine/` est le module **le plus critique opérationnellement** : il
transforme `portfolio_targets` en ordres broker Alpaca, gère les protections
broker-side (TP / stop / trailing), persiste l'audit canonique
(`execution_targets_snapshot`, `execution_order_requests`, `execution_broker_orders`,
`execution_broker_fills`, `execution_positions`, `execution_position_lots`,
`execution_reconciliation_results`, `broker_positions_snapshots`,
`broker_account_snapshots`), calcule la TCA, et alerte sur corporate actions pending.

État global : **module mature, post-cutover canonique**. Architecture canonique
target_snapshot → request → broker_order → fill → position/lot, multi-comptes,
modes simulate/paper/live, gestion `cash` vs `margin`, contraintes PDT,
`swing_only`, `swing_only` overnight, watcher post-exécution séparé. Tests
nombreux. Documentation très détaillée.

Principaux risques :

1. **Le menu interactif `run_execution.py` est un point sensible** (~534 lignes)
   avec beaucoup de logique de présentation + presets `simulate/paper/live` codés en
   dur. Un typo dans un preset live peut être catastrophique.
2. **Live trading sans seconde validation cryptographique** : la confirmation se fait
   via input texte `oui` → un script qui automatise par accident peut fournir cette
   chaîne.
3. **Equity broker fallback à 100 000 $ en cas d'erreur** (cf. `run_execution.py:344`)
   → si `broker.get_account_equity()` échoue silencieusement en live, on continue avec
   un capital fictif → sizing complètement faux.
4. **`ProductionExecutor` orchestre 6+ étapes** (préflight, snapshot, intents, soumission,
   reconciliation, TCA) → fichier probablement gros, complexité élevée. Tests OK mais
   maintenabilité à surveiller.
5. **Réconciliation produit `MANUAL_REVIEW` ou `BLOCKED`** mais le runbook n'est pas
   documenté dans `doc/execution_engine.md` — que doit faire l'opérateur ?
6. **Watcher post-exécution séparé** : conception saine (responsabilité claire),
   mais double mode `once`/`service` + Task Scheduler + NSSM + IHM = surface
   d'exploitation complexe pour un opérateur débutant.
7. **Pas de "kill switch" centralisé** : un script externe ne peut pas annuler tous
   les ordres pending d'un coup en cas d'incident (devrait passer par `cancel_all_orders`
   à étendre).
8. **`ExecutionConfig` immuable mais sérialisé `**preset`** : pas de validation forte
   au runtime des presets eux-mêmes (`max_slippage_bps=20` en live OK, mais un dev
   peut typer `max_slippage_bps="20"` sans erreur).

Priorités immédiates :
- Rendre `equity` fallback **fatal** en mode live (`raise RuntimeError`).
- Ajouter une seconde confirmation live (token / heure de session).
- Documenter le runbook de réconciliation `MANUAL_REVIEW` / `BLOCKED`.
- Ajouter un kill switch global.

---

## 2. Constat détaillé

### 2.1 `run_execution.py` (point d'entrée opérateur)

| Item | Détail |
|---|---|
| Constat | Menu interactif coloré ANSI, presets simulate/paper/live, parsing CLI argparse extensif. `print_env_status()`, `abort_missing_env()`. |
| Force | UX opérateur soignée. Confirmation live `oui` requise. Lecture comptes via `AccountRegistry`. |
| Risque critique | `equity = 100_000.0` en fallback si `broker.get_account_equity()` lève (lignes ~341-346). En mode live, **silence + comportement faux**. |
| Risque 2 | Confirmation live = input texte → contournable par stdin redirect. |
| Risque 3 | Presets lus en module-level dict, mutables (bouts modifiés en CLI). |
| Recommandation | (a) En mode live, exit immédiat si `get_account_equity()` lève ; (b) seconde confirmation : par défaut, demander `account_id` + 4 derniers chiffres d'un token vérifié ; (c) `freeze` les presets via `MappingProxyType` ou dataclass immuable. |

### 2.2 `executor.py` — `ProductionExecutor.execute_run()`

| Item | Détail |
|---|---|
| Constat | 7 étapes documentées : exec_run_id → load targets → execution_runs row → circuit breaker → market hours → constraints snapshot → CA pending alert. Puis intents → idempotency → capital check → submit → broker observation → fills → positions → lots → reconciliation → TCA. |
| Force | Architecture canonique. Idempotence via `idempotency_key`. |
| Risque | **Maintenabilité** : `execute_run()` certainement long. Difficile à tester end-to-end. |
| Risque 2 | **Fiabilité** : la transition entre "ordre soumis" et "fill observé" passe par polling. Si le watcher n'est pas lancé, certains états transitoires peuvent persister. |
| Recommandation | (a) Découper en méthodes privées composables ; (b) introduire un `ExecutionPhase` enum + transitions explicites (state machine). |

### 2.3 `broker_adapter.py`

| Constat | Couche d'adaptation entre `OrderIntent` et `AlpacaTradingClient`. Gère margin/cash/dry-run buying power. |
| Risque | **Fiabilité** : la simulation de buying power en `dry_run` peut diverger du calcul broker réel (multiplicateurs, marge intra-day différentes). |
| Recommandation | Test paramétrique "dry_run vs paper réel" pour vérifier l'équivalence sur cas usuels. |

### 2.4 `oco_manager.py`

| Constat | Gestion logique OCO : TP + stop initial broker-side, fallback trailing si stop initial KO. |
| Risque | OCO côté Alpaca = bracket order ; si l'API broker change, l'oco_manager doit suivre. |
| Recommandation | Test contractuel avec un mock Alpaca qui imite la vraie API bracket. |

### 2.5 `order_intents.py`

| Constat | Construction des ordres d'entrée et de rebalance. |
| Recommandation | Test de génération d'`idempotency_key` cohérente cross-run (même cible → même key, même run_id → resume idempotent). |

### 2.6 `protection_watcher.py` + `run_execution_protection_watch.py`

| Item | Détail |
|---|---|
| Constat | Watcher post-exécution. Modes `once` / `service`. Surveille les protections broker-side, peut promouvoir un stop initial vers trailing dynamique. Documenté de façon exhaustive (`doc/watcher.md` 383 lignes). |
| Force | Bonne séparation conceptuelle : `Execution` arme, `Watcher` supervise. Pédagogique côté IHM (bloc 12.bis). |
| Risque | **Fiabilité** : si le watcher tombe (crash, network), les protections existantes restent (broker-side) → pas catastrophique, mais le trailing dynamique ne s'active pas. |
| Risque 2 | **Sécurité opérationnelle** : 4 modes de lancement (CLI once, IHM, Task Scheduler, NSSM) → risque de double watcher concurrent → race conditions possible sur les annulations / promotions de stop. |
| Risque 3 | Pas de leader election : aucune garantie qu'un seul watcher tourne par compte. |
| Recommandation | (a) Lock distribué (table SQL `execution_locks` déjà présente — à utiliser pour le watcher aussi) ; (b) heartbeat persistant + alarm IHM si > N min sans heartbeat ; (c) refus explicite si un autre watcher actif détecté. |

### 2.7 `reconciliation.py` + `tca.py`

| Constat | Comparaison snapshot / requests / broker / positions / protections. Statuts `SAFE_AUTO`, `MANUAL_REVIEW`, `BLOCKED`. TCA calcule slippage et IS. |
| Risque | **Sécurité opérationnelle** : `MANUAL_REVIEW` n'est pas documenté (que doit faire l'opérateur ? quels SQL inspecter ?). `BLOCKED` non plus. |
| Recommandation | Runbook explicite dans `doc/execution_engine.md` : tableau "statut → cause typique → action opérateur". |

### 2.8 `db_io.py`

| Constat | Repository des 8+ tables d'exécution. |
| Risque | Probablement long, plusieurs centaines de lignes. À refactoriser en sous-classes par domaine (orders / fills / positions / reconciliation). |

### 2.9 `audit.py` — `build_execution_run_summary`

| Constat | Compose un résumé business standardisé pour `run_business_summaries`. |
| Force | Bonne télémétrie. |

---

## 3. Risques prioritaires

### Critique
- `equity` fallback `100_000$` en mode live silencieux → potentiel sizing **massivement
  faux**.
- Pas de leader election watcher → race possible sur les annulations.
- Pas de runbook documenté pour `MANUAL_REVIEW` / `BLOCKED`.

### Élevé
- Confirmation live `oui` contournable.
- Presets mutables.
- `execute_run()` monolithique → maintenabilité.
- Pas de kill switch global.

### Modéré
- Dry-run buying power peut diverger de paper réel.
- Pas de test contractuel `oco_manager` vs Alpaca v2 réelle.
- `db_io.py` probablement gros.

### Faible
- Documentation watcher dense (positif globalement, mais long pour onboarding).

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Côté exécution, Alpaca **broker** reste le canal officiel : pas de biais IEX sur
l'exécution réelle (l'ordre est routé NBBO).

**Mais** :
- `execution_engine.tca` compare le `decision_price` (probablement issu de
  `stock_quote_snapshots` → IEX) au `fill_price` consolidé broker. **TCA biaisé**
  systématiquement.
- En `dry_run` / `simulate`, la simulation des fills consomme aussi du IEX (probable) →
  les rapports `simulate` ne reflètent pas un fill broker réaliste.

**Recommandation** :
- documenter explicitement la limite TCA (`decision_price = IEX`, `fill_price =
  consolidated`) et la rendre lisible dans le résumé TCA ;
- en simulate, chercher un meilleur proxy fill (ex: `(open + close) / 2` du jour
  d'exécution) ou ouvrir l'option `--simulate-fill-strategy open|midpoint|close`.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct côté exécution (les ordres sont en USD, pas en multiples de prix
ajustés).

**Mais** : si une CA tombe entre `target_snapshot` et `fill`, la quantité cible peut
ne plus correspondre à la position réelle. Le module gère bien ça via l'alerte
"CA pending" en préflight + la chaîne `corporate_actions apply` en aval. **OK**.

---

## 6. Quick wins

1. **`equity` fallback fatal en mode live** : `raise RuntimeError` au lieu de
   `equity = 100_000`.
2. **Confirmation live renforcée** : exiger en plus `account_id` saisi (matching).
3. **Freeze `PRESETS`** via `MappingProxyType`.
4. **Runbook réconciliation** dans `doc/execution_engine.md`.
5. **Kill switch CLI** : `python -m execution_engine cancel-all --account live1`
   (route vers `client.list_orders(status='open')` + cancel chaque).
6. **Lock watcher** via `execution_locks` (déjà table existante).
7. **Heartbeat watcher persistant** + alarm IHM.
8. **Documenter dry-run vs paper** divergences possibles.

## 7. Recommandations structurelles

1. **Découper `execute_run()`** en sous-méthodes testables (`_preflight`,
   `_build_intents`, `_submit`, `_observe`, `_reconcile`, `_tca`).
2. **State machine explicite** `ExecutionPhase` avec transitions documentées.
3. **`db_io.py` en repositories** par domaine.
4. **Test contractuel `oco_manager`** vs API Alpaca v2 (tests d'intégration paper).
5. **Métriques IHM "santé exécution"** : taux de fill, slippage médian, `MANUAL_REVIEW`
   count par jour.
6. **`AccountRegistry` + secret store** : sortir les credentials live des env vars
   classiques vers DPAPI / vault (déjà partiellement fait pour le watcher).
7. **Mode "shadow" cross-run** : en parallèle d'un run live, lancer un simulate avec
   les mêmes targets pour mesurer la dérive simulate vs live.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5, 8.

### Moyen terme
- Quick wins 6, 7.
- Découpage `execute_run()` + state machine.
- Métriques IHM.
- Test contractuel oco vs Alpaca paper.

### Long terme
- Repositories par domaine.
- Vault secrets live.
- Mode shadow cross-run.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Très bons. **Manque** :
  - test "equity broker indisponible" en live → exit immédiat.
  - test "deux watchers concurrents" → un seul gagne le lock.
  - test contractuel `oco_manager` vs Alpaca paper réelle (en CI manuelle).
  - test `MANUAL_REVIEW` → assertions sur les colonnes attendues.

### Monitoring
- Audit DB exhaustif. **Manque** :
  - dashboard IHM "santé exécution" (compteurs récents, slippage médian, taux de fill).
  - alarm "MANUAL_REVIEW count > N par jour".
  - alarm "watcher heartbeat > X min".

### Documentation
- Très bonne. **Manque** :
  - runbook `MANUAL_REVIEW` / `BLOCKED`.
  - section "que se passe-t-il si Alpaca est down 30 min en cours de run".
  - section "kill switch d'urgence".

