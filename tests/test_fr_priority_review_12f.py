import json

import pandas as pd
import pytest

from service.fr import priority_review_12f
from service.fr.priority_review_12f import priority_table, verified_sources


def frame():
    return pd.DataFrame([
        {"fold": 6, "entry_session": "2025-01-02", "research_uid": "a", "policy": "oracle_top20_long",
         "future_label_used": False, "tax_qualified": False, "symbol": "A.PA", "isin": "BE_TEST",
         "candidate_rank": 2, "tax_year": 2025},
        {"fold": 6, "entry_session": "2025-01-02", "research_uid": "b", "policy": "oracle_top20_long",
         "future_label_used": False, "tax_qualified": True, "symbol": "B.PA", "isin": "FR_TEST",
         "candidate_rank": 1, "tax_year": 2025}])


def test_priorities_use_intentions_not_country_prefix_or_returns():
    values = frame()
    before = values.copy(deep=True)
    result = priority_table(values)
    assert result.symbol.tolist() == ["A.PA"]
    assert result.first_8_intentions.tolist() == [1]
    assert result.years.tolist() == [[2025]]
    pd.testing.assert_frame_equal(values, before)


def test_duplicate_and_future_label_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        priority_table(pd.concat([frame(), frame()]))
    values = frame()
    values.loc[0, "future_label_used"] = True
    with pytest.raises(ValueError, match="Future"):
        priority_table(values)


def test_modified_source_rejected(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"changed")
    (tmp_path / "report.json").write_text(json.dumps({"sources": {"x": {
        "path": str(source), "sha256": "wrong", "status": "ARCHIVED_NOT_PROMOTED"}}}))
    with pytest.raises(ValueError, match="hash"):
        verified_sources(tmp_path)


def test_partial_reading_never_promotes_tax_ca_or_pit(tmp_path, monkeypatch):
    sources = {key: {"status": "ARCHIVED_NOT_PROMOTED", "sha256": value}
               for key, value in priority_review_12f.REVIEWED_HASHES.items()}
    monkeypatch.setattr(priority_review_12f, "verified_sources", lambda _: sources)
    intentions = tmp_path / "intentions.parquet"
    frame().to_parquet(intentions)
    output = tmp_path / "review"
    report = priority_review_12f.run(output, tmp_path, intentions)
    assert report["tax_rows_promoted"] == report["economic_paths_qualified"] == 0
    assert not report["canonical_writes"]
    reviewed = report["reviewed"][0]
    assert not reviewed["tax"]["annual_2024_2025_eligibility_promoted"]
    assert not reviewed["corporate_actions"]["complete_independent_event_coverage"]
    assert reviewed["corporate_actions"]["available_at_for_strategy"] is None
    with pytest.raises(FileExistsError):
        priority_review_12f.run(output, tmp_path, intentions)


def test_unread_document_cannot_inherit_manual_conclusion(tmp_path, monkeypatch):
    sources = {key: {"status": "ARCHIVED_NOT_PROMOTED", "sha256": value}
               for key, value in priority_review_12f.REVIEWED_HASHES.items()}
    sources["xfab_2024"]["sha256"] = "new-document"
    monkeypatch.setattr(priority_review_12f, "verified_sources", lambda _: sources)
    with pytest.raises(ValueError, match="manually reviewed"):
        priority_review_12f.run(tmp_path / "review", tmp_path, tmp_path / "not-read.parquet")
