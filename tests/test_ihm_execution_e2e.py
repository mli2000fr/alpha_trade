"""tests/test_ihm_execution_e2e.py — Sprint S6 (A-016).

Tests E2E IHM via ``streamlit.testing.v1.AppTest`` couvrant la page
``ihm/pages/execution.py``.

Objectifs (cf. ``prompt/tod/08_sprint_plan.md`` — Sprint S6) :
    1. Garantir que la page Execution Engine se rend sans exception lorsque
       la DB est indisponible (chemin ``render_db_unavailable``).
    2. Garantir que la page se rend sans exception et expose la sélection
       de run + KPI lorsqu'au moins un run d'exécution est présent en base
       (mocks DB).

Les tests sont marqués ``e2e`` (cf. ``pytest.ini``) pour permettre
``pytest -m "not e2e"`` en mode rapide local.

Note implémentation : ``AppTest.from_function`` exécute la fonction dans
un contexte isolé (script dédié) qui ne capte pas les closures pytest. On
applique donc les patches directement dans le runner via
``monkeypatch.setattr`` au niveau module *à l'intérieur* du runner.
"""
from __future__ import annotations

import pytest

# ``streamlit.testing.v1`` requiert streamlit >= 1.28. Skip propre sinon.
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import execution as execution_page


# ──────────────────────────────────────────────────────────────────────────────
# E2E AppTest — page Execution Engine
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_execution_page_handles_db_unavailable_gracefully() -> None:
    """DB indisponible ⇒ render_db_unavailable, pas d'exception."""

    def _runner() -> None:
        from ihm.pages import execution as execution_page

        # Force DB indisponible.
        execution_page.db_available = lambda: False  # type: ignore[assignment]
        execution_page.render()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"


@pytest.mark.e2e
def test_execution_page_renders_run_selectbox_and_kpis() -> None:
    """Branche heureuse : 1 run présent ⇒ selectbox + KPI rendus sans exception."""

    def _runner() -> None:
        import pandas as pd

        from ihm.pages import execution as execution_page

        runs_df = pd.DataFrame(
            [
                {
                    "exec_run_id": "exec-test-001",
                    "status": "completed",
                    "total_targets": 3,
                    "total_submitted": 3,
                    "total_filled": 2,
                    "submission_window": "post_close",
                    "execution_account_id": "paper-test",
                    "started_at": pd.Timestamp("2026-05-05 16:00:00"),
                    "completed_at": pd.Timestamp("2026-05-05 16:05:00"),
                }
            ]
        )

        execution_page.db_available = lambda: True  # type: ignore[assignment]
        execution_page.get_execution_runs = lambda **_: runs_df  # type: ignore[assignment]
        execution_page.get_latest_run_business_summary = lambda **_: None  # type: ignore[assignment]
        execution_page.get_latest_execution_protection_watch_service_summary = lambda **_: None  # type: ignore[assignment]

        execution_page.render()

    at = AppTest.from_function(_runner).run(timeout=20)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"
    # Au moins un selectbox doit être rendu (« Run d'exécution »).
    assert len(at.selectbox) >= 1, "selectbox `Run d'exécution` attendu"


@pytest.mark.e2e
def test_execution_page_render_function_exists() -> None:
    """Anti-régression : la page Execution doit exposer ``render()``."""
    assert hasattr(execution_page, "render")
    assert callable(execution_page.render)



