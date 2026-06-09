# Synthèse Sprint 5 — Live fractional protections : politique produit explicite

_Date : 2026-06-09_

## Checklist
- [x] Choisir une politique produit explicite pour les protections fractionnaires live
- [x] Introduire `fractional_live_mode = entry_only | intraday_only | full_if_supported`
- [x] Conserver la compatibilité avec le flag Sprint 4 `allow_fractional_live_protections`
- [x] Faire dépendre les payloads broker du mode produit
- [x] Bloquer explicitement les chemins fractionnaires non autorisés dans `children_submission`
- [x] Bloquer explicitement les chemins fractionnaires non autorisés dans `protection_watcher`
- [x] Supporter `intraday_only` avec protections `DAY`
- [x] Ajouter et exécuter les tests Sprint 5
- [x] Mettre à jour la documentation

---

## 1. Résumé exécutif

Le **Sprint 5 est implémenté**.

Le projet dispose maintenant d’une **politique produit explicite** pour les protections live sur positions fractionnaires, ce qui supprime les chemins ambigus où une protection broker-side pouvait être tentée sans garantie métier claire.

Le choix retenu est l’**Option C** du plan :
- `entry_only`
- `intraday_only`
- `full_if_supported`

Avec ce Sprint 5 :
- le mode par défaut reste **sûr** (`entry_only`) ;
- `intraday_only` autorise des protections fractionnaires uniquement dans un cadre intraday compatible, avec `time_in_force=day` ;
- `full_if_supported` laisse un opt-in explicite pour les cas où le support broker est jugé suffisant ;
- les modules d’exécution et le watcher refusent explicitement les chemins non autorisés.

---

## 2. Décision produit implémentée

### 2.1 Politique retenue
Fichier : `execution_engine/config.py`

Le Sprint 5 retient la **recommandation Option C** du plan :

```python
fractional_live_mode = "entry_only" | "intraday_only" | "full_if_supported"
```

### 2.2 Sémantique des modes
- **`entry_only`**
  - entrées fractionnaires live/paper autorisées ;
  - protections broker-side fractionnaires refusées explicitement.
- **`intraday_only`**
  - protections fractionnaires autorisées uniquement dans un contexte intraday compatible ;
  - payloads broker de protection forcés en `DAY`.
- **`full_if_supported`**
  - comportement broker-side complet autorisé explicitement ;
  - conserve le modèle historique `GTC` pour les protections fractionnaires opt-in.

### 2.3 Compatibilité Sprint 4 conservée
Le flag Sprint 4 `allow_fractional_live_protections=True` continue de fonctionner via une résolution implicite vers :
- `resolved_fractional_live_mode == "full_if_supported"`

Cela évite de casser le comportement déjà testé au Sprint 4.

---

## 3. Changements réalisés

### 3.1 Centralisation de la politique runtime
Fichier : `execution_engine/config.py`

Ajouté :
- `fractional_live_mode`
- `resolved_fractional_live_mode`
- `can_submit_fractional_protection_orders(...)`
- `resolve_fractional_protection_time_in_force(...)`

But :
- ne plus disperser la logique métier entre flags implicites ;
- rendre la décision produit testable et réutilisable.

### 3.2 Payloads Alpaca dépendants du mode produit
Fichier : `execution_engine/order_intents.py`

Réalisé :
- séparation du calcul de `time_in_force` dans `_resolve_alpaca_time_in_force(...)` ;
- `intent_to_alpaca_payload(intent, config=...)` tient compte du mode ;
- `build_oco_protection_payload(..., config=...)` tient compte du mode.

Résultat :
- protection fractionnaire en `intraday_only` => `time_in_force="day"`
- protection fractionnaire en `entry_only` => rejet explicite si un payload est demandé malgré les garde-fous
- comportement historique entier inchangé

### 3.3 Soumission live des enfants alignée sur la politique
Fichier : `execution_engine/children_submission.py`

Réalisé :
- la décision de soumettre ou non TP / SL / trailing pour un fill fractionnaire passe désormais par `can_submit_fractional_protection_orders(...)` ;
- le motif de refus est journalisé explicitement ;
- le payload d’audit transporte désormais aussi `fractional_live_mode`.

Résultat :
- plus de chemin implicite ou flou ;
- les refus sont métiers et lisibles.

### 3.4 Watcher aligné sur la politique
Fichier : `execution_engine/protection_watcher.py`

Réalisé :
- le watcher refuse explicitement l’armement de protections manquantes si le mode l’interdit ;
- le watcher refuse explicitement la transition `initial_stop -> trailing_stop` si le mode l’interdit ;
- ajout d’une métrique dédiée :
  - `fractional_policy_blocked_items`

Résultat :
- aucun chemin où le watcher “rattrape” accidentellement une protection fractionnaire non autorisée ;
- le mode `intraday_only` est respecté aussi après le run d’exécution.

### 3.5 Application de la config aux soumissions réelles broker
Fichier : `execution_engine/broker_adapter.py`

Réalisé :
- `submit_intent()` passe la config à `intent_to_alpaca_payload()` ;
- `submit_oco_protection()` passe la config à `build_oco_protection_payload()`.

Résultat :
- la politique Sprint 5 s’applique aux **vraies soumissions broker**, pas seulement aux tests/unitaires.

---

## 4. Tests Sprint 5

### 4.1 Tests ajoutés / étendus
#### `tests/test_order_intents.py`
- TIF `DAY` pour protection fractionnaire en `intraday_only`
- rejet explicite d’un payload de protection fractionnaire en `entry_only`
- OCO fractionnaire en `intraday_only` avec `time_in_force="day"`

#### `tests/test_executor.py`
- blocage des protections fractionnaires en `intraday_only` si le profil reste overnight
- autorisation des protections fractionnaires en `intraday_only` sur profil `custom` intraday
- compatibilité conservée avec le mode Sprint 4 / `full_if_supported`

#### `tests/test_protection_watcher.py`
- blocage d’une transition trailing fractionnaire hors fenêtre intraday (`intraday_only` + ancien `trade_date`)
- blocage d’un armement de protections manquantes fractionnaires en `entry_only`

### 4.2 Commandes exécutées

```powershell
python -m pytest -q -o addopts="" tests/test_order_intents.py tests/test_executor.py tests/test_protection_watcher.py
python -m pytest -q -o addopts="" tests/test_execution_engine_executor.py tests/test_broker_snapshot_hardening.py
```

### 4.3 Résultats
- **79 tests passés** sur le périmètre Sprint 5 ciblé
- **23 tests passés** en régression complémentaire
- **102 tests passés** au total sur le scope validé

---

## 5. Fichiers clés Sprint 5

- `execution_engine/config.py`
- `execution_engine/order_intents.py`
- `execution_engine/broker_adapter.py`
- `execution_engine/children_submission.py`
- `execution_engine/protection_watcher.py`
- `tests/test_order_intents.py`
- `tests/test_executor.py`
- `tests/test_protection_watcher.py`
- `prompt/fraction/plan.md`
- `prompt/fraction/sp5.md`

---

## 6. Points désormais couverts

- la politique produit fractional live est **explicite** et centralisée ;
- les protections fractionnaires live ne partent plus “par accident” ;
- `intraday_only` est disponible pour des cas intraday compatibles ;
- `full_if_supported` reste un opt-in explicite ;
- les payloads broker de protection fractionnaire reflètent bien le mode sélectionné ;
- le watcher respecte la même politique que l’exécution live.

---

## 7. Ce qui reste après Sprint 5

Le prochain blocage naturel devient le **Sprint 6 — stabilisation / réconciliation / rollout** :
- revoir toutes les tolérances reconcile/rebalance restantes sur quantités décimales ;
- compléter la non-régression historique ;
- documenter le rollout progressif paper puis live limité ;
- finaliser l’observabilité de production.

