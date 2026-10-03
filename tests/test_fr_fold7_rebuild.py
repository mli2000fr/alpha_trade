import copy

import pytest

from modelFactory.fr_fold7_rebuild import REASON, overlay_row


def sample(extra=()):
    return {"isin": "FR_TEST", "mic": "XPAR", "research_rejection_reasons": [REASON, *extra],
            "strict_rejection_reasons": [REASON, "HISTORICAL_PIT_PROOF_MISSING", *extra],
            "price_proof_sources": ["NONE"], "historical_pit_verified": False,
            "corporate_action_verified": False, "economic_return_ready": False,
            "canonical_strict_eligible": False, "price_verified_official": False,
            "research_j1_eligible": False, "decision": "REJECTED"}


def test_research_only_no_mutation():
    original = sample()
    before = copy.deepcopy(original)
    result = overlay_row(original, {"isin": "FR_TEST", "mics": ["XPAR"]})
    assert original == before
    assert result["research_j1_eligible"] is True
    assert result["canonical_strict_eligible"] is False
    assert result["historical_pit_verified"] is False
    assert result["price_verified_official"] is False
    assert result["strict_rejection_reasons"] == ["HISTORICAL_PIT_PROOF_MISSING"]


def test_other_blockers_preserved():
    result = overlay_row(sample(["MISSING_DELTA_PUBLICATION_DAY"]), {"isin": "FR_TEST", "mics": ["XPAR"]})
    assert result["research_j1_eligible"] is False
    assert result["decision"] == "REJECTED"
    assert result["research_rejection_reasons"] == ["MISSING_DELTA_PUBLICATION_DAY"]


@pytest.mark.parametrize("proof", [{"isin": "OTHER", "mics": ["XPAR"]}, {"isin": "FR_TEST", "mics": ["XMLI"]}])
def test_identity_guard(proof):
    with pytest.raises(ValueError):
        overlay_row(sample(), proof)


def test_missing_blocker_guard():
    row = sample()
    row["research_rejection_reasons"] = []
    with pytest.raises(ValueError):
        overlay_row(row, {"isin": "FR_TEST", "mics": ["XPAR"]})
