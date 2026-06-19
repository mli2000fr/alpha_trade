# Synthèse Sprint 4 — Live Alpaca MVP : fractional entry fiable

_Date : 2026-06-09_

## Checklist
- [x] Brancher explicitement le runtime live/paper sur le flag fractionnaire
- [x] Bloquer les entrées fractionnaires si le flag est désactivé
- [x] Bloquer côté app les assets non fractionables avant broker
- [x] Rejeter explicitement les shorts fractionnaires
- [x] Conserver un format `qty` Alpaca propre et stable
- [x] Borner le MVP aux entrées fractionnaires, protections fractionnaires désactivées par défaut
- [x] Préserver les quantités décimales dans la réconciliation live
- [x] Ajouter et exécuter les tests ciblés Sprint 4
- [x] Mettre à jour la documentation

---

## 1. Résumé exécutif

Le **Sprint 4 est implémenté**.

Le pipeline live/paper sait maintenant accepter une **entrée fractionnaire** de bout en bout, tout en gardant des garde-fous explicites avant appel broker :
- l’entrée fractionnaire n’est active que si `ExecutionConfig.allow_fractional_shares=True` ;
- un asset non fractionable est bloqué localement avec une raison métier lisible ;
- un short fractionnaire est rejeté explicitement ;
- le payload Alpaca continue d’utiliser un `qty` compact via `format_share_quantity()` ;
- les protections fractionnaires broker-side restent **hors MVP** par défaut et sont donc différées proprement.

---

## 2. Changements réalisés

### 2.1 Branchement runtime explicite
Fichier : `execution_engine/config.py`

Réalisé :
- ajout du sous-flag `allow_fractional_live_protections=False` ;
- ajout des propriétés runtime :
  - `fractional_live_entries_enabled`
  - `fractional_live_protections_enabled`

But : rendre explicite la frontière produit entre :
- **Sprint 4** = entrées fractionnaires live/paper ;
- **Sprint 5** = protections fractionnaires broker-side, si support confirmé.

### 2.2 Garde-fous avant broker
Fichier : `execution_engine/order_intents.py`

Réalisé dans `filter_targets_by_live_regime_guards()` :
- blocage d’une cible fractionnaire si `allow_fractional_shares=False` ;
- rejet explicite d’un target `sell` / `short` fractionnaire ;
- maintien du contrôle `fractionable=true` avant broker ;
- journalisation exploitable via les raisons :
  - `fractional_shares_disabled`
  - `fractional_short_not_supported`
  - `asset_not_fractionable`

### 2.3 Boundary MVP : entry-only pour le fractionnaire live
Fichier : `execution_engine/children_submission.py`

Réalisé :
- si un fill parent est fractionnaire et que `allow_fractional_live_protections=False`, aucun TP / STOP fractionnaire n’est soumis au broker ;
- l’application journalise clairement le mode `fractional_live_entry_only_mode` ;
- cela évite d’embarquer trop tôt le sujet le plus risqué du rollout : les protections fractionnaires server-side.

### 2.4 Réconciliation / rebalance
Fichiers :
- `execution_engine/executor.py`
- `execution_engine/children_submission.py`

Réalisé :
- suppression d’une troncature `int(...)` sur `ReconcileDiff.target_qty` ;
- rebalances préparés à des `qty` décimaux ;
- logs d’action enrichis avec des quantités formatées proprement.

### 2.5 Vérifications complémentaires
Fichiers vérifiés sans changement nécessaire :
- `execution_engine/db_io.py`
- `database/assets.py`

Constat :
- la lecture des snapshots et `target_shares` est déjà en `float` ;
- la récupération du flag `fractionable` est déjà disponible ;
- la donnée asset est déjà persistée et consommable par le runtime live.

---

## 3. Tests Sprint 4

### Tests ajoutés / étendus
- `tests/test_order_intents.py`
  - blocage si flag fractionnaire live désactivé ;
  - rejet des shorts fractionnaires ;
  - validation du format `qty=0.125` côté payload Alpaca.
- `tests/test_executor.py`
  - blocage d’une cible fractionnaire avant soumission si le flag est désactivé ;
  - mode entry-only : enfants fractionnaires différés par défaut ;
  - opt-in explicite des protections fractionnaires si le sous-flag est activé.

### Revalidation ciblée
- `tests/test_execution_engine_executor.py`

### Commande exécutée

```powershell
python -m pytest -q -o addopts="" tests/test_order_intents.py tests/test_executor.py tests/test_execution_engine_executor.py
```

### Résultat
- **67 tests passés**

---

## 4. Fichiers clés Sprint 4

- `execution_engine/config.py`
- `execution_engine/order_intents.py`
- `execution_engine/children_submission.py`
- `execution_engine/executor.py`
- `tests/test_order_intents.py`
- `tests/test_executor.py`
- `prompt/fraction/plan.md`
- `prompt/fraction/sp4.md`

---

## 5. Points désormais couverts

- une entrée `buy qty=0.5` peut partir en live/paper **si le flag est activé** et si l’asset est fractionable ;
- un ordre fractionnaire sur asset non fractionable est bloqué **avant broker** ;
- un short fractionnaire est rejeté explicitement côté application ;
- les payloads `qty` restent propres (`100` si entier, `0.125` si décimal) ;
- la frontière MVP est claire : **entry fractionnaire oui, protections fractionnaires broker-side non par défaut** ;
- la réconciliation live n’écrase plus silencieusement certaines quantités décimales.

---

## 6. Ce qui reste après Sprint 4

Le prochain blocage majeur devient le **Sprint 5 — protections fractionnaires live** :
- confirmer le support broker réel pour TP / STOP / trailing sur positions fractionnaires ;
- choisir la politique produit (`entry_only`, `intraday_only`, `full_if_supported`) ;
- adapter watcher / children / TIF / types d’ordres selon la capacité broker réellement observée.

