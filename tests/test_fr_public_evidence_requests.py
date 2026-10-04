import pandas as pd
import pytest

from service.fr.public_evidence_requests import REVIEWS, request_packet


def identity(symbol):
    return {"provider_symbol": symbol, "isin": "FRTEST", "mics": ["XPAR"], "market_reference": [
        {"versions": [{"name": "TEST", "asof_from": "2024-01-01", "asof_to": None}]}]}


def test_packet_keeps_all_candidates_and_unknown_tax():
    paths = pd.DataFrame([
        {"symbol": "ARTO.PA", "fold": 6, "entry_session": "2024-10-10", "exit_session": "2024-10-17",
         "provider_state": "BLOCKED_PRICE_PATH", "missing_price_days": ["2024-10-10"]},
        {"symbol": "ERA.PA", "fold": 6, "entry_session": "2024-07-29", "exit_session": "2024-08-05",
         "provider_state": "BLOCKED_PRICE_PATH", "missing_price_days": ["2024-07-30"]},
    ])
    tax = pd.DataFrame([{"symbol": "ARTO.PA", "isin": "FRTEST", "year": 2024, "status": "UNKNOWN_NOT_EXEMPT"}])
    result = request_packet(paths, tax, [identity(s) for s in paths.symbol], [])
    assert len(result["coverage"]) == 2
    assert result["tax"][0]["state"] == "UNKNOWN_NOT_EXEMPT"
    assert sum(r["request_paid_price"] for r in result["prices"]) == 1
    assert result["prices"][0]["state"].endswith("REJECTION_REQUIRED")
    with pytest.raises(ValueError, match="Missing identity"):
        request_packet(paths, tax, [], [])


def test_review_never_infers_exdate_from_payment_and_keeps_proposals():
    lectra = next(r for r in REVIEWS if r["symbol"] == "LSS.PA")
    assert lectra["ex_date"] is None
    assert lectra["payment_date"] == "2025-05-05"
    stif = next(r for r in REVIEWS if r["symbol"] == "ALSTI.PA")
    assert stif["state"] == "PROPOSAL_ONLY"
    assert stif["payment_date"] is None
    abc = next(r for r in REVIEWS if r["symbol"] == "ABCA.PA")
    assert abc["payment_date"] == "2025-07-10"


def test_additional_public_terms_do_not_promote_missing_exdates():
    ipsos = next(r for r in REVIEWS if r["source"] == "ipsos_paid")
    assert ipsos["cash"] == "1.85" and ipsos["payment_date"] == "2025-07-03"
    assert ipsos["ex_date"] is None
    stif = next(r for r in REVIEWS if r["source"] == "stif_balo")
    assert stif["state"].startswith("PROPOSED")
    assert stif["payment_date"] == "2025-06-02"
    assert stif["ex_date"] is None
