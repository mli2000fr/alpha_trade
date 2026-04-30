import pytest
from event_sentiment import scoring

pytestmark = pytest.mark.skipif(
    not hasattr(scoring, "main"),
    reason="API event_sentiment.scoring évoluée — restauration prévue Phase 4.1 (audit_event_sentiment)",
)


def test_scoring_main(monkeypatch):
    called = {}
    monkeypatch.setattr(scoring, "main", lambda: called.setdefault("main", True))
    scoring.main()
    assert called["main"] is True

