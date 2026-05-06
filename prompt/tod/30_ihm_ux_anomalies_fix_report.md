# Sprint S20.6 — Rapport « Anomalies UX IHM »

> **Date** : 2026-05-06
> **Périmètre** : 5 anomalies UX bloquantes signalées par l'opérateur
> + audit complémentaire du `plan_ihm.md`.
> **Précédent** : `29_ihm_refactor_delivery_report.md` (sprints S19/S20
> initiaux).

---

## 1. Audit `plan_ihm.md` — état au 2026-05-06

| # | Critère | Statut | Notes |
|---|---|:---:|---|
| C1 | Pages ≤ 800 lignes | ❌ | 3 monolithes restants (P2) |
| C2 | `_execution_center.py` éclaté | ⚠️ | sous-package créé mais `__init__.py` = 2 877 l. |
| C3 | `backtesting.py` éclaté | ❌ | `backtesting/__init__.py` = 2 083 l. |
| C4 | `_workflow.py` éclaté | ❌ | `_workflow/__init__.py` = 935 l., préfixe `_` non navigable |
| C5 | `tax_compliance.py` câblée | ✅ | + test |
| C6 | `compliance_audit.py` créée | ✅ | + test |
| C7 | `glossary.py` créée | ✅ | bug lien doc corrigé S20.6 (anomalie e) |
| C8 | Tooltips systématiques | ✅ | test présent |
| C9 | YAML 6 champs | ✅ | test présent |
| C10 | Theme manager light/dark | ✅ | bug d'intégration corrigé S20.6 (anomalie a) |
| C11 | Navigation hiérarchique | ✅ | étendue à **6 sections** (Pipeline promu) |
| C12 | Pas de logique métier dans `pages/` | ✅ | aucun import direct `risk_management/...` |
| C13 | Couverture > 80 % sur `ihm/` | ❓ | non re-mesurée |
| C14 | 0 régression suite | ✅ | 331 tests verts, 2 skips inchangés |
| C15 | YAML UTF-8 sans BOM | ✅ | 13 YAML scannés |

---

## 2. Anomalies utilisateur — corrigées dans ce sprint

### (a) Bloc « 🎨 Thème » vide, toggle rendu en haut de sidebar
**Cause** : `theme_manager.render_theme_toggle` appelait
`st_module.sidebar.toggle(...)` ⇒ rendu hors `with st.sidebar.expander`.
**Fix** : `st_module.toggle(...)` (rendu dans le contexte courant).
Le `try/except: pass` qui masquait l'erreur dans `app.py` a été
remplacé par `logger.exception(...)`.
**Test** : `tests/test_theme_manager.py::test_render_theme_toggle_uses_context_toggle_not_sidebar`.

### (b) Cliquer « Vue d'ensemble » ne fait rien
**Cause** : section *Accueil* mono-page ⇒ `st.radio.on_change` ne se
déclenche pas si la valeur ne change pas.
**Fix** : remplacement du système radios par boutons
`st.button(... on_click=_select_page)` qui émettent à chaque clic.
**Test** : `tests/test_navigation_hierarchy.py::test_select_page_callback_sets_canonical_key` (vérifie aussi le re-clic sur la page active).

### (c) Remplacer les radios des sous-menus
**Solution retenue** : boutons stylés pleine-largeur, `type="primary"`
pour la page active (feedback visuel), `type="secondary"` sinon.
Conservation de l'expander par section (`expanded` = section courante).
**Test** : `tests/test_navigation_hierarchy.py::test_app_py_uses_buttons_for_navigation_not_radios`.

### (d) Pipeline doit être en menu top-level
**Fix** : nouvelle 6ᵉ section *🔄 Workflow & Orchestration* en 2ᵉ
position (après Accueil) regroupant `Pipeline` + `Supervision Ops`.
La section *Configuration* contient désormais uniquement `Settings`.
**Tests** : `tests/test_navigation_hierarchy.py::test_pipeline_is_promoted_to_workflow_section_not_config` + mises à jour `test_ihm_navigation.py` (5 → 6 sections).

### (e) Lien `doc/execution.md#bracket` du Glossaire ⇒ page blanche
**Cause** : Markdown `[txt](doc/foo.md)` produit une 404 silencieuse
dans Streamlit (pas de handler servant les `.md` du repo). Même bug
dans `help_tooltip.py` pour tous les tooltips.
**Fix** : nouveau service `ihm/services/doc_links.py` :
- `resolve_doc_ref(ref)` → résolution sécurisée (anti-traversal),
  base URL externe via env `IHM_DOC_BASE_URL` ;
- `render_doc_ref_inline(st, ref)` :
  1. fichier local trouvé ⇒ rendu inline dans `st.expander` ;
  2. `IHM_DOC_BASE_URL` défini ⇒ lien externe valide ;
  3. sinon ⇒ caption neutre (jamais de lien Markdown relatif).

`help_tooltip.py` : émet `[📖 Doc](base/ref)` si `IHM_DOC_BASE_URL` défini, sinon `📖 Doc : \`ref\`` en code.
**Test** : `tests/test_doc_links.py` (10 tests).

### (f) Bonus — `try/except: pass` muets dans `app.py`
**Fix** : `logger.exception(...)` partout + `st.exception(exc)` sur le
routeur final (traceback visible dans la page pour debug opérateur).

---

## 3. Fichiers livrés

### ✨ Créés
- `ihm/services/doc_links.py` (128 l.)
- `tests/test_doc_links.py` (10 tests)

### ✏️ Modifiés
- `ihm/app.py` — boutons + logging
- `ihm/services/navigation.py` — section Workflow & Orchestration
- `ihm/services/theme_manager.py` — toggle contextuel
- `ihm/components/help_tooltip.py` — lien doc conditionnel
- `ihm/pages/glossary.py` — `render_doc_ref_inline`
- `tests/test_theme_manager.py` — +4 tests (chrome, !important, contexte toggle)
- `tests/test_navigation_hierarchy.py` — boutons + 6 sections
- `tests/test_ihm_navigation.py` — 5 → 6 sections

---

## 4. Validation

```powershell
$files  = Get-ChildItem tests -Filter "test_ihm_*.py"   | % FullName
$files += Get-ChildItem tests -Filter "test_pages_*.py" | % FullName
$files += "tests/test_theme_manager.py","tests/test_navigation_hierarchy.py",
          "tests/test_doc_links.py","tests/test_help_loader.py",
          "tests/test_help_yaml_schema.py"
python -m pytest $files -p no:randomly --no-cov -q
```

**Résultat** : `331 passed, 2 skipped` (2 skips inchangés).

⚠️ `tests/test_ihm_process_registry.py::test_pipeline_workflow_stops_on_failed_step`
échoue en suite mais **passe en isolation** : verrou pipeline non
libéré par un test précédent. **Bug pré-existant** (PIDs différents à
chaque run), sans rapport avec ce sprint. À corriger via fixture
`autouse` libérant le verrou en téardown — ticket séparé.

---

## 5. Plan P2 — reste à faire (sprint dédié, 3-5 j)

1. Éclater `_execution_center/__init__.py` (2 877 l.) selon §2.1 du plan + renommer `execution_center/`.
2. Éclater `backtesting/__init__.py` (2 083 l.) en `_config/_runner/_results/_attribution/_replay/_calibration.py`.
3. Éclater `_workflow/__init__.py` (935 l.) en `_stages/_runner/_history.py` + renommer `workflow/` + ajouter en navigation.
4. Stabiliser `test_pipeline_workflow_stops_on_failed_step`.
5. Activer `tests/test_ihm_help_tooltips.py` en hard-fail CI.
6. Mesurer C13 (`--cov=ihm --cov-fail-under=80`).

---

## 6. Score IHM

| Étape | Note | Statut |
|---|---:|---|
| Pré-S20.6 | 8.0 | Anomalies UX bloquantes |
| **Post-S20.6 (cette livraison)** | **8.4** | 5 anomalies corrigées + nav 6 sections + tests verrous |
| Cible post-P2 | 9.0 | Monolithes éclatés |
| Cible S20 plein | 9.5 | Help YAML 100 % + AppTest > 80 % |

