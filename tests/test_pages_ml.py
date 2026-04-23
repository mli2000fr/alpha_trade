import pandas as pd

from ihm.pages import ml

def test_pages_ml_importable():
    assert hasattr(ml, "__doc__")


def test_summarize_prediction_governance_audit_counts_mismatches() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "served_model": "lightgbm",
                "governance_champion_model": "lightgbm",
                "governance_link_status": "aligned",
            },
            {
                "served_model": "catboost",
                "governance_champion_model": "lightgbm",
                "governance_link_status": "served_model_differs_from_governance_champion",
            },
        ]
    )

    summary = ml._summarize_prediction_governance_audit(audit_df)

    assert summary["latest_served_model"] == "lightgbm"
    assert summary["latest_governance_champion"] == "lightgbm"
    assert summary["latest_link_status"] == "aligned"
    assert summary["mismatch_count"] == 1


def test_build_prediction_audit_filter_options_merges_audit_and_governance_sources() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "run_id": "run-2",
                "served_model": "lightgbm",
                "governance_selection_mode": "auto_selected_champion",
                "governance_link_status": "aligned",
            },
            {
                "run_id": "run-1",
                "served_model": "catboost",
                "governance_selection_mode": "fallback_default_champion",
                "governance_link_status": "served_model_differs_from_governance_champion",
            },
        ]
    )
    governance_df = pd.DataFrame(
        [
            {"run_id": "run-3", "selection_mode": "default_champion"},
            {"run_id": "run-2", "selection_mode": "auto_selected_champion"},
        ]
    )

    options = ml._build_prediction_audit_filter_options(audit_df, governance_df)

    assert options["governance_link_statuses"] == [
        "aligned",
        "served_model_differs_from_governance_champion",
    ]
    assert options["selection_modes"] == [
        "auto_selected_champion",
        "default_champion",
        "fallback_default_champion",
    ]
    assert options["served_models"] == ["catboost", "lightgbm"]
    assert options["run_ids"] == ["run-3", "run-2", "run-1"]


