"""Tests pour la quarantaine champion (Phase 4.2.e)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modelFactory.champion_selection import is_under_quarantine, select_champion
from modelFactory.config import ChampionSelectionConfig


def test_quarantine_disabled_when_thresholds_zero() -> None:
    quarantined, reason = is_under_quarantine(
        "lstm_attention",
        "AAPL",
        min_runs=0,
        min_days=0,
        lookup=lambda s, m: (0, None),
    )
    assert not quarantined and reason == ""


def test_quarantine_blocks_when_runs_below_min() -> None:
    quarantined, reason = is_under_quarantine(
        "lightgbm",
        "AAPL",
        min_runs=3,
        min_days=0,
        lookup=lambda s, m: (1, None),
    )
    assert quarantined is True
    assert "runs<3" in reason


def test_quarantine_releases_when_runs_reached() -> None:
    quarantined, _ = is_under_quarantine(
        "lightgbm",
        "AAPL",
        min_runs=3,
        min_days=0,
        lookup=lambda s, m: (5, datetime.now(timezone.utc) - timedelta(days=10)),
    )
    assert quarantined is False


def test_quarantine_blocks_when_days_below_min() -> None:
    now = datetime(2026, 4, 27, tzinfo=timezone.utc)
    first_completed = now - timedelta(days=2)
    quarantined, reason = is_under_quarantine(
        "catboost",
        "AAPL",
        min_runs=0,
        min_days=7,
        lookup=lambda s, m: (10, first_completed),
        now=now,
    )
    assert quarantined is True
    assert "days<7" in reason


def test_quarantine_releases_after_days_threshold() -> None:
    now = datetime(2026, 4, 27, tzinfo=timezone.utc)
    first_completed = now - timedelta(days=14)
    quarantined, _ = is_under_quarantine(
        "catboost",
        "AAPL",
        min_runs=0,
        min_days=7,
        lookup=lambda s, m: (10, first_completed),
        now=now,
    )
    assert quarantined is False


def test_select_champion_excludes_quarantined_and_falls_back_to_default() -> None:
    challengers = {
        "lstm_attention": {"status": "completed", "selection_score": 0.7, "selection_eligible": True},
        "lightgbm": {"status": "completed", "selection_score": 0.9, "selection_eligible": True},
    }
    artifact_routes = {
        "lstm_attention": {"checkpoint_path": "x"},
        "lightgbm": {"model_path": "y"},
    }
    cfg = ChampionSelectionConfig(
        enabled=True,
        allow_auto_selection=True,
        default_champion="lstm_attention",
        min_runs=5,
        min_days=0,
    )
    # lightgbm = nouveau (1 run), lstm_attention = établi (10 runs)
    def _lookup(symbol, model_name):
        return (10 if model_name == "lstm_attention" else 1, None)

    result = select_champion(
        challengers, artifact_routes, cfg,
        quarantine_lookup=_lookup, symbol="AAPL",
    )
    assert result["selected_model"] == "lstm_attention"
    annotated = result["annotated_challengers"]
    assert annotated["lightgbm"]["quarantined"] is True
    assert "runs<5" in annotated["lightgbm"]["quarantine_reason"]
    assert annotated["lstm_attention"].get("quarantined") in (False, None)


def test_chamionselectionconfig_rejects_negative_thresholds() -> None:
    with pytest.raises(ValueError, match="min_runs"):
        ChampionSelectionConfig(min_runs=-1)
    with pytest.raises(ValueError, match="min_days"):
        ChampionSelectionConfig(min_days=-1)


def test_select_champion_marks_zero_eligible_models_explicitly() -> None:
    challengers = {
        "lstm_attention": {"status": "completed", "selection_score": 0.7, "selection_eligible": False},
        "lightgbm": {"status": "failed", "selection_score": 0.9, "selection_eligible": False},
    }
    artifact_routes = {
        "lstm_attention": {"checkpoint_path": "x"},
        "lightgbm": {"model_path": "y"},
    }
    cfg = ChampionSelectionConfig(
        enabled=True,
        allow_auto_selection=True,
        default_champion="lstm_attention",
    )

    result = select_champion(challengers, artifact_routes, cfg)

    assert result["selected_model"] == "lstm_attention"
    assert result["selection_mode"] == "fallback_default_champion"
    assert result["selection_reason"] == "zero_eligible_models"
    assert result["selected_model_eligible"] is False


