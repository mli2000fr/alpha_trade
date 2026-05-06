"""Sprint S25.5 — Tests INDEX + dead links."""
from __future__ import annotations

from scripts.check_doc_links import find_dead_links
from scripts.generate_doc_index import INDEX_PATH, generate


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

