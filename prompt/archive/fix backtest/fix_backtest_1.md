# Rapport correctifs backtest/live — anomalie exits same-day et stops replay

Date: 2026-06-07

## 1) Constat initial

### 1.1 Backtest replay
- Paramètres observés: `--account-type cash --pdt-rule off --swing-only`.
- Anomalie constatée: ~72% des trades sortaient le jour d'entrée, ce qui est incohérent avec `swing_only`.
- Anomalie additionnelle: sur les artifacts phase4/phase5, `replay_initial_stop_price` était quasi constant par symbole (indice fort d'un bug de mapping replay, pas d'un comportement marché normal).

### 1.2 Pipeline live
- Le moteur live diffère déjà les enfants au fill quand `swing_only=True` (via `should_defer_children`), mais des chemins watcher/post-sync pouvaient encore armer des protections le jour du trade.
- Le mapping des targets était partiellement fait par symbole dans l'executor (risque de collision si cas multi-entrée ambigus).

## 2) Analyses techniques réalisées

### 2.1 Vérifications artifacts existants
- Fichier vérifié: `artifacts/ihm_backtesting_runs/run/20260606_090900_f8bee4a4/artifacts/phase5_watcher_replay_signals.csv`
  - Exemples: `CCXI`, `CROX`, `SHOP` avec `fill_price` variable mais `replay_initial_stop_price` unique.
- Vérification amont:
  - `phase2_execution_targets.csv` avait des `stop_price_initial` variables (donc le problème apparaît ensuite).
  - `phase4_protection_replay_signals.csv` avait déjà les stops figés par symbole.

Conclusion: la corruption se produit en phase4 replay (mapping).

### 2.2 Cause racine phase4
- Dans `backtesting/execution_lifecycle_replay.py`, la logique utilisait un mapping `target` par symbole.
- Ensuite la sélection de l'`entry_intent` dépendait du `risk_run_id` du target (déjà figé au dernier target du symbole).
- Effet: réutilisation du mauvais parent/protections sur plusieurs trades d'un même symbole.

### 2.3 Cause racine exits same-day en phase7
- `backtesting/exit_lifecycle_replay.py` commençait le scan des triggers à `entry_idx` (jour d'entrée inclus), sans respecter `swing_only`.
- Donc sorties possibles le jour d'entrée malgré le mode swing.

## 3) Correctifs implémentés

### 3.1 Backtest phase4: mapping trade-level (fix majeur)
**Fichier:** `backtesting/execution_lifecycle_replay.py`
- Remplacement du mapping `target` par symbole par un mapping clé `(symbol, risk_run_id, trade_date)`.
- Priorité à `entry_intent_id` depuis les signaux pour retrouver le parent exact.
- Fallback défensif si clé stricte absente.

Impact attendu:
- `replay_initial_stop_price`, TP et trailing redeviennent cohérents trade par trade.
- Plus de "stop figé par symbole" dû au bug de replay.

### 3.2 Backtest phase7: respect strict `swing_only`
**Fichier:** `backtesting/exit_lifecycle_replay.py`
- Nouveau paramètre `swing_only: bool = False`.
- Si `swing_only=True`, le scan des sorties démarre à `entry_idx + 1`.
- Ajout d'un garde-fou: invalide un `initial_stop_price >= fill_price` (long-only incohérent).
- Ajout diagnostic `swing_only_applied`.

**Propagation CLI:** `backtesting/cli/_impl.py`
- Passage explicite de `args.swing_only` à `build_phase7_exit_lifecycle_replay(...)`.

Impact attendu:
- Plus de sortie le jour d'entrée en replay quand `--swing-only` est actif.

### 3.3 Export trades/pnl (cohérence report)
**Fichier:** `backtesting/report.py`
- Calcul systématique de `entry_cost`, `proceeds`, `pnl`, `return_pct` pour les lignes pipeline closes.
- Évite les trous `NaN` sur l'export quand il n'y a pas de match legacy.

### 3.4 Live executor: réduction risque de collision de target
**Fichier:** `execution_engine/executor.py`
- Ajout d'un mapping `target_by_intent_id` construit lors du build des intents.
- Utilisation prioritaire de ce mapping pour `_submit_children` (normal + post-sync), fallback symbole conservé.

Impact attendu:
- Target associé au bon intent, même en cas de scénarios ambigus.

### 3.5 Live watcher: blocage same-day en `swing_only`
**Fichier:** `execution_engine/protection_watcher.py`
- `_arm_missing_protections`: si `swing_only` et `trade_date == today`, armement différé + event `CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT`.
- `_process_item`: si `swing_only` et trade date du jour, transition stop->trailing non exécutée ce jour.

**Pré-requis data:** `execution_engine/db_io.py`
- `load_unprotected_filled_parents()` enrichi avec `trade_date` et `parent_created_at`.

Impact attendu:
- Réduction du risque d'exit same-day côté live via les chemins watcher/safety-net.

## 4) Tests et validation

### 4.1 Tests ajoutés
**Fichier:** `tests/test_phase2_bridges.py`
- `test_build_phase4_protection_replay_keeps_trade_specific_stop_levels_for_same_symbol`
  - Vérifie que 2 entrées du même symbole gardent des stops différents en phase4.
- `test_build_phase7_exit_lifecycle_replay_respects_swing_only_no_same_day_exit`
  - Vérifie qu'aucune sortie n'est prise le jour d'entrée avec `swing_only=True`.

### 4.2 Exécution tests ciblés
Commande lancée:
- `python -m pytest -q tests/test_phase2_bridges.py -k "phase4_protection_replay or phase7_exit_lifecycle_replay"`

Résultat:
- Tests ciblés: OK (`......`)
- Le run pytest global échoue sur la policy de couverture (`fail-under=70`) car exécution partielle ciblée (pas un échec fonctionnel des correctifs).

## 5) Réponse à la question utilisateur

### "72% des trades sortent le jour d'entrée, est-ce une anomalie ?"
Oui, dans ce contexte `--swing-only` c'est une anomalie replay.

Correctif appliqué:
- Phase7 respecte maintenant `swing_only` (pas d'exit sur la session d'entrée).

### "Vérifier si même anomalie sur pipeline live"
- Analyse live effectuée:
  - Le flux principal différait déjà les enfants en swing-only.
  - Des chemins watcher pouvaient encore armer/transitionner same-day.
- Correctif appliqué sur watcher live pour différer ces actions en `swing_only` le jour du trade.

## 6) Fichiers modifiés
- `backtesting/execution_lifecycle_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `backtesting/cli/_impl.py`
- `backtesting/report.py`
- `execution_engine/executor.py`
- `execution_engine/db_io.py`
- `execution_engine/protection_watcher.py`
- `tests/test_phase2_bridges.py`

---

## 7) Recommandation de validation finale (opérationnelle)

1. Relancer un backtest replay avec `--swing-only` et comparer:
   - `% exits same-day` attendu ≈ 0% (ou très proche si cas edge de données manquantes).
2. Vérifier sur artifacts phase4:
   - `replay_initial_stop_price` doit varier par trade (et non rester figé par symbole).
3. Sur live/paper:
   - Contrôler événements `CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT` dans les runs du jour en mode swing-only.

