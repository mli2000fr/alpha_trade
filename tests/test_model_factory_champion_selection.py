"""Tests pour la quarantaine champion (Phase 4.2.e)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modelFactory.champion_selection import (
    directional_selection_evidence,
    is_under_quarantine,
    select_champion,
    selection_score_from_result,
)
from modelFactory.config import ChampionSelectionConfig
from modelFactory.trainer import effective_champion_selection_metric


def _directional_result(*, long_values: list[float], short_values: list[float], macro: float) -> dict:
    return {
        "status": "completed",
        "val": {"f1_macro": macro, "f1_long": 0.99, "f1_short": 0.99},
        "test": {"f1_macro": 0.99, "f1_long": 0.99, "f1_short": 0.99},
        "walk_forward": {
            "mean": {"f1_macro": macro},
            "splits": [
                {
                    "test_rows": 100,
                    "true_long_pct": 30.0,
                    "true_short_pct": 30.0,
                    "f1_long": long_value,
                    "f1_short": short_value,
                }
                for long_value, short_value in zip(long_values, short_values, strict=True)
            ],
        },
    }


def _tabular_routes() -> dict[str, dict[str, str]]:
    return {
        "lightgbm": {
            "inference_backend": "lightgbm_tabular",
            "config_path": "config.json",
            "model_path": "lightgbm.pkl",
        },
        "catboost": {
            "inference_backend": "catboost_tabular",
            "config_path": "config.json",
            "model_path": "catboost.pkl",
        },
        "lstm_attention": {
            "inference_backend": "lstm_attention",
            "checkpoint_path": "best.ckpt",
            "scaler_path": "scaler.pkl",
        },
    }


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


def test_selection_score_ignores_noncanonical_selection_score_fields() -> None:
    result = {
        "status": "completed",
        "selection_score": 0.99,
        "test": {"selection_score": 0.98},
        "val": {"selection_score": 0.61},
    }

    assert selection_score_from_result(result) == float("-inf")


def test_selection_score_without_authorized_partition_is_ineligible() -> None:
    result = {"status": "completed", "selection_score": 0.99, "test": {"selection_score": 0.98}}

    assert selection_score_from_result(result) == float("-inf")


def test_select_champion_requires_valid_benchmark_report_when_enabled() -> None:
    challengers = {
        "catboost": {
            "status": "completed",
            "val": {"selection_score": 0.8},
        },
    }
    routes = {
        "catboost": {
            "inference_backend": "catboost_tabular",
            "config_path": "config.json",
            "model_path": "catboost.pkl",
        },
    }
    cfg = ChampionSelectionConfig(
        enabled=True,
        allow_auto_selection=True,
        default_champion="catboost",
        require_benchmark_report=True,
    )

    result = select_champion(challengers, routes, cfg)

    assert result["selection_mode"] == "fallback_default_champion"
    assert result["annotated_challengers"]["catboost"]["eligibility_reason"] == "missing_valid_benchmark_report"


def test_directional_score_uses_supported_walk_forward_folds_only() -> None:
    result = _directional_result(
        long_values=[0.20, 0.50, 0.60, 0.90],
        short_values=[0.30, 0.30, 0.30, 0.30],
        macro=0.10,
    )
    # Le dernier fold existe, mais son support LONG est rendu insuffisant.
    result["walk_forward"]["splits"][-1]["true_long_pct"] = 5.0

    evidence = directional_selection_evidence(result, "f1_long")

    assert evidence["valid_folds"] == 3
    assert evidence["f1_median"] == pytest.approx(0.50)
    assert selection_score_from_result(result, "f1_long") == pytest.approx(0.50)


def test_directional_score_rejects_fewer_than_three_valid_folds() -> None:
    result = _directional_result(
        long_values=[0.80, 0.70],
        short_values=[0.20, 0.20],
        macro=0.90,
    )

    evidence = directional_selection_evidence(result, "f1_long")

    assert evidence["eligible"] is False
    assert selection_score_from_result(result, "f1_long") == float("-inf")


def test_long_role_selects_best_long_champion_and_rejects_missing_folds() -> None:
    challengers = {
        "lightgbm": _directional_result(
            long_values=[0.52, 0.55, 0.50], short_values=[0.20, 0.20, 0.20], macro=0.30,
        ),
        "catboost": _directional_result(
            long_values=[0.38, 0.40, 0.39], short_values=[0.70, 0.70, 0.70], macro=0.60,
        ),
        "lstm_attention": {
            "status": "completed",
            "val": {"f1_macro": 0.95, "f1_long": 0.95},
            "test": {"f1_macro": 0.95, "f1_long": 0.95},
        },
    }
    cfg = ChampionSelectionConfig(
        enabled=True,
        allow_auto_selection=True,
        default_champion="lstm_attention",
    )

    result = select_champion(
        challengers,
        _tabular_routes(),
        cfg,
        selection_metric_override="f1_long",
    )

    assert result["selected_model"] == "lightgbm"
    assert result["selection_metric"] == "f1_long"
    assert result["selection_score"] == pytest.approx(0.52)
    assert result["annotated_challengers"]["lstm_attention"]["selection_eligible"] is False
    assert "directional_valid_folds<3" in result["annotated_challengers"]["lstm_attention"]["eligibility_reason"]


def test_short_role_selects_best_short_champion() -> None:
    challengers = {
        "lightgbm": _directional_result(
            long_values=[0.70, 0.70, 0.70], short_values=[0.35, 0.36, 0.34], macro=0.65,
        ),
        "catboost": _directional_result(
            long_values=[0.20, 0.20, 0.20], short_values=[0.58, 0.55, 0.60], macro=0.35,
        ),
    }
    cfg = ChampionSelectionConfig(enabled=True, allow_auto_selection=True, default_champion="lightgbm")

    result = select_champion(
        challengers,
        _tabular_routes(),
        cfg,
        selection_metric_override="f1_short",
    )

    assert result["selected_model"] == "catboost"
    assert result["selection_score"] == pytest.approx(0.58)


def test_effective_champion_metric_is_role_specific_without_changing_legacy() -> None:
    assert effective_champion_selection_metric("direction_long", "selection_score") == "f1_long"
    assert effective_champion_selection_metric("direction_short", "selection_score") == "f1_short"
    assert effective_champion_selection_metric("direction_legacy", "selection_score") == "selection_score"


