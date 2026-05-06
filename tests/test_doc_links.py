"""Sprint S20.6 — Tests de la résolution des références doc (anomalie e).

Vérifie que :
* un ``doc_ref`` pointant vers un fichier markdown réel est résolu en
  chemin absolu et son contenu peut être lu ;
* un ``doc_ref`` invalide / vide ne plante pas ;
* sans ``IHM_DOC_BASE_URL``, ``render_doc_ref_inline`` n'émet PAS de
  lien Markdown relatif (cause de la page blanche initiale).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ihm.services import doc_links
from ihm.services.doc_links import (
    PROJECT_ROOT,
    resolve_doc_ref,
    render_doc_ref_inline,
)


def test_resolve_none_or_empty_returns_none() -> None:
    assert resolve_doc_ref(None) is None
    assert resolve_doc_ref("") is None
    assert resolve_doc_ref("   ") is None
    assert resolve_doc_ref("—") is None


def test_resolve_unknown_file_yields_no_local_content() -> None:
    res = resolve_doc_ref("doc/__definitely_missing__.md#x")
    assert res is not None
    assert res.has_local_content is False
    assert res.anchor == "x"


def test_resolve_existing_doc_file_returns_absolute_path(tmp_path) -> None:
    # On crée un faux doc dans le repo, puis on le supprime à la fin.
    doc_dir = PROJECT_ROOT / "doc"
    doc_dir.mkdir(exist_ok=True)
    fake = doc_dir / "_test_doc_links_fixture.md"
    fake.write_text("# Hello\n\nContenu de test.\n", encoding="utf-8")
    try:
        res = resolve_doc_ref("doc/_test_doc_links_fixture.md#hello")
        assert res is not None
        assert res.has_local_content is True
        assert res.file_path is not None
        assert res.file_path.is_absolute()
        assert res.anchor == "hello"
        assert "Contenu de test" in res.read_markdown()
    finally:
        fake.unlink(missing_ok=True)


def test_resolve_refuses_path_traversal() -> None:
    """Sécurité : un ``doc_ref`` qui sort de PROJECT_ROOT ne doit jamais
    exposer un fichier hors du repo."""
    res = resolve_doc_ref("../../../etc/passwd")
    assert res is not None
    assert res.has_local_content is False


def test_resolve_uses_external_base_url_when_set(monkeypatch) -> None:
    monkeypatch.setenv("IHM_DOC_BASE_URL", "https://example.test/repo/blob/main")
    res = resolve_doc_ref("doc/execution.md#bracket")
    assert res is not None
    assert res.external_url == "https://example.test/repo/blob/main/doc/execution.md#bracket"


# ---------------------------------------------------------------------------
# Render — on vérifie qu'aucun lien Markdown relatif n'est émis sans base URL
# ---------------------------------------------------------------------------


class _FakeStreamlit:
    """Capture minimaliste des appels ``markdown`` / ``caption`` / ``expander``."""

    def __init__(self) -> None:
        self.captions: list[str] = []
        self.markdowns: list[str] = []
        self.expander_titles: list[str] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)

    def expander(self, label: str, expanded: bool = False):
        self.expander_titles.append(label)
        return self  # context manager: __enter__/__exit__

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_render_inline_skips_when_doc_ref_empty() -> None:
    fake = _FakeStreamlit()
    render_doc_ref_inline(fake, None)
    render_doc_ref_inline(fake, "—")
    assert fake.captions == []
    assert fake.markdowns == []


def test_render_inline_uses_expander_for_local_file() -> None:
    doc_dir = PROJECT_ROOT / "doc"
    doc_dir.mkdir(exist_ok=True)
    fake_doc = doc_dir / "_test_render_inline_fixture.md"
    fake_doc.write_text("# Titre\n\nCorps.\n", encoding="utf-8")
    try:
        fake = _FakeStreamlit()
        render_doc_ref_inline(fake, "doc/_test_render_inline_fixture.md")
        assert fake.expander_titles, "Devrait ouvrir un expander pour rendre le markdown"
        assert any("Titre" in m or "Corps" in m for m in fake.markdowns)
    finally:
        fake_doc.unlink(missing_ok=True)


def test_render_inline_does_not_emit_relative_markdown_link(monkeypatch) -> None:
    """Anti-régression anomalie (e) : sans ``IHM_DOC_BASE_URL``, on ne
    doit JAMAIS produire un lien ``[label](doc/foo.md)`` qui ouvre une
    page blanche dans Streamlit."""
    monkeypatch.delenv("IHM_DOC_BASE_URL", raising=False)
    fake = _FakeStreamlit()
    render_doc_ref_inline(fake, "doc/__definitely_missing__.md#x")
    # Aucune caption ne doit contenir un pattern Markdown link relatif.
    for cap in fake.captions:
        assert "](doc/" not in cap, (
            f"Lien Markdown relatif détecté (régression anomalie e) : {cap!r}"
        )


def test_render_inline_uses_external_url_when_base_set(monkeypatch) -> None:
    monkeypatch.setenv("IHM_DOC_BASE_URL", "https://example.test/repo")
    fake = _FakeStreamlit()
    render_doc_ref_inline(fake, "doc/__missing__.md#x")
    assert fake.captions, "Une caption avec lien externe doit être émise"
    assert any("https://example.test/repo" in c for c in fake.captions)

