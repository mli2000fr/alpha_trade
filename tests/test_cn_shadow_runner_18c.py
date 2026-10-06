"""Sprint 18-C : Oracle prospectif, plan figé et shadow sans broker."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from service.market import cn_shadow_runner_18c as runner
from service.market.cn_execution_contract import CNExecutionContractError

DAY = date(2024, 3, 5)
PUBLISHED = datetime(2024, 3, 4, 8, 0, tzinfo=UTC)
CUTOFF = datetime(2024, 3, 5, 1, 15, tzinfo=UTC)


def _setup_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    statements = [
        "CREATE TABLE instruments (instrument_id INTEGER,market_code TEXT,exchange_mic TEXT,"
        "instrument_type TEXT,currency TEXT,listing_date DATE,delisting_date DATE)",
        "CREATE TABLE instrument_provider_symbols (provider_symbol TEXT,created_at DATETIME,"
        "instrument_id INTEGER,provider TEXT,valid_from DATE,valid_to DATE)",
        "CREATE TABLE market_execution_rules (rule_id INTEGER,market_code TEXT,exchange_mic TEXT,"
        "board_code TEXT,valid_from DATE,valid_to DATE,currency TEXT,settlement_cycle_days INTEGER,"
        "buy_lot_size INTEGER,sell_lot_size INTEGER,tick_size TEXT,daily_price_limit_pct TEXT,"
        "short_selling_allowed INTEGER,same_day_sell_allowed INTEGER,metadata_json TEXT)",
        "CREATE TABLE cn_execution_cost_profiles (profile_id INTEGER,market_code TEXT,"
        "profile_key TEXT,valid_from DATE,valid_to DATE,currency TEXT,source_type TEXT,"
        "commission_bps_buy TEXT,commission_bps_sell TEXT,commission_min_cny TEXT,"
        "transfer_fee_bps_buy TEXT,transfer_fee_bps_sell TEXT,stamp_duty_bps_sell TEXT,"
        "slippage_bps_buy TEXT,slippage_bps_sell TEXT,source_ref TEXT)",
        "CREATE TABLE market_sessions (market_code TEXT,session_date DATE,session_status TEXT,"
        "close_at_utc DATETIME)",
        "CREATE TABLE stock_bars_daily (instrument_id INTEGER,market_code TEXT,`date` DATE,"
        "`open` TEXT,`close` TEXT,volume TEXT,trading_status TEXT,data_adjustment TEXT,"
        "data_source TEXT,source_payload_hash TEXT,available_at DATETIME)",
        "CREATE TABLE cn_daily_price_limits (instrument_id INTEGER,session_date DATE,"
        "policy_code TEXT,locked_up INTEGER,locked_down INTEGER,source TEXT,available_at DATETIME)",
        "CREATE TABLE cn_corporate_actions (instrument_id INTEGER,ex_date DATE,"
        "classification_status TEXT,available_at DATETIME)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text("INSERT INTO instruments VALUES (123,'CN_A','XSHG','equity','CNY','2010-01-01',NULL)"))
        conn.execute(text("INSERT INTO instrument_provider_symbols VALUES "
                          "('sh.600000','2024-03-01 00:00:00',123,'baostock','2010-01-01',NULL)"))
        conn.execute(text("INSERT INTO market_sessions VALUES "
                          "('CN_A','2024-03-05','open','2024-03-05 07:00:00'),"
                          "('CN_A','2024-03-06','open','2024-03-06 07:00:00')"))
    return engine


def _oracle(tmp_path):
    folder = tmp_path / "oracle" / DAY.isoformat()
    folder.mkdir(parents=True)
    frame = pd.DataFrame([{
        "decision_date": DAY.isoformat(), "exchange": "SSE", "code": "600000",
        "board_code": "SH_MAIN", "oracle_top20": True, "oracle_oos": True,
        "score_available_at_utc": "2024-03-04T07:50:00+00:00",
        "model_trained_through": "2023-12-31",
    }])
    export = folder / "oracle_top20.parquet"
    frame.to_parquet(export, index=False)
    report = {
        "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": DAY.isoformat(),
        "score_available_at_utc": "2024-03-04T07:50:00+00:00",
        "export_published_at_utc": PUBLISHED.isoformat(),
        "decision_cutoff_utc": CUTOFF.isoformat(),
        "candidate_export_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
        "quality": {"top20": 1},
    }
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return folder.parent


def _contracts_and_bars(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO market_execution_rules VALUES ("
                          "1,'CN_A','XSHG','SH_MAIN','2018-01-01','2025-12-31','CNY',"
                          "1,100,1,'0.01',NULL,0,0,:metadata)"),
                     {"metadata": json.dumps({"minimum_buy_shares": 100,
                                               "minimum_sell_shares": 100,
                                               "research_only": True,
                                               "rule_version": "test_v1"})})
        conn.execute(text("INSERT INTO cn_execution_cost_profiles VALUES ("
                          "1,'CN_A','cn_a_research','2018-01-01','2025-12-31','CNY',"
                          "'RESEARCH_PROXY','10','10','5','0','0','0','0','0','test')"))
        for day, close in (("2024-03-05", "10.5"), ("2024-03-06", "11")):
            conn.execute(text("INSERT INTO stock_bars_daily VALUES ("
                              "123,'CN_A',:day,'10',:close,'100000','TRADE','raw',"
                              "'baostock','abc',:available)"),
                         {"day": day, "close": close, "available": day + " 07:20:00"})
            conn.execute(text("INSERT INTO cn_daily_price_limits VALUES ("
                              "123,:day,'CN_MAIN_10PCT_V1',0,0,'derived',:available)"),
                         {"day": day, "available": day + " 07:25:00"})


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    engine = _setup_db()
    monkeypatch.setattr(runner, "_engine", lambda _engine: (engine, False))
    root = _oracle(tmp_path)
    output = tmp_path / "shadow"
    plan_path = output / "plans" / f"{DAY}.json"
    yield engine, root, output, plan_path
    engine.dispose()


def test_plan_is_frozen_before_cutoff_and_detects_tampering(pilot) -> None:
    _engine, root, _output, plan_path = pilot
    report = runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                                 now=datetime(2024, 3, 4, 10, 0, tzinfo=UTC),
                                 sample_size=1, budget_cny=Decimal("10000"))
    assert report["status"] == "FROZEN_RESEARCH_ONLY"
    assert report["plans"][0]["intent"]["symbol"] == "sh.600000"
    assert runner.load_frozen_plan(plan_path)["plans"][0].intent.instrument_id == 123
    with pytest.raises(ValueError, match="déjà présent"):
        runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                            sample_size=1)
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    raw["plans"][0]["intent"]["symbol"] = "sh.999999"
    plan_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(RuntimeError, match="déterministe"):
        runner.load_frozen_plan(plan_path)


def test_plan_after_cutoff_is_refused(pilot) -> None:
    _engine, root, _output, plan_path = pilot
    with pytest.raises(RuntimeError, match="pré-cutoff"):
        runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                            now=datetime(2024, 3, 5, 2, 0, tzinfo=UTC), sample_size=1)
    assert not plan_path.exists()


def test_contract_gate_then_attempt_and_later_mark(pilot) -> None:
    engine, root, output, plan_path = pilot
    runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                        now=datetime(2024, 3, 4, 10, 0, tzinfo=UTC), sample_size=1)
    blocked = runner.contract_readiness(decision=DAY, boards=[("XSHG", "SH_MAIN")])
    assert blocked["status"] == "BLOCKED_CONTRACT"
    assert runner.assess_frozen_session(
        plan_path=plan_path, output_root=output,
        now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC))["status"] == "BLOCKED_CONTRACT"
    assert not (output / "attempts").exists()
    _contracts_and_bars(engine)
    assert runner.contract_readiness(decision=DAY, boards=[("XSHG", "SH_MAIN")])["status"] == "READY_FOR_RESEARCH_ATTEMPT"
    with pytest.raises(CNExecutionContractError, match="opt-in"):
        runner.assess_frozen_session(
            plan_path=plan_path, output_root=output,
            now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC))
    with pytest.raises(RuntimeError, match="avant la clôture"):
        runner.assess_frozen_session(
            plan_path=plan_path, output_root=output,
            now=datetime(2024, 3, 5, 6, 0, tzinfo=UTC),
            allow_research_rules=True, allow_research_proxy=True)
    attempted = runner.assess_frozen_session(
        plan_path=plan_path, output_root=output,
        now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC),
        allow_research_rules=True, allow_research_proxy=True)
    assert attempted["states"] == {"HYPOTHETICAL_FILL": 1}
    attempt_file = output / "attempts" / DAY.isoformat() / f"cn18c-{DAY}-123.json"
    assert json.loads(attempt_file.read_text(encoding="utf-8"))["not_broker_execution"]
    marked = runner.mark_frozen_session(
        plan_path=plan_path, mark_session=date(2024, 3, 6), output_root=output,
        now=datetime(2024, 3, 6, 8, 0, tzinfo=UTC))
    assert marked["states"] == {"MARKED_PRICE_ONLY": 1}
    mark_file = output / "marks" / DAY.isoformat() / "2024-03-06" / f"cn18c-{DAY}-123.json"
    assert json.loads(mark_file.read_text(encoding="utf-8"))["mark"]["mark_close_cny"] == "11"


def test_observation_preflight_waits_for_close_and_never_writes_attempt(pilot) -> None:
    engine, root, output, plan_path = pilot
    runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                        now=datetime(2024, 3, 4, 10, 0, tzinfo=UTC), sample_size=1)
    _contracts_and_bars(engine)
    early = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 5, 6, 0, tzinfo=UTC))
    assert early["status"] == "WAITING_FOR_CLOSE"
    assert early["authorizes_attempt"] is False
    assert not (output / "attempts").exists()
    after = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC))
    assert after["status"] == "OBSERVATIONS_INSPECTED"
    assert after["planned"] == after["observed_bars"] == 1
    assert after["issue_count"] == 0
    assert after["observations"][0]["trading_status"] == "TRADE"
    assert after["observations"][0]["volume_shares"] == "100000"
    assert after["observations"][0]["limit_policy"] == "CN_MAIN_10PCT_V1"
    assert after["database_modified"] is False and after["broker_called"] is False
    assert after["authorizes_attempt"] is False
    assert not (output / "attempts").exists()


def test_observation_preflight_reports_missing_bar_without_imputing_fill(pilot) -> None:
    engine, root, output, plan_path = pilot
    runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                        now=datetime(2024, 3, 4, 10, 0, tzinfo=UTC), sample_size=1)
    _contracts_and_bars(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM stock_bars_daily WHERE `date`='2024-03-05'"))
    report = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC))
    assert report["status"] == "OBSERVATIONS_INSPECTED"
    assert report["observed_bars"] == 0
    assert report["issues"] == [{"intent_id": f"cn18c-{DAY}-123",
                                  "reason": "bar_not_available"}]
    assert report["observations"][0]["status"] == "BAR_NOT_AVAILABLE"
    assert report["authorizes_attempt"] is False
    assert not (output / "attempts").exists()


def test_observation_preflight_distinguishes_future_session_from_missing_current(pilot) -> None:
    engine, root, output, plan_path = pilot
    runner.prepare_plan(decision=DAY, oracle_root=root, output_path=plan_path,
                        now=datetime(2024, 3, 4, 10, 0, tzinfo=UTC), sample_size=1)
    _contracts_and_bars(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM market_sessions WHERE session_date='2024-03-05'"))
    future = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 4, 11, 0, tzinfo=UTC))
    assert future["status"] == "WAITING_FOR_SESSION"
    current = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 5, 8, 0, tzinfo=UTC))
    assert current["status"] == "BLOCKED_SESSION"
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO market_sessions VALUES "
                          "('CN_A','2024-03-05','open',NULL),"
                          "('CN_A','2024-03-05','open',NULL)"))
    ambiguous_future = runner.observation_readiness(
        plan_path=plan_path, now=datetime(2024, 3, 4, 11, 0, tzinfo=UTC))
    assert ambiguous_future["status"] == "BLOCKED_SESSION"
    assert not (output / "attempts").exists()
