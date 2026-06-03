# Audit live pipeline — Priorité 3

## Contexte
Cette note synthétise l’implémentation **réelle dans le code source** de l’équivalent Priorité 3 côté live pipeline :
- coûts d’exécution réalistes / observabilité TCA,
- cohérence corporate actions,
- réconciliation et observabilité du pipeline d’exécution,
- adaptation IHM.

> Source de vérité : **le code**. La documentation `/doc` n’est pas supposée être parfaitement à jour.

---

## 1) Coûts d’exécution réalistes / observabilité TCA

### Implémenté
Le live pipeline calcule et persiste des métriques TCA à partir des fills observés :
- `slippage_bps`
- `implementation_shortfall`
- agrégats de run TCA

### Fichiers
- `execution_engine/tca.py`
  - `compute_slippage_bps()`
  - `compute_implementation_shortfall()`
  - `build_tca_summary()`
  - `build_tca_aggregate_frame()`
- `execution_engine/models.py`
  - `ExecutionFill` contient `slippage_bps` et `implementation_shortfall`
  - `TcaSummary` formalise les agrégats
  - `EventType.TCA_SUMMARY` existe pour le journal d’événements
- `execution_engine/executor.py`
  - calcule le résumé TCA en fin de run si `enable_tca` est actif
  - émet l’événement `TCA_SUMMARY`
  - propage maintenant aussi dans les métriques de run :
    - `tca_total_filled`
    - `tca_total_notional`
    - `tca_avg_slippage_bps`
    - `tca_max_slippage_bps`
    - `tca_total_implementation_shortfall`
    - `tca_slippage_alerts`
- `execution_engine/audit.py`
  - `build_execution_run_summary()` persiste désormais ces métriques TCA dans le résumé métier du run

---

## 2) Corporate actions / cohérence données

### Implémenté
Le module corporate actions live formalise la convention de données et applique les événements de manière auditée et idempotente.

### Convention projet
- les prix de marché sont considérés **split-adjusted**,
- les dividendes sont gérés hors prix,
- les flux cash passent via `portfolio_cash_ledger`.

### Fichiers
- `corporate_actions/engine.py`
  - `sync()` : ingestion provider → DB
  - `apply()` : application transactionnelle et idempotente
  - revalidation de l’événement au moment de l’apply
  - un événement invalide déjà persisté est marqué `failed`
- `corporate_actions/reconciliation.py`
  - réconciliation post-corporate-actions entre état interne et broker

---

## 3) Réconciliation / observabilité live pipeline

### Implémenté
Le live pipeline possède une couche explicite de réconciliation d’exécution.

### Fichiers
- `execution_engine/reconciliation.py`
  - `reconcile_execution_state()`
  - `reconcile_targets_vs_broker()`
- `execution_engine/models.py`
  - `ExecutionReconciliationResult` expose :
    - `target_qty`
    - `internal_position_qty`
    - `broker_position_qty`
    - `position_delta`
    - `action`
    - `reconciliation_status`
    - `reason_code`

### Bénéfice
Le pipeline live peut désormais :
- détecter les écarts broker vs projection interne,
- classifier ces écarts,
- préparer une action automatique sûre ou une revue manuelle.

---

## 4) Adaptation IHM live

### Implémenté
L’IHM exécution expose les éléments utiles au suivi live Priority 3.

### Fichiers
- `ihm/pages/execution.py`
  - panneau **TCA agrégé**
  - panneau **Cohérence pipeline trades**
  - affichage des fills, lots et résultats de réconciliation
  - alertes de réconciliation vieillissante

### Ce que l’opérateur voit
- agrégats TCA par run / bucket / mois
- cohérence entre fills, lots reconstruits et réconciliation
- état actionnable des divergences

---

## 5) Validation / tests

Tests ciblés exécutés après mise à jour :

- `tests/test_backtesting_refactor.py`
- `tests/test_executor.py`
- `tests/test_pages_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`

Résultat : **116 tests passés**.

Commande utilisée :

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_backtesting_refactor.py tests/test_executor.py tests/test_pages_backtesting.py tests/test_ihm_backtesting_runner.py -q -o addopts=
```

> Le test ajouté côté live couvre la propagation des métriques TCA dans le résumé de run.

---

## 6) Verdict

### Priorité 3 live pipeline — état
- **Coûts d’exécution réalistes / TCA** : oui
- **Corporate actions cohérentes et auditables** : oui
- **Réconciliation / observabilité pipeline** : oui
- **IHM adaptée** : oui
- **Synthèse P3 live présente dans `/prompt`** : oui

### Note
Il reste des warnings de typage statique sur certains gros fichiers, mais pas de blocage fonctionnel identifié sur les livrables Priority 3 live couverts ici.

