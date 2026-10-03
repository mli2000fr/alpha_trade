from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from service.fr.universe_reference_6c import _write_rows, build_benchmark, build_identities, load_policy, sector_asof

ROOT = Path(__file__).resolve().parents[1]


def test_identity_never_promotes_canonical_and_shared_isin_is_ambiguous():
    history = {
        "symbols": [
            {
                "symbol": s,
                "isin": "FR0000120073",
                "market_reference": [{"mic": "XPAR", "versions": [{"isin": "FR0000120073"}]}],
            }
            for s in ["AIR.PA", "ALIAS.PA"]
        ]
    }
    rows = build_identities(["AIR.PA", "ALIAS.PA", "MISSING.PA"], history)
    assert [r["identity_state"] for r in rows] == ["AMBIGUOUS", "AMBIGUOUS", "UNKNOWN"]
    assert all(r["instrument_id"] is None and r["research_uid"] is None for r in rows)
    unique = build_identities(["AIR.PA"], history)[0]
    assert unique["identity_state"] == "VERIFIED_RESEARCH"
    assert unique["research_uid"] == build_identities(["AIR.PA"], history)[0]["research_uid"]


def test_conflicting_historical_isin_blocks_identity():
    rows = build_identities(
        ["X.PA"],
        {
            "symbols": [
                {
                    "symbol": "X.PA",
                    "isin": "FR0000120073",
                    "market_reference": [{"mic": "XPAR", "versions": [{"isin": "FR0000120271"}]}],
                }
            ]
        },
    )
    assert rows[0]["identity_state"] == "AMBIGUOUS"


def _benchmark_data():
    days = [date(2024, 6, d) for d in [3, 4, 5, 6]]
    rows = [
        {
            "provider_symbol": s,
            "source_session_date": day.isoformat(),
            "decision_session_date": days[i + 1].isoformat(),
            "training_state": "ELIGIBLE",
        }
        for i, day in enumerate(days[:2])
        for s in ["A.PA", "B.PA"]
    ]
    bars = {
        "A.PA": {days[0].isoformat(): {"close": 10}, days[1].isoformat(): {"close": 12}},
        "B.PA": {days[0].isoformat(): {"close": 20}, days[1].isoformat(): {"close": 18}},
    }
    ids = {s: {"identity_state": "VERIFIED_RESEARCH", "research_uid": s} for s in bars}
    config = {"min_constituents": 2, "min_return_coverage": 1, "initial_level": 100}
    return days, rows, bars, ids, config


def test_benchmark_equal_weight_and_j_plus_one_availability():
    days, rows, bars, ids, config = _benchmark_data()
    daily, members = build_benchmark(rows, bars, ids, days, config)
    assert daily[0]["price_return"] == pytest.approx(0.05)
    assert daily[0]["index_level"] == pytest.approx(105)
    assert daily[0]["decision_session_date"] == "2024-06-05"
    assert all(r["eligibility_source_session"] == "2024-06-03" for r in members[:2])
    assert daily[1]["benchmark_state"] == "UNKNOWN"
    assert daily[1]["price_return"] is None


def test_future_eligibility_cannot_select_same_day_constituents():
    days, rows, bars, ids, config = _benchmark_data()
    rows[0]["source_session_date"] = "2024-06-04"
    with pytest.raises(ValueError, match="Composition"):
        build_benchmark(rows, bars, ids, days, config)


def test_quarantined_current_bar_does_not_supply_benchmark_return():
    days, rows, bars, ids, config = _benchmark_data()
    rows = [r for r in rows if not (r["provider_symbol"] == "B.PA" and r["source_session_date"] == "2024-06-04")]
    daily, _ = build_benchmark(rows, bars, ids, days, config)
    assert daily[0]["valid_return_count"] == 1
    assert daily[0]["benchmark_state"] == "UNKNOWN"


def test_sector_current_snapshot_never_backfills_history():
    row = {
        "provider_symbol": "AIR.PA",
        "taxonomy": "TEST",
        "sector_code": "INDUSTRIALS",
        "valid_from": "2020-01-01",
        "valid_to": None,
        "observed_at": "2026-10-03T12:00:00+00:00",
        "available_at": "2026-10-05T00:00:00+00:00",
    }
    assert sector_asof([row], "AIR.PA", datetime(2024, 1, 1, tzinfo=UTC))["sector_state"] == "UNKNOWN"
    assert sector_asof([row], "AIR.PA", datetime(2026, 10, 5, tzinfo=UTC))["sector_code"] == "INDUSTRIALS"
    bad = {**row, "available_at": "2026-10-02T00:00:00+00:00"}
    with pytest.raises(ValueError, match="Disponibilité"):
        sector_asof([bad], "AIR.PA", datetime(2026, 10, 5, tzinfo=UTC))


def test_policy_and_schema_are_isolated_research_only():
    policy = load_policy(ROOT / "config/universe_fr_s6c.yaml")
    assert not policy["canonical_promotion"]
    assert policy["sector"]["historical_state"] == "UNKNOWN"
    sql = (ROOT / "database/sql/fr/migration_fr_0008_reference_research.sql").read_text(encoding="utf-8")
    assert "instrument_id BIGINT UNSIGNED NULL" in sql
    assert "available_at>=observed_at" in sql
    assert "alpha_trade." not in sql


def test_artifact_compression_is_deterministic(tmp_path):
    a, b = tmp_path / "a.gz", tmp_path / "b.gz"
    rows = [{"sector_code": None, "provider_symbol": "AIR.PA"}]
    _write_rows(a, rows)
    _write_rows(b, rows)
    assert a.read_bytes() == b.read_bytes()


def test_invalid_isin_checksum_never_creates_research_uid():
    row = build_identities(["X.PA"], {"symbols": [{"symbol": "X.PA", "isin": "FR0000120074"}]})[0]
    assert row["identity_state"] == "AMBIGUOUS"
    assert row["research_uid"] is None


def test_unknown_day_breaks_benchmark_index_chain():
    days, rows, bars, ids, config = _benchmark_data()
    days += [date(2024, 6, 7), date(2024, 6, 10)]
    for symbol in bars:
        rows += [
            {
                "provider_symbol": symbol,
                "source_session_date": "2024-06-06",
                "decision_session_date": "2024-06-07",
                "training_state": "ELIGIBLE",
            },
            {
                "provider_symbol": symbol,
                "source_session_date": "2024-06-07",
                "decision_session_date": "2024-06-10",
                "training_state": "INELIGIBLE",
            },
        ]
        bars[symbol].update({"2024-06-06": {"close": 10}, "2024-06-07": {"close": 11}})
    daily, _ = build_benchmark(rows, bars, ids, days + [date(2024, 6, 11)], config)
    known = [r for r in daily if r["benchmark_state"] == "KNOWN"]
    assert [r["segment_id"] for r in known] == [1, 2]
    assert known[-1]["index_level"] == pytest.approx(110)
