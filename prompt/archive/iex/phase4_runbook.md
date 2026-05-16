# Phase 4 EODHD - Runbook bascule contrôlée

> **Statut** : prêt à l'exécution dès souscription EODHD active.
> **Réf. plan** : `prompt/iex/plan_eodhd.md` §6 Phase 4.
> **Pré-requis** : Phases 1-3 livrées (60+10+8 tests verts), `EODHD_API_TOKEN` défini, plan EODHD souscrit (idéalement All-In-One pour le bulk).

---

## 1. Préparation (T-1 jour)

### 1.1 Vérifier le smoke test post-souscription
```powershell
$env:EODHD_API_TOKEN = "<votre_token>"
python scripts/eodhd_phase1_smoke.py --bulk-days 3
# Critères phase1_checklist.md §3 doivent tous passer (bulk 200, splits 200, etc.).
```

### 1.2 Backup base de données
```powershell
mysqldump -u root -p alpha_trade stock_bars stock_bars_daily > backups/pre_phase4_eodhd_$(Get-Date -Format yyyyMMdd).sql
```

### 1.3 Vérifier que le pipeline ALPACA est sain (baseline)
```powershell
python -m dataIntegrityEngine.import_alpaca_bar
# Note les compteurs : success_ratio, no_data_symbols, stale_symbols.
```

---

## 2. Bascule en mode shadow (Phase 3 récap)

`config.yaml` reste sur `bars_provider: alpaca`. On lance EODHD **en parallèle** sans écrire :

```powershell
# Dry-run shadow : compare sans toucher la DB
python -m dataIntegrityEngine.import_eodhd_bar
# Lit le run_summary émis (clés eodhd.* + cross_check_stooq.*).
```

Critères de qualité :
- `eodhd.bulk_size` >= 7 000
- `matched_in_bulk / targeted_symbols` >= 0.95
- `eodhd.calls_failed == 0`
- `cross_check_stooq.failed == false`

---

## 3. Activation écriture EODHD (mode shadow + write)

À ce stade `bars_provider` est **toujours alpaca** : Alpaca alimente la prod, EODHD écrit en parallèle (cohabitation `data_source` distincte).

```powershell
# Lance EODHD en write : crée des lignes data_source='eodhd_eod'
python -m dataIntegrityEngine.import_eodhd_bar --write
```

Vérification SQL :
```sql
SELECT data_source, COUNT(*) AS n, MIN(`date`) AS min_d, MAX(`date`) AS max_d
FROM stock_bars_daily
WHERE `date` >= CURDATE() - INTERVAL 7 DAY
GROUP BY data_source;
-- Attendu : alpaca_iex et eodhd_eod cohabitent sur les mêmes dates.
```

Répéter pendant **5 jours** (ou backfill J-30 via `--target-date`).

---

## 4. Critère go/no-go (plan §6 Phase 4)

```powershell
python scripts/eodhd_phase4_volume_audit.py --lookback-days 60
# Sortie : artifacts/eodhd_cache/phase4_volume_audit_<TS>.json
# Exit code 0 -> GO, 1 -> NO-GO
```

### Décision GO si :
- `decision.median_ratio_global` ∈ [10, 50] (ratio EODHD/Alpaca-IEX)
- `decision.no_large_cap_lost == true` (aucune large cap > 10 G$ rejetée à tort)

### Décision NO-GO si :
- ratio < 10 -> EODHD sous-rapporte vs SIP attendu (vérifier que la requête vise bien `data_source='eodhd_eod'`)
- ratio > 50 -> aberrations de volume (dividende exceptionnel ? split non géré ?)
- large_cap_lost : revoir `min_avg_dollar_volume_20d` ou `service/eodhd/symbols_exceptions.json`

---

## 5. Bascule provider (cutover)

Quand le critère go/no-go est validé :

```yaml
# config.yaml
market_data:
  bars_provider: eodhd          # <-- bascule
  fallback_on_failure: true
eodhd:
  enabled: true                 # <-- active
  # ... reste inchangé
```

Effets immédiats au prochain run :
- `import_alpaca_bar.main()` -> **no-op** (mode `noop` dans run_summary)
- `import_eodhd_bar.main()`  -> **actif** en mode write
- Les lectures aval (selector, screener, backtesting) consomment `stock_bars_daily` sans changement de code (data_source mixte tolérée).

Test fumée production :
```powershell
python -m dataIntegrityEngine.import_alpaca_bar  # doit logguer "no-op | bars_provider=eodhd"
python -m dataIntegrityEngine.import_eodhd_bar   # doit logguer mode=write
```

---

## 6. Surveillance J+1 / J+7

### Métriques à surveiller (dashboard IHM)
- `eodhd.calls_used` / 100 000 (cible < 1%)
- `eodhd.circuit_open == false`
- `cross_check_stooq.anomalies_count` (alerte si > 50)
- `selector.candidates_count` doit rester stable (±10% vs baseline Alpaca)

### Comparaison run_summary selector avant/après
```powershell
python -m selector.alpha_scanner > selector_after_eodhd.json
diff selector_before.json selector_after_eodhd.json
```

Le nombre de symboles candidats doit **augmenter** (volume EODHD plus représentatif débloque des large caps mid-trading sur IEX).

---

## 7. Plan de rollback

Si problème détecté en J+1 / J+7 :

```yaml
# config.yaml — rollback immédiat
market_data:
  bars_provider: alpaca
eodhd:
  enabled: false
```

Effet : Alpaca redevient actif au prochain run, EODHD redevient no-op. Les lignes `data_source='eodhd_eod'` restent en base (pas de purge automatique).

Purge optionnelle :
```sql
DELETE FROM stock_bars_daily
WHERE data_source = 'eodhd_eod'
  AND `date` >= '<date_bascule>';
```

---

## 8. Decision log

| Étape | Date | Décision | Auteur | Run ID |
|---|---|---|---|---|
| Smoke post-souscription | YYYY-MM-DD | GO / NO-GO | | phase1_smoke_... |
| Shadow dry-run | | | | |
| Write shadow (J+5) | | | | |
| Audit go/no-go | | GO / NO-GO | | phase4_volume_audit_... |
| Cutover prod | | | | |
| Validation J+1 | | | | |
| Validation J+7 | | | | |

---

## 9. Tests à passer avant chaque jalon

```powershell
# Batterie EODHD (Phases 2-4)
python -m pytest tests/test_clientEodhd.py tests/test_eodhd_symbols.py tests/test_eodhd_split_only.py tests/test_import_eodhd_bar.py tests/test_eodhd_provider_switch.py tests/test_stooq_cross_check_pipeline.py tests/test_eodhd_phase4_volume_audit.py -q -o addopts=""

# Non-régression sensible
python -m pytest tests/test_clientAlpaca.py tests/test_phase1_run_summary.py tests/test_stooq_cross_check.py tests/test_selector_alpha_scanner.py tests/test_selector_run_summaries.py tests/test_backtesting.py tests/test_corporate_actions_cross_check_yahoo.py tests/test_sanitizer_db_ops.py -q -o addopts=""
```

Aucun rouge ne doit subsister avant cutover.

