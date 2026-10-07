import json
import sys
from datetime import date
from types import SimpleNamespace

import pytest

from service.fr.guidance_corpus_11d import pdf_stage, review_stage, select, sha, title_kind, validate_pair


def test_plain_forecast_is_not_revision():
    assert title_kind("Prévisions financières 2025") is None
    assert title_kind("Agenda prévisionnel de communication financière") is None
    assert title_kind("Calendrier prévisionnel et objectifs") is None


def test_direction_title_is_only_candidate():
    assert title_kind("Révision à la baisse des objectifs 2024") == "DOWN_TITLE_NOT_VALIDATED"
    assert title_kind("Relèvement des perspectives 2025") == "UP_TITLE_NOT_VALIDATED"
    assert title_kind("Profit warning : avertissement sur résultats") == "DOWN_TITLE_NOT_VALIDATED"
    assert title_kind("Objectifs revus pour 2025") == "REVISION_UNSPECIFIED_TITLE_NOT_VALIDATED"


def test_credit_rating_not_guidance():
    assert title_kind("Moody's abaisse la notation et les perspectives") is None


def test_selection_new_issuer_priority_and_cap():
    rows = [{"isin": isin, "id": str(i), "kind": "UP_TITLE_NOT_VALIDATED"}
            for i, isin in enumerate(["old", "new", "new", "new", "other"])]
    result = select(rows, {"old"}, per_side=3)
    assert len(result) == 3
    assert all(r["isin"] != "old" for r in result)
    assert sum(r["isin"] == "new" for r in result) == 2
    assert result == select(list(reversed(rows)), {"old"}, per_side=3)


def pair():
    return {"metric": "revenue", "unit": "EUR_million", "scope": "same group",
            "scope_comparable": True, "period_end": "2024-12-31", "old": [30, 30],
            "new": [32, 32], "old_comparator": "target", "new_comparator": "target", "direction": "UP"}


@pytest.mark.parametrize("change", [
    {"scope_comparable": False}, {"period_end": "2023-12-31"},
    {"old": [33, 31]}, {"new": [float("nan"), 32]}, {"direction": "DOWN"},
    {"new": [29, 31]}, {"old_comparator": ""},
])
def test_pair_contract_rejects_ambiguous_or_past(change):
    with pytest.raises(ValueError):
        validate_pair({**pair(), **change}, date(2024, 4, 19))


def test_qualifier_preserved_and_downward_pair():
    p = {**pair(), "old": [34.5, 34.5], "new": [35, 35],
         "old_comparator": "at_least", "new_comparator": "at_least"}
    validate_pair(p, date(2024, 4, 19))
    assert p["new_comparator"] == "at_least"
    validate_pair({**pair(), "old": [3, 4], "new": [1, 1], "direction": "DOWN",
                   "old_comparator": "low_end_of_range", "new_comparator": "around"}, date(2024, 4, 19))


def review_fixture(tmp_path):
    raw = b"%PDF synthetic evidence for provenance tests"
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(raw)
    identity = sha(raw)[:16]
    doc = {"status": "EXTRACTED", "sha256": sha(raw), "pdf_path": str(pdf_path), "pages": 2,
           "transmissions": {"amf": "2024-04-19T05:00:00+00:00"}, "isin": "FR0000000001",
           "issuer": "Fixture", "id": "release", "source_record_sha256": sha(b"metadata"),
           "download_url": "https://example.invalid/source.pdf", "observed_at": "2026-10-04T08:00:00+00:00"}
    (tmp_path / "pdf_report.json").write_text(json.dumps({"documents": [doc], "extracted": 1}))
    record = {"id": identity, "pages": [1], "date_in_document": "2024-04-19",
              "status": "COMPARABLE_FORWARD_PAIR", "reason": "Manually checked", "pairs": [pair(), pair()]}
    manifest = {"independent_second_reviewer": False, "records": [record]}
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(manifest))
    return review_path, manifest, pdf_path


def test_multiple_metrics_count_as_one_announcement_and_pit_stays_blocked(tmp_path):
    path, _, _ = review_fixture(tmp_path)
    report = review_stage(tmp_path, path)
    assert report["comparable_announcements_by_direction"] == {"UP": 1}
    assert report["records"][0]["historical_web_available_at"] is None
    assert report["records"][0]["training_eligible"] is False


@pytest.mark.parametrize("change", [{"pages": [3]}, {"status": "UNKNOWN"}, {"date_in_document": "2024-04-18"}])
def test_review_rejects_missing_page_unknown_type_and_unhandled_republication(tmp_path, change):
    path, manifest, _ = review_fixture(tmp_path)
    manifest["records"][0].update(change)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        review_stage(tmp_path, path)


def test_pdf_integrity_rejects_replaced_evidence(tmp_path):
    path, _, pdf_path = review_fixture(tmp_path)
    pdf_path.write_bytes(b"other PDF")
    with pytest.raises(ValueError, match="checksum"):
        review_stage(tmp_path, path)


def test_pdf_resume_preserves_first_observation_without_fetch(tmp_path, monkeypatch):
    _, _, pdf_path = review_fixture(tmp_path)
    old = json.loads((tmp_path / "pdf_report.json").read_text())["documents"][0]
    old["pages_path"] = str(tmp_path / "text.json")
    old["url"] = old["download_url"]
    selected = [{k: v for k, v in old.items() if k not in ("sha256", "pdf_path", "status")}]
    (tmp_path / "selected_documents.json").write_text(json.dumps(selected))
    (tmp_path / "pdf_report.json").write_text(json.dumps({"documents": [old]}))
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(
        PdfReader=lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "cached")])) )
    monkeypatch.setattr("service.fr.guidance_corpus_11d.fetch", lambda *a, **k: pytest.fail("Unexpected download"))
    monkeypatch.setattr("service.fr.guidance_corpus_11d.time.sleep", lambda _: None)
    result = pdf_stage(tmp_path)
    assert result["extracted"] == 1
    assert result["documents"][0]["observed_at"] == old["observed_at"]
    assert result["documents"][0]["reused_cached_pdf"] is True
    assert sha(pdf_path.read_bytes()) == old["sha256"]
