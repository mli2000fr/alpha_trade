import hashlib
import json

import pytest

import modelFactory.fr_eodhd_euronext_sample_audit as audit
from modelFactory.fr_eodhd_euronext_sample_audit import compare_rows, parse_reference


def test_header_mapping_separates_last_close_and_volume():
    html = '''<table id="AwlHistoricalPriceTable"><thead><tr>
    <th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Last</th><th>Close</th>
    <th>Number of shares</th></tr></thead><tbody><tr>
    <td>02/01/2025</td><td>10</td><td>1,297.00</td><td>9</td><td>10.4</td><td>10.5</td>
    <td>1,234,567</td></tr></tbody></table>'''
    rows = parse_reference(html)
    assert rows["2025-01-02"]["close"] == 10.5
    assert rows["2025-01-02"]["volume"] == 1234567
    assert rows["2025-01-02"]["high"] == 1297.


def test_missing_not_counted_as_wrong_price():
    ref = {"2025-01-02": {"open": None, "high": 10, "low": 9, "close": 10, "volume": 0}}
    got = {"2025-01-02": {"open": 10, "high": 10, "low": 9, "close": 10, "volume": 0}}
    result, differences = compare_rows(ref, got)
    assert result["counts"]["unpaired_price_rows"] == 1
    assert result["counts"].get("paired_price_rows", 0) == 0
    assert differences[0]["kind"] == "MISSING_OR_INVALID_PRICE"


def test_exact_and_practical_tolerances_distinct():
    ref = {"2025-01-02": {"open": 10, "high": 10, "low": 10, "close": 10, "volume": None}}
    got = {"2025-01-02": {"open": 10.001, "high": 10, "low": 10, "close": 10, "volume": 0}}
    result, differences = compare_rows(ref, got)
    assert result["counts"]["paired_price_rows"] == 1
    assert result["counts"]["ohlc_match_0001eur"] == 0
    assert result["counts"]["ohlc_match_10bps"] == 1
    assert result["counts"].get("volume_compared", 0) == 0
    assert differences[0]["field"] == "open"


def test_resume_fixed_sample_bounded_failures_and_progress(tmp_path, monkeypatch):
    previous = tmp_path / "old"
    previous.mkdir()
    sample = [{"symbol": s, "isin": s, "status": "active", "mics": ["XPAR"]} for s in ("A", "B")]
    (previous / "sample.json").write_text(json.dumps(sample))
    (previous / "report.json").write_text(json.dumps({"results": [dict(r, collection_status="FAILED", error="old") for r in sample]}))
    monkeypatch.setattr(audit, "verified_tls_context", lambda: object())
    monkeypatch.setattr(audit.time, "sleep", lambda _: None)
    calls = []
    def collect(candidate, output, context):
        calls.append(candidate["symbol"])
        if candidate["symbol"] == "B":
            raise TimeoutError("offline")
        return {**candidate, "collection_status": "COMPLETED", "counts": {"paired_price_rows": 1}, "by_year": {}}
    monkeypatch.setattr(audit, "collect_one", collect)
    saved = (previous / "report.json").read_bytes()
    result = audit.resume_failed(previous, tmp_path / "new", 0, 2)
    assert calls == ["A", "B", "B"]
    assert result["completed"] == 1 and result["failed"] == 1
    assert result["status"] == "PARTIAL_COLLECTION_FAILURES"
    assert (previous / "report.json").read_bytes() == saved
    assert (tmp_path / "new/sample.json").read_bytes() == (previous / "sample.json").read_bytes()
    assert len(json.loads((tmp_path / "new/progress.json").read_text())) == 2


def test_resume_rejects_changed_identity_before_output(tmp_path):
    previous = tmp_path / "old"
    previous.mkdir()
    candidate = {"symbol": "A", "isin": "FR1", "status": "active", "mics": ["XPAR"]}
    (previous / "sample.json").write_text(json.dumps([candidate]))
    (previous / "report.json").write_text(json.dumps({"results": [dict(candidate, isin="WRONG")]}))
    with pytest.raises(ValueError, match="Identité"):
        audit.resume_failed(previous, tmp_path / "new", 0)
    assert not (tmp_path / "new").exists()


def test_resume_verified_raw_success_without_optional_page(tmp_path, monkeypatch):
    previous = tmp_path / "old"
    previous.mkdir()
    candidate = {"symbol": "A", "isin": "FR1", "status": "active", "mics": ["XPAR"]}
    raw = b'{}'
    (previous / "A.encrypted.json").write_bytes(raw)
    provider = tmp_path / "provider.json"
    provider.write_bytes(b'[]')
    row = dict(candidate, collection_status="COMPLETED", instrument={"key": "test"},
               eodhd_sha256=hashlib.sha256(b'[]').hexdigest(), euronext_raw_sha256=hashlib.sha256(raw).hexdigest())
    (previous / "sample.json").write_text(json.dumps([candidate]))
    (previous / "report.json").write_text(json.dumps({"results": [row]}))
    monkeypatch.setattr(audit, "archive_path", lambda *args: provider)
    monkeypatch.setattr(audit, "decrypt_ajax", lambda *args: "html")
    monkeypatch.setattr(audit, "parse_reference", lambda _: {})
    monkeypatch.setattr(audit, "read_eodhd", lambda _: {})
    result = audit.resume_failed(previous, tmp_path / "new", 0)
    assert result["completed"] == 1
    assert result["results"][0]["previous_page_archive_present"] is False
