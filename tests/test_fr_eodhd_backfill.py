from __future__ import annotations

import gzip
import hashlib
import json

from service.fr import eodhd_backfill
from service.fr.eodhd_quality import audit
from service.fr.import_eodhd_archive import archive_rows


def test_fr_backfill_archives_three_families_and_resumes(monkeypatch, tmp_path):
    monkeypatch.setenv("EODHD_API_TOKEN", "SECRET_TEST_ONLY")
    calls = []

    def fake_fetch(endpoint, token, params, *, pace):
        calls.append(endpoint)
        if endpoint == "exchange-symbol-list/PA":
            if params.get("delisted") == "1":
                return []
            return [{"Code": "AIR", "Currency": "EUR", "Type": "Common Stock", "Isin": "FR0000132577"},
                    {"Code": "ETF", "Currency": "EUR", "Type": "ETF"}]
        if endpoint == "eod/AIR.PA":
            return [{"date": "2016-01-04", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100}]
        return []

    monkeypatch.setattr(eodhd_backfill, "_fetch", fake_fetch)
    first = eodhd_backfill.run(root=tmp_path, start="2016-01-01", end="2016-01-31",
                               workers=1, pace=0.2)
    assert first["selected"] == 1
    assert first["completed"] == 1
    assert first["failed"] == 0
    assert first["eod_rows"] == 1
    assert calls.count("eod/AIR.PA") == 1
    second = eodhd_backfill.run(root=tmp_path, start="2016-01-01", end="2016-01-31",
                                workers=1, pace=0.2)
    assert second["skipped"] == 1
    assert calls.count("eod/AIR.PA") == 1
    key = hashlib.sha256(b"AIR.PA").hexdigest()[:16]
    meta = json.loads((tmp_path / "symbols" / f"{key}.json").read_text(encoding="utf-8"))
    with gzip.open(tmp_path / meta["payloads"]["eod"]["file"], "rt", encoding="utf-8") as stream:
        assert json.load(stream)[0]["date"] == "2016-01-04"
    assert "SECRET_TEST_ONLY" not in (tmp_path / "summary.json").read_text(encoding="utf-8")
    eodhd_backfill._atomic_json(tmp_path / "quality_report.json", audit(tmp_path))
    _, index_rows = archive_rows(tmp_path)
    assert len(index_rows) == 3


def test_fr_backfill_rejects_duplicate_provider_codes(monkeypatch, tmp_path):
    monkeypatch.setenv("EODHD_API_TOKEN", "SECRET_TEST_ONLY")
    row = {"Code": "AIR", "Currency": "EUR", "Type": "Common Stock"}
    def fake_fetch(endpoint, token, params, *, pace):
        return [row]
    monkeypatch.setattr(eodhd_backfill, "_fetch", fake_fetch)
    import pytest
    with pytest.raises(RuntimeError, match="réutilisés"):
        eodhd_backfill.run(root=tmp_path, start="2016-01-01", end="2016-01-31",
                           workers=1, pace=0.2)
