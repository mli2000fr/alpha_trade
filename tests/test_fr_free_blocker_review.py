import hashlib
import json
from copy import deepcopy

import pytest

from service.fr.free_blocker_review import alias_versions, reuse_verified_source


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


def test_reuse_keeps_observation_date_and_checks_hash(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    raw = old / "A.html"
    raw.write_bytes(b"FRTEST")
    row = {"url": "https://issuer.example/a", "path": str(raw),
           "sha256": hashlib.sha256(b"FRTEST").hexdigest(), "observed_at": "2026-10-03T00:00:00Z",
           "status": "ARCHIVED_MANUAL_IDENTITY_REVIEW_NOT_PRICE_FEED"}
    (old / "report.json").write_text(json.dumps({"sources": {"A": row}}))
    alias = {"symbol": "A", "url": row["url"]}
    reused = reuse_verified_source(alias, new, [old])
    assert reused["observed_at"] == row["observed_at"]
    assert (new / "A.html").read_bytes() == b"FRTEST"
    assert reuse_verified_source(dict(alias, url="https://issuer.example/other"), new, [old]) is None
    raw.write_bytes(b"CHANGED")
    with pytest.raises(ValueError, match="modifiée"):
        reuse_verified_source(alias, new, [old])
