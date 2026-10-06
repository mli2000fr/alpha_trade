import pytest

from service.fr.evidence_archive_16e import available, collect, validate_url, verify_record


def test_document_date_does_not_backdate_availability():
    row = {"status": "ARCHIVED", "observed_at": "2026-10-06T19:00:00+00:00",
           "available_at": "2026-10-06T19:00:00+00:00", "document_date": "2026-07-30"}
    assert not available(row, "2026-10-06T07:00:00+00:00")
    assert available(row, "2026-10-07T07:00:00+00:00")
    row["available_at"] = "2026-07-30T00:00:00+00:00"
    with pytest.raises(ValueError):
        available(row, "2026-10-07T07:00:00+00:00")


@pytest.mark.parametrize("url", ["http://www.spie.com/", "https://bad.test/", "https://user@www.spie.com/"])
def test_only_explicit_issuer_https_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_partial_archive_records_failure_without_release(tmp_path):
    sources = [{"id": "one", "symbol": "A.PA", "url": "https://www.spie.com/good"},
               {"id": "two", "symbol": "B.PA", "url": "https://www.spie.com/bad"}]
    def fetch(url):
        if url.endswith("bad"):
            raise OSError("403")
        return b"<html>fixture</html>", "text/html", url
    output = tmp_path / "output"
    result = collect(output, {"market_code": "FR_EQ", "serving_enabled": False, "sources": sources}, fetch=fetch)
    assert result["archived"] == 1 and result["failed"] == 1
    assert not result["serving_enabled"] and not result["sql_writes"]
    first = result["records"][0]
    assert first["available_at"] == first["observed_at"]
    assert first["claim_status"] == "CURATED_REQUIRES_CONTENT_REVIEW"
    assert verify_record(first, output)
    (output / first["raw_path"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        verify_record(first, output)


def test_no_market_or_serving_override(tmp_path):
    with pytest.raises(ValueError):
        collect(tmp_path / "out", {"market_code": "US_EQ", "serving_enabled": False})
    assert not available({"status": "FAILED"}, "2026-10-06T07:00:00+00:00")
