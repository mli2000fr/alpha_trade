"""Sprint S25.5 — Tests INDEX + dead links."""
from __future__ import annotations

from pathlib import Path

from scripts.check_doc_links import find_dead_links
from scripts.generate_doc_index import INDEX_PATH, _category, _read_meta, generate


def test_no_dead_links_in_doc() -> None:
    dead = find_dead_links()
    assert not dead, (
        f"{len(dead)} lien(s) mort(s) détecté(s) dans doc/ :\n  ! "
        + "\n  ! ".join(f"{d['source']} -> {d['target']}" for d in dead)
    )


def test_doc_index_is_up_to_date() -> None:
    """`doc/INDEX.md` doit être à jour (re-run script si modifs doc/)."""
    import re

    expected = generate()
    assert INDEX_PATH.exists(), "doc/INDEX.md absent — lancer `python scripts/generate_doc_index.py`"
    actual = INDEX_PATH.read_text("utf-8")

    def _strip(s: str) -> str:
        return re.sub(r"le \d{4}-\d{2}-\d{2}", "le YYYY-MM-DD", s)

    assert _strip(expected) == _strip(actual), (
        "doc/INDEX.md out-of-date — lancer "
        "`python scripts/generate_doc_index.py` puis commit."
    )


def test_doc_index_category_classifies_s7_central_documents() -> None:
    doc_root = INDEX_PATH.parent

    assert _category(doc_root / "CONVENTIONS.md") == "Documentation centrale"
    assert _category(doc_root / "CHANGELOG.md") == "Documentation centrale"
    assert _category(doc_root / "DOC_FONCTIONNELLE.md") == "Documentation centrale"
    assert _category(doc_root / "DOC_TECHNIQUE.md") == "Documentation centrale"


def test_read_meta_ignores_fenced_code_blocks_when_extracting_h1_and_description(tmp_path: Path) -> None:
    sample = tmp_path / "sample.md"
    sample.write_text(
        """
# Vrai titre

Description opérateur visible.

```powershell
# Faux titre dans un bloc de code
python -m demo
```
""".strip(),
        encoding="utf-8",
    )

    title, desc = _read_meta(sample)

    assert title == "Vrai titre"
    assert desc == "Description opérateur visible."


