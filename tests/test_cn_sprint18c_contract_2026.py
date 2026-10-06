"""Sprint 18-C : contrat 2026 borné, recherche seulement et sans broker."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from dataIntegrityEngine import cn_sprint18c_contract_2026 as migration
from service.market.cn_execution_contract import (
    CNExecutionContractError, estimate_cost, resolve_cost_profile, resolve_rule,
)


@pytest.fixture
def conn(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as db:
        db.execute(text("""CREATE TABLE market_execution_rules (
            rule_id INTEGER PRIMARY KEY,market_code TEXT,exchange_mic TEXT,
            board_code TEXT,valid_from DATE,valid_to DATE,currency TEXT,
            settlement_cycle_days INTEGER,buy_lot_size INTEGER,sell_lot_size INTEGER,
            tick_size TEXT,daily_price_limit_pct TEXT,short_selling_allowed INTEGER,
            same_day_sell_allowed INTEGER,metadata_json TEXT)"""))
        db.execute(text("""CREATE TABLE cn_execution_cost_profiles (
            profile_id INTEGER PRIMARY KEY,market_code TEXT,profile_key TEXT,
            valid_from DATE,valid_to DATE,currency TEXT,source_type TEXT,
            commission_bps_buy TEXT,commission_bps_sell TEXT,commission_min_cny TEXT,
            transfer_fee_bps_buy TEXT,transfer_fee_bps_sell TEXT,
            stamp_duty_bps_sell TEXT,slippage_bps_buy TEXT,slippage_bps_sell TEXT,
            source_ref TEXT,metadata_json TEXT)"""))
        for idx, (mic, board, increment, minimum) in enumerate(migration.SPECS, 1):
            db.execute(text("""INSERT INTO market_execution_rules VALUES (
                :id,'CN_A',:mic,:board,'2026-07-06','2026-12-31','CNY',
                1,:increment,1,'0.01',NULL,0,0,:metadata)"""), {
                "id": idx, "mic": mic, "board": board,
                "increment": increment, "metadata": json.dumps({
                    "minimum_buy_shares": minimum, "minimum_sell_shares": minimum,
                    "research_only": True, "rule_version": migration.VERSION,
                    "source_type": "OFFICIAL_RULES_RESEARCH_EXECUTION",
                    "source_ref": migration.RULE_SOURCES[(mic, board)],
                    "limits": "instrument_session_only", "not_broker_verified": True,
                }),
            })
        db.execute(text("""INSERT INTO cn_execution_cost_profiles VALUES (
            1,'CN_A','cn_a_research','2026-07-06','2026-12-31','CNY',
            'RESEARCH_PROXY','10','10','5','0.1','0.1','5','2','2',
            'research_proxy_only',:metadata)"""), {"metadata": json.dumps({
                "version": "cn_a_research_2026_shadow_v1",
                "not_verified_broker": True,
                "exchange_handling_in_commission_not_added_twice": True,
                "public_fees_ref": migration.FEE_SOURCE_SSE,
                "szse_fees_ref": migration.FEE_SOURCE_SZSE,
                "commission_assumption": "Sprint 11-B 10bps/min5",
                "slippage_assumption_bps_per_side": 2,
            })})
    monkeypatch.setattr(migration, "_database_guard", lambda _conn: None)
    with engine.connect() as db:
        yield db
    engine.dispose()


def test_migration_is_two_idempotent_inserts_without_live_switch() -> None:
    statements = migration._statements(migration.MIGRATION.read_text(encoding="utf-8"))
    assert len(statements) == 2
    assert all("ON DUPLICATE KEY UPDATE" in statement for statement in statements)
    sql_only = "\n".join(
        line for statement in statements for line in statement.splitlines()
        if not line.lstrip().startswith("--")
    )
    assert "live_enabled" not in sql_only
    assert "UPDATE markets" not in sql_only


def test_all_four_boards_and_cost_proxy_are_qualified(conn) -> None:
    result = migration.audit(conn)
    assert result["status"] == "CN_2026_SHADOW_RESEARCH_CONTRACT_READY_NOT_LIVE"
    assert len(result["rules"]) == 4
    assert result["cost_profile"]["source_type"] == "RESEARCH_PROXY"
    for mic, board, increment, minimum in migration.SPECS:
        rule = resolve_rule(
            conn, exchange_mic=mic, board_code=board,
            session_date=date(2026, 10, 8), allow_research_rules=True,
        )
        assert (rule.buy_increment, rule.minimum_buy_shares) == (increment, minimum)
        with pytest.raises(CNExecutionContractError, match="opt-in"):
            resolve_rule(conn, exchange_mic=mic, board_code=board,
                         session_date=date(2026, 10, 8))
    with pytest.raises(CNExecutionContractError, match="trouvé=0"):
        resolve_rule(conn, exchange_mic="XSHG", board_code="SH_MAIN",
                     session_date=date(2026, 6, 30), allow_research_rules=True)
    with pytest.raises(CNExecutionContractError, match="trouvé=0"):
        resolve_rule(conn, exchange_mic="XSHG", board_code="SH_MAIN",
                     session_date=date(2027, 1, 1), allow_research_rules=True)
    with pytest.raises(CNExecutionContractError, match="opt-in"):
        resolve_cost_profile(conn, profile_key="cn_a_research",
                             session_date=date(2026, 10, 8))
    profile = resolve_cost_profile(conn, profile_key="cn_a_research",
                                   session_date=date(2026, 10, 8),
                                   allow_research_proxy=True)
    assert estimate_cost(profile=profile, side="BUY",
                         notional_cny=Decimal("10000")).total_cny == Decimal("12.1")
    assert estimate_cost(profile=profile, side="SELL",
                         notional_cny=Decimal("10000")).total_cny == Decimal("17.1")


def test_divergent_or_overlapping_contract_fails_closed(conn) -> None:
    conn.execute(text("""UPDATE market_execution_rules SET buy_lot_size=50
        WHERE exchange_mic='XSHG' AND board_code='SH_MAIN'"""))
    with pytest.raises(RuntimeError, match="divergente"):
        migration.audit(conn)


def test_guard_rejects_non_cn_database_before_any_install() -> None:
    class WrongDatabase:
        def execute(self, _statement):
            class Result:
                def scalar_one(self):
                    return "alpha_trade"
            return Result()

    with pytest.raises(RuntimeError, match="interdit"):
        migration._database_guard(WrongDatabase())
