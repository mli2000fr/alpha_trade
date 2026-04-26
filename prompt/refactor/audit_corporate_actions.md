# Audit — `corporate_actions`

> Périmètre : `corporate_actions/` (`engine.py`, `cli.py`, `provider.py`, `db_io.py`,
> `processors.py`, `reconciliation.py`, `models.py`, `corporate_action_run.py`).
> Sources : `doc/corporate_actions.md`, `README.md` §7, code listé,
> tests `tests/test_corporate_actions*.py`, `tests/test_processors.py`,
> `tests/test_provider.py`, `tests/test_reconciliation.py`.

---

## 1. Résumé exécutif

`corporate_actions/` gère les **dividendes, splits et reverse splits** : sync depuis
Alpaca Corporate Actions API (`v1/corporate-actions`), persistance dans
`corporate_actions_events`, application sur les positions internes
(`corporate_actions_applications`, `portfolio_cash_ledger`), réconciliation. Multi-comptes.
Phases `sync` (3 modes : `--portfolio-only`, `--all-symbols`, `--symbols`) et `apply`
distinctes.

État global : **module bien circonscrit**, séparation phases claire, idempotence via
`idempotency_key`. Choix architectural cohérent : ne touche **pas** à `stock_bars` (les
prix Alpaca étant déjà `split-adjusted`), gère uniquement la comptabilité portefeuille.

Principaux risques :

1. **Dépendance unique à Alpaca CA API** : pas de cross-check (Yahoo, Nasdaq) — un
   événement raté côté Alpaca = position non ajustée silencieusement.
2. **`--portfolio-only` lit `broker_positions_snapshots`** : si l'`execution` n'a pas
   tourné aujourd'hui, le périmètre peut être stale (positions d'hier ou vide). Le README
   le mentionne explicitement → bonne discipline doc.
3. **`apply` est idempotent via `idempotency_key`**, mais la doc ne précise pas
   comment la clé est construite (symbol + ex_date + ca_type + qty ?). Risque de
   double application si la clé est mal calculée.
4. **Ratios de splits** : Alpaca renvoie souvent des ratios sous forme `2:1`,
   `3:2`, etc. Normalisation dans `provider.py` → tester explicitement les cas
   limites (`reverse_split` 1:10, `split` 7:1 type Tesla).
5. **Pas de gestion explicite des spin-offs** : dividendes en cash OK, splits OK, mais
   un spin-off (nouvelle action distribuée) n'est pas mentionné dans la doc.
6. **Apply sans validation de cohérence**: si `position_qty_before` est différent
   entre la position interne et le snapshot broker, que se passe-t-il ? Pas mentionné.

Priorités immédiates :
- Documenter explicitement la construction de l'`idempotency_key`.
- Cross-check optionnel Yahoo / Nasdaq pour les dividendes.
- Couvrir explicitement les spin-offs (au moins lever un warning).

---

## 2. Constat détaillé

### 2.1 `cli.py` — phases `sync`, `apply`, `status`, `run`

| Item | Détail |
|---|---|
| Constat | 4 sous-commandes propres. Multi-comptes. Modes de sync exclusifs. |
| Force | UX simple. `run` enchaîne sync + apply. |
| Risque | **Maintenabilité** : la résolution du périmètre `--portfolio-only` mélange : positions live broker + ordres BUY pending + dernier snapshot DB. Logique de résolution complexe. |
| Recommandation | Documenter explicitement l'ordre de résolution dans `doc/corporate_actions.md`. |

### 2.2 `engine.py` — `CorporateActionEngine`

| Constat | `sync()` valide → tente insert → distingue `inserted/duplicates/invalid`. `apply()` charge pending → applique → écrit ledger / applications → marque `applied/skipped/failed`. |
| Force | États clairs, idempotence. |
| Risque | **Cohérence** : si `apply()` plante au milieu (avant `mark_applied`), la prochaine exécution retraiterait l'événement → vérifié par idempotency_key, mais à confirmer par test. |
| Recommandation | Test "crash mid-apply" → second run sans double crédit. |

### 2.3 `provider.py` — `AlpacaCorporateActionProvider`

| Constat | Pagination, retry, parsing dividends/splits/reverse splits. |
| Risque | **Qualité data** : pas mention des spin-offs, mergers, name changes. |
| Recommandation | Logger explicitement quand un événement Alpaca a un `ca_type` inattendu. |

### 2.4 `processors.py`

| Constat | `process_dividend()`, `process_split()`. |
| Risque | **Cohérence** : `process_split()` arrondit forcément les fractions (Alpaca paie le cash en lieu et place) → assert que la fraction est gérée via `portfolio_cash_ledger` (cash from fractional shares). |
| Recommandation | Test paramétrique : split 3:2 sur 100 shares = 150 shares ; split 5:3 sur 100 shares = 166 shares + cash résiduel. |

### 2.5 `db_io.py`

| Constat | Repository CA. |
| Risque | Standard pour le projet (couplage SQL inline). |

### 2.6 `reconciliation.py`

| Constat | Réconciliation post-application. Détail non documenté. |
| Recommandation | Documenter dans `doc/corporate_actions.md` ce que la réconciliation fait précisément. |

### 2.7 Idempotence

| Constat | `idempotency_key` mentionnée mais sa construction non documentée. |
| Risque | **Cohérence** : si la clé n'inclut pas l'`account_id`, deux comptes recevant le même événement pourraient se voir refuser le second. |
| Recommandation | Documenter formule `idempotency_key = sha256(account_id|symbol|ex_date|ca_type|ratio_or_amount)`. |

---

## 3. Risques prioritaires

### Critique
- Aucun direct, mais **silence sur les spin-offs / mergers** = positions potentiellement
  fausses.

### Élevé
- Source unique Alpaca CA → pas de cross-check.
- Construction `idempotency_key` non documentée.
- Pas de validation de cohérence position interne vs broker pendant `apply`.

### Modéré
- Logique de résolution `--portfolio-only` complexe, peu documentée.
- Pas de test "crash mid-apply".
- Spin-offs / mergers / name changes non couverts.

### Faible
- `corporate_action_run.py` lanceur historique en doublon avec `cli.py`.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Alpaca CA API est dans le tier gratuit (à confirmer) — pas de couverture intraday vs EOD.
**Limites observables** :

- Couverture des annonces tardives : Alpaca peut publier des CA avec délai vs Nasdaq.
- ETFs et structures complexes : couverture incomplète probable.

**Recommandation** :
- cross-check optionnel **Yahoo Finance dividends** (`yfinance.Ticker("AAPL").dividends`)
  → comparer le `cash_amount` Alpaca vs Yahoo, alarmer si divergence > 1 %.
- cross-check optionnel **Nasdaq dividend calendar** (gratuit) → fenêtre J-30 → J+30.

---

## 5. Choix recommandé `split_adjusted` vs `all`

**Renforce la cohérence du choix `split_adjusted`** :
- les prix `stock_bars_daily` sont déjà ajustés des splits ;
- les dividendes restent payés en cash (pas dans les prix) → `corporate_actions apply`
  les ajoute proprement à `portfolio_cash_ledger` ;
- la performance totale = `current_value(positions) + cumulative_cash_ledger`.

C'est **propre, simple, traçable**. À conserver.

---

## 6. Quick wins

1. **Documenter `idempotency_key`** précisément.
2. **Logger les `ca_type` inattendus** (warning critical).
3. **Test paramétrique splits fractionnels** (3:2, 5:3, 7:3...).
4. **Test "crash mid-apply"** → pas de double crédit.
5. **Documenter ordre de résolution `--portfolio-only`**.
6. **Détecter la divergence position interne vs broker** dans `apply` (warning).
7. **Supprimer `corporate_action_run.py`** ou en faire un alias minimal.
8. **Documenter `reconciliation.py`** (que fait-elle exactement ?).

## 7. Recommandations structurelles

1. **Cross-check Yahoo/Nasdaq dividends** en mode opt-in (`--cross-check yahoo`).
2. **Couvrir les spin-offs explicitement** (nouveau processor `process_spinoff`).
3. **Refactor `engine.py`** pour exposer une interface `CAProcessor[ProtocolEvent]` →
   ajout de nouveaux types CA modulaire.
4. **Persister `idempotency_key`** en colonne séparée (pas seulement comme contrainte
   unique implicite).
5. **Audit dédié `corporate_actions_audit_runs`** sur le modèle de
   `cleaning_audit_runs`.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5, 6, 7, 8.

### Moyen terme
- Cross-check Yahoo/Nasdaq.
- Couverture spin-offs.
- Audit dédié.

### Long terme
- Refactor `CAProcessor` Protocol.
- Couverture mergers / name changes.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Bons (`tests/test_corporate_actions*`, `test_processors.py`, `test_provider.py`).
  **Manque** :
  - test "crash mid-apply".
  - test fractionnel.
  - test cross-account idempotency (même CA, deux comptes).
  - test `ca_type` inconnu.

### Monitoring
- `corporate_actions status` existe. **Manque** :
  - alarm IHM "événement inappliqué depuis > 7 jours".
  - dashboard "dividendes encaissés sur 30j" par compte.

### Documentation
- Bonne. **Manque** :
  - construction `idempotency_key`.
  - liste des `ca_type` supportés vs ignorés.
  - runbook "événement raté côté Alpaca, comment le rattraper".

