from datetime import date, datetime, timezone
import hashlib
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from service.fr.daily_feature_adapter_16b import (
    action_checks, assemble, identity_reasons, master_at, observed_payloads, select_bars,
)

UTC = timezone.utc
CUTOFF = datetime(2026, 10, 6, 7, tzinfo=UTC)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_verified_observation_and_future_ignored(tmp_path):
    folder = tmp_path / "artifacts/fr/operations/eodhd_daily"
    raw = {"symbol": "A.PA", "window": ["2026-10-01", "2026-10-05"], "rows": []}
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    write_json(folder / "raw" / (digest + ".json"), raw)
    obs = {"symbol": "A.PA", "window": raw["window"], "raw_sha256": digest,
           "observed_at": "2026-10-05T20:00:00+00:00", "available_at": "2026-10-05T20:00:00+00:00"}
    write_json(folder / "observations/one.json", obs)
    proofs = {}
    before = observed_payloads(folder, CUTOFF, tmp_path, proofs)
    assert len(before[0]) == 1 and not before[1]
    original_proofs = dict(proofs)
    write_json(folder / "observations/future.json", {**obs,
        "raw_sha256": "f" * 64, "observed_at": "2026-10-06T20:00:00+00:00",
        "available_at": "2026-10-06T20:00:00+00:00"})
    assert len(observed_payloads(folder, CUTOFF, tmp_path, proofs)[0]) == 1
    assert proofs == original_proofs
    (folder / "raw" / (digest + ".json")).write_text("{}")
    assert observed_payloads(folder, CUTOFF, tmp_path, {})[1]


class Calendar:
    days = [d.date() for d in pd.bdate_range("2026-09-07", "2026-10-06")]

    def session(self, day):
        assert day in self.days
        return SimpleNamespace(open_at_utc=datetime.combine(day, datetime.min.time(), UTC).replace(hour=7),
                               close_at_utc=datetime.combine(day, datetime.min.time(), UTC).replace(hour=16))

    def previous_session(self, day, nth=1):
        return self.days[self.days.index(day) - nth]

    def session_dates(self, start, end):
        return [day for day in self.days if start <= day <= end]


def payload(rows, *, kind=None, stamp="2026-10-05T20:00:00+00:00"):
    raw = {"symbol": "A.PA", "window": ["2026-09-07", "2026-10-05"], "rows": rows}
    if kind:
        raw["kind"] = kind
    return {"raw": raw, "time": datetime.fromisoformat(stamp), "observed": datetime.fromisoformat(stamp),
            "observation": {"raw_sha256": "a" * 64}, "path": stamp}


def bars():
    return [{"date": str(day), "open": 100 + i, "high": 102 + i,
             "low": 99 + i, "close": 101 + i, "volume": 1000 + i}
            for i, day in enumerate(Calendar.days[:-1])]


def test_corrections_asof_and_missing_sessions():
    rows = bars()
    corrected = [dict(row, close=row["close"] + 0.5) for row in rows]
    selected, missing = select_bars([payload(rows), payload(corrected, stamp="2026-10-06T20:00:00+00:00")],
                                   "A.PA", Calendar.days[:-1], Calendar(), CUTOFF)
    assert not missing and selected[-1]["close"] == rows[-1]["close"]
    selected, missing = select_bars([payload(rows[:-1])], "A.PA", Calendar.days[:-1], Calendar(), CUTOFF)
    assert missing == ["2026-10-05"]


def test_bad_bar_and_duplicate_fail():
    rows = bars()
    rows[-1]["volume"] = 0
    with pytest.raises(ValueError, match="ZERO_VOLUME"):
        select_bars([payload(rows)], "A.PA", Calendar.days[:-1], Calendar(), CUTOFF)
    with pytest.raises(ValueError, match="duplicate"):
        select_bars([payload(bars() + bars()[:1])], "A.PA", Calendar.days[:-1], Calendar(), CUTOFF)


def test_action_coverage_and_events():
    days = Calendar.days[:-1]
    assert not action_checks([payload([], kind="splits"), payload([], kind="div")], "A.PA", days)
    assert "INCOMPLETE_DIV_OBSERVED_COVERAGE" in action_checks([payload([], kind="splits")], "A.PA", days)
    result = action_checks([payload([{"date": "2026-09-25", "split": "2/1"}], kind="splits"),
                            payload([], kind="div")], "A.PA", days)
    assert "UNQUALIFIED_SPLITS_IN_FEATURE_WINDOW" in result


def master():
    return {"market_code": "FR_EQ", "last_observed_at": "2026-10-05T23:00:00+00:00",
            "end": "2026-10-05", "historical_continuity_confirmed": True,
            "delta_publication_continuity_confirmed": True, "anomalies": [],
            "symbols": [{"isin": "FRTEST", "market_reference": [{"mic": "XPAR", "versions": [
                {"isin": "FRTEST", "currency": "EUR", "cfi": "ESVUFN", "event": "Full", "asof_from": "2026-09-01",
                 "asof_to": None, "termination_reported": None}]}]}]}


def test_master_asof_hash_and_continuity(tmp_path):
    folder = tmp_path / "artifacts/fr/operations/fr_security_master_sync"
    state = master()
    digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    write_json(folder / "versions" / (digest + ".json"), state)
    result, reasons, errors = master_at(folder, CUTOFF, date(2026, 10, 5), tmp_path, {})
    assert result == state and not reasons and not errors
    (folder / "versions" / (digest + ".json")).write_text("{}")
    assert master_at(folder, CUTOFF, date(2026, 10, 5), tmp_path, {})[2]


def test_identity_terminated_and_ambiguous():
    identity = {"isin": "FRTEST", "mics": ["XPAR"]}
    state = master()
    assert not identity_reasons(state, identity, date(2026, 10, 5))
    version = state["symbols"][0]["market_reference"][0]["versions"][0]
    version["termination_reported"] = "2026-10-05"
    assert "DAILY_IDENTITY_TERMINATED_OR_RESERVED" in identity_reasons(state, identity, date(2026, 10, 5))


def test_terminal_other_mic_is_not_second_active_venue():
    from copy import deepcopy
    from service.fr.daily_feature_adapter_16b import identity_resolution
    identity = {"isin": "FRTEST", "mics": ["XMLI", "XPAR"]}
    state = master()
    old = deepcopy(state["symbols"][0]["market_reference"][0])
    old["mic"] = "XMLI"
    old["versions"][0].update(event="TermntdRcrd", termination_reported="2026-09-01")
    state["symbols"][0]["market_reference"].append(old)
    result = identity_resolution(state, identity, date(2026, 10, 5))
    assert result["mic"] == "XPAR" and not result["reasons"]
    old["versions"][0].update(event="Full", termination_reported=None)
    assert "DAILY_IDENTITY_VERSION_AMBIGUOUS" in identity_reasons(state, identity, date(2026, 10, 5))


def test_nominal_currency_does_not_become_quote_evidence():
    from service.fr.daily_feature_adapter_16b import identity_resolution
    state = master()
    state["symbols"][0]["market_reference"][0]["versions"][0]["currency"] = "USD"
    result = identity_resolution(state, {"isin": "FRTEST", "mics": ["XPAR"]}, date(2026, 10, 5))
    assert result["reasons"] == ["NON_EUR_NOMINAL_REQUIRES_TRADING_CURRENCY_PROOF"]
    assert not result["trading_currency_independently_verified"]


def test_assembly_reuses_formulas_but_never_promotes(tmp_path, monkeypatch):
    import service.fr.daily_feature_adapter_16b as adapter
    identity = {"research_uid": "one", "isin": "FRTEST", "provider_symbol": "A.PA", "mics": ["XPAR"]}
    from service.fr.prediction_contract_16a import FEATURES
    manifest = {"features": list(FEATURES), "universe": [identity]}
    monkeypatch.setattr(adapter, "observed_payloads", lambda folder, *args: (
        ([payload(bars())] if folder.name == "eodhd_daily" else
         [payload([], kind="div"), payload([], kind="splits")]), []))
    monkeypatch.setattr(adapter, "master_at", lambda *args: (master(), [], []))
    monkeypatch.setattr(adapter, "preflight", lambda *args, **kwargs: {"serving_allowed": False})
    result = assemble(date(2026, 10, 6), root=tmp_path, calendar=Calendar(), manifest=manifest)
    row = result["dataset"]["rows"][0]
    assert row["values"]["return_20"] == pytest.approx(121 / 101 - 1)
    assert row["values"]["traded_value_mean20_eur"] > 100000  # no premature log1p
    assert not row["tradable_at_session"]
    assert row["qualification"] != "QUALIFIED"
    assert result["report"]["features_computed_count"] == 1
    assert not result["report"]["sql_writes"]
