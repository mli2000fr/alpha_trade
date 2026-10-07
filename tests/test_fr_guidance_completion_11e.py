import json

import pytest

from service.fr.guidance_completion_11e import (
    check_second_review,
    package,
    pair_direction,
    publication_day,
    resolved_manifest_records,
    screen_documents,
)
from service.fr.guidance_corpus_11d import sha


@pytest.mark.parametrize("old,new,direction", [([3,5],[-1,-1],"DOWN"),([40,40],[42,42],"UP"),
    ([12,13],[10.5,12],"UNRESOLVED"),([20,20],[18.2,20],"UNRESOLVED")])
def test_no_invented_direction_for_overlapping_bounds(old, new, direction):
    assert pair_direction(old, new) == direction


@pytest.mark.parametrize("old,new", [([3,1],[4,5]),([1,2],[float("nan"),5]),([1],[2,3])])
def test_invalid_pair(old, new):
    with pytest.raises(ValueError):
        pair_direction(old, new)


def test_transmission_is_latest_paris_day_not_original_publication():
    assert publication_day({"transmissions":{"a":"2024-01-01T23:30:00+00:00","b":"2024-01-01T08:00:00+00:00"}}) == "2024-01-02"
    with pytest.raises(ValueError):
        publication_day({"transmissions":{"a":"2024-01-01T23:30:00"}})


def review_record():
    return {"id":"example", "status":"FIRST_REVIEW_PAIR", "decision":"ACCEPT", "second_reviewer":"Human reader",
            "second_review_date":"2026-10-04", "comments":"Same forward period and scope checked in both PDFs",
            "old_is_forecast":True, "same_period_metric_scope":True, "bounds_qualifiers_correct":True,
            "not_duplicate":True, "training_eligible":False}


def test_second_review_never_grants_pit_or_training_go():
    result = check_second_review({"records":[review_record()]})
    assert result["accepted"] == ["example"]
    assert result["training_eligible"] is False
    assert "PIT_UNQUALIFIED" in result["status"]


@pytest.mark.parametrize("change", [{"decision":"PENDING"}, {"second_reviewer":None}, {"comments":""},
    {"same_period_metric_scope":False}, {"training_eligible":True}, {"status":"UNCERTAINTY_INTERVAL_REVIEW_REQUIRED"}])
def test_pending_or_unqualified_second_review_rejected(change):
    with pytest.raises(ValueError):
        check_second_review({"records":[{**review_record(), **change}]})


def test_duplicate_announcements_rejected():
    with pytest.raises(ValueError):
        check_second_review({"records":[review_record(),review_record()]})


def test_lexical_screen_is_not_semantic_rejection_or_validation(tmp_path):
    pages = tmp_path / "pages.json"
    pages.write_text(json.dumps([{"page":1,"text":"Résultats réalisés 2023 contre 2022."}]), encoding="utf-8")
    doc = {"id":"one","issuer":"Issuer","sha256":"hash","pages_path":str(pages)}
    row = screen_documents([doc])[0]
    assert row["hits"] and row["semantic_validated"] is False
    pages.write_text(json.dumps([{"page":1,"text":"Objectif confirmé."}]), encoding="utf-8")
    row = screen_documents([doc])[0]
    assert row["status"] == "NO_LEXICAL_MATCH_NOT_REJECTED"


def package_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config/research_fr"
    config.mkdir(parents=True)
    (config / "guidance_review_11d_v1.json").write_text('{"records":[]}', encoding="utf-8")
    root = tmp_path / "source"
    root.mkdir()
    pdf = root / "document.pdf"
    pdf.write_bytes(b"%PDF synthetic provenance test")
    pages = root / "pages.json"
    pages.write_text('[{"page":1,"text":"Objectif 2024 de 40 contre 30 précédemment."}]', encoding="utf-8")
    doc = {"id":"id1", "isin":"FRTEST", "issuer":"Test", "sha256":sha(pdf.read_bytes()),
           "pdf_path":str(pdf), "pages_path":str(pages), "pages":1, "url":"https://example.test/source.pdf",
           "transmissions":{"date":"2024-05-01T08:00:00+00:00"}, "observed_at":"2026-10-04T08:00:00+00:00"}
    (root / "pdf_report.json").write_text(json.dumps({"selected":1,"extracted":1,"failed":0,"documents":[doc]}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"records":[{"id":"id1","pages":[1],"status":"FIRST_REVIEW_PAIR",
        "period_end":"2024-12-31","metric":"revenue","unit":"EUR_million","old":[30,30],"new":[40,40],
        "direction":"UP","qualifiers":"Prior and new forecasts, same perimeter"}]}), encoding="utf-8")
    return root, pdf, manifest


def test_package_copies_hash_verified_evidence_but_does_not_approve_training(tmp_path, monkeypatch):
    root, pdf, manifest = package_fixture(tmp_path, monkeypatch)
    out = tmp_path / "review"
    result = package(out, manifest, roots=[root])
    assert result["first_reader_pairs"] == 1 and not result["training_eligible"]
    assert sha((out / "pdfs/id1.pdf").read_bytes()) == sha(pdf.read_bytes())
    review = json.loads((out / "second_review.json").read_text(encoding="utf-8"))
    assert review["records"][0]["decision"] == "PENDING"
    assert review["records"][0]["evidence"][0]["historical_web_available_at"] is None
    with pytest.raises(ValueError):
        package(out, manifest, roots=[root])


def test_package_rejects_changed_source_pdf(tmp_path, monkeypatch):
    root, pdf, manifest = package_fixture(tmp_path, monkeypatch)
    pdf.write_bytes(b"changed content")
    with pytest.raises(ValueError, match="hash mismatch"):
        package(tmp_path / "review", manifest, roots=[root])


def test_package_rejects_past_period_estimate(tmp_path, monkeypatch):
    root, _, manifest = package_fixture(tmp_path, monkeypatch)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["records"][0]["period_end"] = "2023-12-31"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Past period"):
        package(tmp_path / "review", manifest, roots=[root])


def test_nested_manifest_keeps_all_earlier_records_and_hashes(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"records":[{"id":"a"}]}), encoding="utf-8")
    second = tmp_path / "second.json"
    second.write_text(json.dumps({"base_manifest":str(base),"base_manifest_sha256":sha(base.read_bytes()),"records":[{"id":"b"}]}), encoding="utf-8")
    third = tmp_path / "third.json"
    third.write_text(json.dumps({"base_manifest":str(second),"base_manifest_sha256":sha(second.read_bytes()),"records":[{"id":"c"}]}), encoding="utf-8")
    assert [r["id"] for r in resolved_manifest_records(third)] == ["a","b","c"]
    base.write_text('{"records":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        resolved_manifest_records(third)


def test_manifest_duplicate_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"records":[{"id":"a"},{"id":"a"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        resolved_manifest_records(path)
