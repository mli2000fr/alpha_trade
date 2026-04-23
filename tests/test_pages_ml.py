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


