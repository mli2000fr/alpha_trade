import pytest

from modelFactory.fr_fold3_repair_audit import audit_bounds, window_blockers


def test_audit_fold_and_phase_are_explicit():
    folds = [{"fold": 3}, {"fold": 7}]
    assert audit_bounds(folds, 7, "test") == {"fold": 7}
    with pytest.raises(ValueError):
        audit_bounds(folds, 9, "test")
    with pytest.raises(ValueError):
        audit_bounds(folds, 7, "unknown")


def test_window_preserves_missing_documentary_proof():
    proofs = {
        ("A", "2021-01-04"): {
            "research_j1_eligible": False,
            "research_rejection_reasons": ["MISSING_DELTA_PUBLICATION_DAY"],
        }
    }
    before = repr(proofs)
    assert window_blockers(proofs, "A", ["2021-01-04"]) == [
        {"date": "2021-01-04", "reasons": ["MISSING_DELTA_PUBLICATION_DAY"]}
    ]
    assert repr(proofs) == before


def test_unknown_bar_is_not_assumed_admitted():
    assert window_blockers({}, "A", ["2021-01-04"]) == [{"date": "2021-01-04", "reasons": ["MANIFEST_ROW_MISSING"]}]


def test_only_requested_symbol_and_window_used():
    proofs = {
        ("A", "2021-01-04"): {"research_j1_eligible": True},
        ("B", "2021-01-04"): {"research_j1_eligible": False, "research_rejection_reasons": ["UNKNOWN_IDENTITY"]},
    }
    assert window_blockers(proofs, "A", ["2021-01-04"]) == []
    assert window_blockers(proofs, "B", []) == []
