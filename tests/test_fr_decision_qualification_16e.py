from datetime import UTC, date, datetime
import hashlib
import json
from types import SimpleNamespace

import pytest

from service.fr.decision_qualification_16e import audit, evidence_at


def test_future_opening_cannot_be_declared_observed(tmp_path):
    calendar = SimpleNamespace(session=lambda day: SimpleNamespace(open_at_utc=datetime(2026, 10, 7, 7, tzinfo=UTC)))
    with pytest.raises(ValueError, match="has not occurred"):
        audit(date(2026, 10, 7), tmp_path, tmp_path, now=datetime(2026, 10, 6, 20, tzinfo=UTC), calendar=calendar)


def test_source_and_review_must_both_be_known(tmp_path):
    raw = b"fixture"
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "proof").write_bytes(raw)
    source = {"id": "A", "symbol": "A.PA", "status": "ARCHIVED", "raw_path": "proof",
              "sha256": digest, "observed_at": "2026-10-06T19:00:00+00:00",
              "available_at": "2026-10-06T19:00:00+00:00"}
    (tmp_path / "report.json").write_text(json.dumps({"market_code": "FR_EQ", "serving_enabled": False,
                                                     "records": [source]}), encoding="utf-8")
    review = {"market_code": "FR_EQ", "serving_enabled": False, "reviewed_at": "2026-10-06T20:00:00+00:00",
              "records": [{"id": "A", "sha256": digest}]}
    result = evidence_at(tmp_path, review, datetime(2026, 10, 6, 19, 30, tzinfo=UTC))
    assert result["archived_count"] == 1 and result["reviewed_terms_known_count"] == 0
    result = evidence_at(tmp_path, review, datetime(2026, 10, 7, 7, tzinfo=UTC))
    assert result["reviewed_terms_known_count"] == 1
    assert not result["records"][0]["action_adjustment_qualified"]
    (tmp_path / "proof").write_bytes(b"bad")
    with pytest.raises(ValueError, match="checksum"):
        evidence_at(tmp_path, review, datetime(2026, 10, 7, 7, tzinfo=UTC))
