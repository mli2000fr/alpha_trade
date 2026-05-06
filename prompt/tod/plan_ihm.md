# Plan IHM — Refactor professionnel & UX institutionnelle

> **Document destiné à un agent IA développeur** (GitHub Copilot,
> Claude, GPT-class). Ce document est un **prompt opérationnel** :
> chaque section décrit un objectif, les fichiers concernés, les
> règles strictes à respecter, et les critères d'acceptation.
>
> **Objectif global** : transformer l'IHM Streamlit actuelle (16 pages,
> certaines monolithiques de 100-150 KB, sans tooltips, navigation
> plate) en une **interface professionnelle institutionnelle** :
>
> 1. **Claire** : chaque page a un rôle unique, < 800 lignes.
> 2. **Compréhensible** : chaque paramètre, thème, indicateur, bouton
>    expose un tooltip `?` détaillé (rôle, impact, exemple, valeur par
>    défaut, plage acceptable, références doc).
> 3. **Cohérente** : palette/typo/icônes/badges/statuts unifiés.
> 4. **Hiérarchisée** : navigation à 5 sections logiques.
> 5. **Testée** : couverture AppTest (Streamlit testing API) > 80 %.
>
> **Score IHM cible** : 8.0 → **9.5** (cf.
> [`prompt/tod/28_plan_10_10_2.md`](28_plan_10_10_2.md), Phase D).

---

## 0. Règles d'or à respecter par l'agent IA

> ⚠️ **Lisez et respectez ces règles à chaque modification.**

1. **NE JAMAIS** réécrire une page sans avoir d'abord :
   * lu le fichier source en entier (`read_file` sans `limit`) ;
   * lu les services consommés (`ihm/services/*.py`) ;
   * lu les tests AppTest associés (`tests/test_ihm_*.py`,
     `tests/test_pages_*.py`).
2. **NE JAMAIS** supprimer un appel à un service sans vérifier qu'il
   n'est consommé nulle part ailleurs (utiliser `grep_search`).
3. **NE JAMAIS** introduire de logique métier dans `ihm/pages/*.py`.
   Toute logique métier doit vivre dans `ihm/services/` ou
   `ihm/components/` ou les modules cœur (`risk_management/`,
   `execution_engine/`, etc.).
4. **TOUJOURS** ajouter un tooltip `help="..."` à chaque widget
   `st.slider`, `st.selectbox`, `st.number_input`, `st.text_input`,
   `st.checkbox`, `st.radio`, `st.date_input`, `st.time_input`,
   `st.toggle`, `st.color_picker`, `st.file_uploader`. Le contenu vient
   de `ihm/help/<page>.yaml` via `_help(key)`.
5. **TOUJOURS** ajouter un test AppTest minimal (`tests/test_ihm_*.py`)
   pour chaque page refactorée.
6. **TOUJOURS** préserver la rétrocompatibilité des imports publics
   exposés dans `ihm/pages/__init__.py` et `ihm/services/__init__.py`.
7. **TOUJOURS** valider après chaque commit : `pytest tests/test_ihm_*
   tests/test_pages_* --no-cov -p no:randomly` doit rester vert.
8. **NE JAMAIS** dépasser **800 lignes** par fichier `ihm/pages/*.py`
   ou `ihm/components/*.py`. Hard limit. Au-delà → découper.
9. **TOUJOURS** documenter dans le tooltip : (a) **rôle** du paramètre,
   (b) **impact** sur le système (quel module, quelle décision), (c)
   **exemple** d'usage concret, (d) **valeur par défaut**, (e) **plage
   acceptable** (min/max ou enum), (f) **lien doc** (chemin relatif
   vers `doc/`).
10. **NE JAMAIS** committer un YAML help avec un BOM UTF-8 (régression
    de S10.1). Utiliser `utf-8` strict.

---

## 1. État des lieux (audit IHM 2026-05-06)

### 1.1 Inventaire pages et tailles

| Fichier | Taille | Verdict | Priorité refactor |
|---|---:|---|---:|
| `ihm/pages/_execution_center.py` | **150 502 o** (~3 030 l.) | 🔴 monolithe critique | **P0** |
| `ihm/pages/backtesting.py` | **97 113 o** (~1 950 l.) | 🔴 monolithe | **P0** |
| `ihm/pages/_workflow.py` | **45 842 o** (~920 l.) | 🟠 trop gros | **P1** |
| `ihm/pages/ml.py` | **32 999 o** (~660 l.) | 🟡 limite | **P2** |
| `ihm/pages/pipeline.py` | **22 206 o** (~445 l.) | 🟢 OK | — |
| `ihm/pages/settings.py` | **21 258 o** (~425 l.) | 🟢 OK | — |
| `ihm/pages/supervision_ops.py` | **19 089 o** (~380 l.) | 🟢 OK | — |
| `ihm/pages/execution.py` | **16 545 o** (~330 l.) | 🟢 OK | — |
| `ihm/pages/_alpha_scanner_diagnostics.py` | **15 901 o** (~315 l.) | 🟢 OK | — |
| `ihm/pages/screening.py` | **15 270 o** (~305 l.) | 🟢 OK | — |
| `ihm/pages/_shared.py` | **14 989 o** (~300 l.) | 🟢 OK | — |
| `ihm/pages/parity.py` | **11 392 o** (~225 l.) | 🟢 OK | — |
| `ihm/pages/alpaca_accounts.py` | **10 396 o** (~210 l.) | 🟢 OK | — |
| `ihm/pages/overview.py` | **9 015 o** (~180 l.) | 🟢 OK | — |
| `ihm/pages/_data_integrity.py` | **8 418 o** (~170 l.) | 🟢 OK | — |
| `ihm/pages/db_admin.py` | **7 906 o** (~160 l.) | 🟢 OK | — |
| `ihm/pages/risk.py` | **4 460 o** (~90 l.) | 🟢 OK | — |
| `ihm/pages/corporate_actions.py` | **2 652 o** (~55 l.) | 🟢 OK | — |
| `ihm/pages/_watcher_block.py` | **3 340 o** (~70 l.) | 🟢 OK | — |
| `ihm/pages/launch_options/` | sous-package | 🟢 OK | — |

**Manquant** : aucune **page Tax & compliance** (logique livrée dans
`tax/wash_sale.py` mais non câblée).

### 1.2 Diagnostic UX

| Constat | Sévérité | Évidence |
|---|---|---|
| Aucun tooltip `help=` systématique sur les widgets | 🔴 P0 | `grep_search "st\.(slider|selectbox|number_input)" ihm/` ⇒ majorité sans `help=` |
| Pages mélangent config opérateur + observabilité + admin | 🔴 P0 | `_execution_center.py` ≈ 12 sections juxtaposées |
| Pas de glossaire intégré | 🟠 P1 | aucune page `glossary.py` |
| Couleurs/badges incohérents entre pages | 🟠 P1 | `components/status_badges.py` sous-utilisé |
| Pas de mode sombre / clair switchable | 🟡 P2 | thème par défaut Streamlit |
| Navigation plate (16 pages au même niveau) | 🟠 P1 | `services/navigation.py` |
| Pas de page d'aide « quickstart opérateur » | 🟠 P1 | `doc/onboarding_operator.md` n'a pas de pendant IHM |

### 1.3 Diagnostic architecture

| Constat | Sévérité |
|---|---|
| Logique métier dans `ihm/pages/*.py` (calculs, formatage payloads, etc.) | 🟠 P1 |
| Helpers `_render_*` éclatés et privés ; pas de convention claire | 🟠 P1 |
| Certains services (`pipeline_runner`, `backtesting_runner`) appelés directement depuis pages sans abstraction | 🟡 P2 |
| Aucune façade testable pour les pages monolithiques | 🔴 P0 |

---

## 2. Architecture cible

### 2.1 Arborescence cible

```
ihm/
├── app.py                          # Point d'entrée (router + thème + sidebar globale)
├── README.md                       # MAJ : architecture + conventions
├── help/                           # ★ NOUVEAU : tooltips contextuels (1 YAML par page)
│   ├── _common.yaml                # tooltips partagés (broker, account, mode)
│   ├── execution_center.yaml
│   ├── backtesting.yaml
│   ├── settings.yaml
│   ├── risk.yaml
│   ├── screener.yaml
│   ├── selector.yaml
│   ├── ml.yaml
│   ├── parity.yaml
│   ├── tax_compliance.yaml         # ★ NOUVEAU
│   ├── compliance_audit.yaml       # ★ NOUVEAU (chaîne audit HMAC + DR + CVE)
│   └── glossary.yaml               # ★ NOUVEAU (définitions termes)
├── theme/                          # ★ NOUVEAU : palette + fonts + icônes
│   ├── __init__.py
│   ├── palette.py                  # tokens couleurs (light/dark)
│   ├── typography.py               # tokens fonts
│   ├── icons.py                    # mapping icônes Lucide
│   └── badges.py                   # helpers badges colorés
├── components/                     # widgets réutilisables (sans état métier)
│   ├── help_tooltip.py             # ★ NOUVEAU : _help(key) loader
│   ├── status_badges.py            # existant ; harmoniser
│   ├── tables.py                   # existant
│   ├── metrics.py                  # existant
│   ├── kpi_card.py                 # ★ NOUVEAU : carte KPI standardisée
│   ├── section_header.py           # ★ NOUVEAU : titre section + tooltip + lien doc
│   └── ... (existants)
├── services/                       # accès données / appels backend (sans Streamlit)
│   ├── help_loader.py              # ★ NOUVEAU : load YAML + cache
│   ├── theme_manager.py            # ★ NOUVEAU : light/dark toggle
│   └── ... (existants)
├── pages/
│   ├── __init__.py                 # façade : exporter render() de chaque page
│   ├── _shared.py                  # < 800 l. ; sinon découper en _shared/*
│   ├── overview.py                 # tableau de bord global
│   ├── settings.py                 # config opérateur (compte, capital, alerting)
│   ├── glossary.py                 # ★ NOUVEAU
│   ├── compliance_audit.py         # ★ NOUVEAU
│   ├── tax_compliance.py           # ★ NOUVEAU
│   ├── execution_center/           # ★ NOUVEAU (éclatement de _execution_center.py)
│   │   ├── __init__.py             # façade render(), < 200 l.
│   │   ├── _summary.py             # bandeau global + KPI run en cours
│   │   ├── _open_orders.py         # ordres ouverts + actions
│   │   ├── _positions.py           # positions live + P&L
│   │   ├── _brackets.py            # synthetic brackets + OCO
│   │   ├── _fills.py               # journal fills + slippage
│   │   ├── _risk_state.py          # circuit breaker + sizing telemetry
│   │   ├── _broker_health.py       # statut Alpaca/IBKR + failover
│   │   ├── _audit_chain.py         # chaîne HMAC visualisée
│   │   ├── _preflight.py           # rapport preflight
│   │   └── _replay.py              # replay run sélectionné
│   ├── backtesting/                # ★ NOUVEAU (éclatement)
│   │   ├── __init__.py             # façade
│   │   ├── _config.py              # paramètres backtest
│   │   ├── _runner.py              # lancement + suivi
│   │   ├── _results.py             # courbes equity, drawdown, etc.
│   │   ├── _attribution.py         # Brinson-Fachler sectorielle
│   │   ├── _replay.py              # replay signaux/exécutions
│   │   └── _calibration.py         # weights calibration trimestrielle
│   ├── workflow/                   # ★ NOUVEAU (éclatement de _workflow.py)
│   │   ├── __init__.py
│   │   ├── _stages.py
│   │   ├── _runner.py
│   │   └── _history.py
│   └── ... (autres pages déjà OK)
└── tests/
    ├── test_ihm_help_tooltips.py    # ★ NOUVEAU : audit présence help= sur widgets critiques
    ├── test_ihm_execution_center_e2e.py  # ★ NOUVEAU : AppTest exhaustif
    ├── test_ihm_backtesting_e2e.py       # ★ NOUVEAU
    ├── test_ihm_tax_compliance.py        # ★ NOUVEAU
    ├── test_ihm_compliance_audit.py      # ★ NOUVEAU
    ├── test_ihm_glossary.py              # ★ NOUVEAU
    ├── test_help_loader.py               # ★ NOUVEAU
    └── test_theme_manager.py             # ★ NOUVEAU
```

### 2.2 Navigation hiérarchique cible

L'IHM doit grouper les pages en **5 sections** dans la sidebar :

```
🏠 Accueil
   └── Overview (KPI globaux, statut système)

📈 Trading
   ├── Execution center (live)
   ├── Open positions & brackets
   ├── Risk dashboard
   └── Pre-flight & broker health

🔬 Analyse & Recherche
   ├── Screening
   ├── Selector / Alpha scanner
   ├── Backtesting
   ├── Parity (backtest vs live)
   └── ML / Model factory

⚙️ Configuration
   ├── Settings (compte, capital, alerting)
   ├── Alpaca accounts
   ├── Pipeline (run config)
   └── Workflow (orchestration)

🛡️ Conformité & Admin
   ├── Compliance & audit chain
   ├── Tax compliance (wash sales, lots)
   ├── Corporate actions
   ├── DB admin
   ├── Supervision ops
   ├── Data integrity
   └── Glossary
```

Implémenté via `ihm/services/navigation.py` (déjà existant — étendre).

---

## 3. Spécification du système de tooltips `?`

### 3.1 Format YAML `ihm/help/<page>.yaml`

Chaque tooltip doit obligatoirement contenir les 6 champs suivants :

```yaml
# ihm/help/risk.yaml
risk_per_trade_pct:
  title: "Risque par trade (% du capital)"
  description: |
    Pourcentage maximum du capital total qui peut être perdu sur
    une seule position si le stop-loss est touché. Détermine
    directement la taille de position via le sizing ATR :
    `position_size = (capital × risk_pct) / (entry_price - stop_price)`.
  impact: |
    - Module impacté : `risk_management/position_sizer.py`
    - Décision impactée : taille de toute nouvelle position
    - Effet direct sur l'exposition portefeuille et le drawdown max
  example: |
    Capital 100 000 $, risk 0.5 %, entry 50 $, stop 48 $ :
    `(100000 × 0.005) / (50 - 48) = 250 actions` (12 500 $ d'exposition)
  default: 0.5
  range: "[0.1, 5.0] (%)"
  doc_ref: "doc/risk_management.md#sizing-atr"

circuit_breaker_dd_threshold_pct:
  title: "Circuit breaker — drawdown max"
  description: |
    Seuil de drawdown intraday au-delà duquel le circuit breaker
    suspend toute nouvelle entrée et déclenche le mode "flatten" sur
    les positions existantes.
  impact: |
    - Module impacté : `risk_management/circuit_breaker.py`
    - Décision impactée : flatten + suspension entrées
    - Réinitialisation : à la prochaine séance ou via override manuel
  example: |
    Capital initial du jour 100 000 $, seuil 3 % :
    si capital descend sous 97 000 $, déclenchement.
  default: 3.0
  range: "[1.0, 10.0] (%)"
  doc_ref: "doc/risk_management.md#circuit-breaker"
```

### 3.2 Helper `_help(key)`

```python
# ihm/components/help_tooltip.py
from ihm.services.help_loader import load_help

def _help(page: str, key: str) -> str:
    """Retourne le markdown formaté pour un tooltip Streamlit."""
    entry = load_help(page).get(key)
    if entry is None:
        return ""  # ne pas planter si manquant ; logger un warning
    return (
        f"**{entry['title']}**\n\n"
        f"{entry['description']}\n\n"
        f"**Impact** : {entry['impact']}\n\n"
        f"**Exemple** : {entry['example']}\n\n"
        f"**Défaut** : `{entry['default']}` — **Plage** : `{entry['range']}`\n\n"
        f"[📖 Doc]({entry['doc_ref']})"
    )
```

### 3.3 Usage standardisé dans les pages

```python
# AVANT (mauvais)
risk_pct = st.slider("Risk %", 0.1, 5.0, 0.5)

# APRÈS (correct)
from ihm.components.help_tooltip import _help

risk_pct = st.slider(
    "Risque par trade (%)",
    min_value=0.1, max_value=5.0, value=0.5, step=0.1,
    help=_help("risk", "risk_per_trade_pct"),
    key="risk_pct_slider",
)
```

### 3.4 Test de présence systématique

```python
# tests/test_ihm_help_tooltips.py
import ast, pathlib

CRITICAL_WIDGETS = {
    "slider", "selectbox", "number_input", "text_input",
    "checkbox", "radio", "date_input", "toggle",
}
PAGES_DIR = pathlib.Path("ihm/pages")

def test_all_critical_widgets_have_help():
    missing = []
    for py in PAGES_DIR.rglob("*.py"):
        if py.name.startswith("__"):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in CRITICAL_WIDGETS):
                kwargs = {kw.arg for kw in node.keywords}
                if "help" not in kwargs:
                    missing.append(f"{py}:{node.lineno} st.{node.func.attr}")
    assert not missing, f"{len(missing)} widgets sans help= :\n" + "\n".join(missing[:30])
```

---

## 4. Spécification thème pro

### 4.1 Palette unifiée (`ihm/theme/palette.py`)

```python
LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#F8FAFC",
    "primary": "#1E40AF",       # blue-800
    "success": "#16A34A",       # green-600
    "warning": "#CA8A04",       # yellow-600
    "danger": "#DC2626",        # red-600
    "text": "#0F172A",
    "text_muted": "#64748B",
    "border": "#E2E8F0",
}
DARK = {
    "bg": "#0F172A",
    "surface": "#1E293B",
    "primary": "#60A5FA",
    "success": "#4ADE80",
    "warning": "#FACC15",
    "danger": "#F87171",
    "text": "#F1F5F9",
    "text_muted": "#94A3B8",
    "border": "#334155",
}
```

### 4.2 Badges statut harmonisés

```python
# ihm/components/status_badges.py
def status_badge(label: str, level: str) -> str:
    """level ∈ {'ok', 'warning', 'danger', 'neutral', 'info'}"""
    icons = {"ok": "🟢", "warning": "🟡", "danger": "🔴",
             "neutral": "⚪", "info": "🔵"}
    return f"{icons[level]} **{label}**"
```

Tous les statuts (broker health, preflight, DR drill, CVE, parity score)
doivent passer par cette fonction.

### 4.3 Cartes KPI standardisées

```python
# ihm/components/kpi_card.py
def kpi_card(label: str, value, delta=None, help_key=None,
             page=None, level="neutral"):
    st.metric(
        label=label,
        value=value,
        delta=delta,
        help=_help(page, help_key) if help_key else None,
    )
```

---

## 5. Sprints de refactor (alignés `28_plan_10_10_2.md` Phase D)

### Sprint S19 — Découpage des monolithes (2 sem.)

#### S19.1 — `_execution_center.py` (P0 critique)

**Préreq absolu** : écrire `tests/test_ihm_execution_center_e2e.py`
AVANT de toucher au fichier. Couvrir au minimum :
- chargement de la page (smoke) ;
- affichage bandeau KPI ;
- table positions ouvertes ;
- table ordres ouverts ;
- bouton cancel order (mock broker) ;
- bouton flatten (confirmation) ;
- chaîne audit HMAC affichée ;
- replay run sélectionné.

**Découpage** :
1. Identifier les **sections logiques** dans le fichier actuel
   (commentaires `# === Section ===`, fonctions `_render_*`).
2. Pour chaque section, créer `ihm/pages/execution_center/_<section>.py`
   exposant **une seule fonction publique** `def render(ctx) -> None`.
3. La façade `ihm/pages/execution_center/__init__.py` :
   ```python
   import streamlit as st
   from . import (_summary, _positions, _open_orders, _brackets,
                  _fills, _risk_state, _broker_health, _audit_chain,
                  _preflight, _replay)

   def render():
       ctx = _build_context()
       tabs = st.tabs(["Résumé", "Positions", "Ordres", "Brackets",
                       "Fills", "Risque", "Broker", "Audit",
                       "Pre-flight", "Replay"])
       for tab, mod in zip(tabs, [_summary, _positions, _open_orders,
                                   _brackets, _fills, _risk_state,
                                   _broker_health, _audit_chain,
                                   _preflight, _replay]):
           with tab:
               mod.render(ctx)
   ```
4. **Cible** : `__init__.py` < 200 lignes, chaque `_<section>.py` < 500.
5. Lancer la suite AppTest après **chaque** section extraite.

#### S19.2 — `backtesting.py` (P0)

Même méthode, sections : config / runner / results / attribution /
replay / calibration.

#### S19.3 — `_workflow.py` (P1)

Sections : stages / runner / history.

#### S19.4 — Page `tax_compliance.py` (NOUVELLE)

Câblage `tax/wash_sale.py` :
- Sélecteur de période (`from`, `to`).
- Sélecteur de compte.
- Table des lots avec colonnes : symbol, open_date, close_date, qty,
  cost_basis, proceeds, gain_loss, holding_period, wash_sale_flag.
- KPI : nombre de wash sales détectées, montant ajusté.
- Export CSV équivalent 1099-B.
- Tooltips obligatoires sur tous les filtres.

#### S19.5 — Refonte navigation

Étendre `ihm/services/navigation.py` pour exposer la hiérarchie en 5
sections (cf. §2.2). Ne jamais hardcoder dans `app.py`.

### Sprint S20 — UX pro (2 sem.)

#### S20.1 — Module `ihm/components/help_tooltip.py` + `services/help_loader.py`

#### S20.2 — Module `ihm/theme/` complet

#### S20.3 — Remplir `ihm/help/<page>.yaml` pour les ~150 paramètres clés

**Liste indicative non exhaustive** :
- `settings` : capital_initial, mode_broker, account_id, alerting_slack,
  alerting_email, capital_preset, conviction_threshold ;
- `risk` : risk_per_trade_pct, max_concurrent_positions, max_sector_exposure,
  circuit_breaker_dd_threshold_pct, sizing_method ;
- `execution_center` : preflight_enabled, replay_window, oco_strategy,
  bracket_offset_atr_mult, flatten_confirmation ;
- `backtesting` : start_date, end_date, universe, initial_capital,
  commission_model, slippage_model, walk_forward_window ;
- `screener` : min_dollar_volume, min_price, max_price, min_atr_pct,
  rs_threshold, range_compression ;
- `selector` : score_weights, sector_neutralization, top_n,
  filter_profile_strict ;
- `ml` : drift_gate_threshold, model_version, champion_strategy,
  challenger_validation_window ;
- `parity` : tolerance_pct, lookback_days, top_n_divergent ;
- `pipeline` : steps_enabled, parallelism, dry_run.

Pour CHAQUE clé, remplir les 6 champs (title, description, impact,
example, default, range, doc_ref).

#### S20.4 — Page `glossary.py`

Cherchable (`st.text_input` filter) ; charge depuis
`ihm/help/glossary.yaml`. Termes minimum : ATR, slippage, OCO, bracket,
RPO/RTO, HMAC, walk-forward, drift, champion/challenger, wash sale,
Brinson-Fachler, parity score, drawdown, RS, sector neutralization.

#### S20.5 — Test `tests/test_ihm_help_tooltips.py` activé en CI

Hard fail si un widget critique manque `help=`.

---

## 6. Critères d'acceptation finaux

L'agent IA doit valider **chacun** de ces critères avant de clore le
refactor :

| # | Critère | Méthode de vérification |
|---|---|---|
| C1 | Aucun fichier `ihm/pages/*.py` > 800 lignes | `Get-ChildItem ihm/pages -Recurse -File -Include *.py \| Where-Object { (Get-Content $_).Count -gt 800 }` doit retourner vide |
| C2 | `_execution_center.py` éclaté en sous-package | `Test-Path ihm/pages/execution_center/__init__.py` ; ancien fichier renommé `.legacy` puis supprimé |
| C3 | `backtesting.py` éclaté | idem |
| C4 | `_workflow.py` éclaté | idem |
| C5 | Page `tax_compliance.py` câblée | `tests/test_ihm_tax_compliance.py` vert |
| C6 | Page `compliance_audit.py` créée | `tests/test_ihm_compliance_audit.py` vert |
| C7 | Page `glossary.py` créée | `tests/test_ihm_glossary.py` vert |
| C8 | Tooltips systématiques | `tests/test_ihm_help_tooltips.py` vert |
| C9 | Help YAML : 6 champs obligatoires sur 100 % des entrées | `tests/test_help_yaml_schema.py` vert |
| C10 | Theme manager light/dark fonctionnel | `tests/test_theme_manager.py` vert |
| C11 | Navigation hiérarchique 5 sections | `tests/test_navigation_hierarchy.py` vert |
| C12 | Aucune logique métier dans `ihm/pages/*.py` | revue manuelle + grep `import.*risk_management|execution_engine.*` doit passer par `ihm/services/` |
| C13 | Couverture AppTest > 80 % sur `ihm/` | `pytest tests/test_ihm_* tests/test_pages_* --cov=ihm --cov-report=term --cov-fail-under=80` |
| C14 | 0 régression sur la suite globale | `pytest tests/ --no-cov -p no:randomly` ⇒ même nombre de tests verts qu'avant |
| C15 | Encodage UTF-8 strict (no BOM) sur tous YAML | `python -c "for f in glob('ihm/help/*.yaml'): assert open(f, 'rb').read(3) != b'\xef\xbb\xbf'"` |

---

## 7. Procédure recommandée pour l'agent IA

```
Pour CHAQUE page à refactorer :

1. read_file(page_path)                 # lecture complète
2. grep_search(symbols utilisés)        # comprendre les dépendances
3. Lister les sections logiques         # commenter dans un fichier scratch
4. Écrire le test E2E AppTest AVANT     # baseline comportement actuel
5. pytest le test ⇒ doit passer
6. Créer le sous-package + __init__.py façade vide
7. Extraire UNE section ⇒ pytest      # micro-itération
8. Répéter §7 jusqu'à épuisement
9. Supprimer l'ancien fichier monolithique
10. Ajouter tooltips sur TOUS les widgets
11. Remplir le YAML help correspondant
12. pytest tests/test_ihm_help_tooltips.py
13. Commit atomique + message clair
```

**Ne jamais faire de "big bang"** : chaque section extraite doit être
committable indépendamment.

---

## 8. Anti-patterns à éviter absolument

| Anti-pattern | Conséquence | Correction |
|---|---|---|
| Mettre du `requests.post(...)` ou `engine.execute(...)` directement dans une page | Couplage IHM ↔ infra ; intestable | Déplacer dans `ihm/services/` |
| `st.session_state["x"] = compute_complex(...)` dans une page | Re-calcul à chaque rerun ; lenteur | `@st.cache_data` ou helper service |
| Ajouter un widget sans `help=` | Rejet par `tests/test_ihm_help_tooltips.py` | Compléter `ihm/help/<page>.yaml` |
| Copier-coller un bloc de rendu entre 2 pages | Drift ; double maintenance | Extraire en `components/` |
| Hardcoder une couleur hex `#FF0000` | Incohérence thème | Importer de `ihm/theme/palette.py` |
| Hardcoder un libellé en anglais | Incohérence linguistique (projet francophone) | Tous les libellés en français pro |
| Laisser un `print(...)` ou `st.write(debug_var)` | Pollution UI | Logger via `common/logging_setup.py` |
| Importer `pages._execution_center` après split | Import cassé | Mettre à jour `pages/__init__.py` (façade rétro-compat) |
| Modifier `app.py` sans tester le router complet | Pages absentes / dupliquées | `tests/test_app_router.py` à étendre |

---

## 9. Livrables attendus à la fin du refactor

1. **Code** :
   * `ihm/pages/execution_center/` (10 fichiers `_<section>.py` + `__init__.py`).
   * `ihm/pages/backtesting/` (6 fichiers).
   * `ihm/pages/workflow/` (3 fichiers).
   * `ihm/pages/tax_compliance.py`, `compliance_audit.py`, `glossary.py`.
   * `ihm/help/` (10+ YAML files, 100 % des paramètres exposés).
   * `ihm/theme/` (4 fichiers).
   * `ihm/components/help_tooltip.py`, `kpi_card.py`, `section_header.py`.
   * `ihm/services/help_loader.py`, `theme_manager.py`.

2. **Tests** :
   * `tests/test_ihm_execution_center_e2e.py` (≥ 8 cas).
   * `tests/test_ihm_backtesting_e2e.py` (≥ 6 cas).
   * `tests/test_ihm_workflow_e2e.py` (≥ 4 cas).
   * `tests/test_ihm_tax_compliance.py` (≥ 4 cas).
   * `tests/test_ihm_compliance_audit.py` (≥ 4 cas).
   * `tests/test_ihm_glossary.py` (≥ 2 cas).
   * `tests/test_ihm_help_tooltips.py` (audit présence).
   * `tests/test_help_yaml_schema.py` (audit format YAML).
   * `tests/test_theme_manager.py` (light/dark).
   * `tests/test_navigation_hierarchy.py` (5 sections).

3. **Documentation** :
   * `ihm/README.md` mis à jour : architecture, conventions, comment
     ajouter une page, comment ajouter un tooltip.
   * `doc/ihm_style_guide.md` : palette, typographie, badges, icônes,
     règles UX (taille de police, spacing, etc.).
   * Section dans `doc/onboarding_operator.md` : navigation par
     sections + glossaire + tooltips.

4. **Rapport** :
   * `prompt/tod/29_ihm_refactor_delivery_report.md` : récapitulatif
     fichiers créés/modifiés/supprimés, métriques avant/après (taille
     fichiers, % widgets avec help, couverture AppTest).

---

## 10. Score IHM cible et trajectoire

| Étape | Note IHM | Critères principaux |
|---|---:|---|
| Avant refactor (post-Phase C) | **8.0** | dashboard parité ajouté ; monolithes persistants |
| Après S19 (découpage + page Tax) | **8.7** | C1, C2, C3, C4, C5, C11 |
| Après S20 (UX pro + tooltips) | **9.5** | C6, C7, C8, C9, C10, C13, C14 |

**Gain global projet** : +0.18 (note globale 8.40 → 8.58 sur la note
projet, avant les autres sprints S21+).

---

## 11. Annexe — Exemple complet de page refactorée

### Avant (anti-pattern)

```python
# ihm/pages/risk.py (extrait actuel)
import streamlit as st
from risk_management.position_sizer import compute_size

def render():
    st.title("Risk")
    risk = st.slider("Risk %", 0.1, 5.0, 0.5)
    capital = st.number_input("Capital", value=100000)
    entry = st.number_input("Entry", value=50.0)
    stop = st.number_input("Stop", value=48.0)
    size = compute_size(capital, risk / 100, entry, stop)
    st.write(f"Size: {size}")
```

### Après (cible)

```python
# ihm/pages/risk.py (cible)
import streamlit as st
from ihm.components.help_tooltip import _help
from ihm.components.section_header import section_header
from ihm.components.kpi_card import kpi_card
from ihm.services.risk_calculator import sizing_preview  # service métier

PAGE = "risk"

def render():
    section_header(
        title="Gestion du risque",
        subtitle="Sizing ATR + circuit breaker + exposition",
        help_key="risk_overview",
        page=PAGE,
    )

    col1, col2 = st.columns(2)
    with col1:
        risk_pct = st.slider(
            "Risque par trade (%)",
            min_value=0.1, max_value=5.0, value=0.5, step=0.1,
            help=_help(PAGE, "risk_per_trade_pct"),
            key="risk_pct",
        )
        capital = st.number_input(
            "Capital ($)",
            min_value=1000, value=100_000, step=1000,
            help=_help(PAGE, "capital_initial"),
            key="capital",
        )
    with col2:
        entry = st.number_input(
            "Prix d'entrée ($)",
            min_value=0.01, value=50.0, step=0.01,
            help=_help(PAGE, "entry_price"),
            key="entry",
        )
        stop = st.number_input(
            "Prix de stop ($)",
            min_value=0.01, value=48.0, step=0.01,
            help=_help(PAGE, "stop_price"),
            key="stop",
        )

    preview = sizing_preview(capital=capital, risk_pct=risk_pct,
                             entry=entry, stop=stop)
    kpi_card("Taille position (actions)", preview.size,
             help_key="position_size_computed", page=PAGE)
    kpi_card("Exposition ($)", f"{preview.exposure:,.0f}",
             help_key="position_exposure", page=PAGE)
    kpi_card("Risque effectif ($)", f"{preview.risk_amount:,.0f}",
             delta=f"{preview.risk_pct_effective:.2%}",
             help_key="risk_effective", page=PAGE)
```

```yaml
# ihm/help/risk.yaml (extrait)
risk_overview:
  title: "Gestion du risque"
  description: |
    Tableau de bord centralisant le calcul de taille de position
    (ATR-based), l'état du circuit breaker, et le suivi de
    l'exposition par secteur.
  impact: "Module : risk_management/ ; Décisions : sizing, flatten, suspension."
  example: "Voir 'Sizing' ci-dessous pour un cas d'usage capital 100 k$."
  default: "—"
  range: "—"
  doc_ref: "doc/risk_management.md"

risk_per_trade_pct:
  # ... cf. §3.1 ci-dessus ...
```

---

> **Fin du prompt.** L'agent IA doit maintenant exécuter les sprints S19
> et S20 en respectant les **règles d'or** (§0), la **procédure** (§7),
> et valider chaque **critère d'acceptation** (§6) avant de produire le
> rapport `29_ihm_refactor_delivery_report.md`.

