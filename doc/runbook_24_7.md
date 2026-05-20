# Runbook 24/7 — Alpha Trade

> Phase C / S18.1. Procédures opérationnelles pour l'astreinte.

## 1. Alerting & escalation

| Sévérité | Source | Action 1ère ligne | Escalade T+ |
|---|---|---|---|
| **P0** Trading bloqué | Slack `#alpha-trade-critical` | Vérifier broker_adapter health → bascule IBKR | 15 min → Lead SRE |
| **P0** Audit chain corrompue | `verify_audit_chain.py` rc != 0 | STOP execution → snapshot DB | 5 min → Head of Eng |
| **P1** Slippage > 50 bps | Reporting parité | Vérifier microstructure → suspendre symbole | 30 min → Quant lead |
| **P1** Reconciliation broker divergence > 1 % | `run_broker_reconciliation.py` | Investigation lots vs broker_statements | 1 h → Risk officer |
| **P2** Calibration drift > 5 % | Workflow `quarterly_calibration.yml` | Notification Slack, recalibration manuelle | 24 h |

## 2. Procédures clés

### `stock_screener` termine en partial run

**Symptôme** : le `run_summary` ou l'IHM affiche un état de persistance du type
`preserved_previous_scores_partial_run`. Cela signifie que le run a calculé une
photo incomplète (`chunk_failures > 0`) et que `stock_scores` **n'a pas été
remplacée** : le snapshot précédent a été conservé volontairement.

**Impact** : pas de purge destructive, mais l'univers visible en base reflète
encore le dernier run complet. Il faut traiter l'incident de collecte / calcul
avant de considérer le screener du jour comme exploitable.

**Détection** :

- dans l'IHM (`Overview`, `Pipeline`, `Screening`), le résumé du `stock_screener`
  doit mentionner un libellé opérateur du type `snapshot préservé (run partiel)` ;
- dans le payload brut, confirmer :
  - `persistence_status=preserved_previous_scores_partial_run`
  - `chunk_failures > 0`
  - `chunk_error_samples` non vide si des erreurs ont été échantillonnées.

**Action 1ère ligne** :

1. Lire le résumé IHM puis ouvrir le payload brut pour récupérer :
   `run_id`, `chunk_failures`, `chunk_failure_ratio`, `chunk_error_samples`.
2. Contrôler les logs du run `stock_screener` avec le `run_id` : chercher
   `Run screener partiel preserve` puis `Chunks screener en echec`.
3. Identifier si l'erreur est :
   - **provider / DB transitoire** (`timeout`, `connection reset`, etc.) → rejouer le screener ;
   - **benchmark / données manquantes** (`SPY` absent, univers vide) → vérifier l'ingestion amont avant replay ;
   - **erreur de code reproductible** → geler le replay et escalader vers l'équipe dev.
4. Avant tout replay, vérifier si les étapes amont du jour sont saines :
   `import_alpaca_bar`, `data_sanitizer_daily`, `update_sector` si concerné.
5. Relancer ensuite le screener seulement après correction du point amont.

**Commandes utiles** :

```powershell
python -m screener.stock_screener --trade-date 2026-04-17
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
```

**Critères de sortie d'incident** :

- `persistence_status=replaced_scores_full_run`
- `chunk_failures == 0`
- `persisted_rows > 0`
- l'IHM n'affiche plus `snapshot préservé (run partiel)` pour le dernier run.

### Positions sans protection broker-side (TP/SL manquants)

**Symptôme** : une position est ouverte (entrée `FILLED`) mais aucun
ordre `take_profit` ni `initial_stop`/`trailing_stop` n'est actif côté
broker. Risque immédiat : pas de stop-loss → perte non bornée.

**Détection** :

```sql
SELECT r.symbol, r.account_id, r.intent_id, r.exec_run_id
FROM execution_order_requests r
LEFT JOIN execution_broker_orders o ON o.intent_id = r.intent_id
WHERE r.intent_role='entry' AND r.side='buy'
  AND COALESCE(o.normalized_status, r.status) IN ('FILLED','PARTIALLY_FILLED')
  AND NOT EXISTS (
    SELECT 1 FROM execution_order_requests c
    WHERE c.parent_request_id = r.intent_id
      AND c.intent_role IN ('take_profit','initial_stop','trailing_stop')
      AND c.status NOT IN ('CANCELLED','REJECTED','EXPIRED')
  );
```

**Cause typique** : entrée soumise hors RTH (profil `overnight_cash_swing`,
presets `paper`/`live`) puis remplie à l'ouverture suivante alors que ni
l'executor (déjà terminé) ni le watcher (non lancé) n'étaient en mesure
d'armer TP/SL.

**Action 1ère ligne** :

1. Lancer un watcher one-shot pour armer immédiatement les protections
   manquantes (filet `_arm_missing_protections`) :
   ```powershell
   python run_execution_protection_watch.py --mode once --account <id>
   ```
2. Vérifier les métriques émises dans le `run_summary` :
   `armed_missing_protections` > 0 attendu, `armed_missing_protections_failed` == 0.
3. Re-jouer la requête SQL ci-dessus → doit retourner 0 ligne.
4. Si le filet échoue (`_failed > 0`) : ouvrir le watcher en mode debug,
   inspecter `execution_events WHERE event_type='CHILDREN_SUBMITTED' AND
   payload_json LIKE '%watcher_safety_net%'`.
5. En dernier recours, armer manuellement TP/SL via l'UI Alpaca puis
   réconcilier : `python -m execution_engine.reconciliation`.

**Prévention** :

- En exploitation overnight : un watcher persistant **doit** tourner
  (NSSM ou Task Scheduler — cf. `doc/watcher.md` §4).
- Surveiller dans Supervision Ops la métrique
  `armed_missing_protections` : > 0 récurrent en intraday = bug à
  investiguer (la Phase 7b de l'executor devrait avoir armé en run).

### Bascule broker Alpaca → IBKR (read-only failover)

```powershell
# Vérifier circuit breaker actif
python -m execution_engine.preflight --account default
# Forcer failover (session PowerShell courante)
$env:ALPHA_TRADE_BROKER_FAILOVER = "ibkr_readonly"
# Rejouer l'exécution en mode simulation pour garder le chemin run canonique sans writes broker
python run_execution.py simulate --account default
```

### Restore from backup (RPO ≤ 5 min)

```powershell
python scripts/restore_from_backup.py `
    --backup-id <latest> `
    --target-db alpha_trade_restore
```

Cf. `doc/disaster_recovery.md` pour RTO ≤ 30 min.

### Vérification audit chain HMAC

```powershell
python scripts/verify_audit_chain.py --since 7d
```

### Hotfix en production

1. Branche `hotfix/<ticket>` depuis `main`.
2. Test local + tests de non-régression Phase A (parity backtest/live).
3. PR avec label `hotfix` → CI verte obligatoire.
4. Merge + tag `v0.1.X`.
5. Déploiement : `make deploy-prod` (idempotent).
6. Vérifier audit chain post-déploiement.

## 3. Maintenance planifiée

| Fréquence | Tâche | Workflow |
|---|---|---|
| Quotidien | Parité backtest/live | `nightly_parity.yml` |
| Quotidien | Sandbox CI complet | `sandbox_nightly.yml` |
| Quotidien | SBOM + scan CVE | `security_scan.yml` |
| Hebdo | Mutation testing | `mutation_weekly.yml` |
| Mensuel | DR drill (restore + parity) | `dr_drill.yml` |
| Mensuel | Rapport broker mensuel | `monthly_report.yml` |
| Trimestriel | Calibration weights | `quarterly_calibration.yml` |

## 4. Contacts

* Lead SRE — voir Vault `alpha_trade/contacts/sre`
* Quant lead — voir Vault `alpha_trade/contacts/quant`
* Risk officer — voir Vault `alpha_trade/contacts/risk`

