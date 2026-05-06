# 06 — Audit OHLCV / provider primaire / `data_adjustment` / corporate actions

## 1. Question centrale

> Quel est aujourd'hui le **provider OHLCV daily primaire réel** d'Alpha
> Trade, et toutes les conventions associées (sanitation, corporate actions,
> backtesting, scoring) sont-elles cohérentes avec ce choix ?

## 2. Constats factuels (preuves `fichier:ligne`)

| # | Fait | Preuve |
|---|---|---|
| 1 | `bars_provider` configuré à `eodhd` | `config.yaml:51` |
| 2 | Le code respecte ce flag | `dataIntegrityEngine/import_eodhd_bar.py:151-154` (`resolve_bars_provider`) |
| 3 | `import_alpaca_bar.py` se transforme en no-op si `bars_provider != 'alpaca'` | `dataIntegrityEngine/import_alpaca_bar.py:572` (`_resolve_target_bars_provider` default `'alpaca'`) |
| 4 | EODHD adapter écrit `data_adjustment='split'` | `service/eodhd/adapters.py:262, 292` |
| 5 | Alpaca importer écrit `data_adjustment='split'` | `dataIntegrityEngine/import_alpaca_bar.py:36` |
| 6 | Sanitizer écrit par défaut `data_adjustment='split'` | `database/sanitizer_db_ops.py:24, 191` |
| 7 | Convention canonique projet | `README.md:9-16` |
| 8 | Performance totale = MTM + cumul ledger dividendes | `README.md:15-16` |
| 9 | Contrainte SQL `chk_bars_adj` / `chk_daily_adj` | `README.md:11-13` (à vérifier sur le DDL réel `database/sql/`) |
| 10 | Factory provider CA selon `bars_provider` | `corporate_actions/provider.py:399-405` |
| 11 | Cross-check Stooq activé en Phase 3 EODHD | `dataIntegrityEngine/import_eodhd_bar.py:19-20` (commentaire), `cross_check_stooq.py` |

## 3. Réponse à la question centrale

**Provider primaire actuel : EODHD bulk EOD.**

- Le `config.yaml` l'impose, le code respecte ce choix, la factory CA suit.
- La convention `data_adjustment='split'` est cohérente entre Alpaca, EODHD et
  sanitizer.

## 4. Contradictions à corriger

### 4.1 Documentation primaire — **P0 / P1**

- `doc/dataIntegrityEngine.md:3-22` : bandeau IEX présenté comme universel.
  **Doit** mentionner que ce bandeau ne s'applique qu'au mode rétrocompat
  `bars_provider=alpaca`.
- `doc/data_lineage_matrix.md:27-31` : `Alpaca IEX` désigné producteur de
  `stock_bars_daily` ; EODHD étiqueté « Phase 6 ». **Doit** marquer EODHD
  comme producteur primaire.
- `README.md:142` : commande `import_alpaca_bar` instruite — devient un no-op
  silencieux.

### 4.2 Configuration interne contradictoire — **P0**

- `config.yaml:51` `bars_provider: eodhd` ⚡ `config.yaml:55` `eodhd.enabled:
  false`. La seconde clé n'est jamais lue. Soit la supprimer, soit la
  consommer.

### 4.3 Docstring `corporate_actions/engine.py:34-39` — **P0**

- Affirme `« adjustment="all" »` alors que la réalité est `'split'`. Ce
  module gère justement le ledger dividendes — la docstring est
  intrinsèquement incohérente avec son propre code (insertions dans
  `portfolio_cash_ledger`).

### 4.4 Backtesting — **P1**

- README documente la formule canonique
  `MTM(stock_bars_daily.close) + cumulative(portfolio_cash_ledger)`. À ce
  stade de l'audit, **aucun test ne prouve** que `backtesting/analytics.py`
  applique cette formule (cf. A-006). À vérifier en lisant
  `backtesting/analytics.py` et `backtesting/report.py`.

## 5. Cohérence inter-modules sur la convention OHLCV

| Module | Comportement attendu | Statut |
|---|---|---|
| `dataIntegrityEngine.import_*` | Écrire `data_adjustment='split'`, `data_source='alpaca'` ou `'eodhd'` | ✅ |
| `screener` (lecture `stock_bars_daily`) | Lire sans biais provider, ou logguer la composition `data_source` | ⚠️ A-017 |
| `selector` (lecture barres) | Idem + filtre spread cohérent avec provider quotes | ⚠️ A-017 |
| `risk_management` (lecture barres pour ATR) | Idem | ⚠️ A-017 |
| `execution_engine` (TCA, slippage) | Idem | ⚠️ A-017 |
| `corporate_actions` (sync, apply) | Convention split + ledger dividendes | ✅ comportement / ❌ docstring (A-001) |
| `backtesting` (analytics) | Inclure `portfolio_cash_ledger` | ❓ A-006 à valider |
| `IHM` `Settings` | Permettre la bascule `bars_provider` | ✅ `ihm/pages/settings.py:87` |

## 6. Recommandations consolidées

1. **Sprint S1 (P0)** : corriger les 3 anomalies P0 (A-001, A-002, A-003)
   et synchroniser docs `dataIntegrityEngine.md` + `data_lineage_matrix.md` +
   `corporate_actions.md`.
2. **Sprint S2 (P1)** : ajouter tests de cohérence (A-003, A-004, A-005,
   A-008) ; ajouter télémétrie `data_source` à la lecture (A-017).
3. **Sprint S3 (P1)** : valider et tester la convention dans le
   backtesting (A-006).
4. **Sprint S6 (P2)** : implémenter `scripts/generate_data_lineage.py` pour
   tarir la dette doc structurelle (A-019).

## 7. Convention canonique retenue (à publier dans `doc/`)

> **Convention OHLCV Alpha Trade (canonique au 2026-05-06)**
>
> - Provider primaire : **EODHD bulk EOD** (`market_data.bars_provider=eodhd`).
> - Provider rétrocompat : **Alpaca IEX** (sélectionnable via IHM ou
>   `config.yaml`).
> - Quotes live, métadonnées, exécution : **toujours Alpaca**.
> - `data_adjustment` : **`'split'`** (split-only) — contrainte SQL
>   `chk_bars_adj` / `chk_daily_adj`.
> - `data_source` : `'eodhd'` ou `'alpaca_iex'` selon ingestion.
> - Dividendes : comptabilisés via `corporate_actions.processors` →
>   `portfolio_cash_ledger`.
> - Performance totale = `MTM(positions, stock_bars_daily.close) +
>   cumulative(portfolio_cash_ledger)`.
> - Cross-check : Stooq (best-effort), Yahoo (corporate actions).

