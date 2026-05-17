"""tests/test_ihm_pipeline_e2e.py — Sprint S6 (A-016).

Tests E2E IHM via ``streamlit.testing.v1.AppTest`` couvrant la page
``ihm/pages/pipeline.py`` et le sous-formulaire ``_build_launch_options``
refactoré.

Objectifs (cf. ``prompt/tod/08_sprint_plan.md`` — Sprint S6) :
    1. Garantir que la page Pipeline se rend sans exception, expander
       « Paramètres d'exécution » exposé.
    2. Garantir que les helpers ``_render_*_block`` extraits du Sprint S6
       existent et sont bien des callables (anti-régression refactor).
    3. Vérifier qu'un appel direct à ``_build_launch_options`` renvoie des
       :class:`PipelineLaunchOptions` aux défauts swing attendus
       (``simulate`` / ``cash`` / ``pdt=off`` / ``swing_only=True``).

Les tests sont marqués ``e2e`` (cf. ``pytest.ini``) pour permettre
``pytest -m "not e2e"`` en mode rapide local.
"""
from __future__ import annotations

import inspect

import pytest

# ``streamlit.testing.v1`` requiert streamlit >= 1.28. Skip propre sinon.
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

from ihm.pages import _execution_center


# ──────────────────────────────────────────────────────────────────────────────
# Anti-régression refactor S6 — structure du module
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_execution_center_exposes_sprint_s6_helpers() -> None:
    """Les helpers ``_render_*_block`` extraits du Sprint S6 doivent exister."""
    expected_callables = (
        # Sprint S6 (livré initial)
        "_render_event_sentiment_block",
        "_render_signal_aggregator_block",
        "_render_live_confirmation_block",
        # Sprint S6.1 (extraction complète des 9 blocs)
        "_render_execution_block",
        "_render_risk_block",
        "_render_model_factory_block",
        "_render_selector_block",
        "_render_screener_block",
        "_render_data_integrity_block",
        "_render_corporate_actions_block",
        # Façade publique
        "_build_launch_options",
    )
    for name in expected_callables:
        assert hasattr(_execution_center, name), f"helper manquant : {name}"
        assert callable(getattr(_execution_center, name)), f"helper non callable : {name}"


@pytest.mark.e2e
def test_execution_center_exposes_launch_options_context_dataclass() -> None:
    """``LaunchOptionsContext`` doit être un dataclass figé exposé publiquement."""
    assert hasattr(_execution_center, "LaunchOptionsContext")
    ctx_cls = _execution_center.LaunchOptionsContext
    assert ctx_cls.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    fields = {f.name for f in ctx_cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    assert {
        "selected_account_id",
        "execution_defaults",
        "selected_capital_preset",
        "capital_preset_key",
    } <= fields


@pytest.mark.e2e
def test_render_live_confirmation_block_returns_true_for_non_live_modes() -> None:
    """``_render_live_confirmation_block`` doit court-circuiter en simulate/paper.

    Ce test n'a pas besoin d'un AppTest car la branche ``execution_mode != "live"``
    retourne immédiatement ``True`` sans toucher à ``st.session_state``.
    """
    assert _execution_center._render_live_confirmation_block("simulate") is True
    assert _execution_center._render_live_confirmation_block("paper") is True


@pytest.mark.e2e
def test_build_launch_options_signature_is_stable() -> None:
    """Façade ``_build_launch_options`` : signature publique inchangée."""
    sig = inspect.signature(_execution_center._build_launch_options)
    assert list(sig.parameters) == [], (
        "La signature de `_build_launch_options` doit rester sans paramètre "
        "pour préserver l'API consommée par ihm/pages/pipeline.py."
    )


@pytest.mark.e2e
def test_render_event_sentiment_block_returns_expected_keys() -> None:
    """Smoke : helper Event Sentiment renvoie le dict attendu sous AppTest."""

    def _runner() -> None:
        import streamlit as st
        import ihm.pages._execution_center as _ec_mod

        # Éviter la connexion DB réelle qui timeout en environnement de test
        _ec_mod._load_contextual_backlog_preview = lambda *_a, **_kw: {"pending_pairs": 0}

        from ihm.pages._execution_center import _render_event_sentiment_block

        result = _render_event_sentiment_block()
        st.session_state["__test_sentiment_news_provider"] = result["sentiment_news_provider"]
        st.session_state["__test_sentiment_scoring_mode"] = result["sentiment_scoring_mode"]
        st.session_state["__test_sentiment_enable_contextual"] = result["sentiment_enable_contextual_scoring"]
        assert set(result) == {
            "sentiment_start_utc",
            "sentiment_end_utc",
            "sentiment_symbols",
            "sentiment_news_provider",
            "sentiment_ticker_relevance_mode",
            "sentiment_min_relevance_score",
            "sentiment_scoring_mode",
            "sentiment_enable_contextual_scoring",
            "sentiment_contextual_min_relevance",
            "sentiment_contextual_max_pairs",
            "sentiment_pending_limit",
            "sentiment_pending_max_batches_per_run",
            "sentiment_feature_flush_every_n_batches",
            "sentiment_finbert_batch_size",
            "backfill_relevance_dry_run",
            "backfill_relevance_rescore_all",
            "backfill_relevance_batch_size",
            "backfill_relevance_purge_below",
        }

    at = AppTest.from_function(_runner).run(timeout=10)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"
    assert at.session_state["__test_sentiment_news_provider"] == "eodhd"
    assert at.session_state["__test_sentiment_scoring_mode"] == "standard_and_contextual"
    assert at.session_state["__test_sentiment_enable_contextual"] is True


@pytest.mark.e2e
def test_render_signal_aggregator_block_returns_expected_keys() -> None:
    """Smoke : helper Signal Aggregator renvoie le dict attendu sous AppTest."""

    def _runner() -> None:
        from ihm.pages._execution_center import _render_signal_aggregator_block

        result = _render_signal_aggregator_block()
        expected_keys = {
            "signal_aggregator_all_symbols",
            "signal_aggregator_log_level",
            "signal_aggregator_sentiment_weight",
            "signal_aggregator_macro_weight",
            "signal_aggregator_lookback_days",
            "signal_aggregator_min_news_count",
            "signal_aggregator_time_decay_half_life_days",
        }
        assert set(result) == expected_keys

    at = AppTest.from_function(_runner).run(timeout=10)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"


@pytest.mark.e2e
def test_contextual_backlog_estimation_is_manual_and_runs_only_after_click() -> None:
    """Le backlog contextuel ne doit plus être estimé au rendu initial."""

    def _runner() -> None:
        import streamlit as st
        import ihm.pages._execution_center as _ec_mod

        def _fake_preview(
            min_relevance: float,
            start_date_iso: str | None = None,
            end_date_iso: str | None = None,
            symbols_csv: str | None = None,
            ingestion_source: str | None = None,
        ) -> dict[str, object]:
            st.session_state["__test_contextual_estimate_calls"] = int(
                st.session_state.get("__test_contextual_estimate_calls", 0)
            ) + 1
            st.session_state["__test_contextual_estimate_args"] = {
                "min_relevance": min_relevance,
                "start_date_iso": start_date_iso,
                "end_date_iso": end_date_iso,
                "symbols_csv": symbols_csv,
                "ingestion_source": ingestion_source,
            }
            return {"pending_pairs": 12}

        _ec_mod._load_contextual_backlog_preview = _fake_preview

        from ihm.pages._execution_center import _render_event_sentiment_block

        _render_event_sentiment_block()

    at = AppTest.from_function(_runner).run(timeout=15)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"
    assert "__test_contextual_estimate_calls" not in at.session_state
    assert len(at.button) == 1

    at.button[0].click().run(timeout=15)

    assert not at.exception, f"Exception après clic : {at.exception}"
    assert at.session_state["__test_contextual_estimate_calls"] == 1
    assert at.session_state["__test_contextual_estimate_args"] == {
        "min_relevance": 0.3,
        "start_date_iso": None,
        "end_date_iso": None,
        "symbols_csv": "",
        "ingestion_source": "eodhd",
    }


@pytest.mark.e2e
def test_render_execution_block_returns_expected_keys() -> None:
    """Smoke S6.1 : helper Execution renvoie le dict attendu sous AppTest."""

    def _runner() -> None:
        import streamlit as st

        from ihm.pages._execution_center import _render_execution_block

        result = _render_execution_block(None, None)
        st.session_state["__test_execution_keys"] = sorted(result.keys())

    at = AppTest.from_function(_runner).run(timeout=20)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"
    keys = set(at.session_state["__test_execution_keys"])
    assert {
        "trade_date",
        "execution_mode",
        "execution_account_type",
        "execution_pdt_rule",
        "execution_swing_only",
        "execution_submission_window",
        "execution_trailing_trigger",
        "execution_debug",
        "selected_capital_preset",
        "capital_preset_key",
    } <= keys


@pytest.mark.e2e
def test_render_model_factory_block_returns_expected_keys() -> None:
    """Smoke S6.1 : helper Model Factory renvoie le dict attendu sous AppTest."""

    def _runner() -> None:
        import streamlit as st

        from ihm.pages._execution_center import _render_model_factory_block

        result = _render_model_factory_block()
        st.session_state["__test_ml_keys"] = sorted(result.keys())

    at = AppTest.from_function(_runner).run(timeout=20)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"
    keys = set(at.session_state["__test_ml_keys"])
    # Quelques clés représentatives (target / WF / candidate grids)
    assert {
        "ml_accelerator",
        "ml_target_mode",
        "ml_walkforward",
        "ml_wf_max_splits",
        "ml_candidate_horizons_selection",
        "ml_min_trades_fraction",
    } <= keys


@pytest.mark.e2e
def test_build_launch_options_returns_default_swing_options_under_apptest() -> None:
    """``_build_launch_options`` doit renvoyer un :class:`PipelineLaunchOptions`
    aux défauts swing attendus en l'absence de toute interaction utilisateur."""

    def _runner() -> None:
        import streamlit as st

        from ihm.pages._execution_center import _build_launch_options

        options, live_confirmed = _build_launch_options()
        # Stockage dans st.session_state pour récupération hors AppTest.
        st.session_state["__test_options_execution_mode"] = options.execution_mode
        st.session_state["__test_options_account_type"] = options.execution_account_type
        st.session_state["__test_options_pdt_rule"] = options.execution_pdt_rule
        st.session_state["__test_options_swing_only"] = bool(options.execution_swing_only)
        st.session_state["__test_options_sentiment_news_provider"] = options.sentiment_news_provider
        st.session_state["__test_options_fundamentals_provider"] = options.data_integrity_fundamentals_provider
        st.session_state["__test_options_fundamentals_overwrite"] = bool(options.data_integrity_fundamentals_overwrite_existing)
        st.session_state["__test_live_confirmed"] = bool(live_confirmed)

    at = AppTest.from_function(_runner).run(timeout=20)
    assert not at.exception, f"Exception remontée par AppTest : {at.exception}"

    # Défauts swing cash conformes à l'audit IHM (cf. doc IHM + S2).
    assert at.session_state["__test_options_execution_mode"] == "simulate"
    assert at.session_state["__test_options_account_type"] == "cash"
    assert at.session_state["__test_options_pdt_rule"] == "off"
    assert at.session_state["__test_options_swing_only"] is True
    assert at.session_state["__test_options_sentiment_news_provider"] == "eodhd"
    assert at.session_state["__test_options_fundamentals_provider"] == "yahoo_finance"
    assert at.session_state["__test_options_fundamentals_overwrite"] is False
    # Live confirmation court-circuit en non-live ⇒ True.
    assert at.session_state["__test_live_confirmed"] is True


