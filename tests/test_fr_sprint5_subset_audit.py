from service.fr.sprint5_subset_audit import qualify, valid_isin


def test_isin_checksum_is_not_identity_proof():
    assert valid_isin("FR0000120271")
    assert not valid_isin("FR0000120272")
    assert not valid_isin(None)


def test_subset_keeps_delisted_candidates_but_never_grants_canonical_go():
    rows = [
        {"provider_symbol": "A.PA", "reported_isin": "FR0000120271",
         "provider_status": "delisted", "verified_mic": None},
        {"provider_symbol": "B.PA", "reported_isin": None,
         "provider_status": "active", "verified_mic": None},
    ]
    bars = {"A.PA": {"valid_bars": 800, "valid_years": 4},
            "B.PA": {"valid_bars": 800, "valid_years": 4}}
    report = qualify(rows, bars, {})
    assert report["summary"]["candidate_pending_proofs"] == 1
    assert report["summary"]["candidate_current_status"] == {"delisted": 1}
    assert report["summary"]["verified_for_canonical"] == 0
    assert report["symbols"][0]["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"


def test_shared_isin_and_unreviewed_split_defer_candidates():
    rows = [{"provider_symbol": symbol, "reported_isin": "FR0000120271",
             "provider_status": "active", "verified_mic": None}
            for symbol in ("A.PA", "B.PA")]
    bars = {symbol: {"valid_bars": 800, "valid_years": 4}
            for symbol in ("A.PA", "B.PA")}
    report = qualify(rows, bars, {"A.PA": {"splits": 1}})
    assert report["summary"]["candidate_pending_proofs"] == 0
    assert all(item["status"] == "DEFERRED" for item in report["symbols"])
    assert "SPLIT_NOT_INDEPENDENTLY_VALIDATED" in report["symbols"][0]["reasons"]
