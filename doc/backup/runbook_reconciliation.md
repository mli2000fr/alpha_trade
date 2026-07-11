# Runbook — Réconciliation `MANUAL_REVIEW` / `BLOCKED` (Phase 7.6)

> **Audience** : opérateur on-call.
> **Périmètre** : statuts post-exécution nécessitant intervention humaine
> (`execution_engine` + `corporate_actions`).

---

## 1. Cas couverts

| Statut | Module | Cause typique | Alerte auto ? |
|---|---|---|---|
| `MANUAL_REVIEW` | `execution_engine.executor` | Diff irréconciliable broker ↔ DB (qty / fill price) | ⚠️ Log + IHM |
| `BLOCKED` | `execution_engine` | Equity broker indisponible / kill switch actif | ✅ `KILL_SWITCH_ACTIVATED` |
| `RECON_FAILED` | `corporate_actions.reconciliation` | Idempotency conflict / amount mismatch | ⚠️ Log |
| `CASH_LEDGER_MISALIGNMENT` | `execution_engine.cash_ledger_guard` | Écart equity calculée vs rapportée > 1% | ✅ `CASH_LEDGER_MISALIGNMENT` |

> **Sprint S9** : Les alertes automatiques sont envoyées sur tous les canaux
> configurés (Slack, Telegram, Discord, SMS, Email). Voir `doc/service.md` §10.

---

## 2. Procédure générique

1. **Bloquer le pipeline batch** suivant si non encore lancé :
   ```bash
   python -m execution_engine cancel-all --account <account>
   ```
2. **Identifier le run impacté** :
   ```sql
   SELECT run_id, account_id, status, payload
   FROM execution_runs
   WHERE status IN ('MANUAL_REVIEW','BLOCKED','RECON_FAILED')
   ORDER BY started_at DESC LIMIT 5;
   ```
3. **Auditer les ordres** :
   ```sql
   SELECT * FROM execution_orders WHERE run_id = '<run_id>';
   SELECT * FROM execution_audit_events WHERE run_id = '<run_id>';
   ```
4. **Comparer broker ↔ DB** :
   ```python
   from execution_engine.cli import diff_broker_vs_db
   diff_broker_vs_db(account_id="<account>", run_id="<run_id>")
   ```
5. **Décision** :
   - **Accepter le diff broker** → marquer `RECONCILED_MANUAL` + ajouter
     un `execution_audit_events` JSON `{kind: "manual_override", operator: "<name>"}`.
   - **Rejeter** → cancel order côté broker + investigation root cause.

---

## 3. Cas spécifique corporate_actions `RECON_FAILED`

Voir `doc/corporate_actions.md` §9.2 (audit dédié `corporate_actions_audit_runs`).

```sql
SELECT * FROM corporate_actions_audit_runs ORDER BY computed_at DESC LIMIT 5;
SELECT * FROM corporate_actions_events
WHERE provider_event_id IN (SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.failed_event_id'))
                            FROM corporate_actions_audit_runs WHERE status='FAILED');
```

Cross-check avec Yahoo si dividende :

```bash
python -m corporate_actions sync --cross-check yahoo --since <ex_date>
```

---

## 4. Post-mortem template

```markdown
# Post-mortem — <YYYY-MM-DD> <module>:<incident>

## Résumé (1 paragraphe)
## Timeline (UTC)
- HH:MM — détection
- HH:MM — diagnostic
- HH:MM — mitigation
- HH:MM — résolution
## Impact
- Comptes : ...
- Ordres concernés : ...
- Capital exposé : ...
## Root cause
## Mesures correctives
- [ ] Court terme
- [ ] Moyen terme (à porter dans `prompt/refactor/backlog_long_terme.md` si applicable)
```

---

**Réf.** : audit_global §7.6 ; `doc/execution_engine.md` ; `doc/corporate_actions.md`.

