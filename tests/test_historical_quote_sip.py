from datetime import date, datetime, timezone
import json

import pytest
from sqlalchemy import create_engine, text

from common import quote_quality as quality
from dataIntegrityEngine import sync_latest_quotes as sync
from database import selector_reference as selector


@pytest.fixture
def row(tmp_path, monkeypatch):
    monkeypatch.setattr(quality, "ARCHIVE_ROOT", tmp_path / "artifacts" / "quotes")
    day = date(2026, 10, 16)
    quote = {"bp": 25.83, "ap": 25.90, "bs": 1500, "as": 200,
             "t": "2026-10-16T19:59:59.287617986Z"}
    now = datetime(2026, 10, 17, 20, 0)
    value = sync._build_quote_snapshot_row("KE", quote, fallback_utc_now=now)
    value.update(quality.archive_quote("KE", day, "sip", quote, now), quality_status="VALID_RTH")
    value["source_timestamp"] = value["quote_timestamp"]
    return value


def test_qualified_sip_and_sealed_raw(row):
    assert quality.qualified_quote(row, row["quote_date"])
    path = quality.ARCHIVE_ROOT.parent.parent / row["raw_payload_path"]
    archived = json.loads(path.read_text())
    assert archived["quote"]["t"] == "2026-10-16T19:59:59.287617986Z"
    assert archived["request"]["feed"] == "sip"
    assert "KEY" not in path.read_text()
    path.write_text("{}")
    assert not quality.qualified_quote(row, row["quote_date"])


@pytest.mark.parametrize("change", [
    {"feed": "iex"}, {"provider": None}, {"quality_status": None},
    {"quote_timestamp": None, "source_timestamp": None},
    {"source_timestamp": datetime(2026,10,16,19,30)},
    {"source_timestamp": datetime(2026,10,16,20,1)},
    {"source_timestamp": datetime(2026,10,15,19,59)},
    {"bid_size": 0}, {"bid_price": float("nan")},
    {"ask_price": 1}, {"spread_bps": -1}, {"raw_payload_path": "../outside.json"},
])
def test_invalid_or_unknown_quote_cannot_qualify(row, change):
    assert not quality.qualified_quote({**row, **change}, row["quote_date"])


def test_timestamp_microseconds_prevent_rounding_outside_session(row):
    rounded_legacy = {**row, "quote_timestamp": datetime(2026,10,16,20,0)}
    assert quality.qualified_quote(rounded_legacy, row["quote_date"])


def test_archive_must_match_the_stored_quote_not_only_have_a_valid_hash(row):
    altered = {**row, "bid_price": 25.80}
    altered["spread_bps"] = sync._compute_spread_bps(altered["bid_price"],altered["ask_price"])
    assert not quality.qualified_quote(altered, row["quote_date"])
    assert not quality.qualified_quote({**row,"symbol":"WRONG"}, row["quote_date"])


def test_alembic_quote_branch_is_targetable_without_unrelated_migrations():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.iterate_revisions("0106_quote_provenance","0088_us_fact_instrument_constraints"))
    assert [r.revision for r in revisions] == ["0106_quote_provenance"]
    assert script.get_heads() == ["0107_merge_quote_provenance"]


def test_us_quote_publisher_cannot_publish_us_source_into_another_market():
    from common.publish_tradable_universe import publish_full_tradable_universe
    with pytest.raises(ValueError, match="US_EQ"):
        publish_full_tradable_universe(object(),snapshot_date=date(2026,10,16),market_code="FR_EQ")


def test_sip_summary_is_not_labeled_iex():
    from ihm.services.run_summary import build_run_summary_caption, get_run_summary_detail_lines
    record = {"step_key":"sync_latest_quotes", "run_summary":{
        "quotes_feed":"sip", "quote_iex_vs_consolidated_status":"ok",
        "quote_iex_vs_consolidated_bps":2.5, "quote_iex_vs_consolidated_observations":10}}
    caption = build_run_summary_caption(record)
    assert "sip" in caption.lower() and "iex" not in caption.lower()
    assert any("quotes SIP" in line for line in get_run_summary_detail_lines(record))


def test_no_feed_fallback(monkeypatch):
    monkeypatch.setattr("common.config_loader.load_config", lambda: {"market_data":{"quotes_historical_feed":"sip"}})
    assert quality.historical_quote_feed() == "sip"
    with pytest.raises(ValueError, match="aucun fallback"):
        quality.historical_quote_feed("unknown")
    seen = []
    def fetch(symbol, **kwargs):
        seen.append(kwargs["feed"])
        raise RuntimeError("HTTP 403")
    monkeypatch.setattr(sync, "fetch_latest_historical_quote_in_window", fetch)
    with pytest.raises(RuntimeError, match="403"):
        sync._fetch_near_close_quote_for_session("KE", date(2026,10,16), session=None)
    assert seen == ["sip"]


def test_future_sip_window_fails_before_network(monkeypatch):
    monkeypatch.setattr(sync, "list_symbols_for_source", lambda **kw: pytest.fail("No collection expected"))
    with pytest.raises(ValueError, match="15 minutes"):
        sync.sync_latest_quotes(from_date=date(2100,1,4), to_date=date(2100,1,4), feed="sip")


def test_resume_requalifies_iex_and_unknown_even_when_day_exists(row, monkeypatch):
    engine = create_engine("sqlite://")
    columns = {key: "TEXT" for key in row}
    with engine.begin() as c:
        c.execute(text("CREATE TABLE stock_quote_snapshots (" + ",".join(f'{k} {v}' for k,v in columns.items()) + ")"))
        c.execute(text("INSERT INTO stock_quote_snapshots (" + ",".join(row) + ") VALUES (" + ",".join(":"+k for k in row) + ")"),
                  {k: (v.isoformat() if isinstance(v,(date,datetime)) else v) for k,v in row.items()})
    monkeypatch.setattr(selector,"get_sqlalchemy_engine",lambda:engine)
    args = dict(from_date=row["quote_date"],to_date=row["quote_date"],expected_dates=[row["quote_date"]],required_feed="sip")
    assert selector.get_quote_snapshot_resume_state("KE", **args)["is_complete"]
    with engine.begin() as c:
        c.execute(text("UPDATE stock_quote_snapshots SET feed='iex'"))
    assert selector.get_quote_snapshot_resume_state("KE", **args)["missing_days"] == 1
    with engine.begin() as c:
        c.execute(text("UPDATE stock_quote_snapshots SET feed=NULL"))
    assert selector.get_quote_snapshot_resume_state("KE", **args)["missing_days"] == 1


def test_legacy_schema_cannot_silently_discard_provenance(row, monkeypatch):
    from sqlalchemy import Table, MetaData, Column, String, Date
    legacy = Table("stock_quote_snapshots",MetaData(),Column("symbol",String),Column("quote_date",Date))
    monkeypatch.setattr(selector,"get_stock_quote_snapshots_table",lambda:legacy)
    with pytest.raises(RuntimeError, match="Migration 0106"):
        selector.upsert_quote_snapshots([row])
