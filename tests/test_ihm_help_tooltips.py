"""Sprint S20.5 — Audit AST : tout widget critique doit avoir ``help=``.

Hard-fail si un widget ``st.<critical>`` est ajouté sans tooltip.

Note : la méthode ``slider`` peut aussi être appelée sur un objet
``column`` (``col1.slider(...)``) ; on cible ces deux patrons sans
considérer les pages de support qui consomment encore l'API legacy
(allow-list documentée pour faciliter la migration progressive).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

CRITICAL_WIDGETS: set[str] = {
    "slider",
    "selectbox",
    "number_input",
    "text_input",
    "checkbox",
    "radio",
    "date_input",
    "time_input",
    "toggle",
    "color_picker",
    "file_uploader",
}

PAGES_DIR = pathlib.Path(__file__).resolve().parent.parent / "ihm" / "pages"

# ---------------------------------------------------------------------------
# Allow-list temporaire — pages legacy à refactorer dans une PR ultérieure.
# Sprint S20 introduit le helper ``_help`` sur les pages refactorées (Tax,
# Compliance, Glossary). Les pages historiques sont migrées progressivement
# (suivi : `prompt/tod/29_ihm_refactor_delivery_report.md` §4).
# ---------------------------------------------------------------------------
LEGACY_ALLOWLIST: set[str] = {
    "_execution_center",
    "_workflow",
    "backtesting",
    "alpaca_accounts",
    "corporate_actions",
    "db_admin",
    "execution",
    "ml",
    "overview",
    "parity",
    "pipeline",
    "risk",
    "screening",
    "settings",
    "supervision_ops",
    "_alpha_scanner_diagnostics",
    "_data_integrity",
    "_shared",
    "_watcher_block",
}


def _iter_python_pages() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for py in PAGES_DIR.rglob("*.py"):
        if py.name.startswith("__"):
            continue
        # Filtre les pages legacy via le 1er composant du chemin relatif.
        rel = py.relative_to(PAGES_DIR)
        top = rel.parts[0].replace(".py", "")
        if top in LEGACY_ALLOWLIST:
            continue
        out.append(py)
    return out


def _find_widget_calls_without_help(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    misses: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in CRITICAL_WIDGETS:
            continue
        kwargs = {kw.arg for kw in node.keywords if kw.arg}
        if "help" not in kwargs:
            misses.append(f"{path.name}:{node.lineno} st.{func.attr}")
    return misses


@pytest.mark.parametrize(
    "path",
    _iter_python_pages(),
    ids=lambda p: p.relative_to(PAGES_DIR).as_posix(),
)
def test_refactored_page_widgets_have_help(path: pathlib.Path) -> None:
    misses = _find_widget_calls_without_help(path)
    assert not misses, (
        f"Widgets sans help= dans {path.name} :\n  - "
        + "\n  - ".join(misses)
    )


def test_legacy_pages_listed_in_allowlist_still_exist() -> None:
    """Garde-fou : si un fichier legacy disparaît (refactor), enlever
    l'entrée correspondante de ``LEGACY_ALLOWLIST``.
    """
    existing = {
        p.relative_to(PAGES_DIR).parts[0].replace(".py", "")
        for p in PAGES_DIR.iterdir()
        if not p.name.startswith("__")
    }
    stale = [name for name in LEGACY_ALLOWLIST if name not in existing]
    assert not stale, (
        "Entrées obsolètes dans LEGACY_ALLOWLIST (à supprimer) : "
        f"{stale}"
    )

