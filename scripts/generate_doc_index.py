"""Sprint S25.5 — Génère ``doc/INDEX.md`` cherchable.

Scanne ``doc/**/*.md``, extrait le titre H1 + première ligne descriptive,
puis génère un index Markdown trié par catégorie heuristique.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = PROJECT_ROOT / "doc"
INDEX_PATH = DOC_DIR / "INDEX.md"

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _category(path: Path) -> str:
    name = path.name.lower()
    parts = path.relative_to(DOC_DIR).parts
    if name in {"conventions.md", "changelog.md", "doc_fonctionnelle.md", "doc_technique.md"}:
        return "Documentation centrale"
    if "architecture" in parts:
        return "Architecture"
    if name.startswith("runbook"):
        return "Runbooks & Ops"
    if "audit" in name or "compliance" in name or "wash_sale" in name:
        return "Conformité & Audit"
    if "test" in name or "mutation" in name or "fuzz" in name or "formal" in name:
        return "Tests & Vérification"
    if "api" in name or "deprecation" in name:
        return "API & Stabilité"
    if "onboarding" in name or "guide" in name or name.startswith("doc_"):
        return "Documentation utilisateur"
    if "perf" in name or "async" in name:
        return "Performance"
    if (path.relative_to(DOC_DIR).parts[0] == "external_audit"
            if path.relative_to(DOC_DIR).parts else False):
        return "Audit externe"
    return "Divers"


def _sanitize_markdown_for_meta_extraction(text: str) -> str:
    sanitized = text.lstrip("\ufeff")
    sanitized = _FENCED_CODE_BLOCK_RE.sub("", sanitized)
    sanitized = _HTML_COMMENT_RE.sub("", sanitized)
    return sanitized


def _escape_markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").split())


def _read_meta(path: Path) -> tuple[str, str]:
    try:
        text = _sanitize_markdown_for_meta_extraction(path.read_text("utf-8"))
    except Exception:
        return path.stem, ""
    h1 = _H1_RE.search(text)
    title = h1.group(1).strip() if h1 else path.stem
    # Première ligne non vide après le titre.
    lines = text.splitlines()
    desc = ""
    after_h1 = False
    for line in lines:
        if line.startswith("# "):
            after_h1 = True
            continue
        if after_h1:
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", ">", "*", "-", "|")):
                desc = stripped
                break
            if stripped.startswith("> "):
                desc = stripped[2:]
                break
    return title, desc


def generate() -> str:
    files = sorted(p for p in DOC_DIR.rglob("*.md") if p.name != "INDEX.md")
    by_cat: dict[str, list[tuple[str, Path, str]]] = {}
    for f in files:
        title, desc = _read_meta(f)
        cat = _category(f)
        by_cat.setdefault(cat, []).append((title, f, desc))

    out = [
        "# Index de la documentation Alpha Trade",
        "",
        f"> Généré automatiquement par "
        f"`scripts/generate_doc_index.py` le "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
        f"> {len(files)} documents indexés.",
        "",
        "## Sommaire",
        "",
    ]
    for cat in sorted(by_cat):
        anchor = cat.lower().replace(" & ", "-").replace(" ", "-")
        out.append(f"* [{cat}](#{anchor}) ({len(by_cat[cat])})")
    out.append("")

    for cat in sorted(by_cat):
        out.append(f"## {cat}")
        out.append("")
        out.append("| Document | Titre | Description |")
        out.append("|---|---|---|")
        for title, path, desc in sorted(by_cat[cat], key=lambda x: x[1].name):
            rel = path.relative_to(DOC_DIR).as_posix()
            escaped_title = _escape_markdown_table_cell(title)
            short_desc = _escape_markdown_table_cell((desc or "—")[:140])
            out.append(f"| [`{rel}`]({rel}) | {escaped_title} | {short_desc} |")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Génère doc/INDEX.md.")
    p.add_argument("--check", action="store_true",
                   help="Exit 1 si l'index est out-of-date (CI guard).")
    args = p.parse_args(argv)

    new_content = generate()
    if args.check:
        existing = INDEX_PATH.read_text("utf-8") if INDEX_PATH.exists() else ""
        # Ignore la ligne « Généré ... le YYYY-MM-DD » (volatile).
        def _strip_date(s: str) -> str:
            return re.sub(r"le \d{4}-\d{2}-\d{2}", "le YYYY-MM-DD", s)
        if _strip_date(existing) != _strip_date(new_content):
            print("[doc_index] OUT-OF-DATE — re-run "
                  "`python scripts/generate_doc_index.py`.")
            return 1
        print("[doc_index] up-to-date.")
        return 0

    INDEX_PATH.write_text(new_content, "utf-8")
    print(f"[doc_index] -> {INDEX_PATH}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

