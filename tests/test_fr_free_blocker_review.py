from copy import deepcopy

from service.fr.free_blocker_review import alias_versions


def test_alias_requires_exact_isin_name_and_contiguous_ordinary_equity():
    identity = {"provider_symbol": "BNP.PA", "isin": "FR0000131104", "market_reference": [
        {"mic": "XPAR", "versions": [{"name": "BNP PARIBAS ACT.A", "cfi": "ESVUFN", "asof_from": "2020-01-01", "asof_to": None}]}]}
    alias = {"symbol": "BNP.PA", "isin": "FR0000131104", "esma_names": ["BNP PARIBAS ACT.A"], "fiscal_names": ["BNP Paribas"]}
    before = deepcopy(identity)
    assert alias_versions(identity, alias, "BNP Paribas", 2024)
    assert identity == before
    assert not alias_versions(identity, alias, "BNP Other", 2024)
    wrong = deepcopy(identity)
    wrong["isin"] = "FR_WRONG"
    assert not alias_versions(wrong, alias, "BNP Paribas", 2024)
    wrong = deepcopy(identity)
    wrong["market_reference"][0]["versions"][0]["name"] = "BNP PARIBAS SE"
    assert not alias_versions(wrong, alias, "BNP Paribas", 2024)
    wrong = deepcopy(identity)
    wrong["market_reference"][0]["versions"][0]["asof_from"] = "2024-02-01"
    assert not alias_versions(wrong, alias, "BNP Paribas", 2024)
    wrong = deepcopy(identity)
    wrong["market_reference"][0]["versions"][0]["cfi"] = "DBXXXX"
    assert not alias_versions(wrong, alias, "BNP Paribas", 2024)
