# Note de réalignement documentaire — Audit 2026-05-22

> Cette note consolide les mises à jour documentaires identifiées par
> l'audit complet du 2026-05-22 (cf. `prompt/tod3/`). Elle est volontairement
> regroupée ici plutôt qu'éclatée dans chaque doc pour faciliter la revue.
> Les patchs ciblés peuvent être appliqués au fil des sprints S1→S7
> (cf. `prompt/tod3/08_sprint_plan.md`).

## 1. Conventions canoniques en vigueur (à propager dans `doc/CONVENTIONS.md` futur)

| Convention | Valeur | Source vérité code |
|---|---|---|
| `data_adjustment` | `split` (split-only) | `dataIntegrityEngine/import_alpaca_bar.py:36`, `service/eodhd/adapters.py:DATA_ADJUSTMENT_SPLIT` |
| Dividendes | `portfolio_cash_ledger` (jamais dans les prix) | `corporate_actions/engine.py:34-55` |
| Provider OHLCV primaire | `eodhd` | `config.yaml:182` |
| Provider news primaire | `eodhd` | `event_sentiment` defaults |
| Provider quotes | `alpaca` (toujours, IEX biaisé) | `dataIntegrityEngine/sync_latest_quotes.py` |
| Provider metadata | `finnhub` (toujours) | `dataIntegrityEngine/update_sector.py` |
| Provider CA | `alpaca` primaire, EODHD optionnel | `corporate_actions/provider.py` |
| Launcher exécution canonique | `run_execution.py` | README §6 |
| Façade exécution | `python -m execution_engine` (legacy `run`, natif `cancel-all`) | `execution_engine/__main__.py` |
| Swing-only | `true` partout | `capital_presets.yaml` toutes tranches |
| Conviction fusion | quant 0.75 / sentiment 0.15 / macro 0.10 | `config.yaml:200-205`, `core/conviction.py` |
| Kelly | désactivé (statut à clarifier — A-006) | `risk_management/kelly.py` |

## 2. Patchs documentaires à appliquer

### 2.1 `doc/DOC_FONCTIONNELLE.md` — à relire / mettre à jour

- Ajouter encadré "Provider primaire actuel : EODHD".
- Préciser que dividendes ne modifient pas le prix.
- Clarifier l'usage des 7 tranches `capital_presets.yaml` (lien vers `prompt/tod3/04_parametrage_review.md`).
- Signaler explicitement les zones "expérimentales" : Kelly, multi-source bars.

### 2.2 `doc/DOC_TECHNIQUE.md`

- Section "Doctrine d'entrée d'exécution" : `run_execution.py` est canonique ; `python -m execution_engine` est legacy sauf `cancel-all` (cf. anomalie A-002).
- Section "event_sentiment" : ordre des 5 sous-étapes obligatoire (A-003).
- Section "Quote IEX biais" : nommer A-004 et son plan de remédiation.
- Section "Réconciliation J+1" : statut actuel `reconciliation.py` ; cible Sprint S3.

### 2.3 `doc/risk_management.md`

- Documenter explicitement le statut Kelly (expérimental — désactivé par défaut, A-006).
- Documenter la convention `risk_max_drawdown_pct` par tranche (7 % micro → 18 % gros — pourquoi, A-029).
- Documenter convention corrélation : prix split-adjusted (A-025).

### 2.4 `doc/selector.md`

- Renommer ou clarifier `selector_min_relative_strength_index` ≥ 100 : IBD RS rank, pas RSI classique (A-028).
- Documenter `selector_max_anomaly_count` et la monotonie attendue (A-014).

### 2.5 `doc/dataIntegrityEngine.md`

- ✅ Bandeau provider primaire EODHD déjà présent (l. 5-32).
- ✅ Note correction audit 2026-05-22 déjà présente (l. 33-39).
- À ajouter : section "alerting sur fallback silencieux" (A-013).

### 2.6 `doc/data_lineage_matrix.md`

- ✅ Note correction audit 2026-05-22 déjà présente (l. 16-21).
- À ajouter : ligne "stock_quote_snapshots → biais NBBO IEX" plus explicite (A-004).

### 2.7 `doc/event_sentiment.md`

- Documenter l'ordre obligatoire des 5 sous-étapes (A-003).
- Documenter le couplage quota EODHD news + OHLCV + macro (A-019, A-027).

### 2.8 `doc/corporate_actions.md`

- ✅ Convention split-only + ledger documentée (`engine.py:34-55`).
- Ajouter mention oracle "MTM + ledger = total return" à venir Sprint S4 (A-030).

### 2.9 `doc/execution_engine.md`

- Doctrine `run_execution.py` canonique + façade legacy (A-002).
- Réconciliation J+1 : statut actuel + cible Sprint S3 (A-005).
- Gel IHM en mode live (A-024).
- Preflight WARN en simulate (A-021).

### 2.10 `doc/ihm.md`

- Verrou pipeline state machine N+1 (A-015).
- Bandeau "live mode actif" et désactivation actions destructrices (A-024).
- Page "Brokers" doctrine failover (A-016).
- Bannière "SMTP non configuré" (A-012).

### 2.11 `doc/runbook_provider_incident.md`

- Étendre à un incident provider news (A-023).
- Étendre à un fallback silencieux OHLCV (A-013) — quels signaux observer ?

### 2.12 `doc/runbook_reconciliation.md`

- Ajouter chapitre "Réconciliation J+1 vs statement Alpaca" (A-005, Sprint S3).

### 2.13 Nouveaux fichiers à créer

| Fichier | Sprint | Contenu |
|---|---|---|
| `doc/CONVENTIONS.md` | S7 | Index unique des conventions en vigueur (cf. §1 ci-dessus) |
| `doc/CHANGELOG.md` | S7 | Journal des changements documentaires datés |
| `doc/runbook_broker_failover.md` | S5 | Doctrine Alpaca → IBKR + check IHM |
| `doc/_poc/` (sous-dossier) | S7 | Déplacer `async_db_poc.md`, `formal_verification.md`, `tlaps_proofs.md` ou ajouter bandeau "POC non activé" (A-010) |

## 3. Tests documentaires à étendre

- `tests/test_doc_index_and_links.py` : exiger bandeau "POC" sur docs POC.
- `tests/test_doc_provider_alignment.py` : vérifier que `<!-- primary_provider: eodhd -->` est présent dans les docs qui mentionnent un provider.
- Nouveau `tests/test_doc_conventions_index.py` : vérifier que `doc/CONVENTIONS.md` existe et liste les conventions canoniques attendues.

## 4. Procédure de mise à jour recommandée

1. **Sprint S1** : appliquer les patchs §2.3 (risk_management), §2.4 (selector), §2.9 (execution_engine partie A-002), §2.10 (ihm partie banner micro-preset).
2. **Sprint S2** : §2.5 (dataIntegrityEngine alerting fallback), §2.6 (lineage IEX), §2.7 (event_sentiment ordre + quota), §2.10 (ihm dashboard quota).
3. **Sprint S3** : §2.9 (execution_engine réconciliation J+1), §2.10 (ihm verrou pipeline + live), §2.12 (runbook reconciliation).
4. **Sprint S4** : §2.8 (oracle total return), §2.3 (correlation convention).
5. **Sprint S5** : §2.13 (runbook broker failover).
6. **Sprint S6** : §2.3 (Kelly statut), §2.10 (SMTP banner), §2.11 (runbook sentiment).
7. **Sprint S7** : §2.13 (CONVENTIONS, CHANGELOG, _poc), tests documentaires §3.

## 5. Indicateur de complétion documentaire

- Audit livre une **note doc 7.5/10** aujourd'hui.
- Trajectoire post-sprints : 8.5/10 fin S6, 9.0/10 fin S7.
- Cible "10/10 doc" : nécessite en plus un guide opérateur visuel
  (`doc/onboarding_video_script.md` est déjà un bon point de départ).

---

*Note rédigée par l'audit Copilot — 2026-05-22.*  
*Voir `prompt/tod3/` pour le détail complet de l'audit.*

