"""Sprint S19.4 — Tests page Tax Compliance (AppTest E2E)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import tax_compliance as tax_page  # noqa: E402
from ihm.services import tax_data  # noqa: E402
from tax.wash_sale import Lot  # noqa: E402


@pytest.mark.e2e
def test_tax_compliance_page_renders_without_exception() -> None:
    def _runner() -> None:
        from ihm.pages import tax_compliance as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception : {at.exception}"


@pytest.mark.e2e
def test_tax_compliance_renders_kpis() -> None:
    def _runner() -> None:
        from ihm.pages import tax_compliance as page

        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception
    # 3 KPI principaux : lots / wash sales / disallowed.
    assert len(at.metric) >= 3


def test_tax_compliance_render_function_exists() -> None:
    assert hasattr(tax_page, "render")
    assert callable(tax_page.render)


def test_compute_report_detects_wash_sale_on_demo_lots() -> None:
    today = date.today()
    lots = [
        Lot("a", "AAPL", today - timedelta(days=40), 100, 180.0),
        Lot("b", "AAPL", today - timedelta(days=20), -50, 170.0),  # vente perte
        Lot("c", "AAPL", today - timedelta(days=10), 50, 175.0),   # remplacement
    ]
    report = tax_data.compute_report(lots)
    assert len(report.adjustments) == 1
    assert report.total_disallowed_loss > 0


def test_filter_lots_respects_symbol_and_dates() -> None:
    today = date.today()
    lots = [
        Lot("a", "AAPL", today - timedelta(days=40), 10, 1.0),
        Lot("b", "MSFT", today - timedelta(days=10), 10, 1.0),
    ]
    filtered = tax_data.filter_lots(
        lots, symbol="AAPL", date_from=today - timedelta(days=60)
    )
    assert [l.lot_id for l in filtered] == ["a"]

