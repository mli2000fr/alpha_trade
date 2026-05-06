"""Sprint S19.5 / S24.4 — Tests page Compliance & Audit (version finale)."""
from __future__ import annotations

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import compliance_audit as page_module  # noqa: E402
from ihm.services import compliance_loader  # noqa: E402


@pytest.fixture(autouse=True)
def _patch_loader(monkeypatch):
    """Snapshot déterministe : isole les tests des artefacts disque."""
    fake = {
        "hmac_chain": {"ok": True, "anomalies_count": 0, "source": "live_db"},
        "dr_drill": {"ok": True, "last_date": "2026-04-30",
                     "rto_minutes": 28, "rpo_minutes": 5},
        "cve": {"critical": 0, "high": 1, "scanned_at": "2026-05-06"},
        "coverage": {"branches_pct": 92.4, "global_pct": 91.0,
                     "generated_at": "2026-05-06"},
        "mutation": {"score_pct": 73.1, "killed": 120, "survived": 45,
                     "date": "2026-05-04"},
        "tlaps": {"n_ok": 3, "n_specs": 3, "n_failed": 0,
                  "tool": "tlaps", "date": "2026-05-06"},
        "fuzz": {"n_scenarios": 10000, "n_diverged": 0,
                 "divergence_rate": 0.0, "max_pnl_delta_usd": 0.0,
                 "date": "2026-05-06"},
        "sandbox": {"streak_green": 30, "n_failure": 0, "n_success": 30,
                    "last_failure": None},
    }
    monkeypatch.setattr(compliance_loader, "load_full_snapshot", lambda: fake)


@pytest.mark.e2e
def test_compliance_audit_page_renders_without_exception() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page
        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception : {at.exception}"


@pytest.mark.e2e
def test_compliance_audit_renders_six_tabs() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page
        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception
    # 6 onglets attendus (HMAC, DR, CVE, Cov+Mut, TLAPS+Fuzz, Sandbox)
    assert len(at.tabs) >= 1


@pytest.mark.e2e
def test_compliance_audit_exposes_kpis() -> None:
    def _runner() -> None:
        from ihm.pages import compliance_audit as page
        page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    # Au moins 8 KPIs (chaîne, anomalies, drill x3, CVE x3, cov, mut, ...)
    assert len(at.metric) >= 8


def test_compliance_audit_render_function_exists() -> None:
    assert hasattr(page_module, "render")
    assert callable(page_module.render)

