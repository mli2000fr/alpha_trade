"""Sprint S20.4 — Tests page Glossaire."""
from __future__ import annotations

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import glossary as glossary_page  # noqa: E402
from ihm.services import help_loader  # noqa: E402


@pytest.mark.e2e
def test_glossary_page_renders_without_exception() -> None:
    def _runner() -> None:
        from ihm.pages import glossary as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception : {at.exception}"


@pytest.mark.e2e
def test_glossary_page_exposes_search_input() -> None:
    def _runner() -> None:
        from ihm.pages import glossary as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert len(at.text_input) >= 1


def test_glossary_yaml_contains_required_terms() -> None:
    help_loader.reset_cache()
    entries = help_loader.load_help("glossary")
    required = {"ATR", "OCO", "wash_sale", "drift", "drawdown"}
    missing = required - entries.keys()
    assert not missing, f"Termes manquants dans glossary.yaml : {missing}"


def test_glossary_render_function_exists() -> None:
    assert hasattr(glossary_page, "render")
    assert callable(glossary_page.render)

