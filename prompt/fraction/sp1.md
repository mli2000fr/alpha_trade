# Synthèse Sprint 1 — achats fractionnaires

_Date : 2026-06-09_

## Checklist
- [x] Relecture des modèles risk
- [x] Relecture des modèles exécution
- [x] Relecture de la persistance `db_io`
- [x] Vérification des migrations Alembic
- [x] Vérification des tests DB IO
- [x] Vérification de la persistance `fractionable`
- [x] Sauvegarde de la synthèse dans `prompt/fraction/sp1.md`

---

## 1. Résumé exécutif

Le **Sprint 1** du chantier “achats fractionnaires” est **largement déjà implémenté** dans le code actuel.

La situation réelle observée est la suivante :
- les **modèles risk** sont déjà en `float` ;
- les **modèles d’exécution** critiques sont déjà en `float` ;
- la **lecture DB** des quantités ne retronque pas en `int` ;
- une **migration dédiée** existe déjà pour `target_shares` et `fractionable` ;
- les **tests DB IO** couvrent déjà des colonnes `DOUBLE` et un cas fractionnaire ;
- la **persistance locale** du champ asset `fractionable` est déjà prévue.

En pratique, Sprint 1 n’est donc plus un sprint de fondation “à lancer”, mais un sprint de **clôture / hardening**.

---

## 2. État réel par axe

### 2.1 Modèles risk

Fichier : `risk_management/models.py`

Constat :
- `SizingResult.proposed_shares: float`
- `PortfolioEntry.proposed_shares: float`
- `PortfolioEntry.approved_shares: float`
- `RiskDecisionRow.proposed_shares: float`
- `RiskDecisionRow.approved_shares: float`
- `PortfolioTargetRow.shares: float`

Conclusion :
- le blocage “modèles risk encore entiers” est **déjà levé**.

### 2.2 Modèles exécution

Fichier : `execution_engine/models.py`

Constat :
- `ExecutionTarget.target_shares: float`
- `OrderIntent.qty: float`
- `ExecutionOrderRequest.target_qty: float`
- `BrokerOrder.qty: float`
- `BrokerOrder.filled_qty: float`
- `ExecutionFill.filled_qty: float`
- `ExecutionPosition.net_qty: float`
- `ExecutionPositionLot.opened_qty: float`
- `ExecutionPositionLot.remaining_qty: float`
- `ReconcileDiff.target_qty: float`

Conclusion :
- le noyau exécution ne porte plus l’hypothèse “quantité entière” sur ces objets centraux.

### 2.3 Persistance / lecture DB

Fichier : `execution_engine/db_io.py`

Constat :
- `target_shares=float(r["shares"])`
- `target_shares=float(r["target_shares"])`

Conclusion :
- les lectures de cibles d’exécution sont déjà compatibles avec des quantités fractionnaires.
- aucun `int(...)` bloquant n’a été relevé sur ces chemins précis.

### 2.4 Migration Alembic

Fichier : `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`

Constat :
- migration existante ;
- `execution_targets_snapshot.target_shares` est modifié de `Integer` vers `Float` ;
- `stock_metadata.fractionable` est ajouté.

Conclusion :
- la fondation schéma du Sprint 1 existe déjà.

### 2.5 Métadonnées asset `fractionable`

Fichiers :
- `database/assets.py`
- `service/alpaca/clientAlpaca.py`

Constat :
- `fetch_alpaca_assets()` renvoie les assets Alpaca bruts ;
- `database/assets.py` expose `_has_fractionable_column()` ;
- `insert_assets_to_db()` persiste `fractionable` si la colonne existe.

Conclusion :
- la **persistance locale** du flag `fractionable` est en place ;
- il reste à **brancher cette donnée dans les garde-fous métier live** avant soumission broker.

### 2.6 Tests

Fichier : `tests/test_execution_db_io.py`

Constat :
- `portfolio_targets.shares DOUBLE`
- `execution_targets_snapshot.target_shares DOUBLE`
- `execution_order_requests.target_qty DOUBLE`
- un test de lecture vérifie `target_shares == 100.5`

Conclusion :
- les tests DB IO sont déjà alignés avec un stockage fractionnaire minimal.

---

## 3. Ce qui est déjà terminé

### ✅ Terminé
- passage des modèles risk clés en `float` ;
- passage des modèles exécution clés en `float` ;
- lecture des quantités via `float(...)` dans `db_io` ;
- migration Alembic `0037` ;
- schémas de test DB IO compatibles ;
- cas de test fractionnaire `100.5` ;
- persistance conditionnelle du champ `fractionable`.

### 🟡 Partiellement terminé
- disponibilité runtime de `fractionable` côté flux live :
  - stockage OK,
  - usage métier / validation avant broker à confirmer.

### ❌ Non terminé
- helper transverse de quantité :
  - arrondi max 9 décimales,
  - epsilon float,
  - détection quasi-entier,
  - formatage broker/logs,
  - clamp `>= 0`.

---

## 4. Gaps restants pour fermer Sprint 1

### 4.1 Helper transverse de quantité

À créer dans un module dédié, par exemple :
- `execution_engine/quantity_utils.py`
- ou `common/quantity_utils.py`

Responsabilités minimales :
- normaliser une quantité au format Alpaca (max 9 décimales) ;
- comparer deux quantités avec epsilon ;
- formater proprement une quantité entière vs fractionnaire ;
- empêcher les valeurs négatives invalides aux frontières critiques.

### 4.2 Branchement métier de `fractionable`

À documenter / finaliser :
- où la validation doit s’exécuter avant soumission ;
- comment refuser explicitement un ordre fractional sur asset non fractionable ;
- comment journaliser le rejet métier avant appel broker.

### 4.3 Tests ciblés manquants

À ajouter idéalement avant clôture Sprint 1 :
- arrondi à `9` décimales ;
- cas `0.333333333` ;
- quasi-entier / epsilon ;
- formatage payload broker (`1` vs `1.25`) ;
- rejet local si `fractionable != true` pour un ordre fractionnaire live.

---

## 5. Risques encore ouverts

### Risques faibles / résiduels
- restitution DB en `Float` plutôt qu’en `Numeric(20,9)` : acceptable pour Sprint 1, mais à surveiller si des besoins d’exactitude stricte apparaissent.

### Risques moyens
- flag `fractionable` disponible en base mais pas encore consommé partout où nécessaire.

### Risques hors Sprint 1
- `risk_management/position_sizer.py` force encore des tailles entières via `math.floor(...)` ;
- `risk_management/constraints.py` contient encore des divisions tronquées ;
- `backtesting/simulator.py` reste un blocage majeur pour un vrai backtest fractionnaire ;
- les protections live Alpaca fractionnaires restent le risque produit/broker principal.

---

## 6. Recommandation de pilotage

### Décision recommandée
Considérer Sprint 1 comme **presque clôturé**.

### Dernier lot conseillé pour fermeture Sprint 1
1. créer le helper transverse de quantité ;
2. ajouter les tests unitaires de normalisation / formatage ;
3. confirmer le branchement métier de `fractionable` côté live.

### Conséquence planning
Après ce petit lot de finition, l’effort principal doit basculer sur :
- **Sprint 2** : risk management fractionnaire ;
- **Sprint 3** : backtest fractionnaire ;
- **Sprint 4** : live fractional entry avec garde-fous explicites.

---

## 7. Fichiers preuves

- `risk_management/models.py`
- `execution_engine/models.py`
- `execution_engine/db_io.py`
- `database/assets.py`
- `service/alpaca/clientAlpaca.py`
- `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`
- `tests/test_execution_db_io.py`
- `prompt/fraction/plan.md`

---

## 8. Verdict Sprint 1

### Verdict
**Sprint 1 : 80–90% déjà réalisé dans le code.**

### Ce qu’il reste réellement
- unifier la manipulation des quantités ;
- fermer le branchement `fractionable` côté métier live ;
- compléter les tests de robustesse.

### Formulation courte
Le socle type / DB / persistance du fractionnaire est déjà là ; les prochains vrais blocages sont désormais surtout en **risk**, **backtest** et **garde-fous live**.

