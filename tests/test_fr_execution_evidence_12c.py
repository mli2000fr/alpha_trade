from datetime import date

import pytest

from service.fr.execution_evidence_12c import issuer_match, standard_settlement


def test_target_calendar_not_french_holidays_and_april_boundary():
    assert standard_settlement(date(2025, 3, 28)) == date(2025, 4, 1)
    assert standard_settlement(date(2025, 4, 17)) == date(2025, 4, 23)
    assert standard_settlement(date(2024, 3, 28)) == date(2024, 4, 3)
    assert standard_settlement(date(2025, 5, 7)) == date(2025, 5, 9)  # May8 not TARGET closure
    with pytest.raises(ValueError):
        standard_settlement(date(2025, 12, 31))
    with pytest.raises(ValueError):
        standard_settlement(date(2025, 4, 18))


def identity(name="WENDEL", cfi="ESVUFN"):
    return {"provider_symbol": "MF.PA", "market_reference": [{"mic": "XPAR", "versions": [{
        "name": name, "cfi": cfi, "asof_from": "2021-06-04", "asof_to": None}]}]}


def test_exact_issuer_match_no_fuzzy_no_stapled_no_gaps():
    assert issuer_match(identity(), "Wendel", 2025)
    assert not issuer_match(identity("WENDEL SA"), "Wendel", 2025)
    assert not issuer_match(identity(cfi="DBXXXX"), "Wendel", 2025)
    row = identity()
    row["provider_symbol"] = "URW.PA"
    assert not issuer_match(row, "Wendel", 2025)
    row = identity()
    row["market_reference"][0]["versions"].append(dict(row["market_reference"][0]["versions"][0]))
    assert not issuer_match(row, "Wendel", 2025)  # overlapping identities
    row = identity()
    row["market_reference"][0]["versions"][0]["asof_from"] = "2025-02-01"
    assert not issuer_match(row, "Wendel", 2025)
