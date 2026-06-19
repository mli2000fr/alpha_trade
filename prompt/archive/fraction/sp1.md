# Synthèse Sprint 1 — achats fractionnaires

_Date : 2026-06-09_

## Checklist
- [x] Finaliser le helper transverse de quantités
- [x] Brancher la validation runtime `fractionable` avant soumission live
- [x] Ajouter les tests ciblés Sprint 1
- [x] Revalider les fondations déjà livrées
- [x] Mettre à jour la documentation

---

## 1. Verdict

Le **Sprint 1 est clôturé**.

Le socle partagé du fractionnaire est maintenant complet sur le périmètre prévu :
- modèles centraux en `float` ;
- persistance / migration DB compatibles ;
- helper transverse de quantité disponible ;
- métadonnée asset `fractionable` persistée **et consommée** côté garde-fou live ;
- tests ciblés de robustesse ajoutés.

---

## 2. Travaux effectivement terminés

### 2.1 Helper transverse
Fichier : `common/quantity_utils.py`

Ajouts/usage :
- `normalize_share_quantity()`
- `format_share_quantity()`
- `is_effectively_integer_quantity()`
- `QUANTITY_DECIMALS = 9`
- `QUANTITY_EPSILON`

Ce helper est désormais consommé dans :
- `execution_engine/order_intents.py`
- `common/utils.py`

### 2.2 Fondations type / DB déjà en place et confirmées
Fichiers confirmés :
- `risk_management/models.py`
- `execution_engine/models.py`
- `execution_engine/db_io.py`
- `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`

Points confirmés :
- les quantités risk/exécution critiques sont en `float` ;
- les lectures DB ne tronquent plus les quantités ;
- `execution_targets_snapshot.target_shares` est en `Float` ;
- `stock_metadata.fractionable` existe au schéma.

### 2.3 Branchement runtime `fractionable`
Fichiers impactés :
- `database/assets.py`
- `execution_engine/db_io.py`
- `execution_engine/executor.py`
- `execution_engine/order_intents.py`

Ce qui est maintenant vrai :
- les assets Alpaca persistés conservent `fractionable` ;
- `ExecutionRepository.load_fractionable_asset_map()` charge ces capacités ;
- l’executor injecte ces métadonnées dans les garde-fous live ;
- un target **fractionnaire** est bloqué avant soumission si l’asset n’est pas explicitement fractionnable.

---

## 3. Tests ajoutés / adaptés

### Nouveaux tests
- `tests/test_quantity_utils.py`
  - arrondi/troncature à 9 décimales ;
  - clamp du bruit numérique ;
  - détection quasi-entier ;
  - formatage broker.

### Tests enrichis
- `tests/test_order_intents.py`
  - blocage d’un target fractionnaire sur asset non fractionable ;
  - acceptation si l’asset est fractionable.
- `tests/test_execution_db_io.py`
  - chargement du mapping `fractionable` depuis `stock_metadata`.

### Revalidation Sprint 1
Commande exécutée :

```powershell
python -m pytest -q -o addopts="" "F:\projets\tests\test_assets.py" "F:\projets\tests\test_execution_db_io.py" "F:\projets\tests\test_order_intents.py"
```

Résultat :
- **64 passed**

---

## 4. Fichiers clés Sprint 1

- `common/quantity_utils.py`
- `common/utils.py`
- `execution_engine/order_intents.py`
- `execution_engine/db_io.py`
- `execution_engine/executor.py`
- `database/assets.py`
- `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`
- `tests/test_quantity_utils.py`
- `tests/test_order_intents.py`
- `tests/test_execution_db_io.py`
- `tests/test_assets.py`

---

## 5. Risques ouverts après Sprint 1

Ce qui **reste hors Sprint 1** :
- le sizing/contraintes risk fractionnaires end-to-end ;
- le backtest fractionnaire natif ;
- les protections live fractionnaires overnight côté Alpaca.

En pratique, le prochain blocage majeur n’est plus le socle partagé mais le **pipeline risk** puis le **simulateur backtest**.

---

## 6. Formulation courte

Sprint 1 a livré le **socle commun fiable** : représentation float, schéma DB, helper de quantités, métadonnée `fractionable`, et garde-fou live d’entrée avant broker.

