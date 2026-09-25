"""Sprint 12-A : aucune règle implicite, aucun fill fictif CN."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from service.market.cn_execution_contract import (
    CNExecutionContractError,
    InventoryLot,
    assess_fill_proxy,
    estimate_cost,
    prepare_buy,
    prepare_sell,
    resolve_cost_profile,
    resolve_rule,
)


@pytest.fixture
def contract_conn():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE market_execution_rules (
              rule_id INTEGER PRIMARY KEY,market_code TEXT,exchange_mic TEXT,board_code TEXT,
              valid_from DATE,valid_to DATE,currency TEXT,settlement_cycle_days INTEGER,
              buy_lot_size INTEGER,sell_lot_size INTEGER,tick_size TEXT,
              daily_price_limit_pct TEXT,short_selling_allowed INTEGER,
              same_day_sell_allowed INTEGER,metadata_json TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE cn_execution_cost_profiles (
              profile_id INTEGER PRIMARY KEY,market_code TEXT,profile_key TEXT,
              valid_from DATE,valid_to DATE,currency TEXT,source_type TEXT,
              commission_bps_buy TEXT,commission_bps_sell TEXT,commission_min_cny TEXT,
              transfer_fee_bps_buy TEXT,transfer_fee_bps_sell TEXT,
              stamp_duty_bps_sell TEXT,slippage_bps_buy TEXT,slippage_bps_sell TEXT,
              source_ref TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO market_execution_rules VALUES (
              1,'CN_A','XSHG','SH_MAIN','2018-01-01','2025-12-31','CNY',
              1,100,1,'0.01',NULL,0,0,:metadata
            )
        """), {"metadata": '{"minimum_buy_shares":100,"minimum_sell_shares":100,'
                           '"research_only":true,"rule_version":"test_v1"}'})
        conn.execute(text("""
            INSERT INTO cn_execution_cost_profiles VALUES (
              1,'CN_A','cn_a_research','2018-01-01','2025-12-31','CNY',
              'RESEARCH_PROXY','10','10','5','0','0','0','0','0','test_only'
            )
        """))
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _contracts(conn):
    rule = resolve_rule(
        conn, exchange_mic="XSHG", board_code="SH_MAIN",
        session_date=date(2024, 3, 4), allow_research_rules=True,
    )
    cost = resolve_cost_profile(
        conn, profile_key="cn_a_research", session_date=date(2024, 3, 4),
        allow_research_proxy=True,
    )
    return rule, cost


def test_rule_is_dated_and_never_falls_back_to_us_or_2026(contract_conn) -> None:
    with pytest.raises(CNExecutionContractError, match="sans opt-in"):
        resolve_rule(contract_conn, exchange_mic="XSHG", board_code="SH_MAIN",
                     session_date=date(2024, 3, 4))
    with pytest.raises(CNExecutionContractError, match="trouvé=0"):
        resolve_rule(contract_conn, exchange_mic="XSHG", board_code="SH_MAIN",
                     session_date=date(2026, 1, 2), allow_research_rules=True)
    with pytest.raises(CNExecutionContractError, match="MIC ou board"):
        resolve_rule(contract_conn, exchange_mic="XNAS", board_code="SH_MAIN",
                     session_date=date(2024, 3, 4), allow_research_rules=True)


def test_ambiguous_overlapping_rule_fails_closed(contract_conn) -> None:
    contract_conn.execute(text("""
        INSERT INTO market_execution_rules
        SELECT 2,market_code,exchange_mic,board_code,'2020-01-01','2024-12-31',
               currency,settlement_cycle_days,buy_lot_size,sell_lot_size,tick_size,
               daily_price_limit_pct,short_selling_allowed,same_day_sell_allowed,metadata_json
        FROM market_execution_rules WHERE rule_id=1
    """))
    with pytest.raises(CNExecutionContractError, match="trouvé=2"):
        resolve_rule(contract_conn, exchange_mic="XSHG", board_code="SH_MAIN",
                     session_date=date(2024, 3, 4), allow_research_rules=True)


def test_cost_profile_opt_in_and_minimum_fee(contract_conn) -> None:
    with pytest.raises(CNExecutionContractError, match="opt-in"):
        resolve_cost_profile(contract_conn, profile_key="cn_a_research",
                             session_date=date(2024, 3, 4))
    _, profile = _contracts(contract_conn)
    buy = estimate_cost(profile=profile, side="BUY", notional_cny=Decimal("100"))
    sell = estimate_cost(profile=profile, side="SELL", notional_cny=Decimal("10000"))
    assert buy.commission_cny == Decimal("5")
    assert sell.commission_cny == Decimal("10")
    assert buy.stamp_duty_cny == 0


def test_buy_lot_includes_fees_in_budget(contract_conn) -> None:
    rule, profile = _contracts(contract_conn)
    decision = prepare_buy(rule=rule, profile=profile, price_cny=Decimal("10"),
                           budget_cny=Decimal("1000"))
    assert decision.state == "REJECTED"  # 100 actions coûtent 1000 + 5 de frais
    affordable = prepare_buy(rule=rule, profile=profile, price_cny=Decimal("10"),
                             budget_cny=Decimal("1005"))
    assert affordable.state == "ORDER_CANDIDATE" and affordable.shares == 100


def test_t1_and_full_residual_odd_lot(contract_conn) -> None:
    rule, _ = _contracts(contract_conn)
    today = date(2024, 3, 4)
    lots = (InventoryLot(50, date(2024, 3, 1)), InventoryLot(100, today))
    assert prepare_sell(rule=rule, lots=lots, session_date=today,
                        requested_shares=100).state == "DEFERRED_T1"
    assert prepare_sell(rule=rule, lots=lots, session_date=today,
                        requested_shares=50).state == "REJECTED"
    residual = (InventoryLot(50, date(2024, 3, 1)),)
    assert prepare_sell(rule=rule, lots=residual, session_date=today,
                        requested_shares=50).state == "ORDER_CANDIDATE"


def test_limit_data_can_only_make_proxy_eligible_never_a_fill() -> None:
    good = assess_fill_proxy(side="BUY", bar_present=True, trading_status="TRADE",
                             limit_policy="CN_MAIN_10PCT_V1", locked_up=False, locked_down=False)
    assert good.state == "PROXY_ELIGIBLE"
    assert "NO_ORDER_BOOK_FILL_PROOF" in good.reason
    unknown = assess_fill_proxy(side="BUY", bar_present=True, trading_status="TRADE",
                                limit_policy="OBSERVED_OUTSIDE_DERIVED_LIMIT_V1",
                                locked_up=None, locked_down=None)
    assert unknown.state == "UNVERIFIABLE"
    suspended = assess_fill_proxy(side="BUY", bar_present=True,
                                  trading_status="SUSPENDED", limit_policy=None,
                                  locked_up=None, locked_down=None)
    assert suspended.state == "REJECTED"
