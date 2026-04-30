# Audit — `ihm`

> Périmètre : `ihm/` (`app.py`, `pages/*.py`, `services/pipeline_runner.py`,
> `services/backtesting_runner.py`, `services/process_registry.py`, `services/db.py`,
> `services/run_summary.py`).
> Sources : `doc/ihm.md` (536 lignes), code listé,
> tests `tests/test_app.py`, `tests/test_pages_*`, `tests/test_ihm_*`.

---

## 1. Résumé exécutif

`ihm/` est le **cockpit Streamlit** : 9 pages (Vue d'ensemble, Pipeline, Backtesting,
Screening, Risk, Execution, Corporate Actions, ML, Settings/Santé). Pilote des
sous-processus pipeline (workflow 1→14 + steps auxiliaires Data Integrity), maintient
un registre de runs (`artifacts/ihm_pipeline_runs/`, `artifacts/ihm_backtesting_runs/`),
extrait les `::alpha_trade_run_summary::` JSON depuis stdout pour enrichir les vues,
expose un sélecteur multi-comptes, et propose un diagnostic Supervision Ops
(read-only Windows pour Task Scheduler / NSSM watcher).

État global : **module dense, bien architecturé**, séparation page / service /
registry exemplaire. Couverture de tests étendue (chaque page a son test).
Présentation soignée (badges couleur, presets Sync Latest Quotes, sélecteurs).

Principaux risques :

1. **Streamlit = recharge complète à chaque interaction** : si une page fait un appel
   SQL coûteux sans `@st.cache_data`, l'expérience devient pénible. À auditer page par
   page.
2. **Lancement de sous-processus en arrière-plan** : `process_registry.py` gère
   `subprocess.Popen` → risque d'orphan processes si le navigateur est fermé sans
   stop propre. À vérifier le cleanup.
3. **`process_registry`** : artefacts disque persistants — risque de croissance non
   bornée (10 000 runs = 10 000 dossiers). Pas de rotation mentionnée.
4. **Pas d'authentification IHM** : Streamlit local par défaut, mais si un dev expose
   le port 8501 → contrôle complet du pipeline (lancer un live, kill processus...).
5. **Sélecteur multi-comptes côté IHM** : pratique, mais sans verrou cross-utilisateur,
   un seul utilisateur à la fois est sécurisé.
6. **Page `Pipeline` = monolithe** : workflow 1→14 + steps auxiliaires + paramètres
   partagés + centre d'exécution + diagnostic dépendances + bloc 12.bis watcher →
   beaucoup de code dans une seule page.
7. **Diagnostic dépendances Alpha Scanner** (couverture quotes / earnings) avec
   presets Swing Cash Pro / Agressif / Tolérant : très soigné, mais cache `ttl=60s`
   peut induire en erreur (un opérateur croit voir l'état temps réel).
8. **Supervision Ops Windows read-only** : safe, mais la "détection" du watcher
   Windows passe par un bridge PowerShell allowlisté → fragilité si chemin Windows
   change ou exécution policy bloque.

Priorités immédiates :
- Cleanup automatique des processus orphelins.
- Rotation des artefacts `ihm_*_runs/` (TTL 30 jours par défaut).
- Authentification basique (token simple) si exposé hors localhost.
- Découper `pages/pipeline.py`.

---

## 2. Constat détaillé

### 2.1 `app.py`

| Constat | Configure Streamlit, sidebar, formulaire connexion DB, sélecteur compte, routage. |
| Force | Point d'entrée propre. |
| Risque | Pas d'auth. Si `0.0.0.0:8501` accidentellement → exposition réseau. |
| Recommandation | (a) Documenter explicitement "ne jamais exposer hors localhost sans reverse proxy auth" ; (b) check au démarrage que `--server.address=localhost`. |

### 2.2 `services/process_registry.py`

| Item | Détail |
|---|---|
| Constat | Subprocess management. Lance, suit, persiste les runs et logs. Extrait les `run_summary` structurés. |
| Force | Très utile pour l'audit. |
| Risque | **Sécurité opérationnelle** : si Streamlit crash, les `Popen` sont-ils tués ? |
| Risque 2 | **Maintenabilité** : pas de rotation des artefacts. |
| Risque 3 | **Sécurité** : commandes construites par concaténation → un paramètre user mal validé peut injecter. À vérifier (`shlex.quote`). |
| Recommandation | (a) Hook `atexit` qui kill les enfants ; (b) `--max-runs-retention 30` config ; (c) audit des constructions de commande pour shell injection. |

### 2.3 `services/pipeline_runner.py`

| Constat | Définit les steps disponibles + construit les commandes. Mapping IHM ↔ CLI backend. |
| Force | Très bonne factorisation. Mappe les options CLI réelles (cf. doc explicite "options réellement supportées"). |
| Risque | **Maintenabilité** : tout changement de CLI backend exige une mise à jour ici. Pas de test contractuel automatique. |
| Recommandation | Test "tous les paramètres exposés IHM existent dans la CLI backend" via introspection argparse. |

### 2.4 `services/backtesting_runner.py`

| Constat | Idem pipeline_runner mais pour backtest. |
| Recommandation | Idem 2.3. |

### 2.5 `services/run_summary.py`

| Constat | Normalise les résumés métier. |
| Recommandation | Versionner le format des `run_summary` (`schema_version: int` dans chaque payload). |

### 2.6 `services/db.py`

| Constat | Accès DB côté IHM. |
| Risque | **Performance** : Streamlit recharge → si pas de `@st.cache_data`, requêtes répétées. |
| Recommandation | Audit des appels SQL côté pages, mise en cache systématique. |

### 2.7 `pages/overview.py`

| Constat | KPI, statut global, résumés récents pipeline / sélection / sentiment. |
| Risque | Beaucoup de requêtes agrégées → cache obligatoire. |

### 2.8 `pages/pipeline.py`

| Constat | **La page la plus riche** : paramètres partagés, workflow 1→14, steps auxiliaires Data Integrity, centre d'exécution, diagnostic Alpha Scanner deps, bloc 12.bis watcher, import news. |
| Force | Riche fonctionnellement. Très bien documentée dans `doc/ihm.md`. |
| Risque | **Maintenabilité** : monolithe. |
| Recommandation | Découper en modules `pages/pipeline/` :
  - `_workflow.py` (1→14)
  - `_data_integrity.py` (B1, B2)
  - `_execution_center.py`
  - `_alpha_scanner_diagnostics.py`
  - `_watcher_block.py`. |

### 2.9 `pages/backtesting.py`

| Constat | Lance backtest run + backfill + diagnose-screener + recommend-screener. |
| Recommandation | Cohérent avec `services/backtesting_runner.py`. RAS. |

### 2.10 `pages/screening.py` / `risk.py` / `execution.py` / `corporate_actions.py` / `ml.py`

| Constat | Pages de consultation `stock_scores`, `risk_decisions`, `execution_*`,
`corporate_actions_*`, `model_*`. |
| Risque | À auditer le caching côté chaque page. |

### 2.11 `pages/settings.py`

| Constat | Diagnostics environnement, santé, presets pour les seuils data quality. |
| Force | Centralise les presets — bonne pratique. |

### 2.12 Supervision Ops (Windows)

| Constat | Page dédiée (présente mais non listée explicitement dans la liste 9-pages — peut être nichée dans Settings ou Pipeline). Status Task Scheduler / NSSM read-only. Bridge PowerShell allowlisté. Import logs. |
| Risque | **Sécurité opérationnelle** : un bug dans le bridge PowerShell allowlisté = potentielle élévation. |
| Recommandation | Tests rigoureux de l'allowlist + revue du `protection_watcher_secrets.ps1`. |

---

## 3. Risques prioritaires

### Critique
- Aucun.

### Élevé
- Pas d'authentification (mode local accepté, mais à matérialiser via documentation + check).
- Subprocess potentiellement orphelins si Streamlit crash.
- Pas de rotation des artefacts `ihm_*_runs/`.
- Page pipeline monolithique.

### Modéré
- Pas de test contractuel IHM ↔ CLI backend.
- Cache TTL 60s → opérateur peut croire voir temps réel.
- Bridge PowerShell allowlisté = fragile.

### Faible
- Format `run_summary` non versionné.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

L'IHM expose un **diagnostic dépendances Alpha Scanner** soigné pour la couverture
quotes / earnings, avec presets Swing Cash Pro / Agressif / Tolérant et code couleur
vert/orange/rouge. C'est précisément le genre de garde-fou nécessaire face aux limites
IEX.

**À enrichir** :
- ajouter un badge "qualité data marché" basé sur `% symbols with volume_30d > 0` ;
- exposer un panel "Limites Alpaca free" dans Settings rappelant les conventions
  (seuil liquidité IEX, biais spreads, etc.).

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct. L'IHM consomme `stock_bars_daily.close` — la convention split est
transparente.

**Recommandation** : ajouter un badge "Data adjustment: split-adjusted ✅" dans
Settings pour rappeler la convention en place.

---

## 6. Quick wins

1. **Hook `atexit`** dans `process_registry` qui kill les enfants.
2. **Rotation artefacts** : option `IHM_RUNS_RETENTION_DAYS=30`.
3. **Test contractuel IHM ↔ CLI** : introspection argparse.
4. **`schema_version` dans `run_summary`** payload.
5. **Documenter "ne jamais exposer hors localhost sans auth"** dans `doc/ihm.md`.
6. **Check démarrage `--server.address=localhost`**.
7. **Audit shell quoting** dans process_registry.
8. **Cache obligatoire** sur toutes les requêtes DB des pages.

## 7. Recommandations structurelles

1. **Découper `pages/pipeline.py`** en sous-modules.
2. **Auth basique optionnelle** (token query string ou Streamlit native auth si
   activée) pour usage multi-utilisateurs.
3. **Service `ProcessRegistry` singleton DB-backed** au lieu de fichiers : plus de
   stockage cohérent, indexation par run_id, jointure facile avec `run_business_summaries`.
4. **Test snapshot des pages** : Playwright / Streamlit testing pour non-régression
   visuelle.
5. **Centraliser les presets de seuils data quality** (hors page Settings → table SQL
   `ihm_user_preferences` déjà partielle dans `artifacts/ihm_preferences/`).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 5, 6, 7, 8.
- Découpage `pipeline.py`.

### Moyen terme
- Quick wins 3, 4.
- Auth basique optionnelle.
- Test snapshot pages.

### Long terme
- `ProcessRegistry` DB-backed.
- Centralisation préférences IHM en SQL.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Très bons (chaque page a son test). **Manque** :
  - test contractuel IHM ↔ CLI backend.
  - test "subprocess orphelins après crash Streamlit".
  - test snapshot visuel.

### Monitoring
- Pas de "self-monitoring" IHM. **Manque** :
  - métrique "pages les plus lentes" / "appels SQL les plus chers".

### Documentation
- Excellente (`doc/ihm.md` 536 lignes). **Manque** :
  - section sécurité (auth, exposition réseau).
  - section rotation artefacts.
  - section "tests de non-régression visuels".

