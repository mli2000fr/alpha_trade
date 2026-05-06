# Disaster Recovery — Alpha Trade

> Sprint **S12.1** — Phase B (Industrialisation pro-grade).
> Référence : `prompt/tod/22_plan_10_10.md` §3 / §S12.1.

## 1. Objectifs RPO / RTO

| Métrique | Cible | Mesuré dans le drill |
|---|---:|---|
| **RPO** (Recovery Point Objective) | < 5 min | Lag binlog vs dernier dump incrémental |
| **RTO** (Recovery Time Objective) | < 30 min | Temps total `restore_from_backup.py` + smoke tests |
| Drill mensuel | obligatoire | Workflow `.github/workflows/dr_drill.yml` |

Tout dépassement est traité comme un incident **P1** (alerting Slack
`#alpha-trade-ops` via `service/alerting.py`).

## 2. Stratégie de sauvegarde

### 2.1 Dumps logiques (nightly)

```bash
mysqldump \
  --single-transaction \
  --routines --triggers --events \
  --hex-blob \
  --default-character-set=utf8mb4 \
  -h "$DB_HOST" -u "$LOGIN_DB" -p"$PASSWORD_DB" \
  alpha_trade \
  | gzip -9 > "/backups/alpha_trade-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
```

Rétention : **30 jours quotidiens**, **12 mois mensuels** (premier dimanche),
**7 ans annuels** (compliance audit).

### 2.2 Binlogs (RPO continu)

`server-id` + `log_bin = ON` côté MySQL ; flush vers stockage froid
toutes les 5 minutes via `mysqlbinlog --read-from-remote-server --raw`.

### 2.3 Stockage

- Production : **bucket S3 versionné** + glacier après 30 j.
- DR site : **bucket cross-region** (réplication asynchrone).

## 3. Procédure de restauration

### 3.1 Restauration full depuis dump

```powershell
$env:DB_HOST = "<dr-host>"
$env:LOGIN_DB = "<user>"
$env:PASSWORD_DB = "<password>"
python scripts/restore_from_backup.py `
  --dump-path "C:\backups\alpha_trade-20260506T010000Z.sql.gz" `
  --target-host "$env:DB_HOST" `
  --target-db alpha_trade
```

### 3.2 Rejeu binlog (point-in-time)

```bash
python scripts/restore_from_backup.py \
  --dump-path /backups/last.sql.gz \
  --binlog-dir /backups/binlogs/ \
  --until-datetime "2026-05-06 14:30:00"
```

### 3.3 Vérifications post-restore

Le script exécute automatiquement :

1. `alembic upgrade head` — convergence du schema vers la HEAD courante.
2. `python -m execution_engine.preflight --account default --skip-network`
   — preflight applicatif (audit S5 §6).
3. `python scripts/verify_audit_chain.py --strict` — vérification du
   chaînage HMAC-SHA256 (Sprint S12.2).
4. Comptage des tables critiques :
   `assets`, `stock_bars_daily`, `stock_scores`, `risk_decisions`,
   `execution_runs`, `corporate_actions`, `audit_chain_events`.

## 4. Drill mensuel

Workflow GitHub Actions `dr_drill.yml` (cron `0 2 1 * *`) :

1. Spin-up MySQL 8 (service container) + seed minimal.
2. Dump → suppression DB → restauration via `restore_from_backup.py`.
3. Vérifications §3.3.
4. Échec → notification Slack severity=`critical`.

Trace archivée dans `artifacts/dr_drill_runs/<date>/report.json`
pendant 12 mois.

## 5. Responsabilités

| Rôle | Responsabilité |
|---|---|
| **SRE on-call** | Déclenche restauration, suit RTO. |
| **DBA** | Valide intégrité post-restore (`CHECKSUM TABLE`). |
| **Quant lead** | Re-vérifie cohérence `risk_decisions` ↔ `execution_runs` du dernier jour. |

## 6. Liens

- [`scripts/restore_from_backup.py`](../scripts/restore_from_backup.py)
- [`.github/workflows/dr_drill.yml`](../.github/workflows/dr_drill.yml)
- [`scripts/verify_audit_chain.py`](../scripts/verify_audit_chain.py)
- [`database/audit_chain.py`](../database/audit_chain.py)

