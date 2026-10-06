from datetime import UTC, datetime
from types import SimpleNamespace
from pathlib import Path

import pytest

import service.fr.opening_confirmation_16f as module


def protocol():
    return {"schema_version": 1, "market_code": "FR_EQ", "calendar": "XPAR", "decision_date": "2026-10-07",
            "bootstrap_dir": "artifacts/fr/a", "evidence_dir": "artifacts/fr/b", "serving_allowed": False,
            "orders_allowed": False, "sql_writes": False}


def calendar():
    return SimpleNamespace(session=lambda _: SimpleNamespace(open_at_utc=datetime(2026, 10, 7, 7, tzinfo=UTC)),
                           previous_session=lambda _: "2026-10-06")


def test_confirmation_before_opening_never_calls_audit(monkeypatch):
    monkeypatch.setattr(module, "audit", lambda *a, **kw: pytest.fail("Premature audit"))
    with pytest.raises(ValueError, match="actual XPAR"):
        module.execute(protocol(), "confirm", now=datetime(2026, 10, 6, 20, tzinfo=UTC), calendar=calendar())


def test_after_opening_uses_locked_protocol_and_retains_blocks(monkeypatch):
    captured = {}
    def fake(day, bootstrap, archive, **kwargs):
        captured.update(day=day, bootstrap=str(bootstrap), now=kwargs["now"])
        return {"status": "DECISION_AUDITED_SHADOW_BLOCKED", "serving_allowed": False, "sql_writes": False}
    monkeypatch.setattr(module, "audit", fake)
    result = module.execute(protocol(), "confirm", now=datetime(2026, 10, 7, 7, tzinfo=UTC), calendar=calendar())
    assert str(captured["day"]) == "2026-10-07"
    assert Path(captured["bootstrap"]) == Path("artifacts/fr/a")
    assert result["status"] == "DECISION_AUDITED_SHADOW_BLOCKED"
    assert len(result["protocol_sha256"]) == 64 and not result["serving_allowed"]


@pytest.mark.parametrize("key,value", [("market_code", "US_EQ"), ("serving_allowed", True), ("sql_writes", True)])
def test_protocol_cannot_enable_serving(key, value):
    plan = protocol()
    plan[key] = value
    with pytest.raises(ValueError):
        module.validate(plan)


def test_preparation_is_not_a_decision_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "observed_payloads", lambda *args: ([], []))
    monkeypatch.setattr(module, "master_at", lambda *args: ({"end": "2026-10-05"}, ["MASTER_STALE_OR_WRONG_SESSION"], []))
    monkeypatch.setattr(module, "prepare_manifest", lambda **kw: {"universe": [{"provider_symbol": "A.PA"}]})
    monkeypatch.setattr(module, "select_bars", lambda *args: ([], ["2026-10-06"]))
    result = module.execute(protocol(), "prepare", now=datetime(2026, 10, 6, 20, tzinfo=UTC), root=tmp_path, calendar=calendar())
    assert result["status"] == "WAIT_ACTUAL_OPENING"
    assert result["last_session_bars_observed_now"] == 0
    assert "decision_at" not in result and not result["serving_allowed"]
