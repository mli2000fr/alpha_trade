# Corporate Actions — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `corporate_actions/` et les commandes utiles pour :

- synchroniser les dividendes et splits depuis Alpaca,
- appliquer ces événements sur les positions internes du portefeuille,
- alimenter les tables d'audit et de cash ledger,
- éviter des écarts entre positions broker et comptabilité interne.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `corporate_actions/__init__.py` | Package Python |
| `corporate_actions/__main__.py` | Point d'entrée `python -m corporate_actions` |
| `corporate_actions/cli.py` | CLI `sync`, `apply`, `status`, `run` |
| `corporate_actions/engine.py` | Orchestrateur principal `CorporateActionEngine` |
| `corporate_actions/provider.py` | Providers `AlpacaCorporateActionProvider` et `EodhdCorporateActionProvider` + factory `build_corporate_action_provider()` |
| `corporate_actions/db_io.py` | Repository SQL du module |
| `corporate_actions/processors.py` | Traitements dividendes / splits |
| `corporate_actions/reconciliation.py` | Réconciliation post-application |
| `corporate_actions/models.py` | Modèles métiers corporate actions |
| `corporate_actions/corporate_action_run.py` | Lanceur dédié historique |

---

## 2. Prérequis

### 2.1 Pour la phase `sync`

#### Obligatoires

- `corporate_actions_events`
- `stock_metadata`
- credentials Alpaca valides

#### Recommandés

- `broker_positions_snapshots`
- accès positions live broker
- accès ordres pending broker

### 2.2 Pour la phase `apply`

#### Obligatoires

- `corporate_actions_events`
- `corporate_actions_applications`
- `portfolio_cash_ledger`
- `broker_positions_snapshots`

#### Important

Le module **n'ajuste pas** `stock_bars` ni `stock_bars_daily`.

Les prix de marché étant déjà ingérés via Alpaca avec `adjustment="split"`, le module corporate actions gère uniquement :

- la comptabilité portefeuille,
- les quantités,
- le cost basis,
- le cash issu des dividendes ou fractions.

### 2.3 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
```

---

## 3. Commandes utiles

### Synchronisation quotidienne recommandée

```powershell
python -m corporate_actions sync --portfolio-only
```

### Synchronisation ciblée sur un compte multi-comptes

```powershell
python -m corporate_actions sync --portfolio-only --account live1
```

### Backfill explicite sur tout l'univers

```powershell
python -m corporate_actions sync --all-symbols --start 2026-01-01 --end 2026-04-21
```

### Synchronisation ciblée sur quelques symboles

```powershell
python -m corporate_actions sync --symbols AAPL MSFT NVDA
```

### Ignorer les symboles déjà historisés

```powershell
python -m corporate_actions sync --symbols AAPL MSFT NVDA --skip-existing
```

### Application des événements pending

```powershell
python -m corporate_actions apply
python -m corporate_actions apply --account live1
```

### Statut synthétique

```powershell
python -m corporate_actions status
```

### Enchaînement sync puis apply

```powershell
python -m corporate_actions run --portfolio-only
```

---

## 4. Ce que fait le module

### 4.1 Résolution du périmètre de sync

Le CLI peut résoudre les symboles à synchroniser de plusieurs façons :

1. liste explicite `--symbols` ;
2. portefeuille courant `--portfolio-only` ;
3. univers large `--all-symbols` ;
4. fallback via `stock_metadata` ou snapshots broker selon le contexte.

En mode `--portfolio-only`, la résolution privilégie :

- les positions live Alpaca,
- les ordres BUY pending,
- puis le dernier snapshot DB si nécessaire.

### 4.2 Ingestion provider

`AlpacaCorporateActionProvider` :

- appelle `v1/corporate-actions`,
- gère pagination et retry,
- parse cash dividends, splits et reverse splits,
- normalise les ratios de split.

### 4.3 Persistance des événements

`CorporateActionEngine.sync()` :

1. valide les événements ;
2. tente l'insert dans `corporate_actions_events` ;
3. distingue `inserted`, `duplicates`, `invalid`.

### 4.4 Application sur positions

`CorporateActionEngine.apply()` :

1. charge les événements pending ;
2. charge les positions ;
3. applique `process_dividend()` ou `process_split()` ;
4. écrit `corporate_actions_applications` ;
5. écrit `portfolio_cash_ledger` si nécessaire ;
6. marque les événements en `applied`, `skipped` ou `failed`.

### 4.5 Idempotence

L'idempotence repose sur `idempotency_key`.

Un événement déjà appliqué n'est pas retraité.

---

## 5. Pourquoi une commande peut ne rien faire

### 5.1 `sync --portfolio-only` ne ramène aucun symbole

Causes probables :

1. aucune position live broker ;
2. aucun ordre BUY pending ;
3. aucun snapshot broker encore disponible ;
4. `run_execution` n'a jamais été exécuté.

### 5.2 `apply` n'a aucun effet

Causes probables :

1. aucun événement `pending` ;
2. aucune position détenue sur le symbole concerné ;
3. événement déjà appliqué ;
4. type d'événement non supporté.

### 5.3 Peu de dividendes visibles dans le ledger

Causes probables :

1. absence de position sur la date ex-date ;
2. événements historisés mais non encore `apply` ;
3. périmètre de sync trop restreint.

---

## 6. Vérifications utiles

### Résumé global

```powershell
python -m corporate_actions status
```

### Vérifier les derniers événements

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, ca_type, ex_date, status FROM corporate_actions_events ORDER BY ex_date DESC, id DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les dernières applications

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, ca_type, position_qty_before, position_qty_after, cash_impact, account_id FROM corporate_actions_applications ORDER BY applied_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier le cash ledger

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, entry_type, amount, currency, account_id FROM portfolio_cash_ledger ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés corporate actions

```powershell
python -m pytest tests/test_corporate_actions.py tests/test_corporate_actions_cli.py tests/test_corporate_action_run.py tests/test_provider.py tests/test_processors.py tests/test_reconciliation.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. exécuter l'exécution du jour ;
2. lancer `sync --portfolio-only` ;
3. lancer `apply` ;
4. vérifier ensuite `portfolio_cash_ledger` et les applications écrites.

### Séquence recommandée

```powershell
python run_execution.py paper --account live1
python -m corporate_actions sync --portfolio-only --account live1
python -m corporate_actions apply --account live1
```

---

## 9. Phase 5.3 — Idempotence, audit, cross-check

> Réf. `prompt/refactor/plan_phase5.md` § 5.3, `prompt/refactor/audit_corporate_actions.md`.

### 9.1 Construction de l'`idempotency_key`

Chaque `CorporateActionEvent` produit deux clés déterministes (SHA-256 tronqué
à 32 caractères) :

| Méthode | Formule | Usage |
|---|---|---|
| `event.idempotency_key` (legacy) | `sha256(provider \| symbol \| ca_type \| ex_date \| amount_or_split)[:32]` | Rétrocompat lecture des events ingérés avant Phase 5.3.a. |
| `event.compute_idempotency_key(account_id)` | `sha256(account_id_or_GLOBAL \| provider \| symbol \| ca_type \| ex_date \| amount_or_split)[:32]` | Clé à utiliser à l'écriture (sync) et à la vérification d'application (apply). Évite les doubles-crédits cross-comptes. |

Si `account_id is None`, `compute_idempotency_key` renvoie la clé legacy
(pratique pour les outils qui n'ont pas de notion de compte).

`is_event_applied(scoped_key, legacy_key=...)` du repository essaie d'abord la
clé scopée puis tombe sur la legacy : un event ingéré pré-migration ne peut
donc pas être rejoué par erreur.

**Schéma DB** : la colonne `corporate_actions_events.account_idempotency_key`
(migration `0019_corporate_actions_account_idempotency`) porte la nouvelle clé.
Index `UNIQUE` (NULL multiples autorisés sous MySQL/MariaDB).

### 9.2 Audit & monitoring (`corporate_actions_audit_runs`)

Migration `0018_corporate_actions_audit_runs` — table créée pour tracer chaque
exécution de `python -m corporate_actions {sync,apply,run}`. Chaque CLI appelle
`CorporateActionRepository.persist_audit_run(...)` automatiquement, en
best-effort (échec → log debug, jamais bloquant).

| Colonne | Description |
|---|---|
| `run_id` (PK) | `build_summary_run_id("ca-…")` |
| `run_kind` | `sync` \| `apply` \| `reconcile` \| `run` |
| `account_id` | NULL si run global |
| `started_at`, `finished_at`, `duration_seconds` | Timing |
| `fetched / inserted / duplicates / invalid` | Stats sync |
| `applied / skipped / failed` | Stats apply |
| `reconcile_diffs` | Stats réconciliation |
| `anomalies_json` | TEXT — anomalies cross-check Yahoo (Phase 5.3.c) |
| `summary_json` | LONGBLOB — payload `run_summary` complet |

Recommandation rétention : purger > 90 jours (cron mensuel).

Tous les `run_summary` du module portent désormais
`schema_version` (cf. `core.run_summary.attach_schema_version`).

### 9.3 Cross-check Yahoo (opt-in, Phase 5.3.c)

Pour comparer les dividendes ingérés (Alpaca) à un second canal (Yahoo Finance),
installer l'extra optionnel :

```powershell
pip install -e ".[cross-check]"
```

Puis ajouter `--cross-check yahoo` au CLI `sync` ou `run` :

```powershell
python -m corporate_actions sync --portfolio-only --account live1 --cross-check yahoo
python -m corporate_actions run  --portfolio-only --account live1 --cross-check yahoo
```

Comportement :

- Lazy import de `yfinance` (jamais bloquant : si la lib est absente, anomalies = []).
- Pour chaque dividende Yahoo dans la fen�tre `[start_date, end_date]` et la liste de symboles, on compare avec `corporate_actions_events` (provider Alpaca).
- Trois types d'anomalies remont�es dans `summary_json["anomalies_json"]` :
  - `missing_in_ingested` : Yahoo a un dividende, Alpaca non.
  - `missing_in_yahoo` : Alpaca a un dividende, Yahoo non.
  - `amount_mismatch` : montant divergent au-del� de la tol�rance (1e-4 par d�faut).
- Le cross-check **ne bloque jamais** la sync principale (try/except global).
### 9.4 Tests Phase 5.3
```powershell
python -m pytest tests/test_corporate_actions_models.py tests/test_corporate_actions_audit_runs.py tests/test_corporate_actions_cross_check_yahoo.py --no-cov -q
```
