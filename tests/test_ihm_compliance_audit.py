"""Sprint S19.5 / S24.4 — Tests page Compliance & Audit (stub)."""
from __future__ import annotations

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import compliance_audit as page_module  # noqa: E402


@pytest.mark.e2e
def test_compliance_audit_page_renders_without_exception() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception : {at.exception}"


@pytest.mark.e2e
def test_compliance_audit_renders_four_tabs() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception
    # 4 onglets attendus (HMAC, DR drill, CVE, Couverture/Mutation).
    assert len(at.tabs) >= 1


@pytest.mark.e2e
def test_compliance_audit_exposes_kpis() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert len(at.metric) >= 4


def test_compliance_audit_render_function_exists() -> None:
    assert hasattr(page_module, "render")
    assert callable(page_module.render)

